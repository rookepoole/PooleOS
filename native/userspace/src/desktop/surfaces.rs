//! PWS1 bounded client surfaces. Ownership is supplied only by kernel IPC envelopes.
#![forbid(unsafe_code)]
pub const WIDTH: usize = 24;
pub const HEIGHT: usize = 8;
pub const CELLS: usize = WIDTH * HEIGHT;
pub const STORAGE: usize = 2 * CELLS;
pub const BYTES: usize = 64;
pub const OPEN: u8 = 1;
pub const WRITE: u8 = 2;
pub const CLEAR: u8 = 3;
pub const CLOSE: u8 = 4;
pub const OK: u8 = 0;
pub const DENIED: u8 = 1;
pub const INVALID: u8 = 2;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Frame {
    pub op: u8,
    pub status: u8,
    pub sequence: u64,
    pub handle: u64,
    pub offset: u16,
    pub len: u8,
    pub data: [u8; 32],
}
impl Frame {
    #[inline(always)]
    pub const fn new(op: u8, sequence: u64, handle: u64) -> Self {
        Self {
            op,
            status: 0,
            sequence,
            handle,
            offset: 0,
            len: 0,
            data: [0; 32],
        }
    }
    #[inline(always)]
    pub fn encode(&self) -> [u8; BYTES] {
        let mut b = [0; BYTES];
        self.encode_into(&mut b);
        b
    }
    #[inline(always)]
    pub fn encode_into(&self, b: &mut [u8; BYTES]) {
        for byte in b.iter_mut() {
            *byte = core::hint::black_box(0);
        }
        b[..4].copy_from_slice(b"PWS1");
        b[4] = self.op;
        b[5] = self.status;
        b[6] = self.len;
        b[8..16].copy_from_slice(&self.sequence.to_le_bytes());
        b[16..24].copy_from_slice(&self.handle.to_le_bytes());
        b[24..26].copy_from_slice(&self.offset.to_le_bytes());
        for (out, &byte) in b[32..].iter_mut().zip(self.data.iter()) {
            *out = core::hint::black_box(byte);
        }
    }
    #[inline(always)]
    pub fn decode(b: &[u8]) -> Option<Self> {
        if b.len() != BYTES
            || &b[..4] != b"PWS1"
            || b[7] != 0
            || b[26..32].iter().any(|&v| v != 0)
            || !(OPEN..=CLOSE).contains(&b[4])
            || b[5] > INVALID
            || b[6] > 32
        {
            return None;
        }
        let f = Self {
            op: b[4],
            status: b[5],
            sequence: u64::from_le_bytes(b[8..16].try_into().ok()?),
            handle: u64::from_le_bytes(b[16..24].try_into().ok()?),
            offset: u16::from_le_bytes(b[24..26].try_into().ok()?),
            len: b[6],
            data: b[32..].try_into().ok()?,
        };
        if f.sequence == 0
            || f.sequence == u64::MAX
            || f.data[usize::from(f.len)..].iter().any(|&v| v != 0)
        {
            return None;
        }
        Some(f)
    }
}

#[derive(Clone, Copy)]
struct Owner {
    generation: u32,
    handle: u64,
    sequence: u64,
}
impl Owner {
    const EMPTY: Self = Self {
        generation: 0,
        handle: 0,
        sequence: 0,
    };
}
pub struct Surfaces<'a> {
    cells: &'a mut [u8; STORAGE],
    owners: [Owner; 2],
    next: u64,
}
impl<'a> Surfaces<'a> {
    #[inline(always)]
    pub fn new(cells: &'a mut [u8; STORAGE]) -> Self {
        for b in cells.iter_mut() {
            *b = core::hint::black_box(b' ');
        }
        Self {
            cells,
            owners: [Owner::EMPTY; 2],
            next: 0,
        }
    }
    #[inline]
    pub fn cells(&self, index: usize) -> Option<&[u8]> {
        self.cells
            .get(index.checked_mul(CELLS)?..index.checked_add(1)?.checked_mul(CELLS)?)
    }
    #[inline]
    pub fn generation(&self, index: usize) -> u32 {
        self.owners.get(index).map_or(0, |o| o.generation)
    }
    #[inline]
    pub fn open(&self, index: usize) -> bool {
        self.owners.get(index).is_some_and(|o| o.handle != 0)
    }
    /// Trusted lifecycle observation only, never a client-supplied PWS1 command.
    /// Keep the generation tombstone so late OPEN/WRITE cannot resurrect it.
    #[inline]
    pub fn retire(&mut self, index: usize, generation: u32) -> bool {
        if generation == 0
            || !self
                .owners
                .get(index)
                .is_some_and(|o| o.generation == generation && o.handle != 0)
        {
            return false;
        }
        self.clear(index);
        self.owners[index].handle = 0;
        true
    }
    #[inline]
    fn clear(&mut self, index: usize) {
        if let Some(c) = self
            .cells
            .get_mut(index.saturating_mul(CELLS)..index.saturating_add(1).saturating_mul(CELLS))
        {
            for b in c {
                *b = core::hint::black_box(b' ');
            }
        }
    }
    /// slot/generation are kernel-attested receive metadata, never payload fields.
    #[inline]
    pub fn apply(&mut self, slot: u64, generation: u64, f: Frame) -> (Frame, bool) {
        let mut reply = Frame::new(f.op, f.sequence, f.handle);
        reply.status = DENIED;
        if !(4..=5).contains(&slot) || generation == 0 || generation > u64::from(u32::MAX) {
            return (reply, false);
        }
        let index = (slot - 4) as usize;
        let Some(old) = self.owners.get(index).copied() else {
            return (reply, false);
        };
        let shape = f.status == 0
            && f.sequence != 0
            && f.sequence != u64::MAX
            && usize::from(f.len) <= 32
            && f.data
                .get(usize::from(f.len)..)
                .is_some_and(|d| d.iter().all(|&v| v == 0));
        if !shape {
            reply.status = INVALID;
            return (reply, false);
        }
        if f.op == OPEN {
            if f.handle != 0 || f.offset != 0 || f.len != 0 {
                reply.status = INVALID;
                return (reply, false);
            }
            if f.sequence != 1 || generation <= u64::from(old.generation) {
                return (reply, false);
            }
            let Some(next) = self.next.checked_add(1).filter(|&v| v != u64::MAX) else {
                return (reply, false);
            };
            self.clear(index);
            self.next = next;
            if let Some(owner) = self.owners.get_mut(index) {
                *owner = Owner {
                    generation: generation as u32,
                    handle: next,
                    sequence: 1,
                };
            }
            reply.handle = next;
            reply.status = OK;
            return (reply, true);
        }
        if generation != u64::from(old.generation)
            || old.handle == 0
            || f.handle != old.handle
            || old.sequence.checked_add(1) != Some(f.sequence)
        {
            return (reply, false);
        }
        match f.op {
            WRITE => {
                let offset = usize::from(f.offset);
                let len = usize::from(f.len);
                if len == 0
                    || offset.checked_add(len).is_none_or(|end| end > CELLS)
                    || !f.data[..len].iter().all(|&b| (32..=126).contains(&b))
                {
                    reply.status = INVALID;
                    return (reply, false);
                }
                let start = index * CELLS + offset;
                let Some(target) = self.cells.get_mut(start..start + len) else {
                    reply.status = INVALID;
                    return (reply, false);
                };
                for (out, &byte) in target.iter_mut().zip(f.data.iter()) {
                    *out = core::hint::black_box(byte);
                }
            }
            CLEAR | CLOSE if f.offset == 0 && f.len == 0 => self.clear(index),
            _ => {
                reply.status = INVALID;
                return (reply, false);
            }
        }
        if let Some(owner) = self.owners.get_mut(index) {
            owner.sequence = f.sequence;
            if f.op == CLOSE {
                owner.handle = 0;
            }
        }
        reply.status = OK;
        (reply, true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn client_generations_and_tokens_cannot_cross_write_or_replay() {
        let mut cells = [0; STORAGE];
        let mut s = Surfaces::new(&mut cells);
        let (a, _) = s.apply(4, 1, Frame::new(OPEN, 1, 0));
        let (b, _) = s.apply(5, 1, Frame::new(OPEN, 1, 0));
        assert_ne!(a.handle, b.handle);
        let mut f = Frame::new(WRITE, 2, a.handle);
        f.len = 1;
        f.data[0] = b'X';
        assert_eq!(s.apply(5, 1, f).0.status, DENIED);
        assert_eq!(s.apply(4, 2, f).0.status, DENIED);
        assert_eq!(s.apply(4, 1, f).0.status, OK);
        assert_eq!(s.apply(4, 1, f).0.status, DENIED);
        assert_eq!(s.cells(0).unwrap()[0], b'X');
        assert_eq!(s.cells(1).unwrap()[0], b' ');
        let (c, _) = s.apply(4, 2, Frame::new(OPEN, 1, 0));
        assert_ne!(a.handle, c.handle);
        assert_eq!(s.cells(0).unwrap()[0], b' ');
        assert_eq!(s.apply(4, 1, f).0.status, DENIED);
        assert_eq!(s.apply(4, 1, Frame::new(OPEN, 1, 0)).0.status, DENIED);
    }
    #[test]
    fn invalid_commands_are_transactional_and_close_never_recycles_tokens() {
        let mut cells = [0; STORAGE];
        let mut s = Surfaces::new(&mut cells);
        let h = s.apply(4, 1, Frame::new(OPEN, 1, 0)).0.handle;
        for (offset, len, byte) in [
            (192, 1, b'A'),
            (191, 2, b'A'),
            (0, 0, b'A'),
            (0, 33, b'A'),
            (0, 1, 0x1b),
        ] {
            let mut f = Frame::new(WRITE, 2, h);
            f.offset = offset;
            f.len = len;
            f.data[0] = byte;
            assert_ne!(s.apply(4, 1, f).0.status, OK);
            assert!(s.cells(0).unwrap().iter().all(|&v| v == b' '));
        }
        assert_eq!(s.apply(4, 1, Frame::new(CLOSE, 2, h)).0.status, OK);
        assert!(!s.open(0));
        assert_eq!(s.apply(4, 1, Frame::new(OPEN, 1, 0)).0.status, DENIED);
        assert_eq!(s.apply(4, 2, Frame::new(OPEN, 1, 0)).0.status, OK);
    }
    #[test]
    fn hostile_envelopes_generation_wrap_and_handle_exhaustion_fail_closed() {
        let mut cells = [0; STORAGE];
        let mut s = Surfaces::new(&mut cells);
        for (slot, generation) in [(0, 1), (3, 1), (6, 1), (4, 0), (4, u64::MAX)] {
            assert_eq!(
                s.apply(slot, generation, Frame::new(OPEN, 1, 0)).0.status,
                DENIED
            );
        }
        s.next = u64::MAX - 1;
        assert_eq!(s.apply(4, 1, Frame::new(OPEN, 1, 0)).0.status, DENIED);
        assert_eq!(s.generation(0), 0);
    }
    #[test]
    fn wire_is_exact_and_rejects_reserved_trailing_and_bad_sequence() {
        let f = Frame::new(OPEN, 1, 0);
        let good = f.encode();
        assert_eq!(Frame::decode(&good), Some(f));
        for index in [0, 4, 5, 6, 7, 26, 31, 32, 63] {
            let mut bad = good;
            bad[index] = 255;
            assert_eq!(Frame::decode(&bad), None);
        }
        assert_eq!(Frame::decode(&good[..63]), None);
        for seq in [0, u64::MAX] {
            assert_eq!(Frame::decode(&Frame::new(OPEN, seq, 0).encode()), None);
        }
    }
}
