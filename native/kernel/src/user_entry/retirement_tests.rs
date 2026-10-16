use super::*;

#[test]
fn reclaim_erases_all_owned_pages_and_preserves_boot_pages_and_outcome() {
    let mut s = setup();
    let owned = s.handles;
    let boot: std::collections::BTreeMap<_, _> = s
        .memory
        .pages
        .iter()
        .filter(|(a, _)| {
            !owned.iter().any(|h| {
                **a >= h.start_page * PAGE_BYTES && **a < (h.start_page + h.page_count) * PAGE_BYTES
            })
        })
        .map(|(&a, &v)| (a, v))
        .collect();
    let (mut slot, control, id) = task_slot(s.owner);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    let outcome = slot.run(id).unwrap();
    assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
    assert_eq!(s.manager.summary().allocated_pages, 0);
    for h in owned {
        for page in h.start_page..h.start_page + h.page_count {
            assert_eq!(s.memory.pages[&(page * PAGE_BYTES)], [0; 512]);
        }
    }
    for (a, v) in boot {
        assert_eq!(s.memory.pages[&a], v);
    }
    assert_eq!(control.borrow().revocations, 1);
    assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    assert_eq!(
        slot.reclaim(id, &mut s.manager, &mut s.memory),
        Err(task::Error::Missing)
    );
    assert_eq!(slot.run(id), Err(task::Error::Missing));
}

#[test]
fn every_page_boundary_failure_retains_ownership_and_retries_without_reentry() {
    for page in 0..13 {
        for word in [0, 511] {
            for mode in 0..3 {
                let mut s = setup();
                let (mut slot, control, id) = task_slot(s.owner);
                slot.activate(id, &s.manager, &mut s.memory).unwrap();
                let outcome = slot.run(id).unwrap();
                let offset = page * 512 + word;
                match mode {
                    0 => s.memory.fail_write = Some(s.memory.writes + offset),
                    1 => s.memory.fail_read = Some(s.memory.reads + offset),
                    _ => s.memory.corrupt_write = Some(s.memory.writes + offset),
                }
                assert!(matches!(
                    slot.reclaim(id, &mut s.manager, &mut s.memory),
                    Err(task::Error::Reclamation(_))
                ));
                assert_eq!(slot.state(id), Ok(task::State::Reclaiming));
                assert_eq!(slot.outcome(id), Ok(outcome));
                assert_eq!(slot.reclaim_remaining_pages(id), Ok(13));
                assert_eq!(s.manager.summary().allocated_pages, 13);
                retained(&mut s.manager, &s.handles);
                assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
                assert!(slot.run(id).is_err());
                assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
                s.memory.fail_write = None;
                s.memory.fail_read = None;
                s.memory.corrupt_write = None;
                assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
                assert_eq!(control.borrow().entries, 1);
                assert_eq!(control.borrow().revocations, 1);
                assert_eq!(s.manager.summary().allocated_pages, 0);
            }
        }
    }
}

#[test]
fn failed_finish_and_wrong_manager_cannot_release_or_mutate_other_memory() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    let outcome = slot.run(id).unwrap();
    s.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut s.manager, &mut s.memory).is_err());
    retained(&mut s.manager, &s.handles);
    let mut other = setup();
    let writes = s.memory.writes;
    assert_eq!(
        slot.reclaim(id, &mut other.manager, &mut s.memory),
        Err(task::Error::Reclamation(
            crate::user_entry::retirement::Error::Ownership
        ))
    );
    assert_eq!(s.memory.writes, writes);
    assert_eq!(other.manager.summary().allocated_pages, 13);
    s.memory.fail_finish = false;
    assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
}

#[test]
fn revoke_and_after_effect_root_restore_failures_keep_the_cpu_owner() {
    for revoke in [true, false] {
        let mut s = setup();
        let (mut slot, control, id) = task_slot(s.owner);
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        let outcome = slot.run(id).unwrap();
        control.borrow_mut().fail_revoke = revoke;
        s.machine.borrow_mut().write_error = !revoke;
        let writes = s.memory.writes;
        assert!(matches!(
            slot.reclaim(id, &mut s.manager, &mut s.memory),
            Err(task::Error::Cpu(_))
        ));
        assert_eq!(slot.state(id), Ok(task::State::Terminated));
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
        control.borrow_mut().fail_revoke = false;
        s.machine.borrow_mut().write_error = false;
        assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
        assert_eq!(s.machine.borrow().writes.len(), if revoke { 2 } else { 3 });
    }
}

#[test]
fn failed_reclaim_blocks_slot_reuse_and_old_generation_after_success() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    assert!(slot.reclaim(id, &mut s.manager, &mut s.memory).is_err());
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    slot.run(id).unwrap();
    s.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut s.manager, &mut s.memory).is_err());
    let wrong = TaskId::new(id.slot, id.generation + 1).unwrap();
    let writes = s.memory.writes;
    assert_eq!(
        slot.reclaim(wrong, &mut s.manager, &mut s.memory),
        Err(task::Error::Identity)
    );
    assert_eq!(s.memory.writes, writes);
    let next = setup();
    let control = Rc::new(RefCell::new(StopControl::default()));
    let (error, cpu, driver) = slot.insert(next.owner, StopDriver(control)).err().unwrap();
    assert_eq!(error, task::Error::Occupied);
    s.memory.fail_finish = false;
    slot.reclaim(id, &mut s.manager, &mut s.memory).unwrap();
    let new = slot
        .insert(cpu, driver)
        .unwrap_or_else(|_| panic!("empty slot"));
    assert_eq!(new, wrong);
    assert_eq!(
        slot.reclaim(id, &mut s.manager, &mut s.memory),
        Err(task::Error::Identity)
    );
}

#[test]
fn reclamation_requires_settled_terminal_slice_accounting() {
    let mut s = setup();
    let (mut slot, c, id) = task_slot(s.owner);
    c.borrow_mut().slice_terminal = true;
    let (mut scheduler, cpu) = running_scheduler(id);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    let task::Event::Terminated(outcome) = slot.run_slice(id).unwrap().event else {
        panic!()
    };
    assert_eq!(
        slot.reclaim(id, &mut s.manager, &mut s.memory),
        Err(task::Error::State)
    );
    assert_eq!(c.borrow().revocations, 0);
    slot.account_slice(id, &mut scheduler, cpu).unwrap();
    assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
}

#[test]
fn dropped_failed_cleanup_keeps_allocations_retained() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    slot.run(id).unwrap();
    s.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut s.manager, &mut s.memory).is_err());
    drop(slot);
    retained(&mut s.manager, &s.handles);
    assert_eq!(s.manager.summary().allocated_pages, 13);
}

#[test]
fn whole_multipage_image_is_scrubbed_without_following_boot_table_links() {
    use crate::user_entry::{
        spawn::Construction,
        startup::{Arguments, Program},
    };
    struct Never;
    impl Cpu for Never {
        fn snapshot(&mut self) -> Result<Snapshot, CpuError> {
            panic!("unexposed")
        }
        fn write_root(&mut self, _: u64) -> Result<(), CpuError> {
            panic!("unexposed")
        }
    }
    for pages in 1..=4 {
        let mut f = Fixture::new();
        for h in f.handles() {
            f.manager.free(h).unwrap();
        }
        let code = std::vec![0x90; pages * 4096];
        let program = Program::new(&code, 0).unwrap();
        let mut construction = Construction::for_program(&program);
        for _ in 0..5 {
            construction.allocate_next(&mut f.manager).unwrap();
        }
        let handles = construction.handles();
        let (prepared, _) = construction
            .build_program(
                &mut f.manager,
                &mut f.memory,
                &program,
                &Arguments::new(&[b"test"]).unwrap(),
                USER_WINDOW_START + 16 * PAGE_BYTES,
                f.image.stack_page,
                f.core,
                36,
                None,
            )
            .ok()
            .unwrap();
        let mut owner = CpuImage::new(prepared, Never, f.core)
            .retire_owned(&f.manager)
            .ok()
            .unwrap();
        assert_eq!(owner.remaining_pages(), 12 + pages as u64);
        f.memory.fail_write = Some(f.memory.writes + (pages + 4) * 512 - 1);
        assert!(owner.reclaim(&mut f.manager, &mut f.memory).is_err());
        for h in handles.into_iter().flatten() {
            assert_eq!(
                f.manager.free(h),
                Err(PhysicalMemoryError::AllocationRetained)
            );
        }
        f.memory.fail_write = None;
        owner.reclaim(&mut f.manager, &mut f.memory).unwrap();
        assert_eq!(owner.remaining_pages(), 0);
        for h in handles.into_iter().flatten() {
            for p in h.start_page..h.start_page + h.page_count {
                assert_eq!(f.memory.pages[&(p * PAGE_BYTES)], [0; 512]);
            }
        }
        assert_eq!(f.manager.summary().allocated_pages, 0);
    }
}
