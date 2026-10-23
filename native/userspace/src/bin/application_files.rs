#![no_std]
#![no_main]
use poole_userspace::{files::rpc::ApplicationServer, process, startup};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the native launcher owns the live PSTART1 stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(208));
    let (endpoint, peers) =
        startup::application_file_server(block, version).unwrap_or_else(|_| process::exit(208));
    let mut server = ApplicationServer::new(endpoint, peers, process::ConsoleCalls);
    loop {
        if server.poll().is_err() {
            process::exit(209);
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(210)
}
