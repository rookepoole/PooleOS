#!/usr/bin/env python3
"""Qualify live PKLOAD6 PBART1/PBP1, retained PKMAP2 state, and PBEXIT1 boundary."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_boot_handoff,
    native_boot_exit,
    native_kernel_load,
    native_kernel_map,
    native_live_boot_handoff,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / native_kernel_load.READINESS_RELATIVE
NATIVE_ROOT = ROOT / "native"


class QualificationError(RuntimeError):
    """Raised when the PKLOAD6 qualification fails closed."""


def _host_checks(toolchain_root: Path, temporary_root: Path) -> dict[str, Any]:
    cargo, _, environment = qualify_native_pooleboot._toolchain(toolchain_root)
    output = qualify_native_pooleboot._run_checked(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-bootload",
            "--target",
            "x86_64-pc-windows-msvc",
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "bootload-tests"),
            "--",
            "--test-threads=1",
        ],
        cwd=NATIVE_ROOT,
        env=environment,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", output)
    if match is None or int(match.group(1)) < 14:
        raise QualificationError("expected at least fourteen poole-bootload host tests")
    bootload_tests = int(match.group(1))
    package_tests: dict[str, int] = {}
    for package, minimum in (
        ("poole-boot-artifact", 4),
        ("poole-inner-live", 5),
        ("poole-handoff", 8),
        ("poole-live-handoff", 8),
        ("poole-kmap", 14),
        ("poole-boot-exit", 5),
    ):
        package_output = qualify_native_pooleboot._run_checked(
            [
                str(cargo),
                "test",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                package,
                "--lib",
                "--target",
                "x86_64-pc-windows-msvc",
                "--locked",
                "--offline",
                "--target-dir",
                str(temporary_root / f"{package}-tests"),
                "--",
                "--test-threads=1",
            ],
            cwd=NATIVE_ROOT,
            env=environment,
        )
        package_match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", package_output)
        if package_match is None or int(package_match.group(1)) < minimum:
            raise QualificationError(f"expected at least {minimum} {package} host tests")
        package_tests[package] = int(package_match.group(1))
    fmt_packages = (
        "poole-boot-artifact",
        "poole-inner-live",
        "poole-bootload",
        "poole-handoff",
        "poole-live-handoff",
        "poole-kmap",
        "poole-boot-exit",
        "pooleboot",
    )
    for package in fmt_packages:
        qualify_native_pooleboot._run_checked(
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
            env=environment,
        )
    clippy_profiles = (
        ("poole-boot-artifact", "--lib", "x86_64-pc-windows-msvc", "clippy-artifact-host"),
        ("poole-boot-artifact", "--lib", "x86_64-unknown-uefi", "clippy-artifact-uefi"),
        ("poole-inner-live", "--lib", "x86_64-pc-windows-msvc", "clippy-inner-host"),
        ("poole-inner-live", "--lib", "x86_64-unknown-none", "clippy-inner-none"),
        ("poole-inner-live", "--lib", "x86_64-unknown-uefi", "clippy-inner-uefi"),
        ("poole-bootload", "--lib", "x86_64-pc-windows-msvc", "clippy-bootload-host"),
        ("poole-bootload", "--lib", "x86_64-unknown-uefi", "clippy-bootload-uefi"),
        ("poole-handoff", "--lib", "x86_64-pc-windows-msvc", "clippy-handoff-host"),
        ("poole-handoff", "--lib", "x86_64-unknown-uefi", "clippy-handoff-uefi"),
        ("poole-live-handoff", "--lib", "x86_64-pc-windows-msvc", "clippy-live-handoff-host"),
        ("poole-live-handoff", "--lib", "x86_64-unknown-uefi", "clippy-live-handoff-uefi"),
        ("poole-kmap", "--lib", "x86_64-pc-windows-msvc", "clippy-kmap-host"),
        ("poole-kmap", "--lib", "x86_64-unknown-uefi", "clippy-kmap-uefi"),
        ("poole-boot-exit", "--lib", "x86_64-pc-windows-msvc", "clippy-boot-exit-host"),
        ("poole-boot-exit", "--lib", "x86_64-unknown-uefi", "clippy-boot-exit-uefi"),
        ("pooleboot", "--bin", "x86_64-unknown-uefi", "clippy-pooleboot-uefi"),
    )
    for package, kind, target, target_dir in clippy_profiles:
        command = [
            str(cargo),
            "clippy",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            package,
            kind,
        ]
        if kind == "--bin":
            command.append("PooleBoot")
        command.extend(
            [
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(temporary_root / target_dir),
                "--",
                "-D",
                "warnings",
            ]
        )
        qualify_native_pooleboot._run_checked(
            command,
            cwd=NATIVE_ROOT,
            env=environment,
        )
    probe_output = qualify_native_pooleboot._run_checked(
        [
            str(cargo),
            "run",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-kmap",
            "--bin",
            "pkmap2_probe",
            "--release",
            "--target",
            "x86_64-pc-windows-msvc",
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "kmap-probe"),
        ],
        cwd=NATIVE_ROOT,
        env=environment,
    )
    probe_lines = [line for line in probe_output.splitlines() if line.startswith("PKMAP2 PASS")]
    if len(probe_lines) != 1:
        raise QualificationError("expected one exact PKMAP2 Rust probe line")
    probe = native_kernel_map.parse_retained_probe_output(probe_lines[0])
    artifact_probe_target = temporary_root / "artifact-probe"
    qualify_native_pooleboot._run_checked(
        [
            str(cargo),
            "build",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-boot-artifact",
            "--bin",
            "pbart1-probe",
            "--features",
            "host-probe",
            "--release",
            "--target",
            "x86_64-pc-windows-msvc",
            "--locked",
            "--offline",
            "--target-dir",
            str(artifact_probe_target),
        ],
        cwd=NATIVE_ROOT,
        env=environment,
    )
    artifact_probe = (
        artifact_probe_target
        / "x86_64-pc-windows-msvc"
        / "release"
        / "pbart1-probe.exe"
    )
    canonical_artifacts = native_kernel_load.native_boot_artifact.canonical_artifacts()
    hostile = bytearray(canonical_artifacts[native_kernel_load.native_boot_artifact.ROLES[0]])
    hostile[-1] ^= 1
    requests = [
        *(f"P:{value.hex().upper()}" for value in canonical_artifacts.values()),
        f"P:{bytes(hostile).hex().upper()}",
    ]
    completed = subprocess.run(
        [str(artifact_probe)],
        input="\n".join(requests) + "\n",
        cwd=NATIVE_ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise QualificationError("PBART1 Rust probe failed")
    observed = completed.stdout.replace("\r\n", "\n").strip().splitlines()
    expected = []
    for data in canonical_artifacts.values():
        summary = native_kernel_load.native_boot_artifact.summary(data)
        expected.append(
            "OK;"
            f"role={summary['role']};version={summary['version']};"
            f"payload_bytes={summary['payload_bytes']};"
            f"payload_sha256={summary['payload_sha256']};"
            f"file_sha256={summary['file_sha256']}"
        )
    expected.append("ERR:artifact_digest")
    if observed != expected:
        raise QualificationError("PBART1 Rust and Python probe summaries diverge")
    inner_probe_target = temporary_root / "inner-probe"
    qualify_native_pooleboot._run_checked(
        [
            str(cargo),
            "build",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-inner-live",
            "--bin",
            "pinner1-probe",
            "--features",
            "host-probe",
            "--release",
            "--target",
            "x86_64-pc-windows-msvc",
            "--locked",
            "--offline",
            "--target-dir",
            str(inner_probe_target),
        ],
        cwd=NATIVE_ROOT,
        env=environment,
    )
    inner_probe = (
        inner_probe_target
        / "x86_64-pc-windows-msvc"
        / "release"
        / "pinner1-probe.exe"
    )
    canonical_files = [canonical_artifacts[role] for role in native_kernel_load.native_boot_artifact.ROLES]
    reordered = canonical_files[:]
    reordered[0], reordered[1] = reordered[1], reordered[0]
    outer_mutation = canonical_files[:]
    changed_outer = bytearray(outer_mutation[2])
    changed_outer[-1] ^= 1
    outer_mutation[2] = bytes(changed_outer)
    inner_mutation = canonical_files[:]
    changed_initial = bytearray(
        native_kernel_load.native_boot_artifact.parse(inner_mutation[0]).payload
    )
    changed_initial[-1] ^= 1
    inner_mutation[0] = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_INITIAL_SYSTEM,
        1,
        bytes(changed_initial),
    )
    policy_mutation = canonical_files[:]
    changed_policy = bytearray(
        native_kernel_load.native_boot_artifact.parse(policy_mutation[5]).payload
    )
    changed_policy[160] ^= 1
    policy_mutation[5] = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_POLICY_BUNDLE,
        1,
        bytes(changed_policy),
    )

    def inner_request(files: list[bytes]) -> str:
        return "V:" + ":".join(data.hex().upper() for data in files)

    inner_requests = [
        inner_request(canonical_files),
        inner_request(reordered),
        inner_request(outer_mutation),
        inner_request(inner_mutation),
        inner_request(policy_mutation),
    ]
    inner_completed = subprocess.run(
        [str(inner_probe)],
        input="\n".join(inner_requests) + "\n",
        cwd=NATIVE_ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if inner_completed.returncode != 0:
        raise QualificationError("live inner-set Rust probe failed")
    inner_observed = (
        inner_completed.stdout.replace("\r\n", "\n").strip().splitlines()
    )
    inner_summary = native_kernel_load.native_inner_live.validate_development_set(
        canonical_files
    )
    inner_expected = [
        "OK;"
        f"artifacts={inner_summary['artifact_count']};"
        f"parsers={inner_summary['parser_count']};"
        f"bindings={inner_summary['cross_binding_count']};"
        f"denials={inner_summary['development_denial_count']};"
        f"file_bytes={inner_summary['file_bytes']};"
        f"payload_bytes={inner_summary['payload_bytes']};"
        f"set={inner_summary['retained_set_sha256']};"
        "grants=0;actions=0;state_writes=0;hardware_observations=0",
        "ERR:inner.initial.outer:artifact_role_binding",
        "ERR:inner.symbols.outer:artifact_digest",
        "ERR:inner.initial.parse:pinit_body_digest",
        "ERR:inner.policy.recovery_digest:inner_policy_payload_digest",
    ]
    if inner_observed != inner_expected:
        raise QualificationError("live inner-set Rust and Python probes diverge")
    return {
        "bootload_tests_passed": bootload_tests,
        "bootload_tests_total": bootload_tests,
        "artifact_tests_passed": package_tests["poole-boot-artifact"],
        "artifact_tests_total": package_tests["poole-boot-artifact"],
        "artifact_differential_cases": len(expected),
        "inner_tests_passed": package_tests["poole-inner-live"],
        "inner_tests_total": package_tests["poole-inner-live"],
        "inner_differential_cases": len(inner_expected),
        "handoff_tests_passed": package_tests["poole-handoff"],
        "handoff_tests_total": package_tests["poole-handoff"],
        "live_handoff_tests_passed": package_tests["poole-live-handoff"],
        "live_handoff_tests_total": package_tests["poole-live-handoff"],
        "kernel_map_tests_passed": package_tests["poole-kmap"],
        "kernel_map_tests_total": package_tests["poole-kmap"],
        "kernel_map_probe": probe,
        "boot_exit_tests_passed": package_tests["poole-boot-exit"],
        "boot_exit_tests_total": package_tests["poole-boot-exit"],
        "rustfmt_passed": True,
        "rustfmt_packages": list(fmt_packages),
        "clippy_passed": True,
        "clippy_run_count": len(clippy_profiles),
    }


def _rejected(action: Callable[[], object]) -> bool:
    try:
        action()
    except (ValueError, RuntimeError, KeyError, IndexError, struct.error):
        return True
    return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationError(message)


def _mutate(data: bytes, offset: int, value: int) -> bytes:
    changed = bytearray(data)
    changed[offset] = value
    return bytes(changed)


def _set_u32(data: bytes, offset: int, value: int) -> bytes:
    changed = bytearray(data)
    struct.pack_into("<I", changed, offset, value)
    return bytes(changed)


def _set_fat_entry_both(data: bytes, cluster: int, value: int) -> bytes:
    changed = bytearray(data)
    fat_sectors, _ = native_pooleboot._fat_sector_count()
    fat_bytes = fat_sectors * native_pooleboot.SECTOR_BYTES
    first = (
        native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
    ) * native_pooleboot.SECTOR_BYTES
    for copy_index in range(native_pooleboot.FAT_COUNT):
        struct.pack_into("<I", changed, first + copy_index * fat_bytes + cluster * 4, value)
    return bytes(changed)


def _replace_marker(markers: list[str], index: int, old: str, new: str) -> list[str]:
    changed = markers[:]
    if old not in changed[index]:
        raise QualificationError(f"marker mutation source is absent: {old}")
    changed[index] = changed[index].replace(old, new, 1)
    return changed


def _repair_pbp1_record(value: bytearray, record_index: int) -> None:
    descriptor = native_boot_handoff.HEADER_BYTES + record_index * native_boot_handoff.DESCRIPTOR_BYTES
    offset, length = struct.unpack_from("<II", value, descriptor + 8)
    struct.pack_into(
        "<I",
        value,
        descriptor + 20,
        native_boot_handoff._crc32(bytes(value[offset : offset + length])),
    )
    value[48:52] = b"\0" * 4
    struct.pack_into("<I", value, 48, native_boot_handoff._message_crc(bytes(value)))


def _mutated_pbp1(
    data: bytes,
    *,
    transfer_state: bool = False,
    artifact_digest: bool = False,
    artifact_role: bool = False,
    artifact_omission: bool = False,
    artifact_overlap: bool = False,
    artifact_signature: bool = False,
) -> bytes:
    handoff = native_boot_handoff.decode(data)
    changed = bytearray(data)
    if transfer_state:
        core = handoff.record(native_boot_handoff.RECORD_CORE)
        if core is None:
            raise QualificationError("live PBP1 core record is absent")
        struct.pack_into("<Q", changed, core.offset, native_boot_handoff.DEVELOPMENT_MODE)
        _repair_pbp1_record(changed, 0)
    if artifact_digest or artifact_role or artifact_omission or artifact_overlap or artifact_signature:
        artifact = handoff.record(native_boot_handoff.RECORD_LOADED_ARTIFACTS)
        if artifact is None:
            raise QualificationError("live PBP1 artifact record is absent")
        record_index = [item.record_type for item in handoff.records].index(
            native_boot_handoff.RECORD_LOADED_ARTIFACTS
        )
        if artifact_digest:
            changed[artifact.offset + 48] ^= 1
        if artifact_role:
            struct.pack_into(
                "<I",
                changed,
                artifact.offset + native_boot_handoff.ARTIFACT_ENTRY_BYTES,
                native_boot_handoff.ARTIFACT_POLICY_BUNDLE,
            )
        if artifact_overlap:
            kernel_physical = struct.unpack_from("<Q", changed, artifact.offset + 8)[0]
            struct.pack_into(
                "<Q",
                changed,
                artifact.offset + native_boot_handoff.ARTIFACT_ENTRY_BYTES + 8,
                kernel_physical,
            )
        if artifact_signature:
            flags_offset = artifact.offset + native_boot_handoff.ARTIFACT_ENTRY_BYTES + 4
            flags = struct.unpack_from("<I", changed, flags_offset)[0]
            struct.pack_into(
                "<I",
                changed,
                flags_offset,
                flags | native_boot_handoff.ARTIFACT_SIGNATURE_VERIFIED,
            )
        if artifact_omission:
            descriptor = (
                native_boot_handoff.HEADER_BYTES
                + record_index * native_boot_handoff.DESCRIPTOR_BYTES
            )
            struct.pack_into("<H", changed, descriptor + 18, artifact.element_count - 1)
            changed[48:52] = b"\0" * 4
            struct.pack_into(
                "<I", changed, 48, native_boot_handoff._message_crc(bytes(changed))
            )
        else:
            _repair_pbp1_record(changed, record_index)
    return bytes(changed)


def _negative_controls(
    media: bytes,
    inspection: dict[str, Any],
    markers: list[str],
    pbp1_data: bytes,
    pbp1_transcript: dict[str, Any],
    claims: dict[str, bool],
) -> list[dict[str, str]]:
    fat_sectors, _ = native_pooleboot._fat_sector_count()
    data_start_lba = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + native_pooleboot.FAT_COUNT * fat_sectors
    )
    cluster_bytes = native_pooleboot.SECTOR_BYTES * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    efi_clusters = inspection["files"][0]["cluster_count"]
    pooleos_cluster = 5 + efi_clusters
    config_cluster = pooleos_cluster + 1
    manifest_cluster = config_cluster + inspection["files"][1]["cluster_count"]
    kernel_cluster = manifest_cluster + inspection["files"][2]["cluster_count"]
    artifact_cluster = kernel_cluster + inspection["files"][3]["cluster_count"]
    efi_directory_offset = (
        data_start_lba + (3 - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    pooleos_directory_offset = (
        data_start_lba + (pooleos_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    config_offset = (
        data_start_lba + (config_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    manifest_offset = (
        data_start_lba + (manifest_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    kernel_offset = (
        data_start_lba + (kernel_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    artifact_offset = (
        data_start_lba + (artifact_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    if cluster_bytes != 512:
        raise QualificationError("negative controls assume the frozen one-sector cluster profile")

    expected_config_hash = inspection["files"][1]["sha256"]
    expected_manifest_hash = inspection["files"][2]["sha256"]
    expected_file_hashes = [item["sha256"] for item in inspection["files"]]

    def inspect_expected(candidate: bytes) -> dict[str, Any]:
        observed = native_kernel_load.inspect_media_bytes(candidate)
        if [item["sha256"] for item in observed["files"]] != expected_file_hashes:
            raise native_kernel_load.KernelLoadError("qualified product binding changed")
        return observed

    config_missing = _mutate(media, pooleos_directory_offset + 64, 0)
    config_empty = _set_u32(media, pooleos_directory_offset + 64 + 28, 0)
    config_oversize = _set_u32(
        media,
        pooleos_directory_offset + 64 + 28,
        native_kernel_load.native_boot_config.MAX_CONFIG_BYTES + 1,
    )
    config_malformed = _mutate(media, config_offset, ord("X"))
    manifest_missing = _mutate(media, pooleos_directory_offset + 96, 0)
    manifest_empty = _set_u32(media, pooleos_directory_offset + 96 + 28, 0)
    manifest_oversize = _set_u32(
        media,
        pooleos_directory_offset + 96 + 28,
        native_kernel_load.native_system_manifest.MAX_MANIFEST_BYTES + 1,
    )
    manifest_malformed = _mutate(media, manifest_offset, ord("X"))
    kernel_missing = _mutate(media, pooleos_directory_offset + 128, 0)
    kernel_empty = _set_u32(media, pooleos_directory_offset + 128 + 28, 0)
    kernel_oversize = _set_u32(
        media,
        pooleos_directory_offset + 128 + 28,
        native_kernel_load.native_elf_loader.MAX_FILE_BYTES + 1,
    )
    kernel_malformed = _mutate(media, kernel_offset, 0)
    fat_copy = bytearray(media)
    second_fat = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + fat_sectors
    ) * native_pooleboot.SECTOR_BYTES
    fat_copy[second_fat + config_cluster * 4] ^= 1
    fat_loop = _set_fat_entry_both(media, config_cluster, config_cluster)
    directory_path = _mutate(media, efi_directory_offset + 96, ord("X"))
    config_path = _mutate(media, pooleos_directory_offset + 64, ord("X"))
    manifest_path = _mutate(media, pooleos_directory_offset + 96, ord("X"))
    kernel_path = _mutate(media, pooleos_directory_offset + 128, ord("X"))
    config_content = bytearray(media)
    timeout = config_content.find(b"timeout_ms=0", config_offset, config_offset + cluster_bytes)
    if timeout < 0:
        raise QualificationError("canonical timeout field is absent")
    config_content[timeout + len("timeout_ms=")] = ord("1")
    manifest_content = bytearray(media)
    manifest_version = manifest_content.find(
        b"manifest_version=1", manifest_offset, manifest_offset + inspection["files"][2]["byte_count"]
    )
    if manifest_version < 0:
        raise QualificationError("canonical manifest version field is absent")
    manifest_content[manifest_version + len("manifest_version=")] = ord("2")
    kernel_content = bytearray(media)
    kernel_content[kernel_offset + 0x1000] ^= 1
    artifact_directory_offset = pooleos_directory_offset + 160
    artifact_missing = _mutate(media, artifact_directory_offset, 0)
    artifact_empty = _set_u32(media, artifact_directory_offset + 28, 0)
    artifact_oversize = _set_u32(
        media,
        artifact_directory_offset + 28,
        native_kernel_load.native_boot_artifact.MAX_FILE_BYTES + 1,
    )
    artifact_path = _mutate(media, artifact_directory_offset, ord("X"))
    artifact_content = _mutate(
        media,
        artifact_offset + native_kernel_load.native_boot_artifact.HEADER_BYTES,
        media[
            artifact_offset + native_kernel_load.native_boot_artifact.HEADER_BYTES
        ]
        ^ 1,
    )
    artifact_file_bytes = inspection["files"][4]["byte_count"]
    canonical_artifact = media[artifact_offset : artifact_offset + artifact_file_bytes]
    artifact_role = bytearray(canonical_artifact)
    struct.pack_into(
        "<I",
        artifact_role,
        16,
        native_kernel_load.native_boot_artifact.ROLE_POLICY_BUNDLE,
    )
    artifact_version = bytearray(canonical_artifact)
    struct.pack_into("<Q", artifact_version, 24, 0)
    artifact_payload_digest = bytearray(canonical_artifact)
    artifact_payload_digest[48] ^= 1
    artifact_manifest_digest = bytearray(media)
    payload_offset = artifact_offset + native_kernel_load.native_boot_artifact.HEADER_BYTES
    artifact_manifest_digest[payload_offset] ^= 1
    payload_bytes = struct.unpack_from("<Q", artifact_manifest_digest, artifact_offset + 32)[0]
    payload = bytes(
        artifact_manifest_digest[payload_offset : payload_offset + payload_bytes]
    )
    artifact_manifest_digest[
        artifact_offset + 48 : artifact_offset + 80
    ] = hashlib.sha256(payload).digest()
    invalid_inner = bytearray(
        canonical_artifact[native_kernel_load.native_boot_artifact.HEADER_BYTES :]
    )
    service2_flags = (
        native_kernel_load.native_initial_system.HEADER_BYTES
        + 3 * native_kernel_load.native_initial_system.COMPONENT_BYTES
        + native_kernel_load.native_initial_system.SERVICE_BYTES
        + 14
    )
    struct.pack_into("<H", invalid_inner, service2_flags, 1 << 15)
    invalid_inner[120:152] = hashlib.sha256(
        invalid_inner[native_kernel_load.native_initial_system.HEADER_BYTES :]
    ).digest()
    invalid_inner_artifact = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_INITIAL_SYSTEM,
        1,
        bytes(invalid_inner),
    )
    mismatched_inner_version = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_INITIAL_SYSTEM,
        2,
        native_kernel_load.native_initial_system.canonical_bundle(),
    )
    initial_bundle = native_kernel_load.native_initial_system.parse(
        native_kernel_load.native_initial_system.canonical_bundle()
    )
    canonical_recovery_artifact = native_kernel_load.canonical_artifact_files()[
        native_kernel_load.RECOVERY_PATH
    ]
    invalid_recovery_inner = bytearray(
        canonical_recovery_artifact[
            native_kernel_load.native_boot_artifact.HEADER_BYTES :
        ]
    )
    struct.pack_into(
        "<H",
        invalid_recovery_inner,
        native_kernel_load.native_recovery.SLOT_OFFSET + 2,
        1,
    )
    invalid_recovery_inner[104:136] = hashlib.sha256(
        invalid_recovery_inner[native_kernel_load.native_recovery.HEADER_BYTES :]
    ).digest()
    invalid_recovery_artifact = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_RECOVERY,
        1,
        bytes(invalid_recovery_inner),
    )
    mismatched_recovery_version = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_RECOVERY,
        2,
        native_kernel_load.native_recovery.canonical_bundle(),
    )
    recovery_bundle = native_kernel_load.native_recovery.parse(
        native_kernel_load.native_recovery.canonical_bundle()
    )
    canonical_symbols_artifact = native_kernel_load.canonical_artifact_files()[
        native_kernel_load.SYMBOLS_PATH
    ]
    invalid_symbols_inner = bytearray(
        canonical_symbols_artifact[
            native_kernel_load.native_boot_artifact.HEADER_BYTES :
        ]
    )
    first_symbol_flags = (
        native_kernel_load.native_symbols.HEADER_BYTES
        + len(native_kernel_load.native_symbols.canonical_segments())
        * native_kernel_load.native_symbols.SEGMENT_BYTES
        + 10
    )
    struct.pack_into("<H", invalid_symbols_inner, first_symbol_flags, 1 << 15)
    invalid_symbols_inner[304:336] = hashlib.sha256(
        invalid_symbols_inner[native_kernel_load.native_symbols.HEADER_BYTES :]
    ).digest()
    invalid_symbols_artifact = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_SYMBOLS,
        1,
        bytes(invalid_symbols_inner),
    )
    mismatched_symbols_version = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_SYMBOLS,
        2,
        native_kernel_load.native_symbols.canonical_bundle(),
    )
    symbols_bundle = native_kernel_load.native_symbols.parse(
        native_kernel_load.native_symbols.canonical_bundle()
    )
    canonical_microcode_artifact = native_kernel_load.canonical_artifact_files()[
        native_kernel_load.MICROCODE_PATH
    ]
    invalid_microcode_inner = bytearray(
        canonical_microcode_artifact[
            native_kernel_load.native_boot_artifact.HEADER_BYTES :
        ]
    )
    struct.pack_into(
        "<I",
        invalid_microcode_inner,
        native_kernel_load.native_microcode.HEADER_BYTES + 4,
        1 << 31,
    )
    invalid_microcode_inner[288:320] = hashlib.sha256(
        invalid_microcode_inner[native_kernel_load.native_microcode.HEADER_BYTES :]
    ).digest()
    invalid_microcode_inner[320:352] = bytes(32)
    invalid_microcode_inner[320:352] = hashlib.sha256(
        invalid_microcode_inner[: native_kernel_load.native_microcode.HEADER_BYTES]
    ).digest()
    invalid_microcode_artifact = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_MICROCODE,
        1,
        bytes(invalid_microcode_inner),
    )
    mismatched_microcode_version = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_MICROCODE,
        2,
        native_kernel_load.native_microcode.canonical_bundle(),
    )
    microcode_bundle = native_kernel_load.native_microcode.parse(
        native_kernel_load.native_microcode.canonical_bundle()
    )
    canonical_firmware_artifact = native_kernel_load.canonical_artifact_files()[
        native_kernel_load.FIRMWARE_PATH
    ]
    invalid_firmware_inner = bytearray(
        canonical_firmware_artifact[
            native_kernel_load.native_boot_artifact.HEADER_BYTES :
        ]
    )
    struct.pack_into(
        "<I",
        invalid_firmware_inner,
        native_kernel_load.native_firmware.HEADER_BYTES + 16,
        0,
    )
    invalid_firmware_inner[376:408] = hashlib.sha256(
        invalid_firmware_inner[native_kernel_load.native_firmware.HEADER_BYTES :]
    ).digest()
    invalid_firmware_artifact = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_FIRMWARE_MANIFEST,
        1,
        bytes(invalid_firmware_inner),
    )
    mismatched_firmware_version = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_FIRMWARE_MANIFEST,
        2,
        native_kernel_load.native_firmware.canonical_bundle(),
    )
    firmware_bundle = native_kernel_load.native_firmware.parse(
        native_kernel_load.native_firmware.canonical_bundle()
    )
    canonical_policy_artifact = native_kernel_load.canonical_artifact_files()[
        native_kernel_load.POLICY_PATH
    ]
    invalid_policy_inner = bytearray(
        canonical_policy_artifact[
            native_kernel_load.native_boot_artifact.HEADER_BYTES :
        ]
    )
    invalid_policy_inner[-1] ^= 1
    invalid_policy_artifact = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_POLICY_BUNDLE,
        1,
        bytes(invalid_policy_inner),
    )
    mismatched_policy_version = native_kernel_load.native_boot_artifact.encode(
        native_kernel_load.native_boot_artifact.ROLE_POLICY_BUNDLE,
        2,
        native_kernel_load.native_policy.canonical_bundle(),
    )
    policy_bundle = native_kernel_load.native_policy.parse(
        native_kernel_load.native_policy.canonical_bundle()
    )

    marker_summary = native_kernel_load.validate_markers(markers)
    config_oracle = copy.deepcopy(inspection)
    config_oracle["config"]["timeout_ms"] += 1
    manifest_oracle = copy.deepcopy(inspection)
    manifest_oracle["manifest"]["manifest_version"] += 1
    elf_oracle = copy.deepcopy(inspection)
    elf_oracle["kernel"]["plan"]["image_size"] += native_pooleboot.SECTOR_BYTES
    hash_oracle = copy.deepcopy(inspection)
    hash_oracle["kernel"]["loaded_fnv1a64"] = "0" * 16
    artifact_oracle = copy.deepcopy(inspection)
    artifact_oracle["artifact_set"]["fnv1a64"] = "0" * 16
    inner_oracle = copy.deepcopy(inspection)
    inner_oracle["inner_set"]["retained_set_sha256"] = "0" * 64
    overreach = dict(claims)
    overreach["kernel_entry_called"] = True
    stale_binding = native_kernel_load.file_binding(ROOT, native_kernel_load.CONTRACT_RELATIVE)
    stale_binding["sha256"] = "0" * 64

    transcript = native_live_boot_handoff.format_transcript(pbp1_data)
    transcript_lines = transcript.decode("ascii").splitlines()
    duplicate_begin = ("\n".join([transcript_lines[0], transcript_lines[0], *transcript_lines[1:]]) + "\n").encode("ascii")
    offset_gap_lines = transcript_lines[:]
    offset_gap_lines[1] = offset_gap_lines[1].replace("offset=0", "offset=1", 1)
    offset_gap = ("\n".join(offset_gap_lines) + "\n").encode("ascii")
    nonhex_lines = transcript_lines[:]
    nonhex_lines[1] = nonhex_lines[1][:-1] + "G"
    nonhex = ("\n".join(nonhex_lines) + "\n").encode("ascii")
    byte_count_lines = transcript_lines[:]
    byte_count_lines[0] = byte_count_lines[0].replace(
        f"bytes={len(pbp1_data)}", f"bytes={len(pbp1_data) + 1}", 1
    )
    byte_count = ("\n".join(byte_count_lines) + "\n").encode("ascii")
    crc_lines = transcript_lines[:]
    crc_lines[-1] = crc_lines[-1].replace(
        f"message_crc32={native_boot_handoff._u32(pbp1_data, 48):08X}",
        "message_crc32=00000000",
        1,
    )
    wrong_crc = ("\n".join(crc_lines) + "\n").encode("ascii")
    fnv_lines = transcript_lines[:]
    fnv_lines[-1] = fnv_lines[-1].replace(
        f"fnv1a64={native_live_boot_handoff.fnv1a64(pbp1_data):016X}",
        "fnv1a64=0000000000000000",
        1,
    )
    wrong_fnv = ("\n".join(fnv_lines) + "\n").encode("ascii")
    transfer_state = native_live_boot_handoff.format_transcript(
        _mutated_pbp1(pbp1_data, transfer_state=True)
    )
    artifact_digest_summary = native_live_boot_handoff.extract_transcript(
        native_live_boot_handoff.format_transcript(
            _mutated_pbp1(pbp1_data, artifact_digest=True)
        )
    ).summary
    artifact_role_pbp1 = _mutated_pbp1(pbp1_data, artifact_role=True)
    artifact_omission_pbp1 = _mutated_pbp1(pbp1_data, artifact_omission=True)
    artifact_overlap_pbp1 = _mutated_pbp1(pbp1_data, artifact_overlap=True)
    artifact_signature_pbp1 = _mutated_pbp1(pbp1_data, artifact_signature=True)
    marker_byte_divergence = copy.deepcopy(marker_summary)
    marker_byte_divergence["pbp1"]["byte_count"] += 8
    marker_memory_divergence = copy.deepcopy(marker_summary)
    marker_memory_divergence["pbp1"]["memory_entry_count"] += 1

    physical_bits = marker_summary["kernel_map"]["physical_address_bits"]
    kmap_request = native_kernel_map.request_from_elf_plan(
        inspection["kernel"]["plan"], physical_bits
    )
    kmap_model = native_kernel_map.build_model(kmap_request)
    cpu_profile = {
        "paging": True,
        "pae": True,
        "long_mode": True,
        "write_protect": True,
        "nx_supported": True,
        "nx_enabled": True,
        "five_level_paging": False,
        "pcid_enabled": False,
        "physical_address_bits": physical_bits,
    }
    occupied_root = [0] * native_kernel_map.TABLE_ENTRIES
    occupied_root[511] = 0x4003
    alignment_mappings = list(kmap_request.mappings)
    alignment_mappings[1] = dataclasses.replace(
        alignment_mappings[1], virtual_offset=alignment_mappings[1].virtual_offset + 1
    )
    gap_mappings = list(kmap_request.mappings)
    gap_mappings[1] = dataclasses.replace(
        gap_mappings[1], virtual_offset=gap_mappings[1].virtual_offset + native_kernel_map.PAGE_SIZE
    )
    overlap_mappings = list(kmap_request.mappings)
    overlap_mappings[1] = dataclasses.replace(
        overlap_mappings[1], virtual_offset=overlap_mappings[1].virtual_offset - native_kernel_map.PAGE_SIZE
    )
    wx_mappings = list(kmap_request.mappings)
    wx_mappings[3] = dataclasses.replace(wx_mappings[3], permissions="rwx")
    wrong_leaf_physical = native_kernel_map.mutated_model(
        kmap_model,
        ("leaves", 0, "physical_offset"),
        native_kernel_map.PAGE_SIZE,
    )
    wrong_leaf_flags = native_kernel_map.mutated_model(
        kmap_model,
        ("leaves", 0, "normalized_flags"),
        "0000000000000003",
    )
    framebuffer = {
        "first_physical": 0x8000_0000,
        "last_physical": 0x803F_FFFF,
        "first_page_size": marker_summary["kernel_map"]["framebuffer_first_page_bytes"],
        "last_page_size": marker_summary["kernel_map"]["framebuffer_last_page_bytes"],
        "cache_signature": marker_summary["kernel_map"]["framebuffer_cache_signature"],
    }
    framebuffer_translation = dict(framebuffer)
    framebuffer_translation["last_physical"] += 1
    framebuffer_cache = dict(framebuffer)
    framebuffer_cache["cache_signature"] = "3F" if framebuffer["cache_signature"] != "3F" else "00"
    lifecycle = [
        {"state": "prepared", "original_cr3": 0x1000},
        {"state": "candidate_active", "firmware_call_count": 0},
        {"state": "restored", "observed_cr3": 0x1000},
        {"state": "retained", "table_pages_freed": 0},
    ]
    activation_lifecycle = copy.deepcopy(lifecycle)
    activation_lifecycle[1]["state"] = "activation_mismatch"
    rollback_lifecycle = copy.deepcopy(lifecycle)
    rollback_lifecycle[2]["observed_cr3"] = 0x2000
    firmware_lifecycle = copy.deepcopy(lifecycle)
    firmware_lifecycle[1]["firmware_call_count"] = 1
    retention_lifecycle = copy.deepcopy(lifecycle)
    retention_lifecycle[3]["table_pages_freed"] = native_kernel_map.TABLE_PAGE_COUNT
    map_oracle = copy.deepcopy(inspection)
    map_oracle["kernel"]["plan"]["mappings"][1]["permissions"] = "r"

    retained = marker_summary["kernel_map"]["retained"]
    runtime_kmap_request = dataclasses.replace(
        kmap_request, physical_base=retained["kernel_physical_base"]
    )
    retained_request = native_kernel_map.RetainedRequest(
        stack_physical_base=retained["stack_physical_base"],
        stack_page_count=retained["stack_page_count"],
        handoff_physical_base=retained["handoff_physical_base"],
        handoff_capacity_bytes=retained["handoff_page_count"] * native_kernel_map.PAGE_SIZE,
    )
    retained_overlap = dataclasses.replace(
        retained_request, stack_physical_base=retained["kernel_physical_base"]
    )
    retained_stack_shape = dataclasses.replace(retained_request, stack_page_count=7)
    guard_mappings = list(runtime_kmap_request.mappings)
    guard_mappings[-1] = dataclasses.replace(
        guard_mappings[-1],
        byte_count=guard_mappings[-1].byte_count + native_kernel_map.PAGE_SIZE,
    )
    guard_request = dataclasses.replace(
        runtime_kmap_request,
        image_bytes=runtime_kmap_request.image_bytes + native_kernel_map.PAGE_SIZE,
        page_count=runtime_kmap_request.page_count + 1,
        mappings=tuple(guard_mappings),
    )

    range_omission = copy.deepcopy(pbp1_transcript)
    range_kind = copy.deepcopy(pbp1_transcript)
    artifact_range_omission = copy.deepcopy(pbp1_transcript)
    stack_start = retained["stack_physical_base"]
    covering_index = next(
        (
            index
            for index, entry in enumerate(pbp1_transcript["memory_entries"])
            if int(entry["physical_start"], 16)
            <= stack_start
            < int(entry["physical_start"], 16)
            + entry["page_count"] * native_kernel_map.PAGE_SIZE
        ),
        None,
    )
    if covering_index is None:
        raise QualificationError("final PBP1 stack descriptor is absent")
    range_omission["memory_entries"].pop(covering_index)
    range_kind["memory_entries"][covering_index]["kind"] = native_boot_handoff.MEMORY_USABLE
    first_artifact_start = int(pbp1_transcript["artifacts"][1]["physical_base"], 16)
    artifact_covering_index = next(
        (
            index
            for index, entry in enumerate(pbp1_transcript["memory_entries"])
            if int(entry["physical_start"], 16)
            <= first_artifact_start
            < int(entry["physical_start"], 16)
            + entry["page_count"] * native_kernel_map.PAGE_SIZE
        ),
        None,
    )
    if artifact_covering_index is None:
        raise QualificationError("final PBP1 artifact descriptor is absent")
    artifact_range_omission["memory_entries"].pop(artifact_covering_index)
    root_binding = copy.deepcopy(marker_summary)
    root_binding["kernel_map"]["retained"]["page_table_root_physical"] += native_kernel_map.PAGE_SIZE
    stack_binding = copy.deepcopy(marker_summary)
    stack_binding["kernel_map"]["retained"]["stack_physical_base"] += 0x0100_0000
    handoff_binding = copy.deepcopy(marker_summary)
    handoff_binding["kernel_map"]["retained"]["handoff_virtual_base"] += native_kernel_map.PAGE_SIZE

    exit_map = {
        "map_key": 1,
        "map_bytes": 48 * 94,
        "descriptor_size": 48,
        "descriptor_version": 1,
    }
    exit_handoff = {
        "byte_count": pbp1_transcript["byte_count"],
        "boot_services_exited": True,
        "development_mode": True,
        "stack_top_virtual": retained["stack_top_virtual"],
        "page_table_root_physical": retained["page_table_root_physical"],
        "kernel_signature_verified": False,
        "kernel_entry_profile_valid": False,
    }

    def exit_attempt(key: int, result: str) -> list[dict[str, Any]]:
        return [
            {"operation": "get_memory_map", "map": {**exit_map, "map_key": key}},
            {"operation": "finalize_handoff", "handoff": dict(exit_handoff)},
            {"operation": "exit_boot_services", "result": result},
        ]

    success_trace = exit_attempt(1, "success")

    observations = [
        ("NEG-N5-KLOAD-CONFIG-MISSING", _rejected(lambda: inspect_expected(config_missing))),
        ("NEG-N5-KLOAD-CONFIG-EMPTY", _rejected(lambda: inspect_expected(config_empty))),
        ("NEG-N5-KLOAD-CONFIG-OVERSIZE", _rejected(lambda: inspect_expected(config_oversize))),
        ("NEG-N5-KLOAD-CONFIG-MALFORMED", _rejected(lambda: inspect_expected(config_malformed))),
        ("NEG-N5-KLOAD-MANIFEST-MISSING", _rejected(lambda: inspect_expected(manifest_missing))),
        ("NEG-N5-KLOAD-MANIFEST-EMPTY", _rejected(lambda: inspect_expected(manifest_empty))),
        ("NEG-N5-KLOAD-MANIFEST-OVERSIZE", _rejected(lambda: inspect_expected(manifest_oversize))),
        ("NEG-N5-KLOAD-MANIFEST-MALFORMED", _rejected(lambda: inspect_expected(manifest_malformed))),
        ("NEG-N5-KLOAD-KERNEL-MISSING", _rejected(lambda: inspect_expected(kernel_missing))),
        ("NEG-N5-KLOAD-KERNEL-EMPTY", _rejected(lambda: inspect_expected(kernel_empty))),
        ("NEG-N5-KLOAD-KERNEL-OVERSIZE", _rejected(lambda: inspect_expected(kernel_oversize))),
        ("NEG-N5-KLOAD-KERNEL-MALFORMED", _rejected(lambda: inspect_expected(kernel_malformed))),
        ("NEG-N5-KLOAD-FAT-COPY", _rejected(lambda: inspect_expected(bytes(fat_copy)))),
        ("NEG-N5-KLOAD-FAT-CHAIN-LOOP", _rejected(lambda: inspect_expected(fat_loop))),
        ("NEG-N5-KLOAD-DIRECTORY-PATH", _rejected(lambda: inspect_expected(directory_path))),
        ("NEG-N5-KLOAD-CONFIG-PATH", _rejected(lambda: inspect_expected(config_path))),
        ("NEG-N5-KLOAD-MANIFEST-PATH", _rejected(lambda: inspect_expected(manifest_path))),
        ("NEG-N5-KLOAD-KERNEL-PATH", _rejected(lambda: inspect_expected(kernel_path))),
        ("NEG-N5-KLOAD-CONFIG-CONTENT", _rejected(lambda: inspect_expected(bytes(config_content)))),
        ("NEG-N5-KLOAD-MANIFEST-CONTENT", _rejected(lambda: inspect_expected(bytes(manifest_content)))),
        ("NEG-N5-KLOAD-KERNEL-CONTENT", _rejected(lambda: inspect_expected(bytes(kernel_content)))),
        ("NEG-N5-KLOAD-ARTIFACT-MISSING", _rejected(lambda: inspect_expected(artifact_missing))),
        ("NEG-N5-KLOAD-ARTIFACT-EMPTY", _rejected(lambda: inspect_expected(artifact_empty))),
        ("NEG-N5-KLOAD-ARTIFACT-OVERSIZE", _rejected(lambda: inspect_expected(artifact_oversize))),
        ("NEG-N5-KLOAD-ARTIFACT-PATH", _rejected(lambda: inspect_expected(artifact_path))),
        ("NEG-N5-KLOAD-ARTIFACT-CONTENT", _rejected(lambda: inspect_expected(artifact_content))),
        ("NEG-N5-KLOAD-ARTIFACT-ROLE", _rejected(lambda: native_kernel_load.native_boot_artifact.parse_bound(bytes(artifact_role), native_kernel_load.native_boot_artifact.ROLE_INITIAL_SYSTEM, 1))),
        ("NEG-N5-KLOAD-ARTIFACT-VERSION", _rejected(lambda: native_kernel_load.native_boot_artifact.parse(bytes(artifact_version)))),
        ("NEG-N5-KLOAD-ARTIFACT-PAYLOAD-DIGEST", _rejected(lambda: native_kernel_load.native_boot_artifact.parse(bytes(artifact_payload_digest)))),
        ("NEG-N5-KLOAD-ARTIFACT-MANIFEST-DIGEST", _rejected(lambda: inspect_expected(bytes(artifact_manifest_digest)))),
        ("NEG-N5-KLOAD-INITIAL-SYSTEM-INNER-SEMANTICS", _rejected(lambda: native_kernel_load.initial_system_oracle(invalid_inner_artifact, 1))),
        ("NEG-N5-KLOAD-INITIAL-SYSTEM-INNER-VERSION", _rejected(lambda: native_kernel_load.initial_system_oracle(mismatched_inner_version, 2))),
        ("NEG-N5-KLOAD-INITIAL-SYSTEM-ACTIVATION-OVERREACH", _rejected(lambda: native_kernel_load.native_initial_system.authorize_activation(initial_bundle, native_kernel_load.native_initial_system.development_activation_context()))),
        ("NEG-N5-KLOAD-RECOVERY-INNER-SEMANTICS", _rejected(lambda: native_kernel_load.recovery_oracle(invalid_recovery_artifact, 1))),
        ("NEG-N5-KLOAD-RECOVERY-INNER-VERSION", _rejected(lambda: native_kernel_load.recovery_oracle(mismatched_recovery_version, 2))),
        ("NEG-N5-KLOAD-RECOVERY-ACTIVATION-OVERREACH", _rejected(lambda: native_kernel_load.native_recovery.authorize_activation(recovery_bundle, native_kernel_load.native_recovery.development_activation_context()))),
        ("NEG-N5-KLOAD-SYMBOLS-INNER-SEMANTICS", _rejected(lambda: native_kernel_load.symbols_oracle(invalid_symbols_artifact, 1))),
        ("NEG-N5-KLOAD-SYMBOLS-INNER-VERSION", _rejected(lambda: native_kernel_load.symbols_oracle(mismatched_symbols_version, 2))),
        ("NEG-N5-KLOAD-SYMBOLS-ACTIVATION-OVERREACH", _rejected(lambda: native_kernel_load.native_symbols.authorize_consumption(symbols_bundle, native_kernel_load.native_symbols.development_consumption_context(symbols_bundle)))),
        ("NEG-N5-KLOAD-MICROCODE-INNER-SEMANTICS", _rejected(lambda: native_kernel_load.microcode_oracle(invalid_microcode_artifact, 1))),
        ("NEG-N5-KLOAD-MICROCODE-INNER-VERSION", _rejected(lambda: native_kernel_load.microcode_oracle(mismatched_microcode_version, 2))),
        ("NEG-N5-KLOAD-MICROCODE-ACTIVATION-OVERREACH", _rejected(lambda: native_kernel_load.native_microcode.authorize_apply_plan(microcode_bundle, native_kernel_load.native_microcode.development_apply_context(microcode_bundle)))),
        ("NEG-N5-KLOAD-FIRMWARE-INNER-SEMANTICS", _rejected(lambda: native_kernel_load.firmware_oracle(invalid_firmware_artifact, 1))),
        ("NEG-N5-KLOAD-FIRMWARE-INNER-VERSION", _rejected(lambda: native_kernel_load.firmware_oracle(mismatched_firmware_version, 2))),
        ("NEG-N5-KLOAD-FIRMWARE-ACTIVATION-OVERREACH", _rejected(lambda: native_kernel_load.native_firmware.authorize_dry_run_plan(firmware_bundle, native_kernel_load.native_firmware.development_activation_context(firmware_bundle)))),
        ("NEG-N5-KLOAD-POLICY-INNER-SEMANTICS", _rejected(lambda: native_kernel_load.policy_oracle(invalid_policy_artifact, 1))),
        ("NEG-N5-KLOAD-POLICY-INNER-VERSION", _rejected(lambda: native_kernel_load.policy_oracle(mismatched_policy_version, 2))),
        ("NEG-N5-KLOAD-POLICY-ACTIVATION-OVERREACH", _rejected(lambda: native_kernel_load.native_policy.authorize_dry_run_decision(policy_bundle, native_kernel_load.native_policy.development_activation_context(policy_bundle)))),
        ("NEG-N5-KLOAD-MARKER-OMISSION", _rejected(lambda: native_kernel_load.validate_markers(markers[:-1]))),
        ("NEG-N5-KLOAD-MARKER-ORDER", _rejected(lambda: native_kernel_load.validate_markers([markers[1], markers[0], *markers[2:]]))),
        ("NEG-N5-KLOAD-MARKER-CONFIG-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 7, f"bytes={marker_summary['boot_config']['byte_count']}", "bytes=16385")))),
        ("NEG-N5-KLOAD-MARKER-MANIFEST-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 8, f"bytes={marker_summary['manifest']['byte_count']}", "bytes=65537")))),
        ("NEG-N5-KLOAD-MARKER-MANIFEST-SLOT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 8, f"slot={marker_summary['manifest']['slot']}", "slot=4" if marker_summary['manifest']['slot'] != 4 else "slot=3")))),
        ("NEG-N5-KLOAD-MARKER-DIGEST", _rejected(lambda: native_kernel_load.validate_oracle_binding(native_kernel_load.validate_markers(_replace_marker(markers, 9, f"sha256_prefix={marker_summary['manifest']['kernel_sha256_prefix']}", "sha256_prefix=0000000000000000")), inspection, pbp1_transcript))),
        ("NEG-N5-KLOAD-MARKER-KERNEL-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 10, f"bytes={marker_summary['kernel']['file_byte_count']}", "bytes=1048577")))),
        ("NEG-N5-KLOAD-MARKER-PAGE-MATH", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 11, f"pages={marker_summary['kernel']['page_count']}", f"pages={marker_summary['kernel']['page_count'] + 1}")))),
        ("NEG-N5-KLOAD-MARKER-ENTRY-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 11, f"entry_offset={marker_summary['kernel']['entry_offset']}", f"entry_offset={marker_summary['kernel']['image_byte_count']}")))),
        ("NEG-N5-KLOAD-MARKER-ARTIFACT-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 12, "count=6", "count=5")))),
        ("NEG-N5-KLOAD-MARKER-ARTIFACT-SIGNATURE", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 12, "signatures=0", "signatures=1")))),
        ("NEG-N5-KLOAD-MARKER-INNER-PARSER", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "parsers=6", "parsers=5")))),
        ("NEG-N5-KLOAD-MARKER-INNER-BINDING", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "bindings=6", "bindings=5")))),
        ("NEG-N5-KLOAD-MARKER-INNER-DENIAL", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "denials=6", "denials=5")))),
        ("NEG-N5-KLOAD-MARKER-INNER-DIGEST", _rejected(lambda: native_kernel_load.validate_oracle_binding(native_kernel_load.validate_markers(_replace_marker(markers, 13, f"sha256={marker_summary['inner_set']['retained_set_sha256']}", "sha256=" + "0" * 64)), inspection, pbp1_transcript))),
        ("NEG-N5-KLOAD-MARKER-INNER-AUTHORITY", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "authority_grants=0", "authority_grants=1")))),
        ("NEG-N5-KLOAD-MARKER-INNER-ACTION", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "actions=0", "actions=1")))),
        ("NEG-N5-KLOAD-MARKER-INNER-STATE", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "state_writes=0", "state_writes=1")))),
        ("NEG-N5-KLOAD-MARKER-INNER-HARDWARE", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 13, "hardware_observations=0", "hardware_observations=1")))),
        ("NEG-N5-KLOAD-INNER-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, inner_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-MARKER-MAPPING-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 16, "mappings=4", "mappings=3")))),
        ("NEG-N5-KLOAD-MARKER-WX", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 16, "wx=0", "wx=1")))),
        ("NEG-N5-KLOAD-MARKER-RETAIN-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 18, "stack_pages=8", "stack_pages=7")))),
        ("NEG-N5-KLOAD-MARKER-BOUNDARY", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 22, "selection=manifest_digest_untrusted", "selection=trusted")))),
        ("NEG-N5-KLOAD-CONFIG-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, config_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-MANIFEST-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, manifest_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-ELF-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, elf_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-LOADED-HASH-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, hash_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-ARTIFACT-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, artifact_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-CLAIM-OVERREACH", _rejected(lambda: native_kernel_load.validate_claims(overreach))),
        ("NEG-N5-KLOAD-STALE-BINDING", _rejected(lambda: _require(native_kernel_load.binding_matches(stale_binding, ROOT, native_kernel_load.CONTRACT_RELATIVE), "stale binding accepted"))),
        ("NEG-N5-PBP1-TRANSCRIPT-MISSING", _rejected(lambda: native_live_boot_handoff.extract_transcript(b""))),
        ("NEG-N5-PBP1-TRANSCRIPT-DUPLICATE-BEGIN", _rejected(lambda: native_live_boot_handoff.extract_transcript(duplicate_begin))),
        ("NEG-N5-PBP1-TRANSCRIPT-OFFSET-GAP", _rejected(lambda: native_live_boot_handoff.extract_transcript(offset_gap))),
        ("NEG-N5-PBP1-TRANSCRIPT-NONHEX", _rejected(lambda: native_live_boot_handoff.extract_transcript(nonhex))),
        ("NEG-N5-PBP1-TRANSCRIPT-BYTE-COUNT", _rejected(lambda: native_live_boot_handoff.extract_transcript(byte_count))),
        ("NEG-N5-PBP1-TRANSCRIPT-MESSAGE-CRC", _rejected(lambda: native_live_boot_handoff.extract_transcript(wrong_crc))),
        ("NEG-N5-PBP1-TRANSCRIPT-FNV", _rejected(lambda: native_live_boot_handoff.extract_transcript(wrong_fnv))),
        ("NEG-N5-PBP1-EXIT-STATE", _rejected(lambda: native_live_boot_handoff.extract_transcript(transfer_state))),
        ("NEG-N5-PBP1-ARTIFACT-DIGEST-ORACLE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, inspection, artifact_digest_summary))),
        ("NEG-N5-PBP1-ARTIFACT-ROLE", _rejected(lambda: native_live_boot_handoff.extract_transcript(native_live_boot_handoff.format_transcript(artifact_role_pbp1)))),
        ("NEG-N5-PBP1-ARTIFACT-OMISSION", _rejected(lambda: native_live_boot_handoff.extract_transcript(native_live_boot_handoff.format_transcript(artifact_omission_pbp1)))),
        ("NEG-N5-PBP1-ARTIFACT-OVERLAP", _rejected(lambda: native_live_boot_handoff.extract_transcript(native_live_boot_handoff.format_transcript(artifact_overlap_pbp1)))),
        ("NEG-N5-PBP1-ARTIFACT-SIGNATURE", _rejected(lambda: native_live_boot_handoff.extract_transcript(native_live_boot_handoff.format_transcript(artifact_signature_pbp1)))),
        ("NEG-N5-PBP1-ARTIFACT-RANGE-COVERAGE", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(artifact_range_omission, marker_summary, inspection))),
        ("NEG-N5-PBP1-MARKER-BYTE-DIVERGENCE", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(pbp1_transcript, marker_byte_divergence, inspection))),
        ("NEG-N5-PBP1-MARKER-MEMORY-DIVERGENCE", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(pbp1_transcript, marker_memory_divergence, inspection))),
        ("NEG-N5-PBP1-RETAINED-RANGE-OMISSION", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(range_omission, marker_summary, inspection))),
        ("NEG-N5-KMAP-CPU-WP", _rejected(lambda: native_kernel_map.validate_cpu({**cpu_profile, "write_protect": False}))),
        ("NEG-N5-KMAP-CPU-NX-SUPPORT", _rejected(lambda: native_kernel_map.validate_cpu({**cpu_profile, "nx_supported": False}))),
        ("NEG-N5-KMAP-CPU-NX-ENABLE", _rejected(lambda: native_kernel_map.validate_cpu({**cpu_profile, "nx_enabled": False}))),
        ("NEG-N5-KMAP-CPU-LA57", _rejected(lambda: native_kernel_map.validate_cpu({**cpu_profile, "five_level_paging": True}))),
        ("NEG-N5-KMAP-CPU-PCID", _rejected(lambda: native_kernel_map.validate_cpu({**cpu_profile, "pcid_enabled": True}))),
        ("NEG-N5-KMAP-ROOT-OCCUPIED", _rejected(lambda: native_kernel_map.build_model(kmap_request, original_root=occupied_root))),
        ("NEG-N5-KMAP-ALIGNMENT", _rejected(lambda: native_kernel_map.build_model(dataclasses.replace(kmap_request, mappings=tuple(alignment_mappings))))),
        ("NEG-N5-KMAP-COVERAGE-GAP", _rejected(lambda: native_kernel_map.build_model(dataclasses.replace(kmap_request, mappings=tuple(gap_mappings))))),
        ("NEG-N5-KMAP-COVERAGE-OVERLAP", _rejected(lambda: native_kernel_map.build_model(dataclasses.replace(kmap_request, mappings=tuple(overlap_mappings))))),
        ("NEG-N5-KMAP-PHYSICAL-RANGE", _rejected(lambda: native_kernel_map.build_model(dataclasses.replace(kmap_request, physical_base=kmap_request.physical_base + 1)))),
        ("NEG-N5-KMAP-TABLE-OVERLAP", _rejected(lambda: native_kernel_map.build_model(kmap_request, table_base=kmap_request.physical_base))),
        ("NEG-N5-KMAP-WX", _rejected(lambda: native_kernel_map.build_model(dataclasses.replace(kmap_request, mappings=tuple(wx_mappings))))),
        ("NEG-N5-KMAP-LEAF-PHYSICAL", _rejected(lambda: native_kernel_map.validate_model(wrong_leaf_physical))),
        ("NEG-N5-KMAP-LEAF-FLAGS", _rejected(lambda: native_kernel_map.validate_model(wrong_leaf_flags))),
        ("NEG-N5-KMAP-LARGE-PAGE", _rejected(lambda: native_kernel_map.validate_kernel_page_sizes([native_kernel_map.PAGE_SIZE, native_kernel_map.WINDOW_BYTES]))),
        ("NEG-N5-KMAP-FRAMEBUFFER-TRANSLATION", _rejected(lambda: native_kernel_map.validate_framebuffer_preserved(framebuffer, framebuffer_translation))),
        ("NEG-N5-KMAP-FRAMEBUFFER-CACHE", _rejected(lambda: native_kernel_map.validate_framebuffer_preserved(framebuffer, framebuffer_cache))),
        ("NEG-N5-KMAP-ACTIVATION", _rejected(lambda: native_kernel_map.validate_retained_lifecycle(activation_lifecycle))),
        ("NEG-N5-KMAP-ROLLBACK", _rejected(lambda: native_kernel_map.validate_retained_lifecycle(rollback_lifecycle))),
        ("NEG-N5-KMAP-FIRMWARE-ACTIVE", _rejected(lambda: native_kernel_map.validate_retained_lifecycle(firmware_lifecycle))),
        ("NEG-N5-KMAP-RETENTION", _rejected(lambda: native_kernel_map.validate_retained_lifecycle(retention_lifecycle))),
        ("NEG-N5-KMAP-MARKER-PLAN", _rejected(lambda: native_kernel_load.validate_oracle_binding(native_kernel_load.validate_markers(_replace_marker(markers, 16, f"leaf_fnv1a64={marker_summary['kernel_map']['leaf_fingerprint']}", "leaf_fnv1a64=0000000000000000")), inspection, pbp1_transcript))),
        ("NEG-N5-KMAP-MARKER-ACTIVE", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 17, f"mapped_fnv1a64={marker_summary['kernel_map']['mapped_fnv1a64']}", "mapped_fnv1a64=0000000000000000")))),
        ("NEG-N5-KMAP-MARKER-RETAIN", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 18, "firmware_calls_while_active=0", "firmware_calls_while_active=1")))),
        ("NEG-N5-KMAP-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, map_oracle, pbp1_transcript))),
        ("NEG-N5-PBP1-RETAINED-RANGE-KIND", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(range_kind, marker_summary, inspection))),
        ("NEG-N5-PBP1-ROOT-BINDING", _rejected(lambda: native_kernel_load.validate_oracle_binding(root_binding, inspection, pbp1_transcript))),
        ("NEG-N5-PBP1-STACK-BINDING", _rejected(lambda: native_kernel_load.validate_oracle_binding(stack_binding, inspection, pbp1_transcript))),
        ("NEG-N5-PBP1-HANDOFF-BINDING", _rejected(lambda: native_kernel_load.validate_oracle_binding(handoff_binding, inspection, pbp1_transcript))),
        ("NEG-N5-KMAP-RETAINED-OVERLAP", _rejected(lambda: native_kernel_map.build_retained_model(runtime_kmap_request, retained_overlap, table_base=retained["page_table_root_physical"]))),
        ("NEG-N5-KMAP-STACK-SHAPE", _rejected(lambda: native_kernel_map.build_retained_model(runtime_kmap_request, retained_stack_shape, table_base=retained["page_table_root_physical"]))),
        ("NEG-N5-KMAP-GUARD-LAYOUT", _rejected(lambda: native_kernel_map.build_retained_model(guard_request, retained_request, table_base=retained["page_table_root_physical"]))),
        ("NEG-N5-PBEXIT-MAP-SHAPE", _rejected(lambda: native_boot_exit.validate_final_map(native_boot_exit.FinalMap(1, 47, 48, 1)))),
        ("NEG-N5-PBEXIT-DESCRIPTOR-VERSION", _rejected(lambda: native_boot_exit.validate_final_map(native_boot_exit.FinalMap(1, 48, 48, 2)))),
        ("NEG-N5-PBEXIT-ORDER", _rejected(lambda: native_boot_exit.validate_trace(list(reversed(success_trace))))),
        ("NEG-N5-PBEXIT-NONRETRYABLE", _rejected(lambda: native_boot_exit.validate_trace(exit_attempt(1, "device_error")))),
        ("NEG-N5-PBEXIT-RETRY-EXHAUSTED", _rejected(lambda: native_boot_exit.validate_trace(sum((exit_attempt(index, "invalid_parameter") for index in range(4)), [])))),
        ("NEG-N5-PBEXIT-POST-ATTEMPT-FIRMWARE", _rejected(lambda: native_boot_exit.validate_trace([*exit_attempt(1, "invalid_parameter"), {"operation": "other_firmware"}, *exit_attempt(2, "success")]))),
        ("NEG-N5-PBEXIT-POST-EXIT-FIRMWARE", _rejected(lambda: native_boot_exit.validate_trace([*success_trace, {"operation": "get_memory_map", "map": exit_map}]))),
        ("NEG-N5-PBEXIT-MARKER-ATTEMPTS", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 20, "attempts=1", "attempts=2")))),
        ("NEG-N5-PBEXIT-MARKER-DESCRIPTOR", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 20, "descriptor_bytes=48", "descriptor_bytes=56")))),
        ("NEG-N5-PBEXIT-FIRMWARE-BOUNDARY", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 21, "calls_after_exit=0", "calls_after_exit=1")))),
        ("NEG-N5-PBEXIT-TRANSFER", _rejected(lambda: native_boot_exit.validate_trace([*success_trace, {"operation": "transfer"}]))),
    ]
    controls = [
        {
            "id": control_id,
            "expected": "reject",
            "observed": "reject" if rejected else "accept",
            "status": "pass" if rejected else "fail",
        }
        for control_id, rejected in observations
    ]
    if [item["id"] for item in controls] != list(native_kernel_load.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKLOAD6 negative-control order changed")
    if any(item["status"] != "pass" for item in controls):
        failed = [item["id"] for item in controls if item["status"] != "pass"]
        raise QualificationError("PKLOAD6 negative controls failed: " + ", ".join(failed))
    return controls


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> tuple[dict[str, Any], bytes]:
    contract = native_kernel_load.read_json(ROOT / native_kernel_load.CONTRACT_RELATIVE)
    contract_failures = native_kernel_load.contract_errors(contract, ROOT)
    if contract_failures:
        raise QualificationError("; ".join(contract_failures))
    manifest_readiness = native_kernel_load.native_system_manifest.read_json(
        ROOT / native_kernel_load.native_system_manifest.READINESS_RELATIVE
    )
    manifest_failures = native_kernel_load.native_system_manifest.readiness_errors(
        manifest_readiness, ROOT
    )
    if manifest_failures:
        raise QualificationError("current PSM1 readiness is stale: " + "; ".join(manifest_failures))
    symbol_readiness = native_kernel_load.native_symbols.read_json(
        ROOT / native_kernel_load.native_symbols.READINESS_RELATIVE
    )
    symbol_failures = native_kernel_load.native_symbols.readiness_errors(
        symbol_readiness, ROOT
    )
    if symbol_failures:
        raise QualificationError(
            "current PSYM1 readiness is stale: " + "; ".join(symbol_failures)
        )
    microcode_readiness = native_kernel_load.native_microcode.read_json(
        ROOT / native_kernel_load.native_microcode.READINESS_RELATIVE
    )
    microcode_failures = native_kernel_load.native_microcode.readiness_errors(
        microcode_readiness, ROOT
    )
    if microcode_failures:
        raise QualificationError(
            "current PMCU1 readiness is stale: " + "; ".join(microcode_failures)
        )
    firmware_readiness = native_kernel_load.native_firmware.read_json(
        ROOT / native_kernel_load.native_firmware.READINESS_RELATIVE
    )
    firmware_failures = native_kernel_load.native_firmware.readiness_errors(
        firmware_readiness, ROOT
    )
    if firmware_failures:
        raise QualificationError(
            "current PFWM1 readiness is stale: " + "; ".join(firmware_failures)
        )
    policy_readiness = native_kernel_load.native_policy.read_json(
        ROOT / native_kernel_load.native_policy.READINESS_RELATIVE
    )
    policy_failures = native_kernel_load.native_policy.readiness_errors(
        policy_readiness, ROOT
    )
    if policy_failures:
        raise QualificationError(
            "current PPOL1 readiness is stale: " + "; ".join(policy_failures)
        )
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "native-tier0").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pkload5-qualification-", dir=ROOT / "tmp") as temporary:
        temporary_root = Path(temporary)
        host_tests = _host_checks(toolchain_root, temporary_root)
        binary, build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root)
        kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
        host_tests.update(
            {
                "pooleboot_tests_passed": build["host_contract_test_pass_count"],
                "pooleboot_tests_total": build["host_contract_test_count"],
                "kernel_entry_tests_passed": kernel_readiness["host_tests"]["test_pass_count"],
                "kernel_entry_tests_total": kernel_readiness["host_tests"]["test_count"],
            }
        )
        config = native_kernel_load.canonical_config_bytes()
        manifest = native_kernel_load.canonical_manifest_bytes(kernel)
        media_first = native_kernel_load.build_media_bytes(binary, config, manifest, kernel)
        media_second = native_kernel_load.build_media_bytes(binary, config, manifest, kernel)
        if media_first != media_second:
            raise QualificationError("two PKLOAD6 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_first)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKLOAD6 media kernel differs from the fresh PKENTRY1 product")
        probe_expected = native_kernel_map.retained_probe_expectation(
            media_inspection["kernel"]["plan"], 48
        )
        if host_tests["kernel_map_probe"] != probe_expected:
            raise QualificationError("Rust PKMAP2 probe diverges from the independent Python oracle")
        media_path = temporary_root / "pkload5.img"
        media_path.write_bytes(media_first)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        pbp1_payloads: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkload5-run-{run_index}-",
                dir=ROOT / "runs" / "native-tier0",
            ) as run_temporary:
                run, screenshot, pbp1_data = qualify_native_pooleboot._execute_once(
                    f"run-{run_index}",
                    lock,
                    profile,
                    qemu_root,
                    media_path,
                    Path(run_temporary),
                    timeout,
                    native_kernel_load.validate_markers,
                )
                native_kernel_load.validate_oracle_binding(
                    run["marker_summary"],
                    media_inspection,
                    run["pbp1_transcript"],
                )
                runs.append(run)
                screenshots.append(screenshot)
                pbp1_payloads.append(pbp1_data)
    if runs[0]["markers"] != runs[1]["markers"]:
        raise QualificationError("two PKLOAD6 marker sequences differ")
    if screenshots[0] != screenshots[1]:
        raise QualificationError("two PKLOAD6 screenshots differ")
    if pbp1_payloads[0] != pbp1_payloads[1]:
        raise QualificationError("two PKLOAD6 PBP1 byte streams differ")

    claims = native_kernel_load.expected_claims()
    native_kernel_load.validate_claims(claims)
    controls = _negative_controls(
        media_first,
        media_inspection,
        runs[0]["markers"],
        pbp1_payloads[0],
        runs[0]["pbp1_transcript"],
        claims,
    )
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    command = qualify_native_pooleboot._normalized_command(profile)
    kernel_summary = runs[0]["marker_summary"]["kernel"]
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_load_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_live_inner_parse_pkmap2_exit_then_stop_non_promoting",
        "contract_id": native_kernel_load.CONTRACT_ID,
        "selected_move_id": "N5-INNER-LIVE-PARSE-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {
            "N5": "partial",
            "N5.1": "partial",
            "N5.4": "partial",
            "N5.5": "partial",
            "N5.6": "partial",
            "N5.8": "partial",
            "N5.9": "partial",
        },
        "bindings": {
            "contract": native_kernel_load.file_binding(ROOT, native_kernel_load.CONTRACT_RELATIVE),
            "kernel_map_contract": native_kernel_load.file_binding(
                ROOT, "specs/native-kernel-map-contract.json"
            ),
            "boot_exit_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.BOOT_EXIT_CONTRACT_RELATIVE
            ),
            "toolchain_lock": native_kernel_load.file_binding(ROOT, "specs/native-toolchain-lock.json"),
            "toolchain_qualification": native_kernel_load.file_binding(ROOT, "runs/native_toolchain_qualification.json"),
            "tier0_lock": native_kernel_load.file_binding(ROOT, native_tier0.LOCK_RELATIVE),
            "tier0_profile": native_kernel_load.file_binding(ROOT, native_tier0.PROFILE_RELATIVE),
            "tier0_readiness": native_kernel_load.file_binding(ROOT, native_tier0.READINESS_RELATIVE),
            "kernel_entry_contract": native_kernel_load.file_binding(ROOT, "specs/native-kernel-entry-contract.json"),
            "kernel_entry_readiness": native_kernel_load.file_binding(ROOT, "runs/native_kernel_entry_readiness.json"),
            "system_manifest_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_system_manifest.CONTRACT_RELATIVE
            ),
            "system_manifest_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_system_manifest.READINESS_RELATIVE
            ),
            "digest_provider": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_system_manifest.DIGEST_PROVIDER_RELATIVE
            ),
            "initial_system_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_initial_system.CONTRACT_RELATIVE.as_posix()
            ),
            "initial_system_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_initial_system.READINESS_RELATIVE.as_posix()
            ),
            "recovery_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_recovery.CONTRACT_RELATIVE.as_posix()
            ),
            "recovery_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_recovery.READINESS_RELATIVE.as_posix()
            ),
            "symbols_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_symbols.CONTRACT_RELATIVE.as_posix()
            ),
            "symbols_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_symbols.READINESS_RELATIVE.as_posix()
            ),
            "microcode_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_microcode.CONTRACT_RELATIVE.as_posix()
            ),
            "microcode_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_microcode.READINESS_RELATIVE.as_posix()
            ),
            "firmware_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_firmware.CONTRACT_RELATIVE.as_posix()
            ),
            "firmware_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_firmware.READINESS_RELATIVE.as_posix()
            ),
            "policy_contract": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_policy.CONTRACT_RELATIVE.as_posix()
            ),
            "policy_readiness": native_kernel_load.file_binding(
                ROOT, native_kernel_load.native_policy.READINESS_RELATIVE.as_posix()
            ),
            "implementation_inputs": [native_kernel_load.file_binding(ROOT, path) for path in native_kernel_load.IMPLEMENTATION_INPUTS],
        },
        "host_tests": host_tests,
        "build": build,
        "kernel_product": kernel_readiness["product"],
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
            "inspection": media_inspection,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "bootstrap-debug",
            "machine": "pc-q35-11.0",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": native_kernel_load.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "local_paths_recorded": False,
            "runs": runs,
        },
        "oracle": {
            "pbc1_python_match": True,
            "psm1_python_match": True,
            "pbart1_python_match": True,
            "pbart1_rust_python_match": True,
            "pbart1_manifest_cross_binding": True,
            "pinit1_host_oracle_match": True,
            "pinit1_development_activation_denied": True,
            "prec1_host_oracle_match": True,
            "prec1_development_activation_denied": True,
            "psym1_host_oracle_match": True,
            "psym1_development_activation_denied": True,
            "psym1_debug_file_on_media": False,
            "pmcu1_host_oracle_match": True,
            "pmcu1_development_activation_denied": True,
            "pfwm1_host_oracle_match": True,
            "pfwm1_development_activation_denied": True,
            "pfwm1_external_payload_bytes_embedded": False,
            "pfwm1_live_firmware_inventory_observed": False,
            "pfwm1_firmware_mutated": False,
            "ppol1_host_oracle_match": True,
            "ppol1_development_activation_denied": True,
            "ppol1_initial_system_cross_bound": True,
            "ppol1_live_policy_enforcement": False,
            "ppol1_pooleglyph_executable_authority": False,
            "live_inner_set_rust_python_match": True,
            "live_inner_set_exact_retained_bytes": True,
            "live_inner_set_policy_payload_bindings": True,
            "live_inner_set_initial_routes_cross_bound": True,
            "live_inner_set_development_denials": True,
            "live_inner_set_authority_grants": 0,
            "live_inner_set_actions_authorized": 0,
            "live_inner_set_state_writes": 0,
            "pbp1_profile_artifact_cross_binding": True,
            "sha256_python_match": True,
            "pkelf1_python_plan_match": True,
            "loaded_fnv1a64_match": True,
            "pbp1_python_decode_match": True,
            "pbp1_serial_debugcon_exact": True,
            "pbp1_kernel_manifest_cross_binding": True,
            "pkmap2_rust_python_probe_match": True,
            "pkmap2_every_leaf_guard_oracle_match": True,
            "pkmap2_higher_half_alias_match": True,
            "pkmap2_framebuffer_translation_cache_preserved": True,
            "pkmap2_original_cr3_restored": True,
            "pkmap2_retained_ranges_cross_bound": True,
            "pbexit1_final_map_attempt_match": True,
            "pbexit1_zero_post_exit_firmware_calls": True,
            "pbexit1_stop_before_transfer": True,
            "media_reconstruction_exact": True,
        },
        "cleanup": {
            "file_handles_closed": 10,
            "file_pools_freed": 9,
            "pbp1_pools_freed": 0,
            "final_map_work_pools_retained": 2,
            "kmap_table_pages_retained": native_kernel_map.TABLE_PAGE_COUNT,
            "stack_pages_retained": native_kernel_map.STACK_PAGE_COUNT,
            "handoff_pages_retained": native_kernel_map.HANDOFF_PAGE_COUNT,
            "artifact_pages_retained": runs[0]["marker_summary"]["artifact_set"]["page_count"],
            "firmware_calls_while_candidate_active": 0,
            "firmware_calls_after_exit": 0,
            "pages_freed": False,
            "page_count": kernel_summary["page_count"],
            "all_resources_released": False,
        },
        "negative_controls": controls,
        "claims": claims,
        "summary": {
            "rust_host_tests_passed": sum(
                host_tests[name]
                for name in (
                    "bootload_tests_passed",
                    "artifact_tests_passed",
                    "inner_tests_passed",
                    "handoff_tests_passed",
                    "live_handoff_tests_passed",
                    "kernel_map_tests_passed",
                    "boot_exit_tests_passed",
                    "pooleboot_tests_passed",
                    "kernel_entry_tests_passed",
                )
            ),
            "rust_host_tests_total": sum(
                host_tests[name]
                for name in (
                    "bootload_tests_total",
                    "artifact_tests_total",
                    "inner_tests_total",
                    "handoff_tests_total",
                    "live_handoff_tests_total",
                    "kernel_map_tests_total",
                    "boot_exit_tests_total",
                    "pooleboot_tests_total",
                    "kernel_entry_tests_total",
                )
            ),
            "clean_pooleboot_builds_exact": 2,
            "clean_kernel_builds_exact": 2,
            "clean_media_generations_exact": 2,
            "guest_runs_passed": 2,
            "guest_runs_total": 2,
            "ordered_marker_count": len(runs[0]["markers"]),
            "serial_debugcon_match_count": 2,
            "gop_frame_match_count": 2,
            "oracle_match_count": 2,
            "exact_pbp1_match_count": 2,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "microcode_patch_count": media_inspection["microcode"]["patch_count"],
            "microcode_payload_profile": "synthetic_test_only_never_apply",
            "firmware_component_count": media_inspection["firmware"]["component_count"],
            "firmware_dependency_count": media_inspection["firmware"]["dependency_count"],
            "firmware_manifest_profile": "synthetic_qualification_never_apply",
            "policy_mode_count": media_inspection["policy"]["mode_count"],
            "policy_capability_rule_count": media_inspection["policy"][
                "capability_rule_count"
            ],
            "policy_profile": "synthetic_qualification_only",
            "inner_retained_set_sha256": media_inspection["inner_set"][
                "retained_set_sha256"
            ],
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace the candidate PSM1 format before stable boot ABI promotion.",
            "Define and implement signed manifest authentication, trust anchors, algorithm agility, and revocation policy.",
            "Persist and atomically enforce the minimum secure version across update and rollback.",
            "Define the final transfer-time CR3 activation, stack switch, register ABI, and explicit revocation plan.",
            "Authenticate the loaded initial-system, recovery, policy, symbols, microcode, and firmware artifacts through a ratified trust policy.",
            "Authenticate all six live inner contracts and bind authenticated trust, revocation, rollback, and audit state before any action gate can progress beyond the outer-signature denial.",
            "Revalidate the exact retained inner-set bytes in PooleKernel before capability issuance to close the loader-to-kernel TOCTOU boundary.",
            "Implement PooleKernel activation, capability issuance, transactional startup, rollback, and lifecycle enforcement for qualified PINIT1 declarations.",
            "Implement authenticated PREC1 state persistence, PooleBoot enforcement, handoff binding, and PooleKernel-mediated recovery without ambient authority.",
            "Implement signed PSYM1 parsing and bounded capability-authorized diagnostic consumption in PooleBoot and PooleKernel without staging private debug data.",
            "Authenticate PMCU1, validate real vendor containers and licenses, observe privileged per-processor revisions, and implement early PooleKernel apply and post-verify enforcement before any production payload is included or applied.",
            "Implement live bounded FMP, ESRT, capsule, and exact device-plugin inventory adapters, vendor package validation, recovery evidence, and separately authorized update execution before PFWM1 can move beyond synthetic dry-run qualification.",
            "Implement signed PPOL1 verification and live PooleBoot/PooleKernel intersection enforcement, mode transitions, capability issuance, revocation, rollback, and durable audit before policy decisions can be applied.",
            "Transfer to PooleKernel and capture entry, panic, recovery, and reset evidence.",
            "Add fault-injected live EFI_INVALID_PARAMETER retry evidence rather than lifecycle-model evidence alone.",
            "Define how PooleKernel reclaims final-map scratch pools after consuming PBP1.",
            "Qualify hostile firmware behavior, target firmware, physical hardware, and a second clean builder.",
            "Complete Secure Boot, measured boot, TPM policy, signing, ISO, installer, and recovery gates.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }
    errors = native_kernel_load.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report, screenshots[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--screenshot-out", type=Path)
    parser.add_argument("--status-date", default="2026-07-18")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    if args.timeout < 5 or args.timeout > 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report, screenshot = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        output = args.out.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
        if args.screenshot_out is not None:
            screenshot_output = args.screenshot_out.resolve()
            screenshot_output.parent.mkdir(parents=True, exist_ok=True)
            screenshot_output.write_bytes(screenshot)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"PKLOAD6 FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "PKLOAD6 PASS "
        f"tests={summary['rust_host_tests_passed']}/{summary['rust_host_tests_total']} "
        f"runs={summary['guest_runs_passed']}/{summary['guest_runs_total']} "
        f"markers={summary['ordered_marker_count']} "
        f"controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} "
        "transfer=false n5_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
