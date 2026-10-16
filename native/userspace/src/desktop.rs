//! Native local console policy. No kernel link, allocator, firmware calls or ports.
#![forbid(unsafe_code)]
use crate::console::Error;
pub mod compositor;
pub mod font;
pub mod input;
pub mod keyboard;
pub mod mouse;
pub mod publisher;
pub mod surface_rpc;
pub mod surfaces;
pub mod windows;

pub const MAX_COLUMNS: usize = 80;
pub const MAX_ROWS: usize = 24;
pub const INK: u32 = 0xdce9e3;
pub const PAPER: u32 = 0x18221e;

const EXPANDED_ROWS: [u8; 16] = {
    let mut table = [0; 16];
    let mut i = 0;
    while i < 16 {
        let row = i as u8;
        table[i] =
            ((row & 8) >> 3) * 3 | ((row & 4) >> 2) * 12 | ((row & 2) >> 1) * 48 | (row & 1) * 192;
        i += 1;
    }
    table
};

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
            let mut mask = 0u64;
            for py in 0..4 {
                let row = rows.get(ty * 4 + py).copied().unwrap_or(0);
                // Expand five font bits, select this tile's byte and duplicate
                // vertically. The eighth source row is blank padding.
                let half = if tx == 0 {
                    EXPANDED_ROWS[usize::from((row >> 1) & 15)]
                } else {
                    (row & 1) * 3
                };
                mask |= (u64::from(half) * 0x101) << (py * 16);
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
    pub fn window(cells: &'a mut [u8; MAX_COLUMNS * MAX_ROWS]) -> Self {
        for cell in cells.iter_mut() {
            *cell = core::hint::black_box(b' ');
        }
        Self {
            cells,
            columns: 48,
            rows: 19,
            column: 0,
            row: 0,
            left: 0,
            top: 0,
        }
    }
    #[inline]
    pub fn relocate(&mut self, left: u16, top: u16) {
        self.left = left;
        self.top = top;
    }
    pub fn repaint(&self, canvas: &mut impl Canvas) -> Result<(), Error> {
        for row in 0..self.rows {
            for col in 0..self.columns {
                self.cell(canvas, col, row)?;
            }
        }
        self.cursor(canvas)
    }
    /// Paint nonblank cells over an already-cleared PAPER background.
    #[inline]
    pub fn repaint_ink_region(
        &self,
        canvas: &mut impl Canvas,
        damage: windows::Rect,
    ) -> Result<(), Error> {
        let first_col = usize::from(damage.x.saturating_sub(self.left) / 12).min(self.columns);
        let first_row = usize::from(damage.y.saturating_sub(self.top) / 16).min(self.rows);
        let last_col = ((u32::from(damage.x) + u32::from(damage.w))
            .saturating_sub(u32::from(self.left))
            .div_ceil(12) as usize)
            .min(self.columns);
        let last_row = ((u32::from(damage.y) + u32::from(damage.h))
            .saturating_sub(u32::from(self.top))
            .div_ceil(16) as usize)
            .min(self.rows);
        for row in first_row..last_row {
            for col in first_col..last_col {
                if *self
                    .cells
                    .get(row.saturating_mul(MAX_COLUMNS).saturating_add(col))
                    .ok_or(Error::Hardware)?
                    != b' '
                {
                    self.cell(canvas, col, row)?;
                }
            }
        }
        self.cursor(canvas)
    }
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
    type Tile = (u16, u16, u16, u16, u64, u32, u32);
    #[derive(Default)]
    struct Tiles {
        calls: std::vec::Vec<Tile>,
        fail_at: Option<usize>,
    }
    impl Canvas for Tiles {
        fn fill(&mut self, _: u16, _: u16, _: u16, _: u16, _: u32) -> Result<(), Error> {
            panic!("glyph must preserve its tile-only interface")
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
            self.calls.push((x, y, w, h, m, fg, bg));
            if self.fail_at == Some(self.calls.len()) {
                Err(Error::Transport)
            } else {
                Ok(())
            }
        }
    }
    #[test]
    fn expanded_glyphs_match_pixel_oracle_for_every_byte() {
        for byte in 0..=255 {
            let rows = font::rows(byte);
            let mut c = Tiles::default();
            glyph(&mut c, 13, 29, byte, INK, PAPER).unwrap();
            assert_eq!(c.calls.len(), 4);
            for (i, &(x, y, w, h, mask, fg, bg)) in c.calls.iter().enumerate() {
                let tx = i % 2;
                let ty = i / 2;
                let mut expected = 0;
                for py in 0..8 {
                    for px in 0..8 {
                        let gx = (tx * 8 + px) / 2;
                        let gy = (ty * 8 + py) / 2;
                        if gx < 5 && gy < 7 && rows[gy] & (1 << (4 - gx)) != 0 {
                            expected |= 1u64 << (py * 8 + px);
                        }
                    }
                }
                assert_eq!(
                    (x, y, w, h, mask, fg, bg),
                    (
                        13 + (tx * 8) as u16,
                        29 + (ty * 8) as u16,
                        if tx == 0 { 8 } else { 4 },
                        8,
                        expected,
                        INK,
                        PAPER
                    ),
                    "byte={byte} tile={i}"
                );
            }
        }
    }
    #[test]
    fn glyph_stops_at_transport_or_coordinate_failure_without_later_tiles() {
        for fail_at in 1..=4 {
            let mut c = Tiles {
                fail_at: Some(fail_at),
                ..Tiles::default()
            };
            assert!(matches!(
                glyph(&mut c, 0, 0, b'X', INK, PAPER),
                Err(Error::Transport)
            ));
            assert_eq!(c.calls.len(), fail_at);
        }
        for (x, y, accepted) in [(65528, 0, 1), (0, 65528, 2), (65527, 65527, 4)] {
            let mut c = Tiles::default();
            let result = glyph(&mut c, x, y, b'X', INK, PAPER);
            assert_eq!(result.is_ok(), accepted == 4);
            assert_eq!(c.calls.len(), accepted);
        }
    }
    struct Raster {
        pixels: std::vec::Vec<u32>,
        tiles: usize,
        fills: usize,
    }
    impl Raster {
        fn new() -> Self {
            Self {
                pixels: std::vec![0xabcdef; 640 * 480],
                tiles: 0,
                fills: 0,
            }
        }
    }
    impl Canvas for Raster {
        fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, color: u32) -> Result<(), Error> {
            assert!(
                w > 0
                    && h > 0
                    && u32::from(x) + u32::from(w) <= 640
                    && u32::from(y) + u32::from(h) <= 480
            );
            self.fills += 1;
            for yy in y..y + h {
                for xx in x..x + w {
                    self.pixels[usize::from(yy) * 640 + usize::from(xx)] = color;
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
            mask: u64,
            fg: u32,
            bg: u32,
        ) -> Result<(), Error> {
            assert!(w > 0 && w <= 8 && h > 0 && h <= 8 && x + w <= 640 && y + h <= 480);
            self.tiles += 1;
            for yy in 0..h {
                for xx in 0..w {
                    self.pixels[usize::from(y + yy) * 640 + usize::from(x + xx)] =
                        if mask & (1 << (yy * 8 + xx)) != 0 {
                            fg
                        } else {
                            bg
                        };
                }
            }
            Ok(())
        }
    }
    fn region(t: &Terminal, damage: windows::Rect, optimized: bool) -> Raster {
        let mut pixels = Raster::new();
        let mut clip = windows::Clip {
            canvas: &mut pixels,
            rect: damage,
        };
        clip.fill(
            t.left,
            t.top,
            (t.columns * 12) as u16,
            (t.rows * 16) as u16,
            PAPER,
        )
        .unwrap();
        if optimized {
            t.repaint_ink_region(&mut clip, damage).unwrap();
        } else {
            t.repaint(&mut clip).unwrap();
        }
        pixels
    }
    #[test]
    fn sparse_ink_repaint_matches_full_cells_at_damage_edges_and_after_scrolling() {
        let mut cells = [0; MAX_COLUMNS * MAX_ROWS];
        let mut t = Terminal::window(&mut cells);
        t.relocate(24, 84);
        let mut sink = compositor::Damage(None);
        for line in 0..24 {
            for &byte in if line % 2 == 0 {
                &b"Sparse words X\r\n"[..]
            } else {
                &b" \r\n"[..]
            } {
                t.write(&mut sink, byte).unwrap();
            }
        }
        for dense in [false, true] {
            if dense {
                t.cells.fill(b'W');
            }
            for damage in [
                windows::Rect {
                    x: 0,
                    y: 0,
                    w: 640,
                    h: 480,
                },
                windows::Rect {
                    x: 23,
                    y: 83,
                    w: 2,
                    h: 2,
                },
                windows::Rect {
                    x: 35,
                    y: 99,
                    w: 2,
                    h: 2,
                },
                windows::Rect {
                    x: 36,
                    y: 100,
                    w: 12,
                    h: 16,
                },
                windows::Rect {
                    x: 595,
                    y: 380,
                    w: 45,
                    h: 100,
                },
                windows::Rect {
                    x: 0,
                    y: 0,
                    w: 8,
                    h: 8,
                },
                windows::Rect {
                    x: 600,
                    y: 388,
                    w: 40,
                    h: 40,
                },
                windows::Rect {
                    x: 0,
                    y: 0,
                    w: 0,
                    h: 0,
                },
            ] {
                let reference = region(&t, damage, false);
                let current = region(&t, damage, true);
                assert_eq!(
                    current.pixels, reference.pixels,
                    "dense={dense} damage={damage:?}"
                );
                assert!(current.tiles <= reference.tiles);
                for (at, &pixel) in current.pixels.iter().enumerate() {
                    if !damage.contains((at % 640) as u16, (at / 640) as u16) {
                        assert_eq!(pixel, 0xabcdef);
                    }
                }
            }
        }
    }
    #[test]
    fn blank_window_repaint_removes_all_3648_empty_tile_calls() {
        let mut cells = [0; MAX_COLUMNS * MAX_ROWS];
        let mut t = Terminal::window(&mut cells);
        t.relocate(24, 84);
        let r = windows::Rect {
            x: 0,
            y: 0,
            w: 640,
            h: 480,
        };
        let old = region(&t, r, false);
        let new = region(&t, r, true);
        assert_eq!(old.pixels, new.pixels);
        assert_eq!(
            (old.tiles, new.tiles, old.fills, new.fills),
            (3648, 0, 2, 2)
        );
        std::println!(
            "blank_terminal old_tiles={} new_tiles={} background_and_cursor_fills={}",
            old.tiles,
            new.tiles,
            new.fills
        );
    }
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
