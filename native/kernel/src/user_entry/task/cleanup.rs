//! Bounded deferred retry remains inside the non-Clone task-slot owner.
use super::*;
use crate::scheduler::{CpuId, Scheduler, TaskState, WaitKind};

pub const CONTRACT_ID: &str = "PCLEANUP2";
pub const FIRST_DELAY: u32 = 64;
pub const MAX_ATTEMPTS: u8 = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Snapshot {
    pub attempts: u8,
    pub next_dispatch: Option<u32>,
    pub admitted: bool,
}

#[derive(Clone, Copy)]
pub(super) struct Deferred {
    snapshot: Snapshot,
    cpu: CpuId,
    last_dispatch: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Progress {
    Waiting,
    Retried,
    Exhausted,
    Complete(Outcome),
}

impl<H: Cpu, D: Driver> Slot<H, D> {
    pub fn cleanup_status(&self, id: TaskId) -> Result<Option<Snapshot>, Error> {
        Ok(self.owned(id)?.deferred.map(|d| d.snapshot))
    }

    /// Only already-revoked, quiescent retained images enter deferred cleanup.
    /// A deadline overflow fails before scheduler or retry-state mutation.
    pub fn defer_reclamation(
        &mut self,
        id: TaskId,
        scheduler: &mut Scheduler,
        cpu: CpuId,
        admitted: bool,
    ) -> Result<Snapshot, Error> {
        let task = self.owned(id)?;
        if task.state != State::Reclaiming
            || task.cpu.is_some()
            || task.deferred.is_some()
            || task.pending_charge.is_some()
            || task.runtime.unknown
            || task
                .reclaim
                .as_ref()
                .is_none_or(|r| r.remaining_pages() == 0)
        {
            return Err(Error::State);
        }
        self.outcome(id)?;
        scheduler.current(cpu).map_err(Error::Accounting)?;
        let unentered = task.runtime == Runtime::default();
        if !admitted && !unentered {
            return Err(Error::State);
        }
        let now = scheduler.summary().dispatch_count;
        let next = now.checked_add(FIRST_DELAY).ok_or(Error::Exhausted)?;
        let sid =
            crate::scheduler::TaskId::new(id.slot, id.generation).map_err(Error::Accounting)?;
        if admitted {
            if scheduler
                .task_snapshot(sid)
                .map_err(Error::Accounting)?
                .runtime_ticks
                != task.runtime.charged_ticks
            {
                return Err(Error::State);
            }
            scheduler
                .park_reclamation(sid, cpu, unentered)
                .map_err(Error::Accounting)?;
        } else {
            scheduler
                .require_unadmitted_cleanup(sid)
                .map_err(Error::Accounting)?;
        }
        let snapshot = Snapshot {
            attempts: 0,
            next_dispatch: Some(next),
            admitted,
        };
        self.owned_mut(id)?.deferred = Some(Deferred {
            snapshot,
            cpu,
            last_dispatch: now,
        });
        Ok(snapshot)
    }

    /// One bounded whole-image attempt at most. Backoff counts real scheduler
    /// dispatches, not wall time. Exhaustion retains ownership with no completion.
    pub fn reclaim_deferred<M: TableMemory>(
        &mut self,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
        scheduler: &Scheduler,
    ) -> Result<Progress, Error> {
        let task = self.owned(id)?;
        let mut deferred = task.deferred.ok_or(Error::State)?;
        if task.state != State::Reclaiming
            || task.pending_charge.is_some()
            || task.runtime.unknown
            || scheduler
                .current(deferred.cpu)
                .map_err(Error::Accounting)?
                .is_some()
        {
            return Err(Error::State);
        }
        let sid =
            crate::scheduler::TaskId::new(id.slot, id.generation).map_err(Error::Accounting)?;
        if deferred.snapshot.admitted {
            let s = scheduler.task_snapshot(sid).map_err(Error::Accounting)?;
            if s.state != TaskState::Blocked
                || s.wait_kind != WaitKind::Reclamation
                || s.assigned_cpu != Some(deferred.cpu)
                || s.runtime_ticks != task.runtime.charged_ticks
                || s.unmeasured_dispatches != 0
            {
                return Err(Error::State);
            }
        } else {
            scheduler
                .require_unadmitted_cleanup(sid)
                .map_err(Error::Accounting)?;
        }
        let now = scheduler.summary().dispatch_count;
        if now < deferred.last_dispatch {
            return Err(Error::Accounting(crate::scheduler::Error::Invariant));
        }
        deferred.last_dispatch = now;
        self.owned_mut(id)?.deferred = Some(deferred);
        let Some(due) = deferred.snapshot.next_dispatch else {
            return Ok(Progress::Exhausted);
        };
        if now < due {
            return Ok(Progress::Waiting);
        }
        deferred.snapshot.attempts = deferred
            .snapshot
            .attempts
            .checked_add(1)
            .ok_or(Error::Exhausted)?;
        if deferred.snapshot.attempts > MAX_ATTEMPTS {
            return Err(Error::State);
        }
        deferred.snapshot.next_dispatch = if deferred.snapshot.attempts == MAX_ATTEMPTS {
            None
        } else {
            now.checked_add(FIRST_DELAY << deferred.snapshot.attempts)
        };
        self.owned_mut(id)?.deferred = Some(deferred);
        match self.reclaim_inner(id, manager, memory) {
            Ok(outcome) => Ok(Progress::Complete(outcome)),
            Err(Error::Reclamation(_)) => Ok(if deferred.snapshot.next_dispatch.is_some() {
                Progress::Retried
            } else {
                Progress::Exhausted
            }),
            Err(error) => Err(error),
        }
    }
}
