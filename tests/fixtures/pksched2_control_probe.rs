#![allow(dead_code)]

#[path = "../../native/kernel/src/scheduler.rs"]
mod scheduler;
#[path = "../../native/kernel/src/scheduler_preempt.rs"]
mod scheduler_preempt;

use scheduler::{CpuId, Scheduler, TaskId};
use scheduler_preempt::{
    validate_context_ownership, validate_interrupt_frame, BspPreemption, ContextOwnership,
    DeferredEvent, DeferredEventKind, Error, InterruptFrameContract, MAX_DEFERRED_EVENTS,
};

fn frame() -> InterruptFrameContract {
    InterruptFrameContract {
        depth: 1, vector: 0x40, error_code: 0, code_selector: 8, data_selector: 16,
        interrupted_rflags: (1 << 1) | (1 << 9), handler_interrupts_disabled: true,
        scheduler_lock_held: true, handler_rsp: 0x8100, frame_bytes: 176,
        ist_bottom: 0x8000, ist_top: 0xa000,
    }
}

fn controller() -> (BspPreemption, [TaskId; 2]) {
    let cpu = CpuId::new(0).unwrap();
    let mut scheduler = Scheduler::new(1).unwrap();
    let a = scheduler.create_task(0, 1, 10, 1).unwrap();
    let b = scheduler.create_task(1, 1, 10, 1).unwrap();
    scheduler.activate(a, cpu).unwrap();
    scheduler.activate(b, cpu).unwrap();
    assert_eq!(scheduler.dispatch(cpu), Ok(a));
    (BspPreemption::new(scheduler, cpu, 2).unwrap(), [a, b])
}

fn event(tick: u64) -> DeferredEvent {
    DeferredEvent { due_tick: tick, kind: DeferredEventKind::BlockCurrent }
}

fn interrupt_frame() -> usize {
    let good = frame();
    assert_eq!(validate_interrupt_frame(&good), Ok(()));
    let mutations: &[(fn(&mut InterruptFrameContract), Error)] = &[
        (|v| v.depth = 0, Error::InterruptDepth),
        (|v| v.depth = 2, Error::InterruptDepth),
        (|v| v.vector = 0x41, Error::InterruptVector),
        (|v| v.error_code = 1, Error::InterruptErrorCode),
        (|v| v.code_selector = 16, Error::InterruptSelector),
        (|v| v.data_selector = 8, Error::InterruptSelector),
        (|v| v.interrupted_rflags &= !(1 << 1), Error::InterruptedFlags),
        (|v| v.interrupted_rflags &= !(1 << 9), Error::InterruptedFlags),
        (|v| v.interrupted_rflags |= 1 << 14, Error::InterruptedFlags),
        (|v| v.interrupted_rflags |= 1 << 17, Error::InterruptedFlags),
        (|v| v.handler_interrupts_disabled = false, Error::HandlerInterruptState),
        (|v| v.scheduler_lock_held = false, Error::SchedulerLock),
        (|v| v.frame_bytes = 0, Error::IstRange),
        (|v| v.handler_rsp = v.ist_bottom - 1, Error::IstRange),
        (|v| v.handler_rsp = v.ist_top, Error::IstRange),
        (|v| v.handler_rsp = u64::MAX, Error::IstRange),
        (|v| v.ist_top = v.ist_bottom, Error::IstRange),
    ];
    let mut rejected = 0;
    for (mutate, expected) in mutations {
        let mut bad = good;
        mutate(&mut bad);
        assert_eq!(validate_interrupt_frame(&bad), Err(*expected));
        let (mut c, _) = controller();
        let before = c.summary();
        assert_eq!(c.handle_timer(&bad), Err(*expected));
        assert_eq!(c.summary(), before);
        rejected += 1;
    }
    let (mut c, _) = controller();
    assert!(c.handle_timer(&good).is_ok());
    assert_eq!(c.summary().timer_ticks, 1);
    rejected
}

fn context_ownership() -> usize {
    let good = ContextOwnership {
        outgoing_rsp: 0x1080, outgoing_bottom: 0x1000, outgoing_top: 0x2000,
        incoming_rsp: 0x3080, incoming_bottom: 0x3000, incoming_top: 0x4000,
        stack_alignment: 16,
    };
    assert_eq!(validate_context_ownership(&good), Ok(()));
    assert_eq!(validate_context_ownership(&ContextOwnership {
        outgoing_rsp: good.outgoing_top, incoming_rsp: good.incoming_top, ..good
    }), Ok(()));
    let mutations: &[(fn(&mut ContextOwnership), Error)] = &[
        (|v| v.stack_alignment = 8, Error::StackAlignment),
        (|v| v.stack_alignment = 24, Error::StackAlignment),
        (|v| v.outgoing_bottom = v.outgoing_top, Error::TaskStackRange),
        (|v| v.incoming_bottom = v.incoming_top, Error::TaskStackRange),
        (|v| v.outgoing_bottom += 1, Error::TaskStackRange),
        (|v| v.incoming_bottom += 1, Error::TaskStackRange),
        (|v| v.outgoing_top -= 1, Error::TaskStackRange),
        (|v| v.incoming_top -= 1, Error::TaskStackRange),
        (|v| v.outgoing_rsp = v.outgoing_bottom - 8, Error::TaskStackRange),
        (|v| v.incoming_rsp = v.incoming_bottom - 8, Error::TaskStackRange),
        (|v| v.outgoing_rsp = v.outgoing_top + 8, Error::TaskStackRange),
        (|v| v.incoming_rsp = v.incoming_top + 8, Error::TaskStackRange),
        (|v| v.outgoing_rsp += 1, Error::TaskStackRange),
        (|v| v.incoming_rsp += 1, Error::TaskStackRange),
        (|v| { v.incoming_bottom = 0x1800; v.incoming_top = 0x2800;
               v.incoming_rsp = 0x1880; }, Error::StackOverlap),
    ];
    let mut rejected = 0;
    for (mutate, expected) in mutations {
        let mut bad = good;
        mutate(&mut bad);
        assert_eq!(validate_context_ownership(&bad), Err(*expected));
        rejected += 1;
    }
    rejected
}

fn capacity() -> usize {
    let (mut c, _) = controller();
    for tick in 1..=MAX_DEFERRED_EVENTS as u64 {
        c.queue_event(event(tick)).unwrap();
    }
    let before = c.summary();
    assert_eq!(before.pending_events, 8);
    let mut rejected = 0;
    for tick in [9, u64::MAX] {
        assert_eq!(c.queue_event(event(tick)), Err(Error::EventCapacity));
        assert_eq!(c.summary(), before);
        c.validate().unwrap();
        rejected += 1;
    }
    rejected
}

fn deadline() -> usize {
    let (mut c, _) = controller();
    let before = c.summary();
    assert_eq!(c.queue_event(event(0)), Err(Error::EventDeadline));
    assert_eq!(c.summary(), before);
    let mut rejected = 1;
    c.handle_timer(&frame()).unwrap();
    let before = c.summary();
    for tick in [0, 1] {
        assert_eq!(c.queue_event(event(tick)), Err(Error::EventDeadline));
        assert_eq!(c.summary(), before);
        rejected += 1;
    }
    c.queue_event(event(2)).unwrap();
    c.queue_event(event(u64::MAX)).unwrap();
    c.validate().unwrap();
    rejected
}

fn duplicate() -> usize {
    let (mut c, ids) = controller();
    let mut rejected = 0;
    for kind in [DeferredEventKind::BlockCurrent, DeferredEventKind::Signal(ids[0]),
                 DeferredEventKind::Cancel(ids[0]), DeferredEventKind::Timeout(ids[0])] {
        let value = DeferredEvent { due_tick: 2, kind };
        c.queue_event(value).unwrap();
        let before = c.summary();
        assert_eq!(c.queue_event(value), Err(Error::EventDuplicate));
        assert_eq!(c.summary(), before);
        c.validate().unwrap();
        rejected += 1;
    }
    c.queue_event(event(3)).unwrap();
    assert_eq!(c.summary().pending_events, 5);
    rejected
}

fn quantum() -> usize {
    let (c, _) = controller();
    let cpu = CpuId::new(0).unwrap();
    for ticks in [1, 64] {
        assert!(BspPreemption::new(*c.scheduler(), cpu, ticks).is_ok());
    }
    let mut rejected = 0;
    for ticks in [0, 65, u32::MAX] {
        assert!(matches!(BspPreemption::new(*c.scheduler(), cpu, ticks), Err(Error::Quantum)));
        rejected += 1;
    }
    rejected
}

fn rollback() -> usize {
    let mut rejected = 0;
    for variant in 0..3 {
        let (mut c, ids) = controller();
        let kind = match variant {
            0 => DeferredEventKind::Signal(ids[0]),
            1 => DeferredEventKind::Cancel(ids[0]),
            _ => DeferredEventKind::Timeout(ids[0]),
        };
        c.queue_event(DeferredEvent { due_tick: 1, kind }).unwrap();
        let before_tasks = ids.map(|id| c.scheduler().task_snapshot(id).unwrap());
        let before = c.summary();
        // Retry the same failing event: rollback must restore the queue as well as counters.
        for attempt in 1..=2 {
            assert_eq!(c.handle_timer(&frame()), Err(Error::Core));
            let mut expected = before;
            expected.rollback_count += attempt;
            assert_eq!(c.summary(), expected);
            assert_eq!(ids.map(|id| c.scheduler().task_snapshot(id).unwrap()), before_tasks);
            c.validate().unwrap();
            rejected += 1;
        }
    }
    rejected
}

fn main() {
    let groups: [(&str, fn() -> usize); 7] = [
        ("INTERRUPT-FRAME-CONTRACT", interrupt_frame),
        ("CONTEXT-OWNERSHIP", context_ownership),
        ("EVENT-CAPACITY", capacity), ("EVENT-DEADLINE", deadline),
        ("EVENT-DUPLICATE", duplicate), ("QUANTUM-BOUNDARY", quantum),
        ("TRANSACTIONAL-ROLLBACK", rollback),
    ];
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    assert!(arguments.len() <= 1);
    let mut emitted = 0;
    for (name, run) in groups {
        if arguments.first().is_some_and(|selected| selected != name) { continue; }
        let rejected = run();
        assert!(rejected > 0);
        println!("PKSCHED2:CONTROL PASS id=NEG-N12-PKSCHED2-{} attempted={} rejected={}",
                 name, rejected, rejected);
        emitted += 1;
    }
    assert_eq!(emitted, if arguments.is_empty() { 7 } else { 1 });
}
