//! Native terminal cleanup keeps the task slot occupied until every page is freed.
use super::*;

pub(super) fn reap(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &mut scheduler::Scheduler,
    outcome: task::Outcome,
    pages: u64,
    admitted: bool,
    mut job: Option<&mut task::job::Job<2>>,
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
    observation(p, scheduler, "DEFER", serial, debugcon)
}

pub(super) fn poll(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &scheduler::Scheduler,
    job: &mut task::job::Job<2>,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<task::cleanup::Progress, ()> {
    let status = p.slot.cleanup_status(p.id).map_err(|_| ())?.ok_or(())?;
    let result;
    #[cfg(feature = "development-shell-deferred-cleanup")]
    if p.id.slot >= 4 && status.attempts == 0 {
        let mut memory = FaultMemory {
            inner: &mut p.memory,
            mode: 4,
            fired: false,
        };
        result = job
            .reclaim_deferred_child(&mut p.slot, p.id, manager, &mut memory, scheduler)
            .map_err(|_| ())?;
        if !memory.fired || result != task::cleanup::Progress::Retried {
            return Err(());
        }
    } else {
        result = retry(p, manager, scheduler, job)?;
    }
    #[cfg(not(feature = "development-shell-deferred-cleanup"))]
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
    job: &mut task::job::Job<2>,
) -> Result<task::cleanup::Progress, ()> {
    if p.id.slot >= 4 {
        job.reclaim_deferred_child(&mut p.slot, p.id, manager, &mut p.memory, scheduler)
    } else {
        p.slot
            .reclaim_deferred(p.id, manager, &mut p.memory, scheduler)
    }
    .map_err(|_| ())
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

#[cfg(feature = "development-shell-cleanup-retry")]
struct FaultMemory<'a> {
    inner: &'a mut Memory,
    mode: u8,
    fired: bool,
}

#[cfg(feature = "development-shell-cleanup-retry")]
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
