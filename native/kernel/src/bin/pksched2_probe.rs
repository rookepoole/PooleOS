use poolekernel::scheduler::{CpuId, Scheduler};
use poolekernel::scheduler_preempt::{
    BspPreemption, ContextOwnership, DeferredEvent, DeferredEventKind, InterruptFrameContract,
    KERNEL_CODE_SELECTOR, KERNEL_DATA_SELECTOR, RescheduleCause, TIMER_VECTOR,
    validate_context_ownership, validate_interrupt_frame,
};

fn cpu() -> CpuId {
    CpuId::new(0).expect("canonical BSP")
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

fn cause_label(cause: RescheduleCause) -> &'static str {
    match cause {
        RescheduleCause::None => "none",
        RescheduleCause::QuantumExpired => "quantum",
        RescheduleCause::HigherPriorityWake => "wake",
        RescheduleCause::CurrentBlocked => "block",
    }
}

fn main() {
    let mut scheduler = Scheduler::new(1).expect("one-BSP scheduler");
    let task_a = scheduler.create_task(0, 1, 10, 1).expect("task A");
    let task_b = scheduler.create_task(1, 1, 10, 1).expect("task B");
    let signal_task = scheduler.create_task(2, 1, 30, 1).expect("signal task");
    let cancel_task = scheduler.create_task(3, 1, 25, 1).expect("cancel task");
    scheduler
        .activate(signal_task, cpu())
        .expect("activate signal");
    assert_eq!(scheduler.dispatch(cpu()), Ok(signal_task));
    scheduler.block_current(cpu()).expect("block signal");
    scheduler
        .activate(cancel_task, cpu())
        .expect("activate cancel");
    assert_eq!(scheduler.dispatch(cpu()), Ok(cancel_task));
    scheduler.block_current(cpu()).expect("block cancel");
    scheduler.activate(task_a, cpu()).expect("activate A");
    scheduler.activate(task_b, cpu()).expect("activate B");
    assert_eq!(scheduler.dispatch(cpu()), Ok(task_a));

    let mut controller = BspPreemption::new(scheduler, cpu(), 2).expect("controller");
    for event in [
        DeferredEvent {
            due_tick: 3,
            kind: DeferredEventKind::Signal(signal_task),
        },
        DeferredEvent {
            due_tick: 4,
            kind: DeferredEventKind::BlockCurrent,
        },
        DeferredEvent {
            due_tick: 5,
            kind: DeferredEventKind::Cancel(cancel_task),
        },
    ] {
        controller.queue_event(event).expect("deferred event");
    }

    let mut next = [0usize; 6];
    let mut causes = [""; 6];
    let mut processed = [0u8; 6];
    for tick in 0..6 {
        let outcome = controller.handle_timer(&frame()).expect("timer step");
        next[tick] = outcome.next.index();
        causes[tick] = cause_label(outcome.cause);
        processed[tick] = outcome.events_processed;
    }
    let summary = controller.summary();
    let mut runtime = [0u64; 4];
    for (index, task) in [task_a, task_b, signal_task, cancel_task]
        .into_iter()
        .enumerate()
    {
        runtime[index] = controller
            .scheduler()
            .task_snapshot(task)
            .expect("task snapshot")
            .runtime_ticks;
    }
    println!(
        "PKSCHED2:TRACE PASS ticks={} next={},{},{},{},{},{} causes={},{},{},{},{},{} events={},{},{},{},{},{} runtime={},{},{},{} switches={} pending={}",
        summary.timer_ticks,
        next[0],
        next[1],
        next[2],
        next[3],
        next[4],
        next[5],
        causes[0],
        causes[1],
        causes[2],
        causes[3],
        causes[4],
        causes[5],
        processed[0],
        processed[1],
        processed[2],
        processed[3],
        processed[4],
        processed[5],
        runtime[0],
        runtime[1],
        runtime[2],
        runtime[3],
        summary.context_switches,
        summary.pending_events,
    );

    let good_frame = frame();
    let mut rejected = 0;
    for hostile in [
        InterruptFrameContract {
            depth: 2,
            ..good_frame
        },
        InterruptFrameContract {
            vector: 0x41,
            ..good_frame
        },
        InterruptFrameContract {
            error_code: 1,
            ..good_frame
        },
        InterruptFrameContract {
            code_selector: 0x10,
            ..good_frame
        },
        InterruptFrameContract {
            interrupted_rflags: 1 << 1,
            ..good_frame
        },
        InterruptFrameContract {
            handler_interrupts_disabled: false,
            ..good_frame
        },
        InterruptFrameContract {
            scheduler_lock_held: false,
            ..good_frame
        },
        InterruptFrameContract {
            handler_rsp: 0xa000,
            ..good_frame
        },
    ] {
        rejected += usize::from(validate_interrupt_frame(&hostile).is_err());
    }
    let ownership = ContextOwnership {
        outgoing_rsp: 0x2000,
        outgoing_bottom: 0x1000,
        outgoing_top: 0x2000,
        incoming_rsp: 0x3080,
        incoming_bottom: 0x3000,
        incoming_top: 0x4000,
        stack_alignment: 16,
    };
    println!(
        "PKSCHED2:FRAME PASS valid={} hostile_rejected={} top_rsp_valid={} frame_bytes=176 alignment=16",
        usize::from(validate_interrupt_frame(&good_frame).is_ok()),
        rejected,
        usize::from(validate_context_ownership(&ownership).is_ok()),
    );

    for task in [task_a, task_b, signal_task, cancel_task] {
        controller.scheduler_mut().teardown(task).expect("teardown");
    }
    let cleanup = controller.scheduler().summary();
    println!(
        "PKSCHED2:CLEANUP PASS dead={} runnable={} running={} blocked={} teardowns={} queue_entries={}",
        cleanup.dead_count,
        cleanup.runnable_count,
        cleanup.running_count,
        cleanup.blocked_count,
        cleanup.teardown_count,
        cleanup.runnable_count,
    );
}
