"""Independent PKTRAP1 oracle for bounded BSP exception-entry evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKTRAP1"
SELECTED_MOVE_ID = "N7-TRAP-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-trap-contract.json"
SCHEMA_RELATIVE = "specs/native-kernel-trap-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-trap-readiness.json"
FRAME_RELATIVE = "runs/native-kernel-trap-frame.ppm"
PREFIX_MARKER_COUNT = 29
SCENARIOS = {
    "returning": {
        "selector": 1,
        "feature": "development-trap-returning",
        "marker_count": 38,
        "completion": b"POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 scenario=returning",
    },
    "double_fault": {
        "selector": 2,
        "feature": "development-trap-double-fault",
        "marker_count": 33,
        "completion": b"POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 scenario=double_fault",
    },
    "malformed_frame": {
        "selector": 3,
        "feature": "development-trap-malformed-frame",
        "marker_count": 34,
        "completion": b"POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 scenario=malformed_frame",
    },
}
IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "runtime/native_kernel_transfer.py",
    "runtime/native_kernel_trap.py",
    "tools/qualify_native_kernel_trap.py",
    "tests/test_native_kernel_trap.py",
    "docs/native-kernel-trap.md",
)

NEGATIVE_CONTROL_IDS = tuple(
    f"NEG-N7-PKTRAP-{scenario.upper().replace('_', '-')}-{suffix}"
    for scenario in SCENARIOS
    for suffix in (
        "MARKER-OMISSION",
        "MARKER-ORDER",
        "MARKER-DUPLICATE",
        "SELECTOR",
        "SETUP-SCENARIO",
        "GDT-LIMIT",
        "IDT-LIMIT",
        "GATE-COUNT",
        "STACK-BYTES",
        "INTERRUPT-FLAG",
    )
) + (
    "NEG-N7-PKTRAP-RETURNING-ARM-SEQUENCE",
    "NEG-N7-PKTRAP-RETURNING-VECTOR-ORDER",
    "NEG-N7-PKTRAP-RETURNING-ERROR-CODE",
    "NEG-N7-PKTRAP-RETURNING-DEPTH",
    "NEG-N7-PKTRAP-RETURNING-IST",
    "NEG-N7-PKTRAP-RETURNING-RESUME",
    "NEG-N7-PKTRAP-RETURNING-RETURN-COUNT",
    "NEG-N7-PKTRAP-RETURNING-RESULT-COUNT",
    "NEG-N7-PKTRAP-RETURNING-TERMINAL",
    "NEG-N7-PKTRAP-DOUBLE-FAULT-ARM-TRIGGER",
    "NEG-N7-PKTRAP-DOUBLE-FAULT-VECTOR",
    "NEG-N7-PKTRAP-DOUBLE-FAULT-ERROR-CODE",
    "NEG-N7-PKTRAP-DOUBLE-FAULT-DEPTH",
    "NEG-N7-PKTRAP-DOUBLE-FAULT-IST",
    "NEG-N7-PKTRAP-DOUBLE-FAULT-TERMINAL",
    "NEG-N7-PKTRAP-MALFORMED-FRAME-ARM-CONTROL",
    "NEG-N7-PKTRAP-MALFORMED-FRAME-VECTOR",
    "NEG-N7-PKTRAP-MALFORMED-FRAME-SOURCE",
    "NEG-N7-PKTRAP-MALFORMED-FRAME-CONTROL",
    "NEG-N7-PKTRAP-MALFORMED-FRAME-REJECTED",
    "NEG-N7-PKTRAP-MALFORMED-FRAME-TERMINAL",
)

SETUP = re.compile(
    r"^POOLEOS:KERNEL:TRAP-SETUP PASS contract=(PKTRAP1) "
    r"scenario=(returning|double_fault|malformed_frame) bsp=([01]) "
    r"gdt_limit=([0-9]+) idt_limit=([0-9]+) gates=([0-9]+) "
    r"tss=([01]) rsp0=([01]) ist1=([0-9]+) ist2=([0-9]+) "
    r"stack_bytes=([0-9]+) if=([01])$"
)
ENTER = re.compile(
    r"^POOLEOS:KERNEL:TRAP-ENTER PASS contract=(PKTRAP1) "
    r"scenario=(returning|double_fault|malformed_frame) vector=([0-9]+) "
    r"error=(0x[0-9A-F]{16}) depth=([0-9]+) ist=([0-9]+)$"
)
RETURN = re.compile(
    r"^POOLEOS:KERNEL:TRAP-RETURN PASS contract=(PKTRAP1) scenario=(returning) "
    r"vector=([0-9]+) resume=(exact) returned=([0-9]+)$"
)


class KernelTrapError(ValueError):
    """Raised when PKTRAP1 evidence violates its bounded contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelTrapError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelTrapError("binding path escapes the repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def expected_claims() -> dict[str, bool]:
    return {
        "corrected_x86_64_canonical_address_validation": True,
        "bsp_gdt_loaded_and_read_back": True,
        "bsp_tss_loaded_and_read_back": True,
        "bsp_idt_loaded_and_read_back": True,
        "dedicated_fault_ist_observed": True,
        "dedicated_double_fault_ist_observed": True,
        "uniform_integer_trap_frame_observed": True,
        "breakpoint_return_observed": True,
        "invalid_opcode_return_observed": True,
        "guard_page_fault_return_observed": True,
        "double_fault_terminal_containment_observed": True,
        "synthetic_malformed_frame_semantics_rejected": True,
        "six_qemu_runs_exact_within_scenario": True,
        "serial_debugcon_exact_match": True,
        "interrupts_enabled": False,
        "all_256_vectors_installed": False,
        "ist_guard_pages_installed": False,
        "per_cpu_descriptor_tables": False,
        "nmi_machine_check_containment": False,
        "asynchronous_interrupt_state_preserved": False,
        "n7_exit_gate_satisfied": False,
        "production_ready": False,
    }


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "tier0_lock": file_binding(root / "specs/native-tier0-lock.json", root),
        "tier0_profile": file_binding(root / "specs/native-tier0-profile.json", root),
        "kernel_entry_contract": file_binding(
            root / "specs/native-kernel-entry-contract.json", root
        ),
        "kernel_transfer_contract": file_binding(
            root / native_kernel_transfer.CONTRACT_RELATIVE, root
        ),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }


def contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("selected_move_id") != SELECTED_MOVE_ID
    ):
        errors.append("PKTRAP1 contract identity changed")
    if (
        contract.get("production_ready") is not False
        or contract.get("production_promotion_allowed") is not False
    ):
        errors.append("PKTRAP1 contract overclaims production")
    scenarios = contract.get("scenarios", [])
    expected_scenarios = [
        {
            "id": name,
            "selector": profile["selector"],
            "feature": profile["feature"],
            "qemu_runs": 2,
            "marker_count": profile["marker_count"],
        }
        for name, profile in SCENARIOS.items()
    ]
    if scenarios != expected_scenarios:
        errors.append("PKTRAP1 scenario profile changed")
    descriptor = contract.get("descriptor_profile", {})
    if not isinstance(descriptor, dict) or tuple(
        descriptor.get(key)
        for key in (
            "gdt_limit",
            "idt_limit",
            "installed_gate_count",
            "ist_stack_bytes",
            "ist_guard_pages",
            "bsp_only",
        )
    ) != (39, 4095, 5, 8192, 0, True):
        errors.append("PKTRAP1 descriptor boundary changed")
    authority = contract.get("authority_gate", {})
    if not isinstance(authority, dict) or any(
        authority.get(key) != 0
        for key in (
            "signature_verifications",
            "authority_grants",
            "actions_authorized",
            "state_writes",
            "firmware_calls_after_exit",
        )
    ):
        errors.append("PKTRAP1 zero-authority boundary changed")
    qualification = contract.get("qualification", {})
    if (
        not isinstance(qualification, dict)
        or qualification.get("qemu_run_count") != 6
        or qualification.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS)
        or contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS)
    ):
        errors.append("PKTRAP1 qualification boundary changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKTRAP1 claim boundary changed")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("PKTRAP1 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    scenario_runs = execution.get("scenarios", []) if isinstance(execution, dict) else []
    if (
        not isinstance(scenario_runs, list)
        or len(scenario_runs) != 3
        or sum(item.get("run_count", 0) for item in scenario_runs if isinstance(item, dict)) != 6
        or any(
            not isinstance(item, dict)
            or item.get("run_count") != 2
            or item.get("exact_marker_match") is not True
            or item.get("exact_screenshot_match") is not True
            or item.get("exact_pbp1_match") is not True
            for item in scenario_runs
        )
    ):
        errors.append("PKTRAP1 six-run evidence changed")
    controls = readiness.get("negative_controls", [])
    if (
        not isinstance(controls, list)
        or len(controls) != len(NEGATIVE_CONTROL_IDS)
        or [item.get("id") for item in controls if isinstance(item, dict)]
        != list(NEGATIVE_CONTROL_IDS)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKTRAP1 hostile-control evidence changed")
    summary = readiness.get("summary", {})
    if not isinstance(summary, dict) or tuple(
        summary.get(key)
        for key in (
            "scenario_count",
            "qemu_run_count",
            "returning_exception_count",
            "terminal_double_fault_count",
            "malformed_frame_rejection_count",
            "negative_controls_passed",
            "signature_verifications",
            "authority_grants",
            "actions_authorized",
            "state_writes",
            "firmware_calls_after_exit",
        )
    ) != (3, 6, 3, 1, 1, len(NEGATIVE_CONTROL_IDS), 0, 0, 0, 0, 0):
        errors.append("PKTRAP1 readiness summary changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKTRAP1 readiness claim boundary changed")
    if readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PKTRAP1 non-claim boundary changed")
    if (
        readiness.get("production_ready") is not False
        or readiness.get("production_promotion_allowed") is not False
        or readiness.get("n7_exit_gate_satisfied") is not False
    ):
        errors.append("PKTRAP1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelTrapError(f"PKTRAP1 {name} marker violates its contract: {marker!r}")
    return match


def _validate_prefix(markers: list[str], scenario: str) -> dict[str, Any]:
    profile = SCENARIOS[scenario]
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != profile["selector"]:
        raise KernelTrapError("PKTRAP1 transfer selector diverges from its scenario")
    baseline = markers[:PREFIX_MARKER_COUNT]
    baseline[23] = re.sub(r"trap_scenario=[0-5]", "trap_scenario=0", baseline[23], count=1)
    synthetic_terminal = (
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers([*baseline, synthetic_terminal])
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelTrapError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = profile["selector"]
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def _validate_setup(marker: str, scenario: str) -> dict[str, Any]:
    match = _match(SETUP, marker, "setup")
    values = {
        "contract_id": match.group(1),
        "scenario": match.group(2),
        "bsp": int(match.group(3)),
        "gdt_limit": int(match.group(4)),
        "idt_limit": int(match.group(5)),
        "gate_count": int(match.group(6)),
        "tss": int(match.group(7)),
        "rsp0": int(match.group(8)),
        "ist1": int(match.group(9)),
        "ist2": int(match.group(10)),
        "stack_bytes": int(match.group(11)),
        "interrupt_flag": int(match.group(12)),
    }
    if tuple(values[key] for key in values if key != "contract_id") != (
        scenario,
        1,
        39,
        4095,
        5,
        1,
        1,
        1,
        2,
        8192,
        0,
    ):
        raise KernelTrapError("PKTRAP1 descriptor setup changed")
    return values


def _validate_enter(marker: str, scenario: str, vector: int, ist: int) -> dict[str, Any]:
    match = _match(ENTER, marker, "entry")
    values = {
        "scenario": match.group(2),
        "vector": int(match.group(3)),
        "error_code": int(match.group(4), 16),
        "depth": int(match.group(5)),
        "ist": int(match.group(6)),
    }
    if tuple(values.values()) != (scenario, vector, 0, 1, ist):
        raise KernelTrapError("PKTRAP1 normalized trap entry changed")
    return values


def validate_markers(markers: list[str], scenario: str) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise KernelTrapError("unknown PKTRAP1 scenario")
    expected_count = SCENARIOS[scenario]["marker_count"]
    if len(markers) != expected_count:
        raise KernelTrapError(
            f"expected {expected_count} PKTRAP1 {scenario} markers, observed {len(markers)}"
        )
    prefix = _validate_prefix(markers, scenario)
    setup = _validate_setup(markers[29], scenario)

    if scenario == "returning":
        if markers[30] != (
            "POOLEOS:KERNEL:TRAP-ARM PASS contract=PKTRAP1 "
            "scenario=returning sequence=3,6,14"
        ):
            raise KernelTrapError("PKTRAP1 returning arm marker changed")
        entries: list[dict[str, Any]] = []
        for pair_index, vector in enumerate((3, 6, 14)):
            entry_index = 31 + pair_index * 2
            entries.append(_validate_enter(markers[entry_index], scenario, vector, 1))
            returned = _match(RETURN, markers[entry_index + 1], "return")
            if (int(returned.group(3)), returned.group(4), int(returned.group(5))) != (
                vector,
                "exact",
                pair_index + 1,
            ):
                raise KernelTrapError("PKTRAP1 returning disposition changed")
        if markers[37] != (
            "POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 "
            "scenario=returning vectors=3,6,14 returned=3 terminal=halt"
        ):
            raise KernelTrapError("PKTRAP1 returning result changed")
        result = {"entries": entries, "returned": 3, "terminal": "halt"}
    elif scenario == "double_fault":
        if markers[30] != (
            "POOLEOS:KERNEL:TRAP-ARM PASS contract=PKTRAP1 scenario=double_fault "
            "trigger=gp_delivery_failure gp_gate_present=0"
        ):
            raise KernelTrapError("PKTRAP1 double-fault arm marker changed")
        entry = _validate_enter(markers[31], scenario, 8, 2)
        if markers[32] != (
            "POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 "
            "scenario=double_fault vector=8 ist=2 terminal=halt"
        ):
            raise KernelTrapError("PKTRAP1 double-fault result changed")
        result = {"entries": [entry], "double_faults": 1, "terminal": "halt"}
    else:
        if markers[30] != (
            "POOLEOS:KERNEL:TRAP-ARM PASS contract=PKTRAP1 scenario=malformed_frame "
            "vector=3 control=code_selector"
        ):
            raise KernelTrapError("PKTRAP1 malformed-frame arm marker changed")
        entry = _validate_enter(markers[31], scenario, 3, 1)
        if markers[32] != (
            "POOLEOS:KERNEL:TRAP-MALFORMED DENIED contract=PKTRAP1 "
            "scenario=malformed_frame control=code_selector source=synthetic_semantic"
        ):
            raise KernelTrapError("PKTRAP1 malformed-frame denial changed")
        if markers[33] != (
            "POOLEOS:KERNEL:TRAP-RESULT PASS contract=PKTRAP1 "
            "scenario=malformed_frame rejected=1 terminal=halt"
        ):
            raise KernelTrapError("PKTRAP1 malformed-frame result changed")
        result = {"entries": [entry], "rejected": 1, "terminal": "halt"}

    return {
        "scenario": scenario,
        "selector": SCENARIOS[scenario]["selector"],
        "marker_count": len(markers),
        "ordered_contract_match": True,
        "transfer_prefix": prefix,
        "descriptor_setup": setup,
        "result": result,
    }


assert len(NEGATIVE_CONTROL_IDS) == 51
