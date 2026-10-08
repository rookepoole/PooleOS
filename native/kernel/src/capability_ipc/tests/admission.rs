use super::*;
use crate::capability_ipc::admission::{Error as AdmitError, MAX_STEPS, Member, Step};
use std::vec;

fn member(slot: u8, generation: u32) -> Member {
    Member {
        id: TaskId::new(slot, generation).unwrap(),
        image: image(slot),
        priority: 16,
    }
}
fn pair(generation: u32) -> [Member; 2] {
    [member(0, generation), member(1, generation)]
}
fn plan(generation: u32) -> [Step; 4] {
    [
        Step::Endpoint { member: 0 },
        Step::Endpoint { member: 1 },
        Step::Grant {
            endpoint: 1,
            target: member(0, generation).id,
            rights: Rights::SEND,
        },
        Step::Grant {
            endpoint: 0,
            target: member(1, generation).id,
            rights: Rights::SEND,
        },
    ]
}

#[test]
fn admission_commits_queue_members_and_real_attenuated_exchange_together() {
    let mut s = Space::new();
    let mut scheduler = Scheduler::new(1).unwrap();
    let ready = s.admit(&mut scheduler, &pair(1), &plan(1)).unwrap();
    assert_eq!(ready.count, 4);
    assert_eq!(
        &ready.handles[..4],
        &[0x100010001, 0x100010001, 0x100010002, 0x100010002]
    );
    assert_eq!(scheduler.summary().runnable_count, 2);
    let mut memory = Bytes::new();
    assert_eq!(
        s.transfer(caller(0), ready.handles[2], BASE, 8, true, &mut memory),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.transfer(caller(1), ready.handles[1], BASE, 8, false, &mut memory),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.transfer(caller(0), ready.handles[2], BASE, 8, false, &mut memory),
        (Status::Denied, 0)
    );
    scheduler.validate().unwrap();
}

#[test]
fn admission_every_plan_prefix_failure_removes_live_authority_without_generation_rewind() {
    for prefix in 0..=4 {
        let mut s = Space::new();
        let mut scheduler = Scheduler::new(1).unwrap();
        let before = scheduler.summary();
        let mut steps = plan(1).to_vec();
        steps.truncate(prefix);
        steps.push(Step::Endpoint { member: 2 });
        assert_eq!(
            s.admit(&mut scheduler, &pair(1), &steps),
            Err(AdmitError::Plan)
        );
        assert!(s.is_empty());
        assert_eq!(scheduler.summary(), before);
        assert_eq!(s.tables[0].last_task_generation, 1);
        assert_eq!(s.tables[1].last_task_generation, 1);
        assert_eq!(
            s.admit(&mut scheduler, &pair(1), &plan(1)),
            Err(AdmitError::Ipc(Error::Identity))
        );
        let retry = s.admit(&mut scheduler, &pair(2), &plan(2)).unwrap();
        if prefix > 0 {
            assert!(retry.handles[0] >> 32 > 1);
        }
        assert_eq!(scheduler.summary().runnable_count, 2);
    }
}

#[test]
fn admission_endpoint_and_table_exhaustion_are_atomic() {
    for table_full in [false, true] {
        let mut s = Space::new();
        let mut scheduler = Scheduler::new(1).unwrap();
        let steps = if table_full {
            let mut p = vec![Step::Endpoint { member: 0 }];
            p.extend(
                [Step::Grant {
                    endpoint: 0,
                    target: id(1),
                    rights: Rights::SEND,
                }; 5],
            );
            p
        } else {
            (0..5).map(|i| Step::Endpoint { member: i % 2 }).collect()
        };
        assert_eq!(
            s.admit(&mut scheduler, &pair(1), &steps),
            Err(AdmitError::Ipc(Error::Quota))
        );
        assert!(s.is_empty());
        assert_eq!(scheduler.summary(), Scheduler::new(1).unwrap().summary());
    }
}

#[test]
fn admission_partial_attach_does_not_detach_preexisting_task_or_its_pending_message() {
    let mut s = Space::new();
    s.attach(id(1), image(1)).unwrap();
    let endpoint = s.create_endpoint(id(1)).unwrap();
    let mut memory = Bytes::new();
    assert_eq!(
        s.transfer(caller(1), endpoint, BASE, 8, true, &mut memory),
        (Status::Ok, 8)
    );
    let table = s.tables[1];
    let objects = s.objects;
    let mut scheduler = Scheduler::new(1).unwrap();
    assert_eq!(
        s.admit(&mut scheduler, &pair(1), &[]),
        Err(AdmitError::Ipc(Error::Identity))
    );
    assert_eq!(s.tables[1], table);
    assert_eq!(s.objects, objects);
    assert!(s.tables[0].caller.is_none());
    assert_eq!(s.tables[0].last_task_generation, 1);
}

#[test]
fn admission_scheduler_preflight_failure_never_changes_ipc_or_existing_running_peer() {
    let (mut scheduler, cpu) = running(3);
    let snapshot = scheduler.task_snapshot(scheduled(3)).unwrap();
    let summary = scheduler.summary();
    for members in [
        vec![],
        vec![member(0, 1); 5],
        vec![member(0, 1); 2],
        vec![Member {
            priority: 0,
            ..member(0, 1)
        }],
        vec![member(3, 1)],
    ] {
        let mut s = Space::new();
        assert!(s.admit(&mut scheduler, &members, &[]).is_err());
        assert_eq!(s, Space::new());
        assert_eq!(scheduler.summary(), summary);
        assert_eq!(scheduler.task_snapshot(scheduled(3)).unwrap(), snapshot);
        assert_eq!(scheduler.current(cpu).unwrap(), Some(scheduled(3)));
    }
    let mut s = Space::new();
    assert_eq!(
        s.admit(
            &mut scheduler,
            &pair(1),
            &[Step::Endpoint { member: 0 }; MAX_STEPS + 1]
        ),
        Err(AdmitError::Plan)
    );
    assert_eq!(s, Space::new());
}

#[test]
fn admission_rollback_preserves_inherited_source_and_revokes_only_new_exports() {
    let mut s = Space::new();
    s.attach(id(3), image(3)).unwrap();
    let old = s.create_endpoint(id(3)).unwrap();
    let old_cap = s.tables[3].caps[0];
    let old_object = s.objects[0];
    let mut scheduler = Scheduler::new(1).unwrap();
    let steps = [
        Step::Inherit {
            source: id(3),
            handle: old,
            member: 0,
            rights: Rights::SEND,
        },
        Step::Endpoint { member: 1 },
        Step::Grant {
            endpoint: 1,
            target: id(3),
            rights: Rights::SEND,
        },
        Step::Grant {
            endpoint: 0,
            target: id(3),
            rights: Rights::SEND,
        },
    ];
    assert_eq!(
        s.admit(&mut scheduler, &pair(1), &steps),
        Err(AdmitError::Plan)
    );
    assert_eq!(s.tables[3].caps[0], old_cap);
    assert_eq!(s.objects[0], old_object);
    assert!(s.tables[3].caps[1].value.is_none());
    assert_eq!(s.tables[3].caps[1].generation, 1);
    assert!(s.tables[0].caller.is_none() && s.tables[1].caller.is_none());
}

#[test]
fn admission_denies_forward_references_foreign_targets_and_rights_amplification() {
    for bad in [
        Step::Grant {
            endpoint: 1,
            target: id(0),
            rights: Rights::SEND,
        },
        Step::Grant {
            endpoint: 0,
            target: id(3),
            rights: Rights::SEND,
        },
        Step::Grant {
            endpoint: 0,
            target: id(1),
            rights: Rights(16),
        },
        Step::Grant {
            endpoint: 0,
            target: id(1),
            rights: Rights(0),
        },
        Step::Inherit {
            source: id(3),
            handle: 1,
            member: 0,
            rights: Rights::SEND,
        },
    ] {
        let mut s = Space::new();
        let mut scheduler = Scheduler::new(1).unwrap();
        assert!(
            s.admit(
                &mut scheduler,
                &pair(1),
                &[Step::Endpoint { member: 0 }, bad]
            )
            .is_err()
        );
        assert!(s.is_empty());
        assert_eq!(scheduler.summary().task_count, 0);
    }
}

#[test]
fn admission_generation_exhaustion_and_root_collision_never_reset_owners() {
    let mut s = Space::new();
    for c in &mut s.tables[0].caps {
        c.generation = u32::MAX;
    }
    s.clock.generation = u64::MAX;
    s.clock.expired = 19;
    let mut scheduler = Scheduler::new(1).unwrap();
    assert_eq!(
        s.admit(&mut scheduler, &pair(1), &plan(1)),
        Err(AdmitError::Ipc(Error::Quota))
    );
    assert!(s.is_empty());
    assert!(s.tables[0].caps.iter().all(|c| c.generation == u32::MAX));
    assert_eq!((s.clock.generation, s.clock.expired), (u64::MAX, 19));
    let mut collision = pair(2);
    collision[1].image = collision[0].image;
    assert_eq!(
        s.admit(&mut scheduler, &collision, &[]),
        Err(AdmitError::Ipc(Error::Identity))
    );
    assert!(s.is_empty());
    assert_eq!(scheduler.summary().task_count, 0);
}
