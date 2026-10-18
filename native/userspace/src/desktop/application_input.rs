//! Fixed, generation-bound application queues. Only trusted focus supplies input.
#![forbid(unsafe_code)]
use super::surfaces::{Frame, Surfaces};

pub const INPUT: u8 = 5;
pub const CAPACITY: usize = 64;
pub const RESET: u16 = 1;

#[inline]
pub fn valid_key(byte: u8) -> bool {
    matches!(byte, 3 | 8 | 13 | 32..=126)
}

#[derive(Clone, Copy)]
struct Queue {
    identity: Option<(u32, u64)>,
    bytes: [u8; CAPACITY],
    head: usize,
    len: usize,
    cancel: bool,
    discard: bool,
}
impl Queue {
    const EMPTY: Self = Self {
        identity: None,
        bytes: [0; CAPACITY],
        head: 0,
        len: 0,
        cancel: false,
        discard: false,
    };
    #[inline(always)]
    fn new() -> Self {
        // Keep freestanding initialization local, without an external memset.
        Self {
            head: core::hint::black_box(0),
            ..Self::EMPTY
        }
    }
    #[inline]
    fn clear(&mut self) {
        for b in self.bytes.iter_mut() {
            *b = core::hint::black_box(0);
        }
        self.head = 0;
        self.len = 0;
    }
    #[inline]
    fn cancel(&mut self) {
        self.clear();
        self.cancel = true;
        self.discard = true;
    }
}

/// The decoder still owns characters/modifiers; this fence only suppresses keys
/// already physically held at a focus/lifetime boundary until their release.
pub struct Fence {
    held: [u64; 4],
    blocked: [u64; 4],
    extended: bool,
    pause: u8,
    discard_next: bool,
}
impl Fence {
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            held: [0; 4],
            blocked: [0; 4],
            extended: false,
            pause: 0,
            discard_next: false,
        }
    }
    #[inline]
    pub fn boundary(&mut self) {
        for i in 0..4 {
            self.blocked[i] |= self.held[i];
        }
        self.discard_next |= self.extended;
    }
    #[inline]
    fn reset_stream(&mut self) {
        self.boundary();
        self.extended = false;
        self.pause = 0;
        self.discard_next = false;
    }
    #[inline]
    pub fn feed(&mut self, code: u8) -> bool {
        if self.pause != 0 {
            self.pause -= 1;
            return false;
        }
        if code == 0xe1 {
            self.pause = 5;
            self.extended = false;
            self.discard_next = false;
            return false;
        }
        if code == 0xe0 {
            self.extended = true;
            return true;
        }
        let index = usize::from(code & 0x7f) + 128 * usize::from(self.extended);
        self.extended = false;
        let word = index / 64;
        let bit = 1u64 << (index % 64);
        let discard = self.discard_next;
        self.discard_next = false;
        if code & 0x80 != 0 {
            self.held[word] &= !bit;
            self.blocked[word] &= !bit;
            return !discard;
        }
        self.held[word] |= bit;
        if discard {
            self.blocked[word] |= bit;
        }
        self.blocked[word] & bit == 0
    }
}

pub struct Queues {
    // Separate fields avoid an address-bearing bulk-copy helper for a queue array.
    first: Queue,
    second: Queue,
    pub fence: Fence,
    pub(super) quarantined: bool,
}
impl Queues {
    #[inline(always)]
    pub fn new() -> Self {
        Self {
            first: Queue::new(),
            second: Queue::new(),
            fence: Fence::new(),
            quarantined: false,
        }
    }
    #[inline]
    fn queue(&mut self, index: usize) -> Option<&mut Queue> {
        match index {
            0 => Some(&mut self.first),
            1 => Some(&mut self.second),
            _ => None,
        }
    }
    /// Synchronization clears bytes, cancellation and tokens from an old lifetime.
    #[inline]
    pub fn sync(&mut self, surfaces: &Surfaces<'_>) -> u8 {
        let mut changed = 0;
        for (i, q) in [&mut self.first, &mut self.second].into_iter().enumerate() {
            let identity = surfaces.identity(i);
            if q.identity != identity {
                q.clear();
                q.identity = identity;
                q.cancel = false;
                q.discard = false;
                changed |= 1 << i;
            }
        }
        changed
    }
    #[inline]
    pub fn push(&mut self, index: usize, byte: u8) {
        let Some(q) = self.queue(index) else { return };
        if q.identity.is_none() || !valid_key(byte) {
            return;
        }
        if q.discard {
            if byte == b'\r' {
                q.discard = false;
            }
            return;
        }
        if q.len == CAPACITY {
            q.cancel();
            q.discard = byte != b'\r';
            return;
        }
        q.bytes[q.head.wrapping_add(q.len) % CAPACITY] = byte;
        q.len = q.len.saturating_add(1);
    }
    #[inline]
    pub fn focus_lost(&mut self, focus: Option<usize>) {
        if let Some(q) = focus
            .and_then(|i| i.checked_sub(1))
            .and_then(|i| self.queue(i))
        {
            if q.len != 0 {
                q.cancel();
            }
        }
        self.fence.boundary();
    }
    #[inline]
    pub fn reset(&mut self) {
        for q in [&mut self.first, &mut self.second] {
            if q.identity.is_some() {
                q.cancel();
            }
        }
        // Retain known held keys until their breaks, even after controller reset.
        self.fence.reset_stream();
    }
    /// Called only after the surface has authenticated and consumed the request.
    #[inline]
    pub fn drain(&mut self, index: usize, surfaces: &Surfaces<'_>, reply: &mut Frame) {
        self.sync(surfaces);
        let Some(q) = self.queue(index) else { return };
        if q.identity.is_none() {
            return;
        }
        if q.cancel {
            q.cancel = false;
            reply.offset = RESET;
            return;
        }
        let n = q.len.min(32);
        for out in reply.data.iter_mut().take(n) {
            let head = q.head % CAPACITY;
            *out = q.bytes[head];
            q.bytes[head] = 0;
            q.head = head.wrapping_add(1) % CAPACITY;
        }
        q.len = q.len.saturating_sub(n);
        reply.len = n as u8;
    }
}

#[cfg(test)]
mod tests;
