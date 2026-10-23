use super::*;
use crate::{console_ipc::Message, shell::Commands};
use std::{cell::RefCell, collections::VecDeque, rc::Rc, vec::Vec};

const FACTORIES: [u64; 2] = [0x100060001, 0x100060002];
const CHILD: u64 = 0x100050001;
const TERMINAL: (u64, u64) = (0, 4 << 32);

#[derive(Default)]
struct State {
    results: VecDeque<(u64, u64)>,
    calls: Vec<(u64, u64, u64)>,
}
#[derive(Clone, Default)]
struct Fake(Rc<RefCell<State>>);
impl Calls for Fake {
    fn invoke(&mut self, n: u64, h: u64, a: u64) -> (u64, u64) {
        let mut state = self.0.borrow_mut();
        state.calls.push((n, h, a));
        state.results.pop_front().expect("unexpected syscall")
    }
}
fn fixture() -> (Broker, ApplicationProcesses<Fake>, Fake) {
    let calls = Fake::default();
    (
        Broker::new(),
        ApplicationProcesses::new(FACTORIES, calls.clone()).unwrap(),
        calls,
    )
}
fn request(seq: u64, app: App, action: Action, generation: u32) -> Request {
    Request::new(seq, app, action, generation).unwrap()
}
fn start(seq: u64, generation: u32) -> Request {
    request(seq, App::Text, Action::Start, generation)
}
fn step(
    b: &mut Broker,
    p: &mut ApplicationProcesses<Fake>,
    calls: &Fake,
    result: (u64, u64),
) -> Result<bool, Error> {
    let before = calls.0.borrow().calls.len();
    calls.0.borrow_mut().results.push_back(result);
    let result = b.poll(p);
    assert_eq!(calls.0.borrow().calls.len(), before + 1);
    assert!(calls.0.borrow().results.is_empty());
    result
}
fn admitted(b: &mut Broker, p: &mut ApplicationProcesses<Fake>, calls: &Fake) {
    b.begin(start(1, 0), p).unwrap();
    assert_eq!(step(b, p, calls, (0, CHILD)), Ok(true));
    assert_eq!(b.reply().unwrap().status(), Status::Admitted);
    assert_eq!(b.reply().unwrap().generation(), 1);
    b.acknowledge(1).unwrap();
}

#[test]
fn exact_wire_roundtrip_and_legacy_decoder_rejects_control() {
    for app in [App::Text, App::Numbers] {
        for action in [Action::Start, Action::Inspect] {
            for generation in [0, 1, u32::MAX] {
                let req = request(u64::MAX - 1, app, action, generation);
                let frame = Frame::Request(req);
                assert_eq!(Frame::decode(&frame.encode()), Ok(frame));
                assert!(Message::decode(&frame.encode()).is_err());
                assert_eq!(&frame.encode()[..4], b"PLC1");
                assert_eq!(&frame.encode()[20..], &[0; 12]);
            }
        }
    }
    let req = start(7, 1);
    for (status, generation) in [
        (Status::Admitted, 2),
        (Status::Running, 1),
        (Status::StopPending, 1),
        (Status::StopClaimed, 1),
        (Status::Retiring, 1),
        (Status::Absent, 1),
        (Status::Terminal, 1),
        (Status::Denied, 1),
        (Status::LaunchFailed, 2),
        (Status::Stale, 0),
        (Status::Busy, 1),
    ] {
        let reply = Reply::new(req, status, generation).unwrap();
        assert_eq!(reply.request(), req);
        let frame = Frame::Reply(reply);
        assert_eq!(Frame::decode(&frame.encode()), Ok(frame));
        assert!(Message::decode(&frame.encode()).is_err());
    }
    let frame = Frame::Reply(Reply::new(start(1, u32::MAX), Status::Exhausted, u32::MAX).unwrap());
    assert_eq!(Frame::decode(&frame.encode()), Ok(frame));
}

#[test]
fn reserved_fields_lengths_and_unknown_enums_are_rejected() {
    let valid = Frame::Request(start(1, 0)).encode();
    for n in 0..BYTES {
        assert!(Frame::decode(&valid[..n]).is_err());
    }
    let mut long = valid.to_vec();
    long.push(0);
    assert_eq!(Frame::decode(&long), Err(Error::Wire));
    for offset in [
        0, 1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
    ] {
        let mut wire = valid;
        wire[offset] = 255;
        assert_eq!(Frame::decode(&wire), Err(Error::Wire), "offset {offset}");
    }
    for (offset, values) in [(4, &[0, 3][..]), (5, &[0, 3]), (6, &[0, 3])] {
        for &value in values {
            let mut wire = valid;
            wire[offset] = value;
            assert_eq!(Frame::decode(&wire), Err(Error::Wire));
        }
    }
    for status in [0, 13, 255] {
        let mut wire = Frame::Reply(Reply::new(start(1, 0), Status::Admitted, 1).unwrap()).encode();
        wire[7] = status;
        assert_eq!(Frame::decode(&wire), Err(Error::Wire));
    }
}

#[test]
fn generation_relations_cannot_be_forged() {
    for status in [Status::Admitted, Status::LaunchFailed] {
        for (action, expected, actual) in [
            (Action::Inspect, 0, 1),
            (Action::Start, 1, 1),
            (Action::Start, u32::MAX, 0),
        ] {
            assert_eq!(
                Reply::new(request(1, App::Text, action, expected), status, actual),
                Err(Error::Wire)
            );
        }
    }
    for status in [
        Status::Running,
        Status::StopPending,
        Status::StopClaimed,
        Status::Retiring,
        Status::Terminal,
    ] {
        assert_eq!(Reply::new(start(1, 0), status, 0), Err(Error::Wire));
        assert_eq!(Reply::new(start(1, 1), status, 2), Err(Error::Wire));
    }
    for status in [Status::Absent, Status::Denied, Status::Busy] {
        assert_eq!(Reply::new(start(1, 0), status, 1), Err(Error::Wire));
    }
    assert_eq!(Reply::new(start(1, 1), Status::Stale, 1), Err(Error::Wire));
    assert_eq!(
        Reply::new(start(1, 1), Status::Exhausted, 1),
        Err(Error::Wire)
    );
    assert_eq!(
        Reply::new(
            request(1, App::Text, Action::Inspect, u32::MAX),
            Status::Exhausted,
            u32::MAX
        ),
        Err(Error::Wire)
    );
    let mut wire = Frame::Reply(Reply::new(start(1, 0), Status::Admitted, 1).unwrap()).encode();
    wire[20..24].fill(0);
    assert_eq!(Frame::decode(&wire), Err(Error::Wire));
}

#[test]
fn sequence_zero_and_overflow_are_rejected_at_construction_and_decode() {
    for seq in [0, u64::MAX] {
        assert_eq!(
            Request::new(seq, App::Text, Action::Start, 0),
            Err(Error::Sequence)
        );
        let mut wire = Frame::Request(start(1, 0)).encode();
        wire[8..16].copy_from_slice(&seq.to_le_bytes());
        assert_eq!(Frame::decode(&wire), Err(Error::Sequence));
    }
}

#[test]
fn absent_inspection_is_typed_without_kernel_calls() {
    let (mut b, mut p, calls) = fixture();
    b.begin(request(9, App::Numbers, Action::Inspect, 0), &mut p)
        .unwrap();
    assert!(b.poll(&mut p).unwrap());
    assert_eq!(b.reply().unwrap().status(), Status::Absent);
    assert_eq!(b.reply().unwrap().generation(), 0);
    assert!(calls.0.borrow().calls.is_empty());
    assert!(p.close_allowed());
}

#[test]
fn launch_backpressure_ack_and_replay_do_not_duplicate_effects() {
    let (mut b, mut p, calls) = fixture();
    b.begin(start(5, 0), &mut p).unwrap();
    assert_eq!(b.acknowledge(5), Err(Error::Sequence));
    for _ in 0..5 {
        assert_eq!(step(&mut b, &mut p, &calls, (6, 0)), Ok(false));
        assert_eq!(b.begin(start(6, 0), &mut p), Err(Error::Sequence));
        assert!(!p.close_allowed());
    }
    assert_eq!(step(&mut b, &mut p, &calls, (0, CHILD)), Ok(true));
    for _ in 0..5 {
        assert_eq!(b.poll(&mut p), Ok(true));
    }
    assert_eq!(calls.0.borrow().calls, [(19, FACTORIES[0], 1); 6]);
    assert_eq!(b.acknowledge(6), Err(Error::Sequence));
    assert!(b.reply().is_some());
    b.acknowledge(5).unwrap();
    assert_eq!(b.acknowledge(5), Err(Error::Sequence));
    for seq in [1, 4, 5] {
        assert_eq!(b.begin(start(seq, 1), &mut p), Err(Error::Sequence));
    }
    assert!(!p.close_allowed());
}

#[test]
fn stale_generations_have_no_side_effects_and_resynchronize() {
    let (mut b, mut p, calls) = fixture();
    admitted(&mut b, &mut p, &calls);
    for (seq, generation) in [(2, 0), (3, 2), (4, u32::MAX)] {
        b.begin(start(seq, generation), &mut p).unwrap();
        assert_eq!(b.poll(&mut p), Ok(true));
        assert_eq!(b.reply().unwrap().status(), Status::Stale);
        assert_eq!(b.reply().unwrap().generation(), 1);
        b.acknowledge(seq).unwrap();
    }
    assert_eq!(calls.0.borrow().calls.len(), 1);
    assert_eq!(p.child(0).unwrap().handle, CHILD);
}

#[test]
fn live_and_retiring_instances_cannot_be_replaced() {
    let (mut b, mut p, calls) = fixture();
    admitted(&mut b, &mut p, &calls);
    for (value, status) in [
        (1, Status::Running),
        (2, Status::StopPending),
        (3, Status::StopClaimed),
        (4, Status::Retiring),
    ] {
        b.begin(start(value + 1, 1), &mut p).unwrap();
        assert_eq!(step(&mut b, &mut p, &calls, (6, value)), Ok(true));
        assert_eq!(b.reply().unwrap().status(), status);
        assert_eq!(b.reply().unwrap().generation(), 1);
        b.acknowledge(value + 1).unwrap();
        assert!(!p.close_allowed());
        assert_eq!(p.child(0).unwrap().handle, CHILD);
    }
    assert_eq!(&calls.0.borrow().calls[1..], &[(20, CHILD, 0); 4]);
}

#[test]
fn restart_requires_terminal_observation_and_a_separate_launch_step() {
    let (mut b, mut p, calls) = fixture();
    admitted(&mut b, &mut p, &calls);
    b.begin(start(2, 1), &mut p).unwrap();
    assert_eq!(step(&mut b, &mut p, &calls, TERMINAL), Ok(false));
    assert!(p.child(0).is_none());
    assert!(!p.close_allowed());
    for _ in 0..3 {
        assert_eq!(step(&mut b, &mut p, &calls, (6, 0)), Ok(false));
    }
    assert_eq!(
        step(&mut b, &mut p, &calls, (0, CHILD + (1 << 32))),
        Ok(true)
    );
    assert_eq!(b.reply().unwrap().status(), Status::Admitted);
    assert_eq!(b.reply().unwrap().generation(), 2);
    assert_eq!(calls.0.borrow().calls[1], (20, CHILD, 0));
    assert_eq!(&calls.0.borrow().calls[2..], &[(19, FACTORIES[0], 2); 4]);
}

#[test]
fn failed_launch_consumes_generation_but_denial_does_not() {
    let (mut b, mut p, calls) = fixture();
    for (seq, result, status, generation) in [
        (1, (5, 0), Status::Denied, 0),
        (2, (8, 0), Status::LaunchFailed, 1),
    ] {
        b.begin(start(seq, 0), &mut p).unwrap();
        assert_eq!(step(&mut b, &mut p, &calls, result), Ok(true));
        assert_eq!(b.reply().unwrap().status(), status);
        assert_eq!(b.reply().unwrap().generation(), generation);
        b.acknowledge(seq).unwrap();
        assert!(p.child(0).is_none() && p.close_allowed());
    }
    b.begin(request(3, App::Text, Action::Inspect, 1), &mut p)
        .unwrap();
    assert_eq!(b.reply().unwrap().status(), Status::Absent);
    b.acknowledge(3).unwrap();
    b.begin(start(4, 1), &mut p).unwrap();
    assert_eq!(step(&mut b, &mut p, &calls, (0, CHILD)), Ok(true));
    assert_eq!(calls.0.borrow().calls.last(), Some(&(19, FACTORIES[0], 2)));
}

#[test]
fn failed_restart_clears_only_retired_handle() {
    let (mut b, mut p, calls) = fixture();
    admitted(&mut b, &mut p, &calls);
    b.begin(start(2, 1), &mut p).unwrap();
    assert_eq!(step(&mut b, &mut p, &calls, TERMINAL), Ok(false));
    assert_eq!(step(&mut b, &mut p, &calls, (8, 0)), Ok(true));
    assert_eq!(b.reply().unwrap().generation(), 2);
    assert!(p.child(0).is_none() && p.close_allowed());
    b.acknowledge(2).unwrap();
    b.begin(request(3, App::Text, Action::Inspect, 2), &mut p)
        .unwrap();
    assert_eq!(b.reply().unwrap().status(), Status::Absent);
}

#[test]
fn command_in_progress_is_not_overwritten_by_graphical_request() {
    let (mut b, mut p, calls) = fixture();
    assert!(p.begin(b"start numbers").unwrap());
    b.begin(start(1, 0), &mut p).unwrap();
    assert_eq!(b.reply().unwrap().status(), Status::Busy);
    assert_eq!(b.poll(&mut p), Ok(true));
    assert!(calls.0.borrow().calls.is_empty());
    b.acknowledge(1).unwrap();
    calls.0.borrow_mut().results.push_back((0, CHILD));
    assert!(p.poll().unwrap());
    assert_eq!(p.response(), b"numbers: admitted\r\n");
    assert_eq!(calls.0.borrow().calls, [(19, FACTORIES[1], 1)]);
}

#[test]
fn graphical_operation_cannot_be_polled_or_replaced_by_cli() {
    let (mut b, mut p, calls) = fixture();
    b.begin(start(1, 0), &mut p).unwrap();
    assert_eq!(p.begin(b"start text"), Err(Error::Sequence));
    assert_eq!(p.poll(), Err(Error::Sequence));
    assert_eq!(p.observe(0), Err(Error::Sequence));
    assert_eq!(p.request_stop(0), Err(Error::Sequence));
    assert!(calls.0.borrow().calls.is_empty());
    assert_eq!(step(&mut b, &mut p, &calls, (0, CHILD)), Ok(true));
    assert_eq!(p.response(), b"");
}

#[test]
fn inspect_reports_liveness_without_launch_or_stop_authority() {
    let (mut b, mut p, calls) = fixture();
    admitted(&mut b, &mut p, &calls);
    for (i, (value, status)) in [(6, 1), (6, 2), (6, 3), (6, 4), (5, 0), TERMINAL]
        .into_iter()
        .zip([
            Status::Running,
            Status::StopPending,
            Status::StopClaimed,
            Status::Retiring,
            Status::Denied,
            Status::Terminal,
        ])
        .enumerate()
    {
        let seq = i as u64 + 2;
        b.begin(request(seq, App::Text, Action::Inspect, 1), &mut p)
            .unwrap();
        assert_eq!(step(&mut b, &mut p, &calls, value), Ok(true));
        assert_eq!(b.reply().unwrap().status(), status);
        b.acknowledge(seq).unwrap();
        assert_eq!(p.close_allowed(), status == Status::Terminal);
    }
    assert_eq!(&calls.0.borrow().calls[1..], &[(20, CHILD, 0); 6]);
}

#[test]
fn malformed_launch_result_poison_retains_pending_ownership() {
    for result in [(0, 0), (0, FACTORIES[0]), (6, 1), (8, 1), (5, 1), (9, 0)] {
        let (mut b, mut p, calls) = fixture();
        b.begin(start(1, 0), &mut p).unwrap();
        assert_eq!(step(&mut b, &mut p, &calls, result), Err(Error::Transport));
        assert_eq!(b.poll(&mut p), Err(Error::Transport));
        assert_eq!(b.acknowledge(1), Err(Error::Transport));
        assert_eq!(b.begin(start(2, 0), &mut p), Err(Error::Transport));
        assert_eq!(p.begin(b"start text"), Err(Error::Sequence));
        assert!(p.child(0).is_none() && !p.close_allowed());
        assert!(b.reply().is_none());
        assert_eq!(calls.0.borrow().calls.len(), 1);
    }
}

#[test]
fn malformed_inspect_cannot_retire_or_restart_live_process() {
    for action in [Action::Inspect, Action::Start] {
        for result in [(0, 0), (0, 8 << 32), (6, 0), (6, 5), (9, 0), (5, 1)] {
            let (mut b, mut p, calls) = fixture();
            admitted(&mut b, &mut p, &calls);
            b.begin(request(2, App::Text, action, 1), &mut p).unwrap();
            assert_eq!(step(&mut b, &mut p, &calls, result), Err(Error::Transport));
            assert_eq!(p.child(0).unwrap().handle, CHILD);
            assert!(!p.close_allowed());
            assert_eq!(b.poll(&mut p), Err(Error::Transport));
            assert_eq!(calls.0.borrow().calls.len(), 2);
        }
    }
}

#[test]
fn duplicate_child_handle_cannot_alias_app_identity() {
    let (mut b, mut p, calls) = fixture();
    admitted(&mut b, &mut p, &calls);
    b.begin(request(2, App::Numbers, Action::Start, 0), &mut p)
        .unwrap();
    assert_eq!(
        step(&mut b, &mut p, &calls, (0, CHILD)),
        Err(Error::Transport)
    );
    assert_eq!(p.child(0).unwrap().handle, CHILD);
    assert!(p.child(1).is_none());
}

#[test]
fn final_valid_request_sequence_can_be_acknowledged_but_not_replayed() {
    let (mut b, mut p, calls) = fixture();
    let req = request(u64::MAX - 1, App::Text, Action::Inspect, 0);
    b.begin(req, &mut p).unwrap();
    b.acknowledge(u64::MAX - 1).unwrap();
    assert_eq!(b.begin(req, &mut p), Err(Error::Sequence));
    assert_eq!(b.begin(start(1, 0), &mut p), Err(Error::Sequence));
    assert!(calls.0.borrow().calls.is_empty());
}

#[test]
fn unbound_policy_rejects_without_consuming_request() {
    let calls = Fake::default();
    let mut p = ApplicationProcesses::unbound(calls.clone());
    let mut b = Broker::new();
    assert_eq!(b.begin(start(1, 0), &mut p), Err(Error::Wire));
    p.bind(FACTORIES).unwrap();
    b.begin(start(1, 0), &mut p).unwrap();
    assert_eq!(step(&mut b, &mut p, &calls, (0, CHILD)), Ok(true));
}
