#!/usr/bin/env python3
"""Build and qualify the bounded PKENTRY1 PooleKernel product image."""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_elf_loader as elf  # noqa: E402
from runtime import native_kernel_entry as entry  # noqa: E402
from runtime import native_kernel_image as kernel_image  # noqa: E402
from runtime.native_binary import scan_forbidden_markers  # noqa: E402
from tools.qualify_native_elf_loader import (  # noqa: E402
    _build_loader,
    _load_request,
    _probe_lines,
    _toolchain,
)


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / entry.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
PRODUCT_TARGET = "x86_64-unknown-none"
PHYSICAL_BASE = 0x0200_0000
VIRTUAL_BASE = elf.MIN_VIRTUAL_BASE


class QualificationError(RuntimeError):
    """Raised when a PKENTRY1 qualification step fails closed."""


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
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


def _product_flags() -> list[str]:
    linker_script = (NATIVE_ROOT / "kernel" / "linker.ld").resolve()
    return [
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
        "-Cdwarf-version=5",
    ]


def _product_environment(base: dict[str, str]) -> dict[str, str]:
    env = dict(base)
    env.pop("RUSTFLAGS", None)
    env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(_product_flags())
    env["CARGO_PROFILE_RELEASE_DEBUG"] = "2"
    env["CARGO_PROFILE_RELEASE_STRIP"] = "none"
    return env


def _cargo_base(cargo: Path) -> list[str]:
    return [
        str(cargo),
        "--manifest-path",
        str(NATIVE_ROOT / "Cargo.toml"),
    ]


def _host_checks(cargo: Path, env: dict[str, str], temporary_root: Path) -> dict[str, Any]:
    output = _run(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poolekernel",
            "--lib",
            "--target",
            HOST_TARGET,
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
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", output)
    if match is None or int(match.group(1)) != 60:
        raise QualificationError("expected exactly fifty-four PooleKernel host tests")
    for package in ("poolekernel", "poolekernel-fixture"):
        _run(
            [
                str(cargo),
                "fmt",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                package,
                "--",
                "--check",
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
    _run(
        [
            str(cargo),
            "clippy",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poolekernel",
            "--lib",
            "--target",
            HOST_TARGET,
            "--release",
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "clippy-host"),
            "--",
            "-D",
            "warnings",
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        [
            str(cargo),
            "clippy",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
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
            str(temporary_root / "clippy-product"),
            "--",
            "-D",
            "warnings",
        ],
        cwd=NATIVE_ROOT,
        env=_product_environment(env),
    )
    return {
        "test_count": 60,
        "test_pass_count": 60,
        "rustfmt_packages": ["poolekernel", "poolekernel-fixture"],
        "clippy_targets": [HOST_TARGET, PRODUCT_TARGET],
        "status": "pass",
    }


def _build_product(cargo: Path, env: dict[str, str], target_dir: Path) -> tuple[bytes, bytes, kernel_image.LinkedImagePlan]:
    _run(
        [
            str(cargo),
            "build",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
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
        ],
        cwd=NATIVE_ROOT,
        env=_product_environment(env),
    )
    artifact = target_dir / PRODUCT_TARGET / "release" / "PooleKernelLinked"
    if not artifact.is_file():
        raise QualificationError("linked PooleKernel artifact is missing")
    linked = artifact.read_bytes()
    canonical, plan = kernel_image.canonicalize_linked_image(linked)
    return linked, canonical, plan


def _set(data: bytes, offset: int, fmt: str, value: int) -> bytes:
    output = bytearray(data)
    struct.pack_into(fmt, output, offset, value)
    return bytes(output)


def _set_byte(data: bytes, offset: int, value: int) -> bytes:
    output = bytearray(data)
    output[offset] = value
    return bytes(output)


def _phdr(index: int, field_offset: int) -> int:
    return kernel_image.ELF_HEADER_BYTES + index * kernel_image.PROGRAM_HEADER_BYTES + field_offset


def _source_dynamic_positions(linked: bytes) -> dict[int, int]:
    dynamic_offset = struct.unpack_from("<Q", linked, _phdr(4, 8))[0]
    dynamic_size = struct.unpack_from("<Q", linked, _phdr(4, 32))[0]
    positions: dict[int, int] = {}
    for offset in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
        tag = struct.unpack_from("<q", linked, offset)[0]
        positions[tag] = offset
        if tag == kernel_image.DT_NULL:
            break
    return positions


def _linked_negative_controls(
    linked: bytes,
    plan: kernel_image.LinkedImagePlan,
    manifest: bytes,
) -> list[dict[str, Any]]:
    controls: list[tuple[str, bytes, str]] = []
    dynamic_positions = _source_dynamic_positions(linked)
    first_dynamic = struct.unpack_from("<Q", linked, _phdr(4, 8))[0]
    first_relocation = plan.relocation_source_offset
    first_target, _, _ = struct.unpack_from("<QQq", linked, first_relocation)
    second_target = struct.unpack_from("<Q", linked, first_relocation + 24)[0]
    controls.extend(
        [
            ("NEG-N6-KENTRY-LINKED-TRUNCATED", linked[:20], "header_bounds"),
            ("NEG-N6-KENTRY-LINKED-IDENT", _set_byte(linked, 1, 0), "elf_ident"),
            ("NEG-N6-KENTRY-LINKED-TYPE", _set(linked, 16, "<H", 2), "elf_header"),
            ("NEG-N6-KENTRY-LINKED-PHOFF", _set(linked, 32, "<Q", 0), "program_header_geometry"),
            ("NEG-N6-KENTRY-LINKED-SHOFF-ZERO", _set(linked, 40, "<Q", 0), "source_section_table"),
            ("NEG-N6-KENTRY-LINKED-PHDR-ORDER", _set(linked, _phdr(0, 0), "<I", 1), "program_header_order"),
            ("NEG-N6-KENTRY-LINKED-PHDR-PADDR", _set(linked, _phdr(0, 24), "<Q", 0), "phdr_segment"),
            ("NEG-N6-KENTRY-LINKED-RO-FLAGS", _set(linked, _phdr(1, 4), "<I", 6), "load_flags"),
            ("NEG-N6-KENTRY-LINKED-RO-PADDR", _set(linked, _phdr(1, 24), "<Q", 1), "load_geometry"),
            ("NEG-N6-KENTRY-LINKED-TEXT-OFFSET", _set(linked, _phdr(2, 8), "<Q", 0x8001), "load_geometry"),
            ("NEG-N6-KENTRY-LINKED-DATA-FILESZ", _set(linked, _phdr(3, 32), "<Q", 0), "load_geometry"),
            ("NEG-N6-KENTRY-LINKED-LOAD-LAYOUT", _set(linked, _phdr(1, 40), "<Q", 0x9000), "load_layout"),
            ("NEG-N6-KENTRY-LINKED-ENTRY-RANGE", _set(linked, 24, "<Q", 0), "entry_range"),
            ("NEG-N6-KENTRY-LINKED-ENTRY-PREFIX", _set_byte(linked, plan.entry_offset, 0x90), "entry_prefix"),
            ("NEG-N6-KENTRY-LINKED-DYNAMIC-FLAGS", _set(linked, _phdr(4, 4), "<I", 4), "source_dynamic_segment"),
            ("NEG-N6-KENTRY-LINKED-RELRO-FLAGS", _set(linked, _phdr(5, 4), "<I", 6), "source_relro_segment"),
            ("NEG-N6-KENTRY-LINKED-STACK-SIZE", _set(linked, _phdr(6, 40), "<Q", 8), "source_stack_segment"),
            ("NEG-N6-KENTRY-LINKED-DYNAMIC-TAG", _set(linked, first_dynamic, "<q", 0x1234), "source_dynamic_tag"),
            ("NEG-N6-KENTRY-LINKED-RELA-OFFSET", _set(linked, dynamic_positions[kernel_image.DT_RELA] + 8, "<Q", first_relocation + 8), "source_relocation_layout"),
            ("NEG-N6-KENTRY-LINKED-RELA-SIZE", _set(linked, dynamic_positions[kernel_image.DT_RELASZ] + 8, "<Q", 0), "source_relocation_geometry"),
            ("NEG-N6-KENTRY-LINKED-RELA-ENTRY", _set(linked, dynamic_positions[kernel_image.DT_RELAENT] + 8, "<Q", 8), "source_relocation_geometry"),
            ("NEG-N6-KENTRY-LINKED-RELOCATION-TYPE", _set(linked, first_relocation + 8, "<Q", 1), "source_relocation_type"),
            ("NEG-N6-KENTRY-LINKED-RELOCATION-ORDER", _set(linked, first_relocation + 24, "<Q", first_target), "source_relocation_order"),
            ("NEG-N6-KENTRY-LINKED-RELOCATION-TARGET", _set(linked, first_relocation, "<Q", first_dynamic), "source_relocation_target"),
            ("NEG-N6-KENTRY-LINKED-RELOCATION-TARGET-VALUE", _set_byte(linked, first_target, 1), "source_relocation_target_value"),
            ("NEG-N6-KENTRY-LINKED-RELOCATION-ADDEND", _set(linked, first_relocation + 16, "<q", -1), "source_relocation_addend"),
            ("NEG-N6-KENTRY-LINKED-MANIFEST-MISSING", _set_byte(linked, plan.manifest_offset, ord("X")), "manifest_presence"),
            ("NEG-N6-KENTRY-LINKED-MANIFEST-DUPLICATE", linked + manifest, "manifest_presence"),
            ("NEG-N6-KENTRY-LINKED-SECTION-BOUNDS", _set(linked, 40, "<Q", plan.canonical_byte_count - 1), "source_section_bounds"),
        ]
    )
    if second_target <= first_target:
        raise QualificationError("source relocations are not ordered")
    results = []
    for control_id, mutated, expected in controls:
        try:
            kernel_image.inspect_linked_image(mutated, manifest)
        except kernel_image.KernelImageError as error:
            if error.code != expected:
                raise QualificationError(f"{control_id}: expected {expected}, got {error.code}") from error
        else:
            raise QualificationError(f"{control_id}: linked mutation was accepted")
        results.append({"id": control_id, "layer": "linked_lld_input", "expected": expected, "observed": expected, "status": "pass"})
    return results


def _canonical_negative_controls(canonical: bytes, plan: kernel_image.LinkedImagePlan) -> list[dict[str, Any]]:
    first_relocation = plan.relocation_canonical_offset
    first_target = struct.unpack_from("<Q", canonical, first_relocation)[0]
    mutations = [
        ("NEG-N6-KENTRY-PKELF-TRUNCATED", canonical[:20]),
        ("NEG-N6-KENTRY-PKELF-IDENT", _set_byte(canonical, 1, 0)),
        ("NEG-N6-KENTRY-PKELF-SECTIONS", _set(canonical, 40, "<Q", 64)),
        ("NEG-N6-KENTRY-PKELF-PADDR", _set(canonical, _phdr(1, 24), "<Q", 1)),
        ("NEG-N6-KENTRY-PKELF-TEXT-WRITABLE", _set(canonical, _phdr(2, 4), "<I", 7)),
        ("NEG-N6-KENTRY-PKELF-STACK-EXECUTABLE", _set(canonical, _phdr(6, 4), "<I", 7)),
        ("NEG-N6-KENTRY-PKELF-DYNAMIC-TAG", _set(canonical, plan.relro_offset, "<q", 0x1234)),
        ("NEG-N6-KENTRY-PKELF-RELOCATION-TYPE", _set(canonical, first_relocation + 8, "<Q", 1)),
        ("NEG-N6-KENTRY-PKELF-RELOCATION-TARGET-VALUE", _set_byte(canonical, first_target, 1)),
        ("NEG-N6-KENTRY-PKELF-RELOCATION-ADDEND", _set(canonical, first_relocation + 16, "<q", -1)),
    ]
    results = []
    for control_id, mutated in mutations:
        try:
            elf.inspect(mutated, PHYSICAL_BASE, VIRTUAL_BASE)
        except elf.ElfError as error:
            observed = error.code
        else:
            raise QualificationError(f"{control_id}: canonical mutation was accepted")
        results.append({"id": control_id, "layer": "canonical_pkelf1", "expected": "reject", "observed": observed, "status": "pass"})
    call_controls: list[tuple[str, Callable[[], object]]] = [
        ("NEG-N6-KENTRY-PKELF-PHYSICAL-BASE", lambda: elf.inspect(canonical, PHYSICAL_BASE + 1, VIRTUAL_BASE)),
        ("NEG-N6-KENTRY-PKELF-VIRTUAL-BASE", lambda: elf.inspect(canonical, PHYSICAL_BASE, VIRTUAL_BASE + 1)),
        ("NEG-N6-KENTRY-PKELF-CAPACITY", lambda: elf.load(canonical, PHYSICAL_BASE, VIRTUAL_BASE, plan.image_byte_count - 1)),
    ]
    for control_id, operation in call_controls:
        try:
            operation()
        except elf.ElfError as error:
            observed = error.code
        else:
            raise QualificationError(f"{control_id}: invalid loader request was accepted")
        results.append({"id": control_id, "layer": "canonical_pkelf1", "expected": "reject", "observed": observed, "status": "pass"})
    return results


def _manifest_lines() -> list[str]:
    return (NATIVE_ROOT / "kernel" / "manifest.pkm").read_text(encoding="ascii").splitlines()


def _validate_manifest(contract: dict[str, Any]) -> dict[str, str]:
    expected = {
        "entry_contract": entry.CONTRACT_ID,
        "entry_offset": "0x00008000",
        "image_contract": elf.CONTRACT_ID,
        "handoff_contract": "PBP1",
        "build_id": contract["product"]["build_id"],
        "pkentry1_contract_sha256": entry.file_binding(ROOT / entry.CONTRACT_RELATIVE)["sha256"],
        "pbp1_contract_sha256": entry.file_binding(ROOT / "specs/native-boot-handoff-contract.json")["sha256"],
        "pkelf1_contract_sha256": entry.file_binding(ROOT / elf.CONTRACT_RELATIVE)["sha256"],
    }
    lines = _manifest_lines()
    if lines[0] != "POOLEOS-KERNEL-MANIFEST/1" or lines[-1] != "end=PKMID1":
        raise QualificationError("kernel manifest envelope mismatch")
    observed: dict[str, str] = {}
    for line in lines[1:-1]:
        if "=" not in line:
            raise QualificationError("kernel manifest field is malformed")
        key, value = line.split("=", 1)
        if key in observed:
            raise QualificationError("kernel manifest field is duplicated")
        observed[key] = value
    if observed != expected:
        raise QualificationError("kernel manifest contract bindings are stale")
    return observed


def _forbidden_markers() -> dict[str, str]:
    values = {
        "workspace_absolute_windows": str(ROOT),
        "workspace_absolute_forward_slash": ROOT.as_posix(),
        "user_profile_absolute_windows": str(Path.home()),
        "user_profile_absolute_forward_slash": Path.home().as_posix(),
        "windows_account_name": os.environ.get("USERNAME", ""),
        "host_library_kernel32": "kernel32.dll",
        "host_library_ntdll": "ntdll.dll",
        "host_library_msvcrt": "msvcrt",
        "host_library_ucrtbase": "ucrtbase",
        "host_library_vcruntime": "vcruntime",
        "host_sdk_windows_kits": "Windows Kits",
    }
    return {key: value for key, value in values.items() if value}


def make_readiness(toolchain_root: Path) -> tuple[dict[str, Any], bytes]:
    contract = entry.read_json(ROOT / entry.CONTRACT_RELATIVE)
    errors = entry.contract_errors(contract)
    if errors:
        raise QualificationError("; ".join(errors))
    manifest_fields = _validate_manifest(contract)
    cargo, rustc, env = _toolchain(toolchain_root)
    rustc_version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    with tempfile.TemporaryDirectory(prefix="pooleos-pkentry1-") as temporary:
        temporary_root = Path(temporary)
        host_checks = _host_checks(cargo, env, temporary_root)
        linked_one, canonical_one, plan_one = _build_product(cargo, env, temporary_root / "build-one")
        linked_two, canonical_two, plan_two = _build_product(cargo, env, temporary_root / "build-two")
        if linked_one != linked_two:
            raise QualificationError("two clean linked PooleKernel builds differ")
        if canonical_one != canonical_two or plan_one != plan_two:
            raise QualificationError("two clean canonical PooleKernel builds differ")
        if len(linked_one) > contract["product"]["maximum_linked_file_bytes"]:
            raise QualificationError("linked PooleKernel exceeds the contract bound")
        if len(canonical_one) != contract["product"]["canonical_file_bytes"]:
            raise QualificationError("canonical PooleKernel size mismatch")
        if plan_one.image_byte_count != contract["product"]["image_memory_bytes"]:
            raise QualificationError("PooleKernel memory image size mismatch")
        if plan_one.entry_offset != contract["product"]["entry_offset"]:
            raise QualificationError("PooleKernel entry offset mismatch")
        manifest = (NATIVE_ROOT / "kernel" / "manifest.pkm").read_bytes()
        controls = _linked_negative_controls(linked_one, plan_one, manifest)
        controls.extend(_canonical_negative_controls(canonical_one, plan_one))
        markers = _forbidden_markers()
        leakage_hits = scan_forbidden_markers(canonical_one, markers)
        if leakage_hits:
            raise QualificationError(f"canonical PooleKernel leaks host markers: {leakage_hits}")
        injected_marker = next(iter(markers.values())).encode("utf-8")
        if not scan_forbidden_markers(canonical_one + injected_marker, markers):
            raise QualificationError("host-marker negative control did not fire")
        controls.append({"id": "NEG-N6-KENTRY-HOST-MARKER-INJECTED", "layer": "publication_boundary", "expected": "reject", "observed": "marker_detected", "status": "pass"})
        python_plan, python_loaded = elf.load(canonical_one, PHYSICAL_BASE, VIRTUAL_BASE)
        probe, pkelf_qualification = _build_loader(toolchain_root, temporary_root / "pkelf-probe")
        rust_result = _probe_lines(
            probe,
            [_load_request("B", canonical_one, PHYSICAL_BASE, VIRTUAL_BASE, python_plan.image_size)],
        )[0]
        if not rust_result.startswith("OKBYTES:"):
            raise QualificationError(f"Rust PKELF1 loader rejected product: {rust_result}")
        rust_loaded = bytes.fromhex(rust_result.removeprefix("OKBYTES:"))
        if rust_loaded != python_loaded:
            raise QualificationError("Rust and Python loaded PooleKernel bytes differ")
    entry_prefix = canonical_one[plan_one.entry_offset : plan_one.entry_offset + 40]
    if not entry_prefix.startswith(b"\xfa\xfc\x48\x89\xe1\x48\x85\xc9"):
        raise QualificationError("compiled PKENTRY1 stack-check prefix changed")
    product = {
        "linked_byte_count": len(linked_one),
        "linked_sha256": entry.sha256_bytes(linked_one),
        "canonical_byte_count": len(canonical_one),
        "canonical_sha256": entry.sha256_bytes(canonical_one),
        "image_byte_count": plan_one.image_byte_count,
        "loaded_sha256": entry.sha256_bytes(python_loaded),
        "entry_offset": plan_one.entry_offset,
        "entry_prefix_hex": entry_prefix.hex().upper(),
        "relocation_count": plan_one.relocation_count,
        "relocation_source_offset": plan_one.relocation_source_offset,
        "relocation_canonical_offset": plan_one.relocation_canonical_offset,
        "relro_offset": plan_one.relro_offset,
        "relro_byte_count": plan_one.relro_byte_count,
        "manifest_offset": plan_one.manifest_offset,
        "manifest_fields": manifest_fields,
        "host_leakage_hits": [],
    }
    readiness = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_entry_readiness",
        "status_date": "2026-07-16",
        "status": "pass_single_host_product_image_non_promoting",
        "contract_id": entry.CONTRACT_ID,
        "selected_move_id": "N6-KENTRY-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n6_exit_gate_satisfied": False,
        "phase_status": {"N6": "partial", "N6.4": "partial", "N6.5": "partial", "N6.6": "partial"},
        "bindings": entry.expected_bindings(),
        "toolchain": {
            "root_policy": "workspace-local untracked",
            "rustc_version_sha256": entry.sha256_bytes(rustc_version.encode("utf-8")),
            "target": PRODUCT_TARGET,
            "product_rustflags": _product_flags(),
            "pkelf1_probe_qualification": pkelf_qualification,
        },
        "host_tests": host_checks,
        "builds": {
            "clean_build_count": 2,
            "linked_exact_match": True,
            "canonical_exact_match": True,
            "fresh_target_directories": True,
            "cargo_locked": True,
            "cargo_offline": True,
            "source_date_epoch": 0,
        },
        "product": product,
        "negative_controls": controls,
        "claims": entry.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 60,
            "rust_host_tests_total": 60,
            "rustfmt_packages_passed": 2,
            "clippy_runs_passed": 2,
            "clippy_runs_total": 2,
            "clean_builds_matched": 2,
            "clean_builds_total": 2,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "exact_loaded_byte_implementations_matched": 2,
            "exact_loaded_byte_implementations_total": 2,
            "production_claim_count": 0,
        },
        "open_items": [
            "Wire authenticated PooleKernel file discovery, bounded reads, and PKELF1 allocation into PooleBoot.",
            "Install and inspect final page tables, W^X/RELRO permissions, bootstrap stack, read-only PBP1 mapping, and temporary framebuffer mapping.",
            "Replace the QEMU-only unsigned development transfer with an authenticated production PKENTRY1 profile.",
            "Implement GDT, IDT, TSS, exception containment, memory initialization, capability bootstrap, scheduler, IPC, and the initial user-space system.",
            "Reproduce exact product bytes on a second independent builder and qualify target firmware and separately authorized physical media.",
            "Complete the remaining N6 requirements and all downstream N7-N39 production gates."
        ],
        "claim_boundary": contract["claim_boundary"],
    }
    errors = entry.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    return readiness, canonical_one


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--artifact-out", type=Path)
    args = parser.parse_args()
    readiness, product = make_readiness(args.toolchain_root.resolve())
    entry.write_json(readiness, args.out.resolve())
    if args.artifact_out is not None:
        artifact_out = args.artifact_out.resolve()
        artifact_out.parent.mkdir(parents=True, exist_ok=True)
        artifact_out.write_bytes(product)
    print(
        "PKENTRY1 qualification passed: "
        f"tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"canonical_sha256={readiness['product']['canonical_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
