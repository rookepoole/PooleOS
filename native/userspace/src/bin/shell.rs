#![no_std]
#![no_main]
use poole_userspace::{console_ipc::Error, process, shell::Shell};

poole_userspace::entry!(main);

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this entry's argument block.
    let (_, mut channel) = unsafe { process::console_ipc_boot(address, bytes, version, false) }
        .unwrap_or_else(|_| process::exit(160));
    let mut shell = Shell::new();
    loop {
        match shell.poll(&mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(Error::Revoked) => process::exit(163),
            Err(_) => process::exit(161),
        }
    }
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(162)
}
