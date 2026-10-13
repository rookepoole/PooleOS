#![no_std]
#![no_main]
use poole_userspace::{
    console_ipc::Error,
    process,
    shell::{Commands, Shell, processes::Processes},
};

poole_userspace::entry!(main);

// The diagnostic faults only this user process. It confers no kernel authority.
struct ControlCommands<'a>(&'a mut Processes<process::ProcessCalls>);
impl Commands for ControlCommands<'_> {
    fn help(&self) -> &'static [u8] {
        b"help  version  echo TEXT  exit\r\nstart worker|fault  stop worker|fault  status worker|fault\r\nfault shell\r\n"
    }
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error> {
        if line == b"fault shell" {
            // SAFETY: intentional CPL3 invalid instruction tests owner containment.
            unsafe {
                core::arch::asm!("ud2", options(noreturn));
            }
        }
        self.0.begin(line)
    }
    fn poll(&mut self) -> Result<bool, Error> {
        self.0.poll()
    }
    fn response(&self) -> &[u8] {
        self.0.response()
    }
    fn close_allowed(&self) -> bool {
        self.0.close_allowed()
    }
}

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this entry's argument block.
    let (mut channel, factories) = unsafe { process::control_shell_boot(address, bytes, version) }
        .unwrap_or_else(|_| process::exit(180));
    let mut commands = Processes::unbound(process::ProcessCalls);
    commands
        .bind(factories)
        .unwrap_or_else(|_| process::exit(180));
    let mut shell = Shell::with_commands(ControlCommands(&mut commands));
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
