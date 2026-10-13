#![no_std]
#![no_main]
use poole_userspace::{apps::Kind, files::claimed, process, startup, supervisor::Calls};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the diagnostic launcher owns the live PSTART1 stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(214));
    let boot =
        startup::application(block, version, Kind::Text).unwrap_or_else(|_| process::exit(214));
    for _ in 0..16384 {
        match claimed::begin(boot.files, &mut process::ConsoleCalls) {
            Ok(Some(token)) => {
                process::ProcessCalls.invoke(13, token, 0);
                // This diagnostic must be cancelled while blocked, never resumed.
                process::exit(215);
            }
            Ok(None) => {}
            Err(_) => process::exit(216),
        }
    }
    process::exit(217)
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(218)
}
