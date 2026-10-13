//! Existing PSABI1 request/reply operations carry PFILE1, with kernel peer identity.
use super::{BYTES, Frame};
use crate::console_ipc::{Error, rpc::Calls};
const ENVELOPE: usize = 32 + BYTES;
#[inline(always)]
fn token(value: u64, tag: u64) -> bool {
    value >> 32 != 0 && value & 0xffff0000 == tag << 16 && value & 0xffff != 0
}
#[inline(always)]
fn envelope(wire: &[u8]) -> Result<(u64, u64), Error> {
    if !(32..=ENVELOPE).contains(&wire.len()) {
        return Err(Error::Wire);
    }
    let slot = u64::from_le_bytes(wire[..8].try_into().map_err(|_| Error::Wire)?);
    let generation = u64::from_le_bytes(wire[8..16].try_into().map_err(|_| Error::Wire)?);
    let reply = u64::from_le_bytes(wire[16..24].try_into().map_err(|_| Error::Wire)?);
    let bytes = u64::from_le_bytes(wire[24..32].try_into().map_err(|_| Error::Wire)?);
    if slot > u16::MAX as u64
        || generation == 0
        || generation > u32::MAX as u64
        || bytes != (wire.len() - 32) as u64
    {
        return Err(Error::Peer);
    }
    Ok(((generation << 32) | slot, reply))
}
pub struct Client<C> {
    endpoint: u64,
    peer: u64,
    pending: u64,
    expected: (u8, u64, u32),
    calls: C,
}
impl<C: Calls> Client<C> {
    #[inline(always)]
    pub const fn new(endpoint: u64, peer: u64, calls: C) -> Self {
        Self {
            endpoint,
            peer,
            pending: 0,
            expected: (0, 0, 0),
            calls,
        }
    }
    pub fn start(&mut self, request: &Frame) -> Result<bool, Error> {
        if self.pending != 0 {
            return Err(Error::Sequence);
        }
        let mut wire = request.encode();
        match self.calls.invoke(10, self.endpoint, &mut wire) {
            (0, value) if token(value, 3) => {
                self.pending = value;
                self.expected = (request.op, request.sequence, request.offset);
                Ok(true)
            }
            (6, 0) => Ok(false),
            (5 | 9, 0) => Err(Error::Revoked),
            _ => Err(Error::Transport),
        }
    }
    pub fn finish(&mut self) -> Result<Option<Frame>, Error> {
        if self.pending == 0 {
            return Err(Error::Sequence);
        }
        let mut wire = [0; ENVELOPE];
        match self.calls.invoke(11, self.pending, &mut wire) {
            (0, value) if value == ENVELOPE as u64 => {
                self.pending = 0;
                if envelope(&wire)? != (self.peer, 0) {
                    return Err(Error::Peer);
                }
                let reply = Frame::decode(&wire[32..]).ok_or(Error::Wire)?;
                if (reply.op, reply.sequence, reply.offset) != self.expected {
                    return Err(Error::Sequence);
                }
                Ok(Some(reply))
            }
            (6, 0) => Ok(None),
            (9, 0) => {
                self.pending = 0;
                Err(Error::Revoked)
            }
            _ => Err(Error::Transport),
        }
    }
}
pub struct Server<C> {
    endpoint: u64,
    peers: [u64; 2],
    reply: u64,
    output: Frame,
    calls: C,
}
impl<C: Calls> Server<C> {
    #[inline(always)]
    pub const fn new(endpoint: u64, peers: [u64; 2], calls: C) -> Self {
        Self {
            endpoint,
            peers,
            reply: 0,
            output: Frame::empty(super::READ, 1, 0),
            calls,
        }
    }
    /// One syscall per step. A vanished requester cannot kill unrelated clients.
    pub fn poll(&mut self) -> Result<(), Error> {
        if self.reply != 0 {
            let mut wire = self.output.encode();
            match self.calls.invoke(8, self.reply, &mut wire) {
                (0, value) if value == BYTES as u64 => {
                    self.reply = 0;
                    Ok(())
                }
                (5, 0) => {
                    self.reply = 0;
                    Ok(())
                }
                (6, 0) => Ok(()),
                _ => Err(Error::Transport),
            }
        } else {
            let mut wire = [0; ENVELOPE];
            match self.calls.invoke(7, self.endpoint, &mut wire) {
                (0, value) if (32..=ENVELOPE as u64).contains(&value) => {
                    let wire = wire.get(..value as usize).ok_or(Error::Wire)?;
                    let (peer, reply) = envelope(wire)?;
                    // SEND authority also permits untracked messages. They have
                    // already been dequeued and grant no reply authority.
                    if reply == 0 {
                        return Ok(());
                    }
                    if !token(reply, 2) {
                        return Err(Error::Peer);
                    }
                    self.output = if self.peers.contains(&peer) {
                        super::answer(wire.get(32..).ok_or(Error::Wire)?)
                    } else {
                        super::answer(&[])
                    };
                    self.reply = reply;
                    Ok(())
                }
                (6, 0) => Ok(()),
                _ => Err(Error::Transport),
            }
        }
    }
}
#[cfg(test)]
mod tests;
