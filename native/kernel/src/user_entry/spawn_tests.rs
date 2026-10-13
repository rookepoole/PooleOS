use super::*;
use crate::user_entry::spawn::{Construction, Error as SpawnError};
use std::vec::Vec;

fn setup() -> (Fixture, Construction) {
    let mut f = Fixture::new();
    for h in f.handles() {
        f.manager.free(h).unwrap();
    }
    let mut owner = Construction::new();
    for _ in 0..5 {
        owner.allocate_next(&mut f.manager).unwrap();
    }
    (f, owner)
}

fn setup_program(program: &crate::user_entry::startup::Program<'_>) -> (Fixture, Construction) {
    let mut f = Fixture::new();
    for h in f.handles() {
        f.manager.free(h).unwrap();
    }
    let mut owner = Construction::for_program(program);
    for _ in 0..5 {
        owner.allocate_next(&mut f.manager).unwrap();
    }
    f.image = program
        .image(USER_WINDOW_START + 16 * PAGE_BYTES, f.image.stack_page)
        .unwrap();
    (f, owner)
}

#[test]
fn multipage_program_copies_all_bytes_zero_tail_and_keeps_five_owned_allocations() {
    use crate::user_entry::startup::{Arguments, Program};
    for pages in 2..=crate::user_entry::MAX_CODE_PAGES {
        let code: Vec<u8> = (0..pages * PAGE_BYTES - 3)
            .map(|i| (i % 251) as u8)
            .collect();
        let program = Program::new(&code, PAGE_BYTES as usize + 1).unwrap();
        let args = Arguments::new(&[b"large", b"--check"]).unwrap();
        let (mut f, mut c) = setup_program(&program);
        let handles = c.handles();
        assert_eq!(handles.iter().flatten().count(), 5);
        assert_eq!(f.manager.summary().allocated_pages, 12 + pages);
        let (prepared, startup) = c
            .build_program(
                &mut f.manager,
                &mut f.memory,
                &program,
                &args,
                f.image.code_page,
                f.image.stack_page,
                f.core,
                36,
                None,
            )
            .ok()
            .unwrap();
        let admission = prepared.admission().unwrap();
        assert_eq!(admission.code_end, f.image.code_page + pages * PAGE_BYTES);
        let copied: Vec<u8> = (0..pages)
            .flat_map(|page| {
                f.memory.pages[&(admission.code_physical + page * PAGE_BYTES)]
                    .into_iter()
                    .flat_map(u64::to_le_bytes)
            })
            .collect();
        assert_eq!(&copied[..code.len()], code.as_slice());
        assert!(copied[code.len()..].iter().all(|&v| v == 0));
        assert_eq!(
            startup.registers(admission).unwrap()[0],
            USER_WINDOW_START + 3 * PAGE_BYTES
        );
        for h in handles.into_iter().flatten() {
            assert_eq!(
                f.manager.free(h),
                Err(PhysicalMemoryError::AllocationRetained)
            );
        }
        let _parts = prepared.abort(&mut f.manager, &mut f.memory).ok().unwrap();
        for h in handles.into_iter().flatten() {
            f.manager.free(h).unwrap();
        }
        assert_eq!(f.manager.summary().allocated_pages, 0);
    }
}

#[test]
fn later_code_page_write_failures_retain_and_scrub_entire_construction() {
    use crate::user_entry::startup::{Arguments, Program};
    let code = [0x90; 16381];
    let program = Program::new(&code, 0).unwrap();
    let args = Arguments::new(&[b"large"]).unwrap();
    // Nine erased data pages, followed by code words spanning all four pages.
    for at in [9 * 512 + 512, 9 * 512 + 1024, 9 * 512 + 2047] {
        for corrupt in [false, true] {
            let (mut f, mut c) = setup_program(&program);
            if corrupt {
                f.memory.corrupt_write = Some(at);
            } else {
                f.memory.fail_write = Some(at);
            }
            assert!(
                c.build_program(
                    &mut f.manager,
                    &mut f.memory,
                    &program,
                    &args,
                    f.image.code_page,
                    f.image.stack_page,
                    f.core,
                    36,
                    None
                )
                .is_err()
            );
            retained(&mut f, &c);
            assert_eq!(f.manager.summary().allocated_pages, 16);
            f.memory.corrupt_write = None;
            f.memory.fail_write = Some(f.memory.writes + 512);
            assert!(c.abort(&mut f.manager, &mut f.memory).is_err());
            retained(&mut f, &c);
            f.memory.fail_write = None;
            rollback(&mut f, &mut c);
        }
    }
}

#[test]
fn mismatched_program_allocation_size_rejects_before_copy_and_retains_owner() {
    use crate::user_entry::startup::{Arguments, Program};
    let code = [0x90; 4097];
    let program = Program::new(&code, 0).unwrap();
    let args = Arguments::new(&[]).unwrap();
    let (mut f, mut c) = setup();
    let before = f.memory.writes;
    assert!(
        c.build_program(
            &mut f.manager,
            &mut f.memory,
            &program,
            &args,
            USER_WINDOW_START + 16 * PAGE_BYTES,
            f.image.stack_page,
            f.core,
            36,
            None
        )
        .is_err()
    );
    assert_eq!(f.memory.writes, before);
    retained(&mut f, &c);
    rollback(&mut f, &mut c);
}

#[test]
fn program_construction_copies_full_code_and_arguments_before_admission() {
    use crate::user_entry::startup::{Arguments, Program};
    let (mut f, mut c) = setup();
    let code = [0xcc, 0x90, 0x0f, 0x0b, 0x55, 0x66, 0x77, 0x88, 0x99];
    let program = Program::new(&code, 1).unwrap();
    let args = Arguments::new(&[b"init", b"0", b"--verify"]).unwrap();
    let handles = c.handles();
    let (p, startup) = c
        .build_program(
            &mut f.manager,
            &mut f.memory,
            &program,
            &args,
            f.image.code_page,
            f.image.stack_page,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    let admission = p.admission().unwrap();
    assert_eq!(admission.initial_frame.rip, f.image.code_page + 1);
    let copied: Vec<u8> = f.memory.pages[&admission.code_physical]
        .iter()
        .flat_map(|v| v.to_le_bytes())
        .collect();
    assert_eq!(&copied[..code.len()], &code);
    assert!(copied[code.len()..].iter().all(|&b| b == 0));
    let stack: Vec<u8> = f.memory.pages[&admission.stack_physical]
        .iter()
        .flat_map(|v| v.to_le_bytes())
        .collect();
    assert_eq!(&stack[..args.bytes().len()], args.bytes());
    assert!(stack[args.bytes().len()..].iter().all(|&b| b == 0));
    assert_eq!(
        startup.registers(admission).unwrap(),
        [f.image.stack_page, 112, 1, 0, 0, 0]
    );
    assert!(c.handles().iter().all(Option::is_none));
    for h in handles.into_iter().flatten() {
        assert_eq!(
            f.manager.free(h),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
    let _ = p.abort(&mut f.manager, &mut f.memory).ok().unwrap();
    for h in handles.into_iter().flatten() {
        f.manager.free(h).unwrap();
    }
}

#[test]
fn startup_metadata_rejects_every_changed_admission_field() {
    use crate::user_entry::startup::{Arguments, Program};
    let (mut f, mut c) = setup();
    let p = Program::new(&[0x90], 0).unwrap();
    let args = Arguments::new(&[]).unwrap();
    let (prepared, startup) = c
        .build_program(
            &mut f.manager,
            &mut f.memory,
            &p,
            &args,
            f.image.code_page,
            f.image.stack_page,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    let image = prepared.admission().unwrap();
    for case in 0..10 {
        let mut bad = image;
        match case {
            0 => bad.root_physical += PAGE_BYTES,
            1 => bad.root_generation += 1,
            2 => bad.code_physical += PAGE_BYTES,
            3 => bad.stack_physical += PAGE_BYTES,
            4 => bad.initial_frame.rip += 1,
            5 => bad.initial_frame.cs ^= 1,
            6 => bad.initial_frame.ss ^= 1,
            7 => bad.initial_frame.rsp -= 16,
            8 => bad.initial_frame.rflags ^= 1,
            _ => bad.code_end += PAGE_BYTES,
        }
        assert!(startup.registers(bad).is_err());
    }
    assert!(startup.registers(image).is_ok());
}

#[test]
fn argument_write_failures_retain_whole_owner_and_allow_scrub_retry() {
    use crate::user_entry::startup::{Arguments, Program};
    let code = [0x90; 9];
    let p = Program::new(&code, 1).unwrap();
    let args = Arguments::new(&[b"init", b"0", b"--verify"]).unwrap();
    // Six erased data pages, two code words, then fourteen argument words.
    for at in [3074, 3080, 3087] {
        for corrupt in [false, true] {
            let (mut f, mut c) = setup();
            if corrupt {
                f.memory.corrupt_write = Some(at);
            } else {
                f.memory.fail_write = Some(at);
            }
            assert!(
                c.build_program(
                    &mut f.manager,
                    &mut f.memory,
                    &p,
                    &args,
                    f.image.code_page,
                    f.image.stack_page,
                    f.core,
                    36,
                    None
                )
                .is_err()
            );
            retained(&mut f, &c);
            assert_eq!(f.manager.summary().allocated_pages, 13);
            f.memory.corrupt_write = None;
            f.memory.fail_write = Some(f.memory.writes);
            assert!(c.abort(&mut f.manager, &mut f.memory).is_err());
            retained(&mut f, &c);
            f.memory.fail_write = None;
            rollback(&mut f, &mut c);
        }
    }
}

#[test]
fn program_geometry_and_foreign_owner_reject_before_any_copy() {
    use crate::user_entry::startup::{Arguments, Program};
    let (mut f, mut c) = setup();
    let (mut foreign, _) = setup();
    let p = Program::new(&[0x90], 0).unwrap();
    let args = Arguments::new(&[]).unwrap();
    let before = f.memory.writes;
    assert!(
        c.build_program(
            &mut f.manager,
            &mut f.memory,
            &p,
            &args,
            f.image.code_page,
            f.image.code_page,
            f.core,
            36,
            None
        )
        .is_err()
    );
    assert!(
        c.build_program(
            &mut foreign.manager,
            &mut f.memory,
            &p,
            &args,
            f.image.code_page,
            f.image.stack_page,
            f.core,
            36,
            None
        )
        .is_err()
    );
    assert_eq!(f.memory.writes, before);
    rollback(&mut f, &mut c);
}
fn retained(f: &mut Fixture, c: &Construction) {
    for h in c.handles().into_iter().flatten() {
        assert_eq!(
            f.manager.free(h),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
}
fn rollback(f: &mut Fixture, c: &mut Construction) {
    let handles = c.handles();
    c.abort(&mut f.manager, &mut f.memory).unwrap();
    assert_eq!(f.manager.summary().allocated_pages, 0);
    for h in handles.into_iter().flatten() {
        for p in h.start_page..h.start_page + h.page_count {
            assert_eq!(f.memory.pages[&(p * PAGE_BYTES)], [0; 512]);
        }
    }
    assert!(c.handles().iter().all(Option::is_none));
    c.abort(&mut f.manager, &mut f.memory).unwrap();
    assert_eq!(c.allocate_next(&mut f.manager), Err(SpawnError::State));
}

#[test]
fn partial_allocation_failure_at_each_boundary_retains_then_scrubs() {
    for (limit, successful) in [(3, 0), (4, 1), (5, 2), (9, 3), (12, 4)] {
        let mut p = PhysicalMemoryManager::test_manager(4096, limit, 32);
        let mut c = Construction::new();
        for _ in 0..successful {
            c.allocate_next(&mut p).unwrap();
        }
        assert_eq!(c.allocate_next(&mut p), Err(SpawnError::Allocation));
        let mut memory = Fixture::new().memory;
        for h in c.handles().into_iter().flatten() {
            assert_eq!(p.free(h), Err(PhysicalMemoryError::AllocationRetained));
        }
        c.abort(&mut p, &mut memory).unwrap();
        assert_eq!(p.summary().allocated_pages, 0);
    }
}

#[test]
fn success_transfers_tokens_without_an_unretained_interval() {
    let (mut f, mut c) = setup();
    let handles = c.handles();
    let p = c
        .build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    for h in handles.into_iter().flatten() {
        assert_eq!(
            f.manager.free(h),
            Err(PhysicalMemoryError::AllocationRetained)
        );
    }
    assert!(c.handles().iter().all(Option::is_none));
    assert_eq!(
        c.abort(&mut f.manager, &mut f.memory),
        Err(SpawnError::State)
    );
    assert_eq!(c.allocate_next(&mut f.manager), Err(SpawnError::State));
    let parts = p.abort(&mut f.manager, &mut f.memory).ok().unwrap();
    assert_eq!(parts.stack.page_count, 4);
    for h in handles.into_iter().flatten() {
        f.manager.free(h).unwrap();
    }
}

#[test]
fn invalid_payload_shapes_preserve_owner_without_writes() {
    for case in 0..4 {
        let (mut f, mut c) = setup();
        let payload = [0x90; 4097];
        let (size, delta) = match case {
            0 => (0, 0),
            1 => (4097, 0),
            2 => (1, 1),
            _ => (1, 4096),
        };
        f.image.entry += delta;
        let writes = f.memory.writes;
        assert!(
            c.build(
                &mut f.manager,
                &mut f.memory,
                &payload[..size],
                f.image,
                f.core,
                36,
                None
            )
            .is_err()
        );
        assert_eq!(f.memory.writes, writes);
        retained(&mut f, &c);
        rollback(&mut f, &mut c);
    }
}

#[test]
fn after_effect_write_and_corrupt_readback_at_each_construction_region_roll_back() {
    // data erase, payload, user tables, user leaves, private stack tables,
    // private leaves and root attachment. Final count comes from a clean build.
    let (mut f, mut c) = setup();
    let p = c
        .build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    let count = f.memory.writes;
    drop(p);
    for index in [
        0,
        511,
        512,
        1024,
        3071,
        3072,
        3074,
        3075,
        5122,
        5123,
        5124,
        5125,
        5126,
        count - 2,
        count - 1,
    ] {
        for corrupt in [false, true] {
            let (mut f, mut c) = setup();
            if corrupt {
                f.memory.corrupt_write = Some(index);
            } else {
                f.memory.fail_write = Some(index);
            }
            assert!(
                c.build(
                    &mut f.manager,
                    &mut f.memory,
                    &[0x90; 17],
                    f.image,
                    f.core,
                    36,
                    None
                )
                .is_err(),
                "write {index}/{count} corrupt {corrupt}"
            );
            retained(&mut f, &c);
            f.memory.corrupt_write = None;
            f.memory.fail_write = None;
            rollback(&mut f, &mut c);
        }
    }
}

#[test]
fn read_and_finish_failures_keep_complete_rollback_owner() {
    let (mut f, mut c) = setup();
    let p = c
        .build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None,
        )
        .ok()
        .unwrap();
    let reads = f.memory.reads;
    drop(p);
    for index in [0, 3071, 3072, 3075, 5123, reads - 1] {
        let (mut f, mut c) = setup();
        f.memory.fail_read = Some(index);
        assert!(
            c.build(
                &mut f.manager,
                &mut f.memory,
                &[0x90; 17],
                f.image,
                f.core,
                36,
                None
            )
            .is_err()
        );
        retained(&mut f, &c);
        f.memory.fail_read = None;
        rollback(&mut f, &mut c);
    }
    let (mut f, mut c) = setup();
    f.memory.fail_finish = true;
    assert!(
        c.build(
            &mut f.manager,
            &mut f.memory,
            &[0x90; 17],
            f.image,
            f.core,
            36,
            None
        )
        .is_err()
    );
    retained(&mut f, &c);
    f.memory.fail_finish = false;
    rollback(&mut f, &mut c);
}

#[test]
fn failed_cleanup_never_frees_any_page_and_can_retry() {
    for mode in 0..4 {
        let (mut f, mut c) = setup();
        match mode {
            0 => f.memory.fail_write = Some(700),
            1 => f.memory.corrupt_write = Some(700),
            2 => f.memory.fail_read = Some(700),
            _ => f.memory.fail_finish = true,
        }
        assert!(c.abort(&mut f.manager, &mut f.memory).is_err());
        assert_eq!(f.manager.summary().allocated_pages, 13);
        retained(&mut f, &c);
        f.memory.fail_write = None;
        f.memory.corrupt_write = None;
        f.memory.fail_read = None;
        f.memory.fail_finish = false;
        rollback(&mut f, &mut c);
    }
}

#[test]
fn identical_foreign_manager_handles_never_authorize_memory_access() {
    let (mut f, mut c) = setup();
    let (mut other, _) = setup();
    for h in c.handles().into_iter().flatten() {
        assert!(other.manager.validate_allocation(h).is_ok());
    }
    let writes = f.memory.writes;
    assert_eq!(
        c.allocate_next(&mut other.manager),
        Err(SpawnError::Ownership)
    );
    assert!(
        c.build(
            &mut other.manager,
            &mut f.memory,
            &[0x90],
            f.image,
            f.core,
            36,
            None
        )
        .is_err()
    );
    assert_eq!(
        c.abort(&mut other.manager, &mut f.memory),
        Err(SpawnError::Ownership)
    );
    assert_eq!(f.memory.writes, writes);
    rollback(&mut f, &mut c);
}
