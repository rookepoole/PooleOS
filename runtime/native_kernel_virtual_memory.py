"""Independent PKVM2 oracle for bounded active-root virtual memory."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_physical_memory, native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKVM2"
SELECTED_MOVE_ID = "N9-VM-ACTIVE-001"
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
TABLE_PAGES = 8
OWNED_PAGES = 9
PHYSICAL_WRITES = 8720
TEMPORARY_PTE_WRITES = 5528
BOOTSTRAP_INVALIDATIONS = 5528
ACTIVE_CR3_WRITES = 2
ACTIVE_INVALIDATIONS = 3
DIRECT_MAP_START = 0xFFFF_9000_0000_0000
COMPLETION_MARKER = b"POOLEOS:KERNEL:ACTIVE-VM-RESULT PASS contract=PKVM2"

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
    "NEG-N9-PKVM2-MARKER-OMISSION",
    "NEG-N9-PKVM2-MARKER-ORDER",
    "NEG-N9-PKVM2-MARKER-DUPLICATE",
    "NEG-N9-PKVM2-SELECTOR",
    "NEG-N9-PKVM2-CONTRACT",
    "NEG-N9-PKVM2-LAYOUT",
    "NEG-N9-PKVM2-ORIGINAL-ROOT",
    "NEG-N9-PKVM2-CANDIDATE-ALIGNMENT",
    "NEG-N9-PKVM2-TABLE-GENERATION",
    "NEG-N9-PKVM2-DATA-CONTIGUITY",
    "NEG-N9-PKVM2-DATA-GENERATION",
    "NEG-N9-PKVM2-DIRECT-FIRST",
    "NEG-N9-PKVM2-DIRECT-LAST",
    "NEG-N9-PKVM2-INHERITED-KERNEL",
    "NEG-N9-PKVM2-GUARDED-STACK",
    "NEG-N9-PKVM2-HANDOFF",
    "NEG-N9-PKVM2-BOOTSTRAP-REVOCATION",
    "NEG-N9-PKVM2-PRE-ACTIVE-STATE",
    "NEG-N9-PKVM2-CR3-WRITES",
    "NEG-N9-PKVM2-CANDIDATE-READBACK",
    "NEG-N9-PKVM2-ORIGINAL-RESTORE",
    "NEG-N9-PKVM2-ROLLBACK-CONTROL",
    "NEG-N9-PKVM2-BSP",
    "NEG-N9-PKVM2-ACTIVATION-SMP",
    "NEG-N9-PKVM2-LOCAL-INVLPG",
    "NEG-N9-PKVM2-ACTIVE-RECEIPTS",
    "NEG-N9-PKVM2-PROBE",
    "NEG-N9-PKVM2-PROTECT",
    "NEG-N9-PKVM2-USER-UNMAP",
    "NEG-N9-PKVM2-DIRECT-UNMAP",
    "NEG-N9-PKVM2-STALE-ROOT",
    "NEG-N9-PKVM2-PREMATURE-REUSE",
    "NEG-N9-PKVM2-INVALIDATION-SHOOTDOWN",
    "NEG-N9-PKVM2-ROOT-RELEASE",
    "NEG-N9-PKVM2-DATA-RELEASE",
    "NEG-N9-PKVM2-ALLOCATED-RESIDUE",
    "NEG-N9-PKVM2-PHYSICAL-WRITES",
    "NEG-N9-PKVM2-TEMPORARY-PTE-WRITES",
    "NEG-N9-PKVM2-BOOTSTRAP-INVLPG",
    "NEG-N9-PKVM2-ALLOCATION-COUNT",
    "NEG-N9-PKVM2-FREE-COUNT",
    "NEG-N9-PKVM2-RESULT-CR3",
    "NEG-N9-PKVM2-RESULT-INVLPG",
    "NEG-N9-PKVM2-SHOOTDOWN",
    "NEG-N9-PKVM2-OVERCLAIM",
    "NEG-N9-PKVM2-PBP1-FIRST-FIT",
)

LAYOUT_MARKER = (
    "POOLEOS:KERNEL:ACTIVE-VM-LAYOUT PASS contract=PKVM2 canonical_bits=48 "
    "direct_start=0xFFFF900000000000 direct_end=0xFFFFD00000000000 "
    "user_start=0x0000000040000000 page_bytes=4096 table_pages=8 owned_pages=9"
)
EARLY = re.compile(
    r"^POOLEOS:KERNEL:ACTIVE-VM-EARLY PASS contract=(PKVM2) selector=(10) "
    r"bsp=(1) if=(0) stack=(validated_by_wrapper) serial=(initialized)$"
)
STAGE = re.compile(
    r"^POOLEOS:KERNEL:ACTIVE-VM-STAGE PASS contract=(PKVM2) stage=([1-5])$"
)
HEX = r"(0x[0-9A-F]{16})"
DEC = r"([0-9]+)"
CANDIDATE = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-CANDIDATE PASS contract=(PKVM2) original_root={HEX} "
    rf"candidate_root={HEX} table_generation={DEC} data={HEX} data_generation={DEC} "
    rf"direct_first={HEX} direct_last={HEX} inherited_kernel=(exact) guarded_stack=(exact) "
    rf"handoff=(exact) bootstrap_alias_revoked={DEC} root_active={DEC}$"
)
ACTIVATION = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-ACTIVATION PASS contract=(PKVM2) cr3_writes={DEC} "
    r"candidate_readback=(exact) original_restore=(exact) rollback_control=(host_verified) "
    rf"bsp={DEC} smp={DEC}$"
)
INVALIDATION = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-INVALIDATION PASS contract=(PKVM2) local_invlpg={DEC} "
    rf"active_receipts={DEC} probe={HEX} protect={DEC} user_unmap={DEC} direct_unmap={DEC} "
    rf"stale_root_rejected=(host) premature_reuse_rejected={DEC} shootdown={DEC}$"
)
RESULT = re.compile(
    rf"^POOLEOS:KERNEL:ACTIVE-VM-RESULT PASS contract=(PKVM2) profile=(qemu64_tier0) "
    rf"root_released={DEC} data_released={DEC} allocated_pages={DEC} physical_writes={DEC} "
    rf"temporary_pte_writes={DEC} bootstrap_invlpg={DEC} allocations={DEC} frees={DEC} "
    rf"active_cr3_writes={DEC} active_invlpg={DEC} shootdown={DEC} ring3={DEC} "
    rf"huge_pages={DEC} pcid={DEC} cow={DEC} user_faults={DEC} pager={DEC} heap={DEC} "
    rf"smp={DEC} signatures={DEC} authority={DEC} actions={DEC} production={DEC} terminal=(halt)$"
)


class KernelVirtualMemoryError(ValueError):
    """Raised when PKVM2 evidence violates the frozen contract."""


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
        "bounded_owned_page_direct_map_activated": True,
        "one_bsp_candidate_root_installed_and_restored": True,
        "active_address_space_local_invalidation_receipts_exercised": True,
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
        errors.append("PKVM2 contract identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, "qemu64", True):
        errors.append("PKVM2 development profile changed")
    limits = contract.get("limits", {})
    if not isinstance(limits, dict) or tuple(
        limits.get(key)
        for key in (
            "table_pages",
            "mapped_owned_pages",
            "page_bytes",
            "cr3_writes",
            "active_local_invalidations",
        )
    ) != (TABLE_PAGES, OWNED_PAGES, PAGE_BYTES, ACTIVE_CR3_WRITES, ACTIVE_INVALIDATIONS):
        errors.append("PKVM2 bounded capacities changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKVM2 hostile-control inventory changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKVM2 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get(
        "production_promotion_allowed"
    ) is not False:
        errors.append("PKVM2 contract overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    errors.extend(contract_errors(read_json(root / CONTRACT_RELATIVE), root))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKVM2 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key)
        for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKVM2 exact two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)]
        != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKVM2 hostile-control evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKVM2 readiness claims changed")
    if readiness.get("production_ready") is not False or readiness.get(
        "production_promotion_allowed"
    ) is not False:
        errors.append("PKVM2 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelVirtualMemoryError(f"PKVM2 {name} marker violates its contract: {marker!r}")
    return match


def _prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelVirtualMemoryError("PKVM2 transfer selector changed")
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
        raise KernelVirtualMemoryError(f"expected {MARKER_COUNT} PKVM2 markers, observed {len(markers)}")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    stages = [_match(STAGE, markers[26 + index], "stage") for index in range(5)]
    if [int(item.group(2)) for item in stages] != [1, 2, 3, 4, 5]:
        raise KernelVirtualMemoryError("PKVM2 stage order changed")
    if markers[35] != LAYOUT_MARKER:
        raise KernelVirtualMemoryError("PKVM2 layout marker changed")
    candidate_match = _match(CANDIDATE, markers[36], "candidate")
    activation_match = _match(ACTIVATION, markers[37], "activation")
    invalidation_match = _match(INVALIDATION, markers[38], "invalidation")
    result_match = _match(RESULT, markers[39], "result")

    candidate = {
        "original_root": int(candidate_match.group(2), 16),
        "candidate_root": int(candidate_match.group(3), 16),
        "table_generation": int(candidate_match.group(4)),
        "data": int(candidate_match.group(5), 16),
        "data_generation": int(candidate_match.group(6)),
        "direct_first": int(candidate_match.group(7), 16),
        "direct_last": int(candidate_match.group(8), 16),
        "inherited_kernel": candidate_match.group(9),
        "guarded_stack": candidate_match.group(10),
        "handoff": candidate_match.group(11),
        "bootstrap_alias_revoked": int(candidate_match.group(12)),
        "root_active": int(candidate_match.group(13)),
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
        "shootdown": int(invalidation_match.group(10)),
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
        raise KernelVirtualMemoryError("PKVM2 original root differs from PKXFER1")
    if (
        candidate["candidate_root"] % PAGE_BYTES
        or candidate["candidate_root"] == candidate["original_root"]
        or candidate["data"] != candidate["candidate_root"] + TABLE_PAGES * PAGE_BYTES
        or candidate["table_generation"] != 1
        or candidate["data_generation"] != 2
        or candidate["direct_first"] != DIRECT_MAP_START + candidate["candidate_root"]
        or candidate["direct_last"] != DIRECT_MAP_START + candidate["data"] + PAGE_BYTES - 1
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
        raise KernelVirtualMemoryError("PKVM2 candidate ownership or inheritance changed")
    if tuple(activation.values()) != (2, "exact", "exact", "host_verified", 1, 0):
        raise KernelVirtualMemoryError("PKVM2 activation proof changed")
    if tuple(invalidation.values()) != (3, 3, 0xA5, 1, 1, 1, "host", 1, 0):
        raise KernelVirtualMemoryError("PKVM2 invalidation proof changed")
    expected_result = {
        "root_released": 1,
        "data_released": 1,
        "allocated_pages": 0,
        "physical_writes": PHYSICAL_WRITES,
        "temporary_pte_writes": TEMPORARY_PTE_WRITES,
        "bootstrap_invlpg": BOOTSTRAP_INVALIDATIONS,
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
        raise KernelVirtualMemoryError(f"PKVM2 result boundary changed: {changed}")
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
        "layout": LAYOUT_MARKER,
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
    first_dma32 = derived["first_free_address"][1]
    candidate = observation["candidate"]
    if first_dma32 == 0 or candidate["candidate_root"] != first_dma32:
        raise KernelVirtualMemoryError("PKVM2 candidate root is not deterministic DMA32 first-fit")
    if candidate["data"] != first_dma32 + TABLE_PAGES * PAGE_BYTES:
        raise KernelVirtualMemoryError("PKVM2 data frame is not contiguous second allocation")
    return derived
