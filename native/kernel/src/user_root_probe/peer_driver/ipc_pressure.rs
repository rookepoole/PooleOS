//! Reuse the same owned task slots and IPC tables across pressure and peer death.
use super::*;
use poolekernel::{capability_ipc::Error as IpcError, user_entry::syscall::Status};

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
                Err(_) => stop(2000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let baseline = manager.summary().allocated_pages;
    let mut peers = [
        checked!(Peer::new_with_arguments(
            2,
            18,
            [1, 0, 0, 0, 0, 0],
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
            3,
            19,
            [1, 0, 0, 0, 0, 0],
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
    for round in 0..5 {
        if round > 0 {
            for (index, p) in peers.iter_mut().enumerate() {
                checked!(p.restart(
                    18 + index,
                    [u64::from(round + 1), u64::from(round), 0, 0, 0, 0],
                    handoff,
                    core,
                    bits,
                    manager,
                    topology,
                    hpet,
                    if round == 4 && index == 1 {
                        timer_driver::Probe::FailOnce
                    } else {
                        timer_driver::Probe::None
                    }
                ));
            }
        }
        run_round(&mut peers, round, baseline, manager, serial, debugcon);
    }
    for (index, p) in peers.iter_mut().enumerate() {
        checked!(p.restart(
            20 + index,
            [6, 0, 0, 0, 0, 0],
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            timer_driver::Probe::None
        ));
    }
    super::ipc_reply::run(&mut peers, baseline, manager, serial, debugcon);
    let mut clock = checked!(clock_driver::Session::start(
        handoff, core, bits, manager, topology, hpet
    ));
    for round in 0..4u32 {
        for (index, p) in peers.iter_mut().enumerate() {
            checked!(p.restart(
                22 + index,
                [u64::from(round + 7), u64::from(round), 0, 0, 0, 0],
                handoff,
                core,
                bits,
                manager,
                topology,
                hpet,
                timer_driver::Probe::None
            ));
        }
        super::ipc_request::run(&mut peers, round, baseline, manager, serial, debugcon);
        clock
            .idle_interval()
            .unwrap_or_else(|_| stop(2551, serial, debugcon));
    }
    if let Err(stage) = clock.finish(serial, debugcon) {
        stop(5000 + stage, serial, debugcon);
    }
    let mut clock = checked!(clock_driver::Session::start(
        handoff, core, bits, manager, topology, hpet
    ));
    for round in 0..2u32 {
        for (index, p) in peers.iter_mut().enumerate() {
            checked!(p.restart(
                24 + index,
                [u64::from(round + 11), u64::from(round), 0, 0, 0, 0],
                handoff,
                core,
                bits,
                manager,
                topology,
                hpet,
                timer_driver::Probe::None
            ));
        }
        super::ipc_deadline::run(
            &mut peers, round, baseline, &mut clock, manager, serial, debugcon,
        );
    }
    if let Err(stage) = clock.finish_deadlines(serial, debugcon) {
        stop(7000 + stage, serial, debugcon);
    }
    // Preparation has a large bounded frame; do not nest it beneath admission.
    for generation in [13, 14] {
        for p in peers.iter_mut() {
            checked!(p.restart(
                0,
                [0; 6],
                handoff,
                core,
                bits,
                manager,
                topology,
                hpet,
                timer_driver::Probe::None
            ));
        }
        if generation == 13 {
            super::admission::rollback(&mut peers, baseline, manager, serial, debugcon);
        } else {
            super::admission::run(&mut peers, baseline, manager, serial, debugcon);
        }
    }
}

#[inline(never)]
fn run_round(
    peers: &mut [Peer; 2],
    round: u32,
    baseline: u64,
    manager: &mut PhysicalMemoryManager,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(2000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let before = arch::x86_64::user_root_write_count();
    if peers[0].root == peers[1].root || manager.summary().allocated_pages != baseline + 26 {
        stop(2001, serial, debugcon);
    }
    for (index, p) in peers.iter().enumerate() {
        if p.id.slot != index as u8 + 2 || p.id.generation != round + 1 {
            stop(2002, serial, debugcon);
        }
        if round > 0
            && p.slot
                .state(TaskId {
                    slot: p.id.slot,
                    generation: round,
                })
                .is_ok()
        {
            stop(2003, serial, debugcon);
        }
    }
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    let handles = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap(
            [
                (peers[0].id, peers[0].admission),
                (peers[1].id, peers[1].admission),
            ],
            &mut scheduler,
        )
    });
    let base = (u64::from(round + 1) << 32) | 0x10001;
    if handles != [base, base, base + 1, base + 1] {
        stop(2004, serial, debugcon);
    }
    let extra =
        checked!(unsafe { arch::x86_64::user_ipc::with_waits(|s| s.create_endpoint(peers[1].id)) });
    if extra != base + 2 {
        stop(2005, serial, debugcon);
    }
    if round > 0 {
        for p in peers.iter() {
            checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    let stale = TaskId {
                        slot: p.id.slot,
                        generation: round,
                    };
                    if s.attach(stale, p.admission) != Err(IpcError::Identity)
                        || s.detach(stale) != Err(IpcError::Identity)
                    {
                        return Err(IpcError::Identity);
                    }
                    Ok(())
                })
            });
        }
    }
    let mut dead = [false; 2];
    let mut waiting = [None; 2];
    let mut calls = [0; 2];
    let mut ticks = [0u64; 2];
    let mut waits = 0u64;
    let mut wakes = 0u64;
    let mut preempts = 0u64;
    let mut revoked = 0u64;
    let mut recovered = false;
    for _ in 0..64 {
        if dead == [true; 2] {
            break;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let index = checked!(usize::from(id.slot).checked_sub(2).ok_or(()));
        if index >= 2 || dead[index] || peers[index].id.generation != id.generation {
            stop(2006, serial, debugcon);
        }
        let p = &mut peers[index];
        if let Some(ticket) = waiting[index] {
            let status = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|space| {
                    space.complete_wait(ticket, &mut scheduler, cpu, |status| {
                        p.slot
                            .complete_wait(p.id, ticket, status)
                            .map_err(|_| IpcError::Identity)
                    })
                })
            });
            if status
                != if round > 0 && index == 0 {
                    Status::Revoked
                } else {
                    Status::Ok
                }
            {
                stop(2007, serial, debugcon);
            }
            revoked += u64::from(status == Status::Revoked);
            waiting[index] = None;
        }
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let result = p.slot.run_slice(p.id);
        let elapsed = checked!(p.slot.account_slice(p.id, &mut scheduler, cpu));
        ticks[index] = checked!(ticks[index].checked_add(elapsed).ok_or(()));
        let mut outcome = None;
        if round == 4 && index == 1 {
            if recovered
                || result
                    != Err(task::Error::Cpu(
                        poolekernel::user_entry::prepared::cpu::Error::User(
                            poolekernel::user_entry::privilege::Error::Hardware,
                        ),
                    ))
            {
                stop(2008, serial, debugcon);
            }
            checked!(p.recover_timer(manager));
            checked!(scheduler.teardown(id));
            dead[index] = true;
            recovered = true;
        } else {
            let slice = checked!(result);
            match slice.event {
                Event::Waiting { ticket, .. } => {
                    checked!(unsafe {
                        arch::x86_64::user_ipc::with_waits(|s| {
                            s.park_wait(ticket, &mut scheduler, cpu)
                        })
                    });
                    waiting[index] = Some(ticket);
                    waits += 1;
                    if round == 3 && index == 1 {
                        outcome = Some(checked!(p.slot.cancel_waiting(p.id, ticket)));
                    }
                }
                Event::Preempted { .. } => {
                    preempts += 1;
                    if round == 2 && index == 1 {
                        outcome = Some(checked!(p.slot.cancel_suspended(p.id)));
                    } else {
                        checked!(scheduler.yield_current(cpu));
                    }
                }
                Event::Terminated(value) => outcome = Some(value),
            }
            if let Some(outcome) = outcome {
                let valid = if index == 0 {
                    dead[1]
                        && outcome.reason == Reason::Exit(93)
                        && outcome.syscalls == if round == 0 { 12 } else { 13 }
                } else {
                    match (round, outcome.reason, outcome.syscalls) {
                        (0, Reason::Exit(92), 11) => true,
                        (1, Reason::Fault(f), 0) => f.vector == 6 && f.error == 0,
                        (2, Reason::Cancelled, 0) | (3, Reason::Cancelled, 1) => true,
                        _ => false,
                    }
                };
                if !valid {
                    stop(2009, serial, debugcon);
                }
                calls[index] = outcome.syscalls;
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                if let Some(ticket) = waiting[index] {
                    if unsafe {
                        arch::x86_64::user_ipc::with_waits(|s| {
                            s.cancel_wait(ticket, &mut scheduler, cpu)
                        })
                    }
                    .is_ok()
                    {
                        stop(2010, serial, debugcon);
                    }
                    waiting[index] = None;
                }
                dead[index] = true;
            }
        }
        wakes += u64::from(checked!(unsafe {
            arch::x86_64::user_ipc::with_waits(|s| s.poll_wakes(&mut scheduler, cpu))
        }));
    }
    checked!(scheduler.validate());
    let summary = scheduler.summary();
    let dispatches = u64::from(summary.dispatch_count);
    let writes = arch::x86_64::user_root_write_count() - before;
    let expected_waits = if round == 0 {
        3
    } else if round == 3 {
        2
    } else {
        1
    };
    let terminals = if round == 2 || round == 3 { 1 } else { 2 };
    if dead != [true; 2]
        || waiting != [None; 2]
        || waits != expected_waits
        || wakes != if round == 0 { 3 } else { 1 }
        || revoked != u64::from(round > 0)
        || dispatches != preempts + waits + terminals
        || writes != dispatches * 2 + u64::from(round == 2 || round == 3)
        || ticks.contains(&0)
        || summary.dead_count != 2
        || summary.running_count != 0
        || summary.runnable_count != 0
        || recovered != (round == 4)
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(2011, serial, debugcon);
    }
    for (index, p) in peers.iter().enumerate() {
        let id = checked!(scheduler::TaskId::new(p.id.slot, p.id.generation));
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[index] {
            stop(2012, serial, debugcon);
        }
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-IPC-PRESSURE PASS contract=PKIPC2");
    for (label, value) in [
        (" round=", u64::from(round)),
        (" generation=", u64::from(round + 1)),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" owner=");
    log.write_str(["exit", "fault", "cancel", "wait_cancel", "quarantine"][round as usize]);
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [
        (" dispatches=", dispatches),
        (" preemptions=", preempts),
        (" ticks0=", ticks[0]),
        (" ticks1=", ticks[1]),
        (" calls0=", u64::from(calls[0])),
        (" calls1=", u64::from(calls[1])),
        (" waits=", waits),
        (" wakes=", wakes),
        (" revoked=", revoked),
        (" cr3_writes=", writes),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" full_denied=1 stale_denied=1 partial_output=");
    log.write_decimal_u64(if round == 0 { 4 } else { 0 });
    log.write_str(" survivor_exit=93 persistent_slots=1 automatic_retirement=1 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
