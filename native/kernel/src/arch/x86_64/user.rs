//! Development-only single-BSP user entry, with private-stack fault recovery.
pub use super::user_syscall::Observation as CallObservation;
use super::*;
use poolekernel::user_entry::preemption;
use poolekernel::user_entry::prepared::{STACK_BOTTOM, STACK_TOP};
use poolekernel::user_entry::syscall;
use poolekernel::user_entry::task;
#[path = "user_slice.rs"]
mod slices;
#[path = "user_task.rs"]
mod tasks;
use poolekernel::user_entry::{
    self, ImageAdmission, InitialReturnFrame,
    privilege::{self, Action, Controls, Driver, Error, Layout, Observation, Sequence, Trap},
};
pub use slices::{PeerEntry, peer_payload};
pub use tasks::payload as task_payload;

#[repr(C, align(16))]
struct UserGdt([u64; 7]);
static mut USER_GDT: UserGdt = UserGdt([0; 7]);
static mut INITIAL_FX: FxsaveArea = FxsaveArea([0; 512]);
static mut OBSERVED_FX: FxsaveArea = FxsaveArea([0; 512]);
static mut LIVE: Option<Sequence> = None;
static mut TASK: Option<task::Run> = None;
static mut PREEMPT: Option<super::user_preempt::Session> = None;
static ACTIVE_ROOT: core::sync::atomic::AtomicU64 = core::sync::atomic::AtomicU64::new(0);
static RETURN_STACK_TOP: core::sync::atomic::AtomicU64 = core::sync::atomic::AtomicU64::new(0);

#[unsafe(no_mangle)]
static mut poole_user_saved_rsp: u64 = 0;

unsafe extern "C" {
    fn poole_user_enter(frame: *const InitialReturnFrame);
    fn poole_user_return();
    static poole_user_payload: u8;
    static poole_user_cli: u8;
    static poole_user_io: u8;
    static poole_user_syscall: u8;
    static poole_user_read_kernel: u8;
    static poole_user_nx_resume: u8;
    static poole_user_done: u8;
    static poole_user_payload_end: u8;
    static poole_user_spin: u8;
    static poole_user_spin_pause: u8;
    static poole_user_spin_jump: u8;
    static poole_user_calls: u8;
    static poole_user_calls_done: u8;
}

fn layout() -> Result<Layout, Error> {
    let start = (&raw const poole_user_payload) as u64;
    let offset = |p: *const u8| (p as u64).checked_sub(start).ok_or(Error::Layout);
    Ok(Layout {
        cli: offset(&raw const poole_user_cli)?,
        io: offset(&raw const poole_user_io)?,
        syscall: offset(&raw const poole_user_syscall)?,
        read_kernel: offset(&raw const poole_user_read_kernel)?,
        nx_resume: offset(&raw const poole_user_nx_resume)?,
        done: offset(&raw const poole_user_done)?,
        end: offset(&raw const poole_user_payload_end)?,
    })
}

pub fn payload() -> Result<&'static [u8], Error> {
    let len = layout()?.end;
    if len == 0 || len > 4096 - 16 {
        return Err(Error::Layout);
    }
    // SAFETY: linked assembly bounds one immutable executable section, with no relocations inside.
    Ok(unsafe { core::slice::from_raw_parts(&raw const poole_user_payload, len as usize) })
}

fn controls() -> Controls {
    // SAFETY: this module is called only by the exclusive CPL0 BSP profile.
    unsafe {
        Controls {
            cr0: read_cr0(),
            cr4: read_cr4(),
            efer: read_efer(),
        }
    }
}

unsafe fn observe_fx() -> *const u8 {
    let p = unsafe { (&raw mut OBSERVED_FX.0).cast::<u8>() };
    // SAFETY: exclusive profile owns the aligned static and enabled legacy FXSR.
    unsafe {
        write_bytes(p, 0, 512);
        fxsave_area(p);
    }
    p
}

unsafe fn verify_initial_fx() -> Result<(), Error> {
    // SAFETY: legacy FPU controls were configured and this static is private.
    let p = unsafe { observe_fx() };
    if unsafe { read_unaligned(p.cast::<u16>()) } != 0x037f
        || unsafe { read_unaligned(p.add(24).cast::<u32>()) } != 0x1f80
        || !all_zero(unsafe { p.add(2) }, 22)
        || !all_zero(unsafe { p.add(32) }, 384)
    {
        return Err(Error::Registers);
    }
    Ok(())
}

unsafe fn initialize_fx() -> Result<(), Error> {
    let canonical = unsafe { (&raw mut INITIAL_FX.0).cast::<u8>() };
    // SAFETY: enabled x87/SSE, aligned writable observation buffer; no other FP owner.
    let observed = unsafe { observe_fx() };
    let mask = effective_mxcsr_mask(unsafe { read_unaligned(observed.add(28).cast::<u32>()) });
    if 0x1f80 & !mask != 0 {
        return Err(Error::Registers);
    }
    // Restore the full legacy register payload, not FNINIT alone (which leaves data behind).
    unsafe {
        write_bytes(canonical, 0, 512);
        write_unaligned(canonical.cast::<u16>(), 0x037f);
        write_unaligned(canonical.add(24).cast::<u32>(), 0x1f80);
        write_unaligned(canonical.add(28).cast::<u32>(), mask);
        asm!("fxrstor64 [{}]", in(reg) canonical, options(readonly, nostack));
        verify_initial_fx()
    }
}

unsafe fn auxiliary_clean(sep: bool) -> Result<(), Error> {
    // SAFETY: long-mode MSRs and debug registers are owned by this CPL0 BSP profile.
    unsafe {
        for address in [IA32_FS_BASE, IA32_GS_BASE, IA32_KERNEL_GS_BASE] {
            if read_msr(address) != 0 {
                return Err(Error::Registers);
            }
        }
        if sep {
            for address in [0x174, 0x175, 0x176] {
                if read_msr(address) != 0 {
                    return Err(Error::Registers);
                }
            }
        }
        let (a, b, c, d, dr6, dr7): (u64, u64, u64, u64, u64, u64);
        asm!("mov {}, dr0", "mov {}, dr1", "mov {}, dr2", "mov {}, dr3", "mov {}, dr6", "mov {}, dr7",
            out(reg) a,out(reg) b,out(reg) c,out(reg) d,out(reg) dr6,out(reg) dr7,options(nomem,nostack,preserves_flags));
        let ldt: u16;
        asm!("sldt {:x}",out(reg) ldt,options(nomem,nostack,preserves_flags));
        if a | b | c | d != 0 || dr7 != 0x400 || dr6 & 0xe00f != 0 || ldt != 0 {
            return Err(Error::Registers);
        }
    }
    Ok(())
}

pub struct Entry {
    baseline: Controls,
    original_rsp0: u64,
    sep: bool,
    installed: bool,
    budget: Option<preemption::Budget>,
}

impl Entry {
    /// Caller owns the BSP at CPL0, IF clear, no other FP/debug/segment owner,
    /// no AP/DMA or concurrent descriptor/control mutation, and a soft-float kernel.
    /// This bounded profile leaves the stricter CPU baseline installed until halt.
    pub unsafe fn prepare(original_rsp0: u64) -> Result<Self, Error> {
        if read_rflags() & (1 << 9) != 0 || ACTIVE_ROOT.load(Ordering::Acquire) != 0 {
            return Err(Error::Context);
        }
        let leaf1 = cpuid(1, 0);
        let baseline = controls().plan(leaf1.edx)?;
        let sep = leaf1.edx & (1 << 11) != 0;
        // SAFETY: policy validates the exact control changes, CPUID reports FXSR/SSE/MSR.
        unsafe {
            write_cr0(baseline.cr0);
            write_cr4(baseline.cr4);
            write_msr(IA32_EFER, baseline.efer);
            for address in [IA32_FS_BASE, IA32_GS_BASE, IA32_KERNEL_GS_BASE] {
                write_msr(address, 0);
            }
            if sep {
                for address in [0x174, 0x175, 0x176] {
                    write_msr(address, 0);
                }
            }
            asm!("mov dr7, {clear}", "mov dr0, {zero}", "mov dr1, {zero}", "mov dr2, {zero}",
                "mov dr3, {zero}", "mov dr6, {reset}", "lldt {zero:x}",
                clear=in(reg) 0x400u64,zero=in(reg) 0u64,reset=in(reg) 0xffff0ff0u64,
                options(nomem,nostack,preserves_flags));
            auxiliary_clean(sep)?;
            initialize_fx()?;
        }
        if controls() != baseline {
            return Err(Error::Context);
        }
        Ok(Self {
            baseline,
            original_rsp0,
            sep,
            installed: false,
            budget: None,
        })
    }

    pub fn set_timer_budget(&mut self, budget: preemption::Budget) -> Result<(), Error> {
        if self.installed || active() {
            return Err(Error::State);
        }
        self.budget = Some(budget.validate()?);
        Ok(())
    }

    pub fn preemption_observation(&self) -> Result<preemption::Observation, Error> {
        // SAFETY: exclusive owner, IF clear after the assembly returns.
        unsafe { (&*(&raw const PREEMPT)).as_ref() }
            .ok_or(Error::State)?
            .observation()
    }

    fn context(&self, root: u64) -> Result<(), Error> {
        // SAFETY: this private adapter was created under the exclusive CPL0 lease.
        if root == 0
            || unsafe { read_cr3() } != root
            || controls() != self.baseline
            || read_rflags() & (1 << 9) != 0
        {
            return Err(Error::Context);
        }
        unsafe { auxiliary_clean(self.sep) }
    }

    pub fn syscall_observation(&self) -> Result<CallObservation, Error> {
        super::user_syscall::observe()
    }
}

unsafe fn install() -> Result<(), Error> {
    // SAFETY: active root owns a validated guarded stack, all descriptor storage is retained.
    let state = unsafe { install_interrupt_descriptor_tables(STACK_TOP) };
    poolekernel::validate_interrupt_descriptor_state(&state).map_err(|_| Error::Context)?;
    let mut gdt = [0u64; 7];
    unsafe {
        core::ptr::copy_nonoverlapping((&raw const GDT.0).cast::<u64>(), gdt.as_mut_ptr(), 5);
    }
    gdt[3] &= !(2 << 40); // LTR requires available, not the previous busy TSS descriptor.
    gdt[5] = user_entry::USER_DATA_DESCRIPTOR;
    gdt[6] = user_entry::USER_CODE_DESCRIPTOR;
    unsafe {
        write_volatile(&raw mut USER_GDT.0, gdt);
    }
    let pointer = DescriptorPointer {
        limit: user_entry::USER_GDT_LIMIT,
        base: unsafe { (&raw const USER_GDT.0) as u64 },
    };
    unsafe {
        load_gdt_and_tss(&pointer);
    }
    // IST=0 makes CPL3 faults use this task's TSS.RSP0, not the shared test IST.
    for (vector, handler) in [
        (6, poole_trap_invalid_opcode as *const () as u64),
        (13, poole_trap_general_protection as *const () as u64),
        (14, poole_trap_page_fault as *const () as u64),
        (
            usize::from(crate::TIMER_VECTOR),
            poole_interrupt_timer as *const () as u64,
        ),
    ] {
        unsafe {
            write_volatile(
                (&raw mut IDT.0).cast::<IdtGate>().add(vector),
                IdtGate::interrupt(handler, 0),
            );
        }
    }
    let mut observed = DescriptorPointer { limit: 0, base: 0 };
    unsafe {
        asm!("sgdt [{}]",in(reg) &raw mut observed,options(nostack,preserves_flags));
    }
    let limit = unsafe { read_unaligned(&raw const observed.limit) };
    let base = unsafe { read_unaligned(&raw const observed.base) };
    let rsp0 = unsafe { read_unaligned((&raw const TSS.0.rsp).cast::<u64>()) };
    let iomap = unsafe { read_unaligned(&raw const TSS.0.iomap_base) };
    if limit != pointer.limit
        || base != pointer.base
        || rsp0 != STACK_TOP
        || iomap != size_of::<TaskStateSegment>() as u16
    {
        return Err(Error::Context);
    }
    Ok(())
}

impl Driver for Entry {
    fn execute(&mut self, image: ImageAdmission) -> Result<Observation, Error> {
        self.context(image.root_physical)?;
        if self.installed
            || ACTIVE_ROOT.load(Ordering::Acquire) != 0
            || unsafe { read_volatile(&raw const poole_user_saved_rsp) } != 0
        {
            return Err(Error::State);
        }
        let sequence = Sequence::new(image, layout()?)?;
        let preempt = if let Some(budget) = self.budget {
            let start = (&raw const poole_user_payload) as u64;
            let offset = |p: *const u8| (p as u64).checked_sub(start).ok_or(Error::Layout);
            Some(super::user_preempt::Session::new(
                image,
                preemption::Layout {
                    increment: offset(&raw const poole_user_spin)?,
                    pause: offset(&raw const poole_user_spin_pause)?,
                    jump: offset(&raw const poole_user_spin_jump)?,
                    end: layout()?.end,
                },
                budget,
            )?)
        } else {
            None
        };
        self.installed = true;
        // SAFETY: lifetime marked before descriptor writes, exclusive CPU/root retained by CpuImage.
        unsafe {
            install()?;
            initialize_fx()?;
            super::user_syscall::prepare(image)?;
            write_volatile(&raw mut LIVE, Some(sequence));
            write_volatile(&raw mut PREEMPT, preempt);
        }
        ACTIVE_ROOT.store(image.root_physical, Ordering::Release);
        RETURN_STACK_TOP.store(self.original_rsp0, Ordering::Release);
        // SAFETY: exact user frame/mappings, full cleared CPU state, private TSS entry stack,
        // fixed fault payload followed only by the optional timer-controlled spin;
        // that timer remains masked until its private-stack fault handoff.
        unsafe {
            poole_user_enter(&image.initial_frame);
        }
        self.context(image.root_physical)?;
        let count = unsafe { (&*(&raw const LIVE)).as_ref() }
            .ok_or(Error::State)?
            .completed();
        if count != privilege::TRAP_COUNT
            || (self.budget.is_some()
                && self.preemption_observation()?.deliveries != preemption::DELIVERIES)
        {
            return Err(Error::State);
        }
        Ok(Observation {
            root: image.root_physical,
            traps: count,
            cpl: 3,
            restored: true,
        })
    }

    fn quiesce(&mut self, root: u64) -> Result<(), Error> {
        super::user_syscall::clear(root)?;
        self.context(root)?;
        if !self.installed {
            return Ok(());
        }
        if unsafe { (&*(&raw const PREEMPT)).as_ref() }.is_some_and(|s| !s.shutdown_verified()) {
            return Err(Error::Hardware);
        }
        // SAFETY: CPL0/IF0 after bounded return. Detach all private-stack descriptor references.
        let state = unsafe { install_interrupt_descriptor_tables(self.original_rsp0) };
        poolekernel::validate_interrupt_descriptor_state(&state).map_err(|_| Error::Context)?;
        if unsafe { read_unaligned((&raw const TSS.0.rsp).cast::<u64>()) } != self.original_rsp0 {
            return Err(Error::Context);
        }
        unsafe {
            initialize_fx()?;
            write_volatile(&raw mut LIVE, None);
            write_volatile(&raw mut TASK, None);
            write_volatile(&raw mut PREEMPT, None);
            write_volatile(&raw mut poole_user_saved_rsp, 0);
        }
        ACTIVE_ROOT.store(0, Ordering::Release);
        RETURN_STACK_TOP.store(0, Ordering::Release);
        self.installed = false;
        Ok(())
    }
}

pub fn active() -> bool {
    ACTIVE_ROOT.load(Ordering::Acquire) != 0
}

fn snapshot(frame: &TrapFrame, depth: u32) -> Trap {
    Trap {
        root: unsafe { read_cr3() },
        vector: frame.vector,
        error: frame.error_code,
        rip: frame.rip,
        cs: frame.code_selector,
        flags: frame.rflags,
        rsp: frame.rsp,
        ss: frame.data_selector,
        cr2: read_cr2(),
        handler_stack: frame as *const _ as u64,
        depth,
        registers: [
            frame.r15, frame.r14, frame.r13, frame.r12, frame.r11, frame.r10, frame.r9, frame.r8,
            frame.rsi, frame.rdi, frame.rbp, frame.rdx, frame.rcx, frame.rbx, frame.rax,
        ],
    }
}

pub fn recover_copy_fault(frame: &mut TrapFrame, depth: u32) -> bool {
    if !active() || unsafe { read_cr3() } != ACTIVE_ROOT.load(Ordering::Acquire) {
        return false;
    }
    let t = snapshot(frame, depth);
    if let Some(rip) = super::user_syscall::recover(&t) {
        frame.rip = rip;
        true
    } else {
        false
    }
}

fn denied(stage: u64, error: Error, t: &Trap) -> ! {
    // Failure-only, bounded early output. Never return to a rejected user frame.
    let mut serial = unsafe { Com1::initialize() };
    let mut debugcon = DebugCon::new();
    let mut log = crate::EarlyLogger::new(crate::BootSink {
        serial: &mut serial,
        debugcon: &mut debugcon,
        ring: &crate::EARLY_RING,
    });
    log.write_str("POOLEOS:KERNEL:USER-ENTRY DENIED stage=");
    log.write_decimal_u64(stage);
    log.write_str(" error=");
    log.write_decimal_u64(error as u64);
    for (name, value) in [
        (" vector=", t.vector),
        (" rip=", t.rip),
        (" flags=", t.flags),
        (" stack=", t.handler_stack),
        (" progress=", t.registers[0]),
    ] {
        log.write_str(name);
        log.write_hex_u64(value);
    }
    log.write_str("\n");
    crate::poole_kernel_emergency_panic(poolekernel::PanicCode::UserRoot as u32)
}

pub fn dispatch(frame: &mut TrapFrame, depth: u32) {
    let reject =
        || -> ! { crate::poole_kernel_emergency_panic(poolekernel::PanicCode::UserRoot as u32) };
    let root = unsafe { read_cr3() };
    if !active() || root != ACTIVE_ROOT.load(Ordering::Acquire) || read_rflags() & (1 << 9) != 0 {
        reject();
    }
    let t = snapshot(frame, depth);
    if slices::active() {
        slices::dispatch(&t, frame);
        crate::TRAP_DEPTH.store(0, Ordering::Release);
        return;
    }
    if unsafe { (&*(&raw const TASK)).is_some() } {
        tasks::dispatch(&t, frame);
        crate::TRAP_DEPTH.store(0, Ordering::Release);
        return;
    }
    // SAFETY: entry serialized one BSP, IF0; no reference to LIVE survives IRETQ.
    let sequence = unsafe { (&mut *(&raw mut LIVE)).as_mut() }.unwrap_or_else(|| reject());
    if t.vector == syscall::VECTOR {
        if sequence.completed() != privilege::TRAP_COUNT {
            reject()
        }
        if super::user_syscall::dispatch(&t, frame)
            .unwrap_or_else(|e| denied(4, e, &t))
            .is_some()
        {
            denied(4, Error::State, &t);
        }
        crate::TRAP_DEPTH.store(0, Ordering::Release);
        return;
    }
    let calls_done = sequence.image().initial_frame.rip
        + ((&raw const poole_user_calls_done) as u64 - (&raw const poole_user_payload) as u64);
    if sequence.completed() == privilege::TRAP_COUNT && t.vector == 6 && t.rip == calls_done {
        let checked = Trap {
            vector: syscall::VECTOR,
            ..t
        };
        syscall::frame(sequence.image(), &checked).unwrap_or_else(|e| denied(5, e, &t));
        super::user_syscall::finish(root).unwrap_or_else(|e| denied(6, e, &t));
        frame.rflags = user_entry::INITIAL_RFLAGS;
        if let Some(session) = unsafe { (&mut *(&raw mut PREEMPT)).as_mut() } {
            frame.rip = session.start(&t).unwrap_or_else(|e| denied(3, e, &t));
        } else {
            return_kernel(frame)
        }
        crate::TRAP_DEPTH.store(0, Ordering::Release);
        return;
    }
    if frame.vector == u64::from(crate::TIMER_VECTOR) {
        let session = unsafe { (&mut *(&raw mut PREEMPT)).as_mut() }.unwrap_or_else(|| reject());
        if sequence.completed() != privilege::TRAP_COUNT {
            reject();
        }
        if session.interrupt(&t).unwrap_or_else(|e| denied(1, e, &t)) {
            return_kernel(frame);
        } else {
            frame.rflags = user_entry::INITIAL_RFLAGS;
        }
        crate::TRAP_DEPTH.store(0, Ordering::Release);
        return;
    }
    if sequence.completed() == 0 {
        let (ds, es, fs, gs): (u16, u16, u16, u16);
        unsafe {
            asm!("mov {:x}, ds","mov {:x}, es","mov {:x}, fs","mov {:x}, gs",
            out(reg) ds,out(reg) es,out(reg) fs,out(reg) gs,options(nomem,nostack,preserves_flags));
        }
        if ds != user_entry::USER_DATA_SELECTOR as u16
            || es != ds
            || fs != 0
            || gs != 0
            || unsafe { verify_initial_fx() }.is_err()
        {
            reject();
        }
    }
    let action = sequence.accept(&t).unwrap_or_else(|e| denied(2, e, &t));
    frame.rflags = user_entry::INITIAL_RFLAGS;
    match action {
        Action::Resume(rip) => frame.rip = rip,
        Action::ReturnKernel => {
            let p = unsafe { observe_fx() };
            if (0..16).any(|i| unsafe { p.add(160 + i).read_volatile() } != 0xff) {
                reject();
            }
            super::user_syscall::enable().unwrap_or_else(|e| denied(7, e, &t));
            frame.rip = sequence.image().initial_frame.rip
                + ((&raw const poole_user_calls) as u64 - (&raw const poole_user_payload) as u64);
        }
    }
    crate::TRAP_DEPTH.store(0, Ordering::Release);
}

fn return_kernel(frame: &mut TrapFrame) {
    let saved = unsafe { read_volatile(&raw const poole_user_saved_rsp) };
    let top = RETURN_STACK_TOP.load(Ordering::Acquire);
    if top < poolekernel::virtual_memory::KERNEL_IMAGE_START
        || saved < top - poolekernel::BOOTSTRAP_STACK_PAGE_COUNT * 4096
        || saved >= top
        || saved & 7 != 0
        || (STACK_BOTTOM..STACK_TOP).contains(&saved)
    {
        crate::poole_kernel_emergency_panic(poolekernel::PanicCode::UserRoot as u32);
    }
    frame.rip = poole_user_return as *const () as u64;
    frame.code_selector = u64::from(KERNEL_CODE_SELECTOR);
    frame.data_selector = u64::from(KERNEL_DATA_SELECTOR);
    frame.rsp = saved;
    frame.rflags = 2;
}

core::arch::global_asm!(
    r#"
    .section .text.poole_user_entry,"ax",@progbits
    .global poole_user_enter
    .type poole_user_enter,@function
poole_user_enter:
    push rbp
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov qword ptr [rip + poole_user_saved_rsp], rsp
    push qword ptr [rdi + 32]
    push qword ptr [rdi + 24]
    push qword ptr [rdi + 16]
    push qword ptr [rdi + 8]
    push qword ptr [rdi]
    mov eax, 0x2b
    mov ds, ax
    mov es, ax
    xor eax, eax
    mov fs, ax
    mov gs, ax
    xor ebx, ebx
    xor ecx, ecx
    xor edx, edx
    xor ebp, ebp
    xor edi, edi
    xor esi, esi
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    xor r11d, r11d
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    xor r15d, r15d
    iretq
    .global poole_user_return
poole_user_return:
    cli
    mov eax, 0x10
    mov ds, ax
    mov es, ax
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret
    .size poole_user_enter, .-poole_user_enter

    .section .text.poole_user_payload,"ax",@progbits
    .global poole_user_payload
poole_user_payload:
    ud2
    .global poole_user_cli
poole_user_cli:
    cli
    .global poole_user_io
poole_user_io:
    out 0x80, al
    .global poole_user_syscall
poole_user_syscall:
    syscall
    movabs rax, 0xffffffff80000000
    .global poole_user_read_kernel
poole_user_read_kernel:
    mov rax, qword ptr [rax]
    lea rax, [rsp - 16]
    jmp rax
    .global poole_user_nx_resume
poole_user_nx_resume:
    pcmpeqb xmm0, xmm0
    fld1
    .global poole_user_done
poole_user_done:
    ud2
    .macro POOLE_CALL_CHECK status, result
    syscall
    cmp rax, \status
    jne poole_user_call_failed
    cmp rdx, \result
    jne poole_user_call_failed
    .endm
    .global poole_user_calls
poole_user_calls:
    mov edi, 1
    xor eax, eax
    xor esi, esi
    xor edx, edx
    xor r10d, r10d
    xor r8d, r8d
    xor r9d, r9d
    std
    POOLE_CALL_CHECK 0, 1
    mov eax, 99
    POOLE_CALL_CHECK 2, 0
    xor eax, eax
    mov edi, 2
    POOLE_CALL_CHECK 1, 0
    mov edi, 1
    mov eax, 1
    mov r8d, 1
    POOLE_CALL_CHECK 3, 0
    xor r8d, r8d
    movabs rbx, 0x504f4f4c454f5321
    mov qword ptr [rsp - 63], rbx
    lea rsi, [rsp - 63]
    lea rdx, [rsp - 127]
    mov r10d, 8
    mov eax, 1
    POOLE_CALL_CHECK 0, 8
    cmp qword ptr [rsp - 127], rbx
    jne poole_user_call_failed
    mov eax, 1
    xor esi, esi
    xor edx, edx
    xor r10d, r10d
    POOLE_CALL_CHECK 0, 0
    mov eax, 1
    mov r10d, 257
    POOLE_CALL_CHECK 3, 0
    mov eax, 1
    mov r10d, 8
    movabs rsi, 0xffffffff80000000
    lea rdx, [rsp - 127]
    POOLE_CALL_CHECK 3, 0
    mov eax, 1
    mov rsi, -4
    lea rdx, [rsp - 127]
    POOLE_CALL_CHECK 3, 0
    mov eax, 1
    lea rsi, [rsp - 4]
    lea rdx, [rsp - 127]
    POOLE_CALL_CHECK 4, 0
    cmp qword ptr [rsp - 127], rbx
    jne poole_user_call_failed
    mov eax, 1
    lea rsi, [rsp - 63]
    lea rdx, [rsp - 4]
    POOLE_CALL_CHECK 4, 4
    cmp dword ptr [rsp - 4], ebx
    jne poole_user_call_failed
    mov eax, 1
    lea rsi, [rsp - 63]
    lea rdx, [rip + poole_user_payload]
    POOLE_CALL_CHECK 4, 0
    .global poole_user_calls_done
poole_user_calls_done:
    ud2
poole_user_call_failed:
    ud2
    .global poole_user_spin
poole_user_spin:
    lea r15, [r15 + 1]
    .global poole_user_spin_pause
poole_user_spin_pause:
    pause
    .global poole_user_spin_jump
poole_user_spin_jump:
    jmp poole_user_spin
    .global poole_user_payload_end
poole_user_payload_end:
"#
);
