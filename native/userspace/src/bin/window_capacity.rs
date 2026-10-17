#![no_std]
#![no_main]
#[path = "../window_main.rs"]
mod window_main;
poole_userspace::entry!(main);

// The PWCODE1 linker places this real call on the seventh RX page. Startup
// cannot reach the ordinary window service unless that page executes correctly.
#[inline(never)]
#[unsafe(link_section = ".window_capacity")]
fn capacity_probe(value: u64) -> u64 {
    value.rotate_left(17) ^ 0x504f_4f4c_4557_494e
}

extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    let seed = core::hint::black_box(0x0102_0304_0506_0708u64);
    if capacity_probe(seed) != 0x5647_4540_4b47_4b4a {
        poole_userspace::process::exit(158);
    }
    window_main::main(address, bytes, version)
}
