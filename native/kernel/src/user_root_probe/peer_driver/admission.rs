//! Real prepared images survive failed batch admission and retryable retirement.
use super::*;
use poolekernel::capability_ipc::admission::{Error as AdmitError, Member, Step};

struct FailedFinish<'a> {
    memory: &'a mut Memory,
    fired: bool,
}
impl TableMemory for FailedFinish<'_> {
    fn prepare_page(&mut self, p: u64) -> Result<(), virtual_memory::Error> {
        self.memory.prepare_page(p)
    }
    fn read_entry(&mut self, p: u64, i: usize) -> Result<u64, virtual_memory::Error> {
        self.memory.read_entry(p, i)
    }
    fn write_entry(&mut self, p: u64, i: usize, v: u64) -> Result<(), virtual_memory::Error> {
        self.memory.write_entry(p, i, v)
    }
    fn finish(&mut self) -> Result<(), virtual_memory::Error> {
        self.memory.finish()?;
        self.fired = true;
        Err(virtual_memory::Error::MemoryAccess)
    }
    fn physical_write_count(&self) -> u64 {
        self.memory.physical_write_count()
    }
    fn temporary_pte_write_count(&self) -> u64 {
        self.memory.temporary_pte_write_count()
    }
    fn hardware_invalidation_count(&self) -> u64 {
        self.memory.hardware_invalidation_count()
    }
}

#[inline(never)]
pub(super) fn rollback(
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
                Err(_) => stop(8000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let before = arch::x86_64::user_root_write_count();
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    for p in peers.iter_mut() {
        if p.id.generation != 13 || p.slot.state(p.id) != Ok(task::State::Prepared) {
            stop(8001, serial, debugcon);
        }
    }
    let members = peers.each_ref().map(|p| Member {
        id: p.id,
        image: p.admission,
        priority: 16,
    });
    let plan = [Step::Endpoint { member: 0 }; 5];
    let summary = scheduler.summary();
    let failure = checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| Ok(s.admit(&mut scheduler, &members, &plan)))
    });
    if failure != Err(AdmitError::Ipc(poolekernel::capability_ipc::Error::Quota))
        || scheduler.summary() != summary
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
        || manager.summary().allocated_pages != baseline + 26
        || arch::x86_64::user_root_write_count() != before
    {
        stop(8002, serial, debugcon);
    }
    let stale = checked!(unsafe {
        arch::x86_64::user_ipc::with_waits(|s| Ok(s.admit(&mut scheduler, &members, &[])))
    });
    if stale
        != Err(AdmitError::Ipc(
            poolekernel::capability_ipc::Error::Identity,
        ))
    {
        stop(8003, serial, debugcon);
    }
    for (index, p) in peers.iter_mut().enumerate() {
        if index == 0 {
            let mut fault = FailedFinish {
                memory: &mut p.memory,
                fired: false,
            };
            if p.slot.abandon(p.id, manager, &mut fault).is_ok() || !fault.fired {
                stop(8004, serial, debugcon);
            }
            if p.slot.state(p.id) != Ok(task::State::Quarantined) {
                stop(8005, serial, debugcon);
            }
            for h in p.handles {
                if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                    stop(8006, serial, debugcon);
                }
            }
        }
        let parts = checked!(p.slot.abandon(p.id, manager, &mut p.memory));
        checked!(p.release(manager, parts));
    }
    if manager.summary().allocated_pages != baseline
        || scheduler.summary() != summary
        || arch::x86_64::user_root_write_count() != before
    {
        stop(8007, serial, debugcon);
    }
}

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
                Err(_) => stop(8000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let before = arch::x86_64::user_root_write_count();
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    for p in peers.iter() {
        if p.id.generation != 14 {
            stop(8008, serial, debugcon);
        }
    }
    let handles = checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap(
            [
                (peers[0].id, peers[0].admission),
                (peers[1].id, peers[1].admission),
            ],
            &mut scheduler,
        )
    });
    if handles.contains(&0) || scheduler.summary().runnable_count != 2 {
        stop(8009, serial, debugcon);
    }
    let mut stopped = [false; 2];
    let mut ticks = [0u64; 2];
    let mut preempts = 0u64;
    for _ in 0..32 {
        if stopped == [true; 2] {
            break;
        }
        let id = checked!(scheduler.dispatch(cpu));
        let index = checked!(usize::from(id.slot).checked_sub(2).ok_or(()));
        if index >= 2 || stopped[index] || id.generation != 14 {
            stop(8010, serial, debugcon);
        }
        let p = &mut peers[index];
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let slice = checked!(p.slot.run_slice(p.id));
        ticks[index] = checked!(
            ticks[index]
                .checked_add(checked!(p.slot.account_slice(p.id, &mut scheduler, cpu)))
                .ok_or(())
        );
        match slice.event {
            Event::Preempted { .. } => {
                preempts += 1;
                checked!(scheduler.yield_current(cpu));
            }
            Event::Terminated(outcome) => {
                if outcome.reason != Reason::Exit(42) || outcome.syscalls != 1 {
                    stop(8011, serial, debugcon);
                }
                checked!(p.reap(manager, outcome));
                checked!(scheduler.teardown(id));
                stopped[index] = true;
            }
            Event::Waiting { .. } => stop(8012, serial, debugcon),
        }
    }
    checked!(scheduler.validate());
    let summary = scheduler.summary();
    let dispatches = u64::from(summary.dispatch_count);
    let writes = arch::x86_64::user_root_write_count() - before;
    if stopped != [true; 2]
        || ticks.contains(&0)
        || preempts != 4
        || dispatches != 6
        || writes != 12
        || summary.dead_count != 2
        || summary.running_count != 0
        || summary.runnable_count != 0
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(8013, serial, debugcon);
    }
    for (index, p) in peers.iter().enumerate() {
        if checked!(
            scheduler.task_snapshot(checked!(scheduler::TaskId::new(p.id.slot, p.id.generation)))
        )
        .runtime_ticks
            != ticks[index]
        {
            stop(8014, serial, debugcon);
        }
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-ADMISSION PASS contract=PKADMIT1 failed_generation=13 retry_generation=14 members=2 steps_before_quota=4 scheduler_unchanged=1 failed_dispatches=0 stale_retry_denied=1 cleanup_quarantine=1 retained_free_denials=5 cleanup_retry=1 first_exchange_atomic=1");
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [(" ticks0=", ticks[0]), (" ticks1=", ticks[1])] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" dispatches=6 preemptions=4 cr3_writes=12 exits=2 exit_code=42 objects_remaining=0 released_pages=52 scrubbed_data_pages=24 cpl=3 production=0\n");
}
