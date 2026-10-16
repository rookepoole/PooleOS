//! Fixed-capacity window policy. Clients never supply screen coordinates or z-order.
#![forbid(unsafe_code)]
use super::{Canvas, mouse::Motion};
use crate::console::Error;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Rect {
    pub x: u16,
    pub y: u16,
    pub w: u16,
    pub h: u16,
}
impl Rect {
    #[inline]
    pub fn contains(self, x: u16, y: u16) -> bool {
        x >= self.x && y >= self.y && x - self.x < self.w && y - self.y < self.h
    }
    #[inline]
    pub fn intersect(self, other: Self) -> Option<Self> {
        let x = self.x.max(other.x);
        let y = self.y.max(other.y);
        let right =
            (u32::from(self.x) + u32::from(self.w)).min(u32::from(other.x) + u32::from(other.w));
        let bottom =
            (u32::from(self.y) + u32::from(self.h)).min(u32::from(other.y) + u32::from(other.h));
        if right <= u32::from(x) || bottom <= u32::from(y) {
            None
        } else {
            Some(Self {
                x,
                y,
                w: (right - u32::from(x)) as u16,
                h: (bottom - u32::from(y)) as u16,
            })
        }
    }
}

pub struct Clip<'a, C> {
    pub canvas: &'a mut C,
    pub rect: Rect,
}
impl<C: Canvas> Canvas for Clip<'_, C> {
    fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, color: u32) -> Result<(), Error> {
        if let Some(r) = self.rect.intersect(Rect { x, y, w, h }) {
            self.canvas.fill(r.x, r.y, r.w, r.h, color)?;
        }
        Ok(())
    }
    fn tile(
        &mut self,
        x: u16,
        y: u16,
        w: u16,
        h: u16,
        mask: u64,
        fg: u32,
        bg: u32,
    ) -> Result<(), Error> {
        if w > 8 || h > 8 {
            return Err(Error::Hardware);
        }
        if let Some(r) = self.rect.intersect(Rect { x, y, w, h }) {
            let shift = u32::from(r.y.saturating_sub(y)) * 8 + u32::from(r.x.saturating_sub(x));
            self.canvas.tile(
                r.x,
                r.y,
                r.w,
                r.h,
                mask.checked_shr(shift).ok_or(Error::Hardware)?,
                fg,
                bg,
            )?;
        }
        Ok(())
    }
}

pub struct Manager {
    pub bounds: Rect,
    pub windows: [Rect; 3],
    pub order: [usize; 3],
    pub visible: [bool; 3],
    pub available: [bool; 3],
    pub focus: Option<usize>,
    pub x: u16,
    pub y: u16,
    held: bool,
    drag: Option<(usize, u16, u16)>,
}
impl Manager {
    #[inline(always)]
    pub fn new(width: u16, height: u16) -> Result<Self, Error> {
        if !(640..=4096).contains(&width) || !(480..=2160).contains(&height) {
            return Err(Error::Hardware);
        }
        Ok(Self {
            bounds: Rect {
                x: 0,
                y: 0,
                w: width,
                h: height,
            },
            windows: [
                Rect {
                    x: 16,
                    y: 48,
                    w: 592,
                    h: 352,
                },
                Rect {
                    x: width - 320,
                    y: 72,
                    w: 304,
                    h: 176,
                },
                Rect {
                    x: width - 336,
                    y: 264,
                    w: 304,
                    h: 176,
                },
            ],
            order: [1, 2, 0],
            visible: [true, false, false],
            available: [true, false, false],
            focus: Some(0),
            x: width / 2,
            y: height / 2,
            held: false,
            drag: None,
        })
    }
    #[inline]
    pub fn show(&mut self, index: usize) -> Result<(), Error> {
        *self.visible.get_mut(index).ok_or(Error::Hardware)? = true;
        *self.available.get_mut(index).ok_or(Error::Hardware)? = true;
        self.raise(index);
        Ok(())
    }
    #[inline]
    pub fn close(&mut self, index: usize) -> Result<(), Error> {
        *self.visible.get_mut(index).ok_or(Error::Hardware)? = false;
        *self.available.get_mut(index).ok_or(Error::Hardware)? = false;
        if self.focus == Some(index) {
            self.focus = self
                .order
                .iter()
                .rev()
                .copied()
                .find(|&i| self.visible.get(i).copied().unwrap_or(false));
        }
        if self.drag.is_some_and(|(i, _, _)| i == index) {
            self.reset_input();
        }
        Ok(())
    }
    #[inline]
    fn raise(&mut self, index: usize) {
        if let Some(pos) = self.order.iter().position(|v| *v == index) {
            for i in pos..2 {
                self.order[i] = self.order[i + 1];
            }
            self.order[2] = index;
            self.focus = Some(index);
        }
    }
    #[inline]
    pub fn reset_input(&mut self) {
        self.held = false;
        self.drag = None;
    }
    #[inline]
    pub fn motion(&mut self, motion: Motion) -> bool {
        let old = (self.x, self.y);
        self.x = (i32::from(self.x) + i32::from(motion.dx))
            .max(0)
            .min(i32::from(self.bounds.w.saturating_sub(12))) as u16;
        self.y = (i32::from(self.y) + i32::from(motion.dy))
            .max(0)
            .min(i32::from(self.bounds.h.saturating_sub(20))) as u16;
        let pressed = motion.buttons & 1 != 0;
        let mut changed = old != (self.x, self.y);
        if pressed && !self.held {
            if self.y >= self.bounds.h.saturating_sub(32) {
                let index = usize::from(self.x / 160);
                if index < 3 && self.available[index] {
                    self.visible[index] = true;
                    self.raise(index);
                    changed = true;
                }
            } else {
                for &index in self.order.iter().rev() {
                    if index >= 3 {
                        continue;
                    }
                    let r = self.windows[index];
                    if self.visible[index] && r.contains(self.x, self.y) {
                        if self.y.saturating_sub(r.y) < 28
                            && self.x.saturating_sub(r.x) >= r.w.saturating_sub(28)
                        {
                            self.visible[index] = false;
                            self.focus = self
                                .order
                                .iter()
                                .rev()
                                .copied()
                                .find(|&i| self.visible.get(i).copied().unwrap_or(false));
                            changed = true;
                            break;
                        }
                        if self.y.saturating_sub(r.y) < 28 {
                            self.drag = Some((
                                index,
                                self.x.saturating_sub(r.x),
                                self.y.saturating_sub(r.y),
                            ));
                        }
                        self.raise(index);
                        changed = true;
                        break;
                    }
                }
            }
        }
        if pressed {
            if let Some((index, dx, dy)) = self.drag {
                let Some(r) = self.windows.get_mut(index) else {
                    self.reset_input();
                    return changed;
                };
                r.x = self
                    .x
                    .saturating_sub(dx)
                    .min(self.bounds.w.saturating_sub(r.w));
                r.y = self
                    .y
                    .saturating_sub(dy)
                    .max(40)
                    .min(self.bounds.h.saturating_sub(32).saturating_sub(r.h));
            }
        } else {
            self.drag = None;
        }
        self.held = pressed;
        changed
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn closing_focused_surface_restores_focus_and_does_not_restore_closed_taskbar_entry() {
        let mut m = Manager::new(1024, 768).unwrap();
        m.show(1).unwrap();
        m.close(1).unwrap();
        assert_eq!(m.focus, Some(0));
        assert!(!m.visible[1] && !m.available[1]);
        m.x = 200;
        m.y = 744;
        m.motion(Motion {
            dx: 0,
            dy: 0,
            buttons: 1,
        });
        assert!(!m.visible[1]);
        assert!(m.close(3).is_err());
    }
    #[test]
    fn minimize_and_taskbar_restore_preserve_content_and_release_capture() {
        let mut m = Manager::new(640, 480).unwrap();
        m.show(1).unwrap();
        let r = m.windows[1];
        m.x = r.x + r.w - 16;
        m.y = r.y + 12;
        m.motion(Motion {
            dx: 0,
            dy: 0,
            buttons: 1,
        });
        assert!(!m.visible[1]);
        assert_eq!(m.focus, Some(0));
        m.motion(Motion {
            dx: 0,
            dy: 0,
            buttons: 0,
        });
        m.x = 200;
        m.y = 460;
        m.motion(Motion {
            dx: 0,
            dy: 0,
            buttons: 1,
        });
        assert!(m.visible[1]);
        assert_eq!(m.focus, Some(1));
        assert_eq!(m.windows[1], r);
        m.reset_input();
        m.motion(Motion {
            dx: 100,
            dy: 0,
            buttons: 0,
        });
        assert_eq!(m.windows[1], r);
    }
    #[test]
    fn overlap_focus_drag_and_release_obey_bounds() {
        let mut m = Manager::new(640, 480).unwrap();
        m.show(1).unwrap();
        m.x = 330;
        m.y = 80;
        assert!(m.motion(Motion {
            dx: 0,
            dy: 0,
            buttons: 1
        }));
        assert_eq!(m.focus, Some(1));
        m.motion(Motion {
            dx: i16::MAX,
            dy: i16::MAX,
            buttons: 1,
        });
        assert_eq!(m.windows[1].x, 336);
        assert_eq!(m.windows[1].y, 272);
        m.reset_input();
        m.motion(Motion {
            dx: i16::MIN,
            dy: i16::MIN,
            buttons: 0,
        });
        assert_eq!(m.windows[1].x, 336);
        assert_eq!((m.x, m.y), (0, 0));
        assert!(m.show(3).is_err());
    }
    #[test]
    fn every_window_stays_within_each_supported_size() {
        for (w, h) in [(640, 480), (1024, 768), (4096, 2160)] {
            let mut m = Manager::new(w, h).unwrap();
            for i in 0..3 {
                m.show(i).unwrap();
                let r = m.windows[i];
                m.x = r.x + 8;
                m.y = r.y + 8;
                m.motion(Motion {
                    dx: 0,
                    dy: 0,
                    buttons: 1,
                });
                for d in [i16::MIN, i16::MAX] {
                    m.motion(Motion {
                        dx: d,
                        dy: d,
                        buttons: 1,
                    });
                    let r = m.windows[i];
                    assert!(r.x + r.w <= w && r.y + r.h <= h - 32 && r.y >= 40);
                }
                m.reset_input();
            }
        }
        assert!(Manager::new(639, 480).is_err());
        assert!(Manager::new(640, 479).is_err());
    }
    #[test]
    fn rectangle_intersection_uses_wide_arithmetic() {
        let a = Rect {
            x: 65530,
            y: 65530,
            w: 30,
            h: 30,
        };
        assert_eq!(
            a.intersect(Rect {
                x: 65535,
                y: 65535,
                w: 1,
                h: 1
            }),
            Some(Rect {
                x: 65535,
                y: 65535,
                w: 1,
                h: 1
            })
        );
        assert_eq!(
            a.intersect(Rect {
                x: 0,
                y: 0,
                w: 100,
                h: 100
            }),
            None
        );
    }
    #[test]
    fn clipped_tiles_preserve_source_bit_coordinates() {
        struct C;
        impl Canvas for C {
            fn fill(&mut self, _: u16, _: u16, _: u16, _: u16, _: u32) -> Result<(), Error> {
                panic!()
            }
            fn tile(
                &mut self,
                x: u16,
                y: u16,
                w: u16,
                h: u16,
                m: u64,
                _: u32,
                _: u32,
            ) -> Result<(), Error> {
                assert_eq!((x, y, w, h, m), (12, 13, 3, 2, 1));
                Ok(())
            }
        }
        let mut c = C;
        let mut clip = Clip {
            canvas: &mut c,
            rect: Rect {
                x: 12,
                y: 13,
                w: 3,
                h: 2,
            },
        };
        clip.tile(10, 10, 8, 8, 1 << 26, 0, 0).unwrap();
        clip.tile(100, 100, 8, 8, 0, 0, 0).unwrap();
    }
}
