use super::*;
use crate::{console, session_control::rpc::Connection};

const ENDPOINT: u64 = 0x100010001;
const CLIENT: u64 = 0x100000003;
const SERVER: u64 = 0x100000002;

#[derive(Default)]
struct Wire {
    request: Option<[u8; 32]>,
    response: Option<[u8; 32]>,
    generation: u64,
    completion: u64,
    reply: u64,
    calls: usize,
    deny: Option<u64>,
    foreign_response: bool,
}
struct Kernel(Rc<RefCell<Wire>>);
impl console_ipc::rpc::Calls for Kernel {
    fn invoke(&mut self, number: u64, handle: u64, bytes: &mut [u8]) -> (u64, u64) {
        let mut w = self.0.borrow_mut();
        w.calls += 1;
        if w.deny == Some(number) {
            return (6, 0);
        }
        let (payload, peer, reply) = match number {
            10 => {
                assert_eq!(handle, ENDPOINT);
                assert_eq!(w.completion, 0, "second request while completion live");
                assert!(w.request.is_none() && w.response.is_none() && w.reply == 0);
                w.generation += 1;
                w.completion = (w.generation << 32) | 0x30001;
                w.request = Some(bytes.try_into().unwrap());
                return (0, w.completion);
            }
            7 => {
                assert_eq!(handle, ENDPOINT);
                assert_eq!(w.reply, 0, "receive with live reply authority");
                let Some(payload) = w.request.take() else {
                    return (6, 0);
                };
                w.reply = (w.generation << 32) | 0x20001;
                (payload, CLIENT, w.reply)
            }
            8 => {
                assert_ne!(w.reply, 0);
                assert_eq!(handle, w.reply, "wrong or reused one-use reply token");
                assert!(w.response.is_none());
                w.reply = 0;
                w.response = Some(bytes.try_into().unwrap());
                return (0, 32);
            }
            11 => {
                assert_ne!(w.completion, 0);
                assert_eq!(handle, w.completion, "wrong or consumed completion");
                let Some(payload) = w.response.take() else {
                    return (6, 0);
                };
                w.completion = 0;
                let peer = if w.foreign_response {
                    SERVER + 1
                } else {
                    SERVER
                };
                (payload, peer, 0)
            }
            _ => panic!("unexpected session syscall"),
        };
        for (part, value) in
            bytes[..32]
                .chunks_exact_mut(8)
                .zip([peer as u32 as u64, peer >> 32, reply, 32])
        {
            part.copy_from_slice(&value.to_le_bytes());
        }
        bytes[32..].copy_from_slice(&payload);
        (0, 64)
    }
}
#[derive(Default)]
struct Port {
    input: VecDeque<u8>,
    output: Vec<u8>,
}
impl console::Registers for Port {
    fn read(&mut self, offset: u8) -> Result<u8, console::Error> {
        match offset {
            5 => Ok(0x60 | u8::from(!self.input.is_empty())),
            0 => Ok(self.input.pop_front().unwrap()),
            _ => panic!("unexpected port read"),
        }
    }
    fn write(&mut self, offset: u8, value: u8) -> Result<(), console::Error> {
        assert_eq!(offset, 0);
        self.output.push(value);
        Ok(())
    }
}
fn step(
    client: &mut Session<'_>,
    connection: &mut Connection<Kernel>,
    wire: &Rc<RefCell<Wire>>,
    p: &Processes,
    f: &FileCalls,
) -> Result<bool, Error> {
    let before = wire.borrow().calls + p.0.borrow().calls.len() + f.0.borrow().calls.len();
    let result = client.poll(connection);
    let after = wire.borrow().calls + p.0.borrow().calls.len() + f.0.borrow().calls.len();
    assert!(after - before <= 1);
    result
}

#[test]
fn connected_sessions_use_authenticated_one_use_rpc_and_preserve_terminal_draft() {
    fixture(|client, p, f| {
        let wire = Rc::new(RefCell::new(Wire::default()));
        let mut outgoing = Connection::new(
            ENDPOINT,
            console_ipc::Peer::from_packed(SERVER).unwrap(),
            false,
            Kernel(wire.clone()),
        );
        let mut incoming = Connection::new(
            ENDPOINT,
            console_ipc::Peer::from_packed(CLIENT).unwrap(),
            true,
            Kernel(wire.clone()),
        );
        let mut server = console_ipc::control::Server::new();
        let mut port = Port {
            input: b"echo kept".iter().copied().collect(),
            ..Port::default()
        };
        let mut requested = false;
        for _ in 0..30000 {
            step(client, &mut outgoing, &wire, p, f).unwrap();
            server.poll(&mut port, &mut incoming).unwrap();
            if client.shell.len == 9
                && port.input.is_empty()
                && server.request(App::Text, Action::Start, 0).unwrap()
            {
                requested = true;
                break;
            }
        }
        assert!(requested);
        let sequence = client.shell.sequence;
        let output = port.output.clone();
        p.0.borrow_mut().results.extend([(6, 0), (0, CHILD)]);
        // Hold each transport syscall independently while both state machines poll.
        for number in [8, 11, 10, 7] {
            wire.borrow_mut().deny = Some(number);
            for _ in 0..5 {
                step(client, &mut outgoing, &wire, p, f).unwrap();
                server.poll(&mut port, &mut incoming).unwrap();
            }
        }
        wire.borrow_mut().deny = None;
        let mut result = None;
        let mut resumed = false;
        for _ in 0..300 {
            step(client, &mut outgoing, &wire, p, f).unwrap();
            server.poll(&mut port, &mut incoming).unwrap();
            if result.is_none() {
                result = server.take_result();
            }
            if result.is_some()
                && matches!(client.phase, Phase::Console)
                && client.shell.sequence == sequence + 2
            {
                resumed = true;
                break;
            }
        }
        assert!(resumed);
        let reply = result.unwrap();
        assert_eq!(reply.status(), Status::Admitted);
        assert_eq!(reply.request().sequence(), sequence);
        assert_eq!(p.0.borrow().calls.len(), 2);
        assert_eq!(&client.shell.line[..client.shell.len], b"echo kept");
        assert_eq!(port.output, output);
        port.input.push_back(b'\r');
        for _ in 0..3000 {
            step(client, &mut outgoing, &wire, p, f).unwrap();
            server.poll(&mut port, &mut incoming).unwrap();
            if port.output[output.len()..].ends_with(b"kept\r\nPooleOS> ") {
                break;
            }
        }
        assert!(port.output[output.len()..].ends_with(b"kept\r\nPooleOS> "));
        assert_eq!(p.0.borrow().calls.len(), 2);
    });
}

#[test]
fn foreign_kernel_peer_poisoning_precedes_control_effects() {
    fixture(|client, p, f| {
        let wire = Rc::new(RefCell::new(Wire {
            foreign_response: true,
            ..Wire::default()
        }));
        let mut outgoing = Connection::new(
            ENDPOINT,
            console_ipc::Peer::from_packed(SERVER).unwrap(),
            false,
            Kernel(wire.clone()),
        );
        let mut incoming = Connection::new(
            ENDPOINT,
            console_ipc::Peer::from_packed(CLIENT).unwrap(),
            true,
            Kernel(wire.clone()),
        );
        let mut server = console_ipc::control::Server::new();
        let mut port = Port::default();
        let mut failed = false;
        for _ in 0..3000 {
            match step(client, &mut outgoing, &wire, p, f) {
                Err(Error::Peer) => {
                    failed = true;
                    break;
                }
                result => {
                    result.unwrap();
                }
            }
            server.poll(&mut port, &mut incoming).unwrap();
        }
        assert!(failed);
        let before = wire.borrow().calls;
        assert_eq!(
            step(client, &mut outgoing, &wire, p, f),
            Err(Error::Transport)
        );
        assert_eq!(wire.borrow().calls, before);
        assert!(p.0.borrow().calls.is_empty());
    });
}
