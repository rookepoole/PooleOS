//! Exclusive BSP adapter; no untrusted device output enters the kernel logger.
use super::*;
use poolekernel::capability_ipc::{
    admission::Member,
    console::{BASE, BytePorts},
};

struct Ports;
impl BytePorts for Ports {
    fn read(&mut self, port: u16) -> u8 {
        // SAFETY: only the authenticated, range-checked lease path calls this.
        unsafe { super::super::inb(port) }
    }
    fn write(&mut self, port: u16, value: u8) {
        unsafe { super::super::outb(port, value) };
    }
}

pub(super) fn quiesce() -> Result<(), Error> {
    idle()?;
    // This resource is exclusively reserved by the development launch profile.
    // Clear DLAB first so the next write addresses IER, never the divisor latch.
    unsafe {
        super::super::outb(BASE + 3, 3);
        super::super::outb(BASE + 1, 0);
        super::super::outb(BASE + 4, 0);
        super::super::outb(BASE + 2, 7);
        if super::super::inb(BASE + 3) != 3
            || super::super::inb(BASE + 1) != 0
            || super::super::inb(BASE + 4) != 0
        {
            return Err(Error::Hardware);
        }
    }
    Ok(())
}

/// SAFETY: exclusive BSP, IF0, prepared owned roots, no dispatched task or AP.
#[cfg(not(feature = "development-console-ipc"))]
pub unsafe fn bootstrap(
    tasks: [(TaskId, ImageAdmission); 3],
    scheduler: &mut poolekernel::scheduler::Scheduler,
) -> Result<[u64; 5], Error> {
    use poolekernel::capability_ipc::admission::Step;
    idle()?;
    let s = unsafe { &mut *(&raw mut IPC) };
    if !s.is_empty() {
        return Err(Error::State);
    }
    let members = tasks.map(|(id, image)| Member {
        id,
        image,
        priority: 16,
    });
    let admitted = s
        .admit(
            scheduler,
            &members,
            &[
                Step::Endpoint { member: 0 },
                Step::Endpoint { member: 1 },
                Step::Grant {
                    endpoint: 1,
                    target: tasks[0].0,
                    rights: Rights::SEND,
                },
                Step::Grant {
                    endpoint: 0,
                    target: tasks[1].0,
                    rights: Rights::SEND,
                },
                Step::Console { member: 2 },
            ],
        )
        .map_err(|_| Error::State)?;
    // No task may run until quiescence succeeds; failure retains all image owners.
    quiesce()?;
    admitted.handles[..5].try_into().map_err(|_| Error::State)
}

pub(crate) fn byte(caller: Caller, handle: u64, offset: u64, value: Option<u64>) -> (Status, u64) {
    // dispatch_owned has authenticated CPL3, saved Run identity, root/depth and IF0.
    unsafe { &mut *(&raw mut IPC) }.console_byte(caller, handle, offset, value, &mut Ports)
}

/// SAFETY: exclusive BSP/IF0, four owned prepared roots, no dispatched task/AP.
#[cfg(feature = "development-files")]
pub unsafe fn bootstrap_files(
    tasks: [(TaskId, ImageAdmission); 4],
    scheduler: &mut poolekernel::scheduler::Scheduler,
) -> Result<[u64; 8], Error> {
    idle()?;
    let s = unsafe { &mut *(&raw mut IPC) };
    if !s.is_empty() {
        return Err(Error::State);
    }
    let members = tasks.map(|(id, image)| Member {
        id,
        image,
        priority: 16,
    });
    #[cfg(not(feature = "development-windows"))]
    let admitted = s
        .admit_file_session(scheduler, &members)
        .map_err(|_| Error::State)?;
    #[cfg(feature = "development-windows")]
    let admitted = s
        .admit_window_session(scheduler, &members)
        .map_err(|_| Error::State)?;
    #[cfg(feature = "development-windows")]
    if admitted.count != 9 || admitted.handles[8] != 0x100010003 {
        return Err(Error::State);
    }
    quiesce()?;
    admitted.handles[..8].try_into().map_err(|_| Error::State)
}

/// SAFETY: exclusive BSP, IF0, four owned prepared roots, no dispatched task/AP.
#[cfg(all(
    feature = "development-console-ipc",
    not(feature = "development-session-capacity"),
    not(feature = "development-files")
))]
pub unsafe fn bootstrap_ipc(
    tasks: [(TaskId, ImageAdmission); 4],
    scheduler: &mut poolekernel::scheduler::Scheduler,
) -> Result<[u64; 9], Error> {
    idle()?;
    let s = unsafe { &mut *(&raw mut IPC) };
    if !s.is_empty() {
        return Err(Error::State);
    }
    let members = tasks.map(|(id, image)| Member {
        id,
        image,
        priority: 16,
    });
    let admitted = s
        .admit_console_session(scheduler, &members)
        .map_err(|_| Error::State)?;
    quiesce()?;
    admitted.handles[..9].try_into().map_err(|_| Error::State)
}

/// SAFETY: exclusive BSP/IF0, six owned prepared roots, no dispatched task/AP.
#[cfg(feature = "development-session-capacity")]
pub unsafe fn bootstrap_capacity(
    tasks: [(TaskId, ImageAdmission); 6],
    scheduler: &mut poolekernel::scheduler::Scheduler,
) -> Result<[u64; 13], Error> {
    idle()?;
    let s = unsafe { &mut *(&raw mut IPC) };
    if !s.is_empty() {
        return Err(Error::State);
    }
    let members = tasks.map(|(id, image)| Member {
        id,
        image,
        priority: 16,
    });
    let admitted = s
        .admit_console_capacity(scheduler, &members)
        .map_err(|_| Error::State)?;
    quiesce()?;
    admitted.handles[..13].try_into().map_err(|_| Error::State)
}
