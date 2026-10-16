//! Bounded PAPP1 shell jobs. Kernel peer identity and process leases are separate.
#![forbid(unsafe_code)]
use super::{
    Commands,
    processes::{ApplicationProcesses, Observation},
};
use crate::{
    apps::{
        self, Kind,
        wire::{self, Frame},
    },
    console_ipc::{Error, rpc::Calls},
    files,
};

pub const MAX_JOB_POLLS: u32 = 32768;
#[cfg(test)]
const SLOTS: [u64; 2] = [4, 5];

#[derive(Clone, Copy, Eq, PartialEq)]
enum App {
    Text,
    Numbers,
}
impl App {
    fn index(self) -> usize {
        match self {
            Self::Text => 0,
            Self::Numbers => 1,
        }
    }
    fn slot(self) -> u64 {
        match self {
            Self::Text => 4,
            Self::Numbers => 5,
        }
    }
}

#[derive(Clone, Copy)]
struct Client {
    peer: u64,
    sequence: u64,
    ready: u64,
    blocked: bool,
}
impl Client {
    const EMPTY: Self = Self {
        peer: 0,
        sequence: 1,
        ready: 0,
        blocked: false,
    };
}
#[derive(Clone, Copy, Eq, PartialEq)]
enum State {
    Idle,
    Ready,
    Run,
    Result,
    Ack,
    Fault,
    Abort,
    Output,
}

pub struct Jobs<C> {
    endpoint: u64,
    calls: C,
    clients: [Client; 2],
    state: State,
    target: App,
    job: Frame,
    result: Frame,
    reply: u64,
    discard: u64,
    monitor: bool,
    stop: bool,
    remaining: u32,
    output: [u8; 128],
    bytes: usize,
}
fn kind(slot: App) -> Kind {
    match slot {
        App::Text => Kind::Text,
        App::Numbers => Kind::Numbers,
    }
}
fn typed(value: u64, tag: u64) -> bool {
    value >> 32 != 0 && value & 0xffff0000 == tag << 16 && value & 0xffff != 0
}
impl<C: Calls> Jobs<C> {
    #[inline(always)]
    pub const fn new(endpoint: u64, calls: C) -> Self {
        Self {
            endpoint,
            calls,
            clients: [Client::EMPTY; 2],
            state: State::Idle,
            target: App::Text,
            job: Frame::empty(wire::RUN, Kind::Text, 1),
            result: Frame::empty(wire::ACK, Kind::Text, 1),
            reply: 0,
            discard: 0,
            monitor: true,
            stop: false,
            remaining: 0,
            output: [0; 128],
            bytes: 0,
        }
    }
    #[inline(never)]
    fn put(&mut self, byte: u8) -> Result<(), Error> {
        *self.output.get_mut(self.bytes).ok_or(Error::Wire)? = byte;
        self.bytes = self.bytes.checked_add(1).ok_or(Error::Wire)?;
        Ok(())
    }
    fn append(&mut self, bytes: &[u8]) -> Result<(), Error> {
        for &byte in bytes {
            self.put(byte)?;
        }
        Ok(())
    }
    // Keep a variable-length path copy local to the freestanding program.
    #[inline(never)]
    fn path_byte(&mut self, index: usize, byte: u8) -> Result<(), Error> {
        *self.job.data.get_mut(index).ok_or(Error::Wire)? = byte;
        Ok(())
    }
    fn prefix(&mut self) -> Result<(), Error> {
        self.bytes = 0;
        self.append(if self.target == App::Text {
            b"text: "
        } else {
            b"numbers: "
        })
    }
    fn text(&mut self, bytes: &[u8]) -> Result<(), Error> {
        self.prefix()?;
        self.append(bytes)?;
        self.append(b"\r\n")
    }
    fn decimal(&mut self, value: i64) -> Result<(), Error> {
        if value < 0 {
            self.put(b'-')?;
        }
        let mut n = value.unsigned_abs();
        let mut digits = [0; 20];
        let mut count = 0usize;
        loop {
            *digits.get_mut(count).ok_or(Error::Wire)? = b'0' + (n % 10) as u8;
            count = count.checked_add(1).ok_or(Error::Wire)?;
            n /= 10;
            if n == 0 {
                break;
            }
        }
        for i in (0..count).rev() {
            self.put(*digits.get(i).ok_or(Error::Wire)?)?;
        }
        Ok(())
    }
    fn sync<P: crate::supervisor::Calls>(
        &mut self,
        slot: App,
        processes: &ApplicationProcesses<P>,
    ) {
        let peer = processes
            .child(slot.index())
            .map_or(0, |child| (u64::from(child.sequence) << 32) | slot.slot());
        if self.clients[slot.index()].peer != peer {
            // A newly admitted generation requires kernel-observed retirement of
            // the old one. Its cached reply authority has already been revoked.
            self.clients[slot.index()] = Client {
                peer,
                ..Client::EMPTY
            };
        }
    }
    pub fn begin<P: crate::supervisor::Calls>(
        &mut self,
        line: &[u8],
        processes: &ApplicationProcesses<P>,
    ) -> Result<bool, Error> {
        if !matches!(self.state, State::Idle | State::Output) {
            return Err(Error::Sequence);
        }
        let (target, fault, path) = if let Some(path) = line.strip_prefix(b"text ") {
            (App::Text, false, path)
        } else if let Some(path) = line.strip_prefix(b"numbers ") {
            (App::Numbers, false, path)
        } else if line == b"fault text" {
            (App::Text, true, &[][..])
        } else if line == b"fault numbers" {
            (App::Numbers, true, &[][..])
        } else {
            return Ok(false);
        };
        if !typed(self.endpoint, 1) {
            return Err(Error::Wire);
        }
        self.target = target;
        self.sync(target, processes);
        self.state = State::Output;
        if self.clients[target.index()].peer == 0 {
            self.text(b"not started")?;
            return Ok(true);
        }
        if self.clients[target.index()].blocked {
            self.text(b"stop and restart required")?;
            return Ok(true);
        }
        if !fault && !files::valid_path(path) {
            self.text(b"invalid path")?;
            return Ok(true);
        }
        self.job = Frame::empty(
            if fault { wire::FAULT } else { wire::RUN },
            kind(target),
            self.clients[target.index()].sequence,
        );
        self.job.len = path.len() as u8;
        let mut index = 0usize;
        for &byte in path {
            self.path_byte(index, byte)?;
            index = index.checked_add(1).ok_or(Error::Wire)?;
        }
        self.remaining = MAX_JOB_POLLS;
        self.monitor = true;
        self.stop = false;
        self.bytes = 0;
        self.state = State::Ready;
        Ok(true)
    }
    fn abort(&mut self, label: &[u8]) -> Result<(), Error> {
        self.clients[self.target.index()].blocked = true;
        self.state = State::Abort;
        self.stop = true;
        self.text(label)
    }
    fn discard_token(&mut self, token: u64) -> Result<(), Error> {
        match self.calls.invoke(9, token, &mut []) {
            (0 | 5, 0) => Ok(()),
            _ => Err(Error::Transport),
        }
    }
    #[inline(always)]
    fn receive<P: crate::supervisor::Calls>(
        &mut self,
        processes: &ApplicationProcesses<P>,
    ) -> Result<(), Error> {
        let mut bytes = [0; 96];
        match self.calls.invoke(7, self.endpoint, &mut bytes) {
            (6, 0) => return Ok(()),
            (0, count) if (32..=96).contains(&count) => {
                let slot = u64::from_le_bytes(bytes[..8].try_into().map_err(|_| Error::Wire)?);
                let generation =
                    u64::from_le_bytes(bytes[8..16].try_into().map_err(|_| Error::Wire)?);
                let token = u64::from_le_bytes(bytes[16..24].try_into().map_err(|_| Error::Wire)?);
                if slot > u16::MAX as u64
                    || generation == 0
                    || generation > u32::MAX as u64
                    || u64::from_le_bytes(bytes[24..32].try_into().map_err(|_| Error::Wire)?)
                        != count - 32
                {
                    return Err(Error::Peer);
                }
                if token == 0 {
                    return Ok(());
                }
                if !typed(token, 2) {
                    return Err(Error::Peer);
                }
                self.discard = token;
                let index = match slot {
                    4 => App::Text,
                    5 => App::Numbers,
                    _ => return Ok(()),
                };
                self.sync(index, processes);
                let peer = (generation << 32) | slot;
                if self.clients[index.index()].peer != peer || self.clients[index.index()].blocked {
                    return Ok(());
                }
                let decoded = Frame::decode(bytes.get(32..count as usize).ok_or(Error::Wire)?);
                let frame = match decoded {
                    Some(frame)
                        if frame.kind == kind(index)
                            && frame.sequence == self.clients[index.index()].sequence =>
                    {
                        frame
                    }
                    _ => {
                        self.clients[index.index()].blocked = true;
                        if index == self.target {
                            self.abort(b"protocol error; stop requested")?;
                        }
                        return Ok(());
                    }
                };
                if frame.phase == wire::READY
                    && self.clients[index.index()].ready == 0
                    && (index != self.target || self.state == State::Ready)
                {
                    self.clients[index.index()].ready = token;
                    self.discard = 0;
                } else if frame.phase == wire::RESULT
                    && index == self.target
                    && self.state == State::Result
                    && valid_result(&frame)
                {
                    self.result = frame;
                    self.reply = token;
                    self.discard = 0;
                    self.state = State::Ack;
                } else {
                    self.clients[index.index()].blocked = true;
                    if index == self.target {
                        self.abort(b"protocol error; stop requested")?;
                    }
                }
            }
            _ => return Err(Error::Transport),
        }
        Ok(())
    }
    fn result_text(&mut self) -> Result<(), Error> {
        let Some(values) = self.result.values() else {
            return self.text(match self.result.status {
                apps::BAD_PATH => b"invalid path",
                apps::NOT_FOUND => b"not found",
                apps::INVALID_DATA => b"invalid data",
                apps::LIMIT => b"limit exceeded",
                apps::UNAVAILABLE => b"file service unavailable",
                _ => return Err(Error::Wire),
            });
        };
        self.prefix()?;
        // Explicit fields avoid an absolute-pointer label table in the RX image.
        self.append(if self.target == App::Text {
            b"bytes="
        } else {
            b"count="
        })?;
        self.decimal(values[0])?;
        self.append(if self.target == App::Text {
            b" words="
        } else {
            b" sum="
        })?;
        self.decimal(values[1])?;
        self.append(if self.target == App::Text {
            b" lf="
        } else {
            b" min="
        })?;
        self.decimal(values[2])?;
        if self.target == App::Numbers {
            self.append(b" max=")?;
            self.decimal(values[3])?;
        }
        self.append(b"\r\n")
    }
    /// At most one syscall, including process observation/discard/stop, per poll.
    pub fn poll<P: crate::supervisor::Calls>(
        &mut self,
        processes: &mut ApplicationProcesses<P>,
    ) -> Result<bool, Error> {
        if self.state == State::Output {
            return Ok(true);
        }
        if self.state == State::Idle {
            return Err(Error::Sequence);
        }
        if self.state != State::Abort
            && processes.child(self.target.index()).is_some_and(|child| {
                (u64::from(child.sequence) << 32) | self.target.slot()
                    != self.clients[self.target.index()].peer
            })
        {
            self.abort(b"generation changed")?;
            self.stop = false;
        }
        if self.discard != 0 {
            self.discard_token(self.discard)?;
            self.discard = 0;
            return Ok(false);
        }
        if self.state != State::Abort && self.remaining == 0 {
            self.abort(b"timed out; stop requested")?;
        }
        if self.state == State::Abort {
            if self.reply != 0 {
                self.discard_token(self.reply)?;
                self.reply = 0;
                return Ok(false);
            }
            let ready = self.clients[self.target.index()].ready;
            if ready != 0 {
                self.discard_token(ready)?;
                self.clients[self.target.index()].ready = 0;
                return Ok(false);
            }
            if self.stop && !processes.request_stop(self.target.index())? {
                self.text(b"stop denied; restart required")?;
            }
            self.state = State::Output;
            return Ok(true);
        }
        self.remaining = self.remaining.checked_sub(1).ok_or(Error::Sequence)?;
        if self.monitor {
            self.monitor = false;
            if processes.observe(self.target.index())? == Observation::Reported {
                self.clients[self.target.index()].blocked = true;
                self.state = State::Abort;
                self.stop = false;
                self.bytes = 0;
                self.append(processes.response())?;
            }
            return Ok(false);
        }
        self.monitor = true;
        if self.state == State::Ready && self.clients[self.target.index()].ready != 0 {
            self.reply = self.clients[self.target.index()].ready;
            self.clients[self.target.index()].ready = 0;
            self.state = if self.job.phase == wire::FAULT {
                State::Fault
            } else {
                State::Run
            };
        }
        if matches!(self.state, State::Ready | State::Result) {
            self.receive(processes)?;
            return Ok(false);
        }
        let frame = if self.state == State::Ack {
            Frame::empty(
                wire::ACK,
                kind(self.target),
                self.clients[self.target.index()].sequence,
            )
        } else {
            self.job
        };
        let mut bytes = frame.encode();
        match self.calls.invoke(8, self.reply, &mut bytes) {
            (6, 0) => return Ok(false),
            (5, 0) => {
                self.reply = 0;
                self.abort(b"request revoked; stop requested")?;
                return Ok(false);
            }
            (0, 64) => self.reply = 0,
            _ => return Err(Error::Transport),
        }
        match self.state {
            State::Run => self.state = State::Result,
            State::Fault => {
                self.clients[self.target.index()].blocked = true;
                self.text(b"fault requested")?;
                self.state = State::Output;
            }
            State::Ack => {
                if let Some(next) = self.clients[self.target.index()]
                    .sequence
                    .checked_add(1)
                    .filter(|&n| n < u64::MAX)
                {
                    self.clients[self.target.index()].sequence = next;
                } else {
                    self.clients[self.target.index()].blocked = true;
                }
                self.result_text()?;
                self.state = State::Output;
            }
            _ => return Err(Error::Sequence),
        }
        Ok(self.state == State::Output)
    }
    pub fn response(&self) -> &[u8] {
        self.output.get(..self.bytes).unwrap_or(&[])
    }
}

#[inline(always)]
fn valid_result(frame: &Frame) -> bool {
    if frame.status != apps::OK {
        return true;
    }
    let Some([count, sum, min, max]) = frame.values() else {
        return false;
    };
    match frame.kind {
        Kind::Text => {
            (0..=i64::from(apps::MAX_FILE_BYTES)).contains(&count)
                && (0..=count).contains(&sum)
                && (0..=count).contains(&min)
                && max == 0
        }
        Kind::Numbers => {
            (0..=i64::from(apps::MAX_ROWS)).contains(&count)
                && if count == 0 {
                    sum == 0 && min == 0 && max == 0
                } else {
                    min >= i64::from(i32::MIN)
                        && max <= i64::from(i32::MAX)
                        && min <= max
                        && min.checked_mul(count).is_some_and(|bound| sum >= bound)
                        && max.checked_mul(count).is_some_and(|bound| sum <= bound)
                }
        }
    }
}

#[derive(Clone, Copy)]
enum Route {
    Files,
    Processes,
    Jobs,
}
pub struct ApplicationCommands<'a, C, P> {
    files: &'a mut super::files::Files<C>,
    processes: &'a mut ApplicationProcesses<P>,
    jobs: &'a mut Jobs<C>,
    route: Route,
}
impl<'a, C, P> ApplicationCommands<'a, C, P> {
    #[inline(always)]
    pub const fn new(
        files: &'a mut super::files::Files<C>,
        processes: &'a mut ApplicationProcesses<P>,
        jobs: &'a mut Jobs<C>,
    ) -> Self {
        Self {
            files,
            processes,
            jobs,
            route: Route::Processes,
        }
    }
}
impl<C: Calls, P: crate::supervisor::Calls> Commands for ApplicationCommands<'_, C, P> {
    fn help(&self) -> &'static [u8] {
        b"help  version  echo TEXT  exit\r\nls  cat /PATH\r\nstart text|numbers  stop text|numbers  status text|numbers\r\ntext /PATH  numbers /PATH  fault text|numbers\r\n"
    }
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error> {
        if self.files.begin(line)? {
            self.route = Route::Files;
            Ok(true)
        } else if self.processes.begin(line)? {
            self.route = Route::Processes;
            Ok(true)
        } else if self.jobs.begin(line, self.processes)? {
            self.route = Route::Jobs;
            Ok(true)
        } else {
            Ok(false)
        }
    }
    fn poll(&mut self) -> Result<bool, Error> {
        match self.route {
            Route::Files => self.files.poll(),
            Route::Processes => self.processes.poll(),
            Route::Jobs => self.jobs.poll(self.processes),
        }
    }
    fn response(&self) -> &[u8] {
        match self.route {
            Route::Files => self.files.response(),
            Route::Processes => self.processes.response(),
            Route::Jobs => self.jobs.response(),
        }
    }
    fn response_complete(&self) -> bool {
        !matches!(self.route, Route::Files) || self.files.response_complete()
    }
    fn close_allowed(&self) -> bool {
        self.files.close_allowed() && self.processes.close_allowed()
    }
}

#[cfg(test)]
mod tests;
