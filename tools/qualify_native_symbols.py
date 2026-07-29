#!/usr/bin/env python3
"""Qualify PSYM1 parsing, lookup, privacy, identity, and split-debug correspondence."""

from __future__ import annotations

import argparse
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
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_kernel_image as kernel_image  # noqa: E402
from runtime import native_symbols as psym1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / psym1.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
PRODUCT_TARGET = "x86_64-unknown-none"
PARSER_DIFFERENTIAL_CASES = 16_384
LOOKUP_DIFFERENTIAL_CASES = 16_384
PARSER_SEED = 0x5053_594D_3101
LOOKUP_SEED = 0x5053_594D_3102


class QualificationError(RuntimeError):
    """Raised when PSYM1 qualification fails closed."""


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
    lock = psym1.read_json(ROOT / "specs/native-toolchain-lock.json")
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
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _cargo(cargo: Path, *arguments: str) -> list[str]:
    command, *remaining = arguments
    return [
        str(cargo),
        command,
        "--manifest-path",
        str(NATIVE_ROOT / "Cargo.toml"),
        *remaining,
    ]


def _build_validators(
    toolchain_root: Path, temporary_root: Path
) -> tuple[Path, dict[str, Any], Path, dict[str, str]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    test_output = _run(
        _cargo(
            cargo,
            "test",
            "--package",
            "poole-symbols",
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
        raise QualificationError("expected exactly four PSYM1 Rust host tests")
    _run(
        _cargo(cargo, "fmt", "--package", "poole-symbols", "--", "--check"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        _cargo(
            cargo,
            "clippy",
            "--package",
            "poole-symbols",
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
    for target in ("x86_64-unknown-none", "x86_64-unknown-uefi"):
        _run(
            _cargo(
                cargo,
                "build",
                "--package",
                "poole-symbols",
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
            "poole-symbols",
            "--features",
            "host-probe",
            "--bin",
            "psym1-probe",
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
    probe = temporary_root / "probe" / HOST_TARGET / "debug" / "psym1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PSYM1 host probe is missing")
    return (
        probe,
        {
            "status": "pass",
            "rustc": _run([str(rustc), "--version"], cwd=ROOT, env=env).strip(),
            "host_tests": 4,
            "rustfmt_packages": 1,
            "clippy_targets": 1,
            "no_std_targets": ["x86_64-unknown-none", "x86_64-unknown-uefi"],
        },
        cargo,
        env,
    )


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
        raise QualificationError(f"PSYM1 probe failed: {completed.stderr[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError("PSYM1 probe response count mismatch")
    return lines


def _parse_result(data: bytes) -> str:
    try:
        bundle = psym1.parse(data)
    except psym1.SymbolError as error:
        return f"ERR:{error.code}"
    body = bundle.raw[304:336].hex().upper()
    return (
        f"OK;version=1.0;bytes={len(data)};segments={len(bundle.segments)};"
        f"symbols={len(bundle.symbols)};strings={sum(len(item.name) for item in bundle.symbols)};"
        f"image={bundle.image_bytes};entry={bundle.entry_offset:X};body={body}"
    )


def _lookup_result(data: bytes, runtime_base: int, runtime_address: int) -> str:
    try:
        bundle = psym1.parse(data)
        result = psym1.lookup(bundle, runtime_base, runtime_address)
    except psym1.SymbolError as error:
        return f"ERR:{error.code}"
    if result is None:
        return "MISS"
    return (
        f"OK;id={result.symbol.symbol_id};name={result.symbol.name};"
        f"offset={result.symbol_offset:X};steps={result.steps}"
    )


def _qualify_golden(probe: Path, golden: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[str] = []
    expected: list[str] = []
    for vector in golden["vectors"]:
        data = bytes.fromhex(vector["bundle_hex"])
        requests.append(f"P:{data.hex().upper()}")
        expected.append(_parse_result(data))
        for sample in vector["lookup_samples"]:
            requests.append(
                f"L:{data.hex().upper()}:{sample['runtime_base']:X}:{sample['runtime_address']:X}"
            )
            expected.append(
                _lookup_result(data, sample["runtime_base"], sample["runtime_address"])
            )
    observed = _probe_lines(probe, requests)
    if observed != expected:
        index = next(i for i, pair in enumerate(zip(expected, observed, strict=True)) if pair[0] != pair[1])
        raise QualificationError(
            f"PSYM1 golden mismatch {index}: Python={expected[index]} Rust={observed[index]}"
        )
    return [
        {
            "id": vector["id"],
            "bundle_sha256": vector["bundle_sha256"],
            "lookup_sample_count": len(vector["lookup_samples"]),
            "python_result": "pass",
            "rust_result": "pass",
            "status": "pass",
        }
        for vector in golden["vectors"]
    ]


def _mutated_bundle(rng: random.Random, case: int) -> bytes:
    templates = (psym1.canonical_bundle(), psym1.minimal_bundle(), psym1.boundary_bundle())
    output = bytearray(templates[case % len(templates)])
    if case % 257 == 0:
        return bytes(output)
    operation = rng.randrange(8)
    if operation == 0:
        return bytes(output[: rng.randrange(len(output))])
    if operation == 1:
        output.extend(rng.randbytes(1 + rng.randrange(4)))
        return bytes(output)
    if operation == 2:
        output = bytearray(rng.randbytes(rng.randrange(psym1.HEADER_BYTES + 64)))
        return bytes(output)
    positions: list[int] = []
    if operation in (3, 4):
        positions.append(rng.randrange(psym1.HEADER_BYTES))
    else:
        positions.append(rng.randrange(psym1.HEADER_BYTES, len(output)))
    for _ in range(rng.randrange(3)):
        positions.append(rng.randrange(len(output)))
    for position in positions:
        output[position] ^= 1 << rng.randrange(8)
    if operation in (6, 7) and len(output) >= psym1.HEADER_BYTES:
        output[304:336] = hashlib.sha256(output[psym1.HEADER_BYTES :]).digest()
    return bytes(output)


def _qualify_parser_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(PARSER_SEED)
    requests: list[str] = []
    expected: list[str] = []
    accepted = 0
    rejected = 0
    for case in range(PARSER_DIFFERENTIAL_CASES):
        data = _mutated_bundle(rng, case)
        requests.append(f"P:{data.hex().upper()}")
        result = _parse_result(data)
        expected.append(result)
        accepted += int(result.startswith("OK;"))
        rejected += int(result.startswith("ERR:"))
    observed = _probe_lines(probe, requests)
    for index, (python_result, rust_result) in enumerate(zip(expected, observed, strict=True)):
        if python_result != rust_result:
            raise QualificationError(
                f"PSYM1 parser differential mismatch {index}: Python={python_result} Rust={rust_result}"
            )
    if accepted == 0 or rejected == 0:
        raise QualificationError("PSYM1 parser campaign lacks acceptance or rejection coverage")
    return {
        "campaign_id": "PSYM1-PARSER-DIFF-1",
        "seed": f"0x{PARSER_SEED:X}",
        "case_count": len(requests),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "digest_repaired_deep_mutations": True,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def _qualify_lookup_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(LOOKUP_SEED)
    bundles = tuple(psym1.parse(item) for item in (psym1.canonical_bundle(), psym1.minimal_bundle(), psym1.boundary_bundle()))
    requests: list[str] = []
    expected: list[str] = []
    hits = 0
    misses = 0
    rejects = 0
    for case in range(LOOKUP_DIFFERENTIAL_CASES):
        bundle = bundles[case % len(bundles)]
        slide_count = rng.randrange(32)
        base = bundle.preferred_virtual_base + slide_count * bundle.slide_alignment
        mode = rng.randrange(8)
        if mode == 0:
            base += 1
        if mode == 1:
            address = base - 1
        elif mode == 2:
            address = base + bundle.image_bytes
        elif mode in (3, 4):
            symbol = bundle.symbols[rng.randrange(len(bundle.symbols))]
            address = base + symbol.start_offset + rng.randrange(symbol.byte_count)
        else:
            address = base + rng.randrange(bundle.image_bytes)
        result = _lookup_result(bundle.raw, base, address)
        requests.append(f"L:{bundle.raw.hex().upper()}:{base:X}:{address:X}")
        expected.append(result)
        hits += int(result.startswith("OK;"))
        misses += int(result == "MISS")
        rejects += int(result.startswith("ERR:"))
    observed = _probe_lines(probe, requests)
    for index, (python_result, rust_result) in enumerate(zip(expected, observed, strict=True)):
        if python_result != rust_result:
            raise QualificationError(
                f"PSYM1 lookup differential mismatch {index}: Python={python_result} Rust={rust_result}"
            )
    if min(hits, misses, rejects) == 0:
        raise QualificationError("PSYM1 lookup campaign lacks hit, miss, or rejection coverage")
    return {
        "campaign_id": "PSYM1-LOOKUP-DIFF-1",
        "seed": f"0x{LOOKUP_SEED:X}",
        "case_count": len(requests),
        "hit_count": hits,
        "miss_count": misses,
        "rejected_count": rejects,
        "mismatch_count": 0,
        "maximum_observed_steps": max(
            (
                int(result.rsplit("=", 1)[1])
                for result in expected
                if result.startswith("OK;")
            ),
            default=0,
        ),
        "corpus_published": False,
        "status": "pass",
    }


def _activation_expected(mode: str, data: bytes) -> str:
    bundle = psym1.parse(data)
    context = psym1.synthetic_qualified_consumption_context(bundle)
    mutations = {
        "outer-signature": {"outer_signature_verified": False},
        "inner-signature": {"inner_signature_verified": False},
        "manifest-signature": {"manifest_signature_verified": False},
        "kernel-signature": {"kernel_signature_verified": False},
        "role": {"outer_role": 3},
        "version": {"outer_version": 2},
        "payload-digest": {"outer_payload_sha256": "0" * 64},
        "file-digest": {"expected_outer_file_sha256": "B" * 64},
        "canonical-identity": {"canonical_file_sha256": "B" * 64},
        "loaded-identity": {"preferred_loaded_sha256": "B" * 64},
        "build-id": {"build_id_sha256": "B" * 64},
        "debug-identity": {"debug_file_sha256": "B" * 64},
        "source-identity": {"source_manifest_sha256": "B" * 64},
        "identity-evidence": {"identity_evidence_verified": False},
        "stripped-correspondence": {"stripped_correspondence_verified": False},
        "dwarf5": {"dwarf5_verified": False},
        "public-policy": {"public_policy_verified": False},
        "source-paths": {"source_paths_absent": False},
        "pointer-redaction": {"pointer_redaction_enabled": False},
        "diagnostics-authority": {"diagnostics_authorized": False},
        "runtime-base": {"runtime_base": bundle.preferred_virtual_base + 1},
        "symbol-capacity": {"symbol_capacity": 0},
        "string-capacity": {"string_capacity": 0},
        "lookup-capacity": {"lookup_step_capacity": 0},
        "authority-effect": {"authority_effect_requested": True},
    }
    if mode == "development":
        context = psym1.development_consumption_context(bundle)
    elif mode != "qualified":
        import dataclasses

        context = dataclasses.replace(context, **mutations[mode])
    try:
        psym1.authorize_consumption(bundle, context)
    except psym1.SymbolError as error:
        return f"ERR:{error.code}"
    return "OK:activation"


def _qualify_negative_controls(probe: Path, debug_data: bytes) -> list[dict[str, Any]]:
    canonical = psym1.canonical_bundle()
    controls: list[tuple[str, str, str]] = []
    rng = random.Random(0x5053_594D_31FF)
    requests: list[str] = []
    parser_control_count = 0
    attempts = 0
    while parser_control_count < 128:
        attempts += 1
        if attempts > 4096:
            raise QualificationError("could not construct 128 rejecting parser controls")
        mutated = bytearray(canonical)
        position = rng.randrange(len(mutated))
        mutated[position] ^= 1 << rng.randrange(8)
        if attempts % 2 == 0 and position >= psym1.HEADER_BYTES:
            mutated[304:336] = hashlib.sha256(mutated[psym1.HEADER_BYTES :]).digest()
        data = bytes(mutated)
        expected = _parse_result(data)
        if not expected.startswith("ERR:"):
            continue
        parser_control_count += 1
        requests.append(f"P:{data.hex().upper()}")
        controls.append(
            (f"NEG-PSYM1-PARSER-{parser_control_count:03d}", "parser", expected)
        )
    activation_modes = (
        "development",
        "outer-signature",
        "inner-signature",
        "manifest-signature",
        "kernel-signature",
        "role",
        "version",
        "payload-digest",
        "file-digest",
        "canonical-identity",
        "loaded-identity",
        "build-id",
        "debug-identity",
        "source-identity",
        "identity-evidence",
        "stripped-correspondence",
        "dwarf5",
        "public-policy",
        "source-paths",
        "pointer-redaction",
        "diagnostics-authority",
        "runtime-base",
        "symbol-capacity",
        "string-capacity",
        "lookup-capacity",
        "authority-effect",
    )
    for index, mode in enumerate(activation_modes, start=1):
        expected = _activation_expected(mode, canonical)
        if not expected.startswith("ERR:"):
            raise QualificationError(f"negative activation control {mode} remained valid")
        requests.append(f"A:{mode}:{canonical.hex().upper()}")
        controls.append((f"NEG-PSYM1-ACTIVATION-{index:03d}", "activation", expected))
    observed = _probe_lines(probe, requests)
    for index, ((control_id, surface, expected), result) in enumerate(
        zip(controls, observed, strict=True)
    ):
        if result != expected:
            raise QualificationError(
                f"{control_id} mismatch {index}: expected={expected} observed={result}"
            )
        controls[index] = (control_id, surface, result)

    debug_controls = (
        ("NEG-PSYM1-DEBUG-TRUNCATED", debug_data[:20], "psym_debug_elf_size"),
        ("NEG-PSYM1-DEBUG-MAGIC", b"X" + debug_data[1:], "psym_debug_elf_ident"),
        (
            "NEG-PSYM1-DEBUG-TYPE",
            debug_data[:16] + struct.pack("<H", 2) + debug_data[18:],
            "psym_debug_elf_header",
        ),
        (
            "NEG-PSYM1-DEBUG-HOST-PATH",
            debug_data + b"C:\\Users\\private",
            "psym_debug_host_path",
        ),
    )
    output = [
        {"id": control_id, "surface": surface, "expected": result, "observed": result, "status": "pass"}
        for control_id, surface, result in controls
    ]
    for control_id, data, expected in debug_controls:
        try:
            psym1.inspect_debug_elf(data)
        except psym1.SymbolError as error:
            observed_error = error.code
        else:
            raise QualificationError(f"{control_id} was accepted")
        if observed_error != expected:
            raise QualificationError(
                f"{control_id}: expected={expected} observed={observed_error}"
            )
        output.append(
            {"id": control_id, "surface": "debug_elf", "expected": expected, "observed": expected, "status": "pass"}
        )
    return output


def _product_flags(*, dwarf5: bool) -> list[str]:
    linker_script = (NATIVE_ROOT / "kernel" / "linker.ld").resolve()
    flags = [
        "-Cpanic=abort",
        "-Crelocation-model=pic",
        "-Ccode-model=small",
        "-Cforce-frame-pointers=yes",
        "-Cno-redzone=yes",
        "-Clink-arg=-pie",
        "-Clink-arg=--no-dynamic-linker",
        "-Clink-arg=--no-eh-frame-hdr",
        "-Clink-arg=--build-id=none",
        "-Clink-arg=--gc-sections",
        f"-Clink-arg=-T{linker_script}",
        "-Clink-arg=--entry=poole_kernel_entry",
        f"--remap-path-prefix={ROOT.resolve()}=/pooleos",
    ]
    flags.append("-Cdwarf-version=5")
    return flags


def _build_kernel(
    cargo: Path,
    base_env: dict[str, str],
    target_dir: Path,
    *,
    dwarf5: bool,
) -> bytes:
    env = dict(base_env)
    env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(_product_flags(dwarf5=dwarf5))
    env["CARGO_PROFILE_RELEASE_DEBUG"] = "2"
    env["CARGO_PROFILE_RELEASE_STRIP"] = "none" if dwarf5 else "symbols"
    _run(
        _cargo(
            cargo,
            "build",
            "--package",
            "poolekernel",
            "--bin",
            "PooleKernelLinked",
            "--target",
            PRODUCT_TARGET,
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(target_dir),
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    path = target_dir / PRODUCT_TARGET / "release" / "PooleKernelLinked"
    if not path.is_file():
        raise QualificationError("linked PooleKernel product is missing")
    return path.read_bytes()


def _section_names(data: bytes) -> set[str]:
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    section_count = struct.unpack_from("<H", data, 60)[0]
    string_index = struct.unpack_from("<H", data, 62)[0]
    rows = [
        struct.unpack_from("<IIQQQQIIQQ", data, section_offset + index * 64)
        for index in range(section_count)
    ]
    strings_row = rows[string_index]
    strings = data[strings_row[4] : strings_row[4] + strings_row[5]]
    names = set()
    for index, row in enumerate(rows):
        if index == 0:
            continue
        end = strings.find(b"\0", row[0])
        if end < 0:
            raise QualificationError("linked kernel has malformed section names")
        names.add(strings[row[0] : end].decode("ascii"))
    return names


def _qualify_debug_correspondence(
    cargo: Path, env: dict[str, str], temporary_root: Path
) -> tuple[dict[str, Any], bytes]:
    debug_one = _build_kernel(cargo, env, temporary_root / "debug-a", dwarf5=True)
    debug_two = _build_kernel(cargo, env, temporary_root / "debug-b", dwarf5=True)
    if debug_one != debug_two:
        raise QualificationError("split-debug PooleKernel builds are not byte-reproducible")
    debug = psym1.inspect_debug_elf(debug_one)
    if debug.byte_count != psym1.CANONICAL_DEBUG_BYTES or debug.sha256 != psym1.CANONICAL_DEBUG_SHA256:
        raise QualificationError("split-debug PooleKernel identity changed")
    if psym1.public_symbols_from_debug(debug) != psym1.canonical_symbols():
        raise QualificationError("split-debug public symbols changed")
    stripped_linked = _build_kernel(cargo, env, temporary_root / "stripped", dwarf5=False)
    stripped_sections = _section_names(stripped_linked)
    if ".symtab" in stripped_sections or any(name.startswith(".debug") for name in stripped_sections):
        raise QualificationError("stripped PooleKernel retained symbols or debug sections")
    canonical_debug, debug_plan = kernel_image.canonicalize_linked_image(debug_one)
    if psym1.sha256_bytes(canonical_debug) != psym1.CANONICAL_FILE_SHA256:
        raise QualificationError("debug-derived canonical PKELF1 identity changed")
    manifest_data = (NATIVE_ROOT / "kernel" / "manifest.pkm").read_bytes()
    if psym1.sha256_bytes(manifest_data) != psym1.CANONICAL_SOURCE_MANIFEST_SHA256:
        raise QualificationError("kernel source-manifest identity changed")
    derived = psym1.bundle_from_debug(
        debug_one,
        canonical_debug,
        psym1.CANONICAL_LOADED_SHA256,
        manifest_data,
        psym1.CANONICAL_BUILD_ID,
    )
    if derived != psym1.canonical_bundle():
        raise QualificationError("debug-derived PSYM1 bytes differ from the canonical bundle")
    return (
        {
            "status": "pass",
            "debug_build_count": 2,
            "debug_builds_byte_identical": True,
            "debug_file_byte_count": len(debug_one),
            "debug_file_sha256": psym1.sha256_bytes(debug_one),
            "dwarf_compilation_unit_count": len(debug.dwarf_versions),
            "pooleos_leading_dwarf5_unit_count": 3,
            "observed_dwarf_versions": sorted(set(debug.dwarf_versions)),
            "required_section_count": len(psym1.REQUIRED_DWARF5_SECTIONS),
            "public_symbol_count": len(psym1.canonical_symbols()),
            "canonical_file_byte_count": len(canonical_debug),
            "canonical_file_sha256": psym1.sha256_bytes(canonical_debug),
            "canonical_image_byte_count": debug_plan.image_byte_count,
            "canonical_entry_offset": debug_plan.entry_offset,
            "stripped_and_debug_plans_equal": False,
            "stripped_symtab_absent": ".symtab" not in stripped_sections,
            "stripped_debug_sections_absent": not any(name.startswith(".debug") for name in stripped_sections),
            "source_paths_absent": True,
            "debug_file_staged_on_boot_media": False,
            "debug_derived_bundle_sha256": psym1.sha256_bytes(derived),
        },
        debug_one,
    )


def expected_readiness_claims() -> dict[str, bool]:
    return {
        "format_frozen": True,
        "python_oracle_implemented": True,
        "no_std_parser_implemented": True,
        "bounded_lookup_implemented": True,
        "split_debug_correspondence_qualified": True,
        "development_activation_denied": True,
        "symbol_consumption_enabled": False,
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "kernel_export_authority_created": False,
        "full_debug_file_on_boot_media": False,
        "runtime_addresses_disclosed_by_default": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = psym1.read_json(ROOT / psym1.CONTRACT_RELATIVE)
    golden = psym1.read_json(ROOT / psym1.GOLDEN_RELATIVE)
    errors = psym1.contract_errors(contract) + psym1.golden_errors(golden)
    if errors:
        raise QualificationError("; ".join(errors))
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="psym1-", dir=ROOT / "tmp") as temporary:
        temporary_root = Path(temporary)
        probe, validators, cargo, env = _build_validators(toolchain_root, temporary_root)
        golden_results = _qualify_golden(probe, golden)
        debug_correspondence, debug_data = _qualify_debug_correspondence(
            cargo, env, temporary_root
        )
        controls = _qualify_negative_controls(probe, debug_data)
        parser_diff = _qualify_parser_differential(probe)
        lookup_diff = _qualify_lookup_differential(probe)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_symbol_readiness",
        "status_date": "2026-07-18",
        "status": "pass",
        "contract_id": psym1.CONTRACT_ID,
        "selected_move_id": "N5-SYMBOLS-SEMANTICS-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.6": "partial", "N5.9": "partial"},
        "bindings": {
            "contract": psym1._binding_record(ROOT / psym1.CONTRACT_RELATIVE),
            "contract_schema": psym1._binding_record(ROOT / psym1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": psym1._binding_record(ROOT / psym1.GOLDEN_RELATIVE),
            "golden_schema": psym1._binding_record(ROOT / psym1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": psym1._binding_record(ROOT / psym1.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": psym1.implementation_bindings(),
        },
        "validator_qualification": validators,
        "golden_vectors": golden_results,
        "debug_correspondence": debug_correspondence,
        "negative_controls": controls,
        "parser_differential": parser_diff,
        "lookup_differential": lookup_diff,
        "activation_qualification": {
            "status": "pass",
            "synthetic_all_true_result": "OK:activation",
            "synthetic_all_true_context_is_trust_evidence": False,
            "current_unsigned_development_activation_allowed": False,
            "individual_rejecting_context_count": 26,
        },
        "claims": expected_readiness_claims(),
        "summary": {
            "rust_host_tests_passed": 4,
            "rust_host_tests_total": 4,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "golden_vectors_matched": len(golden_results),
            "golden_vectors_total": len(golden_results),
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "parser_differential_cases": parser_diff["case_count"],
            "lookup_differential_cases": lookup_diff["case_count"],
            "differential_mismatches": 0,
            "debug_reproducible_builds": debug_correspondence["debug_build_count"],
            "public_symbols": debug_correspondence["public_symbol_count"],
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PSYM1 before declaring a stable symbol ABI.",
            "Sign PBART1 role 4, PSYM1, its manifest, and the bound PooleKernel under approved roots.",
            "Implement PSYM1 parsing and fail-closed consumption inside PooleBoot.",
            "Implement the bounded target lookup path in PooleKernel without expanding export authority.",
            "Define capability-authorized diagnostic sessions and pointer-redaction policy.",
            "Define secure retention, access, and release policy for private split-debug files.",
            "Qualify panic-safe lookup after final page permissions and exception paths exist.",
            "Prove full debug artifacts are absent from the exact staged and distributed media.",
            "Reproduce the debug and stripped correspondence on an independent builder.",
            "Run target QEMU, firmware, malformed-media, and memory-pressure qualification.",
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(readiness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    errors = psym1.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    print(
        f"PSYM1 qualification passed: tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"parser_differential={readiness['summary']['parser_differential_cases']}; "
        f"lookup_differential={readiness['summary']['lookup_differential_cases']}; "
        f"debug_builds={readiness['summary']['debug_reproducible_builds']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
