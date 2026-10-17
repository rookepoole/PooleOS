//! PPROC1: bounded, generation-bound process control on the exclusive BSP.
use super::*;

pub const CONTRACT_ID: &str = "PPROC1";
pub const COMPLETION_CONTRACT_ID: &str = "PCOMP1";
pub const LEASES: usize = 4;
pub const PER_OWNER: usize = 2;
const TAG: u64 = 5 << 16;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Rights {
    Inspect,
    InspectTerminate,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Attached,
    Pending,
    Claimed,
    Revoked,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Lease {
    owner: Caller,
    target: Caller,
    rights: Rights,
    state: State,
    completion: Option<u64>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Slot {
    generation: u32,
    pub(super) value: Option<Lease>,
}
impl Slot {
    pub(super) const EMPTY: Self = Self {
        generation: 0,
        value: None,
    };
}

/// Not clonable or constructible outside this module. Validate immediately before
/// touching the stopped task. Dropping it leaves the request claimed, not retried.
#[derive(Debug, Eq, PartialEq)]
pub struct StopPermit {
    slot: usize,
    generation: u32,
    owner: Caller,
    target: Caller,
}

impl Space {
    /// Read-only selection within existing Inspect authority, never a task-ID grant.
    /// Revoked/0 means the watched slot has advanced, not physical reclamation of
    /// the queried generation. Exact generations retain PCOMP1 completion semantics.
    pub fn observe_process(&self, caller: Caller, target: TaskId) -> (Status, u64) {
        if !self.process_attached(caller) || TaskId::new(target.slot, target.generation).is_err() {
            return (Status::Denied, 0);
        }
        let mut found = None;
        for (i, p) in self.processes.iter().enumerate() {
            if let Some(l) = p.value {
                if l.owner == caller
                    && l.rights == Rights::Inspect
                    && l.target.id.slot == target.slot
                {
                    if found.is_some() {
                        return (Status::Denied, 0);
                    }
                    found = Some((i, p.generation, l.target.id.generation));
                }
            }
        }
        match found {
            Some((i, generation, current)) if target.generation == current => self
                .process_completion(caller, (u64::from(generation) << 32) | TAG | (i + 1) as u64),
            Some((_, _, current)) if target.generation < current => (Status::Revoked, 0),
            _ => (Status::Denied, 0),
        }
    }

    /// Preflight the observer slot before admit_launch allocates its one parent
    /// process lease. This plan stays private to one exclusive launch operation.
    pub(super) fn prepare_observer(
        &self,
        owner: TaskId,
        parent: TaskId,
        target: TaskId,
        image: ImageAdmission,
    ) -> Result<ObserverGrant, Error> {
        if owner == parent || owner.slot == target.slot {
            return Err(Error::Denied);
        }
        let owner = self.tables[self.table(owner)?]
            .caller
            .ok_or(Error::Identity)?;
        let mut previous = None;
        let mut owned = 0;
        for (i, p) in self.processes.iter().enumerate() {
            if let Some(l) = p.value.filter(|l| l.owner == owner) {
                owned += 1;
                if l.target.id.slot == target.slot {
                    if previous.is_some()
                        || l.rights != Rights::Inspect
                        || l.target.id.generation >= target.generation
                        || l.state != State::Revoked
                        || l.completion.is_none()
                        || self.process_attached(l.target)
                    {
                        return Err(Error::Denied);
                    }
                    previous = Some(i);
                }
            }
        }
        let slot = if let Some(i) = previous {
            i
        } else {
            if owned >= PER_OWNER {
                return Err(Error::Quota);
            }
            // The first usable vacancy belongs to the launch parent's grant.
            self.processes
                .iter()
                .enumerate()
                .filter(|(_, p)| p.value.is_none() && p.generation < u32::MAX)
                .nth(1)
                .map(|(i, _)| i)
                .ok_or(Error::Quota)?
        };
        let before = self.processes[slot];
        let generation = before.generation.checked_add(1).ok_or(Error::Quota)?;
        Ok(ObserverGrant {
            slot,
            before,
            after: Slot {
                generation,
                value: Some(Lease {
                    owner,
                    target: Caller::new(target, image),
                    rights: Rights::Inspect,
                    state: State::Attached,
                    completion: None,
                }),
            },
        })
    }

    pub(super) fn commit_observer(&mut self, grant: ObserverGrant) {
        // admit_launch rejects extra Process steps, so only its first vacancy
        // can change. A retained old observer or second vacancy remains untouched.
        assert_eq!(self.processes[grant.slot], grant.before);
        self.processes[grant.slot] = grant.after;
    }

    fn process_attached(&self, caller: Caller) -> bool {
        self.table(caller.id)
            .is_ok_and(|i| self.tables[i].caller == Some(caller))
    }

    /// Trusted admission only. A raw task ID is never accepted from a syscall.
    pub fn grant_process(
        &mut self,
        owner: TaskId,
        target: TaskId,
        rights: Rights,
    ) -> Result<u64, Error> {
        let from = self.table(owner)?;
        let to = self.table(target)?;
        if owner == target {
            return Err(Error::Denied);
        }
        let owner = self.tables[from].caller.ok_or(Error::Identity)?;
        let target = self.tables[to].caller.ok_or(Error::Identity)?;
        if self
            .processes
            .iter()
            .filter(|p| p.value.is_some_and(|l| l.owner == owner))
            .count()
            >= PER_OWNER
        {
            return Err(Error::Quota);
        }
        let (slot, generation) = self
            .processes
            .iter()
            .enumerate()
            .find_map(|(i, p)| {
                if p.value.is_none() {
                    p.generation.checked_add(1).map(|g| (i, g))
                } else {
                    None
                }
            })
            .ok_or(Error::Quota)?;
        self.processes[slot] = Slot {
            generation,
            value: Some(Lease {
                owner,
                target,
                rights,
                state: State::Attached,
                completion: None,
            }),
        };
        Ok((u64::from(generation) << 32) | TAG | (slot + 1) as u64)
    }

    fn process_slot(&self, caller: Caller, handle: u64) -> Result<usize, Error> {
        let raw = (handle & 0xffff) as usize;
        if !self.process_attached(caller) || handle & 0xffff0000 != TAG || raw == 0 || raw > LEASES
        {
            return Err(Error::Denied);
        }
        let slot = self.processes[raw - 1];
        if slot.generation == 0
            || u64::from(slot.generation) != handle >> 32
            || slot.value.is_none_or(|l| l.owner != caller)
        {
            return Err(Error::Denied);
        }
        Ok(raw - 1)
    }

    /// Ok/1 means the exact authority attachment still exists, not "runnable".
    /// Again/0 means a stop is pending or claimed, never that memory was freed.
    pub fn process_operation(
        &mut self,
        caller: Caller,
        handle: u64,
        terminate: bool,
    ) -> (Status, u64) {
        let Ok(i) = self.process_slot(caller, handle) else {
            return (Status::Denied, 0);
        };
        let lease = self.processes[i].value.expect("resolved lease");
        if terminate && lease.rights != Rights::InspectTerminate {
            return (Status::Denied, 0);
        }
        if lease.state == State::Revoked || !self.process_attached(lease.target) {
            return (Status::Revoked, 0);
        }
        if !terminate {
            return (Status::Ok, 1);
        }
        if lease.state == State::Attached {
            self.processes[i]
                .value
                .as_mut()
                .expect("resolved lease")
                .state = State::Pending;
        }
        (Status::Again, 0)
    }

    /// Trusted quiescent dispatcher only, after root restoration and accounting.
    pub fn claim_process_stop(&mut self) -> Option<StopPermit> {
        for i in 0..LEASES {
            let Some(l) = self.processes[i].value else {
                continue;
            };
            if l.state != State::Pending
                || !self.process_attached(l.owner)
                || !self.process_attached(l.target)
            {
                continue;
            }
            self.processes[i]
                .value
                .as_mut()
                .expect("pending lease")
                .state = State::Claimed;
            return Some(StopPermit {
                slot: i,
                generation: self.processes[i].generation,
                owner: l.owner,
                target: l.target,
            });
        }
        None
    }

    /// Revalidation closes revoke/death/reuse between claim and application.
    /// Failed cleanup may retain this permit; it cannot authorize a new lifetime.
    pub fn validate_process_stop(&self, permit: &StopPermit) -> Result<TaskId, Error> {
        let p = self.processes.get(permit.slot).ok_or(Error::Denied)?;
        let l = p.value.ok_or(Error::Denied)?;
        if p.generation != permit.generation
            || l.owner != permit.owner
            || l.target != permit.target
            || l.rights != Rights::InspectTerminate
            || l.state != State::Claimed
            || !self.process_attached(l.owner)
            || !self.process_attached(l.target)
        {
            return Err(Error::Denied);
        }
        Ok(l.target.id)
    }

    pub fn revoke_process(&mut self, owner: TaskId, handle: u64) -> Result<(), Error> {
        let caller = self.tables[self.table(owner)?]
            .caller
            .ok_or(Error::Identity)?;
        let i = self.process_slot(caller, handle)?;
        self.processes[i].value = None;
        Ok(())
    }

    /// PCOMP1: Again/1..4 = attached, pending, claimed, detached. None of these
    /// states proves runnability or reclamation. Ok carries a terminal reason.
    pub fn process_completion(&self, caller: Caller, handle: u64) -> (Status, u64) {
        let Ok(i) = self.process_slot(caller, handle) else {
            return (Status::Denied, 0);
        };
        let lease = self.processes[i].value.expect("resolved lease");
        if let Some(completion) = lease.completion {
            return (Status::Ok, completion);
        }
        let state = if !self.process_attached(lease.target) {
            4
        } else {
            match lease.state {
                State::Attached => 1,
                State::Pending => 2,
                State::Claimed => 3,
                State::Revoked => 4,
            }
        };
        (Status::Again, state)
    }

    /// Trusted quiescent dispatcher only, after successful physical cleanup and
    /// scheduler teardown. Detachment alone must never call this function.
    /// This checks the observed outcome and exact retained target identities;
    /// cleanup ownership remains the dispatcher's obligation, not a user claim.
    pub fn publish_process_completion(
        &mut self,
        outcome: crate::user_entry::task::Outcome,
        scheduler: &crate::scheduler::Scheduler,
    ) -> Result<usize, Error> {
        use crate::user_entry::task::Reason;
        let slot = usize::from(outcome.id.slot);
        if slot >= TASKS
            || self.tables[slot].caller.is_some()
            || outcome.root == 0
            || outcome.root & 4095 != 0
            || TaskId::new(outcome.id.slot, outcome.id.generation).is_err()
            || outcome.validate(outcome.id, outcome.root).is_err()
        {
            return Err(Error::Identity);
        }
        let id = crate::scheduler::TaskId::new(outcome.id.slot, outcome.id.generation)
            .map_err(|_| Error::Identity)?;
        if !scheduler
            .task_snapshot(id)
            .is_ok_and(|s| s.state == crate::scheduler::TaskState::Dead)
        {
            return Err(Error::Denied);
        }
        let value = match outcome.reason {
            Reason::Exit(code) => (1 << 32) | u64::from(code),
            Reason::Fault(fault) => (2 << 32) | fault.vector,
            Reason::InvalidReturn { violation, .. } => (3 << 32) | violation as u64,
            Reason::Cancelled => 4 << 32,
            Reason::CallLimit => 5 << 32,
            Reason::CallCounterExhausted => 6 << 32,
            Reason::Watchdog => 7 << 32,
        };
        // Validate the whole fan-out before publishing to any inspector.
        for lease in self.processes.iter().filter_map(|p| p.value) {
            if lease.target.id == outcome.id
                && (lease.target.root != outcome.root
                    || lease.state != State::Revoked
                    || lease.completion.is_some())
            {
                return Err(Error::Denied);
            }
        }
        let mut published = 0;
        for lease in self.processes.iter_mut().filter_map(|p| p.value.as_mut()) {
            if lease.target.id == outcome.id {
                lease.completion = Some(value);
                published += 1;
            }
        }
        Ok(published)
    }

    pub(super) fn retire_processes(&mut self, task: TaskId) {
        for p in &mut self.processes {
            if let Some(l) = &mut p.value {
                if l.owner.id == task {
                    p.value = None;
                } else if l.target.id == task {
                    l.state = State::Revoked;
                }
            }
        }
    }
}

pub(super) struct ObserverGrant {
    slot: usize,
    before: Slot,
    after: Slot,
}

#[cfg(test)]
mod tests;

#[cfg(test)]
mod completion_tests;

#[cfg(test)]
mod observer_tests;
