"""Independent PKXEXC1 oracle for bounded x87/SSE exception evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKXEXC1"
SELECTED_MOVE_ID = "N7-XSTATE-EXCEPTION-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-xstate-exception-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-xstate-exception-contract.schema.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-xstate-exception-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-xstate-exception-readiness.json"
FEATURE = "development-xstate-exception"
SELECTOR = 6
PREFIX_MARKER_COUNT = 29
MARKER_COUNT = 41
CPU_MODEL = "EPYC-Rome-v4,-avx,-avx2,-fma,-f16c,-pku"
COMPLETION_MARKER = b"POOLEOS:KERNEL:XSTATE-EXCEPTION-RESULT PASS contract=PKXEXC1"

INITIAL_FCW = 0x037F
INITIAL_MXCSR = 0x1F80
X87_INVALID_FCW = 0x037E
SIMD_INVALID_MXCSR = 0x1F00
REQUIRED_CR0 = (1 << 1) | (1 << 5)
FORBIDDEN_CR0 = (1 << 2) | (1 << 3)
REQUIRED_CR4 = (1 << 9) | (1 << 10) | (1 << 18)

LLVM_OBJDUMP_RELATIVE = (
    ".toolchains/rust-1.97.0/rustup/toolchains/"
    "1.97.0-x86_64-pc-windows-msvc/lib/rustlib/"
    "x86_64-pc-windows-msvc/bin/llvm-objdump.exe"
)
LLVM_OBJDUMP_VERSION = "LLVM version 22.1.6-rust-1.97.0-stable"
LLVM_OBJDUMP_BYTES = 35_279_360
LLVM_OBJDUMP_SHA256 = "84DE1EDCEFED12FEB797F8B1C41DEBA99B6116A6BB3B80A1832FFF2CC06F2F94"
LLVM_TOOLS_ARCHIVE_URL = (
    "https://static.rust-lang.org/dist/2026-07-09/"
    "llvm-tools-1.97.0-x86_64-pc-windows-msvc.tar.xz"
)
LLVM_TOOLS_ARCHIVE_SHA256 = "671B509EC2C9220916D25D8FD546E71EFB552439F8E7AE75CE53208D9395DFB4"

IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/manifest.pkm",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/xstate.rs",
    "native/kernel/src/xstate_exception.rs",
    "runtime/native_kernel_transfer.py",
    "runtime/native_kernel_xstate_policy.py",
    "runtime/native_kernel_xstate_exception.py",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_xstate_policy.py",
    "tools/qualify_native_kernel_xstate_exception.py",
    "tests/test_native_kernel_xstate_exception.py",
    "docs/native-kernel-xstate-exception.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N7-PKXEXC-MARKER-OMISSION",
    "NEG-N7-PKXEXC-MARKER-ORDER",
    "NEG-N7-PKXEXC-MARKER-DUPLICATE",
    "NEG-N7-PKXEXC-SELECTOR",
    "NEG-N7-PKXEXC-CONTRACT",
    "NEG-N7-PKXEXC-PARENT",
    "NEG-N7-PKXEXC-GATES",
    "NEG-N7-PKXEXC-VECTORS",
    "NEG-N7-PKXEXC-IST",
    "NEG-N7-PKXEXC-XCR0",
    "NEG-N7-PKXEXC-CR0",
    "NEG-N7-PKXEXC-CR4",
    "NEG-N7-PKXEXC-PARENT-WRITES",
    "NEG-N7-PKXEXC-DEFAULT-MASKS",
    "NEG-N7-PKXEXC-SEQUENCE",
    "NEG-N7-PKXEXC-X87-FCW-ARM",
    "NEG-N7-PKXEXC-SIMD-MXCSR-ARM",
    "NEG-N7-PKXEXC-NM-STRATEGY",
    "NEG-N7-PKXEXC-X87-VECTOR",
    "NEG-N7-PKXEXC-X87-ERROR",
    "NEG-N7-PKXEXC-X87-STATUS",
    "NEG-N7-PKXEXC-X87-RECOVERY",
    "NEG-N7-PKXEXC-X87-RETURN",
    "NEG-N7-PKXEXC-SIMD-VECTOR",
    "NEG-N7-PKXEXC-SIMD-STATUS",
    "NEG-N7-PKXEXC-SIMD-RECOVERY",
    "NEG-N7-PKXEXC-SIMD-RETURN",
    "NEG-N7-PKXEXC-NM-ARM",
    "NEG-N7-PKXEXC-NM-VECTOR",
    "NEG-N7-PKXEXC-NM-INJECTION",
    "NEG-N7-PKXEXC-NM-SAMPLING",
    "NEG-N7-PKXEXC-NM-RECOVERY",
    "NEG-N7-PKXEXC-DELIVERY-COUNT",
    "NEG-N7-PKXEXC-RECOVERY-COUNT",
    "NEG-N7-PKXEXC-WRITE-COUNT",
    "NEG-N7-PKXEXC-UNEXPECTED",
    "NEG-N7-PKXEXC-AUTHORITY",
    "NEG-N7-PKXEXC-SCHEDULER-CLAIM",
    "NEG-N7-PKXEXC-SMP-CLAIM",
    "NEG-N7-PKXEXC-TARGET-CLAIM",
    "NEG-N7-PKXEXC-SOURCE-AUDIT",
    "NEG-N7-PKXEXC-MACHINE-CODE-AUDIT",
    "NEG-N7-PKXEXC-LLVM-BINDING",
)

HEX64 = r"(0x[0-9A-F]{16})"
SETUP = re.compile(
    rf"^POOLEOS:KERNEL:XSTATE-EXCEPTION-SETUP PASS contract=(PKXEXC1) "
    rf"parent=(PKXSTATE1) selector=([0-9]+) bsp=([01]) gates=([0-9]+) "
    rf"vectors=(7,16,19) ist=([0-9]+) xcr0={HEX64} cr0={HEX64} cr4={HEX64} "
    r"parent_control_writes=([0-9]+) exceptions_masked_default=([01]) if=([01])$"
)
ARM = re.compile(
    rf"^POOLEOS:KERNEL:XSTATE-EXCEPTION-ARM PASS contract=(PKXEXC1) "
    rf"sequence=(16,19,7) x87=(invalid) fcw={HEX64} simd=(invalid) mxcsr={HEX64} "
    r"nm_strategy=(eager_reject)$"
)
ENTER = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-ENTER PASS contract=(PKXEXC1) "
    r"kind=(x87_invalid|simd_invalid|device_not_available) vector=([0-9]+) "
    rf"error={HEX64} depth=([0-9]+) ist=([0-9]+)$"
)
STATE = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-STATE PASS contract=(PKXEXC1) "
    r"kind=(x87_invalid|simd_invalid) "
    rf"fcw_before={HEX64} fsw_before={HEX64} mxcsr_before={HEX64} "
    rf"fcw_after={HEX64} fsw_after={HEX64} mxcsr_after={HEX64} state_sampled=([01])$"
)
RETURN = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-RETURN PASS contract=(PKXEXC1) "
    r"vector=([0-9]+) resume=(exact) returned=([0-9]+) recovery_write=([01])$"
)
NM_ARM = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-ARM PASS contract=(PKXEXC1) vector=(7) "
    r"injection=(test_only) cr0_ts=([01]) recovery=(forbidden) terminal=(reject)$"
)
NM_REJECT = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-REJECT PASS contract=(PKXEXC1) vector=(7) "
    r"strategy=(eager) reason=(ts_set) injection=(test_only) state_sampled=([01]) "
    r"recovery=(forbidden) terminal=(halt)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-RESULT PASS contract=(PKXEXC1) "
    r"deliveries=([0-9]+) recovered=([0-9]+) nm_rejected=([0-9]+) "
    r"privileged_writes=([0-9]+) recovery_writes=([0-9]+) unexpected=([0-9]+) "
    r"signatures=([0-9]+) authority=([0-9]+) actions=([0-9]+) scheduler=([01]) "
    r"smp=([01]) target=([01]) terminal=(halt)$"
)


class KernelXstateExceptionError(ValueError):
    """Raised when PKXEXC1 data violates the frozen contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelXstateExceptionError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelXstateExceptionError("binding path escapes repository") from error
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
        "parent_contract": file_binding(
            root / "specs/native-kernel-xstate-policy-contract.json", root
        ),
        "implementation_inputs": [
            file_binding(root / item, root) for item in IMPLEMENTATION_INPUTS
        ],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "parent_x87_sse_xsave_policy_revalidated": True,
        "x87_invalid_exception_delivered_and_recovered": True,
        "simd_invalid_exception_delivered_and_recovered": True,
        "eager_nm_policy_rejection_delivered": True,
        "exact_resume_sites_observed": True,
        "linked_machine_code_scope_audited": True,
        "qemu_tcg_xm_non_delivery_limitation_observed": True,
        "rust_python_policy_agreement": True,
        "two_qemu_runs_exact_match": True,
        "lazy_nm_recovery_qualified": False,
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
        errors.append("PKXEXC1 identity changed")
    profile = contract.get("development_profile", {})
    if not isinstance(profile, dict) or tuple(
        profile.get(key) for key in ("feature", "selector", "cpu_model", "bsp_only")
    ) != (FEATURE, SELECTOR, CPU_MODEL, True):
        errors.append("PKXEXC1 development profile changed")
    policy = contract.get("exception_policy", {})
    if not isinstance(policy, dict) or tuple(
        policy.get(key)
        for key in (
            "parent_contract",
            "delivery_sequence",
            "x87_invalid_fcw",
            "simd_invalid_mxcsr",
            "recoverable_vectors",
            "terminal_vector",
            "nm_strategy",
            "descriptor_gate_count",
            "ist_index",
        )
    ) != (
        "PKXSTATE1",
        [16, 19, 7],
        X87_INVALID_FCW,
        SIMD_INVALID_MXCSR,
        [16, 19],
        7,
        "eager_reject_test_only",
        8,
        1,
    ):
        errors.append("PKXEXC1 exception policy changed")
    authority = contract.get("authority_gate", {})
    if not isinstance(authority, dict) or tuple(
        authority.get(key)
        for key in (
            "privileged_configuration_writes",
            "recovery_state_writes",
            "msr_writes",
            "signature_verifications",
            "authority_grants",
            "actions_authorized",
            "physical_media_writes",
        )
    ) != (4, 2, 0, 0, 0, 0, 0):
        errors.append("PKXEXC1 authority boundary changed")
    qualification = contract.get("qualification", {})
    if (
        not isinstance(qualification, dict)
        or qualification.get("qemu_run_count") != 2
        or qualification.get("tcg_limitation_probe_count") != 1
        or qualification.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS)
        or contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS)
    ):
        errors.append("PKXEXC1 qualification changed")
    tool = contract.get("machine_code_audit_tool", {})
    if not isinstance(tool, dict) or tuple(
        tool.get(key)
        for key in (
            "relative_path",
            "version",
            "byte_count",
            "sha256",
            "archive_url",
            "archive_sha256",
            "license",
        )
    ) != (
        LLVM_OBJDUMP_RELATIVE,
        LLVM_OBJDUMP_VERSION,
        LLVM_OBJDUMP_BYTES,
        LLVM_OBJDUMP_SHA256,
        LLVM_TOOLS_ARCHIVE_URL,
        LLVM_TOOLS_ARCHIVE_SHA256,
        "Apache-2.0 WITH LLVM-exception",
    ):
        errors.append("PKXEXC1 LLVM binding changed")
    sources = contract.get("source_register", [])
    if not isinstance(sources, list) or len(sources) != 2 or tuple(
        sources[0].get(key)
        for key in (
            "authority",
            "publication",
            "revision",
            "captured_byte_count",
            "captured_sha256",
        )
    ) != (
        "AMD",
        "24593",
        "3.44",
        12_560_767,
        "3D9DCB3F68222392D0EDE9970EFC95E31A047A247D54B454123D6981D278C48C",
    ):
        errors.append("PKXEXC1 source binding changed")
    elif tuple(
        sources[1].get(key) for key in ("authority", "issue", "status", "url")
    ) != (
        "QEMU Project",
        215,
        "open_observed_2026-07-21",
        "https://gitlab.com/qemu-project/qemu/-/issues/215",
    ):
        errors.append("PKXEXC1 QEMU limitation source binding changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKXEXC1 claim boundary changed")
    if (
        contract.get("production_ready") is not False
        or contract.get("production_promotion_allowed") is not False
    ):
        errors.append("PKXEXC1 overclaims production")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors = [
        f"schema {item.path}: {item.message}"
        for item in validate_json(readiness, schema)
    ]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKXEXC1 input bindings changed")
    if (
        readiness.get("claims") != expected_claims()
        or readiness.get("non_claims") != contract.get("non_claims")
    ):
        errors.append("PKXEXC1 readiness boundary changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or len(controls) != len(NEGATIVE_CONTROL_IDS)
        or [item.get("id") for item in controls if isinstance(item, dict)]
        != list(NEGATIVE_CONTROL_IDS)
        or any(
            not isinstance(item, dict) or item.get("status") != "pass"
            for item in controls
        )
    ):
        errors.append("PKXEXC1 hostile controls changed")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or tuple(
        execution.get(key) for key in ("run_count", "cpu_model", "exact_marker_match")
    ) != (2, CPU_MODEL, True):
        errors.append("PKXEXC1 execution changed")
    if (
        readiness.get("production_ready") is not False
        or readiness.get("n7_exit_gate_satisfied") is not False
    ):
        errors.append("PKXEXC1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelXstateExceptionError(
            f"PKXEXC1 {name} marker violates contract: {marker!r}"
        )
    return match


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def _validate_prefix(markers: list[str]) -> dict[str, Any]:
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise KernelXstateExceptionError("PKXEXC1 selector changed")
    baseline = markers[:PREFIX_MARKER_COUNT]
    baseline[23] = re.sub(
        r"trap_scenario=[0-6]", "trap_scenario=0", baseline[23], count=1
    )
    terminal = (
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers([*baseline, terminal])
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelXstateExceptionError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def _parse_enter(marker: str, kind: str, vector: int) -> dict[str, Any]:
    match = _match(ENTER, marker, f"{kind} enter")
    value = {
        "kind": match.group(2),
        "vector": int(match.group(3)),
        "error": _hex(match, 4),
        "depth": int(match.group(5)),
        "ist": int(match.group(6)),
    }
    if tuple(value.values()) != (kind, vector, 0, 1, 1):
        raise KernelXstateExceptionError(f"PKXEXC1 {kind} frame changed")
    return value


def _parse_state(marker: str, kind: str) -> dict[str, Any]:
    match = _match(STATE, marker, f"{kind} state")
    value = {
        "kind": match.group(2),
        "fcw_before": _hex(match, 3),
        "fsw_before": _hex(match, 4),
        "mxcsr_before": _hex(match, 5),
        "fcw_after": _hex(match, 6),
        "fsw_after": _hex(match, 7),
        "mxcsr_after": _hex(match, 8),
        "state_sampled": int(match.group(9)),
    }
    if value["kind"] != kind or value["state_sampled"] != 1:
        raise KernelXstateExceptionError(f"PKXEXC1 {kind} state identity changed")
    if kind == "x87_invalid":
        if (
            value["fcw_before"] != X87_INVALID_FCW
            or value["fsw_before"] & 0x81 != 0x81
            or value["mxcsr_before"] != INITIAL_MXCSR
        ):
            raise KernelXstateExceptionError("PKXEXC1 x87 pending state changed")
    elif (
        value["fcw_before"] != INITIAL_FCW
        or value["fsw_before"] & 0x80FF
        or value["mxcsr_before"] != SIMD_INVALID_MXCSR | 1
    ):
        raise KernelXstateExceptionError("PKXEXC1 SIMD pending state changed")
    if (
        value["fcw_after"] != INITIAL_FCW
        or value["fsw_after"] & 0x80FF
        or value["mxcsr_after"] != INITIAL_MXCSR
    ):
        raise KernelXstateExceptionError(f"PKXEXC1 {kind} recovery state changed")
    return value


def _parse_return(marker: str, vector: int, returned: int) -> dict[str, Any]:
    match = _match(RETURN, marker, f"vector {vector} return")
    value = {
        "vector": int(match.group(2)),
        "resume": match.group(3),
        "returned": int(match.group(4)),
        "recovery_write": int(match.group(5)),
    }
    if tuple(value.values()) != (vector, "exact", returned, 1):
        raise KernelXstateExceptionError(f"PKXEXC1 vector {vector} return changed")
    return value


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelXstateExceptionError(
            f"expected {MARKER_COUNT} markers, observed {len(markers)}"
        )
    prefix = _validate_prefix(markers)
    setup_match = _match(SETUP, markers[29], "setup")
    setup = {
        "parent": setup_match.group(2),
        "selector": int(setup_match.group(3)),
        "bsp": int(setup_match.group(4)),
        "gates": int(setup_match.group(5)),
        "vectors": setup_match.group(6),
        "ist": int(setup_match.group(7)),
        "xcr0": _hex(setup_match, 8),
        "cr0": _hex(setup_match, 9),
        "cr4": _hex(setup_match, 10),
        "parent_control_writes": int(setup_match.group(11)),
        "exceptions_masked_default": int(setup_match.group(12)),
        "interrupts": int(setup_match.group(13)),
    }
    if tuple(
        setup[key]
        for key in (
            "parent",
            "selector",
            "bsp",
            "gates",
            "vectors",
            "ist",
            "xcr0",
            "parent_control_writes",
            "exceptions_masked_default",
            "interrupts",
        )
    ) != ("PKXSTATE1", 6, 1, 8, "7,16,19", 1, 3, 3, 1, 0):
        raise KernelXstateExceptionError("PKXEXC1 setup changed")
    if setup["cr0"] & REQUIRED_CR0 != REQUIRED_CR0 or setup["cr0"] & FORBIDDEN_CR0:
        raise KernelXstateExceptionError("PKXEXC1 CR0 setup changed")
    if setup["cr4"] & REQUIRED_CR4 != REQUIRED_CR4:
        raise KernelXstateExceptionError("PKXEXC1 CR4 setup changed")

    arm_match = _match(ARM, markers[30], "arm")
    arm = {
        "sequence": arm_match.group(2),
        "x87": arm_match.group(3),
        "fcw": _hex(arm_match, 4),
        "simd": arm_match.group(5),
        "mxcsr": _hex(arm_match, 6),
        "nm_strategy": arm_match.group(7),
    }
    if tuple(arm.values()) != (
        "16,19,7",
        "invalid",
        X87_INVALID_FCW,
        "invalid",
        SIMD_INVALID_MXCSR,
        "eager_reject",
    ):
        raise KernelXstateExceptionError("PKXEXC1 arm sequence changed")

    x87 = {
        "enter": _parse_enter(markers[31], "x87_invalid", 16),
        "state": _parse_state(markers[32], "x87_invalid"),
        "return": _parse_return(markers[33], 16, 1),
    }
    simd = {
        "enter": _parse_enter(markers[34], "simd_invalid", 19),
        "state": _parse_state(markers[35], "simd_invalid"),
        "return": _parse_return(markers[36], 19, 2),
    }
    nm_arm_match = _match(NM_ARM, markers[37], "NM arm")
    nm_arm = {
        "vector": int(nm_arm_match.group(2)),
        "injection": nm_arm_match.group(3),
        "cr0_ts": int(nm_arm_match.group(4)),
        "recovery": nm_arm_match.group(5),
        "terminal": nm_arm_match.group(6),
    }
    if tuple(nm_arm.values()) != (7, "test_only", 1, "forbidden", "reject"):
        raise KernelXstateExceptionError("PKXEXC1 NM arm changed")
    nm_enter = _parse_enter(markers[38], "device_not_available", 7)
    nm_match = _match(NM_REJECT, markers[39], "NM reject")
    nm = {
        "vector": int(nm_match.group(2)),
        "strategy": nm_match.group(3),
        "reason": nm_match.group(4),
        "injection": nm_match.group(5),
        "state_sampled": int(nm_match.group(6)),
        "recovery": nm_match.group(7),
        "terminal": nm_match.group(8),
    }
    if tuple(nm.values()) != (
        7,
        "eager",
        "ts_set",
        "test_only",
        0,
        "forbidden",
        "halt",
    ):
        raise KernelXstateExceptionError("PKXEXC1 NM rejection changed")

    result_match = _match(RESULT, markers[40], "result")
    result = {
        "deliveries": int(result_match.group(2)),
        "recovered": int(result_match.group(3)),
        "nm_rejected": int(result_match.group(4)),
        "privileged_writes": int(result_match.group(5)),
        "recovery_writes": int(result_match.group(6)),
        "unexpected": int(result_match.group(7)),
        "signatures": int(result_match.group(8)),
        "authority": int(result_match.group(9)),
        "actions": int(result_match.group(10)),
        "scheduler": int(result_match.group(11)),
        "smp": int(result_match.group(12)),
        "target": int(result_match.group(13)),
        "terminal": result_match.group(14),
    }
    if tuple(result.values()) != (3, 2, 1, 4, 2, 0, 0, 0, 0, 0, 0, 0, "halt"):
        raise KernelXstateExceptionError("PKXEXC1 result boundary changed")
    return {
        "transfer_prefix": prefix,
        "setup": setup,
        "arm": arm,
        "x87": x87,
        "simd": simd,
        "nm_arm": nm_arm,
        "nm_enter": nm_enter,
        "nm": nm,
        "result": result,
    }
