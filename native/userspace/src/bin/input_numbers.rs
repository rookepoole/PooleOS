#![no_std]
#![no_main]
use poole_userspace::{apps::Kind, desktop::publisher::interactive::Interactive, process};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    unsafe {
        process::windows::application_view::<Interactive>(address, bytes, version, Kind::Numbers)
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(204)
}
