//! Saved user registers only; kernel stack pointers never enter a resumable frame.
#![forbid(unsafe_code)]
use super::{
    ImageAdmission, InitialReturnFrame,
    privilege::{Error, Trap},
    syscall,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct Context {
    pub registers: [u64; 15],
    pub frame: InitialReturnFrame,
}
const _: () = assert!(core::mem::size_of::<Context>() == 160);
const _: () = assert!(core::mem::offset_of!(Context, frame) == 120);

impl Context {
    pub fn initial(image: ImageAdmission) -> Self {
        Self {
            registers: [0; 15],
            frame: image.initial_frame,
        }
    }
    /// Explicit supervisor-selected user data, not inherited kernel registers.
    /// The six integer startup arguments use RDI, RSI, RDX, RCX, R8, R9.
    pub fn initial_with_arguments(image: ImageAdmission, arguments: [u64; 6]) -> Self {
        let mut context = Self::initial(image);
        for (index, value) in [9, 8, 11, 12, 7, 6].into_iter().zip(arguments) {
            context.registers[index] = value;
        }
        context
    }
    pub fn capture(image: ImageAdmission, trap: &Trap) -> Result<Self, Error> {
        // Reuse checked IRET geometry; the caller separately authenticates the event.
        syscall::frame(
            image,
            &Trap {
                vector: syscall::VECTOR,
                error: 0,
                ..*trap
            },
        )?;
        Ok(Self {
            registers: trap.registers,
            frame: InitialReturnFrame {
                rip: trap.rip,
                cs: trap.cs,
                rflags: trap.flags & !(1 << 16),
                rsp: trap.rsp,
                ss: trap.ss,
            },
        })
    }
    pub fn validate(&self, image: ImageAdmission) -> Result<(), Error> {
        let f = self.frame;
        syscall::frame(
            image,
            &Trap {
                root: image.root_physical,
                vector: syscall::VECTOR,
                error: 0,
                rip: f.rip,
                cs: f.cs,
                flags: f.rflags,
                rsp: f.rsp,
                ss: f.ss,
                cr2: 0,
                handler_stack: super::prepared::STACK_TOP - super::privilege::FRAME_BYTES,
                depth: 1,
                registers: self.registers,
            },
        )
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
            initial_frame: InitialReturnFrame {
                rip: 0x40000010,
                cs: super::super::USER_CODE_SELECTOR,
                rflags: super::super::INITIAL_RFLAGS,
                rsp: 0x40004000,
                ss: super::super::USER_DATA_SELECTOR,
            },
        }
    }
    #[test]
    fn startup_arguments_change_only_the_six_declared_user_registers() {
        let c = Context::initial_with_arguments(image(), [11, 22, 33, 44, 55, 66]);
        assert_eq!(
            c.registers,
            [0, 0, 0, 0, 0, 0, 66, 55, 22, 11, 0, 33, 44, 0, 0]
        );
        assert_eq!(c.frame, image().initial_frame);
        c.validate(image()).unwrap();
        assert_eq!(
            Context::initial_with_arguments(image(), [0; 6]),
            Context::initial(image())
        );
    }
    #[test]
    fn context_roundtrip_preserves_every_register_and_usable_stack_position() {
        let image = image();
        let mut c = Context::initial(image);
        assert_eq!(c.registers, [0; 15]);
        for (i, r) in c.registers.iter_mut().enumerate() {
            *r = (i as u64 + 1) * 0x11223344556677;
        }
        c.frame.rsp -= 32;
        c.frame.rflags |= (1 << 10) | 1;
        c.validate(image).unwrap();
        let t = Trap {
            root: image.root_physical,
            vector: 32,
            error: 0,
            rip: c.frame.rip,
            cs: c.frame.cs,
            flags: c.frame.rflags | (1 << 16),
            rsp: c.frame.rsp,
            ss: c.frame.ss,
            cr2: 0,
            handler_stack: super::super::prepared::STACK_TOP - super::super::privilege::FRAME_BYTES,
            depth: 1,
            registers: c.registers,
        };
        assert_eq!(Context::capture(image, &t), Ok(c));
        for case in 0..6 {
            let mut bad = t;
            match case {
                0 => bad.root += 4096,
                1 => bad.cs = 8,
                2 => bad.depth = 2,
                3 => bad.handler_stack -= 8,
                4 => bad.rip = u64::MAX,
                _ => bad.rsp = u64::MAX,
            }
            assert!(Context::capture(image, &bad).is_err());
        }
    }
    #[test]
    fn resume_rejects_kernel_addresses_privileged_flags_and_stack_guards() {
        for case in 0..7 {
            let mut c = Context::initial(image());
            match case {
                0 => c.frame.rip = 0xffff_ffff_8000_0000,
                1 => c.frame.cs = 8,
                2 => c.frame.ss = 16,
                3 => c.frame.rsp += 1,
                4 => c.frame.rsp -= 4097,
                5 => c.frame.rflags |= 3 << 12,
                _ => c.frame.rflags &= !(1 << 9),
            }
            assert!(c.validate(image()).is_err());
        }
    }
}
