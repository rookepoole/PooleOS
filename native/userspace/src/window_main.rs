use poole_userspace::{console, console_ipc::Server, process};
pub extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    run::<false>(address, bytes, version)
}
#[inline(always)]
pub fn run<const LIFETIME: bool>(address: u64, bytes: u64, version: u64) -> ! {
    let (mut port, mut channel, endpoint) =
        unsafe { process::windows::boot(address, bytes, version) }
            .unwrap_or_else(|_| process::exit(150));
    console::configure(&mut port).unwrap_or_else(|_| process::exit(151));
    let mut terminal = core::mem::MaybeUninit::<[u8; 1920]>::uninit();
    let mut surfaces = core::mem::MaybeUninit::<[u8; 384]>::uninit();
    let mut keys = core::mem::MaybeUninit::<[u8; 64]>::uninit();
    // Every byte is initialized in place before either reference is created.
    let (cells, app_cells, key_cells) = unsafe {
        for i in 0..1920 {
            terminal
                .as_mut_ptr()
                .cast::<u8>()
                .add(i)
                .write_volatile(b' ');
        }
        for i in 0..384 {
            surfaces
                .as_mut_ptr()
                .cast::<u8>()
                .add(i)
                .write_volatile(b' ');
        }
        for i in 0..64 {
            keys.as_mut_ptr().cast::<u8>().add(i).write_volatile(0);
        }
        (
            terminal.assume_init_mut(),
            surfaces.assume_init_mut(),
            keys.assume_init_mut(),
        )
    };
    let mut local =
        process::windows::Local::<LIFETIME>::new(port, endpoint, cells, app_cells, key_cells);
    local.start().unwrap_or_else(|_| process::exit(154));
    let mut server = Server::new();
    loop {
        local.poll().unwrap_or_else(|_| process::exit(157));
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
