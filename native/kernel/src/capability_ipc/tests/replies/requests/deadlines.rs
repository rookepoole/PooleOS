use super::*;
use crate::user_entry::timer::{Error as ClockError, watchdog::Hardware};
use core::cell::Cell;

struct Hpet {
    raw: Cell<u64>,
    config: u64,
    fail: Cell<bool>,
}
impl Hpet {
    fn new() -> Self {
        Self {
            raw: Cell::new(0),
            config: 0,
            fail: Cell::new(false),
        }
    }
}
impl Hardware for Hpet {
    fn read(&self, offset: u64) -> Result<u64, ClockError> {
        if self.fail.get() {
            return Err(ClockError::Hardware);
        }
        Ok(match offset {
            0 => (1_000_000u64 << 32) | (1 << 13) | 1,
            0x10 => self.config,
            0xf0 => self.raw.get(),
            _ => 0,
        })
    }
    fn write(&mut self, offset: u64, value: u64) -> Result<(), ClockError> {
        assert_eq!(offset, 0x10);
        self.config = value;
        if self.fail.get() {
            Err(ClockError::Hardware)
        } else {
            Ok(())
        }
    }
}
fn clock(s: &mut Space, h: &mut Hpet) {
    s.prepare_clock(h).unwrap();
    s.start_clock(h).unwrap();
    assert_eq!(s.sample_clock(h), Ok(0));
}
fn timed(s: &mut Space, send: u64, m: &mut Wire, ns: u64) -> (Status, u64) {
    s.request_operation(
        caller(0),
        send,
        BASE,
        MAX_BYTES,
        Control::BeginTimed { timeout_ns: ns },
        m,
    )
}

#[test]
fn timed_begin_requires_healthy_owned_epoch_and_checked_relative_bounds() {
    let (mut s, _, _, send, mut m) = setup();
    assert_eq!(
        timed(&mut s, send, &mut m, 10),
        (Status::ClockUnavailable, 0)
    );
    let mut h = Hpet::new();
    s.prepare_clock(&h).unwrap();
    assert_eq!(
        timed(&mut s, send, &mut m, 10),
        (Status::ClockUnavailable, 0)
    );
    s.start_clock(&mut h).unwrap();
    assert_eq!(
        timed(&mut s, send, &mut m, 10),
        (Status::ClockUnavailable, 0)
    );
    s.sample_clock(&h).unwrap();
    for ns in [
        0,
        crate::capability_ipc::deadline::MAX_TIMEOUT_NS + 1,
        u64::MAX,
    ] {
        assert_eq!(timed(&mut s, send, &mut m, ns), (Status::Arguments, 0));
    }
    h.raw.set(u64::MAX - 5);
    s.sample_clock(&h).unwrap();
    assert_eq!(timed(&mut s, send, &mut m, 6), (Status::Arguments, 0));
    assert_eq!(m.accesses, 0);
    assert_eq!(timed(&mut s, send, &mut m, 5).0, Status::Ok);
}

#[test]
fn exact_deadline_expires_queued_or_claimed_request_and_late_authority_is_dead() {
    for claimed in [false, true] {
        let (mut s, _, endpoint, send, mut m) = setup();
        let mut h = Hpet::new();
        clock(&mut s, &mut h);
        let (status, handle) = timed(&mut s, send, &mut m, 10);
        assert_eq!(status, Status::Ok);
        let token = if claimed {
            receive(&mut s, endpoint, &mut m)
        } else {
            0
        };
        h.raw.set(9);
        s.sample_clock(&h).unwrap();
        assert_eq!(take(&mut s, handle, &mut m).0, Status::Again);
        assert_eq!(s.release_clock(&mut h), Err(ClockError::State));
        h.raw.set(10);
        s.sample_clock(&h).unwrap();
        assert_eq!(
            s.prepare_request_wait(caller(0), handle),
            Ok(Admission::Complete(Status::TimedOut))
        );
        assert_eq!(
            s.request_operation(caller(0), handle, 0, 0, Control::Cancel, &mut m)
                .0,
            Status::Denied
        );
        if claimed {
            assert_eq!(
                s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m)
                    .0,
                Status::Denied
            );
        } else {
            assert_eq!(receive(&mut s, endpoint, &mut m), 0);
        }
        h.raw.set(11);
        s.sample_clock(&h).unwrap();
        assert_eq!(s.clock_observation().unwrap().0.expired, 1);
        assert_eq!(take(&mut s, handle, &mut m), (Status::TimedOut, 0));
        assert_eq!(take(&mut s, handle, &mut m), (Status::Denied, 0));
        s.release_clock(&mut h).unwrap();
        assert_eq!(h.config, 0);
    }
}

#[test]
fn earlier_reply_cancel_discard_or_revocation_survives_expiry_and_clock_failure() {
    for cause in 0..4 {
        let (mut s, _, endpoint, send, mut m) = setup();
        let mut h = Hpet::new();
        clock(&mut s, &mut h);
        let (_, handle) = timed(&mut s, send, &mut m, 10);
        let token = receive(&mut s, endpoint, &mut m);
        let expected = match cause {
            0 => {
                assert_eq!(
                    s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m)
                        .0,
                    Status::Ok
                );
                Status::Ok
            }
            1 => {
                s.request_operation(caller(0), handle, 0, 0, Control::Cancel, &mut m);
                Status::Cancelled
            }
            2 => {
                s.message(caller(1), token, 0, 0, Operation::Discard, &mut m);
                Status::Cancelled
            }
            _ => {
                s.detach(id(1)).unwrap();
                Status::Revoked
            }
        };
        h.raw.set(10);
        s.sample_clock(&h).unwrap();
        h.fail.set(true);
        assert!(s.sample_clock(&h).is_err());
        assert_eq!(take(&mut s, handle, &mut m).0, expected);
        assert_eq!(s.clock_observation().unwrap().0.expired, 0);
    }
}

#[test]
fn clock_uncertainty_poison_is_sticky_and_restart_does_not_revive_old_requests() {
    for fault in 0..3 {
        let (mut s, _, endpoint, send, mut m) = setup();
        let mut h = Hpet::new();
        clock(&mut s, &mut h);
        h.raw.set(5);
        s.sample_clock(&h).unwrap();
        let (_, old) = timed(&mut s, send, &mut m, 10);
        let token = receive(&mut s, endpoint, &mut m);
        match fault {
            0 => h.fail.set(true),
            1 => h.raw.set(4),
            _ => h.config = 0,
        }
        assert!(s.sample_clock(&h).is_err());
        h.fail.set(false);
        h.raw.set(6);
        h.config = 1;
        assert!(s.sample_clock(&h).is_err());
        assert!(s.clock_observation().unwrap().0.failed);
        assert_eq!(timed(&mut s, send, &mut m, 10).0, Status::ClockUnavailable);
        assert_eq!(
            s.message(caller(1), token, BASE, 8, Operation::Reply, &mut m)
                .0,
            Status::Denied
        );
        assert!(s.prepare_clock(&h).is_err());
        s.release_clock(&mut h).unwrap();
        clock(&mut s, &mut h);
        assert_eq!(s.clock_observation().unwrap().0.epoch, 2);
        assert_eq!(take(&mut s, old, &mut m).0, Status::ClockUnavailable);
        let (_, new) = timed(&mut s, send, &mut m, 10);
        assert_ne!(new, old);
        h.raw.set(16);
        s.sample_clock(&h).unwrap();
        assert_eq!(take(&mut s, new, &mut m).0, Status::TimedOut);
    }
}

#[test]
fn expiry_between_arm_and_park_wakes_once_and_failed_resume_retains_both_owners() {
    for poison in [false, true] {
        let (mut s, _, _, send, mut m) = setup();
        let mut h = Hpet::new();
        clock(&mut s, &mut h);
        let (_, handle) = timed(&mut s, send, &mut m, 10);
        let Admission::Pending(ticket) = s.prepare_request_wait(caller(0), handle).unwrap() else {
            panic!()
        };
        h.raw.set(10);
        h.fail.set(poison);
        assert_eq!(s.sample_clock(&h).is_err(), poison);
        let expected = if poison {
            Status::ClockUnavailable
        } else {
            Status::TimedOut
        };
        let (mut scheduler, cpu) = running(0);
        charge(&mut scheduler, cpu, 0);
        s.park_wait(ticket, &mut scheduler, cpu).unwrap();
        assert_eq!(scheduler.summary().runnable_count, 0);
        assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(1));
        assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
        scheduler.dispatch(cpu).unwrap();
        let scheduled = crate::scheduler::TaskId::new(0, 1).unwrap();
        let before = (
            scheduler.summary(),
            scheduler.task_snapshot(scheduled).unwrap(),
        );
        assert!(
            s.complete_wait(ticket, &mut scheduler, cpu, |_| Err(Error::Denied))
                .is_err()
        );
        assert_eq!(
            (
                scheduler.summary(),
                scheduler.task_snapshot(scheduled).unwrap()
            ),
            before
        );
        assert_eq!(
            s.complete_wait(ticket, &mut scheduler, cpu, |status| {
                assert_eq!(status, expected);
                Ok(())
            }),
            Ok(expected)
        );
        assert!(
            s.complete_wait(ticket, &mut scheduler, cpu, |_| panic!())
                .is_err()
        );
        assert_eq!(take(&mut s, handle, &mut m).0, expected);
    }
}

#[test]
fn expired_records_keep_quota_until_taken_and_clock_generation_never_wraps() {
    let (mut s, _, endpoint, send, mut m) = setup();
    let mut h = Hpet::new();
    clock(&mut s, &mut h);
    let mut handles = [0; CAPS];
    for handle in &mut handles {
        *handle = timed(&mut s, send, &mut m, 10).1;
        receive(&mut s, endpoint, &mut m);
    }
    h.raw.set(10);
    s.sample_clock(&h).unwrap();
    assert_eq!(s.clock_observation().unwrap().0.expired, CAPS as u64);
    assert_eq!(timed(&mut s, send, &mut m, 10).0, Status::Again);
    s.release_clock(&mut h).unwrap();
    s.clock.generation = u64::MAX;
    assert_eq!(s.prepare_clock(&h), Err(ClockError::State));
    for handle in handles {
        assert_eq!(take(&mut s, handle, &mut m).0, Status::TimedOut);
    }
}

#[test]
fn timed_copy_faults_have_no_admission_and_reply_fault_does_not_prevent_expiry() {
    for offset in 0..MAX_BYTES {
        let (mut s, _, endpoint, send, mut m) = setup();
        let mut h = Hpet::new();
        clock(&mut s, &mut h);
        let before = (s.tables, s.objects);
        m.read_fault = Some(offset);
        assert_eq!(timed(&mut s, send, &mut m, 10).0, Status::Fault);
        assert_eq!((s.tables, s.objects), before);
        m.read_fault = None;
        let (_, handle) = timed(&mut s, send, &mut m, 10);
        let token = receive(&mut s, endpoint, &mut m);
        m.read_fault = Some(offset);
        assert_eq!(
            s.message(caller(1), token, BASE, MAX_BYTES, Operation::Reply, &mut m)
                .0,
            Status::Fault
        );
        h.raw.set(10);
        s.sample_clock(&h).unwrap();
        assert_eq!(take(&mut s, handle, &mut m).0, Status::TimedOut);
    }
}

#[test]
fn timed_syscall_accepts_only_positive_bounded_relative_ns_and_reserved_zero() {
    use crate::user_entry::syscall::{Request, request as parse};
    for ns in [
        1,
        100_000_000,
        crate::capability_ipc::deadline::MAX_TIMEOUT_NS,
    ] {
        assert_eq!(
            parse(14, 1, 123, BASE, 8, ns, 0),
            Ok(Request::RequestControl {
                handle: 123,
                address: BASE,
                bytes: 8,
                operation: Control::BeginTimed { timeout_ns: ns },
            })
        );
        assert_eq!(parse(14, 1, 123, BASE, 8, ns, 1), Err(Status::Arguments));
        assert_eq!(parse(14, 2, 123, BASE, 8, ns, 0), Err(Status::Version));
    }
    for ns in [
        0,
        crate::capability_ipc::deadline::MAX_TIMEOUT_NS + 1,
        u64::MAX,
    ] {
        assert_eq!(parse(14, 1, 123, BASE, 8, ns, 0), Err(Status::Arguments));
    }
    for (address, bytes) in [(0, 8), (BASE, 0), (BASE, 65), (u64::MAX - 3, 8)] {
        assert_eq!(
            parse(14, 1, 123, address, bytes, 10, 0),
            Err(Status::Arguments)
        );
    }
}

#[test]
fn failed_release_and_expiry_counter_overflow_cannot_readmit_timed_work() {
    let (mut s, _, _, send, mut m) = setup();
    let mut h = Hpet::new();
    clock(&mut s, &mut h);
    h.fail.set(true);
    assert!(s.release_clock(&mut h).is_err());
    h.fail.set(false);
    assert_eq!(timed(&mut s, send, &mut m, 10).0, Status::ClockUnavailable);
    assert!(s.sample_clock(&h).is_err());
    s.release_clock(&mut h).unwrap();
    clock(&mut s, &mut h);
    let (_, first) = timed(&mut s, send, &mut m, 1);
    let (_, second) = timed(&mut s, send, &mut m, 2);
    s.clock.expired = u64::MAX;
    h.raw.set(1);
    assert_eq!(s.sample_clock(&h), Err(ClockError::State));
    assert_eq!(take(&mut s, first, &mut m).0, Status::TimedOut);
    assert_eq!(take(&mut s, second, &mut m).0, Status::ClockUnavailable);
    assert_eq!(timed(&mut s, send, &mut m, 10).0, Status::ClockUnavailable);
    assert!(s.sample_clock(&h).is_err());
    s.release_clock(&mut h).unwrap();
}
