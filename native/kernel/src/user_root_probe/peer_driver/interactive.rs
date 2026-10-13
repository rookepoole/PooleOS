//! Opt-in shell integration. Commands and restart decisions remain in CPL3.
use super::*;
use poolekernel::{
    capability_ipc::admission::Member,
    user_entry::startup::{Arguments, Program},
};

static INIT: &[u8] = include_bytes!(env!("POOLEOS_INIT_CODE"));
static COUNTER: &[u8] = include_bytes!(env!("POOLEOS_COUNTER_CODE"));
static CONSOLE: &[u8] = include_bytes!(env!("POOLEOS_CONSOLE_CODE"));
static SHELL: &[u8] = include_bytes!(env!("POOLEOS_CONSOLE_CLIENT_CODE"));
static WORKER: &[u8] = include_bytes!(env!("POOLEOS_WORKER_CODE"));

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
                Ok(v) => v,
                Err(_) => stop(34000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let bad = cfg!(feature = "development-shell-process-bad-owner");
    let baseline = manager.summary().allocated_pages;
    let before = arch::x86_64::user_root_write_count();
    let programs =
        [INIT, COUNTER, CONSOLE, SHELL, WORKER, WORKER].map(|code| checked!(Program::new(code, 0)));
    let args = [
        checked!(Arguments::new(&[
            b"init",
            b"0000000100010001",
            b"0000000100010002"
        ])),
        checked!(Arguments::new(&[
            b"counter",
            b"0000000100010001",
            b"0000000100010002"
        ])),
        checked!(Arguments::new(&[
            b"console-service",
            b"0000000100040001",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000003"
        ])),
        checked!(Arguments::new(&[
            b"control-shell",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000002",
            b"0000000100060001",
            if bad {
                b"0000000200060002"
            } else {
                b"0000000100060002"
            }
        ])),
        checked!(Arguments::new(&[b"worker"])),
        checked!(Arguments::new(&[b"fault"])),
    ];
    // Fill one retained owner at a time; neither from_fn nor a six-value literal
    // may keep a second full image array live during nested construction.
    let mut storage: [Option<Peer>; 6] = [const { None }; 6];
    for i in 0..6 {
        storage[i] = Some(checked!(Peer::new_program(
            i as u8,
            &programs[i],
            &args[i],
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet
        )));
    }
    let mut peers = storage
        .each_mut()
        .map(|slot| slot.as_mut().expect("initialized peer"));
    let pages = programs.each_ref().map(|p| 12 + p.code_pages());
    let total: u64 = pages.iter().sum();
    if baseline > 12
        || manager.summary().allocated_pages != baseline + total
        || peers
            .iter()
            .enumerate()
            .any(|(i, p)| peers[..i].iter().any(|q| p.root == q.root))
    {
        stop(34001, serial, debugcon);
    }
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    let grants = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap_console_ipc(
            core::array::from_fn(|i| (peers[i].id, peers[i].admission)),
            &mut scheduler,
        )
    });
    if grants
        != [
            0x100010001,
            0x100010001,
            0x100010002,
            0x100010002,
            0x100010001,
            0x100010001,
            0x100010002,
            0x100010002,
            0x100040001,
        ]
    {
        stop(34002, serial, debugcon);
    }
    checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| {
            if s.grant_launch(peers[3].id, 1, 4)? != 0x100060001
                || s.grant_launch(peers[3].id, 2, 5)? != 0x100060002
            {
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
            ("init_bytes", INIT.len() as u64),
            ("counter_bytes", COUNTER.len() as u64),
            ("console_bytes", CONSOLE.len() as u64),
            ("shell_bytes", SHELL.len() as u64),
            ("worker_bytes", WORKER.len() as u64),
            ("image_pages", total),
            ("firmware_pages", baseline),
            ("root0", peers[0].root),
            ("root1", peers[1].root),
            ("root2", peers[2].root),
            ("root3", peers[3].root),
            ("root4", peers[4].root),
            ("root5", peers[5].root),
        ],
    );
    let mut live = [true, true, true, true, false, false];
    let mut owned = [true; 6];
    let mut waiting = [None; 6];
    let mut calls = [0u64; 6];
    let mut ticks = [0u64; 6];
    let mut generations = [0u32; 2];
    let mut extra_flushes = 0;
    let mut retired = 0;
    let mut cancelled = 0;
    loop {
        let id = checked!(scheduler.dispatch(cpu));
        let i = usize::from(id.slot);
        if i >= 6 || !live[i] || peers[i].id.generation != id.generation {
            stop(34003, serial, debugcon);
        }
        let p = &mut peers[i];
        if let Some(ticket) = waiting[i] {
            checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    s.complete_wait(ticket, &mut scheduler, cpu, |status| {
                        p.slot
                            .complete_wait(p.id, ticket, status)
                            .map_err(|_| poolekernel::capability_ipc::Error::Identity)
                    })
                })
            });
            waiting[i] = None;
        }
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let result = p.slot.run_slice(p.id);
        ticks[i] = checked!(
            ticks[i]
                .checked_add(checked!(p.slot.account_slice(p.id, &mut scheduler, cpu)))
                .ok_or(())
        );
        let slice = checked!(result);
        match slice.event {
            Event::Waiting { ticket, syscalls } => {
                calls[i] = syscalls;
                checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|s| s.park_wait(ticket, &mut scheduler, cpu))
                });
                waiting[i] = Some(ticket);
            }
            Event::Preempted { syscalls, .. } | Event::BudgetYield { syscalls } => {
                calls[i] = syscalls;
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                calls[i] = outcome.syscalls;
                if i < 2 || (i < 4 && outcome.reason != Reason::Exit(0)) {
                    stop(34004, serial, debugcon);
                }
                checked!(retire(
                    p,
                    outcome,
                    false,
                    manager,
                    &mut scheduler,
                    pages[i],
                    i >= 4
                ));
                live[i] = false;
                owned[i] = false;
                retired += 1;
                retirement(
                    serial,
                    debugcon,
                    outcome,
                    pages[i],
                    scheduler.summary().dispatch_count,
                );
            }
        }
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[i] {
            stop(34005, serial, debugcon);
        }
        if let Some(permit) =
            checked!(unsafe { arch::x86_64::user_ipc::with_waits(|s| Ok(s.claim_process_stop())) })
        {
            let target = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| s.validate_process_stop(&permit))
            });
            let j = usize::from(target.slot);
            if !(4..6).contains(&j) || !live[j] || peers[j].id != target {
                stop(34006, serial, debugcon);
            }
            let p = &mut peers[j];
            let prepared = checked!(p.slot.state(p.id)) == task::State::Prepared;
            let outcome = if prepared {
                task::Outcome {
                    id: p.id,
                    root: p.root,
                    reason: Reason::Cancelled,
                    syscalls: 0,
                }
            } else if let Some(ticket) = waiting[j] {
                checked!(p.slot.cancel_waiting(p.id, ticket))
            } else {
                checked!(p.slot.cancel_suspended(p.id))
            };
            let flushes = arch::x86_64::user_root_write_count();
            checked!(retire(
                p,
                outcome,
                prepared,
                manager,
                &mut scheduler,
                pages[j],
                true
            ));
            if arch::x86_64::user_root_write_count() - flushes != u64::from(!prepared) {
                stop(34007, serial, debugcon);
            }
            extra_flushes += u64::from(!prepared);
            if checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| Ok(s.validate_process_stop(&permit).is_ok()))
            }) {
                stop(34008, serial, debugcon);
            }
            waiting[j] = None;
            live[j] = false;
            owned[j] = false;
            calls[j] = outcome.syscalls;
            retired += 1;
            retirement(
                serial,
                debugcon,
                outcome,
                pages[j],
                scheduler.summary().dispatch_count,
            );
        }
        if let Some(permit) =
            checked!(unsafe { arch::x86_64::user_ipc::with_waits(|s| Ok(s.claim_launch())) })
        {
            let plan = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| s.validate_launch(&permit))
            });
            let j = usize::from(plan.child_slot);
            if !(4..6).contains(&j)
                || plan.owner != peers[3].id
                || !live[3]
                || live[j]
                || plan.program != (j - 3) as u16
                || plan.sequence != checked!(generations[j - 4].checked_add(1).ok_or(()))
            {
                stop(34009, serial, debugcon);
            }
            let p = &mut peers[j];
            if generations[j - 4] == 0 {
                if !owned[j] || p.slot.state(p.id) != Ok(task::State::Prepared) {
                    stop(34010, serial, debugcon);
                }
            } else {
                if owned[j] || p.slot.state(p.id) != Err(task::Error::Missing) {
                    stop(34011, serial, debugcon);
                }
                checked!(p.restart_program(
                    &programs[j],
                    &args[j],
                    handoff,
                    core,
                    bits,
                    manager,
                    topology,
                    hpet
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
            if admitted.count != 1
                || p.id.generation != plan.sequence
                || checked!(unsafe {
                    arch::x86_64::user_ipc::with_waits(|s| Ok(s.validate_launch(&permit).is_ok()))
                })
            {
                stop(34012, serial, debugcon);
            }
            generations[j - 4] = plan.sequence;
            ticks[j] = 0;
            calls[j] = 0;
            live[j] = true;
            owned[j] = true;
            record(
                serial,
                debugcon,
                "ADMIT",
                &[
                    ("task", j as u64),
                    ("generation", u64::from(p.id.generation)),
                    ("sequence", u64::from(plan.sequence)),
                    ("handle", admitted.handles[0]),
                    ("root", p.root),
                    ("owned_pages", pages[j]),
                    ("dispatches", u64::from(scheduler.summary().dispatch_count)),
                ],
            );
        }
        if !live[3] {
            if live[4] || live[5] {
                stop(34013, serial, debugcon);
            }
            for j in 4..6 {
                if !owned[j] {
                    continue;
                }
                let p = &mut peers[j];
                if generations[j - 4] != 0 || p.slot.state(p.id) != Ok(task::State::Prepared) {
                    stop(34014, serial, debugcon);
                }
                let previous = manager.summary().allocated_pages;
                let parts = checked!(p.slot.abandon(p.id, manager, &mut p.memory));
                checked!(p.release(manager, parts));
                if previous - manager.summary().allocated_pages != pages[j] {
                    stop(34015, serial, debugcon);
                }
                owned[j] = false;
                cancelled += 1;
                record(
                    serial,
                    debugcon,
                    "UNUSED",
                    &[
                        ("task", j as u64),
                        ("released_pages", pages[j]),
                        ("dispatches", u64::from(scheduler.summary().dispatch_count)),
                    ],
                );
            }
        }
        checked!(unsafe {
            arch::x86_64::user_ipc::with_waits(|s| s.poll_wakes(&mut scheduler, cpu))
        });
        checked!(scheduler.validate());
        let d = u64::from(scheduler.summary().dispatch_count);
        if unsafe { arch::x86_64::read_cr3() } != core.page_table_root_physical
            || arch::x86_64::user::active()
            || arch::x86_64::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
            || arch::x86_64::user_root_write_count() - before != 2 * d + extra_flushes
            || manager.summary().allocated_pages - baseline
                != (0..6).filter(|&j| owned[j]).map(|j| pages[j]).sum::<u64>()
        {
            stop(34016, serial, debugcon);
        }
        if d.is_multiple_of(64) {
            record(
                serial,
                debugcon,
                "RUN",
                &[
                    ("dispatches", d),
                    ("cr3_writes", arch::x86_64::user_root_write_count() - before),
                    ("extra_flushes", extra_flushes),
                    ("pages", manager.summary().allocated_pages - baseline),
                    ("calls0", calls[0]),
                    ("calls1", calls[1]),
                    ("calls2", calls[2]),
                    ("calls3", calls[3]),
                    ("calls4", calls[4]),
                    ("calls5", calls[5]),
                    ("ticks0", ticks[0]),
                    ("ticks1", ticks[1]),
                    ("ticks2", ticks[2]),
                    ("ticks3", ticks[3]),
                    ("ticks4", ticks[4]),
                    ("ticks5", ticks[5]),
                    (
                        "live_mask",
                        (0..6)
                            .filter(|&j| live[j])
                            .fold(0, |mask, j| mask | (1 << j)),
                    ),
                    ("generation4", u64::from(generations[0])),
                    ("generation5", u64::from(generations[1])),
                    ("retired", retired),
                    ("unused", cancelled),
                ],
            );
        }
    }
}

fn retire(
    p: &mut Peer,
    outcome: task::Outcome,
    prepared: bool,
    manager: &mut PhysicalMemoryManager,
    scheduler: &mut scheduler::Scheduler,
    pages: u64,
    publish: bool,
) -> Result<(), ()> {
    let before = manager.summary().allocated_pages;
    if prepared {
        if outcome.id != p.id
            || outcome.root != p.root
            || outcome.reason != Reason::Cancelled
            || outcome.syscalls != 0
        {
            return Err(());
        }
        let parts = p
            .slot
            .abandon(p.id, manager, &mut p.memory)
            .map_err(|_| ())?;
        p.release(manager, parts)?;
    } else {
        p.reap(manager, outcome)?;
    }
    scheduler
        .teardown(scheduler::TaskId::new(p.id.slot, p.id.generation).map_err(|_| ())?)
        .map_err(|_| ())?;
    if before.checked_sub(manager.summary().allocated_pages) != Some(pages) {
        return Err(());
    }
    // Completion becomes visible only after revocation, memory release and scheduler teardown.
    if publish
        && unsafe {
            arch::x86_64::user_ipc::with_waits(|s| s.publish_process_completion(outcome, scheduler))
        }
        .map_err(|_| ())?
            != 1
    {
        return Err(());
    }
    Ok(())
}

fn retirement(
    serial: &mut Com1,
    debugcon: &mut DebugCon,
    outcome: task::Outcome,
    pages: u64,
    dispatches: u32,
) {
    let word = match outcome.reason {
        Reason::Exit(code) => (1 << 32) | u64::from(code),
        Reason::Fault(fault) => (2 << 32) | fault.vector,
        Reason::Cancelled => 4 << 32,
        _ => stop(34017, serial, debugcon),
    };
    record(
        serial,
        debugcon,
        "RETIRE",
        &[
            ("task", u64::from(outcome.id.slot)),
            ("generation", u64::from(outcome.id.generation)),
            ("outcome", word),
            ("calls", outcome.syscalls),
            ("released_pages", pages),
            ("dispatches", u64::from(dispatches)),
        ],
    );
}

fn record(serial: &mut Com1, debugcon: &mut DebugCon, event: &str, fields: &[(&str, u64)]) {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:CONTROL ");
    log.write_str(event);
    log.write_str(" contract=PSHELLPROC1");
    for (name, value) in fields {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(*value);
    }
    log.write_str(" cpl=3 production=0\n");
}
