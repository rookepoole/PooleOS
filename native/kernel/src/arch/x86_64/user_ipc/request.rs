use poolekernel::user_entry::privilege::Error;

unsafe extern "C" {
    static poole_request_client: u8;
    static poole_request_client_end: u8;
    static poole_request_server: u8;
    static poole_request_server_end: u8;
}
pub(crate) fn payload(server: bool) -> Result<&'static [u8], Error> {
    let (start, end) = if server {
        (
            &raw const poole_request_server,
            &raw const poole_request_server_end,
        )
    } else {
        (
            &raw const poole_request_client,
            &raw const poole_request_client_end,
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
    .section .text.poole_request_payload,"ax",@progbits
    .global poole_request_client
poole_request_client:
    sub rsp, 96
    mov r15, rsi
    mov r13, rdi
    shl r13, 32
    or r13, 0x10002
    mov edi, 1
    mov r14, 0x504F4F4C45525043
    mov qword ptr [rsp], r14
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 8
    mov eax, 10
    syscall
    test eax, eax
    jne 9f
    mov r12, rdx
    mov rsi, r12
    xor edx, edx
    xor r10d, r10d
    mov eax, 12
    syscall
    test eax, eax
    jne 9f
    mov eax, 13
    syscall
    cmp eax, 8
    jne 9f
    mov rdx, rsp
    mov r10d, 96
    mov eax, 11
    syscall
    cmp eax, 8
    jne 9f
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 8
    mov eax, 10
    syscall
    test eax, eax
    jne 9f
    mov r12, rdx
    mov rsi, r12
    xor edx, edx
    xor r10d, r10d
    mov eax, 13
    syscall
    test r15, r15
    je 1f
    mov ebx, 9
    cmp r15, 1
    jne 2f
    mov ebx, 8
2:  cmp eax, ebx
    jne 9f
    mov rdx, rsp
    mov r10d, 96
    mov eax, 11
    syscall
    cmp eax, ebx
    jne 9f
    test edx, edx
    jne 9f
    jmp 3f
1:  test eax, eax
    jne 9f
    lea rdx, [rsp + 88]
    mov r10d, 96
    mov eax, 11
    syscall
    cmp eax, 4
    jne 9f
    cmp edx, 8
    jne 9f
    mov rdx, rsp
    mov eax, 11
    syscall
    test eax, eax
    jne 9f
    cmp edx, 40
    jne 9f
    cmp qword ptr [rsp], 3
    jne 9f
    cmp qword ptr [rsp + 8], 7
    jne 9f
    cmp qword ptr [rsp + 16], 0
    jne 9f
    cmp qword ptr [rsp + 24], 8
    jne 9f
    xor r14, 0x13579bdf
    cmp qword ptr [rsp + 32], r14
    jne 9f
3:  mov rdx, rsp
    mov r10d, 96
    mov eax, 11
    syscall
    cmp eax, 5
    jne 9f
    xor esi, esi
    xor edx, edx
    xor r10d, r10d
    xor eax, eax
    syscall
    test eax, eax
    jne 9f
    mov esi, 97
    xor edx, edx
    mov eax, 2
    syscall
9:  ud2
    .global poole_request_client_end
poole_request_client_end:
    .global poole_request_server
poole_request_server:
    cmp rsi, 2
    je 8f
    sub rsp, 96
    mov r15, rsi
    mov r14, rdi
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    mov edi, 1
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    cmp qword ptr [rsp + 16], 0
    jne 9f
    mov rdx, rsp
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    cmp qword ptr [rsp], 2
    jne 9f
    cmp qword ptr [rsp + 8], r14
    jne 9f
    mov r12, qword ptr [rsp + 16]
    test r12, r12
    je 9f
    cmp qword ptr [rsp + 24], 8
    jne 9f
    cmp r15, 3
    je 8f
    mov rsi, r12
    test r15, r15
    jne 1f
    mov r14, 0x504F4F4C45525043
    cmp qword ptr [rsp + 32], r14
    jne 9f
    xor qword ptr [rsp + 32], 0x13579bdf
    lea rdx, [rsp + 32]
    mov r10d, 8
    mov eax, 8
    syscall
    test eax, eax
    jne 9f
    lea rdx, [rsp + 32]
    mov eax, 8
    syscall
    cmp eax, 5
    jne 9f
    jmp 2f
1:  xor edx, edx
    xor r10d, r10d
    mov eax, 9
    syscall
    test eax, eax
    jne 9f
    mov eax, 9
    syscall
    cmp eax, 5
    jne 9f
2:  mov esi, 96
    xor edx, edx
    xor r10d, r10d
    mov eax, 2
    syscall
8:  int3
9:  ud2
    .global poole_request_server_end
poole_request_server_end:
"#
);
