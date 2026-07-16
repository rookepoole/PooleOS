#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

use core::ffi::c_void;
use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    loop {
        core::hint::spin_loop();
    }
}

#[unsafe(export_name = "efi_main")]
pub extern "efiapi" fn qualification_entry(
    _image_handle: *mut c_void,
    _system_table: *mut c_void,
) -> usize {
    0
}
