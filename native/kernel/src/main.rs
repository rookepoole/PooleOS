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
    BUILD_ID, ByteSink, CPU_POLICY_CONTRACT_ID, DevelopmentTrapScenario, EARLY_LOG_CAPACITY,
    EarlyLogger, EarlyRing, Framebuffer, PanicCode, PanicDisposition, PanicState,
    TRANSFER_CONTRACT_ID, TRAP_CONTRACT_ID, TrapDisposition, TrapError, TrapExpectation,
    TrapObservation, XSTATE_EXCEPTION_CONTRACT_ID, decode_cpu_identity,
    privilege_msr::{machine_check_bank_count, machine_check_ctl_present, validate_snapshot},
    revalidation, validate_cpu_policy_snapshot, validate_descriptor_state,
    validate_development_handoff, validate_entry_envelope, validate_handoff,
    validate_runtime_state, validate_trap_observation, validate_xstate_exception_descriptor_state,
    xstate::{
        AREA_BYTES as XSTATE_AREA_BYTES, CONTRACT_ID as XSTATE_CONTRACT_ID, ContextSwitch,
        effective_mxcsr_mask, validate_context_switch, validate_proof as validate_xstate_proof,
    },
    xstate_exception::{XstateExceptionKind, XstateExceptionState, validate_exception_state},
};

#[used]
#[unsafe(link_section = ".poole.manifest")]
static KERNEL_MANIFEST: [u8; include_bytes!("../manifest.pkm").len()] =
    *include_bytes!("../manifest.pkm");

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_ARM_MARKER: [u8; b"POOLEOS:KERNEL:XSTATE-EXCEPTION-ARM PASS contract=PKXEXC1 sequence=16,19,7 x87=invalid fcw=0x000000000000037E simd=invalid mxcsr=0x0000000000001F00 nm_strategy=eager_reject\n".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-ARM PASS contract=PKXEXC1 sequence=16,19,7 x87=invalid fcw=0x000000000000037E simd=invalid mxcsr=0x0000000000001F00 nm_strategy=eager_reject\n";

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_NM_ARM_MARKER: [u8; b"POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-ARM PASS contract=PKXEXC1 vector=7 injection=test_only cr0_ts=1 recovery=forbidden terminal=reject\n".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-ARM PASS contract=PKXEXC1 vector=7 injection=test_only cr0_ts=1 recovery=forbidden terminal=reject\n";

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_NM_REJECT_MARKER: [u8; b"POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-REJECT PASS contract=PKXEXC1 vector=7 strategy=eager reason=ts_set injection=test_only state_sampled=0 recovery=forbidden terminal=halt\n".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-REJECT PASS contract=PKXEXC1 vector=7 strategy=eager reason=ts_set injection=test_only state_sampled=0 recovery=forbidden terminal=halt\n";

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_RESULT_MARKER: [u8; b"POOLEOS:KERNEL:XSTATE-EXCEPTION-RESULT PASS contract=PKXEXC1 deliveries=3 recovered=2 nm_rejected=1 privileged_writes=4 recovery_writes=2 unexpected=0 signatures=0 authority=0 actions=0 scheduler=0 smp=0 target=0 terminal=halt\n".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-RESULT PASS contract=PKXEXC1 deliveries=3 recovered=2 nm_rejected=1 privileged_writes=4 recovery_writes=2 unexpected=0 signatures=0 authority=0 actions=0 scheduler=0 smp=0 target=0 terminal=halt\n";

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_SETUP_PREFIX: [u8;
    b"POOLEOS:KERNEL:XSTATE-EXCEPTION-SETUP PASS contract=".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-SETUP PASS contract=";

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_SIMD_DELIVERY_ERROR_PREFIX: [u8;
    b"POOLEOS:KERNEL:XSTATE-EXCEPTION-SIMD-DELIVERY-ERROR returned=".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-SIMD-DELIVERY-ERROR returned=";

#[used]
#[unsafe(link_section = ".text.pkxexc_literals")]
static XSTATE_EXCEPTION_PARENT_ERROR_PREFIX: [u8;
    b"POOLEOS:KERNEL:XSTATE-EXCEPTION-PARENT-ERROR reason=".len()] =
    *b"POOLEOS:KERNEL:XSTATE-EXCEPTION-PARENT-ERROR reason=";

macro_rules! pkmsr_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkmsr_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pkmsr_fragment!(
    PKMSR_FEATURES,
    b"POOLEOS:KERNEL:PRIV-MSR-FEATURES OBSERVE contract=PKMSR1 vendor_hex="
);
pkmsr_fragment!(PKMSR_MAX_BASIC, b" max_basic=");
pkmsr_fragment!(PKMSR_MAX_EXTENDED, b" max_extended=");
pkmsr_fragment!(PKMSR_LEAF1_EDX, b" leaf1_edx=");
pkmsr_fragment!(PKMSR_EXT1_EDX, b" ext1_edx=");
pkmsr_fragment!(PKMSR_LEAFA_EAX, b" leafa_eax=");
pkmsr_fragment!(PKMSR_EXT22_EAX, b" ext22_eax=");
pkmsr_fragment!(PKMSR_CR4, b" cr4=");
pkmsr_fragment!(PKMSR_SYSCALL, b" syscall=");
pkmsr_fragment!(PKMSR_RDTSCP, b" rdtscp=");
pkmsr_fragment!(PKMSR_MCE, b" mce=");
pkmsr_fragment!(PKMSR_MCA, b" mca=");
pkmsr_fragment!(PKMSR_ARCH_PMU, b" arch_pmu_version=");
pkmsr_fragment!(PKMSR_AMD_PMU, b" amd_perfmon_v2=");
pkmsr_fragment!(
    PKMSR_LINKAGE,
    b"\nPOOLEOS:KERNEL:PRIV-MSR-LINKAGE OBSERVE contract=PKMSR1 efer="
);
pkmsr_fragment!(PKMSR_STAR, b" star=");
pkmsr_fragment!(PKMSR_LSTAR, b" lstar=");
pkmsr_fragment!(PKMSR_CSTAR, b" cstar=");
pkmsr_fragment!(PKMSR_SFMASK, b" sfmask=");
pkmsr_fragment!(
    PKMSR_BASES,
    b" active=0 reads=5\nPOOLEOS:KERNEL:PRIV-MSR-BASES OBSERVE contract=PKMSR1 fs_base="
);
pkmsr_fragment!(PKMSR_GS_BASE, b" gs_base=");
pkmsr_fragment!(PKMSR_KERNEL_GS_BASE, b" kernel_gs_base=");
pkmsr_fragment!(PKMSR_TSC_AUX, b" tsc_aux=");
pkmsr_fragment!(PKMSR_TSC_AUX_READ, b" tsc_aux_read=");
pkmsr_fragment!(PKMSR_READS, b" reads=");
pkmsr_fragment!(
    PKMSR_MCG,
    b"\nPOOLEOS:KERNEL:PRIV-MSR-MCE OBSERVE contract=PKMSR1 mcg_cap="
);
pkmsr_fragment!(PKMSR_MCG_STATUS, b" mcg_status=");
pkmsr_fragment!(PKMSR_MCG_CTL, b" mcg_ctl=");
pkmsr_fragment!(PKMSR_BANK_COUNT, b" bank_count=");
pkmsr_fragment!(PKMSR_CTL_PRESENT, b" ctl_present=");
pkmsr_fragment!(PKMSR_BANK_READS, b" bank_reads=0 reads=");
pkmsr_fragment!(
    PKMSR_PMU,
    b"\nPOOLEOS:KERNEL:PRIV-MSR-PMU OBSERVE contract=PKMSR1 architectural="
);
pkmsr_fragment!(PKMSR_AMD_V2, b" amd_v2=");
pkmsr_fragment!(PKMSR_PMU_SCOPE, b" msr_reads=0 rdpmc=0 cr4_pce=");
pkmsr_fragment!(PKMSR_DISABLED, b" policy=disabled\n");
pkmsr_fragment!(
    PKMSR_DENIED,
    b"POOLEOS:KERNEL:PRIV-MSR-DENIED contract=PKMSR1 reason="
);
pkmsr_fragment!(
    PKMSR_DENIED_TAIL,
    b" msr_writes=0 authority=0 actions=0 terminal=panic\n"
);
pkmsr_fragment!(
    PKMSR_RESULT,
    b"POOLEOS:KERNEL:PRIV-MSR-RESULT PASS contract=PKMSR1 profile=qemu64_tier0 bsp=1 policy=read_only_support_gated msr_reads="
);
pkmsr_fragment!(
    PKMSR_RESULT_TAIL,
    b" msr_writes=0 control_writes=0 signatures=0 authority=0 actions=0 interrupts=0 syscall_active=0 mce_handler=0 pmu_owner=0 terminal=halt\n"
);

#[used]
#[unsafe(link_section = ".text.pkcpu_literals")]
static CPU_STATE_JOIN: [u8;
    b" ownership=observation_only\nPOOLEOS:KERNEL:CPU-STATE OBSERVE contract=".len()] =
    *b" ownership=observation_only\nPOOLEOS:KERNEL:CPU-STATE OBSERVE contract=";

#[used]
#[unsafe(link_section = ".text.pkcpu_literals")]
static CPU_DENIED_PREFIX: [u8; b"POOLEOS:KERNEL:CPU-DENIED contract=PKCPU1 reason=".len()] =
    *b"POOLEOS:KERNEL:CPU-DENIED contract=PKCPU1 reason=";

#[used]
#[unsafe(link_section = ".text.pkcpu_literals")]
static CPU_DENIED_TAIL: [u8; b" writes=0 authority=0 actions=0 terminal=panic\n".len()] =
    *b" writes=0 authority=0 actions=0 terminal=panic\n";

#[used]
#[unsafe(link_section = ".text.pkcpu_literals")]
static CPU_RESULT_PREFIX: [u8; b"POOLEOS:KERNEL:CPU-RESULT PASS contract=".len()] =
    *b"POOLEOS:KERNEL:CPU-RESULT PASS contract=";

#[used]
#[unsafe(link_section = ".text.pkcpu_literals")]
static CPU_RESULT_TAIL: [u8; b" profile=qemu64_tier0 bsp=1 policy=required_and_support_gated reads=cpuid_cr_msr writes=0 signatures=0 authority=0 actions=0 interrupts=0 terminal=halt\n".len()] =
    *b" profile=qemu64_tier0 bsp=1 policy=required_and_support_gated reads=cpuid_cr_msr writes=0 signatures=0 authority=0 actions=0 interrupts=0 terminal=halt\n";

static EARLY_RING: EarlyRing = EarlyRing::new();
static PANIC_STATE: PanicState = PanicState::new();
static ENTRY_COUNT: AtomicU32 = AtomicU32::new(0);
static TRAP_SCENARIO: AtomicU64 = AtomicU64::new(0);
static TRAP_DEPTH: AtomicU32 = AtomicU32::new(0);
static TRAP_RETURN_COUNT: AtomicU32 = AtomicU32::new(0);
static XSTATE_EXCEPTION_RETURN_COUNT: AtomicU32 = AtomicU32::new(0);
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
        0x100c => PanicCode::CpuPolicy,
        0x100d => PanicCode::XstatePolicy,
        0x100e => PanicCode::XstateException,
        0x100f => PanicCode::PrivilegeMsrPolicy,
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

    if trap_scenario == DevelopmentTrapScenario::CpuPolicy {
        // SAFETY: PKXFER1 has transferred once at CPL0 with IF/DF clear. PKCPU1 performs
        // only support-gated CPUID, control-register, XCR0, and MSR reads.
        let snapshot = unsafe { arch::x86_64::observe_cpu_policy() };
        let discovery = &snapshot.discovery;
        let control = &snapshot.control;
        let identity = decode_cpu_identity(discovery.leaf1_eax);
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_str("POOLEOS:KERNEL:CPU-DISCOVERY OBSERVE contract=");
        logger.write_str(CPU_POLICY_CONTRACT_ID);
        logger.write_str(" vendor_hex=");
        logger.write_hex_bytes(&discovery.vendor);
        logger.write_str(" brand_hex=");
        logger.write_hex_bytes(&discovery.brand);
        logger.write_str(" max_basic=");
        logger.write_hex_u64(u64::from(discovery.max_basic_leaf));
        logger.write_str(" max_extended=");
        logger.write_hex_u64(u64::from(discovery.max_extended_leaf));
        logger.write_str(" signature=");
        logger.write_hex_u64(u64::from(discovery.leaf1_eax));
        logger.write_str(" family=");
        logger.write_decimal_u64(u64::from(identity.family));
        logger.write_str(" model=");
        logger.write_decimal_u64(u64::from(identity.model));
        logger.write_str(" stepping=");
        logger.write_decimal_u64(u64::from(identity.stepping));
        logger.write_str(" logical=");
        let leaf_b_logical = discovery.leaf_b0_ebx & 0xffff;
        let leaf1_logical = (discovery.leaf1_ebx >> 16) & 0xff;
        logger.write_decimal_u64(u64::from(if leaf_b_logical != 0 {
            leaf_b_logical
        } else if leaf1_logical != 0 {
            leaf1_logical
        } else {
            1
        }));
        logger.write_str(" apic_id=");
        logger.write_decimal_u64(u64::from(discovery.leaf1_ebx >> 24));
        logger.write_str(" physical_width=");
        logger.write_decimal_u64(u64::from(discovery.ext8_eax & 0xff));
        logger.write_str(" linear_width=");
        logger.write_decimal_u64(u64::from((discovery.ext8_eax >> 8) & 0xff));
        logger.write_str("\nPOOLEOS:KERNEL:CPU-TOPOLOGY OBSERVE contract=");
        logger.write_str(CPU_POLICY_CONTRACT_ID);
        logger.write_str(" leaf4_eax=");
        logger.write_hex_u64(u64::from(discovery.leaf4_eax));
        logger.write_str(" leaf4_ebx=");
        logger.write_hex_u64(u64::from(discovery.leaf4_ebx));
        logger.write_str(" leaf4_ecx=");
        logger.write_hex_u64(u64::from(discovery.leaf4_ecx));
        logger.write_str(" leaf4_edx=");
        logger.write_hex_u64(u64::from(discovery.leaf4_edx));
        logger.write_str(" leafb0_eax=");
        logger.write_hex_u64(u64::from(discovery.leaf_b0_eax));
        logger.write_str(" leafb0_ebx=");
        logger.write_hex_u64(u64::from(discovery.leaf_b0_ebx));
        logger.write_str(" leafb0_ecx=");
        logger.write_hex_u64(u64::from(discovery.leaf_b0_ecx));
        logger.write_str(" leafb0_edx=");
        logger.write_hex_u64(u64::from(discovery.leaf_b0_edx));
        logger.write_str(" ext6_ecx=");
        logger.write_hex_u64(u64::from(discovery.ext6_ecx));
        logger.write_str("\nPOOLEOS:KERNEL:CPU-FEATURES OBSERVE contract=");
        logger.write_str(CPU_POLICY_CONTRACT_ID);
        logger.write_str(" leaf1_ecx=");
        logger.write_hex_u64(u64::from(discovery.leaf1_ecx));
        logger.write_str(" leaf1_edx=");
        logger.write_hex_u64(u64::from(discovery.leaf1_edx));
        logger.write_str(" leaf6_eax=");
        logger.write_hex_u64(u64::from(discovery.leaf6_eax));
        logger.write_str(" leaf7_ebx=");
        logger.write_hex_u64(u64::from(discovery.leaf7_ebx));
        logger.write_str(" leaf7_ecx=");
        logger.write_hex_u64(u64::from(discovery.leaf7_ecx));
        logger.write_str(" leaf7_edx=");
        logger.write_hex_u64(u64::from(discovery.leaf7_edx));
        logger.write_str(" leafa_eax=");
        logger.write_hex_u64(u64::from(discovery.leaf_a_eax));
        logger.write_str(" ext1_ecx=");
        logger.write_hex_u64(u64::from(discovery.ext1_ecx));
        logger.write_str(" ext1_edx=");
        logger.write_hex_u64(u64::from(discovery.ext1_edx));
        logger.write_str(" ext7_edx=");
        logger.write_hex_u64(u64::from(discovery.ext7_edx));
        logger.write_str(" ext1f_eax=");
        logger.write_hex_u64(u64::from(discovery.ext1f_eax));
        logger.write_str("\nPOOLEOS:KERNEL:CPU-XSAVE OBSERVE contract=");
        logger.write_str(CPU_POLICY_CONTRACT_ID);
        logger.write_str(" leafd0_eax=");
        logger.write_hex_u64(u64::from(discovery.leaf_d0_eax));
        logger.write_str(" leafd0_ebx=");
        logger.write_hex_u64(u64::from(discovery.leaf_d0_ebx));
        logger.write_str(" leafd0_ecx=");
        logger.write_hex_u64(u64::from(discovery.leaf_d0_ecx));
        logger.write_str(" leafd0_edx=");
        logger.write_hex_u64(u64::from(discovery.leaf_d0_edx));
        logger.write_str(" xcr0=");
        logger.write_hex_u64(control.xcr0);
        logger.write_bytes(&CPU_STATE_JOIN);
        logger.write_str(CPU_POLICY_CONTRACT_ID);
        logger.write_str(" cr0=");
        logger.write_hex_u64(control.cr0);
        logger.write_str(" cr4=");
        logger.write_hex_u64(control.cr4);
        logger.write_str(" efer=");
        logger.write_hex_u64(control.efer);
        logger.write_str(" apic_base=");
        logger.write_hex_u64(control.apic_base);
        logger.write_str(" pat=");
        logger.write_hex_u64(control.pat);
        logger.write_str(" mtrr_cap=");
        logger.write_hex_u64(control.mtrr_cap);
        logger.write_str(" mtrr_def=");
        logger.write_hex_u64(control.mtrr_def_type);
        logger.write_str(" msr_read_mask=");
        logger.write_hex_u64(u64::from(control.msr_read_mask));
        logger.write_str("\n");
        if let Err(error) = validate_cpu_policy_snapshot(&snapshot) {
            logger.write_bytes(&CPU_DENIED_PREFIX);
            logger.write_str(error.label());
            logger.write_bytes(&CPU_DENIED_TAIL);
            poole_kernel_emergency_panic(PanicCode::CpuPolicy as u32);
        }
        logger.write_bytes(&CPU_RESULT_PREFIX);
        logger.write_str(CPU_POLICY_CONTRACT_ID);
        logger.write_bytes(&CPU_RESULT_TAIL);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::PrivilegeMsrPolicy {
        // SAFETY: PKXFER1 transferred once at CPL0 with IF/DF clear. PKMSR1 performs
        // only support-gated CPUID, CR4, and allowlisted RDMSR observations.
        let snapshot = unsafe { arch::x86_64::observe_privilege_msr_policy() };
        let bank_count = machine_check_bank_count(&snapshot);
        let ctl_present = machine_check_ctl_present(&snapshot);
        let syscall = snapshot.ext1_edx & (1 << 11) != 0;
        let rdtscp = snapshot.ext1_edx & (1 << 27) != 0;
        let mce = snapshot.leaf1_edx & (1 << 7) != 0;
        let mca = snapshot.leaf1_edx & (1 << 14) != 0;
        let arch_pmu_version = snapshot.leaf_a_eax & 0xff;
        let amd_perfmon_v2 = snapshot.ext22_eax & 0xff;
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKMSR_FEATURES);
        logger.write_hex_bytes(&snapshot.vendor);
        logger.write_bytes(&PKMSR_MAX_BASIC);
        logger.write_hex_u64(u64::from(snapshot.max_basic_leaf));
        logger.write_bytes(&PKMSR_MAX_EXTENDED);
        logger.write_hex_u64(u64::from(snapshot.max_extended_leaf));
        logger.write_bytes(&PKMSR_LEAF1_EDX);
        logger.write_hex_u64(u64::from(snapshot.leaf1_edx));
        logger.write_bytes(&PKMSR_EXT1_EDX);
        logger.write_hex_u64(u64::from(snapshot.ext1_edx));
        logger.write_bytes(&PKMSR_LEAFA_EAX);
        logger.write_hex_u64(u64::from(snapshot.leaf_a_eax));
        logger.write_bytes(&PKMSR_EXT22_EAX);
        logger.write_hex_u64(u64::from(snapshot.ext22_eax));
        logger.write_bytes(&PKMSR_CR4);
        logger.write_hex_u64(snapshot.cr4);
        logger.write_bytes(&PKMSR_SYSCALL);
        logger.write_decimal_u64(u64::from(syscall));
        logger.write_bytes(&PKMSR_RDTSCP);
        logger.write_decimal_u64(u64::from(rdtscp));
        logger.write_bytes(&PKMSR_MCE);
        logger.write_decimal_u64(u64::from(mce));
        logger.write_bytes(&PKMSR_MCA);
        logger.write_decimal_u64(u64::from(mca));
        logger.write_bytes(&PKMSR_ARCH_PMU);
        logger.write_decimal_u64(u64::from(arch_pmu_version));
        logger.write_bytes(&PKMSR_AMD_PMU);
        logger.write_decimal_u64(u64::from(amd_perfmon_v2));
        logger.write_bytes(&PKMSR_LINKAGE);
        logger.write_hex_u64(snapshot.efer);
        logger.write_bytes(&PKMSR_STAR);
        logger.write_hex_u64(snapshot.star);
        logger.write_bytes(&PKMSR_LSTAR);
        logger.write_hex_u64(snapshot.lstar);
        logger.write_bytes(&PKMSR_CSTAR);
        logger.write_hex_u64(snapshot.cstar);
        logger.write_bytes(&PKMSR_SFMASK);
        logger.write_hex_u64(snapshot.sfmask);
        logger.write_bytes(&PKMSR_BASES);
        logger.write_hex_u64(snapshot.fs_base);
        logger.write_bytes(&PKMSR_GS_BASE);
        logger.write_hex_u64(snapshot.gs_base);
        logger.write_bytes(&PKMSR_KERNEL_GS_BASE);
        logger.write_hex_u64(snapshot.kernel_gs_base);
        logger.write_bytes(&PKMSR_TSC_AUX);
        logger.write_hex_u64(snapshot.tsc_aux);
        logger.write_bytes(&PKMSR_TSC_AUX_READ);
        logger.write_decimal_u64(u64::from(rdtscp));
        logger.write_bytes(&PKMSR_READS);
        logger.write_decimal_u64(3 + u64::from(rdtscp));
        logger.write_bytes(&PKMSR_MCG);
        logger.write_hex_u64(snapshot.mcg_cap);
        logger.write_bytes(&PKMSR_MCG_STATUS);
        logger.write_hex_u64(snapshot.mcg_status);
        logger.write_bytes(&PKMSR_MCG_CTL);
        logger.write_hex_u64(snapshot.mcg_ctl);
        logger.write_bytes(&PKMSR_BANK_COUNT);
        logger.write_decimal_u64(u64::from(bank_count));
        logger.write_bytes(&PKMSR_CTL_PRESENT);
        logger.write_decimal_u64(u64::from(ctl_present));
        logger.write_bytes(&PKMSR_BANK_READS);
        logger.write_decimal_u64(2 + u64::from(ctl_present));
        logger.write_bytes(&PKMSR_PMU);
        logger.write_decimal_u64(u64::from(arch_pmu_version != 0));
        logger.write_bytes(&PKMSR_AMD_V2);
        logger.write_decimal_u64(u64::from(amd_perfmon_v2 != 0));
        logger.write_bytes(&PKMSR_PMU_SCOPE);
        logger.write_decimal_u64(u64::from(snapshot.cr4 & (1 << 8) != 0));
        logger.write_bytes(&PKMSR_DISABLED);
        if let Err(error) = validate_snapshot(&snapshot) {
            logger.write_bytes(&PKMSR_DENIED);
            logger.write_str(error.label());
            logger.write_bytes(&PKMSR_DENIED_TAIL);
            poole_kernel_emergency_panic(PanicCode::PrivilegeMsrPolicy as u32);
        }
        logger.write_bytes(&PKMSR_RESULT);
        logger.write_decimal_u64(u64::from(snapshot.msr_read_mask.count_ones()));
        logger.write_bytes(&PKMSR_RESULT_TAIL);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::XstatePolicy {
        // SAFETY: PKXFER1 transferred exactly once at CPL0 with IF/DF clear. The opt-in
        // PKXSTATE1 profile owns the BSP's x87/SSE state and its private aligned images.
        let proof = match unsafe { arch::x86_64::run_xstate_policy() } {
            Ok(value) => value,
            Err(error) => {
                let mut logger = EarlyLogger::new(BootSink {
                    serial: &mut serial,
                    debugcon: &mut debugcon,
                    ring: &EARLY_RING,
                });
                logger.write_str("POOLEOS:KERNEL:XSTATE-DENIED contract=PKXSTATE1 reason=");
                logger.write_str(error.label());
                logger.write_str(" terminal=panic\n");
                poole_kernel_emergency_panic(PanicCode::XstatePolicy as u32);
            }
        };
        let context_switch = ContextSwitch {
            outgoing_owner: 0xa,
            incoming_owner: 0xb,
            outgoing_address: proof.policy.area_address,
            incoming_address: proof.policy.area_address + u64::from(XSTATE_AREA_BYTES),
            image_bytes: XSTATE_AREA_BYTES,
            selected_xcr0: proof.policy.selected_xcr0,
            incoming_initialized: true,
            scheduler_lock_held: true,
            interrupts_disabled: true,
            kernel_simd_active: false,
            same_cpu: true,
        };
        if let Err(error) = validate_xstate_proof(&proof) {
            let mut logger = EarlyLogger::new(BootSink {
                serial: &mut serial,
                debugcon: &mut debugcon,
                ring: &EARLY_RING,
            });
            logger.write_str("POOLEOS:KERNEL:XSTATE-DENIED contract=PKXSTATE1 reason=");
            logger.write_str(error.label());
            logger.write_str(" cr0=");
            logger.write_hex_u64(proof.policy.cr0);
            logger.write_str(" cr4=");
            logger.write_hex_u64(proof.policy.cr4);
            logger.write_str(" fcw=");
            logger.write_hex_u64(u64::from(proof.initial_fcw));
            logger.write_str(" mxcsr=");
            logger.write_hex_u64(u64::from(proof.initial_mxcsr));
            logger.write_str(" terminal=panic\n");
            poole_kernel_emergency_panic(PanicCode::XstatePolicy as u32);
        }
        if validate_context_switch(&context_switch).is_err() {
            poole_kernel_emergency_panic(PanicCode::XstatePolicy as u32);
        }

        let policy = &proof.policy;
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_str("POOLEOS:KERNEL:XSTATE-CAPABILITY PASS contract=");
        logger.write_str(XSTATE_CONTRACT_ID);
        logger.write_str(" leaf1_ecx=");
        logger.write_hex_u64(u64::from(policy.leaf1_ecx));
        logger.write_str(" leaf1_edx=");
        logger.write_hex_u64(u64::from(policy.leaf1_edx));
        logger.write_str(" supported_xcr0=");
        logger.write_hex_u64(policy.supported_xcr0);
        logger.write_str(" leafd1_eax=");
        logger.write_hex_u64(u64::from(policy.leaf_d1_eax));
        logger.write_str(" enabled_bytes=");
        logger.write_decimal_u64(u64::from(policy.enabled_area_bytes));
        logger.write_str(" maximum_bytes=");
        logger.write_decimal_u64(u64::from(policy.maximum_area_bytes));
        logger.write_str("\nPOOLEOS:KERNEL:XSTATE-CONFIG PASS contract=");
        logger.write_str(XSTATE_CONTRACT_ID);
        logger.write_str(" cr0_before=");
        logger.write_hex_u64(proof.cr0_before);
        logger.write_str(" cr0_after=");
        logger.write_hex_u64(policy.cr0);
        logger.write_str(" cr4_before=");
        logger.write_hex_u64(proof.cr4_before);
        logger.write_str(" cr4_after=");
        logger.write_hex_u64(policy.cr4);
        logger.write_str(" xcr0_before=");
        logger.write_hex_u64(proof.xcr0_before);
        logger.write_str(" xcr0_after=");
        logger.write_hex_u64(policy.selected_xcr0);
        logger.write_str(" xss=0x0000000000000000 strategy=eager format=standard area_bytes=");
        logger.write_decimal_u64(u64::from(policy.area_bytes));
        logger.write_str(" alignment=64\nPOOLEOS:KERNEL:XSTATE-INIT PASS contract=");
        logger.write_str(XSTATE_CONTRACT_ID);
        logger.write_str(" fcw=");
        logger.write_hex_u64(u64::from(proof.initial_fcw));
        logger.write_str(" mxcsr=");
        logger.write_hex_u64(u64::from(proof.initial_mxcsr));
        logger.write_str(" mxcsr_mask_raw=");
        logger.write_hex_u64(u64::from(policy.mxcsr_mask));
        logger.write_str(" mxcsr_mask_effective=");
        logger.write_hex_u64(u64::from(effective_mxcsr_mask(policy.mxcsr_mask)));
        logger.write_str(" exceptions=masked nm_policy=unexpected_fail_closed\n");
        logger.write_str("POOLEOS:KERNEL:XSTATE-SWITCH PASS contract=");
        logger.write_str(XSTATE_CONTRACT_ID);
        logger.write_str(" owners=10,11 saves=");
        logger.write_decimal_u64(u64::from(proof.save_count));
        logger.write_str(" restores=");
        logger.write_decimal_u64(u64::from(proof.restore_count));
        logger.write_str(" xstate_bv_a=");
        logger.write_hex_u64(proof.context_a_xstate_bv);
        logger.write_str(" xstate_bv_b=");
        logger.write_hex_u64(proof.context_b_xstate_bv);
        logger.write_str(" match_a=");
        logger.write_decimal_u64(u64::from(proof.context_a_match));
        logger.write_str(" match_b=");
        logger.write_decimal_u64(u64::from(proof.context_b_match));
        logger.write_str(" scheduler_lock=1 interrupts=0 same_cpu=1 kernel_simd=0\n");
        logger.write_str("POOLEOS:KERNEL:XSTATE-CLEAR PASS contract=");
        logger.write_str(XSTATE_CONTRACT_ID);
        logger.write_str(" canonical_xmm0_zero=");
        logger.write_decimal_u64(u64::from(proof.canonical_xmm0_zero));
        logger.write_str(" image_zero_bytes=");
        logger.write_decimal_u64(u64::from(proof.context_image_zero_bytes));
        logger.write_str(" unexpected_nm=");
        logger.write_decimal_u64(u64::from(proof.unexpected_nm_count));
        logger.write_str(" all_selected_components=canonical_image kernel_simd_policy=forbidden\n");
        logger.write_str("POOLEOS:KERNEL:XSTATE-RESULT PASS contract=");
        logger.write_str(XSTATE_CONTRACT_ID);
        logger.write_str(
            " profile=epyc_rome_v4_x87_sse bsp=1 writes=3 signatures=0 authority=0 actions=0 scheduler=0 smp=0 target=0 terminal=halt\n",
        );
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::XstateException {
        // SAFETY: PKXFER1 transferred once at CPL0 with IF/DF clear. PKXEXC1 first
        // reproduces the complete parent PKXSTATE1 configuration and ownership proof.
        let proof = match unsafe { arch::x86_64::run_xstate_policy() } {
            Ok(value) => value,
            Err(error) => {
                let mut logger = EarlyLogger::new(BootSink {
                    serial: &mut serial,
                    debugcon: &mut debugcon,
                    ring: &EARLY_RING,
                });
                logger.write_bytes(&XSTATE_EXCEPTION_PARENT_ERROR_PREFIX);
                logger.write_str(error.label());
                logger.write_str("\n");
                poole_kernel_emergency_panic(PanicCode::XstateException as u32)
            }
        };
        if validate_xstate_proof(&proof).is_err() {
            poole_kernel_emergency_panic(PanicCode::XstateException as u32);
        }
        // SAFETY: the opt-in selector owns the BSP descriptor statics until terminal halt.
        let descriptor_state =
            unsafe { arch::x86_64::install_xstate_exception_descriptor_tables(stack_top as u64) };
        if validate_xstate_exception_descriptor_state(&descriptor_state).is_err() {
            poole_kernel_emergency_panic(PanicCode::XstateException as u32);
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
            logger.write_bytes(&XSTATE_EXCEPTION_SETUP_PREFIX);
            logger.write_str(XSTATE_EXCEPTION_CONTRACT_ID);
            logger.write_str(" parent=PKXSTATE1 selector=6 bsp=1 gates=");
            logger.write_decimal_u64(u64::from(descriptor_state.installed_gate_count));
            logger.write_str(" vectors=7,16,19 ist=1 xcr0=");
            logger.write_hex_u64(proof.policy.selected_xcr0);
            logger.write_str(" cr0=");
            logger.write_hex_u64(proof.policy.cr0);
            logger.write_str(" cr4=");
            logger.write_hex_u64(proof.policy.cr4);
            logger.write_str(" parent_control_writes=3 exceptions_masked_default=1 if=0\n");
            logger.write_bytes(&XSTATE_EXCEPTION_ARM_MARKER);
        }
        // SAFETY: vector 16 is installed; the helper unmask is confined to the owned x87 state.
        unsafe { arch::x86_64::trigger_x87_exception() };
        // SAFETY: vector 19 is installed; the helper unmask is confined to the owned SSE state.
        unsafe { arch::x86_64::trigger_simd_exception() };
        if XSTATE_EXCEPTION_RETURN_COUNT.load(Ordering::Acquire) != 2 {
            let (mxcsr, cr4) = arch::x86_64::observe_simd_exception_diagnostic();
            let mut logger = EarlyLogger::new(BootSink {
                serial: &mut serial,
                debugcon: &mut debugcon,
                ring: &EARLY_RING,
            });
            logger.write_bytes(&XSTATE_EXCEPTION_SIMD_DELIVERY_ERROR_PREFIX);
            logger.write_decimal_u64(u64::from(
                XSTATE_EXCEPTION_RETURN_COUNT.load(Ordering::Acquire),
            ));
            logger.write_str(" mxcsr=");
            logger.write_hex_u64(u64::from(mxcsr));
            logger.write_str(" cr4=");
            logger.write_hex_u64(cr4);
            logger.write_str("\n");
            poole_kernel_emergency_panic(PanicCode::XstateException as u32);
        }
        {
            let mut logger = EarlyLogger::new(BootSink {
                serial: &mut serial,
                debugcon: &mut debugcon,
                ring: &EARLY_RING,
            });
            logger.write_bytes(&XSTATE_EXCEPTION_NM_ARM_MARKER);
        }
        // SAFETY: this terminal helper performs the fourth privileged configuration write,
        // then executes FNOP at the exact exported #NM origin and cannot return.
        unsafe { arch::x86_64::trigger_device_not_available_rejection() }
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
        DevelopmentTrapScenario::CpuPolicy => {
            poole_kernel_emergency_panic(PanicCode::TransferState as u32)
        }
        DevelopmentTrapScenario::XstatePolicy => {
            poole_kernel_emergency_panic(PanicCode::XstatePolicy as u32)
        }
        DevelopmentTrapScenario::XstateException => {
            poole_kernel_emergency_panic(PanicCode::XstateException as u32)
        }
        DevelopmentTrapScenario::PrivilegeMsrPolicy => {
            poole_kernel_emergency_panic(PanicCode::PrivilegeMsrPolicy as u32)
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
    if scenario == DevelopmentTrapScenario::XstateException {
        dispatch_xstate_exception(frame, depth);
        return;
    }
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

fn dispatch_xstate_exception(frame: &mut TrapFrame, depth: u32) {
    let (kind, fault_rip, resume_rip, transition, sampled, injected) = match frame.vector {
        16 => {
            // SAFETY: vector 16 runs with TS clear and the PKXEXC1 handler owns x87 state.
            let value = unsafe { arch::x86_64::recover_x87_exception() };
            (
                XstateExceptionKind::X87Invalid,
                arch::x86_64::x87_exception_fault_address(),
                arch::x86_64::x87_exception_resume_address(),
                value,
                true,
                false,
            )
        }
        19 => {
            // SAFETY: vector 19 runs with TS clear and the PKXEXC1 handler owns SSE state.
            let value = unsafe { arch::x86_64::recover_simd_exception() };
            (
                XstateExceptionKind::SimdInvalid,
                arch::x86_64::simd_exception_fault_address(),
                arch::x86_64::simd_exception_resume_address(),
                value,
                true,
                false,
            )
        }
        7 => {
            let (cr0, cr4) = arch::x86_64::observe_xstate_control_state();
            (
                XstateExceptionKind::DeviceNotAvailable,
                arch::x86_64::device_not_available_fault_address(),
                arch::x86_64::device_not_available_fault_address(),
                arch::x86_64::XstateExceptionTransition {
                    cr0,
                    cr4,
                    fcw_before: 0,
                    fsw_before: 0,
                    mxcsr_before: 0,
                    fcw_after: 0,
                    fsw_after: 0,
                    mxcsr_after: 0,
                },
                false,
                true,
            )
        }
        _ => poole_kernel_emergency_panic(PanicCode::XstateException as u32),
    };
    let observation = TrapObservation {
        vector: frame.vector,
        error_code: frame.error_code,
        rip: frame.rip,
        code_selector: frame.code_selector,
        rflags: frame.rflags,
        saved_rsp: frame.rsp,
        data_selector: frame.data_selector,
        cr2: 0,
        handler_rsp: frame as *mut TrapFrame as u64,
        depth,
    };
    let state = XstateExceptionState {
        kind,
        trap: observation,
        expected_fault_rip: fault_rip,
        expected_resume_rip: resume_rip,
        ist_bottom: IST1_BOTTOM.load(Ordering::Acquire),
        ist_top: IST1_TOP.load(Ordering::Acquire),
        cr0: transition.cr0,
        cr4: transition.cr4,
        fcw_before: transition.fcw_before,
        fsw_before: transition.fsw_before,
        mxcsr_before: transition.mxcsr_before,
        fcw_after: transition.fcw_after,
        fsw_after: transition.fsw_after,
        mxcsr_after: transition.mxcsr_after,
        state_sampled: sampled,
        test_only_ts_injected: injected,
    };
    let disposition = validate_exception_state(&state)
        .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::XstateException as u32));

    // SAFETY: the bounded ring-0 diagnostic path uses only the fixed COM1 probe with IF clear.
    let mut serial = unsafe { Com1::initialize() };
    let mut debugcon = DebugCon::new();
    let mut logger = EarlyLogger::new(BootSink {
        serial: &mut serial,
        debugcon: &mut debugcon,
        ring: &EARLY_RING,
    });
    logger.write_str("POOLEOS:KERNEL:XSTATE-EXCEPTION-ENTER PASS contract=");
    logger.write_str(XSTATE_EXCEPTION_CONTRACT_ID);
    logger.write_str(" kind=");
    logger.write_str(kind.label());
    logger.write_str(" vector=");
    logger.write_decimal_u64(frame.vector);
    logger.write_str(" error=");
    logger.write_hex_u64(frame.error_code);
    logger.write_str(" depth=");
    logger.write_decimal_u64(u64::from(depth));
    logger.write_str(" ist=1\n");

    match disposition {
        TrapDisposition::ResumeAt(address) => {
            logger.write_str("POOLEOS:KERNEL:XSTATE-EXCEPTION-STATE PASS contract=");
            logger.write_str(XSTATE_EXCEPTION_CONTRACT_ID);
            logger.write_str(" kind=");
            logger.write_str(kind.label());
            logger.write_str(" fcw_before=");
            logger.write_hex_u64(u64::from(transition.fcw_before));
            logger.write_str(" fsw_before=");
            logger.write_hex_u64(u64::from(transition.fsw_before));
            logger.write_str(" mxcsr_before=");
            logger.write_hex_u64(u64::from(transition.mxcsr_before));
            logger.write_str(" fcw_after=");
            logger.write_hex_u64(u64::from(transition.fcw_after));
            logger.write_str(" fsw_after=");
            logger.write_hex_u64(u64::from(transition.fsw_after));
            logger.write_str(" mxcsr_after=");
            logger.write_hex_u64(u64::from(transition.mxcsr_after));
            logger.write_str(" state_sampled=1\n");
            frame.rip = address;
            let returned = XSTATE_EXCEPTION_RETURN_COUNT.fetch_add(1, Ordering::AcqRel) + 1;
            logger.write_str("POOLEOS:KERNEL:XSTATE-EXCEPTION-RETURN PASS contract=");
            logger.write_str(XSTATE_EXCEPTION_CONTRACT_ID);
            logger.write_str(" vector=");
            logger.write_decimal_u64(frame.vector);
            logger.write_str(" resume=exact returned=");
            logger.write_decimal_u64(u64::from(returned));
            logger.write_str(" recovery_write=1\n");
            TRAP_DEPTH.store(0, Ordering::Release);
        }
        TrapDisposition::Halt => {
            logger.write_bytes(&XSTATE_EXCEPTION_NM_REJECT_MARKER);
            logger.write_bytes(&XSTATE_EXCEPTION_RESULT_MARKER);
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
