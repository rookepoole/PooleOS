use core::sync::atomic::{AtomicU32, Ordering};

pub const CONTRACT_ID: &str = "PKSCHED1";
pub const MAX_CPUS: usize = 4;
pub const MAX_TASKS: usize = 8;
pub const RUN_QUEUE_CAPACITY: usize = MAX_TASKS;
pub const MAX_BYPASS: u8 = (MAX_TASKS - 1) as u8;
pub const MIN_PRIORITY: u8 = 1;
pub const MAX_PRIORITY: u8 = 31;
pub const COMPLETE_CPU_MASK: u8 = (1 << MAX_CPUS) - 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuId(u8);

impl CpuId {
    pub const fn new(value: u8) -> Result<Self, Error> {
        if value < MAX_CPUS as u8 {
            Ok(Self(value))
        } else {
            Err(Error::CpuRange)
        }
    }

    pub const fn index(self) -> usize {
        self.0 as usize
    }

    pub const fn mask(self) -> u8 {
        1 << self.0
    }

    pub const fn value(self) -> u8 {
        self.0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TaskId {
    pub slot: u8,
    pub generation: u32,
}

impl TaskId {
    pub const fn new(slot: u8, generation: u32) -> Result<Self, Error> {
        if slot as usize >= MAX_TASKS {
            Err(Error::TaskRange)
        } else if generation == 0 {
            Err(Error::Generation)
        } else {
            Ok(Self { slot, generation })
        }
    }

    pub const fn index(self) -> usize {
        self.slot as usize
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum TaskState {
    Dormant = 0,
    Runnable = 1,
    Running = 2,
    Blocked = 3,
    Dead = 4,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum WakeReason {
    None = 0,
    Cancelled = 1,
    TimedOut = 2,
    LockGranted = 3,
    OwnerGone = 4,
    Signalled = 5,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum WaitKind {
    None = 0,
    Event = 1,
    Mutex = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    CpuRange,
    CpuOffline,
    CpuBusy,
    CpuIdle,
    TaskRange,
    TaskMissing,
    Generation,
    GenerationStale,
    Priority,
    Affinity,
    State,
    QueueFull,
    DuplicateRunnable,
    QueueMissing,
    WakePending,
    WaitKind,
    MutexRecursive,
    MutexNotOwner,
    MutexWaitersFull,
    LockOwner,
    BypassOverflow,
    Invariant,
    RefcountOverflow,
    RefcountUnderflow,
    LockBusy,
    LockRecursive,
    UnlockNotOwner,
    OwnerToken,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TaskSnapshot {
    pub id: TaskId,
    pub state: TaskState,
    pub base_priority: u8,
    pub effective_priority: u8,
    pub affinity_mask: u8,
    pub assigned_cpu: Option<CpuId>,
    pub wake_reason: WakeReason,
    pub wait_kind: WaitKind,
    pub bypass_count: u8,
    pub dispatch_count: u32,
    pub runtime_ticks: u64,
}

#[derive(Clone, Copy)]
struct Task {
    generation: u32,
    state: TaskState,
    base_priority: u8,
    effective_priority: u8,
    affinity_mask: u8,
    assigned_cpu: Option<CpuId>,
    queued_cpu: Option<CpuId>,
    wake_reason: WakeReason,
    wait_kind: WaitKind,
    bypass_count: u8,
    dispatch_count: u32,
    runtime_ticks: u64,
}

impl Task {
    const fn empty() -> Self {
        Self {
            generation: 0,
            state: TaskState::Dormant,
            base_priority: MIN_PRIORITY,
            effective_priority: MIN_PRIORITY,
            affinity_mask: 0,
            assigned_cpu: None,
            queued_cpu: None,
            wake_reason: WakeReason::None,
            wait_kind: WaitKind::None,
            bypass_count: 0,
            dispatch_count: 0,
            runtime_ticks: 0,
        }
    }

    const fn id(self, slot: usize) -> TaskId {
        TaskId {
            slot: slot as u8,
            generation: self.generation,
        }
    }
}

#[derive(Clone, Copy)]
struct RunQueue {
    entries: [Option<TaskId>; RUN_QUEUE_CAPACITY],
    len: usize,
}

impl RunQueue {
    const fn empty() -> Self {
        Self {
            entries: [None; RUN_QUEUE_CAPACITY],
            len: 0,
        }
    }

    fn push(&mut self, id: TaskId) -> Result<(), Error> {
        if self.entries[..self.len].contains(&Some(id)) {
            return Err(Error::DuplicateRunnable);
        }
        if self.len == RUN_QUEUE_CAPACITY {
            return Err(Error::QueueFull);
        }
        self.entries[self.len] = Some(id);
        self.len += 1;
        Ok(())
    }

    fn remove_at(&mut self, index: usize) -> Result<TaskId, Error> {
        if index >= self.len {
            return Err(Error::QueueMissing);
        }
        let id = self.entries[index].ok_or(Error::QueueMissing)?;
        for cursor in index..self.len - 1 {
            self.entries[cursor] = self.entries[cursor + 1];
        }
        self.len -= 1;
        self.entries[self.len] = None;
        Ok(id)
    }

    fn remove(&mut self, id: TaskId) -> Result<(), Error> {
        let index = self.entries[..self.len]
            .iter()
            .position(|entry| *entry == Some(id))
            .ok_or(Error::QueueMissing)?;
        self.remove_at(index).map(|_| ())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SchedulerSummary {
    pub sequence: u64,
    pub task_count: u8,
    pub runnable_count: u8,
    pub running_count: u8,
    pub blocked_count: u8,
    pub dead_count: u8,
    pub dispatch_count: u32,
    pub migration_count: u32,
    pub wake_count: u32,
    pub teardown_count: u32,
    pub priority_inheritance_count: u32,
}

#[derive(Clone, Copy)]
pub struct Scheduler {
    tasks: [Task; MAX_TASKS],
    queues: [RunQueue; MAX_CPUS],
    current: [Option<TaskId>; MAX_CPUS],
    cpu_online_mask: u8,
    mutex_owner: Option<TaskId>,
    mutex_waiters: [Option<TaskId>; MAX_TASKS],
    mutex_waiter_count: usize,
    sequence: u64,
    dispatch_count: u32,
    migration_count: u32,
    wake_count: u32,
    teardown_count: u32,
    priority_inheritance_count: u32,
}

impl Scheduler {
    pub const fn new(cpu_online_mask: u8) -> Result<Self, Error> {
        if cpu_online_mask == 0 || cpu_online_mask & !COMPLETE_CPU_MASK != 0 {
            return Err(Error::CpuRange);
        }
        Ok(Self {
            tasks: [Task::empty(); MAX_TASKS],
            queues: [RunQueue::empty(); MAX_CPUS],
            current: [None; MAX_CPUS],
            cpu_online_mask,
            mutex_owner: None,
            mutex_waiters: [None; MAX_TASKS],
            mutex_waiter_count: 0,
            sequence: 0,
            dispatch_count: 0,
            migration_count: 0,
            wake_count: 0,
            teardown_count: 0,
            priority_inheritance_count: 0,
        })
    }

    pub fn create_task(
        &mut self,
        slot: u8,
        generation: u32,
        priority: u8,
        affinity_mask: u8,
    ) -> Result<TaskId, Error> {
        let id = TaskId::new(slot, generation)?;
        if !(MIN_PRIORITY..=MAX_PRIORITY).contains(&priority) {
            return Err(Error::Priority);
        }
        if affinity_mask == 0
            || affinity_mask & !self.cpu_online_mask != 0
            || affinity_mask & !COMPLETE_CPU_MASK != 0
        {
            return Err(Error::Affinity);
        }
        let task = &mut self.tasks[id.index()];
        if task.generation != 0 && task.state != TaskState::Dead {
            return Err(Error::State);
        }
        if task.generation != 0 && generation <= task.generation {
            return Err(Error::GenerationStale);
        }
        *task = Task {
            generation,
            state: TaskState::Dormant,
            base_priority: priority,
            effective_priority: priority,
            affinity_mask,
            assigned_cpu: None,
            queued_cpu: None,
            wake_reason: WakeReason::None,
            wait_kind: WaitKind::None,
            bypass_count: 0,
            dispatch_count: 0,
            runtime_ticks: 0,
        };
        self.bump_sequence();
        Ok(id)
    }

    pub fn activate(&mut self, id: TaskId, cpu: CpuId) -> Result<(), Error> {
        self.require_online(cpu)?;
        let index = self.task_index(id)?;
        if self.tasks[index].state != TaskState::Dormant {
            return Err(Error::State);
        }
        if self.tasks[index].affinity_mask & cpu.mask() == 0 {
            return Err(Error::Affinity);
        }
        self.tasks[index].state = TaskState::Runnable;
        self.tasks[index].assigned_cpu = Some(cpu);
        self.enqueue(index, cpu)?;
        self.bump_sequence();
        self.validate()
    }

    pub fn dispatch(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        self.require_online(cpu)?;
        if self.current[cpu.index()].is_some() {
            return Err(Error::CpuBusy);
        }
        let queue_index = self.pick_queue_index(cpu)?;
        let id = self.queues[cpu.index()].remove_at(queue_index)?;
        let index = self.task_index(id)?;
        let selected_priority = self.tasks[index].effective_priority;
        for cursor in 0..self.queues[cpu.index()].len {
            let other = self.queues[cpu.index()].entries[cursor].ok_or(Error::Invariant)?;
            let other_index = self.task_index(other)?;
            if self.tasks[other_index].effective_priority == selected_priority {
                self.tasks[other_index].bypass_count = self.tasks[other_index]
                    .bypass_count
                    .checked_add(1)
                    .ok_or(Error::BypassOverflow)?;
                if self.tasks[other_index].bypass_count > MAX_BYPASS {
                    return Err(Error::BypassOverflow);
                }
            }
        }
        let task = &mut self.tasks[index];
        task.state = TaskState::Running;
        task.queued_cpu = None;
        task.assigned_cpu = Some(cpu);
        task.bypass_count = 0;
        task.dispatch_count = task.dispatch_count.checked_add(1).ok_or(Error::Invariant)?;
        self.current[cpu.index()] = Some(id);
        self.dispatch_count = self.dispatch_count.checked_add(1).ok_or(Error::Invariant)?;
        self.bump_sequence();
        self.validate()?;
        Ok(id)
    }

    pub fn account_tick(&mut self, cpu: CpuId, ticks: u64) -> Result<(), Error> {
        if ticks == 0 {
            return Err(Error::Invariant);
        }
        let id = self.current_id(cpu)?;
        let index = self.task_index(id)?;
        self.tasks[index].runtime_ticks = self.tasks[index]
            .runtime_ticks
            .checked_add(ticks)
            .ok_or(Error::Invariant)?;
        self.bump_sequence();
        self.validate()
    }

    pub fn yield_current(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        let id = self.take_current(cpu)?;
        let index = self.task_index(id)?;
        self.tasks[index].state = TaskState::Runnable;
        self.tasks[index].assigned_cpu = Some(cpu);
        self.enqueue(index, cpu)?;
        self.bump_sequence();
        self.validate()?;
        Ok(id)
    }

    pub fn block_current(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        let id = self.take_current(cpu)?;
        let index = self.task_index(id)?;
        let task = &mut self.tasks[index];
        task.state = TaskState::Blocked;
        task.assigned_cpu = Some(cpu);
        task.wait_kind = WaitKind::Event;
        task.wake_reason = WakeReason::None;
        task.bypass_count = 0;
        self.bump_sequence();
        self.validate()?;
        Ok(id)
    }

    pub fn cancel_wait(&mut self, id: TaskId, cpu: CpuId) -> Result<(), Error> {
        self.wake(id, cpu, WakeReason::Cancelled)
    }

    pub fn timeout_wait(&mut self, id: TaskId, cpu: CpuId) -> Result<(), Error> {
        self.wake(id, cpu, WakeReason::TimedOut)
    }

    pub fn signal_wait(&mut self, id: TaskId, cpu: CpuId) -> Result<(), Error> {
        self.wake(id, cpu, WakeReason::Signalled)
    }

    pub fn consume_wake(&mut self, cpu: CpuId) -> Result<WakeReason, Error> {
        let id = self.current_id(cpu)?;
        let index = self.task_index(id)?;
        let reason = self.tasks[index].wake_reason;
        if reason == WakeReason::None {
            return Err(Error::WakePending);
        }
        self.tasks[index].wake_reason = WakeReason::None;
        self.bump_sequence();
        self.validate()?;
        Ok(reason)
    }

    pub fn migrate(&mut self, id: TaskId, target: CpuId) -> Result<(), Error> {
        self.require_online(target)?;
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.state != TaskState::Runnable {
            return Err(Error::State);
        }
        if task.affinity_mask & target.mask() == 0 {
            return Err(Error::Affinity);
        }
        let source = task.queued_cpu.ok_or(Error::QueueMissing)?;
        if source == target {
            return Err(Error::State);
        }
        self.queues[source.index()].remove(id)?;
        self.tasks[index].queued_cpu = None;
        self.tasks[index].assigned_cpu = Some(target);
        if let Err(error) = self.enqueue(index, target) {
            self.tasks[index].assigned_cpu = Some(source);
            self.enqueue(index, source)?;
            return Err(error);
        }
        self.migration_count = self
            .migration_count
            .checked_add(1)
            .ok_or(Error::Invariant)?;
        self.bump_sequence();
        self.validate()
    }

    pub fn set_priority(&mut self, id: TaskId, priority: u8) -> Result<(), Error> {
        if !(MIN_PRIORITY..=MAX_PRIORITY).contains(&priority) {
            return Err(Error::Priority);
        }
        let index = self.task_index(id)?;
        self.tasks[index].base_priority = priority;
        self.recompute_effective_priorities()?;
        self.bump_sequence();
        self.validate()
    }

    pub fn lock_mutex(&mut self, cpu: CpuId) -> Result<(), Error> {
        let id = self.current_id(cpu)?;
        if self.mutex_owner == Some(id) {
            return Err(Error::MutexRecursive);
        }
        if self.mutex_owner.is_none() {
            self.mutex_owner = Some(id);
            self.bump_sequence();
            return self.validate();
        }
        if self.mutex_waiter_count == MAX_TASKS {
            return Err(Error::MutexWaitersFull);
        }
        self.take_current(cpu)?;
        let index = self.task_index(id)?;
        self.tasks[index].state = TaskState::Blocked;
        self.tasks[index].assigned_cpu = Some(cpu);
        self.tasks[index].wait_kind = WaitKind::Mutex;
        self.tasks[index].wake_reason = WakeReason::None;
        self.tasks[index].bypass_count = 0;
        self.mutex_waiters[self.mutex_waiter_count] = Some(id);
        self.mutex_waiter_count += 1;
        let before = self
            .mutex_owner
            .map(|owner| self.tasks[owner.index()].effective_priority);
        self.recompute_effective_priorities()?;
        let after = self
            .mutex_owner
            .map(|owner| self.tasks[owner.index()].effective_priority);
        if after > before {
            self.priority_inheritance_count = self
                .priority_inheritance_count
                .checked_add(1)
                .ok_or(Error::Invariant)?;
        }
        self.bump_sequence();
        self.validate()
    }

    pub fn unlock_mutex(&mut self, cpu: CpuId) -> Result<Option<TaskId>, Error> {
        let id = self.current_id(cpu)?;
        if self.mutex_owner != Some(id) {
            return Err(Error::MutexNotOwner);
        }
        let selected = self.highest_mutex_waiter()?;
        self.mutex_owner = selected;
        if let Some(waiter) = selected {
            self.remove_mutex_waiter(waiter)?;
            let waiter_index = self.task_index(waiter)?;
            let target = self.select_allowed_cpu(self.tasks[waiter_index].affinity_mask)?;
            self.tasks[waiter_index].state = TaskState::Runnable;
            self.tasks[waiter_index].wait_kind = WaitKind::None;
            self.tasks[waiter_index].wake_reason = WakeReason::LockGranted;
            self.tasks[waiter_index].assigned_cpu = Some(target);
            self.enqueue(waiter_index, target)?;
            self.wake_count = self.wake_count.checked_add(1).ok_or(Error::Invariant)?;
        }
        self.recompute_effective_priorities()?;
        self.bump_sequence();
        self.validate()?;
        Ok(selected)
    }

    pub fn teardown(&mut self, id: TaskId) -> Result<(), Error> {
        let index = self.task_index(id)?;
        match self.tasks[index].state {
            TaskState::Dormant => return Err(Error::State),
            TaskState::Runnable => {
                let cpu = self.tasks[index].queued_cpu.ok_or(Error::QueueMissing)?;
                self.queues[cpu.index()].remove(id)?;
            }
            TaskState::Running => {
                let cpu = self.tasks[index].assigned_cpu.ok_or(Error::CpuRange)?;
                if self.current[cpu.index()] != Some(id) {
                    return Err(Error::Invariant);
                }
                self.current[cpu.index()] = None;
            }
            TaskState::Blocked => {
                if self.tasks[index].wait_kind == WaitKind::Mutex {
                    self.remove_mutex_waiter(id)?;
                }
            }
            TaskState::Dead => return Err(Error::State),
        }
        if self.mutex_owner == Some(id) {
            self.mutex_owner = None;
            while self.mutex_waiter_count != 0 {
                let waiter = self.mutex_waiters[0].ok_or(Error::Invariant)?;
                self.remove_mutex_waiter(waiter)?;
                let waiter_index = self.task_index(waiter)?;
                let target = self.select_allowed_cpu(self.tasks[waiter_index].affinity_mask)?;
                self.tasks[waiter_index].state = TaskState::Runnable;
                self.tasks[waiter_index].wait_kind = WaitKind::None;
                self.tasks[waiter_index].wake_reason = WakeReason::OwnerGone;
                self.tasks[waiter_index].assigned_cpu = Some(target);
                self.enqueue(waiter_index, target)?;
                self.wake_count = self.wake_count.checked_add(1).ok_or(Error::Invariant)?;
            }
        }
        let task = &mut self.tasks[index];
        task.state = TaskState::Dead;
        task.assigned_cpu = None;
        task.queued_cpu = None;
        task.wake_reason = WakeReason::None;
        task.wait_kind = WaitKind::None;
        task.bypass_count = 0;
        task.effective_priority = task.base_priority;
        self.recompute_effective_priorities()?;
        self.teardown_count = self.teardown_count.checked_add(1).ok_or(Error::Invariant)?;
        self.bump_sequence();
        self.validate()
    }

    pub fn task_snapshot(&self, id: TaskId) -> Result<TaskSnapshot, Error> {
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        Ok(TaskSnapshot {
            id,
            state: task.state,
            base_priority: task.base_priority,
            effective_priority: task.effective_priority,
            affinity_mask: task.affinity_mask,
            assigned_cpu: task.assigned_cpu,
            wake_reason: task.wake_reason,
            wait_kind: task.wait_kind,
            bypass_count: task.bypass_count,
            dispatch_count: task.dispatch_count,
            runtime_ticks: task.runtime_ticks,
        })
    }

    pub fn current(&self, cpu: CpuId) -> Result<Option<TaskId>, Error> {
        self.require_online(cpu)?;
        Ok(self.current[cpu.index()])
    }

    pub fn queue_len(&self, cpu: CpuId) -> Result<usize, Error> {
        self.require_online(cpu)?;
        Ok(self.queues[cpu.index()].len)
    }

    pub fn mutex_owner(&self) -> Option<TaskId> {
        self.mutex_owner
    }

    pub fn summary(&self) -> SchedulerSummary {
        let mut summary = SchedulerSummary {
            sequence: self.sequence,
            task_count: 0,
            runnable_count: 0,
            running_count: 0,
            blocked_count: 0,
            dead_count: 0,
            dispatch_count: self.dispatch_count,
            migration_count: self.migration_count,
            wake_count: self.wake_count,
            teardown_count: self.teardown_count,
            priority_inheritance_count: self.priority_inheritance_count,
        };
        for task in self.tasks {
            if task.generation == 0 {
                continue;
            }
            summary.task_count += 1;
            match task.state {
                TaskState::Dormant => {}
                TaskState::Runnable => summary.runnable_count += 1,
                TaskState::Running => summary.running_count += 1,
                TaskState::Blocked => summary.blocked_count += 1,
                TaskState::Dead => summary.dead_count += 1,
            }
        }
        summary
    }

    pub fn validate(&self) -> Result<(), Error> {
        let mut queued = [0u8; MAX_TASKS];
        let mut running = [0u8; MAX_TASKS];
        for cpu_index in 0..MAX_CPUS {
            let cpu = CpuId(cpu_index as u8);
            let queue = &self.queues[cpu_index];
            if queue.len > RUN_QUEUE_CAPACITY {
                return Err(Error::Invariant);
            }
            for cursor in 0..queue.len {
                let id = queue.entries[cursor].ok_or(Error::Invariant)?;
                let task_index = self.task_index(id)?;
                let task = self.tasks[task_index];
                if task.state != TaskState::Runnable
                    || task.queued_cpu != Some(cpu)
                    || task.assigned_cpu != Some(cpu)
                    || task.affinity_mask & cpu.mask() == 0
                    || task.bypass_count > MAX_BYPASS
                {
                    return Err(Error::Invariant);
                }
                queued[task_index] = queued[task_index].checked_add(1).ok_or(Error::Invariant)?;
            }
            if queue.entries[queue.len..].iter().any(Option::is_some) {
                return Err(Error::Invariant);
            }
            if let Some(id) = self.current[cpu_index] {
                let task_index = self.task_index(id)?;
                let task = self.tasks[task_index];
                if task.state != TaskState::Running
                    || task.assigned_cpu != Some(cpu)
                    || task.queued_cpu.is_some()
                    || task.affinity_mask & cpu.mask() == 0
                {
                    return Err(Error::Invariant);
                }
                running[task_index] = running[task_index].checked_add(1).ok_or(Error::Invariant)?;
            }
        }
        for index in 0..MAX_TASKS {
            let task = self.tasks[index];
            if task.generation == 0 {
                if queued[index] != 0 || running[index] != 0 {
                    return Err(Error::Invariant);
                }
                continue;
            }
            match task.state {
                TaskState::Dormant => {
                    if queued[index] != 0
                        || running[index] != 0
                        || task.assigned_cpu.is_some()
                        || task.queued_cpu.is_some()
                    {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Runnable => {
                    if queued[index] != 1 || running[index] != 0 || task.queued_cpu.is_none() {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Running => {
                    if queued[index] != 0 || running[index] != 1 || task.queued_cpu.is_some() {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Blocked => {
                    if queued[index] != 0
                        || running[index] != 0
                        || task.wait_kind == WaitKind::None
                        || task.queued_cpu.is_some()
                        || task.bypass_count != 0
                    {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Dead => {
                    if queued[index] != 0
                        || running[index] != 0
                        || task.assigned_cpu.is_some()
                        || task.queued_cpu.is_some()
                        || task.wait_kind != WaitKind::None
                        || task.wake_reason != WakeReason::None
                        || task.bypass_count != 0
                    {
                        return Err(Error::Invariant);
                    }
                }
            }
            if task.effective_priority < task.base_priority
                || task.effective_priority > MAX_PRIORITY
                || task.affinity_mask == 0
                || task.affinity_mask & !self.cpu_online_mask != 0
            {
                return Err(Error::Invariant);
            }
            if task.wake_reason != WakeReason::None
                && !matches!(task.state, TaskState::Runnable | TaskState::Running)
            {
                return Err(Error::Invariant);
            }
        }
        let mut waiters = [0u8; MAX_TASKS];
        for cursor in 0..self.mutex_waiter_count {
            let id = self.mutex_waiters[cursor].ok_or(Error::Invariant)?;
            let index = self.task_index(id)?;
            let task = self.tasks[index];
            if task.state != TaskState::Blocked || task.wait_kind != WaitKind::Mutex {
                return Err(Error::Invariant);
            }
            waiters[index] = waiters[index].checked_add(1).ok_or(Error::Invariant)?;
        }
        if self.mutex_waiters[self.mutex_waiter_count..]
            .iter()
            .any(Option::is_some)
        {
            return Err(Error::Invariant);
        }
        for (index, task) in self.tasks.iter().enumerate() {
            if (task.wait_kind == WaitKind::Mutex) != (waiters[index] == 1) {
                return Err(Error::Invariant);
            }
            if waiters[index] > 1 {
                return Err(Error::DuplicateRunnable);
            }
        }
        if let Some(owner) = self.mutex_owner {
            let owner_index = self.task_index(owner)?;
            if !matches!(
                self.tasks[owner_index].state,
                TaskState::Runnable | TaskState::Running
            ) {
                return Err(Error::LockOwner);
            }
            let mut required = self.tasks[owner_index].base_priority;
            for cursor in 0..self.mutex_waiter_count {
                let waiter = self.mutex_waiters[cursor].ok_or(Error::Invariant)?;
                required = required.max(self.tasks[waiter.index()].base_priority);
            }
            if self.tasks[owner_index].effective_priority != required {
                return Err(Error::Invariant);
            }
        } else if self.mutex_waiter_count != 0 {
            return Err(Error::LockOwner);
        }
        Ok(())
    }

    fn task_index(&self, id: TaskId) -> Result<usize, Error> {
        if id.index() >= MAX_TASKS {
            return Err(Error::TaskRange);
        }
        let task = self.tasks[id.index()];
        if task.generation == 0 {
            Err(Error::TaskMissing)
        } else if task.generation != id.generation {
            Err(Error::GenerationStale)
        } else {
            Ok(id.index())
        }
    }

    fn require_online(&self, cpu: CpuId) -> Result<(), Error> {
        if cpu.index() >= MAX_CPUS {
            Err(Error::CpuRange)
        } else if self.cpu_online_mask & cpu.mask() == 0 {
            Err(Error::CpuOffline)
        } else {
            Ok(())
        }
    }

    fn enqueue(&mut self, index: usize, cpu: CpuId) -> Result<(), Error> {
        let task = self.tasks[index];
        if task.state != TaskState::Runnable || task.queued_cpu.is_some() {
            return Err(Error::State);
        }
        if task.affinity_mask & cpu.mask() == 0 {
            return Err(Error::Affinity);
        }
        let id = task.id(index);
        self.queues[cpu.index()].push(id)?;
        self.tasks[index].queued_cpu = Some(cpu);
        Ok(())
    }

    fn pick_queue_index(&self, cpu: CpuId) -> Result<usize, Error> {
        let queue = &self.queues[cpu.index()];
        if queue.len == 0 {
            return Err(Error::CpuIdle);
        }
        let mut selected = 0usize;
        for cursor in 1..queue.len {
            let candidate = queue.entries[cursor].ok_or(Error::Invariant)?;
            let incumbent = queue.entries[selected].ok_or(Error::Invariant)?;
            let candidate_task = self.tasks[self.task_index(candidate)?];
            let incumbent_task = self.tasks[self.task_index(incumbent)?];
            if candidate_task.effective_priority > incumbent_task.effective_priority
                || candidate_task.effective_priority == incumbent_task.effective_priority
                    && candidate_task.bypass_count > incumbent_task.bypass_count
            {
                selected = cursor;
            }
        }
        Ok(selected)
    }

    fn current_id(&self, cpu: CpuId) -> Result<TaskId, Error> {
        self.require_online(cpu)?;
        self.current[cpu.index()].ok_or(Error::CpuIdle)
    }

    fn take_current(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        self.require_online(cpu)?;
        self.current[cpu.index()].take().ok_or(Error::CpuIdle)
    }

    fn wake(&mut self, id: TaskId, cpu: CpuId, reason: WakeReason) -> Result<(), Error> {
        self.require_online(cpu)?;
        if reason == WakeReason::None || reason == WakeReason::LockGranted {
            return Err(Error::WakePending);
        }
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.state != TaskState::Blocked || task.wait_kind != WaitKind::Event {
            return Err(Error::WaitKind);
        }
        if task.wake_reason != WakeReason::None {
            return Err(Error::WakePending);
        }
        if task.affinity_mask & cpu.mask() == 0 {
            return Err(Error::Affinity);
        }
        self.tasks[index].state = TaskState::Runnable;
        self.tasks[index].wait_kind = WaitKind::None;
        self.tasks[index].wake_reason = reason;
        self.tasks[index].assigned_cpu = Some(cpu);
        self.enqueue(index, cpu)?;
        self.wake_count = self.wake_count.checked_add(1).ok_or(Error::Invariant)?;
        self.bump_sequence();
        self.validate()
    }

    fn highest_mutex_waiter(&self) -> Result<Option<TaskId>, Error> {
        let mut selected = None;
        for cursor in 0..self.mutex_waiter_count {
            let candidate = self.mutex_waiters[cursor].ok_or(Error::Invariant)?;
            selected = match selected {
                None => Some(candidate),
                Some(incumbent) => {
                    if self.tasks[candidate.index()].base_priority
                        > self.tasks[incumbent.index()].base_priority
                    {
                        Some(candidate)
                    } else {
                        Some(incumbent)
                    }
                }
            };
        }
        Ok(selected)
    }

    fn remove_mutex_waiter(&mut self, id: TaskId) -> Result<(), Error> {
        let index = self.mutex_waiters[..self.mutex_waiter_count]
            .iter()
            .position(|entry| *entry == Some(id))
            .ok_or(Error::QueueMissing)?;
        for cursor in index..self.mutex_waiter_count - 1 {
            self.mutex_waiters[cursor] = self.mutex_waiters[cursor + 1];
        }
        self.mutex_waiter_count -= 1;
        self.mutex_waiters[self.mutex_waiter_count] = None;
        Ok(())
    }

    fn recompute_effective_priorities(&mut self) -> Result<(), Error> {
        for task in &mut self.tasks {
            if task.generation != 0 {
                task.effective_priority = task.base_priority;
            }
        }
        if let Some(owner) = self.mutex_owner {
            let owner_index = self.task_index(owner)?;
            let mut required = self.tasks[owner_index].base_priority;
            for cursor in 0..self.mutex_waiter_count {
                let waiter = self.mutex_waiters[cursor].ok_or(Error::Invariant)?;
                required = required.max(self.tasks[waiter.index()].base_priority);
            }
            self.tasks[owner_index].effective_priority = required;
        }
        Ok(())
    }

    fn select_allowed_cpu(&self, affinity_mask: u8) -> Result<CpuId, Error> {
        for cpu in 0..MAX_CPUS as u8 {
            let candidate = CpuId(cpu);
            if self.cpu_online_mask & candidate.mask() != 0 && affinity_mask & candidate.mask() != 0
            {
                return Ok(candidate);
            }
        }
        Err(Error::Affinity)
    }

    fn bump_sequence(&mut self) {
        self.sequence = self.sequence.wrapping_add(1);
    }
}

pub struct RefCount {
    value: AtomicU32,
}

impl RefCount {
    pub const fn new(value: u32) -> Self {
        Self {
            value: AtomicU32::new(value),
        }
    }

    pub fn load(&self) -> u32 {
        self.value.load(Ordering::Acquire)
    }

    pub fn increment(&self) -> Result<u32, Error> {
        self.value
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |value| {
                value.checked_add(1)
            })
            .map(|previous| previous + 1)
            .map_err(|_| Error::RefcountOverflow)
    }

    pub fn decrement(&self) -> Result<u32, Error> {
        self.value
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |value| {
                value.checked_sub(1)
            })
            .map(|previous| previous - 1)
            .map_err(|_| Error::RefcountUnderflow)
    }
}

pub struct RawSpinLock {
    owner: AtomicU32,
    contention: AtomicU32,
}

impl RawSpinLock {
    pub const fn new() -> Self {
        Self {
            owner: AtomicU32::new(0),
            contention: AtomicU32::new(0),
        }
    }

    pub fn lock_bounded(&self, owner: u32, attempts: u32) -> Result<(), Error> {
        if owner == 0 {
            return Err(Error::OwnerToken);
        }
        if self.owner.load(Ordering::Relaxed) == owner {
            return Err(Error::LockRecursive);
        }
        for _ in 0..attempts {
            match self
                .owner
                .compare_exchange(0, owner, Ordering::Acquire, Ordering::Relaxed)
            {
                Ok(_) => return Ok(()),
                Err(value) if value == owner => return Err(Error::LockRecursive),
                Err(_) => {
                    self.contention.fetch_add(1, Ordering::Relaxed);
                    core::hint::spin_loop();
                }
            }
        }
        Err(Error::LockBusy)
    }

    pub fn unlock(&self, owner: u32) -> Result<(), Error> {
        if owner == 0 {
            return Err(Error::OwnerToken);
        }
        self.owner
            .compare_exchange(owner, 0, Ordering::Release, Ordering::Relaxed)
            .map(|_| ())
            .map_err(|_| Error::UnlockNotOwner)
    }

    pub fn owner(&self) -> u32 {
        self.owner.load(Ordering::Acquire)
    }

    pub fn contention(&self) -> u32 {
        self.contention.load(Ordering::Relaxed)
    }
}

impl Default for RawSpinLock {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ContextSwitchContract {
    pub outgoing: TaskId,
    pub incoming: TaskId,
    pub cpu: CpuId,
    pub scheduler_lock_held: bool,
    pub interrupts_disabled: bool,
    pub same_address_space: bool,
    pub fs_gs_unchanged: bool,
    pub xstate_unused: bool,
    pub debug_state_unused: bool,
    pub pmu_state_unused: bool,
    pub kernel_stacks_distinct: bool,
    pub stack_alignment: u8,
}

pub fn validate_context_switch_contract(value: &ContextSwitchContract) -> Result<(), Error> {
    if value.outgoing == value.incoming
        || value.outgoing.index() >= MAX_TASKS
        || value.incoming.index() >= MAX_TASKS
        || value.outgoing.generation == 0
        || value.incoming.generation == 0
        || !value.scheduler_lock_held
        || !value.interrupts_disabled
        || !value.same_address_space
        || !value.fs_gs_unchanged
        || !value.xstate_unused
        || !value.debug_state_unused
        || !value.pmu_state_unused
        || !value.kernel_stacks_distinct
        || value.stack_alignment != 16
    {
        Err(Error::Invariant)
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cpu(value: u8) -> CpuId {
        CpuId::new(value).unwrap()
    }

    fn scheduler() -> Scheduler {
        Scheduler::new(COMPLETE_CPU_MASK).unwrap()
    }

    #[test]
    fn creates_activates_and_dispatches_generation_safe_tasks() {
        let mut scheduler = scheduler();
        let id = scheduler.create_task(0, 1, 10, 0x3).unwrap();
        scheduler.activate(id, cpu(1)).unwrap();
        assert_eq!(scheduler.dispatch(cpu(1)), Ok(id));
        assert_eq!(scheduler.current(cpu(1)), Ok(Some(id)));
        assert_eq!(scheduler.validate(), Ok(()));
    }

    #[test]
    fn rejects_stale_generation_and_duplicate_activation() {
        let mut scheduler = scheduler();
        let id = scheduler.create_task(0, 2, 10, 1).unwrap();
        scheduler.activate(id, cpu(0)).unwrap();
        assert_eq!(scheduler.activate(id, cpu(0)), Err(Error::State));
        assert_eq!(
            scheduler.task_snapshot(TaskId {
                slot: 0,
                generation: 1
            }),
            Err(Error::GenerationStale)
        );
    }

    #[test]
    fn priority_then_bypass_orders_equal_priority_tasks() {
        let mut scheduler = scheduler();
        let low = scheduler.create_task(0, 1, 2, 1).unwrap();
        let a = scheduler.create_task(1, 1, 20, 1).unwrap();
        let b = scheduler.create_task(2, 1, 20, 1).unwrap();
        for id in [low, a, b] {
            scheduler.activate(id, cpu(0)).unwrap();
        }
        assert_eq!(scheduler.dispatch(cpu(0)), Ok(a));
        scheduler.yield_current(cpu(0)).unwrap();
        assert_eq!(scheduler.dispatch(cpu(0)), Ok(b));
        scheduler.yield_current(cpu(0)).unwrap();
        assert_eq!(scheduler.dispatch(cpu(0)), Ok(a));
        assert!(scheduler.task_snapshot(low).unwrap().bypass_count <= MAX_BYPASS);
    }

    #[test]
    fn full_equal_priority_cohort_remains_round_robin_bounded() {
        let mut scheduler = scheduler();
        let mut ids = [TaskId {
            slot: 0,
            generation: 1,
        }; MAX_TASKS];
        let mut dispatches = [0u8; MAX_TASKS];
        for (slot, id) in ids.iter_mut().enumerate() {
            *id = scheduler
                .create_task(slot as u8, 1, 16, COMPLETE_CPU_MASK)
                .unwrap();
            scheduler.activate(*id, cpu(0)).unwrap();
        }
        for _ in 0..MAX_TASKS * 8 {
            let selected = scheduler.dispatch(cpu(0)).unwrap();
            dispatches[selected.index()] += 1;
            scheduler.yield_current(cpu(0)).unwrap();
            for id in ids {
                assert!(scheduler.task_snapshot(id).unwrap().bypass_count <= MAX_BYPASS);
            }
        }
        assert_eq!(dispatches, [8; MAX_TASKS]);
    }

    #[test]
    fn cancel_and_timeout_deliver_exactly_once() {
        let mut scheduler = scheduler();
        let cancel = scheduler.create_task(0, 1, 10, 1).unwrap();
        let timeout = scheduler.create_task(1, 1, 10, 2).unwrap();
        scheduler.activate(cancel, cpu(0)).unwrap();
        scheduler.activate(timeout, cpu(1)).unwrap();
        scheduler.dispatch(cpu(0)).unwrap();
        scheduler.dispatch(cpu(1)).unwrap();
        scheduler.block_current(cpu(0)).unwrap();
        scheduler.block_current(cpu(1)).unwrap();
        scheduler.cancel_wait(cancel, cpu(0)).unwrap();
        scheduler.timeout_wait(timeout, cpu(1)).unwrap();
        assert_eq!(scheduler.cancel_wait(cancel, cpu(0)), Err(Error::WaitKind));
        scheduler.dispatch(cpu(0)).unwrap();
        scheduler.dispatch(cpu(1)).unwrap();
        assert_eq!(scheduler.consume_wake(cpu(0)), Ok(WakeReason::Cancelled));
        assert_eq!(scheduler.consume_wake(cpu(1)), Ok(WakeReason::TimedOut));
    }

    #[test]
    fn migration_respects_hard_affinity_and_queue_ownership() {
        let mut scheduler = scheduler();
        let id = scheduler.create_task(0, 1, 10, 0x3).unwrap();
        scheduler.activate(id, cpu(0)).unwrap();
        scheduler.migrate(id, cpu(1)).unwrap();
        assert_eq!(scheduler.queue_len(cpu(0)), Ok(0));
        assert_eq!(scheduler.queue_len(cpu(1)), Ok(1));
        assert_eq!(scheduler.migrate(id, cpu(2)), Err(Error::Affinity));
    }

    #[test]
    fn mutex_inherits_priority_and_hands_to_highest_waiter() {
        let mut scheduler = scheduler();
        let low = scheduler.create_task(0, 1, 2, 1).unwrap();
        scheduler.activate(low, cpu(0)).unwrap();
        scheduler.dispatch(cpu(0)).unwrap();
        scheduler.lock_mutex(cpu(0)).unwrap();
        scheduler.yield_current(cpu(0)).unwrap();

        let high = scheduler.create_task(1, 1, 30, 2).unwrap();
        scheduler.activate(high, cpu(1)).unwrap();
        scheduler.dispatch(cpu(1)).unwrap();
        scheduler.lock_mutex(cpu(1)).unwrap();
        assert_eq!(scheduler.task_snapshot(low).unwrap().effective_priority, 30);

        assert_eq!(scheduler.dispatch(cpu(0)), Ok(low));
        assert_eq!(scheduler.unlock_mutex(cpu(0)), Ok(Some(high)));
        assert_eq!(scheduler.mutex_owner(), Some(high));
        assert_eq!(scheduler.task_snapshot(low).unwrap().effective_priority, 2);
    }

    #[test]
    fn mutex_rejects_recursion_and_non_owner_unlock() {
        let mut scheduler = scheduler();
        let a = scheduler.create_task(0, 1, 10, 1).unwrap();
        scheduler.activate(a, cpu(0)).unwrap();
        scheduler.dispatch(cpu(0)).unwrap();
        scheduler.lock_mutex(cpu(0)).unwrap();
        assert_eq!(scheduler.lock_mutex(cpu(0)), Err(Error::MutexRecursive));
        let b = scheduler.create_task(1, 1, 20, 2).unwrap();
        scheduler.activate(b, cpu(1)).unwrap();
        scheduler.dispatch(cpu(1)).unwrap();
        assert_eq!(scheduler.unlock_mutex(cpu(1)), Err(Error::MutexNotOwner));
    }

    #[test]
    fn owner_teardown_wakes_waiters_without_leaks() {
        let mut scheduler = scheduler();
        let owner = scheduler.create_task(0, 1, 2, 1).unwrap();
        scheduler.activate(owner, cpu(0)).unwrap();
        scheduler.dispatch(cpu(0)).unwrap();
        scheduler.lock_mutex(cpu(0)).unwrap();
        scheduler.yield_current(cpu(0)).unwrap();
        let waiter = scheduler.create_task(1, 1, 20, 2).unwrap();
        scheduler.activate(waiter, cpu(1)).unwrap();
        scheduler.dispatch(cpu(1)).unwrap();
        scheduler.lock_mutex(cpu(1)).unwrap();
        scheduler.teardown(owner).unwrap();
        assert_eq!(scheduler.mutex_owner(), None);
        assert_eq!(
            scheduler.task_snapshot(waiter).unwrap().wake_reason,
            WakeReason::OwnerGone
        );
        assert_eq!(scheduler.validate(), Ok(()));
    }

    #[test]
    fn teardown_releases_running_runnable_and_blocked_tasks() {
        let mut scheduler = scheduler();
        let running = scheduler.create_task(0, 1, 10, 1).unwrap();
        let runnable = scheduler.create_task(1, 1, 10, 2).unwrap();
        let blocked = scheduler.create_task(2, 1, 10, 4).unwrap();
        scheduler.activate(running, cpu(0)).unwrap();
        scheduler.activate(runnable, cpu(1)).unwrap();
        scheduler.activate(blocked, cpu(2)).unwrap();
        scheduler.dispatch(cpu(0)).unwrap();
        scheduler.dispatch(cpu(2)).unwrap();
        scheduler.block_current(cpu(2)).unwrap();
        for id in [running, runnable, blocked] {
            scheduler.teardown(id).unwrap();
            assert_eq!(scheduler.task_snapshot(id).unwrap().state, TaskState::Dead);
        }
        assert_eq!(scheduler.validate(), Ok(()));
    }

    #[test]
    fn refcount_fails_closed_at_both_bounds() {
        let zero = RefCount::new(0);
        assert_eq!(zero.decrement(), Err(Error::RefcountUnderflow));
        let maximum = RefCount::new(u32::MAX);
        assert_eq!(maximum.increment(), Err(Error::RefcountOverflow));
        let count = RefCount::new(1);
        assert_eq!(count.increment(), Ok(2));
        assert_eq!(count.decrement(), Ok(1));
    }

    #[test]
    fn raw_spinlock_tracks_owner_recursion_and_contention() {
        let lock = RawSpinLock::new();
        assert_eq!(lock.lock_bounded(0, 1), Err(Error::OwnerToken));
        assert_eq!(lock.lock_bounded(7, 1), Ok(()));
        assert_eq!(lock.lock_bounded(7, 1), Err(Error::LockRecursive));
        assert_eq!(lock.lock_bounded(8, 2), Err(Error::LockBusy));
        assert_eq!(lock.unlock(8), Err(Error::UnlockNotOwner));
        assert_eq!(lock.unlock(7), Ok(()));
        assert_eq!(lock.owner(), 0);
        assert_eq!(lock.contention(), 2);
    }

    #[test]
    fn context_switch_contract_is_fail_closed() {
        let valid = ContextSwitchContract {
            outgoing: TaskId::new(0, 1).unwrap(),
            incoming: TaskId::new(1, 1).unwrap(),
            cpu: cpu(0),
            scheduler_lock_held: true,
            interrupts_disabled: true,
            same_address_space: true,
            fs_gs_unchanged: true,
            xstate_unused: true,
            debug_state_unused: true,
            pmu_state_unused: true,
            kernel_stacks_distinct: true,
            stack_alignment: 16,
        };
        assert_eq!(validate_context_switch_contract(&valid), Ok(()));
        let mut invalid = valid;
        invalid.interrupts_disabled = false;
        assert_eq!(
            validate_context_switch_contract(&invalid),
            Err(Error::Invariant)
        );
        invalid = valid;
        invalid.incoming = invalid.outgoing;
        assert_eq!(
            validate_context_switch_contract(&invalid),
            Err(Error::Invariant)
        );
    }

    #[test]
    fn deterministic_four_cpu_stress_preserves_invariants() {
        let mut scheduler = scheduler();
        let mut ids = [TaskId {
            slot: 0,
            generation: 1,
        }; MAX_TASKS];
        for (slot, id) in ids.iter_mut().enumerate() {
            *id = scheduler
                .create_task(slot as u8, 1, (slot as u8 % 4) + 8, COMPLETE_CPU_MASK)
                .unwrap();
            scheduler
                .activate(*id, cpu((slot % MAX_CPUS) as u8))
                .unwrap();
        }
        let mut state = 0x5a17_91d3_6c8e_204fu64;
        for _ in 0..4096 {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let selected_cpu = cpu((state as usize % MAX_CPUS) as u8);
            if scheduler.current(selected_cpu).unwrap().is_none() {
                let _ = scheduler.dispatch(selected_cpu);
            } else if state & 3 == 0 {
                let _ = scheduler.account_tick(selected_cpu, 1);
                let _ = scheduler.yield_current(selected_cpu);
            } else if state & 7 == 1 {
                let _ = scheduler.account_tick(selected_cpu, 2);
            } else {
                let _ = scheduler.yield_current(selected_cpu);
            }
            let id = ids[(state.rotate_left(9) as usize) % MAX_TASKS];
            let target = cpu((state.rotate_right(11) as usize % MAX_CPUS) as u8);
            let _ = scheduler.migrate(id, target);
            assert_eq!(scheduler.validate(), Ok(()));
        }
        assert!(scheduler.summary().dispatch_count > 1000);
    }
}
