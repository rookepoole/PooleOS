//! PAPP1 bounded file applications. Computation and job policy stay in user space.
#![forbid(unsafe_code)]
pub mod program;
pub mod stats;
pub mod wire;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Kind {
    Text = 1,
    Numbers = 2,
}
impl Kind {
    #[inline(always)]
    pub fn decode(byte: u8) -> Option<Self> {
        match byte {
            1 => Some(Self::Text),
            2 => Some(Self::Numbers),
            _ => None,
        }
    }
}
pub const MAX_FILE_BYTES: u32 = 4096;
pub const MAX_ROWS: u32 = 256;
pub const OK: u8 = 0;
pub const BAD_PATH: u8 = 1;
pub const NOT_FOUND: u8 = 2;
pub const INVALID_DATA: u8 = 3;
pub const LIMIT: u8 = 4;
pub const UNAVAILABLE: u8 = 5;
