#![no_std]
#![no_main]
use poole_userspace::{
    apps::Kind,
    files::probe::{EXIT_COMPLETE, Probe, Progress},
    process, startup,
};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the development launcher owns the live PSTART1 stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(211));
    let boot =
        startup::application(block, version, Kind::Text).unwrap_or_else(|_| process::exit(211));
    let mut probe = Probe::new(boot.files, boot.file_peer, process::ConsoleCalls);
    loop {
        match probe.poll() {
            Ok(Progress::Pending) => {}
            Ok(Progress::AbandonOutstandingRequest) => process::exit(EXIT_COMPLETE),
            Err(_) => process::exit(212),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(213)
}
