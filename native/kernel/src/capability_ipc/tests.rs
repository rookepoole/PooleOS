use super::wait::{Admission, Readiness, Ticket};
use super::*;
use crate::scheduler::{CpuId, Scheduler, WakeReason};
use crate::virtual_memory::USER_WINDOW_START as BASE;

fn scheduled(slot: u8) -> crate::scheduler::TaskId {
    crate::scheduler::TaskId::new(slot, 1).unwrap()
}
fn running(slot: u8) -> (Scheduler, CpuId) {
    let mut scheduler = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let id = scheduler.create_task(slot, 1, 16, 1).unwrap();
    scheduler.activate(id, cpu).unwrap();
    scheduler.dispatch(cpu).unwrap();
    (scheduler, cpu)
}
fn pending(s: &mut Space, slot: u8, h: u64, readiness: Readiness) -> Ticket {
    let Admission::Pending(ticket) = s.prepare_wait(caller(slot), h, readiness).unwrap() else {
        panic!("not pending")
    };
    ticket
}
fn charge(s: &mut Scheduler, cpu: CpuId, slot: u8) {
    let snapshot = s.task_snapshot(scheduled(slot)).unwrap();
    s.account_dispatch(
        cpu,
        scheduled(slot),
        snapshot.dispatch_count,
        snapshot.runtime_ticks,
        7,
    )
    .unwrap();
}

#[test]
fn wait_authority_duplicate_exhaustion_and_abi_arguments_are_checked() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let send = s.derive(id(0), h, id(1), Rights::SEND).unwrap();
    assert_eq!(
        s.prepare_wait(caller(1), send, Readiness::Readable),
        Err(Status::Denied)
    );
    assert_eq!(
        s.prepare_wait(
            Caller {
                generation: 2,
                ..caller(0)
            },
            h,
            Readiness::Readable
        ),
        Err(Status::Denied)
    );
    assert_eq!(
        s.prepare_wait(caller(0), 0, Readiness::Readable),
        Err(Status::Denied)
    );
    assert_eq!(
        s.prepare_wait(caller(1), send, Readiness::Writable),
        Ok(Admission::Ready)
    );
    s.tables[0].wait_generation = u64::MAX;
    assert_eq!(
        s.prepare_wait(caller(0), h, Readiness::Readable),
        Err(Status::Again)
    );
    assert!(s.tables[0].wait.is_none());
    s.tables[0].wait_generation = 0;
    pending(&mut s, 0, h, Readiness::Readable);
    assert_eq!(
        s.prepare_wait(caller(0), h, Readiness::Readable),
        Err(Status::Again)
    );
    use crate::user_entry::syscall::{Request, request};
    assert_eq!(
        request(5, 1, h, 0, 0, 0, 0),
        Ok(Request::Wait {
            handle: h,
            readiness: Readiness::Readable
        })
    );
    assert_eq!(
        request(5, 1, h, 1, 0, 0, 0),
        Ok(Request::Wait {
            handle: h,
            readiness: Readiness::Writable
        })
    );
    for args in [
        (1, 2, 0, 0, 0),
        (1, 0, 1, 0, 0),
        (1, 0, 0, 1, 0),
        (1, 0, 0, 0, 1),
    ] {
        assert_eq!(
            request(5, args.0, h, args.1, args.2, args.3, args.4),
            Err(Status::Arguments)
        );
    }
    assert_eq!(request(5, 2, h, 0, 0, 0, 0), Err(Status::Version));
}

#[test]
fn wait_park_rejects_uncharged_wrong_cpu_and_duplicate_without_losing_owner() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let ticket = pending(&mut s, 0, h, Readiness::Readable);
    let (mut scheduler, cpu) = running(0);
    let before = scheduler.summary();
    assert!(s.park_wait(ticket, &mut scheduler, cpu).is_err());
    assert_eq!(scheduler.summary(), before);
    charge(&mut scheduler, cpu, 0);
    assert!(
        s.park_wait(ticket, &mut scheduler, CpuId::new(1).unwrap())
            .is_err()
    );
    s.park_wait(ticket, &mut scheduler, cpu).unwrap();
    let before = scheduler.summary();
    assert!(s.park_wait(ticket, &mut scheduler, cpu).is_err());
    assert!(scheduler.cancel_wait(scheduled(0), cpu).is_err());
    assert!(scheduler.signal_wait(scheduled(0), cpu).is_err());
    assert_eq!(scheduler.summary(), before);
    assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
    scheduler.validate().unwrap();
}

#[test]
fn arrival_between_arm_and_park_is_not_lost_and_completion_retries_exactly_once() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let ticket = pending(&mut s, 0, h, Readiness::Readable);
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, true, &mut Bytes::new()),
        (Status::Ok, 8)
    );
    let (mut scheduler, cpu) = running(0);
    charge(&mut scheduler, cpu, 0);
    s.park_wait(ticket, &mut scheduler, cpu).unwrap();
    assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(1));
    assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
    assert!(s.cancel_wait(ticket, &mut scheduler, cpu).is_err());
    assert!(
        s.complete_wait(ticket, &mut scheduler, cpu, |_| panic!("not dispatched"))
            .is_err()
    );
    scheduler.dispatch(cpu).unwrap();
    let before = scheduler.summary();
    assert!(
        s.complete_wait(ticket, &mut scheduler, cpu, |_| Err(Error::Denied))
            .is_err()
    );
    assert_eq!(scheduler.summary(), before);
    assert_eq!(
        scheduler.task_snapshot(scheduled(0)).unwrap().wake_reason,
        WakeReason::Signalled
    );
    assert_eq!(
        s.complete_wait(ticket, &mut scheduler, cpu, |status| {
            assert_eq!(status, Status::Ok);
            Ok(())
        }),
        Ok(Status::Ok)
    );
    assert!(
        s.complete_wait(ticket, &mut scheduler, cpu, |_| panic!("replayed"))
            .is_err()
    );
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, false, &mut Bytes::new()),
        (Status::Ok, 8)
    );
    let next = pending(&mut s, 0, h, Readiness::Readable);
    assert_ne!(next, ticket);
    assert!(s.park_wait(ticket, &mut scheduler, cpu).is_err());
}

#[test]
fn writable_wait_wakes_after_dequeue_without_reserving_capacity_or_borrowing_buffer() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let mut memory = Bytes::new();
    for _ in 0..DEPTH {
        assert_eq!(
            s.transfer(caller(0), h, BASE, 8, true, &mut memory),
            (Status::Ok, 8)
        );
    }
    let ticket = pending(&mut s, 0, h, Readiness::Writable);
    let (mut scheduler, cpu) = running(0);
    charge(&mut scheduler, cpu, 0);
    s.park_wait(ticket, &mut scheduler, cpu).unwrap();
    assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, false, &mut memory),
        (Status::Ok, 8)
    );
    assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(1));
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, true, &mut memory),
        (Status::Ok, 8)
    );
    scheduler.dispatch(cpu).unwrap();
    s.complete_wait(ticket, &mut scheduler, cpu, |_| Ok(()))
        .unwrap();
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, true, &mut memory),
        (Status::Again, 0)
    );
}

#[test]
fn cancelled_and_revoked_waits_resume_once_and_destroyed_objects_cannot_rebind() {
    for mode in 0..4 {
        let mut s = space();
        let h = s.create_endpoint(id(0)).unwrap();
        let receive = s.derive(id(0), h, id(1), Rights::RECEIVE).unwrap();
        let ticket = pending(&mut s, 1, receive, Readiness::Readable);
        let (mut scheduler, cpu) = running(1);
        charge(&mut scheduler, cpu, 1);
        s.park_wait(ticket, &mut scheduler, cpu).unwrap();
        match mode {
            0 => s.cancel_wait(ticket, &mut scheduler, cpu).unwrap(),
            1 => s.close(id(1), receive).unwrap(),
            2 => s.destroy(id(0), h).unwrap(),
            _ => s.detach(id(0)).unwrap(),
        }
        if mode != 0 {
            if mode == 2 {
                s.create_endpoint(id(0)).unwrap();
            }
            assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(1));
        }
        assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
        scheduler.dispatch(cpu).unwrap();
        let expected = if mode == 0 {
            Status::Cancelled
        } else {
            Status::Revoked
        };
        assert_eq!(
            s.complete_wait(ticket, &mut scheduler, cpu, |status| {
                assert_eq!(status, expected);
                Ok(())
            }),
            Ok(expected)
        );
        assert!(s.cancel_wait(ticket, &mut scheduler, cpu).is_err());
        scheduler.validate().unwrap();
    }
}

#[test]
fn detached_waiter_cannot_wake_reused_task_or_reset_ticket_generation() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let ticket = pending(&mut s, 0, h, Readiness::Readable);
    let (mut scheduler, cpu) = running(0);
    charge(&mut scheduler, cpu, 0);
    s.park_wait(ticket, &mut scheduler, cpu).unwrap();
    s.detach_if_attached(id(0)).unwrap();
    scheduler.teardown(scheduled(0)).unwrap();
    s.detach_if_attached(id(0)).unwrap();
    let next = TaskId {
        generation: 2,
        ..id(0)
    };
    s.attach(next, image(0)).unwrap();
    assert_eq!(s.tables[0].wait_generation, 1);
    assert!(s.detach_if_attached(id(0)).is_err());
    assert!(s.cancel_wait(ticket, &mut scheduler, cpu).is_err());
    assert_eq!(s.poll_wakes(&mut scheduler, cpu), Ok(0));
}

fn image(slot: u8) -> ImageAdmission {
    ImageAdmission {
        root_physical: 0x100000 + u64::from(slot) * 4096,
        root_generation: 1,
        code_physical: 0x200000,
        stack_physical: 0x210000,
        initial_frame: crate::user_entry::InitialReturnFrame {
            rip: BASE + 16,
            rsp: BASE + 16384,
            cs: 0x33,
            ss: 0x2b,
            rflags: 0x202,
        },
    }
}
fn id(slot: u8) -> TaskId {
    TaskId::new(slot, 1).unwrap()
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
struct Bytes {
    data: [u8; MAX_BYTES],
    fault: Option<usize>,
    accesses: usize,
}
impl Bytes {
    fn new() -> Self {
        Self {
            data: [0x5a; MAX_BYTES],
            fault: None,
            accesses: 0,
        }
    }
}
impl Memory for Bytes {
    fn read(&mut self, address: u64) -> Result<u8, Status> {
        self.accesses += 1;
        let i = (address - BASE) as usize;
        if self.fault == Some(i) {
            Err(Status::Fault)
        } else {
            Ok(self.data[i])
        }
    }
    fn write(&mut self, address: u64, byte: u8) -> Result<(), Status> {
        self.accesses += 1;
        let i = (address - BASE) as usize;
        if self.fault == Some(i) {
            Err(Status::Fault)
        } else {
            self.data[i] = byte;
            Ok(())
        }
    }
}
#[test]
fn identity_root_generation_duplicate_roots_and_reuse_are_bound() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let mut m = Bytes::new();
    for c in [
        Caller {
            root: image(1).root_physical,
            ..caller(0)
        },
        Caller {
            generation: 2,
            ..caller(0)
        },
        Caller {
            id: id(1),
            ..caller(0)
        },
        Caller {
            id: TaskId {
                generation: 2,
                ..id(0)
            },
            ..caller(0)
        },
    ] {
        assert_eq!(s.transfer(c, h, BASE, 8, true, &mut m), (Status::Denied, 0));
    }
    assert_eq!(m.accesses, 0);
    assert_eq!(s.attach(id(0), image(0)), Err(Error::Identity));
    s.detach(id(0)).unwrap();
    assert_eq!(s.attach(id(0), image(0)), Err(Error::Identity));
    let next = TaskId {
        generation: 2,
        ..id(0)
    };
    assert_eq!(s.attach(next, image(1)), Err(Error::Identity));
    s.attach(next, image(0)).unwrap();
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, true, &mut m),
        (Status::Denied, 0)
    );
}
#[test]
fn task_local_typed_handles_deny_forgery_and_rights_amplification() {
    let mut s = space();
    let owner = s.create_endpoint(id(0)).unwrap();
    let send = s.derive(id(0), owner, id(1), Rights::SEND).unwrap();
    let mut m = Bytes::new();
    for h in [
        0,
        send ^ (1 << 32),
        send ^ (3 << 16),
        send | (1 << 31),
        send + CAPS as u64,
    ] {
        assert_eq!(
            s.transfer(caller(1), h, BASE, 8, true, &mut m),
            (Status::Denied, 0)
        );
        assert_eq!(s.close(id(1), h), Err(Error::Denied));
    }
    assert_eq!(
        s.transfer(caller(2), send, BASE, 8, true, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.transfer(caller(1), send, BASE, 8, false, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.derive(id(1), send, id(2), Rights::ALL),
        Err(Error::Denied)
    );
    assert_eq!(s.destroy(id(1), send), Err(Error::Denied));
    for rights in [Rights(0), Rights(16), Rights(255)] {
        assert_eq!(s.derive(id(0), owner, id(2), rights), Err(Error::Denied));
    }
    assert_eq!(m.accesses, 0);
}
#[test]
fn close_reuse_and_destroy_revoke_all_derived_handles_before_object_reuse() {
    let mut s = space();
    let owner = s.create_endpoint(id(0)).unwrap();
    let child = s.derive(id(0), owner, id(1), Rights::ALL).unwrap();
    let grandchild = s.derive(id(1), child, id(2), Rights::SEND).unwrap();
    s.close(id(1), child).unwrap();
    let replacement = s.derive(id(0), owner, id(1), Rights::SEND).unwrap();
    assert_ne!(child, replacement);
    let mut m = Bytes::new();
    assert_eq!(
        s.transfer(caller(1), child, BASE, 8, true, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.transfer(caller(2), grandchild, BASE, 8, true, &mut m),
        (Status::Ok, 8)
    );
    s.destroy(id(0), owner).unwrap();
    let next = s.create_endpoint(id(0)).unwrap();
    assert_ne!(owner, next);
    for (c, h) in [
        (caller(0), owner),
        (caller(1), replacement),
        (caller(2), grandchild),
    ] {
        assert_eq!(s.transfer(c, h, BASE, 8, true, &mut m), (Status::Denied, 0));
    }
    assert_eq!(
        s.transfer(caller(0), next, BASE, 8, false, &mut m),
        (Status::Again, 0)
    );
}
#[test]
fn bounded_fifo_wrap_full_empty_and_short_receive_preserve_messages() {
    let mut s = space();
    let owner = s.create_endpoint(id(0)).unwrap();
    let send = s.derive(id(0), owner, id(1), Rights::SEND).unwrap();
    let mut m = Bytes::new();
    for round in 0..8 {
        for i in 0..DEPTH {
            m.data.fill((round * DEPTH + i) as u8);
            assert_eq!(
                s.transfer(caller(1), send, BASE, MAX_BYTES, true, &mut m),
                (Status::Ok, MAX_BYTES as u64)
            );
        }
        let before = m.accesses;
        assert_eq!(
            s.transfer(caller(1), send, BASE, 1, true, &mut m),
            (Status::Again, 0)
        );
        assert_eq!(
            s.transfer(caller(0), owner, BASE, MAX_BYTES - 1, false, &mut m),
            (Status::TooSmall, MAX_BYTES as u64)
        );
        assert_eq!(m.accesses, before);
        for i in 0..DEPTH {
            assert_eq!(
                s.transfer(caller(0), owner, BASE, MAX_BYTES, false, &mut m),
                (Status::Ok, MAX_BYTES as u64)
            );
            assert_eq!(m.data, [(round * DEPTH + i) as u8; MAX_BYTES]);
        }
        assert_eq!(
            s.transfer(caller(0), owner, BASE, MAX_BYTES, false, &mut m),
            (Status::Again, 0)
        );
        assert!(
            s.objects[0]
                .value
                .unwrap()
                .queue
                .iter()
                .all(|m| *m == Message::EMPTY)
        );
    }
}
#[test]
fn every_copy_in_fault_leaves_queue_exactly_unchanged() {
    for i in 0..MAX_BYTES {
        let mut s = space();
        let h = s.create_endpoint(id(0)).unwrap();
        let before = s.objects;
        let mut m = Bytes::new();
        m.fault = Some(i);
        assert_eq!(
            s.transfer(caller(0), h, BASE, MAX_BYTES, true, &mut m),
            (Status::Fault, 0)
        );
        assert_eq!(s.objects, before);
        assert_eq!(m.accesses, i + 1);
    }
}
#[test]
fn every_copy_out_fault_reports_prefix_without_consuming_then_retry_succeeds() {
    for i in 0..MAX_BYTES {
        let mut s = space();
        let h = s.create_endpoint(id(0)).unwrap();
        let mut m = Bytes::new();
        assert_eq!(
            s.transfer(caller(0), h, BASE, MAX_BYTES, true, &mut m),
            (Status::Ok, MAX_BYTES as u64)
        );
        let before = s.objects;
        m.data.fill(0);
        m.fault = Some(i);
        assert_eq!(
            s.transfer(caller(0), h, BASE, MAX_BYTES, false, &mut m),
            (Status::Fault, i as u64)
        );
        assert_eq!(s.objects, before);
        assert_eq!(m.data[..i], [0x5a; MAX_BYTES][..i]);
        assert!(m.data[i..].iter().all(|b| *b == 0));
        m.fault = None;
        assert_eq!(
            s.transfer(caller(0), h, BASE, MAX_BYTES, false, &mut m),
            (Status::Ok, MAX_BYTES as u64)
        );
        assert_eq!(m.data, [0x5a; MAX_BYTES]);
        assert_eq!(
            s.transfer(caller(0), h, BASE, 1, false, &mut m),
            (Status::Again, 0)
        );
    }
}
#[test]
fn bounds_reject_zero_overflow_and_kernel_pointers_without_access() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let mut m = Bytes::new();
    for (address, bytes) in [
        (BASE, 0),
        (BASE, MAX_BYTES + 1),
        (0, 1),
        (u64::MAX - 3, 8),
        (crate::virtual_memory::USER_WINDOW_END_EXCLUSIVE - 3, 4),
    ] {
        for send in [false, true] {
            assert_eq!(
                s.transfer(caller(0), h, address, bytes, send, &mut m),
                (Status::Arguments, 0)
            );
        }
    }
    assert_eq!(m.accesses, 0);
}
#[test]
fn cap_and_object_quota_failure_has_no_allocation_or_generation_effect() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    for _ in 0..CAPS {
        s.derive(id(0), h, id(1), Rights::SEND).unwrap();
    }
    let tables = s.tables;
    let objects = s.objects;
    assert_eq!(s.derive(id(0), h, id(1), Rights::SEND), Err(Error::Quota));
    assert_eq!(s.create_endpoint(id(1)), Err(Error::Quota));
    assert_eq!(s.tables, tables);
    assert_eq!(s.objects, objects);
    for _ in 1..ENDPOINTS {
        s.create_endpoint(id(0)).unwrap();
    }
    let tables = s.tables;
    let objects = s.objects;
    assert_eq!(s.create_endpoint(id(2)), Err(Error::Quota));
    assert_eq!(s.tables, tables);
    assert_eq!(s.objects, objects);
}
#[test]
fn capability_and_object_generation_exhaustion_never_wrap() {
    let mut s = space();
    for c in &mut s.tables[0].caps {
        c.generation = u32::MAX;
    }
    assert_eq!(s.create_endpoint(id(0)), Err(Error::Quota));
    assert!(s.objects.iter().all(|o| o.generation == 0));
    for o in &mut s.objects {
        o.generation = u32::MAX;
    }
    assert_eq!(s.create_endpoint(id(1)), Err(Error::Quota));
    assert!(s.tables[1].caps.iter().all(|c| c.generation == 0));
}
#[test]
fn dead_owner_revokes_endpoints_and_queued_data_while_unrelated_peer_survives() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    let survivor = s.create_endpoint(id(1)).unwrap();
    let send = s.derive(id(0), h, id(1), Rights::SEND).unwrap();
    let mut m = Bytes::new();
    assert_eq!(
        s.transfer(caller(1), send, BASE, 8, true, &mut m),
        (Status::Ok, 8)
    );
    s.detach(id(0)).unwrap();
    assert_eq!(s.detach(id(0)), Err(Error::Identity));
    assert_eq!(
        s.transfer(caller(1), send, BASE, 8, true, &mut m),
        (Status::Denied, 0)
    );
    assert_eq!(
        s.transfer(caller(1), survivor, BASE, 8, true, &mut m),
        (Status::Ok, 8)
    );
    assert_eq!(
        s.transfer(caller(1), survivor, BASE, 8, false, &mut m),
        (Status::Ok, 8)
    );
    for i in 1..TASKS {
        s.detach(id(i as u8)).unwrap();
    }
    assert!(s.is_empty());
}
#[test]
fn stale_internal_object_generation_is_denied_even_with_valid_cap_slot() {
    let mut s = space();
    let h = s.create_endpoint(id(0)).unwrap();
    s.objects[0].generation += 1;
    assert_eq!(
        s.transfer(caller(0), h, BASE, 8, true, &mut Bytes::new()),
        (Status::Denied, 0)
    );
}
