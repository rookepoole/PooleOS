//! Command policy uses only explicit launch/process handles, never raw task IDs.
#![forbid(unsafe_code)]
use super::{Commands, Error};
use crate::supervisor::{Calls, Completion};

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
}
pub struct Processes<C> {
    tasks: [Task; 2],
    pending: Option<(usize, Operation)>,
    calls: C,
    output: [u8; 64],
    bytes: usize,
}
fn typed(handle: u64, tag: u64) -> bool {
    handle >> 32 != 0 && handle & 0xffff0000 == tag << 16 && handle & 0xffff != 0
}
impl<C: Calls> Processes<C> {
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
    fn reply(&mut self, slot: usize, label: &[u8], detail: Option<u32>) -> Result<bool, Error> {
        self.bytes = 0;
        self.output.fill(0);
        for bytes in [
            if slot == 0 {
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
impl<C: Calls> Commands for Processes<C> {
    fn help(&self) -> &'static [u8] {
        b"help  version  echo TEXT  exit\r\nstart worker|fault  stop worker|fault  status worker|fault\r\n"
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
            b"worker" => 0,
            b"fault" => 1,
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
        if operation == Operation::Start {
            let sequence = task.sequence.checked_add(1).ok_or(Error::Sequence)?;
            match self.calls.invoke(19, task.factory, u64::from(sequence)) {
                (6, 0) => Ok(false),
                (0, handle)
                    if typed(handle, 5) && self.tasks.iter().all(|t| t.handle != Some(handle)) =>
                {
                    *self.tasks.get_mut(slot).ok_or(Error::Wire)? = Task {
                        sequence,
                        handle: Some(handle),
                        complete: false,
                        ..task
                    };
                    self.reply(slot, b"admitted", None)
                }
                (8, 0) => {
                    *self.tasks.get_mut(slot).ok_or(Error::Wire)? = Task {
                        sequence,
                        handle: None,
                        complete: true,
                        ..task
                    };
                    self.reply(slot, b"launch failed", None)
                }
                (5, 0) => self.reply(slot, b"denied", None),
                _ => Err(Error::Transport),
            }
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
                (0, value) => {
                    Completion::decode(value).map_err(|_| Error::Transport)?;
                    if operation == Operation::InspectStart {
                        self.tasks.get_mut(slot).ok_or(Error::Wire)?.complete = true;
                        self.pending = Some((slot, Operation::Start));
                        Ok(false)
                    } else {
                        self.terminal(slot, value)
                    }
                }
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
