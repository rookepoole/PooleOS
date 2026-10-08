//! One owned, resumable CPL3 quantum. Scheduling runs on the original kernel root.
use super::*;
use poolekernel::scheduler_smp::TaskId;
use poolekernel::user_entry::{
    context::Context,
    task::{Event, Slice},
};

struct Saved {
    context: Context,
    fx: FxsaveArea,
}
struct Session {
    image: ImageAdmission,
    run: task::Run,
    budget: preemption::Budget,
    start: u64,
    saved: Option<Saved>,
    event: Option<Event>,
    ticks: Option<u64>,
}
static mut SLICE: Option<Session> = None;
pub(super) fn active() -> bool {
    unsafe { (&*(&raw const SLICE)).is_some() }
}

pub struct PeerEntry {
    entry: Entry,
    run: Option<task::Run>,
    saved: Option<Saved>,
    budget: Option<preemption::Budget>,
    suppress_local: bool,
    lose_sample: bool,
    arguments: [u64; 6],
}
impl PeerEntry {
    /// Same sole-BSP, IF0 and state-ownership preconditions as Entry::prepare.
    pub unsafe fn new(original_rsp0: u64) -> Result<Self, Error> {
        Ok(Self {
            entry: unsafe { Entry::prepare(original_rsp0)? },
            run: None,
            saved: None,
            budget: None,
            suppress_local: false,
            lose_sample: false,
            arguments: [0; 6],
        })
    }
    pub fn set_budget(&mut self, budget: preemption::Budget) -> Result<(), Error> {
        if self.entry.installed || super::active() || active() {
            return Err(Error::State);
        }
        self.budget = Some(budget.validate()?);
        Ok(())
    }
    pub fn set_initial_arguments(&mut self, arguments: [u64; 6]) -> Result<(), Error> {
        if self.entry.installed
            || self.run.is_some()
            || self.saved.is_some()
            || super::active()
            || active()
        {
            return Err(Error::State);
        }
        self.arguments = arguments;
        Ok(())
    }
    pub fn inject_missing_local_timer(&mut self) -> Result<(), Error> {
        if self.entry.installed || self.run.is_some() || active() {
            return Err(Error::State);
        }
        self.suppress_local = true;
        Ok(())
    }
    /// Development fault injection after a real authenticated quantum returns.
    pub fn inject_lost_sample(&mut self) -> Result<(), Error> {
        if self.entry.installed || self.run.is_some() || active() {
            return Err(Error::State);
        }
        self.lose_sample = true;
        Ok(())
    }
}
impl task::Driver for PeerEntry {
    fn revoke(&mut self, id: TaskId) -> Result<(), Error> {
        unsafe { super::super::user_ipc::detach(id) }
    }
    fn execute(&mut self, _: ImageAdmission, _: TaskId) -> Result<task::Outcome, Error> {
        Err(Error::State)
    }
    fn quiesce(&mut self, root: u64) -> Result<(), Error> {
        if crate::IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != 0 {
            return Err(Error::Hardware);
        }
        privilege::Driver::quiesce(&mut self.entry, root)?;
        unsafe {
            write_volatile(&raw mut SLICE, None);
        }
        Ok(())
    }
}
impl task::SliceDriver for PeerEntry {
    fn complete_wait(
        &mut self,
        id: TaskId,
        ticket: poolekernel::capability_ipc::wait::Ticket,
        status: syscall::Status,
    ) -> Result<(), Error> {
        if self.entry.installed
            || super::active()
            || active()
            || !matches!(
                status,
                syscall::Status::Ok | syscall::Status::Cancelled | syscall::Status::Revoked
            )
        {
            return Err(Error::State);
        }
        let run = self.run.as_ref().ok_or(Error::State)?;
        let image = run.admission();
        if !run.matches(image, id) || !ticket.matches_image(id, image) {
            return Err(Error::State);
        }
        let saved = self.saved.as_mut().ok_or(Error::State)?;
        let mut context = saved.context;
        context.registers[14] = status as u64;
        context.registers[11] = 0;
        context.frame.rflags &= !((1 << 10) | (1 << 16));
        context.validate(image)?;
        saved.context = context;
        Ok(())
    }
    fn execute_slice(&mut self, image: ImageAdmission, id: TaskId) -> Result<Slice, Error> {
        self.entry.context(image.root_physical)?;
        if self.entry.installed
            || super::active()
            || active()
            || unsafe {
                (&*(&raw const LIVE)).is_some()
                    || (&*(&raw const TASK)).is_some()
                    || (&*(&raw const PREEMPT)).is_some()
                    || read_volatile(&raw const poole_user_saved_rsp) != 0
            }
        {
            return Err(Error::State);
        }
        let budget = self.budget.ok_or(Error::State)?;
        if self.run.as_ref().is_some_and(|r| !r.matches(image, id)) {
            return Err(Error::State);
        }
        let context = self
            .saved
            .as_ref()
            .map(|s| s.context)
            .unwrap_or_else(|| Context::initial_with_arguments(image, self.arguments));
        context.validate(image)?;
        let run = match self.run.take() {
            Some(r) => r,
            None => task::Run::new(image, id)?,
        };
        self.entry.installed = true;
        // Install and restore only after the owning CpuImage entered quarantine.
        unsafe {
            install()?;
            initialize_fx()?;
            if let Some(saved) = self.saved.as_ref() {
                asm!("fxrstor64 [{}]", in(reg) saved.fx.0.as_ptr(), options(readonly, nostack));
            }
            super::super::user_syscall::prepare(image)?;
            write_volatile(
                &raw mut SLICE,
                Some(Session {
                    image,
                    run,
                    budget,
                    start: 0,
                    saved: None,
                    event: None,
                    ticks: None,
                }),
            );
        }
        ACTIVE_ROOT.store(image.root_physical, Ordering::Release);
        RETURN_STACK_TOP.store(self.entry.original_rsp0, Ordering::Release);
        super::super::user_syscall::enable()?;
        let start = super::super::user_preempt::arm_quantum(budget, self.suppress_local)?;
        unsafe { (&mut *(&raw mut SLICE)).as_mut() }
            .ok_or(Error::State)?
            .start = start;
        // SAFETY: checked private frame, full GPR/legacy-FP ownership; kernel stays IF0.
        unsafe {
            poole_user_resume(&context);
        }
        self.entry.context(image.root_physical)?;
        let session = unsafe { (&mut *(&raw mut SLICE)).take() }.ok_or(Error::State)?;
        let event = session.event.ok_or(Error::State)?;
        let ticks = session.ticks.ok_or(Error::State)?;
        self.run = Some(session.run);
        self.saved = session.saved;
        if self.lose_sample {
            self.lose_sample = false;
            return Err(Error::Hardware);
        }
        Ok(Slice {
            id,
            root: image.root_physical,
            ticks,
            event,
        })
    }
}

pub(super) fn dispatch(t: &Trap, frame: &mut TrapFrame) {
    let s =
        unsafe { (&mut *(&raw mut SLICE)).as_mut() }.unwrap_or_else(|| denied(11, Error::State, t));
    if s.event.is_some() {
        denied(11, Error::State, t);
    }
    if t.vector == u64::from(user_entry::timer::watchdog::VECTOR) {
        let outcome = s.run.watchdog(t).unwrap_or_else(|e| denied(16, e, t));
        s.ticks = Some(
            super::super::user_watchdog::finish(s.budget, s.start)
                .unwrap_or_else(|e| denied(16, e, t)),
        );
        s.event = Some(Event::Terminated(outcome));
    } else if t.vector == u64::from(crate::TIMER_VECTOR) {
        let resumable = s.run.preempt(t).unwrap_or_else(|e| denied(11, e, t));
        let ticks = super::super::user_preempt::finish_quantum(s.budget, s.start)
            .unwrap_or_else(|e| denied(12, e, t));
        s.ticks = Some(ticks);
        if crate::IRQ_TIMER_DELIVERIES.fetch_add(1, Ordering::AcqRel) != 0
            || crate::IRQ_EOI_COUNT.fetch_add(1, Ordering::AcqRel) != 0
        {
            denied(12, Error::Hardware, t);
        }
        if resumable {
            let context = Context::capture(s.image, t).unwrap_or_else(|e| denied(11, e, t));
            let mut fx = FxsaveArea([0; 512]);
            unsafe {
                fxsave_area(fx.0.as_mut_ptr());
            }
            s.saved = Some(Saved { context, fx });
            s.event = Some(Event::Preempted {
                ticks,
                syscalls: s.run.calls(),
                progress: t.registers[0],
            });
        } else {
            s.event = Some(Event::Terminated(
                s.run
                    .outcome()
                    .unwrap_or_else(|| denied(11, Error::State, t)),
            ));
        }
    } else {
        if t.vector == syscall::VECTOR {
            if s.run.call(t).unwrap_or_else(|e| denied(13, e, t)) {
                let caller = s.run.ipc_caller(t).unwrap_or_else(|e| denied(13, e, t));
                match super::super::user_syscall::dispatch_owned(t, frame, Some(caller))
                    .unwrap_or_else(|e| denied(13, e, t))
                {
                    super::super::user_syscall::Action::Returned => return,
                    super::super::user_syscall::Action::Exit(code) => {
                        s.run.exit(code).unwrap_or_else(|e| denied(13, e, t));
                    }
                    super::super::user_syscall::Action::Waiting(ticket) => {
                        let context =
                            Context::capture(s.image, t).unwrap_or_else(|e| denied(13, e, t));
                        let mut fx = FxsaveArea([0; 512]);
                        unsafe {
                            fxsave_area(fx.0.as_mut_ptr());
                        }
                        s.saved = Some(Saved { context, fx });
                        s.ticks = Some(
                            super::super::user_preempt::terminal_ticks(s.budget, s.start)
                                .unwrap_or_else(|e| denied(14, e, t)),
                        );
                        s.event = Some(Event::Waiting {
                            ticket,
                            syscalls: s.run.calls(),
                        });
                        super::super::user_syscall::disable(t.root)
                            .unwrap_or_else(|e| denied(15, e, t));
                        return_kernel(frame);
                        return;
                    }
                }
            }
        } else {
            s.run.fault(t).unwrap_or_else(|e| denied(14, e, t));
            acknowledge_user_fault(t).unwrap_or_else(|e| denied(14, e, t));
        }
        s.ticks = Some(
            super::super::user_preempt::terminal_ticks(s.budget, s.start)
                .unwrap_or_else(|e| denied(14, e, t)),
        );
        s.event = Some(Event::Terminated(
            s.run
                .outcome()
                .unwrap_or_else(|| denied(14, Error::State, t)),
        ));
    }
    super::super::user_syscall::disable(t.root).unwrap_or_else(|e| denied(15, e, t));
    return_kernel(frame);
}

unsafe extern "C" {
    fn poole_user_resume(context: *const Context);
    static poole_peer_exit: u8;
    static poole_peer_exit_end: u8;
    static poole_peer_fault: u8;
    static poole_peer_fault_end: u8;
    static poole_peer_spin: u8;
    static poole_peer_spin_end: u8;
    static poole_peer_survivor: u8;
    static poole_peer_survivor_end: u8;
    static poole_peer_limit: u8;
    static poole_peer_limit_end: u8;
    static poole_peer_bad_stack: u8;
    static poole_peer_bad_stack_end: u8;
    static poole_peer_noncanonical_stack: u8;
    static poole_peer_noncanonical_stack_end: u8;
    static poole_peer_nt: u8;
    static poole_peer_nt_end: u8;
    static poole_peer_ac: u8;
    static poole_peer_ac_end: u8;
    static poole_peer_last_syscall: u8;
    static poole_peer_last_syscall_end: u8;
    static poole_peer_timer_stack: u8;
    static poole_peer_timer_stack_end: u8;
    static poole_peer_divide: u8;
    static poole_peer_divide_end: u8;
    static poole_peer_debug: u8;
    static poole_peer_debug_end: u8;
    static poole_peer_breakpoint: u8;
    static poole_peer_breakpoint_end: u8;
    static poole_peer_stack_fault: u8;
    static poole_peer_stack_fault_end: u8;
}
pub fn peer_payload(kind: usize) -> Result<&'static [u8], Error> {
    if kind == 18 || kind == 19 {
        return super::super::user_ipc::pressure_payload(kind == 19);
    }
    if kind == 16 || kind == 17 {
        return super::super::user_ipc::payload(kind == 17);
    }
    let (s, e) = match kind {
        0 => (&raw const poole_peer_exit, &raw const poole_peer_exit_end),
        1 => (&raw const poole_peer_fault, &raw const poole_peer_fault_end),
        2 => (&raw const poole_peer_spin, &raw const poole_peer_spin_end),
        3 => (
            &raw const poole_peer_survivor,
            &raw const poole_peer_survivor_end,
        ),
        4 => (&raw const poole_peer_limit, &raw const poole_peer_limit_end),
        5 => (
            &raw const poole_peer_bad_stack,
            &raw const poole_peer_bad_stack_end,
        ),
        6 => (
            &raw const poole_peer_noncanonical_stack,
            &raw const poole_peer_noncanonical_stack_end,
        ),
        7 => (&raw const poole_peer_nt, &raw const poole_peer_nt_end),
        8 => (&raw const poole_peer_ac, &raw const poole_peer_ac_end),
        9 => (
            &raw const poole_peer_last_syscall,
            &raw const poole_peer_last_syscall_end,
        ),
        10 => (
            &raw const poole_peer_timer_stack,
            &raw const poole_peer_timer_stack_end,
        ),
        11 => (
            &raw const poole_peer_divide,
            &raw const poole_peer_divide_end,
        ),
        12 => (&raw const poole_peer_debug, &raw const poole_peer_debug_end),
        13 => (
            &raw const poole_peer_breakpoint,
            &raw const poole_peer_breakpoint_end,
        ),
        14 => (
            &raw const poole_peer_stack_fault,
            &raw const poole_peer_stack_fault_end,
        ),
        _ => return Err(Error::Layout),
    };
    let n = (e as usize).checked_sub(s as usize).ok_or(Error::Layout)?;
    if n == 0 || n > 4080 {
        return Err(Error::Layout);
    }
    Ok(unsafe { core::slice::from_raw_parts(s, n) })
}

core::arch::global_asm!(
    r#"
    .section .text.poole_user_resume,"ax",@progbits
    .global poole_user_resume
poole_user_resume:
    push rbp
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov qword ptr [rip + poole_user_saved_rsp], rsp
    push qword ptr [rdi + 152]
    push qword ptr [rdi + 144]
    push qword ptr [rdi + 136]
    push qword ptr [rdi + 128]
    push qword ptr [rdi + 120]
    mov eax, 0x2b
    mov ds, ax
    mov es, ax
    xor eax, eax
    mov fs, ax
    mov gs, ax
    .set regoff, 112
    .rept 15
    push qword ptr [rdi + regoff]
    .set regoff, regoff - 8
    .endr
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rsi
    pop rdi
    pop rbp
    pop rdx
    pop rcx
    pop rbx
    pop rax
    iretq

    .macro peer name, limit, identity, terminal
    .global poole_peer_\name
poole_peer_\name:
    sub rsp, 32
    mov r14, \identity
    mov r13, \limit
    mov rbx, r14
    mov rbp, r14
    mov r8, r14
    mov r9, r14
    mov r10, r14
    mov r11, r14
    mov r12, r14
    movq xmm0, r14
    movq xmm15, r14
    mov qword ptr [rsp], r14
    fld1
1:  inc r15
    cmp r15, r13
    jb 1b
    cmp rbx, r14
    jne 9f
    cmp rbp, r14
    jne 9f
    cmp r8, r14
    jne 9f
    cmp r9, r14
    jne 9f
    cmp r10, r14
    jne 9f
    cmp r11, r14
    jne 9f
    cmp r12, r14
    jne 9f
    cmp qword ptr [rsp], r14
    jne 9f
    movq rax, xmm0
    cmp rax, r14
    jne 9f
    movq rax, xmm15
    cmp rax, r14
    jne 9f
    fstp qword ptr [rsp + 8]
    movabs rax, 0x3ff0000000000000
    cmp qword ptr [rsp + 8], rax
    jne 9f
    .if \terminal == 2
    mov r12d, 66
8:  xor eax, eax
    mov edi, 1
    xor esi, esi
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    syscall
    dec r12d
    jnz 8b
    .elseif \terminal == 1
    ud2
    .elseif \terminal >= 3
    xor eax, eax
    mov edi, 1
    xor esi, esi
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    .if \terminal == 3
    movabs rsp, 0xffffffff80000000
    syscall
    .elseif \terminal == 4
    movabs rsp, 0x800000000000
    syscall
    .elseif \terminal == 5
    pushfq
    or qword ptr [rsp], 0x4000
    popfq
    syscall
    .elseif \terminal == 6
    pushfq
    or qword ptr [rsp], 0x40000
    popfq
    syscall
    .elseif \terminal == 7
    jmp 8f
    .elseif \terminal == 8
    pushfq
    or qword ptr [rsp], 0x40000
    popfq
    movabs rsp, 0xffffffff80000000
8:  pause
    jmp 8b
    .elseif \terminal == 9
    mov eax, 1
    xor ecx, ecx
    div rcx
    .elseif \terminal == 10
    pushfq
    or qword ptr [rsp], 0x100
    popfq
    nop
    .elseif \terminal == 11
    int3
    .elseif \terminal == 12
    movabs rsp, 0x800000000000
    mov rax, qword ptr [rsp]
    .endif
    ud2
    .else
    mov eax, 2
    mov edi, 1
    mov esi, \identity
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    syscall
    .endif
9:  mov eax, 2
    mov edi, 1
    mov esi, 255
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    syscall
    ud2
    .if \terminal == 7
    .fill 4078 - (. - poole_peer_\name), 1, 0x90
8:  syscall
    .endif
    .global poole_peer_\name\()_end
poole_peer_\name\()_end:
    .endm
    peer exit, 8000000, 42, 0
    peer fault, 8000000, 43, 1
    peer spin, -1, 44, 0
    peer survivor, 20000000, 84, 0
    peer limit, 8000000, 45, 2
    peer bad_stack, 8000000, 46, 3
    peer noncanonical_stack, 8000000, 47, 4
    peer nt, 8000000, 48, 5
    peer ac, 8000000, 49, 6
    peer last_syscall, 8000000, 50, 7
    peer timer_stack, 8000000, 51, 8
    peer divide, 8000000, 52, 9
    peer debug, 8000000, 53, 10
    peer breakpoint, 8000000, 54, 11
    peer stack_fault, 8000000, 55, 12
"#
);
