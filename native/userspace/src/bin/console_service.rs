#![no_std]
#![no_main]
use poole_userspace::{console, console_ipc::Server, process};

poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: only the owned PSTART1 launcher may invoke this entry shim.
    let (Some(mut port), mut channel) =
        unsafe { process::console_ipc_boot(address, bytes, version, true) }
            .unwrap_or_else(|_| process::exit(150))
    else {
        process::exit(150);
    };
    console::configure(&mut port).unwrap_or_else(|_| process::exit(151));
    let mut server = Server::new();
    loop {
        match server.poll(&mut port, &mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(_) => process::exit(152),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(153)
}
