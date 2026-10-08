use super::*;
use crate::capability_ipc::reply::{HEADER_BYTES, Operation, RECEIVE_BYTES};
mod requests;

struct Wire {
    data: [u8; RECEIVE_BYTES],
    read_fault: Option<usize>,
    write_fault: Option<usize>,
    accesses: usize,
}
impl Wire {
    fn new() -> Self {
        Self {
            data: [0x5a; RECEIVE_BYTES],
            read_fault: None,
            write_fault: None,
            accesses: 0,
        }
    }
    fn word(&self, n: usize) -> u64 {
        u64::from_le_bytes(self.data[n * 8..n * 8 + 8].try_into().unwrap())
    }
}
impl Memory for Wire {
    fn read(&mut self, address: u64) -> Result<u8, Status> {
        self.accesses += 1;
        let i = (address - BASE) as usize;
        if self.read_fault == Some(i) {
            Err(Status::Fault)
        } else {
            Ok(self.data[i])
        }
    }
    fn write(&mut self, address: u64, byte: u8) -> Result<(), Status> {
        self.accesses += 1;
        let i = (address - BASE) as usize;
        if self.write_fault == Some(i) {
            Err(Status::Fault)
        } else {
            self.data[i] = byte;
            Ok(())
        }
    }
}
fn setup() -> (Space, u64, u64, u64, Wire) {
    let mut s = space();
    let back = s.create_endpoint(id(0)).unwrap();
    let endpoint = s.create_endpoint(id(1)).unwrap();
    let send = s.derive(id(1), endpoint, id(0), Rights::SEND).unwrap();
    (s, back, endpoint, send, Wire::new())
}
fn request(s: &mut Space, send: u64, back: u64, m: &mut Wire) {
    assert_eq!(
        s.message(
            caller(0),
            send,
            BASE,
            MAX_BYTES,
            Operation::Request { reply_to: back },
            m
        ),
        (Status::Ok, MAX_BYTES as u64)
    );
}
fn receive(s: &mut Space, endpoint: u64, m: &mut Wire) -> u64 {
    assert_eq!(
        s.message(
            caller(1),
            endpoint,
            BASE,
            RECEIVE_BYTES,
            Operation::Receive,
            m
        ),
        (Status::Ok, RECEIVE_BYTES as u64)
    );
    assert_eq!((m.word(0), m.word(1), m.word(3)), (0, 1, MAX_BYTES as u64));
    m.word(2)
}

#[test]
fn authenticated_sender_is_snapshot_identity_not_user_payload_or_current_liveness() {
    let (mut s, _, endpoint, send, mut m) = setup();
    m.data.fill(0xff);
    assert_eq!(
        s.transfer(caller(0), send, BASE, 8, true, &mut m),
        (Status::Ok, 8)
    );
    s.detach(id(0)).unwrap();
    assert_eq!(
        s.message(
            caller(1),
            endpoint,
            BASE,
            RECEIVE_BYTES,
            Operation::Receive,
            &mut m
        ),
        (Status::Ok, 40)
    );
    assert_eq!(
        (m.word(0), m.word(1), m.word(2), m.word(3), m.word(4)),
        (0, 1, 0, 8, u64::MAX)
    );
    let other = s.derive(id(1), endpoint, id(2), Rights::SEND).unwrap();
    assert_eq!(
        s.transfer(caller(2), other, BASE, 8, true, &mut m),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.message(
            caller(1),
            endpoint,
            BASE,
            RECEIVE_BYTES,
            Operation::Receive,
            &mut m
        ),
        (Status::Ok, 40)
    );
    assert_eq!((m.word(0), m.word(1)), (2, 1));
}

#[test]
fn reply_is_task_local_typed_single_use_and_not_permanent_send_authority() {
    let (mut s, back, endpoint, send, mut m) = setup();
    request(&mut s, send, back, &mut m);
    let token = receive(&mut s, endpoint, &mut m);
    assert_eq!(token, 0x100020001);
    for c in [
        caller(0),
        caller(2),
        Caller {
            root: 0x999000,
            ..caller(1)
        },
        Caller {
            generation: 2,
            ..caller(1)
        },
    ] {
        assert_eq!(
            s.message(c, token, BASE, 8, Operation::Reply, &mut m),
            (Status::Denied, 0)
        );
    }
    for bad in [
        0,
        endpoint,
        token ^ (1 << 32),
        token | (1 << 24),
        token + CAPS as u64,
    ] {
        assert_eq!(
            s.message(caller(1), bad, BASE, 8, Operation::Reply, &mut m),
            (Status::Denied, 0)
        );
    }
    assert_eq!(
        s.transfer(caller(1), token, BASE, 8, true, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.derive(id(1), token, id(2), Rights::SEND),
        Err(Error::Denied)
    );
    assert_eq!(
        s.prepare_wait(caller(1), token, Readiness::Writable),
        Err(Status::Denied)
    );
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.message(
            caller(0),
            back,
            BASE,
            RECEIVE_BYTES,
            Operation::Receive,
            &mut m
        ),
        (Status::Ok, 40)
    );
    assert_eq!((m.word(0), m.word(1), m.word(2)), (1, 1, 0));
    request(&mut s, send, back, &mut m);
    let next = receive(&mut s, endpoint, &mut m);
    assert_eq!(next, token + (1 << 32));
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.message(caller(1), next, 0, 0, Operation::Discard, &mut m),
        (Status::Ok, 0)
    );
    assert_eq!(
        s.message(caller(1), next, 0, 0, Operation::Discard, &mut m),
        (Status::Denied, 0)
    );
}

#[test]
fn requester_needs_owned_receive_endpoint_and_authenticated_identity_before_copy() {
    let (mut s, back, endpoint, send, mut m) = setup();
    let borrowed = s.derive(id(1), endpoint, id(0), Rights::RECEIVE).unwrap();
    let before = (s.tables, s.objects);
    for reply_to in [0, send, borrowed, back ^ (1 << 32)] {
        assert_eq!(
            s.message(
                caller(0),
                send,
                BASE,
                8,
                Operation::Request { reply_to },
                &mut m
            ),
            (Status::Denied, 0)
        );
    }
    assert_eq!(
        s.message(
            Caller {
                root: image(1).root_physical,
                ..caller(0)
            },
            send,
            BASE,
            8,
            Operation::Request { reply_to: back },
            &mut m
        ),
        (Status::Denied, 0)
    );
    assert_eq!((s.tables, s.objects), before);
    assert_eq!(m.accesses, 0);
}

#[test]
fn every_request_and_reply_input_fault_preserves_exact_queue_and_authority() {
    for i in 0..MAX_BYTES {
        let (mut s, back, endpoint, send, mut m) = setup();
        let before = (s.tables, s.objects);
        m.read_fault = Some(i);
        assert_eq!(
            s.message(
                caller(0),
                send,
                BASE,
                MAX_BYTES,
                Operation::Request { reply_to: back },
                &mut m
            ),
            (Status::Fault, 0)
        );
        assert_eq!((s.tables, s.objects), before);
        m.read_fault = None;
        request(&mut s, send, back, &mut m);
        let token = receive(&mut s, endpoint, &mut m);
        let before = (s.tables, s.objects);
        m.read_fault = Some(i);
        assert_eq!(
            s.message(caller(1), token, BASE, MAX_BYTES, Operation::Reply, &mut m),
            (Status::Fault, 0)
        );
        assert_eq!((s.tables, s.objects), before);
        m.read_fault = None;
        assert_eq!(
            s.message(caller(1), token, BASE, MAX_BYTES, Operation::Reply, &mut m),
            (Status::Ok, MAX_BYTES as u64)
        );
    }
}

#[test]
fn every_envelope_output_fault_leaves_token_unminted_and_message_intact() {
    for i in 0..RECEIVE_BYTES {
        let (mut s, back, endpoint, send, mut m) = setup();
        request(&mut s, send, back, &mut m);
        let before = (s.tables, s.objects);
        m.write_fault = Some(i);
        assert_eq!(
            s.message(
                caller(1),
                endpoint,
                BASE,
                RECEIVE_BYTES,
                Operation::Receive,
                &mut m
            ),
            (Status::Fault, i as u64)
        );
        assert_eq!((s.tables, s.objects), before);
        assert_eq!(
            s.message(caller(1), 0x100020001, BASE, 8, Operation::Reply, &mut m),
            (Status::Denied, 0)
        );
        m.write_fault = None;
        assert_eq!(receive(&mut s, endpoint, &mut m), 0x100020001);
        assert_eq!(&m.data[HEADER_BYTES..], &[0x5a; MAX_BYTES]);
    }
}

#[test]
fn short_or_legacy_receive_cannot_lose_reply_ownership_or_payload() {
    let (mut s, back, endpoint, send, mut m) = setup();
    request(&mut s, send, back, &mut m);
    let before = (s.tables, s.objects);
    let accesses = m.accesses;
    assert_eq!(
        s.transfer(caller(1), endpoint, BASE, MAX_BYTES, false, &mut m),
        (Status::Denied, 0)
    );
    for n in 1..RECEIVE_BYTES {
        assert_eq!(
            s.message(caller(1), endpoint, BASE, n, Operation::Receive, &mut m),
            (Status::TooSmall, RECEIVE_BYTES as u64)
        );
    }
    assert_eq!((s.tables, s.objects), before);
    assert_eq!(m.accesses, accesses);
    assert_ne!(receive(&mut s, endpoint, &mut m), 0);
}

#[test]
fn full_reply_mailbox_retains_token_without_reading_then_retry_consumes_once() {
    let (mut s, back, endpoint, send, mut m) = setup();
    request(&mut s, send, back, &mut m);
    let token = receive(&mut s, endpoint, &mut m);
    for _ in 0..DEPTH {
        assert_eq!(
            s.transfer(caller(0), back, BASE, 8, true, &mut m),
            (Status::Ok, 8)
        );
    }
    let before = (s.tables, s.objects);
    let accesses = m.accesses;
    m.read_fault = Some(0);
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Again, 0)
    );
    assert_eq!((s.tables, s.objects), before);
    assert_eq!(m.accesses, accesses);
    assert_eq!(
        s.transfer(caller(0), back, BASE, 8, false, &mut m),
        (Status::Ok, 8)
    );
    m.read_fault = None;
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
        (Status::Denied, 0)
    );
}

#[test]
fn reply_table_quota_and_explicit_discard_allow_recovery_without_dropping_requests() {
    let (mut s, back, endpoint, send, mut m) = setup();
    let mut tokens = [0; CAPS];
    for token in &mut tokens {
        request(&mut s, send, back, &mut m);
        *token = receive(&mut s, endpoint, &mut m);
    }
    request(&mut s, send, back, &mut m);
    let before = (s.tables, s.objects);
    let accesses = m.accesses;
    assert_eq!(
        s.message(
            caller(1),
            endpoint,
            BASE,
            RECEIVE_BYTES,
            Operation::Receive,
            &mut m
        ),
        (Status::Again, 0)
    );
    assert_eq!((s.tables, s.objects), before);
    assert_eq!(m.accesses, accesses);
    assert_eq!(
        s.message(caller(1), tokens[0], 0, 0, Operation::Discard, &mut m),
        (Status::Ok, 0)
    );
    assert_eq!(receive(&mut s, endpoint, &mut m), tokens[0] + (1 << 32));
}

#[test]
fn reply_generation_exhaustion_and_detach_never_reset_high_water_marks() {
    let (mut s, back, endpoint, send, mut m) = setup();
    request(&mut s, send, back, &mut m);
    for r in &mut s.tables[1].replies {
        r.generation = u32::MAX;
    }
    let before = (s.tables, s.objects);
    assert_eq!(
        s.message(
            caller(1),
            endpoint,
            BASE,
            RECEIVE_BYTES,
            Operation::Receive,
            &mut m
        ),
        (Status::Again, 0)
    );
    assert_eq!((s.tables, s.objects), before);
    s.detach(id(1)).unwrap();
    s.attach(
        TaskId {
            generation: 2,
            ..id(1)
        },
        image(1),
    )
    .unwrap();
    assert!(
        s.tables[1]
            .replies
            .iter()
            .all(|r| r.generation == u32::MAX && r.value.is_none())
    );
}

#[test]
fn requester_and_endpoint_revocation_reclaim_tokens_and_reject_reuse() {
    for mode in 0..4 {
        let (mut s, back, endpoint, send, mut m) = setup();
        request(&mut s, send, back, &mut m);
        let token = receive(&mut s, endpoint, &mut m);
        match mode {
            0 => s.close(id(0), back).unwrap(),
            1 => s.destroy(id(0), back).unwrap(),
            2 => s.detach(id(0)).unwrap(),
            _ => s.destroy(id(1), endpoint).unwrap(),
        }
        assert!(s.tables[1].replies.iter().all(|r| r.value.is_none()));
        assert_eq!(s.tables[1].replies[0].generation, 1);
        let before = m.accesses;
        assert_eq!(
            s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m),
            (Status::Denied, 0)
        );
        assert_eq!(m.accesses, before);
    }
}

#[test]
fn cancelled_queued_request_keeps_historical_sender_but_cannot_mint_a_reply() {
    for mode in 0..3 {
        let (mut s, back, endpoint, send, mut m) = setup();
        request(&mut s, send, back, &mut m);
        match mode {
            0 => s.close(id(0), back).unwrap(),
            1 => s.destroy(id(0), back).unwrap(),
            _ => s.detach(id(0)).unwrap(),
        }
        assert_eq!(receive(&mut s, endpoint, &mut m), 0);
        assert!(
            s.tables[1]
                .replies
                .iter()
                .all(|r| r.generation == 0 && r.value.is_none())
        );
    }
}

#[test]
fn server_retirement_revokes_tokens_and_same_slot_new_task_cannot_replay() {
    let (mut s, back, endpoint, send, mut m) = setup();
    request(&mut s, send, back, &mut m);
    let token = receive(&mut s, endpoint, &mut m);
    s.detach(id(1)).unwrap();
    let next = TaskId {
        generation: 2,
        ..id(1)
    };
    s.attach(next, image(1)).unwrap();
    for c in [caller(1), Caller::new(next, image(1))] {
        assert_eq!(
            s.message(c, token, BASE, 8, Operation::Reply, &mut m),
            (Status::Denied, 0)
        );
    }
    for slot in [id(0), next, id(2), id(3)] {
        s.detach(slot).unwrap();
    }
    assert!(s.is_empty());
}

#[test]
fn new_syscalls_validate_version_reserved_buffers_and_separate_reply_argument() {
    use crate::user_entry::syscall::{Request, request};
    for (n, operation, size, arg) in [
        (6, Operation::Request { reply_to: 99 }, 64, 99),
        (7, Operation::Receive, 96, 0),
        (8, Operation::Reply, 64, 0),
        (9, Operation::Discard, 0, 0),
    ] {
        let addr = if n == 9 { 0 } else { BASE };
        assert_eq!(
            request(n, 1, 123, addr, size, arg, 0),
            Ok(Request::Message {
                handle: 123,
                address: addr,
                bytes: size as usize,
                operation
            })
        );
        assert_eq!(request(n, 2, 123, addr, size, arg, 0), Err(Status::Version));
        assert_eq!(
            request(n, 1, 123, addr, size, arg, 1),
            Err(Status::Arguments)
        );
        assert_eq!(
            request(n, 1, 123, addr, size + 1, arg, 0),
            Err(Status::Arguments)
        );
        if n != 9 {
            for bad in [
                0,
                u64::MAX - 3,
                crate::virtual_memory::USER_WINDOW_END_EXCLUSIVE - 3,
            ] {
                assert_eq!(
                    request(n, 1, 123, bad, size, arg, 0),
                    Err(Status::Arguments)
                );
            }
        }
        if n != 6 {
            assert_eq!(request(n, 1, 123, addr, size, 1, 0), Err(Status::Arguments));
        }
    }
}
