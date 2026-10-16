#![no_std]
#![no_main]
use poole_userspace::{
    console_ipc::Error,
    files::rpc::Client,
    process,
    shell::{Commands, Shell, files::Files, processes::Processes},
    startup,
};
poole_userspace::entry!(main);
struct FileCommands<'a> {
    files: &'a mut Files<process::ConsoleCalls>,
    processes: &'a mut Processes<process::ProcessCalls>,
    file: bool,
}
impl Commands for FileCommands<'_> {
    fn help(&self) -> &'static [u8] {
        b"help  version  echo TEXT  exit\r\nls  cat /PATH\r\nstart worker|fault  stop worker|fault  status worker|fault\r\nfault shell\r\n"
    }
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error> {
        if line == b"fault shell" {
            // SAFETY: intentional CPL3 invalid instruction, no kernel authority.
            unsafe {
                core::arch::asm!("ud2", options(noreturn));
            }
        }
        self.file = self.files.begin(line)?;
        if self.file {
            Ok(true)
        } else {
            self.processes.begin(line)
        }
    }
    fn poll(&mut self) -> Result<bool, Error> {
        if self.file {
            self.files.poll()
        } else {
            self.processes.poll()
        }
    }
    fn response(&self) -> &[u8] {
        if self.file {
            self.files.response()
        } else {
            self.processes.response()
        }
    }
    fn response_complete(&self) -> bool {
        !self.file || self.files.response_complete()
    }
    fn close_allowed(&self) -> bool {
        self.files.close_allowed() && self.processes.close_allowed()
    }
}
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this live startup stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(197));
    let boot = startup::file_shell(block, version).unwrap_or_else(|_| process::exit(197));
    let mut channel = process::console_client(boot.console);
    let mut processes = Processes::unbound(process::ProcessCalls);
    processes
        .bind(boot.factories)
        .unwrap_or_else(|_| process::exit(197));
    let mut files = Files::new(Client::new(boot.endpoint, boot.peer, process::ConsoleCalls));
    let mut shell = Shell::with_commands(FileCommands {
        files: &mut files,
        processes: &mut processes,
        file: false,
    });
    loop {
        match shell.poll(&mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(Error::Revoked) => process::exit(183),
            Err(_) => process::exit(198),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(199)
}
