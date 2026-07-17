#!/usr/bin/env python3
"""Qualify live PKLOAD3 manifest selection, pre-exit PBP1, and cleanup."""

from __future__ import annotations

import argparse
import copy
import json
import re
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_boot_handoff,
    native_kernel_load,
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
    """Raised when the PKLOAD3 qualification fails closed."""


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
    handoff_tests: dict[str, int] = {}
    for package, minimum in (("poole-handoff", 8), ("poole-live-handoff", 6)):
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
        handoff_tests[package] = int(package_match.group(1))
    fmt_packages = ("poole-bootload", "poole-handoff", "poole-live-handoff", "pooleboot")
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
        ("poole-bootload", "--lib", "x86_64-pc-windows-msvc", "clippy-bootload-host"),
        ("poole-bootload", "--lib", "x86_64-unknown-uefi", "clippy-bootload-uefi"),
        ("poole-handoff", "--lib", "x86_64-pc-windows-msvc", "clippy-handoff-host"),
        ("poole-handoff", "--lib", "x86_64-unknown-uefi", "clippy-handoff-uefi"),
        ("poole-live-handoff", "--lib", "x86_64-pc-windows-msvc", "clippy-live-handoff-host"),
        ("poole-live-handoff", "--lib", "x86_64-unknown-uefi", "clippy-live-handoff-uefi"),
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
    return {
        "bootload_tests_passed": bootload_tests,
        "bootload_tests_total": bootload_tests,
        "handoff_tests_passed": handoff_tests["poole-handoff"],
        "handoff_tests_total": handoff_tests["poole-handoff"],
        "live_handoff_tests_passed": handoff_tests["poole-live-handoff"],
        "live_handoff_tests_total": handoff_tests["poole-live-handoff"],
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


def _mutated_pbp1(data: bytes, *, transfer_state: bool = False, artifact_digest: bool = False) -> bytes:
    handoff = native_boot_handoff.decode(data)
    changed = bytearray(data)
    if transfer_state:
        core = handoff.record(native_boot_handoff.RECORD_CORE)
        if core is None:
            raise QualificationError("live PBP1 core record is absent")
        struct.pack_into("<Q", changed, core.offset + 56, 0x0040_0000)
        _repair_pbp1_record(changed, 0)
    if artifact_digest:
        artifact = handoff.record(native_boot_handoff.RECORD_LOADED_ARTIFACTS)
        if artifact is None:
            raise QualificationError("live PBP1 artifact record is absent")
        record_index = [item.record_type for item in handoff.records].index(
            native_boot_handoff.RECORD_LOADED_ARTIFACTS
        )
        changed[artifact.offset + 48] ^= 1
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
    if cluster_bytes != 512:
        raise QualificationError("negative controls assume the frozen one-sector cluster profile")

    expected_config_hash = inspection["files"][1]["sha256"]
    expected_manifest_hash = inspection["files"][2]["sha256"]
    expected_kernel_hash = inspection["files"][3]["sha256"]

    def inspect_expected(candidate: bytes) -> dict[str, Any]:
        observed = native_kernel_load.inspect_media_bytes(candidate)
        if (
            observed["files"][1]["sha256"] != expected_config_hash
            or observed["files"][2]["sha256"] != expected_manifest_hash
            or observed["files"][3]["sha256"] != expected_kernel_hash
        ):
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

    marker_summary = native_kernel_load.validate_markers(markers)
    config_oracle = copy.deepcopy(inspection)
    config_oracle["config"]["timeout_ms"] += 1
    manifest_oracle = copy.deepcopy(inspection)
    manifest_oracle["manifest"]["manifest_version"] += 1
    elf_oracle = copy.deepcopy(inspection)
    elf_oracle["kernel"]["plan"]["image_size"] += native_pooleboot.SECTOR_BYTES
    hash_oracle = copy.deepcopy(inspection)
    hash_oracle["kernel"]["loaded_fnv1a64"] = "0" * 16
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
    marker_byte_divergence = copy.deepcopy(marker_summary)
    marker_byte_divergence["pbp1"]["byte_count"] += 8
    marker_memory_divergence = copy.deepcopy(marker_summary)
    marker_memory_divergence["pbp1"]["memory_entry_count"] += 1

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
        ("NEG-N5-KLOAD-MARKER-OMISSION", _rejected(lambda: native_kernel_load.validate_markers(markers[:-1]))),
        ("NEG-N5-KLOAD-MARKER-ORDER", _rejected(lambda: native_kernel_load.validate_markers([markers[1], markers[0], *markers[2:]]))),
        ("NEG-N5-KLOAD-MARKER-CONFIG-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 7, f"bytes={marker_summary['boot_config']['byte_count']}", "bytes=16385")))),
        ("NEG-N5-KLOAD-MARKER-MANIFEST-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 8, f"bytes={marker_summary['manifest']['byte_count']}", "bytes=65537")))),
        ("NEG-N5-KLOAD-MARKER-MANIFEST-SLOT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 8, f"slot={marker_summary['manifest']['slot']}", "slot=4" if marker_summary['manifest']['slot'] != 4 else "slot=3")))),
        ("NEG-N5-KLOAD-MARKER-DIGEST", _rejected(lambda: native_kernel_load.validate_oracle_binding(native_kernel_load.validate_markers(_replace_marker(markers, 9, f"sha256_prefix={marker_summary['manifest']['kernel_sha256_prefix']}", "sha256_prefix=0000000000000000")), inspection, pbp1_transcript))),
        ("NEG-N5-KLOAD-MARKER-KERNEL-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 10, f"bytes={marker_summary['kernel']['file_byte_count']}", "bytes=1048577")))),
        ("NEG-N5-KLOAD-MARKER-PAGE-MATH", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 11, f"pages={marker_summary['kernel']['page_count']}", f"pages={marker_summary['kernel']['page_count'] + 1}")))),
        ("NEG-N5-KLOAD-MARKER-ENTRY-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 11, f"entry_offset={marker_summary['kernel']['entry_offset']}", f"entry_offset={marker_summary['kernel']['image_byte_count']}")))),
        ("NEG-N5-KLOAD-MARKER-MAPPING-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 12, "mappings=4", "mappings=3")))),
        ("NEG-N5-KLOAD-MARKER-WX", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 12, "wx=0", "wx=1")))),
        ("NEG-N5-KLOAD-MARKER-RELEASE-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 15, "files_closed=4", "files_closed=3")))),
        ("NEG-N5-KLOAD-MARKER-BOUNDARY", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 18, "selection=manifest_digest_untrusted", "selection=trusted")))),
        ("NEG-N5-KLOAD-CONFIG-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, config_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-MANIFEST-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, manifest_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-ELF-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, elf_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-LOADED-HASH-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, hash_oracle, pbp1_transcript))),
        ("NEG-N5-KLOAD-CLAIM-OVERREACH", _rejected(lambda: native_kernel_load.validate_claims(overreach))),
        ("NEG-N5-KLOAD-STALE-BINDING", _rejected(lambda: _require(native_kernel_load.binding_matches(stale_binding, ROOT, native_kernel_load.CONTRACT_RELATIVE), "stale binding accepted"))),
        ("NEG-N5-PBP1-TRANSCRIPT-MISSING", _rejected(lambda: native_live_boot_handoff.extract_transcript(b""))),
        ("NEG-N5-PBP1-TRANSCRIPT-DUPLICATE-BEGIN", _rejected(lambda: native_live_boot_handoff.extract_transcript(duplicate_begin))),
        ("NEG-N5-PBP1-TRANSCRIPT-OFFSET-GAP", _rejected(lambda: native_live_boot_handoff.extract_transcript(offset_gap))),
        ("NEG-N5-PBP1-TRANSCRIPT-NONHEX", _rejected(lambda: native_live_boot_handoff.extract_transcript(nonhex))),
        ("NEG-N5-PBP1-TRANSCRIPT-BYTE-COUNT", _rejected(lambda: native_live_boot_handoff.extract_transcript(byte_count))),
        ("NEG-N5-PBP1-TRANSCRIPT-MESSAGE-CRC", _rejected(lambda: native_live_boot_handoff.extract_transcript(wrong_crc))),
        ("NEG-N5-PBP1-TRANSCRIPT-FNV", _rejected(lambda: native_live_boot_handoff.extract_transcript(wrong_fnv))),
        ("NEG-N5-PBP1-PREEXIT-TRANSFER-STATE", _rejected(lambda: native_live_boot_handoff.extract_transcript(transfer_state))),
        ("NEG-N5-PBP1-ARTIFACT-DIGEST-ORACLE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, inspection, artifact_digest_summary))),
        ("NEG-N5-PBP1-MARKER-BYTE-DIVERGENCE", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(pbp1_transcript, marker_byte_divergence, inspection))),
        ("NEG-N5-PBP1-MARKER-MEMORY-DIVERGENCE", _rejected(lambda: native_live_boot_handoff.validate_oracle_binding(pbp1_transcript, marker_memory_divergence, inspection))),
        ("NEG-N5-PBP1-RELEASE-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 14, "pools_freed=3", "pools_freed=2")))),
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
        raise QualificationError("PKLOAD3 negative-control order changed")
    if any(item["status"] != "pass" for item in controls):
        failed = [item["id"] for item in controls if item["status"] != "pass"]
        raise QualificationError("PKLOAD3 negative controls failed: " + ", ".join(failed))
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
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "native-tier0").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pkload2-qualification-", dir=ROOT / "tmp") as temporary:
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
            raise QualificationError("two PKLOAD3 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_first)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKLOAD3 media kernel differs from the fresh PKENTRY1 product")
        media_path = temporary_root / "pkload2.img"
        media_path.write_bytes(media_first)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        pbp1_payloads: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkload2-run-{run_index}-",
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
        raise QualificationError("two PKLOAD3 marker sequences differ")
    if screenshots[0] != screenshots[1]:
        raise QualificationError("two PKLOAD3 screenshots differ")
    if pbp1_payloads[0] != pbp1_payloads[1]:
        raise QualificationError("two PKLOAD3 PBP1 byte streams differ")

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
        "status": "pass_single_host_two_run_live_manifest_pre_exit_pbp1_then_release_non_promoting",
        "contract_id": native_kernel_load.CONTRACT_ID,
        "selected_move_id": "N5-PBP1-LIVE-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {
            "N5": "partial",
            "N5.1": "partial",
            "N5.4": "partial",
            "N5.5": "partial",
            "N5.8": "partial",
        },
        "bindings": {
            "contract": native_kernel_load.file_binding(ROOT, native_kernel_load.CONTRACT_RELATIVE),
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
            "sha256_python_match": True,
            "pkelf1_python_plan_match": True,
            "loaded_fnv1a64_match": True,
            "pbp1_python_decode_match": True,
            "pbp1_serial_debugcon_exact": True,
            "pbp1_kernel_manifest_cross_binding": True,
            "media_reconstruction_exact": True,
        },
        "cleanup": {
            "file_handles_closed": 4,
            "file_pools_freed": 3,
            "pbp1_pools_freed": 3,
            "pages_freed": True,
            "page_count": kernel_summary["page_count"],
            "all_resources_released": True,
        },
        "negative_controls": controls,
        "claims": claims,
        "summary": {
            "rust_host_tests_passed": sum(
                host_tests[name]
                for name in (
                    "bootload_tests_passed",
                    "handoff_tests_passed",
                    "live_handoff_tests_passed",
                    "pooleboot_tests_passed",
                    "kernel_entry_tests_passed",
                )
            ),
            "rust_host_tests_total": sum(
                host_tests[name]
                for name in (
                    "bootload_tests_total",
                    "handoff_tests_total",
                    "live_handoff_tests_total",
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
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace the candidate PSM1 format before stable boot ABI promotion.",
            "Define and implement signed manifest authentication, trust anchors, algorithm agility, and revocation policy.",
            "Persist and atomically enforce the minimum secure version across update and rollback.",
            "Retain allocated kernel pages and install the exact r, rx, r, and rw page-table permissions.",
            "Load and authenticate the initial-system, recovery, policy, symbols, and optional microcode artifacts.",
            "Retain and map the finalized PBP1 container read-only only after kernel mappings and transfer state exist.",
            "Recapture the final memory map and prove the exact ExitBootServices retry/no-later-boot-service sequence.",
            "Transfer to PooleKernel and capture entry, panic, recovery, and reset evidence.",
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
    parser.add_argument("--status-date", default="2026-07-17")
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
        print(f"PKLOAD3 FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "PKLOAD3 PASS "
        f"tests={summary['rust_host_tests_passed']}/{summary['rust_host_tests_total']} "
        f"runs={summary['guest_runs_passed']}/{summary['guest_runs_total']} "
        f"markers={summary['ordered_marker_count']} "
        f"controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} "
        "transfer=false n5_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
