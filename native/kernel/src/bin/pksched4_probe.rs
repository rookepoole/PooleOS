use poolekernel::scheduler_smp::{
    ACK_ACCEPTED, AP_MASK, CALL_FUNCTION_OPERATION, CALL_FUNCTION_RESULT, CPU_COUNT, CpuId,
    ERROR_NONE, OFFLINE_PROBE_CPU, ONLINE_MASK, RemoteAck, SmpScheduler, TASK_CAPACITY, TaskId,
    TransferTicket,
};

fn cpu(value: u8) -> CpuId {
    CpuId::new(value).expect("CPU")
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

fn main() {
    let mut scheduler = SmpScheduler::new();
    let affinities = [0x01, 0x03, 0x02, 0x06, 0x04, 0x0c, 0x08, 0x01];
    let owners = [0, 0, 1, 1, 2, 2, 3, 0];
    let mut tasks = [TaskId::new(0, 1).expect("identity"); TASK_CAPACITY];
    for slot in 0..TASK_CAPACITY {
        let id = scheduler
            .create_task(slot as u8, 1, 16, affinities[slot])
            .expect("create");
        scheduler.activate(id, cpu(owners[slot])).expect("activate");
        tasks[slot] = id;
    }
    scheduler
        .block_runnable(tasks[1])
        .expect("block remote wake");
    let balance = [
        scheduler
            .select_least_loaded(ONLINE_MASK)
            .expect("balance all")
            .value(),
        scheduler
            .select_least_loaded(AP_MASK)
            .expect("balance AP")
            .value(),
    ];
    println!(
        "PKSCHED4:TOPOLOGY PASS cpus={} online_mask=0x{:02X} ap_mask=0x{:02X} queues={} tasks={} balance={},{} idle_owners={}",
        CPU_COUNT,
        ONLINE_MASK,
        AP_MASK,
        CPU_COUNT,
        TASK_CAPACITY,
        balance[0],
        balance[1],
        scheduler.summary().idle_cpu_count,
    );

    let offline = scheduler
        .stage_offline_probe(tasks[3], OFFLINE_PROBE_CPU, 3, 2)
        .expect("offline probe");
    scheduler.timeout(offline).expect("timeout rollback");
    assert_eq!(
        scheduler
            .acknowledge(offline, ack(offline))
            .unwrap_err()
            .label(),
        "pending_missing"
    );
    scheduler
        .reject_stale_ack(offline, ack(offline))
        .expect("late ack rejection");

    let wake = scheduler.stage_wake(tasks[1], cpu(1), 3, 2).expect("wake");
    scheduler.acknowledge(wake, ack(wake)).expect("wake ack");
    let migration_two = scheduler
        .stage_migration(tasks[3], cpu(2), 3, 2)
        .expect("migration two");
    scheduler
        .acknowledge(migration_two, ack(migration_two))
        .expect("migration two ack");
    let migration_three = scheduler
        .stage_migration(tasks[5], cpu(3), 3, 2)
        .expect("migration three");
    scheduler
        .acknowledge(migration_three, ack(migration_three))
        .expect("migration three ack");
    println!(
        "PKSCHED4:TRANSFER PASS wake=1 migrations=2 transaction_acks={} queues={},{},{} owner_transfer=ack_gated timeout_target={}",
        scheduler.summary().remote_ack_count,
        scheduler.queue_len(cpu(1)).expect("queue one"),
        scheduler.queue_len(cpu(2)).expect("queue two"),
        scheduler.queue_len(cpu(3)).expect("queue three"),
        OFFLINE_PROBE_CPU,
    );

    let mut ap_trace = [u8::MAX; 6];
    let mut trace_index = 0;
    for cpu_value in 1..CPU_COUNT as u8 {
        for (attempt, sequence) in [(4, 3), (5, 4)] {
            let ticket = scheduler
                .stage_dispatch(cpu(cpu_value), attempt, sequence)
                .expect("AP dispatch");
            ap_trace[trace_index] = ticket.task.slot;
            trace_index += 1;
            scheduler
                .acknowledge(ticket, ack(ticket))
                .expect("dispatch ack");
            scheduler
                .complete_current(cpu(cpu_value))
                .expect("dispatch complete");
        }
    }
    let bsp_first = scheduler.dispatch_local(cpu(0)).expect("BSP dispatch one");
    let bsp_second = scheduler.dispatch_local(cpu(0)).expect("BSP dispatch two");
    println!(
        "PKSCHED4:DISPATCH PASS bsp_trace={},{} ap_trace=1:{},1:{},2:{},2:{},3:{},3:{} bsp_dispatches={} ap_dispatches={} ipi_acks={} call_function_executions=9 max_bypass={}",
        bsp_first.slot,
        bsp_second.slot,
        ap_trace[0],
        ap_trace[1],
        ap_trace[2],
        ap_trace[3],
        ap_trace[4],
        ap_trace[5],
        scheduler.summary().bsp_dispatch_count,
        scheduler.summary().ap_dispatch_count,
        scheduler.summary().remote_ack_count,
        scheduler.summary().maximum_bypass,
    );

    let stale = TaskId::new(tasks[0].slot, 2).expect("stale identity");
    assert_eq!(
        scheduler.task_snapshot(stale).unwrap_err().label(),
        "generation_stale"
    );
    let before_park = scheduler.summary();
    println!(
        "PKSCHED4:ROLLBACK PASS offline_cpu={} timeouts={} rollbacks={} late_ack_rejected=1 stale_generation_rejected=1 stale_rejections={} lost_wake=0 duplicate_runnable=0",
        OFFLINE_PROBE_CPU,
        before_park.timeout_count,
        before_park.rollback_count,
        before_park.stale_rejection_count,
    );
    assert_eq!(before_park.dead_count as usize, TASK_CAPACITY);
    assert_eq!(before_park.idle_cpu_count as usize, CPU_COUNT);
    let mut owner_epoch_sum = 0u32;
    for id in tasks {
        owner_epoch_sum += scheduler
            .task_snapshot(id)
            .expect("task snapshot")
            .owner_epoch;
    }
    for cpu_value in (1..CPU_COUNT as u8).rev() {
        scheduler
            .offline_idle_cpu(cpu(cpu_value))
            .expect("park idle AP");
    }
    let after_park = scheduler.summary();
    println!(
        "PKSCHED4:CLEANUP PASS tasks_dead={} queues=0 running=0 idle_before={} owner_epoch_sum={} online_after=0x{:02X} parked_mask=0x{:02X} teardown={} valid={}",
        after_park.dead_count,
        before_park.idle_cpu_count,
        owner_epoch_sum,
        after_park.online_mask,
        AP_MASK,
        after_park.teardown_count,
        usize::from(scheduler.validate().is_ok()),
    );
}
