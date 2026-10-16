//! A retained cleanup wait cannot be woken or reused as a completed task.
use super::*;

impl Scheduler {
    pub(crate) fn require_unadmitted_cleanup(&self, id: TaskId) -> Result<(), Error> {
        self.validate()?;
        let task = self.tasks.get(id.index()).ok_or(Error::TaskRange)?;
        if task.generation == 0
            || (task.state == TaskState::Dead && task.generation < id.generation)
        {
            Ok(())
        } else {
            Err(Error::State)
        }
    }

    /// Called only after the owned image has revoked authority and entered
    /// reclamation. An unentered image may have one uncharged scheduler selection.
    pub(crate) fn park_reclamation(
        &mut self,
        id: TaskId,
        cpu: CpuId,
        unentered: bool,
    ) -> Result<(), Error> {
        self.validate()?;
        self.require_online(cpu)?;
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.assigned_cpu != Some(cpu)
            || task.unmeasured_dispatches != 0
            || self.mutex_owner == Some(id)
            || self.external_priority_donation[index] != 0
            || matches!(
                task.wait_kind,
                WaitKind::Mutex | WaitKind::ExternalLock | WaitKind::Reclamation
            )
            || (unentered
                && (task.runtime_ticks != 0
                    || task.charged_dispatch != 0
                    || task.dispatch_count > 1))
            || (!unentered && task.charged_dispatch != task.dispatch_count)
        {
            return Err(Error::State);
        }
        let mut staged = *self;
        match task.state {
            TaskState::Runnable => staged.queues[cpu.index()].remove(id)?,
            TaskState::Running => {
                if staged.current[cpu.index()] != Some(id) {
                    return Err(Error::Invariant);
                }
                staged.current[cpu.index()] = None;
            }
            TaskState::Blocked => {}
            _ => return Err(Error::State),
        }
        let task = &mut staged.tasks[index];
        task.state = TaskState::Blocked;
        task.wait_kind = WaitKind::Reclamation;
        task.wake_reason = WakeReason::None;
        task.queued_cpu = None;
        task.bypass_count = 0;
        staged.bump_sequence();
        staged.validate()?;
        *self = staged;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cleanup_wait_rejects_all_wakes_reuse_and_activation_until_teardown() {
        let mut s = Scheduler::new(1).unwrap();
        let cpu = CpuId::new(0).unwrap();
        let id = s.create_task(0, 1, 16, 1).unwrap();
        s.activate(id, cpu).unwrap();
        s.park_reclamation(id, cpu, true).unwrap();
        let before = s.task_snapshot(id).unwrap();
        assert_eq!(before.wait_kind, WaitKind::Reclamation);
        assert!(s.cancel_wait(id, cpu).is_err());
        assert!(s.signal_wait(id, cpu).is_err());
        assert!(s.timeout_wait(id, cpu).is_err());
        assert!(s.wake_ipc_waiter(id, cpu, WakeReason::OwnerGone).is_err());
        assert!(s.wake_lock_waiter(id, cpu, WakeReason::Cancelled).is_err());
        assert!(s.activate(id, cpu).is_err());
        assert!(s.create_task(0, 2, 16, 1).is_err());
        assert!(s.park_reclamation(id, cpu, true).is_err());
        assert_eq!(s.task_snapshot(id).unwrap(), before);
        assert_eq!(s.summary().teardown_count, 0);
        s.teardown(id).unwrap();
        assert!(
            s.require_unadmitted_cleanup(TaskId::new(0, 2).unwrap())
                .is_ok()
        );
        assert!(s.require_unadmitted_cleanup(id).is_err());
        s.create_task(0, 2, 16, 1).unwrap();
    }

    #[test]
    fn cleanup_park_is_transactional_and_requires_settled_local_execution() {
        let mut s = Scheduler::new(3).unwrap();
        let cpu = CpuId::new(0).unwrap();
        let id = s.create_task(0, 1, 16, 1).unwrap();
        s.activate(id, cpu).unwrap();
        s.dispatch(cpu).unwrap();
        let before = s.task_snapshot(id).unwrap();
        assert!(
            s.park_reclamation(id, CpuId::new(1).unwrap(), true)
                .is_err()
        );
        assert!(
            s.park_reclamation(TaskId::new(0, 2).unwrap(), cpu, true)
                .is_err()
        );
        assert!(s.park_reclamation(id, cpu, false).is_err());
        assert_eq!(s.task_snapshot(id).unwrap(), before);
        assert_eq!(s.current(cpu), Ok(Some(id)));
        s.account_dispatch(cpu, id, 1, 0, 17).unwrap();
        assert!(s.park_reclamation(id, cpu, true).is_err());
        s.park_reclamation(id, cpu, false).unwrap();
        assert_eq!(s.current(cpu), Ok(None));
        assert_eq!(s.task_snapshot(id).unwrap().runtime_ticks, 17);
        s.validate().unwrap();
    }

    #[test]
    fn cleanup_park_rejects_lock_ownership_and_unmeasured_dispatches() {
        let mut s = Scheduler::new(1).unwrap();
        let cpu = CpuId::new(0).unwrap();
        let id = s.create_task(0, 1, 16, 1).unwrap();
        s.activate(id, cpu).unwrap();
        s.dispatch(cpu).unwrap();
        s.account_dispatch(cpu, id, 1, 0, 1).unwrap();
        s.lock_mutex(cpu).unwrap();
        assert!(s.park_reclamation(id, cpu, false).is_err());
        s.unlock_mutex(cpu).unwrap();
        s.yield_current(cpu).unwrap();
        s.dispatch(cpu).unwrap();
        s.record_unmeasured_dispatch(cpu, id, 2, 1).unwrap();
        assert!(s.park_reclamation(id, cpu, false).is_err());
        assert!(
            s.require_unadmitted_cleanup(TaskId::new(0, 2).unwrap())
                .is_err()
        );
        s.validate().unwrap();
    }
}
