"""Dependency-free PE32+ and ELF64 inspection for native qualification artifacts."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Mapping
from typing import Any


class BinaryFormatError(ValueError):
    """Raised when a binary is malformed or outside the supported subset."""


def _range(data: bytes, offset: int, size: int, label: str) -> memoryview:
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise BinaryFormatError(f"{label} extends beyond the file")
    return memoryview(data)[offset : offset + size]


def _u16(data: bytes, offset: int, label: str) -> int:
    return struct.unpack("<H", _range(data, offset, 2, label))[0]


def _u32(data: bytes, offset: int, label: str) -> int:
    return struct.unpack("<I", _range(data, offset, 4, label))[0]


def _u64(data: bytes, offset: int, label: str) -> int:
    return struct.unpack("<Q", _range(data, offset, 8, label))[0]


def _digest(data: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(data).hexdigest().upper(), "byte_count": len(data)}


def inspect_pe32_plus(data: bytes) -> dict[str, Any]:
    if bytes(_range(data, 0, 2, "DOS signature")) != b"MZ":
        raise BinaryFormatError("missing DOS MZ signature")
    pe_offset = _u32(data, 0x3C, "DOS PE offset")
    if bytes(_range(data, pe_offset, 4, "PE signature")) != b"PE\0\0":
        raise BinaryFormatError("missing PE signature")

    coff = pe_offset + 4
    machine = _u16(data, coff, "COFF machine")
    section_count = _u16(data, coff + 2, "COFF section count")
    timestamp = _u32(data, coff + 4, "COFF timestamp")
    optional_size = _u16(data, coff + 16, "COFF optional-header size")
    characteristics = _u16(data, coff + 18, "COFF characteristics")
    optional = coff + 20
    _range(data, optional, optional_size, "PE optional header")
    if optional_size < 112 or _u16(data, optional, "PE optional magic") != 0x20B:
        raise BinaryFormatError("image is not PE32+")

    entry = _u32(data, optional + 16, "PE entry point")
    image_base = _u64(data, optional + 24, "PE image base")
    section_alignment = _u32(data, optional + 32, "PE section alignment")
    file_alignment = _u32(data, optional + 36, "PE file alignment")
    image_size = _u32(data, optional + 56, "PE image size")
    header_size = _u32(data, optional + 60, "PE header size")
    subsystem = _u16(data, optional + 68, "PE subsystem")
    dll_characteristics = _u16(data, optional + 70, "PE DLL characteristics")
    directory_count = _u32(data, optional + 108, "PE data-directory count")
    import_rva = 0
    import_size = 0
    debug_rva = 0
    debug_size = 0
    if directory_count > 1:
        if optional_size < 128:
            raise BinaryFormatError("PE import directory is truncated")
        import_rva = _u32(data, optional + 120, "PE import RVA")
        import_size = _u32(data, optional + 124, "PE import size")
    if directory_count > 6:
        if optional_size < 168:
            raise BinaryFormatError("PE debug directory is truncated")
        debug_rva = _u32(data, optional + 160, "PE debug RVA")
        debug_size = _u32(data, optional + 164, "PE debug size")

    section_table = optional + optional_size
    sections: list[dict[str, Any]] = []
    for index in range(section_count):
        offset = section_table + index * 40
        header = bytes(_range(data, offset, 40, f"PE section {index}"))
        name = header[:8].split(b"\0", 1)[0].decode("ascii", errors="strict")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", header, 8)
        if raw_size:
            _range(data, raw_offset, raw_size, f"PE section {name!r} data")
        sections.append(
            {
                "name": name,
                "virtual_address": virtual_address,
                "virtual_size": virtual_size,
                "raw_offset": raw_offset,
                "raw_size": raw_size,
                "characteristics": struct.unpack_from("<I", header, 36)[0],
            }
        )

    return {
        **_digest(data),
        "format": "PE32+",
        "machine": machine,
        "section_count": section_count,
        "timestamp": timestamp,
        "entry_point": entry,
        "entry_nonzero": entry != 0,
        "image_base": image_base,
        "image_size": image_size,
        "header_size": header_size,
        "section_alignment": section_alignment,
        "file_alignment": file_alignment,
        "subsystem": subsystem,
        "characteristics": characteristics,
        "dll_characteristics": dll_characteristics,
        "imports_present": import_rva != 0 or import_size != 0,
        "import_directory": {"rva": import_rva, "size": import_size},
        "debug_directory_present": debug_rva != 0 or debug_size != 0,
        "debug_directory": {"rva": debug_rva, "size": debug_size},
        "sections": sections,
    }


def inspect_elf64(data: bytes) -> dict[str, Any]:
    ident = bytes(_range(data, 0, 16, "ELF identification"))
    if ident[:4] != b"\x7fELF":
        raise BinaryFormatError("missing ELF signature")
    if ident[4] != 2 or ident[5] != 1 or ident[6] != 1:
        raise BinaryFormatError("ELF must be 64-bit little-endian version 1")

    header = struct.unpack("<HHIQQQIHHHHHH", _range(data, 16, 48, "ELF64 header"))
    (
        elf_type,
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
        string_section_index,
    ) = header
    if header_size != 64 or version != 1:
        raise BinaryFormatError("unsupported ELF64 header")
    if program_count and program_entry_size < 56:
        raise BinaryFormatError("ELF64 program-header entries are too small")
    if section_count and section_entry_size < 64:
        raise BinaryFormatError("ELF64 section-header entries are too small")

    program_types = {0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP", 4: "NOTE", 6: "PHDR", 7: "TLS"}
    programs: list[dict[str, Any]] = []
    for index in range(program_count):
        offset = program_offset + index * program_entry_size
        values = struct.unpack("<IIQQQQQQ", _range(data, offset, 56, f"ELF program header {index}"))
        kind, program_flags, file_offset, virtual, physical, file_size, memory_size, alignment = values
        if file_size:
            _range(data, file_offset, file_size, f"ELF segment {index} data")
        programs.append(
            {
                "type": kind,
                "type_name": program_types.get(kind, "OTHER"),
                "flags": program_flags,
                "file_offset": file_offset,
                "virtual_address": virtual,
                "physical_address": physical,
                "file_size": file_size,
                "memory_size": memory_size,
                "alignment": alignment,
            }
        )

    raw_sections: list[tuple[int, ...]] = []
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        raw_sections.append(
            struct.unpack("<IIQQQQIIQQ", _range(data, offset, 64, f"ELF section header {index}"))
        )
    if section_count and string_section_index >= section_count:
        raise BinaryFormatError("ELF section-name string table index is invalid")
    string_table = b""
    if section_count:
        string_header = raw_sections[string_section_index]
        string_table = bytes(_range(data, string_header[4], string_header[5], "ELF section-name strings"))

    def section_name(offset: int) -> str:
        if offset >= len(string_table):
            raise BinaryFormatError("ELF section name extends beyond the string table")
        end = string_table.find(b"\0", offset)
        if end < 0:
            raise BinaryFormatError("ELF section name is unterminated")
        return string_table[offset:end].decode("ascii", errors="strict")

    sections: list[dict[str, Any]] = []
    for values in raw_sections:
        name_offset, kind, section_flags, address, file_offset, size, link, info, alignment, entry_size = values
        if kind != 8 and size:
            _range(data, file_offset, size, "ELF section data")
        sections.append(
            {
                "name": section_name(name_offset),
                "type": kind,
                "flags": section_flags,
                "address": address,
                "file_offset": file_offset,
                "size": size,
                "link": link,
                "info": info,
                "alignment": alignment,
                "entry_size": entry_size,
            }
        )

    program_kinds = {item["type"] for item in programs}
    return {
        **_digest(data),
        "format": "ELF64",
        "elf_type": elf_type,
        "machine": machine,
        "flags": flags,
        "entry_point": entry,
        "entry_nonzero": entry != 0,
        "program_header_count": program_count,
        "section_count": section_count,
        "dynamic_segment_present": 2 in program_kinds,
        "interpreter_segment_present": 3 in program_kinds,
        "program_headers": programs,
        "sections": sections,
    }


def inspect_binary(data: bytes) -> dict[str, Any]:
    if data.startswith(b"MZ"):
        return inspect_pe32_plus(data)
    if data.startswith(b"\x7fELF"):
        return inspect_elf64(data)
    raise BinaryFormatError("binary is neither PE32+ nor ELF64")


def validate_binary(data: bytes, expected: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        inspection = inspect_binary(data)
    except BinaryFormatError as error:
        return None, [str(error)]
    errors: list[str] = []
    for field in ("format", "machine", "subsystem", "timestamp", "elf_type"):
        if field in expected and inspection.get(field) != expected[field]:
            errors.append(f"{field}: expected {expected[field]!r}, got {inspection.get(field)!r}")
    for field in (
        "entry_nonzero",
        "imports_present",
        "debug_directory_present",
        "dynamic_segment_present",
        "interpreter_segment_present",
    ):
        if field in expected and inspection.get(field) is not expected[field]:
            errors.append(f"{field}: expected {expected[field]!r}, got {inspection.get(field)!r}")
    return inspection, errors


def scan_forbidden_markers(data: bytes, markers: Mapping[str, str | bytes]) -> list[dict[str, str]]:
    folded = data.lower()
    hits: list[dict[str, str]] = []
    for marker_id, raw_marker in markers.items():
        marker = raw_marker if isinstance(raw_marker, bytes) else raw_marker.encode("utf-8")
        if not marker:
            continue
        ascii_marker = marker.lower()
        utf16_marker = marker.decode("utf-8", errors="strict").encode("utf-16le").lower()
        if ascii_marker in folded:
            hits.append({"marker_id": marker_id, "encoding": "utf8_or_ascii"})
        if utf16_marker in folded:
            hits.append({"marker_id": marker_id, "encoding": "utf16le"})
    return sorted(hits, key=lambda item: (item["marker_id"], item["encoding"]))
