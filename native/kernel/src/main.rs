#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

mod arch {
    pub mod x86_64;
}

use core::panic::PanicInfo;
use core::ptr::{read_volatile, write_volatile};
use core::sync::atomic::{AtomicU32, AtomicU64, Ordering};

use arch::x86_64::{Com1, DebugCon, TrapFrame, halt_forever};
use poolekernel::{
    BUILD_ID, ByteSink, CPU_POLICY_CONTRACT_ID, DevelopmentTrapScenario, EARLY_LOG_CAPACITY,
    EarlyLogger, EarlyRing, Framebuffer, PanicCode, PanicDisposition, PanicState,
    TRANSFER_CONTRACT_ID, TRAP_CONTRACT_ID, TrapDisposition, TrapError, TrapExpectation,
    TrapObservation, XSTATE_EXCEPTION_CONTRACT_ID,
    active_virtual_memory::{
        self, ActiveHardware, run_profile as run_active_virtual_memory_profile,
    },
    decode_cpu_identity,
    physical_memory::{Zone, run_profile as run_physical_memory_profile},
    privilege_msr::{machine_check_bank_count, machine_check_ctl_present, validate_snapshot},
    revalidation, validate_cpu_policy_snapshot, validate_descriptor_state,
    validate_development_handoff, validate_entry_envelope, validate_handoff,
    validate_runtime_state, validate_trap_observation, validate_xstate_exception_descriptor_state,
    virtual_memory::{self, TableMemory, run_profile as run_virtual_memory_profile},
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

macro_rules! pkpmm_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkpmm_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pkpmm_fragment!(
    PKPMM_DENIED,
    b"POOLEOS:KERNEL:PMM-DENIED contract=PKPMM1 reason="
);
pkpmm_fragment!(
    PKPMM_DENIED_TAIL,
    b" physical_writes=0 mappings=0 reclaim=0 authority=0 actions=0 terminal=panic\n"
);
pkpmm_fragment!(
    PKPMM_EARLY,
    b"POOLEOS:KERNEL:PMM-EARLY PASS contract=PKPMM1 selector=8 stack=validated_by_wrapper serial=initialized\n"
);
pkpmm_fragment!(
    PKPMM_STAGE,
    b"POOLEOS:KERNEL:PMM-STAGE PASS contract=PKPMM1 stage="
);
pkpmm_fragment!(
    PKPMM_MAP,
    b"POOLEOS:KERNEL:PMM-MAP PASS contract=PKPMM1 entries="
);
pkpmm_fragment!(PKPMM_USABLE, b" usable_pages=");
pkpmm_fragment!(PKPMM_BOOT_RECLAIMABLE, b" boot_reclaimable_pages=");
pkpmm_fragment!(PKPMM_LOADER_RESERVED, b" loader_reserved_pages=");
pkpmm_fragment!(PKPMM_NULL_GUARD, b" null_guard_pages=");
pkpmm_fragment!(
    PKPMM_ZONES,
    b"\nPOOLEOS:KERNEL:PMM-ZONES PASS contract=PKPMM1 dma_source="
);
pkpmm_fragment!(PKPMM_DMA_MANAGED, b" dma_managed=");
pkpmm_fragment!(PKPMM_DMA32_SOURCE, b" dma32_source=");
pkpmm_fragment!(PKPMM_DMA32_MANAGED, b" dma32_managed=");
pkpmm_fragment!(PKPMM_NORMAL_SOURCE, b" normal_source=");
pkpmm_fragment!(PKPMM_NORMAL_MANAGED, b" normal_managed=");
pkpmm_fragment!(PKPMM_EXTENTS, b" extents=");
pkpmm_fragment!(PKPMM_LARGEST_DMA, b" largest_dma=");
pkpmm_fragment!(PKPMM_LARGEST_DMA32, b" largest_dma32=");
pkpmm_fragment!(PKPMM_LARGEST_NORMAL, b" largest_normal=");
pkpmm_fragment!(
    PKPMM_OWNERSHIP,
    b"\nPOOLEOS:KERNEL:PMM-OWNERSHIP PASS contract=PKPMM1 kernel_base="
);
pkpmm_fragment!(PKPMM_KERNEL_PAGES, b" kernel_pages=");
pkpmm_fragment!(PKPMM_HANDOFF_BASE, b" handoff_base=");
pkpmm_fragment!(PKPMM_HANDOFF_PAGES, b" handoff_pages=");
pkpmm_fragment!(PKPMM_ROOT, b" root=");
pkpmm_fragment!(PKPMM_PROTECTED, b" protected=1\n");
pkpmm_fragment!(PKPMM_EXERCISE_DENIED, b"POOLEOS:KERNEL:PMM-DENIED contract=PKPMM1 reason=exercise_invariant physical_writes=0 mappings=0 reclaim=0 authority=0 actions=0 terminal=panic\n");
pkpmm_fragment!(
    PKPMM_EXERCISE,
    b"POOLEOS:KERNEL:PMM-EXERCISE PASS contract=PKPMM1 allocations="
);
pkpmm_fragment!(PKPMM_FREES, b" frees=");
pkpmm_fragment!(PKPMM_DMA_START, b" dma_start=");
pkpmm_fragment!(PKPMM_DMA32_START, b" dma32_start=");
pkpmm_fragment!(PKPMM_DOUBLE_FREE, b" double_free_rejected=");
pkpmm_fragment!(PKPMM_QUOTA, b" quota_rejected=");
pkpmm_fragment!(PKPMM_UNAVAILABLE, b" unavailable_rejected=");
pkpmm_fragment!(PKPMM_METADATA_POISON, b" metadata_poison=");
pkpmm_fragment!(PKPMM_COALESCES, b" coalesces=");
pkpmm_fragment!(
    PKPMM_RESULT,
    b"\nPOOLEOS:KERNEL:PMM-RESULT PASS contract=PKPMM1 profile=qemu64_tier0 managed_pages="
);
pkpmm_fragment!(PKPMM_RESULT_TAIL, b" allocated_pages=0 physical_writes=0 mappings=0 reclaim=0 concurrency=0 signatures=0 authority=0 actions=0 terminal=halt\n");

macro_rules! pkvm_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkvm_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pkvm_fragment!(
    PKVM_DENIED,
    b"POOLEOS:KERNEL:VM-DENIED contract=PKVM1 reason="
);
pkvm_fragment!(
    PKVM_DENIED_TAIL,
    b" effects=unqualified authority=0 actions=0 terminal=panic\n"
);
pkvm_fragment!(
    PKVM_EARLY,
    b"POOLEOS:KERNEL:VM-EARLY PASS contract=PKVM1 selector=9 stack=validated_by_wrapper serial=initialized\n"
);
pkvm_fragment!(
    PKVM_STAGE,
    b"POOLEOS:KERNEL:VM-STAGE PASS contract=PKVM1 stage="
);
pkvm_fragment!(
    PKVM_LAYOUT,
    b"POOLEOS:KERNEL:VM-LAYOUT PASS contract=PKVM1 canonical_bits=48 null_guard_end=0x0000000000010000 user_end=0x0000800000000000 kernel_start=0xFFFF800000000000 direct_start=0xFFFF900000000000 direct_end=0xFFFFD00000000000 temp_start=0xFFFFFFFF80150000 temp_end=0xFFFFFFFF80151000 kernel_image_start=0xFFFFFFFF80000000 kernel_image_end=0xFFFFFFFFC0000000 window_start=0x0000000040000000 window_pages=512\n"
);
pkvm_fragment!(
    PKVM_TABLES,
    b"POOLEOS:KERNEL:VM-TABLES PASS contract=PKVM1 root="
);
pkvm_fragment!(PKVM_TABLE_GENERATION, b" table_generation=");
pkvm_fragment!(PKVM_DATA, b" data=");
pkvm_fragment!(PKVM_DATA_GENERATION, b" data_generation=");
pkvm_fragment!(
    PKVM_TABLES_TAIL,
    b" table_pages=4 materialized=4 temporary_verified=4 root_active=0\n"
);
pkvm_fragment!(
    PKVM_TRANSLATION,
    b"POOLEOS:KERNEL:VM-TRANSLATION PASS contract=PKVM1 mapped_physical="
);
pkvm_fragment!(
    PKVM_TRANSLATION_TAIL,
    b" mapped_permissions=rw_nx_user protected_permissions=rx_user cache=write_back page_bytes=4096\n"
);
pkvm_fragment!(
    PKVM_TRANSACTION,
    b"POOLEOS:KERNEL:VM-TRANSACTION PASS contract=PKVM1 maps=2 protects=1 unmaps=2 inactive_receipts=2 cache_alias_rejected=1 wx_rejected=1 premature_reuse_rejected=1 rollback_controls=host_verified\n"
);
pkvm_fragment!(
    PKVM_RESULT,
    b"POOLEOS:KERNEL:VM-RESULT PASS contract=PKVM1 profile=qemu64_tier0 root_released=1 data_released=1 allocated_pages="
);
pkvm_fragment!(PKVM_PHYSICAL_WRITES, b" physical_writes=");
pkvm_fragment!(PKVM_TEMPORARY_PTE_WRITES, b" temporary_pte_writes=");
pkvm_fragment!(PKVM_ALLOCATIONS, b" allocations=");
pkvm_fragment!(PKVM_FREES, b" frees=");
pkvm_fragment!(PKVM_INVLPG, b" active_cr3_writes=0 invlpg=");
pkvm_fragment!(
    PKVM_RESULT_TAIL,
    b" shootdown=0 huge_pages=0 cow=0 user_faults=0 pager=0 heap=0 smp=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n"
);

macro_rules! pkavm_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkavm_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pkavm_fragment!(
    PKAVM_DENIED,
    b"POOLEOS:KERNEL:ACTIVE-VM-DENIED contract=PKVM2 reason="
);
pkavm_fragment!(
    PKAVM_DENIED_TAIL,
    b" effects=fail_closed authority=0 actions=0 terminal=panic\n"
);
pkavm_fragment!(
    PKAVM_EARLY,
    b"POOLEOS:KERNEL:ACTIVE-VM-EARLY PASS contract=PKVM2 selector=10 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n"
);
pkavm_fragment!(
    PKAVM_STAGE,
    b"POOLEOS:KERNEL:ACTIVE-VM-STAGE PASS contract=PKVM2 stage="
);
pkavm_fragment!(
    PKAVM_LAYOUT,
    b"POOLEOS:KERNEL:ACTIVE-VM-LAYOUT PASS contract=PKVM2 canonical_bits=48 direct_start=0xFFFF900000000000 direct_end=0xFFFFD00000000000 user_start=0x0000000040000000 page_bytes=4096 table_pages=8 owned_pages=9\n"
);
pkavm_fragment!(
    PKAVM_CANDIDATE,
    b"POOLEOS:KERNEL:ACTIVE-VM-CANDIDATE PASS contract=PKVM2 original_root="
);
pkavm_fragment!(PKAVM_ROOT, b" candidate_root=");
pkavm_fragment!(PKAVM_TABLE_GENERATION, b" table_generation=");
pkavm_fragment!(PKAVM_DATA, b" data=");
pkavm_fragment!(PKAVM_DATA_GENERATION, b" data_generation=");
pkavm_fragment!(PKAVM_DIRECT_FIRST, b" direct_first=");
pkavm_fragment!(PKAVM_DIRECT_LAST, b" direct_last=");
pkavm_fragment!(
    PKAVM_CANDIDATE_TAIL,
    b" inherited_kernel=exact guarded_stack=exact handoff=exact bootstrap_alias_revoked=1 root_active=0\n"
);
pkavm_fragment!(
    PKAVM_ACTIVATION,
    b"POOLEOS:KERNEL:ACTIVE-VM-ACTIVATION PASS contract=PKVM2 cr3_writes="
);
pkavm_fragment!(
    PKAVM_ACTIVATION_TAIL,
    b" candidate_readback=exact original_restore=exact rollback_control=host_verified bsp=1 smp=0\n"
);
pkavm_fragment!(
    PKAVM_INVALIDATION,
    b"POOLEOS:KERNEL:ACTIVE-VM-INVALIDATION PASS contract=PKVM2 local_invlpg="
);
pkavm_fragment!(PKAVM_RECEIPTS, b" active_receipts=");
pkavm_fragment!(PKAVM_PROBE, b" probe=");
pkavm_fragment!(
    PKAVM_INVALIDATION_TAIL,
    b" protect=1 user_unmap=1 direct_unmap=1 stale_root_rejected=host premature_reuse_rejected=1 shootdown=0\n"
);
pkavm_fragment!(
    PKAVM_RESULT,
    b"POOLEOS:KERNEL:ACTIVE-VM-RESULT PASS contract=PKVM2 profile=qemu64_tier0 root_released=1 data_released=1 allocated_pages="
);
pkavm_fragment!(PKAVM_PHYSICAL_WRITES, b" physical_writes=");
pkavm_fragment!(PKAVM_TEMPORARY_WRITES, b" temporary_pte_writes=");
pkavm_fragment!(PKAVM_BOOTSTRAP_INVLPG, b" bootstrap_invlpg=");
pkavm_fragment!(PKAVM_ALLOCATIONS, b" allocations=");
pkavm_fragment!(PKAVM_FREES, b" frees=");
pkavm_fragment!(
    PKAVM_RESULT_TAIL,
    b" active_cr3_writes=2 active_invlpg=3 shootdown=0 ring3=0 huge_pages=0 pcid=0 cow=0 user_faults=0 pager=0 heap=0 smp=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n"
);

macro_rules! pkentry_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkentry_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pkentry_fragment!(PKENTRY_ENTRY, b"POOLEOS:KERNEL:ENTRY PASS contract=");
pkentry_fragment!(PKENTRY_TRANSFER, b" transfer_contract=");
pkentry_fragment!(PKENTRY_BUILD, b" build=");
pkentry_fragment!(PKENTRY_COUNT, b" entry_count=");
pkentry_fragment!(PKENTRY_SERIAL, b" serial=");
pkentry_fragment!(PKENTRY_PRESENT, b"present");
pkentry_fragment!(PKENTRY_ABSENT, b"absent");
pkentry_fragment!(PKENTRY_STATE, b"\nPOOLEOS:KERNEL:STATE PASS handoff=");
pkentry_fragment!(PKENTRY_BYTES, b" bytes=");
pkentry_fragment!(PKENTRY_RUNTIME, b" entry=");
pkentry_fragment!(PKENTRY_STACK, b" stack_top=");
pkentry_fragment!(PKENTRY_ROOT, b" root=");
pkentry_fragment!(PKENTRY_CR3, b" cr3=");
pkentry_fragment!(PKENTRY_RFLAGS, b" rflags_if=0 rflags_df=0\n");
pkentry_fragment!(
    PKENTRY_PBP1,
    b"POOLEOS:KERNEL:PBP1 PASS profile=development records="
);
pkentry_fragment!(PKENTRY_ARTIFACTS, b" artifacts=");
pkentry_fragment!(PKENTRY_PROFILE, b" production_profile_valid=0\n");
pkentry_fragment!(
    PKENTRY_REVALIDATION,
    b"POOLEOS:KERNEL:PKREVAL PASS contract="
);
pkentry_fragment!(PKENTRY_FILES, b" files=");
pkentry_fragment!(PKENTRY_PARSERS, b" parsers=");
pkentry_fragment!(PKENTRY_MANIFEST_BYTES, b" manifest_bytes=");
pkentry_fragment!(PKENTRY_RETAINED_BYTES, b" retained_bytes=");
pkentry_fragment!(PKENTRY_RETAINED_SHA, b" retained_set_sha256=");
pkentry_fragment!(PKENTRY_POLICY_SHA, b" policy_sha256=");
pkentry_fragment!(PKENTRY_STATE_SHA, b" state_sha256=");
pkentry_fragment!(PKENTRY_DENIAL, b" denial=");
pkentry_fragment!(PKENTRY_AUTHORITY, b" authority=");
pkentry_fragment!(PKENTRY_ACTIONS, b" actions=");
pkentry_fragment!(PKENTRY_WRITES, b" writes=");
pkentry_fragment!(PKENTRY_NEWLINE, b"\n");
pkentry_fragment!(PKENTRY_FRAMEBUFFER, b"POOLEOS KERNEL ENTRY\nBUILD ");
pkentry_fragment!(PKENTRY_FRAMEBUFFER_TAIL, b"\nPBP1 VALID\n");
pkentry_fragment!(PKENTRY_TRANSFER_DENIED, b"POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0\n");

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

struct ActivePhysicalReader;

impl poole_kmap::TableReader for ActivePhysicalReader {
    fn read_entry(&self, table_address: u64, index: usize) -> Result<u64, poole_kmap::Error> {
        if table_address == 0
            || !table_address.is_multiple_of(poole_kmap::PAGE_SIZE)
            || table_address > usize::MAX as u64
            || index >= poole_kmap::TABLE_ENTRIES
        {
            return Err(poole_kmap::Error::TranslationAddress);
        }
        let pointer = (table_address as usize as *const u64).wrapping_add(index);
        // SAFETY: PKVM1 uses this reader only after PKENTRY1 validates the active
        // retained root; PKMAP2 keeps its four retained page-table frames identity-mapped.
        Ok(unsafe { read_volatile(pointer) })
    }
}

struct BootstrapTableMemory {
    active_root: u64,
    active_leaf_table: u64,
    physical_address_bits: u8,
    mapped_physical: Option<u64>,
    writes: u64,
    temporary_pte_writes: u64,
    invalidations: u64,
}

impl BootstrapTableMemory {
    const TEMPORARY_LEAF_INDEX: usize = 336;
    const TEMPORARY_ENTRY_FLAGS: u64 = (1 << 0) | (1 << 1) | (1 << 63);
    const PHYSICAL_MASK_52: u64 = 0x000f_ffff_ffff_f000;

    fn new(active_root: u64, physical_address_bits: u8) -> Result<Self, virtual_memory::Error> {
        if active_root == 0 || !active_root.is_multiple_of(poole_kmap::PAGE_SIZE) {
            return Err(virtual_memory::Error::BootstrapRoot);
        }
        let active_leaf_table = active_root + 3 * poole_kmap::PAGE_SIZE;
        let reader = ActivePhysicalReader;
        for address in [
            active_leaf_table,
            active_leaf_table + poole_kmap::PAGE_SIZE - 1,
        ] {
            let translation =
                poole_kmap::translate(&reader, active_root, address, physical_address_bits)
                    .map_err(|_| virtual_memory::Error::BootstrapRetainedIdentity)?;
            if translation.physical_address != address || !translation.writable {
                return Err(virtual_memory::Error::BootstrapRetainedIdentity);
            }
        }
        // SAFETY: the loop above proves that the retained PKMAP2 leaf table is
        // identity-mapped and writable through its physical address.
        let value = unsafe {
            read_volatile(
                (active_leaf_table as usize as *const u64).wrapping_add(Self::TEMPORARY_LEAF_INDEX),
            )
        };
        if value != 0 {
            return Err(virtual_memory::Error::BootstrapLeafOccupied);
        }
        Ok(Self {
            active_root,
            active_leaf_table,
            physical_address_bits,
            mapped_physical: None,
            writes: 0,
            temporary_pte_writes: 0,
            invalidations: 0,
        })
    }

    fn target_pointer(index: usize) -> Result<*mut u64, virtual_memory::Error> {
        if index >= poole_kmap::TABLE_ENTRIES {
            return Err(virtual_memory::Error::MemoryAccess);
        }
        Ok((virtual_memory::TEMPORARY_MAP_START as usize as *mut u64).wrapping_add(index))
    }

    fn leaf_pointer(&self) -> *mut u64 {
        (self.active_leaf_table as usize as *mut u64).wrapping_add(Self::TEMPORARY_LEAF_INDEX)
    }

    fn invalidate(&mut self) {
        // SAFETY: selectors 9 and 10 run at CPL0 on the BSP with interrupts disabled;
        // the operand is the single PKMAP2 bootstrap temporary leaf.
        unsafe { arch::x86_64::invalidate_page(virtual_memory::TEMPORARY_MAP_START) };
        self.invalidations += 1;
    }

    fn ensure_mapped(&mut self, physical_address: u64) -> Result<(), virtual_memory::Error> {
        if physical_address == 0
            || !physical_address.is_multiple_of(poole_kmap::PAGE_SIZE)
            || physical_address & !Self::PHYSICAL_MASK_52 != 0
        {
            return Err(virtual_memory::Error::BootstrapTargetAddress);
        }
        if self.mapped_physical == Some(physical_address) {
            return Ok(());
        }
        let leaf = self.leaf_pointer();
        // SAFETY: new() proves the private PKMAP2 leaf table is identity-mapped.
        let observed = unsafe { read_volatile(leaf) };
        match self.mapped_physical {
            Some(current)
                if observed & Self::PHYSICAL_MASK_52 == current
                    && observed & Self::TEMPORARY_ENTRY_FLAGS == Self::TEMPORARY_ENTRY_FLAGS =>
            {
                // SAFETY: the selected VM profile exclusively owns the installed leaf.
                unsafe { write_volatile(leaf, 0) };
                self.temporary_pte_writes += 1;
                self.invalidate();
            }
            None if observed == 0 => {}
            _ => return Err(virtual_memory::Error::BootstrapLeafState),
        }
        // SAFETY: the target frame is generation-owned by PKVM1 and this leaf is
        // outside kernel, stack, guard, and handoff mappings.
        unsafe { write_volatile(leaf, physical_address | Self::TEMPORARY_ENTRY_FLAGS) };
        self.temporary_pte_writes += 1;
        self.invalidate();
        self.mapped_physical = Some(physical_address);
        let translation = poole_kmap::translate(
            &ActivePhysicalReader,
            self.active_root,
            virtual_memory::TEMPORARY_MAP_START,
            self.physical_address_bits,
        )
        .map_err(|_| virtual_memory::Error::BootstrapTranslation)?;
        if translation.physical_address != physical_address
            || !translation.writable
            || translation.executable
            || translation.user
        {
            return Err(virtual_memory::Error::BootstrapTranslation);
        }
        Ok(())
    }
}

impl TableMemory for BootstrapTableMemory {
    fn prepare_page(&mut self, physical_address: u64) -> Result<(), virtual_memory::Error> {
        self.ensure_mapped(physical_address)
    }

    fn read_entry(
        &mut self,
        table_address: u64,
        index: usize,
    ) -> Result<u64, virtual_memory::Error> {
        self.ensure_mapped(table_address)?;
        let pointer = Self::target_pointer(index)?;
        // SAFETY: ensure_mapped proves the target table occupies the temporary leaf.
        Ok(unsafe { read_volatile(pointer) })
    }

    fn write_entry(
        &mut self,
        table_address: u64,
        index: usize,
        value: u64,
    ) -> Result<(), virtual_memory::Error> {
        self.ensure_mapped(table_address)?;
        let pointer = Self::target_pointer(index)?;
        // SAFETY: PKVM1 owns the PMM generation for the currently mapped table page.
        unsafe { write_volatile(pointer, value) };
        self.writes = self
            .writes
            .checked_add(1)
            .ok_or(virtual_memory::Error::MemoryAccess)?;
        Ok(())
    }

    fn finish(&mut self) -> Result<(), virtual_memory::Error> {
        let current = self
            .mapped_physical
            .ok_or(virtual_memory::Error::BootstrapLeafState)?;
        let leaf = self.leaf_pointer();
        // SAFETY: the selected VM profile exclusively owns the installed temporary leaf.
        let observed = unsafe { read_volatile(leaf) };
        if observed & Self::PHYSICAL_MASK_52 != current
            || observed & Self::TEMPORARY_ENTRY_FLAGS != Self::TEMPORARY_ENTRY_FLAGS
        {
            return Err(virtual_memory::Error::BootstrapLeafState);
        }
        // SAFETY: clearing the owned leaf revokes the final temporary alias.
        unsafe { write_volatile(leaf, 0) };
        self.temporary_pte_writes += 1;
        self.invalidate();
        self.mapped_physical = None;
        if poole_kmap::translate(
            &ActivePhysicalReader,
            self.active_root,
            virtual_memory::TEMPORARY_MAP_START,
            self.physical_address_bits,
        ) != Err(poole_kmap::Error::TranslationMissing)
        {
            return Err(virtual_memory::Error::BootstrapRevocation);
        }
        Ok(())
    }

    fn physical_write_count(&self) -> u64 {
        self.writes
    }

    fn temporary_pte_write_count(&self) -> u64 {
        self.temporary_pte_writes
    }

    fn hardware_invalidation_count(&self) -> u64 {
        self.invalidations
    }
}

struct LiveActiveHardware;

impl ActiveHardware for LiveActiveHardware {
    fn interrupts_disabled(&mut self) -> bool {
        arch::x86_64::read_rflags() & (1 << 9) == 0
    }

    fn cpu_id(&mut self) -> u32 {
        active_virtual_memory::BSP_CPU_ID
    }

    fn read_cr3(&mut self) -> u64 {
        // SAFETY: PKVM2 runs at CPL0 after PKENTRY1 validates the transfer state.
        unsafe { arch::x86_64::read_cr3() }
    }

    fn write_cr3(&mut self, value: u64) -> Result<(), active_virtual_memory::Error> {
        if value == 0 || !value.is_multiple_of(poole_handoff::PAGE_BYTES) {
            return Err(active_virtual_memory::Error::PhysicalAddress);
        }
        // SAFETY: PKVM2 audits the candidate root or supplies the exact retained root;
        // both preserve the executing high-half image and current guarded stack.
        unsafe { arch::x86_64::write_cr3(value) };
        Ok(())
    }

    fn invalidate_page(
        &mut self,
        virtual_address: u64,
    ) -> Result<(), active_virtual_memory::Error> {
        if !virtual_memory::is_canonical_48(virtual_address) {
            return Err(active_virtual_memory::Error::MemoryAccess);
        }
        // SAFETY: PKVM2 owns the current BSP root and the exact leaf transition.
        unsafe { arch::x86_64::invalidate_page(virtual_address) };
        Ok(())
    }

    fn read_u64(&mut self, virtual_address: u64) -> Result<u64, active_virtual_memory::Error> {
        if !virtual_memory::is_canonical_48(virtual_address)
            || !virtual_address.is_multiple_of(core::mem::align_of::<u64>() as u64)
            || virtual_address > usize::MAX as u64
        {
            return Err(active_virtual_memory::Error::MemoryAccess);
        }
        // SAFETY: PKVM2 supplies an audited, supervisor RW/NX direct-map address.
        Ok(unsafe { read_volatile(virtual_address as usize as *const u64) })
    }

    fn write_u64(
        &mut self,
        virtual_address: u64,
        value: u64,
    ) -> Result<(), active_virtual_memory::Error> {
        if !virtual_memory::is_canonical_48(virtual_address)
            || !virtual_address.is_multiple_of(core::mem::align_of::<u64>() as u64)
            || virtual_address > usize::MAX as u64
        {
            return Err(active_virtual_memory::Error::MemoryAccess);
        }
        // SAFETY: PKVM2 supplies an audited, supervisor RW/NX direct-map address.
        unsafe { write_volatile(virtual_address as usize as *mut u64, value) };
        Ok(())
    }

    fn read_u8(&mut self, virtual_address: u64) -> Result<u8, active_virtual_memory::Error> {
        if !virtual_memory::is_canonical_48(virtual_address) || virtual_address > usize::MAX as u64
        {
            return Err(active_virtual_memory::Error::MemoryAccess);
        }
        // SAFETY: PKVM2 supplies its one audited user-window probe address.
        Ok(unsafe { read_volatile(virtual_address as usize as *const u8) })
    }

    fn write_u8(
        &mut self,
        virtual_address: u64,
        value: u8,
    ) -> Result<(), active_virtual_memory::Error> {
        if !virtual_memory::is_canonical_48(virtual_address) || virtual_address > usize::MAX as u64
        {
            return Err(active_virtual_memory::Error::MemoryAccess);
        }
        // SAFETY: PKVM2 writes only while the audited user-window leaf is writable.
        unsafe { write_volatile(virtual_address as usize as *mut u8, value) };
        Ok(())
    }
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

#[inline(never)]
fn log_physical_memory_stage(serial: &mut Com1, debugcon: &mut DebugCon, stage: u64) {
    let mut logger = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    logger.write_bytes(&PKPMM_STAGE);
    logger.write_decimal_u64(stage);
    logger.write_bytes(&PKENTRY_NEWLINE);
}

#[inline(never)]
fn log_virtual_memory_stage(serial: &mut Com1, debugcon: &mut DebugCon, stage: u64) {
    let mut logger = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    logger.write_bytes(&PKVM_STAGE);
    logger.write_decimal_u64(stage);
    logger.write_bytes(&PKENTRY_NEWLINE);
}

#[inline(never)]
fn log_active_virtual_memory_stage(serial: &mut Com1, debugcon: &mut DebugCon, stage: u64) {
    let mut logger = EarlyLogger::new(BootSink {
        serial,
        debugcon,
        ring: &EARLY_RING,
    });
    logger.write_bytes(&PKAVM_STAGE);
    logger.write_decimal_u64(stage);
    logger.write_bytes(&PKENTRY_NEWLINE);
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
        0x1010 => PanicCode::PhysicalMemory,
        0x1011 => PanicCode::VirtualMemory,
        0x1012 => PanicCode::ActiveVirtualMemory,
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

    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKPMM_EARLY);
    }
    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKVM_EARLY);
    }
    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKAVM_EARLY);
    }

    if let Err(error) = validate_entry_envelope(handoff_address, handoff_length, magic, stack_top) {
        poole_kernel_emergency_panic(error.panic_code() as u32);
    }
    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        log_physical_memory_stage(&mut serial, &mut debugcon, 1);
    }
    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        log_virtual_memory_stage(&mut serial, &mut debugcon, 1);
    }
    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        log_active_virtual_memory_stage(&mut serial, &mut debugcon, 1);
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
    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        log_physical_memory_stage(&mut serial, &mut debugcon, 2);
    }
    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        log_virtual_memory_stage(&mut serial, &mut debugcon, 2);
    }
    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        log_active_virtual_memory_stage(&mut serial, &mut debugcon, 2);
    }
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
    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        log_physical_memory_stage(&mut serial, &mut debugcon, 3);
    }
    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        log_virtual_memory_stage(&mut serial, &mut debugcon, 3);
    }
    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        log_active_virtual_memory_stage(&mut serial, &mut debugcon, 3);
    }
    let decoded = match poole_handoff::decode(handoff) {
        Ok(value) => value,
        Err(_) => poole_kernel_emergency_panic(PanicCode::HandoffDecode as u32),
    };
    let loaded_artifacts = match decoded.record(poole_handoff::RECORD_LOADED_ARTIFACTS) {
        Some(value) => value,
        None => poole_kernel_emergency_panic(PanicCode::HandoffProfile as u32),
    };
    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        log_physical_memory_stage(&mut serial, &mut debugcon, 4);
    }
    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        log_virtual_memory_stage(&mut serial, &mut debugcon, 4);
    }
    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        log_active_virtual_memory_stage(&mut serial, &mut debugcon, 4);
    }
    // SAFETY: PKENTRY1 requires every PBP1 retained-input range to remain
    // immutable and identity-mapped until this independent revalidation ends.
    let revalidated = match unsafe { revalidation::revalidate_development_from_handoff(handoff) } {
        Ok(value) => value,
        Err(_) => poole_kernel_emergency_panic(PanicCode::TrustRevalidation as u32),
    };
    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        log_physical_memory_stage(&mut serial, &mut debugcon, 5);
    }
    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        log_virtual_memory_stage(&mut serial, &mut debugcon, 5);
    }
    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        log_active_virtual_memory_stage(&mut serial, &mut debugcon, 5);
    }

    {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKENTRY_ENTRY);
        logger.write_str(poolekernel::ENTRY_CONTRACT_ID);
        logger.write_bytes(&PKENTRY_TRANSFER);
        logger.write_str(TRANSFER_CONTRACT_ID);
        logger.write_bytes(&PKENTRY_BUILD);
        logger.write_bytes(BUILD_ID);
        logger.write_bytes(&PKENTRY_COUNT);
        logger.write_decimal_u64(u64::from(entry_count));
        logger.write_bytes(&PKENTRY_SERIAL);
        logger.write_bytes(if serial_available {
            &PKENTRY_PRESENT
        } else {
            &PKENTRY_ABSENT
        });
        logger.write_bytes(&PKENTRY_STATE);
        logger.write_hex_u64(handoff_address as u64);
        logger.write_bytes(&PKENTRY_BYTES);
        logger.write_decimal_u64(handoff_length as u64);
        logger.write_bytes(&PKENTRY_RUNTIME);
        logger.write_hex_u64(runtime_entry);
        logger.write_bytes(&PKENTRY_STACK);
        logger.write_hex_u64(stack_top as u64);
        logger.write_bytes(&PKENTRY_ROOT);
        logger.write_hex_u64(validated.core.page_table_root_physical);
        logger.write_bytes(&PKENTRY_CR3);
        logger.write_hex_u64(observed_cr3);
        logger.write_bytes(&PKENTRY_RFLAGS);
        logger.write_bytes(&PKENTRY_PBP1);
        logger.write_decimal_u64(decoded.header().record_count as u64);
        logger.write_bytes(&PKENTRY_ARTIFACTS);
        logger.write_decimal_u64(loaded_artifacts.descriptor.element_count as u64);
        logger.write_bytes(&PKENTRY_PROFILE);
        logger.write_bytes(&PKENTRY_REVALIDATION);
        logger.write_str(revalidation::CONTRACT_ID);
        logger.write_bytes(&PKENTRY_FILES);
        logger.write_decimal_u64(u64::from(revalidated.retained_file_count));
        logger.write_bytes(&PKENTRY_ARTIFACTS);
        logger.write_decimal_u64(u64::from(revalidated.artifact_count));
        logger.write_bytes(&PKENTRY_PARSERS);
        logger.write_decimal_u64(u64::from(revalidated.parser_count));
        logger.write_bytes(&PKENTRY_MANIFEST_BYTES);
        logger.write_decimal_u64(u64::from(revalidated.manifest_bytes));
        logger.write_bytes(&PKENTRY_RETAINED_BYTES);
        logger.write_decimal_u64(u64::from(revalidated.retained_file_bytes));
        logger.write_bytes(&PKENTRY_RETAINED_SHA);
        logger.write_hex_bytes(&revalidated.retained_set_sha256);
        logger.write_bytes(&PKENTRY_POLICY_SHA);
        logger.write_hex_bytes(&revalidated.policy_sha256);
        logger.write_bytes(&PKENTRY_STATE_SHA);
        logger.write_hex_bytes(&revalidated.state_sha256);
        logger.write_bytes(&PKENTRY_DENIAL);
        logger.write_str(revalidated.denial);
        logger.write_bytes(&PKENTRY_AUTHORITY);
        logger.write_decimal_u64(u64::from(revalidated.authority_grants));
        logger.write_bytes(&PKENTRY_ACTIONS);
        logger.write_decimal_u64(u64::from(revalidated.actions_authorized));
        logger.write_bytes(&PKENTRY_WRITES);
        logger.write_decimal_u64(u64::from(revalidated.state_writes));
        logger.write_bytes(&PKENTRY_NEWLINE);
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
            logger.write_bytes(&PKENTRY_FRAMEBUFFER);
            logger.write_bytes(BUILD_ID);
            logger.write_bytes(&PKENTRY_FRAMEBUFFER_TAIL);
        }
    }

    if trap_scenario == DevelopmentTrapScenario::None {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKENTRY_TRANSFER_DENIED);
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

    if trap_scenario == DevelopmentTrapScenario::PhysicalMemory {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        macro_rules! pmm_try {
            ($operation:expr) => {
                match $operation {
                    Ok(value) => value,
                    Err(error) => {
                        logger.write_bytes(&PKPMM_DENIED);
                        logger.write_str(error.label());
                        logger.write_bytes(&PKPMM_DENIED_TAIL);
                        poole_kernel_emergency_panic(PanicCode::PhysicalMemory as u32)
                    }
                }
            };
        }
        let proof = pmm_try!(run_physical_memory_profile(&decoded, validated.core));
        let initial = proof.initial;
        logger.write_bytes(&PKPMM_MAP);
        logger.write_decimal_u64(initial.memory_entry_count as u64);
        logger.write_bytes(&PKPMM_USABLE);
        logger.write_decimal_u64(initial.source_pages[poole_handoff::MEMORY_USABLE as usize]);
        logger.write_bytes(&PKPMM_BOOT_RECLAIMABLE);
        logger.write_decimal_u64(
            initial.source_pages[poole_handoff::MEMORY_BOOT_RECLAIMABLE as usize],
        );
        logger.write_bytes(&PKPMM_LOADER_RESERVED);
        logger.write_decimal_u64(
            initial.source_pages[poole_handoff::MEMORY_LOADER_RESERVED as usize],
        );
        logger.write_bytes(&PKPMM_NULL_GUARD);
        logger.write_decimal_u64(initial.null_guard_pages);
        logger.write_bytes(&PKPMM_ZONES);
        logger.write_decimal_u64(initial.source_usable_pages[Zone::Dma as usize]);
        logger.write_bytes(&PKPMM_DMA_MANAGED);
        logger.write_decimal_u64(initial.managed_pages[Zone::Dma as usize]);
        logger.write_bytes(&PKPMM_DMA32_SOURCE);
        logger.write_decimal_u64(initial.source_usable_pages[Zone::Dma32 as usize]);
        logger.write_bytes(&PKPMM_DMA32_MANAGED);
        logger.write_decimal_u64(initial.managed_pages[Zone::Dma32 as usize]);
        logger.write_bytes(&PKPMM_NORMAL_SOURCE);
        logger.write_decimal_u64(initial.source_usable_pages[Zone::Normal as usize]);
        logger.write_bytes(&PKPMM_NORMAL_MANAGED);
        logger.write_decimal_u64(initial.managed_pages[Zone::Normal as usize]);
        logger.write_bytes(&PKPMM_EXTENTS);
        logger.write_decimal_u64(initial.free_extent_count as u64);
        logger.write_bytes(&PKPMM_LARGEST_DMA);
        logger.write_decimal_u64(initial.largest_free_pages[Zone::Dma as usize]);
        logger.write_bytes(&PKPMM_LARGEST_DMA32);
        logger.write_decimal_u64(initial.largest_free_pages[Zone::Dma32 as usize]);
        logger.write_bytes(&PKPMM_LARGEST_NORMAL);
        logger.write_decimal_u64(initial.largest_free_pages[Zone::Normal as usize]);
        logger.write_bytes(&PKPMM_OWNERSHIP);
        logger.write_hex_u64(validated.core.kernel_physical_base);
        logger.write_bytes(&PKPMM_KERNEL_PAGES);
        logger.write_decimal_u64(
            validated
                .core
                .kernel_physical_size
                .div_ceil(poole_handoff::PAGE_BYTES),
        );
        logger.write_bytes(&PKPMM_HANDOFF_BASE);
        logger.write_hex_u64(validated.core.handoff_physical_base);
        logger.write_bytes(&PKPMM_HANDOFF_PAGES);
        logger.write_decimal_u64(
            validated
                .core
                .handoff_byte_count
                .div_ceil(poole_handoff::PAGE_BYTES),
        );
        logger.write_bytes(&PKPMM_ROOT);
        logger.write_hex_u64(validated.core.page_table_root_physical);
        logger.write_bytes(&PKPMM_PROTECTED);

        let final_state = proof.final_state;
        logger.write_bytes(&PKPMM_EXERCISE);
        logger.write_decimal_u64(final_state.allocation_count);
        logger.write_bytes(&PKPMM_FREES);
        logger.write_decimal_u64(final_state.free_count);
        logger.write_bytes(&PKPMM_DMA_START);
        logger.write_hex_u64(proof.dma_start_page * poole_handoff::PAGE_BYTES);
        logger.write_bytes(&PKPMM_DMA32_START);
        logger.write_hex_u64(proof.dma32_start_page * poole_handoff::PAGE_BYTES);
        logger.write_bytes(&PKPMM_DOUBLE_FREE);
        logger.write_decimal_u64(final_state.rejected_double_frees);
        logger.write_bytes(&PKPMM_QUOTA);
        logger.write_decimal_u64(final_state.rejected_quota_requests);
        logger.write_bytes(&PKPMM_UNAVAILABLE);
        logger.write_decimal_u64(final_state.rejected_unavailable_requests);
        logger.write_bytes(&PKPMM_METADATA_POISON);
        logger.write_decimal_u64(final_state.metadata_poison_events);
        logger.write_bytes(&PKPMM_COALESCES);
        logger.write_decimal_u64(final_state.coalesce_events);
        logger.write_bytes(&PKPMM_RESULT);
        logger.write_decimal_u64(
            final_state.managed_pages[0]
                + final_state.managed_pages[1]
                + final_state.managed_pages[2],
        );
        logger.write_bytes(&PKPMM_RESULT_TAIL);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::VirtualMemory {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        macro_rules! vm_try {
            ($operation:expr) => {
                match $operation {
                    Ok(value) => value,
                    Err(error) => {
                        logger.write_bytes(&PKVM_DENIED);
                        logger.write_str(error.label());
                        logger.write_bytes(&PKVM_DENIED_TAIL);
                        poole_kernel_emergency_panic(PanicCode::VirtualMemory as u32)
                    }
                }
            };
        }
        let physical_bits = vm_try!(
            arch::x86_64::physical_address_bits().ok_or(virtual_memory::Error::BootstrapRoot)
        );
        let mut table_memory = vm_try!(BootstrapTableMemory::new(observed_cr3, physical_bits));
        let proof = vm_try!(run_virtual_memory_profile(
            &decoded,
            validated.core,
            &mut table_memory,
        ));
        logger.write_bytes(&PKVM_LAYOUT);
        logger.write_bytes(&PKVM_TABLES);
        logger.write_hex_u64(proof.root_physical);
        logger.write_bytes(&PKVM_TABLE_GENERATION);
        logger.write_decimal_u64(proof.table_generation);
        logger.write_bytes(&PKVM_DATA);
        logger.write_hex_u64(proof.data_physical);
        logger.write_bytes(&PKVM_DATA_GENERATION);
        logger.write_decimal_u64(proof.data_generation);
        logger.write_bytes(&PKVM_TABLES_TAIL);
        logger.write_bytes(&PKVM_TRANSLATION);
        logger.write_hex_u64(proof.mapped_translation.physical_address);
        logger.write_bytes(&PKVM_TRANSLATION_TAIL);
        logger.write_bytes(&PKVM_TRANSACTION);
        logger.write_bytes(&PKVM_RESULT);
        logger.write_decimal_u64(proof.final_allocated_pages);
        logger.write_bytes(&PKVM_PHYSICAL_WRITES);
        logger.write_decimal_u64(proof.physical_write_count);
        logger.write_bytes(&PKVM_TEMPORARY_PTE_WRITES);
        logger.write_decimal_u64(proof.temporary_pte_write_count);
        logger.write_bytes(&PKVM_ALLOCATIONS);
        logger.write_decimal_u64(proof.final_allocation_count);
        logger.write_bytes(&PKVM_FREES);
        logger.write_decimal_u64(proof.final_free_count);
        logger.write_bytes(&PKVM_INVLPG);
        logger.write_decimal_u64(proof.hardware_invalidation_count);
        logger.write_bytes(&PKVM_RESULT_TAIL);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::ActiveVirtualMemory {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        macro_rules! active_vm_try {
            ($operation:expr) => {
                match $operation {
                    Ok(value) => value,
                    Err(error) => {
                        logger.write_bytes(&PKAVM_DENIED);
                        logger.write_str(error.label());
                        logger.write_bytes(&PKAVM_DENIED_TAIL);
                        poole_kernel_emergency_panic(PanicCode::ActiveVirtualMemory as u32)
                    }
                }
            };
        }
        let physical_bits = active_vm_try!(
            arch::x86_64::physical_address_bits().ok_or(active_virtual_memory::Error::AddressWidth)
        );
        let mut table_memory = match BootstrapTableMemory::new(observed_cr3, physical_bits) {
            Ok(value) => value,
            Err(error) => {
                logger.write_bytes(&PKAVM_DENIED);
                logger.write_str(error.label());
                logger.write_bytes(&PKAVM_DENIED_TAIL);
                poole_kernel_emergency_panic(PanicCode::ActiveVirtualMemory as u32)
            }
        };
        let mut hardware = LiveActiveHardware;
        let proof = active_vm_try!(run_active_virtual_memory_profile(
            &decoded,
            validated.core,
            observed_cr3,
            physical_bits,
            &mut table_memory,
            &mut hardware,
        ));
        let summary = proof.summary;
        logger.write_bytes(&PKAVM_LAYOUT);
        logger.write_bytes(&PKAVM_CANDIDATE);
        logger.write_hex_u64(summary.original_root);
        logger.write_bytes(&PKAVM_ROOT);
        logger.write_hex_u64(summary.candidate_root);
        logger.write_bytes(&PKAVM_TABLE_GENERATION);
        logger.write_decimal_u64(summary.table_generation);
        logger.write_bytes(&PKAVM_DATA);
        logger.write_hex_u64(summary.data_physical);
        logger.write_bytes(&PKAVM_DATA_GENERATION);
        logger.write_decimal_u64(summary.data_generation);
        logger.write_bytes(&PKAVM_DIRECT_FIRST);
        logger.write_hex_u64(summary.direct_map_first);
        logger.write_bytes(&PKAVM_DIRECT_LAST);
        logger.write_hex_u64(summary.direct_map_last);
        logger.write_bytes(&PKAVM_CANDIDATE_TAIL);
        logger.write_bytes(&PKAVM_ACTIVATION);
        logger.write_decimal_u64(summary.cr3_writes);
        logger.write_bytes(&PKAVM_ACTIVATION_TAIL);
        logger.write_bytes(&PKAVM_INVALIDATION);
        logger.write_decimal_u64(summary.local_invalidations);
        logger.write_bytes(&PKAVM_RECEIPTS);
        logger.write_decimal_u64(summary.active_receipts);
        logger.write_bytes(&PKAVM_PROBE);
        logger.write_hex_u64(u64::from(proof.probe_value));
        logger.write_bytes(&PKAVM_INVALIDATION_TAIL);
        logger.write_bytes(&PKAVM_RESULT);
        logger.write_decimal_u64(proof.final_allocated_pages);
        logger.write_bytes(&PKAVM_PHYSICAL_WRITES);
        logger.write_decimal_u64(proof.physical_write_count);
        logger.write_bytes(&PKAVM_TEMPORARY_WRITES);
        logger.write_decimal_u64(proof.temporary_pte_write_count);
        logger.write_bytes(&PKAVM_BOOTSTRAP_INVLPG);
        logger.write_decimal_u64(proof.bootstrap_invalidation_count);
        logger.write_bytes(&PKAVM_ALLOCATIONS);
        logger.write_decimal_u64(proof.final_allocation_count);
        logger.write_bytes(&PKAVM_FREES);
        logger.write_decimal_u64(proof.final_free_count);
        logger.write_bytes(&PKAVM_RESULT_TAIL);
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
                .checked_sub(
                    (poolekernel::BOOTSTRAP_STACK_PAGE_COUNT + 1) * poole_handoff::PAGE_BYTES,
                )
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
        DevelopmentTrapScenario::PhysicalMemory => {
            poole_kernel_emergency_panic(PanicCode::PhysicalMemory as u32)
        }
        DevelopmentTrapScenario::VirtualMemory => {
            poole_kernel_emergency_panic(PanicCode::VirtualMemory as u32)
        }
        DevelopmentTrapScenario::ActiveVirtualMemory => {
            poole_kernel_emergency_panic(PanicCode::ActiveVirtualMemory as u32)
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
