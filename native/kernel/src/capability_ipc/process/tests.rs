use super::*;
use crate::user_entry::{
    InitialReturnFrame,
    syscall::{Request, request},
};

fn id(slot: u8) -> TaskId {
    TaskId::new(slot, 1).unwrap()
}
fn image(slot: u8) -> ImageAdmission {
    ImageAdmission {
        root_physical: 0x100000 + u64::from(slot) * 4096,
        root_generation: 1,
        code_physical: 0x200000,
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
fn caller(slot: u8) -> Caller {
    Caller::new(id(slot), image(slot))
}
fn space() -> Space {
    let mut s = Space::new();
    for i in 0..TASKS {
        s.attach(id(i as u8), image(i as u8)).unwrap();
    }
    s
}
fn grant(s: &mut Space) -> u64 {
    s.grant_process(id(0), id(1), Rights::InspectTerminate)
        .unwrap()
}

#[test]
fn abi_has_no_user_pointer_task_id_or_extra_argument() {
    for number in [17, 18] {
        assert_eq!(
            request(number, 1, 123, 0, 0, 0, 0),
            Ok(Request::Process {
                handle: 123,
                terminate: number == 18
            })
        );
        for args in [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]] {
            assert_eq!(
                request(number, 1, 123, args[0], args[1], args[2], args[3]),
                Err(Status::Arguments)
            );
        }
        assert_eq!(request(number, 2, 123, 0, 0, 0, 0), Err(Status::Version));
    }
    assert_eq!(request(20, 1, 0, 0, 0, 0, 0), Err(Status::Unknown));
}

#[test]
fn owner_identity_handle_type_generation_and_rights_are_enforced() {
    let mut s = space();
    let h = grant(&mut s);
    let inspect = s.grant_process(id(2), id(1), Rights::Inspect).unwrap();
    assert_eq!(
        s.process_operation(caller(2), inspect, false),
        (Status::Ok, 1)
    );
    assert_eq!(
        s.process_operation(caller(2), inspect, true),
        (Status::Denied, 0)
    );
    for c in [
        caller(1),
        caller(2),
        Caller {
            root: caller(0).root + 4096,
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
        assert_eq!(s.process_operation(c, h, true), (Status::Denied, 0));
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
        assert_eq!(
            s.process_operation(caller(0), bad, true),
            (Status::Denied, 0)
        );
    }
    let endpoint = s.create_endpoint(id(0)).unwrap();
    assert_eq!(
        s.process_operation(caller(0), endpoint, true),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.resolve(0, h, super::super::Rights::SEND),
        Err(Error::Denied)
    );
    assert!(s.claim_process_stop().is_none());
    assert_eq!(s.process_operation(caller(0), h, false), (Status::Ok, 1));
}

#[test]
fn queued_stop_is_idempotent_claimed_once_and_never_reports_reaped() {
    let mut s = space();
    let h = grant(&mut s);
    for _ in 0..10 {
        assert_eq!(s.process_operation(caller(0), h, true), (Status::Again, 0));
    }
    let permit = s.claim_process_stop().unwrap();
    assert_eq!(s.validate_process_stop(&permit), Ok(id(1)));
    assert!(s.claim_process_stop().is_none());
    assert_eq!(s.process_operation(caller(0), h, true), (Status::Again, 0));
    assert_eq!(s.process_operation(caller(0), h, false), (Status::Ok, 1));
    assert_eq!(s.tables[1].caller, Some(caller(1)));
    s.detach(id(1)).unwrap();
    assert_eq!(s.validate_process_stop(&permit), Err(Error::Denied));
    assert_eq!(
        s.process_operation(caller(0), h, false),
        (Status::Revoked, 0)
    );
    assert_eq!(
        s.process_operation(caller(0), h, true),
        (Status::Revoked, 0)
    );
    assert!(s.claim_process_stop().is_none());
}

#[test]
fn dropped_claim_is_retained_fail_closed_until_trusted_revocation() {
    let mut s = space();
    let h = grant(&mut s);
    s.process_operation(caller(0), h, true);
    {
        let _permit = s.claim_process_stop().unwrap();
    }
    for _ in 0..4 {
        assert_eq!(s.process_operation(caller(0), h, true), (Status::Again, 0));
        assert!(s.claim_process_stop().is_none());
    }
    s.revoke_process(id(0), h).unwrap();
    assert_eq!(s.process_operation(caller(0), h, true), (Status::Denied, 0));
    let fresh = grant(&mut s);
    assert_ne!(fresh, h);
    assert_eq!(
        s.process_operation(caller(0), fresh, false),
        (Status::Ok, 1)
    );
}

#[test]
fn revoke_owner_death_and_target_reuse_invalidate_pending_and_claimed_work() {
    for claimed in [false, true] {
        for mutation in 0..3 {
            let mut s = space();
            let h = grant(&mut s);
            s.process_operation(caller(0), h, true);
            let p = if claimed {
                s.claim_process_stop()
            } else {
                None
            };
            match mutation {
                0 => s.revoke_process(id(0), h).unwrap(),
                1 => {
                    s.detach(id(0)).unwrap();
                    s.attach(TaskId::new(0, 2).unwrap(), image(0)).unwrap();
                }
                _ => {
                    s.detach(id(1)).unwrap();
                    s.attach(TaskId::new(1, 2).unwrap(), image(1)).unwrap();
                }
            }
            if let Some(p) = p {
                assert_eq!(s.validate_process_stop(&p), Err(Error::Denied));
            }
            assert!(s.claim_process_stop().is_none());
            assert_ne!(s.process_operation(caller(0), h, true), (Status::Again, 0));
            assert!(s.tables[1].caller.is_some());
        }
    }
}

#[test]
fn lease_reuse_invalidates_old_permit_even_for_same_live_owner_and_target() {
    let mut s = space();
    let h = grant(&mut s);
    s.process_operation(caller(0), h, true);
    let old = s.claim_process_stop().unwrap();
    s.revoke_process(id(0), h).unwrap();
    let fresh = grant(&mut s);
    s.process_operation(caller(0), fresh, true);
    let new = s.claim_process_stop().unwrap();
    assert_eq!(s.validate_process_stop(&old), Err(Error::Denied));
    assert_eq!(s.validate_process_stop(&new), Ok(id(1)));
}

#[test]
fn quotas_and_generation_exhaustion_fail_without_mutation_or_ipc_loss() {
    let mut s = space();
    let endpoint = s.create_endpoint(id(0)).unwrap();
    let mut handles = [0; LEASES];
    for (i, h) in handles.iter_mut().enumerate() {
        *h = s
            .grant_process(id((i / 2) as u8), id(7), Rights::InspectTerminate)
            .unwrap();
    }
    for owner in [0, 2] {
        let before = s.processes;
        assert_eq!(
            s.grant_process(id(owner), id(7), Rights::Inspect),
            Err(Error::Quota)
        );
        assert_eq!(s.processes, before);
    }
    s.revoke_process(id(1), handles[2]).unwrap();
    let before = s.processes;
    assert_eq!(
        s.grant_process(id(0), id(6), Rights::Inspect),
        Err(Error::Quota)
    );
    assert_eq!(s.processes, before);
    s.processes[2].generation = u32::MAX;
    assert_eq!(
        s.grant_process(id(2), id(7), Rights::Inspect),
        Err(Error::Quota)
    );
    assert_eq!(s.processes[2].generation, u32::MAX);
    assert!(s.resolve(0, endpoint, super::super::Rights::SEND).is_ok());
    for i in 0..TASKS {
        s.detach(id(i as u8)).unwrap();
    }
    assert!(s.is_empty());
}

#[test]
fn grant_requires_distinct_attached_tasks_and_revoked_leases_still_charge_quota() {
    let mut s = space();
    let before = s.processes;
    assert_eq!(
        s.grant_process(id(0), id(0), Rights::InspectTerminate),
        Err(Error::Denied)
    );
    assert_eq!(
        s.grant_process(id(0), TaskId::new(1, 2).unwrap(), Rights::InspectTerminate),
        Err(Error::Identity)
    );
    assert_eq!(s.processes, before);
    let h = grant(&mut s);
    s.grant_process(id(0), id(2), Rights::Inspect).unwrap();
    s.detach(id(1)).unwrap();
    assert_eq!(
        s.grant_process(id(0), id(3), Rights::Inspect),
        Err(Error::Quota)
    );
    s.revoke_process(id(0), h).unwrap();
    assert!(s.grant_process(id(0), id(3), Rights::Inspect).is_ok());
}
