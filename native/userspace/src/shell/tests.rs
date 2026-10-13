use super::*;
use std::{collections::VecDeque, vec::Vec};

#[derive(Default)]
struct Console {
    input: VecDeque<u8>,
    output: Vec<u8>,
    request: Option<Message>,
    sends: Vec<Message>,
    blocked_send: bool,
    blocked_receive: bool,
    closed: bool,
}
impl Channel for Console {
    fn send(&mut self, message: Message) -> Result<bool, Error> {
        if self.blocked_send {
            return Ok(false);
        }
        assert!(self.request.is_none());
        assert_eq!(message.sequence(), self.sends.len() as u64 + 1);
        self.request = Some(message);
        self.sends.push(message);
        Ok(true)
    }
    fn receive(&mut self) -> Result<Option<Message>, Error> {
        if self.blocked_receive {
            return Ok(None);
        }
        let request = self.request.unwrap();
        let result = match request.kind() {
            Kind::Write => {
                self.output.extend_from_slice(request.payload());
                Message::new(Kind::Written, request.sequence(), &[])?
            }
            Kind::Read => {
                let Some(byte) = self.input.pop_front() else {
                    return Ok(None);
                };
                Message::new(Kind::Input, request.sequence(), &[byte])?
            }
            Kind::Close => {
                self.closed = true;
                Message::new(Kind::Closed, request.sequence(), &[])?
            }
            _ => panic!("response sent as request"),
        };
        self.request = None;
        Ok(Some(result))
    }
}
fn run(input: &[u8]) -> Console {
    let mut console = Console {
        input: input.iter().copied().collect(),
        ..Console::default()
    };
    let mut shell = Shell::new();
    for _ in 0..20000 {
        if shell.poll(&mut console).unwrap() {
            let count = console.sends.len();
            assert!(shell.poll(&mut console).unwrap());
            assert_eq!(console.sends.len(), count);
            assert!(console.input.is_empty());
            return console;
        }
    }
    panic!("shell did not terminate");
}
fn contains(output: &[u8], bytes: &[u8]) -> bool {
    output.windows(bytes.len()).any(|w| w == bytes)
}

#[test]
fn exact_commands_and_close_handshake() {
    let console = run(b"help\rversion\recho ABC-270\rexit\r");
    assert_eq!(console.output, b"PooleOS native shell\r\nPooleOS> help\r\nhelp  version  echo TEXT  exit\r\nPooleOS> version\r\nPooleOS native development / PooleShell 0.1\r\nPooleOS> echo ABC-270\r\nABC-270\r\nPooleOS> exit\r\nBye.\r\n");
    assert!(console.closed);
    assert_eq!(console.sends.last().unwrap().kind(), Kind::Close);
}
#[test]
fn crlf_is_one_command_and_lf_is_supported() {
    let console = run(b"echo a\r\necho b\n\x04");
    assert_eq!(console.output, b"PooleOS native shell\r\nPooleOS> echo a\r\na\r\nPooleOS> echo b\r\nb\r\nPooleOS> Bye.\r\n");
}
#[test]
fn backspace_and_delete_edit_the_command() {
    let console = run(b"\x08echx\x08o XY\x7fZ\r\x04");
    assert!(contains(
        &console.output,
        b"echx\x08 \x08o XY\x08 \x08Z\r\nXZ\r\n"
    ));
}
#[test]
fn interrupt_discards_line_and_returns_prompt() {
    let console = run(b"exit\x03echo kept\r\x04");
    assert!(contains(
        &console.output,
        b"exit^C\r\nPooleOS> echo kept\r\nkept\r\n"
    ));
}
#[test]
fn empty_line_and_echo_have_no_unknown_command() {
    let console = run(b"\recho\recho \r\x04");
    assert!(!contains(&console.output, b"Unknown"));
    assert!(!contains(&console.output, b"Invalid"));
}
#[test]
fn command_tokens_are_exact_and_do_not_execute_suffixes() {
    let console = run(b"exitjunk\rhelp x\r echo hi\r\x04");
    assert_eq!(
        console
            .output
            .windows(16)
            .filter(|w| *w == b"Unknown command.")
            .count(),
        3
    );
}
#[test]
fn full_length_line_is_accepted_and_chunked() {
    let mut input = Vec::from(&b"echo "[..]);
    input.extend_from_slice(&[b'x'; 59]);
    input.extend_from_slice(b"\r\x04");
    let console = run(&input);
    assert!(!contains(&console.output, b"Invalid"));
    assert!(contains(&console.output, &[b'x'; 59]));
    assert!(console.sends.iter().all(|m| m.payload().len() <= PAYLOAD));
}
#[test]
fn overflow_rejects_whole_line_even_after_backspace() {
    let mut input = Vec::from(&b"echo "[..]);
    input.extend_from_slice(&[b'x'; 60]);
    input.extend_from_slice(b"\x08\r\x04");
    let console = run(&input);
    assert!(contains(&console.output, b"Invalid line.\r\nPooleOS> Bye."));
}
#[test]
fn invalid_bytes_cannot_turn_exit_prefix_into_a_command() {
    for byte in [0, 1, 9, 27, 128, 255] {
        let console = run(&[b'e', b'x', b'i', b't', byte, b'\r', 4]);
        assert!(contains(&console.output, b"Invalid line.\r\nPooleOS> Bye."));
    }
}
#[test]
fn interrupt_resets_invalid_line_and_eof_does_not_execute_partial_input() {
    let console = run(b"exit\xff\x03echo x\x04\r\x04");
    assert!(contains(&console.output, b"echo x\r\nx\r\nPooleOS> Bye."));
    assert!(!contains(&console.output, b"Invalid line."));
}
#[test]
fn send_backpressure_preserves_cursor_sequence_and_bytes() {
    let mut shell = Shell::new();
    let mut console = Console {
        blocked_send: true,
        ..Console::default()
    };
    for _ in 0..20 {
        assert!(!shell.poll(&mut console).unwrap());
    }
    assert_eq!((shell.cursor, shell.sequence), (0, 1));
    assert!(shell.pending.is_none());
    console.blocked_send = false;
    shell.poll(&mut console).unwrap();
    assert_eq!(console.sends[0].payload(), &BANNER[..16]);
}
#[test]
fn receive_backpressure_does_not_duplicate_a_request() {
    let mut shell = Shell::new();
    let mut console = Console {
        blocked_receive: true,
        ..Console::default()
    };
    for _ in 0..20 {
        assert!(!shell.poll(&mut console).unwrap());
    }
    assert_eq!(console.sends.len(), 1);
    assert_eq!((shell.cursor, shell.sequence), (0, 1));
    console.blocked_receive = false;
    shell.poll(&mut console).unwrap();
    assert_eq!((shell.cursor, shell.sequence), (16, 2));
}
struct Reply(Result<Option<Message>, Error>);
impl Channel for Reply {
    fn send(&mut self, _: Message) -> Result<bool, Error> {
        Ok(true)
    }
    fn receive(&mut self) -> Result<Option<Message>, Error> {
        self.0
    }
}
#[test]
fn wrong_sequence_kind_and_revoked_peer_fail_without_advancing() {
    for reply in [
        Ok(Some(Message::new(Kind::Written, 2, &[]).unwrap())),
        Ok(Some(Message::new(Kind::Closed, 1, &[]).unwrap())),
        Err(Error::Revoked),
        Err(Error::Transport),
    ] {
        let mut shell = Shell::new();
        let mut channel = Reply(reply);
        shell.poll(&mut channel).unwrap();
        assert!(shell.poll(&mut channel).is_err());
        assert_eq!((shell.cursor, shell.sequence), (0, 1));
    }
}
#[test]
fn sequence_exhaustion_fails_instead_of_wrapping() {
    let mut shell = Shell::new();
    shell.sequence = u64::MAX - 1;
    let mut channel = Reply(Ok(Some(
        Message::new(Kind::Written, u64::MAX - 1, &[]).unwrap(),
    )));
    shell.poll(&mut channel).unwrap();
    shell.poll(&mut channel).unwrap();
    assert_eq!(shell.poll(&mut channel), Err(Error::Sequence));
    assert_eq!(shell.sequence, u64::MAX);
}

struct Script(std::rc::Rc<std::cell::RefCell<VecDeque<((u64, u64, u64), (u64, u64))>>>);
impl crate::supervisor::Calls for Script {
    fn invoke(&mut self, number: u64, handle: u64, argument: u64) -> (u64, u64) {
        let (expected, result) = self
            .0
            .borrow_mut()
            .pop_front()
            .expect("unexpected process call");
        assert_eq!((number, handle, argument), expected);
        result
    }
}
fn control(input: &[u8], script: &[((u64, u64, u64), (u64, u64))], backpressure: bool) -> Console {
    let queue = std::rc::Rc::new(std::cell::RefCell::new(script.iter().copied().collect()));
    let policy =
        processes::Processes::new([0x100060001, 0x100060002], Script(queue.clone())).unwrap();
    let mut shell = Shell::with_commands(policy);
    let mut console = Console {
        input: input.iter().copied().collect(),
        ..Console::default()
    };
    for i in 0..40000 {
        console.blocked_send = backpressure && i % 3 != 0;
        console.blocked_receive = backpressure && i % 4 != 0;
        if shell.poll(&mut console).unwrap() {
            assert!(queue.borrow().is_empty());
            assert!(console.input.is_empty());
            assert!(console.closed);
            return console;
        }
    }
    panic!("control shell did not terminate");
}
#[test]
fn process_commands_survive_console_backpressure_without_duplicate_actions() {
    let script = [
        ((19, 0x100060001, 1), (6, 0)),
        ((19, 0x100060001, 1), (0, 0x100050001)),
        ((18, 0x100050001, 0), (6, 0)),
        ((20, 0x100050001, 0), (0, 4 << 32)),
        ((19, 0x100060002, 1), (0, 0x100050002)),
        ((20, 0x100050002, 0), (0, (2 << 32) | 6)),
        ((20, 0x100050001, 0), (0, 4 << 32)),
        ((19, 0x100060001, 2), (0, 0x200050001)),
        ((18, 0x200050001, 0), (6, 0)),
        ((20, 0x200050001, 0), (0, 4 << 32)),
    ];
    let input = b"start worker\rexit\rstop worker\rstatus worker\rstart fault\rstatus fault\rstart worker\rstop worker\rstatus worker\rexit\r";
    let unblocked = control(input, &script, false);
    let blocked = control(input, &script, true);
    assert_eq!(unblocked.output, blocked.output);
    for text in [
        &b"Stop tasks and check status before exit."[..],
        b"worker: admitted",
        b"worker: stop requested",
        b"worker: cancelled",
        b"fault: fault 0x00000006",
        b"Bye.",
    ] {
        assert!(contains(&blocked.output, text));
    }
}
#[test]
fn unknown_and_corrupt_process_commands_never_call_the_kernel() {
    let console = control(
        b"start kernel\rstart worker extra\rstart worker\xff\r\x04",
        &[],
        true,
    );
    assert!(contains(&console.output, b"Unknown command."));
    assert!(contains(&console.output, b"Invalid line."));
}
#[test]
fn denied_launch_does_not_invent_a_task_or_prevent_close() {
    let console = control(
        b"start worker\rstatus worker\rexit\r",
        &[((19, 0x100060001, 1), (5, 0))],
        true,
    );
    assert!(contains(&console.output, b"worker: denied"));
    assert!(contains(&console.output, b"worker: not started"));
}
