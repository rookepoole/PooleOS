use super::*;
use std::vec::Vec;
#[derive(Default)]
struct Loopback {
    pending: Option<Frame>,
    sends: usize,
    blocked: bool,
    denied: bool,
}
impl Calls for Loopback {
    fn invoke(&mut self, number: u64, _: u64, wire: &mut [u8]) -> (u64, u64) {
        if self.denied {
            return (5, 0);
        }
        self.blocked = !self.blocked;
        if self.blocked {
            return (6, 0);
        }
        if number == 10 {
            assert!(self.pending.is_none());
            self.sends += 1;
            self.pending = Some(files::answer(wire));
            (0, 0x100030001)
        } else {
            assert_eq!(number, 11);
            let reply = self.pending.take().unwrap();
            wire.fill(0);
            wire[0..8].copy_from_slice(&1u64.to_le_bytes());
            wire[8..16].copy_from_slice(&1u64.to_le_bytes());
            wire[24..32].copy_from_slice(&64u64.to_le_bytes());
            wire[32..].copy_from_slice(&reply.encode());
            (0, 96)
        }
    }
}
fn commands() -> Files<Loopback> {
    Files::new(Client::new(0x100010003, 0x100000001, Loopback::default()))
}
#[test]
fn full_shell_streams_files_with_console_backpressure_and_prompts_only_at_completion() {
    use crate::{
        console_ipc::{Channel, Kind, Message},
        shell::Shell,
    };
    struct Console {
        input: std::collections::VecDeque<u8>,
        output: Vec<u8>,
        request: Option<Message>,
        block: bool,
    }
    impl Channel for Console {
        fn send(&mut self, message: Message) -> Result<bool, Error> {
            self.block = !self.block;
            if self.block {
                return Ok(false);
            }
            assert!(self.request.is_none());
            self.request = Some(message);
            Ok(true)
        }
        fn receive(&mut self) -> Result<Option<Message>, Error> {
            self.block = !self.block;
            if self.block {
                return Ok(None);
            }
            let request = self.request.take().unwrap();
            let reply = match request.kind() {
                Kind::Read => Message::new(
                    Kind::Input,
                    request.sequence(),
                    &[self.input.pop_front().unwrap()],
                )?,
                Kind::Write => {
                    self.output.extend_from_slice(request.payload());
                    Message::new(Kind::Written, request.sequence(), &[])?
                }
                Kind::Close => Message::new(Kind::Closed, request.sequence(), &[])?,
                _ => panic!(),
            };
            Ok(Some(reply))
        }
    }
    let mut f = commands();
    let mut shell = Shell::with_commands(&mut f);
    let mut console = Console {
        input: b"cat /readme.txt\rcat /empty.txt\rexit\r"
            .iter()
            .copied()
            .collect(),
        output: Vec::new(),
        request: None,
        block: false,
    };
    let mut done = false;
    for _ in 0..20000 {
        if shell.poll(&mut console).unwrap() {
            done = true;
            break;
        }
    }
    assert!(done);
    let mut expected = Vec::from(&b"PooleOS native shell\r\nPooleOS> cat /readme.txt\r\n"[..]);
    expected.extend_from_slice(files::entry(0).unwrap().1);
    expected.extend_from_slice(b"PooleOS> cat /empty.txt\r\nPooleOS> exit\r\nBye.\r\n");
    assert_eq!(console.output, expected);
}
fn run(f: &mut Files<Loopback>, line: &[u8]) -> Vec<u8> {
    assert!(f.begin(line).unwrap());
    let mut output = Vec::new();
    for _ in 0..200 {
        if f.poll().unwrap() {
            output.extend_from_slice(f.response());
            if f.response_complete() {
                return output;
            }
            assert!(!f.close_allowed());
        }
    }
    panic!("unbounded file operation");
}
#[test]
fn commands_stream_listing_multichunk_empty_missing_and_repeated_reads() {
    let mut f = commands();
    assert_eq!(
        run(&mut f, b"ls"),
        b"/readme.txt\r\n/version.txt\r\n/numbers.csv\r\n/empty.txt\r\n"
    );
    for _ in 0..2 {
        assert_eq!(run(&mut f, b"cat /readme.txt"), files::entry(0).unwrap().1);
    }
    assert_eq!(run(&mut f, b"cat /empty.txt"), b"");
    assert_eq!(run(&mut f, b"cat /absent"), b"File not found.\r\n");
    assert_eq!(run(&mut f, b"cat /../readme.txt"), b"Invalid path.\r\n");
    assert!(f.close_allowed());
    assert!(!f.begin(b"ls /extra").unwrap());
}
#[test]
fn denied_file_grant_is_a_command_error_not_a_shell_crash() {
    let mut f = Files::new(Client::new(
        0x200010003,
        0x100000001,
        Loopback {
            denied: true,
            ..Loopback::default()
        },
    ));
    assert_eq!(run(&mut f, b"ls"), b"File service unavailable.\r\n");
    assert_eq!(
        run(&mut f, b"cat /version.txt"),
        b"File service unavailable.\r\n"
    );
    assert!(f.close_allowed());
}
#[test]
fn hostile_sizes_changes_empty_progress_and_terminal_controls_fail_closed() {
    for mode in 0..6 {
        let mut f = commands();
        f.begin(b"cat /version.txt").unwrap();
        let mut reply = Frame::empty(files::READ, 1, 0);
        reply.total = 3;
        reply.len = 1;
        reply.data[0] = b'x';
        match mode {
            0 => reply.total = 1025,
            1 => {
                reply.total = 0;
            }
            2 => {
                reply.len = 0;
                reply.data[0] = 0;
            }
            3 => {
                reply.data[0] = 27;
            }
            4 => {
                f.total = Some(4);
            }
            _ => {
                reply.status = files::END;
                reply.total = 0;
                reply.len = 0;
            }
        }
        assert!(f.receive(reply).is_err(), "{mode}");
    }
}
