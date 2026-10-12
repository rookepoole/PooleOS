//! Bounded user-owned restart policy. Kernel launch completion is not liveness.
#![forbid(unsafe_code)]

pub trait Calls {
    fn invoke(&mut self, number: u64, handle: u64, argument: u64) -> (u64, u64);
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Policy,
    Transport,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Starting,
    Monitoring(u64),
    Finished,
}
pub struct Supervisor {
    factory: u64,
    sequence: u32,
    limit: u32,
    state: State,
}
#[inline(always)]
fn typed(handle: u64, tag: u64) -> bool {
    handle >> 32 != 0 && handle & 0xffff0000 == tag << 16 && handle & 0xffff != 0
}
impl Supervisor {
    #[inline(always)]
    pub fn new(factory: u64, limit: u32) -> Result<Self, Error> {
        if !typed(factory, 6) || !(1..=16).contains(&limit) {
            return Err(Error::Policy);
        }
        Ok(Self {
            factory,
            sequence: 1,
            limit,
            state: State::Starting,
        })
    }
    /// Exactly one bounded kernel call per step. Revocation means detached, not
    /// necessarily reclaimed; the launch dispatcher must enforce actual Slot reuse.
    pub fn step(&mut self, calls: &mut impl Calls) -> Result<bool, Error> {
        match self.state {
            State::Starting => match calls.invoke(19, self.factory, u64::from(self.sequence)) {
                (6, 0) => {}
                (0, handle) if typed(handle, 5) => self.state = State::Monitoring(handle),
                _ => return Err(Error::Transport),
            },
            State::Monitoring(handle) => match calls.invoke(17, handle, 0) {
                (0, 1) => {}
                (9, 0) => {
                    if self.sequence == self.limit {
                        self.state = State::Finished;
                    } else {
                        self.sequence = self.sequence.checked_add(1).ok_or(Error::Policy)?;
                        self.state = State::Starting;
                    }
                }
                _ => return Err(Error::Transport),
            },
            State::Finished => {}
        }
        Ok(self.state == State::Finished)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    struct Fake {
        expected: (u64, u64, u64),
        result: (u64, u64),
        calls: usize,
    }
    impl Calls for Fake {
        fn invoke(&mut self, n: u64, h: u64, a: u64) -> (u64, u64) {
            assert_eq!((n, h, a), self.expected);
            self.calls += 1;
            self.result
        }
    }
    const FACTORY: u64 = 0x100060001;
    const CHILD: u64 = 0x100050001;
    fn fake(n: u64, h: u64, a: u64, result: (u64, u64)) -> Fake {
        Fake {
            expected: (n, h, a),
            result,
            calls: 0,
        }
    }
    #[test]
    fn numbered_launch_polls_once_per_step_then_monitors_actual_child() {
        let mut s = Supervisor::new(FACTORY, 2).unwrap();
        let mut f = fake(19, FACTORY, 1, (6, 0));
        for _ in 0..4 {
            assert_eq!(s.step(&mut f), Ok(false));
        }
        assert_eq!(f.calls, 4);
        f.result = (0, CHILD);
        assert_eq!(s.step(&mut f), Ok(false));
        let mut f = fake(17, CHILD, 0, (0, 1));
        assert_eq!(s.step(&mut f), Ok(false));
        f.result = (9, 0);
        assert_eq!(s.step(&mut f), Ok(false));
        let mut f = fake(19, FACTORY, 2, (0, CHILD + (1 << 32)));
        assert_eq!(s.step(&mut f), Ok(false));
        let mut f = fake(17, CHILD + (1 << 32), 0, (9, 0));
        assert_eq!(s.step(&mut f), Ok(true));
        assert_eq!(s.step(&mut f), Ok(true));
        assert_eq!(f.calls, 1);
    }
    #[test]
    fn malformed_transport_never_advances_or_creates_authority() {
        for result in [
            (0, 0),
            (0, FACTORY),
            (6, 1),
            (5, 0),
            (8, 0),
            (9, 0),
            (u64::MAX, 0),
        ] {
            let mut s = Supervisor::new(FACTORY, 2).unwrap();
            assert_eq!(
                s.step(&mut fake(19, FACTORY, 1, result)),
                Err(Error::Transport)
            );
            assert_eq!(s.state, State::Starting);
            assert_eq!(s.sequence, 1);
        }
    }
    #[test]
    fn malformed_inspection_never_triggers_a_restart() {
        for result in [(0, 0), (9, 1), (6, 0), (5, 0), (8, 0)] {
            let mut s = Supervisor::new(FACTORY, 2).unwrap();
            s.step(&mut fake(19, FACTORY, 1, (0, CHILD))).unwrap();
            assert_eq!(
                s.step(&mut fake(17, CHILD, 0, result)),
                Err(Error::Transport)
            );
            assert_eq!(s.state, State::Monitoring(CHILD));
            assert_eq!(s.sequence, 1);
        }
    }
    #[test]
    fn policy_limit_and_handle_type_fail_closed() {
        for h in [0, 1, CHILD, 0x60001, 0x100060000] {
            assert!(Supervisor::new(h, 2).is_err());
        }
        for limit in [0, 17, u32::MAX] {
            assert!(Supervisor::new(FACTORY, limit).is_err());
        }
        let mut s = Supervisor::new(FACTORY, 1).unwrap();
        s.step(&mut fake(19, FACTORY, 1, (0, CHILD))).unwrap();
        assert_eq!(s.step(&mut fake(17, CHILD, 0, (9, 0))), Ok(true));
    }
}
