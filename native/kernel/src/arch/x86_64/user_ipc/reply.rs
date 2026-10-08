use poolekernel::user_entry::privilege::Error;

unsafe extern "C" {
    static poole_reply_client: u8;
    static poole_reply_client_end: u8;
    static poole_reply_server: u8;
    static poole_reply_server_end: u8;
}
pub(crate) fn payload(server: bool) -> Result<&'static [u8], Error> {
    let (start, end) = if server {
        (
            &raw const poole_reply_server,
            &raw const poole_reply_server_end,
        )
    } else {
        (
            &raw const poole_reply_client,
            &raw const poole_reply_client_end,
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
    .section .text.poole_reply_payload,"ax",@progbits
    .global poole_reply_client
poole_reply_client:
    sub rsp, 96
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    lea r12, [r13 + 1]
    mov edi, 1
    mov r14, 0x504F4F4C45525043
    mov qword ptr [rsp], r14
    mov rsi, r12
    mov r8, r12
    mov rdx, rsp
    mov r10d, 8
    mov eax, 6
    syscall
    cmp eax, 5
    jne 9f
    mov r8, r13
    mov rdx, rsp
    mov eax, 6
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    mov rdx, rsp
    mov eax, 6
    syscall
    test eax, eax
    jne 9f
    xor r8d, r8d
    mov rsi, r13
    xor edx, edx
    xor r10d, r10d
    mov eax, 5
    syscall
    test eax, eax
    jne 9f
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    cmp edx, 40
    jne 9f
    cmp qword ptr [rsp], 3
    jne 9f
    cmp qword ptr [rsp + 8], 6
    jne 9f
    cmp qword ptr [rsp + 16], 0
    jne 9f
    cmp qword ptr [rsp + 24], 8
    jne 9f
    xor r14, 0x13579bdf
    cmp qword ptr [rsp + 32], r14
    jne 9f
    mov rsi, 0x200020001
    mov rdx, rsp
    mov r10d, 8
    mov eax, 8
    syscall
    cmp eax, 5
    jne 9f
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    cmp eax, 6
    jne 9f
    mov esi, 95
    xor edx, edx
    xor r10d, r10d
    mov eax, 2
    syscall
9:  ud2
    .global poole_reply_client_end
poole_reply_client_end:
    .global poole_reply_server
poole_reply_server:
    sub rsp, 96
    mov r13, rdi
    shl r13, 32
    or r13, 0x10001
    mov edi, 1
    mov rsi, r13
    lea rdx, [rsp + 88]
    mov r10d, 96
    mov eax, 7
    syscall
    cmp eax, 4
    jne 9f
    cmp edx, 8
    jne 9f
    cmp qword ptr [rsp + 88], 2
    jne 9f
    mov rsi, 0x100020001
    mov rdx, rsp
    mov r10d, 8
    mov eax, 8
    syscall
    cmp eax, 5
    jne 9f
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    cmp edx, 40
    jne 9f
    cmp qword ptr [rsp], 2
    jne 9f
    cmp qword ptr [rsp + 8], 6
    jne 9f
    mov r12, 0x100020001
    cmp qword ptr [rsp + 16], r12
    jne 9f
    cmp qword ptr [rsp + 24], 8
    jne 9f
    mov r14, 0x504F4F4C45525043
    cmp qword ptr [rsp + 32], r14
    jne 9f
    xor qword ptr [rsp + 32], 0x13579bdf
    mov rsi, r12
    lea rdx, [rsp + 32]
    mov r10d, 8
    mov eax, 3
    syscall
    cmp eax, 5
    jne 9f
    lea rdx, [rsp + 96]
    mov eax, 8
    syscall
    cmp eax, 4
    jne 9f
    lea rdx, [rsp + 32]
    mov eax, 8
    syscall
    test eax, eax
    jne 9f
    cmp edx, 8
    jne 9f
    lea rdx, [rsp + 32]
    mov eax, 8
    syscall
    cmp eax, 5
    jne 9f
    mov rsi, r13
    mov rdx, rsp
    mov r10d, 96
    mov eax, 7
    syscall
    test eax, eax
    jne 9f
    mov r12, 0x200020001
    cmp qword ptr [rsp + 16], r12
    jne 9f
    mov rsi, r12
    xor edx, edx
    xor r10d, r10d
    mov eax, 9
    syscall
    test eax, eax
    jne 9f
    mov eax, 9
    syscall
    cmp eax, 5
    jne 9f
    mov esi, 94
    mov eax, 2
    syscall
9:  ud2
    .global poole_reply_server_end
poole_reply_server_end:
"#
);
