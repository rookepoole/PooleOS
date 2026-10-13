//! Development-only native client controls; not a useful application or file policy.
#![forbid(unsafe_code)]
use super::{Frame, INVALID, OK, RANGE, READ, VERSION};
use crate::console_ipc::{Error, rpc::Calls};

pub const CASES: u8 = 13;
pub const EXIT_COMPLETE: u32 = 85;
const MAX_POLLS: u32 = 16384;

#[inline(always)]
fn valid() -> Frame {
    let mut f = Frame::empty(READ, 1, 0);
    f.len = 12;
    f.data[..12].copy_from_slice(b"/version.txt");
    f
}

#[inline(always)]
fn malformed(case: u8, wire: &mut [u8; 64]) -> Result<usize, Error> {
    match case {
        0 => return Ok(1),
        1 => return Ok(63),
        2 => wire[0] = b'X',
        3 => wire[4] = 255,
        4 => wire[7] = 1,
        5 => wire[8..16].fill(0),
        6 => wire[8..16].fill(255),
        7 => wire[63] = 1,
        8 => wire[5] = 1,
        9 => wire[20] = 1,
        10 => wire[6] = 41,
        11 => {
            wire[24..].fill(0);
            wire[24..29].copy_from_slice(b"/../x");
            wire[6] = 5;
        }
        12 => wire[16..20].fill(255),
        _ => return Err(Error::Wire),
    }
    Ok(64)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Progress {
    Pending,
    AbandonOutstandingRequest,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Plain,
    BadBegin,
    BadTake,
    GoodBegin,
    GoodTake,
    Abandon,
    Finished,
    Failed,
}
pub struct Probe<C> {
    calls: C,
    endpoint: u64,
    peer: u64,
    pending: u64,
    case: u8,
    state: State,
    polls: u32,
}
impl<C: Calls> Probe<C> {
    pub const fn new(endpoint: u64, peer: u64, calls: C) -> Self {
        Self {
            calls,
            endpoint,
            peer,
            pending: 0,
            case: 0,
            state: State::Plain,
            polls: 0,
        }
    }
    fn begin(&mut self, bad: bool) -> Result<bool, Error> {
        let mut wire = valid().encode();
        let len = if bad {
            malformed(self.case, &mut wire)?
        } else {
            64
        };
        match self.calls.invoke(10, self.endpoint, &mut wire[..len]) {
            (0, token)
                if token >> 32 != 0 && token & 0xffff0000 == 3 << 16 && token & 0xffff != 0 =>
            {
                self.pending = token;
                Ok(true)
            }
            (6, 0) => Ok(false),
            _ => Err(Error::Transport),
        }
    }
    fn take(&mut self, bad: bool) -> Result<bool, Error> {
        let mut wire = [0; 96];
        match self.calls.invoke(11, self.pending, &mut wire) {
            (6, 0) => return Ok(false),
            (0, 96) => {}
            _ => return Err(Error::Transport),
        }
        let word = |at| u64::from_le_bytes(wire[at..at + 8].try_into().unwrap());
        if word(0) != self.peer & 0xffffffff
            || word(8) != self.peer >> 32
            || word(16) != 0
            || word(24) != 64
        {
            return Err(Error::Peer);
        }
        let reply = Frame::decode(&wire[32..]).ok_or(Error::Wire)?;
        let offset = if bad && self.case == 12 { u32::MAX } else { 0 };
        let status = if !bad {
            OK
        } else if self.case == 12 {
            RANGE
        } else {
            INVALID
        };
        if reply.op != READ
            || reply.sequence != 1
            || reply.offset != offset
            || reply.status != status
        {
            return Err(Error::Wire);
        }
        if bad {
            if reply.len != 0 || reply.total != 0 {
                return Err(Error::Wire);
            }
        } else if reply.total != VERSION.len() as u32
            || !super::same_bytes(reply.payload().ok_or(Error::Wire)?, VERSION)
        {
            return Err(Error::Wire);
        }
        self.pending = 0;
        Ok(true)
    }
    fn step(&mut self) -> Result<Progress, Error> {
        self.polls = self
            .polls
            .checked_add(1)
            .filter(|&n| n <= MAX_POLLS)
            .ok_or(Error::Sequence)?;
        match self.state {
            State::Plain => {
                let mut wire = valid().encode();
                let len = malformed(self.case, &mut wire)?;
                match self.calls.invoke(3, self.endpoint, &mut wire[..len]) {
                    (0, bytes) if bytes == len as u64 => self.state = State::BadBegin,
                    (6, 0) => {}
                    _ => return Err(Error::Transport),
                }
            }
            State::BadBegin => {
                if self.begin(true)? {
                    self.state = State::BadTake;
                }
            }
            State::BadTake => {
                if self.take(true)? {
                    self.state = State::GoodBegin;
                }
            }
            State::GoodBegin => {
                if self.begin(false)? {
                    self.state = State::GoodTake;
                }
            }
            State::GoodTake => {
                if self.take(false)? {
                    self.case = self
                        .case
                        .checked_add(1)
                        .filter(|&n| n <= CASES)
                        .ok_or(Error::Sequence)?;
                    self.state = if self.case == CASES {
                        State::Abandon
                    } else {
                        State::Plain
                    };
                }
            }
            State::Abandon => {
                if self.begin(false)? {
                    self.state = State::Finished;
                    return Ok(Progress::AbandonOutstandingRequest);
                }
            }
            State::Finished | State::Failed => return Err(Error::Sequence),
        }
        Ok(Progress::Pending)
    }
    pub fn poll(&mut self) -> Result<Progress, Error> {
        let result = self.step();
        if result.is_err() {
            self.state = State::Failed;
        }
        result
    }
}

#[cfg(test)]
mod tests;
