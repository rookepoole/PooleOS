#![no_std]
#![no_main]
use poole_userspace::{
    process,
    supervisor::{Completion, Supervisor},
};

// Each jump must fetch instructions from a different owned executable page.
core::arch::global_asm!(
    ".section .text.start,\"ax\",@progbits",
    ".global _start",
    "_start:",
    "xor ebp, ebp",
    "mov ecx, 1",
    "jmp 2f",
    ".balign 4096, 0x90",
    "2: inc ecx",
    "jmp 3f",
    ".balign 4096, 0x90",
    "3: inc ecx",
    "jmp 4f",
    ".balign 4096, 0x90",
    "4: inc ecx",
    "call {main}",
    "ud2",
    main = sym main,
);

extern "C" fn main(address: u64, bytes: u64, version: u64, pages: u64) -> ! {
    if pages != 4 {
        process::exit(173);
    }
    // SAFETY: the owned PSTART1 launcher supplies this live argument block.
    let (factory, limit) = unsafe { process::supervisor_boot(address, bytes, version) }
        .unwrap_or_else(|_| process::exit(169));
    let mut state = Supervisor::new(factory, limit).unwrap_or_else(|_| process::exit(169));
    loop {
        match state.step(&mut process::ProcessCalls) {
            Ok(true) => process::exit(if state.last_completion() == Some(Completion::Exit(100)) {
                0
            } else {
                172
            }),
            Ok(false) => {}
            Err(_) => process::exit(170),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(171)
}
