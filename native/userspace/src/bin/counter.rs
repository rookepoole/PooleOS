#![no_std]
#![no_main]
use poole_userspace::{process, protocol::Counter, service, startup::Role};

poole_userspace::entry!(main);

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the entry shim is invoked only by the owned PSTART1 kernel launcher.
    let boot = unsafe { process::boot(address, bytes, version, Role::Counter) }
        .unwrap_or_else(|_| process::exit(120));
    let mut channel = process::Ipc::new(boot);
    let mut state = Counter::new();
    loop {
        if service::counter_step(&mut state, &mut channel).is_err() {
            process::exit(121);
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(122)
}
