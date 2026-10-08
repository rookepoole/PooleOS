//! Caller-owned completion records. Outcomes never depend on endpoint queue capacity.
use super::*;
use crate::virtual_memory::{USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START};

const TAG: u64 = 3 << 16;
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Operation {
    Begin,
    Take,
    Cancel,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Key {
    caller: Caller,
    slot: usize,
    generation: u32,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Request {
    endpoint: Object,
    receiver: Option<Caller>,
    completion: Option<(Status, Message)>,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Slot {
    pub(super) generation: u32,
    value: Option<Request>,
}
impl Slot {
    pub(super) const EMPTY: Self = Self {
        generation: 0,
        value: None,
    };
    pub(super) fn occupied(self) -> bool {
        self.value.is_some()
    }
}

impl Space {
    fn request_key(&self, caller: Caller, handle: u64) -> Result<Key, Status> {
        let t = self.table(caller.id).map_err(|_| Status::Denied)?;
        let slot = (handle & 0xffff) as usize;
        if self.tables[t].caller != Some(caller)
            || handle & 0xffff0000 != TAG
            || slot == 0
            || slot > CAPS
        {
            return Err(Status::Denied);
        }
        let r = self.tables[t].requests[slot - 1];
        if r.generation == 0 || u64::from(r.generation) != handle >> 32 || r.value.is_none() {
            return Err(Status::Denied);
        }
        Ok(Key {
            caller,
            slot: slot - 1,
            generation: r.generation,
        })
    }
    fn request_record(&self, key: Key) -> Option<Request> {
        let t = self.table(key.caller.id).ok()?;
        let r = self.tables[t].requests[key.slot];
        if self.tables[t].caller != Some(key.caller) || r.generation != key.generation {
            return None;
        }
        r.value
    }
    pub(super) fn pending_request(&self, key: Key) -> bool {
        self.request_record(key)
            .is_some_and(|r| r.completion.is_none())
    }
    pub(super) fn claim_request(&mut self, key: Key, receiver: Caller) {
        let r = self.tables[usize::from(key.caller.id.slot)].requests[key.slot]
            .value
            .as_mut()
            .unwrap();
        debug_assert!(r.completion.is_none() && r.receiver.is_none());
        r.receiver = Some(receiver);
    }
    pub(super) fn finish_request(&mut self, key: Key, status: Status, message: Message) {
        let r = self.tables[usize::from(key.caller.id.slot)].requests[key.slot]
            .value
            .as_mut()
            .unwrap();
        debug_assert!(r.completion.is_none());
        r.completion = Some((status, message));
    }
    pub(super) fn revoke_requests(&mut self, endpoint: Object) {
        for table in &mut self.tables {
            for slot in &mut table.requests {
                if let Some(r) = slot.value.as_mut() {
                    if r.endpoint == endpoint && r.completion.is_none() {
                        r.completion = Some((Status::Revoked, Message::EMPTY));
                    }
                }
            }
        }
    }
    pub(super) fn retire_requests(&mut self, owner: TaskId) {
        for (t, table) in self.tables.iter_mut().enumerate() {
            for slot in &mut table.requests {
                if t == usize::from(owner.slot) {
                    slot.value = None;
                    continue;
                }
                if let Some(r) = slot.value.as_mut() {
                    if r.receiver.is_some_and(|c| c.id == owner) && r.completion.is_none() {
                        r.completion = Some((Status::Revoked, Message::EMPTY));
                    }
                }
            }
        }
    }
    pub(super) fn request_status(
        &self,
        caller: Caller,
        handle: u64,
    ) -> Result<Option<Status>, Status> {
        let key = self.request_key(caller, handle)?;
        Ok(self.request_record(key).unwrap().completion.map(|c| c.0))
    }
    /// Only the authenticated requester can cancel or consume its completion record.
    pub fn request_operation(
        &mut self,
        caller: Caller,
        handle: u64,
        address: u64,
        bytes: usize,
        operation: Operation,
        memory: &mut impl Memory,
    ) -> (Status, u64) {
        if operation == Operation::Cancel {
            if address != 0 || bytes != 0 {
                return (Status::Arguments, 0);
            }
        } else {
            let max = if operation == Operation::Begin {
                MAX_BYTES
            } else {
                reply::RECEIVE_BYTES
            };
            if bytes == 0
                || bytes > max
                || address < USER_WINDOW_START
                || address
                    .checked_add(bytes as u64)
                    .is_none_or(|e| e > USER_WINDOW_END_EXCLUSIVE)
            {
                return (Status::Arguments, 0);
            }
        }
        let Ok(t) = self.table(caller.id) else {
            return (Status::Denied, 0);
        };
        if self.tables[t].caller != Some(caller) {
            return (Status::Denied, 0);
        }
        if operation == Operation::Begin {
            let Ok(cap) = self.resolve(t, handle, Rights::SEND) else {
                return (Status::Denied, 0);
            };
            let Some((slot, generation)) =
                self.tables[t]
                    .requests
                    .iter()
                    .enumerate()
                    .find_map(|(i, r)| {
                        if r.value.is_none() {
                            r.generation.checked_add(1).map(|g| (i, g))
                        } else {
                            None
                        }
                    })
            else {
                return (Status::Again, 0);
            };
            let result = self.transfer(caller, handle, address, bytes, true, memory);
            if result.0 != Status::Ok {
                return result;
            }
            let key = Key {
                caller,
                slot,
                generation,
            };
            self.tables[t].requests[slot] = Slot {
                generation,
                value: Some(Request {
                    endpoint: cap.object,
                    receiver: None,
                    completion: None,
                }),
            };
            let e = self.objects[cap.object.slot].value.as_mut().unwrap();
            e.queue[(e.head + e.len - 1) % DEPTH].reply = Some(reply::Route::tracked(key));
            return (
                Status::Ok,
                (u64::from(generation) << 32) | TAG | (slot + 1) as u64,
            );
        }
        let Ok(key) = self.request_key(caller, handle) else {
            return (Status::Denied, 0);
        };
        let record = self.request_record(key).unwrap();
        if operation == Operation::Cancel {
            if record.completion.is_some() {
                return (Status::Denied, 0);
            }
            self.finish_request(key, Status::Cancelled, Message::EMPTY);
            self.prune_replies();
            return (Status::Ok, 0);
        }
        let Some((status, message)) = record.completion else {
            return (Status::Again, 0);
        };
        if status == Status::Ok {
            let result = reply::copy_envelope(message, 0, address, bytes, memory);
            if result.0 != Status::Ok {
                return result;
            }
            self.tables[t].requests[key.slot].value = None;
            result
        } else {
            self.tables[t].requests[key.slot].value = None;
            (status, 0)
        }
    }
}
