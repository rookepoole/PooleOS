use super::*;
use crate::user_entry::prepared::cpu::{Cpu, CpuImage, Error as CpuError, Snapshot, State};
use crate::user_entry::privilege;
use std::{cell::RefCell, rc::Rc};

struct Machine {
    snapshot: Snapshot,
    writes: std::vec::Vec<u64>,
    reads: usize,
    fail_read: Option<usize>,
    write_error: bool,
    suppress_write: bool,
    change_cpu_after_write: bool,
    change_cpu_on_read: Option<usize>,
}

struct Hardware(Rc<RefCell<Machine>>);

use crate::scheduler_smp::TaskId;
use crate::user_entry::task::{self, Outcome, Reason, Slot};
#[derive(Default)]
struct StopControl {
    fail_execute: bool,
    fail_quiesce: bool,
    corrupt: u8,
    entries: u32,
    shutdowns: u32,
    slice_terminal: bool,
    budget_yield: bool,
    zero_ticks: bool,
    wait: Option<crate::capability_ipc::wait::Ticket>,
    fail_complete: bool,
    completions: u32,
    fail_revoke: bool,
    revocations: u32,
}
struct StopDriver(Rc<RefCell<StopControl>>);
impl task::SliceDriver for StopDriver {
    fn complete_wait(
        &mut self,
        _: TaskId,
        _: crate::capability_ipc::wait::Ticket,
        _: crate::user_entry::syscall::Status,
    ) -> Result<(), privilege::Error> {
        let mut c = self.0.borrow_mut();
        if c.fail_complete {
            return Err(privilege::Error::State);
        }
        c.completions += 1;
        c.wait = None;
        Ok(())
    }
    fn execute_slice(
        &mut self,
        image: ImageAdmission,
        id: TaskId,
    ) -> Result<task::Slice, privilege::Error> {
        let o = task::Driver::execute(self, image, id)?;
        let c = self.0.borrow();
        Ok(task::Slice {
            id: o.id,
            root: o.root,
            ticks: u64::from(!c.zero_ticks),
            event: if let Some(ticket) = c.wait {
                task::Event::Waiting {
                    ticket,
                    syscalls: o.syscalls,
                }
            } else if c.slice_terminal {
                task::Event::Terminated(o)
            } else if c.budget_yield || c.corrupt == 4 {
                task::Event::BudgetYield {
                    syscalls: if c.corrupt == 4 {
                        63
                    } else {
                        u64::from(c.entries) * 64
                    },
                }
            } else {
                task::Event::Preempted {
                    ticks: u64::from(!c.zero_ticks),
                    syscalls: o.syscalls,
                    progress: u64::from(c.entries),
                }
            },
        })
    }
}
impl task::Driver for StopDriver {
    fn revoke(&mut self, _: TaskId) -> Result<(), privilege::Error> {
        let mut c = self.0.borrow_mut();
        c.revocations += 1;
        if c.fail_revoke {
            Err(privilege::Error::State)
        } else {
            Ok(())
        }
    }
    fn execute(&mut self, image: ImageAdmission, id: TaskId) -> Result<Outcome, privilege::Error> {
        let mut c = self.0.borrow_mut();
        c.entries += 1;
        if c.fail_execute {
            return Err(privilege::Error::Hardware);
        }
        let mut o = Outcome {
            id,
            root: image.root_physical,
            reason: Reason::Exit(42),
            syscalls: 2,
        };
        match c.corrupt {
            1 => o.id.generation += 1,
            2 => o.root += 4096,
            3 => o.syscalls = 0,
            4 => {
                o.syscalls = 65;
                o.reason = Reason::CallCounterExhausted;
            }
            _ => {}
        }
        Ok(o)
    }
    fn quiesce(&mut self, _: u64) -> Result<(), privilege::Error> {
        let mut c = self.0.borrow_mut();
        c.shutdowns += 1;
        if c.fail_quiesce {
            Err(privilege::Error::Hardware)
        } else {
            Ok(())
        }
    }
}
fn task_slot(
    owner: CpuImage<Hardware>,
) -> (Slot<Hardware, StopDriver>, Rc<RefCell<StopControl>>, TaskId) {
    let mut slot = Slot::new(0).unwrap();
    let control = Rc::new(RefCell::new(StopControl::default()));
    let id = slot
        .insert(owner, StopDriver(Rc::clone(&control)))
        .unwrap_or_else(|(e, _, _)| panic!("insert {e:?}"));
    (slot, control, id)
}

fn running_scheduler(id: TaskId) -> (crate::scheduler::Scheduler, crate::scheduler::CpuId) {
    let mut scheduler = crate::scheduler::Scheduler::new(1).unwrap();
    let cpu = crate::scheduler::CpuId::new(0).unwrap();
    let sid = scheduler
        .create_task(id.slot, id.generation, 16, 1)
        .unwrap();
    scheduler.activate(sid, cpu).unwrap();
    scheduler.dispatch(cpu).unwrap();
    (scheduler, cpu)
}

#[test]
fn waiting_task_requires_settled_slice_and_exact_notification_before_resuming() {
    use crate::capability_ipc::{
        Caller, Space,
        wait::{Admission, Readiness},
    };
    let mut s = setup();
    let image = s.image;
    let (mut slot, c, id) = task_slot(s.owner);
    let mut space = Space::new();
    space.attach(id, image).unwrap();
    let h = space.create_endpoint(id).unwrap();
    let Admission::Pending(ticket) = space
        .prepare_wait(Caller::new(id, image), h, Readiness::Readable)
        .unwrap()
    else {
        panic!()
    };
    c.borrow_mut().wait = Some(ticket);
    let (mut scheduler, cpu) = running_scheduler(id);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    slot.run_slice(id).unwrap();
    assert_eq!(slot.state(id), Ok(task::State::Waiting));
    assert_eq!(s.machine.borrow().snapshot.cr3, s.original);
    assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
    assert!(slot.cancel_suspended(id).is_err());
    assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
    assert!(
        slot.complete_wait(id, ticket, crate::user_entry::syscall::Status::Ok)
            .is_err()
    );
    slot.account_slice(id, &mut scheduler, cpu).unwrap();
    space.park_wait(ticket, &mut scheduler, cpu).unwrap();
    space.cancel_wait(ticket, &mut scheduler, cpu).unwrap();
    scheduler.dispatch(cpu).unwrap();
    c.borrow_mut().fail_complete = true;
    assert!(
        space
            .complete_wait(ticket, &mut scheduler, cpu, |status| {
                slot.complete_wait(id, ticket, status)
                    .map_err(|_| crate::capability_ipc::Error::Denied)
            })
            .is_err()
    );
    assert_eq!(c.borrow().completions, 0);
    assert_eq!(slot.state(id), Ok(task::State::Waiting));
    retained(&mut s.manager, &s.handles);
    c.borrow_mut().fail_complete = false;
    space
        .complete_wait(ticket, &mut scheduler, cpu, |status| {
            slot.complete_wait(id, ticket, status)
                .map_err(|_| crate::capability_ipc::Error::Denied)
        })
        .unwrap();
    assert_eq!(c.borrow().completions, 1);
    assert!(
        slot.complete_wait(id, ticket, crate::user_entry::syscall::Status::Ok)
            .is_err()
    );
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    c.borrow_mut().slice_terminal = true;
    slot.run_slice(id).unwrap();
    slot.account_slice(id, &mut scheduler, cpu).unwrap();
    slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
}

#[test]
fn waiting_task_termination_never_resumes_and_retains_failed_retirement_for_retry() {
    use crate::capability_ipc::{
        Caller, Space,
        wait::{Admission, Readiness},
    };
    for notified in [false, true] {
        let mut s = setup();
        let image = s.image;
        let (mut slot, c, id) = task_slot(s.owner);
        let mut space = Space::new();
        space.attach(id, image).unwrap();
        let h = space.create_endpoint(id).unwrap();
        let Admission::Pending(ticket) = space
            .prepare_wait(Caller::new(id, image), h, Readiness::Readable)
            .unwrap()
        else {
            panic!()
        };
        let other = TaskId::new(1, 1).unwrap();
        let other_image = ImageAdmission {
            root_physical: image.root_physical + 4096,
            ..image
        };
        space.attach(other, other_image).unwrap();
        let other_h = space.create_endpoint(other).unwrap();
        let Admission::Pending(wrong) = space
            .prepare_wait(
                Caller::new(other, other_image),
                other_h,
                Readiness::Readable,
            )
            .unwrap()
        else {
            panic!()
        };
        assert!(slot.cancel_waiting(id, ticket).is_err());
        c.borrow_mut().wait = Some(ticket);
        let (mut scheduler, cpu) = running_scheduler(id);
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert!(slot.cancel_waiting(id, ticket).is_err());
        slot.run_slice(id).unwrap();
        assert!(slot.cancel_waiting(id, ticket).is_err());
        slot.account_slice(id, &mut scheduler, cpu).unwrap();
        space.park_wait(ticket, &mut scheduler, cpu).unwrap();
        if notified {
            space.cancel_wait(ticket, &mut scheduler, cpu).unwrap();
        }
        assert_eq!(slot.cancel_waiting(id, wrong), Err(task::Error::Identity));
        assert_eq!(slot.state(id), Ok(task::State::Waiting));
        let outcome = slot.cancel_waiting(id, ticket).unwrap();
        assert_eq!(outcome.reason, Reason::Cancelled);
        assert_eq!(outcome.syscalls, 2);
        assert!(slot.cancel_waiting(id, ticket).is_err());
        assert!(
            slot.complete_wait(id, ticket, crate::user_entry::syscall::Status::Cancelled)
                .is_err()
        );
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert_eq!(c.borrow().completions, 0);
        c.borrow_mut().fail_revoke = true;
        assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
        retained(&mut s.manager, &s.handles);
        c.borrow_mut().fail_revoke = false;
        let (_, actual) = slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
        assert_eq!(actual, outcome);
        space.detach(id).unwrap();
        scheduler
            .teardown(crate::scheduler::TaskId::new(id.slot, id.generation).unwrap())
            .unwrap();
        assert!(space.cancel_wait(ticket, &mut scheduler, cpu).is_err());
        assert_eq!(scheduler.summary().runnable_count, 0);
        assert_eq!(scheduler.summary().dead_count, 1);
        scheduler.validate().unwrap();
        assert_eq!(s.machine.borrow().snapshot.cr3, s.original);
    }
}

#[test]
fn retirement_revocation_failure_retains_root_and_supports_terminal_and_quarantine_retry() {
    for failed_execution in [false, true] {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        c.borrow_mut().fail_execute = failed_execution;
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert_eq!(slot.run(id).is_err(), failed_execution);
        c.borrow_mut().fail_revoke = true;
        if failed_execution {
            assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
        } else {
            assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
        }
        retained(&mut s.manager, &s.handles);
        assert_eq!(s.machine.borrow().writes, [s.candidate]);
        c.borrow_mut().fail_revoke = false;
        if failed_execution {
            slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        } else {
            slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
        }
        assert_eq!(c.borrow().revocations, 2);
        assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    }
}

#[test]
fn runtime_pending_charge_blocks_resume_cancel_and_release_until_settled_once() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    let (mut scheduler, cpu) = running_scheduler(id);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    slot.run_slice(id).unwrap();
    assert_eq!(slot.runtime(id).unwrap().pending_ticks, Some(1));
    assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
    assert!(slot.cancel_suspended(id).is_err());
    assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
    assert_eq!(slot.account_slice(id, &mut scheduler, cpu), Ok(1));
    let charged = slot.runtime(id).unwrap();
    assert_eq!(
        (
            charged.charged_slices,
            charged.charged_ticks,
            charged.pending_ticks
        ),
        (1, 1, None)
    );
    assert_eq!(
        slot.account_slice(id, &mut scheduler, cpu),
        Err(task::Error::State)
    );
    assert_eq!(slot.runtime(id).unwrap(), charged);
    slot.cancel_suspended(id).unwrap();
    slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
    assert_eq!(
        scheduler
            .task_snapshot(crate::scheduler::TaskId::new(0, 1).unwrap())
            .unwrap()
            .runtime_ticks,
        1
    );
}

#[test]
fn runtime_terminal_and_cleanup_failure_keep_exact_charge_across_rejected_settlement_and_retry() {
    for terminal in [false, true] {
        for zero in [false, true] {
            if zero && !terminal {
                continue;
            }
            let mut s = setup();
            let (mut slot, c, id) = task_slot(s.owner);
            c.borrow_mut().slice_terminal = terminal;
            c.borrow_mut().zero_ticks = zero;
            c.borrow_mut().fail_quiesce = true;
            let (mut scheduler, cpu) = running_scheduler(id);
            slot.activate(id, &s.manager, &mut s.memory).unwrap();
            assert!(slot.run_slice(id).is_err());
            let pending = slot.runtime(id).unwrap();
            assert!(!pending.unknown);
            assert_eq!(pending.pending_ticks, Some(u64::from(!zero)));
            assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
            assert!(
                slot.account_slice(
                    TaskId {
                        generation: 2,
                        ..id
                    },
                    &mut scheduler,
                    cpu
                )
                .is_err()
            );
            let (mut foreign, _) = running_scheduler(TaskId::new(1, 1).unwrap());
            assert!(slot.account_slice(id, &mut foreign, cpu).is_err());
            assert!(
                slot.account_slice(id, &mut scheduler, crate::scheduler::CpuId::new(1).unwrap())
                    .is_err()
            );
            assert_eq!(slot.runtime(id).unwrap(), pending);
            assert_eq!(
                slot.account_slice(id, &mut scheduler, cpu),
                Ok(u64::from(!zero))
            );
            assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
            assert!(slot.account_slice(id, &mut scheduler, cpu).is_err());
            retained(&mut s.manager, &s.handles);
            c.borrow_mut().fail_quiesce = false;
            slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
            assert_eq!(c.borrow().entries, 1);
            assert_eq!(
                scheduler
                    .task_snapshot(crate::scheduler::TaskId::new(0, 1).unwrap())
                    .unwrap()
                    .runtime_ticks,
                u64::from(!zero)
            );
        }
    }
}

#[test]
fn runtime_missing_measurement_is_unknown_not_zero_and_retained_until_recorded() {
    let mut s = setup();
    let (mut slot, c, id) = task_slot(s.owner);
    c.borrow_mut().fail_execute = true;
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    assert!(slot.run_slice(id).is_err());
    assert_eq!(
        slot.runtime(id).unwrap(),
        task::Runtime {
            unknown: true,
            ..task::Runtime::default()
        }
    );
    let (mut scheduler, cpu) = running_scheduler(id);
    assert!(slot.account_slice(id, &mut scheduler, cpu).is_err());
    assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
    retained(&mut s.manager, &s.handles);
}

#[test]
fn unknown_settlement_preserves_measured_prefix_and_retries_device_and_root_cleanup() {
    for prior_slice in [false, true] {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        let (mut scheduler, cpu) = running_scheduler(id);
        let sid = crate::scheduler::TaskId::new(id.slot, id.generation).unwrap();
        if prior_slice {
            slot.activate(id, &s.manager, &mut s.memory).unwrap();
            slot.run_slice(id).unwrap();
            slot.account_slice(id, &mut scheduler, cpu).unwrap();
            scheduler.yield_current(cpu).unwrap();
            scheduler.dispatch(cpu).unwrap();
        }
        c.borrow_mut().fail_execute = true;
        c.borrow_mut().fail_quiesce = true;
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert!(slot.run_slice(id).is_err());
        let pending = slot.runtime(id).unwrap();
        assert!(pending.unknown);
        assert_eq!(pending.charged_ticks, u64::from(prior_slice));
        assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
        assert!(
            slot.account_unknown(
                TaskId {
                    generation: 2,
                    ..id
                },
                &mut scheduler,
                cpu
            )
            .is_err()
        );
        assert!(
            slot.account_unknown(id, &mut scheduler, crate::scheduler::CpuId::new(1).unwrap())
                .is_err()
        );
        let (mut foreign, _) = running_scheduler(TaskId::new(1, 1).unwrap());
        assert!(slot.account_unknown(id, &mut foreign, cpu).is_err());
        assert_eq!(slot.runtime(id).unwrap(), pending);
        slot.account_unknown(id, &mut scheduler, cpu).unwrap();
        let settled = slot.runtime(id).unwrap();
        assert!(!settled.unknown);
        assert_eq!(settled.unmeasured_slices, 1);
        assert_eq!(settled.charged_ticks, u64::from(prior_slice));
        assert_eq!(
            scheduler.task_snapshot(sid).unwrap().unmeasured_dispatches,
            1
        );
        assert!(slot.account_unknown(id, &mut scheduler, cpu).is_err());
        assert!(slot.account_slice(id, &mut scheduler, cpu).is_err());
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert!(slot.cancel_suspended(id).is_err());
        assert!(slot.outcome(id).is_err());
        assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
        assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
        retained(&mut s.manager, &s.handles);
        c.borrow_mut().fail_quiesce = false;
        s.machine.borrow_mut().write_error = true;
        assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
        retained(&mut s.manager, &s.handles);
        assert_eq!(slot.runtime(id).unwrap(), settled);
        assert_eq!(scheduler.current(cpu), Ok(Some(sid)));
        s.machine.borrow_mut().write_error = false;
        slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        scheduler.teardown(sid).unwrap();
        assert_eq!(
            scheduler.task_snapshot(sid).unwrap().unmeasured_dispatches,
            1
        );
        assert_eq!(
            scheduler.task_snapshot(sid).unwrap().runtime_ticks,
            u64::from(prior_slice)
        );
        assert_eq!(c.borrow().entries, 1 + u32::from(prior_slice));
    }
}

#[test]
fn unknown_settlement_cannot_discard_a_valid_pending_measurement() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    let (mut scheduler, cpu) = running_scheduler(id);
    assert!(slot.account_unknown(id, &mut scheduler, cpu).is_err());
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    assert!(slot.account_unknown(id, &mut scheduler, cpu).is_err());
    slot.run_slice(id).unwrap();
    assert!(slot.account_unknown(id, &mut scheduler, cpu).is_err());
    slot.account_slice(id, &mut scheduler, cpu).unwrap();
    assert!(slot.account_unknown(id, &mut scheduler, cpu).is_err());
    slot.cancel_suspended(id).unwrap();
    assert!(slot.account_unknown(id, &mut scheduler, cpu).is_err());
    slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
}

#[test]
fn task_exit_quiesces_then_reaps_and_reused_slot_rejects_old_identity() {
    let mut s = setup();
    let (mut slot, control, id) = task_slot(s.owner);
    assert!(slot.outcome(id).is_err());
    assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    let o = slot.run(id).unwrap();
    assert_eq!(o.reason, Reason::Exit(42));
    assert_eq!(control.borrow().shutdowns, 1);
    retained(&mut s.manager, &s.handles);
    assert_eq!(slot.run(id), Err(task::Error::State));
    let (_, reaped) = slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
    assert_eq!(reaped, o);
    assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    assert_eq!(slot.state(id), Err(task::Error::Missing));
    assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
    let mut next = setup();
    let next_control = Rc::new(RefCell::new(StopControl::default()));
    let new = slot
        .insert(next.owner, StopDriver(Rc::clone(&next_control)))
        .unwrap_or_else(|(e, _, _)| panic!("{e:?}"));
    assert_eq!(new.generation, id.generation + 1);
    assert_eq!(new.slot, id.slot);
    assert_eq!(slot.run(id), Err(task::Error::Identity));
    assert!(next.machine.borrow().writes.is_empty());
    assert_eq!(next_control.borrow().entries, 0);
    slot.abandon(new, &mut next.manager, &mut next.memory)
        .unwrap();
}

#[test]
fn task_cleanup_failure_keeps_exact_driver_and_memory_quarantined() {
    for execute_failure in [false, true] {
        let mut s = setup();
        let (mut slot, control, id) = task_slot(s.owner);
        control.borrow_mut().fail_execute = execute_failure;
        control.borrow_mut().fail_quiesce = true;
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert!(slot.run(id).is_err());
        assert_eq!(slot.state(id), Ok(task::State::Quarantined));
        assert!(slot.outcome(id).is_err());
        assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
        assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
        assert_eq!(s.machine.borrow().writes, [s.candidate]);
        retained(&mut s.manager, &s.handles);
        control.borrow_mut().fail_quiesce = false;
        slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
        assert_eq!(control.borrow().entries, 1);
        assert_eq!(slot.state(id), Err(task::Error::Missing));
    }
}

#[test]
fn task_wrong_outcomes_never_publish_exit_status_or_resume() {
    for corrupt in 1..=4 {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        c.borrow_mut().corrupt = corrupt;
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert!(slot.run(id).is_err());
        assert!(slot.outcome(id).is_err());
        assert_eq!(slot.run(id), Err(task::Error::State));
        retained(&mut s.manager, &s.handles);
        slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        assert_eq!(c.borrow().entries, 1);
        assert_eq!(c.borrow().shutdowns, 1);
    }
}

#[test]
fn task_activation_or_retirement_write_failures_retain_owner_for_retry() {
    for activation_failure in [true, false] {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        if activation_failure {
            s.machine.borrow_mut().write_error = true;
            assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
            assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
            retained(&mut s.manager, &s.handles);
            s.machine.borrow_mut().write_error = false;
            slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
            assert_eq!(c.borrow().entries, 0);
        } else {
            slot.activate(id, &s.manager, &mut s.memory).unwrap();
            slot.run(id).unwrap();
            s.machine.borrow_mut().write_error = true;
            assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
            assert_eq!(slot.run(id), Err(task::Error::State));
            retained(&mut s.manager, &s.handles);
            s.machine.borrow_mut().write_error = false;
            slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
            assert_eq!(c.borrow().entries, 1);
        }
        assert_eq!(slot.state(id), Err(task::Error::Missing));
    }
}

#[test]
fn occupied_task_slot_returns_unmodified_new_owner_and_drop_never_frees() {
    let mut s = setup();
    let (mut slot, _, id) = task_slot(s.owner);
    let mut next = setup();
    let c = Rc::new(RefCell::new(StopControl::default()));
    let (e, owner, _) = slot.insert(next.owner, StopDriver(c)).err().unwrap();
    assert_eq!(e, task::Error::Occupied);
    retained(&mut next.manager, &next.handles);
    assert_eq!(slot.state(id), Ok(task::State::Prepared));
    drop(owner);
    drop(slot);
    retained(&mut s.manager, &s.handles);
    retained(&mut next.manager, &next.handles);
    assert!(s.machine.borrow().writes.is_empty());
    assert!(next.machine.borrow().writes.is_empty());
}

#[test]
fn prepared_task_cancel_has_no_cpu_or_driver_effect() {
    let mut s = setup();
    let (mut slot, c, id) = task_slot(s.owner);
    assert_eq!(slot.run(id), Err(task::Error::State));
    slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
    assert!(s.machine.borrow().writes.is_empty());
    assert_eq!(c.borrow().entries, 0);
    assert_eq!(c.borrow().shutdowns, 0);
    assert_eq!(slot.state(id), Err(task::Error::Missing));
}

#[test]
fn task_quanta_retain_memory_across_suspension_and_restore_before_resuming() {
    let mut s = setup();
    let (mut slot, c, id) = task_slot(s.owner);
    let (mut scheduler, cpu) = running_scheduler(id);
    assert!(slot.cancel_suspended(id).is_err());
    for n in 1..=3 {
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert!(slot.cancel_suspended(id).is_err());
        let result = slot.run_slice(id).unwrap();
        assert_eq!(
            result.event,
            task::Event::Preempted {
                ticks: 1,
                syscalls: 2,
                progress: n
            }
        );
        assert_eq!(slot.state(id), Ok(task::State::Suspended));
        assert_eq!(s.machine.borrow().snapshot.cr3, s.original);
        assert!(slot.run_slice(id).is_err());
        assert!(slot.reap(id, &mut s.manager, &mut s.memory).is_err());
        retained(&mut s.manager, &s.handles);
        slot.account_slice(id, &mut scheduler, cpu).unwrap();
        scheduler.yield_current(cpu).unwrap();
        scheduler.dispatch(cpu).unwrap();
    }
    c.borrow_mut().slice_terminal = true;
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    assert!(matches!(
        slot.run_slice(id).unwrap().event,
        task::Event::Terminated(_)
    ));
    assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
    slot.account_slice(id, &mut scheduler, cpu).unwrap();
    slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
    assert_eq!(
        s.machine.borrow().writes,
        [
            s.candidate,
            s.original,
            s.candidate,
            s.original,
            s.candidate,
            s.original,
            s.candidate,
            s.original
        ]
    );
    assert_eq!(c.borrow().shutdowns, 4);
}

#[test]
fn cancellation_never_reenters_saved_state_and_stale_cancel_has_no_effect() {
    let mut s = setup();
    let (mut slot, c, id) = task_slot(s.owner);
    slot.activate(id, &s.manager, &mut s.memory).unwrap();
    slot.run_slice(id).unwrap();
    let (mut scheduler, cpu) = running_scheduler(id);
    slot.account_slice(id, &mut scheduler, cpu).unwrap();
    assert_eq!(
        slot.cancel_suspended(TaskId {
            generation: 2,
            ..id
        }),
        Err(task::Error::Identity)
    );
    let o = slot.cancel_suspended(id).unwrap();
    assert_eq!(o.reason, Reason::Cancelled);
    assert!(slot.cancel_suspended(id).is_err());
    assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
    assert!(slot.run_slice(id).is_err());
    retained(&mut s.manager, &s.handles);
    slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
    assert_eq!(
        s.machine.borrow().writes,
        [s.candidate, s.original, s.original]
    );
    assert_eq!(c.borrow().entries, 1);
}

#[test]
fn budget_yield_requires_settlement_before_replenishment_or_cancellation() {
    let mut s = setup();
    let (mut slot, c, id) = task_slot(s.owner);
    c.borrow_mut().budget_yield = true;
    let (mut scheduler, cpu) = running_scheduler(id);
    for n in 1..=5 {
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert_eq!(
            slot.run_slice(id).unwrap().event,
            task::Event::BudgetYield { syscalls: n * 64 }
        );
        assert_eq!(slot.state(id), Ok(task::State::Suspended));
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert!(slot.cancel_suspended(id).is_err());
        retained(&mut s.manager, &s.handles);
        slot.account_slice(id, &mut scheduler, cpu).unwrap();
        assert!(slot.account_slice(id, &mut scheduler, cpu).is_err());
        scheduler.yield_current(cpu).unwrap();
        scheduler.dispatch(cpu).unwrap();
    }
    let o = slot.cancel_suspended(id).unwrap();
    assert_eq!((o.reason, o.syscalls), (Reason::Cancelled, 320));
    assert_eq!(slot.runtime(id).unwrap().charged_slices, 5);
    assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
    slot.reap(id, &mut s.manager, &mut s.memory).unwrap();
    assert_eq!(c.borrow().entries, 5);
}

#[test]
fn budget_yield_cleanup_failure_retains_the_charge_and_cannot_resume() {
    for fail_quiesce in [false, true] {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        c.borrow_mut().budget_yield = true;
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        if fail_quiesce {
            c.borrow_mut().fail_quiesce = true;
        } else {
            s.machine.borrow_mut().write_error = true;
        }
        assert!(slot.run_slice(id).is_err());
        assert_eq!(slot.state(id), Ok(task::State::Quarantined));
        assert_eq!(slot.runtime(id).unwrap().pending_ticks, Some(1));
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert!(slot.cancel_suspended(id).is_err());
        retained(&mut s.manager, &s.handles);
        let (mut scheduler, cpu) = running_scheduler(id);
        slot.account_slice(id, &mut scheduler, cpu).unwrap();
        c.borrow_mut().fail_quiesce = false;
        s.machine.borrow_mut().write_error = false;
        slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        assert_eq!(c.borrow().entries, 1);
    }
}

#[test]
fn quantum_execute_quiesce_or_suspend_failure_cannot_resume_or_free() {
    for case in 0..3 {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        match case {
            0 => c.borrow_mut().fail_execute = true,
            1 => c.borrow_mut().fail_quiesce = true,
            _ => s.machine.borrow_mut().write_error = true,
        }
        assert!(slot.run_slice(id).is_err());
        assert_eq!(slot.state(id), Ok(task::State::Quarantined));
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert!(slot.run_slice(id).is_err());
        assert!(slot.cancel_suspended(id).is_err());
        retained(&mut s.manager, &s.handles);
        c.borrow_mut().fail_execute = false;
        c.borrow_mut().fail_quiesce = false;
        s.machine.borrow_mut().write_error = false;
        if case == 0 {
            assert!(slot.runtime(id).unwrap().unknown);
            assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
        } else {
            let (mut scheduler, cpu) = running_scheduler(id);
            assert_eq!(slot.account_slice(id, &mut scheduler, cpu), Ok(1));
            slot.abandon(id, &mut s.manager, &mut s.memory).unwrap();
        }
        assert_eq!(c.borrow().entries, 1);
    }
}

#[test]
fn forged_quantum_observations_never_admit_suspended_state() {
    for case in 0..4 {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        if case == 3 {
            c.borrow_mut().zero_ticks = true;
        } else {
            c.borrow_mut().corrupt = [1, 2, 4][case];
        }
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        assert!(slot.run_slice(id).is_err());
        assert_eq!(slot.state(id), Ok(task::State::Quarantined));
        retained(&mut s.manager, &s.handles);
        assert!(slot.runtime(id).unwrap().unknown);
        assert!(slot.abandon(id, &mut s.manager, &mut s.memory).is_err());
    }
}

#[test]
fn suspended_resume_revalidates_cpu_identity_and_root_mappings_before_effects() {
    for case in 0..2 {
        let mut s = setup();
        let (mut slot, c, id) = task_slot(s.owner);
        slot.activate(id, &s.manager, &mut s.memory).unwrap();
        slot.run_slice(id).unwrap();
        let (mut scheduler, cpu) = running_scheduler(id);
        slot.account_slice(id, &mut scheduler, cpu).unwrap();
        if case == 0 {
            s.machine.borrow_mut().snapshot.cpu_id += 1;
        } else {
            s.memory.pages.get_mut(&s.candidate).unwrap()[0] = 0;
        }
        assert!(slot.activate(id, &s.manager, &mut s.memory).is_err());
        assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
        assert_eq!(c.borrow().entries, 1);
        retained(&mut s.manager, &s.handles);
        assert!(slot.run_slice(id).is_err());
    }
}

impl Cpu for Hardware {
    fn snapshot(&mut self) -> Result<Snapshot, CpuError> {
        let mut machine = self.0.borrow_mut();
        let index = machine.reads;
        machine.reads += 1;
        if machine.fail_read == Some(index) {
            return Err(CpuError::Hardware);
        }
        if machine.change_cpu_on_read == Some(index) {
            machine.snapshot.cpu_id += 1;
        }
        Ok(machine.snapshot)
    }

    fn write_root(&mut self, root: u64) -> Result<(), CpuError> {
        let mut machine = self.0.borrow_mut();
        machine.writes.push(root);
        if !machine.suppress_write {
            machine.snapshot.cr3 = root;
        }
        if machine.change_cpu_after_write {
            machine.snapshot.cpu_id += 1;
        }
        if machine.write_error {
            Err(CpuError::Hardware)
        } else {
            Ok(())
        }
    }
}

struct Setup {
    image: ImageAdmission,
    manager: PhysicalMemoryManager,
    memory: Memory,
    owner: CpuImage<Hardware>,
    machine: Rc<RefCell<Machine>>,
    handles: std::vec::Vec<AllocationHandle>,
    original: u64,
    candidate: u64,
}

fn setup() -> Setup {
    setup_with_timer(false)
}

fn setup_with_timer(timer: bool) -> Setup {
    let fixture = Fixture::new();
    let handles = fixture.handles();
    let core = fixture.core;
    let (manager, memory, prepared) = if timer {
        ready_timer(fixture)
    } else {
        ready(fixture)
    };
    let image = prepared.admission().unwrap();
    let candidate = image.root_physical;
    let machine = Rc::new(RefCell::new(Machine {
        snapshot: Snapshot {
            cpu_id: 7,
            active_cpus: 1,
            cr0: 1 | (1 << 16) | (1 << 31),
            cr3: core.page_table_root_physical,
            cr4: 1 << 5,
            efer: (1 << 8) | (1 << 10) | (1 << 11),
            rflags: 2,
        },
        writes: std::vec::Vec::new(),
        reads: 0,
        fail_read: None,
        write_error: false,
        suppress_write: false,
        change_cpu_after_write: false,
        change_cpu_on_read: None,
    }));
    let owner = CpuImage::new(prepared, Hardware(Rc::clone(&machine)), core);
    Setup {
        image,
        manager,
        memory,
        owner,
        machine,
        handles,
        original: core.page_table_root_physical,
        candidate,
    }
}

#[test]
fn cpu_activation_and_retirement_keep_exact_ownership_until_flush_and_detach() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.state(), State::Active);
    retained(&mut s.manager, &s.handles);
    // Hardware A/D writes after activation must not defeat safe inactive cleanup.
    s.memory.pages.get_mut(&s.candidate).unwrap()[0] |= A;
    let stack_index = ((USER_WINDOW_START + 3 * PAGE_BYTES) >> 12 & 511) as usize;
    s.memory
        .pages
        .get_mut(&(s.candidate + 3 * PAGE_BYTES))
        .unwrap()[stack_index] |= A | D;
    let parts = s
        .owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("retire {e:?}"));
    assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    assert_eq!(s.memory.pages[&s.candidate][STACK_SLOT], 0);
    assert_eq!(s.memory.pages[&s.candidate][KERNEL_SLOT], 0);
    for h in s.handles {
        s.manager.validate_allocation(h).unwrap();
    }
    s.manager.free(parts.stack).unwrap();
    s.manager.free(parts.stack_tables).unwrap();
}

#[test]
fn unsupported_cpu_contexts_and_nonexact_roots_never_write_cr3() {
    for case in 0..12 {
        let mut s = setup();
        {
            let mut m = s.machine.borrow_mut();
            match case {
                0 => m.snapshot.active_cpus = 2,
                1 => m.snapshot.rflags |= 1 << 9,
                2 => m.snapshot.cr0 &= !1,
                3 => m.snapshot.cr0 &= !(1 << 16),
                4 => m.snapshot.cr0 &= !(1 << 31),
                5 => m.snapshot.cr4 &= !(1 << 5),
                6 => m.snapshot.cr4 |= 1 << 7,
                7 => m.snapshot.cr4 |= 1 << 12,
                8 => m.snapshot.cr4 |= 1 << 17,
                9 => m.snapshot.efer &= !(1 << 11),
                10 => m.snapshot.cr3 |= 8,
                _ => m.snapshot.cr3 = s.candidate,
            }
        }
        assert!(
            s.owner.activate(&s.manager, &mut s.memory).is_err(),
            "{case}"
        );
        assert_eq!(s.owner.state(), State::Inactive);
        assert!(s.machine.borrow().writes.is_empty());
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn fresh_mapping_and_manager_replay_precede_any_cpu_exposure() {
    for case in 0..4 {
        let mut s = setup();
        match case {
            0 => s.memory.pages.get_mut(&s.candidate).unwrap()[77] = 0x700003,
            1 => {
                s.memory
                    .pages
                    .get_mut(&(s.original + 3 * PAGE_BYTES))
                    .unwrap()[0] |= W
            }
            2 => s.memory.fail_finish = true,
            _ => s.memory.fail_read = Some(s.memory.reads),
        }
        assert!(s.owner.activate(&s.manager, &mut s.memory).is_err());
        assert!(s.machine.borrow().writes.is_empty());
        retained(&mut s.manager, &s.handles);
    }
    let mut s = setup();
    let foreign = Fixture::new();
    assert_eq!(
        s.owner.activate(&foreign.manager, &mut s.memory),
        Err(CpuError::Prepared(Error::Ownership))
    );
    assert!(s.machine.borrow().writes.is_empty());
}

#[test]
fn context_is_sampled_again_after_mapping_audit() {
    let mut s = setup();
    s.machine.borrow_mut().change_cpu_on_read = Some(1);
    assert_eq!(
        s.owner.activate(&s.manager, &mut s.memory),
        Err(CpuError::Context)
    );
    assert!(s.machine.borrow().writes.is_empty());
    assert_eq!(s.owner.state(), State::Inactive);
}

#[test]
fn failed_cr3_writes_with_or_without_effect_stay_quarantined_until_new_flush() {
    for effect in [false, true] {
        let mut s = setup();
        s.machine.borrow_mut().write_error = true;
        s.machine.borrow_mut().suppress_write = !effect;
        assert_eq!(
            s.owner.activate(&s.manager, &mut s.memory),
            Err(CpuError::Hardware)
        );
        assert_eq!(s.owner.state(), State::Uncertain);
        retained(&mut s.manager, &s.handles);
        s.machine.borrow_mut().write_error = false;
        s.machine.borrow_mut().suppress_write = false;
        s.owner
            .retire(&mut s.manager, &mut s.memory)
            .unwrap_or_else(|(e, _)| panic!("recovery {e:?}"));
        assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    }
}

#[test]
fn failed_readback_and_silent_noop_do_not_create_active_or_releasable_owners() {
    for case in 0..3 {
        let mut s = setup();
        match case {
            0 => s.machine.borrow_mut().suppress_write = true,
            1 => s.machine.borrow_mut().fail_read = Some(2),
            _ => s.machine.borrow_mut().change_cpu_after_write = true,
        }
        assert!(s.owner.activate(&s.manager, &mut s.memory).is_err());
        assert_eq!(s.owner.state(), State::Uncertain);
        drop(s.owner);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn second_activation_is_rejected_before_touching_hardware() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    let reads = s.machine.borrow().reads;
    assert_eq!(
        s.owner.activate(&s.manager, &mut s.memory),
        Err(CpuError::State)
    );
    assert_eq!(s.machine.borrow().reads, reads);
    assert_eq!(s.machine.borrow().writes, [s.candidate]);
}

#[test]
fn failed_restoration_and_postrestore_readback_never_detach_pages() {
    for case in 0..4 {
        let mut s = setup();
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        let writes = s.memory.writes;
        match case {
            0 => s.machine.borrow_mut().write_error = true,
            1 => s.machine.borrow_mut().suppress_write = true,
            2 => {
                let n = s.machine.borrow().reads;
                s.machine.borrow_mut().fail_read = Some(n + 1);
            }
            _ => s.machine.borrow_mut().change_cpu_after_write = true,
        }
        let (_, owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
        assert_eq!(owner.state(), State::Uncertain);
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn restoration_retry_flushes_even_when_original_root_is_already_observed() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    s.machine.borrow_mut().write_error = true;
    let (_, owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
    assert_eq!(s.machine.borrow().snapshot.cr3, s.original);
    retained(&mut s.manager, &s.handles);
    s.machine.borrow_mut().write_error = false;
    owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("retry {e:?}"));
    assert_eq!(
        s.machine.borrow().writes,
        [s.candidate, s.original, s.original]
    );
}

#[test]
fn foreign_manager_cpu_migration_mode_changes_and_unknown_root_prevent_cleanup() {
    for case in 0..5 {
        let mut s = setup();
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        let writes = s.memory.writes;
        let mut foreign = Fixture::new();
        match case {
            0 => s.machine.borrow_mut().snapshot.cpu_id += 1,
            1 => s.machine.borrow_mut().snapshot.active_cpus = 2,
            2 => s.machine.borrow_mut().snapshot.cr4 |= 1 << 7,
            3 => s.machine.borrow_mut().snapshot.cr3 = 0x99000,
            _ => (),
        }
        let manager = if case == 4 {
            &mut foreign.manager
        } else {
            &mut s.manager
        };
        let (_, owner) = s.owner.retire(manager, &mut s.memory).err().unwrap();
        assert_eq!(owner.state(), State::Active);
        assert_eq!(s.machine.borrow().writes, [s.candidate]);
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn postrestore_detachment_failure_keeps_tokens_and_retries_with_fresh_flush() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    s.memory.fail_write = Some(s.memory.writes);
    let (_, owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
    assert_eq!(owner.state(), State::Restored);
    retained(&mut s.manager, &s.handles);
    s.memory.fail_write = None;
    owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("cleanup retry {e:?}"));
    assert_eq!(
        s.machine.borrow().writes,
        [s.candidate, s.original, s.original]
    );
}

#[test]
fn never_exposed_owner_can_detach_without_inventing_a_cpu_flush() {
    let mut s = setup();
    s.owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("cancel {e:?}"));
    assert!(s.machine.borrow().writes.is_empty());
    assert_eq!(s.machine.borrow().reads, 0);
}

struct TimerDriver {
    machine: Rc<RefCell<Machine>>,
    execute_error: bool,
    stop_error: bool,
    change_context: bool,
    malformed: u8,
    calls: std::vec::Vec<&'static str>,
}

impl TimerDriver {
    fn new(s: &Setup) -> Self {
        Self {
            machine: Rc::clone(&s.machine),
            execute_error: false,
            stop_error: false,
            change_context: false,
            malformed: 0,
            calls: std::vec::Vec::new(),
        }
    }
}

impl crate::user_entry::timer::Driver for TimerDriver {
    fn execute(
        &mut self,
        root: u64,
        mappings: timer::Mappings,
    ) -> Result<timer::Observation, timer::Error> {
        assert_eq!(mappings, timer::Mappings::fixture());
        assert_eq!(self.machine.borrow().snapshot.cr3, root);
        self.calls.push("execute");
        if self.execute_error {
            return Err(timer::Error::Hardware);
        }
        Ok(timer::Observation {
            observed_root: root + u64::from(self.malformed == 1),
            deliveries: if self.malformed == 2 { 0 } else { 3 },
            eois: if self.malformed == 3 { 2 } else { 3 },
        })
    }
    fn quiesce(&mut self, root: u64, _: timer::Mappings) -> Result<(), timer::Error> {
        assert_eq!(self.machine.borrow().snapshot.cr3, root);
        self.calls.push("stop");
        if self.change_context {
            self.machine.borrow_mut().snapshot.cpu_id += 1;
        }
        if self.stop_error {
            Err(timer::Error::Hardware)
        } else {
            Ok(())
        }
    }
}

#[test]
fn timer_success_shutdown_precedes_root_restore_and_leaf_cleanup() {
    let mut s = setup_with_timer(true);
    let mut driver = TimerDriver::new(&s);
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.exercise_timer(&mut driver).unwrap().deliveries, 3);
    assert_eq!(driver.calls, ["execute", "stop"]);
    retained(&mut s.manager, &s.handles);
    let parts = s
        .owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("{e:?}"));
    for page in parts.stack_tables.start_page..parts.stack_tables.start_page + 3 {
        assert_eq!(s.memory.pages[&(page * PAGE_BYTES)], [0; 512]);
    }
    assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
}

#[test]
fn failed_timer_execution_still_runs_verified_shutdown() {
    let mut s = setup_with_timer(true);
    let mut driver = TimerDriver::new(&s);
    driver.execute_error = true;
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(
        s.owner.exercise_timer(&mut driver),
        Err(CpuError::Timer(timer::Error::Hardware))
    );
    assert_eq!(driver.calls, ["execute", "stop"]);
    assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_ok());
}

#[test]
fn failed_shutdown_prevents_cr3_restore_and_all_memory_release_until_retry() {
    for execute_error in [false, true] {
        let mut s = setup_with_timer(true);
        let mut driver = TimerDriver::new(&s);
        driver.execute_error = execute_error;
        driver.stop_error = true;
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        assert!(s.owner.exercise_timer(&mut driver).is_err());
        let writes = s.memory.writes;
        let (error, mut owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
        assert_eq!(error, CpuError::Timer(timer::Error::State));
        assert_eq!(s.machine.borrow().writes, [s.candidate]);
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
        assert!(owner.exercise_timer(&mut driver).is_err());
        assert_eq!(driver.calls, ["execute", "stop"]);
        driver.stop_error = false;
        owner.quiesce_timer(&mut driver).unwrap();
        assert!(owner.retire(&mut s.manager, &mut s.memory).is_ok());
    }
}

#[test]
fn context_drift_during_shutdown_never_admits_retirement() {
    let mut s = setup_with_timer(true);
    let mut driver = TimerDriver::new(&s);
    driver.change_context = true;
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.exercise_timer(&mut driver), Err(CpuError::Context));
    assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_err());
    assert_eq!(s.machine.borrow().writes, [s.candidate]);
    retained(&mut s.manager, &s.handles);
}

#[test]
fn malformed_timer_observations_fail_even_after_safe_shutdown() {
    for malformed in 1..=3 {
        let mut s = setup_with_timer(true);
        let mut driver = TimerDriver::new(&s);
        driver.malformed = malformed;
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        assert_eq!(
            s.owner.exercise_timer(&mut driver),
            Err(CpuError::Timer(timer::Error::Hardware))
        );
        assert_eq!(driver.calls, ["execute", "stop"]);
        assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_ok());
    }
}

#[test]
fn timer_requires_active_mapped_owner_without_touching_driver() {
    for mapped in [false, true] {
        let mut s = setup_with_timer(mapped);
        let mut driver = TimerDriver::new(&s);
        assert!(s.owner.exercise_timer(&mut driver).is_err());
        if !mapped {
            s.owner.activate(&s.manager, &mut s.memory).unwrap();
            assert!(s.owner.exercise_timer(&mut driver).is_err());
        }
        assert!(driver.calls.is_empty());
    }
}

struct UserDriver {
    machine: Rc<RefCell<Machine>>,
    fail_execute: bool,
    fail_detach: bool,
    drift: bool,
    malformed: u8,
    calls: std::vec::Vec<&'static str>,
}
impl UserDriver {
    fn new(s: &Setup) -> Self {
        Self {
            machine: Rc::clone(&s.machine),
            fail_execute: false,
            fail_detach: false,
            drift: false,
            malformed: 0,
            calls: std::vec::Vec::new(),
        }
    }
}
impl privilege::Driver for UserDriver {
    fn execute(
        &mut self,
        image: ImageAdmission,
    ) -> Result<privilege::Observation, privilege::Error> {
        self.calls.push("enter");
        assert_eq!(self.machine.borrow().snapshot.cr3, image.root_physical);
        if self.fail_execute {
            return Err(privilege::Error::Hardware);
        }
        Ok(privilege::Observation {
            root: image.root_physical + u64::from(self.malformed == 1),
            traps: if self.malformed == 2 { 6 } else { 7 },
            cpl: if self.malformed == 3 { 0 } else { 3 },
            restored: self.malformed != 4,
        })
    }
    fn quiesce(&mut self, root: u64) -> Result<(), privilege::Error> {
        self.calls.push("detach");
        assert_eq!(self.machine.borrow().snapshot.cr3, root);
        if self.drift {
            self.machine.borrow_mut().snapshot.cpu_id += 1;
        }
        if self.fail_detach {
            Err(privilege::Error::Hardware)
        } else {
            Ok(())
        }
    }
}

#[test]
fn user_entry_success_or_error_always_detaches_before_retirement() {
    for error in [false, true] {
        let mut s = setup();
        let mut d = UserDriver::new(&s);
        d.fail_execute = error;
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        assert_eq!(s.owner.exercise_user(&mut d).is_err(), error);
        assert_eq!(d.calls, ["enter", "detach"]);
        retained(&mut s.manager, &s.handles);
        assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_ok());
        assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    }
}

#[test]
fn failed_user_detach_keeps_stack_retained_blocks_timer_and_retries() {
    let mut s = setup_with_timer(true);
    let mut d = UserDriver::new(&s);
    d.fail_detach = true;
    let mut timer = TimerDriver::new(&s);
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert!(s.owner.exercise_user(&mut d).is_err());
    assert!(s.owner.exercise_timer(&mut timer).is_err());
    assert!(timer.calls.is_empty());
    let writes = s.memory.writes;
    let (error, mut owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
    assert_eq!(error, CpuError::User(privilege::Error::State));
    assert_eq!(s.memory.writes, writes);
    assert_eq!(s.machine.borrow().writes, [s.candidate]);
    retained(&mut s.manager, &s.handles);
    assert!(owner.exercise_user(&mut d).is_err());
    assert_eq!(d.calls, ["enter", "detach"]);
    d.fail_detach = false;
    owner.quiesce_user(&mut d).unwrap();
    assert!(owner.retire(&mut s.manager, &mut s.memory).is_ok());
}

#[test]
fn user_driver_context_drift_never_releases_private_entry_stack() {
    let mut s = setup();
    let mut d = UserDriver::new(&s);
    d.drift = true;
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.exercise_user(&mut d), Err(CpuError::Context));
    assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_err());
    retained(&mut s.manager, &s.handles);
}

#[test]
fn user_observations_cannot_claim_wrong_root_cpl_or_incomplete_return() {
    for malformed in 1..=4 {
        let mut s = setup();
        let mut d = UserDriver::new(&s);
        d.malformed = malformed;
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        assert_eq!(
            s.owner.exercise_user(&mut d),
            Err(CpuError::User(privilege::Error::Hardware))
        );
        assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_ok());
    }
}

#[test]
fn pending_timer_shutdown_or_inactive_owner_cannot_enter_user() {
    let mut s = setup_with_timer(true);
    let mut d = UserDriver::new(&s);
    assert!(s.owner.exercise_user(&mut d).is_err());
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    let mut timer = TimerDriver::new(&s);
    timer.stop_error = true;
    assert!(s.owner.exercise_timer(&mut timer).is_err());
    assert!(s.owner.exercise_user(&mut d).is_err());
    assert!(d.calls.is_empty());
}
