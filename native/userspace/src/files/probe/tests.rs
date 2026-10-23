use super::*;
use std::vec::Vec;
struct Server {
    pending: Option<[u8; 64]>,
    seen: Vec<(u64, Vec<u8>)>,
    corrupt: Option<usize>,
    again: bool,
}
impl Calls for Server {
    fn invoke(&mut self, n: u64, _: u64, wire: &mut [u8]) -> (u64, u64) {
        self.seen.push((n, wire.to_vec()));
        if self.again {
            self.again = false;
            return (6, 0);
        }
        match n {
            3 => (0, wire.len() as u64),
            10 => {
                assert!(self.pending.is_none());
                self.pending = Some(super::super::answer(wire).encode());
                (0, 0x100030001)
            }
            11 => {
                let response = self.pending.take().unwrap();
                for (i, w) in [1u64, 1, 0, 64].iter().enumerate() {
                    wire[i * 8..i * 8 + 8].copy_from_slice(&w.to_le_bytes());
                }
                wire[32..].copy_from_slice(&response);
                if let Some(at) = self.corrupt {
                    wire[at] ^= 128;
                }
                (0, 96)
            }
            _ => panic!("unexpected call"),
        }
    }
}
fn server() -> Server {
    Server {
        pending: None,
        seen: Vec::new(),
        corrupt: None,
        again: false,
    }
}
#[test]
fn all_malformed_cases_are_distinct_and_have_bounded_error_contracts() {
    let mut seen = Vec::new();
    for case in 0..CASES {
        let mut wire = valid().encode();
        let len = malformed(case, &mut wire).unwrap();
        assert!(!seen.contains(&wire[..len].to_vec()));
        seen.push(wire[..len].to_vec());
        let reply = super::super::answer(&wire[..len]);
        assert_eq!(reply.status, if case == 12 { RANGE } else { INVALID });
        assert_eq!((reply.len, reply.total), (0, 0));
    }
    assert!(malformed(CASES, &mut valid().encode()).is_err());
}
#[test]
fn every_untracked_and_malformed_message_is_followed_by_a_valid_read_before_abandon() {
    let mut p = Probe::new(0x100010002, 0x100000001, server());
    for _ in 0..CASES * 5 {
        assert_eq!(p.poll(), Ok(Progress::Pending));
    }
    assert_eq!(p.poll(), Ok(Progress::AbandonOutstandingRequest));
    assert_eq!(p.case, CASES);
    assert_ne!(p.pending, 0);
    assert!(p.calls.pending.is_some());
    assert_eq!(p.calls.seen.iter().filter(|(n, _)| *n == 3).count(), 13);
    assert_eq!(p.calls.seen.iter().filter(|(n, _)| *n == 10).count(), 27);
    assert_eq!(p.calls.seen.iter().filter(|(n, _)| *n == 11).count(), 26);
    let count = p.calls.seen.len();
    assert!(p.poll().is_err());
    assert_eq!(count, p.calls.seen.len());
}
#[test]
fn malformed_or_foreign_completions_fail_without_further_requests() {
    for at in [0, 8, 16, 24, 32, 36, 39, 40, 48, 56, 95] {
        let mut s = server();
        s.corrupt = Some(at);
        let mut p = Probe::new(0x100010002, 0x100000001, s);
        p.poll().unwrap();
        p.poll().unwrap();
        assert!(p.poll().is_err());
        let count = p.calls.seen.len();
        assert!(p.poll().is_err());
        assert_eq!(p.calls.seen.len(), count);
    }
}
#[test]
fn backpressure_retains_the_exact_current_operation() {
    let mut p = Probe::new(0x100010002, 0x100000001, server());
    for _ in 0..5 {
        let state = p.state;
        p.calls.again = true;
        assert_eq!(p.poll(), Ok(Progress::Pending));
        assert_eq!(p.state, state);
        assert_eq!(p.poll(), Ok(Progress::Pending));
        assert_ne!(p.state, state);
    }
}
#[test]
fn polling_is_bounded_and_never_fabricates_a_successful_abandonment() {
    let mut p = Probe::new(0x100010002, 0x100000001, server());
    for _ in 0..MAX_POLLS {
        p.calls.again = true;
        assert_eq!(p.poll(), Ok(Progress::Pending));
    }
    assert_eq!(p.poll(), Err(Error::Sequence));
    assert_eq!(p.pending, 0);
}
