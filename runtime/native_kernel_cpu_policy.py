"""Independent PKCPU1 oracle for read-only BSP CPU policy evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKCPU1"
SELECTED_MOVE_ID = "N7-CPU-POLICY-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-cpu-policy-contract.json"
SCHEMA_RELATIVE = "specs/native-kernel-cpu-policy-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-cpu-policy-readiness.json"
MARKER_COUNT = 35
PREFIX_MARKER_COUNT = 29
SELECTOR = 4
FEATURE = "development-cpu-policy"
COMPLETION_MARKER = b"POOLEOS:KERNEL:CPU-RESULT PASS contract=PKCPU1"

REQUIRED_LEAF1_EDX = (
    (1 << 0)
    | (1 << 4)
    | (1 << 5)
    | (1 << 6)
    | (1 << 8)
    | (1 << 9)
    | (1 << 12)
    | (1 << 13)
    | (1 << 15)
    | (1 << 16)
    | (1 << 24)
    | (1 << 25)
    | (1 << 26)
)
REQUIRED_EXT1_EDX = (1 << 11) | (1 << 20) | (1 << 29)
REQUIRED_CR0 = (1 << 0) | (1 << 1) | (1 << 4) | (1 << 5) | (1 << 16) | (1 << 31)
FORBIDDEN_CR0 = (1 << 2) | (1 << 3) | (1 << 29) | (1 << 30)
REQUIRED_CR4 = (1 << 5) | (1 << 9) | (1 << 10)
FORBIDDEN_CR4 = (1 << 12) | (1 << 13) | (1 << 14) | (1 << 22) | (1 << 23) | (1 << 24)
REQUIRED_EFER = (1 << 8) | (1 << 10) | (1 << 11)
ALLOWED_EFER = (1 << 0) | (1 << 8) | (1 << 10) | (1 << 11) | (1 << 12) | (1 << 13) | (1 << 14) | (1 << 15)
MSR_READ_MASK = 0x1F

IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/manifest.pkm",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "runtime/native_kernel_cpu_policy.py",
    "runtime/native_kernel_transfer.py",
    "tools/qualify_native_kernel_cpu_policy.py",
    "tests/test_native_kernel_cpu_policy.py",
    "docs/native-kernel-cpu-policy.md",
    "runs/native_kernel_entry_readiness.json",
    "runs/native-kernel-revalidation-readiness.json",
    "runs/native_kernel_load_readiness.json",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N7-PKCPU-MARKER-OMISSION",
    "NEG-N7-PKCPU-MARKER-ORDER",
    "NEG-N7-PKCPU-MARKER-DUPLICATE",
    "NEG-N7-PKCPU-SELECTOR",
    "NEG-N7-PKCPU-CONTRACT",
    "NEG-N7-PKCPU-VENDOR",
    "NEG-N7-PKCPU-BRAND",
    "NEG-N7-PKCPU-MAX-BASIC",
    "NEG-N7-PKCPU-MAX-EXTENDED",
    "NEG-N7-PKCPU-IDENTITY-FAMILY",
    "NEG-N7-PKCPU-IDENTITY-MODEL",
    "NEG-N7-PKCPU-IDENTITY-STEPPING",
    "NEG-N7-PKCPU-LOGICAL-COUNT",
    "NEG-N7-PKCPU-PHYSICAL-WIDTH",
    "NEG-N7-PKCPU-LINEAR-WIDTH",
    "NEG-N7-PKCPU-TOPOLOGY-ID",
    "NEG-N7-PKCPU-LEAF1-REQUIRED",
    "NEG-N7-PKCPU-EXT1-REQUIRED",
    "NEG-N7-PKCPU-CR0-REQUIRED",
    "NEG-N7-PKCPU-CR0-FORBIDDEN",
    "NEG-N7-PKCPU-CR4-REQUIRED",
    "NEG-N7-PKCPU-CR4-FORBIDDEN",
    "NEG-N7-PKCPU-FEATURE-GATE",
    "NEG-N7-PKCPU-OSXSAVE-CONSISTENCY",
    "NEG-N7-PKCPU-XCR0-BASELINE",
    "NEG-N7-PKCPU-EFER-REQUIRED",
    "NEG-N7-PKCPU-EFER-RESERVED",
    "NEG-N7-PKCPU-MSR-READ-ALLOWLIST",
    "NEG-N7-PKCPU-APIC-ENABLE",
    "NEG-N7-PKCPU-APIC-RESERVED",
    "NEG-N7-PKCPU-PAT-TYPE",
    "NEG-N7-PKCPU-MTRR-CAP",
    "NEG-N7-PKCPU-MTRR-DEFAULT",
    "NEG-N7-PKCPU-RESULT-PROFILE",
    "NEG-N7-PKCPU-RESULT-READS",
    "NEG-N7-PKCPU-RESULT-WRITES",
    "NEG-N7-PKCPU-RESULT-SIGNATURES",
    "NEG-N7-PKCPU-RESULT-AUTHORITY",
    "NEG-N7-PKCPU-RESULT-ACTIONS",
    "NEG-N7-PKCPU-RESULT-INTERRUPTS",
    "NEG-N7-PKCPU-RESULT-TERMINAL",
)

HEX64 = r"(0x[0-9A-F]{16})"
DISCOVERY = re.compile(
    r"^POOLEOS:KERNEL:CPU-DISCOVERY OBSERVE contract=(PKCPU1) "
    r"vendor_hex=([0-9A-F]{24}) brand_hex=([0-9A-F]{96}) "
    rf"max_basic={HEX64} max_extended={HEX64} signature={HEX64} "
    r"family=([0-9]+) model=([0-9]+) stepping=([0-9]+) logical=([0-9]+) "
    r"apic_id=([0-9]+) physical_width=([0-9]+) linear_width=([0-9]+)$"
)
TOPOLOGY = re.compile(
    rf"^POOLEOS:KERNEL:CPU-TOPOLOGY OBSERVE contract=(PKCPU1) leaf4_eax={HEX64} "
    rf"leaf4_ebx={HEX64} leaf4_ecx={HEX64} leaf4_edx={HEX64} leafb0_eax={HEX64} "
    rf"leafb0_ebx={HEX64} leafb0_ecx={HEX64} leafb0_edx={HEX64} ext6_ecx={HEX64}$"
)
FEATURES = re.compile(
    rf"^POOLEOS:KERNEL:CPU-FEATURES OBSERVE contract=(PKCPU1) leaf1_ecx={HEX64} "
    rf"leaf1_edx={HEX64} leaf6_eax={HEX64} leaf7_ebx={HEX64} leaf7_ecx={HEX64} "
    rf"leaf7_edx={HEX64} leafa_eax={HEX64} ext1_ecx={HEX64} ext1_edx={HEX64} "
    rf"ext7_edx={HEX64} ext1f_eax={HEX64}$"
)
XSAVE = re.compile(
    rf"^POOLEOS:KERNEL:CPU-XSAVE OBSERVE contract=(PKCPU1) leafd0_eax={HEX64} "
    rf"leafd0_ebx={HEX64} leafd0_ecx={HEX64} leafd0_edx={HEX64} xcr0={HEX64} "
    r"ownership=(observation_only)$"
)
STATE = re.compile(
    rf"^POOLEOS:KERNEL:CPU-STATE OBSERVE contract=(PKCPU1) cr0={HEX64} cr4={HEX64} "
    rf"efer={HEX64} apic_base={HEX64} pat={HEX64} mtrr_cap={HEX64} "
    rf"mtrr_def={HEX64} msr_read_mask={HEX64}$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:CPU-RESULT PASS contract=(PKCPU1) profile=(qemu64_tier0) "
    r"bsp=([01]) policy=(required_and_support_gated) reads=(cpuid_cr_msr) writes=([0-9]+) "
    r"signatures=([0-9]+) authority=([0-9]+) actions=([0-9]+) interrupts=([01]) "
    r"terminal=(halt)$"
)


class KernelCpuPolicyError(ValueError):
    """Raised when PKCPU1 evidence violates its bounded contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelCpuPolicyError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelCpuPolicyError("binding path escapes the repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "tier0_lock": file_binding(root / "specs/native-tier0-lock.json", root),
        "tier0_profile": file_binding(root / "specs/native-tier0-profile.json", root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "cpuid_vendor_brand_identity_observed": True,
        "cpuid_feature_and_width_policy_observed": True,
        "topology_cache_and_optional_facilities_observed": True,
        "cr0_cr4_efer_read_only_policy_observed": True,
        "support_gated_xcr0_observed": True,
        "allowlisted_apic_pat_mtrr_msrs_observed": True,
        "rust_python_policy_agreement": True,
        "two_qemu_runs_exact_match": True,
        "cpu_state_writes_performed": False,
        "microcode_or_errata_policy_complete": False,
        "xsave_context_ownership_complete": False,
        "target_cpu_qualified": False,
        "n7_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if (contract.get("contract_id"), contract.get("selected_move_id")) != (
        CONTRACT_ID,
        SELECTED_MOVE_ID,
    ):
        errors.append("PKCPU1 contract identity changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKCPU1 contract overclaims production")
    profile = contract.get("cpu_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key)
        for key in ("feature", "selector", "tier0_cpu_model", "bsp_only", "read_only")
    ) != (FEATURE, SELECTOR, "qemu64", True, True):
        errors.append("PKCPU1 development profile changed")
    policy = contract.get("policy", {})
    if not isinstance(policy, dict) or tuple(
        policy.get(key)
        for key in (
            "required_leaf1_edx",
            "required_ext1_edx",
            "required_cr0",
            "forbidden_cr0",
            "required_cr4",
            "forbidden_cr4",
            "required_efer",
            "msr_read_mask",
        )
    ) != (
        REQUIRED_LEAF1_EDX,
        REQUIRED_EXT1_EDX,
        REQUIRED_CR0,
        FORBIDDEN_CR0,
        REQUIRED_CR4,
        FORBIDDEN_CR4,
        REQUIRED_EFER,
        MSR_READ_MASK,
    ):
        errors.append("PKCPU1 frozen bit policy changed")
    qualification = contract.get("qualification", {})
    if (
        not isinstance(qualification, dict)
        or qualification.get("qemu_run_count") != 2
        or qualification.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS)
        or contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS)
    ):
        errors.append("PKCPU1 qualification profile changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKCPU1 claim boundary changed")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKCPU1 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key)
        for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKCPU1 two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKCPU1 hostile-control evidence changed")
    summary = readiness.get("summary", {})
    if not isinstance(summary, dict) or tuple(
        summary.get(key)
        for key in (
            "qemu_run_count",
            "marker_count",
            "negative_controls_passed",
            "state_writes",
            "authority_grants",
            "production_claim_count",
        )
    ) != (2, MARKER_COUNT, len(NEGATIVE_CONTROL_IDS), 0, 0, 0):
        errors.append("PKCPU1 summary changed")
    if readiness.get("claims") != expected_claims() or readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PKCPU1 readiness claim boundary changed")
    if (
        readiness.get("production_ready") is not False
        or readiness.get("production_promotion_allowed") is not False
        or readiness.get("n7_exit_gate_satisfied") is not False
    ):
        errors.append("PKCPU1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelCpuPolicyError(f"PKCPU1 {name} marker violates its contract: {marker!r}")
    return match


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def _decode_identity(signature: int) -> tuple[int, int, int]:
    stepping = signature & 0x0F
    base_model = (signature >> 4) & 0x0F
    base_family = (signature >> 8) & 0x0F
    extended_model = (signature >> 16) & 0x0F
    extended_family = (signature >> 20) & 0xFF
    family = base_family + extended_family if base_family == 0x0F else base_family
    model = base_model | (extended_model << 4) if base_family in (0x06, 0x0F) else base_model
    return family, model, stepping


def _valid_brand(value: bytes) -> bool:
    printable = False
    nul_seen = False
    for byte in value:
        if byte == 0:
            nul_seen = True
        elif nul_seen or not 0x20 <= byte <= 0x7E:
            return False
        elif byte != 0x20:
            printable = True
    return printable


def _validate_prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelCpuPolicyError("PKCPU1 transfer selector changed")
    baseline = markers[:PREFIX_MARKER_COUNT]
    baseline[23] = re.sub(r"trap_scenario=[0-4]", "trap_scenario=0", baseline[23], count=1)
    terminal = (
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers([*baseline, terminal])
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelCpuPolicyError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelCpuPolicyError(f"expected {MARKER_COUNT} PKCPU1 markers, observed {len(markers)}")
    prefix = _validate_prefix(markers)
    discovery_match = _match(DISCOVERY, markers[29], "discovery")
    topology_match = _match(TOPOLOGY, markers[30], "topology")
    features_match = _match(FEATURES, markers[31], "features")
    xsave_match = _match(XSAVE, markers[32], "xsave")
    state_match = _match(STATE, markers[33], "state")
    result_match = _match(RESULT, markers[34], "result")

    vendor = bytes.fromhex(discovery_match.group(2))
    brand = bytes.fromhex(discovery_match.group(3))
    discovery = {
        "vendor": vendor.decode("ascii", errors="strict"),
        "brand_hex": discovery_match.group(3),
        "max_basic_leaf": _hex(discovery_match, 4),
        "max_extended_leaf": _hex(discovery_match, 5),
        "signature": _hex(discovery_match, 6),
        "family": int(discovery_match.group(7)),
        "model": int(discovery_match.group(8)),
        "stepping": int(discovery_match.group(9)),
        "logical_processors": int(discovery_match.group(10)),
        "apic_id": int(discovery_match.group(11)),
        "physical_width": int(discovery_match.group(12)),
        "linear_width": int(discovery_match.group(13)),
    }
    if vendor not in (b"AuthenticAMD", b"GenuineIntel") or not _valid_brand(brand):
        raise KernelCpuPolicyError("PKCPU1 vendor or brand is invalid")
    if discovery["max_basic_leaf"] < 7 or discovery["max_extended_leaf"] < 0x80000008:
        raise KernelCpuPolicyError("PKCPU1 CPUID leaf range is incomplete")
    if _decode_identity(discovery["signature"]) != (
        discovery["family"],
        discovery["model"],
        discovery["stepping"],
    ):
        raise KernelCpuPolicyError("PKCPU1 decoded identity changed")
    if not 36 <= discovery["physical_width"] <= 52 or discovery["linear_width"] != 48:
        raise KernelCpuPolicyError("PKCPU1 address-width policy failed")
    if discovery["logical_processors"] == 0:
        raise KernelCpuPolicyError("PKCPU1 topology count is zero")

    topology_values = [_hex(topology_match, index) for index in range(2, 11)]
    topology = dict(
        zip(
            ("leaf4_eax", "leaf4_ebx", "leaf4_ecx", "leaf4_edx", "leafb0_eax", "leafb0_ebx", "leafb0_ecx", "leafb0_edx", "ext6_ecx"),
            topology_values,
            strict=True,
        )
    )
    if topology["leafb0_ebx"] and topology["leafb0_edx"] != discovery["apic_id"]:
        raise KernelCpuPolicyError("PKCPU1 topology identifiers disagree")

    feature_values = [_hex(features_match, index) for index in range(2, 13)]
    features = dict(
        zip(
            ("leaf1_ecx", "leaf1_edx", "leaf6_eax", "leaf7_ebx", "leaf7_ecx", "leaf7_edx", "leafa_eax", "ext1_ecx", "ext1_edx", "ext7_edx", "ext1f_eax"),
            feature_values,
            strict=True,
        )
    )
    if features["leaf1_edx"] & REQUIRED_LEAF1_EDX != REQUIRED_LEAF1_EDX or features["ext1_edx"] & REQUIRED_EXT1_EDX != REQUIRED_EXT1_EDX:
        raise KernelCpuPolicyError("PKCPU1 mandatory feature baseline failed")

    xsave_values = [_hex(xsave_match, index) for index in range(2, 7)]
    xsave = dict(zip(("leafd0_eax", "leafd0_ebx", "leafd0_ecx", "leafd0_edx", "xcr0"), xsave_values, strict=True))
    state_values = [_hex(state_match, index) for index in range(2, 10)]
    state = dict(zip(("cr0", "cr4", "efer", "apic_base", "pat", "mtrr_cap", "mtrr_def", "msr_read_mask"), state_values, strict=True))
    if state["cr0"] & REQUIRED_CR0 != REQUIRED_CR0 or state["cr0"] & FORBIDDEN_CR0:
        raise KernelCpuPolicyError("PKCPU1 CR0 policy failed")
    if state["cr4"] & REQUIRED_CR4 != REQUIRED_CR4 or state["cr4"] & FORBIDDEN_CR4:
        raise KernelCpuPolicyError("PKCPU1 CR4 policy failed")
    support_gated = (
        (1 << 11, features["leaf7_ecx"] & (1 << 2)),
        (1 << 16, features["leaf7_ebx"] & (1 << 0)),
        (1 << 17, features["leaf1_ecx"] & (1 << 17)),
        (1 << 20, features["leaf7_ebx"] & (1 << 7)),
        (1 << 21, features["leaf7_ebx"] & (1 << 20)),
    )
    if any(state["cr4"] & control and not support for control, support in support_gated):
        raise KernelCpuPolicyError("PKCPU1 enabled an unsupported CR4 feature")
    xsave_supported = bool(features["leaf1_ecx"] & (1 << 26))
    osxsave = bool(features["leaf1_ecx"] & (1 << 27))
    if osxsave != bool(state["cr4"] & (1 << 18)) or osxsave and not xsave_supported:
        raise KernelCpuPolicyError("PKCPU1 OSXSAVE state contradicts CPUID")
    if xsave_supported:
        supported_xcr0 = xsave["leafd0_eax"] | (xsave["leafd0_edx"] << 32)
        if supported_xcr0 & 3 != 3 or osxsave and (xsave["xcr0"] & 3 != 3 or xsave["xcr0"] & ~supported_xcr0) or not osxsave and xsave["xcr0"]:
            raise KernelCpuPolicyError("PKCPU1 XCR0 policy failed")
    elif any(xsave.values()) or state["cr4"] & (1 << 18):
        raise KernelCpuPolicyError("PKCPU1 emitted XSAVE state without support")
    if state["efer"] & REQUIRED_EFER != REQUIRED_EFER or state["efer"] & ~ALLOWED_EFER or state["efer"] & (1 << 12):
        raise KernelCpuPolicyError("PKCPU1 EFER policy failed")
    if state["msr_read_mask"] != MSR_READ_MASK:
        raise KernelCpuPolicyError("PKCPU1 MSR read set changed")
    physical_mask = (1 << discovery["physical_width"]) - 1
    apic_address = state["apic_base"] & 0x000FFFFFFFFFF000
    if (
        state["apic_base"] & ~(0x000FFFFFFFFFF000 | 0xD00)
        or state["apic_base"] & 0x2FF
        or not state["apic_base"] & (1 << 11)
        or state["apic_base"] & (1 << 10) and not features["leaf1_ecx"] & (1 << 21)
        or not apic_address
        or apic_address & ~physical_mask
    ):
        raise KernelCpuPolicyError("PKCPU1 APIC-base policy failed")
    if any((state["pat"] >> (index * 8)) & 0xFF not in (0, 1, 4, 5, 6, 7) for index in range(8)):
        raise KernelCpuPolicyError("PKCPU1 PAT policy failed")
    variable_ranges = state["mtrr_cap"] & 0xFF
    default_type = state["mtrr_def"] & 0xFF
    if (
        state["mtrr_cap"] & ~(0xFF | (1 << 8) | (1 << 10) | (1 << 11))
        or not 1 <= variable_ranges <= 32
        or state["mtrr_def"] & ~(0xFF | (1 << 10) | (1 << 11))
        or default_type not in (0, 1, 4, 5, 6, 7)
        or not state["mtrr_def"] & (1 << 11)
        or state["mtrr_def"] & (1 << 10) and not state["mtrr_cap"] & (1 << 8)
    ):
        raise KernelCpuPolicyError("PKCPU1 MTRR policy failed")

    result = {
        "profile": result_match.group(2),
        "bsp": int(result_match.group(3)),
        "policy": result_match.group(4),
        "reads": result_match.group(5),
        "writes": int(result_match.group(6)),
        "signature_verifications": int(result_match.group(7)),
        "authority_grants": int(result_match.group(8)),
        "actions_authorized": int(result_match.group(9)),
        "interrupts": int(result_match.group(10)),
        "terminal": result_match.group(11),
    }
    if tuple(result.values()) != (
        "qemu64_tier0", 1, "required_and_support_gated", "cpuid_cr_msr", 0, 0, 0, 0, 0, "halt"
    ):
        raise KernelCpuPolicyError("PKCPU1 result boundary changed")
    return {
        "contract_id": CONTRACT_ID,
        "marker_count": len(markers),
        "ordered_contract_match": True,
        "transfer_prefix": prefix,
        "discovery": discovery,
        "topology": topology,
        "features": features,
        "xsave": xsave,
        "state": state,
        "result": result,
    }
