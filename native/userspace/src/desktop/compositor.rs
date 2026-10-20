//! Retained text surfaces and damaged-region composition, entirely in CPL3.
#![forbid(unsafe_code)]
use super::{
    Canvas, Terminal, glyph,
    surfaces::Surfaces,
    windows::{Clip, Manager, Rect},
};
use crate::console::Error;
pub struct Damage(pub Option<Rect>);

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn interactive_wait_budget_covers_two_maximum_scene_compositions() {
        struct Work(u32);
        impl Canvas for Work {
            fn fill(&mut self, _: u16, _: u16, w: u16, h: u16, _: u32) -> Result<(), Error> {
                self.0 += u32::from(w).div_ceil(64) * u32::from(h).div_ceil(32);
                Ok(())
            }
            fn tile(
                &mut self,
                _: u16,
                _: u16,
                _: u16,
                _: u16,
                _: u64,
                _: u32,
                _: u32,
            ) -> Result<(), Error> {
                self.0 += 1;
                Ok(())
            }
        }
        use crate::desktop::surfaces::{Frame, OPEN, WRITE};
        for (w, h) in [(1000, 600), (1280, 800), (4096, 2160)] {
            let mut m = Manager::new(w, h).unwrap();
            let mut cells = [b'W'; 1920];
            let mut app = [0; 384];
            let mut terminal = Terminal::window(&mut cells);
            terminal.relocate(24, 84);
            terminal.cells.fill(b'W');
            let mut s = Surfaces::new(&mut app);
            for index in 0..2 {
                let handle = s.apply(4 + index, 1, Frame::new(OPEN, 1, 0)).0.handle;
                for row in 0..8 {
                    let mut f = Frame::new(WRITE, 2 + row, handle);
                    f.offset = 24 * row as u16;
                    f.len = 24;
                    f.data[..24].fill(b'W');
                    assert_eq!(s.apply(4 + index, 1, f).0.status, 0);
                }
                m.show(index as usize + 1).unwrap();
            }
            let mut work = Work(0);
            paint(&m, &terminal, &s, &mut work, m.bounds).unwrap();
            // Two consecutive full scenes, with one Again for each accepted draw
            // at the fixed32-command display queue. Ordinary4096 is insufficient.
            assert!(work.0 > 4096);
            assert!(work.0 * 4 < crate::desktop::surface_rpc::INPUT_POLL_LIMIT);
            let mut controls = crate::desktop::launch::Controls::new();
            controls.activate(2, true, &mut m).unwrap();
            work.0 = 0;
            paint_launch(&m, &terminal, &s, &mut work, m.bounds, &controls).unwrap();
            // Reserve the remaining characters up to the longest status label.
            assert!((work.0 + 7 * 4) * 4 < crate::desktop::surface_rpc::INPUT_POLL_LIMIT);
        }
    }
    #[test]
    fn terminal_region_skips_undamaged_glyphs() {
        struct Count(usize);
        impl Canvas for Count {
            fn fill(&mut self, _: u16, _: u16, _: u16, _: u16, _: u32) -> Result<(), Error> {
                Ok(())
            }
            fn tile(
                &mut self,
                _: u16,
                _: u16,
                _: u16,
                _: u16,
                _: u64,
                _: u32,
                _: u32,
            ) -> Result<(), Error> {
                self.0 += 1;
                Ok(())
            }
        }
        let mut cells = [0; 1920];
        let mut t = Terminal::window(&mut cells);
        t.relocate(24, 84);
        t.cells.fill(b'X');
        let mut c = Count(0);
        t.repaint_ink_region(
            &mut c,
            Rect {
                x: 36,
                y: 100,
                w: 12,
                h: 16,
            },
        )
        .unwrap();
        assert_eq!(c.0, 4);
        t.repaint_ink_region(
            &mut c,
            Rect {
                x: 0,
                y: 0,
                w: 12,
                h: 16,
            },
        )
        .unwrap();
        assert_eq!(c.0, 4);
        t.repaint_ink_region(
            &mut c,
            Rect {
                x: 35,
                y: 99,
                w: 2,
                h: 2,
            },
        )
        .unwrap();
        assert_eq!(c.0, 20);
    }
    #[test]
    fn composition_is_bounded_and_occlusion_matches_back_to_front_order() {
        struct Raster {
            w: usize,
            h: usize,
            p: std::vec::Vec<u32>,
        }
        impl Canvas for Raster {
            fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, c: u32) -> Result<(), Error> {
                assert!(
                    w > 0
                        && h > 0
                        && usize::from(x) + usize::from(w) <= self.w
                        && usize::from(y) + usize::from(h) <= self.h
                );
                for yy in y..y + h {
                    for xx in x..x + w {
                        self.p[usize::from(yy) * self.w + usize::from(xx)] = c;
                    }
                }
                Ok(())
            }
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
                assert!(w <= 8 && h <= 8);
                for yy in 0..h {
                    for xx in 0..w {
                        self.fill(
                            x + xx,
                            y + yy,
                            1,
                            1,
                            if m & (1 << (yy * 8 + xx)) != 0 {
                                fg
                            } else {
                                bg
                            },
                        )?;
                    }
                }
                Ok(())
            }
        }
        for (w, h) in [(640, 480), (1024, 768)] {
            let mut m = Manager::new(w, h).unwrap();
            let mut cells = [0; 1920];
            let mut app = [0; 384];
            let mut t = Terminal::window(&mut cells);
            t.relocate(24, 84);
            let s = Surfaces::new(&mut app);
            let mut c = Raster {
                w: usize::from(w),
                h: usize::from(h),
                p: std::vec![0;usize::from(w)*usize::from(h)],
            };
            paint(&m, &t, &s, &mut c, m.bounds).unwrap();
            m.show(1).unwrap();
            m.focus = Some(0);
            let r = m.windows[1];
            paint(&m, &t, &s, &mut c, r).unwrap();
            paint(
                &m,
                &t,
                &s,
                &mut c,
                Rect {
                    x: 0,
                    y: h - 32,
                    w,
                    h: 32,
                },
            )
            .unwrap();
            let incremental = c.p.clone();
            paint(&m, &t, &s, &mut c, m.bounds).unwrap();
            assert_eq!(incremental, c.p);
            let at = usize::from(r.y + 30) * c.w + usize::from(r.x + 4);
            assert_eq!(c.p[at], 0xf8faf9);
            m.visible[1] = false;
            paint(&m, &t, &s, &mut c, r).unwrap();
            if w == 640 {
                assert_eq!(c.p[at], super::super::PAPER);
            }
            assert!(c.p.iter().all(|&v| v != 0));
        }
    }
}
impl Damage {
    #[inline]
    pub fn add(&mut self, r: Rect) {
        self.0 = Some(if let Some(old) = self.0 {
            let x = old.x.min(r.x);
            let y = old.y.min(r.y);
            Rect {
                x,
                y,
                w: old
                    .x
                    .saturating_add(old.w)
                    .max(r.x.saturating_add(r.w))
                    .saturating_sub(x),
                h: old
                    .y
                    .saturating_add(old.h)
                    .max(r.y.saturating_add(r.h))
                    .saturating_sub(y),
            }
        } else {
            r
        });
    }
}
impl Canvas for Damage {
    #[inline]
    fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, _: u32) -> Result<(), Error> {
        self.add(Rect { x, y, w, h });
        Ok(())
    }
    #[inline]
    fn tile(
        &mut self,
        x: u16,
        y: u16,
        w: u16,
        h: u16,
        _: u64,
        _: u32,
        _: u32,
    ) -> Result<(), Error> {
        self.add(Rect { x, y, w, h });
        Ok(())
    }
}
#[inline(never)]
fn text(c: &mut impl Canvas, x: u16, y: u16, s: &[u8], fg: u32, bg: u32) -> Result<(), Error> {
    for (i, &b) in s.iter().enumerate() {
        glyph(
            c,
            x.saturating_add((i as u16).saturating_mul(12)),
            y,
            b,
            fg,
            bg,
        )?;
    }
    Ok(())
}
pub fn paint(
    m: &Manager,
    t: &Terminal<'_>,
    s: &Surfaces<'_>,
    canvas: &mut impl Canvas,
    damage: Rect,
) -> Result<(), Error> {
    paint_mode(m, t, s, canvas, damage, None)
}
#[inline]
pub fn paint_launch(
    m: &Manager,
    t: &Terminal<'_>,
    s: &Surfaces<'_>,
    canvas: &mut impl Canvas,
    damage: Rect,
    controls: &super::launch::Controls,
) -> Result<(), Error> {
    paint_mode(m, t, s, canvas, damage, Some(controls))
}
// Keep one renderer when ordinary terminal writes and launch-status paints coexist.
#[inline(never)]
fn paint_mode(
    m: &Manager,
    t: &Terminal<'_>,
    s: &Surfaces<'_>,
    canvas: &mut impl Canvas,
    damage: Rect,
    controls: Option<&super::launch::Controls>,
) -> Result<(), Error> {
    let mut c = Clip {
        canvas,
        rect: damage,
    };
    c.fill(0, 0, m.bounds.w, m.bounds.h, 0xd3dfdf)?;
    c.fill(0, 0, m.bounds.w, 32, 0xf7faf9)?;
    text(&mut c, 16, 8, b"PooleOS", 0x235b4b, 0xf7faf9)?;
    if let Some(controls) = controls {
        if let Some(app) = controls.last() {
            let name: &[u8] = if app == crate::session_control::App::Text {
                b"Text: "
            } else {
                b"Numbers: "
            };
            let status = controls.label(app);
            let surface: &[u8] = if m.available[app.index() + 1] {
                b" / surface"
            } else {
                b" / no surface"
            };
            let mut x = 144;
            for part in [name, status, surface] {
                text(&mut c, x, 8, part, 0x253e37, 0xf7faf9)?;
                x = x.saturating_add((part.len() as u16).saturating_mul(12));
            }
        }
    }
    for &i in &m.order {
        if i >= 3 {
            return Err(Error::Hardware);
        }
        if !m.visible[i] {
            continue;
        }
        let r = m.windows[i];
        if r.intersect(damage).is_none() {
            continue;
        }
        let border = if m.focus == Some(i) {
            0x508d78
        } else {
            0x829090
        };
        c.fill(r.x, r.y, r.w, r.h, border)?;
        let title = if m.focus == Some(i) {
            0xf7faf9
        } else {
            0xe2e8e6
        };
        c.fill(
            r.x.saturating_add(1),
            r.y.saturating_add(1),
            r.w.saturating_sub(2),
            27,
            title,
        )?;
        text(
            &mut c,
            r.x.saturating_add(10),
            r.y.saturating_add(6),
            match i {
                0 => b"Terminal",
                1 => b"PooleText",
                _ => b"PooleNumbers",
            },
            0x253e37,
            title,
        )?;
        c.fill(
            r.x.saturating_add(r.w).saturating_sub(20),
            r.y.saturating_add(17),
            10,
            2,
            0x253e37,
        )?;
        let bg = if i == 0 { super::PAPER } else { 0xf8faf9 };
        c.fill(
            r.x.saturating_add(1),
            r.y.saturating_add(28),
            r.w.saturating_sub(2),
            r.h.saturating_sub(29),
            bg,
        )?;
        if i == 0 {
            t.repaint_ink_region(&mut c, damage)?;
        } else {
            let cells = s.cells(i - 1).ok_or(Error::Hardware)?;
            for (j, &b) in cells.iter().enumerate() {
                if b != b' ' {
                    glyph(
                        &mut c,
                        r.x.saturating_add(8).saturating_add((j % 24) as u16 * 12),
                        r.y.saturating_add(36)
                            .saturating_add(((j / 24) as u16).saturating_mul(16)),
                        b,
                        0x293b35,
                        bg,
                    )?;
                }
            }
        }
    }
    let y = m.bounds.h.saturating_sub(32);
    c.fill(0, y, m.bounds.w, 32, 0xf7faf9)?;
    for i in 0..3 {
        if controls.is_none() && !m.available[i] {
            continue;
        }
        let x = i as u16 * 160;
        text(
            &mut c,
            x + 12,
            y.saturating_add(8),
            match i {
                0 => b"Terminal",
                1 => b"Text",
                _ => b"Numbers",
            },
            0x253e37,
            0xf7faf9,
        )?;
        if m.focus == Some(i) {
            c.fill(x + 12, y.saturating_add(29), 120, 3, 0x508d78)?;
        }
    }
    // A small two-tone pointer stays legible on both content and window chrome.
    for dy in 0..18u16 {
        let width = if dy < 12 { 1 + dy / 2 } else { 3 };
        c.fill(m.x, m.y.saturating_add(dy), width, 1, 0x172b24)?;
        if dy > 2 && dy < 11 && width > 2 {
            c.fill(
                m.x.saturating_add(1),
                m.y.saturating_add(dy),
                width - 2,
                1,
                0xffffff,
            )?;
        }
    }
    Ok(())
}
