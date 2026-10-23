use super::*;
use crate::{
    console_ipc::{BYTES, ENVELOPE_BYTES},
    session_control::{Action, App, Reply, Status},
};
use std::vec::Vec;

const ENDPOINT: u64 = 0x100010002;
const COMPLETION: u64 = 0x100030001;
const REPLY: u64 = 0x100020001;
fn transport(server: bool) -> Transport {
    Transport::new(ENDPOINT, Peer::from_packed(0x100000002).unwrap(), server)
}
fn console(kind: Kind, seq: u64) -> Exchange {
    Exchange::Console(
        Message::new(kind, seq, if kind == Kind::Input { b"x" } else { b"" }).unwrap(),
    )
}
fn request() -> Request {
    Request::new(1, App::Text, Action::Start, 0).unwrap()
}
fn answer() -> Exchange {
    Exchange::Control(Frame::Reply(
        Reply::new(request(), Status::Admitted, 1).unwrap(),
    ))
}
fn envelope(exchange: Exchange, token: u64) -> [u8; ENVELOPE_BYTES] {
    let mut wire = [0; ENVELOPE_BYTES];
    for (i, word) in [2u64, 1, token, BYTES as u64].iter().enumerate() {
        wire[i * 8..i * 8 + 8].copy_from_slice(&word.to_le_bytes());
    }
    wire[32..].copy_from_slice(&exchange.encode());
    wire
}
struct Kernel {
    result: (u64, u64),
    output: Option<[u8; ENVELOPE_BYTES]>,
    calls: Vec<(u64, u64, Vec<u8>)>,
}
impl Kernel {
    fn new() -> Self {
        Self {
            result: (6, 0),
            output: None,
            calls: Vec::new(),
        }
    }
    fn receive(&mut self, exchange: Exchange, token: u64) {
        self.result = (0, ENVELOPE_BYTES as u64);
        self.output = Some(envelope(exchange, token));
    }
    fn send(&mut self, result: (u64, u64)) {
        self.result = result;
        self.output = None;
    }
}
impl rpc::Calls for Kernel {
    fn invoke(&mut self, n: u64, h: u64, wire: &mut [u8]) -> (u64, u64) {
        self.calls.push((n, h, wire.to_vec()));
        if let Some(output) = self.output {
            wire.copy_from_slice(&output);
        }
        self.result
    }
}

#[test]
fn full_typed_roundtrip_uses_only_existing_rpc_and_one_use_tokens() {
    let (mut client, mut server, mut k) = (transport(false), transport(true), Kernel::new());
    let read = console(Kind::Read, 1);
    k.send((0, COMPLETION));
    assert_eq!(client.send(read, &mut k), Ok(true));
    k.receive(read, REPLY);
    assert_eq!(server.receive(&mut k), Ok(Some(read)));
    k.send((0, 32));
    assert_eq!(server.send(request().into(), &mut k), Ok(true));
    k.receive(request().into(), 0);
    assert_eq!(client.receive(&mut k), Ok(Some(request().into())));
    k.send((0, COMPLETION + (1 << 32)));
    assert_eq!(client.send(answer(), &mut k), Ok(true));
    k.receive(answer(), REPLY + (1 << 32));
    assert_eq!(server.receive(&mut k), Ok(Some(answer())));
    k.send((0, 32));
    assert_eq!(server.send(console(Kind::Written, 2), &mut k), Ok(true));
    k.receive(console(Kind::Written, 2), 0);
    assert_eq!(client.receive(&mut k), Ok(Some(console(Kind::Written, 2))));
    assert_eq!(
        k.calls.iter().map(|c| (c.0, c.1)).collect::<Vec<_>>(),
        [
            (10, ENDPOINT),
            (7, ENDPOINT),
            (8, REPLY),
            (11, COMPLETION),
            (10, ENDPOINT),
            (7, ENDPOINT),
            (8, REPLY + (1 << 32)),
            (11, COMPLETION + (1 << 32)),
        ]
    );
}

#[test]
fn control_reply_pressure_retains_identical_bytes_and_token() {
    let (mut t, mut k) = (transport(true), Kernel::new());
    k.receive(console(Kind::Read, 1), REPLY);
    t.receive(&mut k).unwrap();
    k.send((6, 0));
    for _ in 0..4 {
        assert_eq!(t.send(request().into(), &mut k), Ok(false));
    }
    assert!(
        k.calls[1..]
            .iter()
            .all(|c| *c == (8, REPLY, Exchange::from(request()).encode().to_vec()))
    );
    k.send((0, 32));
    assert_eq!(t.send(request().into(), &mut k), Ok(true));
    let count = k.calls.len();
    assert_eq!(t.send(request().into(), &mut k), Err(Error::Transport));
    assert_eq!(k.calls.len(), count);
    assert_eq!(t.receive(&mut k), Err(Error::Transport));
    assert_eq!(k.calls.len(), count);
}

#[test]
fn client_send_and_receive_pressure_do_not_start_extra_exchanges() {
    let (mut t, mut k) = (transport(false), Kernel::new());
    for _ in 0..4 {
        assert_eq!(t.send(answer(), &mut k), Ok(false));
    }
    assert!(
        k.calls
            .iter()
            .all(|c| *c == (10, ENDPOINT, answer().encode().to_vec()))
    );
    k.send((0, COMPLETION));
    t.send(answer(), &mut k).unwrap();
    k.send((6, 0));
    for _ in 0..4 {
        assert_eq!(t.receive(&mut k), Ok(None));
    }
    assert!(k.calls[5..].iter().all(|c| (c.0, c.1) == (11, COMPLETION)));
    k.receive(console(Kind::Written, 2), 0);
    assert_eq!(t.receive(&mut k), Ok(Some(console(Kind::Written, 2))));
}

#[test]
fn forged_peer_envelopes_and_reply_authority_never_reach_control_decoder() {
    for server in [false, true] {
        let incoming = if server { answer() } else { request().into() };
        let token = if server { REPLY } else { 0 };
        for offset in [0, 7, 8, 15, 24, 31] {
            let (mut t, mut k) = (transport(server), Kernel::new());
            if !server {
                k.send((0, COMPLETION));
                t.send(console(Kind::Read, 1), &mut k).unwrap();
            }
            k.receive(incoming, token);
            k.output.as_mut().unwrap()[offset] ^= 1;
            assert_eq!(t.receive(&mut k), Err(Error::Peer));
            let count = k.calls.len();
            assert_eq!(t.receive(&mut k), Err(Error::Transport));
            assert_eq!(k.calls.len(), count);
        }
    }
    for token in [0, COMPLETION, 0x20001, 0x100020000, u64::MAX] {
        let (mut t, mut k) = (transport(true), Kernel::new());
        k.receive(answer(), token);
        assert_eq!(t.receive(&mut k), Err(Error::Peer));
    }
    let (mut t, mut k) = (transport(false), Kernel::new());
    k.send((0, COMPLETION));
    t.send(console(Kind::Read, 1), &mut k).unwrap();
    k.receive(request().into(), REPLY);
    assert_eq!(t.receive(&mut k), Err(Error::Peer));
}

#[test]
fn direction_checks_reject_control_echo_and_inverted_console_without_sending() {
    for (server, wrong) in [
        (true, answer()),
        (false, request().into()),
        (true, console(Kind::Read, 1)),
        (false, console(Kind::Written, 1)),
    ] {
        let (mut t, mut k) = (transport(server), Kernel::new());
        assert_eq!(t.send(wrong, &mut k), Err(Error::Wire));
        assert!(k.calls.is_empty());
        assert_eq!(t.receive(&mut k), Err(Error::Transport));
        assert!(k.calls.is_empty());
    }
    for (server, wrong) in [
        (true, request().into()),
        (false, answer()),
        (true, console(Kind::Written, 1)),
        (false, console(Kind::Read, 1)),
    ] {
        let (mut t, mut k) = (transport(server), Kernel::new());
        if !server {
            k.send((0, COMPLETION));
            t.send(console(Kind::Read, 1), &mut k).unwrap();
        }
        k.receive(wrong, if server { REPLY } else { 0 });
        assert_eq!(t.receive(&mut k), Err(Error::Wire));
    }
}

#[test]
fn malformed_control_payload_poisons_even_with_authentic_peer() {
    for offset in [32, 36, 37, 38, 39, 56, 63] {
        let (mut t, mut k) = (transport(true), Kernel::new());
        k.receive(answer(), REPLY);
        k.output.as_mut().unwrap()[offset] = 255;
        assert!(t.receive(&mut k).is_err());
        let count = k.calls.len();
        assert_eq!(t.send(request().into(), &mut k), Err(Error::Transport));
        assert_eq!(k.calls.len(), count);
    }
}

#[test]
fn legacy_transport_does_not_silently_enable_control_mode() {
    let mut k = Kernel::new();
    let mut server = rpc::Transport::new(ENDPOINT, Peer::from_packed(0x100000002).unwrap(), true);
    k.receive(answer(), REPLY);
    assert_eq!(server.receive(&mut k), Err(Error::Wire));
    let mut client = rpc::Transport::new(ENDPOINT, Peer::from_packed(0x100000002).unwrap(), false);
    k.send((0, COMPLETION));
    client
        .send(Message::new(Kind::Read, 1, b"").unwrap(), &mut k)
        .unwrap();
    k.receive(request().into(), 0);
    assert_eq!(client.receive(&mut k), Err(Error::Wire));
}

#[test]
fn revoked_or_malformed_rpc_results_never_reuse_consumed_authority() {
    for result in [(9, 0), (9, 1), (0, 63), (0, 65), (6, 1), (5, 0)] {
        let (mut t, mut k) = (transport(false), Kernel::new());
        k.send((0, COMPLETION));
        t.send(console(Kind::Read, 1), &mut k).unwrap();
        k.send(result);
        assert_eq!(
            t.receive(&mut k),
            Err(if result == (9, 0) {
                Error::Revoked
            } else {
                Error::Transport
            })
        );
        let count = k.calls.len();
        assert_eq!(t.send(answer(), &mut k), Err(Error::Transport));
        assert_eq!(t.receive(&mut k), Err(Error::Transport));
        assert_eq!(k.calls.len(), count);
    }
}

#[test]
fn wire_sequences_are_preserved_not_inferred_from_process_generation() {
    assert_eq!(Exchange::from(request()).sequence(), 1);
    assert_eq!(answer().sequence(), 1);
    assert_eq!(console(Kind::Written, 2).sequence(), 2);
    let req = Request::new(123, App::Numbers, Action::Start, 9).unwrap();
    let e = Exchange::Control(Frame::Reply(Reply::new(req, Status::Admitted, 10).unwrap()));
    assert_eq!(e.sequence(), 123);
    assert_eq!(Exchange::decode(&e.encode()), Ok(e));
}
