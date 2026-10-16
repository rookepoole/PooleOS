use super::tests::{caller, grant, id, image, space};
use super::*;
use crate::{
    scheduler::{CpuId, Scheduler},
    user_entry::{
        syscall::{Request, request},
        task::{Fault, Outcome, Reason},
    },
};

fn outcome(reason: Reason) -> Outcome {
    Outcome {
        id: id(1),
        root: image(1).root_physical,
        reason,
        syscalls: 1,
    }
}
fn scheduler() -> Scheduler {
    let mut q = Scheduler::new(1).unwrap();
    let task = q.create_task(1, 1, 16, 1).unwrap();
    q.activate(task, CpuId::new(0).unwrap()).unwrap();
    q
}
fn retired() -> Scheduler {
    let mut q = scheduler();
    q.teardown(crate::scheduler::TaskId::new(1, 1).unwrap())
        .unwrap();
    q
}

#[test]
fn completion_abi_is_read_only_and_rejects_extra_arguments() {
    assert_eq!(
        request(20, 1, 123, 0, 0, 0, 0),
        Ok(Request::ProcessCompletion(123))
    );
    for a in [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]] {
        assert_eq!(
            request(20, 1, 123, a[0], a[1], a[2], a[3]),
            Err(Status::Arguments)
        );
    }
    assert_eq!(request(20, 2, 123, 0, 0, 0, 0), Err(Status::Version));
}

#[test]
fn detached_is_not_complete_and_publication_requires_scheduler_teardown() {
    let mut s = space();
    let h = grant(&mut s);
    let out = outcome(Reason::Exit(100));
    assert_eq!(s.process_completion(caller(0), h), (Status::Again, 1));
    assert_eq!(
        s.publish_process_completion(out, &retired()),
        Err(Error::Identity)
    );
    s.process_operation(caller(0), h, true);
    assert_eq!(s.process_completion(caller(0), h), (Status::Again, 2));
    let _permit = s.claim_process_stop().unwrap();
    assert_eq!(s.process_completion(caller(0), h), (Status::Again, 3));
    s.detach(id(1)).unwrap();
    for _ in 0..10 {
        assert_eq!(s.process_completion(caller(0), h), (Status::Again, 4));
    }
    for q in [scheduler(), Scheduler::new(1).unwrap()] {
        assert_eq!(s.publish_process_completion(out, &q), Err(Error::Denied));
        assert_eq!(s.process_completion(caller(0), h), (Status::Again, 4));
    }
    assert_eq!(s.publish_process_completion(out, &retired()), Ok(1));
    for _ in 0..10 {
        assert_eq!(
            s.process_completion(caller(0), h),
            (Status::Ok, (1 << 32) | 100)
        );
        assert_eq!(
            s.process_operation(caller(0), h, false),
            (Status::Revoked, 0)
        );
    }
    assert_eq!(
        s.publish_process_completion(out, &retired()),
        Err(Error::Denied)
    );
    assert_eq!(
        s.publish_process_completion(outcome(Reason::Cancelled), &retired()),
        Err(Error::Denied)
    );
}

#[test]
fn completion_enforces_owner_root_identity_type_and_generation() {
    let mut s = space();
    let h = grant(&mut s);
    for c in [
        caller(1),
        caller(2),
        Caller {
            root: 0,
            ..caller(0)
        },
        Caller {
            generation: 2,
            ..caller(0)
        },
        Caller {
            id: TaskId::new(0, 2).unwrap(),
            ..caller(0)
        },
    ] {
        assert_eq!(s.process_completion(c, h), (Status::Denied, 0));
    }
    for bad in [
        0,
        1,
        u64::MAX,
        h ^ (1 << 32),
        h ^ (1 << 16),
        h & !0xffff,
        h + LEASES as u64,
    ] {
        assert_eq!(s.process_completion(caller(0), bad), (Status::Denied, 0));
    }
    s.detach(id(1)).unwrap();
    s.publish_process_completion(outcome(Reason::Exit(0)), &retired())
        .unwrap();
    s.revoke_process(id(0), h).unwrap();
    assert_eq!(s.process_completion(caller(0), h), (Status::Denied, 0));
    s.attach(TaskId::new(1, 2).unwrap(), image(1)).unwrap();
    let fresh = s
        .grant_process(id(0), TaskId::new(1, 2).unwrap(), Rights::Inspect)
        .unwrap();
    assert_ne!(fresh, h);
    assert_eq!(s.process_completion(caller(0), fresh), (Status::Again, 1));
    assert!(
        s.publish_process_completion(outcome(Reason::Exit(0)), &retired())
            .is_err()
    );
    s.detach(id(0)).unwrap();
    s.attach(TaskId::new(0, 2).unwrap(), image(0)).unwrap();
    assert_eq!(s.process_completion(caller(0), fresh), (Status::Denied, 0));
    assert!(s.processes.iter().all(|p| p.value.is_none()));
}

#[test]
fn terminal_reasons_are_bounded_and_never_disclose_fault_addresses() {
    use crate::user_entry::syscall::ReturnViolation;
    for (reason, calls, value) in [
        (Reason::Exit(u32::MAX), 1, (1 << 32) | u64::from(u32::MAX)),
        (
            Reason::Fault(Fault {
                vector: 14,
                error: 4,
                instruction: 0x40000010,
                address: 0x12345,
            }),
            0,
            (2 << 32) | 14,
        ),
        (
            Reason::InvalidReturn {
                vector: 256,
                violation: ReturnViolation::Flags,
            },
            1,
            (3 << 32) | 3,
        ),
        (Reason::Cancelled, 0, 4 << 32),
        (Reason::CallLimit, 64, 5 << 32),
        (Reason::CallCounterExhausted, u64::MAX, 6 << 32),
        (Reason::Watchdog, 0, 7 << 32),
    ] {
        let mut s = space();
        let h = grant(&mut s);
        let inspect = s.grant_process(id(2), id(1), Rights::Inspect).unwrap();
        s.detach(id(1)).unwrap();
        assert_eq!(
            s.publish_process_completion(
                Outcome {
                    syscalls: calls,
                    ..outcome(reason)
                },
                &retired()
            ),
            Ok(2)
        );
        for (c, handle) in [(caller(0), h), (caller(2), inspect)] {
            assert_eq!(s.process_completion(c, handle), (Status::Ok, value));
        }
    }
}

#[test]
fn invalid_outcomes_and_conflicting_inspector_fail_before_any_publication() {
    let mut s = space();
    let h = grant(&mut s);
    let inspect = s.grant_process(id(2), id(1), Rights::Inspect).unwrap();
    s.detach(id(1)).unwrap();
    let out = outcome(Reason::Exit(100));
    for bad in [
        Outcome { root: 0, ..out },
        Outcome {
            root: out.root + 1,
            ..out
        },
        Outcome {
            root: out.root + 4096,
            ..out
        },
        Outcome { syscalls: 0, ..out },
        outcome(Reason::CallLimit),
        outcome(Reason::CallCounterExhausted),
        outcome(Reason::Fault(Fault {
            vector: 2,
            error: 0,
            instruction: 0,
            address: 0,
        })),
        outcome(Reason::InvalidReturn {
            vector: 65,
            violation: crate::user_entry::syscall::ReturnViolation::Stack,
        }),
    ] {
        assert!(s.publish_process_completion(bad, &retired()).is_err());
        assert_eq!(s.process_completion(caller(0), h), (Status::Again, 4));
        assert_eq!(s.process_completion(caller(2), inspect), (Status::Again, 4));
    }
    s.processes[1].value.as_mut().unwrap().target.root += 4096;
    let before = s.processes;
    assert_eq!(
        s.publish_process_completion(out, &retired()),
        Err(Error::Denied)
    );
    assert_eq!(s.processes, before);
}
