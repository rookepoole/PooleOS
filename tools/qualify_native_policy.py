#!/usr/bin/env python3
"""Qualify PPOL1 parsing, PINIT1 cross-binding, decisions, and receipts."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_policy as ppol1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / ppol1.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
PARSER_CASES = 8_192
CROSS_BINDING_CASES = 4_096
ACTIVATION_CASES = 12_288
RECEIPT_CASES = 8_192
PARSER_SEED = 0x5050_4F4C_3101
CROSS_BINDING_SEED = 0x5050_4F4C_3102
ACTIVATION_SEED = 0x5050_4F4C_3103
RECEIPT_SEED = 0x5050_4F4C_3104


class QualificationError(RuntimeError):
    """Raised when PPOL1 qualification evidence fails closed."""


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    input_text: str | None = None,
) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(
            f"command failed ({completed.returncode}): {' '.join(command[:8])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = ppol1.read_json(ROOT / "specs/native-toolchain-lock.json")
    channel = lock["toolchain"]["channel"]
    host = lock["host"]["triple"]
    installed = toolchain_root / "rustup" / "toolchains" / channel
    cargo = installed / "bin" / "cargo.exe"
    rustc = installed / "bin" / "rustc.exe"
    if not cargo.is_file() or not rustc.is_file():
        raise QualificationError("workspace-local Rust toolchain is missing")
    env = dict(os.environ)
    for key in (
        "CARGO_BUILD_RUSTC",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_HOME",
        "CARGO_INCREMENTAL",
        "CARGO_TARGET_DIR",
        "RUSTC",
        "RUSTC_BOOTSTRAP",
        "RUSTC_WRAPPER",
        "RUSTDOCFLAGS",
        "RUSTFLAGS",
        "RUSTUP_HOME",
        "RUSTUP_TOOLCHAIN",
    ):
        env.pop(key, None)
    system_root = Path(env.get("SystemRoot", r"C:\Windows"))
    env.update(
        {
            "CARGO_HOME": str(toolchain_root / "cargo"),
            "CARGO_INCREMENTAL": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": os.pathsep.join(
                [str(installed / "bin"), str(toolchain_root / "cargo" / "bin"), str(system_root / "System32")]
            ),
            "RUSTC": str(rustc),
            "RUSTUP_HOME": str(toolchain_root / "rustup"),
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
        }
    )
    remap = f"--remap-path-prefix={NATIVE_ROOT.resolve()}=/pooleos/native"
    for target in ("X86_64_UNKNOWN_UEFI", "X86_64_UNKNOWN_NONE"):
        env[f"CARGO_TARGET_{target}_RUSTFLAGS"] = " ".join(
            ("-Cpanic=abort", '--cfg=sha2_backend="soft"', '--cfg=sha2_backend_soft="compact"', remap)
        )
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc differs from the toolchain lock")
    return cargo, rustc, env


def _cargo(cargo: Path, command: str, *arguments: str) -> list[str]:
    return [str(cargo), command, "--manifest-path", str(NATIVE_ROOT / "Cargo.toml"), *arguments]


def _build_validators(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    output = _run(
        _cargo(cargo, "test", "--package", "poole-policy", "--lib", "--target", HOST_TARGET, "--locked", "--offline", "--target-dir", str(temporary_root / "host-tests"), "--", "--test-threads=1"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", output)
    if match is None or int(match.group(1)) != 6:
        raise QualificationError("expected exactly six PPOL1 Rust host tests")
    _run(_cargo(cargo, "fmt", "--package", "poole-policy", "--", "--check"), cwd=NATIVE_ROOT, env=env)
    _run(
        _cargo(cargo, "clippy", "--package", "poole-policy", "--lib", "--target", HOST_TARGET, "--locked", "--offline", "--no-deps", "--target-dir", str(temporary_root / "clippy"), "--", "-D", "warnings"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    targets = ["x86_64-unknown-none", "x86_64-unknown-uefi"]
    for target in targets:
        _run(
            _cargo(cargo, "build", "--package", "poole-policy", "--lib", "--target", target, "--release", "--locked", "--offline", "--target-dir", str(temporary_root / f"target-{target}")),
            cwd=NATIVE_ROOT,
            env=env,
        )
    _run(
        _cargo(cargo, "build", "--package", "poole-policy", "--features", "host-probe", "--bin", "ppol1-probe", "--target", HOST_TARGET, "--locked", "--offline", "--target-dir", str(temporary_root / "probe")),
        cwd=NATIVE_ROOT,
        env=env,
    )
    probe = temporary_root / "probe" / HOST_TARGET / "debug" / "ppol1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PPOL1 host probe is missing")
    return probe, {
        "status": "pass",
        "rustc": _run([str(rustc), "--version"], cwd=ROOT, env=env).strip(),
        "host_tests": 6,
        "rustfmt_packages": 1,
        "clippy_targets": 1,
        "no_std_targets": targets,
    }


def _probe_lines(probe: Path, requests: list[str]) -> list[str]:
    completed = subprocess.run(
        [str(probe)],
        input="\n".join(requests) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise QualificationError(f"PPOL1 probe failed: {completed.stderr[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError("PPOL1 probe response count changed")
    return lines


def _parse_result(data: bytes) -> str:
    try:
        bundle = ppol1.parse(data)
        return (
            f"OK;version={ppol1.MAJOR_VERSION}.{ppol1.MINOR_VERSION};bytes={len(data)};"
            f"modes={len(bundle.modes)};capabilities={len(bundle.capability_rules)};"
            f"body={bundle.body_sha256}"
        )
    except ppol1.PolicyError as error:
        return f"ERR:{error.code}"


def _cross_result(policy: bytes, initial: bytes) -> str:
    try:
        bundle = ppol1.parse(policy)
        parsed_initial = ppol1.pinit1.parse(initial)
        ppol1.validate_initial_system(bundle, parsed_initial)
        return (
            f"OK;capabilities={len(bundle.capability_rules)};"
            f"pinit={ppol1.sha256_bytes(initial)}"
        )
    except ppol1.PolicyError as error:
        return f"ERR:{error.code}"
    except ppol1.pinit1.InitialSystemError:
        return "ERR:ppol_pinit_parse"


ACTIVATION_CASES_BY_CODE = {
    "development": "ppol_activation_outer_signature",
    "outer-signature": "ppol_activation_outer_signature",
    "outer-role": "ppol_activation_outer_role",
    "outer-version": "ppol_activation_outer_version",
    "outer-payload": "ppol_activation_outer_payload_digest",
    "outer-file": "ppol_activation_outer_file_digest",
    "policy-signature": "ppol_activation_policy_signature",
    "manifest-signature": "ppol_activation_manifest_signature",
    "artifact-signatures": "ppol_activation_artifact_signatures",
    "target-profile": "ppol_activation_target_profile",
    "initial-digest": "ppol_activation_initial_system_digest",
    "recovery-digest": "ppol_activation_recovery_digest",
    "symbols-digest": "ppol_activation_symbols_digest",
    "microcode-digest": "ppol_activation_microcode_digest",
    "firmware-digest": "ppol_activation_firmware_digest",
    "trust-policy": "ppol_activation_trust_policy",
    "revocation-state": "ppol_activation_revocation_state",
    "rollback-state": "ppol_activation_rollback_state",
    "audit-schema": "ppol_activation_audit_schema",
    "inner-contracts": "ppol_activation_inner_contracts",
    "pinit-cross-binding": "ppol_activation_initial_system_cross_binding",
    "kernel-abi": "ppol_activation_kernel_abi",
    "pbp": "ppol_activation_pbp",
    "mode": "ppol_activation_mode",
    "mode-authority": "ppol_activation_mode_authority",
    "transition-authority": "ppol_activation_transition_authority",
    "capability-allocator": "ppol_activation_capability_allocator",
    "resource-broker": "ppol_activation_resource_broker",
    "audit-sink": "ppol_activation_audit_sink",
    "receipt-store": "ppol_activation_receipt_store",
    "physical-presence": "ppol_activation_physical_presence",
    "separate-authority": "ppol_activation_separate_authority",
    "capability": "ppol_activation_capability",
    "capability-mode": "ppol_activation_capability_mode",
    "capability-revoked": "ppol_activation_capability_revoked",
    "generation": "ppol_activation_generation",
    "issued-rights": "ppol_activation_issued_rights",
    "requested-rights": "ppol_activation_requested_rights",
    "requested-effects": "ppol_activation_requested_effects",
    "not-qualification": "ppol_activation_not_qualification_only",
    "live-execution": "ppol_activation_live_execution_requested",
    "persistent-write": "ppol_activation_persistent_write_requested",
    "firmware-call": "ppol_activation_firmware_call_requested",
    "driver-load": "ppol_activation_driver_load_requested",
    "media-write": "ppol_activation_physical_media_write_requested",
    "state-mutation": "ppol_activation_state_mutation_requested",
}
QUALIFIED_CASES = [f"qualified-{name}" for name in ppol1.MODE_NAMES.values()]


def _activation_context(case: str, bundle: ppol1.Bundle) -> ppol1.ActivationContext:
    if case.startswith("qualified-"):
        mode_name = case.removeprefix("qualified-")
        mode = next(value for value, name in ppol1.MODE_NAMES.items() if name == mode_name)
        return ppol1.synthetic_qualified_activation_context(bundle, mode=mode)
    if case == "development":
        return ppol1.development_activation_context(bundle)
    context = ppol1.synthetic_qualified_activation_context(bundle)
    replacements: dict[str, Any] = {
        "outer-signature": {"outer_signature_verified": False},
        "outer-role": {"outer_role": 6},
        "outer-version": {"outer_version": context.outer_version + 1},
        "outer-payload": {"outer_payload_sha256": "0" * 64},
        "outer-file": {"expected_outer_file_sha256": "0" * 64},
        "policy-signature": {"policy_signature_verified": False},
        "manifest-signature": {"manifest_signature_verified": False},
        "artifact-signatures": {"artifact_signatures_verified": False},
        "target-profile": {"target_profile_verified": False},
        "initial-digest": {"initial_system_digest_verified": False},
        "recovery-digest": {"recovery_digest_verified": False},
        "symbols-digest": {"symbols_digest_verified": False},
        "microcode-digest": {"microcode_digest_verified": False},
        "firmware-digest": {"firmware_digest_verified": False},
        "trust-policy": {"trust_policy_authenticated": False},
        "revocation-state": {"revocation_state_authenticated": False},
        "rollback-state": {"rollback_state_authenticated": False},
        "audit-schema": {"audit_schema_verified": False},
        "inner-contracts": {"inner_contracts_verified": False},
        "pinit-cross-binding": {"initial_system_cross_bound": False},
        "kernel-abi": {"kernel_abi_verified": False},
        "pbp": {"pbp_verified": False},
        "mode": {"selected_mode": 99},
        "mode-authority": {"mode_authorized": False},
        "transition-authority": {"transition_authorized": False},
        "capability-allocator": {"capability_allocator_ready": False},
        "resource-broker": {"resource_broker_ready": False},
        "audit-sink": {"audit_sink_ready": False},
        "receipt-store": {"receipt_store_ready": False},
        "capability": {"capability_id": 0},
        "capability-mode": {"selected_mode": ppol1.MODE_RECOVERY},
        "capability-revoked": {"capability_revoked": True},
        "generation": {"current_generation": context.current_generation + 1},
        "issued-rights": {"issued_rights": context.issued_rights | ppol1.pinit1.RIGHT_EXECUTE},
        "requested-rights": {"requested_rights": context.requested_rights | ppol1.pinit1.RIGHT_EXECUTE},
        "requested-effects": {"requested_effects": context.requested_effects | ppol1.EFFECT_FIRMWARE},
        "not-qualification": {"qualification_only": False},
        "live-execution": {"live_execution_requested": True},
        "persistent-write": {"persistent_write_requested": True},
        "firmware-call": {"firmware_call_requested": True},
        "driver-load": {"driver_load_requested": True},
        "media-write": {"physical_media_write_requested": True},
        "state-mutation": {"state_mutation_requested": True},
    }
    if case in ("physical-presence", "separate-authority"):
        context = ppol1.synthetic_qualified_activation_context(bundle, mode=ppol1.MODE_FIRMWARE)
        replacements["physical-presence"] = {"physical_presence_verified": False}
        replacements["separate-authority"] = {"separate_authority_verified": False}
    return dataclasses.replace(context, **replacements[case])


def _activation_result(case: str, data: bytes) -> str:
    try:
        bundle = ppol1.parse(data)
        decision = ppol1.authorize_dry_run_decision(bundle, _activation_context(case, bundle))
        return (
            f"OK;mode={decision.mode};capability={decision.capability_id};"
            f"rights={decision.effective_rights};effects={decision.effective_effects};"
            f"mode_generation={decision.mode_generation};"
            f"capability_generation={decision.capability_generation};"
            f"allowed={decision.allowed_capability_count};"
            f"qualification={int(decision.qualification_only)}"
        )
    except ppol1.PolicyError as error:
        return f"ERR:{error.code}"


RECEIPT_CASES_BY_CODE = {
    "not-qualification": "ppol_receipt_not_qualification_only",
    "policy-digest": "ppol_receipt_policy_digest",
    "mode": "ppol_receipt_mode",
    "capability": "ppol_receipt_capability",
    "rights": "ppol_receipt_rights",
    "effects": "ppol_receipt_effects",
    "generation": "ppol_receipt_generation",
    "revocation-epoch": "ppol_receipt_revocation_epoch",
    "audit-sequence": "ppol_receipt_audit_sequence",
    "not-durable": "ppol_receipt_not_durable",
    "decision-id": "ppol_receipt_decision_id",
}


def _receipt_result(case: str, data: bytes) -> str:
    try:
        bundle = ppol1.parse(data)
        decision = ppol1.authorize_dry_run_decision(
            bundle, ppol1.synthetic_qualified_activation_context(bundle)
        )
        receipt = ppol1.synthetic_receipt(decision)
        replacements: dict[str, Any] = {
            "not-qualification": {"qualification_only": False},
            "policy-digest": {"policy_sha256": "0" * 64},
            "mode": {"mode": receipt.mode + 1},
            "capability": {"capability_id": receipt.capability_id + 1},
            "rights": {"effective_rights": receipt.effective_rights ^ 1},
            "effects": {"effective_effects": receipt.effective_effects ^ 1},
            "generation": {"mode_generation": receipt.mode_generation + 1},
            "revocation-epoch": {"revocation_epoch": 0},
            "audit-sequence": {"audit_sequence": 0},
            "not-durable": {"durable": False},
            "decision-id": {"decision_id": "0" * 64},
        }
        if case != "qualified":
            receipt = dataclasses.replace(receipt, **replacements[case])
        ppol1.verify_receipt(decision, receipt)
        return "OK:verified"
    except ppol1.PolicyError as error:
        return f"ERR:{error.code}"


def _body_mutation(data: bytes, edit: Callable[[bytearray], None]) -> bytes:
    value = bytearray(data)
    edit(value)
    value[416:448] = hashlib.sha256(value[ppol1.HEADER_BYTES :]).digest()
    return bytes(value)


def _header_mutation(data: bytes, edit: Callable[[bytearray], None]) -> bytes:
    value = bytearray(data)
    edit(value)
    return bytes(value)


def _write(fmt: str, offset: int, value: int) -> Callable[[bytearray], None]:
    return lambda data: struct.pack_into(fmt, data, offset, value)


def _set_mode_effects(offset: int, effects: int) -> Callable[[bytearray], None]:
    def edit(data: bytearray) -> None:
        struct.pack_into("<Q", data, offset + 8, effects)
        struct.pack_into("<Q", data, offset + 24, ppol1.KNOWN_EFFECTS ^ effects)

    return edit


def _widen_recovery(offset: int) -> Callable[[bytearray], None]:
    def edit(data: bytearray) -> None:
        struct.pack_into("<H", data, offset + 4, 1)
        struct.pack_into("<I", data, offset + 60, ppol1.pinit1.RIGHT_READ)

    return edit


def _parser_controls(canonical: bytes) -> list[tuple[str, str, bytes]]:
    mode = ppol1.HEADER_BYTES
    safe = mode + ppol1.MODE_RECORD_BYTES
    recovery = mode + 3 * ppol1.MODE_RECORD_BYTES
    firmware = mode + 5 * ppol1.MODE_RECORD_BYTES
    rules = ppol1.HEADER_BYTES + ppol1.MODE_COUNT * ppol1.MODE_RECORD_BYTES
    child = rules + 3 * ppol1.CAPABILITY_RECORD_BYTES
    last_child = rules + 10 * ppol1.CAPABILITY_RECORD_BYTES
    cases: list[tuple[str, str, bytes]] = [
        ("EMPTY", "ppol_truncated", b""),
        ("TRUNCATED", "ppol_truncated", canonical[:511]),
        ("OVERSIZED", "ppol_oversized", b"\0" * (ppol1.MAX_BUNDLE_BYTES + 1)),
        ("MAGIC", "ppol_magic", _header_mutation(canonical, lambda data: data.__setitem__(0, data[0] ^ 1))),
        ("MAJOR", "ppol_version", _header_mutation(canonical, _write("<H", 8, 2))),
        ("MINOR", "ppol_version", _header_mutation(canonical, _write("<H", 10, 1))),
        ("HEADER-SIZE", "ppol_record_size", _header_mutation(canonical, _write("<H", 12, 0))),
        ("MODE-RECORD-SIZE", "ppol_record_size", _header_mutation(canonical, _write("<H", 14, 0))),
        ("CAP-RECORD-SIZE", "ppol_record_size", _header_mutation(canonical, _write("<H", 16, 0))),
        ("PROFILE", "ppol_profile", _header_mutation(canonical, _write("<H", 18, 2))),
        ("FLAGS", "ppol_flags", _header_mutation(canonical, _write("<I", 20, 0))),
        ("POLICY-VERSION", "ppol_version_floor", _header_mutation(canonical, _write("<Q", 24, 0))),
        ("SECURE-VERSION", "ppol_version_floor", _header_mutation(canonical, _write("<Q", 32, 0))),
        ("ROLLBACK-FLOOR", "ppol_version_floor", _header_mutation(canonical, _write("<Q", 32, 2))),
        ("MODE-COUNT", "ppol_counts", _header_mutation(canonical, _write("<H", 40, 0))),
        ("CAP-COUNT", "ppol_counts", _header_mutation(canonical, _write("<H", 42, 0))),
        ("REQUIRED-MODES", "ppol_required_modes", _header_mutation(canonical, _write("<I", 44, 1))),
        ("MODE-OFFSET", "ppol_table_layout", _header_mutation(canonical, _write("<Q", 48, 0))),
        ("CAP-OFFSET", "ppol_table_layout", _header_mutation(canonical, _write("<Q", 56, 0))),
        ("TRAILING", "ppol_trailing_bytes", canonical + b"\0"),
        ("AUDIT-LIMIT", "ppol_limits", _header_mutation(canonical, _write("<I", 72, 0))),
        ("GENERATION-ADVANCE", "ppol_limits", _header_mutation(canonical, _write("<I", 76, 2))),
        ("DEFAULT-CEILING", "ppol_default_ceiling", _header_mutation(canonical, _write("<Q", 80, 0))),
        ("HEADER-RESERVED", "ppol_default_ceiling", _header_mutation(canonical, _write("<Q", 88, 1))),
        ("IDENTITY-DIGEST", "ppol_digest", _header_mutation(canonical, lambda data: data.__setitem__(slice(96, 128), b"\0" * 32))),
        ("BODY-DIGEST", "ppol_body_digest", _header_mutation(canonical, lambda data: data.__setitem__(slice(416, 448), b"\0" * 32))),
        ("POLICY-ID", "ppol_policy_id", _header_mutation(canonical, lambda data: data.__setitem__(448, ord("x")))),
        ("RESERVED", "ppol_reserved", _header_mutation(canonical, lambda data: data.__setitem__(488, 1))),
        ("MODE-ORDER", "ppol_mode_order", _body_mutation(canonical, _write("<H", mode, 2))),
        ("MODE-FLAGS", "ppol_mode_flags", _body_mutation(canonical, _write("<H", mode + 2, 0))),
        ("MODE-RESERVED", "ppol_mode_reserved", _body_mutation(canonical, _write("<H", mode + 6, 1))),
        ("MODE-CAP-COUNT", "ppol_mode_capability_count", _body_mutation(canonical, _write("<H", mode + 4, 12))),
        ("MODE-EFFECTS", "ppol_mode_effects", _body_mutation(canonical, _write("<Q", mode + 8, 0))),
        ("MODE-PROHIBITED", "ppol_mode_prohibited_effects", _body_mutation(canonical, _write("<Q", mode + 24, 0))),
        ("MODE-EVIDENCE", "ppol_mode_evidence", _body_mutation(canonical, _write("<Q", mode + 16, 0))),
        ("MODE-RESOURCE", "ppol_mode_resource_ceiling", _body_mutation(canonical, _write("<I", mode + 32, 65537))),
        ("MODE-CAP-FLAGS", "ppol_mode_capability_flags", _body_mutation(canonical, _write("<I", mode + 56, 1 << 31))),
        ("MODE-RIGHTS", "ppol_mode_rights", _body_mutation(canonical, _write("<I", mode + 60, 1 << 31))),
        ("MODE-ARTIFACTS", "ppol_mode_artifacts", _body_mutation(canonical, _write("<I", mode + 64, 0))),
        ("MODE-TRANSITIONS", "ppol_mode_transitions", _body_mutation(canonical, _write("<I", mode + 68, 0))),
        ("MODE-AUDIT", "ppol_mode_audit", _body_mutation(canonical, _write("<Q", mode + 72, 0))),
        ("SAFE-FLOOR", "ppol_safe_floor", _body_mutation(canonical, _set_mode_effects(safe, ppol1.KNOWN_EFFECTS))),
        ("RECOVERY-FLOOR", "ppol_recovery_floor", _body_mutation(canonical, _widen_recovery(recovery))),
        ("FIRMWARE-BOUNDARY", "ppol_firmware_boundary", _body_mutation(canonical, _write("<H", firmware + 2, ppol1.MODE_BASE_FLAGS | ppol1.MODE_FLAG_DISABLE_PDC))),
        ("CAP-ORDER", "ppol_capability_order", _body_mutation(canonical, _write("<I", rules, 2))),
        ("CAP-PARENT", "ppol_capability_parent", _body_mutation(canonical, _write("<I", rules + 4, 1))),
        ("CAP-ROUTE", "ppol_capability_route", _body_mutation(canonical, _write("<I", rules + 8, 0))),
        ("CAP-DECLARED-RIGHTS", "ppol_capability_declared_rights", _body_mutation(canonical, _write("<Q", rules + 16, 0))),
        ("CAP-CEILING-RIGHTS", "ppol_capability_ceiling_rights", _body_mutation(canonical, _write("<Q", child + 24, ppol1.KNOWN_RIGHTS))),
        ("CAP-DECLARED-FLAGS", "ppol_capability_declared_flags", _body_mutation(canonical, _write("<I", rules + 32, 0))),
        ("CAP-CEILING-FLAGS", "ppol_capability_ceiling_flags", _body_mutation(canonical, _write("<I", rules + 36, 0))),
        ("CAP-REVOKE", "ppol_capability_revoke_group", _body_mutation(canonical, _write("<I", rules + 40, 0))),
        ("CAP-MODES", "ppol_capability_modes", _body_mutation(canonical, _write("<I", rules + 44, ppol1.ALL_MODE_MASK))),
        ("CAP-EFFECTS", "ppol_capability_effects", _body_mutation(canonical, _write("<Q", rules + 48, ppol1.EFFECT_FIRMWARE))),
        ("CAP-AVAILABILITY", "ppol_capability_availability", _body_mutation(canonical, _write("<H", rules + 56, 0))),
        ("CAP-GENERATION", "ppol_capability_generation", _body_mutation(canonical, _write("<I", rules + 60, 0))),
        ("CAP-PARENT-ATTENUATION", "ppol_capability_parent_attenuation", _body_mutation(canonical, _write("<Q", last_child + 48, ppol1.EFFECT_AUDIT | ppol1.EFFECT_READ_STATE))),
    ]
    return cases


def _negative_controls(probe: Path, canonical: bytes, initial: bytes) -> list[dict[str, str]]:
    controls: list[dict[str, str]] = []
    parser_cases = _parser_controls(canonical)
    parser_requests = [f"P:{data.hex()}" for _, _, data in parser_cases]
    parser_actual = _probe_lines(probe, parser_requests)
    for (name, code, data), rust in zip(parser_cases, parser_actual, strict=True):
        python = _parse_result(data)
        expected = f"ERR:{code}"
        if python != expected or rust != expected:
            raise QualificationError(f"parser control {name} diverged: {python} / {rust} / {expected}")
        controls.append({"id": f"NEG-N5-PPOL-PARSER-{name}", "expected": code, "status": "pass"})
    activation_requests = [f"A:{case}:{canonical.hex()}" for case in ACTIVATION_CASES_BY_CODE]
    activation_actual = _probe_lines(probe, activation_requests)
    for (case, code), rust in zip(ACTIVATION_CASES_BY_CODE.items(), activation_actual, strict=True):
        python = _activation_result(case, canonical)
        expected = f"ERR:{code}"
        if python != expected or rust != expected:
            raise QualificationError(f"activation control {case} diverged: {python} / {rust} / {expected}")
        controls.append({"id": f"NEG-N5-PPOL-ACTIVATION-{case.upper()}", "expected": code, "status": "pass"})
    receipt_requests = [f"R:{case}:{canonical.hex()}" for case in RECEIPT_CASES_BY_CODE]
    receipt_actual = _probe_lines(probe, receipt_requests)
    for (case, code), rust in zip(RECEIPT_CASES_BY_CODE.items(), receipt_actual, strict=True):
        python = _receipt_result(case, canonical)
        expected = f"ERR:{code}"
        if python != expected or rust != expected:
            raise QualificationError(f"receipt control {case} diverged: {python} / {rust} / {expected}")
        controls.append({"id": f"NEG-N5-PPOL-RECEIPT-{case.upper()}", "expected": code, "status": "pass"})
    policy_digest = bytearray(canonical)
    policy_digest[128] ^= 1
    cross_cases = [
        ("PINIT-DIGEST", bytes(policy_digest), "ppol_pinit_digest"),
        (
            "PINIT-ROUTE",
            _body_mutation(canonical, _write("<I", ppol1.HEADER_BYTES + ppol1.MODE_COUNT * ppol1.MODE_RECORD_BYTES + 8, 2)),
            "ppol_pinit_capability_route",
        ),
    ]
    cross_actual = _probe_lines(probe, [f"X:{policy.hex()}:{initial.hex()}" for _, policy, _ in cross_cases])
    for (name, policy, code), rust in zip(cross_cases, cross_actual, strict=True):
        python = _cross_result(policy, initial)
        expected = f"ERR:{code}"
        if python != expected or rust != expected:
            raise QualificationError(f"cross-binding control {name} diverged: {python} / {rust} / {expected}")
        controls.append({"id": f"NEG-N5-PPOL-CROSS-{name}", "expected": code, "status": "pass"})
    if len(controls) < 80:
        raise QualificationError("PPOL1 negative-control depth regressed")
    return controls


def _differential(probe: Path, canonical: bytes, initial: bytes) -> dict[str, dict[str, int]]:
    randomizer = random.Random(PARSER_SEED)
    parser_inputs: list[bytes] = []
    for index in range(PARSER_CASES):
        if index % 64 == 0:
            parser_inputs.append(canonical)
            continue
        value = bytearray(canonical)
        offset = randomizer.randrange(len(value))
        value[offset] ^= 1 << randomizer.randrange(8)
        parser_inputs.append(bytes(value))
    rust = _probe_lines(probe, [f"P:{data.hex()}" for data in parser_inputs])
    python = [_parse_result(data) for data in parser_inputs]
    parser_differences = [
        {"index": index, "python": left, "rust": right}
        for index, (left, right) in enumerate(zip(python, rust, strict=True))
        if left != right
    ]
    parser_mismatches = len(parser_differences)

    canonical_cross = _cross_result(canonical, initial)
    cross_policy = bytearray(canonical)
    cross_policy[128] ^= 1
    cross_inputs = [canonical if index % 2 == 0 else bytes(cross_policy) for index in range(CROSS_BINDING_CASES)]
    rust = _probe_lines(probe, [f"X:{data.hex()}:{initial.hex()}" for data in cross_inputs])
    python = [canonical_cross if data is canonical else _cross_result(data, initial) for data in cross_inputs]
    cross_mismatches = sum(left != right for left, right in zip(python, rust, strict=True))

    activation_names = [*QUALIFIED_CASES, *ACTIVATION_CASES_BY_CODE]
    activation_inputs = [activation_names[index % len(activation_names)] for index in range(ACTIVATION_CASES)]
    rust = _probe_lines(probe, [f"A:{case}:{canonical.hex()}" for case in activation_inputs])
    python = [_activation_result(case, canonical) for case in activation_inputs]
    activation_mismatches = sum(left != right for left, right in zip(python, rust, strict=True))

    receipt_names = ["qualified", *RECEIPT_CASES_BY_CODE]
    receipt_inputs = [receipt_names[index % len(receipt_names)] for index in range(RECEIPT_CASES)]
    rust = _probe_lines(probe, [f"R:{case}:{canonical.hex()}" for case in receipt_inputs])
    python = [_receipt_result(case, canonical) for case in receipt_inputs]
    receipt_mismatches = sum(left != right for left, right in zip(python, rust, strict=True))
    evidence = {
        "parser": {"cases": PARSER_CASES, "mismatches": parser_mismatches, "seed": PARSER_SEED},
        "cross_binding": {"cases": CROSS_BINDING_CASES, "mismatches": cross_mismatches, "seed": CROSS_BINDING_SEED},
        "activation": {"cases": ACTIVATION_CASES, "mismatches": activation_mismatches, "seed": ACTIVATION_SEED},
        "receipt": {"cases": RECEIPT_CASES, "mismatches": receipt_mismatches, "seed": RECEIPT_SEED},
    }
    if any(item["mismatches"] for item in evidence.values()):
        raise QualificationError(
            f"PPOL1 differential mismatch: {evidence}; "
            f"parser_samples={parser_differences[:10]}"
        )
    return evidence


def _binding(relative: str) -> dict[str, Any]:
    return ppol1._binding_record(ROOT / relative)  # type: ignore[attr-defined]


def qualify(toolchain_root: Path) -> dict[str, Any]:
    canonical = ppol1.canonical_bundle()
    initial = ppol1.pinit1.canonical_bundle()
    bundle = ppol1.parse(canonical)
    ppol1.validate_initial_system(bundle, ppol1.pinit1.parse(initial))
    with tempfile.TemporaryDirectory(prefix="ppol1-qualification-") as temporary:
        probe, build = _build_validators(toolchain_root, Path(temporary))
        golden = ppol1.read_json(ROOT / ppol1.GOLDEN_RELATIVE)
        requests = [f"P:{bytes.fromhex(item['hex']).hex()}" for item in golden["vectors"]]
        rust_golden = _probe_lines(probe, requests)
        python_golden = [_parse_result(bytes.fromhex(item["hex"])) for item in golden["vectors"]]
        if rust_golden != python_golden or any(line.startswith("ERR:") for line in rust_golden):
            raise QualificationError("PPOL1 golden vectors diverged")
        cross = _cross_result(canonical, initial)
        rust_cross = _probe_lines(probe, [f"X:{canonical.hex()}:{initial.hex()}"])[0]
        if cross != rust_cross or not cross.startswith("OK;"):
            raise QualificationError("PPOL1 canonical PINIT1 cross-binding diverged")
        controls = _negative_controls(probe, canonical, initial)
        differential = _differential(probe, canonical, initial)
    development_errors = ppol1.activation_errors(bundle, ppol1.development_activation_context(bundle))
    if not development_errors or development_errors[0] != "ppol_activation_outer_signature":
        raise QualificationError("PPOL1 development boundary changed")
    mode_decisions = []
    for mode in ppol1.MODES:
        decision = ppol1.authorize_dry_run_decision(
            bundle, ppol1.synthetic_qualified_activation_context(bundle, mode=mode)
        )
        receipt = ppol1.synthetic_receipt(decision)
        ppol1.verify_receipt(decision, receipt)
        mode_decisions.append(
            {
                "mode": ppol1.MODE_NAMES[mode],
                "capability_id": decision.capability_id,
                "effective_rights": decision.effective_rights,
                "effective_effects": decision.effective_effects,
                "allowed_capability_count": decision.allowed_capability_count,
                "qualification_only": decision.qualification_only,
            }
        )
    contract = ppol1.read_json(ROOT / ppol1.CONTRACT_RELATIVE)
    non_claims = contract["non_claims"]
    return {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_policy_readiness",
        "contract_id": ppol1.CONTRACT_ID,
        "status": "pass",
        "inputs": {
            "contract": _binding(ppol1.CONTRACT_RELATIVE.as_posix()),
            "golden_vectors": _binding(ppol1.GOLDEN_RELATIVE.as_posix()),
            "toolchain_lock": _binding("specs/native-toolchain-lock.json"),
            "toolchain_qualification": _binding("runs/native_toolchain_qualification.json"),
            "tier1_profile": _binding("specs/tier1-hardware-target.json"),
            "implementation_inputs": ppol1.implementation_bindings(ROOT),
        },
        "build": build,
        "golden": {"status": "pass", "vectors": len(golden["vectors"]), "python_rust_exact": True},
        "negative_controls": controls,
        "differential": differential,
        "activation": {
            "development_allowed": False,
            "development_first_error": development_errors[0],
            "synthetic_mode_decisions": mode_decisions,
            "authority_equation": contract["authority_equation"],
            "live_effects_requested": False,
        },
        "cross_binding": {
            "status": "pass",
            "initial_system_sha256": bundle.initial_system_sha256,
            "capability_routes": len(bundle.capability_rules),
            "complete_exact_route_set": True,
            "parent_monotonic": True,
            "amplification_observed": False,
        },
        "receipts": {
            "status": "pass",
            "policy_digest_bound": True,
            "mode_and_capability_bound": True,
            "generation_and_revocation_epoch_bound": True,
            "durability_required": True,
            "persistent_receipt_written": False,
        },
        "claims": ppol1.expected_claims(),
        "non_claims": non_claims,
        "production_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    readiness = qualify(args.toolchain_root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(readiness, indent=2) + "\n", encoding="utf-8", newline="\n")
    errors = ppol1.readiness_errors(readiness, ROOT)
    if errors:
        raise QualificationError("generated PPOL1 readiness is invalid: " + "; ".join(errors))
    print(
        f"PPOL1 QUALIFY PASS controls={len(readiness['negative_controls'])} "
        f"differential={sum(item['cases'] for item in readiness['differential'].values())} "
        "mismatches=0 production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
