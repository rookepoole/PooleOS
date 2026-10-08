//! Sole-BSP IPC owner. Copy faults may borrow COPY, never this suspended owner.
use poolekernel::{
    capability_ipc::{Caller, Rights, Space},
    scheduler_smp::TaskId,
    user_entry::{
        ImageAdmission,
        privilege::Error,
        syscall::{Memory, Status},
    },
};

static mut IPC: Space = Space::new();
/// SAFETY: the clock adapter authenticates the exclusive BSP/root/IF0 before
/// borrowing this owner, including during a suspended authenticated syscall.
pub unsafe fn with_clock<T>(
    f: impl FnOnce(&mut Space) -> Result<T, poolekernel::user_entry::timer::Error>,
) -> Result<T, poolekernel::user_entry::timer::Error> {
    f(unsafe { &mut *(&raw mut IPC) })
}
mod pressure;
pub(super) use pressure::payload as pressure_payload;
mod reply;
pub(super) use reply::payload as reply_payload;
mod request;
pub(super) use request::payload as request_payload;
mod deadline;
pub(super) use deadline::payload as deadline_payload;

fn idle() -> Result<(), Error> {
    if super::user::active() || super::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0 {
        Err(Error::State)
    } else {
        Ok(())
    }
}

/// SAFETY: exclusive BSP, no running task or concurrent reference to this owner.
pub unsafe fn bootstrap(
    tasks: [(TaskId, ImageAdmission); 2],
    scheduler: &mut poolekernel::scheduler::Scheduler,
) -> Result<[u64; 4], Error> {
    use poolekernel::capability_ipc::admission::{Member, Step};
    idle()?;
    let s = unsafe { &mut *(&raw mut IPC) };
    if !s.is_empty() {
        return Err(Error::State);
    }
    let members = tasks.map(|(id, image)| Member {
        id,
        image,
        priority: 16,
    });
    let plan = [
        Step::Endpoint { member: 0 },
        Step::Endpoint { member: 1 },
        Step::Grant {
            endpoint: 1,
            target: tasks[0].0,
            rights: Rights::SEND,
        },
        Step::Grant {
            endpoint: 0,
            target: tasks[1].0,
            rights: Rights::SEND,
        },
    ];
    let result = s
        .admit(scheduler, &members, &plan)
        .map_err(|_| Error::State)?;
    Ok(result.handles[..4].try_into().map_err(|_| Error::State)?)
}

/// SAFETY: exclusive BSP and stopped task; detach before freeing its image.
pub unsafe fn detach(id: TaskId) -> Result<(), Error> {
    idle()?;
    unsafe { &mut *(&raw mut IPC) }
        .detach_if_attached(id)
        .map_err(|_| Error::State)
}

pub(super) fn prepare_wait(
    caller: Caller,
    handle: u64,
    readiness: poolekernel::capability_ipc::wait::Readiness,
) -> Result<poolekernel::capability_ipc::wait::Admission, Status> {
    unsafe { &mut *(&raw mut IPC) }.prepare_wait(caller, handle, readiness)
}

pub(super) fn prepare_request_wait(
    caller: Caller,
    handle: u64,
) -> Result<poolekernel::capability_ipc::wait::Admission, Status> {
    unsafe { &mut *(&raw mut IPC) }.prepare_request_wait(caller, handle)
}
pub(super) fn request_operation(
    caller: Caller,
    handle: u64,
    address: u64,
    bytes: usize,
    operation: poolekernel::capability_ipc::request::Operation,
    memory: &mut impl Memory,
) -> (Status, u64) {
    unsafe { &mut *(&raw mut IPC) }
        .request_operation(caller, handle, address, bytes, operation, memory)
}

/// SAFETY: exclusive BSP with both tasks quiescent on the original kernel root.
pub unsafe fn with_waits<T>(
    f: impl FnOnce(&mut Space) -> Result<T, poolekernel::capability_ipc::Error>,
) -> Result<T, Error> {
    idle()?;
    f(unsafe { &mut *(&raw mut IPC) }).map_err(|_| Error::State)
}

/// SAFETY: same exclusive owner boundary as bootstrap.
pub unsafe fn empty() -> Result<bool, Error> {
    idle()?;
    Ok(unsafe { &*(&raw const IPC) }.is_empty())
}

pub(super) fn transfer(
    caller: Caller,
    handle: u64,
    address: u64,
    bytes: usize,
    send: bool,
    memory: &mut impl Memory,
) -> (Status, u64) {
    // The trap adapter authenticates root, CPL3, depth, IF0 and saved Run identity.
    unsafe { &mut *(&raw mut IPC) }.transfer(caller, handle, address, bytes, send, memory)
}

pub(super) fn message(
    caller: Caller,
    handle: u64,
    address: u64,
    bytes: usize,
    operation: poolekernel::capability_ipc::reply::Operation,
    memory: &mut impl Memory,
) -> (Status, u64) {
    unsafe { &mut *(&raw mut IPC) }.message(caller, handle, address, bytes, operation, memory)
}

unsafe extern "C" {
    static poole_ipc_client: u8;
    static poole_ipc_client_end: u8;
    static poole_ipc_server: u8;
    static poole_ipc_server_end: u8;
}
pub(super) fn payload(server: bool) -> Result<&'static [u8], Error> {
    let (start, end) = if server {
        (&raw const poole_ipc_server, &raw const poole_ipc_server_end)
    } else {
        (&raw const poole_ipc_client, &raw const poole_ipc_client_end)
    };
    let n = (end as usize)
        .checked_sub(start as usize)
        .ok_or(Error::Layout)?;
    if n == 0 || n > 4080 {
        return Err(Error::Layout);
    }
    Ok(unsafe { core::slice::from_raw_parts(start, n) })
}

// Relocation-free test payloads use only their two granted bootstrap handles.
// The server reads, transforms and returns actual bytes from the client's message.
core::arch::global_asm!(
    r#"
    .section .text.poole_ipc_payload,"ax",@progbits
    .global poole_ipc_client
poole_ipc_client:
    sub rsp, 16
    mov r12, 0x0000000100010002
    mov r13, 0x0000000100010001
    mov r14, 0x504F4F4C45495043
    mov qword ptr [rsp], r14
    mov edi, 1
    mov r15, 0x12563478
    movq xmm15, r15
    mov rsi, r13
    xor edx, edx
    xor r10d, r10d
    mov eax, 5
    syscall
    cmp eax, 8
    jne 9f
    test edx, edx
    jne 9f
    cmp r15, 0x12563478
    jne 9f
    movq rax, xmm15
    cmp rax, r15
    jne 9f
    mov esi, 0
    mov rdx, rsp
    mov r10d, 8
    mov eax, 3
    syscall
    cmp eax, 5
    jne 9f
    mov rsi, r12
    mov rdx, rsp
    mov eax, 4
    syscall
    cmp eax, 5
    jne 9f
    mov rdx, rsp
    mov r10d, 65
    mov eax, 3
    syscall
    cmp eax, 3
    jne 9f
    mov r10d, 8
    lea rdx, [rip + poole_ipc_client]
    and rdx, -4096
    add rdx, 4096
    mov eax, 3
    syscall
    cmp eax, 4
    jne 9f
    mov rdx, rsp
    mov eax, 3
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    mov eax, 5
    mov rsi, r13
    xor edx, edx
    xor r10d, r10d
    syscall
    test eax, eax
    jne 9f
    test edx, edx
    jne 9f
    cmp r15, 0x12563478
    jne 9f
    movq rax, xmm15
    cmp rax, r15
    jne 9f
    mov eax, 4
    mov r10d, 8
    mov rdx, rsp
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    xor r14, 0x13579BDF
    cmp qword ptr [rsp], r14
    jne 9f
    mov eax, 2
    mov esi, 91
    xor edx, edx
    xor r10d, r10d
    syscall
9:  ud2
    .global poole_ipc_client_end
poole_ipc_client_end:
    .global poole_ipc_server
poole_ipc_server:
    sub rsp, 16
    mov r12, 0x0000000100010002
    mov r13, 0x0000000100010001
    mov edi, 1
    mov eax, 5
    mov rsi, r13
    xor edx, edx
    xor r10d, r10d
    syscall
    test eax, eax
    jne 9f
    test edx, edx
    jne 9f
    mov r10d, 8
    mov eax, 4
    mov rsi, r13
    mov rdx, rsp
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    mov r14, 0x504F4F4C45495043
    cmp qword ptr [rsp], r14
    jne 9f
    xor qword ptr [rsp], 0x13579BDF
    mov eax, 3
    mov rsi, r12
    mov rdx, rsp
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    mov eax, 2
    mov esi, 90
    xor edx, edx
    xor r10d, r10d
    syscall
9:  ud2
    .global poole_ipc_server_end
poole_ipc_server_end:
"#
);
