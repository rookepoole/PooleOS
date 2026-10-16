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
pub enum Completion {
    Exit(u32),
    Fault(u8),
    InvalidReturn(u8),
    Cancelled,
    CallLimit,
    CallCounterExhausted,
    Watchdog,
}
impl Completion {
    #[inline(always)]
    pub fn decode(value: u64) -> Result<Self, Error> {
        let detail = value as u32;
        Ok(match value >> 32 {
            1 => Self::Exit(detail),
            2 if matches!(
                detail,
                0 | 1 | 3 | 4 | 5 | 6 | 11 | 12 | 13 | 14 | 16 | 17 | 19
            ) =>
            {
                Self::Fault(detail as u8)
            }
            3 if (1..=3).contains(&detail) => Self::InvalidReturn(detail as u8),
            4 if detail == 0 => Self::Cancelled,
            5 if detail == 0 => Self::CallLimit,
            6 if detail == 0 => Self::CallCounterExhausted,
            7 if detail == 0 => Self::Watchdog,
            _ => return Err(Error::Transport),
        })
    }
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
    last_completion: Option<Completion>,
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
            last_completion: None,
        })
    }
    pub const fn last_completion(&self) -> Option<Completion> {
        self.last_completion
    }
    /// Exactly one bounded kernel call per step. A detached child is not complete;
    /// only a validated PCOMP1 terminal result can advance the restart sequence.
    pub fn step(&mut self, calls: &mut impl Calls) -> Result<bool, Error> {
        match self.state {
            State::Starting => match calls.invoke(19, self.factory, u64::from(self.sequence)) {
                (6, 0) => {}
                (0, handle) if typed(handle, 5) => self.state = State::Monitoring(handle),
                _ => return Err(Error::Transport),
            },
            State::Monitoring(handle) => match calls.invoke(20, handle, 0) {
                (6, 1..=4) => {}
                (0, value) => {
                    let completion = Completion::decode(value)?;
                    self.last_completion = Some(completion);
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
        let mut f = fake(20, CHILD, 0, (6, 1));
        assert_eq!(s.step(&mut f), Ok(false));
        f.result = (0, (1 << 32) | 100);
        assert_eq!(s.step(&mut f), Ok(false));
        let mut f = fake(19, FACTORY, 2, (0, CHILD + (1 << 32)));
        assert_eq!(s.step(&mut f), Ok(false));
        let mut f = fake(20, CHILD + (1 << 32), 0, (0, (1 << 32) | 100));
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
        for result in [(0, 0), (9, 0), (9, 1), (6, 0), (6, 5), (5, 0), (8, 0)] {
            let mut s = Supervisor::new(FACTORY, 2).unwrap();
            s.step(&mut fake(19, FACTORY, 1, (0, CHILD))).unwrap();
            assert_eq!(
                s.step(&mut fake(20, CHILD, 0, result)),
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
        assert_eq!(s.step(&mut fake(20, CHILD, 0, (0, 4 << 32))), Ok(true));
    }

    #[test]
    fn detachment_and_stop_progress_never_trigger_restart() {
        let mut s = Supervisor::new(FACTORY, 2).unwrap();
        s.step(&mut fake(19, FACTORY, 1, (0, CHILD))).unwrap();
        for progress in [1, 2, 3, 4, 4, 4] {
            assert_eq!(s.step(&mut fake(20, CHILD, 0, (6, progress))), Ok(false));
            assert_eq!(s.sequence, 1);
            assert_eq!(s.last_completion(), None);
        }
        assert_eq!(
            s.step(&mut fake(20, CHILD, 0, (0, (2 << 32) | 6))),
            Ok(false)
        );
        assert_eq!(s.sequence, 2);
        assert_eq!(s.last_completion(), Some(Completion::Fault(6)));
    }

    #[test]
    fn completion_encoding_rejects_unknown_tags_and_reserved_details() {
        for code in [0, 100, u32::MAX] {
            assert_eq!(
                Completion::decode((1 << 32) | u64::from(code)),
                Ok(Completion::Exit(code))
            );
        }
        for vector in [0, 1, 3, 4, 5, 6, 11, 12, 13, 14, 16, 17, 19] {
            assert_eq!(
                Completion::decode((2 << 32) | vector),
                Ok(Completion::Fault(vector as u8))
            );
        }
        for value in [
            0,
            1,
            8 << 32,
            u64::MAX,
            (2 << 32) | 2,
            (2 << 32) | 256,
            3 << 32,
            (3 << 32) | 4,
            (4 << 32) | 1,
            (5 << 32) | 64,
            (6 << 32) | 1,
            (7 << 32) | 1,
        ] {
            assert_eq!(Completion::decode(value), Err(Error::Transport));
        }
        for (tag, completion) in [
            (4, Completion::Cancelled),
            (5, Completion::CallLimit),
            (6, Completion::CallCounterExhausted),
            (7, Completion::Watchdog),
        ] {
            assert_eq!(Completion::decode(tag << 32), Ok(completion));
        }
        for detail in 1..=3 {
            assert_eq!(
                Completion::decode((3 << 32) | detail),
                Ok(Completion::InvalidReturn(detail as u8))
            );
        }
    }
}
