//! Architectural termination adapter; general scheduling remains separate.
use super::*;
use poolekernel::scheduler_smp::TaskId;

impl task::Driver for Entry {
    fn revoke(&mut self, id: TaskId) -> Result<(), Error> {
        unsafe { super::super::user_ipc::detach(id) }
    }
    fn execute(&mut self, image: ImageAdmission, id: TaskId) -> Result<task::Outcome, Error> {
        self.context(image.root_physical)?;
        if self.installed
            || self.budget.is_some()
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
        let task = task::Run::new(image, id)?;
        self.installed = true;
        // Possible architectural effects are now owned by the task's quarantine.
        unsafe {
            install()?;
            initialize_fx()?;
            super::super::user_syscall::prepare(image)?;
            write_volatile(&raw mut TASK, Some(task));
        }
        ACTIVE_ROOT.store(image.root_physical, Ordering::Release);
        RETURN_STACK_TOP.store(self.original_rsp0, Ordering::Release);
        super::super::user_syscall::enable()?;
        // SAFETY: exclusive admitted image/private entry stack and initialized state.
        unsafe {
            poole_user_enter(&image.initial_frame);
        }
        self.context(image.root_physical)?;
        unsafe { (&*(&raw const TASK)).as_ref() }
            .and_then(task::Run::outcome)
            .ok_or(Error::State)
    }
    fn quiesce(&mut self, root: u64) -> Result<(), Error> {
        privilege::Driver::quiesce(self, root)
    }
}

pub(super) fn dispatch(t: &Trap, frame: &mut TrapFrame) {
    let task =
        unsafe { (&mut *(&raw mut TASK)).as_mut() }.unwrap_or_else(|| denied(8, Error::State, t));
    if t.vector == syscall::VECTOR {
        if task.call(t).unwrap_or_else(|e| denied(8, e, t)) {
            let code =
                super::super::user_syscall::dispatch(t, frame).unwrap_or_else(|e| denied(8, e, t));
            let Some(code) = code else {
                return;
            };
            task.exit(code).unwrap_or_else(|e| denied(8, e, t));
        }
    } else {
        task.fault(t).unwrap_or_else(|e| denied(9, e, t));
        acknowledge_user_fault(t).unwrap_or_else(|e| denied(9, e, t));
    }
    // Never IRET to the stopped user frame, even when RIP/RSP themselves are bad.
    super::super::user_syscall::disable(t.root).unwrap_or_else(|e| denied(10, e, t));
    return_kernel(frame);
}

unsafe extern "C" {
    static poole_task_exit: u8;
    static poole_task_exit_end: u8;
    static poole_task_ud: u8;
    static poole_task_ud_end: u8;
    static poole_task_gp: u8;
    static poole_task_gp_end: u8;
    static poole_task_pf: u8;
    static poole_task_pf_end: u8;
}
pub fn payload(index: usize) -> Result<&'static [u8], Error> {
    let (start, end) = match index {
        0 => (&raw const poole_task_exit, &raw const poole_task_exit_end),
        1 => (&raw const poole_task_ud, &raw const poole_task_ud_end),
        2 => (&raw const poole_task_gp, &raw const poole_task_gp_end),
        3 => (&raw const poole_task_pf, &raw const poole_task_pf_end),
        _ => return Err(Error::Layout),
    };
    let size = (end as usize)
        .checked_sub(start as usize)
        .ok_or(Error::Layout)?;
    if size == 0 || size > 4080 {
        return Err(Error::Layout);
    }
    // SAFETY: exact bounds of immutable relocation-free linked payloads.
    Ok(unsafe { core::slice::from_raw_parts(start, size) })
}

core::arch::global_asm!(
    r#"
    .section .text.poole_task_payload,"ax",@progbits
    .global poole_task_exit
poole_task_exit:
    mov edi, 1
    syscall
    test rax, rax
    jnz 2f
    cmp rdx, 1
    jne 2f
    mov eax, 2
    mov esi, 42
    xor edx, edx
    syscall
2:  ud2
    .global poole_task_exit_end
poole_task_exit_end:
    .global poole_task_ud
poole_task_ud:
    ud2
    .global poole_task_ud_end
poole_task_ud_end:
    .global poole_task_gp
poole_task_gp:
    cli
    ud2
    .global poole_task_gp_end
poole_task_gp_end:
    .global poole_task_pf
poole_task_pf:
    movabs rax, 0xffffffff80000000
    mov rax, qword ptr [rax]
    ud2
    .global poole_task_pf_end
poole_task_pf_end:
"#
);
