//! Both tasks park; real HPET expiry wakes the caller before the late reply attempt.
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
    clock: &mut clock_driver::Session,
    manager: &mut PhysicalMemoryManager,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(6000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let generation = round + 11;
    let before = arch::x86_64::user_root_write_count();
    if round > 1
        || peers[0].root == peers[1].root
        || manager.summary().allocated_pages != baseline + 26
    {
        stop(6001, serial, debugcon);
    }
    let handles = checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| {
            if !s.is_empty() {
                return Err(IpcError::Identity);
            }
            for (i, p) in peers.iter().enumerate() {
                if p.id.slot != i as u8 + 2 || p.id.generation != generation {
                    return Err(IpcError::Identity);
                }
                s.attach(p.id, p.admission)?;
            }
            let back = s.create_endpoint(peers[0].id)?;
            let endpoint = s.create_endpoint(peers[1].id)?;
            let park = s.create_endpoint(peers[1].id)?;
            let send = s.derive(peers[1].id, endpoint, peers[0].id, Rights::SEND)?;
            let wake = s.derive(peers[1].id, park, peers[0].id, Rights::SEND)?;
            let ack = s.derive(peers[0].id, back, peers[1].id, Rights::SEND)?;
            Ok([back, endpoint, park, send, wake, ack])
        })
    });
    let base = (u64::from(generation) << 32) | 0x10001;
    let control = u64::from(round + 6) << 32;
    if handles
        != [
            base,
            base,
            control | 0x10002,
            base + 1,
            (u64::from(round + 1) << 32) | 0x10003,
            control | 0x10003,
        ]
    {
        stop(6002, serial, debugcon);
    }
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    for p in peers.iter() {
        let id = checked!(scheduler.create_task(p.id.slot, p.id.generation, 16, 1));
        checked!(scheduler.activate(id, cpu));
    }
    let mut stopped = [false; 2];
    let mut waiting = [None; 2];
    let mut calls = [0u32; 2];
    let mut ticks = [0u64; 2];
    let mut waits = 0u64;
    let mut wakes = 0u64;
    let mut idle_expiries = 0u64;
    let mut expiry_ns = 0;
    for _ in 0..32 {
        if stopped == [true; 2] {
            break;
        }
        if scheduler.summary().runnable_count == 0 {
            if scheduler.summary().blocked_count != 2
                || waiting.iter().any(Option::is_none)
                || idle_expiries != 0
            {
                stop(6003, serial, debugcon);
            }
            expiry_ns = checked!(clock.expire_idle());
            let n = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| s.poll_wakes(&mut scheduler, cpu))
            });
            if n != 1 {
                stop(6004, serial, debugcon);
            }
            wakes += u64::from(n);
            idle_expiries += 1;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let index = checked!(usize::from(id.slot).checked_sub(2).ok_or(()));
        if index >= 2 || stopped[index] || id.generation != generation {
            stop(6005, serial, debugcon);
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
            let expected = if index == 0 && waits == 2 {
                Status::TimedOut
            } else {
                Status::Ok
            };
            if status != expected {
                stop(6006, serial, debugcon);
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
            Event::Waiting { ticket, .. } => {
                checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|s| s.park_wait(ticket, &mut scheduler, cpu))
                });
                waiting[index] = Some(ticket);
                waits += 1;
            }
            Event::Preempted { .. } => stop(6007, serial, debugcon),
            Event::Terminated(outcome) => {
                if outcome.reason != Reason::Exit(if index == 0 { 98 } else { 99 })
                    || outcome.syscalls != if index == 0 { 9 } else { 5 }
                {
                    let (reason, value, instruction) = match outcome.reason {
                        Reason::Exit(code) => (0, u64::from(code), 0),
                        Reason::Fault(f) => (1, f.vector, f.instruction),
                        _ => (2, 0, 0),
                    };
                    let mut log = EarlyLogger::new(BootSink {
                        serial,
                        debugcon,
                        ring: &EARLY_RING,
                    });
                    log.write_str("POOLEOS:KERNEL:USER-DEADLINE DENIED");
                    for (label, value) in [
                        (" round=", u64::from(round)),
                        (" task=", index as u64),
                        (" calls=", u64::from(outcome.syscalls)),
                        (" reason=", reason),
                        (" value=", value),
                        (" instruction=", instruction),
                        (" waits=", waits),
                        (" wakes=", wakes),
                        (" idle=", idle_expiries),
                    ] {
                        log.write_str(label);
                        log.write_decimal_u64(value);
                    }
                    log.write_str("\n");
                    stop(6008, serial, debugcon);
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
    let writes = arch::x86_64::user_root_write_count() - before;
    if stopped != [true; 2]
        || waiting != [None; 2]
        || waits != 3
        || wakes != 3
        || idle_expiries != 1
        || summary.dispatch_count != 5
        || writes != 10
        || ticks.contains(&0)
        || summary.dead_count != 2
        || summary.running_count != 0
        || summary.runnable_count != 0
        || summary.blocked_count != 0
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(6009, serial, debugcon);
    }
    for (index, p) in peers.iter().enumerate() {
        let id = checked!(scheduler::TaskId::new(p.id.slot, p.id.generation));
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[index] {
            stop(6010, serial, debugcon);
        }
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-IPC-DEADLINE PASS contract=PKIPC5");
    for (label, value) in [
        (" round=", u64::from(round)),
        (" generation=", u64::from(generation)),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [
        (" ticks0=", ticks[0]),
        (" ticks1=", ticks[1]),
        (" expiry_ns=", expiry_ns),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" epoch=2 timeout_ns=100000000 dispatches=5 preemptions=0 waits=3 wakes=3 idle_expiries=1 all_blocked=2 late_reply_denied=1 completion_retained=1 calls0=9 calls1=5 client_exit=98 server_exit=99 cr3_writes=10 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
