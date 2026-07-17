#!/usr/bin/env python3
"""Qualify PKELF1 parsing, loading, hostile controls, and differential cases."""

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_elf_loader as elf  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / elf.READINESS_RELATIVE
DIFFERENTIAL_CASES = 16_384
DIFFERENTIAL_SEED = 0x504B_454C_4631


class QualificationError(RuntimeError):
    """Raised when PKELF1 qualification fails closed."""


@dataclass(frozen=True)
class Control:
    control_id: str
    data: bytes
    expected_code: str
    physical_base: int = 0x0200_0000
    virtual_base: int = elf.MIN_VIRTUAL_BASE
    capacity: int = 0x4000


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
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _single_rlib(target_dir: Path, target: str, crate_name: str) -> Path:
    artifacts = sorted((target_dir / target / "release" / "deps").glob(f"lib{crate_name}-*.rlib"))
    if len(artifacts) != 1:
        raise QualificationError(f"expected one {crate_name} rlib for {target}, found {len(artifacts)}")
    return artifacts[0]


def _build_loader(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
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
            "poole-elf",
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
        raise QualificationError("expected exactly twelve PKELF1 Rust host tests")

    _run(
        [
            str(cargo),
            "fmt",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-elf",
            "--",
            "--check",
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    clippy_runs = []
    for target in (host_target, "x86_64-unknown-uefi", "x86_64-unknown-none"):
        command = [
            str(cargo),
            "clippy",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-elf",
            "--lib",
            "--target",
            target,
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / f"clippy-{target}"),
            "--",
            "-D",
            "warnings",
        ]
        _run(command, cwd=NATIVE_ROOT, env=env)
        clippy_runs.append({"target": target, "status": "pass"})

    target_results = []
    integration_results = []
    for target in ("x86_64-unknown-uefi", "x86_64-unknown-none"):
        loader_target = temporary_root / f"loader-{target}"
        _run(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "poole-elf",
                "--lib",
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(loader_target),
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
        artifact = _single_rlib(loader_target, target, "poole_elf")
        target_results.append(
            {
                "target": target,
                "status": "pass",
                "byte_count": artifact.stat().st_size,
                "sha256": elf.sha256_bytes(artifact.read_bytes()),
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
                "pooleboot_rlib_sha256": elf.sha256_bytes(boot_artifact.read_bytes()),
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
            "poole-elf",
            "--bin",
            "poole-elf-probe",
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
    probe = probe_target / host_target / "release" / "poole-elf-probe.exe"
    if not probe.is_file():
        raise QualificationError("PKELF1 host probe is missing")
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    return probe, {
        "rustc_version_sha256": elf.sha256_bytes(version.encode("utf-8")),
        "rust_host_target": host_target,
        "rust_host_test_count": 12,
        "rust_host_test_pass_count": 12,
        "rustfmt_status": "pass",
        "clippy_runs": clippy_runs,
        "no_std_target_builds": target_results,
        "pooleboot_compile_time_integration_builds": integration_results,
        "host_probe_byte_count": probe.stat().st_size,
        "host_probe_artifact_identity_recorded": False,
        "host_probe_role": "ephemeral host-only differential and exact-byte transport",
    }


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
        raise QualificationError(f"PKELF1 probe failed: {completed.stdout[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError(f"PKELF1 probe response count mismatch: {len(lines)} != {len(requests)}")
    return lines


def _load_request(prefix: str, data: bytes, physical: int, virtual: int, capacity: int) -> str:
    return f"{prefix}:{virtual:x}:{physical:x}:{capacity}:{data.hex()}"


def _qualify_golden(probe: Path, golden: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for vector in golden["vectors"]:
        data = bytes.fromhex(vector["file_hex"])
        physical = int(vector["physical_base"])
        virtual = int(vector["virtual_base"])
        capacity = int(vector["image_byte_count"])
        plan, python_loaded = elf.load(data, physical, virtual, capacity)
        expected_summary = elf.semantic_summary(plan, python_loaded)
        rust_summary = _probe_lines(probe, [_load_request("L", data, physical, virtual, capacity)])[0]
        if rust_summary != expected_summary or rust_summary != vector["semantic_summary"]:
            raise QualificationError(f"golden semantic mismatch: {vector['id']}")
        rust_bytes_result = _probe_lines(probe, [_load_request("B", data, physical, virtual, capacity)])[0]
        if not rust_bytes_result.startswith("OKBYTES:"):
            raise QualificationError(f"golden byte transport rejected: {vector['id']}")
        rust_loaded = bytes.fromhex(rust_bytes_result.removeprefix("OKBYTES:"))
        if rust_loaded != python_loaded[: plan.image_size]:
            raise QualificationError(f"golden loaded bytes mismatch: {vector['id']}")
        if elf.sha256_bytes(rust_loaded) != vector["loaded_sha256"]:
            raise QualificationError(f"golden loaded hash mismatch: {vector['id']}")
        results.append(
            {
                "id": vector["id"],
                "status": "pass",
                "file_byte_count": len(data),
                "file_sha256": elf.sha256_bytes(data),
                "image_byte_count": plan.image_size,
                "loaded_sha256": elf.sha256_bytes(rust_loaded),
                "relocation_count": plan.relocation_count,
                "python_semantics_match": True,
                "rust_semantics_match": True,
                "exact_loaded_bytes_match": True,
            }
        )
    return results


def _set(data: bytes, offset: int, fmt: str, value: int) -> bytes:
    mutated = bytearray(data)
    struct.pack_into(fmt, mutated, offset, value)
    return bytes(mutated)


def _set_byte(data: bytes, offset: int, value: int) -> bytes:
    mutated = bytearray(data)
    mutated[offset] = value
    return bytes(mutated)


def _phdr_offset(index: int, field: str) -> int:
    offsets = {
        "type": 0,
        "flags": 4,
        "offset": 8,
        "vaddr": 16,
        "paddr": 24,
        "filesz": 32,
        "memsz": 40,
        "align": 48,
    }
    return elf.ELF_HEADER_BYTES + index * elf.PROGRAM_HEADER_BYTES + offsets[field]


def _set_phdr(data: bytes, index: int, field: str, value: int) -> bytes:
    fmt = "<I" if field in ("type", "flags") else "<Q"
    return _set(data, _phdr_offset(index, field), fmt, value)


def _controls() -> list[Control]:
    base = elf.build_fixture("minimal_relative_v1")
    controls: list[Control] = []

    def add(control_id: str, data: bytes, code: str, **changes: int) -> None:
        controls.append(Control(control_id, data, code, **changes))

    add("empty", b"", "empty", capacity=0)
    add("header_truncated_one", base[:1], "header_truncated")
    add("header_truncated_sixty_three", base[:63], "header_truncated")
    add("program_table_truncated", base[:455], "program_header_bounds")
    add("file_too_large", base + bytes(elf.MAX_FILE_BYTES + 1 - len(base)), "file_too_large")

    for control_id, offset, value, code in (
        ("bad_magic_first", 0, 0, "magic"),
        ("bad_magic_last", 3, 0, "magic"),
        ("elf32_class", 4, 1, "class"),
        ("invalid_class", 4, 0, "class"),
        ("big_endian", 5, 2, "encoding"),
        ("invalid_encoding", 5, 0, "encoding"),
        ("ident_version_zero", 6, 0, "ident_version"),
        ("linux_osabi", 7, 3, "osabi"),
        ("abi_version_one", 8, 1, "abi_version"),
        ("ident_padding_first", 9, 1, "ident_padding"),
        ("ident_padding_last", 15, 1, "ident_padding"),
    ):
        add(control_id, _set_byte(base, offset, value), code)

    for control_id, offset, fmt, value, code in (
        ("et_exec", 16, "<H", 2, "file_type"),
        ("et_rel", 16, "<H", 1, "file_type"),
        ("machine_i386", 18, "<H", 3, "machine"),
        ("machine_aarch64", 18, "<H", 183, "machine"),
        ("header_version_zero", 20, "<I", 0, "version"),
        ("entry_header_flags", 48, "<I", 1, "header_flags"),
        ("header_size_short", 52, "<H", 63, "header_size"),
        ("program_offset_zero", 32, "<Q", 0, "program_header_offset"),
        ("program_offset_shifted", 32, "<Q", 65, "program_header_offset"),
        ("program_entry_short", 54, "<H", 55, "program_header_size"),
        ("program_count_short", 56, "<H", 6, "program_header_count"),
        ("program_count_long", 56, "<H", 8, "program_header_count"),
        ("section_offset_present", 40, "<Q", 0x3000, "section_table"),
        ("section_entry_invalid", 58, "<H", 63, "section_table"),
        ("section_count_present", 60, "<H", 1, "section_table"),
        ("section_name_present", 62, "<H", 1, "section_table"),
    ):
        add(control_id, _set(base, offset, fmt, value), code)

    for index, segment_type, label in (
        (6, 3, "interp"),
        (6, 4, "note"),
        (6, 5, "shlib"),
        (6, 7, "tls"),
        (6, 0x7000_0001, "processor_specific"),
    ):
        add(f"unsupported_{label}", _set_phdr(base, index, "type", segment_type), "unsupported_segment")
    add("program_header_order_first", _set_phdr(base, 0, "type", elf.PT_LOAD), "program_header_order")
    add("program_header_order_dynamic", _set_phdr(base, 4, "type", elf.PT_LOAD), "program_header_order")

    for control_id, field, value in (
        ("phdr_flags", "flags", 0),
        ("phdr_offset", "offset", 0),
        ("phdr_vaddr", "vaddr", 0),
        ("phdr_paddr", "paddr", 1),
        ("phdr_filesz", "filesz", 391),
        ("phdr_memsz", "memsz", 393),
        ("phdr_align", "align", 16),
    ):
        add(control_id, _set_phdr(base, 0, field, value), "phdr_segment")

    for control_id, index, field, value, code in (
        ("load_r_missing_read", 1, "flags", 0, "load_flags"),
        ("load_rx_writable", 2, "flags", 7, "load_flags"),
        ("load_rw_missing_write", 3, "flags", 4, "load_flags"),
        ("load_alignment_small", 1, "align", 1, "load_alignment"),
        ("load_offset_unaligned", 2, "offset", 0x1001, "load_alignment"),
        ("load_vaddr_unaligned", 2, "vaddr", 0x1001, "load_alignment"),
        ("load_offset_vaddr_mismatch", 2, "offset", 0x2000, "load_alignment"),
        ("load_physical_address", 2, "paddr", 0x1000, "load_address"),
        ("load_file_size_zero", 1, "filesz", 0, "segment_size"),
        ("load_memory_size_zero", 1, "memsz", 0, "segment_size"),
        ("load_file_larger_than_memory", 1, "filesz", 0x2000, "segment_size"),
        ("load_memory_not_page_multiple", 3, "memsz", 0x2001, "segment_size"),
        ("load_memory_outside_profile", 3, "memsz", elf.MAX_IMAGE_BYTES, "segment_bounds"),
        ("load_memory_add_overflow", 3, "memsz", 0xFFFF_FFFF_FFFF_F000, "segment_bounds"),
        ("first_load_not_zero", 1, "offset", 0x1000, "load_alignment"),
        ("noncontiguous_rx", 2, "vaddr", 0x2000, "load_alignment"),
        ("first_load_overlap", 1, "memsz", 0x2000, "segment_layout"),
        ("rw_only_one_page", 3, "memsz", 0x1000, "segment_size"),
    ):
        add(control_id, _set_phdr(base, index, field, value), code)
    load_file_outside = _set_phdr(_set_phdr(base, 2, "filesz", 0x3000), 2, "memsz", 0x3000)
    add("load_file_outside", load_file_outside, "segment_bounds")
    add("trailing_unclaimed_byte", base + b"\0", "file_coverage", capacity=0x4000)
    add("final_load_truncated", base[:-1], "segment_bounds")

    for control_id, entry in (
        ("entry_zero", 0),
        ("entry_in_header", 0x200),
        ("entry_at_text_end", 0x2000),
        ("entry_in_writable", 0x2100),
    ):
        add(control_id, _set(base, 24, "<Q", entry), "entry_point")

    for control_id, field, value in (
        ("relro_flags", "flags", 6),
        ("relro_offset", "offset", 0x2008),
        ("relro_vaddr", "vaddr", 0x2008),
        ("relro_paddr", "paddr", 1),
        ("relro_filesz", "filesz", 0x800),
        ("relro_memsz", "memsz", 0x800),
        ("relro_alignment", "align", 8),
        ("relro_covers_writable", "memsz", 0x2000),
        ("relro_exceeds_file", "filesz", 0x2000),
    ):
        add(control_id, _set_phdr(base, 5, field, value), "relro_segment")

    for control_id, field, value in (
        ("stack_executable", "flags", 7),
        ("stack_offset", "offset", 1),
        ("stack_vaddr", "vaddr", 1),
        ("stack_paddr", "paddr", 1),
        ("stack_filesz", "filesz", 1),
        ("stack_memsz", "memsz", 1),
        ("stack_alignment", "align", 8),
    ):
        add(control_id, _set_phdr(base, 6, field, value), "stack_segment")

    for control_id, field, value in (
        ("dynamic_flags", "flags", 4),
        ("dynamic_offset", "offset", 0x2008),
        ("dynamic_vaddr", "vaddr", 0x2008),
        ("dynamic_paddr", "paddr", 1),
        ("dynamic_filesz", "filesz", 48),
        ("dynamic_memsz", "memsz", 48),
        ("dynamic_alignment", "align", 16),
    ):
        add(control_id, _set_phdr(base, 4, field, value), "dynamic_segment")

    for control_id, offset, fmt, value, code in (
        ("dynamic_first_tag", 0x2000, "<q", elf.DT_NULL, "dynamic_order"),
        ("dynamic_second_tag", 0x2010, "<q", elf.DT_RELAENT, "dynamic_order"),
        ("dynamic_third_tag", 0x2020, "<q", elf.DT_RELASZ, "dynamic_order"),
        ("dynamic_terminal_tag", 0x2030, "<q", elf.DT_RELA, "dynamic_order"),
        ("dynamic_terminal_value", 0x2038, "<Q", 1, "dynamic_entry"),
        ("rela_entry_size_short", 0x2028, "<Q", 23, "relocation_entry_size"),
        ("rela_size_zero", 0x2018, "<Q", 0, "relocation_table"),
        ("rela_size_partial", 0x2018, "<Q", 25, "relocation_table"),
        ("rela_count_over_limit", 0x2018, "<Q", (elf.MAX_RELOCATIONS + 1) * 24, "relocation_count"),
        ("rela_address_unaligned", 0x2008, "<Q", 0x2041, "relocation_table"),
        ("rela_overlaps_dynamic", 0x2008, "<Q", 0x2030, "relocation_table"),
        ("rela_outside_relro", 0x2008, "<Q", 0x3000, "relocation_table"),
        ("rela_crosses_relro_end", 0x2008, "<Q", 0x2FF0, "relocation_table"),
        ("relocation_wrong_type", 0x2048, "<Q", 7, "relocation_type"),
        ("relocation_symbol", 0x2048, "<Q", (1 << 32) | 8, "relocation_symbol"),
        ("relocation_target_unaligned", 0x2040, "<Q", 0x2071, "relocation_target"),
        ("relocation_target_text", 0x2040, "<Q", 0x1080, "relocation_target"),
        ("relocation_target_dynamic", 0x2040, "<Q", 0x2000, "relocation_target"),
        ("relocation_target_table", 0x2040, "<Q", 0x2040, "relocation_target"),
        ("relocation_target_bss", 0x2040, "<Q", 0x3000, "relocation_target"),
        ("relocation_negative_addend", 0x2050, "<q", -1, "relocation_addend"),
        ("relocation_addend_at_end", 0x2050, "<q", 0x4000, "relocation_addend"),
        ("relocation_addend_large", 0x2050, "<q", 0x7FFF_FFFF_FFFF_FFFF, "relocation_addend"),
    ):
        add(control_id, _set(base, offset, fmt, value), code)
    first_target = struct.unpack_from("<Q", base, 0x2040)[0]
    second_target = struct.unpack_from("<Q", base, 0x2058)[0]
    add("relocation_duplicate_target", _set(base, 0x2058, "<Q", first_target), "relocation_order")
    descending = _set(_set(base, 0x2040, "<Q", second_target), 0x2058, "<Q", first_target)
    add("relocation_descending_target", descending, "relocation_order")
    add("relocation_target_nonzero", _set_byte(base, first_target, 1), "relocation_target")

    add("physical_below_minimum", base, "physical_base", physical_base=elf.MIN_PHYSICAL_BASE - elf.PAGE_SIZE)
    add("physical_unaligned", base, "physical_base", physical_base=0x0200_0001)
    add(
        "physical_exceeds_ceiling",
        base,
        "physical_base",
        physical_base=elf.MAX_PHYSICAL_EXCLUSIVE - elf.PAGE_SIZE,
    )
    add("virtual_below_window", base, "virtual_base", virtual_base=elf.MIN_VIRTUAL_BASE - elf.VIRTUAL_BASE_ALIGNMENT)
    add("virtual_unaligned", base, "virtual_base", virtual_base=elf.MIN_VIRTUAL_BASE + elf.PAGE_SIZE)
    add("virtual_at_window_end", base, "virtual_base", virtual_base=elf.MAX_VIRTUAL_EXCLUSIVE)
    large_image = _set_phdr(base, 3, "memsz", 0x400000)
    add(
        "virtual_image_crosses_window",
        large_image,
        "virtual_base",
        virtual_base=elf.MAX_VIRTUAL_EXCLUSIVE - elf.VIRTUAL_BASE_ALIGNMENT,
        capacity=0x402000,
    )
    add("output_one_byte_short", base, "output_capacity", capacity=0x3FFF)
    add("output_zero", base, "output_capacity", capacity=0)

    if len(controls) < 100:
        raise QualificationError(f"hostile control set unexpectedly small: {len(controls)}")
    if len({control.control_id for control in controls}) != len(controls):
        raise QualificationError("hostile control ids are not unique")
    return controls


def _qualify_controls(probe: Path) -> list[dict[str, Any]]:
    controls = _controls()
    requests = [
        _load_request("L", control.data, control.physical_base, control.virtual_base, control.capacity)
        for control in controls
    ]
    rust_results = _probe_lines(probe, requests)
    results = []
    for control, rust_result in zip(controls, rust_results, strict=True):
        expected = f"ERR:{control.expected_code}"
        python_result = elf.result_summary(
            control.data,
            control.physical_base,
            control.virtual_base,
            control.capacity,
        )
        if python_result != expected:
            raise QualificationError(
                f"hostile control oracle mismatch {control.control_id}: expected={expected}, Python={python_result}"
            )
        if rust_result != expected:
            raise QualificationError(
                f"hostile control Rust mismatch {control.control_id}: expected={expected}, Rust={rust_result}"
            )
        results.append(
            {
                "id": control.control_id,
                "expected_result": expected,
                "python_result": python_result,
                "rust_result": rust_result,
                "status": "pass",
            }
        )
    return results


def _differential_case(
    base: bytes, rng: random.Random, index: int
) -> tuple[bytes, int, int, int, int, list[tuple[int, int]]]:
    physical = 0x0200_0000
    virtual = elf.MIN_VIRTUAL_BASE
    capacity = 0x4000
    length = len(base)
    patches: dict[int, int] = {}
    mode = index % 10
    if mode == 0:
        pass
    elif mode == 1:
        offset = rng.randrange(len(base))
        patches[offset] = base[offset] ^ (1 << rng.randrange(8))
    elif mode == 2:
        for _ in range(2 + rng.randrange(3)):
            offset = rng.randrange(len(base))
            patches[offset] = rng.randrange(256)
    elif mode == 3:
        length = rng.randrange(len(base) + 1)
    elif mode == 4:
        structural_offsets = [
            0,
            4,
            16,
            18,
            24,
            32,
            48,
            54,
            56,
            64,
            68,
            64 + 2 * 56 + 4,
            64 + 3 * 56 + 40,
            0x2000,
            0x2008,
            0x2018,
            0x2040,
            0x2048,
            0x2050,
        ]
        offset = rng.choice(structural_offsets)
        patches[offset] = base[offset] ^ (1 << rng.randrange(8))
    elif mode == 5:
        physical = 0x0200_0000 + rng.randrange(1, 2048) * elf.PAGE_SIZE
        virtual = elf.MIN_VIRTUAL_BASE + rng.randrange(0, 256) * elf.VIRTUAL_BASE_ALIGNMENT
    elif mode == 6:
        capacity = rng.randrange(0x4000)
    elif mode == 7:
        physical = rng.choice((0, elf.MIN_PHYSICAL_BASE - 1, 0x0200_0001, elf.MAX_PHYSICAL_EXCLUSIVE))
    elif mode == 8:
        virtual = rng.choice(
            (
                0,
                elf.MIN_VIRTUAL_BASE - elf.VIRTUAL_BASE_ALIGNMENT,
                elf.MIN_VIRTUAL_BASE + elf.PAGE_SIZE,
                elf.MAX_VIRTUAL_EXCLUSIVE,
            )
        )
    else:
        offset = rng.randrange(0x0800, 0x1000)
        patches[offset] = rng.randrange(1, 256)
    data = bytearray(base[:length])
    for offset, value in patches.items():
        if offset < length:
            data[offset] = value
    return bytes(data), physical, virtual, capacity, length, sorted(patches.items())


def _qualify_differential(probe: Path) -> dict[str, Any]:
    base = elf.build_fixture("minimal_relative_v1")
    rng = random.Random(DIFFERENTIAL_SEED)
    valid_count = 0
    rejected_count = 0
    outcome = hashlib.sha256()
    batch_size = 256
    for start in range(0, DIFFERENTIAL_CASES, batch_size):
        cases = []
        requests = [f"C:{base.hex()}"]
        for index in range(start, min(start + batch_size, DIFFERENTIAL_CASES)):
            data, physical, virtual, capacity, length, patches = _differential_case(base, rng, index)
            expected = elf.result_summary(data, physical, virtual, capacity)
            patch_text = ",".join(f"{offset:x}={value:02x}" for offset, value in patches if offset < length) or "-"
            requests.append(f"M:{virtual:x}:{physical:x}:{capacity}:{length}:{patch_text}")
            cases.append((index, expected))
        responses = _probe_lines(probe, requests)
        if responses[0] != "OKCACHE":
            raise QualificationError("PKELF1 differential cache transport failed")
        for (index, expected), rust_result in zip(cases, responses[1:], strict=True):
            if rust_result != expected:
                raise QualificationError(
                    f"differential mismatch at case {index}: Python={expected}, Rust={rust_result}"
                )
            valid_count += int(expected.startswith("OK;"))
            rejected_count += int(expected.startswith("ERR:"))
            outcome.update(f"{index}:{expected}\n".encode("utf-8"))
    if valid_count == 0 or rejected_count == 0 or valid_count + rejected_count != DIFFERENTIAL_CASES:
        raise QualificationError("differential campaign did not cover both acceptance and rejection")
    return {
        "campaign_id": "PKELF1-DIFF-1",
        "generator": "cached exact base image plus deterministic byte replacement, truncation, address, capacity, structural, and accepted-payload mutations",
        "seed": DIFFERENTIAL_SEED,
        "case_count": DIFFERENTIAL_CASES,
        "valid_result_count": valid_count,
        "rejected_result_count": rejected_count,
        "mismatch_count": 0,
        "outcome_sha256": outcome.hexdigest().upper(),
        "corpus_published": False,
        "status": "pass",
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = elf.read_json(ROOT / elf.CONTRACT_RELATIVE)
    golden = elf.read_json(ROOT / elf.GOLDEN_RELATIVE)
    errors = elf.contract_errors(contract) + elf.golden_errors(golden)
    if errors:
        raise QualificationError("; ".join(errors))
    with tempfile.TemporaryDirectory(prefix="pooleos-pkelf1-") as temporary:
        probe, parser_qualification = _build_loader(toolchain_root, Path(temporary))
        golden_results = _qualify_golden(probe, golden)
        controls = _qualify_controls(probe)
        differential = _qualify_differential(probe)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_elf_loader_readiness",
        "status_date": "2026-07-16",
        "status": "pass_single_host_synthetic_non_promoting",
        "contract_id": elf.CONTRACT_ID,
        "selected_move_id": "N5-ELF-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.5": "partial"},
        "bindings": {
            "contract": elf.file_binding(ROOT / elf.CONTRACT_RELATIVE),
            "contract_schema": elf.file_binding(ROOT / elf.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": elf.file_binding(ROOT / elf.GOLDEN_RELATIVE),
            "golden_schema": elf.file_binding(ROOT / elf.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": elf.file_binding(ROOT / elf.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": [elf.file_binding(ROOT / path) for path in elf.IMPLEMENTATION_INPUTS],
        },
        "parser_qualification": parser_qualification,
        "golden_vectors": golden_results,
        "negative_controls": controls,
        "differential_fuzz": differential,
        "claims": elf.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 12,
            "rust_host_tests_total": 12,
            "rustfmt_passed": 1,
            "clippy_runs_passed": 3,
            "clippy_runs_total": 3,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "pooleboot_integration_builds_passed": 2,
            "pooleboot_integration_builds_total": 2,
            "golden_vectors_matched": len(golden_results),
            "golden_vectors_total": 3,
            "exact_loaded_byte_vectors_matched": len(golden_results),
            "maximum_relocations_exercised": elf.MAX_RELOCATIONS,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "differential_fuzz_cases": differential["case_count"],
            "differential_mismatches": differential["mismatch_count"],
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PKELF1 before declaring a stable kernel-image ABI.",
            "Produce a source-built functional PooleKernel ET_DYN image that conforms to PKELF1.",
            "Authenticate exact kernel bytes through the signed manifest before parsing or loading.",
            "Implement bounded UEFI file reads and EfiLoaderData page allocation with cleanup on every failure.",
            "Build page tables from the returned W^X and RELRO plan and verify hardware-enforced permissions.",
            "Bind exact file and loaded-memory hashes plus mapping metadata into live PBP1 records.",
            "Retrieve the final memory map, exit boot services, transfer to kernel entry, and consume PBP1.",
            "Reproduce on a second independent builder and execute on target firmware.",
            "Complete separately authorized physical-media qualification and signed ISO release gates."
        ],
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    readiness = make_readiness(args.toolchain_root.resolve())
    elf.write_json(readiness, args.out)
    errors = elf.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    print(
        f"PKELF1 qualification passed: tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"differential={readiness['summary']['differential_fuzz_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
