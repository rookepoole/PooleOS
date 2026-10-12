//! PLAUNCH1 adapter: actual independently compiled supervisor chooses restarts.
use super::*;
use poolekernel::{
    capability_ipc::admission::Member,
    user_entry::startup::{Arguments, Program},
};
static SUPERVISOR: &[u8] = include_bytes!(env!("POOLEOS_SUPERVISOR_CODE"));

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
                Err(_) => stop(32000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let bad = cfg!(feature = "development-process-launch-bad-owner");
    let baseline = manager.summary().allocated_pages;
    let before = arch::x86_64::user_root_write_count();
    let program = checked!(Program::new(SUPERVISOR, 0));
    let arguments = checked!(Arguments::new(&[
        b"supervisor",
        if bad {
            b"0000000200060001"
        } else {
            b"0000000100060001"
        },
        b"0000000000000002"
    ]));
    let mut peers = [
        checked!(Peer::new_with_arguments(
            0,
            26,
            [256, 1, 0, 0, 0, 0],
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            timer_driver::Probe::None,
            false
        )),
        checked!(Peer::new_program(
            1, &program, &arguments, handoff, core, bits, manager, topology, hpet
        )),
        checked!(Peer::new_with_arguments(
            2,
            26,
            [8192, 1, 0, 0, 0, 0],
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
    if baseline > 12
        || manager.summary().allocated_pages != baseline + 39
        || peers
            .iter()
            .enumerate()
            .any(|(i, p)| peers[..i].iter().any(|q| q.root == p.root))
    {
        stop(32001, serial, debugcon);
    }
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| {
            if !s.is_empty() {
                return Err(poolekernel::capability_ipc::Error::Identity);
            }
            s.admit(
                &mut scheduler,
                &[1, 2].map(|i| Member {
                    id: peers[i].id,
                    image: peers[i].admission,
                    priority: 16,
                }),
                &[],
            )
            .map_err(|_| poolekernel::capability_ipc::Error::Identity)?;
            if s.grant_launch(peers[1].id, 1, 0)? != 0x100060001 {
                return Err(poolekernel::capability_ipc::Error::Identity);
            }
            Ok(())
        })
    });
    record(
        serial,
        debugcon,
        "START",
        &[
            ("bad_owner", u64::from(bad)),
            ("supervisor_bytes", SUPERVISOR.len() as u64),
            ("root0", peers[0].root),
            ("root1", peers[1].root),
            ("root2", peers[2].root),
            ("image_pages", 39),
            ("firmware_pages", baseline),
        ],
    );
    let mut launched = 0u32;
    let mut retired = 0u32;
    let mut dead = [false; 3];
    let mut ticks = [0u64; 3];
    let mut lifetime_ticks = [0u64; 3];
    let mut calls = [0u64; 3];
    let mut survivor_after_restart = 0u64;
    let mut owner_exit = u32::MAX;
    let mut prepared_cancelled = 0u64;
    for _ in 0..512 {
        let id = checked!(scheduler.dispatch(cpu));
        let i = usize::from(id.slot);
        if i >= 3 || dead[i] || id.generation != peers[i].id.generation {
            stop(32002, serial, debugcon);
        }
        let p = &mut peers[i];
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let result = p.slot.run_slice(p.id);
        let charged = checked!(p.slot.account_slice(p.id, &mut scheduler, cpu));
        ticks[i] += charged;
        lifetime_ticks[i] += charged;
        let runtime = checked!(p.slot.runtime(p.id));
        if runtime.unknown
            || runtime.charged_ticks != lifetime_ticks[i]
            || checked!(scheduler.task_snapshot(id)).runtime_ticks != lifetime_ticks[i]
        {
            stop(32018, serial, debugcon);
        }
        let slice = checked!(result);
        if i == 2 && launched == 2 {
            survivor_after_restart += 1;
        }
        match slice.event {
            Event::BudgetYield { .. } | Event::Preempted { .. } => {
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                let expected = if i == 1 {
                    if bad { 170 } else { 0 }
                } else {
                    100
                };
                if outcome.reason != Reason::Exit(expected) {
                    stop(32003, serial, debugcon);
                }
                calls[i] += u64::from(outcome.syscalls);
                let pages = manager.summary().allocated_pages;
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                dead[i] = true;
                if pages - manager.summary().allocated_pages != 13 {
                    stop(32004, serial, debugcon);
                }
                if i == 0 {
                    retired += 1;
                    if outcome.syscalls != 257 || retired != launched {
                        stop(32005, serial, debugcon);
                    }
                    record(
                        serial,
                        debugcon,
                        "RETIRED",
                        &[
                            ("sequence", u64::from(retired)),
                            ("child_generation", u64::from(p.id.generation)),
                            ("calls", outcome.syscalls),
                            ("released_pages", 13),
                            ("scrubbed_data_pages", 6),
                        ],
                    );
                } else if i == 1 {
                    owner_exit = expected;
                    if bad {
                        if launched != 0
                            || retired != 0
                            || peers[0].slot.state(peers[0].id) != Ok(task::State::Prepared)
                        {
                            stop(32006, serial, debugcon);
                        }
                        let p = &mut peers[0];
                        let pages = manager.summary().allocated_pages;
                        let parts = checked!(p.slot.abandon(p.id, manager, &mut p.memory));
                        checked!(p.release(manager, parts));
                        if pages - manager.summary().allocated_pages != 13 {
                            stop(32008, serial, debugcon);
                        }
                        dead[0] = true;
                        prepared_cancelled = 1;
                        record(
                            serial,
                            debugcon,
                            "CANCELLED",
                            &[
                                ("prepared", 1),
                                ("calls", 0),
                                ("released_pages", 13),
                                ("scrubbed_data_pages", 6),
                            ],
                        );
                    } else if retired != 2 {
                        stop(32009, serial, debugcon);
                    }
                }
            }
            Event::Waiting { .. } => stop(32010, serial, debugcon),
        }
        if unsafe { arch::x86_64::read_cr3() } != core.page_table_root_physical
            || arch::x86_64::user::active()
            || arch::x86_64::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
        {
            stop(32011, serial, debugcon);
        }
        if let Some(permit) =
            checked!(unsafe { arch::x86_64::user_ipc::with_waits(|s| Ok(s.claim_launch())) })
        {
            let plan = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| s.validate_launch(&permit))
            });
            if bad
                || launched >= 2
                || plan.owner != peers[1].id
                || plan.program != 1
                || plan.child_slot != 0
                || plan.sequence != launched + 1
            {
                stop(32012, serial, debugcon);
            }
            let p = &mut peers[0];
            if launched == 0 {
                if p.slot.state(p.id) != Ok(task::State::Prepared) {
                    stop(32013, serial, debugcon);
                }
            } else {
                if !dead[0]
                    || retired != launched
                    || p.slot.state(p.id) != Err(task::Error::Missing)
                {
                    stop(32014, serial, debugcon);
                }
                checked!(p.restart(
                    26,
                    [256, 1, 0, 0, 0, 0],
                    handoff,
                    core,
                    bits,
                    manager,
                    topology,
                    hpet,
                    timer_driver::Probe::None
                ));
            }
            let admitted = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    s.admit_launch(
                        &permit,
                        &mut scheduler,
                        Member {
                            id: p.id,
                            image: p.admission,
                            priority: 16,
                        },
                        &[],
                    )
                    .map_err(|_| poolekernel::capability_ipc::Error::Identity)
                })
            });
            launched += 1;
            lifetime_ticks[0] = 0;
            dead[0] = false;
            if admitted.count != 1
                || admitted.handles[0] != (u64::from(launched) << 32) | 0x50001
                || p.id.generation != launched
            {
                stop(32015, serial, debugcon);
            }
            if checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    Ok(s.validate_launch(&permit).is_ok() || s.claim_launch().is_some())
                })
            }) {
                stop(32016, serial, debugcon);
            }
            record(
                serial,
                debugcon,
                "ADMITTED",
                &[
                    ("sequence", u64::from(launched)),
                    ("child_generation", u64::from(p.id.generation)),
                    ("root", p.root),
                    ("handle", admitted.handles[0]),
                    ("owned_pages", 13),
                ],
            );
        }
        if dead.iter().all(|v| *v) {
            break;
        }
    }
    let summary = scheduler.summary();
    let dispatches = u64::from(summary.dispatch_count);
    let writes = arch::x86_64::user_root_write_count() - before;
    if !dead.iter().all(|v| *v)
        || calls[2] != 8193
        || calls[0] != if bad { 0 } else { 514 }
        || ticks[1] == 0
        || ticks[2] == 0
        || (!bad && (ticks[0] == 0 || survivor_after_restart == 0))
        || writes != 2 * dispatches
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::with_waits(|s| Ok(s.is_empty())) })
    {
        stop(32017, serial, debugcon);
    }
    checked!(scheduler.validate());
    record(
        serial,
        debugcon,
        "RESULT",
        &[
            ("launched", u64::from(launched)),
            ("retired", u64::from(retired)),
            ("prepared_cancelled", prepared_cancelled),
            ("supervisor_exit", u64::from(owner_exit)),
            ("supervisor_calls", calls[1]),
            ("child_calls", calls[0]),
            ("survivor_calls", calls[2]),
            ("survivor_after_restart", survivor_after_restart),
            ("ticks0", ticks[0]),
            ("ticks1", ticks[1]),
            ("ticks2", ticks[2]),
            ("dispatches", dispatches),
            ("cr3_writes", writes),
            ("released_pages", if bad { 39 } else { 52 }),
            ("scrubbed_data_pages", if bad { 18 } else { 24 }),
            ("objects_remaining", 0),
        ],
    );
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str(
        "POOLEOS:KERNEL:LAUNCH-END PASS contract=PLAUNCH1 cpl=3 production=0 terminal=halt\n",
    );
    halt_forever();
}

fn record(serial: &mut Com1, debugcon: &mut DebugCon, event: &str, fields: &[(&str, u64)]) {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:LAUNCH-");
    log.write_str(event);
    log.write_str(" PASS contract=PLAUNCH1");
    for (name, value) in fields {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(*value);
    }
    log.write_str("\n");
}
