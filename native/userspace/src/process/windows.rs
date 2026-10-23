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
        Self::with_terminal(
            port,
            endpoint,
            Terminal::window(cells),
            surface_cells,
            key_cells,
        )
    }
    #[inline(always)]
    pub fn new_compact(
        port: Console,
        endpoint: u64,
        cells: &'a mut [u8; desktop::WINDOW_CELLS],
        surface_cells: &'a mut [u8; 384],
        key_cells: &'a mut [u8; 64],
    ) -> Self {
        Self::with_terminal(
            port,
            endpoint,
            Terminal::compact_window(cells),
            surface_cells,
            key_cells,
        )
    }
    #[inline(always)]
    fn with_terminal(
        port: Console,
        endpoint: u64,
        terminal: Terminal<'a>,
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
            terminal,
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
    pub fn start_launch(&mut self, controls: &desktop::launch::Controls) -> Result<(), Error> {
        self.paint_launch(self.manager.bounds, controls)
    }
    #[inline(always)]
    fn paint_launch(&mut self, r: Rect, controls: &desktop::launch::Controls) -> Result<(), Error> {
        compositor::paint_launch(
            &self.manager,
            &self.terminal,
            &self.surfaces,
            &mut self.display,
            r,
            controls,
        )
    }
    #[inline(never)]
    pub fn launch_status(&mut self, controls: &desktop::launch::Controls) -> Result<(), Error> {
        self.paint_launch(
            Rect {
                x: 0,
                y: 0,
                w: self.manager.bounds.w,
                h: 32,
            },
            controls,
        )
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
        self.poll_mode::<false>(None)
    }
    #[inline(always)]
    pub fn poll_mode<const INPUT: bool>(
        &mut self,
        input: Option<&mut desktop::application_input::Queues>,
    ) -> Result<(), Error> {
        if INPUT {
            // Polling must return before composition uses its nested draw frames.
            for rect in self.poll_input::<false>(input, None)?.into_iter().flatten() {
                self.paint(rect)?;
            }
            Ok(())
        } else {
            self.poll_inner::<false, false>(input, &mut [None; 3], None)
        }
    }
    #[inline(always)]
    pub fn poll_launch(
        &mut self,
        input: &mut desktop::application_input::Queues,
        controls: &mut desktop::launch::Controls,
    ) -> Result<(), Error> {
        for rect in self
            .poll_input::<true>(Some(input), Some(controls))?
            .into_iter()
            .flatten()
        {
            self.paint_launch(rect, controls)?;
        }
        Ok(())
    }
    // Keep interactive poll temporaries out of the long-lived entry frame.
    #[inline(never)]
    fn poll_input<const LAUNCH: bool>(
        &mut self,
        input: Option<&mut desktop::application_input::Queues>,
        controls: Option<&mut desktop::launch::Controls>,
    ) -> Result<[Option<Rect>; 3], Error> {
        let mut damage = [None; 3];
        self.poll_inner::<true, LAUNCH>(input, &mut damage, controls)?;
        Ok(damage)
    }
    #[inline(always)]
    fn poll_inner<const INPUT: bool, const LAUNCH: bool>(
        &mut self,
        mut input: Option<&mut desktop::application_input::Queues>,
        pending: &mut [Option<Rect>; 3],
        controls: Option<&mut desktop::launch::Controls>,
    ) -> Result<(), Error> {
        if INPUT && (!LIFETIME || input.is_none()) {
            return Err(Error::Transport);
        }
        let old_focus = self.manager.focus;
        let mut damage = None;
        let mut pointer_damage = [None; 2];
        if let Some(i) = self
            .rpc
            .poll_mode::<INPUT>(&mut ConsoleCalls, &mut self.surfaces, input.as_deref_mut())
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
            let rect = if !self.surfaces.open(i) {
                self.manager.bounds
            } else {
                self.manager.windows[i + 1]
            };
            if INPUT {
                damage = Some(if newly_open {
                    self.manager.bounds
                } else {
                    rect
                });
            } else {
                self.paint(rect)?;
            }
            if newly_open && !INPUT {
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
                if INPUT {
                    damage = Some(self.manager.bounds);
                } else {
                    self.paint(self.manager.bounds)?;
                }
            }
        }
        if INPUT {
            let queues = input.as_mut().ok_or(Error::Transport)?;
            let changed = queues.sync(&self.surfaces);
            let replacement = self
                .manager
                .focus
                .is_some_and(|i| (1..=2).contains(&i) && changed & (1 << (i - 1)) != 0);
            if old_focus != self.manager.focus || replacement {
                self.input
                    .lifetime_boundary(queues, &mut self.manager, old_focus);
                damage = Some(self.manager.bounds);
            }
        }
        let update = if LAUNCH {
            self.input.poll_launch(
                &mut self.manager,
                &mut Ps2(self.display.0),
                input.ok_or(Error::Transport)?,
                controls.ok_or(Error::Transport)?,
            )?
        } else {
            self.input
                .poll_mode::<INPUT>(&mut self.manager, &mut Ps2(self.display.0), input)?
        };
        if update.scene_changed {
            self.locate();
            if INPUT {
                damage = Some(self.manager.bounds);
            } else {
                self.paint(self.manager.bounds)?;
            }
        } else if update.pointer_changed && (!INPUT || damage != Some(self.manager.bounds)) {
            if INPUT {
                pointer_damage = [
                    Some(Rect {
                        x: update.old_pointer.0,
                        y: update.old_pointer.1,
                        w: 12,
                        h: 20,
                    }),
                    Some(Rect {
                        x: self.manager.x,
                        y: self.manager.y,
                        w: 12,
                        h: 20,
                    }),
                ];
            } else {
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
        }
        if INPUT {
            *pending = [pointer_damage[0], pointer_damage[1], damage];
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
pub unsafe fn launch_boot(
    address: u64,
    bytes: u64,
    version: u64,
) -> Result<
    (
        Console,
        crate::session_control::rpc::Connection<ConsoleCalls>,
        u64,
    ),
    crate::startup::Error,
> {
    let block = unsafe { super::file_block(address, bytes) }?;
    let (boot, surface) = crate::startup::launch_console(block, version)?;
    Ok((
        Console(boot.port.ok_or(crate::startup::Error::Handle)?),
        crate::session_control::rpc::Connection::new(boot.receive, boot.peer, true, ConsoleCalls),
        surface,
    ))
}
/// SAFETY: caller supplies the live kernel-owned PSTART1 entry block.
#[inline(always)]
pub unsafe fn application(address: u64, bytes: u64, version: u64, kind: crate::apps::Kind) -> ! {
    unsafe { application_view::<desktop::publisher::Publisher>(address, bytes, version, kind) }
}
/// SAFETY: caller supplies the live kernel-owned PSTART1 entry block.
#[inline(always)]
pub unsafe fn application_view<V: desktop::publisher::View>(
    address: u64,
    bytes: u64,
    version: u64,
    kind: crate::apps::Kind,
) -> ! {
    let block = unsafe { super::file_block(address, bytes) }.unwrap_or_else(|_| super::exit(200));
    let (boot, endpoint) = crate::startup::window_application(block, version, kind)
        .unwrap_or_else(|_| super::exit(200));
    let mut publisher = V::new(endpoint, kind);
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
