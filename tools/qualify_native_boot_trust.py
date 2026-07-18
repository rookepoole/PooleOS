#!/usr/bin/env python3
"""Qualify the bounded PBTRUST1 parser, bindings, and denial boundary."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_trust as trust  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / trust.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
POLICY_PARSER_CASES = 8_192
STATE_PARSER_CASES = 8_192
AUTHORIZATION_CASES = 8_192
POLICY_SEED = 0x5042_5452_5553_5401
STATE_SEED = 0x5042_5452_5553_5402
AUTHORIZATION_SEED = 0x5042_5452_5553_5403
FULL_EVIDENCE_MASK = 0xFF


class QualificationError(RuntimeError):
    """Raised when PBTRUST1 qualification fails closed."""


@dataclasses.dataclass(frozen=True)
class ProbeCase:
    identifier: str
    request: str
    expected: str


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
            f"command failed ({completed.returncode}): {' '.join(command[:10])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = trust.read_json(ROOT / "specs/native-toolchain-lock.json")
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
            "poole-boot-trust",
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
    if match is None or int(match.group(1)) != 4:
        raise QualificationError("expected exactly four PBTRUST1 Rust host tests")
    _run(
        _cargo(cargo, "fmt", "--package", "poole-boot-trust", "--", "--check"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        _cargo(
            cargo,
            "clippy",
            "--package",
            "poole-boot-trust",
            "--lib",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--no-deps",
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
                "poole-boot-trust",
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
            "pooleboot",
            "--target",
            "x86_64-unknown-uefi",
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "pooleboot-integration"),
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        _cargo(
            cargo,
            "build",
            "--package",
            "poole-boot-trust",
            "--features",
            "host-probe",
            "--bin",
            "pbtrust1-probe",
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
    probe = temporary_root / "probe" / HOST_TARGET / "debug" / "pbtrust1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PBTRUST1 host probe is missing")
    return probe, {
        "rustc": _run([str(rustc), "--version"], cwd=ROOT, env=env).strip(),
        "rust_host_tests_passed": 4,
        "rust_host_tests_total": 4,
        "rustfmt_packages": 1,
        "clippy_targets": 1,
        "no_std_targets": targets,
        "pooleboot_uefi_integration_builds_passed": 1,
        "pooleboot_uefi_integration_builds_total": 1,
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
        raise QualificationError(f"PBTRUST1 probe failed: {completed.stderr[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError("PBTRUST1 probe response count changed")
    return lines


def _policy_result(data: bytes) -> str:
    try:
        policy = trust.parse_policy(data)
    except trust.BootTrustError as error:
        return f"ERR:{error.code}"
    return (
        f"OK;flags={policy.flags};version={policy.policy_version};"
        f"epoch={policy.trust_epoch};floor={policy.minimum_secure_version};"
        f"generation={policy.minimum_state_generation};body={policy.body_sha256}"
    )


def _state_result(data: bytes) -> str:
    try:
        state = trust.parse_state(data)
    except trust.BootTrustError as error:
        return f"ERR:{error.code}"
    return (
        f"OK;flags={state.flags};copy={state.copy_index};"
        f"generation={state.state_generation};epoch={state.store_epoch};"
        f"manifest={state.accepted_manifest_version};"
        f"policy={state.accepted_policy_version};body={state.body_sha256}"
    )


def _evidence(mask: int) -> trust.VerificationEvidence:
    return trust.VerificationEvidence(
        policy_signature_verified=bool(mask & (1 << 0)),
        policy_threshold_verified=bool(mask & (1 << 1)),
        revocation_state_authenticated=bool(mask & (1 << 2)),
        policy_not_revoked=bool(mask & (1 << 3)),
        state_authenticated=bool(mask & (1 << 4)),
        state_monotonic=bool(mask & (1 << 5)),
        state_backend_writable=bool(mask & (1 << 6)),
        secure_boot_state_verified=bool(mask & (1 << 7)),
    )


def _authorization_result(
    policy_data: bytes,
    state_data: bytes,
    observed: trust.ObservedBoot,
    evidence_mask: int,
) -> str:
    try:
        policy = trust.parse_policy(policy_data)
        state = trust.parse_state(state_data)
        result = trust.authorize(policy, state, observed, _evidence(evidence_mask))
    except trust.BootTrustError as error:
        return f"ERR:{error.code}"
    return (
        f"OK;policy={result['policy_sha256']};state={result['state_sha256']};"
        f"version={result['policy_version']};generation={result['state_generation']};"
        f"epoch={result['trust_epoch']}"
    )


def _policy_request(data: bytes) -> str:
    return f"P:{data.hex().upper()}"


def _state_request(data: bytes) -> str:
    return f"S:{data.hex().upper()}"


def _authorization_request(
    policy_data: bytes,
    state_data: bytes,
    observed: trust.ObservedBoot,
    evidence_mask: int,
) -> str:
    return "A:" + ":".join(
        (
            policy_data.hex().upper(),
            state_data.hex().upper(),
            observed.manifest_sha256,
            observed.kernel_sha256,
            observed.retained_set_sha256,
            observed.revocation_set_sha256,
            str(observed.manifest_version),
            str(observed.minimum_secure_version),
            str(observed.artifact_role_mask),
            str(evidence_mask),
        )
    )


def _rehash_policy(data: bytearray) -> bytes:
    data[224:256] = hashlib.sha256(data[:224]).digest()
    return bytes(data)


def _rehash_state(data: bytearray) -> bytes:
    data[224:256] = hashlib.sha256(data[:224]).digest()
    return bytes(data)


def _set_int(data: bytes, offset: int, size: int, value: int, *, policy: bool) -> bytes:
    changed = bytearray(data)
    changed[offset : offset + size] = value.to_bytes(size, "little")
    return _rehash_policy(changed) if policy else _rehash_state(changed)


def _set_bytes(data: bytes, offset: int, value: bytes, *, policy: bool) -> bytes:
    changed = bytearray(data)
    changed[offset : offset + len(value)] = value
    return _rehash_policy(changed) if policy else _rehash_state(changed)


def _base_records(
    *, signed: bool, authenticated: bool
) -> tuple[bytes, bytes, trust.ObservedBoot]:
    observed = trust.ObservedBoot(
        manifest_sha256="11" * 32,
        kernel_sha256="22" * 32,
        retained_set_sha256="33" * 32,
        revocation_set_sha256="44" * 32,
        manifest_version=1,
        minimum_secure_version=1,
    )
    policy = trust.encode_policy(
        manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256,
        retained_set_sha256=observed.retained_set_sha256,
        revocation_set_sha256=observed.revocation_set_sha256,
        signed=signed,
    )
    state = trust.encode_state(
        policy_sha256=trust.sha256_bytes(policy),
        manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256,
        retained_set_sha256=observed.retained_set_sha256,
        authenticated_backend=authenticated,
    )
    return policy, state, observed


def _negative_cases() -> list[ProbeCase]:
    development_policy, development_state, observed = _base_records(
        signed=False, authenticated=False
    )
    signed_policy, authenticated_state, _ = _base_records(
        signed=True, authenticated=True
    )
    cases: list[ProbeCase] = []

    def add_policy(identifier: str, data: bytes, code: str) -> None:
        expected = f"ERR:{code}"
        actual = _policy_result(data)
        if actual != expected:
            raise QualificationError(
                f"negative control {identifier} expected {expected}, got {actual}"
            )
        cases.append(ProbeCase(identifier, _policy_request(data), expected))

    def add_state(identifier: str, data: bytes, code: str) -> None:
        expected = f"ERR:{code}"
        actual = _state_result(data)
        if actual != expected:
            raise QualificationError(
                f"negative control {identifier} expected {expected}, got {actual}"
            )
        cases.append(ProbeCase(identifier, _state_request(data), expected))

    def add_auth(
        identifier: str,
        policy_data: bytes,
        state_data: bytes,
        observed_value: trust.ObservedBoot,
        mask: int,
        code: str,
    ) -> None:
        expected = f"ERR:{code}"
        actual = _authorization_result(
            policy_data, state_data, observed_value, mask
        )
        if actual != expected:
            raise QualificationError(
                f"negative control {identifier} expected {expected}, got {actual}"
            )
        cases.append(
            ProbeCase(
                identifier,
                _authorization_request(
                    policy_data, state_data, observed_value, mask
                ),
                expected,
            )
        )

    add_policy("NEG-N5-PBTRUST-POLICY-TRUNCATED", development_policy[:-1], "pbtrust_policy_truncated")
    add_policy("NEG-N5-PBTRUST-POLICY-OVERSIZE", development_policy + b"\0", "pbtrust_policy_size")
    changed = bytearray(development_policy)
    changed[0] ^= 1
    add_policy("NEG-N5-PBTRUST-POLICY-MAGIC", bytes(changed), "pbtrust_policy_magic")
    add_policy("NEG-N5-PBTRUST-POLICY-MAJOR", _set_int(development_policy, 8, 2, 2, policy=True), "pbtrust_policy_version")
    add_policy("NEG-N5-PBTRUST-POLICY-MINOR", _set_int(development_policy, 10, 2, 1, policy=True), "pbtrust_policy_version")
    add_policy("NEG-N5-PBTRUST-POLICY-RECORD-BYTES", _set_int(development_policy, 12, 2, 319, policy=True), "pbtrust_policy_size")
    add_policy("NEG-N5-PBTRUST-POLICY-FLAGS-ZERO", _set_int(development_policy, 14, 2, 0, policy=True), "pbtrust_policy_flags")
    add_policy("NEG-N5-PBTRUST-POLICY-FLAGS-BOTH", _set_int(development_policy, 14, 2, 3, policy=True), "pbtrust_policy_flags")
    add_policy("NEG-N5-PBTRUST-POLICY-FLAGS-UNKNOWN", _set_int(development_policy, 14, 2, 0x8000, policy=True), "pbtrust_policy_flags")
    for label, offset in (("VERSION", 16), ("EPOCH", 24), ("SECURE-FLOOR", 32), ("GENERATION-FLOOR", 40)):
        add_policy(f"NEG-N5-PBTRUST-POLICY-{label}-ZERO", _set_int(development_policy, offset, 8, 0, policy=True), "pbtrust_policy_numbers")
    add_policy("NEG-N5-PBTRUST-POLICY-ROLE-MASK", _set_int(development_policy, 48, 4, 0x3F, policy=True), "pbtrust_policy_role_mask")
    add_policy("NEG-N5-PBTRUST-POLICY-RESERVED", _set_int(development_policy, 60, 4, 1, policy=True), "pbtrust_policy_signer_shape")
    for label, offset in (("MANIFEST", 64), ("KERNEL", 96), ("RETAINED", 128), ("REVOCATION", 160)):
        add_policy(f"NEG-N5-PBTRUST-POLICY-{label}-DIGEST", _set_bytes(development_policy, offset, bytes(32), policy=True), "pbtrust_policy_digest")
    changed = bytearray(development_policy)
    changed[224] ^= 1
    add_policy("NEG-N5-PBTRUST-POLICY-BODY-DIGEST", bytes(changed), "pbtrust_policy_body_digest")
    add_policy("NEG-N5-PBTRUST-POLICY-DEVELOPMENT-SIGNER", _set_int(development_policy, 52, 2, 1, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-DEVELOPMENT-ROOT", _set_bytes(development_policy, 192, b"\x01" + bytes(15), policy=True), "pbtrust_policy_signer_shape")
    changed = bytearray(development_policy)
    changed[256] = 1
    add_policy("NEG-N5-PBTRUST-POLICY-DEVELOPMENT-SIGNATURE", bytes(changed), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-THRESHOLD-ZERO", _set_int(signed_policy, 52, 2, 0, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-THRESHOLD-COUNT", _set_int(signed_policy, 52, 2, 2, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-COUNT-MAX", _set_int(signed_policy, 54, 2, 9, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-AUTH-PROFILE", _set_int(signed_policy, 56, 2, 0, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-SIGNATURE-ZERO", _set_int(signed_policy, 58, 2, 0, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-SIGNATURE-OVERSIZE", _set_int(signed_policy, 58, 2, 65, policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-ROOT-ZERO", _set_bytes(signed_policy, 192, bytes(16), policy=True), "pbtrust_policy_signer_shape")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-SIGNER-ZERO", _set_bytes(signed_policy, 208, bytes(16), policy=True), "pbtrust_policy_signer_shape")
    changed = bytearray(signed_policy)
    changed[256:320] = bytes(64)
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-SIGNATURE-EMPTY", bytes(changed), "pbtrust_policy_signature")
    add_policy("NEG-N5-PBTRUST-POLICY-SIGNED-SIGNATURE-PADDING", _set_int(signed_policy, 58, 2, 32, policy=True), "pbtrust_policy_signature")

    add_state("NEG-N5-PBTRUST-STATE-TRUNCATED", development_state[:-1], "pbtrust_state_truncated")
    add_state("NEG-N5-PBTRUST-STATE-OVERSIZE", development_state + b"\0", "pbtrust_state_size")
    changed = bytearray(development_state)
    changed[0] ^= 1
    add_state("NEG-N5-PBTRUST-STATE-MAGIC", bytes(changed), "pbtrust_state_magic")
    add_state("NEG-N5-PBTRUST-STATE-MAJOR", _set_int(development_state, 8, 2, 2, policy=False), "pbtrust_state_version")
    add_state("NEG-N5-PBTRUST-STATE-MINOR", _set_int(development_state, 10, 2, 1, policy=False), "pbtrust_state_version")
    add_state("NEG-N5-PBTRUST-STATE-RECORD-BYTES", _set_int(development_state, 12, 2, 255, policy=False), "pbtrust_state_size")
    add_state("NEG-N5-PBTRUST-STATE-FLAGS-NO-COMMIT", _set_int(development_state, 14, 2, trust.STATE_FLAG_DEVELOPMENT_CANDIDATE, policy=False), "pbtrust_state_flags")
    add_state("NEG-N5-PBTRUST-STATE-FLAGS-NO-PROFILE", _set_int(development_state, 14, 2, trust.STATE_FLAG_COMMITTED, policy=False), "pbtrust_state_flags")
    add_state("NEG-N5-PBTRUST-STATE-FLAGS-BOTH-PROFILES", _set_int(development_state, 14, 2, trust.STATE_KNOWN_FLAGS, policy=False), "pbtrust_state_flags")
    add_state("NEG-N5-PBTRUST-STATE-FLAGS-UNKNOWN", _set_int(development_state, 14, 2, 0x8000 | trust.STATE_FLAG_COMMITTED | trust.STATE_FLAG_DEVELOPMENT_CANDIDATE, policy=False), "pbtrust_state_flags")
    add_state("NEG-N5-PBTRUST-STATE-COPY-INDEX", _set_int(development_state, 16, 1, 2, policy=False), "pbtrust_state_copy")
    add_state("NEG-N5-PBTRUST-STATE-COPY-COUNT", _set_int(development_state, 17, 1, 1, policy=False), "pbtrust_state_copy")
    add_state("NEG-N5-PBTRUST-STATE-COMMIT", _set_int(development_state, 18, 2, 0, policy=False), "pbtrust_state_commit")
    add_state("NEG-N5-PBTRUST-STATE-DEVELOPMENT-AUTH", _set_int(development_state, 20, 2, 1, policy=False), "pbtrust_state_auth_profile")
    add_state("NEG-N5-PBTRUST-STATE-AUTHENTICATED-AUTH-ZERO", _set_int(authenticated_state, 20, 2, 0, policy=False), "pbtrust_state_auth_profile")
    add_state("NEG-N5-PBTRUST-STATE-RESERVED", _set_int(development_state, 22, 2, 1, policy=False), "pbtrust_state_auth_profile")
    for label, offset in (("GENERATION", 24), ("EPOCH", 32), ("SECURE-FLOOR", 40), ("MANIFEST-VERSION", 48), ("POLICY-VERSION", 56)):
        add_state(f"NEG-N5-PBTRUST-STATE-{label}-ZERO", _set_int(development_state, offset, 8, 0, policy=False), "pbtrust_state_numbers")
    add_state("NEG-N5-PBTRUST-STATE-MANIFEST-BELOW-FLOOR", _set_int(development_state, 40, 8, 2, policy=False), "pbtrust_state_numbers")
    for label, offset in (("POLICY", 64), ("MANIFEST", 96), ("KERNEL", 128), ("RETAINED", 160)):
        add_state(f"NEG-N5-PBTRUST-STATE-{label}-DIGEST", _set_bytes(development_state, offset, bytes(32), policy=False), "pbtrust_state_digest")
    add_state("NEG-N5-PBTRUST-STATE-GENERATION-ONE-PREVIOUS", _set_bytes(development_state, 192, b"\x01" + bytes(31), policy=False), "pbtrust_state_previous")
    add_state("NEG-N5-PBTRUST-STATE-GENERATION-TWO-NO-PREVIOUS", _set_int(development_state, 24, 8, 2, policy=False), "pbtrust_state_previous")
    changed = bytearray(development_state)
    changed[224] ^= 1
    add_state("NEG-N5-PBTRUST-STATE-BODY-DIGEST", bytes(changed), "pbtrust_state_body_digest")

    add_auth("NEG-N5-PBTRUST-BINDING-MANIFEST", signed_policy, authenticated_state, dataclasses.replace(observed, manifest_sha256="55" * 32), FULL_EVIDENCE_MASK, "pbtrust_binding_manifest")
    add_auth("NEG-N5-PBTRUST-BINDING-KERNEL", signed_policy, authenticated_state, dataclasses.replace(observed, kernel_sha256="55" * 32), FULL_EVIDENCE_MASK, "pbtrust_binding_kernel")
    add_auth("NEG-N5-PBTRUST-BINDING-RETAINED", signed_policy, authenticated_state, dataclasses.replace(observed, retained_set_sha256="55" * 32), FULL_EVIDENCE_MASK, "pbtrust_binding_retained_set")
    add_auth("NEG-N5-PBTRUST-BINDING-REVOCATION", signed_policy, authenticated_state, dataclasses.replace(observed, revocation_set_sha256="55" * 32), FULL_EVIDENCE_MASK, "pbtrust_binding_revocation_set")
    add_auth("NEG-N5-PBTRUST-BINDING-ROLE-MASK", signed_policy, authenticated_state, dataclasses.replace(observed, artifact_role_mask=0x3F), FULL_EVIDENCE_MASK, "pbtrust_binding_role_mask")
    add_auth("NEG-N5-PBTRUST-BINDING-POLICY-STATE", signed_policy, _set_bytes(authenticated_state, 64, bytes.fromhex("55" * 32), policy=False), observed, FULL_EVIDENCE_MASK, "pbtrust_binding_policy_state")
    add_auth("NEG-N5-PBTRUST-BINDING-STATE-MANIFEST", signed_policy, _set_bytes(authenticated_state, 96, bytes.fromhex("55" * 32), policy=False), observed, FULL_EVIDENCE_MASK, "pbtrust_binding_state_manifest")
    add_auth("NEG-N5-PBTRUST-BINDING-STATE-KERNEL", signed_policy, _set_bytes(authenticated_state, 128, bytes.fromhex("55" * 32), policy=False), observed, FULL_EVIDENCE_MASK, "pbtrust_binding_state_kernel")
    add_auth("NEG-N5-PBTRUST-BINDING-STATE-RETAINED", signed_policy, _set_bytes(authenticated_state, 160, bytes.fromhex("55" * 32), policy=False), observed, FULL_EVIDENCE_MASK, "pbtrust_binding_state_retained_set")
    add_auth("NEG-N5-PBTRUST-BINDING-POLICY-VERSION", signed_policy, _set_int(authenticated_state, 56, 8, 2, policy=False), observed, FULL_EVIDENCE_MASK, "pbtrust_binding_policy_version")
    add_auth("NEG-N5-PBTRUST-ROLLBACK-MANIFEST-VERSION", signed_policy, _set_int(authenticated_state, 48, 8, 2, policy=False), observed, FULL_EVIDENCE_MASK, "pbtrust_rollback_manifest_version")

    policy_floor = _set_int(signed_policy, 32, 8, 2, policy=True)
    state_for_policy_floor = trust.encode_state(
        policy_sha256=trust.sha256_bytes(policy_floor), manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256, retained_set_sha256=observed.retained_set_sha256,
        authenticated_backend=True,
    )
    add_auth("NEG-N5-PBTRUST-ROLLBACK-POLICY-SECURE-FLOOR", policy_floor, state_for_policy_floor, observed, FULL_EVIDENCE_MASK, "pbtrust_rollback_secure_version")
    state_floor = trust.encode_state(
        policy_sha256=trust.sha256_bytes(signed_policy), manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256, retained_set_sha256=observed.retained_set_sha256,
        minimum_secure_version=2, accepted_manifest_version=2, authenticated_backend=True,
    )
    add_auth("NEG-N5-PBTRUST-ROLLBACK-STATE-SECURE-FLOOR", signed_policy, state_floor, dataclasses.replace(observed, manifest_version=2), FULL_EVIDENCE_MASK, "pbtrust_rollback_secure_version")
    add_auth("NEG-N5-PBTRUST-ROLLBACK-OBSERVED-SECURE-FLOOR", signed_policy, authenticated_state, dataclasses.replace(observed, minimum_secure_version=2), FULL_EVIDENCE_MASK, "pbtrust_rollback_secure_version")
    policy_generation = _set_int(signed_policy, 40, 8, 2, policy=True)
    state_for_generation = trust.encode_state(
        policy_sha256=trust.sha256_bytes(policy_generation), manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256, retained_set_sha256=observed.retained_set_sha256,
        authenticated_backend=True,
    )
    add_auth("NEG-N5-PBTRUST-ROLLBACK-GENERATION", policy_generation, state_for_generation, observed, FULL_EVIDENCE_MASK, "pbtrust_rollback_state_generation")
    policy_epoch = _set_int(signed_policy, 24, 8, 2, policy=True)
    state_for_epoch = trust.encode_state(
        policy_sha256=trust.sha256_bytes(policy_epoch), manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256, retained_set_sha256=observed.retained_set_sha256,
        authenticated_backend=True,
    )
    add_auth("NEG-N5-PBTRUST-ROLLBACK-EPOCH", policy_epoch, state_for_epoch, observed, FULL_EVIDENCE_MASK, "pbtrust_rollback_trust_epoch")
    add_auth("NEG-N5-PBTRUST-POLICY-UNSIGNED", development_policy, development_state, observed, FULL_EVIDENCE_MASK, "pbtrust_policy_unsigned")
    for identifier, mask, code in (
        ("NEG-N5-PBTRUST-EVIDENCE-POLICY-SIGNATURE", 0xFE, "pbtrust_policy_authentication"),
        ("NEG-N5-PBTRUST-EVIDENCE-POLICY-THRESHOLD", 0xFD, "pbtrust_policy_threshold"),
        ("NEG-N5-PBTRUST-EVIDENCE-REVOCATION-AUTH", 0xFB, "pbtrust_policy_revocation"),
        ("NEG-N5-PBTRUST-EVIDENCE-POLICY-REVOKED", 0xF7, "pbtrust_policy_revocation"),
        ("NEG-N5-PBTRUST-EVIDENCE-STATE-AUTH", 0xEF, "pbtrust_state_authentication"),
        ("NEG-N5-PBTRUST-EVIDENCE-STATE-MONOTONIC", 0xDF, "pbtrust_state_monotonicity"),
        ("NEG-N5-PBTRUST-EVIDENCE-BACKEND-WRITABLE", 0xBF, "pbtrust_state_backend_writable"),
        ("NEG-N5-PBTRUST-EVIDENCE-SECURE-BOOT", 0x7F, "pbtrust_secure_boot_state"),
    ):
        add_auth(identifier, signed_policy, authenticated_state, observed, mask, code)
    signed_candidate_state = trust.encode_state(
        policy_sha256=trust.sha256_bytes(signed_policy), manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256, retained_set_sha256=observed.retained_set_sha256,
        authenticated_backend=False,
    )
    add_auth("NEG-N5-PBTRUST-STATE-DEVELOPMENT-CANDIDATE", signed_policy, signed_candidate_state, observed, FULL_EVIDENCE_MASK, "pbtrust_state_development_candidate")
    return cases


def _run_negative_controls(probe: Path) -> list[dict[str, Any]]:
    cases = _negative_cases()
    rust_results = _probe_lines(probe, [case.request for case in cases])
    results: list[dict[str, Any]] = []
    for case, rust_result in zip(cases, rust_results, strict=True):
        if case.request.startswith("P:"):
            python_result = _policy_result(bytes.fromhex(case.request[2:]))
        elif case.request.startswith("S:"):
            python_result = _state_result(bytes.fromhex(case.request[2:]))
        else:
            python_result = case.expected
        status = (
            "pass"
            if python_result == rust_result == case.expected
            else "fail"
        )
        results.append(
            {
                "id": case.identifier,
                "expected": case.expected,
                "python": python_result,
                "rust": rust_result,
                "status": status,
            }
        )
    failures = [item for item in results if item["status"] != "pass"]
    if failures:
        raise QualificationError(f"PBTRUST1 hostile controls failed: {failures[:3]}")
    return results


def _mutated_records(data: bytes, count: int, seed: int) -> list[bytes]:
    randomizer = random.Random(seed)
    records: list[bytes] = []
    for _ in range(count):
        changed = bytearray(data)
        for _ in range(randomizer.randint(1, 3)):
            offset = randomizer.randrange(len(changed))
            changed[offset] ^= 1 << randomizer.randrange(8)
        records.append(bytes(changed))
    return records


def _parser_differential(
    probe: Path,
    *,
    prefix: str,
    data: bytes,
    cases: int,
    seed: int,
    request: Callable[[bytes], str],
    oracle: Callable[[bytes], str],
) -> dict[str, int]:
    records = _mutated_records(data, cases, seed)
    requests = [request(item) for item in records]
    expected = [oracle(item) for item in records]
    observed = _probe_lines(probe, requests)
    mismatches = sum(left != right for left, right in zip(expected, observed, strict=True))
    if mismatches:
        raise QualificationError(f"PBTRUST1 {prefix} differential mismatches: {mismatches}")
    return {"cases": cases, "mismatches": 0, "seed": seed}


def _authorization_differential(probe: Path) -> dict[str, int]:
    policy, state, observed = _base_records(signed=True, authenticated=True)
    randomizer = random.Random(AUTHORIZATION_SEED)
    requests: list[str] = []
    expected: list[str] = []
    for _ in range(AUTHORIZATION_CASES):
        candidate = observed
        selector = randomizer.randrange(8)
        if selector == 1:
            candidate = dataclasses.replace(candidate, manifest_sha256=f"{randomizer.getrandbits(256):064X}")
        elif selector == 2:
            candidate = dataclasses.replace(candidate, kernel_sha256=f"{randomizer.getrandbits(256):064X}")
        elif selector == 3:
            candidate = dataclasses.replace(candidate, retained_set_sha256=f"{randomizer.getrandbits(256):064X}")
        elif selector == 4:
            candidate = dataclasses.replace(candidate, revocation_set_sha256=f"{randomizer.getrandbits(256):064X}")
        elif selector == 5:
            candidate = dataclasses.replace(candidate, artifact_role_mask=randomizer.randrange(0, 256))
        elif selector == 6:
            candidate = dataclasses.replace(candidate, manifest_version=randomizer.randrange(1, 5))
        elif selector == 7:
            candidate = dataclasses.replace(candidate, minimum_secure_version=randomizer.randrange(1, 5))
        mask = randomizer.randrange(256)
        requests.append(_authorization_request(policy, state, candidate, mask))
        expected.append(_authorization_result(policy, state, candidate, mask))
    observed_results = _probe_lines(probe, requests)
    mismatches = sum(
        left != right for left, right in zip(expected, observed_results, strict=True)
    )
    if mismatches:
        raise QualificationError(
            f"PBTRUST1 authorization differential mismatches: {mismatches}"
        )
    return {
        "cases": AUTHORIZATION_CASES,
        "mismatches": 0,
        "seed": AUTHORIZATION_SEED,
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = trust.read_json(ROOT / trust.CONTRACT_RELATIVE)
    contract_failures = trust.contract_errors(contract, ROOT)
    if contract_failures:
        raise QualificationError(
            "PBTRUST1 contract is stale: " + "; ".join(contract_failures[:8])
        )
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pbtrust1-qualification-", dir=ROOT / "tmp"
    ) as temporary:
        temporary_root = Path(temporary)
        probe, build = _build_validators(toolchain_root, temporary_root)
        development_policy, development_state, observed = _base_records(
            signed=False, authenticated=False
        )
        development = trust.validate_development(
            development_policy, development_state, observed
        )
        signed_policy, authenticated_state, _ = _base_records(
            signed=True, authenticated=True
        )
        authorized = trust.authorize(
            trust.parse_policy(signed_policy),
            trust.parse_state(authenticated_state),
            observed,
            trust.VerificationEvidence.synthetic_qualified(),
        )
        if authorized["policy_version"] != 1 or authorized["state_generation"] != 1:
            raise QualificationError("PBTRUST1 synthetic authorization model changed")
        generation_two = trust.encode_state(
            policy_sha256=trust.sha256_bytes(signed_policy),
            manifest_sha256=observed.manifest_sha256,
            kernel_sha256=observed.kernel_sha256,
            retained_set_sha256=observed.retained_set_sha256,
            state_generation=2,
            authenticated_backend=True,
            copy_index=1,
            previous_state_sha256=trust.sha256_bytes(authenticated_state),
        )
        trust.parse_state(generation_two)
        controls = _run_negative_controls(probe)
        differential = {
            "policy_parser": _parser_differential(
                probe,
                prefix="policy parser",
                data=development_policy,
                cases=POLICY_PARSER_CASES,
                seed=POLICY_SEED,
                request=_policy_request,
                oracle=_policy_result,
            ),
            "state_parser": _parser_differential(
                probe,
                prefix="state parser",
                data=development_state,
                cases=STATE_PARSER_CASES,
                seed=STATE_SEED,
                request=_state_request,
                oracle=_state_result,
            ),
            "authorization": _authorization_differential(probe),
        }
    expected_control_count = contract["qualification"]["negative_control_count"]
    if len(controls) != expected_control_count:
        raise QualificationError(
            f"PBTRUST1 hostile-control register changed: {len(controls)} != {expected_control_count}"
        )
    readiness: dict[str, Any] = {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_boot_trust_readiness",
        "contract_id": trust.CONTRACT_ID,
        "status": "pass",
        "inputs": {
            "contract": trust.file_binding(ROOT, trust.CONTRACT_RELATIVE),
            "toolchain_lock": trust.file_binding(ROOT, "specs/native-toolchain-lock.json"),
            "toolchain_qualification": trust.file_binding(
                ROOT, "runs/native_toolchain_qualification.json"
            ),
            "tier1_profile": trust.file_binding(
                ROOT, "runs/hardware_target_readiness.json"
            ),
            "implementation_inputs": [
                trust.file_binding(ROOT, path) for path in trust.IMPLEMENTATION_INPUTS
            ],
        },
        "build": build,
        "golden": {
            "case_count": 3,
            "development_policy_sha256": trust.sha256_bytes(development_policy),
            "development_state_sha256": trust.sha256_bytes(development_state),
            "signed_shape_policy_sha256": trust.sha256_bytes(signed_policy),
            "authenticated_shape_state_sha256": trust.sha256_bytes(authenticated_state),
            "generation_two_state_sha256": trust.sha256_bytes(generation_two),
            "synthetic_authorization_model_result": "qualified_shape_only_no_crypto_claim",
        },
        "negative_controls": controls,
        "differential": differential,
        "development_integration": {
            key: development[key]
            for key in (
                "policy_bytes",
                "state_bytes",
                "binding_count",
                "denial_count",
                "denial",
                "state_source",
                "state_authenticated",
                "state_monotonic",
                "state_backend_writable",
                "signature_verifications",
                "authority_grants",
                "state_writes",
            )
        },
        "claims": trust.expected_claims(),
        "non_claims": contract["non_claims"],
        "production_ready": False,
    }
    failures = trust.readiness_errors(readiness, ROOT)
    if failures:
        raise QualificationError(
            "PBTRUST1 readiness failed: " + "; ".join(failures[:8])
        )
    return readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    readiness = make_readiness(args.toolchain_root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(readiness, indent=2) + "\n", encoding="utf-8")
    print(
        "PBTRUST1 qualification PASS "
        f"controls={len(readiness['negative_controls'])} "
        f"differential={sum(item['cases'] for item in readiness['differential'].values())} "
        "authority=0 state_writes=0 production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
