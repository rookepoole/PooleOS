//! PKIPC1: original, allocation-free endpoint authority for one exclusive BSP.
//! Handles name entries in the authenticated task's table, never global objects.
#![forbid(unsafe_code)]

use crate::{
    scheduler_smp::TaskId,
    user_entry::{
        ImageAdmission,
        syscall::{Memory, Status},
    },
};

pub const CONTRACT_ID: &str = "PKIPC1";
pub const TASKS: usize = 4;
pub const CAPS: usize = 4;
pub const ENDPOINTS: usize = 4;
pub const DEPTH: usize = 4;
pub const MAX_BYTES: usize = 64;
const ENDPOINT_TAG: u64 = 1 << 16;
pub mod reply;
pub mod request;
pub mod wait;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Rights(u8);
impl Rights {
    pub const SEND: Self = Self(1);
    pub const RECEIVE: Self = Self(2);
    pub const ALL: Self = Self(15);
    const GRANT: Self = Self(4);
    const DESTROY: Self = Self(8);
    fn contains(self, other: Self) -> bool {
        other.0 != 0 && other.0 & !self.0 == 0
    }
}

/// Constructed only from a kernel-owned Run after authenticating its trap.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Caller {
    id: TaskId,
    root: u64,
    generation: u64,
}
impl Caller {
    pub(crate) fn new(id: TaskId, image: ImageAdmission) -> Self {
        Self {
            id,
            root: image.root_physical,
            generation: image.root_generation,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Identity,
    Denied,
    Quota,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Object {
    slot: usize,
    generation: u32,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Capability {
    object: Object,
    rights: Rights,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct CapSlot {
    generation: u32,
    value: Option<Capability>,
}
impl CapSlot {
    const EMPTY: Self = Self {
        generation: 0,
        value: None,
    };
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Table {
    last_task_generation: u32,
    caller: Option<Caller>,
    caps: [CapSlot; CAPS],
    wait_generation: u64,
    wait: Option<wait::Wait>,
    replies: [reply::Slot; CAPS],
    requests: [request::Slot; CAPS],
}
impl Table {
    const EMPTY: Self = Self {
        last_task_generation: 0,
        caller: None,
        caps: [CapSlot::EMPTY; CAPS],
        wait_generation: 0,
        wait: None,
        replies: [reply::Slot::EMPTY; CAPS],
        requests: [request::Slot::EMPTY; CAPS],
    };
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Message {
    bytes: [u8; MAX_BYTES],
    len: usize,
    sender: Option<Caller>,
    reply: Option<reply::Route>,
}
impl Message {
    const EMPTY: Self = Self {
        bytes: [0; MAX_BYTES],
        len: 0,
        sender: None,
        reply: None,
    };
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Endpoint {
    owner: TaskId,
    queue: [Message; DEPTH],
    head: usize,
    len: usize,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ObjectSlot {
    generation: u32,
    value: Option<Endpoint>,
}
impl ObjectSlot {
    const EMPTY: Self = Self {
        generation: 0,
        value: None,
    };
}

/// The caller must hold this owner exclusively across validation, copy and commit.
/// Creation, delegation and destruction remain trusted supervisor operations.
#[derive(Debug, Eq, PartialEq)]
pub struct Space {
    tables: [Table; TASKS],
    objects: [ObjectSlot; ENDPOINTS],
}
impl Default for Space {
    fn default() -> Self {
        Self::new()
    }
}
impl Space {
    pub const fn new() -> Self {
        Self {
            tables: [Table::EMPTY; TASKS],
            objects: [ObjectSlot::EMPTY; ENDPOINTS],
        }
    }
    pub fn attach(&mut self, id: TaskId, image: ImageAdmission) -> Result<(), Error> {
        let index = usize::from(id.slot);
        if index >= TASKS
            || id.generation == 0
            || image.root_physical == 0
            || image.root_physical & 4095 != 0
            || image.root_generation == 0
            || self.tables[index].caller.is_some()
            || id.generation <= self.tables[index].last_task_generation
            || self
                .tables
                .iter()
                .any(|t| t.caller.is_some_and(|c| c.root == image.root_physical))
        {
            return Err(Error::Identity);
        }
        let table = &mut self.tables[index];
        table.caller = Some(Caller::new(id, image));
        table.last_task_generation = id.generation;
        Ok(())
    }
    fn table(&self, id: TaskId) -> Result<usize, Error> {
        let i = usize::from(id.slot);
        if self
            .tables
            .get(i)
            .and_then(|t| t.caller)
            .is_some_and(|c| c.id == id)
        {
            Ok(i)
        } else {
            Err(Error::Identity)
        }
    }
    fn vacancy(&self, task: usize) -> Result<(usize, u32), Error> {
        self.tables[task]
            .caps
            .iter()
            .enumerate()
            .find_map(|(i, c)| {
                if c.value.is_none() {
                    c.generation.checked_add(1).map(|g| (i, g))
                } else {
                    None
                }
            })
            .ok_or(Error::Quota)
    }
    fn install(&mut self, task: usize, slot: usize, generation: u32, cap: Capability) -> u64 {
        self.tables[task].caps[slot] = CapSlot {
            generation,
            value: Some(cap),
        };
        (u64::from(generation) << 32) | ENDPOINT_TAG | (slot + 1) as u64
    }
    pub fn create_endpoint(&mut self, owner: TaskId) -> Result<u64, Error> {
        let t = self.table(owner)?;
        let (c, g) = self.vacancy(t)?;
        let (slot, generation) = self
            .objects
            .iter()
            .enumerate()
            .find_map(|(i, o)| {
                if o.value.is_none() {
                    o.generation.checked_add(1).map(|g| (i, g))
                } else {
                    None
                }
            })
            .ok_or(Error::Quota)?;
        self.objects[slot] = ObjectSlot {
            generation,
            value: Some(Endpoint {
                owner,
                queue: [Message::EMPTY; DEPTH],
                head: 0,
                len: 0,
            }),
        };
        Ok(self.install(
            t,
            c,
            g,
            Capability {
                object: Object { slot, generation },
                rights: Rights::ALL,
            },
        ))
    }
    fn resolve(&self, task: usize, handle: u64, need: Rights) -> Result<Capability, Error> {
        let raw_slot = (handle & 0xffff) as usize;
        if handle & 0xffff0000 != ENDPOINT_TAG || raw_slot == 0 || raw_slot > CAPS {
            return Err(Error::Denied);
        }
        let c = self.tables[task].caps[raw_slot - 1];
        let cap = c.value.ok_or(Error::Denied)?;
        if c.generation == 0
            || u64::from(c.generation) != handle >> 32
            || (need.0 != 0 && !cap.rights.contains(need))
        {
            return Err(Error::Denied);
        }
        let o = self.objects[cap.object.slot];
        if o.generation != cap.object.generation || o.value.is_none() {
            return Err(Error::Denied);
        }
        Ok(cap)
    }
    /// Trusted bootstrap delegation is attenuating; table exhaustion has no effects.
    pub fn derive(
        &mut self,
        owner: TaskId,
        handle: u64,
        to: TaskId,
        rights: Rights,
    ) -> Result<u64, Error> {
        let from = self.table(owner)?;
        let target = self.table(to)?;
        let cap = self.resolve(from, handle, Rights::GRANT)?;
        if !cap.rights.contains(rights) {
            return Err(Error::Denied);
        }
        let (slot, generation) = self.vacancy(target)?;
        Ok(self.install(target, slot, generation, Capability { rights, ..cap }))
    }
    pub fn close(&mut self, owner: TaskId, handle: u64) -> Result<(), Error> {
        let t = self.table(owner)?;
        self.resolve(t, handle, Rights(0))?;
        self.tables[t].caps[(handle & 0xffff) as usize - 1].value = None;
        self.prune_replies();
        Ok(())
    }
    fn remove_object(&mut self, object: Object) {
        self.revoke_requests(object);
        for table in &mut self.tables {
            for c in &mut table.caps {
                if c.value.is_some_and(|cap| cap.object == object) {
                    c.value = None;
                }
            }
        }
        // Overwrite queued payloads before dropping the object's live state.
        if let Some(e) = self.objects[object.slot].value.as_mut() {
            e.queue.fill(Message::EMPTY);
        }
        self.objects[object.slot].value = None;
    }
    pub fn destroy(&mut self, owner: TaskId, handle: u64) -> Result<(), Error> {
        let t = self.table(owner)?;
        let object = self.resolve(t, handle, Rights::DESTROY)?.object;
        self.remove_object(object);
        self.prune_replies();
        Ok(())
    }
    /// Called after task execution is stopped, before its root or identity is reused.
    pub fn detach(&mut self, owner: TaskId) -> Result<(), Error> {
        let t = self.table(owner)?;
        self.retire_requests(owner);
        for i in 0..ENDPOINTS {
            if self.objects[i].value.is_some_and(|e| e.owner == owner) {
                self.remove_object(Object {
                    slot: i,
                    generation: self.objects[i].generation,
                });
            }
        }
        for c in &mut self.tables[t].caps {
            c.value = None;
        }
        self.tables[t].caller = None;
        self.tables[t].wait = None;
        for r in &mut self.tables[t].replies {
            r.value = None;
        }
        self.prune_replies();
        Ok(())
    }
    /// Retirement hook: absence is idempotent, a different live generation is not.
    pub fn detach_if_attached(&mut self, owner: TaskId) -> Result<(), Error> {
        let table = self
            .tables
            .get(usize::from(owner.slot))
            .ok_or(Error::Identity)?;
        if table.caller.is_none() {
            return Ok(());
        }
        self.detach(owner)
    }
    pub fn is_empty(&self) -> bool {
        self.tables.iter().all(|t| {
            t.caller.is_none()
                && t.wait.is_none()
                && t.caps.iter().all(|c| c.value.is_none())
                && t.replies.iter().all(|r| r.value.is_none())
                && t.requests.iter().all(|r| !r.occupied())
        }) && self.objects.iter().all(|o| o.value.is_none())
    }
    /// Failed copy-in publishes nothing. Failed copy-out keeps the entire message
    /// queued and reports only the user-memory prefix written, never a dequeue.
    pub fn transfer(
        &mut self,
        caller: Caller,
        handle: u64,
        address: u64,
        bytes: usize,
        send: bool,
        memory: &mut impl Memory,
    ) -> (Status, u64) {
        use crate::virtual_memory::{USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START};
        if bytes == 0
            || bytes > MAX_BYTES
            || address < USER_WINDOW_START
            || address
                .checked_add(bytes as u64)
                .is_none_or(|end| end > USER_WINDOW_END_EXCLUSIVE)
        {
            return (Status::Arguments, 0);
        }
        let Ok(t) = self.table(caller.id) else {
            return (Status::Denied, 0);
        };
        if self.tables[t].caller != Some(caller) {
            return (Status::Denied, 0);
        }
        let Ok(cap) = self.resolve(t, handle, if send { Rights::SEND } else { Rights::RECEIVE })
        else {
            return (Status::Denied, 0);
        };
        let e = self.objects[cap.object.slot]
            .value
            .as_mut()
            .expect("resolved live endpoint");
        if send {
            if e.len == DEPTH {
                return (Status::Again, 0);
            }
            let mut message = Message::EMPTY;
            message.len = bytes;
            message.sender = Some(caller);
            for (i, byte) in message.bytes[..bytes].iter_mut().enumerate() {
                let Ok(value) = memory.read(address + i as u64) else {
                    return (Status::Fault, 0);
                };
                *byte = value;
            }
            e.queue[(e.head + e.len) % DEPTH] = message;
            e.len += 1;
            (Status::Ok, bytes as u64)
        } else {
            if e.len == 0 {
                return (Status::Again, 0);
            }
            let message = e.queue[e.head];
            if message.reply.is_some() {
                return (Status::Denied, 0);
            }
            if bytes < message.len {
                return (Status::TooSmall, message.len as u64);
            }
            for (i, byte) in message.bytes[..message.len].iter().enumerate() {
                if memory.write(address + i as u64, *byte).is_err() {
                    return (Status::Fault, i as u64);
                }
            }
            e.queue[e.head] = Message::EMPTY;
            e.head = (e.head + 1) % DEPTH;
            e.len -= 1;
            (Status::Ok, message.len as u64)
        }
    }
}

#[cfg(test)]
mod tests;
