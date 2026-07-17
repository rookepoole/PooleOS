#!/usr/bin/env python3
"""Qualify PSM1 grammar, SHA-256, hostile controls, and differential cases."""

from __future__ import annotations

import argparse
import json
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

from runtime import native_system_manifest as psm1  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_boot_config as rust_tools  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / psm1.READINESS_RELATIVE
FUZZ_CASES = 16_384
FUZZ_SEED = 0x5053_4D31
DIGEST_CASES = 1_024


class QualificationError(RuntimeError):
    """Raised when the PSM1 qualification fails closed."""


@dataclass(frozen=True)
class Control:
    control_id: str
    data: bytes
    capacity: int = psm1.MAX_ARTIFACTS


def _build_parsers(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = rust_tools._toolchain(toolchain_root)
    host_target = "x86_64-pc-windows-msvc"
    host_tests = rust_tools._run(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-manifest",
            "--lib",
            "--target",
            host_target,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "host-tests"),
            "--",
            "--test-threads=1",
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", host_tests)
    if match is None or int(match.group(1)) != 8:
        raise QualificationError("expected exactly eight PSM1 Rust host tests")

    target_results = []
    for target in ("x86_64-unknown-uefi", "x86_64-unknown-none"):
        target_dir = temporary_root / f"manifest-{target}"
        rust_tools._run(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "poole-manifest",
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
        artifact = rust_tools._single_rlib(target_dir, target, "poole_manifest")
        target_results.append(
            {
                "target": target,
                "status": "pass",
                "byte_count": artifact.stat().st_size,
                "sha256": psm1.sha256_bytes(artifact.read_bytes()),
            }
        )

    integration_dir = temporary_root / "pooleboot-uefi"
    rust_tools._run(
        [
            str(cargo),
            "build",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "pooleboot",
            "--bin",
            "PooleBoot",
            "--target",
            "x86_64-unknown-uefi",
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(integration_dir),
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    pooleboot = integration_dir / "x86_64-unknown-uefi" / "release" / "PooleBoot.efi"
    if not pooleboot.is_file():
        raise QualificationError("PSM1 PooleBoot integration binary is missing")

    probe_dir = temporary_root / "host-probe"
    rust_tools._run(
        [
            str(cargo),
            "build",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-manifest",
            "--bin",
            "psm1-probe",
            "--features",
            "host-probe",
            "--target",
            host_target,
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(probe_dir),
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    probe = probe_dir / host_target / "release" / "psm1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PSM1 host probe is missing")
    version = rust_tools._run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    return probe, {
        "rustc_version_sha256": psm1.sha256_bytes(version.encode("utf-8")),
        "rust_host_target": host_target,
        "rust_host_test_count": 8,
        "rust_host_test_pass_count": 8,
        "no_std_target_builds": target_results,
        "pooleboot_uefi_integration": {
            "status": "pass",
            "byte_count": pooleboot.stat().st_size,
            "sha256": psm1.sha256_bytes(pooleboot.read_bytes()),
        },
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


def _replace_many(data: bytes, replacements: tuple[tuple[bytes, bytes], ...]) -> bytes:
    for old, new in replacements:
        data = _replace(data, old, new)
    return data


def _controls() -> list[Control]:
    minimal = psm1.build_fixture("minimal_kernel_v1")
    multi = psm1.build_fixture("multi_artifact_v1")
    lines = _lines(minimal)
    multi_lines = _lines(multi)
    controls: list[Control] = []

    def add(control_id: str, data: bytes, capacity: int = psm1.MAX_ARTIFACTS) -> None:
        controls.append(Control(control_id, data, capacity))

    add("NEG-N5-PSM1-EMPTY", b"")
    add("NEG-N5-PSM1-OVERSIZED", b"A" * psm1.MAX_MANIFEST_BYTES + b"\n")
    add("NEG-N5-PSM1-FINAL-LF", minimal[:-1])
    add("NEG-N5-PSM1-NUL", b"\0" + minimal[1:])
    add("NEG-N5-PSM1-BOM", b"\xef\xbb\xbf" + minimal)
    add("NEG-N5-PSM1-CRLF", minimal.replace(b"\n", b"\r\n", 1))
    add("NEG-N5-PSM1-NON-ASCII", b"\x80" + minimal[1:])
    add("NEG-N5-PSM1-WHITESPACE", _replace(minimal, b"slot=1", b"slot=1 "))
    add("NEG-N5-PSM1-EMPTY-LINE", minimal.replace(b"\n", b"\n\n", 1))
    add("NEG-N5-PSM1-LINE-OVERSIZED", _replace(minimal, b"KERNEL.ELF", b"A" * 380 + b".ELF"))
    too_many = [psm1.MAGIC.encode()] + [f"future_{index}=1".encode() for index in range(191)] + [psm1.END_MARKER.encode()]
    add("NEG-N5-PSM1-LINE-COUNT", _join(too_many))
    add("NEG-N5-PSM1-MAGIC", _replace(minimal, b"POOLEOS-SYSTEM-MANIFEST", b"OTHER-SYSTEM-MANIFEST"))
    add("NEG-N5-PSM1-MAJOR-VERSION", _replace(minimal, b"MANIFEST/1.0", b"MANIFEST/2.0"))
    add("NEG-N5-PSM1-MINOR-VERSION", _replace(minimal, b"MANIFEST/1.0", b"MANIFEST/1.1"))
    add("NEG-N5-PSM1-NO-EQUALS", _replace(minimal, b"slot=1", b"slot1"))
    add("NEG-N5-PSM1-EMPTY-KEY", _replace(minimal, b"slot=1", b"=1"))
    add("NEG-N5-PSM1-EMPTY-VALUE", _replace(minimal, b"slot=1", b"slot="))
    add("NEG-N5-PSM1-MULTIPLE-EQUALS", _replace(minimal, b"slot=1", b"slot==1"))
    add("NEG-N5-PSM1-DUPLICATE-STATIC", _replace(minimal, b"slot=1", b"manifest_id=ONE"))
    add("NEG-N5-PSM1-DUPLICATE-ARTIFACT", _replace(minimal, b"artifact.kernel.format", b"artifact.kernel.type"))
    add("NEG-N5-PSM1-UNKNOWN-STATIC", _replace(minimal, b"slot=1", b"partition=1"))
    add("NEG-N5-PSM1-UNKNOWN-ARTIFACT", _replace(minimal, b"artifact.kernel.format", b"artifact.kernel.codec"))
    swapped = lines.copy()
    swapped[1], swapped[2] = swapped[2], swapped[1]
    add("NEG-N5-PSM1-HEADER-ORDER", _join(swapped))
    swapped = lines.copy()
    swapped[7], swapped[8] = swapped[8], swapped[7]
    add("NEG-N5-PSM1-ARTIFACT-FIELD-ORDER", _join(swapped))
    add("NEG-N5-PSM1-TRUNCATED-HEADER", _join(lines[:3] + [psm1.END_MARKER.encode()]))
    add("NEG-N5-PSM1-TRUNCATED-ARTIFACT", _join(lines[:12] + lines[13:]))
    add("NEG-N5-PSM1-END-MISSING", _join(multi_lines[:-1]))
    add("NEG-N5-PSM1-END-WRONG", _replace(minimal, b"end=PSM1", b"end=PSM2"))
    add("NEG-N5-PSM1-MANIFEST-ID", _replace(minimal, b"manifest_id=PSM", b"manifest_id=psm"))
    add("NEG-N5-PSM1-SLOT-ZERO", _replace(minimal, b"slot=1", b"slot=0"))
    add("NEG-N5-PSM1-SLOT-HIGH", _replace(minimal, b"slot=1", b"slot=5"))
    add("NEG-N5-PSM1-SLOT-LEADING-ZERO", _replace(minimal, b"slot=1", b"slot=01"))
    add("NEG-N5-PSM1-MANIFEST-VERSION-ZERO", _replace(minimal, b"manifest_version=1", b"manifest_version=0"))
    add("NEG-N5-PSM1-VERSION-FLOOR", _replace(minimal, b"minimum_secure_version=1", b"minimum_secure_version=2"))
    add("NEG-N5-PSM1-COUNT-ZERO", _replace(minimal, b"artifact_count=1", b"artifact_count=0"))
    add("NEG-N5-PSM1-COUNT-HIGH", _replace(minimal, b"artifact_count=1", b"artifact_count=17"))
    add("NEG-N5-PSM1-COUNT-SHORT", _replace(minimal, b"artifact_count=1", b"artifact_count=2"))
    add("NEG-N5-PSM1-COUNT-EXTRA", _replace(multi, b"artifact_count=2", b"artifact_count=1"))
    add("NEG-N5-PSM1-ARTIFACT-ID-START", minimal.replace(b"artifact.kernel.", b"artifact.1kernel."))
    add("NEG-N5-PSM1-ARTIFACT-ID-LENGTH", minimal.replace(b"artifact.kernel.", b"artifact." + b"k" * 32 + b"."))
    reordered = multi_lines.copy()
    reordered[6:14], reordered[14:22] = reordered[14:22], reordered[6:14]
    add("NEG-N5-PSM1-ARTIFACT-ORDER", _join(reordered))
    add("NEG-N5-PSM1-ARTIFACT-TYPE", _replace(minimal, b"type=kernel", b"type=unknown"))
    add("NEG-N5-PSM1-FORMAT", _replace(minimal, b"format=PKELF1", b"format=pkelf1"))
    add("NEG-N5-PSM1-ARTIFACT-VERSION-FLOOR", _replace(multi, b"artifact.kernel.version=7", b"artifact.kernel.version=5"))
    path = b"\\EFI\\POOLEOS\\KERNEL.ELF"
    add("NEG-N5-PSM1-PATH-RELATIVE", _replace(minimal, path, b"KERNEL.ELF"))
    add("NEG-N5-PSM1-PATH-ROOT", _replace(minimal, path, b"\\EFI\\OTHER\\KERNEL.ELF"))
    add("NEG-N5-PSM1-PATH-SLASH", _replace(minimal, path, b"\\EFI\\POOLEOS/KERNEL.ELF"))
    add("NEG-N5-PSM1-PATH-TRAVERSAL", _replace(minimal, path, b"\\EFI\\POOLEOS\\..\\KERNEL.ELF"))
    add("NEG-N5-PSM1-PATH-EMPTY-SEGMENT", _replace(minimal, path, b"\\EFI\\POOLEOS\\DIR\\\\KERNEL.ELF"))
    add("NEG-N5-PSM1-PATH-LOWERCASE", _replace(minimal, path, b"\\EFI\\POOLEOS\\kernel.ELF"))
    add("NEG-N5-PSM1-PATH-LENGTH", _replace(minimal, path, psm1.MANIFEST_ROOT.encode() + b"A" * 225 + b".ELF"))
    add("NEG-N5-PSM1-FILE-ZERO", _replace(minimal, b"file_bytes=3", b"file_bytes=0"))
    add("NEG-N5-PSM1-FILE-HIGH", _replace(minimal, b"file_bytes=3", b"file_bytes=67108865"))
    add("NEG-N5-PSM1-IMAGE-HIGH", _replace(minimal, b"image_bytes=4096", b"image_bytes=536870913"))
    digest = psm1.sha256_bytes(b"abc").encode()
    add("NEG-N5-PSM1-DIGEST-LENGTH", _replace(minimal, digest, digest[:-1]))
    add("NEG-N5-PSM1-DIGEST-LOWERCASE", _replace(minimal, digest, digest.lower()))
    add("NEG-N5-PSM1-ENTRY-CONTRACT", _replace(multi, b"artifact.policy.entry_contract=none", b"artifact.policy.entry_contract=PPENTRY1"))
    add("NEG-N5-PSM1-KERNEL-FORMAT", _replace(minimal, b"format=PKELF1", b"format=PXABI1"))
    add("NEG-N5-PSM1-KERNEL-ENTRY", _replace(minimal, b"entry_contract=PKENTRY1", b"entry_contract=none"))
    add("NEG-N5-PSM1-KERNEL-IMAGE-ZERO", _replace(minimal, b"image_bytes=4096", b"image_bytes=0"))
    missing_kernel = _replace_many(
        minimal,
        (
            (b"type=kernel", b"type=policy"),
            (b"format=PKELF1", b"format=PPOL1"),
            (b"image_bytes=4096", b"image_bytes=0"),
            (b"entry_contract=PKENTRY1", b"entry_contract=none"),
        ),
    )
    add("NEG-N5-PSM1-KERNEL-MISSING", missing_kernel)
    duplicate_kernel = _replace_many(
        multi,
        (
            (b"artifact.policy.type=policy", b"artifact.policy.type=kernel"),
            (b"artifact.policy.format=PPOL1", b"artifact.policy.format=PKELF1"),
            (b"artifact.policy.image_bytes=0", b"artifact.policy.image_bytes=4096"),
            (b"artifact.policy.entry_contract=none", b"artifact.policy.entry_contract=PKENTRY1"),
        ),
    )
    add("NEG-N5-PSM1-KERNEL-DUPLICATE", duplicate_kernel)
    add("NEG-N5-PSM1-DUPLICATE-PATH", _replace(multi, b"\\EFI\\POOLEOS\\POLICY_A.POL", b"\\EFI\\POOLEOS\\KERNEL_A.ELF"))
    add("NEG-N5-PSM1-OUTPUT-CAPACITY", minimal, capacity=0)
    if tuple(item.control_id for item in controls) != psm1.NEGATIVE_CONTROL_IDS:
        raise QualificationError("PSM1 negative-control implementation order changed")
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
        raise QualificationError(f"PSM1 probe failed: {completed.stdout[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError(f"PSM1 probe result count mismatch: {len(lines)} != {len(requests)}")
    return lines


def _qualify_golden(probe: Path, golden: dict[str, Any]) -> list[dict[str, Any]]:
    observed = _probe_lines(
        probe,
        [f"P:{psm1.MAX_ARTIFACTS}:{item['hex']}" for item in golden["vectors"]],
    )
    results = []
    for item, actual in zip(golden["vectors"], observed, strict=True):
        if actual != item["summary"]:
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


def _qualify_controls(probe: Path) -> list[dict[str, Any]]:
    controls = _controls()
    python_results = [psm1.parse_result(item.data, item.capacity) for item in controls]
    rust_results = _probe_lines(
        probe,
        [f"P:{item.capacity}:{item.data.hex().upper()}" for item in controls],
    )
    results = []
    for control, python_result, rust_result in zip(
        controls, python_results, rust_results, strict=True
    ):
        if not python_result.startswith("ERR:") or not rust_result.startswith("ERR:"):
            raise QualificationError(
                f"{control.control_id} did not reject: Python={python_result}, Rust={rust_result}"
            )
        results.append(
            {
                "id": control.control_id,
                "status": "pass",
                "python_result": python_result,
                "rust_result": rust_result,
                "rejection_agreement": True,
            }
        )
    return results


def _valid_case(rng: random.Random, case: int) -> bytes:
    count = rng.randrange(1, psm1.MAX_ARTIFACTS + 1)
    floor = rng.randrange(0, 9)
    manifest_version = rng.randrange(max(1, floor), 64)
    artifacts = []
    for index in range(count - 1):
        artifacts.append(
            psm1.Artifact(
                f"a{index:02d}",
                "policy",
                "PPOL1",
                rng.randrange(max(1, floor), 64),
                psm1.MANIFEST_ROOT + f"CASE_{case:X}_{index}.POL",
                rng.randrange(1, 4097),
                0,
                psm1.sha256_bytes(f"{case}:{index}".encode()),
                "none",
            )
        )
    artifacts.append(
        psm1.Artifact(
            "kernel",
            "kernel",
            "PKELF1",
            rng.randrange(max(1, floor), 64),
            psm1.MANIFEST_ROOT + f"KERNEL_{case:X}.ELF",
            rng.randrange(1, 65537),
            rng.randrange(1, 1025) * 4096,
            psm1.sha256_bytes(f"kernel:{case}".encode()),
            "PKENTRY1",
        )
    )
    return psm1.encode(
        artifacts,
        manifest_id=f"PSM-DIFF-{case:X}",
        slot=rng.randrange(1, psm1.MAX_SLOT + 1),
        manifest_version=manifest_version,
        minimum_secure_version=floor,
    )


def _mutated_case(rng: random.Random, case: int) -> bytes:
    value = bytearray(_valid_case(rng, case))
    operation = rng.randrange(8)
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
    elif operation == 6:
        value.extend(b"future=1\n")
    else:
        value = bytearray(value.replace(b"slot=1", b"slot=0", 1))
    return bytes(value)


def _qualify_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(FUZZ_SEED)
    accepted = 0
    rejected = 0
    for start in range(0, FUZZ_CASES, 512):
        batch = [
            _valid_case(rng, case) if case % 2 == 0 else _mutated_case(rng, case)
            for case in range(start, min(start + 512, FUZZ_CASES))
        ]
        python_results = [psm1.parse_result(data) for data in batch]
        rust_results = _probe_lines(
            probe,
            [f"P:{psm1.MAX_ARTIFACTS}:{data.hex().upper()}" for data in batch],
        )
        for offset, (python_result, rust_result) in enumerate(
            zip(python_results, rust_results, strict=True)
        ):
            python_ok = python_result.startswith("OK;")
            rust_ok = rust_result.startswith("OK;")
            if python_ok != rust_ok or (python_ok and python_result != rust_result):
                raise QualificationError(
                    f"differential mismatch at case {start + offset}: "
                    f"Python={python_result}, Rust={rust_result}"
                )
            accepted += int(python_ok)
            rejected += int(not python_ok)
    if accepted == 0 or rejected == 0 or accepted + rejected != FUZZ_CASES:
        raise QualificationError("PSM1 differential campaign lacks acceptance or rejection coverage")
    return {
        "campaign_id": "PSM1-DIFF-1",
        "seed": f"0x{FUZZ_SEED:08X}",
        "case_count": FUZZ_CASES,
        "accepted_result_count": accepted,
        "rejected_result_count": rejected,
        "acceptance_mismatch_count": 0,
        "accepted_semantic_mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def _qualify_digest(probe: Path) -> dict[str, Any]:
    vectors = (
        b"",
        b"abc",
        b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
    )
    rng = random.Random(FUZZ_SEED ^ 0x5348_4132)
    cases = list(vectors)
    for index in range(DIGEST_CASES):
        length = index % 1025
        cases.append(bytes(rng.randrange(256) for _ in range(length)))
    observed = []
    for start in range(0, len(cases), 128):
        observed.extend(
            _probe_lines(
                probe,
                [f"D:{data.hex().upper()}" for data in cases[start : start + 128]],
            )
        )
    expected = [psm1.digest_result(data) for data in cases]
    if observed != expected:
        mismatch = next(index for index, pair in enumerate(zip(observed, expected)) if pair[0] != pair[1])
        raise QualificationError(f"SHA-256 differential mismatch at case {mismatch}")
    return {
        "algorithm": "SHA-256",
        "provider_contract": "PBDIGEST1",
        "standard_vector_count": len(vectors),
        "deterministic_differential_case_count": DIGEST_CASES,
        "python_hashlib_mismatch_count": 0,
        "status": "pass",
        "security_review_complete": False,
        "provider_promotion_allowed": False,
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = psm1.read_json(ROOT / psm1.CONTRACT_RELATIVE)
    golden = psm1.read_json(ROOT / psm1.GOLDEN_RELATIVE)
    failures = psm1.contract_errors(contract, ROOT) + psm1.golden_errors(golden, ROOT)
    digest_schema = psm1.read_json(ROOT / psm1.DIGEST_PROVIDER_SCHEMA_RELATIVE)
    digest_provider = psm1.read_json(ROOT / psm1.DIGEST_PROVIDER_RELATIVE)
    failures.extend(
        f"digest schema {item.path}: {item.message}"
        for item in validate_json(digest_provider, digest_schema)
    )
    if failures:
        raise QualificationError("; ".join(failures))
    with tempfile.TemporaryDirectory(prefix="pooleos-psm1-", dir=ROOT / "tmp") as temporary:
        probe, parser_qualification = _build_parsers(toolchain_root, Path(temporary))
        golden_results = _qualify_golden(probe, golden)
        controls = _qualify_controls(probe)
        differential = _qualify_differential(probe)
        digest = _qualify_digest(probe)
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_system_manifest_readiness",
        "status_date": "2026-07-17",
        "status": "pass_single_host_synthetic_non_promoting",
        "contract_id": psm1.CONTRACT_ID,
        "selected_move_id": "N5-MANIFEST-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.1": "partial", "N5.4": "partial", "N5.5": "partial"},
        "bindings": {
            "contract": psm1.file_binding(ROOT, psm1.CONTRACT_RELATIVE),
            "contract_schema": psm1.file_binding(ROOT, psm1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": psm1.file_binding(ROOT, psm1.GOLDEN_RELATIVE),
            "golden_schema": psm1.file_binding(ROOT, psm1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": psm1.file_binding(ROOT, psm1.READINESS_SCHEMA_RELATIVE),
            "digest_provider": psm1.file_binding(ROOT, psm1.DIGEST_PROVIDER_RELATIVE),
            "digest_provider_schema": psm1.file_binding(ROOT, psm1.DIGEST_PROVIDER_SCHEMA_RELATIVE),
            "implementation_inputs": [psm1.file_binding(ROOT, path) for path in psm1.IMPLEMENTATION_INPUTS],
        },
        "parser_qualification": parser_qualification,
        "golden_vectors": golden_results,
        "negative_controls": controls,
        "differential_fuzz": differential,
        "digest_qualification": digest,
        "claims": psm1.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 8,
            "rust_host_tests_total": 8,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "pooleboot_uefi_integration_builds_passed": 1,
            "pooleboot_uefi_integration_builds_total": 1,
            "golden_vectors_passed": 3,
            "golden_vectors_total": 3,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "differential_cases": FUZZ_CASES,
            "digest_cases": 3 + DIGEST_CASES,
            "mismatch_count": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PSM1 before treating it as a stable boot ABI.",
            "Define signed manifest envelopes, trust anchors, algorithm agility, and revocation policy.",
            "Persist and atomically enforce minimum secure version state across updates and rollback.",
            "Complete independent cryptographic review of the vendored SHA-256 provider and target backend.",
            "Prove live PSM1 file discovery, size bounds, parsing, path selection, and digest binding in PKLOAD2.",
            "Load and authenticate initial-system, recovery, policy, symbols, microcode, firmware, and PooleGlyph artifacts.",
            "Retain exact mappings, construct PBP1, exit boot services, and transfer to PooleKernel.",
            "Qualify target firmware, physical hardware, a second clean builder, signing, ISO, installer, and recovery.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }
    errors = psm1.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
        report = make_readiness(args.toolchain_root.resolve())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(psm1.canonical_json_bytes(report))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, QualificationError) as error:
        print(f"NATIVE_SYSTEM_MANIFEST_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "NATIVE_SYSTEM_MANIFEST_QUALIFICATION PASS "
        f"rust={summary['rust_host_tests_passed']}/{summary['rust_host_tests_total']} "
        f"vectors={summary['golden_vectors_passed']}/{summary['golden_vectors_total']} "
        f"controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} "
        f"differential={summary['differential_cases']} mismatch=0 production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
