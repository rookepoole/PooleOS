//! Native terminal cleanup keeps the task slot occupied until every page is freed.
use super::*;

pub(super) fn reap(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &mut scheduler::Scheduler,
    outcome: task::Outcome,
    pages: u64,
    admitted: bool,
    mut job: Option<&mut ManagedJob<'_>>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<bool, ()> {
    if p.slot.outcome(p.id) != Ok(outcome) {
        return Err(());
    }
    for h in p.handles {
        if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
            return Err(());
        }
    }
    #[cfg(feature = "development-launch-failure")]
    if !admitted && outcome.id.slot == 5 && outcome.id.generation == 2 {
        let before = manager.summary().allocated_pages;
        let mut memory = FaultMemory {
            inner: &mut p.memory,
            mode: 4,
            fired: false,
        };
        let children = job.as_ref().ok_or(())?.child_count();
        let result =
            job.as_deref_mut()
                .ok_or(())?
                .reclaim_child(&mut p.slot, p.id, manager, &mut memory);
        if !memory.fired
            || result
                != Err(task::Error::Reclamation(
                    poolekernel::user_entry::retirement::Error::Memory,
                ))
            || manager.summary().allocated_pages != before
            || job.as_ref().ok_or(())?.child_count() != children
            || p.slot.reclaim_remaining_pages(p.id) != Ok(pages)
        {
            return Err(());
        }
        defer(p, scheduler, false, serial, debugcon)?;
        return Ok(false);
    }
    #[cfg(feature = "development-shell-cleanup-retry")]
    if admitted && (4..6).contains(&outcome.id.slot) && (1..=2).contains(&outcome.id.generation) {
        let before = manager.summary().allocated_pages;
        let mode = 1 + (outcome.id.slot - 4) * 2 + (outcome.id.generation as u8 - 1);
        let mut memory = FaultMemory {
            inner: &mut p.memory,
            mode,
            fired: false,
        };
        let children = job.as_ref().map(|j| j.child_count());
        let result = match job.as_deref_mut() {
            Some(j) => j.reclaim_child(&mut p.slot, p.id, manager, &mut memory),
            None => p.slot.reclaim(p.id, manager, &mut memory),
        };
        if !memory.fired
            || !matches!(result, Err(task::Error::Reclamation(_)))
            || p.slot.state(p.id) != Ok(task::State::Reclaiming)
            || p.slot.reclaim_remaining_pages(p.id) != Ok(pages)
            || job.as_ref().map(|j| j.child_count()) != children
            || manager.summary().allocated_pages != before
            || p.slot.run_slice(p.id).is_ok()
            || p.slot.activate(p.id, manager, &mut p.memory).is_ok()
            || unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    Ok(s.publish_process_completion(outcome, scheduler).is_ok())
                })
            }
            .map_err(|_| ())?
        {
            return Err(());
        }
        for h in p.handles {
            if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                return Err(());
            }
        }
        if cfg!(feature = "development-shell-deferred-cleanup") {
            defer(p, scheduler, admitted, serial, debugcon)?;
            return Ok(false);
        }
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:RECLAIM RETRY contract=PRECLAIM1");
        for (name, value) in [
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("mode", u64::from(mode)),
            ("retained_pages", pages),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ] {
            log.write_str(" ");
            log.write_str(name);
            log.write_str("=");
            log.write_decimal_u64(value);
        }
        log.write_str(" released_pages=0 ordinary_free_denials=5 no_reentry=1 early_completion_rejected=1 cpl=0 production=0\n");
    }
    #[cfg(not(feature = "development-shell-cleanup-retry"))]
    let _ = pages;
    let result = match job.as_deref_mut() {
        Some(j) => j.reclaim_child(&mut p.slot, p.id, manager, &mut p.memory),
        None => p.slot.reclaim(p.id, manager, &mut p.memory),
    };
    if matches!(
        result,
        Err(task::Error::Reclamation(
            poolekernel::user_entry::retirement::Error::Memory
                | poolekernel::user_entry::retirement::Error::Readback
        ))
    ) {
        if p.slot.reclaim_remaining_pages(p.id) != Ok(pages) {
            return Err(());
        }
        defer(p, scheduler, admitted, serial, debugcon)?;
        return Ok(false);
    }
    if result.map_err(|_| ())? != outcome || p.slot.state(p.id) != Err(task::Error::Missing) {
        return Err(());
    }
    Ok(true)
}

fn defer(
    p: &mut Peer,
    scheduler: &mut scheduler::Scheduler,
    admitted: bool,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    let cpu = scheduler::CpuId::new(0).map_err(|_| ())?;
    p.slot
        .defer_reclamation(p.id, scheduler, cpu, admitted)
        .map_err(|_| ())?;
    observation(p, scheduler, "DEFER", serial, debugcon)?;
    #[cfg(feature = "development-shell-orphan-recovery")]
    entered_observation(p, scheduler, "PARKED", serial, debugcon)?;
    Ok(())
}

pub(super) fn poll(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &scheduler::Scheduler,
    job: &mut ManagedJob<'_>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<task::cleanup::Progress, ()> {
    let status = p.slot.cleanup_status(p.id).map_err(|_| ())?.ok_or(())?;
    let result;
    #[cfg(any(
        feature = "development-shell-deferred-cleanup",
        feature = "development-launch-orphan"
    ))]
    if (cfg!(feature = "development-shell-deferred-cleanup")
        && p.id.slot >= 4
        && (status.attempts == 0
            || cfg!(feature = "development-app-cleanup-exhaustion")
            || cfg!(feature = "development-shell-orphan-recovery")))
        || (cfg!(feature = "development-launch-orphan")
            && p.id.slot == 5
            && p.id.generation == 2
            && !status.admitted)
    {
        let mut memory = FaultMemory {
            inner: &mut p.memory,
            mode: 4,
            fired: false,
        };
        result = job
            .reclaim_deferred_child(&mut p.slot, p.id, manager, &mut memory, scheduler)
            .map_err(|_| ())?;
        let expected = if status.attempts + 1 == task::cleanup::MAX_ATTEMPTS {
            task::cleanup::Progress::Exhausted
        } else {
            task::cleanup::Progress::Retried
        };
        if !memory.fired || result != expected {
            return Err(());
        }
    } else {
        result = retry(p, manager, scheduler, job)?;
    }
    #[cfg(not(any(
        feature = "development-shell-deferred-cleanup",
        feature = "development-launch-orphan"
    )))]
    {
        let _ = status;
        result = retry(p, manager, scheduler, job)?;
    }
    if matches!(
        result,
        task::cleanup::Progress::Retried | task::cleanup::Progress::Exhausted
    ) {
        let outcome = p.slot.outcome(p.id).map_err(|_| ())?;
        if p.slot.run_slice(p.id).is_ok()
            || p.slot.activate(p.id, manager, &mut p.memory).is_ok()
            || unsafe {
                arch::x86_64::user_ipc::with_waits(|s| {
                    Ok(s.publish_process_completion(outcome, scheduler).is_ok())
                })
            }
            .map_err(|_| ())?
        {
            return Err(());
        }
        for h in p.handles {
            if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                return Err(());
            }
        }
    }
    match result {
        task::cleanup::Progress::Retried => observation(p, scheduler, "RETRY", serial, debugcon)?,
        task::cleanup::Progress::Exhausted => {
            observation(p, scheduler, "EXHAUSTED", serial, debugcon)?
        }
        task::cleanup::Progress::Complete(_) => {
            cleanup_record(
                serial,
                debugcon,
                "COMPLETE",
                p.id,
                status.attempts + 1,
                0,
                0,
                scheduler.summary().dispatch_count,
                status.admitted,
            );
        }
        task::cleanup::Progress::Waiting => return Err(()),
    }
    Ok(result)
}

fn retry(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &scheduler::Scheduler,
    job: &mut ManagedJob<'_>,
) -> Result<task::cleanup::Progress, ()> {
    if p.id.slot >= 4 {
        job.reclaim_deferred_child(&mut p.slot, p.id, manager, &mut p.memory, scheduler)
    } else {
        p.slot
            .reclaim_deferred(p.id, manager, &mut p.memory, scheduler)
    }
    .map_err(|_| ())
}

pub(super) fn recover(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &scheduler::Scheduler,
    job: &mut ManagedJob<'_>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<Option<task::cleanup::Progress>, ()> {
    use task::cleanup::{Progress, Recovery};
    let remaining = p.slot.reclaim_remaining_pages(p.id).map_err(|_| ())?;
    let progress;
    #[cfg(any(
        feature = "development-launch-orphan-stuck",
        feature = "development-shell-orphan-stuck"
    ))]
    {
        let mut memory = FaultMemory {
            inner: &mut p.memory,
            mode: 4,
            fired: false,
        };
        progress = job
            .recover_exhausted_child(&mut p.slot, p.id, manager, &mut memory, scheduler)
            .map_err(|_| ())?;
        if memory.fired != (progress == Recovery::Retained) {
            return Err(());
        }
    }
    #[cfg(not(any(
        feature = "development-launch-orphan-stuck",
        feature = "development-shell-orphan-stuck"
    )))]
    {
        progress = job
            .recover_exhausted_child(&mut p.slot, p.id, manager, &mut p.memory, scheduler)
            .map_err(|_| ())?;
    }
    let result = match progress {
        Recovery::Waiting | Recovery::Unavailable => return Ok(None),
        Recovery::Retained => {
            if p.slot.reclaim_remaining_pages(p.id) != Ok(remaining) {
                return Err(());
            }
            for h in p.handles {
                if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                    return Err(());
                }
            }
            Progress::Exhausted
        }
        Recovery::Complete(outcome) => Progress::Complete(outcome),
    };
    record(
        serial,
        debugcon,
        "RECOVER",
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("root", p.root),
            ("attempts", 1),
            (
                "retained_pages",
                if matches!(result, Progress::Complete(_)) {
                    0
                } else {
                    remaining
                },
            ),
            (
                "recovered",
                u64::from(matches!(result, Progress::Complete(_))),
            ),
            ("children", job.child_count() as u64),
            ("writes", p.memory.physical_write_count()),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
    Ok(Some(result))
}

#[cfg(feature = "development-shell-orphan-recovery")]
pub(super) fn entered_observation(
    p: &Peer,
    scheduler: &scheduler::Scheduler,
    event: &str,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    let status = p.slot.cleanup_status(p.id).map_err(|_| ())?.ok_or(())?;
    let runtime = p.slot.runtime(p.id).map_err(|_| ())?;
    let outcome = p.slot.outcome(p.id).map_err(|_| ())?;
    let sid = scheduler::TaskId::new(p.id.slot, p.id.generation).map_err(|_| ())?;
    let scheduled = scheduler.task_snapshot(sid).map_err(|_| ())?;
    if p.id.slot != 4
        || p.id.generation != 1
        || !status.admitted
        || p.slot.state(p.id) != Ok(task::State::Reclaiming)
        || outcome.reason != Reason::Cancelled
        || outcome.syscalls == 0
        || runtime.charged_ticks == 0
        || runtime.charged_slices == 0
        || runtime.pending_ticks.is_some()
        || runtime.unknown
        || scheduled.wait_kind != scheduler::WaitKind::Reclamation
        || scheduled.runtime_ticks != runtime.charged_ticks
        || scheduled.dispatch_count != runtime.charged_slices
        || scheduled.unmeasured_dispatches != 0
        || (event == "HELD"
            && (status.attempts != task::cleanup::MAX_ATTEMPTS || status.next_dispatch.is_some()))
    {
        return Err(());
    }
    record(
        serial,
        debugcon,
        event,
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("root", p.root),
            ("attempts", u64::from(status.attempts)),
            ("next", u64::from(status.next_dispatch.unwrap_or(0))),
            (
                "pages",
                p.slot.reclaim_remaining_pages(p.id).map_err(|_| ())?,
            ),
            ("writes", p.memory.physical_write_count()),
            ("calls", outcome.syscalls),
            ("ticks", runtime.charged_ticks),
            ("slices", u64::from(runtime.charged_slices)),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
    Ok(())
}

#[cfg(feature = "development-launch-orphan-stuck")]
pub(super) fn orphan_hold(
    p: &Peer,
    scheduler: &scheduler::Scheduler,
    job: &ManagedJob<'_>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    let status = p.slot.cleanup_status(p.id).map_err(|_| ())?.ok_or(())?;
    let runtime = p.slot.runtime(p.id).map_err(|_| ())?;
    if !job.is_closing()
        || job.child_count() != 1
        || p.id.slot != 5
        || p.id.generation != 2
        || status.admitted
        || status.attempts != task::cleanup::MAX_ATTEMPTS
        || status.next_dispatch.is_some()
        || runtime != task::Runtime::default()
        || p.slot.state(p.id) != Ok(task::State::Reclaiming)
    {
        return Err(());
    }
    record(
        serial,
        debugcon,
        "HELD",
        &[
            ("task", 5),
            ("generation", 2),
            ("root", p.root),
            (
                "pages",
                p.slot.reclaim_remaining_pages(p.id).map_err(|_| ())?,
            ),
            ("children", job.child_count() as u64),
            ("writes", p.memory.physical_write_count()),
            ("calls", p.slot.outcome(p.id).map_err(|_| ())?.syscalls),
            ("ticks", runtime.charged_ticks),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
    Ok(())
}

#[cfg(feature = "development-app-cleanup-exhaustion")]
pub(super) fn exhausted_observation(
    p: &Peer,
    scheduler: &scheduler::Scheduler,
    job: &ManagedJob<'_>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    let Some(status) = p.slot.cleanup_status(p.id).map_err(|_| ())? else {
        return Ok(());
    };
    if status.next_dispatch.is_some() {
        return Ok(());
    }
    let id = scheduler::TaskId::new(p.id.slot, p.id.generation).map_err(|_| ())?;
    let scheduled = scheduler.task_snapshot(id).map_err(|_| ())?;
    let runtime = p.slot.runtime(p.id).map_err(|_| ())?;
    if status.attempts != task::cleanup::MAX_ATTEMPTS
        || !status.admitted
        || p.slot.state(p.id) != Ok(task::State::Reclaiming)
        || scheduled.wait_kind != scheduler::WaitKind::Reclamation
        || scheduled.runtime_ticks != runtime.charged_ticks
        || runtime.pending_ticks.is_some()
        || runtime.unknown
        || job.child_count() != 2
    {
        return Err(());
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:EXHAUST HOLD contract=PCLEANUP3");
    for (name, value) in [
        ("task", u64::from(p.id.slot)),
        ("generation", u64::from(p.id.generation)),
        ("attempts", u64::from(status.attempts)),
        (
            "pages",
            p.slot.reclaim_remaining_pages(p.id).map_err(|_| ())?,
        ),
        ("writes", p.memory.physical_write_count()),
        ("calls", p.slot.outcome(p.id).map_err(|_| ())?.syscalls),
        ("ticks", runtime.charged_ticks),
        ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ("children", job.child_count() as u64),
    ] {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(value);
    }
    log.write_str(" cpl=0 production=0\n");
    Ok(())
}

fn observation(
    p: &Peer,
    scheduler: &scheduler::Scheduler,
    event: &str,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    let s = p.slot.cleanup_status(p.id).map_err(|_| ())?.ok_or(())?;
    let pages = p.slot.reclaim_remaining_pages(p.id).map_err(|_| ())?;
    cleanup_record(
        serial,
        debugcon,
        event,
        p.id,
        s.attempts,
        s.next_dispatch.unwrap_or(0),
        pages,
        scheduler.summary().dispatch_count,
        s.admitted,
    );
    Ok(())
}

fn cleanup_record(
    serial: &mut Com1,
    debugcon: &mut DebugCon,
    event: &str,
    id: poolekernel::scheduler_smp::TaskId,
    attempts: u8,
    next: u32,
    pages: u64,
    dispatches: u32,
    admitted: bool,
) {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:CLEANUP ");
    log.write_str(event);
    log.write_str(" contract=PCLEANUP2");
    for (name, value) in [
        ("task", u64::from(id.slot)),
        ("generation", u64::from(id.generation)),
        ("attempts", u64::from(attempts)),
        ("next", u64::from(next)),
        ("pages", pages),
        ("dispatches", u64::from(dispatches)),
        ("admitted", u64::from(admitted)),
    ] {
        log.write_str(" ");
        log.write_str(name);
        log.write_str("=");
        log.write_decimal_u64(value);
    }
    log.write_str(" cpl=0 production=0\n");
}

#[cfg(any(
    feature = "development-shell-cleanup-retry",
    feature = "development-launch-failure"
))]
struct FaultMemory<'a> {
    inner: &'a mut Memory,
    mode: u8,
    fired: bool,
}

#[cfg(any(
    feature = "development-shell-cleanup-retry",
    feature = "development-launch-failure"
))]
impl TableMemory for FaultMemory<'_> {
    fn prepare_page(&mut self, address: u64) -> Result<(), Error> {
        self.inner.prepare_page(address)
    }
    fn read_entry(&mut self, address: u64, index: usize) -> Result<u64, Error> {
        let value = self.inner.read_entry(address, index)?;
        if !self.fired && self.mode == 3 {
            self.fired = true;
            return Err(Error::MemoryAccess);
        }
        Ok(value)
    }
    fn write_entry(&mut self, address: u64, index: usize, value: u64) -> Result<(), Error> {
        if !self.fired && self.mode == 2 {
            self.fired = true;
            return self.inner.write_entry(address, index, value ^ 1);
        }
        self.inner.write_entry(address, index, value)?;
        if !self.fired && self.mode == 1 {
            self.fired = true;
            return Err(Error::MemoryAccess);
        }
        Ok(())
    }
    fn finish(&mut self) -> Result<(), Error> {
        self.inner.finish()?;
        if !self.fired && self.mode == 4 {
            self.fired = true;
            return Err(Error::MemoryAccess);
        }
        Ok(())
    }
    fn physical_write_count(&self) -> u64 {
        self.inner.physical_write_count()
    }
    fn temporary_pte_write_count(&self) -> u64 {
        self.inner.temporary_pte_write_count()
    }
    fn hardware_invalidation_count(&self) -> u64 {
        self.inner.hardware_invalidation_count()
    }
}
