use super::*;
use crate::scheduler::{CpuId, Scheduler, WaitKind};
use task::cleanup::{FIRST_DELAY, MAX_ATTEMPTS, Progress};

fn advance(s: &mut Scheduler, cpu: CpuId, count: u32) {
    for _ in 0..count {
        let id = s.dispatch(cpu).unwrap();
        let t = s.task_snapshot(id).unwrap();
        s.account_dispatch(cpu, id, t.dispatch_count, t.runtime_ticks, 1)
            .unwrap();
        s.yield_current(cpu).unwrap();
    }
}

#[test]
fn deferred_prepared_cleanup_waits_retries_once_and_keeps_unrelated_tasks_running() {
    let mut f = setup();
    let (mut slot, control, id) = task_slot(f.owner);
    let out = slot.cancel_prepared(id).unwrap();
    f.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut f.manager, &mut f.memory).is_err());
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    assert!(
        slot.defer_reclamation(id, &mut s, CpuId::new(1).unwrap(), false)
            .is_err()
    );
    assert_eq!(
        slot.defer_reclamation(id, &mut s, cpu, false)
            .unwrap()
            .next_dispatch,
        Some(64)
    );
    assert!(slot.defer_reclamation(id, &mut s, cpu, false).is_err());
    assert!(slot.reclaim(id, &mut f.manager, &mut f.memory).is_err());
    let writes = f.memory.writes;
    for _ in 0..63 {
        advance(&mut s, cpu, 1);
        assert_eq!(
            slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s),
            Ok(Progress::Waiting)
        );
    }
    assert_eq!(f.memory.writes, writes);
    advance(&mut s, cpu, 1);
    assert_eq!(
        slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s),
        Ok(Progress::Retried)
    );
    assert_eq!(
        slot.cleanup_status(id).unwrap().unwrap().next_dispatch,
        Some(192)
    );
    assert_eq!(slot.reclaim_remaining_pages(id), Ok(13));
    retained(&mut f.manager, &f.handles);
    f.memory.fail_finish = false;
    advance(&mut s, cpu, 127);
    assert_eq!(
        slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s),
        Ok(Progress::Waiting)
    );
    advance(&mut s, cpu, 1);
    assert_eq!(
        slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s),
        Ok(Progress::Complete(out))
    );
    assert_eq!(f.manager.summary().allocated_pages, 0);
    assert_eq!(s.task_snapshot(other).unwrap().runtime_ticks, 192);
    assert_eq!(control.borrow().entries, 0);
    assert_eq!(control.borrow().revocations, 1);
    assert!(f.machine.borrow().writes.is_empty());
    assert!(
        slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s)
            .is_err()
    );
}

#[test]
fn exhausted_cleanup_keeps_pages_and_job_membership_without_further_memory_writes() {
    let parent = setup_at(false, 4096);
    let mut f = setup_at(false, 4224);
    let (p, _, pid) = job_tests::at(parent.owner, 3);
    let (mut slot, _, id) = job_tests::at(f.owner, 4);
    let mut job = task::job::Job::<2>::new(&p, pid).unwrap();
    job.adopt(&slot, id).unwrap();
    slot.cancel_prepared(id).unwrap();
    f.memory.fail_finish = true;
    assert!(
        job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
            .is_err()
    );
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let child = s.create_task(id.slot, id.generation, 16, 1).unwrap();
    s.activate(child, cpu).unwrap();
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    slot.defer_reclamation(id, &mut s, cpu, true).unwrap();
    assert_eq!(
        s.task_snapshot(child).unwrap().wait_kind,
        WaitKind::Reclamation
    );
    for attempt in 1..=MAX_ATTEMPTS {
        advance(&mut s, cpu, FIRST_DELAY << (attempt - 1));
        assert_eq!(
            job.reclaim_deferred_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
            Ok(if attempt == MAX_ATTEMPTS {
                Progress::Exhausted
            } else {
                Progress::Retried
            })
        );
        assert_eq!(job.child_count(), 1);
        assert_eq!(slot.cleanup_status(id).unwrap().unwrap().attempts, attempt);
    }
    let writes = f.memory.writes;
    f.memory.fail_finish = false;
    advance(&mut s, cpu, 1000);
    for _ in 0..4 {
        assert_eq!(
            slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s),
            Ok(Progress::Exhausted)
        );
    }
    assert_eq!(f.memory.writes, writes);
    assert_eq!(slot.reclaim_remaining_pages(id), Ok(13));
    assert_eq!(s.summary().teardown_count, 0);
    assert!(s.create_task(id.slot, id.generation + 1, 16, 1).is_err());
    assert!(s.cancel_wait(child, cpu).is_err());
    drop(slot);
    drop(job);
    retained(&mut f.manager, &f.handles);
}

#[test]
fn deferred_cleanup_rejects_early_state_stale_identity_and_running_cpu() {
    let mut f = setup();
    let (mut slot, _, id) = task_slot(f.owner);
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    assert!(slot.defer_reclamation(id, &mut s, cpu, false).is_err());
    slot.cancel_prepared(id).unwrap();
    assert!(slot.defer_reclamation(id, &mut s, cpu, false).is_err());
    f.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut f.manager, &mut f.memory).is_err());
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    assert!(slot.defer_reclamation(id, &mut s, cpu, true).is_err());
    assert_eq!(slot.cleanup_status(id), Ok(None));
    slot.defer_reclamation(id, &mut s, cpu, false).unwrap();
    assert!(
        slot.reclaim_deferred(
            TaskId::new(id.slot, id.generation + 1).unwrap(),
            &mut f.manager,
            &mut f.memory,
            &s
        )
        .is_err()
    );
    advance(&mut s, cpu, 64);
    s.dispatch(cpu).unwrap();
    let writes = f.memory.writes;
    assert!(
        slot.reclaim_deferred(id, &mut f.manager, &mut f.memory, &s)
            .is_err()
    );
    assert_eq!(slot.cleanup_status(id).unwrap().unwrap().attempts, 0);
    assert_eq!(f.memory.writes, writes);
}

#[test]
fn two_exhausted_children_keep_distinct_owners_and_stop_retry_writes() {
    let parent = setup_at(false, 4096);
    let a = setup_at(false, 4224);
    let b = setup_at(false, 4352);
    let (p, _, pid) = job_tests::at(parent.owner, 3);
    let mut job = task::job::Job::<2>::new(&p, pid).unwrap();
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    let mut children = [a, b]
        .into_iter()
        .enumerate()
        .map(|(i, mut f)| {
            let (mut slot, control, id) = job_tests::at(f.owner, 4 + i as u8);
            job.adopt(&slot, id).unwrap();
            slot.cancel_prepared(id).unwrap();
            f.memory.fail_finish = true;
            assert!(
                job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
                    .is_err()
            );
            let child = s.create_task(id.slot, id.generation, 16, 1).unwrap();
            s.activate(child, cpu).unwrap();
            slot.defer_reclamation(id, &mut s, cpu, true).unwrap();
            (slot, control, id, f.manager, f.memory, f.handles)
        })
        .collect::<std::vec::Vec<_>>();
    for attempt in 1..=MAX_ATTEMPTS {
        advance(&mut s, cpu, FIRST_DELAY << (attempt - 1));
        for (slot, _, id, manager, memory, _) in &mut children {
            assert_eq!(
                job.reclaim_deferred_child(slot, *id, manager, memory, &s),
                Ok(if attempt == MAX_ATTEMPTS {
                    Progress::Exhausted
                } else {
                    Progress::Retried
                })
            );
            assert_eq!(job.child_count(), 2);
        }
    }
    let writes = children
        .iter()
        .map(|c| c.4.writes)
        .collect::<std::vec::Vec<_>>();
    advance(&mut s, cpu, 1024);
    for (i, (slot, control, id, manager, memory, handles)) in children.iter_mut().enumerate() {
        memory.fail_finish = false;
        for _ in 0..4 {
            assert_eq!(
                job.reclaim_deferred_child(slot, *id, manager, memory, &s),
                Ok(Progress::Exhausted)
            );
        }
        assert_eq!(memory.writes, writes[i]);
        assert_eq!(slot.reclaim_remaining_pages(*id), Ok(13));
        assert_eq!(
            slot.cleanup_status(*id).unwrap().unwrap().next_dispatch,
            None
        );
        assert!(slot.run_slice(*id).is_err());
        assert!(slot.activate(*id, manager, memory).is_err());
        assert!(s.create_task(id.slot, id.generation + 1, 16, 1).is_err());
        assert_eq!(control.borrow().entries, 0);
        retained(manager, handles);
    }
    assert_eq!(job.child_count(), 2);
    assert_eq!(s.summary().teardown_count, 0);
    assert_eq!(s.task_snapshot(other).unwrap().runtime_ticks, 1472);
}

#[test]
fn deferred_entered_task_preserves_accounting_and_job_until_success() {
    let parent = setup_at(false, 4096);
    let mut f = setup_at(false, 4224);
    let (p, _, pid) = job_tests::at(parent.owner, 3);
    let (mut slot, control, id) = job_tests::at(f.owner, 4);
    let mut job = task::job::Job::<2>::new(&p, pid).unwrap();
    job.adopt(&slot, id).unwrap();
    control.borrow_mut().slice_terminal = true;
    let (mut s, cpu) = running_scheduler(id);
    slot.activate(id, &f.manager, &mut f.memory).unwrap();
    let task::Event::Terminated(out) = slot.run_slice(id).unwrap().event else {
        panic!()
    };
    slot.account_slice(id, &mut s, cpu).unwrap();
    f.memory.fail_finish = true;
    assert!(
        job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
            .is_err()
    );
    slot.defer_reclamation(id, &mut s, cpu, true).unwrap();
    let frozen = slot.runtime(id).unwrap();
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    advance(&mut s, cpu, 64);
    f.memory.fail_finish = false;
    assert_eq!(
        job.reclaim_deferred_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
        Ok(Progress::Complete(out))
    );
    assert_eq!(job.child_count(), 0);
    assert_eq!(
        s.task_snapshot(crate::scheduler::TaskId::new(id.slot, id.generation).unwrap())
            .unwrap()
            .runtime_ticks,
        frozen.charged_ticks
    );
    assert_eq!(control.borrow().entries, 1);
    assert_eq!(control.borrow().revocations, 1);
}
