#![no_std]
#![no_main]
#![deny(warnings)]
#![forbid(unsafe_op_in_unsafe_fn)]

mod arch {
    pub mod x86_64;
}

use core::cell::UnsafeCell;
use core::panic::PanicInfo;
use core::ptr::{read_volatile, write_volatile};
use core::sync::atomic::{AtomicU32, AtomicU64, Ordering};

use arch::x86_64::{Com1, DebugCon, TrapFrame, halt_forever};
use poolekernel::{
    BUILD_ID, ByteSink, CPU_POLICY_CONTRACT_ID, DevelopmentTrapScenario, EARLY_LOG_CAPACITY,
    EarlyLogger, EarlyRing, Framebuffer, PanicCode, PanicDisposition, PanicState,
    TRANSFER_CONTRACT_ID, TRAP_CONTRACT_ID, TrapDisposition, TrapError, TrapExpectation,
    TrapObservation, XSTATE_EXCEPTION_CONTRACT_ID, acpi,
    active_virtual_memory::{
        self, ActiveHardware, run_profile as run_active_virtual_memory_profile,
    },
    decode_cpu_identity,
    interrupt_time::{
        self, APIC_BASE_ENABLE, APIC_BASE_X2APIC, APIC_ERROR_VECTOR, HpetClock, SPURIOUS_VECTOR,
        TIMER_VECTOR, VectorLedger, calibrate_apic_timer, parse_hpet, parse_madt,
        timer_initial_count, validate_apic_discovery,
    },
    physical_memory::{
        AllocationHandle, DEFAULT_QUOTA_PAGES, LEDGER_ARENA_PAGE_CAPACITY, LEDGER_GUARD_PAGE_COUNT,
        METADATA_ARENA_PAGE_COUNT, MetadataArenaAccess, PageAccessError, PhysicalMemoryError,
        PhysicalMemoryManager, PhysicalPageAccess, ReclaimStage, ScrubKind, ScrubReceipt, Zone,
        run_profile as run_physical_memory_profile,
    },
    privilege_msr::{machine_check_bank_count, machine_check_ctl_present, validate_snapshot},
    revalidation,
    scheduler::{
        ContextSwitchContract as SchedulerContextSwitchContract, CpuId as SchedulerCpuId,
        RawSpinLock as SchedulerRawSpinLock, Scheduler, TaskId as SchedulerTaskId,
        TaskState as SchedulerTaskState, validate_context_switch_contract,
    },
    scheduler_preempt::{
        BspPreemption, ContextOwnership as SchedulerContextOwnership, DeferredEvent,
        DeferredEventKind, InterruptFrameContract as SchedulerInterruptFrameContract,
        RescheduleCause, validate_context_ownership as validate_scheduler_context_ownership,
    },
    smp::{self, MailboxSnapshot, ResourceLayout},
    smp_ipi::{
        self, IpiSnapshot, Operation as IpiOperation, Request as IpiRequest, ShootdownRequest,
        ShootdownSnapshot,
    },
    smp_runtime::{self, MailboxSnapshot as RuntimeMailboxSnapshot},
    validate_cpu_policy_snapshot, validate_descriptor_state, validate_development_handoff,
    validate_entry_envelope, validate_handoff, validate_interrupt_descriptor_state,
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
    b"POOLEOS:KERNEL:PMM-DENIED contract=PKPMM7 reason="
);
pkpmm_fragment!(
    PKPMM_DENIED_TAIL,
    b" physical_effects=fail_closed ownership_release=0 reclaim=0 authority=0 actions=0 terminal=panic\n"
);
pkpmm_fragment!(
    PKPMM_EARLY,
    b"POOLEOS:KERNEL:PMM-EARLY PASS contract=PKPMM7 selector=8 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n"
);
pkpmm_fragment!(
    PKPMM_STAGE,
    b"POOLEOS:KERNEL:PMM-STAGE PASS contract=PKPMM7 stage="
);
pkpmm_fragment!(
    PKPMM_MAP,
    b"POOLEOS:KERNEL:PMM-MAP PASS contract=PKPMM7 entries="
);
pkpmm_fragment!(PKPMM_USABLE, b" usable_pages=");
pkpmm_fragment!(PKPMM_BOOT_RECLAIMABLE, b" boot_reclaimable_pages=");
pkpmm_fragment!(PKPMM_LOADER_RESERVED, b" loader_reserved_pages=");
pkpmm_fragment!(PKPMM_NULL_GUARD, b" null_guard_pages=");
pkpmm_fragment!(
    PKPMM_ZONES,
    b"\nPOOLEOS:KERNEL:PMM-ZONES PASS contract=PKPMM7 dma_source="
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
    b"\nPOOLEOS:KERNEL:PMM-OWNERSHIP PASS contract=PKPMM7 kernel_base="
);
pkpmm_fragment!(PKPMM_KERNEL_PAGES, b" kernel_pages=");
pkpmm_fragment!(PKPMM_HANDOFF_BASE, b" handoff_base=");
pkpmm_fragment!(PKPMM_HANDOFF_PAGES, b" handoff_pages=");
pkpmm_fragment!(PKPMM_ROOT, b" root=");
pkpmm_fragment!(PKPMM_PROTECTED, b" protected=1\n");
pkpmm_fragment!(PKPMM_EXERCISE_DENIED, b"POOLEOS:KERNEL:PMM-DENIED contract=PKPMM7 reason=exercise_invariant physical_effects=fail_closed ownership_release=0 reclaim=0 authority=0 actions=0 terminal=panic\n");
pkpmm_fragment!(
    PKPMM_METADATA,
    b"POOLEOS:KERNEL:PMM-METADATA PASS contract=PKPMM7 pages="
);
pkpmm_fragment!(PKPMM_METADATA_PHYSICAL, b" physical_start=");
pkpmm_fragment!(PKPMM_METADATA_VIRTUAL, b" virtual_start=");
pkpmm_fragment!(PKPMM_METADATA_GENERATION, b" generation=");
pkpmm_fragment!(PKPMM_METADATA_OWNER, b" owner=");
pkpmm_fragment!(PKPMM_METADATA_BYTES, b" manager_bytes=");
pkpmm_fragment!(PKPMM_METADATA_SOURCE, b" source_records=");
pkpmm_fragment!(PKPMM_METADATA_EXTENTS, b" free_extents=");
pkpmm_fragment!(PKPMM_METADATA_ALLOCATIONS, b" allocation_records=");
pkpmm_fragment!(PKPMM_METADATA_RECEIPTS, b" receipt_records=");
pkpmm_fragment!(PKPMM_METADATA_HANDOFF_CHECKSUM, b" handoff_checksum=");
pkpmm_fragment!(PKPMM_METADATA_FINAL_CHECKSUM, b" final_checksum=");
pkpmm_fragment!(PKPMM_METADATA_GUARDS, b" guard_pages=");
pkpmm_fragment!(PKPMM_METADATA_MAPPINGS, b" mappings=");
pkpmm_fragment!(PKPMM_METADATA_PTE_WRITES, b" pte_writes=");
pkpmm_fragment!(PKPMM_METADATA_RELEASE_EXCLUDED, b" release_excluded=");
pkpmm_fragment!(PKPMM_METADATA_RELEASE_REJECTED, b" release_rejected=");
pkpmm_fragment!(PKPMM_METADATA_INTEGRITY, b" integrity=");
pkpmm_fragment!(
    PKPMM_METADATA_RESERVATION_ROLLBACKS,
    b" reservation_rollbacks="
);
pkpmm_fragment!(PKPMM_METADATA_MAPPING_ROLLBACKS, b" mapping_rollbacks=");
pkpmm_fragment!(
    PKPMM_METADATA_TAIL,
    b" handoff=validated corruption=host_verified rollback=host_verified\n"
);
pkpmm_fragment!(
    PKPMM_GROWTH,
    b"POOLEOS:KERNEL:PMM-GROWTH PASS contract=PKPMM7 initial_generation="
);
pkpmm_fragment!(PKPMM_GROWTH_FINAL_GENERATION, b" final_generation=");
pkpmm_fragment!(PKPMM_GROWTH_INITIAL_PAGES, b" initial_pages=");
pkpmm_fragment!(PKPMM_GROWTH_FINAL_PAGES, b" final_pages=");
pkpmm_fragment!(PKPMM_GROWTH_FREE_CAPACITY, b" free_capacity=");
pkpmm_fragment!(PKPMM_GROWTH_ALLOCATION_CAPACITY, b" allocation_capacity=");
pkpmm_fragment!(PKPMM_GROWTH_SOURCE_CAPACITY, b" source_capacity=");
pkpmm_fragment!(PKPMM_GROWTH_SCRUB_CAPACITY, b" scrub_capacity=");
pkpmm_fragment!(PKPMM_GROWTH_RECLAIM_CAPACITY, b" reclaim_capacity=");
pkpmm_fragment!(PKPMM_GROWTH_RETIRED_GENERATION, b" retired_generation=");
pkpmm_fragment!(PKPMM_GROWTH_RETIRED_PAGES, b" retired_pages=");
pkpmm_fragment!(PKPMM_GROWTH_MAPPED_PAGES, b" mapped_pages=");
pkpmm_fragment!(PKPMM_GROWTH_PTE_WRITES, b" pte_writes=");
pkpmm_fragment!(PKPMM_GROWTH_CHECKSUM, b" checksum=");
pkpmm_fragment!(PKPMM_GROWTH_PRESSURE_CHECKS, b" guard_pages=4 mapping_events=4 revoked=3 integrity=1 atomic=1 rollbacks=0 retirement_failures=0 retirement_retry=0 pressure_checks=");
pkpmm_fragment!(PKPMM_GROWTH_PRESSURE_TRIGGERS, b" pressure_triggers=");
pkpmm_fragment!(PKPMM_GROWTH_AUTOMATIC_GROWTHS, b" automatic_growths=");
pkpmm_fragment!(PKPMM_GROWTH_PRESSURE_CYCLES, b" pressure_cycles=");
pkpmm_fragment!(PKPMM_GROWTH_SOFT_FALLBACKS, b" soft_fallbacks=");
pkpmm_fragment!(PKPMM_GROWTH_HARD_REJECTIONS, b" hard_rejections=");
pkpmm_fragment!(PKPMM_GROWTH_TAIL, b" growth_headroom_allocation=1 growth_headroom_scrub=4 window_capacity=32 next_pages=58 pre_effect=host_verified concurrency=0 smp=0 authority=0 actions=0 production=0\n");
pkpmm_fragment!(
    PKPMM_RECLAIM,
    b"POOLEOS:KERNEL:PMM-RECLAIM PASS contract=PKPMM7 stage=post_exit_boot_services class=boot_services sequence="
);
pkpmm_fragment!(PKPMM_RECLAIM_SOURCE_RECORDS, b" source_records=");
pkpmm_fragment!(PKPMM_RECLAIM_RANGES, b" ranges=");
pkpmm_fragment!(PKPMM_RECLAIM_PAGES, b" pages=");
pkpmm_fragment!(PKPMM_RECLAIM_DMA_PAGES, b" dma_pages=");
pkpmm_fragment!(PKPMM_RECLAIM_DMA32_PAGES, b" dma32_pages=");
pkpmm_fragment!(PKPMM_RECLAIM_NORMAL_PAGES, b" normal_pages=");
pkpmm_fragment!(PKPMM_RECLAIM_PRE_EXTENTS, b" pre_extents=");
pkpmm_fragment!(PKPMM_RECLAIM_POST_EXTENTS, b" post_extents=");
pkpmm_fragment!(PKPMM_RECLAIM_SCRUB_BYTES, b" scrub_bytes=");
pkpmm_fragment!(PKPMM_RECLAIM_VERIFIED_BYTES, b" verified_bytes=");
pkpmm_fragment!(PKPMM_RECLAIM_RANGE_CHECKSUM, b" range_checksum=");
pkpmm_fragment!(PKPMM_RECLAIM_RECEIPT_CHECKSUM, b" receipt_checksum=");
pkpmm_fragment!(PKPMM_RECLAIM_IDEMPOTENT, b" idempotent=");
pkpmm_fragment!(PKPMM_RECLAIM_ACPI_HELD, b" acpi_held_pages=");
pkpmm_fragment!(PKPMM_RECLAIM_ACPI_EARLY_REJECTED, b" acpi_early_rejected=");
pkpmm_fragment!(
    PKPMM_RECLAIM_TAIL,
    b" retained_excluded=1 atomic=1 rollback=host_verified\n"
);
pkpmm_fragment!(
    PKPMM_ACPI_SNAPSHOT,
    b"POOLEOS:KERNEL:PMM-ACPI-SNAPSHOT PASS contract=PKACPI1 pmm=PKPMM7 rsdp="
);
pkpmm_fragment!(PKPMM_ACPI_XSDT, b" xsdt=");
pkpmm_fragment!(PKPMM_ACPI_ENTRIES, b" xsdt_entries=");
pkpmm_fragment!(PKPMM_ACPI_MASK, b" required_mask=");
pkpmm_fragment!(PKPMM_ACPI_FACP, b" facp_bytes=");
pkpmm_fragment!(PKPMM_ACPI_APIC, b" apic_bytes=");
pkpmm_fragment!(PKPMM_ACPI_HPET, b" hpet_bytes=");
pkpmm_fragment!(PKPMM_ACPI_MCFG, b" mcfg_bytes=");
pkpmm_fragment!(PKPMM_ACPI_DESTINATION, b" snapshot=");
pkpmm_fragment!(PKPMM_ACPI_PAGES, b" snapshot_pages=");
pkpmm_fragment!(PKPMM_ACPI_BYTES, b" snapshot_bytes=");
pkpmm_fragment!(PKPMM_ACPI_COPIED, b" copied_bytes=");
pkpmm_fragment!(PKPMM_ACPI_SOURCE_CHECKSUM, b" source_checksum=");
pkpmm_fragment!(PKPMM_ACPI_SNAPSHOT_CHECKSUM, b" snapshot_checksum=");
pkpmm_fragment!(PKPMM_ACPI_TAIL, b" required=APIC,FACP,HPET,MCFG copy_verified=1 lifecycle_released=1 retained=1 aml=0 smp=0 target=0 production=0\n");
pkpmm_fragment!(
    PKPMM_ACPI_RECLAIM,
    b"POOLEOS:KERNEL:PMM-ACPI-RECLAIM PASS contract=PKPMM7 stage=acpi_tables_released class=acpi sequence="
);
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_SOURCE, b" source_records=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_RANGES, b" ranges=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_PAGES, b" pages=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_DMA, b" dma_pages=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_DMA32, b" dma32_pages=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_NORMAL, b" normal_pages=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_PRE, b" pre_extents=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_POST, b" post_extents=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_ZEROED, b" scrub_bytes=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_VERIFIED, b" verified_bytes=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_RANGE_CHECKSUM, b" range_checksum=");
pkpmm_fragment!(PKPMM_ACPI_RECLAIM_RECEIPT_CHECKSUM, b" receipt_checksum=");
pkpmm_fragment!(
    PKPMM_ACPI_RECLAIM_TAIL,
    b" idempotent=1 snapshot_retained=1 atomic=1 rollback=host_verified\n"
);
pkpmm_fragment!(
    PKPMM_SCRUB,
    b"POOLEOS:KERNEL:PMM-SCRUB PASS contract=PKPMM7 allocations="
);
pkpmm_fragment!(PKPMM_FREES, b" frees=");
pkpmm_fragment!(PKPMM_START, b" start=");
pkpmm_fragment!(PKPMM_FIRST_GENERATION, b" first_generation=");
pkpmm_fragment!(PKPMM_REUSE_GENERATION, b" reuse_generation=");
pkpmm_fragment!(PKPMM_ALLOCATION_RECEIPTS, b" allocation_receipts=");
pkpmm_fragment!(PKPMM_RELEASE_RECEIPTS, b" release_receipts=");
pkpmm_fragment!(PKPMM_SCRUB_PAGES, b" scrub_pages=");
pkpmm_fragment!(PKPMM_SCRUB_BYTES, b" scrub_bytes=");
pkpmm_fragment!(PKPMM_VERIFIED_BYTES, b" verified_bytes=");
pkpmm_fragment!(PKPMM_STALE_PATTERN, b" stale_pattern=");
pkpmm_fragment!(PKPMM_STALE_ABSENT, b" stale_absent=");
pkpmm_fragment!(PKPMM_DOUBLE_FREE, b" double_free_rejected=");
pkpmm_fragment!(PKPMM_QUOTA, b" quota_rejected=");
pkpmm_fragment!(PKPMM_UNAVAILABLE, b" unavailable_rejected=");
pkpmm_fragment!(PKPMM_METADATA_POISON, b" metadata_poison=");
pkpmm_fragment!(PKPMM_COALESCES, b" coalesces=");
pkpmm_fragment!(PKPMM_ROLLBACK, b" rollback=host_verified\n");
pkpmm_fragment!(
    PKPMM_RESULT,
    b"POOLEOS:KERNEL:PMM-RESULT PASS contract=PKPMM7 profile=qemu64_tier0 managed_pages="
);
pkpmm_fragment!(PKPMM_ALLOCATED_PAGES, b" allocated_pages=");
pkpmm_fragment!(PKPMM_PHYSICAL_WRITES, b" physical_writes=");
pkpmm_fragment!(PKPMM_PHYSICAL_READS, b" physical_reads=");
pkpmm_fragment!(PKPMM_TEMPORARY_WRITES, b" temporary_pte_writes=");
pkpmm_fragment!(PKPMM_BOOTSTRAP_INVLPG, b" bootstrap_invlpg=");
pkpmm_fragment!(PKPMM_RESULT_TAIL, b" alias_revoked=1 metadata_retained=1 ledger_generation_retained=1 acpi_snapshot_retained=1 mappings=temporary_single_page_plus_guarded_metadata_and_repeated_ledger_generations reclaim=1 acpi_reclaim=1 concurrency=0 smp=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");

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
    b"POOLEOS:KERNEL:ACTIVE-VM-DENIED contract=PKVM3 reason="
);
pkavm_fragment!(
    PKAVM_DENIED_TAIL,
    b" effects=fail_closed authority=0 actions=0 terminal=panic\n"
);
pkavm_fragment!(
    PKAVM_EARLY,
    b"POOLEOS:KERNEL:ACTIVE-VM-EARLY PASS contract=PKVM3 selector=10 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n"
);
pkavm_fragment!(
    PKAVM_STAGE,
    b"POOLEOS:KERNEL:ACTIVE-VM-STAGE PASS contract=PKVM3 stage="
);
pkavm_fragment!(
    PKAVM_LAYOUT,
    b"POOLEOS:KERNEL:ACTIVE-VM-LAYOUT PASS contract=PKVM3 canonical_bits=48 direct_start=0xFFFF900000000000 direct_end=0xFFFFD00000000000 user_start=0x0000000040000000 page_bytes=4096 table_pages="
);
pkavm_fragment!(
    PKAVM_LAYOUT_DIRECT_DIRECTORIES,
    b" direct_directory_tables="
);
pkavm_fragment!(PKAVM_LAYOUT_DIRECT_TABLES, b" direct_page_tables=");
pkavm_fragment!(PKAVM_LAYOUT_MAPPED_PAGES, b" mapped_pages=");
pkavm_fragment!(PKAVM_LINE_END, b"\n");
pkavm_fragment!(
    PKAVM_CANDIDATE,
    b"POOLEOS:KERNEL:ACTIVE-VM-CANDIDATE PASS contract=PKVM3 original_root="
);
pkavm_fragment!(PKAVM_ROOT, b" candidate_root=");
pkavm_fragment!(PKAVM_TABLE_GENERATION, b" table_generation=");
pkavm_fragment!(PKAVM_DATA, b" data=");
pkavm_fragment!(PKAVM_DATA_GENERATION, b" data_generation=");
pkavm_fragment!(PKAVM_DIRECT_FIRST, b" direct_first=");
pkavm_fragment!(PKAVM_DIRECT_LAST, b" direct_last=");
pkavm_fragment!(PKAVM_DIRECT_GENERATION, b" direct_generation=");
pkavm_fragment!(PKAVM_DIRECT_RANGES, b" direct_ranges=");
pkavm_fragment!(PKAVM_DIRECT_GAPS, b" gap_pages=");
pkavm_fragment!(PKAVM_DIRECT_EXCLUDED, b" retained_excluded_pages=");
pkavm_fragment!(PKAVM_DIRECT_CHECKSUM, b" coverage_checksum=");
pkavm_fragment!(
    PKAVM_CANDIDATE_TAIL,
    b" cache=write_back cache_alias_rejected=1 inherited_kernel=exact guarded_stack=exact handoff=exact bootstrap_alias_revoked=1 root_active=0\n"
);
pkavm_fragment!(
    PKAVM_ACTIVATION,
    b"POOLEOS:KERNEL:ACTIVE-VM-ACTIVATION PASS contract=PKVM3 cr3_writes="
);
pkavm_fragment!(
    PKAVM_ACTIVATION_TAIL,
    b" candidate_readback=exact original_restore=exact rollback_control=host_verified bsp=1 smp=0\n"
);
pkavm_fragment!(
    PKAVM_INVALIDATION,
    b"POOLEOS:KERNEL:ACTIVE-VM-INVALIDATION PASS contract=PKVM3 local_invlpg="
);
pkavm_fragment!(PKAVM_RECEIPTS, b" active_receipts=");
pkavm_fragment!(PKAVM_PROBE, b" probe=");
pkavm_fragment!(
    PKAVM_INVALIDATION_TAIL,
    b" protect=1 user_unmap=1 direct_unmap=1 stale_root_rejected=host premature_reuse_rejected=1 generation_retirement_receipts=1 local_context_flushes=1 remote_shootdowns_pending=0 future_smp_shootdown_required=1 old_generation_reclaim_deferred=1 exact_release_receipt=1 shootdown=0\n"
);
pkavm_fragment!(
    PKAVM_RESULT,
    b"POOLEOS:KERNEL:ACTIVE-VM-RESULT PASS contract=PKVM3 profile=qemu64_tier0 root_released=1 data_released=1 allocated_pages="
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

macro_rules! pkirq_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkirq_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pkirq_fragment!(PKIRQ_EARLY, b"POOLEOS:KERNEL:IRQ-EARLY PASS contract=PKIRQ1 selector=11 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pkirq_fragment!(
    PKIRQ_DENIED,
    b"POOLEOS:KERNEL:IRQ-DENIED contract=PKIRQ1 reason="
);
pkirq_fragment!(
    PKIRQ_DENIED_TAIL,
    b" rollback=terminal_fail_closed authority=0 actions=0 production=0 terminal=panic\n"
);
pkirq_fragment!(
    PKIRQ_ACPI,
    b"POOLEOS:KERNEL:IRQ-ACPI PASS contract=PKIRQ1 madt_bytes="
);
pkirq_fragment!(PKIRQ_PROCESSORS, b" processors=");
pkirq_fragment!(PKIRQ_ENABLED, b" enabled=");
pkirq_fragment!(PKIRQ_IOAPICS, b" ioapics=");
pkirq_fragment!(PKIRQ_OVERRIDES, b" overrides=");
pkirq_fragment!(PKIRQ_NMI_SOURCES, b" nmi_sources=");
pkirq_fragment!(PKIRQ_LOCAL_NMIS, b" local_nmis=");
pkirq_fragment!(PKIRQ_UNKNOWN, b" unknown=");
pkirq_fragment!(PKIRQ_PCAT, b" pcat=");
pkirq_fragment!(PKIRQ_APIC_PHYSICAL, b" apic_physical=");
pkirq_fragment!(PKIRQ_HPET_PHYSICAL, b" hpet_physical=");
pkirq_fragment!(PKIRQ_ACPI_TAIL, b" retained_snapshot=1 complete_walk=1\n");
pkirq_fragment!(
    PKIRQ_APIC,
    b"POOLEOS:KERNEL:IRQ-APIC PASS contract=PKIRQ1 apic_id="
);
pkirq_fragment!(PKIRQ_VERSION, b" version=");
pkirq_fragment!(PKIRQ_MAX_LVT, b" max_lvt=");
pkirq_fragment!(PKIRQ_GLOBAL, b" global_enable=");
pkirq_fragment!(PKIRQ_MSR_WRITES, b" msr_writes=");
pkirq_fragment!(PKIRQ_SVR, b" svr_vector=255 software_enable=1 pic_masked=");
pkirq_fragment!(PKIRQ_MMIO, b" mmio=uncacheable guarded=3\n");
pkirq_fragment!(
    PKIRQ_VECTOR,
    b"POOLEOS:KERNEL:IRQ-VECTORS PASS contract=PKIRQ1 owned="
);
pkirq_fragment!(
    PKIRQ_TIMER_VECTOR,
    b" timer=64 ipi_first=224 ipi_last=239 error=240 spurious=255 collisions=host_verified\n"
);
pkirq_fragment!(
    PKIRQ_CLOCK,
    b"POOLEOS:KERNEL:IRQ-CLOCK PASS contract=PKIRQ1 source=hpet counter_bits="
);
pkirq_fragment!(PKIRQ_PERIOD, b" period_fs=");
pkirq_fragment!(PKIRQ_HPET_TICKS, b" sample_ticks=");
pkirq_fragment!(PKIRQ_SAMPLE_NS, b" sample_ns=");
pkirq_fragment!(PKIRQ_APIC_TICKS, b" apic_ticks=");
pkirq_fragment!(PKIRQ_FREQUENCY, b" apic_hz=");
pkirq_fragment!(PKIRQ_INITIAL, b" one_shot_initial=");
pkirq_fragment!(PKIRQ_MONOTONIC_NS, b" monotonic_ns=");
pkirq_fragment!(PKIRQ_CLOCK_TAIL, b" overflow=checked wrap=bounded\n");
pkirq_fragment!(
    PKIRQ_DELIVERY,
    b"POOLEOS:KERNEL:IRQ-DELIVERY PASS contract=PKIRQ1 timer_deliveries="
);
pkirq_fragment!(PKIRQ_EOIS, b" eois=");
pkirq_fragment!(PKIRQ_ERRORS, b" apic_errors=");
pkirq_fragment!(PKIRQ_SPURIOUS, b" spurious=");
pkirq_fragment!(PKIRQ_ISR, b" in_service_after=");
pkirq_fragment!(PKIRQ_DELIVERY_TAIL, b" exact_one_shot=1 unacknowledged=0\n");
pkirq_fragment!(PKIRQ_RESULT, b"POOLEOS:KERNEL:IRQ-RESULT PASS contract=PKIRQ1 profile=qemu64_tier0 bsp=1 madt=1 local_apic=1 hpet=1 vectors=1 timer=1 deliveries=");
pkirq_fragment!(PKIRQ_RESULT_TAIL, b" rollback=1 mmio_revoked=1 pic_restored=1 interrupts=disabled smp=0 ap_start=0 shootdown=0 target=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");

macro_rules! pksmp_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pksmp_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pksmp_fragment!(PKSMP_EARLY, b"POOLEOS:KERNEL:SMP-EARLY PASS contract=PKSMP1 selector=12 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pksmp_fragment!(
    PKSMP_DENIED,
    b"POOLEOS:KERNEL:SMP-DENIED contract=PKSMP1 reason="
);
pksmp_fragment!(
    PKSMP_DENIED_TAIL,
    b" cleanup=fail_closed authority=0 actions=0 production=0 terminal=panic\n"
);
pksmp_fragment!(
    PKSMP_TOPOLOGY,
    b"POOLEOS:KERNEL:SMP-TOPOLOGY PASS contract=PKSMP1 madt_bytes="
);
pksmp_fragment!(PKSMP_PROCESSORS, b" processors=");
pksmp_fragment!(PKSMP_ENABLED, b" enabled=");
pksmp_fragment!(PKSMP_BSP_APIC, b" bsp_apic_id=");
pksmp_fragment!(PKSMP_TARGET_APIC, b" target_apic_id=");
pksmp_fragment!(PKSMP_APIC_PHYSICAL, b" apic_physical=");
pksmp_fragment!(PKSMP_HPET_PHYSICAL, b" hpet_physical=");
pksmp_fragment!(
    PKSMP_TOPOLOGY_TAIL,
    b" x2apic=0 selection=lowest_enabled_non_bsp retained_snapshot=1\n"
);
pksmp_fragment!(
    PKSMP_RESOURCES,
    b"POOLEOS:KERNEL:SMP-RESOURCES PASS contract=PKSMP1 physical_start="
);
pksmp_fragment!(PKSMP_RESOURCE_PAGES, b" pages=");
pksmp_fragment!(PKSMP_VECTOR, b" sipi_vector=");
pksmp_fragment!(PKSMP_TRAMPOLINE_BYTES, b" trampoline_bytes=");
pksmp_fragment!(PKSMP_ALLOCATION_SEQUENCE, b" allocation_sequence=");
pksmp_fragment!(
    PKSMP_RESOURCES_TAIL,
    b" tables=4 stack_pages=4 per_cpu_pages=1 guard_pages=4 below_1mib=1 allocation_scrubbed=1\n"
);
pksmp_fragment!(
    PKSMP_TABLES,
    b"POOLEOS:KERNEL:SMP-TABLES PASS contract=PKSMP1 pml4="
);
pksmp_fragment!(PKSMP_PDPT, b" pdpt=");
pksmp_fragment!(PKSMP_PD, b" pd=");
pksmp_fragment!(PKSMP_PT, b" pt=");
pksmp_fragment!(PKSMP_TABLES_TAIL, b" identity_pages=6 trampoline=rx stack=rw_nx per_cpu=rw_nx guards=absent high_alias=revocable\n");
pksmp_fragment!(
    PKSMP_START,
    b"POOLEOS:KERNEL:SMP-START PASS contract=PKSMP1 init_asserts="
);
pksmp_fragment!(PKSMP_INIT_DEASSERTS, b" init_deasserts=");
pksmp_fragment!(PKSMP_SIPIS, b" sipis=");
pksmp_fragment!(
    PKSMP_START_TAIL,
    b" delivery_timeouts=0 sequence=init_sipi_sipi\n"
);
pksmp_fragment!(
    PKSMP_ONLINE,
    b"POOLEOS:KERNEL:SMP-ONLINE PASS contract=PKSMP1 state="
);
pksmp_fragment!(PKSMP_OBSERVED_APIC, b" observed_apic_id=");
pksmp_fragment!(PKSMP_LEAF1_ECX, b" leaf1_ecx=");
pksmp_fragment!(PKSMP_LEAF1_EDX, b" leaf1_edx=");
pksmp_fragment!(PKSMP_CR0, b" cr0=");
pksmp_fragment!(PKSMP_CR3, b" cr3=");
pksmp_fragment!(PKSMP_CR4, b" cr4=");
pksmp_fragment!(PKSMP_EFER, b" efer=");
pksmp_fragment!(PKSMP_ONLINE_TAIL, b" mode=x86_64 tsc_order=validated\n");
pksmp_fragment!(
    PKSMP_STOP,
    b"POOLEOS:KERNEL:SMP-STOP PASS contract=PKSMP1 command="
);
pksmp_fragment!(PKSMP_STOP_STATE, b" state=");
pksmp_fragment!(PKSMP_TSC_ONLINE, b" tsc_online=");
pksmp_fragment!(PKSMP_TSC_STOP, b" tsc_stop=");
pksmp_fragment!(PKSMP_CHECKSUM, b" checksum=");
pksmp_fragment!(
    PKSMP_STOP_TAIL,
    b" final_init=1 parked=1 mailbox_validated=1\n"
);
pksmp_fragment!(
    PKSMP_RELEASE,
    b"POOLEOS:KERNEL:SMP-RELEASE PASS contract=PKSMP1 release_sequence="
);
pksmp_fragment!(PKSMP_ZEROED_BYTES, b" zeroed_bytes=");
pksmp_fragment!(PKSMP_VERIFIED_BYTES, b" verified_bytes=");
pksmp_fragment!(PKSMP_RELEASE_TAIL, b" resources_released=14 mailbox_revoked=1 mmio_revoked=1 pic_restored=1 hpet_restored=1 apic_base_restored=unchanged\n");
pksmp_fragment!(PKSMP_RESULT, b"POOLEOS:KERNEL:SMP-RESULT PASS contract=PKSMP1 profile=qemu64_tier0_two_vcpu bsp=1 ap_started=1 ap_online=1 ap_quiesced=1 ap_parked=1 per_cpu=1 stack_pages=4 guards=4 rollback=host_verified ipi_service=0 shootdown=0 scheduler=0 target=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");

macro_rules! pksmp2_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pksmp2_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pksmp2_fragment!(PKSMP2_EARLY, b"POOLEOS:KERNEL:SMP-RUNTIME-EARLY PASS contract=PKSMP2 selector=13 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pksmp2_fragment!(
    PKSMP2_DENIED,
    b"POOLEOS:KERNEL:SMP-RUNTIME-DENIED contract=PKSMP2 reason="
);
pksmp2_fragment!(
    PKSMP2_DENIED_TAIL,
    b" cleanup=fail_closed authority=0 actions=0 production=0 terminal=panic\n"
);
pksmp2_fragment!(
    PKSMP2_TOPOLOGY,
    b"POOLEOS:KERNEL:SMP-RUNTIME-TOPOLOGY PASS contract=PKSMP2 madt_bytes="
);
pksmp2_fragment!(PKSMP2_PROCESSORS, b" processors=");
pksmp2_fragment!(PKSMP2_ENABLED, b" enabled=");
pksmp2_fragment!(PKSMP2_BSP_APIC, b" bsp_apic_id=");
pksmp2_fragment!(PKSMP2_TARGET_APIC, b" target_apic_id=");
pksmp2_fragment!(PKSMP2_APIC_PHYSICAL, b" apic_physical=");
pksmp2_fragment!(PKSMP2_HPET_PHYSICAL, b" hpet_physical=");
pksmp2_fragment!(
    PKSMP2_TOPOLOGY_TAIL,
    b" x2apic=0 selection=lowest_enabled_non_bsp retained_snapshot=1\n"
);
pksmp2_fragment!(
    PKSMP2_RESOURCES,
    b"POOLEOS:KERNEL:SMP-RUNTIME-RESOURCES PASS contract=PKSMP2 physical_start="
);
pksmp2_fragment!(PKSMP2_RESOURCE_PAGES, b" pages=");
pksmp2_fragment!(PKSMP2_VECTOR, b" sipi_vector=");
pksmp2_fragment!(PKSMP2_TRAMPOLINE_BYTES, b" trampoline_bytes=");
pksmp2_fragment!(PKSMP2_ALLOCATION_SEQUENCE, b" allocation_sequence=");
pksmp2_fragment!(PKSMP2_RESOURCES_TAIL, b" tables=4 mapped_pages=13 guard_pages=14 reserved_absent=1 below_1mib=1 allocation_scrubbed=1\n");
pksmp2_fragment!(
    PKSMP2_TABLES,
    b"POOLEOS:KERNEL:SMP-RUNTIME-TABLES PASS contract=PKSMP2 pml4="
);
pksmp2_fragment!(PKSMP2_PDPT, b" pdpt=");
pksmp2_fragment!(PKSMP2_PD, b" pd=");
pksmp2_fragment!(PKSMP2_PT, b" pt=");
pksmp2_fragment!(PKSMP2_TABLES_TAIL, b" identity_pages=13 trampoline=rx idt=ro_nx mutable=rw_nx guards=absent reserved=absent high_alias=revocable\n");
pksmp2_fragment!(
    PKSMP2_START,
    b"POOLEOS:KERNEL:SMP-RUNTIME-START PASS contract=PKSMP2 init_asserts="
);
pksmp2_fragment!(PKSMP2_INIT_DEASSERTS, b" init_deasserts=");
pksmp2_fragment!(PKSMP2_SIPIS, b" sipis=");
pksmp2_fragment!(
    PKSMP2_START_TAIL,
    b" delivery_timeouts=0 sequence=init_sipi_sipi\n"
);
pksmp2_fragment!(
    PKSMP2_DESCRIPTORS,
    b"POOLEOS:KERNEL:SMP-RUNTIME-DESCRIPTORS PASS contract=PKSMP2 gdt="
);
pksmp2_fragment!(PKSMP2_GDT_LIMIT, b" gdt_limit=");
pksmp2_fragment!(PKSMP2_TSS, b" tss=");
pksmp2_fragment!(PKSMP2_TR, b" tr=");
pksmp2_fragment!(PKSMP2_CODE_SELECTOR, b" code_selector=");
pksmp2_fragment!(PKSMP2_DATA_SELECTOR, b" data_selector=");
pksmp2_fragment!(PKSMP2_IDT, b" idt=");
pksmp2_fragment!(PKSMP2_IDT_LIMIT, b" idt_limit=");
pksmp2_fragment!(PKSMP2_GATES, b" gates=");
pksmp2_fragment!(PKSMP2_TSS_BUSY, b" tss_busy=");
pksmp2_fragment!(PKSMP2_IDT_VERIFIED, b" idt_verified=");
pksmp2_fragment!(PKSMP2_DESCRIPTORS_TAIL, b" ltr=hardware lidt=hardware\n");
pksmp2_fragment!(
    PKSMP2_STACKS,
    b"POOLEOS:KERNEL:SMP-RUNTIME-STACKS PASS contract=PKSMP2 rsp0_bottom="
);
pksmp2_fragment!(PKSMP2_RSP0_TOP, b" rsp0_top=");
pksmp2_fragment!(PKSMP2_OBSERVED_RSP, b" observed_rsp=");
pksmp2_fragment!(PKSMP2_IST1_BOTTOM, b" ist1_bottom=");
pksmp2_fragment!(PKSMP2_IST1_TOP, b" ist1_top=");
pksmp2_fragment!(PKSMP2_IST2_BOTTOM, b" ist2_bottom=");
pksmp2_fragment!(PKSMP2_IST2_TOP, b" ist2_top=");
pksmp2_fragment!(
    PKSMP2_STACKS_TAIL,
    b" rsp0_pages=4 ist_pages_each=2 guards=14\n"
);
pksmp2_fragment!(
    PKSMP2_XSTATE,
    b"POOLEOS:KERNEL:SMP-RUNTIME-XSTATE PASS contract=PKSMP2 base="
);
pksmp2_fragment!(PKSMP2_XSTATE_BYTES, b" bytes=");
pksmp2_fragment!(PKSMP2_SUPPORTED_XCR0, b" supported_xcr0=");
pksmp2_fragment!(PKSMP2_ENABLED_BYTES, b" enabled_bytes=");
pksmp2_fragment!(PKSMP2_MAXIMUM_BYTES, b" maximum_bytes=");
pksmp2_fragment!(PKSMP2_XCR0, b" xcr0=");
pksmp2_fragment!(PKSMP2_XSTATE_BV, b" xstate_bv=");
pksmp2_fragment!(PKSMP2_FCW, b" fcw=");
pksmp2_fragment!(PKSMP2_MXCSR, b" mxcsr=");
pksmp2_fragment!(PKSMP2_OWNER_INITIAL, b" owner_initial=");
pksmp2_fragment!(PKSMP2_OWNER_FINAL, b" owner_final=");
pksmp2_fragment!(PKSMP2_SAVES, b" saves=");
pksmp2_fragment!(PKSMP2_RESTORES, b" restores=");
pksmp2_fragment!(PKSMP2_XSTATE_VERIFIED, b" image_verified=");
pksmp2_fragment!(PKSMP2_XSTATE_TAIL, b" policy=eager\n");
pksmp2_fragment!(PKSMP2_VECTORS, b"POOLEOS:KERNEL:SMP-RUNTIME-VECTORS PASS contract=PKSMP2 exceptions=8 interrupts=19 timer=64 ipi_first=224 ipi_last=239 error=240 spurious=255 if=0 fault=0\n");
pksmp2_fragment!(
    PKSMP2_ONLINE,
    b"POOLEOS:KERNEL:SMP-RUNTIME-ONLINE PASS contract=PKSMP2 state="
);
pksmp2_fragment!(PKSMP2_RUNTIME_STATE, b" runtime_state=");
pksmp2_fragment!(PKSMP2_OBSERVED_APIC, b" observed_apic_id=");
pksmp2_fragment!(PKSMP2_LEAF1_ECX, b" leaf1_ecx=");
pksmp2_fragment!(PKSMP2_LEAF1_EDX, b" leaf1_edx=");
pksmp2_fragment!(PKSMP2_CR0, b" cr0=");
pksmp2_fragment!(PKSMP2_CR3, b" cr3=");
pksmp2_fragment!(PKSMP2_CR4, b" cr4=");
pksmp2_fragment!(PKSMP2_EFER, b" efer=");
pksmp2_fragment!(PKSMP2_RFLAGS, b" rflags=");
pksmp2_fragment!(PKSMP2_ONLINE_TAIL, b" mode=x86_64 tsc_order=validated\n");
pksmp2_fragment!(
    PKSMP2_STOP,
    b"POOLEOS:KERNEL:SMP-RUNTIME-STOP PASS contract=PKSMP2 command="
);
pksmp2_fragment!(PKSMP2_STOP_STATE, b" state=");
pksmp2_fragment!(PKSMP2_STOP_RUNTIME_STATE, b" runtime_state=");
pksmp2_fragment!(PKSMP2_TSC_ONLINE, b" tsc_online=");
pksmp2_fragment!(PKSMP2_TSC_STOP, b" tsc_stop=");
pksmp2_fragment!(PKSMP2_BASELINE_CHECKSUM, b" baseline_checksum=");
pksmp2_fragment!(PKSMP2_RUNTIME_CHECKSUM, b" runtime_checksum=");
pksmp2_fragment!(
    PKSMP2_STOP_TAIL,
    b" final_init=1 parked=1 mailbox_validated=1 resources_validated=1\n"
);
pksmp2_fragment!(
    PKSMP2_RELEASE,
    b"POOLEOS:KERNEL:SMP-RUNTIME-RELEASE PASS contract=PKSMP2 release_sequence="
);
pksmp2_fragment!(PKSMP2_ZEROED_BYTES, b" zeroed_bytes=");
pksmp2_fragment!(PKSMP2_VERIFIED_BYTES, b" verified_bytes=");
pksmp2_fragment!(PKSMP2_RELEASE_TAIL, b" resources_released=32 runtime_revoked=1 mmio_revoked=1 pic_restored=1 hpet_restored=1 apic_base_restored=unchanged\n");
pksmp2_fragment!(PKSMP2_RESULT, b"POOLEOS:KERNEL:SMP-RUNTIME-RESULT PASS contract=PKSMP2 profile=sandybridge_x87_sse_two_vcpu bsp=1 ap_started=1 ap_online=1 descriptors=1 stacks=3 xstate=1 vectors=27 ap_quiesced=1 ap_parked=1 resources_released=32 rollback=host_verified ipi_service=0 shootdown=0 scheduler=0 target=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");

macro_rules! pksmp3_fragment {
    ($name:ident, $value:literal) => {
        #[cfg(any())]
        #[used]
        #[unsafe(link_section = ".text.pksmp3_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pksmp3_fragment!(PKSMP3_EARLY, b"POOLEOS:KERNEL:SMP-IPI-EARLY PASS contract=PKSMP4 selector=14 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pksmp3_fragment!(
    PKSMP3_DENIED,
    b"POOLEOS:KERNEL:SMP-IPI-DENIED contract=PKSMP4 reason="
);
pksmp3_fragment!(PKSMP3_DENIED_TAIL, b" cleanup=fail_closed capability_revoked=1 authority=0 actions=0 production=0 terminal=panic\n");
pksmp3_fragment!(
    PKSMP3_TOPOLOGY,
    b"POOLEOS:KERNEL:SMP-IPI-TOPOLOGY PASS contract=PKSMP4 processors="
);
pksmp3_fragment!(
    PKSMP3_RESOURCES,
    b"POOLEOS:KERNEL:SMP-IPI-RESOURCES PASS contract=PKSMP4 physical_start="
);
pksmp3_fragment!(PKSMP3_ONLINE, b"POOLEOS:KERNEL:SMP-IPI-ONLINE PASS contract=PKSMP4 service_state=2 if=1 vectors=224,225,226,227,228,229 apic_mmio=0x00000000FEE00000 apic_table=1\n");
pksmp3_fragment!(PKSMP3_ACCEPTED, b"POOLEOS:KERNEL:SMP-IPI-ACCEPTED PASS contract=PKSMP4 operations=reschedule,shootdown_remote_invlpg,call_allowlist_noop,diagnostic,panic_notice,stop sequences=1,2,3,4,5,6 accepted=");
pksmp3_fragment!(PKSMP3_CONTROLS, b"POOLEOS:KERNEL:SMP-IPI-CONTROLS PASS contract=PKSMP4 invalid_capability=1 vector_mismatch=1 stale_sequence=1 duplicate_sequence=1 denied=");
pksmp3_fragment!(PKSMP3_TIMEOUT, b"POOLEOS:KERNEL:SMP-IPI-TIMEOUT PASS contract=PKSMP4 operation=shootdown target_apic_id=2 target_mask=0x0000000000000004 attempt=6 bounded=1 offline_cpu=1 retry_same_attempt=1 timeout_count=");
pksmp3_fragment!(
    PKSMP3_SHOOTDOWN_RECEIPT,
    b"POOLEOS:KERNEL:SMP-SHOOTDOWN PASS contract=PKSMP4 root="
);
pksmp3_fragment!(
    PKSMP3_PROBE,
    b" probe=0x00000000001FF000 retired_generation="
);
pksmp3_fragment!(PKSMP3_ACTIVE_GENERATION, b" active_generation=");
pksmp3_fragment!(PKSMP3_TARGET_MASK, b" target_mask=");
pksmp3_fragment!(PKSMP3_ACK_MASK, b" ack_mask=");
pksmp3_fragment!(PKSMP3_OLD_FRAME, b" old_frame=");
pksmp3_fragment!(PKSMP3_NEW_FRAME, b" new_frame=");
pksmp3_fragment!(PKSMP3_OBSERVED_BEFORE, b" observed_before=");
pksmp3_fragment!(PKSMP3_OBSERVED_AFTER, b" observed_after=");
pksmp3_fragment!(PKSMP3_INVALIDATIONS, b" invalidations=");
pksmp3_fragment!(PKSMP3_LAST_ACK_GENERATION, b" last_ack_generation=");
pksmp3_fragment!(PKSMP3_PREMATURE_RECLAIM, b" premature_reclaim_rejected=");
pksmp3_fragment!(PKSMP3_RECLAIM_STATE, b" reclaim_state=");
pksmp3_fragment!(PKSMP3_SHOOTDOWN_CHECKSUM, b" shootdown_checksum=");
pksmp3_fragment!(
    PKSMP3_STOP,
    b"POOLEOS:KERNEL:SMP-IPI-STOP PASS contract=PKSMP4 ack_attempt="
);
pksmp3_fragment!(
    PKSMP3_RELEASE,
    b"POOLEOS:KERNEL:SMP-IPI-RELEASE PASS contract=PKSMP4 release_sequence="
);
pksmp3_fragment!(PKSMP3_RESULT, b"POOLEOS:KERNEL:SMP-IPI-RESULT PASS contract=PKSMP4 profile=sandybridge_x87_sse_two_vcpu capability_gate=development_fixed_token operation_classes=6 valid_deliveries=6 denied_deliveries=4 offline_timeouts=1 eois=10 panic_latched=1 stop_quiesced=1 ap_parked=1 resources_released=34 rollback=host_verified shootdown_remote_invlpg=1 tlb_invalidations=1 generation_retirement=1 no_reuse_before_retirement=1 call_allowlist_noop=1 arbitrary_callback=0 scheduler=0 target=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");
pksmp3_fragment!(PKSMP3_ENABLED, b" enabled=");
pksmp3_fragment!(PKSMP3_BSP_APIC, b" bsp_apic_id=");
pksmp3_fragment!(PKSMP3_TARGET_APIC, b" target_apic_id=");
pksmp3_fragment!(PKSMP3_APIC_PHYSICAL, b" apic_physical=");
pksmp3_fragment!(PKSMP3_TOPOLOGY_TAIL, b" selection=lowest_enabled_non_bsp\n");
pksmp3_fragment!(PKSMP3_PAGES, b" pages=");
pksmp3_fragment!(PKSMP3_SIPI_VECTOR, b" sipi_vector=");
pksmp3_fragment!(PKSMP3_TRAMPOLINE_BYTES, b" trampoline_bytes=");
pksmp3_fragment!(PKSMP3_ALLOCATION_SEQUENCE, b" allocation_sequence=");
pksmp3_fragment!(PKSMP3_RESOURCES_TAIL, b" tables=5 mapped_pages=13 guard_pages=14 apic_pt_offset=31 apic_leaf=pwt_pcd_rw_nx below_1mib=1\n");
pksmp3_fragment!(PKSMP3_RESCHEDULE, b" reschedule=");
pksmp3_fragment!(PKSMP3_SHOOTDOWN, b" shootdown=");
pksmp3_fragment!(PKSMP3_CALL_FUNCTION, b" call_function=");
pksmp3_fragment!(PKSMP3_DIAGNOSTIC, b" diagnostic=");
pksmp3_fragment!(PKSMP3_PANIC, b" panic=");
pksmp3_fragment!(PKSMP3_STOP_COUNT, b" stop=");
pksmp3_fragment!(PKSMP3_DELIVERY_COUNT, b" delivery_count=");
pksmp3_fragment!(PKSMP3_EOI_COUNT, b" eoi_count=");
pksmp3_fragment!(PKSMP3_SPURIOUS, b" spurious=");
pksmp3_fragment!(PKSMP3_APIC_ERROR, b" apic_error=");
pksmp3_fragment!(PKSMP3_NEWLINE, b"\n");
pksmp3_fragment!(PKSMP3_ACK_SEQUENCE, b" ack_sequence=");
pksmp3_fragment!(PKSMP3_LAST_SEQUENCE, b" last_accepted_sequence=");
pksmp3_fragment!(PKSMP3_SERVICE_STATE, b" service_state=");
pksmp3_fragment!(PKSMP3_MAILBOX_STATE, b" mailbox_state=");
pksmp3_fragment!(PKSMP3_RUNTIME_STATE, b" runtime_state=");
pksmp3_fragment!(PKSMP3_PANIC_LATCHED, b" panic_latched=");
pksmp3_fragment!(PKSMP3_RESPONSE_CHECKSUM, b" response_checksum=");
pksmp3_fragment!(PKSMP3_BASELINE_CHECKSUM, b" baseline_checksum=");
pksmp3_fragment!(PKSMP3_RUNTIME_CHECKSUM, b" runtime_checksum=");
pksmp3_fragment!(PKSMP3_INIT_ASSERTS, b" init_asserts=");
pksmp3_fragment!(PKSMP3_INIT_DEASSERTS, b" init_deasserts=");
pksmp3_fragment!(PKSMP3_SIPIS, b" sipis=");
pksmp3_fragment!(PKSMP3_TSS_BUSY, b" tss_busy=");
pksmp3_fragment!(PKSMP3_IDT_VERIFIED, b" idt_verified=");
pksmp3_fragment!(PKSMP3_XSTATE_VERIFIED, b" xstate_verified=");
pksmp3_fragment!(PKSMP3_APIC_TABLE_VERIFIED, b" apic_table_verified=");
pksmp3_fragment!(PKSMP3_STOP_TAIL, b" final_init=1 parked=1\n");
pksmp3_fragment!(PKSMP3_ZEROED_BYTES, b" zeroed_bytes=");
pksmp3_fragment!(PKSMP3_VERIFIED_BYTES, b" verified_bytes=");
pksmp3_fragment!(
    PKSMP3_FRAME_ALLOCATION_SEQUENCES,
    b" frame_allocation_sequences="
);
pksmp3_fragment!(PKSMP3_FRAME_RELEASE_SEQUENCES, b" frame_release_sequences=");
pksmp3_fragment!(PKSMP3_FRAME_ZEROED_BYTES, b" frame_zeroed_bytes=");
pksmp3_fragment!(PKSMP3_FRAME_VERIFIED_BYTES, b" frame_verified_bytes=");
pksmp3_fragment!(PKSMP3_RELEASE_TAIL, b" resources_released=34 capability_revoked=1 runtime_revoked=1 mmio_revoked=1 pic_restored=1 hpet_restored=1 apic_base_restored=unchanged\n");

macro_rules! pksmp5_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pksmp5_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pksmp5_fragment!(PKSMP5_EARLY, b"POOLEOS:KERNEL:SMP-MULTI-EARLY PASS contract=PKSMP5 selector=14 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pksmp5_fragment!(
    PKSMP5_DENIED,
    b"POOLEOS:KERNEL:SMP-MULTI-DENIED contract=PKSMP5 reason="
);
pksmp5_fragment!(
    PKSMP5_DENIED_TAIL,
    b" cleanup=fail_closed authority=0 actions=0 production=0 terminal=panic\n"
);
pksmp5_fragment!(
    PKSMP5_TOPOLOGY,
    b"POOLEOS:KERNEL:SMP-MULTI-TOPOLOGY PASS contract=PKSMP5 processors="
);
pksmp5_fragment!(
    PKSMP5_PARTIAL,
    b"POOLEOS:KERNEL:SMP-MULTI-PARTIAL-ROLLBACK PASS contract=PKSMP5 started_mask="
);
pksmp5_fragment!(
    PKSMP5_RETRY,
    b"POOLEOS:KERNEL:SMP-MULTI-RETRY PASS contract=PKSMP5 retry_count="
);
pksmp5_fragment!(
    PKSMP5_AP,
    b"POOLEOS:KERNEL:SMP-MULTI-AP PASS contract=PKSMP5 ap_index="
);
pksmp5_fragment!(
    PKSMP5_SHOOTDOWN,
    b"POOLEOS:KERNEL:SMP-MULTI-SHOOTDOWN PASS contract=PKSMP5 target_mask="
);
pksmp5_fragment!(
    PKSMP5_LIFECYCLE,
    b"POOLEOS:KERNEL:SMP-MULTI-LIFECYCLE PASS contract=PKSMP5 started_mask="
);
pksmp5_fragment!(
    PKSMP5_RELEASE,
    b"POOLEOS:KERNEL:SMP-MULTI-RELEASE PASS contract=PKSMP5 resource_pages="
);
pksmp5_fragment!(PKSMP5_RESULT, b"POOLEOS:KERNEL:SMP-MULTI-RESULT PASS contract=PKSMP5 profile=sandybridge_x87_sse_four_vcpu aps=3 simultaneous_online=1 partial_start_timeout=1 partial_rollback=1 fresh_retry=1 target_mask=0x000000000000000E ack_mask=0x000000000000000E tlb_invalidations=3 no_reuse_before_all_acks=1 stop_quiesced=3 ap_parked=3 resources_released=102 scheduler=0 general_broadcast=0 target_hardware=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");
pksmp5_fragment!(PKSMP5_ENABLED, b" enabled=");
pksmp5_fragment!(PKSMP5_BSP_APIC_ID, b" bsp_apic_id=");
pksmp5_fragment!(PKSMP5_TARGET_APIC_IDS, b" target_apic_ids=");
pksmp5_fragment!(PKSMP5_COMMA, b",");
pksmp5_fragment!(PKSMP5_TARGET_MASK, b" target_mask=");
pksmp5_fragment!(PKSMP5_APIC_PHYSICAL, b" apic_physical=");
pksmp5_fragment!(
    PKSMP5_TOPOLOGY_TAIL,
    b" selection=exact_enabled_legacy_apic_topology\n"
);
pksmp5_fragment!(PKSMP5_TIMEOUT_APIC_ID, b" timeout_apic_id=");
pksmp5_fragment!(PKSMP5_TIMEOUT_MASK, b" timeout_mask=");
pksmp5_fragment!(PKSMP5_TIMEOUT_COUNT, b" timeout_count=");
pksmp5_fragment!(PKSMP5_PARKED_MASK, b" parked_mask=");
pksmp5_fragment!(PKSMP5_RELEASED_MASK, b" released_mask=");
pksmp5_fragment!(PKSMP5_RESOURCE_PAGES, b" resource_pages=");
pksmp5_fragment!(PKSMP5_FRAME_PAGES, b" frame_pages=");
pksmp5_fragment!(PKSMP5_ZEROED_BYTES, b" zeroed_bytes=");
pksmp5_fragment!(PKSMP5_VERIFIED_BYTES, b" verified_bytes=");
pksmp5_fragment!(PKSMP5_PARTIAL_TAIL, b" fresh_allocation_required=1\n");
pksmp5_fragment!(PKSMP5_PARTIAL_ROLLBACK_COUNT, b" partial_rollback_count=");
pksmp5_fragment!(PKSMP5_STARTED_MASK, b" started_mask=");
pksmp5_fragment!(PKSMP5_ONLINE_MASK, b" online_mask=");
pksmp5_fragment!(PKSMP5_RETRY_TAIL, b" simultaneous_online=1\n");
pksmp5_fragment!(PKSMP5_APIC_ID, b" apic_id=");
pksmp5_fragment!(PKSMP5_PHYSICAL_START, b" physical_start=");
pksmp5_fragment!(PKSMP5_PAGES, b" pages=");
pksmp5_fragment!(PKSMP5_SIPI_VECTOR, b" sipi_vector=");
pksmp5_fragment!(PKSMP5_TRAMPOLINE_BYTES, b" trampoline_bytes=");
pksmp5_fragment!(PKSMP5_ALLOCATION_SEQUENCE, b" allocation_sequence=");
pksmp5_fragment!(
    PKSMP5_FRAME_ALLOCATION_SEQUENCES,
    b" frame_allocation_sequences="
);
pksmp5_fragment!(PKSMP5_FRAME_RELEASE_SEQUENCES, b" frame_release_sequences=");
pksmp5_fragment!(
    PKSMP5_RESOURCE_RELEASE_SEQUENCE,
    b" resource_release_sequence="
);
pksmp5_fragment!(PKSMP5_SERVICE_STATE, b" service_state=");
pksmp5_fragment!(PKSMP5_MAILBOX_STATE, b" mailbox_state=");
pksmp5_fragment!(PKSMP5_RUNTIME_STATE, b" runtime_state=");
pksmp5_fragment!(PKSMP5_DELIVERIES, b" deliveries=");
pksmp5_fragment!(PKSMP5_ACCEPTED, b" accepted=");
pksmp5_fragment!(PKSMP5_DENIED_COUNT, b" denied=");
pksmp5_fragment!(PKSMP5_EOIS, b" eois=");
pksmp5_fragment!(PKSMP5_DIAGNOSTIC, b" diagnostic=");
pksmp5_fragment!(PKSMP5_SHOOTDOWN_COUNT, b" shootdown=");
pksmp5_fragment!(PKSMP5_STOP, b" stop=");
pksmp5_fragment!(PKSMP5_INIT_ASSERTS, b" init_asserts=");
pksmp5_fragment!(PKSMP5_INIT_DEASSERTS, b" init_deasserts=");
pksmp5_fragment!(PKSMP5_SIPIS, b" sipis=");
pksmp5_fragment!(PKSMP5_ACK_MASK, b" ack_mask=");
pksmp5_fragment!(PKSMP5_INVALIDATIONS, b" invalidations=");
pksmp5_fragment!(PKSMP5_BASELINE_CHECKSUM, b" baseline_checksum=");
pksmp5_fragment!(PKSMP5_RUNTIME_CHECKSUM, b" runtime_checksum=");
pksmp5_fragment!(PKSMP5_RESPONSE_CHECKSUM, b" response_checksum=");
pksmp5_fragment!(
    PKSMP5_AP_TAIL,
    b" tss_busy=1 idt_verified=1 xstate_verified=1 apic_table_verified=1 parked=1\n"
);
pksmp5_fragment!(PKSMP5_RETIRED_GENERATION, b" retired_generation=");
pksmp5_fragment!(PKSMP5_ACTIVE_GENERATION, b" active_generation=");
pksmp5_fragment!(PKSMP5_ROOT_CHECKSUM, b" root_checksum=");
pksmp5_fragment!(PKSMP5_OLD_FRAME_CHECKSUM, b" old_frame_checksum=");
pksmp5_fragment!(PKSMP5_NEW_FRAME_CHECKSUM, b" new_frame_checksum=");
pksmp5_fragment!(
    PKSMP5_PREMATURE_RECLAIM_REJECTIONS,
    b" premature_reclaim_rejections="
);
pksmp5_fragment!(PKSMP5_SHOOTDOWN_TAIL, b" reclaim_state=released\n");
pksmp5_fragment!(PKSMP5_QUIESCED_MASK, b" quiesced_mask=");
pksmp5_fragment!(PKSMP5_VALIDATED_MASK, b" validated_mask=");
pksmp5_fragment!(PKSMP5_RETRY_COUNT, b" retry_count=");
pksmp5_fragment!(PKSMP5_LIFECYCLE_TAIL, b" exact_accounting=1\n");
pksmp5_fragment!(PKSMP5_RESOURCE_ZEROED_BYTES, b" resource_zeroed_bytes=");
pksmp5_fragment!(PKSMP5_RESOURCE_VERIFIED_BYTES, b" resource_verified_bytes=");
pksmp5_fragment!(PKSMP5_FRAME_ZEROED_BYTES, b" frame_zeroed_bytes=");
pksmp5_fragment!(PKSMP5_FRAME_VERIFIED_BYTES, b" frame_verified_bytes=");
pksmp5_fragment!(PKSMP5_TOTAL_PAGES, b" total_pages=");
pksmp5_fragment!(PKSMP5_RELEASE_TAIL, b" capability_revoked=1 runtime_revoked=1 mmio_revoked=1 pic_restored=1 hpet_restored=1 apic_base_restored=unchanged\n");

macro_rules! pksched1_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pksched1_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pksched1_fragment!(PKSCHED1_EARLY, b"POOLEOS:KERNEL:SCHED-EARLY PASS contract=PKSCHED1 selector=15 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pksched1_fragment!(PKSCHED1_CORE, b"POOLEOS:KERNEL:SCHED-CORE PASS contract=PKSCHED1 cpu_capacity=4 task_capacity=8 active_tasks=2 queue_count=4 policy=fixed_priority_round_robin priorities=1-31 dispatches=8 migrations=0 wakes=0 teardowns=2 max_bypass=7 trace=0,1,0,1,0,1,0,1\n");
pksched1_fragment!(PKSCHED1_SWITCH, b"POOLEOS:KERNEL:SCHED-SWITCH PASS contract=PKSCHED1 tasks=2 dispatches=8 transitions=16 task0_runs=4 task1_runs=4 callee_saved=6 rflags=1 same_cr3=1 fs_gs_unchanged=1 xstate_unused=1 debug_unused=1 pmu_unused=1 stacks_distinct=1 stack_bytes=16384 alignment=16 errors=0\n");
pksched1_fragment!(PKSCHED1_CLEANUP, b"POOLEOS:KERNEL:SCHED-CLEANUP PASS contract=PKSCHED1 scheduler_lock_released=1 stack_bytes_cleared=32768 task_contexts_retired=2 queue_entries=0 running=0 blocked=0 dead=2\n");
pksched1_fragment!(PKSCHED1_RESULT, b"POOLEOS:KERNEL:SCHED-RESULT PASS contract=PKSCHED1 profile=qemu64_bsp_cooperative core=1 hardware_switch=1 bsp=1 smp_dispatch=0 preemption=0 ring3=0 address_spaces=1 xstate_switch=0 target=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");

macro_rules! pksched2_fragment {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pksched2_literals")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pksched2_fragment!(PKSCHED2_EARLY, b"POOLEOS:KERNEL:SCHED-PREEMPT-EARLY PASS contract=PKSCHED2 selector=16 parent_scheduler=PKSCHED1 parent_timer=PKIRQ1 bsp=1 if=0 stack=validated_by_wrapper serial=initialized\n");
pksched2_fragment!(
    PKSCHED2_DENIED,
    b"POOLEOS:KERNEL:SCHED-PREEMPT-DENIED contract=PKSCHED2 reason="
);
pksched2_fragment!(
    PKSCHED2_DENIED_TAIL,
    b" rollback=fail_closed authority=0 actions=0 production=0 terminal=panic\n"
);
pksched2_fragment!(
    PKSCHED2_ARM,
    b"POOLEOS:KERNEL:SCHED-PREEMPT-ARM PASS contract=PKSCHED2 timer_vector=64 one_shot_count="
);
pksched2_fragment!(PKSCHED2_FREQUENCY, b" apic_ticks_per_second=");
pksched2_fragment!(PKSCHED2_ARM_TAIL, b" quantum_ticks=2 tasks=4 deferred_capacity=8 events=3 stacks=4 stack_bytes=16384 ist=1 handler_if=0 interrupted_if=1\n");
pksched2_fragment!(PKSCHED2_TRACE, b"POOLEOS:KERNEL:SCHED-PREEMPT-TRACE PASS contract=PKSCHED2 ticks=6 next_trace=0,1,2,0,3,3 causes=none,quantum,wake,block,wake,none events=signal:2@3,block@4,cancel:3@5 runtime_ticks=3,1,1,1 quantum_reschedules=1 wake_reschedules=2 block_reschedules=1 frame_switches=4\n");
pksched2_fragment!(PKSCHED2_FRAME, b"POOLEOS:KERNEL:SCHED-PREEMPT-FRAME PASS contract=PKSCHED2 frames_saved=6 frames_restored=4 eois=6 nested=0 lock_contention=0 task_entries=1,1,1,1 launcher_transitions=2 same_cr3=1 fs_gs_unchanged=1 stack_ownership=exact\n");
pksched2_fragment!(PKSCHED2_CLEANUP, b"POOLEOS:KERNEL:SCHED-PREEMPT-CLEANUP PASS contract=PKSCHED2 timer_masked=1 controller_retired=1 contexts_cleared=4 stack_bytes_cleared=65536 tasks_dead=4 queue_entries=0 running=0 blocked=0 lock_released=1 apic_restored=1 pic_restored=1 hpet_restored=1 mmio_revoked=1\n");
pksched2_fragment!(PKSCHED2_RESULT, b"POOLEOS:KERNEL:SCHED-PREEMPT-RESULT PASS contract=PKSCHED2 profile=qemu64_bsp_interrupt_return preemption=timer_and_wakeup bsp=1 ap_dispatch=0 ring3=0 address_spaces=1 xstate_switch=0 target=0 signatures=0 authority=0 actions=0 production=0 terminal=halt\n");

struct SchedulerPreemptionRuntimeCell(UnsafeCell<Option<BspPreemption>>);

// SAFETY: selector 16 is BSP-only; IF and the scheduler lock serialize every access.
unsafe impl Sync for SchedulerPreemptionRuntimeCell {}

impl SchedulerPreemptionRuntimeCell {
    const fn new() -> Self {
        Self(UnsafeCell::new(None))
    }

    unsafe fn install(&self, controller: BspPreemption) -> Result<(), ()> {
        // SAFETY: the caller holds exclusive pre-launch ownership with IF clear.
        let slot = unsafe { &mut *self.0.get() };
        if slot.is_some() {
            return Err(());
        }
        *slot = Some(controller);
        Ok(())
    }

    unsafe fn with_mut<R>(&self, operation: impl FnOnce(&mut BspPreemption) -> R) -> Option<R> {
        // SAFETY: the interrupt gate cleared IF and the caller holds the scheduler lock.
        unsafe { (&mut *self.0.get()).as_mut().map(operation) }
    }

    unsafe fn take(&self) -> Option<BspPreemption> {
        // SAFETY: the timer is masked and IF is clear after bounded launcher return.
        unsafe { (&mut *self.0.get()).take() }
    }
}

struct SchedulerPreemptionContexts(UnsafeCell<[Option<TrapFrame>; 4]>);

// SAFETY: the same selector-16 BSP/IF/lock protocol serializes every frame access.
unsafe impl Sync for SchedulerPreemptionContexts {}

impl SchedulerPreemptionContexts {
    const fn new() -> Self {
        Self(UnsafeCell::new([None; 4]))
    }

    unsafe fn install(&self, contexts: [TrapFrame; 4]) {
        // SAFETY: installation occurs once before timer delivery is armed.
        unsafe { *self.0.get() = contexts.map(Some) };
    }

    unsafe fn save(&self, task: usize, frame: TrapFrame) -> Result<(), ()> {
        if task >= 4 {
            return Err(());
        }
        // SAFETY: the interrupt handler owns this task's stopped context.
        unsafe { (*self.0.get())[task] = Some(frame) };
        Ok(())
    }

    unsafe fn load(&self, task: usize) -> Option<TrapFrame> {
        if task >= 4 {
            return None;
        }
        // SAFETY: the scheduler selected this stopped context while holding the lock.
        unsafe { (*self.0.get())[task] }
    }

    unsafe fn clear(&self) -> usize {
        // SAFETY: no task context remains runnable after controller teardown.
        let contexts = unsafe { &mut *self.0.get() };
        let count = contexts.iter().filter(|value| value.is_some()).count();
        *contexts = [None; 4];
        count
    }
}

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
static IRQ_APIC_VIRTUAL: AtomicU64 = AtomicU64::new(0);
static IRQ_TIMER_DELIVERIES: AtomicU32 = AtomicU32::new(0);
static IRQ_EOI_COUNT: AtomicU32 = AtomicU32::new(0);
static IRQ_ERROR_COUNT: AtomicU32 = AtomicU32::new(0);
static IRQ_SPURIOUS_COUNT: AtomicU32 = AtomicU32::new(0);
static SMP_IPI_FAILURE_STAGE: AtomicU32 = AtomicU32::new(0);
static SMP_IPI_FAILURE_DETAIL: AtomicU64 = AtomicU64::new(0);
static SCHEDULER_SWITCH_LOCK: SchedulerRawSpinLock = SchedulerRawSpinLock::new();
static SCHEDULER_PREEMPT_RUNTIME: SchedulerPreemptionRuntimeCell =
    SchedulerPreemptionRuntimeCell::new();
static SCHEDULER_PREEMPT_CONTEXTS: SchedulerPreemptionContexts = SchedulerPreemptionContexts::new();
static SCHEDULER_PREEMPT_TIMER_COUNT: AtomicU32 = AtomicU32::new(0);
static SCHEDULER_PREEMPT_FRAME_SWITCHES: AtomicU32 = AtomicU32::new(0);
#[unsafe(no_mangle)]
static poole_scheduler_preempt_done: AtomicU32 = AtomicU32::new(0);

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
    reads: u64,
    temporary_pte_writes: u64,
    invalidations: u64,
    metadata_physical_start: Option<u64>,
    metadata_mapped_pages: u64,
    metadata_pte_writes: u64,
    metadata_guard_pages_verified: u64,
    metadata_mapping_rollbacks: u64,
    ledger_physical_start: [Option<u64>; 2],
    ledger_mapped_pages: [u64; 2],
    ledger_guard_pages_verified: [u64; 2],
    ledger_pte_writes: u64,
    ledger_mapping_rollbacks: u64,
    mmio_physical: [Option<u64>; 2],
    mmio_pte_writes: u64,
    mmio_guard_pages_verified: u64,
}

impl BootstrapTableMemory {
    const TEMPORARY_LEAF_INDEX: usize = poole_kmap::TEMPORARY_PAGE_INDEX;
    const TEMPORARY_ENTRY_FLAGS: u64 = (1 << 0) | (1 << 1) | (1 << 63);
    const UNCACHED_MMIO_ENTRY_FLAGS: u64 =
        Self::TEMPORARY_ENTRY_FLAGS | poole_kmap::ENTRY_PWT | poole_kmap::ENTRY_PCD;
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
        for index in Self::TEMPORARY_LEAF_INDEX..=poole_kmap::MMIO_GUARD_HIGH_PAGE {
            // SAFETY: the loop above proves that the retained leaf table is writable.
            let value = unsafe {
                read_volatile((active_leaf_table as usize as *const u64).wrapping_add(index))
            };
            if value != 0 {
                return Err(virtual_memory::Error::BootstrapLeafOccupied);
            }
        }
        Ok(Self {
            active_root,
            active_leaf_table,
            physical_address_bits,
            mapped_physical: None,
            writes: 0,
            reads: 0,
            temporary_pte_writes: 0,
            invalidations: 0,
            metadata_physical_start: None,
            metadata_mapped_pages: 0,
            metadata_pte_writes: 0,
            metadata_guard_pages_verified: 0,
            metadata_mapping_rollbacks: 0,
            ledger_physical_start: [None; 2],
            ledger_mapped_pages: [0; 2],
            ledger_guard_pages_verified: [0; 2],
            ledger_pte_writes: 0,
            ledger_mapping_rollbacks: 0,
            mmio_physical: [None; 2],
            mmio_pte_writes: 0,
            mmio_guard_pages_verified: 0,
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

    fn indexed_leaf_pointer(&self, index: usize) -> *mut u64 {
        (self.active_leaf_table as usize as *mut u64).wrapping_add(index)
    }

    fn invalidate_address(&mut self, virtual_address: u64) {
        // SAFETY: selectors 8 through 10 run at CPL0 on the BSP with interrupts disabled.
        unsafe { arch::x86_64::invalidate_page(virtual_address) };
        self.invalidations += 1;
    }

    fn invalidate(&mut self) {
        self.invalidate_address(virtual_memory::TEMPORARY_MAP_START);
    }

    fn mmio_guards_absent(&self) -> Result<(), virtual_memory::Error> {
        for (index, virtual_address) in [
            (
                poole_kmap::MMIO_GUARD_LOW_PAGE,
                virtual_memory::MMIO_GUARD_LOW_START,
            ),
            (
                poole_kmap::MMIO_GUARD_MIDDLE_PAGE,
                virtual_memory::MMIO_GUARD_MIDDLE_START,
            ),
            (
                poole_kmap::MMIO_GUARD_HIGH_PAGE,
                virtual_memory::MMIO_GUARD_HIGH_START,
            ),
        ] {
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            if unsafe { read_volatile(self.indexed_leaf_pointer(index)) } != 0
                || poole_kmap::translate(
                    &ActivePhysicalReader,
                    self.active_root,
                    virtual_address,
                    self.physical_address_bits,
                ) != Err(poole_kmap::Error::TranslationMissing)
            {
                return Err(virtual_memory::Error::BootstrapLeafState);
            }
        }
        Ok(())
    }

    fn install_uncached_mmio(
        &mut self,
        local_apic_physical: u64,
        hpet_physical: u64,
    ) -> Result<(u64, u64), virtual_memory::Error> {
        if self.mmio_physical != [None; 2]
            || local_apic_physical == 0
            || hpet_physical == 0
            || !local_apic_physical.is_multiple_of(poole_kmap::PAGE_SIZE)
            || !hpet_physical.is_multiple_of(poole_kmap::PAGE_SIZE)
            || local_apic_physical == hpet_physical
            || local_apic_physical & !Self::PHYSICAL_MASK_52 != 0
            || hpet_physical & !Self::PHYSICAL_MASK_52 != 0
        {
            return Err(virtual_memory::Error::BootstrapTargetAddress);
        }
        self.mmio_guards_absent()?;
        let mappings = [
            (
                poole_kmap::LOCAL_APIC_PAGE,
                virtual_memory::LOCAL_APIC_MAP_START,
                local_apic_physical,
            ),
            (
                poole_kmap::HPET_PAGE,
                virtual_memory::HPET_MAP_START,
                hpet_physical,
            ),
        ];
        for (slot, (index, virtual_address, physical_address)) in
            mappings.iter().copied().enumerate()
        {
            let leaf = self.indexed_leaf_pointer(index);
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            if unsafe { read_volatile(leaf) } != 0 {
                if slot != 0 {
                    self.uninstall_uncached_mmio_prefix(slot)?;
                }
                return Err(virtual_memory::Error::BootstrapLeafOccupied);
            }
            // SAFETY: PKIRQ1 exclusively owns these absent guarded leaf slots.
            unsafe { write_volatile(leaf, physical_address | Self::UNCACHED_MMIO_ENTRY_FLAGS) };
            self.temporary_pte_writes += 1;
            self.mmio_pte_writes += 1;
            self.invalidate_address(virtual_address);
            let translation = poole_kmap::translate(
                &ActivePhysicalReader,
                self.active_root,
                virtual_address,
                self.physical_address_bits,
            )
            .map_err(|_| virtual_memory::Error::BootstrapTranslation)?;
            if translation.physical_address != physical_address
                || !translation.writable
                || translation.executable
                || translation.user
                || !translation.cache.pwt
                || !translation.cache.pcd
                || translation.cache.pat
            {
                self.uninstall_uncached_mmio_prefix(slot + 1)?;
                return Err(virtual_memory::Error::BootstrapTranslation);
            }
            self.mmio_physical[slot] = Some(physical_address);
        }
        self.mmio_guard_pages_verified = 3;
        Ok((
            virtual_memory::LOCAL_APIC_MAP_START,
            virtual_memory::HPET_MAP_START,
        ))
    }

    fn uninstall_uncached_mmio_prefix(
        &mut self,
        installed: usize,
    ) -> Result<(), virtual_memory::Error> {
        let mappings = [
            (
                poole_kmap::LOCAL_APIC_PAGE,
                virtual_memory::LOCAL_APIC_MAP_START,
            ),
            (poole_kmap::HPET_PAGE, virtual_memory::HPET_MAP_START),
        ];
        for slot in (0..installed).rev() {
            let (index, virtual_address) = mappings[slot];
            let leaf = self.indexed_leaf_pointer(index);
            // SAFETY: this transaction installed and exclusively owns the leaf.
            unsafe { write_volatile(leaf, 0) };
            self.temporary_pte_writes += 1;
            self.mmio_pte_writes += 1;
            self.invalidate_address(virtual_address);
            self.mmio_physical[slot] = None;
        }
        self.mmio_guard_pages_verified = 0;
        self.mmio_guards_absent()
    }

    fn uninstall_uncached_mmio(&mut self) -> Result<(), virtual_memory::Error> {
        if self.mmio_physical.iter().any(Option::is_none) || self.mmio_guard_pages_verified != 3 {
            return Err(virtual_memory::Error::BootstrapLeafState);
        }
        self.uninstall_uncached_mmio_prefix(2)
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
        // SAFETY: the selected profile has exclusive ownership of the target frame,
        // and this leaf is outside kernel, stack, guard, and handoff mappings.
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

    fn revoke_temporary_mapping(&mut self) -> Result<(), virtual_memory::Error> {
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

    fn validate_active_uncached_mmio(&self) -> Result<(), virtual_memory::Error> {
        if self.mmio_physical.iter().any(Option::is_none) || self.mmio_guard_pages_verified != 3 {
            return Err(virtual_memory::Error::BootstrapLeafState);
        }
        self.mmio_guards_absent()?;
        for (slot, virtual_address) in [
            virtual_memory::LOCAL_APIC_MAP_START,
            virtual_memory::HPET_MAP_START,
        ]
        .into_iter()
        .enumerate()
        {
            let physical_address =
                self.mmio_physical[slot].ok_or(virtual_memory::Error::BootstrapLeafState)?;
            let translation = poole_kmap::translate(
                &ActivePhysicalReader,
                self.active_root,
                virtual_address,
                self.physical_address_bits,
            )
            .map_err(|_| virtual_memory::Error::BootstrapTranslation)?;
            if translation.physical_address != physical_address
                || !translation.writable
                || translation.executable
                || translation.user
                || !translation.cache.pwt
                || !translation.cache.pcd
                || translation.cache.pat
            {
                return Err(virtual_memory::Error::BootstrapTranslation);
            }
        }
        Ok(())
    }

    fn metadata_guards_absent(&self) -> Result<(), virtual_memory::Error> {
        for (index, virtual_address) in [
            (
                poole_kmap::METADATA_GUARD_LOW_PAGE,
                virtual_memory::METADATA_GUARD_LOW_START,
            ),
            (
                poole_kmap::METADATA_GUARD_HIGH_PAGE,
                virtual_memory::METADATA_GUARD_HIGH_START,
            ),
        ] {
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            if unsafe { read_volatile(self.indexed_leaf_pointer(index)) } != 0
                || poole_kmap::translate(
                    &ActivePhysicalReader,
                    self.active_root,
                    virtual_address,
                    self.physical_address_bits,
                ) != Err(poole_kmap::Error::TranslationMissing)
            {
                return Err(virtual_memory::Error::BootstrapLeafState);
            }
        }
        Ok(())
    }

    fn ledger_geometry(
        slot: u8,
    ) -> Result<(usize, u64, usize, u64, usize, u64), virtual_memory::Error> {
        match slot {
            0 => Ok((
                poole_kmap::LEDGER_A_GUARD_LOW_PAGE,
                virtual_memory::LEDGER_A_GUARD_LOW_START,
                poole_kmap::LEDGER_A_FIRST_PAGE,
                virtual_memory::LEDGER_A_MAP_START,
                poole_kmap::LEDGER_A_GUARD_HIGH_PAGE,
                virtual_memory::LEDGER_A_GUARD_HIGH_START,
            )),
            1 => Ok((
                poole_kmap::LEDGER_B_GUARD_LOW_PAGE,
                virtual_memory::LEDGER_B_GUARD_LOW_START,
                poole_kmap::LEDGER_B_FIRST_PAGE,
                virtual_memory::LEDGER_B_MAP_START,
                poole_kmap::LEDGER_B_GUARD_HIGH_PAGE,
                virtual_memory::LEDGER_B_GUARD_HIGH_START,
            )),
            _ => Err(virtual_memory::Error::BootstrapTargetAddress),
        }
    }

    fn ledger_guards_absent(&self, slot: u8) -> Result<(), virtual_memory::Error> {
        let (low_index, low_virtual, _, _, high_index, high_virtual) = Self::ledger_geometry(slot)?;
        for (index, virtual_address) in [(low_index, low_virtual), (high_index, high_virtual)] {
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            if unsafe { read_volatile(self.indexed_leaf_pointer(index)) } != 0
                || poole_kmap::translate(
                    &ActivePhysicalReader,
                    self.active_root,
                    virtual_address,
                    self.physical_address_bits,
                ) != Err(poole_kmap::Error::TranslationMissing)
            {
                return Err(virtual_memory::Error::BootstrapLeafState);
            }
        }
        Ok(())
    }

    fn rollback_ledger_prefix(
        &mut self,
        slot: u8,
        physical_address: u64,
        installed_pages: usize,
    ) -> Result<(), virtual_memory::Error> {
        let (_, _, first_page, virtual_start, _, _) = Self::ledger_geometry(slot)?;
        for offset in (0..installed_pages).rev() {
            let expected = physical_address
                .checked_add(offset as u64 * poole_kmap::PAGE_SIZE)
                .ok_or(virtual_memory::Error::BootstrapTargetAddress)?;
            let leaf = self.indexed_leaf_pointer(first_page + offset);
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            let observed = unsafe { read_volatile(leaf) };
            if observed & Self::PHYSICAL_MASK_52 != expected
                || observed & Self::TEMPORARY_ENTRY_FLAGS != Self::TEMPORARY_ENTRY_FLAGS
            {
                return Err(virtual_memory::Error::BootstrapLeafState);
            }
            // SAFETY: this transaction installed and exclusively owns the leaf.
            unsafe { write_volatile(leaf, 0) };
            self.temporary_pte_writes += 1;
            self.ledger_pte_writes += 1;
            self.invalidate_address(virtual_start + offset as u64 * poole_kmap::PAGE_SIZE);
        }
        self.ledger_guards_absent(slot)
    }

    fn rollback_metadata_prefix(
        &mut self,
        physical_address: u64,
        installed_pages: usize,
    ) -> Result<(), virtual_memory::Error> {
        for offset in (0..installed_pages).rev() {
            let expected = physical_address
                .checked_add(offset as u64 * poole_kmap::PAGE_SIZE)
                .ok_or(virtual_memory::Error::BootstrapTargetAddress)?;
            let leaf = self.indexed_leaf_pointer(poole_kmap::METADATA_FIRST_PAGE + offset);
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            let observed = unsafe { read_volatile(leaf) };
            if observed & Self::PHYSICAL_MASK_52 != expected
                || observed & Self::TEMPORARY_ENTRY_FLAGS != Self::TEMPORARY_ENTRY_FLAGS
            {
                return Err(virtual_memory::Error::BootstrapLeafState);
            }
            // SAFETY: this transaction installed and exclusively owns the leaf.
            unsafe { write_volatile(leaf, 0) };
            self.temporary_pte_writes += 1;
            self.metadata_pte_writes += 1;
            self.invalidate_address(
                virtual_memory::METADATA_MAP_START + offset as u64 * poole_kmap::PAGE_SIZE,
            );
        }
        self.metadata_mapping_rollbacks += 1;
        self.metadata_guards_absent()
    }
}

impl PhysicalPageAccess for BootstrapTableMemory {
    fn write_word(
        &mut self,
        physical_address: u64,
        word_index: usize,
        value: u64,
    ) -> Result<(), PageAccessError> {
        self.ensure_mapped(physical_address)
            .map_err(|_| PageAccessError::Access)?;
        let pointer = Self::target_pointer(word_index).map_err(|_| PageAccessError::Access)?;
        // SAFETY: PKPMM7 owns the planned, held, or still-live PMM extent and ensure_mapped
        // proves that its exact physical page occupies the supervisor RW/NX alias.
        unsafe { write_volatile(pointer, value) };
        self.writes = self.writes.checked_add(1).ok_or(PageAccessError::Access)?;
        Ok(())
    }

    fn read_word(
        &mut self,
        physical_address: u64,
        word_index: usize,
    ) -> Result<u64, PageAccessError> {
        self.ensure_mapped(physical_address)
            .map_err(|_| PageAccessError::Access)?;
        let pointer = Self::target_pointer(word_index).map_err(|_| PageAccessError::Access)?;
        // SAFETY: the same PKPMM7 ownership and temporary-alias proof as write_word
        // applies; volatile readback is required before the scrub receipt is minted.
        let value = unsafe { read_volatile(pointer) };
        self.reads = self.reads.checked_add(1).ok_or(PageAccessError::Access)?;
        Ok(value)
    }
}

impl interrupt_time::PhysicalRead for BootstrapTableMemory {
    fn read_word(
        &mut self,
        page_address: u64,
        word_index: usize,
    ) -> Result<u64, interrupt_time::Error> {
        PhysicalPageAccess::read_word(self, page_address, word_index)
            .map_err(|_| interrupt_time::Error::PhysicalAccess)
    }
}

impl MetadataArenaAccess for BootstrapTableMemory {
    fn install_metadata_arena(
        &mut self,
        physical_address: u64,
        page_count: u64,
    ) -> Result<u64, PageAccessError> {
        if self.metadata_physical_start.is_some()
            || page_count != METADATA_ARENA_PAGE_COUNT
            || page_count as usize != poole_kmap::METADATA_PAGE_COUNT
            || physical_address == 0
            || !physical_address.is_multiple_of(poole_kmap::PAGE_SIZE)
            || physical_address & !Self::PHYSICAL_MASK_52 != 0
        {
            return Err(PageAccessError::Access);
        }
        self.metadata_guards_absent()
            .map_err(|_| PageAccessError::Access)?;
        for offset in 0..poole_kmap::METADATA_PAGE_COUNT {
            let leaf = self.indexed_leaf_pointer(poole_kmap::METADATA_FIRST_PAGE + offset);
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            if unsafe { read_volatile(leaf) } != 0 {
                if offset != 0 {
                    self.rollback_metadata_prefix(physical_address, offset)
                        .map_err(|_| PageAccessError::Access)?;
                }
                return Err(PageAccessError::Access);
            }
            let physical = physical_address
                .checked_add(offset as u64 * poole_kmap::PAGE_SIZE)
                .ok_or(PageAccessError::Access)?;
            // SAFETY: the metadata transaction owns this absent leaf exclusively.
            unsafe { write_volatile(leaf, physical | Self::TEMPORARY_ENTRY_FLAGS) };
            self.temporary_pte_writes += 1;
            self.metadata_pte_writes += 1;
            let virtual_address =
                virtual_memory::METADATA_MAP_START + offset as u64 * poole_kmap::PAGE_SIZE;
            self.invalidate_address(virtual_address);
            let translation = poole_kmap::translate(
                &ActivePhysicalReader,
                self.active_root,
                virtual_address,
                self.physical_address_bits,
            );
            if !matches!(
                translation,
                Ok(value)
                    if value.physical_address == physical
                        && value.writable
                        && !value.executable
                        && !value.user
            ) {
                self.rollback_metadata_prefix(physical_address, offset + 1)
                    .map_err(|_| PageAccessError::Access)?;
                return Err(PageAccessError::Access);
            }
        }
        self.metadata_physical_start = Some(physical_address);
        self.metadata_mapped_pages = page_count;
        Ok(virtual_memory::METADATA_MAP_START)
    }

    fn finalize_metadata_handoff(
        &mut self,
        virtual_address: u64,
        manager_byte_count: u64,
    ) -> Result<(), PageAccessError> {
        let physical_address = self
            .metadata_physical_start
            .ok_or(PageAccessError::Access)?;
        if virtual_address != virtual_memory::METADATA_MAP_START
            || manager_byte_count == 0
            || manager_byte_count > METADATA_ARENA_PAGE_COUNT * poole_kmap::PAGE_SIZE
            || self.metadata_mapped_pages != METADATA_ARENA_PAGE_COUNT
        {
            return Err(PageAccessError::Access);
        }
        self.metadata_guards_absent()
            .map_err(|_| PageAccessError::Access)?;
        for offset in 0..poole_kmap::METADATA_PAGE_COUNT {
            let translation = poole_kmap::translate(
                &ActivePhysicalReader,
                self.active_root,
                virtual_address + offset as u64 * poole_kmap::PAGE_SIZE,
                self.physical_address_bits,
            )
            .map_err(|_| PageAccessError::Access)?;
            if translation.physical_address
                != physical_address + offset as u64 * poole_kmap::PAGE_SIZE
                || !translation.writable
                || translation.executable
                || translation.user
            {
                return Err(PageAccessError::Access);
            }
        }
        self.metadata_guard_pages_verified = 2;
        Ok(())
    }

    fn uninstall_metadata_arena(
        &mut self,
        virtual_address: u64,
        page_count: u64,
    ) -> Result<(), PageAccessError> {
        let physical_address = self
            .metadata_physical_start
            .ok_or(PageAccessError::Access)?;
        if virtual_address != virtual_memory::METADATA_MAP_START
            || page_count != METADATA_ARENA_PAGE_COUNT
            || self.metadata_mapped_pages != page_count
        {
            return Err(PageAccessError::Access);
        }
        self.rollback_metadata_prefix(physical_address, page_count as usize)
            .map_err(|_| PageAccessError::Access)?;
        self.metadata_physical_start = None;
        self.metadata_mapped_pages = 0;
        self.metadata_guard_pages_verified = 0;
        Ok(())
    }

    fn install_ledger_arena(
        &mut self,
        slot: u8,
        physical_address: u64,
        page_count: u64,
    ) -> Result<u64, PageAccessError> {
        let slot_index = usize::from(slot);
        let (_, _, first_page, virtual_start, _, _) =
            Self::ledger_geometry(slot).map_err(|_| PageAccessError::Access)?;
        if slot_index >= self.ledger_physical_start.len()
            || self.ledger_physical_start[slot_index].is_some()
            || page_count == 0
            || page_count > LEDGER_ARENA_PAGE_CAPACITY
            || physical_address == 0
            || !physical_address.is_multiple_of(poole_kmap::PAGE_SIZE)
            || physical_address & !Self::PHYSICAL_MASK_52 != 0
        {
            return Err(PageAccessError::Access);
        }
        self.ledger_guards_absent(slot)
            .map_err(|_| PageAccessError::Access)?;
        for offset in 0..page_count as usize {
            let leaf = self.indexed_leaf_pointer(first_page + offset);
            // SAFETY: new() proves the retained leaf table is identity-mapped.
            if unsafe { read_volatile(leaf) } != 0 {
                if offset != 0 {
                    self.rollback_ledger_prefix(slot, physical_address, offset)
                        .map_err(|_| PageAccessError::Access)?;
                    self.ledger_mapping_rollbacks += 1;
                }
                return Err(PageAccessError::Access);
            }
            let physical = physical_address
                .checked_add(offset as u64 * poole_kmap::PAGE_SIZE)
                .ok_or(PageAccessError::Access)?;
            // SAFETY: this ledger generation owns the absent leaf exclusively.
            unsafe { write_volatile(leaf, physical | Self::TEMPORARY_ENTRY_FLAGS) };
            self.temporary_pte_writes += 1;
            self.ledger_pte_writes += 1;
            let virtual_address = virtual_start + offset as u64 * poole_kmap::PAGE_SIZE;
            self.invalidate_address(virtual_address);
            let translation = poole_kmap::translate(
                &ActivePhysicalReader,
                self.active_root,
                virtual_address,
                self.physical_address_bits,
            );
            if !matches!(
                translation,
                Ok(value)
                    if value.physical_address == physical
                        && value.writable
                        && !value.executable
                        && !value.user
            ) {
                self.rollback_ledger_prefix(slot, physical_address, offset + 1)
                    .map_err(|_| PageAccessError::Access)?;
                self.ledger_mapping_rollbacks += 1;
                return Err(PageAccessError::Access);
            }
        }
        self.ledger_physical_start[slot_index] = Some(physical_address);
        self.ledger_mapped_pages[slot_index] = page_count;
        Ok(virtual_start)
    }

    fn finalize_ledger_arena(
        &mut self,
        slot: u8,
        virtual_address: u64,
        page_count: u64,
    ) -> Result<(), PageAccessError> {
        let slot_index = usize::from(slot);
        let (_, _, _, expected_virtual, _, _) =
            Self::ledger_geometry(slot).map_err(|_| PageAccessError::Access)?;
        let physical_address = self
            .ledger_physical_start
            .get(slot_index)
            .copied()
            .flatten()
            .ok_or(PageAccessError::Access)?;
        if virtual_address != expected_virtual
            || page_count == 0
            || page_count > LEDGER_ARENA_PAGE_CAPACITY
            || self.ledger_mapped_pages[slot_index] != page_count
        {
            return Err(PageAccessError::Access);
        }
        self.ledger_guards_absent(slot)
            .map_err(|_| PageAccessError::Access)?;
        for offset in 0..page_count as usize {
            let translation = poole_kmap::translate(
                &ActivePhysicalReader,
                self.active_root,
                virtual_address + offset as u64 * poole_kmap::PAGE_SIZE,
                self.physical_address_bits,
            )
            .map_err(|_| PageAccessError::Access)?;
            if translation.physical_address
                != physical_address + offset as u64 * poole_kmap::PAGE_SIZE
                || !translation.writable
                || translation.executable
                || translation.user
            {
                return Err(PageAccessError::Access);
            }
        }
        self.ledger_guard_pages_verified[slot_index] = LEDGER_GUARD_PAGE_COUNT;
        Ok(())
    }

    fn uninstall_ledger_arena(
        &mut self,
        slot: u8,
        virtual_address: u64,
        page_count: u64,
    ) -> Result<(), PageAccessError> {
        let slot_index = usize::from(slot);
        let (_, _, _, expected_virtual, _, _) =
            Self::ledger_geometry(slot).map_err(|_| PageAccessError::Access)?;
        let physical_address = self
            .ledger_physical_start
            .get(slot_index)
            .copied()
            .flatten()
            .ok_or(PageAccessError::Access)?;
        if virtual_address != expected_virtual
            || page_count == 0
            || self.ledger_mapped_pages[slot_index] != page_count
        {
            return Err(PageAccessError::Access);
        }
        self.rollback_ledger_prefix(slot, physical_address, page_count as usize)
            .map_err(|_| PageAccessError::Access)?;
        self.ledger_physical_start[slot_index] = None;
        self.ledger_mapped_pages[slot_index] = 0;
        self.ledger_guard_pages_verified[slot_index] = 0;
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
        self.revoke_temporary_mapping()?;
        self.metadata_guards_absent()?;
        match self.metadata_physical_start {
            Some(physical_address) => {
                if self.metadata_mapped_pages != METADATA_ARENA_PAGE_COUNT
                    || self.metadata_guard_pages_verified != 2
                {
                    return Err(virtual_memory::Error::BootstrapLeafState);
                }
                for offset in 0..poole_kmap::METADATA_PAGE_COUNT {
                    let translation = poole_kmap::translate(
                        &ActivePhysicalReader,
                        self.active_root,
                        virtual_memory::METADATA_MAP_START + offset as u64 * poole_kmap::PAGE_SIZE,
                        self.physical_address_bits,
                    )
                    .map_err(|_| virtual_memory::Error::BootstrapTranslation)?;
                    if translation.physical_address
                        != physical_address + offset as u64 * poole_kmap::PAGE_SIZE
                        || !translation.writable
                        || translation.executable
                        || translation.user
                    {
                        return Err(virtual_memory::Error::BootstrapTranslation);
                    }
                }
            }
            None => {
                if self.metadata_mapped_pages != 0 || self.metadata_guard_pages_verified != 0 {
                    return Err(virtual_memory::Error::BootstrapLeafState);
                }
            }
        }
        let mut active_ledgers = 0u64;
        for slot in 0..2u8 {
            self.ledger_guards_absent(slot)?;
            let index = usize::from(slot);
            match self.ledger_physical_start[index] {
                Some(physical_address) => {
                    active_ledgers += 1;
                    let page_count = self.ledger_mapped_pages[index];
                    if page_count == 0
                        || page_count > LEDGER_ARENA_PAGE_CAPACITY
                        || self.ledger_guard_pages_verified[index] != LEDGER_GUARD_PAGE_COUNT
                    {
                        return Err(virtual_memory::Error::BootstrapLeafState);
                    }
                    let (_, _, _, virtual_start, _, _) = Self::ledger_geometry(slot)?;
                    for offset in 0..page_count {
                        let translation = poole_kmap::translate(
                            &ActivePhysicalReader,
                            self.active_root,
                            virtual_start + offset * poole_kmap::PAGE_SIZE,
                            self.physical_address_bits,
                        )
                        .map_err(|_| virtual_memory::Error::BootstrapTranslation)?;
                        if translation.physical_address
                            != physical_address + offset * poole_kmap::PAGE_SIZE
                            || !translation.writable
                            || translation.executable
                            || translation.user
                        {
                            return Err(virtual_memory::Error::BootstrapTranslation);
                        }
                    }
                }
                None => {
                    if self.ledger_mapped_pages[index] != 0
                        || self.ledger_guard_pages_verified[index] != 0
                    {
                        return Err(virtual_memory::Error::BootstrapLeafState);
                    }
                }
            }
        }
        let expected_active_ledgers = u64::from(self.metadata_physical_start.is_some());
        if active_ledgers != expected_active_ledgers {
            return Err(virtual_memory::Error::BootstrapLeafState);
        }
        if self.mmio_physical != [None; 2] || self.mmio_guard_pages_verified != 0 {
            return Err(virtual_memory::Error::BootstrapLeafState);
        }
        self.mmio_guards_absent()?;
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

struct LiveInterruptHardware {
    local_apic_virtual: u64,
    hpet_virtual: u64,
}

impl LiveInterruptHardware {
    const APIC_REGISTER_LIMIT: u64 = 0x400;
    const HPET_REGISTER_LIMIT: u64 = 0x1000;

    fn apic_read(&self, offset: u64) -> Result<u32, interrupt_time::Error> {
        if offset >= Self::APIC_REGISTER_LIMIT || !offset.is_multiple_of(16) {
            return Err(interrupt_time::Error::TableAddress);
        }
        let address = self
            .local_apic_virtual
            .checked_add(offset)
            .ok_or(interrupt_time::Error::TableAddress)?;
        // SAFETY: PKIRQ1 maps exactly one guarded local-APIC page UC and validates offset.
        Ok(unsafe { read_volatile(address as usize as *const u32) })
    }

    fn apic_write(&mut self, offset: u64, value: u32) -> Result<(), interrupt_time::Error> {
        if offset >= Self::APIC_REGISTER_LIMIT || !offset.is_multiple_of(16) {
            return Err(interrupt_time::Error::TableAddress);
        }
        let address = self
            .local_apic_virtual
            .checked_add(offset)
            .ok_or(interrupt_time::Error::TableAddress)?;
        // SAFETY: PKIRQ1 maps exactly one guarded local-APIC page UC and owns the register.
        unsafe { write_volatile(address as usize as *mut u32, value) };
        Ok(())
    }

    fn hpet_read(&self, offset: u64) -> Result<u64, interrupt_time::Error> {
        if offset >= Self::HPET_REGISTER_LIMIT || !offset.is_multiple_of(8) {
            return Err(interrupt_time::Error::TableAddress);
        }
        let address = self
            .hpet_virtual
            .checked_add(offset)
            .ok_or(interrupt_time::Error::TableAddress)?;
        // SAFETY: PKIRQ1 maps exactly one guarded HPET page UC and validates offset.
        Ok(unsafe { read_volatile(address as usize as *const u64) })
    }

    fn hpet_write(&mut self, offset: u64, value: u64) -> Result<(), interrupt_time::Error> {
        if offset >= Self::HPET_REGISTER_LIMIT || !offset.is_multiple_of(8) {
            return Err(interrupt_time::Error::TableAddress);
        }
        let address = self
            .hpet_virtual
            .checked_add(offset)
            .ok_or(interrupt_time::Error::TableAddress)?;
        // SAFETY: PKIRQ1 maps exactly one guarded HPET page UC and owns configuration only.
        unsafe { write_volatile(address as usize as *mut u64, value) };
        Ok(())
    }

    fn in_service_count(&self) -> Result<u32, interrupt_time::Error> {
        let mut count = 0u32;
        for bank in 0..8u64 {
            count = count
                .checked_add(self.apic_read(0x100 + bank * 0x10)?.count_ones())
                .ok_or(interrupt_time::Error::TableShape)?;
        }
        Ok(count)
    }
}

const SMP_RESOURCE_OWNER: u16 = 0x534d;
const SMP_INIT_ASSERT_NANOSECONDS: u64 = 10_000_000;
const SMP_INTER_IPI_NANOSECONDS: u64 = 200_000;
const SMP_MAILBOX_TIMEOUT_NANOSECONDS: u64 = 100_000_000;
const SMP_HPET_POLL_LIMIT: u64 = 50_000_000;
const SMP_APIC_POLL_LIMIT: u64 = 2_000_000;
const SMP_APIC_ICR_LOW: u64 = 0x300;
const SMP_APIC_ICR_HIGH: u64 = 0x310;
const SMP_APIC_DELIVERY_PENDING: u32 = 1 << 12;
const SMP_APIC_INIT_ASSERT: u32 = 0x0000_c500;
const SMP_APIC_INIT_DEASSERT: u32 = 0x0000_8500;
const SMP_APIC_STARTUP: u32 = 0x0000_4600;

#[derive(Clone, Copy)]
struct SmpOperationProof {
    mailbox: MailboxSnapshot,
    init_asserts: u64,
    init_deasserts: u64,
    sipis: u64,
}

#[derive(Clone, Copy)]
struct SmpLiveProof {
    madt_bytes: u64,
    processor_count: u64,
    enabled_processor_count: u64,
    bsp_apic_id: u32,
    target_apic_id: u32,
    apic_physical: u64,
    hpet_physical: u64,
    layout: ResourceLayout,
    trampoline_bytes: u64,
    allocation_receipt: ScrubReceipt,
    release_receipt: ScrubReceipt,
    operation: SmpOperationProof,
}

fn smp_write_page_bytes(
    access: &mut BootstrapTableMemory,
    physical_address: u64,
    bytes: &[u8; smp::PAGE_BYTES as usize],
) -> Result<(), smp::Error> {
    for (word_index, chunk) in bytes.chunks_exact(8).enumerate() {
        let mut word = [0u8; 8];
        word.copy_from_slice(chunk);
        PhysicalPageAccess::write_word(
            access,
            physical_address,
            word_index,
            u64::from_le_bytes(word),
        )
        .map_err(|_| smp::Error::PhysicalAccess)?;
    }
    Ok(())
}

fn smp_prepare_resources(
    access: &mut BootstrapTableMemory,
    layout: ResourceLayout,
    bsp_apic_id: u32,
    target_apic_id: u32,
) -> Result<usize, smp::Error> {
    let (trampoline, trampoline_bytes) =
        arch::x86_64::build_ap_trampoline_page(layout).map_err(|_| smp::Error::Trampoline)?;
    smp_write_page_bytes(access, layout.trampoline(), &trampoline)?;

    TableMemory::write_entry(
        access,
        layout.pml4(),
        0,
        layout.pdpt() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    TableMemory::write_entry(
        access,
        layout.pdpt(),
        0,
        layout.page_directory() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    TableMemory::write_entry(
        access,
        layout.page_directory(),
        0,
        layout.page_table() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    for offset in 0..layout.page_count {
        if ResourceLayout::is_mapped_offset(offset) {
            let index = usize::try_from(layout.page_address(offset) / smp::PAGE_BYTES)
                .map_err(|_| smp::Error::ResourceAddress)?;
            TableMemory::write_entry(
                access,
                layout.page_table(),
                index,
                layout.leaf_entry(offset)?,
            )
            .map_err(|_| smp::Error::Memory)?;
        }
    }
    for offset in [
        smp::STACK_GUARD_LOW_OFFSET,
        smp::STACK_GUARD_HIGH_OFFSET,
        smp::PER_CPU_GUARD_LOW_OFFSET,
        smp::PER_CPU_GUARD_HIGH_OFFSET,
    ] {
        let index = usize::try_from(layout.page_address(offset) / smp::PAGE_BYTES)
            .map_err(|_| smp::Error::ResourceAddress)?;
        if TableMemory::read_entry(access, layout.page_table(), index)
            .map_err(|_| smp::Error::Memory)?
            != 0
        {
            return Err(smp::Error::PageRole);
        }
    }

    let prepared_words = [
        smp::MAILBOX_MAGIC,
        u64::from(smp::MAILBOX_VERSION) | (u64::from(smp::MAILBOX_STATE_PREPARED) << 32),
        u64::from(smp::MAILBOX_COMMAND_NONE) | (u64::from(target_apic_id) << 32),
        u64::from(bsp_apic_id),
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ];
    for (word_index, value) in prepared_words.into_iter().enumerate() {
        PhysicalPageAccess::write_word(access, layout.per_cpu(), word_index, value)
            .map_err(|_| smp::Error::PhysicalAccess)?;
    }
    access
        .ensure_mapped(layout.per_cpu())
        .map_err(|_| smp::Error::PhysicalAccess)?;
    if smp_mailbox_read_u64(smp::MAILBOX_MAGIC_OFFSET) != smp::MAILBOX_MAGIC
        || smp_mailbox_read_u32(smp::MAILBOX_VERSION_OFFSET) != smp::MAILBOX_VERSION
        || smp_mailbox_read_u32(smp::MAILBOX_STATE_OFFSET) != smp::MAILBOX_STATE_PREPARED
        || smp_mailbox_read_u32(smp::MAILBOX_TARGET_APIC_ID_OFFSET) != target_apic_id
        || smp_mailbox_read_u32(smp::MAILBOX_BSP_APIC_ID_OFFSET) != bsp_apic_id
    {
        return Err(smp::Error::MailboxShape);
    }
    Ok(trampoline_bytes)
}

fn smp_mailbox_address(offset: usize) -> usize {
    virtual_memory::TEMPORARY_MAP_START as usize + offset
}

fn smp_mailbox_read_u32(offset: usize) -> u32 {
    debug_assert!(offset + core::mem::size_of::<u32>() <= smp::MAILBOX_BYTES);
    // SAFETY: PKSMP1 keeps the per-CPU page in the private supervisor alias while the AP runs.
    unsafe { read_volatile(smp_mailbox_address(offset) as *const u32) }
}

fn smp_mailbox_read_u64(offset: usize) -> u64 {
    debug_assert!(offset + core::mem::size_of::<u64>() <= smp::MAILBOX_BYTES);
    // SAFETY: every u64 mailbox field is aligned and bounded inside the retained alias.
    unsafe { read_volatile(smp_mailbox_address(offset) as *const u64) }
}

fn smp_mailbox_write_u32(offset: usize, value: u32) {
    debug_assert!(offset + core::mem::size_of::<u32>() <= smp::MAILBOX_BYTES);
    // SAFETY: the BSP owns command writes and the AP owns only observation/state fields.
    unsafe { write_volatile(smp_mailbox_address(offset) as *mut u32, value) };
    arch::x86_64::memory_fence();
}

fn smp_mailbox_write_u64(offset: usize, value: u64) {
    debug_assert!(offset + core::mem::size_of::<u64>() <= smp::MAILBOX_BYTES);
    // SAFETY: the BSP writes the checksum only after observing the AP's quiesced state.
    unsafe { write_volatile(smp_mailbox_address(offset) as *mut u64, value) };
    arch::x86_64::memory_fence();
}

fn smp_mailbox_snapshot() -> MailboxSnapshot {
    arch::x86_64::memory_fence();
    MailboxSnapshot {
        magic: smp_mailbox_read_u64(smp::MAILBOX_MAGIC_OFFSET),
        version: smp_mailbox_read_u32(smp::MAILBOX_VERSION_OFFSET),
        state: smp_mailbox_read_u32(smp::MAILBOX_STATE_OFFSET),
        command: smp_mailbox_read_u32(smp::MAILBOX_COMMAND_OFFSET),
        target_apic_id: smp_mailbox_read_u32(smp::MAILBOX_TARGET_APIC_ID_OFFSET),
        bsp_apic_id: smp_mailbox_read_u32(smp::MAILBOX_BSP_APIC_ID_OFFSET),
        observed_apic_id: smp_mailbox_read_u32(smp::MAILBOX_OBSERVED_APIC_ID_OFFSET),
        leaf1_ecx: smp_mailbox_read_u32(smp::MAILBOX_LEAF1_ECX_OFFSET),
        leaf1_edx: smp_mailbox_read_u32(smp::MAILBOX_LEAF1_EDX_OFFSET),
        cr0: smp_mailbox_read_u64(smp::MAILBOX_CR0_OFFSET),
        cr3: smp_mailbox_read_u64(smp::MAILBOX_CR3_OFFSET),
        cr4: smp_mailbox_read_u64(smp::MAILBOX_CR4_OFFSET),
        efer: smp_mailbox_read_u64(smp::MAILBOX_EFER_OFFSET),
        tsc_online: smp_mailbox_read_u64(smp::MAILBOX_TSC_ONLINE_OFFSET),
        tsc_stop: smp_mailbox_read_u64(smp::MAILBOX_TSC_STOP_OFFSET),
        checksum: smp_mailbox_read_u64(smp::MAILBOX_CHECKSUM_OFFSET),
    }
}

fn smp_hpet_period(hardware: &LiveInterruptHardware) -> Result<u64, smp::Error> {
    let capabilities = hardware.hpet_read(0).map_err(|_| smp::Error::Hpet)?;
    let period = capabilities >> 32;
    if capabilities & (1 << 13) == 0 || period == 0 || period > 100_000_000 {
        return Err(smp::Error::Hpet);
    }
    Ok(period)
}

fn smp_hpet_ticks(nanoseconds: u64, period_femtoseconds: u64) -> Result<u64, smp::Error> {
    let femtoseconds = u128::from(nanoseconds)
        .checked_mul(1_000_000)
        .ok_or(smp::Error::Hpet)?;
    let period = u128::from(period_femtoseconds);
    let ticks = femtoseconds
        .checked_add(period - 1)
        .ok_or(smp::Error::Hpet)?
        / period;
    u64::try_from(ticks.max(1)).map_err(|_| smp::Error::Hpet)
}

fn smp_hpet_wait(
    hardware: &LiveInterruptHardware,
    period_femtoseconds: u64,
    nanoseconds: u64,
) -> Result<(), smp::Error> {
    let target = smp_hpet_ticks(nanoseconds, period_femtoseconds)?;
    let start = hardware.hpet_read(0xf0).map_err(|_| smp::Error::Hpet)?;
    for _ in 0..SMP_HPET_POLL_LIMIT {
        let current = hardware.hpet_read(0xf0).map_err(|_| smp::Error::Hpet)?;
        if current.wrapping_sub(start) >= target {
            return Ok(());
        }
        core::hint::spin_loop();
    }
    Err(smp::Error::Timeout)
}

fn smp_wait_mailbox_state(
    hardware: &LiveInterruptHardware,
    period_femtoseconds: u64,
    prior: u32,
    expected: u32,
) -> Result<(), smp::Error> {
    let target = smp_hpet_ticks(SMP_MAILBOX_TIMEOUT_NANOSECONDS, period_femtoseconds)?;
    let start = hardware.hpet_read(0xf0).map_err(|_| smp::Error::Hpet)?;
    for _ in 0..SMP_HPET_POLL_LIMIT {
        let state = smp_mailbox_read_u32(smp::MAILBOX_STATE_OFFSET);
        if state == expected {
            arch::x86_64::memory_fence();
            return Ok(());
        }
        if state == u32::MAX {
            return Err(smp::Error::MailboxState);
        }
        if state != prior {
            return Err(smp::Error::MailboxState);
        }
        let current = hardware.hpet_read(0xf0).map_err(|_| smp::Error::Hpet)?;
        if current.wrapping_sub(start) >= target {
            return Err(smp::Error::Timeout);
        }
        core::hint::spin_loop();
    }
    Err(smp::Error::Timeout)
}

fn smp_apic_wait_idle(hardware: &LiveInterruptHardware) -> Result<(), smp::Error> {
    for _ in 0..SMP_APIC_POLL_LIMIT {
        if hardware
            .apic_read(SMP_APIC_ICR_LOW)
            .map_err(|_| smp::Error::Apic)?
            & SMP_APIC_DELIVERY_PENDING
            == 0
        {
            return Ok(());
        }
        core::hint::spin_loop();
    }
    Err(smp::Error::Timeout)
}

fn smp_apic_command(
    hardware: &mut LiveInterruptHardware,
    target_apic_id: u32,
    command: u32,
) -> Result<(), smp::Error> {
    if target_apic_id > u32::from(u8::MAX) {
        return Err(smp::Error::TargetApicId);
    }
    smp_apic_wait_idle(hardware)?;
    hardware
        .apic_write(SMP_APIC_ICR_HIGH, target_apic_id << 24)
        .map_err(|_| smp::Error::Apic)?;
    hardware
        .apic_write(SMP_APIC_ICR_LOW, command)
        .map_err(|_| smp::Error::Apic)?;
    smp_apic_wait_idle(hardware)
}

fn smp_init_sequence(
    hardware: &mut LiveInterruptHardware,
    target_apic_id: u32,
    period_femtoseconds: u64,
) -> Result<(), smp::Error> {
    smp_apic_command(hardware, target_apic_id, SMP_APIC_INIT_ASSERT)?;
    smp_hpet_wait(hardware, period_femtoseconds, SMP_INIT_ASSERT_NANOSECONDS)?;
    smp_apic_command(hardware, target_apic_id, SMP_APIC_INIT_DEASSERT)?;
    smp_hpet_wait(hardware, period_femtoseconds, SMP_INTER_IPI_NANOSECONDS)
}

fn smp_release_resources(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    allocation: poolekernel::physical_memory::AllocationHandle,
) -> Result<ScrubReceipt, smp::Error> {
    TableMemory::finish(access).map_err(|_| smp::Error::PhysicalAccess)?;
    let receipt = manager
        .free_scrubbed(allocation, access)
        .map_err(|_| smp::Error::Memory)?;
    TableMemory::finish(access).map_err(|_| smp::Error::PhysicalAccess)?;
    let expected_bytes = smp::RESOURCE_PAGE_COUNT
        .checked_mul(smp::PAGE_BYTES)
        .ok_or(smp::Error::ResourceAddress)?;
    if receipt.kind != ScrubKind::Release
        || receipt.page_count != smp::RESOURCE_PAGE_COUNT
        || receipt.zeroed_bytes != expected_bytes
        || receipt.verified_bytes != expected_bytes
    {
        return Err(smp::Error::Rollback);
    }
    Ok(receipt)
}

fn run_smp_first_ap(
    handoff: &poole_handoff::Handoff<'_>,
    core: poole_handoff::CoreRecord,
    observed_cr3: u64,
) -> Result<SmpLiveProof, smp::Error> {
    let physical_bits = arch::x86_64::physical_address_bits().ok_or(smp::Error::Memory)?;
    let mut page_access =
        BootstrapTableMemory::new(observed_cr3, physical_bits).map_err(|_| smp::Error::Memory)?;
    let mut manager = PhysicalMemoryManager::from_handoff(handoff, core, DEFAULT_QUOTA_PAGES)
        .map_err(|_| smp::Error::Memory)?;
    manager
        .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
        .map_err(|_| smp::Error::Memory)?;
    let acpi_snapshot = acpi::consume_required_tables(handoff, &mut manager, &mut page_access)
        .map_err(smp::Error::Acpi)?;
    let madt_receipt = acpi_snapshot.required_tables[0];
    let hpet_receipt = acpi_snapshot.required_tables[2];
    let madt_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(madt_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let hpet_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(hpet_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let topology = parse_madt(&mut page_access, madt_snapshot, madt_receipt.byte_count)
        .map_err(|_| smp::Error::Madt)?;
    let hpet = parse_hpet(&mut page_access, hpet_snapshot, hpet_receipt.byte_count)
        .map_err(|_| smp::Error::Hpet)?;
    if !hpet.counter_64_bit_capable {
        return Err(smp::Error::Hpet);
    }

    let cpu = arch::x86_64::observe_apic_cpu();
    if !cpu.apic_supported {
        return Err(smp::Error::Apic);
    }
    // SAFETY: CPUID reports APIC and this selector runs at CPL0 with IF clear.
    let original_apic_base = unsafe { arch::x86_64::read_local_apic_base() };
    if original_apic_base & (APIC_BASE_ENABLE | APIC_BASE_X2APIC) != APIC_BASE_ENABLE {
        return Err(smp::Error::Apic);
    }
    let apic_physical = original_apic_base & interrupt_time::APIC_BASE_ADDRESS_MASK;
    if apic_physical != topology.local_apic_address {
        return Err(smp::Error::Apic);
    }
    let target = smp::select_first_ap(&topology, cpu.initial_apic_id)?;

    let (allocation, allocation_receipt) = manager
        .allocate_scrubbed(
            Zone::Dma,
            smp::RESOURCE_PAGE_COUNT,
            SMP_RESOURCE_OWNER,
            &mut page_access,
        )
        .map_err(|_| smp::Error::Memory)?;
    let layout = ResourceLayout::new(allocation.start_page, allocation.page_count)?;
    let mut transaction = smp::FirstApTransaction::new();
    transaction.reserve()?;
    let trampoline_bytes = match smp_prepare_resources(
        &mut page_access,
        layout,
        cpu.initial_apic_id,
        target.apic_id,
    ) {
        Ok(value) => value,
        Err(error) => {
            smp_release_resources(&mut manager, &mut page_access, allocation)?;
            let _ = transaction.rollback(false)?;
            return Err(error);
        }
    };
    transaction.prepare()?;

    let hpet_page = hpet.physical_address & !0xfff;
    let (apic_virtual, hpet_page_virtual) =
        match page_access.install_uncached_mmio(apic_physical, hpet_page) {
            Ok(value) => value,
            Err(_) => {
                smp_release_resources(&mut manager, &mut page_access, allocation)?;
                let _ = transaction.rollback(false)?;
                return Err(smp::Error::PhysicalAccess);
            }
        };
    let hpet_virtual = hpet_page_virtual
        .checked_add(hpet.physical_address & 0xfff)
        .ok_or(smp::Error::Hpet)?;
    let mut hardware = LiveInterruptHardware {
        local_apic_virtual: apic_virtual,
        hpet_virtual,
    };

    let mut original_hpet_config = None;
    let mut pic_masks = None;
    let mut hpet_changed = false;
    let mut ap_started = false;
    let mut period_femtoseconds = None;
    let operation_result = (|| -> Result<SmpOperationProof, smp::Error> {
        let discovery = validate_apic_discovery(
            &topology,
            cpu,
            original_apic_base,
            hardware.apic_read(0x20).map_err(|_| smp::Error::Apic)?,
            hardware.apic_read(0x30).map_err(|_| smp::Error::Apic)?,
        )
        .map_err(|_| smp::Error::Apic)?;
        if !discovery.bsp || !discovery.globally_enabled || discovery.apic_id != cpu.initial_apic_id
        {
            return Err(smp::Error::Apic);
        }
        let period = smp_hpet_period(&hardware)?;
        period_femtoseconds = Some(period);
        let hpet_config = hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)?;
        original_hpet_config = Some(hpet_config);
        if topology.pcat_compatible {
            // SAFETY: IF is clear and PKSMP1 restores the exact two mask bytes during cleanup.
            pic_masks = Some(
                unsafe { arch::x86_64::mask_legacy_pic() }
                    .map_err(|_| smp::Error::PhysicalAccess)?,
            );
        }
        if hpet_config & 1 == 0 {
            hardware
                .hpet_write(0x10, hpet_config | 1)
                .map_err(|_| smp::Error::Hpet)?;
            hpet_changed = true;
            if hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)? != hpet_config | 1 {
                return Err(smp::Error::Hpet);
            }
        }

        let (bsp_leaf1_ecx, bsp_leaf1_edx) = arch::x86_64::observe_leaf1_features();
        if bsp_leaf1_edx & smp::REQUIRED_LEAF1_EDX != smp::REQUIRED_LEAF1_EDX {
            return Err(smp::Error::FeatureMismatch);
        }
        let bsp_tsc_before = arch::x86_64::read_tsc_ordered();
        smp_init_sequence(&mut hardware, target.apic_id, period)?;
        transaction.init_sent()?;
        ap_started = true;
        smp_apic_command(
            &mut hardware,
            target.apic_id,
            SMP_APIC_STARTUP | u32::from(layout.sipi_vector()),
        )?;
        smp_hpet_wait(&hardware, period, SMP_INTER_IPI_NANOSECONDS)?;
        smp_apic_command(
            &mut hardware,
            target.apic_id,
            SMP_APIC_STARTUP | u32::from(layout.sipi_vector()),
        )?;
        smp_hpet_wait(&hardware, period, SMP_INTER_IPI_NANOSECONDS)?;
        transaction.startup_sent()?;
        smp_wait_mailbox_state(
            &hardware,
            period,
            smp::MAILBOX_STATE_PREPARED,
            smp::MAILBOX_STATE_ONLINE,
        )?;
        let bsp_tsc_after = arch::x86_64::read_tsc_ordered();
        transaction.online()?;
        smp_mailbox_write_u32(smp::MAILBOX_COMMAND_OFFSET, smp::MAILBOX_COMMAND_STOP);
        smp_wait_mailbox_state(
            &hardware,
            period,
            smp::MAILBOX_STATE_ONLINE,
            smp::MAILBOX_STATE_QUIESCED,
        )?;
        transaction.quiesced()?;
        let mut mailbox = smp_mailbox_snapshot();
        mailbox.checksum = smp::mailbox_checksum(&mailbox);
        smp_mailbox_write_u64(smp::MAILBOX_CHECKSUM_OFFSET, mailbox.checksum);
        mailbox = smp_mailbox_snapshot();
        smp::validate_mailbox(
            &mailbox,
            layout,
            bsp_leaf1_ecx,
            bsp_leaf1_edx,
            bsp_tsc_before,
            bsp_tsc_after,
        )?;
        Ok(SmpOperationProof {
            mailbox,
            init_asserts: 1,
            init_deasserts: 1,
            sipis: 2,
        })
    })();

    let park_result = if ap_started {
        match period_femtoseconds {
            Some(period) => smp_init_sequence(&mut hardware, target.apic_id, period),
            None => Err(smp::Error::Rollback),
        }
    } else {
        Ok(())
    };
    if park_result.is_err() {
        if let (true, Some(config)) = (hpet_changed, original_hpet_config) {
            let _ = hardware.hpet_write(0x10, config);
        }
        if let Some(masks) = pic_masks {
            // SAFETY: IF remains clear; retaining AP resources takes precedence on failure.
            let _ = unsafe { arch::x86_64::restore_legacy_pic(masks) };
        }
        return Err(smp::Error::Rollback);
    }
    if operation_result.is_ok() {
        transaction.parked()?;
    }

    let mut cleanup_error = None;
    if let (true, Some(config)) = (hpet_changed, original_hpet_config) {
        let restore_failed = hardware.hpet_write(0x10, config).is_err()
            || hardware.hpet_read(0x10).ok() != Some(config);
        if restore_failed {
            cleanup_error = Some(smp::Error::Hpet);
        }
    }
    if let Some(masks) = pic_masks {
        // SAFETY: the AP is reset, IF is clear, and these are the exact observed masks.
        if unsafe { arch::x86_64::restore_legacy_pic(masks) }.is_err() {
            cleanup_error = Some(smp::Error::PhysicalAccess);
        }
    }
    if page_access.uninstall_uncached_mmio().is_err() {
        cleanup_error = Some(smp::Error::PhysicalAccess);
    }
    let release_receipt = match smp_release_resources(&mut manager, &mut page_access, allocation) {
        Ok(value) => value,
        Err(error) => {
            cleanup_error = Some(error);
            allocation_receipt
        }
    };

    match operation_result {
        Err(error) => {
            let _ = transaction.rollback(true)?;
            Err(cleanup_error.unwrap_or(error))
        }
        Ok(operation) => {
            if let Some(error) = cleanup_error {
                return Err(error);
            }
            transaction.released()?;
            Ok(SmpLiveProof {
                madt_bytes: madt_receipt.byte_count,
                processor_count: topology.processor_count as u64,
                enabled_processor_count: topology.enabled_processor_count as u64,
                bsp_apic_id: cpu.initial_apic_id,
                target_apic_id: target.apic_id,
                apic_physical,
                hpet_physical: hpet.physical_address,
                layout,
                trampoline_bytes: trampoline_bytes as u64,
                allocation_receipt,
                release_receipt,
                operation,
            })
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SmpRuntimeLiveError {
    Base(smp::Error),
    Runtime(smp_runtime::Error),
}

impl SmpRuntimeLiveError {
    const fn label(self) -> &'static str {
        match self {
            Self::Base(error) => error.label(),
            Self::Runtime(error) => error.label(),
        }
    }
}

impl From<smp::Error> for SmpRuntimeLiveError {
    fn from(value: smp::Error) -> Self {
        Self::Base(value)
    }
}

impl From<smp_runtime::Error> for SmpRuntimeLiveError {
    fn from(value: smp_runtime::Error) -> Self {
        Self::Runtime(value)
    }
}

#[derive(Clone, Copy)]
struct SmpRuntimeOperationProof {
    mailbox: RuntimeMailboxSnapshot,
    init_asserts: u64,
    init_deasserts: u64,
    sipis: u64,
    tss_busy_verified: bool,
    idt_verified: bool,
    xstate_verified: bool,
}

#[derive(Clone, Copy)]
struct SmpRuntimeLiveProof {
    madt_bytes: u64,
    processor_count: u64,
    enabled_processor_count: u64,
    bsp_apic_id: u32,
    target_apic_id: u32,
    apic_physical: u64,
    hpet_physical: u64,
    layout: smp_runtime::ResourceLayout,
    trampoline_bytes: u64,
    allocation_receipt: ScrubReceipt,
    release_receipt: ScrubReceipt,
    operation: SmpRuntimeOperationProof,
}

fn smp_runtime_put_u32(
    page: &mut [u8; smp_runtime::PAGE_BYTES as usize],
    offset: usize,
    value: u32,
) {
    page[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn smp_runtime_put_u64(
    page: &mut [u8; smp_runtime::PAGE_BYTES as usize],
    offset: usize,
    value: u64,
) {
    page[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}

fn smp_runtime_prepare_resources(
    access: &mut BootstrapTableMemory,
    layout: smp_runtime::ResourceLayout,
    bsp_apic_id: u32,
    target_apic_id: u32,
) -> Result<(usize, u64), SmpRuntimeLiveError> {
    let (trampoline, trampoline_bytes, fault_handler) =
        arch::x86_64::build_ap_runtime_trampoline_page(layout)
            .map_err(|_| smp::Error::Trampoline)?;
    smp_write_page_bytes(access, layout.trampoline(), &trampoline)?;
    let descriptor = smp_runtime::build_descriptor_page(layout);
    smp_write_page_bytes(
        access,
        layout.page_address(smp_runtime::DESCRIPTOR_PAGE_OFFSET),
        &descriptor,
    )?;
    let idt = smp_runtime::build_idt_page(layout, fault_handler)?;
    smp_write_page_bytes(access, layout.idt(), &idt)?;

    TableMemory::write_entry(
        access,
        layout.pml4(),
        0,
        layout.pdpt() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    TableMemory::write_entry(
        access,
        layout.pdpt(),
        0,
        layout.page_directory() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    TableMemory::write_entry(
        access,
        layout.page_directory(),
        0,
        layout.page_table() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    for offset in 0..layout.page_count {
        if smp_runtime::ResourceLayout::is_mapped_offset(offset) {
            let index = usize::try_from(layout.page_address(offset) / smp_runtime::PAGE_BYTES)
                .map_err(|_| smp_runtime::Error::ResourceAddress)?;
            TableMemory::write_entry(
                access,
                layout.page_table(),
                index,
                layout.leaf_entry(offset)?,
            )
            .map_err(|_| smp::Error::Memory)?;
        }
    }
    for offset in 0..layout.page_count {
        if smp_runtime::ResourceLayout::is_mapped_offset(offset) {
            continue;
        }
        let index = usize::try_from(layout.page_address(offset) / smp_runtime::PAGE_BYTES)
            .map_err(|_| smp_runtime::Error::ResourceAddress)?;
        if TableMemory::read_entry(access, layout.page_table(), index)
            .map_err(|_| smp::Error::Memory)?
            != 0
        {
            return Err(smp_runtime::Error::PageRole.into());
        }
    }

    let mut mailbox_page = [0u8; smp_runtime::PAGE_BYTES as usize];
    smp_runtime_put_u64(
        &mut mailbox_page,
        smp_runtime::MAILBOX_MAGIC_OFFSET,
        smp_runtime::MAILBOX_MAGIC,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_VERSION_OFFSET,
        smp_runtime::MAILBOX_VERSION,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_STATE_OFFSET,
        smp_runtime::MAILBOX_STATE_PREPARED,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_COMMAND_OFFSET,
        smp_runtime::MAILBOX_COMMAND_NONE,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_TARGET_APIC_ID_OFFSET,
        target_apic_id,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_BSP_APIC_ID_OFFSET,
        bsp_apic_id,
    );
    smp_runtime_put_u64(
        &mut mailbox_page,
        smp_runtime::MAILBOX_RUNTIME_MAGIC_OFFSET,
        smp_runtime::RUNTIME_MAGIC,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_RUNTIME_VERSION_OFFSET,
        smp_runtime::RUNTIME_VERSION,
    );
    smp_runtime_put_u32(
        &mut mailbox_page,
        smp_runtime::MAILBOX_RUNTIME_STATE_OFFSET,
        smp_runtime::RUNTIME_STATE_PREPARED,
    );
    for (offset, value) in [
        (smp_runtime::MAILBOX_EXPECTED_GDT_BASE_OFFSET, layout.gdt()),
        (smp_runtime::MAILBOX_EXPECTED_IDT_BASE_OFFSET, layout.idt()),
        (smp_runtime::MAILBOX_EXPECTED_TSS_BASE_OFFSET, layout.tss()),
        (smp_runtime::MAILBOX_RSP0_OFFSET, layout.rsp0_top()),
        (
            smp_runtime::MAILBOX_IST1_BOTTOM_OFFSET,
            layout.ist1_bottom(),
        ),
        (smp_runtime::MAILBOX_IST1_TOP_OFFSET, layout.ist1_top()),
        (
            smp_runtime::MAILBOX_IST2_BOTTOM_OFFSET,
            layout.ist2_bottom(),
        ),
        (smp_runtime::MAILBOX_IST2_TOP_OFFSET, layout.ist2_top()),
        (smp_runtime::MAILBOX_XSTATE_BASE_OFFSET, layout.xstate()),
    ] {
        smp_runtime_put_u64(&mut mailbox_page, offset, value);
    }
    for (offset, value) in [
        (smp_runtime::MAILBOX_XSTATE_BYTES_OFFSET, XSTATE_AREA_BYTES),
        (
            smp_runtime::MAILBOX_XSTATE_OWNER_INITIAL_OFFSET,
            smp_runtime::owner_token(target_apic_id),
        ),
        (
            smp_runtime::MAILBOX_INSTALLED_GATE_COUNT_OFFSET,
            smp_runtime::INSTALLED_GATE_COUNT,
        ),
        (
            smp_runtime::MAILBOX_OWNED_INTERRUPT_VECTOR_COUNT_OFFSET,
            smp_runtime::OWNED_INTERRUPT_VECTOR_COUNT,
        ),
    ] {
        smp_runtime_put_u32(&mut mailbox_page, offset, value);
    }
    smp_write_page_bytes(access, layout.local(), &mailbox_page)?;
    access
        .ensure_mapped(layout.local())
        .map_err(|_| smp::Error::PhysicalAccess)?;
    if smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_MAGIC_OFFSET) != smp_runtime::MAILBOX_MAGIC
        || smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_VERSION_OFFSET)
            != smp_runtime::MAILBOX_VERSION
        || smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_STATE_OFFSET)
            != smp_runtime::MAILBOX_STATE_PREPARED
        || smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_EXPECTED_GDT_BASE_OFFSET)
            != layout.gdt()
        || smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_EXPECTED_IDT_BASE_OFFSET)
            != layout.idt()
        || smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_XSTATE_BASE_OFFSET) != layout.xstate()
    {
        return Err(smp_runtime::Error::MailboxShape.into());
    }
    Ok((trampoline_bytes, fault_handler))
}

fn smp_runtime_mailbox_read_u32(offset: usize) -> u32 {
    debug_assert!(offset + core::mem::size_of::<u32>() <= smp_runtime::MAILBOX_BYTES);
    // SAFETY: PKSMP2 retains one private supervisor alias for the AP-local page.
    unsafe { read_volatile(smp_mailbox_address(offset) as *const u32) }
}

fn smp_runtime_mailbox_read_u64(offset: usize) -> u64 {
    debug_assert!(offset + core::mem::size_of::<u64>() <= smp_runtime::MAILBOX_BYTES);
    // SAFETY: every u64 field is aligned and bounded by the generated layout.
    unsafe { read_volatile(smp_mailbox_address(offset) as *const u64) }
}

fn smp_runtime_mailbox_write_u32(offset: usize, value: u32) {
    debug_assert!(offset + core::mem::size_of::<u32>() <= smp_runtime::MAILBOX_BYTES);
    // SAFETY: the BSP owns command writes; AP-owned observation fields are read-only here.
    unsafe { write_volatile(smp_mailbox_address(offset) as *mut u32, value) };
    arch::x86_64::memory_fence();
}

fn smp_runtime_mailbox_write_u64(offset: usize, value: u64) {
    debug_assert!(offset + core::mem::size_of::<u64>() <= smp_runtime::MAILBOX_BYTES);
    // SAFETY: checksums are committed only after the AP reports quiescence.
    unsafe { write_volatile(smp_mailbox_address(offset) as *mut u64, value) };
    arch::x86_64::memory_fence();
}

fn smp_runtime_mailbox_snapshot() -> RuntimeMailboxSnapshot {
    arch::x86_64::memory_fence();
    RuntimeMailboxSnapshot {
        magic: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_MAGIC_OFFSET),
        version: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_VERSION_OFFSET),
        state: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_STATE_OFFSET),
        command: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_COMMAND_OFFSET),
        target_apic_id: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_TARGET_APIC_ID_OFFSET),
        bsp_apic_id: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_BSP_APIC_ID_OFFSET),
        observed_apic_id: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_OBSERVED_APIC_ID_OFFSET,
        ),
        leaf1_ecx: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_LEAF1_ECX_OFFSET),
        leaf1_edx: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_LEAF1_EDX_OFFSET),
        cr0: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_CR0_OFFSET),
        cr3: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_CR3_OFFSET),
        cr4: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_CR4_OFFSET),
        efer: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_EFER_OFFSET),
        tsc_online: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_TSC_ONLINE_OFFSET),
        tsc_stop: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_TSC_STOP_OFFSET),
        baseline_checksum: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_BASELINE_CHECKSUM_OFFSET,
        ),
        runtime_magic: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_RUNTIME_MAGIC_OFFSET),
        runtime_version: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_RUNTIME_VERSION_OFFSET),
        runtime_state: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_RUNTIME_STATE_OFFSET),
        expected_gdt_base: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_EXPECTED_GDT_BASE_OFFSET,
        ),
        expected_idt_base: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_EXPECTED_IDT_BASE_OFFSET,
        ),
        expected_tss_base: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_EXPECTED_TSS_BASE_OFFSET,
        ),
        rsp0: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_RSP0_OFFSET),
        ist1_bottom: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_IST1_BOTTOM_OFFSET),
        ist1_top: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_IST1_TOP_OFFSET),
        ist2_bottom: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_IST2_BOTTOM_OFFSET),
        ist2_top: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_IST2_TOP_OFFSET),
        xstate_base: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_XSTATE_BASE_OFFSET),
        xstate_bytes: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_XSTATE_BYTES_OFFSET),
        xstate_owner_initial: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_XSTATE_OWNER_INITIAL_OFFSET,
        ),
        observed_gdt_base: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_OBSERVED_GDT_BASE_OFFSET,
        ),
        observed_idt_base: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_OBSERVED_IDT_BASE_OFFSET,
        ),
        observed_rsp: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_OBSERVED_RSP_OFFSET),
        xcr0: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_XCR0_OFFSET),
        xstate_bv: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_XSTATE_BV_OFFSET),
        rflags: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_RFLAGS_OFFSET),
        observed_gdt_limit: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_OBSERVED_GDT_LIMIT_OFFSET,
        ),
        observed_idt_limit: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_OBSERVED_IDT_LIMIT_OFFSET,
        ),
        task_selector: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_TASK_SELECTOR_OFFSET),
        code_selector: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_CODE_SELECTOR_OFFSET),
        data_selector: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_DATA_SELECTOR_OFFSET),
        installed_gate_count: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_INSTALLED_GATE_COUNT_OFFSET,
        ),
        owned_interrupt_vector_count: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_OWNED_INTERRUPT_VECTOR_COUNT_OFFSET,
        ),
        interrupts_enabled: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_INTERRUPTS_ENABLED_OFFSET,
        ),
        initial_fcw: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_INITIAL_FCW_OFFSET),
        initial_mxcsr: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_INITIAL_MXCSR_OFFSET),
        xstate_owner_final: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_XSTATE_OWNER_FINAL_OFFSET,
        ),
        xstate_save_count: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_XSTATE_SAVE_COUNT_OFFSET,
        ),
        xstate_restore_count: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_XSTATE_RESTORE_COUNT_OFFSET,
        ),
        fault_code: smp_runtime_mailbox_read_u32(smp_runtime::MAILBOX_FAULT_CODE_OFFSET),
        supported_xcr0: smp_runtime_mailbox_read_u64(smp_runtime::MAILBOX_SUPPORTED_XCR0_OFFSET),
        enabled_area_bytes: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_ENABLED_AREA_BYTES_OFFSET,
        ),
        maximum_area_bytes: smp_runtime_mailbox_read_u32(
            smp_runtime::MAILBOX_MAXIMUM_AREA_BYTES_OFFSET,
        ),
        runtime_checksum: smp_runtime_mailbox_read_u64(
            smp_runtime::MAILBOX_RUNTIME_CHECKSUM_OFFSET,
        ),
    }
}

fn smp_runtime_read_page_bytes(
    access: &mut BootstrapTableMemory,
    physical_address: u64,
) -> Result<[u8; smp_runtime::PAGE_BYTES as usize], SmpRuntimeLiveError> {
    let mut page = [0u8; smp_runtime::PAGE_BYTES as usize];
    for word_index in 0..(smp_runtime::PAGE_BYTES as usize / 8) {
        let word = PhysicalPageAccess::read_word(access, physical_address, word_index)
            .map_err(|_| smp::Error::PhysicalAccess)?;
        page[word_index * 8..word_index * 8 + 8].copy_from_slice(&word.to_le_bytes());
    }
    Ok(page)
}

fn smp_runtime_release_resources(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    allocation: poolekernel::physical_memory::AllocationHandle,
) -> Result<ScrubReceipt, SmpRuntimeLiveError> {
    TableMemory::finish(access).map_err(|_| smp::Error::PhysicalAccess)?;
    let receipt = manager
        .free_scrubbed(allocation, access)
        .map_err(|_| smp::Error::Memory)?;
    TableMemory::finish(access).map_err(|_| smp::Error::PhysicalAccess)?;
    let expected_bytes = smp_runtime::RESOURCE_PAGE_COUNT
        .checked_mul(smp_runtime::PAGE_BYTES)
        .ok_or(smp_runtime::Error::ResourceAddress)?;
    if receipt.kind != ScrubKind::Release
        || receipt.page_count != smp_runtime::RESOURCE_PAGE_COUNT
        || receipt.zeroed_bytes != expected_bytes
        || receipt.verified_bytes != expected_bytes
    {
        return Err(smp_runtime::Error::Rollback.into());
    }
    Ok(receipt)
}

fn smp_runtime_release_resources_with_live_mmio(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    allocation: poolekernel::physical_memory::AllocationHandle,
) -> Result<ScrubReceipt, SmpIpiLiveError> {
    access
        .revoke_temporary_mapping()
        .map_err(|_| smp::Error::PhysicalAccess)?;
    access
        .validate_active_uncached_mmio()
        .map_err(|_| smp::Error::PhysicalAccess)?;
    let receipt = manager
        .free_scrubbed_automatic(allocation, access)
        .map(|(receipt, _)| receipt)
        .map_err(smp_ipi_memory_error)?;
    access
        .revoke_temporary_mapping()
        .map_err(|_| smp::Error::PhysicalAccess)?;
    access
        .validate_active_uncached_mmio()
        .map_err(|_| smp::Error::PhysicalAccess)?;
    let expected_bytes = smp_runtime::RESOURCE_PAGE_COUNT
        .checked_mul(smp_runtime::PAGE_BYTES)
        .ok_or(smp_runtime::Error::ResourceAddress)?;
    if receipt.kind != ScrubKind::Release
        || receipt.page_count != smp_runtime::RESOURCE_PAGE_COUNT
        || receipt.zeroed_bytes != expected_bytes
        || receipt.verified_bytes != expected_bytes
    {
        return Err(smp_runtime::Error::Rollback.into());
    }
    Ok(receipt)
}

fn run_smp_percpu_runtime(
    handoff: &poole_handoff::Handoff<'_>,
    core: poole_handoff::CoreRecord,
    observed_cr3: u64,
) -> Result<SmpRuntimeLiveProof, SmpRuntimeLiveError> {
    let physical_bits = arch::x86_64::physical_address_bits().ok_or(smp::Error::Memory)?;
    let mut page_access =
        BootstrapTableMemory::new(observed_cr3, physical_bits).map_err(|_| smp::Error::Memory)?;
    let mut manager = PhysicalMemoryManager::from_handoff(handoff, core, DEFAULT_QUOTA_PAGES)
        .map_err(|_| smp::Error::Memory)?;
    manager
        .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
        .map_err(|_| smp::Error::Memory)?;
    let acpi_snapshot = acpi::consume_required_tables(handoff, &mut manager, &mut page_access)
        .map_err(smp::Error::Acpi)?;
    let madt_receipt = acpi_snapshot.required_tables[0];
    let hpet_receipt = acpi_snapshot.required_tables[2];
    let madt_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(madt_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let hpet_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(hpet_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let topology = parse_madt(&mut page_access, madt_snapshot, madt_receipt.byte_count)
        .map_err(|_| smp::Error::Madt)?;
    let hpet = parse_hpet(&mut page_access, hpet_snapshot, hpet_receipt.byte_count)
        .map_err(|_| smp::Error::Hpet)?;
    if !hpet.counter_64_bit_capable {
        return Err(smp::Error::Hpet.into());
    }

    let cpu = arch::x86_64::observe_apic_cpu();
    if !cpu.apic_supported {
        return Err(smp::Error::Apic.into());
    }
    // SAFETY: CPUID reports APIC and selector 13 runs at CPL0 with IF clear.
    let original_apic_base = unsafe { arch::x86_64::read_local_apic_base() };
    if original_apic_base & (APIC_BASE_ENABLE | APIC_BASE_X2APIC) != APIC_BASE_ENABLE {
        return Err(smp::Error::Apic.into());
    }
    let apic_physical = original_apic_base & interrupt_time::APIC_BASE_ADDRESS_MASK;
    if apic_physical != topology.local_apic_address {
        return Err(smp::Error::Apic.into());
    }
    let target = smp::select_first_ap(&topology, cpu.initial_apic_id)?;

    let (allocation, allocation_receipt) = manager
        .allocate_scrubbed(
            Zone::Dma,
            smp_runtime::RESOURCE_PAGE_COUNT,
            SMP_RESOURCE_OWNER,
            &mut page_access,
        )
        .map_err(|_| smp::Error::Memory)?;
    let layout = smp_runtime::ResourceLayout::new(allocation.start_page, allocation.page_count)?;
    let mut transaction = smp_runtime::PerCpuRuntimeTransaction::new();
    transaction.reserve()?;
    let (trampoline_bytes, fault_handler) = match smp_runtime_prepare_resources(
        &mut page_access,
        layout,
        cpu.initial_apic_id,
        target.apic_id,
    ) {
        Ok(value) => value,
        Err(error) => {
            smp_runtime_release_resources(&mut manager, &mut page_access, allocation)?;
            let _ = transaction.rollback(false)?;
            return Err(error);
        }
    };
    transaction.prepare()?;

    let hpet_page = hpet.physical_address & !0xfff;
    let (apic_virtual, hpet_page_virtual) =
        match page_access.install_uncached_mmio(apic_physical, hpet_page) {
            Ok(value) => value,
            Err(_) => {
                smp_runtime_release_resources(&mut manager, &mut page_access, allocation)?;
                let _ = transaction.rollback(false)?;
                return Err(smp::Error::PhysicalAccess.into());
            }
        };
    let hpet_virtual = hpet_page_virtual
        .checked_add(hpet.physical_address & 0xfff)
        .ok_or(smp::Error::Hpet)?;
    let mut hardware = LiveInterruptHardware {
        local_apic_virtual: apic_virtual,
        hpet_virtual,
    };

    let mut original_hpet_config = None;
    let mut pic_masks = None;
    let mut hpet_changed = false;
    let mut ap_started = false;
    let mut period_femtoseconds = None;
    let mut operation_result = (|| -> Result<SmpRuntimeOperationProof, SmpRuntimeLiveError> {
        let discovery = validate_apic_discovery(
            &topology,
            cpu,
            original_apic_base,
            hardware.apic_read(0x20).map_err(|_| smp::Error::Apic)?,
            hardware.apic_read(0x30).map_err(|_| smp::Error::Apic)?,
        )
        .map_err(|_| smp::Error::Apic)?;
        if !discovery.bsp || !discovery.globally_enabled || discovery.apic_id != cpu.initial_apic_id
        {
            return Err(smp::Error::Apic.into());
        }
        let period = smp_hpet_period(&hardware)?;
        period_femtoseconds = Some(period);
        let hpet_config = hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)?;
        original_hpet_config = Some(hpet_config);
        if topology.pcat_compatible {
            // SAFETY: IF is clear and PKSMP2 restores the exact masks after final INIT.
            pic_masks = Some(
                unsafe { arch::x86_64::mask_legacy_pic() }
                    .map_err(|_| smp::Error::PhysicalAccess)?,
            );
        }
        if hpet_config & 1 == 0 {
            hardware
                .hpet_write(0x10, hpet_config | 1)
                .map_err(|_| smp::Error::Hpet)?;
            hpet_changed = true;
            if hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)? != hpet_config | 1 {
                return Err(smp::Error::Hpet.into());
            }
        }

        let (bsp_leaf1_ecx, bsp_leaf1_edx) = arch::x86_64::observe_leaf1_features();
        if bsp_leaf1_ecx & smp_runtime::REQUIRED_HARDWARE_LEAF1_ECX
            != smp_runtime::REQUIRED_HARDWARE_LEAF1_ECX
            || bsp_leaf1_edx & smp::REQUIRED_LEAF1_EDX != smp::REQUIRED_LEAF1_EDX
        {
            return Err(smp_runtime::Error::FeatureMismatch.into());
        }
        let bsp_tsc_before = arch::x86_64::read_tsc_ordered();
        smp_init_sequence(&mut hardware, target.apic_id, period)?;
        ap_started = true;
        transaction.startup_sent()?;
        smp_apic_command(
            &mut hardware,
            target.apic_id,
            SMP_APIC_STARTUP | u32::from(layout.sipi_vector()),
        )?;
        smp_hpet_wait(&hardware, period, SMP_INTER_IPI_NANOSECONDS)?;
        smp_apic_command(
            &mut hardware,
            target.apic_id,
            SMP_APIC_STARTUP | u32::from(layout.sipi_vector()),
        )?;
        smp_hpet_wait(&hardware, period, SMP_INTER_IPI_NANOSECONDS)?;
        smp_wait_mailbox_state(
            &hardware,
            period,
            smp_runtime::MAILBOX_STATE_PREPARED,
            smp_runtime::MAILBOX_STATE_ONLINE,
        )?;
        let bsp_tsc_after = arch::x86_64::read_tsc_ordered();
        transaction.online()?;
        smp_runtime_mailbox_write_u32(
            smp_runtime::MAILBOX_COMMAND_OFFSET,
            smp_runtime::MAILBOX_COMMAND_STOP,
        );
        smp_wait_mailbox_state(
            &hardware,
            period,
            smp_runtime::MAILBOX_STATE_ONLINE,
            smp_runtime::MAILBOX_STATE_QUIESCED,
        )?;
        transaction.quiesced()?;
        let mut mailbox = smp_runtime_mailbox_snapshot();
        mailbox.baseline_checksum = smp_runtime::baseline_checksum(&mailbox);
        smp_runtime_mailbox_write_u64(
            smp_runtime::MAILBOX_BASELINE_CHECKSUM_OFFSET,
            mailbox.baseline_checksum,
        );
        mailbox.runtime_checksum = smp_runtime::runtime_checksum(&mailbox);
        smp_runtime_mailbox_write_u64(
            smp_runtime::MAILBOX_RUNTIME_CHECKSUM_OFFSET,
            mailbox.runtime_checksum,
        );
        mailbox = smp_runtime_mailbox_snapshot();
        smp_runtime::validate_mailbox(
            &mailbox,
            layout,
            bsp_leaf1_ecx,
            bsp_leaf1_edx,
            bsp_tsc_before,
            bsp_tsc_after,
        )?;
        Ok(SmpRuntimeOperationProof {
            mailbox,
            init_asserts: 1,
            init_deasserts: 1,
            sipis: 2,
            tss_busy_verified: false,
            idt_verified: false,
            xstate_verified: false,
        })
    })();

    let park_result = if ap_started {
        match period_femtoseconds {
            Some(period) => smp_init_sequence(&mut hardware, target.apic_id, period),
            None => Err(smp::Error::Rollback),
        }
    } else {
        Ok(())
    };
    if park_result.is_err() {
        if let (true, Some(config)) = (hpet_changed, original_hpet_config) {
            let _ = hardware.hpet_write(0x10, config);
        }
        if let Some(masks) = pic_masks {
            // SAFETY: IF remains clear; retaining all AP resources takes precedence.
            let _ = unsafe { arch::x86_64::restore_legacy_pic(masks) };
        }
        return Err(smp_runtime::Error::Rollback.into());
    }
    if operation_result.is_ok() {
        transaction.parked()?;
    }

    if let Ok(mut operation) = operation_result {
        let descriptor = smp_runtime_read_page_bytes(
            &mut page_access,
            layout.page_address(smp_runtime::DESCRIPTOR_PAGE_OFFSET),
        );
        let idt = smp_runtime_read_page_bytes(&mut page_access, layout.idt());
        let xstate = smp_runtime_read_page_bytes(&mut page_access, layout.xstate());
        operation_result = match (descriptor, idt, xstate) {
            (Ok(descriptor), Ok(idt), Ok(xstate)) => {
                match smp_runtime::validate_post_ap_resources(
                    layout,
                    &descriptor,
                    &idt,
                    &xstate,
                    fault_handler,
                    &operation.mailbox,
                ) {
                    Ok(()) => {
                        transaction.validated()?;
                        operation.tss_busy_verified = true;
                        operation.idt_verified = true;
                        operation.xstate_verified = true;
                        Ok(operation)
                    }
                    Err(error) => Err(error.into()),
                }
            }
            (Err(error), _, _) | (_, Err(error), _) | (_, _, Err(error)) => Err(error),
        };
    }

    let mut cleanup_error = None;
    if let (true, Some(config)) = (hpet_changed, original_hpet_config) {
        let restore_failed = hardware.hpet_write(0x10, config).is_err()
            || hardware.hpet_read(0x10).ok() != Some(config);
        if restore_failed {
            cleanup_error = Some(SmpRuntimeLiveError::Base(smp::Error::Hpet));
        }
    }
    if let Some(masks) = pic_masks {
        // SAFETY: the AP is reset, IF is clear, and these are the observed masks.
        if unsafe { arch::x86_64::restore_legacy_pic(masks) }.is_err() {
            cleanup_error = Some(SmpRuntimeLiveError::Base(smp::Error::PhysicalAccess));
        }
    }
    if page_access.uninstall_uncached_mmio().is_err() {
        cleanup_error = Some(SmpRuntimeLiveError::Base(smp::Error::PhysicalAccess));
    }
    let release_receipt =
        match smp_runtime_release_resources(&mut manager, &mut page_access, allocation) {
            Ok(value) => value,
            Err(error) => {
                cleanup_error = Some(error);
                allocation_receipt
            }
        };

    match operation_result {
        Err(error) => {
            let _ = transaction.rollback(true)?;
            Err(cleanup_error.unwrap_or(error))
        }
        Ok(operation) => {
            if let Some(error) = cleanup_error {
                return Err(error);
            }
            transaction.released()?;
            Ok(SmpRuntimeLiveProof {
                madt_bytes: madt_receipt.byte_count,
                processor_count: topology.processor_count as u64,
                enabled_processor_count: topology.enabled_processor_count as u64,
                bsp_apic_id: cpu.initial_apic_id,
                target_apic_id: target.apic_id,
                apic_physical,
                hpet_physical: hpet.physical_address,
                layout,
                trampoline_bytes: trampoline_bytes as u64,
                allocation_receipt,
                release_receipt,
                operation,
            })
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SmpIpiLiveError {
    Base(smp::Error),
    Runtime(smp_runtime::Error),
    Ipi(smp_ipi::Error),
}

impl SmpIpiLiveError {
    #[inline(always)]
    fn code(self) -> u32 {
        let class = match self {
            Self::Base(error) => 0x1000 | error.code(),
            Self::Runtime(_) => 0x2000,
            Self::Ipi(_) => 0x3000,
        };
        class | (SMP_IPI_FAILURE_STAGE.load(Ordering::Relaxed) << 16)
    }
}

impl From<smp::Error> for SmpIpiLiveError {
    fn from(value: smp::Error) -> Self {
        Self::Base(value)
    }
}

impl From<smp_runtime::Error> for SmpIpiLiveError {
    fn from(value: smp_runtime::Error) -> Self {
        Self::Runtime(value)
    }
}

impl From<smp_ipi::Error> for SmpIpiLiveError {
    fn from(value: smp_ipi::Error) -> Self {
        Self::Ipi(value)
    }
}

fn smp_ipi_memory_error(error: PhysicalMemoryError) -> SmpIpiLiveError {
    let detail = if error == PhysicalMemoryError::MetadataCorruption {
        1
    } else if error == PhysicalMemoryError::MetadataOwnership {
        2
    } else {
        3
    };
    SMP_IPI_FAILURE_DETAIL.store(detail << 32, Ordering::Relaxed);
    smp::Error::Memory.into()
}

impl From<SmpRuntimeLiveError> for SmpIpiLiveError {
    fn from(value: SmpRuntimeLiveError) -> Self {
        match value {
            SmpRuntimeLiveError::Base(error) => Self::Base(error),
            SmpRuntimeLiveError::Runtime(error) => Self::Runtime(error),
        }
    }
}

#[derive(Clone, Copy)]
struct SmpIpiApResource {
    target_apic_id: u32,
    allocation: AllocationHandle,
    allocation_receipt: ScrubReceipt,
    layout: smp_runtime::ResourceLayout,
    old_frame: Option<AllocationHandle>,
    old_frame_allocation_receipt: ScrubReceipt,
    old_frame_physical: u64,
    new_frame: Option<AllocationHandle>,
    new_frame_allocation_receipt: ScrubReceipt,
    new_frame_physical: u64,
    shootdown: ShootdownRequest,
    handlers: smp_ipi::HandlerLayout,
    trampoline_bytes: u64,
}

#[derive(Clone, Copy)]
struct SmpIpiApOperationProof {
    mailbox: RuntimeMailboxSnapshot,
    ipi: IpiSnapshot,
    init_asserts: u64,
    init_deasserts: u64,
    sipis: u64,
    timeout_count: u32,
    old_frame_release_receipt: ScrubReceipt,
    new_frame_release_receipt: ScrubReceipt,
    resource_release_receipt: ScrubReceipt,
}

#[derive(Clone, Copy)]
struct SmpIpiPartialRollbackProof {
    started_mask: u64,
    parked_mask: u64,
    released_mask: u64,
    timeout_target_apic_id: u32,
    timeout_count: u32,
    resource_pages_released: u64,
    frame_pages_released: u64,
    zeroed_bytes: u64,
    verified_bytes: u64,
}

#[derive(Clone, Copy)]
struct SmpIpiLiveProof {
    processor_count: u64,
    enabled_processor_count: u64,
    bsp_apic_id: u32,
    target_apic_ids: [u32; smp_ipi::AP_COUNT],
    apic_physical: u64,
    partial: SmpIpiPartialRollbackProof,
    aps: [SmpIpiApResource; smp_ipi::AP_COUNT],
    operations: [SmpIpiApOperationProof; smp_ipi::AP_COUNT],
    lifecycle: smp_ipi::MultiApReceipt,
    retirement: smp_ipi::MultiGenerationRetirementReceipt,
    premature_reclaim_rejections: u64,
}

type SmpIpiExecutionReceipt = (
    [RuntimeMailboxSnapshot; smp_ipi::AP_COUNT],
    [IpiSnapshot; smp_ipi::AP_COUNT],
    [ScrubReceipt; smp_ipi::AP_COUNT],
    smp_ipi::MultiGenerationRetirementReceipt,
    u64,
);

const SMP_IPI_ENTRY_WRITE_THROUGH: u64 = 1 << 3;
const SMP_IPI_ENTRY_CACHE_DISABLE: u64 = 1 << 4;
const SMP_IPI_ENTRY_ACCESSED: u64 = 1 << 5;
const SMP_IPI_ENTRY_DIRTY: u64 = 1 << 6;
const SMP_IPI_APIC_LEAF_FLAGS: u64 = smp::ENTRY_PRESENT
    | smp::ENTRY_WRITABLE
    | SMP_IPI_ENTRY_WRITE_THROUGH
    | SMP_IPI_ENTRY_CACHE_DISABLE
    | smp::ENTRY_NO_EXECUTE;

fn smp_ipi_mailbox_read_u32(offset: usize) -> u32 {
    debug_assert!(offset + core::mem::size_of::<u32>() <= smp_ipi::MAILBOX_BYTES);
    // SAFETY: PKSMP3 retains one private supervisor alias for the AP-local page.
    unsafe { read_volatile(smp_mailbox_address(offset) as *const u32) }
}

fn smp_ipi_mailbox_read_u64(offset: usize) -> u64 {
    debug_assert!(offset + core::mem::size_of::<u64>() <= smp_ipi::MAILBOX_BYTES);
    // SAFETY: every extension u64 is aligned and bounded by the frozen PKSMP3 ABI.
    unsafe { read_volatile(smp_mailbox_address(offset) as *const u64) }
}

fn smp_ipi_mailbox_write_u32(offset: usize, value: u32) {
    debug_assert!(offset + core::mem::size_of::<u32>() <= smp_ipi::MAILBOX_BYTES);
    // SAFETY: the BSP owns request publication and initial extension state.
    unsafe { write_volatile(smp_mailbox_address(offset) as *mut u32, value) };
    arch::x86_64::memory_fence();
}

fn smp_ipi_mailbox_write_u64(offset: usize, value: u64) {
    debug_assert!(offset + core::mem::size_of::<u64>() <= smp_ipi::MAILBOX_BYTES);
    // SAFETY: the BSP owns request publication and initial extension state.
    unsafe { write_volatile(smp_mailbox_address(offset) as *mut u64, value) };
    arch::x86_64::memory_fence();
}

fn smp_ipi_mailbox_snapshot() -> IpiSnapshot {
    arch::x86_64::memory_fence();
    IpiSnapshot {
        magic: smp_ipi_mailbox_read_u64(smp_ipi::MAGIC_OFFSET),
        version: smp_ipi_mailbox_read_u32(smp_ipi::VERSION_OFFSET),
        service_state: smp_ipi_mailbox_read_u32(smp_ipi::SERVICE_STATE_OFFSET),
        capability_high: smp_ipi_mailbox_read_u64(smp_ipi::CAPABILITY_HIGH_OFFSET),
        capability_low: smp_ipi_mailbox_read_u64(smp_ipi::CAPABILITY_LOW_OFFSET),
        request_capability_high: smp_ipi_mailbox_read_u64(smp_ipi::REQUEST_CAPABILITY_HIGH_OFFSET),
        request_capability_low: smp_ipi_mailbox_read_u64(smp_ipi::REQUEST_CAPABILITY_LOW_OFFSET),
        request_attempt: smp_ipi_mailbox_read_u64(smp_ipi::REQUEST_ATTEMPT_OFFSET),
        request_sequence: smp_ipi_mailbox_read_u64(smp_ipi::REQUEST_SEQUENCE_OFFSET),
        payload: smp_ipi_mailbox_read_u64(smp_ipi::PAYLOAD_OFFSET),
        request_checksum: smp_ipi_mailbox_read_u64(smp_ipi::REQUEST_CHECKSUM_OFFSET),
        ack_attempt: smp_ipi_mailbox_read_u64(smp_ipi::ACK_ATTEMPT_OFFSET),
        ack_sequence: smp_ipi_mailbox_read_u64(smp_ipi::ACK_SEQUENCE_OFFSET),
        result: smp_ipi_mailbox_read_u64(smp_ipi::RESULT_OFFSET),
        response_checksum: smp_ipi_mailbox_read_u64(smp_ipi::RESPONSE_CHECKSUM_OFFSET),
        last_accepted_sequence: smp_ipi_mailbox_read_u64(smp_ipi::LAST_ACCEPTED_SEQUENCE_OFFSET),
        request_operation: smp_ipi_mailbox_read_u32(smp_ipi::REQUEST_OPERATION_OFFSET),
        request_vector: smp_ipi_mailbox_read_u32(smp_ipi::REQUEST_VECTOR_OFFSET),
        request_target_apic_id: smp_ipi_mailbox_read_u32(smp_ipi::REQUEST_TARGET_APIC_ID_OFFSET),
        request_status: smp_ipi_mailbox_read_u32(smp_ipi::REQUEST_STATUS_OFFSET),
        ack_operation: smp_ipi_mailbox_read_u32(smp_ipi::ACK_OPERATION_OFFSET),
        ack_status: smp_ipi_mailbox_read_u32(smp_ipi::ACK_STATUS_OFFSET),
        ack_error: smp_ipi_mailbox_read_u32(smp_ipi::ACK_ERROR_OFFSET),
        delivery_count: smp_ipi_mailbox_read_u32(smp_ipi::DELIVERY_COUNT_OFFSET),
        eoi_count: smp_ipi_mailbox_read_u32(smp_ipi::EOI_COUNT_OFFSET),
        accepted_count: smp_ipi_mailbox_read_u32(smp_ipi::ACCEPTED_COUNT_OFFSET),
        denied_count: smp_ipi_mailbox_read_u32(smp_ipi::DENIED_COUNT_OFFSET),
        reschedule_count: smp_ipi_mailbox_read_u32(smp_ipi::RESCHEDULE_COUNT_OFFSET),
        shootdown_count: smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_COUNT_OFFSET),
        call_function_count: smp_ipi_mailbox_read_u32(smp_ipi::CALL_FUNCTION_COUNT_OFFSET),
        diagnostic_count: smp_ipi_mailbox_read_u32(smp_ipi::DIAGNOSTIC_COUNT_OFFSET),
        stop_count: smp_ipi_mailbox_read_u32(smp_ipi::STOP_COUNT_OFFSET),
        panic_count: smp_ipi_mailbox_read_u32(smp_ipi::PANIC_COUNT_OFFSET),
        panic_latched: smp_ipi_mailbox_read_u32(smp_ipi::PANIC_LATCHED_OFFSET),
        spurious_count: smp_ipi_mailbox_read_u32(smp_ipi::SPURIOUS_COUNT_OFFSET),
        apic_error_count: smp_ipi_mailbox_read_u32(smp_ipi::APIC_ERROR_COUNT_OFFSET),
        shootdown: ShootdownSnapshot {
            magic: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_MAGIC_OFFSET),
            version: smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_VERSION_OFFSET),
            state: smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_STATE_OFFSET),
            error: smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_ERROR_OFFSET),
            root_physical: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_ROOT_PHYSICAL_OFFSET),
            virtual_address: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_VIRTUAL_ADDRESS_OFFSET),
            retired_generation: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_RETIRED_GENERATION_OFFSET,
            ),
            active_generation: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_ACTIVE_GENERATION_OFFSET,
            ),
            target_mask: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_TARGET_MASK_OFFSET),
            ack_mask: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_ACK_MASK_OFFSET),
            old_frame_physical: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_OLD_FRAME_PHYSICAL_OFFSET,
            ),
            new_frame_physical: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_NEW_FRAME_PHYSICAL_OFFSET,
            ),
            observed_before: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_OBSERVED_BEFORE_OFFSET),
            observed_after: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_OBSERVED_AFTER_OFFSET),
            invalidation_count: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_INVALIDATION_COUNT_OFFSET,
            ),
            request_checksum: smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_OFFSET),
            response_checksum: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_RESPONSE_CHECKSUM_OFFSET,
            ),
            last_ack_generation: smp_ipi_mailbox_read_u64(
                smp_ipi::SHOOTDOWN_LAST_ACK_GENERATION_OFFSET,
            ),
            timeout_count: smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_TIMEOUT_COUNT_OFFSET),
            reclaim_state: smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_RECLAIM_STATE_OFFSET),
        },
    }
}

fn smp_ipi_prepare_resources(
    access: &mut BootstrapTableMemory,
    layout: smp_runtime::ResourceLayout,
    bsp_apic_id: u32,
    target_apic_id: u32,
    apic_physical: u64,
    shootdown: &ShootdownRequest,
) -> Result<(usize, smp_ipi::HandlerLayout), SmpIpiLiveError> {
    if apic_physical != smp_ipi::APIC_PHYSICAL_ADDRESS {
        return Err(smp_ipi::Error::ResourceAddress.into());
    }
    let _ = smp_runtime_prepare_resources(access, layout, bsp_apic_id, target_apic_id)?;
    let (trampoline, trampoline_bytes, handlers) =
        arch::x86_64::build_ap_ipi_trampoline_page(layout).map_err(|_| smp::Error::Trampoline)?;
    smp_write_page_bytes(access, layout.trampoline(), &trampoline)?;
    let idt = smp_ipi::build_idt_page(layout, handlers)?;
    smp_write_page_bytes(access, layout.idt(), &idt)?;
    TableMemory::write_entry(
        access,
        layout.page_table(),
        smp_ipi::PROBE_PAGE_TABLE_INDEX,
        shootdown.old_frame_physical
            | smp::ENTRY_PRESENT
            | smp::ENTRY_WRITABLE
            | smp::ENTRY_NO_EXECUTE,
    )
    .map_err(|_| smp::Error::Memory)?;

    let apic_table = layout.page_address(smp_ipi::APIC_PAGE_TABLE_OFFSET);
    TableMemory::write_entry(
        access,
        layout.pdpt(),
        smp_ipi::APIC_PDPT_INDEX,
        layout.page_directory() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    TableMemory::write_entry(
        access,
        layout.page_directory(),
        smp_ipi::APIC_PAGE_DIRECTORY_INDEX,
        apic_table | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE,
    )
    .map_err(|_| smp::Error::Memory)?;
    TableMemory::write_entry(
        access,
        apic_table,
        smp_ipi::APIC_PAGE_TABLE_INDEX,
        apic_physical | SMP_IPI_APIC_LEAF_FLAGS,
    )
    .map_err(|_| smp::Error::Memory)?;

    if TableMemory::read_entry(access, layout.pdpt(), smp_ipi::APIC_PDPT_INDEX)
        .map_err(|_| smp::Error::Memory)?
        != layout.page_directory() | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE
        || TableMemory::read_entry(
            access,
            layout.page_directory(),
            smp_ipi::APIC_PAGE_DIRECTORY_INDEX,
        )
        .map_err(|_| smp::Error::Memory)?
            != apic_table | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE
        || TableMemory::read_entry(access, apic_table, smp_ipi::APIC_PAGE_TABLE_INDEX)
            .map_err(|_| smp::Error::Memory)?
            != apic_physical | SMP_IPI_APIC_LEAF_FLAGS
    {
        return Err(smp_ipi::Error::PageRole.into());
    }
    access
        .ensure_mapped(layout.local())
        .map_err(|_| smp::Error::PhysicalAccess)?;
    smp_ipi_mailbox_write_u64(smp_ipi::MAGIC_OFFSET, smp_ipi::EXTENSION_MAGIC);
    smp_ipi_mailbox_write_u32(smp_ipi::VERSION_OFFSET, smp_ipi::EXTENSION_VERSION);
    smp_ipi_mailbox_write_u32(
        smp_ipi::SERVICE_STATE_OFFSET,
        smp_ipi::SERVICE_STATE_PREPARED,
    );
    smp_ipi_mailbox_write_u64(smp_ipi::CAPABILITY_HIGH_OFFSET, smp_ipi::CAPABILITY_HIGH);
    smp_ipi_mailbox_write_u64(smp_ipi::CAPABILITY_LOW_OFFSET, smp_ipi::CAPABILITY_LOW);
    smp_ipi_mailbox_write_u64(smp_ipi::SHOOTDOWN_MAGIC_OFFSET, smp_ipi::SHOOTDOWN_MAGIC);
    smp_ipi_mailbox_write_u32(
        smp_ipi::SHOOTDOWN_VERSION_OFFSET,
        smp_ipi::SHOOTDOWN_VERSION,
    );
    smp_ipi_mailbox_write_u32(
        smp_ipi::SHOOTDOWN_STATE_OFFSET,
        smp_ipi::SHOOTDOWN_STATE_PREPARED,
    );
    smp_ipi_mailbox_write_u32(smp_ipi::SHOOTDOWN_ERROR_OFFSET, smp_ipi::ERROR_NONE);
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_ROOT_PHYSICAL_OFFSET,
        shootdown.root_physical,
    );
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_VIRTUAL_ADDRESS_OFFSET,
        shootdown.virtual_address,
    );
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_RETIRED_GENERATION_OFFSET,
        shootdown.retired_generation,
    );
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_ACTIVE_GENERATION_OFFSET,
        shootdown.active_generation,
    );
    smp_ipi_mailbox_write_u64(smp_ipi::SHOOTDOWN_TARGET_MASK_OFFSET, shootdown.target_mask);
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_OLD_FRAME_PHYSICAL_OFFSET,
        shootdown.old_frame_physical,
    );
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_NEW_FRAME_PHYSICAL_OFFSET,
        shootdown.new_frame_physical,
    );
    smp_ipi_mailbox_write_u64(
        smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_OFFSET,
        shootdown.checksum,
    );
    smp_ipi_mailbox_write_u32(
        smp_ipi::SHOOTDOWN_RECLAIM_STATE_OFFSET,
        smp_ipi::RECLAIM_BLOCKED,
    );
    if smp_ipi_mailbox_read_u64(smp_ipi::MAGIC_OFFSET) != smp_ipi::EXTENSION_MAGIC
        || smp_ipi_mailbox_read_u32(smp_ipi::VERSION_OFFSET) != smp_ipi::EXTENSION_VERSION
        || smp_ipi_mailbox_read_u32(smp_ipi::SERVICE_STATE_OFFSET)
            != smp_ipi::SERVICE_STATE_PREPARED
        || smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_MAGIC_OFFSET) != smp_ipi::SHOOTDOWN_MAGIC
        || smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_OFFSET)
            != shootdown.checksum
    {
        return Err(smp_ipi::Error::MailboxShape.into());
    }
    Ok((trampoline_bytes, handlers))
}

fn smp_ipi_publish_request(request: &IpiRequest) {
    smp_ipi_mailbox_write_u32(smp_ipi::REQUEST_STATUS_OFFSET, smp_ipi::REQUEST_IDLE);
    smp_ipi_mailbox_write_u64(
        smp_ipi::REQUEST_CAPABILITY_HIGH_OFFSET,
        request.capability_high,
    );
    smp_ipi_mailbox_write_u64(
        smp_ipi::REQUEST_CAPABILITY_LOW_OFFSET,
        request.capability_low,
    );
    smp_ipi_mailbox_write_u64(smp_ipi::REQUEST_ATTEMPT_OFFSET, request.attempt);
    smp_ipi_mailbox_write_u64(smp_ipi::REQUEST_SEQUENCE_OFFSET, request.sequence);
    smp_ipi_mailbox_write_u64(smp_ipi::PAYLOAD_OFFSET, request.payload);
    smp_ipi_mailbox_write_u32(smp_ipi::REQUEST_OPERATION_OFFSET, request.operation);
    smp_ipi_mailbox_write_u32(smp_ipi::REQUEST_VECTOR_OFFSET, request.vector);
    smp_ipi_mailbox_write_u32(
        smp_ipi::REQUEST_TARGET_APIC_ID_OFFSET,
        request.target_apic_id,
    );
    smp_ipi_mailbox_write_u64(smp_ipi::REQUEST_CHECKSUM_OFFSET, request.checksum);
    arch::x86_64::memory_fence();
    smp_ipi_mailbox_write_u32(smp_ipi::REQUEST_STATUS_OFFSET, request.status);
}

fn smp_ipi_wait_ack(
    hardware: &LiveInterruptHardware,
    period_femtoseconds: u64,
    attempt: u64,
) -> Result<IpiSnapshot, SmpIpiLiveError> {
    let target = smp_hpet_ticks(SMP_MAILBOX_TIMEOUT_NANOSECONDS, period_femtoseconds)?;
    let start = hardware.hpet_read(0xf0).map_err(|_| smp::Error::Hpet)?;
    for _ in 0..SMP_HPET_POLL_LIMIT {
        if smp_ipi_mailbox_read_u32(smp_ipi::SERVICE_STATE_OFFSET) == smp_ipi::SERVICE_STATE_FAULTED
        {
            return Err(smp_ipi::Error::MailboxShape.into());
        }
        if smp_ipi_mailbox_read_u64(smp_ipi::ACK_ATTEMPT_OFFSET) == attempt {
            let snapshot = smp_ipi_mailbox_snapshot();
            if snapshot.response_checksum != smp_ipi::response_checksum(&snapshot) {
                return Err(smp_ipi::Error::Checksum.into());
            }
            return Ok(snapshot);
        }
        let current = hardware.hpet_read(0xf0).map_err(|_| smp::Error::Hpet)?;
        if current.wrapping_sub(start) >= target {
            return Err(smp::Error::Timeout.into());
        }
        core::hint::spin_loop();
    }
    Err(smp::Error::Timeout.into())
}

fn smp_ipi_deliver(
    hardware: &mut LiveInterruptHardware,
    period_femtoseconds: u64,
    handler_operation: IpiOperation,
    request: &IpiRequest,
    expected_status: u32,
    expected_error: u32,
    expected_result: u64,
) -> Result<IpiSnapshot, SmpIpiLiveError> {
    smp_ipi_publish_request(request);
    smp_apic_command(
        hardware,
        request.target_apic_id,
        u32::from(handler_operation.vector()),
    )?;
    let snapshot = smp_ipi_wait_ack(hardware, period_femtoseconds, request.attempt)?;
    if snapshot.ack_sequence != request.sequence
        || snapshot.ack_operation != handler_operation as u32
        || snapshot.ack_status != expected_status
        || snapshot.ack_error != expected_error
        || snapshot.request_status != smp_ipi::REQUEST_IDLE
    {
        return Err(smp_ipi::Error::Result.into());
    }
    if snapshot.result != expected_result {
        return Err(smp_ipi::Error::Result.into());
    }
    Ok(snapshot)
}

fn smp_ipi_validate_post_ap_resources(
    access: &mut BootstrapTableMemory,
    layout: smp_runtime::ResourceLayout,
    handlers: smp_ipi::HandlerLayout,
    mailbox: &RuntimeMailboxSnapshot,
    apic_physical: u64,
    new_frame_physical: u64,
) -> Result<(), SmpIpiLiveError> {
    let descriptor = smp_runtime_read_page_bytes(
        access,
        layout.page_address(smp_runtime::DESCRIPTOR_PAGE_OFFSET),
    )?;
    let idt = smp_runtime_read_page_bytes(access, layout.idt())?;
    let xstate = smp_runtime_read_page_bytes(access, layout.xstate())?;
    let compatibility_idt = smp_runtime::build_idt_page(layout, handlers.fault)?;
    smp_runtime::validate_post_ap_resources(
        layout,
        &descriptor,
        &compatibility_idt,
        &xstate,
        handlers.fault,
        mailbox,
    )?;
    if idt != smp_ipi::build_idt_page(layout, handlers)? {
        return Err(smp_ipi::Error::Idt.into());
    }
    let apic_table = layout.page_address(smp_ipi::APIC_PAGE_TABLE_OFFSET);
    if TableMemory::read_entry(access, layout.pdpt(), smp_ipi::APIC_PDPT_INDEX)
        .map_err(|_| smp::Error::Memory)?
        != layout.page_directory()
            | smp::ENTRY_PRESENT
            | smp::ENTRY_WRITABLE
            | SMP_IPI_ENTRY_ACCESSED
        || TableMemory::read_entry(
            access,
            layout.page_directory(),
            smp_ipi::APIC_PAGE_DIRECTORY_INDEX,
        )
        .map_err(|_| smp::Error::Memory)?
            != apic_table | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE | SMP_IPI_ENTRY_ACCESSED
        || TableMemory::read_entry(access, apic_table, smp_ipi::APIC_PAGE_TABLE_INDEX)
            .map_err(|_| smp::Error::Memory)?
            != apic_physical
                | SMP_IPI_APIC_LEAF_FLAGS
                | SMP_IPI_ENTRY_ACCESSED
                | SMP_IPI_ENTRY_DIRTY
    {
        return Err(smp_ipi::Error::PageRole.into());
    }
    for index in 1..512 {
        if TableMemory::read_entry(access, apic_table, index).map_err(|_| smp::Error::Memory)? != 0
        {
            return Err(smp_ipi::Error::PageRole.into());
        }
    }
    let probe_leaf =
        TableMemory::read_entry(access, layout.page_table(), smp_ipi::PROBE_PAGE_TABLE_INDEX)
            .map_err(|_| smp::Error::Memory)?;
    if probe_leaf
        != (new_frame_physical
            | smp::ENTRY_PRESENT
            | smp::ENTRY_WRITABLE
            | smp::ENTRY_NO_EXECUTE
            | SMP_IPI_ENTRY_ACCESSED)
    {
        return Err(smp_ipi::Error::PageRole.into());
    }
    Ok(())
}

#[derive(Clone, Copy)]
struct SmpIpiReleaseProof {
    old_frame: Option<ScrubReceipt>,
    new_frame: Option<ScrubReceipt>,
    resource: ScrubReceipt,
}

fn smp_ipi_allocate_ap_resource(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    bsp_apic_id: u32,
    target_apic_id: u32,
    apic_physical: u64,
) -> Result<SmpIpiApResource, SmpIpiLiveError> {
    let (allocation, allocation_receipt, _) = manager
        .allocate_scrubbed_automatic(
            Zone::Dma,
            smp_runtime::RESOURCE_PAGE_COUNT,
            SMP_RESOURCE_OWNER,
            access,
        )
        .map_err(|_| smp::Error::Memory)?;
    let layout =
        match smp_runtime::ResourceLayout::new(allocation.start_page, allocation.page_count) {
            Ok(value) => value,
            Err(error) => {
                let _ = manager.free_scrubbed_automatic(allocation, access);
                return Err(error.into());
            }
        };
    let (old_frame, old_frame_allocation_receipt, _) = match manager.allocate_scrubbed_automatic(
        Zone::Dma,
        1,
        smp_ipi::SHOOTDOWN_FRAME_OWNER,
        access,
    ) {
        Ok(value) => value,
        Err(_) => {
            let _ = smp_runtime_release_resources_with_live_mmio(manager, access, allocation);
            return Err(smp::Error::Memory.into());
        }
    };
    let (new_frame, new_frame_allocation_receipt, _) = match manager.allocate_scrubbed_automatic(
        Zone::Dma,
        1,
        smp_ipi::SHOOTDOWN_FRAME_OWNER,
        access,
    ) {
        Ok(value) => value,
        Err(_) => {
            let _ = manager.free_scrubbed_automatic(old_frame, access);
            let _ = smp_runtime_release_resources_with_live_mmio(manager, access, allocation);
            return Err(smp::Error::Memory.into());
        }
    };
    let old_frame_physical = old_frame
        .start_page
        .checked_mul(smp_ipi::PAGE_BYTES)
        .ok_or(smp::Error::Memory)?;
    let new_frame_physical = new_frame
        .start_page
        .checked_mul(smp_ipi::PAGE_BYTES)
        .ok_or(smp::Error::Memory)?;
    let prepare_result = (|| -> Result<(usize, smp_ipi::HandlerLayout), SmpIpiLiveError> {
        PhysicalPageAccess::write_word(access, old_frame_physical, 0, smp_ipi::OLD_FRAME_VALUE)
            .map_err(|_| smp::Error::Memory)?;
        PhysicalPageAccess::write_word(access, new_frame_physical, 0, smp_ipi::NEW_FRAME_VALUE)
            .map_err(|_| smp::Error::Memory)?;
        if PhysicalPageAccess::read_word(access, old_frame_physical, 0)
            .map_err(|_| smp::Error::Memory)?
            != smp_ipi::OLD_FRAME_VALUE
            || PhysicalPageAccess::read_word(access, new_frame_physical, 0)
                .map_err(|_| smp::Error::Memory)?
                != smp_ipi::NEW_FRAME_VALUE
        {
            return Err(smp::Error::Memory.into());
        }
        let shootdown = ShootdownRequest::canonical_for_target(
            target_apic_id,
            layout.pml4(),
            old_frame_physical,
            new_frame_physical,
        );
        smp_ipi::validate_shootdown_request_for_target(
            &shootdown,
            layout.pml4(),
            0,
            target_apic_id,
        )
        .map_err(|_| smp_ipi::Error::Result)?;
        smp_ipi_prepare_resources(
            access,
            layout,
            bsp_apic_id,
            target_apic_id,
            apic_physical,
            &shootdown,
        )
    })();
    match prepare_result {
        Ok((trampoline_bytes, handlers)) => Ok(SmpIpiApResource {
            target_apic_id,
            allocation,
            allocation_receipt,
            layout,
            old_frame: Some(old_frame),
            old_frame_allocation_receipt,
            old_frame_physical,
            new_frame: Some(new_frame),
            new_frame_allocation_receipt,
            new_frame_physical,
            shootdown: ShootdownRequest::canonical_for_target(
                target_apic_id,
                layout.pml4(),
                old_frame_physical,
                new_frame_physical,
            ),
            handlers,
            trampoline_bytes: trampoline_bytes as u64,
        }),
        Err(error) => {
            let _ = manager.free_scrubbed_automatic(new_frame, access);
            let _ = manager.free_scrubbed_automatic(old_frame, access);
            let _ = smp_runtime_release_resources_with_live_mmio(manager, access, allocation);
            Err(error)
        }
    }
}

fn smp_ipi_release_ap_resource(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    resource: &mut SmpIpiApResource,
    mmio_active: bool,
) -> Result<SmpIpiReleaseProof, SmpIpiLiveError> {
    SMP_IPI_FAILURE_STAGE.store(40, Ordering::Relaxed);
    let old_frame = match resource.old_frame.take() {
        Some(handle) => Some(
            manager
                .free_scrubbed_automatic(handle, access)
                .map(|(receipt, _)| receipt)
                .map_err(smp_ipi_memory_error)?,
        ),
        None => None,
    };
    SMP_IPI_FAILURE_STAGE.store(41, Ordering::Relaxed);
    let new_frame = match resource.new_frame.take() {
        Some(handle) => Some(
            manager
                .free_scrubbed_automatic(handle, access)
                .map(|(receipt, _)| receipt)
                .map_err(smp_ipi_memory_error)?,
        ),
        None => None,
    };
    SMP_IPI_FAILURE_STAGE.store(42, Ordering::Relaxed);
    let resource_receipt = if mmio_active {
        smp_runtime_release_resources_with_live_mmio(manager, access, resource.allocation)?
    } else {
        smp_runtime_release_resources(manager, access, resource.allocation)?
    };
    Ok(SmpIpiReleaseProof {
        old_frame,
        new_frame,
        resource: resource_receipt,
    })
}

fn smp_ipi_allocate_resource_set(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    bsp_apic_id: u32,
    target_apic_ids: [u32; smp_ipi::AP_COUNT],
    apic_physical: u64,
) -> Result<[SmpIpiApResource; smp_ipi::AP_COUNT], SmpIpiLiveError> {
    let first = smp_ipi_allocate_ap_resource(
        manager,
        access,
        bsp_apic_id,
        target_apic_ids[0],
        apic_physical,
    )?;
    let second = match smp_ipi_allocate_ap_resource(
        manager,
        access,
        bsp_apic_id,
        target_apic_ids[1],
        apic_physical,
    ) {
        Ok(value) => value,
        Err(error) => {
            let mut first = first;
            let _ = smp_ipi_release_ap_resource(manager, access, &mut first, true);
            return Err(error);
        }
    };
    let third = match smp_ipi_allocate_ap_resource(
        manager,
        access,
        bsp_apic_id,
        target_apic_ids[2],
        apic_physical,
    ) {
        Ok(value) => value,
        Err(error) => {
            let mut first = first;
            let mut second = second;
            let _ = smp_ipi_release_ap_resource(manager, access, &mut second, true);
            let _ = smp_ipi_release_ap_resource(manager, access, &mut first, true);
            return Err(error);
        }
    };
    Ok([first, second, third])
}

fn smp_ipi_start_ap(
    hardware: &mut LiveInterruptHardware,
    access: &mut BootstrapTableMemory,
    period_femtoseconds: u64,
    resource: &SmpIpiApResource,
) -> Result<(), SmpIpiLiveError> {
    access
        .ensure_mapped(resource.layout.local())
        .map_err(|_| smp::Error::PhysicalAccess)?;
    smp_init_sequence(hardware, resource.target_apic_id, period_femtoseconds)?;
    smp_apic_command(
        hardware,
        resource.target_apic_id,
        SMP_APIC_STARTUP | u32::from(resource.layout.sipi_vector()),
    )?;
    smp_hpet_wait(hardware, period_femtoseconds, SMP_INTER_IPI_NANOSECONDS)?;
    smp_apic_command(
        hardware,
        resource.target_apic_id,
        SMP_APIC_STARTUP | u32::from(resource.layout.sipi_vector()),
    )?;
    smp_hpet_wait(hardware, period_femtoseconds, SMP_INTER_IPI_NANOSECONDS)?;
    smp_wait_mailbox_state(
        hardware,
        period_femtoseconds,
        smp_runtime::MAILBOX_STATE_PREPARED,
        smp_runtime::MAILBOX_STATE_ONLINE,
    )?;
    Ok(())
}

fn smp_ipi_stop_ap(
    hardware: &mut LiveInterruptHardware,
    access: &mut BootstrapTableMemory,
    period_femtoseconds: u64,
    resource: &SmpIpiApResource,
) -> Result<(RuntimeMailboxSnapshot, IpiSnapshot), SmpIpiLiveError> {
    access
        .ensure_mapped(resource.layout.local())
        .map_err(|_| smp::Error::PhysicalAccess)?;
    let request = IpiRequest::canonical(4, 3, IpiOperation::Stop, resource.target_apic_id);
    let _ = smp_ipi_deliver(
        hardware,
        period_femtoseconds,
        IpiOperation::Stop,
        &request,
        smp_ipi::ACK_ACCEPTED,
        smp_ipi::ERROR_NONE,
        smp_ipi::RESULT_STOP_QUIESCED,
    )?;
    smp_wait_mailbox_state(
        hardware,
        period_femtoseconds,
        smp_runtime::MAILBOX_STATE_ONLINE,
        smp_runtime::MAILBOX_STATE_QUIESCED,
    )?;
    let ipi = smp_ipi_mailbox_snapshot();
    let mut mailbox = smp_runtime_mailbox_snapshot();
    mailbox.baseline_checksum = smp_runtime::baseline_checksum(&mailbox);
    smp_runtime_mailbox_write_u64(
        smp_runtime::MAILBOX_BASELINE_CHECKSUM_OFFSET,
        mailbox.baseline_checksum,
    );
    mailbox.runtime_checksum = smp_runtime::runtime_checksum(&mailbox);
    smp_runtime_mailbox_write_u64(
        smp_runtime::MAILBOX_RUNTIME_CHECKSUM_OFFSET,
        mailbox.runtime_checksum,
    );
    Ok((smp_runtime_mailbox_snapshot(), ipi))
}

fn smp_ipi_run_partial_rollback(
    manager: &mut PhysicalMemoryManager,
    access: &mut BootstrapTableMemory,
    hardware: &mut LiveInterruptHardware,
    period_femtoseconds: u64,
    bsp_apic_id: u32,
    apic_physical: u64,
    transaction: &mut smp_ipi::MultiApTransaction,
) -> Result<SmpIpiPartialRollbackProof, SmpIpiLiveError> {
    SMP_IPI_FAILURE_STAGE.store(20, Ordering::Relaxed);
    let mut resources = smp_ipi_allocate_resource_set(
        manager,
        access,
        bsp_apic_id,
        smp_ipi::EXPECTED_APIC_IDS,
        apic_physical,
    )?;
    SMP_IPI_FAILURE_STAGE.store(21, Ordering::Relaxed);
    transaction.reserve()?;
    transaction.prepare()?;
    let mut started_mask = 0u64;
    let attempt = (|| -> Result<(), SmpIpiLiveError> {
        for (index, resource) in resources.iter().take(2).enumerate() {
            SMP_IPI_FAILURE_STAGE.store(22 + index as u32, Ordering::Relaxed);
            smp_ipi_start_ap(hardware, access, period_femtoseconds, resource)?;
            started_mask |= smp_ipi::local_target_mask(resource.target_apic_id)
                .ok_or(smp_ipi::Error::Target)?;
        }
        SMP_IPI_FAILURE_STAGE.store(24, Ordering::Relaxed);
        transaction.partial_started(started_mask)?;
        access
            .ensure_mapped(resources[2].layout.local())
            .map_err(|_| smp::Error::PhysicalAccess)?;
        SMP_IPI_FAILURE_STAGE.store(25, Ordering::Relaxed);
        smp_init_sequence(hardware, smp_ipi::OFFLINE_APIC_ID, period_femtoseconds)?;
        for _ in 0..2 {
            smp_apic_command(
                hardware,
                smp_ipi::OFFLINE_APIC_ID,
                SMP_APIC_STARTUP | u32::from(resources[2].layout.sipi_vector()),
            )?;
            smp_hpet_wait(hardware, period_femtoseconds, SMP_INTER_IPI_NANOSECONDS)?;
        }
        SMP_IPI_FAILURE_STAGE.store(26, Ordering::Relaxed);
        match smp_wait_mailbox_state(
            hardware,
            period_femtoseconds,
            smp_runtime::MAILBOX_STATE_PREPARED,
            smp_runtime::MAILBOX_STATE_ONLINE,
        ) {
            Err(smp::Error::Timeout) => {}
            Err(error) => return Err(error.into()),
            Ok(()) => return Err(smp_ipi::Error::Target.into()),
        }
        transaction.partial_timeout(smp_ipi::OFFLINE_APIC_ID)?;
        Ok(())
    })();

    SMP_IPI_FAILURE_STAGE.store(27, Ordering::Relaxed);
    let mut parked_mask = 0u64;
    for resource in resources.iter().take(2).rev() {
        let mask =
            smp_ipi::local_target_mask(resource.target_apic_id).ok_or(smp_ipi::Error::Target)?;
        if started_mask & mask != 0 {
            smp_init_sequence(hardware, resource.target_apic_id, period_femtoseconds)
                .map_err(|_| smp_ipi::Error::Rollback)?;
            parked_mask |= mask;
        }
    }
    if parked_mask != started_mask {
        return Err(smp_ipi::Error::Rollback.into());
    }
    if let Err(error) = attempt {
        for resource in resources.iter_mut().rev() {
            let _ = smp_ipi_release_ap_resource(manager, access, resource, true);
        }
        return Err(error);
    }
    SMP_IPI_FAILURE_STAGE.store(28, Ordering::Relaxed);
    transaction.partial_parked(parked_mask)?;

    let mut resource_pages_released = 0u64;
    let mut frame_pages_released = 0u64;
    let mut zeroed_bytes = 0u64;
    let mut verified_bytes = 0u64;
    SMP_IPI_FAILURE_STAGE.store(29, Ordering::Relaxed);
    for (release_index, resource) in resources.iter_mut().rev().enumerate() {
        SMP_IPI_FAILURE_STAGE.store(29 + release_index as u32, Ordering::Relaxed);
        let release = smp_ipi_release_ap_resource(manager, access, resource, true)?;
        resource_pages_released = resource_pages_released
            .checked_add(release.resource.page_count)
            .ok_or(smp::Error::Memory)?;
        zeroed_bytes = zeroed_bytes
            .checked_add(release.resource.zeroed_bytes)
            .ok_or(smp::Error::Memory)?;
        verified_bytes = verified_bytes
            .checked_add(release.resource.verified_bytes)
            .ok_or(smp::Error::Memory)?;
        for frame in [release.old_frame, release.new_frame].into_iter().flatten() {
            frame_pages_released = frame_pages_released
                .checked_add(frame.page_count)
                .ok_or(smp::Error::Memory)?;
            zeroed_bytes = zeroed_bytes
                .checked_add(frame.zeroed_bytes)
                .ok_or(smp::Error::Memory)?;
            verified_bytes = verified_bytes
                .checked_add(frame.verified_bytes)
                .ok_or(smp::Error::Memory)?;
        }
    }
    SMP_IPI_FAILURE_STAGE.store(43, Ordering::Relaxed);
    if resource_pages_released != smp_runtime::RESOURCE_PAGE_COUNT * smp_ipi::AP_COUNT as u64
        || frame_pages_released != 2 * smp_ipi::AP_COUNT as u64
    {
        return Err(smp_ipi::Error::Rollback.into());
    }
    SMP_IPI_FAILURE_STAGE.store(44, Ordering::Relaxed);
    transaction.partial_released(smp_ipi::TARGET_CPU_MASK)?;
    Ok(SmpIpiPartialRollbackProof {
        started_mask,
        parked_mask,
        released_mask: smp_ipi::TARGET_CPU_MASK,
        timeout_target_apic_id: smp_ipi::OFFLINE_APIC_ID,
        timeout_count: smp_ipi::LIVE_TIMEOUT_COUNT,
        resource_pages_released,
        frame_pages_released,
        zeroed_bytes,
        verified_bytes,
    })
}

#[cfg(any())]
fn run_smp_ipi_legacy(
    handoff: &poole_handoff::Handoff<'_>,
    core: poole_handoff::CoreRecord,
    observed_cr3: u64,
) -> Result<SmpIpiLiveProof, SmpIpiLiveError> {
    SMP_IPI_FAILURE_DETAIL.store(0, Ordering::Relaxed);
    SMP_IPI_FAILURE_STAGE.store(1, Ordering::Relaxed);
    let physical_bits = arch::x86_64::physical_address_bits().ok_or(smp::Error::Memory)?;
    let mut page_access =
        BootstrapTableMemory::new(observed_cr3, physical_bits).map_err(|_| smp::Error::Memory)?;
    let mut manager = PhysicalMemoryManager::from_handoff(handoff, core, DEFAULT_QUOTA_PAGES)
        .map_err(|_| smp::Error::Memory)?;
    manager
        .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
        .map_err(|_| smp::Error::Memory)?;
    let acpi_snapshot = acpi::consume_required_tables(handoff, &mut manager, &mut page_access)
        .map_err(smp::Error::Acpi)?;
    let madt_receipt = acpi_snapshot.required_tables[0];
    let hpet_receipt = acpi_snapshot.required_tables[2];
    let madt_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(madt_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let hpet_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(hpet_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let topology = parse_madt(&mut page_access, madt_snapshot, madt_receipt.byte_count)
        .map_err(|_| smp::Error::Madt)?;
    let hpet = parse_hpet(&mut page_access, hpet_snapshot, hpet_receipt.byte_count)
        .map_err(|_| smp::Error::Hpet)?;
    if !hpet.counter_64_bit_capable {
        return Err(smp::Error::Hpet.into());
    }
    let cpu = arch::x86_64::observe_apic_cpu();
    if !cpu.apic_supported {
        return Err(smp::Error::Apic.into());
    }
    // SAFETY: CPUID reports APIC and selector 14 runs at CPL0 with IF clear.
    let original_apic_base = unsafe { arch::x86_64::read_local_apic_base() };
    if original_apic_base & (APIC_BASE_ENABLE | APIC_BASE_X2APIC) != APIC_BASE_ENABLE {
        return Err(smp::Error::Apic.into());
    }
    let apic_physical = original_apic_base & interrupt_time::APIC_BASE_ADDRESS_MASK;
    if apic_physical != topology.local_apic_address
        || apic_physical != smp_ipi::APIC_PHYSICAL_ADDRESS
    {
        return Err(smp::Error::Apic.into());
    }
    let target = smp::select_first_ap(&topology, cpu.initial_apic_id)?;
    let (allocation, allocation_receipt) = manager
        .allocate_scrubbed(
            Zone::Dma,
            smp_runtime::RESOURCE_PAGE_COUNT,
            SMP_RESOURCE_OWNER,
            &mut page_access,
        )
        .map_err(|_| smp::Error::Memory)?;
    let layout = smp_runtime::ResourceLayout::new(allocation.start_page, allocation.page_count)?;
    let (old_frame, old_frame_allocation_receipt) = match manager.allocate_scrubbed(
        Zone::Dma,
        1,
        smp_ipi::SHOOTDOWN_FRAME_OWNER,
        &mut page_access,
    ) {
        Ok(value) => value,
        Err(_) => {
            let _ = smp_runtime_release_resources(&mut manager, &mut page_access, allocation)?;
            return Err(smp::Error::Memory.into());
        }
    };
    let (new_frame, new_frame_allocation_receipt) = match manager.allocate_scrubbed(
        Zone::Dma,
        1,
        smp_ipi::SHOOTDOWN_FRAME_OWNER,
        &mut page_access,
    ) {
        Ok(value) => value,
        Err(_) => {
            let _ = manager.free_scrubbed(old_frame, &mut page_access);
            let _ = smp_runtime_release_resources(&mut manager, &mut page_access, allocation)?;
            return Err(smp::Error::Memory.into());
        }
    };
    let old_frame_physical = old_frame
        .start_page
        .checked_mul(smp_ipi::PAGE_BYTES)
        .ok_or(smp::Error::Memory)?;
    let new_frame_physical = new_frame
        .start_page
        .checked_mul(smp_ipi::PAGE_BYTES)
        .ok_or(smp::Error::Memory)?;
    PhysicalPageAccess::write_word(
        &mut page_access,
        old_frame_physical,
        0,
        smp_ipi::OLD_FRAME_VALUE,
    )
    .map_err(|_| smp::Error::Memory)?;
    PhysicalPageAccess::write_word(
        &mut page_access,
        new_frame_physical,
        0,
        smp_ipi::NEW_FRAME_VALUE,
    )
    .map_err(|_| smp::Error::Memory)?;
    if PhysicalPageAccess::read_word(&mut page_access, old_frame_physical, 0)
        .map_err(|_| smp::Error::Memory)?
        != smp_ipi::OLD_FRAME_VALUE
        || PhysicalPageAccess::read_word(&mut page_access, new_frame_physical, 0)
            .map_err(|_| smp::Error::Memory)?
            != smp_ipi::NEW_FRAME_VALUE
    {
        return Err(smp::Error::Memory.into());
    }
    let shootdown =
        ShootdownRequest::canonical(layout.pml4(), old_frame_physical, new_frame_physical);
    smp_ipi::validate_shootdown_request(&shootdown, layout.pml4(), 0)
        .map_err(|_| smp_ipi::Error::Result)?;
    let mut deferred_reclaim =
        smp_ipi::DeferredReclaim::new(shootdown).map_err(|_| smp_ipi::Error::Transition)?;
    let mut transaction = smp_ipi::IpiTransaction::new();
    transaction.reserve()?;
    let (trampoline_bytes, handlers) = match smp_ipi_prepare_resources(
        &mut page_access,
        layout,
        cpu.initial_apic_id,
        target.apic_id,
        apic_physical,
        &shootdown,
    ) {
        Ok(value) => value,
        Err(error) => {
            let _ = manager.free_scrubbed(new_frame, &mut page_access);
            let _ = manager.free_scrubbed(old_frame, &mut page_access);
            smp_runtime_release_resources(&mut manager, &mut page_access, allocation)?;
            let _ = transaction.rollback(false)?;
            return Err(error);
        }
    };
    transaction.prepare()?;
    let hpet_page = hpet.physical_address & !0xfff;
    let (apic_virtual, hpet_page_virtual) =
        match page_access.install_uncached_mmio(apic_physical, hpet_page) {
            Ok(value) => value,
            Err(_) => {
                smp_runtime_release_resources(&mut manager, &mut page_access, allocation)?;
                let _ = transaction.rollback(false)?;
                return Err(smp::Error::PhysicalAccess.into());
            }
        };
    let hpet_virtual = hpet_page_virtual
        .checked_add(hpet.physical_address & 0xfff)
        .ok_or(smp::Error::Hpet)?;
    let mut hardware = LiveInterruptHardware {
        local_apic_virtual: apic_virtual,
        hpet_virtual,
    };
    let mut original_hpet_config = None;
    let mut pic_masks = None;
    let mut hpet_changed = false;
    let mut ap_started = false;
    let mut old_frame_release_receipt: Option<ScrubReceipt> = None;
    let mut new_frame_release_receipt: Option<ScrubReceipt> = None;
    let mut period_femtoseconds = None;
    let mut operation_result = (|| -> Result<SmpIpiOperationProof, SmpIpiLiveError> {
        SMP_IPI_FAILURE_STAGE.store(2, Ordering::Relaxed);
        let discovery = validate_apic_discovery(
            &topology,
            cpu,
            original_apic_base,
            hardware.apic_read(0x20).map_err(|_| smp::Error::Apic)?,
            hardware.apic_read(0x30).map_err(|_| smp::Error::Apic)?,
        )
        .map_err(|_| smp::Error::Apic)?;
        if !discovery.bsp || !discovery.globally_enabled || discovery.apic_id != cpu.initial_apic_id
        {
            return Err(smp::Error::Apic.into());
        }
        let period = smp_hpet_period(&hardware)?;
        period_femtoseconds = Some(period);
        let hpet_config = hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)?;
        original_hpet_config = Some(hpet_config);
        if topology.pcat_compatible {
            // SAFETY: IF is clear and PKSMP3 restores the exact masks after final INIT.
            pic_masks = Some(
                unsafe { arch::x86_64::mask_legacy_pic() }
                    .map_err(|_| smp::Error::PhysicalAccess)?,
            );
        }
        if hpet_config & 1 == 0 {
            hardware
                .hpet_write(0x10, hpet_config | 1)
                .map_err(|_| smp::Error::Hpet)?;
            hpet_changed = true;
            if hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)? != hpet_config | 1 {
                return Err(smp::Error::Hpet.into());
            }
        }
        let (bsp_leaf1_ecx, bsp_leaf1_edx) = arch::x86_64::observe_leaf1_features();
        if bsp_leaf1_ecx & smp_runtime::REQUIRED_HARDWARE_LEAF1_ECX
            != smp_runtime::REQUIRED_HARDWARE_LEAF1_ECX
            || bsp_leaf1_edx & smp::REQUIRED_LEAF1_EDX != smp::REQUIRED_LEAF1_EDX
        {
            return Err(smp_runtime::Error::FeatureMismatch.into());
        }
        let bsp_tsc_before = arch::x86_64::read_tsc_ordered();
        smp_init_sequence(&mut hardware, target.apic_id, period)?;
        SMP_IPI_FAILURE_STAGE.store(3, Ordering::Relaxed);
        ap_started = true;
        transaction.startup_sent()?;
        smp_apic_command(
            &mut hardware,
            target.apic_id,
            SMP_APIC_STARTUP | u32::from(layout.sipi_vector()),
        )?;
        smp_hpet_wait(&hardware, period, SMP_INTER_IPI_NANOSECONDS)?;
        smp_apic_command(
            &mut hardware,
            target.apic_id,
            SMP_APIC_STARTUP | u32::from(layout.sipi_vector()),
        )?;
        smp_hpet_wait(&hardware, period, SMP_INTER_IPI_NANOSECONDS)?;
        smp_wait_mailbox_state(
            &hardware,
            period,
            smp_runtime::MAILBOX_STATE_PREPARED,
            smp_runtime::MAILBOX_STATE_ONLINE,
        )?;
        SMP_IPI_FAILURE_STAGE.store(4, Ordering::Relaxed);
        let bsp_tsc_after = arch::x86_64::read_tsc_ordered();
        transaction.online()?;
        if smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_OBSERVED_BEFORE_OFFSET)
            != smp_ipi::OLD_FRAME_VALUE
        {
            return Err(smp_ipi::Error::Result.into());
        }

        let mut request = IpiRequest::canonical(1, 1, IpiOperation::Reschedule, target.apic_id);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Reschedule,
            &request,
            smp_ipi::ACK_ACCEPTED,
            smp_ipi::ERROR_NONE,
            smp_ipi::RESULT_RESCHEDULE_OBSERVED,
        )?;
        request = IpiRequest::canonical(2, 2, IpiOperation::Shootdown, target.apic_id);
        request.capability_high ^= 1;
        request.checksum = smp_ipi::request_checksum(&request);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Shootdown,
            &request,
            smp_ipi::ACK_DENIED,
            smp_ipi::ERROR_CAPABILITY,
            0,
        )?;
        request = IpiRequest::canonical(3, 2, IpiOperation::Shootdown, target.apic_id);
        request.vector = u32::from(IpiOperation::Diagnostic.vector());
        request.checksum = smp_ipi::request_checksum(&request);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Shootdown,
            &request,
            smp_ipi::ACK_DENIED,
            smp_ipi::ERROR_VECTOR,
            0,
        )?;
        request = IpiRequest::canonical(4, 0, IpiOperation::Shootdown, target.apic_id);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Shootdown,
            &request,
            smp_ipi::ACK_DENIED,
            smp_ipi::ERROR_STALE_SEQUENCE,
            0,
        )?;
        request = IpiRequest::canonical(5, 1, IpiOperation::Shootdown, target.apic_id);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Shootdown,
            &request,
            smp_ipi::ACK_DENIED,
            smp_ipi::ERROR_DUPLICATE_SEQUENCE,
            0,
        )?;
        deferred_reclaim
            .arm()
            .map_err(|_| smp_ipi::Error::Transition)?;
        SMP_IPI_FAILURE_STAGE.store(5, Ordering::Relaxed);
        let mut offline_shootdown = shootdown;
        offline_shootdown.target_mask = smp_ipi::OFFLINE_CPU_MASK;
        offline_shootdown.checksum = smp_ipi::shootdown_request_checksum(&offline_shootdown);
        smp_ipi_mailbox_write_u64(
            smp_ipi::SHOOTDOWN_TARGET_MASK_OFFSET,
            offline_shootdown.target_mask,
        );
        smp_ipi_mailbox_write_u64(
            smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_OFFSET,
            offline_shootdown.checksum,
        );
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_STATE_OFFSET,
            smp_ipi::SHOOTDOWN_STATE_ARMED,
        );
        request = IpiRequest::canonical(6, 2, IpiOperation::Shootdown, 2);
        smp_ipi_publish_request(&request);
        smp_apic_command(
            &mut hardware,
            2,
            u32::from(IpiOperation::Shootdown.vector()),
        )?;
        SMP_IPI_FAILURE_STAGE.store(6, Ordering::Relaxed);
        match smp_ipi_wait_ack(&hardware, period, request.attempt) {
            Err(SmpIpiLiveError::Base(smp::Error::Timeout)) => {}
            Err(error) => return Err(error),
            Ok(_) => return Err(smp_ipi::Error::Target.into()),
        }
        deferred_reclaim
            .timeout()
            .map_err(|_| smp_ipi::Error::Transition)?;
        SMP_IPI_FAILURE_STAGE.store(7, Ordering::Relaxed);
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_TIMEOUT_COUNT_OFFSET,
            smp_ipi::LIVE_TIMEOUT_COUNT,
        );
        smp_ipi_mailbox_write_u64(smp_ipi::SHOOTDOWN_TARGET_MASK_OFFSET, shootdown.target_mask);
        smp_ipi_mailbox_write_u64(
            smp_ipi::SHOOTDOWN_REQUEST_CHECKSUM_OFFSET,
            shootdown.checksum,
        );
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_STATE_OFFSET,
            smp_ipi::SHOOTDOWN_STATE_PREPARED,
        );
        deferred_reclaim
            .arm()
            .map_err(|_| smp_ipi::Error::Transition)?;
        let premature_reclaim_rejected = deferred_reclaim.authorize().is_err();
        if !premature_reclaim_rejected {
            return Err(smp_ipi::Error::Transition.into());
        }
        let probe_leaf_before = TableMemory::read_entry(
            &mut page_access,
            layout.page_table(),
            smp_ipi::PROBE_PAGE_TABLE_INDEX,
        )
        .map_err(|_| smp::Error::Memory)?;
        if probe_leaf_before & 0x000f_ffff_ffff_f000 != old_frame_physical
            || probe_leaf_before & SMP_IPI_ENTRY_ACCESSED == 0
        {
            return Err(smp_ipi::Error::PageRole.into());
        }
        TableMemory::write_entry(
            &mut page_access,
            layout.page_table(),
            smp_ipi::PROBE_PAGE_TABLE_INDEX,
            new_frame_physical | smp::ENTRY_PRESENT | smp::ENTRY_WRITABLE | smp::ENTRY_NO_EXECUTE,
        )
        .map_err(|_| smp::Error::Memory)?;
        arch::x86_64::memory_fence();
        page_access
            .ensure_mapped(layout.local())
            .map_err(|_| smp::Error::PhysicalAccess)?;
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_STATE_OFFSET,
            smp_ipi::SHOOTDOWN_STATE_ARMED,
        );
        request = IpiRequest::canonical(6, 2, IpiOperation::Shootdown, target.apic_id);
        let shootdown_ack = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Shootdown,
            &request,
            smp_ipi::ACK_ACCEPTED,
            smp_ipi::ERROR_NONE,
            smp_ipi::RESULT_SHOOTDOWN_INVALIDATED,
        )?;
        SMP_IPI_FAILURE_STAGE.store(8, Ordering::Relaxed);
        smp_ipi::validate_shootdown_ack(&shootdown_ack.shootdown, &shootdown)?;
        deferred_reclaim
            .acknowledge(&shootdown_ack.shootdown)
            .map_err(|_| smp_ipi::Error::Transition)?;
        let retirement_receipt = deferred_reclaim
            .authorize()
            .map_err(|_| smp_ipi::Error::Transition)?;
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_RECLAIM_STATE_OFFSET,
            smp_ipi::RECLAIM_AUTHORIZED,
        );
        let retired_release = manager
            .free_scrubbed(old_frame, &mut page_access)
            .map_err(|_| smp::Error::Memory)?;
        page_access
            .ensure_mapped(layout.local())
            .map_err(|_| smp::Error::PhysicalAccess)?;
        deferred_reclaim
            .released(retirement_receipt)
            .map_err(|_| smp_ipi::Error::Transition)?;
        old_frame_release_receipt = Some(retired_release);
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_RECLAIM_STATE_OFFSET,
            smp_ipi::RECLAIM_RELEASED,
        );
        request = IpiRequest::canonical(7, 3, IpiOperation::CallFunction, target.apic_id);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::CallFunction,
            &request,
            smp_ipi::ACK_ACCEPTED,
            smp_ipi::ERROR_NONE,
            smp_ipi::RESULT_CALL_ALLOWLIST_NOOP,
        )?;
        request = IpiRequest::canonical(8, 4, IpiOperation::Diagnostic, target.apic_id);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Diagnostic,
            &request,
            smp_ipi::ACK_ACCEPTED,
            smp_ipi::ERROR_NONE,
            smp_ipi::RESULT_DIAGNOSTIC_OBSERVED,
        )?;
        request = IpiRequest::canonical(9, 5, IpiOperation::Panic, target.apic_id);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Panic,
            &request,
            smp_ipi::ACK_ACCEPTED,
            smp_ipi::ERROR_NONE,
            smp_ipi::RESULT_PANIC_LATCHED,
        )?;
        transaction.exercised()?;
        request = IpiRequest::canonical(10, 6, IpiOperation::Stop, target.apic_id);
        SMP_IPI_FAILURE_STAGE.store(9, Ordering::Relaxed);
        let _ = smp_ipi_deliver(
            &mut hardware,
            period,
            IpiOperation::Stop,
            &request,
            smp_ipi::ACK_ACCEPTED,
            smp_ipi::ERROR_NONE,
            smp_ipi::RESULT_STOP_QUIESCED,
        )?;
        smp_wait_mailbox_state(
            &hardware,
            period,
            smp_runtime::MAILBOX_STATE_ONLINE,
            smp_runtime::MAILBOX_STATE_QUIESCED,
        )?;
        let ipi = smp_ipi_mailbox_snapshot();
        transaction.quiesced()?;

        let mut mailbox = smp_runtime_mailbox_snapshot();
        mailbox.baseline_checksum = smp_runtime::baseline_checksum(&mailbox);
        smp_runtime_mailbox_write_u64(
            smp_runtime::MAILBOX_BASELINE_CHECKSUM_OFFSET,
            mailbox.baseline_checksum,
        );
        mailbox.runtime_checksum = smp_runtime::runtime_checksum(&mailbox);
        smp_runtime_mailbox_write_u64(
            smp_runtime::MAILBOX_RUNTIME_CHECKSUM_OFFSET,
            mailbox.runtime_checksum,
        );
        mailbox = smp_runtime_mailbox_snapshot();
        smp_runtime::validate_mailbox(
            &mailbox,
            layout,
            bsp_leaf1_ecx,
            bsp_leaf1_edx,
            bsp_tsc_before,
            bsp_tsc_after,
        )?;
        smp_ipi::validate_final(&ipi, target.apic_id, smp_ipi::LIVE_TIMEOUT_COUNT)?;
        Ok(SmpIpiOperationProof {
            mailbox,
            ipi,
            handlers,
            init_asserts: 1,
            init_deasserts: 1,
            sipis: 2,
            timeout_count: smp_ipi::LIVE_TIMEOUT_COUNT,
            tss_busy_verified: false,
            idt_verified: false,
            xstate_verified: false,
            apic_table_verified: false,
            retirement_receipt,
            old_frame_release_receipt: retired_release,
            premature_reclaim_rejected,
        })
    })();
    let operation_failure_stage = operation_result
        .as_ref()
        .err()
        .map(|_| SMP_IPI_FAILURE_STAGE.load(Ordering::Relaxed));
    if operation_result.is_err() {
        let detail = (u64::from(smp_ipi_mailbox_read_u32(smp_ipi::SERVICE_STATE_OFFSET) & 0x0f)
            << 32)
            | ((smp_ipi_mailbox_read_u64(smp_ipi::ACK_ATTEMPT_OFFSET) & 0xff) << 36)
            | (u64::from(smp_ipi_mailbox_read_u32(smp_ipi::ACK_STATUS_OFFSET) & 0x0f) << 44)
            | (u64::from(smp_ipi_mailbox_read_u32(smp_ipi::ACK_ERROR_OFFSET) & 0xff) << 48)
            | (u64::from(smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_STATE_OFFSET) & 0x0f) << 56)
            | (u64::from(smp_ipi_mailbox_read_u32(smp_ipi::SHOOTDOWN_ERROR_OFFSET) & 0x0f) << 60);
        SMP_IPI_FAILURE_DETAIL.store(detail, Ordering::Relaxed);
    }

    let park_result = if ap_started {
        SMP_IPI_FAILURE_STAGE.store(10, Ordering::Relaxed);
        match period_femtoseconds {
            Some(period) => smp_init_sequence(&mut hardware, target.apic_id, period),
            None => Err(smp::Error::Rollback),
        }
    } else {
        Ok(())
    };
    if park_result.is_err() {
        if let (true, Some(config)) = (hpet_changed, original_hpet_config) {
            let _ = hardware.hpet_write(0x10, config);
        }
        if let Some(masks) = pic_masks {
            // SAFETY: IF remains clear; retaining all AP resources takes precedence.
            let _ = unsafe { arch::x86_64::restore_legacy_pic(masks) };
        }
        return Err(smp_ipi::Error::Rollback.into());
    }
    if operation_result.is_ok() {
        transaction.parked()?;
    }

    if let Ok(mut operation) = operation_result {
        SMP_IPI_FAILURE_STAGE.store(11, Ordering::Relaxed);
        operation_result = match smp_ipi_validate_post_ap_resources(
            &mut page_access,
            layout,
            operation.handlers,
            &operation.mailbox,
            apic_physical,
            new_frame_physical,
        ) {
            Ok(()) => {
                transaction.validated()?;
                operation.tss_busy_verified = true;
                operation.idt_verified = true;
                operation.xstate_verified = true;
                operation.apic_table_verified = true;
                Ok(operation)
            }
            Err(error) => Err(error),
        };
    }

    let mut cleanup_error = None;
    SMP_IPI_FAILURE_STAGE.store(12, Ordering::Relaxed);
    if let (true, Some(config)) = (hpet_changed, original_hpet_config) {
        let restore_failed = hardware.hpet_write(0x10, config).is_err()
            || hardware.hpet_read(0x10).ok() != Some(config);
        if restore_failed {
            cleanup_error = Some(SmpIpiLiveError::Base(smp::Error::Hpet));
        }
    }
    if let Some(masks) = pic_masks {
        // SAFETY: the AP is reset, IF is clear, and these are the observed masks.
        if unsafe { arch::x86_64::restore_legacy_pic(masks) }.is_err() {
            cleanup_error = Some(SmpIpiLiveError::Base(smp::Error::PhysicalAccess));
        }
    }
    if page_access.uninstall_uncached_mmio().is_err() {
        cleanup_error = Some(SmpIpiLiveError::Base(smp::Error::PhysicalAccess));
    }
    if old_frame_release_receipt.is_none() {
        match manager.free_scrubbed(old_frame, &mut page_access) {
            Ok(_) => {}
            Err(_) => cleanup_error = Some(SmpIpiLiveError::Base(smp::Error::Memory)),
        }
    }
    match manager.free_scrubbed(new_frame, &mut page_access) {
        Ok(receipt) => new_frame_release_receipt = Some(receipt),
        Err(_) => cleanup_error = Some(SmpIpiLiveError::Base(smp::Error::Memory)),
    }
    let release_receipt =
        match smp_runtime_release_resources(&mut manager, &mut page_access, allocation) {
            Ok(value) => value,
            Err(error) => {
                cleanup_error = Some(error.into());
                allocation_receipt
            }
        };
    match operation_result {
        Err(error) => {
            let _ = transaction.rollback(true)?;
            match cleanup_error {
                Some(cleanup) => Err(cleanup),
                None => {
                    SMP_IPI_FAILURE_STAGE
                        .store(operation_failure_stage.unwrap_or(0), Ordering::Relaxed);
                    Err(error)
                }
            }
        }
        Ok(operation) => {
            if let Some(error) = cleanup_error {
                return Err(error);
            }
            let new_frame_release_receipt = new_frame_release_receipt.ok_or(smp::Error::Memory)?;
            transaction.released()?;
            SMP_IPI_FAILURE_STAGE.store(0, Ordering::Relaxed);
            Ok(SmpIpiLiveProof {
                processor_count: topology.processor_count as u64,
                enabled_processor_count: topology.enabled_processor_count as u64,
                bsp_apic_id: cpu.initial_apic_id,
                target_apic_id: target.apic_id,
                apic_physical,
                layout,
                trampoline_bytes: trampoline_bytes as u64,
                allocation_receipt,
                release_receipt,
                old_frame_allocation_receipt,
                new_frame_allocation_receipt,
                new_frame_release_receipt,
                operation,
            })
        }
    }
}

fn run_smp_ipi(
    handoff: &poole_handoff::Handoff<'_>,
    core: poole_handoff::CoreRecord,
    observed_cr3: u64,
) -> Result<SmpIpiLiveProof, SmpIpiLiveError> {
    SMP_IPI_FAILURE_DETAIL.store(0, Ordering::Relaxed);
    SMP_IPI_FAILURE_STAGE.store(1, Ordering::Relaxed);
    let physical_bits = arch::x86_64::physical_address_bits().ok_or(smp::Error::Memory)?;
    let mut page_access =
        BootstrapTableMemory::new(observed_cr3, physical_bits).map_err(|_| smp::Error::Memory)?;
    let mut bootstrap_manager =
        PhysicalMemoryManager::from_handoff(handoff, core, smp_ipi::MULTI_AP_QUOTA_PAGES)
            .map_err(|_| smp::Error::Memory)?;
    let metadata_migration = bootstrap_manager
        .migrate_to_metadata(&mut page_access)
        .map_err(smp_ipi_memory_error)?;
    // SAFETY: PKPMM7 copied, sealed, and validated the complete manager in the
    // guarded metadata mapping, which remains installed for this selector.
    let manager = unsafe {
        &mut *(metadata_migration.manager_address as usize as *mut PhysicalMemoryManager)
    };
    manager
        .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
        .map_err(|_| smp::Error::Memory)?;
    let acpi_snapshot = acpi::consume_required_tables(handoff, manager, &mut page_access)
        .map_err(smp::Error::Acpi)?;
    let madt_receipt = acpi_snapshot.required_tables[0];
    let hpet_receipt = acpi_snapshot.required_tables[2];
    let madt_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(madt_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let hpet_snapshot = acpi_snapshot
        .snapshot_physical_address
        .checked_add(hpet_receipt.snapshot_offset)
        .ok_or(smp::Error::AcpiAddress)?;
    let topology = parse_madt(&mut page_access, madt_snapshot, madt_receipt.byte_count)
        .map_err(|_| smp::Error::Madt)?;
    let hpet = parse_hpet(&mut page_access, hpet_snapshot, hpet_receipt.byte_count)
        .map_err(|_| smp::Error::Hpet)?;
    if !hpet.counter_64_bit_capable {
        return Err(smp::Error::Hpet.into());
    }
    let cpu = arch::x86_64::observe_apic_cpu();
    if !cpu.apic_supported {
        return Err(smp::Error::Apic.into());
    }
    // SAFETY: CPUID reports APIC and selector 14 runs at CPL0 with IF clear.
    let original_apic_base = unsafe { arch::x86_64::read_local_apic_base() };
    if original_apic_base & (APIC_BASE_ENABLE | APIC_BASE_X2APIC) != APIC_BASE_ENABLE {
        return Err(smp::Error::Apic.into());
    }
    let apic_physical = original_apic_base & interrupt_time::APIC_BASE_ADDRESS_MASK;
    if apic_physical != topology.local_apic_address
        || apic_physical != smp_ipi::APIC_PHYSICAL_ADDRESS
    {
        return Err(smp::Error::Apic.into());
    }
    let targets = smp_ipi::select_exact_aps(&topology, cpu.initial_apic_id)?;
    let target_apic_ids = [targets[0].apic_id, targets[1].apic_id, targets[2].apic_id];

    let hpet_page = hpet.physical_address & !0xfff;
    let (apic_virtual, hpet_page_virtual) = page_access
        .install_uncached_mmio(apic_physical, hpet_page)
        .map_err(|_| smp::Error::PhysicalAccess)?;
    let hpet_virtual = hpet_page_virtual
        .checked_add(hpet.physical_address & 0xfff)
        .ok_or(smp::Error::Hpet)?;
    let mut hardware = LiveInterruptHardware {
        local_apic_virtual: apic_virtual,
        hpet_virtual,
    };
    let discovery = validate_apic_discovery(
        &topology,
        cpu,
        original_apic_base,
        hardware.apic_read(0x20).map_err(|_| smp::Error::Apic)?,
        hardware.apic_read(0x30).map_err(|_| smp::Error::Apic)?,
    )
    .map_err(|_| smp::Error::Apic)?;
    if !discovery.bsp || !discovery.globally_enabled || discovery.apic_id != cpu.initial_apic_id {
        return Err(smp::Error::Apic.into());
    }
    let period = smp_hpet_period(&hardware)?;
    let original_hpet_config = hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)?;
    let mut hpet_changed = false;
    let pic_masks = if topology.pcat_compatible {
        // SAFETY: IF is clear and every return path restores these exact masks after AP parking.
        Some(unsafe { arch::x86_64::mask_legacy_pic() }.map_err(|_| smp::Error::PhysicalAccess)?)
    } else {
        None
    };
    if original_hpet_config & 1 == 0 {
        hardware
            .hpet_write(0x10, original_hpet_config | 1)
            .map_err(|_| smp::Error::Hpet)?;
        if hardware.hpet_read(0x10).map_err(|_| smp::Error::Hpet)? != original_hpet_config | 1 {
            return Err(smp::Error::Hpet.into());
        }
        hpet_changed = true;
    }
    let (bsp_leaf1_ecx, bsp_leaf1_edx) = arch::x86_64::observe_leaf1_features();
    if bsp_leaf1_ecx & smp_runtime::REQUIRED_HARDWARE_LEAF1_ECX
        != smp_runtime::REQUIRED_HARDWARE_LEAF1_ECX
        || bsp_leaf1_edx & smp::REQUIRED_LEAF1_EDX != smp::REQUIRED_LEAF1_EDX
    {
        return Err(smp_runtime::Error::FeatureMismatch.into());
    }

    let mut lifecycle = smp_ipi::MultiApTransaction::new();
    SMP_IPI_FAILURE_STAGE.store(2, Ordering::Relaxed);
    let partial = smp_ipi_run_partial_rollback(
        manager,
        &mut page_access,
        &mut hardware,
        period,
        cpu.initial_apic_id,
        apic_physical,
        &mut lifecycle,
    )?;
    lifecycle.retry_reserve()?;
    let mut resources = smp_ipi_allocate_resource_set(
        manager,
        &mut page_access,
        cpu.initial_apic_id,
        target_apic_ids,
        apic_physical,
    )?;
    lifecycle.retry_prepare()?;

    let mut started_mask = 0u64;
    let bsp_tsc_before = arch::x86_64::read_tsc_ordered();
    let operation = (|| -> Result<SmpIpiExecutionReceipt, SmpIpiLiveError> {
        SMP_IPI_FAILURE_STAGE.store(3, Ordering::Relaxed);
        for resource in &resources {
            smp_ipi_start_ap(&mut hardware, &mut page_access, period, resource)?;
            started_mask |= smp_ipi::local_target_mask(resource.target_apic_id)
                .ok_or(smp_ipi::Error::Target)?;
        }
        let bsp_tsc_after = arch::x86_64::read_tsc_ordered();
        lifecycle.all_online(started_mask, started_mask)?;
        SMP_IPI_FAILURE_STAGE.store(4, Ordering::Relaxed);

        for resource in &resources {
            page_access
                .ensure_mapped(resource.layout.local())
                .map_err(|_| smp::Error::PhysicalAccess)?;
            if smp_ipi_mailbox_read_u64(smp_ipi::SHOOTDOWN_OBSERVED_BEFORE_OFFSET)
                != smp_ipi::OLD_FRAME_VALUE
            {
                return Err(smp_ipi::Error::Result.into());
            }
            let diagnostic =
                IpiRequest::canonical(1, 1, IpiOperation::Diagnostic, resource.target_apic_id);
            let _ = smp_ipi_deliver(
                &mut hardware,
                period,
                IpiOperation::Diagnostic,
                &diagnostic,
                smp_ipi::ACK_ACCEPTED,
                smp_ipi::ERROR_NONE,
                smp_ipi::RESULT_DIAGNOSTIC_OBSERVED,
            )?;
            let mut denied =
                IpiRequest::canonical(2, 2, IpiOperation::Shootdown, resource.target_apic_id);
            denied.capability_high ^= 1;
            denied.checksum = smp_ipi::request_checksum(&denied);
            let _ = smp_ipi_deliver(
                &mut hardware,
                period,
                IpiOperation::Shootdown,
                &denied,
                smp_ipi::ACK_DENIED,
                smp_ipi::ERROR_CAPABILITY,
                0,
            )?;
        }

        let requests = [
            resources[0].shootdown,
            resources[1].shootdown,
            resources[2].shootdown,
        ];
        let mut reclaim =
            smp_ipi::MultiDeferredReclaim::new(requests).map_err(|_| smp_ipi::Error::Transition)?;
        reclaim.arm().map_err(|_| smp_ipi::Error::Transition)?;
        page_access
            .ensure_mapped(resources[0].layout.local())
            .map_err(|_| smp::Error::PhysicalAccess)?;
        let offline_request =
            IpiRequest::canonical(3, 2, IpiOperation::Shootdown, smp_ipi::OFFLINE_APIC_ID);
        smp_ipi_publish_request(&offline_request);
        smp_apic_command(
            &mut hardware,
            smp_ipi::OFFLINE_APIC_ID,
            u32::from(IpiOperation::Shootdown.vector()),
        )?;
        match smp_ipi_wait_ack(&hardware, period, offline_request.attempt) {
            Err(SmpIpiLiveError::Base(smp::Error::Timeout)) => {}
            Err(error) => return Err(error),
            Ok(_) => return Err(smp_ipi::Error::Target.into()),
        }
        reclaim
            .timeout(smp_ipi::OFFLINE_CPU_MASK)
            .map_err(|_| smp_ipi::Error::Transition)?;
        smp_ipi_mailbox_write_u32(
            smp_ipi::SHOOTDOWN_TIMEOUT_COUNT_OFFSET,
            smp_ipi::LIVE_TIMEOUT_COUNT,
        );
        reclaim.arm().map_err(|_| smp_ipi::Error::Transition)?;

        let mut premature_reclaim_rejections = 0u64;
        for (index, resource) in resources.iter().enumerate() {
            let probe_leaf_before = TableMemory::read_entry(
                &mut page_access,
                resource.layout.page_table(),
                smp_ipi::PROBE_PAGE_TABLE_INDEX,
            )
            .map_err(|_| smp::Error::Memory)?;
            if probe_leaf_before & 0x000f_ffff_ffff_f000 != resource.old_frame_physical
                || probe_leaf_before & SMP_IPI_ENTRY_ACCESSED == 0
            {
                return Err(smp_ipi::Error::PageRole.into());
            }
            TableMemory::write_entry(
                &mut page_access,
                resource.layout.page_table(),
                smp_ipi::PROBE_PAGE_TABLE_INDEX,
                resource.new_frame_physical
                    | smp::ENTRY_PRESENT
                    | smp::ENTRY_WRITABLE
                    | smp::ENTRY_NO_EXECUTE,
            )
            .map_err(|_| smp::Error::Memory)?;
            arch::x86_64::memory_fence();
            page_access
                .ensure_mapped(resource.layout.local())
                .map_err(|_| smp::Error::PhysicalAccess)?;
            smp_ipi_mailbox_write_u32(
                smp_ipi::SHOOTDOWN_STATE_OFFSET,
                smp_ipi::SHOOTDOWN_STATE_ARMED,
            );
            let request =
                IpiRequest::canonical(3, 2, IpiOperation::Shootdown, resource.target_apic_id);
            let ack = smp_ipi_deliver(
                &mut hardware,
                period,
                IpiOperation::Shootdown,
                &request,
                smp_ipi::ACK_ACCEPTED,
                smp_ipi::ERROR_NONE,
                smp_ipi::RESULT_SHOOTDOWN_INVALIDATED,
            )?;
            smp_ipi::validate_shootdown_ack_for_target(
                &ack.shootdown,
                &resource.shootdown,
                resource.target_apic_id,
            )?;
            reclaim
                .acknowledge(resource.target_apic_id, &ack.shootdown)
                .map_err(|_| smp_ipi::Error::Transition)?;
            if index + 1 != smp_ipi::AP_COUNT {
                if reclaim.authorize().is_ok() {
                    return Err(smp_ipi::Error::Transition.into());
                }
                premature_reclaim_rejections += 1;
            }
        }
        let retirement = reclaim
            .authorize()
            .map_err(|_| smp_ipi::Error::Transition)?;
        lifecycle.exercised(retirement.ack_mask)?;
        SMP_IPI_FAILURE_STAGE.store(5, Ordering::Relaxed);

        let mut old_releases: [Option<ScrubReceipt>; smp_ipi::AP_COUNT] = [None; smp_ipi::AP_COUNT];
        for (index, resource) in resources.iter_mut().enumerate() {
            SMP_IPI_FAILURE_STAGE.store(70 + index as u32, Ordering::Relaxed);
            page_access
                .ensure_mapped(resource.layout.local())
                .map_err(|_| smp::Error::PhysicalAccess)?;
            smp_ipi_mailbox_write_u32(
                smp_ipi::SHOOTDOWN_RECLAIM_STATE_OFFSET,
                smp_ipi::RECLAIM_AUTHORIZED,
            );
            let handle = resource
                .old_frame
                .take()
                .ok_or(smp_ipi::Error::Transition)?;
            old_releases[index] = Some(
                manager
                    .free_scrubbed(handle, &mut page_access)
                    .map_err(|_| smp::Error::Memory)?,
            );
        }
        SMP_IPI_FAILURE_STAGE.store(74, Ordering::Relaxed);
        reclaim
            .released(retirement)
            .map_err(|_| smp_ipi::Error::Transition)?;
        SMP_IPI_FAILURE_STAGE.store(75, Ordering::Relaxed);
        for resource in &resources {
            page_access
                .ensure_mapped(resource.layout.local())
                .map_err(|_| smp::Error::PhysicalAccess)?;
            smp_ipi_mailbox_write_u32(
                smp_ipi::SHOOTDOWN_RECLAIM_STATE_OFFSET,
                smp_ipi::RECLAIM_RELEASED,
            );
        }

        let mut mailboxes: [Option<RuntimeMailboxSnapshot>; smp_ipi::AP_COUNT] =
            [None; smp_ipi::AP_COUNT];
        let mut ipis: [Option<IpiSnapshot>; smp_ipi::AP_COUNT] = [None; smp_ipi::AP_COUNT];
        for (index, resource) in resources.iter().enumerate() {
            SMP_IPI_FAILURE_STAGE.store(80 + index as u32 * 3, Ordering::Relaxed);
            let (mailbox, ipi) =
                smp_ipi_stop_ap(&mut hardware, &mut page_access, period, resource)?;
            SMP_IPI_FAILURE_STAGE.store(81 + index as u32 * 3, Ordering::Relaxed);
            smp_runtime::validate_mailbox(
                &mailbox,
                resource.layout,
                bsp_leaf1_ecx,
                bsp_leaf1_edx,
                bsp_tsc_before,
                bsp_tsc_after,
            )?;
            SMP_IPI_FAILURE_STAGE.store(82 + index as u32 * 3, Ordering::Relaxed);
            smp_ipi::validate_final(&ipi, resource.target_apic_id, u32::from(index == 0))?;
            mailboxes[index] = Some(mailbox);
            ipis[index] = Some(ipi);
        }
        SMP_IPI_FAILURE_STAGE.store(90, Ordering::Relaxed);
        lifecycle.quiesced(smp_ipi::TARGET_CPU_MASK)?;
        Ok((
            [
                mailboxes[0].ok_or(smp_ipi::Error::Transition)?,
                mailboxes[1].ok_or(smp_ipi::Error::Transition)?,
                mailboxes[2].ok_or(smp_ipi::Error::Transition)?,
            ],
            [
                ipis[0].ok_or(smp_ipi::Error::Transition)?,
                ipis[1].ok_or(smp_ipi::Error::Transition)?,
                ipis[2].ok_or(smp_ipi::Error::Transition)?,
            ],
            [
                old_releases[0].ok_or(smp_ipi::Error::Transition)?,
                old_releases[1].ok_or(smp_ipi::Error::Transition)?,
                old_releases[2].ok_or(smp_ipi::Error::Transition)?,
            ],
            retirement,
            premature_reclaim_rejections,
        ))
    })();

    let operation_failure_stage = if operation.is_err() {
        SMP_IPI_FAILURE_STAGE.load(Ordering::Relaxed)
    } else {
        0
    };
    let mut parked_mask = 0u64;
    for resource in resources.iter().rev() {
        let local_mask =
            smp_ipi::local_target_mask(resource.target_apic_id).ok_or(smp_ipi::Error::Target)?;
        if started_mask & local_mask != 0 {
            smp_init_sequence(&mut hardware, resource.target_apic_id, period)
                .map_err(|_| smp_ipi::Error::Rollback)?;
            parked_mask |= local_mask;
        }
    }
    if parked_mask != started_mask {
        return Err(smp_ipi::Error::Rollback.into());
    }

    let mut post_validation_error = None;
    let mut cleanup_failure_stage = 0u32;
    if let Ok((mailboxes, _, _, _, _)) = &operation {
        lifecycle.parked(parked_mask)?;
        SMP_IPI_FAILURE_STAGE.store(6, Ordering::Relaxed);
        for (index, resource) in resources.iter().enumerate() {
            if let Err(error) = smp_ipi_validate_post_ap_resources(
                &mut page_access,
                resource.layout,
                resource.handlers,
                &mailboxes[index],
                apic_physical,
                resource.new_frame_physical,
            ) {
                post_validation_error = Some(error);
                cleanup_failure_stage = 50 + index as u32;
                break;
            }
        }
        if post_validation_error.is_none() {
            lifecycle.validated(smp_ipi::TARGET_CPU_MASK)?;
        }
    }

    let mut cleanup_error = post_validation_error;
    if hpet_changed {
        let restore_failed = hardware.hpet_write(0x10, original_hpet_config).is_err()
            || hardware.hpet_read(0x10).ok() != Some(original_hpet_config);
        if restore_failed {
            cleanup_error = Some(smp::Error::Hpet.into());
            cleanup_failure_stage = 54;
        }
    }
    if let Some(masks) = pic_masks {
        // SAFETY: every started AP is INIT-parked and IF remains clear.
        if unsafe { arch::x86_64::restore_legacy_pic(masks) }.is_err() {
            cleanup_error = Some(smp::Error::PhysicalAccess.into());
            cleanup_failure_stage = 55;
        }
    }
    if page_access.uninstall_uncached_mmio().is_err() {
        cleanup_error = Some(smp::Error::PhysicalAccess.into());
        cleanup_failure_stage = 56;
    }

    let mut releases: [Option<SmpIpiReleaseProof>; smp_ipi::AP_COUNT] = [None; smp_ipi::AP_COUNT];
    for index in (0..smp_ipi::AP_COUNT).rev() {
        match smp_ipi_release_ap_resource(manager, &mut page_access, &mut resources[index], false) {
            Ok(value) => releases[index] = Some(value),
            Err(error) => {
                cleanup_error = Some(error);
                cleanup_failure_stage = 57 + index as u32;
            }
        }
    }
    let operation = match operation {
        Ok(value) => value,
        Err(error) => {
            if cleanup_failure_stage != 0 {
                SMP_IPI_FAILURE_STAGE.store(cleanup_failure_stage, Ordering::Relaxed);
            } else {
                SMP_IPI_FAILURE_STAGE.store(operation_failure_stage, Ordering::Relaxed);
            }
            return Err(cleanup_error.unwrap_or(error));
        }
    };
    if let Some(error) = cleanup_error {
        SMP_IPI_FAILURE_STAGE.store(cleanup_failure_stage, Ordering::Relaxed);
        return Err(error);
    }
    SMP_IPI_FAILURE_STAGE.store(61, Ordering::Relaxed);
    let (mailboxes, ipis, old_releases, retirement, premature_reclaim_rejections) = operation;
    let mut operations: [Option<SmpIpiApOperationProof>; smp_ipi::AP_COUNT] =
        [None; smp_ipi::AP_COUNT];
    for index in 0..smp_ipi::AP_COUNT {
        let release = releases[index].ok_or(smp_ipi::Error::Rollback)?;
        operations[index] = Some(SmpIpiApOperationProof {
            mailbox: mailboxes[index],
            ipi: ipis[index],
            init_asserts: 1,
            init_deasserts: 1,
            sipis: 2,
            timeout_count: u32::from(index == 0),
            old_frame_release_receipt: old_releases[index],
            new_frame_release_receipt: release.new_frame.ok_or(smp_ipi::Error::Rollback)?,
            resource_release_receipt: release.resource,
        });
    }
    SMP_IPI_FAILURE_STAGE.store(62, Ordering::Relaxed);
    let lifecycle_receipt = lifecycle.released(smp_ipi::TARGET_CPU_MASK)?;
    SMP_IPI_FAILURE_STAGE.store(0, Ordering::Relaxed);
    Ok(SmpIpiLiveProof {
        processor_count: topology.processor_count as u64,
        enabled_processor_count: topology.enabled_processor_count as u64,
        bsp_apic_id: cpu.initial_apic_id,
        target_apic_ids,
        apic_physical,
        partial,
        aps: resources,
        operations: [
            operations[0].ok_or(smp_ipi::Error::Rollback)?,
            operations[1].ok_or(smp_ipi::Error::Rollback)?,
            operations[2].ok_or(smp_ipi::Error::Rollback)?,
        ],
        lifecycle: lifecycle_receipt,
        retirement,
        premature_reclaim_rejections,
    })
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
        // SAFETY: PKVM3 runs at CPL0 after PKENTRY1 validates the transfer state.
        unsafe { arch::x86_64::read_cr3() }
    }

    fn write_cr3(&mut self, value: u64) -> Result<(), active_virtual_memory::Error> {
        if value == 0 || !value.is_multiple_of(poole_handoff::PAGE_BYTES) {
            return Err(active_virtual_memory::Error::PhysicalAddress);
        }
        // SAFETY: PKVM3 audits the candidate root or supplies the exact retained root;
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
        // SAFETY: PKVM3 owns the current BSP root and the exact leaf transition.
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
        // SAFETY: PKVM3 supplies an audited, supervisor RW/NX direct-map address.
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
        // SAFETY: PKVM3 supplies an audited, supervisor RW/NX direct-map address.
        unsafe { write_volatile(virtual_address as usize as *mut u64, value) };
        Ok(())
    }

    fn read_u8(&mut self, virtual_address: u64) -> Result<u8, active_virtual_memory::Error> {
        if !virtual_memory::is_canonical_48(virtual_address) || virtual_address > usize::MAX as u64
        {
            return Err(active_virtual_memory::Error::MemoryAccess);
        }
        // SAFETY: PKVM3 supplies its one audited user-window probe address.
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
        // SAFETY: PKVM3 writes only while the audited user-window leaf is writable.
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
        0x1013 => PanicCode::InterruptTime,
        0x1014 => PanicCode::SmpFirstAp,
        0x1015 => PanicCode::SmpPerCpuRuntime,
        0x1016 => PanicCode::SmpIpi,
        0x1017 => PanicCode::Scheduler,
        0x1018 => PanicCode::SchedulerPreempt,
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
    if trap_scenario == DevelopmentTrapScenario::InterruptTime {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKIRQ_EARLY);
    }
    if trap_scenario == DevelopmentTrapScenario::SmpFirstAp {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKSMP_EARLY);
    }
    if trap_scenario == DevelopmentTrapScenario::SmpPerCpuRuntime {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKSMP2_EARLY);
    }
    #[cfg(any())]
    {
        if trap_scenario == DevelopmentTrapScenario::SmpIpi {
            let mut logger = EarlyLogger::new(BootSink {
                serial: &mut serial,
                debugcon: &mut debugcon,
                ring: &EARLY_RING,
            });
            logger.write_bytes(&PKSMP3_EARLY);
        }
    }
    if trap_scenario == DevelopmentTrapScenario::SmpIpi {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKSMP5_EARLY);
    }
    if trap_scenario == DevelopmentTrapScenario::Scheduler {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKSCHED1_EARLY);
    }
    if trap_scenario == DevelopmentTrapScenario::SchedulerPreempt {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKSCHED2_EARLY);
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
        let physical_bits = pmm_try!(
            arch::x86_64::physical_address_bits()
                .ok_or(poolekernel::physical_memory::PhysicalMemoryError::AddressRange)
        );
        let mut page_access = pmm_try!(
            BootstrapTableMemory::new(observed_cr3, physical_bits)
                .map_err(|_| poolekernel::physical_memory::PhysicalMemoryError::ScrubAccess)
        );
        let proof = pmm_try!(run_physical_memory_profile(
            &decoded,
            validated.core,
            &mut page_access,
        ));
        pmm_try!(
            page_access
                .finish()
                .map_err(|_| poolekernel::physical_memory::PhysicalMemoryError::ScrubAccess)
        );
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
        let metadata = proof.metadata;
        logger.write_bytes(&PKPMM_METADATA);
        logger.write_decimal_u64(metadata.page_count);
        logger.write_bytes(&PKPMM_METADATA_PHYSICAL);
        logger.write_hex_u64(metadata.physical_start_page * poole_handoff::PAGE_BYTES);
        logger.write_bytes(&PKPMM_METADATA_VIRTUAL);
        logger.write_hex_u64(metadata.virtual_start);
        logger.write_bytes(&PKPMM_METADATA_GENERATION);
        logger.write_decimal_u64(metadata.generation);
        logger.write_bytes(&PKPMM_METADATA_OWNER);
        logger.write_decimal_u64(u64::from(metadata.owner));
        logger.write_bytes(&PKPMM_METADATA_BYTES);
        logger.write_decimal_u64(metadata.manager_byte_count);
        logger.write_bytes(&PKPMM_METADATA_SOURCE);
        logger.write_decimal_u64(metadata.source_record_count);
        logger.write_bytes(&PKPMM_METADATA_EXTENTS);
        logger.write_decimal_u64(metadata.free_extent_count);
        logger.write_bytes(&PKPMM_METADATA_ALLOCATIONS);
        logger.write_decimal_u64(metadata.allocation_record_count);
        logger.write_bytes(&PKPMM_METADATA_RECEIPTS);
        logger.write_decimal_u64(metadata.receipt_ledger_count);
        logger.write_bytes(&PKPMM_METADATA_HANDOFF_CHECKSUM);
        logger.write_hex_u64(metadata.logical_checksum);
        logger.write_bytes(&PKPMM_METADATA_FINAL_CHECKSUM);
        logger.write_hex_u64(proof.final_metadata_checksum);
        logger.write_bytes(&PKPMM_METADATA_GUARDS);
        logger.write_decimal_u64(metadata.guard_page_count);
        logger.write_bytes(&PKPMM_METADATA_MAPPINGS);
        logger.write_decimal_u64(metadata.mapping_count);
        logger.write_bytes(&PKPMM_METADATA_PTE_WRITES);
        logger.write_decimal_u64(page_access.metadata_pte_writes);
        logger.write_bytes(&PKPMM_METADATA_RELEASE_EXCLUDED);
        logger.write_decimal_u64(u64::from(metadata.release_excluded));
        logger.write_bytes(&PKPMM_METADATA_RELEASE_REJECTED);
        logger.write_decimal_u64(u64::from(proof.metadata_release_rejected));
        logger.write_bytes(&PKPMM_METADATA_INTEGRITY);
        logger.write_decimal_u64(u64::from(
            metadata.integrity_verified && proof.metadata_integrity_verified,
        ));
        logger.write_bytes(&PKPMM_METADATA_RESERVATION_ROLLBACKS);
        logger.write_decimal_u64(final_state.metadata_migration_rollbacks);
        logger.write_bytes(&PKPMM_METADATA_MAPPING_ROLLBACKS);
        logger.write_decimal_u64(page_access.metadata_mapping_rollbacks);
        logger.write_bytes(&PKPMM_METADATA_TAIL);

        let ledger_initial = proof.ledger_initial;
        let ledger_growth = proof.ledger_growth;
        logger.write_bytes(&PKPMM_GROWTH);
        logger.write_decimal_u64(ledger_initial.generation);
        logger.write_bytes(&PKPMM_GROWTH_FINAL_GENERATION);
        logger.write_decimal_u64(ledger_growth.generation);
        logger.write_bytes(&PKPMM_GROWTH_INITIAL_PAGES);
        logger.write_decimal_u64(ledger_initial.page_count);
        logger.write_bytes(&PKPMM_GROWTH_FINAL_PAGES);
        logger.write_decimal_u64(ledger_growth.page_count);
        logger.write_bytes(&PKPMM_GROWTH_FREE_CAPACITY);
        logger.write_decimal_u64(ledger_growth.free_capacity);
        logger.write_bytes(&PKPMM_GROWTH_ALLOCATION_CAPACITY);
        logger.write_decimal_u64(ledger_growth.allocation_capacity);
        logger.write_bytes(&PKPMM_GROWTH_SOURCE_CAPACITY);
        logger.write_decimal_u64(ledger_growth.source_capacity);
        logger.write_bytes(&PKPMM_GROWTH_SCRUB_CAPACITY);
        logger.write_decimal_u64(ledger_growth.scrub_capacity);
        logger.write_bytes(&PKPMM_GROWTH_RECLAIM_CAPACITY);
        logger.write_decimal_u64(ledger_growth.reclaim_capacity);
        logger.write_bytes(&PKPMM_GROWTH_RETIRED_GENERATION);
        logger.write_decimal_u64(ledger_growth.retired_generation);
        logger.write_bytes(&PKPMM_GROWTH_RETIRED_PAGES);
        logger.write_decimal_u64(ledger_growth.retired_page_count);
        logger.write_bytes(&PKPMM_GROWTH_MAPPED_PAGES);
        logger.write_decimal_u64(final_state.ledger_pages);
        logger.write_bytes(&PKPMM_GROWTH_PTE_WRITES);
        logger.write_decimal_u64(page_access.ledger_pte_writes);
        logger.write_bytes(&PKPMM_GROWTH_CHECKSUM);
        logger.write_hex_u64(ledger_growth.logical_checksum);
        logger.write_bytes(&PKPMM_GROWTH_PRESSURE_CHECKS);
        logger.write_decimal_u64(final_state.ledger_pressure_checks);
        logger.write_bytes(&PKPMM_GROWTH_PRESSURE_TRIGGERS);
        logger.write_decimal_u64(final_state.ledger_pressure_triggers);
        logger.write_bytes(&PKPMM_GROWTH_AUTOMATIC_GROWTHS);
        logger.write_decimal_u64(final_state.ledger_automatic_growths);
        logger.write_bytes(&PKPMM_GROWTH_PRESSURE_CYCLES);
        logger.write_decimal_u64(proof.pressure_cycle_count);
        logger.write_bytes(&PKPMM_GROWTH_SOFT_FALLBACKS);
        logger.write_decimal_u64(final_state.ledger_soft_window_fallbacks);
        logger.write_bytes(&PKPMM_GROWTH_HARD_REJECTIONS);
        logger.write_decimal_u64(final_state.ledger_hard_window_rejections);
        logger.write_bytes(&PKPMM_GROWTH_TAIL);

        let reclaim = proof.boot_reclaim;
        logger.write_bytes(&PKPMM_RECLAIM);
        logger.write_decimal_u64(reclaim.sequence);
        logger.write_bytes(&PKPMM_RECLAIM_SOURCE_RECORDS);
        logger.write_decimal_u64(reclaim.source_record_count);
        logger.write_bytes(&PKPMM_RECLAIM_RANGES);
        logger.write_decimal_u64(reclaim.range_count);
        logger.write_bytes(&PKPMM_RECLAIM_PAGES);
        logger.write_decimal_u64(reclaim.page_count);
        logger.write_bytes(&PKPMM_RECLAIM_DMA_PAGES);
        logger.write_decimal_u64(reclaim.pages_by_zone[Zone::Dma as usize]);
        logger.write_bytes(&PKPMM_RECLAIM_DMA32_PAGES);
        logger.write_decimal_u64(reclaim.pages_by_zone[Zone::Dma32 as usize]);
        logger.write_bytes(&PKPMM_RECLAIM_NORMAL_PAGES);
        logger.write_decimal_u64(reclaim.pages_by_zone[Zone::Normal as usize]);
        logger.write_bytes(&PKPMM_RECLAIM_PRE_EXTENTS);
        logger.write_decimal_u64(reclaim.pre_free_extent_count);
        logger.write_bytes(&PKPMM_RECLAIM_POST_EXTENTS);
        logger.write_decimal_u64(reclaim.post_free_extent_count);
        logger.write_bytes(&PKPMM_RECLAIM_SCRUB_BYTES);
        logger.write_decimal_u64(reclaim.zeroed_bytes);
        logger.write_bytes(&PKPMM_RECLAIM_VERIFIED_BYTES);
        logger.write_decimal_u64(reclaim.verified_bytes);
        logger.write_bytes(&PKPMM_RECLAIM_RANGE_CHECKSUM);
        logger.write_hex_u64(reclaim.range_checksum);
        logger.write_bytes(&PKPMM_RECLAIM_RECEIPT_CHECKSUM);
        logger.write_hex_u64(reclaim.receipt_checksum);
        logger.write_bytes(&PKPMM_RECLAIM_IDEMPOTENT);
        logger.write_decimal_u64(u64::from(proof.boot_reclaim_idempotent));
        logger.write_bytes(&PKPMM_RECLAIM_ACPI_HELD);
        logger.write_decimal_u64(
            initial.source_pages[poole_handoff::MEMORY_ACPI_RECLAIMABLE as usize],
        );
        logger.write_bytes(&PKPMM_RECLAIM_ACPI_EARLY_REJECTED);
        logger.write_decimal_u64(u64::from(proof.acpi_early_rejected));
        logger.write_bytes(&PKPMM_RECLAIM_TAIL);

        let acpi = proof.acpi_snapshot;
        logger.write_bytes(&PKPMM_ACPI_SNAPSHOT);
        logger.write_hex_u64(acpi.rsdp_source_address);
        logger.write_bytes(&PKPMM_ACPI_XSDT);
        logger.write_hex_u64(acpi.xsdt_source_address);
        logger.write_bytes(&PKPMM_ACPI_ENTRIES);
        logger.write_decimal_u64(acpi.xsdt_entry_count);
        logger.write_bytes(&PKPMM_ACPI_MASK);
        logger.write_hex_u64(u64::from(acpi.required_table_mask));
        logger.write_bytes(&PKPMM_ACPI_FACP);
        logger.write_decimal_u64(acpi.required_tables[1].byte_count);
        logger.write_bytes(&PKPMM_ACPI_APIC);
        logger.write_decimal_u64(acpi.required_tables[0].byte_count);
        logger.write_bytes(&PKPMM_ACPI_HPET);
        logger.write_decimal_u64(acpi.required_tables[2].byte_count);
        logger.write_bytes(&PKPMM_ACPI_MCFG);
        logger.write_decimal_u64(acpi.required_tables[3].byte_count);
        logger.write_bytes(&PKPMM_ACPI_DESTINATION);
        logger.write_hex_u64(acpi.snapshot_physical_address);
        logger.write_bytes(&PKPMM_ACPI_PAGES);
        logger.write_decimal_u64(acpi.snapshot_page_count);
        logger.write_bytes(&PKPMM_ACPI_BYTES);
        logger.write_decimal_u64(acpi.snapshot_byte_count);
        logger.write_bytes(&PKPMM_ACPI_COPIED);
        logger.write_decimal_u64(acpi.copied_byte_count);
        logger.write_bytes(&PKPMM_ACPI_SOURCE_CHECKSUM);
        logger.write_hex_u64(acpi.source_checksum);
        logger.write_bytes(&PKPMM_ACPI_SNAPSHOT_CHECKSUM);
        logger.write_hex_u64(acpi.snapshot_checksum);
        logger.write_bytes(&PKPMM_ACPI_TAIL);

        let acpi_reclaim = proof.acpi_reclaim;
        logger.write_bytes(&PKPMM_ACPI_RECLAIM);
        logger.write_decimal_u64(acpi_reclaim.sequence);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_SOURCE);
        logger.write_decimal_u64(acpi_reclaim.source_record_count);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_RANGES);
        logger.write_decimal_u64(acpi_reclaim.range_count);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_PAGES);
        logger.write_decimal_u64(acpi_reclaim.page_count);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_DMA);
        logger.write_decimal_u64(acpi_reclaim.pages_by_zone[Zone::Dma as usize]);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_DMA32);
        logger.write_decimal_u64(acpi_reclaim.pages_by_zone[Zone::Dma32 as usize]);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_NORMAL);
        logger.write_decimal_u64(acpi_reclaim.pages_by_zone[Zone::Normal as usize]);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_PRE);
        logger.write_decimal_u64(acpi_reclaim.pre_free_extent_count);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_POST);
        logger.write_decimal_u64(acpi_reclaim.post_free_extent_count);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_ZEROED);
        logger.write_decimal_u64(acpi_reclaim.zeroed_bytes);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_VERIFIED);
        logger.write_decimal_u64(acpi_reclaim.verified_bytes);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_RANGE_CHECKSUM);
        logger.write_hex_u64(acpi_reclaim.range_checksum);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_RECEIPT_CHECKSUM);
        logger.write_hex_u64(acpi_reclaim.receipt_checksum);
        logger.write_bytes(&PKPMM_ACPI_RECLAIM_TAIL);

        logger.write_bytes(&PKPMM_SCRUB);
        logger.write_decimal_u64(final_state.allocation_count);
        logger.write_bytes(&PKPMM_FREES);
        logger.write_decimal_u64(final_state.free_count);
        logger.write_bytes(&PKPMM_START);
        logger.write_hex_u64(proof.start_page * poole_handoff::PAGE_BYTES);
        logger.write_bytes(&PKPMM_FIRST_GENERATION);
        logger.write_decimal_u64(proof.first_generation);
        logger.write_bytes(&PKPMM_REUSE_GENERATION);
        logger.write_decimal_u64(proof.reuse_generation);
        logger.write_bytes(&PKPMM_ALLOCATION_RECEIPTS);
        logger.write_decimal_u64(
            proof
                .receipts
                .iter()
                .filter(|receipt| receipt.kind == ScrubKind::Allocation)
                .count() as u64,
        );
        logger.write_bytes(&PKPMM_RELEASE_RECEIPTS);
        logger.write_decimal_u64(
            proof
                .receipts
                .iter()
                .filter(|receipt| receipt.kind == ScrubKind::Release)
                .count() as u64,
        );
        logger.write_bytes(&PKPMM_SCRUB_PAGES);
        logger.write_decimal_u64(
            final_state.allocation_scrub_pages
                + final_state.release_scrub_pages
                + final_state.reclaim_scrub_pages,
        );
        logger.write_bytes(&PKPMM_SCRUB_BYTES);
        logger.write_decimal_u64(final_state.scrub_zeroed_bytes);
        logger.write_bytes(&PKPMM_VERIFIED_BYTES);
        logger.write_decimal_u64(final_state.scrub_verified_bytes);
        logger.write_bytes(&PKPMM_STALE_PATTERN);
        logger.write_hex_u64(proof.stale_pattern);
        logger.write_bytes(&PKPMM_STALE_ABSENT);
        logger.write_decimal_u64(u64::from(proof.stale_pattern_absent));
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
        logger.write_bytes(&PKPMM_ROLLBACK);
        logger.write_bytes(&PKPMM_RESULT);
        logger.write_decimal_u64(
            final_state.managed_pages[0]
                + final_state.managed_pages[1]
                + final_state.managed_pages[2],
        );
        logger.write_bytes(&PKPMM_ALLOCATED_PAGES);
        logger.write_decimal_u64(final_state.allocated_pages);
        logger.write_bytes(&PKPMM_PHYSICAL_WRITES);
        logger.write_decimal_u64(page_access.writes);
        logger.write_bytes(&PKPMM_PHYSICAL_READS);
        logger.write_decimal_u64(page_access.reads);
        logger.write_bytes(&PKPMM_TEMPORARY_WRITES);
        logger.write_decimal_u64(page_access.temporary_pte_writes);
        logger.write_bytes(&PKPMM_BOOTSTRAP_INVLPG);
        logger.write_decimal_u64(page_access.invalidations);
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
        logger.write_decimal_u64(summary.table_pages);
        logger.write_bytes(&PKAVM_LAYOUT_DIRECT_DIRECTORIES);
        logger.write_decimal_u64(summary.direct_directory_tables);
        logger.write_bytes(&PKAVM_LAYOUT_DIRECT_TABLES);
        logger.write_decimal_u64(summary.direct_page_tables);
        logger.write_bytes(&PKAVM_LAYOUT_MAPPED_PAGES);
        logger.write_decimal_u64(summary.direct_map_page_count);
        logger.write_bytes(&PKAVM_LINE_END);
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
        logger.write_bytes(&PKAVM_DIRECT_GENERATION);
        logger.write_decimal_u64(summary.direct_map_generation);
        logger.write_bytes(&PKAVM_DIRECT_RANGES);
        logger.write_decimal_u64(summary.direct_map_range_count);
        logger.write_bytes(&PKAVM_DIRECT_GAPS);
        logger.write_decimal_u64(summary.direct_map_gap_pages);
        logger.write_bytes(&PKAVM_DIRECT_EXCLUDED);
        logger.write_decimal_u64(summary.retained_excluded_pages);
        logger.write_bytes(&PKAVM_DIRECT_CHECKSUM);
        logger.write_hex_u64(summary.direct_map_checksum);
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

    if matches!(
        trap_scenario,
        DevelopmentTrapScenario::InterruptTime | DevelopmentTrapScenario::SchedulerPreempt
    ) {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        let scheduler_preempt = trap_scenario == DevelopmentTrapScenario::SchedulerPreempt;
        let failure_head: &[u8] = if scheduler_preempt {
            &PKSCHED2_DENIED
        } else {
            &PKIRQ_DENIED
        };
        let failure_tail: &[u8] = if scheduler_preempt {
            &PKSCHED2_DENIED_TAIL
        } else {
            &PKIRQ_DENIED_TAIL
        };
        let failure_panic = if scheduler_preempt {
            PanicCode::SchedulerPreempt
        } else {
            PanicCode::InterruptTime
        };
        macro_rules! irq_try {
            ($operation:expr) => {
                match $operation {
                    Ok(value) => value,
                    Err(error) => {
                        logger.write_bytes(failure_head);
                        logger.write_str(error.label());
                        logger.write_bytes(failure_tail);
                        poole_kernel_emergency_panic(failure_panic as u32)
                    }
                }
            };
        }
        macro_rules! irq_require {
            ($condition:expr, $error:expr) => {
                if !$condition {
                    logger.write_bytes(failure_head);
                    logger.write_str($error.label());
                    logger.write_bytes(failure_tail);
                    poole_kernel_emergency_panic(failure_panic as u32)
                }
            };
        }

        let physical_bits =
            irq_try!(arch::x86_64::physical_address_bits().ok_or(interrupt_time::Error::ApicBase));
        let mut page_access = match BootstrapTableMemory::new(observed_cr3, physical_bits) {
            Ok(value) => value,
            Err(_) => {
                logger.write_bytes(failure_head);
                logger.write_str(interrupt_time::Error::PhysicalAccess.label());
                logger.write_bytes(failure_tail);
                poole_kernel_emergency_panic(failure_panic as u32)
            }
        };
        let memory_proof =
            match run_physical_memory_profile(&decoded, validated.core, &mut page_access) {
                Ok(value) => value,
                Err(_) => {
                    logger.write_bytes(failure_head);
                    logger.write_str(interrupt_time::Error::PhysicalAccess.label());
                    logger.write_bytes(failure_tail);
                    poole_kernel_emergency_panic(failure_panic as u32)
                }
            };
        let acpi = memory_proof.acpi_snapshot;
        let madt_receipt = acpi.required_tables[0];
        let hpet_receipt = acpi.required_tables[2];
        let madt_snapshot = irq_try!(
            acpi.snapshot_physical_address
                .checked_add(madt_receipt.snapshot_offset)
                .ok_or(interrupt_time::Error::TableAddress)
        );
        let hpet_snapshot = irq_try!(
            acpi.snapshot_physical_address
                .checked_add(hpet_receipt.snapshot_offset)
                .ok_or(interrupt_time::Error::TableAddress)
        );
        let topology = irq_try!(parse_madt(
            &mut page_access,
            madt_snapshot,
            madt_receipt.byte_count,
        ));
        let hpet = irq_try!(parse_hpet(
            &mut page_access,
            hpet_snapshot,
            hpet_receipt.byte_count,
        ));
        let vectors = irq_try!(VectorLedger::new());
        irq_require!(
            vectors.owner(TIMER_VECTOR) == interrupt_time::VectorOwner::Timer
                && vectors.owner(APIC_ERROR_VECTOR) == interrupt_time::VectorOwner::ApicError
                && vectors.owner(SPURIOUS_VECTOR) == interrupt_time::VectorOwner::Spurious,
            interrupt_time::Error::VectorOwned
        );

        let cpu = arch::x86_64::observe_apic_cpu();
        irq_require!(cpu.apic_supported, interrupt_time::Error::ApicUnsupported);
        // SAFETY: CPUID reports APIC and PKIRQ1 is executing at CPL0 with IF clear.
        let original_apic_base = unsafe { arch::x86_64::read_local_apic_base() };
        irq_require!(
            original_apic_base & APIC_BASE_X2APIC == 0,
            interrupt_time::Error::X2ApicActive
        );
        let apic_physical = original_apic_base & interrupt_time::APIC_BASE_ADDRESS_MASK;
        irq_require!(
            apic_physical == topology.local_apic_address,
            interrupt_time::Error::ApicBase
        );
        let mut apic_msr_writes = 0u64;
        let enabled_apic_base = if original_apic_base & APIC_BASE_ENABLE == 0 {
            let enabled = original_apic_base | APIC_BASE_ENABLE;
            // SAFETY: this exact write changes only IA32_APIC_BASE.EN on the BSP.
            unsafe { arch::x86_64::write_local_apic_base(enabled) };
            apic_msr_writes = 1;
            // SAFETY: typed readback verifies the exact enable transition.
            irq_require!(
                unsafe { arch::x86_64::read_local_apic_base() } == enabled,
                interrupt_time::Error::ApicBase
            );
            enabled
        } else {
            original_apic_base
        };

        let hpet_page = hpet.physical_address & !0xfff;
        let (apic_virtual, hpet_page_virtual) =
            match page_access.install_uncached_mmio(apic_physical, hpet_page) {
                Ok(value) => value,
                Err(_) => {
                    logger.write_bytes(failure_head);
                    logger.write_str(interrupt_time::Error::PhysicalAccess.label());
                    logger.write_bytes(failure_tail);
                    poole_kernel_emergency_panic(failure_panic as u32)
                }
            };
        let hpet_virtual = irq_try!(
            hpet_page_virtual
                .checked_add(hpet.physical_address & 0xfff)
                .ok_or(interrupt_time::Error::TableAddress)
        );
        let mut hardware = LiveInterruptHardware {
            local_apic_virtual: apic_virtual,
            hpet_virtual,
        };

        let apic_id_register = irq_try!(hardware.apic_read(0x20));
        let apic_version_register = irq_try!(hardware.apic_read(0x30));
        let discovery = irq_try!(validate_apic_discovery(
            &topology,
            cpu,
            enabled_apic_base,
            apic_id_register,
            apic_version_register,
        ));
        irq_require!(discovery.bsp, interrupt_time::Error::ProcessorMissing);

        let original_tpr = irq_try!(hardware.apic_read(0x80));
        let original_svr = irq_try!(hardware.apic_read(0xf0));
        let original_lvt_timer = irq_try!(hardware.apic_read(0x320));
        let original_lvt_thermal = irq_try!(hardware.apic_read(0x330));
        let original_lvt_performance = irq_try!(hardware.apic_read(0x340));
        let original_lvt_lint0 = irq_try!(hardware.apic_read(0x350));
        let original_lvt_lint1 = irq_try!(hardware.apic_read(0x360));
        let original_lvt_error = irq_try!(hardware.apic_read(0x370));
        let original_divide = irq_try!(hardware.apic_read(0x3e0));
        let original_hpet_config = irq_try!(hardware.hpet_read(0x10));
        irq_require!(
            hardware.in_service_count() == Ok(0),
            interrupt_time::Error::TableShape
        );

        let pic_masks = if topology.pcat_compatible {
            // SAFETY: ACPI PCAT_COMPAT requires the dual 8259 to be masked before APIC use.
            match unsafe { arch::x86_64::mask_legacy_pic() } {
                Ok(value) => Some(value),
                Err(()) => {
                    logger.write_bytes(failure_head);
                    logger.write_str(interrupt_time::Error::PhysicalAccess.label());
                    logger.write_bytes(failure_tail);
                    poole_kernel_emergency_panic(failure_panic as u32)
                }
            }
        } else {
            None
        };

        irq_try!(hardware.apic_write(0x80, 0));
        irq_try!(hardware.apic_write(0x320, u32::from(TIMER_VECTOR) | (1 << 16)));
        irq_try!(hardware.apic_write(0x330, original_lvt_thermal | (1 << 16)));
        irq_try!(hardware.apic_write(0x340, original_lvt_performance | (1 << 16)));
        irq_try!(hardware.apic_write(0x350, original_lvt_lint0 | (1 << 16)));
        irq_try!(hardware.apic_write(0x360, original_lvt_lint1 | (1 << 16)));
        irq_try!(hardware.apic_write(0x370, u32::from(APIC_ERROR_VECTOR) | (1 << 16)));
        irq_try!(hardware.apic_write(0x280, 0));
        let _cleared_esr = irq_try!(hardware.apic_read(0x280));
        irq_try!(hardware.apic_write(
            0xf0,
            (original_svr & !0xff) | u32::from(SPURIOUS_VECTOR) | (1 << 8),
        ));
        irq_try!(hardware.apic_write(0x3e0, 0x3));

        let hpet_capabilities = irq_try!(hardware.hpet_read(0));
        let hpet_period = hpet_capabilities >> 32;
        irq_require!(
            (100_000..=100_000_000).contains(&hpet_period),
            interrupt_time::Error::HpetPeriod
        );
        let counter_bits = if hpet_capabilities & (1 << 13) != 0 {
            64
        } else {
            32
        };
        irq_require!(
            hpet.counter_64_bit_capable == (counter_bits == 64),
            interrupt_time::Error::CounterWidth
        );
        if original_hpet_config & 1 == 0 {
            irq_try!(hardware.hpet_write(0x10, original_hpet_config | 1));
            irq_require!(
                irq_try!(hardware.hpet_read(0x10)) & 1 != 0,
                interrupt_time::Error::HpetRegisterShape
            );
        }
        let counter_mask = if counter_bits == 64 {
            u64::MAX
        } else {
            u64::from(u32::MAX)
        };
        let calibration_start = irq_try!(hardware.hpet_read(0xf0)) & counter_mask;
        irq_try!(hardware.apic_write(0x380, u32::MAX));
        let target_hpet_ticks = 10_000_000_000_000u64.div_ceil(hpet_period);
        let mut calibration_end = calibration_start;
        let mut poll_count = 0u64;
        while calibration_end.wrapping_sub(calibration_start) & counter_mask < target_hpet_ticks {
            calibration_end = irq_try!(hardware.hpet_read(0xf0)) & counter_mask;
            poll_count = irq_try!(
                poll_count
                    .checked_add(1)
                    .ok_or(interrupt_time::Error::CalibrationSample)
            );
            irq_require!(
                poll_count <= 100_000_000,
                interrupt_time::Error::CalibrationSample
            );
            core::hint::spin_loop();
        }
        let calibration_current = irq_try!(hardware.apic_read(0x390));
        irq_try!(hardware.apic_write(0x320, u32::from(TIMER_VECTOR) | (1 << 16)));
        let elapsed_hpet_ticks = calibration_end.wrapping_sub(calibration_start) & counter_mask;
        let calibration = irq_try!(calibrate_apic_timer(
            u32::MAX,
            calibration_current,
            elapsed_hpet_ticks,
            hpet_period,
        ));
        let one_shot_count = irq_try!(timer_initial_count(
            calibration.apic_ticks_per_second,
            10_000_000,
        ));

        let descriptor_state = unsafe {
            // SAFETY: PKIRQ1 owns the one-BSP descriptor installation while IF is clear.
            arch::x86_64::install_interrupt_descriptor_tables(stack_top as u64)
        };
        irq_require!(
            validate_interrupt_descriptor_state(&descriptor_state).is_ok(),
            interrupt_time::Error::TableShape
        );
        IST1_BOTTOM.store(descriptor_state.ist1_bottom, Ordering::Release);
        IST1_TOP.store(descriptor_state.ist1_top, Ordering::Release);
        IST2_BOTTOM.store(descriptor_state.ist2_bottom, Ordering::Release);
        IST2_TOP.store(descriptor_state.ist2_top, Ordering::Release);
        IRQ_TIMER_DELIVERIES.store(0, Ordering::Release);
        IRQ_EOI_COUNT.store(0, Ordering::Release);
        IRQ_ERROR_COUNT.store(0, Ordering::Release);
        IRQ_SPURIOUS_COUNT.store(0, Ordering::Release);
        IRQ_APIC_VIRTUAL.store(apic_virtual, Ordering::Release);

        irq_try!(hardware.apic_write(0x370, u32::from(APIC_ERROR_VECTOR)));
        let monotonic_start = irq_try!(hardware.hpet_read(0xf0)) & counter_mask;
        let max_sample_delta = core::cmp::min(
            counter_mask / 2,
            5_000_000_000_000_000u64.div_ceil(hpet_period),
        );
        let mut clock = irq_try!(HpetClock::new(
            counter_bits,
            hpet_period,
            monotonic_start,
            max_sample_delta,
        ));
        let preempt_evidence = if scheduler_preempt {
            macro_rules! sched_try {
                ($operation:expr, $reason:literal) => {
                    match $operation {
                        Ok(value) => value,
                        Err(_) => {
                            logger.write_bytes(&PKSCHED2_DENIED);
                            logger.write_str($reason);
                            logger.write_bytes(&PKSCHED2_DENIED_TAIL);
                            poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
                        }
                    }
                };
            }
            macro_rules! sched_require {
                ($condition:expr, $reason:literal) => {
                    if !$condition {
                        logger.write_bytes(&PKSCHED2_DENIED);
                        logger.write_str($reason);
                        logger.write_bytes(&PKSCHED2_DENIED_TAIL);
                        poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
                    }
                };
            }

            let scheduler_cpu = sched_try!(SchedulerCpuId::new(0), "cpu");
            let mut scheduler = sched_try!(Scheduler::new(1), "scheduler_init");
            let task_a = sched_try!(scheduler.create_task(0, 1, 10, 1), "task_a");
            let task_b = sched_try!(scheduler.create_task(1, 1, 10, 1), "task_b");
            let signal_task = sched_try!(scheduler.create_task(2, 1, 30, 1), "signal_task");
            let cancel_task = sched_try!(scheduler.create_task(3, 1, 25, 1), "cancel_task");
            sched_try!(
                scheduler.activate(signal_task, scheduler_cpu),
                "signal_activate"
            );
            sched_require!(
                sched_try!(scheduler.dispatch(scheduler_cpu), "signal_dispatch") == signal_task,
                "signal_dispatch_identity"
            );
            sched_try!(scheduler.block_current(scheduler_cpu), "signal_block");
            sched_try!(
                scheduler.activate(cancel_task, scheduler_cpu),
                "cancel_activate"
            );
            sched_require!(
                sched_try!(scheduler.dispatch(scheduler_cpu), "cancel_dispatch") == cancel_task,
                "cancel_dispatch_identity"
            );
            sched_try!(scheduler.block_current(scheduler_cpu), "cancel_block");
            sched_try!(scheduler.activate(task_a, scheduler_cpu), "task_a_activate");
            sched_try!(scheduler.activate(task_b, scheduler_cpu), "task_b_activate");
            sched_require!(
                sched_try!(scheduler.dispatch(scheduler_cpu), "task_a_dispatch") == task_a,
                "task_a_dispatch_identity"
            );
            let mut controller = sched_try!(
                BspPreemption::new(scheduler, scheduler_cpu, 2),
                "controller_init"
            );
            sched_try!(
                controller.queue_event(DeferredEvent {
                    due_tick: 3,
                    kind: DeferredEventKind::Signal(signal_task),
                }),
                "signal_event"
            );
            sched_try!(
                controller.queue_event(DeferredEvent {
                    due_tick: 4,
                    kind: DeferredEventKind::BlockCurrent,
                }),
                "block_event"
            );
            sched_try!(
                controller.queue_event(DeferredEvent {
                    due_tick: 5,
                    kind: DeferredEventKind::Cancel(cancel_task),
                }),
                "cancel_event"
            );
            let contexts = sched_try!(
                arch::x86_64::prepare_scheduler_preemption_contexts(stack_top as u64),
                "context_prepare"
            );
            // SAFETY: selector 16 has exclusive BSP ownership before timer delivery starts.
            sched_require!(
                unsafe { SCHEDULER_PREEMPT_RUNTIME.install(controller) }.is_ok(),
                "controller_install"
            );
            // SAFETY: every prepared frame is stack- and entry-bound by the arch helper.
            unsafe { SCHEDULER_PREEMPT_CONTEXTS.install(contexts) };
            SCHEDULER_PREEMPT_TIMER_COUNT.store(one_shot_count, Ordering::Release);
            SCHEDULER_PREEMPT_FRAME_SWITCHES.store(0, Ordering::Release);
            poole_scheduler_preempt_done.store(0, Ordering::Release);

            logger.write_bytes(&PKSCHED2_ARM);
            logger.write_decimal_u64(u64::from(one_shot_count));
            logger.write_bytes(&PKSCHED2_FREQUENCY);
            logger.write_decimal_u64(calibration.apic_ticks_per_second);
            logger.write_bytes(&PKSCHED2_ARM_TAIL);

            irq_try!(hardware.apic_write(0x320, u32::from(TIMER_VECTOR)));
            irq_try!(hardware.apic_write(0x380, one_shot_count));
            let hardware_proof = match arch::x86_64::run_scheduler_preemption_launcher() {
                Ok(value) => value,
                Err(error) => {
                    logger.write_bytes(&PKSCHED2_DENIED);
                    logger.write_str(error.label());
                    logger.write_bytes(&PKSCHED2_DENIED_TAIL);
                    poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
                }
            };
            irq_try!(hardware.apic_write(0x320, u32::from(TIMER_VECTOR) | (1 << 16)));
            sched_require!(
                poole_scheduler_preempt_done.load(Ordering::Acquire) == 1,
                "terminal_tick"
            );
            // SAFETY: the launcher returned with IF clear and the timer is masked.
            let mut controller = unsafe { SCHEDULER_PREEMPT_RUNTIME.take() }.unwrap_or_else(|| {
                poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
            });
            let summary = controller.summary();
            sched_require!(
                summary.timer_ticks == 6
                    && summary.events_processed == 3
                    && summary.signal_events == 1
                    && summary.cancel_events == 1
                    && summary.timeout_events == 0
                    && summary.block_events == 1
                    && summary.quantum_reschedules == 1
                    && summary.wake_reschedules == 2
                    && summary.block_reschedules == 1
                    && summary.context_switches == 4
                    && summary.rollback_count == 0
                    && summary.pending_events == 0
                    && summary.scheduler.dispatch_count == 7
                    && summary.scheduler.runnable_count == 2
                    && summary.scheduler.running_count == 1
                    && summary.scheduler.blocked_count == 1,
                "summary"
            );
            let expected_runtime = [3, 1, 1, 1];
            for (task, ticks) in [task_a, task_b, signal_task, cancel_task]
                .into_iter()
                .zip(expected_runtime)
            {
                sched_require!(
                    sched_try!(controller.scheduler().task_snapshot(task), "task_snapshot")
                        .runtime_ticks
                        == ticks,
                    "runtime_accounting"
                );
            }
            for task in [task_a, task_b, signal_task, cancel_task] {
                sched_try!(controller.scheduler_mut().teardown(task), "task_teardown");
            }
            let cleanup = controller.scheduler().summary();
            sched_require!(
                cleanup.dead_count == 4
                    && cleanup.runnable_count == 0
                    && cleanup.running_count == 0
                    && cleanup.blocked_count == 0
                    && cleanup.teardown_count == 4,
                "scheduler_cleanup"
            );
            // SAFETY: all scheduler task ownership is retired before dropping saved frames.
            let contexts_cleared = unsafe { SCHEDULER_PREEMPT_CONTEXTS.clear() };
            sched_require!(contexts_cleared == 4, "context_cleanup");
            let hardware_proof = sched_try!(
                arch::x86_64::clear_scheduler_preemption_stacks(hardware_proof),
                "stack_cleanup"
            );
            sched_require!(
                SCHEDULER_SWITCH_LOCK.owner() == 0
                    && hardware_proof.task_entry_count == [1, 1, 1, 1]
                    && hardware_proof.launcher_transition_count == 2
                    && hardware_proof.stack_bytes_cleared == 65_536,
                "hardware_cleanup"
            );
            SCHEDULER_PREEMPT_TIMER_COUNT.store(0, Ordering::Release);
            poole_scheduler_preempt_done.store(0, Ordering::Release);
            Some((summary, cleanup, hardware_proof, contexts_cleared))
        } else {
            for expected in 1..=8u32 {
                irq_try!(hardware.apic_write(0x320, u32::from(TIMER_VECTOR)));
                irq_try!(hardware.apic_write(0x380, one_shot_count));
                // SAFETY: IDT, UC APIC mapping, vector ownership, and one-shot timer are live.
                unsafe { arch::x86_64::enable_interrupts_halt_disable() };
                irq_try!(hardware.apic_write(0x320, u32::from(TIMER_VECTOR) | (1 << 16)));
                irq_require!(
                    IRQ_TIMER_DELIVERIES.load(Ordering::Acquire) == expected,
                    interrupt_time::Error::TimerCount
                );
            }
            None
        };
        let monotonic_end = irq_try!(hardware.hpet_read(0xf0)) & counter_mask;
        let monotonic_nanoseconds = irq_try!(clock.sample(monotonic_end));
        let timer_deliveries = IRQ_TIMER_DELIVERIES.load(Ordering::Acquire);
        let eoi_count = IRQ_EOI_COUNT.load(Ordering::Acquire);
        let error_count = IRQ_ERROR_COUNT.load(Ordering::Acquire);
        let spurious_count = IRQ_SPURIOUS_COUNT.load(Ordering::Acquire);
        let in_service_after = irq_try!(hardware.in_service_count());
        irq_require!(
            timer_deliveries == if scheduler_preempt { 6 } else { 8 }
                && eoi_count == timer_deliveries
                && error_count == 0
                && spurious_count == 0
                && in_service_after == 0
                && TRAP_DEPTH.load(Ordering::Acquire) == 0,
            interrupt_time::Error::TimerCount
        );

        irq_try!(hardware.apic_write(0x320, original_lvt_timer));
        irq_try!(hardware.apic_write(0x370, original_lvt_error));
        irq_try!(hardware.apic_write(0x330, original_lvt_thermal));
        irq_try!(hardware.apic_write(0x340, original_lvt_performance));
        irq_try!(hardware.apic_write(0x350, original_lvt_lint0));
        irq_try!(hardware.apic_write(0x360, original_lvt_lint1));
        irq_try!(hardware.apic_write(0x3e0, original_divide));
        irq_try!(hardware.apic_write(0x80, original_tpr));
        irq_try!(hardware.apic_write(0xf0, original_svr));
        if irq_try!(hardware.hpet_read(0x10)) != original_hpet_config {
            irq_try!(hardware.hpet_write(0x10, original_hpet_config));
        }
        IRQ_APIC_VIRTUAL.store(0, Ordering::Release);
        if let Some(masks) = pic_masks {
            // SAFETY: IF remains clear and PKIRQ1 restores the exact observed masks.
            if unsafe { arch::x86_64::restore_legacy_pic(masks) }.is_err() {
                logger.write_bytes(failure_head);
                logger.write_str(interrupt_time::Error::PhysicalAccess.label());
                logger.write_bytes(failure_tail);
                poole_kernel_emergency_panic(failure_panic as u32)
            }
        }
        if apic_msr_writes != 0 {
            // SAFETY: all APIC interrupt sources are masked and IF is clear before rollback.
            unsafe { arch::x86_64::write_local_apic_base(original_apic_base) };
            // SAFETY: typed readback verifies exact IA32_APIC_BASE restoration.
            irq_require!(
                unsafe { arch::x86_64::read_local_apic_base() } == original_apic_base,
                interrupt_time::Error::ApicBase
            );
            apic_msr_writes += 1;
        }
        if page_access.uninstall_uncached_mmio().is_err()
            || TableMemory::finish(&mut page_access).is_err()
        {
            logger.write_bytes(failure_head);
            logger.write_str(interrupt_time::Error::PhysicalAccess.label());
            logger.write_bytes(failure_tail);
            poole_kernel_emergency_panic(failure_panic as u32)
        }

        if let Some((summary, cleanup, hardware_proof, contexts_cleared)) = preempt_evidence {
            if timer_deliveries != 6
                || eoi_count != 6
                || error_count != 0
                || spurious_count != 0
                || in_service_after != 0
                || SCHEDULER_PREEMPT_FRAME_SWITCHES.load(Ordering::Acquire) != 4
                || summary.timer_ticks != 6
                || cleanup.dead_count != 4
                || hardware_proof.task_entry_count != [1, 1, 1, 1]
                || !hardware_proof.same_cr3
                || !hardware_proof.fs_gs_unchanged
                || !hardware_proof.returned_with_interrupts_disabled
                || contexts_cleared != 4
            {
                logger.write_bytes(&PKSCHED2_DENIED);
                logger.write_str("final_evidence");
                logger.write_bytes(&PKSCHED2_DENIED_TAIL);
                poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
            }
            logger.write_bytes(&PKSCHED2_TRACE);
            logger.write_bytes(&PKSCHED2_FRAME);
            logger.write_bytes(&PKSCHED2_CLEANUP);
            logger.write_bytes(&PKSCHED2_RESULT);
            halt_forever()
        }

        logger.write_bytes(&PKIRQ_ACPI);
        logger.write_decimal_u64(madt_receipt.byte_count);
        logger.write_bytes(&PKIRQ_PROCESSORS);
        logger.write_decimal_u64(topology.processor_count as u64);
        logger.write_bytes(&PKIRQ_ENABLED);
        logger.write_decimal_u64(topology.enabled_processor_count as u64);
        logger.write_bytes(&PKIRQ_IOAPICS);
        logger.write_decimal_u64(topology.io_apic_count as u64);
        logger.write_bytes(&PKIRQ_OVERRIDES);
        logger.write_decimal_u64(topology.override_count as u64);
        logger.write_bytes(&PKIRQ_NMI_SOURCES);
        logger.write_decimal_u64(topology.nmi_source_count as u64);
        logger.write_bytes(&PKIRQ_LOCAL_NMIS);
        logger.write_decimal_u64(topology.local_nmi_count as u64);
        logger.write_bytes(&PKIRQ_UNKNOWN);
        logger.write_decimal_u64(topology.unknown_structure_count as u64);
        logger.write_bytes(&PKIRQ_PCAT);
        logger.write_decimal_u64(u64::from(topology.pcat_compatible));
        logger.write_bytes(&PKIRQ_APIC_PHYSICAL);
        logger.write_hex_u64(apic_physical);
        logger.write_bytes(&PKIRQ_HPET_PHYSICAL);
        logger.write_hex_u64(hpet.physical_address);
        logger.write_bytes(&PKIRQ_ACPI_TAIL);
        logger.write_bytes(&PKIRQ_APIC);
        logger.write_decimal_u64(u64::from(discovery.apic_id));
        logger.write_bytes(&PKIRQ_VERSION);
        logger.write_decimal_u64(u64::from(discovery.version));
        logger.write_bytes(&PKIRQ_MAX_LVT);
        logger.write_decimal_u64(u64::from(discovery.max_lvt_entry));
        logger.write_bytes(&PKIRQ_GLOBAL);
        logger.write_decimal_u64(u64::from(discovery.globally_enabled));
        logger.write_bytes(&PKIRQ_MSR_WRITES);
        logger.write_decimal_u64(apic_msr_writes);
        logger.write_bytes(&PKIRQ_SVR);
        logger.write_decimal_u64(u64::from(topology.pcat_compatible));
        logger.write_bytes(&PKIRQ_MMIO);
        logger.write_bytes(&PKIRQ_VECTOR);
        logger.write_decimal_u64(u64::from(vectors.owned_count()));
        logger.write_bytes(&PKIRQ_TIMER_VECTOR);
        logger.write_bytes(&PKIRQ_CLOCK);
        logger.write_decimal_u64(u64::from(counter_bits));
        logger.write_bytes(&PKIRQ_PERIOD);
        logger.write_decimal_u64(hpet_period);
        logger.write_bytes(&PKIRQ_HPET_TICKS);
        logger.write_decimal_u64(calibration.hpet_ticks);
        logger.write_bytes(&PKIRQ_SAMPLE_NS);
        logger.write_decimal_u64(calibration.sample_nanoseconds);
        logger.write_bytes(&PKIRQ_APIC_TICKS);
        logger.write_decimal_u64(calibration.elapsed_apic_ticks);
        logger.write_bytes(&PKIRQ_FREQUENCY);
        logger.write_decimal_u64(calibration.apic_ticks_per_second);
        logger.write_bytes(&PKIRQ_INITIAL);
        logger.write_decimal_u64(u64::from(one_shot_count));
        logger.write_bytes(&PKIRQ_MONOTONIC_NS);
        logger.write_decimal_u64(monotonic_nanoseconds);
        logger.write_bytes(&PKIRQ_CLOCK_TAIL);
        logger.write_bytes(&PKIRQ_DELIVERY);
        logger.write_decimal_u64(u64::from(timer_deliveries));
        logger.write_bytes(&PKIRQ_EOIS);
        logger.write_decimal_u64(u64::from(eoi_count));
        logger.write_bytes(&PKIRQ_ERRORS);
        logger.write_decimal_u64(u64::from(error_count));
        logger.write_bytes(&PKIRQ_SPURIOUS);
        logger.write_decimal_u64(u64::from(spurious_count));
        logger.write_bytes(&PKIRQ_ISR);
        logger.write_decimal_u64(u64::from(in_service_after));
        logger.write_bytes(&PKIRQ_DELIVERY_TAIL);
        logger.write_bytes(&PKIRQ_RESULT);
        logger.write_decimal_u64(u64::from(timer_deliveries));
        logger.write_bytes(&PKIRQ_RESULT_TAIL);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::SmpFirstAp {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        let proof = match run_smp_first_ap(&decoded, validated.core, observed_cr3) {
            Ok(value) => value,
            Err(error) => {
                logger.write_bytes(&PKSMP_DENIED);
                logger.write_str(error.label());
                logger.write_bytes(&PKSMP_DENIED_TAIL);
                poole_kernel_emergency_panic(PanicCode::SmpFirstAp as u32)
            }
        };
        let mailbox = proof.operation.mailbox;
        logger.write_bytes(&PKSMP_TOPOLOGY);
        logger.write_decimal_u64(proof.madt_bytes);
        logger.write_bytes(&PKSMP_PROCESSORS);
        logger.write_decimal_u64(proof.processor_count);
        logger.write_bytes(&PKSMP_ENABLED);
        logger.write_decimal_u64(proof.enabled_processor_count);
        logger.write_bytes(&PKSMP_BSP_APIC);
        logger.write_decimal_u64(u64::from(proof.bsp_apic_id));
        logger.write_bytes(&PKSMP_TARGET_APIC);
        logger.write_decimal_u64(u64::from(proof.target_apic_id));
        logger.write_bytes(&PKSMP_APIC_PHYSICAL);
        logger.write_hex_u64(proof.apic_physical);
        logger.write_bytes(&PKSMP_HPET_PHYSICAL);
        logger.write_hex_u64(proof.hpet_physical);
        logger.write_bytes(&PKSMP_TOPOLOGY_TAIL);

        logger.write_bytes(&PKSMP_RESOURCES);
        logger.write_hex_u64(proof.layout.trampoline());
        logger.write_bytes(&PKSMP_RESOURCE_PAGES);
        logger.write_decimal_u64(proof.layout.page_count);
        logger.write_bytes(&PKSMP_VECTOR);
        logger.write_decimal_u64(u64::from(proof.layout.sipi_vector()));
        logger.write_bytes(&PKSMP_TRAMPOLINE_BYTES);
        logger.write_decimal_u64(proof.trampoline_bytes);
        logger.write_bytes(&PKSMP_ALLOCATION_SEQUENCE);
        logger.write_decimal_u64(proof.allocation_receipt.sequence);
        logger.write_bytes(&PKSMP_RESOURCES_TAIL);

        logger.write_bytes(&PKSMP_TABLES);
        logger.write_hex_u64(proof.layout.pml4());
        logger.write_bytes(&PKSMP_PDPT);
        logger.write_hex_u64(proof.layout.pdpt());
        logger.write_bytes(&PKSMP_PD);
        logger.write_hex_u64(proof.layout.page_directory());
        logger.write_bytes(&PKSMP_PT);
        logger.write_hex_u64(proof.layout.page_table());
        logger.write_bytes(&PKSMP_TABLES_TAIL);

        logger.write_bytes(&PKSMP_START);
        logger.write_decimal_u64(proof.operation.init_asserts);
        logger.write_bytes(&PKSMP_INIT_DEASSERTS);
        logger.write_decimal_u64(proof.operation.init_deasserts);
        logger.write_bytes(&PKSMP_SIPIS);
        logger.write_decimal_u64(proof.operation.sipis);
        logger.write_bytes(&PKSMP_START_TAIL);

        logger.write_bytes(&PKSMP_ONLINE);
        logger.write_decimal_u64(u64::from(smp::MAILBOX_STATE_ONLINE));
        logger.write_bytes(&PKSMP_OBSERVED_APIC);
        logger.write_decimal_u64(u64::from(mailbox.observed_apic_id));
        logger.write_bytes(&PKSMP_LEAF1_ECX);
        logger.write_hex_u64(u64::from(mailbox.leaf1_ecx));
        logger.write_bytes(&PKSMP_LEAF1_EDX);
        logger.write_hex_u64(u64::from(mailbox.leaf1_edx));
        logger.write_bytes(&PKSMP_CR0);
        logger.write_hex_u64(mailbox.cr0);
        logger.write_bytes(&PKSMP_CR3);
        logger.write_hex_u64(mailbox.cr3);
        logger.write_bytes(&PKSMP_CR4);
        logger.write_hex_u64(mailbox.cr4);
        logger.write_bytes(&PKSMP_EFER);
        logger.write_hex_u64(mailbox.efer);
        logger.write_bytes(&PKSMP_ONLINE_TAIL);

        logger.write_bytes(&PKSMP_STOP);
        logger.write_decimal_u64(u64::from(mailbox.command));
        logger.write_bytes(&PKSMP_STOP_STATE);
        logger.write_decimal_u64(u64::from(mailbox.state));
        logger.write_bytes(&PKSMP_TSC_ONLINE);
        logger.write_hex_u64(mailbox.tsc_online);
        logger.write_bytes(&PKSMP_TSC_STOP);
        logger.write_hex_u64(mailbox.tsc_stop);
        logger.write_bytes(&PKSMP_CHECKSUM);
        logger.write_hex_u64(mailbox.checksum);
        logger.write_bytes(&PKSMP_STOP_TAIL);

        logger.write_bytes(&PKSMP_RELEASE);
        logger.write_decimal_u64(proof.release_receipt.sequence);
        logger.write_bytes(&PKSMP_ZEROED_BYTES);
        logger.write_decimal_u64(proof.release_receipt.zeroed_bytes);
        logger.write_bytes(&PKSMP_VERIFIED_BYTES);
        logger.write_decimal_u64(proof.release_receipt.verified_bytes);
        logger.write_bytes(&PKSMP_RELEASE_TAIL);
        logger.write_bytes(&PKSMP_RESULT);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::SmpPerCpuRuntime {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        let proof = match run_smp_percpu_runtime(&decoded, validated.core, observed_cr3) {
            Ok(value) => value,
            Err(error) => {
                logger.write_bytes(&PKSMP2_DENIED);
                logger.write_str(error.label());
                logger.write_bytes(&PKSMP2_DENIED_TAIL);
                poole_kernel_emergency_panic(PanicCode::SmpPerCpuRuntime as u32)
            }
        };
        let mailbox = proof.operation.mailbox;
        logger.write_bytes(&PKSMP2_TOPOLOGY);
        logger.write_decimal_u64(proof.madt_bytes);
        logger.write_bytes(&PKSMP2_PROCESSORS);
        logger.write_decimal_u64(proof.processor_count);
        logger.write_bytes(&PKSMP2_ENABLED);
        logger.write_decimal_u64(proof.enabled_processor_count);
        logger.write_bytes(&PKSMP2_BSP_APIC);
        logger.write_decimal_u64(u64::from(proof.bsp_apic_id));
        logger.write_bytes(&PKSMP2_TARGET_APIC);
        logger.write_decimal_u64(u64::from(proof.target_apic_id));
        logger.write_bytes(&PKSMP2_APIC_PHYSICAL);
        logger.write_hex_u64(proof.apic_physical);
        logger.write_bytes(&PKSMP2_HPET_PHYSICAL);
        logger.write_hex_u64(proof.hpet_physical);
        logger.write_bytes(&PKSMP2_TOPOLOGY_TAIL);

        logger.write_bytes(&PKSMP2_RESOURCES);
        logger.write_hex_u64(proof.layout.trampoline());
        logger.write_bytes(&PKSMP2_RESOURCE_PAGES);
        logger.write_decimal_u64(proof.layout.page_count);
        logger.write_bytes(&PKSMP2_VECTOR);
        logger.write_decimal_u64(u64::from(proof.layout.sipi_vector()));
        logger.write_bytes(&PKSMP2_TRAMPOLINE_BYTES);
        logger.write_decimal_u64(proof.trampoline_bytes);
        logger.write_bytes(&PKSMP2_ALLOCATION_SEQUENCE);
        logger.write_decimal_u64(proof.allocation_receipt.sequence);
        logger.write_bytes(&PKSMP2_RESOURCES_TAIL);

        logger.write_bytes(&PKSMP2_TABLES);
        logger.write_hex_u64(proof.layout.pml4());
        logger.write_bytes(&PKSMP2_PDPT);
        logger.write_hex_u64(proof.layout.pdpt());
        logger.write_bytes(&PKSMP2_PD);
        logger.write_hex_u64(proof.layout.page_directory());
        logger.write_bytes(&PKSMP2_PT);
        logger.write_hex_u64(proof.layout.page_table());
        logger.write_bytes(&PKSMP2_TABLES_TAIL);

        logger.write_bytes(&PKSMP2_START);
        logger.write_decimal_u64(proof.operation.init_asserts);
        logger.write_bytes(&PKSMP2_INIT_DEASSERTS);
        logger.write_decimal_u64(proof.operation.init_deasserts);
        logger.write_bytes(&PKSMP2_SIPIS);
        logger.write_decimal_u64(proof.operation.sipis);
        logger.write_bytes(&PKSMP2_START_TAIL);

        logger.write_bytes(&PKSMP2_DESCRIPTORS);
        logger.write_hex_u64(mailbox.observed_gdt_base);
        logger.write_bytes(&PKSMP2_GDT_LIMIT);
        logger.write_decimal_u64(u64::from(mailbox.observed_gdt_limit));
        logger.write_bytes(&PKSMP2_TSS);
        logger.write_hex_u64(mailbox.expected_tss_base);
        logger.write_bytes(&PKSMP2_TR);
        logger.write_hex_u64(u64::from(mailbox.task_selector));
        logger.write_bytes(&PKSMP2_CODE_SELECTOR);
        logger.write_hex_u64(u64::from(mailbox.code_selector));
        logger.write_bytes(&PKSMP2_DATA_SELECTOR);
        logger.write_hex_u64(u64::from(mailbox.data_selector));
        logger.write_bytes(&PKSMP2_IDT);
        logger.write_hex_u64(mailbox.observed_idt_base);
        logger.write_bytes(&PKSMP2_IDT_LIMIT);
        logger.write_decimal_u64(u64::from(mailbox.observed_idt_limit));
        logger.write_bytes(&PKSMP2_GATES);
        logger.write_decimal_u64(u64::from(mailbox.installed_gate_count));
        logger.write_bytes(&PKSMP2_TSS_BUSY);
        logger.write_decimal_u64(proof.operation.tss_busy_verified as u64);
        logger.write_bytes(&PKSMP2_IDT_VERIFIED);
        logger.write_decimal_u64(proof.operation.idt_verified as u64);
        logger.write_bytes(&PKSMP2_DESCRIPTORS_TAIL);

        logger.write_bytes(&PKSMP2_STACKS);
        logger.write_hex_u64(proof.layout.rsp0_bottom());
        logger.write_bytes(&PKSMP2_RSP0_TOP);
        logger.write_hex_u64(mailbox.rsp0);
        logger.write_bytes(&PKSMP2_OBSERVED_RSP);
        logger.write_hex_u64(mailbox.observed_rsp);
        logger.write_bytes(&PKSMP2_IST1_BOTTOM);
        logger.write_hex_u64(mailbox.ist1_bottom);
        logger.write_bytes(&PKSMP2_IST1_TOP);
        logger.write_hex_u64(mailbox.ist1_top);
        logger.write_bytes(&PKSMP2_IST2_BOTTOM);
        logger.write_hex_u64(mailbox.ist2_bottom);
        logger.write_bytes(&PKSMP2_IST2_TOP);
        logger.write_hex_u64(mailbox.ist2_top);
        logger.write_bytes(&PKSMP2_STACKS_TAIL);

        logger.write_bytes(&PKSMP2_XSTATE);
        logger.write_hex_u64(mailbox.xstate_base);
        logger.write_bytes(&PKSMP2_XSTATE_BYTES);
        logger.write_decimal_u64(u64::from(mailbox.xstate_bytes));
        logger.write_bytes(&PKSMP2_SUPPORTED_XCR0);
        logger.write_hex_u64(mailbox.supported_xcr0);
        logger.write_bytes(&PKSMP2_ENABLED_BYTES);
        logger.write_decimal_u64(u64::from(mailbox.enabled_area_bytes));
        logger.write_bytes(&PKSMP2_MAXIMUM_BYTES);
        logger.write_decimal_u64(u64::from(mailbox.maximum_area_bytes));
        logger.write_bytes(&PKSMP2_XCR0);
        logger.write_hex_u64(mailbox.xcr0);
        logger.write_bytes(&PKSMP2_XSTATE_BV);
        logger.write_hex_u64(mailbox.xstate_bv);
        logger.write_bytes(&PKSMP2_FCW);
        logger.write_hex_u64(u64::from(mailbox.initial_fcw));
        logger.write_bytes(&PKSMP2_MXCSR);
        logger.write_hex_u64(u64::from(mailbox.initial_mxcsr));
        logger.write_bytes(&PKSMP2_OWNER_INITIAL);
        logger.write_hex_u64(u64::from(mailbox.xstate_owner_initial));
        logger.write_bytes(&PKSMP2_OWNER_FINAL);
        logger.write_hex_u64(u64::from(mailbox.xstate_owner_final));
        logger.write_bytes(&PKSMP2_SAVES);
        logger.write_decimal_u64(u64::from(mailbox.xstate_save_count));
        logger.write_bytes(&PKSMP2_RESTORES);
        logger.write_decimal_u64(u64::from(mailbox.xstate_restore_count));
        logger.write_bytes(&PKSMP2_XSTATE_VERIFIED);
        logger.write_decimal_u64(proof.operation.xstate_verified as u64);
        logger.write_bytes(&PKSMP2_XSTATE_TAIL);

        logger.write_bytes(&PKSMP2_VECTORS);
        logger.write_bytes(&PKSMP2_ONLINE);
        logger.write_decimal_u64(u64::from(smp_runtime::MAILBOX_STATE_ONLINE));
        logger.write_bytes(&PKSMP2_RUNTIME_STATE);
        logger.write_decimal_u64(u64::from(smp_runtime::RUNTIME_STATE_ONLINE));
        logger.write_bytes(&PKSMP2_OBSERVED_APIC);
        logger.write_decimal_u64(u64::from(mailbox.observed_apic_id));
        logger.write_bytes(&PKSMP2_LEAF1_ECX);
        logger.write_hex_u64(u64::from(mailbox.leaf1_ecx));
        logger.write_bytes(&PKSMP2_LEAF1_EDX);
        logger.write_hex_u64(u64::from(mailbox.leaf1_edx));
        logger.write_bytes(&PKSMP2_CR0);
        logger.write_hex_u64(mailbox.cr0);
        logger.write_bytes(&PKSMP2_CR3);
        logger.write_hex_u64(mailbox.cr3);
        logger.write_bytes(&PKSMP2_CR4);
        logger.write_hex_u64(mailbox.cr4);
        logger.write_bytes(&PKSMP2_EFER);
        logger.write_hex_u64(mailbox.efer);
        logger.write_bytes(&PKSMP2_RFLAGS);
        logger.write_hex_u64(mailbox.rflags);
        logger.write_bytes(&PKSMP2_ONLINE_TAIL);

        logger.write_bytes(&PKSMP2_STOP);
        logger.write_decimal_u64(u64::from(mailbox.command));
        logger.write_bytes(&PKSMP2_STOP_STATE);
        logger.write_decimal_u64(u64::from(mailbox.state));
        logger.write_bytes(&PKSMP2_STOP_RUNTIME_STATE);
        logger.write_decimal_u64(u64::from(mailbox.runtime_state));
        logger.write_bytes(&PKSMP2_TSC_ONLINE);
        logger.write_hex_u64(mailbox.tsc_online);
        logger.write_bytes(&PKSMP2_TSC_STOP);
        logger.write_hex_u64(mailbox.tsc_stop);
        logger.write_bytes(&PKSMP2_BASELINE_CHECKSUM);
        logger.write_hex_u64(mailbox.baseline_checksum);
        logger.write_bytes(&PKSMP2_RUNTIME_CHECKSUM);
        logger.write_hex_u64(mailbox.runtime_checksum);
        logger.write_bytes(&PKSMP2_STOP_TAIL);

        logger.write_bytes(&PKSMP2_RELEASE);
        logger.write_decimal_u64(proof.release_receipt.sequence);
        logger.write_bytes(&PKSMP2_ZEROED_BYTES);
        logger.write_decimal_u64(proof.release_receipt.zeroed_bytes);
        logger.write_bytes(&PKSMP2_VERIFIED_BYTES);
        logger.write_decimal_u64(proof.release_receipt.verified_bytes);
        logger.write_bytes(&PKSMP2_RELEASE_TAIL);
        logger.write_bytes(&PKSMP2_RESULT);
        halt_forever()
    }

    #[cfg(any())]
    {
        if trap_scenario == DevelopmentTrapScenario::SmpIpi {
            let mut logger = EarlyLogger::new(BootSink {
                serial: &mut serial,
                debugcon: &mut debugcon,
                ring: &EARLY_RING,
            });
            let proof = match run_smp_ipi(&decoded, validated.core, observed_cr3) {
                Ok(value) => value,
                Err(error) => {
                    logger.write_bytes(&PKSMP3_DENIED);
                    let reason =
                        u64::from(error.code()) | SMP_IPI_FAILURE_DETAIL.load(Ordering::Relaxed);
                    logger.write_hex_u64(reason);
                    logger.write_bytes(&PKSMP3_DENIED_TAIL);
                    poole_kernel_emergency_panic(PanicCode::SmpIpi as u32)
                }
            };
            let mailbox = proof.operation.mailbox;
            let ipi = proof.operation.ipi;
            let shootdown = ipi.shootdown;
            let retirement = proof.operation.retirement_receipt;

            logger.write_bytes(&PKSMP3_TOPOLOGY);
            logger.write_decimal_u64(proof.processor_count);
            logger.write_bytes(&PKSMP3_ENABLED);
            logger.write_decimal_u64(proof.enabled_processor_count);
            logger.write_bytes(&PKSMP3_BSP_APIC);
            logger.write_decimal_u64(u64::from(proof.bsp_apic_id));
            logger.write_bytes(&PKSMP3_TARGET_APIC);
            logger.write_decimal_u64(u64::from(proof.target_apic_id));
            logger.write_bytes(&PKSMP3_APIC_PHYSICAL);
            logger.write_hex_u64(proof.apic_physical);
            logger.write_bytes(&PKSMP3_TOPOLOGY_TAIL);

            logger.write_bytes(&PKSMP3_RESOURCES);
            logger.write_hex_u64(proof.layout.trampoline());
            logger.write_bytes(&PKSMP3_PAGES);
            logger.write_decimal_u64(proof.layout.page_count);
            logger.write_bytes(&PKSMP3_SIPI_VECTOR);
            logger.write_decimal_u64(u64::from(proof.layout.sipi_vector()));
            logger.write_bytes(&PKSMP3_TRAMPOLINE_BYTES);
            logger.write_decimal_u64(proof.trampoline_bytes);
            logger.write_bytes(&PKSMP3_ALLOCATION_SEQUENCE);
            logger.write_decimal_u64(proof.allocation_receipt.sequence);
            logger.write_bytes(&PKSMP3_RESOURCES_TAIL);

            logger.write_bytes(&PKSMP3_ONLINE);
            logger.write_bytes(&PKSMP3_ACCEPTED);
            logger.write_decimal_u64(u64::from(ipi.accepted_count));
            logger.write_bytes(&PKSMP3_RESCHEDULE);
            logger.write_decimal_u64(u64::from(ipi.reschedule_count));
            logger.write_bytes(&PKSMP3_SHOOTDOWN);
            logger.write_decimal_u64(u64::from(ipi.shootdown_count));
            logger.write_bytes(&PKSMP3_CALL_FUNCTION);
            logger.write_decimal_u64(u64::from(ipi.call_function_count));
            logger.write_bytes(&PKSMP3_DIAGNOSTIC);
            logger.write_decimal_u64(u64::from(ipi.diagnostic_count));
            logger.write_bytes(&PKSMP3_PANIC);
            logger.write_decimal_u64(u64::from(ipi.panic_count));
            logger.write_bytes(&PKSMP3_STOP_COUNT);
            logger.write_decimal_u64(u64::from(ipi.stop_count));
            logger.write_bytes(&PKSMP3_NEWLINE);

            logger.write_bytes(&PKSMP3_CONTROLS);
            logger.write_decimal_u64(u64::from(ipi.denied_count));
            logger.write_bytes(&PKSMP3_DELIVERY_COUNT);
            logger.write_decimal_u64(u64::from(ipi.delivery_count));
            logger.write_bytes(&PKSMP3_EOI_COUNT);
            logger.write_decimal_u64(u64::from(ipi.eoi_count));
            logger.write_bytes(&PKSMP3_SPURIOUS);
            logger.write_decimal_u64(u64::from(ipi.spurious_count));
            logger.write_bytes(&PKSMP3_APIC_ERROR);
            logger.write_decimal_u64(u64::from(ipi.apic_error_count));
            logger.write_bytes(&PKSMP3_NEWLINE);

            logger.write_bytes(&PKSMP3_TIMEOUT);
            logger.write_decimal_u64(u64::from(proof.operation.timeout_count));
            logger.write_bytes(&PKSMP3_NEWLINE);

            logger.write_bytes(&PKSMP3_SHOOTDOWN_RECEIPT);
            logger.write_hex_u64(retirement.root_physical);
            logger.write_bytes(&PKSMP3_PROBE);
            logger.write_decimal_u64(retirement.retired_generation);
            logger.write_bytes(&PKSMP3_ACTIVE_GENERATION);
            logger.write_decimal_u64(retirement.active_generation);
            logger.write_bytes(&PKSMP3_TARGET_MASK);
            logger.write_hex_u64(retirement.target_mask);
            logger.write_bytes(&PKSMP3_ACK_MASK);
            logger.write_hex_u64(retirement.ack_mask);
            logger.write_bytes(&PKSMP3_OLD_FRAME);
            logger.write_hex_u64(shootdown.old_frame_physical);
            logger.write_bytes(&PKSMP3_NEW_FRAME);
            logger.write_hex_u64(shootdown.new_frame_physical);
            logger.write_bytes(&PKSMP3_OBSERVED_BEFORE);
            logger.write_hex_u64(shootdown.observed_before);
            logger.write_bytes(&PKSMP3_OBSERVED_AFTER);
            logger.write_hex_u64(shootdown.observed_after);
            logger.write_bytes(&PKSMP3_INVALIDATIONS);
            logger.write_decimal_u64(retirement.invalidation_count);
            logger.write_bytes(&PKSMP3_LAST_ACK_GENERATION);
            logger.write_decimal_u64(shootdown.last_ack_generation);
            logger.write_bytes(&PKSMP3_PREMATURE_RECLAIM);
            logger.write_decimal_u64(proof.operation.premature_reclaim_rejected as u64);
            logger.write_bytes(&PKSMP3_RECLAIM_STATE);
            logger.write_decimal_u64(u64::from(shootdown.reclaim_state));
            logger.write_bytes(&PKSMP3_SHOOTDOWN_CHECKSUM);
            logger.write_hex_u64(shootdown.response_checksum);
            logger.write_bytes(&PKSMP3_NEWLINE);

            logger.write_bytes(&PKSMP3_STOP);
            logger.write_decimal_u64(ipi.ack_attempt);
            logger.write_bytes(&PKSMP3_ACK_SEQUENCE);
            logger.write_decimal_u64(ipi.ack_sequence);
            logger.write_bytes(&PKSMP3_LAST_SEQUENCE);
            logger.write_decimal_u64(ipi.last_accepted_sequence);
            logger.write_bytes(&PKSMP3_SERVICE_STATE);
            logger.write_decimal_u64(u64::from(ipi.service_state));
            logger.write_bytes(&PKSMP3_MAILBOX_STATE);
            logger.write_decimal_u64(u64::from(mailbox.state));
            logger.write_bytes(&PKSMP3_RUNTIME_STATE);
            logger.write_decimal_u64(u64::from(mailbox.runtime_state));
            logger.write_bytes(&PKSMP3_PANIC_LATCHED);
            logger.write_decimal_u64(u64::from(ipi.panic_latched));
            logger.write_bytes(&PKSMP3_RESPONSE_CHECKSUM);
            logger.write_hex_u64(ipi.response_checksum);
            logger.write_bytes(&PKSMP3_BASELINE_CHECKSUM);
            logger.write_hex_u64(mailbox.baseline_checksum);
            logger.write_bytes(&PKSMP3_RUNTIME_CHECKSUM);
            logger.write_hex_u64(mailbox.runtime_checksum);
            logger.write_bytes(&PKSMP3_INIT_ASSERTS);
            logger.write_decimal_u64(proof.operation.init_asserts);
            logger.write_bytes(&PKSMP3_INIT_DEASSERTS);
            logger.write_decimal_u64(proof.operation.init_deasserts);
            logger.write_bytes(&PKSMP3_SIPIS);
            logger.write_decimal_u64(proof.operation.sipis);
            logger.write_bytes(&PKSMP3_TSS_BUSY);
            logger.write_decimal_u64(proof.operation.tss_busy_verified as u64);
            logger.write_bytes(&PKSMP3_IDT_VERIFIED);
            logger.write_decimal_u64(proof.operation.idt_verified as u64);
            logger.write_bytes(&PKSMP3_XSTATE_VERIFIED);
            logger.write_decimal_u64(proof.operation.xstate_verified as u64);
            logger.write_bytes(&PKSMP3_APIC_TABLE_VERIFIED);
            logger.write_decimal_u64(proof.operation.apic_table_verified as u64);
            logger.write_bytes(&PKSMP3_STOP_TAIL);

            logger.write_bytes(&PKSMP3_RELEASE);
            logger.write_decimal_u64(proof.release_receipt.sequence);
            logger.write_bytes(&PKSMP3_ZEROED_BYTES);
            logger.write_decimal_u64(proof.release_receipt.zeroed_bytes);
            logger.write_bytes(&PKSMP3_VERIFIED_BYTES);
            logger.write_decimal_u64(proof.release_receipt.verified_bytes);
            logger.write_bytes(&PKSMP3_FRAME_ALLOCATION_SEQUENCES);
            logger.write_decimal_u64(proof.old_frame_allocation_receipt.sequence);
            logger.write_bytes(b",");
            logger.write_decimal_u64(proof.new_frame_allocation_receipt.sequence);
            logger.write_bytes(&PKSMP3_FRAME_RELEASE_SEQUENCES);
            logger.write_decimal_u64(proof.operation.old_frame_release_receipt.sequence);
            logger.write_bytes(b",");
            logger.write_decimal_u64(proof.new_frame_release_receipt.sequence);
            logger.write_bytes(&PKSMP3_FRAME_ZEROED_BYTES);
            logger.write_decimal_u64(
                proof.operation.old_frame_release_receipt.zeroed_bytes
                    + proof.new_frame_release_receipt.zeroed_bytes,
            );
            logger.write_bytes(&PKSMP3_FRAME_VERIFIED_BYTES);
            logger.write_decimal_u64(
                proof.operation.old_frame_release_receipt.verified_bytes
                    + proof.new_frame_release_receipt.verified_bytes,
            );
            logger.write_bytes(&PKSMP3_RELEASE_TAIL);
            logger.write_bytes(&PKSMP3_RESULT);
            halt_forever()
        }
    }

    if trap_scenario == DevelopmentTrapScenario::SmpIpi {
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        let proof = match run_smp_ipi(&decoded, validated.core, observed_cr3) {
            Ok(value) => value,
            Err(error) => {
                logger.write_bytes(&PKSMP5_DENIED);
                let reason =
                    u64::from(error.code()) | SMP_IPI_FAILURE_DETAIL.load(Ordering::Relaxed);
                logger.write_hex_u64(reason);
                logger.write_bytes(&PKSMP5_DENIED_TAIL);
                poole_kernel_emergency_panic(PanicCode::SmpIpi as u32)
            }
        };

        logger.write_bytes(&PKSMP5_TOPOLOGY);
        logger.write_decimal_u64(proof.processor_count);
        logger.write_bytes(&PKSMP5_ENABLED);
        logger.write_decimal_u64(proof.enabled_processor_count);
        logger.write_bytes(&PKSMP5_BSP_APIC_ID);
        logger.write_decimal_u64(u64::from(proof.bsp_apic_id));
        logger.write_bytes(&PKSMP5_TARGET_APIC_IDS);
        for (index, apic_id) in proof.target_apic_ids.into_iter().enumerate() {
            if index != 0 {
                logger.write_bytes(&PKSMP5_COMMA);
            }
            logger.write_decimal_u64(u64::from(apic_id));
        }
        logger.write_bytes(&PKSMP5_TARGET_MASK);
        logger.write_hex_u64(smp_ipi::TARGET_CPU_MASK);
        logger.write_bytes(&PKSMP5_APIC_PHYSICAL);
        logger.write_hex_u64(proof.apic_physical);
        logger.write_bytes(&PKSMP5_TOPOLOGY_TAIL);

        logger.write_bytes(&PKSMP5_PARTIAL);
        logger.write_hex_u64(proof.partial.started_mask);
        logger.write_bytes(&PKSMP5_TIMEOUT_APIC_ID);
        logger.write_decimal_u64(u64::from(proof.partial.timeout_target_apic_id));
        logger.write_bytes(&PKSMP5_TIMEOUT_MASK);
        logger.write_hex_u64(smp_ipi::OFFLINE_CPU_MASK);
        logger.write_bytes(&PKSMP5_TIMEOUT_COUNT);
        logger.write_decimal_u64(u64::from(proof.partial.timeout_count));
        logger.write_bytes(&PKSMP5_PARKED_MASK);
        logger.write_hex_u64(proof.partial.parked_mask);
        logger.write_bytes(&PKSMP5_RELEASED_MASK);
        logger.write_hex_u64(proof.partial.released_mask);
        logger.write_bytes(&PKSMP5_RESOURCE_PAGES);
        logger.write_decimal_u64(proof.partial.resource_pages_released);
        logger.write_bytes(&PKSMP5_FRAME_PAGES);
        logger.write_decimal_u64(proof.partial.frame_pages_released);
        logger.write_bytes(&PKSMP5_ZEROED_BYTES);
        logger.write_decimal_u64(proof.partial.zeroed_bytes);
        logger.write_bytes(&PKSMP5_VERIFIED_BYTES);
        logger.write_decimal_u64(proof.partial.verified_bytes);
        logger.write_bytes(&PKSMP5_PARTIAL_TAIL);

        logger.write_bytes(&PKSMP5_RETRY);
        logger.write_decimal_u64(u64::from(proof.lifecycle.retry_count));
        logger.write_bytes(&PKSMP5_PARTIAL_ROLLBACK_COUNT);
        logger.write_decimal_u64(u64::from(proof.lifecycle.partial_rollback_count));
        logger.write_bytes(&PKSMP5_STARTED_MASK);
        logger.write_hex_u64(proof.lifecycle.started_mask);
        logger.write_bytes(&PKSMP5_ONLINE_MASK);
        logger.write_hex_u64(proof.lifecycle.online_mask);
        logger.write_bytes(&PKSMP5_RETRY_TAIL);

        let mut resource_pages = 0u64;
        let mut frame_pages = 0u64;
        let mut resource_zeroed_bytes = 0u64;
        let mut frame_zeroed_bytes = 0u64;
        let mut resource_verified_bytes = 0u64;
        let mut frame_verified_bytes = 0u64;
        for index in 0..smp_ipi::AP_COUNT {
            let resource = proof.aps[index];
            let operation = proof.operations[index];
            let ipi = operation.ipi;
            let mailbox = operation.mailbox;
            logger.write_bytes(&PKSMP5_AP);
            logger.write_decimal_u64(index as u64);
            logger.write_bytes(&PKSMP5_APIC_ID);
            logger.write_decimal_u64(u64::from(resource.target_apic_id));
            logger.write_bytes(&PKSMP5_PHYSICAL_START);
            logger.write_hex_u64(resource.layout.trampoline());
            logger.write_bytes(&PKSMP5_PAGES);
            logger.write_decimal_u64(resource.layout.page_count);
            logger.write_bytes(&PKSMP5_SIPI_VECTOR);
            logger.write_decimal_u64(u64::from(resource.layout.sipi_vector()));
            logger.write_bytes(&PKSMP5_TRAMPOLINE_BYTES);
            logger.write_decimal_u64(resource.trampoline_bytes);
            logger.write_bytes(&PKSMP5_ALLOCATION_SEQUENCE);
            logger.write_decimal_u64(resource.allocation_receipt.sequence);
            logger.write_bytes(&PKSMP5_FRAME_ALLOCATION_SEQUENCES);
            logger.write_decimal_u64(resource.old_frame_allocation_receipt.sequence);
            logger.write_bytes(&PKSMP5_COMMA);
            logger.write_decimal_u64(resource.new_frame_allocation_receipt.sequence);
            logger.write_bytes(&PKSMP5_FRAME_RELEASE_SEQUENCES);
            logger.write_decimal_u64(operation.old_frame_release_receipt.sequence);
            logger.write_bytes(&PKSMP5_COMMA);
            logger.write_decimal_u64(operation.new_frame_release_receipt.sequence);
            logger.write_bytes(&PKSMP5_RESOURCE_RELEASE_SEQUENCE);
            logger.write_decimal_u64(operation.resource_release_receipt.sequence);
            logger.write_bytes(&PKSMP5_SERVICE_STATE);
            logger.write_decimal_u64(u64::from(ipi.service_state));
            logger.write_bytes(&PKSMP5_MAILBOX_STATE);
            logger.write_decimal_u64(u64::from(mailbox.state));
            logger.write_bytes(&PKSMP5_RUNTIME_STATE);
            logger.write_decimal_u64(u64::from(mailbox.runtime_state));
            logger.write_bytes(&PKSMP5_DELIVERIES);
            logger.write_decimal_u64(u64::from(ipi.delivery_count));
            logger.write_bytes(&PKSMP5_ACCEPTED);
            logger.write_decimal_u64(u64::from(ipi.accepted_count));
            logger.write_bytes(&PKSMP5_DENIED_COUNT);
            logger.write_decimal_u64(u64::from(ipi.denied_count));
            logger.write_bytes(&PKSMP5_EOIS);
            logger.write_decimal_u64(u64::from(ipi.eoi_count));
            logger.write_bytes(&PKSMP5_DIAGNOSTIC);
            logger.write_decimal_u64(u64::from(ipi.diagnostic_count));
            logger.write_bytes(&PKSMP5_SHOOTDOWN_COUNT);
            logger.write_decimal_u64(u64::from(ipi.shootdown_count));
            logger.write_bytes(&PKSMP5_STOP);
            logger.write_decimal_u64(u64::from(ipi.stop_count));
            logger.write_bytes(&PKSMP5_TIMEOUT_COUNT);
            logger.write_decimal_u64(u64::from(operation.timeout_count));
            logger.write_bytes(&PKSMP5_INIT_ASSERTS);
            logger.write_decimal_u64(operation.init_asserts);
            logger.write_bytes(&PKSMP5_INIT_DEASSERTS);
            logger.write_decimal_u64(operation.init_deasserts);
            logger.write_bytes(&PKSMP5_SIPIS);
            logger.write_decimal_u64(operation.sipis);
            logger.write_bytes(&PKSMP5_TARGET_MASK);
            logger.write_hex_u64(ipi.shootdown.target_mask);
            logger.write_bytes(&PKSMP5_ACK_MASK);
            logger.write_hex_u64(ipi.shootdown.ack_mask);
            logger.write_bytes(&PKSMP5_INVALIDATIONS);
            logger.write_decimal_u64(ipi.shootdown.invalidation_count);
            logger.write_bytes(&PKSMP5_BASELINE_CHECKSUM);
            logger.write_hex_u64(mailbox.baseline_checksum);
            logger.write_bytes(&PKSMP5_RUNTIME_CHECKSUM);
            logger.write_hex_u64(mailbox.runtime_checksum);
            logger.write_bytes(&PKSMP5_RESPONSE_CHECKSUM);
            logger.write_hex_u64(ipi.response_checksum);
            logger.write_bytes(&PKSMP5_AP_TAIL);

            resource_pages += operation.resource_release_receipt.page_count;
            frame_pages += operation.old_frame_release_receipt.page_count
                + operation.new_frame_release_receipt.page_count;
            resource_zeroed_bytes += operation.resource_release_receipt.zeroed_bytes;
            resource_verified_bytes += operation.resource_release_receipt.verified_bytes;
            frame_zeroed_bytes += operation.old_frame_release_receipt.zeroed_bytes
                + operation.new_frame_release_receipt.zeroed_bytes;
            frame_verified_bytes += operation.old_frame_release_receipt.verified_bytes
                + operation.new_frame_release_receipt.verified_bytes;
        }

        logger.write_bytes(&PKSMP5_SHOOTDOWN);
        logger.write_hex_u64(proof.retirement.target_mask);
        logger.write_bytes(&PKSMP5_ACK_MASK);
        logger.write_hex_u64(proof.retirement.ack_mask);
        logger.write_bytes(&PKSMP5_RETIRED_GENERATION);
        logger.write_decimal_u64(proof.retirement.retired_generation);
        logger.write_bytes(&PKSMP5_ACTIVE_GENERATION);
        logger.write_decimal_u64(proof.retirement.active_generation);
        logger.write_bytes(&PKSMP5_INVALIDATIONS);
        logger.write_decimal_u64(proof.retirement.invalidation_count);
        logger.write_bytes(&PKSMP5_ROOT_CHECKSUM);
        logger.write_hex_u64(proof.retirement.root_checksum);
        logger.write_bytes(&PKSMP5_OLD_FRAME_CHECKSUM);
        logger.write_hex_u64(proof.retirement.old_frame_checksum);
        logger.write_bytes(&PKSMP5_NEW_FRAME_CHECKSUM);
        logger.write_hex_u64(proof.retirement.new_frame_checksum);
        logger.write_bytes(&PKSMP5_PREMATURE_RECLAIM_REJECTIONS);
        logger.write_decimal_u64(proof.premature_reclaim_rejections);
        logger.write_bytes(&PKSMP5_SHOOTDOWN_TAIL);

        logger.write_bytes(&PKSMP5_LIFECYCLE);
        logger.write_hex_u64(proof.lifecycle.started_mask);
        logger.write_bytes(&PKSMP5_ONLINE_MASK);
        logger.write_hex_u64(proof.lifecycle.online_mask);
        logger.write_bytes(&PKSMP5_QUIESCED_MASK);
        logger.write_hex_u64(proof.lifecycle.quiesced_mask);
        logger.write_bytes(&PKSMP5_PARKED_MASK);
        logger.write_hex_u64(proof.lifecycle.parked_mask);
        logger.write_bytes(&PKSMP5_VALIDATED_MASK);
        logger.write_hex_u64(proof.lifecycle.validated_mask);
        logger.write_bytes(&PKSMP5_RELEASED_MASK);
        logger.write_hex_u64(proof.lifecycle.released_mask);
        logger.write_bytes(&PKSMP5_TIMEOUT_COUNT);
        logger.write_decimal_u64(u64::from(proof.lifecycle.timeout_count));
        logger.write_bytes(&PKSMP5_RETRY_COUNT);
        logger.write_decimal_u64(u64::from(proof.lifecycle.retry_count));
        logger.write_bytes(&PKSMP5_PARTIAL_ROLLBACK_COUNT);
        logger.write_decimal_u64(u64::from(proof.lifecycle.partial_rollback_count));
        logger.write_bytes(&PKSMP5_LIFECYCLE_TAIL);

        logger.write_bytes(&PKSMP5_RELEASE);
        logger.write_decimal_u64(resource_pages);
        logger.write_bytes(&PKSMP5_FRAME_PAGES);
        logger.write_decimal_u64(frame_pages);
        logger.write_bytes(&PKSMP5_RESOURCE_ZEROED_BYTES);
        logger.write_decimal_u64(resource_zeroed_bytes);
        logger.write_bytes(&PKSMP5_RESOURCE_VERIFIED_BYTES);
        logger.write_decimal_u64(resource_verified_bytes);
        logger.write_bytes(&PKSMP5_FRAME_ZEROED_BYTES);
        logger.write_decimal_u64(frame_zeroed_bytes);
        logger.write_bytes(&PKSMP5_FRAME_VERIFIED_BYTES);
        logger.write_decimal_u64(frame_verified_bytes);
        logger.write_bytes(&PKSMP5_TOTAL_PAGES);
        logger.write_decimal_u64(resource_pages + frame_pages);
        logger.write_bytes(&PKSMP5_RELEASE_TAIL);
        logger.write_bytes(&PKSMP5_RESULT);
        halt_forever()
    }

    if trap_scenario == DevelopmentTrapScenario::Scheduler {
        let cpu = SchedulerCpuId::new(0)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        let mut neutral = Scheduler::new(1)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        let task_a = neutral
            .create_task(0, 1, 16, 1)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        let task_b = neutral
            .create_task(1, 1, 16, 1)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        neutral
            .activate(task_a, cpu)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        neutral
            .activate(task_b, cpu)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));

        let mut trace = [0u8; 8];
        for slot in &mut trace {
            let selected = neutral
                .dispatch(cpu)
                .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
            *slot = selected.slot;
            neutral
                .account_tick(cpu, 1)
                .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
            neutral
                .yield_current(cpu)
                .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        }
        if trace != [0, 1, 0, 1, 0, 1, 0, 1] {
            poole_kernel_emergency_panic(PanicCode::Scheduler as u32);
        }

        SCHEDULER_SWITCH_LOCK
            .lock_bounded(1, 1)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        let switch_contract = SchedulerContextSwitchContract {
            outgoing: SchedulerTaskId::new(0, 1)
                .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32)),
            incoming: SchedulerTaskId::new(1, 1)
                .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32)),
            cpu,
            scheduler_lock_held: SCHEDULER_SWITCH_LOCK.owner() == 1,
            interrupts_disabled: arch::x86_64::read_rflags() & (1 << 9) == 0,
            same_address_space: true,
            fs_gs_unchanged: true,
            xstate_unused: true,
            debug_state_unused: true,
            pmu_state_unused: true,
            kernel_stacks_distinct: true,
            stack_alignment: 16,
        };
        validate_context_switch_contract(&switch_contract)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        let switch_proof = arch::x86_64::run_scheduler_context_switch_probe(&trace)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
        if SCHEDULER_SWITCH_LOCK.owner() != 1 {
            poole_kernel_emergency_panic(PanicCode::Scheduler as u32);
        }
        SCHEDULER_SWITCH_LOCK
            .unlock(1)
            .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));

        for task in [task_a, task_b] {
            neutral
                .teardown(task)
                .unwrap_or_else(|_| poole_kernel_emergency_panic(PanicCode::Scheduler as u32));
            match neutral.task_snapshot(task) {
                Ok(snapshot) if snapshot.state == SchedulerTaskState::Dead => {}
                _ => poole_kernel_emergency_panic(PanicCode::Scheduler as u32),
            }
        }
        let summary = neutral.summary();
        if summary.task_count != 2
            || summary.runnable_count != 0
            || summary.running_count != 0
            || summary.blocked_count != 0
            || summary.dead_count != 2
            || summary.dispatch_count != 8
            || summary.migration_count != 0
            || summary.wake_count != 0
            || summary.teardown_count != 2
            || neutral.queue_len(cpu) != Ok(0)
            || SCHEDULER_SWITCH_LOCK.owner() != 0
            || switch_proof.dispatch_count != 8
            || switch_proof.machine_transition_count != 16
            || switch_proof.task_a_runs != 4
            || switch_proof.task_b_runs != 4
            || switch_proof.callee_saved_register_count != 6
            || !switch_proof.rflags_preserved
            || !switch_proof.same_cr3
            || !switch_proof.fs_gs_unchanged
            || !switch_proof.xstate_unused
            || !switch_proof.debug_state_unused
            || !switch_proof.pmu_state_unused
            || !switch_proof.stacks_distinct
            || switch_proof.stack_bytes_each != 16_384
            || switch_proof.stack_alignment != 16
            || switch_proof.stack_bytes_cleared != 32_768
            || switch_proof.register_error_count != 0
        {
            poole_kernel_emergency_panic(PanicCode::Scheduler as u32);
        }
        let mut logger = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        logger.write_bytes(&PKSCHED1_CORE);
        logger.write_bytes(&PKSCHED1_SWITCH);
        logger.write_bytes(&PKSCHED1_CLEANUP);
        logger.write_bytes(&PKSCHED1_RESULT);
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
        DevelopmentTrapScenario::InterruptTime => {
            poole_kernel_emergency_panic(PanicCode::InterruptTime as u32)
        }
        DevelopmentTrapScenario::SmpFirstAp => {
            poole_kernel_emergency_panic(PanicCode::SmpFirstAp as u32)
        }
        DevelopmentTrapScenario::SmpPerCpuRuntime => {
            poole_kernel_emergency_panic(PanicCode::SmpPerCpuRuntime as u32)
        }
        DevelopmentTrapScenario::SmpIpi => poole_kernel_emergency_panic(PanicCode::SmpIpi as u32),
        DevelopmentTrapScenario::Scheduler => {
            poole_kernel_emergency_panic(PanicCode::Scheduler as u32)
        }
        DevelopmentTrapScenario::SchedulerPreempt => {
            poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
        }
    }
}

fn dispatch_scheduler_preemption(frame: &mut TrapFrame, depth: u32) {
    if SCHEDULER_SWITCH_LOCK.lock_bounded(2, 1).is_err() {
        poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
    }
    let ist_bottom = IST1_BOTTOM.load(Ordering::Acquire);
    let ist_top = IST1_TOP.load(Ordering::Acquire);
    let handler_rsp = frame as *const TrapFrame as u64;
    let frame_contract = SchedulerInterruptFrameContract {
        depth,
        vector: frame.vector,
        error_code: frame.error_code,
        code_selector: frame.code_selector,
        data_selector: frame.data_selector,
        interrupted_rflags: frame.rflags,
        handler_interrupts_disabled: arch::x86_64::read_rflags() & (1 << 9) == 0,
        scheduler_lock_held: SCHEDULER_SWITCH_LOCK.owner() == 2,
        handler_rsp,
        frame_bytes: core::mem::size_of::<TrapFrame>() as u64,
        ist_bottom,
        ist_top,
    };
    let operation = unsafe {
        // SAFETY: the interrupt gate cleared IF and owner token 2 serializes the runtime cell.
        SCHEDULER_PREEMPT_RUNTIME.with_mut(|controller| {
            let current = controller
                .scheduler()
                .current(SchedulerCpuId::new(0).map_err(|_| ())?)
                .map_err(|_| ())?
                .ok_or(())?;
            let outgoing = current.index();
            if !arch::x86_64::scheduler_preemption_context_valid(outgoing, frame) {
                return Err(());
            }
            // SAFETY: the interrupted task is stopped on IST1 and owns this complete frame.
            SCHEDULER_PREEMPT_CONTEXTS
                .save(outgoing, *frame)
                .map_err(|_| ())?;
            let outcome = controller.handle_timer(&frame_contract).map_err(|_| ())?;
            Ok((outcome, outgoing))
        })
    };
    let (outcome, outgoing) = match operation {
        Some(Ok(value)) => value,
        _ => poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32),
    };
    let expected_next = [0usize, 1, 2, 0, 3, 3];
    let expected_cause = [
        RescheduleCause::None,
        RescheduleCause::QuantumExpired,
        RescheduleCause::HigherPriorityWake,
        RescheduleCause::CurrentBlocked,
        RescheduleCause::HigherPriorityWake,
        RescheduleCause::None,
    ];
    let expected_events = [0u8, 0, 1, 1, 1, 0];
    let tick_index = outcome
        .tick
        .checked_sub(1)
        .and_then(|value| usize::try_from(value).ok())
        .filter(|value| *value < expected_next.len())
        .unwrap_or_else(|| poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32));
    let incoming_task = outcome.next.index();
    let expected_switch = outgoing != expected_next[tick_index];
    if incoming_task != expected_next[tick_index]
        || outcome.cause != expected_cause[tick_index]
        || outcome.events_processed != expected_events[tick_index]
        || outcome.context_switch_required != expected_switch
        || outcome.previous.index() != outgoing
    {
        poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
    }

    let incoming = if outcome.context_switch_required {
        let value = unsafe {
            // SAFETY: the scheduler selected this stopped or initialized task context.
            SCHEDULER_PREEMPT_CONTEXTS.load(incoming_task)
        }
        .unwrap_or_else(|| poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32));
        if !arch::x86_64::scheduler_preemption_context_valid(incoming_task, &value) {
            poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
        }
        let (outgoing_bottom, outgoing_top) =
            arch::x86_64::scheduler_preemption_stack_bounds(outgoing).unwrap_or_else(|| {
                poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
            });
        let (incoming_bottom, incoming_top) =
            arch::x86_64::scheduler_preemption_stack_bounds(incoming_task).unwrap_or_else(|| {
                poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32)
            });
        if validate_scheduler_context_ownership(&SchedulerContextOwnership {
            outgoing_rsp: frame.rsp,
            outgoing_bottom,
            outgoing_top,
            incoming_rsp: value.rsp,
            incoming_bottom,
            incoming_top,
            stack_alignment: 16,
        })
        .is_err()
        {
            poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
        }
        Some(value)
    } else {
        None
    };

    let apic = IRQ_APIC_VIRTUAL.load(Ordering::Acquire);
    let timer_count = SCHEDULER_PREEMPT_TIMER_COUNT.load(Ordering::Acquire);
    if apic == 0 || timer_count == 0 {
        poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
    }
    let increment = |counter: &AtomicU32| {
        if counter.fetch_add(1, Ordering::AcqRel) == u32::MAX {
            poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
        }
    };
    increment(&IRQ_TIMER_DELIVERIES);
    // SAFETY: selector 16 retains the guarded UC local-APIC mapping until final rollback.
    unsafe { write_volatile((apic + 0xb0) as usize as *mut u32, 0) };
    increment(&IRQ_EOI_COUNT);
    if let Some(value) = incoming {
        *frame = value;
        increment(&SCHEDULER_PREEMPT_FRAME_SWITCHES);
    }
    if outcome.tick == 6 {
        poole_scheduler_preempt_done.store(1, Ordering::Release);
    } else {
        // SAFETY: the LVT timer remains in one-shot mode and IF is still clear.
        unsafe { write_volatile((apic + 0x380) as usize as *mut u32, timer_count) };
    }
    if SCHEDULER_SWITCH_LOCK.unlock(2).is_err() {
        poole_kernel_emergency_panic(PanicCode::SchedulerPreempt as u32);
    }
    TRAP_DEPTH.store(0, Ordering::Release);
}

fn dispatch_interrupt_time(frame: &TrapFrame, depth: u32) {
    let ist_bottom = IST1_BOTTOM.load(Ordering::Acquire);
    let ist_top = IST1_TOP.load(Ordering::Acquire);
    let handler_rsp = frame as *const TrapFrame as u64;
    if depth != 1
        || frame.error_code != 0
        || frame.code_selector != u64::from(poolekernel::KERNEL_CODE_SELECTOR)
        || frame.data_selector != u64::from(poolekernel::KERNEL_DATA_SELECTOR)
        || frame.rflags & (1 << 1) == 0
        || frame.rflags & (1 << 9) == 0
        || frame.rflags & ((1 << 14) | (1 << 17)) != 0
        || handler_rsp < ist_bottom
        || handler_rsp
            .checked_add(core::mem::size_of::<TrapFrame>() as u64)
            .is_none_or(|end| end > ist_top)
    {
        poole_kernel_emergency_panic(PanicCode::InterruptTime as u32);
    }
    let apic = IRQ_APIC_VIRTUAL.load(Ordering::Acquire);
    if apic == 0 {
        poole_kernel_emergency_panic(PanicCode::InterruptTime as u32);
    }
    let increment = |counter: &AtomicU32| {
        let previous = counter.fetch_add(1, Ordering::AcqRel);
        if previous == u32::MAX {
            poole_kernel_emergency_panic(PanicCode::InterruptTime as u32);
        }
    };
    match frame.vector {
        vector if vector == u64::from(TIMER_VECTOR) => {
            increment(&IRQ_TIMER_DELIVERIES);
            // SAFETY: PKIRQ1 keeps the guarded UC local-APIC mapping live until IF closes.
            unsafe { write_volatile((apic + 0xb0) as usize as *mut u32, 0) };
            increment(&IRQ_EOI_COUNT);
        }
        vector if vector == u64::from(APIC_ERROR_VECTOR) => {
            increment(&IRQ_ERROR_COUNT);
            // SAFETY: local APIC errors enter the in-service state and require EOI.
            unsafe { write_volatile((apic + 0xb0) as usize as *mut u32, 0) };
            increment(&IRQ_EOI_COUNT);
        }
        vector if vector == u64::from(SPURIOUS_VECTOR) => {
            increment(&IRQ_SPURIOUS_COUNT);
        }
        _ => poole_kernel_emergency_panic(PanicCode::InterruptTime as u32),
    }
    TRAP_DEPTH.store(0, Ordering::Release);
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
    if scenario == DevelopmentTrapScenario::SchedulerPreempt {
        dispatch_scheduler_preemption(frame, depth);
        return;
    }
    if scenario == DevelopmentTrapScenario::InterruptTime {
        dispatch_interrupt_time(frame, depth);
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
