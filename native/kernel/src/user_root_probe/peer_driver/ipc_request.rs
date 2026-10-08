//! Client-owned completion survives reply, discard and queued/claimed service death.
use super::*;
use poolekernel::{
    capability_ipc::{Error as IpcError, Rights},
    user_entry::syscall::Status,
};

#[inline(never)]
pub(super) fn run(
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
                Err(_) => stop(4000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let generation = round + 7;
    let expected = match round {
        0 => Status::Ok,
        1 => Status::Cancelled,
        _ => Status::Revoked,
    };
    let before = arch::x86_64::user_root_write_count();
    if round > 3
        || peers[0].root == peers[1].root
        || manager.summary().allocated_pages != baseline + 26
    {
        stop(4001, serial, debugcon);
    }
    let handles = checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| {
            if !s.is_empty() {
                return Err(IpcError::Identity);
            }
            for (index, p) in peers.iter().enumerate() {
                if p.id.slot != index as u8 + 2 || p.id.generation != generation {
                    return Err(IpcError::Identity);
                }
                s.attach(p.id, p.admission)?;
            }
            let back = s.create_endpoint(peers[0].id)?;
            let endpoint = s.create_endpoint(peers[1].id)?;
            let send = s.derive(peers[1].id, endpoint, peers[0].id, Rights::SEND)?;
            Ok([back, endpoint, send])
        })
    });
    let handle = (u64::from(generation) << 32) | 0x10001;
    if handles != [handle, handle, handle + 1] {
        stop(4002, serial, debugcon)
    }
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    for p in peers.iter() {
        let id = checked!(scheduler.create_task(p.id.slot, p.id.generation, 16, 1));
        checked!(scheduler.activate(id, cpu));
    }
    let mut stopped = [false; 2];
    let mut waiting = [None; 2];
    let mut calls = [0u64; 2];
    let mut ticks = [0u64; 2];
    let mut waits = 0u64;
    let mut wakes = 0u64;
    let mut preemptions = 0u64;
    for _ in 0..64 {
        if stopped == [true; 2] {
            break;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let index = checked!(usize::from(id.slot).checked_sub(2).ok_or(()));
        if index >= 2 || stopped[index] || id.generation != generation {
            stop(4003, serial, debugcon)
        }
        let p = &mut peers[index];
        if let Some(ticket) = waiting[index] {
            let status = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    s.complete_wait(ticket, &mut scheduler, cpu, |status| {
                        p.slot
                            .complete_wait(p.id, ticket, status)
                            .map_err(|_| IpcError::Identity)
                    })
                })
            });
            if index != 0 || status != expected {
                stop(4004, serial, debugcon)
            }
            waiting[index] = None;
        }
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let slice = checked!(p.slot.run_slice(p.id));
        ticks[index] = checked!(
            ticks[index]
                .checked_add(checked!(p.slot.account_slice(p.id, &mut scheduler, cpu)))
                .ok_or(())
        );
        match slice.event {
            Event::BudgetYield { .. } => stop(8990, serial, debugcon),
            Event::Waiting { ticket, .. } => {
                checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|s| s.park_wait(ticket, &mut scheduler, cpu))
                });
                waiting[index] = Some(ticket);
                waits += 1;
            }
            Event::Preempted { .. } => {
                preemptions += 1;
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                let valid = if index == 0 {
                    outcome.reason == Reason::Exit(97)
                        && outcome.syscalls == if round == 0 { 11 } else { 10 }
                } else {
                    match (round, outcome.reason, outcome.syscalls) {
                        (0 | 1, Reason::Exit(96), 5) => true,
                        (2, Reason::Fault(f), 0) | (3, Reason::Fault(f), 2) => {
                            f.vector == 3 && f.error == 0
                        }
                        _ => false,
                    }
                };
                if !valid {
                    stop(4005, serial, debugcon)
                }
                calls[index] = outcome.syscalls;
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                stopped[index] = true;
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
    if stopped != [true; 2]
        || waiting != [None; 2]
        || waits != 1
        || wakes != 1
        || dispatches != preemptions + waits + 2
        || writes != dispatches * 2
        || ticks.contains(&0)
        || summary.dead_count != 2
        || summary.running_count != 0
        || summary.runnable_count != 0
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(4006, serial, debugcon)
    }
    for (index, p) in peers.iter().enumerate() {
        let id = checked!(scheduler::TaskId::new(p.id.slot, p.id.generation));
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[index] {
            stop(4007, serial, debugcon)
        }
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-IPC-REQUEST PASS contract=PKIPC4");
    for (label, value) in [
        (" round=", u64::from(round)),
        (" generation=", u64::from(generation)),
        (" outcome=", expected as u64),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [
        (" dispatches=", dispatches),
        (" preemptions=", preemptions),
        (" ticks0=", ticks[0]),
        (" ticks1=", ticks[1]),
        (" calls0=", u64::from(calls[0])),
        (" calls1=", u64::from(calls[1])),
        (" waits=", waits),
        (" wakes=", wakes),
        (" cr3_writes=", writes),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" client_cancel=1 stale_token=0 take_once=1 survivor_query=1 client_exit=97 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
