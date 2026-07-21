#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

mod arch {
    pub mod x86_64;
}

use core::panic::PanicInfo;
use core::sync::atomic::{AtomicU32, AtomicU64, Ordering};

use arch::x86_64::{Com1, DebugCon, TrapFrame, halt_forever};
use poolekernel::{
    BUILD_ID, ByteSink, DevelopmentTrapScenario, EARLY_LOG_CAPACITY, EarlyLogger, EarlyRing,
    Framebuffer, PanicCode, PanicDisposition, PanicState, TRANSFER_CONTRACT_ID, TRAP_CONTRACT_ID,
    TrapDisposition, TrapError, TrapExpectation, TrapObservation, revalidation,
    validate_descriptor_state, validate_development_handoff, validate_entry_envelope,
    validate_handoff, validate_runtime_state, validate_trap_observation,
};

#[used]
#[unsafe(link_section = ".poole.manifest")]
static KERNEL_MANIFEST: [u8; include_bytes!("../manifest.pkm").len()] =
    *include_bytes!("../manifest.pkm");

static EARLY_RING: EarlyRing = EarlyRing::new();
static PANIC_STATE: PanicState = PanicState::new();
static ENTRY_COUNT: AtomicU32 = AtomicU32::new(0);
static TRAP_SCENARIO: AtomicU64 = AtomicU64::new(0);
static TRAP_DEPTH: AtomicU32 = AtomicU32::new(0);
static TRAP_RETURN_COUNT: AtomicU32 = AtomicU32::new(0);
static EXPECTED_PAGE_FAULT_ADDRESS: AtomicU64 = AtomicU64::new(0);
static IST1_BOTTOM: AtomicU64 = AtomicU64::new(0);
static IST1_TOP: AtomicU64 = AtomicU64::new(0);
static IST2_BOTTOM: AtomicU64 = AtomicU64::new(0);
static IST2_TOP: AtomicU64 = AtomicU64::new(0);

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
    sub rsp, 16
    mov qword ptr [rsp], r10
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
        0x100a => PanicCode::DescriptorState,
        0x100b => PanicCode::TrapContract,
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
    trap_scenario_selector: u64,
) -> ! {
    let entry_count = ENTRY_COUNT.fetch_add(1, Ordering::SeqCst).wrapping_add(1);
    if entry_count != 1 {
        poole_kernel_emergency_panic(PanicCode::Reentry as u32);
    }
    let trap_scenario = match DevelopmentTrapScenario::from_selector(trap_scenario_selector) {
        Some(value) => value,
        None => poole_kernel_emergency_panic(PanicCode::TransferState as u32),
    };
    TRAP_SCENARIO.store(trap_scenario_selector, Ordering::Release);
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

    if trap_scenario == DevelopmentTrapScenario::None {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_str(
            "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0\n",
        );
        halt_forever()
    }

    // SAFETY: PKXFER1 has installed the retained bootstrap stack, disabled IF/DF,
    // and transferred once on the BSP. PKTRAP1 owns these private descriptor statics.
    let descriptor_state = unsafe { arch::x86_64::install_descriptor_tables(stack_top as u64) };
    if validate_descriptor_state(&descriptor_state).is_err() {
        poole_kernel_emergency_panic(PanicCode::DescriptorState as u32);
    }
    IST1_BOTTOM.store(descriptor_state.ist1_bottom, Ordering::Release);
    IST1_TOP.store(descriptor_state.ist1_top, Ordering::Release);
    IST2_BOTTOM.store(descriptor_state.ist2_bottom, Ordering::Release);
    IST2_TOP.store(descriptor_state.ist2_top, Ordering::Release);
    {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_str("POOLEOS:KERNEL:TRAP-SETUP PASS contract=");
        logger.write_str(TRAP_CONTRACT_ID);
        logger.write_str(" scenario=");
        logger.write_str(trap_scenario.label());
        logger.write_str(" bsp=1 gdt_limit=");
        logger.write_decimal_u64(u64::from(descriptor_state.gdt_limit));
        logger.write_str(" idt_limit=");
        logger.write_decimal_u64(u64::from(descriptor_state.idt_limit));
        logger.write_str(" gates=");
        logger.write_decimal_u64(u64::from(descriptor_state.installed_gate_count));
        logger.write_str(" tss=1 rsp0=1 ist1=1 ist2=2 stack_bytes=");
        logger.write_decimal_u64(poolekernel::IST_STACK_BYTES);
        logger.write_str(" if=0\n");
    }

    match trap_scenario {
        DevelopmentTrapScenario::None => {
            poole_kernel_emergency_panic(PanicCode::TransferState as u32)
        }
        DevelopmentTrapScenario::Returning => {
            {
                let mut logger = EarlyLogger::new(BootSink {
                    serial: &mut serial,
                    debugcon: &mut debugcon,
                    ring: &EARLY_RING,
                });
                logger.write_str(
                    "POOLEOS:KERNEL:TRAP-ARM PASS contract=PKTRAP1 scenario=returning sequence=3,6,14\n",
                );
            }
            // SAFETY: the exact gates, TSS, IST pointers, and normalized frame passed setup.
            unsafe { arch::x86_64::trigger_breakpoint() };
            // SAFETY: #UD resumes only after the exact UD2 origin is validated.
            unsafe { arch::x86_64::trigger_invalid_opcode() };
            let guard_address = (stack_top as u64)
                .checked_sub(9 * poole_handoff::PAGE_BYTES)
                .unwrap_or_else(|| poole_kernel_emergency_panic(PanicCode::TrapContract as u32));
            EXPECTED_PAGE_FAULT_ADDRESS.store(guard_address, Ordering::Release);
            // SAFETY: the address is the retained stack's verified non-present low guard page.
            unsafe { arch::x86_64::trigger_page_fault(guard_address) };
            if TRAP_RETURN_COUNT.load(Ordering::Acquire) != 3 {
                poole_kernel_emergency_panic(PanicCode::TrapContract as u32);
            }
            let mut logger = EarlyLogger::new(BootSink {
                serial: &mut serial,
                debugcon: &mut debugcon,
                ring: &EARLY_RING,
            });
            logger.write_str(
                "POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 scenario=returning vectors=3,6,14 returned=3 terminal=halt\n",
            );
            halt_forever()
        }
        DevelopmentTrapScenario::DoubleFault => {
            {
                let mut logger = EarlyLogger::new(BootSink {
                    serial: &mut serial,
                    debugcon: &mut debugcon,
                    ring: &EARLY_RING,
                });
                logger.write_str(
                    "POOLEOS:KERNEL:TRAP-ARM PASS contract=PKTRAP1 scenario=double_fault trigger=gp_delivery_failure gp_gate_present=0\n",
                );
            }
            // SAFETY: this terminal scenario deliberately makes #GP delivery fail so
            // the processor must dispatch #DF through its separate IST2 gate.
            unsafe {
                arch::x86_64::arm_double_fault_delivery_failure();
                arch::x86_64::trigger_double_fault()
            }
        }
        DevelopmentTrapScenario::MalformedFrame => {
            {
                let mut logger = EarlyLogger::new(BootSink {
                    serial: &mut serial,
                    debugcon: &mut debugcon,
                    ring: &EARLY_RING,
                });
                logger.write_str(
                    "POOLEOS:KERNEL:TRAP-ARM PASS contract=PKTRAP1 scenario=malformed_frame vector=3 control=code_selector\n",
                );
            }
            // SAFETY: the valid #BP frame is then subjected to a synthetic semantic corruption.
            unsafe { arch::x86_64::trigger_breakpoint() };
            poole_kernel_emergency_panic(PanicCode::UnexpectedReturn as u32)
        }
    }
}

#[unsafe(no_mangle)]
extern "C" fn poole_kernel_trap_dispatch(frame_pointer: *mut TrapFrame) {
    if frame_pointer.is_null() {
        poole_kernel_emergency_panic(PanicCode::TrapContract as u32);
    }
    let depth = TRAP_DEPTH.fetch_add(1, Ordering::AcqRel).wrapping_add(1);
    if depth != 1 {
        poole_kernel_emergency_panic(PanicCode::TrapContract as u32);
    }
    // SAFETY: every installed PKTRAP1 stub passes its complete normalized frame.
    let frame = unsafe { &mut *frame_pointer };
    let scenario = DevelopmentTrapScenario::from_selector(TRAP_SCENARIO.load(Ordering::Acquire))
        .unwrap_or_else(|| poole_kernel_emergency_panic(PanicCode::TrapContract as u32));
    let (fault_rip, resume_rip, expected_cr2, ist_bottom, ist_top, terminal) =
        match (scenario, frame.vector) {
            (DevelopmentTrapScenario::Returning | DevelopmentTrapScenario::MalformedFrame, 3) => (
                arch::x86_64::breakpoint_resume_address(),
                arch::x86_64::breakpoint_resume_address(),
                None,
                IST1_BOTTOM.load(Ordering::Acquire),
                IST1_TOP.load(Ordering::Acquire),
                false,
            ),
            (DevelopmentTrapScenario::Returning, 6) => (
                arch::x86_64::invalid_opcode_fault_address(),
                arch::x86_64::invalid_opcode_resume_address(),
                None,
                IST1_BOTTOM.load(Ordering::Acquire),
                IST1_TOP.load(Ordering::Acquire),
                false,
            ),
            (DevelopmentTrapScenario::Returning, 14) => (
                arch::x86_64::page_fault_fault_address(),
                arch::x86_64::page_fault_resume_address(),
                Some(EXPECTED_PAGE_FAULT_ADDRESS.load(Ordering::Acquire)),
                IST1_BOTTOM.load(Ordering::Acquire),
                IST1_TOP.load(Ordering::Acquire),
                false,
            ),
            (DevelopmentTrapScenario::DoubleFault, 8) => (
                arch::x86_64::double_fault_origin_address(),
                arch::x86_64::double_fault_origin_address(),
                None,
                IST2_BOTTOM.load(Ordering::Acquire),
                IST2_TOP.load(Ordering::Acquire),
                true,
            ),
            _ => poole_kernel_emergency_panic(PanicCode::TrapContract as u32),
        };
    let observation = TrapObservation {
        vector: frame.vector,
        error_code: frame.error_code,
        rip: frame.rip,
        code_selector: frame.code_selector,
        rflags: frame.rflags,
        saved_rsp: frame.rsp,
        data_selector: frame.data_selector,
        cr2: if frame.vector == 14 {
            arch::x86_64::read_cr2()
        } else {
            0
        },
        handler_rsp: frame_pointer as u64,
        depth,
    };
    let expectation = TrapExpectation {
        vector: frame.vector,
        error_code: 0,
        fault_rip,
        resume_rip,
        expected_cr2,
        ist_bottom,
        ist_top,
        terminal,
    };
    let disposition = validate_trap_observation(&observation, &expectation)
        .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::TrapContract as u32));

    // SAFETY: this remains the bounded ring-0 diagnostic path with IF disabled.
    let mut serial = unsafe { Com1::initialize() };
    let mut debugcon = DebugCon::new();
    let mut logger = EarlyLogger::new(BootSink {
        serial: &mut serial,
        debugcon: &mut debugcon,
        ring: &EARLY_RING,
    });
    logger.write_str("POOLEOS:KERNEL:TRAP-ENTER PASS contract=PKTRAP1 scenario=");
    logger.write_str(scenario.label());
    logger.write_str(" vector=");
    logger.write_decimal_u64(frame.vector);
    logger.write_str(" error=");
    logger.write_hex_u64(frame.error_code);
    logger.write_str(" depth=");
    logger.write_decimal_u64(u64::from(depth));
    logger.write_str(" ist=");
    logger.write_decimal_u64(if frame.vector == 8 { 2 } else { 1 });
    logger.write_str("\n");

    if scenario == DevelopmentTrapScenario::MalformedFrame {
        let mut malformed = observation;
        malformed.code_selector = u64::from(poolekernel::KERNEL_DATA_SELECTOR);
        if validate_trap_observation(&malformed, &expectation) != Err(TrapError::CodeSelector) {
            poole_kernel_emergency_panic(PanicCode::TrapContract as u32);
        }
        logger.write_str(
            "POOLEOS:KERNEL:TRAP-MALFORMED DENIED contract=PKTRAP1 scenario=malformed_frame control=code_selector source=synthetic_semantic\n",
        );
        logger.write_str(
            "POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 scenario=malformed_frame rejected=1 terminal=halt\n",
        );
        halt_forever()
    }

    match disposition {
        TrapDisposition::ResumeAt(address) => {
            frame.rip = address;
            let returned = TRAP_RETURN_COUNT.fetch_add(1, Ordering::AcqRel) + 1;
            logger.write_str(
                "POOLEOS:KERNEL:TRAP-RETURN PASS contract=PKTRAP1 scenario=returning vector=",
            );
            logger.write_decimal_u64(frame.vector);
            logger.write_str(" resume=exact returned=");
            logger.write_decimal_u64(u64::from(returned));
            logger.write_str("\n");
            TRAP_DEPTH.store(0, Ordering::Release);
        }
        TrapDisposition::Halt => {
            logger.write_str(
                "POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 scenario=double_fault vector=8 ist=2 terminal=halt\n",
            );
            halt_forever()
        }
    }
}

fn poole_kernel_entry_address() -> u64 {
    unsafe extern "C" {
        fn poole_kernel_entry();
    }
    poole_kernel_entry as *const () as usize as u64
}

const _: () = assert!(EARLY_LOG_CAPACITY >= 4096);
