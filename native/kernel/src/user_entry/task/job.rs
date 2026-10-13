//! Bounded cancel-on-parent-death relationship, independent of revocable handles.
//! Task slots keep the memory owners; this record cannot free by identity alone.
use super::*;

pub const CONTRACT_ID: &str = "PJOB1";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Identity {
    id: TaskId,
    root: u64,
    root_generation: u64,
}
impl Identity {
    pub(super) fn new(id: TaskId, image: ImageAdmission) -> Self {
        Self {
            id,
            root: image.root_physical,
            root_generation: image.root_generation,
        }
    }
}

/// Trusted supervisor policy selects membership before admission. Independent
/// services are not enrolled. Parent detachment does not erase this obligation.
/// Dropping the job cannot release the memory retained by its task slots.
///
/// ```compile_fail
/// use poolekernel::user_entry::task::job::Job;
/// fn duplicate(job: &Job<2>) -> Job<2> { job.clone() }
/// ```
#[must_use = "job children must remain owned until reclaimed"]
pub struct Job<const N: usize> {
    owner: Identity,
    closing: bool,
    children: [Option<Identity>; N],
}
impl<const N: usize> Job<N> {
    pub fn new<H: Cpu, D: Driver>(owner: &Slot<H, D>, id: TaskId) -> Result<Self, Error> {
        let task = owner.owned(id)?;
        if N == 0 || N > crate::scheduler::MAX_TASKS || task.state != State::Prepared {
            return Err(Error::State);
        }
        Ok(Self {
            owner: task.identity,
            closing: false,
            children: [None; N],
        })
    }

    pub fn adopt<H: Cpu, D: Driver>(
        &mut self,
        child: &Slot<H, D>,
        id: TaskId,
    ) -> Result<(), Error> {
        let task = child.owned(id)?;
        if self.closing
            || task.state != State::Prepared
            || id.slot == self.owner.id.slot
            || task.identity.root == self.owner.root
            || self
                .children
                .iter()
                .flatten()
                .any(|c| c.id.slot == id.slot || c.root == task.identity.root)
        {
            return Err(Error::State);
        }
        let place = self
            .children
            .iter_mut()
            .find(|c| c.is_none())
            .ok_or(Error::Occupied)?;
        *place = Some(task.identity);
        Ok(())
    }

    /// Called from a settled terminal slot before parent reclamation/IPC detach.
    /// Repeated observation of the same terminal owner is harmless, never reopening.
    pub fn owner_stopped<H: Cpu, D: Driver>(
        &mut self,
        owner: &Slot<H, D>,
        id: TaskId,
    ) -> Result<Outcome, Error> {
        let task = owner.owned(id)?;
        if task.identity != self.owner || task.pending_charge.is_some() || task.runtime.unknown {
            return Err(Error::Identity);
        }
        let outcome = owner.outcome(id)?;
        self.closing = true;
        Ok(outcome)
    }

    pub fn is_closing(&self) -> bool {
        self.closing
    }
    pub fn child_count(&self) -> usize {
        self.children.iter().flatten().count()
    }
    pub fn next_orphan(&self) -> Option<TaskId> {
        if self.closing {
            self.children.iter().flatten().next().map(|c| c.id)
        } else {
            None
        }
    }

    fn member<H: Cpu, D: Driver>(&self, child: &Slot<H, D>, id: TaskId) -> Result<usize, Error> {
        let task = child.owned(id)?;
        self.children
            .iter()
            .position(|c| *c == Some(task.identity))
            .ok_or(Error::Identity)
    }

    pub fn cancel_orphan<H: Cpu, D: SliceDriver>(
        &self,
        child: &mut Slot<H, D>,
        id: TaskId,
        wait: Option<crate::capability_ipc::wait::Ticket>,
    ) -> Result<Outcome, Error> {
        self.member(child, id)?;
        if !self.closing {
            return Err(Error::State);
        }
        match (child.state(id)?, wait) {
            (State::Prepared, None) => child.cancel_prepared(id),
            (State::Suspended, None) => child.cancel_suspended(id),
            (State::Waiting, Some(ticket)) => child.cancel_waiting(id, ticket),
            (State::Terminated | State::Reclaiming, None) => child.outcome(id),
            _ => Err(Error::State),
        }
    }

    /// Membership survives every cleanup error, including partially released
    /// allocations. A missing/different slot cannot clear it using a claimed result.
    pub fn reclaim_child<H: Cpu, D: Driver, M: TableMemory>(
        &mut self,
        child: &mut Slot<H, D>,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<Outcome, Error> {
        let index = self.member(child, id)?;
        let outcome = child.reclaim(id, manager, memory)?;
        self.children[index] = None;
        Ok(outcome)
    }
}
