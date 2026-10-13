#![no_std]
#![no_main]
use poole_userspace::{apps::Kind, process};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this live mapped startup block.
    unsafe { process::application(address, bytes, version, Kind::Numbers) }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(203)
}
