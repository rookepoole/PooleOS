#!/usr/bin/env python3
"""Fail-closed canonicalization of pinned-LLD PooleKernel output into PKELF1."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from runtime import native_elf_loader as pkelf


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "native" / "kernel" / "manifest.pkm"

ELF_HEADER_BYTES = 64
PROGRAM_HEADER_BYTES = 56
PROGRAM_HEADER_COUNT = 7
PAGE_SIZE = 4096
RELA_ENTRY_BYTES = 24
CANONICAL_DYNAMIC_BYTES = 64

PT_LOAD = 1
PT_DYNAMIC = 2
PT_PHDR = 6
PT_GNU_STACK = 0x6474_E551
PT_GNU_RELRO = 0x6474_E552
PF_X = 1
PF_W = 2
PF_R = 4

DT_NULL = 0
DT_NEEDED = 1
DT_HASH = 4
DT_STRTAB = 5
DT_SYMTAB = 6
DT_RELA = 7
DT_RELASZ = 8
DT_RELAENT = 9
DT_STRSZ = 10
DT_SYMENT = 11
DT_DEBUG = 21
DT_FLAGS = 30
DT_GNU_HASH = 0x6FFF_FEF5
DT_FLAGS_1 = 0x6FFF_FFFB
DT_RELACOUNT = 0x6FFF_FFF9
R_X86_64_RELATIVE = 8

ALLOWED_SOURCE_DYNAMIC_TAGS = {
    DT_NULL,
    DT_HASH,
    DT_STRTAB,
    DT_SYMTAB,
    DT_RELA,
    DT_RELASZ,
    DT_RELAENT,
    DT_STRSZ,
    DT_SYMENT,
    DT_DEBUG,
    DT_FLAGS,
    DT_GNU_HASH,
    DT_FLAGS_1,
    DT_RELACOUNT,
}


class KernelImageError(ValueError):
    """A stable canonicalizer rejection."""

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
class LinkedImagePlan:
    linked_byte_count: int
    canonical_byte_count: int
    entry_offset: int
    image_byte_count: int
    source_dynamic_entry_count: int
    relocation_count: int
    relocation_source_offset: int
    relocation_canonical_offset: int
    relro_offset: int
    relro_byte_count: int
    manifest_offset: int
    load_segments: tuple[ProgramHeader, ProgramHeader, ProgramHeader]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _unpack(fmt: str, data: bytes, offset: int, code: str) -> tuple[int, ...]:
    try:
        return struct.unpack_from(fmt, data, offset)
    except struct.error as error:
        raise KernelImageError(code) from error


def _program_header(data: bytes, index: int) -> ProgramHeader:
    values = _unpack(
        "<IIQQQQQQ",
        data,
        ELF_HEADER_BYTES + index * PROGRAM_HEADER_BYTES,
        "program_header_bounds",
    )
    return ProgramHeader(*values)


def _contains(start: int, size: int, inner_start: int, inner_size: int) -> bool:
    if min(start, size, inner_start, inner_size) < 0:
        return False
    end = start + size
    inner_end = inner_start + inner_size
    return end <= 0xFFFF_FFFF_FFFF_FFFF and inner_end <= end and inner_start >= start


def _overlaps(left_start: int, left_size: int, right_start: int, right_size: int) -> bool:
    return left_start < right_start + right_size and right_start < left_start + left_size


def _in_any_load(loads: Iterable[ProgramHeader], address: int, size: int = 1) -> bool:
    return any(_contains(load.virtual_address, load.memory_size, address, size) for load in loads)


def _source_dynamic_entries(data: bytes, dynamic: ProgramHeader) -> list[tuple[int, int]]:
    if dynamic.file_size == 0 or dynamic.file_size % 16:
        raise KernelImageError("source_dynamic_size")
    entries: list[tuple[int, int]] = []
    for offset in range(dynamic.offset, dynamic.offset + dynamic.file_size, 16):
        tag, value = _unpack("<qQ", data, offset, "source_dynamic_bounds")
        if tag not in ALLOWED_SOURCE_DYNAMIC_TAGS:
            raise KernelImageError("source_dynamic_tag")
        entries.append((tag, value))
        if tag == DT_NULL:
            break
    if not entries or entries[-1][0] != DT_NULL:
        raise KernelImageError("source_dynamic_terminator")
    if len({tag for tag, _ in entries}) != len(entries):
        raise KernelImageError("source_dynamic_duplicate")
    if any(data[dynamic.offset + len(entries) * 16 : dynamic.offset + dynamic.file_size]):
        raise KernelImageError("source_dynamic_trailing")
    return entries


def inspect_linked_image(data: bytes, manifest: bytes | None = None) -> LinkedImagePlan:
    manifest = MANIFEST_PATH.read_bytes() if manifest is None else manifest
    if len(data) < ELF_HEADER_BYTES + PROGRAM_HEADER_BYTES * PROGRAM_HEADER_COUNT:
        raise KernelImageError("header_bounds")
    if data[:16] != b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8:
        raise KernelImageError("elf_ident")
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
    ) = _unpack("<HHIQQQIHHHHHH", data, 16, "header_bounds")
    if (file_type, machine, version, flags) != (3, 62, 1, 0):
        raise KernelImageError("elf_header")
    if (
        program_offset != ELF_HEADER_BYTES
        or header_size != ELF_HEADER_BYTES
        or program_entry_size != PROGRAM_HEADER_BYTES
        or program_count != PROGRAM_HEADER_COUNT
    ):
        raise KernelImageError("program_header_geometry")
    if section_offset == 0 or section_entry_size != 64 or section_count == 0 or section_name_index >= section_count:
        raise KernelImageError("source_section_table")

    headers = tuple(_program_header(data, index) for index in range(PROGRAM_HEADER_COUNT))
    expected_types = (
        PT_PHDR,
        PT_LOAD,
        PT_LOAD,
        PT_LOAD,
        PT_DYNAMIC,
        PT_GNU_RELRO,
        PT_GNU_STACK,
    )
    if tuple(header.segment_type for header in headers) != expected_types:
        raise KernelImageError("program_header_order")
    phdr, ro, text, writable, dynamic, relro, stack = headers
    if (
        phdr.flags != PF_R
        or phdr.offset != ELF_HEADER_BYTES
        or phdr.virtual_address != ELF_HEADER_BYTES
        or phdr.physical_address != ELF_HEADER_BYTES
        or phdr.file_size != PROGRAM_HEADER_BYTES * PROGRAM_HEADER_COUNT
        or phdr.memory_size != phdr.file_size
        or phdr.alignment != 8
    ):
        raise KernelImageError("phdr_segment")

    loads = (ro, text, writable)
    for load, expected_flags in zip(loads, (PF_R, PF_R | PF_X, PF_R | PF_W), strict=True):
        if load.flags != expected_flags:
            raise KernelImageError("load_flags")
        if (
            load.offset != load.virtual_address
            or load.physical_address != load.virtual_address
            or load.alignment != PAGE_SIZE
            or load.offset % PAGE_SIZE
            or load.file_size == 0
            or load.memory_size == 0
            or load.file_size > load.memory_size
            or load.memory_size % PAGE_SIZE
        ):
            raise KernelImageError("load_geometry")
        if load.offset + load.file_size > len(data):
            raise KernelImageError("load_bounds")
    if (
        ro.offset != 0
        or ro.file_size != ro.memory_size
        or text.file_size != text.memory_size
        or ro.offset + ro.memory_size != text.offset
        or text.offset + text.memory_size != writable.offset
        or writable.memory_size < PAGE_SIZE * 2
    ):
        raise KernelImageError("load_layout")
    canonical_end = writable.offset + writable.file_size
    if section_offset < canonical_end or section_offset + section_entry_size * section_count > len(data):
        raise KernelImageError("source_section_bounds")
    if not _contains(text.virtual_address, text.file_size, entry, 2):
        raise KernelImageError("entry_range")
    if data[entry : entry + 2] != b"\xfa\xfc":
        raise KernelImageError("entry_prefix")

    if (
        dynamic.flags != PF_R | PF_W
        or dynamic.offset != writable.offset
        or dynamic.virtual_address != writable.virtual_address
        or dynamic.physical_address != writable.virtual_address
        or dynamic.file_size != dynamic.memory_size
        or dynamic.alignment != 8
    ):
        raise KernelImageError("source_dynamic_segment")
    if (
        relro.flags != PF_R
        or relro.offset != writable.offset
        or relro.virtual_address != writable.virtual_address
        or relro.physical_address != writable.virtual_address
        or relro.file_size != relro.memory_size
        or relro.file_size < PAGE_SIZE
        or relro.file_size % PAGE_SIZE
        or relro.file_size > writable.file_size
        or relro.file_size >= writable.memory_size
    ):
        raise KernelImageError("source_relro_segment")
    if (
        stack.flags != PF_R | PF_W
        or any(
            (
                stack.offset,
                stack.virtual_address,
                stack.physical_address,
                stack.file_size,
                stack.memory_size,
            )
        )
        or stack.alignment not in (0, 16)
    ):
        raise KernelImageError("source_stack_segment")

    entries = _source_dynamic_entries(data, dynamic)
    values = {tag: value for tag, value in entries}
    if DT_NEEDED in values:
        raise KernelImageError("source_import")
    for required in (DT_RELA, DT_RELASZ, DT_RELAENT):
        if required not in values:
            raise KernelImageError("source_relocation_metadata")
    relocation_offset = values[DT_RELA]
    relocation_size = values[DT_RELASZ]
    if values[DT_RELAENT] != RELA_ENTRY_BYTES or not relocation_size or relocation_size % RELA_ENTRY_BYTES:
        raise KernelImageError("source_relocation_geometry")
    relocation_count = relocation_size // RELA_ENTRY_BYTES
    if not 1 <= relocation_count <= pkelf.MAX_RELOCATIONS:
        raise KernelImageError("source_relocation_count")
    if values.get(DT_RELACOUNT, relocation_count) != relocation_count:
        raise KernelImageError("source_relocation_count")
    if relocation_offset != dynamic.offset + dynamic.file_size:
        raise KernelImageError("source_relocation_layout")
    relocation_end = relocation_offset + relocation_size
    if not _contains(relro.offset, relro.file_size, relocation_offset, relocation_size):
        raise KernelImageError("source_relocation_bounds")
    canonical_relocation_offset = dynamic.offset + CANONICAL_DYNAMIC_BYTES
    if canonical_relocation_offset + relocation_size > relocation_end:
        raise KernelImageError("canonical_relocation_capacity")

    previous_target = -1
    for index in range(relocation_count):
        record_offset = relocation_offset + index * RELA_ENTRY_BYTES
        target, info, addend = _unpack("<QQq", data, record_offset, "source_relocation_bounds")
        if info & 0xFFFF_FFFF != R_X86_64_RELATIVE or info >> 32:
            raise KernelImageError("source_relocation_type")
        if target <= previous_target:
            raise KernelImageError("source_relocation_order")
        previous_target = target
        if (
            target % 8
            or not _contains(relro.offset, relro.file_size, target, 8)
            or _overlaps(dynamic.offset, dynamic.file_size, target, 8)
            or _overlaps(relocation_offset, relocation_size, target, 8)
        ):
            raise KernelImageError("source_relocation_target")
        if any(data[target : target + 8]):
            raise KernelImageError("source_relocation_target_value")
        if addend < 0 or not _in_any_load(loads, addend):
            raise KernelImageError("source_relocation_addend")

    manifest_offset = data.find(manifest)
    if manifest_offset < 0 or data.count(manifest) != 1:
        raise KernelImageError("manifest_presence")
    if not _contains(ro.offset, ro.file_size, manifest_offset, len(manifest)):
        raise KernelImageError("manifest_segment")

    return LinkedImagePlan(
        linked_byte_count=len(data),
        canonical_byte_count=canonical_end,
        entry_offset=entry,
        image_byte_count=writable.offset + writable.memory_size,
        source_dynamic_entry_count=len(entries),
        relocation_count=relocation_count,
        relocation_source_offset=relocation_offset,
        relocation_canonical_offset=canonical_relocation_offset,
        relro_offset=relro.offset,
        relro_byte_count=relro.file_size,
        manifest_offset=manifest_offset,
        load_segments=loads,
    )


def canonicalize_linked_image(
    data: bytes,
    manifest: bytes | None = None,
) -> tuple[bytes, LinkedImagePlan]:
    manifest = MANIFEST_PATH.read_bytes() if manifest is None else manifest
    plan = inspect_linked_image(data, manifest)
    output = bytearray(data[: plan.canonical_byte_count])
    relocation_size = plan.relocation_count * RELA_ENTRY_BYTES
    relocations = bytes(
        data[
            plan.relocation_source_offset : plan.relocation_source_offset + relocation_size
        ]
    )
    output[plan.relro_offset : plan.relocation_source_offset + relocation_size] = b"\x00" * (
        plan.relocation_source_offset + relocation_size - plan.relro_offset
    )
    dynamic_entries = (
        (DT_RELA, plan.relocation_canonical_offset),
        (DT_RELASZ, relocation_size),
        (DT_RELAENT, RELA_ENTRY_BYTES),
        (DT_NULL, 0),
    )
    for index, (tag, value) in enumerate(dynamic_entries):
        struct.pack_into("<qQ", output, plan.relro_offset + index * 16, tag, value)
    output[
        plan.relocation_canonical_offset : plan.relocation_canonical_offset + relocation_size
    ] = relocations

    struct.pack_into("<Q", output, 40, 0)
    struct.pack_into("<H", output, 58, 0)
    struct.pack_into("<H", output, 60, 0)
    struct.pack_into("<H", output, 62, 0)
    for index in range(PROGRAM_HEADER_COUNT):
        base = ELF_HEADER_BYTES + index * PROGRAM_HEADER_BYTES
        struct.pack_into("<Q", output, base + 24, 0)
    dynamic_base = ELF_HEADER_BYTES + 4 * PROGRAM_HEADER_BYTES
    struct.pack_into("<Q", output, dynamic_base + 32, CANONICAL_DYNAMIC_BYTES)
    struct.pack_into("<Q", output, dynamic_base + 40, CANONICAL_DYNAMIC_BYTES)
    relro_base = ELF_HEADER_BYTES + 5 * PROGRAM_HEADER_BYTES
    struct.pack_into("<Q", output, relro_base + 48, PAGE_SIZE)
    stack_base = ELF_HEADER_BYTES + 6 * PROGRAM_HEADER_BYTES
    struct.pack_into("<Q", output, stack_base + 48, 16)

    canonical = bytes(output)
    try:
        inspected = pkelf.inspect(
            canonical,
            physical_base=0x0200_0000,
            virtual_base=pkelf.MIN_VIRTUAL_BASE,
        )
    except pkelf.ElfError as error:
        raise KernelImageError(f"canonical_pkelf_{error.code}") from error
    if (
        inspected.entry_offset != plan.entry_offset
        or inspected.image_size != plan.image_byte_count
        or inspected.relocation_count != plan.relocation_count
    ):
        raise KernelImageError("canonical_summary")
    if canonical.count(manifest) != 1 or canonical[plan.entry_offset : plan.entry_offset + 2] != b"\xfa\xfc":
        raise KernelImageError("canonical_content")
    return canonical, plan
