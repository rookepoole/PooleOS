//! PAPP1 fixed, canonical 64-byte application job/result messages.
use super::{Kind, OK, UNAVAILABLE};
pub const BYTES: usize = 64;
pub const READY: u8 = 1;
pub const RUN: u8 = 2;
pub const RESULT: u8 = 3;
pub const ACK: u8 = 4;
pub const FAULT: u8 = 5;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Frame {
    pub phase: u8,
    pub kind: Kind,
    pub status: u8,
    pub sequence: u64,
    pub len: u8,
    pub data: [u8; 40],
}
impl Frame {
    #[inline(always)]
    pub const fn empty(phase: u8, kind: Kind, sequence: u64) -> Self {
        Self {
            phase,
            kind,
            status: OK,
            sequence,
            len: 0,
            data: [0; 40],
        }
    }
    #[inline(always)]
    pub fn encode(&self) -> [u8; BYTES] {
        let mut wire = [0; BYTES];
        wire[..4].copy_from_slice(b"PAP1");
        wire[4] = self.phase;
        wire[5] = self.kind as u8;
        wire[6] = self.status;
        wire[7] = self.len;
        wire[8..16].copy_from_slice(&self.sequence.to_le_bytes());
        wire[24..].copy_from_slice(&self.data);
        wire
    }
    #[inline(always)]
    pub fn decode(wire: &[u8]) -> Option<Self> {
        if wire.len() != BYTES
            || &wire[..4] != b"PAP1"
            || !(READY..=FAULT).contains(&wire[4])
            || wire[6] > UNAVAILABLE
            || wire[7] > 40
            || wire[16..24].iter().any(|&b| b != 0)
            || wire[24 + usize::from(wire[7])..].iter().any(|&b| b != 0)
        {
            return None;
        }
        let sequence = u64::from_le_bytes(wire[8..16].try_into().ok()?);
        if sequence == 0 || sequence == u64::MAX {
            return None;
        }
        let phase = wire[4];
        let valid = if phase == RESULT {
            (wire[6] == OK && wire[7] == 32) || (wire[6] != OK && wire[7] == 0)
        } else {
            wire[6] == OK && (phase == RUN || wire[7] == 0)
        };
        if !valid {
            return None;
        }
        let mut frame = Self::empty(phase, Kind::decode(wire[5])?, sequence);
        frame.status = wire[6];
        frame.len = wire[7];
        frame.data.copy_from_slice(&wire[24..]);
        Some(frame)
    }
    #[inline(always)]
    pub fn result(kind: Kind, sequence: u64, values: Result<[i64; 4], u8>) -> Self {
        let mut frame = Self::empty(RESULT, kind, sequence);
        match values {
            Ok(values) => {
                frame.len = 32;
                for (slot, value) in frame.data.chunks_exact_mut(8).zip(values) {
                    slot.copy_from_slice(&value.to_le_bytes());
                }
            }
            Err(status) => frame.status = status,
        }
        frame
    }
    #[inline(always)]
    pub fn values(&self) -> Option<[i64; 4]> {
        if self.phase != RESULT || self.status != OK || self.len != 32 {
            return None;
        }
        Some([
            i64::from_le_bytes(self.data[0..8].try_into().ok()?),
            i64::from_le_bytes(self.data[8..16].try_into().ok()?),
            i64::from_le_bytes(self.data[16..24].try_into().ok()?),
            i64::from_le_bytes(self.data[24..32].try_into().ok()?),
        ])
    }
}
#[cfg(test)]
mod tests;
