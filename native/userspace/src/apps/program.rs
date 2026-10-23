//! One syscall per poll; file contents never traverse the kernel as app policy.
use super::{
    BAD_PATH, INVALID_DATA, Kind, LIMIT, MAX_FILE_BYTES, NOT_FOUND, UNAVAILABLE,
    stats::Accumulator,
    wire::{self, Frame},
};
use crate::{
    console_ipc::{Error, rpc::Calls},
    files,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Ready,
    Job,
    Read,
    Wait,
    Data,
    Report,
    Ack,
    Fault,
    Failed,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Progress {
    Pending,
    JobComplete,
    FaultRequested,
}

pub struct Program<C> {
    control: C,
    endpoint: u64,
    peer: u64,
    pending: u64,
    kind: Kind,
    sequence: u64,
    file_sequence: u64,
    files: files::rpc::Client<C>,
    request: files::Frame,
    total: Option<u32>,
    accumulator: Accumulator,
    output: Frame,
    state: State,
}
impl<C: Calls> Program<C> {
    #[inline(always)]
    pub const fn new(
        kind: Kind,
        endpoint: u64,
        peer: u64,
        control: C,
        files: files::rpc::Client<C>,
    ) -> Self {
        Self {
            control,
            endpoint,
            peer,
            pending: 0,
            kind,
            sequence: 1,
            file_sequence: 1,
            files,
            request: files::Frame::empty(files::READ, 1, 0),
            total: None,
            accumulator: Accumulator::new(kind),
            output: Frame::empty(wire::READY, kind, 1),
            state: State::Ready,
        }
    }
    #[inline(always)]
    pub fn display_result(&self) -> Option<Frame> {
        if matches!(self.state, State::Report | State::Ack) {
            Some(self.output)
        } else {
            None
        }
    }
    #[inline(always)]
    pub fn display_idle(&self) -> bool {
        matches!(self.state, State::Ready | State::Job)
    }
    fn report(&mut self, values: Result<[i64; 4], u8>) {
        self.output = Frame::result(self.kind, self.sequence, values);
        self.state = State::Report;
    }
    fn send(&mut self) -> Result<bool, Error> {
        let mut bytes = self.output.encode();
        match self.control.invoke(10, self.endpoint, &mut bytes) {
            (0, token)
                if token >> 32 != 0 && token & 0xffff0000 == 3 << 16 && token & 0xffff != 0 =>
            {
                self.pending = token;
                Ok(true)
            }
            (6, 0) => Ok(false),
            (5 | 9, 0) => Err(Error::Revoked),
            _ => Err(Error::Transport),
        }
    }
    #[inline(always)]
    fn receive(&mut self) -> Result<Option<Frame>, Error> {
        let mut bytes = [0; 96];
        match self.control.invoke(11, self.pending, &mut bytes) {
            (0, 96) => {
                self.pending = 0;
                let slot = u64::from_le_bytes(bytes[..8].try_into().map_err(|_| Error::Wire)?);
                let generation =
                    u64::from_le_bytes(bytes[8..16].try_into().map_err(|_| Error::Wire)?);
                if slot > u16::MAX as u64
                    || generation == 0
                    || generation > u32::MAX as u64
                    || (generation << 32) | slot != self.peer
                    || bytes[16..24].iter().any(|&b| b != 0)
                    || u64::from_le_bytes(bytes[24..32].try_into().map_err(|_| Error::Wire)?) != 64
                {
                    return Err(Error::Peer);
                }
                let frame = Frame::decode(&bytes[32..]).ok_or(Error::Wire)?;
                if frame.kind != self.kind || frame.sequence != self.sequence {
                    return Err(Error::Sequence);
                }
                Ok(Some(frame))
            }
            (6, 0) => Ok(None),
            (9, 0) => {
                self.pending = 0;
                Err(Error::Revoked)
            }
            _ => Err(Error::Transport),
        }
    }
    fn data(&mut self, reply: files::Frame) -> Result<(), Error> {
        self.file_sequence = self
            .file_sequence
            .checked_add(1)
            .filter(|&n| n < u64::MAX)
            .ok_or(Error::Sequence)?;
        if reply.status != files::OK {
            if reply.len != 0 || reply.total != 0 {
                return Err(Error::Wire);
            }
            self.report(Err(match reply.status {
                files::NOT_FOUND => NOT_FOUND,
                files::INVALID | files::RANGE => INVALID_DATA,
                _ => return Err(Error::Wire),
            }));
            return Ok(());
        }
        if reply.total > MAX_FILE_BYTES {
            self.report(Err(LIMIT));
            return Ok(());
        }
        if self.total.is_some_and(|n| n != reply.total) {
            return Err(Error::Wire);
        }
        self.total = Some(reply.total);
        let end = self
            .request
            .offset
            .checked_add(u32::from(reply.len))
            .ok_or(Error::Wire)?;
        if end > reply.total || (reply.len == 0 && end != reply.total) {
            return Err(Error::Wire);
        }
        if let Err(error) = self.accumulator.push(reply.payload().ok_or(Error::Wire)?) {
            self.report(Err(error));
        } else if end == reply.total {
            let result = self.accumulator.finish();
            self.report(result);
        } else {
            self.request.offset = end;
            self.request.sequence = self.file_sequence;
            self.state = State::Read;
        }
        Ok(())
    }
    fn step(&mut self) -> Result<Progress, Error> {
        match self.state {
            State::Ready | State::Report => {
                if self.send()? {
                    self.state = if self.state == State::Ready {
                        State::Job
                    } else {
                        State::Ack
                    };
                }
            }
            State::Job => {
                if let Some(job) = self.receive()? {
                    if job.phase == wire::FAULT {
                        self.state = State::Fault;
                        return Ok(Progress::FaultRequested);
                    }
                    if job.phase != wire::RUN {
                        return Err(Error::Sequence);
                    }
                    let path = job.data.get(..usize::from(job.len)).ok_or(Error::Wire)?;
                    if !files::valid_path(path) {
                        self.report(Err(BAD_PATH));
                    } else {
                        self.request = files::Frame::empty(files::READ, self.file_sequence, 0);
                        self.request.len = job.len;
                        self.request.data = job.data;
                        self.total = None;
                        self.accumulator = Accumulator::new(self.kind);
                        self.state = State::Read;
                    }
                }
            }
            State::Read => match self.files.start(&self.request) {
                Ok(true) => self.state = State::Wait,
                Ok(false) => {}
                Err(Error::Revoked) => self.report(Err(UNAVAILABLE)),
                Err(error) => return Err(error),
            },
            State::Wait => {
                if self.files.wait()? {
                    self.state = State::Data;
                }
            }
            State::Data => match self.files.finish() {
                Ok(Some(reply)) => self.data(reply)?,
                Ok(None) => self.state = State::Wait,
                Err(Error::Revoked) => self.report(Err(UNAVAILABLE)),
                Err(error) => return Err(error),
            },
            State::Ack => {
                if let Some(reply) = self.receive()? {
                    if reply.phase != wire::ACK {
                        return Err(Error::Sequence);
                    }
                    self.sequence = self
                        .sequence
                        .checked_add(1)
                        .filter(|&n| n < u64::MAX)
                        .ok_or(Error::Sequence)?;
                    self.output = Frame::empty(wire::READY, self.kind, self.sequence);
                    self.state = State::Ready;
                    return Ok(Progress::JobComplete);
                }
            }
            State::Fault => return Ok(Progress::FaultRequested),
            State::Failed => return Err(Error::Transport),
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
