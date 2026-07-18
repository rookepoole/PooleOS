#!/usr/bin/env python3
"""Qualify PBP1 layouts, golden bytes, hostile controls, and differential fuzzing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_handoff as pbp1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / pbp1.READINESS_RELATIVE
FUZZ_CASES = 16_384
FUZZ_SEED = 0x5042_5031


class QualificationError(RuntimeError):
    """Raised when a PBP1 qualification step fails closed."""


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
            f"command failed ({completed.returncode}): {' '.join(command[:4])}\n"
            + "\n".join(output.splitlines()[-30:])
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
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _build_codecs(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    host_target = "x86_64-pc-windows-msvc"
    test_target = temporary_root / "host-tests"
    test_output = _run(
        [
            str(cargo), "test", "--manifest-path", str(NATIVE_ROOT / "Cargo.toml"), "--package",
            "poole-handoff", "--lib", "--target", host_target, "--locked", "--offline",
            "--target-dir", str(test_target), "--", "--test-threads=1",
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test_output)
    if match is None or int(match.group(1)) != 8:
        raise QualificationError("expected exactly eight PBP1 Rust host tests")

    target_results = []
    for target in ("x86_64-unknown-uefi", "x86_64-unknown-none"):
        target_dir = temporary_root / f"build-{target}"
        _run(
            [
                str(cargo), "build", "--manifest-path", str(NATIVE_ROOT / "Cargo.toml"), "--package",
                "poole-handoff", "--lib", "--target", target, "--release", "--locked", "--offline",
                "--target-dir", str(target_dir),
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
        artifacts = sorted((target_dir / target / "release" / "deps").glob("libpoole_handoff-*.rlib"))
        if len(artifacts) != 1:
            raise QualificationError(f"expected one no_std rlib for {target}")
        data = artifacts[0].read_bytes()
        target_results.append(
            {"target": target, "status": "pass", "byte_count": len(data), "sha256": pbp1.sha256_bytes(data)}
        )

    probe_target = temporary_root / "host-probe"
    _run(
        [
            str(cargo), "build", "--manifest-path", str(NATIVE_ROOT / "Cargo.toml"), "--package",
            "poole-handoff", "--bin", "pbp1-probe", "--features", "host-probe", "--target", host_target,
            "--release", "--locked", "--offline", "--target-dir", str(probe_target),
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    probe = probe_target / host_target / "release" / "pbp1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PBP1 host probe is missing")
    return probe, {
        "rustc_version_sha256": pbp1.sha256_bytes(
            _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env).encode("utf-8")
        ),
        "rust_host_target": host_target,
        "rust_host_test_count": 8,
        "rust_host_test_pass_count": 8,
        "no_std_target_builds": target_results,
        "layout_assertion_count": 12,
        "host_probe_byte_count": probe.stat().st_size,
        "host_probe_artifact_identity_recorded": False,
        "host_probe_role": "ephemeral host-only differential transport",
    }


def _repair_message(value: bytearray) -> None:
    value[48:52] = b"\0" * 4
    struct.pack_into("<I", value, 48, pbp1._message_crc(bytes(value)))


def _record_geometry(value: bytes, index: int) -> tuple[int, int, int]:
    base = pbp1.HEADER_BYTES + index * pbp1.DESCRIPTOR_BYTES
    offset = struct.unpack_from("<I", value, base + 8)[0]
    length = struct.unpack_from("<I", value, base + 12)[0]
    return base, offset, length


def _repair_record(value: bytearray, index: int) -> None:
    base, offset, length = _record_geometry(value, index)
    struct.pack_into("<I", value, base + 20, pbp1._crc32(bytes(value[offset : offset + length])))
    _repair_message(value)


def _mutated_controls() -> list[tuple[str, str, bytes]]:
    full = pbp1.build_fixture("full_kernel_entry_v1")
    minimal = pbp1.build_fixture("minimal_v1")
    forward = pbp1.build_fixture("forward_optional_v1_1")
    controls: list[tuple[str, str, bytes]] = []

    def add(control_id: str, value: bytearray, *, repair_message: bool = False, repair_record: int | None = None, surface: str = "decode") -> None:
        if repair_record is not None:
            _repair_record(value, repair_record)
        elif repair_message:
            _repair_message(value)
        controls.append((control_id, surface, bytes(value)))

    value = bytearray(full); value[0] ^= 1; add(pbp1.NEGATIVE_CONTROL_IDS[0], value)
    value = bytearray(full); struct.pack_into("<H", value, 8, 0); add(pbp1.NEGATIVE_CONTROL_IDS[1], value, repair_message=True)
    value = bytearray(full); struct.pack_into("<H", value, 8, 2); add(pbp1.NEGATIVE_CONTROL_IDS[2], value, repair_message=True)
    value = bytearray(full); struct.pack_into("<HH", value, 10, 1, 1); add(pbp1.NEGATIVE_CONTROL_IDS[3], value, repair_message=True)
    value = bytearray(full); struct.pack_into("<H", value, 14, 63); add(pbp1.NEGATIVE_CONTROL_IDS[4], value, repair_message=True)
    value = bytearray(full); struct.pack_into("<I", value, 16, len(value) - 8); add(pbp1.NEGATIVE_CONTROL_IDS[5], value, repair_message=True)
    value = bytearray(full); struct.pack_into("<I", value, 52, 1); add(pbp1.NEGATIVE_CONTROL_IDS[6], value, repair_message=True)
    value = bytearray(full); struct.pack_into("<Q", value, 56, 1); add(pbp1.NEGATIVE_CONTROL_IDS[7], value, repair_message=True)
    value = bytearray(full); value[48] ^= 1; add(pbp1.NEGATIVE_CONTROL_IDS[8], value)
    value = bytearray(full); struct.pack_into("<H", value, pbp1.HEADER_BYTES + pbp1.DESCRIPTOR_BYTES, 1); add(pbp1.NEGATIVE_CONTROL_IDS[9], value, repair_message=True)
    value = bytearray(full); base, offset, _ = _record_geometry(value, 1); struct.pack_into("<I", value, base + 8, offset + 8); add(pbp1.NEGATIVE_CONTROL_IDS[10], value, repair_message=True)
    value = bytearray(full); base, _, length = _record_geometry(value, 1); struct.pack_into("<I", value, base + 12, length + 1); add(pbp1.NEGATIVE_CONTROL_IDS[11], value, repair_message=True)
    value = bytearray(full); base, _, _ = _record_geometry(value, 1); value[base + 20] ^= 1; add(pbp1.NEGATIVE_CONTROL_IDS[12], value, repair_message=True)
    value = bytearray(full); base, _, _ = _record_geometry(value, 1); struct.pack_into("<I", value, base + 4, pbp1.RECORD_REQUIRED | pbp1.RECORD_ARRAY | 0x80); add(pbp1.NEGATIVE_CONTROL_IDS[13], value, repair_message=True)
    value = bytearray(forward); base, _, _ = _record_geometry(value, 2); struct.pack_into("<I", value, base + 4, pbp1.RECORD_REQUIRED); add(pbp1.NEGATIVE_CONTROL_IDS[14], value, repair_message=True)
    value = bytearray(forward); struct.pack_into("<H", value, 10, 0); add(pbp1.NEGATIVE_CONTROL_IDS[15], value, repair_message=True)
    value = bytearray(full); features = struct.unpack_from("<Q", value, 32)[0] | (1 << 60); required = struct.unpack_from("<Q", value, 40)[0] | (1 << 60); struct.pack_into("<QQ", value, 32, features, required); add(pbp1.NEGATIVE_CONTROL_IDS[16], value, repair_message=True)
    value = bytearray(minimal); features = struct.unpack_from("<Q", value, 32)[0] & ~pbp1.FEATURE_CORE; required = struct.unpack_from("<Q", value, 40)[0] & ~pbp1.FEATURE_CORE; struct.pack_into("<QQ", value, 32, features, required); add(pbp1.NEGATIVE_CONTROL_IDS[17], value, repair_message=True)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 1); struct.pack_into("<Q", value, offset + pbp1.MEMORY_ENTRY_BYTES, 0x000F_8000); add(pbp1.NEGATIVE_CONTROL_IDS[18], value, repair_record=1)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 1); struct.pack_into("<Q", value, offset + 8, 0); add(pbp1.NEGATIVE_CONTROL_IDS[19], value, repair_record=1)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 2); struct.pack_into("<I", value, offset + 24, 1000); add(pbp1.NEGATIVE_CONTROL_IDS[20], value, repair_record=2)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 3); value[offset + 40 : offset + 56] = value[offset : offset + 16]; add(pbp1.NEGATIVE_CONTROL_IDS[21], value, repair_record=3)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 4); value[offset + 48 : offset + 80] = b"\0" * 32; add(pbp1.NEGATIVE_CONTROL_IDS[22], value, repair_record=4)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 4); struct.pack_into("<Q", value, offset + 8, 0x0040_0000); add(pbp1.NEGATIVE_CONTROL_IDS[23], value, repair_record=4)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 5); value[offset] = 0xFF; add(pbp1.NEGATIVE_CONTROL_IDS[24], value, repair_record=5)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 6); struct.pack_into("<QQ", value, offset + 32, 0xFFFF_FFFF_FFFF_FFF0, 0x100); add(pbp1.NEGATIVE_CONTROL_IDS[25], value, repair_record=6)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 7); value[offset + 8 : offset + 72] = b"\0" * 64; add(pbp1.NEGATIVE_CONTROL_IDS[26], value, repair_record=7)
    value = bytearray(full); _, offset, length = _record_geometry(value, 8); value[offset + length - 1] = 0xFF; add(pbp1.NEGATIVE_CONTROL_IDS[27], value, repair_record=8)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 9); struct.pack_into("<I", value, offset + 36, 8192); add(pbp1.NEGATIVE_CONTROL_IDS[28], value, repair_record=9)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 10); struct.pack_into("<QQ", value, offset + 16, 2_000_000, 1_000_000); add(pbp1.NEGATIVE_CONTROL_IDS[29], value, repair_record=10)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 11); value[offset + 24 : offset + 56] = b"\0" * 32; add(pbp1.NEGATIVE_CONTROL_IDS[30], value, repair_record=11)
    value = bytearray(full); _, offset, _ = _record_geometry(value, 0); flags = struct.unpack_from("<Q", value, offset)[0] & ~pbp1.BOOT_SERVICES_EXITED; struct.pack_into("<Q", value, offset, flags); add(pbp1.NEGATIVE_CONTROL_IDS[31], value, repair_record=0, surface="kernel_profile")
    if [item[0] for item in controls] != list(pbp1.NEGATIVE_CONTROL_IDS):
        raise QualificationError("negative control construction order changed")
    return controls


def _probe(probe: Path, cases: list[tuple[bytes, bool]], env: dict[str, str]) -> list[bool]:
    input_text = "".join(("K:" if kernel else "") + value.hex() + "\n" for value, kernel in cases)
    output = _run([str(probe)], cwd=ROOT, env=env, input_text=input_text)
    lines = [line.strip() for line in output.splitlines()]
    if len(lines) != len(cases) or any(line not in {"OK", "ERR"} for line in lines):
        raise QualificationError("Rust probe returned malformed result count")
    return [line == "OK" for line in lines]


def _run_controls(probe: Path, env: dict[str, str]) -> tuple[list[dict[str, Any]], list[bytes]]:
    source = _mutated_controls()
    rust_results = _probe(probe, [(value, surface == "kernel_profile") for _, surface, value in source], env)
    results = []
    corpus = []
    for (control_id, surface, value), rust_accepted in zip(source, rust_results, strict=True):
        python_accepted = False
        try:
            handoff = pbp1.decode(value)
            if surface == "kernel_profile":
                pbp1.validate_kernel_entry_profile(handoff)
            python_accepted = True
        except pbp1.BootHandoffError:
            pass
        if python_accepted or rust_accepted:
            raise QualificationError(f"negative control was accepted: {control_id}")
        results.append(
            {
                "id": control_id,
                "surface": surface,
                "expected": "reject",
                "python_observed": "reject",
                "rust_observed": "reject",
                "status": "pass",
                "input_sha256": pbp1.sha256_bytes(value),
                "input_byte_count": len(value),
            }
        )
        corpus.append(value)
    return results, corpus


def _fuzz_cases() -> list[bytes]:
    bases = [
        pbp1.build_fixture("full_kernel_entry_v1"),
        pbp1.build_fixture("minimal_v1"),
        pbp1.build_fixture("forward_optional_v1_1"),
    ]
    state = FUZZ_SEED

    def next_u32() -> int:
        nonlocal state
        state = (state * 1_664_525 + 1_013_904_223) & 0xFFFF_FFFF
        return state

    cases: list[bytes] = []
    for index in range(FUZZ_CASES):
        base = bases[next_u32() % len(bases)]
        mode = index % 6
        value = bytearray(base)
        if mode == 0:
            position = next_u32() % len(value)
            value[position] ^= 1 << (next_u32() % 8)
        elif mode == 1:
            value = value[: next_u32() % (len(value) + 1)]
        elif mode == 2:
            position = next_u32() % len(value)
            value[position] = next_u32() & 0xFF
            if len(value) >= pbp1.HEADER_BYTES:
                _repair_message(value)
        elif mode == 3:
            try:
                handoff = pbp1.decode(bytes(value))
                record_index = next_u32() % len(handoff.records)
                record = handoff.records[record_index]
                position = record.offset + next_u32() % record.length
                value[position] ^= 1 << (next_u32() % 8)
                _repair_record(value, record_index)
            except pbp1.BootHandoffError:
                pass
        elif mode == 4:
            position = next_u32() % pbp1.HEADER_BYTES
            value[position] ^= next_u32() & 0xFF
            _repair_message(value)
        else:
            value.extend(struct.pack("<I", next_u32()))
        cases.append(bytes(value))
    return cases


def _run_fuzz(probe: Path, env: dict[str, str]) -> dict[str, Any]:
    cases = _fuzz_cases()
    python_results = []
    for value in cases:
        try:
            pbp1.decode(value)
            python_results.append(True)
        except pbp1.BootHandoffError:
            python_results.append(False)
    rust_results = _probe(probe, [(value, False) for value in cases], env)
    mismatches = [index for index, (python, rust) in enumerate(zip(python_results, rust_results, strict=True)) if python != rust]
    if mismatches:
        raise QualificationError(f"Rust/Python differential mismatch at case {mismatches[0]}")
    digest = hashlib.sha256()
    for value, accepted in zip(cases, python_results, strict=True):
        digest.update(struct.pack("<I?", len(value), accepted))
        digest.update(value)
    return {
        "algorithm": "LCG plus deterministic structural, truncation, checksum, payload, and extension mutations",
        "seed": f"0x{FUZZ_SEED:08X}",
        "case_count": len(cases),
        "python_accept_count": sum(python_results),
        "python_reject_count": len(cases) - sum(python_results),
        "rust_accept_count": sum(rust_results),
        "rust_reject_count": len(cases) - sum(rust_results),
        "differential_mismatch_count": 0,
        "corpus_and_outcome_sha256": digest.hexdigest().upper(),
        "corpus_published": False,
    }


def qualify(toolchain_root: Path, temporary_root: Path) -> dict[str, Any]:
    contract = pbp1.read_json(ROOT / pbp1.CONTRACT_RELATIVE)
    golden = pbp1.read_json(ROOT / pbp1.GOLDEN_RELATIVE)
    contract_issues = pbp1.contract_errors(contract)
    golden_issues = pbp1.golden_errors(golden)
    if contract_issues or golden_issues:
        raise QualificationError("; ".join((contract_issues + golden_issues)[:12]))
    probe, codec = _build_codecs(toolchain_root, temporary_root)
    _, _, env = _toolchain(toolchain_root)

    vector_results = []
    probe_cases: list[tuple[bytes, bool]] = []
    for item in golden["vectors"]:
        data = bytes.fromhex(item["hex"])
        handoff = pbp1.decode(data)
        if item["kernel_entry_profile"]:
            pbp1.validate_kernel_entry_profile(handoff)
        probe_cases.append((data, bool(item["kernel_entry_profile"])))
    rust_vectors = _probe(probe, probe_cases, env)
    if not all(rust_vectors):
        raise QualificationError("Rust decoder rejected a golden vector")
    for item in golden["vectors"]:
        vector_results.append(
            {
                "id": item["id"],
                "sha256": item["sha256"],
                "byte_count": item["byte_count"],
                "python_decode": "pass",
                "rust_decode": "pass",
                "kernel_entry_profile": item["kernel_entry_profile"],
                "synthetic": True,
            }
        )

    controls, malformed = _run_controls(probe, env)
    fuzz = _run_fuzz(probe, env)
    malformed_digest = hashlib.sha256()
    for value in malformed:
        malformed_digest.update(struct.pack("<I", len(value)))
        malformed_digest.update(value)

    readiness = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_boot_handoff_readiness",
        "status_date": "2026-07-16",
        "status": "pass_single_host_synthetic_non_promoting",
        "contract_id": "PBP1",
        "selected_move_id": "N5-BOOTPROTO-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.8": "partial"},
        "bindings": {
            "contract": pbp1.file_binding(ROOT / pbp1.CONTRACT_RELATIVE),
            "contract_schema": pbp1.file_binding(ROOT / pbp1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": pbp1.file_binding(ROOT / pbp1.GOLDEN_RELATIVE),
            "golden_schema": pbp1.file_binding(ROOT / pbp1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": pbp1.file_binding(ROOT / pbp1.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": [pbp1.file_binding(ROOT / path) for path in pbp1.IMPLEMENTATION_INPUTS],
        },
        "codec_qualification": codec,
        "golden_vectors": vector_results,
        "negative_controls": controls,
        "differential_fuzz": {
            **fuzz,
            "malformed_control_count": len(malformed),
            "malformed_control_corpus_sha256": malformed_digest.hexdigest().upper(),
        },
        "claims": pbp1.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 8,
            "rust_host_tests_total": 8,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "layout_assertions_passed": 12,
            "golden_vectors_matched": 3,
            "golden_vectors_total": 3,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(pbp1.NEGATIVE_CONTROL_IDS),
            "differential_fuzz_cases": fuzz["case_count"],
            "differential_mismatches": fuzz["differential_mismatch_count"],
            "production_claim_count": 0,
        },
        "open_items": [
            "Retain the live PBP1 container only after kernel mappings, final memory-map capture, and ExitBootServices retry policy are implemented.",
            "Implement the PooleKernel PBP1 intake path with read-only mapping, early copy policy, serial-first rejection, and exact entry assembly.",
            "Cross-check normalized memory-map records against captured UEFI descriptor streams, including larger future descriptor sizes.",
            "Exercise the final GetMemoryMap and ExitBootServices retry loop under malformed and map-changing firmware fixtures.",
            "Bind PBP1 loaded-artifact roles to the signed system-manifest, rollback, measurement, and recovery contracts.",
            "Add coverage-guided native fuzzing, sanitizer/Miri-equivalent host checks where supported, and independent security review.",
            "Reproduce qualification on a second clean builder and target firmware.",
            "Cryptographically ratify the ABI only through the separately approved owner signing and release process.",
        ],
        "claim_boundary": [
            "The full kernel-entry vector is synthetic and does not prove successful ExitBootServices or PooleKernel execution.",
            "The Rust library compiles for UEFI and freestanding targets; PKLOAD5 separately proves retained post-exit development PBP1 plus PKMAP2/PBEXIT1 stop-before-transfer behavior, while this standalone receipt does not claim a transferable live handoff.",
            "The Python implementation is an independent host oracle and is prohibited from the production boot chain.",
            "CRC-32 is corruption detection, not authentication or signed-manifest verification.",
            "Finite negative and deterministic fuzz corpora do not prove correctness for all byte strings or hardware states.",
            "No target firmware, physical media, Secure Boot, TPM, signature, loader, or kernel transfer was exercised.",
            "No N5 exit, production readiness, signing, merge, tag, release, or publication authority follows.",
        ],
    }
    issues = pbp1.readiness_errors(readiness)
    if issues:
        raise QualificationError("; ".join(issues[:12]))
    return readiness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="pooleos-pbp1-") as temporary:
            readiness = qualify(args.toolchain_root.resolve(), Path(temporary))
        pbp1.write_json(readiness, args.out)
        summary = readiness["summary"]
        print(
            f"wrote {args.out}: tests={summary['rust_host_tests_passed']}/8 "
            f"targets={summary['no_std_target_builds_passed']}/2 vectors={summary['golden_vectors_matched']}/3 "
            f"negatives={summary['negative_controls_passed']}/32 fuzz={summary['differential_fuzz_cases']} "
            f"mismatches={summary['differential_mismatches']}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, QualificationError, pbp1.BootHandoffError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
