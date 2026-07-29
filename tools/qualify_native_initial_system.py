#!/usr/bin/env python3
"""Qualify PINIT1 validators, activation gates, hostile controls, and differential cases."""

from __future__ import annotations

import argparse
import dataclasses
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

from runtime import native_initial_system as pinit1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / pinit1.READINESS_RELATIVE
DIFFERENTIAL_CASES = 16_384
DIFFERENTIAL_SEED = 0x5049_4E49_5431


class QualificationError(RuntimeError):
    """Raised when PINIT1 qualification fails closed."""


@dataclass(frozen=True)
class Control:
    control_id: str
    surface: str
    data: bytes
    mode: str = ""


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
            f"command failed ({completed.returncode}): {' '.join(command[:6])}\n"
            + "\n".join(output.splitlines()[-60:])
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
    artifacts = sorted((target_dir / target / "release" / "deps").glob("libpoole_initial_system-*.rlib"))
    if len(artifacts) != 1:
        raise QualificationError(f"expected one PINIT1 rlib for {target}, found {len(artifacts)}")
    return artifacts[0]


def _build_validators(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    host_target = "x86_64-pc-windows-msvc"
    test_target = temporary_root / "host-tests"
    test_output = _run(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-initial-system",
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
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test_output)
    if match is None or int(match.group(1)) != 3:
        raise QualificationError("expected exactly three PINIT1 Rust host tests")

    target_results = []
    for target in ("x86_64-unknown-uefi", "x86_64-unknown-none"):
        target_dir = temporary_root / f"validator-{target}"
        _run(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "poole-initial-system",
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
        target_results.append(
            {
                "target": target,
                "status": "pass",
                "byte_count": artifact.stat().st_size,
                "sha256": pinit1.sha256_bytes(artifact.read_bytes()),
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
            "poole-initial-system",
            "--bin",
            "pinit1-probe",
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
    probe = probe_target / host_target / "release" / "pinit1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PINIT1 host probe is missing")
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    return probe, {
        "rustc_version_sha256": pinit1.sha256_bytes(version.encode("utf-8")),
        "rust_host_target": host_target,
        "rust_host_test_count": 3,
        "rust_host_test_pass_count": 3,
        "no_std_target_builds": target_results,
        "host_probe_byte_count": probe.stat().st_size,
        "host_probe_artifact_identity_recorded": False,
        "host_probe_role": "ephemeral host-only differential transport",
    }


def _repair_body(value: bytearray) -> None:
    if len(value) >= pinit1.HEADER_BYTES:
        value[120:152] = __import__("hashlib").sha256(value[pinit1.HEADER_BYTES :]).digest()


def _changed(base: bytes, offset: int, payload: bytes, *, repair: bool = False) -> bytes:
    value = bytearray(base)
    value[offset : offset + len(payload)] = payload
    if repair:
        _repair_body(value)
    return bytes(value)


def _u16(base: bytes, offset: int, value: int, *, repair: bool = False) -> bytes:
    return _changed(base, offset, struct.pack("<H", value), repair=repair)


def _u32(base: bytes, offset: int, value: int, *, repair: bool = False) -> bytes:
    return _changed(base, offset, struct.pack("<I", value), repair=repair)


def _u64(base: bytes, offset: int, value: int, *, repair: bool = False) -> bytes:
    return _changed(base, offset, struct.pack("<Q", value), repair=repair)


def _multi(base: bytes, changes: list[tuple[int, bytes]]) -> bytes:
    value = bytearray(base)
    for offset, payload in changes:
        value[offset : offset + len(payload)] = payload
    _repair_body(value)
    return bytes(value)


def _parser_controls() -> list[Control]:
    base = pinit1.canonical_bundle()
    component = 192
    service = 432
    dependency = 720
    resource = 768
    capability = 960
    string_offset = 1488
    blob_offset = 1640
    controls: list[Control] = []

    def add(control_id: str, data: bytes) -> None:
        controls.append(Control(control_id, "parse", data))

    add("NEG-N5-PINIT1-EMPTY", b"")
    add("NEG-N5-PINIT1-TRUNCATED-HEADER", base[:100])
    add("NEG-N5-PINIT1-OVERSIZED", b"\0" * (pinit1.MAX_BUNDLE_BYTES + 1))
    add("NEG-N5-PINIT1-MAGIC", _changed(base, 0, b"BADINIT1"))
    add("NEG-N5-PINIT1-MAJOR-VERSION", _u16(base, 8, 2))
    add("NEG-N5-PINIT1-MINOR-VERSION", _u16(base, 10, 1))
    add("NEG-N5-PINIT1-HEADER-BYTES", _u16(base, 12, 184))
    add("NEG-N5-PINIT1-ALIGNMENT", _u16(base, 14, 16))
    add("NEG-N5-PINIT1-TOTAL-SIZE", _u32(base, 16, len(base) + 1))
    add("NEG-N5-PINIT1-FLAGS-MISSING", _u32(base, 20, pinit1.REQUIRED_FLAGS & ~1))
    add("NEG-N5-PINIT1-FLAGS-UNKNOWN", _u32(base, 20, pinit1.REQUIRED_FLAGS | (1 << 31)))
    add("NEG-N5-PINIT1-BUNDLE-VERSION-ZERO", _u64(base, 24, 0))
    add("NEG-N5-PINIT1-SECURE-VERSION-ZERO", _u64(base, 32, 0))
    add("NEG-N5-PINIT1-ROLLBACK-FLOOR", _u64(base, 32, 2))
    add("NEG-N5-PINIT1-ROOT-ZERO", _u32(base, 40, 0))
    add("NEG-N5-PINIT1-ROOT-OUT-OF-RANGE", _u32(base, 40, 4))
    add("NEG-N5-PINIT1-BOOT-MODES-ZERO", _u32(base, 44, 0))
    add("NEG-N5-PINIT1-BOOT-MODES-UNKNOWN", _u32(base, 44, pinit1.KNOWN_BOOT_MODES | 16))
    add("NEG-N5-PINIT1-KERNEL-ABI-ZERO", _u16(base, 48, 0))
    add("NEG-N5-PINIT1-PBP-ABI-ZERO", _u16(base, 52, 0))
    add("NEG-N5-PINIT1-HEADER-RESERVED", _changed(base, 152, b"\x01"))
    add("NEG-N5-PINIT1-COMPONENT-COUNT-ZERO", _u16(base, 56, 0))
    add("NEG-N5-PINIT1-SERVICE-COUNT-HIGH", _u16(base, 58, pinit1.MAX_SERVICES + 1))
    add("NEG-N5-PINIT1-DEPENDENCY-COUNT-HIGH", _u16(base, 60, pinit1.MAX_DEPENDENCIES + 1))
    add("NEG-N5-PINIT1-RESOURCE-COUNT-ZERO", _u16(base, 62, 0))
    add("NEG-N5-PINIT1-CAPABILITY-COUNT-ZERO", _u16(base, 64, 0))
    add("NEG-N5-PINIT1-STRING-BYTES-ZERO", _u32(base, 92, 0))
    add("NEG-N5-PINIT1-BLOB-BYTES-ZERO", _u32(base, 100, 0))
    add("NEG-N5-PINIT1-BLOB-BYTES-HIGH", _u32(base, 100, pinit1.MAX_COMPONENT_BLOB_BYTES + 1))
    add("NEG-N5-PINIT1-TABLE-OFFSET", _u32(base, 72, 440))
    add("NEG-N5-PINIT1-BLOB-OFFSET", _u32(base, 96, blob_offset + 8))
    add("NEG-N5-PINIT1-PADDING", _changed(base, 1638, b"\x01", repair=True))
    add("NEG-N5-PINIT1-BODY-DIGEST", _changed(base, 120, b"\x00"))

    add("NEG-N5-PINIT1-COMPONENT-ID", _u32(base, component, 2, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-KIND", _u16(base, component + 4, 9, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-FLAGS", _u16(base, component + 6, 3, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-FORMAT", _changed(base, component + 16, b"OTHER1\0\0", repair=True))
    add("NEG-N5-PINIT1-COMPONENT-IMAGE-SIZE", _u32(base, component + 32, 0, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-ALIGNMENT-ZERO", _u32(base, component + 36, 0, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-ALIGNMENT-NONPOWER", _u32(base, component + 36, 3, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-BLOB-OFFSET", _u32(base, component + 24, 8, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-BLOB-ZERO", _u32(base, component + 28, 0, repair=True))
    add("NEG-N5-PINIT1-COMPONENT-DIGEST", _changed(base, blob_offset, b"X", repair=True))
    add("NEG-N5-PINIT1-COMPONENT-RESERVED", _changed(base, component + 72, b"\x01", repair=True))
    add("NEG-N5-PINIT1-COMPONENT-NAME", _u32(base, component + 8, 150, repair=True))
    add(
        "NEG-N5-PINIT1-COMPONENT-NAME-DUPLICATE",
        _multi(
            base,
            [
                (component + pinit1.COMPONENT_BYTES + 8, base[component + 8 : component + 14]),
            ],
        ),
    )
    add("NEG-N5-PINIT1-STRING-TABLE", _changed(base, string_offset, b"z", repair=True))

    service2 = service + pinit1.SERVICE_BYTES
    service3 = service + 2 * pinit1.SERVICE_BYTES
    add("NEG-N5-PINIT1-SERVICE-ID", _u32(base, service, 2, repair=True))
    add("NEG-N5-PINIT1-SERVICE-COMPONENT", _u32(base, service, 0, repair=True))
    add("NEG-N5-PINIT1-SERVICE-FLAGS-UNKNOWN", _u16(base, service2 + 14, 1 << 15, repair=True))
    add(
        "NEG-N5-PINIT1-SERVICE-CRITICAL-OPTIONAL",
        _u16(base, service2 + 14, pinit1.SERVICE_CRITICAL | pinit1.SERVICE_STATELESS, repair=True),
    )
    add(
        "NEG-N5-PINIT1-SERVICE-REQUIRED-DEGRADED",
        _u16(
            base,
            service2 + 14,
            pinit1.SERVICE_REQUIRED | pinit1.SERVICE_ALLOW_DEGRADED | pinit1.SERVICE_STATELESS,
            repair=True,
        ),
    )
    add("NEG-N5-PINIT1-SERVICE-START-TIMEOUT", _u32(base, service + 16, 0, repair=True))
    add("NEG-N5-PINIT1-SERVICE-STOP-TIMEOUT", _u32(base, service + 20, 0, repair=True))
    add("NEG-N5-PINIT1-SERVICE-RESTART-POLICY", _u16(base, service2 + 24, 3, repair=True))
    add("NEG-N5-PINIT1-SERVICE-RESTART-PARAMETERS", _u32(base, service + 32, 1, repair=True))
    add("NEG-N5-PINIT1-SERVICE-FAILURE-POLICY", _u16(base, service2 + 26, 0, repair=True))
    add(
        "NEG-N5-PINIT1-SERVICE-REQUIRED-FAILURE",
        _u16(base, service3 + 26, pinit1.FAILURE_CONTINUE_DEGRADED, repair=True),
    )
    add("NEG-N5-PINIT1-SERVICE-READINESS-POLICY", _u16(base, service + 28, 2, repair=True))
    add("NEG-N5-PINIT1-SERVICE-SHUTDOWN-POLICY", _u16(base, service + 30, 0, repair=True))
    add("NEG-N5-PINIT1-SERVICE-HEALTH-TIMEOUT", _u32(base, service + 48, 0, repair=True))
    add("NEG-N5-PINIT1-SERVICE-READY-RESOURCE", _u32(base, service + 52, 1, repair=True))
    add("NEG-N5-PINIT1-SERVICE-STATE-SCHEMA", _u32(base, service2 + 64, 1, repair=True))
    add("NEG-N5-PINIT1-SERVICE-RESERVED", _changed(base, service + 68, b"\x01", repair=True))

    dependency2 = dependency + pinit1.DEPENDENCY_BYTES
    dependency3 = dependency + 2 * pinit1.DEPENDENCY_BYTES
    add("NEG-N5-PINIT1-DEPENDENCY-ORDER", _u32(base, dependency, 3, repair=True))
    add("NEG-N5-PINIT1-DEPENDENCY-SELF", _u32(base, dependency + 4, 2, repair=True))
    add("NEG-N5-PINIT1-DEPENDENCY-KIND", _u16(base, dependency + 8, 3, repair=True))
    add("NEG-N5-PINIT1-DEPENDENCY-CYCLE", _u32(base, dependency + 4, 3, repair=True))
    add(
        "NEG-N5-PINIT1-DEPENDENCY-REACHABILITY",
        _u16(base, dependency2 + 8, pinit1.DEPENDENCY_WEAK, repair=True),
    )
    add(
        "NEG-N5-PINIT1-DEPENDENCY-AVAILABILITY",
        _multi(
            base,
            [
                (service2 + 14, struct.pack("<H", pinit1.SERVICE_STATELESS)),
                (dependency3 + 8, struct.pack("<H", pinit1.DEPENDENCY_STRONG)),
            ],
        ),
    )
    add("NEG-N5-PINIT1-STARTUP-RANK", _u16(base, service3 + 62, 1, repair=True))

    resource2 = resource + pinit1.RESOURCE_BYTES
    resource3 = resource + 2 * pinit1.RESOURCE_BYTES
    resource4 = resource + 3 * pinit1.RESOURCE_BYTES
    add("NEG-N5-PINIT1-RESOURCE-ID", _u32(base, resource, 2, repair=True))
    add("NEG-N5-PINIT1-RESOURCE-PROVIDER", _u32(base, resource, 4, repair=True))
    add("NEG-N5-PINIT1-RESOURCE-KIND", _u16(base, resource + 14, 9, repair=True))
    add("NEG-N5-PINIT1-RESOURCE-FLAGS-UNKNOWN", _u32(base, resource + 16, 1 << 31, repair=True))
    add(
        "NEG-N5-PINIT1-RESOURCE-NOT-REVOCABLE",
        _u32(base, resource + 16, pinit1.RESOURCE_REQUIRED | pinit1.RESOURCE_ZERO_ON_REVOKE | pinit1.RESOURCE_EXCLUSIVE, repair=True),
    )
    add(
        "NEG-N5-PINIT1-RESOURCE-SHARE-EXCLUSIVE",
        _u32(
            base,
            resource2 + 16,
            pinit1.RESOURCE_REQUIRED | pinit1.RESOURCE_REVOCABLE | pinit1.RESOURCE_SHAREABLE | pinit1.RESOURCE_EXCLUSIVE,
            repair=True,
        ),
    )
    add(
        "NEG-N5-PINIT1-RESOURCE-ZERO-ON-ENDPOINT",
        _u32(
            base,
            resource3 + 16,
            pinit1.RESOURCE_REQUIRED | pinit1.RESOURCE_REVOCABLE | pinit1.RESOURCE_ZERO_ON_REVOKE | pinit1.RESOURCE_EXCLUSIVE,
            repair=True,
        ),
    )
    add("NEG-N5-PINIT1-RESOURCE-MINIMUM-ZERO", _u64(base, resource + 24, 0, repair=True))
    add("NEG-N5-PINIT1-RESOURCE-MAXIMUM-LIMIT", _u64(base, resource3 + 32, 4097, repair=True))
    add("NEG-N5-PINIT1-RESOURCE-GENERATION", _u32(base, resource + 40, 0, repair=True))

    capability4 = capability + 3 * pinit1.CAPABILITY_BYTES
    capability10 = capability + 9 * pinit1.CAPABILITY_BYTES
    capability11 = capability + 10 * pinit1.CAPABILITY_BYTES
    add("NEG-N5-PINIT1-CAPABILITY-ID", _u32(base, capability, 2, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-PARENT-FORWARD", _u32(base, capability4 + 4, 5, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-HOLDER", _u32(base, capability + 8, 0, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-RESOURCE", _u32(base, capability + 12, 0, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-RIGHTS-ZERO", _u64(base, capability + 16, 0, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-RIGHTS-UNKNOWN", _u64(base, capability + 16, 1 << 16, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-FLAGS-UNKNOWN", _u32(base, capability + 24, 1 << 31, repair=True))
    add(
        "NEG-N5-PINIT1-CAPABILITY-NOT-REVOCABLE",
        _u32(base, capability + 24, pinit1.CAP_DERIVABLE | pinit1.CAP_LIFECYCLE_BOUND, repair=True),
    )
    add(
        "NEG-N5-PINIT1-CAPABILITY-NOT-LIFECYCLE",
        _u32(base, capability + 24, pinit1.CAP_REVOCABLE | pinit1.CAP_DERIVABLE, repair=True),
    )
    add("NEG-N5-PINIT1-CAPABILITY-REVOKE-GROUP", _u32(base, capability + 28, 0, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-LEASE", _u32(base, capability + 32, 1, repair=True))
    add(
        "NEG-N5-PINIT1-CAPABILITY-DERIVATION-LIMIT",
        _u16(base, capability + 36, pinit1.MAX_CAPABILITIES + 1, repair=True),
    )
    add("NEG-N5-PINIT1-CAPABILITY-AVAILABILITY", _u16(base, capability + 38, 3, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-SOURCE", _u32(base, capability + 8, 2, repair=True))
    add(
        "NEG-N5-PINIT1-CAPABILITY-ATTENUATION-RIGHTS",
        _multi(
            base,
            [
                (capability + 16, struct.pack("<Q", 7)),
                (capability4 + 16, struct.pack("<Q", 15)),
            ],
        ),
    )
    add("NEG-N5-PINIT1-CAPABILITY-ATTENUATION-RESOURCE", _u32(base, capability4 + 12, 2, repair=True))
    add("NEG-N5-PINIT1-CAPABILITY-REVOCATION", _u32(base, capability4 + 28, 2, repair=True))
    add(
        "NEG-N5-PINIT1-CAPABILITY-AVAILABILITY-UPGRADE",
        _u16(base, capability11 + 38, pinit1.AVAILABILITY_REQUIRED, repair=True),
    )
    add(
        "NEG-N5-PINIT1-CAPABILITY-ROUTE",
        _multi(
            base,
            [
                (resource4 + 4, struct.pack("<I", 3)),
                (capability10 + 8, struct.pack("<I", 3)),
                (capability11 + 8, struct.pack("<I", 2)),
            ],
        ),
    )
    add("NEG-N5-PINIT1-SERVICE-CAPABILITY-BUDGET", _u16(base, service + 56, 4, repair=True))
    add("NEG-N5-PINIT1-SERVICE-RESOURCE-BUDGET", _u16(base, service + 58, 4, repair=True))
    add("NEG-N5-PINIT1-SERVICE-DEPENDENCY-BUDGET", _u16(base, service2 + 60, 2, repair=True))
    add("NEG-N5-PINIT1-TOTAL-RESTART-BUDGET", _u32(base, 112, 7))
    return controls


def _controls() -> list[Control]:
    controls = _parser_controls()
    base = pinit1.canonical_bundle()
    activation_ids = pinit1.NEGATIVE_CONTROL_IDS[len(controls) :]
    if len(activation_ids) != len(pinit1.ACTIVATION_MODES):
        raise QualificationError("activation control register length mismatch")
    controls.extend(
        Control(control_id, "activation", base, mode)
        for control_id, mode in zip(activation_ids, pinit1.ACTIVATION_MODES, strict=True)
    )
    if tuple(control.control_id for control in controls) != pinit1.NEGATIVE_CONTROL_IDS:
        raise QualificationError("negative control implementation order differs from the public register")
    return controls


def _probe_lines(probe: Path, requests: list[str]) -> list[str]:
    completed = subprocess.run(
        [str(probe)],
        input="\n".join(requests) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise QualificationError(f"PINIT1 probe failed: {completed.stdout[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError(f"PINIT1 probe result count mismatch: {len(lines)} != {len(requests)}")
    return lines


def _control_request(control: Control) -> tuple[str, str]:
    if control.surface == "parse":
        return f"P:{control.data.hex().upper()}", pinit1.parse_result(control.data)
    bundle = pinit1.parse(control.data)
    context = pinit1.activation_context(control.mode, bundle)
    try:
        pinit1.authorize_activation(bundle, context)
        expected = "OK:activation"
    except pinit1.InitialSystemError as error:
        expected = f"ERR:{error.code}"
    return f"A:{control.mode}:{control.data.hex().upper()}", expected


def _qualify_controls(probe: Path) -> list[dict[str, Any]]:
    controls = _controls()
    pairs = [_control_request(control) for control in controls]
    actual = _probe_lines(probe, [request for request, _ in pairs])
    results = []
    for control, (_, expected), observed in zip(controls, pairs, actual, strict=True):
        if expected != observed:
            raise QualificationError(f"{control.control_id} mismatch: Python={expected}, Rust={observed}")
        if not observed.startswith("ERR:"):
            raise QualificationError(f"{control.control_id} did not reject")
        results.append(
            {
                "id": control.control_id,
                "surface": control.surface,
                "status": "pass",
                "rust_python_result": observed,
            }
        )
    return results


def _qualify_golden(probe: Path, golden: dict[str, Any]) -> list[dict[str, Any]]:
    actual = _probe_lines(probe, [f"P:{item['hex']}" for item in golden["vectors"]])
    results = []
    for item, observed in zip(golden["vectors"], actual, strict=True):
        if observed != item["summary"]:
            raise QualificationError(f"golden semantic mismatch for {item['id']}")
        results.append(
            {
                "id": item["id"],
                "status": "pass",
                "byte_count": item["byte_count"],
                "sha256": item["sha256"],
                "semantic_summary_matched": True,
            }
        )
    return results


def _valid_case(rng: random.Random, case: int) -> bytes:
    source = (pinit1.minimal_bundle, pinit1.canonical_bundle, pinit1.data_component_bundle)[case % 3]()
    base = pinit1.parse(source)
    suffix = f".c{case:x}"
    components = tuple(
        dataclasses.replace(item, name=item.name + suffix, blob=item.blob + case.to_bytes(4, "little"))
        for item in base.components
    )
    services = tuple(dataclasses.replace(item, name=item.name + suffix) for item in base.services)
    resources = tuple(dataclasses.replace(item, name=item.name + suffix) for item in base.resources)
    version = rng.randrange(1, 33)
    minimum = rng.randrange(1, version + 1)
    return pinit1.encode(
        bundle_version=version,
        minimum_secure_version=minimum,
        root_service_id=base.root_service_id,
        allowed_boot_modes=rng.randrange(1, pinit1.KNOWN_BOOT_MODES + 1),
        required_kernel_abi_major=base.required_kernel_abi_major,
        minimum_kernel_abi_minor=base.minimum_kernel_abi_minor,
        required_pbp_major=base.required_pbp_major,
        minimum_pbp_minor=base.minimum_pbp_minor,
        start_timeout_ms=base.start_timeout_ms,
        rollback_timeout_ms=base.rollback_timeout_ms,
        max_total_restarts=base.max_total_restarts,
        components=components,
        services=services,
        dependencies=base.dependencies,
        resources=resources,
        capabilities=base.capabilities,
    )


def _mutated_case(rng: random.Random, case: int) -> bytes:
    value = bytearray(_valid_case(rng, case))
    operation = rng.randrange(8)
    if operation == 0 and value:
        del value[rng.randrange(len(value))]
    elif operation == 1 and value:
        value[rng.randrange(len(value))] ^= 1 << rng.randrange(8)
    elif operation == 2 and value:
        del value[rng.randrange(len(value)) :]
    elif operation == 3:
        value.insert(rng.randrange(len(value) + 1), rng.randrange(256))
    elif operation == 4:
        value.extend(bytes([rng.randrange(256)]))
    elif operation == 5:
        value[20:24] = struct.pack("<I", pinit1.REQUIRED_FLAGS ^ 1)
    elif operation == 6 and len(value) > pinit1.HEADER_BYTES:
        position = rng.randrange(pinit1.HEADER_BYTES, len(value))
        value[position] ^= 1
        _repair_body(value)
    else:
        value[120] ^= 1
    return bytes(value)


def _qualify_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(DIFFERENTIAL_SEED)
    batch_size = 256
    valid_results = 0
    rejected_results = 0
    compared = 0
    for start in range(0, DIFFERENTIAL_CASES, batch_size):
        data_batch = []
        intended_valid = []
        for case in range(start, min(start + batch_size, DIFFERENTIAL_CASES)):
            valid = case % 2 == 0
            data_batch.append(_valid_case(rng, case) if valid else _mutated_case(rng, case))
            intended_valid.append(valid)
        expected = [pinit1.parse_result(data) for data in data_batch]
        actual = _probe_lines(probe, [f"P:{data.hex().upper()}" for data in data_batch])
        for offset, (must_accept, python_result, rust_result) in enumerate(
            zip(intended_valid, expected, actual, strict=True)
        ):
            if python_result != rust_result:
                raise QualificationError(
                    f"differential mismatch at case {start + offset}: Python={python_result}, Rust={rust_result}"
                )
            if must_accept and not python_result.startswith("OK;"):
                raise QualificationError(f"generated valid case {start + offset} rejected: {python_result}")
            valid_results += int(python_result.startswith("OK;"))
            rejected_results += int(python_result.startswith("ERR:"))
            compared += 1
    if compared != DIFFERENTIAL_CASES or valid_results == 0 or rejected_results == 0:
        raise QualificationError("differential campaign did not cover both acceptance and rejection")
    return {
        "campaign_id": "PINIT1-DIFF-1",
        "seed": f"0x{DIFFERENTIAL_SEED:X}",
        "generator": "deterministic valid minimal, canonical, and data-bearing bundles plus deletion, bit flip, truncation, insertion, suffix, flag, body-with-repaired-digest, and digest mutations",
        "case_count": compared,
        "valid_result_count": valid_results,
        "rejected_result_count": rejected_results,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def _qualify_activation(probe: Path) -> dict[str, Any]:
    data = pinit1.canonical_bundle()
    observed = _probe_lines(
        probe,
        [
            f"A:qualified:{data.hex().upper()}",
            f"A:development:{data.hex().upper()}",
        ],
    )
    if observed != ["OK:activation", "ERR:pinit_activation_outer_signature_verified"]:
        raise QualificationError(f"activation boundary mismatch: {observed}")
    return {
        "status": "pass",
        "synthetic_all_true_context_result": observed[0],
        "synthetic_all_true_context_is_trust_evidence": False,
        "current_unsigned_development_context_result": observed[1],
        "current_unsigned_development_activation_allowed": False,
        "individual_precondition_negative_count": len(pinit1.ACTIVATION_MODES),
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = pinit1.read_json(ROOT / pinit1.CONTRACT_RELATIVE)
    golden = pinit1.read_json(ROOT / pinit1.GOLDEN_RELATIVE)
    errors = pinit1.contract_errors(contract) + pinit1.golden_errors(golden)
    if errors:
        raise QualificationError("; ".join(errors))
    with tempfile.TemporaryDirectory(prefix="pooleos-pinit1-") as temporary:
        probe, validator_qualification = _build_validators(toolchain_root, Path(temporary))
        golden_results = _qualify_golden(probe, golden)
        controls = _qualify_controls(probe)
        differential = _qualify_differential(probe)
        activation = _qualify_activation(probe)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_initial_system_readiness",
        "status_date": "2026-07-18",
        "status": "pass_single_host_synthetic_non_promoting",
        "contract_id": pinit1.CONTRACT_ID,
        "selected_move_id": "N5-INIT-BUNDLE-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.6": "partial", "N21": "not_started"},
        "bindings": {
            "contract": pinit1.file_binding(ROOT / pinit1.CONTRACT_RELATIVE),
            "contract_schema": pinit1.file_binding(ROOT / pinit1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": pinit1.file_binding(ROOT / pinit1.GOLDEN_RELATIVE),
            "golden_schema": pinit1.file_binding(ROOT / pinit1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": pinit1.file_binding(ROOT / pinit1.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": [pinit1.file_binding(ROOT / path) for path in pinit1.IMPLEMENTATION_INPUTS],
        },
        "validator_qualification": validator_qualification,
        "golden_vectors": golden_results,
        "negative_controls": controls,
        "differential_fuzz": differential,
        "activation_qualification": activation,
        "claims": pinit1.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 3,
            "rust_host_tests_total": 3,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "golden_vectors_matched": 3,
            "golden_vectors_total": 3,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "differential_fuzz_cases": differential["case_count"],
            "differential_mismatches": differential["mismatch_count"],
            "development_activation_denied": True,
            "synthetic_activation_passed": True,
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PINIT1 before declaring a stable initial-system ABI.",
            "Freeze and verify PXABI1 component bytes before any component can execute.",
            "Implement PooleKernel capability objects, derivation, attenuation, and transitive revocation.",
            "Implement abstract resource allocation, quotas, deterministic rollback, and teardown.",
            "Implement an initial-system transaction engine in native user space after kernel entry exists.",
            "Authenticate PSM1 and PBART1 with an approved trust root and independent signature review.",
            "Persist and authenticate rollback state across normal, previous, safe, and recovery boots.",
            "Bind live kernel ABI, PBP, boot mode, allocator, broker, component, and capacity evidence.",
            "Freeze recovery, symbols, microcode, firmware-manifest, and policy inner formats.",
            "Run fault injection for partial allocation, launch timeout, readiness failure, restart exhaustion, and rollback timeout.",
            "Reproduce validators on a second independent builder and target firmware.",
            "Complete kernel transfer, native execution, physical-media, signed ISO, and N5-N39 gates.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    readiness = make_readiness(args.toolchain_root.resolve())
    pinit1.write_json(readiness, args.out)
    errors = pinit1.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    print(
        f"PINIT1 qualification passed: tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"differential={readiness['summary']['differential_fuzz_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
