//! App-owned scratch editing and computation; no editing policy runs in the WM.
#![forbid(unsafe_code)]
use super::{Publisher, Snapshot, View};
use crate::{
    apps::{self, Kind, stats::Accumulator, wire},
    console_ipc::{Error, rpc::Calls},
    desktop::{
        application_input::{INPUT, RESET},
        surfaces::{Frame, WRITE},
    },
};

pub const DRAFT_BYTES: usize = 48;
pub struct Draft {
    bytes: [u8; DRAFT_BYTES],
    used: usize,
    blocked: bool,
    lost: u8,
}
impl Draft {
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            bytes: [0; DRAFT_BYTES],
            used: 0,
            blocked: false,
            lost: 0,
        }
    }
    #[inline(always)]
    fn clear(&mut self) {
        for b in self.bytes.iter_mut() {
            *b = core::hint::black_box(0);
        }
        self.used = 0;
    }
    #[inline(always)]
    pub fn reset(&mut self) {
        self.clear();
        self.blocked = false;
        self.lost = 2;
    }
    #[inline(always)]
    fn evaluate(&self, kind: Kind) -> Result<[i64; 4], u8> {
        let bytes = self.bytes.get(..self.used).ok_or(apps::INVALID_DATA)?;
        let mut accumulator = Accumulator::new(kind);
        if kind == Kind::Text {
            accumulator.push(bytes)?;
        } else {
            let mut row = false;
            for &byte in bytes {
                if matches!(byte, b' ' | b',') {
                    if row {
                        accumulator.push(b"\n")?;
                        row = false;
                    }
                } else {
                    accumulator.push(&[byte])?;
                    row = true;
                }
            }
        }
        accumulator.finish()
    }
    #[inline(always)]
    pub fn key(&mut self, kind: Kind, byte: u8) -> Option<Result<[i64; 4], u8>> {
        if byte == 3 {
            self.clear();
            self.blocked = false;
            self.lost = 0;
            return None;
        }
        if self.blocked {
            if byte == b'\r' {
                self.blocked = false;
                return Some(Err(apps::LIMIT));
            }
            return None;
        }
        match byte {
            b'\r' => Some(self.evaluate(kind)),
            8 => {
                self.lost = 0;
                if self.used != 0 {
                    self.used -= 1;
                    if let Some(out) = self.bytes.get_mut(self.used) {
                        *out = 0;
                    }
                }
                None
            }
            32..=126 => {
                if let Some(out) = self.bytes.get_mut(self.used) {
                    *out = byte;
                    self.used = self.used.saturating_add(1);
                    self.lost = 0;
                } else {
                    self.clear();
                    self.blocked = true;
                    self.lost = 1;
                }
                None
            }
            _ => None,
        }
    }
    #[inline(always)]
    fn row(&self, row: u8) -> Frame {
        let mut f = Frame::new(WRITE, 1, 0);
        f.offset = 24 * (6 + u16::from(row));
        f.len = 24;
        for i in 0..24 {
            f.data[i] = self
                .bytes
                .get(usize::from(row) * 24 + i)
                .copied()
                .filter(|&b| b != 0)
                .unwrap_or(b' ');
        }
        if row == 0 && self.lost != 0 {
            let label: &[u8] = if self.lost == 1 {
                b"Input limit"
            } else {
                b"Input reset"
            };
            for (out, &b) in f.data.iter_mut().zip(label) {
                *out = core::hint::black_box(b);
            }
        }
        f
    }
}

pub struct Interactive {
    base: Publisher,
    draft: Draft,
    mode: u8,
    failed: bool,
}
impl Interactive {
    #[inline(always)]
    fn result(&mut self, result: Result<[i64; 4], u8>) {
        self.base.active = Snapshot {
            sequence: self.base.latest.sequence,
            status: result.err().unwrap_or(0),
            values: result.unwrap_or([0; 4]),
        };
        self.base.phase = 2;
    }
    // One local monomorph keeps the two application-loop call sites within four pages.
    #[inline(never)]
    fn step(&mut self, calls: &mut impl Calls) -> Result<(), Error> {
        if self.mode == 0 {
            if self.base.phase != 8 || self.base.latest.sequence != self.base.active.sequence {
                self.base.poll_mode::<true>(calls)?;
                if self.base.phase == 8 {
                    self.mode = 2;
                }
                return Ok(());
            }
            self.mode = 1;
        }
        let frame = if self.mode == 1 {
            Frame::new(INPUT, 1, 0)
        } else {
            self.draft.row(self.mode - 2)
        };
        if let Some(reply) = self.base.client.step_mode::<true>(calls, frame)? {
            if self.mode == 1 {
                if reply.offset == RESET {
                    self.draft.reset();
                    self.result(Err(apps::UNAVAILABLE));
                } else {
                    for &byte in reply.data.iter().take(usize::from(reply.len)) {
                        if let Some(result) = self.draft.key(self.base.kind, byte) {
                            self.result(result);
                        }
                    }
                }
                self.mode = if self.base.phase != 8 {
                    0
                } else if reply.len != 0 {
                    2
                } else {
                    0
                };
            } else {
                self.mode = if self.mode == 2 { 3 } else { 0 };
            }
        }
        Ok(())
    }
}
impl View for Interactive {
    #[inline(always)]
    fn new(endpoint: u64, kind: Kind) -> Self {
        // Distinct scalar initializers avoid copying padded snapshot aggregates.
        Self {
            base: Publisher {
                client: super::Client::new(endpoint),
                kind,
                active: Snapshot {
                    sequence: 0,
                    status: 0,
                    values: [core::hint::black_box(0); 4],
                },
                latest: Snapshot {
                    sequence: 0,
                    status: 0,
                    values: [core::hint::black_box(0); 4],
                },
                phase: 0,
            },
            draft: Draft::new(),
            mode: 0,
            failed: false,
        }
    }
    #[inline(always)]
    fn pending(&self) -> bool {
        self.base.pending()
    }
    #[inline(always)]
    fn observe(&mut self, result: wire::Frame) {
        self.base.observe(result);
    }
    #[inline(always)]
    fn poll(&mut self, calls: &mut impl Calls) -> Result<(), Error> {
        if self.failed {
            return Err(Error::Transport);
        }
        let result = self.step(calls);
        if result.is_err() {
            self.failed = true;
        }
        result
    }
}

#[cfg(test)]
mod tests;
