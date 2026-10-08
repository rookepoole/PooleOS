//! Relocation-free CPL3 pressure/death programs. Startup words select a generation
//! and case; they confer no authority unless the kernel's table agrees.
use super::Error;

unsafe extern "C" {
    static poole_ipc_pressure_client: u8;
    static poole_ipc_pressure_client_end: u8;
    static poole_ipc_pressure_server: u8;
    static poole_ipc_pressure_server_end: u8;
}
pub(crate) fn payload(server: bool) -> Result<&'static [u8], Error> {
    let (start, end) = if server {
        (
            &raw const poole_ipc_pressure_server,
            &raw const poole_ipc_pressure_server_end,
        )
    } else {
        (
            &raw const poole_ipc_pressure_client,
            &raw const poole_ipc_pressure_client_end,
        )
    };
    let bytes = (end as usize)
        .checked_sub(start as usize)
        .ok_or(Error::Layout)?;
    if bytes == 0 || bytes > 4080 {
        return Err(Error::Layout);
    }
    Ok(unsafe { core::slice::from_raw_parts(start, bytes) })
}

core::arch::global_asm!(
    r#"
    .section .text.poole_ipc_pressure,"ax",@progbits
    .global poole_ipc_pressure_client
poole_ipc_pressure_client:
    sub rsp, 16
    mov rbp, rsi
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    lea r12, [r13 + 1]
    mov r15d, 0x12563478
    movq xmm15, r15
    mov edi, 1
    mov rsi, r12
    mov rax, 0x100000000
    sub rsi, rax
    mov rdx, rsp
    mov r10d, 8
    mov eax, 3
    syscall
    cmp eax, 5
    jne 9f
    test edx, edx
    jne 9f
    mov r14d, 1
1:  mov qword ptr [rsp], r14
    mov rsi, r12
    mov rdx, rsp
    mov eax, 3
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    inc r14
    cmp r14, 5
    jne 1b
    lea rdx, [rip + poole_ipc_pressure_client]
    and rdx, -4096
    add rdx, 4096
    mov eax, 3
    syscall
    cmp eax, 6
    jne 9f
    test edx, edx
    jne 9f
    mov eax, 5
    mov edx, 1
    xor r10d, r10d
    syscall
    test rbp, rbp
    jnz 2f
    test eax, eax
    jne 9f
    test edx, edx
    jne 9f
    mov qword ptr [rsp], r14
    mov eax, 3
    mov rdx, rsp
    mov r10d, 8
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
    jmp 3f
2:  cmp eax, 9
    jne 9f
    test edx, edx
    jne 9f
    mov eax, 3
    mov rdx, rsp
    mov r10d, 8
    syscall
    cmp eax, 5
    jne 9f
    test edx, edx
    jne 9f
    mov eax, 5
    mov edx, 1
    xor r10d, r10d
    syscall
    cmp eax, 5
    jne 9f
    test edx, edx
    jne 9f
    mov qword ptr [rsp], 15
    mov eax, 3
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 8
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
3:  mov eax, 4
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 8
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    cmp qword ptr [rsp], 15
    jne 9f
    mov eax, 4
    mov rdx, rsp
    syscall
    cmp eax, 6
    jne 9f
    test edx, edx
    jne 9f
    cmp r15, 0x12563478
    jne 9f
    movq rax, xmm15
    cmp rax, r15
    jne 9f
    mov eax, 2
    mov esi, 93
    xor edx, edx
    xor r10d, r10d
    syscall
9:  ud2
    .global poole_ipc_pressure_client_end
poole_ipc_pressure_client_end:
    .global poole_ipc_pressure_server
poole_ipc_pressure_server:
    sub rsp, 16
    mov rbp, rsi
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    lea r12, [r13 + 1]
    mov edi, 1
    cmp ebp, 2
    je 7f
    cmp ebp, 3
    je 8f
    test ebp, ebp
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
    mov eax, 4
    mov rdx, rsp
    mov r10d, 4
    syscall
    cmp eax, 7
    jne 9f
    cmp edx, 8
    jne 9f
    mov eax, 4
    lea rdx, [rsp + 12]
    mov r10d, 8
    syscall
    cmp eax, 4
    jne 9f
    cmp edx, 4
    jne 9f
    cmp dword ptr [rsp + 12], 1
    jne 9f
    mov r14d, 1
1:  mov eax, 4
    mov rdx, rsp
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    cmp qword ptr [rsp], r14
    jne 9f
    add rbp, r14
    inc r14
    cmp r14, 5
    jne 1b
    mov eax, 5
    xor edx, edx
    xor r10d, r10d
    syscall
    test eax, eax
    jne 9f
    test edx, edx
    jne 9f
    mov eax, 4
    mov rdx, rsp
    mov r10d, 8
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    cmp qword ptr [rsp], r14
    jne 9f
    add rbp, r14
    mov qword ptr [rsp], rbp
    mov eax, 3
    mov rsi, r12
    mov rdx, rsp
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    mov eax, 2
    mov esi, 92
    xor edx, edx
    xor r10d, r10d
    syscall
7:  inc r15
    jmp 7b
8:  mov eax, 5
    lea rsi, [r13 + 2]
    xor edx, edx
    xor r10d, r10d
    syscall
9:  ud2
    .global poole_ipc_pressure_server_end
poole_ipc_pressure_server_end:
"#
);
