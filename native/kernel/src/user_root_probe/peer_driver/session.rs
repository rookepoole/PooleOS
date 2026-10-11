//! Opt-in native session; diagnostic fault injections are not part of dispatch.
use super::*;
use poolekernel::user_entry::startup::{Arguments, Program};

static INIT: &[u8] = include_bytes!(env!("POOLEOS_INIT_CODE"));
static COUNTER: &[u8] = include_bytes!(env!("POOLEOS_COUNTER_CODE"));
#[cfg(feature = "development-console")]
static CONSOLE: &[u8] = include_bytes!(env!("POOLEOS_CONSOLE_CODE"));
#[cfg(feature = "development-console-ipc")]
static CLIENT: &[u8] = include_bytes!(env!("POOLEOS_CONSOLE_CLIENT_CODE"));
const TASK_COUNT: usize = if cfg!(feature = "development-console-ipc") {
    4
} else if cfg!(feature = "development-console") {
    3
} else {
    2
};

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
) -> ! {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(value) => value,
                Err(_) => stop(20000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let baseline = manager.summary().allocated_pages;
    let before = arch::x86_64::user_root_write_count();
    let init = checked!(Program::new(INIT, 0));
    let counter = checked!(Program::new(COUNTER, 0));
    #[cfg(feature = "development-console")]
    let console = checked!(Program::new(CONSOLE, 0));
    #[cfg(all(
        feature = "development-console",
        not(feature = "development-console-ipc")
    ))]
    let args2 = checked!(Arguments::new(&[
        b"console",
        if cfg!(feature = "development-console-bad-handle") {
            b"0000000100040002"
        } else {
            b"0000000100040001"
        }
    ]));
    #[cfg(feature = "development-console-ipc")]
    let args2 = checked!(Arguments::new(&[
        b"console-service",
        b"0000000100040001",
        b"0000000100010001",
        b"0000000100010002",
        if cfg!(feature = "development-console-ipc-bad-peer") {
            b"0000000100000000"
        } else {
            b"0000000100000003"
        },
    ]));
    #[cfg(feature = "development-console-ipc")]
    let client = checked!(Program::new(CLIENT, 0));
    #[cfg(feature = "development-console-ipc")]
    let args3 = checked!(Arguments::new(&[
        b"console-client",
        b"0000000100010001",
        b"0000000100010002",
        b"0000000100000002",
    ]));
    let args0 = checked!(Arguments::new(&[
        b"init",
        b"0000000100010001",
        b"0000000100010002"
    ]));
    let counter_role: &[u8] = if cfg!(feature = "development-session-bad-startup") {
        b"invalid"
    } else {
        b"counter"
    };
    let args1 = checked!(Arguments::new(&[
        counter_role,
        b"0000000100010001",
        b"0000000100010002"
    ]));
    let mut peers = [
        checked!(Peer::new_program(
            0, &init, &args0, handoff, core, bits, manager, topology, hpet
        )),
        checked!(Peer::new_program(
            1, &counter, &args1, handoff, core, bits, manager, topology, hpet
        )),
        #[cfg(feature = "development-console")]
        checked!(Peer::new_program(
            2, &console, &args2, handoff, core, bits, manager, topology, hpet
        )),
        #[cfg(feature = "development-console-ipc")]
        checked!(Peer::new_program(
            3, &client, &args3, handoff, core, bits, manager, topology, hpet
        )),
    ];
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    #[cfg(not(feature = "development-console"))]
    let grants = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap(
            [
                (peers[0].id, peers[0].admission),
                (peers[1].id, peers[1].admission),
            ],
            &mut scheduler,
        )
    });
    #[cfg(all(
        feature = "development-console",
        not(feature = "development-console-ipc")
    ))]
    let grants = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap_console(
            core::array::from_fn(|i| (peers[i].id, peers[i].admission)),
            &mut scheduler,
        )
    });
    #[cfg(feature = "development-console-ipc")]
    let grants = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap_console_ipc(
            core::array::from_fn(|i| (peers[i].id, peers[i].admission)),
            &mut scheduler,
        )
    });
    // Prepared strings are only locators. Authenticate the actual granted handles
    // before either task can run; never manufacture authority from argument text.
    if grants[..4] != [0x100010001, 0x100010001, 0x100010002, 0x100010002]
        || peers[0].root == peers[1].root
        || manager.summary().allocated_pages != baseline + 13 * TASK_COUNT as u64
    {
        stop(20001, serial, debugcon);
    }
    #[cfg(all(
        feature = "development-console",
        not(feature = "development-console-ipc")
    ))]
    if grants[4] != 0x100040001 || peers[2].root == peers[0].root || peers[2].root == peers[1].root
    {
        stop(20005, serial, debugcon);
    }
    #[cfg(feature = "development-console-ipc")]
    if grants[4..]
        != [
            0x100010001,
            0x100010001,
            0x100010002,
            0x100010002,
            0x100040001,
        ]
        || peers
            .iter()
            .enumerate()
            .any(|(i, p)| peers[..i].iter().any(|q| p.root == q.root))
        || peers
            .iter()
            .enumerate()
            .any(|(i, p)| usize::from(p.id.slot) != i || p.id.generation != 1)
    {
        stop(20006, serial, debugcon);
    }
    {
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        #[cfg(not(feature = "development-console"))]
        log.write_str("POOLEOS:SESSION START contract=PSESSION1 programs=2 bootstrap=PSTART1 abi=PSABI1 init_bytes=");
        #[cfg(all(feature = "development-console", not(feature = "development-console-ipc")))]
        log.write_str("POOLEOS:SESSION START contract=PSESSION2 programs=3 bootstrap=PSTART1 abi=PSABI1 init_bytes=");
        #[cfg(feature = "development-console-ipc")]
        log.write_str("POOLEOS:SESSION START contract=PSESSION3 programs=4 bootstrap=PSTART1 abi=PSABI1 init_bytes=");
        log.write_decimal_u64(INIT.len() as u64);
        log.write_str(" counter_bytes=");
        log.write_decimal_u64(COUNTER.len() as u64);
        #[cfg(feature = "development-console")]
        {
            log.write_str(" console_bytes=");
            log.write_decimal_u64(CONSOLE.len() as u64);
        }
        #[cfg(feature = "development-console-ipc")]
        {
            log.write_str(" client_bytes=");
            log.write_decimal_u64(CLIENT.len() as u64);
        }
        for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
            log.write_str(label);
            log.write_hex_u64(value);
        }
        #[cfg(not(feature = "development-console"))]
        log.write_str(" granted_handles=4 diagnostics=0 production=0\n");
        #[cfg(feature = "development-console")]
        {
            log.write_str(" root2=");
            log.write_hex_u64(peers[2].root);
            #[cfg(not(feature = "development-console-ipc"))]
            log.write_str(" granted_handles=5 port=COM2 irq=0 diagnostics=0 production=0\n");
            #[cfg(feature = "development-console-ipc")]
            {
                log.write_str(" root3=");
                log.write_hex_u64(peers[3].root);
                log.write_str(" task_image_pages=52 firmware_pages=");
                log.write_decimal_u64(baseline);
                log.write_str(
                    " granted_handles=9 protocol=PCS1 port=COM2 irq=0 diagnostics=0 production=0\n",
                );
            }
        }
    }
    let mut waiting = [None; TASK_COUNT];
    let mut dead = [false; TASK_COUNT];
    let mut calls = [0u64; TASK_COUNT];
    let mut ticks = [0u64; TASK_COUNT];
    let mut waits = 0u64;
    let mut wakes = 0u64;
    let mut preemptions = 0u64;
    let mut yields = 0u64;
    loop {
        let id = checked!(scheduler.dispatch(cpu));
        let index = usize::from(id.slot);
        if index >= TASK_COUNT || dead[index] || peers[index].id.generation != id.generation {
            stop(20002, serial, debugcon);
        }
        let p = &mut peers[index];
        if let Some(ticket) = waiting[index] {
            checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|space| {
                    space.complete_wait(ticket, &mut scheduler, cpu, |status| {
                        p.slot
                            .complete_wait(p.id, ticket, status)
                            .map_err(|_| poolekernel::capability_ipc::Error::Identity)
                    })
                })
            });
            waiting[index] = None;
        }
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let result = p.slot.run_slice(p.id);
        // Settle even a failed quantum before handling its result; retained failure
        // owners are never freed on this fail-closed path.
        let elapsed = checked!(p.slot.account_slice(p.id, &mut scheduler, cpu));
        ticks[index] = checked!(ticks[index].checked_add(elapsed).ok_or(()));
        let slice = checked!(result);
        match slice.event {
            Event::Waiting { ticket, syscalls } => {
                calls[index] = syscalls;
                checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|space| {
                        space.park_wait(ticket, &mut scheduler, cpu)
                    })
                });
                waiting[index] = Some(ticket);
                waits = checked!(waits.checked_add(1).ok_or(()));
            }
            Event::Preempted { syscalls, .. } => {
                calls[index] = syscalls;
                preemptions = checked!(preemptions.checked_add(1).ok_or(()));
                checked!(scheduler.yield_current(cpu));
            }
            Event::BudgetYield { syscalls } => {
                calls[index] = syscalls;
                yields = checked!(yields.checked_add(1).ok_or(()));
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                calls[index] = u64::from(outcome.syscalls);
                // Revoke endpoints and wake dependent tasks before destroying memory.
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                dead[index] = true;
                let mut log = EarlyLogger::new(BootSink {
                    serial,
                    debugcon,
                    ring: &EARLY_RING,
                });
                log.write_str("POOLEOS:SESSION STOP task=");
                log.write_decimal_u64(index as u64);
                match outcome.reason {
                    Reason::Exit(code) => {
                        log.write_str(" reason=exit value=");
                        log.write_decimal_u64(u64::from(code));
                    }
                    Reason::Fault(fault) => {
                        log.write_str(" reason=fault value=");
                        log.write_decimal_u64(fault.vector);
                    }
                    _ => log.write_str(" reason=other value=0"),
                }
                log.write_str(" authority_revoked=1 image_reaped=1 production=0\n");
            }
        }
        // This fixed bootstrap pair has an explicit mutual dependency. An owned
        // receive endpoint can remain valid after its only service peer dies;
        // cancel that dependent wait instead of pretending readiness implies EOF.
        // General service supervision belongs in user space and is not provided here.
        for dependent in 0..2 {
            if dead[1 - dependent] && !dead[dependent] {
                if let Some(ticket) = waiting[dependent] {
                    let task = checked!(scheduler::TaskId::new(
                        peers[dependent].id.slot,
                        peers[dependent].id.generation,
                    ));
                    if checked!(scheduler.task_snapshot(task)).state
                        == scheduler::TaskState::Blocked
                    {
                        checked!(unsafe {
                            arch::x86_64::user_ipc::with_waits(|space| {
                                space.cancel_wait(ticket, &mut scheduler, cpu)
                            })
                        });
                    }
                }
            }
        }
        wakes = checked!(
            wakes
                .checked_add(u64::from(checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|space| {
                        space.poll_wakes(&mut scheduler, cpu)
                    })
                })))
                .ok_or(())
        );
        checked!(scheduler.validate());
        let summary = scheduler.summary();
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[index]
            || unsafe { arch::x86_64::read_cr3() } != core.page_table_root_physical
            || arch::x86_64::user::active()
        {
            stop(20003, serial, debugcon);
        }
        if dead == [true; TASK_COUNT] {
            if manager.summary().allocated_pages != baseline
                || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
                || waiting != [None; TASK_COUNT]
            {
                stop(20004, serial, debugcon);
            }
            let mut log = EarlyLogger::new(BootSink {
                serial,
                debugcon,
                ring: &EARLY_RING,
            });
            log.write_str("POOLEOS:SESSION EMPTY tasks=0 objects=0 released_pages=");
            log.write_decimal_u64(13 * TASK_COUNT as u64);
            log.write_str(" kernel_alive=1 production=0\n");
            // No restart/supervision policy exists yet. Keep the quiescent kernel
            // resident; this is not a usable shell or a healthy service session.
            halt_forever();
        }
        let dispatches = u64::from(summary.dispatch_count);
        if dispatches.is_multiple_of(64) {
            let mut log = EarlyLogger::new(BootSink {
                serial,
                debugcon,
                ring: &EARLY_RING,
            });
            log.write_str("POOLEOS:SESSION RUN");
            for (label, value) in [
                (" dispatches=", dispatches),
                (" calls0=", calls[0]),
                (" calls1=", calls[1]),
                (" ticks0=", ticks[0]),
                (" ticks1=", ticks[1]),
                (" waits=", waits),
                (" wakes=", wakes),
                (" preemptions=", preemptions),
                (" yields=", yields),
                (
                    " cr3_writes=",
                    arch::x86_64::user_root_write_count() - before,
                ),
            ] {
                log.write_str(label);
                log.write_decimal_u64(value);
            }
            #[cfg(feature = "development-console")]
            for (label, value) in [
                (" calls2=", calls[2]),
                (" ticks2=", ticks[2]),
                (" console_dead=", u64::from(dead[2])),
                (
                    " allocated_pages=",
                    manager.summary().allocated_pages - baseline,
                ),
            ] {
                log.write_str(label);
                log.write_decimal_u64(value);
            }
            #[cfg(feature = "development-console-ipc")]
            for (label, value) in [
                (" calls3=", calls[3]),
                (" ticks3=", ticks[3]),
                (" client_dead=", u64::from(dead[3])),
            ] {
                log.write_str(label);
                log.write_decimal_u64(value);
            }
            log.write_str(" cpl=3 kernel_root_restored=1 production=0\n");
        }
    }
}
