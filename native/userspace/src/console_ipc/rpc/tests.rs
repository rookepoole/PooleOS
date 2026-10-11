use super::*;
use crate::console_ipc::Kind;
use std::{vec, vec::Vec};

const ENDPOINT: u64 = 0x100010002;
const REQUEST: u64 = 0x100030001;
const REPLY: u64 = 0x100020001;
fn message(kind: Kind) -> Message {
    Message::new(kind, 1, &[]).unwrap()
}
fn transport(server: bool) -> Transport {
    Transport::new(ENDPOINT, Peer::from_packed(0x100000002).unwrap(), server)
}
fn envelope(message: Message, reply: u64) -> [u8; ENVELOPE_BYTES] {
    let mut wire = [0; ENVELOPE_BYTES];
    for (i, value) in [2u64, 1, reply, BYTES as u64].iter().enumerate() {
        wire[i * 8..i * 8 + 8].copy_from_slice(&value.to_le_bytes());
    }
    wire[32..].copy_from_slice(&message.encode());
    wire
}
struct Kernel {
    result: (u64, u64),
    output: Option<[u8; ENVELOPE_BYTES]>,
    calls: Vec<(u64, u64, Vec<u8>)>,
}
impl Kernel {
    fn new(result: (u64, u64)) -> Self {
        Self {
            result,
            output: None,
            calls: Vec::new(),
        }
    }
}
impl Calls for Kernel {
    fn invoke(&mut self, n: u64, h: u64, wire: &mut [u8]) -> (u64, u64) {
        self.calls.push((n, h, wire.to_vec()));
        if let Some(output) = self.output {
            wire.copy_from_slice(&output);
        }
        self.result
    }
}

#[test]
fn client_begin_pressure_and_pending_take_preserve_one_request() {
    let (mut t, mut k) = (transport(false), Kernel::new((6, 0)));
    let request = message(Kind::Close);
    for _ in 0..4 {
        assert_eq!(t.send(request, &mut k), Ok(false));
    }
    assert_eq!(k.calls, vec![(10, ENDPOINT, request.encode().to_vec()); 4]);
    k.result = (0, REQUEST);
    assert_eq!(t.send(request, &mut k), Ok(true));
    let count = k.calls.len();
    assert_eq!(t.send(request, &mut k), Err(Error::Transport));
    assert_eq!(k.calls.len(), count);
    k.result = (6, 0);
    for _ in 0..4 {
        assert_eq!(t.receive(&mut k), Ok(None));
        assert_eq!(t.pending, REQUEST);
    }
    k.result = (0, ENVELOPE_BYTES as u64);
    k.output = Some(envelope(message(Kind::Closed), 0));
    assert_eq!(t.receive(&mut k), Ok(Some(message(Kind::Closed))));
    assert_eq!(
        (k.calls.last().unwrap().0, k.calls.last().unwrap().1),
        (11, REQUEST)
    );
    assert_eq!(t.pending, 0);
}

#[test]
fn only_exact_kernel_revocation_is_a_terminal_revoked_outcome() {
    for (status, value, expected) in [
        (9, 0, Error::Revoked),
        (9, 1, Error::Transport),
        (8, 0, Error::Transport),
        (10, 0, Error::Transport),
        (11, 0, Error::Transport),
        (5, 0, Error::Transport),
    ] {
        let (mut t, mut k) = (transport(false), Kernel::new((0, REQUEST)));
        t.send(message(Kind::Read), &mut k).unwrap();
        k.result = (status, value);
        assert_eq!(t.receive(&mut k), Err(expected));
        if expected == Error::Revoked {
            assert_eq!(t.pending, 0);
            let count = k.calls.len();
            assert_eq!(t.receive(&mut k), Err(Error::Transport));
            assert_eq!(k.calls.len(), count);
        }
    }
    let (mut s, mut k) = (transport(true), Kernel::new((9, 0)));
    assert_eq!(s.receive(&mut k), Err(Error::Transport));
}

#[test]
fn service_requires_authenticated_sender_and_nonzero_reply_authority() {
    let good = envelope(message(Kind::Read), REPLY);
    for reply in [0, REQUEST, 0x20001, 0x100020000, u64::MAX] {
        let (mut s, mut k) = (transport(true), Kernel::new((0, 64)));
        k.output = Some(envelope(message(Kind::Read), reply));
        assert!(s.receive(&mut k).is_err());
        assert_eq!(s.pending, 0);
    }
    for at in [0, 7, 8, 15, 24, 31, 32, 39, 63] {
        let (mut s, mut k) = (transport(true), Kernel::new((0, 64)));
        let mut bad = good;
        bad[at] ^= 1;
        k.output = Some(bad);
        assert!(s.receive(&mut k).is_err(), "{at}");
        assert_eq!(s.pending, 0);
    }
    let (mut s, mut k) = (transport(true), Kernel::new((0, 64)));
    k.output = Some(good);
    assert_eq!(s.receive(&mut k), Ok(Some(message(Kind::Read))));
    assert_eq!(s.pending, REPLY);
    assert_eq!((k.calls[0].0, k.calls[0].1), (7, ENDPOINT));
}

#[test]
fn service_keeps_exact_reply_under_pressure_and_consumes_token_once() {
    let (mut s, mut k) = (transport(true), Kernel::new((0, 64)));
    k.output = Some(envelope(message(Kind::Close), REPLY));
    s.receive(&mut k).unwrap();
    let count = k.calls.len();
    assert_eq!(s.receive(&mut k), Err(Error::Transport));
    assert_eq!(k.calls.len(), count);
    k.output = None;
    k.result = (6, 0);
    let reply = message(Kind::Closed);
    for _ in 0..4 {
        assert_eq!(s.send(reply, &mut k), Ok(false));
        assert_eq!(s.pending, REPLY);
    }
    assert_eq!(
        &k.calls[1..],
        vec![(8, REPLY, reply.encode().to_vec()); 4].as_slice()
    );
    k.result = (0, 32);
    assert_eq!(s.send(reply, &mut k), Ok(true));
    assert_eq!(s.pending, 0);
    let count = k.calls.len();
    assert_eq!(s.send(reply, &mut k), Err(Error::Transport));
    assert_eq!(k.calls.len(), count);
}

#[test]
fn successful_take_consumes_request_but_rejects_forged_completion_envelope() {
    let good = envelope(message(Kind::Closed), 0);
    for at in [0, 7, 8, 15, 16, 23, 24, 31, 32, 39, 63] {
        let (mut t, mut k) = (transport(false), Kernel::new((0, REQUEST)));
        t.send(message(Kind::Close), &mut k).unwrap();
        let mut bad = good;
        bad[at] ^= 1;
        k.output = Some(bad);
        k.result = (0, 64);
        assert!(t.receive(&mut k).is_err(), "{at}");
        assert_eq!(t.pending, 0);
    }
}

#[test]
fn unexpected_status_lengths_or_token_shapes_never_qualify_success() {
    for result in [
        (0, 0),
        (0, 32),
        (0, REPLY),
        (0, 0x30001),
        (0, 0x100030000),
        (6, 1),
        (4, 0),
    ] {
        let (mut t, mut k) = (transport(false), Kernel::new(result));
        assert_eq!(t.send(message(Kind::Read), &mut k), Err(Error::Transport));
        assert_eq!(t.pending, 0);
    }
    for result in [(0, 0), (0, 32), (0, 63), (0, 65), (6, 1), (4, 0)] {
        let (mut s, mut k) = (transport(true), Kernel::new(result));
        assert_eq!(s.receive(&mut k), Err(Error::Transport));
    }
    for result in [(0, 0), (0, 31), (0, 33), (6, 1), (5, 0)] {
        let (mut s, mut k) = (transport(true), Kernel::new((0, 64)));
        k.output = Some(envelope(message(Kind::Close), REPLY));
        s.receive(&mut k).unwrap();
        k.output = None;
        k.result = result;
        assert_eq!(s.send(message(Kind::Closed), &mut k), Err(Error::Transport));
        assert_eq!(s.pending, REPLY);
    }
}
