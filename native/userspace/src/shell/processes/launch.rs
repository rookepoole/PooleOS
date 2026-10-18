//! Shared launch transitions and the typed broker's exclusive operation modes.
use super::*;
use crate::session_control::{Action, Reply, Request, Status};

#[inline]
fn live(value: u64) -> Result<Status, Error> {
    match value {
        1 => Ok(Status::Running),
        2 => Ok(Status::StopPending),
        3 => Ok(Status::StopClaimed),
        4 => Ok(Status::Retiring),
        _ => Err(Error::Transport),
    }
}

impl<C: Calls, const APPLICATIONS: bool> Policy<C, APPLICATIONS> {
    pub(super) fn start_step(
        &mut self,
        slot: usize,
        inspect: bool,
        next: Operation,
    ) -> Result<Option<Status>, Error> {
        let task = *self.tasks.get(slot).ok_or(Error::Wire)?;
        if inspect {
            let handle = task.handle.ok_or(Error::Sequence)?;
            return match self.calls.invoke(20, handle, 0) {
                (0, value) => {
                    Completion::decode(value).map_err(|_| Error::Transport)?;
                    self.tasks[slot].complete = true;
                    self.pending = Some((slot, next));
                    Ok(None)
                }
                (6, value) if !task.complete => live(value).map(Some),
                (5, 0) => Ok(Some(Status::Denied)),
                _ => Err(Error::Transport),
            };
        }
        let sequence = task.sequence.checked_add(1).ok_or(Error::Sequence)?;
        match self.calls.invoke(19, task.factory, u64::from(sequence)) {
            (6, 0) => Ok(None),
            (0, handle)
                if typed(handle, 5) && self.tasks.iter().all(|t| t.handle != Some(handle)) =>
            {
                self.tasks[slot] = Task {
                    sequence,
                    handle: Some(handle),
                    complete: false,
                    ..task
                };
                Ok(Some(Status::Admitted))
            }
            (8, 0) => {
                self.tasks[slot] = Task {
                    sequence,
                    handle: None,
                    complete: true,
                    ..task
                };
                Ok(Some(Status::LaunchFailed))
            }
            (5, 0) => Ok(Some(Status::Denied)),
            _ => Err(Error::Transport),
        }
    }
}

impl<C: Calls> ApplicationProcesses<C> {
    pub(crate) fn begin_launch(&mut self, request: Request) -> Result<Option<Reply>, Error> {
        if self.tasks.iter().any(|task| task.factory == 0) {
            return Err(Error::Wire);
        }
        let slot = request.app.index();
        let task = self.tasks[slot];
        let immediate = if task.sequence != request.generation {
            Some(Status::Stale)
        } else if self.pending.is_some() {
            Some(Status::Busy)
        } else if request.action == Action::Inspect && task.handle.is_none() {
            Some(Status::Absent)
        } else {
            None
        };
        if let Some(status) = immediate {
            return Reply::new(request, status, task.sequence).map(Some);
        }
        self.pending = Some((
            slot,
            match request.action {
                Action::Start if task.handle.is_some() => Operation::LaunchInspect,
                Action::Start => Operation::LaunchStart,
                Action::Inspect => Operation::LaunchStatus,
            },
        ));
        Ok(None)
    }

    pub(crate) fn poll_launch(&mut self, request: Request) -> Result<Option<Reply>, Error> {
        let (slot, operation) = self.pending.ok_or(Error::Sequence)?;
        let task = *self.tasks.get(slot).ok_or(Error::Wire)?;
        if slot != request.app.index() || task.sequence != request.generation {
            return Err(Error::Sequence);
        }
        let status = match (request.action, operation) {
            (Action::Start, Operation::LaunchStart) if task.sequence == u32::MAX => {
                Some(Status::Exhausted)
            }
            (Action::Start, Operation::LaunchStart | Operation::LaunchInspect) => self.start_step(
                slot,
                operation == Operation::LaunchInspect,
                Operation::LaunchStart,
            )?,
            (Action::Inspect, Operation::LaunchStatus) => {
                let handle = task.handle.ok_or(Error::Sequence)?;
                Some(match self.calls.invoke(20, handle, 0) {
                    (0, value) => {
                        Completion::decode(value).map_err(|_| Error::Transport)?;
                        self.tasks[slot].complete = true;
                        Status::Terminal
                    }
                    (6, value) if !task.complete => live(value)?,
                    (5, 0) => Status::Denied,
                    _ => return Err(Error::Transport),
                })
            }
            _ => return Err(Error::Sequence),
        };
        let Some(status) = status else {
            return Ok(None);
        };
        let reply = Reply::new(request, status, self.tasks[slot].sequence)?;
        self.pending = None;
        Ok(Some(reply))
    }
}
