use super::*;
use crate::{
    scheduler::Scheduler,
    user_entry::{
        InitialReturnFrame,
        syscall::{Request, request},
    },
};
use std::vec::Vec;

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
            rip: 0x40000000,
            rsp: 0x40004000,
            cs: 0x33,
            ss: 0x2b,
            rflags: 0x202,
        },
    }
}
fn setup() -> (Space, Caller, u64) {
    let mut space = Space::new();
    space.attach(id(0, 1), image(0)).unwrap();
    space.attach(id(1, 1), image(1)).unwrap();
    let handle = space.grant_console(id(0, 1)).unwrap();
    (space, Caller::new(id(0, 1), image(0)), handle)
}

#[cfg(feature = "development-desktop")]
#[test]
fn local_console_child_authority_is_distinct_caller_bound_and_revoked() {
    let (mut s, c, h) = setup();
    let child = s.desktop_authority(c, h, true).unwrap();
    assert_ne!(h, child);
    assert_eq!(s.desktop_authority(c, child, false), Some(child));
    assert_eq!(s.desktop_authority(c, h, false), None);
    assert_eq!(s.desktop_authority(c, child, true), None);
    let mut ports = Ports::default();
    assert_eq!(
        s.console_byte(c, child, 0, None, &mut ports),
        (Status::Denied, 0)
    );
    assert!(ports.0.is_empty());
    for bad in [
        Caller::new(id(1, 1), image(1)),
        Caller {
            root: c.root + 4096,
            ..c
        },
        Caller { generation: 2, ..c },
        Caller { id: id(0, 2), ..c },
    ] {
        assert_eq!(s.desktop_authority(bad, h, true), None);
        assert_eq!(s.desktop_authority(bad, child, false), None);
    }
    for bad in [0, 1, child + 1, child ^ (1 << 32), u64::MAX] {
        assert_eq!(s.desktop_authority(c, bad, false), None);
    }
    assert_eq!(
        s.derive(c.id, child, id(1, 1), Rights::ALL),
        Err(Error::Denied)
    );
    s.detach(c.id).unwrap();
    assert_eq!(s.desktop_authority(c, child, false), None);
    let new = id(0, 2);
    s.attach(new, image(0)).unwrap();
    let h2 = s.grant_console(new).unwrap();
    let c2 = Caller::new(new, image(0));
    assert_eq!(s.desktop_authority(c2, child, false), None);
    assert_ne!(s.desktop_authority(c2, h2, true), Some(child));
}

#[cfg(feature = "development-desktop")]
#[test]
fn local_console_syscall_shape_rejects_reserved_fields_and_wrong_version() {
    for n in 21..=25 {
        assert!(request(n, 1, 3, 0, 0, 0, 0).is_ok());
        assert_eq!(request(n, 2, 3, 0, 0, 0, 0), Err(Status::Version));
        assert_eq!(request(n, 1, 3, 0, 0, 0, 1), Err(Status::Arguments));
        if n != 24 {
            assert_eq!(request(n, 1, 3, 0, 0, 1, 0), Err(Status::Arguments));
        }
        if matches!(n, 21 | 22 | 25) {
            assert_eq!(request(n, 1, 3, 1, 0, 0, 0), Err(Status::Arguments));
            assert_eq!(request(n, 1, 3, 0, 1, 0, 0), Err(Status::Arguments));
        }
    }
    assert!(request(24, 1, 3, 0, 0, u64::MAX, 0).is_ok());
    assert_eq!(request(26, 1, 0, 0, 0, 0, 0), Err(Status::Unknown));
}
#[derive(Default)]
struct Ports(Vec<(u16, Option<u8>)>);
impl BytePorts for Ports {
    fn read(&mut self, port: u16) -> u8 {
        self.0.push((port, None));
        0xa5
    }
    fn write(&mut self, port: u16, value: u8) {
        self.0.push((port, Some(value)));
    }
}

#[test]
fn console_every_register_and_byte_obeys_the_frozen_effect_mask() {
    let (mut s, c, h) = setup();
    for offset in 0..8 {
        let mut p = Ports::default();
        assert_eq!(
            s.console_byte(c, h, offset, None, &mut p),
            (Status::Ok, 0xa5)
        );
        assert_eq!(p.0, [(BASE + offset as u16, None)]);
        for v in 0..=255 {
            // Independent explicit whitelist, including interrupt and DMA controls.
            let allowed = [
                (1, 0),
                (2, 0),
                (2, 1),
                (2, 7),
                (3, 3),
                (3, 131),
                (4, 0),
                (4, 3),
            ]
            .contains(&(offset, v))
                || offset == 0
                || offset == 7;
            p.0.clear();
            assert_eq!(
                s.console_byte(c, h, offset, Some(v), &mut p),
                (if allowed { Status::Ok } else { Status::Denied }, 0)
            );
            assert_eq!(p.0.len(), usize::from(allowed));
            if allowed {
                assert_eq!(p.0[0], (BASE + offset as u16, Some(v as u8)));
            }
        }
    }
}

#[test]
fn console_forged_handles_callers_roots_and_raw_ports_have_no_effect() {
    let (mut s, c, h) = setup();
    let mut p = Ports::default();
    for bad in [0, 1, h ^ (1 << 32), h + 1, h ^ (1 << 16), u64::MAX] {
        assert_eq!(
            s.console_byte(c, bad, 0, Some(42), &mut p),
            (Status::Denied, 0)
        );
    }
    for bad in [
        Caller::new(id(1, 1), image(1)),
        Caller {
            root: c.root + 4096,
            ..c
        },
        Caller { generation: 2, ..c },
        Caller { id: id(0, 2), ..c },
    ] {
        assert_eq!(s.console_byte(bad, h, 5, None, &mut p), (Status::Denied, 0));
    }
    for offset in [8, 0xe9, 0x3f8, 0x2f8, u64::MAX] {
        assert_eq!(
            s.console_byte(c, h, offset, None, &mut p),
            (Status::Arguments, 0)
        );
    }
    for v in [256, u64::MAX] {
        assert_eq!(
            s.console_byte(c, h, 0, Some(v), &mut p),
            (Status::Arguments, 0)
        );
    }
    assert!(p.0.is_empty());
    assert_eq!(
        s.derive(id(0, 1), h, id(1, 1), Rights::ALL),
        Err(Error::Denied)
    );
    assert_eq!(s.grant_console(id(1, 1)), Err(Error::Quota));
}

#[test]
fn console_revoke_generation_reuse_and_exhaustion_never_resurrect_authority() {
    let (mut s, c, h) = setup();
    s.detach(id(1, 1)).unwrap();
    assert!(s.owns_console(c.id));
    s.detach(c.id).unwrap();
    assert!(s.is_empty());
    let mut p = Ports::default();
    assert_eq!(s.console_byte(c, h, 0, None, &mut p), (Status::Denied, 0));
    let next = id(0, 2);
    s.attach(next, image(0)).unwrap();
    let new = s.grant_console(next).unwrap();
    assert_ne!(h, new);
    assert_eq!(
        s.console_byte(Caller::new(next, image(0)), h, 0, None, &mut p),
        (Status::Denied, 0)
    );
    s.detach(next).unwrap();
    s.console.generation = u32::MAX;
    s.attach(id(0, 3), image(0)).unwrap();
    assert_eq!(s.grant_console(id(0, 3)), Err(Error::Quota));
    assert!(s.console.owner.is_none());
    assert!(p.0.is_empty());
}

#[test]
fn console_atomic_admission_rollback_consumes_handles_but_not_scheduler_state() {
    use super::super::admission::{Member, Step};
    let mut s = Space::new();
    let mut q = Scheduler::new(1).unwrap();
    let before = q.summary();
    let members = [Member {
        id: id(0, 1),
        image: image(0),
        priority: 16,
    }];
    assert!(
        s.admit(
            &mut q,
            &members,
            &[Step::Console { member: 0 }, Step::Console { member: 0 }]
        )
        .is_err()
    );
    assert_eq!(q.summary(), before);
    q.validate().unwrap();
    assert!(s.is_empty());
    assert_eq!(s.console.generation, 1);
    let members = [Member {
        id: id(0, 2),
        ..members[0]
    }];
    let result = s
        .admit(&mut q, &members, &[Step::Console { member: 0 }])
        .unwrap();
    assert_eq!(result.handles[0], 0x200040001);
}

#[test]
fn console_abi_rejects_width_pointer_flags_and_version_confusion() {
    for number in [15, 16] {
        assert_eq!(
            request(number, 1, 3, 7, 0, 0, 0),
            Ok(Request::Console {
                handle: 3,
                offset: 7,
                value: (number == 16).then_some(0)
            })
        );
        for args in [
            (0, 0, 0, 0, 0),
            (1, 8, 0, 0, 0),
            (1, u64::MAX, 0, 0, 0),
            (1, 0, 256, 0, 0),
            (1, 0, 0, 1, 0),
            (1, 0, 0, 0, 1),
        ] {
            assert!(request(number, args.0, 3, args.1, args.2, args.3, args.4).is_err());
        }
    }
    assert_eq!(request(15, 1, 3, 0, 1, 0, 0), Err(Status::Arguments));
    assert!(request(16, 1, 3, 0, 255, 0, 0).is_ok());
}

#[test]
fn console_failed_new_task_admission_preserves_the_existing_owner() {
    use super::super::admission::{Member, Step};
    let mut s = Space::new();
    let mut scheduler = Scheduler::new(1).unwrap();
    let member = |slot| Member {
        id: id(slot, 1),
        image: image(slot),
        priority: 16,
    };
    let first = s
        .admit(&mut scheduler, &[member(0)], &[Step::Console { member: 0 }])
        .unwrap();
    let before = scheduler.summary();
    assert!(
        s.admit(&mut scheduler, &[member(1)], &[Step::Console { member: 0 }])
            .is_err()
    );
    assert_eq!(scheduler.summary(), before);
    assert!(s.owns_console(id(0, 1)));
    assert_eq!(s.console.generation, 1);
    let mut ports = Ports::default();
    assert_eq!(
        s.console_byte(
            Caller::new(id(0, 1), image(0)),
            first.handles[0],
            5,
            None,
            &mut ports
        ),
        (Status::Ok, 0xa5)
    );
    assert_eq!(ports.0.len(), 1);
}
