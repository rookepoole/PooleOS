//! Allocation-free PKSCHED5 AP-local typed deferred-work ownership.

use crate::smp_ipi;

pub const CONTRACT_ID: &str = "PKSCHED5";
pub const SELECTED_MOVE_ID: &str = "N12-SCHED-AP-WORKERS-001";
pub const CPU_COUNT: usize = 4;
pub const AP_COUNT: usize = 3;
pub const WORK_CAPACITY: usize = 15;
pub const ONLINE_MASK: u8 = 0x0f;
pub const AP_MASK: u8 = 0x0e;
pub const OFFLINE_PROBE_CPU: u8 = 4;
pub const MAX_HIGH_BYPASS: u8 = 2;
pub const WORKER_STACK_BYTES: u32 = 8 * 1024;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Capacity,
    Duplicate,
    IntakeClosed,
    TopHalfContext,
    CpuRange,
    CpuOffline,
    InvalidRequest,
    DispatchBeforeEoi,
    Empty,
    PendingBusy,
    PendingMissing,
    TicketMismatch,
    Acknowledgement,
    TimeoutTarget,
    StaleId,
    State,
    FlushPending,
    ReclaimOrder,
    WorkerBusy,
    Counter,
    Invariant,
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Capacity => "capacity",
            Self::Duplicate => "duplicate",
            Self::IntakeClosed => "intake_closed",
            Self::TopHalfContext => "top_half_context",
            Self::CpuRange => "cpu_range",
            Self::CpuOffline => "cpu_offline",
            Self::InvalidRequest => "invalid_request",
            Self::DispatchBeforeEoi => "dispatch_before_eoi",
            Self::Empty => "empty",
            Self::PendingBusy => "pending_busy",
            Self::PendingMissing => "pending_missing",
            Self::TicketMismatch => "ticket_mismatch",
            Self::Acknowledgement => "acknowledgement",
            Self::TimeoutTarget => "timeout_target",
            Self::StaleId => "stale_id",
            Self::State => "state",
            Self::FlushPending => "flush_pending",
            Self::ReclaimOrder => "reclaim_order",
            Self::WorkerBusy => "worker_busy",
            Self::Counter => "counter",
            Self::Invariant => "invariant",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Priority {
    High,
    Normal,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Consumer {
    DriverTimerBottomHalf {
        vector: u8,
        sample: u32,
    },
    ServiceGenerationReclaim {
        retired_generation: u32,
        active_generation: u32,
    },
}

impl Consumer {
    pub const fn payload(self) -> u64 {
        match self {
            Self::DriverTimerBottomHalf { .. } => smp_ipi::CALL_DRIVER_TIMER_TOKEN,
            Self::ServiceGenerationReclaim { .. } => smp_ipi::CALL_SERVICE_RECLAIM_TOKEN,
        }
    }

    pub const fn expected_result(self) -> u64 {
        match self {
            Self::DriverTimerBottomHalf { .. } => smp_ipi::RESULT_CALL_DRIVER_TIMER,
            Self::ServiceGenerationReclaim { .. } => smp_ipi::RESULT_CALL_SERVICE_RECLAIM,
        }
    }

    const fn valid(self) -> bool {
        match self {
            Self::DriverTimerBottomHalf { vector, sample } => vector == 64 && sample != 0,
            Self::ServiceGenerationReclaim {
                retired_generation,
                active_generation,
            } => retired_generation != 0 && active_generation == retired_generation.wrapping_add(1),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WorkRequest {
    pub key: u16,
    pub source_cpu: u8,
    pub target_cpu: u8,
    pub priority: Priority,
    pub consumer: Consumer,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WorkId {
    pub slot: u8,
    pub generation: u32,
}

impl WorkId {
    pub const fn new(slot: u8, generation: u32) -> Result<Self, Error> {
        if slot as usize >= WORK_CAPACITY || generation == 0 {
            Err(Error::StaleId)
        } else {
            Ok(Self { slot, generation })
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WorkState {
    Free,
    Queued,
    Dispatching,
    Completed,
    Cancelled,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TopHalfContext {
    pub interrupt_depth: u8,
    pub interrupts_disabled: bool,
    pub queue_lock_held: bool,
    pub worker_context: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DispatchPermit {
    pub eoi_epoch: u64,
    pub enqueue_watermark: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FlushToken {
    pub enqueue_watermark: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DispatchTicket {
    pub transaction: u64,
    pub id: WorkId,
    pub source_cpu: u8,
    pub target_cpu: u8,
    pub worker_generation: u32,
    pub request_attempt: u64,
    pub request_sequence: u64,
    pub payload: u64,
    pub expected_result: u64,
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
pub struct Receipt {
    pub id: WorkId,
    pub target_cpu: u8,
    pub state: WorkState,
    pub completion_sequence: u64,
    pub result: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub intake_open: bool,
    pub shutdown_complete: bool,
    pub online_mask: u8,
    pub enqueue_sequence: u64,
    pub completion_sequence: u64,
    pub eoi_epoch: u64,
    pub enqueued: u32,
    pub completed: u32,
    pub cancelled: u32,
    pub queued_cancellations: u32,
    pub remote_cancel_requests: u32,
    pub remote_cancel_completions: u32,
    pub duplicate_suppressed: u32,
    pub dispatches: u32,
    pub remote_acks: u32,
    pub timeout_count: u32,
    pub rollback_count: u32,
    pub stale_rejections: u32,
    pub reclaimed: u32,
    pub worker_retirements: u32,
    pub driver_executions: u32,
    pub service_executions: u32,
    pub worker_entries: [u32; AP_COUNT],
    pub queued: u8,
    pub dispatching: u8,
    pub terminal: u8,
    pub free: u8,
    pub maximum_high_bypass: u8,
    pub driver_sample_sum: u32,
    pub active_service_generation: u32,
}

const EMPTY_CONSUMER: Consumer = Consumer::DriverTimerBottomHalf {
    vector: 64,
    sample: 1,
};

const EMPTY_REQUEST: WorkRequest = WorkRequest {
    key: 0,
    source_cpu: 0,
    target_cpu: 1,
    priority: Priority::Normal,
    consumer: EMPTY_CONSUMER,
};

#[derive(Clone, Copy)]
struct Slot {
    generation: u32,
    state: WorkState,
    request: WorkRequest,
    enqueue_sequence: u64,
    completion_sequence: u64,
    cancel_requested: bool,
    result: u64,
}

impl Slot {
    const EMPTY: Self = Self {
        generation: 0,
        state: WorkState::Free,
        request: EMPTY_REQUEST,
        enqueue_sequence: 0,
        completion_sequence: 0,
        cancel_requested: false,
        result: 0,
    };

    const fn id(self, index: usize) -> WorkId {
        WorkId {
            slot: index as u8,
            generation: self.generation,
        }
    }
}

#[derive(Clone, Copy)]
pub struct ApWorkerController {
    slots: [Slot; WORK_CAPACITY],
    pending: [Option<DispatchTicket>; CPU_COUNT],
    offline_pending: Option<DispatchTicket>,
    last_timed_out: Option<DispatchTicket>,
    intake_open: bool,
    shutdown_complete: bool,
    online_mask: u8,
    worker_generation: [u32; CPU_COUNT],
    high_bypass: [u8; CPU_COUNT],
    enqueue_sequence: u64,
    completion_sequence: u64,
    eoi_epoch: u64,
    transaction_sequence: u64,
    enqueued: u32,
    completed: u32,
    cancelled: u32,
    queued_cancellations: u32,
    remote_cancel_requests: u32,
    remote_cancel_completions: u32,
    duplicate_suppressed: u32,
    dispatches: u32,
    remote_acks: u32,
    timeout_count: u32,
    rollback_count: u32,
    stale_rejections: u32,
    reclaimed: u32,
    worker_retirements: u32,
    driver_executions: u32,
    service_executions: u32,
    worker_entries: [u32; AP_COUNT],
    maximum_high_bypass: u8,
    driver_sample_sum: u32,
    active_service_generation: u32,
}

impl Default for ApWorkerController {
    fn default() -> Self {
        Self::new()
    }
}

impl ApWorkerController {
    pub const fn new() -> Self {
        Self {
            slots: [Slot::EMPTY; WORK_CAPACITY],
            pending: [None; CPU_COUNT],
            offline_pending: None,
            last_timed_out: None,
            intake_open: true,
            shutdown_complete: false,
            online_mask: ONLINE_MASK,
            worker_generation: [0, 1, 1, 1],
            high_bypass: [0; CPU_COUNT],
            enqueue_sequence: 0,
            completion_sequence: 0,
            eoi_epoch: 0,
            transaction_sequence: 0,
            enqueued: 0,
            completed: 0,
            cancelled: 0,
            queued_cancellations: 0,
            remote_cancel_requests: 0,
            remote_cancel_completions: 0,
            duplicate_suppressed: 0,
            dispatches: 0,
            remote_acks: 0,
            timeout_count: 0,
            rollback_count: 0,
            stale_rejections: 0,
            reclaimed: 0,
            worker_retirements: 0,
            driver_executions: 0,
            service_executions: 0,
            worker_entries: [0; AP_COUNT],
            maximum_high_bypass: 0,
            driver_sample_sum: 0,
            active_service_generation: 1,
        }
    }

    pub fn enqueue_from_top_half(
        &mut self,
        context: TopHalfContext,
        request: WorkRequest,
    ) -> Result<WorkId, Error> {
        if !self.intake_open {
            return Err(Error::IntakeClosed);
        }
        if context.interrupt_depth != 1
            || !context.interrupts_disabled
            || context.queue_lock_held
            || context.worker_context
        {
            return Err(Error::TopHalfContext);
        }
        if request.key == 0
            || request.source_cpu != 0
            || request.target_cpu == 0
            || request.target_cpu as usize >= CPU_COUNT
            || !request.consumer.valid()
        {
            return Err(Error::InvalidRequest);
        }
        if self.online_mask & (1 << request.target_cpu) == 0 {
            return Err(Error::CpuOffline);
        }
        if self.slots.iter().any(|slot| {
            slot.state != WorkState::Free
                && slot.request.key == request.key
                && slot.request.target_cpu == request.target_cpu
        }) {
            self.duplicate_suppressed = increment(self.duplicate_suppressed)?;
            return Err(Error::Duplicate);
        }
        let index = self
            .slots
            .iter()
            .position(|slot| slot.state == WorkState::Free)
            .ok_or(Error::Capacity)?;
        self.enqueue_sequence = self.enqueue_sequence.checked_add(1).ok_or(Error::Counter)?;
        let generation = self.slots[index]
            .generation
            .checked_add(1)
            .ok_or(Error::Counter)?;
        self.slots[index] = Slot {
            generation,
            state: WorkState::Queued,
            request,
            enqueue_sequence: self.enqueue_sequence,
            completion_sequence: 0,
            cancel_requested: false,
            result: 0,
        };
        self.enqueued = increment(self.enqueued)?;
        self.validate()?;
        Ok(self.slots[index].id(index))
    }

    pub fn observe_eoi(&mut self) -> Result<DispatchPermit, Error> {
        self.eoi_epoch = self.eoi_epoch.checked_add(1).ok_or(Error::Counter)?;
        Ok(DispatchPermit {
            eoi_epoch: self.eoi_epoch,
            enqueue_watermark: self.enqueue_sequence,
        })
    }

    pub const fn begin_flush(&self) -> FlushToken {
        FlushToken {
            enqueue_watermark: self.enqueue_sequence,
        }
    }

    pub fn flush_complete(&self, token: FlushToken) -> bool {
        self.slots.iter().all(|slot| {
            slot.state == WorkState::Free
                || slot.enqueue_sequence > token.enqueue_watermark
                || matches!(slot.state, WorkState::Completed | WorkState::Cancelled)
        })
    }

    pub fn stage_dispatch(
        &mut self,
        target_cpu: u8,
        permit: DispatchPermit,
        request_attempt: u64,
        request_sequence: u64,
    ) -> Result<DispatchTicket, Error> {
        self.require_dispatch_permit(permit)?;
        let target = self.require_ap(target_cpu)?;
        if self.pending[target].is_some() {
            return Err(Error::PendingBusy);
        }
        let index = self.select_next(target_cpu).ok_or(Error::Empty)?;
        if self.slots[index].enqueue_sequence > permit.enqueue_watermark {
            return Err(Error::DispatchBeforeEoi);
        }
        let ticket = self.install_ticket(
            index,
            self.slots[index].request.target_cpu,
            target_cpu,
            self.worker_generation[target],
            request_attempt,
            request_sequence,
        )?;
        self.pending[target] = Some(ticket);
        self.dispatches = increment(self.dispatches)?;
        self.validate()?;
        Ok(ticket)
    }

    pub fn stage_offline_probe(
        &mut self,
        id: WorkId,
        offline_cpu: u8,
        permit: DispatchPermit,
        request_attempt: u64,
        request_sequence: u64,
    ) -> Result<DispatchTicket, Error> {
        self.require_dispatch_permit(permit)?;
        if offline_cpu != OFFLINE_PROBE_CPU {
            return Err(Error::TimeoutTarget);
        }
        if self.offline_pending.is_some() {
            return Err(Error::PendingBusy);
        }
        let index = self.resolve(id)?;
        if self.slots[index].state != WorkState::Queued {
            return Err(Error::State);
        }
        if self.slots[index].enqueue_sequence > permit.enqueue_watermark {
            return Err(Error::DispatchBeforeEoi);
        }
        let ticket = self.install_ticket(
            index,
            self.slots[index].request.target_cpu,
            offline_cpu,
            0,
            request_attempt,
            request_sequence,
        )?;
        self.offline_pending = Some(ticket);
        self.validate()?;
        Ok(ticket)
    }

    pub fn cancel(&mut self, id: WorkId) -> Result<(), Error> {
        let index = self.resolve(id)?;
        match self.slots[index].state {
            WorkState::Queued => {
                self.complete_terminal(index, WorkState::Cancelled, 0)?;
                self.queued_cancellations = increment(self.queued_cancellations)?;
            }
            WorkState::Dispatching => {
                if self.slots[index].cancel_requested {
                    return Err(Error::State);
                }
                self.slots[index].cancel_requested = true;
                self.remote_cancel_requests = increment(self.remote_cancel_requests)?;
            }
            _ => return Err(Error::State),
        }
        self.validate()
    }

    pub fn acknowledge(
        &mut self,
        ticket: DispatchTicket,
        ack: RemoteAck,
    ) -> Result<Receipt, Error> {
        let target = self.require_ap(ticket.target_cpu)?;
        if self.pending[target] != Some(ticket) {
            return Err(Error::TicketMismatch);
        }
        if ack.target_cpu != ticket.target_cpu
            || ack.attempt != ticket.request_attempt
            || ack.sequence != ticket.request_sequence
            || ack.operation != smp_ipi::Operation::CallFunction as u32
            || ack.status != smp_ipi::ACK_ACCEPTED
            || ack.error != smp_ipi::ERROR_NONE
            || ack.result != ticket.expected_result
        {
            return Err(Error::Acknowledgement);
        }
        let index = self.resolve(ticket.id)?;
        if self.slots[index].state != WorkState::Dispatching
            || self.slots[index].request.target_cpu != ticket.source_cpu
            || self.worker_generation[target] != ticket.worker_generation
        {
            return Err(Error::State);
        }
        let consumer = self.slots[index].request.consumer;
        let mut next_driver_sample_sum = self.driver_sample_sum;
        let mut next_service_generation = self.active_service_generation;
        if !self.slots[index].cancel_requested {
            match consumer {
                Consumer::DriverTimerBottomHalf { sample, .. } => {
                    next_driver_sample_sum = next_driver_sample_sum
                        .checked_add(sample)
                        .ok_or(Error::Counter)?;
                }
                Consumer::ServiceGenerationReclaim {
                    retired_generation,
                    active_generation,
                } => {
                    if retired_generation != next_service_generation {
                        return Err(Error::ReclaimOrder);
                    }
                    next_service_generation = active_generation;
                }
            }
        }
        self.pending[target] = None;
        self.worker_entries[target - 1] = increment(self.worker_entries[target - 1])?;
        self.remote_acks = increment(self.remote_acks)?;
        match consumer {
            Consumer::DriverTimerBottomHalf { .. } => {
                self.driver_executions = increment(self.driver_executions)?;
            }
            Consumer::ServiceGenerationReclaim { .. } => {
                self.service_executions = increment(self.service_executions)?;
            }
        }
        let state = if self.slots[index].cancel_requested {
            self.remote_cancel_completions = increment(self.remote_cancel_completions)?;
            WorkState::Cancelled
        } else {
            self.driver_sample_sum = next_driver_sample_sum;
            self.active_service_generation = next_service_generation;
            WorkState::Completed
        };
        self.complete_terminal(index, state, ack.result)?;
        let receipt = Receipt {
            id: ticket.id,
            target_cpu: ticket.target_cpu,
            state,
            completion_sequence: self.slots[index].completion_sequence,
            result: ack.result,
        };
        self.validate()?;
        Ok(receipt)
    }

    pub fn timeout(&mut self, ticket: DispatchTicket) -> Result<(), Error> {
        if ticket.target_cpu != OFFLINE_PROBE_CPU || self.offline_pending != Some(ticket) {
            return Err(Error::TimeoutTarget);
        }
        let index = self.resolve(ticket.id)?;
        if self.slots[index].state != WorkState::Dispatching
            || self.slots[index].request.target_cpu != ticket.source_cpu
        {
            return Err(Error::State);
        }
        self.slots[index].state = WorkState::Queued;
        self.offline_pending = None;
        self.last_timed_out = Some(ticket);
        self.timeout_count = increment(self.timeout_count)?;
        self.rollback_count = increment(self.rollback_count)?;
        self.validate()
    }

    pub fn reject_stale_ack(
        &mut self,
        ticket: DispatchTicket,
        ack: RemoteAck,
    ) -> Result<(), Error> {
        if self.last_timed_out != Some(ticket)
            || self.offline_pending.is_some()
            || ack.target_cpu != ticket.target_cpu
            || ack.attempt != ticket.request_attempt
            || ack.sequence != ticket.request_sequence
        {
            return Err(Error::TicketMismatch);
        }
        self.stale_rejections = increment(self.stale_rejections)?;
        Ok(())
    }

    pub fn reclaim(&mut self, id: WorkId, token: FlushToken) -> Result<(), Error> {
        if !self.flush_complete(token) {
            return Err(Error::FlushPending);
        }
        let index = self.resolve(id)?;
        if self.slots[index].enqueue_sequence > token.enqueue_watermark {
            return Err(Error::ReclaimOrder);
        }
        if !matches!(
            self.slots[index].state,
            WorkState::Completed | WorkState::Cancelled
        ) {
            return Err(Error::State);
        }
        let generation = self.slots[index].generation;
        self.slots[index] = Slot {
            generation,
            ..Slot::EMPTY
        };
        self.reclaimed = increment(self.reclaimed)?;
        self.validate()
    }

    pub fn retire_all_terminal(&mut self, token: FlushToken) -> Result<u8, Error> {
        if !self.flush_complete(token) {
            return Err(Error::FlushPending);
        }
        let mut retired = 0u8;
        for index in 0..WORK_CAPACITY {
            if matches!(
                self.slots[index].state,
                WorkState::Completed | WorkState::Cancelled
            ) && self.slots[index].enqueue_sequence <= token.enqueue_watermark
            {
                let id = self.slots[index].id(index);
                self.reclaim(id, token)?;
                retired = retired.checked_add(1).ok_or(Error::Counter)?;
            }
        }
        Ok(retired)
    }

    pub fn offline_worker(&mut self, cpu: u8) -> Result<(), Error> {
        let index = self.require_ap(cpu)?;
        if self.pending[index].is_some()
            || self
                .slots
                .iter()
                .any(|slot| slot.state != WorkState::Free && slot.request.target_cpu == cpu)
        {
            return Err(Error::WorkerBusy);
        }
        self.online_mask &= !(1 << cpu);
        self.worker_generation[index] = self.worker_generation[index]
            .checked_add(1)
            .ok_or(Error::Counter)?;
        self.worker_retirements = increment(self.worker_retirements)?;
        self.validate()
    }

    pub fn finish_shutdown(&mut self) -> Result<(), Error> {
        self.intake_open = false;
        if self.online_mask != 1
            || self.offline_pending.is_some()
            || self.pending.iter().any(Option::is_some)
            || self.slots.iter().any(|slot| slot.state != WorkState::Free)
        {
            return Err(Error::WorkerBusy);
        }
        self.shutdown_complete = true;
        self.validate()
    }

    pub fn request(&self, id: WorkId) -> Result<WorkRequest, Error> {
        Ok(self.slots[self.resolve(id)?].request)
    }

    pub fn summary(&self) -> Summary {
        let mut queued = 0u8;
        let mut dispatching = 0u8;
        let mut terminal = 0u8;
        let mut free = 0u8;
        for slot in &self.slots {
            match slot.state {
                WorkState::Free => free += 1,
                WorkState::Queued => queued += 1,
                WorkState::Dispatching => dispatching += 1,
                WorkState::Completed | WorkState::Cancelled => terminal += 1,
            }
        }
        Summary {
            intake_open: self.intake_open,
            shutdown_complete: self.shutdown_complete,
            online_mask: self.online_mask,
            enqueue_sequence: self.enqueue_sequence,
            completion_sequence: self.completion_sequence,
            eoi_epoch: self.eoi_epoch,
            enqueued: self.enqueued,
            completed: self.completed,
            cancelled: self.cancelled,
            queued_cancellations: self.queued_cancellations,
            remote_cancel_requests: self.remote_cancel_requests,
            remote_cancel_completions: self.remote_cancel_completions,
            duplicate_suppressed: self.duplicate_suppressed,
            dispatches: self.dispatches,
            remote_acks: self.remote_acks,
            timeout_count: self.timeout_count,
            rollback_count: self.rollback_count,
            stale_rejections: self.stale_rejections,
            reclaimed: self.reclaimed,
            worker_retirements: self.worker_retirements,
            driver_executions: self.driver_executions,
            service_executions: self.service_executions,
            worker_entries: self.worker_entries,
            queued,
            dispatching,
            terminal,
            free,
            maximum_high_bypass: self.maximum_high_bypass,
            driver_sample_sum: self.driver_sample_sum,
            active_service_generation: self.active_service_generation,
        }
    }

    pub fn validate(&self) -> Result<(), Error> {
        if self.online_mask & 1 == 0 || self.online_mask & !ONLINE_MASK != 0 {
            return Err(Error::Invariant);
        }
        let mut dispatching = 0usize;
        for (index, slot) in self.slots.iter().enumerate() {
            if slot.state == WorkState::Free {
                continue;
            }
            if slot.generation == 0
                || slot.request.key == 0
                || slot.request.source_cpu != 0
                || slot.request.target_cpu == 0
                || slot.request.target_cpu as usize >= CPU_COUNT
                || !slot.request.consumer.valid()
                || slot.enqueue_sequence == 0
                || slot.enqueue_sequence > self.enqueue_sequence
            {
                return Err(Error::Invariant);
            }
            if slot.state == WorkState::Dispatching {
                dispatching += 1;
                let id = slot.id(index);
                let owned = self.pending.iter().flatten().any(|ticket| ticket.id == id)
                    || self.offline_pending.is_some_and(|ticket| ticket.id == id);
                if !owned {
                    return Err(Error::Invariant);
                }
            }
            if matches!(slot.state, WorkState::Completed | WorkState::Cancelled)
                && slot.completion_sequence == 0
            {
                return Err(Error::Invariant);
            }
            for later in &self.slots[index + 1..] {
                if later.state != WorkState::Free
                    && later.request.key == slot.request.key
                    && later.request.target_cpu == slot.request.target_cpu
                {
                    return Err(Error::Invariant);
                }
            }
        }
        let pending_count =
            self.pending.iter().flatten().count() + usize::from(self.offline_pending.is_some());
        if pending_count != dispatching
            || self.completed + self.cancelled + self.reclaimed > self.enqueued + self.reclaimed
            || self.remote_cancel_completions > self.remote_cancel_requests
            || self.remote_acks != self.worker_entries.iter().copied().sum::<u32>()
            || self.maximum_high_bypass > MAX_HIGH_BYPASS
            || self.worker_retirements > AP_COUNT as u32
            || self.active_service_generation == 0
        {
            return Err(Error::Invariant);
        }
        if self.shutdown_complete
            && (self.intake_open
                || self.online_mask != 1
                || pending_count != 0
                || self.slots.iter().any(|slot| slot.state != WorkState::Free))
        {
            return Err(Error::Invariant);
        }
        Ok(())
    }

    fn require_dispatch_permit(&self, permit: DispatchPermit) -> Result<(), Error> {
        if permit.eoi_epoch == 0
            || permit.eoi_epoch != self.eoi_epoch
            || permit.enqueue_watermark > self.enqueue_sequence
        {
            Err(Error::DispatchBeforeEoi)
        } else {
            Ok(())
        }
    }

    fn require_ap(&self, cpu: u8) -> Result<usize, Error> {
        if cpu == 0 || cpu as usize >= CPU_COUNT {
            return Err(Error::CpuRange);
        }
        if self.online_mask & (1 << cpu) == 0 {
            return Err(Error::CpuOffline);
        }
        Ok(cpu as usize)
    }

    fn resolve(&self, id: WorkId) -> Result<usize, Error> {
        let index = id.slot as usize;
        if index >= WORK_CAPACITY
            || self.slots[index].state == WorkState::Free
            || self.slots[index].generation != id.generation
        {
            Err(Error::StaleId)
        } else {
            Ok(index)
        }
    }

    fn install_ticket(
        &mut self,
        index: usize,
        source_cpu: u8,
        target_cpu: u8,
        worker_generation: u32,
        request_attempt: u64,
        request_sequence: u64,
    ) -> Result<DispatchTicket, Error> {
        if request_attempt == 0 || request_sequence == 0 {
            return Err(Error::InvalidRequest);
        }
        self.transaction_sequence = self
            .transaction_sequence
            .checked_add(1)
            .ok_or(Error::Counter)?;
        self.slots[index].state = WorkState::Dispatching;
        let consumer = self.slots[index].request.consumer;
        Ok(DispatchTicket {
            transaction: self.transaction_sequence,
            id: self.slots[index].id(index),
            source_cpu,
            target_cpu,
            worker_generation,
            request_attempt,
            request_sequence,
            payload: consumer.payload(),
            expected_result: consumer.expected_result(),
        })
    }

    fn select_next(&mut self, target_cpu: u8) -> Option<usize> {
        let target = target_cpu as usize;
        let high = self.oldest_queued(target_cpu, Priority::High);
        let normal = self.oldest_queued(target_cpu, Priority::Normal);
        match (high, normal) {
            (Some(_), Some(normal)) if self.high_bypass[target] >= MAX_HIGH_BYPASS => {
                self.high_bypass[target] = 0;
                Some(normal)
            }
            (Some(high), Some(_)) => {
                self.high_bypass[target] += 1;
                self.maximum_high_bypass = self.maximum_high_bypass.max(self.high_bypass[target]);
                Some(high)
            }
            (Some(high), None) => Some(high),
            (None, Some(normal)) => {
                self.high_bypass[target] = 0;
                Some(normal)
            }
            (None, None) => None,
        }
    }

    fn oldest_queued(&self, target_cpu: u8, priority: Priority) -> Option<usize> {
        self.slots
            .iter()
            .enumerate()
            .filter(|(_, slot)| {
                slot.state == WorkState::Queued
                    && slot.request.target_cpu == target_cpu
                    && slot.request.priority == priority
            })
            .min_by_key(|(_, slot)| slot.enqueue_sequence)
            .map(|(index, _)| index)
    }

    fn complete_terminal(
        &mut self,
        index: usize,
        state: WorkState,
        result: u64,
    ) -> Result<(), Error> {
        self.completion_sequence = self
            .completion_sequence
            .checked_add(1)
            .ok_or(Error::Counter)?;
        self.slots[index].state = state;
        self.slots[index].completion_sequence = self.completion_sequence;
        self.slots[index].result = result;
        match state {
            WorkState::Completed => self.completed = increment(self.completed)?,
            WorkState::Cancelled => self.cancelled = increment(self.cancelled)?,
            _ => return Err(Error::State),
        }
        Ok(())
    }
}

fn increment(value: u32) -> Result<u32, Error> {
    value.checked_add(1).ok_or(Error::Counter)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn top_half() -> TopHalfContext {
        TopHalfContext {
            interrupt_depth: 1,
            interrupts_disabled: true,
            queue_lock_held: false,
            worker_context: false,
        }
    }

    fn driver(key: u16, cpu: u8, sample: u32, priority: Priority) -> WorkRequest {
        WorkRequest {
            key,
            source_cpu: 0,
            target_cpu: cpu,
            priority,
            consumer: Consumer::DriverTimerBottomHalf { vector: 64, sample },
        }
    }

    fn service(key: u16, cpu: u8, retired: u32) -> WorkRequest {
        WorkRequest {
            key,
            source_cpu: 0,
            target_cpu: cpu,
            priority: Priority::Normal,
            consumer: Consumer::ServiceGenerationReclaim {
                retired_generation: retired,
                active_generation: retired + 1,
            },
        }
    }

    fn ack(ticket: DispatchTicket) -> RemoteAck {
        RemoteAck {
            target_cpu: ticket.target_cpu,
            attempt: ticket.request_attempt,
            sequence: ticket.request_sequence,
            operation: smp_ipi::Operation::CallFunction as u32,
            status: smp_ipi::ACK_ACCEPTED,
            error: smp_ipi::ERROR_NONE,
            result: ticket.expected_result,
        }
    }

    #[test]
    fn top_half_and_typed_consumer_contracts_fail_closed() {
        let mut controller = ApWorkerController::new();
        let mut invalid = top_half();
        invalid.worker_context = true;
        assert_eq!(
            controller.enqueue_from_top_half(invalid, driver(1, 1, 1, Priority::High)),
            Err(Error::TopHalfContext)
        );
        assert_eq!(
            controller.enqueue_from_top_half(top_half(), driver(1, 0, 1, Priority::High)),
            Err(Error::InvalidRequest)
        );
        assert_eq!(
            controller.enqueue_from_top_half(top_half(), driver(1, 1, 0, Priority::High)),
            Err(Error::InvalidRequest)
        );
    }

    #[test]
    fn dispatch_requires_eoi_and_exact_remote_ack() {
        let mut controller = ApWorkerController::new();
        let id = controller
            .enqueue_from_top_half(top_half(), driver(1, 1, 7, Priority::High))
            .unwrap();
        assert_eq!(
            controller.stage_dispatch(
                1,
                DispatchPermit {
                    eoi_epoch: 0,
                    enqueue_watermark: 1,
                },
                3,
                2,
            ),
            Err(Error::DispatchBeforeEoi)
        );
        let permit = controller.observe_eoi().unwrap();
        let ticket = controller.stage_dispatch(1, permit, 3, 2).unwrap();
        let mut forged = ack(ticket);
        forged.result ^= 1;
        assert_eq!(
            controller.acknowledge(ticket, forged),
            Err(Error::Acknowledgement)
        );
        assert_eq!(controller.acknowledge(ticket, ack(ticket)).unwrap().id, id);
    }

    #[test]
    fn queued_and_remote_cancellation_are_exact() {
        let mut controller = ApWorkerController::new();
        let queued = controller
            .enqueue_from_top_half(top_half(), driver(1, 1, 1, Priority::High))
            .unwrap();
        let remote = controller
            .enqueue_from_top_half(top_half(), driver(2, 2, 2, Priority::High))
            .unwrap();
        controller.cancel(queued).unwrap();
        let permit = controller.observe_eoi().unwrap();
        let ticket = controller.stage_dispatch(2, permit, 3, 2).unwrap();
        controller.cancel(remote).unwrap();
        let receipt = controller.acknowledge(ticket, ack(ticket)).unwrap();
        assert_eq!(receipt.state, WorkState::Cancelled);
        assert_eq!(controller.summary().driver_sample_sum, 0);
        assert_eq!(controller.summary().cancelled, 2);
    }

    #[test]
    fn offline_timeout_restores_source_queue_and_rejects_late_ack() {
        let mut controller = ApWorkerController::new();
        let id = controller
            .enqueue_from_top_half(top_half(), driver(1, 2, 7, Priority::High))
            .unwrap();
        let permit = controller.observe_eoi().unwrap();
        let ticket = controller
            .stage_offline_probe(id, OFFLINE_PROBE_CPU, permit, 3, 2)
            .unwrap();
        controller.timeout(ticket).unwrap();
        controller.reject_stale_ack(ticket, ack(ticket)).unwrap();
        assert_eq!(controller.request(id).unwrap().target_cpu, 2);
        let live = controller.stage_dispatch(2, permit, 3, 2).unwrap();
        controller.acknowledge(live, ack(live)).unwrap();
        assert_eq!(controller.summary().rollback_count, 1);
    }

    #[test]
    fn fairness_bounds_high_priority_bypass_per_ap() {
        let mut controller = ApWorkerController::new();
        let normal = controller
            .enqueue_from_top_half(top_half(), service(1, 1, 1))
            .unwrap();
        for key in 2..=4 {
            controller
                .enqueue_from_top_half(top_half(), driver(key, 1, key.into(), Priority::High))
                .unwrap();
        }
        let permit = controller.observe_eoi().unwrap();
        let first = controller.stage_dispatch(1, permit, 3, 2).unwrap();
        controller.acknowledge(first, ack(first)).unwrap();
        let second = controller.stage_dispatch(1, permit, 4, 3).unwrap();
        controller.acknowledge(second, ack(second)).unwrap();
        let third = controller.stage_dispatch(1, permit, 5, 4).unwrap();
        assert_eq!(third.id, normal);
        controller.acknowledge(third, ack(third)).unwrap();
        assert_eq!(controller.summary().maximum_high_bypass, MAX_HIGH_BYPASS);
    }

    #[test]
    fn flush_blocks_until_every_watermarked_item_is_terminal() {
        let mut controller = ApWorkerController::new();
        controller
            .enqueue_from_top_half(top_half(), driver(1, 1, 1, Priority::High))
            .unwrap();
        let token = controller.begin_flush();
        assert!(!controller.flush_complete(token));
        let permit = controller.observe_eoi().unwrap();
        let ticket = controller.stage_dispatch(1, permit, 3, 2).unwrap();
        controller.acknowledge(ticket, ack(ticket)).unwrap();
        assert!(controller.flush_complete(token));
    }

    #[test]
    fn service_reclamation_requires_exact_generation_order() {
        let mut controller = ApWorkerController::new();
        controller
            .enqueue_from_top_half(top_half(), service(1, 1, 2))
            .unwrap();
        let permit = controller.observe_eoi().unwrap();
        let ticket = controller.stage_dispatch(1, permit, 3, 2).unwrap();
        assert_eq!(
            controller.acknowledge(ticket, ack(ticket)),
            Err(Error::ReclaimOrder)
        );
    }

    #[test]
    fn flush_token_gates_slot_reclamation_and_stale_ids() {
        let mut controller = ApWorkerController::new();
        let id = controller
            .enqueue_from_top_half(top_half(), driver(1, 1, 1, Priority::High))
            .unwrap();
        let token = controller.begin_flush();
        let permit = controller.observe_eoi().unwrap();
        let ticket = controller.stage_dispatch(1, permit, 3, 2).unwrap();
        assert_eq!(controller.reclaim(id, token), Err(Error::FlushPending));
        controller.acknowledge(ticket, ack(ticket)).unwrap();
        controller.reclaim(id, token).unwrap();
        assert_eq!(controller.request(id), Err(Error::StaleId));
    }

    #[test]
    fn worker_offline_requires_empty_reclaimed_ownership() {
        let mut controller = ApWorkerController::new();
        let id = controller
            .enqueue_from_top_half(top_half(), driver(1, 3, 1, Priority::High))
            .unwrap();
        assert_eq!(controller.offline_worker(3), Err(Error::WorkerBusy));
        controller.cancel(id).unwrap();
        let token = controller.begin_flush();
        controller.reclaim(id, token).unwrap();
        controller.offline_worker(3).unwrap();
        assert_eq!(controller.summary().online_mask, 0x07);
    }

    #[test]
    fn complete_teardown_reclaims_every_slot_and_worker() {
        let mut controller = ApWorkerController::new();
        let mut ids = [WorkId::new(0, 1).unwrap(); AP_COUNT];
        for cpu in 1..=AP_COUNT as u8 {
            ids[cpu as usize - 1] = controller
                .enqueue_from_top_half(top_half(), service(cpu.into(), cpu, cpu.into()))
                .unwrap();
        }
        let token = controller.begin_flush();
        let permit = controller.observe_eoi().unwrap();
        for cpu in 1..=AP_COUNT as u8 {
            let ticket = controller
                .stage_dispatch(cpu, permit, 2 + u64::from(cpu), 1 + u64::from(cpu))
                .unwrap();
            controller.acknowledge(ticket, ack(ticket)).unwrap();
        }
        assert_eq!(
            controller.retire_all_terminal(token).unwrap(),
            AP_COUNT as u8
        );
        for cpu in (1..=AP_COUNT as u8).rev() {
            controller.offline_worker(cpu).unwrap();
        }
        controller.finish_shutdown().unwrap();
        let summary = controller.summary();
        assert_eq!(summary.free as usize, WORK_CAPACITY);
        assert_eq!(summary.active_service_generation, 4);
        assert!(summary.shutdown_complete);
        assert!(controller.validate().is_ok());
    }
}
