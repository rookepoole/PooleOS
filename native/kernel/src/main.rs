#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

mod arch {
    pub mod x86_64;
}

use core::panic::PanicInfo;

use arch::x86_64::{Com1, halt_forever};
use poolekernel::{
    BUILD_ID, ByteSink, EARLY_LOG_CAPACITY, EarlyLogger, EarlyRing, Framebuffer, PanicCode,
    PanicDisposition, PanicState, validate_entry_envelope, validate_handoff,
};

#[used]
#[unsafe(link_section = ".poole.manifest")]
static KERNEL_MANIFEST: [u8; include_bytes!("../manifest.pkm").len()] =
    *include_bytes!("../manifest.pkm");

static EARLY_RING: EarlyRing = EarlyRing::new();
static PANIC_STATE: PanicState = PanicState::new();

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
    ring: &'a EarlyRing,
}

impl ByteSink for BootSink<'_> {
    fn write_byte(&mut self, byte: u8) {
        self.ring.push(byte);
        self.serial.write_byte(byte);
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
        _ => PanicCode::UnexpectedReturn,
    };
    let disposition = PANIC_STATE.begin(code);
    // SAFETY: this is the ring-0 emergency path and uses only the bounded fixed COM1 probe.
    let mut serial = unsafe { Com1::initialize() };
    let mut logger = EarlyLogger::new(BootSink {
        serial: &mut serial,
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
) -> ! {
    // SAFETY: PKENTRY1 enters at ring 0 and permits the bounded fixed COM1 probe.
    let mut serial = unsafe { Com1::initialize() };
    {
        let serial_available = serial.available();
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            ring: &EARLY_RING,
        });
        logger.write_str("POOLEOS:KERNEL:ENTRY\nBUILD:");
        logger.write_bytes(BUILD_ID);
        logger.write_str("\nSERIAL:");
        logger.write_str(if serial_available {
            "PRESENT\n"
        } else {
            "ABSENT\n"
        });
    }

    if let Err(error) = validate_entry_envelope(handoff_address, handoff_length, magic, stack_top) {
        poole_kernel_emergency_panic(error.panic_code() as u32);
    }

    // SAFETY: the envelope passed canonical range, overflow, alignment, and size checks;
    // PKENTRY1 requires PooleBoot to map the complete immutable range read-only at entry.
    let handoff =
        unsafe { core::slice::from_raw_parts(handoff_address as *const u8, handoff_length) };
    let runtime_entry = poole_kernel_entry_address();
    let validated = match validate_handoff(handoff, runtime_entry, stack_top as u64) {
        Ok(value) => value,
        Err(error) => poole_kernel_emergency_panic(error.panic_code() as u32),
    };

    {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            ring: &EARLY_RING,
        });
        logger.write_str("PBP1:VALID\nENTRY:");
        logger.write_hex_u64(runtime_entry);
        logger.write_str("\nIMAGE-BYTES:");
        logger.write_decimal_u64(validated.core.kernel_virtual_size);
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
            ring: &EARLY_RING,
        });
        logger.write_str("POOLEOS:KERNEL:ENTRY-READY\n");
        logger.write_str("EARLY-LOG-WRITES:");
        logger.write_decimal_u64(EARLY_RING.total_writes() as u64);
        logger.write_str("\n");
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
