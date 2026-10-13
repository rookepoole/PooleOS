use super::*;
use std::{collections::VecDeque, vec::Vec};
#[derive(Default)]
struct CallsMock {
    steps: VecDeque<(u64, u64, Vec<u8>, (u64, u64))>,
}
impl Calls for CallsMock {
    fn invoke(&mut self, number: u64, handle: u64, wire: &mut [u8]) -> (u64, u64) {
        let (n, h, bytes, result) = self.steps.pop_front().expect("unexpected syscall");
        assert_eq!((number, handle), (n, h));
        if !bytes.is_empty() {
            if matches!(number, 7 | 11) {
                wire[..bytes.len()].copy_from_slice(&bytes);
            } else {
                assert_eq!(wire, bytes);
            }
        }
        result
    }
}
fn wrap(peer: u64, token: u64, payload: &[u8]) -> Vec<u8> {
    let mut wire = Vec::new();
    for word in [peer & 0xffffffff, peer >> 32, token, payload.len() as u64] {
        wire.extend_from_slice(&word.to_le_bytes());
    }
    wire.extend_from_slice(payload);
    wire
}
const ENDPOINT: u64 = 0x100010001;
const REQUEST: u64 = 0x100030001;
const REPLY: u64 = 0x100020001;
const PEER: u64 = 0x100000001;
#[test]
fn application_file_access_is_opt_in_and_uses_kernel_role_not_payload_identity() {
    fn check<const APPS: bool>(peer: u64, allowed: bool) {
        let request = Frame::empty(super::super::LIST, 1, 0);
        let encoded = request.encode();
        let response = super::super::answer(if allowed { &encoded } else { &[] }).encode();
        let calls = CallsMock {
            steps: [
                (7, ENDPOINT, wrap(peer, 0, &request.encode()), (0, 96)),
                (7, ENDPOINT, wrap(peer, REPLY, &request.encode()), (0, 96)),
                (8, REPLY, response.to_vec(), (0, 64)),
            ]
            .into(),
        };
        let mut server = Service::<_, APPS>::new(ENDPOINT, [PEER, 0x100000003], calls);
        for _ in 0..3 {
            server.poll().unwrap();
        }
        assert_eq!(server.reply, 0);
        assert!(server.calls.steps.is_empty());
    }
    for generation in [1u64, 2, u32::MAX as u64] {
        for slot in [4, 5] {
            check::<true>((generation << 32) | slot, true);
            check::<false>((generation << 32) | slot, false);
        }
    }
    for peer in [0x100000002, 0x100000006, 0x200000003, 0x100000104] {
        check::<true>(peer, false);
    }
    for peer in [PEER, 0x100000003] {
        check::<true>(peer, true);
    }
}
#[test]
fn plain_messages_without_reply_authority_do_not_terminate_the_service() {
    let request = Frame::empty(super::super::LIST, 1, 0);
    let calls = CallsMock {
        steps: [
            (7, ENDPOINT, wrap(PEER, 0, &request.encode()), (0, 96)),
            (7, ENDPOINT, wrap(PEER, REPLY, &request.encode()), (0, 96)),
            (
                8,
                REPLY,
                super::super::answer(&request.encode()).encode().to_vec(),
                (0, 64),
            ),
        ]
        .into(),
    };
    let mut server = Server::new(ENDPOINT, [PEER, 0x100000003], calls);
    for _ in 0..3 {
        server.poll().unwrap();
    }
    assert_eq!(server.reply, 0);
    assert!(server.calls.steps.is_empty());
}
#[test]
fn client_retries_backpressure_and_authenticates_completion() {
    let request = Frame::empty(super::super::LIST, 7, 0);
    let reply = super::super::answer(&request.encode());
    let calls = CallsMock {
        steps: [
            (10, ENDPOINT, request.encode().to_vec(), (6, 0)),
            (10, ENDPOINT, request.encode().to_vec(), (0, REQUEST)),
            (11, REQUEST, Vec::new(), (6, 0)),
            (11, REQUEST, wrap(PEER, 0, &reply.encode()), (0, 96)),
        ]
        .into(),
    };
    let mut client = Client::new(ENDPOINT, PEER, calls);
    assert!(client.finish().is_err());
    assert!(!client.start(&request).unwrap());
    assert!(client.start(&request).unwrap());
    assert_eq!(client.start(&request), Err(Error::Sequence));
    assert_eq!(client.finish(), Ok(None));
    assert_eq!(client.finish(), Ok(Some(reply)));
    assert!(client.calls.steps.is_empty());
}
#[test]
fn client_rejects_spoofed_stale_malformed_or_uncorrelated_replies() {
    let request = Frame::empty(super::super::LIST, 7, 0);
    for at in [0, 8, 16, 24, 32, 36, 39, 40, 48, 95] {
        let reply = super::super::answer(&request.encode());
        let mut wire = wrap(PEER, 0, &reply.encode());
        wire[at] ^= 0x80;
        let calls = CallsMock {
            steps: [
                (10, ENDPOINT, Vec::new(), (0, REQUEST)),
                (11, REQUEST, wire, (0, 96)),
            ]
            .into(),
        };
        let mut client = Client::new(ENDPOINT, PEER, calls);
        assert!(client.start(&request).unwrap());
        assert!(client.finish().is_err(), "mutation {at}");
    }
}
#[test]
fn denied_endpoint_and_revoked_request_do_not_leave_pending_state() {
    let request = Frame::empty(super::super::READ, 1, 0);
    let calls = CallsMock {
        steps: [
            (10, ENDPOINT, Vec::new(), (5, 0)),
            (10, ENDPOINT, Vec::new(), (0, REQUEST)),
            (11, REQUEST, Vec::new(), (9, 0)),
        ]
        .into(),
    };
    let mut client = Client::new(ENDPOINT, PEER, calls);
    assert_eq!(client.start(&request), Err(Error::Revoked));
    assert!(client.start(&request).unwrap());
    assert_eq!(client.finish(), Err(Error::Revoked));
    assert_eq!(client.pending, 0);
}
#[test]
fn server_handles_short_malformed_unauthorized_and_vanished_requesters() {
    let request = Frame::empty(super::super::LIST, 1, 0);
    for (peer, bytes) in [
        (PEER, Vec::from(&b"bad"[..])),
        (PEER + 1, request.encode().to_vec()),
    ] {
        let request_wire = wrap(peer, REPLY, &bytes);
        let calls = CallsMock {
            steps: [
                (
                    7,
                    ENDPOINT,
                    request_wire.clone(),
                    (0, request_wire.len() as u64),
                ),
                (
                    8,
                    REPLY,
                    super::super::answer(&[]).encode().to_vec(),
                    (5, 0),
                ),
                (
                    7,
                    ENDPOINT,
                    wrap(PEER, REPLY + 1, &request.encode()),
                    (0, 96),
                ),
                (
                    8,
                    REPLY + 1,
                    super::super::answer(&request.encode()).encode().to_vec(),
                    (0, 64),
                ),
            ]
            .into(),
        };
        let mut server = Server::new(ENDPOINT, [PEER, 0x100000003], calls);
        for _ in 0..4 {
            server.poll().unwrap();
        }
        assert_eq!(server.reply, 0);
        assert!(server.calls.steps.is_empty());
    }
}
#[test]
fn server_keeps_one_reply_across_backpressure() {
    let request = Frame::empty(super::super::LIST, 1, 0);
    let response = super::super::answer(&request.encode()).encode();
    let calls = CallsMock {
        steps: [
            (7, ENDPOINT, Vec::new(), (6, 0)),
            (7, ENDPOINT, wrap(PEER, REPLY, &request.encode()), (0, 96)),
            (8, REPLY, response.to_vec(), (6, 0)),
            (8, REPLY, response.to_vec(), (0, 64)),
        ]
        .into(),
    };
    let mut server = Server::new(ENDPOINT, [PEER, 0x100000003], calls);
    for _ in 0..4 {
        server.poll().unwrap();
    }
    assert_eq!(server.reply, 0);
}
