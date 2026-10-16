//! Advisory readiness waits own no user buffer and reserve no message.
use super::*;
use crate::scheduler::{CpuId, Scheduler, WakeReason};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Readiness {
    Readable,
    Writable,
}
impl Readiness {
    fn rights(self) -> Rights {
        match self {
            Self::Readable => Rights::RECEIVE,
            Self::Writable => Rights::SEND,
        }
    }
}

/// Kernel-only identity, never a user-supplied token or scheduler task number.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Ticket {
    caller: Caller,
    generation: u64,
}
impl Ticket {
    pub fn matches(self, id: TaskId, root: u64) -> bool {
        self.caller.id == id && self.caller.root == root
    }
    pub fn matches_image(self, id: TaskId, image: ImageAdmission) -> bool {
        self.caller == Caller::new(id, image)
    }
    fn scheduled(self) -> Result<crate::scheduler::TaskId, Error> {
        crate::scheduler::TaskId::new(self.caller.id.slot, self.caller.id.generation)
            .map_err(|_| Error::Identity)
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Admission {
    Ready,
    Complete(Status),
    Pending(Ticket),
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Armed,
    Parked,
    Notified(Status),
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Wait {
    ticket: Ticket,
    target: Target,
    state: State,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Target {
    Endpoint {
        handle: u64,
        object: Object,
        readiness: Readiness,
    },
    Request(u64),
}

fn reason(status: Status) -> Result<WakeReason, Error> {
    match status {
        Status::Ok => Ok(WakeReason::Signalled),
        Status::Cancelled => Ok(WakeReason::Cancelled),
        Status::Revoked => Ok(WakeReason::OwnerGone),
        Status::TimedOut => Ok(WakeReason::TimedOut),
        Status::ClockUnavailable => Ok(WakeReason::OwnerGone),
        _ => Err(Error::Denied),
    }
}
impl Space {
    fn ready(&self, object: Object, readiness: Readiness) -> bool {
        let e = self.objects[object.slot]
            .value
            .expect("resolved live endpoint");
        match readiness {
            Readiness::Readable => e.len != 0,
            Readiness::Writable => e.len < DEPTH,
        }
    }
    pub fn prepare_wait(
        &mut self,
        caller: Caller,
        handle: u64,
        readiness: Readiness,
    ) -> Result<Admission, Status> {
        let t = self.table(caller.id).map_err(|_| Status::Denied)?;
        if self.tables[t].caller != Some(caller) {
            return Err(Status::Denied);
        }
        let cap = self
            .resolve(t, handle, readiness.rights())
            .map_err(|_| Status::Denied)?;
        if self.tables[t].wait.is_some() {
            return Err(Status::Again);
        }
        if self.ready(cap.object, readiness) {
            return Ok(Admission::Ready);
        }
        self.arm_wait(
            caller,
            Target::Endpoint {
                handle,
                object: cap.object,
                readiness,
            },
        )
    }
    pub fn prepare_request_wait(
        &mut self,
        caller: Caller,
        handle: u64,
    ) -> Result<Admission, Status> {
        let status = self.request_status(caller, handle)?;
        let t = usize::from(caller.id.slot);
        if self.tables[t].wait.is_some() {
            return Err(Status::Again);
        }
        if let Some(status) = status {
            return Ok(Admission::Complete(status));
        }
        self.arm_wait(caller, Target::Request(handle))
    }
    fn arm_wait(&mut self, caller: Caller, target: Target) -> Result<Admission, Status> {
        let t = usize::from(caller.id.slot);
        let generation = self.tables[t]
            .wait_generation
            .checked_add(1)
            .ok_or(Status::Again)?;
        let ticket = Ticket { caller, generation };
        self.tables[t].wait_generation = generation;
        self.tables[t].wait = Some(Wait {
            ticket,
            target,
            state: State::Armed,
        });
        Ok(Admission::Pending(ticket))
    }
    fn waiting(&self, ticket: Ticket) -> Result<(usize, Wait), Error> {
        let t = self.table(ticket.caller.id)?;
        let wait = self.tables[t].wait.ok_or(Error::Identity)?;
        if self.tables[t].caller != Some(ticket.caller) || wait.ticket != ticket {
            return Err(Error::Identity);
        }
        Ok((t, wait))
    }
    /// The supervisor has quiesced the task, restored its kernel root and charged its slice.
    pub fn park_wait(
        &mut self,
        ticket: Ticket,
        scheduler: &mut Scheduler,
        cpu: CpuId,
    ) -> Result<(), Error> {
        let (t, mut wait) = self.waiting(ticket)?;
        if wait.state != State::Armed {
            return Err(Error::Denied);
        }
        scheduler
            .block_current_for_ipc(cpu, ticket.scheduled()?)
            .map_err(|_| Error::Denied)?;
        wait.state = State::Parked;
        self.tables[t].wait = Some(wait);
        Ok(())
    }
    fn notify(
        &mut self,
        t: usize,
        mut wait: Wait,
        status: Status,
        scheduler: &mut Scheduler,
        cpu: CpuId,
    ) -> Result<(), Error> {
        if wait.state != State::Parked {
            return Err(Error::Denied);
        }
        scheduler
            .wake_ipc_waiter(wait.ticket.scheduled()?, cpu, reason(status)?)
            .map_err(|_| Error::Denied)?;
        wait.state = State::Notified(status);
        self.tables[t].wait = Some(wait);
        Ok(())
    }
    /// Called after every park and kernel-side endpoint change. Each wake is atomic;
    /// earlier successful notifications remain committed if a later wake fails.
    pub fn poll_wakes(&mut self, scheduler: &mut Scheduler, cpu: CpuId) -> Result<u32, Error> {
        let mut count = 0;
        for t in 0..TASKS {
            let Some(wait) = self.tables[t].wait else {
                continue;
            };
            if wait.state != State::Parked {
                continue;
            }
            let status = match wait.target {
                Target::Endpoint {
                    handle,
                    object,
                    readiness,
                } => match self.resolve(t, handle, readiness.rights()) {
                    Ok(cap) if cap.object == object => {
                        if !self.ready(cap.object, readiness) {
                            continue;
                        }
                        Status::Ok
                    }
                    _ => Status::Revoked,
                },
                Target::Request(handle) => match self.request_status(wait.ticket.caller, handle) {
                    Ok(None) => continue,
                    Ok(Some(status)) => status,
                    Err(_) => Status::Revoked,
                },
            };
            self.notify(t, wait, status, scheduler, cpu)?;
            count += 1;
        }
        Ok(count)
    }
    /// Trusted supervisor cancellation; no user cancellation authority is implied.
    pub fn cancel_wait(
        &mut self,
        ticket: Ticket,
        scheduler: &mut Scheduler,
        cpu: CpuId,
    ) -> Result<(), Error> {
        let (t, wait) = self.waiting(ticket)?;
        self.notify(t, wait, Status::Cancelled, scheduler, cpu)
    }
    /// The adapter must be failure-atomic: validate before changing saved context.
    /// No fallible operation follows its successful context update.
    pub fn complete_wait(
        &mut self,
        ticket: Ticket,
        scheduler: &mut Scheduler,
        cpu: CpuId,
        resume: impl FnOnce(Status) -> Result<(), Error>,
    ) -> Result<Status, Error> {
        let (t, wait) = self.waiting(ticket)?;
        let State::Notified(status) = wait.state else {
            return Err(Error::Denied);
        };
        let mut staged = *scheduler;
        staged
            .consume_ipc_wake(cpu, ticket.scheduled()?, reason(status)?)
            .map_err(|_| Error::Denied)?;
        resume(status)?;
        *scheduler = staged;
        self.tables[t].wait = None;
        Ok(status)
    }
}
