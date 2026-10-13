use super::*;
use std::{collections::VecDeque, vec::Vec};
const FACTORIES: [u64; 2] = [0x100060001, 0x100060002];
const CHILD: u64 = 0x100050001;

#[test]
fn in_place_binding_is_atomic_and_cannot_reset_authority_or_generations() {
    let mut p = Processes::unbound(Fake::default());
    assert!(!p.close_allowed());
    assert_eq!(p.begin(b"start worker"), Err(Error::Wire));
    assert_eq!(p.bind([FACTORIES[0], 0]), Err(Error::Wire));
    assert!(p.tasks.iter().all(|task| task.factory == 0));
    p.bind(FACTORIES).unwrap();
    assert!(p.close_allowed());
    assert_eq!(p.bind(FACTORIES), Err(Error::Wire));
    assert!(p.calls.calls.is_empty());
}
#[derive(Default)]
struct Fake {
    replies: VecDeque<(u64, u64)>,
    calls: Vec<(u64, u64, u64)>,
}
impl Calls for Fake {
    fn invoke(&mut self, n: u64, h: u64, a: u64) -> (u64, u64) {
        self.calls.push((n, h, a));
        self.replies.pop_front().expect("unexpected syscall")
    }
}
fn policy() -> Processes<Fake> {
    Processes::new(FACTORIES, Fake::default()).unwrap()
}
fn step(p: &mut Processes<Fake>, result: (u64, u64)) -> Result<bool, Error> {
    p.calls.replies.push_back(result);
    let before = p.calls.calls.len();
    let r = p.poll();
    assert_eq!(p.calls.calls.len(), before + 1);
    r
}
fn start(p: &mut Processes<Fake>) {
    assert_eq!(p.begin(b"start worker"), Ok(true));
    assert_eq!(step(p, (0, CHILD)), Ok(true));
    assert_eq!(p.response(), b"worker: admitted\r\n");
}
#[test]
fn names_tokens_and_factory_shapes_are_exact() {
    for f in [
        [0, FACTORIES[1]],
        [CHILD, FACTORIES[1]],
        [FACTORIES[0]; 2],
        [0x60001, FACTORIES[1]],
        [0x100060000, FACTORIES[1]],
    ] {
        assert!(Processes::new(f, Fake::default()).is_err());
    }
    let mut p = policy();
    for line in [
        &b"start"[..],
        b"start  worker",
        b"start worker ",
        b"start WORKER",
        b"stop 4",
        b"status worker\0",
        b"launch worker",
    ] {
        assert_eq!(p.begin(line), Ok(false));
    }
    assert!(p.calls.calls.is_empty());
}
#[test]
fn absent_tasks_need_no_kernel_calls_or_fabricated_handles() {
    let mut p = policy();
    for line in [b"status worker".as_slice(), b"stop worker"] {
        p.begin(line).unwrap();
        assert_eq!(p.poll(), Ok(true));
        assert_eq!(p.response(), b"worker: not started\r\n");
    }
    assert!(p.close_allowed() && p.calls.calls.is_empty());
}
#[test]
fn launch_backpressure_repeats_one_sequence_until_real_handle() {
    let mut p = policy();
    p.begin(b"start worker").unwrap();
    assert_eq!(p.begin(b"start fault"), Err(Error::Sequence));
    for _ in 0..5 {
        assert_eq!(step(&mut p, (6, 0)), Ok(false));
    }
    assert!(!p.close_allowed());
    assert_eq!(step(&mut p, (0, CHILD)), Ok(true));
    assert!(p.calls.calls.iter().all(|&c| c == (19, FACTORIES[0], 1)));
    assert!(!p.close_allowed());
}
#[test]
fn live_or_detached_child_cannot_be_superseded() {
    let mut p = policy();
    start(&mut p);
    for (state, label) in [
        (1, &b"attached"[..]),
        (2, b"stop pending"),
        (3, b"stop claimed"),
        (4, b"retiring"),
    ] {
        p.begin(b"start worker").unwrap();
        assert_eq!(step(&mut p, (6, state)), Ok(true));
        assert_eq!(p.calls.calls.last(), Some(&(20, CHILD, 0)));
        assert!(p.response().windows(label.len()).any(|w| w == label));
        assert_eq!(p.tasks[0].sequence, 1);
    }
}
#[test]
fn stop_request_never_claims_retirement_or_allows_close() {
    let mut p = policy();
    start(&mut p);
    p.begin(b"stop worker").unwrap();
    assert_eq!(step(&mut p, (6, 0)), Ok(true));
    assert_eq!(p.response(), b"worker: stop requested\r\n");
    assert_eq!(p.calls.calls.last(), Some(&(18, CHILD, 0)));
    assert!(!p.close_allowed());
    p.begin(b"status worker").unwrap();
    assert_eq!(step(&mut p, (0, 4 << 32)), Ok(true));
    assert_eq!(p.response(), b"worker: cancelled\r\n");
    assert!(p.close_allowed());
}
#[test]
fn revoked_stop_polls_completion_instead_of_inventing_exit() {
    let mut p = policy();
    start(&mut p);
    p.begin(b"stop worker").unwrap();
    assert_eq!(step(&mut p, (9, 0)), Ok(false));
    assert!(!p.close_allowed());
    assert_eq!(step(&mut p, (0, (1 << 32) | 0xdeadbeef)), Ok(true));
    assert_eq!(p.response(), b"worker: exit 0xDEADBEEF\r\n");
    assert_eq!(p.calls.calls.last(), Some(&(20, CHILD, 0)));
}
#[test]
fn restart_waits_for_terminal_result_then_advances_once() {
    let mut p = policy();
    start(&mut p);
    p.begin(b"start worker").unwrap();
    assert_eq!(step(&mut p, (0, 4 << 32)), Ok(false));
    for _ in 0..3 {
        assert_eq!(step(&mut p, (6, 0)), Ok(false));
    }
    assert_eq!(step(&mut p, (0, CHILD + (1 << 32))), Ok(true));
    assert!(
        p.calls.calls[2..]
            .iter()
            .all(|&c| c == (19, FACTORIES[0], 2))
    );
    assert!(!p.close_allowed());
}
#[test]
fn independent_factories_do_not_share_process_identity() {
    let mut p = policy();
    start(&mut p);
    p.begin(b"start fault").unwrap();
    assert_eq!(step(&mut p, (0, CHILD)), Err(Error::Transport));
    assert_eq!(p.tasks[1].handle, None);
    assert_eq!(step(&mut p, (0, CHILD + 1)), Ok(true));
    p.begin(b"status fault").unwrap();
    assert_eq!(step(&mut p, (0, (2 << 32) | 6)), Ok(true));
    assert_eq!(p.response(), b"fault: fault 0x00000006\r\n");
    assert!(!p.close_allowed());
    p.begin(b"status worker").unwrap();
    assert_eq!(step(&mut p, (6, 1)), Ok(true));
    assert_eq!(p.response(), b"worker: attached\r\n");
}
#[test]
fn denied_or_failed_launch_does_not_create_a_process() {
    let mut p = policy();
    p.begin(b"start worker").unwrap();
    assert_eq!(step(&mut p, (5, 0)), Ok(true));
    assert_eq!(p.tasks[0].sequence, 0);
    assert_eq!(p.response(), b"worker: denied\r\n");
    assert!(p.close_allowed());
    p.begin(b"start worker").unwrap();
    assert_eq!(step(&mut p, (8, 0)), Ok(true));
    assert_eq!(p.tasks[0].sequence, 1);
    assert!(p.close_allowed());
    p.begin(b"start worker").unwrap();
    assert_eq!(step(&mut p, (0, CHILD)), Ok(true));
    assert_eq!(p.calls.calls.last(), Some(&(19, FACTORIES[0], 2)));
}
#[test]
fn failed_restart_discards_only_the_retired_superseded_handle() {
    let mut p = policy();
    start(&mut p);
    p.begin(b"start worker").unwrap();
    assert_eq!(step(&mut p, (0, 4 << 32)), Ok(false));
    assert_eq!(step(&mut p, (8, 0)), Ok(true));
    assert!(p.close_allowed());
    assert_eq!(p.tasks[0].handle, None);
    p.begin(b"start worker").unwrap();
    assert_eq!(step(&mut p, (0, CHILD + (1 << 32))), Ok(true));
    assert_eq!(p.calls.calls.last(), Some(&(19, FACTORIES[0], 3)));
}
#[test]
fn malformed_results_never_advance_lifetime_or_admit_authority() {
    for result in [
        (0, 0),
        (0, FACTORIES[0]),
        (5, 1),
        (6, 1),
        (8, 1),
        (u64::MAX, 0),
    ] {
        let mut p = policy();
        p.begin(b"start worker").unwrap();
        assert_eq!(step(&mut p, result), Err(Error::Transport));
        assert_eq!(p.tasks[0].sequence, 0);
        assert_eq!(p.tasks[0].handle, None);
    }
    for result in [(0, 0), (0, 8 << 32), (6, 0), (6, 5), (9, 0), (5, 1)] {
        let mut p = policy();
        start(&mut p);
        p.begin(b"status worker").unwrap();
        assert_eq!(step(&mut p, result), Err(Error::Transport));
        assert!(!p.close_allowed());
    }
}
#[test]
fn completed_generation_cannot_regress_and_sequence_cannot_wrap() {
    let mut p = policy();
    start(&mut p);
    p.begin(b"status worker").unwrap();
    assert_eq!(step(&mut p, (0, 4 << 32)), Ok(true));
    p.begin(b"status worker").unwrap();
    assert_eq!(step(&mut p, (6, 1)), Err(Error::Transport));
    let mut p = policy();
    p.tasks[0].sequence = u32::MAX;
    p.begin(b"start worker").unwrap();
    assert_eq!(p.poll(), Err(Error::Sequence));
    assert!(p.calls.calls.is_empty());
}
