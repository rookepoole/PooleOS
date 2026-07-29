"""Independent PKVM3 oracle for the sparse generation-owned direct map."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_physical_memory, native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKVM3"
SELECTED_MOVE_ID = "N9-VM-DIRECT-MAP-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-virtual-memory-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-virtual-memory-contract.schema.json"
SCHEMA_RELATIVE = "specs/native-kernel-virtual-memory-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-virtual-memory-readiness.json"
FEATURE = "development-active-virtual-memory"
SELECTOR = 10
MARKER_COUNT = 40
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 31
COMMON_KERNEL_MARKER_COUNT = 4
PAGE_BYTES = 4096
ACTIVE_CR3_WRITES = 2
ACTIVE_INVALIDATIONS = 3
DIRECT_MAP_START = 0xFFFF_9000_0000_0000
COMPLETION_MARKER = b"POOLEOS:KERNEL:ACTIVE-VM-RESULT PASS contract=PKVM3"

IMPLEMENTATION_INPUTS = (
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/active_virtual_memory.rs",
    "native/kernel/src/physical_memory.rs",
    "native/kernel/src/virtual_memory.rs",
    "native/kmap/src/lib.rs",
    "models/tla/PooleVirtualMemory.tla",
    "runtime/native_kernel_physical_memory.py",
    "runtime/native_kernel_transfer.py",
    "runtime/native_kernel_virtual_memory.py",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-map-contract.json",
    "tools/qualify_native_kernel_virtual_memory.py",
    "tests/test_native_kernel_virtual_memory.py",
    "docs/native-kernel-virtual-memory.md",
    "runs/native-kernel-transfer-readiness.json",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N9-PKVM3-MARKER-OMISSION",
    "NEG-N9-PKVM3-MARKER-ORDER",
    "NEG-N9-PKVM3-MARKER-DUPLICATE",
    "NEG-N9-PKVM3-SELECTOR",
    "NEG-N9-PKVM3-CONTRACT",
    "NEG-N9-PKVM3-TOPOLOGY",
    "NEG-N9-PKVM3-ORIGINAL-ROOT",
    "NEG-N9-PKVM3-CANDIDATE-ALIGNMENT",
    "NEG-N9-PKVM3-TABLE-GENERATION",
    "NEG-N9-PKVM3-DATA-CONTIGUITY",
    "NEG-N9-PKVM3-DATA-GENERATION",
    "NEG-N9-PKVM3-DIRECT-FIRST",
    "NEG-N9-PKVM3-DIRECT-LAST",
    "NEG-N9-PKVM3-DIRECT-GENERATION",
    "NEG-N9-PKVM3-DIRECT-RANGES",
    "NEG-N9-PKVM3-MAPPED-PAGES",
    "NEG-N9-PKVM3-GAP-PAGES",
    "NEG-N9-PKVM3-RETAINED-EXCLUSION",
    "NEG-N9-PKVM3-COVERAGE-CHECKSUM",
    "NEG-N9-PKVM3-CACHE-POLICY",
    "NEG-N9-PKVM3-CACHE-ALIAS",
    "NEG-N9-PKVM3-INHERITED-KERNEL",
    "NEG-N9-PKVM3-GUARDED-STACK",
    "NEG-N9-PKVM3-HANDOFF",
    "NEG-N9-PKVM3-BOOTSTRAP-REVOCATION",
    "NEG-N9-PKVM3-PRE-ACTIVE-STATE",
    "NEG-N9-PKVM3-CR3-WRITES",
    "NEG-N9-PKVM3-CANDIDATE-READBACK",
    "NEG-N9-PKVM3-ORIGINAL-RESTORE",
    "NEG-N9-PKVM3-ROLLBACK-CONTROL",
    "NEG-N9-PKVM3-BSP",
    "NEG-N9-PKVM3-ACTIVATION-SMP",
    "NEG-N9-PKVM3-LOCAL-INVLPG",
    "NEG-N9-PKVM3-ACTIVE-RECEIPTS",
    "NEG-N9-PKVM3-PROBE",
    "NEG-N9-PKVM3-LEAF-MUTATIONS",
    "NEG-N9-PKVM3-RETIREMENT-RECEIPT",
    "NEG-N9-PKVM3-CONTEXT-FLUSH",
    "NEG-N9-PKVM3-REMOTE-PENDING",
    "NEG-N9-PKVM3-FUTURE-SMP",
    "NEG-N9-PKVM3-DEFERRED-RECLAIM",
    "NEG-N9-PKVM3-EXACT-RELEASE",
    "NEG-N9-PKVM3-PHYSICAL-WRITES",
    "NEG-N9-PKVM3-TEMPORARY-MAPPING",
    "NEG-N9-PKVM3-OVERCLAIM",
    "NEG-N9-PKVM3-PBP1-BINDING",
)

HEX = r"(0x[0-9A-F]{16})"
DEC = r"([0-9]+)"
LAYOUT = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-LAYOUT PASS contract=(PKVM3) canonical_bits=(48) "
    rf"direct_start=(0xFFFF900000000000) direct_end=(0xFFFFD00000000000) "
    rf"user_start=(0x0000000040000000) page_bytes=(4096) table_pages={DEC} "
    rf"direct_directory_tables={DEC} direct_page_tables={DEC} mapped_pages={DEC}$"
)
EARLY = re.compile(
    r"^POOLEOS:KERNEL:ACTIVE-VM-EARLY PASS contract=(PKVM3) selector=(10) "
    r"bsp=(1) if=(0) stack=(validated_by_wrapper) serial=(initialized)$"
)
STAGE = re.compile(
    r"^POOLEOS:KERNEL:ACTIVE-VM-STAGE PASS contract=(PKVM3) stage=([1-5])$"
)
CANDIDATE = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-CANDIDATE PASS contract=(PKVM3) original_root={HEX} "
    rf"candidate_root={HEX} table_generation={DEC} data={HEX} data_generation={DEC} "
    rf"direct_first={HEX} direct_last={HEX} direct_generation={DEC} direct_ranges={DEC} "
    rf"gap_pages={DEC} retained_excluded_pages={DEC} coverage_checksum={HEX} "
    rf"cache=(write_back) cache_alias_rejected={DEC} inherited_kernel=(exact) guarded_stack=(exact) "
    rf"handoff=(exact) bootstrap_alias_revoked={DEC} root_active={DEC}$"
)
ACTIVATION = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-ACTIVATION PASS contract=(PKVM3) cr3_writes={DEC} "
    r"candidate_readback=(exact) original_restore=(exact) rollback_control=(host_verified) "
    rf"bsp={DEC} smp={DEC}$"
)
INVALIDATION = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-INVALIDATION PASS contract=(PKVM3) local_invlpg={DEC} "
    rf"active_receipts={DEC} probe={HEX} protect={DEC} user_unmap={DEC} direct_unmap={DEC} "
    rf"stale_root_rejected=(host) premature_reuse_rejected={DEC} generation_retirement_receipts={DEC} "
    rf"local_context_flushes={DEC} remote_shootdowns_pending={DEC} future_smp_shootdown_required={DEC} "
    rf"old_generation_reclaim_deferred={DEC} exact_release_receipt={DEC} shootdown={DEC}$"
)
RESULT = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-RESULT PASS contract=(PKVM3) profile=(qemu64_tier0) "
    rf"root_released={DEC} data_released={DEC} allocated_pages={DEC} physical_writes={DEC} "
    rf"temporary_pte_writes={DEC} bootstrap_invlpg={DEC} allocations={DEC} frees={DEC} "
    rf"active_cr3_writes={DEC} active_invlpg={DEC} shootdown={DEC} ring3={DEC} "
    rf"huge_pages={DEC} pcid={DEC} cow={DEC} user_faults={DEC} pager={DEC} heap={DEC} "
    rf"smp={DEC} signatures={DEC} authority={DEC} actions={DEC} production={DEC} terminal=(halt)$"
)


class KernelVirtualMemoryError(ValueError):
    """Raised when PKVM3 evidence violates the frozen contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelVirtualMemoryError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelVirtualMemoryError("binding path escapes repository") from error
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
        "canonical_48_bit_layout_frozen": True,
        "kernel_stack_and_handoff_mappings_inherited_exactly": True,
        "live_pmm_generation_bound_table_and_data_frames": True,
        "kernel_complete_candidate_root_materialized": True,
        "complete_profile_pmm_ownership_direct_map_activated": True,
        "sparse_holes_and_retained_ranges_unmapped": True,
        "single_write_back_cache_policy_enforced": True,
        "one_bsp_candidate_root_installed_and_restored": True,
        "active_address_space_local_invalidation_receipts_exercised": True,
        "generation_retirement_receipt_enforced": True,
        "future_smp_shootdown_dependency_enforced": True,
        "architectural_accessed_dirty_bits_handled": True,
        "transactional_leaf_and_cr3_rollback_host_tested": True,
        "frame_reuse_before_user_and_direct_receipts_rejected": True,
        "bootstrap_temporary_mapping_activated_and_revoked": True,
        "smp_shootdown_implemented": False,
        "ring3_huge_pages_pcid_cow_user_faults_or_pager_implemented": False,
        "n9_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if (contract.get("contract_id"), contract.get("selected_move_id")) != (
        CONTRACT_ID,
        SELECTED_MOVE_ID,
    ):
        errors.append("PKVM3 contract identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, "qemu64", True):
        errors.append("PKVM3 development profile changed")
    limits = contract.get("limits", {})
    if not isinstance(limits, dict) or tuple(
        limits.get(key)
        for key in (
            "max_direct_page_tables",
            "max_direct_directory_tables",
            "page_bytes",
            "cr3_writes",
            "active_local_invalidations",
        )
    ) != (512, 4, PAGE_BYTES, ACTIVE_CR3_WRITES, ACTIVE_INVALIDATIONS):
        errors.append("PKVM3 bounded capacities changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKVM3 hostile-control inventory changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKVM3 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get(
        "production_promotion_allowed"
    ) is not False:
        errors.append("PKVM3 contract overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    errors.extend(contract_errors(read_json(root / CONTRACT_RELATIVE), root))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKVM3 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key)
        for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKVM3 exact two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)]
        != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKVM3 hostile-control evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKVM3 readiness claims changed")
    if readiness.get("production_ready") is not False or readiness.get(
        "production_promotion_allowed"
    ) is not False:
        errors.append("PKVM3 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelVirtualMemoryError(f"PKVM3 {name} marker violates its contract: {marker!r}")
    return match


def _prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelVirtualMemoryError("PKVM3 transfer selector changed")
    baseline = [
        *markers[:BOOT_TRANSFER_MARKER_COUNT],
        *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT],
    ]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append(
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelVirtualMemoryError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelVirtualMemoryError(f"expected {MARKER_COUNT} PKVM3 markers, observed {len(markers)}")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    stages = [_match(STAGE, markers[26 + index], "stage") for index in range(5)]
    if [int(item.group(2)) for item in stages] != [1, 2, 3, 4, 5]:
        raise KernelVirtualMemoryError("PKVM3 stage order changed")
    layout_match = _match(LAYOUT, markers[35], "layout")
    candidate_match = _match(CANDIDATE, markers[36], "candidate")
    activation_match = _match(ACTIVATION, markers[37], "activation")
    invalidation_match = _match(INVALIDATION, markers[38], "invalidation")
    result_match = _match(RESULT, markers[39], "result")

    layout = {
        "table_pages": int(layout_match.group(7)),
        "direct_directory_tables": int(layout_match.group(8)),
        "direct_page_tables": int(layout_match.group(9)),
        "mapped_pages": int(layout_match.group(10)),
    }
    candidate = {
        "original_root": int(candidate_match.group(2), 16),
        "candidate_root": int(candidate_match.group(3), 16),
        "table_generation": int(candidate_match.group(4)),
        "data": int(candidate_match.group(5), 16),
        "data_generation": int(candidate_match.group(6)),
        "direct_first": int(candidate_match.group(7), 16),
        "direct_last": int(candidate_match.group(8), 16),
        "direct_generation": int(candidate_match.group(9)),
        "direct_ranges": int(candidate_match.group(10)),
        "gap_pages": int(candidate_match.group(11)),
        "retained_excluded_pages": int(candidate_match.group(12)),
        "coverage_checksum": int(candidate_match.group(13), 16),
        "cache": candidate_match.group(14),
        "cache_alias_rejected": int(candidate_match.group(15)),
        "inherited_kernel": candidate_match.group(16),
        "guarded_stack": candidate_match.group(17),
        "handoff": candidate_match.group(18),
        "bootstrap_alias_revoked": int(candidate_match.group(19)),
        "root_active": int(candidate_match.group(20)),
    }
    activation = {
        "cr3_writes": int(activation_match.group(2)),
        "candidate_readback": activation_match.group(3),
        "original_restore": activation_match.group(4),
        "rollback_control": activation_match.group(5),
        "bsp": int(activation_match.group(6)),
        "smp": int(activation_match.group(7)),
    }
    invalidation = {
        "local_invlpg": int(invalidation_match.group(2)),
        "active_receipts": int(invalidation_match.group(3)),
        "probe": int(invalidation_match.group(4), 16),
        "protect": int(invalidation_match.group(5)),
        "user_unmap": int(invalidation_match.group(6)),
        "direct_unmap": int(invalidation_match.group(7)),
        "stale_root_rejected": invalidation_match.group(8),
        "premature_reuse_rejected": int(invalidation_match.group(9)),
        "generation_retirement_receipts": int(invalidation_match.group(10)),
        "local_context_flushes": int(invalidation_match.group(11)),
        "remote_shootdowns_pending": int(invalidation_match.group(12)),
        "future_smp_shootdown_required": int(invalidation_match.group(13)),
        "old_generation_reclaim_deferred": int(invalidation_match.group(14)),
        "exact_release_receipt": int(invalidation_match.group(15)),
        "shootdown": int(invalidation_match.group(16)),
    }
    names = (
        "root_released",
        "data_released",
        "allocated_pages",
        "physical_writes",
        "temporary_pte_writes",
        "bootstrap_invlpg",
        "allocations",
        "frees",
        "active_cr3_writes",
        "active_invlpg",
        "shootdown",
        "ring3",
        "huge_pages",
        "pcid",
        "cow",
        "user_faults",
        "pager",
        "heap",
        "smp",
        "signatures",
        "authority",
        "actions",
        "production",
    )
    result = {name: int(result_match.group(index + 3)) for index, name in enumerate(names)}
    result["terminal"] = result_match.group(26)

    original_from_transfer = prefix["transfer_arm"]["root"]
    if candidate["original_root"] != original_from_transfer:
        raise KernelVirtualMemoryError("PKVM3 original root differs from PKXFER1")
    if (
        candidate["candidate_root"] % PAGE_BYTES
        or candidate["candidate_root"] == candidate["original_root"]
        or layout["table_pages"] != (
            5 + layout["direct_directory_tables"] + layout["direct_page_tables"]
        )
        or layout["mapped_pages"] == 0
        or candidate["data"] != candidate["candidate_root"] + layout["table_pages"] * PAGE_BYTES
        or candidate["table_generation"] != 1
        or candidate["data_generation"] != 2
        or candidate["direct_generation"] != candidate["table_generation"]
        or candidate["direct_ranges"] == 0
        or candidate["direct_first"] < DIRECT_MAP_START + PAGE_BYTES
        or candidate["direct_last"] <= candidate["direct_first"]
        or candidate["coverage_checksum"] == 0
        or candidate["cache"] != "write_back"
        or candidate["cache_alias_rejected"] != 1
        or tuple(
            candidate[key]
            for key in (
                "inherited_kernel",
                "guarded_stack",
                "handoff",
                "bootstrap_alias_revoked",
                "root_active",
            )
        )
        != ("exact", "exact", "exact", 1, 0)
    ):
        raise KernelVirtualMemoryError("PKVM3 candidate ownership or inheritance changed")
    if tuple(activation.values()) != (2, "exact", "exact", "host_verified", 1, 0):
        raise KernelVirtualMemoryError("PKVM3 activation proof changed")
    if tuple(invalidation.values()) != (
        3, 3, 0xA5, 1, 1, 1, "host", 1, 1, 1, 0, 1, 1, 1, 0
    ):
        raise KernelVirtualMemoryError("PKVM3 invalidation proof changed")
    expected_physical_writes = (
        2 * layout["table_pages"] * 512
        + 512
        + 5
        + layout["direct_directory_tables"]
        + layout["direct_page_tables"]
        + layout["mapped_pages"]
    )
    expected_result = {
        "root_released": 1,
        "data_released": 1,
        "allocated_pages": 0,
        "physical_writes": expected_physical_writes,
        "temporary_pte_writes": result["temporary_pte_writes"],
        "bootstrap_invlpg": result["temporary_pte_writes"],
        "allocations": 2,
        "frees": 2,
        "active_cr3_writes": ACTIVE_CR3_WRITES,
        "active_invlpg": ACTIVE_INVALIDATIONS,
        "shootdown": 0,
        "ring3": 0,
        "huge_pages": 0,
        "pcid": 0,
        "cow": 0,
        "user_faults": 0,
        "pager": 0,
        "heap": 0,
        "smp": 0,
        "signatures": 0,
        "authority": 0,
        "actions": 0,
        "production": 0,
        "terminal": "halt",
    }
    if result != expected_result:
        changed = {
            key: {"expected": expected_result[key], "observed": result.get(key)}
            for key in expected_result
            if result.get(key) != expected_result[key]
        }
        raise KernelVirtualMemoryError(f"PKVM3 result boundary changed: {changed}")
    if result["temporary_pte_writes"] == 0:
        raise KernelVirtualMemoryError("PKVM3 temporary mapping evidence is empty")
    return {
        "transfer_prefix": prefix,
        "early": {
            "selector": int(early.group(2)),
            "bsp": int(early.group(3)),
            "if": int(early.group(4)),
            "stack": early.group(5),
            "serial": early.group(6),
        },
        "stages": [1, 2, 3, 4, 5],
        "layout": layout,
        "candidate": candidate,
        "activation": activation,
        "invalidation": invalidation,
        "result": result,
        "marker_count": len(markers),
    }


def validate_observation_binding(
    observation: dict[str, Any], transcript: dict[str, Any]
) -> dict[str, Any]:
    try:
        derived = native_kernel_physical_memory.derive_memory_summary(transcript)
    except native_kernel_physical_memory.KernelPhysicalMemoryError as error:
        raise KernelVirtualMemoryError(str(error)) from error
    entries = transcript.get("memory_entries")
    if not isinstance(entries, list):
        raise KernelVirtualMemoryError("PKVM3 PBP1 memory map is missing")
    ranges: list[list[int]] = []
    for entry in entries:
        if not isinstance(entry, dict) or int(entry.get("kind", -1)) != 1:
            continue
        start_page = int(str(entry["physical_start"]), 16) // PAGE_BYTES
        page_count = int(entry["page_count"])
        if start_page == 0:
            start_page = 1
            page_count -= 1
        if page_count <= 0:
            continue
        if ranges and ranges[-1][0] + ranges[-1][1] == start_page:
            ranges[-1][1] += page_count
        else:
            ranges.append([start_page, page_count])
    if not ranges:
        raise KernelVirtualMemoryError("PKVM3 has no PMM-admitted direct-map ranges")
    mapped_pages = sum(item[1] for item in ranges)
    gap_pages = sum(
        ranges[index][0] - (ranges[index - 1][0] + ranges[index - 1][1])
        for index in range(1, len(ranges))
    )
    first_page = ranges[0][0]
    end_page = ranges[-1][0] + ranges[-1][1]
    regions = sorted(
        {
            region
            for start_page, page_count in ranges
            for region in range(start_page // 512, (start_page + page_count - 1) // 512 + 1)
        }
    )
    directories = sorted({region // 512 for region in regions})
    table_pages = 5 + len(directories) + len(regions)
    coverage_checksum = 0xCBF29CE484222325
    for value in (
        1,
        len(ranges),
        mapped_pages,
        0,
        gap_pages,
        first_page,
        end_page,
    ):
        coverage_checksum = native_kernel_physical_memory._fnv_u64(coverage_checksum, value)
    for start_page, page_count in ranges:
        for value in (start_page, page_count, 0):
            coverage_checksum = native_kernel_physical_memory._fnv_u64(coverage_checksum, value)

    first_dma32 = derived["first_free_address"][1]
    layout = observation["layout"]
    candidate = observation["candidate"]
    if first_dma32 == 0 or candidate["candidate_root"] != first_dma32:
        raise KernelVirtualMemoryError("PKVM3 candidate root is not deterministic DMA32 first-fit")
    expected_layout = {
        "table_pages": table_pages,
        "direct_directory_tables": len(directories),
        "direct_page_tables": len(regions),
        "mapped_pages": mapped_pages,
    }
    if layout != expected_layout:
        raise KernelVirtualMemoryError(
            f"PKVM3 sparse topology differs from PMM ownership: expected={expected_layout}, observed={layout}"
        )
    expected_candidate = {
        "data": first_dma32 + table_pages * PAGE_BYTES,
        "direct_first": DIRECT_MAP_START + first_page * PAGE_BYTES,
        "direct_last": DIRECT_MAP_START + end_page * PAGE_BYTES - 1,
        "direct_generation": 1,
        "direct_ranges": len(ranges),
        "gap_pages": gap_pages,
        "retained_excluded_pages": 0,
        "coverage_checksum": coverage_checksum,
    }
    changed = {
        key: {"expected": value, "observed": candidate.get(key)}
        for key, value in expected_candidate.items()
        if candidate.get(key) != value
    }
    if changed:
        raise KernelVirtualMemoryError(f"PKVM3 PMM coverage binding changed: {changed}")
    derived["direct_map"] = {
        "ranges": [
            {"start_page": start_page, "page_count": page_count, "cache": "write_back"}
            for start_page, page_count in ranges
        ],
        "mapped_pages": mapped_pages,
        "gap_pages": gap_pages,
        "first_page": first_page,
        "end_page": end_page,
        "direct_page_tables": len(regions),
        "direct_directory_tables": len(directories),
        "table_pages": table_pages,
        "coverage_checksum": coverage_checksum,
    }
    return derived
