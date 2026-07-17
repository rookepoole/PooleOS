#!/usr/bin/env python3
"""Qualify PBC1 grammar, parsers, hostile controls, and differential cases."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_config as pbc1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / pbc1.READINESS_RELATIVE
FUZZ_CASES = 16_384
FUZZ_SEED = 0x5042_4331


class QualificationError(RuntimeError):
    """Raised when a PBC1 qualification step fails closed."""


@dataclass(frozen=True)
class Control:
    control_id: str
    surface: str
    data: bytes = b""
    capacity: int = pbc1.MAX_ENTRIES
    configured_limit: int = 0
    observed_size: int = 0


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
            f"command failed ({completed.returncode}): {' '.join(command[:5])}\n"
            + "\n".join(output.splitlines()[-40:])
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
    env["CARGO_TARGET_X86_64_UNKNOWN_UEFI_RUSTFLAGS"] = " ".join(
        (
            "-Cpanic=abort",
            "-Clink-arg=/debug:none",
            "-Clink-arg=/timestamp:0",
            '--cfg=sha2_backend="soft"',
            '--cfg=sha2_backend_soft="compact"',
            f"--remap-path-prefix={native_root}=/pooleos/native",
        )
    )
    env["CARGO_TARGET_X86_64_UNKNOWN_NONE_RUSTFLAGS"] = " ".join(
        (
            "-Cpanic=abort",
            "-Crelocation-model=static",
            "-Clink-arg=--entry=_start",
            "-Clink-arg=--build-id=none",
            "-Clink-arg=--gc-sections",
            "-Clink-arg=-static",
            f"--remap-path-prefix={native_root}=/pooleos/native",
        )
    )
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _single_rlib(target_dir: Path, target: str, crate_name: str) -> Path:
    artifacts = sorted((target_dir / target / "release" / "deps").glob(f"lib{crate_name}-*.rlib"))
    if len(artifacts) != 1:
        raise QualificationError(f"expected one {crate_name} rlib for {target}, found {len(artifacts)}")
    return artifacts[0]


def _build_parsers(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
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
            "poole-boot-config",
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
    if match is None or int(match.group(1)) != 12:
        raise QualificationError("expected exactly twelve PBC1 Rust host tests")

    target_results = []
    integration_results = []
    for target in ("x86_64-unknown-uefi", "x86_64-unknown-none"):
        parser_target = temporary_root / f"parser-{target}"
        _run(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "poole-boot-config",
                "--lib",
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(parser_target),
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
        artifact = _single_rlib(parser_target, target, "poole_boot_config")
        target_results.append(
            {
                "target": target,
                "status": "pass",
                "byte_count": artifact.stat().st_size,
                "sha256": pbc1.sha256_bytes(artifact.read_bytes()),
            }
        )

        boot_target = temporary_root / f"pooleboot-{target}"
        _run(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "pooleboot",
                "--lib",
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(boot_target),
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
        boot_artifact = _single_rlib(boot_target, target, "pooleboot")
        integration_results.append(
            {
                "target": target,
                "status": "pass",
                "pooleboot_rlib_byte_count": boot_artifact.stat().st_size,
                "pooleboot_rlib_sha256": pbc1.sha256_bytes(boot_artifact.read_bytes()),
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
            "poole-boot-config",
            "--bin",
            "pbc1-probe",
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
    probe = probe_target / host_target / "release" / "pbc1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PBC1 host probe is missing")
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    return probe, {
        "rustc_version_sha256": pbc1.sha256_bytes(version.encode("utf-8")),
        "rust_host_target": host_target,
        "rust_host_test_count": 12,
        "rust_host_test_pass_count": 12,
        "no_std_target_builds": target_results,
        "pooleboot_compile_time_integration_builds": integration_results,
        "host_probe_byte_count": probe.stat().st_size,
        "host_probe_artifact_identity_recorded": False,
        "host_probe_role": "ephemeral host-only differential transport",
    }


def _lines(data: bytes) -> list[bytes]:
    return data[:-1].split(b"\n")


def _join(lines: list[bytes]) -> bytes:
    return b"\n".join(lines) + b"\n"


def _replace(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise QualificationError(f"control mutation source is not unique: {old!r}")
    return data.replace(old, new, 1)


def _controls() -> list[Control]:
    minimal = pbc1.build_fixture("minimal_v1")
    multi = pbc1.build_fixture("multi_mode_v1")
    minimal_lines = _lines(minimal)
    multi_lines = _lines(multi)
    controls: list[Control] = []

    def parse(control_id: str, data: bytes, capacity: int = pbc1.MAX_ENTRIES) -> None:
        controls.append(Control(control_id, "parse", data=data, capacity=capacity))

    def size(control_id: str, configured: int, observed: int) -> None:
        controls.append(Control(control_id, "artifact_size", configured_limit=configured, observed_size=observed))

    parse("NEG-N5-PBC1-EMPTY", b"")
    parse("NEG-N5-PBC1-CONFIG-OVERSIZED", b"A" * pbc1.MAX_CONFIG_BYTES + b"\n")
    parse("NEG-N5-PBC1-FINAL-LF", minimal[:-1])
    parse("NEG-N5-PBC1-NUL", b"\0" + minimal[1:])
    parse("NEG-N5-PBC1-BOM", b"\xef\xbb\xbf" + minimal)
    parse("NEG-N5-PBC1-CRLF", minimal.replace(b"\n", b"\r\n", 1))
    parse("NEG-N5-PBC1-NON-ASCII", b"\x80" + minimal[1:])
    parse("NEG-N5-PBC1-SPACE", _replace(minimal, b"timeout_ms=0", b"timeout_ms=0 "))
    parse("NEG-N5-PBC1-EMPTY-LINE", minimal.replace(b"\n", b"\n\n", 1))
    parse(
        "NEG-N5-PBC1-LINE-OVERSIZED",
        _replace(minimal, b"\\EFI\\POOLEOS\\MANIFEST_A.PBM", pbc1.MANIFEST_ROOT.encode() + b"A" * 300 + b".PBM"),
    )
    many_lines = [b"POOLEOS-BOOTCFG/1.0"] + [f"key{index}=1".encode() for index in range(63)] + [b"end=PBC1"]
    parse("NEG-N5-PBC1-LINE-COUNT", _join(many_lines))
    parse("NEG-N5-PBC1-MAGIC", _replace(minimal, b"POOLEOS-BOOTCFG", b"OTHEROS-BOOTCFG"))
    parse("NEG-N5-PBC1-MAJOR-VERSION", _replace(minimal, b"/1.0", b"/2.0"))
    parse("NEG-N5-PBC1-MINOR-VERSION", _replace(minimal, b"/1.0", b"/1.1"))
    parse("NEG-N5-PBC1-NO-EQUALS", _replace(minimal, b"entry_count=1", b"entry_count1"))
    parse("NEG-N5-PBC1-EMPTY-KEY", _replace(minimal, b"entry_count=1", b"=1"))
    parse("NEG-N5-PBC1-EMPTY-VALUE", _replace(minimal, b"entry_count=1", b"entry_count="))
    parse("NEG-N5-PBC1-MULTIPLE-EQUALS", _replace(minimal, b"entry_count=1", b"entry_count==1"))
    parse("NEG-N5-PBC1-DUPLICATE-STATIC", _replace(minimal, b"timeout_ms=0", b"entry_count=0"))
    parse("NEG-N5-PBC1-DUPLICATE-ENTRY", _replace(minimal, b"entry.normal.slot=1", b"entry.normal.mode=1"))
    parse("NEG-N5-PBC1-UNKNOWN-STATIC", _replace(minimal, b"timeout_ms=0", b"delay_ms=0"))
    parse("NEG-N5-PBC1-UNKNOWN-ENTRY", _replace(minimal, b"entry.normal.slot=1", b"entry.normal.partition=1"))
    swapped = minimal_lines.copy()
    swapped[2], swapped[3] = swapped[3], swapped[2]
    parse("NEG-N5-PBC1-HEADER-ORDER", _join(swapped))
    swapped = minimal_lines.copy()
    swapped[6], swapped[7] = swapped[7], swapped[6]
    parse("NEG-N5-PBC1-ENTRY-FIELD-ORDER", _join(swapped))
    parse("NEG-N5-PBC1-TRUNCATED-HEADER", _join(minimal_lines[:3] + [b"end=PBC1"]))
    parse("NEG-N5-PBC1-TRUNCATED-ENTRY", _join(minimal_lines[:7] + minimal_lines[8:]))
    parse("NEG-N5-PBC1-END-MISSING", _join(minimal_lines[:-1]))
    parse("NEG-N5-PBC1-END-WRONG", _replace(minimal, b"end=PBC1", b"end=PBC2"))
    parse("NEG-N5-PBC1-ENTRY-COUNT-ZERO", _replace(minimal, b"entry_count=1", b"entry_count=0"))
    parse("NEG-N5-PBC1-ENTRY-COUNT-HIGH", _replace(minimal, b"entry_count=1", b"entry_count=9"))
    parse("NEG-N5-PBC1-ENTRY-COUNT-LEADING-ZERO", _replace(minimal, b"entry_count=1", b"entry_count=01"))
    parse("NEG-N5-PBC1-ENTRY-COUNT-NONNUMERIC", _replace(minimal, b"entry_count=1", b"entry_count=one"))
    parse("NEG-N5-PBC1-TIMEOUT-HIGH", _replace(minimal, b"timeout_ms=0", b"timeout_ms=30001"))
    parse("NEG-N5-PBC1-TIMEOUT-NEGATIVE", _replace(minimal, b"timeout_ms=0", b"timeout_ms=-1"))
    parse("NEG-N5-PBC1-TIMEOUT-OVERFLOW", _replace(minimal, b"timeout_ms=0", b"timeout_ms=18446744073709551616"))
    parse("NEG-N5-PBC1-ATTEMPTS-ZERO", _replace(minimal, b"boot_attempt_limit=3", b"boot_attempt_limit=0"))
    parse("NEG-N5-PBC1-ATTEMPTS-HIGH", _replace(minimal, b"boot_attempt_limit=3", b"boot_attempt_limit=9"))
    parse("NEG-N5-PBC1-DEFAULT-ID", _replace(minimal, b"default_entry=normal", b"default_entry=Normal"))
    parse("NEG-N5-PBC1-DEFAULT-MISSING", _replace(minimal, b"default_entry=normal", b"default_entry=recovery"))
    parse("NEG-N5-PBC1-ENTRY-ID-START", minimal.replace(b"entry.normal.", b"entry.1normal."))
    parse("NEG-N5-PBC1-ENTRY-ID-LENGTH", minimal.replace(b"entry.normal.", b"entry." + b"a" * 32 + b"."))
    reordered = multi_lines.copy()
    reordered[5:9], reordered[9:13] = reordered[9:13], reordered[5:9]
    parse("NEG-N5-PBC1-ENTRY-ORDER", _join(reordered))
    parse("NEG-N5-PBC1-MODE", _replace(minimal, b"mode=normal", b"mode=fast"))
    parse("NEG-N5-PBC1-SLOT-ZERO", _replace(minimal, b"slot=1", b"slot=0"))
    parse("NEG-N5-PBC1-SLOT-HIGH", _replace(minimal, b"slot=1", b"slot=5"))
    parse("NEG-N5-PBC1-SLOT-LEADING-ZERO", _replace(minimal, b"slot=1", b"slot=01"))
    path = b"\\EFI\\POOLEOS\\MANIFEST_A.PBM"
    parse("NEG-N5-PBC1-PATH-RELATIVE", _replace(minimal, path, b"MANIFEST_A.PBM"))
    parse("NEG-N5-PBC1-PATH-ROOT", _replace(minimal, path, b"\\EFI\\OTHER\\MANIFEST_A.PBM"))
    parse("NEG-N5-PBC1-PATH-SLASH", _replace(minimal, path, b"\\EFI\\POOLEOS/MANIFEST_A.PBM"))
    parse("NEG-N5-PBC1-PATH-TRAVERSAL", _replace(minimal, path, b"\\EFI\\POOLEOS\\..\\MANIFEST_A.PBM"))
    parse("NEG-N5-PBC1-PATH-EMPTY-SEGMENT", _replace(minimal, path, b"\\EFI\\POOLEOS\\DIR\\\\MANIFEST_A.PBM"))
    parse("NEG-N5-PBC1-PATH-LOWERCASE", _replace(minimal, path, b"\\EFI\\POOLEOS\\manifest_a.PBM"))
    parse("NEG-N5-PBC1-PATH-SUFFIX", _replace(minimal, path, b"\\EFI\\POOLEOS\\MANIFEST_A.ELF"))
    parse("NEG-N5-PBC1-PATH-LENGTH", _replace(minimal, path, pbc1.MANIFEST_ROOT.encode() + b"A" * 237 + b".PBM"))
    parse("NEG-N5-PBC1-MANIFEST-LIMIT-ZERO", _replace(minimal, b"manifest_max_bytes=65536", b"manifest_max_bytes=0"))
    parse("NEG-N5-PBC1-MANIFEST-LIMIT-HIGH", _replace(minimal, b"manifest_max_bytes=65536", b"manifest_max_bytes=1048577"))
    parse("NEG-N5-PBC1-MANIFEST-LIMIT-OVERFLOW", _replace(minimal, b"manifest_max_bytes=65536", b"manifest_max_bytes=18446744073709551616"))
    parse("NEG-N5-PBC1-OUTPUT-CAPACITY", minimal, capacity=0)
    size("NEG-N5-PBC1-ARTIFACT-ZERO", 1024, 0)
    size("NEG-N5-PBC1-ARTIFACT-OVER-CONFIGURED", 1024, 1025)
    size("NEG-N5-PBC1-ARTIFACT-OVER-ABSOLUTE", pbc1.MAX_MANIFEST_BYTES + 1, 1)
    parse("NEG-N5-PBC1-DECLARED-COUNT-SHORT", _replace(minimal, b"entry_count=1", b"entry_count=2"))
    extra = minimal_lines[:-1] + [
        b"entry.other.mode=safe",
        b"entry.other.slot=2",
        b"entry.other.manifest=\\EFI\\POOLEOS\\OTHER.PBM",
        b"entry.other.manifest_max_bytes=65536",
        b"end=PBC1",
    ]
    parse("NEG-N5-PBC1-DECLARED-COUNT-EXTRA", _join(extra))
    parse("NEG-N5-PBC1-TRAILING-KEY", _join(minimal_lines[:-1] + [b"future=1", b"end=PBC1"]))

    if tuple(control.control_id for control in controls) != pbc1.NEGATIVE_CONTROL_IDS:
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
        raise QualificationError(f"PBC1 probe failed: {completed.stdout[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError(f"PBC1 probe result count mismatch: {len(lines)} != {len(requests)}")
    return lines


def _control_request(control: Control) -> tuple[str, str]:
    if control.surface == "parse":
        request = f"P:{control.capacity}:{control.data.hex().upper()}"
        expected = pbc1.parse_result(control.data, control.capacity)
    else:
        request = f"S:{control.configured_limit}:{control.observed_size}"
        expected = pbc1.size_result(control.configured_limit, control.observed_size)
    return request, expected


def _qualify_controls(probe: Path) -> list[dict[str, Any]]:
    controls = _controls()
    pairs = [_control_request(control) for control in controls]
    actual = _probe_lines(probe, [request for request, _ in pairs])
    results = []
    for control, (_, expected), observed in zip(controls, pairs, actual, strict=True):
        if expected != observed:
            raise QualificationError(f"{control.control_id} parser mismatch: Python={expected}, Rust={observed}")
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
    requests = [f"P:{pbc1.MAX_ENTRIES}:{item['hex']}" for item in golden["vectors"]]
    actual = _probe_lines(probe, requests)
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


def _random_entry(rng: random.Random, case: int, index: int) -> pbc1.Entry:
    identifier = f"e{case:x}_{index}"
    mode = pbc1.MODES[rng.randrange(len(pbc1.MODES))]
    slot = rng.randrange(1, pbc1.MAX_SLOT + 1)
    manifest = pbc1.MANIFEST_ROOT + f"CASE_{case:X}_{index}.PBM"
    limit = rng.randrange(1, pbc1.MAX_MANIFEST_BYTES + 1)
    return pbc1.Entry(identifier, mode, slot, manifest, limit)


def _valid_case(rng: random.Random, case: int) -> bytes:
    count = rng.randrange(1, pbc1.MAX_ENTRIES + 1)
    entries = tuple(_random_entry(rng, case, index) for index in range(count))
    default = entries[rng.randrange(count)].id
    return pbc1.encode(
        entries,
        default_entry=default,
        timeout_ms=rng.randrange(pbc1.MAX_TIMEOUT_MS + 1),
        boot_attempt_limit=rng.randrange(1, pbc1.MAX_BOOT_ATTEMPTS + 1),
    )


def _mutated_case(rng: random.Random, case: int) -> bytes:
    value = bytearray(_valid_case(rng, case))
    operation = rng.randrange(7)
    if operation == 0 and value:
        del value[rng.randrange(len(value))]
    elif operation == 1 and value:
        value[rng.randrange(len(value))] = rng.randrange(256)
    elif operation == 2 and value:
        del value[rng.randrange(len(value)) :]
    elif operation == 3:
        value.insert(rng.randrange(len(value) + 1), rng.randrange(256))
    elif operation == 4:
        position = value.find(b"\n")
        if position >= 0:
            value[position:position] = b"\r"
    elif operation == 5:
        value.extend(bytes([rng.randrange(256)]))
    else:
        value.extend(b"future=1\n")
    return bytes(value)


def _qualify_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(FUZZ_SEED)
    batch_size = 512
    valid_cases = 0
    rejected_cases = 0
    compared = 0
    for start in range(0, FUZZ_CASES, batch_size):
        data_batch = []
        for case in range(start, min(start + batch_size, FUZZ_CASES)):
            data = _valid_case(rng, case) if case % 2 == 0 else _mutated_case(rng, case)
            data_batch.append(data)
        expected = [pbc1.parse_result(data) for data in data_batch]
        actual = _probe_lines(
            probe,
            [f"P:{pbc1.MAX_ENTRIES}:{data.hex().upper()}" for data in data_batch],
        )
        for offset, (python_result, rust_result) in enumerate(zip(expected, actual, strict=True)):
            if python_result != rust_result:
                raise QualificationError(
                    f"differential mismatch at case {start + offset}: Python={python_result}, Rust={rust_result}"
                )
            valid_cases += int(python_result.startswith("OK;"))
            rejected_cases += int(python_result.startswith("ERR:"))
            compared += 1
    if compared != FUZZ_CASES or valid_cases == 0 or rejected_cases == 0:
        raise QualificationError("differential campaign did not cover both acceptance and rejection")
    return {
        "campaign_id": "PBC1-DIFF-1",
        "generator": "deterministic valid configurations plus byte deletion, replacement, truncation, insertion, CR, suffix, and trailing-key mutations",
        "case_count": compared,
        "valid_result_count": valid_cases,
        "rejected_result_count": rejected_cases,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = pbc1.read_json(ROOT / pbc1.CONTRACT_RELATIVE)
    golden = pbc1.read_json(ROOT / pbc1.GOLDEN_RELATIVE)
    contract_errors = pbc1.contract_errors(contract)
    golden_errors = pbc1.golden_errors(golden)
    if contract_errors or golden_errors:
        raise QualificationError("; ".join(contract_errors + golden_errors))
    with tempfile.TemporaryDirectory(prefix="pooleos-pbc1-") as temporary:
        probe, parser_qualification = _build_parsers(toolchain_root, Path(temporary))
        golden_results = _qualify_golden(probe, golden)
        controls = _qualify_controls(probe)
        differential = _qualify_differential(probe)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_boot_config_readiness",
        "status_date": "2026-07-16",
        "status": "pass_single_host_synthetic_non_promoting",
        "contract_id": pbc1.CONTRACT_ID,
        "selected_move_id": "N5-BOOTCFG-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.4": "partial"},
        "bindings": {
            "contract": pbc1.file_binding(ROOT / pbc1.CONTRACT_RELATIVE),
            "contract_schema": pbc1.file_binding(ROOT / pbc1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": pbc1.file_binding(ROOT / pbc1.GOLDEN_RELATIVE),
            "golden_schema": pbc1.file_binding(ROOT / pbc1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": pbc1.file_binding(ROOT / pbc1.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": [pbc1.file_binding(ROOT / path) for path in pbc1.IMPLEMENTATION_INPUTS],
        },
        "parser_qualification": parser_qualification,
        "golden_vectors": golden_results,
        "negative_controls": controls,
        "differential_fuzz": differential,
        "claims": pbc1.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 12,
            "rust_host_tests_total": 12,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "golden_vectors_matched": 3,
            "golden_vectors_total": 3,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "differential_fuzz_cases": differential["case_count"],
            "differential_mismatches": differential["mismatch_count"],
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PBC1 before declaring a stable boot ABI.",
            "Implement Loaded Image and Simple File System discovery in PooleBoot.",
            "Read the bounded configuration file with exact truncation and size checks.",
            "Bind selected entries to signed manifest verification and rollback policy.",
            "Implement boot-menu input, timeout, safe, previous, recovery, and diagnostic behavior.",
            "Implement ELF64 loading and exact loaded-artifact hashing.",
            "Populate PBP1 from live firmware state and transfer only after ExitBootServices.",
            "Reproduce on a second independent builder and execute on target firmware.",
            "Complete separately authorized physical-media qualification and signed ISO release gates.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    readiness = make_readiness(args.toolchain_root.resolve())
    pbc1.write_json(readiness, args.out)
    errors = pbc1.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    print(
        f"PBC1 qualification passed: tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"differential={readiness['summary']['differential_fuzz_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
