"""Independent Python oracle for the canonical Poole Boot Protocol PBP1 bytes."""

from __future__ import annotations

import binascii
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("specs/native-boot-handoff-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-boot-handoff-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-boot-handoff-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-boot-handoff-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_boot_handoff_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-boot-handoff-readiness.schema.json")

MAGIC = b"PBP1\r\n\x1a\n"
MAJOR = 1
MINOR = 0
HEADER_BYTES = 64
DESCRIPTOR_BYTES = 32
ALIGNMENT = 8
MAX_TOTAL_BYTES = 1024 * 1024
MAX_RECORDS = 32
PAGE_BYTES = 4096

RECORD_CORE = 1
RECORD_MEMORY_MAP = 2
RECORD_FRAMEBUFFER = 3
RECORD_FIRMWARE_TABLES = 4
RECORD_LOADED_ARTIFACTS = 5
RECORD_COMMAND_LINE = 6
RECORD_BOOT_DEVICE = 7
RECORD_RANDOM_SEED = 8
RECORD_EARLY_LOG = 9
RECORD_CPU_BOOTSTRAP = 10
RECORD_BOOT_TIMESTAMPS = 11
RECORD_TCG_EVENT_LOG = 12
FIRST_EXTENSION_RECORD = 0x8000

FEATURE_CORE = 1 << 0
FEATURE_MEMORY_MAP = 1 << 1
FEATURE_FRAMEBUFFER = 1 << 2
FEATURE_FIRMWARE_TABLES = 1 << 3
FEATURE_LOADED_ARTIFACTS = 1 << 4
FEATURE_COMMAND_LINE = 1 << 5
FEATURE_BOOT_DEVICE = 1 << 6
FEATURE_RANDOM_SEED = 1 << 7
FEATURE_EARLY_LOG = 1 << 8
FEATURE_CPU_BOOTSTRAP = 1 << 9
FEATURE_BOOT_TIMESTAMPS = 1 << 10
FEATURE_TCG_EVENT_LOG = 1 << 11
KNOWN_FEATURES = (1 << 12) - 1
BASE_REQUIRED_FEATURES = FEATURE_CORE | FEATURE_MEMORY_MAP
KERNEL_ENTRY_REQUIRED_FEATURES = (
    FEATURE_CORE
    | FEATURE_MEMORY_MAP
    | FEATURE_FIRMWARE_TABLES
    | FEATURE_LOADED_ARTIFACTS
    | FEATURE_BOOT_DEVICE
    | FEATURE_RANDOM_SEED
    | FEATURE_CPU_BOOTSTRAP
)

RECORD_REQUIRED = 1 << 0
RECORD_ARRAY = 1 << 1
RECORD_REDACT = 1 << 2
KNOWN_RECORD_FLAGS = (1 << 3) - 1

BOOT_SERVICES_EXITED = 1 << 0
SECURE_BOOT_ENABLED = 1 << 1
SECURE_BOOT_VERIFIED = 1 << 2
MEASURED_BOOT_ACTIVE = 1 << 3
DEVELOPMENT_MODE = 1 << 4
RECOVERY_MODE = 1 << 5
SAFE_MODE = 1 << 6
RUNTIME_SERVICES_RETAINED = 1 << 7
KNOWN_BOOT_FLAGS = (1 << 8) - 1

ARTIFACT_KERNEL = 1
ARTIFACT_INITIAL_SYSTEM = 2
ARTIFACT_RECOVERY = 3
ARTIFACT_SYMBOLS = 4
ARTIFACT_MICROCODE = 5
ARTIFACT_FIRMWARE_MANIFEST = 6
ARTIFACT_POLICY_BUNDLE = 7
ARTIFACT_CRASH_KERNEL = 8
ARTIFACT_HASH_VERIFIED = 1 << 0
ARTIFACT_SIGNATURE_VERIFIED = 1 << 1
ARTIFACT_MEASURED = 1 << 2
ARTIFACT_EXECUTABLE = 1 << 3
ARTIFACT_WRITABLE = 1 << 4
KNOWN_ARTIFACT_FLAGS = (1 << 5) - 1

MEMORY_RESERVED = 0
MEMORY_USABLE = 1
MEMORY_BOOT_RECLAIMABLE = 2
MEMORY_RUNTIME_CODE = 3
MEMORY_RUNTIME_DATA = 4
MEMORY_ACPI_RECLAIMABLE = 5
MEMORY_ACPI_NVS = 6
MEMORY_MMIO = 7
MEMORY_PERSISTENT = 8
MEMORY_UNUSABLE = 9
MEMORY_LOADER_RESERVED = 10
MEMORY_FRAMEBUFFER = 11

CORE_BYTES = 128
MEMORY_ENTRY_BYTES = 40
FRAMEBUFFER_BYTES = 48
FIRMWARE_TABLE_ENTRY_BYTES = 40
ARTIFACT_ENTRY_BYTES = 80
BOOT_DEVICE_BYTES = 96
RANDOM_SEED_BYTES = 72
EARLY_LOG_HEADER_BYTES = 16
CPU_BOOTSTRAP_BYTES = 64
BOOT_TIMESTAMPS_BYTES = 48
TCG_EVENT_LOG_BYTES = 56

NEGATIVE_CONTROL_IDS = (
    "NEG-N5-PBP1-MAGIC",
    "NEG-N5-PBP1-MAJOR-DOWNGRADE",
    "NEG-N5-PBP1-MAJOR-FUTURE",
    "NEG-N5-PBP1-READER-MINOR",
    "NEG-N5-PBP1-HEADER-SIZE",
    "NEG-N5-PBP1-TOTAL-SIZE",
    "NEG-N5-PBP1-HEADER-FLAGS",
    "NEG-N5-PBP1-HEADER-RESERVED",
    "NEG-N5-PBP1-MESSAGE-CRC",
    "NEG-N5-PBP1-RECORD-ORDER",
    "NEG-N5-PBP1-RECORD-OFFSET",
    "NEG-N5-PBP1-RECORD-LENGTH",
    "NEG-N5-PBP1-RECORD-CRC",
    "NEG-N5-PBP1-RECORD-FLAGS",
    "NEG-N5-PBP1-UNKNOWN-REQUIRED",
    "NEG-N5-PBP1-UNKNOWN-SAME-MINOR",
    "NEG-N5-PBP1-UNKNOWN-REQUIRED-FEATURE",
    "NEG-N5-PBP1-MISSING-CORE",
    "NEG-N5-PBP1-MEMORY-OVERLAP",
    "NEG-N5-PBP1-MEMORY-ZERO-PAGES",
    "NEG-N5-PBP1-FRAMEBUFFER-STRIDE",
    "NEG-N5-PBP1-FIRMWARE-DUPLICATE",
    "NEG-N5-PBP1-ARTIFACT-DIGEST",
    "NEG-N5-PBP1-KERNEL-CROSS-BINDING",
    "NEG-N5-PBP1-COMMAND-UTF8",
    "NEG-N5-PBP1-BOOT-DEVICE-RANGE",
    "NEG-N5-PBP1-RANDOM-ZERO",
    "NEG-N5-PBP1-EARLY-LOG-UTF8",
    "NEG-N5-PBP1-CPU-PAGE-SIZE",
    "NEG-N5-PBP1-TIMESTAMP-ORDER",
    "NEG-N5-PBP1-TCG-DIGEST",
    "NEG-N5-PBP1-KERNEL-PROFILE-EBS",
)

IMPLEMENTATION_INPUTS = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/handoff/Cargo.toml",
    "native/handoff/README.md",
    "native/handoff/src/lib.rs",
    "native/handoff/src/bin/pbp1_probe.rs",
    "runtime/native_boot_handoff.py",
    "tools/generate_native_boot_handoff_vectors.py",
    "tools/qualify_native_boot_handoff.py",
    "tests/test_native_boot_handoff.py",
    "docs/native-boot-handoff.md",
)


class BootHandoffError(ValueError):
    """Raised when PBP1 bytes or their public evidence fail closed."""


@dataclass(frozen=True)
class Record:
    record_type: int
    revision: int
    flags: int
    offset: int
    length: int
    element_size: int
    element_count: int
    content_crc32: int
    payload: bytes


@dataclass(frozen=True)
class Handoff:
    data: bytes
    writer_major: int
    writer_minor: int
    minimum_reader_minor: int
    total_size: int
    features: int
    required_features: int
    records: tuple[Record, ...]

    def record(self, record_type: int) -> Record | None:
        return next((item for item in self.records if item.record_type == record_type), None)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise BootHandoffError(f"JSON object required: {path.name}")
    return value


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise BootHandoffError("binding path escapes the repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def _align(value: int) -> int:
    return (value + ALIGNMENT - 1) & ~(ALIGNMENT - 1)


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise BootHandoffError("buffer too small")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise BootHandoffError("buffer too small")
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 8 > len(data):
        raise BootHandoffError("buffer too small")
    return struct.unpack_from("<Q", data, offset)[0]


def _crc32(data: bytes) -> int:
    return binascii.crc32(data) & 0xFFFF_FFFF


def _message_crc(data: bytes) -> int:
    copy = bytearray(data)
    if len(copy) >= 52:
        copy[48:52] = b"\0" * 4
    return _crc32(bytes(copy))


def _feature_for(record_type: int) -> int:
    return 1 << (record_type - 1) if RECORD_CORE <= record_type <= RECORD_TCG_EVENT_LOG else 0


def _structural_flags(record_type: int) -> int:
    if record_type in {RECORD_MEMORY_MAP, RECORD_FIRMWARE_TABLES, RECORD_LOADED_ARTIFACTS}:
        return RECORD_ARRAY
    if record_type == RECORD_RANDOM_SEED:
        return RECORD_REDACT
    return 0


def _range_end(start: int, size: int) -> int:
    if not 0 < size <= 0xFFFF_FFFF_FFFF_FFFF or not 0 <= start <= 0xFFFF_FFFF_FFFF_FFFF:
        raise BootHandoffError("invalid address range")
    end = start + size
    if end > 0xFFFF_FFFF_FFFF_FFFF:
        raise BootHandoffError("address range overflow")
    return end


def _validate_core(payload: bytes, total_size: int | None) -> dict[str, int]:
    if len(payload) != CORE_BYTES or _u32(payload, 124) != 0:
        raise BootHandoffError("core shape")
    names = (
        "boot_flags",
        "kernel_physical_base",
        "kernel_physical_size",
        "kernel_virtual_base",
        "kernel_virtual_size",
        "kernel_entry_virtual",
        "initial_stack_top_virtual",
        "page_table_root_physical",
        "handoff_physical_base",
        "handoff_virtual_base",
        "handoff_byte_count",
        "uefi_system_table_physical",
        "uefi_runtime_services_physical",
    )
    core = {name: _u64(payload, index * 8) for index, name in enumerate(names)}
    core.update(
        boot_attempt=_u32(payload, 104),
        boot_attempt_limit=_u32(payload, 108),
        boot_slot=_u32(payload, 112),
        selected_entry=_u32(payload, 116),
        uefi_revision=_u32(payload, 120),
    )
    if (
        core["boot_flags"] & ~KNOWN_BOOT_FLAGS
        or core["kernel_physical_base"] % PAGE_BYTES
        or core["kernel_virtual_base"] % PAGE_BYTES
        or not core["page_table_root_physical"]
        or core["page_table_root_physical"] % PAGE_BYTES
        or not core["handoff_physical_base"]
        or core["handoff_physical_base"] % ALIGNMENT
        or not core["handoff_virtual_base"]
        or core["handoff_virtual_base"] % ALIGNMENT
        or not core["initial_stack_top_virtual"]
        or core["initial_stack_top_virtual"] % 16
        or not 1 <= core["boot_attempt_limit"] <= 32
        or core["boot_attempt"] > core["boot_attempt_limit"]
        or core["boot_slot"] not in {1, 2, 3, 4}
        or not core["selected_entry"]
        or not core["uefi_revision"]
    ):
        raise BootHandoffError("core value")
    _range_end(core["kernel_physical_base"], core["kernel_physical_size"])
    virtual_end = _range_end(core["kernel_virtual_base"], core["kernel_virtual_size"])
    if not core["kernel_virtual_base"] <= core["kernel_entry_virtual"] < virtual_end:
        raise BootHandoffError("kernel entry range")
    _range_end(core["handoff_physical_base"], core["handoff_byte_count"])
    _range_end(core["handoff_virtual_base"], core["handoff_byte_count"])
    if total_size is not None and core["handoff_byte_count"] != total_size:
        raise BootHandoffError("handoff size cross-binding")
    if core["boot_flags"] & SECURE_BOOT_VERIFIED and not core["boot_flags"] & SECURE_BOOT_ENABLED:
        raise BootHandoffError("secure boot state")
    retained = bool(core["boot_flags"] & RUNTIME_SERVICES_RETAINED)
    system_table = core["uefi_system_table_physical"]
    runtime_services = core["uefi_runtime_services_physical"]
    if retained:
        if not system_table or not runtime_services:
            raise BootHandoffError("runtime service pointer state")
    elif system_table or runtime_services:
        raise BootHandoffError("runtime service pointer state")
    return core


def _validate_memory_map(payload: bytes, count: int) -> None:
    if not 1 <= count <= 16_384 or len(payload) != count * MEMORY_ENTRY_BYTES:
        raise BootHandoffError("memory map shape")
    previous_end = 0
    for index in range(count):
        base = index * MEMORY_ENTRY_BYTES
        start, pages, _attributes = struct.unpack_from("<QQQ", payload, base)
        kind = _u32(payload, base + 24)
        if _u64(payload, base + 32) or start % PAGE_BYTES or not pages or kind > MEMORY_FRAMEBUFFER:
            raise BootHandoffError("memory map value")
        end = _range_end(start, pages * PAGE_BYTES)
        if index and start < previous_end:
            raise BootHandoffError("memory map overlap")
        previous_end = end


def _validate_framebuffer(payload: bytes) -> None:
    if len(payload) != FRAMEBUFFER_BYTES:
        raise BootHandoffError("framebuffer shape")
    base, size, width, height, stride, pixel_format, red, green, blue, reserved = struct.unpack(
        "<QQIIIIIIII", payload
    )
    if (
        not base
        or base & 3
        or not 320 <= width <= 16_384
        or not 200 <= height <= 16_384
        or not width <= stride <= 16_384
        or pixel_format not in {1, 2, 3}
    ):
        raise BootHandoffError("framebuffer value")
    needed = stride * height * 4
    if size < needed or size > 512 * 1024 * 1024:
        raise BootHandoffError("framebuffer range")
    _range_end(base, size)
    masks = (red, green, blue, reserved)
    if pixel_format == 1 and masks != (0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000):
        raise BootHandoffError("RGB masks")
    if pixel_format == 2 and masks != (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000):
        raise BootHandoffError("BGR masks")
    if pixel_format == 3 and (
        not red
        or not green
        or not blue
        or red & green
        or red & blue
        or green & blue
        or reserved & (red | green | blue)
    ):
        raise BootHandoffError("bitmask overlap")


def _validate_firmware(payload: bytes, count: int) -> None:
    if not 1 <= count <= 64 or len(payload) != count * FIRMWARE_TABLE_ENTRY_BYTES:
        raise BootHandoffError("firmware table shape")
    previous = b""
    for index in range(count):
        base = index * FIRMWARE_TABLE_ENTRY_BYTES
        guid = payload[base : base + 16]
        address, size, flags, reserved = struct.unpack_from("<QQII", payload, base + 16)
        if (
            not any(guid)
            or not address
            or address % 8
            or not 0 < size <= 16 * 1024 * 1024
            or flags & ~0x7
            or reserved
            or previous >= guid
        ):
            raise BootHandoffError("firmware table value")
        _range_end(address, size)
        previous = guid


def _validate_artifacts(payload: bytes, count: int) -> None:
    if not 1 <= count <= 64 or len(payload) != count * ARTIFACT_ENTRY_BYTES:
        raise BootHandoffError("artifact shape")
    previous_role = 0
    for index in range(count):
        base = index * ARTIFACT_ENTRY_BYTES
        role, flags = struct.unpack_from("<II", payload, base)
        physical, size, virtual_start, virtual_size, entry = struct.unpack_from("<QQQQQ", payload, base + 8)
        digest = payload[base + 48 : base + 80]
        if (
            not 1 <= role <= ARTIFACT_CRASH_KERNEL
            or role <= previous_role
            or flags & ~KNOWN_ARTIFACT_FLAGS
            or not physical
            or physical % PAGE_BYTES
            or not size
            or not any(digest)
        ):
            raise BootHandoffError("artifact value")
        _range_end(physical, size)
        if flags & ARTIFACT_EXECUTABLE:
            end = _range_end(virtual_start, virtual_size)
            if not virtual_start or virtual_start % PAGE_BYTES or not virtual_start <= entry < end:
                raise BootHandoffError("artifact executable range")
        elif entry or bool(virtual_start) != bool(virtual_size):
            raise BootHandoffError("artifact non-executable range")
        previous_role = role


def _validate_command(payload: bytes) -> None:
    if not 1 <= len(payload) <= 4096:
        raise BootHandoffError("command shape")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BootHandoffError("command UTF-8") from error
    if any(character in "\0\r\n" or (ord(character) < 32 and character != "\t") for character in text):
        raise BootHandoffError("command control character")


def _validate_boot_device(payload: bytes) -> None:
    if len(payload) != BOOT_DEVICE_BYTES:
        raise BootHandoffError("boot device shape")
    start, size, block_size, flags = struct.unpack_from("<QQII", payload, 32)
    if (
        not any(payload[0:16])
        or not any(payload[16:32])
        or not size
        or start + size > 0xFFFF_FFFF_FFFF_FFFF
        or not 512 <= block_size <= 65_536
        or block_size & (block_size - 1)
        or flags & ~0x3
        or not any(payload[56:88])
        or any(payload[88:96])
    ):
        raise BootHandoffError("boot device value")


def _validate_random(payload: bytes) -> None:
    if len(payload) != RANDOM_SEED_BYTES:
        raise BootHandoffError("random seed shape")
    quality, sources = struct.unpack_from("<II", payload)
    if quality > 3 or sources & ~0xF or (quality and not any(payload[8:72])):
        raise BootHandoffError("random seed value")


def _validate_early_log(payload: bytes) -> None:
    if not EARLY_LOG_HEADER_BYTES <= len(payload) <= EARLY_LOG_HEADER_BYTES + 65_536:
        raise BootHandoffError("early log shape")
    if _u16(payload, 12) != 1 or _u16(payload, 14):
        raise BootHandoffError("early log header")
    try:
        payload[16:].decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BootHandoffError("early log UTF-8") from error


def _validate_cpu(payload: bytes) -> None:
    if len(payload) != CPU_BOOTSTRAP_BYTES:
        raise BootHandoffError("CPU bootstrap shape")
    flags = _u32(payload, 4)
    physical_bits, virtual_bits = struct.unpack_from("<HH", payload, 8)
    stack_bottom, stack_size = struct.unpack_from("<QQ", payload, 16)
    page_levels, page_size = struct.unpack_from("<II", payload, 32)
    if (
        flags & ~0x3
        or not 36 <= physical_bits <= 64
        or not 48 <= virtual_bits <= 64
        or not stack_bottom
        or stack_bottom % 16
        or stack_size < PAGE_BYTES
        or stack_size % PAGE_BYTES
        or page_levels not in {4, 5}
        or page_size != PAGE_BYTES
        or any(payload[40:64])
    ):
        raise BootHandoffError("CPU bootstrap value")
    _range_end(stack_bottom, stack_size)


def _validate_timestamps(payload: bytes) -> None:
    if len(payload) != BOOT_TIMESTAMPS_BYTES:
        raise BootHandoffError("timestamp shape")
    flags, _monotonic, start, handoff, frequency, _wallclock = struct.unpack("<QQQQQQ", payload)
    if flags & ~0x7 or start > handoff or ((start or handoff) and not frequency):
        raise BootHandoffError("timestamp value")


def _validate_tcg(payload: bytes) -> None:
    if len(payload) != TCG_EVENT_LOG_BYTES:
        raise BootHandoffError("TCG shape")
    physical, size, event_format, flags = struct.unpack_from("<QQII", payload)
    if (
        not physical
        or physical % 8
        or not 0 < size <= 16 * 1024 * 1024
        or event_format not in {1, 2}
        or flags & ~0x3
        or not any(payload[24:56])
    ):
        raise BootHandoffError("TCG value")
    _range_end(physical, size)


def _validate_payload(record: Record, total_size: int | None) -> None:
    if record.flags & ~KNOWN_RECORD_FLAGS:
        raise BootHandoffError("record flags")
    known = record.record_type <= RECORD_TCG_EVENT_LOG
    if known:
        if record.revision != 1 or record.flags & (RECORD_ARRAY | RECORD_REDACT) != _structural_flags(record.record_type):
            raise BootHandoffError("known record metadata")
    elif record.record_type < FIRST_EXTENSION_RECORD or not record.revision or record.flags & RECORD_REQUIRED:
        raise BootHandoffError("unknown required record")
    if record.flags & RECORD_ARRAY:
        if (
            not record.element_size
            or not record.element_count
            or record.element_size * record.element_count != len(record.payload)
        ):
            raise BootHandoffError("array shape")
    else:
        variable = record.record_type in {RECORD_COMMAND_LINE, RECORD_EARLY_LOG} or record.record_type >= FIRST_EXTENSION_RECORD
        if variable and (record.element_size or record.element_count):
            raise BootHandoffError("variable record shape")
        if not variable and (record.element_count != 1 or record.element_size != len(record.payload)):
            raise BootHandoffError("singleton shape")
    validators = {
        RECORD_CORE: lambda: _validate_core(record.payload, total_size),
        RECORD_MEMORY_MAP: lambda: _validate_memory_map(record.payload, record.element_count),
        RECORD_FRAMEBUFFER: lambda: _validate_framebuffer(record.payload),
        RECORD_FIRMWARE_TABLES: lambda: _validate_firmware(record.payload, record.element_count),
        RECORD_LOADED_ARTIFACTS: lambda: _validate_artifacts(record.payload, record.element_count),
        RECORD_COMMAND_LINE: lambda: _validate_command(record.payload),
        RECORD_BOOT_DEVICE: lambda: _validate_boot_device(record.payload),
        RECORD_RANDOM_SEED: lambda: _validate_random(record.payload),
        RECORD_EARLY_LOG: lambda: _validate_early_log(record.payload),
        RECORD_CPU_BOOTSTRAP: lambda: _validate_cpu(record.payload),
        RECORD_BOOT_TIMESTAMPS: lambda: _validate_timestamps(record.payload),
        RECORD_TCG_EVENT_LOG: lambda: _validate_tcg(record.payload),
    }
    if record.record_type == RECORD_MEMORY_MAP and record.element_size != MEMORY_ENTRY_BYTES:
        raise BootHandoffError("memory element size")
    if record.record_type == RECORD_FIRMWARE_TABLES and record.element_size != FIRMWARE_TABLE_ENTRY_BYTES:
        raise BootHandoffError("firmware element size")
    if record.record_type == RECORD_LOADED_ARTIFACTS and record.element_size != ARTIFACT_ENTRY_BYTES:
        raise BootHandoffError("artifact element size")
    validator = validators.get(record.record_type)
    if validator:
        validator()


def decode(data: bytes) -> Handoff:
    if len(data) < HEADER_BYTES:
        raise BootHandoffError("buffer too small")
    if len(data) > MAX_TOTAL_BYTES:
        raise BootHandoffError("total size")
    if data[:8] != MAGIC:
        raise BootHandoffError("magic")
    writer_major, writer_minor, minimum_reader_minor, header_size = struct.unpack_from("<HHHH", data, 8)
    total_size, record_count, descriptor_size, table_offset, payload_offset = struct.unpack_from("<IHHII", data, 16)
    features, required_features = struct.unpack_from("<QQ", data, 32)
    if writer_major != MAJOR:
        raise BootHandoffError("major version")
    if minimum_reader_minor > writer_minor or minimum_reader_minor > MINOR:
        raise BootHandoffError("minor version")
    if total_size != len(data) or total_size > MAX_TOTAL_BYTES:
        raise BootHandoffError("total size")
    if not 2 <= record_count <= MAX_RECORDS:
        raise BootHandoffError("record count")
    expected_payload = _align(HEADER_BYTES + record_count * DESCRIPTOR_BYTES)
    if (
        header_size != HEADER_BYTES
        or descriptor_size != DESCRIPTOR_BYTES
        or table_offset != HEADER_BYTES
        or payload_offset != expected_payload
        or _u32(data, 52)
    ):
        raise BootHandoffError("header layout")
    if _u64(data, 56):
        raise BootHandoffError("header reserved")
    if _message_crc(data) != _u32(data, 48):
        raise BootHandoffError("message checksum")
    if required_features & ~features or required_features & ~KNOWN_FEATURES:
        raise BootHandoffError("required feature")
    if writer_minor == MINOR and features & ~KNOWN_FEATURES:
        raise BootHandoffError("unknown feature")

    records: list[Record] = []
    expected_offset = payload_offset
    previous_type = 0
    observed_features = 0
    observed_required = 0
    for index in range(record_count):
        base = HEADER_BYTES + index * DESCRIPTOR_BYTES
        record_type, revision, flags, offset, length, element_size, element_count, content_crc, reserved = struct.unpack_from(
            "<HHIIIHHIQ", data, base
        )
        if reserved:
            raise BootHandoffError("descriptor reserved")
        if record_type <= previous_type:
            raise BootHandoffError("record order")
        if offset != expected_offset or offset % ALIGNMENT or not length:
            raise BootHandoffError("record layout")
        end = offset + length
        if end > len(data):
            raise BootHandoffError("record range")
        payload = data[offset:end]
        if _crc32(payload) != content_crc:
            raise BootHandoffError("record checksum")
        record = Record(record_type, revision, flags, offset, length, element_size, element_count, content_crc, payload)
        _validate_payload(record, total_size)
        aligned_end = _align(end)
        if aligned_end > total_size or any(data[end:aligned_end]):
            raise BootHandoffError("record padding")
        records.append(record)
        expected_offset = aligned_end
        previous_type = record_type
        feature = _feature_for(record_type)
        observed_features |= feature
        if flags & RECORD_REQUIRED:
            observed_required |= feature
        if record_type >= FIRST_EXTENSION_RECORD and writer_minor <= MINOR:
            raise BootHandoffError("extension minor")
    if expected_offset != total_size:
        raise BootHandoffError("trailing bytes")
    if observed_features != features & KNOWN_FEATURES or observed_required != required_features:
        raise BootHandoffError("feature mismatch")
    if features & BASE_REQUIRED_FEATURES != BASE_REQUIRED_FEATURES or required_features & BASE_REQUIRED_FEATURES != BASE_REQUIRED_FEATURES:
        raise BootHandoffError("missing base records")

    handoff = Handoff(
        data=data,
        writer_major=writer_major,
        writer_minor=writer_minor,
        minimum_reader_minor=minimum_reader_minor,
        total_size=total_size,
        features=features,
        required_features=required_features,
        records=tuple(records),
    )
    _validate_cross_records(handoff)
    return handoff


def _validate_cross_records(handoff: Handoff) -> None:
    core_record = handoff.record(RECORD_CORE)
    if core_record is None:
        raise BootHandoffError("missing core")
    core = _validate_core(core_record.payload, handoff.total_size)
    if core["boot_flags"] & MEASURED_BOOT_ACTIVE and not handoff.features & FEATURE_TCG_EVENT_LOG:
        raise BootHandoffError("measured boot without event log")
    artifacts = handoff.record(RECORD_LOADED_ARTIFACTS)
    if artifacts:
        kernel_found = False
        for index in range(artifacts.element_count):
            base = index * ARTIFACT_ENTRY_BYTES
            if _u32(artifacts.payload, base) == ARTIFACT_KERNEL:
                kernel_found = True
                observed = struct.unpack_from("<QQQQQ", artifacts.payload, base + 8)
                expected = (
                    core["kernel_physical_base"],
                    core["kernel_physical_size"],
                    core["kernel_virtual_base"],
                    core["kernel_virtual_size"],
                    core["kernel_entry_virtual"],
                )
                if observed != expected:
                    raise BootHandoffError("kernel artifact cross-binding")
        if not kernel_found:
            raise BootHandoffError("kernel artifact missing")


def validate_kernel_entry_profile(handoff: Handoff) -> None:
    if (
        handoff.features & KERNEL_ENTRY_REQUIRED_FEATURES != KERNEL_ENTRY_REQUIRED_FEATURES
        or handoff.required_features & KERNEL_ENTRY_REQUIRED_FEATURES != KERNEL_ENTRY_REQUIRED_FEATURES
    ):
        raise BootHandoffError("kernel profile features")
    core_record = handoff.record(RECORD_CORE)
    random_record = handoff.record(RECORD_RANDOM_SEED)
    artifacts = handoff.record(RECORD_LOADED_ARTIFACTS)
    if core_record is None or random_record is None or artifacts is None:
        raise BootHandoffError("kernel profile record")
    core = _validate_core(core_record.payload, handoff.total_size)
    if not core["boot_flags"] & BOOT_SERVICES_EXITED or _u32(random_record.payload, 0) < 2:
        raise BootHandoffError("kernel profile state")
    required_roles = 0
    for index in range(artifacts.element_count):
        base = index * ARTIFACT_ENTRY_BYTES
        role, flags = struct.unpack_from("<II", artifacts.payload, base)
        if role in {ARTIFACT_KERNEL, ARTIFACT_INITIAL_SYSTEM}:
            required_roles |= 1 << (role - 1)
            required_flags = ARTIFACT_HASH_VERIFIED | ARTIFACT_SIGNATURE_VERIFIED
            if flags & required_flags != required_flags:
                raise BootHandoffError("kernel profile artifact verification")
    if required_roles != 0b11:
        raise BootHandoffError("kernel profile artifact roles")


def encoded_size(payload_lengths: Iterable[int]) -> int:
    lengths = tuple(payload_lengths)
    if not 2 <= len(lengths) <= MAX_RECORDS or any(length <= 0 for length in lengths):
        raise BootHandoffError("record count or payload length")
    size = _align(HEADER_BYTES + len(lengths) * DESCRIPTOR_BYTES)
    for length in lengths:
        size = _align(size + length)
    if size > MAX_TOTAL_BYTES:
        raise BootHandoffError("encoded size")
    return size


def encode(records: Iterable[dict[str, Any]], *, writer_minor: int = 0, minimum_reader_minor: int = 0) -> bytes:
    values = tuple(records)
    total = encoded_size(len(item["payload"]) for item in values)
    if minimum_reader_minor > writer_minor or minimum_reader_minor > MINOR:
        raise BootHandoffError("minor version")
    output = bytearray(total)
    output[0:8] = MAGIC
    payload_offset = _align(HEADER_BYTES + len(values) * DESCRIPTOR_BYTES)
    struct.pack_into(
        "<HHHHIHHII",
        output,
        8,
        MAJOR,
        writer_minor,
        minimum_reader_minor,
        HEADER_BYTES,
        total,
        len(values),
        DESCRIPTOR_BYTES,
        HEADER_BYTES,
        payload_offset,
    )
    cursor = payload_offset
    previous_type = 0
    features = 0
    required_features = 0
    for index, source in enumerate(values):
        payload = bytes(source["payload"])
        item = Record(
            int(source["record_type"]),
            int(source.get("revision", 1)),
            int(source.get("flags", 0)),
            cursor,
            len(payload),
            int(source.get("element_size", len(payload))),
            int(source.get("element_count", 1)),
            _crc32(payload),
            payload,
        )
        if item.record_type <= previous_type:
            raise BootHandoffError("record order")
        if item.record_type >= FIRST_EXTENSION_RECORD and writer_minor <= MINOR:
            raise BootHandoffError("extension minor")
        _validate_payload(item, None)
        end = cursor + len(payload)
        output[cursor:end] = payload
        descriptor_offset = HEADER_BYTES + index * DESCRIPTOR_BYTES
        struct.pack_into(
            "<HHIIIHHIQ",
            output,
            descriptor_offset,
            item.record_type,
            item.revision,
            item.flags,
            item.offset,
            item.length,
            item.element_size,
            item.element_count,
            item.content_crc32,
            0,
        )
        feature = _feature_for(item.record_type)
        features |= feature
        if item.flags & RECORD_REQUIRED:
            required_features |= feature
        previous_type = item.record_type
        cursor = _align(end)
    struct.pack_into("<QQ", output, 32, features, required_features)
    struct.pack_into("<I", output, 48, _message_crc(bytes(output)))
    result = bytes(output)
    decode(result)
    return result


def _core_payload(total: int, boot_flags: int) -> bytes:
    values = (
        boot_flags,
        0x0020_0000,
        0x0010_0000,
        0xFFFF_FFFF_8000_0000,
        0x0010_0000,
        0xFFFF_FFFF_8000_1000,
        0xFFFF_FFFF_8020_0000,
        0x003F_0000,
        0x0038_0000,
        0xFFFF_8000_0038_0000,
        total,
        0,
        0,
    )
    return struct.pack("<13Q6I", *values, 1, 3, 1, 1, 0x0002_0064, 0)


def _memory_payload() -> bytes:
    entries = (
        (0x000F_0000, 16, 0, MEMORY_ACPI_RECLAIMABLE, 9, 0),
        (0x0010_0000, 256, 0, MEMORY_USABLE, 7, 0),
        (0x0020_0000, 512, 0, MEMORY_LOADER_RESERVED, 2, 0),
        (0x0040_0000, 4096, 0, MEMORY_USABLE, 7, 0),
        (0x8000_0000, 1000, 0, MEMORY_FRAMEBUFFER, 11, 0),
    )
    return b"".join(struct.pack("<QQQIIQ", *entry) for entry in entries)


def _full_payloads(total: int) -> tuple[dict[str, Any], ...]:
    core = _core_payload(
        total,
        BOOT_SERVICES_EXITED | SECURE_BOOT_ENABLED | SECURE_BOOT_VERIFIED | MEASURED_BOOT_ACTIVE,
    )
    memory = _memory_payload()
    framebuffer = struct.pack(
        "<QQIIIIIIII",
        0x8000_0000,
        4_096_000,
        1280,
        800,
        1280,
        2,
        0x00FF_0000,
        0x0000_FF00,
        0x0000_00FF,
        0xFF00_0000,
    )
    acpi_guid = bytes.fromhex("8868E871E4F111D3BC220080C73C8881")
    smbios_guid = bytes.fromhex("F2FD154497944A2C992EE5BBCF20E394")
    firmware = b"".join(
        (
            struct.pack("<16sQQII", acpi_guid, 0x000F_0000, 36, 0x7, 0),
            struct.pack("<16sQQII", smbios_guid, 0x000F_1000, 24, 0x7, 0),
        )
    )
    verified_exec = ARTIFACT_HASH_VERIFIED | ARTIFACT_SIGNATURE_VERIFIED | ARTIFACT_MEASURED | ARTIFACT_EXECUTABLE
    artifacts = b"".join(
        (
            struct.pack(
                "<IIQQQQQ32s",
                ARTIFACT_KERNEL,
                verified_exec,
                0x0020_0000,
                0x0010_0000,
                0xFFFF_FFFF_8000_0000,
                0x0010_0000,
                0xFFFF_FFFF_8000_1000,
                hashlib.sha256(b"PBP1 synthetic kernel fixture").digest(),
            ),
            struct.pack(
                "<IIQQQQQ32s",
                ARTIFACT_INITIAL_SYSTEM,
                ARTIFACT_HASH_VERIFIED | ARTIFACT_SIGNATURE_VERIFIED | ARTIFACT_MEASURED,
                0x0030_0000,
                0x0004_0000,
                0,
                0,
                0,
                hashlib.sha256(b"PBP1 synthetic initial-system fixture").digest(),
            ),
        )
    )
    command = b"root=poolefs:slot-a quiet"
    boot_device = struct.pack(
        "<16s16sQQII32s8s",
        bytes.fromhex("504F4F4C454F534E8000000000000097"),
        bytes.fromhex("504F4F4C455350008000000000000001"),
        2048,
        131_039,
        512,
        1,
        hashlib.sha256(b"PBP1 synthetic UEFI device path").digest(),
        b"\0" * 8,
    )
    random_seed = struct.pack("<II64s", 3, 0x7, bytes(range(64)))
    log_text = b"POOLEBOOT PBP1 synthetic fixture\n"
    early_log = struct.pack("<QIHH", 4, 0, 1, 0) + log_text
    cpu = struct.pack(
        "<IIHHIQQII24s",
        0,
        0x3,
        52,
        48,
        0,
        0xFFFF_FFFF_801F_0000,
        0x0001_0000,
        4,
        4096,
        b"\0" * 24,
    )
    timestamps = struct.pack("<QQQQQQ", 0x7, 42, 1_000_000, 1_250_000, 1_000_000_000, 1_783_853_200)
    tcg = struct.pack(
        "<QQII32s",
        0x0037_0000,
        0x0001_0000,
        2,
        1,
        hashlib.sha256(b"PBP1 synthetic TCG event log").digest(),
    )
    return (
        {"record_type": RECORD_CORE, "flags": RECORD_REQUIRED, "element_size": CORE_BYTES, "element_count": 1, "payload": core},
        {"record_type": RECORD_MEMORY_MAP, "flags": RECORD_REQUIRED | RECORD_ARRAY, "element_size": MEMORY_ENTRY_BYTES, "element_count": len(memory) // MEMORY_ENTRY_BYTES, "payload": memory},
        {"record_type": RECORD_FRAMEBUFFER, "element_size": FRAMEBUFFER_BYTES, "element_count": 1, "payload": framebuffer},
        {"record_type": RECORD_FIRMWARE_TABLES, "flags": RECORD_REQUIRED | RECORD_ARRAY, "element_size": FIRMWARE_TABLE_ENTRY_BYTES, "element_count": 2, "payload": firmware},
        {"record_type": RECORD_LOADED_ARTIFACTS, "flags": RECORD_REQUIRED | RECORD_ARRAY, "element_size": ARTIFACT_ENTRY_BYTES, "element_count": 2, "payload": artifacts},
        {"record_type": RECORD_COMMAND_LINE, "element_size": 0, "element_count": 0, "payload": command},
        {"record_type": RECORD_BOOT_DEVICE, "flags": RECORD_REQUIRED, "element_size": BOOT_DEVICE_BYTES, "element_count": 1, "payload": boot_device},
        {"record_type": RECORD_RANDOM_SEED, "flags": RECORD_REQUIRED | RECORD_REDACT, "element_size": RANDOM_SEED_BYTES, "element_count": 1, "payload": random_seed},
        {"record_type": RECORD_EARLY_LOG, "element_size": 0, "element_count": 0, "payload": early_log},
        {"record_type": RECORD_CPU_BOOTSTRAP, "flags": RECORD_REQUIRED, "element_size": CPU_BOOTSTRAP_BYTES, "element_count": 1, "payload": cpu},
        {"record_type": RECORD_BOOT_TIMESTAMPS, "element_size": BOOT_TIMESTAMPS_BYTES, "element_count": 1, "payload": timestamps},
        {"record_type": RECORD_TCG_EVENT_LOG, "element_size": TCG_EVENT_LOG_BYTES, "element_count": 1, "payload": tcg},
    )


def build_fixture(vector_id: str) -> bytes:
    memory = _memory_payload()
    if vector_id == "minimal_v1":
        total = encoded_size((CORE_BYTES, len(memory)))
        records = (
            {"record_type": RECORD_CORE, "flags": RECORD_REQUIRED, "element_size": CORE_BYTES, "element_count": 1, "payload": _core_payload(total, BOOT_SERVICES_EXITED)},
            {"record_type": RECORD_MEMORY_MAP, "flags": RECORD_REQUIRED | RECORD_ARRAY, "element_size": MEMORY_ENTRY_BYTES, "element_count": len(memory) // MEMORY_ENTRY_BYTES, "payload": memory},
        )
        return encode(records)
    if vector_id == "forward_optional_v1_1":
        extension = b"future"
        total = encoded_size((CORE_BYTES, len(memory), len(extension)))
        records = (
            {"record_type": RECORD_CORE, "flags": RECORD_REQUIRED, "element_size": CORE_BYTES, "element_count": 1, "payload": _core_payload(total, BOOT_SERVICES_EXITED)},
            {"record_type": RECORD_MEMORY_MAP, "flags": RECORD_REQUIRED | RECORD_ARRAY, "element_size": MEMORY_ENTRY_BYTES, "element_count": len(memory) // MEMORY_ENTRY_BYTES, "payload": memory},
            {"record_type": FIRST_EXTENSION_RECORD, "revision": 1, "element_size": 0, "element_count": 0, "payload": extension},
        )
        return encode(records, writer_minor=1)
    if vector_id == "full_kernel_entry_v1":
        placeholder = _full_payloads(1)
        total = encoded_size(len(item["payload"]) for item in placeholder)
        return encode(_full_payloads(total))
    raise BootHandoffError(f"unknown fixture: {vector_id}")


def make_golden_vectors() -> dict[str, Any]:
    definitions = (
        ("full_kernel_entry_v1", True, "All current known records; synthetic kernel-entry profile."),
        ("minimal_v1", False, "Only the two format-mandatory records; valid but not kernel-entry ready."),
        ("forward_optional_v1_1", False, "Minor 1 optional extension accepted by the minor 0 reader."),
    )
    vectors = []
    for vector_id, kernel_ready, purpose in definitions:
        data = build_fixture(vector_id)
        handoff = decode(data)
        if kernel_ready:
            validate_kernel_entry_profile(handoff)
        else:
            try:
                validate_kernel_entry_profile(handoff)
            except BootHandoffError:
                pass
            else:
                raise BootHandoffError("non-kernel vector unexpectedly satisfies kernel profile")
        vectors.append(
            {
                "id": vector_id,
                "purpose": purpose,
                "writer_major": handoff.writer_major,
                "writer_minor": handoff.writer_minor,
                "minimum_reader_minor": handoff.minimum_reader_minor,
                "record_count": len(handoff.records),
                "byte_count": len(data),
                "sha256": sha256_bytes(data),
                "kernel_entry_profile": kernel_ready,
                "hex": data.hex().upper(),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_boot_handoff_golden_vectors",
        "contract_id": "PBP1",
        "status": "synthetic_non_promoting_golden_bytes",
        "production_ready": False,
        "vectors": vectors,
        "claim_boundary": [
            "Every vector is synthetic protocol data, not a captured firmware-to-kernel transfer.",
            "A kernel-entry-profile vector proves codec agreement only; it does not prove that ExitBootServices occurred or that PooleKernel executed.",
            "Random-seed bytes are deterministic public fixtures and contain no operational entropy or secret material.",
        ],
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors.extend(f"schema {item.path}: {item.message}" for item in validate_json(contract, schema))
    wire = contract.get("wire", {})
    expected_wire = {
        "magic_hex": MAGIC.hex().upper(),
        "major": MAJOR,
        "minor": MINOR,
        "endianness": "little",
        "header_bytes": HEADER_BYTES,
        "descriptor_bytes": DESCRIPTOR_BYTES,
        "alignment_bytes": ALIGNMENT,
        "maximum_total_bytes": MAX_TOTAL_BYTES,
        "maximum_record_count": MAX_RECORDS,
        "message_checksum": "IEEE CRC-32 with header bytes 48..51 zeroed",
        "record_checksum": "IEEE CRC-32 over exact payload bytes",
    }
    if wire != expected_wire:
        errors.append("wire constants changed")
    records = contract.get("records", [])
    expected_types = list(range(RECORD_CORE, RECORD_TCG_EVENT_LOG + 1))
    if [item.get("type") for item in records if isinstance(item, dict)] != expected_types:
        errors.append("known record type set changed")
    expected_sizes = {
        RECORD_CORE: CORE_BYTES,
        RECORD_MEMORY_MAP: MEMORY_ENTRY_BYTES,
        RECORD_FRAMEBUFFER: FRAMEBUFFER_BYTES,
        RECORD_FIRMWARE_TABLES: FIRMWARE_TABLE_ENTRY_BYTES,
        RECORD_LOADED_ARTIFACTS: ARTIFACT_ENTRY_BYTES,
        RECORD_COMMAND_LINE: None,
        RECORD_BOOT_DEVICE: BOOT_DEVICE_BYTES,
        RECORD_RANDOM_SEED: RANDOM_SEED_BYTES,
        RECORD_EARLY_LOG: None,
        RECORD_CPU_BOOTSTRAP: CPU_BOOTSTRAP_BYTES,
        RECORD_BOOT_TIMESTAMPS: BOOT_TIMESTAMPS_BYTES,
        RECORD_TCG_EVENT_LOG: TCG_EVENT_LOG_BYTES,
    }
    for item in records:
        if isinstance(item, dict) and item.get("fixed_or_element_bytes") != expected_sizes.get(item.get("type")):
            errors.append(f"record size changed: {item.get('type')}")
    if contract.get("required_base_features") != ["core", "memory_map"]:
        errors.append("base feature profile changed")
    if contract.get("production_claims") != {
        "schema_defined": True,
        "rust_codec_executed": True,
        "independent_python_codec_executed": True,
        "pooleboot_populates_handoff": False,
        "exit_boot_services_executed": False,
        "poolekernel_consumes_handoff": False,
        "poolekernel_executed": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }:
        errors.append("contract claim boundary changed")
    return errors


def golden_errors(golden: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    schema = read_json(root / GOLDEN_SCHEMA_RELATIVE)
    errors.extend(f"schema {item.path}: {item.message}" for item in validate_json(golden, schema))
    try:
        expected = make_golden_vectors()
    except (BootHandoffError, ValueError, struct.error) as error:
        return errors + [f"unable to construct golden vectors: {error}"]
    if golden != expected:
        errors.append("golden vectors do not reproduce exactly")
    return errors


def expected_claims() -> dict[str, bool]:
    return {
        "canonical_schema_defined": True,
        "rust_no_std_codec_executed": True,
        "independent_python_codec_executed": True,
        "golden_byte_agreement": True,
        "downgrade_controls_executed": True,
        "malformed_corpus_executed": True,
        "deterministic_differential_fuzz_executed": True,
        "pooleboot_populates_handoff": False,
        "exit_boot_services_executed": False,
        "poolekernel_consumes_handoff": False,
        "poolekernel_executed": False,
        "target_firmware_tested": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors.extend(f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema))
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
        golden = read_json(root / GOLDEN_RELATIVE)
    except (OSError, json.JSONDecodeError, BootHandoffError) as error:
        return errors + [f"unable to read bound contract: {error}"]
    errors.extend(f"contract {item}" for item in contract_errors(contract, root))
    errors.extend(f"golden {item}" for item in golden_errors(golden, root))
    bindings = readiness.get("bindings", {})
    expected_bindings = {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "golden_vectors": file_binding(root / GOLDEN_RELATIVE, root),
        "golden_schema": file_binding(root / GOLDEN_SCHEMA_RELATIVE, root),
        "readiness_schema": file_binding(root / READINESS_SCHEMA_RELATIVE, root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }
    if bindings != expected_bindings:
        errors.append("readiness input bindings are stale")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary changed")
    summary = readiness.get("summary", {})
    expected_summary = {
        "rust_host_tests_passed": 8,
        "rust_host_tests_total": 8,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "layout_assertions_passed": 12,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": len(NEGATIVE_CONTROL_IDS),
        "negative_controls_total": len(NEGATIVE_CONTROL_IDS),
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "production_claim_count": 0,
    }
    if summary != expected_summary:
        errors.append("readiness summary changed")
    if readiness.get("production_ready") is not False or readiness.get("n5_exit_gate_satisfied") is not False:
        errors.append("readiness overclaims production or N5 exit")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("negative control register changed")
    if any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("negative control did not pass")
    return errors
