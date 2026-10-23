//! Process observation hides unavailable surfaces; it does not reclaim memory.
#![forbid(unsafe_code)]
use super::surfaces::Surfaces;
use crate::{
    console::Error,
    supervisor::{Calls, Completion},
};

/// At most two read-only queries, independent of pending surface RPC replies.
/// Validate the complete observation batch before changing either surface.
#[inline(always)]
pub fn poll(surfaces: &mut Surfaces<'_>, calls: &mut impl Calls) -> Result<u8, Error> {
    let generations = [surfaces.generation(0), surfaces.generation(1)];
    let mut retired = 0;
    for i in 0..2 {
        let generation = generations[i];
        if !surfaces.open(i) {
            continue;
        }
        let unavailable = match calls.invoke(27, (i + 4) as u64, u64::from(generation)) {
            (6, 1..=3) => false,
            (6, 4) | (9, 0) => true,
            (0, value) => {
                Completion::decode(value).map_err(|_| Error::Transport)?;
                true
            }
            _ => return Err(Error::Transport),
        };
        if unavailable {
            retired |= 1 << i;
        }
    }
    for i in 0..2 {
        let generation = generations[i];
        if retired & (1 << i) != 0 && !surfaces.retire(i, generation) {
            return Err(Error::Transport);
        }
    }
    Ok(retired)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::desktop::surfaces::{DENIED, Frame, OPEN, WRITE};
    struct Observe {
        replies: [(u64, u64); 2],
        seen: usize,
    }
    impl Calls for Observe {
        fn invoke(&mut self, n: u64, slot: u64, generation: u64) -> (u64, u64) {
            assert_eq!(n, 27);
            assert!((4..=5).contains(&slot));
            assert_eq!(generation, 1);
            self.seen += 1;
            self.replies[(slot - 4) as usize]
        }
    }
    fn open(s: &mut Surfaces<'_>, slot: u64, generation: u64) -> Frame {
        let reply = s.apply(slot, generation, Frame::new(OPEN, 1, 0)).0;
        let mut write = Frame::new(WRITE, 2, reply.handle);
        write.len = 1;
        write.data[0] = b'X';
        assert_eq!(s.apply(slot, generation, write).0.status, 0);
        write
    }
    #[test]
    fn exact_retirement_keeps_tombstone_and_cannot_cross_close_a_restart() {
        let mut cells = [0; 384];
        let mut s = Surfaces::new(&mut cells);
        let old = open(&mut s, 4, 1);
        open(&mut s, 5, 1);
        let mut c = Observe {
            replies: [(0, (2 << 32) | 6), (6, 1)],
            seen: 0,
        };
        assert_eq!(poll(&mut s, &mut c), Ok(1));
        assert_eq!(c.seen, 2);
        assert!(!s.open(0));
        assert_eq!(s.generation(0), 1);
        assert!(s.cells(0).unwrap().iter().all(|&b| b == b' '));
        assert_eq!(s.cells(1).unwrap()[0], b'X');
        assert!(s.open(1));
        assert_eq!(s.apply(4, 1, old).0.status, DENIED);
        assert_eq!(s.apply(4, 1, Frame::new(OPEN, 1, 0)).0.status, DENIED);
        open(&mut s, 4, 2);
        for (index, generation) in [(0, 0), (0, 1), (0, 3), (2, 2), (usize::MAX, 2)] {
            assert!(!s.retire(index, generation));
        }
        assert!(s.open(0));
        assert_eq!(s.cells(0).unwrap()[0], b'X');
        assert!(s.retire(0, 2));
        assert!(!s.retire(0, 2));
        assert!(s.open(1));
    }
    #[test]
    fn detached_and_superseded_are_unavailable_not_completion_and_pending_stays_visible() {
        for (state, closed) in [
            ((6, 1), false),
            ((6, 2), false),
            ((6, 3), false),
            ((6, 4), true),
            ((9, 0), true),
            ((0, 4 << 32), true),
        ] {
            let mut cells = [0; 384];
            let mut s = Surfaces::new(&mut cells);
            open(&mut s, 4, 1);
            let mut c = Observe {
                replies: [state, (5, 0)],
                seen: 0,
            };
            assert_eq!(poll(&mut s, &mut c), Ok(u8::from(closed)));
            assert_eq!(s.open(0), !closed);
            assert_eq!(c.seen, 1);
            if closed {
                assert_eq!(poll(&mut s, &mut c), Ok(0));
                assert_eq!(c.seen, 1);
            }
        }
    }
    #[test]
    fn malformed_or_denied_second_observation_does_not_partially_retire_first() {
        for bad in [
            (5, 0),
            (9, 1),
            (6, 0),
            (6, 5),
            (0, 0),
            (0, (4 << 32) | 1),
            (0, 8 << 32),
            (u64::MAX, 0),
        ] {
            let mut cells = [0; 384];
            let mut s = Surfaces::new(&mut cells);
            open(&mut s, 4, 1);
            open(&mut s, 5, 1);
            let mut c = Observe {
                replies: [(0, 4 << 32), bad],
                seen: 0,
            };
            assert_eq!(poll(&mut s, &mut c), Err(Error::Transport));
            assert!(s.open(0) && s.open(1));
            assert_eq!(s.cells(0).unwrap()[0], b'X');
        }
    }
}
