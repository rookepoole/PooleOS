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
    for exhausted in 0..ENDPOINTS {
        let (mut s, mut scheduler) = (Space::new(), Scheduler::new(1).unwrap());
        // Leave too few allocatable endpoint slots for the final pair.
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
