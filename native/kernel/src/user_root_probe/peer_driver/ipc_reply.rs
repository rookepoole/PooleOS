//! Actual user-owned one-use replies without a permanent server SEND grant.
use super::*;
use poolekernel::{
    capability_ipc::{Error as IpcError, Rights},
    user_entry::syscall::Status,
};

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
                Err(_) => stop(3000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let before = arch::x86_64::user_root_write_count();
    if peers[0].root == peers[1].root || manager.summary().allocated_pages != baseline + 26 {
        stop(3001, serial, debugcon);
    }
    let handles = checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| {
            if !s.is_empty() {
                return Err(IpcError::Identity);
            }
            for (index, p) in peers.iter().enumerate() {
                if p.id.slot != index as u8 + 2 || p.id.generation != 6 {
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
    if handles != [0x600010001, 0x600010001, 0x600010002] {
        stop(3002, serial, debugcon);
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
        if index >= 2 || stopped[index] || id.generation != 6 {
            stop(3003, serial, debugcon);
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
            if status != Status::Ok {
                stop(3004, serial, debugcon);
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
                if outcome.reason != Reason::Exit(if index == 0 { 95 } else { 94 })
                    || outcome.syscalls != if index == 0 { 8 } else { 11 }
                {
                    stop(3005, serial, debugcon);
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
        stop(3006, serial, debugcon);
    }
    for (index, p) in peers.iter().enumerate() {
        let id = checked!(scheduler::TaskId::new(p.id.slot, p.id.generation));
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[index] {
            stop(3007, serial, debugcon);
        }
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-IPC-REPLY PASS contract=PKIPC3 generation=6 endpoints=2 handles=3 sender_client=2 sender_server=3 reply_generations=2 reply_consumed=1 reply_discarded=1 replay_denied=2 unminted_denied=1 cross_owner_denied=1 wrong_type_denied=1 request_rights_denied=1 output_prefix=8 input_fault=1 transformed=1");
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
    log.write_str(" client_exit=95 server_exit=94 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
