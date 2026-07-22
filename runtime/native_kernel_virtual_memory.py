"""Independent PKVM1 oracle for the bounded virtual-memory foundation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_physical_memory, native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKVM1"
SELECTED_MOVE_ID = "N9-VM-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-virtual-memory-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-virtual-memory-contract.schema.json"
SCHEMA_RELATIVE = "specs/native-kernel-virtual-memory-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-virtual-memory-readiness.json"
FEATURE = "development-virtual-memory"
SELECTOR = 9
MARKER_COUNT = 40
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 31
COMMON_KERNEL_MARKER_COUNT = 4
PAGE_BYTES = 4096
TABLE_PAGES = 4
PHYSICAL_WRITES = 4104
TEMPORARY_PTE_WRITES = 40
HARDWARE_INVALIDATIONS = 40
COMPLETION_MARKER = b"POOLEOS:KERNEL:VM-RESULT PASS contract=PKVM1"

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
    "NEG-N9-PKVM-MARKER-OMISSION",
    "NEG-N9-PKVM-MARKER-ORDER",
    "NEG-N9-PKVM-MARKER-DUPLICATE",
    "NEG-N9-PKVM-SELECTOR",
    "NEG-N9-PKVM-CONTRACT",
    "NEG-N9-PKVM-LAYOUT",
    "NEG-N9-PKVM-ROOT-ALIGNMENT",
    "NEG-N9-PKVM-TABLE-GENERATION",
    "NEG-N9-PKVM-DATA-CONTIGUITY",
    "NEG-N9-PKVM-DATA-GENERATION",
    "NEG-N9-PKVM-TABLE-PAGES",
    "NEG-N9-PKVM-MATERIALIZED",
    "NEG-N9-PKVM-TEMPORARY-VERIFY",
    "NEG-N9-PKVM-ROOT-ACTIVE",
    "NEG-N9-PKVM-TRANSLATION",
    "NEG-N9-PKVM-MAPPED-PERMISSIONS",
    "NEG-N9-PKVM-PROTECTED-PERMISSIONS",
    "NEG-N9-PKVM-CACHE",
    "NEG-N9-PKVM-PAGE-BYTES",
    "NEG-N9-PKVM-MAPS",
    "NEG-N9-PKVM-PROTECTS",
    "NEG-N9-PKVM-UNMAPS",
    "NEG-N9-PKVM-RECEIPTS",
    "NEG-N9-PKVM-CACHE-ALIAS",
    "NEG-N9-PKVM-WX",
    "NEG-N9-PKVM-PREMATURE-REUSE",
    "NEG-N9-PKVM-ROLLBACK",
    "NEG-N9-PKVM-ROOT-RELEASE",
    "NEG-N9-PKVM-DATA-RELEASE",
    "NEG-N9-PKVM-ALLOCATED-RESIDUE",
    "NEG-N9-PKVM-PHYSICAL-WRITES",
    "NEG-N9-PKVM-TEMPORARY-PTE-WRITES",
    "NEG-N9-PKVM-ALLOCATION-COUNT",
    "NEG-N9-PKVM-FREE-COUNT",
    "NEG-N9-PKVM-ACTIVE-CR3",
    "NEG-N9-PKVM-INVLPG",
    "NEG-N9-PKVM-SHOOTDOWN",
    "NEG-N9-PKVM-OVERCLAIM",
    "NEG-N9-PKVM-PBP1-FIRST-FIT",
)

LAYOUT_MARKER = (
    "POOLEOS:KERNEL:VM-LAYOUT PASS contract=PKVM1 canonical_bits=48 "
    "null_guard_end=0x0000000000010000 user_end=0x0000800000000000 "
    "kernel_start=0xFFFF800000000000 direct_start=0xFFFF900000000000 "
    "direct_end=0xFFFFD00000000000 temp_start=0xFFFFFFFF80150000 "
    "temp_end=0xFFFFFFFF80151000 kernel_image_start=0xFFFFFFFF80000000 "
    "kernel_image_end=0xFFFFFFFFC0000000 window_start=0x0000000040000000 window_pages=512"
)
EARLY = re.compile(
    r"^POOLEOS:KERNEL:VM-EARLY PASS contract=(PKVM1) selector=(9) "
    r"stack=(validated_by_wrapper) serial=(initialized)$"
)
STAGE = re.compile(r"^POOLEOS:KERNEL:VM-STAGE PASS contract=(PKVM1) stage=([1-5])$")
HEX = r"(0x[0-9A-F]{16})"
DEC = r"([0-9]+)"
TABLES = re.compile(
    rf"^POOLEOS:KERNEL:VM-TABLES PASS contract=(PKVM1) root={HEX} "
    rf"table_generation={DEC} data={HEX} data_generation={DEC} table_pages={DEC} "
    rf"materialized={DEC} temporary_verified={DEC} root_active=([01])$"
)
TRANSLATION = re.compile(
    rf"^POOLEOS:KERNEL:VM-TRANSLATION PASS contract=(PKVM1) mapped_physical={HEX} "
    r"mapped_permissions=(rw_nx_user) protected_permissions=(rx_user) "
    rf"cache=(write_back) page_bytes={DEC}$"
)
TRANSACTION = re.compile(
    rf"^POOLEOS:KERNEL:VM-TRANSACTION PASS contract=(PKVM1) maps={DEC} protects={DEC} "
    rf"unmaps={DEC} inactive_receipts={DEC} cache_alias_rejected={DEC} wx_rejected={DEC} "
    rf"premature_reuse_rejected={DEC} rollback_controls=(host_verified)$"
)
RESULT = re.compile(
    rf"^POOLEOS:KERNEL:VM-RESULT PASS contract=(PKVM1) profile=(qemu64_tier0) "
    rf"root_released={DEC} data_released={DEC} allocated_pages={DEC} physical_writes={DEC} "
    rf"temporary_pte_writes={DEC} "
    rf"allocations={DEC} frees={DEC} active_cr3_writes={DEC} invlpg={DEC} shootdown={DEC} "
    rf"huge_pages={DEC} cow={DEC} user_faults={DEC} pager={DEC} heap={DEC} smp={DEC} "
    rf"signatures={DEC} authority={DEC} actions={DEC} production={DEC} terminal=(halt)$"
)


class KernelVirtualMemoryError(ValueError):
    """Raised when PKVM1 evidence violates the frozen contract."""


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
        "live_pmm_generation_bound_table_and_data_frames": True,
        "four_level_4k_page_tables_materialized_in_physical_ram": True,
        "bounded_map_protect_unmap_implemented": True,
        "writable_executable_and_cache_alias_rejection_exercised": True,
        "transactional_leaf_rollback_host_tested": True,
        "inactive_root_invalidation_receipts_exercised": True,
        "frame_reuse_before_all_alias_receipts_rejected": True,
        "active_root_installed": False,
        "hardware_tlb_invalidation_executed": True,
        "smp_shootdown_implemented": False,
        "huge_pages_cow_user_faults_or_pager_implemented": False,
        "bootstrap_temporary_mapping_activated_and_revoked": True,
        "kernel_direct_map_activated": False,
        "n9_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if (contract.get("contract_id"), contract.get("selected_move_id")) != (CONTRACT_ID, SELECTED_MOVE_ID):
        errors.append("PKVM1 contract identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, "qemu64", True):
        errors.append("PKVM1 development profile changed")
    limits = contract.get("limits", {})
    if not isinstance(limits, dict) or tuple(
        limits.get(key) for key in ("table_pages", "mappings", "frames", "pending_invalidations", "page_bytes")
    ) != (4, 8, 4, 8, 4096):
        errors.append("PKVM1 bounded capacities changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKVM1 hostile-control inventory changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKVM1 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKVM1 contract overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    errors.extend(contract_errors(read_json(root / CONTRACT_RELATIVE), root))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKVM1 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key) for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKVM1 exact two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKVM1 hostile-control evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKVM1 readiness claims changed")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("PKVM1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelVirtualMemoryError(f"PKVM1 {name} marker violates its contract: {marker!r}")
    return match


def _prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelVirtualMemoryError("PKVM1 transfer selector changed")
    baseline = [
        *markers[:BOOT_TRANSFER_MARKER_COUNT],
        *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT],
    ]
    baseline[23] = re.sub(r"trap_scenario=[0-9]", "trap_scenario=0", baseline[23], count=1)
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
        raise KernelVirtualMemoryError(f"expected {MARKER_COUNT} PKVM1 markers, observed {len(markers)}")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    stages = [_match(STAGE, markers[26 + index], "stage") for index in range(5)]
    if [int(item.group(2)) for item in stages] != [1, 2, 3, 4, 5]:
        raise KernelVirtualMemoryError("PKVM1 stage order changed")
    if markers[35] != LAYOUT_MARKER:
        raise KernelVirtualMemoryError("PKVM1 layout marker changed")
    tables_match = _match(TABLES, markers[36], "tables")
    translation_match = _match(TRANSLATION, markers[37], "translation")
    transaction_match = _match(TRANSACTION, markers[38], "transaction")
    result_match = _match(RESULT, markers[39], "result")
    tables = {
        "root": int(tables_match.group(2), 16),
        "table_generation": int(tables_match.group(3)),
        "data": int(tables_match.group(4), 16),
        "data_generation": int(tables_match.group(5)),
        "table_pages": int(tables_match.group(6)),
        "materialized": int(tables_match.group(7)),
        "temporary_verified": int(tables_match.group(8)),
        "root_active": int(tables_match.group(9)),
    }
    translation = {
        "mapped_physical": int(translation_match.group(2), 16),
        "mapped_permissions": translation_match.group(3),
        "protected_permissions": translation_match.group(4),
        "cache": translation_match.group(5),
        "page_bytes": int(translation_match.group(6)),
    }
    transaction = {
        "maps": int(transaction_match.group(2)),
        "protects": int(transaction_match.group(3)),
        "unmaps": int(transaction_match.group(4)),
        "inactive_receipts": int(transaction_match.group(5)),
        "cache_alias_rejected": int(transaction_match.group(6)),
        "wx_rejected": int(transaction_match.group(7)),
        "premature_reuse_rejected": int(transaction_match.group(8)),
        "rollback_controls": transaction_match.group(9),
    }
    names = (
        "root_released", "data_released", "allocated_pages", "physical_writes",
        "temporary_pte_writes",
        "allocations", "frees", "active_cr3_writes", "invlpg", "shootdown",
        "huge_pages", "cow", "user_faults", "pager", "heap", "smp", "signatures",
        "authority", "actions", "production",
    )
    result = {name: int(result_match.group(index + 3)) for index, name in enumerate(names)}
    result["terminal"] = result_match.group(23)
    if (
        tables["root"] % PAGE_BYTES
        or tables["data"] != tables["root"] + TABLE_PAGES * PAGE_BYTES
        or tuple(tables[key] for key in ("table_generation", "data_generation", "table_pages", "materialized", "temporary_verified", "root_active"))
        != (1, 2, 4, 4, 4, 0)
    ):
        raise KernelVirtualMemoryError("PKVM1 table ownership changed")
    if translation != {
        "mapped_physical": tables["data"],
        "mapped_permissions": "rw_nx_user",
        "protected_permissions": "rx_user",
        "cache": "write_back",
        "page_bytes": PAGE_BYTES,
    }:
        raise KernelVirtualMemoryError("PKVM1 translation changed")
    if tuple(transaction.values()) != (2, 1, 2, 2, 1, 1, 1, "host_verified"):
        raise KernelVirtualMemoryError("PKVM1 transaction proof changed")
    expected_result = {
        "root_released": 1, "data_released": 1, "allocated_pages": 0,
        "physical_writes": PHYSICAL_WRITES, "temporary_pte_writes": TEMPORARY_PTE_WRITES,
        "allocations": 2, "frees": 2,
        "active_cr3_writes": 0, "invlpg": HARDWARE_INVALIDATIONS,
        "shootdown": 0, "huge_pages": 0,
        "cow": 0, "user_faults": 0, "pager": 0, "heap": 0, "smp": 0,
        "signatures": 0, "authority": 0, "actions": 0, "production": 0,
        "terminal": "halt",
    }
    if result != expected_result:
        raise KernelVirtualMemoryError("PKVM1 result boundary changed")
    return {
        "transfer_prefix": prefix,
        "early": {"selector": int(early.group(2)), "stack": early.group(3), "serial": early.group(4)},
        "stages": [1, 2, 3, 4, 5],
        "layout": LAYOUT_MARKER,
        "tables": tables,
        "translation": translation,
        "transaction": transaction,
        "result": result,
        "marker_count": len(markers),
    }


def validate_observation_binding(observation: dict[str, Any], transcript: dict[str, Any]) -> dict[str, Any]:
    try:
        derived = native_kernel_physical_memory.derive_memory_summary(transcript)
    except native_kernel_physical_memory.KernelPhysicalMemoryError as error:
        raise KernelVirtualMemoryError(str(error)) from error
    first_dma32 = derived["first_free_address"][1]
    if first_dma32 == 0 or observation["tables"]["root"] != first_dma32:
        raise KernelVirtualMemoryError("PKVM1 root is not deterministic DMA32 first-fit")
    if observation["tables"]["data"] != first_dma32 + TABLE_PAGES * PAGE_BYTES:
        raise KernelVirtualMemoryError("PKVM1 data frame is not contiguous second allocation")
    return derived
