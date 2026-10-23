use super::*;
use crate::desktop::{application_input::Queues, surfaces::Surfaces};

#[test]
fn scratch_text_edits_in_app_and_computes_exact_bytes_without_persistence() {
    let mut d = Draft::new();
    for &b in b"PooleOX\x08S native" {
        assert!(d.key(Kind::Text, b).is_none());
    }
    assert_eq!(d.key(Kind::Text, b'\r'), Some(Ok([14, 2, 0, 0])));
    assert_eq!(&d.row(0).data[..14], b"PooleOS native");
    d.key(Kind::Text, 3);
    assert_eq!(d.used, 0);
    assert!(d.bytes.iter().all(|&b| b == 0));
}

#[test]
fn numeric_input_reuses_checked_accumulator_with_bounded_separators() {
    for (text, expected) in [
        (&b"3, -2 8"[..], Ok([3, 9, -2, 8])),
        (
            &b"-2147483648,2147483647"[..],
            Ok([2, -1, -2147483648, 2147483647]),
        ),
        (&b"2147483648"[..], Err(apps::INVALID_DATA)),
        (&b"-2147483649"[..], Err(apps::INVALID_DATA)),
        (&b"3+8"[..], Err(apps::INVALID_DATA)),
    ] {
        let mut d = Draft::new();
        for &b in text {
            d.key(Kind::Numbers, b);
        }
        assert_eq!(d.key(Kind::Numbers, b'\r'), Some(expected));
    }
}

#[test]
fn draft_limit_and_transport_reset_never_execute_a_truncated_numeric_input() {
    let mut d = Draft::new();
    for _ in 0..49 {
        d.key(Kind::Numbers, b'1');
    }
    assert_eq!((d.used, d.blocked, d.lost), (0, true, 1));
    assert_eq!(&d.row(0).data[..11], b"Input limit");
    d.key(Kind::Numbers, b'7');
    assert_eq!(d.key(Kind::Numbers, b'\r'), Some(Err(apps::LIMIT)));
    d.key(Kind::Numbers, b'3');
    assert_eq!(d.key(Kind::Numbers, b'\r'), Some(Ok([1, 3, 3, 3])));
    d.reset();
    assert_eq!(&d.row(0).data[..11], b"Input reset");
    assert!(d.bytes.iter().all(|&b| b == 0));
    d.key(Kind::Numbers, b'4');
    assert_eq!(d.key(Kind::Numbers, b'\r'), Some(Ok([1, 4, 4, 4])));
}

struct Bridge<'a> {
    surfaces: Surfaces<'a>,
    input: Queues,
    reply: Option<Frame>,
    requests: usize,
    stall: bool,
}
impl<'a> Bridge<'a> {
    fn new(cells: &'a mut [u8; 384]) -> Self {
        Self {
            surfaces: Surfaces::new(cells),
            input: Queues::new(),
            reply: None,
            requests: 0,
            stall: false,
        }
    }
    fn keys(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.input.push(0, b);
        }
    }
}
impl Calls for Bridge<'_> {
    fn invoke(&mut self, n: u64, _: u64, w: &mut [u8]) -> (u64, u64) {
        match n {
            10 => {
                assert!(self.reply.is_none());
                self.requests += 1;
                let f = Frame::decode_mode::<true>(w).unwrap();
                let reply = if f.op == INPUT {
                    let (mut r, index) = self.surfaces.input_request(4, 1, f);
                    if let Some(i) = index {
                        self.input.drain(i, &self.surfaces, &mut r);
                    }
                    r
                } else {
                    self.surfaces.apply(4, 1, f).0
                };
                self.input.sync(&self.surfaces);
                self.reply = Some(reply);
                (0, 0x100030001)
            }
            11 if self.stall => (6, 0),
            11 => {
                let reply = self.reply.take().unwrap();
                w.fill(0);
                w[..8].copy_from_slice(&2u64.to_le_bytes());
                w[8..16].copy_from_slice(&1u64.to_le_bytes());
                w[24..32].copy_from_slice(&64u64.to_le_bytes());
                reply.encode_into((&mut w[32..]).try_into().unwrap());
                (0, 96)
            }
            _ => panic!(),
        }
    }
}
fn run(p: &mut Interactive, b: &mut Bridge<'_>, n: usize) {
    for _ in 0..n {
        p.poll(b).unwrap();
    }
}

#[test]
fn input_reply_backpressure_never_retargets_or_reapplies_a_batch() {
    let mut cells = [0; 384];
    let mut b = Bridge::new(&mut cells);
    let mut p = Interactive::new(1, Kind::Text);
    run(&mut p, &mut b, 20);
    b.keys(b"first");
    b.stall = true;
    p.poll(&mut b).unwrap();
    let requests = b.requests;
    let reply = b.reply;
    b.keys(b" second");
    run(&mut p, &mut b, 20);
    assert_eq!(b.requests, requests);
    assert_eq!(b.reply, reply);
    assert_eq!(p.draft.used, 0);
    b.stall = false;
    run(&mut p, &mut b, 15);
    assert_eq!(&p.draft.bytes[..p.draft.used], b"first second");
    b.keys(b"\r");
    run(&mut p, &mut b, 20);
    assert_eq!(p.base.active.values, [12, 2, 0, 0]);
    assert_eq!(&b.surfaces.cells(0).unwrap()[144..156], b"first second");
}

#[test]
fn file_result_publication_preserves_app_owned_draft_and_rpc_sequence() {
    let mut cells = [0; 384];
    let mut b = Bridge::new(&mut cells);
    let mut p = Interactive::new(1, Kind::Text);
    run(&mut p, &mut b, 20);
    b.keys(b"note");
    run(&mut p, &mut b, 10);
    p.observe(wire::Frame::result(Kind::Text, 2, Ok([37, 5, 1, 0])));
    run(&mut p, &mut b, 20);
    assert_eq!(p.base.active.values, [37, 5, 1, 0]);
    assert_eq!(p.base.active.sequence, 2);
    assert_eq!(&b.surfaces.cells(0).unwrap()[144..148], b"note");
    b.keys(b"\r");
    run(&mut p, &mut b, 20);
    assert_eq!(p.base.active.values, [4, 1, 0, 0]);
    p.observe(wire::Frame::result(Kind::Text, 3, Ok([153, 23, 3, 0])));
    run(&mut p, &mut b, 20);
    assert_eq!(p.base.active.values, [153, 23, 3, 0]);
    assert_eq!(&b.surfaces.cells(0).unwrap()[144..148], b"note");
}

#[test]
fn malformed_reset_payload_fails_closed_without_new_surface_requests() {
    let mut cells = [0; 384];
    let mut b = Bridge::new(&mut cells);
    let mut p = Interactive::new(1, Kind::Text);
    run(&mut p, &mut b, 20);
    b.stall = true;
    p.poll(&mut b).unwrap();
    let reply = b.reply.as_mut().unwrap();
    assert_eq!(reply.op, INPUT);
    reply.offset = RESET;
    reply.len = 1;
    reply.data[0] = b'X';
    b.stall = false;
    assert!(p.poll(&mut b).is_err());
    let requests = b.requests;
    for _ in 0..20 {
        assert!(p.poll(&mut b).is_err());
    }
    assert_eq!(b.requests, requests);
    assert_eq!(p.draft.used, 0);
}
