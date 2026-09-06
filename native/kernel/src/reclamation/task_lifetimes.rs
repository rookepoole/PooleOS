//! PKLIFE1: serialized scheduler ownership and pinned, inactive address spaces.
//! No CPU grace period, CR3 switch, raw-memory lifetime or capability is implied.

#![forbid(unsafe_code)]

use super::{Handle, Limits, Owner, Pin, Pool};
use crate::physical_memory::{PhysicalMemoryError, PhysicalMemoryManager, RetainedAllocation};
use crate::scheduler_smp::{self as sched, CpuId, SmpScheduler, TaskId, TaskState};
use crate::virtual_memory::{AddressSpace, MAX_FRAMES};

pub const CONTRACT_ID: &str = "PKLIFE1";
const CAPACITY: usize = sched::TASK_CAPACITY;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Pool(super::Error),
    Scheduler(sched::Error),
    Attached,
    Draining,
    Occupied,
    Missing,
    Stale,
    GenerationExhausted,
    AddressSpace,
    PhysicalMemory(PhysicalMemoryError),
    DuplicateRoot,
    NotDead,
    Retired,
    NotRetired,
}

impl From<sched::Error> for Error {
    fn from(value: sched::Error) -> Self {
        Self::Scheduler(value)
    }
}

impl From<super::Error> for Error {
    fn from(value: super::Error) -> Self {
        Self::Pool(value)
    }
}

/// Owns the actual PKVM1 object and mandatory retention of its tables and frames.
/// No mutable address-space or retention-token access escapes through a reader.
/// Dropping resources retains physical allocations; it never fabricates quiescence.
///
/// ```compile_fail
/// use poolekernel::reclamation::task_lifetimes::Resources;
/// use poolekernel::virtual_memory::AddressSpace;
/// fn unretained(space: AddressSpace) {
///     let _ = Resources::new(space, ());
/// }
/// ```
///
/// ```compile_fail
/// use poolekernel::reclamation::task_lifetimes::Resources;
/// use poolekernel::virtual_memory::AddressSpace;
/// fn bypass(resources: &mut Resources<()>) -> &mut AddressSpace {
///     resources.address_space()
/// }
/// ```
pub struct Resources<T> {
    space: AddressSpace,
    payload: T,
    retained: [Option<RetainedAllocation>; MAX_FRAMES + 1],
}

impl<T> Resources<T> {
    /// Failure returns the original objects and leaves all retention unchanged.
    #[allow(clippy::result_large_err)]
    pub fn new(
        space: AddressSpace,
        payload: T,
        manager: &mut PhysicalMemoryManager,
    ) -> Result<Self, (Error, AddressSpace, T)> {
        let summary = space.summary();
        if summary.root_active || summary.root_released || summary.root_generation == 0 {
            return Err((Error::AddressSpace, space, payload));
        }
        match manager.retain_allocations(space.allocation_handles()) {
            Ok(retained) => Ok(Self {
                space,
                payload,
                retained,
            }),
            Err(error) => Err((Error::PhysicalMemory(error), space, payload)),
        }
    }

    pub const fn address_space(&self) -> &AddressSpace {
        &self.space
    }

    pub const fn payload(&self) -> &T {
        &self.payload
    }

    /// Only an exclusive owner (never a pinned reader) can end retention.
    /// This returns an inactive PKVM1 object; unmap receipts and physical release
    /// still belong to that object. Failure returns the complete retained owner.
    #[allow(clippy::result_large_err)]
    pub fn into_parts(
        self,
        manager: &mut PhysicalMemoryManager,
    ) -> Result<(AddressSpace, T), (Error, Self)> {
        let Self {
            space,
            payload,
            retained,
        } = self;
        match manager.release_retentions(retained) {
            Ok(()) => Ok((space, payload)),
            Err((error, retained)) => Err((
                Error::PhysicalMemory(error),
                Self {
                    space,
                    payload,
                    retained,
                },
            )),
        }
    }
}

pub type Reader<'a, T> = Pin<'a, Resources<T>, CAPACITY>;

/// One scheduler namespace per storage lifetime; no public pool bypass exists.
///
/// ```compile_fail
/// use poolekernel::reclamation::{Limits, task_lifetimes::Storage};
/// use poolekernel::scheduler_smp::TaskId;
/// fn invalid(storage: &mut Storage<u64>) {
///     let tasks = storage.attach().unwrap();
///     let reader = tasks.pin(TaskId::new(0, 1).unwrap()).unwrap();
///     drop(tasks);
///     *storage = Storage::new(Limits::default()).unwrap();
///     println!("{}", reader.payload());
/// }
/// ```
///
/// ```compile_fail
/// use poolekernel::reclamation::task_lifetimes::Reader;
/// fn invalid(reader: Reader<'_, u64>, manager: &mut poolekernel::physical_memory::PhysicalMemoryManager) {
///     let _owned_address_space = reader.into_parts(manager);
/// }
/// ```
pub struct Storage<T> {
    pool: Pool<Resources<T>, CAPACITY>,
    attached: bool,
}

impl<T> Storage<T> {
    pub fn new(limits: Limits) -> Result<Self, Error> {
        Ok(Self {
            pool: Pool::new(limits)?,
            attached: false,
        })
    }

    /// The exclusive borrow prevents a second controller or storage replacement
    /// while this controller or any of its readers can still access resources.
    pub fn attach(&mut self) -> Result<TaskLifetimes<'_, T>, Error> {
        if self.attached {
            return Err(Error::Attached);
        }
        self.attached = true;
        Ok(TaskLifetimes {
            store: self,
            scheduler: SmpScheduler::new(),
            entries: [const { None }; CAPACITY],
            generations: [0; CAPACITY],
            draining: false,
        })
    }
}

struct Binding<'a, T> {
    task: TaskId,
    handle: Handle<'a, Resources<T>, CAPACITY>,
    owner: Owner,
    root: u64,
    retired: bool,
}

/// Owns the real PKSCHED4 controller. TaskId is namespace-local, not authority.
/// Mutations are serialized by &mut self; only scoped readers cross threads.
/// Dropping this controller seals admission and retains unreclaimed objects in
/// Storage. It cannot fabricate a grace period or free physical allocations.
pub struct TaskLifetimes<'a, T> {
    store: &'a Storage<T>,
    scheduler: SmpScheduler,
    entries: [Option<Binding<'a, T>>; CAPACITY],
    generations: [u32; CAPACITY],
    draining: bool,
}

impl<'a, T> TaskLifetimes<'a, T> {
    fn binding(&self, id: TaskId) -> Result<&Binding<'a, T>, Error> {
        TaskId::new(id.slot, id.generation)?;
        let binding = self.entries[id.index()].as_ref().ok_or(Error::Missing)?;
        if binding.task != id {
            return Err(Error::Stale);
        }
        Ok(binding)
    }

    /// Failed admission returns both the original address space and payload.
    #[allow(clippy::result_large_err)]
    pub fn create(
        &mut self,
        slot: u8,
        priority: u8,
        affinity: u8,
        resources: Resources<T>,
    ) -> Result<TaskId, (Error, Resources<T>)> {
        let validate = || {
            if self.draining {
                return Err(Error::Draining);
            }
            TaskId::new(slot, 1)?;
            if priority == 0 || priority > 31 {
                return Err(sched::Error::Priority.into());
            }
            if affinity == 0 || affinity & !sched::ONLINE_MASK != 0 {
                return Err(sched::Error::Affinity.into());
            }
            if self.entries[slot as usize].is_some() {
                return Err(Error::Occupied);
            }
            let generation = self.generations[slot as usize]
                .checked_add(1)
                .ok_or(Error::GenerationExhausted)?;
            let space = resources.space.summary();
            if space.root_active || space.root_released || space.root_generation == 0 {
                return Err(Error::AddressSpace);
            }
            if self
                .entries
                .iter()
                .flatten()
                .any(|item| item.root == space.root_physical)
            {
                return Err(Error::DuplicateRoot);
            }
            Ok((generation, space.root_generation, space.root_physical))
        };
        let (generation, root_generation, root) = match validate() {
            Ok(value) => value,
            Err(error) => return Err((error, resources)),
        };
        let owner = Owner {
            task_generation: u64::from(generation),
            address_space_generation: root_generation,
        };
        let handle = match self.store.pool.publish(owner, resources) {
            Ok(handle) => handle,
            Err((error, resources)) => return Err((error.into(), resources)),
        };
        let task = match self
            .scheduler
            .create_task(slot, generation, priority, affinity)
        {
            Ok(task) => task,
            Err(error) => {
                // No handle escaped, no reader exists, and this controller is
                // the pool's only metadata writer. Rollback cannot contend.
                self.store
                    .pool
                    .retire(handle, owner)
                    .expect("PKLIFE1 unpublished retire");
                let resources = self
                    .store
                    .pool
                    .reclaim(handle, owner)
                    .expect("PKLIFE1 unpublished reclaim");
                return Err((error.into(), resources));
            }
        };
        self.generations[slot as usize] = generation;
        self.entries[slot as usize] = Some(Binding {
            task,
            handle,
            owner,
            root,
            retired: false,
        });
        Ok(task)
    }

    pub fn pin(&self, task: TaskId) -> Result<Reader<'a, T>, Error> {
        let binding = self.binding(task)?;
        if self.draining {
            return Err(Error::Draining);
        }
        Ok(self.store.pool.pin(binding.handle)?)
    }

    pub fn activate(&mut self, task: TaskId, cpu: CpuId) -> Result<(), Error> {
        self.binding(task)?;
        if self.draining {
            return Err(Error::Draining);
        }
        Ok(self.scheduler.activate(task, cpu)?)
    }

    pub fn block(&mut self, task: TaskId) -> Result<(), Error> {
        self.binding(task)?;
        Ok(self.scheduler.block_runnable(task)?)
    }

    /// Removal from scheduler ownership is necessary, but not a hardware ACK.
    pub fn retire(&mut self, task: TaskId) -> Result<(), Error> {
        if self.binding(task)?.retired {
            return Err(Error::Retired);
        }
        if self.scheduler.has_pending() {
            return Err(sched::Error::PendingBusy.into());
        }
        if self.scheduler.task_snapshot(task)?.state != TaskState::Dead {
            return Err(Error::NotDead);
        }
        let binding = self.binding(task)?;
        self.store.pool.retire(binding.handle, binding.owner)?;
        self.entries[task.index()]
            .as_mut()
            .expect("PKLIFE1 binding")
            .retired = true;
        Ok(())
    }

    pub fn cancel(&mut self, task: TaskId) -> Result<(), Error> {
        self.binding(task)?;
        self.scheduler.cancel_task(task)?;
        self.retire(task)
    }

    /// A never-activated task has no run-queue owner. Activate then cancel it on
    /// an allowed online lane so the existing scheduler performs its teardown.
    pub fn cancel_dormant(&mut self, task: TaskId) -> Result<(), Error> {
        self.binding(task)?;
        if self.scheduler.has_pending() {
            return Err(sched::Error::PendingBusy.into());
        }
        let state = self.scheduler.task_snapshot(task)?;
        if state.state != TaskState::Dormant {
            return Err(sched::Error::State.into());
        }
        let cpu = self.scheduler.select_least_loaded(state.affinity_mask)?;
        self.scheduler.activate(task, cpu)?;
        self.cancel(task)
    }

    pub fn dispatch_local(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        if self.draining {
            return Err(Error::Draining);
        }
        let task = self.scheduler.dispatch_local(cpu)?;
        self.retire(task)?;
        Ok(task)
    }

    pub fn stage_dispatch(
        &mut self,
        cpu: CpuId,
        attempt: u64,
        sequence: u64,
    ) -> Result<sched::TransferTicket, Error> {
        if self.draining {
            return Err(Error::Draining);
        }
        Ok(self.scheduler.stage_dispatch(cpu, attempt, sequence)?)
    }

    /// Carries the existing scheduler's exact receipt checks, not CPU proof.
    pub fn acknowledge(
        &mut self,
        ticket: sched::TransferTicket,
        ack: sched::RemoteAck,
    ) -> Result<(), Error> {
        Ok(self.scheduler.acknowledge(ticket, ack)?)
    }

    pub fn complete_current(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        let task = self.scheduler.complete_current(cpu)?;
        self.retire(task)?;
        Ok(task)
    }

    pub fn stage_offline_probe(
        &mut self,
        task: TaskId,
        attempt: u64,
        sequence: u64,
    ) -> Result<sched::TransferTicket, Error> {
        self.binding(task)?;
        if self.draining {
            return Err(Error::Draining);
        }
        Ok(self
            .scheduler
            .stage_offline_probe(task, sched::OFFLINE_PROBE_CPU, attempt, sequence)?)
    }

    pub fn timeout_offline(&mut self, ticket: sched::TransferTicket) -> Result<(), Error> {
        Ok(self.scheduler.timeout(ticket)?)
    }

    pub fn reclaim(&mut self, task: TaskId) -> Result<Resources<T>, Error> {
        let binding = self.binding(task)?;
        if !binding.retired {
            return Err(Error::NotRetired);
        }
        let resources = self.store.pool.reclaim(binding.handle, binding.owner)?;
        self.entries[task.index()] = None;
        Ok(resources)
    }

    pub fn begin_shutdown(&mut self) -> Result<(), Error> {
        self.store.pool.begin_shutdown()?;
        self.draining = true;
        Ok(())
    }

    pub fn is_drained(&self) -> Result<bool, Error> {
        Ok(self.draining
            && self.entries.iter().all(Option::is_none)
            && self.store.pool.is_drained()?)
    }

    pub fn scheduler(&self) -> &SmpScheduler {
        &self.scheduler
    }

    pub fn snapshot(&mut self, task: TaskId) -> Result<sched::TaskSnapshot, Error> {
        self.binding(task)?;
        Ok(self.scheduler.task_snapshot(task)?)
    }
}

impl<T> Drop for TaskLifetimes<'_, T> {
    fn drop(&mut self) {
        self.store
            .pool
            .begin_shutdown()
            .expect("PKLIFE1 exclusive shutdown");
    }
}
