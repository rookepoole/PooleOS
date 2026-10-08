//! Asynchronous request/reply authority, not synchronous call or scheduling donation.
use super::*;
use crate::virtual_memory::{USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START};

pub const HEADER_BYTES: usize = 32;
pub const RECEIVE_BYTES: usize = HEADER_BYTES + MAX_BYTES;
const TAG: u64 = 2 << 16;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Operation {
    Request { reply_to: u64 },
    Receive,
    Reply,
    Discard,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Route {
    requester: Caller,
    receive_handle: u64,
    destination: Object,
    request_endpoint: Object,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) struct Slot {
    pub(super) generation: u32,
    pub(super) value: Option<Route>,
}
impl Slot {
    pub(super) const EMPTY: Self = Self {
        generation: 0,
        value: None,
    };
}

impl Space {
    fn live_route(&self, route: Route) -> bool {
        let Ok(t) = self.table(route.requester.id) else {
            return false;
        };
        let source = self.objects[route.request_endpoint.slot];
        self.tables[t].caller == Some(route.requester)
            && source.generation == route.request_endpoint.generation
            && source.value.is_some()
            && self
                .resolve(t, route.receive_handle, Rights::RECEIVE)
                .is_ok_and(|c| c.object == route.destination)
    }

    pub(super) fn prune_replies(&mut self) {
        for t in 0..TASKS {
            for r in 0..CAPS {
                if self.tables[t].replies[r]
                    .value
                    .is_some_and(|v| !self.live_route(v))
                {
                    self.tables[t].replies[r].value = None;
                }
            }
        }
    }

    fn reply_slot(&self, t: usize, handle: u64) -> Result<(usize, Route), Status> {
        let slot = (handle & 0xffff) as usize;
        if handle & 0xffff0000 != TAG || slot == 0 || slot > CAPS {
            return Err(Status::Denied);
        }
        let r = self.tables[t].replies[slot - 1];
        let route = r.value.ok_or(Status::Denied)?;
        if r.generation == 0 || u64::from(r.generation) != handle >> 32 || !self.live_route(route) {
            return Err(Status::Denied);
        }
        Ok((slot - 1, route))
    }

    /// Header is four LE u64s: sender slot, sender generation, reply token, payload length.
    /// Identity describes the sender at enqueue time; it grants no task authority.
    pub fn message(
        &mut self,
        caller: Caller,
        handle: u64,
        address: u64,
        bytes: usize,
        operation: Operation,
        memory: &mut impl Memory,
    ) -> (Status, u64) {
        if operation == Operation::Discard {
            if address != 0 || bytes != 0 {
                return (Status::Arguments, 0);
            }
        } else {
            let max = if operation == Operation::Receive {
                RECEIVE_BYTES
            } else {
                MAX_BYTES
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
        match operation {
            Operation::Request { reply_to } => {
                let Ok(request) = self.resolve(t, handle, Rights::SEND) else {
                    return (Status::Denied, 0);
                };
                let Ok(reply) = self.resolve(t, reply_to, Rights::RECEIVE) else {
                    return (Status::Denied, 0);
                };
                if self.objects[reply.object.slot].value.unwrap().owner != caller.id {
                    return (Status::Denied, 0);
                }
                let result = self.transfer(caller, handle, address, bytes, true, memory);
                if result.0 == Status::Ok {
                    let e = self.objects[request.object.slot].value.as_mut().unwrap();
                    e.queue[(e.head + e.len - 1) % DEPTH].reply = Some(Route {
                        requester: caller,
                        receive_handle: reply_to,
                        destination: reply.object,
                        request_endpoint: request.object,
                    });
                }
                result
            }
            Operation::Receive => self.receive_message(t, handle, address, bytes, memory),
            Operation::Reply | Operation::Discard => {
                let Ok((slot, route)) = self.reply_slot(t, handle) else {
                    return (Status::Denied, 0);
                };
                if operation == Operation::Discard {
                    self.tables[t].replies[slot].value = None;
                    return (Status::Ok, 0);
                }
                let e = self.objects[route.destination.slot].value.as_mut().unwrap();
                if e.len == DEPTH {
                    return (Status::Again, 0);
                }
                let mut message = Message {
                    len: bytes,
                    sender: Some(caller),
                    ..Message::EMPTY
                };
                for (i, byte) in message.bytes[..bytes].iter_mut().enumerate() {
                    let Ok(value) = memory.read(address + i as u64) else {
                        return (Status::Fault, 0);
                    };
                    *byte = value;
                }
                e.queue[(e.head + e.len) % DEPTH] = message;
                e.len += 1;
                self.tables[t].replies[slot].value = None;
                (Status::Ok, bytes as u64)
            }
        }
    }

    fn receive_message(
        &mut self,
        t: usize,
        handle: u64,
        address: u64,
        bytes: usize,
        memory: &mut impl Memory,
    ) -> (Status, u64) {
        let Ok(cap) = self.resolve(t, handle, Rights::RECEIVE) else {
            return (Status::Denied, 0);
        };
        let e = self.objects[cap.object.slot].value.as_ref().unwrap();
        if e.len == 0 {
            return (Status::Again, 0);
        }
        let message = e.queue[e.head];
        let required = HEADER_BYTES + message.len;
        if bytes < required {
            return (Status::TooSmall, required as u64);
        }
        // A cancelled request stays readable, but can never mint live reply authority.
        let route = message.reply.filter(|route| self.live_route(*route));
        let allocation = if route.is_some() {
            let Some(v) = self.tables[t]
                .replies
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
            Some(v)
        } else {
            None
        };
        let token = allocation.map_or(0, |(i, g)| (u64::from(g) << 32) | TAG | (i + 1) as u64);
        let sender = message
            .sender
            .expect("queued messages always retain their caller")
            .id;
        let mut envelope = [0u8; RECEIVE_BYTES];
        for (i, word) in [
            u64::from(sender.slot),
            u64::from(sender.generation),
            token,
            message.len as u64,
        ]
        .iter()
        .enumerate()
        {
            envelope[i * 8..i * 8 + 8].copy_from_slice(&word.to_le_bytes());
        }
        envelope[HEADER_BYTES..required].copy_from_slice(&message.bytes[..message.len]);
        for (i, byte) in envelope[..required].iter().enumerate() {
            if memory.write(address + i as u64, *byte).is_err() {
                return (Status::Fault, i as u64);
            }
        }
        // No authority or queue mutation before complete copy-out; no fallible step after it.
        if let Some((i, generation)) = allocation {
            self.tables[t].replies[i] = Slot {
                generation,
                value: route,
            };
        }
        let e = self.objects[cap.object.slot].value.as_mut().unwrap();
        e.queue[e.head] = Message::EMPTY;
        e.head = (e.head + 1) % DEPTH;
        e.len -= 1;
        (Status::Ok, required as u64)
    }
}
