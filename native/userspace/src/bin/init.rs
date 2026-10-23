#![no_std]
#![no_main]
use poole_userspace::{process, protocol::Init, service, startup::Role};

poole_userspace::entry!(main);

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the entry shim is invoked only by the owned PSTART1 kernel launcher.
    let boot = unsafe { process::boot(address, bytes, version, Role::Init) }
        .unwrap_or_else(|_| process::exit(110));
    let mut channel = process::Ipc::new(boot);
    let mut state = Init::new();
    loop {
        if service::init_step(&mut state, &mut channel).is_err() {
            process::exit(111);
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(112)
}
