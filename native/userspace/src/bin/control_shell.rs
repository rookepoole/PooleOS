#![no_std]
#![no_main]
use poole_userspace::{
    console_ipc::Error,
    process,
    shell::{Shell, processes::Processes},
};

poole_userspace::entry!(main);

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this entry's argument block.
    let (mut channel, factories) = unsafe { process::control_shell_boot(address, bytes, version) }
        .unwrap_or_else(|_| process::exit(180));
    let mut commands = Processes::unbound(process::ProcessCalls);
    commands
        .bind(factories)
        .unwrap_or_else(|_| process::exit(180));
    let mut shell = Shell::with_commands(&mut commands);
    loop {
        match shell.poll(&mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(Error::Revoked) => process::exit(183),
            Err(_) => process::exit(181),
        }
    }
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(182)
}
