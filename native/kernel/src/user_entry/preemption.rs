//! Fixed-profile CPL3 timer-frame admission; no hardware authority is created here.
#![forbid(unsafe_code)]

use super::prepared::STACK_TOP;
use super::{
    INITIAL_RFLAGS, ImageAdmission,
    privilege::{Error, FRAME_BYTES, Trap},
};
use crate::{
    interrupt_time::TIMER_VECTOR,
    virtual_memory::{USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START},
};

pub const CONTRACT_ID: &str = "PKUSER6";
pub const DELIVERIES: u32 = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Budget {
    pub count: u32,
    pub period_fs: u64,
    pub counter_mask: u64,
}

impl Budget {
    pub fn validate(self) -> Result<Self, Error> {
        if self.count == 0
            || !(100_000..=100_000_000).contains(&self.period_fs)
            || ![u64::MAX, u64::from(u32::MAX)].contains(&self.counter_mask)
        {
            return Err(Error::Hardware);
        }
        Ok(self)
    }

    pub fn elapsed(self, start: u64, now: u64) -> Result<u64, Error> {
        self.validate()?;
        let ticks = now.wrapping_sub(start) & self.counter_mask;
        if ticks == 0 || ticks > 100_000_000_000_000u64.div_ceil(self.period_fs) {
            return Err(Error::Hardware);
        }
        Ok(ticks)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Layout {
    pub increment: u64,
    pub pause: u64,
    pub jump: u64,
    pub end: u64,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Observation {
    pub deliveries: u32,
    pub resumes: u32,
    pub first_progress: u64,
    pub last_progress: u64,
}

pub struct Sequence {
    image: ImageAdmission,
    layout: Layout,
    registers: [u64; 15],
    observed: Observation,
}

impl Sequence {
    pub fn new(image: ImageAdmission, layout: Layout, registers: [u64; 15]) -> Result<Self, Error> {
        let f = image.initial_frame;
        if image.root_physical == 0
            || image.root_physical & 4095 != 0
            || image.root_generation == 0
            || f.rip < USER_WINDOW_START
            || f.rip >= USER_WINDOW_END_EXCLUSIVE - 4096
            || f.rip & 4095 != 16
            || f.rsp & 4095 != 0
            || f.rsp <= f.rip + 4096
            || f.rsp >= USER_WINDOW_END_EXCLUSIVE
            || f.rflags != INITIAL_RFLAGS
            || f.cs != super::USER_CODE_SELECTOR
            || f.ss != super::USER_DATA_SELECTOR
            || registers[0] != 0
            || layout.end > 4096 - 16
            || layout.increment >= layout.pause
            || layout.pause >= layout.jump
            || layout.jump >= layout.end
        {
            return Err(Error::Layout);
        }
        Ok(Self {
            image,
            layout,
            registers,
            observed: Observation::default(),
        })
    }

    pub fn observation(&self) -> Observation {
        self.observed
    }

    /// True terminates the spinning task. Rejection is atomic and never grants a resume.
    pub fn accept(&mut self, t: &Trap) -> Result<bool, Error> {
        if self.observed.deliveries >= DELIVERIES {
            return Err(Error::State);
        }
        let f = self.image.initial_frame;
        if t.root != self.image.root_physical
            || t.cs != f.cs
            || t.ss != f.ss
            // Event frames may carry RF. It grants no privilege; controlled resumes clear it.
            || t.flags & !(1 << 16) != INITIAL_RFLAGS
            || t.rsp != f.rsp
            || t.depth != 1
            || t.handler_stack != STACK_TOP - FRAME_BYTES
        {
            return Err(Error::Frame);
        }
        if t.vector != u64::from(TIMER_VECTOR)
            || t.error != 0
            || ![self.layout.increment, self.layout.pause, self.layout.jump]
                .into_iter()
                .any(|o| t.rip == f.rip + o)
        {
            return Err(Error::Fault);
        }
        let progress = t.registers[0];
        if t.registers[1..] != self.registers[1..]
            || progress == 0
            || progress <= self.observed.last_progress
        {
            return Err(Error::Registers);
        }
        if self.observed.deliveries == 0 {
            self.observed.first_progress = progress;
        }
        self.observed.last_progress = progress;
        self.observed.deliveries += 1;
        let terminal = self.observed.deliveries == DELIVERIES;
        if !terminal {
            self.observed.resumes += 1;
        }
        Ok(terminal)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn image() -> ImageAdmission {
        ImageAdmission {
            root_physical: 0x100000,
            root_generation: 1,
            code_physical: 0x200000,
            stack_physical: 0x210000,
            initial_frame: super::super::InitialReturnFrame {
                rip: USER_WINDOW_START + 16,
                cs: super::super::USER_CODE_SELECTOR,
                rflags: INITIAL_RFLAGS,
                rsp: USER_WINDOW_START + 4 * 4096,
                ss: super::super::USER_DATA_SELECTOR,
            },
        }
    }
    fn layout() -> Layout {
        Layout {
            increment: 40,
            pause: 44,
            jump: 46,
            end: 48,
        }
    }
    fn trap() -> Trap {
        let i = image();
        let mut registers = [0; 15];
        registers[0] = 1;
        Trap {
            root: i.root_physical,
            vector: u64::from(TIMER_VECTOR),
            error: 0,
            rip: i.initial_frame.rip + layout().increment,
            cs: i.initial_frame.cs,
            flags: INITIAL_RFLAGS,
            rsp: i.initial_frame.rsp,
            ss: i.initial_frame.ss,
            cr2: 0,
            handler_stack: STACK_TOP - FRAME_BYTES,
            depth: 1,
            registers,
        }
    }
    #[test]
    fn three_interrupts_resume_twice_then_recover_and_reject_replay() {
        let mut s = Sequence::new(image(), layout(), [0; 15]).unwrap();
        for (index, offset) in [40, 44, 46].into_iter().enumerate() {
            let mut t = trap();
            t.rip = image().initial_frame.rip + offset;
            t.registers[0] = (index as u64 + 1) * 100;
            assert_eq!(s.accept(&t), Ok(index == 2));
        }
        assert_eq!(
            s.observation(),
            Observation {
                deliveries: 3,
                resumes: 2,
                first_progress: 100,
                last_progress: 300
            }
        );
        assert_eq!(s.accept(&trap()), Err(Error::State));
    }
    #[test]
    fn layout_and_image_arithmetic_are_bounded() {
        for case in 0..8 {
            let mut i = image();
            let mut l = layout();
            let mut r = [0; 15];
            match case {
                0 => i.root_physical = 0,
                1 => i.initial_frame.rip = u64::MAX - 4095 + 16,
                2 => i.initial_frame.rsp = 0,
                3 => i.initial_frame.cs = 8,
                4 => l.end = u64::MAX,
                5 => l.pause = l.increment,
                6 => r[0] = 1,
                _ => i.initial_frame.rflags |= 3 << 12,
            }
            assert!(Sequence::new(i, l, r).is_err());
        }
    }
    #[test]
    fn wrong_privilege_root_frame_vector_and_instruction_do_not_advance() {
        for case in 0..12 {
            let mut s = Sequence::new(image(), layout(), [0; 15]).unwrap();
            let mut t = trap();
            match case {
                0 => t.root += 4096,
                1 => t.cs = 8,
                2 => t.ss = 16,
                3 => t.rsp -= 16,
                4 => t.flags |= 3 << 12,
                5 => t.flags &= !(1 << 9),
                6 => t.flags |= 1 << 10,
                7 => t.depth = 2,
                8 => t.handler_stack -= 8,
                9 => t.vector = 6,
                10 => t.error = 1,
                _ => t.rip += 1,
            }
            assert!(s.accept(&t).is_err());
            assert_eq!(s.observation(), Observation::default());
        }
        for bit in 0..64 {
            let mut s = Sequence::new(image(), layout(), [0; 15]).unwrap();
            let mut t = trap();
            t.flags ^= 1 << bit;
            if bit == 16 {
                assert_eq!(s.accept(&t), Ok(false));
            } else {
                assert_eq!(s.accept(&t), Err(Error::Frame));
                assert_eq!(s.observation(), Observation::default());
            }
        }
    }
    #[test]
    fn all_preserved_registers_and_strict_progress_are_checked() {
        for index in 1..15 {
            let mut s = Sequence::new(image(), layout(), [0; 15]).unwrap();
            let mut t = trap();
            t.registers[index] = 1;
            assert_eq!(s.accept(&t), Err(Error::Registers));
        }
        let mut s = Sequence::new(image(), layout(), [0; 15]).unwrap();
        let mut t = trap();
        t.registers[0] = 0;
        assert_eq!(s.accept(&t), Err(Error::Registers));
        t.registers[0] = 10;
        assert_eq!(s.accept(&t), Ok(false));
        for progress in [0, 9, 10] {
            t.registers[0] = progress;
            assert_eq!(s.accept(&t), Err(Error::Registers));
        }
        assert_eq!(s.observation().deliveries, 1);
    }
    #[test]
    fn timer_budget_rejects_deadline_and_clock_failure_and_supports_wrap() {
        let b = Budget {
            count: 1000,
            period_fs: 100_000_000,
            counter_mask: u64::from(u32::MAX),
        };
        assert_eq!(b.elapsed(100, 110), Ok(10));
        assert_eq!(b.elapsed(u32::MAX as u64 - 2, 4), Ok(7));
        for now in [100, 99, 1_000_101] {
            assert!(b.elapsed(100, now).is_err());
        }
        for bad in [
            Budget { count: 0, ..b },
            Budget { period_fs: 0, ..b },
            Budget {
                counter_mask: 0,
                ..b
            },
        ] {
            assert!(bad.validate().is_err());
            assert!(bad.elapsed(1, 2).is_err());
        }
    }
}
