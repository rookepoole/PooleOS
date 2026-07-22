"""Independent PKMSR1 oracle for bounded privileged-MSR policy evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKMSR1"
SELECTED_MOVE_ID = "N7-PRIVILEGE-MSR-POLICY-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-privilege-msr-policy-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-privilege-msr-policy-contract.schema.json"
SCHEMA_RELATIVE = "specs/native-kernel-privilege-msr-policy-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-privilege-msr-policy-readiness.json"
MARKER_COUNT = 35
PREFIX_MARKER_COUNT = 29
SELECTOR = 7
FEATURE = "development-privilege-msr-policy"
COMPLETION_MARKER = b"POOLEOS:KERNEL:PRIV-MSR-RESULT PASS contract=PKMSR1"

READ_EFER = 1 << 0
READ_STAR = 1 << 1
READ_LSTAR = 1 << 2
READ_CSTAR = 1 << 3
READ_SFMASK = 1 << 4
READ_FS_BASE = 1 << 5
READ_GS_BASE = 1 << 6
READ_KERNEL_GS_BASE = 1 << 7
READ_TSC_AUX = 1 << 8
READ_MCG_CAP = 1 << 9
READ_MCG_STATUS = 1 << 10
READ_MCG_CTL = 1 << 11
LINKAGE_READS = READ_EFER | READ_STAR | READ_LSTAR | READ_CSTAR | READ_SFMASK
BASE_READS = READ_FS_BASE | READ_GS_BASE | READ_KERNEL_GS_BASE
MCA_GLOBAL_READS = READ_MCG_CAP | READ_MCG_STATUS
REQUIRED_EFER = (1 << 8) | (1 << 10) | (1 << 11)
ALLOWED_EFER = (1 << 0) | REQUIRED_EFER | (1 << 12) | (1 << 13) | (1 << 14) | (1 << 15)

IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/manifest.pkm",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/privilege_msr.rs",
    "runtime/native_kernel_privilege_msr_policy.py",
    "runtime/native_kernel_transfer.py",
    "tools/qualify_native_kernel_privilege_msr_policy.py",
    "tests/test_native_kernel_privilege_msr_policy.py",
    "docs/native-kernel-privilege-msr-policy.md",
    "runs/native_kernel_entry_readiness.json",
    "runs/native-kernel-revalidation-readiness.json",
    "runs/native_kernel_load_readiness.json",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N7-PKMSR-MARKER-OMISSION",
    "NEG-N7-PKMSR-MARKER-ORDER",
    "NEG-N7-PKMSR-MARKER-DUPLICATE",
    "NEG-N7-PKMSR-SELECTOR",
    "NEG-N7-PKMSR-CONTRACT",
    "NEG-N7-PKMSR-VENDOR",
    "NEG-N7-PKMSR-MAX-BASIC",
    "NEG-N7-PKMSR-MAX-EXTENDED",
    "NEG-N7-PKMSR-MCE-FEATURE",
    "NEG-N7-PKMSR-MCA-FEATURE",
    "NEG-N7-PKMSR-SYSCALL-FEATURE",
    "NEG-N7-PKMSR-RDTSCP-FEATURE",
    "NEG-N7-PKMSR-LONG-MODE-FEATURE",
    "NEG-N7-PKMSR-FEATURE-MARKER",
    "NEG-N7-PKMSR-ARCH-PMU",
    "NEG-N7-PKMSR-AMD-PERFMON-V2",
    "NEG-N7-PKMSR-CR4-PCE",
    "NEG-N7-PKMSR-EFER-REQUIRED",
    "NEG-N7-PKMSR-EFER-SCE",
    "NEG-N7-PKMSR-EFER-RESERVED",
    "NEG-N7-PKMSR-STAR-ACTIVE",
    "NEG-N7-PKMSR-LSTAR-CANONICAL",
    "NEG-N7-PKMSR-SFMASK-ACTIVE",
    "NEG-N7-PKMSR-FS-BASE-ACTIVE",
    "NEG-N7-PKMSR-GS-BASE-CANONICAL",
    "NEG-N7-PKMSR-TSC-AUX-ACTIVE",
    "NEG-N7-PKMSR-TSC-AUX-READ",
    "NEG-N7-PKMSR-MCG-CAP-RESERVED",
    "NEG-N7-PKMSR-MCG-BANK-COUNT",
    "NEG-N7-PKMSR-MCG-STATUS-ACTIVE",
    "NEG-N7-PKMSR-MCG-STATUS-RESERVED",
    "NEG-N7-PKMSR-MCG-CTL-BANK",
    "NEG-N7-PKMSR-MCG-READ-COUNT",
    "NEG-N7-PKMSR-MCG-BANK-READ",
    "NEG-N7-PKMSR-PMU-MSR-READ",
    "NEG-N7-PKMSR-RDPMC",
    "NEG-N7-PKMSR-RESULT-READ-COUNT",
    "NEG-N7-PKMSR-MSR-WRITE",
    "NEG-N7-PKMSR-CONTROL-WRITE",
    "NEG-N7-PKMSR-SIGNATURE",
    "NEG-N7-PKMSR-AUTHORITY",
    "NEG-N7-PKMSR-ACTION",
    "NEG-N7-PKMSR-INTERRUPT",
    "NEG-N7-PKMSR-SYSCALL-ACTIVE",
    "NEG-N7-PKMSR-MCE-HANDLER",
    "NEG-N7-PKMSR-PMU-OWNER",
    "NEG-N7-PKMSR-TERMINAL",
)

HEX64 = r"(0x[0-9A-F]{16})"
FEATURES = re.compile(
    rf"^POOLEOS:KERNEL:PRIV-MSR-FEATURES OBSERVE contract=(PKMSR1) "
    rf"vendor_hex=([0-9A-F]{{24}}) max_basic={HEX64} max_extended={HEX64} "
    rf"leaf1_edx={HEX64} ext1_edx={HEX64} leafa_eax={HEX64} ext22_eax={HEX64} "
    rf"cr4={HEX64} syscall=([01]) rdtscp=([01]) mce=([01]) mca=([01]) "
    r"arch_pmu_version=([0-9]+) amd_perfmon_v2=([0-9]+)$"
)
LINKAGE = re.compile(
    rf"^POOLEOS:KERNEL:PRIV-MSR-LINKAGE OBSERVE contract=(PKMSR1) efer={HEX64} "
    rf"star={HEX64} lstar={HEX64} cstar={HEX64} sfmask={HEX64} active=([01]) reads=([0-9]+)$"
)
BASES = re.compile(
    rf"^POOLEOS:KERNEL:PRIV-MSR-BASES OBSERVE contract=(PKMSR1) fs_base={HEX64} "
    rf"gs_base={HEX64} kernel_gs_base={HEX64} tsc_aux={HEX64} "
    r"tsc_aux_read=([01]) reads=([0-9]+)$"
)
MCE = re.compile(
    rf"^POOLEOS:KERNEL:PRIV-MSR-MCE OBSERVE contract=(PKMSR1) mcg_cap={HEX64} "
    rf"mcg_status={HEX64} mcg_ctl={HEX64} bank_count=([0-9]+) ctl_present=([01]) "
    r"bank_reads=([0-9]+) reads=([0-9]+)$"
)
PMU = re.compile(
    r"^POOLEOS:KERNEL:PRIV-MSR-PMU OBSERVE contract=(PKMSR1) architectural=([01]) "
    r"amd_v2=([01]) msr_reads=([0-9]+) rdpmc=([0-9]+) cr4_pce=([01]) policy=(disabled)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:PRIV-MSR-RESULT PASS contract=(PKMSR1) profile=(qemu64_tier0) "
    r"bsp=([01]) policy=(read_only_support_gated) msr_reads=([0-9]+) msr_writes=([0-9]+) "
    r"control_writes=([0-9]+) signatures=([0-9]+) authority=([0-9]+) actions=([0-9]+) "
    r"interrupts=([01]) syscall_active=([01]) mce_handler=([01]) pmu_owner=([01]) terminal=(halt)$"
)


class KernelPrivilegeMsrPolicyError(ValueError):
    """Raised when PKMSR1 evidence violates its bounded policy."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelPrivilegeMsrPolicyError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelPrivilegeMsrPolicyError("binding path escapes repository") from error
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
        "support_gated_system_linkage_msrs_observed": True,
        "inactive_syscall_baseline_observed": True,
        "early_fs_gs_kernel_gs_and_tsc_aux_observed": False,
        "global_machine_check_capability_and_status_observed": True,
        "unsupported_pmu_path_failed_closed": True,
        "reserved_bit_and_canonical_address_policy_enforced": True,
        "rust_python_policy_agreement": True,
        "linked_machine_code_no_wrmsr_audited": True,
        "two_qemu_runs_exact_match": True,
        "syscall_entry_activated": False,
        "machine_check_handler_activated": False,
        "performance_monitor_owner_activated": False,
        "target_cpu_qualified": False,
        "n7_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if (contract.get("contract_id"), contract.get("selected_move_id")) != (
        CONTRACT_ID,
        SELECTED_MOVE_ID,
    ):
        errors.append("PKMSR1 contract identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only", "read_only")
    ) != (FEATURE, SELECTOR, "qemu64", True, True):
        errors.append("PKMSR1 development profile changed")
    qualification = contract.get("qualification", {})
    if (
        not isinstance(qualification, dict)
        or qualification.get("qemu_run_count") != 2
        or qualification.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS)
        or contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS)
    ):
        errors.append("PKMSR1 qualification profile changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKMSR1 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKMSR1 contract overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract, root))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKMSR1 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key)
        for key in ("run_count", "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")
    ) != (2, True, True, True):
        errors.append("PKMSR1 exact two-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKMSR1 hostile-control evidence changed")
    summary = readiness.get("summary", {})
    if not isinstance(summary, dict) or tuple(
        summary.get(key)
        for key in (
            "qemu_run_count",
            "marker_count",
            "negative_controls_passed",
            "msr_writes",
            "authority_grants",
            "production_claim_count",
        )
    ) != (2, MARKER_COUNT, len(NEGATIVE_CONTROL_IDS), 0, 0, 0):
        errors.append("PKMSR1 summary changed")
    if readiness.get("claims") != expected_claims() or readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PKMSR1 readiness claim boundary changed")
    if (
        readiness.get("production_ready") is not False
        or readiness.get("production_promotion_allowed") is not False
        or readiness.get("n7_exit_gate_satisfied") is not False
    ):
        errors.append("PKMSR1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelPrivilegeMsrPolicyError(f"PKMSR1 {name} marker violates its contract: {marker!r}")
    return match


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def _canonical_48(value: int) -> bool:
    high = value >> 48
    return high == (0xFFFF if value & (1 << 47) else 0)


def _validate_prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 transfer selector changed")
    baseline = markers[:PREFIX_MARKER_COUNT]
    baseline[23] = re.sub(r"trap_scenario=[0-7]", "trap_scenario=0", baseline[23], count=1)
    terminal = (
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers([*baseline, terminal])
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelPrivilegeMsrPolicyError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelPrivilegeMsrPolicyError(f"expected {MARKER_COUNT} PKMSR1 markers, observed {len(markers)}")
    prefix = _validate_prefix(markers)
    feature_match = _match(FEATURES, markers[29], "features")
    linkage_match = _match(LINKAGE, markers[30], "linkage")
    bases_match = _match(BASES, markers[31], "bases")
    mce_match = _match(MCE, markers[32], "machine-check")
    pmu_match = _match(PMU, markers[33], "performance-monitoring")
    result_match = _match(RESULT, markers[34], "result")

    vendor = bytes.fromhex(feature_match.group(2))
    features = {
        "vendor": vendor.decode("ascii", errors="strict"),
        "max_basic_leaf": _hex(feature_match, 3),
        "max_extended_leaf": _hex(feature_match, 4),
        "leaf1_edx": _hex(feature_match, 5),
        "ext1_edx": _hex(feature_match, 6),
        "leaf_a_eax": _hex(feature_match, 7),
        "ext22_eax": _hex(feature_match, 8),
        "cr4": _hex(feature_match, 9),
        "syscall": int(feature_match.group(10)),
        "rdtscp": int(feature_match.group(11)),
        "mce": int(feature_match.group(12)),
        "mca": int(feature_match.group(13)),
        "architectural_pmu_version": int(feature_match.group(14)),
        "amd_perfmon_v2": int(feature_match.group(15)),
    }
    if vendor != b"AuthenticAMD" or features["max_basic_leaf"] < 0x0A or features["max_extended_leaf"] < 0x80000008:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 vendor or leaf range changed")
    expected_feature_bits = {
        "mce": bool(features["leaf1_edx"] & (1 << 7)),
        "mca": bool(features["leaf1_edx"] & (1 << 14)),
        "syscall": bool(features["ext1_edx"] & (1 << 11)),
        "rdtscp": bool(features["ext1_edx"] & (1 << 27)),
    }
    if any(features[key] != int(value) for key, value in expected_feature_bits.items()) or not all(
        expected_feature_bits[key] for key in ("mce", "mca", "syscall")
    ):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 required feature gate changed")
    if not features["ext1_edx"] & (1 << 29):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 long-mode feature disappeared")
    arch_version = features["leaf_a_eax"] & 0xFF
    amd_version = features["ext22_eax"] & 0xFF if features["max_extended_leaf"] >= 0x80000022 else 0
    if (
        features["max_extended_leaf"] < 0x80000022
        and features["ext22_eax"]
        or features["architectural_pmu_version"] != arch_version
        or features["amd_perfmon_v2"] != amd_version
        or arch_version
        or amd_version
        or features["cr4"] & (1 << 8)
    ):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 unsupported PMU policy changed")

    linkage = {
        "efer": _hex(linkage_match, 2),
        "star": _hex(linkage_match, 3),
        "lstar": _hex(linkage_match, 4),
        "cstar": _hex(linkage_match, 5),
        "sfmask": _hex(linkage_match, 6),
        "active": int(linkage_match.group(7)),
        "reads": int(linkage_match.group(8)),
    }
    if linkage["efer"] & REQUIRED_EFER != REQUIRED_EFER or linkage["efer"] & ~ALLOWED_EFER or linkage["efer"] & ((1 << 0) | (1 << 12)):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 EFER policy changed")
    if not _canonical_48(linkage["lstar"]) or not _canonical_48(linkage["cstar"]):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 linkage target is not canonical")
    if any(linkage[key] for key in ("star", "lstar", "cstar", "sfmask", "active")) or linkage["reads"] != 5:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 inactive linkage baseline changed")

    bases = {
        "fs_base": _hex(bases_match, 2),
        "gs_base": _hex(bases_match, 3),
        "kernel_gs_base": _hex(bases_match, 4),
        "tsc_aux": _hex(bases_match, 5),
        "tsc_aux_read": int(bases_match.group(6)),
        "reads": int(bases_match.group(7)),
    }
    if not all(_canonical_48(bases[key]) for key in ("fs_base", "gs_base", "kernel_gs_base")):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 FS/GS base is not canonical")
    if any(bases[key] for key in ("fs_base", "gs_base", "kernel_gs_base", "tsc_aux")):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 early per-CPU state is active")
    if bases["tsc_aux_read"] != features["rdtscp"] or bases["reads"] != 3 + features["rdtscp"]:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 TSC_AUX read gate changed")

    machine_check = {
        "mcg_cap": _hex(mce_match, 2),
        "mcg_status": _hex(mce_match, 3),
        "mcg_ctl": _hex(mce_match, 4),
        "bank_count": int(mce_match.group(5)),
        "ctl_present": int(mce_match.group(6)),
        "bank_reads": int(mce_match.group(7)),
        "reads": int(mce_match.group(8)),
    }
    bank_count = machine_check["mcg_cap"] & 0xFF
    ctl_present = int(bool(machine_check["mcg_cap"] & (1 << 8)))
    if (
        machine_check["mcg_cap"] & ~0x010001FF
        or not machine_check["mcg_cap"] & (1 << 24)
        or not 1 <= bank_count <= 32
    ):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 MCG_CAP policy changed")
    if machine_check["bank_count"] != bank_count or machine_check["ctl_present"] != ctl_present:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 machine-check capability decoding changed")
    if machine_check["mcg_status"] & ~0x7 or machine_check["mcg_status"]:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 active or reserved MCG_STATUS changed")
    if (ctl_present and machine_check["mcg_ctl"] != 0xFFFFFFFFFFFFFFFF) or (
        not ctl_present and machine_check["mcg_ctl"]
    ):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 qemu64 MCG_CTL profile changed")
    if machine_check["bank_reads"] or machine_check["reads"] != 2 + ctl_present:
        raise KernelPrivilegeMsrPolicyError("PKMSR1 global-only machine-check read scope changed")

    pmu = {
        "architectural": int(pmu_match.group(2)),
        "amd_v2": int(pmu_match.group(3)),
        "msr_reads": int(pmu_match.group(4)),
        "rdpmc": int(pmu_match.group(5)),
        "cr4_pce": int(pmu_match.group(6)),
    }
    if any(pmu.values()):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 PMU path is not disabled")

    expected_mask = LINKAGE_READS | BASE_READS | MCA_GLOBAL_READS
    if features["rdtscp"]:
        expected_mask |= READ_TSC_AUX
    if ctl_present:
        expected_mask |= READ_MCG_CTL
    expected_read_count = expected_mask.bit_count()
    result = {
        "bsp": int(result_match.group(3)),
        "msr_reads": int(result_match.group(5)),
        "msr_writes": int(result_match.group(6)),
        "control_writes": int(result_match.group(7)),
        "signatures": int(result_match.group(8)),
        "authority": int(result_match.group(9)),
        "actions": int(result_match.group(10)),
        "interrupts": int(result_match.group(11)),
        "syscall_active": int(result_match.group(12)),
        "mce_handler": int(result_match.group(13)),
        "pmu_owner": int(result_match.group(14)),
        "terminal": result_match.group(15),
        "msr_read_mask": expected_mask,
    }
    if result["bsp"] != 1 or result["msr_reads"] != expected_read_count or any(
        result[key]
        for key in (
            "msr_writes",
            "control_writes",
            "signatures",
            "authority",
            "actions",
            "interrupts",
            "syscall_active",
            "mce_handler",
            "pmu_owner",
        )
    ):
        raise KernelPrivilegeMsrPolicyError("PKMSR1 result authority boundary changed")
    return {
        "transfer_prefix": prefix,
        "features": features,
        "linkage": linkage,
        "bases": bases,
        "machine_check": machine_check,
        "performance_monitoring": pmu,
        "result": result,
        "marker_count": len(markers),
    }
