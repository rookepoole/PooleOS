use super::tests::image;
use super::*;
use crate::capability_ipc::{
    admission::{Member, Step},
    launch::Permit,
};
use crate::scheduler::Scheduler;
#[cfg(feature = "development-window-lifecycle")]
use crate::user_entry::syscall::Request;
use crate::user_entry::syscall::request;
use crate::user_entry::task::{Outcome, Reason};

fn id(slot: u8, generation: u32) -> TaskId {
    TaskId::new(slot, generation).unwrap()
}
fn member(slot: u8, generation: u32) -> Member {
    Member {
        id: id(slot, generation),
        image: image(slot),
        priority: 16,
    }
}
fn fixture() -> (Space, Scheduler, Caller, u64) {
    let mut s = Space::new();
    let mut q = Scheduler::new(1).unwrap();
    s.admit(&mut q, &[member(0, 1), member(2, 1), member(3, 1)], &[])
        .unwrap();
    let h = s.grant_launch(id(0, 1), 7, 1).unwrap();
    (s, q, Caller::new(id(0, 1), image(0)), h)
}
fn claim(s: &mut Space, c: Caller, h: u64, generation: u32) -> Permit {
    assert_eq!(s.request_launch(c, h, generation), (Status::Again, 0));
    s.claim_launch().unwrap()
}
fn unchanged_scheduler(mut a: Scheduler, mut b: Scheduler) {
    assert_eq!(a.summary(), b.summary());
    let cpu = crate::scheduler::CpuId::new(0).unwrap();
    assert_eq!(a.current(cpu), b.current(cpu));
    for slot in 0..TASKS as u8 {
        for generation in 1..=2 {
            let id = crate::scheduler::TaskId::new(slot, generation).unwrap();
            assert_eq!(a.task_snapshot(id), b.task_snapshot(id));
        }
    }
    for _ in 0..TASKS * 2 {
        assert_eq!(a.dispatch(cpu), b.dispatch(cpu));
        assert_eq!(a.yield_current(cpu), b.yield_current(cpu));
    }
    a.validate().unwrap();
    b.validate().unwrap();
}

fn observer() -> Caller {
    Caller::new(id(2, 1), image(2))
}
fn finish(s: &mut Space, q: &mut Scheduler, slot: u8, generation: u32) {
    s.detach(id(slot, generation)).unwrap();
    q.teardown(crate::scheduler::TaskId::new(slot, generation).unwrap())
        .unwrap();
    assert_eq!(
        s.observe_process(observer(), id(slot, generation)),
        (Status::Again, 4)
    );
    assert_eq!(
        s.publish_process_completion(
            Outcome {
                id: id(slot, generation),
                root: image(slot).root_physical,
                reason: Reason::Cancelled,
                syscalls: 1,
            },
            q
        ),
        Ok(2)
    );
}

#[test]
fn observer_is_read_only_generation_bound_and_never_granted_by_task_identity() {
    let (mut s, mut q, c, factory) = fixture();
    let permit = claim(&mut s, c, factory, 1);
    let a = s
        .admit_observed_launch(&permit, &mut q, member(1, 1), &[], observer().id)
        .unwrap();
    assert_eq!(a.count, 1);
    assert_eq!(
        s.process_operation(c, a.handles[0], true),
        (Status::Again, 0)
    );
    let before = s.processes;
    for wrong in [
        c,
        Caller::new(id(3, 1), image(3)),
        Caller {
            root: 0,
            ..observer()
        },
        Caller {
            generation: 2,
            ..observer()
        },
        Caller {
            id: id(2, 2),
            ..observer()
        },
    ] {
        assert_eq!(s.observe_process(wrong, id(1, 1)), (Status::Denied, 0));
    }
    assert_eq!(s.observe_process(observer(), id(1, 2)), (Status::Denied, 0));
    assert_eq!(s.observe_process(observer(), id(3, 1)), (Status::Denied, 0));
    assert_eq!(s.observe_process(observer(), id(1, 1)), (Status::Again, 1));
    for i in 0..process::LEASES {
        let h = (u64::from(s.processes[i].generation) << 32) | (5 << 16) | (i + 1) as u64;
        assert_eq!(
            s.process_operation(observer(), h, true),
            (Status::Denied, 0)
        );
    }
    assert_eq!(s.processes, before);
    finish(&mut s, &mut q, 1, 1);
    assert_eq!(
        s.observe_process(observer(), id(1, 1)),
        (Status::Ok, 4 << 32)
    );
}

#[test]
fn two_app_restarts_reuse_four_leases_without_stale_observer_or_completion() {
    let (mut s, mut q, c, a) = fixture();
    let b = s.grant_launch(c.id, 8, 4).unwrap();
    for generation in 1..=12 {
        for (slot, factory) in [(1, a), (4, b)] {
            let permit = claim(&mut s, c, factory, generation);
            s.admit_observed_launch(
                &permit,
                &mut q,
                member(slot, generation),
                &[],
                observer().id,
            )
            .unwrap();
            assert_eq!(
                s.observe_process(observer(), id(slot, generation)),
                (Status::Again, 1)
            );
            if generation > 1 {
                assert_eq!(
                    s.observe_process(observer(), id(slot, generation - 1)),
                    (Status::Revoked, 0)
                );
                assert!(
                    s.publish_process_completion(
                        Outcome {
                            id: id(slot, generation - 1),
                            root: image(slot).root_physical,
                            reason: Reason::Cancelled,
                            syscalls: 1,
                        },
                        &q
                    )
                    .is_err()
                );
            }
        }
        assert_eq!(s.processes.iter().filter(|p| p.value.is_some()).count(), 4);
        finish(&mut s, &mut q, 1, generation);
        assert_eq!(
            s.observe_process(observer(), id(4, generation)),
            (Status::Again, 1)
        );
        finish(&mut s, &mut q, 4, generation);
    }
}

#[test]
fn failed_launch_retains_completed_observer_and_scheduler_without_new_authority() {
    let (mut s, mut q, c, h) = fixture();
    let first = claim(&mut s, c, h, 1);
    s.admit_observed_launch(&first, &mut q, member(1, 1), &[], observer().id)
        .unwrap();
    finish(&mut s, &mut q, 1, 1);
    let next = claim(&mut s, c, h, 2);
    // Parent grant is last in admission; its quota failure rolls back new endpoints.
    s.grant_process(c.id, id(2, 1), process::Rights::Inspect)
        .unwrap();
    s.grant_process(c.id, id(3, 1), process::Rights::Inspect)
        .unwrap();
    let before = s.processes;
    let scheduler = q;
    assert!(
        s.admit_observed_launch(
            &next,
            &mut q,
            member(1, 2),
            &[Step::Endpoint { member: 0 }],
            observer().id
        )
        .is_err()
    );
    assert_eq!(s.processes, before);
    unchanged_scheduler(q, scheduler);
    assert!(s.table(id(1, 2)).is_err());
    assert!(s.objects.iter().all(|o| o.value.is_none()));
    assert_eq!(
        s.observe_process(observer(), id(1, 1)),
        (Status::Ok, 4 << 32)
    );
    assert_eq!(s.observe_process(observer(), id(1, 2)), (Status::Denied, 0));
}

#[test]
fn quota_relief_requires_explicit_failure_and_preserves_independent_generations() {
    let (mut s, mut q, c, factory) = fixture();
    let endpoint = s.create_endpoint(c.id).unwrap();
    let steps = [Step::Inherit {
        source: c.id,
        handle: endpoint,
        member: 0,
        rights: crate::capability_ipc::Rights::SEND,
    }; 3];
    let first = claim(&mut s, c, factory, 1);
    s.admit_observed_launch(&first, &mut q, member(1, 1), &steps, observer().id)
        .unwrap();
    finish(&mut s, &mut q, 1, 1);
    let rejected = claim(&mut s, c, factory, 2);
    let pressure = [
        s.grant_process(c.id, id(2, 1), process::Rights::Inspect)
            .unwrap(),
        s.grant_process(c.id, id(3, 1), process::Rights::Inspect)
            .unwrap(),
    ];
    let processes = s.processes;
    let scheduler = q;
    for handle in pressure {
        assert_eq!(s.process_operation(c, handle, false), (Status::Ok, 1));
        assert_eq!(s.process_operation(c, handle, true), (Status::Denied, 0));
    }
    assert_eq!(
        s.grant_process(c.id, id(2, 1), process::Rights::Inspect),
        Err(Error::Quota)
    );
    assert_eq!(
        s.admit_observed_launch(&rejected, &mut q, member(1, 2), &steps, observer().id),
        Err(admission::Error::Ipc(Error::Quota)),
    );
    assert_eq!(s.processes, processes);
    unchanged_scheduler(q, scheduler);
    assert!(s.table(id(1, 2)).is_err());
    assert!(s.tables[1].caps.iter().all(|slot| slot.value.is_none()));
    assert_eq!(
        s.observe_process(observer(), id(1, 1)),
        (Status::Ok, 4 << 32)
    );
    assert_eq!(s.observe_process(observer(), id(1, 2)), (Status::Denied, 0));
    for handle in pressure {
        s.revoke_process(c.id, handle).unwrap();
        assert_eq!(s.process_operation(c, handle, false), (Status::Denied, 0));
    }
    assert_eq!(s.request_launch(c, factory, 2), (Status::Again, 0));
    assert_eq!(s.request_launch(c, factory, 3), (Status::Again, 0));
    // The native owner separately proves image reclamation before this publication.
    s.fail_launch(&rejected).unwrap();
    assert_eq!(s.request_launch(c, factory, 2), (Status::Cancelled, 0));
    let retry = claim(&mut s, c, factory, 3);
    assert!(s.fail_launch(&rejected).is_err());
    let admitted = s
        .admit_observed_launch(&retry, &mut q, member(1, 3), &steps, observer().id)
        .unwrap();
    assert_eq!(admitted.count, 4);
    for (i, handle) in admitted.handles[..3].iter().enumerate() {
        assert_eq!(*handle, (3 << 32) | 0x10000 | (i + 1) as u64);
    }
    assert_eq!(admitted.handles[3], (3 << 32) | 0x50001);
    assert_eq!(s.observe_process(observer(), id(1, 3)), (Status::Again, 1));
    assert_eq!(
        s.observe_process(observer(), id(1, 2)),
        (Status::Revoked, 0)
    );
    assert_eq!(s.processes[1].generation, 2);
    for handle in pressure {
        assert_eq!(s.process_operation(c, handle, true), (Status::Denied, 0));
    }
}

#[test]
fn observer_preflight_rejects_missing_duplicate_unfinished_exhausted_and_extra_authority() {
    for case in 0..7 {
        let (mut s, mut q, c, h) = fixture();
        let first = claim(&mut s, c, h, 1);
        s.admit_observed_launch(&first, &mut q, member(1, 1), &[], observer().id)
            .unwrap();
        finish(&mut s, &mut q, 1, 1);
        let next = claim(&mut s, c, h, 2);
        let index = s
            .processes
            .iter()
            .position(|p| p.value.is_some_and(|l| l.owner == observer()))
            .unwrap();
        let owner = match case {
            0 => c.id,
            1 => id(1, 2),
            2 => id(7, 1),
            _ => observer().id,
        };
        if case == 3 {
            s.processes[index].value.as_mut().unwrap().completion = None;
        }
        if case == 4 {
            s.processes[index].generation = u32::MAX;
        }
        if case == 5 {
            let mut extra = s.processes[index];
            extra.generation = 1;
            s.processes[3] = extra;
        }
        let before = s.processes;
        let scheduler = q;
        let extra = [Step::Process {
            member: 0,
            owner: c.id,
            rights: process::Rights::InspectTerminate,
        }];
        assert!(
            s.admit_observed_launch(
                &next,
                &mut q,
                member(1, 2),
                if case == 6 { &extra } else { &[] },
                owner
            )
            .is_err(),
            "case {case}"
        );
        assert_eq!(s.processes, before);
        unchanged_scheduler(q, scheduler);
        assert!(s.table(id(1, 2)).is_err());
    }
}

#[test]
fn ambiguous_inspect_grants_and_observer_retirement_cannot_leak_state() {
    let (mut s, mut q, c, h) = fixture();
    let first = claim(&mut s, c, h, 1);
    s.admit_observed_launch(&first, &mut q, member(1, 1), &[], observer().id)
        .unwrap();
    let duplicate = s
        .grant_process(observer().id, id(1, 1), process::Rights::Inspect)
        .unwrap();
    assert_eq!(s.observe_process(observer(), id(1, 1)), (Status::Denied, 0));
    s.revoke_process(observer().id, duplicate).unwrap();
    s.detach(observer().id).unwrap();
    assert_eq!(s.observe_process(observer(), id(1, 1)), (Status::Denied, 0));
    assert_eq!(s.processes.iter().filter(|p| p.value.is_some()).count(), 1);
    let parent_handle = s.request_launch(c, h, 1).1;
    assert_eq!(
        s.process_operation(c, parent_handle, false),
        (Status::Ok, 1)
    );
    s.detach(id(1, 1)).unwrap();
    q.teardown(crate::scheduler::TaskId::new(1, 1).unwrap())
        .unwrap();
    assert_eq!(
        s.publish_process_completion(
            Outcome {
                id: id(1, 1),
                root: image(1).root_physical,
                reason: Reason::Cancelled,
                syscalls: 1,
            },
            &q
        ),
        Ok(1)
    );
    assert_eq!(
        s.process_completion(c, parent_handle),
        (Status::Ok, 4 << 32)
    );

    // An orphan still has exactly its live read-only observer, not a parent lease.
    let (mut s, mut q, c, h) = fixture();
    let first = claim(&mut s, c, h, 1);
    s.admit_observed_launch(&first, &mut q, member(1, 1), &[], observer().id)
        .unwrap();
    s.detach(c.id).unwrap();
    s.detach(id(1, 1)).unwrap();
    q.teardown(crate::scheduler::TaskId::new(1, 1).unwrap())
        .unwrap();
    assert_eq!(
        s.publish_process_completion(
            Outcome {
                id: id(1, 1),
                root: image(1).root_physical,
                reason: Reason::Cancelled,
                syscalls: 1,
            },
            &q
        ),
        Ok(1)
    );
    assert_eq!(
        s.observe_process(observer(), id(1, 1)),
        (Status::Ok, 4 << 32)
    );
}

#[cfg(feature = "development-window-lifecycle")]
#[test]
fn observation_syscall_validates_identity_shape_and_reserved_arguments() {
    assert_eq!(
        request(27, 1, 4, 1, 0, 0, 0),
        Ok(Request::ProcessObservation(id(4, 1)))
    );
    for (slot, generation) in [
        (8, 1),
        (256, 1),
        (4, 0),
        (4, 1u64 << 32),
        (u64::MAX, u64::MAX),
    ] {
        assert_eq!(
            request(27, 1, slot, generation, 0, 0, 0),
            Err(Status::Arguments)
        );
    }
    for tail in [[1, 0, 0], [0, 1, 0], [0, 0, 1]] {
        assert_eq!(
            request(27, 1, 4, 1, tail[0], tail[1], tail[2]),
            Err(Status::Arguments)
        );
    }
    assert_eq!(request(27, 2, 4, 1, 0, 0, 0), Err(Status::Version));
}

#[cfg(not(feature = "development-window-lifecycle"))]
#[test]
fn ordinary_syscall_profile_does_not_opt_into_observation() {
    assert_eq!(request(27, 1, 4, 1, 0, 0, 0), Err(Status::Unknown));
}
