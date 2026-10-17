//! Native window-console and surface client adapters. No framebuffer mapping in CPL3.
use super::{
    Console, ConsoleCalls, ConsoleIpc,
    desktop::{Display, invoke},
};
use crate::{
    console::{Error, Registers},
    desktop::{
        self, Terminal,
        compositor::{self, Damage},
        input::{Device, Input},
        surface_rpc,
        surfaces::Surfaces,
        windows::{Manager, Rect},
    },
};
pub struct Local<'a, const LIFETIME: bool = false> {
    serial: Console,
    display: Display,
    terminal: Terminal<'a>,
    surfaces: Surfaces<'a>,
    manager: Manager,
    input: Input<'a>,
    rpc: surface_rpc::Server,
}
struct Ps2(u64);
impl Device for Ps2 {
    #[inline(always)]
    fn next(&mut self) -> Result<Option<u64>, Error> {
        match invoke(26, self.0, 0, 0, 0) {
            (0, byte) => Ok(Some(byte)),
            (6, 0) => Ok(None),
            _ => Err(Error::Transport),
        }
    }
}
impl<'a, const LIFETIME: bool> Local<'a, LIFETIME> {
    #[inline(always)]
    pub fn new(
        port: Console,
        endpoint: u64,
        cells: &'a mut [u8; 1920],
        surface_cells: &'a mut [u8; 384],
        key_cells: &'a mut [u8; 64],
    ) -> Self {
        let (status, h) = invoke(21, port.0, 0, 0, 0);
        if status != 0 {
            super::exit(154);
        }
        let (status, dim) = invoke(22, h, 0, 0, 0);
        if status != 0 {
            super::exit(154);
        }
        let w = u16::try_from(dim & 0xffffffff).unwrap_or_else(|_| super::exit(154));
        let height = u16::try_from(dim >> 32).unwrap_or_else(|_| super::exit(154));
        let mut local = Self {
            serial: port,
            display: Display(h),
            terminal: Terminal::window(cells),
            surfaces: Surfaces::new(surface_cells),
            manager: Manager::new(w, height).unwrap_or_else(|_| super::exit(154)),
            input: Input::new(key_cells),
            rpc: surface_rpc::Server::new(endpoint),
        };
        local.locate();
        local
    }
    #[inline(always)]
    pub fn start(&mut self) -> Result<(), Error> {
        self.paint(self.manager.bounds)
    }
    #[inline(always)]
    fn locate(&mut self) {
        let r = self.manager.windows[0];
        self.terminal
            .relocate(r.x.saturating_add(8), r.y.saturating_add(36));
    }
    #[inline(always)]
    fn paint(&mut self, r: Rect) -> Result<(), Error> {
        compositor::paint(
            &self.manager,
            &self.terminal,
            &self.surfaces,
            &mut self.display,
            r,
        )
    }
    #[inline(always)]
    pub fn poll(&mut self) -> Result<(), Error> {
        if let Some(i) = self
            .rpc
            .poll(&mut ConsoleCalls, &mut self.surfaces)
            .map_err(|_| Error::Transport)?
        {
            if i >= 2 {
                return Err(Error::Hardware);
            }
            let newly_open = self.surfaces.open(i) && !self.manager.available[i + 1];
            if newly_open {
                let focus = self.manager.focus;
                self.manager.show(i + 1)?;
                // Starting a job must not steal the terminal's keyboard focus.
                self.manager.focus = focus;
            }
            if !self.surfaces.open(i) {
                let focus = self.manager.focus;
                self.manager.close(i + 1)?;
                if focus != self.manager.focus {
                    self.input.clear_focus();
                }
            }
            self.paint(if !self.surfaces.open(i) {
                self.manager.bounds
            } else {
                self.manager.windows[i + 1]
            })?;
            if newly_open {
                self.paint(Rect {
                    x: 0,
                    y: self.manager.bounds.h.saturating_sub(32),
                    w: self.manager.bounds.w,
                    h: 32,
                })?;
            }
        }
        if LIFETIME {
            let retired = desktop::lifecycle::poll(&mut self.surfaces, &mut super::ProcessCalls)?;
            if retired != 0 {
                let focus = self.manager.focus;
                for i in 0..2 {
                    if retired & (1 << i) != 0 {
                        self.manager.close(i + 1)?;
                    }
                }
                if focus != self.manager.focus {
                    self.input.clear_focus();
                }
                self.paint(self.manager.bounds)?;
            }
        }
        let update = self
            .input
            .poll(&mut self.manager, &mut Ps2(self.display.0))?;
        if update.scene_changed {
            self.locate();
            self.paint(self.manager.bounds)?;
        } else if update.pointer_changed {
            self.paint(Rect {
                x: update.old_pointer.0,
                y: update.old_pointer.1,
                w: 12,
                h: 20,
            })?;
            self.paint(Rect {
                x: self.manager.x,
                y: self.manager.y,
                w: 12,
                h: 20,
            })?;
        }
        Ok(())
    }
}
impl<const LIFETIME: bool> Registers for Local<'_, LIFETIME> {
    #[inline(always)]
    fn read(&mut self, offset: u8) -> Result<u8, Error> {
        let focused = self.manager.focus == Some(0) && self.manager.visible[0];
        if offset == 0 && focused {
            if let Some(b) = self.input.pop() {
                return Ok(b);
            }
        }
        let value = self.serial.read(offset)?;
        Ok(if offset == 5 && focused && self.input.ready() {
            value | 1
        } else {
            value
        })
    }
    #[inline(always)]
    fn write(&mut self, offset: u8, value: u8) -> Result<(), Error> {
        self.serial.write(offset, value)?;
        if offset == 0 {
            let mut damage = Damage(None);
            self.terminal.write(&mut damage, value)?;
            if let Some(r) = damage.0 {
                self.paint(r)?;
            }
        }
        Ok(())
    }
}
/// SAFETY: caller supplies the live kernel-owned PSTART1 entry block.
#[inline(always)]
pub unsafe fn boot(
    address: u64,
    bytes: u64,
    version: u64,
) -> Result<(Console, ConsoleIpc, u64), crate::startup::Error> {
    let block = unsafe { super::file_block(address, bytes) }?;
    let (boot, surface) = crate::startup::window_console(block, version)?;
    let port = Console(boot.port.ok_or(crate::startup::Error::Handle)?);
    Ok((
        port,
        ConsoleIpc(crate::console_ipc::rpc::Transport::new(
            boot.receive,
            boot.peer,
            true,
        )),
        surface,
    ))
}
/// SAFETY: caller supplies the live kernel-owned PSTART1 entry block.
#[inline(always)]
pub unsafe fn application(address: u64, bytes: u64, version: u64, kind: crate::apps::Kind) -> ! {
    let block = unsafe { super::file_block(address, bytes) }.unwrap_or_else(|_| super::exit(200));
    let (boot, endpoint) = crate::startup::window_application(block, version, kind)
        .unwrap_or_else(|_| super::exit(200));
    let mut publisher = desktop::publisher::Publisher::new(endpoint, kind);
    let files = crate::files::rpc::Client::new(boot.files, boot.file_peer, ConsoleCalls);
    let mut app = crate::apps::program::Program::new(
        kind,
        boot.control,
        boot.control_peer,
        ConsoleCalls,
        files,
    );
    loop {
        // Drain at most one surface request before entering a file read/wait.
        if publisher.pending() {
            let _ = publisher.poll(&mut ConsoleCalls);
            continue;
        }
        if let Some(result) = app.display_result() {
            publisher.observe(result);
        }
        match app.poll() {
            Ok(crate::apps::program::Progress::FaultRequested) => unsafe {
                super::asm!("ud2", options(noreturn));
            },
            Ok(_) => {}
            Err(_) => super::exit(202),
        }
        if app.display_idle() {
            let _ = publisher.poll(&mut ConsoleCalls);
        }
    }
}
