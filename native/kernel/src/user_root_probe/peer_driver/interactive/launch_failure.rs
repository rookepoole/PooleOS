//! A rejected launch keeps its permit until its exact prepared image is gone.
use super::*;
use poolekernel::capability_ipc::{admission, launch};

#[cfg(feature = "development-launch-quota")]
#[must_use = "diagnostic pressure must be explicitly released"]
pub(super) struct Pressure {
    lease: launch::ProcessPressure,
    target: TaskId,
    plan: launch::Plan,
}

#[cfg(feature = "development-launch-quota")]
impl Pressure {
    pub(super) fn hold(
        space: &mut poolekernel::capability_ipc::Space,
        permit: &launch::Permit,
        target: TaskId,
    ) -> Result<Self, poolekernel::capability_ipc::Error> {
        let plan = space.validate_launch(permit)?;
        let lease = launch::ProcessPressure::hold(space, permit, target)?;
        Ok(Self {
            lease,
            target,
            plan,
        })
    }

    pub(super) fn release(
        &self,
        space: &mut poolekernel::capability_ipc::Space,
    ) -> Result<(), poolekernel::capability_ipc::Error> {
        self.lease.release(space)
    }

    pub(super) fn record(
        &self,
        event: &str,
        scheduler: &scheduler::Scheduler,
        serial: &mut Com1,
        debugcon: &mut DebugCon,
    ) {
        record(
            serial,
            debugcon,
            event,
            &[
                ("task", u64::from(self.plan.child_slot)),
                ("generation", u64::from(self.plan.sequence)),
                ("owner", u64::from(self.plan.owner.slot)),
                ("owner_generation", u64::from(self.plan.owner.generation)),
                ("target", u64::from(self.target.slot)),
                ("target_generation", u64::from(self.target.generation)),
                ("handle", self.lease.handle()),
                (
                    "owner_limit",
                    poolekernel::capability_ipc::process::PER_OWNER as u64,
                ),
                ("dispatches", u64::from(scheduler.summary().dispatch_count)),
            ],
        );
    }
}

#[must_use = "failed admission retains its permit until image reclamation"]
pub(super) struct Pending {
    permit: launch::Permit,
    plan: launch::Plan,
    outcome: task::Outcome,
    reason: u64,
}

impl Pending {
    pub(super) fn cancel(
        p: &mut Peer,
        permit: launch::Permit,
        plan: launch::Plan,
        error: admission::Error,
    ) -> Result<Self, ()> {
        if !error.recoverable_rejection()
            || p.id.slot != plan.child_slot
            || p.id.generation != plan.sequence
            || p.slot.state(p.id) != Ok(task::State::Prepared)
            || p.slot.runtime(p.id) != Ok(task::Runtime::default())
            || unsafe { arch::x86_64::user_ipc::with_waits(|s| s.validate_launch(&permit)) }
                .map_err(|_| ())?
                != plan
        {
            return Err(());
        }
        let writes = arch::x86_64::user_root_write_count();
        let outcome = p.slot.cancel_prepared(p.id).map_err(|_| ())?;
        if outcome.id != p.id
            || outcome.root != p.root
            || outcome.reason != task::Reason::Cancelled
            || outcome.syscalls != 0
            || arch::x86_64::user_root_write_count() != writes
        {
            return Err(());
        }
        Ok(Self {
            permit,
            plan,
            outcome,
            reason: match error {
                admission::Error::Ipc(poolekernel::capability_ipc::Error::Denied) => 1,
                admission::Error::Ipc(poolekernel::capability_ipc::Error::Quota) => 2,
                _ => return Err(()),
            },
        })
    }

    pub(super) fn rejected(
        &self,
        p: &Peer,
        pages: u64,
        scheduler: &scheduler::Scheduler,
        serial: &mut Com1,
        debugcon: &mut DebugCon,
    ) {
        record(
            serial,
            debugcon,
            "REJECT",
            &[
                ("task", u64::from(p.id.slot)),
                ("generation", u64::from(p.id.generation)),
                ("sequence", u64::from(self.plan.sequence)),
                ("root", p.root),
                ("owned_pages", pages),
                ("reason", self.reason),
                ("syscalls", self.outcome.syscalls),
                ("dispatches", u64::from(scheduler.summary().dispatch_count)),
            ],
        );
    }

    pub(super) fn complete(
        self,
        p: &Peer,
        job: &ManagedJob<'_>,
        scheduler: &scheduler::Scheduler,
        serial: &mut Com1,
        debugcon: &mut DebugCon,
    ) -> Result<(), ()> {
        if p.id != self.outcome.id
            || p.root != self.outcome.root
            || p.slot.state(p.id) != Err(task::Error::Missing)
        {
            return Err(());
        }
        let published = unsafe {
            arch::x86_64::user_ipc::with_waits(|s| {
                if job.is_closing() {
                    // Owner teardown has revoked the factory; never resurrect its reply.
                    if s.validate_launch(&self.permit).is_ok() {
                        return Err(poolekernel::capability_ipc::Error::Identity);
                    }
                    Ok(false)
                } else {
                    if s.validate_launch(&self.permit)? != self.plan {
                        return Err(poolekernel::capability_ipc::Error::Identity);
                    }
                    s.fail_launch(&self.permit)?;
                    Ok(true)
                }
            })
        }
        .map_err(|_| ())?;
        record(
            serial,
            debugcon,
            "FAILED",
            &[
                ("task", u64::from(p.id.slot)),
                ("generation", u64::from(p.id.generation)),
                ("sequence", u64::from(self.plan.sequence)),
                ("root", p.root),
                ("published", u64::from(published)),
                ("dispatches", u64::from(scheduler.summary().dispatch_count)),
            ],
        );
        Ok(())
    }
}
