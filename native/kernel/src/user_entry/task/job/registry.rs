//! Exclusive single-supervisor job graph and bounded round-robin orphan selection.
use super::*;

pub const CONTRACT_ID: &str = "PJOBREG1";

struct Entry<const C: usize> {
    job: Job<C>,
    next_child: usize,
}

/// Diagnostic identities only; operations still authenticate the retained slot.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Work {
    pub owner: TaskId,
    pub child: TaskId,
}

/// Owns jobs until closed and drained. Dropping this registry retains slot claims.
/// No mutable Job reference or removal of a live obligation is exposed.
#[must_use = "registry jobs must remain owned until drained"]
pub struct Registry<const J: usize, const C: usize> {
    entries: [Option<Entry<C>>; J],
    next_owner: usize,
}

impl<const J: usize, const C: usize> Registry<J, C> {
    pub fn new() -> Result<Self, Error> {
        if J == 0 || C == 0 || J > crate::scheduler::MAX_TASKS || C > crate::scheduler::MAX_TASKS {
            return Err(Error::State);
        }
        Ok(Self {
            entries: [const { None }; J],
            next_owner: 0,
        })
    }

    fn index(&self, id: TaskId) -> Result<usize, Error> {
        self.entries
            .iter()
            .position(|e| e.as_ref().is_some_and(|e| e.job.owner.id == id))
            .ok_or(Error::Identity)
    }

    fn contains_owner(&self, identity: Identity) -> bool {
        self.entries
            .iter()
            .flatten()
            .any(|e| e.job.owner == identity)
    }

    pub fn create<H: Cpu, D: Driver>(
        &mut self,
        owner: &mut Slot<H, D>,
        id: TaskId,
    ) -> Result<(), Error> {
        let task = owner.owned(id)?;
        if self
            .entries
            .iter()
            .flatten()
            .any(|e| e.job.owner.id.slot == id.slot || e.job.owner.root == task.identity.root)
        {
            return Err(Error::Occupied);
        }
        if self
            .entries
            .iter()
            .flatten()
            .flat_map(|e| e.job.children.iter().flatten())
            .any(|c| (c.id.slot == id.slot || c.root == task.identity.root) && *c != task.identity)
        {
            return Err(Error::Identity);
        }
        if let Some(parent) = task.parent_job {
            if !task.registry_owned
                || !self
                    .entries
                    .iter()
                    .flatten()
                    .any(|e| e.job.owner == parent && e.job.children.contains(&Some(task.identity)))
            {
                return Err(Error::Identity);
            }
        } else if task.registry_owned {
            return Err(Error::Identity);
        }
        let place = self
            .entries
            .iter()
            .position(Option::is_none)
            .ok_or(Error::Occupied)?;
        let job = Job::new_inner(owner, id, true)?;
        self.entries[place] = Some(Entry { job, next_child: 0 });
        Ok(())
    }

    pub fn owner(&mut self, id: TaskId) -> Result<Owner<'_, J, C>, Error> {
        let index = self.index(id)?;
        Ok(Owner {
            registry: self,
            index,
        })
    }

    fn adopt<H: Cpu, D: Driver>(
        &mut self,
        index: usize,
        child: &mut Slot<H, D>,
        id: TaskId,
    ) -> Result<(), Error> {
        let task = child.owned(id)?;
        let registered = self.contains_owner(task.identity);
        if self.entries.iter().flatten().any(|e| {
            ((e.job.owner.id.slot == id.slot || e.job.owner.root == task.identity.root)
                && e.job.owner != task.identity)
                || e.job
                    .children
                    .iter()
                    .flatten()
                    .any(|c| c.id.slot == id.slot || c.root == task.identity.root)
        }) {
            return Err(Error::Identity);
        }
        if (task.registry_owned || task.owned_job != OwnerState::Unused) && !registered {
            return Err(Error::Identity);
        }
        let mut cursor = self.entries[index]
            .as_ref()
            .ok_or(Error::Missing)?
            .job
            .owner;
        // At most J ancestors exist; even corrupted cyclic ancestry fails closed.
        for _ in 0..J {
            if cursor == task.identity {
                return Err(Error::State);
            }
            match self
                .entries
                .iter()
                .flatten()
                .find(|e| e.job.children.contains(&Some(cursor)))
            {
                Some(parent) => cursor = parent.job.owner,
                None => {
                    return self.entries[index]
                        .as_mut()
                        .ok_or(Error::Missing)?
                        .job
                        .adopt_inner(child, id, true);
                }
            }
        }
        Err(Error::State)
    }

    /// One opportunity per call. Failures/waiting do not pin either cursor.
    /// Selection alone does not change task state, revoke, write or reset a budget.
    pub fn next_orphan(&mut self) -> Option<Work> {
        for step in 0..J {
            let index = (self.next_owner + step) % J;
            let Some(entry) = self.entries[index].as_mut() else {
                continue;
            };
            if !entry.job.closing {
                continue;
            }
            for child_step in 0..C {
                let slot = (entry.next_child + child_step) % C;
                if let Some(child) = entry.job.children[slot] {
                    entry.next_child = (slot + 1) % C;
                    self.next_owner = (index + 1) % J;
                    return Some(Work {
                        owner: entry.job.owner.id,
                        child: child.id,
                    });
                }
            }
        }
        None
    }

    pub fn job_count(&self) -> usize {
        self.entries.iter().flatten().count()
    }

    /// Retires only the supervisor record, never the owner's task or memory.
    pub fn retire(&mut self, id: TaskId) -> Result<(), Error> {
        let index = self.index(id)?;
        let job = &self.entries[index].as_ref().ok_or(Error::Missing)?.job;
        if !job.closing || job.child_count() != 0 {
            return Err(Error::State);
        }
        self.entries[index] = None;
        Ok(())
    }
}

/// Short-lived exclusive view. Admission cannot escape registry topology checks.
pub struct Owner<'a, const J: usize, const C: usize> {
    registry: &'a mut Registry<J, C>,
    index: usize,
}

impl<const J: usize, const C: usize> Owner<'_, J, C> {
    fn job(&self) -> &Job<C> {
        &self.registry.entries[self.index]
            .as_ref()
            .expect("owned registry entry")
            .job
    }
    fn job_mut(&mut self) -> &mut Job<C> {
        &mut self.registry.entries[self.index]
            .as_mut()
            .expect("owned registry entry")
            .job
    }
    pub fn adopt<H: Cpu, D: Driver>(
        &mut self,
        child: &mut Slot<H, D>,
        id: TaskId,
    ) -> Result<(), Error> {
        self.registry.adopt(self.index, child, id)
    }
    pub fn owner_stopped<H: Cpu, D: Driver>(
        &mut self,
        owner: &mut Slot<H, D>,
        id: TaskId,
    ) -> Result<Outcome, Error> {
        self.job_mut().owner_stopped(owner, id)
    }
    pub fn is_closing(&self) -> bool {
        self.job().is_closing()
    }
    pub fn child_count(&self) -> usize {
        self.job().child_count()
    }
    pub fn cancel_orphan<H: Cpu, D: SliceDriver>(
        &self,
        child: &mut Slot<H, D>,
        id: TaskId,
        wait: Option<crate::capability_ipc::wait::Ticket>,
    ) -> Result<Outcome, Error> {
        self.job().cancel_orphan(child, id, wait)
    }
    pub fn reclaim_child<H: Cpu, D: Driver, M: TableMemory>(
        &mut self,
        child: &mut Slot<H, D>,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<Outcome, Error> {
        self.job_mut().reclaim_child(child, id, manager, memory)
    }
    pub fn reclaim_deferred_child<H: Cpu, D: Driver, M: TableMemory>(
        &mut self,
        child: &mut Slot<H, D>,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
        scheduler: &crate::scheduler::Scheduler,
    ) -> Result<cleanup::Progress, Error> {
        self.job_mut()
            .reclaim_deferred_child(child, id, manager, memory, scheduler)
    }
    pub fn recover_exhausted_child<H: Cpu, D: Driver, M: TableMemory>(
        &mut self,
        child: &mut Slot<H, D>,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
        scheduler: &crate::scheduler::Scheduler,
    ) -> Result<cleanup::Recovery, Error> {
        self.job_mut()
            .recover_exhausted_child(child, id, manager, memory, scheduler)
    }
}
