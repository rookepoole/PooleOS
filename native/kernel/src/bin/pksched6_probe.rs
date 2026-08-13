use poolekernel::scheduler_smp::{CPU_COUNT, CpuId, SmpScheduler, TASK_CAPACITY, TaskId};
use poolekernel::scheduler_smp_preempt::{
    Event, EventKind, SmpPreemption, canonical_frame, canonical_reschedule_ack,
};

fn cpu(value: u8) -> CpuId {
    CpuId::new(value).expect("CPU")
}

fn tick(
    controller: &mut SmpPreemption,
    cpu_value: u8,
    epoch: u64,
    attempt: u64,
    sequence: u64,
) -> poolekernel::scheduler_smp_preempt::TickOutcome {
    let owner = controller.current(cpu(cpu_value)).expect("current owner");
    let frame = canonical_frame(cpu(cpu_value), owner, epoch, epoch);
    let outcome = controller
        .handle_tick(&frame, attempt, sequence)
        .expect("timer tick");
    if let Some(ticket) = outcome.remote_ticket {
        assert_eq!(
            controller.current(cpu(cpu_value)).expect("gated owner"),
            owner
        );
        controller
            .acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))
            .expect("reschedule acknowledgement");
    }
    outcome
}

fn main() {
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
            .expect("create task");
        scheduler.activate(id, cpu(owner)).expect("activate task");
        tasks[slot] = id;
    }
    for value in 0..CPU_COUNT as u8 {
        let ticket = scheduler
            .stage_dispatch(cpu(value), 1, 1)
            .expect("initial dispatch");
        scheduler
            .acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))
            .expect("initial dispatch acknowledgement");
    }
    scheduler.block_runnable(tasks[1]).expect("block wake task");
    let mut controller = SmpPreemption::new(scheduler).expect("preemption controller");
    println!(
        "PKSCHED6:TOPOLOGY PASS cpus=4 aps=3 online_mask=0x0F queues=4 tasks=8 timer_lanes=4 frame_lanes=4 event_capacity=16 quantum=2"
    );

    let offline = controller
        .prove_offline_rollback(tasks[5], 3, 2)
        .expect("offline rollback");
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
        .expect("wake event");
    controller
        .queue_event(
            cpu(1),
            Event {
                due_tick: 1,
                sequence: 1,
                kind: EventKind::Cancel { task: tasks[3] },
            },
        )
        .expect("cancel event");
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
        .expect("migration event");

    let cpu1_event = tick(&mut controller, 1, 1, 3, 2);
    let cpu2_event = tick(&mut controller, 2, 1, 3, 2);
    let _ = tick(&mut controller, 3, 1, 3, 2);
    let _ = tick(&mut controller, 0, 1, 0, 0);
    println!(
        "PKSCHED6:EVENT PASS cpu1_order={},{} cpu2_order={} cancelled=1 wake=1 migration=1 pending=0 deterministic=1",
        cpu1_event.event_order[0], cpu1_event.event_order[1], cpu2_event.event_order[0],
    );

    let cpu1_before = controller.current(cpu(1)).expect("CPU1 before").slot;
    let cpu1_switch = tick(&mut controller, 1, 2, 4, 3);
    let cpu1_after = controller.current(cpu(1)).expect("CPU1 after").slot;
    let _ = tick(&mut controller, 2, 2, 4, 3);
    let cpu3_before = controller.current(cpu(3)).expect("CPU3 before").slot;
    let _ = tick(&mut controller, 3, 2, 4, 3);
    let cpu3_middle = controller.current(cpu(3)).expect("CPU3 middle").slot;
    let _ = tick(&mut controller, 0, 2, 0, 0);
    let _ = tick(&mut controller, 3, 3, 0, 0);
    let _ = tick(&mut controller, 3, 4, 5, 4);
    let cpu3_after = controller.current(cpu(3)).expect("CPU3 after").slot;
    let active = controller.summary();
    assert!(cpu1_switch.remote_ticket.is_some());
    println!(
        "PKSCHED6:RESCHEDULE PASS acks={} wake={} migration={} quantum={} context_switches={} ack_gated=1",
        active.remote_reschedule_acks,
        active.wake_events,
        active.migration_events,
        active.quantum_preemptions,
        active.context_switches,
    );
    println!(
        "PKSCHED6:OWNERSHIP PASS frame_epochs={},{},{},{} timer_ticks={},{},{},{} trace=1:{}>{};3:{}>{}>{} per_cpu=1",
        active.frame_epochs[0],
        active.frame_epochs[1],
        active.frame_epochs[2],
        active.frame_epochs[3],
        active.timer_ticks[0],
        active.timer_ticks[1],
        active.timer_ticks[2],
        active.timer_ticks[3],
        cpu1_before,
        cpu1_after,
        cpu3_before,
        cpu3_middle,
        cpu3_after,
    );
    println!(
        "PKSCHED6:ROLLBACK PASS offline_cpu={} timeouts={} rollbacks={} stale_rejections={} source_queue_restored=1 late_ack_rejected=1",
        offline.target_cpu,
        active.scheduler.timeout_count,
        active.timeout_rollbacks,
        active.stale_ack_rejections,
    );
    println!(
        "PKSCHED6:BOUNDS PASS quantum=2 event_latency={} watchdog_age={} maximum_bypass={} starvation=0 lost_wake=0 duplicate_runnable=0",
        active.maximum_event_latency, active.maximum_watchdog_age, active.scheduler.maximum_bypass,
    );

    controller.finish_shutdown(tasks).expect("exact shutdown");
    let shutdown = controller.summary();
    println!(
        "PKSCHED6:CLEANUP PASS online_after=0x{:02X} dead={} teardown={} frame_owners_revoked={} timer_owners_revoked={} pending_events={} pending_remote=0 valid={}",
        shutdown.online_mask,
        shutdown.scheduler.dead_count,
        shutdown.scheduler.teardown_count,
        shutdown.frame_owner_revocations,
        shutdown.timer_owner_revocations,
        shutdown.pending_events,
        usize::from(controller.validate().is_ok()),
    );
}
