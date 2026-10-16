use super::*;
use crate::{
    scheduler::Scheduler,
    user_entry::{InitialReturnFrame, syscall::Memory},
};

fn members() -> [admission::Member; 4] {
    core::array::from_fn(|i| admission::Member {
        id: TaskId::new(i as u8, 1).unwrap(),
        priority: 16,
        image: ImageAdmission {
            root_physical: 0x100000 + i as u64 * 4096,
            root_generation: 1,
            code_physical: 0x200000 + i as u64 * 4096,
            code_end: 0x40001000,
            stack_physical: 0x300000 + i as u64 * 4096,
            initial_frame: InitialReturnFrame {
                rip: 0x40000000,
                rsp: 0x40004000,
                cs: 0x33,
                ss: 0x2b,
                rflags: 0x202,
            },
        },
    })
}
const ADDRESS: u64 = 0x40004000;
struct Bytes([u8; 96]);
impl Memory for Bytes {
    fn read(&mut self, at: u64) -> Result<u8, Status> {
        self.0
            .get(at.wrapping_sub(ADDRESS) as usize)
            .copied()
            .ok_or(Status::Fault)
    }
    fn write(&mut self, at: u64, byte: u8) -> Result<(), Status> {
        *self
            .0
            .get_mut(at.wrapping_sub(ADDRESS) as usize)
            .ok_or(Status::Fault)? = byte;
        Ok(())
    }
}
fn caller(m: admission::Member) -> Caller {
    Caller::new(m.id, m.image)
}

#[cfg(feature = "development-windows")]
#[test]
fn window_endpoint_is_distinct_and_apps_receive_no_display_or_receive_authority() {
    let m = members();
    let mut s = Space::new();
    let mut scheduler = Scheduler::new(1).unwrap();
    let a = s.admit_window_session(&mut scheduler, &m).unwrap();
    assert_eq!(a.count, 9);
    assert_eq!(a.handles[8], 0x100010003);
    let own = s.resolve(2, a.handles[8], Rights::RECEIVE).unwrap();
    let console = s.resolve(2, a.handles[2], Rights::RECEIVE).unwrap();
    assert_ne!(own.object, console.object);
    let child = capacity_members()[4];
    s.attach(child.id, child.image).unwrap();
    let send = s
        .derive(m[2].id, a.handles[8], child.id, Rights::SEND)
        .unwrap();
    assert!(s.resolve(4, send, Rights::SEND).is_ok());
    assert!(s.resolve(4, send, Rights::RECEIVE).is_err());
    assert!(s.derive(child.id, send, m[3].id, Rights::SEND).is_err());
    assert_eq!(s.desktop_authority(caller(child), a.handles[7], true), None);
    s.detach(m[2].id).unwrap();
    assert!(s.resolve(4, send, Rights::SEND).is_err());
}
#[cfg(feature = "development-windows")]
#[test]
fn last_window_endpoint_exhaustion_rolls_back_console_lease_and_scheduler() {
    let m = members();
    let mut s = Space::new();
    let mut scheduler = Scheduler::new(1).unwrap();
    for i in 3..ENDPOINTS {
        s.objects[i].generation = u32::MAX;
    }
    assert!(s.admit_window_session(&mut scheduler, &m).is_err());
    assert!(s.is_empty());
    assert_eq!(scheduler.summary().runnable_count, 0);
    for member in m {
        assert!(!s.owns_console(member.id));
    }
}

fn capacity_members() -> [admission::Member; 6] {
    core::array::from_fn(|i| {
        let mut m = members()[0];
        m.id = TaskId::new(i as u8, 1).unwrap();
        m.image.root_physical += i as u64 * 4096;
        m.image.code_physical += i as u64 * 4096;
        m.image.stack_physical += i as u64 * 4096;
        m
    })
}

#[test]
fn file_session_grants_are_read_only_routes_without_device_or_transfer_authority() {
    let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), members());
    let a = s.admit_file_session(&mut scheduler, &m).unwrap();
    assert_eq!(a.count, 8);
    assert_eq!(
        &a.handles[..8],
        &[
            0x100010001,
            0x100010001,
            0x100010001,
            0x100010001,
            0x100010002,
            0x100010002,
            0x100010003,
            0x100040001
        ]
    );
    assert_eq!(scheduler.summary().runnable_count, 4);
    for i in 0..4 {
        assert_eq!(s.owns_console(m[i].id), i == 2);
    }
    for (i, h) in [(0, a.handles[1]), (3, a.handles[6])] {
        let cap = s.resolve(i, h, Rights::SEND).unwrap();
        assert_eq!(s.objects[cap.object.slot].value.unwrap().owner, m[1].id);
        assert!(s.resolve(i, h, Rights::RECEIVE).is_err());
        assert!(s.derive(m[i].id, h, m[2].id, Rights::SEND).is_err());
        assert!(s.resolve(i, h + (1 << 32), Rights::SEND).is_err());
    }
    assert!(s.resolve(1, 0x100010002, Rights::SEND).is_err());
    assert!(s.resolve(2, 0x100010003, Rights::SEND).is_err());
    scheduler.validate().unwrap();
}
#[test]
fn file_session_admission_failure_is_atomic() {
    let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), members());
    s.console.generation = u32::MAX;
    let before = scheduler.summary();
    assert!(s.admit_file_session(&mut scheduler, &m).is_err());
    assert_eq!(scheduler.summary(), before);
    assert!(s.is_empty());
    assert!(m.iter().all(|member| !s.owns_console(member.id)));
}

#[test]
fn six_member_capacity_preserves_pair_and_device_authority() {
    let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), capacity_members());
    let a = s.admit_console_capacity(&mut scheduler, &m).unwrap();
    assert_eq!(a.count, 13);
    assert_eq!(
        &a.handles[9..13],
        &[0x100010001, 0x100010001, 0x100010002, 0x100010002]
    );
    assert_eq!(scheduler.summary().runnable_count, 6);
    for i in 0..6 {
        assert_eq!(s.owns_console(m[i].id), i == 2);
        let own = s.resolve(i, 0x100010001, Rights::RECEIVE).unwrap();
        let send = s.resolve(i, 0x100010002, Rights::SEND).unwrap();
        assert_eq!(s.objects[own.object.slot].value.unwrap().owner, m[i].id);
        assert_eq!(
            s.objects[send.object.slot].value.unwrap().owner,
            m[i ^ 1].id
        );
        assert!(s.resolve(i, 0x100010002, Rights::RECEIVE).is_err());
        assert!(
            s.derive(m[i].id, 0x100010002, m[(i + 2) % 6].id, Rights::SEND)
                .is_err()
        );
    }
    let mut wire = Bytes([37; 96]);
    assert_eq!(
        s.transfer(caller(m[4]), a.handles[11], ADDRESS, 32, true, &mut wire),
        (Status::Ok, 32)
    );
    assert_eq!(
        s.transfer(caller(m[5]), a.handles[10], ADDRESS, 32, false, &mut wire),
        (Status::Ok, 32)
    );
    for member in m {
        s.detach(member.id).unwrap();
    }
    assert!(s.is_empty());
}

#[test]
fn six_member_capacity_rollback_covers_every_endpoint_slot_and_device_lease() {
    let m = capacity_members();
    for start in 0..ENDPOINTS {
        let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
        for offset in 0..3 {
            s.objects[(start + offset) % ENDPOINTS].generation = u32::MAX;
        }
        let before = scheduler.summary();
        assert!(s.admit_console_capacity(&mut scheduler, &m).is_err());
        assert_eq!(scheduler.summary(), before);
        assert!(s.is_empty());
        assert!(m.iter().all(|v| !s.owns_console(v.id)));
        assert!(m.iter().all(|v| s.attach(v.id, v.image).is_err()));
    }
}

#[test]
fn four_member_grants_are_separate_pairs_and_only_service_owns_device() {
    let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), members());
    let a = s.admit_console_session(&mut scheduler, &m).unwrap();
    assert_eq!(a.count, 9);
    assert_eq!(
        &a.handles[..9],
        &[
            0x100010001,
            0x100010001,
            0x100010002,
            0x100010002,
            0x100010001,
            0x100010001,
            0x100010002,
            0x100010002,
            0x100040001
        ]
    );
    for i in 0..4 {
        assert_eq!(s.owns_console(m[i].id), i == 2);
    }
    let mut bytes = Bytes([42; 96]);
    for i in 0..4 {
        assert_eq!(
            s.transfer(caller(m[i]), a.handles[0], ADDRESS, 32, true, &mut bytes),
            (Status::Ok, 32)
        );
        // The same numeric handle resolves only within the caller's table, never another pair.
        let own = s.resolve(i, a.handles[0], Rights::RECEIVE).unwrap();
        let send = s.resolve(i, a.handles[2], Rights::SEND).unwrap();
        assert_eq!(s.objects[own.object.slot].value.unwrap().owner, m[i].id);
        assert_eq!(
            s.objects[send.object.slot].value.unwrap().owner,
            m[i ^ 1].id
        );
        assert_eq!(
            s.resolve(i, a.handles[2], Rights::RECEIVE),
            Err(Error::Denied)
        );
        assert_eq!(
            s.derive(m[i].id, a.handles[2], m[(i + 2) % 4].id, Rights::SEND),
            Err(Error::Denied)
        );
        let mut bad = caller(m[i]);
        bad.root = m[(i + 2) % 4].image.root_physical;
        assert_eq!(
            s.transfer(bad, a.handles[2], ADDRESS, 32, true, &mut bytes),
            (Status::Denied, 0)
        );
    }
    scheduler.validate().unwrap();
}

#[test]
fn queued_plain_ack_survives_sender_retirement_but_new_sends_do_not() {
    let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), members());
    let a = s.admit_console_session(&mut scheduler, &m).unwrap();
    let mut bytes = Bytes([7; 96]);
    for _ in 0..DEPTH {
        assert_eq!(
            s.transfer(caller(m[2]), a.handles[6], ADDRESS, 32, true, &mut bytes),
            (Status::Ok, 32)
        );
    }
    assert_eq!(
        s.transfer(caller(m[2]), a.handles[6], ADDRESS, 32, true, &mut bytes),
        (Status::Again, 0)
    );
    s.detach(m[2].id).unwrap();
    assert!(!s.owns_console(m[2].id));
    assert_eq!(
        s.transfer(caller(m[3]), a.handles[7], ADDRESS, 32, true, &mut bytes),
        (Status::Denied, 0)
    );
    for _ in 0..DEPTH {
        assert_eq!(
            s.message(
                caller(m[3]),
                a.handles[5],
                ADDRESS,
                64,
                reply::Operation::Receive,
                &mut bytes
            ),
            (Status::Ok, 64)
        );
        assert_eq!(&bytes.0[..8], &2u64.to_le_bytes());
        assert_eq!(&bytes.0[8..16], &1u64.to_le_bytes());
        assert_eq!(&bytes.0[16..24], &[0; 8]);
        assert_eq!(&bytes.0[24..32], &32u64.to_le_bytes());
        assert_eq!(&bytes.0[32..64], &[7; 32]);
    }
    assert_eq!(
        s.message(
            caller(m[3]),
            a.handles[5],
            ADDRESS,
            64,
            reply::Operation::Receive,
            &mut bytes
        ),
        (Status::Again, 0)
    );
    // Absence here is not EOF: the receiver still owns its mailbox.
    for i in [3, 0, 1] {
        s.detach(m[i].id).unwrap();
    }
    assert!(s.is_empty());
}

#[test]
fn four_member_admission_failure_does_not_publish_partial_scheduler_or_objects() {
    let m = members();
    for exhausted in 0..4 {
        let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
        // Leave too few allocatable endpoint slots for the final pair.
        for slot in &mut s.objects[4..] {
            slot.generation = u32::MAX;
        }
        s.objects[exhausted].generation = u32::MAX;
        let before = scheduler.summary();
        assert!(s.admit_console_session(&mut scheduler, &m).is_err());
        assert!(s.is_empty());
        assert_eq!(scheduler.summary(), before);
        scheduler.validate().unwrap();
        for member in m {
            assert!(s.attach(member.id, member.image).is_err());
        }
    }
}

#[test]
fn four_member_duplicate_identity_and_retired_generations_cannot_readmit() {
    let (mut s, mut scheduler, mut m) = (Space::new(), Scheduler::new(1).unwrap(), members());
    m[3] = m[2];
    assert!(s.admit_console_session(&mut scheduler, &m).is_err());
    assert!(s.is_empty());
    m = members();
    s.admit_console_session(&mut scheduler, &m).unwrap();
    for member in m {
        s.detach(member.id).unwrap();
    }
    assert!(s.is_empty());
    let mut fresh = Scheduler::new(1).unwrap();
    assert!(s.admit_console_session(&mut fresh, &m).is_err());
    assert!(s.is_empty());
}

#[test]
fn tracked_console_completion_survives_service_retirement_and_full_client_mailbox() {
    use crate::capability_ipc::{reply::Operation as Reply, request::Operation as Request};
    let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), members());
    let a = s.admit_console_session(&mut scheduler, &m).unwrap();
    let mut bytes = Bytes([7; 96]);
    let (status, request) = s.request_operation(
        caller(m[3]),
        a.handles[7],
        ADDRESS,
        32,
        Request::Begin,
        &mut bytes,
    );
    assert_eq!(status, Status::Ok);
    assert_eq!(
        s.message(
            caller(m[2]),
            a.handles[4],
            ADDRESS,
            64,
            Reply::Receive,
            &mut bytes
        ),
        (Status::Ok, 64)
    );
    let token = u64::from_le_bytes(bytes.0[16..24].try_into().unwrap());
    for _ in 0..DEPTH {
        assert_eq!(
            s.transfer(caller(m[2]), a.handles[6], ADDRESS, 32, true, &mut bytes),
            (Status::Ok, 32)
        );
    }
    bytes.0[..32].fill(42);
    assert_eq!(
        s.message(caller(m[2]), token, ADDRESS, 32, Reply::Reply, &mut bytes),
        (Status::Ok, 32)
    );
    s.detach(m[2].id).unwrap();
    assert_eq!(
        s.request_operation(
            caller(m[3]),
            request,
            ADDRESS,
            64,
            Request::Take,
            &mut bytes
        ),
        (Status::Ok, 64)
    );
    assert_eq!(&bytes.0[..8], &2u64.to_le_bytes());
    assert_eq!(&bytes.0[8..16], &1u64.to_le_bytes());
    assert_eq!(&bytes.0[16..24], &[0; 8]);
    assert_eq!(&bytes.0[32..64], &[42; 32]);
    assert_eq!(
        s.request_operation(
            caller(m[3]),
            request,
            ADDRESS,
            64,
            Request::Take,
            &mut bytes
        ),
        (Status::Denied, 0)
    );
}

#[test]
fn tracked_console_death_is_durable_before_or_after_delivery_without_mailbox_space() {
    use crate::capability_ipc::{reply::Operation as Reply, request::Operation as Request};
    for delivered in [false, true] {
        let (mut s, mut scheduler, m) = (Space::new(), Scheduler::new(1).unwrap(), members());
        let a = s.admit_console_session(&mut scheduler, &m).unwrap();
        let mut bytes = Bytes([7; 96]);
        let (status, request) = s.request_operation(
            caller(m[3]),
            a.handles[7],
            ADDRESS,
            32,
            Request::Begin,
            &mut bytes,
        );
        assert_eq!(status, Status::Ok);
        if delivered {
            assert_eq!(
                s.message(
                    caller(m[2]),
                    a.handles[4],
                    ADDRESS,
                    64,
                    Reply::Receive,
                    &mut bytes
                ),
                (Status::Ok, 64)
            );
        }
        for _ in 0..DEPTH {
            assert_eq!(
                s.transfer(caller(m[2]), a.handles[6], ADDRESS, 32, true, &mut bytes),
                (Status::Ok, 32)
            );
        }
        s.detach(m[2].id).unwrap();
        let before = bytes.0;
        assert_eq!(
            s.request_operation(
                caller(m[3]),
                request,
                ADDRESS,
                64,
                Request::Take,
                &mut bytes
            ),
            (Status::Revoked, 0)
        );
        assert_eq!(bytes.0, before);
        assert_eq!(
            s.request_operation(
                caller(m[3]),
                request,
                ADDRESS,
                64,
                Request::Take,
                &mut bytes
            ),
            (Status::Denied, 0)
        );
        assert_eq!(
            s.transfer(caller(m[0]), a.handles[2], ADDRESS, 32, true, &mut bytes),
            (Status::Ok, 32)
        );
        assert_eq!(
            s.transfer(caller(m[1]), a.handles[1], ADDRESS, 32, false, &mut bytes),
            (Status::Ok, 32)
        );
        for i in [3, 0, 1] {
            s.detach(m[i].id).unwrap();
        }
        assert!(s.is_empty());
    }
}
