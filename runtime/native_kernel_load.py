"""Deterministic PKLOAD1 media, independent oracles, markers, and claims."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

from runtime import native_boot_config, native_elf_loader, native_pooleboot
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKLOAD1"
CONFIG_PATH = "EFI/POOLEOS/BOOT.CFG"
KERNEL_PATH = "EFI/POOLEOS/KERNEL.ELF"
POOLEOS_DIRECTORY_NAME = b"POOLEOS    "
CONFIG_SHORT_NAME = b"BOOT    CFG"
KERNEL_SHORT_NAME = b"KERNEL  ELF"
PHYSICAL_ORACLE_BASE = 0x0200_0000
CONTRACT_RELATIVE = "specs/native-kernel-load-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-load-contract.schema.json"
READINESS_RELATIVE = "runs/native_kernel_load_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-load-readiness.schema.json"

IMPLEMENTATION_INPUTS = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/lib.rs",
    "native/boot/src/main.rs",
    "native/boot/src/kload.rs",
    "native/bootload/Cargo.toml",
    "native/bootload/src/lib.rs",
    "native/bootcfg/src/lib.rs",
    "native/elf/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "runtime/native_boot_config.py",
    "runtime/native_elf_loader.py",
    "runtime/native_kernel_image.py",
    "runtime/native_kernel_load.py",
    "runtime/native_pooleboot.py",
    "specs/native-kernel-load-contract.json",
    "specs/native-kernel-load-contract.schema.json",
    "specs/native-kernel-load-readiness.schema.json",
    "tools/qualify_native_kernel_load.py",
)

TRUE_CLAIMS = (
    "loaded_image_protocol_observed",
    "simple_filesystem_protocol_observed",
    "live_pbc1_file_parsed",
    "live_pkelf1_file_read",
    "pkelf1_relocated_into_firmware_pages",
    "pkelf1_mapping_plan_validated",
    "all_kload_resources_released",
    "two_qemu_runs_exact",
)
FALSE_CLAIMS = (
    "manifest_authenticated_selection",
    "kernel_signature_verified",
    "kernel_pages_retained",
    "page_tables_activated",
    "kernel_entry_called",
    "pbp1_handoff_produced",
    "exit_boot_services_called",
    "secure_boot_enforced",
    "measured_boot_performed",
    "physical_hardware_tested",
    "n5_exit_gate_satisfied",
    "production_ready",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N5-KLOAD-CONFIG-MISSING",
    "NEG-N5-KLOAD-CONFIG-EMPTY",
    "NEG-N5-KLOAD-CONFIG-OVERSIZE",
    "NEG-N5-KLOAD-CONFIG-MALFORMED",
    "NEG-N5-KLOAD-KERNEL-MISSING",
    "NEG-N5-KLOAD-KERNEL-EMPTY",
    "NEG-N5-KLOAD-KERNEL-OVERSIZE",
    "NEG-N5-KLOAD-KERNEL-MALFORMED",
    "NEG-N5-KLOAD-FAT-COPY",
    "NEG-N5-KLOAD-FAT-CHAIN-LOOP",
    "NEG-N5-KLOAD-DIRECTORY-PATH",
    "NEG-N5-KLOAD-CONFIG-PATH",
    "NEG-N5-KLOAD-KERNEL-PATH",
    "NEG-N5-KLOAD-CONFIG-CONTENT",
    "NEG-N5-KLOAD-KERNEL-CONTENT",
    "NEG-N5-KLOAD-MARKER-OMISSION",
    "NEG-N5-KLOAD-MARKER-ORDER",
    "NEG-N5-KLOAD-MARKER-CONFIG-BOUND",
    "NEG-N5-KLOAD-MARKER-KERNEL-BOUND",
    "NEG-N5-KLOAD-MARKER-PAGE-MATH",
    "NEG-N5-KLOAD-MARKER-ENTRY-BOUND",
    "NEG-N5-KLOAD-MARKER-MAPPING-COUNT",
    "NEG-N5-KLOAD-MARKER-WX",
    "NEG-N5-KLOAD-MARKER-RELEASE-COUNT",
    "NEG-N5-KLOAD-MARKER-BOUNDARY",
    "NEG-N5-KLOAD-CONFIG-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-ELF-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-LOADED-HASH-DIVERGENCE",
    "NEG-N5-KLOAD-CLAIM-OVERREACH",
    "NEG-N5-KLOAD-STALE-BINDING",
)

MARKER_PATTERNS = (
    re.compile(r"^POOLEBOOT/0\.1 ENTRY$"),
    re.compile(r"^POOLEBOOT/0\.1 SYSTEM_TABLE PASS revision=0x[0-9A-F]{8}$"),
    re.compile(r"^POOLEBOOT/0\.1 BOOT_SERVICES PASS$"),
    re.compile(r"^POOLEBOOT/0\.1 WATCHDOG status=0x[0-9A-F]{16}$"),
    re.compile(r"^POOLEBOOT/0\.1 CONSOLE (?:PASS|FALLBACK status=0x[0-9A-F]{16})$"),
    re.compile(
        r"^POOLEBOOT/0\.1 CONFIG PASS count=([0-9]+) acpi20=([01]) smbios3=([01]) smbios2=([01])$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 FILESYSTEM PASS loaded_image=1 simple_fs=1 root=1$"),
    re.compile(
        r"^POOLEBOOT/0\.1 BOOTCFG PASS bytes=([0-9]+) entries=([0-9]+) default_hash=([0-9A-F]{16}) timeout_ms=([0-9]+) attempts=([0-9]+) slot=([0-9]+) manifest_max_bytes=([0-9]+)$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 KERNEL_FILE PASS bytes=([0-9]+) path=fixed_development$"),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_LOAD PASS image_bytes=([0-9]+) pages=([0-9]+) entry_offset=([0-9]+) relocations=([0-9]+) fnv1a64=([0-9A-F]{16})$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_MAP PASS mappings=([0-9]+) rx=([0-9]+) rw=([0-9]+) wx=([0-9]+) activation=not_performed$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_RELEASE PASS files_closed=([0-9]+) pools_freed=([0-9]+) pages_freed=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 GOP PASS width=([0-9]+) height=([0-9]+) stride=([0-9]+) mode=([0-9]+) format=(RGB|BGR)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 MEMORY_MAP PASS bytes=([0-9]+) descriptor_bytes=([0-9]+) descriptors=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 BOUNDARY unsigned=1 secure_boot=not_tested selection=fixed_untrusted kernel=loaded_then_released mappings=planned_not_activated entry=not_called exit_boot_services=not_called$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 FRAME READY$"),
    re.compile(r"^POOLEBOOT/0\.1 RETURN EFI_SUCCESS$"),
)


class KernelLoadError(RuntimeError):
    """Raised when a PKLOAD1 proof input violates its bounded contract."""


def canonical_config_bytes() -> bytes:
    return native_boot_config.encode(
        (
            native_boot_config.Entry(
                "normal",
                "normal",
                1,
                r"\EFI\POOLEOS\MANIFEST_A.PBM",
                65_536,
            ),
        ),
        default_entry="normal",
        timeout_ms=0,
        boot_attempt_limit=3,
    )


def _cluster_count(byte_count: int) -> int:
    if byte_count <= 0:
        raise KernelLoadError("file payload is empty")
    return (byte_count + native_pooleboot.SECTOR_BYTES - 1) // native_pooleboot.SECTOR_BYTES


def _write_chain(
    image: bytearray,
    fat: bytearray,
    data_start_lba: int,
    first_cluster: int,
    payload: bytes,
) -> tuple[int, int]:
    count = _cluster_count(len(payload))
    last_cluster = first_cluster + count - 1
    for index, cluster in enumerate(range(first_cluster, last_cluster + 1)):
        next_cluster = native_pooleboot.FAT_END if cluster == last_cluster else cluster + 1
        struct.pack_into("<I", fat, cluster * 4, next_cluster)
        chunk = payload[
            index * native_pooleboot.SECTOR_BYTES : (index + 1) * native_pooleboot.SECTOR_BYTES
        ]
        native_pooleboot._write_cluster(image, data_start_lba, cluster, chunk)
    return count, last_cluster


def build_media_bytes(efi_data: bytes, config_data: bytes, kernel_data: bytes) -> bytes:
    try:
        native_boot_config.parse(config_data)
        kernel_plan, _ = native_elf_loader.load(
            kernel_data,
            PHYSICAL_ORACLE_BASE,
            native_elf_loader.MIN_VIRTUAL_BASE,
        )
    except (native_boot_config.BootConfigError, native_elf_loader.ElfError) as error:
        raise KernelLoadError(f"PKLOAD1 input validation failed: {error}") from error
    if len(config_data) > native_boot_config.MAX_CONFIG_BYTES:
        raise KernelLoadError("PBC1 input exceeds its file bound")
    if len(kernel_data) > native_elf_loader.MAX_FILE_BYTES:
        raise KernelLoadError("PKELF1 input exceeds its file bound")
    if kernel_plan.image_size > native_elf_loader.MAX_IMAGE_BYTES:
        raise KernelLoadError("PKELF1 image exceeds its allocation bound")

    image = bytearray(native_pooleboot.build_media_bytes(efi_data))
    fat_sectors, cluster_count = native_pooleboot._fat_sector_count()
    fat_offset = (
        native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
    ) * native_pooleboot.SECTOR_BYTES
    fat_byte_count = fat_sectors * native_pooleboot.SECTOR_BYTES
    fat = bytearray(image[fat_offset : fat_offset + fat_byte_count])
    data_start_lba = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + native_pooleboot.FAT_COUNT * fat_sectors
    )
    efi_clusters = _cluster_count(len(efi_data))
    pooleos_cluster = 5 + efi_clusters
    config_first = pooleos_cluster + 1
    config_clusters, config_last = _write_chain(
        image, fat, data_start_lba, config_first, config_data
    )
    kernel_first = config_last + 1
    kernel_clusters, kernel_last = _write_chain(
        image, fat, data_start_lba, kernel_first, kernel_data
    )
    if kernel_last > cluster_count + 1:
        raise KernelLoadError("PKLOAD1 files do not fit in the deterministic ESP")
    struct.pack_into("<I", fat, pooleos_cluster * 4, native_pooleboot.FAT_END)

    efi_directory = bytearray(
        native_pooleboot._cluster_bytes(bytes(image), data_start_lba, 3)
    )
    efi_directory[96:128] = native_pooleboot._directory_entry(
        POOLEOS_DIRECTORY_NAME, 0x10, pooleos_cluster
    )
    native_pooleboot._write_cluster(image, data_start_lba, 3, efi_directory)

    pooleos_directory = bytearray(native_pooleboot.SECTOR_BYTES)
    pooleos_directory[0:32] = native_pooleboot._directory_entry(
        b".          ", 0x10, pooleos_cluster
    )
    pooleos_directory[32:64] = native_pooleboot._directory_entry(b"..         ", 0x10, 3)
    pooleos_directory[64:96] = native_pooleboot._directory_entry(
        CONFIG_SHORT_NAME, 0x20, config_first, len(config_data)
    )
    pooleos_directory[96:128] = native_pooleboot._directory_entry(
        KERNEL_SHORT_NAME, 0x20, kernel_first, len(kernel_data)
    )
    native_pooleboot._write_cluster(image, data_start_lba, pooleos_cluster, pooleos_directory)

    for index in range(native_pooleboot.FAT_COUNT):
        copy_offset = fat_offset + index * fat_byte_count
        image[copy_offset : copy_offset + fat_byte_count] = fat
    allocated_clusters = 4 + efi_clusters + config_clusters + kernel_clusters
    free_clusters = cluster_count - allocated_clusters
    next_free = kernel_last + 1 if kernel_last + 1 <= cluster_count + 1 else 0xFFFF_FFFF
    for sector in (1, 7):
        fsinfo_offset = (
            native_pooleboot.ESP_START_LBA + sector
        ) * native_pooleboot.SECTOR_BYTES
        struct.pack_into("<I", image, fsinfo_offset + 488, free_clusters)
        struct.pack_into("<I", image, fsinfo_offset + 492, next_free)
    return bytes(image)


def _file_bytes(
    data: bytes,
    fat: bytes,
    data_start_lba: int,
    entry: dict[str, int],
    cluster_count: int,
    maximum_size: int,
    label: str,
) -> tuple[bytes, list[int]]:
    size = entry.get("size", 0)
    if entry.get("attributes") != 0x20 or size <= 0 or size > maximum_size:
        raise KernelLoadError(f"{label} directory entry is invalid")
    chain = native_pooleboot._cluster_chain(fat, entry["cluster"], cluster_count)
    expected = _cluster_count(size)
    if len(chain) != expected:
        raise KernelLoadError(f"{label} FAT chain length differs from its file size")
    payload = b"".join(
        native_pooleboot._cluster_bytes(data, data_start_lba, cluster) for cluster in chain
    )[:size]
    return payload, chain


def inspect_media_bytes(data: bytes) -> dict[str, Any]:
    if len(data) != native_pooleboot.IMAGE_BYTES:
        raise KernelLoadError("PKLOAD1 image byte count is not canonical")
    try:
        primary = native_pooleboot._parse_gpt_header(
            data,
            native_pooleboot.PRIMARY_HEADER_LBA,
            native_pooleboot.BACKUP_HEADER_LBA,
            native_pooleboot.PRIMARY_ENTRIES_LBA,
        )
        backup = native_pooleboot._parse_gpt_header(
            data,
            native_pooleboot.BACKUP_HEADER_LBA,
            native_pooleboot.PRIMARY_HEADER_LBA,
            native_pooleboot.BACKUP_ENTRIES_LBA,
        )
        if primary["entries"] != backup["entries"]:
            raise KernelLoadError("primary and backup GPT entries differ")
        fat_sectors, cluster_count = native_pooleboot._fat_sector_count()
        fat_offset = (
            native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
        ) * native_pooleboot.SECTOR_BYTES
        fat_bytes = fat_sectors * native_pooleboot.SECTOR_BYTES
        first_fat = native_pooleboot._slice(data, fat_offset, fat_bytes, "PKLOAD1 first FAT")
        second_fat = native_pooleboot._slice(
            data, fat_offset + fat_bytes, fat_bytes, "PKLOAD1 second FAT"
        )
        if first_fat != second_fat:
            raise KernelLoadError("PKLOAD1 FAT copies differ")
        data_start_lba = (
            native_pooleboot.ESP_START_LBA
            + native_pooleboot.FAT_RESERVED_SECTORS
            + native_pooleboot.FAT_COUNT * fat_sectors
        )
        root_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, 2)
        )
        if set(root_entries) != {native_pooleboot.VOLUME_LABEL, b"EFI        "}:
            raise KernelLoadError("PKLOAD1 root directory changed")
        efi_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, 3)
        )
        expected_efi_names = {
            b".          ",
            b"..         ",
            b"BOOT       ",
            POOLEOS_DIRECTORY_NAME,
        }
        if set(efi_entries) != expected_efi_names:
            raise KernelLoadError("PKLOAD1 EFI directory changed")
        boot_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, 4)
        )
        if set(boot_entries) != {b".          ", b"..         ", b"BOOTX64 EFI"}:
            raise KernelLoadError("PKLOAD1 EFI/BOOT directory changed")
        efi_data, efi_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            boot_entries[b"BOOTX64 EFI"],
            cluster_count,
            native_pooleboot.MAX_EFI_BYTES,
            "PooleBoot",
        )
        expected_pooleos_cluster = efi_chain[-1] + 1
        pooleos_entry = efi_entries[POOLEOS_DIRECTORY_NAME]
        if pooleos_entry != {
            "attributes": 0x10,
            "cluster": expected_pooleos_cluster,
            "size": 0,
        }:
            raise KernelLoadError("PKLOAD1 POOLEOS directory placement changed")
        pooleos_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, expected_pooleos_cluster)
        )
        if set(pooleos_entries) != {
            b".          ",
            b"..         ",
            CONFIG_SHORT_NAME,
            KERNEL_SHORT_NAME,
        }:
            raise KernelLoadError("PKLOAD1 POOLEOS directory changed")
        config_data, config_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[CONFIG_SHORT_NAME],
            cluster_count,
            native_boot_config.MAX_CONFIG_BYTES,
            "PBC1",
        )
        kernel_data, kernel_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[KERNEL_SHORT_NAME],
            cluster_count,
            native_elf_loader.MAX_FILE_BYTES,
            "PKELF1",
        )
        if config_chain[0] != expected_pooleos_cluster + 1 or kernel_chain[0] != config_chain[-1] + 1:
            raise KernelLoadError("PKLOAD1 file cluster placement changed")
        config = native_boot_config.parse(config_data)
        kernel_plan, loaded = native_elf_loader.load(
            kernel_data,
            PHYSICAL_ORACLE_BASE,
            native_elf_loader.MIN_VIRTUAL_BASE,
        )
    except (
        native_pooleboot.PooleBootError,
        native_boot_config.BootConfigError,
        native_elf_loader.ElfError,
        KeyError,
        IndexError,
        struct.error,
    ) as error:
        raise KernelLoadError(f"PKLOAD1 media inspection failed: {error}") from error

    if config_data != canonical_config_bytes():
        raise KernelLoadError("PKLOAD1 config differs from the canonical development profile")
    expected = build_media_bytes(efi_data, config_data, kernel_data)
    if data != expected:
        raise KernelLoadError("PKLOAD1 media differs from its canonical reconstruction")
    base = native_pooleboot.inspect_media_bytes(native_pooleboot.build_media_bytes(efi_data))
    base["image"]["sha256"] = native_pooleboot.sha256_bytes(data)
    base["files"] = [
        {
            "path": native_pooleboot.FALLBACK_PATH,
            "sha256": native_pooleboot.sha256_bytes(efi_data),
            "byte_count": len(efi_data),
            "cluster_count": len(efi_chain),
        },
        {
            "path": CONFIG_PATH,
            "sha256": native_pooleboot.sha256_bytes(config_data),
            "byte_count": len(config_data),
            "cluster_count": len(config_chain),
        },
        {
            "path": KERNEL_PATH,
            "sha256": native_pooleboot.sha256_bytes(kernel_data),
            "byte_count": len(kernel_data),
            "cluster_count": len(kernel_chain),
        },
    ]
    base["config"] = {
        "default_entry": config.default_entry,
        "default_entry_hash": f"{native_elf_loader.fnv1a64(config.default_entry.encode('ascii')):016X}",
        "entry_count": len(config.entries),
        "timeout_ms": config.timeout_ms,
        "boot_attempt_limit": config.boot_attempt_limit,
        "selected_slot": next(
            entry.slot for entry in config.entries if entry.id == config.default_entry
        ),
        "manifest_max_bytes": next(
            entry.manifest_max_bytes for entry in config.entries if entry.id == config.default_entry
        ),
    }
    base["kernel"] = {
        "plan": dataclasses.asdict(kernel_plan),
        "loaded_fnv1a64": f"{native_elf_loader.fnv1a64(loaded):016X}",
        "loaded_sha256": native_pooleboot.sha256_bytes(loaded),
    }
    base["fat32"]["cluster_count"] = cluster_count
    return base


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != len(MARKER_PATTERNS):
        raise KernelLoadError(
            f"expected {len(MARKER_PATTERNS)} PKLOAD1 markers, observed {len(markers)}"
        )
    matches = []
    for index, (pattern, marker) in enumerate(zip(MARKER_PATTERNS, markers, strict=True)):
        match = pattern.fullmatch(marker)
        if match is None:
            raise KernelLoadError(f"PKLOAD1 marker {index} violates its contract: {marker!r}")
        matches.append(match)

    config_bytes = int(matches[7].group(1))
    config_entries = int(matches[7].group(2))
    timeout_ms = int(matches[7].group(4))
    attempts = int(matches[7].group(5))
    slot = int(matches[7].group(6))
    manifest_max = int(matches[7].group(7))
    if not 1 <= config_bytes <= native_boot_config.MAX_CONFIG_BYTES:
        raise KernelLoadError("PKLOAD1 config marker exceeds its byte bound")
    if not 1 <= config_entries <= native_boot_config.MAX_ENTRIES:
        raise KernelLoadError("PKLOAD1 config marker exceeds its entry bound")
    if timeout_ms > native_boot_config.MAX_TIMEOUT_MS or not 1 <= attempts <= 8 or not 1 <= slot <= 4:
        raise KernelLoadError("PKLOAD1 config marker exceeds its policy bounds")
    if not 1 <= manifest_max <= native_boot_config.MAX_MANIFEST_BYTES:
        raise KernelLoadError("PKLOAD1 config marker exceeds its manifest bound")

    kernel_file_bytes = int(matches[8].group(1))
    image_bytes = int(matches[9].group(1))
    pages = int(matches[9].group(2))
    entry_offset = int(matches[9].group(3))
    relocations = int(matches[9].group(4))
    if not 1 <= kernel_file_bytes <= native_elf_loader.MAX_FILE_BYTES:
        raise KernelLoadError("PKLOAD1 kernel marker exceeds its file bound")
    if not 1 <= image_bytes <= native_elf_loader.MAX_IMAGE_BYTES:
        raise KernelLoadError("PKLOAD1 kernel marker exceeds its image bound")
    if pages <= 0 or pages * native_elf_loader.PAGE_SIZE != image_bytes:
        raise KernelLoadError("PKLOAD1 marker page math is inconsistent")
    if not 0 <= entry_offset < image_bytes or relocations > native_elf_loader.MAX_RELOCATIONS:
        raise KernelLoadError("PKLOAD1 entry or relocation marker exceeds its bound")

    mappings = int(matches[10].group(1))
    read_execute = int(matches[10].group(2))
    read_write = int(matches[10].group(3))
    writable_executable = int(matches[10].group(4))
    if (mappings, read_execute, read_write, writable_executable) != (4, 1, 1, 0):
        raise KernelLoadError("PKLOAD1 mapping marker violates W^X or shape")
    if (
        int(matches[11].group(1)),
        int(matches[11].group(2)),
        int(matches[11].group(3)),
    ) != (3, 2, pages):
        raise KernelLoadError("PKLOAD1 release marker does not account for every resource")

    config_table_count = int(matches[5].group(1))
    width = int(matches[12].group(1))
    height = int(matches[12].group(2))
    stride = int(matches[12].group(3))
    map_bytes = int(matches[13].group(1))
    descriptor_bytes = int(matches[13].group(2))
    descriptor_count = int(matches[13].group(3))
    if config_table_count > 256:
        raise KernelLoadError("configuration-table marker exceeds its bound")
    if width < 320 or height < 200 or stride < width or stride > 16_384:
        raise KernelLoadError("GOP marker geometry is outside its bound")
    if descriptor_bytes < 40 or descriptor_bytes > 256 or descriptor_bytes % 8:
        raise KernelLoadError("memory-map descriptor marker is outside its bound")
    if map_bytes != descriptor_bytes * descriptor_count or map_bytes > 1024 * 1024:
        raise KernelLoadError("memory-map marker shape is inconsistent")
    return {
        "marker_count": len(markers),
        "ordered_contract_match": True,
        "config_table_count": config_table_count,
        "boot_config": {
            "byte_count": config_bytes,
            "entry_count": config_entries,
            "default_entry_hash": matches[7].group(3),
            "timeout_ms": timeout_ms,
            "boot_attempt_limit": attempts,
            "selected_slot": slot,
            "manifest_max_bytes": manifest_max,
        },
        "kernel": {
            "file_byte_count": kernel_file_bytes,
            "image_byte_count": image_bytes,
            "page_count": pages,
            "entry_offset": entry_offset,
            "relocation_count": relocations,
            "loaded_fnv1a64": matches[9].group(5),
            "mapping_count": mappings,
            "read_execute_count": read_execute,
            "read_write_count": read_write,
            "writable_executable_count": writable_executable,
            "resources_released": True,
        },
        "gop": {
            "width": width,
            "height": height,
            "stride": stride,
            "mode": int(matches[12].group(4)),
            "format": matches[12].group(5),
        },
        "memory_map": {
            "byte_count": map_bytes,
            "descriptor_bytes": descriptor_bytes,
            "descriptor_count": descriptor_count,
        },
    }


def validate_oracle_binding(
    marker_summary: dict[str, Any],
    media_inspection: dict[str, Any],
) -> None:
    config = marker_summary["boot_config"]
    media_config = media_inspection["config"]
    config_file = media_inspection["files"][1]
    if (
        config["byte_count"] != config_file["byte_count"]
        or config["entry_count"] != media_config["entry_count"]
        or config["default_entry_hash"] != media_config["default_entry_hash"]
        or config["timeout_ms"] != media_config["timeout_ms"]
        or config["boot_attempt_limit"] != media_config["boot_attempt_limit"]
        or config["selected_slot"] != media_config["selected_slot"]
        or config["manifest_max_bytes"] != media_config["manifest_max_bytes"]
    ):
        raise KernelLoadError("firmware PBC1 markers diverge from the independent media oracle")
    kernel = marker_summary["kernel"]
    media_kernel = media_inspection["kernel"]
    kernel_file = media_inspection["files"][2]
    plan = media_kernel["plan"]
    if (
        kernel["file_byte_count"] != kernel_file["byte_count"]
        or kernel["image_byte_count"] != plan["image_size"]
        or kernel["entry_offset"] != plan["entry_offset"]
        or kernel["relocation_count"] != plan["relocation_count"]
        or kernel["loaded_fnv1a64"] != media_kernel["loaded_fnv1a64"]
    ):
        raise KernelLoadError("firmware PKELF1 markers diverge from the independent media oracle")


def expected_claims() -> dict[str, bool]:
    return {
        **{name: True for name in TRUE_CLAIMS},
        **{name: False for name in FALSE_CLAIMS},
    }


def validate_claims(claims: dict[str, Any]) -> None:
    expected = expected_claims()
    if claims != expected:
        raise KernelLoadError("PKLOAD1 claim set contains an omission or overreach")


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(
        "ascii"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelLoadError(f"JSON root must be an object: {path.name}")
    return value


def file_binding(root: Path, relative_path: str) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise KernelLoadError(f"binding escapes repository root: {relative_path}") from error
    data = path.read_bytes()
    return {
        "path": relative_path.replace("\\", "/"),
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
    }


def binding_matches(binding: Any, root: Path, expected_path: str) -> bool:
    if not isinstance(binding, dict) or binding.get("path") != expected_path:
        return False
    try:
        return binding == file_binding(root, expected_path)
    except (OSError, KernelLoadError):
        return False


def _schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    schema = read_json(root / schema_relative)
    return [f"schema {item.path}: {item.message}" for item in validate_json(value, schema)]


def contract_errors(contract: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(contract, root, CONTRACT_SCHEMA_RELATIVE)
    if contract.get("phase_mapping") != ["N5.1", "N5.4", "N5.5"]:
        errors.append("PKLOAD1 phase mapping changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKLOAD1 negative-control register changed")
    if contract.get("required_marker_count") != len(MARKER_PATTERNS):
        errors.append("PKLOAD1 marker count changed")
    media = contract.get("media", {})
    if media.get("config_path") != CONFIG_PATH or media.get("kernel_path") != KERNEL_PATH:
        errors.append("PKLOAD1 fixed development paths changed")
    try:
        validate_claims(contract.get("claims", {}))
    except KernelLoadError as error:
        errors.append(str(error))
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
    except (OSError, json.JSONDecodeError, KernelLoadError) as error:
        return errors + [f"PKLOAD1 contract cannot be read: {error}"]
    errors.extend(contract_errors(contract, root))
    bindings = readiness.get("bindings", {})
    expected_bindings = {
        "contract": CONTRACT_RELATIVE,
        "toolchain_lock": "specs/native-toolchain-lock.json",
        "toolchain_qualification": "runs/native_toolchain_qualification.json",
        "tier0_lock": "specs/native-tier0-lock.json",
        "tier0_profile": "specs/native-tier0-profile.json",
        "tier0_readiness": "runs/native_tier0_readiness.json",
        "kernel_entry_contract": "specs/native-kernel-entry-contract.json",
        "kernel_entry_readiness": "runs/native_kernel_entry_readiness.json",
    }
    for name, path in expected_bindings.items():
        if not binding_matches(bindings.get(name), root, path):
            errors.append(f"stale {name} binding")
    implementation = bindings.get("implementation_inputs", [])
    if not isinstance(implementation, list) or [
        item.get("path") for item in implementation if isinstance(item, dict)
    ] != list(IMPLEMENTATION_INPUTS):
        errors.append("PKLOAD1 implementation-input order changed")
    else:
        for item, path in zip(implementation, IMPLEMENTATION_INPUTS, strict=True):
            if not binding_matches(item, root, path):
                errors.append(f"stale implementation input {path}")

    media = readiness.get("media", {}).get("inspection", {})
    files = media.get("files", [])
    build = readiness.get("build", {})
    kernel_product = readiness.get("kernel_product", {})
    if not isinstance(files, list) or len(files) != 3:
        errors.append("PKLOAD1 media must contain exactly three files")
    else:
        expected_paths = [native_pooleboot.FALLBACK_PATH, CONFIG_PATH, KERNEL_PATH]
        if [item.get("path") for item in files] != expected_paths:
            errors.append("PKLOAD1 media path order changed")
        if files[0].get("sha256") != build.get("sha256"):
            errors.append("embedded PooleBoot does not match its build")
        if files[2].get("sha256") != kernel_product.get("canonical_sha256"):
            errors.append("embedded PooleKernel does not match PKENTRY1")
    runs = readiness.get("execution", {}).get("runs", [])
    marker_sets: list[list[str]] = []
    if not isinstance(runs, list) or len(runs) != 2:
        errors.append("PKLOAD1 execution must contain exactly two runs")
    else:
        for index, run in enumerate(runs):
            try:
                summary = validate_markers(run.get("markers", []))
                validate_oracle_binding(summary, media)
            except (KernelLoadError, KeyError, TypeError) as error:
                errors.append(f"PKLOAD1 run {index} validation failed: {error}")
                continue
            marker_sets.append(run["markers"])
            if run.get("marker_summary") != summary:
                errors.append(f"PKLOAD1 run {index} marker summary changed")
            if run.get("marker_sha256") != sha256_bytes(
                native_pooleboot.canonical_json_bytes(run["markers"])
            ):
                errors.append(f"PKLOAD1 run {index} marker digest changed")
    if len(marker_sets) == 2 and marker_sets[0] != marker_sets[1]:
        errors.append("PKLOAD1 run markers differ")

    execution = readiness.get("execution", {})
    normalized = execution.get("normalized_command", [])
    if execution.get("normalized_command_sha256") != sha256_bytes(
        native_pooleboot.canonical_json_bytes(normalized)
    ):
        errors.append("PKLOAD1 normalized command digest mismatch")

    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(
        NEGATIVE_CONTROL_IDS
    ):
        errors.append("PKLOAD1 readiness negative-control register changed")
    if any(
        item.get("expected") != "reject"
        or item.get("observed") != "reject"
        or item.get("status") != "pass"
        for item in controls
        if isinstance(item, dict)
    ):
        errors.append("PKLOAD1 readiness has a failing negative control")
    try:
        validate_claims(readiness.get("claims", {}))
    except KernelLoadError as error:
        errors.append(str(error))
    if readiness.get("claim_boundary") != contract.get("claim_boundary"):
        errors.append("PKLOAD1 readiness claim boundary differs from its contract")
    if native_pooleboot.ABSOLUTE_USER_PATH.search(json.dumps(readiness, ensure_ascii=True)):
        errors.append("absolute user path leaked into PKLOAD1 readiness")
    return errors
