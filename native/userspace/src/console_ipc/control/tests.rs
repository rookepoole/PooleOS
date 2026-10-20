use super::*;
use crate::{console, session_control::Status};
use std::{collections::VecDeque, vec::Vec};

#[derive(Default)]
struct Link {
    incoming: VecDeque<Result<Exchange, Error>>,
    sent: Vec<Exchange>,
    blocked: bool,
    failure: Option<Error>,
    calls: usize,
}
impl Channel for Link {
    fn receive(&mut self) -> Result<Option<Exchange>, Error> {
        self.calls += 1;
        self.incoming.pop_front().transpose()
    }
    fn send(&mut self, exchange: Exchange) -> Result<bool, Error> {
        self.calls += 1;
        self.sent.push(exchange);
        if let Some(error) = self.failure {
            return Err(error);
        }
        Ok(!self.blocked)
    }
}
#[derive(Default)]
struct Port {
    input: VecDeque<u8>,
    output: Vec<u8>,
    busy: bool,
    calls: usize,
}
impl Registers for Port {
    fn read(&mut self, offset: u8) -> Result<u8, console::Error> {
        self.calls += 1;
        match offset {
            5 => Ok(if self.busy { 0 } else { 0x60 } | u8::from(!self.input.is_empty())),
            0 => Ok(self.input.pop_front().unwrap()),
            _ => panic!("unexpected port read"),
        }
    }
    fn write(&mut self, offset: u8, value: u8) -> Result<(), console::Error> {
        self.calls += 1;
        assert_eq!(offset, 0);
        self.output.push(value);
        Ok(())
    }
}
fn waiting(sequence: u64) -> Server {
    let mut server = Server::new();
    server.console.sequence = sequence;
    server.console.phase = crate::console_ipc::Phase::Read;
    server
}
fn start(server: &mut Server) {
    assert_eq!(server.request(App::Text, Action::Start, 0), Ok(true));
}
fn poll(server: &mut Server, link: &mut Link) {
    let before = link.calls;
    let mut port = Port::default();
    assert_eq!(server.poll(&mut port, link), Ok(false));
    assert!(link.calls - before <= 1);
    assert_eq!(
        port.calls, 0,
        "control must not read or write terminal bytes"
    );
}
fn admitted(sequence: u64) -> Reply {
    Reply::new(
        Request::new(sequence, App::Text, Action::Start, 0).unwrap(),
        Status::Admitted,
        1,
    )
    .unwrap()
}

#[test]
fn control_slot_requires_outstanding_read_and_no_unconsumed_result() {
    use crate::console_ipc::Phase as Ordinary;
    for phase in [
        Ordinary::Idle,
        Ordinary::Write {
            message: Message::new(Kind::Write, 1, b"x").unwrap(),
            cursor: 0,
        },
        Ordinary::Drain,
        Ordinary::Reply {
            message: Message::new(Kind::Input, 1, b"x").unwrap(),
            closing: false,
        },
        Ordinary::Closed,
    ] {
        let mut s = waiting(1);
        s.console.phase = phase;
        assert_eq!(s.request(App::Text, Action::Start, 0), Ok(false));
        assert_eq!(s.console.phase, phase);
    }
    let mut s = waiting(1);
    s.result = Some(admitted(1));
    assert_eq!(s.request(App::Numbers, Action::Inspect, 0), Ok(false));
    assert!(s.take_result().is_some());
    start(&mut s);
    assert_eq!(s.request(App::Text, Action::Start, 0), Ok(false));
}

#[test]
fn exact_request_result_ack_are_retained_under_backpressure() {
    let mut s = waiting(7);
    let mut link = Link {
        blocked: true,
        ..Link::default()
    };
    start(&mut s);
    for _ in 0..4 {
        poll(&mut s, &mut link);
    }
    assert!(
        link.sent
            .iter()
            .all(|v| *v == Exchange::Control(Frame::Request(admitted(7).request())))
    );
    assert!(s.take_result().is_none());
    link.blocked = false;
    poll(&mut s, &mut link);
    for _ in 0..3 {
        poll(&mut s, &mut link);
    }
    link.incoming
        .push_back(Ok(Exchange::Control(Frame::Reply(admitted(7)))));
    poll(&mut s, &mut link);
    assert!(s.take_result().is_none());
    link.blocked = true;
    for _ in 0..4 {
        poll(&mut s, &mut link);
    }
    let ack = Exchange::Console(Message::new(Kind::Written, 8, &[]).unwrap());
    assert!(link.sent[5..].iter().all(|v| *v == ack));
    assert_eq!(s.console.sequence, 7);
    link.blocked = false;
    poll(&mut s, &mut link);
    assert_eq!(s.console.sequence, 9);
    assert_eq!(s.console.phase, crate::console_ipc::Phase::Idle);
    assert_eq!(s.take_result(), Some(admitted(7)));
    assert_eq!(s.take_result(), None);
}

#[test]
fn wrong_request_identity_in_result_poisons_without_ack() {
    for request in [
        Request::new(8, App::Text, Action::Start, 0).unwrap(),
        Request::new(7, App::Numbers, Action::Start, 0).unwrap(),
        Request::new(7, App::Text, Action::Inspect, 0).unwrap(),
        Request::new(7, App::Text, Action::Start, 1).unwrap(),
    ] {
        let mut s = waiting(7);
        let mut link = Link::default();
        start(&mut s);
        poll(&mut s, &mut link);
        link.incoming.push_back(Ok(Exchange::Control(Frame::Reply(
            Reply::new(request, Status::Busy, request.generation).unwrap(),
        ))));
        assert_eq!(
            s.poll(&mut Port::default(), &mut link),
            Err(Error::Sequence)
        );
        let calls = link.calls;
        assert_eq!(
            s.poll(&mut Port::default(), &mut link),
            Err(Error::Transport)
        );
        assert_eq!(
            s.request(App::Text, Action::Start, 0),
            Err(Error::Transport)
        );
        assert_eq!(link.calls, calls);
        assert_eq!(link.sent.len(), 1);
        assert!(s.take_result().is_none());
    }
}

#[test]
fn wrong_direction_or_console_result_is_rejected() {
    for wrong in [
        Exchange::Control(Frame::Request(admitted(7).request())),
        Exchange::Console(Message::new(Kind::Read, 8, &[]).unwrap()),
        Exchange::Console(Message::new(Kind::Written, 8, &[]).unwrap()),
    ] {
        let mut s = waiting(7);
        let mut link = Link::default();
        start(&mut s);
        poll(&mut s, &mut link);
        link.incoming.push_back(Ok(wrong));
        assert_eq!(s.poll(&mut Port::default(), &mut link), Err(Error::Wire));
        assert_eq!(link.sent.len(), 1);
    }
}

#[test]
fn duplicate_result_after_ack_cannot_start_another_transaction() {
    let mut s = waiting(7);
    let mut link = Link::default();
    start(&mut s);
    poll(&mut s, &mut link);
    let result = Exchange::Control(Frame::Reply(admitted(7)));
    link.incoming.push_back(Ok(result));
    poll(&mut s, &mut link);
    poll(&mut s, &mut link);
    assert_eq!(s.take_result(), Some(admitted(7)));
    link.incoming.push_back(Ok(result));
    assert_eq!(s.poll(&mut Port::default(), &mut link), Err(Error::Wire));
    assert_eq!(link.sent.len(), 2);
}

#[test]
fn exhaustion_rejects_before_send_and_last_valid_transaction_resumes() {
    for sequence in [0, u64::MAX - 2, u64::MAX - 1, u64::MAX] {
        let mut s = waiting(sequence);
        assert_eq!(s.request(App::Text, Action::Start, 0), Err(Error::Sequence));
        let mut link = Link::default();
        assert_eq!(
            s.poll(&mut Port::default(), &mut link),
            Err(Error::Transport)
        );
        assert_eq!(link.calls, 0);
    }
    let sequence = u64::MAX - 3;
    let mut s = waiting(sequence);
    let mut link = Link::default();
    start(&mut s);
    poll(&mut s, &mut link);
    link.incoming
        .push_back(Ok(Exchange::Control(Frame::Reply(admitted(sequence)))));
    poll(&mut s, &mut link);
    poll(&mut s, &mut link);
    assert_eq!(s.console.sequence, u64::MAX - 1);
    assert!(s.take_result().is_some());
}

#[test]
fn transport_failure_at_request_result_or_ack_never_retries_effect() {
    for stage in 0..3 {
        let mut s = waiting(7);
        let mut link = Link::default();
        start(&mut s);
        if stage > 0 {
            poll(&mut s, &mut link);
        }
        if stage == 2 {
            link.incoming
                .push_back(Ok(Exchange::Control(Frame::Reply(admitted(7)))));
            poll(&mut s, &mut link);
        }
        if stage == 1 {
            link.incoming.push_back(Err(Error::Revoked));
        } else {
            link.failure = Some(Error::Revoked);
        }
        assert_eq!(s.poll(&mut Port::default(), &mut link), Err(Error::Revoked));
        let before = link.calls;
        assert_eq!(
            s.poll(&mut Port::default(), &mut link),
            Err(Error::Transport)
        );
        assert_eq!(link.calls, before);
        assert!(s.take_result().is_none());
    }
}

#[test]
fn partially_written_output_and_already_read_input_are_not_replaced() {
    let mut s = Server::new();
    let mut link = Link::default();
    let mut port = Port::default();
    link.incoming.push_back(Ok(Exchange::Console(
        Message::new(Kind::Write, 1, b"abc").unwrap(),
    )));
    s.poll(&mut port, &mut link).unwrap();
    for expected in [b"a".as_slice(), b"ab", b"abc"] {
        assert_eq!(s.request(App::Text, Action::Start, 0), Ok(false));
        s.poll(&mut port, &mut link).unwrap();
        assert_eq!(port.output, expected);
    }
    assert_eq!(s.request(App::Text, Action::Start, 0), Ok(false));
    s.poll(&mut port, &mut link).unwrap();
    link.incoming.push_back(Ok(Exchange::Console(
        Message::new(Kind::Read, 2, &[]).unwrap(),
    )));
    s.poll(&mut port, &mut link).unwrap();
    port.input.push_back(b'z');
    s.poll(&mut port, &mut link).unwrap();
    assert_eq!(s.request(App::Text, Action::Start, 0), Ok(false));
    s.poll(&mut port, &mut link).unwrap();
    assert_eq!(
        link.sent.last(),
        Some(&Exchange::Console(
            Message::new(Kind::Input, 2, b"z").unwrap()
        ))
    );
}
