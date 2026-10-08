//! Four independently owned sequential task lifetimes, not peer scheduling.
use super::*;
use poolekernel::user_entry::task::{self, Reason, Slot};

pub fn run_all(
    core: CoreRecord,
    bits: u8,
    manager: &mut PhysicalMemoryManager,
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
    let baseline_pages = manager.summary().allocated_pages;
    let mut slot = checked!(60, Slot::new(0));
    let mut previous = None;
    for case in 0..4 {
        let tables = checked!(
            61,
            manager.allocate(Zone::Dma32, 4, virtual_memory::TABLE_OWNER)
        );
        let code = checked!(
            62,
            manager.allocate(Zone::Dma32, 1, virtual_memory::DATA_OWNER)
        );
        let stack = checked!(
            63,
            manager.allocate(Zone::Dma32, 1, virtual_memory::DATA_OWNER)
        );
        let entry_stack = checked!(
            64,
            manager.allocate(Zone::Dma32, STACK_PAGE_COUNT, STACK_OWNER)
        );
        let entry_tables = checked!(
            65,
            manager.allocate(
                Zone::Dma32,
                prepared::STACK_TABLE_PAGES,
                prepared::STACK_TABLE_OWNER
            )
        );
        let handles = [tables, code, stack, entry_stack, entry_tables];
        let mut memory = Memory {
            access: checked!(
                66,
                Access::new(manager, core.page_table_root_physical, bits, handles)
            ),
            root: core.page_table_root_physical,
            bits,
            writes: 0,
        };
        for h in [code, stack, entry_stack] {
            checked!(67, memory.zero(h));
        }
        let payload = checked!(68, arch::x86_64::user::task_payload(case));
        for (index, bytes) in payload.chunks(8).enumerate() {
            let mut word = [0; 8];
            word[..bytes.len()].copy_from_slice(bytes);
            let word = u64::from_le_bytes(word);
            checked!(
                68,
                memory.write_entry(code.start_page * PAGE_BYTES, index + 2, word)
            );
            if checked!(
                68,
                memory.read_entry(code.start_page * PAGE_BYTES, index + 2)
            ) != word
            {
                stop(68, serial, debugcon);
            }
        }
        let mut space = checked!(69, AddressSpace::initialize(manager, tables, &mut memory));
        let image = InitialImage {
            code_page: USER_WINDOW_START,
            entry: USER_WINDOW_START + 16,
            stack_page: USER_WINDOW_START + 3 * PAGE_BYTES,
        };
        checked!(
            70,
            space.map(
                manager,
                &mut memory,
                image.code_page,
                code,
                Permissions::USER_RX,
                CachePolicy::WriteBack
            )
        );
        checked!(
            71,
            space.map(
                manager,
                &mut memory,
                image.stack_page,
                stack,
                Permissions::USER_RW,
                CachePolicy::WriteBack
            )
        );
        let prepared = checked!(
            72,
            PreparedImage::prepare(
                DetachedImage {
                    space,
                    stack: entry_stack,
                    stack_tables: entry_tables
                },
                manager,
                &mut memory,
                image,
                core,
                bits
            )
        );
        let root = checked!(73, prepared.admission().ok_or(())).root_physical;
        // SAFETY: same sole-BSP profile; previous task was fully quiesced and released.
        let entry = checked!(74, unsafe {
            arch::x86_64::user::Entry::prepare(core.initial_stack_top_virtual)
        });
        let hardware =
            unsafe { arch::x86_64::UserRootCpu::new(core.page_table_root_physical, root) };
        let id = checked!(
            75,
            slot.insert(CpuImage::new(prepared, hardware, core), entry)
        );
        if let Some(old) = previous {
            if slot.run(old) != Err(task::Error::Identity) {
                stop(76, serial, debugcon);
            }
        }
        checked!(77, slot.activate(id, manager, &mut memory));
        let outcome = checked!(78, slot.run(id));
        let (kind, value) = match (case, outcome.reason) {
            (0, Reason::Exit(42)) if outcome.syscalls == 2 => ("exit", 42),
            (1, Reason::Fault(f)) if f.vector == 6 && f.error == 0 && outcome.syscalls == 0 => {
                ("fault", 6)
            }
            (2, Reason::Fault(f)) if f.vector == 13 && f.error == 0 && outcome.syscalls == 0 => {
                ("fault", 13)
            }
            (3, Reason::Fault(f))
                if f.vector == 14
                    && f.error == 5
                    && f.address == virtual_memory::KERNEL_IMAGE_START
                    && outcome.syscalls == 0 =>
            {
                ("fault", 14)
            }
            _ => stop(79, serial, debugcon),
        };
        if slot.run(id) != Err(task::Error::State) {
            stop(80, serial, debugcon);
        }
        for h in handles {
            if manager.free(h) != Err(PhysicalMemoryError::AllocationRetained) {
                stop(81, serial, debugcon);
            }
        }
        let (mut parts, reaped) = checked!(82, slot.reap(id, manager, &mut memory));
        if reaped != outcome
            || slot.state(id) != Err(task::Error::Missing)
            || slot.reap(id, manager, &mut memory).is_ok()
        {
            stop(83, serial, debugcon);
        }
        for h in [code, stack, entry_stack] {
            checked!(84, memory.zero(h));
        }
        for address in [image.code_page, image.stack_page] {
            let token = checked!(85, parts.space.begin_unmap(&mut memory, address));
            checked!(86, parts.space.acknowledge_inactive(token));
            if !checked!(87, parts.space.complete_unmap(manager, token)) {
                stop(87, serial, debugcon);
            }
        }
        checked!(88, parts.space.release(manager, &mut memory));
        checked!(89, manager.free(parts.stack));
        checked!(90, manager.free(parts.stack_tables));
        checked!(91, memory.finish());
        if manager.summary().allocated_pages != baseline_pages {
            stop(92, serial, debugcon);
        }
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-TASK PASS contract=PKUSER8 slot=0 generation=");
        log.write_decimal_u64(u64::from(id.generation));
        log.write_str(" root=");
        log.write_hex_u64(root);
        log.write_str(" reason=");
        log.write_str(kind);
        log.write_str(" value=");
        log.write_decimal_u64(value);
        log.write_str(" syscalls=");
        log.write_decimal_u64(u64::from(outcome.syscalls));
        log.write_str(" cpl=3 stale_denials=");
        log.write_decimal_u64(u64::from(previous.is_some()));
        log.write_str(" restart_denied=1 repeat_reap_denied=1 retained_free_denials=5 entry_quiesced=1 root_restored=1 released_pages=13 scrubbed_data_pages=6 production=0\n");
        previous = Some(id);
    }
}
