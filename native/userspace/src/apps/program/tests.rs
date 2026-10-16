use super::*;
use std::{cell::RefCell, collections::VecDeque, rc::Rc, vec, vec::Vec};
const CONTROL: u64 = 0x100010001;
const FILE: u64 = 0x100010002;
const SHELL: u64 = 0x100000003;
const SERVER: u64 = 0x100000001;

struct StateMock {
    jobs: VecDeque<Vec<u8>>,
    results: Vec<Frame>,
    body: Option<Vec<u8>>,
    pending: [Option<Vec<u8>>; 2],
    tokens: [u64; 2],
    start_again: [bool; 2],
    finish_again: [bool; 2],
    calls: usize,
    file_requests: Vec<files::Frame>,
    control_mutation: Option<(usize, u8)>,
    file_fault: u8,
    fault_job: bool,
    waits: usize,
    wait_result: (u64, u64),
}
#[derive(Clone)]
struct Adapter {
    shared: Rc<RefCell<StateMock>>,
    lane: usize,
}
impl Calls for Adapter {
    fn invoke(&mut self, number: u64, handle: u64, bytes: &mut [u8]) -> (u64, u64) {
        let mut s = self.shared.borrow_mut();
        let lane = self.lane;
        s.calls += 1;
        if number == 10 {
            assert_eq!(handle, if lane == 0 { CONTROL } else { FILE });
            assert!(s.pending[lane].is_none());
            if s.start_again[lane] {
                s.start_again[lane] = false;
                return (6, 0);
            }
            s.start_again[lane] = true;
            if lane == 1 && s.file_fault == 1 {
                return (5, 0);
            }
            if lane == 0 {
                let f = Frame::decode(bytes).unwrap();
                if f.phase == wire::RESULT {
                    s.results.push(f);
                } else {
                    assert_eq!(f.phase, wire::READY);
                }
            } else {
                s.file_requests.push(files::Frame::decode(bytes).unwrap());
            }
            s.pending[lane] = Some(bytes.to_vec());
            s.tokens[lane] += 1u64 << 32;
            return (0, s.tokens[lane]);
        }
        if number == 13 {
            assert_eq!(lane, 1);
            assert_eq!(handle, s.tokens[1]);
            assert!(s.pending[1].is_some());
            assert!(bytes.is_empty());
            s.waits += 1;
            return s.wait_result;
        }
        assert_eq!(number, 11);
        assert_eq!(handle, s.tokens[lane]);
        assert!(s.pending[lane].is_some());
        if s.finish_again[lane] {
            s.finish_again[lane] = false;
            return (6, 0);
        }
        s.finish_again[lane] = true;
        if lane == 1 && s.file_fault == 2 {
            s.pending[lane] = None;
            return (9, 0);
        }
        let payload = if lane == 0 {
            let request = Frame::decode(s.pending[0].as_ref().unwrap()).unwrap();
            let mut reply = Frame::empty(wire::ACK, request.kind, request.sequence);
            if request.phase == wire::READY {
                if s.fault_job {
                    reply.phase = wire::FAULT;
                } else if let Some(path) = s.jobs.pop_front() {
                    reply.phase = wire::RUN;
                    reply.len = path.len() as u8;
                    reply.data[..path.len()].copy_from_slice(&path);
                } else {
                    return (6, 0);
                }
            }
            reply.encode()
        } else {
            let request = files::Frame::decode(s.pending[1].as_ref().unwrap()).unwrap();
            let mut reply = files::answer(&request.encode());
            if let Some(body) = &s.body {
                reply = files::Frame::empty(files::READ, request.sequence, request.offset);
                reply.total = body.len() as u32;
                let tail = &body[request.offset as usize..];
                let part = &tail[..tail.len().min(40)];
                reply.len = part.len() as u8;
                reply.data[..part.len()].copy_from_slice(part);
            }
            match s.file_fault {
                3 => {
                    reply.len = 0;
                    reply.data.fill(0);
                    reply.total = 1;
                }
                4 => reply.total = MAX_FILE_BYTES + 1,
                5 if request.offset != 0 => reply.total += 1,
                6 => reply.offset += 1,
                7 => {
                    reply.status = files::NOT_FOUND;
                    reply.len = 1;
                    reply.total = 1;
                }
                _ => {}
            }
            reply.encode()
        };
        s.pending[lane] = None;
        let peer = if lane == 0 { SHELL } else { SERVER };
        bytes[..8].copy_from_slice(&(peer & 0xffffffff).to_le_bytes());
        bytes[8..16].copy_from_slice(&(peer >> 32).to_le_bytes());
        bytes[16..24].fill(0);
        bytes[24..32].copy_from_slice(&64u64.to_le_bytes());
        bytes[32..].copy_from_slice(&payload);
        if lane == 0 {
            if let Some((index, byte)) = s.control_mutation {
                bytes[index] = byte;
            }
        }
        (0, 96)
    }
}
fn fixture(kind: Kind, paths: &[&[u8]]) -> (Program<Adapter>, Rc<RefCell<StateMock>>) {
    let shared = Rc::new(RefCell::new(StateMock {
        jobs: paths.iter().map(|path| path.to_vec()).collect(),
        results: Vec::new(),
        body: None,
        pending: [None, None],
        tokens: [0x30001, 0x30002],
        start_again: [true; 2],
        finish_again: [true; 2],
        calls: 0,
        file_requests: Vec::new(),
        control_mutation: None,
        file_fault: 0,
        fault_job: false,
        waits: 0,
        wait_result: (0, 0),
    }));
    let control = Adapter {
        shared: shared.clone(),
        lane: 0,
    };
    let file = Adapter {
        shared: shared.clone(),
        lane: 1,
    };
    (
        Program::new(
            kind,
            CONTROL,
            SHELL,
            control,
            files::rpc::Client::new(FILE, SERVER, file),
        ),
        shared,
    )
}
fn drive(
    app: &mut Program<Adapter>,
    shared: &Rc<RefCell<StateMock>>,
    jobs: usize,
) -> Result<(), Error> {
    let mut complete = 0;
    for _ in 0..5000 {
        let before = shared.borrow().calls;
        let progress = app.poll();
        assert!(
            shared.borrow().calls - before <= 1,
            "more than one syscall per poll"
        );
        match progress? {
            Progress::JobComplete => {
                complete += 1;
                if complete == jobs {
                    return Ok(());
                }
            }
            Progress::FaultRequested => panic!("unexpected fault"),
            Progress::Pending => {}
        }
    }
    panic!("bounded host dialogue did not finish")
}
#[test]
fn text_jobs_read_real_bundle_chunks_and_wait_for_authenticated_ack() {
    let (mut app, s) = fixture(
        Kind::Text,
        &[b"/readme.txt", b"/empty.txt", b"/version.txt"],
    );
    drive(&mut app, &s, 3).unwrap();
    let s = s.borrow();
    for (result, index) in s.results.iter().zip([0, 3, 1]) {
        let data = files::entry(index).unwrap().1;
        let expected = [
            data.len() as i64,
            data.split(|b| matches!(b, b' ' | b'\r' | b'\n' | b'\t'))
                .filter(|w| !w.is_empty())
                .count() as i64,
            data.iter().filter(|&&b| b == b'\n').count() as i64,
            0,
        ];
        assert_eq!(result.values(), Some(expected));
    }
    assert_eq!(
        s.results.iter().map(|r| r.sequence).collect::<Vec<_>>(),
        vec![1, 2, 3]
    );
    assert!(s.file_requests.len() > 3);
    assert_eq!(s.waits, s.file_requests.len() * 2);
    assert!(
        s.file_requests
            .windows(2)
            .all(|p| p[1].sequence == p[0].sequence + 1)
    );
    assert_eq!(app.state, State::Ready);
}
#[test]
fn numbers_jobs_compute_changed_data_instead_of_fixed_demo_answers() {
    for body in [
        &b"value\r\n3\r\n5\r\n8\r\n13\r\n21\r\n"[..],
        &b"value\n-100\n3\n7\n"[..],
    ] {
        let (mut app, s) = fixture(Kind::Numbers, &[b"/numbers.csv"]);
        s.borrow_mut().body = Some(body.to_vec());
        drive(&mut app, &s, 1).unwrap();
        let values: Vec<i64> = std::str::from_utf8(body)
            .unwrap()
            .lines()
            .skip(1)
            .map(|v| v.parse().unwrap())
            .collect();
        assert_eq!(
            s.borrow().results[0].values(),
            Some([
                values.len() as i64,
                values.iter().sum(),
                *values.iter().min().unwrap(),
                *values.iter().max().unwrap()
            ])
        );
    }
}
#[test]
fn bad_paths_missing_files_and_data_errors_are_results_not_process_death() {
    let (mut app, s) = fixture(
        Kind::Numbers,
        &[
            b"/../x",
            b"/missing.txt",
            b"/readme.txt",
            b"/numbers.csv",
            b"/empty.txt",
        ],
    );
    drive(&mut app, &s, 5).unwrap();
    assert_eq!(
        s.borrow()
            .results
            .iter()
            .map(|r| r.status)
            .collect::<Vec<_>>(),
        vec![BAD_PATH, NOT_FOUND, INVALID_DATA, 0, 0]
    );
    assert_eq!(s.borrow().results[3].values(), Some([5, 50, 3, 21]));
    assert_eq!(s.borrow().results[4].values(), Some([0; 4]));
}
#[test]
fn denied_or_revoked_file_access_returns_unavailable_and_job_loop_survives() {
    for mode in [1, 2] {
        let (mut app, s) = fixture(Kind::Text, &[b"/readme.txt", b"/version.txt"]);
        s.borrow_mut().file_fault = mode;
        drive(&mut app, &s, 2).unwrap();
        assert_eq!(
            s.borrow()
                .results
                .iter()
                .map(|r| r.status)
                .collect::<Vec<_>>(),
            vec![UNAVAILABLE; 2]
        );
    }
}
#[test]
fn wait_backpressure_never_polls_early_and_revoked_wakeup_is_consumed() {
    let (mut app, s) = fixture(Kind::Text, &[b"/readme.txt"]);
    for _ in 0..30 {
        if app.state == State::Wait {
            break;
        }
        app.poll().unwrap();
    }
    assert_eq!(app.state, State::Wait);
    s.borrow_mut().wait_result = (6, 0);
    let before = s.borrow().calls;
    for _ in 0..10 {
        assert_eq!(app.poll(), Ok(Progress::Pending));
        assert_eq!(app.state, State::Wait);
    }
    assert_eq!(s.borrow().calls, before + 10);
    assert_eq!(s.borrow().waits, 10);
    assert!(s.borrow().finish_again[1]);
    s.borrow_mut().wait_result = (9, 0);
    s.borrow_mut().file_fault = 2;
    drive(&mut app, &s, 1).unwrap();
    assert_eq!(s.borrow().results[0].status, UNAVAILABLE);
    assert!(s.borrow().pending[1].is_none());
}
#[test]
fn invalid_wait_fails_closed_without_accepting_file_bytes() {
    for result in [(0, 1), (9, 1), (5, 0), (255, 0)] {
        let (mut app, s) = fixture(Kind::Text, &[b"/readme.txt"]);
        s.borrow_mut().wait_result = result;
        assert_eq!(drive(&mut app, &s, 1), Err(Error::Transport));
        assert!(s.borrow().results.is_empty());
        let calls = s.borrow().calls;
        assert_eq!(app.poll(), Err(Error::Transport));
        assert_eq!(s.borrow().calls, calls);
    }
}
#[test]
fn hostile_file_progress_identity_totals_and_error_payloads_fail_closed() {
    for mode in [3, 5, 6, 7] {
        let (mut app, s) = fixture(Kind::Text, &[b"/readme.txt"]);
        s.borrow_mut().file_fault = mode;
        assert!(drive(&mut app, &s, 1).is_err(), "mode {mode}");
        assert!(s.borrow().results.is_empty());
        let calls = s.borrow().calls;
        assert_eq!(app.poll(), Err(Error::Transport));
        assert_eq!(s.borrow().calls, calls);
    }
    let (mut app, s) = fixture(Kind::Text, &[b"/readme.txt"]);
    s.borrow_mut().file_fault = 4;
    drive(&mut app, &s, 1).unwrap();
    assert_eq!(s.borrow().results[0].status, LIMIT);
}
#[test]
fn wrong_control_peer_token_phase_kind_sequence_or_padding_is_not_a_job() {
    for (at, byte) in [
        (0, 4),
        (8, 2),
        (16, 1),
        (24, 63),
        (32, 0),
        (36, wire::ACK),
        (37, Kind::Numbers as u8),
        (40, 2),
        (48, 1),
        (95, 1),
    ] {
        let (mut app, s) = fixture(Kind::Text, &[b"/readme.txt"]);
        s.borrow_mut().control_mutation = Some((at, byte));
        assert!(drive(&mut app, &s, 1).is_err(), "{at}/{byte}");
        assert!(s.borrow().file_requests.is_empty());
        assert!(s.borrow().results.is_empty());
    }
}
#[test]
fn explicit_fault_requires_authenticated_job_and_never_performs_file_io() {
    let (mut app, s) = fixture(Kind::Text, &[]);
    s.borrow_mut().fault_job = true;
    for _ in 0..10 {
        if app.poll().unwrap() == Progress::FaultRequested {
            assert!(s.borrow().file_requests.is_empty());
            assert_eq!(app.state, State::Fault);
            return;
        }
    }
    panic!("fault job was not delivered");
}
#[test]
fn result_is_retained_until_ack_and_sequence_exhaustion_never_wraps() {
    let (mut app, s) = fixture(Kind::Text, &[b"/empty.txt"]);
    for _ in 0..100 {
        if app.state == State::Ack {
            break;
        }
        app.poll().unwrap();
    }
    assert_eq!(app.state, State::Ack);
    assert_eq!(app.sequence, 1);
    assert_eq!(s.borrow().results.len(), 1);
    // A result cannot be promoted to complete using a replayed job reply.
    s.borrow_mut().control_mutation = Some((36, wire::RUN));
    assert!(drive(&mut app, &s, 1).is_err());
    let (mut app, s) = fixture(Kind::Text, &[b"/empty.txt"]);
    app.sequence = u64::MAX - 1;
    app.output.sequence = app.sequence;
    assert_eq!(drive(&mut app, &s, 1), Err(Error::Sequence));
    assert_eq!(app.sequence, u64::MAX - 1);
}
