//! PLC1 typed launch control. Authentication belongs to the kernel IPC adapter.
#![forbid(unsafe_code)]
use crate::{console_ipc::Error, shell::processes::ApplicationProcesses, supervisor::Calls};

pub const BYTES: usize = 32;
pub mod rpc;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum App {
    Text = 1,
    Numbers = 2,
}
impl App {
    #[inline]
    pub const fn index(self) -> usize {
        self as usize - 1
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Action {
    Start = 1,
    Inspect = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Status {
    Admitted = 1,
    Running = 2,
    StopPending = 3,
    StopClaimed = 4,
    Retiring = 5,
    Absent = 6,
    Terminal = 7,
    Denied = 8,
    LaunchFailed = 9,
    Stale = 10,
    Exhausted = 11,
    Busy = 12,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Request {
    sequence: u64,
    pub app: App,
    pub action: Action,
    pub generation: u32,
}
impl Request {
    #[inline]
    pub const fn new(
        sequence: u64,
        app: App,
        action: Action,
        generation: u32,
    ) -> Result<Self, Error> {
        if sequence == 0 || sequence == u64::MAX {
            return Err(Error::Sequence);
        }
        Ok(Self {
            sequence,
            app,
            action,
            generation,
        })
    }
    #[inline]
    pub const fn sequence(self) -> u64 {
        self.sequence
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Reply {
    request: Request,
    status: Status,
    generation: u32,
}
impl Reply {
    #[inline]
    pub fn new(request: Request, status: Status, generation: u32) -> Result<Self, Error> {
        let expected = request.generation;
        let valid = match status {
            Status::Admitted | Status::LaunchFailed => {
                request.action == Action::Start && expected.checked_add(1) == Some(generation)
            }
            Status::Stale => generation != expected,
            Status::Exhausted => {
                request.action == Action::Start && generation == u32::MAX && expected == generation
            }
            Status::Running
            | Status::StopPending
            | Status::StopClaimed
            | Status::Retiring
            | Status::Terminal => generation != 0 && generation == expected,
            Status::Absent | Status::Denied | Status::Busy => generation == expected,
        };
        if !valid {
            return Err(Error::Wire);
        }
        Ok(Self {
            request,
            status,
            generation,
        })
    }
    #[inline]
    pub const fn status(self) -> Status {
        self.status
    }
    #[inline]
    pub const fn request(self) -> Request {
        self.request
    }
    #[inline]
    pub const fn generation(self) -> u32 {
        self.generation
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Frame {
    Request(Request),
    Reply(Reply),
}
impl Frame {
    #[inline]
    pub fn encode(self) -> [u8; BYTES] {
        let (request, tag, status, generation) = match self {
            Self::Request(request) => (request, 1, 0, 0),
            Self::Reply(reply) => (reply.request, 2, reply.status as u8, reply.generation),
        };
        let mut wire = [0; BYTES];
        wire[..4].copy_from_slice(b"PLC1");
        wire[4] = tag;
        wire[5] = request.action as u8;
        wire[6] = request.app as u8;
        wire[7] = status;
        wire[8..16].copy_from_slice(&request.sequence.to_le_bytes());
        wire[16..20].copy_from_slice(&request.generation.to_le_bytes());
        wire[20..24].copy_from_slice(&generation.to_le_bytes());
        wire
    }
    #[inline]
    pub fn decode(wire: &[u8]) -> Result<Self, Error> {
        if wire.len() != BYTES || &wire[..4] != b"PLC1" || wire[24..] != [0; 8] {
            return Err(Error::Wire);
        }
        let action = match wire[5] {
            1 => Action::Start,
            2 => Action::Inspect,
            _ => return Err(Error::Wire),
        };
        let app = match wire[6] {
            1 => App::Text,
            2 => App::Numbers,
            _ => return Err(Error::Wire),
        };
        let request = Request::new(
            u64::from_le_bytes(wire[8..16].try_into().map_err(|_| Error::Wire)?),
            app,
            action,
            u32::from_le_bytes(wire[16..20].try_into().map_err(|_| Error::Wire)?),
        )?;
        let generation = u32::from_le_bytes(wire[20..24].try_into().map_err(|_| Error::Wire)?);
        match wire[4] {
            1 if wire[7] == 0 && generation == 0 => Ok(Self::Request(request)),
            2 => {
                let status = match wire[7] {
                    1 => Status::Admitted,
                    2 => Status::Running,
                    3 => Status::StopPending,
                    4 => Status::StopClaimed,
                    5 => Status::Retiring,
                    6 => Status::Absent,
                    7 => Status::Terminal,
                    8 => Status::Denied,
                    9 => Status::LaunchFailed,
                    10 => Status::Stale,
                    11 => Status::Exhausted,
                    12 => Status::Busy,
                    _ => return Err(Error::Wire),
                };
                Reply::new(request, status, generation).map(Self::Reply)
            }
            _ => Err(Error::Wire),
        }
    }
}

/// One accepted request and retained result; transport acknowledgments release
/// the slot, never the monotonic replay fence or process ownership.
pub struct Broker {
    last: u64,
    request: Option<Request>,
    result: Option<Reply>,
    failed: bool,
}
impl Default for Broker {
    #[inline]
    fn default() -> Self {
        Self::new()
    }
}
impl Broker {
    #[inline]
    pub const fn new() -> Self {
        Self {
            last: 0,
            request: None,
            result: None,
            failed: false,
        }
    }
    pub fn begin<C: Calls>(
        &mut self,
        request: Request,
        processes: &mut ApplicationProcesses<C>,
    ) -> Result<(), Error> {
        if self.failed {
            return Err(Error::Transport);
        }
        if self.request.is_some() || request.sequence <= self.last {
            return Err(Error::Sequence);
        }
        let result = processes.begin_launch(request)?;
        self.last = request.sequence;
        self.request = Some(request);
        self.result = result;
        Ok(())
    }
    /// At most one process syscall; a retained reply performs no syscall.
    pub fn poll<C: Calls>(
        &mut self,
        processes: &mut ApplicationProcesses<C>,
    ) -> Result<bool, Error> {
        if self.failed {
            return Err(Error::Transport);
        }
        let request = self.request.ok_or(Error::Sequence)?;
        if self.result.is_none() {
            match processes.poll_launch(request) {
                Ok(reply) => self.result = reply,
                Err(error) => {
                    self.failed = true;
                    return Err(error);
                }
            }
        }
        Ok(self.result.is_some())
    }
    #[inline]
    pub const fn reply(&self) -> Option<Reply> {
        self.result
    }
    #[inline]
    pub fn acknowledge(&mut self, sequence: u64) -> Result<(), Error> {
        if self.failed {
            return Err(Error::Transport);
        }
        if self.result.is_none() || self.request.map(Request::sequence) != Some(sequence) {
            return Err(Error::Sequence);
        }
        self.request = None;
        self.result = None;
        Ok(())
    }
}

#[cfg(test)]
mod tests;
