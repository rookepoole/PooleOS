#!/usr/bin/env python3
"""Qualify PREC1 parsers, state transitions, activation gates, and differential cases."""

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_recovery as prec1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / prec1.READINESS_RELATIVE
PARSER_DIFFERENTIAL_CASES = 16_384
TRANSITION_DIFFERENTIAL_CASES = 8_192
DIFFERENTIAL_SEED = 0x5052_4543_3101
TRANSITION_SEED = 0x5052_4543_3102


class QualificationError(RuntimeError):
    """Raised when PREC1 qualification fails closed."""


@dataclass(frozen=True)
class Control:
    control_id: str
    surface: str
    request: str
    expected: str


def _run(command: list[str], *, cwd: Path, env: dict[str, str], input_text: str | None = None) -> str:
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
            f"command failed ({completed.returncode}): {' '.join(command[:7])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = json.loads((ROOT / "specs/native-toolchain-lock.json").read_text(encoding="utf-8"))
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
    native_root = NATIVE_ROOT.resolve()
    for target in ("X86_64_UNKNOWN_UEFI", "X86_64_UNKNOWN_NONE"):
        env[f"CARGO_TARGET_{target}_RUSTFLAGS"] = " ".join(
            (
                "-Cpanic=abort",
                '--cfg=sha2_backend="soft"',
                '--cfg=sha2_backend_soft="compact"',
                f"--remap-path-prefix={native_root}=/pooleos/native",
            )
        )
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _single_rlib(target_dir: Path, target: str) -> Path:
    artifacts = sorted((target_dir / target / "release" / "deps").glob("libpoole_recovery-*.rlib"))
    if len(artifacts) != 1:
        raise QualificationError(f"expected one PREC1 rlib for {target}, found {len(artifacts)}")
    return artifacts[0]


def _build_validators(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    host_target = "x86_64-pc-windows-msvc"
    test_target = temporary_root / "host-tests"
    output = _run(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-recovery",
            "--lib",
            "--target",
            host_target,
            "--locked",
            "--offline",
            "--target-dir",
            str(test_target),
            "--",
            "--test-threads=1",
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", output)
    if match is None or int(match.group(1)) != 3:
        raise QualificationError("expected exactly three PREC1 Rust host tests")

    targets = []
    for target in ("x86_64-unknown-uefi", "x86_64-unknown-none"):
        target_dir = temporary_root / f"validator-{target}"
        _run(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "poole-recovery",
                "--lib",
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(target_dir),
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
        artifact = _single_rlib(target_dir, target)
        targets.append(
            {
                "target": target,
                "status": "pass",
                "byte_count": artifact.stat().st_size,
                "sha256": prec1.sha256_bytes(artifact.read_bytes()),
            }
        )

    probe_target = temporary_root / "host-probe"
    _run(
        [
            str(cargo),
            "build",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-recovery",
            "--bin",
            "prec1-probe",
            "--features",
            "host-probe",
            "--target",
            host_target,
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(probe_target),
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    probe = probe_target / host_target / "release" / "prec1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PREC1 host probe is missing")
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    return probe, {
        "rustc_version_sha256": prec1.sha256_bytes(version.encode("utf-8")),
        "rust_host_target": host_target,
        "rust_host_test_count": 3,
        "rust_host_test_pass_count": 3,
        "no_std_target_builds": targets,
        "host_probe_byte_count": probe.stat().st_size,
        "host_probe_artifact_identity_recorded": False,
        "host_probe_role": "ephemeral host-only differential and transition transport",
    }


def _probe_lines(probe: Path, requests: list[str]) -> list[str]:
    output = subprocess.run(
        [str(probe)],
        cwd=ROOT,
        input="\n".join(requests) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if output.returncode != 0:
        raise QualificationError(f"PREC1 probe failed: {output.stdout[-2000:]}")
    lines = output.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError(f"PREC1 probe returned {len(lines)} lines for {len(requests)} requests")
    return lines


def _repair_policy(data: bytearray) -> None:
    if len(data) == prec1.TOTAL_BYTES:
        data[104:136] = hashlib.sha256(data[prec1.HEADER_BYTES :]).digest()


def _policy_change(base: bytes, offset: int, payload: bytes, *, repair: bool = False) -> bytes:
    value = bytearray(base)
    value[offset : offset + len(payload)] = payload
    if repair:
        _repair_policy(value)
    return bytes(value)


def _policy_controls() -> list[Control]:
    base = prec1.canonical_bundle()
    controls: list[Control] = []

    def add(name: str, data: bytes) -> None:
        controls.append(Control(f"NEG-N5-PREC1-{name}", "policy_parse", f"P:{data.hex().upper()}", prec1.parse_result(data)))

    add("EMPTY", b"")
    add("TRUNCATED", base[:100])
    add("TRAILING", base + b"\0")
    add("MAGIC", _policy_change(base, 0, b"BADPREC1"))
    add("MAJOR", _policy_change(base, 8, struct.pack("<H", 2)))
    add("MINOR", _policy_change(base, 10, struct.pack("<H", 1)))
    add("HEADER", _policy_change(base, 12, struct.pack("<H", 248)))
    add("ALIGNMENT", _policy_change(base, 14, struct.pack("<H", 16)))
    add("TOTAL", _policy_change(base, 16, struct.pack("<I", 991)))
    add("FLAGS-MISSING", _policy_change(base, 20, struct.pack("<I", prec1.REQUIRED_FLAGS ^ 1)))
    add("FLAGS-UNKNOWN", _policy_change(base, 20, struct.pack("<I", prec1.REQUIRED_FLAGS | (1 << 31))))
    add("VERSION-ZERO", _policy_change(base, 24, struct.pack("<Q", 0)))
    add("FLOOR-ZERO", _policy_change(base, 32, struct.pack("<Q", 0)))
    add("ROLLBACK", _policy_change(base, 32, struct.pack("<Q", 2)))
    add("PBP-ABI", _policy_change(base, 40, struct.pack("<H", 0)))
    add("KERNEL-ABI", _policy_change(base, 44, struct.pack("<H", 0)))
    add("ATTEMPTS-ZERO", _policy_change(base, 48, struct.pack("<H", 0)))
    add("ATTEMPTS-HIGH", _policy_change(base, 48, struct.pack("<H", 8)))
    add("SAFE-ATTEMPTS", _policy_change(base, 50, struct.pack("<H", 2)))
    add("DEADLINE-ZERO", _policy_change(base, 52, struct.pack("<I", 0)))
    add("DEADLINE-HIGH", _policy_change(base, 52, struct.pack("<I", 3601)))
    add("STATE-BYTES", _policy_change(base, 56, struct.pack("<H", 120)))
    add("CHECKSUM-BYTES", _policy_change(base, 58, struct.pack("<H", 32)))
    add("SLOT-COUNT", _policy_change(base, 60, struct.pack("<H", 3)))
    add("FAILURE-COUNT", _policy_change(base, 62, struct.pack("<H", 9)))
    add("AUTHORITY-COUNT", _policy_change(base, 64, struct.pack("<H", 6)))
    add("WRITE-POLICY", _policy_change(base, 66, struct.pack("<H", 0)))
    add("SLOT-OFFSET", _policy_change(base, 68, struct.pack("<I", 264)))
    add("FAILURE-OFFSET", _policy_change(base, 72, struct.pack("<I", 456)))
    add("AUTHORITY-OFFSET", _policy_change(base, 76, struct.pack("<I", 776)))
    add("MODES", _policy_change(base, 80, struct.pack("<I", 0x1F)))
    add("FAILURE-MASK", _policy_change(base, 84, struct.pack("<I", 0x1FF)))
    add("ACTION-MASK", _policy_change(base, 88, struct.pack("<I", 0x1F)))
    add("HANDOFF", _policy_change(base, 92, struct.pack("<I", 0x1F)))
    add("GENERATION-FLOOR", _policy_change(base, 96, struct.pack("<Q", 0)))
    add("BODY-DIGEST", _policy_change(base, 104, b"\0"))
    add("RECOVERY-DIGEST", _policy_change(base, 136, b"\0" * 32))
    add("STATE-STORE", _policy_change(base, 168, b"\0" * 16))
    add("NORMAL-FALLBACK", _policy_change(base, 184, struct.pack("<H", prec1.ACTION_RECOVERY)))
    add("SAFE-FALLBACK", _policy_change(base, 186, struct.pack("<H", prec1.ACTION_PREVIOUS)))
    add("NO-KNOWN-GOOD", _policy_change(base, 188, struct.pack("<H", prec1.ACTION_HALT)))
    add("WRITE-FAILURE", _policy_change(base, 190, struct.pack("<H", prec1.ACTION_HALT)))
    add("AUTHORITY-CEILING", _policy_change(base, 192, struct.pack("<I", 8)))
    add("TRANSPORT", _policy_change(base, 196, struct.pack("<I", 1)))
    add("HEADER-RESERVED", _policy_change(base, 200, b"\1"))
    slot1 = prec1.SLOT_OFFSET
    slot2 = slot1 + prec1.SLOT_BYTES
    add("SLOT-ID", _policy_change(base, slot1, struct.pack("<H", 2), repair=True))
    add("SLOT-FLAGS", _policy_change(base, slot1 + 2, struct.pack("<H", 1), repair=True))
    add("SLOT-PRIORITY-ZERO", _policy_change(base, slot1 + 4, struct.pack("<I", 0), repair=True))
    add("SLOT-PRIORITY-ORDER", _policy_change(base, slot2 + 4, struct.pack("<I", 15), repair=True))
    add("SLOT-VERSION", _policy_change(base, slot2 + 8, struct.pack("<Q", 0), repair=True))
    add("SLOT-RECOVERY-VERSION", _policy_change(base, slot1 + 16, struct.pack("<Q", 0), repair=True))
    add("SLOT-MANIFEST-ZERO", _policy_change(base, slot1 + 24, b"\0" * 32, repair=True))
    add("SLOT-MANIFEST-DUP", _policy_change(base, slot2 + 24, base[slot1 + 24 : slot1 + 56], repair=True))
    add("SLOT-RESERVED", _policy_change(base, slot1 + 88, b"\1", repair=True))
    failure = prec1.FAILURE_OFFSET
    add("FAILURE-ID", _policy_change(base, failure, struct.pack("<H", 2), repair=True))
    add("FAILURE-RULE", _policy_change(base, failure + 2, struct.pack("<H", prec1.ACTION_HALT), repair=True))
    add("FAILURE-EVIDENCE", _policy_change(base, failure + 10, struct.pack("<H", 999), repair=True))
    add("FAILURE-RESERVED", _policy_change(base, failure + 16, b"\1", repair=True))
    add("FAILURE-MODE", _policy_change(base, failure + 12, struct.pack("<I", 1), repair=True))
    authority = prec1.AUTHORITY_OFFSET
    add("AUTHORITY-ID", _policy_change(base, authority, struct.pack("<H", 2), repair=True))
    add("AUTHORITY-RULE", _policy_change(base, authority + 2, struct.pack("<H", 0), repair=True))
    add("AUTHORITY-FACTORS", _policy_change(base, authority + 4, struct.pack("<I", 1 << 31), repair=True))
    add("AUTHORITY-AMBIENT", _policy_change(base, authority + 8, struct.pack("<I", 0), repair=True))
    add("AUTHORITY-RESERVED", _policy_change(base, authority + 24, b"\1", repair=True))
    add("AUTHORITY-EVIDENCE", _policy_change(base, authority + 20, struct.pack("<I", 999), repair=True))
    add("SLOT-KERNEL-DUP", _policy_change(base, slot2 + 56, base[slot1 + 56 : slot1 + 88], repair=True))
    if len(controls) != 66:
        raise QualificationError(f"expected 66 policy controls, found {len(controls)}")
    return controls


def _state_change(base: bytes, offset: int, payload: bytes, *, repair: bool = True) -> bytes:
    value = bytearray(base)
    value[offset : offset + len(payload)] = payload
    if repair and len(value) == prec1.STATE_BYTES:
        value[112:128] = hashlib.sha256(value[:112]).digest()[:16]
    return bytes(value)


def _state_controls() -> list[Control]:
    policy = prec1.parse(prec1.canonical_bundle())
    base = prec1.encode_state(prec1.canonical_state(policy))
    controls: list[Control] = []

    def add(name: str, data: bytes) -> None:
        controls.append(
            Control(f"NEG-N5-PREC1-STATE-{name}", "state_parse", f"S:{data.hex().upper()}", prec1.parse_state_result(data))
        )

    add("TRUNCATED", base[:80])
    add("TRAILING", base + b"\0")
    add("MAGIC", _state_change(base, 0, b"BADSTAT1"))
    add("MAJOR", _state_change(base, 8, struct.pack("<H", 2)))
    add("MINOR", _state_change(base, 10, struct.pack("<H", 1)))
    add("SIZE", _state_change(base, 12, struct.pack("<H", 120)))
    add("FLAGS", _state_change(base, 14, struct.pack("<H", 1 << 15)))
    add("GENERATION", _state_change(base, 16, struct.pack("<Q", 0)))
    add("FLOOR", _state_change(base, 24, struct.pack("<Q", 0)))
    add("ACTIVE-ZERO", _state_change(base, 32, b"\0"))
    add("PENDING-HIGH", _state_change(base, 33, b"\3"))
    add("PENDING-ACTIVE", _state_change(base, 33, b"\2"))
    add("KNOWN-GOOD-ZERO", _state_change(base, 34, b"\0"))
    add("KNOWN-GOOD-MASK", _state_change(base, 34, b"\7"))
    add("UNBOOTABLE-MASK", _state_change(base, 35, b"\4"))
    add("SAFE-MASK", _state_change(base, 38, b"\4"))
    add("MASK-CONFLICT", _state_change(base, 35, b"\2"))
    add("ACTIVE-NOT-KNOWN", _state_change(base, 34, b"\1"))
    add("ATTEMPTS-A", _state_change(base, 36, b"\10"))
    add("ATTEMPTS-B", _state_change(base, 37, b"\10"))
    add("MODE", _state_change(base, 39, b"\7"))
    add("FAILURE", _state_change(base, 40, struct.pack("<H", 11)))
    add("FAILURE-RESERVED", _state_change(base, 42, b"\1"))
    add("SUCCESS-SLOT", _state_change(base, 70, b"\0"))
    add("SUCCESS-GENERATION-ZERO", _state_change(base, 72, struct.pack("<Q", 0)))
    add("SUCCESS-GENERATION-FUTURE", _state_change(base, 72, struct.pack("<Q", 12)))
    add("POLICY-VERSION", _state_change(base, 80, struct.pack("<Q", 0)))
    add("STORE-EPOCH", _state_change(base, 88, struct.pack("<Q", 0)))
    add("EVIDENCE-SEQUENCE", _state_change(base, 96, struct.pack("<Q", 0)))
    add("INFLIGHT", _state_change(base, 14, struct.pack("<H", prec1.STATE_INFLIGHT)))
    add("RESERVED", _state_change(base, 104, struct.pack("<Q", 1)))
    add("CHECKSUM", _state_change(base, 112, b"\0", repair=False))
    if len(controls) != 32:
        raise QualificationError(f"expected 32 state controls, found {len(controls)}")
    return controls


def _decision_transport(decision: prec1.BootDecision) -> str:
    return f"{prec1.decision_summary(decision)};state={prec1.encode_state(decision.state).hex().upper()}"


def _transition_result(
    policy: prec1.Bundle,
    state: prec1.RecoveryState,
    requested: int,
    presence: bool,
    nonce: int,
    authenticated: bool,
    writable: bool,
) -> str:
    try:
        return _decision_transport(
            prec1.select_boot(
                policy,
                state,
                requested,
                physical_presence=presence,
                boot_nonce=nonce,
                state_authenticated=authenticated,
                state_writable=writable,
            )
        )
    except prec1.RecoveryError as error:
        return f"ERR:{error.code}"


def _transition_request(
    policy: prec1.Bundle,
    state: prec1.RecoveryState,
    requested: int,
    presence: bool,
    nonce: int,
    authenticated: bool,
    writable: bool,
) -> str:
    return (
        f"T:{requested}:{int(presence)}:{nonce}:{int(authenticated)}:{int(writable)}:"
        f"{policy.raw.hex().upper()}:{prec1.encode_state(state).hex().upper()}"
    )


def _success_result(policy: prec1.Bundle, state: prec1.RecoveryState, mode: str) -> str:
    receipt = prec1.SuccessReceipt(True, state.inflight_generation, state.inflight_slot, state.inflight_mode, state.boot_nonce)
    if mode == "auth":
        receipt = dataclasses.replace(receipt, authenticated=False)
    elif mode == "generation":
        receipt = dataclasses.replace(receipt, generation=receipt.generation + 1)
    elif mode == "slot":
        receipt = dataclasses.replace(receipt, slot=3 - receipt.slot)
    elif mode == "mode":
        receipt = dataclasses.replace(receipt, mode=2 if receipt.mode == 1 else 1)
    elif mode == "nonce":
        receipt = dataclasses.replace(receipt, boot_nonce=receipt.boot_nonce + 1)
    try:
        next_state = prec1.report_boot_success(policy, state, receipt)
        return f"{prec1.state_summary(next_state)};state={prec1.encode_state(next_state).hex().upper()}"
    except prec1.RecoveryError as error:
        return f"ERR:{error.code}"


def _failure_result(policy: prec1.Bundle, state: prec1.RecoveryState, failure_id: int, authenticated: bool) -> str:
    try:
        decision = prec1.report_boot_failure(policy, state, failure_id, authenticated=authenticated)
        state_text = prec1.state_summary(decision.state).removeprefix("OK;")
        return f"OK;action={decision.action};{state_text};state={prec1.encode_state(decision.state).hex().upper()}"
    except prec1.RecoveryError as error:
        return f"ERR:{error.code}"


def _transition_controls() -> list[Control]:
    policy = prec1.parse(prec1.canonical_bundle())
    base = prec1.canonical_state(policy)
    controls: list[Control] = []

    def add_transition(name: str, state: prec1.RecoveryState, requested: int, presence: bool, nonce: int, auth: bool, writable: bool) -> None:
        controls.append(
            Control(
                f"CTRL-N5-PREC1-{name}",
                "transition",
                _transition_request(policy, state, requested, presence, nonce, auth, writable),
                _transition_result(policy, state, requested, presence, nonce, auth, writable),
            )
        )

    add_transition("STATE-AUTH", base, 1, False, 1, False, True)
    inflight = prec1.select_boot(policy, base, 1, boot_nonce=2).state
    add_transition("INFLIGHT-RESELECT", inflight, 1, False, 3, True, True)
    add_transition("NONCE-ZERO", base, 1, False, 0, True, True)
    add_transition("FIRMWARE-PRESENCE", base, prec1.MODE_FIRMWARE, False, 4, True, True)
    add_transition("STATE-WRITE-FAILURE", base, 1, False, 5, True, False)
    add_transition("RECOVERY-REQUEST", dataclasses.replace(base, flags=prec1.STATE_RECOVERY_REQUESTED), 1, False, 6, True, True)
    add_transition("SAFE-REQUEST", dataclasses.replace(base, flags=prec1.STATE_SAFE_REQUESTED), 1, False, 7, True, True)
    add_transition("CANDIDATE-DECREMENT", base, 1, False, 8, True, True)
    add_transition("ATTEMPT-EXHAUSTED", dataclasses.replace(base, attempts_a=0), 1, False, 9, True, True)
    add_transition("NO-ELIGIBLE-SLOT", dataclasses.replace(base, minimum_secure_version=3), 1, False, 10, True, True)
    add_transition(
        "SAFE-LOOP-BOUND",
        dataclasses.replace(base, flags=prec1.STATE_SAFE_REQUESTED, safe_attempted_mask=0b10),
        1,
        False,
        11,
        True,
        True,
    )
    add_transition("PREVIOUS", base, prec1.MODE_PREVIOUS, False, 12, True, True)
    add_transition("DIAGNOSTIC", base, prec1.MODE_DIAGNOSTIC, False, 13, True, True)
    add_transition("FIRMWARE", base, prec1.MODE_FIRMWARE, True, 14, True, True)

    selected = prec1.select_boot(policy, base, 1, boot_nonce=15).state
    for mode in ("auth", "generation", "slot", "mode", "nonce", "qualified"):
        controls.append(
            Control(
                f"CTRL-N5-PREC1-SUCCESS-{mode.upper()}",
                "success_receipt",
                f"U:{mode}:{policy.raw.hex().upper()}:{prec1.encode_state(selected).hex().upper()}",
                _success_result(policy, selected, mode),
            )
        )
    controls.append(
        Control(
            "CTRL-N5-PREC1-FAILURE-AUTH",
            "failure_receipt",
            f"F:7:0:{policy.raw.hex().upper()}:{prec1.encode_state(selected).hex().upper()}",
            _failure_result(policy, selected, 7, False),
        )
    )
    controls.append(
        Control(
            "CTRL-N5-PREC1-FAILURE-NO-INFLIGHT",
            "failure_receipt",
            f"F:7:1:{policy.raw.hex().upper()}:{prec1.encode_state(base).hex().upper()}",
            _failure_result(policy, base, 7, True),
        )
    )
    controls.append(
        Control(
            "CTRL-N5-PREC1-FAILURE-ID",
            "failure_receipt",
            f"F:11:1:{policy.raw.hex().upper()}:{prec1.encode_state(selected).hex().upper()}",
            _failure_result(policy, selected, 11, True),
        )
    )
    exhausted = prec1.select_boot(policy, dataclasses.replace(base, attempts_a=1), 1, boot_nonce=16).state
    controls.append(
        Control(
            "CTRL-N5-PREC1-FAILURE-EXHAUSTED",
            "failure_receipt",
            f"F:7:1:{policy.raw.hex().upper()}:{prec1.encode_state(exhausted).hex().upper()}",
            _failure_result(policy, exhausted, 7, True),
        )
    )
    if len(controls) != 24:
        raise QualificationError(f"expected 24 transition controls, found {len(controls)}")
    return controls


def _activation_controls() -> list[Control]:
    policy = prec1.parse(prec1.canonical_bundle())
    controls = []
    for mode in prec1.ACTIVATION_MODES:
        try:
            prec1.authorize_activation(policy, prec1.activation_context(mode, policy))
            expected = "OK:activation"
        except prec1.RecoveryError as error:
            expected = f"ERR:{error.code}"
        controls.append(
            Control(
                f"NEG-N5-PREC1-ACTIVATION-{mode.upper()}",
                "activation",
                f"A:{mode}:{policy.raw.hex().upper()}",
                expected,
            )
        )
    if len(controls) != 22:
        raise QualificationError(f"expected 22 activation controls, found {len(controls)}")
    return controls


def _controls() -> list[Control]:
    controls = _policy_controls() + _state_controls() + _transition_controls() + _activation_controls()
    if len(controls) != 144 or len({item.control_id for item in controls}) != 144:
        raise QualificationError("PREC1 control registry must contain exactly 144 unique controls")
    return controls


def _qualify_controls(probe: Path) -> list[dict[str, Any]]:
    controls = _controls()
    observed = _probe_lines(probe, [control.request for control in controls])
    results = []
    for control, actual in zip(controls, observed, strict=True):
        if actual != control.expected:
            raise QualificationError(f"{control.control_id} mismatch: Python={control.expected}, Rust={actual}")
        results.append(
            {
                "id": control.control_id,
                "surface": control.surface,
                "status": "pass",
                "rust_python_result": actual,
            }
        )
    return results


def _qualify_golden(probe: Path, golden: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[str] = []
    expected: list[str] = []
    for item in golden["vectors"]:
        requests.extend((f"P:{item['policy_hex']}", f"S:{item['state_hex']}"))
        expected.extend((item["policy_summary"], item["state_summary"]))
    observed = _probe_lines(probe, requests)
    if observed != expected:
        raise QualificationError("PREC1 golden policy/state semantic mismatch")
    results = []
    for item in golden["vectors"]:
        policy = prec1.parse(bytes.fromhex(item["policy_hex"]))
        state = prec1.parse_state(bytes.fromhex(item["state_hex"]), policy)
        decision = prec1.select_boot(policy, state, item["requested_mode"], boot_nonce=item["boot_nonce"])
        if prec1.decision_summary(decision) != item["decision_summary"] or prec1.encode_state(decision.state).hex().upper() != item["next_state_hex"]:
            raise QualificationError(f"PREC1 golden transition mismatch for {item['id']}")
        results.append(
            {
                "id": item["id"],
                "status": "pass",
                "policy_byte_count": item["policy_byte_count"],
                "policy_sha256": item["policy_sha256"],
                "state_byte_count": item["state_byte_count"],
                "state_sha256": item["state_sha256"],
                "policy_state_and_transition_matched": True,
            }
        )
    return results


def _mutated_policy(rng: random.Random, case: int) -> bytes:
    base = bytearray((prec1.minimal_bundle(), prec1.canonical_bundle(), prec1.versioned_bundle())[case % 3])
    operation = rng.randrange(5)
    if operation == 0:
        del base[rng.randrange(len(base)) :]
    elif operation == 1:
        base.append(rng.randrange(256))
    else:
        for _ in range(1 + rng.randrange(4)):
            position = rng.randrange(len(base))
            base[position] ^= 1 << rng.randrange(8)
    return bytes(base)


def _mutated_state(rng: random.Random, case: int) -> bytes:
    policy_bytes = (prec1.minimal_bundle(), prec1.canonical_bundle(), prec1.versioned_bundle())[case % 3]
    policy = prec1.parse(policy_bytes)
    state = prec1.minimal_state(policy) if case % 3 == 0 else prec1.canonical_state(policy)
    base = bytearray(prec1.encode_state(state))
    operation = rng.randrange(5)
    if operation == 0:
        del base[rng.randrange(len(base)) :]
    elif operation == 1:
        base.append(rng.randrange(256))
    else:
        for _ in range(1 + rng.randrange(3)):
            position = rng.randrange(len(base))
            base[position] ^= 1 << rng.randrange(8)
    return bytes(base)


def _qualify_parser_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(DIFFERENTIAL_SEED)
    requests = []
    expected = []
    policy_cases = PARSER_DIFFERENTIAL_CASES // 2
    for case in range(policy_cases):
        data = _mutated_policy(rng, case)
        requests.append(f"P:{data.hex().upper()}")
        expected.append(prec1.parse_result(data))
    for case in range(PARSER_DIFFERENTIAL_CASES - policy_cases):
        data = _mutated_state(rng, case)
        requests.append(f"S:{data.hex().upper()}")
        expected.append(prec1.parse_state_result(data))
    observed = _probe_lines(probe, requests)
    mismatches = [(index, left, right) for index, (left, right) in enumerate(zip(expected, observed, strict=True)) if left != right]
    if mismatches:
        index, left, right = mismatches[0]
        raise QualificationError(f"PREC1 parser differential mismatch {index}: Python={left}, Rust={right}")
    return {
        "campaign_id": "PREC1-DIFF-1",
        "seed": f"0x{DIFFERENTIAL_SEED:X}",
        "generator": "deterministic policy and state truncation, extension, and one-to-four-byte bit mutation",
        "case_count": len(requests),
        "policy_case_count": policy_cases,
        "state_case_count": len(requests) - policy_cases,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def _qualify_transition_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(TRANSITION_SEED)
    policy = prec1.parse(prec1.canonical_bundle())
    template = prec1.canonical_state(policy)
    requests = []
    expected = []
    accepted = 0
    rejected = 0
    for case in range(TRANSITION_DIFFERENTIAL_CASES):
        active = 1 + rng.randrange(2)
        has_pending = bool(rng.randrange(2))
        pending = 3 - active if has_pending else 0
        known_good = 1 << (active - 1)
        if not has_pending and rng.randrange(2):
            known_good = 0b11
        flag_choice = rng.randrange(4)
        flags = 0
        if flag_choice == 1:
            flags = prec1.STATE_SAFE_REQUESTED
        elif flag_choice == 2:
            flags = prec1.STATE_RECOVERY_REQUESTED
        state = dataclasses.replace(
            template,
            flags=flags,
            generation=policy.state_generation_floor + case,
            active_slot=active,
            pending_slot=pending,
            known_good_mask=known_good,
            attempts_a=rng.randrange(policy.max_attempts + 1),
            attempts_b=rng.randrange(policy.max_attempts + 1),
            safe_attempted_mask=rng.randrange(4),
            current_mode=0,
            last_failure=rng.randrange(prec1.FAILURE_COUNT + 1),
            boot_nonce=0,
            inflight_generation=0,
            inflight_slot=0,
            inflight_mode=0,
            last_success_slot=active,
            last_success_generation=policy.state_generation_floor + case,
            evidence_sequence=1 + case,
            raw=b"",
        )
        state = prec1.parse_state(prec1.encode_state(state), policy)
        requested = rng.randrange(7)
        presence = bool(rng.randrange(2))
        nonce = case + 1
        result = _transition_result(policy, state, requested, presence, nonce, True, True)
        requests.append(_transition_request(policy, state, requested, presence, nonce, True, True))
        expected.append(result)
        accepted += int(result.startswith("OK;"))
        rejected += int(result.startswith("ERR:"))
    observed = _probe_lines(probe, requests)
    for index, (left, right) in enumerate(zip(expected, observed, strict=True)):
        if left != right:
            raise QualificationError(f"PREC1 transition differential mismatch {index}: Python={left}, Rust={right}")
    if accepted == 0 or rejected == 0:
        raise QualificationError("PREC1 transition campaign must cover acceptance and rejection")
    return {
        "campaign_id": "PREC1-TRANSITION-DIFF-1",
        "seed": f"0x{TRANSITION_SEED:X}",
        "case_count": len(requests),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = prec1.read_json(ROOT / prec1.CONTRACT_RELATIVE)
    golden = prec1.read_json(ROOT / prec1.GOLDEN_RELATIVE)
    errors = prec1.contract_errors(contract) + prec1.golden_errors(golden)
    if errors:
        raise QualificationError("; ".join(errors))
    with tempfile.TemporaryDirectory(prefix="pooleos-prec1-") as temporary:
        probe, validators = _build_validators(toolchain_root, Path(temporary))
        golden_results = _qualify_golden(probe, golden)
        controls = _qualify_controls(probe)
        parser_diff = _qualify_parser_differential(probe)
        transition_diff = _qualify_transition_differential(probe)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_recovery_readiness",
        "status_date": "2026-07-18",
        "status": "pass_single_host_synthetic_non_promoting",
        "contract_id": prec1.CONTRACT_ID,
        "selected_move_id": "N5-RECOVERY-SEMANTICS-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.6": "partial", "N5.9": "partial", "N21": "not_started"},
        "bindings": {
            "contract": prec1.file_binding(ROOT / prec1.CONTRACT_RELATIVE),
            "contract_schema": prec1.file_binding(ROOT / prec1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": prec1.file_binding(ROOT / prec1.GOLDEN_RELATIVE),
            "golden_schema": prec1.file_binding(ROOT / prec1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": prec1.file_binding(ROOT / prec1.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": [prec1.file_binding(ROOT / path) for path in prec1.IMPLEMENTATION_INPUTS],
        },
        "validator_qualification": validators,
        "golden_vectors": golden_results,
        "negative_controls": controls,
        "differential_fuzz": parser_diff,
        "transition_qualification": transition_diff,
        "activation_qualification": {
            "status": "pass",
            "synthetic_all_true_result": "OK:activation",
            "synthetic_all_true_context_is_trust_evidence": False,
            "current_unsigned_development_activation_allowed": False,
            "individual_rejecting_context_count": len(prec1.ACTIVATION_MODES),
        },
        "claims": prec1.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 3,
            "rust_host_tests_total": 3,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "golden_vectors_matched": 3,
            "golden_vectors_total": 3,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "parser_differential_cases": parser_diff["case_count"],
            "transition_differential_cases": transition_diff["case_count"],
            "differential_mismatches": 0,
            "development_activation_denied": True,
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PREC1 before declaring a stable recovery ABI.",
            "Define the authenticated UEFI variable GUID, names, attributes, and transport semantics.",
            "Implement monotonic authenticated state persistence and out-of-resource failure handling.",
            "Prove that any file fallback carries non-security state only.",
            "Sign PSM1, PBART1, PREC1, and recovery components under an approved trust root.",
            "Implement PREC1 parsing and enforcement inside PooleBoot.",
            "Record selected recovery mode, slot, generation, nonce, and failure in the live PBP1 handoff.",
            "Implement PooleKernel-mediated recovery capabilities without ambient firmware, disk, or network authority.",
            "Build the offline PooleRecovery executable, UI, evidence export, rollback, repair, and reinstall paths.",
            "Qualify encrypted-volume unlock and destructive-action physical-presence policy.",
            "Run power-loss, corrupted-state, exhausted-variable-store, and target-firmware fault injection.",
            "Reproduce validators on an independent builder and target firmware.",
            "Complete signed physical-media, production ISO, and N5-N39 exit gates.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    readiness = make_readiness(args.toolchain_root.resolve())
    prec1.write_json(readiness, args.out)
    errors = prec1.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    print(
        f"PREC1 qualification passed: tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"parser_differential={readiness['summary']['parser_differential_cases']}; "
        f"transition_differential={readiness['summary']['transition_differential_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
