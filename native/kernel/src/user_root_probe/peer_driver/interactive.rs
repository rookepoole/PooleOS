//! Opt-in shell integration. Commands and restart decisions remain in CPL3.
use super::*;
#[cfg(feature = "development-applications")]
mod applications;
mod launch_failure;
mod reclaim;
use poolekernel::{
    capability_ipc::admission::Member,
    user_entry::startup::{Arguments, Program},
};

static INIT: &[u8] = include_bytes!(env!("POOLEOS_INIT_CODE"));
static COUNTER: &[u8] = include_bytes!(env!("POOLEOS_COUNTER_CODE"));
static CONSOLE: &[u8] = include_bytes!(env!("POOLEOS_CONSOLE_CODE"));
static SHELL: &[u8] = include_bytes!(env!("POOLEOS_CONSOLE_CLIENT_CODE"));
#[cfg(not(feature = "development-applications"))]
static WORKER: &[u8] = include_bytes!(env!("POOLEOS_WORKER_CODE"));
#[cfg(feature = "development-applications")]
static TEXT: &[u8] = include_bytes!(env!("POOLEOS_TEXT_CODE"));
#[cfg(feature = "development-applications")]
static NUMBERS: &[u8] = include_bytes!(env!("POOLEOS_NUMBERS_CODE"));

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
    #[cfg(not(feature = "development-applications"))]
    let programs =
        [INIT, COUNTER, CONSOLE, SHELL, WORKER, WORKER].map(|code| checked!(Program::new(code, 0)));
    #[cfg(feature = "development-applications")]
    let programs = [INIT, COUNTER, CONSOLE, SHELL, TEXT, NUMBERS];
    #[cfg(feature = "development-applications")]
    let programs = core::array::from_fn::<_, 6, _>(|i| {
        #[cfg(feature = "development-window-capacity")]
        if i == 2 {
            return checked!(Program::window_service(programs[i], 0));
        }
        #[cfg(feature = "development-launch-session")]
        if i == 3 {
            return checked!(Program::launch_shell(programs[i], 0));
        }
        checked!(Program::new(programs[i], 0))
    });
    #[allow(unused_mut)]
    let mut args = [
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
    #[cfg(feature = "development-files")]
    {
        args[0] = checked!(Arguments::new(&[
            b"file-init",
            b"0000000100010001",
            b"0000000100000001"
        ]));
        args[1] = checked!(Arguments::new(&[
            b"file-service",
            b"0000000100010001",
            b"0000000100000000",
            b"0000000100000003"
        ]));
        args[3] = checked!(Arguments::new(&[
            b"file-shell",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000002",
            b"0000000100060001",
            b"0000000100060002",
            if cfg!(feature = "development-files-bad-handle") {
                b"0000000200010003"
            } else {
                b"0000000100010003"
            },
            b"0000000100000001",
        ]));
    }
    #[cfg(feature = "development-applications")]
    checked!(applications::configure(&mut args));
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
    let mut job = checked!(task::job::Job::<2>::new(&peers[3].slot, peers[3].id));
    for child in &peers[4..] {
        checked!(job.adopt(&child.slot, child.id));
    }
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
    #[cfg(not(feature = "development-files"))]
    let grants = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap_console_ipc(
            core::array::from_fn(|i| (peers[i].id, peers[i].admission)),
            &mut scheduler,
        )
    });
    #[cfg(not(feature = "development-files"))]
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
    #[cfg(feature = "development-files")]
    {
        let grants = checked!(unsafe {
            arch::x86_64::user_ipc::bootstrap_files(
                core::array::from_fn(|i| (peers[i].id, peers[i].admission)),
                &mut scheduler,
            )
        });
        if grants
            != [
                0x100010001,
                0x100010001,
                0x100010001,
                0x100010001,
                0x100010002,
                0x100010002,
                0x100010003,
                0x100040001,
            ]
        {
            stop(34022, serial, debugcon);
        }
        // Slot one replaces the legacy counter role only in this opt-in profile.
        record(
            serial,
            debugcon,
            "FILES",
            &[
                ("version", 1),
                ("init_slot", 0),
                ("service_slot", 1),
                ("shell_slot", 3),
                (
                    "bad_handle",
                    u64::from(cfg!(feature = "development-files-bad-handle")),
                ),
                ("grants", grants.len() as u64),
            ],
        );
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
    #[cfg(not(feature = "development-applications"))]
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
    #[cfg(feature = "development-applications")]
    applications::start(&peers, total, baseline, serial, debugcon);
    let mut live = [true, true, true, true, false, false];
    let mut owned = [true; 6];
    let mut waiting = [None; 6];
    let mut calls = [0u64; 6];
    let mut ticks = [0u64; 6];
    let mut generations = [0u32; 2];
    let mut failures: [Option<launch_failure::Pending>; 2] = [None, None];
    let mut extra_flushes = 0;
    let mut held_dispatches = 0;
    let mut retired = 0;
    let mut cancelled = 0;
    let mut owner_fault = false;
    let mut cleanup_cursor = 0;
    let mut job_drained = false;
    loop {
        // A retained diagnostic tail can progress even without another log record.
        serial.flush();
        // At most one due retained owner is serviced between real user dispatches.
        for offset in 0..6 {
            let j = (cleanup_cursor + offset) % 6;
            if !owned[j] {
                continue;
            }
            let p = &mut peers[j];
            let Some(status) = checked!(p.slot.cleanup_status(p.id)) else {
                continue;
            };
            let Some(due) = status.next_dispatch else {
                continue;
            };
            if scheduler.summary().dispatch_count < due {
                continue;
            }
            cleanup_cursor = (j + 1) % 6;
            let prepared = checked!(p.slot.runtime(p.id)) == task::Runtime::default();
            let previous = manager.summary().allocated_pages;
            let result = checked!(reclaim::poll(
                p, manager, &scheduler, &mut job, serial, debugcon
            ));
            if let task::cleanup::Progress::Complete(outcome) = result {
                if previous.checked_sub(manager.summary().allocated_pages) != Some(pages[j]) {
                    stop(34020, serial, debugcon);
                }
                if status.admitted {
                    checked!(finish_retire(p, outcome, &mut scheduler, j >= 4, &job));
                    retired += 1;
                    retirement(
                        serial,
                        debugcon,
                        outcome,
                        pages[j],
                        scheduler.summary().dispatch_count,
                    );
                    if j >= 4 && owner_fault {
                        orphan_retired(p, prepared, &job, &scheduler, serial, debugcon);
                    }
                } else {
                    cancelled += 1;
                    if j >= 4 && failures[j - 4].is_some() {
                        let pending = checked!(failures[j - 4].take().ok_or(()));
                        checked!(pending.complete(p, &job, &scheduler, serial, debugcon));
                    } else {
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
                live[j] = false;
                owned[j] = false;
            } else if previous != manager.summary().allocated_pages {
                stop(34021, serial, debugcon);
            }
            break;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let i = usize::from(id.slot);
        if i >= 6 || !live[i] || peers[i].id.generation != id.generation {
            stop(34003, serial, debugcon);
        }
        let p = &mut peers[i];
        if cfg!(feature = "development-shell-prepared-stop") && i == 4 && id.generation == 1 {
            if held_dispatches != 0
                || p.slot.state(p.id) != Ok(task::State::Prepared)
                || waiting[i].is_some()
                || calls[i] != 0
                || ticks[i] != 0
            {
                stop(34018, serial, debugcon);
            }
            checked!(scheduler.block_current(cpu));
            held_dispatches = 1;
            prepared_hold(
                p,
                scheduler.summary().dispatch_count,
                arch::x86_64::user_root_write_count() - before,
                serial,
                debugcon,
            );
        } else {
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
                #[cfg(feature = "development-applications")]
                checked!(applications::file_wait(
                    p, "WAKE", calls[i], &scheduler, serial, debugcon
                ));
                waiting[i] = None;
            }
            checked!(p.slot.activate(p.id, manager, &mut p.memory));
            let result = p.slot.run_slice(p.id);
            if let Err(error) = result {
                let (component, code) = match error {
                    task::Error::Cpu(poolekernel::user_entry::prepared::cpu::Error::User(
                        error,
                    )) => ("slice-user", error as u64),
                    task::Error::Accounting(error) => ("slice-accounting", error as u64),
                    _ => ("slice-other", 0),
                };
                arch::x86_64::user::report_failure(component, i as u64, code);
            }
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
                        arch::x86_64::user_ipc::with_waits(|s| {
                            s.park_wait(ticket, &mut scheduler, cpu)
                        })
                    });
                    waiting[i] = Some(ticket);
                    #[cfg(feature = "development-applications")]
                    checked!(applications::file_wait(
                        p, "WAIT", calls[i], &scheduler, serial, debugcon
                    ));
                }
                Event::Preempted { syscalls, .. } | Event::BudgetYield { syscalls } => {
                    calls[i] = syscalls;
                    checked!(scheduler.yield_current(cpu));
                }
                Event::Terminated(outcome) => {
                    calls[i] = outcome.syscalls;
                    #[cfg(feature = "development-file-controls")]
                    let request_state = if i == 4 {
                        Some(checked!(applications::requester_snapshot(p, outcome)))
                    } else {
                        None
                    };
                    if i < 2 || (i == 2 && outcome.reason != Reason::Exit(0)) {
                        let (component, code) = match outcome.reason {
                            Reason::Exit(code) => ("service-exit", u64::from(code)),
                            Reason::Fault(fault) => {
                                arch::x86_64::user::report_failure(
                                    "service-fault-ip",
                                    i as u64,
                                    fault.instruction,
                                );
                                arch::x86_64::user::report_failure(
                                    "service-fault-address",
                                    i as u64,
                                    fault.address,
                                );
                                arch::x86_64::user::report_failure(
                                    "service-fault-error",
                                    i as u64,
                                    fault.error,
                                );
                                ("service-fault", fault.vector)
                            }
                            Reason::InvalidReturn { violation, .. } => {
                                ("service-return", violation as u64)
                            }
                            Reason::Cancelled => ("service-cancelled", 0),
                            Reason::CallLimit => ("service-call-limit", outcome.syscalls),
                            Reason::CallCounterExhausted => {
                                ("service-call-counter", outcome.syscalls)
                            }
                            Reason::Watchdog => ("service-watchdog", outcome.syscalls),
                        };
                        arch::x86_64::user::report_failure(component, i as u64, code);
                        stop(34004, serial, debugcon);
                    }
                    if i == 3 {
                        checked!(job.owner_stopped(&p.slot, p.id));
                        owner_fault = outcome.reason != Reason::Exit(0);
                        if owner_fault {
                            job_record(
                                serial,
                                debugcon,
                                "OWNER",
                                &[
                                    ("task", u64::from(p.id.slot)),
                                    ("generation", u64::from(p.id.generation)),
                                    ("root", p.root),
                                    ("children", job.child_count() as u64),
                                    ("dispatches", u64::from(scheduler.summary().dispatch_count)),
                                ],
                            );
                        }
                    }
                    let complete = checked!(retire(
                        p,
                        outcome,
                        manager,
                        &mut scheduler,
                        pages[i],
                        i >= 4,
                        &mut job,
                        serial,
                        debugcon
                    ));
                    if complete {
                        #[cfg(feature = "development-file-controls")]
                        if let Some(state) = request_state {
                            checked!(applications::requester_retired(
                                p, state, &scheduler, serial, debugcon
                            ));
                        }
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
            }
            // Terminated slices retain their root until retirement; only now
            // are all event paths back in the retained boot address space.
            #[cfg(feature = "development-desktop")]
            checked!(arch::x86_64::desktop::flush());
            if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[i] {
                stop(34005, serial, debugcon);
            }
        }
        #[cfg(feature = "development-claimed-requester")]
        if live[4]
            && let Some(ticket) = waiting[4]
        {
            let state = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| s.request_snapshot(peers[4].id))
            });
            if state.claimed == 1 {
                let sid = checked!(scheduler::TaskId::new(4, peers[4].id.generation));
                let scheduled = checked!(scheduler.task_snapshot(sid));
                if state.queued != 0
                    || state.completed != 0
                    || peers[4].slot.state(peers[4].id) != Ok(task::State::Waiting)
                    || scheduled.state != scheduler::TaskState::Blocked
                    || scheduled.wait_kind != scheduler::WaitKind::Ipc
                {
                    stop(34101, serial, debugcon);
                }
                let p = &mut peers[4];
                let outcome = checked!(p.slot.cancel_waiting(p.id, ticket));
                let flushes = arch::x86_64::user_root_write_count();
                if !checked!(retire(
                    p,
                    outcome,
                    manager,
                    &mut scheduler,
                    pages[4],
                    true,
                    &mut job,
                    serial,
                    debugcon
                )) || arch::x86_64::user_root_write_count() - flushes != 1
                    || checked!(unsafe {
                        arch::x86_64::user_ipc::with_waits(|s| {
                            Ok(s.cancel_wait(ticket, &mut scheduler, cpu).is_ok())
                        })
                    })
                {
                    stop(34102, serial, debugcon);
                }
                extra_flushes += 1;
                record(
                    serial,
                    debugcon,
                    "CLAIMED",
                    &[
                        ("task", 4),
                        ("generation", u64::from(p.id.generation)),
                        ("waiting", 1),
                        ("stale_wait_rejected", 1),
                        ("service_task", 1),
                        ("service_generation", 1),
                        ("dispatches", u64::from(scheduler.summary().dispatch_count)),
                    ],
                );
                checked!(applications::requester_retired(
                    p, state, &scheduler, serial, debugcon
                ));
                waiting[4] = None;
                calls[4] = outcome.syscalls;
                live[4] = false;
                owned[4] = false;
                retired += 1;
                retirement(
                    serial,
                    debugcon,
                    outcome,
                    pages[4],
                    scheduler.summary().dispatch_count,
                );
            }
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
                checked!(p.slot.cancel_prepared(p.id))
            } else if let Some(ticket) = waiting[j] {
                checked!(p.slot.cancel_waiting(p.id, ticket))
            } else {
                checked!(p.slot.cancel_suspended(p.id))
            };
            let flushes = arch::x86_64::user_root_write_count();
            let complete = checked!(retire(
                p,
                outcome,
                manager,
                &mut scheduler,
                pages[j],
                true,
                &mut job,
                serial,
                debugcon
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
            calls[j] = outcome.syscalls;
            if complete {
                live[j] = false;
                owned[j] = false;
                retired += 1;
                retirement(
                    serial,
                    debugcon,
                    outcome,
                    pages[j],
                    scheduler.summary().dispatch_count,
                );
            }
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
                || failures[j - 4].is_some()
                || plan.program != (j - 3) as u16
                || plan.sequence != checked!(generations[j - 4].checked_add(1).ok_or(()))
            {
                stop(34009, serial, debugcon);
            }
            #[cfg(all(
                feature = "development-applications",
                not(feature = "development-windows")
            ))]
            let steps = poolekernel::development_apps::grants(peers[3].id, peers[1].id);
            #[cfg(feature = "development-windows")]
            let steps =
                poolekernel::development_apps::window_grants(peers[3].id, peers[1].id, peers[2].id);
            #[cfg(not(feature = "development-applications"))]
            let steps = [];
            #[cfg(feature = "development-launch-failure")]
            let steps = {
                let mut steps = steps;
                if plan.sequence == 2 {
                    // Two valid grants are installed before the stale third grant fails.
                    steps[2] = poolekernel::capability_ipc::admission::Step::Inherit {
                        source: peers[2].id,
                        handle: 0x200010003,
                        member: 0,
                        rights: poolekernel::capability_ipc::Rights::SEND,
                    };
                }
                steps
            };
            #[cfg(feature = "development-window-lifecycle")]
            let observer = peers[2].id;
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
                checked!(job.adopt(&p.slot, p.id));
            }
            let before_admission = scheduler.summary();
            let admitted = checked!(unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    #[cfg(feature = "development-window-lifecycle")]
                    return Ok(s.admit_observed_launch(
                        &permit,
                        &mut scheduler,
                        Member {
                            id: p.id,
                            image: p.admission,
                            priority: 16,
                        },
                        &steps,
                        observer,
                    ));
                    #[cfg(not(feature = "development-window-lifecycle"))]
                    Ok(s.admit_launch(
                        &permit,
                        &mut scheduler,
                        Member {
                            id: p.id,
                            image: p.admission,
                            priority: 16,
                        },
                        &steps,
                    ))
                })
            });
            match admitted {
                Err(error) => {
                    if !error.recoverable_rejection() || scheduler.summary() != before_admission {
                        stop(34022, serial, debugcon);
                    }
                    let pending = checked!(launch_failure::Pending::cancel(p, permit, plan, error));
                    generations[j - 4] = plan.sequence;
                    ticks[j] = 0;
                    calls[j] = 0;
                    owned[j] = true;
                    pending.rejected(p, pages[j], &scheduler, serial, debugcon);
                    let outcome = checked!(p.slot.outcome(p.id));
                    let previous = manager.summary().allocated_pages;
                    let complete = checked!(reclaim::reap(
                        p,
                        manager,
                        &mut scheduler,
                        outcome,
                        pages[j],
                        false,
                        Some(&mut job),
                        serial,
                        debugcon
                    ));
                    if complete {
                        if previous.checked_sub(manager.summary().allocated_pages) != Some(pages[j])
                        {
                            stop(34023, serial, debugcon);
                        }
                        checked!(pending.complete(p, &job, &scheduler, serial, debugcon));
                        owned[j] = false;
                        cancelled += 1;
                    } else {
                        if previous != manager.summary().allocated_pages {
                            stop(34024, serial, debugcon);
                        }
                        failures[j - 4] = Some(pending);
                    }
                }
                Ok(admitted) => {
                    let handle_index = steps.len();
                    if admitted.count != handle_index + 1
                        || p.id.generation != plan.sequence
                        || checked!(unsafe {
                            arch::x86_64::user_ipc::with_waits(|s| {
                                Ok(s.validate_launch(&permit).is_ok())
                            })
                        })
                    {
                        stop(34012, serial, debugcon);
                    }
                    #[cfg(feature = "development-applications")]
                    checked!(applications::handoff(
                        p,
                        &args[j],
                        &admitted.handles[..handle_index],
                        core,
                        &scheduler,
                        serial,
                        debugcon
                    ));
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
                            ("handle", admitted.handles[handle_index]),
                            ("root", p.root),
                            ("owned_pages", pages[j]),
                            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
                        ],
                    );
                }
            }
        }
        if job.is_closing() {
            for j in 4..6 {
                if !owned[j] {
                    continue;
                }
                let p = &mut peers[j];
                if checked!(p.slot.cleanup_status(p.id)).is_some() {
                    continue;
                }
                let admitted = live[j];
                let prepared = checked!(p.slot.state(p.id)) == task::State::Prepared;
                if !admitted && (generations[j - 4] != 0 || !prepared) {
                    stop(34014, serial, debugcon);
                }
                let previous = manager.summary().allocated_pages;
                let outcome = checked!(job.cancel_orphan(&mut p.slot, p.id, waiting[j]));
                let flushes = arch::x86_64::user_root_write_count();
                let complete;
                if admitted {
                    complete = checked!(retire(
                        p,
                        outcome,
                        manager,
                        &mut scheduler,
                        pages[j],
                        true,
                        &mut job,
                        serial,
                        debugcon
                    ));
                    if complete {
                        retired += 1;
                        retirement(
                            serial,
                            debugcon,
                            outcome,
                            pages[j],
                            scheduler.summary().dispatch_count,
                        );
                        if owner_fault {
                            orphan_retired(p, prepared, &job, &scheduler, serial, debugcon);
                        }
                    }
                } else {
                    complete = checked!(reclaim::reap(
                        p,
                        manager,
                        &mut scheduler,
                        outcome,
                        pages[j],
                        false,
                        Some(&mut job),
                        serial,
                        debugcon
                    ));
                    if complete {
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
                if previous - manager.summary().allocated_pages
                    != if complete { pages[j] } else { 0 }
                {
                    stop(34015, serial, debugcon);
                }
                if arch::x86_64::user_root_write_count() - flushes != u64::from(!prepared) {
                    stop(34019, serial, debugcon);
                }
                extra_flushes += u64::from(!prepared);
                calls[j] = outcome.syscalls;
                waiting[j] = None;
                if complete {
                    live[j] = false;
                    owned[j] = false;
                }
            }
            if owner_fault && !job_drained && job.child_count() == 0 {
                job_drained = true;
                job_record(
                    serial,
                    debugcon,
                    "DRAINED",
                    &[
                        ("children", job.child_count() as u64),
                        ("owned_pages", manager.summary().allocated_pages - baseline),
                        ("dispatches", u64::from(scheduler.summary().dispatch_count)),
                    ],
                );
            }
        }
        checked!(unsafe {
            arch::x86_64::user_ipc::with_waits(|s| s.poll_wakes(&mut scheduler, cpu))
        });
        checked!(scheduler.validate());
        let [routed_arms, routed_restores] = checked!(arch::x86_64::user_watchdog::routed_proof());
        let d = u64::from(scheduler.summary().dispatch_count);
        if unsafe { arch::x86_64::read_cr3() } != core.page_table_root_physical
            || arch::x86_64::user::active()
            || arch::x86_64::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
            || arch::x86_64::user_root_write_count() - before
                != 2 * (d - held_dispatches) + extra_flushes
            || manager.summary().allocated_pages - baseline
                != (0..6).filter(|&j| owned[j]).map(|j| pages[j]).sum::<u64>()
            || routed_arms != routed_restores
        {
            stop(34016, serial, debugcon);
        }
        if d.is_multiple_of(64) {
            #[cfg(feature = "development-serial-recovery")]
            let serial_before = serial.status();
            #[cfg(feature = "development-serial-recovery")]
            if d == 64 {
                serial.challenge_busy_interval();
            }
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
            #[cfg(feature = "development-serial-recovery")]
            if d == 64 {
                let state = serial.status();
                if !state.available
                    || state.pending != 0
                    || state.saturated
                    || state.rejected != 0
                    || state.timeouts != serial_before.timeouts + 1
                    || state.transmitted <= serial_before.transmitted
                {
                    stop(34090, serial, debugcon);
                }
                record(
                    serial,
                    debugcon,
                    "SERIAL",
                    &[
                        ("dispatches", d),
                        ("withheld", poolekernel::early_serial::READY_POLLS as u64),
                        ("timeouts", state.timeouts - serial_before.timeouts),
                        ("pending", state.pending as u64),
                        ("rejected", state.rejected),
                        ("transmitted", state.transmitted - serial_before.transmitted),
                    ],
                );
            }
            #[cfg(feature = "development-app-cleanup-exhaustion")]
            for p in &peers[4..6] {
                checked!(reclaim::exhausted_observation(
                    p, &scheduler, &job, serial, debugcon
                ));
            }
        }
    }
}

fn retire(
    p: &mut Peer,
    outcome: task::Outcome,
    manager: &mut PhysicalMemoryManager,
    scheduler: &mut scheduler::Scheduler,
    pages: u64,
    publish: bool,
    job: &mut task::job::Job<2>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<bool, ()> {
    let before = manager.summary().allocated_pages;
    let child = p.id.slot >= 4;
    let complete = reclaim::reap(
        p,
        manager,
        scheduler,
        outcome,
        pages,
        true,
        if child { Some(&mut *job) } else { None },
        serial,
        debugcon,
    )?;
    if !complete {
        return Ok(false);
    }
    if before.checked_sub(manager.summary().allocated_pages) != Some(pages) {
        return Err(());
    }
    finish_retire(p, outcome, scheduler, publish, job)?;
    Ok(true)
}

fn finish_retire(
    p: &Peer,
    outcome: task::Outcome,
    scheduler: &mut scheduler::Scheduler,
    publish: bool,
    job: &task::job::Job<2>,
) -> Result<(), ()> {
    if p.slot.state(p.id) != Err(task::Error::Missing) {
        return Err(());
    }
    scheduler
        .teardown(scheduler::TaskId::new(p.id.slot, p.id.generation).map_err(|_| ())?)
        .map_err(|_| ())?;
    // Completion becomes visible only after revocation, memory release and scheduler teardown.
    // The lifecycle profile also retains one Inspect-only window observer.
    let expected_recipients = usize::from(!job.is_closing())
        + usize::from(cfg!(feature = "development-window-lifecycle"));
    if publish
        && unsafe {
            arch::x86_64::user_ipc::with_waits(|s| s.publish_process_completion(outcome, scheduler))
        }
        .map_err(|_| ())?
            != expected_recipients
    {
        return Err(());
    }
    Ok(())
}

fn orphan_retired(
    p: &Peer,
    prepared: bool,
    job: &task::job::Job<2>,
    scheduler: &scheduler::Scheduler,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    job_record(
        serial,
        debugcon,
        "CHILD",
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("root", p.root),
            ("prepared", u64::from(prepared)),
            ("remaining", job.child_count() as u64),
            ("published", 0),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
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

fn prepared_hold(
    p: &Peer,
    dispatches: u32,
    writes: u64,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:PREPARED HOLD contract=PCANCEL1 task=4 generation=1");
    for (name, value) in [
        ("root", p.root),
        ("dispatches", u64::from(dispatches)),
        ("cr3_writes", writes),
    ] {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(value);
    }
    log.write_str(" calls=0 ticks=0 state=blocked entered=0 cpl=0 production=0\n");
}

fn job_record(serial: &mut Com1, debugcon: &mut DebugCon, event: &str, fields: &[(&str, u64)]) {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:JOB ");
    log.write_str(event);
    log.write_str(" contract=PJOB1");
    for &(name, value) in fields {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(value);
    }
    log.write_str(" cpl=0 production=0\n");
}

fn record(serial: &mut Com1, debugcon: &mut DebugCon, event: &str, fields: &[(&str, u64)]) {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str(if cfg!(feature = "development-applications") {
        "POOLEOS:APPS "
    } else {
        "POOLEOS:CONTROL "
    });
    log.write_str(event);
    log.write_str(if cfg!(feature = "development-applications") {
        " contract=PAPPSESSION1"
    } else {
        " contract=PSHELLPROC1"
    });
    for (name, value) in fields {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(*value);
    }
    log.write_str(" cpl=3 production=0\n");
}
