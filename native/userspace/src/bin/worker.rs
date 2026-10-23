#![no_std]
#![no_main]
use poole_userspace::{process, supervisor::Calls};

poole_userspace::entry!(main);

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this entry's argument block.
    let fault = unsafe { process::diagnostic_boot(address, bytes, version) }
        .unwrap_or_else(|_| process::exit(190));
    if fault {
        // The diagnostic must trap at CPL3, not report a simulated fault by Exit.
        unsafe {
            core::arch::asm!("ud2", options(noreturn));
        }
    }
    loop {
        if process::ProcessCalls.invoke(0, 0, 0) != (0, 1) {
            process::exit(191);
        }
    }
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(192)
}
