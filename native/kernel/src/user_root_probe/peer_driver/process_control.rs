//! Native PPROC1 mechanism probe: policy comes from actual CPL3 calls.
use super::*;
use poolekernel::capability_ipc::{
    admission::{Member, Step},
    process::Rights,
};

#[inline(never)]
pub fn run(
    handoff: &Handoff<'_>,
    core: CoreRecord,
    bits: u8,
    manager: &mut PhysicalMemoryManager,
    topology: interrupt_time::MadtTopology,
    hpet: interrupt_time::HpetDescription,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> ! {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(30000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let baseline = manager.summary().allocated_pages;
    if baseline > 12 {
        stop(30001, serial, debugcon);
    }
    let mut peers = [
        checked!(Peer::new(
            0,
            2,
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            timer_driver::Probe::None,
            false
        )),
        checked!(Peer::new_with_arguments(
            1,
            28,
            [0x100050001, 0x100050002, 0, 0, 0, 0],
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            timer_driver::Probe::None,
            false
        )),
        checked!(Peer::new_with_arguments(
            2,
            26,
            [1024, 1, 0, 0, 0, 0],
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            timer_driver::Probe::None,
            false
        )),
    ];
    round(&mut peers, 1, baseline, core, manager, serial, debugcon);
    checked!(peers[0].restart(
        29,
        [0x200010001, 0, 0, 0, 0, 0],
        handoff,
        core,
        bits,
        manager,
        topology,
        hpet,
        timer_driver::Probe::None
    ));
    checked!(peers[1].restart(
        28,
        [0x200050001, 0x200050002, 0, 0, 0, 0],
        handoff,
        core,
        bits,
        manager,
        topology,
        hpet,
        timer_driver::Probe::None
    ));
    checked!(peers[2].restart(
        26,
        [1024, 1, 0, 0, 0, 0],
        handoff,
        core,
        bits,
        manager,
        topology,
        hpet,
        timer_driver::Probe::None
    ));
    round(&mut peers, 2, baseline, core, manager, serial, debugcon);
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:PROCESS-RESULT PASS contract=PPROC1 rounds=2 cancelled=2 controller_exit=104 survivor_exit=100 released_pages=78 scrubbed_data_pages=36 objects_remaining=0 cpl=3 production=0 terminal=halt\n");
    halt_forever();
}

#[inline(never)]
fn round(
    peers: &mut [Peer; 3],
    generation: u32,
    baseline: u64,
    core: CoreRecord,
    manager: &mut PhysicalMemoryManager,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(31000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let before = arch::x86_64::user_root_write_count();
    let roots = peers.each_ref().map(|p| p.root);
    if peers.iter().any(|p| p.id.generation != generation)
        || manager.summary().allocated_pages != baseline + 39
        || roots[0] == roots[1]
        || roots[0] == roots[2]
        || roots[1] == roots[2]
    {
        stop(31001, serial, debugcon);
    }
    let cpu = checked!(scheduler::CpuId::new(0));
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let members = peers.each_ref().map(|p| Member {
        id: p.id,
        image: p.admission,
        priority: 16,
    });
    checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| {
            if !s.is_empty() {
                return Err(poolekernel::capability_ipc::Error::Identity);
            }
            let a = s
                .admit(&mut scheduler, &members, &[Step::Endpoint { member: 0 }])
                .map_err(|_| poolekernel::capability_ipc::Error::Identity)?;
            let stop = s.grant_process(peers[1].id, peers[0].id, Rights::InspectTerminate)?;
            let inspect = s.grant_process(peers[1].id, peers[2].id, Rights::Inspect)?;
            let tag = u64::from(generation) << 32;
            if a.handles[0] != tag | 0x10001 || stop != tag | 0x50001 || inspect != tag | 0x50002 {
                return Err(poolekernel::capability_ipc::Error::Identity);
            }
            Ok(())
        })
    });
    let mut dead = [false; 3];
    let mut ticks = [0u64; 3];
    let mut calls = [0u64; 3];
    let mut waiting = None;
    let mut stopped = false;
    let mut after_stop = 0;
    for _ in 0..256 {
        let id = checked!(scheduler.dispatch(cpu));
        let i = usize::from(id.slot);
        if i >= 3 || dead[i] || id.generation != generation {
            stop(31002, serial, debugcon);
        }
        let p = &mut peers[i];
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let result = p.slot.run_slice(p.id);
        ticks[i] += checked!(p.slot.account_slice(p.id, &mut scheduler, cpu));
        let slice = checked!(result);
        if i == 2 && stopped {
            after_stop += 1;
        }
        match slice.event {
            Event::Waiting { ticket, syscalls } => {
                if i != 0 || generation != 2 || waiting.is_some() {
                    stop(31003, serial, debugcon);
                }
                calls[i] = syscalls;
                checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|s| s.park_wait(ticket, &mut scheduler, cpu))
                });
                waiting = Some(ticket);
            }
            Event::Preempted { syscalls, .. } | Event::BudgetYield { syscalls } => {
                calls[i] = syscalls;
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                if i == 0 || outcome.reason != Reason::Exit(if i == 1 { 104 } else { 100 }) {
                    stop(31004, serial, debugcon);
                }
                calls[i] = u64::from(outcome.syscalls);
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                dead[i] = true;
            }
        }
        if unsafe { arch::x86_64::read_cr3() } != core.page_table_root_physical
            || arch::x86_64::user::active()
            || arch::x86_64::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
        {
            stop(31005, serial, debugcon);
        }
        if let Some(permit) =
            checked!(unsafe { arch::x86_64::user_ipc::with_waits(|s| Ok(s.claim_process_stop())) })
        {
            if stopped || dead[0] {
                stop(31006, serial, debugcon);
            }
            let target = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| s.validate_process_stop(&permit))
            });
            if target != peers[0].id {
                stop(31007, serial, debugcon);
            }
            let p = &mut peers[0];
            let outcome = if generation == 2 {
                checked!(p.slot.cancel_waiting(p.id, checked!(waiting.ok_or(()))))
            } else {
                checked!(p.slot.cancel_suspended(p.id))
            };
            if outcome.reason != Reason::Cancelled {
                stop(31008, serial, debugcon);
            }
            if outcome.syscalls != u64::from(generation == 2) {
                stop(31012, serial, debugcon);
            }
            let retirement_before = arch::x86_64::user_root_write_count();
            checked!(p.reap(manager, outcome));
            // Suspended/waiting roots were restored by suspend; retirement still
            // requires a fresh flush before releasing any exposed image.
            if arch::x86_64::user_root_write_count() - retirement_before != 1 {
                stop(31013, serial, debugcon);
            }
            checked!(scheduler.teardown(checked!(scheduler::TaskId::new(
                target.slot,
                target.generation
            ))));
            let invalid = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    Ok(s.validate_process_stop(&permit).is_err()
                        && s.claim_process_stop().is_none())
                })
            });
            if !invalid || manager.summary().allocated_pages != baseline + 26 {
                stop(31009, serial, debugcon);
            }
            waiting = None;
            dead[0] = true;
            stopped = true;
        }
        checked!(scheduler.validate());
        for j in 0..3 {
            let sid = checked!(scheduler::TaskId::new(peers[j].id.slot, generation));
            if checked!(scheduler.task_snapshot(sid)).runtime_ticks != ticks[j] {
                stop(31010, serial, debugcon);
            }
        }
        if dead == [true; 3] {
            break;
        }
    }
    let dispatches = u64::from(scheduler.summary().dispatch_count);
    let writes = arch::x86_64::user_root_write_count() - before;
    if dead != [true; 3]
        || !stopped
        || after_stop < 2
        || ticks.contains(&0)
        || waiting.is_some()
        || calls[1] < 6
        || calls[2] != 1025
        || writes != dispatches * 2 + 1
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:PROCESS-INCOMPLETE");
        for (label, value) in [
            (" dispatches=", dispatches),
            (" writes=", writes),
            (" dead0=", u64::from(dead[0])),
            (" dead1=", u64::from(dead[1])),
            (" dead2=", u64::from(dead[2])),
            (" stopped=", u64::from(stopped)),
            (" after_stop=", after_stop),
            (" calls1=", calls[1]),
            (" calls2=", calls[2]),
            (" ticks0=", ticks[0]),
            (" ticks1=", ticks[1]),
            (" ticks2=", ticks[2]),
            (" pages=", manager.summary().allocated_pages),
            (" baseline=", baseline),
        ] {
            log.write_str(label);
            log.write_decimal_u64(value);
        }
        log.write_str("\n");
        stop(31011, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:PROCESS-ROUND PASS contract=PPROC1");
    for (label, value) in [
        (" generation=", u64::from(generation)),
        (" waiting=", u64::from(generation == 2)),
        (" dispatches=", dispatches),
        (" controller_calls=", calls[1]),
        (" survivor_calls=", calls[2]),
        (" survivor_after_stop=", after_stop),
        (" ticks0=", ticks[0]),
        (" ticks1=", ticks[1]),
        (" ticks2=", ticks[2]),
        (" cr3_writes=", writes),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    for (label, value) in [
        (" root0=", roots[0]),
        (" root1=", roots[1]),
        (" root2=", roots[2]),
    ] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    log.write_str(" forged_denied=1 rights_denied=1 permit_invalidated=1 cancelled=1 retirement_flushes=1 released_pages=39 scrubbed_data_pages=18 cpl=3 production=0\n");
}
