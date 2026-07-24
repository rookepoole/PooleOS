#!/usr/bin/env python3
"""Qualify PooleKernel exact retained-byte revalidation (PKREVAL1)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_handoff as pbp1  # noqa: E402
from runtime import native_kernel_revalidation as revalidation  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / revalidation.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
MUTATION_CASES = 32_768


class QualificationError(RuntimeError):
    pass


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    expected_codes: tuple[int, ...] = (0,),
) -> tuple[int, str]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.replace("\r\n", "\n")
    if completed.returncode not in expected_codes:
        raise QualificationError(
            f"command failed ({completed.returncode}): {' '.join(command[:10])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return completed.returncode, output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = json.loads((ROOT / "specs/native-toolchain-lock.json").read_text(encoding="utf-8"))
    channel = lock["toolchain"]["channel"]
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
    for target in ("X86_64_UNKNOWN_NONE", "X86_64_UNKNOWN_UEFI"):
        env[f"CARGO_TARGET_{target}_RUSTFLAGS"] = " ".join(
            ("-Cpanic=abort", '--cfg=sha2_backend="soft"', '--cfg=sha2_backend_soft="compact"', remap)
        )
    _, version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or lock["host"]["triple"] not in version:
        raise QualificationError("workspace-local rustc differs from the lock")
    return cargo, rustc, env


def _cargo(cargo: Path, command: str, *arguments: str) -> list[str]:
    return [
        str(cargo),
        command,
        "--manifest-path",
        str(NATIVE_ROOT / "Cargo.toml"),
        *arguments,
    ]


def _build(toolchain_root: Path, temporary: Path) -> tuple[Path, dict[str, Any], dict[str, str]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    _, fmt_output = _run(
        _cargo(cargo, "fmt", "--package", "poolekernel", "--", "--check"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    host_target = temporary / "host"
    _, test_output = _run(
        _cargo(
            cargo,
            "test",
            "--package",
            "poolekernel",
            "--lib",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(host_target),
            "--",
            "--test-threads=1",
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test_output)
    if match is None or int(match.group(1)) != 79:
        raise QualificationError("expected exactly seventy-nine PooleKernel Rust host tests")
    _run(
        _cargo(
            cargo,
            "build",
            "--package",
            "poolekernel",
            "--features",
            "host-probe",
            "--bin",
            "pkreval1-probe",
            "--target",
            HOST_TARGET,
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(host_target),
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    target_root = temporary / "targets"
    target_results = {}
    for package, binary, target in (
        ("poolekernel", "PooleKernelLinked", "x86_64-unknown-none"),
        ("pooleboot", "PooleBoot", "x86_64-unknown-uefi"),
    ):
        _run(
            _cargo(
                cargo,
                "build",
                "--package",
                package,
                "--bin",
                binary,
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(target_root),
            ),
            cwd=NATIVE_ROOT,
            env=env,
        )
        product = target_root / target / "release" / (binary + (".efi" if target.endswith("uefi") else ""))
        if not product.is_file():
            raise QualificationError(f"target product missing: {product.name}")
        target_results[target] = {
            "package": package,
            "binary": binary,
            "byte_count": product.stat().st_size,
            "sha256": hashlib.sha256(product.read_bytes()).hexdigest().upper(),
        }
    probe = host_target / HOST_TARGET / "release" / "pkreval1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PKREVAL1 host probe is missing")
    return probe, {
        "rustc": rustc.name,
        "host_test_count": 79,
        "format_check": "pass" if not fmt_output.strip() else "pass_with_output",
        "host_probe_sha256": hashlib.sha256(probe.read_bytes()).hexdigest().upper(),
        "targets": target_results,
    }, env


def _write_bundle(root: Path, handoff: bytes, files: Sequence[bytes]) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths = [root / "handoff.pbp"] + [root / f"retained-{index}.bin" for index in range(9)]
    paths[0].write_bytes(handoff)
    for path, data in zip(paths[1:], files, strict=True):
        path.write_bytes(data)
    return paths


def _probe_result(probe: Path, paths: Sequence[Path], *prefix: str) -> tuple[int, str]:
    return _run(
        [str(probe), *prefix, *(str(path) for path in paths)],
        cwd=ROOT,
        env=dict(os.environ),
        expected_codes=(0, 2, 3),
    )


def _reject_code(output: str) -> str:
    matches = re.findall(r"PKREVAL1(?: LOCATOR)? REJECT code=([a-z0-9_]+)", output)
    if not matches:
        raise QualificationError("PKREVAL1 reject marker missing")
    return matches[-1]


def _oracle_code(bundle: revalidation.CanonicalBundle, handoff: bytes, files: Sequence[bytes], bases=None) -> str:
    try:
        revalidation.revalidate_development(
            handoff,
            files,
            bundle.physical_bases if bases is None else bases,
        )
    except revalidation.KernelRevalidationError as error:
        return error.code
    return "pass"


def _controls(
    probe: Path,
    root: Path,
    bundle: revalidation.CanonicalBundle,
) -> list[dict[str, object]]:
    cases: list[tuple[str, bytes, tuple[bytes, ...], tuple[str, ...], tuple[int, ...] | None]] = []
    for index, source in enumerate(bundle.files):
        mutated = bytearray(source)
        mutated[len(mutated) // 2] ^= 0x80
        files = list(bundle.files)
        files[index] = bytes(mutated)
        cases.append((f"NEG-N5-PKREVAL-POST-LOAD-MUTATION-{index + 1:02d}", bundle.handoff, tuple(files), (), None))
    for index, source in enumerate(bundle.files):
        files = list(bundle.files)
        files[index] = source[:-1]
        cases.append((f"NEG-N5-PKREVAL-TRUNCATION-{index + 1:02d}", bundle.handoff, tuple(files), (), None))
    for index, source in enumerate(bundle.files):
        mutated = bytearray(source)
        mutated[-1] ^= 1
        files = list(bundle.files)
        files[index] = bytes(mutated)
        handoff = revalidation.rewrite_file_digest(bundle.handoff, index, files[index])
        cases.append((f"NEG-N5-PKREVAL-DIGEST-REPAIR-{index + 1:02d}", handoff, tuple(files), (), None))
    reordered = list(bundle.files)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    cases.append(("NEG-N5-PKREVAL-ORDER", bundle.handoff, tuple(reordered), (), None))
    cases.append(("NEG-N5-PKREVAL-LOCATOR", bundle.handoff, bundle.files, ("--locator", "0"), (bundle.physical_bases[0] + pbp1.PAGE_BYTES, *bundle.physical_bases[1:])))
    cases.extend(
        (
            (
                "NEG-N5-PKREVAL-WRITABLE",
                revalidation.rewrite_profile_descriptor(
                    bundle.handoff, 1, flags=pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_WRITABLE
                ),
                bundle.files,
                (),
                None,
            ),
            (
                "NEG-N5-PKREVAL-MISSING-HASH",
                revalidation.rewrite_profile_descriptor(bundle.handoff, 1, flags=0),
                bundle.files,
                (),
                None,
            ),
            (
                "NEG-N5-PKREVAL-NONKERNEL-EXECUTABLE",
                revalidation.rewrite_profile_descriptor(
                    bundle.handoff, 1, flags=pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_EXECUTABLE
                ),
                bundle.files,
                (),
                None,
            ),
            (
                "NEG-N5-PKREVAL-OVERLAP",
                revalidation.rewrite_profile_descriptor(
                    bundle.handoff, 2, physical_base=bundle.physical_bases[0]
                ),
                bundle.files,
                (),
                None,
            ),
            (
                "NEG-N5-PKREVAL-EBS-CLEAR",
                revalidation.rewrite_core_boot_flags(bundle.handoff, pbp1.DEVELOPMENT_MODE),
                bundle.files,
                (),
                None,
            ),
            (
                "NEG-N5-PKREVAL-SIZE-SUMMARY",
                revalidation.rewrite_profile_descriptor(
                    bundle.handoff, 1, byte_count=len(bundle.files[0]) + 1
                ),
                bundle.files,
                (),
                None,
            ),
            (
                "NEG-N5-PKREVAL-DIGEST-SUMMARY",
                revalidation.rewrite_profile_descriptor(
                    bundle.handoff, 1, sha256=hashlib.sha256(b"loader summary substitution").digest()
                ),
                bundle.files,
                (),
                None,
            ),
        )
    )
    controls = []
    for identifier, handoff, files, prefix, bases in cases:
        paths = _write_bundle(root, handoff, files)
        returncode, output = _probe_result(probe, paths, *prefix)
        expected = _oracle_code(bundle, handoff, files, bases)
        observed = _reject_code(output)
        if expected == "pass" or observed != expected:
            raise QualificationError(f"{identifier} diverged: Rust={observed} Python={expected}")
        if prefix and returncode != 0:
            raise QualificationError(f"{identifier} locator control did not complete")
        if not prefix and returncode != 2:
            raise QualificationError(f"{identifier} did not reject")
        controls.append(
            {
                "id": identifier,
                "expected": expected,
                "observed": observed,
                "rust_python_match": True,
                "status": "pass",
            }
        )
    return controls


def make_readiness(toolchain_root: Path, status_date: str) -> dict[str, object]:
    contract = revalidation.read_json(ROOT / revalidation.CONTRACT_RELATIVE)
    schema = revalidation.read_json(ROOT / revalidation.SCHEMA_RELATIVE)
    if contract.get("contract_id") != revalidation.CONTRACT_ID:
        raise QualificationError("PKREVAL1 contract ID changed")
    with tempfile.TemporaryDirectory(prefix="pooleos-pkreval1-") as temporary_value:
        temporary = Path(temporary_value)
        probe, build, _ = _build(toolchain_root, temporary)
        bundle = revalidation.canonical_bundle()
        paths = _write_bundle(temporary / "bundle", bundle.handoff, bundle.files)
        _, baseline_output = _probe_result(probe, paths)
        baseline_lines = [line for line in baseline_output.splitlines() if line.startswith("PKREVAL1 PASS")]
        if len(baseline_lines) != 1:
            raise QualificationError("PKREVAL1 golden marker missing")
        golden = revalidation.revalidate_development(
            bundle.handoff, bundle.files, bundle.physical_bases
        )
        _, mutation_output = _probe_result(probe, paths, "--mutations", str(MUTATION_CASES))
        mutation_match = re.search(
            r"PKREVAL1 MUTATION PASS cases=([0-9]+) rejects=([0-9]+) expected_file_digest=([0-9]+) role_coverage=([0-9]+) outcome_fnv1a64=([0-9A-F]{16})",
            mutation_output,
        )
        if mutation_match is None:
            raise QualificationError("PKREVAL1 mutation marker missing")
        rust_differential = {
            "case_count": int(mutation_match.group(1)),
            "reject_count": int(mutation_match.group(2)),
            "expected_file_digest_count": int(mutation_match.group(3)),
            "role_coverage": int(mutation_match.group(4)),
            "outcome_fnv1a64": mutation_match.group(5),
        }
        python_differential = revalidation.mutation_campaign(bundle, MUTATION_CASES)
        if rust_differential != python_differential:
            raise QualificationError("PKREVAL1 Rust/Python differential result changed")
        control_root = temporary / "controls"
        control_root.mkdir()
        controls = _controls(probe, control_root, bundle)
    expected_controls = int(contract["qualification"]["negative_control_count"])
    if len(controls) != expected_controls:
        raise QualificationError(f"PKREVAL1 controls changed: {len(controls)} != {expected_controls}")
    readiness: dict[str, object] = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_revalidation_readiness",
        "status_date": status_date,
        "status": "pass_single_host_fail_closed_non_promoting",
        "contract_id": revalidation.CONTRACT_ID,
        "selected_move_id": revalidation.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "inputs": {
            "contract": revalidation.file_binding(ROOT / revalidation.CONTRACT_RELATIVE),
            "toolchain_lock": revalidation.file_binding(ROOT / "specs/native-toolchain-lock.json"),
            "implementation_inputs": [
                revalidation.file_binding(ROOT / path) for path in revalidation.IMPLEMENTATION_INPUTS
            ],
        },
        "build": build,
        "golden": {
            **golden,
            "handoff_sha256": revalidation.sha256_bytes(bundle.handoff),
            "retained_file_sha256": [revalidation.sha256_bytes(data) for data in bundle.files],
            "rust_marker": baseline_lines[0],
            "rust_python_match": True,
        },
        "negative_controls": controls,
        "differential": rust_differential,
        "claims": contract["claims"],
        "non_claims": contract["non_claims"],
        "open_items": [
            "Replace the ESP PBTS1 development candidate with a selected authenticated PBSTATE1 backend snapshot.",
            "Implement cryptographic policy, revocation, Secure Boot, and monotonic-state evidence under separate key authority.",
            "Execute the PKREVAL1 path after a qualified PooleBoot-to-PooleKernel transfer.",
            "Revoke temporary identity mappings after retained-byte consumption and before capability delegation.",
            "Qualify target firmware, physical hardware, a second builder, signed ISO, installer, and recovery flows."
        ],
    }
    errors = list(validate_json(readiness, schema))
    if errors:
        raise QualificationError("PKREVAL1 readiness schema failed: " + "; ".join(errors[:8]))
    return readiness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-18")
    args = parser.parse_args(argv)
    readiness = make_readiness(args.toolchain_root.resolve(), args.status_date)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(readiness, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        "PKREVAL1 qualification PASS "
        f"controls={len(readiness['negative_controls'])} "
        f"differential={readiness['differential']['case_count']} "
        "authority=0 actions=0 state_writes=0 production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
