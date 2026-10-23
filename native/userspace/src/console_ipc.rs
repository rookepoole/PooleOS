//! PCS1: bounded single-client console policy; sender identity comes from PSABI1.
#![forbid(unsafe_code)]
use crate::console::{self, Registers};

pub const BYTES: usize = 32;
pub const ENVELOPE_BYTES: usize = 64;
pub const PAYLOAD: usize = 16;
pub mod control;
pub mod rpc;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Transport,
    Revoked,
    Wire,
    Peer,
    Sequence,
    Device(console::Error),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Kind {
    Read = 1,
    Write = 2,
    Close = 3,
    Input = 4,
    Written = 5,
    Closed = 6,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Message {
    kind: Kind,
    sequence: u64,
    len: u8,
    data: [u8; PAYLOAD],
}
impl Message {
    #[inline]
    pub fn kind(&self) -> Kind {
        self.kind
    }
    #[inline]
    pub fn sequence(&self) -> u64 {
        self.sequence
    }
    #[inline]
    pub fn payload(&self) -> &[u8] {
        &self.data[..usize::from(self.len).min(PAYLOAD)]
    }
    #[inline]
    pub fn new(kind: Kind, sequence: u64, data: &[u8]) -> Result<Self, Error> {
        if sequence == 0 || sequence == u64::MAX {
            return Err(Error::Sequence);
        }
        let valid = match kind {
            Kind::Write => (1..=PAYLOAD).contains(&data.len()),
            Kind::Input => data.len() == 1,
            _ => data.is_empty(),
        };
        if !valid {
            return Err(Error::Wire);
        }
        let message = Self {
            kind,
            sequence,
            len: data.len() as u8,
            data: core::array::from_fn(|i| data.get(i).copied().unwrap_or(0)),
        };
        Ok(message)
    }
    #[inline]
    pub fn encode(self) -> [u8; BYTES] {
        let mut wire = [0; BYTES];
        wire[..4].copy_from_slice(b"PCS1");
        wire[4] = self.kind as u8;
        wire[5] = self.len;
        wire[8..16].copy_from_slice(&self.sequence.to_le_bytes());
        wire[16..].copy_from_slice(&self.data);
        wire
    }
    #[inline]
    pub fn decode(wire: &[u8]) -> Result<Self, Error> {
        if wire.len() != BYTES
            || &wire[..4] != b"PCS1"
            || wire[6..8] != [0, 0]
            || usize::from(wire[5]) > PAYLOAD
        {
            return Err(Error::Wire);
        }
        let kind = match wire[4] {
            1 => Kind::Read,
            2 => Kind::Write,
            3 => Kind::Close,
            4 => Kind::Input,
            5 => Kind::Written,
            6 => Kind::Closed,
            _ => return Err(Error::Wire),
        };
        let len = usize::from(wire[5]);
        let end = 16usize.checked_add(len).ok_or(Error::Wire)?;
        if wire.get(end..).ok_or(Error::Wire)?.iter().any(|&v| v != 0) {
            return Err(Error::Wire);
        }
        let sequence = u64::from_le_bytes(wire[8..16].try_into().map_err(|_| Error::Wire)?);
        Self::new(kind, sequence, wire.get(16..end).ok_or(Error::Wire)?)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Peer {
    slot: u64,
    generation: u64,
}
impl Peer {
    #[inline]
    pub fn from_packed(value: u64) -> Result<Self, Error> {
        let peer = Self {
            slot: value & 0xffff_ffff,
            generation: value >> 32,
        };
        if peer.slot > u64::from(u16::MAX) || peer.generation == 0 {
            return Err(Error::Peer);
        }
        Ok(peer)
    }
    /// Only a successful kernel receive7 may supply this envelope.
    #[inline]
    pub fn decode(self, wire: &[u8]) -> Result<Message, Error> {
        Message::decode(self.payload(wire)?)
    }
    /// Authenticate the kernel envelope before selecting an explicit wire codec.
    #[inline]
    pub(crate) fn payload(self, wire: &[u8]) -> Result<&[u8], Error> {
        if wire.len() != ENVELOPE_BYTES {
            return Err(Error::Wire);
        }
        for (word, expected) in
            wire[..32]
                .chunks_exact(8)
                .zip([self.slot, self.generation, 0, BYTES as u64])
        {
            if u64::from_le_bytes(word.try_into().map_err(|_| Error::Wire)?) != expected {
                return Err(Error::Peer);
            }
        }
        Ok(&wire[32..])
    }
}

pub trait Channel {
    /// None/false is backpressure, not failure. Received messages must be peer-authenticated.
    fn receive(&mut self) -> Result<Option<Message>, Error>;
    fn send(&mut self, message: Message) -> Result<bool, Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Phase {
    Idle,
    Read,
    Write { message: Message, cursor: usize },
    Drain,
    Reply { message: Message, closing: bool },
    Closed,
}
pub struct Server {
    sequence: u64,
    phase: Phase,
}
impl Server {
    pub const fn new() -> Self {
        Self {
            sequence: 1,
            phase: Phase::Idle,
        }
    }
    /// Each step performs at most one transport operation or one bounded UART poll.
    #[inline]
    pub fn poll(
        &mut self,
        port: &mut impl Registers,
        channel: &mut impl Channel,
    ) -> Result<bool, Error> {
        let next = match self.phase {
            Phase::Idle => {
                let Some(message) = channel.receive()? else {
                    return Ok(false);
                };
                if message.sequence != self.sequence {
                    return Err(Error::Sequence);
                }
                match message.kind {
                    Kind::Read => Phase::Read,
                    Kind::Write => Phase::Write { message, cursor: 0 },
                    Kind::Close => Phase::Drain,
                    _ => return Err(Error::Wire),
                }
            }
            Phase::Read => {
                if console::status(port).map_err(Error::Device)? & 1 == 0 {
                    return Ok(false);
                }
                let byte = port.read(0).map_err(Error::Device)?;
                Phase::Reply {
                    message: Message::new(Kind::Input, self.sequence, &[byte])?,
                    closing: false,
                }
            }
            Phase::Write { message, cursor } => {
                let byte = *message.data.get(cursor).ok_or(Error::Wire)?;
                if !console::send(port, byte).map_err(Error::Device)? {
                    return Ok(false);
                }
                let next_cursor = cursor.checked_add(1).ok_or(Error::Wire)?;
                if next_cursor == usize::from(message.len) {
                    Phase::Reply {
                        message: Message::new(Kind::Written, self.sequence, &[])?,
                        closing: false,
                    }
                } else {
                    Phase::Write {
                        message,
                        cursor: next_cursor,
                    }
                }
            }
            Phase::Drain => {
                if console::status(port).map_err(Error::Device)? & 0x40 == 0 {
                    return Ok(false);
                }
                Phase::Reply {
                    message: Message::new(Kind::Closed, self.sequence, &[])?,
                    closing: true,
                }
            }
            Phase::Reply { message, closing } => {
                if !channel.send(message)? {
                    return Ok(false);
                }
                self.sequence = self.sequence.checked_add(1).ok_or(Error::Sequence)?;
                if closing { Phase::Closed } else { Phase::Idle }
            }
            Phase::Closed => return Ok(true),
        };
        self.phase = next;
        Ok(self.phase == Phase::Closed)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ClientPhase {
    Send(Message),
    Receive(Kind),
    Closed,
}
/// A separate user-space echo client for admission qualification, not a shell.
pub struct Client {
    sequence: u64,
    phase: ClientPhase,
}
impl Client {
    #[inline]
    pub fn new() -> Self {
        Self {
            sequence: 1,
            phase: ClientPhase::Send(Message {
                kind: Kind::Read,
                sequence: 1,
                len: 0,
                data: [0; PAYLOAD],
            }),
        }
    }
    #[inline]
    pub fn poll(&mut self, channel: &mut impl Channel) -> Result<bool, Error> {
        let next = match self.phase {
            ClientPhase::Send(message) => {
                if !channel.send(message)? {
                    return Ok(false);
                }
                ClientPhase::Receive(match message.kind {
                    Kind::Read => Kind::Input,
                    Kind::Write => Kind::Written,
                    Kind::Close => Kind::Closed,
                    _ => return Err(Error::Wire),
                })
            }
            ClientPhase::Receive(kind) => {
                let Some(message) = channel.receive()? else {
                    return Ok(false);
                };
                if message.sequence != self.sequence || message.kind != kind {
                    return Err(Error::Sequence);
                }
                if kind == Kind::Closed {
                    ClientPhase::Closed
                } else {
                    let sequence = self.sequence.checked_add(1).ok_or(Error::Sequence)?;
                    let request = match kind {
                        Kind::Input if message.data[0] == 4 => {
                            Message::new(Kind::Close, sequence, &[])?
                        }
                        Kind::Input => Message::new(Kind::Write, sequence, &message.data[..1])?,
                        Kind::Written => Message::new(Kind::Read, sequence, &[])?,
                        _ => return Err(Error::Wire),
                    };
                    self.sequence = sequence;
                    ClientPhase::Send(request)
                }
            }
            ClientPhase::Closed => return Ok(true),
        };
        self.phase = next;
        Ok(self.phase == ClientPhase::Closed)
    }
}

#[cfg(test)]
mod tests;
