use super::*;
fn read(path: &[u8], offset: u32) -> Frame {
    let mut request = Frame::empty(READ, 7, offset);
    request.len = path.len() as u8;
    request.data[..path.len()].copy_from_slice(path);
    answer(&request.encode())
}
#[test]
fn listing_and_multichunk_reads_match_exact_bundle() {
    for index in 0..ENTRIES {
        let (path, bytes) = entry(index).unwrap();
        let list = answer(&Frame::empty(LIST, 1, index).encode());
        assert_eq!(list.status, OK);
        assert_eq!(list.payload(), Some(path));
        assert_eq!(list.total as usize, bytes.len());
        let mut got = std::vec::Vec::new();
        loop {
            let reply = read(path, got.len() as u32);
            assert_eq!(reply.status, OK);
            assert_eq!(reply.total as usize, bytes.len());
            assert_eq!(Frame::decode(&reply.encode()), Some(reply));
            got.extend_from_slice(reply.payload().unwrap());
            if got.len() == bytes.len() {
                break;
            }
        }
        assert_eq!(got, bytes);
        assert_eq!(read(path, bytes.len() as u32).len, 0);
        assert_eq!(read(path, bytes.len() as u32 + 1).status, RANGE);
        assert_eq!(read(path, u32::MAX).status, RANGE);
    }
}
#[test]
fn paths_are_exact_canonical_flat_and_never_host_paths() {
    for path in [
        &b""[..],
        b"/",
        b"../x",
        b"/../x",
        b"/a/../x",
        b"/a//x",
        b"/a\\b",
        b"/A",
        b"/.a",
        b"/a..b",
        b"/a\0b",
        b"/a b",
        b"C:/file",
        b"/%2e%2e",
        b"/\xff",
    ] {
        assert!(!valid_path(path), "{path:?}");
        assert_eq!(read(path, 0).status, INVALID);
    }
    assert!(!valid_path(&[b'a'; 41]));
    assert_eq!(read(b"/missing.txt", 0).status, NOT_FOUND);
    assert_eq!(read(b"/empty.txt", 0).payload(), Some(&b""[..]));
}
#[test]
fn malformed_frames_and_reserved_bytes_fail_closed_without_panics() {
    let wire = Frame::empty(LIST, 3, 0).encode();
    for length in 0..BYTES {
        assert!(Frame::decode(&wire[..length]).is_none());
    }
    for at in [0, 1, 2, 3, 4, 5, 6, 7, 24, 63] {
        let mut bad = wire;
        bad[at] = 255;
        assert!(Frame::decode(&bad).is_none(), "{at}");
        assert_eq!(answer(&bad).status, INVALID);
    }
    for sequence in [0, u64::MAX] {
        assert!(Frame::decode(&Frame::empty(READ, sequence, 0).encode()).is_none());
    }
}
#[test]
fn request_fields_and_listing_end_are_strict() {
    assert_eq!(answer(&Frame::empty(LIST, 1, ENTRIES).encode()).status, END);
    assert_eq!(
        answer(&Frame::empty(LIST, 1, ENTRIES + 1).encode()).status,
        RANGE
    );
    assert_eq!(
        answer(&Frame::empty(LIST, 1, u32::MAX).encode()).status,
        RANGE
    );
    for field in 0..3 {
        let mut request = Frame::empty(LIST, 1, 0);
        match field {
            0 => request.total = 1,
            1 => request.status = END,
            _ => request.len = 1,
        }
        assert_eq!(answer(&request.encode()).status, INVALID);
    }
}
