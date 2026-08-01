use crate::scheduler::{CpuId, Scheduler, SchedulerSummary, TaskId, TaskSnapshot};

pub const CONTRACT_ID: &str = "PKSCHED2";
pub const TIMER_VECTOR: u8 = 0x40;
pub const KERNEL_CODE_SELECTOR: u64 = 0x08;
pub const KERNEL_DATA_SELECTOR: u64 = 0x10;
pub const MAX_DEFERRED_EVENTS: usize = 8;
pub const MIN_QUANTUM_TICKS: u32 = 1;
pub const MAX_QUANTUM_TICKS: u32 = 64;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Core,
    Quantum,
    EventCapacity,
    EventDeadline,
    EventDuplicate,
    InterruptDepth,
    InterruptVector,
    InterruptErrorCode,
    InterruptSelector,
    InterruptedFlags,
    HandlerInterruptState,
    SchedulerLock,
    IstRange,
    TaskStackRange,
    StackOverlap,
    StackAlignment,
    Counter,
    Invariant,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DeferredEventKind {
    Signal(TaskId),
    Cancel(TaskId),
    Timeout(TaskId),
    BlockCurrent,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DeferredEvent {
    pub due_tick: u64,
    pub kind: DeferredEventKind,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RescheduleCause {
    None,
    QuantumExpired,
    HigherPriorityWake,
    CurrentBlocked,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InterruptFrameContract {
    pub depth: u32,
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
pub struct ContextOwnership {
    pub outgoing_rsp: u64,
    pub outgoing_bottom: u64,
    pub outgoing_top: u64,
    pub incoming_rsp: u64,
    pub incoming_bottom: u64,
    pub incoming_top: u64,
    pub stack_alignment: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InterruptOutcome {
    pub tick: u64,
    pub previous: TaskId,
    pub next: TaskId,
    pub cause: RescheduleCause,
    pub events_processed: u8,
    pub context_switch_required: bool,
    pub quantum_remaining: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PreemptionSummary {
    pub timer_ticks: u64,
    pub events_processed: u32,
    pub signal_events: u32,
    pub cancel_events: u32,
    pub timeout_events: u32,
    pub block_events: u32,
    pub quantum_reschedules: u32,
    pub wake_reschedules: u32,
    pub block_reschedules: u32,
    pub context_switches: u32,
    pub rollback_count: u32,
    pub pending_events: u8,
    pub quantum_remaining: u32,
    pub scheduler: SchedulerSummary,
}

#[derive(Clone, Copy)]
pub struct BspPreemption {
    scheduler: Scheduler,
    cpu: CpuId,
    quantum_ticks: u32,
    quantum_remaining: u32,
    events: [Option<DeferredEvent>; MAX_DEFERRED_EVENTS],
    event_count: usize,
    timer_ticks: u64,
    events_processed: u32,
    signal_events: u32,
    cancel_events: u32,
    timeout_events: u32,
    block_events: u32,
    quantum_reschedules: u32,
    wake_reschedules: u32,
    block_reschedules: u32,
    context_switches: u32,
    rollback_count: u32,
}

impl BspPreemption {
    pub fn new(scheduler: Scheduler, cpu: CpuId, quantum_ticks: u32) -> Result<Self, Error> {
        if !(MIN_QUANTUM_TICKS..=MAX_QUANTUM_TICKS).contains(&quantum_ticks) {
            return Err(Error::Quantum);
        }
        scheduler.validate().map_err(|_| Error::Core)?;
        scheduler
            .current(cpu)
            .map_err(|_| Error::Core)?
            .ok_or(Error::Core)?;
        Ok(Self {
            scheduler,
            cpu,
            quantum_ticks,
            quantum_remaining: quantum_ticks,
            events: [None; MAX_DEFERRED_EVENTS],
            event_count: 0,
            timer_ticks: 0,
            events_processed: 0,
            signal_events: 0,
            cancel_events: 0,
            timeout_events: 0,
            block_events: 0,
            quantum_reschedules: 0,
            wake_reschedules: 0,
            block_reschedules: 0,
            context_switches: 0,
            rollback_count: 0,
        })
    }

    pub fn scheduler(&self) -> &Scheduler {
        &self.scheduler
    }

    pub fn scheduler_mut(&mut self) -> &mut Scheduler {
        &mut self.scheduler
    }

    pub fn queue_event(&mut self, event: DeferredEvent) -> Result<(), Error> {
        if event.due_tick <= self.timer_ticks {
            return Err(Error::EventDeadline);
        }
        if self.event_count == MAX_DEFERRED_EVENTS {
            return Err(Error::EventCapacity);
        }
        if self.events[..self.event_count].contains(&Some(event)) {
            return Err(Error::EventDuplicate);
        }
        let mut insert = self.event_count;
        while insert > 0 {
            let prior = self.events[insert - 1].ok_or(Error::Invariant)?;
            if prior.due_tick <= event.due_tick {
                break;
            }
            self.events[insert] = Some(prior);
            insert -= 1;
        }
        self.events[insert] = Some(event);
        self.event_count += 1;
        self.validate()
    }

    pub fn handle_timer(
        &mut self,
        frame: &InterruptFrameContract,
    ) -> Result<InterruptOutcome, Error> {
        validate_interrupt_frame(frame)?;
        let before = *self;
        match self.handle_timer_inner() {
            Ok(outcome) => Ok(outcome),
            Err(error) => {
                let rollback_count = before.rollback_count.checked_add(1).ok_or(Error::Counter)?;
                *self = before;
                self.rollback_count = rollback_count;
                Err(error)
            }
        }
    }

    pub fn summary(&self) -> PreemptionSummary {
        PreemptionSummary {
            timer_ticks: self.timer_ticks,
            events_processed: self.events_processed,
            signal_events: self.signal_events,
            cancel_events: self.cancel_events,
            timeout_events: self.timeout_events,
            block_events: self.block_events,
            quantum_reschedules: self.quantum_reschedules,
            wake_reschedules: self.wake_reschedules,
            block_reschedules: self.block_reschedules,
            context_switches: self.context_switches,
            rollback_count: self.rollback_count,
            pending_events: self.event_count as u8,
            quantum_remaining: self.quantum_remaining,
            scheduler: self.scheduler.summary(),
        }
    }

    pub fn validate(&self) -> Result<(), Error> {
        if !(MIN_QUANTUM_TICKS..=MAX_QUANTUM_TICKS).contains(&self.quantum_ticks)
            || self.quantum_remaining == 0
            || self.quantum_remaining > self.quantum_ticks
            || self.event_count > MAX_DEFERRED_EVENTS
            || self.events[self.event_count..].iter().any(Option::is_some)
        {
            return Err(Error::Invariant);
        }
        let mut prior_due = self.timer_ticks;
        for event in self.events[..self.event_count].iter().copied() {
            let event = event.ok_or(Error::Invariant)?;
            if event.due_tick <= self.timer_ticks || event.due_tick < prior_due {
                return Err(Error::Invariant);
            }
            prior_due = event.due_tick;
        }
        self.scheduler.validate().map_err(|_| Error::Core)
    }

    fn handle_timer_inner(&mut self) -> Result<InterruptOutcome, Error> {
        let previous = self
            .scheduler
            .current(self.cpu)
            .map_err(|_| Error::Core)?
            .ok_or(Error::Core)?;
        let previous_priority = self
            .scheduler
            .task_snapshot(previous)
            .map_err(|_| Error::Core)?
            .effective_priority;
        self.timer_ticks = self.timer_ticks.checked_add(1).ok_or(Error::Counter)?;
        self.scheduler
            .account_tick(self.cpu, 1)
            .map_err(|_| Error::Core)?;
        self.quantum_remaining = self
            .quantum_remaining
            .checked_sub(1)
            .ok_or(Error::Quantum)?;

        let mut cause = RescheduleCause::None;
        let mut processed = 0u8;
        while self.event_count != 0 {
            let event = self.events[0].ok_or(Error::Invariant)?;
            if event.due_tick > self.timer_ticks {
                break;
            }
            self.remove_first_event()?;
            processed = processed.checked_add(1).ok_or(Error::Counter)?;
            self.events_processed = self.events_processed.checked_add(1).ok_or(Error::Counter)?;
            match event.kind {
                DeferredEventKind::Signal(id) => {
                    self.scheduler
                        .signal_wait(id, self.cpu)
                        .map_err(|_| Error::Core)?;
                    self.signal_events = self.signal_events.checked_add(1).ok_or(Error::Counter)?;
                    if self
                        .scheduler
                        .task_snapshot(id)
                        .map_err(|_| Error::Core)?
                        .effective_priority
                        > previous_priority
                    {
                        cause = RescheduleCause::HigherPriorityWake;
                    }
                }
                DeferredEventKind::Cancel(id) => {
                    self.scheduler
                        .cancel_wait(id, self.cpu)
                        .map_err(|_| Error::Core)?;
                    self.cancel_events = self.cancel_events.checked_add(1).ok_or(Error::Counter)?;
                    if self
                        .scheduler
                        .task_snapshot(id)
                        .map_err(|_| Error::Core)?
                        .effective_priority
                        > previous_priority
                    {
                        cause = RescheduleCause::HigherPriorityWake;
                    }
                }
                DeferredEventKind::Timeout(id) => {
                    self.scheduler
                        .timeout_wait(id, self.cpu)
                        .map_err(|_| Error::Core)?;
                    self.timeout_events =
                        self.timeout_events.checked_add(1).ok_or(Error::Counter)?;
                    if self
                        .scheduler
                        .task_snapshot(id)
                        .map_err(|_| Error::Core)?
                        .effective_priority
                        > previous_priority
                    {
                        cause = RescheduleCause::HigherPriorityWake;
                    }
                }
                DeferredEventKind::BlockCurrent => {
                    self.scheduler
                        .block_current(self.cpu)
                        .map_err(|_| Error::Core)?;
                    self.block_events = self.block_events.checked_add(1).ok_or(Error::Counter)?;
                    cause = RescheduleCause::CurrentBlocked;
                }
            }
        }

        if cause == RescheduleCause::None && self.quantum_remaining == 0 {
            cause = RescheduleCause::QuantumExpired;
        }
        if cause != RescheduleCause::None {
            if self
                .scheduler
                .current(self.cpu)
                .map_err(|_| Error::Core)?
                .is_some()
            {
                self.scheduler
                    .yield_current(self.cpu)
                    .map_err(|_| Error::Core)?;
            }
            let next = self.scheduler.dispatch(self.cpu).map_err(|_| Error::Core)?;
            self.quantum_remaining = self.quantum_ticks;
            match cause {
                RescheduleCause::None => {}
                RescheduleCause::QuantumExpired => {
                    self.quantum_reschedules = self
                        .quantum_reschedules
                        .checked_add(1)
                        .ok_or(Error::Counter)?;
                }
                RescheduleCause::HigherPriorityWake => {
                    self.wake_reschedules =
                        self.wake_reschedules.checked_add(1).ok_or(Error::Counter)?;
                }
                RescheduleCause::CurrentBlocked => {
                    self.block_reschedules = self
                        .block_reschedules
                        .checked_add(1)
                        .ok_or(Error::Counter)?;
                }
            }
            let switched = previous != next;
            if switched {
                self.context_switches =
                    self.context_switches.checked_add(1).ok_or(Error::Counter)?;
            }
            self.validate()?;
            return Ok(InterruptOutcome {
                tick: self.timer_ticks,
                previous,
                next,
                cause,
                events_processed: processed,
                context_switch_required: switched,
                quantum_remaining: self.quantum_remaining,
            });
        }

        self.validate()?;
        Ok(InterruptOutcome {
            tick: self.timer_ticks,
            previous,
            next: previous,
            cause,
            events_processed: processed,
            context_switch_required: false,
            quantum_remaining: self.quantum_remaining,
        })
    }

    fn remove_first_event(&mut self) -> Result<(), Error> {
        if self.event_count == 0 {
            return Err(Error::Invariant);
        }
        for index in 1..self.event_count {
            self.events[index - 1] = self.events[index];
        }
        self.event_count -= 1;
        self.events[self.event_count] = None;
        Ok(())
    }
}

pub fn validate_interrupt_frame(frame: &InterruptFrameContract) -> Result<(), Error> {
    if frame.depth != 1 {
        return Err(Error::InterruptDepth);
    }
    if frame.vector != u64::from(TIMER_VECTOR) {
        return Err(Error::InterruptVector);
    }
    if frame.error_code != 0 {
        return Err(Error::InterruptErrorCode);
    }
    if frame.code_selector != KERNEL_CODE_SELECTOR || frame.data_selector != KERNEL_DATA_SELECTOR {
        return Err(Error::InterruptSelector);
    }
    if frame.interrupted_rflags & (1 << 1) == 0
        || frame.interrupted_rflags & (1 << 9) == 0
        || frame.interrupted_rflags & ((1 << 14) | (1 << 17)) != 0
    {
        return Err(Error::InterruptedFlags);
    }
    if !frame.handler_interrupts_disabled {
        return Err(Error::HandlerInterruptState);
    }
    if !frame.scheduler_lock_held {
        return Err(Error::SchedulerLock);
    }
    if frame.frame_bytes == 0
        || frame.handler_rsp < frame.ist_bottom
        || frame
            .handler_rsp
            .checked_add(frame.frame_bytes)
            .is_none_or(|end| end > frame.ist_top)
    {
        return Err(Error::IstRange);
    }
    Ok(())
}

pub fn validate_context_ownership(value: &ContextOwnership) -> Result<(), Error> {
    if value.stack_alignment < 16 || !value.stack_alignment.is_power_of_two() {
        return Err(Error::StackAlignment);
    }
    for (rsp, bottom, top) in [
        (
            value.outgoing_rsp,
            value.outgoing_bottom,
            value.outgoing_top,
        ),
        (
            value.incoming_rsp,
            value.incoming_bottom,
            value.incoming_top,
        ),
    ] {
        if bottom >= top
            || !bottom.is_multiple_of(value.stack_alignment)
            || !top.is_multiple_of(value.stack_alignment)
            || rsp < bottom
            || rsp > top
            || !rsp.is_multiple_of(8)
        {
            return Err(Error::TaskStackRange);
        }
    }
    if value.outgoing_bottom < value.incoming_top && value.incoming_bottom < value.outgoing_top {
        return Err(Error::StackOverlap);
    }
    Ok(())
}

pub fn task_snapshot(controller: &BspPreemption, id: TaskId) -> Result<TaskSnapshot, Error> {
    controller
        .scheduler
        .task_snapshot(id)
        .map_err(|_| Error::Core)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scheduler::{TaskState, WakeReason};

    fn cpu() -> CpuId {
        CpuId::new(0).unwrap()
    }

    fn frame() -> InterruptFrameContract {
        InterruptFrameContract {
            depth: 1,
            vector: u64::from(TIMER_VECTOR),
            error_code: 0,
            code_selector: KERNEL_CODE_SELECTOR,
            data_selector: KERNEL_DATA_SELECTOR,
            interrupted_rflags: (1 << 1) | (1 << 9),
            handler_interrupts_disabled: true,
            scheduler_lock_held: true,
            handler_rsp: 0x8100,
            frame_bytes: 176,
            ist_bottom: 0x8000,
            ist_top: 0xa000,
        }
    }

    fn live_controller() -> (BspPreemption, [TaskId; 4]) {
        let mut scheduler = Scheduler::new(1).unwrap();
        let a = scheduler.create_task(0, 1, 10, 1).unwrap();
        let b = scheduler.create_task(1, 1, 10, 1).unwrap();
        let signal = scheduler.create_task(2, 1, 30, 1).unwrap();
        let cancel = scheduler.create_task(3, 1, 25, 1).unwrap();
        scheduler.activate(signal, cpu()).unwrap();
        scheduler.dispatch(cpu()).unwrap();
        scheduler.block_current(cpu()).unwrap();
        scheduler.activate(cancel, cpu()).unwrap();
        scheduler.dispatch(cpu()).unwrap();
        scheduler.block_current(cpu()).unwrap();
        scheduler.activate(a, cpu()).unwrap();
        scheduler.activate(b, cpu()).unwrap();
        assert_eq!(scheduler.dispatch(cpu()), Ok(a));
        let mut controller = BspPreemption::new(scheduler, cpu(), 2).unwrap();
        controller
            .queue_event(DeferredEvent {
                due_tick: 3,
                kind: DeferredEventKind::Signal(signal),
            })
            .unwrap();
        controller
            .queue_event(DeferredEvent {
                due_tick: 4,
                kind: DeferredEventKind::BlockCurrent,
            })
            .unwrap();
        controller
            .queue_event(DeferredEvent {
                due_tick: 5,
                kind: DeferredEventKind::Cancel(cancel),
            })
            .unwrap();
        (controller, [a, b, signal, cancel])
    }

    #[test]
    fn exact_live_trace_has_quantum_signal_block_and_cancel_switches() {
        let (mut controller, ids) = live_controller();
        let expected = [
            (ids[0], RescheduleCause::None),
            (ids[1], RescheduleCause::QuantumExpired),
            (ids[2], RescheduleCause::HigherPriorityWake),
            (ids[0], RescheduleCause::CurrentBlocked),
            (ids[3], RescheduleCause::HigherPriorityWake),
            (ids[3], RescheduleCause::None),
        ];
        for (next, cause) in expected {
            let outcome = controller.handle_timer(&frame()).unwrap();
            assert_eq!(outcome.next, next);
            assert_eq!(outcome.cause, cause);
        }
        let summary = controller.summary();
        assert_eq!(summary.timer_ticks, 6);
        assert_eq!(summary.context_switches, 4);
        assert_eq!(summary.events_processed, 3);
        assert_eq!(summary.signal_events, 1);
        assert_eq!(summary.cancel_events, 1);
        assert_eq!(summary.block_events, 1);
        assert_eq!(
            task_snapshot(&controller, ids[3]).unwrap().wake_reason,
            WakeReason::Cancelled
        );
        assert_eq!(
            task_snapshot(&controller, ids[2]).unwrap().state,
            TaskState::Blocked
        );
    }

    #[test]
    fn equal_deadline_events_keep_insertion_order_and_timeout_exactly_once() {
        let (mut controller, ids) = live_controller();
        assert_eq!(
            controller.queue_event(DeferredEvent {
                due_tick: 3,
                kind: DeferredEventKind::Timeout(ids[2]),
            }),
            Ok(())
        );
        assert_eq!(
            controller.queue_event(DeferredEvent {
                due_tick: 3,
                kind: DeferredEventKind::Timeout(ids[2]),
            }),
            Err(Error::EventDuplicate)
        );
    }

    #[test]
    fn invalid_due_event_rolls_back_every_scheduler_mutation() {
        let (mut controller, ids) = live_controller();
        controller.events[0] = Some(DeferredEvent {
            due_tick: 1,
            kind: DeferredEventKind::Cancel(ids[0]),
        });
        let before = controller.scheduler.summary();
        assert_eq!(controller.handle_timer(&frame()), Err(Error::Core));
        assert_eq!(controller.scheduler.summary(), before);
        assert_eq!(controller.summary().timer_ticks, 0);
        assert_eq!(controller.summary().rollback_count, 1);
    }

    #[test]
    fn queue_rejects_past_duplicate_and_capacity_overflow() {
        let (mut controller, ids) = live_controller();
        assert_eq!(
            controller.queue_event(DeferredEvent {
                due_tick: 0,
                kind: DeferredEventKind::Timeout(ids[0]),
            }),
            Err(Error::EventDeadline)
        );
        for tick in 6..=10 {
            controller
                .queue_event(DeferredEvent {
                    due_tick: tick,
                    kind: DeferredEventKind::Timeout(ids[0]),
                })
                .unwrap();
        }
        assert_eq!(controller.event_count, MAX_DEFERRED_EVENTS);
        assert_eq!(
            controller.queue_event(DeferredEvent {
                due_tick: 11,
                kind: DeferredEventKind::BlockCurrent,
            }),
            Err(Error::EventCapacity)
        );
    }

    #[test]
    fn interrupt_frame_contract_rejects_each_authority_boundary() {
        let good = frame();
        assert_eq!(validate_interrupt_frame(&good), Ok(()));
        let mutations: [(fn(&mut InterruptFrameContract), Error); 8] = [
            (|v| v.depth = 2, Error::InterruptDepth),
            (|v| v.vector = 0x41, Error::InterruptVector),
            (|v| v.error_code = 1, Error::InterruptErrorCode),
            (|v| v.code_selector = 0x10, Error::InterruptSelector),
            (
                |v| v.interrupted_rflags &= !(1 << 9),
                Error::InterruptedFlags,
            ),
            (
                |v| v.handler_interrupts_disabled = false,
                Error::HandlerInterruptState,
            ),
            (|v| v.scheduler_lock_held = false, Error::SchedulerLock),
            (|v| v.handler_rsp = v.ist_top, Error::IstRange),
        ];
        for (mutate, error) in mutations {
            let mut value = good;
            mutate(&mut value);
            assert_eq!(validate_interrupt_frame(&value), Err(error));
        }
    }

    #[test]
    fn context_ownership_requires_private_aligned_stack_ranges() {
        let good = ContextOwnership {
            outgoing_rsp: 0x1080,
            outgoing_bottom: 0x1000,
            outgoing_top: 0x2000,
            incoming_rsp: 0x3080,
            incoming_bottom: 0x3000,
            incoming_top: 0x4000,
            stack_alignment: 16,
        };
        assert_eq!(validate_context_ownership(&good), Ok(()));
        assert_eq!(
            validate_context_ownership(&ContextOwnership {
                outgoing_rsp: good.outgoing_top,
                ..good
            }),
            Ok(())
        );
        assert_eq!(
            validate_context_ownership(&ContextOwnership {
                incoming_rsp: 0x1880,
                incoming_bottom: 0x1800,
                incoming_top: 0x2800,
                ..good
            }),
            Err(Error::StackOverlap)
        );
        assert_eq!(
            validate_context_ownership(&ContextOwnership {
                incoming_rsp: 0x4010,
                ..good
            }),
            Err(Error::TaskStackRange)
        );
    }

    #[test]
    fn quantum_bounds_fail_closed() {
        let mut scheduler = Scheduler::new(1).unwrap();
        let id = scheduler.create_task(0, 1, 10, 1).unwrap();
        scheduler.activate(id, cpu()).unwrap();
        scheduler.dispatch(cpu()).unwrap();
        assert!(matches!(
            BspPreemption::new(scheduler, cpu(), 0),
            Err(Error::Quantum)
        ));
        assert!(matches!(
            BspPreemption::new(scheduler, cpu(), MAX_QUANTUM_TICKS + 1),
            Err(Error::Quantum)
        ));
    }
}
