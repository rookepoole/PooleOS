#!/usr/bin/env python3
"""Bindings and fail-closed validation for the PKENTRY1 readiness receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID = "PKENTRY1"
CONTRACT_RELATIVE = Path("specs/native-kernel-entry-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-kernel-entry-contract.schema.json")
READINESS_RELATIVE = Path("runs/native_kernel_entry_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-kernel-entry-readiness.schema.json")

IMPLEMENTATION_INPUTS = (
    Path("native/Cargo.toml"),
    Path("native/Cargo.lock"),
    Path("native/kernel/Cargo.toml"),
    Path("native/kernel/README.md"),
    Path("native/kernel/arch/x86_64/README.md"),
    Path("native/kernel/linker.ld"),
    Path("native/kernel/manifest.pkm"),
    Path("native/kernel/src/lib.rs"),
    Path("native/kernel/src/main.rs"),
    Path("native/kernel/src/arch/x86_64.rs"),
    Path("native/kernel/src/physical_memory.rs"),
    Path("native/kernel/src/virtual_memory.rs"),
    Path("native/kernel/src/active_virtual_memory.rs"),
    Path("native/fixtures/poolekernel/Cargo.toml"),
    Path("native/fixtures/poolekernel/README.md"),
    Path("native/fixtures/poolekernel/src/main.rs"),
    Path("runtime/native_kernel_image.py"),
    Path("runtime/native_kernel_entry.py"),
    Path("tools/qualify_native_kernel_entry.py"),
    Path("tests/test_native_kernel_entry.py"),
    Path("docs/native-kernel-entry.md"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "byte_count": len(data),
        "sha256": sha256_bytes(data),
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def expected_claims() -> dict[str, bool]:
    return {
        "real_poolekernel_product_image": True,
        "legacy_empty_fixture_isolated": True,
        "allocation_free_pbp1_consumer": True,
        "bounded_early_ring": True,
        "bounded_com1_candidate": True,
        "optional_framebuffer_sink": True,
        "deterministic_panic_taxonomy": True,
        "reproducible_single_host_image": True,
        "live_pooleboot_transfer": False,
        "exit_boot_services_executed": False,
        "page_tables_installed": False,
        "final_wx_permissions_installed": False,
        "hardware_serial_executed": False,
        "hardware_framebuffer_executed": False,
        "gdt_idt_tss_initialized": False,
        "kernel_runtime_initialized": False,
        "qemu_kernel_execution": False,
        "target_firmware_tested": False,
        "second_host_reproduced": False,
        "bootable_iso": False,
        "n6_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: Any) -> list[str]:
    schema = read_json(ROOT / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if not isinstance(contract, dict):
        return errors + ["contract is not an object"]
    if contract.get("contract_id") != CONTRACT_ID:
        errors.append("contract id mismatch")
    product = contract.get("product", {})
    expected_product = {
        "target": "x86_64-unknown-none",
        "format_contract": "PKELF1",
        "handoff_contract": "PBP1",
        "entry_offset": 0x8000,
        "image_memory_bytes": 0x46000,
        "canonical_file_bytes": 0x3C000,
        "maximum_relocations": 4096,
        "segment_boundaries": {
            "read_only_end": 0x8000,
            "text_start": 0x8000,
            "text_end": 0x36000,
            "relro_end": 0x3C000,
            "image_end": 0x46000,
        },
    }
    for key, value in expected_product.items():
        if product.get(key) != value:
            errors.append(f"contract product mismatch: {key}")
    if contract.get("claims") != expected_claims():
        errors.append("contract claim boundary mismatch")
    return errors


def expected_bindings(root: Path = ROOT) -> dict[str, Any]:
    return {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "readiness_schema": file_binding(root / READINESS_SCHEMA_RELATIVE, root),
        "pbp1_contract": file_binding(root / "specs/native-boot-handoff-contract.json", root),
        "pkelf1_contract": file_binding(root / "specs/native-elf-loader-contract.json", root),
        "toolchain_lock": file_binding(root / "specs/native-toolchain-lock.json", root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }


def readiness_errors(readiness: Any, root: Path = ROOT) -> list[str]:
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    if not isinstance(readiness, dict):
        return errors + ["readiness is not an object"]
    errors.extend(f"contract {item}" for item in contract_errors(read_json(root / CONTRACT_RELATIVE)))
    if readiness.get("bindings") != expected_bindings(root):
        errors.append("readiness input bindings are stale")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary mismatch")
    if readiness.get("production_ready") is not False:
        errors.append("readiness overclaims production")
    if readiness.get("production_promotion_allowed") is not False:
        errors.append("readiness overclaims promotion")
    if readiness.get("n6_exit_gate_satisfied") is not False:
        errors.append("readiness overclaims N6 exit")
    summary = readiness.get("summary", {})
    for passed, total in (
        ("rust_host_tests_passed", "rust_host_tests_total"),
        ("clean_builds_matched", "clean_builds_total"),
        ("negative_controls_passed", "negative_controls_total"),
        ("exact_loaded_byte_implementations_matched", "exact_loaded_byte_implementations_total"),
    ):
        if not isinstance(summary.get(total), int) or summary.get(passed) != summary.get(total):
            errors.append(f"readiness summary mismatch: {passed}")
    if summary.get("rust_host_tests_total") != 74:
        errors.append("readiness host-test count mismatch")
    if summary.get("clean_builds_total") != 2:
        errors.append("readiness clean-build count mismatch")
    if summary.get("negative_controls_total", 0) < 32:
        errors.append("readiness negative-control count is too small")
    product = readiness.get("product", {})
    contract_product = read_json(root / CONTRACT_RELATIVE)["product"]
    if product.get("canonical_byte_count") != contract_product["canonical_file_bytes"]:
        errors.append("readiness canonical product size mismatch")
    if product.get("image_byte_count") != contract_product["image_memory_bytes"]:
        errors.append("readiness image size mismatch")
    if product.get("entry_offset") != contract_product["entry_offset"]:
        errors.append("readiness entry mismatch")
    return errors
