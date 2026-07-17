#![no_std]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

use core::marker::PhantomData;
use core::ptr;
use core::sync::atomic::{AtomicU8, AtomicU32, AtomicUsize, Ordering};

use poole_handoff::{self, CoreRecord, Handoff, RECORD_FRAMEBUFFER, validate_kernel_entry_profile};

pub const ENTRY_CONTRACT_ID: &str = "PKENTRY1";
pub const BUILD_ID: &[u8] = b"PKBUILD1-CYCLE101-N6-KENTRY-001";
pub const ENTRY_OFFSET: u64 = 0x4000;
pub const EARLY_LOG_CAPACITY: usize = 4096;
pub const HANDOFF_MAGIC_U64: u64 = u64::from_le_bytes(poole_handoff::MAGIC);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum PanicCode {
    RustPanic = 0x1001,
    StackContract = 0x1002,
    HandoffEnvelope = 0x1003,
    HandoffDecode = 0x1004,
    HandoffProfile = 0x1005,
    RuntimeContinuity = 0x1006,
    UnexpectedReturn = 0x10ff,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PanicDisposition {
    Primary,
    Nested,
}

pub struct PanicState {
    depth: AtomicU32,
    last_code: AtomicU32,
}

impl PanicState {
    pub const fn new() -> Self {
        Self {
            depth: AtomicU32::new(0),
            last_code: AtomicU32::new(0),
        }
    }

    pub fn begin(&self, code: PanicCode) -> PanicDisposition {
        self.last_code.store(code as u32, Ordering::Release);
        if self.depth.fetch_add(1, Ordering::AcqRel) == 0 {
            PanicDisposition::Primary
        } else {
            PanicDisposition::Nested
        }
    }

    pub fn depth(&self) -> u32 {
        self.depth.load(Ordering::Acquire)
    }

    pub fn last_code(&self) -> u32 {
        self.last_code.load(Ordering::Acquire)
    }
}

impl Default for PanicState {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EntryError {
    NullHandoff,
    HandoffAlignment,
    HandoffLength,
    HandoffRange,
    NoncanonicalHandoff,
    Magic,
    NullStack,
    StackAlignment,
    NoncanonicalStack,
    Decode,
    KernelProfile,
    EntryMismatch,
    EntryOffset,
    StackMismatch,
}

impl EntryError {
    pub const fn panic_code(self) -> PanicCode {
        match self {
            Self::NullStack | Self::StackAlignment | Self::NoncanonicalStack => {
                PanicCode::StackContract
            }
            Self::Decode => PanicCode::HandoffDecode,
            Self::KernelProfile => PanicCode::HandoffProfile,
            Self::EntryMismatch | Self::EntryOffset | Self::StackMismatch => {
                PanicCode::RuntimeContinuity
            }
            _ => PanicCode::HandoffEnvelope,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FramebufferSpec {
    pub physical_base: u64,
    pub byte_count: u64,
    pub width: u32,
    pub height: u32,
    pub stride: u32,
    pub pixel_format: u32,
    pub foreground: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ValidatedEntry {
    pub core: CoreRecord,
    pub framebuffer: Option<FramebufferSpec>,
}

pub const fn is_canonical_x86_64(address: u64) -> bool {
    let upper = address >> 48;
    upper == 0 || upper == 0xffff
}

pub fn validate_entry_envelope(
    handoff_address: usize,
    handoff_length: usize,
    magic: u64,
    stack_top: usize,
) -> Result<(), EntryError> {
    if handoff_address == 0 {
        return Err(EntryError::NullHandoff);
    }
    if !handoff_address.is_multiple_of(8) {
        return Err(EntryError::HandoffAlignment);
    }
    if !(poole_handoff::HEADER_BYTES..=poole_handoff::MAX_TOTAL_BYTES).contains(&handoff_length) {
        return Err(EntryError::HandoffLength);
    }
    let handoff_end = handoff_address
        .checked_add(handoff_length - 1)
        .ok_or(EntryError::HandoffRange)?;
    if !is_canonical_x86_64(handoff_address as u64) || !is_canonical_x86_64(handoff_end as u64) {
        return Err(EntryError::NoncanonicalHandoff);
    }
    if magic != HANDOFF_MAGIC_U64 {
        return Err(EntryError::Magic);
    }
    if stack_top == 0 {
        return Err(EntryError::NullStack);
    }
    if !stack_top.is_multiple_of(16) {
        return Err(EntryError::StackAlignment);
    }
    if !is_canonical_x86_64(stack_top as u64) {
        return Err(EntryError::NoncanonicalStack);
    }
    Ok(())
}

pub fn validate_handoff(
    bytes: &[u8],
    runtime_entry: u64,
    stack_top: u64,
) -> Result<ValidatedEntry, EntryError> {
    let handoff = poole_handoff::decode(bytes).map_err(|_| EntryError::Decode)?;
    validate_kernel_entry_profile(&handoff).map_err(|_| EntryError::KernelProfile)?;
    let core = handoff.core().map_err(|_| EntryError::Decode)?;
    if core.kernel_entry_virtual != runtime_entry {
        return Err(EntryError::EntryMismatch);
    }
    if runtime_entry.checked_sub(core.kernel_virtual_base) != Some(ENTRY_OFFSET) {
        return Err(EntryError::EntryOffset);
    }
    if core.initial_stack_top_virtual != stack_top {
        return Err(EntryError::StackMismatch);
    }
    Ok(ValidatedEntry {
        core,
        framebuffer: framebuffer_spec(&handoff),
    })
}

fn read_u32(bytes: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ])
}

fn read_u64(bytes: &[u8], offset: usize) -> u64 {
    u64::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
        bytes[offset + 5],
        bytes[offset + 6],
        bytes[offset + 7],
    ])
}

fn framebuffer_spec(handoff: &Handoff<'_>) -> Option<FramebufferSpec> {
    let record = handoff.record(RECORD_FRAMEBUFFER)?;
    let payload = record.payload;
    if payload.len() != poole_handoff::FRAMEBUFFER_BYTES {
        return None;
    }
    let physical_base = read_u64(payload, 0);
    let byte_count = read_u64(payload, 8);
    if !framebuffer_identity_range_is_safe(physical_base, byte_count) {
        return None;
    }
    Some(FramebufferSpec {
        physical_base,
        byte_count,
        width: read_u32(payload, 16),
        height: read_u32(payload, 20),
        stride: read_u32(payload, 24),
        pixel_format: read_u32(payload, 28),
        foreground: read_u32(payload, 32) | read_u32(payload, 36) | read_u32(payload, 40),
    })
}

pub fn framebuffer_identity_range_is_safe(physical_base: u64, byte_count: u64) -> bool {
    if physical_base == 0
        || !physical_base.is_multiple_of(4)
        || byte_count == 0
        || !byte_count.is_multiple_of(4)
    {
        return false;
    }
    let Some(last_byte) = physical_base.checked_add(byte_count - 1) else {
        return false;
    };
    is_canonical_x86_64(physical_base) && is_canonical_x86_64(last_byte)
}

pub trait ByteSink {
    fn write_byte(&mut self, byte: u8);
}

pub struct EarlyRing {
    bytes: [AtomicU8; EARLY_LOG_CAPACITY],
    writes: AtomicUsize,
}

impl EarlyRing {
    pub const fn new() -> Self {
        Self {
            bytes: [const { AtomicU8::new(0) }; EARLY_LOG_CAPACITY],
            writes: AtomicUsize::new(0),
        }
    }

    pub fn push(&self, byte: u8) {
        let sequence = self.writes.fetch_add(1, Ordering::AcqRel);
        self.bytes[sequence % EARLY_LOG_CAPACITY].store(byte, Ordering::Release);
    }

    pub fn write(&self, bytes: &[u8]) {
        for byte in bytes {
            self.push(*byte);
        }
    }

    pub fn total_writes(&self) -> usize {
        self.writes.load(Ordering::Acquire)
    }

    pub fn snapshot(&self, output: &mut [u8]) -> usize {
        let total = self.total_writes();
        let count = total.min(EARLY_LOG_CAPACITY).min(output.len());
        let start = total.saturating_sub(count);
        for (index, target) in output[..count].iter_mut().enumerate() {
            *target = self.bytes[(start + index) % EARLY_LOG_CAPACITY].load(Ordering::Acquire);
        }
        count
    }
}

impl Default for EarlyRing {
    fn default() -> Self {
        Self::new()
    }
}

pub struct RingSink<'a>(pub &'a EarlyRing);

impl ByteSink for RingSink<'_> {
    fn write_byte(&mut self, byte: u8) {
        self.0.push(byte);
    }
}

pub struct EarlyLogger<S> {
    sink: S,
}

impl<S: ByteSink> EarlyLogger<S> {
    pub const fn new(sink: S) -> Self {
        Self { sink }
    }

    pub fn write_bytes(&mut self, bytes: &[u8]) {
        for byte in bytes {
            self.sink.write_byte(*byte);
        }
    }

    pub fn write_str(&mut self, text: &str) {
        self.write_bytes(text.as_bytes());
    }

    pub fn write_hex_u64(&mut self, value: u64) {
        const HEX: &[u8; 16] = b"0123456789ABCDEF";
        self.write_str("0x");
        for shift in (0..16).rev() {
            self.sink
                .write_byte(HEX[((value >> (shift * 4)) & 0xf) as usize]);
        }
    }

    pub fn write_decimal_u64(&mut self, mut value: u64) {
        let mut digits = [0u8; 20];
        let mut used = 0usize;
        loop {
            digits[used] = b'0' + (value % 10) as u8;
            used += 1;
            value /= 10;
            if value == 0 {
                break;
            }
        }
        while used != 0 {
            used -= 1;
            self.sink.write_byte(digits[used]);
        }
    }

    pub fn into_inner(self) -> S {
        self.sink
    }
}

pub struct Framebuffer<'a> {
    pixels: *mut u32,
    pixel_count: usize,
    width: usize,
    height: usize,
    stride: usize,
    foreground: u32,
    background: u32,
    cursor_x: usize,
    cursor_y: usize,
    _borrow: PhantomData<&'a mut [u32]>,
}

impl<'a> Framebuffer<'a> {
    pub fn from_slice(
        pixels: &'a mut [u32],
        width: usize,
        height: usize,
        stride: usize,
        foreground: u32,
        background: u32,
    ) -> Option<Self> {
        let pointer = pixels.as_mut_ptr();
        let count = pixels.len();
        // SAFETY: the pointer and length originate from the uniquely borrowed slice.
        unsafe {
            Self::from_raw_parts(
                pointer, count, width, height, stride, foreground, background,
            )
        }
    }

    /// Creates a volatile framebuffer sink over an already mapped writable range.
    ///
    /// # Safety
    ///
    /// `pixels..pixels + pixel_count` must remain mapped, writable, and exclusively
    /// borrowed for `'a`. The mapping must not be revoked while the sink exists.
    pub unsafe fn from_raw_parts(
        pixels: *mut u32,
        pixel_count: usize,
        width: usize,
        height: usize,
        stride: usize,
        foreground: u32,
        background: u32,
    ) -> Option<Self> {
        let required = stride.checked_mul(height)?;
        if pixels.is_null() || width < 6 || height < 8 || stride < width || required > pixel_count {
            return None;
        }
        Some(Self {
            pixels,
            pixel_count,
            width,
            height,
            stride,
            foreground,
            background,
            cursor_x: 0,
            cursor_y: 0,
            _borrow: PhantomData,
        })
    }

    fn write_pixel(&mut self, x: usize, y: usize, color: u32) {
        let Some(index) = y
            .checked_mul(self.stride)
            .and_then(|row| row.checked_add(x))
        else {
            return;
        };
        if x >= self.width || y >= self.height || index >= self.pixel_count {
            return;
        }
        // SAFETY: construction validated the complete stride-by-height range.
        unsafe { ptr::write_volatile(self.pixels.add(index), color) };
    }

    fn newline(&mut self) {
        self.cursor_x = 0;
        self.cursor_y += 8;
        if self.cursor_y + 7 >= self.height {
            self.cursor_y = 0;
        }
    }

    fn draw_glyph(&mut self, byte: u8) {
        if self.cursor_x + 5 >= self.width {
            self.newline();
        }
        let rows = glyph_rows(byte);
        for (row, bits) in rows.iter().enumerate() {
            for column in 0..5 {
                let color = if bits & (1 << (4 - column)) != 0 {
                    self.foreground
                } else {
                    self.background
                };
                self.write_pixel(self.cursor_x + column, self.cursor_y + row, color);
            }
        }
        self.cursor_x += 6;
    }
}

impl ByteSink for Framebuffer<'_> {
    fn write_byte(&mut self, byte: u8) {
        match byte {
            b'\n' => self.newline(),
            b'\r' => self.cursor_x = 0,
            value => self.draw_glyph(value.to_ascii_uppercase()),
        }
    }
}

fn glyph_rows(byte: u8) -> [u8; 7] {
    match byte {
        b' ' => [0, 0, 0, 0, 0, 0, 0],
        b'-' => [0, 0, 0, 0b11111, 0, 0, 0],
        b'.' => [0, 0, 0, 0, 0, 0b00110, 0b00110],
        b':' => [0, 0b00110, 0b00110, 0, 0b00110, 0b00110, 0],
        b'/' => [0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0, 0],
        b'0' => [
            0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110,
        ],
        b'1' => [
            0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110,
        ],
        b'2' => [
            0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111,
        ],
        b'3' => [
            0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110,
        ],
        b'4' => [
            0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010,
        ],
        b'5' => [
            0b11111, 0b10000, 0b10000, 0b11110, 0b00001, 0b00001, 0b11110,
        ],
        b'6' => [
            0b01110, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110,
        ],
        b'7' => [
            0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000,
        ],
        b'8' => [
            0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110,
        ],
        b'9' => [
            0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110,
        ],
        b'A' => [
            0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001,
        ],
        b'B' => [
            0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110,
        ],
        b'C' => [
            0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110,
        ],
        b'D' => [
            0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110,
        ],
        b'E' => [
            0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111,
        ],
        b'F' => [
            0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000,
        ],
        b'G' => [
            0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110,
        ],
        b'H' => [
            0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001,
        ],
        b'I' => [
            0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110,
        ],
        b'J' => [
            0b00111, 0b00010, 0b00010, 0b00010, 0b10010, 0b10010, 0b01100,
        ],
        b'K' => [
            0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001,
        ],
        b'L' => [
            0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111,
        ],
        b'M' => [
            0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001,
        ],
        b'N' => [
            0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001,
        ],
        b'O' => [
            0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110,
        ],
        b'P' => [
            0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000,
        ],
        b'Q' => [
            0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101,
        ],
        b'R' => [
            0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001,
        ],
        b'S' => [
            0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110,
        ],
        b'T' => [
            0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100,
        ],
        b'U' => [
            0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110,
        ],
        b'V' => [
            0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100,
        ],
        b'W' => [
            0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010,
        ],
        b'X' => [
            0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001,
        ],
        b'Y' => [
            0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100,
        ],
        b'Z' => [
            0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111,
        ],
        _ => [
            0b11111, 0b10001, 0b10101, 0b10101, 0b10001, 0b10001, 0b11111,
        ],
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec::Vec;

    #[derive(Default)]
    struct TestSink(Vec<u8>);

    impl ByteSink for TestSink {
        fn write_byte(&mut self, byte: u8) {
            self.0.push(byte);
        }
    }

    #[test]
    fn canonical_address_rules_cover_both_halves() {
        assert!(is_canonical_x86_64(0x0000_7fff_ffff_ffff));
        assert!(is_canonical_x86_64(0xffff_8000_0000_0000));
        assert!(!is_canonical_x86_64(0x0001_0000_0000_0000));
    }

    #[test]
    fn accepts_valid_entry_envelope() {
        assert_eq!(
            validate_entry_envelope(
                0xffff_9000_0000_0000,
                4096,
                HANDOFF_MAGIC_U64,
                0xffff_9000_0010_0000
            ),
            Ok(())
        );
    }

    #[test]
    fn rejects_null_and_misaligned_handoff() {
        assert_eq!(
            validate_entry_envelope(0, 4096, HANDOFF_MAGIC_U64, 0x1000),
            Err(EntryError::NullHandoff)
        );
        assert_eq!(
            validate_entry_envelope(0x1001, 4096, HANDOFF_MAGIC_U64, 0x2000),
            Err(EntryError::HandoffAlignment)
        );
    }

    #[test]
    fn rejects_bad_handoff_length_and_range() {
        assert_eq!(
            validate_entry_envelope(0x1000, 1, HANDOFF_MAGIC_U64, 0x2000),
            Err(EntryError::HandoffLength)
        );
        assert_eq!(
            validate_entry_envelope(usize::MAX - 255, 512, HANDOFF_MAGIC_U64, 0x2000,),
            Err(EntryError::HandoffRange)
        );
    }

    #[test]
    fn rejects_wrong_magic() {
        assert_eq!(
            validate_entry_envelope(0x1000, 4096, 0, 0x2000),
            Err(EntryError::Magic)
        );
    }

    #[test]
    fn rejects_bad_stack_contract() {
        assert_eq!(
            validate_entry_envelope(0x1000, 4096, HANDOFF_MAGIC_U64, 0),
            Err(EntryError::NullStack)
        );
        assert_eq!(
            validate_entry_envelope(0x1000, 4096, HANDOFF_MAGIC_U64, 0x2008),
            Err(EntryError::StackAlignment)
        );
    }

    #[test]
    fn ring_preserves_written_order() {
        let ring = EarlyRing::new();
        ring.write(b"POOLE");
        let mut output = [0u8; 8];
        assert_eq!(ring.snapshot(&mut output), 5);
        assert_eq!(&output[..5], b"POOLE");
    }

    #[test]
    fn ring_wraps_to_latest_bytes() {
        let ring = EarlyRing::new();
        for index in 0..EARLY_LOG_CAPACITY + 7 {
            ring.push((index & 0xff) as u8);
        }
        let mut output = [0u8; 7];
        assert_eq!(ring.snapshot(&mut output), 7);
        for (index, value) in output.iter().enumerate() {
            assert_eq!(*value, ((EARLY_LOG_CAPACITY + index) & 0xff) as u8);
        }
    }

    #[test]
    fn bounded_logger_formats_hex_and_decimal() {
        let mut logger = EarlyLogger::new(TestSink::default());
        logger.write_hex_u64(0x1234);
        logger.write_str("/");
        logger.write_decimal_u64(18_446_744_073_709_551_615);
        let output = logger.into_inner().0;
        assert_eq!(output, b"0x0000000000001234/18446744073709551615");
    }

    #[test]
    fn panic_state_distinguishes_nested_entry() {
        let state = PanicState::new();
        assert_eq!(state.begin(PanicCode::RustPanic), PanicDisposition::Primary);
        assert_eq!(
            state.begin(PanicCode::UnexpectedReturn),
            PanicDisposition::Nested
        );
        assert_eq!(state.depth(), 2);
        assert_eq!(state.last_code(), PanicCode::UnexpectedReturn as u32);
    }

    #[test]
    fn framebuffer_rejects_invalid_geometry() {
        let mut pixels = [0u32; 64];
        assert!(Framebuffer::from_slice(&mut pixels, 8, 8, 7, 1, 0).is_none());
    }

    #[test]
    fn framebuffer_identity_range_rejects_unsafe_addresses() {
        assert!(framebuffer_identity_range_is_safe(0x8000_0000, 4096));
        assert!(!framebuffer_identity_range_is_safe(0, 4096));
        assert!(!framebuffer_identity_range_is_safe(0x8000_0002, 4096));
        assert!(!framebuffer_identity_range_is_safe(0x8000_0000, 4095));
        assert!(!framebuffer_identity_range_is_safe(
            0x0000_ffff_ffff_f000,
            8192
        ));
        assert!(!framebuffer_identity_range_is_safe(u64::MAX - 3, 8));
    }

    #[test]
    fn framebuffer_draws_inside_declared_bounds() {
        let mut pixels = [0u32; 16 * 16];
        {
            let mut framebuffer = Framebuffer::from_slice(&mut pixels, 16, 16, 16, 0x00ff_ffff, 0)
                .expect("valid framebuffer");
            framebuffer.write_byte(b'A');
            framebuffer.write_byte(b'\n');
            framebuffer.write_byte(b'?');
        }
        assert!(pixels.iter().any(|pixel| *pixel == 0x00ff_ffff));
        assert_eq!(pixels.len(), 256);
    }
}
