#![no_std]
#![no_main]
//! Opt-in session shell selected only by explicit native launch profiles.
use poole_userspace::{
    console_ipc::Error,
    files::rpc::Client as FileClient,
    process,
    session_control::rpc::Connection,
    shell::{
        applications::{ApplicationCommands, Jobs},
        control::Client,
        files::Files,
        processes::ApplicationProcesses,
    },
    startup,
};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the native launcher owns the live PSTART1 stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(204));
    let boot = startup::launch_shell(block, version).unwrap_or_else(|_| process::exit(204));
    let mut channel = Connection::new(
        boot.console.send,
        boot.console.peer,
        false,
        process::ConsoleCalls,
    );
    let mut processes = ApplicationProcesses::unbound(process::ProcessCalls);
    processes
        .bind(boot.factories)
        .unwrap_or_else(|_| process::exit(204));
    let mut files = Files::new(FileClient::new(
        boot.endpoint,
        boot.peer,
        process::ConsoleCalls,
    ));
    let mut jobs = Jobs::new(boot.console.receive, process::ConsoleCalls);
    let mut shell = Client::new(ApplicationCommands::new(
        &mut files,
        &mut processes,
        &mut jobs,
    ));
    loop {
        match shell.poll(&mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(Error::Revoked) => process::exit(205),
            Err(_) => process::exit(206),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(207)
}
