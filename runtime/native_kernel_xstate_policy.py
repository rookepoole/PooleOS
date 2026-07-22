"""Independent PKXSTATE1 oracle for bounded x87/SSE XSAVE evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKXSTATE1"
SELECTED_MOVE_ID = "N7-XSTATE-POLICY-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-xstate-policy-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-xstate-policy-contract.schema.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-xstate-policy-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-xstate-policy-readiness.json"
FEATURE = "development-xstate-policy"
SELECTOR = 5
PREFIX_MARKER_COUNT = 29
MARKER_COUNT = 35
SELECTED_XCR0 = 3
AREA_BYTES = 4096
INITIAL_FCW = 0x037F
INITIAL_MXCSR = 0x1F80
MXCSR_MASK_FALLBACK = 0xFFBF
CPU_MODEL = "EPYC-Rome-v4,-avx,-avx2,-fma,-f16c,-pku"
COMPLETION_MARKER = b"POOLEOS:KERNEL:XSTATE-RESULT PASS contract=PKXSTATE1"

IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/xstate.rs",
    "runtime/native_kernel_transfer.py",
    "runtime/native_kernel_xstate_policy.py",
    "tools/qualify_native_kernel_xstate_policy.py",
    "tests/test_native_kernel_xstate_policy.py",
    "docs/native-kernel-xstate-policy.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N7-PKXSTATE-MARKER-OMISSION",
    "NEG-N7-PKXSTATE-MARKER-ORDER",
    "NEG-N7-PKXSTATE-MARKER-DUPLICATE",
    "NEG-N7-PKXSTATE-SELECTOR",
    "NEG-N7-PKXSTATE-CONTRACT",
    "NEG-N7-PKXSTATE-XSAVE-FEATURE",
    "NEG-N7-PKXSTATE-OSXSAVE-FEATURE",
    "NEG-N7-PKXSTATE-SSE2-FEATURE",
    "NEG-N7-PKXSTATE-XCR0-SUPPORT",
    "NEG-N7-PKXSTATE-LEAFD1-RESERVED",
    "NEG-N7-PKXSTATE-ENABLED-SIZE-LOW",
    "NEG-N7-PKXSTATE-ENABLED-SIZE-HIGH",
    "NEG-N7-PKXSTATE-MAXIMUM-SIZE",
    "NEG-N7-PKXSTATE-CR0-TS",
    "NEG-N7-PKXSTATE-CR0-EM",
    "NEG-N7-PKXSTATE-CR4-OSXSAVE",
    "NEG-N7-PKXSTATE-XCR0-SELECTED",
    "NEG-N7-PKXSTATE-XSS",
    "NEG-N7-PKXSTATE-STRATEGY",
    "NEG-N7-PKXSTATE-FORMAT",
    "NEG-N7-PKXSTATE-AREA-SIZE",
    "NEG-N7-PKXSTATE-ALIGNMENT",
    "NEG-N7-PKXSTATE-FCW",
    "NEG-N7-PKXSTATE-MXCSR",
    "NEG-N7-PKXSTATE-MXCSR-MASK",
    "NEG-N7-PKXSTATE-SAVE-COUNT",
    "NEG-N7-PKXSTATE-RESTORE-COUNT",
    "NEG-N7-PKXSTATE-XSTATE-BV",
    "NEG-N7-PKXSTATE-CONTEXT-MATCH",
    "NEG-N7-PKXSTATE-SCHEDULER-LOCK",
    "NEG-N7-PKXSTATE-INTERRUPTS",
    "NEG-N7-PKXSTATE-CPU-MIGRATION",
    "NEG-N7-PKXSTATE-KERNEL-SIMD",
    "NEG-N7-PKXSTATE-CANONICAL-CLEAR",
    "NEG-N7-PKXSTATE-IMAGE-CLEAR",
    "NEG-N7-PKXSTATE-NM",
    "NEG-N7-PKXSTATE-WRITES",
    "NEG-N7-PKXSTATE-SIGNATURES",
    "NEG-N7-PKXSTATE-AUTHORITY",
    "NEG-N7-PKXSTATE-ACTIONS",
    "NEG-N7-PKXSTATE-SCHEDULER-CLAIM",
    "NEG-N7-PKXSTATE-SMP-CLAIM",
    "NEG-N7-PKXSTATE-TARGET-CLAIM",
)

HEX64 = r"(0x[0-9A-F]{16})"
CAPABILITY = re.compile(
    rf"^POOLEOS:KERNEL:XSTATE-CAPABILITY PASS contract=(PKXSTATE1) leaf1_ecx={HEX64} "
    rf"leaf1_edx={HEX64} supported_xcr0={HEX64} leafd1_eax={HEX64} "
    r"enabled_bytes=([0-9]+) maximum_bytes=([0-9]+)$"
)
CONFIG = re.compile(
    rf"^POOLEOS:KERNEL:XSTATE-CONFIG PASS contract=(PKXSTATE1) cr0_before={HEX64} "
    rf"cr0_after={HEX64} cr4_before={HEX64} cr4_after={HEX64} xcr0_before={HEX64} "
    rf"xcr0_after={HEX64} xss={HEX64} strategy=(eager) format=(standard) "
    r"area_bytes=([0-9]+) alignment=([0-9]+)$"
)
INIT = re.compile(
    rf"^POOLEOS:KERNEL:XSTATE-INIT PASS contract=(PKXSTATE1) fcw={HEX64} mxcsr={HEX64} "
    rf"mxcsr_mask_raw={HEX64} mxcsr_mask_effective={HEX64} exceptions=(masked) "
    r"nm_policy=(unexpected_fail_closed)$"
)
SWITCH = re.compile(
    rf"^POOLEOS:KERNEL:XSTATE-SWITCH PASS contract=(PKXSTATE1) owners=(10,11) "
    rf"saves=([0-9]+) restores=([0-9]+) xstate_bv_a={HEX64} xstate_bv_b={HEX64} "
    r"match_a=([01]) match_b=([01]) scheduler_lock=([01]) interrupts=([01]) "
    r"same_cpu=([01]) kernel_simd=([01])$"
)
CLEAR = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-CLEAR PASS contract=(PKXSTATE1) canonical_xmm0_zero=([01]) "
    r"image_zero_bytes=([0-9]+) unexpected_nm=([0-9]+) "
    r"all_selected_components=(canonical_image) kernel_simd_policy=(forbidden)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-RESULT PASS contract=(PKXSTATE1) "
    r"profile=(epyc_rome_v4_x87_sse) bsp=([01]) writes=([0-9]+) signatures=([0-9]+) "
    r"authority=([0-9]+) actions=([0-9]+) scheduler=([01]) smp=([01]) target=([01]) "
    r"terminal=(halt)$"
)


class KernelXstatePolicyError(ValueError):
    """Raised when PKXSTATE1 data violates the frozen policy."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelXstatePolicyError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelXstatePolicyError("binding path escapes repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "readiness_schema": file_binding(root / READINESS_SCHEMA_RELATIVE, root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "tier0_lock": file_binding(root / "specs/native-tier0-lock.json", root),
        "tier0_profile": file_binding(root / "specs/native-tier0-profile.json", root),
        "implementation_inputs": [file_binding(root / item, root) for item in IMPLEMENTATION_INPUTS],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "x87_sse_xsave_policy_frozen": True,
        "eager_standard_xsave_selected": True,
        "two_context_round_trip_observed": True,
        "canonical_initial_state_observed": True,
        "per_context_images_cleared": True,
        "kernel_simd_forbidden": True,
        "rust_python_policy_agreement": True,
        "two_qemu_runs_exact_match": True,
        "avx_or_extended_xstate_qualified": False,
        "unmasked_x87_sse_exception_handlers_qualified": False,
        "lazy_nm_strategy_qualified": False,
        "scheduler_context_switch_integrated": False,
        "smp_or_cpu_migration_qualified": False,
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
        errors.append("PKXSTATE1 identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, CPU_MODEL, True):
        errors.append("PKXSTATE1 development profile changed")
    policy = contract.get("policy", {})
    if not isinstance(policy, dict) or tuple(
        policy.get(key)
        for key in (
            "selected_xcr0",
            "xss",
            "area_bytes",
            "alignment_bytes",
            "initial_fcw",
            "initial_mxcsr",
            "mxcsr_mask_fallback",
            "strategy",
            "format",
            "kernel_simd",
            "xsaves_capability_allowed_without_selection",
        )
    ) != (3, 0, 4096, 64, 0x037F, 0x1F80, 0xFFBF, "eager", "standard_xsave", "forbidden", True):
        errors.append("PKXSTATE1 frozen policy changed")
    qualification = contract.get("qualification", {})
    if (
        not isinstance(qualification, dict)
        or qualification.get("qemu_run_count") != 2
        or qualification.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS)
        or contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS)
    ):
        errors.append("PKXSTATE1 qualification changed")
    authority_gate = contract.get("authority_gate", {})
    if not isinstance(authority_gate, dict) or tuple(
        authority_gate.get(key)
        for key in (
            "privileged_configuration_writes",
            "write_allowlist",
            "msr_writes",
            "signature_verifications",
            "authority_grants",
            "actions_authorized",
            "post_exit_firmware_calls",
            "physical_media_writes",
        )
    ) != (3, ["CR0", "CR4", "XCR0"], 0, 0, 0, 0, 0, 0):
        errors.append("PKXSTATE1 authority boundary changed")
    sources = contract.get("source_register", [])
    if not isinstance(sources, list) or len(sources) != 1 or tuple(
        sources[0].get(key) for key in ("authority", "publication", "revision", "captured_byte_count", "captured_sha256")
    ) != ("AMD", "24593", "3.44", 12560767, "3D9DCB3F68222392D0EDE9970EFC95E31A047A247D54B454123D6981D278C48C"):
        errors.append("PKXSTATE1 source binding changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKXSTATE1 claim boundary changed")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("PKXSTATE1 overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKXSTATE1 input bindings changed")
    if readiness.get("claims") != expected_claims() or readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PKXSTATE1 readiness boundary changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or len(controls) != len(NEGATIVE_CONTROL_IDS)
        or [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKXSTATE1 hostile controls changed")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key) for key in ("run_count", "cpu_model", "exact_marker_match")
    ) != (2, CPU_MODEL, True):
        errors.append("PKXSTATE1 execution changed")
    if readiness.get("production_ready") is not False or readiness.get("n7_exit_gate_satisfied") is not False:
        errors.append("PKXSTATE1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelXstatePolicyError(f"PKXSTATE1 {name} marker violates contract: {marker!r}")
    return match


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def _validate_prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelXstatePolicyError("PKXSTATE1 selector changed")
    baseline = markers[:PREFIX_MARKER_COUNT]
    baseline[23] = re.sub(r"trap_scenario=[0-6]", "trap_scenario=0", baseline[23], count=1)
    terminal = (
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers([*baseline, terminal])
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelXstatePolicyError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelXstatePolicyError(f"expected {MARKER_COUNT} markers, observed {len(markers)}")
    prefix = _validate_prefix(markers)
    cap_match = _match(CAPABILITY, markers[29], "capability")
    config_match = _match(CONFIG, markers[30], "config")
    init_match = _match(INIT, markers[31], "init")
    switch_match = _match(SWITCH, markers[32], "switch")
    clear_match = _match(CLEAR, markers[33], "clear")
    result_match = _match(RESULT, markers[34], "result")

    capability = {
        "leaf1_ecx": _hex(cap_match, 2),
        "leaf1_edx": _hex(cap_match, 3),
        "supported_xcr0": _hex(cap_match, 4),
        "leaf_d1_eax": _hex(cap_match, 5),
        "enabled_area_bytes": int(cap_match.group(6)),
        "maximum_area_bytes": int(cap_match.group(7)),
    }
    if capability["leaf1_ecx"] & ((1 << 26) | (1 << 27)) != (1 << 26) | (1 << 27):
        raise KernelXstatePolicyError("PKXSTATE1 XSAVE/OSXSAVE features missing")
    required_edx = (1 << 0) | (1 << 24) | (1 << 25) | (1 << 26)
    if capability["leaf1_edx"] & required_edx != required_edx:
        raise KernelXstatePolicyError("PKXSTATE1 x87/SSE features missing")
    if capability["supported_xcr0"] & SELECTED_XCR0 != SELECTED_XCR0:
        raise KernelXstatePolicyError("PKXSTATE1 component support missing")
    if capability["leaf_d1_eax"] & ~0x0F:
        raise KernelXstatePolicyError("PKXSTATE1 CPUID leaf D1 contains an unknown capability")
    if not 576 <= capability["enabled_area_bytes"] <= AREA_BYTES or capability["maximum_area_bytes"] < capability["enabled_area_bytes"]:
        raise KernelXstatePolicyError("PKXSTATE1 area size is invalid")

    config = {
        "cr0_before": _hex(config_match, 2),
        "cr0_after": _hex(config_match, 3),
        "cr4_before": _hex(config_match, 4),
        "cr4_after": _hex(config_match, 5),
        "xcr0_before": _hex(config_match, 6),
        "xcr0_after": _hex(config_match, 7),
        "xss": _hex(config_match, 8),
        "strategy": config_match.group(9),
        "format": config_match.group(10),
        "area_bytes": int(config_match.group(11)),
        "alignment": int(config_match.group(12)),
    }
    if config["cr0_after"] & ((1 << 1) | (1 << 5)) != (1 << 1) | (1 << 5) or config["cr0_after"] & ((1 << 2) | (1 << 3)):
        raise KernelXstatePolicyError("PKXSTATE1 CR0 policy changed")
    if config["cr4_after"] & ((1 << 9) | (1 << 10) | (1 << 18)) != (1 << 9) | (1 << 10) | (1 << 18):
        raise KernelXstatePolicyError("PKXSTATE1 CR4 policy changed")
    if tuple(config[key] for key in ("xcr0_after", "xss", "strategy", "format", "area_bytes", "alignment")) != (3, 0, "eager", "standard", 4096, 64):
        raise KernelXstatePolicyError("PKXSTATE1 configuration changed")

    init = {
        "fcw": _hex(init_match, 2),
        "mxcsr": _hex(init_match, 3),
        "mxcsr_mask_raw": _hex(init_match, 4),
        "mxcsr_mask_effective": _hex(init_match, 5),
        "exceptions": init_match.group(6),
        "nm_policy": init_match.group(7),
    }
    effective = init["mxcsr_mask_raw"] or MXCSR_MASK_FALLBACK
    if tuple(init[key] for key in ("fcw", "mxcsr", "mxcsr_mask_effective")) != (INITIAL_FCW, INITIAL_MXCSR, effective) or INITIAL_MXCSR & ~effective:
        raise KernelXstatePolicyError("PKXSTATE1 canonical initialization changed")

    switch = {
        "owners": switch_match.group(2),
        "saves": int(switch_match.group(3)),
        "restores": int(switch_match.group(4)),
        "xstate_bv_a": _hex(switch_match, 5),
        "xstate_bv_b": _hex(switch_match, 6),
        "match_a": int(switch_match.group(7)),
        "match_b": int(switch_match.group(8)),
        "scheduler_lock": int(switch_match.group(9)),
        "interrupts": int(switch_match.group(10)),
        "same_cpu": int(switch_match.group(11)),
        "kernel_simd": int(switch_match.group(12)),
    }
    if tuple(switch[key] for key in ("owners", "saves", "restores", "match_a", "match_b", "scheduler_lock", "interrupts", "same_cpu", "kernel_simd")) != ("10,11", 2, 4, 1, 1, 1, 0, 1, 0):
        raise KernelXstatePolicyError("PKXSTATE1 switch preconditions changed")
    for key in ("xstate_bv_a", "xstate_bv_b"):
        if switch[key] & ~SELECTED_XCR0 or switch[key] & 2 == 0:
            raise KernelXstatePolicyError("PKXSTATE1 XSTATE_BV changed")

    clear = {
        "canonical_xmm0_zero": int(clear_match.group(2)),
        "image_zero_bytes": int(clear_match.group(3)),
        "unexpected_nm": int(clear_match.group(4)),
        "all_selected_components": clear_match.group(5),
        "kernel_simd_policy": clear_match.group(6),
    }
    if tuple(clear.values()) != (1, AREA_BYTES * 2, 0, "canonical_image", "forbidden"):
        raise KernelXstatePolicyError("PKXSTATE1 clear receipt changed")

    result = {
        "profile": result_match.group(2),
        "bsp": int(result_match.group(3)),
        "writes": int(result_match.group(4)),
        "signatures": int(result_match.group(5)),
        "authority": int(result_match.group(6)),
        "actions": int(result_match.group(7)),
        "scheduler": int(result_match.group(8)),
        "smp": int(result_match.group(9)),
        "target": int(result_match.group(10)),
        "terminal": result_match.group(11),
    }
    if tuple(result.values()) != ("epyc_rome_v4_x87_sse", 1, 3, 0, 0, 0, 0, 0, 0, "halt"):
        raise KernelXstatePolicyError("PKXSTATE1 result boundary changed")
    return {
        "transfer_prefix": prefix,
        "capability": capability,
        "config": config,
        "initialization": init,
        "switch": switch,
        "clear": clear,
        "result": result,
    }
