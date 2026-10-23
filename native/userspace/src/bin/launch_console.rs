#![no_std]
#![no_main]
use poole_userspace::{
    console,
    console_ipc::control::Server,
    desktop::{WINDOW_CELLS, application_input::Queues, launch::Controls},
    process,
};
poole_userspace::entry!(main);

#[inline(never)]
#[unsafe(link_section = ".window_capacity")]
fn capacity_probe(value: u64) -> u64 {
    value.rotate_left(17) ^ 0x504f_4f4c_4557_494e
}

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    let seed = core::hint::black_box(0x0102_0304_0506_0708u64);
    if capacity_probe(seed) != 0x5647_4540_4b47_4b4a {
        process::exit(158);
    }
    let (mut port, mut channel, endpoint) =
        unsafe { process::windows::launch_boot(address, bytes, version) }
            .unwrap_or_else(|_| process::exit(150));
    console::configure(&mut port).unwrap_or_else(|_| process::exit(151));
    let mut terminal = core::mem::MaybeUninit::<[u8; WINDOW_CELLS]>::uninit();
    let mut surfaces = core::mem::MaybeUninit::<[u8; 384]>::uninit();
    let mut keys = core::mem::MaybeUninit::<[u8; 64]>::uninit();
    // Initialize in the retained entry frame; returning whole arrays adds a second stack copy.
    let (cells, app_cells, key_cells) = unsafe {
        for i in 0..WINDOW_CELLS {
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
        process::windows::Local::<true>::new_compact(port, endpoint, cells, app_cells, key_cells);
    let mut controls = Controls::new();
    local
        .start_launch(&controls)
        .unwrap_or_else(|_| process::exit(154));
    let mut input = Queues::new();
    let mut server = Server::new();
    loop {
        local
            .poll_launch(&mut input, &mut controls)
            .unwrap_or_else(|_| process::exit(157));
        if controls
            .advance(&mut server)
            .unwrap_or_else(|_| process::exit(159))
        {
            local
                .launch_status(&controls)
                .unwrap_or_else(|_| process::exit(154));
        }
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
