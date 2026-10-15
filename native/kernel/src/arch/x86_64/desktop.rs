//! BSP-only development display transport. Rendering policy lives in CPL3.
use super::{inb, read_cr3, read_rflags};
use poolekernel::{
    FramebufferSpec,
    display::{Queue, Surface},
    user_entry::syscall::Status,
};

struct State {
    spec: FramebufferSpec,
    surface: Surface,
    root: u64,
    queue: Queue,
}
static mut STATE: Option<State> = None;

/// SAFETY: exclusive BSP/IF0, validated retained GOP identity mapping and boot root.
pub unsafe fn initialize(spec: FramebufferSpec, root: u64) -> Result<(), ()> {
    let surface = Surface::new(spec).ok_or(())?;
    if read_rflags() & (1 << 9) != 0
        || unsafe { read_cr3() } != root
        || unsafe { (&*(&raw const STATE)).is_some() }
    {
        return Err(());
    }
    unsafe {
        *(&raw mut STATE) = Some(State {
            spec,
            surface,
            root,
            queue: Queue::new(),
        });
    }
    Ok(())
}

/// Caller/child authority is checked by user_ipc before reaching this adapter.
pub(super) fn operation(number: u64, argument: u64, value: u64, mask: u64) -> (Status, u64) {
    let Some(s) = (unsafe { (&mut *(&raw mut STATE)).as_mut() }) else {
        return (Status::Denied, 0);
    };
    match number {
        22 => (Status::Ok, s.surface.dimensions()),
        23 | 24 => match s.surface.command(
            argument,
            value,
            if number == 24 { Some(mask) } else { None },
        ) {
            Ok(command) => match s.queue.push(command) {
                Ok(()) => (Status::Ok, 0),
                Err(e) => (e, 0),
            },
            Err(e) => (e, 0),
        },
        25 => {
            // Emulated, firmware-initialized translated PS/2 only. No controller
            // writes, reset/A20 commands, interrupt routing or arbitrary port API.
            let status = unsafe { inb(0x64) };
            if status & 1 == 0 {
                return (Status::Again, 0);
            }
            let byte = unsafe { inb(0x60) };
            if status & 0xc0 != 0 {
                (Status::Ok, 256)
            } else if status & 0x20 != 0 {
                (Status::Again, 0)
            } else {
                (Status::Ok, u64::from(byte))
            }
        }
        _ => (Status::Arguments, 0),
    }
}

/// Never write GOP memory under a user CR3: that range is deliberately absent.
/// The dispatcher drains accepted commands before retirement or the next task.
pub fn flush() -> Result<(), ()> {
    let s = unsafe { (&mut *(&raw mut STATE)).as_mut() }.ok_or(())?;
    if read_rflags() & (1 << 9) != 0 || unsafe { read_cr3() } != s.root {
        return Err(());
    }
    s.queue.drain(|c| {
        for y in 0..c.height {
            for x in 0..c.width {
                let index = u64::from(c.y + y) * u64::from(s.surface.stride) + u64::from(c.x + x);
                // SAFETY: validated retained mapping, command bounds, sole writer,
                // checked root and IF0. No untrusted address reaches this operation.
                unsafe {
                    core::ptr::write_volatile(
                        (s.spec.physical_base as *mut u32).add(index as usize),
                        c.color(x, y),
                    );
                }
            }
        }
    });
    Ok(())
}
