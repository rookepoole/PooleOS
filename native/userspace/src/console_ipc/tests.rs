use super::*;
use std::{collections::VecDeque, vec, vec::Vec};

#[derive(Default)]
struct Device {
    input: VecDeque<u8>,
    output: Vec<u8>,
    ready: bool,
    drained: bool,
    calls: usize,
    failed: bool,
}
impl Registers for Device {
    fn read(&mut self, offset: u8) -> Result<u8, console::Error> {
        self.calls += 1;
        if self.failed {
            return Err(console::Error::Hardware);
        }
        match offset {
            5 => Ok(u8::from(!self.input.is_empty())
                | if self.ready { 0x20 } else { 0 }
                | if self.drained { 0x40 } else { 0 }),
            0 => self.input.pop_front().ok_or(console::Error::Hardware),
            _ => panic!("unexpected register"),
        }
    }
    fn write(&mut self, offset: u8, value: u8) -> Result<(), console::Error> {
        self.calls += 1;
        if self.failed {
            return Err(console::Error::Hardware);
        }
        assert_eq!(offset, 0);
        assert!(self.ready);
        self.output.push(value);
        Ok(())
    }
}
struct Io {
    incoming: VecDeque<Message>,
    outgoing: VecDeque<Message>,
    ready: bool,
    fail: bool,
    receives: usize,
    attempts: Vec<Message>,
}
impl Io {
    fn new() -> Self {
        Self {
            incoming: VecDeque::new(),
            outgoing: VecDeque::new(),
            ready: true,
            fail: false,
            receives: 0,
            attempts: Vec::new(),
        }
    }
}
impl Channel for Io {
    fn receive(&mut self) -> Result<Option<Message>, Error> {
        self.receives += 1;
        if self.fail {
            return Err(Error::Transport);
        }
        Ok(self.incoming.pop_front())
    }
    fn send(&mut self, message: Message) -> Result<bool, Error> {
        self.attempts.push(message);
        if self.fail {
            return Err(Error::Transport);
        }
        if self.ready {
            self.outgoing.push_back(message);
        }
        Ok(self.ready)
    }
}
fn msg(kind: Kind, sequence: u64, data: &[u8]) -> Message {
    Message::new(kind, sequence, data).unwrap()
}
fn block(args: &[&[u8]]) -> Vec<u8> {
    let mut b = vec![0; 96];
    b[..8].copy_from_slice(b"PSTART1\0");
    b[16..24].copy_from_slice(&(args.len() as u64).to_le_bytes());
    for (i, arg) in args.iter().enumerate() {
        let offset = b.len() as u64;
        b[32 + i * 8..40 + i * 8].copy_from_slice(&offset.to_le_bytes());
        b.extend_from_slice(arg);
        b.push(0);
    }
    b.resize((b.len() + 7) & !7, 0);
    let n = b.len() as u64;
    b[8..16].copy_from_slice(&n.to_le_bytes());
    b
}

#[test]
fn message_round_trip_covers_every_kind_payload_and_sequence_boundary() {
    for sequence in [1, 2, u64::MAX - 1] {
        for (kind, data) in [
            (Kind::Read, &b""[..]),
            (Kind::Close, b""),
            (Kind::Written, b""),
            (Kind::Closed, b""),
            (Kind::Input, b"x"),
        ] {
            let m = msg(kind, sequence, data);
            assert_eq!(Message::decode(&m.encode()), Ok(m));
        }
        for len in 1..=PAYLOAD {
            let m = msg(Kind::Write, sequence, &[255; PAYLOAD][..len]);
            assert_eq!(Message::decode(&m.encode()), Ok(m));
        }
    }
    for seq in [0, u64::MAX] {
        assert!(Message::new(Kind::Read, seq, &[]).is_err());
    }
    assert!(Message::new(Kind::Write, 1, &[]).is_err());
    assert!(Message::new(Kind::Write, 1, &[0; 17]).is_err());
    assert!(Message::new(Kind::Input, 1, &[0; 2]).is_err());
    assert!(Message::new(Kind::Close, 1, &[0]).is_err());
}

#[test]
fn malformed_wire_cannot_smuggle_length_reserved_tail_or_unknown_kind() {
    let good = msg(Kind::Read, 1, &[]).encode();
    for n in 0..BYTES {
        assert!(Message::decode(&good[..n]).is_err());
    }
    let mut extra = good.to_vec();
    extra.push(0);
    assert!(Message::decode(&extra).is_err());
    for at in [0, 1, 2, 3, 5, 6, 7, 16, 31] {
        let mut bad = good;
        bad[at] ^= 1;
        assert!(Message::decode(&bad).is_err(), "{at}");
    }
    for kind in [0, 7, 255] {
        let mut bad = good;
        bad[4] = kind;
        assert!(Message::decode(&bad).is_err());
    }
    for seq in [0u64, u64::MAX] {
        let mut bad = good;
        bad[8..16].copy_from_slice(&seq.to_le_bytes());
        assert!(Message::decode(&bad).is_err());
    }
    for len in [0, 2, 16, 17, 255] {
        let mut bad = msg(Kind::Input, 1, &[1]).encode();
        bad[5] = len;
        assert!(Message::decode(&bad).is_err());
    }
}

#[test]
fn kernel_envelope_identity_token_and_size_precede_payload_acceptance() {
    let peer = Peer::from_packed(0x100000003).unwrap();
    let m = msg(Kind::Read, 1, &[]);
    let mut wire = [0; ENVELOPE_BYTES];
    wire[..8].copy_from_slice(&3u64.to_le_bytes());
    wire[8..16].copy_from_slice(&1u64.to_le_bytes());
    wire[24..32].copy_from_slice(&(BYTES as u64).to_le_bytes());
    wire[32..].copy_from_slice(&m.encode());
    assert_eq!(peer.decode(&wire), Ok(m));
    for n in 0..wire.len() {
        assert!(peer.decode(&wire[..n]).is_err());
    }
    for at in [0, 7, 8, 15, 16, 23, 24, 31, 32, 39, 63] {
        let mut bad = wire;
        bad[at] ^= 1;
        assert!(peer.decode(&bad).is_err(), "{at}");
    }
    for bad in [0, 3, 0x100010000, u64::MAX] {
        assert!(Peer::from_packed(bad).is_err());
    }
    assert!(Peer::from_packed(0x100000000).is_ok());
}

#[test]
fn startup_service_client_roles_and_peer_metadata_are_strict_and_owned() {
    let s = block(&[
        b"console-service",
        b"0000000100040001",
        b"0000000100010001",
        b"0000000100010002",
        b"0000000100000003",
    ]);
    let c = block(&[
        b"console-client",
        b"0000000100010001",
        b"0000000100010002",
        b"0000000100000002",
    ]);
    for (bytes, server) in [(&s, true), (&c, false)] {
        let result = crate::startup::console_ipc(bytes, 1, server).unwrap();
        assert_eq!(result.port.is_some(), server);
        assert!(crate::startup::console_ipc(bytes, 1, !server).is_err());
        for n in 0..bytes.len() {
            assert!(crate::startup::console_ipc(&bytes[..n], 1, server).is_err());
        }
        for at in [0, 8, 16, 24, 32, 95, 96, bytes.len() - 1] {
            let mut bad = bytes.clone();
            bad[at] ^= 1;
            assert!(
                crate::startup::console_ipc(&bad, 1, server).is_err(),
                "{at}"
            );
        }
    }
    for peer in [
        b"0000000000000003",
        b"0000000100010000",
        b"000000010000000a",
    ] {
        let bad = block(&[
            b"console-client",
            b"0000000100010001",
            b"0000000100010002",
            peer,
        ]);
        assert!(crate::startup::console_ipc(&bad, 1, false).is_err());
    }
    let bad = block(&[
        b"console-client",
        b"0000000100010001",
        b"0000000100010001",
        b"0000000100000002",
    ]);
    assert!(crate::startup::console_ipc(&bad, 1, false).is_err());
}

#[test]
fn receive_reply_backpressure_never_consumes_another_request_or_input_byte() {
    let mut port = Device::default();
    port.input.extend([b'a', b'b']);
    let mut io = Io::new();
    io.ready = false;
    io.incoming
        .extend([msg(Kind::Read, 1, &[]), msg(Kind::Read, 2, &[])]);
    let mut server = Server::new();
    assert!(!server.poll(&mut port, &mut io).unwrap());
    assert!(!server.poll(&mut port, &mut io).unwrap());
    let calls = port.calls;
    for _ in 0..20 {
        assert!(!server.poll(&mut port, &mut io).unwrap());
    }
    assert_eq!(port.calls, calls);
    assert_eq!(io.receives, 1);
    assert_eq!(port.input.len(), 1);
    assert_eq!(io.incoming.len(), 1);
    assert_eq!(server.sequence, 1);
    io.ready = true;
    server.poll(&mut port, &mut io).unwrap();
    assert_eq!(io.outgoing.pop_front(), Some(msg(Kind::Input, 1, b"a")));
    assert_eq!(server.sequence, 2);
}

#[test]
fn writes_advance_once_per_success_and_reply_pressure_never_duplicates_output() {
    let data = *b"0123456789ABCDEF";
    let mut port = Device::default();
    let mut io = Io::new();
    let mut s = Server::new();
    io.incoming.push_back(msg(Kind::Write, 1, &data));
    s.poll(&mut port, &mut io).unwrap();
    for _ in 0..10 {
        s.poll(&mut port, &mut io).unwrap();
    }
    assert!(port.output.is_empty());
    for &byte in &data {
        port.ready = true;
        s.poll(&mut port, &mut io).unwrap();
        assert_eq!(port.output.last(), Some(&byte));
        port.ready = false;
        if port.output.len() != PAYLOAD {
            s.poll(&mut port, &mut io).unwrap();
        }
    }
    io.ready = false;
    let calls = port.calls;
    for _ in 0..10 {
        s.poll(&mut port, &mut io).unwrap();
    }
    assert_eq!(port.output, data);
    assert_eq!(port.calls, calls);
    assert_eq!(s.sequence, 1);
    io.ready = true;
    s.poll(&mut port, &mut io).unwrap();
    assert_eq!(io.outgoing.pop_front(), Some(msg(Kind::Written, 1, &[])));
    assert_eq!(s.sequence, 2);
}

#[test]
fn close_waits_for_hardware_drain_and_sent_ack_then_stays_closed() {
    let mut p = Device::default();
    let mut io = Io::new();
    let mut s = Server::new();
    io.incoming.push_back(msg(Kind::Close, 1, &[]));
    s.poll(&mut p, &mut io).unwrap();
    for _ in 0..10 {
        assert!(!s.poll(&mut p, &mut io).unwrap());
    }
    assert!(io.outgoing.is_empty());
    p.drained = true;
    s.poll(&mut p, &mut io).unwrap();
    io.ready = false;
    for _ in 0..10 {
        assert!(!s.poll(&mut p, &mut io).unwrap());
    }
    io.ready = true;
    assert!(s.poll(&mut p, &mut io).unwrap());
    assert_eq!(io.outgoing.pop_front(), Some(msg(Kind::Closed, 1, &[])));
    let counts = (p.calls, io.receives, io.attempts.len());
    for _ in 0..10 {
        assert!(s.poll(&mut p, &mut io).unwrap());
    }
    assert_eq!((p.calls, io.receives, io.attempts.len()), counts);
}

#[test]
fn unsolicited_replayed_and_response_kind_requests_have_no_port_effect() {
    for m in [
        msg(Kind::Write, 2, b"x"),
        msg(Kind::Written, 1, &[]),
        msg(Kind::Input, 1, b"x"),
        msg(Kind::Closed, 1, &[]),
    ] {
        let mut p = Device::default();
        let mut io = Io::new();
        let mut s = Server::new();
        io.incoming.push_back(m);
        assert!(s.poll(&mut p, &mut io).is_err());
        assert_eq!(p.calls, 0);
        assert_eq!(s.sequence, 1);
        assert!(io.outgoing.is_empty());
    }
    let mut p = Device::default();
    let mut io = Io::new();
    let mut s = Server::new();
    s.sequence = 2;
    io.incoming.push_back(msg(Kind::Read, 1, &[]));
    assert_eq!(s.poll(&mut p, &mut io), Err(Error::Sequence));
    assert_eq!(p.calls, 0);
}

#[test]
fn fatal_transport_and_device_failures_do_not_create_acknowledgements() {
    let mut p = Device::default();
    let mut io = Io::new();
    let mut s = Server::new();
    io.fail = true;
    assert_eq!(s.poll(&mut p, &mut io), Err(Error::Transport));
    assert_eq!(p.calls, 0);
    io.fail = false;
    io.incoming.push_back(msg(Kind::Read, 1, &[]));
    s.poll(&mut p, &mut io).unwrap();
    p.failed = true;
    assert_eq!(
        s.poll(&mut p, &mut io),
        Err(Error::Device(console::Error::Hardware))
    );
    assert!(io.outgoing.is_empty());
    assert_eq!(s.sequence, 1);
    let mut c = Client::new();
    io.fail = true;
    assert_eq!(c.poll(&mut io), Err(Error::Transport));
    assert_eq!(c.sequence, 1);
}

#[test]
fn client_rejects_wrong_response_kind_or_sequence_before_output() {
    for m in [
        msg(Kind::Written, 1, &[]),
        msg(Kind::Input, 2, b"a"),
        msg(Kind::Read, 1, &[]),
    ] {
        let mut c = Client::new();
        let mut io = Io::new();
        c.poll(&mut io).unwrap();
        io.incoming.push_back(m);
        assert_eq!(c.poll(&mut io), Err(Error::Sequence));
        assert_eq!(c.sequence, 1);
        assert_eq!(io.outgoing.len(), 1);
    }
}

#[test]
fn client_backpressure_keeps_identical_request_and_sequence_never_wraps() {
    let mut c = Client::new();
    let mut io = Io::new();
    io.ready = false;
    for _ in 0..12 {
        assert!(!c.poll(&mut io).unwrap());
    }
    assert_eq!(io.attempts, vec![msg(Kind::Read, 1, &[]); 12]);
    assert_eq!(c.sequence, 1);
    io.ready = true;
    c.poll(&mut io).unwrap();
    io.incoming.push_back(msg(Kind::Input, 1, b"a"));
    c.poll(&mut io).unwrap();
    c.poll(&mut io).unwrap();
    assert_eq!(io.outgoing.back(), Some(&msg(Kind::Write, 2, b"a")));
    c.sequence = u64::MAX - 1;
    c.phase = ClientPhase::Receive(Kind::Written);
    io.incoming.push_back(msg(Kind::Written, u64::MAX - 1, &[]));
    assert_eq!(c.poll(&mut io), Err(Error::Sequence));
    assert_eq!(c.sequence, u64::MAX - 1);
}

#[test]
fn independent_state_machines_echo_all_non_eot_bytes_with_pressure_then_close() {
    let data: Vec<u8> = (0..=255).filter(|&b| b != 4).collect();
    let mut p = Device::default();
    p.input.extend(data.iter().copied());
    p.input.push_back(4);
    let mut service = Server::new();
    let mut client = Client::new();
    let mut s = Io::new();
    let mut c = Io::new();
    let mut closed = (false, false);
    for step in 0..20000 {
        p.ready = step % 5 != 0;
        p.drained = step % 7 != 0;
        s.ready = step % 3 != 0;
        c.ready = step % 4 != 0;
        closed.0 = service.poll(&mut p, &mut s).unwrap();
        closed.1 = client.poll(&mut c).unwrap();
        while let Some(m) = s.outgoing.pop_front() {
            c.incoming.push_back(Message::decode(&m.encode()).unwrap());
        }
        while let Some(m) = c.outgoing.pop_front() {
            s.incoming.push_back(Message::decode(&m.encode()).unwrap());
        }
        assert!(s.incoming.len() <= 1 && c.incoming.len() <= 1);
        if closed == (true, true) {
            break;
        }
    }
    assert_eq!(closed, (true, true));
    assert_eq!(p.output, data);
    assert!(p.input.is_empty());
    assert!(s.incoming.is_empty() && c.incoming.is_empty());
    assert_eq!(client.sequence, 512);
    assert_eq!(service.sequence, 513);
}
