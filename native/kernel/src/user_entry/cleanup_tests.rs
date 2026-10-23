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
fn exclusive_job_deferred_bypass_preserves_budget_writes_and_runtime() {
    let p = setup_at(false, 4096);
    let mut c = setup_at(false, 4224);
    let (mut parent, _, pid) = job_tests::at(p.owner, 3);
    let (mut child, control, cid) = job_tests::at(c.owner, 4);
    let mut job = task::job::Job::<1>::new(&mut parent, pid).unwrap();
    job.adopt(&mut child, cid).unwrap();
    child.cancel_prepared(cid).unwrap();
    c.memory.fail_finish = true;
    assert!(
        job.reclaim_child(&mut child, cid, &mut c.manager, &mut c.memory)
            .is_err()
    );
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    child.defer_reclamation(cid, &mut s, cpu, false).unwrap();
    advance(&mut s, cpu, FIRST_DELAY);
    let status = child.cleanup_status(cid).unwrap();
    let runtime = child.runtime(cid).unwrap();
    let writes = c.memory.writes;
    let revokes = control.borrow().revocations;
    for _ in 0..4 {
        assert_eq!(
            child.reclaim_deferred(cid, &mut c.manager, &mut c.memory, &s),
            Err(task::Error::Identity)
        );
        assert!(child.reclaim(cid, &mut c.manager, &mut c.memory).is_err());
        assert!(child.reap(cid, &mut c.manager, &mut c.memory).is_err());
    }
    assert_eq!(child.cleanup_status(cid).unwrap(), status);
    assert_eq!(child.runtime(cid).unwrap(), runtime);
    assert_eq!(
        (c.memory.writes, control.borrow().revocations),
        (writes, revokes)
    );
    assert_eq!(
        s.task_snapshot(other).unwrap().runtime_ticks,
        u64::from(FIRST_DELAY)
    );
    retained(&mut c.manager, &c.handles);
    c.memory.fail_finish = false;
    assert!(matches!(
        job.reclaim_deferred_child(&mut child, cid, &mut c.manager, &mut c.memory, &s),
        Ok(Progress::Complete(_))
    ));
    assert_eq!(job.child_count(), 0);
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
    let (mut p, _, pid) = job_tests::at(parent.owner, 3);
    let (mut slot, _, id) = job_tests::at(f.owner, 4);
    let mut job = task::job::Job::<2>::new(&mut p, pid).unwrap();
    job.adopt(&mut slot, id).unwrap();
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
            job.reclaim_deferred_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
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
    let (mut p, _, pid) = job_tests::at(parent.owner, 3);
    let mut job = task::job::Job::<2>::new(&mut p, pid).unwrap();
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let other = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(other, cpu).unwrap();
    let mut children = [a, b]
        .into_iter()
        .enumerate()
        .map(|(i, mut f)| {
            let (mut slot, control, id) = job_tests::at(f.owner, 4 + i as u8);
            job.adopt(&mut slot, id).unwrap();
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
    let (mut p, _, pid) = job_tests::at(parent.owner, 3);
    let (mut slot, control, id) = job_tests::at(f.owner, 4);
    let mut job = task::job::Job::<2>::new(&mut p, pid).unwrap();
    job.adopt(&mut slot, id).unwrap();
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

#[test]
fn closed_job_recovers_exact_exhausted_children_once_without_resetting_normal_budget() {
    use task::cleanup::Recovery;
    for admitted in [false, true] {
        for persistent in [false, true] {
            let parent = setup_at(false, 4096);
            let mut f = setup_at(false, 4224);
            let (mut p, _, pid) = job_tests::at(parent.owner, 3);
            let (mut slot, control, id) = job_tests::at(f.owner, 4);
            let mut job = task::job::Job::<2>::new(&mut p, pid).unwrap();
            job.adopt(&mut slot, id).unwrap();
            let out = slot.cancel_prepared(id).unwrap();
            f.memory.fail_finish = true;
            assert!(
                job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
                    .is_err()
            );
            let mut s = Scheduler::new(1).unwrap();
            let cpu = CpuId::new(0).unwrap();
            if admitted {
                let child = s.create_task(id.slot, id.generation, 16, 1).unwrap();
                s.activate(child, cpu).unwrap();
            }
            let other = s.create_task(7, 1, 16, 1).unwrap();
            s.activate(other, cpu).unwrap();
            slot.defer_reclamation(id, &mut s, cpu, admitted).unwrap();
            for attempt in 1..=MAX_ATTEMPTS {
                advance(&mut s, cpu, FIRST_DELAY << (attempt - 1));
                let expected = if attempt == MAX_ATTEMPTS {
                    Progress::Exhausted
                } else {
                    Progress::Retried
                };
                assert_eq!(
                    job.reclaim_deferred_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
                    Ok(expected)
                );
            }
            let frozen = slot.cleanup_status(id).unwrap();
            let writes = f.memory.writes;
            assert!(
                job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s)
                    .is_err()
            );
            p.cancel_prepared(pid).unwrap();
            job.owner_stopped(&mut p, pid).unwrap();
            for _ in 0..FIRST_DELAY {
                assert_eq!(
                    job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
                    Ok(Recovery::Waiting)
                );
                advance(&mut s, cpu, 1);
                // Ordinary observation must not postpone the recovery cooldown.
                assert_eq!(
                    job.reclaim_deferred_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
                    Ok(Progress::Exhausted)
                );
            }
            assert_eq!(f.memory.writes, writes);
            assert_eq!(job.child_count(), 1);
            assert_eq!(slot.cleanup_status(id).unwrap(), frozen);
            let stale = TaskId::new(id.slot, id.generation + 1).unwrap();
            assert!(
                job.recover_exhausted_child(&mut slot, stale, &mut f.manager, &mut f.memory, &s)
                    .is_err()
            );
            let wrong_clock = Scheduler::new(1).unwrap();
            assert!(
                job.recover_exhausted_child(
                    &mut slot,
                    id,
                    &mut f.manager,
                    &mut f.memory,
                    &wrong_clock
                )
                .is_err()
            );
            let running = s.dispatch(cpu).unwrap();
            assert!(
                job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s)
                    .is_err()
            );
            let time = s.task_snapshot(running).unwrap();
            s.account_dispatch(cpu, running, time.dispatch_count, time.runtime_ticks, 1)
                .unwrap();
            s.yield_current(cpu).unwrap();
            assert_eq!(f.memory.writes, writes);
            f.memory.fail_finish = persistent;
            assert_eq!(
                job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
                Ok(if persistent {
                    Recovery::Retained
                } else {
                    Recovery::Complete(out)
                })
            );
            assert_eq!(control.borrow().entries, 0);
            assert_eq!(control.borrow().revocations, 1);
            assert_eq!(s.summary().teardown_count, 0);
            if persistent {
                assert_eq!(job.child_count(), 1);
                assert_eq!(slot.cleanup_status(id).unwrap(), frozen);
                assert_eq!(slot.reclaim_remaining_pages(id), Ok(13));
                let writes = f.memory.writes;
                f.memory.fail_finish = false;
                advance(&mut s, cpu, 1024);
                for _ in 0..8 {
                    assert_eq!(
                        job.recover_exhausted_child(
                            &mut slot,
                            id,
                            &mut f.manager,
                            &mut f.memory,
                            &s
                        ),
                        Ok(Recovery::Unavailable)
                    );
                    assert_eq!(
                        job.reclaim_deferred_child(
                            &mut slot,
                            id,
                            &mut f.manager,
                            &mut f.memory,
                            &s
                        ),
                        Ok(Progress::Exhausted)
                    );
                    assert!(
                        job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
                            .is_err()
                    );
                }
                assert_eq!(f.memory.writes, writes);
                retained(&mut f.manager, &f.handles);
            } else {
                assert_eq!(job.child_count(), 0);
                assert_eq!(f.manager.summary().allocated_pages, 0);
                assert_eq!(slot.state(id), Err(task::Error::Missing));
                assert!(
                    job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s)
                        .is_err()
                );
            }
        }
    }
}

#[test]
fn orphan_recovery_requires_exhaustion_and_exact_closed_membership() {
    let parent = setup_at(false, 4096);
    let foreign = setup_at(false, 4352);
    let mut f = setup_at(false, 4224);
    let (mut p, _, pid) = job_tests::at(parent.owner, 3);
    let (mut q, _, qid) = job_tests::at(foreign.owner, 6);
    let (mut slot, _, id) = job_tests::at(f.owner, 4);
    let mut job = task::job::Job::<2>::new(&mut p, pid).unwrap();
    let mut other = task::job::Job::<2>::new(&mut q, qid).unwrap();
    job.adopt(&mut slot, id).unwrap();
    p.cancel_prepared(pid).unwrap();
    q.cancel_prepared(qid).unwrap();
    job.owner_stopped(&mut p, pid).unwrap();
    other.owner_stopped(&mut q, qid).unwrap();
    let mut s = Scheduler::new(1).unwrap();
    let cpu = CpuId::new(0).unwrap();
    let peer = s.create_task(7, 1, 16, 1).unwrap();
    s.activate(peer, cpu).unwrap();
    assert!(
        job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s)
            .is_err()
    );
    slot.cancel_prepared(id).unwrap();
    f.memory.fail_finish = true;
    assert!(
        job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
            .is_err()
    );
    slot.defer_reclamation(id, &mut s, cpu, false).unwrap();
    for attempt in 1..=MAX_ATTEMPTS {
        let writes = f.memory.writes;
        let frozen = slot.cleanup_status(id).unwrap();
        assert!(
            job.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s)
                .is_err()
        );
        assert_eq!(f.memory.writes, writes);
        assert_eq!(slot.cleanup_status(id).unwrap(), frozen);
        advance(&mut s, cpu, FIRST_DELAY << (attempt - 1));
        job.reclaim_deferred_child(&mut slot, id, &mut f.manager, &mut f.memory, &s)
            .unwrap();
    }
    advance(&mut s, cpu, FIRST_DELAY);
    let writes = f.memory.writes;
    assert_eq!(
        other.recover_exhausted_child(&mut slot, id, &mut f.manager, &mut f.memory, &s),
        Err(task::Error::Identity)
    );
    assert_eq!(f.memory.writes, writes);
    assert_eq!(job.child_count(), 1);
    retained(&mut f.manager, &f.handles);
}

fn settled_scheduler(id: TaskId, slices: u32, ticks: u64) -> (Scheduler, CpuId) {
    let (mut scheduler, cpu) = running_scheduler(id);
    let sid = crate::scheduler::TaskId::new(id.slot, id.generation).unwrap();
    for ordinal in 1..=slices {
        if ordinal > 1 {
            assert_eq!(scheduler.dispatch(cpu), Ok(sid));
        }
        scheduler
            .account_dispatch(
                cpu,
                sid,
                ordinal,
                if ordinal == 1 { 0 } else { ticks },
                if ordinal == 1 { ticks } else { 0 },
            )
            .unwrap();
        scheduler.yield_current(cpu).unwrap();
    }
    (scheduler, cpu)
}

#[test]
fn entered_cleanup_rejects_equal_ticks_with_wrong_slice_count_before_parking() {
    let mut f = setup();
    let (mut slot, control, id) = task_slot(f.owner);
    let (mut scheduler, cpu) = running_scheduler(id);
    for terminal in [false, true] {
        control.borrow_mut().slice_terminal = terminal;
        slot.activate(id, &f.manager, &mut f.memory).unwrap();
        slot.run_slice(id).unwrap();
        slot.account_slice(id, &mut scheduler, cpu).unwrap();
        if !terminal {
            scheduler.yield_current(cpu).unwrap();
            scheduler.dispatch(cpu).unwrap();
        }
    }
    let runtime = slot.runtime(id).unwrap();
    assert_eq!((runtime.charged_slices, runtime.charged_ticks), (2, 2));
    f.memory.fail_finish = true;
    assert!(slot.reclaim(id, &mut f.manager, &mut f.memory).is_err());
    let writes = f.memory.writes;
    let sid = crate::scheduler::TaskId::new(id.slot, id.generation).unwrap();
    for slices in [1, 3] {
        let (mut mismatched, other_cpu) = settled_scheduler(id, slices, runtime.charged_ticks);
        let before = mismatched.task_snapshot(sid).unwrap();
        assert_eq!(
            slot.defer_reclamation(id, &mut mismatched, other_cpu, true),
            Err(task::Error::State)
        );
        assert_eq!(mismatched.task_snapshot(sid).unwrap(), before);
        assert_eq!(slot.cleanup_status(id), Ok(None));
        assert_eq!(slot.runtime(id), Ok(runtime));
        assert_eq!(f.memory.writes, writes);
    }
    slot.defer_reclamation(id, &mut scheduler, cpu, true)
        .unwrap();
    assert_eq!(control.borrow().entries, 2);
    assert_eq!(control.borrow().revocations, 1);
    retained(&mut f.manager, &f.handles);
}

#[test]
fn entered_exhausted_recovery_matches_slices_and_preserves_terminal_accounting() {
    use task::cleanup::Recovery;
    for terminal in [false, true] {
        for persistent in [false, true] {
            let parent = setup_at(false, 4096);
            let mut f = setup_at(false, 4224);
            let (mut p, _, pid) = job_tests::at(parent.owner, 3);
            let (mut slot, control, id) = job_tests::at(f.owner, 4);
            let mut job = task::job::Job::<2>::new(&mut p, pid).unwrap();
            job.adopt(&mut slot, id).unwrap();
            let (mut scheduler, cpu) = running_scheduler(id);
            let sid = crate::scheduler::TaskId::new(id.slot, id.generation).unwrap();
            for ordinal in 1..=2 {
                control.borrow_mut().slice_terminal = terminal && ordinal == 2;
                slot.activate(id, &f.manager, &mut f.memory).unwrap();
                slot.run_slice(id).unwrap();
                slot.account_slice(id, &mut scheduler, cpu).unwrap();
                if ordinal == 1 {
                    scheduler.yield_current(cpu).unwrap();
                    scheduler.dispatch(cpu).unwrap();
                }
            }
            let out = if terminal {
                slot.outcome(id).unwrap()
            } else {
                slot.cancel_suspended(id).unwrap()
            };
            let runtime = slot.runtime(id).unwrap();
            assert_eq!((runtime.charged_slices, runtime.charged_ticks), (2, 2));
            f.memory.fail_finish = true;
            assert!(
                job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
                    .is_err()
            );
            slot.defer_reclamation(id, &mut scheduler, cpu, true)
                .unwrap();
            let parked = scheduler.task_snapshot(sid).unwrap();
            let peer = scheduler.create_task(7, 1, 16, 1).unwrap();
            scheduler.activate(peer, cpu).unwrap();
            for attempt in 1..=MAX_ATTEMPTS {
                advance(&mut scheduler, cpu, FIRST_DELAY << (attempt - 1));
                assert_eq!(
                    job.reclaim_deferred_child(
                        &mut slot,
                        id,
                        &mut f.manager,
                        &mut f.memory,
                        &scheduler
                    ),
                    Ok(if attempt == MAX_ATTEMPTS {
                        Progress::Exhausted
                    } else {
                        Progress::Retried
                    })
                );
                assert_eq!(slot.runtime(id), Ok(runtime));
                assert_eq!(scheduler.task_snapshot(sid), Ok(parked));
            }
            p.cancel_prepared(pid).unwrap();
            job.owner_stopped(&mut p, pid).unwrap();
            advance(&mut scheduler, cpu, FIRST_DELAY);
            let writes = f.memory.writes;
            let roots = f.machine.borrow().writes.clone();
            let budget = slot.cleanup_status(id).unwrap();
            for slices in [1, 3] {
                let (mut mismatched, other_cpu) =
                    settled_scheduler(id, slices, runtime.charged_ticks);
                mismatched.park_reclamation(sid, other_cpu, false).unwrap();
                let other = mismatched.create_task(7, 1, 16, 1).unwrap();
                mismatched.activate(other, other_cpu).unwrap();
                advance(
                    &mut mismatched,
                    other_cpu,
                    scheduler.summary().dispatch_count,
                );
                assert_eq!(
                    job.recover_exhausted_child(
                        &mut slot,
                        id,
                        &mut f.manager,
                        &mut f.memory,
                        &mismatched
                    ),
                    Err(task::Error::State)
                );
                assert_eq!(
                    job.reclaim_deferred_child(
                        &mut slot,
                        id,
                        &mut f.manager,
                        &mut f.memory,
                        &mismatched
                    ),
                    Err(task::Error::State)
                );
                assert_eq!(f.memory.writes, writes);
                assert_eq!(slot.cleanup_status(id), Ok(budget));
                assert_eq!(job.child_count(), 1);
            }
            f.memory.fail_finish = persistent;
            assert_eq!(
                job.recover_exhausted_child(
                    &mut slot,
                    id,
                    &mut f.manager,
                    &mut f.memory,
                    &scheduler
                ),
                Ok(if persistent {
                    Recovery::Retained
                } else {
                    Recovery::Complete(out)
                })
            );
            assert_eq!(scheduler.task_snapshot(sid), Ok(parked));
            assert!(
                scheduler
                    .create_task(id.slot, id.generation + 1, 16, 1)
                    .is_err()
            );
            assert!(slot.activate(id, &f.manager, &mut f.memory).is_err());
            assert!(slot.run_slice(id).is_err());
            if persistent {
                let writes = f.memory.writes;
                let peer_ticks = scheduler.task_snapshot(peer).unwrap().runtime_ticks;
                f.memory.fail_finish = false;
                advance(&mut scheduler, cpu, 1024);
                for _ in 0..4 {
                    assert_eq!(
                        job.recover_exhausted_child(
                            &mut slot,
                            id,
                            &mut f.manager,
                            &mut f.memory,
                            &scheduler
                        ),
                        Ok(Recovery::Unavailable)
                    );
                    assert_eq!(
                        job.reclaim_deferred_child(
                            &mut slot,
                            id,
                            &mut f.manager,
                            &mut f.memory,
                            &scheduler
                        ),
                        Ok(Progress::Exhausted)
                    );
                    assert!(
                        job.reclaim_child(&mut slot, id, &mut f.manager, &mut f.memory)
                            .is_err()
                    );
                }
                assert_eq!(
                    scheduler.task_snapshot(peer).unwrap().runtime_ticks,
                    peer_ticks + 1024
                );
                assert_eq!(f.memory.writes, writes);
                assert_eq!(slot.runtime(id), Ok(runtime));
                assert_eq!(slot.outcome(id), Ok(out));
                assert_eq!(slot.reclaim_remaining_pages(id), Ok(13));
                assert_eq!(job.child_count(), 1);
                assert!(scheduler.cancel_wait(sid, cpu).is_err());
                retained(&mut f.manager, &f.handles);
            } else {
                assert_eq!(slot.state(id), Err(task::Error::Missing));
                assert_eq!(f.manager.summary().allocated_pages, 0);
                assert_eq!(job.child_count(), 0);
                scheduler.teardown(sid).unwrap();
                scheduler
                    .create_task(id.slot, id.generation + 1, 16, 1)
                    .unwrap();
                assert!(
                    job.recover_exhausted_child(
                        &mut slot,
                        id,
                        &mut f.manager,
                        &mut f.memory,
                        &scheduler
                    )
                    .is_err()
                );
            }
            assert_eq!(f.machine.borrow().writes, roots);
            assert_eq!(control.borrow().entries, 2);
            assert_eq!(control.borrow().revocations, 1);
        }
    }
}
