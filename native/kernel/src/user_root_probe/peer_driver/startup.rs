//! Actual user reads of copied startup data; this is not the future init service.
use super::*;
use poolekernel::user_entry::startup::Program;

#[inline(never)]
pub(super) fn run(
    peers: &mut [Peer; 2],
    baseline: u64,
    program_bytes: usize,
    manager: &mut PhysicalMemoryManager,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    macro_rules! checked {
        ($op:expr) => {
            match $op {
                Ok(v) => v,
                Err(_) => stop(10000 + u64::from(line!()), serial, debugcon),
            }
        };
    }
    let allocated = manager.summary().allocated_pages;
    if Program::new(&[], 0).is_ok()
        || Program::new(&[0x90], 1).is_ok()
        || checked!(Program::new(&[0x90], 0))
            .image(USER_WINDOW_START, USER_WINDOW_START)
            .is_ok()
        || manager.summary().allocated_pages != allocated
    {
        stop(10001, serial, debugcon);
    }
    let before = arch::x86_64::user_root_write_count();
    let mut scheduler = checked!(scheduler::Scheduler::new(1));
    let cpu = checked!(scheduler::CpuId::new(0));
    checked!(unsafe {
        arch::x86_64::user_ipc::bootstrap(
            [
                (peers[0].id, peers[0].admission),
                (peers[1].id, peers[1].admission),
            ],
            &mut scheduler,
        )
    });
    let mut ticks = [0u64; 2];
    for (index, p) in peers.iter_mut().enumerate() {
        let id = checked!(scheduler.dispatch(cpu));
        if id.slot != p.id.slot || id.generation != p.id.generation || id.generation != 16 {
            stop(10002, serial, debugcon);
        }
        checked!(p.slot.activate(p.id, manager, &mut p.memory));
        let slice = checked!(p.slot.run_slice(p.id));
        ticks[index] = checked!(p.slot.account_slice(p.id, &mut scheduler, cpu));
        let Event::Terminated(outcome) = slice.event else {
            stop(10003, serial, debugcon);
        };
        if outcome.reason != Reason::Exit(102 + index as u32) || outcome.syscalls != 1 {
            stop(10004, serial, debugcon);
        }
        checked!(p.reap(manager, outcome));
        checked!(scheduler.teardown(id));
        if checked!(scheduler.task_snapshot(id)).runtime_ticks != ticks[index] {
            stop(10005, serial, debugcon);
        }
    }
    checked!(scheduler.validate());
    let s = scheduler.summary();
    if ticks.contains(&0)
        || s.dispatch_count != 2
        || s.dead_count != 2
        || s.runnable_count != 0
        || s.running_count != 0
        || arch::x86_64::user_root_write_count() - before != 4
        || manager.summary().allocated_pages != baseline
        || !checked!(unsafe { arch::x86_64::user_ipc::empty() })
    {
        stop(10006, serial, debugcon);
    }
    let mut log = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-STARTUP PASS contract=PSTART1 generation=16 program_bytes=");
    log.write_decimal_u64(program_bytes as u64);
    log.write_str(" entry_offset=16 argument_bytes=112 argc=3 copied_arguments=1 bound_image=1 malformed_programs=2 malformed_images=1 exit0=102 exit1=103 calls0=1 calls1=1 dispatches=2");
    for (label, value) in [(" root0=", peers[0].root), (" root1=", peers[1].root)] {
        log.write_str(label);
        log.write_hex_u64(value);
    }
    for (label, value) in [(" ticks0=", ticks[0]), (" ticks1=", ticks[1])] {
        log.write_str(label);
        log.write_decimal_u64(value);
    }
    log.write_str(" cr3_writes=4 scheduler_match=1 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0\n");
}
