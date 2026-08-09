//! Allocation-free PKSCHED4 scheduler ownership for one exact four-CPU topology.

pub const CONTRACT_ID: &str = "PKSCHED4";
pub const SELECTED_MOVE_ID: &str = "N12-SCHED-SMP-001";
pub const CPU_COUNT: usize = 4;
pub const TASK_CAPACITY: usize = 8;
pub const ONLINE_MASK: u8 = 0x0f;
pub const AP_MASK: u8 = 0x0e;
pub const OFFLINE_PROBE_CPU: u8 = 4;
pub const CALL_FUNCTION_OPERATION: u32 = 3;
pub const ACK_ACCEPTED: u32 = 1;
pub const ERROR_NONE: u32 = 0;
pub const CALL_FUNCTION_RESULT: u64 = 0x4341_4c4c_4e4f_4f50;
pub const MAX_EQUAL_PRIORITY_BYPASS: u8 = (TASK_CAPACITY - 1) as u8;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuId(u8);

impl CpuId {
    pub const fn new(value: u8) -> Result<Self, Error> {
        if value < CPU_COUNT as u8 {
            Ok(Self(value))
        } else {
            Err(Error::CpuRange)
        }
    }

    pub const fn value(self) -> u8 {
        self.0
    }

    pub const fn index(self) -> usize {
        self.0 as usize
    }

    pub const fn mask(self) -> u8 {
        1 << self.0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TaskId {
    pub slot: u8,
    pub generation: u32,
}

impl TaskId {
    pub const fn new(slot: u8, generation: u32) -> Result<Self, Error> {
        if slot as usize >= TASK_CAPACITY {
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
    Blocked = 2,
    Transfer = 3,
    Running = 4,
    Dead = 5,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum TransferKind {
    Wake = 1,
    Migration = 2,
    Dispatch = 3,
    OfflineProbe = 4,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    CpuRange,
    CpuOffline,
    CpuBusy,
    CpuNotIdle,
    TaskRange,
    TaskMissing,
    Generation,
    GenerationStale,
    Priority,
    Affinity,
    State,
    QueueFull,
    QueueMissing,
    DuplicateRunnable,
    PendingBusy,
    PendingMissing,
    TicketMismatch,
    Acknowledgement,
    TimeoutTarget,
    Counter,
    Invariant,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::CpuRange => "cpu_range",
            Self::CpuOffline => "cpu_offline",
            Self::CpuBusy => "cpu_busy",
            Self::CpuNotIdle => "cpu_not_idle",
            Self::TaskRange => "task_range",
            Self::TaskMissing => "task_missing",
            Self::Generation => "generation",
            Self::GenerationStale => "generation_stale",
            Self::Priority => "priority",
            Self::Affinity => "affinity",
            Self::State => "state",
            Self::QueueFull => "queue_full",
            Self::QueueMissing => "queue_missing",
            Self::DuplicateRunnable => "duplicate_runnable",
            Self::PendingBusy => "pending_busy",
            Self::PendingMissing => "pending_missing",
            Self::TicketMismatch => "ticket_mismatch",
            Self::Acknowledgement => "acknowledgement",
            Self::TimeoutTarget => "timeout_target",
            Self::Counter => "counter",
            Self::Invariant => "invariant",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TransferTicket {
    pub transaction: u64,
    pub kind: TransferKind,
    pub task: TaskId,
    pub source_cpu: u8,
    pub target_cpu: u8,
    pub owner_epoch: u32,
    pub request_attempt: u64,
    pub request_sequence: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RemoteAck {
    pub target_cpu: u8,
    pub attempt: u64,
    pub sequence: u64,
    pub operation: u32,
    pub status: u32,
    pub error: u32,
    pub result: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TaskSnapshot {
    pub id: TaskId,
    pub state: TaskState,
    pub owner_cpu: Option<CpuId>,
    pub owner_epoch: u32,
    pub priority: u8,
    pub affinity_mask: u8,
    pub dispatch_count: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub sequence: u64,
    pub online_mask: u8,
    pub idle_cpu_count: u8,
    pub runnable_count: u8,
    pub blocked_count: u8,
    pub transfer_count: u8,
    pub running_count: u8,
    pub dead_count: u8,
    pub remote_wake_count: u32,
    pub migration_count: u32,
    pub dispatch_count: u32,
    pub bsp_dispatch_count: u32,
    pub ap_dispatch_count: u32,
    pub remote_ack_count: u32,
    pub timeout_count: u32,
    pub rollback_count: u32,
    pub stale_rejection_count: u32,
    pub teardown_count: u32,
    pub maximum_bypass: u8,
}

#[derive(Clone, Copy)]
struct Task {
    generation: u32,
    state: TaskState,
    priority: u8,
    affinity_mask: u8,
    owner_cpu: Option<CpuId>,
    owner_epoch: u32,
    queued_cpu: Option<CpuId>,
    bypass_count: u8,
    dispatch_count: u32,
}

impl Task {
    const fn empty() -> Self {
        Self {
            generation: 0,
            state: TaskState::Dormant,
            priority: 1,
            affinity_mask: 0,
            owner_cpu: None,
            owner_epoch: 0,
            queued_cpu: None,
            bypass_count: 0,
            dispatch_count: 0,
        }
    }

    const fn id(self, index: usize) -> TaskId {
        TaskId {
            slot: index as u8,
            generation: self.generation,
        }
    }
}

#[derive(Clone, Copy)]
struct Queue {
    entries: [Option<TaskId>; TASK_CAPACITY],
    len: usize,
}

impl Queue {
    const fn empty() -> Self {
        Self {
            entries: [None; TASK_CAPACITY],
            len: 0,
        }
    }

    fn push(&mut self, id: TaskId) -> Result<(), Error> {
        self.insert(self.len, id)
    }

    fn insert(&mut self, index: usize, id: TaskId) -> Result<(), Error> {
        if index > self.len {
            return Err(Error::QueueMissing);
        }
        if self.entries[..self.len].contains(&Some(id)) {
            return Err(Error::DuplicateRunnable);
        }
        if self.len == TASK_CAPACITY {
            return Err(Error::QueueFull);
        }
        for cursor in (index..self.len).rev() {
            self.entries[cursor + 1] = self.entries[cursor];
        }
        self.entries[index] = Some(id);
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

    fn remove(&mut self, id: TaskId) -> Result<usize, Error> {
        let index = self.entries[..self.len]
            .iter()
            .position(|entry| *entry == Some(id))
            .ok_or(Error::QueueMissing)?;
        self.remove_at(index)?;
        Ok(index)
    }
}

#[derive(Clone, Copy)]
struct Pending {
    ticket: TransferTicket,
}

pub struct SmpScheduler {
    tasks: [Task; TASK_CAPACITY],
    queues: [Queue; CPU_COUNT],
    current: [Option<TaskId>; CPU_COUNT],
    online_mask: u8,
    pending: Option<Pending>,
    sequence: u64,
    transaction: u64,
    remote_wake_count: u32,
    migration_count: u32,
    dispatch_count: u32,
    bsp_dispatch_count: u32,
    ap_dispatch_count: u32,
    remote_ack_count: u32,
    timeout_count: u32,
    rollback_count: u32,
    stale_rejection_count: u32,
    teardown_count: u32,
    maximum_bypass: u8,
}

impl SmpScheduler {
    pub const fn new() -> Self {
        Self {
            tasks: [Task::empty(); TASK_CAPACITY],
            queues: [Queue::empty(); CPU_COUNT],
            current: [None; CPU_COUNT],
            online_mask: ONLINE_MASK,
            pending: None,
            sequence: 0,
            transaction: 0,
            remote_wake_count: 0,
            migration_count: 0,
            dispatch_count: 0,
            bsp_dispatch_count: 0,
            ap_dispatch_count: 0,
            remote_ack_count: 0,
            timeout_count: 0,
            rollback_count: 0,
            stale_rejection_count: 0,
            teardown_count: 0,
            maximum_bypass: 0,
        }
    }

    pub fn create_task(
        &mut self,
        slot: u8,
        generation: u32,
        priority: u8,
        affinity_mask: u8,
    ) -> Result<TaskId, Error> {
        let id = TaskId::new(slot, generation)?;
        if priority == 0 || priority > 31 {
            return Err(Error::Priority);
        }
        if affinity_mask == 0 || affinity_mask & !ONLINE_MASK != 0 {
            return Err(Error::Affinity);
        }
        let task = self.tasks[id.index()];
        if task.generation != 0 && task.state != TaskState::Dead {
            return Err(Error::State);
        }
        if task.generation != 0 && generation <= task.generation {
            return Err(Error::GenerationStale);
        }
        self.tasks[id.index()] = Task {
            generation,
            state: TaskState::Dormant,
            priority,
            affinity_mask,
            owner_cpu: None,
            owner_epoch: 0,
            queued_cpu: None,
            bypass_count: 0,
            dispatch_count: 0,
        };
        self.bump();
        Ok(id)
    }

    pub fn activate(&mut self, id: TaskId, cpu: CpuId) -> Result<(), Error> {
        self.require_online(cpu)?;
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.state != TaskState::Dormant || task.affinity_mask & cpu.mask() == 0 {
            return Err(Error::State);
        }
        self.tasks[index].state = TaskState::Runnable;
        self.tasks[index].owner_cpu = Some(cpu);
        self.tasks[index].owner_epoch = 1;
        self.enqueue(index, cpu)?;
        self.bump();
        self.validate()
    }

    pub fn block_runnable(&mut self, id: TaskId) -> Result<(), Error> {
        self.require_no_pending()?;
        let index = self.task_index(id)?;
        if self.tasks[index].state != TaskState::Runnable {
            return Err(Error::State);
        }
        let cpu = self.tasks[index].queued_cpu.ok_or(Error::QueueMissing)?;
        self.queues[cpu.index()].remove(id)?;
        self.tasks[index].state = TaskState::Blocked;
        self.tasks[index].queued_cpu = None;
        self.tasks[index].bypass_count = 0;
        self.bump();
        self.validate()
    }

    pub fn stage_wake(
        &mut self,
        id: TaskId,
        target: CpuId,
        attempt: u64,
        sequence: u64,
    ) -> Result<TransferTicket, Error> {
        self.require_no_pending()?;
        self.require_online(target)?;
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.state != TaskState::Blocked || task.affinity_mask & target.mask() == 0 {
            return Err(Error::State);
        }
        let source = task.owner_cpu.ok_or(Error::Invariant)?;
        self.install_pending(
            TransferKind::Wake,
            id,
            source.value(),
            target.value(),
            attempt,
            sequence,
        )
    }

    pub fn stage_migration(
        &mut self,
        id: TaskId,
        target: CpuId,
        attempt: u64,
        sequence: u64,
    ) -> Result<TransferTicket, Error> {
        self.require_no_pending()?;
        self.require_online(target)?;
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.state != TaskState::Runnable || task.affinity_mask & target.mask() == 0 {
            return Err(Error::State);
        }
        let source = task.queued_cpu.ok_or(Error::QueueMissing)?;
        if source == target {
            return Err(Error::State);
        }
        if !self.queues[source.index()].entries[..self.queues[source.index()].len]
            .contains(&Some(id))
        {
            return Err(Error::QueueMissing);
        }
        self.install_pending(
            TransferKind::Migration,
            id,
            source.value(),
            target.value(),
            attempt,
            sequence,
        )
    }

    pub fn stage_offline_probe(
        &mut self,
        id: TaskId,
        target_cpu: u8,
        attempt: u64,
        sequence: u64,
    ) -> Result<TransferTicket, Error> {
        self.require_no_pending()?;
        if target_cpu != OFFLINE_PROBE_CPU {
            return Err(Error::TimeoutTarget);
        }
        let index = self.task_index(id)?;
        let task = self.tasks[index];
        if task.state != TaskState::Runnable {
            return Err(Error::State);
        }
        let source = task.queued_cpu.ok_or(Error::QueueMissing)?;
        self.install_pending(
            TransferKind::OfflineProbe,
            id,
            source.value(),
            target_cpu,
            attempt,
            sequence,
        )
    }

    pub fn stage_dispatch(
        &mut self,
        cpu: CpuId,
        attempt: u64,
        sequence: u64,
    ) -> Result<TransferTicket, Error> {
        self.require_no_pending()?;
        self.require_online(cpu)?;
        if self.current[cpu.index()].is_some() {
            return Err(Error::CpuBusy);
        }
        if attempt == 0 || sequence == 0 {
            return Err(Error::Acknowledgement);
        }
        let queue_index = self.pick(cpu)?;
        let id = self.queues[cpu.index()].remove_at(queue_index)?;
        let index = self.task_index(id)?;
        let selected_priority = self.tasks[index].priority;
        for cursor in 0..self.queues[cpu.index()].len {
            let other = self.queues[cpu.index()].entries[cursor].ok_or(Error::Invariant)?;
            let other_index = self.task_index(other)?;
            if self.tasks[other_index].priority == selected_priority {
                self.tasks[other_index].bypass_count = self.tasks[other_index]
                    .bypass_count
                    .checked_add(1)
                    .ok_or(Error::Counter)?;
                if self.tasks[other_index].bypass_count > MAX_EQUAL_PRIORITY_BYPASS {
                    return Err(Error::Counter);
                }
                self.maximum_bypass = self
                    .maximum_bypass
                    .max(self.tasks[other_index].bypass_count);
            }
        }
        self.tasks[index].state = TaskState::Transfer;
        self.tasks[index].queued_cpu = None;
        self.install_pending(
            TransferKind::Dispatch,
            id,
            cpu.value(),
            cpu.value(),
            attempt,
            sequence,
        )
    }

    pub fn acknowledge(&mut self, ticket: TransferTicket, ack: RemoteAck) -> Result<(), Error> {
        let pending = self.pending.ok_or(Error::PendingMissing)?;
        if pending.ticket != ticket {
            return Err(Error::TicketMismatch);
        }
        if ack.target_cpu != ticket.target_cpu
            || ack.attempt != ticket.request_attempt
            || ack.sequence != ticket.request_sequence
            || ack.operation != CALL_FUNCTION_OPERATION
            || ack.status != ACK_ACCEPTED
            || ack.error != ERROR_NONE
            || ack.result != CALL_FUNCTION_RESULT
        {
            return Err(Error::Acknowledgement);
        }
        let index = self.task_index(ticket.task)?;
        if self.tasks[index].owner_epoch != ticket.owner_epoch {
            return Err(Error::GenerationStale);
        }
        let target = CpuId::new(ticket.target_cpu)?;
        match ticket.kind {
            TransferKind::Wake => {
                if self.tasks[index].state != TaskState::Blocked {
                    return Err(Error::State);
                }
                self.tasks[index].state = TaskState::Runnable;
                self.tasks[index].owner_cpu = Some(target);
                self.tasks[index].owner_epoch = increment(self.tasks[index].owner_epoch)?;
                self.enqueue(index, target)?;
                self.remote_wake_count = increment(self.remote_wake_count)?;
            }
            TransferKind::Migration => {
                if self.tasks[index].state != TaskState::Runnable {
                    return Err(Error::State);
                }
                let source = CpuId::new(ticket.source_cpu)?;
                self.queues[source.index()].remove(ticket.task)?;
                self.tasks[index].queued_cpu = None;
                self.tasks[index].owner_cpu = Some(target);
                self.tasks[index].owner_epoch = increment(self.tasks[index].owner_epoch)?;
                self.enqueue(index, target)?;
                self.migration_count = increment(self.migration_count)?;
            }
            TransferKind::Dispatch => {
                if self.tasks[index].state != TaskState::Transfer
                    || self.current[target.index()].is_some()
                {
                    return Err(Error::State);
                }
                self.tasks[index].state = TaskState::Running;
                self.tasks[index].owner_cpu = Some(target);
                self.tasks[index].owner_epoch = increment(self.tasks[index].owner_epoch)?;
                self.tasks[index].bypass_count = 0;
                self.tasks[index].dispatch_count = increment(self.tasks[index].dispatch_count)?;
                self.current[target.index()] = Some(ticket.task);
                self.dispatch_count = increment(self.dispatch_count)?;
                if target.value() == 0 {
                    self.bsp_dispatch_count = increment(self.bsp_dispatch_count)?;
                } else {
                    self.ap_dispatch_count = increment(self.ap_dispatch_count)?;
                }
            }
            TransferKind::OfflineProbe => return Err(Error::Acknowledgement),
        }
        self.pending = None;
        self.remote_ack_count = increment(self.remote_ack_count)?;
        self.bump();
        self.validate()
    }

    pub fn timeout(&mut self, ticket: TransferTicket) -> Result<(), Error> {
        let pending = self.pending.ok_or(Error::PendingMissing)?;
        if pending.ticket != ticket || ticket.kind != TransferKind::OfflineProbe {
            return Err(Error::TicketMismatch);
        }
        let index = self.task_index(ticket.task)?;
        if self.tasks[index].state != TaskState::Runnable
            || self.tasks[index].queued_cpu.map(CpuId::value) != Some(ticket.source_cpu)
        {
            return Err(Error::Invariant);
        }
        self.pending = None;
        self.timeout_count = increment(self.timeout_count)?;
        self.rollback_count = increment(self.rollback_count)?;
        self.bump();
        self.validate()
    }

    pub fn reject_stale_ack(
        &mut self,
        ticket: TransferTicket,
        ack: RemoteAck,
    ) -> Result<(), Error> {
        if self.pending.is_some() || self.acknowledge(ticket, ack) != Err(Error::PendingMissing) {
            return Err(Error::Invariant);
        }
        self.stale_rejection_count = increment(self.stale_rejection_count)?;
        self.bump();
        Ok(())
    }

    pub fn complete_current(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        self.require_no_pending()?;
        self.require_online(cpu)?;
        let id = self.current[cpu.index()].take().ok_or(Error::CpuNotIdle)?;
        let index = self.task_index(id)?;
        if self.tasks[index].state != TaskState::Running {
            return Err(Error::Invariant);
        }
        self.tasks[index].state = TaskState::Dead;
        self.tasks[index].owner_cpu = None;
        self.tasks[index].queued_cpu = None;
        self.tasks[index].bypass_count = 0;
        self.teardown_count = increment(self.teardown_count)?;
        self.bump();
        self.validate()?;
        Ok(id)
    }

    pub fn dispatch_local(&mut self, cpu: CpuId) -> Result<TaskId, Error> {
        self.require_no_pending()?;
        self.require_online(cpu)?;
        if cpu.value() != 0 || self.current[cpu.index()].is_some() {
            return Err(Error::CpuBusy);
        }
        let queue_index = self.pick(cpu)?;
        let id = self.queues[cpu.index()].remove_at(queue_index)?;
        let index = self.task_index(id)?;
        self.tasks[index].state = TaskState::Running;
        self.tasks[index].queued_cpu = None;
        self.tasks[index].owner_epoch = increment(self.tasks[index].owner_epoch)?;
        self.tasks[index].dispatch_count = increment(self.tasks[index].dispatch_count)?;
        self.tasks[index].bypass_count = 0;
        self.current[cpu.index()] = Some(id);
        self.dispatch_count = increment(self.dispatch_count)?;
        self.bsp_dispatch_count = increment(self.bsp_dispatch_count)?;
        self.bump();
        self.validate()?;
        self.complete_current(cpu)
    }

    pub fn select_least_loaded(&self, affinity_mask: u8) -> Result<CpuId, Error> {
        if affinity_mask == 0 || affinity_mask & !ONLINE_MASK != 0 {
            return Err(Error::Affinity);
        }
        let mut selected = None;
        let mut selected_load = usize::MAX;
        for value in 0..CPU_COUNT as u8 {
            let cpu = CpuId(value);
            if self.online_mask & cpu.mask() == 0 || affinity_mask & cpu.mask() == 0 {
                continue;
            }
            let load =
                self.queues[cpu.index()].len + usize::from(self.current[cpu.index()].is_some());
            if load < selected_load {
                selected = Some(cpu);
                selected_load = load;
            }
        }
        selected.ok_or(Error::CpuOffline)
    }

    pub fn offline_idle_cpu(&mut self, cpu: CpuId) -> Result<(), Error> {
        self.require_no_pending()?;
        self.require_online(cpu)?;
        if cpu.value() == 0
            || self.current[cpu.index()].is_some()
            || self.queues[cpu.index()].len != 0
        {
            return Err(Error::CpuNotIdle);
        }
        self.online_mask &= !cpu.mask();
        self.bump();
        self.validate()
    }

    pub fn task_snapshot(&mut self, id: TaskId) -> Result<TaskSnapshot, Error> {
        let index = match self.task_index(id) {
            Ok(value) => value,
            Err(error @ Error::GenerationStale) => {
                self.stale_rejection_count = increment(self.stale_rejection_count)?;
                return Err(error);
            }
            Err(error) => return Err(error),
        };
        let task = self.tasks[index];
        Ok(TaskSnapshot {
            id,
            state: task.state,
            owner_cpu: task.owner_cpu,
            owner_epoch: task.owner_epoch,
            priority: task.priority,
            affinity_mask: task.affinity_mask,
            dispatch_count: task.dispatch_count,
        })
    }

    pub fn queue_len(&self, cpu: CpuId) -> Result<usize, Error> {
        self.require_online(cpu)?;
        Ok(self.queues[cpu.index()].len)
    }

    pub fn summary(&self) -> Summary {
        let mut value = Summary {
            sequence: self.sequence,
            online_mask: self.online_mask,
            idle_cpu_count: 0,
            runnable_count: 0,
            blocked_count: 0,
            transfer_count: 0,
            running_count: 0,
            dead_count: 0,
            remote_wake_count: self.remote_wake_count,
            migration_count: self.migration_count,
            dispatch_count: self.dispatch_count,
            bsp_dispatch_count: self.bsp_dispatch_count,
            ap_dispatch_count: self.ap_dispatch_count,
            remote_ack_count: self.remote_ack_count,
            timeout_count: self.timeout_count,
            rollback_count: self.rollback_count,
            stale_rejection_count: self.stale_rejection_count,
            teardown_count: self.teardown_count,
            maximum_bypass: self.maximum_bypass,
        };
        for cpu in 0..CPU_COUNT {
            if self.online_mask & (1 << cpu) != 0 && self.current[cpu].is_none() {
                value.idle_cpu_count += 1;
            }
        }
        for task in self.tasks {
            match task.state {
                TaskState::Runnable => value.runnable_count += 1,
                TaskState::Blocked => value.blocked_count += 1,
                TaskState::Transfer => value.transfer_count += 1,
                TaskState::Running => value.running_count += 1,
                TaskState::Dead => value.dead_count += 1,
                TaskState::Dormant => {}
            }
        }
        value
    }

    pub fn validate(&self) -> Result<(), Error> {
        if self.online_mask == 0 || self.online_mask & !ONLINE_MASK != 0 {
            return Err(Error::Invariant);
        }
        let mut queued = [0u8; TASK_CAPACITY];
        let mut running = [0u8; TASK_CAPACITY];
        for cpu_index in 0..CPU_COUNT {
            let cpu = CpuId(cpu_index as u8);
            let queue = &self.queues[cpu_index];
            if self.online_mask & cpu.mask() == 0
                && (queue.len != 0 || self.current[cpu_index].is_some())
            {
                return Err(Error::Invariant);
            }
            if queue.len > TASK_CAPACITY || queue.entries[queue.len..].iter().any(Option::is_some) {
                return Err(Error::Invariant);
            }
            for entry in &queue.entries[..queue.len] {
                let id = entry.ok_or(Error::Invariant)?;
                let index = self.task_index(id)?;
                let task = self.tasks[index];
                if task.state != TaskState::Runnable
                    || task.queued_cpu != Some(cpu)
                    || task.owner_cpu != Some(cpu)
                    || task.affinity_mask & cpu.mask() == 0
                    || task.bypass_count > MAX_EQUAL_PRIORITY_BYPASS
                {
                    return Err(Error::Invariant);
                }
                queued[index] = queued[index].checked_add(1).ok_or(Error::Invariant)?;
            }
            if let Some(id) = self.current[cpu_index] {
                let index = self.task_index(id)?;
                let task = self.tasks[index];
                if task.state != TaskState::Running
                    || task.owner_cpu != Some(cpu)
                    || task.queued_cpu.is_some()
                {
                    return Err(Error::Invariant);
                }
                running[index] = running[index].checked_add(1).ok_or(Error::Invariant)?;
            }
        }
        for (index, task) in self.tasks.iter().copied().enumerate() {
            if task.generation == 0 {
                if task.state != TaskState::Dormant || queued[index] != 0 || running[index] != 0 {
                    return Err(Error::Invariant);
                }
                continue;
            }
            if task.affinity_mask == 0 || task.affinity_mask & !ONLINE_MASK != 0 {
                return Err(Error::Invariant);
            }
            match task.state {
                TaskState::Dormant => {
                    if task.owner_cpu.is_some() || task.queued_cpu.is_some() {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Runnable => {
                    if queued[index] != 1 || running[index] != 0 || task.queued_cpu.is_none() {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Blocked => {
                    if queued[index] != 0
                        || running[index] != 0
                        || task.owner_cpu.is_none()
                        || task.queued_cpu.is_some()
                    {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Transfer => {
                    if queued[index] != 0 || running[index] != 0 || task.queued_cpu.is_some() {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Running => {
                    if queued[index] != 0 || running[index] != 1 || task.queued_cpu.is_some() {
                        return Err(Error::Invariant);
                    }
                }
                TaskState::Dead => {
                    if queued[index] != 0
                        || running[index] != 0
                        || task.owner_cpu.is_some()
                        || task.queued_cpu.is_some()
                    {
                        return Err(Error::Invariant);
                    }
                }
            }
            if queued[index] > 1
                || running[index] > 1
                || task.owner_epoch == 0 && task.state != TaskState::Dormant
            {
                return Err(Error::DuplicateRunnable);
            }
        }
        if let Some(pending) = self.pending {
            let index = self.task_index(pending.ticket.task)?;
            let task = self.tasks[index];
            match pending.ticket.kind {
                TransferKind::Wake if task.state != TaskState::Blocked => {
                    return Err(Error::Invariant);
                }
                TransferKind::Migration | TransferKind::OfflineProbe
                    if task.state != TaskState::Runnable =>
                {
                    return Err(Error::Invariant);
                }
                TransferKind::Dispatch if task.state != TaskState::Transfer => {
                    return Err(Error::Invariant);
                }
                _ => {}
            }
        } else if self
            .tasks
            .iter()
            .any(|task| task.state == TaskState::Transfer)
        {
            return Err(Error::Invariant);
        }
        Ok(())
    }

    fn install_pending(
        &mut self,
        kind: TransferKind,
        task: TaskId,
        source_cpu: u8,
        target_cpu: u8,
        request_attempt: u64,
        request_sequence: u64,
    ) -> Result<TransferTicket, Error> {
        if request_attempt == 0 || request_sequence == 0 {
            return Err(Error::Acknowledgement);
        }
        self.transaction = self.transaction.checked_add(1).ok_or(Error::Counter)?;
        let owner_epoch = self.tasks[self.task_index(task)?].owner_epoch;
        let ticket = TransferTicket {
            transaction: self.transaction,
            kind,
            task,
            source_cpu,
            target_cpu,
            owner_epoch,
            request_attempt,
            request_sequence,
        };
        self.pending = Some(Pending { ticket });
        self.bump();
        self.validate()?;
        Ok(ticket)
    }

    fn task_index(&self, id: TaskId) -> Result<usize, Error> {
        if id.index() >= TASK_CAPACITY {
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
        if self.online_mask & cpu.mask() == 0 {
            Err(Error::CpuOffline)
        } else {
            Ok(())
        }
    }

    fn require_no_pending(&self) -> Result<(), Error> {
        if self.pending.is_some() {
            Err(Error::PendingBusy)
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
        self.queues[cpu.index()].push(task.id(index))?;
        self.tasks[index].queued_cpu = Some(cpu);
        Ok(())
    }

    fn pick(&self, cpu: CpuId) -> Result<usize, Error> {
        let queue = &self.queues[cpu.index()];
        if queue.len == 0 {
            return Err(Error::CpuNotIdle);
        }
        let mut selected = 0usize;
        for cursor in 1..queue.len {
            let candidate = queue.entries[cursor].ok_or(Error::Invariant)?;
            let incumbent = queue.entries[selected].ok_or(Error::Invariant)?;
            let candidate_task = self.tasks[self.task_index(candidate)?];
            let incumbent_task = self.tasks[self.task_index(incumbent)?];
            if candidate_task.priority > incumbent_task.priority
                || candidate_task.priority == incumbent_task.priority
                    && candidate_task.bypass_count > incumbent_task.bypass_count
            {
                selected = cursor;
            }
        }
        Ok(selected)
    }

    fn bump(&mut self) {
        self.sequence = self.sequence.wrapping_add(1);
    }
}

impl Default for SmpScheduler {
    fn default() -> Self {
        Self::new()
    }
}

fn increment(value: u32) -> Result<u32, Error> {
    value.checked_add(1).ok_or(Error::Counter)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cpu(value: u8) -> CpuId {
        CpuId::new(value).unwrap()
    }

    fn ack(ticket: TransferTicket) -> RemoteAck {
        RemoteAck {
            target_cpu: ticket.target_cpu,
            attempt: ticket.request_attempt,
            sequence: ticket.request_sequence,
            operation: CALL_FUNCTION_OPERATION,
            status: ACK_ACCEPTED,
            error: ERROR_NONE,
            result: CALL_FUNCTION_RESULT,
        }
    }

    fn task(scheduler: &mut SmpScheduler, slot: u8, affinity: u8, owner: u8) -> TaskId {
        let id = scheduler.create_task(slot, 1, 16, affinity).unwrap();
        scheduler.activate(id, cpu(owner)).unwrap();
        id
    }

    #[test]
    fn wake_migration_and_dispatch_commit_only_after_exact_ack() {
        let mut scheduler = SmpScheduler::new();
        let wake = task(&mut scheduler, 0, 0x03, 0);
        scheduler.block_runnable(wake).unwrap();
        let migrate = task(&mut scheduler, 1, 0x06, 1);
        let wake_ticket = scheduler.stage_wake(wake, cpu(1), 3, 2).unwrap();
        assert_eq!(
            scheduler.task_snapshot(wake).unwrap().state,
            TaskState::Blocked
        );
        scheduler
            .acknowledge(wake_ticket, ack(wake_ticket))
            .unwrap();
        let migration = scheduler.stage_migration(migrate, cpu(2), 3, 2).unwrap();
        assert_eq!(scheduler.queue_len(cpu(1)), Ok(2));
        scheduler.acknowledge(migration, ack(migration)).unwrap();
        assert_eq!(scheduler.queue_len(cpu(1)), Ok(1));
        assert_eq!(scheduler.queue_len(cpu(2)), Ok(1));
        let dispatch = scheduler.stage_dispatch(cpu(2), 4, 3).unwrap();
        scheduler.acknowledge(dispatch, ack(dispatch)).unwrap();
        assert_eq!(scheduler.complete_current(cpu(2)), Ok(migrate));
        assert_eq!(scheduler.summary().remote_ack_count, 3);
        assert_eq!(scheduler.validate(), Ok(()));
    }

    #[test]
    fn offline_timeout_preserves_source_queue_and_rejects_late_ack() {
        let mut scheduler = SmpScheduler::new();
        let id = task(&mut scheduler, 0, 0x06, 1);
        let ticket = scheduler
            .stage_offline_probe(id, OFFLINE_PROBE_CPU, 3, 2)
            .unwrap();
        scheduler.timeout(ticket).unwrap();
        assert_eq!(scheduler.queue_len(cpu(1)), Ok(1));
        assert_eq!(
            scheduler.acknowledge(ticket, ack(ticket)),
            Err(Error::PendingMissing)
        );
        scheduler.reject_stale_ack(ticket, ack(ticket)).unwrap();
        let summary = scheduler.summary();
        assert_eq!(
            (
                summary.timeout_count,
                summary.rollback_count,
                summary.stale_rejection_count
            ),
            (1, 1, 1)
        );
    }

    #[test]
    fn generation_and_ack_binding_fail_closed() {
        let mut scheduler = SmpScheduler::new();
        let id = task(&mut scheduler, 0, 0x02, 1);
        let stale = TaskId::new(id.slot, 2).unwrap();
        assert_eq!(scheduler.task_snapshot(stale), Err(Error::GenerationStale));
        let ticket = scheduler.stage_dispatch(cpu(1), 4, 3).unwrap();
        let mut hostile = ack(ticket);
        hostile.sequence += 1;
        assert_eq!(
            scheduler.acknowledge(ticket, hostile),
            Err(Error::Acknowledgement)
        );
        scheduler.acknowledge(ticket, ack(ticket)).unwrap();
    }

    #[test]
    fn equal_priority_round_robin_has_a_bounded_bypass() {
        let mut scheduler = SmpScheduler::new();
        let first = task(&mut scheduler, 0, 0x02, 1);
        let second = task(&mut scheduler, 1, 0x02, 1);
        let one = scheduler.stage_dispatch(cpu(1), 1, 1).unwrap();
        assert_eq!(one.task, first);
        scheduler.acknowledge(one, ack(one)).unwrap();
        scheduler.complete_current(cpu(1)).unwrap();
        let two = scheduler.stage_dispatch(cpu(1), 2, 2).unwrap();
        assert_eq!(two.task, second);
        scheduler.acknowledge(two, ack(two)).unwrap();
        scheduler.complete_current(cpu(1)).unwrap();
        assert_eq!(scheduler.summary().maximum_bypass, 1);
    }

    #[test]
    fn topology_balancer_uses_load_then_cpu_id() {
        let mut scheduler = SmpScheduler::new();
        assert_eq!(scheduler.select_least_loaded(ONLINE_MASK), Ok(cpu(0)));
        task(&mut scheduler, 0, 0x01, 0);
        assert_eq!(scheduler.select_least_loaded(ONLINE_MASK), Ok(cpu(1)));
        assert_eq!(scheduler.select_least_loaded(0x0c), Ok(cpu(2)));
    }

    #[test]
    fn cpu_offline_requires_exact_idle_ownership() {
        let mut scheduler = SmpScheduler::new();
        task(&mut scheduler, 0, 0x02, 1);
        assert_eq!(scheduler.offline_idle_cpu(cpu(1)), Err(Error::CpuNotIdle));
        let dispatch = scheduler.stage_dispatch(cpu(1), 1, 1).unwrap();
        scheduler.acknowledge(dispatch, ack(dispatch)).unwrap();
        scheduler.complete_current(cpu(1)).unwrap();
        scheduler.offline_idle_cpu(cpu(1)).unwrap();
        assert_eq!(scheduler.queue_len(cpu(1)), Err(Error::CpuOffline));
    }

    #[test]
    fn local_dispatch_uses_the_same_identity_and_teardown_rules() {
        let mut scheduler = SmpScheduler::new();
        let first = task(&mut scheduler, 0, 0x01, 0);
        let second = task(&mut scheduler, 1, 0x01, 0);
        assert_eq!(scheduler.dispatch_local(cpu(0)), Ok(first));
        assert_eq!(scheduler.dispatch_local(cpu(0)), Ok(second));
        let summary = scheduler.summary();
        assert_eq!(
            (
                summary.bsp_dispatch_count,
                summary.dead_count,
                summary.teardown_count
            ),
            (2, 2, 2)
        );
    }

    #[test]
    fn complete_teardown_leaves_four_idle_owners_and_no_duplicates() {
        let mut scheduler = SmpScheduler::new();
        for slot in 0..TASK_CAPACITY as u8 {
            task(&mut scheduler, slot, 1 << (slot % 4), slot % 4);
        }
        for cpu_value in 0..CPU_COUNT as u8 {
            for sequence in 1..=2 {
                if cpu_value == 0 {
                    scheduler.dispatch_local(cpu(cpu_value)).unwrap();
                } else {
                    let ticket = scheduler
                        .stage_dispatch(cpu(cpu_value), sequence, sequence)
                        .unwrap();
                    scheduler.acknowledge(ticket, ack(ticket)).unwrap();
                    scheduler.complete_current(cpu(cpu_value)).unwrap();
                }
            }
        }
        let summary = scheduler.summary();
        assert_eq!(
            (
                summary.dead_count,
                summary.idle_cpu_count,
                summary.runnable_count
            ),
            (8, 4, 0)
        );
        assert_eq!(scheduler.validate(), Ok(()));
    }
}
