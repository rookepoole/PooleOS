use poolekernel::user_entry::privilege::Error;
unsafe extern "C" {
    static poole_deadline_client: u8;
    static poole_deadline_client_end: u8;
    static poole_deadline_server: u8;
    static poole_deadline_server_end: u8;
}
pub(crate) fn payload(server: bool) -> Result<&'static [u8], Error> {
    let (start, end) = if server {
        (
            &raw const poole_deadline_server,
            &raw const poole_deadline_server_end,
        )
    } else {
        (
            &raw const poole_deadline_client,
            &raw const poole_deadline_client_end,
        )
    };
    let n = (end as usize)
        .checked_sub(start as usize)
        .ok_or(Error::Layout)?;
    if n == 0 || n > 4080 {
        return Err(Error::Layout);
    }
    Ok(unsafe { core::slice::from_raw_parts(start, n) })
}

core::arch::global_asm!(
    r#"
    .section .text.poole_deadline_payload,"ax",@progbits
    .global poole_deadline_client
poole_deadline_client:
    sub rsp, 96
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    lea r12, [rsi + 1]
    shl r12, 32
    or r12, 0x10003
    mov edi, 1
    mov qword ptr [rsp], 0x556677
    lea rsi, [r13 + 1]
    mov rdx, rsp
    mov r10d, 8
    mov r8d, 100000000
    mov eax, 14
    syscall
    test eax, eax
    jne 9f
    mov r14, rdx
    xor r8d, r8d
    mov rsi, r14
    xor edx, edx
    xor r10d, r10d
    mov eax, 13
    syscall
    cmp eax, 10
    jne 9f
    mov eax, 12
    syscall
    cmp eax, 5
    jne 9f
    mov rsi, r12
    mov rdx, rsp
    mov r10d, 8
    mov eax, 3
    syscall
    test eax, eax
    jne 9f
    mov rsi, r13
    xor edx, edx
    xor r10d, r10d
    mov eax, 5
    syscall
    test eax, eax
    jne 9f
    mov rdx, rsp
    mov r10d, 8
    mov eax, 4
    syscall
    test eax, eax
    jne 9f
    cmp qword ptr [rsp], 0x123456
    jne 9f
    mov rsi, r14
    mov rdx, rsp
    mov r10d, 96
    mov eax, 11
    syscall
    cmp eax, 10
    jne 9f
    xor esi, esi
    xor edx, edx
    xor r10d, r10d
    xor eax, eax
    syscall
    test eax, eax
    jne 9f
    mov esi, 98
    xor edx, edx
    mov eax, 2
    syscall
9:  ud2
    .global poole_deadline_client_end
poole_deadline_client_end:
    .global poole_deadline_server
poole_deadline_server:
    sub rsp, 96
    mov rbx, rsi
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    lea r14, [rsi + 6]
    shl r14, 32
    or r14, 0x10002
    lea r15, [r14 + 1]
    mov edi, 1
    test ebx, ebx
    je 1f
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    mov r12, qword ptr [rsp + 16]
    test r12, r12
    je 9f
1:  mov rsi, r14
    xor edx, edx
    xor r10d, r10d
    mov eax, 5
    syscall
    test eax, eax
    jne 9f
    test ebx, ebx
    jne 2f
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    mov r12, qword ptr [rsp + 16]
    test r12, r12
    jne 9f
2:  mov rsi, r12
    mov rdx, rsp
    mov r10d, 8
    mov eax, 8
    syscall
    cmp eax, 5
    jne 9f
    mov qword ptr [rsp], 0x123456
    mov rsi, r15
    mov rdx, rsp
    mov r10d, 8
    mov eax, 3
    syscall
    test eax, eax
    jne 9f
    mov esi, 99
    xor edx, edx
    xor r10d, r10d
    mov eax, 2
    syscall
9:  ud2
    .global poole_deadline_server_end
poole_deadline_server_end:
"#
);
