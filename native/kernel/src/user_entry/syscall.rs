//! Versioned, nonblocking first-user ABI. No endpoint or object authority is granted.
#![forbid(unsafe_code)]

use super::{
    INITIAL_RFLAGS, ImageAdmission,
    prepared::{STACK_BOTTOM, STACK_TOP},
    privilege::{Error, FRAME_BYTES, Trap},
};
use crate::virtual_memory::{USER_WINDOW_END_EXCLUSIVE, USER_WINDOW_START};

pub const CONTRACT_ID: &str = "PKUSER7";
pub const ABI_ID: &str = "PSABI1";
pub const VERSION: u64 = 1;
pub const VECTOR: u64 = 256;
pub const MAX_COPY: usize = 256;
pub const STAR: u64 = (0x23 << 48) | (8 << 32);
pub const FMASK: u64 =
    (1 << 8) | (1 << 9) | (1 << 10) | (3 << 12) | (1 << 14) | (1 << 16) | (1 << 18);
const USER_FLAGS: u64 = INITIAL_RFLAGS
    | 1
    | (1 << 2)
    | (1 << 4)
    | (1 << 6)
    | (1 << 7)
    | (1 << 10)
    | (1 << 11)
    | (1 << 16);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u64)]
pub enum Status {
    Ok = 0,
    Version = 1,
    Unknown = 2,
    Arguments = 3,
    Fault = 4,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Request {
    Version,
    Exit(u32),
    Copy {
        source: u64,
        destination: u64,
        bytes: usize,
    },
}

pub fn request(
    number: u64,
    version: u64,
    source: u64,
    destination: u64,
    bytes: u64,
    flags: u64,
    reserved: u64,
) -> Result<Request, Status> {
    if version != VERSION {
        return Err(Status::Version);
    }
    if flags != 0 || reserved != 0 {
        return Err(Status::Arguments);
    }
    match number {
        0 if source == 0 && destination == 0 && bytes == 0 => Ok(Request::Version),
        0 => Err(Status::Arguments),
        1 => {
            if bytes > MAX_COPY as u64 {
                return Err(Status::Arguments);
            }
            if bytes != 0 {
                for start in [source, destination] {
                    let end = start.checked_add(bytes).ok_or(Status::Arguments)?;
                    if start < USER_WINDOW_START || end > USER_WINDOW_END_EXCLUSIVE {
                        return Err(Status::Arguments);
                    }
                }
            }
            Ok(Request::Copy {
                source,
                destination,
                bytes: bytes as usize,
            })
        }
        2 if source <= u32::MAX as u64 && destination == 0 && bytes == 0 => {
            Ok(Request::Exit(source as u32))
        }
        2 => Err(Status::Arguments),
        _ => Err(Status::Unknown),
    }
}

pub fn frame(image: ImageAdmission, t: &Trap) -> Result<(), Error> {
    let f = image.initial_frame;
    if t.root != image.root_physical
        || t.depth != 1
        || t.vector != VECTOR
        || t.error != 0
        || t.cs != f.cs
        || t.ss != f.ss
        || t.rsp != f.rsp
        || t.handler_stack != STACK_TOP - FRAME_BYTES
        || t.rip < f.rip
        || t.rip >= (f.rip & !4095) + 4096
        || t.flags & !USER_FLAGS != 0
        || t.flags & INITIAL_RFLAGS != INITIAL_RFLAGS
    {
        return Err(Error::Frame);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CopyFault {
    pub root: u64,
    pub address: u64,
    pub instruction: u64,
    pub recovery: u64,
    pub write: bool,
}

impl CopyFault {
    pub fn recover(self, t: &Trap) -> Result<u64, Error> {
        if t.root != self.root
            || t.depth != 2
            || t.vector != 14
            || t.rip != self.instruction
            || t.cr2 != self.address
            || t.cs != 8
            || t.ss != 16
            || t.error & !3 != 0
            || (t.error & 2 != 0) != self.write
            || t.flags & ((1 << 9) | (1 << 10)) != 0
            || !(STACK_BOTTOM + FRAME_BYTES..STACK_TOP - FRAME_BYTES).contains(&t.handler_stack)
            || !(STACK_BOTTOM + FRAME_BYTES..STACK_TOP).contains(&t.rsp)
            || t.handler_stack != (t.rsp & !15) - FRAME_BYTES
            || !(USER_WINDOW_START..USER_WINDOW_END_EXCLUSIVE).contains(&self.address)
        {
            return Err(Error::Fault);
        }
        Ok(self.recovery)
    }
}

/// Trusted byte adapter must retain the admitted root and gate exact fault recovery.
/// Bytes may fault but cannot access memory outside that unchanged user window.
pub trait Memory {
    fn read(&mut self, address: u64) -> Result<u8, Status>;
    fn write(&mut self, address: u64, byte: u8) -> Result<(), Status>;
}

/// Input failure leaves the destination untouched. Output failure reports its committed prefix.
/// Snapshotting also makes overlapping source/destination copies deterministic.
pub fn copy(
    memory: &mut impl Memory,
    source: u64,
    destination: u64,
    bytes: usize,
) -> (Status, u64) {
    if request(1, VERSION, source, destination, bytes as u64, 0, 0).is_err() {
        return (Status::Arguments, 0);
    }
    let mut snapshot = [0u8; MAX_COPY];
    for (index, byte) in snapshot[..bytes].iter_mut().enumerate() {
        match memory.read(source + index as u64) {
            Ok(value) => *byte = value,
            Err(_) => return (Status::Fault, 0),
        }
    }
    for (index, byte) in snapshot[..bytes].iter().enumerate() {
        if memory.write(destination + index as u64, *byte).is_err() {
            return (Status::Fault, index as u64);
        }
    }
    (Status::Ok, bytes as u64)
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
                cs: 0x33,
                ss: 0x2b,
                rsp: USER_WINDOW_START + 16384,
                rflags: INITIAL_RFLAGS,
            },
        }
    }
    fn trap() -> Trap {
        let i = image();
        Trap {
            root: i.root_physical,
            vector: VECTOR,
            error: 0,
            rip: i.initial_frame.rip + 2,
            cs: 0x33,
            ss: 0x2b,
            flags: INITIAL_RFLAGS,
            rsp: i.initial_frame.rsp,
            cr2: 0,
            handler_stack: STACK_TOP - FRAME_BYTES,
            depth: 1,
            registers: [0; 15],
        }
    }
    #[test]
    fn version_unknown_reserved_and_query_arguments_are_distinct() {
        assert_eq!(request(0, 1, 0, 0, 0, 0, 0), Ok(Request::Version));
        assert_eq!(request(0, 2, 0, 0, 0, 0, 0), Err(Status::Version));
        assert_eq!(request(99, 1, 0, 0, 0, 0, 0), Err(Status::Unknown));
        for (s, d, n, f, r) in [
            (1, 0, 0, 0, 0),
            (0, 1, 0, 0, 0),
            (0, 0, 1, 0, 0),
            (0, 0, 0, 1, 0),
            (0, 0, 0, 0, 1),
        ] {
            assert_eq!(request(0, 1, s, d, n, f, r), Err(Status::Arguments));
        }
    }
    #[test]
    fn exit_accepts_only_versioned_u32_status_and_no_pointer_or_length() {
        for code in [0, 42, u32::MAX as u64] {
            assert_eq!(
                request(2, 1, code, 0, 0, 0, 0),
                Ok(Request::Exit(code as u32))
            );
        }
        for (code, dest, len, flags, reserved) in [
            (1u64 << 32, 0, 0, 0, 0),
            (42, 1, 0, 0, 0),
            (42, 0, 1, 0, 0),
            (42, 0, 0, 1, 0),
            (42, 0, 0, 0, 1),
        ] {
            assert_eq!(
                request(2, 1, code, dest, len, flags, reserved),
                Err(Status::Arguments)
            );
        }
        assert_eq!(request(2, 0, 42, 0, 0, 0, 0), Err(Status::Version));
    }
    #[test]
    fn copy_bounds_include_zero_unaligned_edges_but_not_wrap_or_kernel() {
        assert_eq!(
            request(1, 1, 0, 0, 0, 0, 0),
            Ok(Request::Copy {
                source: 0,
                destination: 0,
                bytes: 0
            })
        );
        assert!(
            request(
                1,
                1,
                USER_WINDOW_START + 1,
                USER_WINDOW_END_EXCLUSIVE - 256,
                256,
                0,
                0
            )
            .is_ok()
        );
        for (s, d, n) in [
            (0, USER_WINDOW_START, 1),
            (USER_WINDOW_START, 0, 1),
            (u64::MAX - 3, USER_WINDOW_START, 8),
            (USER_WINDOW_START, USER_WINDOW_END_EXCLUSIVE - 3, 4),
            (USER_WINDOW_START, USER_WINDOW_START, 257),
        ] {
            assert_eq!(request(1, 1, s, d, n, 0, 0), Err(Status::Arguments));
        }
    }
    #[test]
    fn return_frame_is_user_canonical_owned_and_exactly_scoped() {
        assert_eq!(frame(image(), &trap()), Ok(()));
        for case in 0..12 {
            let mut t = trap();
            match case {
                0 => t.root += 4096,
                1 => t.depth = 2,
                2 => t.vector = 6,
                3 => t.error = 1,
                4 => t.cs = 8,
                5 => t.ss = 16,
                6 => t.rsp += 8,
                7 => t.handler_stack -= 8,
                8 => t.rip = 0xffff800000000000,
                9 => t.rip = USER_WINDOW_START,
                10 => t.flags |= 3 << 12,
                _ => t.flags &= !(1 << 9),
            }
            assert_eq!(frame(image(), &t), Err(Error::Frame));
        }
        for bit in 0..64 {
            let mut t = trap();
            t.flags ^= 1 << bit;
            assert_eq!(
                frame(image(), &t).is_ok(),
                (USER_FLAGS & (1 << bit) != 0) && (INITIAL_RFLAGS & (1 << bit) == 0)
            );
        }
    }
    fn fault() -> (CopyFault, Trap) {
        let mut t = trap();
        t.vector = 14;
        t.depth = 2;
        t.cs = 8;
        t.ss = 16;
        t.flags = 2 | 1 << 16;
        t.rsp = STACK_TOP - 512;
        t.handler_stack = t.rsp - FRAME_BYTES;
        t.cr2 = USER_WINDOW_START + 4096;
        t.rip = 0xffffffff80010000;
        (
            CopyFault {
                root: t.root,
                address: t.cr2,
                instruction: t.rip,
                recovery: t.rip + 8,
                write: false,
            },
            t,
        )
    }
    #[test]
    fn recovery_accepts_only_exact_armed_supervisor_copy_fault() {
        let (f, t) = fault();
        assert_eq!(f.recover(&t), Ok(f.recovery));
        for case in 0..13 {
            let mut t = t;
            match case {
                0 => t.root += 4096,
                1 => t.depth = 1,
                2 => t.vector = 13,
                3 => t.rip += 1,
                4 => t.cr2 += 1,
                5 => t.cs = 0x33,
                6 => t.ss = 0x2b,
                7 => t.error = 4,
                8 => t.error = 2,
                9 => t.flags |= 1 << 9,
                10 => t.flags |= 1 << 10,
                11 => t.handler_stack = STACK_BOTTOM,
                _ => t.rsp = 0,
            }
            assert_eq!(f.recover(&t), Err(Error::Fault));
        }
        let mut t = t;
        t.error = 3;
        assert!(CopyFault { write: true, ..f }.recover(&t).is_ok());
        t.error |= 1 << 4;
        assert!(CopyFault { write: true, ..f }.recover(&t).is_err());
    }
    struct Bytes {
        data: [u8; 512],
        read_fault: Option<u64>,
        write_fault: Option<u64>,
        reads: usize,
        writes: usize,
    }
    impl Bytes {
        fn new() -> Self {
            Self {
                data: [0; 512],
                read_fault: None,
                write_fault: None,
                reads: 0,
                writes: 0,
            }
        }
    }
    impl Memory for Bytes {
        fn read(&mut self, a: u64) -> Result<u8, Status> {
            self.reads += 1;
            if self.read_fault == Some(a) {
                return Err(Status::Fault);
            }
            Ok(self.data[(a - USER_WINDOW_START) as usize])
        }
        fn write(&mut self, a: u64, b: u8) -> Result<(), Status> {
            self.writes += 1;
            if self.write_fault == Some(a) {
                return Err(Status::Fault);
            }
            self.data[(a - USER_WINDOW_START) as usize] = b;
            Ok(())
        }
    }
    #[test]
    fn copy_snapshots_overlapping_input_and_bounds_all_accesses() {
        let mut m = Bytes::new();
        for i in 0..256 {
            m.data[i] = i as u8;
        }
        assert_eq!(
            copy(&mut m, USER_WINDOW_START, USER_WINDOW_START + 1, 256),
            (Status::Ok, 256)
        );
        for i in 0..256 {
            assert_eq!(m.data[i + 1], i as u8);
        }
        assert_eq!((m.reads, m.writes), (256, 256));
        assert_eq!(copy(&mut m, 0, 0, 0), (Status::Ok, 0));
        assert_eq!(copy(&mut m, 0, 0, 1), (Status::Arguments, 0));
        assert_eq!((m.reads, m.writes), (256, 256));
    }
    #[test]
    fn every_input_fault_has_no_destination_effect_and_output_fault_reports_prefix() {
        for index in 0..256 {
            let mut m = Bytes::new();
            m.data[..256].fill(0x5a);
            m.read_fault = Some(USER_WINDOW_START + index);
            assert_eq!(
                copy(&mut m, USER_WINDOW_START, USER_WINDOW_START + 256, 256),
                (Status::Fault, 0)
            );
            assert_eq!(m.writes, 0);
            assert_eq!(m.data[256..], [0; 256]);
            m.read_fault = None;
            m.write_fault = Some(USER_WINDOW_START + 256 + index);
            assert_eq!(
                copy(&mut m, USER_WINDOW_START, USER_WINDOW_START + 256, 256),
                (Status::Fault, index)
            );
            assert!(m.data[256..256 + index as usize].iter().all(|b| *b == 0x5a));
            assert!(m.data[256 + index as usize..].iter().all(|b| *b == 0));
        }
    }
}
