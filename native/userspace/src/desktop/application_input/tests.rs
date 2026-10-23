use super::*;
use crate::desktop::{
    keyboard::Keyboard,
    surfaces::{DENIED, INVALID, OK, OPEN},
};

fn open(s: &mut Surfaces<'_>, slot: u64, generation: u64) -> u64 {
    s.apply(slot, generation, Frame::new(OPEN, 1, 0)).0.handle
}
fn poll(
    q: &mut Queues,
    s: &mut Surfaces<'_>,
    slot: u64,
    generation: u64,
    sequence: u64,
    handle: u64,
) -> Frame {
    let (mut reply, index) = s.input_request(slot, generation, Frame::new(INPUT, sequence, handle));
    if let Some(i) = index {
        q.drain(i, s, &mut reply);
    }
    reply
}

#[test]
fn exact_input_authority_cannot_cross_read_replay_or_advance_on_rejection() {
    let mut cells = [0; 384];
    let mut s = Surfaces::new(&mut cells);
    let a = open(&mut s, 4, 1);
    let b = open(&mut s, 5, 1);
    let mut q = Queues::new();
    q.sync(&s);
    q.push(0, b'A');
    q.push(1, b'B');
    for (slot, generation, seq, handle) in [
        (5, 1, 2, a),
        (4, 2, 2, a),
        (4, 0, 2, a),
        (4, 1, 3, a),
        (4, 1, 2, b),
        (3, 1, 2, a),
        (6, 1, 2, a),
        (4, u64::MAX, 2, a),
    ] {
        assert_eq!(
            poll(&mut q, &mut s, slot, generation, seq, handle).status,
            DENIED
        );
    }
    let reply = poll(&mut q, &mut s, 4, 1, 2, a);
    assert_eq!((reply.status, reply.len, reply.data[0]), (OK, 1, b'A'));
    assert_eq!(poll(&mut q, &mut s, 4, 1, 2, a).status, DENIED);
    assert_eq!(poll(&mut q, &mut s, 5, 1, 2, b).data[0], b'B');
}

#[test]
fn request_shape_and_legacy_profile_reject_input_without_consumption() {
    let mut cells = [0; 384];
    let mut s = Surfaces::new(&mut cells);
    let h = open(&mut s, 4, 1);
    let f = Frame::new(INPUT, 2, h);
    assert!(Frame::decode(&f.encode()).is_none());
    assert_eq!(Frame::decode_mode::<true>(&f.encode()), Some(f));
    assert_eq!(s.apply(4, 1, f).0.status, INVALID);
    for case in 0..7 {
        let mut bad = f;
        match case {
            0 => bad.status = 1,
            1 => bad.offset = 1,
            2 => bad.len = 1,
            3 => bad.data[31] = 1,
            4 => bad.sequence = 0,
            5 => bad.sequence = u64::MAX,
            _ => bad.op = 2,
        }
        assert_eq!(s.input_request(4, 1, bad).0.status, INVALID);
    }
    assert_eq!(s.input_request(4, 1, f).1, Some(0));
}

#[test]
fn queues_are_bounded_ordered_and_scrub_consumed_bytes() {
    let mut cells = [0; 384];
    let mut s = Surfaces::new(&mut cells);
    let h = open(&mut s, 4, 1);
    let mut q = Queues::new();
    q.sync(&s);
    for round in 0..6u8 {
        for n in 0..64u8 {
            q.push(0, b' ' + (n + round) % 90);
        }
        for batch in 0..2u64 {
            let r = poll(&mut q, &mut s, 4, 1, 2 + u64::from(round) * 2 + batch, h);
            assert_eq!((r.offset, r.len), (0, 32));
            for n in 0..32 {
                assert_eq!(r.data[n], b' ' + (n as u8 + batch as u8 * 32 + round) % 90);
            }
        }
        assert!(q.first.bytes.iter().all(|&b| b == 0));
        assert_eq!(q.first.len, 0);
    }
}

#[test]
fn overflow_and_focus_loss_cancel_only_the_affected_owner() {
    let mut cells = [0; 384];
    let mut s = Surfaces::new(&mut cells);
    let a = open(&mut s, 4, 1);
    let b = open(&mut s, 5, 1);
    let mut q = Queues::new();
    q.sync(&s);
    for _ in 0..65 {
        q.push(0, b'9');
    }
    q.push(1, b'7');
    let r = poll(&mut q, &mut s, 4, 1, 2, a);
    assert_eq!((r.offset, r.len), (RESET, 0));
    q.push(0, b'3');
    q.push(0, b'\r');
    q.push(0, b'4');
    assert_eq!(poll(&mut q, &mut s, 4, 1, 3, a).data[0], b'4');
    q.focus_lost(Some(2));
    assert_eq!(poll(&mut q, &mut s, 5, 1, 2, b).offset, RESET);
    assert_eq!(poll(&mut q, &mut s, 4, 1, 4, a).offset, 0);
    q.push(1, b'8');
    q.push(1, b'\r');
    q.push(1, b'2');
    assert_eq!(poll(&mut q, &mut s, 5, 1, 3, b).data[0], b'2');
}

#[test]
fn reset_cancellation_and_queued_bytes_cannot_survive_replacement_or_retirement() {
    let mut cells = [0; 384];
    let mut s = Surfaces::new(&mut cells);
    let old = open(&mut s, 4, 1);
    let b = open(&mut s, 5, 1);
    let mut q = Queues::new();
    q.sync(&s);
    q.push(0, b'X');
    q.push(1, b'Y');
    q.reset();
    assert_eq!(poll(&mut q, &mut s, 5, 1, 2, b).offset, RESET);
    assert!(s.retire(0, 1));
    assert_eq!(q.sync(&s), 1);
    assert!(q.first.bytes.iter().all(|&b| b == 0));
    let fresh = open(&mut s, 4, 2);
    q.sync(&s);
    q.push(0, b'N');
    assert_eq!(poll(&mut q, &mut s, 4, 1, 2, old).status, DENIED);
    let r = poll(&mut q, &mut s, 4, 2, 2, fresh);
    assert_eq!((r.offset, r.len, r.data[0]), (0, 1, b'N'));
    for byte in [0, 1, 2, 4, 9, 10, 27, 127, 255] {
        q.push(0, byte);
    }
    assert_eq!(poll(&mut q, &mut s, 4, 2, 3, fresh).len, 0);
}

fn key(f: &mut Fence, k: &mut Keyboard, code: u8) -> Option<u8> {
    if f.feed(code) {
        k.feed(code)
    } else {
        k.cancel_prefix();
        None
    }
}
#[test]
fn held_keys_and_modifiers_do_not_cross_focus_until_release() {
    let mut f = Fence::new();
    let mut k = Keyboard::new();
    key(&mut f, &mut k, 0x2a);
    assert_eq!(key(&mut f, &mut k, 0x1e), Some(b'A'));
    f.boundary();
    k.focus_reset();
    assert_eq!(key(&mut f, &mut k, 0x1e), None);
    assert_eq!(key(&mut f, &mut k, 0x2a), None);
    assert_eq!(key(&mut f, &mut k, 0x30), Some(b'b'));
    key(&mut f, &mut k, 0x9e);
    key(&mut f, &mut k, 0xaa);
    assert_eq!(key(&mut f, &mut k, 0x1e), Some(b'a'));
    key(&mut f, &mut k, 0x1d);
    f.boundary();
    k.focus_reset();
    assert_eq!(key(&mut f, &mut k, 0x1d), None);
    assert_eq!(key(&mut f, &mut k, 0x2e), Some(b'c'));
}

#[test]
fn extended_release_and_partial_prefix_boundary_do_not_create_stuck_keys() {
    let mut f = Fence::new();
    let mut k = Keyboard::new();
    key(&mut f, &mut k, 0xe0);
    assert_eq!(key(&mut f, &mut k, 0x1c), Some(b'\r'));
    f.boundary();
    k.focus_reset();
    key(&mut f, &mut k, 0xe0);
    assert_eq!(key(&mut f, &mut k, 0x1c), None);
    assert_eq!(key(&mut f, &mut k, 0x30), Some(b'b'));
    key(&mut f, &mut k, 0xe0);
    key(&mut f, &mut k, 0x9c);
    key(&mut f, &mut k, 0xe0);
    f.boundary();
    k.focus_reset();
    assert_eq!(key(&mut f, &mut k, 0x1c), None);
    key(&mut f, &mut k, 0xe0);
    key(&mut f, &mut k, 0x9c);
    assert_eq!(key(&mut f, &mut k, 0x1c), Some(b'\r'));
    key(&mut f, &mut k, 0xe0);
    assert_eq!(key(&mut f, &mut k, 0x1c), Some(b'\r'));
}

#[test]
fn pause_prefixes_and_caps_state_do_not_damage_fresh_focus_input() {
    let mut f = Fence::new();
    let mut k = Keyboard::new();
    for b in [0xe1, 0x1d, 0x45, 0xe1, 0x9d, 0xc5] {
        assert_eq!(key(&mut f, &mut k, b), None);
    }
    assert_eq!(key(&mut f, &mut k, 0x1e), Some(b'a'));
    key(&mut f, &mut k, 0x9e);
    key(&mut f, &mut k, 0x3a);
    key(&mut f, &mut k, 0xba);
    f.boundary();
    k.focus_reset();
    assert_eq!(key(&mut f, &mut k, 0x1e), Some(b'A'));
}

#[test]
fn controller_reset_discards_partial_prefix_but_retains_known_held_fence() {
    let mut q = Queues::new();
    let mut k = Keyboard::new();
    assert_eq!(key(&mut q.fence, &mut k, 0x1e), Some(b'a'));
    key(&mut q.fence, &mut k, 0xe0);
    q.reset();
    k = Keyboard::new();
    assert_eq!(key(&mut q.fence, &mut k, 0x30), Some(b'b'));
    assert_eq!(key(&mut q.fence, &mut k, 0x1e), None);
    key(&mut q.fence, &mut k, 0x9e);
    assert_eq!(key(&mut q.fence, &mut k, 0x1e), Some(b'a'));
    key(&mut q.fence, &mut k, 0xe1);
    q.reset();
    k = Keyboard::new();
    assert_eq!(key(&mut q.fence, &mut k, 0x2e), Some(b'c'));
}
