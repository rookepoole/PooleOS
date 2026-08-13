//! Allocation-free PKSCHED6 timer/event preemption for one exact four-CPU topology.

use crate::scheduler_smp::{
    ACK_ACCEPTED, CPU_COUNT, CpuId, ERROR_NONE, Error as SchedulerError, OFFLINE_PROBE_CPU,
    ONLINE_MASK, RESCHEDULE_OPERATION, RESCHEDULE_RESULT, RemoteAck, SmpScheduler, TASK_CAPACITY,
    TaskId, TaskState, TransferKind, TransferTicket,
};

pub const CONTRACT_ID: &str = "PKSCHED6";
pub const SELECTED_MOVE_ID: &str = "N12-SCHED-SMP-PREEMPT-001";
pub const TIMER_VECTOR: u8 = 0x40;
pub const KERNEL_CODE_SELECTOR: u64 = 0x08;
pub const KERNEL_DATA_SELECTOR: u64 = 0x10;
pub const EVENT_CAPACITY_PER_CPU: usize = 4;
pub const QUANTUM_TICKS: u32 = 2;
pub const MAX_EVENT_LATENCY_TICKS: u64 = 1;
pub const MAX_WATCHDOG_TICKS: u32 = QUANTUM_TICKS;
pub const IST_BYTES_PER_CPU: u64 = 8192;
pub const IST_STRIDE: u64 = 16384;
pub const IST_BASE: u64 = 0xffff_ffff_8100_0000;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Scheduler,
    CpuRange,
    EventCapacity,
    EventDeadline,
    EventSequence,
    EventOwner,
    EventDuplicate,
    PendingRemote,
    FrameCpu,
    FrameApic,
    FrameEpoch,
    FrameVector,
    FrameErrorCode,
    FrameSelector,
    FrameFlags,
    FrameInterruptState,
    FrameLock,
    FrameStack,
    Watchdog,
    Counter,
    Shutdown,
    Invariant,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Scheduler => "scheduler",
            Self::CpuRange => "cpu_range",
            Self::EventCapacity => "event_capacity",
            Self::EventDeadline => "event_deadline",
            Self::EventSequence => "event_sequence",
            Self::EventOwner => "event_owner",
            Self::EventDuplicate => "event_duplicate",
            Self::PendingRemote => "pending_remote",
            Self::FrameCpu => "frame_cpu",
            Self::FrameApic => "frame_apic",
            Self::FrameEpoch => "frame_epoch",
            Self::FrameVector => "frame_vector",
            Self::FrameErrorCode => "frame_error_code",
            Self::FrameSelector => "frame_selector",
            Self::FrameFlags => "frame_flags",
            Self::FrameInterruptState => "frame_interrupt_state",
            Self::FrameLock => "frame_lock",
            Self::FrameStack => "frame_stack",
            Self::Watchdog => "watchdog",
            Self::Counter => "counter",
            Self::Shutdown => "shutdown",
            Self::Invariant => "invariant",
        }
    }
}

impl From<SchedulerError> for Error {
    fn from(_: SchedulerError) -> Self {
        Self::Scheduler
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EventKind {
    Cancel { task: TaskId },
    Wake { task: TaskId, target: CpuId },
    Migrate { task: TaskId, target: CpuId },
}

impl EventKind {
    const fn order(self) -> u8 {
        match self {
            Self::Cancel { .. } => 1,
            Self::Wake { .. } => 2,
            Self::Migrate { .. } => 3,
        }
    }

    const fn task(self) -> TaskId {
        match self {
            Self::Cancel { task } | Self::Wake { task, .. } | Self::Migrate { task, .. } => task,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Event {
    pub due_tick: u64,
    pub sequence: u64,
    pub kind: EventKind,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FrameContract {
    pub cpu: CpuId,
    pub apic_id: u32,
    pub frame_owner: TaskId,
    pub frame_epoch: u64,
    pub timer_epoch: u64,
    pub vector: u64,
    pub error_code: u64,
    pub code_selector: u64,
    pub data_selector: u64,
    pub interrupted_rflags: u64,
    pub handler_interrupts_disabled: bool,
    pub scheduler_lock_held: bool,
    pub handler_rsp: u64,
    pub frame_bytes: u64,
    pub ist_bottom: u64,
    pub ist_top: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Cause {
    None,
    Cancel,
    Wake,
    Migration,
    Quantum,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TickOutcome {
    pub cpu: CpuId,
    pub tick: u64,
    pub previous: TaskId,
    pub cause: Cause,
    pub events_processed: u8,
    pub event_order: [u8; EVENT_CAPACITY_PER_CPU],
    pub remote_ticket: Option<TransferTicket>,
    pub quantum_remaining: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub online_mask: u8,
    pub frame_epochs: [u64; CPU_COUNT],
    pub timer_ticks: [u64; CPU_COUNT],
    pub pending_events: u8,
    pub cancelled_events: u32,
    pub wake_events: u32,
    pub migration_events: u32,
    pub quantum_preemptions: u32,
    pub remote_reschedule_acks: u32,
    pub context_switches: u32,
    pub timeout_rollbacks: u32,
    pub stale_ack_rejections: u32,
    pub maximum_event_latency: u64,
    pub maximum_watchdog_age: u32,
    pub frame_owner_revocations: u32,
    pub timer_owner_revocations: u32,
    pub scheduler: crate::scheduler_smp::Summary,
}

#[derive(Clone, Copy)]
struct CpuLane {
    cpu: CpuId,
    apic_id: u32,
    online: bool,
    frame_epoch: u64,
    timer_ticks: u64,
    quantum_remaining: u32,
    watchdog_age: u32,
    events: [Option<Event>; EVENT_CAPACITY_PER_CPU],
    event_count: usize,
}

impl CpuLane {
    const fn new(cpu: CpuId) -> Self {
        Self {
            cpu,
            apic_id: cpu.value() as u32,
            online: true,
            frame_epoch: 0,
            timer_ticks: 0,
            quantum_remaining: QUANTUM_TICKS,
            watchdog_age: 0,
            events: [None; EVENT_CAPACITY_PER_CPU],
            event_count: 0,
        }
    }

    fn remove_first(&mut self) -> Result<Event, Error> {
        let event = self.events[0].ok_or(Error::Invariant)?;
        for index in 1..self.event_count {
            self.events[index - 1] = self.events[index];
        }
        self.event_count -= 1;
        self.events[self.event_count] = None;
        Ok(event)
    }
}

#[derive(Clone, Copy)]
pub struct SmpPreemption {
    scheduler: SmpScheduler,
    lanes: [CpuLane; CPU_COUNT],
    cancelled_events: u32,
    wake_events: u32,
    migration_events: u32,
    quantum_preemptions: u32,
    remote_reschedule_acks: u32,
    context_switches: u32,
    timeout_rollbacks: u32,
    stale_ack_rejections: u32,
    maximum_event_latency: u64,
    maximum_watchdog_age: u32,
    frame_owner_revocations: u32,
    timer_owner_revocations: u32,
    pending_remote: Option<TransferTicket>,
}

impl SmpPreemption {
    pub fn new(scheduler: SmpScheduler) -> Result<Self, Error> {
        scheduler.validate()?;
        if scheduler.summary().online_mask != ONLINE_MASK {
            return Err(Error::Invariant);
        }
        for value in 0..CPU_COUNT as u8 {
            if scheduler.current(CpuId::new(value)?)?.is_none() {
                return Err(Error::Invariant);
            }
        }
        let value = Self {
            scheduler,
            lanes: [
                CpuLane::new(CpuId::new(0).map_err(|_| Error::CpuRange)?),
                CpuLane::new(CpuId::new(1).map_err(|_| Error::CpuRange)?),
                CpuLane::new(CpuId::new(2).map_err(|_| Error::CpuRange)?),
                CpuLane::new(CpuId::new(3).map_err(|_| Error::CpuRange)?),
            ],
            cancelled_events: 0,
            wake_events: 0,
            migration_events: 0,
            quantum_preemptions: 0,
            remote_reschedule_acks: 0,
            context_switches: 0,
            timeout_rollbacks: 0,
            stale_ack_rejections: 0,
            maximum_event_latency: 0,
            maximum_watchdog_age: 0,
            frame_owner_revocations: 0,
            timer_owner_revocations: 0,
            pending_remote: None,
        };
        value.validate()?;
        Ok(value)
    }

    pub fn scheduler(&self) -> &SmpScheduler {
        &self.scheduler
    }

    pub fn current(&self, cpu: CpuId) -> Result<TaskId, Error> {
        self.scheduler.current(cpu)?.ok_or(Error::Invariant)
    }

    pub fn task_snapshot(
        &mut self,
        task: TaskId,
    ) -> Result<crate::scheduler_smp::TaskSnapshot, Error> {
        self.scheduler.task_snapshot(task).map_err(Into::into)
    }

    pub fn queue_event(&mut self, owner: CpuId, event: Event) -> Result<(), Error> {
        if self.pending_remote.is_some() {
            return Err(Error::PendingRemote);
        }
        let lane = &self.lanes[owner.index()];
        if event.due_tick <= lane.timer_ticks {
            return Err(Error::EventDeadline);
        }
        if event.sequence == 0 {
            return Err(Error::EventSequence);
        }
        if lane.event_count == EVENT_CAPACITY_PER_CPU {
            return Err(Error::EventCapacity);
        }
        if lane.events[..lane.event_count].contains(&Some(event)) {
            return Err(Error::EventDuplicate);
        }
        let task = self.scheduler.task_snapshot(event.kind.task())?;
        match event.kind {
            EventKind::Cancel { .. }
                if task.owner_cpu != Some(owner)
                    || !matches!(task.state, TaskState::Runnable | TaskState::Blocked) =>
            {
                return Err(Error::EventOwner);
            }
            EventKind::Wake { target, .. }
                if target != owner || task.state != TaskState::Blocked =>
            {
                return Err(Error::EventOwner);
            }
            EventKind::Migrate { target, .. }
                if target == owner
                    || task.owner_cpu != Some(owner)
                    || task.state != TaskState::Runnable =>
            {
                return Err(Error::EventOwner);
            }
            _ => {}
        }

        let lane = &mut self.lanes[owner.index()];
        let mut insert = lane.event_count;
        while insert > 0 {
            let prior = lane.events[insert - 1].ok_or(Error::Invariant)?;
            let prior_key = (prior.due_tick, prior.kind.order(), prior.sequence);
            let event_key = (event.due_tick, event.kind.order(), event.sequence);
            if prior_key <= event_key {
                break;
            }
            lane.events[insert] = Some(prior);
            insert -= 1;
        }
        lane.events[insert] = Some(event);
        lane.event_count += 1;
        self.validate()
    }

    pub fn handle_tick(
        &mut self,
        frame: &FrameContract,
        attempt: u64,
        sequence: u64,
    ) -> Result<TickOutcome, Error> {
        if self.pending_remote.is_some() {
            return Err(Error::PendingRemote);
        }
        self.validate_frame(frame)?;
        let before = *self;
        match self.handle_tick_inner(frame.cpu, attempt, sequence) {
            Ok(value) => Ok(value),
            Err(error) => {
                *self = before;
                Err(error)
            }
        }
    }

    fn handle_tick_inner(
        &mut self,
        cpu: CpuId,
        attempt: u64,
        sequence: u64,
    ) -> Result<TickOutcome, Error> {
        let previous = self.current(cpu)?;
        let lane = &mut self.lanes[cpu.index()];
        lane.timer_ticks = lane.timer_ticks.checked_add(1).ok_or(Error::Counter)?;
        lane.frame_epoch = lane.frame_epoch.checked_add(1).ok_or(Error::Counter)?;
        lane.quantum_remaining = lane
            .quantum_remaining
            .checked_sub(1)
            .ok_or(Error::Invariant)?;
        let tick = lane.timer_ticks;
        let mut processed = 0u8;
        let mut order = [0u8; EVENT_CAPACITY_PER_CPU];
        let mut cause = Cause::None;
        let mut ticket = None;

        while self.lanes[cpu.index()].event_count != 0 {
            let event = self.lanes[cpu.index()].events[0].ok_or(Error::Invariant)?;
            if event.due_tick > tick {
                break;
            }
            let event = self.lanes[cpu.index()].remove_first()?;
            let latency = tick.checked_sub(event.due_tick).ok_or(Error::Counter)?;
            if latency > MAX_EVENT_LATENCY_TICKS {
                return Err(Error::Watchdog);
            }
            self.maximum_event_latency = self.maximum_event_latency.max(latency);
            order[usize::from(processed)] = event.kind.order();
            processed = processed.checked_add(1).ok_or(Error::Counter)?;
            match event.kind {
                EventKind::Cancel { task } => {
                    self.scheduler.cancel_task(task)?;
                    self.cancelled_events = increment(self.cancelled_events)?;
                    cause = Cause::Cancel;
                }
                EventKind::Wake { task, target } => {
                    let staged = self.scheduler.stage_wake(task, target, attempt, sequence)?;
                    self.wake_events = increment(self.wake_events)?;
                    cause = Cause::Wake;
                    ticket = Some(staged);
                    break;
                }
                EventKind::Migrate { task, target } => {
                    let staged = self
                        .scheduler
                        .stage_migration(task, target, attempt, sequence)?;
                    self.migration_events = increment(self.migration_events)?;
                    cause = Cause::Migration;
                    ticket = Some(staged);
                    break;
                }
            }
        }

        if ticket.is_none() && self.lanes[cpu.index()].quantum_remaining == 0 {
            if self.scheduler.queue_len(cpu)? != 0 {
                let staged = self.scheduler.stage_preempt(cpu, attempt, sequence)?;
                self.quantum_preemptions = increment(self.quantum_preemptions)?;
                cause = Cause::Quantum;
                ticket = Some(staged);
            } else {
                self.lanes[cpu.index()].quantum_remaining = QUANTUM_TICKS;
                self.lanes[cpu.index()].watchdog_age = 0;
            }
        }
        if self.scheduler.queue_len(cpu)? != 0 {
            self.lanes[cpu.index()].watchdog_age = self.lanes[cpu.index()]
                .watchdog_age
                .checked_add(1)
                .ok_or(Error::Counter)?;
            if self.lanes[cpu.index()].watchdog_age > MAX_WATCHDOG_TICKS {
                return Err(Error::Watchdog);
            }
            self.maximum_watchdog_age = self
                .maximum_watchdog_age
                .max(self.lanes[cpu.index()].watchdog_age);
        }
        self.pending_remote = ticket;
        self.validate()?;
        Ok(TickOutcome {
            cpu,
            tick,
            previous,
            cause,
            events_processed: processed,
            event_order: order,
            remote_ticket: ticket,
            quantum_remaining: self.lanes[cpu.index()].quantum_remaining,
        })
    }

    pub fn acknowledge_reschedule(
        &mut self,
        ticket: TransferTicket,
        ack: RemoteAck,
    ) -> Result<(), Error> {
        if self.pending_remote != Some(ticket) {
            return Err(Error::PendingRemote);
        }
        let target = CpuId::new(ticket.target_cpu)?;
        let before = self.scheduler.current(target)?;
        self.scheduler.acknowledge_reschedule(ticket, ack)?;
        let after = self.scheduler.current(target)?;
        self.pending_remote = None;
        self.remote_reschedule_acks = increment(self.remote_reschedule_acks)?;
        if ticket.kind == TransferKind::Preempt {
            self.lanes[target.index()].quantum_remaining = QUANTUM_TICKS;
            self.lanes[target.index()].watchdog_age = 0;
            if before != after {
                self.context_switches = increment(self.context_switches)?;
            }
        }
        self.validate()
    }

    pub fn prove_offline_rollback(
        &mut self,
        task: TaskId,
        attempt: u64,
        sequence: u64,
    ) -> Result<TransferTicket, Error> {
        let ticket = self.stage_offline_probe(task, attempt, sequence)?;
        self.timeout_offline(ticket)?;
        Ok(ticket)
    }

    pub fn stage_offline_probe(
        &mut self,
        task: TaskId,
        attempt: u64,
        sequence: u64,
    ) -> Result<TransferTicket, Error> {
        if self.pending_remote.is_some() {
            return Err(Error::PendingRemote);
        }
        let ticket =
            self.scheduler
                .stage_offline_probe(task, OFFLINE_PROBE_CPU, attempt, sequence)?;
        self.pending_remote = Some(ticket);
        self.validate()?;
        Ok(ticket)
    }

    pub fn timeout_offline(&mut self, ticket: TransferTicket) -> Result<(), Error> {
        if self.pending_remote != Some(ticket) || ticket.kind != TransferKind::OfflineProbe {
            return Err(Error::PendingRemote);
        }
        self.scheduler.timeout(ticket)?;
        self.pending_remote = None;
        self.timeout_rollbacks = increment(self.timeout_rollbacks)?;
        self.scheduler.reject_stale_ack(
            ticket,
            RemoteAck {
                target_cpu: ticket.target_cpu,
                attempt: ticket.request_attempt,
                sequence: ticket.request_sequence,
                operation: RESCHEDULE_OPERATION,
                status: ACK_ACCEPTED,
                error: ERROR_NONE,
                result: RESCHEDULE_RESULT,
            },
        )?;
        self.stale_ack_rejections = increment(self.stale_ack_rejections)?;
        self.validate()?;
        Ok(())
    }

    pub fn finish_shutdown(&mut self, tasks: [TaskId; TASK_CAPACITY]) -> Result<(), Error> {
        if self.pending_remote.is_some() || self.lanes.iter().any(|lane| lane.event_count != 0) {
            return Err(Error::Shutdown);
        }
        for value in 0..CPU_COUNT as u8 {
            let cpu = CpuId::new(value)?;
            if self.scheduler.current(cpu)?.is_some() {
                self.scheduler.complete_current(cpu)?;
            }
        }
        for task in tasks {
            match self.scheduler.task_snapshot(task)?.state {
                TaskState::Runnable | TaskState::Blocked => self.scheduler.cancel_task(task)?,
                TaskState::Dead => {}
                _ => return Err(Error::Shutdown),
            }
        }
        for value in (1..CPU_COUNT as u8).rev() {
            let cpu = CpuId::new(value)?;
            self.scheduler.offline_idle_cpu(cpu)?;
            self.lanes[cpu.index()].online = false;
            self.frame_owner_revocations = increment(self.frame_owner_revocations)?;
            self.timer_owner_revocations = increment(self.timer_owner_revocations)?;
        }
        self.validate()
    }

    pub fn summary(&self) -> Summary {
        let mut frame_epochs = [0u64; CPU_COUNT];
        let mut timer_ticks = [0u64; CPU_COUNT];
        let mut pending_events = 0u8;
        for (index, lane) in self.lanes.iter().enumerate() {
            frame_epochs[index] = lane.frame_epoch;
            timer_ticks[index] = lane.timer_ticks;
            pending_events = pending_events.saturating_add(lane.event_count as u8);
        }
        Summary {
            online_mask: self.scheduler.summary().online_mask,
            frame_epochs,
            timer_ticks,
            pending_events,
            cancelled_events: self.cancelled_events,
            wake_events: self.wake_events,
            migration_events: self.migration_events,
            quantum_preemptions: self.quantum_preemptions,
            remote_reschedule_acks: self.remote_reschedule_acks,
            context_switches: self.context_switches,
            timeout_rollbacks: self.timeout_rollbacks,
            stale_ack_rejections: self.stale_ack_rejections,
            maximum_event_latency: self.maximum_event_latency,
            maximum_watchdog_age: self.maximum_watchdog_age,
            frame_owner_revocations: self.frame_owner_revocations,
            timer_owner_revocations: self.timer_owner_revocations,
            scheduler: self.scheduler.summary(),
        }
    }

    pub fn validate(&self) -> Result<(), Error> {
        self.scheduler.validate()?;
        if self.maximum_event_latency > MAX_EVENT_LATENCY_TICKS
            || self.maximum_watchdog_age > MAX_WATCHDOG_TICKS
        {
            return Err(Error::Watchdog);
        }
        if self.pending_remote.is_some() != self.scheduler.has_pending() {
            return Err(Error::Invariant);
        }
        for lane in &self.lanes {
            if lane.cpu.index() >= CPU_COUNT
                || lane.apic_id != u32::from(lane.cpu.value())
                || lane.frame_epoch != lane.timer_ticks
                || lane.quantum_remaining == 0
                    && self.pending_remote.is_none_or(|ticket| {
                        ticket.kind != TransferKind::Preempt
                            || ticket.target_cpu as usize != lane.cpu.index()
                    })
                || lane.quantum_remaining > QUANTUM_TICKS
                || lane.watchdog_age > MAX_WATCHDOG_TICKS
                || lane.event_count > EVENT_CAPACITY_PER_CPU
                || lane.events[lane.event_count..].iter().any(Option::is_some)
            {
                return Err(Error::Invariant);
            }
            if lane.online != (self.scheduler.summary().online_mask & lane.cpu.mask() != 0) {
                return Err(Error::Invariant);
            }
            let mut prior = (lane.timer_ticks, 0u8, 0u64);
            for event in lane.events[..lane.event_count].iter().copied() {
                let event = event.ok_or(Error::Invariant)?;
                let key = (event.due_tick, event.kind.order(), event.sequence);
                if event.due_tick <= lane.timer_ticks || key < prior {
                    return Err(Error::Invariant);
                }
                prior = key;
            }
        }
        Ok(())
    }

    fn validate_frame(&self, frame: &FrameContract) -> Result<(), Error> {
        let lane = self.lanes.get(frame.cpu.index()).ok_or(Error::FrameCpu)?;
        if !lane.online || lane.cpu != frame.cpu {
            return Err(Error::FrameCpu);
        }
        if frame.apic_id != lane.apic_id {
            return Err(Error::FrameApic);
        }
        if frame.frame_owner != self.current(frame.cpu)? {
            return Err(Error::EventOwner);
        }
        if frame.frame_epoch != lane.frame_epoch + 1 || frame.timer_epoch != lane.timer_ticks + 1 {
            return Err(Error::FrameEpoch);
        }
        if frame.vector != u64::from(TIMER_VECTOR) {
            return Err(Error::FrameVector);
        }
        if frame.error_code != 0 {
            return Err(Error::FrameErrorCode);
        }
        if frame.code_selector != KERNEL_CODE_SELECTOR
            || frame.data_selector != KERNEL_DATA_SELECTOR
        {
            return Err(Error::FrameSelector);
        }
        if frame.interrupted_rflags & (1 << 1) == 0
            || frame.interrupted_rflags & (1 << 9) == 0
            || frame.interrupted_rflags & ((1 << 14) | (1 << 17)) != 0
        {
            return Err(Error::FrameFlags);
        }
        if !frame.handler_interrupts_disabled {
            return Err(Error::FrameInterruptState);
        }
        if !frame.scheduler_lock_held {
            return Err(Error::FrameLock);
        }
        let (bottom, top) = ist_range(frame.cpu);
        if frame.ist_bottom != bottom
            || frame.ist_top != top
            || frame.frame_bytes == 0
            || frame.handler_rsp < bottom
            || frame
                .handler_rsp
                .checked_add(frame.frame_bytes)
                .is_none_or(|end| end > top)
        {
            return Err(Error::FrameStack);
        }
        Ok(())
    }
}

pub const fn ist_range(cpu: CpuId) -> (u64, u64) {
    let bottom = IST_BASE + cpu.value() as u64 * IST_STRIDE;
    (bottom, bottom + IST_BYTES_PER_CPU)
}

pub fn canonical_frame(
    cpu: CpuId,
    owner: TaskId,
    frame_epoch: u64,
    timer_epoch: u64,
) -> FrameContract {
    let (bottom, top) = ist_range(cpu);
    FrameContract {
        cpu,
        apic_id: u32::from(cpu.value()),
        frame_owner: owner,
        frame_epoch,
        timer_epoch,
        vector: u64::from(TIMER_VECTOR),
        error_code: 0,
        code_selector: KERNEL_CODE_SELECTOR,
        data_selector: KERNEL_DATA_SELECTOR,
        interrupted_rflags: (1 << 1) | (1 << 9),
        handler_interrupts_disabled: true,
        scheduler_lock_held: true,
        handler_rsp: top - 256,
        frame_bytes: 176,
        ist_bottom: bottom,
        ist_top: top,
    }
}

pub const fn canonical_reschedule_ack(ticket: TransferTicket) -> RemoteAck {
    RemoteAck {
        target_cpu: ticket.target_cpu,
        attempt: ticket.request_attempt,
        sequence: ticket.request_sequence,
        operation: RESCHEDULE_OPERATION,
        status: ACK_ACCEPTED,
        error: ERROR_NONE,
        result: RESCHEDULE_RESULT,
    }
}

fn increment(value: u32) -> Result<u32, Error> {
    value.checked_add(1).ok_or(Error::Counter)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cpu(value: u8) -> CpuId {
        CpuId::new(value).expect("CPU")
    }

    fn fixture() -> (SmpPreemption, [TaskId; TASK_CAPACITY]) {
        let mut scheduler = SmpScheduler::new();
        let mut tasks = [TaskId::new(0, 1).expect("identity"); TASK_CAPACITY];
        for slot in 0..TASK_CAPACITY {
            let owner = (slot / 2) as u8;
            let affinity = match slot {
                1 => 0x03,
                5 => 0x0c,
                _ => 1 << owner,
            };
            let id = scheduler
                .create_task(slot as u8, 1, 16, affinity)
                .expect("create");
            scheduler.activate(id, cpu(owner)).expect("activate");
            tasks[slot] = id;
        }
        for value in 0..CPU_COUNT as u8 {
            let ticket = scheduler
                .stage_dispatch(cpu(value), 1, 1)
                .expect("initial dispatch");
            scheduler
                .acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))
                .expect("initial dispatch ack");
        }
        scheduler
            .block_runnable(tasks[1])
            .expect("blocked wake task");
        (SmpPreemption::new(scheduler).expect("controller"), tasks)
    }

    #[test]
    fn same_tick_cancel_precedes_wake_and_remote_ack_commits_the_wake() {
        let (mut controller, tasks) = fixture();
        controller
            .queue_event(
                cpu(1),
                Event {
                    due_tick: 1,
                    sequence: 2,
                    kind: EventKind::Wake {
                        task: tasks[1],
                        target: cpu(1),
                    },
                },
            )
            .expect("wake");
        controller
            .queue_event(
                cpu(1),
                Event {
                    due_tick: 1,
                    sequence: 1,
                    kind: EventKind::Cancel { task: tasks[3] },
                },
            )
            .expect("cancel");
        let frame = canonical_frame(cpu(1), controller.current(cpu(1)).unwrap(), 1, 1);
        let outcome = controller.handle_tick(&frame, 3, 2).expect("tick");
        assert_eq!(outcome.event_order[..2], [1, 2]);
        let ticket = outcome.remote_ticket.expect("wake ticket");
        assert_eq!(
            controller.task_snapshot(tasks[1]).unwrap().state,
            TaskState::Blocked
        );
        controller
            .acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))
            .expect("wake ack");
        assert_eq!(controller.summary().cancelled_events, 1);
        assert_eq!(controller.summary().wake_events, 1);
    }

    #[test]
    fn quantum_preemption_keeps_current_owner_until_exact_remote_ack() {
        let (mut controller, _) = fixture();
        for epoch in 1..=2 {
            let owner = controller.current(cpu(3)).unwrap();
            let frame = canonical_frame(cpu(3), owner, epoch, epoch);
            let outcome = controller
                .handle_tick(&frame, epoch + 2, epoch + 1)
                .expect("tick");
            if let Some(ticket) = outcome.remote_ticket {
                assert_eq!(controller.current(cpu(3)).unwrap(), owner);
                controller
                    .acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))
                    .expect("preempt ack");
                assert_ne!(controller.current(cpu(3)).unwrap(), owner);
            }
        }
        assert_eq!(controller.summary().quantum_preemptions, 1);
        assert_eq!(controller.summary().context_switches, 1);
    }

    #[test]
    fn migration_and_offline_timeout_preserve_exact_source_ownership() {
        let (mut controller, tasks) = fixture();
        let before = controller.task_snapshot(tasks[5]).unwrap().owner_cpu;
        controller
            .prove_offline_rollback(tasks[5], 3, 2)
            .expect("offline rollback");
        assert_eq!(
            controller.task_snapshot(tasks[5]).unwrap().owner_cpu,
            before
        );
        controller
            .queue_event(
                cpu(2),
                Event {
                    due_tick: 1,
                    sequence: 1,
                    kind: EventKind::Migrate {
                        task: tasks[5],
                        target: cpu(3),
                    },
                },
            )
            .expect("migration");
        let frame = canonical_frame(cpu(2), controller.current(cpu(2)).unwrap(), 1, 1);
        let outcome = controller.handle_tick(&frame, 3, 2).expect("tick");
        let ticket = outcome.remote_ticket.expect("migration ticket");
        controller
            .acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))
            .expect("migration ack");
        assert_eq!(
            controller.task_snapshot(tasks[5]).unwrap().owner_cpu,
            Some(cpu(3))
        );
    }

    #[test]
    fn frame_contract_rejects_cross_cpu_epoch_and_stack_substitution() {
        let (mut controller, _) = fixture();
        let mut frame = canonical_frame(cpu(1), controller.current(cpu(1)).unwrap(), 1, 1);
        frame.apic_id = 2;
        assert_eq!(controller.handle_tick(&frame, 3, 2), Err(Error::FrameApic));
        frame = canonical_frame(cpu(1), controller.current(cpu(1)).unwrap(), 2, 1);
        assert_eq!(controller.handle_tick(&frame, 3, 2), Err(Error::FrameEpoch));
        frame = canonical_frame(cpu(1), controller.current(cpu(1)).unwrap(), 1, 1);
        frame.ist_bottom += IST_STRIDE;
        assert_eq!(controller.handle_tick(&frame, 3, 2), Err(Error::FrameStack));
    }

    #[test]
    fn complete_shutdown_revokes_ap_timer_and_frame_owners() {
        let (mut controller, tasks) = fixture();
        controller.finish_shutdown(tasks).expect("shutdown");
        let summary = controller.summary();
        assert_eq!(summary.online_mask, 1);
        assert_eq!(summary.scheduler.dead_count as usize, TASK_CAPACITY);
        assert_eq!(summary.scheduler.teardown_count as usize, TASK_CAPACITY);
        assert_eq!(summary.frame_owner_revocations, 3);
        assert_eq!(summary.timer_owner_revocations, 3);
        assert_eq!(controller.validate(), Ok(()));
    }
}
