//! PKPORT1: one exclusive polled COM2 lease, not arbitrary x86 I/O authority.
use super::*;

const TAG: u64 = 4 << 16;
pub const BASE: u16 = 0x2f8;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Lease {
    generation: u32,
    pub(super) owner: Option<Caller>,
}
impl Lease {
    pub(super) const EMPTY: Self = Self {
        generation: 0,
        owner: None,
    };
    fn handle(self) -> u64 {
        (u64::from(self.generation) << 32) | TAG | 1
    }
}

/// Trusted adapter; the resource owner validates every address and value first.
pub trait BytePorts {
    fn read(&mut self, port: u16) -> u8;
    fn write(&mut self, port: u16, value: u8);
}

impl Space {
    /// Trusted four-image launch: two separate endpoint pairs, one device owner.
    /// No caller may dispatch until this transaction and hardware quiescence pass.
    pub fn admit_console_session(
        &mut self,
        scheduler: &mut crate::scheduler::Scheduler,
        members: &[admission::Member; 4],
    ) -> Result<admission::Admitted, admission::Error> {
        use admission::Step;
        self.admit(
            scheduler,
            members,
            &[
                Step::Endpoint { member: 0 },
                Step::Endpoint { member: 1 },
                Step::Grant {
                    endpoint: 1,
                    target: members[0].id,
                    rights: Rights::SEND,
                },
                Step::Grant {
                    endpoint: 0,
                    target: members[1].id,
                    rights: Rights::SEND,
                },
                Step::Endpoint { member: 2 },
                Step::Endpoint { member: 3 },
                Step::Grant {
                    endpoint: 5,
                    target: members[2].id,
                    rights: Rights::SEND,
                },
                Step::Grant {
                    endpoint: 4,
                    target: members[3].id,
                    rights: Rights::SEND,
                },
                Step::Console { member: 2 },
            ],
        )
    }

    /// Trusted prepared-task admission only. No hardware operation occurs here.
    pub fn grant_console(&mut self, id: TaskId) -> Result<u64, Error> {
        let t = self.table(id)?;
        if self.console.owner.is_some() {
            return Err(Error::Quota);
        }
        let generation = self.console.generation.checked_add(1).ok_or(Error::Quota)?;
        self.console = Lease {
            generation,
            owner: self.tables[t].caller,
        };
        Ok(self.console.handle())
    }

    pub fn owns_console(&self, id: TaskId) -> bool {
        self.console.owner.is_some_and(|owner| owner.id == id)
    }

    pub fn console_byte(
        &mut self,
        caller: Caller,
        handle: u64,
        offset: u64,
        value: Option<u64>,
        ports: &mut impl BytePorts,
    ) -> (Status, u64) {
        if offset > 7 || value.is_some_and(|v| v > u8::MAX as u64) {
            return (Status::Arguments, 0);
        }
        let Ok(t) = self.table(caller.id) else {
            return (Status::Denied, 0);
        };
        if self.tables[t].caller != Some(caller)
            || self.console.owner != Some(caller)
            || self.console.generation == 0
            || handle != self.console.handle()
        {
            return (Status::Denied, 0);
        }
        let port = BASE + offset as u16;
        if let Some(byte) = value {
            let allowed = match offset {
                0 | 7 => true,
                1 => byte == 0,
                2 => matches!(byte, 0 | 1 | 7),
                3 => matches!(byte, 3 | 0x83),
                4 => matches!(byte, 0 | 3),
                _ => false,
            };
            if !allowed {
                return (Status::Denied, 0);
            }
            ports.write(port, byte as u8);
            (Status::Ok, 0)
        } else {
            (Status::Ok, u64::from(ports.read(port)))
        }
    }
}

#[cfg(test)]
mod session_tests;
#[cfg(test)]
mod tests;
