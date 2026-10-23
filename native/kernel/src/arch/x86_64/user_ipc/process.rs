//! Relocation-free CPL3 qualification programs, not the future supervisor.
use super::*;
unsafe extern "C" {
    static poole_process_controller: u8;
    static poole_process_controller_end: u8;
    static poole_process_waiter: u8;
    static poole_process_waiter_end: u8;
}
pub fn payload(waiter: bool) -> Result<&'static [u8], Error> {
    let (s, e) = if waiter {
        (
            &raw const poole_process_waiter,
            &raw const poole_process_waiter_end,
        )
    } else {
        (
            &raw const poole_process_controller,
            &raw const poole_process_controller_end,
        )
    };
    let n = (e as usize).checked_sub(s as usize).ok_or(Error::Layout)?;
    if n == 0 || n > 4080 {
        return Err(Error::Layout);
    }
    Ok(unsafe { core::slice::from_raw_parts(s, n) })
}

core::arch::global_asm!(
    r#"
    .section .text.poole_process_payload,"ax",@progbits
    .macro process_call number, handle
    mov eax, \number
    mov edi, 1
    mov rsi, \handle
    xor edx, edx
    xor r10d, r10d
    xor r8d, r8d
    xor r9d, r9d
    syscall
    .endm
    .global poole_process_controller
poole_process_controller:
    mov r12, rdi
    mov r13, rsi
    mov r14, r12
    movabs rax, 0x100000000
    xor r14, rax
    process_call 18, r14
    cmp rax, 5
    jne 9f
    test rdx, rdx
    jnz 9f
    process_call 18, r13
    cmp rax, 5
    jne 9f
    test rdx, rdx
    jnz 9f
    process_call 17, r12
    test rax, rax
    jnz 9f
    cmp rdx, 1
    jne 9f
    process_call 18, r12
    cmp rax, 6
    jne 9f
    test rdx, rdx
    jnz 9f
1:  process_call 17, r12
    cmp rax, 9
    je 2f
    test rax, rax
    jnz 9f
    cmp rdx, 1
    jne 9f
    jmp 1b
2:  test rdx, rdx
    jnz 9f
    mov esi, 104
    jmp 8f
9:  mov esi, 255
8:  mov eax, 2
    mov edi, 1
    xor edx, edx
    xor r10d, r10d
    xor r8d, r8d
    xor r9d, r9d
    syscall
    ud2
    .global poole_process_controller_end
poole_process_controller_end:
    .global poole_process_waiter
poole_process_waiter:
    mov r12, rdi
    process_call 5, r12
    ud2
    .global poole_process_waiter_end
poole_process_waiter_end:
    .purgem process_call
"#
);
