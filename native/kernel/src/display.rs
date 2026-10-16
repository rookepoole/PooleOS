//! PDISPLAY1: bounded value-only commands; no user pointers or physical mappings.
#![forbid(unsafe_code)]
use crate::{FramebufferSpec, user_entry::syscall::Status};

pub const CAPACITY: usize = 32;
pub const MAX_PIXELS: u32 = 4096;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Surface {
    pub width: u32,
    pub height: u32,
    pub stride: u32,
    pub rgb: bool,
}
impl Surface {
    pub fn new(spec: FramebufferSpec) -> Option<Self> {
        if !(320..=4096).contains(&spec.width)
            || !(200..=2160).contains(&spec.height)
            || spec.stride < spec.width
            || !matches!(spec.pixel_format, 1 | 2)
            || u64::from(spec.stride)
                .checked_mul(u64::from(spec.height))?
                .checked_mul(4)?
                > spec.byte_count
            || !crate::framebuffer_identity_range_is_safe(spec.physical_base, spec.byte_count)
        {
            return None;
        }
        Some(Self {
            width: spec.width,
            height: spec.height,
            stride: spec.stride,
            // PBP1 numbers differ from the firmware's raw GOP enumeration.
            rgb: spec.pixel_format == 1,
        })
    }
    pub fn dimensions(self) -> u64 {
        u64::from(self.width) | (u64::from(self.height) << 32)
    }
    pub fn pixel(self, color: u32) -> u32 {
        if self.rgb {
            (color & 0xff00) | ((color & 0xff) << 16) | ((color >> 16) & 0xff)
        } else {
            color
        }
    }
    pub fn command(self, rect: u64, colors: u64, mask: Option<u64>) -> Result<Command, Status> {
        let x = (rect & 0xffff) as u32;
        let y = ((rect >> 16) & 0xffff) as u32;
        let width = ((rect >> 32) & 0xffff) as u32;
        let height = (rect >> 48) as u32;
        if width == 0
            || height == 0
            || width * height > MAX_PIXELS
            || x + width > self.width
            || y + height > self.height
            || colors >> (if mask.is_some() { 48 } else { 24 }) != 0
            || mask.is_some() && (width > 8 || height > 8)
        {
            return Err(Status::Arguments);
        }
        Ok(Command {
            x,
            y,
            width,
            height,
            foreground: self.pixel(colors as u32 & 0xffffff),
            background: self.pixel((colors >> 24) as u32),
            mask,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Command {
    pub x: u32,
    pub y: u32,
    pub width: u32,
    pub height: u32,
    pub foreground: u32,
    pub background: u32,
    pub mask: Option<u64>,
}
impl Command {
    pub fn color(self, x: u32, y: u32) -> u32 {
        match self.mask {
            Some(mask) if mask & (1 << (y * 8 + x)) == 0 => self.background,
            _ => self.foreground,
        }
    }
}

pub struct Queue {
    commands: [Option<Command>; CAPACITY],
    len: usize,
}
impl Queue {
    pub const fn new() -> Self {
        Self {
            commands: [None; CAPACITY],
            len: 0,
        }
    }
    pub fn push(&mut self, command: Command) -> Result<(), Status> {
        let slot = self.commands.get_mut(self.len).ok_or(Status::Again)?;
        *slot = Some(command);
        self.len += 1;
        Ok(())
    }
    /// Called only in the retained boot root, before another task is dispatched.
    pub fn drain(&mut self, mut emit: impl FnMut(Command)) {
        for slot in &mut self.commands[..self.len] {
            if let Some(command) = slot.take() {
                emit(command);
            }
        }
        self.len = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn spec() -> FramebufferSpec {
        FramebufferSpec {
            physical_base: 0x80000000,
            byte_count: 1024 * 768 * 4,
            width: 1024,
            height: 768,
            stride: 1024,
            pixel_format: 2,
            foreground: 0,
        }
    }
    fn rect(x: u64, y: u64, w: u64, h: u64) -> u64 {
        x | y << 16 | w << 32 | h << 48
    }
    #[test]
    fn rejects_bad_surface_before_any_access() {
        assert!(Surface::new(spec()).is_some());
        for case in 0..8 {
            let mut s = spec();
            match case {
                0 => s.width = 0,
                1 => s.height = 2161,
                2 => s.stride = 1023,
                3 => s.byte_count -= 4,
                4 => s.pixel_format = 3,
                5 => s.physical_base = 0,
                6 => s.pixel_format = 0,
                _ => s.physical_base = u64::MAX - 3,
            }
            assert!(Surface::new(s).is_none());
        }
    }
    #[test]
    fn rejects_wrap_outside_empty_huge_and_reserved_colors() {
        let s = Surface::new(spec()).unwrap();
        for r in [
            rect(0, 0, 0, 1),
            rect(0, 0, 1, 0),
            rect(1024, 0, 1, 1),
            rect(0, 768, 1, 1),
            rect(1023, 767, 2, 1),
            rect(0, 0, 65, 64),
            u64::MAX,
        ] {
            assert_eq!(s.command(r, 0, None), Err(Status::Arguments));
        }
        assert!(s.command(rect(1023, 767, 1, 1), 0xffffff, None).is_ok());
        assert!(s.command(rect(0, 0, 64, 64), 0, None).is_ok());
        assert!(
            s.command(rect(0, 0, 8, 8), 0xffffffffffff, Some(u64::MAX))
                .is_ok()
        );
        for (r, c, m) in [
            (rect(0, 0, 1, 1), 1 << 24, None),
            (rect(0, 0, 8, 8), 1 << 48, Some(0)),
            (rect(0, 0, 9, 8), 0, Some(0)),
            (rect(0, 0, 8, 9), 0, Some(0)),
        ] {
            assert_eq!(s.command(r, c, m), Err(Status::Arguments));
        }
    }
    #[test]
    fn exact_rgb_bgr_and_mask_bit_order() {
        let s = Surface::new(spec()).unwrap();
        assert_eq!(s.pixel(0x123456), 0x123456);
        assert_eq!(
            Surface::new(FramebufferSpec {
                pixel_format: 1,
                ..spec()
            })
            .unwrap()
            .pixel(0x123456),
            0x563412
        );
        let c = s
            .command(rect(0, 0, 8, 8), 0x112233aabbcc, Some(1 | 1 << 63))
            .unwrap();
        for y in 0..8 {
            for x in 0..8 {
                assert_eq!(
                    c.color(x, y),
                    if (x, y) == (0, 0) || (x, y) == (7, 7) {
                        0xaabbcc
                    } else {
                        0x112233
                    }
                );
            }
        }
    }
    #[test]
    fn queue_backpressure_never_loses_or_reorders_and_can_be_reused() {
        let s = Surface::new(spec()).unwrap();
        let mut q = Queue::new();
        for n in 0..CAPACITY {
            q.push(s.command(rect(n as u64, 0, 1, 1), n as u64, None).unwrap())
                .unwrap();
        }
        assert_eq!(
            q.push(s.command(rect(100, 0, 1, 1), 0, None).unwrap()),
            Err(Status::Again)
        );
        let mut i = 0;
        q.drain(|c| {
            assert_eq!(c.x, i);
            i += 1;
        });
        assert_eq!(i, 32);
        q.drain(|_| panic!("duplicate"));
        q.push(s.command(rect(100, 0, 1, 1), 0, None).unwrap())
            .unwrap();
        q.drain(|c| assert_eq!(c.x, 100));
    }
}
