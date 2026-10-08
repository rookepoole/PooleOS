//! Bounded first-user-entry policy. Hardware effects remain a trusted boundary.
#![forbid(unsafe_code)]

use super::prepared::{STACK_BOTTOM, STACK_TOP};
use super::{INITIAL_RFLAGS, ImageAdmission, USER_CODE_SELECTOR, USER_DATA_SELECTOR};
use crate::virtual_memory::{KERNEL_IMAGE_START, USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START};

pub const CONTRACT_ID: &str = "PKUSER5";
pub const TRAP_COUNT: u32 = 7;
pub const FRAME_BYTES: u64 = 22 * 8;
pub const REQUIRED_FEATURES: u32 = 1 | (1 << 5) | (1 << 24) | (1 << 25) | (1 << 26);
const REQUIRED_CR0: u64 = 1 | (1 << 16) | (1 << 31);
const REQUIRED_EFER: u64 = (1 << 8) | (1 << 10) | (1 << 11);
const ALLOWED_CR4: u64 = (1 << 2)
    | (1 << 3)
    | (1 << 5)
    | (1 << 6)
    | (1 << 8)
    | (1 << 9)
    | (1 << 10)
    | (1 << 11)
    | (1 << 16)
    | (1 << 20)
    | (1 << 21);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    State,
    Context,
    Layout,
    Registers,
    Frame,
    Fault,
    Hardware,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Controls {
    pub cr0: u64,
    pub cr4: u64,
    pub efer: u64,
}

impl Controls {
    /// First profile exposes x87/SSE only. Reject already-enabled extended state,
    /// paging/virtualization modes or fast-FXSAVE semantics we do not own yet.
    pub fn plan(self, features: u32) -> Result<Self, Error> {
        if features & REQUIRED_FEATURES != REQUIRED_FEATURES
            || self.cr0 & REQUIRED_CR0 != REQUIRED_CR0
            || self.cr4 & (1 << 5) == 0
            || self.cr4 & !ALLOWED_CR4 != 0
            || self.efer & REQUIRED_EFER != REQUIRED_EFER
            || self.efer & !(REQUIRED_EFER | 1) != 0
        {
            return Err(Error::Context);
        }
        Ok(Self {
            cr0: (self.cr0 | 2 | (1 << 5)) & !(4 | 8),
            cr4: (self.cr4 | (1 << 2) | (1 << 3) | (1 << 9) | (1 << 10)) & !((1 << 8) | (1 << 16)),
            efer: self.efer & !1,
        })
    }
}

/// Offsets come from linked assembly labels, not a hand-maintained byte stream.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Layout {
    pub cli: u64,
    pub io: u64,
    pub syscall: u64,
    pub read_kernel: u64,
    pub nx_resume: u64,
    pub done: u64,
    pub end: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Trap {
    pub root: u64,
    pub vector: u64,
    pub error: u64,
    pub rip: u64,
    pub cs: u64,
    pub flags: u64,
    pub rsp: u64,
    pub ss: u64,
    pub cr2: u64,
    pub handler_stack: u64,
    pub depth: u32,
    pub registers: [u64; 15],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Action {
    Resume(u64),
    ReturnKernel,
}

pub struct Sequence {
    image: ImageAdmission,
    layout: Layout,
    completed: u32,
}

impl Sequence {
    pub fn new(image: ImageAdmission, layout: Layout) -> Result<Self, Error> {
        let f = image.initial_frame;
        if image.root_physical == 0
            || image.root_physical & 4095 != 0
            || image.root_generation == 0
            || f.cs != USER_CODE_SELECTOR
            || f.ss != USER_DATA_SELECTOR
            || f.rflags != INITIAL_RFLAGS
            || f.rip < USER_WINDOW_START
            || f.rip >= USER_WINDOW_END_EXCLUSIVE - 4096
            || f.rip & 4095 != 16
            || f.rsp & 4095 != 0
            || f.rsp <= f.rip + 4096
            || f.rsp >= USER_WINDOW_END_EXCLUSIVE
        {
            return Err(Error::Layout);
        }
        let points = [
            0,
            layout.cli,
            layout.io,
            layout.syscall,
            layout.read_kernel,
            layout.nx_resume,
            layout.done,
            layout.end,
        ];
        if points.windows(2).any(|w| w[0] >= w[1])
            || layout.end > 4096 - 16
            || layout.cli < 2
            || layout.io < layout.cli + 1
            || layout.syscall < layout.io + 2
            || layout.read_kernel < layout.syscall + 2
            || layout.nx_resume < layout.read_kernel + 3
            || layout.end < layout.done + 2
        {
            return Err(Error::Layout);
        }
        Ok(Self {
            image,
            layout,
            completed: 0,
        })
    }

    pub const fn completed(&self) -> u32 {
        self.completed
    }

    pub const fn image(&self) -> ImageAdmission {
        self.image
    }

    /// Only a matching, contained event advances the sequence; failure is atomic.
    pub fn accept(&mut self, t: &Trap) -> Result<Action, Error> {
        if self.completed >= TRAP_COUNT {
            return Err(Error::State);
        }
        let f = self.image.initial_frame;
        if t.root != self.image.root_physical
            || t.cs != f.cs
            || t.ss != f.ss
            || t.rsp != f.rsp
            || t.flags & !(1 << 16) != INITIAL_RFLAGS
            || t.depth != 1
            || t.handler_stack != STACK_TOP - FRAME_BYTES
            || t.handler_stack < STACK_BOTTOM
        {
            return Err(Error::Frame);
        }
        if self.completed == 0 && t.registers != [0; 15] {
            return Err(Error::Registers);
        }
        let l = self.layout;
        let (rip, vector, error, cr2, action) = match self.completed {
            0 => (f.rip, 6, 0, None, Action::Resume(f.rip + 2)),
            1 => (
                f.rip + l.cli,
                13,
                0,
                None,
                Action::Resume(f.rip + l.cli + 1),
            ),
            2 => (f.rip + l.io, 13, 0, None, Action::Resume(f.rip + l.io + 2)),
            3 => (
                f.rip + l.syscall,
                6,
                0,
                None,
                Action::Resume(f.rip + l.syscall + 2),
            ),
            4 => (
                f.rip + l.read_kernel,
                14,
                5,
                Some(KERNEL_IMAGE_START),
                Action::Resume(f.rip + l.read_kernel + 3),
            ),
            5 => (
                f.rsp - 16,
                14,
                21,
                Some(f.rsp - 16),
                Action::Resume(f.rip + l.nx_resume),
            ),
            _ => (f.rip + l.done, 6, 0, None, Action::ReturnKernel),
        };
        if t.rip != rip || t.vector != vector || t.error != error || cr2.is_some_and(|v| t.cr2 != v)
        {
            return Err(Error::Fault);
        }
        self.completed += 1;
        Ok(action)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Observation {
    pub root: u64,
    pub traps: u32,
    pub cpl: u8,
    pub restored: bool,
}

/// A trusted exclusive CPL0 adapter. Returning Err may follow descriptor or CPU
/// effects. `quiesce` must detach every reference to the private task-entry stack,
/// sanitize retained user state and return with IF clear before resources retire.
pub trait Driver {
    fn execute(&mut self, image: ImageAdmission) -> Result<Observation, Error>;
    fn quiesce(&mut self, root: u64) -> Result<(), Error>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::user_entry::InitialReturnFrame;
    fn controls() -> Controls {
        Controls {
            cr0: REQUIRED_CR0,
            cr4: 1 << 5,
            efer: REQUIRED_EFER | 1,
        }
    }
    fn image() -> ImageAdmission {
        ImageAdmission {
            root_physical: 0x100000,
            root_generation: 1,
            code_physical: 0x200000,
            stack_physical: 0x210000,
            initial_frame: InitialReturnFrame {
                rip: USER_WINDOW_START + 16,
                cs: USER_CODE_SELECTOR,
                rflags: INITIAL_RFLAGS,
                rsp: USER_WINDOW_START + 4 * 4096,
                ss: USER_DATA_SELECTOR,
            },
        }
    }
    fn layout() -> Layout {
        Layout {
            cli: 2,
            io: 3,
            syscall: 5,
            read_kernel: 17,
            nx_resume: 26,
            done: 34,
            end: 36,
        }
    }
    fn trap() -> Trap {
        let i = image();
        Trap {
            root: i.root_physical,
            vector: 6,
            error: 0,
            rip: i.initial_frame.rip,
            cs: USER_CODE_SELECTOR,
            flags: INITIAL_RFLAGS | (1 << 16),
            rsp: i.initial_frame.rsp,
            ss: USER_DATA_SELECTOR,
            cr2: 0,
            handler_stack: STACK_TOP - FRAME_BYTES,
            depth: 1,
            registers: [0; 15],
        }
    }
    #[test]
    fn controls_require_owned_baseline_and_disable_ambient_entry_features() {
        let mut c = controls();
        c.cr0 |= 12;
        c.cr4 |= (1 << 8) | (1 << 16);
        let p = c.plan(REQUIRED_FEATURES).unwrap();
        assert_eq!(p.cr0 & 12, 0);
        assert_eq!(p.efer & 1, 0);
        assert_eq!(p.cr4 & ((1 << 8) | (1 << 16)), 0);
        assert_eq!(p.plan(REQUIRED_FEATURES), Ok(p));
    }
    #[test]
    fn unsupported_control_modes_and_missing_features_reject() {
        for bit in [0, 5, 24, 25, 26] {
            assert!(controls().plan(REQUIRED_FEATURES & !(1 << bit)).is_err());
        }
        for bit in [7, 12, 13, 14, 17, 18, 22, 23, 24, 63] {
            let mut c = controls();
            c.cr4 |= 1 << bit;
            assert!(c.plan(REQUIRED_FEATURES).is_err());
        }
        for bit in [12, 13, 14, 15, 63] {
            let mut c = controls();
            c.efer |= 1 << bit;
            assert!(c.plan(REQUIRED_FEATURES).is_err());
        }
        for bit in [0, 16, 31] {
            let mut c = controls();
            c.cr0 &= !(1 << bit);
            assert!(c.plan(REQUIRED_FEATURES).is_err());
        }
    }
    #[test]
    fn image_and_linked_layout_must_be_exact_and_bounded() {
        for case in 0..12 {
            let mut i = image();
            let mut l = layout();
            match case {
                0 => i.root_physical = 1,
                1 => i.root_generation = 0,
                2 => i.initial_frame.cs = 8,
                3 => i.initial_frame.rflags |= 3 << 12,
                4 => i.initial_frame.rsp = i.initial_frame.rip,
                5 => l.end = 4096,
                6 => l.io = l.cli,
                7 => l.cli = 1,
                8 => i.initial_frame.rip = u64::MAX - 4095 + 16,
                9 => i.initial_frame.rip = USER_WINDOW_END_EXCLUSIVE + 16,
                10 => i.initial_frame.rsp = USER_WINDOW_END_EXCLUSIVE,
                _ => l.end = u64::MAX,
            }
            assert!(Sequence::new(i, l).is_err());
        }
    }
    #[test]
    fn privilege_flags_root_stack_and_recursion_reject_without_progress() {
        for case in 0..10 {
            let mut t = trap();
            let mut s = Sequence::new(image(), layout()).unwrap();
            match case {
                0 => t.cs = 8,
                1 => t.ss = 0x10,
                2 => t.flags |= 3 << 12,
                3 => t.flags &= !(1 << 9),
                4 => t.root += 4096,
                5 => t.rsp -= 16,
                6 => t.handler_stack += 8,
                7 => t.depth = 2,
                8 => t.flags |= 1 << 10,
                _ => t.flags |= 1 << 18,
            }
            assert!(s.accept(&t).is_err());
            assert_eq!(s.completed(), 0);
        }
    }
    #[test]
    fn every_initial_register_must_be_zero() {
        for index in 0..15 {
            let mut t = trap();
            t.registers[index] = 1;
            assert_eq!(
                Sequence::new(image(), layout()).unwrap().accept(&t),
                Err(Error::Registers)
            );
        }
    }
    #[test]
    fn seven_faults_are_ordered_exact_and_terminal() {
        let mut s = Sequence::new(image(), layout()).unwrap();
        let mut t = trap();
        let base = t.rip;
        let l = layout();
        let cases = [
            (base, 6, 0, 0),
            (base + l.cli, 13, 0, 0),
            (base + l.io, 13, 0, 0),
            (base + l.syscall, 6, 0, 0),
            (base + l.read_kernel, 14, 5, KERNEL_IMAGE_START),
            (t.rsp - 16, 14, 21, t.rsp - 16),
            (base + l.done, 6, 0, 0),
        ];
        for (index, (rip, vector, error, cr2)) in cases.into_iter().enumerate() {
            t.rip = rip;
            t.vector = vector;
            t.error = error;
            t.cr2 = cr2;
            for case in 0..3 {
                let mut bad = t;
                match case {
                    0 => bad.rip += 1,
                    1 => bad.vector ^= 1,
                    _ => bad.error ^= 1,
                }
                assert!(s.accept(&bad).is_err());
                assert_eq!(s.completed(), index as u32);
            }
            if vector == 14 {
                let mut bad = t;
                bad.cr2 ^= 1;
                assert!(s.accept(&bad).is_err());
            }
            let action = s.accept(&t).unwrap();
            assert_eq!(action == Action::ReturnKernel, index == 6);
        }
        assert_eq!(s.completed(), TRAP_COUNT);
        assert_eq!(s.accept(&t), Err(Error::State));
    }
}
