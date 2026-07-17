#!/usr/bin/env python3
"""Independent host oracle for the bounded PKELF1 PooleKernel image profile."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID = "PKELF1"
CONTRACT_RELATIVE = Path("specs/native-elf-loader-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-elf-loader-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-elf-loader-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-elf-loader-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_elf_loader_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-elf-loader-readiness.schema.json")

IMPLEMENTATION_INPUTS = (
    Path("native/elf/Cargo.toml"),
    Path("native/elf/src/lib.rs"),
    Path("native/elf/src/bin/poole_elf_probe.rs"),
    Path("native/Cargo.toml"),
    Path("native/Cargo.lock"),
    Path("native/boot/Cargo.toml"),
    Path("native/boot/src/lib.rs"),
    Path("runtime/native_elf_loader.py"),
    Path("tools/generate_native_elf_loader_vectors.py"),
    Path("tools/qualify_native_elf_loader.py"),
    Path("docs/native-elf-loader.md"),
)

PAGE_SIZE = 4096
VIRTUAL_BASE_ALIGNMENT = 2 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MIN_PHYSICAL_BASE = 0x0010_0000
MAX_PHYSICAL_EXCLUSIVE = 1 << 52
MIN_VIRTUAL_BASE = 0xFFFF_FFFF_8000_0000
MAX_VIRTUAL_EXCLUSIVE = 0xFFFF_FFFF_C000_0000
PROGRAM_HEADER_COUNT = 7
LOAD_SEGMENT_COUNT = 3
MAPPING_COUNT = 4
MAX_RELOCATIONS = 4096

ELF_HEADER_BYTES = 64
PROGRAM_HEADER_BYTES = 56
DYNAMIC_BYTES = 64
RELA_ENTRY_BYTES = 24

PT_LOAD = 1
PT_DYNAMIC = 2
PT_PHDR = 6
PT_GNU_STACK = 0x6474_E551
PT_GNU_RELRO = 0x6474_E552
PF_X = 1
PF_W = 2
PF_R = 4
DT_NULL = 0
DT_RELA = 7
DT_RELASZ = 8
DT_RELAENT = 9
R_X86_64_RELATIVE = 8


class ElfError(ValueError):
    """A stable fail-closed PKELF1 error."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProgramHeader:
    segment_type: int
    flags: int
    offset: int
    virtual_address: int
    physical_address: int
    file_size: int
    memory_size: int
    alignment: int


@dataclass(frozen=True)
class SegmentPlan:
    file_offset: int
    virtual_offset: int
    file_size: int
    memory_size: int
    permissions: str


@dataclass(frozen=True)
class MappingPlan:
    virtual_offset: int
    memory_size: int
    permissions: str


@dataclass(frozen=True)
class ImagePlan:
    file_size: int
    image_size: int
    entry_offset: int
    entry_virtual: int
    entry_physical: int
    physical_base: int
    virtual_base: int
    relocation_count: int
    relro_offset: int
    relro_size: int
    segments: tuple[SegmentPlan, ...]
    mappings: tuple[MappingPlan, ...]
    relocation_address: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "byte_count": len(data),
        "sha256": sha256_bytes(data),
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _checked_add(left: int, right: int, code: str) -> int:
    value = left + right
    if left < 0 or right < 0 or value > 0xFFFF_FFFF_FFFF_FFFF:
        raise ElfError(code)
    return value


def _contains(start: int, size: int, inner_start: int, inner_size: int) -> bool:
    try:
        end = _checked_add(start, size, "arithmetic_overflow")
        inner_end = _checked_add(inner_start, inner_size, "arithmetic_overflow")
    except ElfError:
        return False
    return inner_start >= start and inner_end <= end


def _overlaps(left_start: int, left_size: int, right_start: int, right_size: int) -> bool:
    try:
        left_end = _checked_add(left_start, left_size, "arithmetic_overflow")
        right_end = _checked_add(right_start, right_size, "arithmetic_overflow")
    except ElfError:
        return True
    return left_start < right_end and right_start < left_end


def _unpack(fmt: str, data: bytes, offset: int, code: str) -> tuple[int, ...]:
    try:
        return struct.unpack_from(fmt, data, offset)
    except struct.error as exc:
        raise ElfError(code) from exc


def _program_header(data: bytes, index: int) -> ProgramHeader:
    values = _unpack("<IIQQQQQQ", data, ELF_HEADER_BYTES + index * PROGRAM_HEADER_BYTES, "program_header_bounds")
    return ProgramHeader(*values)


def _validate_header(data: bytes) -> tuple[int, tuple[ProgramHeader, ...]]:
    if not data:
        raise ElfError("empty")
    if len(data) < ELF_HEADER_BYTES:
        raise ElfError("header_truncated")
    if len(data) > MAX_FILE_BYTES:
        raise ElfError("file_too_large")
    if data[:4] != b"\x7fELF":
        raise ElfError("magic")
    if data[4] != 2:
        raise ElfError("class")
    if data[5] != 1:
        raise ElfError("encoding")
    if data[6] != 1:
        raise ElfError("ident_version")
    if data[7] != 0:
        raise ElfError("osabi")
    if data[8] != 0:
        raise ElfError("abi_version")
    if any(data[9:16]):
        raise ElfError("ident_padding")
    (
        file_type,
        machine,
        version,
        entry,
        program_offset,
        section_offset,
        flags,
        header_size,
        program_entry_size,
        program_count,
        section_entry_size,
        section_count,
        section_name_index,
    ) = _unpack("<HHIQQQIHHHHHH", data, 16, "header_truncated")
    if file_type != 3:
        raise ElfError("file_type")
    if machine != 62:
        raise ElfError("machine")
    if version != 1:
        raise ElfError("version")
    if program_offset != ELF_HEADER_BYTES:
        raise ElfError("program_header_offset")
    if flags != 0:
        raise ElfError("header_flags")
    if header_size != ELF_HEADER_BYTES:
        raise ElfError("header_size")
    if program_entry_size != PROGRAM_HEADER_BYTES:
        raise ElfError("program_header_size")
    if program_count != PROGRAM_HEADER_COUNT:
        raise ElfError("program_header_count")
    if section_offset != 0 or section_count != 0 or section_name_index != 0 or section_entry_size not in (0, 64):
        raise ElfError("section_table")
    if ELF_HEADER_BYTES + PROGRAM_HEADER_BYTES * PROGRAM_HEADER_COUNT > len(data):
        raise ElfError("program_header_bounds")
    headers = tuple(_program_header(data, index) for index in range(PROGRAM_HEADER_COUNT))
    allowed = {PT_PHDR, PT_LOAD, PT_DYNAMIC, PT_GNU_RELRO, PT_GNU_STACK}
    if any(header.segment_type not in allowed for header in headers):
        raise ElfError("unsupported_segment")
    expected = (PT_PHDR, PT_LOAD, PT_LOAD, PT_LOAD, PT_DYNAMIC, PT_GNU_RELRO, PT_GNU_STACK)
    if tuple(header.segment_type for header in headers) != expected:
        raise ElfError("program_header_order")
    return entry, headers


def _validate_phdr(header: ProgramHeader) -> None:
    expected_size = PROGRAM_HEADER_BYTES * PROGRAM_HEADER_COUNT
    if (
        header.flags != PF_R
        or header.offset != ELF_HEADER_BYTES
        or header.virtual_address != ELF_HEADER_BYTES
        or header.physical_address != 0
        or header.file_size != expected_size
        or header.memory_size != expected_size
        or header.alignment != 8
    ):
        raise ElfError("phdr_segment")


def _validate_loads(data: bytes, headers: tuple[ProgramHeader, ...]) -> tuple[tuple[ProgramHeader, ...], int]:
    loads = headers[1:4]
    if len(loads) != LOAD_SEGMENT_COUNT:
        raise ElfError("load_count")
    expected_flags = (PF_R, PF_R | PF_X, PF_R | PF_W)
    for load, flags in zip(loads, expected_flags, strict=True):
        if load.flags != flags or load.flags & (PF_W | PF_X) == (PF_W | PF_X):
            raise ElfError("load_flags")
        if (
            load.alignment != PAGE_SIZE
            or load.offset % PAGE_SIZE
            or load.virtual_address % PAGE_SIZE
            or load.offset != load.virtual_address
        ):
            raise ElfError("load_alignment")
        if load.physical_address != 0:
            raise ElfError("load_address")
        if (
            load.file_size == 0
            or load.memory_size == 0
            or load.file_size > load.memory_size
            or load.memory_size % PAGE_SIZE
        ):
            raise ElfError("segment_size")
        file_end = _checked_add(load.offset, load.file_size, "segment_bounds")
        memory_end = _checked_add(load.virtual_address, load.memory_size, "segment_bounds")
        if file_end > len(data) or memory_end > MAX_IMAGE_BYTES:
            raise ElfError("segment_bounds")
    if loads[0].virtual_address != 0 or loads[0].offset != 0:
        raise ElfError("segment_layout")
    if (
        loads[0].file_size != loads[0].memory_size
        or loads[1].file_size != loads[1].memory_size
        or loads[0].virtual_address + loads[0].memory_size != loads[1].virtual_address
        or loads[1].virtual_address + loads[1].memory_size != loads[2].virtual_address
        or loads[0].file_size != loads[1].offset
        or loads[1].offset + loads[1].file_size != loads[2].offset
    ):
        raise ElfError("segment_layout")
    if loads[0].file_size < ELF_HEADER_BYTES + PROGRAM_HEADER_BYTES * PROGRAM_HEADER_COUNT:
        raise ElfError("file_coverage")
    if loads[2].offset + loads[2].file_size != len(data):
        raise ElfError("file_coverage")
    image_size = _checked_add(loads[2].virtual_address, loads[2].memory_size, "segment_bounds")
    if loads[2].memory_size < PAGE_SIZE * 2 or image_size > MAX_IMAGE_BYTES:
        raise ElfError("segment_size")
    return loads, image_size


def _validate_bases(physical_base: int, virtual_base: int, image_size: int) -> None:
    if (
        physical_base < MIN_PHYSICAL_BASE
        or physical_base % PAGE_SIZE
        or _checked_add(physical_base, image_size, "physical_base") > MAX_PHYSICAL_EXCLUSIVE
    ):
        raise ElfError("physical_base")
    if (
        virtual_base < MIN_VIRTUAL_BASE
        or virtual_base >= MAX_VIRTUAL_EXCLUSIVE
        or virtual_base % VIRTUAL_BASE_ALIGNMENT
        or _checked_add(virtual_base, image_size, "virtual_base") > MAX_VIRTUAL_EXCLUSIVE
    ):
        raise ElfError("virtual_base")


def _validate_metadata(
    data: bytes,
    dynamic: ProgramHeader,
    relro: ProgramHeader,
    stack: ProgramHeader,
    writable: ProgramHeader,
) -> tuple[int, int, int]:
    if (
        relro.flags != PF_R
        or relro.offset != writable.offset
        or relro.virtual_address != writable.virtual_address
        or relro.physical_address != 0
        or relro.file_size != relro.memory_size
        or relro.memory_size < PAGE_SIZE
        or relro.memory_size % PAGE_SIZE
        or relro.alignment != PAGE_SIZE
        or relro.memory_size >= writable.memory_size
        or relro.memory_size > writable.file_size
    ):
        raise ElfError("relro_segment")
    if (
        stack.flags != PF_R | PF_W
        or stack.offset != 0
        or stack.virtual_address != 0
        or stack.physical_address != 0
        or stack.file_size != 0
        or stack.memory_size != 0
        or stack.alignment != 16
    ):
        raise ElfError("stack_segment")
    if (
        dynamic.flags != PF_R | PF_W
        or dynamic.offset != writable.offset
        or dynamic.virtual_address != writable.virtual_address
        or dynamic.physical_address != 0
        or dynamic.file_size != DYNAMIC_BYTES
        or dynamic.memory_size != DYNAMIC_BYTES
        or dynamic.alignment != 8
        or not _contains(relro.virtual_address, relro.memory_size, dynamic.virtual_address, dynamic.memory_size)
    ):
        raise ElfError("dynamic_segment")
    entries = tuple(_unpack("<qQ", data, dynamic.offset + index * 16, "dynamic_segment") for index in range(4))
    if tuple(tag for tag, _ in entries) != (DT_RELA, DT_RELASZ, DT_RELAENT, DT_NULL):
        raise ElfError("dynamic_order")
    if entries[3][1] != 0:
        raise ElfError("dynamic_entry")
    relocation_address = entries[0][1]
    relocation_size = entries[1][1]
    if entries[2][1] != RELA_ENTRY_BYTES:
        raise ElfError("relocation_entry_size")
    if relocation_size == 0 or relocation_size % RELA_ENTRY_BYTES:
        raise ElfError("relocation_table")
    relocation_count = relocation_size // RELA_ENTRY_BYTES
    if relocation_count == 0 or relocation_count > MAX_RELOCATIONS:
        raise ElfError("relocation_count")
    if (
        relocation_address % 8
        or _overlaps(dynamic.virtual_address, dynamic.memory_size, relocation_address, relocation_size)
        or not _contains(relro.virtual_address, relro.memory_size, relocation_address, relocation_size)
        or not _contains(writable.virtual_address, writable.file_size, relocation_address, relocation_size)
    ):
        raise ElfError("relocation_table")
    return relocation_address, relocation_size, relocation_count


def _validate_relocations(
    data: bytes,
    relocation_address: int,
    relocation_size: int,
    relocation_count: int,
    dynamic: ProgramHeader,
    relro: ProgramHeader,
    loads: tuple[ProgramHeader, ...],
    image_size: int,
    virtual_base: int,
) -> None:
    previous_target: int | None = None
    image_end = _checked_add(virtual_base, image_size, "relocation_value")
    for index in range(relocation_count):
        record = relocation_address + index * RELA_ENTRY_BYTES
        target, info, addend = _unpack("<QQq", data, record, "relocation_table")
        if info & 0xFFFF_FFFF != R_X86_64_RELATIVE:
            raise ElfError("relocation_type")
        if info >> 32:
            raise ElfError("relocation_symbol")
        if previous_target is not None and target <= previous_target:
            raise ElfError("relocation_order")
        previous_target = target
        if (
            target % 8
            or not _contains(relro.virtual_address, relro.memory_size, target, 8)
            or _overlaps(dynamic.virtual_address, dynamic.memory_size, target, 8)
            or _overlaps(relocation_address, relocation_size, target, 8)
        ):
            raise ElfError("relocation_target")
        if target + 8 > len(data) or any(data[target : target + 8]):
            raise ElfError("relocation_target")
        if addend < 0 or addend >= image_size or not any(
            _contains(load.virtual_address, load.memory_size, addend, 1) for load in loads
        ):
            raise ElfError("relocation_addend")
        value = _checked_add(virtual_base, addend, "relocation_value")
        if value < virtual_base or value >= image_end:
            raise ElfError("relocation_value")


def inspect(data: bytes, physical_base: int, virtual_base: int) -> ImagePlan:
    entry, headers = _validate_header(data)
    _validate_phdr(headers[0])
    loads, image_size = _validate_loads(data, headers)
    _validate_bases(physical_base, virtual_base, image_size)
    if not _contains(loads[1].virtual_address, loads[1].file_size, entry, 1):
        raise ElfError("entry_point")
    relocation_address, relocation_size, relocation_count = _validate_metadata(
        data, headers[4], headers[5], headers[6], loads[2]
    )
    _validate_relocations(
        data,
        relocation_address,
        relocation_size,
        relocation_count,
        headers[4],
        headers[5],
        loads,
        image_size,
        virtual_base,
    )
    segments = tuple(
        SegmentPlan(load.offset, load.virtual_address, load.file_size, load.memory_size, permissions)
        for load, permissions in zip(loads, ("r", "rx", "rw"), strict=True)
    )
    relro_end = headers[5].virtual_address + headers[5].memory_size
    writable_end = loads[2].virtual_address + loads[2].memory_size
    mappings = (
        MappingPlan(loads[0].virtual_address, loads[0].memory_size, "r"),
        MappingPlan(loads[1].virtual_address, loads[1].memory_size, "rx"),
        MappingPlan(headers[5].virtual_address, headers[5].memory_size, "r"),
        MappingPlan(relro_end, writable_end - relro_end, "rw"),
    )
    return ImagePlan(
        file_size=len(data),
        image_size=image_size,
        entry_offset=entry,
        entry_virtual=virtual_base + entry,
        entry_physical=physical_base + entry,
        physical_base=physical_base,
        virtual_base=virtual_base,
        relocation_count=relocation_count,
        relro_offset=headers[5].virtual_address,
        relro_size=headers[5].memory_size,
        segments=segments,
        mappings=mappings,
        relocation_address=relocation_address,
    )


def load(data: bytes, physical_base: int, virtual_base: int, capacity: int | None = None) -> tuple[ImagePlan, bytes]:
    plan = inspect(data, physical_base, virtual_base)
    if capacity is None:
        capacity = plan.image_size
    if capacity < plan.image_size:
        raise ElfError("output_capacity")
    destination = bytearray(b"\xA5" * capacity)
    destination[: plan.image_size] = b"\0" * plan.image_size
    for segment in plan.segments:
        destination[segment.virtual_offset : segment.virtual_offset + segment.file_size] = data[
            segment.file_offset : segment.file_offset + segment.file_size
        ]
    for index in range(plan.relocation_count):
        record = plan.relocation_address + index * RELA_ENTRY_BYTES
        target, _, addend = struct.unpack_from("<QQq", data, record)
        struct.pack_into("<Q", destination, target, plan.virtual_base + addend)
    return plan, bytes(destination)


def fnv1a64(data: bytes) -> int:
    value = 0xCBF2_9CE4_8422_2325
    for byte in data:
        value ^= byte
        value = value * 0x0000_0100_0000_01B3 & 0xFFFF_FFFF_FFFF_FFFF
    return value


def _range_text(plans: Iterable[SegmentPlan | MappingPlan]) -> str:
    return ",".join(f"{plan.virtual_offset:08x}+{plan.memory_size:08x}:{plan.permissions}" for plan in plans)


def semantic_summary(plan: ImagePlan, loaded: bytes) -> str:
    return (
        f"OK;file_size={plan.file_size};image_size={plan.image_size};"
        f"entry_offset={plan.entry_offset:08x};entry_virtual={plan.entry_virtual:016x};"
        f"entry_physical={plan.entry_physical:016x};physical_base={plan.physical_base:016x};"
        f"virtual_base={plan.virtual_base:016x};relocations={plan.relocation_count};"
        f"relro={plan.relro_offset:08x}+{plan.relro_size:08x};"
        f"segments={_range_text(plan.segments)};mappings={_range_text(plan.mappings)};"
        f"fnv64={fnv1a64(loaded[: plan.image_size]):016x}"
    )


def result_summary(data: bytes, physical_base: int, virtual_base: int, capacity: int) -> str:
    try:
        plan, loaded = load(data, physical_base, virtual_base, capacity)
    except ElfError as exc:
        return f"ERR:{exc.code}"
    return semantic_summary(plan, loaded)


def _write_program_header(data: bytearray, index: int, values: tuple[int, ...]) -> None:
    struct.pack_into("<IIQQQQQQ", data, ELF_HEADER_BYTES + index * PROGRAM_HEADER_BYTES, *values)


def build_fixture(name: str) -> bytes:
    profiles = {
        "minimal_relative_v1": (2, 1),
        "alternate_base_v1": (32, 2),
        "maximum_relocations_v1": (MAX_RELOCATIONS, None),
    }
    if name not in profiles:
        raise KeyError(name)
    relocation_count, requested_relro_pages = profiles[name]
    relocation_address = 0x2040
    relocation_size = relocation_count * RELA_ENTRY_BYTES
    target_start = (relocation_address + relocation_size + 7) & ~7
    target_end = target_start + relocation_count * 8
    minimum_relro_size = target_end - 0x2000
    computed_pages = (minimum_relro_size + PAGE_SIZE - 1) // PAGE_SIZE
    relro_pages = requested_relro_pages or computed_pages
    if relro_pages < computed_pages:
        raise AssertionError("fixture profile cannot hold relocations")
    relro_size = relro_pages * PAGE_SIZE
    writable_file_size = relro_size
    writable_memory_size = relro_size + PAGE_SIZE
    file_size = 0x2000 + writable_file_size
    data = bytearray(file_size)
    data[:16] = b"\x7fELF" + bytes((2, 1, 1, 0, 0)) + bytes(7)
    struct.pack_into(
        "<HHIQQQIHHHHHH",
        data,
        16,
        3,
        62,
        1,
        0x1000,
        ELF_HEADER_BYTES,
        0,
        0,
        ELF_HEADER_BYTES,
        PROGRAM_HEADER_BYTES,
        PROGRAM_HEADER_COUNT,
        0,
        0,
        0,
    )
    _write_program_header(data, 0, (PT_PHDR, PF_R, 64, 64, 0, 392, 392, 8))
    _write_program_header(data, 1, (PT_LOAD, PF_R, 0, 0, 0, 0x1000, 0x1000, PAGE_SIZE))
    _write_program_header(data, 2, (PT_LOAD, PF_R | PF_X, 0x1000, 0x1000, 0, 0x1000, 0x1000, PAGE_SIZE))
    _write_program_header(
        data,
        3,
        (PT_LOAD, PF_R | PF_W, 0x2000, 0x2000, 0, writable_file_size, writable_memory_size, PAGE_SIZE),
    )
    _write_program_header(data, 4, (PT_DYNAMIC, PF_R | PF_W, 0x2000, 0x2000, 0, 64, 64, 8))
    _write_program_header(
        data, 5, (PT_GNU_RELRO, PF_R, 0x2000, 0x2000, 0, relro_size, relro_size, PAGE_SIZE)
    )
    _write_program_header(data, 6, (PT_GNU_STACK, PF_R | PF_W, 0, 0, 0, 0, 0, 16))
    data[0x1000:0x1010] = b"\xFA\xF4\xEB\xFD" + b"PKELF1\0\0\0\0\0\0"
    dynamic = ((DT_RELA, relocation_address), (DT_RELASZ, relocation_size), (DT_RELAENT, 24), (DT_NULL, 0))
    for index, (tag, value) in enumerate(dynamic):
        struct.pack_into("<qQ", data, 0x2000 + index * 16, tag, value)
    image_size = 0x2000 + writable_memory_size
    for index in range(relocation_count):
        target = target_start + index * 8
        selector = index % 4
        if selector == 0:
            addend = 0
        elif selector == 1:
            addend = 0x1000 + index % 0x1000
        elif selector == 2:
            addend = 0x2000 + index % relro_size
        else:
            addend = image_size - PAGE_SIZE + index % PAGE_SIZE
        struct.pack_into("<QQq", data, relocation_address + index * RELA_ENTRY_BYTES, target, R_X86_64_RELATIVE, addend)
    return bytes(data)


def vector_profiles() -> tuple[dict[str, int | str], ...]:
    return (
        {
            "id": "minimal_relative_v1",
            "physical_base": 0x0200_0000,
            "virtual_base": MIN_VIRTUAL_BASE,
        },
        {
            "id": "alternate_base_v1",
            "physical_base": 0x1200_0000,
            "virtual_base": MIN_VIRTUAL_BASE + 0x0200_0000,
        },
        {
            "id": "maximum_relocations_v1",
            "physical_base": 0x0000_0001_0000_0000,
            "virtual_base": MIN_VIRTUAL_BASE + 0x1000_0000,
        },
    )


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_no_std_loader_boundary": True,
        "program_headers_authoritative": True,
        "three_load_segment_profile": True,
        "bss_zero_fill": True,
        "relative_relocations_only": True,
        "post_relocation_wx_plan": True,
        "exact_loaded_bytes_compared": True,
        "synthetic_kernel_image_only": True,
        "live_uefi_file_read": False,
        "uefi_page_allocation": False,
        "page_table_mapping": False,
        "signed_manifest_verification": False,
        "exit_boot_services": False,
        "kernel_entry_transfer": False,
        "poolekernel_execution": False,
        "abi_ratified": False,
        "second_host_reproduced": False,
        "target_firmware_tested": False,
        "physical_media_written": False,
        "production_ready": False,
    }


def contract_errors(contract: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract is not an object"]
    if contract.get("contract_id") != CONTRACT_ID:
        errors.append("contract id mismatch")
    bounds = contract.get("bounds", {})
    expected = {
        "max_file_bytes": MAX_FILE_BYTES,
        "max_image_bytes": MAX_IMAGE_BYTES,
        "program_header_count": PROGRAM_HEADER_COUNT,
        "load_segment_count": LOAD_SEGMENT_COUNT,
        "mapping_count": MAPPING_COUNT,
        "max_relocations": MAX_RELOCATIONS,
    }
    for key, value in expected.items():
        if bounds.get(key) != value:
            errors.append(f"contract bound mismatch: {key}")
    if contract.get("claims") != expected_claims():
        errors.append("contract claim boundary mismatch")
    return errors


def golden_errors(golden: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(golden, dict) or golden.get("contract_id") != CONTRACT_ID:
        return ["golden vector header mismatch"]
    vectors = golden.get("vectors")
    if not isinstance(vectors, list) or len(vectors) != 3:
        return ["golden vector count mismatch"]
    expected_ids = [profile["id"] for profile in vector_profiles()]
    if [vector.get("id") for vector in vectors] != expected_ids:
        errors.append("golden vector order mismatch")
    for vector, profile in zip(vectors, vector_profiles(), strict=True):
        data = build_fixture(str(profile["id"]))
        plan, loaded = load(data, int(profile["physical_base"]), int(profile["virtual_base"]))
        checks = {
            "file_hex": data.hex(),
            "file_byte_count": len(data),
            "file_sha256": sha256_bytes(data),
            "physical_base": int(profile["physical_base"]),
            "virtual_base": int(profile["virtual_base"]),
            "image_byte_count": plan.image_size,
            "loaded_sha256": sha256_bytes(loaded[: plan.image_size]),
            "semantic_summary": semantic_summary(plan, loaded),
            "expected_plan": {
                "file_size": plan.file_size,
                "image_size": plan.image_size,
                "entry_offset": plan.entry_offset,
                "entry_virtual": plan.entry_virtual,
                "entry_physical": plan.entry_physical,
                "relocation_count": plan.relocation_count,
                "relro_offset": plan.relro_offset,
                "relro_size": plan.relro_size,
                "segments": [
                    {
                        "file_offset": segment.file_offset,
                        "virtual_offset": segment.virtual_offset,
                        "file_size": segment.file_size,
                        "memory_size": segment.memory_size,
                        "permissions": segment.permissions,
                    }
                    for segment in plan.segments
                ],
                "mappings": [
                    {
                        "virtual_offset": mapping.virtual_offset,
                        "memory_size": mapping.memory_size,
                        "permissions": mapping.permissions,
                    }
                    for mapping in plan.mappings
                ],
            },
        }
        for key, value in checks.items():
            if vector.get(key) != value:
                errors.append(f"golden vector {profile['id']} mismatch: {key}")
    return errors


def readiness_errors(readiness: Any) -> list[str]:
    errors = [
        f"schema {item.path}: {item.message}"
        for item in validate_json(readiness, read_json(ROOT / READINESS_SCHEMA_RELATIVE))
    ]
    if not isinstance(readiness, dict) or readiness.get("contract_id") != CONTRACT_ID:
        return ["readiness header mismatch"]
    contract = read_json(ROOT / CONTRACT_RELATIVE)
    golden = read_json(ROOT / GOLDEN_RELATIVE)
    errors.extend(f"contract {item}" for item in contract_errors(contract))
    errors.extend(f"golden {item}" for item in golden_errors(golden))
    expected_bindings = {
        "contract": file_binding(ROOT / CONTRACT_RELATIVE),
        "contract_schema": file_binding(ROOT / CONTRACT_SCHEMA_RELATIVE),
        "golden_vectors": file_binding(ROOT / GOLDEN_RELATIVE),
        "golden_schema": file_binding(ROOT / GOLDEN_SCHEMA_RELATIVE),
        "readiness_schema": file_binding(ROOT / READINESS_SCHEMA_RELATIVE),
        "implementation_inputs": [file_binding(ROOT / path) for path in IMPLEMENTATION_INPUTS],
    }
    if readiness.get("bindings") != expected_bindings:
        errors.append("readiness input bindings are stale")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("readiness promotion boundary mismatch")
    if readiness.get("n5_exit_gate_satisfied") is not False:
        errors.append("readiness overclaims N5 exit")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary mismatch")
    summary = readiness.get("summary", {})
    expected_summary = {
        "rust_host_tests_passed": 12,
        "rust_host_tests_total": 12,
        "rustfmt_passed": 1,
        "clippy_runs_passed": 3,
        "clippy_runs_total": 3,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "pooleboot_integration_builds_passed": 2,
        "pooleboot_integration_builds_total": 2,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "exact_loaded_byte_vectors_matched": 3,
        "maximum_relocations_exercised": MAX_RELOCATIONS,
        "negative_controls_passed": 129,
        "negative_controls_total": 129,
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "production_claim_count": 0,
    }
    if summary != expected_summary:
        errors.append("readiness summary changed")
    controls = readiness.get("negative_controls", [])
    if len(controls) != 129 or len({item.get("id") for item in controls if isinstance(item, dict)}) != 129:
        errors.append("negative control register changed")
    if any(
        item.get("status") != "pass"
        or item.get("expected_result") != item.get("python_result")
        or item.get("expected_result") != item.get("rust_result")
        for item in controls
        if isinstance(item, dict)
    ):
        errors.append("negative control did not pass")
    differential = readiness.get("differential_fuzz", {})
    if (
        differential.get("case_count") != 16_384
        or differential.get("mismatch_count") != 0
        or differential.get("valid_result_count", 0) <= 0
        or differential.get("rejected_result_count", 0) <= 0
        or differential.get("valid_result_count", 0) + differential.get("rejected_result_count", 0) != 16_384
        or differential.get("corpus_published") is not False
    ):
        errors.append("readiness differential mismatch")
    return errors
