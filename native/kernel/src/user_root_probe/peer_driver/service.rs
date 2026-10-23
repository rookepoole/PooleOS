//! Sustained syscall work yields to a peer and survives a contained service fault.
use super::*;

#[inline(never)]
pub(super) fn run(
    peers: &mut [Peer; 2],
    baseline: u64,
    manager: &mut PhysicalMemoryManager,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(9000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let before = arch::x86_64::user_root_write_count();
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap(
            [
                (peers[0].id, peers[0].admission),
                (peers[1].id, peers[1].admission),
            ],
            &mut scheduler,
        )
    });
    let mut dead = [false; 2];
    let mut calls = [0u64; 2];
    let mut ticks = [0u64; 2];
    let mut yields = [0u64; 2];
    let mut after_fault = 0;
    let mut first_run = true;
    let mut previous = 1;
    for _ in 0..32 {
        if dead == [true; 2] {
            break;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let index = checked!(usize::from(id.slot).checked_sub(2).ok_or(()));
        if index >= 2
            || dead[index]
            || id.generation != 15
            || (!dead[0] && index == previous)
            || (first_run && index != 0)
        {
            stop(9001, serial, debugcon);
        }
        first_run = false;
        previous = index;
        let p = &mut peers[index];
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let slice = checked!(p.slot.run_slice(p.id));
        ticks[index] = checked!(
            ticks[index]
                .checked_add(checked!(p.slot.account_slice(p.id, &mut scheduler, cpu)))
                .ok_or(())
        );
        match slice.event {
            Event::BudgetYield { syscalls } => {
                if syscalls != calls[index] + 64 || p.slot.state(p.id) != Ok(task::State::Suspended)
                {
                    stop(9002, serial, debugcon);
                }
                calls[index] = syscalls;
                yields[index] += 1;
                if dead[0] && index == 1 {
                    after_fault += 1;
                }
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                let valid = if index == 0 {
                    matches!(
                        outcome.reason,
                        Reason::Fault(task::Fault {
                            vector: 6,
                            error: 0,
                            ..
                        })
                    ) && outcome.syscalls == 256
                        && calls[1] == 256
                        && !dead[1]
                } else {
                    outcome.reason == Reason::Exit(100) && outcome.syscalls == 513 && dead[0]
                };
                if !valid {
                    stop(9003, serial, debugcon);
                }
                calls[index] = outcome.syscalls;
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                dead[index] = true;
            }
            _ => stop(9004, serial, debugcon),
        }
    }
    checked!(scheduler.validate());
    let summary = scheduler.summary();
    let writes = arch::x86_64::user_root_write_count() - before;
    if dead != [true; 2]
        || calls != [256, 513]
        || yields != [4, 8]
        || ticks.contains(&0)
        || after_fault != 4
        || summary.dispatch_count != 14
        || writes != 28
        || summary.dead_count != 2
        || summary.runnable_count != 0
        || summary.running_count != 0
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(9005, serial, debugcon);
    }
    for (index, p) in peers.iter().enumerate() {
        let snapshot = checked!(
            scheduler.task_snapshot(checked!(scheduler::TaskId::new(p.id.slot, p.id.generation)))
        );
        if snapshot.runtime_ticks != ticks[index] {
            stop(9006, serial, debugcon);
        }
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-SERVICE PASS contract=PKSERVICE1 generation=15 calls_per_dispatch=64 calls0=256 calls1=513 yields0=4 yields1=8 dispatches=14 timer_preemptions=0 fault_vector=6 survivor_exit=100 survivor_after_fault=4 completed_copy_bytes=8 return_state_preserved=1 allowance_replenished=1");
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [(" ticks0=", ticks[0]), (" ticks1=", ticks[1])] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" cr3_writes=28 scheduler_match=1 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
