"""Deterministic PooleBoot proof media, inspection, and marker contracts."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
import re
import struct
import uuid
from pathlib import Path
from typing import Any

from runtime.native_binary import validate_binary


SECTOR_BYTES = 512
IMAGE_BYTES = 64 * 1024 * 1024
IMAGE_SECTORS = IMAGE_BYTES // SECTOR_BYTES
GPT_HEADER_BYTES = 92
GPT_ENTRY_COUNT = 128
GPT_ENTRY_BYTES = 128
GPT_ENTRY_SECTORS = GPT_ENTRY_COUNT * GPT_ENTRY_BYTES // SECTOR_BYTES
PRIMARY_HEADER_LBA = 1
PRIMARY_ENTRIES_LBA = 2
BACKUP_HEADER_LBA = IMAGE_SECTORS - 1
BACKUP_ENTRIES_LBA = BACKUP_HEADER_LBA - GPT_ENTRY_SECTORS
FIRST_USABLE_LBA = 34
LAST_USABLE_LBA = BACKUP_ENTRIES_LBA - 1
ESP_START_LBA = 2048
ESP_END_LBA = LAST_USABLE_LBA
ESP_SECTORS = ESP_END_LBA - ESP_START_LBA + 1
FAT_RESERVED_SECTORS = 32
FAT_COUNT = 2
FAT_SECTORS_PER_CLUSTER = 1
FAT_ROOT_CLUSTER = 2
FAT_MEDIA = 0xF8
FAT_END = 0x0FFFFFFF
FAT32_MIN_CLUSTERS = 65_525
FAT32_MAX_CLUSTERS = 0x0FFFFFF5
MAX_EFI_BYTES = 256 * 1024
SAFE_MEDIA_OUTPUT_ROOTS = ("tmp", "runs/native-tier0")
WINDOWS_DEVICE_PREFIXES = ("\\\\.\\", "\\\\?\\", "\\??\\", "\\device\\", "\\\\globalroot\\")
WINDOWS_RESERVED_PATH_COMPONENT = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$",
    flags=re.IGNORECASE,
)
DISK_GUID = uuid.UUID("504f4f4c-454f-534e-8000-000000000097")
ESP_UNIQUE_GUID = uuid.UUID("504f4f4c-4553-5000-8000-000000000001")
ESP_TYPE_GUID = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
VOLUME_LABEL = b"POOLEOS ESP"
VOLUME_ID = 0x97970001
FALLBACK_PATH = "EFI/BOOT/BOOTX64.EFI"
FIXED_FAT_DATE = 0x0021

TRUE_PROOF_CLAIMS = (
    "one_host_pe32_reproducible",
    "deterministic_gpt_esp_observed",
    "pooleboot_guest_entry_observed",
    "gop_frame_observed",
    "bounded_final_memory_map_observed",
    "poolekernel_loaded",
    "system_manifest_parsed",
    "manifest_selected_kernel_path",
    "manifest_kernel_sha256_matched",
    "live_pbart1_files_read",
    "pbart1_role_version_payload_digest_validated",
    "initial_system_inner_oracle_validated",
    "initial_system_development_activation_denied",
    "recovery_inner_oracle_validated",
    "recovery_development_activation_denied",
    "symbols_inner_oracle_validated",
    "symbols_development_activation_denied",
    "artifact_set_manifest_sha256_matched",
    "artifact_pages_retained",
    "pbp1_profile_artifacts_cross_bound",
    "live_pbp1_post_exit_development_observed",
    "pbp1_serial_debugcon_exact",
    "pbp1_kernel_manifest_cross_bound",
    "pkmap2_exact_4k_leaves_observed",
    "pkmap2_guarded_stack_retained",
    "pkmap2_read_only_handoff_retained",
    "temporary_candidate_cr3_activated",
    "higher_half_kernel_alias_verified",
    "wp_nx_wx_enforced",
    "framebuffer_translation_cache_preserved",
    "original_cr3_restored_before_exit",
    "kernel_pages_retained",
    "page_tables_retained",
    "zero_firmware_calls_while_candidate_active",
    "exit_boot_services_called",
    "no_firmware_calls_after_exit",
    "stop_before_transfer_observed",
    "two_qemu_runs_exact",
)
FALSE_PROOF_CLAIMS = (
    "complete_pooleboot_loader",
    "manifest_signature_verified",
    "manifest_trusted",
    "persistent_rollback_state_enforced",
    "kernel_signature_verified",
    "artifact_signatures_verified",
    "artifact_semantics_applied",
    "pooleboot_initial_system_semantics_enforced",
    "poolekernel_initial_system_activation_enforced",
    "initial_system_executed",
    "pooleboot_recovery_semantics_enforced",
    "poolekernel_recovery_activation_enforced",
    "recovery_executed",
    "pooleboot_symbols_semantics_enforced",
    "poolekernel_symbols_activation_enforced",
    "symbols_consumed",
    "microcode_applied",
    "poolekernel_executed",
    "all_kload_resources_released",
    "final_kernel_address_space_established",
    "final_framebuffer_cache_policy_qualified",
    "kernel_entry_called",
    "transferable_pbp1_handoff_produced",
    "secure_boot_enforced",
    "measured_boot_performed",
    "owner_signature_present",
    "physical_hardware_tested",
    "target_firmware_tested",
    "physical_media_tested",
    "n5_exit_gate_satisfied",
    "production_boot_evidence",
    "production_ready",
)
NEGATIVE_CONTROL_IDS = (
    "NEG-N5-KLOAD-CONFIG-MISSING",
    "NEG-N5-KLOAD-CONFIG-EMPTY",
    "NEG-N5-KLOAD-CONFIG-OVERSIZE",
    "NEG-N5-KLOAD-CONFIG-MALFORMED",
    "NEG-N5-KLOAD-MANIFEST-MISSING",
    "NEG-N5-KLOAD-MANIFEST-EMPTY",
    "NEG-N5-KLOAD-MANIFEST-OVERSIZE",
    "NEG-N5-KLOAD-MANIFEST-MALFORMED",
    "NEG-N5-KLOAD-KERNEL-MISSING",
    "NEG-N5-KLOAD-KERNEL-EMPTY",
    "NEG-N5-KLOAD-KERNEL-OVERSIZE",
    "NEG-N5-KLOAD-KERNEL-MALFORMED",
    "NEG-N5-KLOAD-FAT-COPY",
    "NEG-N5-KLOAD-FAT-CHAIN-LOOP",
    "NEG-N5-KLOAD-DIRECTORY-PATH",
    "NEG-N5-KLOAD-CONFIG-PATH",
    "NEG-N5-KLOAD-MANIFEST-PATH",
    "NEG-N5-KLOAD-KERNEL-PATH",
    "NEG-N5-KLOAD-CONFIG-CONTENT",
    "NEG-N5-KLOAD-MANIFEST-CONTENT",
    "NEG-N5-KLOAD-KERNEL-CONTENT",
    "NEG-N5-KLOAD-ARTIFACT-MISSING",
    "NEG-N5-KLOAD-ARTIFACT-EMPTY",
    "NEG-N5-KLOAD-ARTIFACT-OVERSIZE",
    "NEG-N5-KLOAD-ARTIFACT-PATH",
    "NEG-N5-KLOAD-ARTIFACT-CONTENT",
    "NEG-N5-KLOAD-ARTIFACT-ROLE",
    "NEG-N5-KLOAD-ARTIFACT-VERSION",
    "NEG-N5-KLOAD-ARTIFACT-PAYLOAD-DIGEST",
    "NEG-N5-KLOAD-ARTIFACT-MANIFEST-DIGEST",
    "NEG-N5-KLOAD-INITIAL-SYSTEM-INNER-SEMANTICS",
    "NEG-N5-KLOAD-INITIAL-SYSTEM-INNER-VERSION",
    "NEG-N5-KLOAD-INITIAL-SYSTEM-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-RECOVERY-INNER-SEMANTICS",
    "NEG-N5-KLOAD-RECOVERY-INNER-VERSION",
    "NEG-N5-KLOAD-RECOVERY-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-SYMBOLS-INNER-SEMANTICS",
    "NEG-N5-KLOAD-SYMBOLS-INNER-VERSION",
    "NEG-N5-KLOAD-SYMBOLS-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-MARKER-OMISSION",
    "NEG-N5-KLOAD-MARKER-ORDER",
    "NEG-N5-KLOAD-MARKER-CONFIG-BOUND",
    "NEG-N5-KLOAD-MARKER-MANIFEST-BOUND",
    "NEG-N5-KLOAD-MARKER-MANIFEST-SLOT",
    "NEG-N5-KLOAD-MARKER-DIGEST",
    "NEG-N5-KLOAD-MARKER-KERNEL-BOUND",
    "NEG-N5-KLOAD-MARKER-PAGE-MATH",
    "NEG-N5-KLOAD-MARKER-ENTRY-BOUND",
    "NEG-N5-KLOAD-MARKER-ARTIFACT-COUNT",
    "NEG-N5-KLOAD-MARKER-ARTIFACT-SIGNATURE",
    "NEG-N5-KLOAD-MARKER-MAPPING-COUNT",
    "NEG-N5-KLOAD-MARKER-WX",
    "NEG-N5-KLOAD-MARKER-RETAIN-COUNT",
    "NEG-N5-KLOAD-MARKER-BOUNDARY",
    "NEG-N5-KLOAD-CONFIG-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-MANIFEST-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-ELF-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-LOADED-HASH-DIVERGENCE",
    "NEG-N5-KLOAD-ARTIFACT-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-CLAIM-OVERREACH",
    "NEG-N5-KLOAD-STALE-BINDING",
    "NEG-N5-PBP1-TRANSCRIPT-MISSING",
    "NEG-N5-PBP1-TRANSCRIPT-DUPLICATE-BEGIN",
    "NEG-N5-PBP1-TRANSCRIPT-OFFSET-GAP",
    "NEG-N5-PBP1-TRANSCRIPT-NONHEX",
    "NEG-N5-PBP1-TRANSCRIPT-BYTE-COUNT",
    "NEG-N5-PBP1-TRANSCRIPT-MESSAGE-CRC",
    "NEG-N5-PBP1-TRANSCRIPT-FNV",
    "NEG-N5-PBP1-EXIT-STATE",
    "NEG-N5-PBP1-ARTIFACT-DIGEST-ORACLE",
    "NEG-N5-PBP1-ARTIFACT-ROLE",
    "NEG-N5-PBP1-ARTIFACT-OMISSION",
    "NEG-N5-PBP1-ARTIFACT-OVERLAP",
    "NEG-N5-PBP1-ARTIFACT-SIGNATURE",
    "NEG-N5-PBP1-ARTIFACT-RANGE-COVERAGE",
    "NEG-N5-PBP1-MARKER-BYTE-DIVERGENCE",
    "NEG-N5-PBP1-MARKER-MEMORY-DIVERGENCE",
    "NEG-N5-PBP1-RETAINED-RANGE-OMISSION",
    "NEG-N5-KMAP-CPU-WP",
    "NEG-N5-KMAP-CPU-NX-SUPPORT",
    "NEG-N5-KMAP-CPU-NX-ENABLE",
    "NEG-N5-KMAP-CPU-LA57",
    "NEG-N5-KMAP-CPU-PCID",
    "NEG-N5-KMAP-ROOT-OCCUPIED",
    "NEG-N5-KMAP-ALIGNMENT",
    "NEG-N5-KMAP-COVERAGE-GAP",
    "NEG-N5-KMAP-COVERAGE-OVERLAP",
    "NEG-N5-KMAP-PHYSICAL-RANGE",
    "NEG-N5-KMAP-TABLE-OVERLAP",
    "NEG-N5-KMAP-WX",
    "NEG-N5-KMAP-LEAF-PHYSICAL",
    "NEG-N5-KMAP-LEAF-FLAGS",
    "NEG-N5-KMAP-LARGE-PAGE",
    "NEG-N5-KMAP-FRAMEBUFFER-TRANSLATION",
    "NEG-N5-KMAP-FRAMEBUFFER-CACHE",
    "NEG-N5-KMAP-ACTIVATION",
    "NEG-N5-KMAP-ROLLBACK",
    "NEG-N5-KMAP-FIRMWARE-ACTIVE",
    "NEG-N5-KMAP-RETENTION",
    "NEG-N5-KMAP-MARKER-PLAN",
    "NEG-N5-KMAP-MARKER-ACTIVE",
    "NEG-N5-KMAP-MARKER-RETAIN",
    "NEG-N5-KMAP-ORACLE-DIVERGENCE",
    "NEG-N5-PBP1-RETAINED-RANGE-KIND",
    "NEG-N5-PBP1-ROOT-BINDING",
    "NEG-N5-PBP1-STACK-BINDING",
    "NEG-N5-PBP1-HANDOFF-BINDING",
    "NEG-N5-KMAP-RETAINED-OVERLAP",
    "NEG-N5-KMAP-STACK-SHAPE",
    "NEG-N5-KMAP-GUARD-LAYOUT",
    "NEG-N5-PBEXIT-MAP-SHAPE",
    "NEG-N5-PBEXIT-DESCRIPTOR-VERSION",
    "NEG-N5-PBEXIT-ORDER",
    "NEG-N5-PBEXIT-NONRETRYABLE",
    "NEG-N5-PBEXIT-RETRY-EXHAUSTED",
    "NEG-N5-PBEXIT-POST-ATTEMPT-FIRMWARE",
    "NEG-N5-PBEXIT-POST-EXIT-FIRMWARE",
    "NEG-N5-PBEXIT-MARKER-ATTEMPTS",
    "NEG-N5-PBEXIT-MARKER-DESCRIPTOR",
    "NEG-N5-PBEXIT-FIRMWARE-BOUNDARY",
    "NEG-N5-PBEXIT-TRANSFER",
)
CONTRACT_RELATIVE = "specs/native-pooleboot-proof.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-pooleboot-proof.schema.json"
READINESS_RELATIVE = "runs/native_pooleboot_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-pooleboot-readiness.schema.json"
PROOF_IMPLEMENTATION_INPUTS = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/rust-toolchain.toml",
    "native/.cargo/config.toml",
    "native/artifact/Cargo.toml",
    "native/artifact/src/lib.rs",
    "native/artifact/src/bin/pbart1_probe.rs",
    "native/boot/Cargo.toml",
    "native/boot/src/lib.rs",
    "native/boot/src/main.rs",
    "native/boot/src/kload.rs",
    "native/boot/src/livehandoff.rs",
    "native/boot/src/kmap.rs",
    "native/boot/src/exit.rs",
    "native/bootcfg/Cargo.toml",
    "native/bootcfg/src/lib.rs",
    "native/bootload/Cargo.toml",
    "native/bootload/src/lib.rs",
    "native/elf/Cargo.toml",
    "native/elf/src/lib.rs",
    "native/handoff/Cargo.toml",
    "native/handoff/src/lib.rs",
    "native/manifest/Cargo.toml",
    "native/manifest/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kmap/Cargo.toml",
    "native/kmap/src/bin/pkmap1_probe.rs",
    "native/kmap/src/bin/pkmap2_probe.rs",
    "native/kmap/src/lib.rs",
    "native/livehandoff/Cargo.toml",
    "native/livehandoff/src/lib.rs",
    "native/bootexit/Cargo.toml",
    "native/bootexit/README.md",
    "native/bootexit/src/lib.rs",
    "runtime/native_binary.py",
    "runtime/native_boot_artifact.py",
    "runtime/native_boot_exit.py",
    "runtime/native_boot_config.py",
    "runtime/native_elf_loader.py",
    "runtime/native_kernel_image.py",
    "runtime/native_kernel_load.py",
    "runtime/native_initial_system.py",
    "native/recovery/Cargo.toml",
    "native/recovery/src/lib.rs",
    "native/recovery/src/bin/prec1_probe.rs",
    "runtime/native_recovery.py",
    "native/symbols/Cargo.toml",
    "native/symbols/src/lib.rs",
    "native/symbols/src/bin/psym1_probe.rs",
    "runtime/native_symbols.py",
    "runtime/native_kernel_map.py",
    "runtime/native_live_boot_handoff.py",
    "runtime/native_pooleboot.py",
    "runtime/native_system_manifest.py",
    "runtime/native_tier0.py",
    "docs/native-initial-system-profile.md",
    "docs/native-initial-system-bundle.md",
    "docs/native-recovery-bundle.md",
    "specs/native-recovery-contract.json",
    "specs/native-recovery-contract.schema.json",
    "specs/native-recovery-golden-vectors.json",
    "specs/native-recovery-golden-vectors.schema.json",
    "specs/native-recovery-readiness.schema.json",
    "specs/fixtures/prec1-canonical.bin",
    "specs/fixtures/prec1-canonical-state.bin",
    "runs/native_recovery_readiness.json",
    "docs/native-symbol-bundle.md",
    "specs/native-symbol-contract.json",
    "specs/native-symbol-contract.schema.json",
    "specs/native-symbol-golden-vectors.json",
    "specs/native-symbol-golden-vectors.schema.json",
    "specs/native-symbol-readiness.schema.json",
    "specs/fixtures/psym1-canonical.bin",
    "specs/fixtures/psym1-minimal.bin",
    "specs/fixtures/psym1-boundary.bin",
    "runs/native_symbol_readiness.json",
    "specs/native-pooleboot-proof.json",
    "specs/native-pooleboot-proof.schema.json",
    "specs/native-pooleboot-readiness.schema.json",
    "specs/native-kernel-load-contract.json",
    "specs/native-kernel-load-contract.schema.json",
    "specs/native-kernel-load-readiness.schema.json",
    "specs/native-kernel-map-contract.json",
    "specs/native-kernel-map-contract.schema.json",
    "specs/native-boot-exit-contract.json",
    "specs/native-boot-exit-contract.schema.json",
    "specs/native-boot-digest-provider.json",
    "specs/native-boot-digest-provider.schema.json",
    "specs/native-system-manifest-contract.json",
    "specs/native-system-manifest-contract.schema.json",
    "specs/native-system-manifest-readiness.schema.json",
    "specs/native-tier0-lock.json",
    "specs/native-tier0-profile.json",
    "runs/native_tier0_readiness.json",
    "runs/native_system_manifest_readiness.json",
    "tools/build_native_pooleboot_media.py",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_entry.py",
    "tools/qualify_native_kernel_load.py",
    "tools/generate_native_recovery_vectors.py",
    "tools/qualify_native_recovery.py",
    "tools/generate_native_symbol_vectors.py",
    "tools/qualify_native_symbols.py",
    "tools/qualify_native_system_manifest.py",
    "tests/test_native_recovery.py",
    "tests/test_native_symbols.py",
)
ABSOLUTE_USER_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+|/(?:Users|home)/[^/\s]+)",
    flags=re.IGNORECASE,
)

MARKER_PREFIX = "POOLEBOOT/0.1 "


class PooleBootError(RuntimeError):
    """Raised when a PooleBoot proof input fails its bounded contract."""


def _reject_unsafe_raw_path(candidate: Path) -> None:
    raw = str(candidate)
    if not raw or "\0" in raw:
        raise PooleBootError("PooleBoot path is empty or contains a NUL byte")
    normalized = raw.replace("/", "\\").casefold()
    if normalized.startswith(WINDOWS_DEVICE_PREFIXES):
        raise PooleBootError("Windows device and object-manager namespaces are forbidden")


def _workspace_candidate(root: Path, candidate: Path) -> tuple[Path, tuple[str, ...]]:
    candidate = Path(candidate)
    _reject_unsafe_raw_path(candidate)
    root_absolute = Path(os.path.abspath(root))
    if not root_absolute.is_dir():
        raise PooleBootError("PooleBoot workspace root is not an existing directory")
    lexical = Path(
        os.path.abspath(candidate if candidate.is_absolute() else root_absolute / candidate)
    )
    try:
        relative = lexical.relative_to(root_absolute)
    except ValueError as error:
        raise PooleBootError("PooleBoot path escapes the workspace root") from error
    relative_parts = relative.parts
    if not relative_parts:
        raise PooleBootError("PooleBoot path must name a workspace file")
    for part in relative_parts:
        if ":" in part:
            raise PooleBootError("alternate data streams are forbidden")
        if part != part.rstrip(" ."):
            raise PooleBootError("path components ending in a space or dot are forbidden")
        if WINDOWS_RESERVED_PATH_COMPONENT.fullmatch(part):
            raise PooleBootError("reserved Windows device names are forbidden")

    current = root_absolute
    for index, part in enumerate(relative_parts):
        current /= part
        if current.is_symlink():
            raise PooleBootError("symlink paths are forbidden for PooleBoot media")
        if current.exists() and index < len(relative_parts) - 1 and not current.is_dir():
            raise PooleBootError("PooleBoot path has a non-directory parent")

    resolved_root = root_absolute.resolve(strict=True)
    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise PooleBootError("PooleBoot path resolves outside the workspace root") from error
    return resolved, tuple(part.replace("\\", "/") for part in relative_parts)


def validate_workspace_input_file(
    root: Path,
    candidate: Path,
    suffix: str,
    maximum_byte_count: int,
) -> Path:
    if not suffix.startswith(".") or maximum_byte_count <= 0:
        raise PooleBootError("invalid PooleBoot input-file policy")
    resolved, _ = _workspace_candidate(root, candidate)
    if resolved.suffix.casefold() != suffix.casefold():
        raise PooleBootError(f"PooleBoot input must use the {suffix} suffix")
    if not resolved.exists() or not resolved.is_file():
        raise PooleBootError("PooleBoot input must be an existing regular workspace file")
    byte_count = resolved.stat().st_size
    if byte_count <= 0 or byte_count > maximum_byte_count:
        raise PooleBootError("PooleBoot input file is empty or exceeds its byte bound")
    return resolved


def validate_workspace_output_path(root: Path, candidate: Path, suffix: str) -> Path:
    if suffix not in (".img", ".json"):
        raise PooleBootError("unsupported PooleBoot output suffix policy")
    resolved, _ = _workspace_candidate(root, candidate)
    if resolved.suffix.casefold() != suffix:
        raise PooleBootError(f"PooleBoot output must use the {suffix} suffix")
    resolved_root = Path(os.path.abspath(root)).resolve(strict=True)
    allowed = False
    for relative_root in SAFE_MEDIA_OUTPUT_ROOTS:
        safe_root = (resolved_root / relative_root).resolve(strict=False)
        try:
            resolved.relative_to(safe_root)
        except ValueError:
            continue
        allowed = True
        break
    if not allowed:
        raise PooleBootError(
            "PooleBoot output must remain under tmp or runs/native-tier0"
        )
    if resolved.exists() and not resolved.is_file():
        raise PooleBootError("PooleBoot output may replace only a regular file")
    return resolved


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _crc32(data: bytes | bytearray) -> int:
    return binascii.crc32(data) & 0xFFFFFFFF


def _lba_offset(lba: int) -> int:
    if lba < 0 or lba >= IMAGE_SECTORS:
        raise PooleBootError(f"LBA outside proof image: {lba}")
    return lba * SECTOR_BYTES


def _fat_sector_count() -> tuple[int, int]:
    entries_per_sector = SECTOR_BYTES // 4
    for fat_sectors in range(1, ESP_SECTORS):
        data_sectors = ESP_SECTORS - FAT_RESERVED_SECTORS - FAT_COUNT * fat_sectors
        if data_sectors <= 0:
            break
        cluster_count = data_sectors // FAT_SECTORS_PER_CLUSTER
        if fat_sectors * entries_per_sector >= cluster_count + 2:
            if not FAT32_MIN_CLUSTERS <= cluster_count <= FAT32_MAX_CLUSTERS:
                raise PooleBootError("proof ESP does not have a valid FAT32 cluster count")
            return fat_sectors, cluster_count
    raise PooleBootError("proof ESP is too small for FAT32")


def _gpt_header(current_lba: int, backup_lba: int, entries_lba: int, entries_crc: int) -> bytes:
    header = bytearray(SECTOR_BYTES)
    struct.pack_into(
        "<8sIIIIQQQQ16sQIII",
        header,
        0,
        b"EFI PART",
        0x00010000,
        GPT_HEADER_BYTES,
        0,
        0,
        current_lba,
        backup_lba,
        FIRST_USABLE_LBA,
        LAST_USABLE_LBA,
        DISK_GUID.bytes_le,
        entries_lba,
        GPT_ENTRY_COUNT,
        GPT_ENTRY_BYTES,
        entries_crc,
    )
    struct.pack_into("<I", header, 16, _crc32(header[:GPT_HEADER_BYTES]))
    return bytes(header)


def _directory_entry(name: bytes, attributes: int, cluster: int = 0, size: int = 0) -> bytes:
    if len(name) != 11:
        raise PooleBootError("FAT short name must contain exactly 11 bytes")
    if cluster < 0 or cluster > 0x0FFFFFFF or size < 0 or size > 0xFFFFFFFF:
        raise PooleBootError("FAT directory entry exceeds its bounded representation")
    return struct.pack(
        "<11sBBBHHHHHHHI",
        name,
        attributes,
        0,
        0,
        0,
        FIXED_FAT_DATE,
        FIXED_FAT_DATE,
        (cluster >> 16) & 0xFFFF,
        0,
        FIXED_FAT_DATE,
        cluster & 0xFFFF,
        size,
    )


def _write_cluster(image: bytearray, data_start_lba: int, cluster: int, data: bytes) -> None:
    if cluster < 2 or len(data) > SECTOR_BYTES * FAT_SECTORS_PER_CLUSTER:
        raise PooleBootError("invalid proof FAT cluster write")
    lba = data_start_lba + (cluster - 2) * FAT_SECTORS_PER_CLUSTER
    offset = _lba_offset(lba)
    image[offset : offset + len(data)] = data


def build_media_bytes(efi_data: bytes) -> bytes:
    if not efi_data or len(efi_data) > MAX_EFI_BYTES:
        raise PooleBootError("PooleBoot EFI payload is empty or exceeds the proof-media bound")
    inspection, errors = validate_binary(
        efi_data,
        {
            "format": "PE32+",
            "machine": 0x8664,
            "subsystem": 10,
            "timestamp": 0,
            "entry_nonzero": True,
            "imports_present": False,
            "debug_directory_present": False,
        },
    )
    if errors or inspection is None:
        raise PooleBootError("PooleBoot EFI payload violates the PE32+ contract: " + "; ".join(errors))

    fat_sectors, cluster_count = _fat_sector_count()
    data_start_lba = ESP_START_LBA + FAT_RESERVED_SECTORS + FAT_COUNT * fat_sectors
    file_cluster_count = (len(efi_data) + SECTOR_BYTES - 1) // SECTOR_BYTES
    first_file_cluster = 5
    last_file_cluster = first_file_cluster + file_cluster_count - 1
    if last_file_cluster > cluster_count + 1:
        raise PooleBootError("PooleBoot EFI payload does not fit in the proof ESP")

    image = bytearray(IMAGE_BYTES)
    protective = bytearray(SECTOR_BYTES)
    protective[446:462] = struct.pack(
        "<B3sB3sII",
        0,
        b"\x00\x02\x00",
        0xEE,
        b"\xff\xff\xff",
        1,
        min(IMAGE_SECTORS - 1, 0xFFFFFFFF),
    )
    protective[510:512] = b"\x55\xaa"
    image[0:SECTOR_BYTES] = protective

    entries = bytearray(GPT_ENTRY_COUNT * GPT_ENTRY_BYTES)
    partition_name = "POOLEOS ESP".encode("utf-16le")
    entries[0:128] = struct.pack(
        "<16s16sQQQ72s",
        ESP_TYPE_GUID.bytes_le,
        ESP_UNIQUE_GUID.bytes_le,
        ESP_START_LBA,
        ESP_END_LBA,
        0,
        partition_name.ljust(72, b"\0"),
    )
    entries_crc = _crc32(entries)
    primary_entries_offset = _lba_offset(PRIMARY_ENTRIES_LBA)
    image[primary_entries_offset : primary_entries_offset + len(entries)] = entries
    backup_entries_offset = _lba_offset(BACKUP_ENTRIES_LBA)
    image[backup_entries_offset : backup_entries_offset + len(entries)] = entries
    image[_lba_offset(PRIMARY_HEADER_LBA) : _lba_offset(PRIMARY_HEADER_LBA) + SECTOR_BYTES] = _gpt_header(
        PRIMARY_HEADER_LBA, BACKUP_HEADER_LBA, PRIMARY_ENTRIES_LBA, entries_crc
    )
    image[_lba_offset(BACKUP_HEADER_LBA) : _lba_offset(BACKUP_HEADER_LBA) + SECTOR_BYTES] = _gpt_header(
        BACKUP_HEADER_LBA, PRIMARY_HEADER_LBA, BACKUP_ENTRIES_LBA, entries_crc
    )

    boot = bytearray(SECTOR_BYTES)
    boot[0:3] = b"\xeb\x58\x90"
    boot[3:11] = b"POOLEOS "
    struct.pack_into("<H", boot, 11, SECTOR_BYTES)
    boot[13] = FAT_SECTORS_PER_CLUSTER
    struct.pack_into("<H", boot, 14, FAT_RESERVED_SECTORS)
    boot[16] = FAT_COUNT
    struct.pack_into("<H", boot, 17, 0)
    struct.pack_into("<H", boot, 19, 0)
    boot[21] = FAT_MEDIA
    struct.pack_into("<H", boot, 22, 0)
    struct.pack_into("<H", boot, 24, 63)
    struct.pack_into("<H", boot, 26, 255)
    struct.pack_into("<I", boot, 28, ESP_START_LBA)
    struct.pack_into("<I", boot, 32, ESP_SECTORS)
    struct.pack_into("<I", boot, 36, fat_sectors)
    struct.pack_into("<H", boot, 40, 0)
    struct.pack_into("<H", boot, 42, 0)
    struct.pack_into("<I", boot, 44, FAT_ROOT_CLUSTER)
    struct.pack_into("<H", boot, 48, 1)
    struct.pack_into("<H", boot, 50, 6)
    boot[64] = 0x80
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, VOLUME_ID)
    boot[71:82] = VOLUME_LABEL
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"
    image[_lba_offset(ESP_START_LBA) : _lba_offset(ESP_START_LBA) + SECTOR_BYTES] = boot
    image[_lba_offset(ESP_START_LBA + 6) : _lba_offset(ESP_START_LBA + 6) + SECTOR_BYTES] = boot

    allocated_clusters = 3 + file_cluster_count
    free_clusters = cluster_count - allocated_clusters
    next_free = last_file_cluster + 1 if last_file_cluster + 1 <= cluster_count + 1 else 0xFFFFFFFF
    fsinfo = bytearray(SECTOR_BYTES)
    struct.pack_into("<I", fsinfo, 0, 0x41615252)
    struct.pack_into("<I", fsinfo, 484, 0x61417272)
    struct.pack_into("<I", fsinfo, 488, free_clusters)
    struct.pack_into("<I", fsinfo, 492, next_free)
    struct.pack_into("<I", fsinfo, 508, 0xAA550000)
    image[_lba_offset(ESP_START_LBA + 1) : _lba_offset(ESP_START_LBA + 2)] = fsinfo
    image[_lba_offset(ESP_START_LBA + 7) : _lba_offset(ESP_START_LBA + 8)] = fsinfo

    fat = bytearray(fat_sectors * SECTOR_BYTES)
    struct.pack_into("<I", fat, 0, 0x0FFFFFF8)
    struct.pack_into("<I", fat, 4, 0x0FFFFFFF)
    for cluster in (2, 3, 4):
        struct.pack_into("<I", fat, cluster * 4, FAT_END)
    for cluster in range(first_file_cluster, last_file_cluster + 1):
        next_cluster = FAT_END if cluster == last_file_cluster else cluster + 1
        struct.pack_into("<I", fat, cluster * 4, next_cluster)
    for index in range(FAT_COUNT):
        fat_offset = _lba_offset(ESP_START_LBA + FAT_RESERVED_SECTORS + index * fat_sectors)
        image[fat_offset : fat_offset + len(fat)] = fat

    root = bytearray(SECTOR_BYTES)
    root[0:32] = _directory_entry(VOLUME_LABEL, 0x08)
    root[32:64] = _directory_entry(b"EFI        ", 0x10, 3)
    _write_cluster(image, data_start_lba, 2, root)
    efi_directory = bytearray(SECTOR_BYTES)
    efi_directory[0:32] = _directory_entry(b".          ", 0x10, 3)
    efi_directory[32:64] = _directory_entry(b"..         ", 0x10, 2)
    efi_directory[64:96] = _directory_entry(b"BOOT       ", 0x10, 4)
    _write_cluster(image, data_start_lba, 3, efi_directory)
    boot_directory = bytearray(SECTOR_BYTES)
    boot_directory[0:32] = _directory_entry(b".          ", 0x10, 4)
    boot_directory[32:64] = _directory_entry(b"..         ", 0x10, 3)
    boot_directory[64:96] = _directory_entry(b"BOOTX64 EFI", 0x20, first_file_cluster, len(efi_data))
    _write_cluster(image, data_start_lba, 4, boot_directory)
    for index, cluster in enumerate(range(first_file_cluster, last_file_cluster + 1)):
        chunk = efi_data[index * SECTOR_BYTES : (index + 1) * SECTOR_BYTES]
        _write_cluster(image, data_start_lba, cluster, chunk)
    return bytes(image)


def _slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise PooleBootError(f"{label} exceeds the proof image")
    return data[offset : offset + size]


def _parse_gpt_header(data: bytes, lba: int, expected_backup: int, expected_entries: int) -> dict[str, Any]:
    sector = _slice(data, lba * SECTOR_BYTES, SECTOR_BYTES, "GPT header")
    if sector[:8] != b"EFI PART":
        raise PooleBootError("GPT header signature is missing")
    revision, header_size, stored_crc, reserved = struct.unpack_from("<IIII", sector, 8)
    if revision != 0x00010000 or header_size != GPT_HEADER_BYTES or reserved != 0:
        raise PooleBootError("GPT header revision, size, or reserved field is invalid")
    header_copy = bytearray(sector[:header_size])
    struct.pack_into("<I", header_copy, 16, 0)
    if _crc32(header_copy) != stored_crc:
        raise PooleBootError("GPT header CRC mismatch")
    current, backup, first_usable, last_usable = struct.unpack_from("<QQQQ", sector, 24)
    disk_guid = uuid.UUID(bytes_le=sector[56:72])
    entries_lba, entry_count, entry_size, entries_crc = struct.unpack_from("<QIII", sector, 72)
    if (
        current != lba
        or backup != expected_backup
        or first_usable != FIRST_USABLE_LBA
        or last_usable != LAST_USABLE_LBA
        or disk_guid != DISK_GUID
        or entries_lba != expected_entries
        or entry_count != GPT_ENTRY_COUNT
        or entry_size != GPT_ENTRY_BYTES
    ):
        raise PooleBootError("GPT header geometry or deterministic identity is invalid")
    entries = _slice(data, entries_lba * SECTOR_BYTES, entry_count * entry_size, "GPT entries")
    if _crc32(entries) != entries_crc:
        raise PooleBootError("GPT partition-entry CRC mismatch")
    return {
        "current_lba": current,
        "backup_lba": backup,
        "entries_lba": entries_lba,
        "header_crc32": f"{stored_crc:08X}",
        "entries_crc32": f"{entries_crc:08X}",
        "entries_sha256": sha256_bytes(entries),
        "entries": entries,
    }


def _fat_entry(fat: bytes, cluster: int) -> int:
    offset = cluster * 4
    if offset + 4 > len(fat):
        raise PooleBootError("FAT entry lies outside the FAT")
    return struct.unpack_from("<I", fat, offset)[0] & 0x0FFFFFFF


def _cluster_chain(fat: bytes, start: int, cluster_count: int) -> list[int]:
    if start < 2 or start > cluster_count + 1:
        raise PooleBootError("FAT chain starts outside the data region")
    chain: list[int] = []
    seen: set[int] = set()
    cluster = start
    while True:
        if cluster in seen:
            raise PooleBootError("FAT chain loop detected")
        if cluster < 2 or cluster > cluster_count + 1:
            raise PooleBootError("FAT chain leaves the data region")
        seen.add(cluster)
        chain.append(cluster)
        if len(chain) > cluster_count:
            raise PooleBootError("FAT chain exceeds the cluster bound")
        next_cluster = _fat_entry(fat, cluster)
        if next_cluster >= 0x0FFFFFF8:
            return chain
        if next_cluster in (0, 1) or 0x0FFFFFF0 <= next_cluster < 0x0FFFFFF8:
            raise PooleBootError("FAT chain contains a free, reserved, or bad cluster")
        cluster = next_cluster


def _cluster_bytes(data: bytes, data_start_lba: int, cluster: int) -> bytes:
    lba = data_start_lba + (cluster - 2) * FAT_SECTORS_PER_CLUSTER
    return _slice(data, lba * SECTOR_BYTES, SECTOR_BYTES * FAT_SECTORS_PER_CLUSTER, "FAT cluster")


def _directory_entries(raw: bytes) -> dict[bytes, dict[str, int]]:
    entries: dict[bytes, dict[str, int]] = {}
    for offset in range(0, len(raw), 32):
        entry = raw[offset : offset + 32]
        if entry[0] == 0:
            break
        if entry[0] == 0xE5:
            continue
        attributes = entry[11]
        if attributes == 0x0F:
            raise PooleBootError("long filename entry is outside the proof-media contract")
        name = entry[:11]
        cluster = (struct.unpack_from("<H", entry, 20)[0] << 16) | struct.unpack_from("<H", entry, 26)[0]
        size = struct.unpack_from("<I", entry, 28)[0]
        if name in entries:
            raise PooleBootError("duplicate FAT short-name entry")
        entries[name] = {"attributes": attributes, "cluster": cluster, "size": size}
    return entries


def inspect_media_bytes(data: bytes) -> dict[str, Any]:
    if len(data) != IMAGE_BYTES:
        raise PooleBootError(f"proof image must be exactly {IMAGE_BYTES} bytes")
    if data[510:512] != b"\x55\xaa":
        raise PooleBootError("protective MBR signature is missing")
    status, _, partition_type, _, first_lba, sector_count = struct.unpack_from("<B3sB3sII", data, 446)
    if status != 0 or partition_type != 0xEE or first_lba != 1 or sector_count != IMAGE_SECTORS - 1:
        raise PooleBootError("protective MBR entry is invalid")

    primary = _parse_gpt_header(data, PRIMARY_HEADER_LBA, BACKUP_HEADER_LBA, PRIMARY_ENTRIES_LBA)
    backup = _parse_gpt_header(data, BACKUP_HEADER_LBA, PRIMARY_HEADER_LBA, BACKUP_ENTRIES_LBA)
    if primary["entries"] != backup["entries"]:
        raise PooleBootError("primary and backup GPT partition arrays differ")
    first_entry = primary["entries"][:GPT_ENTRY_BYTES]
    type_guid = uuid.UUID(bytes_le=first_entry[:16])
    unique_guid = uuid.UUID(bytes_le=first_entry[16:32])
    start_lba, end_lba, attributes = struct.unpack_from("<QQQ", first_entry, 32)
    name = first_entry[56:128].decode("utf-16le").rstrip("\0")
    if (
        type_guid != ESP_TYPE_GUID
        or unique_guid != ESP_UNIQUE_GUID
        or start_lba != ESP_START_LBA
        or end_lba != ESP_END_LBA
        or attributes != 0
        or name != "POOLEOS ESP"
        or any(primary["entries"][GPT_ENTRY_BYTES:])
    ):
        raise PooleBootError("deterministic ESP partition entry is invalid")

    boot_offset = ESP_START_LBA * SECTOR_BYTES
    boot = _slice(data, boot_offset, SECTOR_BYTES, "FAT32 boot sector")
    if boot[510:512] != b"\x55\xaa" or boot[82:90] != b"FAT32   ":
        raise PooleBootError("FAT32 boot signature or type marker is invalid")
    bytes_per_sector = struct.unpack_from("<H", boot, 11)[0]
    sectors_per_cluster = boot[13]
    reserved = struct.unpack_from("<H", boot, 14)[0]
    fat_count = boot[16]
    hidden = struct.unpack_from("<I", boot, 28)[0]
    total_sectors = struct.unpack_from("<I", boot, 32)[0]
    fat_sectors = struct.unpack_from("<I", boot, 36)[0]
    root_cluster = struct.unpack_from("<I", boot, 44)[0]
    fsinfo_sector = struct.unpack_from("<H", boot, 48)[0]
    backup_boot_sector = struct.unpack_from("<H", boot, 50)[0]
    if (
        bytes_per_sector != SECTOR_BYTES
        or sectors_per_cluster != FAT_SECTORS_PER_CLUSTER
        or reserved != FAT_RESERVED_SECTORS
        or fat_count != FAT_COUNT
        or hidden != ESP_START_LBA
        or total_sectors != ESP_SECTORS
        or root_cluster != FAT_ROOT_CLUSTER
        or fsinfo_sector != 1
        or backup_boot_sector != 6
        or boot[71:82] != VOLUME_LABEL
        or struct.unpack_from("<I", boot, 67)[0] != VOLUME_ID
    ):
        raise PooleBootError("FAT32 BPB or deterministic volume identity is invalid")
    expected_fat_sectors, expected_cluster_count = _fat_sector_count()
    if fat_sectors != expected_fat_sectors:
        raise PooleBootError("FAT32 table size is not canonical")
    if _slice(data, (ESP_START_LBA + 6) * SECTOR_BYTES, SECTOR_BYTES, "backup FAT boot sector") != boot:
        raise PooleBootError("FAT32 primary and backup boot sectors differ")
    fsinfo = _slice(data, (ESP_START_LBA + 1) * SECTOR_BYTES, SECTOR_BYTES, "FAT32 FSInfo")
    if (
        struct.unpack_from("<I", fsinfo, 0)[0] != 0x41615252
        or struct.unpack_from("<I", fsinfo, 484)[0] != 0x61417272
        or struct.unpack_from("<I", fsinfo, 508)[0] != 0xAA550000
        or _slice(data, (ESP_START_LBA + 7) * SECTOR_BYTES, SECTOR_BYTES, "backup FAT32 FSInfo") != fsinfo
    ):
        raise PooleBootError("FAT32 FSInfo signatures or backup differ")

    first_fat_offset = (ESP_START_LBA + reserved) * SECTOR_BYTES
    fat_bytes = fat_sectors * SECTOR_BYTES
    first_fat = _slice(data, first_fat_offset, fat_bytes, "first FAT")
    second_fat = _slice(data, first_fat_offset + fat_bytes, fat_bytes, "second FAT")
    if first_fat != second_fat:
        raise PooleBootError("FAT32 copies differ")
    if _fat_entry(first_fat, 0) != 0x0FFFFFF8 or _fat_entry(first_fat, 1) != 0x0FFFFFFF:
        raise PooleBootError("FAT32 reserved entries are invalid")
    data_start_lba = ESP_START_LBA + reserved + fat_count * fat_sectors

    root_chain = _cluster_chain(first_fat, root_cluster, expected_cluster_count)
    if root_chain != [2]:
        raise PooleBootError("proof root directory must occupy exactly one cluster")
    root_entries = _directory_entries(_cluster_bytes(data, data_start_lba, 2))
    if root_entries.get(VOLUME_LABEL, {}).get("attributes") != 0x08:
        raise PooleBootError("FAT32 volume-label directory entry is missing")
    if root_entries.get(b"EFI        ") != {"attributes": 0x10, "cluster": 3, "size": 0}:
        raise PooleBootError("EFI directory entry is missing or malformed")
    if set(root_entries) != {VOLUME_LABEL, b"EFI        "}:
        raise PooleBootError("unexpected root-directory entry")

    efi_entries = _directory_entries(_cluster_bytes(data, data_start_lba, 3))
    if efi_entries.get(b"BOOT       ") != {"attributes": 0x10, "cluster": 4, "size": 0}:
        raise PooleBootError("EFI/BOOT directory entry is missing or malformed")
    if set(efi_entries) != {b".          ", b"..         ", b"BOOT       "}:
        raise PooleBootError("unexpected EFI directory entry")
    boot_entries = _directory_entries(_cluster_bytes(data, data_start_lba, 4))
    fallback = boot_entries.get(b"BOOTX64 EFI")
    if fallback is None or fallback["attributes"] != 0x20:
        raise PooleBootError("UEFI removable-media fallback file is missing")
    if set(boot_entries) != {b".          ", b"..         ", b"BOOTX64 EFI"}:
        raise PooleBootError("unexpected EFI/BOOT directory entry")
    if fallback["size"] <= 0 or fallback["size"] > MAX_EFI_BYTES:
        raise PooleBootError("fallback EFI file size is invalid")
    file_chain = _cluster_chain(first_fat, fallback["cluster"], expected_cluster_count)
    expected_clusters = (fallback["size"] + SECTOR_BYTES - 1) // SECTOR_BYTES
    if len(file_chain) != expected_clusters:
        raise PooleBootError("fallback EFI cluster chain does not match its file size")
    file_data = b"".join(_cluster_bytes(data, data_start_lba, cluster) for cluster in file_chain)
    file_data = file_data[: fallback["size"]]
    inspection, errors = validate_binary(
        file_data,
        {
            "format": "PE32+",
            "machine": 0x8664,
            "subsystem": 10,
            "timestamp": 0,
            "entry_nonzero": True,
            "imports_present": False,
            "debug_directory_present": False,
        },
    )
    if errors or inspection is None:
        raise PooleBootError("embedded fallback EFI file violates the PE32+ contract: " + "; ".join(errors))

    return {
        "image": {
            "sha256": sha256_bytes(data),
            "byte_count": len(data),
            "sector_bytes": SECTOR_BYTES,
            "sector_count": IMAGE_SECTORS,
            "protective_mbr_valid": True,
        },
        "gpt": {
            "disk_guid": str(DISK_GUID).upper(),
            "primary_header_crc32": primary["header_crc32"],
            "backup_header_crc32": backup["header_crc32"],
            "partition_entries_crc32": primary["entries_crc32"],
            "primary_backup_entries_exact_match": True,
        },
        "esp": {
            "type_guid": str(type_guid).upper(),
            "unique_guid": str(unique_guid).upper(),
            "start_lba": start_lba,
            "end_lba": end_lba,
            "sector_count": end_lba - start_lba + 1,
            "label": name,
        },
        "fat32": {
            "volume_label": VOLUME_LABEL.decode("ascii"),
            "volume_id": f"{VOLUME_ID:08X}",
            "fat_count": fat_count,
            "fat_sector_count": fat_sectors,
            "cluster_count": expected_cluster_count,
            "fat_copies_exact_match": True,
            "boot_sector_backup_exact_match": True,
            "fsinfo_backup_exact_match": True,
        },
        "files": [
            {
                "path": FALLBACK_PATH,
                "sha256": sha256_bytes(file_data),
                "byte_count": len(file_data),
                "cluster_count": len(file_chain),
            }
        ],
        "embedded_efi": inspection,
    }


def extract_markers(raw: bytes) -> list[str]:
    text = raw.decode("ascii", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in text.splitlines() if line.strip().startswith(MARKER_PREFIX)]


def validate_markers(markers: list[str]) -> dict[str, Any]:
    from runtime import native_kernel_load

    try:
        return native_kernel_load.validate_markers(markers)
    except native_kernel_load.KernelLoadError as error:
        raise PooleBootError(str(error)) from error


def inspect_ppm(data: bytes) -> dict[str, Any]:
    if not data.startswith(b"P6\n"):
        raise PooleBootError("QMP screenshot is not a binary PPM image")
    parts = data.split(b"\n", 3)
    if len(parts) != 4:
        raise PooleBootError("QMP PPM header is truncated")
    try:
        width_text, height_text = parts[1].split()
        width = int(width_text)
        height = int(height_text)
        maximum = int(parts[2])
    except (ValueError, TypeError) as error:
        raise PooleBootError("QMP PPM header is malformed") from error
    pixels = parts[3]
    if width < 320 or height < 200 or width > 16_384 or height > 16_384 or maximum != 255:
        raise PooleBootError("QMP PPM geometry or component range is invalid")
    if len(pixels) != width * height * 3:
        raise PooleBootError("QMP PPM pixel payload length is inconsistent")
    colors: set[bytes] = set()
    bright_cyan_count = 0
    dark_count = 0
    for offset in range(0, len(pixels), 3):
        pixel = pixels[offset : offset + 3]
        if len(colors) < 1024:
            colors.add(pixel)
        red, green, blue = pixel
        bright_cyan_count += int(green >= 160 and blue >= 170 and blue + green > red * 2)
        dark_count += int(red <= 20 and green <= 30 and blue <= 35)
    total = width * height
    if len(colors) < 4 or bright_cyan_count < total // 500 or dark_count < total // 4:
        raise PooleBootError("QMP screenshot lacks the required high-contrast PooleOS identity")
    return {
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
        "width": width,
        "height": height,
        "pixel_count": total,
        "sampled_unique_color_count": len(colors),
        "bright_cyan_pixel_count": bright_cyan_count,
        "dark_pixel_count": dark_count,
        "nonblank": True,
        "poole_identity_palette_observed": True,
    }


def expected_claims() -> dict[str, bool]:
    return {
        **{name: True for name in TRUE_PROOF_CLAIMS},
        **{name: False for name in FALSE_PROOF_CLAIMS},
    }


def validate_claims(claims: dict[str, Any]) -> None:
    expected = expected_claims()
    if set(claims) != set(expected):
        raise PooleBootError("PooleBoot proof claim set changed")
    for name, value in expected.items():
        if claims.get(name) is not value:
            raise PooleBootError(f"PooleBoot proof claim overreach or omission: {name}")


def file_binding(root: Path, relative_path: str) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise PooleBootError(f"binding escapes repository root: {relative_path}") from error
    data = path.read_bytes()
    return {
        "path": relative_path.replace("\\", "/"),
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise PooleBootError(f"JSON root must be an object: {path.name}")
    return value


def _schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    from runtime.schema_validation import validate_json

    schema = read_json(root / schema_relative)
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def proof_contract_errors(contract: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(contract, root, CONTRACT_SCHEMA_RELATIVE)
    if contract.get("phase_mapping") != [
        "N5.1",
        "N5.2",
        "N5.3",
        "N5.4",
        "N5.5",
        "N5.6",
        "N5.7",
        "N5.8",
        "N5.9",
    ]:
        errors.append("PooleBoot proof phase mapping changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PooleBoot proof negative-control register changed")
    if contract.get("required_markers") != [
        "ENTRY",
        "SYSTEM_TABLE PASS",
        "BOOT_SERVICES PASS",
        "WATCHDOG",
        "CONSOLE PASS_OR_FALLBACK",
        "CONFIG PASS",
        "FILESYSTEM PASS",
        "BOOTCFG PASS",
        "MANIFEST PASS",
        "KERNEL_BINDING PASS",
        "KERNEL_FILE PASS",
        "KERNEL_LOAD PASS",
        "ARTIFACT_SET PASS",
        "GOP PASS",
        "FRAME READY",
        "KERNEL_MAP_PLAN PASS",
        "KERNEL_MAP_ACTIVE PASS",
        "KERNEL_MAP_RETAIN PASS",
        "PBP1_FINAL PASS",
        "EXIT_BOOT_SERVICES PASS",
        "FIRMWARE_BOUNDARY PASS",
        "BOUNDARY",
        "STOP BEFORE TRANSFER",
    ]:
        errors.append("PooleBoot proof marker register changed")
    media = contract.get("media", {})
    if media.get("artifact_paths") != [
        "EFI/POOLEOS/INITIAL.PBA",
        "EFI/POOLEOS/RECOVERY.PBA",
        "EFI/POOLEOS/SYMBOLS.PBA",
        "EFI/POOLEOS/MICROCOD.PBA",
        "EFI/POOLEOS/FIRMWARE.PBA",
        "EFI/POOLEOS/POLICY.PBA",
    ]:
        errors.append("PooleBoot proof artifact path register changed")
    expected_media_policy = {
        "ordinary_workspace_file_only": True,
        "allowed_output_roots": list(SAFE_MEDIA_OUTPUT_ROOTS),
        "input_must_be_workspace_regular_file": True,
        "device_namespace_allowed": False,
        "alternate_data_stream_allowed": False,
        "reserved_device_name_allowed": False,
        "symlink_paths_allowed": False,
        "physical_media_write_allowed": False,
    }
    for name, expected in expected_media_policy.items():
        if media.get(name) != expected:
            errors.append(f"PooleBoot proof media policy changed: {name}")
    execution = contract.get("execution", {})
    if execution.get("guest_network") is not False or execution.get("host_acceleration") is not False:
        errors.append("PooleBoot proof execution boundary changed")
    return errors


def _check_binding(
    errors: list[str],
    binding: Any,
    root: Path,
    expected_path: str,
    label: str,
) -> None:
    if not isinstance(binding, dict) or binding.get("path") != expected_path:
        errors.append(f"{label} binding path changed")
        return
    try:
        expected = file_binding(root, expected_path)
    except (OSError, PooleBootError) as error:
        errors.append(f"{label} binding cannot be read: {error}")
        return
    if binding != expected:
        errors.append(f"stale {label} binding")


def readiness_contract_errors(readiness: dict[str, Any], root: Path) -> list[str]:
    from runtime import native_kernel_load

    errors = _schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
    except (OSError, json.JSONDecodeError, PooleBootError) as error:
        return errors + [f"PooleBoot proof contract cannot be read: {error}"]
    errors.extend(proof_contract_errors(contract, root))
    bindings = readiness.get("bindings", {})
    expected_bindings = {
        "contract": CONTRACT_RELATIVE,
        "toolchain_lock": "specs/native-toolchain-lock.json",
        "toolchain_qualification": "runs/native_toolchain_qualification.json",
        "tier0_lock": "specs/native-tier0-lock.json",
        "tier0_profile": "specs/native-tier0-profile.json",
        "tier0_readiness": "runs/native_tier0_readiness.json",
        "kernel_entry_readiness": "runs/native_kernel_entry_readiness.json",
        "kernel_load_contract": "specs/native-kernel-load-contract.json",
        "kernel_load_readiness": "runs/native_kernel_load_readiness.json",
        "system_manifest_contract": "specs/native-system-manifest-contract.json",
        "system_manifest_readiness": "runs/native_system_manifest_readiness.json",
        "initial_system_contract": "specs/native-initial-system-contract.json",
        "initial_system_readiness": "runs/native_initial_system_readiness.json",
        "recovery_contract": "specs/native-recovery-contract.json",
        "recovery_readiness": "runs/native_recovery_readiness.json",
        "symbols_contract": "specs/native-symbol-contract.json",
        "symbols_readiness": "runs/native_symbol_readiness.json",
    }
    for name, relative_path in expected_bindings.items():
        _check_binding(errors, bindings.get(name), root, relative_path, name)
    implementation_inputs = bindings.get("implementation_inputs", [])
    if not isinstance(implementation_inputs, list) or [
        item.get("path") for item in implementation_inputs if isinstance(item, dict)
    ] != list(PROOF_IMPLEMENTATION_INPUTS):
        errors.append("PooleBoot implementation-input order changed")
    else:
        for item, relative_path in zip(implementation_inputs, PROOF_IMPLEMENTATION_INPUTS, strict=True):
            _check_binding(errors, item, root, relative_path, f"implementation input {relative_path}")

    build = readiness.get("build", {})
    inspection = build.get("inspection", {})
    expected_pe = {
        "format": "PE32+",
        "machine": 0x8664,
        "subsystem": 10,
        "timestamp": 0,
        "entry_nonzero": True,
        "imports_present": False,
        "debug_directory_present": False,
    }
    if any(inspection.get(key) != value for key, value in expected_pe.items()):
        errors.append("PooleBoot build inspection violates the PE32+ proof contract")
    if build.get("clean_build_count") != 2 or build.get("exact_clean_build_match") is not True:
        errors.append("PooleBoot clean-build evidence is incomplete")
    media = readiness.get("media", {})
    media_inspection = media.get("inspection", {})
    files = media_inspection.get("files", [])
    embedded = media_inspection.get("embedded_efi", {})
    if not isinstance(files, list) or len(files) != 10:
        errors.append("PooleBoot media file manifest does not contain exactly ten files")
    else:
        file_item = files[0]
        if (
            file_item.get("path") != FALLBACK_PATH
            or file_item.get("sha256") != build.get("sha256")
            or file_item.get("byte_count") != build.get("byte_count")
        ):
            errors.append("embedded fallback EFI does not match the clean PooleBoot build")
        if [item.get("path") for item in files] != [
            FALLBACK_PATH,
            "EFI/POOLEOS/BOOT.CFG",
            "EFI/POOLEOS/SYSTEM_A.PBM",
            "EFI/POOLEOS/KERNEL.ELF",
            "EFI/POOLEOS/INITIAL.PBA",
            "EFI/POOLEOS/RECOVERY.PBA",
            "EFI/POOLEOS/SYMBOLS.PBA",
            "EFI/POOLEOS/MICROCOD.PBA",
            "EFI/POOLEOS/FIRMWARE.PBA",
            "EFI/POOLEOS/POLICY.PBA",
        ]:
            errors.append("PooleBoot media file paths changed")
        artifact_set = media_inspection.get("artifact_set", {})
        if (
            artifact_set.get("contract_id") != "PBART1"
            or artifact_set.get("artifact_count") != 6
            or artifact_set.get("signatures_verified") is not False
            or artifact_set.get("measured") is not False
            or artifact_set.get("semantics_applied") is not False
        ):
            errors.append("PooleBoot artifact-set boundary changed")
        symbols = media_inspection.get("symbols", {})
        if (
            symbols.get("contract_id") != "PSYM1"
            or symbols.get("activation_allowed") is not False
            or symbols.get("pooleboot_enforced") is not False
            or symbols.get("poolekernel_enforced") is not False
            or symbols.get("symbols_consumed") is not False
            or symbols.get("runtime_addresses_disclosed") is not False
            or symbols.get("full_debug_file_on_media") is not False
            or symbols.get("authority_created") is not False
        ):
            errors.append("PooleBoot PSYM1 media boundary changed")
    if embedded.get("sha256") != build.get("sha256") or embedded.get("byte_count") != build.get(
        "byte_count"
    ):
        errors.append("embedded EFI inspection does not match the clean PooleBoot build")
    if media.get("ordinary_workspace_file_only") is not True:
        errors.append("PooleBoot readiness does not preserve the ordinary-file boundary")
    if media.get("physical_media_write_performed") is not False:
        errors.append("PooleBoot readiness claims a physical-media write")

    execution = readiness.get("execution", {})
    runs = execution.get("runs", [])
    marker_sets: list[list[str]] = []
    screenshot_hashes: list[str] = []
    if not isinstance(runs, list) or len(runs) != 2:
        errors.append("PooleBoot execution does not contain exactly two runs")
    else:
        for index, run in enumerate(runs):
            if not isinstance(run, dict):
                errors.append(f"PooleBoot run {index} is not an object")
                continue
            markers = run.get("markers", [])
            try:
                summary = validate_markers(markers)
                native_kernel_load.validate_oracle_binding(
                    summary,
                    media_inspection,
                    run.get("pbp1_transcript"),
                )
            except (PooleBootError, native_kernel_load.KernelLoadError) as error:
                errors.append(f"PooleBoot run {index} marker failure: {error}")
                continue
            marker_sets.append(markers)
            expected_marker_hash = sha256_bytes(canonical_json_bytes(markers))
            if run.get("marker_sha256") != expected_marker_hash:
                errors.append(f"PooleBoot run {index} marker digest mismatch")
            if run.get("marker_summary") != summary:
                errors.append(f"PooleBoot run {index} marker summary mismatch")
            screenshot = run.get("screenshot", {})
            screenshot_hashes.append(screenshot.get("sha256", ""))
            if (
                screenshot.get("width") != summary["gop"]["width"]
                or screenshot.get("height") != summary["gop"]["height"]
                or screenshot.get("nonblank") is not True
                or screenshot.get("poole_identity_palette_observed") is not True
            ):
                errors.append(f"PooleBoot run {index} screenshot and GOP marker differ")
            for name, expected in (
                ("fresh_vars_copy", True),
                ("media_read_only", True),
                ("guest_network", False),
                ("host_acceleration", False),
                ("qmp_loopback_only", True),
                ("qmp_quit_requested", True),
                ("serial_debugcon_exact_match", True),
                ("local_paths_recorded", False),
            ):
                if run.get(name) is not expected:
                    errors.append(f"PooleBoot run {index} boundary changed: {name}")
            if run.get("qemu_exit_code") != 0 or run.get("stderr_byte_count") != 0:
                errors.append(f"PooleBoot run {index} did not exit cleanly through QMP")
    if len(marker_sets) == 2 and marker_sets[0] != marker_sets[1]:
        errors.append("PooleBoot run marker sequences differ")
    if len(screenshot_hashes) == 2 and screenshot_hashes[0] != screenshot_hashes[1]:
        errors.append("PooleBoot run screenshots differ")
    normalized = execution.get("normalized_command", [])
    if execution.get("normalized_command_sha256") != sha256_bytes(canonical_json_bytes(normalized)):
        errors.append("PooleBoot normalized command digest mismatch")
    joined_command = "\n".join(normalized) if isinstance(normalized, list) else ""
    for required in ("VGA,id=poole_gop", "tcp:127.0.0.1:$QMP_PORT,server=on,wait=off"):
        if required not in joined_command:
            errors.append(f"PooleBoot normalized command is missing {required}")
    for forbidden in ("-netdev", "-virtfs", "accel=kvm", "accel=whpx"):
        if forbidden in joined_command:
            errors.append(f"PooleBoot normalized command contains forbidden input: {forbidden}")

    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("PooleBoot readiness negative-control register changed")
    if any(
        item.get("status") != "pass"
        or item.get("expected") != "reject"
        or item.get("observed") != "reject"
        for item in controls
        if isinstance(item, dict)
    ):
        errors.append("PooleBoot readiness has a failing negative control")
    try:
        validate_claims(readiness.get("claims", {}))
    except PooleBootError as error:
        errors.append(str(error))
    if readiness.get("claim_boundary") != contract.get("claim_boundary"):
        errors.append("PooleBoot readiness claim boundary differs from its contract")
    if ABSOLUTE_USER_PATH.search(json.dumps(readiness, ensure_ascii=True)):
        errors.append("absolute user path leaked into PooleBoot readiness")
    return errors
