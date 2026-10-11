#![no_std]
#![no_main]
use poole_userspace::{
    console::{self, Echo},
    process,
};

poole_userspace::entry!(main);

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: invoked by the owned PSTART1 entry shim with a mapped argument block.
    let mut port = unsafe { process::console_boot(address, bytes, version) }
        .unwrap_or_else(|_| process::exit(130));
    console::configure(&mut port).unwrap_or_else(|_| process::exit(131));
    for &byte in b"PooleConsole ready\r\n" {
        while !console::send(&mut port, byte).unwrap_or_else(|_| process::exit(132)) {}
    }
    let mut echo = Echo::new();
    loop {
        match echo.poll(&mut port) {
            Ok(true) => process::exit(0),
            Ok(false) => {}
            Err(_) => process::exit(133),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(134)
}
