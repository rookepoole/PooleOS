pub const CONTRACT_ID: &str = "PKSCHED3";
pub const WORK_CAPACITY: usize = 8;
pub const WORKER_COUNT: u8 = 2;
pub const MAX_HIGH_BYPASS: u8 = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Capacity,
    Duplicate,
    IntakeClosed,
    TopHalfContext,
    Recursion,
    InvalidRequest,
    InvalidWorker,
    DispatchBeforeEoi,
    Empty,
    StaleId,
    State,
    WorkerOwnership,
    FlushPending,
    ShutdownPending,
    FaultInjected,
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
            Self::Recursion => "recursion",
            Self::InvalidRequest => "invalid_request",
            Self::InvalidWorker => "invalid_worker",
            Self::DispatchBeforeEoi => "dispatch_before_eoi",
            Self::Empty => "empty",
            Self::StaleId => "stale_id",
            Self::State => "state",
            Self::WorkerOwnership => "worker_ownership",
            Self::FlushPending => "flush_pending",
            Self::ShutdownPending => "shutdown_pending",
            Self::FaultInjected => "fault_injected",
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
pub enum Operation {
    Add(u32),
    Xor(u32),
    Fence(u32),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WorkRequest {
    pub key: u16,
    pub source: u8,
    pub priority: Priority,
    pub operation: Operation,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WorkId {
    pub slot: u8,
    pub generation: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WorkState {
    Free,
    Reserved,
    Queued,
    Running,
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
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FlushToken {
    pub enqueue_watermark: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Receipt {
    pub id: WorkId,
    pub worker: u8,
    pub state: WorkState,
    pub completion_sequence: u64,
    pub result: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FaultPoint {
    None,
    AfterReserve,
    AfterQueue,
    BeforeExecute,
    BeforeCommit,
    Cleanup,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub intake_open: bool,
    pub shutdown_complete: bool,
    pub enqueue_sequence: u64,
    pub completion_sequence: u64,
    pub eoi_epoch: u64,
    pub enqueued: u32,
    pub completed: u32,
    pub cancelled: u32,
    pub duplicate_suppressed: u32,
    pub running_cancel_requests: u32,
    pub dispatches: u32,
    pub retired: u32,
    pub rollback_count: u32,
    pub pending: u8,
    pub running: u8,
    pub terminal: u8,
    pub free: u8,
    pub max_high_bypass_observed: u8,
    pub sum_lane: u32,
    pub xor_lane: u32,
    pub fence_lane: u32,
}

const EMPTY_REQUEST: WorkRequest = WorkRequest {
    key: 0,
    source: 0,
    priority: Priority::Normal,
    operation: Operation::Fence(0),
};

#[derive(Clone, Copy)]
struct Slot {
    generation: u32,
    state: WorkState,
    request: WorkRequest,
    enqueue_sequence: u64,
    completion_sequence: u64,
    owner: u8,
    cancel_requested: bool,
    result: u32,
}

impl Slot {
    const EMPTY: Self = Self {
        generation: 0,
        state: WorkState::Free,
        request: EMPTY_REQUEST,
        enqueue_sequence: 0,
        completion_sequence: 0,
        owner: u8::MAX,
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
pub struct DeferredWorkController {
    slots: [Slot; WORK_CAPACITY],
    intake_open: bool,
    shutdown_complete: bool,
    active_worker: u8,
    enqueue_sequence: u64,
    completion_sequence: u64,
    eoi_epoch: u64,
    enqueued: u32,
    completed: u32,
    cancelled: u32,
    duplicate_suppressed: u32,
    running_cancel_requests: u32,
    dispatches: u32,
    retired: u32,
    rollback_count: u32,
    high_bypass: u8,
    max_high_bypass_observed: u8,
    sum_lane: u32,
    xor_lane: u32,
    fence_lane: u32,
}

impl Default for DeferredWorkController {
    fn default() -> Self {
        Self::new()
    }
}

impl DeferredWorkController {
    pub const fn new() -> Self {
        Self {
            slots: [Slot::EMPTY; WORK_CAPACITY],
            intake_open: true,
            shutdown_complete: false,
            active_worker: u8::MAX,
            enqueue_sequence: 0,
            completion_sequence: 0,
            eoi_epoch: 0,
            enqueued: 0,
            completed: 0,
            cancelled: 0,
            duplicate_suppressed: 0,
            running_cancel_requests: 0,
            dispatches: 0,
            retired: 0,
            rollback_count: 0,
            high_bypass: 0,
            max_high_bypass_observed: 0,
            sum_lane: 0,
            xor_lane: 0,
            fence_lane: 0,
        }
    }

    pub fn enqueue_from_top_half(
        &mut self,
        request: WorkRequest,
        context: &TopHalfContext,
        fault: FaultPoint,
    ) -> Result<WorkId, Error> {
        if context.worker_context || self.active_worker != u8::MAX {
            return Err(Error::Recursion);
        }
        if context.interrupt_depth != 1 || !context.interrupts_disabled || !context.queue_lock_held
        {
            return Err(Error::TopHalfContext);
        }
        if !self.intake_open {
            return Err(Error::IntakeClosed);
        }
        if request.key == 0 || operation_value(request.operation) == 0 {
            return Err(Error::InvalidRequest);
        }
        if self.slots.iter().any(|slot| {
            slot.state != WorkState::Free
                && slot.request.key == request.key
                && slot.request.source == request.source
        }) {
            self.duplicate_suppressed = increment(self.duplicate_suppressed)?;
            return Err(Error::Duplicate);
        }
        let index = self
            .slots
            .iter()
            .position(|slot| slot.state == WorkState::Free)
            .ok_or(Error::Capacity)?;
        let generation = self.slots[index].generation.wrapping_add(1);
        if generation == 0 {
            return Err(Error::Counter);
        }
        self.slots[index] = Slot {
            generation,
            state: WorkState::Reserved,
            request,
            enqueue_sequence: 0,
            completion_sequence: 0,
            owner: u8::MAX,
            cancel_requested: false,
            result: 0,
        };
        if fault == FaultPoint::AfterReserve {
            self.rollback_slot(index)?;
            return Err(Error::FaultInjected);
        }
        self.enqueue_sequence = self.enqueue_sequence.checked_add(1).ok_or(Error::Counter)?;
        self.slots[index].enqueue_sequence = self.enqueue_sequence;
        self.slots[index].state = WorkState::Queued;
        if fault == FaultPoint::AfterQueue {
            self.rollback_slot(index)?;
            return Err(Error::FaultInjected);
        }
        self.enqueued = increment(self.enqueued)?;
        self.validate()?;
        Ok(self.slots[index].id(index))
    }

    pub fn observe_eoi(&mut self) -> Result<DispatchPermit, Error> {
        if self.active_worker != u8::MAX {
            return Err(Error::WorkerOwnership);
        }
        self.eoi_epoch = self.eoi_epoch.checked_add(1).ok_or(Error::Counter)?;
        Ok(DispatchPermit {
            eoi_epoch: self.eoi_epoch,
        })
    }

    pub fn begin_flush(&self) -> FlushToken {
        FlushToken {
            enqueue_watermark: self.enqueue_sequence,
        }
    }

    pub fn flush_complete(&self, token: FlushToken) -> bool {
        self.slots.iter().all(|slot| {
            slot.enqueue_sequence == 0
                || slot.enqueue_sequence > token.enqueue_watermark
                || matches!(
                    slot.state,
                    WorkState::Completed | WorkState::Cancelled | WorkState::Free
                )
        })
    }

    pub fn claim_one(
        &mut self,
        worker: u8,
        permit: DispatchPermit,
        fault: FaultPoint,
    ) -> Result<WorkId, Error> {
        if worker >= WORKER_COUNT {
            return Err(Error::InvalidWorker);
        }
        if permit.eoi_epoch == 0 || permit.eoi_epoch != self.eoi_epoch {
            return Err(Error::DispatchBeforeEoi);
        }
        if self.active_worker != u8::MAX {
            return Err(Error::WorkerOwnership);
        }
        let index = self.select_next().ok_or(Error::Empty)?;
        if fault == FaultPoint::BeforeExecute {
            self.rollback_count = increment(self.rollback_count)?;
            return Err(Error::FaultInjected);
        }
        self.slots[index].state = WorkState::Running;
        self.slots[index].owner = worker;
        self.active_worker = worker;
        self.dispatches = increment(self.dispatches)?;
        self.validate()?;
        Ok(self.slots[index].id(index))
    }

    pub fn finish_claimed(
        &mut self,
        worker: u8,
        id: WorkId,
        fault: FaultPoint,
    ) -> Result<Receipt, Error> {
        let index = self.resolve(id)?;
        if self.active_worker != worker
            || self.slots[index].owner != worker
            || self.slots[index].state != WorkState::Running
        {
            return Err(Error::WorkerOwnership);
        }
        if fault == FaultPoint::BeforeCommit {
            self.slots[index].state = WorkState::Queued;
            self.slots[index].owner = u8::MAX;
            self.active_worker = u8::MAX;
            self.rollback_count = increment(self.rollback_count)?;
            self.validate()?;
            return Err(Error::FaultInjected);
        }
        let cancelled = self.slots[index].cancel_requested;
        let result = if cancelled {
            0
        } else {
            self.apply(self.slots[index].request.operation)?
        };
        self.completion_sequence = self
            .completion_sequence
            .checked_add(1)
            .ok_or(Error::Counter)?;
        let state = if cancelled {
            self.cancelled = increment(self.cancelled)?;
            WorkState::Cancelled
        } else {
            self.completed = increment(self.completed)?;
            WorkState::Completed
        };
        self.slots[index].state = state;
        self.slots[index].owner = u8::MAX;
        self.slots[index].completion_sequence = self.completion_sequence;
        self.slots[index].result = result;
        self.active_worker = u8::MAX;
        self.validate()?;
        Ok(Receipt {
            id,
            worker,
            state,
            completion_sequence: self.completion_sequence,
            result,
        })
    }

    pub fn dispatch_one(&mut self, worker: u8, permit: DispatchPermit) -> Result<Receipt, Error> {
        let id = self.claim_one(worker, permit, FaultPoint::None)?;
        self.finish_claimed(worker, id, FaultPoint::None)
    }

    pub fn cancel(&mut self, id: WorkId) -> Result<(), Error> {
        let index = self.resolve(id)?;
        match self.slots[index].state {
            WorkState::Queued => {
                self.complete_cancel(index)?;
                self.validate()
            }
            WorkState::Running => {
                if self.slots[index].cancel_requested {
                    return Err(Error::State);
                }
                self.slots[index].cancel_requested = true;
                self.running_cancel_requests = increment(self.running_cancel_requests)?;
                self.validate()
            }
            _ => Err(Error::State),
        }
    }

    pub fn request(&self, id: WorkId) -> Result<WorkRequest, Error> {
        Ok(self.slots[self.resolve(id)?].request)
    }

    pub fn retire(&mut self, id: WorkId, fault: FaultPoint) -> Result<(), Error> {
        let index = self.resolve(id)?;
        if !matches!(
            self.slots[index].state,
            WorkState::Completed | WorkState::Cancelled
        ) {
            return Err(Error::State);
        }
        if fault == FaultPoint::Cleanup {
            self.rollback_count = increment(self.rollback_count)?;
            return Err(Error::FaultInjected);
        }
        let generation = self.slots[index].generation;
        self.slots[index] = Slot {
            generation,
            ..Slot::EMPTY
        };
        self.retired = increment(self.retired)?;
        self.validate()
    }

    pub fn retire_all_terminal(&mut self) -> Result<u8, Error> {
        let mut retired = 0u8;
        for index in 0..WORK_CAPACITY {
            if matches!(
                self.slots[index].state,
                WorkState::Completed | WorkState::Cancelled
            ) {
                let id = self.slots[index].id(index);
                self.retire(id, FaultPoint::None)?;
                retired = retired.checked_add(1).ok_or(Error::Counter)?;
            }
        }
        Ok(retired)
    }

    pub fn begin_shutdown(&mut self) -> Result<u8, Error> {
        self.intake_open = false;
        let mut cancelled = 0u8;
        for index in 0..WORK_CAPACITY {
            match self.slots[index].state {
                WorkState::Queued => {
                    self.complete_cancel(index)?;
                    cancelled = cancelled.checked_add(1).ok_or(Error::Counter)?;
                }
                WorkState::Running if !self.slots[index].cancel_requested => {
                    self.slots[index].cancel_requested = true;
                    self.running_cancel_requests = increment(self.running_cancel_requests)?;
                }
                _ => {}
            }
        }
        self.validate()?;
        Ok(cancelled)
    }

    pub fn finish_shutdown(&mut self) -> Result<u8, Error> {
        if self.active_worker != u8::MAX
            || self.slots.iter().any(|slot| {
                matches!(
                    slot.state,
                    WorkState::Reserved | WorkState::Queued | WorkState::Running
                )
            })
        {
            return Err(Error::ShutdownPending);
        }
        let retired = self.retire_all_terminal()?;
        self.shutdown_complete = true;
        self.validate()?;
        Ok(retired)
    }

    pub fn summary(&self) -> Summary {
        let mut pending = 0u8;
        let mut running = 0u8;
        let mut terminal = 0u8;
        let mut free = 0u8;
        for slot in &self.slots {
            match slot.state {
                WorkState::Reserved | WorkState::Queued => pending += 1,
                WorkState::Running => running += 1,
                WorkState::Completed | WorkState::Cancelled => terminal += 1,
                WorkState::Free => free += 1,
            }
        }
        Summary {
            intake_open: self.intake_open,
            shutdown_complete: self.shutdown_complete,
            enqueue_sequence: self.enqueue_sequence,
            completion_sequence: self.completion_sequence,
            eoi_epoch: self.eoi_epoch,
            enqueued: self.enqueued,
            completed: self.completed,
            cancelled: self.cancelled,
            duplicate_suppressed: self.duplicate_suppressed,
            running_cancel_requests: self.running_cancel_requests,
            dispatches: self.dispatches,
            retired: self.retired,
            rollback_count: self.rollback_count,
            pending,
            running,
            terminal,
            free,
            max_high_bypass_observed: self.max_high_bypass_observed,
            sum_lane: self.sum_lane,
            xor_lane: self.xor_lane,
            fence_lane: self.fence_lane,
        }
    }

    pub fn validate(&self) -> Result<(), Error> {
        let mut running = 0u8;
        for (index, slot) in self.slots.iter().enumerate() {
            if slot.state == WorkState::Free {
                if slot.owner != u8::MAX
                    || slot.cancel_requested
                    || slot.enqueue_sequence != 0
                    || slot.completion_sequence != 0
                {
                    return Err(Error::Invariant);
                }
                continue;
            }
            if slot.generation == 0 || slot.request.key == 0 || slot.enqueue_sequence == 0 {
                return Err(Error::Invariant);
            }
            if slot.state == WorkState::Running {
                running = running.checked_add(1).ok_or(Error::Counter)?;
                if slot.owner >= WORKER_COUNT || self.active_worker != slot.owner {
                    return Err(Error::Invariant);
                }
            } else if slot.owner != u8::MAX {
                return Err(Error::Invariant);
            }
            if matches!(slot.state, WorkState::Completed | WorkState::Cancelled)
                != (slot.completion_sequence != 0)
            {
                return Err(Error::Invariant);
            }
            for other in self.slots.iter().skip(index + 1) {
                if other.state != WorkState::Free
                    && slot.request.key == other.request.key
                    && slot.request.source == other.request.source
                {
                    return Err(Error::Invariant);
                }
            }
        }
        if (running == 0) != (self.active_worker == u8::MAX) || running > 1 {
            return Err(Error::Invariant);
        }
        if self.shutdown_complete
            && (self.intake_open || self.slots.iter().any(|slot| slot.state != WorkState::Free))
        {
            return Err(Error::Invariant);
        }
        Ok(())
    }

    fn rollback_slot(&mut self, index: usize) -> Result<(), Error> {
        let generation = self.slots[index].generation;
        self.slots[index] = Slot {
            generation,
            ..Slot::EMPTY
        };
        self.rollback_count = increment(self.rollback_count)?;
        Ok(())
    }

    fn resolve(&self, id: WorkId) -> Result<usize, Error> {
        let index = usize::from(id.slot);
        if index >= WORK_CAPACITY
            || self.slots[index].state == WorkState::Free
            || self.slots[index].generation != id.generation
        {
            return Err(Error::StaleId);
        }
        Ok(index)
    }

    fn select_next(&mut self) -> Option<usize> {
        let high = self.oldest_queued(Priority::High);
        let normal = self.oldest_queued(Priority::Normal);
        match (high, normal) {
            (Some(_), Some(normal_index)) if self.high_bypass >= MAX_HIGH_BYPASS => {
                self.high_bypass = 0;
                Some(normal_index)
            }
            (Some(high_index), Some(_)) => {
                self.high_bypass += 1;
                self.max_high_bypass_observed = self.max_high_bypass_observed.max(self.high_bypass);
                Some(high_index)
            }
            (Some(high_index), None) => {
                self.high_bypass = 0;
                Some(high_index)
            }
            (None, Some(normal_index)) => {
                self.high_bypass = 0;
                Some(normal_index)
            }
            (None, None) => None,
        }
    }

    fn oldest_queued(&self, priority: Priority) -> Option<usize> {
        self.slots
            .iter()
            .enumerate()
            .filter(|(_, slot)| {
                slot.state == WorkState::Queued && slot.request.priority == priority
            })
            .min_by_key(|(_, slot)| slot.enqueue_sequence)
            .map(|(index, _)| index)
    }

    fn complete_cancel(&mut self, index: usize) -> Result<(), Error> {
        self.completion_sequence = self
            .completion_sequence
            .checked_add(1)
            .ok_or(Error::Counter)?;
        self.slots[index].state = WorkState::Cancelled;
        self.slots[index].owner = u8::MAX;
        self.slots[index].completion_sequence = self.completion_sequence;
        self.slots[index].result = 0;
        self.cancelled = increment(self.cancelled)?;
        Ok(())
    }

    fn apply(&mut self, operation: Operation) -> Result<u32, Error> {
        match operation {
            Operation::Add(value) => {
                self.sum_lane = self.sum_lane.checked_add(value).ok_or(Error::Counter)?;
                Ok(self.sum_lane)
            }
            Operation::Xor(value) => {
                self.xor_lane ^= value;
                Ok(self.xor_lane)
            }
            Operation::Fence(value) => {
                self.fence_lane = self.fence_lane.checked_add(value).ok_or(Error::Counter)?;
                Ok(self.fence_lane)
            }
        }
    }
}

const fn operation_value(operation: Operation) -> u32 {
    match operation {
        Operation::Add(value) | Operation::Xor(value) | Operation::Fence(value) => value,
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
            queue_lock_held: true,
            worker_context: false,
        }
    }

    fn request(key: u16, priority: Priority, operation: Operation) -> WorkRequest {
        WorkRequest {
            key,
            source: 7,
            priority,
            operation,
        }
    }

    #[test]
    fn enforces_top_half_and_duplicate_contracts() {
        let mut controller = DeferredWorkController::new();
        let item = request(1, Priority::High, Operation::Add(1));
        assert!(
            controller
                .enqueue_from_top_half(item, &top_half(), FaultPoint::None)
                .is_ok()
        );
        assert_eq!(
            controller.enqueue_from_top_half(item, &top_half(), FaultPoint::None),
            Err(Error::Duplicate)
        );
        assert_eq!(
            controller.enqueue_from_top_half(
                request(2, Priority::Normal, Operation::Add(1)),
                &TopHalfContext {
                    worker_context: true,
                    ..top_half()
                },
                FaultPoint::None,
            ),
            Err(Error::Recursion)
        );
    }

    #[test]
    fn dispatch_requires_eoi_and_bounds_priority_bypass() {
        let mut controller = DeferredWorkController::new();
        for (key, priority) in [
            (1, Priority::High),
            (2, Priority::Normal),
            (3, Priority::High),
            (4, Priority::High),
            (5, Priority::High),
        ] {
            controller
                .enqueue_from_top_half(
                    request(key, priority, Operation::Add(u32::from(key))),
                    &top_half(),
                    FaultPoint::None,
                )
                .unwrap();
        }
        assert_eq!(
            controller.claim_one(0, DispatchPermit { eoi_epoch: 0 }, FaultPoint::None),
            Err(Error::DispatchBeforeEoi)
        );
        let permit = controller.observe_eoi().unwrap();
        let mut slots = [0u8; 5];
        for (index, worker) in [0, 1, 0, 1, 0].into_iter().enumerate() {
            slots[index] = controller.dispatch_one(worker, permit).unwrap().id.slot;
        }
        assert_eq!(slots, [0, 2, 3, 1, 4]);
        assert_eq!(controller.summary().max_high_bypass_observed, 3);
    }

    #[test]
    fn queued_and_running_cancellation_are_exact() {
        let mut controller = DeferredWorkController::new();
        let queued = controller
            .enqueue_from_top_half(
                request(1, Priority::High, Operation::Add(4)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        let running = controller
            .enqueue_from_top_half(
                request(2, Priority::Normal, Operation::Fence(9)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        controller.cancel(queued).unwrap();
        let permit = controller.observe_eoi().unwrap();
        let claimed = controller.claim_one(1, permit, FaultPoint::None).unwrap();
        assert_eq!(claimed, running);
        controller.cancel(running).unwrap();
        let receipt = controller
            .finish_claimed(1, running, FaultPoint::None)
            .unwrap();
        assert_eq!(receipt.state, WorkState::Cancelled);
        let summary = controller.summary();
        assert_eq!(summary.cancelled, 2);
        assert_eq!(summary.running_cancel_requests, 1);
        assert_eq!(summary.fence_lane, 0);
    }

    #[test]
    fn flush_waits_for_exact_terminal_receipts() {
        let mut controller = DeferredWorkController::new();
        controller
            .enqueue_from_top_half(
                request(1, Priority::Normal, Operation::Xor(7)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        let token = controller.begin_flush();
        assert!(!controller.flush_complete(token));
        let permit = controller.observe_eoi().unwrap();
        controller.dispatch_one(0, permit).unwrap();
        assert!(controller.flush_complete(token));
    }

    #[test]
    fn generation_blocks_stale_reclamation() {
        let mut controller = DeferredWorkController::new();
        let first = controller
            .enqueue_from_top_half(
                request(1, Priority::Normal, Operation::Add(1)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        let permit = controller.observe_eoi().unwrap();
        controller.dispatch_one(0, permit).unwrap();
        controller.retire(first, FaultPoint::None).unwrap();
        let second = controller
            .enqueue_from_top_half(
                request(2, Priority::Normal, Operation::Add(1)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        assert_eq!(first.slot, second.slot);
        assert_ne!(first.generation, second.generation);
        assert_eq!(controller.cancel(first), Err(Error::StaleId));
    }

    #[test]
    fn every_fault_boundary_rolls_back_without_reuse() {
        let mut controller = DeferredWorkController::new();
        for (key, fault) in [(1, FaultPoint::AfterReserve), (2, FaultPoint::AfterQueue)] {
            assert_eq!(
                controller.enqueue_from_top_half(
                    request(key, Priority::High, Operation::Add(1)),
                    &top_half(),
                    fault,
                ),
                Err(Error::FaultInjected)
            );
        }
        let id = controller
            .enqueue_from_top_half(
                request(3, Priority::High, Operation::Add(1)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        let permit = controller.observe_eoi().unwrap();
        assert_eq!(
            controller.claim_one(0, permit, FaultPoint::BeforeExecute),
            Err(Error::FaultInjected)
        );
        let claimed = controller.claim_one(0, permit, FaultPoint::None).unwrap();
        assert_eq!(claimed, id);
        assert_eq!(
            controller.finish_claimed(0, id, FaultPoint::BeforeCommit),
            Err(Error::FaultInjected)
        );
        controller.dispatch_one(1, permit).unwrap();
        assert_eq!(
            controller.retire(id, FaultPoint::Cleanup),
            Err(Error::FaultInjected)
        );
        controller.retire(id, FaultPoint::None).unwrap();
        assert_eq!(controller.summary().rollback_count, 5);
    }

    #[test]
    fn shutdown_closes_intake_cancels_and_retires() {
        let mut controller = DeferredWorkController::new();
        controller
            .enqueue_from_top_half(
                request(1, Priority::Normal, Operation::Add(1)),
                &top_half(),
                FaultPoint::None,
            )
            .unwrap();
        assert_eq!(controller.begin_shutdown(), Ok(1));
        assert_eq!(controller.finish_shutdown(), Ok(1));
        assert_eq!(
            controller.enqueue_from_top_half(
                request(2, Priority::Normal, Operation::Add(1)),
                &top_half(),
                FaultPoint::None,
            ),
            Err(Error::IntakeClosed)
        );
        let summary = controller.summary();
        assert!(summary.shutdown_complete);
        assert_eq!(summary.free, WORK_CAPACITY as u8);
    }
}
