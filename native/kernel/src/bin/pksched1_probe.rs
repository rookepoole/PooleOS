use poolekernel::scheduler::{
    COMPLETE_CPU_MASK, ContextSwitchContract, CpuId, MAX_CPUS, MAX_TASKS, Scheduler, TaskId,
    validate_context_switch_contract,
};

const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;

fn cpu(value: u8) -> CpuId {
    CpuId::new(value).expect("bounded CPU")
}

fn fold(mut checksum: u64, value: u64) -> u64 {
    for byte in value.to_le_bytes() {
        checksum ^= u64::from(byte);
        checksum = checksum.wrapping_mul(FNV_PRIME);
    }
    checksum
}

fn stress_profile() {
    let mut scheduler = Scheduler::new(COMPLETE_CPU_MASK).expect("four-CPU scheduler");
    let mut ids = [TaskId {
        slot: 0,
        generation: 1,
    }; MAX_TASKS];
    for (slot, id) in ids.iter_mut().enumerate() {
        *id = scheduler
            .create_task(
                slot as u8,
                1,
                (slot as u8 % MAX_CPUS as u8) + 8,
                COMPLETE_CPU_MASK,
            )
            .expect("task create");
        scheduler
            .activate(*id, cpu((slot % MAX_CPUS) as u8))
            .expect("task activate");
    }

    let mut random = 0x5a17_91d3_6c8e_204fu64;
    for _ in 0..4096 {
        random ^= random << 13;
        random ^= random >> 7;
        random ^= random << 17;
        let selected_cpu = cpu((random as usize % MAX_CPUS) as u8);
        if scheduler
            .current(selected_cpu)
            .expect("current query")
            .is_none()
        {
            let _ = scheduler.dispatch(selected_cpu);
        } else if random & 3 == 0 {
            let _ = scheduler.account_tick(selected_cpu, 1);
            let _ = scheduler.yield_current(selected_cpu);
        } else if random & 7 == 1 {
            let _ = scheduler.account_tick(selected_cpu, 2);
        } else {
            let _ = scheduler.yield_current(selected_cpu);
        }
        let id = ids[(random.rotate_left(9) as usize) % MAX_TASKS];
        let target = cpu((random.rotate_right(11) as usize % MAX_CPUS) as u8);
        let _ = scheduler.migrate(id, target);
        scheduler.validate().expect("stress invariant");
    }

    let summary = scheduler.summary();
    let mut checksum = FNV_OFFSET;
    let mut task_dispatches = [0u32; MAX_TASKS];
    let mut runtime_ticks = [0u64; MAX_TASKS];
    for (slot, id) in ids.into_iter().enumerate() {
        let task = scheduler.task_snapshot(id).expect("task snapshot");
        task_dispatches[slot] = task.dispatch_count;
        runtime_ticks[slot] = task.runtime_ticks;
        for value in [
            u64::from(task.id.slot),
            u64::from(task.id.generation),
            task.state as u64,
            u64::from(task.base_priority),
            u64::from(task.effective_priority),
            u64::from(task.affinity_mask),
            task.assigned_cpu
                .map_or(0, |value| u64::from(value.value()) + 1),
            task.wake_reason as u64,
            task.wait_kind as u64,
            u64::from(task.bypass_count),
            u64::from(task.dispatch_count),
            task.runtime_ticks,
        ] {
            checksum = fold(checksum, value);
        }
    }
    println!(
        "PKSCHED1:STRESS PASS sequence={} tasks={} runnable={} running={} blocked={} dead={} dispatches={} migrations={} wakes={} teardowns={} inheritance={} checksum=0x{checksum:016X} task_dispatches={},{},{},{},{},{},{},{} runtime_ticks={},{},{},{},{},{},{},{}",
        summary.sequence,
        summary.task_count,
        summary.runnable_count,
        summary.running_count,
        summary.blocked_count,
        summary.dead_count,
        summary.dispatch_count,
        summary.migration_count,
        summary.wake_count,
        summary.teardown_count,
        summary.priority_inheritance_count,
        task_dispatches[0],
        task_dispatches[1],
        task_dispatches[2],
        task_dispatches[3],
        task_dispatches[4],
        task_dispatches[5],
        task_dispatches[6],
        task_dispatches[7],
        runtime_ticks[0],
        runtime_ticks[1],
        runtime_ticks[2],
        runtime_ticks[3],
        runtime_ticks[4],
        runtime_ticks[5],
        runtime_ticks[6],
        runtime_ticks[7],
    );
}

fn wait_profile() {
    let mut scheduler = Scheduler::new(0x3).expect("two-CPU scheduler");
    let cancelled = scheduler.create_task(0, 1, 10, 1).expect("cancel task");
    let timed_out = scheduler.create_task(1, 1, 10, 2).expect("timeout task");
    scheduler
        .activate(cancelled, cpu(0))
        .expect("cancel activate");
    scheduler
        .activate(timed_out, cpu(1))
        .expect("timeout activate");
    scheduler.dispatch(cpu(0)).expect("cancel dispatch");
    scheduler.dispatch(cpu(1)).expect("timeout dispatch");
    scheduler.block_current(cpu(0)).expect("cancel block");
    scheduler.block_current(cpu(1)).expect("timeout block");
    scheduler
        .cancel_wait(cancelled, cpu(0))
        .expect("cancel wake");
    scheduler
        .timeout_wait(timed_out, cpu(1))
        .expect("timeout wake");
    scheduler.dispatch(cpu(0)).expect("cancel redispatch");
    scheduler.dispatch(cpu(1)).expect("timeout redispatch");
    let cancel_reason = scheduler.consume_wake(cpu(0)).expect("cancel consume");
    let timeout_reason = scheduler.consume_wake(cpu(1)).expect("timeout consume");
    let duplicate_rejected = scheduler.cancel_wait(cancelled, cpu(0)).is_err();
    let summary = scheduler.summary();
    println!(
        "PKSCHED1:WAIT PASS sequence={} wakes={} cancel_reason={} timeout_reason={} duplicate_rejected={}",
        summary.sequence,
        summary.wake_count,
        cancel_reason as u8,
        timeout_reason as u8,
        u8::from(duplicate_rejected),
    );
}

fn inheritance_profile() {
    let mut scheduler = Scheduler::new(0x3).expect("two-CPU scheduler");
    let owner = scheduler.create_task(0, 1, 2, 1).expect("owner task");
    scheduler.activate(owner, cpu(0)).expect("owner activate");
    scheduler.dispatch(cpu(0)).expect("owner dispatch");
    scheduler.lock_mutex(cpu(0)).expect("owner lock");
    scheduler.yield_current(cpu(0)).expect("owner yield");
    let waiter = scheduler.create_task(1, 1, 30, 2).expect("waiter task");
    scheduler.activate(waiter, cpu(1)).expect("waiter activate");
    scheduler.dispatch(cpu(1)).expect("waiter dispatch");
    scheduler.lock_mutex(cpu(1)).expect("waiter block");
    let inherited = scheduler
        .task_snapshot(owner)
        .expect("owner snapshot")
        .effective_priority;
    scheduler.dispatch(cpu(0)).expect("owner redispatch");
    let granted = scheduler
        .unlock_mutex(cpu(0))
        .expect("owner unlock")
        .expect("waiter grant");
    let restored = scheduler
        .task_snapshot(owner)
        .expect("owner restored")
        .effective_priority;
    println!(
        "PKSCHED1:INHERIT PASS owner_slot={} waiter_slot={} inherited={} restored={} granted_slot={} inheritance_events={}",
        owner.slot,
        waiter.slot,
        inherited,
        restored,
        granted.slot,
        scheduler.summary().priority_inheritance_count,
    );
}

fn context_profile() {
    let base = ContextSwitchContract {
        outgoing: TaskId::new(0, 1).expect("outgoing task"),
        incoming: TaskId::new(1, 1).expect("incoming task"),
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
    validate_context_switch_contract(&base).expect("valid context");
    let mut rejected = 0u8;
    for index in 0..8 {
        let mut hostile = base;
        match index {
            0 => hostile.incoming = hostile.outgoing,
            1 => hostile.scheduler_lock_held = false,
            2 => hostile.interrupts_disabled = false,
            3 => hostile.same_address_space = false,
            4 => hostile.fs_gs_unchanged = false,
            5 => hostile.xstate_unused = false,
            6 => hostile.kernel_stacks_distinct = false,
            _ => hostile.stack_alignment = 8,
        }
        rejected += u8::from(validate_context_switch_contract(&hostile).is_err());
    }
    println!(
        "PKSCHED1:CONTEXT PASS valid=1 hostile_rejected={} alignment=16 callee_saved=6",
        rejected
    );
}

fn main() {
    stress_profile();
    wait_profile();
    inheritance_profile();
    context_profile();
}
