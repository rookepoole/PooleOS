#![no_std]
#![no_main]
use poole_userspace::{console, console_ipc::Server, process};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    let (Some(mut port), mut channel) =
        unsafe { process::console_ipc_boot(address, bytes, version, true) }
            .unwrap_or_else(|_| process::exit(150))
    else {
        process::exit(150)
    };
    console::configure(&mut port).unwrap_or_else(|_| process::exit(151));
    const CELLS: usize = poole_userspace::desktop::MAX_COLUMNS * poole_userspace::desktop::MAX_ROWS;
    let mut storage = core::mem::MaybeUninit::<[u8; CELLS]>::uninit();
    // Initialize in place: the current freestanding image contract has no libc.
    // Every byte is written before creating a reference; storage never moves.
    let cells = unsafe {
        let base = storage.as_mut_ptr().cast::<u8>();
        for i in 0..CELLS {
            base.add(i).write_volatile(b' ');
        }
        storage.assume_init_mut()
    };
    let mut local =
        process::desktop::Local::new(port, cells).unwrap_or_else(|_| process::exit(154));
    let mut server = Server::new();
    loop {
        match server.poll(&mut local, &mut channel) {
            Ok(false) => {}
            Ok(true) => process::exit(0),
            Err(_) => process::exit(155),
        }
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(156)
}
