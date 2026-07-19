#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

mod arch {
    pub mod x86_64;
}

use core::panic::PanicInfo;
use core::sync::atomic::{AtomicU32, Ordering};

use arch::x86_64::{Com1, DebugCon, halt_forever};
use poolekernel::{
    BUILD_ID, ByteSink, EARLY_LOG_CAPACITY, EarlyLogger, EarlyRing, Framebuffer, PanicCode,
    PanicDisposition, PanicState, TRANSFER_CONTRACT_ID, revalidation, validate_development_handoff,
    validate_entry_envelope, validate_handoff, validate_runtime_state,
};

#[used]
#[unsafe(link_section = ".poole.manifest")]
static KERNEL_MANIFEST: [u8; include_bytes!("../manifest.pkm").len()] =
    *include_bytes!("../manifest.pkm");

static EARLY_RING: EarlyRing = EarlyRing::new();
static PANIC_STATE: PanicState = PanicState::new();
static ENTRY_COUNT: AtomicU32 = AtomicU32::new(0);

core::arch::global_asm!(
    r#"
    .section .text.poole_entry,"ax",@progbits
    .global poole_kernel_entry
    .type poole_kernel_entry,@function
poole_kernel_entry:
    cli
    cld
    mov rcx, rsp
    test rcx, rcx
    jz .Lpoole_bad_stack
    test rcx, 15
    jnz .Lpoole_bad_stack
    mov rax, rcx
    shl rax, 16
    sar rax, 16
    cmp rax, rcx
    jne .Lpoole_bad_stack
    mov r8, cr3
    pushfq
    pop r9
    call poole_kernel_rust_entry
    mov edi, 0x10ff
    call poole_kernel_emergency_panic
.Lpoole_halt:
    cli
    hlt
    jmp .Lpoole_halt
.Lpoole_bad_stack:
    # No language call is safe until the incoming stack contract holds.
    jmp .Lpoole_halt
    .size poole_kernel_entry, .-poole_kernel_entry
"#
);

struct BootSink<'a> {
    serial: &'a mut Com1,
    debugcon: &'a mut DebugCon,
    ring: &'a EarlyRing,
}

impl ByteSink for BootSink<'_> {
    fn write_byte(&mut self, byte: u8) {
        if byte == b'\n' {
            self.ring.push(b'\r');
            self.serial.write_byte(b'\r');
            self.debugcon.write_byte(b'\r');
        }
        self.ring.push(byte);
        self.serial.write_byte(byte);
        self.debugcon.write_byte(byte);
    }
}

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    poole_kernel_emergency_panic(PanicCode::RustPanic as u32)
}

#[unsafe(no_mangle)]
extern "C" fn poole_kernel_emergency_panic(code: u32) -> ! {
    let code = match code {
        0x1001 => PanicCode::RustPanic,
        0x1002 => PanicCode::StackContract,
        0x1003 => PanicCode::HandoffEnvelope,
        0x1004 => PanicCode::HandoffDecode,
        0x1005 => PanicCode::HandoffProfile,
        0x1006 => PanicCode::RuntimeContinuity,
        0x1007 => PanicCode::TrustRevalidation,
        0x1008 => PanicCode::TransferState,
        0x1009 => PanicCode::Reentry,
        _ => PanicCode::UnexpectedReturn,
    };
    let disposition = PANIC_STATE.begin(code);
    // SAFETY: this is the ring-0 emergency path and uses only the bounded fixed COM1 probe.
    let mut serial = unsafe { Com1::initialize() };
    let mut debugcon = DebugCon::new();
    let mut logger = EarlyLogger::new(BootSink {
        serial: &mut serial,
        debugcon: &mut debugcon,
        ring: &EARLY_RING,
    });
    match disposition {
        PanicDisposition::Primary => logger.write_str("POOLEOS:PANIC:"),
        PanicDisposition::Nested => logger.write_str("POOLEOS:NESTED-PANIC:"),
    }
    logger.write_hex_u64(code as u64);
    logger.write_str("\n");
    halt_forever()
}

#[unsafe(no_mangle)]
extern "C" fn poole_kernel_rust_entry(
    handoff_address: usize,
    handoff_length: usize,
    magic: u64,
    stack_top: usize,
    observed_cr3: u64,
    observed_rflags: u64,
) -> ! {
    let entry_count = ENTRY_COUNT.fetch_add(1, Ordering::SeqCst).wrapping_add(1);
    if entry_count != 1 {
        poole_kernel_emergency_panic(PanicCode::Reentry as u32);
    }
    // SAFETY: PKENTRY1 enters at ring 0 and permits the bounded fixed COM1 probe.
    let mut serial = unsafe { Com1::initialize() };
    let serial_available = serial.available();
    let mut debugcon = DebugCon::new();

    if let Err(error) = validate_entry_envelope(handoff_address, handoff_length, magic, stack_top) {
        poole_kernel_emergency_panic(error.panic_code() as u32);
    }

    // SAFETY: the envelope passed canonical range, overflow, alignment, and size checks;
    // PKENTRY1 requires PooleBoot to map the complete immutable range read-only at entry.
    let handoff =
        unsafe { core::slice::from_raw_parts(handoff_address as *const u8, handoff_length) };
    let runtime_entry = poole_kernel_entry_address();
    let validated = match validate_handoff(handoff, runtime_entry, stack_top as u64) {
        Ok(_) => poole_kernel_emergency_panic(PanicCode::TransferState as u32),
        Err(poolekernel::EntryError::KernelProfile) => {
            match validate_development_handoff(handoff, runtime_entry, stack_top as u64) {
                Ok(value) => value,
                Err(error) => poole_kernel_emergency_panic(error.panic_code() as u32),
            }
        }
        Err(error) => poole_kernel_emergency_panic(error.panic_code() as u32),
    };
    if let Err(error) = validate_runtime_state(
        &validated,
        handoff_address as u64,
        handoff_length,
        stack_top as u64,
        observed_cr3,
        observed_rflags,
    ) {
        poole_kernel_emergency_panic(error.panic_code() as u32);
    }
    let decoded = match poole_handoff::decode(handoff) {
        Ok(value) => value,
        Err(_) => poole_kernel_emergency_panic(PanicCode::HandoffDecode as u32),
    };
    let loaded_artifacts = match decoded.record(poole_handoff::RECORD_LOADED_ARTIFACTS) {
        Some(value) => value,
        None => poole_kernel_emergency_panic(PanicCode::HandoffProfile as u32),
    };
    // SAFETY: PKENTRY1 requires every PBP1 retained-input range to remain
    // immutable and identity-mapped until this independent revalidation ends.
    let revalidated = match unsafe { revalidation::revalidate_development_from_handoff(handoff) } {
        Ok(value) => value,
        Err(_) => poole_kernel_emergency_panic(PanicCode::TrustRevalidation as u32),
    };

    {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_str("POOLEOS:KERNEL:ENTRY PASS contract=");
        logger.write_str(poolekernel::ENTRY_CONTRACT_ID);
        logger.write_str(" transfer_contract=");
        logger.write_str(TRANSFER_CONTRACT_ID);
        logger.write_str(" build=");
        logger.write_bytes(BUILD_ID);
        logger.write_str(" entry_count=");
        logger.write_decimal_u64(u64::from(entry_count));
        logger.write_str(" serial=");
        logger.write_str(if serial_available {
            "present"
        } else {
            "absent"
        });
        logger.write_str("\nPOOLEOS:KERNEL:STATE PASS handoff=");
        logger.write_hex_u64(handoff_address as u64);
        logger.write_str(" bytes=");
        logger.write_decimal_u64(handoff_length as u64);
        logger.write_str(" entry=");
        logger.write_hex_u64(runtime_entry);
        logger.write_str(" stack_top=");
        logger.write_hex_u64(stack_top as u64);
        logger.write_str(" root=");
        logger.write_hex_u64(validated.core.page_table_root_physical);
        logger.write_str(" cr3=");
        logger.write_hex_u64(observed_cr3);
        logger.write_str(" rflags_if=0 rflags_df=0\n");
        logger.write_str("POOLEOS:KERNEL:PBP1 PASS profile=development records=");
        logger.write_decimal_u64(decoded.header().record_count as u64);
        logger.write_str(" artifacts=");
        logger.write_decimal_u64(loaded_artifacts.descriptor.element_count as u64);
        logger.write_str(" production_profile_valid=0\n");
        logger.write_str("POOLEOS:KERNEL:PKREVAL PASS contract=");
        logger.write_str(revalidation::CONTRACT_ID);
        logger.write_str(" files=");
        logger.write_decimal_u64(u64::from(revalidated.retained_file_count));
        logger.write_str(" artifacts=");
        logger.write_decimal_u64(u64::from(revalidated.artifact_count));
        logger.write_str(" parsers=");
        logger.write_decimal_u64(u64::from(revalidated.parser_count));
        logger.write_str(" manifest_bytes=");
        logger.write_decimal_u64(u64::from(revalidated.manifest_bytes));
        logger.write_str(" retained_bytes=");
        logger.write_decimal_u64(u64::from(revalidated.retained_file_bytes));
        logger.write_str(" retained_set_sha256=");
        logger.write_hex_bytes(&revalidated.retained_set_sha256);
        logger.write_str(" policy_sha256=");
        logger.write_hex_bytes(&revalidated.policy_sha256);
        logger.write_str(" state_sha256=");
        logger.write_hex_bytes(&revalidated.state_sha256);
        logger.write_str(" denial=");
        logger.write_str(revalidated.denial);
        logger.write_str(" authority=");
        logger.write_decimal_u64(u64::from(revalidated.authority_grants));
        logger.write_str(" actions=");
        logger.write_decimal_u64(u64::from(revalidated.actions_authorized));
        logger.write_str(" writes=");
        logger.write_decimal_u64(u64::from(revalidated.state_writes));
        logger.write_str("\n");
    }

    if let Some(spec) = validated.framebuffer {
        let pixel_count = usize::try_from(spec.byte_count / 4).unwrap_or(0);
        let base = usize::try_from(spec.physical_base).unwrap_or(0);
        // SAFETY: PKENTRY1 requires an optional framebuffer record's complete physical
        // range to be temporarily identity-mapped writable until PooleKernel remaps it.
        let framebuffer = unsafe {
            Framebuffer::from_raw_parts(
                base as *mut u32,
                pixel_count,
                spec.width as usize,
                spec.height as usize,
                spec.stride as usize,
                spec.foreground,
                0,
            )
        };
        if let Some(framebuffer) = framebuffer {
            let mut logger = EarlyLogger::new(framebuffer);
            logger.write_str("POOLEOS KERNEL ENTRY\nBUILD ");
            logger.write_bytes(BUILD_ID);
            logger.write_str("\nPBP1 VALID\n");
        }
    }

    {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_str(
            "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0\n",
        );
    }
    halt_forever()
}

fn poole_kernel_entry_address() -> u64 {
    unsafe extern "C" {
        fn poole_kernel_entry();
    }
    poole_kernel_entry as *const () as usize as u64
}

const _: () = assert!(EARLY_LOG_CAPACITY >= 4096);
