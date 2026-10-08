//! A returned quantum loses its sample and encounters a real pending-IRQ cleanup failure.
use super::*;

#[inline(never)]
pub(crate) fn run(
    handoff: &Handoff<'_>,
    core: CoreRecord,
    bits: u8,
    manager: &mut PhysicalMemoryManager,
    topology: interrupt_time::MadtTopology,
    hpet: interrupt_time::HpetDescription,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(129, serial, debugcon),
            }
        };
    }
    let baseline = manager.summary().allocated_pages;
    let backup_before = checked!(arch::x86_64::user_watchdog::proof());
    let before = arch::x86_64::user_root_write_count();
    let mut failed = checked!(Peer::new(
        0,
        15,
        handoff,
        core,
        bits,
        manager,
        topology,
        hpet,
        timer_driver::Probe::FailOnce,
        false
    ));
    let mut peer = checked!(Peer::new(
        1,
        3,
        handoff,
        core,
        bits,
        manager,
        topology,
        hpet,
        timer_driver::Probe::None,
        false
    ));
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    let id = checked!(scheduler.create_task(0, failed.id.generation, 16, 1));
    let peer_id = checked!(scheduler.create_task(1, peer.id.generation, 16, 1));
    checked!(scheduler.activate(id, cpu));
    checked!(scheduler.activate(peer_id, cpu));
    if checked!(scheduler.dispatch(cpu)) != id {
        stop(130, serial, debugcon);
    }
    checked!(failed.slot.activate(failed.id, manager, &mut failed.memory));
    let result = failed.slot.run_slice(failed.id);
    let pending = checked!(failed.slot.runtime(failed.id));
    if result
        != Err(task::Error::Cpu(
            poolekernel::user_entry::prepared::cpu::Error::User(
                poolekernel::user_entry::privilege::Error::Hardware,
            ),
        ))
        || !pending.unknown
        || pending.pending_ticks.is_some()
        || pending.charged_slices != 0
        || failed
            .slot
            .account_slice(failed.id, &mut scheduler, cpu)
            .is_ok()
        || failed
            .slot
            .abandon(failed.id, manager, &mut failed.memory)
            .is_ok()
    {
        stop(130, serial, debugcon);
    }
    for handle in failed.handles {
        if manager.free(handle) != Err(PhysicalMemoryError::AllocationRetained) {
            stop(130, serial, debugcon);
        }
    }
    let before_record = scheduler.summary();
    if failed
        .slot
        .account_unknown(
            TaskId {
                generation: failed.id.generation + 1,
                ..failed.id
            },
            &mut scheduler,
            cpu,
        )
        .is_ok()
        || failed
            .slot
            .account_unknown(
                failed.id,
                &mut scheduler,
                checked!(scheduler::CpuId::new(1)),
            )
            .is_ok()
        || scheduler.summary() != before_record
        || checked!(failed.slot.runtime(failed.id)) != pending
    {
        stop(131, serial, debugcon);
    }
    checked!(failed.slot.account_unknown(failed.id, &mut scheduler, cpu));
    let settled = checked!(failed.slot.runtime(failed.id));
    let snapshot = checked!(scheduler.task_snapshot(id));
    if settled.unknown
        || settled.unmeasured_slices != 1
        || settled.charged_ticks != 0
        || snapshot.unmeasured_dispatches != 1
        || snapshot.runtime_ticks != 0
        || failed
            .slot
            .account_unknown(failed.id, &mut scheduler, cpu)
            .is_ok()
        || scheduler.yield_current(cpu).is_ok()
        || scheduler.block_current(cpu).is_ok()
        || scheduler.account_dispatch(cpu, id, 1, 0, 0).is_ok()
        || checked!(scheduler.task_snapshot(id)) != snapshot
        || checked!(scheduler.current(cpu)) != Some(id)
        || failed.slot.outcome(failed.id).is_ok()
    {
        stop(131, serial, debugcon);
    }
    // Existing recovery verifies retained root/descriptors/device, restart/reap
    // denial, pending-IRQ draining and quiescence before restoring/freeing memory.
    checked!(failed.recover_timer(manager));
    checked!(scheduler.teardown(id));
    let retired = checked!(scheduler.task_snapshot(id));
    if retired.unmeasured_dispatches != 1
        || retired.runtime_ticks != 0
        || retired.state != scheduler::TaskState::Dead
        || manager.summary().allocated_pages != baseline + 13
    {
        stop(132, serial, debugcon);
    }
    let mut ticks = 0u64;
    let mut preemptions = 0u64;
    let mut progress = 0u64;
    let mut exited = false;
    for _ in 0..64 {
        if checked!(scheduler.dispatch(cpu)) != peer_id {
            stop(133, serial, debugcon);
        }
        checked!(peer.slot.activate(peer.id, manager, &mut peer.memory));
        let slice = checked!(peer.slot.run_slice(peer.id));
        let elapsed = checked!(peer.slot.account_slice(peer.id, &mut scheduler, cpu));
        if peer
            .slot
            .account_slice(peer.id, &mut scheduler, cpu)
            .is_ok()
        {
            stop(133, serial, debugcon);
        }
        ticks = checked!(ticks.checked_add(elapsed).ok_or(()));
        match slice.event {
            Event::Preempted {
                ticks: observed,
                syscalls,
                progress: now,
            } => {
                if observed != elapsed || syscalls != 0 || now <= progress {
                    stop(133, serial, debugcon);
                }
                progress = now;
                preemptions += 1;
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                if outcome.reason != Reason::Exit(84) || outcome.syscalls != 1 {
                    stop(133, serial, debugcon);
                }
                checked!(peer.reap(manager, outcome));
                checked!(scheduler.teardown(peer_id));
                exited = true;
                break;
            }
        }
    }
    checked!(scheduler.validate());
    let summary = scheduler.summary();
    let backup = checked!(arch::x86_64::user_watchdog::proof());
    let dispatches = u64::from(summary.dispatch_count);
    let writes = arch::x86_64::user_root_write_count() - before;
    let measured = checked!(scheduler.task_snapshot(peer_id));
    if !exited
        || preemptions < 2
        || progress == 0
        || ticks == 0
        || dispatches != preemptions + 2
        || writes != 2 * dispatches
        || summary.dead_count != 2
        || summary.running_count != 0
        || summary.runnable_count != 0
        || measured.unmeasured_dispatches != 0
        || measured.runtime_ticks != ticks
        || manager.summary().allocated_pages != baseline
        || backup
            != [
                backup_before[0] + dispatches,
                backup_before[1],
                backup_before[2] + dispatches,
                backup_before[3] + dispatches,
            ]
    {
        stop(134, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-UNKNOWN PASS contract=PKUSER15 injection=returned_sample_loss unmeasured=1 measured0=0 total0=unknown pending=0 duplicate_denied=1 stale_denied=1 cpu_denied=1 zero_charge_denied=1 requeue_denied=1 outcome_denied=1 cleanup_retry=1 retained_pages=13 free_denials=5");
    for (label, value) in [(" root0=", failed.root), (" root1=", peer.root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [
        (" dispatches=", dispatches),
        (" peer_preemptions=", preemptions),
        (" peer_progress=", progress),
        (" peer_ticks=", ticks),
        (" cr3_writes=", writes),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" peer_exit=84 scheduler_match=1 retired_unknown=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
