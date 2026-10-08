//! Single-BSP development syscall lease and exact-instruction copy fault fixups.
use super::*;
use poolekernel::user_entry::{
    ImageAdmission,
    prepared::STACK_TOP,
    privilege::{Error, Trap},
    syscall::{self, CopyFault, Memory, Request, Status},
};

const MSRS: [u32; 4] = [0xc0000081, 0xc0000082, 0xc0000083, 0xc0000084];
static mut SESSION: Option<Session> = None;
static mut COPY: Option<CopyFault> = None;
static READ_FAULTS: core::sync::atomic::AtomicU32 = core::sync::atomic::AtomicU32::new(0);
static WRITE_FAULTS: core::sync::atomic::AtomicU32 = core::sync::atomic::AtomicU32::new(0);
#[unsafe(no_mangle)]
static mut poole_syscall_user_rsp: u64 = 0;

#[derive(Clone, Copy)]
pub struct Observation {
    pub calls: u32,
    pub statuses: [u32; 5],
    pub read_faults: u32,
    pub write_faults: u32,
}
struct Session {
    image: ImageAdmission,
    active: bool,
    sealed: bool,
    counts: [u32; 5],
}
unsafe extern "C" {
    fn poole_user_syscall_entry();
    fn poole_copy_read(address: u64, unused: u64, smap: u64) -> u64;
    fn poole_copy_write(address: u64, byte: u64, smap: u64) -> u64;
    static poole_copy_read_access: u8;
    static poole_copy_read_fault: u8;
    static poole_copy_write_access: u8;
    static poole_copy_write_fault: u8;
}

pub(super) fn prepare(image: ImageAdmission) -> Result<(), Error> {
    if unsafe { (&*(&raw const SESSION)).is_some() || (&*(&raw const COPY)).is_some() }
        || cpuid(0x80000000, 0).eax < 0x80000001
        || cpuid(0x80000001, 0).edx & (1 << 11) == 0
    {
        return Err(Error::Context);
    }
    unsafe {
        write_volatile(
            &raw mut SESSION,
            Some(Session {
                image,
                active: false,
                sealed: false,
                counts: [0; 5],
            }),
        );
    }
    READ_FAULTS.store(0, Ordering::Release);
    WRITE_FAULTS.store(0, Ordering::Release);
    Ok(())
}

pub(super) fn enable() -> Result<(), Error> {
    let s = unsafe { (&mut *(&raw mut SESSION)).as_mut() }.ok_or(Error::State)?;
    if s.active
        || s.sealed
        || unsafe { read_cr3() } != s.image.root_physical
        || read_rflags() & (1 << 9) != 0
    {
        return Err(Error::State);
    }
    s.active = true; // Mark possible effects before writing the entry MSRs.
    let values = [
        syscall::STAR,
        poole_user_syscall_entry as *const () as u64,
        0,
        syscall::FMASK,
    ];
    unsafe {
        for (m, v) in MSRS.into_iter().zip(values) {
            write_msr(m, v);
            if read_msr(m) != v {
                return Err(Error::Hardware);
            }
        }
        let e = read_msr(IA32_EFER) | 1;
        write_msr(IA32_EFER, e);
        if read_msr(IA32_EFER) != e {
            return Err(Error::Hardware);
        }
    }
    Ok(())
}

pub(super) fn disable(root: u64) -> Result<(), Error> {
    let Some(s) = (unsafe { (&mut *(&raw mut SESSION)).as_mut() }) else {
        return Ok(());
    };
    if root != s.image.root_physical
        || unsafe { read_cr3() } != root
        || read_rflags() & (1 << 9) != 0
    {
        return Err(Error::Context);
    }
    unsafe {
        let e = read_msr(IA32_EFER) & !1;
        write_msr(IA32_EFER, e);
        if read_msr(IA32_EFER) != e {
            return Err(Error::Hardware);
        }
        for m in MSRS {
            write_msr(m, 0);
            if read_msr(m) != 0 {
                return Err(Error::Hardware);
            }
        }
    }
    if unsafe { (&*(&raw const COPY)).is_some() } {
        return Err(Error::State);
    }
    s.active = false;
    Ok(())
}

pub(super) fn clear(root: u64) -> Result<(), Error> {
    disable(root)?;
    unsafe {
        write_volatile(&raw mut SESSION, None);
        write_volatile(&raw mut poole_syscall_user_rsp, 0);
    }
    Ok(())
}

pub(super) fn observe() -> Result<Observation, Error> {
    let s = unsafe { (&*(&raw const SESSION)).as_ref() }.ok_or(Error::State)?;
    Ok(Observation {
        calls: s.counts.iter().sum(),
        statuses: s.counts,
        read_faults: READ_FAULTS.load(Ordering::Acquire),
        write_faults: WRITE_FAULTS.load(Ordering::Acquire),
    })
}

pub(super) fn finish(root: u64) -> Result<(), Error> {
    let o = observe()?;
    if o.calls != 12 || o.statuses != [3, 1, 1, 4, 3] || o.read_faults != 1 || o.write_faults != 2 {
        return Err(Error::State);
    }
    disable(root)?;
    unsafe { (&mut *(&raw mut SESSION)).as_mut() }
        .ok_or(Error::State)?
        .sealed = true;
    Ok(())
}

struct Access {
    root: u64,
    smap: bool,
}
impl Access {
    fn byte(&mut self, address: u64, value: Option<u8>) -> Result<u64, Status> {
        if unsafe { read_cr3() } != self.root
            || read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
            || unsafe { (&*(&raw const COPY)).is_some() }
        {
            crate::poole_kernel_emergency_panic(poolekernel::PanicCode::UserRoot as u32);
        }
        let (instruction, recovery) = if value.is_some() {
            (
                (&raw const poole_copy_write_access) as u64,
                (&raw const poole_copy_write_fault) as u64,
            )
        } else {
            (
                (&raw const poole_copy_read_access) as u64,
                (&raw const poole_copy_read_fault) as u64,
            )
        };
        // CpuImage owns all admitted mappings and frames; IF0/no AP/DMA prevents map races.
        unsafe {
            write_volatile(
                &raw mut COPY,
                Some(CopyFault {
                    root: self.root,
                    address,
                    instruction,
                    recovery,
                    write: value.is_some(),
                }),
            );
        }
        let result = unsafe {
            asm!("lfence", options(nostack, preserves_flags));
            if let Some(b) = value {
                poole_copy_write(address, u64::from(b), u64::from(self.smap))
            } else {
                poole_copy_read(address, 0, u64::from(self.smap))
            }
        };
        unsafe { write_volatile(&raw mut COPY, None) };
        if unsafe { read_cr3() } != self.root
            || read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
        {
            crate::poole_kernel_emergency_panic(poolekernel::PanicCode::UserRoot as u32);
        }
        Ok(result)
    }
}
impl Memory for Access {
    fn read(&mut self, address: u64) -> Result<u8, Status> {
        u8::try_from(self.byte(address, None)?).map_err(|_| Status::Fault)
    }
    fn write(&mut self, address: u64, byte: u8) -> Result<(), Status> {
        if self.byte(address, Some(byte))? == 0 {
            Ok(())
        } else {
            Err(Status::Fault)
        }
    }
}

pub(super) fn dispatch(t: &Trap, frame: &mut TrapFrame) -> Result<Option<u32>, Error> {
    let s = unsafe { (&mut *(&raw mut SESSION)).as_mut() }.ok_or(Error::State)?;
    if !s.active
        || s.sealed
        || s.counts.iter().sum::<u32>() >= 64
        || read_rflags() & syscall::FMASK != 0
    {
        return Err(Error::State);
    }
    syscall::frame(s.image, t)?;
    let result = match syscall::request(
        frame.rax, frame.rdi, frame.rsi, frame.rdx, frame.r10, frame.r8, frame.r9,
    ) {
        Ok(Request::Version) => (Status::Ok, syscall::VERSION),
        Ok(Request::Exit(code)) => {
            s.counts[Status::Ok as usize] += 1;
            return Ok(Some(code));
        }
        Ok(Request::Copy {
            source,
            destination,
            bytes,
        }) => syscall::copy(
            &mut Access {
                root: t.root,
                smap: unsafe { read_cr4() } & (1 << 21) != 0,
            },
            source,
            destination,
            bytes,
        ),
        Err(e) => (e, 0),
    };
    s.counts[result.0 as usize] += 1;
    frame.rax = result.0 as u64;
    frame.rdx = result.1;
    frame.rflags = t.flags & !((1 << 10) | (1 << 16));
    Ok(None)
}

pub(super) fn recover(t: &Trap) -> Option<u64> {
    // Do not borrow SESSION: its exclusive syscall handler is suspended here.
    let f = unsafe { read_volatile(&raw const COPY) }?;
    let target = f.recover(t).ok()?;
    if f.write {
        WRITE_FAULTS.fetch_add(1, Ordering::AcqRel);
    } else {
        READ_FAULTS.fetch_add(1, Ordering::AcqRel);
    }
    Some(target)
}

core::arch::global_asm!(r#"
    .section .text.poole_syscall,"ax",@progbits
    .global poole_user_syscall_entry
poole_user_syscall_entry:
    mov qword ptr [rip + poole_syscall_user_rsp], rsp
    movabs rsp, {stack_top}
    push 0x2b
    push qword ptr [rip + poole_syscall_user_rsp]
    push r11
    push 0x33
    push rcx
    push 0
    push 256
    jmp poole_trap_common

    .global poole_copy_read
poole_copy_read:
    test edx, edx
    jz 2f
    stac
2:
    .global poole_copy_read_access
poole_copy_read_access:
    movzx eax, byte ptr [rdi]
    jmp 3f
    .global poole_copy_read_fault
poole_copy_read_fault:
    mov eax, 256
3:
    test edx, edx
    jz 4f
    clac
4:
    ret

    .global poole_copy_write
poole_copy_write:
    test edx, edx
    jz 2f
    stac
2:
    .global poole_copy_write_access
poole_copy_write_access:
    mov byte ptr [rdi], sil
    xor eax, eax
    jmp 3f
    .global poole_copy_write_fault
poole_copy_write_fault:
    mov eax, 1
3:
    test edx, edx
    jz 4f
    clac
4:
    ret
"#, stack_top=const STACK_TOP);
