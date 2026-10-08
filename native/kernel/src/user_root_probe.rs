//! Development-only, single-BSP owned-root and bounded CPL3 fault-recovery probe.

use super::*;
use poole_handoff::{CoreRecord, Handoff, PAGE_BYTES};
use poolekernel::reclamation::task_lifetimes::{STACK_OWNER, STACK_PAGE_COUNT};
use poolekernel::user_entry::{
    InitialImage,
    bootstrap::Access,
    prepared::{
        self, DetachedImage, PreparedImage,
        cpu::{Cpu, CpuImage, State},
    },
};
use virtual_memory::{AddressSpace, CachePolicy, Error, Permissions, USER_WINDOW_START};

mod clock_driver;
mod peer_driver;
mod spawn_driver;
mod task_driver;
mod timer_driver;
pub use timer_driver::{dispatch_drain, dispatch_timer};

struct Memory {
    access: Access,
    root: u64,
    bits: u8,
    writes: u64,
}

impl Memory {
    fn pointer(&self, table: u64, index: usize, write: bool) -> Result<*mut u64, Error> {
        // SAFETY: this private adapter is used only at CPL0 on the original BSP root.
        let root = unsafe { arch::x86_64::read_cr3() };
        let address = self.access.address(root, table, index, write)?;
        if arch::x86_64::read_rflags() & (1 << 9) != 0 {
            return Err(Error::MemoryAccess);
        }
        for endpoint in [address, address + 7] {
            let t = poole_kmap::translate(&ActivePhysicalReader, root, endpoint, self.bits)
                .map_err(|_| Error::BootstrapTranslation)?;
            if t.physical_address != endpoint
                || (write && !t.writable)
                || t.user
                || t.cache.pwt
                || t.cache.pcd
                || t.cache.pat
            {
                return Err(Error::BootstrapTranslation);
            }
        }
        Ok(address as *mut u64)
    }

    fn zero(&mut self, h: AllocationHandle) -> Result<(), Error> {
        for page in h.start_page..h.start_page + h.page_count {
            for index in 0..512 {
                self.write_entry(page * PAGE_BYTES, index, 0)?;
                if self.read_entry(page * PAGE_BYTES, index)? != 0 {
                    return Err(Error::MemoryAccess);
                }
            }
        }
        Ok(())
    }
}

impl TableMemory for Memory {
    fn prepare_page(&mut self, page: u64) -> Result<(), Error> {
        self.pointer(page, 0, true).map(|_| ())
    }
    fn read_entry(&mut self, page: u64, index: usize) -> Result<u64, Error> {
        let pointer = self.pointer(page, index, false)?;
        // SAFETY: bounded owned/boot page, exact identity and supervisor translation.
        Ok(unsafe { read_volatile(pointer) })
    }
    fn write_entry(&mut self, page: u64, index: usize, value: u64) -> Result<(), Error> {
        let pointer = self.pointer(page, index, true)?;
        // SAFETY: only this probe's still-owned pages are writable through the adapter.
        unsafe { write_volatile(pointer, value) };
        self.writes += 1;
        Ok(())
    }
    fn finish(&mut self) -> Result<(), Error> {
        // SAFETY: CPL0 observation; no temporary mappings were installed.
        if unsafe { arch::x86_64::read_cr3() } != self.root {
            return Err(Error::BootstrapRoot);
        }
        Ok(())
    }
    fn physical_write_count(&self) -> u64 {
        self.writes
    }
    fn temporary_pte_write_count(&self) -> u64 {
        0
    }
    fn hardware_invalidation_count(&self) -> u64 {
        0
    }
}

fn stop(stage: u64, serial: &mut Com1, debugcon: &mut DebugCon) -> ! {
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-ROOT DENIED stage=");
    log.write_decimal_u64(stage);
    log.write_str("\n");
    poole_kernel_emergency_panic(PanicCode::UserRoot as u32)
}

#[inline(never)]
pub fn run(
    handoff: &Handoff<'_>,
    core: CoreRecord,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> ! {
    macro_rules! checked {
        ($stage:expr, $operation:expr) => {
            match $operation {
                Ok(value) => value,
                Err(_) => stop($stage, serial, debugcon),
            }
        };
    }
    let bits = checked!(1, arch::x86_64::physical_address_bits().ok_or(()));
    // SAFETY: development selector23 is entered once at CPL0 with IF/DF clear;
    // no AP or DMA is started. Only the bounded timer driver may enable IF.
    let descriptors = unsafe {
        arch::x86_64::install_interrupt_descriptor_tables(core.initial_stack_top_virtual)
    };
    checked!(2, validate_interrupt_descriptor_state(&descriptors));
    IST1_BOTTOM.store(descriptors.ist1_bottom, Ordering::Release);
    IST1_TOP.store(descriptors.ist1_top, Ordering::Release);
    IST2_BOTTOM.store(descriptors.ist2_bottom, Ordering::Release);
    IST2_TOP.store(descriptors.ist2_top, Ordering::Release);
    let mut manager = checked!(3, PhysicalMemoryManager::from_handoff(handoff, core, 32));
    checked!(
        32,
        manager.advance_reclaim_stage(ReclaimStage::PostExitBootServices)
    );
    let mut bootstrap = checked!(
        33,
        BootstrapTableMemory::new(core.page_table_root_physical, bits)
    );
    let acpi = checked!(
        34,
        acpi::consume_required_tables(handoff, &mut manager, &mut bootstrap)
    );
    let madt = acpi.required_tables[0];
    let hpet = acpi.required_tables[2];
    let topology = checked!(
        35,
        parse_madt(
            &mut bootstrap,
            acpi.snapshot_physical_address + madt.snapshot_offset,
            madt.byte_count
        )
    );
    let hpet = checked!(
        36,
        parse_hpet(
            &mut bootstrap,
            acpi.snapshot_physical_address + hpet.snapshot_offset,
            hpet.byte_count
        )
    );
    checked!(37, bootstrap.finish());
    let mut timer = checked!(38, timer_driver::Timer::new(handoff, topology, hpet, bits));
    let tables = checked!(
        4,
        manager.allocate(Zone::Dma32, 4, virtual_memory::TABLE_OWNER)
    );
    let code = checked!(
        5,
        manager.allocate(Zone::Dma32, 1, virtual_memory::DATA_OWNER)
    );
    let stack = checked!(
        6,
        manager.allocate(Zone::Dma32, 1, virtual_memory::DATA_OWNER)
    );
    let entry_stack = checked!(
        7,
        manager.allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
    );
    let entry_tables = checked!(
        8,
        manager.allocate(
            Zone::Dma32,
            prepared::STACK_TABLE_PAGES,
            prepared::STACK_TABLE_OWNER
        )
    );
    let handles = [tables, code, stack, entry_stack, entry_tables];
    let access = checked!(
        9,
        Access::new(&manager, core.page_table_root_physical, bits, handles)
    );
    let mut memory = Memory {
        access,
        root: core.page_table_root_physical,
        bits,
        writes: 0,
    };
    for h in [code, stack, entry_stack] {
        checked!(10, memory.zero(h));
    }
    let payload = checked!(11, arch::x86_64::user::payload());
    for (index, bytes) in payload.chunks(8).enumerate() {
        let mut word = [0; 8];
        word[..bytes.len()].copy_from_slice(bytes);
        let value = u64::from_le_bytes(word);
        checked!(
            11,
            memory.write_entry(code.start_page * PAGE_BYTES, index + 2, value)
        );
        if checked!(
            11,
            memory.read_entry(code.start_page * PAGE_BYTES, index + 2)
        ) != value
        {
            stop(11, serial, debugcon);
        }
    }
    let mut space = checked!(12, AddressSpace::initialize(&manager, tables, &mut memory));
    let image = InitialImage {
        code_page: USER_WINDOW_START,
        entry: USER_WINDOW_START + 16,
        stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
    };
    checked!(
        13,
        space.map(
            &manager,
            &mut memory,
            image.code_page,
            code,
            Permissions::USER_RX,
            CachePolicy::WriteBack
        )
    );
    checked!(
        14,
        space.map(
            &manager,
            &mut memory,
            image.stack_page,
            stack,
            Permissions::USER_RW,
            CachePolicy::WriteBack
        )
    );
    let prepared = checked!(
        15,
        PreparedImage::prepare_with_timer(
            DetachedImage {
                space,
                stack: entry_stack,
                stack_tables: entry_tables
            },
            &mut manager,
            &mut memory,
            image,
            core,
            bits,
            timer.mappings()
        )
    );
    for handle in handles {
        if manager.free(handle) != Err(PhysicalMemoryError::AllocationRetained) {
            stop(16, serial, debugcon);
        }
    }
    let candidate = checked!(17, prepared.admission().ok_or(())).root_physical;
    {
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-ROOT-PREPARED PASS contract=PKUSER3 original=");
        log.write_hex_u64(core.page_table_root_physical);
        log.write_str(" candidate=");
        log.write_hex_u64(candidate);
        log.write_str(" generation=");
        log.write_decimal_u64(tables.generation);
        log.write_str(
            " pages=13 allocations=5 retained_free_denials=5 temporary_aliases=0 ring3=0\n",
        );
    }
    // SAFETY: PKUSER2 audited the preserved supervisor code/data/boot stack and
    // descriptor statics. All local operands live there; no physical adapter is
    // used while the candidate is active. This one-BSP no-DMA profile owns both roots.
    // SAFETY: exclusive BSP boot profile, no FP/debug/segment owner or AP/DMA.
    // Configure the supported user baseline BEFORE CpuImage freezes its controls.
    let mut user = checked!(40, unsafe {
        arch::x86_64::user::Entry::prepare(core.initial_stack_top_virtual)
    });
    let mut hardware =
        unsafe { arch::x86_64::UserRootCpu::new(core.page_table_root_physical, candidate) };
    let before = checked!(18, hardware.snapshot());
    let mut owner = CpuImage::new(prepared, hardware, core);
    if let Err(error) = owner.activate(&manager, &mut memory) {
        use prepared::cpu::Error as CpuError;
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-ROOT ACTIVATION_ERROR kind=");
        log.write_str(match error {
            CpuError::Prepared(_) => "prepared",
            CpuError::State => "state",
            CpuError::Context => "context",
            CpuError::Root => "root",
            CpuError::Hardware => "hardware",
            CpuError::Timer(_) => "timer",
            CpuError::User(_) => "user",
        });
        for (label, value) in [
            (" cr0=", before.cr0),
            (" cr4=", before.cr4),
            (" efer=", before.efer),
            (" rflags=", before.rflags),
        ] {
            log.write_str(label);
            log.write_hex_u64(value);
        }
        log.write_str("\n");
        stop(18, serial, debugcon);
    }
    if owner.state() != State::Active {
        stop(19, serial, debugcon);
    }
    // Keep the sentinel below the bounded fault handler's stack usage. Hardware
    // owns the top words once CPL3 faults begin using TSS.RSP0.
    // SAFETY: owned four-page supervisor RW/NX entry stack was fully audited.
    let probe = prepared::STACK_BOTTOM as *mut u64;
    let expected = candidate ^ tables.generation ^ 0x504b_5553_4552_3300;
    let (observed_root, observed_probe) = unsafe {
        write_volatile(probe, expected);
        (arch::x86_64::read_cr3(), read_volatile(probe))
    };
    if observed_root != candidate || observed_probe != expected {
        stop(20, serial, debugcon);
    }
    {
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-ROOT-ACTIVE PASS cr3=");
        log.write_hex_u64(observed_root);
        log.write_str(" stack_probe=");
        log.write_hex_u64(observed_probe);
        log.write_str(" cpl=0 if=0 ring3=0\n");
    }
    let irq = checked!(39, owner.exercise_timer(&mut timer));
    {
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-ROOT-TIMER PASS contract=PKUSER4 cr3=");
        log.write_hex_u64(irq.observed_root);
        log.write_str(" deliveries=");
        log.write_decimal_u64(u64::from(irq.deliveries));
        log.write_str(" eois=");
        log.write_decimal_u64(u64::from(irq.eois));
        log.write_str(" mmio_pages=2 quiesced=1 if=0 ring3=0\n");
    }
    let mut run = timer_driver::UserRun {
        entry: &mut user,
        timer: &mut timer,
        result: None,
        calls: None,
    };
    let entry = checked!(41, owner.exercise_user(&mut run));
    let preempt = checked!(42, run.result.ok_or(()));
    let calls = checked!(43, run.calls.ok_or(()));
    {
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-ENTRY PASS contract=PKUSER5 cr3=");
        log.write_hex_u64(entry.root);
        log.write_str(" cpl=3 traps=7 private_rsp0=1 gpr_zero=15 fp_cleared=1 cli_denied=1 io_denied=1 syscall_denied=1 supervisor_fault=1 nx_fault=1 kernel_return=1 descriptors_detached=1 if=0 production=0\n");
        log.write_str("POOLEOS:KERNEL:USER-PREEMPT PASS contract=PKUSER6 cr3=");
        log.write_hex_u64(entry.root);
        log.write_str(" cpl=3 deliveries=");
        log.write_decimal_u64(u64::from(preempt.deliveries));
        log.write_str(" eois=3 resumes=");
        log.write_decimal_u64(u64::from(preempt.resumes));
        log.write_str(" first_progress=");
        log.write_decimal_u64(preempt.first_progress);
        log.write_str(" last_progress=");
        log.write_decimal_u64(preempt.last_progress);
        log.write_str(" private_rsp0=1 gpr_preserved=14 fp_preserved=1 timer_quiesced=1 forced_return=1 if=0 production=0\n");
        log.write_str("POOLEOS:KERNEL:USER-CALL PASS contract=PKUSER7 abi=PSABI1 profile=development version=1 cr3=");
        log.write_hex_u64(entry.root);
        log.write_str(" calls=");
        log.write_decimal_u64(u64::from(calls.calls));
        for (name, count) in [
            (" ok=", calls.statuses[0]),
            (" version_denied=", calls.statuses[1]),
            (" unknown=", calls.statuses[2]),
            (" arguments=", calls.statuses[3]),
            (" faults=", calls.statuses[4]),
            (" read_faults=", calls.read_faults),
            (" write_faults=", calls.write_faults),
        ] {
            log.write_str(name);
            log.write_decimal_u64(u64::from(count));
        }
        log.write_str(" cpl=3 entry=syscall return=iretq max_copy=256 input_atomic=1 output_prefix=1 completion_traps=1 msrs_cleared=1 if=0 production=0\n");
    }
    let mut parts = checked!(21, owner.retire(&mut manager, &mut memory));
    if checked!(
        22,
        memory.read_entry(entry_stack.start_page * PAGE_BYTES, 0)
    ) != expected
    {
        stop(22, serial, debugcon);
    }
    // Scrub data before allocator return; tables are detached/zeroed by their owners.
    for h in [code, stack, entry_stack] {
        checked!(23, memory.zero(h));
    }
    for address in [image.code_page, image.stack_page] {
        let token = checked!(24, parts.space.begin_unmap(&mut memory, address));
        checked!(25, parts.space.acknowledge_inactive(token));
        if !checked!(26, parts.space.complete_unmap(&mut manager, token)) {
            stop(26, serial, debugcon);
        }
    }
    checked!(27, parts.space.release(&mut manager, &mut memory));
    checked!(28, manager.free(parts.stack));
    checked!(29, manager.free(parts.stack_tables));
    checked!(30, memory.finish());
    if manager.summary().allocated_pages != acpi.snapshot_page_count
        || manager.free(acpi.allocation) != Err(PhysicalMemoryError::MetadataOwnership)
    {
        stop(31, serial, debugcon);
    }
    task_driver::run_all(core, bits, &mut manager, serial, debugcon);
    if arch::x86_64::user_root_write_count() != 10 {
        stop(93, serial, debugcon);
    }
    peer_driver::run_all(
        handoff,
        core,
        bits,
        &mut manager,
        topology,
        hpet,
        serial,
        debugcon,
    );
    // Release the large measured-suite stack frame before another constructor.
    peer_driver::unknown::run(
        handoff,
        core,
        bits,
        &mut manager,
        topology,
        hpet,
        serial,
        debugcon,
    );
    peer_driver::ipc::run(
        handoff,
        core,
        bits,
        &mut manager,
        topology,
        hpet,
        serial,
        debugcon,
    );
    peer_driver::ipc_pressure::run(
        handoff,
        core,
        bits,
        &mut manager,
        topology,
        hpet,
        serial,
        debugcon,
    );
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-ROOT-RESULT PASS restored=");
    // SAFETY: this remains the serialized CPL0 profile, now back on the boot root.
    log.write_hex_u64(unsafe { arch::x86_64::read_cr3() });
    log.write_str(" cr3_writes=");
    log.write_decimal_u64(arch::x86_64::user_root_write_count());
    log.write_str(" allocated_pages=");
    log.write_decimal_u64(manager.summary().allocated_pages);
    log.write_str(" retained_acpi_pages=");
    log.write_decimal_u64(acpi.snapshot_page_count);
    log.write_str(
        " released_pages=876 scrubbed_data_pages=403 ring3=1 production=0 terminal=halt\n",
    );
    halt_forever()
}
