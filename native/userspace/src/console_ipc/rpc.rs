//! PRPC1: caller-owned completions and one-use reply authority over PCS1 payloads.
use super::{BYTES, ENVELOPE_BYTES, Error, Message, Peer};

pub trait Calls {
    /// Kernel copies synchronously; the adapter must keep this buffer live.
    fn invoke(&mut self, number: u64, handle: u64, wire: &mut [u8]) -> (u64, u64);
}

#[inline]
fn token(value: u64, tag: u64) -> bool {
    value >> 32 != 0 && value & 0xffff_0000 == tag << 16 && value & 0xffff != 0
}

pub struct Transport {
    endpoint: u64,
    peer: Peer,
    server: bool,
    pending: u64,
}
impl Transport {
    #[inline]
    pub fn new(endpoint: u64, peer: Peer, server: bool) -> Self {
        Self {
            endpoint,
            peer,
            server,
            pending: 0,
        }
    }
    #[inline(always)]
    pub fn send(&mut self, message: Message, calls: &mut impl Calls) -> Result<bool, Error> {
        if self.server == (self.pending == 0) {
            return Err(Error::Transport);
        }
        let mut wire = message.encode();
        let (number, handle) = if self.server {
            (8, self.pending)
        } else {
            (10, self.endpoint)
        };
        match calls.invoke(number, handle, &mut wire) {
            (0, value) if self.server && value == BYTES as u64 => {
                self.pending = 0;
                Ok(true)
            }
            (0, value) if !self.server && token(value, 3) => {
                self.pending = value;
                Ok(true)
            }
            (6, 0) => Ok(false),
            _ => Err(Error::Transport),
        }
    }
    #[inline(always)]
    pub fn receive(&mut self, calls: &mut impl Calls) -> Result<Option<Message>, Error> {
        if self.server != (self.pending == 0) {
            return Err(Error::Transport);
        }
        let mut wire = [0; ENVELOPE_BYTES];
        let (number, handle) = if self.server {
            (7, self.endpoint)
        } else {
            (11, self.pending)
        };
        match calls.invoke(number, handle, &mut wire) {
            (0, n) if n == ENVELOPE_BYTES as u64 => {
                if self.server {
                    let reply =
                        u64::from_le_bytes(wire[16..24].try_into().map_err(|_| Error::Wire)?);
                    if !token(reply, 2) {
                        return Err(Error::Peer);
                    }
                    // Authenticate the remaining kernel envelope using the unchanged PCS1 decoder.
                    wire[16..24].fill(0);
                    let message = self.peer.decode(&wire)?;
                    self.pending = reply;
                    Ok(Some(message))
                } else {
                    self.pending = 0;
                    self.peer.decode(&wire).map(Some)
                }
            }
            (6, 0) => Ok(None),
            (9, 0) if !self.server => {
                self.pending = 0;
                Err(Error::Revoked)
            }
            _ => Err(Error::Transport),
        }
    }
}

#[cfg(test)]
mod tests;
