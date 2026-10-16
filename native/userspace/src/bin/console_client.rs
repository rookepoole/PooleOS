#![no_std]
#![no_main]
use poole_userspace::{console_ipc::Client, process};

poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: only the owned PSTART1 launcher may invoke this entry shim.
    let (_, mut channel) = unsafe { process::console_ipc_boot(address, bytes, version, false) }
        .unwrap_or_else(|_| process::exit(160));
    let mut client = Client::new();
    loop {
        match client.poll(&mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(poole_userspace::console_ipc::Error::Revoked) => process::exit(163),
            Err(_) => process::exit(161),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(162)
}
