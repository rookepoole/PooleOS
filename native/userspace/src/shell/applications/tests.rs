use super::*;
use crate::apps::program::{Program, Progress};
use std::{
    cell::RefCell,
    collections::{BTreeMap, VecDeque},
    rc::Rc,
    string::String,
    vec::Vec,
};
const SHELL: u64 = 0x100000003;
const FILES: u64 = 0x100000001;
const CONTROL: u64 = 0x100010001;
const FILE: u64 = 0x100010002;
const FACTORIES: [u64; 2] = [0x100060001, 0x100060002];
struct Pending {
    actor: u64,
    reply: Option<(u64, Vec<u8>)>,
    cancelled: bool,
    claimed: bool,
}
struct Packet {
    peer: u64,
    token: u64,
    payload: Vec<u8>,
}
#[derive(Clone, Copy, Default)]
struct Life {
    sequence: u32,
    handle: u64,
    completion: Option<u64>,
    stops: usize,
}
#[derive(Default)]
struct Bus {
    next: u64,
    pending: BTreeMap<u64, Pending>,
    queue: VecDeque<Packet>,
    life: [Life; 2],
    calls: usize,
    discarded: usize,
    ack_again: usize,
    deny_reply: bool,
    peak_claimed: usize,
    file_reads: [usize; 2],
}
fn tracked(reply: u64) -> u64 {
    (reply & !0xffff0000) | (3 << 16)
}
fn envelope(peer: u64, token: u64, payload: &[u8], bytes: &mut [u8]) -> (u64, u64) {
    for (i, value) in [peer & 0xffffffff, peer >> 32, token, payload.len() as u64]
        .into_iter()
        .enumerate()
    {
        bytes[i * 8..i * 8 + 8].copy_from_slice(&value.to_le_bytes());
    }
    bytes[32..32 + payload.len()].copy_from_slice(payload);
    (0, 32 + payload.len() as u64)
}
impl Bus {
    fn request(&mut self, actor: u64, data: &[u8], file: bool) -> u64 {
        self.next += 1;
        let token = (self.next << 32) | 0x30001;
        let reply = if file {
            self.file_reads[(actor as usize & 0xffffffff) - 4] += 1;
            Some((FILES, files::answer(data).encode().to_vec()))
        } else {
            self.queue.push_back(Packet {
                peer: actor,
                token: (self.next << 32) | 0x20001,
                payload: data.to_vec(),
            });
            None
        };
        self.pending.insert(
            token,
            Pending {
                actor,
                reply,
                cancelled: false,
                claimed: false,
            },
        );
        token
    }
    fn retire(&mut self, index: usize, completion: u64) {
        self.life[index].completion = Some(completion);
        let peer = (u64::from(self.life[index].sequence) << 32) | SLOTS[index];
        for pending in self.pending.values_mut().filter(|p| p.actor == peer) {
            pending.cancelled = true;
            pending.claimed = false;
        }
    }
}
#[derive(Clone)]
struct Rpc {
    bus: Rc<RefCell<Bus>>,
    actor: u64,
}
impl Calls for Rpc {
    fn invoke(&mut self, number: u64, handle: u64, wire: &mut [u8]) -> (u64, u64) {
        let mut b = self.bus.borrow_mut();
        b.calls += 1;
        if self.actor != SHELL {
            if number == 10 {
                assert!(handle == CONTROL || handle == FILE);
                return (0, b.request(self.actor, wire, handle == FILE));
            }
            let p = b.pending.get(&handle).expect("app owns request");
            assert_eq!(p.actor, self.actor);
            if number == 13 {
                assert!(wire.is_empty());
                return (
                    if p.cancelled {
                        9
                    } else if p.reply.is_some() {
                        0
                    } else {
                        6
                    },
                    0,
                );
            }
            assert_eq!(number, 11);
            if p.cancelled {
                b.pending.remove(&handle);
                return (9, 0);
            }
            let Some((peer, data)) = p.reply.clone() else {
                return (6, 0);
            };
            b.pending.remove(&handle);
            return envelope(peer, 0, &data, wire);
        }
        match number {
            7 => {
                assert_eq!(handle, CONTROL);
                let Some(packet) = b.queue.pop_front() else {
                    return (6, 0);
                };
                let token = if packet.token != 0 {
                    match b.pending.get_mut(&tracked(packet.token)) {
                        Some(p) if !p.cancelled => {
                            p.claimed = true;
                            packet.token
                        }
                        _ => 0,
                    }
                } else {
                    0
                };
                let count = b.pending.values().filter(|p| p.claimed).count();
                b.peak_claimed = b.peak_claimed.max(count);
                envelope(packet.peer, token, &packet.payload, wire)
            }
            8 | 9 => {
                if number == 8 && b.deny_reply {
                    b.deny_reply = false;
                    return (5, 0);
                }
                if number == 8 && Frame::decode(wire).unwrap().phase == wire::ACK && b.ack_again > 0
                {
                    b.ack_again -= 1;
                    return (6, 0);
                }
                let Some(p) = b.pending.get_mut(&tracked(handle)) else {
                    return (5, 0);
                };
                if p.cancelled {
                    return (5, 0);
                }
                assert!(p.claimed);
                p.claimed = false;
                if number == 9 {
                    assert!(wire.is_empty());
                    p.cancelled = true;
                    b.discarded += 1;
                    (0, 0)
                } else {
                    p.reply = Some((SHELL, wire.to_vec()));
                    (0, wire.len() as u64)
                }
            }
            _ => panic!("unexpected RPC {number}"),
        }
    }
}
#[derive(Clone)]
struct ProcessesMock(Rc<RefCell<Bus>>);
impl crate::supervisor::Calls for ProcessesMock {
    fn invoke(&mut self, number: u64, handle: u64, argument: u64) -> (u64, u64) {
        let mut b = self.0.borrow_mut();
        b.calls += 1;
        if number == 19 {
            let index = FACTORIES.iter().position(|&h| h == handle).unwrap();
            let life = &mut b.life[index];
            assert!(life.sequence == 0 || life.completion.is_some());
            assert_eq!(argument, u64::from(life.sequence) + 1);
            life.sequence += 1;
            // Slots are one-based, and these two leases must stay distinct.
            life.handle = (u64::from(life.sequence) << 32) | 0x50000 | (index + 1) as u64;
            life.completion = None;
            return (0, life.handle);
        }
        assert_eq!(argument, 0);
        let index = b
            .life
            .iter()
            .position(|life| life.handle == handle)
            .unwrap();
        match number {
            20 => b.life[index].completion.map_or((6, 1), |value| (0, value)),
            18 => {
                b.life[index].stops += 1;
                b.retire(index, 4 << 32);
                (6, 0)
            }
            _ => panic!("unexpected process call {number}"),
        }
    }
}
struct Harness {
    bus: Rc<RefCell<Bus>>,
    processes: ApplicationProcesses<ProcessesMock>,
    jobs: Jobs<Rpc>,
    apps: [Option<Program<Rpc>>; 2],
}
impl Harness {
    fn new() -> Self {
        let bus = Rc::new(RefCell::new(Bus::default()));
        Self {
            processes: ApplicationProcesses::new(FACTORIES, ProcessesMock(bus.clone())).unwrap(),
            jobs: Jobs::new(
                CONTROL,
                Rpc {
                    bus: bus.clone(),
                    actor: SHELL,
                },
            ),
            bus,
            apps: [None, None],
        }
    }
    fn process(&mut self, line: &[u8]) -> Vec<u8> {
        assert!(self.processes.begin(line).unwrap());
        for _ in 0..4 {
            if self.processes.poll().unwrap() {
                return self.processes.response().to_vec();
            }
        }
        panic!("process did not complete")
    }
    fn start(&mut self, index: usize) {
        let result = self.process(if index == 0 {
            b"start text"
        } else {
            b"start numbers"
        });
        assert!(result.ends_with(b": admitted\r\n"));
        let actor = (u64::from(self.bus.borrow().life[index].sequence) << 32) | SLOTS[index];
        let rpc = Rpc {
            bus: self.bus.clone(),
            actor,
        };
        self.apps[index] = Some(Program::new(
            kind(if index == 0 { App::Text } else { App::Numbers }),
            CONTROL,
            SHELL,
            rpc.clone(),
            files::rpc::Client::new(FILE, FILES, rpc),
        ));
    }
    fn app_steps(&mut self) {
        for i in 0..2 {
            if self.bus.borrow().life[i].completion.is_some() {
                self.apps[i] = None;
            }
            if let Some(app) = &mut self.apps[i] {
                let before = self.bus.borrow().calls;
                let result = app.poll();
                assert!(self.bus.borrow().calls - before <= 1);
                match result {
                    Ok(Progress::FaultRequested) => self.bus.borrow_mut().retire(i, (2 << 32) | 6),
                    Err(_) => self.bus.borrow_mut().retire(i, (1 << 32) | 202),
                    _ => {}
                }
            }
        }
    }
    fn step(&mut self) -> bool {
        let before = self.bus.borrow().calls;
        let done = self.jobs.poll(&mut self.processes).unwrap();
        assert!(self.bus.borrow().calls - before <= 1);
        self.app_steps();
        done
    }
    fn command(&mut self, line: &[u8]) -> String {
        assert!(self.jobs.begin(line, &self.processes).unwrap());
        for _ in 0..MAX_JOB_POLLS * 2 + 8 {
            if self.step() {
                return String::from_utf8(self.jobs.response().to_vec()).unwrap();
            }
        }
        panic!("bounded job did not finish")
    }
}

#[test]
fn both_actual_programs_compute_changed_files_and_repeated_jobs_over_the_bridge() {
    let mut h = Harness::new();
    h.start(0);
    h.start(1);
    for _ in 0..8 {
        assert_eq!(
            h.command(b"numbers /numbers.csv"),
            "numbers: count=5 sum=50 min=3 max=21\r\n"
        );
        assert_eq!(
            h.command(b"numbers /empty.txt"),
            "numbers: count=0 sum=0 min=0 max=0\r\n"
        );
        assert_eq!(
            h.command(b"text /empty.txt"),
            "text: bytes=0 words=0 lf=0\r\n"
        );
        for index in [0, 2] {
            let (path, body) = files::entry(index).unwrap();
            let line = [b"text ".as_slice(), path].concat();
            let words = body
                .split(|b| b.is_ascii_whitespace())
                .filter(|s| !s.is_empty())
                .count();
            let lf = body.iter().filter(|&&b| b == b'\n').count();
            assert_eq!(
                h.command(&line),
                std::format!("text: bytes={} words={words} lf={lf}\r\n", body.len())
            );
        }
    }
    assert!(h.bus.borrow().file_reads.iter().all(|&n| n > 8));
    assert!(h.bus.borrow().life.iter().all(|l| l.completion.is_none()));
    assert!(h.bus.borrow().peak_claimed <= 3);
    assert!(!h.processes.close_allowed());
}

#[test]
fn error_results_and_invalid_commands_do_not_poison_the_next_real_job() {
    let mut h = Harness::new();
    assert_eq!(h.command(b"text /readme.txt"), "text: not started\r\n");
    h.start(0);
    h.start(1);
    for line in [b"text /../x".as_slice(), b"text /A", b"text ", b"text /a/b"] {
        assert_eq!(h.command(line), "text: invalid path\r\n");
    }
    for line in [b"text".as_slice(), b"fault 4", b"fault text ", b"numbers"] {
        assert!(!h.jobs.begin(line, &h.processes).unwrap());
    }
    assert_eq!(
        h.command(b"numbers /readme.txt"),
        "numbers: invalid data\r\n"
    );
    assert_eq!(h.command(b"text /missing.txt"), "text: not found\r\n");
    assert_eq!(
        h.command(b"numbers /numbers.csv"),
        "numbers: count=5 sum=50 min=3 max=21\r\n"
    );
}

#[test]
fn acknowledgement_backpressure_keeps_results_hidden_until_accepted() {
    let mut h = Harness::new();
    h.start(1);
    h.bus.borrow_mut().ack_again = 8;
    h.jobs.begin(b"numbers /numbers.csv", &h.processes).unwrap();
    let mut saw_ack = false;
    for _ in 0..1000 {
        if h.jobs.state == State::Ack && h.bus.borrow().ack_again > 0 {
            saw_ack = true;
            assert!(h.jobs.response().is_empty());
        }
        if h.step() {
            break;
        }
    }
    assert!(saw_ack);
    assert_eq!(
        h.jobs.response(),
        b"numbers: count=5 sum=50 min=3 max=21\r\n"
    );
}

#[test]
fn application_fault_is_observed_and_the_other_program_remains_useful() {
    let mut h = Harness::new();
    h.start(0);
    h.start(1);
    assert_eq!(
        h.command(b"text /empty.txt"),
        "text: bytes=0 words=0 lf=0\r\n"
    );
    assert_eq!(h.command(b"fault numbers"), "numbers: fault requested\r\n");
    assert_eq!(
        h.process(b"status numbers"),
        b"numbers: fault 0x00000006\r\n"
    );
    assert_eq!(
        h.command(b"text /numbers.csv"),
        "text: bytes=24 words=6 lf=6\r\n"
    );
    h.start(1);
    assert_eq!(
        h.command(b"numbers /numbers.csv"),
        "numbers: count=5 sum=50 min=3 max=21\r\n"
    );
    assert_eq!(h.jobs.clients[1].peer, 0x200000005);
}

#[test]
fn stop_restart_discards_old_generation_requests_and_resets_job_sequence() {
    let mut h = Harness::new();
    h.start(0);
    h.start(1);
    h.command(b"numbers /numbers.csv");
    assert_ne!(h.jobs.clients[0].ready, 0);
    h.process(b"stop text");
    h.process(b"status text");
    h.start(0);
    h.bus.borrow_mut().request(
        0x100000004,
        &Frame::empty(wire::READY, Kind::Text, 1).encode(),
        false,
    );
    assert_eq!(
        h.command(b"text /empty.txt"),
        "text: bytes=0 words=0 lf=0\r\n"
    );
    assert_eq!(h.jobs.clients[0].peer, 0x200000004);
    assert_eq!(h.jobs.clients[0].sequence, 2);
    assert!(h.bus.borrow().discarded > 0);
}

#[test]
fn app_death_while_waiting_for_a_result_releases_replies_and_reports_real_completion() {
    let mut h = Harness::new();
    h.start(0);
    h.jobs.begin(b"text /readme.txt", &h.processes).unwrap();
    for _ in 0..100 {
        h.step();
        if h.jobs.state == State::Result {
            break;
        }
    }
    assert_eq!(h.jobs.state as u8, State::Result as u8);
    h.bus.borrow_mut().retire(0, (2 << 32) | 6);
    for _ in 0..10 {
        if h.step() {
            break;
        }
    }
    assert_eq!(h.jobs.response(), b"text: fault 0x00000006\r\n");
    assert!(h.processes.close_allowed());
    assert_eq!(h.bus.borrow().life[0].stops, 0);
}

#[test]
fn foreign_and_plain_messages_are_discarded_without_reinterpreting_payload_identity() {
    let mut h = Harness::new();
    h.start(0);
    let data = Frame::empty(wire::READY, Kind::Text, 1).encode();
    h.bus.borrow_mut().request(0x100000002, &data, false);
    h.bus.borrow_mut().queue.push_back(Packet {
        peer: 0x100000004,
        token: 0,
        payload: data.to_vec(),
    });
    assert_eq!(
        h.command(b"text /empty.txt"),
        "text: bytes=0 words=0 lf=0\r\n"
    );
    assert_eq!(h.bus.borrow().discarded, 1);
    assert_eq!(h.bus.borrow().life[0].stops, 0);
}

#[test]
fn malformed_ready_sequence_kind_padding_and_phase_stop_only_the_target() {
    for at in [0, 4, 5, 6, 7, 8, 16, 63] {
        let mut h = Harness::new();
        h.start(0);
        h.start(1);
        let mut data = Frame::empty(wire::READY, Kind::Text, 1).encode();
        data[at] ^= 0x80;
        h.bus.borrow_mut().request(0x100000004, &data, false);
        assert_eq!(
            h.command(b"text /empty.txt"),
            "text: protocol error; stop requested\r\n"
        );
        assert_eq!(h.bus.borrow().life[0].stops, 1);
        assert_eq!(
            h.command(b"numbers /numbers.csv"),
            "numbers: count=5 sum=50 min=3 max=21\r\n"
        );
    }
}

#[test]
fn bounded_job_timeout_discards_cached_authority_requests_stop_and_allows_restart() {
    let mut h = Harness::new();
    h.start(0);
    h.jobs.begin(b"text /empty.txt", &h.processes).unwrap();
    // Model a scheduled child that never issues READY, without claiming real time.
    let mut done = false;
    for _ in 0..MAX_JOB_POLLS + 5 {
        let before = h.bus.borrow().calls;
        done = h.jobs.poll(&mut h.processes).unwrap();
        assert!(h.bus.borrow().calls - before <= 1);
        if done {
            break;
        }
    }
    assert!(done);
    assert_eq!(h.jobs.response(), b"text: timed out; stop requested\r\n");
    assert_eq!(h.bus.borrow().life[0].stops, 1);
    assert!(!h.processes.close_allowed());
    h.process(b"status text");
    h.start(0);
    assert_eq!(
        h.command(b"text /empty.txt"),
        "text: bytes=0 words=0 lf=0\r\n"
    );
}

#[test]
fn revoked_reply_and_mid_job_generation_change_never_target_the_new_child() {
    let mut h = Harness::new();
    h.start(0);
    h.bus.borrow_mut().deny_reply = true;
    assert_eq!(
        h.command(b"text /empty.txt"),
        "text: request revoked; stop requested\r\n"
    );
    h.process(b"status text");
    h.start(0);
    h.jobs.begin(b"text /empty.txt", &h.processes).unwrap();
    h.process(b"stop text");
    h.process(b"status text");
    h.start(0);
    let before = h.bus.borrow().life[0].stops;
    for _ in 0..10 {
        if h.step() {
            break;
        }
    }
    assert_eq!(h.jobs.response(), b"text: generation changed\r\n");
    assert_eq!(h.bus.borrow().life[0].stops, before);
    assert_eq!(
        h.command(b"text /empty.txt"),
        "text: bytes=0 words=0 lf=0\r\n"
    );
}

#[test]
fn successful_result_bounds_reject_impossible_counters_without_overflow() {
    for values in [
        [-1, 0, 0, 0],
        [4097, 0, 0, 0],
        [4, 5, 0, 0],
        [4, 0, 5, 0],
        [0, 0, 0, 1],
    ] {
        assert!(!valid_result(&Frame::result(Kind::Text, 1, Ok(values))));
    }
    for values in [
        [-1, 0, 0, 0],
        [257, 0, 0, 0],
        [0, 1, 0, 0],
        [1, 4, 5, 3],
        [1, 0, i64::MIN, 0],
        [1, 0, 0, i64::MAX],
        [1, -1, 0, 4],
        [1, 5, 0, 4],
    ] {
        assert!(!valid_result(&Frame::result(Kind::Numbers, 1, Ok(values))));
    }
    let mut h = Harness::new();
    h.jobs.target = App::Numbers;
    for value in [i32::MIN, i32::MAX] {
        let value = i64::from(value);
        let frame = Frame::result(Kind::Numbers, 1, Ok([256, 256 * value, value, value]));
        assert!(valid_result(&frame));
        h.jobs.result = frame;
        h.jobs.result_text().unwrap();
        assert_eq!(
            h.jobs.response(),
            std::format!(
                "numbers: count=256 sum={} min={value} max={value}\r\n",
                256 * value
            )
            .as_bytes()
        );
    }
}

#[test]
fn command_policy_routes_files_lifecycle_and_jobs_without_fake_success() {
    let mut h = Harness::new();
    h.start(0);
    let mut files = super::super::files::Files::new(files::rpc::Client::new(
        FILE,
        FILES,
        Rpc {
            bus: h.bus.clone(),
            actor: 0x100000004,
        },
    ));
    let mut commands = ApplicationCommands::new(&mut files, &mut h.processes, &mut h.jobs);
    assert!(commands.begin(b"cat /empty.txt").unwrap());
    for _ in 0..10 {
        if commands.poll().unwrap() {
            break;
        }
    }
    assert_eq!(commands.response(), b"");
    assert!(commands.response_complete());
    assert!(commands.begin(b"status text").unwrap());
    assert!(commands.poll().unwrap());
    assert_eq!(commands.response(), b"text: attached\r\n");
    assert!(commands.begin(b"numbers /numbers.csv").unwrap());
    assert!(commands.poll().unwrap());
    assert_eq!(commands.response(), b"numbers: not started\r\n");
    assert!(!commands.begin(b"start worker").unwrap());
    assert!(!commands.close_allowed());
}

#[test]
fn job_sequence_exhaustion_returns_the_last_result_without_wrapping_or_killing_shell() {
    let mut h = Harness::new();
    h.start(0);
    h.jobs.begin(b"text /empty.txt", &h.processes).unwrap();
    let sequence = u64::MAX - 1;
    let result = Frame::result(Kind::Text, sequence, Ok([0; 4]));
    h.jobs.clients[0].sequence = sequence;
    h.jobs.state = State::Result;
    h.jobs.monitor = false;
    h.bus
        .borrow_mut()
        .request(0x100000004, &result.encode(), false);
    for _ in 0..8 {
        if h.jobs.poll(&mut h.processes).unwrap() {
            break;
        }
    }
    assert_eq!(h.jobs.response(), b"text: bytes=0 words=0 lf=0\r\n");
    assert!(h.jobs.clients[0].blocked);
    assert_eq!(h.jobs.clients[0].sequence, sequence);
    assert!(h.jobs.begin(b"text /empty.txt", &h.processes).unwrap());
    assert_eq!(h.jobs.response(), b"text: stop and restart required\r\n");
}
