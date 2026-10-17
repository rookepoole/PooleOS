//! PLAUNCH1: trusted program/slot grants; user policy requests numbered launches.
use super::*;
use crate::scheduler::Scheduler;
use admission::{Member, Step};

pub const CONTRACT_ID: &str = "PLAUNCH1";
pub const LEASES: usize = 2;
const TAG: u64 = 6 << 16;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Idle,
    Pending,
    Claimed,
    Complete(u64),
    Failed,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Lease {
    owner: Caller,
    program: u16,
    child_slot: u8,
    sequence: u32,
    state: State,
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

#[derive(Debug, Eq, PartialEq)]
pub struct Permit {
    slot: usize,
    generation: u32,
    lease: Lease,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Plan {
    pub owner: TaskId,
    pub program: u16,
    pub child_slot: u8,
    pub sequence: u32,
}

impl Space {
    /// The trusted catalogue maps nonzero program IDs to fixed code/arguments.
    /// A lease reserves one empty slot. It does not allocate an image or promise
    /// memory availability. No user pointer, code ID or task ID grants authority.
    pub fn grant_launch(
        &mut self,
        owner: TaskId,
        program: u16,
        child_slot: u8,
    ) -> Result<u64, Error> {
        let owner = self.tables[self.table(owner)?]
            .caller
            .ok_or(Error::Identity)?;
        if program == 0
            || usize::from(child_slot) >= TASKS
            || self.tables[usize::from(child_slot)].caller.is_some()
            || self
                .launches
                .iter()
                .any(|s| s.value.is_some_and(|l| l.child_slot == child_slot))
        {
            return Err(Error::Denied);
        }
        let (slot, generation) = self
            .launches
            .iter()
            .enumerate()
            .find_map(|(i, s)| {
                if s.value.is_none() {
                    s.generation.checked_add(1).map(|g| (i, g))
                } else {
                    None
                }
            })
            .ok_or(Error::Quota)?;
        self.launches[slot] = Slot {
            generation,
            value: Some(Lease {
                owner,
                program,
                child_slot,
                sequence: 0,
                state: State::Idle,
            }),
        };
        Ok((u64::from(generation) << 32) | TAG | (slot + 1) as u64)
    }

    fn launch_slot(&self, caller: Caller, handle: u64) -> Result<usize, Error> {
        let raw = (handle & 0xffff) as usize;
        if self.table(caller.id).is_err()
            || self.tables[usize::from(caller.id.slot)].caller != Some(caller)
            || handle & 0xffff0000 != TAG
            || raw == 0
            || raw > LEASES
        {
            return Err(Error::Denied);
        }
        let s = self.launches[raw - 1];
        if s.generation == 0
            || u64::from(s.generation) != handle >> 32
            || s.value.is_none_or(|l| l.owner != caller)
        {
            return Err(Error::Denied);
        }
        Ok(raw - 1)
    }

    /// Same sequence polls one operation forever, including after child death.
    /// Only the exact next nonzero sequence starts a new operation. Superseding
    /// a completed operation invalidates its old, already-revoked process handle.
    pub fn request_launch(&mut self, caller: Caller, handle: u64, sequence: u32) -> (Status, u64) {
        let Ok(i) = self.launch_slot(caller, handle) else {
            return (Status::Denied, 0);
        };
        if sequence == 0 {
            return (Status::Arguments, 0);
        }
        let l = self.launches[i].value.expect("resolved launch");
        if sequence == l.sequence {
            return match l.state {
                State::Complete(h) => (Status::Ok, h),
                State::Failed => (Status::Cancelled, 0),
                _ => (Status::Again, 0),
            };
        }
        if l.sequence.checked_add(1) != Some(sequence) {
            return (Status::Arguments, 0);
        }
        if !matches!(l.state, State::Idle | State::Complete(_) | State::Failed)
            || self.tables[usize::from(l.child_slot)].caller.is_some()
        {
            return (Status::Again, 0);
        }
        if let State::Complete(h) = l.state {
            match self.process_completion(caller, h).0 {
                Status::Ok => {}
                Status::Again => return (Status::Again, 0),
                _ => return (Status::Denied, 0),
            }
            self.revoke_process(caller.id, h)
                .expect("revoked launch child");
        }
        self.launches[i].value = Some(Lease {
            sequence,
            state: State::Pending,
            ..l
        });
        (Status::Again, 0)
    }

    /// Exclusive, quiescent dispatcher only. Dropped permits stay claimed.
    pub fn claim_launch(&mut self) -> Option<Permit> {
        for i in 0..LEASES {
            let Some(l) = self.launches[i].value else {
                continue;
            };
            if l.state == State::Pending
                && self.tables[usize::from(l.child_slot)].caller.is_none()
                && self.table(l.owner.id).is_ok()
                && self.tables[usize::from(l.owner.id.slot)].caller == Some(l.owner)
            {
                let lease = Lease {
                    state: State::Claimed,
                    ..l
                };
                self.launches[i].value = Some(lease);
                return Some(Permit {
                    slot: i,
                    generation: self.launches[i].generation,
                    lease,
                });
            }
        }
        None
    }

    pub fn validate_launch(&self, permit: &Permit) -> Result<Plan, Error> {
        let s = self.launches.get(permit.slot).ok_or(Error::Denied)?;
        let l = s.value.ok_or(Error::Denied)?;
        if s.generation != permit.generation
            || l != permit.lease
            || l.state != State::Claimed
            || self.table(l.owner.id).is_err()
            || self.tables[usize::from(l.owner.id.slot)].caller != Some(l.owner)
            || self.tables[usize::from(l.child_slot)].caller.is_some()
        {
            return Err(Error::Denied);
        }
        Ok(Plan {
            owner: l.owner.id,
            program: l.program,
            child_slot: l.child_slot,
            sequence: l.sequence,
        })
    }

    /// Admit a prepared image, its IPC grants, its parent's process handle and
    /// the launch completion in one exclusive operation, with no dispatch window.
    /// Caller must match the catalogue and prove the previous Slot fully empty.
    /// An error leaves the prepared image owned by the caller, never reclaimed.
    pub fn admit_launch(
        &mut self,
        permit: &Permit,
        scheduler: &mut Scheduler,
        member: Member,
        steps: &[Step],
    ) -> Result<admission::Admitted, admission::Error> {
        let plan = self
            .validate_launch(permit)
            .map_err(admission::Error::Ipc)?;
        if member.id.slot != plan.child_slot || steps.len() >= admission::MAX_STEPS {
            return Err(admission::Error::Plan);
        }
        // Extra process grants are not part of this bounded launch contract.
        if steps.iter().any(|s| matches!(s, Step::Process { .. })) {
            return Err(admission::Error::Plan);
        }
        let mut all = [Step::Endpoint { member: 0 }; admission::MAX_STEPS];
        all[..steps.len()].copy_from_slice(steps);
        all[steps.len()] = Step::Process {
            member: 0,
            owner: plan.owner,
            rights: process::Rights::InspectTerminate,
        };
        let admitted = self.admit(scheduler, &[member], &all[..steps.len() + 1])?;
        self.launches[permit.slot]
            .value
            .as_mut()
            .expect("exclusive launch")
            .state = State::Complete(admitted.handles[steps.len()]);
        Ok(admitted)
    }

    /// Trusted read-only observer admission; not a user delegation operation.
    /// A completed prior observer is replaced only after admission succeeds.
    /// No callback, allocation or dispatch occurs between admission and commit.
    pub fn admit_observed_launch(
        &mut self,
        permit: &Permit,
        scheduler: &mut Scheduler,
        member: Member,
        steps: &[Step],
        observer: TaskId,
    ) -> Result<admission::Admitted, admission::Error> {
        let plan = self
            .validate_launch(permit)
            .map_err(admission::Error::Ipc)?;
        let grant = self
            .prepare_observer(observer, plan.owner, member.id, member.image)
            .map_err(admission::Error::Ipc)?;
        let admitted = self.admit_launch(permit, scheduler, member, steps)?;
        self.commit_observer(grant);
        Ok(admitted)
    }

    /// Trusted failure completion only after construction has been rolled back
    /// or no image was allocated. Retained cleanup must not call this method.
    pub fn fail_launch(&mut self, permit: &Permit) -> Result<(), Error> {
        self.validate_launch(permit)?;
        self.launches[permit.slot]
            .value
            .as_mut()
            .expect("validated launch")
            .state = State::Failed;
        Ok(())
    }

    pub fn revoke_launch(&mut self, owner: TaskId, handle: u64) -> Result<(), Error> {
        let caller = self.tables[self.table(owner)?]
            .caller
            .ok_or(Error::Identity)?;
        let i = self.launch_slot(caller, handle)?;
        self.launches[i].value = None;
        Ok(())
    }

    pub(super) fn retire_launches(&mut self, owner: TaskId) {
        for s in &mut self.launches {
            if s.value.is_some_and(|l| l.owner.id == owner) {
                s.value = None;
            }
        }
    }
}

#[cfg(test)]
mod tests;
