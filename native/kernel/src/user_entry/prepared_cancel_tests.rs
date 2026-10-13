use super::*;

#[test]
fn prepared_cancel_derives_identity_without_execution_or_release() {
    let mut s = setup();
    let (mut slot, control, id) = task_slot(s.owner);
    let outcome = slot.cancel_prepared(id).unwrap();
    assert_eq!(
        outcome,
        Outcome {
            id,
            root: s.candidate,
            reason: Reason::Cancelled,
            syscalls: 0
        }
    );
    assert_eq!(slot.outcome(id), Ok(outcome));
    assert_eq!(slot.state(id), Ok(task::State::Terminated));
    assert_eq!(slot.runtime(id), Ok(task::Runtime::default()));
    assert!(slot.cancel_prepared(id).is_err());
    assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
    assert!(slot.run(id).is_err());
    retained(&mut s.manager, &s.handles);
    assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
    assert!(s.machine.borrow().writes.is_empty());
    assert_eq!(control.borrow().entries, 0);
    assert_eq!(control.borrow().shutdowns, 0);
    assert_eq!(control.borrow().revocations, 1);
    assert_eq!(s.manager.summary().allocated_pages, 0);
}

#[test]
fn prepared_cancel_rejects_stale_and_every_exposed_task_state() {
    for mode in 0..4 {
        let mut s = setup();
        let (mut slot, control, id) = task_slot(s.owner);
        let wrong = TaskId::new(id.slot, id.generation + 1).unwrap();
        assert_eq!(slot.cancel_prepared(wrong), Err(task::Error::Identity));
        if mode == 0 {
            s.machine.borrow_mut().write_error = true;
            assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        } else {
            slot.activate(id, &s.manager, &mut s.memory).unwrap();
            if mode == 2 {
                slot.run_slice(id).unwrap();
            }
            if mode == 3 {
                slot.run(id).unwrap();
            }
        }
        let before = slot.state(id);
        let calls = control.borrow().entries;
        assert_eq!(slot.cancel_prepared(id), Err(task::Error::State));
        assert_eq!(slot.state(id), before);
        assert_eq!(control.borrow().entries, calls);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn prepared_cancellation_keeps_all_page_boundaries_owned_on_failed_erase() {
    for page in 0..13 {
        for word in [0, 511] {
            for mode in 0..3 {
                let mut s = setup();
                let (mut slot, control, id) = task_slot(s.owner);
                let outcome = slot.cancel_prepared(id).unwrap();
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
                assert_eq!(slot.reclaim_remaining_pages(id), Ok(13));
                assert_eq!(slot.outcome(id), Ok(outcome));
                assert!(slot.cancel_prepared(id).is_err());
                assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
                assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
                retained(&mut s.manager, &s.handles);
                s.memory.fail_write = None;
                s.memory.fail_read = None;
                s.memory.corrupt_write = None;
                assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
                assert_eq!(s.manager.summary().allocated_pages, 0);
                assert!(s.machine.borrow().writes.is_empty());
                assert_eq!(control.borrow().entries, 0);
                assert_eq!(control.borrow().revocations, 1);
            }
        }
    }
}

#[test]
fn prepared_revoke_and_finish_failures_preserve_cancellation_and_retry() {
    let mut s = setup();
    let (mut slot, control, id) = task_slot(s.owner);
    let outcome = slot.cancel_prepared(id).unwrap();
    control.borrow_mut().fail_revoke = true;
    let before = s.memory.writes;
    assert!(matches!(
        slot.reclaim(id, &mut s.manager, &mut s.memory),
        Err(task::Error::Cpu(_))
    ));
    assert_eq!(s.memory.writes, before);
    retained(&mut s.manager, &s.handles);
    control.borrow_mut().fail_revoke = false;
    s.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut s.manager, &mut s.memory).is_err());
    assert_eq!(slot.outcome(id), Ok(outcome));
    retained(&mut s.manager, &s.handles);
    s.memory.fail_finish = false;
    assert_eq!(slot.reclaim(id, &mut s.manager, &mut s.memory), Ok(outcome));
    assert!(s.machine.borrow().writes.is_empty());
}

#[test]
fn prepared_generation_cannot_be_reused_until_cleanup_finishes() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    slot.cancel_prepared(id).unwrap();
    s.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut s.manager, &mut s.memory).is_err());
    let next = setup();
    let (error, cpu, driver) = slot
        .insert(
            next.owner,
            StopDriver(Rc::new(RefCell::new(StopControl::default()))),
        )
        .err()
        .unwrap();
    assert_eq!(error, task::Error::Occupied);
    s.memory.fail_finish = false;
    slot.reclaim(id, &mut s.manager, &mut s.memory).unwrap();
    let next_id = slot
        .insert(cpu, driver)
        .unwrap_or_else(|_| panic!("empty slot"));
    assert_eq!(next_id.generation, id.generation + 1);
    assert_eq!(slot.cancel_prepared(id), Err(task::Error::Identity));
    assert_eq!(slot.cancel_prepared(next_id).unwrap().root, next.candidate);
}

#[test]
fn prepared_slot_rejects_previously_exposed_cpu_owner_before_insertion() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.unexposed_admission(), Err(CpuError::State));
    let mut slot = Slot::new(0).unwrap();
    let control = Rc::new(RefCell::new(StopControl::default()));
    let (error, _, _) = slot.insert(s.owner, StopDriver(control)).err().unwrap();
    assert_eq!(error, task::Error::State);
    assert_eq!(
        slot.state(TaskId::new(0, 1).unwrap()),
        Err(task::Error::Missing)
    );
    retained(&mut s.manager, &s.handles);
}
