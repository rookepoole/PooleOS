//! Actual late-bound grants for the opt-in application session.
use super::*;
use poolekernel::development_apps;

#[inline(never)]
pub(super) fn configure(args: &mut [Arguments; 6]) -> Result<(), ()> {
    args[1] = Arguments::new(&[
        b"app-file-service",
        b"0000000100010001",
        b"0000000100000000",
        b"0000000100000003",
    ])
    .map_err(|_| ())?;
    args[3] = Arguments::new(&[
        b"app-shell",
        b"0000000100010001",
        b"0000000100010002",
        b"0000000100000002",
        b"0000000100060001",
        b"0000000100060002",
        b"0000000100010003",
        b"0000000100000001",
    ])
    .map_err(|_| ())?;
    args[4] = development_apps::arguments(4, 0, 0).map_err(|_| ())?;
    args[5] = development_apps::arguments(5, 0, 0).map_err(|_| ())?;
    Ok(())
}

#[inline(never)]
pub(super) fn handoff(
    p: &mut Peer,
    expected: &Arguments,
    grants: &[u64],
    core: CoreRecord,
    scheduler: &scheduler::Scheduler,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    if grants.len() != 2
        || arch::x86_64::user::active()
        || unsafe { arch::x86_64::read_cr3() } != core.page_table_root_physical
        || arch::x86_64::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
    {
        return Err(());
    }
    let files = if cfg!(feature = "development-applications-bad-file") && p.id.slot == 5 {
        grants[1].checked_add(1 << 32).ok_or(())?
    } else {
        grants[1]
    };
    let replacement =
        development_apps::arguments(u16::from(p.id.slot), grants[0], files).map_err(|_| ())?;
    let startup = p.startup.as_ref().ok_or(())?;
    // Admission has committed. IF0 and the sole dispatcher prevent either parent
    // or child from observing it until the complete owned-byte handoff succeeds.
    // Any error halts with owners retained; this does not roll admission back.
    p.slot
        .replace_startup_arguments(p.id, startup, expected, &replacement, &mut p.memory)
        .map_err(|_| ())?;
    record(
        serial,
        debugcon,
        "HANDOFF",
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("control", grants[0]),
            ("files", grants[1]),
            ("startup_files", files),
            ("bytes", replacement.bytes().len() as u64),
            ("entered", 0),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
    Ok(())
}

pub(super) fn start(
    peers: &[&mut Peer; 6],
    pages: u64,
    baseline: u64,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) {
    record(
        serial,
        debugcon,
        "START",
        &[
            (
                "bad_file",
                u64::from(cfg!(feature = "development-applications-bad-file")),
            ),
            ("init_bytes", INIT.len() as u64),
            ("files_bytes", COUNTER.len() as u64),
            ("console_bytes", CONSOLE.len() as u64),
            ("shell_bytes", SHELL.len() as u64),
            ("text_bytes", TEXT.len() as u64),
            ("numbers_bytes", NUMBERS.len() as u64),
            ("image_pages", pages),
            ("firmware_pages", baseline),
            ("root0", peers[0].root),
            ("root1", peers[1].root),
            ("root2", peers[2].root),
            ("root3", peers[3].root),
            ("root4", peers[4].root),
            ("root5", peers[5].root),
        ],
    );
}
