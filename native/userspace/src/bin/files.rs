#![no_std]
#![no_main]
use poole_userspace::{files::rpc::Server, process, startup};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this live startup stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(190));
    let (endpoint, peers) =
        startup::file_server(block, version).unwrap_or_else(|_| process::exit(190));
    let mut server = Server::new(endpoint, peers, process::ConsoleCalls);
    loop {
        server.poll().unwrap_or_else(|_| process::exit(191));
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(192)
}
