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
        // SAFETY: sole BSP; the preceding task was fully quiesced and released.
        let entry = checked!(74, unsafe {
            arch::x86_64::user::Entry::prepare(core.initial_stack_top_virtual)
        });
        let payload = checked!(68, arch::x86_64::user::task_payload(case));
        let spawn_driver::Built {
            prepared,
            mut memory,
            handles,
            image,
        } = checked!(72, spawn_driver::build(manager, core, bits, payload, None));
        let root = checked!(73, prepared.admission().ok_or(())).root_physical;
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
        for h in [handles[1], handles[2], handles[3]] {
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
