"""Independent PKXFER1 oracle for PooleBoot-to-PooleKernel transfer evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence

from runtime import (
    native_boot_exit,
    native_elf_loader,
    native_kernel_load,
    native_kernel_revalidation,
)
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKXFER1"
SELECTED_MOVE_ID = "N5-KERNEL-TRANSFER-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-transfer-contract.json"
SCHEMA_RELATIVE = "specs/native-kernel-transfer-readiness.schema.json"
READINESS_RELATIVE = "runs/native-kernel-transfer-readiness.json"
MARKER_COUNT = 30
BOOT_PREFIX_MARKER_COUNT = 23
KERNEL_MARKER_COUNT = 5
COMPLETION_MARKER = b"POOLEOS:KERNEL:TRANSFER-DENIED PASS"
KERNEL_BUILD_ID = "PKBUILD1-CYCLE132-N9-PMM-GROWTH-AUTOMATION-001"
TRANSFER_BOUNDARY = (
    "POOLEBOOT/0.1 BOUNDARY unsigned=1 secure_boot=not_tested "
    "selection=manifest_digest_untrusted artifacts=digest_verified_untrusted "
    "semantics=parsed_live_unsigned_denied authority=none actions=none "
    "kernel=retained handoff=retained mappings=retained entry=armed "
    "exit_boot_services=called transfer=one_way_development"
)
IMPLEMENTATION_INPUTS = (
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/boot/src/kmap.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/revalidation.rs",
    "runtime/native_kernel_transfer.py",
    "tools/qualify_native_kernel_transfer.py",
    "tests/test_native_kernel_transfer.py",
    "docs/native-kernel-transfer.md",
    "runs/native_kernel_entry_readiness.json",
    "runs/native-kernel-revalidation-readiness.json",
    "runs/native_kernel_load_readiness.json",
)
NEGATIVE_CONTROL_IDS = (
    "NEG-N5-PKXFER-MARKER-OMISSION",
    "NEG-N5-PKXFER-MARKER-ORDER",
    "NEG-N5-PKXFER-MARKER-DUPLICATE",
    "NEG-N5-PKXFER-ARM-CONTRACT",
    "NEG-N5-PKXFER-ARM-MODE",
    "NEG-N5-PKXFER-ARM-EMULATOR",
    "NEG-N5-PKXFER-ARM-ENTRY",
    "NEG-N5-PKXFER-ARM-HANDOFF",
    "NEG-N5-PKXFER-ARM-BYTE-COUNT",
    "NEG-N5-PKXFER-ARM-STACK",
    "NEG-N5-PKXFER-ARM-ROOT",
    "NEG-N5-PKXFER-ARM-CR3",
    "NEG-N5-PKXFER-ARM-TRAP-SCENARIO",
    "NEG-N5-PKXFER-ARM-SIGNATURE",
    "NEG-N5-PKXFER-ARM-AUTHORITY",
    "NEG-N5-PKXFER-ARM-ACTION",
    "NEG-N5-PKXFER-ARM-STATE-WRITE",
    "NEG-N5-PKXFER-ARM-FIRMWARE",
    "NEG-N5-PKXFER-BOUNDARY",
    "NEG-N5-PKXFER-ENTRY-CONTRACT",
    "NEG-N5-PKXFER-ENTRY-TRANSFER-CONTRACT",
    "NEG-N5-PKXFER-ENTRY-BUILD",
    "NEG-N5-PKXFER-ENTRY-COUNT",
    "NEG-N5-PKXFER-ENTRY-SERIAL",
    "NEG-N5-PKXFER-STATE-HANDOFF",
    "NEG-N5-PKXFER-STATE-BYTE-COUNT",
    "NEG-N5-PKXFER-STATE-ENTRY",
    "NEG-N5-PKXFER-STATE-STACK",
    "NEG-N5-PKXFER-STATE-ROOT",
    "NEG-N5-PKXFER-STATE-CR3",
    "NEG-N5-PKXFER-STATE-IF",
    "NEG-N5-PKXFER-STATE-DF",
    "NEG-N5-PKXFER-PBP1-PROFILE",
    "NEG-N5-PKXFER-PBP1-RECORD-COUNT",
    "NEG-N5-PKXFER-PBP1-ARTIFACT-COUNT",
    "NEG-N5-PKXFER-PBP1-PRODUCTION",
    "NEG-N5-PKXFER-REVALIDATION-CONTRACT",
    "NEG-N5-PKXFER-REVALIDATION-FILE-COUNT",
    "NEG-N5-PKXFER-REVALIDATION-ARTIFACT-COUNT",
    "NEG-N5-PKXFER-REVALIDATION-PARSER-COUNT",
    "NEG-N5-PKXFER-REVALIDATION-MANIFEST-BYTES",
    "NEG-N5-PKXFER-REVALIDATION-RETAINED-BYTES",
    "NEG-N5-PKXFER-REVALIDATION-RETAINED-DIGEST",
    "NEG-N5-PKXFER-REVALIDATION-POLICY-DIGEST",
    "NEG-N5-PKXFER-REVALIDATION-STATE-DIGEST",
    "NEG-N5-PKXFER-REVALIDATION-DENIAL",
    "NEG-N5-PKXFER-REVALIDATION-AUTHORITY",
    "NEG-N5-PKXFER-REVALIDATION-ACTION",
    "NEG-N5-PKXFER-REVALIDATION-STATE-WRITE",
    "NEG-N5-PKXFER-TERMINAL-CONTRACT",
    "NEG-N5-PKXFER-TERMINAL-MODE",
    "NEG-N5-PKXFER-TERMINAL-ENTRY-COUNT",
    "NEG-N5-PKXFER-TERMINAL-FIRMWARE",
    "NEG-N5-PKXFER-TERMINAL-SIGNATURE",
    "NEG-N5-PKXFER-TERMINAL-AUTHORITY",
    "NEG-N5-PKXFER-TERMINAL-ACTION",
    "NEG-N5-PKXFER-TERMINAL-STATE-WRITE",
    "NEG-N5-PKXFER-UNEXPECTED-RETURN",
)

TRANSFER_ARM = re.compile(
    r"^POOLEBOOT/0\.1 TRANSFER_ARM PASS contract=(PKXFER1) mode=(development) "
    r"emulator_only=([01]) entry=([0-9A-F]{16}) handoff=([0-9A-F]{16}) "
    r"bytes=([0-9]+) stack_top=([0-9A-F]{16}) root=([0-9A-F]{16}) "
    r"cr3=([0-9A-F]{16}) trap_scenario=([0-9]+) signatures=([0-9]+) authority=([0-9]+) "
    r"actions=([0-9]+) writes=([0-9]+) firmware_calls_after_exit=([0-9]+)$"
)
KERNEL_ENTRY = re.compile(
    r"^POOLEOS:KERNEL:ENTRY PASS contract=(PKENTRY1) transfer_contract=(PKXFER1) "
    r"build=(PKBUILD1-[A-Z0-9-]+) entry_count=([0-9]+) serial=(present|absent)$"
)
KERNEL_STATE = re.compile(
    r"^POOLEOS:KERNEL:STATE PASS handoff=(0x[0-9A-F]{16}) bytes=([0-9]+) "
    r"entry=(0x[0-9A-F]{16}) stack_top=(0x[0-9A-F]{16}) "
    r"root=(0x[0-9A-F]{16}) cr3=(0x[0-9A-F]{16}) "
    r"rflags_if=([01]) rflags_df=([01])$"
)
KERNEL_PBP1 = re.compile(
    r"^POOLEOS:KERNEL:PBP1 PASS profile=(development) records=([0-9]+) "
    r"artifacts=([0-9]+) production_profile_valid=([01])$"
)
KERNEL_REVALIDATION = re.compile(
    r"^POOLEOS:KERNEL:PKREVAL PASS contract=(PKREVAL1) files=([0-9]+) "
    r"artifacts=([0-9]+) parsers=([0-9]+) manifest_bytes=([0-9]+) "
    r"retained_bytes=([0-9]+) retained_set_sha256=([0-9A-F]{64}) "
    r"policy_sha256=([0-9A-F]{64}) state_sha256=([0-9A-F]{64}) "
    r"denial=(pbtrust_policy_unsigned) authority=([0-9]+) actions=([0-9]+) "
    r"writes=([0-9]+)$"
)
KERNEL_TERMINAL = re.compile(
    r"^POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=(PKXFER1) terminal=(halt) "
    r"entry_count=([0-9]+) post_exit_firmware_calls=([0-9]+) "
    r"signatures=([0-9]+) authority=([0-9]+) actions=([0-9]+) writes=([0-9]+)$"
)


class KernelTransferError(ValueError):
    """Raised when PKXFER1 evidence violates its bounded contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelTransferError(f"JSON object required: {path.name}")
    return value


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelTransferError("binding path escapes the repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def expected_claims() -> dict[str, bool]:
    return {
        "exit_boot_services_succeeded_before_transfer": True,
        "retained_cr3_installed": True,
        "bootstrap_stack_installed": True,
        "sysv_register_contract_observed": True,
        "interrupts_and_direction_flag_cleared": True,
        "live_poolekernel_entry_executed": True,
        "exact_pbp1_revalidated_in_kernel": True,
        "nine_retained_files_revalidated_in_kernel": True,
        "serial_debugcon_exact_match": True,
        "two_qemu_runs_exact_match": True,
        "terminal_unsigned_denial": True,
        "default_pooleboot_transfer_enabled": False,
        "authenticated_kernel_entry_profile_valid": False,
        "target_firmware_qualified": False,
        "physical_media_written": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("selected_move_id") != SELECTED_MOVE_ID
    ):
        errors.append("PKXFER1 contract identity changed")
    if (
        contract.get("production_ready") is not False
        or contract.get("production_promotion_allowed") is not False
    ):
        errors.append("PKXFER1 contract overclaims production")
    profile = contract.get("transfer_profile", {})
    if not isinstance(profile, dict) or (
        profile.get("feature"),
        profile.get("emulator_only"),
        profile.get("marker_count"),
        profile.get("kernel_marker_count"),
        profile.get("terminal_result"),
        profile.get("trap_scenario"),
    ) != (
        "development-transfer",
        True,
        MARKER_COUNT,
        KERNEL_MARKER_COUNT,
        "halt_unsigned_denial",
        0,
    ):
        errors.append("PKXFER1 transfer profile changed")
    authority = contract.get("authority_gate", {})
    if not isinstance(authority, dict) or tuple(
        authority.get(key)
        for key in (
            "signature_verifications",
            "authority_grants",
            "actions_authorized",
            "state_writes",
            "firmware_calls_after_exit",
        )
    ) != (0, 0, 0, 0, 0):
        errors.append("PKXFER1 zero-authority gate changed")
    if contract.get("claims") != expected_claims():
        errors.append("PKXFER1 claim boundary changed")
    qualification = contract.get("qualification", {})
    if (
        not isinstance(qualification, dict)
        or qualification.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS)
        or contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS)
    ):
        errors.append("PKXFER1 hostile-control profile changed")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    contract = read_json(root / CONTRACT_RELATIVE)
    errors.extend(contract_errors(contract))
    expected_inputs = {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "tier0_lock": file_binding(root / "specs/native-tier0-lock.json", root),
        "tier0_profile": file_binding(root / "specs/native-tier0-profile.json", root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }
    if readiness.get("inputs") != expected_inputs:
        errors.append("PKXFER1 readiness input bindings are stale")
    execution = readiness.get("execution", {})
    if not isinstance(execution, dict) or (
        execution.get("run_count"),
        execution.get("exact_marker_match"),
        execution.get("exact_screenshot_match"),
        execution.get("exact_pbp1_match"),
    ) != (2, True, True, True):
        errors.append("PKXFER1 two-run evidence changed")
    summary = readiness.get("summary", {})
    if not isinstance(summary, dict) or (
        summary.get("marker_count"),
        summary.get("kernel_marker_count"),
        summary.get("retained_file_count"),
        summary.get("signature_verifications"),
        summary.get("authority_grants"),
        summary.get("actions_authorized"),
        summary.get("state_writes"),
        summary.get("firmware_calls_after_exit"),
    ) != (MARKER_COUNT, KERNEL_MARKER_COUNT, 9, 0, 0, 0, 0, 0):
        errors.append("PKXFER1 summary changed")
    controls = readiness.get("negative_controls", [])
    qualification = contract.get("qualification", {})
    expected_control_count = qualification.get("negative_control_count") if isinstance(qualification, dict) else None
    if (
        not isinstance(controls, list)
        or len(controls) != expected_control_count
        or len({item.get("id") for item in controls if isinstance(item, dict)}) != len(controls)
        or any(not isinstance(item, dict) or item.get("status") != "pass" for item in controls)
    ):
        errors.append("PKXFER1 hostile-control evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PKXFER1 readiness claim boundary changed")
    if readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PKXFER1 non-claim boundary changed")
    if (
        readiness.get("production_ready") is not False
        or readiness.get("production_promotion_allowed") is not False
        or readiness.get("n5_exit_gate_satisfied") is not False
    ):
        errors.append("PKXFER1 readiness overclaims production")
    return errors


def extract_markers(raw: bytes) -> list[str]:
    text = raw.decode("ascii", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    prefixes = ("POOLEBOOT/0.1 ", "POOLEOS:KERNEL:")
    return [line.strip() for line in text.splitlines() if line.strip().startswith(prefixes)]


def _match(pattern: re.Pattern[str], marker: str, name: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    if match is None:
        raise KernelTransferError(f"PKXFER1 {name} marker violates its contract: {marker!r}")
    return match


def _canonical_x86_64(address: int) -> bool:
    sign = (address >> 47) & 1
    upper = address >> 48
    return (sign == 0 and upper == 0) or (sign == 1 and upper == 0xFFFF)


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != MARKER_COUNT:
        raise KernelTransferError(f"expected {MARKER_COUNT} PKXFER1 markers, observed {len(markers)}")

    synthetic_default_tail = [native_boot_exit.DEVELOPMENT_BOUNDARY, native_boot_exit.STOP_MARKER]
    try:
        boot = native_kernel_load.validate_markers(
            [*markers[:BOOT_PREFIX_MARKER_COUNT], *synthetic_default_tail]
        )
    except native_kernel_load.KernelLoadError as error:
        raise KernelTransferError(str(error)) from error
    boot["boot_exit"] = {
        key: value
        for key, value in boot["boot_exit"].items()
        if key not in {"transfer_allowed", "stopped_before_transfer"}
    }
    boot["boot_exit"]["successful_exit_prefix_validated"] = True
    boot["boot_exit"]["synthetic_stop_used_for_prefix_parser_only"] = True

    arm = _match(TRANSFER_ARM, markers[23], "transfer-arm")
    if markers[24] != TRANSFER_BOUNDARY:
        raise KernelTransferError("PKXFER1 one-way development boundary changed")
    entry = _match(KERNEL_ENTRY, markers[25], "kernel-entry")
    state = _match(KERNEL_STATE, markers[26], "kernel-state")
    pbp1 = _match(KERNEL_PBP1, markers[27], "kernel-pbp1")
    revalidation = _match(KERNEL_REVALIDATION, markers[28], "kernel-revalidation")
    terminal = _match(KERNEL_TERMINAL, markers[29], "kernel-terminal")

    arm_values = {
        "contract_id": arm.group(1),
        "mode": arm.group(2),
        "emulator_only": int(arm.group(3)),
        "entry": int(arm.group(4), 16),
        "handoff": int(arm.group(5), 16),
        "handoff_bytes": int(arm.group(6)),
        "stack_top": int(arm.group(7), 16),
        "root": int(arm.group(8), 16),
        "cr3": int(arm.group(9), 16),
        "trap_scenario": int(arm.group(10)),
        "signature_verifications": int(arm.group(11)),
        "authority_grants": int(arm.group(12)),
        "actions_authorized": int(arm.group(13)),
        "state_writes": int(arm.group(14)),
        "firmware_calls_after_exit": int(arm.group(15)),
    }
    retained = boot["kernel_map"]["retained"]
    expected_entry = native_elf_loader.MIN_VIRTUAL_BASE + boot["kernel"]["entry_offset"]
    if (
        arm_values["emulator_only"] != 1
        or arm_values["entry"] != expected_entry
        or arm_values["handoff"] != retained["handoff_virtual_base"]
        or arm_values["handoff_bytes"] != boot["pbp1"]["byte_count"]
        or arm_values["stack_top"] != retained["stack_top_virtual"]
        or arm_values["root"] != retained["page_table_root_physical"]
        or arm_values["cr3"] & ~0x18 & 0xFFF
        or arm_values["cr3"] & ~0xFFF != arm_values["root"]
        or arm_values["trap_scenario"] != 0
        or any(
            arm_values[key]
            for key in (
                "signature_verifications",
                "authority_grants",
                "actions_authorized",
                "state_writes",
                "firmware_calls_after_exit",
            )
        )
        or not all(
            _canonical_x86_64(arm_values[key]) for key in ("entry", "handoff", "stack_top")
        )
    ):
        raise KernelTransferError("PKXFER1 transfer-arm state diverges from retained boot evidence")

    entry_values = {
        "entry_contract": entry.group(1),
        "transfer_contract": entry.group(2),
        "build_id": entry.group(3),
        "entry_count": int(entry.group(4)),
        "serial": entry.group(5),
    }
    if (
        entry_values["build_id"] != KERNEL_BUILD_ID
        or entry_values["entry_count"] != 1
        or entry_values["serial"] != "present"
    ):
        raise KernelTransferError("PKXFER1 kernel entry is not a single dual-channel entry")

    state_values = {
        "handoff": int(state.group(1), 16),
        "handoff_bytes": int(state.group(2)),
        "entry": int(state.group(3), 16),
        "stack_top": int(state.group(4), 16),
        "root": int(state.group(5), 16),
        "cr3": int(state.group(6), 16),
        "rflags_if": int(state.group(7)),
        "rflags_df": int(state.group(8)),
    }
    if (
        tuple(state_values[key] for key in ("handoff", "handoff_bytes", "entry", "stack_top", "root", "cr3"))
        != tuple(arm_values[key] for key in ("handoff", "handoff_bytes", "entry", "stack_top", "root", "cr3"))
        or state_values["rflags_if"] != 0
        or state_values["rflags_df"] != 0
    ):
        raise KernelTransferError("PKXFER1 kernel-observed transfer state diverges from PooleBoot")

    pbp1_values = {
        "profile": pbp1.group(1),
        "record_count": int(pbp1.group(2)),
        "artifact_count": int(pbp1.group(3)),
        "production_profile_valid": int(pbp1.group(4)),
    }
    if (
        pbp1_values["record_count"] != boot["pbp1"]["record_count"]
        or pbp1_values["artifact_count"] != boot["pbp1"]["artifact_count"]
        or pbp1_values["production_profile_valid"] != 0
    ):
        raise KernelTransferError("PKXFER1 kernel PBP1 profile diverges from PooleBoot")

    revalidation_values = {
        "contract_id": revalidation.group(1),
        "retained_file_count": int(revalidation.group(2)),
        "artifact_count": int(revalidation.group(3)),
        "parser_count": int(revalidation.group(4)),
        "manifest_bytes": int(revalidation.group(5)),
        "retained_file_bytes": int(revalidation.group(6)),
        "retained_set_sha256": revalidation.group(7),
        "policy_sha256": revalidation.group(8),
        "state_sha256": revalidation.group(9),
        "denial": revalidation.group(10),
        "authority_grants": int(revalidation.group(11)),
        "actions_authorized": int(revalidation.group(12)),
        "state_writes": int(revalidation.group(13)),
    }
    expected_retained_bytes = (
        boot["artifact_set"]["file_bytes"]
        + boot["manifest"]["byte_count"]
        + boot["trust_state"]["policy_bytes"]
        + boot["trust_state"]["state_bytes"]
    )
    if (
        tuple(
            revalidation_values[key]
            for key in ("retained_file_count", "artifact_count", "parser_count")
        )
        != (9, 6, 9)
        or revalidation_values["manifest_bytes"] != boot["manifest"]["byte_count"]
        or revalidation_values["retained_file_bytes"] != expected_retained_bytes
        or revalidation_values["retained_set_sha256"]
        != boot["inner_set"]["retained_set_sha256"]
        or revalidation_values["policy_sha256"] != boot["trust_state"]["policy_sha256"]
        or revalidation_values["state_sha256"] != boot["trust_state"]["state_sha256"]
        or revalidation_values["denial"] != boot["trust_state"]["denial"]
        or any(
            revalidation_values[key]
            for key in ("authority_grants", "actions_authorized", "state_writes")
        )
    ):
        raise KernelTransferError("PKXFER1 guest revalidation summary diverges from boot evidence")

    terminal_values = {
        "contract_id": terminal.group(1),
        "terminal": terminal.group(2),
        "entry_count": int(terminal.group(3)),
        "firmware_calls_after_exit": int(terminal.group(4)),
        "signature_verifications": int(terminal.group(5)),
        "authority_grants": int(terminal.group(6)),
        "actions_authorized": int(terminal.group(7)),
        "state_writes": int(terminal.group(8)),
    }
    if terminal_values["entry_count"] != 1 or any(
        terminal_values[key]
        for key in (
            "firmware_calls_after_exit",
            "signature_verifications",
            "authority_grants",
            "actions_authorized",
            "state_writes",
        )
    ):
        raise KernelTransferError("PKXFER1 terminal state created authority or observable effects")

    return {
        "marker_count": len(markers),
        "ordered_contract_match": True,
        "boot_prefix": boot,
        "transfer_arm": arm_values,
        "kernel_entry": entry_values,
        "kernel_state": state_values,
        "kernel_pbp1": pbp1_values,
        "kernel_revalidation": revalidation_values,
        "kernel_terminal": terminal_values,
    }


def validate_transcript_binding(
    marker_summary: dict[str, Any], transcript: dict[str, Any]
) -> dict[str, Any]:
    core = transcript.get("core", {})
    arm = marker_summary["transfer_arm"]
    kernel_pbp1 = marker_summary["kernel_pbp1"]
    if (
        transcript.get("boot_services_exited") is not True
        or transcript.get("exit_development_profile_validated") is not True
        or transcript.get("kernel_entry_profile_rejected") is not True
        or transcript.get("record_count") != kernel_pbp1["record_count"]
        or transcript.get("artifact_count") != kernel_pbp1["artifact_count"]
        or transcript.get("byte_count") != arm["handoff_bytes"]
        or int(str(core.get("kernel_entry_virtual", "0")), 16) != arm["entry"]
        or int(str(core.get("initial_stack_top_virtual", "0")), 16) != arm["stack_top"]
        or int(str(core.get("page_table_root_physical", "0")), 16) != arm["root"]
        or int(str(core.get("handoff_virtual_base", "0")), 16) != arm["handoff"]
        or core.get("handoff_byte_count") != arm["handoff_bytes"]
    ):
        raise KernelTransferError("PKXFER1 reconstructed PBP1 diverges from live transfer state")
    return {
        "exact_transfer_fields_bound": True,
        "production_kernel_entry_profile_rejected": True,
        "development_revalidation_profile_accepted": True,
    }


def canonical_retained_files(
    manifest_data: bytes,
    kernel_data: bytes,
    artifact_files: dict[str, bytes],
) -> tuple[bytes, ...]:
    trust_files, _ = native_kernel_load.canonical_trust_files(
        manifest_data, kernel_data, artifact_files
    )
    return (
        *(artifact_files[item[4]] for item in native_kernel_load.ARTIFACT_DEFINITIONS),
        manifest_data,
        trust_files[native_kernel_load.TRUST_POLICY_PATH],
        trust_files[native_kernel_load.TRUST_STATE_PATH],
    )


def validate_revalidation_binding(
    marker_summary: dict[str, Any],
    handoff_data: bytes,
    files: Sequence[bytes],
) -> dict[str, Any]:
    try:
        oracle = native_kernel_revalidation.revalidate_development(handoff_data, files)
    except native_kernel_revalidation.KernelRevalidationError as error:
        raise KernelTransferError(error.code) from error
    guest = marker_summary["kernel_revalidation"]
    compared = (
        "retained_file_count",
        "artifact_count",
        "parser_count",
        "manifest_bytes",
        "retained_file_bytes",
        "retained_set_sha256",
        "policy_sha256",
        "state_sha256",
        "denial",
        "authority_grants",
        "actions_authorized",
        "state_writes",
    )
    if any(guest[key] != oracle[key] for key in compared):
        raise KernelTransferError("PKXFER1 guest and independent host PKREVAL1 results diverge")
    return {**oracle, "guest_host_exact_match": True}
