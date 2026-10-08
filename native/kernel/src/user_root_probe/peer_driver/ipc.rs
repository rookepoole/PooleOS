//! Actual CPL3 request/reply through two bounded kernel-owned endpoints.
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
                Err(_) => stop(1000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let baseline = manager.summary().allocated_pages;
    let before = arch::x86_64::user_root_write_count();
    let mut peers = [
        checked!(Peer::new(
            0,
            16,
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            timer_driver::Probe::None,
            false
        )),
        checked!(Peer::new(
            1,
            17,
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
    if peers[0].root == peers[1].root || manager.summary().allocated_pages != baseline + 26 {
        stop(135, serial, debugcon);
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
    if handles != [0x100010001, 0x100010001, 0x100010002, 0x100010002] {
        stop(135, serial, debugcon);
    }
    let mut stopped = [false; 2];
    let mut calls = [0; 2];
    let mut ticks = 0u64;
    let mut preemptions = 0u64;
    let mut waiting = [None; 2];
    let mut waits = 0u64;
    let mut wakes = 0u64;
    let mut cancellations = 0u64;
    for _ in 0..64 {
        if stopped == [true; 2] {
            break;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let index = usize::from(id.slot);
        if index >= 2
            || stopped[index]
            || peers[index].id.slot != id.slot
            || peers[index].id.generation != id.generation
        {
            stop(136, serial, debugcon);
        }
        let p = &mut peers[index];
        if let Some(ticket) = waiting[index] {
            let status = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|space| {
                    space.complete_wait(ticket, &mut scheduler, cpu, |status| {
                        p.slot
                            .complete_wait(p.id, ticket, status)
                            .map_err(|_| poolekernel::capability_ipc::Error::Identity)
                    })
                })
            });
            if !matches!(
                status,
                poolekernel::user_entry::syscall::Status::Ok
                    | poolekernel::user_entry::syscall::Status::Cancelled
            ) {
                stop(136, serial, debugcon);
            }
            waiting[index] = None;
        }
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let slice = checked!(p.slot.run_slice(p.id));
        let elapsed = checked!(p.slot.account_slice(p.id, &mut scheduler, cpu));
        ticks = checked!(ticks.checked_add(elapsed).ok_or(()));
        match slice.event {
            Event::Waiting { ticket, .. } => {
                checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|space| {
                        space.park_wait(ticket, &mut scheduler, cpu)
                    })
                });
                waiting[index] = Some(ticket);
                waits += 1;
                if index == 0 && cancellations == 0 {
                    checked!(unsafe {
                        arch::x86_64::user_ipc::with_waits(|space| {
                            space.cancel_wait(ticket, &mut scheduler, cpu)
                        })
                    });
                    cancellations += 1;
                }
            }
            Event::Preempted { .. } => {
                preemptions += 1;
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                if outcome.reason != Reason::Exit(if index == 0 { 91 } else { 90 })
                    || outcome.syscalls != if index == 0 { 9 } else { 4 }
                {
                    stop(137, serial, debugcon);
                }
                calls[index] = outcome.syscalls;
                // Slot retirement revokes this task's IPC authority before releasing its root.
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                stopped[index] = true;
            }
        }
        wakes += u64::from(checked!(unsafe {
            arch::x86_64::user_ipc::with_waits(|space| space.poll_wakes(&mut scheduler, cpu))
        }));
    }
    checked!(scheduler.validate());
    let summary = scheduler.summary();
    let dispatches = u64::from(summary.dispatch_count);
    let writes = arch::x86_64::user_root_write_count() - before;
    if stopped != [true; 2]
        || dispatches != preemptions + waits + 2
        || waits != 3
        || wakes != 2
        || cancellations != 1
        || waiting != [None; 2]
        || writes != dispatches * 2
        || ticks == 0
        || summary.dead_count != 2
        || summary.running_count != 0
        || summary.runnable_count != 0
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(138, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-IPC PASS contract=PKIPC1 abi=PSABI1 endpoints=2 handles=4 max_bytes=64 depth=4 request_bytes=8 reply_bytes=8 transformed=1 forged_denied=1 rights_denied=1 oversize_denied=1 copy_fault_denied=1");
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [
        (" dispatches=", dispatches),
        (" preemptions=", preemptions),
        (" ticks=", ticks),
        (" calls0=", u64::from(calls[0])),
        (" calls1=", u64::from(calls[1])),
        (" cr3_writes=", writes),
        (" waits=", waits),
        (" wakes=", wakes),
        (" cancellations=", cancellations),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" client_exit=91 server_exit=90 owners_detached=2 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 blocking=1 automatic_retirement=1 saved_state=1 production=0\n");
}
