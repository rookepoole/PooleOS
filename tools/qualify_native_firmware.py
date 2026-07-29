#!/usr/bin/env python3
"""Qualify PFWM1 parsing, dry-run gating, and post-reset verification."""

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

from runtime import native_firmware as pfwm1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / pfwm1.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
PARSER_DIFFERENTIAL_CASES = 16_384
ACTIVATION_DIFFERENTIAL_CASES = 8_192
POST_RESET_DIFFERENTIAL_CASES = 8_192
PARSER_SEED = 0x5046_574D_3101
ACTIVATION_SEED = 0x5046_574D_3102
POST_RESET_SEED = 0x5046_574D_3103


class QualificationError(RuntimeError):
    """Raised when PFWM1 qualification fails closed."""


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
    lock = pfwm1.read_json(ROOT / "specs/native-toolchain-lock.json")
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
                [
                    str(installed / "bin"),
                    str(toolchain_root / "cargo" / "bin"),
                    str(system_root / "System32"),
                ]
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
            (
                "-Cpanic=abort",
                '--cfg=sha2_backend="soft"',
                '--cfg=sha2_backend_soft="compact"',
                remap,
            )
        )
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc differs from the toolchain lock")
    return cargo, rustc, env


def _cargo(cargo: Path, command: str, *arguments: str) -> list[str]:
    return [
        str(cargo),
        command,
        "--manifest-path",
        str(NATIVE_ROOT / "Cargo.toml"),
        *arguments,
    ]


def _build_validators(
    toolchain_root: Path, temporary_root: Path
) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    test_output = _run(
        _cargo(
            cargo,
            "test",
            "--package",
            "poole-firmware",
            "--lib",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "host-tests"),
            "--",
            "--test-threads=1",
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test_output)
    if match is None or int(match.group(1)) != 5:
        raise QualificationError("expected exactly five PFWM1 Rust host tests")
    _run(
        _cargo(cargo, "fmt", "--package", "poole-firmware", "--", "--check"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        _cargo(
            cargo,
            "clippy",
            "--package",
            "poole-firmware",
            "--lib",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "clippy"),
            "--",
            "-D",
            "warnings",
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    targets = ["x86_64-unknown-none", "x86_64-unknown-uefi"]
    for target in targets:
        _run(
            _cargo(
                cargo,
                "build",
                "--package",
                "poole-firmware",
                "--lib",
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(temporary_root / f"target-{target}"),
            ),
            cwd=NATIVE_ROOT,
            env=env,
        )
    _run(
        _cargo(
            cargo,
            "build",
            "--package",
            "poole-firmware",
            "--features",
            "host-probe",
            "--bin",
            "pfwm1-probe",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "probe"),
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    probe = temporary_root / "probe" / HOST_TARGET / "debug" / "pfwm1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PFWM1 host probe is missing")
    return probe, {
        "status": "pass",
        "rustc": _run([str(rustc), "--version"], cwd=ROOT, env=env).strip(),
        "host_tests": 5,
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
        raise QualificationError(f"PFWM1 probe failed: {completed.stderr[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError("PFWM1 probe response count changed")
    return lines


def _parse_result(data: bytes) -> str:
    try:
        bundle = pfwm1.parse(data)
    except pfwm1.FirmwareError as error:
        return f"ERR:{error.code}"
    payload = sum(item.external_payload_bytes for item in bundle.components)
    return (
        f"OK;version={pfwm1.MAJOR_VERSION}.{pfwm1.MINOR_VERSION};bytes={len(data)};"
        f"components={len(bundle.components)};dependencies={len(bundle.dependencies)};"
        f"payload={payload};body={bundle.body_sha256}"
    )


ACTIVATION_MODES = (
    ("development", "pfwm_activation_outer_signature"),
    ("outer-signature", "pfwm_activation_outer_signature"),
    ("outer-role", "pfwm_activation_outer_role"),
    ("outer-version", "pfwm_activation_outer_version"),
    ("outer-payload", "pfwm_activation_outer_payload_digest"),
    ("outer-file", "pfwm_activation_outer_file_digest"),
    ("manifest-signature", "pfwm_activation_manifest_signature"),
    ("package-signature", "pfwm_activation_package_signature"),
    ("vendor-signature", "pfwm_activation_vendor_signature"),
    ("target-profile", "pfwm_activation_target_profile"),
    ("hardware-inventory", "pfwm_activation_hardware_inventory"),
    ("device-identity", "pfwm_activation_device_identity"),
    ("current-versions", "pfwm_activation_current_versions"),
    ("transport-support", "pfwm_activation_transport_support"),
    ("firmware-services", "pfwm_activation_firmware_services"),
    ("updater-plugins", "pfwm_activation_updater_plugins"),
    ("plugin-authority", "pfwm_activation_plugin_authority"),
    ("external-payloads", "pfwm_activation_external_payloads"),
    ("payload-digests", "pfwm_activation_payload_digests"),
    ("license-policy", "pfwm_activation_license_policy"),
    ("redistribution", "pfwm_activation_redistribution"),
    ("revocation-state", "pfwm_activation_revocation_state"),
    ("component-revoked", "pfwm_activation_component_revoked"),
    ("anti-rollback", "pfwm_activation_anti_rollback"),
    ("recovery", "pfwm_activation_recovery"),
    ("recovery-backup", "pfwm_activation_recovery_backup"),
    ("staging", "pfwm_activation_staging"),
    ("staging-capacity", "pfwm_activation_staging_capacity"),
    ("power", "pfwm_activation_power"),
    ("ac-power", "pfwm_activation_ac_power"),
    ("battery", "pfwm_activation_battery"),
    ("transaction-journal", "pfwm_activation_transaction_journal"),
    ("quiescence", "pfwm_activation_quiescence"),
    ("storage-guard", "pfwm_activation_storage_guard"),
    ("suspend-shutdown", "pfwm_activation_suspend_shutdown_guard"),
    ("reset-authority", "pfwm_activation_reset_authority"),
    ("reboot-authority", "pfwm_activation_reboot_authority"),
    ("user-confirmation", "pfwm_activation_user_confirmation"),
    ("physical-presence", "pfwm_activation_physical_presence"),
    ("post-reset-verifier", "pfwm_activation_post_reset_verifier"),
    ("receipt-storage", "pfwm_activation_receipt_storage"),
    ("firmware-authority", "pfwm_activation_firmware_change_authority"),
    ("not-qualification", "pfwm_activation_not_qualification_only"),
    ("live-call", "pfwm_activation_live_firmware_call_requested"),
    ("driver-load", "pfwm_activation_driver_load_requested"),
    ("media-write", "pfwm_activation_physical_media_write_requested"),
    ("firmware-mutation", "pfwm_activation_firmware_mutation_requested"),
)

ACTIVATION_FIELD_MODES: dict[str, tuple[str, Any]] = {
    "outer-signature": ("outer_signature_verified", False),
    "outer-role": ("outer_role", 5),
    "outer-version": ("outer_version", 2),
    "manifest-signature": ("manifest_signature_verified", False),
    "package-signature": ("package_signature_verified", False),
    "vendor-signature": ("vendor_signatures_verified", False),
    "target-profile": ("target_profile_verified", False),
    "hardware-inventory": ("hardware_inventory_observed", False),
    "device-identity": ("exact_device_identities_verified", False),
    "transport-support": ("transport_support_verified", False),
    "firmware-services": ("firmware_service_inventory_verified", False),
    "updater-plugins": ("updater_plugins_verified", False),
    "plugin-authority": ("plugin_authority_granted", False),
    "external-payloads": ("external_payloads_present", False),
    "payload-digests": ("payload_digests_verified", False),
    "license-policy": ("license_policy_satisfied", False),
    "redistribution": ("redistribution_authorized", False),
    "revocation-state": ("revocation_state_authenticated", False),
    "component-revoked": ("no_components_revoked", False),
    "anti-rollback": ("anti_rollback_state_authenticated", False),
    "recovery": ("recovery_ready", False),
    "recovery-backup": ("recovery_backup_verified", False),
    "staging": ("protected_staging_ready", False),
    "staging-capacity": ("staging_capacity_bytes", 0),
    "power": ("stable_power", False),
    "ac-power": ("ac_power_present", False),
    "battery": ("battery_percent", 0),
    "transaction-journal": ("transaction_journal_ready", False),
    "quiescence": ("quiescence_ready", False),
    "storage-guard": ("storage_guard_ready", False),
    "suspend-shutdown": ("suspend_shutdown_guard_ready", False),
    "reset-authority": ("reset_authorized", False),
    "reboot-authority": ("reboot_authorized", False),
    "user-confirmation": ("user_confirmed", False),
    "physical-presence": ("physical_presence_verified", False),
    "post-reset-verifier": ("post_reset_verifier_ready", False),
    "receipt-storage": ("receipt_storage_ready", False),
    "firmware-authority": ("firmware_change_authorized", False),
    "not-qualification": ("qualification_only", False),
    "live-call": ("live_firmware_call_requested", True),
    "driver-load": ("driver_load_requested", True),
    "media-write": ("physical_media_write_requested", True),
    "firmware-mutation": ("firmware_mutation_requested", True),
}


def _activation_result(mode: str, data: bytes) -> str:
    try:
        bundle = pfwm1.parse(data)
        if mode == "development":
            context = pfwm1.development_activation_context(bundle)
        else:
            context = pfwm1.synthetic_qualified_activation_context(bundle)
            if mode == "outer-payload":
                context = dataclasses.replace(context, outer_payload_sha256="00" * 32)
            elif mode == "outer-file":
                context = dataclasses.replace(context, expected_outer_file_sha256="00" * 32)
            elif mode == "current-versions":
                observed = list(context.observed_versions)
                observed[0] = dataclasses.replace(observed[0], version=observed[0].version ^ 1)
                context = dataclasses.replace(context, observed_versions=tuple(observed))
            elif mode in ACTIVATION_FIELD_MODES:
                field, value = ACTIVATION_FIELD_MODES[mode]
                context = dataclasses.replace(context, **{field: value})
            elif mode != "qualified":
                raise QualificationError(f"unknown activation mode {mode}")
        plan = pfwm1.authorize_dry_run_plan(bundle, context)
    except pfwm1.FirmwareError as error:
        return f"ERR:{error.code}"
    return (
        f"OK;components={len(plan.component_order)};parallel={plan.maximum_parallel_components};"
        f"payload={plan.external_payload_bytes};reset={int(plan.reset_required)};"
        f"qualification={int(plan.qualification_only)}"
    )


POST_RESET_MODES = (
    ("not-qualification", "pfwm_post_reset_not_qualification_only"),
    ("count", "pfwm_post_reset_record_count"),
    ("order", "pfwm_post_reset_record_order"),
    ("resource", "pfwm_post_reset_resource_identity"),
    ("hardware-instance", "pfwm_post_reset_hardware_instance"),
    ("version", "pfwm_post_reset_version"),
    ("last-version", "pfwm_post_reset_last_attempt_version"),
    ("last-status", "pfwm_post_reset_last_attempt_status"),
    ("reenumeration", "pfwm_post_reset_reenumeration"),
    ("self-test", "pfwm_post_reset_self_test"),
    ("recovery", "pfwm_post_reset_recovery"),
    ("receipt", "pfwm_post_reset_receipt"),
    ("boot-loop", "pfwm_post_reset_boot_loop_guard"),
    ("state-commit", "pfwm_post_reset_state_commit"),
    ("driver-rebind", "pfwm_post_reset_driver_rebind"),
)

POST_RESET_FIELDS = {
    "order": ("component_id", 0),
    "resource": ("resource_guid", b"\0" * 16),
    "hardware-instance": ("hardware_instance", 0),
    "version": ("observed_version", 0),
    "last-version": ("last_attempt_version", 0),
    "last-status": ("last_attempt_status", 1),
    "reenumeration": ("reenumerated", False),
    "self-test": ("self_test_passed", False),
    "recovery": ("recovery_intact", False),
    "receipt": ("receipt_persisted", False),
    "boot-loop": ("boot_loop_prevented", False),
    "state-commit": ("state_committed", False),
    "driver-rebind": ("driver_rebound_after_validation", False),
}


def _post_reset_result(mode: str, data: bytes) -> str:
    try:
        bundle = pfwm1.parse(data)
        records = list(pfwm1.synthetic_post_reset_records(bundle))
        qualification_only = mode != "not-qualification"
        if mode == "count":
            records.pop()
        elif mode in POST_RESET_FIELDS:
            field, value = POST_RESET_FIELDS[mode]
            records[0] = dataclasses.replace(records[0], **{field: value})
        elif mode not in ("qualified", "not-qualification"):
            raise QualificationError(f"unknown post-reset mode {mode}")
        pfwm1.verify_post_reset(bundle, records, qualification_only=qualification_only)
    except pfwm1.FirmwareError as error:
        return f"ERR:{error.code}"
    return "OK:verified"


def _repair_body(data: bytearray) -> None:
    data[376:408] = hashlib.sha256(data[pfwm1.HEADER_BYTES :]).digest()


def _mutate(
    original: bytes,
    change: Callable[[bytearray], None],
    *,
    repair_body: bool = False,
) -> bytes:
    data = bytearray(original)
    change(data)
    if repair_body:
        _repair_body(data)
    return bytes(data)


def _parser_controls() -> list[tuple[str, bytes, str]]:
    data = pfwm1.canonical_bundle()
    c0 = pfwm1.HEADER_BYTES
    c1 = c0 + pfwm1.COMPONENT_RECORD_BYTES
    c2 = c1 + pfwm1.COMPONENT_RECORD_BYTES
    dep = c2 + pfwm1.COMPONENT_RECORD_BYTES

    def pack(fmt: str, offset: int, value: int) -> Callable[[bytearray], None]:
        return lambda value_bytes: struct.pack_into(fmt, value_bytes, offset, value)

    controls = [
        ("TRUNCATED", data[:511], "pfwm_truncated"),
        ("OVERSIZED", data + b"\0" * (pfwm1.MAX_MANIFEST_BYTES + 1), "pfwm_oversized"),
        ("MAGIC", _mutate(data, lambda x: x.__setitem__(0, x[0] ^ 1)), "pfwm_magic"),
        ("VERSION", _mutate(data, pack("<H", 8, 2)), "pfwm_version"),
        ("HEADER-SIZE", _mutate(data, pack("<H", 12, 256)), "pfwm_header_size"),
        ("RECORD-SIZE", _mutate(data, pack("<H", 14, 128)), "pfwm_record_size"),
        ("PROFILE", _mutate(data, pack("<H", 18, 2)), "pfwm_profile"),
        ("FLAGS", _mutate(data, pack("<I", 20, 0)), "pfwm_flags"),
        ("MANIFEST-VERSION", _mutate(data, pack("<Q", 24, 0)), "pfwm_manifest_version"),
        ("COUNTS", _mutate(data, pack("<I", 32, 0)), "pfwm_counts"),
        ("COMPONENT-OFFSET", _mutate(data, pack("<Q", 40, 0)), "pfwm_table_layout"),
        ("DEPENDENCY-OFFSET", _mutate(data, pack("<Q", 48, 0)), "pfwm_table_layout"),
        ("TOTAL-SIZE", _mutate(data, pack("<Q", 56, len(data) - 1)), "pfwm_truncated"),
        ("TRAILING", data + b"X", "pfwm_trailing_bytes"),
        ("LIMITS", _mutate(data, pack("<Q", 64, 0)), "pfwm_limits"),
        ("DIGEST-ZERO", _mutate(data, lambda x: x.__setitem__(slice(88, 120), b"\0" * 32)), "pfwm_digest_zero"),
        ("MANIFEST-ID", _mutate(data, lambda x: x.__setitem__(408, ord("p"))), "pfwm_manifest_id"),
        ("RESERVED", _mutate(data, lambda x: x.__setitem__(448, 1)), "pfwm_reserved"),
        ("BODY-DIGEST", _mutate(data, lambda x: x.__setitem__(376, x[376] ^ 1)), "pfwm_body_digest"),
        ("COMPONENT-ID", _mutate(data, pack("<I", c0, 0), repair_body=True), "pfwm_component_id"),
        ("COMPONENT-DUPLICATE-ID", _mutate(data, pack("<I", c1, 100), repair_body=True), "pfwm_component_id"),
        ("COMPONENT-ORDER", _mutate(data, lambda x: (struct.pack_into("<H", x, c1 + 8, 0), struct.pack_into("<I", x, c1, 50)), repair_body=True), "pfwm_component_order"),
        ("COMPONENT-KIND", _mutate(data, pack("<H", c0 + 4, 9), repair_body=True), "pfwm_component_kind"),
        ("COMPONENT-TRANSPORT", _mutate(data, pack("<H", c0 + 6, 9), repair_body=True), "pfwm_component_transport"),
        ("COMPONENT-MAPPING", _mutate(data, pack("<H", c0 + 6, pfwm1.TRANSPORT_DEVICE_PLUGIN), repair_body=True), "pfwm_component_mapping"),
        ("COMPONENT-FLAGS", _mutate(data, pack("<I", c0 + 16, 0), repair_body=True), "pfwm_component_flags"),
        ("COMPONENT-RESERVED", _mutate(data, pack("<I", c0 + 20, 1), repair_body=True), "pfwm_component_reserved"),
        ("COMPONENT-GUID", _mutate(data, lambda x: x.__setitem__(slice(c0 + 24, c0 + 40), b"\0" * 16), repair_body=True), "pfwm_component_guid"),
        ("COMPONENT-DUPLICATE-GUID", _mutate(data, lambda x: (x.__setitem__(slice(c1 + 24, c1 + 40), x[c0 + 24 : c0 + 40]), struct.pack_into("<Q", x, c1 + 40, 100)), repair_body=True), "pfwm_component_guid"),
        ("COMPONENT-HARDWARE-INSTANCE", _mutate(data, pack("<Q", c0 + 40, 0), repair_body=True), "pfwm_component_hardware_instance"),
        ("COMPONENT-VERSIONS", _mutate(data, pack("<Q", c0 + 56, 0xF1120001), repair_body=True), "pfwm_component_versions"),
        ("COMPONENT-PAYLOAD-SIZE", _mutate(data, pack("<Q", c0 + 88, 0), repair_body=True), "pfwm_component_payload_size"),
        ("COMPONENT-DIGEST", _mutate(data, lambda x: x.__setitem__(slice(c0 + 96, c0 + 128), b"\0" * 32), repair_body=True), "pfwm_component_digest"),
        ("DEPENDENCY-LAYOUT", _mutate(data, pack("<I", c1 + 12, 1), repair_body=True), "pfwm_dependency_layout"),
        ("DEPENDENCY-ID", _mutate(data, pack("<I", dep, 999), repair_body=True), "pfwm_dependency_id"),
        ("DEPENDENCY-VERSION", _mutate(data, pack("<Q", dep + 8, 1), repair_body=True), "pfwm_dependency_version"),
        ("DEPENDENCY-PHASE", _mutate(data, lambda x: (struct.pack_into("<H", x, c1 + 8, 0), struct.pack_into("<H", x, c2 + 8, 1)), repair_body=True), "pfwm_dependency_phase"),
        ("PHASE-GAP", _mutate(data, pack("<H", c2 + 8, 3), repair_body=True), "pfwm_phase_order"),
        ("MANIFEST-PAYLOAD-LIMIT", _mutate(data, pack("<Q", 64, 4096), repair_body=False), "pfwm_component_payload_size"),
    ]
    for _, candidate, expected in controls:
        if _parse_result(candidate) != f"ERR:{expected}":
            raise QualificationError(f"PFWM1 parser control expected {expected}")
    return controls


def _named_controls(probe: Path) -> list[dict[str, str]]:
    controls: list[tuple[str, str, str]] = []
    parser_controls = _parser_controls()
    parser_lines = _probe_lines(probe, [f"P:{data.hex()}" for _, data, _ in parser_controls])
    for (name, _, expected), line in zip(parser_controls, parser_lines, strict=True):
        if line != f"ERR:{expected}":
            raise QualificationError(f"Rust rejected {name} as {line}, expected {expected}")
        controls.append((f"NEG-N5-PFWM-PARSE-{name}", expected, "pass"))

    canonical = pfwm1.canonical_bundle()
    activation_lines = _probe_lines(
        probe, [f"A:{mode}:{canonical.hex()}" for mode, _ in ACTIVATION_MODES]
    )
    for (mode, expected), line in zip(ACTIVATION_MODES, activation_lines, strict=True):
        python = _activation_result(mode, canonical)
        if python != f"ERR:{expected}" or line != python:
            raise QualificationError(f"activation control {mode} diverged: {python} / {line}")
        controls.append((f"NEG-N5-PFWM-ACTIVATE-{mode.upper()}", expected, "pass"))

    post_lines = _probe_lines(
        probe, [f"R:{mode}:{canonical.hex()}" for mode, _ in POST_RESET_MODES]
    )
    for (mode, expected), line in zip(POST_RESET_MODES, post_lines, strict=True):
        python = _post_reset_result(mode, canonical)
        if python != f"ERR:{expected}" or line != python:
            raise QualificationError(f"post-reset control {mode} diverged: {python} / {line}")
        controls.append((f"NEG-N5-PFWM-POST-{mode.upper()}", expected, "pass"))
    return [{"id": identifier, "expected": expected, "status": status} for identifier, expected, status in controls]


def _mutated_manifest(rng: random.Random, case: int) -> bytes:
    sources = (pfwm1.canonical_bundle(), pfwm1.minimal_bundle(), pfwm1.boundary_bundle())
    source = sources[case % len(sources)]
    mode = case % 8
    if mode == 0:
        return source
    if mode == 1:
        return source[: rng.randrange(0, len(source) + 1)]
    if mode == 2:
        return source + rng.randbytes(rng.randrange(1, 9))
    data = bytearray(source)
    if mode == 3:
        data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
    elif mode == 4:
        for _ in range(rng.randrange(1, 5)):
            data[rng.randrange(len(data))] = rng.randrange(256)
    elif mode == 5:
        start = rng.randrange(len(data))
        end = min(len(data), start + rng.randrange(1, 65))
        data[start:end] = b"\0" * (end - start)
    elif mode == 6:
        offset = rng.choice((8, 12, 14, 18, 20, 24, 32, 36, 40, 48, 56, 64, 72, 76, 80, 84))
        width = 2 if offset in (8, 12, 14, 18, 76) else 4 if offset in (20, 32, 36, 72, 80, 84) else 8
        data[offset : offset + width] = rng.randbytes(width)
    else:
        start = rng.randrange(pfwm1.HEADER_BYTES, len(data))
        data[start] ^= 0x80
        _repair_body(data)
    return bytes(data)


def _differential(probe: Path) -> dict[str, dict[str, int]]:
    rng = random.Random(PARSER_SEED)
    parser_candidates = [_mutated_manifest(rng, index) for index in range(PARSER_DIFFERENTIAL_CASES)]
    expected = [_parse_result(data) for data in parser_candidates]
    actual = _probe_lines(probe, [f"P:{data.hex()}" for data in parser_candidates])
    parser_mismatches = sum(left != right for left, right in zip(expected, actual, strict=True))
    if parser_mismatches:
        raise QualificationError(f"PFWM1 parser differential mismatches: {parser_mismatches}")

    canonical = pfwm1.canonical_bundle()
    rng = random.Random(ACTIVATION_SEED)
    activation_modes = ["qualified", *(mode for mode, _ in ACTIVATION_MODES)]
    selected_activation = [rng.choice(activation_modes) for _ in range(ACTIVATION_DIFFERENTIAL_CASES)]
    expected = [_activation_result(mode, canonical) for mode in selected_activation]
    actual = _probe_lines(probe, [f"A:{mode}:{canonical.hex()}" for mode in selected_activation])
    activation_mismatches = sum(left != right for left, right in zip(expected, actual, strict=True))
    if activation_mismatches:
        raise QualificationError(f"PFWM1 activation differential mismatches: {activation_mismatches}")

    rng = random.Random(POST_RESET_SEED)
    post_modes = ["qualified", *(mode for mode, _ in POST_RESET_MODES)]
    selected_post = [rng.choice(post_modes) for _ in range(POST_RESET_DIFFERENTIAL_CASES)]
    expected = [_post_reset_result(mode, canonical) for mode in selected_post]
    actual = _probe_lines(probe, [f"R:{mode}:{canonical.hex()}" for mode in selected_post])
    post_mismatches = sum(left != right for left, right in zip(expected, actual, strict=True))
    if post_mismatches:
        raise QualificationError(f"PFWM1 post-reset differential mismatches: {post_mismatches}")
    return {
        "parser": {"cases": PARSER_DIFFERENTIAL_CASES, "mismatches": 0, "seed": PARSER_SEED},
        "activation": {"cases": ACTIVATION_DIFFERENTIAL_CASES, "mismatches": 0, "seed": ACTIVATION_SEED},
        "post_reset": {"cases": POST_RESET_DIFFERENTIAL_CASES, "mismatches": 0, "seed": POST_RESET_SEED},
    }


def _binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": pfwm1.sha256_bytes(data),
    }


def make_readiness(toolchain_root: Path = DEFAULT_TOOLCHAIN_ROOT) -> dict[str, Any]:
    contract = pfwm1.read_json(ROOT / pfwm1.CONTRACT_RELATIVE)
    golden = pfwm1.read_json(ROOT / pfwm1.GOLDEN_RELATIVE)
    contract_failures = pfwm1.contract_errors(contract, ROOT)
    golden_failures = pfwm1.golden_errors(golden, ROOT)
    if contract_failures or golden_failures:
        raise QualificationError("\n".join([*contract_failures, *golden_failures]))
    with tempfile.TemporaryDirectory(prefix="pooleos-pfwm1-") as directory:
        probe, build = _build_validators(toolchain_root, Path(directory))
        golden_requests = [f"P:{item['hex']}" for item in golden["vectors"]]
        golden_results = _probe_lines(probe, golden_requests)
        for item, rust_result in zip(golden["vectors"], golden_results, strict=True):
            data = bytes.fromhex(item["hex"])
            if _parse_result(data) != rust_result or pfwm1.summary(pfwm1.parse(data)) != item["summary"]:
                raise QualificationError(f"PFWM1 golden vector {item['id']} diverged")
        controls = _named_controls(probe)
        differential = _differential(probe)
        canonical = pfwm1.parse(pfwm1.canonical_bundle())
        development_errors = pfwm1.activation_errors(
            canonical, pfwm1.development_activation_context(canonical)
        )
        qualified_plan = pfwm1.authorize_dry_run_plan(
            canonical, pfwm1.synthetic_qualified_activation_context(canonical)
        )
        pfwm1.verify_post_reset(
            canonical,
            pfwm1.synthetic_post_reset_records(canonical),
            qualification_only=True,
        )
    report = {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_firmware_readiness",
        "contract_id": pfwm1.CONTRACT_ID,
        "status": "pass",
        "inputs": {
            "contract": _binding(ROOT / pfwm1.CONTRACT_RELATIVE),
            "golden_vectors": _binding(ROOT / pfwm1.GOLDEN_RELATIVE),
            "toolchain_lock": _binding(ROOT / "specs/native-toolchain-lock.json"),
            "toolchain_qualification": _binding(ROOT / "runs/native_toolchain_qualification.json"),
            "tier1_profile": _binding(ROOT / "specs/tier1-hardware-target.json"),
            "implementation_inputs": pfwm1.implementation_bindings(ROOT),
        },
        "build": build,
        "golden": {
            "status": "pass",
            "vector_count": len(golden["vectors"]),
            "python_vectors": len(golden["vectors"]),
            "rust_vectors": len(golden["vectors"]),
        },
        "negative_controls": controls,
        "differential": differential,
        "activation": {
            "canonical_profile": "synthetic_qualification_never_apply",
            "development_first_error": development_errors[0],
            "qualified_dry_run": dataclasses.asdict(qualified_plan),
            "live_apply_implementation_present": False,
            "production_apply_authority_created": False,
        },
        "payloads": {
            "component_count": len(canonical.components),
            "declared_external_payload_bytes": sum(
                item.external_payload_bytes for item in canonical.components
            ),
            "embedded_payload_count": 0,
            "embedded_payload_bytes": 0,
            "production_vendor_payload_count": 0,
        },
        "claims": pfwm1.expected_claims(),
        "non_claims": contract["non_claims"],
        "production_ready": False,
    }
    errors = pfwm1.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("\n".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    report = make_readiness(args.toolchain_root)
    encoded = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    if args.check:
        if not args.out.is_file() or args.out.read_bytes() != encoded:
            raise QualificationError(f"stale PFWM1 readiness: {args.out}")
        print("PFWM1 readiness is current")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(encoded)
    print(
        f"wrote {args.out}: {len(report['negative_controls'])} controls, "
        f"{sum(item['cases'] for item in report['differential'].values())} differential cases"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
