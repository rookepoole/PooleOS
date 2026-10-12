#![no_std]
#![no_main]
use poole_userspace::{process, supervisor::Supervisor};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this live argument block.
    let (factory, limit) = unsafe { process::supervisor_boot(address, bytes, version) }
        .unwrap_or_else(|_| process::exit(169));
    let mut state = Supervisor::new(factory, limit).unwrap_or_else(|_| process::exit(169));
    loop {
        match state.step(&mut process::ProcessCalls) {
            Ok(true) => process::exit(0),
            Ok(false) => {}
            Err(_) => process::exit(170),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(171)
}
