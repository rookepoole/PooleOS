#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

mod exit;
mod kload;
mod kmap;
#[allow(dead_code)]
mod livehandoff;

use core::arch::asm;
use core::ffi::c_void;
use core::fmt::{self, Write};
use core::mem::{size_of, transmute_copy};
use core::panic::PanicInfo;
use core::ptr::{null, null_mut, write_volatile};
use core::slice::from_raw_parts;

use pooleboot::{
    ContractError, EFI_BUFFER_TOO_SMALL, FramebufferLayout, identity_rgb, pack_pixel,
    validate_configuration_tables, validate_framebuffer, validate_table_header,
};

type EfiStatus = usize;
type EfiHandle = *mut c_void;

const EFI_SUCCESS: EfiStatus = 0;
const EFI_INVALID_PARAMETER: EfiStatus = pooleboot::EFI_ERROR_BIT | 2;
const EFI_UNSUPPORTED: EfiStatus = pooleboot::EFI_ERROR_BIT | 3;
const EFI_OUT_OF_RESOURCES: EfiStatus = pooleboot::EFI_ERROR_BIT | 9;
const EFI_COMPROMISED_DATA: EfiStatus = pooleboot::EFI_ERROR_BIT | 33;
const EFI_LOADER_DATA: u32 = 2;
const EFI_SYSTEM_TABLE_SIGNATURE: u64 = 0x5453_5953_2049_4249;
const EFI_BOOT_SERVICES_SIGNATURE: u64 = 0x5652_4553_544f_4f42;
const COM1_BASE: u16 = 0x03f8;
const DEBUGCON_PORT: u16 = 0x0402;
const DEBUG_EXIT_PORT: u16 = 0x00f4;

#[repr(C)]
#[derive(Clone, Copy)]
struct EfiTableHeader {
    signature: u64,
    revision: u32,
    header_size: u32,
    crc32: u32,
    reserved: u32,
}

#[repr(C)]
struct EfiSimpleTextOutputProtocol {
    reset: usize,
    output_string: usize,
    test_string: usize,
    query_mode: usize,
    set_mode: usize,
    set_attribute: usize,
    clear_screen: usize,
    set_cursor_position: usize,
    enable_cursor: usize,
    mode: usize,
}

#[repr(C)]
struct EfiSystemTable {
    header: EfiTableHeader,
    firmware_vendor: *const u16,
    firmware_revision: u32,
    console_in_handle: EfiHandle,
    console_in: *mut c_void,
    console_out_handle: EfiHandle,
    console_out: *mut EfiSimpleTextOutputProtocol,
    standard_error_handle: EfiHandle,
    standard_error: *mut EfiSimpleTextOutputProtocol,
    runtime_services: *mut c_void,
    boot_services: *mut EfiBootServices,
    configuration_table_count: usize,
    configuration_tables: *const EfiConfigurationTable,
}

#[repr(C)]
struct EfiBootServices {
    header: EfiTableHeader,
    raise_tpl: usize,
    restore_tpl: usize,
    allocate_pages: usize,
    free_pages: usize,
    get_memory_map: usize,
    allocate_pool: usize,
    free_pool: usize,
    create_event: usize,
    set_timer: usize,
    wait_for_event: usize,
    signal_event: usize,
    close_event: usize,
    check_event: usize,
    install_protocol_interface: usize,
    reinstall_protocol_interface: usize,
    uninstall_protocol_interface: usize,
    handle_protocol: usize,
    reserved: usize,
    register_protocol_notify: usize,
    locate_handle: usize,
    locate_device_path: usize,
    install_configuration_table: usize,
    load_image: usize,
    start_image: usize,
    exit: usize,
    unload_image: usize,
    exit_boot_services: usize,
    get_next_monotonic_count: usize,
    stall: usize,
    set_watchdog_timer: usize,
    connect_controller: usize,
    disconnect_controller: usize,
    open_protocol: usize,
    close_protocol: usize,
    open_protocol_information: usize,
    protocols_per_handle: usize,
    locate_handle_buffer: usize,
    locate_protocol: usize,
    install_multiple_protocol_interfaces: usize,
    uninstall_multiple_protocol_interfaces: usize,
    calculate_crc32: usize,
    copy_mem: usize,
    set_mem: usize,
    create_event_ex: usize,
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
struct EfiGuid {
    data1: u32,
    data2: u16,
    data3: u16,
    data4: [u8; 8],
}

#[repr(C)]
struct EfiConfigurationTable {
    vendor_guid: EfiGuid,
    vendor_table: *const c_void,
}

#[repr(C)]
struct EfiGraphicsOutputProtocol {
    query_mode: usize,
    set_mode: usize,
    blt: usize,
    mode: *const EfiGraphicsOutputProtocolMode,
}

#[repr(C)]
struct EfiGraphicsOutputProtocolMode {
    max_mode: u32,
    mode: u32,
    info: *const EfiGraphicsOutputModeInformation,
    size_of_info: usize,
    framebuffer_base: u64,
    framebuffer_size: usize,
}

#[repr(C)]
struct EfiGraphicsOutputModeInformation {
    version: u32,
    horizontal_resolution: u32,
    vertical_resolution: u32,
    pixel_format: u32,
    red_mask: u32,
    green_mask: u32,
    blue_mask: u32,
    reserved_mask: u32,
    pixels_per_scan_line: u32,
}

const GOP_GUID: EfiGuid = EfiGuid {
    data1: 0x9042_a9de,
    data2: 0x23dc,
    data3: 0x4a38,
    data4: [0x96, 0xfb, 0x7a, 0xde, 0xd0, 0x80, 0x51, 0x6a],
};
const ACPI_20_GUID: EfiGuid = EfiGuid {
    data1: 0x8868_e871,
    data2: 0xe4f1,
    data3: 0x11d3,
    data4: [0xbc, 0x22, 0x00, 0x80, 0xc7, 0x3c, 0x88, 0x81],
};
const SMBIOS3_GUID: EfiGuid = EfiGuid {
    data1: 0xf2fd_1544,
    data2: 0x9794,
    data3: 0x4a2c,
    data4: [0x99, 0x2e, 0xe5, 0xbb, 0xcf, 0x20, 0xe3, 0x94],
};
const SMBIOS_GUID: EfiGuid = EfiGuid {
    data1: 0xeb9d_2d31,
    data2: 0x2d88,
    data3: 0x11d3,
    data4: [0x9a, 0x16, 0x00, 0x90, 0x27, 0x3f, 0xc1, 0x4d],
};

type OutputString = extern "efiapi" fn(*mut EfiSimpleTextOutputProtocol, *const u16) -> EfiStatus;
type GetMemoryMap =
    extern "efiapi" fn(*mut usize, *mut c_void, *mut usize, *mut usize, *mut u32) -> EfiStatus;
type AllocatePool = extern "efiapi" fn(u32, usize, *mut *mut c_void) -> EfiStatus;
type FreePool = extern "efiapi" fn(*mut c_void) -> EfiStatus;
type LocateProtocol =
    extern "efiapi" fn(*const EfiGuid, *mut c_void, *mut *mut c_void) -> EfiStatus;
type SetWatchdogTimer = extern "efiapi" fn(usize, u64, usize, *const u16) -> EfiStatus;

struct DiagnosticWriter;

impl Write for DiagnosticWriter {
    fn write_str(&mut self, value: &str) -> fmt::Result {
        emit_bytes(value.as_bytes());
        Ok(())
    }
}

#[derive(Clone, Copy)]
struct ConfigSummary {
    count: usize,
    acpi20: bool,
    smbios3: bool,
    smbios2: bool,
}

#[derive(Clone, Copy)]
struct GopSummary {
    layout: FramebufferLayout,
    mode: u32,
    physical_base: u64,
    byte_count: usize,
}

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    emit_bytes(b"POOLEBOOT/0.1 PANIC\n");
    unsafe {
        out_byte(DEBUG_EXIT_PORT, 0x21);
    }
    loop {
        core::hint::spin_loop();
    }
}

unsafe fn out_byte(port: u16, value: u8) {
    unsafe {
        asm!("out dx, al", in("dx") port, in("al") value, options(nomem, nostack, preserves_flags));
    }
}

unsafe fn in_byte(port: u16) -> u8 {
    let value: u8;
    unsafe {
        asm!("in al, dx", in("dx") port, out("al") value, options(nomem, nostack, preserves_flags));
    }
    value
}

fn initialize_serial() {
    unsafe {
        out_byte(COM1_BASE + 1, 0x00);
        out_byte(COM1_BASE + 3, 0x80);
        out_byte(COM1_BASE, 0x03);
        out_byte(COM1_BASE + 1, 0x00);
        out_byte(COM1_BASE + 3, 0x03);
        out_byte(COM1_BASE + 2, 0xc7);
        out_byte(COM1_BASE + 4, 0x0b);
    }
}

fn emit_byte(byte: u8) {
    unsafe {
        out_byte(DEBUGCON_PORT, byte);
    }
    for _ in 0..100_000 {
        if unsafe { in_byte(COM1_BASE + 5) } & 0x20 != 0 {
            unsafe {
                out_byte(COM1_BASE, byte);
            }
            return;
        }
        core::hint::spin_loop();
    }
}

fn emit_bytes(bytes: &[u8]) {
    for byte in bytes {
        if *byte == b'\n' {
            emit_byte(b'\r');
        }
        emit_byte(*byte);
    }
}

fn diagnostic(args: fmt::Arguments<'_>) {
    let _ = DiagnosticWriter.write_fmt(args);
}

fn fail(stage: &str, status: EfiStatus) -> EfiStatus {
    diagnostic(format_args!(
        "POOLEBOOT/0.1 ERROR stage={} status=0x{:016X}\n",
        stage, status as u64
    ));
    status
}

fn fail_detail(failure: kload::Failure) -> EfiStatus {
    diagnostic(format_args!(
        "POOLEBOOT/0.1 ERROR stage={} code={} status=0x{:016X}\n",
        failure.stage, failure.code, failure.status as u64
    ));
    failure.status
}

fn fail_exit_detail(failure: exit::Failure) -> EfiStatus {
    diagnostic(format_args!(
        "POOLEBOOT/0.1 ERROR stage={} code={} status=0x{:016X}\n",
        failure.stage, failure.code, failure.status as u64
    ));
    failure.status
}

fn allocate_pool_call(
    call: AllocatePool,
    memory_type: u32,
    byte_count: usize,
    pointer: *mut *mut c_void,
) -> EfiStatus {
    call(memory_type, byte_count, pointer)
}

fn free_pool_call(call: FreePool, pointer: *mut c_void) -> EfiStatus {
    call(pointer)
}

unsafe fn table_slice<'a>(pointer: *const u8, header_size: u32) -> Result<&'a [u8], ContractError> {
    if pointer.is_null() || header_size < pooleboot::TABLE_HEADER_BYTES as u32 {
        return Err(ContractError::BufferTooSmall);
    }
    let size = header_size as usize;
    if size > pooleboot::MAX_FIRMWARE_TABLE_BYTES {
        return Err(ContractError::HeaderSize);
    }
    Ok(unsafe { from_raw_parts(pointer, size) })
}

unsafe fn function<T: Copy>(address: usize) -> Result<T, EfiStatus> {
    if address == 0 || size_of::<T>() != size_of::<usize>() {
        return Err(EFI_COMPROMISED_DATA);
    }
    Ok(unsafe { transmute_copy::<usize, T>(&address) })
}

fn console_message(console: *mut EfiSimpleTextOutputProtocol) -> Result<(), EfiStatus> {
    if console.is_null() {
        return Err(EFI_UNSUPPORTED);
    }
    let output_address = unsafe { (*console).output_string };
    let output: OutputString = unsafe { function(output_address)? };
    const MESSAGE: &[u16] = &[
        0x0050, 0x006f, 0x006f, 0x006c, 0x0065, 0x004f, 0x0053, 0x0020, 0x006e, 0x0061, 0x0074,
        0x0069, 0x0076, 0x0065, 0x0020, 0x0055, 0x0045, 0x0046, 0x0049, 0x0020, 0x0070, 0x0072,
        0x006f, 0x006f, 0x0066, 0x0020, 0x006f, 0x0066, 0x0020, 0x006c, 0x0069, 0x0066, 0x0065,
        0x000d, 0x000a, 0x0000,
    ];
    let status = output(console, MESSAGE.as_ptr());
    if status == EFI_SUCCESS {
        Ok(())
    } else {
        Err(status)
    }
}

fn summarize_configuration_tables(system: &EfiSystemTable) -> Result<ConfigSummary, EfiStatus> {
    let count = validate_configuration_tables(
        system.configuration_table_count,
        !system.configuration_tables.is_null(),
    )
    .map_err(|_| EFI_COMPROMISED_DATA)?;
    let mut summary = ConfigSummary {
        count,
        acpi20: false,
        smbios3: false,
        smbios2: false,
    };
    if count == 0 {
        return Ok(summary);
    }
    let tables = unsafe { from_raw_parts(system.configuration_tables, count) };
    for table in tables {
        summary.acpi20 |= table.vendor_guid == ACPI_20_GUID;
        summary.smbios3 |= table.vendor_guid == SMBIOS3_GUID;
        summary.smbios2 |= table.vendor_guid == SMBIOS_GUID;
    }
    Ok(summary)
}

fn discover_gop(boot_services: &EfiBootServices) -> Result<GopSummary, EfiStatus> {
    let locate: LocateProtocol = unsafe { function(boot_services.locate_protocol)? };
    let mut interface = null_mut();
    let status = locate(&GOP_GUID, null_mut(), &mut interface);
    if status != EFI_SUCCESS || interface.is_null() {
        return Err(if status == EFI_SUCCESS {
            EFI_COMPROMISED_DATA
        } else {
            status
        });
    }
    let protocol = unsafe { &*(interface as *const EfiGraphicsOutputProtocol) };
    if protocol.mode.is_null() {
        return Err(EFI_COMPROMISED_DATA);
    }
    let mode = unsafe { &*protocol.mode };
    if mode.info.is_null() || mode.size_of_info < size_of::<EfiGraphicsOutputModeInformation>() {
        return Err(EFI_COMPROMISED_DATA);
    }
    let info = unsafe { &*mode.info };
    let layout = validate_framebuffer(
        info.horizontal_resolution as usize,
        info.vertical_resolution as usize,
        info.pixels_per_scan_line as usize,
        info.pixel_format,
        mode.framebuffer_base,
        mode.framebuffer_size,
    )
    .map_err(|_| EFI_UNSUPPORTED)?;
    if mode.framebuffer_base > usize::MAX as u64 {
        return Err(EFI_UNSUPPORTED);
    }
    let framebuffer = mode.framebuffer_base as usize as *mut u32;
    for y in 0..layout.height {
        for x in 0..layout.width {
            let pixel = pack_pixel(
                identity_rgb(x, y, layout.width, layout.height),
                layout.format,
            );
            let index = y * layout.stride + x;
            unsafe {
                write_volatile(framebuffer.wrapping_add(index), pixel);
            }
        }
    }
    Ok(GopSummary {
        layout,
        mode: mode.mode,
        physical_base: mode.framebuffer_base,
        byte_count: mode.framebuffer_size,
    })
}

fn run(image_handle: EfiHandle, system_table: *mut EfiSystemTable) -> EfiStatus {
    initialize_serial();
    diagnostic(format_args!("POOLEBOOT/0.1 ENTRY\n"));
    if image_handle.is_null() || system_table.is_null() {
        return fail("entry", EFI_INVALID_PARAMETER);
    }

    let system = unsafe { &*system_table };
    let system_bytes =
        match unsafe { table_slice(system_table.cast::<u8>(), system.header.header_size) } {
            Ok(bytes) => bytes,
            Err(_) => return fail("system_table_bounds", EFI_COMPROMISED_DATA),
        };
    if validate_table_header(
        system_bytes,
        EFI_SYSTEM_TABLE_SIGNATURE,
        size_of::<EfiSystemTable>(),
    )
    .is_err()
    {
        return fail("system_table", EFI_COMPROMISED_DATA);
    }
    diagnostic(format_args!(
        "POOLEBOOT/0.1 SYSTEM_TABLE PASS revision=0x{:08X}\n",
        system.header.revision
    ));

    if system.boot_services.is_null() {
        return fail("boot_services_pointer", EFI_COMPROMISED_DATA);
    }
    let boot_services = unsafe { &*system.boot_services };
    let boot_bytes = match unsafe {
        table_slice(
            system.boot_services.cast::<u8>(),
            boot_services.header.header_size,
        )
    } {
        Ok(bytes) => bytes,
        Err(_) => return fail("boot_services_bounds", EFI_COMPROMISED_DATA),
    };
    if validate_table_header(
        boot_bytes,
        EFI_BOOT_SERVICES_SIGNATURE,
        size_of::<EfiBootServices>(),
    )
    .is_err()
    {
        return fail("boot_services", EFI_COMPROMISED_DATA);
    }
    diagnostic(format_args!("POOLEBOOT/0.1 BOOT_SERVICES PASS\n"));

    let watchdog: SetWatchdogTimer = match unsafe { function(boot_services.set_watchdog_timer) } {
        Ok(function) => function,
        Err(status) => return fail("watchdog_pointer", status),
    };
    let watchdog_status = watchdog(0, 0, 0, null());
    diagnostic(format_args!(
        "POOLEBOOT/0.1 WATCHDOG status=0x{:016X}\n",
        watchdog_status as u64
    ));

    match console_message(system.console_out) {
        Ok(()) => diagnostic(format_args!("POOLEBOOT/0.1 CONSOLE PASS\n")),
        Err(status) => diagnostic(format_args!(
            "POOLEBOOT/0.1 CONSOLE FALLBACK status=0x{:016X}\n",
            status as u64
        )),
    }

    let config = match summarize_configuration_tables(system) {
        Ok(summary) => summary,
        Err(status) => return fail("configuration_tables", status),
    };
    diagnostic(format_args!(
        "POOLEBOOT/0.1 CONFIG PASS count={} acpi20={} smbios3={} smbios2={}\n",
        config.count,
        u8::from(config.acpi20),
        u8::from(config.smbios3),
        u8::from(config.smbios2)
    ));

    let gop_result = discover_gop(boot_services);

    let kernel = match kload::load_manifest_kernel(image_handle, boot_services) {
        Ok(summary) => summary,
        Err(failure) => return fail_detail(failure),
    };
    diagnostic(format_args!(
        "POOLEBOOT/0.1 FILESYSTEM PASS loaded_image=1 simple_fs=1 root=1\n"
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 BOOTCFG PASS bytes={} entries={} default_hash={:016X} timeout_ms={} attempts={} slot={} manifest_max_bytes={}\n",
        kernel.config.byte_count,
        kernel.config.entry_count,
        kernel.config.default_entry_hash,
        kernel.config.timeout_ms,
        kernel.config.boot_attempt_limit,
        kernel.config.selected_slot,
        kernel.config.manifest_max_bytes
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 MANIFEST PASS bytes={} artifacts={} id_hash={:016X} slot={} version={} minimum_secure_version={}\n",
        kernel.manifest.byte_count,
        kernel.manifest.artifact_count,
        kernel.manifest.manifest_id_hash,
        kernel.manifest.slot,
        kernel.manifest.manifest_version,
        kernel.manifest.minimum_secure_version
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 KERNEL_BINDING PASS version={} file_bytes={} image_bytes={} sha256_prefix={:016X} path=manifest\n",
        kernel.manifest.kernel_version,
        kernel.manifest.kernel_file_bytes,
        kernel.manifest.kernel_image_bytes,
        kernel.kernel_digest_prefix
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 KERNEL_FILE PASS bytes={} path=manifest_development\n",
        kernel.kernel_file_bytes
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 KERNEL_LOAD PASS image_bytes={} pages={} entry_offset={} relocations={} files_closed={} pools_freed={} fnv1a64={:016X}\n",
        kernel.kernel_image_bytes,
        kernel.page_count,
        kernel.entry_offset,
        kernel.relocation_count,
        kernel.closed_file_count,
        kernel.freed_pool_count,
        kernel.loaded_fnv1a64
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 ARTIFACT_SET PASS contract={} count={} file_bytes={} pages={} roles=2-7 fnv1a64={:016X} retained=1 signatures=0 measured=0\n",
        pooleboot::bootload::artifact::CONTRACT_ID,
        kernel.artifacts.len(),
        kernel.artifact_file_bytes,
        kernel.artifact_page_count,
        kernel.artifact_set_fnv1a64,
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 INNER_SET PASS proof={} artifacts={} parsers={} bindings={} denials={} file_bytes={} payload_bytes={} sha256={} retained=1 authority_grants={} actions={} state_writes={} hardware_observations={}\n",
        poole_inner_live::PROOF_ID,
        kernel.inner.artifact_count,
        kernel.inner.parser_count,
        kernel.inner.cross_binding_count,
        kernel.inner.development_denial_count,
        kernel.inner.file_bytes,
        kernel.inner.payload_bytes,
        kernel.inner.digest_hex(),
        kernel.inner.authority_grants,
        kernel.inner.actions_authorized,
        kernel.inner.state_writes,
        kernel.inner.hardware_observations,
    ));
    diagnostic(format_args!(
        "POOLEBOOT/0.1 TRUST_STATE DENY contract={} policy_bytes={} state_bytes={} bindings={} denials={} denial={} policy_sha256={} state_sha256={} source=esp_candidate auth=missing monotonic=missing signatures=0 authority_grants={} state_writes={}\n",
        poole_boot_trust::CONTRACT_ID,
        kernel.trust.policy_bytes,
        kernel.trust.state_bytes,
        kernel.trust.binding_count,
        kernel.trust.denial_count,
        kernel.trust.denial,
        poole_boot_trust::DigestHex::new(&kernel.trust.policy_sha256),
        poole_boot_trust::DigestHex::new(&kernel.trust.state_sha256),
        kernel.trust.authority_grants,
        kernel.trust.state_writes,
    ));
    let gop = match gop_result {
        Ok(summary) => {
            diagnostic(format_args!(
                "POOLEBOOT/0.1 GOP PASS width={} height={} stride={} mode={} format={}\n",
                summary.layout.width,
                summary.layout.height,
                summary.layout.stride,
                summary.mode,
                match summary.layout.format {
                    pooleboot::PixelFormat::Rgb => "RGB",
                    pooleboot::PixelFormat::Bgr => "BGR",
                }
            ));
            Some(summary)
        }
        Err(status) => {
            diagnostic(format_args!(
                "POOLEBOOT/0.1 GOP FALLBACK status=0x{:016X}\n",
                status as u64
            ));
            None
        }
    };
    if gop.is_some() {
        diagnostic(format_args!("POOLEBOOT/0.1 FRAME READY\n"));
    }
    match exit::exit_and_stop(
        image_handle,
        boot_services,
        &kernel,
        gop,
        system.header.revision,
    ) {
        Ok(()) => unreachable!(),
        Err(failure) => {
            if let Err(release_failure) = kload::release_loaded_pages(boot_services, &kernel) {
                return fail_detail(release_failure);
            }
            fail_exit_detail(failure)
        }
    }
}

#[unsafe(export_name = "efi_main")]
pub extern "efiapi" fn efi_entry(image_handle: EfiHandle, system_table: *mut c_void) -> EfiStatus {
    run(image_handle, system_table.cast::<EfiSystemTable>())
}
