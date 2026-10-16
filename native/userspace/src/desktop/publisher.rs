//! Bounded snapshot publishing, independent of application job acknowledgements.
#![forbid(unsafe_code)]
use super::{
    surface_rpc::Client,
    surfaces::{CLEAR, Frame, OPEN, WRITE},
};
use crate::{
    apps::{Kind, wire},
    console_ipc::{Error, rpc::Calls},
};

#[derive(Clone, Copy)]
struct Snapshot {
    sequence: u64,
    status: u8,
    values: [i64; 4],
}
pub struct Publisher {
    client: Client,
    kind: Kind,
    latest: Snapshot,
    active: Snapshot,
    phase: u8,
}
impl Publisher {
    #[inline(always)]
    pub const fn new(endpoint: u64, kind: Kind) -> Self {
        let empty = Snapshot {
            sequence: 0,
            status: 0,
            values: [0; 4],
        };
        Self {
            client: Client::new(endpoint),
            kind,
            latest: empty,
            active: empty,
            phase: 0,
        }
    }
    #[inline(always)]
    pub fn pending(&self) -> bool {
        self.client.pending()
    }
    #[inline(always)]
    pub fn observe(&mut self, result: wire::Frame) {
        if result.kind == self.kind && result.sequence > self.latest.sequence {
            self.latest = Snapshot {
                sequence: result.sequence,
                status: result.status,
                values: result.values().unwrap_or([0; 4]),
            };
        }
    }
    #[inline(always)]
    fn request(&self) -> Frame {
        let mut f = Frame::new(
            if self.phase == 0 {
                OPEN
            } else if self.phase == 2 {
                CLEAR
            } else {
                WRITE
            },
            1,
            0,
        );
        if self.phase == 1 || self.phase == 3 {
            let text: &[u8] = if self.phase == 1 {
                b"Ready"
            } else if self.active.status == 0 {
                b"Result snapshot"
            } else {
                b"Job failed"
            };
            f.len = text.len() as u8;
            for (a, b) in f.data.iter_mut().zip(text) {
                *a = core::hint::black_box(*b);
            }
        } else if (4..8).contains(&self.phase) {
            let index = usize::from(self.phase - 4);
            f.offset = 24 * (index as u16 + 2);
            f.len = 24;
            for b in f.data.iter_mut().take(24) {
                *b = core::hint::black_box(b' ');
            }
            if !(self.kind == Kind::Text && index == 3) && self.active.status == 0 {
                // Flat bytes avoid an address-bearing compiler switch table in PUSERBIN1.
                let labels = if self.kind == Kind::Text {
                    b"Bytes Words Lines       "
                } else {
                    b"Rows  Sum   Min   Max   "
                };
                for (a, b) in f.data.iter_mut().zip(labels.iter().skip(index * 6).take(6)) {
                    *a = core::hint::black_box(*b);
                }
                let value = self.active.values.get(index).copied().unwrap_or(0);
                let mut n = value.unsigned_abs();
                let mut first = true;
                for digit in f.data.iter_mut().take(24).skip(6).rev() {
                    if first || n != 0 {
                        *digit = b'0' + (n % 10) as u8;
                        n /= 10;
                        first = false;
                    } else {
                        if value < 0 {
                            *digit = b'-';
                        }
                        break;
                    }
                }
            }
        }
        f
    }
    /// One bounded RPC step. Call only outside application file-read/wait states.
    #[inline(always)]
    pub fn poll(&mut self, calls: &mut impl Calls) -> Result<(), Error> {
        if self.phase == 9 {
            return Ok(());
        }
        if self.phase == 8 {
            if self.latest.sequence == self.active.sequence {
                return Ok(());
            }
            self.active = self.latest;
            self.phase = 2;
        }
        match self.client.step(calls, self.request()) {
            Ok(true) => {
                self.phase = if self.phase == 1 {
                    8
                } else {
                    self.phase.saturating_add(1)
                }
            }
            Ok(false) => {}
            Err(e) => {
                self.phase = 9;
                return Err(e);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;
    struct Fake {
        sent: Vec<Frame>,
        stall: bool,
    }
    impl Calls for Fake {
        fn invoke(&mut self, n: u64, _: u64, w: &mut [u8]) -> (u64, u64) {
            match n {
                10 => {
                    self.sent.push(Frame::decode(w).unwrap());
                    (0, 0x100030001)
                }
                11 if self.stall => (6, 0),
                11 => {
                    let r = self.sent.last().unwrap();
                    w.fill(0);
                    w[..8].copy_from_slice(&2u64.to_le_bytes());
                    w[8..16].copy_from_slice(&1u64.to_le_bytes());
                    w[24..32].copy_from_slice(&64u64.to_le_bytes());
                    let f = Frame::new(r.op, r.sequence, 1);
                    f.encode_into((&mut w[32..]).try_into().unwrap());
                    (0, 96)
                }
                _ => panic!(),
            }
        }
    }
    #[test]
    fn pending_publish_is_bounded_and_does_not_mix_new_snapshots() {
        let mut p = Publisher::new(1, Kind::Numbers);
        let mut f = Fake {
            sent: Vec::new(),
            stall: false,
        };
        p.poll(&mut f).unwrap();
        p.poll(&mut f).unwrap();
        p.observe(wire::Frame::result(Kind::Numbers, 2, Ok([4, -22, -9, 8])));
        f.stall = true;
        p.poll(&mut f).unwrap();
        assert!(p.pending());
        p.observe(wire::Frame::result(Kind::Numbers, 3, Ok([5, 30, 1, 10])));
        for _ in 0..20 {
            p.poll(&mut f).unwrap();
        }
        assert_eq!(f.sent.len(), 3);
        f.stall = false;
        for _ in 0..6 {
            p.poll(&mut f).unwrap();
        }
        assert_eq!(p.phase, 8);
        assert_eq!(p.active.sequence, 2);
        assert_eq!(&f.sent[5].data[..3], b"Sum");
        assert_eq!(&f.sent[5].data[21..24], b"-22");
        p.poll(&mut f).unwrap();
        assert_eq!(p.active.sequence, 3);
    }
    #[test]
    fn text_rows_and_error_snapshots_are_labelled_without_stale_values() {
        let mut p = Publisher::new(1, Kind::Text);
        p.active = Snapshot {
            sequence: 2,
            status: 0,
            values: [150, 27, 9, 0],
        };
        p.phase = 4;
        assert_eq!(&p.request().data[..5], b"Bytes");
        p.phase = 7;
        assert_eq!(&p.request().data[..24], &[b' '; 24]);
        p.active.status = 1;
        p.phase = 3;
        assert_eq!(&p.request().data[..10], b"Job failed");
        p.phase = 4;
        assert_eq!(&p.request().data[..24], &[b' '; 24]);
    }
}
