//! Incremental ASCII text counts and bounded signed-i32 single-column summaries.
use super::{INVALID_DATA, Kind, LIMIT, MAX_FILE_BYTES, MAX_ROWS};

pub struct Accumulator {
    kind: Kind,
    bytes: u32,
    lines: u32,
    words: u32,
    in_word: bool,
    row: [u8; 11],
    used: usize,
    cr: bool,
    first: bool,
    count: u32,
    sum: i64,
    min: i32,
    max: i32,
    failed: bool,
    finished: bool,
}
impl Accumulator {
    #[inline(always)]
    pub const fn new(kind: Kind) -> Self {
        Self {
            kind,
            bytes: 0,
            lines: 0,
            words: 0,
            in_word: false,
            row: [0; 11],
            used: 0,
            cr: false,
            first: true,
            count: 0,
            sum: 0,
            min: 0,
            max: 0,
            failed: false,
            finished: false,
        }
    }
    #[inline(always)]
    fn end_row(&mut self) -> Result<(), u8> {
        let row = self.row.get(..self.used).ok_or(INVALID_DATA)?;
        if self.first && crate::files::same_bytes(row, b"value") {
            self.first = false;
            self.used = 0;
            return Ok(());
        }
        self.first = false;
        let negative = row.first() == Some(&b'-');
        let digits = row.get(usize::from(negative)..).ok_or(INVALID_DATA)?;
        if digits.is_empty() || digits.len() > 10 {
            return Err(INVALID_DATA);
        }
        let mut magnitude = 0u32;
        for &byte in digits {
            if !byte.is_ascii_digit() {
                return Err(INVALID_DATA);
            }
            magnitude = magnitude
                .checked_mul(10)
                .and_then(|v| v.checked_add(u32::from(byte - b'0')))
                .ok_or(INVALID_DATA)?;
        }
        if magnitude > i32::MAX as u32 + u32::from(negative) {
            return Err(INVALID_DATA);
        }
        let signed = if negative {
            -i64::from(magnitude)
        } else {
            i64::from(magnitude)
        };
        if self.count >= MAX_ROWS {
            return Err(LIMIT);
        }
        let number = signed as i32;
        if self.count == 0 {
            self.min = number;
            self.max = number;
        }
        self.min = self.min.min(number);
        self.max = self.max.max(number);
        self.sum = self.sum.checked_add(signed).ok_or(LIMIT)?;
        self.count = self.count.checked_add(1).ok_or(LIMIT)?;
        self.used = 0;
        Ok(())
    }
    #[inline(always)]
    fn byte(&mut self, byte: u8) -> Result<(), u8> {
        self.bytes = self
            .bytes
            .checked_add(1)
            .filter(|&n| n <= MAX_FILE_BYTES)
            .ok_or(LIMIT)?;
        if self.kind == Kind::Text {
            if !matches!(byte, 32..=126 | b'\r' | b'\n' | b'\t') {
                return Err(INVALID_DATA);
            }
            let space = matches!(byte, b' ' | b'\r' | b'\n' | b'\t');
            if !space && !self.in_word {
                self.words = self.words.checked_add(1).ok_or(LIMIT)?;
            }
            self.in_word = !space;
            if byte == b'\n' {
                self.lines = self.lines.checked_add(1).ok_or(LIMIT)?;
            }
        } else {
            if self.cr && byte != b'\n' {
                return Err(INVALID_DATA);
            }
            match byte {
                b'\r' => self.cr = true,
                b'\n' => {
                    self.cr = false;
                    self.end_row()?;
                }
                _ => {
                    *self.row.get_mut(self.used).ok_or(INVALID_DATA)? = byte;
                    self.used = self.used.checked_add(1).ok_or(INVALID_DATA)?;
                }
            }
        }
        Ok(())
    }
    #[inline(always)]
    pub fn push(&mut self, bytes: &[u8]) -> Result<(), u8> {
        if self.failed || self.finished {
            return Err(INVALID_DATA);
        }
        for &byte in bytes {
            if let Err(error) = self.byte(byte) {
                self.failed = true;
                return Err(error);
            }
        }
        Ok(())
    }
    /// Text: bytes, words, LF count, zero. Numbers: count, sum, min, max.
    /// An empty numeric dataset has all-zero results, distinguished by count.
    #[inline(always)]
    pub fn finish(&mut self) -> Result<[i64; 4], u8> {
        if self.failed || self.finished {
            return Err(INVALID_DATA);
        }
        self.finished = true;
        if self.kind == Kind::Text {
            return Ok([
                i64::from(self.bytes),
                i64::from(self.words),
                i64::from(self.lines),
                0,
            ]);
        }
        if self.cr {
            return Err(INVALID_DATA);
        }
        if self.used != 0 {
            self.end_row()?;
        }
        Ok([
            i64::from(self.count),
            self.sum,
            i64::from(self.min),
            i64::from(self.max),
        ])
    }
}
#[cfg(test)]
mod tests;
