use super::*;

fn members(generation: u32) -> [Member; TASKS] {
    core::array::from_fn(|i| member(i as u8, generation))
}
fn ring(generation: u32) -> [Step; TASKS * 2] {
    core::array::from_fn(|i| {
        if i < TASKS {
            Step::Endpoint { member: i as u8 }
        } else {
            Step::Grant {
                endpoint: (i - TASKS) as u8,
                target: member(((i - TASKS + 1) % TASKS) as u8, generation).id,
                rights: Rights::SEND,
            }
        }
    })
}

#[test]
fn eight_task_ring_covers_every_table_endpoint_and_scheduler_slot() {
    assert_eq!((TASKS, ENDPOINTS, CAPS, DEPTH, MAX_BYTES), (8, 8, 4, 4, 64));
    let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
    let a = s.admit(&mut scheduler, &members(1), &ring(1)).unwrap();
    assert_eq!(a.count, 16);
    assert_eq!(scheduler.summary().runnable_count, 8);
    let mut memory = Bytes::new();
    for i in 0..TASKS {
        let next = ((i + 1) % TASKS) as u8;
        memory.data[0] = i as u8;
        assert_eq!(
            s.transfer(
                caller(next),
                a.handles[TASKS + i],
                BASE,
                8,
                true,
                &mut memory
            ),
            (Status::Ok, 8)
        );
        assert_eq!(
            s.transfer(
                caller(next),
                a.handles[TASKS + i],
                BASE,
                8,
                false,
                &mut memory
            ),
            (Status::Denied, 0)
        );
        assert_eq!(
            s.transfer(caller(i as u8), a.handles[i], BASE, 8, false, &mut memory),
            (Status::Ok, 8)
        );
        assert_eq!(memory.data[0], i as u8);
        assert_eq!(s.create_endpoint(id(i as u8)), Err(Error::Quota));
    }
    let cpu = crate::scheduler::CpuId::new(0).unwrap();
    let mut seen = [false; TASKS];
    for _ in 0..TASKS {
        let id = scheduler.dispatch(cpu).unwrap();
        assert!(!seen[usize::from(id.slot)]);
        seen[usize::from(id.slot)] = true;
        scheduler.yield_current(cpu).unwrap();
    }
    assert!(seen.into_iter().all(|v| v));
    for i in (0..TASKS).rev() {
        s.detach(id(i as u8)).unwrap();
        scheduler
            .teardown(crate::scheduler::TaskId::new(i as u8, 1).unwrap())
            .unwrap();
    }
    assert!(s.is_empty());
    scheduler.validate().unwrap();
}

#[test]
fn eight_task_every_admission_prefix_rolls_back_without_generation_rewind() {
    for prefix in 0..=16 {
        let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
        let mut steps = ring(1).to_vec();
        steps.truncate(prefix);
        steps.push(Step::Endpoint {
            member: TASKS as u8,
        });
        let before = scheduler.summary();
        assert_eq!(
            s.admit(&mut scheduler, &members(1), &steps),
            Err(AdmitError::Plan)
        );
        assert_eq!(scheduler.summary(), before);
        assert!(s.is_empty());
        assert!(s.tables.iter().all(|t| t.last_task_generation == 1));
        assert!(s.admit(&mut scheduler, &members(1), &ring(1)).is_err());
        let a = s.admit(&mut scheduler, &members(2), &ring(2)).unwrap();
        for i in 0..TASKS.min(prefix) {
            assert!(a.handles[i] >> 32 > 1);
        }
        scheduler.validate().unwrap();
    }
}

#[test]
fn upper_slot_collision_and_exhausted_generation_preserve_existing_owner() {
    for duplicate_root in [false, true] {
        let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
        s.attach(id(7), image(7)).unwrap();
        let endpoint = s.create_endpoint(id(7)).unwrap();
        let mut memory = Bytes::new();
        assert_eq!(
            s.transfer(caller(7), endpoint, BASE, 8, true, &mut memory),
            (Status::Ok, 8)
        );
        let old = s.tables[7];
        let before = scheduler.summary();
        let mut m = members(1);
        if duplicate_root {
            m[4].image = image(7);
        }
        assert!(s.admit(&mut scheduler, &m, &ring(1)).is_err());
        assert_eq!(scheduler.summary(), before);
        assert_eq!(s.tables[7], old);
        assert_eq!(
            s.transfer(caller(7), endpoint, BASE, 8, false, &mut memory),
            (Status::Ok, 8)
        );
        s.detach(id(7)).unwrap();
        assert!(s.is_empty());
    }
    let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
    s.tables[7].last_task_generation = u32::MAX;
    assert!(s.admit(&mut scheduler, &members(1), &ring(1)).is_err());
    assert!(s.is_empty());
    assert_eq!(s.tables[7].last_task_generation, u32::MAX);
    assert_eq!(scheduler.summary().runnable_count, 0);
}

#[test]
fn tracked_completion_and_revocation_work_in_highest_slots_without_cross_pair_authority() {
    use crate::capability_ipc::{reply::Operation as Reply, request::Operation as Request};
    let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
    let a = s.admit(&mut scheduler, &members(1), &ring(1)).unwrap();
    let mut wire = Bytes::new();
    let (status, request) = s.request_operation(
        caller(7),
        a.handles[TASKS + 6],
        BASE,
        8,
        Request::Begin,
        &mut wire,
    );
    assert_eq!(status, Status::Ok);
    assert_eq!(
        s.message(caller(6), a.handles[6], BASE, 64, Reply::Receive, &mut wire),
        (Status::Ok, 40)
    );
    let reply = u64::from_le_bytes(wire.data[16..24].try_into().unwrap());
    assert_eq!(u64::from_le_bytes(wire.data[..8].try_into().unwrap()), 7);
    assert_eq!(
        s.message(caller(0), reply, BASE, 8, Reply::Reply, &mut wire),
        (Status::Denied, 0)
    );
    s.detach(id(6)).unwrap();
    let before = wire.accesses;
    assert_eq!(
        s.request_operation(caller(7), request, BASE, 64, Request::Take, &mut wire),
        (Status::Revoked, 0)
    );
    assert_eq!(wire.accesses, before);
    assert_eq!(
        s.request_operation(caller(7), request, BASE, 64, Request::Take, &mut wire),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.transfer(caller(1), a.handles[TASKS], BASE, 8, true, &mut wire),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.transfer(caller(0), a.handles[0], BASE, 8, false, &mut wire),
        (Status::Ok, 8)
    );
    for i in [0, 1, 2, 3, 4, 5, 7] {
        s.detach(id(i)).unwrap();
    }
    assert!(s.is_empty());
}
