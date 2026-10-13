use super::*;
#[test]
fn all_phases_and_signed_results_round_trip_with_canonical_padding() {
    for kind in [Kind::Text, Kind::Numbers] {
        for phase in [READY, RUN, ACK, FAULT] {
            let mut f = Frame::empty(phase, kind, 7);
            if phase == RUN {
                f.len = 2;
                f.data[..2].copy_from_slice(b"/x");
            }
            assert_eq!(Frame::decode(&f.encode()), Some(f));
        }
        let f = Frame::result(kind, 8, Ok([2, -1, i32::MIN as i64, i32::MAX as i64]));
        assert_eq!(Frame::decode(&f.encode()), Some(f));
        assert_eq!(f.values(), Some([2, -1, i32::MIN as i64, i32::MAX as i64]));
        for status in 1..=UNAVAILABLE {
            let f = Frame::result(kind, 9, Err(status));
            assert_eq!(Frame::decode(&f.encode()), Some(f));
            assert_eq!(f.values(), None);
        }
    }
}
#[test]
fn malformed_frames_and_ambiguous_payloads_reject() {
    let base = Frame::empty(READY, Kind::Text, 1).encode();
    for (at, byte) in [
        (0, 0),
        (4, 0),
        (4, 6),
        (5, 0),
        (5, 3),
        (6, 1),
        (7, 1),
        (7, 41),
        (8, 0),
        (16, 1),
        (23, 1),
        (24, 1),
        (63, 1),
    ] {
        let mut bad = base;
        bad[at] = byte;
        assert!(Frame::decode(&bad).is_none(), "{at}/{byte}");
    }
    for length in 0..64 {
        assert!(Frame::decode(&base[..length]).is_none());
    }
    let mut bad = base;
    bad[8..16].fill(255);
    assert!(Frame::decode(&bad).is_none());
    let result = Frame::result(Kind::Numbers, 1, Ok([0; 4])).encode();
    for (at, byte) in [(6, 2), (7, 0), (7, 31), (7, 33), (56, 1)] {
        let mut bad = result;
        bad[at] = byte;
        assert!(Frame::decode(&bad).is_none());
    }
}
