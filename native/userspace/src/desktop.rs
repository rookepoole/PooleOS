//! Native local console policy. No kernel link, allocator, firmware calls or ports.
#![forbid(unsafe_code)]
use crate::console::Error;
pub mod font;
pub mod keyboard;

pub const MAX_COLUMNS: usize = 80;
pub const MAX_ROWS: usize = 24;
pub const INK: u32 = 0xdce9e3;
pub const PAPER: u32 = 0x18221e;

pub trait Canvas {
    fn fill(&mut self, x: u16, y: u16, width: u16, height: u16, color: u32) -> Result<(), Error>;
    fn tile(
        &mut self,
        x: u16,
        y: u16,
        width: u16,
        height: u16,
        mask: u64,
        foreground: u32,
        background: u32,
    ) -> Result<(), Error>;
}

#[inline]
pub fn glyph(
    canvas: &mut impl Canvas,
    x: u16,
    y: u16,
    byte: u8,
    fg: u32,
    bg: u32,
) -> Result<(), Error> {
    let rows = font::rows(byte);
    for ty in 0..2 {
        for tx in 0..2 {
            let mut mask = 0;
            for py in 0..8 {
                for px in 0..8 {
                    let gx = (tx * 8 + px) / 2;
                    let gy = (ty * 8 + py) / 2;
                    if gx < 5 && gy < 7 && rows[gy] & (1 << (4 - gx)) != 0 {
                        mask |= 1 << (py * 8 + px);
                    }
                }
            }
            canvas.tile(
                x.checked_add((tx * 8) as u16).ok_or(Error::Hardware)?,
                y.checked_add((ty * 8) as u16).ok_or(Error::Hardware)?,
                if tx == 0 { 8 } else { 4 },
                8,
                mask,
                fg,
                bg,
            )?;
        }
    }
    Ok(())
}

pub struct Terminal<'a> {
    cells: &'a mut [u8; MAX_COLUMNS * MAX_ROWS],
    columns: usize,
    rows: usize,
    column: usize,
    row: usize,
    left: u16,
    top: u16,
}
impl<'a> Terminal<'a> {
    #[inline(always)]
    pub fn new(
        width: u16,
        height: u16,
        cells: &'a mut [u8; MAX_COLUMNS * MAX_ROWS],
    ) -> Result<Self, Error> {
        if width < 320 || height < 200 {
            return Err(Error::Hardware);
        }
        for cell in cells.iter_mut() {
            *cell = core::hint::black_box(b' ');
        }
        Ok(Self {
            cells,
            columns: usize::from((width - 48) / 12).min(MAX_COLUMNS),
            rows: usize::from((height - 104) / 16).min(MAX_ROWS),
            column: 0,
            row: 0,
            left: 24,
            top: 72,
        })
    }
    pub fn paint(&self, canvas: &mut impl Canvas, width: u16, height: u16) -> Result<(), Error> {
        canvas.fill(0, 0, width, height, 0xe8eeeb)?;
        canvas.fill(0, 0, width, 48, 0xf8faf9)?;
        canvas.fill(0, 47, width, 1, 0xb4c6bd)?;
        for (i, &b) in b"PooleOS".iter().enumerate() {
            glyph(canvas, 24 + i as u16 * 12, 16, b, 0x235b4b, 0xf8faf9)?;
        }
        for (i, &b) in b"Terminal".iter().enumerate() {
            glyph(canvas, 136 + i as u16 * 12, 16, b, 0x35463e, 0xf8faf9)?;
        }
        canvas.fill(
            self.left.saturating_sub(8),
            self.top.saturating_sub(8),
            self.columns.saturating_mul(12).saturating_add(16) as u16,
            self.rows.saturating_mul(16).saturating_add(16) as u16,
            PAPER,
        )?;
        self.cursor(canvas)
    }
    fn cell(&self, canvas: &mut impl Canvas, col: usize, row: usize) -> Result<(), Error> {
        glyph(
            canvas,
            self.left
                .checked_add((col as u16).checked_mul(12).ok_or(Error::Hardware)?)
                .ok_or(Error::Hardware)?,
            self.top
                .checked_add((row as u16).checked_mul(16).ok_or(Error::Hardware)?)
                .ok_or(Error::Hardware)?,
            *self
                .cells
                .get(row.saturating_mul(MAX_COLUMNS).saturating_add(col))
                .ok_or(Error::Hardware)?,
            INK,
            PAPER,
        )
    }
    fn cursor(&self, canvas: &mut impl Canvas) -> Result<(), Error> {
        canvas.fill(
            self.left
                .saturating_add((self.column as u16).saturating_mul(12)),
            self.top
                .saturating_add((self.row as u16).saturating_mul(16))
                .saturating_add(14),
            10,
            2,
            0x79c9a8,
        )
    }
    fn newline(&mut self, canvas: &mut impl Canvas) -> Result<(), Error> {
        self.column = 0;
        if self.row.saturating_add(1) < self.rows {
            self.row = self.row.saturating_add(1);
        } else {
            let end = self.rows.saturating_mul(MAX_COLUMNS);
            for i in 0..end {
                let byte = if i.saturating_add(MAX_COLUMNS) < end {
                    *self
                        .cells
                        .get(i.saturating_add(MAX_COLUMNS))
                        .ok_or(Error::Hardware)?
                } else {
                    b' '
                };
                // Avoid an implicit freestanding memmove/memset runtime dependency.
                let cell = self.cells.get_mut(i).ok_or(Error::Hardware)?;
                let changed = *cell != byte;
                *cell = core::hint::black_box(byte);
                if changed && i % MAX_COLUMNS < self.columns {
                    self.cell(canvas, i % MAX_COLUMNS, i / MAX_COLUMNS)?;
                }
            }
        }
        Ok(())
    }
    pub fn write(&mut self, canvas: &mut impl Canvas, byte: u8) -> Result<(), Error> {
        self.cell(canvas, self.column, self.row)?;
        match byte {
            b'\r' => self.column = 0,
            b'\n' => self.newline(canvas)?,
            8 => self.column = self.column.saturating_sub(1),
            32..=126 => {
                *self
                    .cells
                    .get_mut(
                        self.row
                            .saturating_mul(MAX_COLUMNS)
                            .saturating_add(self.column),
                    )
                    .ok_or(Error::Hardware)? = byte;
                self.cell(canvas, self.column, self.row)?;
                if self.column.saturating_add(1) == self.columns {
                    self.newline(canvas)?;
                } else {
                    self.column = self.column.saturating_add(1);
                }
            }
            _ => {}
        }
        self.cursor(canvas)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Bounds {
        w: u16,
        h: u16,
        count: usize,
    }
    impl Canvas for Bounds {
        fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, _: u32) -> Result<(), Error> {
            assert!(
                w > 0
                    && h > 0
                    && u32::from(x) + u32::from(w) <= u32::from(self.w)
                    && u32::from(y) + u32::from(h) <= u32::from(self.h)
            );
            self.count += 1;
            Ok(())
        }
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
            assert!(w <= 8 && h <= 8);
            self.fill(x, y, w, h, 0)
        }
    }
    #[test]
    fn terminal_fits_small_and_large_displays_and_scrolls_without_overflow() {
        for (w, h) in [
            (320, 200),
            (640, 480),
            (1024, 768),
            (1920, 1080),
            (4096, 2160),
        ] {
            let mut c = Bounds { w, h, count: 0 };
            let mut cells = [0; MAX_COLUMNS * MAX_ROWS];
            let mut t = Terminal::new(w, h, &mut cells).unwrap();
            t.paint(&mut c, w, h).unwrap();
            for _ in 0..30 {
                for &b in b"abcdefghijklmnopqrstuvwxyz0123456789\r\n" {
                    t.write(&mut c, b).unwrap();
                }
            }
            assert!(c.count > 100);
            assert!(t.row < t.rows && t.column < t.columns);
        }
        let mut cells = [0; MAX_COLUMNS * MAX_ROWS];
        assert!(Terminal::new(319, 200, &mut cells).is_err());
        assert!(Terminal::new(320, 199, &mut cells).is_err());
    }
    #[test]
    fn terminal_preserves_case_backspace_crlf_and_controls_are_not_escape_sequences() {
        let mut c = Bounds {
            w: 640,
            h: 480,
            count: 0,
        };
        let mut cells = [0; MAX_COLUMNS * MAX_ROWS];
        let mut t = Terminal::new(640, 480, &mut cells).unwrap();
        for &b in b"AbC\x08 \x08d\r\nZ\x1b" {
            t.write(&mut c, b).unwrap();
        }
        assert_eq!(&t.cells[..3], b"Abd");
        assert_eq!(t.cells[MAX_COLUMNS], b'Z');
        assert_eq!((t.column, t.row), (1, 1));
    }
    #[test]
    fn terminal_scroll_retains_lines_in_order_and_clears_last_row() {
        let mut c = Bounds {
            w: 320,
            h: 200,
            count: 0,
        };
        let mut cells = [0; MAX_COLUMNS * MAX_ROWS];
        let mut t = Terminal::new(320, 200, &mut cells).unwrap();
        for i in 0..10 {
            t.write(&mut c, b'0' + i).unwrap();
            t.write(&mut c, b'\n').unwrap();
        }
        assert_eq!(t.cells[0], b'5');
        assert_eq!(t.cells[4 * MAX_COLUMNS], b'9');
        assert!(
            t.cells[5 * MAX_COLUMNS..6 * MAX_COLUMNS]
                .iter()
                .all(|b| *b == b' ')
        );
        for _ in 0..6 {
            t.write(&mut c, b'\n').unwrap();
        }
        let before = c.count;
        t.write(&mut c, b'\n').unwrap();
        assert_eq!(c.count - before, 5, "unchanged cells must not be repainted");
    }
}
