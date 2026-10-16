use super::*;
fn unchanged_scheduler(mut actual: Scheduler, mut before: Scheduler) {
    assert_eq!(actual.summary(), before.summary());
    let cpu = crate::scheduler::CpuId::new(0).unwrap();
    assert_eq!(actual.current(cpu), before.current(cpu));
    for slot in 0..TASKS as u8 {
        for generation in [1, 2] {
            let id = crate::scheduler::TaskId::new(slot, generation).unwrap();
            assert_eq!(actual.task_snapshot(id), before.task_snapshot(id));
        }
    }
    for _ in 0..TASKS * 2 {
        assert_eq!(actual.dispatch(cpu), before.dispatch(cpu));
        assert_eq!(actual.yield_current(cpu), before.yield_current(cpu));
    }
    actual.validate().unwrap();
    before.validate().unwrap();
}
use crate::user_entry::{
    InitialReturnFrame,
    syscall::{Request, request},
};

fn id(slot: u8, generation: u32) -> TaskId {
    TaskId::new(slot, generation).unwrap()
}
fn image(slot: u8) -> ImageAdmission {
    ImageAdmission {
        root_physical: 0x100000 + u64::from(slot) * 4096,
        root_generation: 1,
        code_physical: 0x200000,
        code_end: 0x40001000,
        stack_physical: 0x210000,
        initial_frame: InitialReturnFrame {
            rip: 0x40000010,
            rsp: 0x40004000,
            cs: 0x33,
            ss: 0x2b,
            rflags: 0x202,
        },
    }
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
fn claim(s: &mut Space, c: Caller, h: u64, n: u32) -> Permit {
    assert_eq!(s.request_launch(c, h, n), (Status::Again, 0));
    s.claim_launch().unwrap()
}

fn application_steps(s: &mut Space, owner: TaskId) -> [Step; 2] {
    let control = s.create_endpoint(owner).unwrap();
    let files = s.create_endpoint(id(2, 1)).unwrap();
    [
        Step::Inherit {
            source: owner,
            handle: control,
            member: 0,
            rights: Rights::SEND,
        },
        Step::Inherit {
            source: id(2, 1),
            handle: files,
            member: 0,
            rights: Rights::SEND,
        },
    ]
}

#[test]
fn application_launch_attenuates_both_endpoints_and_never_grants_ownership() {
    let (mut s, mut q, c, factory) = fixture();
    let steps = application_steps(&mut s, c.id);
    let permit = claim(&mut s, c, factory, 1);
    let admitted = s
        .admit_launch(&permit, &mut q, member(1, 1), &steps)
        .unwrap();
    assert_eq!(admitted.count, 3);
    for handle in &admitted.handles[..2] {
        assert!(s.resolve(1, *handle, Rights::SEND).is_ok());
        for denied in [Rights::RECEIVE, Rights::GRANT, Rights::DESTROY, Rights::ALL] {
            assert_eq!(s.resolve(1, *handle, denied), Err(Error::Denied));
        }
        assert_eq!(
            s.derive(id(1, 1), *handle, c.id, Rights::SEND),
            Err(Error::Denied)
        );
        assert_eq!(s.destroy(id(1, 1), *handle), Err(Error::Denied));
    }
    assert_eq!(
        s.tables[1]
            .caps
            .iter()
            .filter(|cap| cap.value.is_some())
            .count(),
        2
    );
    assert_eq!(
        s.objects
            .iter()
            .filter(|object| object.value.is_some())
            .count(),
        2
    );
    assert!(s.objects.iter().all(|object| {
        !object
            .value
            .is_some_and(|endpoint| endpoint.owner == id(1, 1))
    }));
    assert_eq!(
        s.request_launch(c, factory, 1),
        (Status::Ok, admitted.handles[2])
    );
    assert_eq!(
        s.process_operation(c, admitted.handles[2], false),
        (Status::Ok, 1)
    );
}

#[test]
fn application_restart_uses_actual_new_handles_and_rejects_both_old_grants() {
    let (mut s, mut q, c, factory) = fixture();
    let steps = application_steps(&mut s, c.id);
    let mut old = [0; 2];
    for generation in 1..=3 {
        let permit = claim(&mut s, c, factory, generation);
        let admitted = s
            .admit_launch(&permit, &mut q, member(1, generation), &steps)
            .unwrap();
        for index in 0..2 {
            assert_ne!(admitted.handles[index], old[index]);
            assert_eq!(admitted.handles[index] >> 32, u64::from(generation));
            assert!(s.resolve(1, admitted.handles[index], Rights::SEND).is_ok());
            assert_eq!(s.resolve(1, old[index], Rights::SEND), Err(Error::Denied));
        }
        old.copy_from_slice(&admitted.handles[..2]);
        s.detach(id(1, generation)).unwrap();
        q.teardown(crate::scheduler::TaskId::new(1, generation).unwrap())
            .unwrap();
        for handle in old {
            assert_eq!(s.resolve(1, handle, Rights::SEND), Err(Error::Denied));
        }
        assert_eq!(
            s.publish_process_completion(
                crate::user_entry::task::Outcome {
                    id: id(1, generation),
                    root: image(1).root_physical,
                    reason: crate::user_entry::task::Reason::Cancelled,
                    syscalls: 0,
                },
                &q
            ),
            Ok(1)
        );
        for step in steps {
            let Step::Inherit { source, handle, .. } = step else {
                panic!()
            };
            assert!(
                s.resolve(usize::from(source.slot), handle, Rights::ALL)
                    .is_ok()
            );
        }
    }
}

#[test]
fn second_application_grant_failure_removes_first_and_preserves_services() {
    for mode in 0..3 {
        let (mut s, mut q, c, factory) = fixture();
        let mut steps = application_steps(&mut s, c.id);
        let Step::Inherit { source, handle, .. } = steps[1] else {
            panic!()
        };
        steps[1] = Step::Inherit {
            source,
            member: 0,
            rights: Rights::SEND,
            handle: match mode {
                0 => handle ^ (1 << 32),
                1 => s.derive(source, handle, id(3, 1), Rights::SEND).unwrap(),
                _ => handle,
            },
        };
        if mode == 1 {
            let Step::Inherit { handle, .. } = steps[1] else {
                panic!()
            };
            steps[1] = Step::Inherit {
                source: id(3, 1),
                handle,
                member: 0,
                rights: Rights::SEND,
            };
        } else if mode == 2 {
            s.detach(source).unwrap();
        }
        let before = q;
        let permit = claim(&mut s, c, factory, 1);
        assert!(
            s.admit_launch(&permit, &mut q, member(1, 1), &steps)
                .is_err()
        );
        unchanged_scheduler(q, before);
        assert!(s.table(id(1, 1)).is_err());
        assert!(s.tables[1].caps.iter().all(|cap| cap.value.is_none()));
        assert!(s.processes.iter().all(|process| process.value.is_none()));
        assert!(s.validate_launch(&permit).is_ok());
        let Step::Inherit { source, handle, .. } = steps[0] else {
            panic!()
        };
        assert!(
            s.resolve(usize::from(source.slot), handle, Rights::ALL)
                .is_ok()
        );
    }
}

#[test]
fn process_quota_after_both_application_grants_rolls_back_without_endpoint_leaks() {
    let (mut s, mut q, c, factory) = fixture();
    let steps = application_steps(&mut s, c.id);
    let lease = s
        .grant_process(c.id, id(2, 1), process::Rights::Inspect)
        .unwrap();
    s.grant_process(c.id, id(3, 1), process::Rights::Inspect)
        .unwrap();
    let permit = claim(&mut s, c, factory, 1);
    let before = q;
    assert_eq!(
        s.admit_launch(&permit, &mut q, member(1, 1), &steps),
        Err(admission::Error::Ipc(Error::Quota))
    );
    unchanged_scheduler(q, before);
    assert!(s.table(id(1, 1)).is_err());
    assert!(s.tables[1].caps.iter().all(|cap| cap.value.is_none()));
    assert_eq!(
        s.objects
            .iter()
            .filter(|object| object.value.is_some())
            .count(),
        2
    );
    assert_eq!(s.process_operation(c, lease, false), (Status::Ok, 1));
    assert!(s.validate_launch(&permit).is_ok());
    s.revoke_process(c.id, lease).unwrap();
    let admitted = s
        .admit_launch(&permit, &mut q, member(1, 2), &steps)
        .unwrap();
    assert_eq!(admitted.handles[0] >> 32, 2);
    assert_eq!(admitted.handles[1] >> 32, 2);
}

#[test]
fn abi_numbered_requests_reject_pointers_extra_args_zero_and_overflow() {
    assert_eq!(
        request(19, 1, 123, 1, 0, 0, 0),
        Ok(Request::Launch {
            handle: 123,
            sequence: 1
        })
    );
    for n in [0, u32::MAX as u64 + 1, u64::MAX] {
        assert_eq!(request(19, 1, 123, n, 0, 0, 0), Err(Status::Arguments));
    }
    for a in [[1, 0, 0], [0, 1, 0], [0, 0, 1]] {
        assert_eq!(
            request(19, 1, 123, 1, a[0], a[1], a[2]),
            Err(Status::Arguments)
        );
    }
    assert_eq!(request(19, 2, 123, 1, 0, 0, 0), Err(Status::Version));
}

#[test]
fn trusted_catalogue_slot_reservation_quota_and_generation_never_wrap() {
    let (mut s, _, c, h) = fixture();
    for (program, slot) in [(0, 4), (1, 0), (1, 1), (1, 8)] {
        assert_eq!(s.grant_launch(c.id, program, slot), Err(Error::Denied));
    }
    let other = s.grant_launch(id(2, 1), 8, 4).unwrap();
    assert_eq!(s.grant_launch(c.id, 9, 5), Err(Error::Quota));
    s.revoke_launch(id(2, 1), other).unwrap();
    s.launches[1].generation = u32::MAX;
    assert_eq!(s.grant_launch(c.id, 9, 5), Err(Error::Quota));
    s.revoke_launch(c.id, h).unwrap();
    let fresh = s.grant_launch(c.id, 7, 1).unwrap();
    assert_ne!(fresh, h);
    assert_eq!(s.request_launch(c, h, 1), (Status::Denied, 0));
}

#[test]
fn full_caller_type_sequence_and_duplicate_claim_are_enforced() {
    let (mut s, _, c, h) = fixture();
    for caller in [
        Caller::new(id(2, 1), image(2)),
        Caller {
            root: c.root + 4096,
            ..c
        },
        Caller { generation: 2, ..c },
        Caller { id: id(0, 2), ..c },
    ] {
        assert_eq!(s.request_launch(caller, h, 1), (Status::Denied, 0));
    }
    for bad in [
        0,
        1,
        u64::MAX,
        h ^ (1 << 32),
        h ^ (1 << 16),
        h & !0xffff,
        h + 2,
    ] {
        assert_eq!(s.request_launch(c, bad, 1), (Status::Denied, 0));
    }
    for seq in [0, 2, u32::MAX] {
        assert_eq!(s.request_launch(c, h, seq), (Status::Arguments, 0));
    }
    let p = claim(&mut s, c, h, 1);
    assert_eq!(
        s.validate_launch(&p),
        Ok(Plan {
            owner: c.id,
            program: 7,
            child_slot: 1,
            sequence: 1
        })
    );
    assert_eq!(s.request_launch(c, h, 1), (Status::Again, 0));
    assert_eq!(s.request_launch(c, h, 2), (Status::Again, 0));
    assert!(s.claim_launch().is_none());
    assert_eq!(s.process_operation(c, h, true), (Status::Denied, 0));
    assert!(s.resolve(0, h, Rights::SEND).is_err());
}

#[test]
fn atomic_child_admission_returns_owned_handle_and_same_sequence_never_restarts() {
    let (mut s, mut q, c, h) = fixture();
    let p = claim(&mut s, c, h, 1);
    let result = s
        .admit_launch(
            &p,
            &mut q,
            member(1, 1),
            &[
                Step::Endpoint { member: 0 },
                Step::Grant {
                    endpoint: 0,
                    target: c.id,
                    rights: Rights::SEND,
                },
            ],
        )
        .unwrap();
    let child = result.handles[2];
    assert_eq!(s.request_launch(c, h, 1), (Status::Ok, child));
    assert_eq!(s.process_operation(c, child, false), (Status::Ok, 1));
    assert_eq!(s.request_launch(c, h, 2), (Status::Again, 0));
    assert!(s.validate_launch(&p).is_err());
    assert!(s.claim_launch().is_none());
    s.detach(id(1, 1)).unwrap();
    q.teardown(crate::scheduler::TaskId::new(1, 1).unwrap())
        .unwrap();
    for _ in 0..3 {
        assert_eq!(s.request_launch(c, h, 1), (Status::Ok, child));
        assert!(s.claim_launch().is_none());
        assert_eq!(s.request_launch(c, h, 2), (Status::Again, 0));
    }
    assert_eq!(
        s.publish_process_completion(
            crate::user_entry::task::Outcome {
                id: id(1, 1),
                root: image(1).root_physical,
                reason: crate::user_entry::task::Reason::Exit(100),
                syscalls: 257,
            },
            &q
        ),
        Ok(1)
    );
    let p2 = claim(&mut s, c, h, 2);
    assert_eq!(s.process_operation(c, child, true), (Status::Denied, 0));
    let r2 = s.admit_launch(&p2, &mut q, member(1, 2), &[]).unwrap();
    assert_ne!(r2.handles[0], child);
    assert_eq!(s.request_launch(c, h, 2), (Status::Ok, r2.handles[0]));
    assert_eq!(s.request_launch(c, h, 1), (Status::Arguments, 0));
}

#[test]
fn process_grant_failure_rolls_back_scheduler_endpoints_and_keeps_claim() {
    let (mut s, mut q, c, h) = fixture();
    let a = s
        .grant_process(c.id, id(2, 1), process::Rights::Inspect)
        .unwrap();
    s.grant_process(c.id, id(3, 1), process::Rights::Inspect)
        .unwrap();
    let p = claim(&mut s, c, h, 1);
    let before = q;
    assert_eq!(
        s.admit_launch(
            &p,
            &mut q,
            member(1, 1),
            &[
                Step::Endpoint { member: 0 },
                Step::Grant {
                    endpoint: 0,
                    target: c.id,
                    rights: Rights::SEND
                }
            ]
        ),
        Err(admission::Error::Ipc(Error::Quota))
    );
    unchanged_scheduler(q, before);
    assert!(s.table(id(1, 1)).is_err());
    assert!(s.objects.iter().all(|o| o.value.is_none()));
    assert!(s.tables[0].caps.iter().all(|c| c.value.is_none()));
    assert_eq!(s.process_operation(c, a, false), (Status::Ok, 1));
    assert!(s.validate_launch(&p).is_ok());
    assert!(s.claim_launch().is_none());
    // Admission consumed the failed child's generation; retry needs a fresh one.
    s.revoke_process(c.id, a).unwrap();
    assert!(s.admit_launch(&p, &mut q, member(1, 1), &[]).is_err());
    assert!(s.admit_launch(&p, &mut q, member(1, 2), &[]).is_ok());
}

#[test]
fn failed_general_admission_removes_new_process_grants_without_quota_leak() {
    let (mut s, mut q, c, _) = fixture();
    let before = q;
    assert!(
        s.admit(
            &mut q,
            &[member(1, 1)],
            &[
                Step::Process {
                    member: 0,
                    owner: c.id,
                    rights: process::Rights::InspectTerminate
                },
                Step::Endpoint { member: 9 }
            ]
        )
        .is_err()
    );
    unchanged_scheduler(q, before);
    assert!(s.processes.iter().all(|p| p.value.is_none()));
    let a = s
        .admit(
            &mut q,
            &[member(1, 2)],
            &[Step::Process {
                member: 0,
                owner: c.id,
                rights: process::Rights::InspectTerminate,
            }],
        )
        .unwrap();
    assert_eq!(a.handles[0] >> 32, 2);
}

#[test]
fn revoke_owner_death_reuse_and_occupied_child_invalidate_effect() {
    for mutation in 0..3 {
        let (mut s, mut q, c, h) = fixture();
        let p = claim(&mut s, c, h, 1);
        match mutation {
            0 => {
                s.revoke_launch(c.id, h).unwrap();
                s.grant_launch(c.id, 7, 1).unwrap();
            }
            1 => {
                s.detach(c.id).unwrap();
                s.attach(id(0, 2), image(0)).unwrap();
            }
            _ => {
                s.admit(&mut q, &[member(1, 1)], &[]).unwrap();
            }
        }
        let before = q;
        assert!(s.admit_launch(&p, &mut q, member(1, 2), &[]).is_err());
        unchanged_scheduler(q, before);
        assert!(s.fail_launch(&p).is_err());
    }
}

#[test]
fn dropped_claim_failure_completion_and_exhausted_sequence_are_fail_closed() {
    let (mut s, mut q, c, h) = fixture();
    {
        let _p = claim(&mut s, c, h, 1);
    }
    assert!(s.claim_launch().is_none());
    assert_eq!(s.request_launch(c, h, 2), (Status::Again, 0));
    s.revoke_launch(c.id, h).unwrap();
    let h = s.grant_launch(c.id, 7, 1).unwrap();
    let p = claim(&mut s, c, h, 1);
    s.fail_launch(&p).unwrap();
    assert_eq!(s.request_launch(c, h, 1), (Status::Cancelled, 0));
    assert!(s.fail_launch(&p).is_err());
    let p = claim(&mut s, c, h, 2);
    assert!(s.admit_launch(&p, &mut q, member(4, 1), &[]).is_err());
    assert!(
        s.admit_launch(
            &p,
            &mut q,
            member(1, 1),
            &[Step::Process {
                member: 0,
                owner: c.id,
                rights: process::Rights::Inspect
            }]
        )
        .is_err()
    );
    s.fail_launch(&p).unwrap();
    s.launches[0].value.as_mut().unwrap().sequence = u32::MAX;
    assert_eq!(s.request_launch(c, h, 1), (Status::Arguments, 0));
    assert_eq!(s.request_launch(c, h, u32::MAX), (Status::Cancelled, 0));
    for slot in [0, 2, 3] {
        s.detach(id(slot, 1)).unwrap();
    }
    assert!(s.is_empty());
}
