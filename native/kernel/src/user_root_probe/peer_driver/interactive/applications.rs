//! Actual late-bound grants for the opt-in application session.
use super::*;
use poolekernel::development_apps;

pub(super) fn file_wait(
    p: &Peer,
    event: &str,
    calls: u64,
    scheduler: &scheduler::Scheduler,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    // Diagnostic requesters have their own cancellation/death observation contract.
    if p.id.slot < 4
        || cfg!(any(
            feature = "development-file-controls",
            feature = "development-claimed-requester",
            feature = "development-app-cleanup-exhaustion"
        ))
    {
        return Ok(());
    }
    let state = unsafe { arch::x86_64::user_ipc::with_waits(|s| s.request_snapshot(p.id)) }
        .map_err(|_| ())?;
    record(
        serial,
        debugcon,
        event,
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("calls", calls),
            ("queued", u64::from(state.queued)),
            ("claimed", u64::from(state.claimed)),
            ("completed", u64::from(state.completed)),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
    Ok(())
}

#[cfg(feature = "development-file-controls")]
pub(super) fn requester_snapshot(
    p: &Peer,
    outcome: task::Outcome,
) -> Result<poolekernel::capability_ipc::request::Snapshot, ()> {
    if outcome.reason != Reason::Exit(85) || p.id.slot != 4 {
        return Err(());
    }
    let state = unsafe { arch::x86_64::user_ipc::with_waits(|s| s.request_snapshot(p.id)) }
        .map_err(|_| ())?;
    if state.queued + state.claimed != 1 || state.completed != 0 {
        return Err(());
    }
    Ok(state)
}

#[cfg(any(
    feature = "development-file-controls",
    feature = "development-claimed-requester"
))]
pub(super) fn requester_retired(
    p: &Peer,
    state: poolekernel::capability_ipc::request::Snapshot,
    scheduler: &scheduler::Scheduler,
    serial: &mut Com1,
    debugcon: &mut DebugCon,
) -> Result<(), ()> {
    let detached =
        unsafe { arch::x86_64::user_ipc::with_waits(|s| Ok(s.request_snapshot(p.id).is_err())) }
            .map_err(|_| ())?;
    if !detached {
        return Err(());
    }
    record(
        serial,
        debugcon,
        "REQUESTER",
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("queued", u64::from(state.queued)),
            ("claimed", u64::from(state.claimed)),
            ("completed", u64::from(state.completed)),
            ("detached", 1),
            ("dispatches", u64::from(scheduler.summary().dispatch_count)),
        ],
    );
    Ok(())
}

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
    #[cfg(feature = "development-windows")]
    {
        args[2] = Arguments::new(&[
            b"window-console",
            b"0000000100040001",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000003",
            b"0000000100010003",
        ])
        .map_err(|_| ())?;
        args[4] = development_apps::window_arguments(4, 0, 0, 0).map_err(|_| ())?;
        args[5] = development_apps::window_arguments(5, 0, 0, 0).map_err(|_| ())?;
    }
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
    if grants.len()
        != if cfg!(feature = "development-windows") {
            3
        } else {
            2
        }
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
    #[cfg(not(feature = "development-windows"))]
    let replacement =
        development_apps::arguments(u16::from(p.id.slot), grants[0], files).map_err(|_| ())?;
    #[cfg(feature = "development-windows")]
    let replacement =
        development_apps::window_arguments(u16::from(p.id.slot), grants[0], files, grants[2])
            .map_err(|_| ())?;
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
    #[cfg(feature = "development-windows")]
    record(
        serial,
        debugcon,
        "SURFACE",
        &[
            ("task", u64::from(p.id.slot)),
            ("generation", u64::from(p.id.generation)),
            ("send", grants[2]),
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
