//! Failure-atomic, trusted BSP bootstrap of prepared task identities and authority.
//! Image ownership stays with the caller; this module never switches or frees roots.
use super::*;
use crate::scheduler::{self, CpuId, Scheduler};

pub const CONTRACT_ID: &str = "PKADMIT1";
pub const MAX_STEPS: usize = TASKS * CAPS;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Member {
    pub id: TaskId,
    pub image: ImageAdmission,
    pub priority: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Step {
    Endpoint {
        member: u8,
    },
    Inherit {
        source: TaskId,
        handle: u64,
        member: u8,
        rights: Rights,
    },
    /// Only an earlier Endpoint step can be exported to an existing task.
    Grant {
        endpoint: u8,
        target: TaskId,
        rights: Rights,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Plan,
    Scheduler(scheduler::Error),
    Ipc(super::Error),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Admitted {
    pub handles: [u64; MAX_STEPS],
    pub count: usize,
}

impl Space {
    /// Exclusive BSP/IF0 supervisor operation, not a user authority API. Members
    /// must name caller-owned, never-dispatched prepared images. On error their
    /// original owner must retire them; attached task generations stay consumed.
    /// No callback or hardware effect occurs while partial authority is installed.
    pub fn admit(
        &mut self,
        scheduler: &mut Scheduler,
        members: &[Member],
        steps: &[Step],
    ) -> Result<Admitted, Error> {
        if members.is_empty() || members.len() > TASKS || steps.len() > MAX_STEPS {
            return Err(Error::Plan);
        }
        scheduler.validate().map_err(Error::Scheduler)?;
        // Scheduler contains no device/linear owners. Keep its original queues,
        // counters and task state untouched until the entire authority plan passes.
        let mut ready = *scheduler;
        let cpu = CpuId::new(0).map_err(Error::Scheduler)?;
        for member in members {
            let id = ready
                .create_task(member.id.slot, member.id.generation, member.priority, 1)
                .map_err(Error::Scheduler)?;
            ready.activate(id, cpu).map_err(Error::Scheduler)?;
        }
        let mut attached = 0;
        let mut result = Admitted {
            handles: [0; MAX_STEPS],
            count: steps.len(),
        };
        let installed = (|| {
            for member in members {
                self.attach(member.id, member.image).map_err(Error::Ipc)?;
                attached += 1;
            }
            for (index, step) in steps.iter().enumerate() {
                result.handles[index] = match *step {
                    Step::Endpoint { member } => {
                        let id = members.get(usize::from(member)).ok_or(Error::Plan)?.id;
                        self.create_endpoint(id).map_err(Error::Ipc)?
                    }
                    Step::Inherit {
                        source,
                        handle,
                        member,
                        rights,
                    } => {
                        let target = members.get(usize::from(member)).ok_or(Error::Plan)?.id;
                        self.derive(source, handle, target, rights)
                            .map_err(Error::Ipc)?
                    }
                    Step::Grant {
                        endpoint,
                        target,
                        rights,
                    } => {
                        let from = usize::from(endpoint);
                        if from >= index {
                            return Err(Error::Plan);
                        }
                        let Step::Endpoint { member } = steps[from] else {
                            return Err(Error::Plan);
                        };
                        let owner = members[usize::from(member)].id;
                        self.derive(owner, result.handles[from], target, rights)
                            .map_err(Error::Ipc)?
                    }
                };
            }
            Ok(())
        })();
        if let Err(error) = installed {
            // Only newly attached tables and their new endpoints may be removed.
            // Exported new endpoints are revoked everywhere; inherited grants
            // disappear with their new recipient, not their existing source.
            for member in members[..attached].iter().rev() {
                self.detach_table(usize::from(member.id.slot), member.id);
            }
            return Err(error);
        }
        *scheduler = ready;
        Ok(result)
    }
}
