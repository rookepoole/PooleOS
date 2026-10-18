//! Command policy uses only explicit launch/process handles, never raw task IDs.
#![forbid(unsafe_code)]
use super::{Commands, Error};
use crate::supervisor::{Calls, Completion};
mod launch;

#[derive(Clone, Copy)]
struct Task {
    factory: u64,
    sequence: u32,
    handle: Option<u64>,
    complete: bool,
}
impl Task {
    const fn new(factory: u64) -> Self {
        Self {
            factory,
            sequence: 0,
            handle: None,
            complete: true,
        }
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Operation {
    Start,
    InspectStart,
    Stop,
    Status,
    LaunchStart,
    LaunchInspect,
    LaunchStatus,
}
pub type Processes<C> = Policy<C, false>;
pub type ApplicationProcesses<C> = Policy<C, true>;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Child {
    pub sequence: u32,
    pub handle: u64,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Observation {
    Attached,
    Reported,
}

pub struct Policy<C, const APPLICATIONS: bool> {
    tasks: [Task; 2],
    pending: Option<(usize, Operation)>,
    calls: C,
    output: [u8; 64],
    bytes: usize,
}
fn typed(handle: u64, tag: u64) -> bool {
    handle >> 32 != 0 && handle & 0xffff0000 == tag << 16 && handle & 0xffff != 0
}
impl<C: Calls, const APPLICATIONS: bool> Policy<C, APPLICATIONS> {
    #[inline(always)]
    pub fn new(factories: [u64; 2], calls: C) -> Result<Self, Error> {
        let mut policy = Self::unbound(calls);
        policy.bind(factories)?;
        Ok(policy)
    }
    /// In-place startup avoids moving the response buffer through a Result.
    #[inline(always)]
    pub const fn unbound(calls: C) -> Self {
        Self {
            tasks: [Task::new(0), Task::new(0)],
            pending: None,
            calls,
            output: [0; 64],
            bytes: 0,
        }
    }
    pub fn bind(&mut self, factories: [u64; 2]) -> Result<(), Error> {
        if self.tasks.iter().any(|task| task.factory != 0)
            || factories[0] == factories[1]
            || factories.iter().any(|&handle| !typed(handle, 6))
        {
            return Err(Error::Wire);
        }
        self.tasks[0].factory = factories[0];
        self.tasks[1].factory = factories[1];
        Ok(())
    }
    pub fn child(&self, slot: usize) -> Option<Child> {
        let task = self.tasks.get(slot)?;
        if task.complete {
            return None;
        }
        Some(Child {
            sequence: task.sequence,
            handle: task.handle?,
        })
    }
    /// One observation call; only the kernel's terminal result closes a lifetime.
    pub fn observe(&mut self, slot: usize) -> Result<Observation, Error> {
        if self.pending.is_some() {
            return Err(Error::Sequence);
        }
        let Some(child) = self.child(slot) else {
            self.reply(slot, b"not started", None)?;
            return Ok(Observation::Reported);
        };
        match self.calls.invoke(20, child.handle, 0) {
            (6, 1) => Ok(Observation::Attached),
            (6, 2..=4) => {
                self.reply(slot, b"stopping", None)?;
                Ok(Observation::Reported)
            }
            (0, value) => {
                self.terminal(slot, value)?;
                Ok(Observation::Reported)
            }
            (5, 0) => {
                self.reply(slot, b"denied", None)?;
                Ok(Observation::Reported)
            }
            _ => Err(Error::Transport),
        }
    }
    /// A stop request is not a completion or permission to close the session.
    pub fn request_stop(&mut self, slot: usize) -> Result<bool, Error> {
        if self.pending.is_some() {
            return Err(Error::Sequence);
        }
        let Some(child) = self.child(slot) else {
            return Ok(true);
        };
        match self.calls.invoke(18, child.handle, 0) {
            (6 | 9, 0) => Ok(true),
            (5, 0) => Ok(false),
            _ => Err(Error::Transport),
        }
    }
    fn reply(&mut self, slot: usize, label: &[u8], detail: Option<u32>) -> Result<bool, Error> {
        self.bytes = 0;
        self.output.fill(0);
        for bytes in [
            if APPLICATIONS {
                if slot == 0 {
                    &b"text: "[..]
                } else {
                    &b"numbers: "[..]
                }
            } else if slot == 0 {
                &b"worker: "[..]
            } else {
                &b"fault: "[..]
            },
            label,
        ] {
            self.append(bytes)?;
        }
        if let Some(value) = detail {
            self.append(b" 0x")?;
            for shift in (0..8).rev() {
                let digit = ((value >> (shift * 4)) & 15) as u8;
                self.append(&[if digit < 10 {
                    b'0' + digit
                } else {
                    b'A' + digit - 10
                }])?;
            }
        }
        self.append(b"\r\n")?;
        self.pending = None;
        Ok(true)
    }
    fn append(&mut self, bytes: &[u8]) -> Result<(), Error> {
        for &byte in bytes {
            self.put(byte)?;
        }
        Ok(())
    }
    // Keep bounded byte output local to this relocation-free program.
    #[inline(never)]
    fn put(&mut self, byte: u8) -> Result<(), Error> {
        *self.output.get_mut(self.bytes).ok_or(Error::Wire)? = byte;
        self.bytes = self.bytes.checked_add(1).ok_or(Error::Wire)?;
        Ok(())
    }
    fn terminal(&mut self, slot: usize, value: u64) -> Result<bool, Error> {
        let (label, detail): (&[u8], Option<u32>) =
            match Completion::decode(value).map_err(|_| Error::Transport)? {
                Completion::Exit(code) => (b"exit", Some(code)),
                Completion::Fault(vector) => (b"fault", Some(u32::from(vector))),
                Completion::InvalidReturn(reason) => (b"invalid return", Some(u32::from(reason))),
                Completion::Cancelled => (b"cancelled", None),
                Completion::CallLimit => (b"call limit", None),
                Completion::CallCounterExhausted => (b"counter exhausted", None),
                Completion::Watchdog => (b"watchdog", None),
            };
        self.tasks.get_mut(slot).ok_or(Error::Wire)?.complete = true;
        self.reply(slot, label, detail)
    }
}
impl<C: Calls, const APPLICATIONS: bool> Commands for Policy<C, APPLICATIONS> {
    fn help(&self) -> &'static [u8] {
        if APPLICATIONS {
            b"help  version  echo TEXT  exit\r\nstart text|numbers  stop text|numbers  status text|numbers\r\n"
        } else {
            b"help  version  echo TEXT  exit\r\nstart worker|fault  stop worker|fault  status worker|fault\r\n"
        }
    }
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error> {
        if self.tasks.iter().any(|task| task.factory == 0) {
            return Err(Error::Wire);
        }
        if self.pending.is_some() {
            return Err(Error::Sequence);
        }
        let (operation, name) = if let Some(name) = line.strip_prefix(b"start ") {
            (Operation::Start, name)
        } else if let Some(name) = line.strip_prefix(b"stop ") {
            (Operation::Stop, name)
        } else if let Some(name) = line.strip_prefix(b"status ") {
            (Operation::Status, name)
        } else {
            return Ok(false);
        };
        let slot = match name {
            b"text" if APPLICATIONS => 0,
            b"numbers" if APPLICATIONS => 1,
            b"worker" if !APPLICATIONS => 0,
            b"fault" if !APPLICATIONS => 1,
            _ => return Ok(false),
        };
        let task = self.tasks.get(slot).ok_or(Error::Wire)?;
        let operation = if operation == Operation::Start && task.handle.is_some() {
            Operation::InspectStart
        } else {
            operation
        };
        self.pending = Some((slot, operation));
        Ok(true)
    }
    /// One syscall per step. Console output is emitted only after an observed result.
    #[inline(never)]
    fn poll(&mut self) -> Result<bool, Error> {
        let (slot, operation) = self.pending.ok_or(Error::Sequence)?;
        let task = *self.tasks.get(slot).ok_or(Error::Wire)?;
        if matches!(
            operation,
            Operation::LaunchStart | Operation::LaunchInspect | Operation::LaunchStatus
        ) {
            return Err(Error::Sequence);
        }
        if matches!(operation, Operation::Start | Operation::InspectStart) {
            use crate::session_control::Status;
            let Some(status) =
                self.start_step(slot, operation == Operation::InspectStart, Operation::Start)?
            else {
                return Ok(false);
            };
            let label: &[u8] = match status {
                Status::Admitted => b"admitted",
                Status::LaunchFailed => b"launch failed",
                Status::Denied => b"denied",
                Status::Running => b"attached",
                Status::StopPending => b"stop pending",
                Status::StopClaimed => b"stop claimed",
                Status::Retiring => b"retiring",
                _ => return Err(Error::Transport),
            };
            self.reply(slot, label, None)
        } else {
            let Some(handle) = task.handle else {
                return self.reply(slot, b"not started", None);
            };
            if operation == Operation::Stop {
                return match self.calls.invoke(18, handle, 0) {
                    (6, 0) => self.reply(slot, b"stop requested", None),
                    (9, 0) => {
                        self.pending = Some((slot, Operation::Status));
                        Ok(false)
                    }
                    (5, 0) => self.reply(slot, b"denied", None),
                    _ => Err(Error::Transport),
                };
            }
            match self.calls.invoke(20, handle, 0) {
                (0, value) => self.terminal(slot, value),
                (6, value @ 1..=4) if !task.complete => self.reply(
                    slot,
                    match value {
                        1 => b"attached",
                        2 => b"stop pending",
                        3 => b"stop claimed",
                        _ => b"retiring",
                    },
                    None,
                ),
                (5, 0) => self.reply(slot, b"denied", None),
                _ => Err(Error::Transport),
            }
        }
    }
    fn response(&self) -> &[u8] {
        self.output.get(..self.bytes).unwrap_or(&[])
    }
    fn close_allowed(&self) -> bool {
        self.pending.is_none()
            && self
                .tasks
                .iter()
                .all(|task| task.factory != 0 && task.complete)
    }
}

#[cfg(test)]
mod tests;
