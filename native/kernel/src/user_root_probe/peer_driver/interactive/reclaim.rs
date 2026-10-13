//! Native terminal cleanup keeps the task slot occupied until every page is freed.
use super::*;

pub(super) fn reap(
    p: &mut Peer,
    manager: &mut PhysicalMemoryManager,
    scheduler: &scheduler::Scheduler,
    outcome: task::Outcome,
    pages: u64,
    admitted: bool,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
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
        let result = p.slot.reclaim(p.id, manager, &mut memory);
        if !memory.fired
            || !matches!(result, Err(task::Error::Reclamation(_)))
            || p.slot.state(p.id) != Ok(task::State::Reclaiming)
            || p.slot.reclaim_remaining_pages(p.id) != Ok(pages)
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
    let _ = (scheduler, pages, admitted, serial, debugcon);
    if p.slot
        .reclaim(p.id, manager, &mut p.memory)
        .map_err(|_| ())?
        != outcome
        || p.slot.state(p.id) != Err(task::Error::Missing)
    {
        return Err(());
    }
    Ok(())
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
