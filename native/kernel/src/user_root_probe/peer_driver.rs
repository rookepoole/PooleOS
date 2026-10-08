//! Existing PKSCHED1 queues drive actual private-root CPL3 quanta, not a transcript.
use super::*;
use poolekernel::{
    scheduler,
    scheduler_smp::TaskId,
    user_entry::task::{self, Event, Reason, Slot},
};
use timer_driver::{PeerRun, Timer};

struct Peer {
    slot: Slot<arch::x86_64::UserRootCpu, PeerRun>,
    id: TaskId,
    memory: Memory,
    handles: [AllocationHandle; 5],
    image: InitialImage,
    root: u64,
}
impl Peer {
    fn new(
        index: u8,
        kind: usize,
        handoff: &Handoff<'_>,
        core: CoreRecord,
        bits: u8,
        manager: &mut PhysicalMemoryManager,
        topology: interrupt_time::MadtTopology,
        hpet: interrupt_time::HpetDescription,
    ) -> Result<Self, ()> {
        let tables = manager
            .allocate(Zone::Dma32, 4, virtual_memory::TABLE_OWNER)
            .map_err(|_| ())?;
        let code = manager
            .allocate(Zone::Dma32, 1, virtual_memory::DATA_OWNER)
            .map_err(|_| ())?;
        let stack = manager
            .allocate(Zone::Dma32, 1, virtual_memory::DATA_OWNER)
            .map_err(|_| ())?;
        let entry_stack = manager
            .allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
            .map_err(|_| ())?;
        let entry_tables = manager
            .allocate(
                Zone::Dma32,
                prepared::STACK_TABLE_PAGES,
                prepared::STACK_TABLE_OWNER,
            )
            .map_err(|_| ())?;
        let handles = [tables, code, stack, entry_stack, entry_tables];
        let mut memory = Memory {
            access: Access::new(manager, core.page_table_root_physical, bits, handles)
                .map_err(|_| ())?,
            root: core.page_table_root_physical,
            bits,
            writes: 0,
        };
        for h in [code, stack, entry_stack] {
            memory.zero(h).map_err(|_| ())?;
        }
        let bytes = arch::x86_64::user::peer_payload(kind).map_err(|_| ())?;
        for (index, chunk) in bytes.chunks(8).enumerate() {
            let mut word = [0; 8];
            word[..chunk.len()].copy_from_slice(chunk);
            let word = u64::from_le_bytes(word);
            memory
                .write_entry(code.start_page * PAGE_BYTES, index + 2, word)
                .map_err(|_| ())?;
            if memory
                .read_entry(code.start_page * PAGE_BYTES, index + 2)
                .map_err(|_| ())?
                != word
            {
                return Err(());
            }
        }
        let mut space = AddressSpace::initialize(manager, tables, &mut memory).map_err(|_| ())?;
        let image = InitialImage {
            code_page: USER_WINDOW_START,
            entry: USER_WINDOW_START + 16,
            stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
        };
        space
            .map(
                manager,
                &mut memory,
                image.code_page,
                code,
                Permissions::USER_RX,
                CachePolicy::WriteBack,
            )
            .map_err(|_| ())?;
        space
            .map(
                manager,
                &mut memory,
                image.stack_page,
                stack,
                Permissions::USER_RW,
                CachePolicy::WriteBack,
            )
            .map_err(|_| ())?;
        let timer = Timer::new(handoff, topology, hpet, bits).map_err(|_| ())?;
        let prepared = PreparedImage::prepare_with_timer(
            DetachedImage {
                space,
                stack: entry_stack,
                stack_tables: entry_tables,
            },
            manager,
            &mut memory,
            image,
            core,
            bits,
            timer.mappings(),
        )
        .map_err(|_| ())?;
        let root = prepared.admission().ok_or(())?.root_physical;
        // SAFETY: exclusive BSP, IF0, before any task activation; both roots remain owned.
        let entry = unsafe { arch::x86_64::user::PeerEntry::new(core.initial_stack_top_virtual) }
            .map_err(|_| ())?;
        let cpu = unsafe { arch::x86_64::UserRootCpu::new(core.page_table_root_physical, root) };
        let mut slot = Slot::new(index).map_err(|_| ())?;
        let id = slot
            .insert(CpuImage::new(prepared, cpu, core), PeerRun { entry, timer })
            .map_err(|_| ())?;
        Ok(Self {
            slot,
            id,
            memory,
            handles,
            image,
            root,
        })
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
        let (mut parts, observed) = self
            .slot
            .reap(self.id, manager, &mut self.memory)
            .map_err(|_| ())?;
        if observed != expected || self.slot.reap(self.id, manager, &mut self.memory).is_ok() {
            return Err(());
        }
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
    for round in 0..4 {
        let first_kind = if round == 3 { 4 } else { round };
        let mut peers = [
            checked!(
                100,
                Peer::new(0, first_kind, handoff, core, bits, manager, topology, hpet)
            ),
            checked!(
                101,
                Peer::new(1, 3, handoff, core, bits, manager, topology, hpet)
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
            let slice = checked!(107, peer.slot.run_slice(peer.id));
            let mut terminated = None;
            match slice.event {
                Event::Preempted {
                    ticks: elapsed,
                    syscalls,
                    progress: now,
                } => {
                    if now <= progress[index] || syscalls != 0 {
                        stop(108, serial, debugcon);
                    }
                    progress[index] = now;
                    preemptions[index] += 1;
                    ticks[index] = checked!(108, ticks[index].checked_add(elapsed).ok_or(()));
                    checked!(109, scheduler.account_tick(cpu, elapsed));
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
                        _ => false,
                    }
                };
                if !valid || (index == 1 && !dead[0]) {
                    stop(113, serial, debugcon);
                }
                checked!(114, scheduler.teardown(scheduled));
                checked!(115, peer.reap(manager, outcome));
                dead[index] = true;
                if index == 0 {
                    first_reason = Some(outcome.reason);
                }
            }
        }
        checked!(116, scheduler.validate());
        let summary = scheduler.summary();
        let writes = arch::x86_64::user_root_write_count() - before;
        if dead != [true; 2]
            || preemptions[0] < 1
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
            _ => stop(119, serial, debugcon),
        };
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER9 scheduler=PKSCHED1 round=");
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
        log.write_str(" survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
    }
}
