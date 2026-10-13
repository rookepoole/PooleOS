use super::*;
struct Fake {
    response: (u64, u64),
    slot: u64,
    reply: u64,
    calls: usize,
}
impl Calls for Fake {
    fn invoke(&mut self, number: u64, _: u64, wire: &mut [u8]) -> (u64, u64) {
        self.calls += 1;
        if number == 7 {
            wire[..8].copy_from_slice(&self.slot.to_le_bytes());
            wire[8..16].copy_from_slice(&1u64.to_le_bytes());
            wire[16..24].copy_from_slice(&self.reply.to_le_bytes());
            wire[24..32].copy_from_slice(&64u64.to_le_bytes());
            return (0, 96);
        }
        self.response
    }
}
fn fake(response: (u64, u64), slot: u64) -> Fake {
    Fake {
        response,
        slot,
        reply: 0x100020001,
        calls: 0,
    }
}
#[test]
fn waiting_request_requires_exact_success_and_a_caller_owned_request_token() {
    assert_eq!(
        begin(1, &mut fake((0, 0x100030001), 4)),
        Ok(Some(0x100030001))
    );
    assert_eq!(begin(1, &mut fake((6, 0), 4)), Ok(None));
    for value in [
        (0, 0),
        (0, 0x100020001),
        (0, 0x100030000),
        (0, 0x30001),
        (5, 0),
        (6, 1),
        (9, 0),
    ] {
        assert_eq!(begin(1, &mut fake(value, 4)), Err(Error::Transport));
    }
}
#[test]
fn vanished_waiting_requester_requires_denied_late_reply() {
    let mut calls = CheckedReplies::new(fake((5, 0), 4));
    assert_eq!(calls.invoke(7, 1, &mut [0; 96]), (0, 96));
    assert!(calls.expect_denied);
    assert_eq!(calls.invoke(8, 0x100020001, &mut [0; 64]), (5, 0));
    assert!(!calls.expect_denied && !calls.failed);
}
#[test]
fn false_reply_success_or_other_status_fails_and_stops_further_calls() {
    for response in [(0, 64), (0, 0), (5, 1), (6, 0), (9, 0), (255, 0)] {
        let mut calls = CheckedReplies::new(fake(response, 4));
        calls.invoke(7, 1, &mut [0; 96]);
        assert_eq!(calls.invoke(8, 1, &mut [0; 64]), (255, 0));
        let count = calls.inner.calls;
        assert_eq!(calls.invoke(7, 1, &mut [0; 96]), (255, 0));
        assert_eq!(calls.inner.calls, count);
    }
}
#[test]
fn other_clients_keep_ordinary_success_and_backpressure_semantics() {
    for slot in [0, 3, 5] {
        for response in [(0, 64), (6, 0), (5, 0)] {
            let mut calls = CheckedReplies::new(fake(response, slot));
            calls.invoke(7, 1, &mut [0; 96]);
            assert!(!calls.expect_denied);
            assert_eq!(calls.invoke(8, 1, &mut [0; 64]), response);
            assert!(!calls.failed);
        }
    }
}
#[test]
fn untracked_text_message_never_creates_an_expected_reply() {
    let mut f = fake((0, 64), 4);
    f.reply = 0;
    let mut calls = CheckedReplies::new(f);
    calls.invoke(7, 1, &mut [0; 96]);
    assert!(!calls.expect_denied);
}
struct Versions {
    count: usize,
    fail: Option<usize>,
}
impl crate::supervisor::Calls for Versions {
    fn invoke(&mut self, n: u64, h: u64, a: u64) -> (u64, u64) {
        assert_eq!((n, h, a), (0, 0, 0));
        self.count += 1;
        if self.fail == Some(self.count) {
            (3, 0)
        } else {
            (0, 1)
        }
    }
}
#[test]
fn pacing_uses_exact_bounded_version_queries_and_rejects_each_failure() {
    let mut calls = Versions {
        count: 0,
        fail: None,
    };
    assert_eq!(pace(&mut calls), Ok(()));
    assert_eq!(calls.count, 64);
    for at in 1..=64 {
        let mut calls = Versions {
            count: 0,
            fail: Some(at),
        };
        assert_eq!(pace(&mut calls), Err(Error::Transport));
        assert_eq!(calls.count, at);
    }
}
