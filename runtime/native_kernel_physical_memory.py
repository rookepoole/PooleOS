"""Independent PKPMM7 oracle for ACPI-gated reclaim and retained snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_map, native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKPMM7"
ACPI_CONTRACT_ID = "PKACPI1"
SELECTED_MOVE_ID = "N9-PMM-ACPI-CONSUMER-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-physical-memory-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-physical-memory-contract.schema.json"
SCHEMA_RELATIVE = "specs/native-kernel-physical-memory-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-physical-memory-readiness.json"
MARKER_COUNT = 45
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 31
COMMON_KERNEL_MARKER_COUNT = 4
SELECTOR = 8
FEATURE = "development-physical-memory"
PAGE_BYTES = 4096
DMA_END = 16 * 1024 * 1024
DMA32_END = 4 * 1024 * 1024 * 1024
MAX_MEMORY_ENTRIES = 256
COMPLETION_MARKER = b"POOLEOS:KERNEL:PMM-RESULT PASS contract=PKPMM7"
METADATA_ARENA_PAGE_COUNT = 5
METADATA_GUARD_PAGE_COUNT = 2
METADATA_OWNER = 0x4D45
METADATA_MANAGER_BYTES = 15632
LEDGER_INITIAL_PAGE_COUNT = 4
LEDGER_PAGE_COUNTS = (4, 8, 15, 29)
LEDGER_FINAL_PAGE_COUNT = 29
LEDGER_FINAL_CAPACITIES = (2048, 256, 2048, 128, 16)
LEDGER_RETIRED_PAGE_COUNT = 27
LEDGER_PTE_WRITES = 83
LEDGER_PRESSURE_COUNTS = (119, 7, 3, 59, 3, 1)
LEDGER_GROWTH_HEADROOM = (1, 4)
LEDGER_WINDOW_PAGE_CAPACITY = 32
LEDGER_NEXT_PAGE_COUNT = 58
MAX_SCRUB_RECEIPTS = 16
MAX_RECLAIM_RECEIPTS = 2
METADATA_MAP_START = (
    native_kernel_map.MIN_VIRTUAL_BASE + native_kernel_map.METADATA_FIRST_PAGE * PAGE_BYTES
)
BOOT_RECLAIM_PAGE_COUNT = 11250
BOOT_RECLAIM_SOURCE_RECORD_COUNT = 70
BOOT_RECLAIM_RANGE_COUNT = 12
BOOT_RECLAIM_PAGES_BY_ZONE = (2018, 9232, 0)
ACPI_HELD_PAGE_COUNT = 11
BOOT_RECLAIM_RANGE_CHECKSUM = 0xFDAB689F085C3287
BOOT_RECLAIM_RECEIPT_CHECKSUM = 0x5DEA9A3BC9E10C18
RECLAIM_SCRUB_BYTES = BOOT_RECLAIM_PAGE_COUNT * PAGE_BYTES
ACPI_RECLAIM_SOURCE_RECORD_COUNT = 1
ACPI_RECLAIM_RANGE_COUNT = 1
ACPI_RECLAIM_PAGE_COUNT = 11
ACPI_RECLAIM_PAGES_BY_ZONE = (0, 11, 0)
ACPI_RECLAIM_RANGE_CHECKSUM = 0xC718FB26B45257F2
ACPI_RECLAIM_RECEIPT_CHECKSUM = 0x60DAA52A8A05ABD6
ACPI_SNAPSHOT_PAGE_COUNT = 1
ACPI_SNAPSHOT_BYTE_COUNT = 616
ACPI_SNAPSHOT_COPIED_BYTES = 600
ACPI_RSDP_ADDRESS = 0x1F77E014
ACPI_XSDT_ADDRESS = 0x1F77D0E8
ACPI_XSDT_ENTRY_COUNT = 6
ACPI_REQUIRED_TABLE_BYTES = (120, 244, 56, 60)
SCRUB_PAGE_COUNT = (
    211
    + ACPI_SNAPSHOT_PAGE_COUNT
    + BOOT_RECLAIM_PAGE_COUNT
    + ACPI_RECLAIM_PAGE_COUNT
)
SCRUB_BYTES = SCRUB_PAGE_COUNT * PAGE_BYTES
PHYSICAL_WRITES = 5_875_277
PHYSICAL_READS = 5_879_957
TEMPORARY_PTE_WRITES = 23_172
BOOTSTRAP_INVALIDATIONS = 23_172
METADATA_PTE_WRITES = 5
STALE_PATTERN = 0xA5A55A5AC3C33C3C

IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/handoff/src/lib.rs",
    "native/kmap/src/lib.rs",
    "native/livehandoff/src/lib.rs",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/acpi.rs",
    "native/kernel/src/physical_memory.rs",
    "native/kernel/src/revalidation.rs",
    "runtime/native_boot_exit.py",
    "runtime/native_kernel_map.py",
    "runtime/native_kernel_physical_memory.py",
    "runtime/native_kernel_transfer.py",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-load-contract.json",
    "specs/native-kernel-map-contract.json",
    "tools/qualify_native_kernel_physical_memory.py",
    "tests/test_native_kernel_physical_memory.py",
    "docs/native-kernel-physical-memory.md",
    "runs/native-kernel-transfer-readiness.json",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N9-PKPMM-MARKER-OMISSION",
    "NEG-N9-PKPMM-MARKER-ORDER",
    "NEG-N9-PKPMM-MARKER-DUPLICATE",
    "NEG-N9-PKPMM-SELECTOR",
    "NEG-N9-PKPMM-CONTRACT",
    "NEG-N9-PKPMM-ENTRY-COUNT",
    "NEG-N9-PKPMM-USABLE-PAGES",
    "NEG-N9-PKPMM-BOOT-RECLAIMABLE",
    "NEG-N9-PKPMM-LOADER-RESERVED",
    "NEG-N9-PKPMM-NULL-GUARD",
    "NEG-N9-PKPMM-DMA-SOURCE",
    "NEG-N9-PKPMM-DMA-MANAGED",
    "NEG-N9-PKPMM-DMA32-SOURCE",
    "NEG-N9-PKPMM-DMA32-MANAGED",
    "NEG-N9-PKPMM-NORMAL-SOURCE",
    "NEG-N9-PKPMM-NORMAL-MANAGED",
    "NEG-N9-PKPMM-EXTENT-COUNT",
    "NEG-N9-PKPMM-LARGEST-DMA",
    "NEG-N9-PKPMM-LARGEST-DMA32",
    "NEG-N9-PKPMM-LARGEST-NORMAL",
    "NEG-N9-PKPMM-KERNEL-BASE",
    "NEG-N9-PKPMM-KERNEL-PAGES",
    "NEG-N9-PKPMM-HANDOFF-BASE",
    "NEG-N9-PKPMM-HANDOFF-PAGES",
    "NEG-N9-PKPMM-ROOT",
    "NEG-N9-PKPMM-PROTECTED",
    "NEG-N9-PKPMM-METADATA-PAGES",
    "NEG-N9-PKPMM-METADATA-PHYSICAL",
    "NEG-N9-PKPMM-METADATA-VIRTUAL",
    "NEG-N9-PKPMM-METADATA-GENERATION",
    "NEG-N9-PKPMM-METADATA-OWNER",
    "NEG-N9-PKPMM-METADATA-MANAGER-BYTES",
    "NEG-N9-PKPMM-METADATA-SOURCE-RECORDS",
    "NEG-N9-PKPMM-METADATA-FREE-EXTENTS",
    "NEG-N9-PKPMM-METADATA-ALLOCATION-RECORDS",
    "NEG-N9-PKPMM-METADATA-RECEIPT-RECORDS",
    "NEG-N9-PKPMM-METADATA-HANDOFF-CHECKSUM",
    "NEG-N9-PKPMM-METADATA-FINAL-CHECKSUM",
    "NEG-N9-PKPMM-METADATA-GUARD-PAGES",
    "NEG-N9-PKPMM-METADATA-MAPPING-COUNT",
    "NEG-N9-PKPMM-METADATA-PTE-WRITES",
    "NEG-N9-PKPMM-METADATA-RELEASE-EXCLUDED",
    "NEG-N9-PKPMM-METADATA-RELEASE-REJECTED",
    "NEG-N9-PKPMM-METADATA-INTEGRITY",
    "NEG-N9-PKPMM-METADATA-RESERVATION-ROLLBACK",
    "NEG-N9-PKPMM-METADATA-MAPPING-ROLLBACK",
    "NEG-N9-PKPMM-METADATA-HANDOFF",
    "NEG-N9-PKPMM-METADATA-CORRUPTION",
    "NEG-N9-PKPMM-METADATA-ROLLBACK",
    "NEG-N9-PKPMM-GROWTH-INITIAL-GENERATION",
    "NEG-N9-PKPMM-GROWTH-FINAL-GENERATION",
    "NEG-N9-PKPMM-GROWTH-INITIAL-PAGES",
    "NEG-N9-PKPMM-GROWTH-FINAL-PAGES",
    "NEG-N9-PKPMM-GROWTH-FREE-CAPACITY",
    "NEG-N9-PKPMM-GROWTH-ALLOCATION-CAPACITY",
    "NEG-N9-PKPMM-GROWTH-SOURCE-CAPACITY",
    "NEG-N9-PKPMM-GROWTH-SCRUB-CAPACITY",
    "NEG-N9-PKPMM-GROWTH-RECLAIM-CAPACITY",
    "NEG-N9-PKPMM-GROWTH-RETIRED-GENERATION",
    "NEG-N9-PKPMM-GROWTH-RETIRED-PAGES",
    "NEG-N9-PKPMM-GROWTH-MAPPED-PAGES",
    "NEG-N9-PKPMM-GROWTH-PTE-WRITES",
    "NEG-N9-PKPMM-GROWTH-CHECKSUM",
    "NEG-N9-PKPMM-GROWTH-GUARDS",
    "NEG-N9-PKPMM-GROWTH-MAPPING-EVENTS",
    "NEG-N9-PKPMM-GROWTH-REVOCATION",
    "NEG-N9-PKPMM-GROWTH-INTEGRITY",
    "NEG-N9-PKPMM-GROWTH-ATOMIC",
    "NEG-N9-PKPMM-GROWTH-ROLLBACKS",
    "NEG-N9-PKPMM-GROWTH-RETIREMENT-FAILURES",
    "NEG-N9-PKPMM-GROWTH-RETIREMENT-RETRY",
    "NEG-N9-PKPMM-PRESSURE-CHECKS",
    "NEG-N9-PKPMM-PRESSURE-TRIGGERS",
    "NEG-N9-PKPMM-PRESSURE-AUTO-GROWTHS",
    "NEG-N9-PKPMM-PRESSURE-CYCLES",
    "NEG-N9-PKPMM-PRESSURE-SOFT-FALLBACKS",
    "NEG-N9-PKPMM-PRESSURE-HARD-REJECTIONS",
    "NEG-N9-PKPMM-PRESSURE-HEADROOM",
    "NEG-N9-PKPMM-GROWTH-WINDOW-BOUND",
    "NEG-N9-PKPMM-GROWTH-NEXT-LAYOUT",
    "NEG-N9-PKPMM-PRESSURE-PRE-EFFECT",
    "NEG-N9-PKPMM-GROWTH-CONCURRENCY",
    "NEG-N9-PKPMM-GROWTH-SMP",
    "NEG-N9-PKPMM-GROWTH-AUTHORITY",
    "NEG-N9-PKPMM-GROWTH-ACTIONS",
    "NEG-N9-PKPMM-GROWTH-PRODUCTION",
    "NEG-N9-PKPMM-RECLAIM-STAGE",
    "NEG-N9-PKPMM-RECLAIM-CLASS",
    "NEG-N9-PKPMM-RECLAIM-SEQUENCE",
    "NEG-N9-PKPMM-RECLAIM-SOURCE-RECORDS",
    "NEG-N9-PKPMM-RECLAIM-RANGES",
    "NEG-N9-PKPMM-RECLAIM-PAGES",
    "NEG-N9-PKPMM-RECLAIM-DMA-PAGES",
    "NEG-N9-PKPMM-RECLAIM-DMA32-PAGES",
    "NEG-N9-PKPMM-RECLAIM-NORMAL-PAGES",
    "NEG-N9-PKPMM-RECLAIM-PRE-EXTENTS",
    "NEG-N9-PKPMM-RECLAIM-POST-EXTENTS",
    "NEG-N9-PKPMM-RECLAIM-SCRUB-BYTES",
    "NEG-N9-PKPMM-RECLAIM-VERIFIED-BYTES",
    "NEG-N9-PKPMM-RECLAIM-RANGE-CHECKSUM",
    "NEG-N9-PKPMM-RECLAIM-RECEIPT-CHECKSUM",
    "NEG-N9-PKPMM-RECLAIM-IDEMPOTENT",
    "NEG-N9-PKPMM-RECLAIM-ACPI-HELD",
    "NEG-N9-PKPMM-RECLAIM-ACPI-EARLY",
    "NEG-N9-PKPMM-RECLAIM-RETAINED",
    "NEG-N9-PKPMM-RECLAIM-ATOMIC",
    "NEG-N9-PKPMM-RECLAIM-ROLLBACK",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-CONTRACT",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-PMM",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-RSDP",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-XSDT",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-XSDT-ENTRIES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-REQUIRED-MASK",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-FACP-BYTES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-APIC-BYTES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-HPET-BYTES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-MCFG-BYTES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-DESTINATION",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-PAGES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-BYTES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-COPIED-BYTES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-SOURCE-CHECKSUM",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-DESTINATION-CHECKSUM",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-REQUIRED-TABLES",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-COPY-VERIFIED",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-LIFECYCLE",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-RETAINED",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-AML",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-SMP",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-TARGET",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-PRODUCTION",
    "NEG-N9-PKPMM-ACPI-RECLAIM-STAGE",
    "NEG-N9-PKPMM-ACPI-RECLAIM-CLASS",
    "NEG-N9-PKPMM-ACPI-RECLAIM-SEQUENCE",
    "NEG-N9-PKPMM-ACPI-RECLAIM-SOURCE-RECORDS",
    "NEG-N9-PKPMM-ACPI-RECLAIM-RANGES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-PAGES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-DMA-PAGES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-DMA32-PAGES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-NORMAL-PAGES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-PRE-EXTENTS",
    "NEG-N9-PKPMM-ACPI-RECLAIM-POST-EXTENTS",
    "NEG-N9-PKPMM-ACPI-RECLAIM-SCRUB-BYTES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-VERIFIED-BYTES",
    "NEG-N9-PKPMM-ACPI-RECLAIM-RANGE-CHECKSUM",
    "NEG-N9-PKPMM-ACPI-RECLAIM-RECEIPT-CHECKSUM",
    "NEG-N9-PKPMM-ACPI-RECLAIM-IDEMPOTENT",
    "NEG-N9-PKPMM-ACPI-RECLAIM-SNAPSHOT-RETAINED",
    "NEG-N9-PKPMM-ACPI-RECLAIM-ATOMIC",
    "NEG-N9-PKPMM-ACPI-RECLAIM-ROLLBACK",
    "NEG-N9-PKPMM-ALLOCATION-COUNT",
    "NEG-N9-PKPMM-FREE-COUNT",
    "NEG-N9-PKPMM-START",
    "NEG-N9-PKPMM-FIRST-GENERATION",
    "NEG-N9-PKPMM-REUSE-GENERATION",
    "NEG-N9-PKPMM-ALLOCATION-RECEIPTS",
    "NEG-N9-PKPMM-RELEASE-RECEIPTS",
    "NEG-N9-PKPMM-SCRUB-PAGES",
    "NEG-N9-PKPMM-SCRUB-BYTES",
    "NEG-N9-PKPMM-VERIFIED-BYTES",
    "NEG-N9-PKPMM-STALE-PATTERN",
    "NEG-N9-PKPMM-STALE-ABSENT",
    "NEG-N9-PKPMM-DOUBLE-FREE",
    "NEG-N9-PKPMM-QUOTA",
    "NEG-N9-PKPMM-UNAVAILABLE",
    "NEG-N9-PKPMM-METADATA-POISON",
    "NEG-N9-PKPMM-COALESCE",
    "NEG-N9-PKPMM-ROLLBACK",
    "NEG-N9-PKPMM-MANAGED-TOTAL",
    "NEG-N9-PKPMM-ALLOCATED-RESIDUE",
    "NEG-N9-PKPMM-PHYSICAL-WRITE",
    "NEG-N9-PKPMM-PHYSICAL-READ",
    "NEG-N9-PKPMM-TEMPORARY-PTE-WRITE",
    "NEG-N9-PKPMM-BOOTSTRAP-INVLPG",
    "NEG-N9-PKPMM-ALIAS-REVOCATION",
    "NEG-N9-PKPMM-METADATA-RETAINED",
    "NEG-N9-PKPMM-LEDGER-GENERATION-RETAINED",
    "NEG-N9-PKPMM-ACPI-SNAPSHOT-RESULT-RETAINED",
    "NEG-N9-PKPMM-MAPPING",
    "NEG-N9-PKPMM-RECLAIM",
    "NEG-N9-PKPMM-ACPI-RECLAIM",
    "NEG-N9-PKPMM-CONCURRENCY",
    "NEG-N9-PKPMM-SMP",
    "NEG-N9-PKPMM-SIGNATURE",
    "NEG-N9-PKPMM-AUTHORITY",
    "NEG-N9-PKPMM-ACTION",
    "NEG-N9-PKPMM-PRODUCTION",
    "NEG-N9-PKPMM-TERMINAL",
    "NEG-N9-PKPMM-PBP1-OVERLAP",
    "NEG-N9-PKPMM-PBP1-SOURCE-KIND",
    "NEG-N9-PKPMM-PBP1-CORE-OWNERSHIP",
)

DEC = r"([0-9]+)"
HEX = r"(0x[0-9A-F]{16})"
EARLY = re.compile(
    r"^POOLEOS:KERNEL:PMM-EARLY PASS contract=(PKPMM7) selector=(8) bsp=(1) if=(0) "
    r"stack=(validated_by_wrapper) serial=(initialized)$"
)
STAGE = re.compile(r"^POOLEOS:KERNEL:PMM-STAGE PASS contract=(PKPMM7) stage=([1-5])$")
MAP = re.compile(
    rf"^POOLEOS:KERNEL:PMM-MAP PASS contract=(PKPMM7) entries={DEC} usable_pages={DEC} "
    rf"boot_reclaimable_pages={DEC} loader_reserved_pages={DEC} null_guard_pages={DEC}$"
)
ZONES = re.compile(
    rf"^POOLEOS:KERNEL:PMM-ZONES PASS contract=(PKPMM7) dma_source={DEC} dma_managed={DEC} "
    rf"dma32_source={DEC} dma32_managed={DEC} normal_source={DEC} normal_managed={DEC} "
    rf"extents={DEC} largest_dma={DEC} largest_dma32={DEC} largest_normal={DEC}$"
)
OWNERSHIP = re.compile(
    rf"^POOLEOS:KERNEL:PMM-OWNERSHIP PASS contract=(PKPMM7) kernel_base={HEX} kernel_pages={DEC} "
    rf"handoff_base={HEX} handoff_pages={DEC} root={HEX} protected=([01])$"
)
METADATA = re.compile(
    rf"^POOLEOS:KERNEL:PMM-METADATA PASS contract=(PKPMM7) pages={DEC} physical_start={HEX} "
    rf"virtual_start={HEX} generation={DEC} owner={DEC} manager_bytes={DEC} source_records={DEC} "
    rf"free_extents={DEC} allocation_records={DEC} receipt_records={DEC} handoff_checksum={HEX} "
    rf"final_checksum={HEX} guard_pages={DEC} mappings={DEC} pte_writes={DEC} release_excluded={DEC} "
    rf"release_rejected={DEC} integrity={DEC} reservation_rollbacks={DEC} mapping_rollbacks={DEC} "
    rf"handoff=(validated) corruption=(host_verified) rollback=(host_verified)$"
)
GROWTH = re.compile(
    rf"^POOLEOS:KERNEL:PMM-GROWTH PASS contract=(PKPMM7) initial_generation={DEC} "
    rf"final_generation={DEC} initial_pages={DEC} final_pages={DEC} free_capacity={DEC} "
    rf"allocation_capacity={DEC} source_capacity={DEC} scrub_capacity={DEC} reclaim_capacity={DEC} "
    rf"retired_generation={DEC} retired_pages={DEC} mapped_pages={DEC} pte_writes={DEC} checksum={HEX} "
    rf"guard_pages={DEC} mapping_events={DEC} revoked={DEC} integrity={DEC} atomic={DEC} rollbacks={DEC} "
    rf"retirement_failures={DEC} retirement_retry={DEC} pressure_checks={DEC} pressure_triggers={DEC} "
    rf"automatic_growths={DEC} pressure_cycles={DEC} soft_fallbacks={DEC} hard_rejections={DEC} "
    rf"growth_headroom_allocation={DEC} growth_headroom_scrub={DEC} window_capacity={DEC} next_pages={DEC} "
    rf"pre_effect=(host_verified) concurrency={DEC} smp={DEC} authority={DEC} actions={DEC} production={DEC}$"
)
RECLAIM = re.compile(
    rf"^POOLEOS:KERNEL:PMM-RECLAIM PASS contract=(PKPMM7) stage=(post_exit_boot_services) "
    rf"class=(boot_services) sequence={DEC} source_records={DEC} ranges={DEC} pages={DEC} "
    rf"dma_pages={DEC} dma32_pages={DEC} normal_pages={DEC} pre_extents={DEC} post_extents={DEC} "
    rf"scrub_bytes={DEC} verified_bytes={DEC} range_checksum={HEX} receipt_checksum={HEX} "
    rf"idempotent={DEC} acpi_held_pages={DEC} acpi_early_rejected={DEC} retained_excluded={DEC} "
    rf"atomic={DEC} rollback=(host_verified)$"
)
ACPI_SNAPSHOT = re.compile(
    rf"^POOLEOS:KERNEL:PMM-ACPI-SNAPSHOT PASS contract=(PKACPI1) pmm=(PKPMM7) "
    rf"rsdp={HEX} xsdt={HEX} xsdt_entries={DEC} required_mask={HEX} "
    rf"facp_bytes={DEC} apic_bytes={DEC} hpet_bytes={DEC} mcfg_bytes={DEC} "
    rf"snapshot={HEX} snapshot_pages={DEC} snapshot_bytes={DEC} copied_bytes={DEC} "
    rf"source_checksum={HEX} snapshot_checksum={HEX} required=(APIC,FACP,HPET,MCFG) "
    rf"copy_verified=(1) lifecycle_released=(1) retained=(1) aml=(0) smp=(0) target=(0) production=(0)$"
)
ACPI_RECLAIM = re.compile(
    rf"^POOLEOS:KERNEL:PMM-ACPI-RECLAIM PASS contract=(PKPMM7) "
    rf"stage=(acpi_tables_released) class=(acpi) sequence={DEC} source_records={DEC} "
    rf"ranges={DEC} pages={DEC} dma_pages={DEC} dma32_pages={DEC} normal_pages={DEC} "
    rf"pre_extents={DEC} post_extents={DEC} scrub_bytes={DEC} verified_bytes={DEC} "
    rf"range_checksum={HEX} receipt_checksum={HEX} idempotent=(1) snapshot_retained=(1) "
    rf"atomic=(1) rollback=(host_verified)$"
)
SCRUB = re.compile(
    rf"^POOLEOS:KERNEL:PMM-SCRUB PASS contract=(PKPMM7) allocations={DEC} frees={DEC} "
    rf"start={HEX} first_generation={DEC} reuse_generation={DEC} allocation_receipts={DEC} "
    rf"release_receipts={DEC} scrub_pages={DEC} scrub_bytes={DEC} verified_bytes={DEC} "
    rf"stale_pattern={HEX} stale_absent={DEC} double_free_rejected={DEC} quota_rejected={DEC} "
    rf"unavailable_rejected={DEC} metadata_poison={DEC} coalesces={DEC} rollback=(host_verified)$"
)
RESULT = re.compile(
    rf"^POOLEOS:KERNEL:PMM-RESULT PASS contract=(PKPMM7) profile=(qemu64_tier0) managed_pages={DEC} "
    rf"allocated_pages={DEC} physical_writes={DEC} physical_reads={DEC} temporary_pte_writes={DEC} "
    rf"bootstrap_invlpg={DEC} alias_revoked={DEC} metadata_retained={DEC} ledger_generation_retained={DEC} "
    rf"acpi_snapshot_retained={DEC} "
    rf"mappings=(temporary_single_page_plus_guarded_metadata_and_repeated_ledger_generations) reclaim={DEC} acpi_reclaim={DEC} "
    rf"concurrency={DEC} smp={DEC} signatures={DEC} authority={DEC} actions={DEC} production={DEC} "
    rf"terminal=(halt)$"
)


class KernelPhysicalMemoryError(ValueError):
    """Raised when PKPMM6 evidence violates the frozen growth contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelPhysicalMemoryError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelPhysicalMemoryError("binding path escapes repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "tier0_lock": file_binding(root / "specs/native-tier0-lock.json", root),
        "tier0_profile": file_binding(root / "specs/native-tier0-profile.json", root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "live_pbp1_memory_map_consumed_by_poolekernel": True,
        "firmware_source_kind_pairs_revalidated": True,
        "usable_only_initial_ownership_enforced": True,
        "kernel_handoff_and_root_loader_ownership_audited": True,
        "dma_dma32_normal_zone_accounting_enforced": True,
        "bounded_allocate_free_and_coalesce_exercised": True,
        "quota_and_double_free_rejection_exercised": True,
        "metadata_poison_state_exercised": True,
        "physical_page_contents_scrubbed": True,
        "allocation_scrub_before_handle_commit": True,
        "release_scrub_before_reuse": True,
        "full_page_readback_verified": True,
        "generation_and_sequence_bound_scrub_receipts": True,
        "stale_pattern_absent_after_exact_reuse": True,
        "scrub_failure_ownership_rollback_host_tested": True,
        "bootstrap_temporary_alias_revoked": True,
        "metadata_arena_guarded_mapping_retained": True,
        "metadata_bootstrap_ledgers_migrated": True,
        "metadata_generation_owned_ledgers_active": True,
        "metadata_all_ledger_capacities_expanded": True,
        "metadata_alternate_guarded_windows_enforced": True,
        "metadata_old_generation_revoked_scrubbed_retired": True,
        "metadata_growth_precommit_rollback_host_tested": True,
        "metadata_retirement_failure_recovery_host_tested": True,
        "metadata_pressure_capacity_checked_before_automatic_operations": True,
        "metadata_pressure_repeated_multi_generation_growth_exercised": True,
        "metadata_pressure_retry_headroom_enforced": True,
        "metadata_bounded_window_soft_fallback_exercised": True,
        "metadata_bounded_window_hard_rejection_pre_effect_host_tested": True,
        "metadata_logical_integrity_seal_enforced": True,
        "metadata_handoff_and_mapping_rollback_host_tested": True,
        "metadata_release_exclusion_enforced": True,
        "boot_services_reclaim_lifecycle_enforced": True,
        "boot_services_reclaim_scrubbed_and_activated": True,
        "reclaim_capacity_and_retained_range_preflight_enforced": True,
        "reclaim_atomicity_rollback_and_idempotence_host_tested": True,
        "generation_bound_reclaim_receipt_enforced": True,
        "acpi_reclaim_timing_enforced": True,
        "acpi20_rsdp_handoff_consumed": True,
        "acpi_xsdt_and_required_tables_validated": True,
        "acpi_required_tables_copied_and_readback_verified": True,
        "acpi_snapshot_retained_and_release_excluded": True,
        "acpi_release_requires_opaque_consumer_evidence": True,
        "acpi_reclaim_activated": True,
        "complete_direct_map_or_address_space_claimed": False,
        "concurrent_or_smp_allocator_qualified": False,
        "n9_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if (contract.get("contract_id"), contract.get("selected_move_id")) != (CONTRACT_ID, SELECTED_MOVE_ID):
        errors.append("PKPMM7 contract identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, "qemu64", True):
        errors.append("PKPMM7 development profile changed")
    limits = contract.get("limits", {})
    if not isinstance(limits, dict) or tuple(
        limits.get(key)
        for key in (
            "memory_entries",
            "free_extents",
            "allocations",
            "scrub_receipts",
            "reclaim_receipts",
            "quota_pages",
            "metadata_arena_pages",
            "metadata_guard_pages",
        )
    ) != (256, 256, 32, 16, 2, 64, 5, 2):
        errors.append("PKPMM7 bounded capacities changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKPMM7 hostile-control inventory changed")
    metadata_arena = contract.get("metadata_arena", {})
    if not isinstance(metadata_arena, dict) or tuple(
        metadata_arena.get(key)
        for key in ("owner_id", "manager_byte_count", "page_count", "guard_page_count")
    ) != (METADATA_OWNER, METADATA_MANAGER_BYTES, METADATA_ARENA_PAGE_COUNT, METADATA_GUARD_PAGE_COUNT):
        errors.append("PKPMM7 metadata arena shape changed")
    ledger_generations = contract.get("ledger_generations", {})
    if (
        not isinstance(ledger_generations, dict)
        or ledger_generations.get("initial_capacities")
        != {"free_extents": 256, "allocations": 32, "source_records": 256, "scrub_receipts": 16, "reclaim_receipts": 2}
        or ledger_generations.get("final_capacities")
        != {"free_extents": 2048, "allocations": 256, "source_records": 2048, "scrub_receipts": 128, "reclaim_receipts": 16}
        or ledger_generations.get("generation_capacities")
        != [
            {"pages": 4, "free_extents": 256, "allocations": 32, "source_records": 256, "scrub_receipts": 16, "reclaim_receipts": 2},
            {"pages": 8, "free_extents": 512, "allocations": 64, "source_records": 512, "scrub_receipts": 32, "reclaim_receipts": 4},
            {"pages": 15, "free_extents": 1024, "allocations": 128, "source_records": 1024, "scrub_receipts": 64, "reclaim_receipts": 8},
            {"pages": 29, "free_extents": 2048, "allocations": 256, "source_records": 2048, "scrub_receipts": 128, "reclaim_receipts": 16},
        ]
        or tuple(
            ledger_generations.get(key)
            for key in (
                "live_generation_events", "live_retired_generations", "live_retired_pages",
                "live_mapping_pte_writes", "concurrency_qualified"
            )
        )
        != (4, 3, LEDGER_RETIRED_PAGE_COUNT, LEDGER_PTE_WRITES, False)
        or ledger_generations.get("pressure_policy", {}).get("check_count")
        != LEDGER_PRESSURE_COUNTS[0]
        or ledger_generations.get("pressure_policy", {}).get("trigger_count")
        != LEDGER_PRESSURE_COUNTS[1]
        or ledger_generations.get("pressure_policy", {}).get("automatic_growth_count")
        != LEDGER_PRESSURE_COUNTS[2]
        or ledger_generations.get("pressure_policy", {}).get("successful_pressure_cycles")
        != LEDGER_PRESSURE_COUNTS[3]
        or ledger_generations.get("pressure_policy", {}).get("soft_window_fallback_count")
        != LEDGER_PRESSURE_COUNTS[4]
        or ledger_generations.get("pressure_policy", {}).get("hard_window_rejection_count")
        != LEDGER_PRESSURE_COUNTS[5]
    ):
        errors.append("PKPMM7 ledger-generation contract changed")
    reclaim = contract.get("reclaim_policy", {})
    if not isinstance(reclaim, dict) or tuple(
        reclaim.get(key)
        for key in (
            "boot_services_source_kind",
            "acpi_source_kind",
            "boot_services_required_stage",
            "acpi_required_stage",
            "live_boot_reclaim_pages",
            "live_acpi_pages_held_before_release",
            "live_acpi_pages_reclaimed",
            "live_acpi_positive_activation",
        )
    ) != (2, 5, "post_exit_boot_services", "acpi_tables_released", 11250, 11, 11, True):
        errors.append("PKPMM7 reclaim policy changed")
    acpi_consumer = contract.get("acpi_consumer", {})
    if not isinstance(acpi_consumer, dict) or tuple(
        acpi_consumer.get(key)
        for key in (
            "contract_id",
            "source_alignment_bytes",
            "required_tables",
            "snapshot_maximum_pages",
            "live_snapshot_pages",
            "live_snapshot_bytes",
            "live_copied_bytes",
        )
    ) != (
        ACPI_CONTRACT_ID,
        4,
        ["APIC", "FACP", "HPET", "MCFG"],
        64,
        ACPI_SNAPSHOT_PAGE_COUNT,
        ACPI_SNAPSHOT_BYTE_COUNT,
        ACPI_SNAPSHOT_COPIED_BYTES,
    ):
        errors.append("PKACPI1 consumer contract changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKPMM7 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKPMM7 contract overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    errors.extend(contract_errors(read_json(root / CONTRACT_RELATIVE), root))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKPMM6 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key) for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKPMM6 exact two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKPMM6 hostile-control evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKPMM6 readiness claims changed")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("PKPMM6 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelPhysicalMemoryError(f"PKPMM6 {name} marker violates its contract: {marker!r}")
    return match


def _dec(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 10)


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def _validate_prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelPhysicalMemoryError("PKPMM6 transfer selector changed")
    baseline = [
        *markers[:BOOT_TRANSFER_MARKER_COUNT],
        *markers[
            COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START
            + COMMON_KERNEL_MARKER_COUNT
        ],
    ]
    baseline[23] = re.sub(r"trap_scenario=[0-9]", "trap_scenario=0", baseline[23], count=1)
    terminal = (
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers([*baseline, terminal])
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelPhysicalMemoryError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelPhysicalMemoryError(f"expected {MARKER_COUNT} PKPMM7 markers, observed {len(markers)}")
    prefix = _validate_prefix(markers)
    early_match = _match(EARLY, markers[25], "early-entry")
    stages = [_match(STAGE, markers[26 + index], "stage") for index in range(5)]
    if [int(item.group(2)) for item in stages] != [1, 2, 3, 4, 5]:
        raise KernelPhysicalMemoryError("PKPMM7 stage order changed")
    map_match = _match(MAP, markers[35], "map")
    zone_match = _match(ZONES, markers[36], "zones")
    owner_match = _match(OWNERSHIP, markers[37], "ownership")
    metadata_match = _match(METADATA, markers[38], "metadata")
    growth_match = _match(GROWTH, markers[39], "growth")
    reclaim_match = _match(RECLAIM, markers[40], "reclaim")
    acpi_snapshot_match = _match(ACPI_SNAPSHOT, markers[41], "acpi-snapshot")
    acpi_reclaim_match = _match(ACPI_RECLAIM, markers[42], "acpi-reclaim")
    scrub_match = _match(SCRUB, markers[43], "scrub")
    result_match = _match(RESULT, markers[44], "result")
    map_summary = {
        "entries": _dec(map_match, 2),
        "usable_pages": _dec(map_match, 3),
        "boot_reclaimable_pages": _dec(map_match, 4),
        "loader_reserved_pages": _dec(map_match, 5),
        "null_guard_pages": _dec(map_match, 6),
    }
    zones = {
        "dma_source": _dec(zone_match, 2),
        "dma_managed": _dec(zone_match, 3),
        "dma32_source": _dec(zone_match, 4),
        "dma32_managed": _dec(zone_match, 5),
        "normal_source": _dec(zone_match, 6),
        "normal_managed": _dec(zone_match, 7),
        "extents": _dec(zone_match, 8),
        "largest_dma": _dec(zone_match, 9),
        "largest_dma32": _dec(zone_match, 10),
        "largest_normal": _dec(zone_match, 11),
    }
    ownership = {
        "kernel_base": _hex(owner_match, 2),
        "kernel_pages": _dec(owner_match, 3),
        "handoff_base": _hex(owner_match, 4),
        "handoff_pages": _dec(owner_match, 5),
        "root": _hex(owner_match, 6),
        "protected": _dec(owner_match, 7),
    }
    metadata = {
        "pages": _dec(metadata_match, 2),
        "physical_start": _hex(metadata_match, 3),
        "virtual_start": _hex(metadata_match, 4),
        "generation": _dec(metadata_match, 5),
        "owner": _dec(metadata_match, 6),
        "manager_bytes": _dec(metadata_match, 7),
        "source_records": _dec(metadata_match, 8),
        "free_extents": _dec(metadata_match, 9),
        "allocation_records": _dec(metadata_match, 10),
        "receipt_records": _dec(metadata_match, 11),
        "handoff_checksum": _hex(metadata_match, 12),
        "final_checksum": _hex(metadata_match, 13),
        "guard_pages": _dec(metadata_match, 14),
        "mappings": _dec(metadata_match, 15),
        "pte_writes": _dec(metadata_match, 16),
        "release_excluded": _dec(metadata_match, 17),
        "release_rejected": _dec(metadata_match, 18),
        "integrity": _dec(metadata_match, 19),
        "reservation_rollbacks": _dec(metadata_match, 20),
        "mapping_rollbacks": _dec(metadata_match, 21),
        "handoff": metadata_match.group(22),
        "corruption": metadata_match.group(23),
        "rollback": metadata_match.group(24),
    }
    growth = {
        "initial_generation": _dec(growth_match, 2),
        "final_generation": _dec(growth_match, 3),
        "initial_pages": _dec(growth_match, 4),
        "final_pages": _dec(growth_match, 5),
        "free_capacity": _dec(growth_match, 6),
        "allocation_capacity": _dec(growth_match, 7),
        "source_capacity": _dec(growth_match, 8),
        "scrub_capacity": _dec(growth_match, 9),
        "reclaim_capacity": _dec(growth_match, 10),
        "retired_generation": _dec(growth_match, 11),
        "retired_pages": _dec(growth_match, 12),
        "mapped_pages": _dec(growth_match, 13),
        "pte_writes": _dec(growth_match, 14),
        "checksum": _hex(growth_match, 15),
        "guard_pages": _dec(growth_match, 16),
        "mapping_events": _dec(growth_match, 17),
        "revoked": _dec(growth_match, 18),
        "integrity": _dec(growth_match, 19),
        "atomic": _dec(growth_match, 20),
        "rollbacks": _dec(growth_match, 21),
        "retirement_failures": _dec(growth_match, 22),
        "retirement_retry": _dec(growth_match, 23),
        "pressure_checks": _dec(growth_match, 24),
        "pressure_triggers": _dec(growth_match, 25),
        "automatic_growths": _dec(growth_match, 26),
        "pressure_cycles": _dec(growth_match, 27),
        "soft_fallbacks": _dec(growth_match, 28),
        "hard_rejections": _dec(growth_match, 29),
        "growth_headroom_allocation": _dec(growth_match, 30),
        "growth_headroom_scrub": _dec(growth_match, 31),
        "window_capacity": _dec(growth_match, 32),
        "next_pages": _dec(growth_match, 33),
        "pre_effect": growth_match.group(34),
        "concurrency": _dec(growth_match, 35),
        "smp": _dec(growth_match, 36),
        "authority": _dec(growth_match, 37),
        "actions": _dec(growth_match, 38),
        "production": _dec(growth_match, 39),
    }
    reclaim = {
        "stage": reclaim_match.group(2),
        "class": reclaim_match.group(3),
        "sequence": _dec(reclaim_match, 4),
        "source_records": _dec(reclaim_match, 5),
        "ranges": _dec(reclaim_match, 6),
        "pages": _dec(reclaim_match, 7),
        "dma_pages": _dec(reclaim_match, 8),
        "dma32_pages": _dec(reclaim_match, 9),
        "normal_pages": _dec(reclaim_match, 10),
        "pre_extents": _dec(reclaim_match, 11),
        "post_extents": _dec(reclaim_match, 12),
        "scrub_bytes": _dec(reclaim_match, 13),
        "verified_bytes": _dec(reclaim_match, 14),
        "range_checksum": _hex(reclaim_match, 15),
        "receipt_checksum": _hex(reclaim_match, 16),
        "idempotent": _dec(reclaim_match, 17),
        "acpi_held_pages": _dec(reclaim_match, 18),
        "acpi_early_rejected": _dec(reclaim_match, 19),
        "retained_excluded": _dec(reclaim_match, 20),
        "atomic": _dec(reclaim_match, 21),
        "rollback": reclaim_match.group(22),
    }
    acpi_snapshot = {
        "contract_id": acpi_snapshot_match.group(1),
        "pmm_contract_id": acpi_snapshot_match.group(2),
        "rsdp": _hex(acpi_snapshot_match, 3),
        "xsdt": _hex(acpi_snapshot_match, 4),
        "xsdt_entries": _dec(acpi_snapshot_match, 5),
        "required_mask": _hex(acpi_snapshot_match, 6),
        "facp_bytes": _dec(acpi_snapshot_match, 7),
        "apic_bytes": _dec(acpi_snapshot_match, 8),
        "hpet_bytes": _dec(acpi_snapshot_match, 9),
        "mcfg_bytes": _dec(acpi_snapshot_match, 10),
        "snapshot": _hex(acpi_snapshot_match, 11),
        "snapshot_pages": _dec(acpi_snapshot_match, 12),
        "snapshot_bytes": _dec(acpi_snapshot_match, 13),
        "copied_bytes": _dec(acpi_snapshot_match, 14),
        "source_checksum": _hex(acpi_snapshot_match, 15),
        "snapshot_checksum": _hex(acpi_snapshot_match, 16),
        "required": acpi_snapshot_match.group(17),
        "copy_verified": _dec(acpi_snapshot_match, 18),
        "lifecycle_released": _dec(acpi_snapshot_match, 19),
        "retained": _dec(acpi_snapshot_match, 20),
        "aml": _dec(acpi_snapshot_match, 21),
        "smp": _dec(acpi_snapshot_match, 22),
        "target": _dec(acpi_snapshot_match, 23),
        "production": _dec(acpi_snapshot_match, 24),
    }
    acpi_reclaim = {
        "stage": acpi_reclaim_match.group(2),
        "class": acpi_reclaim_match.group(3),
        "sequence": _dec(acpi_reclaim_match, 4),
        "source_records": _dec(acpi_reclaim_match, 5),
        "ranges": _dec(acpi_reclaim_match, 6),
        "pages": _dec(acpi_reclaim_match, 7),
        "dma_pages": _dec(acpi_reclaim_match, 8),
        "dma32_pages": _dec(acpi_reclaim_match, 9),
        "normal_pages": _dec(acpi_reclaim_match, 10),
        "pre_extents": _dec(acpi_reclaim_match, 11),
        "post_extents": _dec(acpi_reclaim_match, 12),
        "scrub_bytes": _dec(acpi_reclaim_match, 13),
        "verified_bytes": _dec(acpi_reclaim_match, 14),
        "range_checksum": _hex(acpi_reclaim_match, 15),
        "receipt_checksum": _hex(acpi_reclaim_match, 16),
        "idempotent": _dec(acpi_reclaim_match, 17),
        "snapshot_retained": _dec(acpi_reclaim_match, 18),
        "atomic": _dec(acpi_reclaim_match, 19),
        "rollback": acpi_reclaim_match.group(20),
    }
    scrub = {
        "allocations": _dec(scrub_match, 2),
        "frees": _dec(scrub_match, 3),
        "start": _hex(scrub_match, 4),
        "first_generation": _dec(scrub_match, 5),
        "reuse_generation": _dec(scrub_match, 6),
        "allocation_receipts": _dec(scrub_match, 7),
        "release_receipts": _dec(scrub_match, 8),
        "scrub_pages": _dec(scrub_match, 9),
        "scrub_bytes": _dec(scrub_match, 10),
        "verified_bytes": _dec(scrub_match, 11),
        "stale_pattern": _hex(scrub_match, 12),
        "stale_absent": _dec(scrub_match, 13),
        "double_free_rejected": _dec(scrub_match, 14),
        "quota_rejected": _dec(scrub_match, 15),
        "unavailable_rejected": _dec(scrub_match, 16),
        "metadata_poison": _dec(scrub_match, 17),
        "coalesces": _dec(scrub_match, 18),
        "rollback": scrub_match.group(19),
    }
    result = {
        "managed_pages": _dec(result_match, 3),
        "allocated_pages": _dec(result_match, 4),
        "physical_writes": _dec(result_match, 5),
        "physical_reads": _dec(result_match, 6),
        "temporary_pte_writes": _dec(result_match, 7),
        "bootstrap_invlpg": _dec(result_match, 8),
        "alias_revoked": _dec(result_match, 9),
        "metadata_retained": _dec(result_match, 10),
        "ledger_generation_retained": _dec(result_match, 11),
        "acpi_snapshot_retained": _dec(result_match, 12),
        "mappings": result_match.group(13),
        "reclaim": _dec(result_match, 14),
        "acpi_reclaim": _dec(result_match, 15),
        "concurrency": _dec(result_match, 16),
        "smp": _dec(result_match, 17),
        "signatures": _dec(result_match, 18),
        "authority": _dec(result_match, 19),
        "actions": _dec(result_match, 20),
        "production": _dec(result_match, 21),
        "terminal": result_match.group(22),
    }
    if (
        map_summary["entries"] == 0
        or map_summary["entries"] > MAX_MEMORY_ENTRIES
        or map_summary["entries"]
        != prefix["boot_prefix"]["pbp1"]["memory_entry_count"]
    ):
        raise KernelPhysicalMemoryError("PKPMM6 memory-entry bound changed")
    if map_summary["null_guard_pages"] != 1 or map_summary["usable_pages"] != sum(
        zones[key] for key in ("dma_source", "dma32_source", "normal_source")
    ):
        raise KernelPhysicalMemoryError("PKPMM6 source accounting changed")
    if map_summary["usable_pages"] - 1 != sum(
        zones[key] for key in ("dma_managed", "dma32_managed", "normal_managed")
    ):
        raise KernelPhysicalMemoryError("PKPMM6 managed accounting changed")
    if ownership["protected"] != 1 or any(value % PAGE_BYTES for value in (
        ownership["kernel_base"], ownership["handoff_base"], ownership["root"]
    )):
        raise KernelPhysicalMemoryError("PKPMM6 protected ownership marker changed")
    exact_metadata = (
        metadata["pages"],
        metadata["virtual_start"],
        metadata["generation"],
        metadata["owner"],
        metadata["manager_bytes"],
        metadata["source_records"],
        metadata["free_extents"],
        metadata["allocation_records"],
        metadata["receipt_records"],
        metadata["guard_pages"],
        metadata["mappings"],
        metadata["pte_writes"],
        metadata["release_excluded"],
        metadata["release_rejected"],
        metadata["integrity"],
        metadata["reservation_rollbacks"],
        metadata["mapping_rollbacks"],
        metadata["handoff"],
        metadata["corruption"],
        metadata["rollback"],
    )
    if exact_metadata != (
        METADATA_ARENA_PAGE_COUNT,
        METADATA_MAP_START,
        1,
        METADATA_OWNER,
        METADATA_MANAGER_BYTES,
        map_summary["entries"],
        zones["extents"],
        1,
        1,
        METADATA_GUARD_PAGE_COUNT,
        METADATA_ARENA_PAGE_COUNT,
        METADATA_PTE_WRITES,
        1,
        1,
        1,
        0,
        0,
        "validated",
        "host_verified",
        "host_verified",
    ):
        raise KernelPhysicalMemoryError("PKPMM6 metadata arena boundary changed")
    if (
        metadata["physical_start"] % PAGE_BYTES
        or not DMA_END <= metadata["physical_start"] < DMA32_END
        or metadata["handoff_checksum"] == 0
        or metadata["final_checksum"] == 0
        or metadata["handoff_checksum"] == metadata["final_checksum"]
    ):
        raise KernelPhysicalMemoryError("PKPMM6 metadata handoff evidence changed")
    exact_growth = (
        growth["initial_generation"],
        growth["final_generation"],
        growth["initial_pages"],
        growth["final_pages"],
        growth["free_capacity"],
        growth["allocation_capacity"],
        growth["source_capacity"],
        growth["scrub_capacity"],
        growth["reclaim_capacity"],
        growth["retired_generation"],
        growth["retired_pages"],
        growth["mapped_pages"],
        growth["pte_writes"],
        growth["guard_pages"],
        growth["mapping_events"],
        growth["revoked"],
        growth["integrity"],
        growth["atomic"],
        growth["rollbacks"],
        growth["retirement_failures"],
        growth["retirement_retry"],
        growth["pressure_checks"],
        growth["pressure_triggers"],
        growth["automatic_growths"],
        growth["pressure_cycles"],
        growth["soft_fallbacks"],
        growth["hard_rejections"],
        growth["growth_headroom_allocation"],
        growth["growth_headroom_scrub"],
        growth["window_capacity"],
        growth["next_pages"],
        growth["pre_effect"],
        growth["concurrency"],
        growth["smp"],
        growth["authority"],
        growth["actions"],
        growth["production"],
    )
    expected_growth = (
        2, 33, LEDGER_INITIAL_PAGE_COUNT, LEDGER_FINAL_PAGE_COUNT,
        *LEDGER_FINAL_CAPACITIES, 17, 15,
        LEDGER_FINAL_PAGE_COUNT, LEDGER_PTE_WRITES, 4, 4, 3, 1, 1,
        0, 0, 0, *LEDGER_PRESSURE_COUNTS, *LEDGER_GROWTH_HEADROOM,
        LEDGER_WINDOW_PAGE_CAPACITY, LEDGER_NEXT_PAGE_COUNT, "host_verified",
        0, 0, 0, 0, 0,
    )
    if exact_growth != expected_growth or growth["checksum"] == 0:
        raise KernelPhysicalMemoryError(
            "PKPMM6 ledger growth boundary changed: "
            f"observed={exact_growth!r}; expected={expected_growth!r}; "
            f"checksum={growth['checksum']}"
        )
    exact_reclaim = (
        reclaim["stage"],
        reclaim["class"],
        reclaim["sequence"],
        reclaim["source_records"],
        reclaim["ranges"],
        reclaim["pages"],
        reclaim["dma_pages"],
        reclaim["dma32_pages"],
        reclaim["normal_pages"],
        reclaim["pre_extents"],
        reclaim["post_extents"],
        reclaim["scrub_bytes"],
        reclaim["verified_bytes"],
        reclaim["range_checksum"],
        reclaim["receipt_checksum"],
        reclaim["idempotent"],
        reclaim["acpi_held_pages"],
        reclaim["acpi_early_rejected"],
        reclaim["retained_excluded"],
        reclaim["atomic"],
        reclaim["rollback"],
    )
    if exact_reclaim != (
        "post_exit_boot_services",
        "boot_services",
        1,
        BOOT_RECLAIM_SOURCE_RECORD_COUNT,
        BOOT_RECLAIM_RANGE_COUNT,
        BOOT_RECLAIM_PAGE_COUNT,
        *BOOT_RECLAIM_PAGES_BY_ZONE,
        13,
        15,
        RECLAIM_SCRUB_BYTES,
        RECLAIM_SCRUB_BYTES,
        BOOT_RECLAIM_RANGE_CHECKSUM,
        BOOT_RECLAIM_RECEIPT_CHECKSUM,
        1,
        ACPI_HELD_PAGE_COUNT,
        1,
        1,
        1,
        "host_verified",
    ):
        raise KernelPhysicalMemoryError("PKPMM7 held-class reclaim boundary changed")
    xsdt_bytes = 36 + acpi_snapshot["xsdt_entries"] * 8
    snapshot_cursor = (40 + xsdt_bytes + 7) & ~7
    for byte_count in (
        acpi_snapshot["apic_bytes"],
        acpi_snapshot["facp_bytes"],
        acpi_snapshot["hpet_bytes"],
        acpi_snapshot["mcfg_bytes"],
    ):
        snapshot_cursor = (snapshot_cursor + byte_count + 7) & ~7
    copied_bytes = (
        36
        + xsdt_bytes
        + acpi_snapshot["apic_bytes"]
        + acpi_snapshot["facp_bytes"]
        + acpi_snapshot["hpet_bytes"]
        + acpi_snapshot["mcfg_bytes"]
    )
    if (
        acpi_snapshot["contract_id"] != ACPI_CONTRACT_ID
        or acpi_snapshot["pmm_contract_id"] != CONTRACT_ID
        or acpi_snapshot["rsdp"] != ACPI_RSDP_ADDRESS
        or acpi_snapshot["xsdt"] != ACPI_XSDT_ADDRESS
        or acpi_snapshot["xsdt_entries"] != ACPI_XSDT_ENTRY_COUNT
        or acpi_snapshot["required_mask"] != 0x0F
        or (
            acpi_snapshot["apic_bytes"],
            acpi_snapshot["facp_bytes"],
            acpi_snapshot["hpet_bytes"],
            acpi_snapshot["mcfg_bytes"],
        )
        != ACPI_REQUIRED_TABLE_BYTES
        or any(
            acpi_snapshot[key] > 64 * 1024
            for key in ("apic_bytes", "facp_bytes", "hpet_bytes", "mcfg_bytes")
        )
        or acpi_snapshot["snapshot"] % PAGE_BYTES
        or not DMA_END <= acpi_snapshot["snapshot"] < DMA32_END
        or acpi_snapshot["snapshot_bytes"] != snapshot_cursor
        or acpi_snapshot["copied_bytes"] != copied_bytes
        or acpi_snapshot["snapshot_pages"]
        != (acpi_snapshot["snapshot_bytes"] + PAGE_BYTES - 1) // PAGE_BYTES
        or acpi_snapshot["snapshot_pages"] != ACPI_SNAPSHOT_PAGE_COUNT
        or acpi_snapshot["snapshot_bytes"] != ACPI_SNAPSHOT_BYTE_COUNT
        or acpi_snapshot["copied_bytes"] != ACPI_SNAPSHOT_COPIED_BYTES
        or acpi_snapshot["source_checksum"] == 0
        or acpi_snapshot["snapshot_checksum"] == 0
        or acpi_snapshot["required"] != "APIC,FACP,HPET,MCFG"
        or any(
            acpi_snapshot[key] != expected
            for key, expected in (
                ("copy_verified", 1),
                ("lifecycle_released", 1),
                ("retained", 1),
                ("aml", 0),
                ("smp", 0),
                ("target", 0),
                ("production", 0),
            )
        )
    ):
        raise KernelPhysicalMemoryError("PKACPI1 retained snapshot boundary changed")
    if (
        acpi_reclaim["stage"] != "acpi_tables_released"
        or acpi_reclaim["class"] != "acpi"
        or acpi_reclaim["sequence"] != 2
        or acpi_reclaim["source_records"] != ACPI_RECLAIM_SOURCE_RECORD_COUNT
        or acpi_reclaim["ranges"] != ACPI_RECLAIM_RANGE_COUNT
        or acpi_reclaim["pages"] != reclaim["acpi_held_pages"]
        or acpi_reclaim["pages"]
        != acpi_reclaim["dma_pages"]
        + acpi_reclaim["dma32_pages"]
        + acpi_reclaim["normal_pages"]
        or acpi_reclaim["pre_extents"] != reclaim["post_extents"]
        or acpi_reclaim["pages"] != ACPI_RECLAIM_PAGE_COUNT
        or (
            acpi_reclaim["dma_pages"],
            acpi_reclaim["dma32_pages"],
            acpi_reclaim["normal_pages"],
        )
        != ACPI_RECLAIM_PAGES_BY_ZONE
        or acpi_reclaim["post_extents"] != 15
        or acpi_reclaim["scrub_bytes"] != acpi_reclaim["pages"] * PAGE_BYTES
        or acpi_reclaim["verified_bytes"] != acpi_reclaim["scrub_bytes"]
        or acpi_reclaim["range_checksum"] != ACPI_RECLAIM_RANGE_CHECKSUM
        or acpi_reclaim["receipt_checksum"] != ACPI_RECLAIM_RECEIPT_CHECKSUM
        or acpi_reclaim["idempotent"] != 1
        or acpi_reclaim["snapshot_retained"] != 1
        or acpi_reclaim["atomic"] != 1
        or acpi_reclaim["rollback"] != "host_verified"
    ):
        raise KernelPhysicalMemoryError("PKPMM7 ACPI reclaim boundary changed")
    exact_scrub = (
        scrub["allocations"],
        scrub["frees"],
        scrub["first_generation"],
        scrub["reuse_generation"],
        scrub["allocation_receipts"],
        scrub["release_receipts"],
        scrub["scrub_pages"],
        scrub["scrub_bytes"],
        scrub["verified_bytes"],
        scrub["stale_pattern"],
        scrub["stale_absent"],
        scrub["double_free_rejected"],
        scrub["quota_rejected"],
        scrub["unavailable_rejected"],
        scrub["metadata_poison"],
        scrub["coalesces"],
        scrub["rollback"],
    )
    expected_scrub_pages = (
        211
        + acpi_snapshot["snapshot_pages"]
        + reclaim["pages"]
        + acpi_reclaim["pages"]
    )
    if (
        exact_scrub[:6] != (66, 63, 3, 4, 2, 2)
        or scrub["scrub_pages"] != expected_scrub_pages
        or scrub["scrub_bytes"] != expected_scrub_pages * PAGE_BYTES
        or scrub["verified_bytes"] != scrub["scrub_bytes"]
        or exact_scrub[9:15] != (STALE_PATTERN, 1, 1, 1, 1, 63)
        or scrub["coalesces"] < 72
        or scrub["rollback"] != "host_verified"
    ):
        raise KernelPhysicalMemoryError("PKPMM7 bounded scrub exercise changed")
    exact_result = (
        result["managed_pages"],
        result["allocated_pages"],
        PHYSICAL_WRITES,
        PHYSICAL_READS,
        TEMPORARY_PTE_WRITES,
        BOOTSTRAP_INVALIDATIONS,
        result["alias_revoked"],
        result["metadata_retained"],
        result["ledger_generation_retained"],
        result["acpi_snapshot_retained"],
        result["mappings"],
        result["reclaim"],
        result["acpi_reclaim"],
        result["concurrency"],
        result["smp"],
        result["signatures"],
        result["authority"],
        result["actions"],
        result["production"],
        result["terminal"],
    )
    expected_result = (
        map_summary["usable_pages"] - 1 + reclaim["pages"] + acpi_reclaim["pages"],
        METADATA_ARENA_PAGE_COUNT
        + LEDGER_FINAL_PAGE_COUNT
        + acpi_snapshot["snapshot_pages"],
        result["physical_writes"],
        result["physical_reads"],
        result["temporary_pte_writes"],
        result["bootstrap_invlpg"],
        1,
        1,
        1,
        1,
        "temporary_single_page_plus_guarded_metadata_and_repeated_ledger_generations",
        1, 1, 0, 0, 0, 0, 0, 0, "halt",
    )
    if (
        exact_result != expected_result
        or result["physical_writes"] <= scrub["scrub_pages"] * (PAGE_BYTES // 8)
        or result["physical_reads"] <= result["physical_writes"]
        or result["temporary_pte_writes"] != result["bootstrap_invlpg"]
        or result["temporary_pte_writes"] <= 0
    ):
        raise KernelPhysicalMemoryError(
            "PKPMM7 result boundary changed: "
            f"observed={exact_result!r}; expected={expected_result!r}"
        )
    return {
        "transfer_prefix": prefix,
        "early": {
            "selector": int(early_match.group(2)),
            "bsp": int(early_match.group(3)),
            "interrupt_flag": int(early_match.group(4)),
            "stack": early_match.group(5),
            "serial": early_match.group(6),
        },
        "stages": [1, 2, 3, 4, 5],
        "map": map_summary,
        "zones": zones,
        "ownership": ownership,
        "metadata": metadata,
        "growth": growth,
        "reclaim": reclaim,
        "acpi_snapshot": acpi_snapshot,
        "acpi_reclaim": acpi_reclaim,
        "scrub": scrub,
        "result": result,
        "marker_count": len(markers),
    }


def _zone_index(address: int) -> int:
    if address < DMA_END:
        return 0
    if address < DMA32_END:
        return 1
    return 2


def _source_matches(source: int, kind: int) -> bool:
    return (source, kind) in {
        (0, 0), (13, 0), (15, 0), (1, 10), (2, 10), (3, 2), (4, 2),
        (5, 3), (6, 4), (7, 1), (8, 9), (9, 5), (10, 6), (11, 7),
        (12, 7), (14, 8),
    }


def _fnv_u64(state: int, value: int) -> int:
    for byte in value.to_bytes(8, "little"):
        state ^= byte
        state = (state * 0x00000100000001B3) & ((1 << 64) - 1)
    return state


def derive_memory_summary(transcript: dict[str, Any]) -> dict[str, Any]:
    entries = transcript.get("memory_entries")
    core = transcript.get("core")
    if not isinstance(entries, list) or not isinstance(core, dict) or not 1 <= len(entries) <= MAX_MEMORY_ENTRIES:
        raise KernelPhysicalMemoryError("PKPMM6 PBP1 memory map is missing or out of bounds")
    kind_pages = [0] * 12
    source = [0, 0, 0]
    managed = [0, 0, 0]
    extents: list[tuple[int, int, int]] = []
    previous_end = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise KernelPhysicalMemoryError("PKPMM6 PBP1 memory entry is not an object")
        start = int(str(entry["physical_start"]), 16)
        pages = int(entry["page_count"])
        kind = int(entry["kind"])
        source_type = int(entry["source_type"])
        end = start + pages * PAGE_BYTES
        if start % PAGE_BYTES or pages <= 0 or not 0 <= kind < 12 or end <= start:
            raise KernelPhysicalMemoryError("PKPMM6 PBP1 memory entry shape changed")
        if index and start < previous_end:
            raise KernelPhysicalMemoryError("PKPMM6 PBP1 memory map overlaps or is unsorted")
        if not _source_matches(source_type, kind):
            raise KernelPhysicalMemoryError("PKPMM6 PBP1 source-kind mapping changed")
        previous_end = end
        kind_pages[kind] += pages
        if kind != 1:
            continue
        cursor = start
        while cursor < end:
            zone = _zone_index(cursor)
            boundary = (DMA_END, DMA32_END, end)[zone]
            part_end = min(end, boundary)
            part_pages = (part_end - cursor) // PAGE_BYTES
            source[zone] += part_pages
            managed_start = cursor
            if managed_start == 0:
                managed_start = PAGE_BYTES
                part_pages -= 1
            if part_pages:
                managed[zone] += part_pages
                start_page = managed_start // PAGE_BYTES
                if extents and extents[-1][2] == zone and extents[-1][0] + extents[-1][1] == start_page:
                    old = extents[-1]
                    extents[-1] = (old[0], old[1] + part_pages, zone)
                else:
                    extents.append((start_page, part_pages, zone))
            cursor = part_end
    largest = [0, 0, 0]
    for _, pages, zone in extents:
        largest[zone] = max(largest[zone], pages)
    post_metadata_extents = list(extents)
    for index, (start_page, pages, zone) in enumerate(post_metadata_extents):
        if zone != 1:
            continue
        if pages < METADATA_ARENA_PAGE_COUNT:
            raise KernelPhysicalMemoryError("PKPMM6 first DMA32 extent cannot hold metadata arena")
        if pages == METADATA_ARENA_PAGE_COUNT:
            post_metadata_extents.pop(index)
        else:
            post_metadata_extents[index] = (
                start_page + METADATA_ARENA_PAGE_COUNT,
                pages - METADATA_ARENA_PAGE_COUNT,
                zone,
            )
        break
    else:
        raise KernelPhysicalMemoryError("PKPMM6 PBP1 map has no DMA32 metadata extent")
    post_metadata_largest = [0, 0, 0]
    for _, pages, zone in post_metadata_extents:
        post_metadata_largest[zone] = max(post_metadata_largest[zone], pages)

    # PKPMM6 follows the allocator itself: each replacement is DMA32 first-fit,
    # then the complete predecessor generation is returned and coalesced. This
    # independently derives the final retained generation and its free holes.
    post_generation_extents = list(post_metadata_extents)
    active_generation: tuple[int, int, int] | None = None
    ordinary_first_address = 0

    def allocate_dma32_first_fit(page_count: int) -> tuple[int, int, int]:
        for index, (start_page, pages, zone) in enumerate(post_generation_extents):
            if zone != 1 or pages < page_count:
                continue
            allocated = (start_page, page_count, zone)
            if pages == page_count:
                post_generation_extents.pop(index)
            else:
                post_generation_extents[index] = (
                    start_page + page_count, pages - page_count, zone
                )
            return allocated
        raise KernelPhysicalMemoryError(
            "PKPMM6 first post-metadata DMA32 extent cannot hold ledger generation"
        )

    def release_extent(extent: tuple[int, int, int]) -> None:
        post_generation_extents.append(extent)
        merged: list[tuple[int, int, int]] = []
        for candidate in sorted(post_generation_extents):
            if merged and merged[-1][2] == candidate[2] and merged[-1][0] + merged[-1][1] == candidate[0]:
                previous = merged[-1]
                merged[-1] = (previous[0], previous[1] + candidate[1], previous[2])
            else:
                merged.append(candidate)
        post_generation_extents[:] = merged

    active_generation = allocate_dma32_first_fit(LEDGER_PAGE_COUNTS[0])
    ordinary_first_address = next(
        start * PAGE_BYTES
        for start, pages, zone in post_generation_extents
        if zone == 1 and pages
    )
    snapshot_extent = allocate_dma32_first_fit(ACPI_SNAPSHOT_PAGE_COUNT)
    snapshot_physical_address = snapshot_extent[0] * PAGE_BYTES
    for page_count in LEDGER_PAGE_COUNTS[1:]:
        candidate = allocate_dma32_first_fit(page_count)
        if active_generation is not None:
            release_extent(active_generation)
        active_generation = candidate

    boot_ranges: list[tuple[int, int, int]] = []
    boot_source_records = 0
    boot_pages_by_zone = [0, 0, 0]
    range_checksum = _fnv_u64(_fnv_u64(0xCBF29CE484222325, 1), 2)
    for entry in entries:
        if int(entry["kind"]) != 2:
            continue
        boot_source_records += 1
        start_page = int(str(entry["physical_start"]), 16) // PAGE_BYTES
        remaining = int(entry["page_count"])
        for value in (start_page, remaining, int(entry["kind"]), int(entry["source_type"])):
            range_checksum = _fnv_u64(range_checksum, value)
        while remaining:
            zone = _zone_index(start_page * PAGE_BYTES)
            boundary_page = (DMA_END // PAGE_BYTES, DMA32_END // PAGE_BYTES, 1 << 52)[zone]
            take = min(remaining, boundary_page - start_page)
            if take <= 0:
                raise KernelPhysicalMemoryError("PKPMM6 reclaim range cannot advance")
            boot_pages_by_zone[zone] += take
            if (
                boot_ranges
                and boot_ranges[-1][2] == zone
                and boot_ranges[-1][0] + boot_ranges[-1][1] == start_page
            ):
                previous = boot_ranges[-1]
                boot_ranges[-1] = (previous[0], previous[1] + take, zone)
            else:
                boot_ranges.append((start_page, take, zone))
            start_page += take
            remaining -= take
    post_reclaim_extents: list[tuple[int, int, int]] = []
    reclaim_coalesces = 0
    for extent in sorted([*post_generation_extents, *boot_ranges]):
        if post_reclaim_extents:
            previous = post_reclaim_extents[-1]
            previous_end = previous[0] + previous[1]
            if extent[0] < previous_end:
                raise KernelPhysicalMemoryError("PKPMM6 reclaim overlaps retained ownership")
            if previous[2] == extent[2] and extent[0] == previous_end:
                post_reclaim_extents[-1] = (
                    previous[0], previous[1] + extent[1], previous[2]
                )
                reclaim_coalesces += 1
                continue
        post_reclaim_extents.append(extent)
    boot_pages = sum(boot_pages_by_zone)
    reclaim_bytes = boot_pages * PAGE_BYTES
    receipt_values = (
        1, 1, 1, 2, boot_source_records, len(boot_ranges), boot_pages,
        len(post_generation_extents), len(post_reclaim_extents), reclaim_bytes,
        reclaim_bytes, range_checksum, *boot_pages_by_zone,
    )
    receipt_checksum = 0xCBF29CE484222325
    for value in receipt_values:
        receipt_checksum = _fnv_u64(receipt_checksum, value)
    post_reclaim_largest = [0, 0, 0]
    post_reclaim_first = [0, 0, 0]
    for start_page, pages, zone in post_reclaim_extents:
        post_reclaim_largest[zone] = max(post_reclaim_largest[zone], pages)
        if post_reclaim_first[zone] == 0:
            post_reclaim_first[zone] = start_page * PAGE_BYTES

    acpi_ranges: list[tuple[int, int, int]] = []
    acpi_source_records = 0
    acpi_pages_by_zone = [0, 0, 0]
    acpi_range_checksum = _fnv_u64(_fnv_u64(0xCBF29CE484222325, 2), 2)
    for entry in entries:
        if int(entry["kind"]) != 5:
            continue
        acpi_source_records += 1
        start_page = int(str(entry["physical_start"]), 16) // PAGE_BYTES
        remaining = int(entry["page_count"])
        for value in (start_page, remaining, int(entry["kind"]), int(entry["source_type"])):
            acpi_range_checksum = _fnv_u64(acpi_range_checksum, value)
        while remaining:
            zone = _zone_index(start_page * PAGE_BYTES)
            boundary_page = (DMA_END // PAGE_BYTES, DMA32_END // PAGE_BYTES, 1 << 52)[zone]
            take = min(remaining, boundary_page - start_page)
            if take <= 0:
                raise KernelPhysicalMemoryError("PKPMM7 ACPI reclaim range cannot advance")
            acpi_pages_by_zone[zone] += take
            if (
                acpi_ranges
                and acpi_ranges[-1][2] == zone
                and acpi_ranges[-1][0] + acpi_ranges[-1][1] == start_page
            ):
                previous = acpi_ranges[-1]
                acpi_ranges[-1] = (previous[0], previous[1] + take, zone)
            else:
                acpi_ranges.append((start_page, take, zone))
            start_page += take
            remaining -= take
    post_acpi_reclaim_extents: list[tuple[int, int, int]] = []
    acpi_reclaim_coalesces = 0
    for extent in sorted([*post_reclaim_extents, *acpi_ranges]):
        if post_acpi_reclaim_extents:
            previous = post_acpi_reclaim_extents[-1]
            previous_end = previous[0] + previous[1]
            if extent[0] < previous_end:
                raise KernelPhysicalMemoryError("PKPMM7 ACPI reclaim overlaps retained ownership")
            if previous[2] == extent[2] and extent[0] == previous_end:
                post_acpi_reclaim_extents[-1] = (
                    previous[0],
                    previous[1] + extent[1],
                    previous[2],
                )
                acpi_reclaim_coalesces += 1
                continue
        post_acpi_reclaim_extents.append(extent)
    acpi_pages = sum(acpi_pages_by_zone)
    acpi_reclaim_bytes = acpi_pages * PAGE_BYTES
    acpi_receipt_values = (
        2,
        2,
        2,
        2,
        acpi_source_records,
        len(acpi_ranges),
        acpi_pages,
        len(post_reclaim_extents),
        len(post_acpi_reclaim_extents),
        acpi_reclaim_bytes,
        acpi_reclaim_bytes,
        acpi_range_checksum,
        *acpi_pages_by_zone,
    )
    acpi_receipt_checksum = 0xCBF29CE484222325
    for value in acpi_receipt_values:
        acpi_receipt_checksum = _fnv_u64(acpi_receipt_checksum, value)

    def range_has_loader(start: int, byte_count: int) -> bool:
        target_end = start + byte_count
        covered = start
        for entry in entries:
            entry_start = int(str(entry["physical_start"]), 16)
            entry_end = entry_start + int(entry["page_count"]) * PAGE_BYTES
            if entry_end <= covered or entry_start > covered:
                continue
            if int(entry["kind"]) != 10:
                return False
            covered = min(entry_end, target_end)
            if covered == target_end:
                return True
        return False

    kernel_base = int(str(core["kernel_physical_base"]), 16)
    kernel_size = int(core["kernel_physical_size"])
    handoff_base = int(str(core["handoff_physical_base"]), 16)
    handoff_size = int(core["handoff_byte_count"])
    root = int(str(core["page_table_root_physical"]), 16)
    if not all((
        range_has_loader(kernel_base, kernel_size),
        range_has_loader(handoff_base, handoff_size),
        range_has_loader(root, PAGE_BYTES),
    )):
        raise KernelPhysicalMemoryError("PKPMM6 PBP1 core range escaped loader-reserved ownership")
    first = [next((start * PAGE_BYTES for start, pages, item_zone in extents if item_zone == zone and pages), 0) for zone in range(3)]
    return {
        "entry_count": len(entries),
        "kind_pages": kind_pages,
        "source_usable_pages": source,
        "managed_pages": managed,
        "free_extent_count": len(extents),
        "largest_free_pages": largest,
        "post_metadata_free_extent_count": len(post_metadata_extents),
        "post_metadata_largest_free_pages": post_metadata_largest,
        "boot_reclaim": {
            "source_record_count": boot_source_records,
            "range_count": len(boot_ranges),
            "pages_by_zone": boot_pages_by_zone,
            "page_count": boot_pages,
            "pre_free_extent_count": len(post_generation_extents),
            "post_free_extent_count": len(post_reclaim_extents),
            "coalesce_events": reclaim_coalesces,
            "range_checksum": range_checksum,
            "receipt_checksum": receipt_checksum,
            "scrub_bytes": reclaim_bytes,
            "largest_free_pages": post_reclaim_largest,
            "first_free_address": post_reclaim_first,
        },
        "acpi_snapshot": {
            "physical_address": snapshot_physical_address,
            "page_count": ACPI_SNAPSHOT_PAGE_COUNT,
        },
        "acpi_reclaim": {
            "source_record_count": acpi_source_records,
            "range_count": len(acpi_ranges),
            "pages_by_zone": acpi_pages_by_zone,
            "page_count": acpi_pages,
            "pre_free_extent_count": len(post_reclaim_extents),
            "post_free_extent_count": len(post_acpi_reclaim_extents),
            "coalesce_events": acpi_reclaim_coalesces,
            "range_checksum": acpi_range_checksum,
            "receipt_checksum": acpi_receipt_checksum,
            "scrub_bytes": acpi_reclaim_bytes,
        },
        "first_free_address": first,
        "ordinary_first_address": ordinary_first_address,
        "kernel_base": kernel_base,
        "kernel_pages": (kernel_size + PAGE_BYTES - 1) // PAGE_BYTES,
        "handoff_base": handoff_base,
        "handoff_pages": (handoff_size + PAGE_BYTES - 1) // PAGE_BYTES,
        "root": root,
        "null_guard_pages": int(bool(entries and int(str(entries[0]["physical_start"]), 16) == 0 and int(entries[0]["kind"]) == 1)),
    }


def validate_observation_binding(observation: dict[str, Any], transcript: dict[str, Any]) -> dict[str, Any]:
    derived = derive_memory_summary(transcript)
    firmware_tables = transcript.get("firmware_tables")
    if not isinstance(firmware_tables, list) or len(firmware_tables) != 1:
        raise KernelPhysicalMemoryError("PKACPI1 PBP1 firmware-table binding is missing")
    firmware_table = firmware_tables[0]
    if (
        not isinstance(firmware_table, dict)
        or int(str(firmware_table.get("physical_address")), 16)
        != observation["acpi_snapshot"]["rsdp"]
        or firmware_table.get("byte_count") != 36
        or firmware_table.get("physical") is not True
        or firmware_table.get("checksum_validated") is not True
        or firmware_table.get("copied") is not False
    ):
        raise KernelPhysicalMemoryError("PKACPI1 marker disagrees with the PBP1 ACPI 2.0 record")
    expected_map = {
        "entries": derived["entry_count"],
        "usable_pages": derived["kind_pages"][1],
        "boot_reclaimable_pages": derived["kind_pages"][2],
        "loader_reserved_pages": derived["kind_pages"][10],
        "null_guard_pages": derived["null_guard_pages"],
    }
    expected_zones = {
        "dma_source": derived["source_usable_pages"][0],
        "dma_managed": derived["managed_pages"][0],
        "dma32_source": derived["source_usable_pages"][1],
        "dma32_managed": derived["managed_pages"][1],
        "normal_source": derived["source_usable_pages"][2],
        "normal_managed": derived["managed_pages"][2],
        "extents": derived["post_metadata_free_extent_count"],
        "largest_dma": derived["post_metadata_largest_free_pages"][0],
        "largest_dma32": derived["post_metadata_largest_free_pages"][1],
        "largest_normal": derived["post_metadata_largest_free_pages"][2],
    }
    expected_ownership = {
        "kernel_base": derived["kernel_base"],
        "kernel_pages": derived["kernel_pages"],
        "handoff_base": derived["handoff_base"],
        "handoff_pages": derived["handoff_pages"],
        "root": derived["root"],
        "protected": 1,
    }
    reclaim = derived["boot_reclaim"]
    expected_reclaim = {
        "stage": "post_exit_boot_services",
        "class": "boot_services",
        "sequence": 1,
        "source_records": reclaim["source_record_count"],
        "ranges": reclaim["range_count"],
        "pages": reclaim["page_count"],
        "dma_pages": reclaim["pages_by_zone"][0],
        "dma32_pages": reclaim["pages_by_zone"][1],
        "normal_pages": reclaim["pages_by_zone"][2],
        "pre_extents": reclaim["pre_free_extent_count"],
        "post_extents": reclaim["post_free_extent_count"],
        "scrub_bytes": reclaim["scrub_bytes"],
        "verified_bytes": reclaim["scrub_bytes"],
        "range_checksum": reclaim["range_checksum"],
        "receipt_checksum": reclaim["receipt_checksum"],
        "idempotent": 1,
        "acpi_held_pages": derived["kind_pages"][5],
        "acpi_early_rejected": 1,
        "retained_excluded": 1,
        "atomic": 1,
        "rollback": "host_verified",
    }
    acpi_reclaim = derived["acpi_reclaim"]
    expected_acpi_reclaim = {
        "stage": "acpi_tables_released",
        "class": "acpi",
        "sequence": 2,
        "source_records": acpi_reclaim["source_record_count"],
        "ranges": acpi_reclaim["range_count"],
        "pages": acpi_reclaim["page_count"],
        "dma_pages": acpi_reclaim["pages_by_zone"][0],
        "dma32_pages": acpi_reclaim["pages_by_zone"][1],
        "normal_pages": acpi_reclaim["pages_by_zone"][2],
        "pre_extents": acpi_reclaim["pre_free_extent_count"],
        "post_extents": acpi_reclaim["post_free_extent_count"],
        "scrub_bytes": acpi_reclaim["scrub_bytes"],
        "verified_bytes": acpi_reclaim["scrub_bytes"],
        "range_checksum": acpi_reclaim["range_checksum"],
        "receipt_checksum": acpi_reclaim["receipt_checksum"],
        "idempotent": 1,
        "snapshot_retained": 1,
        "atomic": 1,
        "rollback": "host_verified",
    }
    if observation["map"] != expected_map or observation["zones"] != expected_zones:
        raise KernelPhysicalMemoryError("PKPMM6 markers disagree with independent PBP1 accounting")
    if observation["ownership"] != expected_ownership:
        raise KernelPhysicalMemoryError("PKPMM6 ownership marker disagrees with PBP1 core ranges")
    if observation["reclaim"] != expected_reclaim:
        raise KernelPhysicalMemoryError("PKPMM7 boot reclaim receipt disagrees with independent PBP1 accounting")
    if observation["acpi_reclaim"] != expected_acpi_reclaim:
        raise KernelPhysicalMemoryError("PKPMM7 ACPI reclaim receipt disagrees with independent PBP1 accounting")
    if (
        observation["acpi_snapshot"]["snapshot"]
        != derived["acpi_snapshot"]["physical_address"]
        or observation["acpi_snapshot"]["snapshot_pages"]
        != derived["acpi_snapshot"]["page_count"]
    ):
        raise KernelPhysicalMemoryError("PKACPI1 snapshot is not deterministic DMA32 first-fit")
    if observation["metadata"]["physical_start"] != derived["first_free_address"][1]:
        raise KernelPhysicalMemoryError("PKPMM6 metadata arena is not deterministic DMA32 first-fit")
    if observation["scrub"]["start"] != derived["ordinary_first_address"]:
        raise KernelPhysicalMemoryError("PKPMM6 ordinary allocation did not follow pre-reclaim first fit")
    return derived
