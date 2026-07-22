"""Independent PKPMM2 oracle for bounded physical-page scrubbing."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKPMM2"
SELECTED_MOVE_ID = "N9-PMM-SCRUB-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-physical-memory-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-physical-memory-contract.schema.json"
SCHEMA_RELATIVE = "specs/native-kernel-physical-memory-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-physical-memory-readiness.json"
MARKER_COUNT = 40
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 31
COMMON_KERNEL_MARKER_COUNT = 4
SELECTOR = 8
FEATURE = "development-physical-memory"
PAGE_BYTES = 4096
DMA_END = 16 * 1024 * 1024
DMA32_END = 4 * 1024 * 1024 * 1024
MAX_MEMORY_ENTRIES = 256
COMPLETION_MARKER = b"POOLEOS:KERNEL:PMM-RESULT PASS contract=PKPMM2"
SCRUB_PAGE_COUNT = 8
SCRUB_BYTES = SCRUB_PAGE_COUNT * PAGE_BYTES
PHYSICAL_WRITES = (SCRUB_PAGE_COUNT + 2) * (PAGE_BYTES // 8)
PHYSICAL_READS = (SCRUB_PAGE_COUNT + 4) * (PAGE_BYTES // 8)
TEMPORARY_PTE_WRITES = 28
BOOTSTRAP_INVALIDATIONS = 28
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
    "NEG-N9-PKPMM-MAPPING",
    "NEG-N9-PKPMM-RECLAIM",
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
    r"^POOLEOS:KERNEL:PMM-EARLY PASS contract=(PKPMM2) selector=(8) bsp=(1) if=(0) "
    r"stack=(validated_by_wrapper) serial=(initialized)$"
)
STAGE = re.compile(r"^POOLEOS:KERNEL:PMM-STAGE PASS contract=(PKPMM2) stage=([1-5])$")
MAP = re.compile(
    rf"^POOLEOS:KERNEL:PMM-MAP PASS contract=(PKPMM2) entries={DEC} usable_pages={DEC} "
    rf"boot_reclaimable_pages={DEC} loader_reserved_pages={DEC} null_guard_pages={DEC}$"
)
ZONES = re.compile(
    rf"^POOLEOS:KERNEL:PMM-ZONES PASS contract=(PKPMM2) dma_source={DEC} dma_managed={DEC} "
    rf"dma32_source={DEC} dma32_managed={DEC} normal_source={DEC} normal_managed={DEC} "
    rf"extents={DEC} largest_dma={DEC} largest_dma32={DEC} largest_normal={DEC}$"
)
OWNERSHIP = re.compile(
    rf"^POOLEOS:KERNEL:PMM-OWNERSHIP PASS contract=(PKPMM2) kernel_base={HEX} kernel_pages={DEC} "
    rf"handoff_base={HEX} handoff_pages={DEC} root={HEX} protected=([01])$"
)
SCRUB = re.compile(
    rf"^POOLEOS:KERNEL:PMM-SCRUB PASS contract=(PKPMM2) allocations={DEC} frees={DEC} "
    rf"start={HEX} first_generation={DEC} reuse_generation={DEC} allocation_receipts={DEC} "
    rf"release_receipts={DEC} scrub_pages={DEC} scrub_bytes={DEC} verified_bytes={DEC} "
    rf"stale_pattern={HEX} stale_absent={DEC} double_free_rejected={DEC} quota_rejected={DEC} "
    rf"unavailable_rejected={DEC} metadata_poison={DEC} coalesces={DEC} rollback=(host_verified)$"
)
RESULT = re.compile(
    rf"^POOLEOS:KERNEL:PMM-RESULT PASS contract=(PKPMM2) profile=(qemu64_tier0) managed_pages={DEC} "
    rf"allocated_pages={DEC} physical_writes={DEC} physical_reads={DEC} temporary_pte_writes={DEC} "
    rf"bootstrap_invlpg={DEC} alias_revoked={DEC} mappings=(temporary_single_page) reclaim={DEC} "
    rf"concurrency={DEC} smp={DEC} signatures={DEC} authority={DEC} actions={DEC} production={DEC} "
    rf"terminal=(halt)$"
)


class KernelPhysicalMemoryError(ValueError):
    """Raised when PKPMM2 evidence violates the frozen scrub contract."""


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
        "boot_or_acpi_reclaim_activated": False,
        "complete_direct_map_or_address_space_claimed": False,
        "concurrent_or_smp_allocator_qualified": False,
        "n9_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if (contract.get("contract_id"), contract.get("selected_move_id")) != (CONTRACT_ID, SELECTED_MOVE_ID):
        errors.append("PKPMM2 contract identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, "qemu64", True):
        errors.append("PKPMM2 development profile changed")
    limits = contract.get("limits", {})
    if not isinstance(limits, dict) or tuple(
        limits.get(key) for key in ("memory_entries", "free_extents", "allocations", "quota_pages")
    ) != (256, 256, 32, 64):
        errors.append("PKPMM2 bounded capacities changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKPMM2 hostile-control inventory changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKPMM2 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKPMM2 contract overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    errors.extend(contract_errors(read_json(root / CONTRACT_RELATIVE), root))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKPMM2 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key) for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKPMM2 exact two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKPMM2 hostile-control evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKPMM2 readiness claims changed")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("PKPMM2 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelPhysicalMemoryError(f"PKPMM2 {name} marker violates its contract: {marker!r}")
    return match


def _dec(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 10)


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def _validate_prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelPhysicalMemoryError("PKPMM2 transfer selector changed")
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
        raise KernelPhysicalMemoryError(f"expected {MARKER_COUNT} PKPMM2 markers, observed {len(markers)}")
    prefix = _validate_prefix(markers)
    early_match = _match(EARLY, markers[25], "early-entry")
    stages = [_match(STAGE, markers[26 + index], "stage") for index in range(5)]
    if [int(item.group(2)) for item in stages] != [1, 2, 3, 4, 5]:
        raise KernelPhysicalMemoryError("PKPMM2 stage order changed")
    map_match = _match(MAP, markers[35], "map")
    zone_match = _match(ZONES, markers[36], "zones")
    owner_match = _match(OWNERSHIP, markers[37], "ownership")
    scrub_match = _match(SCRUB, markers[38], "scrub")
    result_match = _match(RESULT, markers[39], "result")
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
        "mappings": result_match.group(10),
        "reclaim": _dec(result_match, 11),
        "concurrency": _dec(result_match, 12),
        "smp": _dec(result_match, 13),
        "signatures": _dec(result_match, 14),
        "authority": _dec(result_match, 15),
        "actions": _dec(result_match, 16),
        "production": _dec(result_match, 17),
        "terminal": result_match.group(18),
    }
    if (
        map_summary["entries"] == 0
        or map_summary["entries"] > MAX_MEMORY_ENTRIES
        or map_summary["entries"]
        != prefix["boot_prefix"]["pbp1"]["memory_entry_count"]
    ):
        raise KernelPhysicalMemoryError("PKPMM2 memory-entry bound changed")
    if map_summary["null_guard_pages"] != 1 or map_summary["usable_pages"] != sum(
        zones[key] for key in ("dma_source", "dma32_source", "normal_source")
    ):
        raise KernelPhysicalMemoryError("PKPMM2 source accounting changed")
    if map_summary["usable_pages"] - 1 != sum(
        zones[key] for key in ("dma_managed", "dma32_managed", "normal_managed")
    ):
        raise KernelPhysicalMemoryError("PKPMM2 managed accounting changed")
    if ownership["protected"] != 1 or any(value % PAGE_BYTES for value in (
        ownership["kernel_base"], ownership["handoff_base"], ownership["root"]
    )):
        raise KernelPhysicalMemoryError("PKPMM2 protected ownership marker changed")
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
    if exact_scrub != (
        2, 2, 1, 2, 2, 2, SCRUB_PAGE_COUNT, SCRUB_BYTES, SCRUB_BYTES,
        STALE_PATTERN, 1, 1, 1, 1, 2, 2, "host_verified",
    ):
        raise KernelPhysicalMemoryError("PKPMM2 bounded scrub exercise changed")
    if not DMA_END <= scrub["start"] < DMA32_END:
        raise KernelPhysicalMemoryError("PKPMM2 scrub allocation escaped its DMA32 zone")
    exact_result = (
        result["managed_pages"],
        result["allocated_pages"],
        result["physical_writes"],
        result["physical_reads"],
        result["temporary_pte_writes"],
        result["bootstrap_invlpg"],
        result["alias_revoked"],
        result["mappings"],
        result["reclaim"],
        result["concurrency"],
        result["smp"],
        result["signatures"],
        result["authority"],
        result["actions"],
        result["production"],
        result["terminal"],
    )
    if exact_result != (
        map_summary["usable_pages"] - 1, 0, PHYSICAL_WRITES, PHYSICAL_READS,
        TEMPORARY_PTE_WRITES, BOOTSTRAP_INVALIDATIONS, 1, "temporary_single_page",
        0, 0, 0, 0, 0, 0, 0, "halt",
    ):
        raise KernelPhysicalMemoryError("PKPMM2 result boundary changed")
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


def derive_memory_summary(transcript: dict[str, Any]) -> dict[str, Any]:
    entries = transcript.get("memory_entries")
    core = transcript.get("core")
    if not isinstance(entries, list) or not isinstance(core, dict) or not 1 <= len(entries) <= MAX_MEMORY_ENTRIES:
        raise KernelPhysicalMemoryError("PKPMM2 PBP1 memory map is missing or out of bounds")
    kind_pages = [0] * 12
    source = [0, 0, 0]
    managed = [0, 0, 0]
    extents: list[tuple[int, int, int]] = []
    previous_end = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise KernelPhysicalMemoryError("PKPMM2 PBP1 memory entry is not an object")
        start = int(str(entry["physical_start"]), 16)
        pages = int(entry["page_count"])
        kind = int(entry["kind"])
        source_type = int(entry["source_type"])
        end = start + pages * PAGE_BYTES
        if start % PAGE_BYTES or pages <= 0 or not 0 <= kind < 12 or end <= start:
            raise KernelPhysicalMemoryError("PKPMM2 PBP1 memory entry shape changed")
        if index and start < previous_end:
            raise KernelPhysicalMemoryError("PKPMM2 PBP1 memory map overlaps or is unsorted")
        if not _source_matches(source_type, kind):
            raise KernelPhysicalMemoryError("PKPMM2 PBP1 source-kind mapping changed")
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
        raise KernelPhysicalMemoryError("PKPMM2 PBP1 core range escaped loader-reserved ownership")
    first = [next((start * PAGE_BYTES for start, pages, item_zone in extents if item_zone == zone and pages), 0) for zone in range(3)]
    return {
        "entry_count": len(entries),
        "kind_pages": kind_pages,
        "source_usable_pages": source,
        "managed_pages": managed,
        "free_extent_count": len(extents),
        "largest_free_pages": largest,
        "first_free_address": first,
        "kernel_base": kernel_base,
        "kernel_pages": (kernel_size + PAGE_BYTES - 1) // PAGE_BYTES,
        "handoff_base": handoff_base,
        "handoff_pages": (handoff_size + PAGE_BYTES - 1) // PAGE_BYTES,
        "root": root,
        "null_guard_pages": int(bool(entries and int(str(entries[0]["physical_start"]), 16) == 0 and int(entries[0]["kind"]) == 1)),
    }


def validate_observation_binding(observation: dict[str, Any], transcript: dict[str, Any]) -> dict[str, Any]:
    derived = derive_memory_summary(transcript)
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
        "extents": derived["free_extent_count"],
        "largest_dma": derived["largest_free_pages"][0],
        "largest_dma32": derived["largest_free_pages"][1],
        "largest_normal": derived["largest_free_pages"][2],
    }
    expected_ownership = {
        "kernel_base": derived["kernel_base"],
        "kernel_pages": derived["kernel_pages"],
        "handoff_base": derived["handoff_base"],
        "handoff_pages": derived["handoff_pages"],
        "root": derived["root"],
        "protected": 1,
    }
    if observation["map"] != expected_map or observation["zones"] != expected_zones:
        raise KernelPhysicalMemoryError("PKPMM2 markers disagree with independent PBP1 accounting")
    if observation["ownership"] != expected_ownership:
        raise KernelPhysicalMemoryError("PKPMM2 ownership marker disagrees with PBP1 core ranges")
    if observation["scrub"]["start"] != derived["first_free_address"][1]:
        raise KernelPhysicalMemoryError("PKPMM2 DMA32 scrub allocation is not deterministic first-fit")
    return derived
