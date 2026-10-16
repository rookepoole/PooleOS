use super::*;
use crate::user_entry::startup::{Arguments, Startup};
use crate::user_entry::task::arguments::Error as ArgumentError;

fn arguments(handle: &[u8]) -> Arguments {
    Arguments::new(&[
        b"text-app",
        handle,
        b"0000000100000003",
        b"0000000100010002",
        b"0000000100000001",
    ])
    .unwrap()
}

fn seeded(args: &Arguments) -> (Setup, Startup) {
    let mut s = setup();
    s.memory.prepare_page(s.image.stack_physical).unwrap();
    for (index, word) in args.bytes().chunks_exact(8).enumerate() {
        s.memory
            .write_entry(
                s.image.stack_physical,
                index,
                u64::from_le_bytes(word.try_into().unwrap()),
            )
            .unwrap();
    }
    let startup = Startup::bind(s.image, args);
    (s, startup)
}

#[test]
fn late_startup_handoff_changes_only_the_bound_block_and_preserves_entry_registers() {
    for args in [
        Arguments::new(&[]).unwrap(),
        arguments(b"0000000100010001"),
        Arguments::new(&[&[b'a'; 415]]).unwrap(),
    ] {
        let replacement = if args.bytes().len() == 96 {
            Arguments::new(&[]).unwrap()
        } else if args.bytes().len() == 512 {
            Arguments::new(&[&[b'z'; 415]]).unwrap()
        } else {
            arguments(b"000000FF00010001")
        };
        let (mut s, startup) = seeded(&args);
        let registers = startup.registers(s.image).unwrap();
        let mut expected_pages = s.memory.pages.clone();
        for (i, word) in replacement.bytes().chunks_exact(8).enumerate() {
            expected_pages.get_mut(&s.image.stack_physical).unwrap()[i] =
                u64::from_le_bytes(word.try_into().unwrap());
        }
        let before = s.memory.writes;
        let (mut slot, control, id) = task_slot(s.owner);
        slot.replace_startup_arguments(id, &startup, &args, &replacement, &mut s.memory)
            .unwrap();
        assert_eq!(s.memory.pages, expected_pages);
        assert_eq!(s.memory.writes - before, args.bytes().len() / 8);
        assert_eq!(startup.registers(s.image).unwrap(), registers);
        assert_eq!(slot.state(id), Ok(task::State::Prepared));
        assert_eq!(slot.runtime(id), Ok(task::Runtime::default()));
        assert_eq!(control.borrow().entries, 0);
        assert!(s.machine.borrow().writes.is_empty());
        retained(&mut s.manager, &s.handles);
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        slot.run(id).unwrap();
        slot.reclaim(id, &mut s.manager, &mut s.memory).unwrap();
        assert_eq!(s.manager.summary().allocated_pages, 0);
    }
}

#[test]
fn startup_handoff_rejects_wrong_identity_image_and_lengths_before_memory_access() {
    let old = arguments(b"0000000100010001");
    let next = arguments(b"0000000200010001");
    let (mut s, startup) = seeded(&old);
    let mut other = s.image;
    other.stack_physical += PAGE_BYTES;
    let wrong = Startup::bind(other, &old);
    let short = Arguments::new(&[]).unwrap();
    let (mut slot, _, id) = task_slot(s.owner);
    let reads = s.memory.reads;
    let writes = s.memory.writes;
    assert_eq!(
        slot.replace_startup_arguments(
            TaskId::new(0, 2).unwrap(),
            &startup,
            &old,
            &next,
            &mut s.memory
        ),
        Err(task::Error::Identity)
    );
    for (metadata, expected, replacement) in [
        (&wrong, &old, &next),
        (&startup, &short, &next),
        (&startup, &old, &short),
    ] {
        assert_eq!(
            slot.replace_startup_arguments(id, metadata, expected, replacement, &mut s.memory),
            Err(task::Error::Arguments(ArgumentError::Metadata))
        );
        assert_eq!(slot.state(id), Ok(task::State::Prepared));
    }
    assert_eq!((s.memory.reads, s.memory.writes), (reads, writes));
    slot.replace_startup_arguments(id, &startup, &old, &next, &mut s.memory)
        .unwrap();
}

#[test]
fn mismatched_original_word_never_writes_and_quarantines_retained_owner() {
    let old = arguments(b"0000000100010001");
    let next = arguments(b"0000000200010001");
    for index in 0..old.bytes().len() / 8 {
        let (mut s, startup) = seeded(&old);
        s.memory.pages.get_mut(&s.image.stack_physical).unwrap()[index] ^= 1;
        let (mut slot, control, id) = task_slot(s.owner);
        let before = s.memory.writes;
        assert_eq!(
            slot.replace_startup_arguments(id, &startup, &old, &next, &mut s.memory),
            Err(task::Error::Arguments(ArgumentError::Contents))
        );
        assert_eq!(s.memory.writes, before);
        assert_eq!(slot.state(id), Ok(task::State::Quarantined));
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert!(slot.cancel_prepared(id).is_err());
        assert!(
            slot.replace_startup_arguments(id, &startup, &old, &next, &mut s.memory)
                .is_err()
        );
        retained(&mut s.manager, &s.handles);
        slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        assert_eq!(slot.state(id), Err(task::Error::Missing));
        assert_eq!(control.borrow().entries, 0);
    }
}

#[test]
fn every_startup_word_read_write_and_readback_failure_blocks_entry_without_losing_owner() {
    let old = arguments(b"0000000100010001");
    let next = arguments(b"0000000200010001");
    let words = old.bytes().len() / 8;
    for mode in 0..4 {
        for index in 0..words {
            let (mut s, startup) = seeded(&old);
            match mode {
                0 => s.memory.fail_read = Some(s.memory.reads + index),
                1 => s.memory.fail_write = Some(s.memory.writes + index),
                2 => s.memory.corrupt_write = Some(s.memory.writes + index),
                _ => s.memory.fail_read = Some(s.memory.reads + words + index),
            }
            let (mut slot, control, id) = task_slot(s.owner);
            assert!(
                slot.replace_startup_arguments(id, &startup, &old, &next, &mut s.memory)
                    .is_err()
            );
            assert_eq!(slot.state(id), Ok(task::State::Quarantined));
            assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
            assert!(slot.run(id).is_err());
            assert!(slot.outcome(id).is_err());
            retained(&mut s.manager, &s.handles);
            assert_eq!(control.borrow().entries, 0);
            assert!(s.machine.borrow().writes.is_empty());
            s.memory.fail_read = None;
            s.memory.fail_write = None;
            s.memory.corrupt_write = None;
            slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
            assert_eq!(slot.state(id), Err(task::Error::Missing));
        }
    }
}

struct FinishMemory<'a> {
    memory: &'a mut Memory,
    finish: usize,
    fail: usize,
}
impl TableMemory for FinishMemory<'_> {
    fn prepare_page(&mut self, p: u64) -> Result<(), vm::Error> {
        self.memory.prepare_page(p)
    }
    fn read_entry(&mut self, p: u64, i: usize) -> Result<u64, vm::Error> {
        self.memory.read_entry(p, i)
    }
    fn write_entry(&mut self, p: u64, i: usize, v: u64) -> Result<(), vm::Error> {
        self.memory.write_entry(p, i, v)
    }
    fn finish(&mut self) -> Result<(), vm::Error> {
        self.finish += 1;
        self.memory.finish()?;
        if self.finish == self.fail {
            Err(vm::Error::MemoryAccess)
        } else {
            Ok(())
        }
    }
    fn physical_write_count(&self) -> u64 {
        self.memory.physical_write_count()
    }
    fn temporary_pte_write_count(&self) -> u64 {
        0
    }
    fn hardware_invalidation_count(&self) -> u64 {
        0
    }
}

#[test]
fn startup_finish_failures_and_post_write_mutation_are_quarantined() {
    let old = arguments(b"0000000100010001");
    let next = arguments(b"0000000200010001");
    for mode in 0..3 {
        let (mut s, startup) = seeded(&old);
        if mode == 0 {
            s.memory.corrupt_user_on_finish = Some(s.image.stack_physical);
        }
        let (mut slot, _, id) = task_slot(s.owner);
        let mut memory = FinishMemory {
            memory: &mut s.memory,
            finish: 0,
            fail: mode,
        };
        assert!(
            slot.replace_startup_arguments(id, &startup, &old, &next, &mut memory)
                .is_err()
        );
        assert_eq!(slot.state(id), Ok(task::State::Quarantined));
        retained(&mut s.manager, &s.handles);
        slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
    }
}

#[test]
fn startup_handoff_rejects_active_suspended_waiting_terminal_and_reclaimed_images() {
    let args = arguments(b"0000000100010001");
    for mode in 0..6 {
        let (mut s, startup) = seeded(&args);
        let (mut slot, control, id) = task_slot(s.owner);
        if mode == 0 {
            slot.cancel_prepared(id).unwrap();
        } else {
            if mode == 3 {
                let mut ipc = crate::capability_ipc::Space::new();
                ipc.attach(id, s.image).unwrap();
                let endpoint = ipc.create_endpoint(id).unwrap();
                let crate::capability_ipc::wait::Admission::Pending(ticket) = ipc
                    .prepare_wait(
                        crate::capability_ipc::Caller::new(id, s.image),
                        endpoint,
                        crate::capability_ipc::wait::Readiness::Readable,
                    )
                    .unwrap()
                else {
                    panic!()
                };
                control.borrow_mut().wait = Some(ticket);
            }
            slot.activate(id, &s.manager, &mut s.memory).unwrap();
            if mode == 2 || mode == 3 {
                slot.run_slice(id).unwrap();
            }
            if mode >= 4 {
                slot.run(id).unwrap();
            }
            if mode == 5 {
                slot.reclaim(id, &mut s.manager, &mut s.memory).unwrap();
            }
        }
        let state = slot.state(id);
        let before = (s.memory.reads, s.memory.writes);
        assert!(
            slot.replace_startup_arguments(id, &startup, &args, &args, &mut s.memory)
                .is_err()
        );
        assert_eq!(slot.state(id), state);
        assert_eq!((s.memory.reads, s.memory.writes), before);
    }
}

#[test]
fn actual_admission_handles_are_written_before_the_owned_application_can_enter() {
    use crate::capability_ipc::{
        Caller, Rights, Space,
        admission::{Member, Step},
    };
    use crate::user_entry::syscall::Status;
    let old = arguments(b"0000000100010001");
    let (mut s, startup) = seeded(&old);
    let (mut slot, control, child) = task_slot(s.owner);
    let mut space = Space::new();
    let mut scheduler = crate::scheduler::Scheduler::new(1).unwrap();
    let shell = TaskId::new(3, 1).unwrap();
    let files = TaskId::new(1, 1).unwrap();
    let shell_image = ImageAdmission {
        root_physical: 0x800000,
        ..s.image
    };
    let file_image = ImageAdmission {
        root_physical: 0x900000,
        ..s.image
    };
    space
        .admit(
            &mut scheduler,
            &[
                Member {
                    id: shell,
                    image: shell_image,
                    priority: 16,
                },
                Member {
                    id: files,
                    image: file_image,
                    priority: 16,
                },
            ],
            &[],
        )
        .unwrap();
    let endpoint = space.create_endpoint(shell).unwrap();
    let file_endpoint = space.create_endpoint(files).unwrap();
    let factory = space.grant_launch(shell, 1, child.slot).unwrap();
    let caller = Caller::new(shell, shell_image);
    assert_eq!(space.request_launch(caller, factory, 1), (Status::Again, 0));
    let permit = space.claim_launch().unwrap();
    let result = space
        .admit_launch(
            &permit,
            &mut scheduler,
            Member {
                id: child,
                image: s.image,
                priority: 16,
            },
            &[
                Step::Inherit {
                    source: shell,
                    handle: endpoint,
                    member: 0,
                    rights: Rights::SEND,
                },
                Step::Inherit {
                    source: files,
                    handle: file_endpoint,
                    member: 0,
                    rights: Rights::SEND,
                },
            ],
        )
        .unwrap();
    assert_eq!(result.count, 3);
    let control_handle = std::format!("{:016X}", result.handles[0]);
    let file_handle = std::format!("{:016X}", result.handles[1]);
    let replacement = Arguments::new(&[
        b"text-app",
        control_handle.as_bytes(),
        b"0000000100000003",
        file_handle.as_bytes(),
        b"0000000100000001",
    ])
    .unwrap();
    slot.replace_startup_arguments(child, &startup, &old, &replacement, &mut s.memory)
        .unwrap();
    let copied: std::vec::Vec<u8> = s.memory.pages[&s.image.stack_physical]
        .iter()
        .flat_map(|v| v.to_le_bytes())
        .collect();
    assert_eq!(&copied[..replacement.bytes().len()], replacement.bytes());
    assert_eq!(
        space.request_launch(caller, factory, 1),
        (Status::Ok, result.handles[2])
    );
    assert_eq!(control.borrow().entries, 0);
    assert_eq!(scheduler.summary().dispatch_count, 0);
    assert_eq!(slot.state(child), Ok(task::State::Prepared));
    retained(&mut s.manager, &s.handles);
}
