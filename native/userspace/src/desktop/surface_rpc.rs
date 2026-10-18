//! PWS1 transport over kernel-authenticated PRPC1 envelopes, independent of PCS1.
#![forbid(unsafe_code)]
#[cfg(test)]
use super::surfaces;
use super::surfaces::{Frame, Surfaces};
use crate::console_ipc::{Error, rpc::Calls};
// Interactive clients can wait behind a full software composition. The render
// work test bounds two scene turns including display-queue backpressure retries.
pub const INPUT_POLL_LIMIT: u32 = 65_536;
#[inline(always)]
fn word(w: &[u8], start: usize) -> Result<u64, Error> {
    Ok(u64::from_le_bytes(
        w.get(start..start + 8)
            .ok_or(Error::Wire)?
            .try_into()
            .map_err(|_| Error::Wire)?,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::VecDeque, vec::Vec};
    struct Fake {
        incoming: VecDeque<[u8; 96]>,
        reply_status: u64,
        sent: Vec<Vec<u8>>,
        discarded: usize,
    }
    impl Calls for Fake {
        fn invoke(&mut self, n: u64, _: u64, w: &mut [u8]) -> (u64, u64) {
            match n {
                7 => {
                    if let Some(b) = self.incoming.pop_front() {
                        w.copy_from_slice(&b);
                        (0, 96)
                    } else {
                        (6, 0)
                    }
                }
                8 => {
                    self.sent.push(w.to_vec());
                    (
                        self.reply_status,
                        if self.reply_status == 0 { 64 } else { 0 },
                    )
                }
                9 => {
                    self.discarded += 1;
                    (0, 0)
                }
                _ => panic!(),
            }
        }
    }
    fn envelope(slot: u64, g: u64, f: Frame) -> [u8; 96] {
        let mut w = [0; 96];
        w[..8].copy_from_slice(&slot.to_le_bytes());
        w[8..16].copy_from_slice(&g.to_le_bytes());
        w[16..24].copy_from_slice(&0x100020001u64.to_le_bytes());
        w[24..32].copy_from_slice(&64u64.to_le_bytes());
        w[32..].copy_from_slice(&f.encode());
        w
    }
    #[test]
    fn response_backpressure_does_not_reapply_open_or_consume_next_client() {
        let mut f = Fake {
            incoming: [
                envelope(4, 1, Frame::new(surfaces::OPEN, 1, 0)),
                envelope(5, 1, Frame::new(surfaces::OPEN, 1, 0)),
            ]
            .into(),
            reply_status: 6,
            sent: Vec::new(),
            discarded: 0,
        };
        let mut storage = [0; 384];
        let mut s = Surfaces::new(&mut storage);
        let mut server = Server::new(1);
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), Some(0));
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), None);
        assert_eq!(f.incoming.len(), 1);
        assert_eq!(f.sent[0], f.sent[1]);
        f.reply_status = 0;
        server.poll(&mut f, &mut s).unwrap();
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), Some(1));
        assert!(s.open(0) && s.open(1));
    }
    #[test]
    fn lifecycle_retirement_runs_while_reply_is_backpressured_and_old_writes_stay_dead() {
        struct Dead;
        impl crate::supervisor::Calls for Dead {
            fn invoke(&mut self, n: u64, slot: u64, generation: u64) -> (u64, u64) {
                assert_eq!((n, slot, generation), (27, 4, 1));
                (6, 4)
            }
        }
        let mut f = Fake {
            incoming: [envelope(4, 1, Frame::new(surfaces::OPEN, 1, 0))].into(),
            reply_status: 6,
            sent: Vec::new(),
            discarded: 0,
        };
        let mut storage = [0; 384];
        let mut s = Surfaces::new(&mut storage);
        let mut server = Server::new(1);
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), Some(0));
        let handle = Frame::decode(&f.sent[0]).unwrap().handle;
        assert_eq!(super::super::lifecycle::poll(&mut s, &mut Dead), Ok(1));
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), None);
        assert!(!s.open(0));
        assert_eq!(f.sent[0], f.sent[1]);
        f.reply_status = 9;
        server.poll(&mut f, &mut s).unwrap();
        let mut old = Frame::new(surfaces::WRITE, 2, handle);
        old.len = 1;
        old.data[0] = b'X';
        f.incoming.extend([
            envelope(4, 1, old),
            envelope(4, 2, Frame::new(surfaces::OPEN, 1, 0)),
        ]);
        f.reply_status = 0;
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), None);
        assert_eq!(
            Frame::decode(f.sent.last().unwrap()).unwrap().status,
            surfaces::DENIED
        );
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), Some(0));
        assert!(s.open(0));
        assert_eq!(s.generation(0), 2);
        assert!(!s.retire(0, 1));
    }
    #[test]
    fn malicious_and_retired_clients_do_not_kill_surface_service() {
        let mut bad = envelope(4, 1, Frame::new(surfaces::OPEN, 1, 0));
        bad[39] = 1;
        let mut f = Fake {
            incoming: [
                bad,
                envelope(3, 1, Frame::new(surfaces::OPEN, 1, 0)),
                envelope(4, 1, Frame::new(surfaces::OPEN, 1, 0)),
            ]
            .into(),
            reply_status: 5,
            sent: Vec::new(),
            discarded: 0,
        };
        let mut storage = [0; 384];
        let mut s = Surfaces::new(&mut storage);
        let mut server = Server::new(1);
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), None);
        assert_eq!(f.discarded, 1);
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), None);
        assert!(!s.open(0));
        f.reply_status = 0;
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), Some(0));
        assert_eq!(Frame::decode(&f.sent[0]).unwrap().status, surfaces::DENIED);
    }
    #[test]
    fn client_rejects_forged_identity_and_times_out_with_cancellation() {
        struct F {
            slot: u64,
            polls: usize,
            cancelled: bool,
            stall: bool,
        }
        impl Calls for F {
            fn invoke(&mut self, n: u64, _: u64, w: &mut [u8]) -> (u64, u64) {
                match n {
                    10 => (0, 0x100030001),
                    11 => {
                        self.polls += 1;
                        if self.stall {
                            return (6, 0);
                        }
                        let mut reply = Frame::new(surfaces::OPEN, 1, 1);
                        reply.status = 0;
                        let mut b = envelope(self.slot, 1, reply);
                        b[16..24].fill(0);
                        w.copy_from_slice(&b);
                        (0, 96)
                    }
                    12 => {
                        self.cancelled = true;
                        (0, 0)
                    }
                    _ => panic!(),
                }
            }
        }
        for slot in [0, 1, 3, 4, u64::MAX] {
            let mut f = F {
                slot,
                polls: 0,
                cancelled: false,
                stall: false,
            };
            assert!(
                Client::new(1)
                    .exchange(&mut f, Frame::new(surfaces::OPEN, 1, 0))
                    .is_err()
            );
        }
        let mut f = F {
            slot: 2,
            polls: 0,
            cancelled: false,
            stall: true,
        };
        assert!(
            Client::new(1)
                .exchange(&mut f, Frame::new(surfaces::OPEN, 1, 0))
                .is_err()
        );
        assert_eq!(f.polls, 4097);
        assert!(f.cancelled);
        f.stall = false;
        assert!(
            Client::new(1)
                .exchange(&mut f, Frame::new(surfaces::OPEN, 1, 0))
                .is_ok()
        );
    }
    #[test]
    fn cancelled_queued_request_cannot_mutate_surface_or_stop_server() {
        let mut cancelled = envelope(4, 1, Frame::new(surfaces::OPEN, 1, 0));
        cancelled[16..24].fill(0);
        let mut f = Fake {
            incoming: [cancelled, envelope(4, 1, Frame::new(surfaces::OPEN, 1, 0))].into(),
            reply_status: 0,
            sent: Vec::new(),
            discarded: 0,
        };
        let mut storage = [0; 384];
        let mut s = Surfaces::new(&mut storage);
        let mut server = Server::new(1);
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), None);
        assert!(!s.open(0));
        assert!(f.sent.is_empty());
        assert_eq!(f.discarded, 0);
        assert_eq!(server.poll(&mut f, &mut s).unwrap(), Some(0));
        assert!(s.open(0));
    }

    #[test]
    fn input_reply_backpressure_is_exact_and_cannot_drain_next_owner() {
        use crate::desktop::application_input::{INPUT, Queues};
        let mut storage = [0; 384];
        let mut s = Surfaces::new(&mut storage);
        let a = s.apply(4, 1, Frame::new(surfaces::OPEN, 1, 0)).0.handle;
        let b = s.apply(5, 1, Frame::new(surfaces::OPEN, 1, 0)).0.handle;
        let mut q = Queues::new();
        q.sync(&s);
        q.push(0, b'A');
        q.push(1, b'B');
        let mut f = Fake {
            incoming: [
                envelope(4, 1, Frame::new(INPUT, 2, a)),
                envelope(5, 1, Frame::new(INPUT, 2, b)),
            ]
            .into(),
            reply_status: 6,
            sent: Vec::new(),
            discarded: 0,
        };
        let mut server = Server::new(1);
        server
            .poll_mode::<true>(&mut f, &mut s, Some(&mut q))
            .unwrap();
        q.push(0, b'C');
        for _ in 0..8 {
            server
                .poll_mode::<true>(&mut f, &mut s, Some(&mut q))
                .unwrap();
        }
        assert_eq!(f.incoming.len(), 1);
        assert!(f.sent.iter().all(|r| r == &f.sent[0]));
        assert_eq!(
            Frame::decode_mode::<true>(&f.sent[0]).unwrap().data[0],
            b'A'
        );
        f.reply_status = 0;
        server
            .poll_mode::<true>(&mut f, &mut s, Some(&mut q))
            .unwrap();
        server
            .poll_mode::<true>(&mut f, &mut s, Some(&mut q))
            .unwrap();
        assert_eq!(
            Frame::decode_mode::<true>(f.sent.last().unwrap())
                .unwrap()
                .data[0],
            b'B'
        );
        f.incoming
            .push_back(envelope(4, 1, Frame::new(INPUT, 3, a)));
        server
            .poll_mode::<true>(&mut f, &mut s, Some(&mut q))
            .unwrap();
        assert_eq!(
            Frame::decode_mode::<true>(f.sent.last().unwrap())
                .unwrap()
                .data[0],
            b'C'
        );
    }

    #[test]
    fn interactive_poll_budget_survives_composition_but_still_cancels_once() {
        struct Delayed {
            polls: u32,
            ready: u32,
            requests: u32,
            cancels: u32,
        }
        impl Calls for Delayed {
            fn invoke(&mut self, n: u64, _: u64, wire: &mut [u8]) -> (u64, u64) {
                match n {
                    10 => {
                        self.requests += 1;
                        (0, 0x100030001)
                    }
                    11 => {
                        self.polls += 1;
                        if self.polls <= self.ready {
                            return (6, 0);
                        }
                        let mut response = envelope(2, 1, Frame::new(surfaces::OPEN, 1, 1));
                        response[16..24].fill(0);
                        wire.copy_from_slice(&response);
                        (0, 96)
                    }
                    12 => {
                        self.cancels += 1;
                        (0, 0)
                    }
                    _ => panic!(),
                }
            }
        }
        let mut client = Client::new(1);
        let mut calls = Delayed {
            polls: 0,
            ready: 5000,
            requests: 0,
            cancels: 0,
        };
        for _ in 0..5000 {
            assert!(
                client
                    .step_mode::<true>(&mut calls, Frame::new(surfaces::OPEN, 1, 0))
                    .unwrap()
                    .is_none()
            );
        }
        assert!(
            client
                .step_mode::<true>(&mut calls, Frame::new(surfaces::OPEN, 1, 0))
                .unwrap()
                .is_some()
        );
        assert_eq!((calls.requests, calls.cancels), (1, 0));
        let mut client = Client::new(1);
        calls = Delayed {
            polls: 0,
            ready: u32::MAX,
            requests: 0,
            cancels: 0,
        };
        for _ in 0..INPUT_POLL_LIMIT {
            assert!(
                client
                    .step_mode::<true>(&mut calls, Frame::new(surfaces::OPEN, 1, 0))
                    .unwrap()
                    .is_none()
            );
        }
        assert!(
            client
                .step_mode::<true>(&mut calls, Frame::new(surfaces::OPEN, 1, 0))
                .is_err()
        );
        assert_eq!(
            (calls.requests, calls.cancels, calls.polls),
            (1, 1, INPUT_POLL_LIMIT + 1)
        );
        assert!(!client.pending());
    }

    #[test]
    fn cancelled_and_denied_input_requests_preserve_unconsumed_owned_queue() {
        use crate::desktop::application_input::{INPUT, Queues};
        let mut storage = [0; 384];
        let mut s = Surfaces::new(&mut storage);
        let a = s.apply(4, 1, Frame::new(surfaces::OPEN, 1, 0)).0.handle;
        let mut q = Queues::new();
        q.sync(&s);
        q.push(0, b'X');
        let mut cancelled = envelope(4, 1, Frame::new(INPUT, 2, a));
        cancelled[16..24].fill(0);
        let mut f = Fake {
            incoming: [
                cancelled,
                envelope(5, 1, Frame::new(INPUT, 2, a)),
                envelope(4, 1, Frame::new(INPUT, 2, a)),
            ]
            .into(),
            reply_status: 0,
            sent: Vec::new(),
            discarded: 0,
        };
        let mut server = Server::new(1);
        for _ in 0..3 {
            server
                .poll_mode::<true>(&mut f, &mut s, Some(&mut q))
                .unwrap();
        }
        assert_eq!(f.sent.len(), 2);
        assert_eq!(
            Frame::decode_mode::<true>(&f.sent[0]).unwrap().status,
            surfaces::DENIED
        );
        assert_eq!(
            Frame::decode_mode::<true>(&f.sent[1]).unwrap().data[0],
            b'X'
        );
        assert!(!s.open(1));
    }
}
#[inline]
fn token(h: u64, tag: u64) -> bool {
    h >> 32 != 0 && h & 0xffff0000 == tag << 16 && h & 0xffff != 0
}
pub struct Server {
    endpoint: u64,
    reply: u64,
    output: [u8; 64],
}
impl Server {
    #[inline(always)]
    pub const fn new(endpoint: u64) -> Self {
        Self {
            endpoint,
            reply: 0,
            output: [0; 64],
        }
    }
    pub fn poll(
        &mut self,
        calls: &mut impl Calls,
        surfaces: &mut Surfaces<'_>,
    ) -> Result<Option<usize>, Error> {
        self.poll_mode::<false>(calls, surfaces, None)
    }
    #[inline]
    pub fn poll_mode<const INPUT: bool>(
        &mut self,
        calls: &mut impl Calls,
        surfaces: &mut Surfaces<'_>,
        mut input: Option<&mut super::application_input::Queues>,
    ) -> Result<Option<usize>, Error> {
        if INPUT && input.is_none() {
            return Err(Error::Transport);
        }
        let mut changed = None;
        if self.reply == 0 {
            let mut w = [0; 96];
            match calls.invoke(7, self.endpoint, &mut w) {
                (6, 0) => return Ok(None),
                (0, n) if (32..=96).contains(&n) => {
                    let reply = word(&w, 16)?;
                    // Cancelled/plain messages remain readable but carry no reply authority.
                    if reply == 0 {
                        return Ok(None);
                    }
                    if !token(reply, 2) {
                        return Err(Error::Transport);
                    }
                    let frame = if n == 96 && word(&w, 24)? == 64 {
                        Frame::decode_mode::<INPUT>(&w[32..])
                    } else {
                        None
                    };
                    let Some(frame) = frame else {
                        let (status, value) = calls.invoke(9, reply, &mut []);
                        return if matches!(status, 0 | 5 | 9) && value == 0 {
                            Ok(None)
                        } else {
                            Err(Error::Transport)
                        };
                    };
                    let slot = word(&w, 0)?;
                    let generation = word(&w, 8)?;
                    let (output, dirty) = if INPUT && frame.op == super::application_input::INPUT {
                        let (mut output, index) = surfaces.input_request(slot, generation, frame);
                        if let Some(i) = index {
                            input
                                .as_mut()
                                .ok_or(Error::Transport)?
                                .drain(i, surfaces, &mut output);
                        }
                        (output, false)
                    } else {
                        surfaces.apply(slot, generation, frame)
                    };
                    output.encode_into(&mut self.output);
                    self.reply = reply;
                    if dirty {
                        changed = Some(
                            usize::try_from(slot.checked_sub(4).ok_or(Error::Peer)?)
                                .map_err(|_| Error::Peer)?,
                        );
                    }
                }
                _ => return Err(Error::Transport),
            }
        }
        match calls.invoke(8, self.reply, &mut self.output) {
            (0, 64) | (5, 0) | (9, 0) => self.reply = 0,
            (6, 0) => {}
            _ => return Err(Error::Transport),
        }
        Ok(changed)
    }
}
pub struct Client {
    endpoint: u64,
    handle: u64,
    sequence: u64,
    pending: u64,
    op: u8,
    polls: u32,
}
impl Client {
    #[inline(always)]
    pub const fn new(endpoint: u64) -> Self {
        Self {
            endpoint,
            handle: 0,
            sequence: 0,
            pending: 0,
            op: 0,
            polls: 0,
        }
    }
    #[inline]
    pub fn pending(&self) -> bool {
        self.pending != 0
    }
    /// At most one submit and one completion poll. A pending operation retains its identity.
    #[inline(always)]
    pub fn step(&mut self, calls: &mut impl Calls, frame: Frame) -> Result<bool, Error> {
        self.step_mode::<false>(calls, frame).map(|r| r.is_some())
    }
    #[inline(always)]
    pub fn step_mode<const INPUT: bool>(
        &mut self,
        calls: &mut impl Calls,
        mut frame: Frame,
    ) -> Result<Option<Frame>, Error> {
        frame.sequence = self.sequence.checked_add(1).ok_or(Error::Wire)?;
        frame.handle = self.handle;
        if self.pending == 0 {
            let mut request = [0; 64];
            frame.encode_into(&mut request);
            match calls.invoke(10, self.endpoint, &mut request) {
                (0, h) if token(h, 3) => {
                    self.pending = h;
                    self.op = frame.op;
                    self.polls = 0;
                }
                (6, 0) => return Ok(None),
                _ => return Err(Error::Transport),
            }
        }
        let mut w = [0; 96];
        if self.polls >= if INPUT { INPUT_POLL_LIMIT } else { 4096 } {
            let _ = calls.invoke(12, self.pending, &mut []);
            let _ = calls.invoke(11, self.pending, &mut w);
            self.pending = 0;
            return Err(Error::Transport);
        }
        self.polls += 1;
        match calls.invoke(11, self.pending, &mut w) {
            (6, 0) => Ok(None),
            (0, 96)
                if word(&w, 0)? == 2
                    && word(&w, 8)? == 1
                    && word(&w, 16)? == 0
                    && word(&w, 24)? == 64 =>
            {
                self.pending = 0;
                let reply = Frame::decode_mode::<INPUT>(&w[32..]).ok_or(Error::Wire)?;
                let payload = if INPUT && self.op == super::application_input::INPUT {
                    (reply.offset == 0
                        || reply.offset == super::application_input::RESET && reply.len == 0)
                        && reply
                            .data
                            .iter()
                            .take(usize::from(reply.len))
                            .all(|&b| super::application_input::valid_key(b))
                } else {
                    reply.offset == 0 && reply.len == 0
                };
                if reply.status != 0
                    || reply.op != self.op
                    || reply.sequence != frame.sequence
                    || reply.handle == 0
                    || !payload
                    || (self.handle != 0 && reply.handle != self.handle)
                {
                    return Err(Error::Peer);
                }
                self.handle = reply.handle;
                self.sequence = reply.sequence;
                Ok(Some(reply))
            }
            _ => {
                self.pending = 0;
                Err(Error::Transport)
            }
        }
    }
    #[cfg(test)]
    fn exchange(&mut self, calls: &mut impl Calls, frame: Frame) -> Result<(), Error> {
        for _ in 0..4097 {
            if self.step(calls, frame)? {
                return Ok(());
            }
        }
        Err(Error::Transport)
    }
}
