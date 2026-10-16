//! Initial user-space service control protocol. No kernel authority is encoded.
#![forbid(unsafe_code)]

pub const BYTES: usize = 32;
const MAGIC: &[u8; 8] = b"PSVC1\0\0\0";
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u64)]
pub enum Kind {
    Start = 1,
    Ready = 2,
    Advance = 3,
    Value = 4,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Message {
    pub kind: Kind,
    pub sequence: u64,
    pub value: u64,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Wire,
    State,
    Sequence,
    Value,
    Exhausted,
}

impl Message {
    #[inline]
    pub fn encode(self) -> [u8; BYTES] {
        let mut bytes = [0; BYTES];
        bytes[..8].copy_from_slice(MAGIC);
        bytes[8..16].copy_from_slice(&(self.kind as u64).to_le_bytes());
        bytes[16..24].copy_from_slice(&self.sequence.to_le_bytes());
        bytes[24..].copy_from_slice(&self.value.to_le_bytes());
        bytes
    }
    #[inline]
    pub fn decode(bytes: &[u8]) -> Result<Self, Error> {
        if bytes.len() != BYTES || bytes[..8] != *MAGIC {
            return Err(Error::Wire);
        }
        let word = |at| u64::from_le_bytes(bytes[at..at + 8].try_into().unwrap());
        let kind = match word(8) {
            1 => Kind::Start,
            2 => Kind::Ready,
            3 => Kind::Advance,
            4 => Kind::Value,
            _ => return Err(Error::Wire),
        };
        Ok(Self {
            kind,
            sequence: word(16),
            value: word(24),
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Init {
    sequence: u64,
    ready: bool,
}
impl Init {
    #[inline]
    pub const fn new() -> Self {
        Self {
            sequence: 0,
            ready: false,
        }
    }
    #[inline]
    pub fn request(&self) -> Result<Message, Error> {
        if !self.ready {
            return Ok(Message {
                kind: Kind::Start,
                sequence: 0,
                value: 0,
            });
        }
        Ok(Message {
            kind: Kind::Advance,
            sequence: self.sequence.checked_add(1).ok_or(Error::Exhausted)?,
            value: 1,
        })
    }
    #[inline]
    pub fn accept(&mut self, reply: Message) -> Result<(), Error> {
        let request = self.request()?;
        if reply.kind != if self.ready { Kind::Value } else { Kind::Ready } {
            return Err(Error::State);
        }
        if reply.sequence != request.sequence {
            return Err(Error::Sequence);
        }
        if reply.value != request.sequence {
            return Err(Error::Value);
        }
        self.sequence = reply.sequence;
        self.ready = true;
        Ok(())
    }
    pub fn completed(&self) -> u64 {
        self.sequence
    }
}
impl Default for Init {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Counter {
    sequence: u64,
    started: bool,
}
impl Counter {
    #[inline]
    pub const fn new() -> Self {
        Self {
            sequence: 0,
            started: false,
        }
    }
    /// Return an uncommitted successor: sending failure leaves the caller's state intact.
    #[inline]
    pub fn prepare(&self, request: Message) -> Result<(Self, Message), Error> {
        if !self.started {
            if request
                != (Message {
                    kind: Kind::Start,
                    sequence: 0,
                    value: 0,
                })
            {
                return Err(Error::State);
            }
            return Ok((
                Self {
                    sequence: 0,
                    started: true,
                },
                Message {
                    kind: Kind::Ready,
                    sequence: 0,
                    value: 0,
                },
            ));
        }
        if request.kind != Kind::Advance {
            return Err(Error::State);
        }
        let next = self.sequence.checked_add(1).ok_or(Error::Exhausted)?;
        if request.sequence != next {
            return Err(Error::Sequence);
        }
        if request.value != 1 {
            return Err(Error::Value);
        }
        Ok((
            Self {
                sequence: next,
                started: true,
            },
            Message {
                kind: Kind::Value,
                sequence: next,
                value: next,
            },
        ))
    }
}
impl Default for Counter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wire_is_exact_and_rejects_noncanonical_inputs() {
        for kind in [Kind::Start, Kind::Ready, Kind::Advance, Kind::Value] {
            let m = Message {
                kind,
                sequence: u64::MAX,
                value: 17,
            };
            assert_eq!(Message::decode(&m.encode()), Ok(m));
        }
        let wire = Message {
            kind: Kind::Start,
            sequence: 0,
            value: 0,
        }
        .encode();
        for size in 0..BYTES {
            assert!(Message::decode(&wire[..size]).is_err());
        }
        assert!(Message::decode(&[0; BYTES + 1]).is_err());
        for at in 0..16 {
            let mut b = wire;
            b[at] = 255;
            assert!(Message::decode(&b).is_err());
        }
    }
    #[test]
    fn init_controls_startup_and_monotonic_service_progress() {
        let mut init = Init::new();
        let mut counter = Counter::new();
        for expected in 0..1000 {
            let (next, reply) = counter.prepare(init.request().unwrap()).unwrap();
            counter = next;
            init.accept(reply).unwrap();
            assert_eq!(init.completed(), expected);
        }
    }
    #[test]
    fn failed_send_cannot_commit_counter_transition() {
        let counter = Counter::new();
        let request = Init::new().request().unwrap();
        let first = counter.prepare(request).unwrap();
        assert_eq!(counter, Counter::new());
        assert_eq!(counter.prepare(request).unwrap(), first);
        assert!(first.0.prepare(request).is_err());
    }
    #[test]
    fn init_rejects_bad_replies_without_changing_state() {
        for ready in [false, true] {
            let init = Init { sequence: 7, ready };
            let good = if ready {
                Message {
                    kind: Kind::Value,
                    sequence: 8,
                    value: 8,
                }
            } else {
                Message {
                    kind: Kind::Ready,
                    sequence: 0,
                    value: 0,
                }
            };
            for bad in [
                Message {
                    kind: Kind::Start,
                    ..good
                },
                Message {
                    sequence: u64::MAX,
                    ..good
                },
                Message {
                    value: u64::MAX,
                    ..good
                },
            ] {
                let mut candidate = init;
                assert!(candidate.accept(bad).is_err());
                assert_eq!(candidate, init);
            }
        }
    }
    #[test]
    fn counter_rejects_replay_skips_and_bad_operation() {
        let counter = Counter {
            sequence: 7,
            started: true,
        };
        for request in [
            Message {
                kind: Kind::Start,
                sequence: 8,
                value: 1,
            },
            Message {
                kind: Kind::Advance,
                sequence: 7,
                value: 1,
            },
            Message {
                kind: Kind::Advance,
                sequence: 9,
                value: 1,
            },
            Message {
                kind: Kind::Advance,
                sequence: 8,
                value: 2,
            },
        ] {
            assert!(counter.prepare(request).is_err());
        }
    }
    #[test]
    fn sequence_exhaustion_never_wraps_to_start() {
        let mut init = Init {
            sequence: u64::MAX,
            ready: true,
        };
        assert_eq!(init.request(), Err(Error::Exhausted));
        assert_eq!(
            init.accept(Message {
                kind: Kind::Value,
                sequence: 0,
                value: 0
            }),
            Err(Error::Exhausted)
        );
        assert_eq!(
            Counter {
                sequence: u64::MAX,
                started: true
            }
            .prepare(Message {
                kind: Kind::Advance,
                sequence: 0,
                value: 1
            }),
            Err(Error::Exhausted)
        );
    }
}
