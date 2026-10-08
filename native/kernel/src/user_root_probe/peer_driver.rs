//! Existing PKSCHED1 queues drive actual private-root CPL3 quanta, not a transcript.
use super::*;
use poolekernel::{
    scheduler,
    scheduler_smp::TaskId,
    user_entry::{
        syscall::ReturnViolation,
        task::{self, Event, Reason, Slot},
    },
};
use timer_driver::{PeerRun, Timer};

pub(super) mod ipc;
pub(super) mod ipc_pressure;
mod ipc_reply;
pub(super) mod unknown;

// A constructor error carries its owner even if cleanup or slot commit failed.
// This development harness halts on unanticipated quarantine; no owner is freed.
#[allow(dead_code)]
enum PeerFailure {
    Setup,
    Construction(spawn_driver::Failure),
    Slot {
        image: CpuImage<arch::x86_64::UserRootCpu>,
        driver: PeerRun,
        memory: Memory,
    },
}

struct Peer {
    slot: Slot<arch::x86_64::UserRootCpu, PeerRun>,
    id: TaskId,
    memory: Memory,
    handles: [AllocationHandle; 5],
    image: InitialImage,
    root: u64,
    admission: poolekernel::user_entry::ImageAdmission,
}
impl Peer {
    #[inline(never)]
    fn new(
        index: u8,
        kind: usize,
        handoff: &Handoff<'_>,
        core: CoreRecord,
        bits: u8,
        manager: &mut PhysicalMemoryManager,
        topology: interrupt_time::MadtTopology,
        hpet: interrupt_time::HpetDescription,
        probe: timer_driver::Probe,
        missing_local: bool,
    ) -> Result<Self, PeerFailure> {
        Self::new_with_arguments(
            index,
            kind,
            [0; 6],
            handoff,
            core,
            bits,
            manager,
            topology,
            hpet,
            probe,
            missing_local,
        )
    }

    #[inline(never)]
    fn new_with_arguments(
        index: u8,
        kind: usize,
        arguments: [u64; 6],
        handoff: &Handoff<'_>,
        core: CoreRecord,
        bits: u8,
        manager: &mut PhysicalMemoryManager,
        topology: interrupt_time::MadtTopology,
        hpet: interrupt_time::HpetDescription,
        probe: timer_driver::Probe,
        missing_local: bool,
    ) -> Result<Self, PeerFailure> {
        let mut timer =
            Timer::new(handoff, topology, hpet, bits).map_err(|_| PeerFailure::Setup)?;
        timer.set_probe(probe);
        let bytes = arch::x86_64::user::peer_payload(if kind == 15 { 0 } else { kind })
            .map_err(|_| PeerFailure::Setup)?;
        // SAFETY: exclusive BSP, IF0, before allocation or task activation.
        let mut entry =
            unsafe { arch::x86_64::user::PeerEntry::new(core.initial_stack_top_virtual) }
                .map_err(|_| PeerFailure::Setup)?;
        entry
            .set_initial_arguments(arguments)
            .map_err(|_| PeerFailure::Setup)?;
        if missing_local {
            entry
                .inject_missing_local_timer()
                .map_err(|_| PeerFailure::Setup)?;
        }
        if kind == 15 {
            entry.inject_lost_sample().map_err(|_| PeerFailure::Setup)?;
        }
        let built = spawn_driver::build(manager, core, bits, bytes, Some(timer.mappings()))
            .map_err(PeerFailure::Construction)?;
        Self::install(index, entry, timer, built, core)
    }

    // Keep slot/CPU-image temporaries off the deep mapping-validation call path.
    #[inline(never)]
    fn install(
        index: u8,
        entry: arch::x86_64::user::PeerEntry,
        timer: Timer,
        built: spawn_driver::Built,
        core: CoreRecord,
    ) -> Result<Self, PeerFailure> {
        let mut slot = Slot::new(index).map_err(|_| PeerFailure::Setup)?;
        let spawn_driver::Built {
            prepared,
            memory,
            handles,
            image,
        } = built;
        let admission = prepared
            .admission()
            .expect("successful construction admits its image");
        let root = admission.root_physical;
        let cpu = unsafe { arch::x86_64::UserRootCpu::new(core.page_table_root_physical, root) };
        let id = match slot.insert(CpuImage::new(prepared, cpu, core), PeerRun { entry, timer }) {
            Ok(id) => id,
            Err((_, image, driver)) => {
                return Err(PeerFailure::Slot {
                    image,
                    driver,
                    memory,
                });
            }
        };
        Ok(Self {
            slot,
            id,
            memory,
            handles,
            image,
            root,
            admission,
        })
    }
    /// Reuse the exact empty slot in place; never copy a large ownership container
    /// through the constructor's deep mapping-validation stack.
    #[inline(never)]
    fn restart(
        &mut self,
        kind: usize,
        arguments: [u64; 6],
        handoff: &Handoff<'_>,
        core: CoreRecord,
        bits: u8,
        manager: &mut PhysicalMemoryManager,
        topology: interrupt_time::MadtTopology,
        hpet: interrupt_time::HpetDescription,
        probe: timer_driver::Probe,
    ) -> Result<(), PeerFailure> {
        if self.slot.state(self.id) != Err(task::Error::Missing) {
            return Err(PeerFailure::Setup);
        }
        let mut timer =
            Timer::new(handoff, topology, hpet, bits).map_err(|_| PeerFailure::Setup)?;
        timer.set_probe(probe);
        let bytes = arch::x86_64::user::peer_payload(kind).map_err(|_| PeerFailure::Setup)?;
        let mut entry =
            unsafe { arch::x86_64::user::PeerEntry::new(core.initial_stack_top_virtual) }
                .map_err(|_| PeerFailure::Setup)?;
        entry
            .set_initial_arguments(arguments)
            .map_err(|_| PeerFailure::Setup)?;
        let built = spawn_driver::build(manager, core, bits, bytes, Some(timer.mappings()))
            .map_err(PeerFailure::Construction)?;
        self.reinstall(entry, timer, built, core)
    }
    #[inline(never)]
    fn reinstall(
        &mut self,
        entry: arch::x86_64::user::PeerEntry,
        timer: Timer,
        built: spawn_driver::Built,
        core: CoreRecord,
    ) -> Result<(), PeerFailure> {
        let spawn_driver::Built {
            prepared,
            memory,
            handles,
            image,
        } = built;
        let admission = prepared
            .admission()
            .expect("successful construction admits its image");
        let root = admission.root_physical;
        let cpu = unsafe { arch::x86_64::UserRootCpu::new(core.page_table_root_physical, root) };
        let id = match self
            .slot
            .insert(CpuImage::new(prepared, cpu, core), PeerRun { entry, timer })
        {
            Ok(id) => id,
            Err((_, image, driver)) => {
                return Err(PeerFailure::Slot {
                    image,
                    driver,
                    memory,
                });
            }
        };
        self.id = id;
        self.memory = memory;
        self.handles = handles;
        self.image = image;
        self.root = root;
        self.admission = admission;
        Ok(())
    }
    fn reap(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        expected: task::Outcome,
    ) -> Result<(), ()> {
        for h in self.handles {
            if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                return Err(());
            }
        }
        if self.slot.run_slice(self.id).is_ok() {
            return Err(());
        }
        let (parts, observed) = self
            .slot
            .reap(self.id, manager, &mut self.memory)
            .map_err(|_| ())?;
        if observed != expected || self.slot.reap(self.id, manager, &mut self.memory).is_ok() {
            return Err(());
        }
        self.release(manager, parts)
    }
    fn recover_timer(&mut self, manager: &mut PhysicalMemoryManager) -> Result<(), ()> {
        if self.slot.state(self.id) != Ok(task::State::Quarantined)
            || unsafe { arch::x86_64::read_cr3() } != self.root
            || !arch::x86_64::user::active()
            || arch::x86_64::read_rflags() & (1 << 9) != 0
            || IRQ_APIC_VIRTUAL.load(Ordering::Acquire)
                != poolekernel::user_entry::timer::APIC_VIRTUAL
            || self.slot.run_slice(self.id).is_ok()
            || self.slot.reap(self.id, manager, &mut self.memory).is_ok()
            || self
                .slot
                .activate(self.id, manager, &mut self.memory)
                .is_ok()
        {
            return Err(());
        }
        for h in self.handles {
            if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                return Err(());
            }
        }
        let parts = self
            .slot
            .abandon(self.id, manager, &mut self.memory)
            .map_err(|_| ())?;
        if self
            .slot
            .abandon(self.id, manager, &mut self.memory)
            .is_ok()
            || arch::x86_64::user::active()
            || IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != 0
        {
            return Err(());
        }
        self.release(manager, parts)
    }
    fn release(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        mut parts: DetachedImage,
    ) -> Result<(), ()> {
        for h in [self.handles[1], self.handles[2], self.handles[3]] {
            self.memory.zero(h).map_err(|_| ())?;
        }
        for address in [self.image.code_page, self.image.stack_page] {
            let t = parts
                .space
                .begin_unmap(&mut self.memory, address)
                .map_err(|_| ())?;
            parts.space.acknowledge_inactive(t).map_err(|_| ())?;
            if !parts.space.complete_unmap(manager, t).map_err(|_| ())? {
                return Err(());
            }
        }
        parts
            .space
            .release(manager, &mut self.memory)
            .map_err(|_| ())?;
        manager.free(parts.stack).map_err(|_| ())?;
        manager.free(parts.stack_tables).map_err(|_| ())?;
        self.memory.finish().map_err(|_| ())
    }
}

#[inline(never)]
pub fn run_all(
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
        ($stage:expr,$op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop($stage, serial, debugcon),
            }
        };
    }
    let baseline = manager.summary().allocated_pages;
    let mut spawn_rollbacks = 0;
    let mut quota_rollback = false;
    let mut timer_recovered = false;
    let mut samples = 0u64;
    let mut terminal_samples = 0u64;
    let mut runtime_ticks = 0u64;
    let mut terminal_ticks = 0u64;
    let mut preempt_ticks = 0u64;
    let mut failed_ticks = 0u64;
    let mut duplicate_denials = 0u64;
    let mut watchdog_ticks = 0u64;
    for round in 0..16 {
        let first_kind = if round == 15 {
            2
        } else if round == 14 {
            0
        } else if round >= 3 {
            round + 1
        } else {
            round
        };
        let probe = match round {
            0 => timer_driver::Probe::Pending,
            1 => timer_driver::Probe::Late,
            14 => timer_driver::Probe::FailOnce,
            _ => timer_driver::Probe::None,
        };
        let mut peers = [
            checked!(
                100,
                Peer::new(
                    0,
                    first_kind,
                    handoff,
                    core,
                    bits,
                    manager,
                    topology,
                    hpet,
                    probe,
                    round == 15
                )
            ),
            checked!(
                101,
                Peer::new(
                    1,
                    3,
                    handoff,
                    core,
                    bits,
                    manager,
                    topology,
                    hpet,
                    timer_driver::Probe::None,
                    false
                )
            ),
        ];
        if peers[0].root == peers[1].root || manager.summary().allocated_pages != baseline + 26 {
            stop(102, serial, debugcon);
        }
        let mut scheduler = checked!(103, scheduler::Scheduler::new(1));
        let cpu = checked!(103, scheduler::CpuId::new(0));
        for p in &peers {
            let id = checked!(
                104,
                scheduler.create_task(p.id.slot, p.id.generation, 16, 1)
            );
            checked!(104, scheduler.activate(id, cpu));
        }
        let before = arch::x86_64::user_root_write_count();
        let mut preemptions = [0u64; 2];
        let mut progress = [0u64; 2];
        let mut ticks = [0u64; 2];
        let mut dead = [false; 2];
        let mut after_stop = 0u64;
        let mut first_reason = None;
        for _ in 0..64 {
            if dead == [true; 2] {
                break;
            }
            let scheduled = checked!(105, scheduler.dispatch(cpu));
            let index = scheduled.index();
            if index >= 2 || dead[index] {
                stop(105, serial, debugcon);
            }
            let peer = &mut peers[index];
            if scheduled.generation != peer.id.generation {
                stop(105, serial, debugcon);
            }
            checked!(106, peer.slot.activate(peer.id, manager, &mut peer.memory));
            let result = peer.slot.run_slice(peer.id);
            let elapsed = checked!(126, peer.slot.account_slice(peer.id, &mut scheduler, cpu));
            if peer.slot.account_slice(peer.id, &mut scheduler, cpu) != Err(task::Error::State) {
                stop(126, serial, debugcon);
            }
            duplicate_denials += 1;
            samples += 1;
            ticks[index] = checked!(126, ticks[index].checked_add(elapsed).ok_or(()));
            runtime_ticks = checked!(126, runtime_ticks.checked_add(elapsed).ok_or(()));
            let accounting = checked!(126, peer.slot.runtime(peer.id));
            if accounting.pending_ticks.is_some()
                || accounting.unknown
                || accounting.charged_ticks != ticks[index]
                || checked!(126, scheduler.task_snapshot(scheduled)).runtime_ticks != ticks[index]
            {
                stop(126, serial, debugcon);
            }
            if result.is_err() && round == 14 && index == 0 && !timer_recovered {
                if result
                    != Err(task::Error::Cpu(
                        poolekernel::user_entry::prepared::cpu::Error::User(
                            poolekernel::user_entry::privilege::Error::Hardware,
                        ),
                    ))
                {
                    stop(123, serial, debugcon);
                }
                checked!(124, peer.recover_timer(manager));
                failed_ticks = elapsed;
                checked!(124, scheduler.teardown(scheduled));
                timer_recovered = true;
                dead[0] = true;
                continue;
            }
            let slice = checked!(107, result);
            let mut terminated = None;
            match slice.event {
                Event::Waiting { .. } => stop(108, serial, debugcon),
                Event::Preempted {
                    ticks: observed,
                    syscalls,
                    progress: now,
                } => {
                    if now <= progress[index] || syscalls != 0 || observed != elapsed {
                        stop(108, serial, debugcon);
                    }
                    progress[index] = now;
                    preemptions[index] += 1;
                    if round == 0 && index == 1 && preemptions[index] == 1 {
                        let timer = checked!(120, Timer::new(handoff, topology, hpet, bits));
                        checked!(
                            122,
                            spawn_driver::quota_case(manager, core, bits, timer.mappings())
                        );
                        quota_rollback = true;
                    }
                    if round == 0 && index == 1 && dead[0] && spawn_rollbacks == 0 {
                        let timer = checked!(120, Timer::new(handoff, topology, hpet, bits));
                        spawn_rollbacks = match spawn_driver::fault_cases(
                            manager,
                            core,
                            bits,
                            timer.mappings(),
                        ) {
                            Ok(count) => count,
                            Err(stage) => stop(12000 + stage, serial, debugcon),
                        };
                        if spawn_rollbacks != 6 {
                            stop(120, serial, debugcon);
                        }
                    }
                    preempt_ticks = checked!(109, preempt_ticks.checked_add(elapsed).ok_or(()));
                    if index == 1 && dead[0] {
                        after_stop += 1;
                    }
                    for h in peer.handles {
                        if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                            stop(110, serial, debugcon);
                        }
                    }
                    if round == 2 && index == 0 && preemptions[0] == 3 {
                        terminated = Some(checked!(111, peer.slot.cancel_suspended(peer.id)));
                    } else if checked!(112, scheduler.yield_current(cpu)) != scheduled {
                        stop(112, serial, debugcon);
                    }
                }
                Event::Terminated(outcome) => {
                    terminal_samples += 1;
                    terminal_ticks = checked!(109, terminal_ticks.checked_add(elapsed).ok_or(()));
                    terminated = Some(outcome);
                }
            }
            if let Some(outcome) = terminated {
                let valid = if index == 1 {
                    outcome.reason == Reason::Exit(84) && outcome.syscalls == 1
                } else {
                    match (round, outcome.reason) {
                        (0, Reason::Exit(42)) => outcome.syscalls == 1,
                        (1, Reason::Fault(f)) => {
                            f.vector == 6 && f.error == 0 && outcome.syscalls == 0
                        }
                        (2, Reason::Cancelled) => outcome.syscalls == 0,
                        (3, Reason::CallLimit) => outcome.syscalls == 64,
                        (15, Reason::Watchdog) => outcome.syscalls == 0,
                        (
                            4 | 5,
                            Reason::InvalidReturn {
                                vector: 256,
                                violation: ReturnViolation::Stack,
                            },
                        )
                        | (
                            6 | 7,
                            Reason::InvalidReturn {
                                vector: 256,
                                violation: ReturnViolation::Flags,
                            },
                        )
                        | (
                            8,
                            Reason::InvalidReturn {
                                vector: 256,
                                violation: ReturnViolation::Instruction,
                            },
                        )
                        | (
                            9,
                            Reason::InvalidReturn {
                                vector: 64,
                                violation: ReturnViolation::Stack,
                            },
                        ) => outcome.syscalls == 0,
                        (10..=13, Reason::Fault(f)) => {
                            // This TCG-only probe records QEMU issue 928, not native #SS qualification.
                            f.vector == [0, 1, 3, 13][round - 10]
                                && f.error == 0
                                && outcome.syscalls == 0
                        }
                        _ => false,
                    }
                };
                if !valid || (index == 1 && !dead[0]) {
                    let mut log = EarlyLogger::new(BootSink {
                        serial,
                        debugcon,
                        ring: &EARLY_RING,
                    });
                    log.write_str("POOLEOS:KERNEL:USER-PEER-REJECT round=");
                    log.write_decimal_u64(round as u64);
                    log.write_str(" task=");
                    log.write_decimal_u64(index as u64);
                    log.write_str(" syscalls=");
                    log.write_decimal_u64(u64::from(outcome.syscalls));
                    if let Reason::Fault(f) = outcome.reason {
                        for (label, value) in [
                            (" vector=", f.vector),
                            (" error=", f.error),
                            (" instruction=", f.instruction),
                            (" address=", f.address),
                        ] {
                            log.write_str(label);
                            log.write_hex_u64(value);
                        }
                    }
                    log.write_str("\n");
                    stop(113, serial, debugcon);
                }
                checked!(114, scheduler.teardown(scheduled));
                checked!(115, peer.reap(manager, outcome));
                dead[index] = true;
                if index == 0 {
                    first_reason = Some(outcome.reason);
                    if round == 15 {
                        watchdog_ticks = elapsed;
                    }
                }
            }
        }
        checked!(116, scheduler.validate());
        let summary = scheduler.summary();
        let writes = arch::x86_64::user_root_write_count() - before;
        if dead != [true; 2]
            || (round < 14 && preemptions[0] < 1)
            || (round == 14 && (!timer_recovered || preemptions[0] != 0))
            || (round == 15
                && (first_reason != Some(Reason::Watchdog)
                    || preemptions[0] != 0
                    || watchdog_ticks == 0
                    || after_stop != preemptions[1]))
            || preemptions[1] < 2
            || after_stop < 1
            || summary.running_count != 0
            || summary.runnable_count != 0
            || summary.dead_count != 2
            || writes != u64::from(summary.dispatch_count) * 2 + u64::from(round == 2)
            || manager.summary().allocated_pages != baseline
        {
            stop(117, serial, debugcon);
        }
        for index in 0..2 {
            let id = checked!(
                118,
                scheduler::TaskId::new(peers[index].id.slot, peers[index].id.generation)
            );
            if checked!(118, scheduler.task_snapshot(id)).runtime_ticks != ticks[index] {
                stop(118, serial, debugcon);
            }
        }
        let (reason, value) = match first_reason {
            Some(Reason::Exit(code)) => ("exit", u64::from(code)),
            Some(Reason::Fault(f)) => ("fault", f.vector),
            Some(Reason::Cancelled) => ("cancel", 0),
            Some(Reason::CallLimit) => ("limit", 64),
            Some(Reason::Watchdog) => ("watchdog", 65),
            Some(Reason::InvalidReturn { violation, .. }) => ("return", violation as u64),
            None if round == 14 && timer_recovered => ("quarantine", 0),
            _ => stop(119, serial, debugcon),
        };
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER10 scheduler=PKSCHED1 round=");
        log.write_decimal_u64(round as u64);
        log.write_str(" first=");
        log.write_str(reason);
        log.write_str(" value=");
        log.write_decimal_u64(value);
        for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
            log.write_str(label);
            log.write_hex_u64(value);
        }
        for (label, value) in [
            (" dispatches=", u64::from(summary.dispatch_count)),
            (" preempt0=", preemptions[0]),
            (" preempt1=", preemptions[1]),
            (" progress0=", progress[0]),
            (" progress1=", progress[1]),
            (" ticks0=", ticks[0]),
            (" ticks1=", ticks[1]),
            (" survivor_after_stop=", after_stop),
            (" cr3_writes=", writes),
        ] {
            log.write_str(label);
            log.write_decimal_u64(value);
        }
        log.write_str(" return_vector=");
        log.write_decimal_u64(match first_reason {
            Some(Reason::InvalidReturn { vector, .. }) => vector,
            _ => 0,
        });
        log.write_str(" survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
    }
    if spawn_rollbacks != 6 || !quota_rollback {
        stop(121, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-SPAWN PASS contract=PKUSER11 quota_failures=1 quota_released_pages=5 quota_scrubbed_pages=5 after_effect_failures=6 cleanup_quarantines=6 cleanup_retries=6 retained_free_denials=30 released_pages=83 scrubbed_pages=83 peer_resumed=1 peer_exit=84 cpu_exposures=0 production=0\n");
    let deliveries = match timer_driver::drain_proof() {
        Ok(v) => v,
        Err(_) => stop(125, serial, debugcon),
    };
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-TIMER-DRAIN PASS contract=PKUSER12 pending=1 late=1 quarantines=1 retries=1 retained_pages=13 free_denials=5 restart_denials=2 reap_denials=1 peer_exit=84 deliveries=");
    log.write_decimal_u64(u64::from(deliveries));
    log.write_str(" eois=");
    log.write_decimal_u64(u64::from(deliveries));
    log.write_str(" empty_irr_isr=1 kernel_window=1 detached_after_shutdown=1 if=0 production=0\n");
    drop(log);
    if samples != 156
        || terminal_samples != 30
        || duplicate_denials != samples
        || failed_ticks == 0
        || terminal_ticks == 0
        || runtime_ticks != preempt_ticks + terminal_ticks + failed_ticks
    {
        stop(127, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-RUNTIME PASS contract=PKUSER13");
    for (label, value) in [
        (" samples=", samples),
        (" terminal_samples=", terminal_samples),
        (" duplicate_denials=", duplicate_denials),
        (" ticks=", runtime_ticks),
        (" preempt_ticks=", preempt_ticks),
        (" terminal_ticks=", terminal_ticks),
        (" failed_cleanup_ticks=", failed_ticks),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" failed_cleanup_samples=1 scheduler_match=1 pending=0 unknown=0 clock=hpet charge_window=arm_to_event production=0\n");
    drop(log);
    let proof = checked!(128, arch::x86_64::user_watchdog::proof());
    if proof != [samples, 1, samples, samples] || watchdog_ticks == 0 {
        stop(128, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-WATCHDOG PASS contract=PKUSER14 source=hpet_msi local_masked=1 recoveries=1");
    for (label, value) in [
        (" arms=", proof[0]),
        (" stops=", proof[2]),
        (" restores=", proof[3]),
        (" ticks=", watchdog_ticks),
    ] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(
        " deadline_ns=50000000 peer_exit=84 shared_apic=1 requires_if=1 nmi=0 production=0\n",
    );
}
