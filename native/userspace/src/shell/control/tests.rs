use super::*;
use crate::{
    files,
    session_control::{Action, App, Status},
    shell::{Commands, applications::Jobs, files::Files, processes::ApplicationProcesses},
};
use std::{cell::RefCell, collections::VecDeque, rc::Rc, vec::Vec};

mod integration;

const CHILD: u64 = 0x100050001;
#[derive(Default)]
struct ProcessState {
    results: VecDeque<(u64, u64)>,
    calls: Vec<(u64, u64, u64)>,
}
#[derive(Clone, Default)]
struct Processes(Rc<RefCell<ProcessState>>);
impl crate::supervisor::Calls for Processes {
    fn invoke(&mut self, n: u64, h: u64, a: u64) -> (u64, u64) {
        let mut state = self.0.borrow_mut();
        state.calls.push((n, h, a));
        state
            .results
            .pop_front()
            .expect("unexpected process syscall")
    }
}
#[derive(Default)]
struct FileState {
    calls: Vec<u64>,
    request: Option<[u8; files::BYTES]>,
    blocked: bool,
}
#[derive(Clone, Default)]
struct FileCalls(Rc<RefCell<FileState>>);
impl console_ipc::rpc::Calls for FileCalls {
    fn invoke(&mut self, n: u64, _: u64, wire: &mut [u8]) -> (u64, u64) {
        let mut state = self.0.borrow_mut();
        state.calls.push(n);
        match n {
            10 => {
                assert!(state.request.is_none());
                state.request = Some(wire.try_into().unwrap());
                (0, 0x100030001)
            }
            11 if state.blocked => (6, 0),
            11 => {
                let response = files::answer(&state.request.take().unwrap()).encode();
                for (part, value) in
                    wire[..32]
                        .chunks_exact_mut(8)
                        .zip([1u64, 1, 0, files::BYTES as u64])
                {
                    part.copy_from_slice(&value.to_le_bytes());
                }
                wire[32..].copy_from_slice(&response);
                (0, wire.len() as u64)
            }
            7 => (6, 0),
            _ => panic!("unexpected file/job syscall"),
        }
    }
}
type Session<'a> = Client<'a, FileCalls, Processes>;
fn fixture(test: impl FnOnce(&mut Session<'_>, &Processes, &FileCalls)) {
    let p = Processes::default();
    let f = FileCalls::default();
    f.0.borrow_mut().blocked = true;
    let mut processes = ApplicationProcesses::new([0x100060001, 0x100060002], p.clone()).unwrap();
    let mut files = Files::new(files::rpc::Client::new(0x100010001, 0x100000001, f.clone()));
    let mut jobs = Jobs::new(0x100010002, f.clone());
    let commands = ApplicationCommands::new(&mut files, &mut processes, &mut jobs);
    test(&mut Client::new(commands), &p, &f);
}

#[derive(Default)]
struct Host {
    input: VecDeque<u8>,
    output: Vec<u8>,
    pending: Option<Message>,
    control: Option<Reply>,
    next: Option<Result<Exchange, Error>>,
    sends: Vec<Exchange>,
    block_send: bool,
    block_receive: bool,
    fail_send: bool,
    calls: usize,
}
impl Channel for Host {
    fn send(&mut self, exchange: Exchange) -> Result<bool, Error> {
        self.calls += 1;
        self.sends.push(exchange);
        if self.fail_send {
            return Err(Error::Revoked);
        }
        if self.block_send {
            return Ok(false);
        }
        assert!(self.pending.is_none() && self.control.is_none());
        match exchange {
            Exchange::Console(message) => self.pending = Some(message),
            Exchange::Control(Frame::Reply(reply)) => self.control = Some(reply),
            _ => panic!("wrong direction"),
        }
        Ok(true)
    }
    fn receive(&mut self) -> Result<Option<Exchange>, Error> {
        self.calls += 1;
        if self.block_receive {
            return Ok(None);
        }
        if let Some(result) = self.next.take() {
            self.pending = None;
            self.control = None;
            return result.map(Some);
        }
        if let Some(reply) = self.control.take() {
            return Ok(Some(Exchange::Console(Message::new(
                Kind::Written,
                reply.request().sequence() + 1,
                &[],
            )?)));
        }
        let message = self.pending.unwrap();
        let reply = match message.kind() {
            Kind::Write => {
                self.output.extend_from_slice(message.payload());
                Message::new(Kind::Written, message.sequence(), &[])?
            }
            Kind::Read => {
                let Some(byte) = self.input.pop_front() else {
                    return Ok(None);
                };
                Message::new(Kind::Input, message.sequence(), &[byte])?
            }
            Kind::Close => Message::new(Kind::Closed, message.sequence(), &[])?,
            _ => panic!("invalid shell request"),
        };
        self.pending = None;
        Ok(Some(Exchange::Console(reply)))
    }
}
fn tick(s: &mut Session<'_>, h: &mut Host, p: &Processes, f: &FileCalls) -> Result<bool, Error> {
    let before = h.calls + p.0.borrow().calls.len() + f.0.borrow().calls.len();
    let result = s.poll(h);
    let after = h.calls + p.0.borrow().calls.len() + f.0.borrow().calls.len();
    assert!(
        after - before <= 1,
        "more than one IPC/process call in a poll"
    );
    result
}
fn until_read(s: &mut Session<'_>, h: &mut Host, p: &Processes, f: &FileCalls) {
    for _ in 0..30000 {
        tick(s, h, p, f).unwrap();
        if matches!(s.phase, Phase::Console)
            && s.shell.pending == Some((Kind::Input, 0))
            && h.input.is_empty()
        {
            return;
        }
    }
    panic!("shell did not reach Read");
}
fn begin(
    s: &mut Session<'_>,
    h: &mut Host,
    p: &Processes,
    f: &FileCalls,
    action: Action,
    generation: u32,
) -> Request {
    let request = Request::new(s.shell.sequence, App::Text, action, generation).unwrap();
    h.next = Some(Ok(Exchange::Control(Frame::Request(request))));
    tick(s, h, p, f).unwrap();
    assert!(matches!(s.phase, Phase::Process));
    request
}
fn finish(s: &mut Session<'_>, h: &mut Host, p: &Processes, f: &FileCalls) {
    for _ in 0..32 {
        tick(s, h, p, f).unwrap();
        if matches!(s.phase, Phase::Console) {
            return;
        }
    }
    panic!("control did not complete");
}

#[test]
fn admitted_control_preserves_partial_command_and_does_not_print_or_execute_it() {
    fixture(|s, p, f| {
        let mut h = Host {
            input: b"echo kept".iter().copied().collect(),
            ..Host::default()
        };
        until_read(s, &mut h, p, f);
        let output = h.output.clone();
        p.0.borrow_mut().results.push_back((0, CHILD));
        let request = begin(s, &mut h, p, f, Action::Start, 0);
        finish(s, &mut h, p, f);
        assert_eq!(&s.shell.line[..s.shell.len], b"echo kept");
        assert_eq!(h.output, output);
        assert_eq!(s.shell.sequence, request.sequence() + 2);
        assert!(s.shell.pending.is_none());
        assert_eq!(p.0.borrow().calls, [(19, 0x100060001, 1)]);
        h.input.push_back(b'\r');
        until_read(s, &mut h, p, f);
        assert!(h.output.ends_with(b"echo kept\r\nkept\r\nPooleOS> "));
        assert!(f.0.borrow().calls.is_empty());
    });
}

#[test]
fn rejected_overlong_and_crlf_drafts_survive_inspection_unchanged() {
    for input in [
        b"echo pre".to_vec(),
        std::vec![b'x'; 65],
        b"bad\x01".to_vec(),
        b"\r".to_vec(),
    ] {
        fixture(|s, p, f| {
            let mut h = Host {
                input: input.iter().copied().collect(),
                ..Host::default()
            };
            until_read(s, &mut h, p, f);
            let snapshot = (
                s.shell.line,
                s.shell.len,
                s.shell.rejected,
                s.shell.skip_lf,
                s.shell.cursor,
            );
            let output = h.output.clone();
            begin(s, &mut h, p, f, Action::Inspect, 0);
            finish(s, &mut h, p, f);
            assert_eq!(
                snapshot,
                (
                    s.shell.line,
                    s.shell.len,
                    s.shell.rejected,
                    s.shell.skip_lf,
                    s.shell.cursor
                )
            );
            assert_eq!(h.output, output);
            assert!(p.0.borrow().calls.is_empty());
        });
    }
}

#[test]
fn launch_reply_and_ack_backpressure_cannot_repeat_admission() {
    fixture(|s, p, f| {
        let mut h = Host::default();
        until_read(s, &mut h, p, f);
        p.0.borrow_mut()
            .results
            .extend([(6, 0), (6, 0), (0, CHILD)]);
        let request = begin(s, &mut h, p, f, Action::Start, 0);
        for _ in 0..3 {
            tick(s, &mut h, p, f).unwrap();
        }
        assert!(matches!(s.phase, Phase::Send(_)));
        let count = h.sends.len();
        h.block_send = true;
        for _ in 0..5 {
            tick(s, &mut h, p, f).unwrap();
        }
        let expected = Exchange::Control(Frame::Reply(
            Reply::new(request, Status::Admitted, 1).unwrap(),
        ));
        assert!(h.sends[count..].iter().all(|v| *v == expected));
        assert_eq!(p.0.borrow().calls, [(19, 0x100060001, 1); 3]);
        h.block_send = false;
        tick(s, &mut h, p, f).unwrap();
        h.block_receive = true;
        for _ in 0..5 {
            tick(s, &mut h, p, f).unwrap();
        }
        assert_eq!(s.shell.sequence, request.sequence());
        h.block_receive = false;
        tick(s, &mut h, p, f).unwrap();
        assert_eq!(s.shell.sequence, request.sequence() + 2);
        assert_eq!(p.0.borrow().calls.len(), 3);
    });
}

#[test]
fn wrong_sequence_and_reply_direction_reject_before_process_effects() {
    for variant in 0..3 {
        fixture(|s, p, f| {
            let mut h = Host::default();
            until_read(s, &mut h, p, f);
            let seq = s.shell.sequence;
            let request = Request::new(
                if variant == 0 {
                    seq - 1
                } else if variant == 1 {
                    seq + 1
                } else {
                    seq
                },
                App::Text,
                Action::Start,
                0,
            )
            .unwrap();
            h.next = Some(Ok(Exchange::Control(if variant == 2 {
                Frame::Reply(Reply::new(request, Status::Admitted, 1).unwrap())
            } else {
                Frame::Request(request)
            })));
            assert!(tick(s, &mut h, p, f).is_err());
            let before = h.calls;
            assert_eq!(tick(s, &mut h, p, f), Err(Error::Transport));
            assert_eq!(h.calls, before);
            assert!(p.0.borrow().calls.is_empty());
        });
    }
}

#[test]
fn control_cannot_replace_write_or_close_acknowledgment() {
    for kind in [Kind::Written, Kind::Closed] {
        fixture(|s, p, f| {
            let mut h = Host::default();
            tick(s, &mut h, p, f).unwrap();
            s.shell.pending = Some((kind, 16));
            let request = Request::new(s.shell.sequence, App::Text, Action::Start, 0).unwrap();
            h.next = Some(Ok(Exchange::Control(Frame::Request(request))));
            assert_eq!(tick(s, &mut h, p, f), Err(Error::Sequence));
            assert!(p.0.borrow().calls.is_empty());
            assert_eq!(s.shell.cursor, 0);
            assert_eq!(s.shell.pending, Some((kind, 16)));
        });
    }
}

#[test]
fn mismatched_ack_poisoning_retains_owned_child_without_relaunch() {
    for variant in 0..4 {
        fixture(|s, p, f| {
            let mut h = Host::default();
            until_read(s, &mut h, p, f);
            p.0.borrow_mut().results.push_back((0, CHILD));
            let request = begin(s, &mut h, p, f, Action::Start, 0);
            tick(s, &mut h, p, f).unwrap();
            tick(s, &mut h, p, f).unwrap();
            let reply = match variant {
                0 => {
                    Exchange::Console(Message::new(Kind::Written, request.sequence(), &[]).unwrap())
                }
                1 => Exchange::Console(
                    Message::new(Kind::Written, request.sequence() + 2, &[]).unwrap(),
                ),
                2 => Exchange::Console(
                    Message::new(Kind::Input, request.sequence() + 1, b"x").unwrap(),
                ),
                _ => Exchange::Control(Frame::Request(request)),
            };
            h.next = Some(Ok(reply));
            assert!(tick(s, &mut h, p, f).is_err());
            let before = h.calls;
            assert_eq!(tick(s, &mut h, p, f), Err(Error::Transport));
            assert_eq!(h.calls, before);
            assert_eq!(p.0.borrow().calls.len(), 1);
            assert!(!s.shell.commands.process_owner().close_allowed());
        });
    }
}

#[test]
fn malformed_kernel_result_and_revoked_send_fail_closed() {
    for malformed in [true, false] {
        fixture(|s, p, f| {
            let mut h = Host::default();
            until_read(s, &mut h, p, f);
            p.0.borrow_mut()
                .results
                .push_back((0, if malformed { 0x100010001 } else { CHILD }));
            begin(s, &mut h, p, f, Action::Start, 0);
            if malformed {
                assert_eq!(tick(s, &mut h, p, f), Err(Error::Transport));
            } else {
                tick(s, &mut h, p, f).unwrap();
                h.fail_send = true;
                assert_eq!(tick(s, &mut h, p, f), Err(Error::Revoked));
            }
            let before = h.calls;
            assert_eq!(tick(s, &mut h, p, f), Err(Error::Transport));
            assert_eq!(h.calls, before);
            assert_eq!(p.0.borrow().calls.len(), 1);
            assert!(!s.shell.commands.process_owner().close_allowed());
        });
    }
}

#[test]
fn exhausted_session_rejects_before_launch_and_last_valid_sequence_completes() {
    for sequence in [u64::MAX - 2, u64::MAX - 1] {
        fixture(|s, p, f| {
            let mut h = Host::default();
            until_read(s, &mut h, p, f);
            s.shell.sequence = sequence;
            h.next = Some(Ok(Exchange::Control(Frame::Request(
                Request::new(sequence, App::Text, Action::Start, 0).unwrap(),
            ))));
            assert_eq!(tick(s, &mut h, p, f), Err(Error::Sequence));
            assert!(p.0.borrow().calls.is_empty());
        });
    }
    fixture(|s, p, f| {
        let mut h = Host::default();
        until_read(s, &mut h, p, f);
        s.shell.sequence = u64::MAX - 3;
        begin(s, &mut h, p, f, Action::Inspect, 0);
        finish(s, &mut h, p, f);
        assert_eq!(s.shell.sequence, u64::MAX - 1);
        tick(s, &mut h, p, f).unwrap();
        assert_eq!(h.pending.unwrap().sequence(), u64::MAX - 1);
    });
}

#[test]
fn active_file_job_keeps_request_and_output_until_normal_completion() {
    fixture(|s, p, f| {
        let mut h = Host {
            input: b"cat /readme.txt\r".iter().copied().collect(),
            ..Host::default()
        };
        for _ in 0..1000 {
            tick(s, &mut h, p, f).unwrap();
            if f.0.borrow().request.is_some() {
                break;
            }
        }
        assert!(f.0.borrow().request.is_some());
        let before = f.0.borrow().request;
        let request = Request::new(s.shell.sequence, App::Text, Action::Start, 0).unwrap();
        h.next = Some(Ok(Exchange::Control(Frame::Request(request))));
        let transport_calls = h.calls;
        for _ in 0..10 {
            tick(s, &mut h, p, f).unwrap();
        }
        assert_eq!(h.calls, transport_calls);
        assert_eq!(f.0.borrow().request, before);
        assert_eq!(f.0.borrow().calls.iter().filter(|&&n| n == 10).count(), 1);
        assert!(p.0.borrow().calls.is_empty());
        assert!(matches!(s.shell.next, super::super::Next::Command));
        h.next = None;
        f.0.borrow_mut().blocked = false;
        until_read(s, &mut h, p, f);
        assert!(h.output.ends_with(b"PooleOS> "));
        assert!(
            !h.output
                .windows(b"File not found".len())
                .any(|w| w == b"File not found")
        );
        assert!(f.0.borrow().request.is_none());
        begin(s, &mut h, p, f, Action::Inspect, 0);
        finish(s, &mut h, p, f);
        assert!(p.0.borrow().calls.is_empty());
    });
}

#[test]
fn waiting_application_job_cannot_be_interrupted_by_control() {
    fixture(|s, p, f| {
        let mut h = Host::default();
        until_read(s, &mut h, p, f);
        p.0.borrow_mut().results.push_back((0, CHILD));
        begin(s, &mut h, p, f, Action::Start, 0);
        finish(s, &mut h, p, f);
        h.input.extend(b"text /readme.txt\r");
        p.0.borrow_mut().results.extend([(6, 1); 20]);
        for _ in 0..1000 {
            tick(s, &mut h, p, f).unwrap();
            if f.0.borrow().calls.contains(&7) {
                break;
            }
        }
        assert!(f.0.borrow().calls.contains(&7));
        let calls = h.calls;
        for _ in 0..10 {
            tick(s, &mut h, p, f).unwrap();
        }
        assert_eq!(h.calls, calls);
        assert_eq!(
            p.0.borrow()
                .calls
                .iter()
                .filter(|&&(n, _, _)| n == 19)
                .count(),
            1
        );
        assert!(matches!(s.shell.next, super::super::Next::Command));
    });
}

#[test]
fn stale_control_does_not_change_generation_or_cli_output() {
    fixture(|s, p, f| {
        let mut h = Host::default();
        until_read(s, &mut h, p, f);
        let before = h.output.clone();
        let request = begin(s, &mut h, p, f, Action::Start, 9);
        finish(s, &mut h, p, f);
        assert!(h.sends.contains(&Exchange::Control(Frame::Reply(
            Reply::new(request, Status::Stale, 0).unwrap()
        ))));
        assert_eq!(h.output, before);
        assert!(p.0.borrow().calls.is_empty());
    });
}
