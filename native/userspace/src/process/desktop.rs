//! PSABI1 local-console adapter. Device addresses never cross into this process.
use super::{Console, asm};
use crate::{
    console::{Error, Registers},
    desktop::{Canvas, Terminal, keyboard::Keyboard},
};

#[inline(always)]
fn invoke(number: u64, handle: u64, argument: u64, value: u64, mask: u64) -> (u64, u64) {
    let status: u64;
    let result: u64;
    // No pointers or memory copy: all arguments are bounded integer commands.
    unsafe {
        asm!("syscall",inlateout("rax") number=>status,in("rdi") 1u64,in("rsi") handle,
        inlateout("rdx") argument=>result,in("r10") value,in("r8") mask,in("r9") 0u64,
        lateout("rcx") _,lateout("r11") _,options(nostack));
    }
    (status, result)
}
struct Display(u64);
impl Display {
    #[inline]
    fn submit(&mut self, n: u64, r: u64, c: u64, m: u64) -> Result<(), Error> {
        // Retry only queue backpressure; each syscall retains scheduler accounting.
        loop {
            match invoke(n, self.0, r, c, m) {
                (0, 0) => return Ok(()),
                (6, 0) => {}
                _ => return Err(Error::Transport),
            }
        }
    }
    #[inline]
    fn rect(x: u16, y: u16, w: u16, h: u16) -> u64 {
        u64::from(x) | u64::from(y) << 16 | u64::from(w) << 32 | u64::from(h) << 48
    }
}
impl Canvas for Display {
    #[inline]
    fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, c: u32) -> Result<(), Error> {
        for dy in (0..h).step_by(32) {
            for dx in (0..w).step_by(64) {
                self.submit(
                    23,
                    Self::rect(
                        x.checked_add(dx).ok_or(Error::Hardware)?,
                        y.checked_add(dy).ok_or(Error::Hardware)?,
                        w.saturating_sub(dx).min(64),
                        h.saturating_sub(dy).min(32),
                    ),
                    u64::from(c),
                    0,
                )?;
            }
        }
        Ok(())
    }
    #[inline]
    fn tile(
        &mut self,
        x: u16,
        y: u16,
        w: u16,
        h: u16,
        m: u64,
        fg: u32,
        bg: u32,
    ) -> Result<(), Error> {
        self.submit(
            24,
            Self::rect(x, y, w, h),
            u64::from(fg) | (u64::from(bg) << 24),
            m,
        )
    }
}
pub struct Local<'a> {
    serial: Console,
    display: Display,
    terminal: Terminal<'a>,
    keyboard: Keyboard,
    pending: Option<u8>,
}
impl<'a> Local<'a> {
    #[inline(always)]
    pub fn new(
        serial: Console,
        cells: &'a mut [u8; crate::desktop::MAX_COLUMNS * crate::desktop::MAX_ROWS],
    ) -> Result<Self, Error> {
        let (s, h) = invoke(21, serial.0, 0, 0, 0);
        if s != 0 {
            return Err(Error::Transport);
        }
        let (s, dimensions) = invoke(22, h, 0, 0, 0);
        if s != 0 {
            return Err(Error::Transport);
        }
        let w = u16::try_from(dimensions & 0xffffffff).map_err(|_| Error::Hardware)?;
        let hgt = u16::try_from(dimensions >> 32).map_err(|_| Error::Hardware)?;
        let terminal = Terminal::new(w, hgt, cells)?;
        let mut display = Display(h);
        terminal.paint(&mut display, w, hgt)?;
        Ok(Self {
            serial,
            display,
            terminal,
            keyboard: Keyboard::new(),
            pending: None,
        })
    }
}
impl Registers for Local<'_> {
    #[inline]
    fn read(&mut self, offset: u8) -> Result<u8, Error> {
        if offset == 0 {
            if let Some(byte) = self.pending.take() {
                return Ok(byte);
            }
        }
        let mut value = self.serial.read(offset)?;
        if offset == 5 {
            if value & 1 == 0 && self.pending.is_none() {
                match invoke(25, self.display.0, 0, 0, 0) {
                    (0, byte) if byte <= 255 => self.pending = self.keyboard.feed(byte as u8),
                    (0, 256) => self.keyboard = Keyboard::new(),
                    (6, 0) => {}
                    _ => return Err(Error::Transport),
                }
            }
            if self.pending.is_some() {
                value |= 1;
            }
        }
        Ok(value)
    }
    #[inline]
    fn write(&mut self, offset: u8, value: u8) -> Result<(), Error> {
        self.serial.write(offset, value)?;
        if offset == 0 {
            self.terminal.write(&mut self.display, value)?;
        }
        Ok(())
    }
}
