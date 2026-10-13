//! Diagnostic-only pacing and stale-reply assertions for a waiting requester.
#![forbid(unsafe_code)]
use crate::console_ipc::{Error, rpc::Calls};

#[inline(always)]
pub fn begin<C: Calls>(endpoint: u64, calls: &mut C) -> Result<Option<u64>, Error> {
    let mut frame = super::Frame::empty(super::READ, 1, 0);
    frame.len = 12;
    frame.data[..12].copy_from_slice(b"/version.txt");
    let mut wire = frame.encode();
    match calls.invoke(10, endpoint, &mut wire) {
        (0, token) if token >> 32 != 0 && token & 0xffff0000 == 3 << 16 && token & 0xffff != 0 => {
            Ok(Some(token))
        }
        (6, 0) => Ok(None),
        _ => Err(Error::Transport),
    }
}

// The real kernel dispatch budget is 64 calls. This diagnostic forces a return
// between receive and reply without changing the production scheduler or ABI.
#[inline(always)]
pub fn pace<C: crate::supervisor::Calls>(calls: &mut C) -> Result<(), Error> {
    for _ in 0..64 {
        if calls.invoke(0, 0, 0) != (0, 1) {
            return Err(Error::Transport);
        }
    }
    Ok(())
}

pub struct CheckedReplies<C> {
    inner: C,
    expect_denied: bool,
    failed: bool,
}
impl<C: Calls> CheckedReplies<C> {
    #[inline(always)]
    pub const fn new(inner: C) -> Self {
        Self {
            inner,
            expect_denied: false,
            failed: false,
        }
    }
}
impl<C: Calls> Calls for CheckedReplies<C> {
    #[inline(always)]
    fn invoke(&mut self, number: u64, handle: u64, wire: &mut [u8]) -> (u64, u64) {
        if self.failed {
            return (255, 0);
        }
        let result = self.inner.invoke(number, handle, wire);
        if number == 7 && result.0 == 0 && (32..=96).contains(&result.1) && wire.len() >= 32 {
            let peer = u64::from_le_bytes(wire[..8].try_into().unwrap());
            let reply = u64::from_le_bytes(wire[16..24].try_into().unwrap());
            self.expect_denied = peer == 4 && reply != 0;
        } else if number == 8 && self.expect_denied {
            if result != (5, 0) {
                self.failed = true;
                return (255, 0);
            }
            self.expect_denied = false;
        }
        result
    }
}

#[cfg(test)]
mod tests;
