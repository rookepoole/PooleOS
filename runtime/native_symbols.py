"""Independent PSYM1 public diagnostic-symbol bundle and ELF debug oracle."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Final, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("specs/native-symbol-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-symbol-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-symbol-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-symbol-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_symbol_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-symbol-readiness.schema.json")

CONTRACT_ID: Final = "PSYM1"
MAGIC: Final = b"PSYM1\0\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 384
SEGMENT_BYTES: Final = 32
SYMBOL_BYTES: Final = 48
MAX_BUNDLE_BYTES: Final = 512 * 1024
MAX_IMAGE_BYTES: Final = 64 * 1024 * 1024
MAX_SEGMENTS: Final = 16
MAX_SYMBOLS: Final = 4096
MAX_NAME_BYTES: Final = 127
MAX_STRING_BYTES: Final = 256 * 1024
MAX_LOOKUP_STEPS: Final = 13

PROFILE_PUBLIC_DIAGNOSTIC: Final = 1
ADDRESS_IMAGE_RELATIVE: Final = 1
NAME_ASCII_OPAQUE: Final = 1
PRIVACY_PUBLIC: Final = 1
LOOKUP_BINARY_SEARCH: Final = 1
MANGLING_OPAQUE_LINKER: Final = 1
POINTER_REDACT_RUNTIME: Final = 1

FLAG_IMAGE_RELATIVE: Final = 1 << 0
FLAG_KERNEL_IDENTITY_BOUND: Final = 1 << 1
FLAG_BUILD_ID_BOUND: Final = 1 << 2
FLAG_SPLIT_DEBUG_BOUND: Final = 1 << 3
FLAG_STRIPPED_PRODUCT: Final = 1 << 4
FLAG_SORTED_NONOVERLAP: Final = 1 << 5
FLAG_BOUNDED_LOOKUP: Final = 1 << 6
FLAG_ASCII_OPAQUE_NAMES: Final = 1 << 7
FLAG_NO_SOURCE_PATHS: Final = 1 << 8
FLAG_POINTER_REDACTION_DEFAULT: Final = 1 << 9
FLAG_DIAGNOSTIC_ONLY: Final = 1 << 10
FLAG_NO_AUTHORITY: Final = 1 << 11
FLAG_OUTER_SIGNATURE: Final = 1 << 12
FLAG_INNER_SIGNATURE: Final = 1 << 13
FLAG_MANIFEST_SIGNATURE: Final = 1 << 14
REQUIRED_FLAGS: Final = (
    FLAG_IMAGE_RELATIVE
    | FLAG_KERNEL_IDENTITY_BOUND
    | FLAG_BUILD_ID_BOUND
    | FLAG_SPLIT_DEBUG_BOUND
    | FLAG_STRIPPED_PRODUCT
    | FLAG_SORTED_NONOVERLAP
    | FLAG_BOUNDED_LOOKUP
    | FLAG_ASCII_OPAQUE_NAMES
    | FLAG_NO_SOURCE_PATHS
    | FLAG_POINTER_REDACTION_DEFAULT
    | FLAG_DIAGNOSTIC_ONLY
    | FLAG_NO_AUTHORITY
    | FLAG_OUTER_SIGNATURE
    | FLAG_INNER_SIGNATURE
    | FLAG_MANIFEST_SIGNATURE
)

SEGMENT_READ: Final = 1 << 0
SEGMENT_WRITE: Final = 1 << 1
SEGMENT_EXECUTE: Final = 1 << 2
SEGMENT_RELRO: Final = 1 << 3
SEGMENT_KNOWN_FLAGS: Final = SEGMENT_READ | SEGMENT_WRITE | SEGMENT_EXECUTE | SEGMENT_RELRO
SEGMENT_RODATA: Final = 1
SEGMENT_TEXT: Final = 2
SEGMENT_RELRO_DATA: Final = 3
SEGMENT_DATA_BSS: Final = 4
SEGMENT_FLAGS_BY_KIND: Final = {
    SEGMENT_RODATA: SEGMENT_READ,
    SEGMENT_TEXT: SEGMENT_READ | SEGMENT_EXECUTE,
    SEGMENT_RELRO_DATA: SEGMENT_READ | SEGMENT_RELRO,
    SEGMENT_DATA_BSS: SEGMENT_READ | SEGMENT_WRITE,
}

SYMBOL_FUNCTION: Final = 1
SYMBOL_OBJECT: Final = 2
BIND_GLOBAL: Final = 1
VISIBILITY_DEFAULT: Final = 0
SYMBOL_EXECUTABLE: Final = 1 << 0
SYMBOL_ENTRY: Final = 1 << 1
SYMBOL_PANIC_SAFE: Final = 1 << 2
SYMBOL_DIAGNOSTIC_PUBLIC: Final = 1 << 3
SYMBOL_KNOWN_FLAGS: Final = (
    SYMBOL_EXECUTABLE | SYMBOL_ENTRY | SYMBOL_PANIC_SAFE | SYMBOL_DIAGNOSTIC_PUBLIC
)

PREFERRED_VIRTUAL_BASE: Final = 0xFFFF_FFFF_8000_0000
VIRTUAL_WINDOW_END_EXCLUSIVE: Final = 0xFFFF_FFFF_C000_0000
SLIDE_ALIGNMENT: Final = 2 * 1024 * 1024

CANONICAL_IMAGE_BYTES: Final = 262_144
CANONICAL_ENTRY_OFFSET: Final = 0x8000
CANONICAL_FILE_SHA256: Final = "8DE68D5A5F9D71DBA57843B0AA55C9A42207C4026D69B6383B3C751DC5E434FA"
CANONICAL_LOADED_SHA256: Final = "D8B7F49D034234A1C31CA9697380E6913CB21A3298FCEE9C049DD518C63433D4"
CANONICAL_BUILD_ID: Final = "PKBUILD1-CYCLE126-N9-VM-001"
CANONICAL_BUILD_ID_SHA256: Final = "5DB9BEA804A72E7CA7A90E516FAB013DAC677582C3F779E60E657AC759857F26"
CANONICAL_DEBUG_SHA256: Final = "31DCD4CC92C786097E010C14BCADDAD4291EC0B429248D0D842CA2D27ADDBE0D"
CANONICAL_DEBUG_BYTES: Final = 3_986_944
CANONICAL_SOURCE_MANIFEST_SHA256: Final = (
    "014C3E197EB197C5D189BCF2D619A7A9A9BE5ACA0564A94937F8E02272F5EA2D"
)
PUBLIC_SYMBOL_NAMES: Final = (
    "poole_kernel_entry",
    "poole_kernel_emergency_panic",
    "poole_kernel_rust_entry",
)

REQUIRED_DWARF5_SECTIONS: Final = (
    ".debug_abbrev",
    ".debug_info",
    ".debug_line",
    ".debug_loclists",
    ".debug_names",
    ".debug_rnglists",
    ".debug_str",
    ".symtab",
    ".strtab",
)

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/symbols/Cargo.toml",
    "native/symbols/src/lib.rs",
    "native/symbols/src/bin/psym1_probe.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "runtime/native_symbols.py",
    "runtime/native_boot_artifact.py",
    "tools/generate_native_symbol_vectors.py",
    "tools/qualify_native_symbols.py",
    "tests/test_native_symbols.py",
    "docs/native-symbol-bundle.md",
)


class SymbolError(RuntimeError):
    """Raised when PSYM1, debug ELF, lookup, or consumption violates the contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Identity:
    canonical_file_sha256: str
    preferred_loaded_sha256: str
    build_id_sha256: str
    debug_file_sha256: str
    source_manifest_sha256: str


@dataclasses.dataclass(frozen=True)
class Segment:
    segment_id: int
    kind: int
    flags: int
    start_offset: int
    byte_count: int


@dataclasses.dataclass(frozen=True)
class Symbol:
    symbol_id: int
    segment_id: int
    kind: int
    binding: int
    visibility: int
    privacy: int
    flags: int
    start_offset: int
    byte_count: int
    name: str


@dataclasses.dataclass(frozen=True)
class Bundle:
    raw: bytes
    flags: int
    image_bytes: int
    preferred_virtual_base: int
    virtual_window_end_exclusive: int
    slide_alignment: int
    entry_offset: int
    identity: Identity
    segments: tuple[Segment, ...]
    symbols: tuple[Symbol, ...]


@dataclasses.dataclass(frozen=True)
class LookupResult:
    symbol: Symbol
    symbol_offset: int
    steps: int


@dataclasses.dataclass(frozen=True)
class ConsumptionContext:
    outer_role: int
    outer_version: int
    outer_payload_sha256: str
    outer_file_sha256: str
    expected_outer_file_sha256: str
    outer_signature_verified: bool
    inner_signature_verified: bool
    manifest_signature_verified: bool
    kernel_signature_verified: bool
    canonical_file_sha256: str
    preferred_loaded_sha256: str
    build_id_sha256: str
    debug_file_sha256: str
    source_manifest_sha256: str
    identity_evidence_verified: bool
    stripped_correspondence_verified: bool
    dwarf5_verified: bool
    public_policy_verified: bool
    source_paths_absent: bool
    pointer_redaction_enabled: bool
    diagnostics_authorized: bool
    runtime_base: int
    symbol_capacity: int
    string_capacity: int
    lookup_step_capacity: int
    authority_effect_requested: bool


@dataclasses.dataclass(frozen=True)
class ElfSection:
    name: str
    section_type: int
    offset: int
    byte_count: int
    link: int
    entry_bytes: int


@dataclasses.dataclass(frozen=True)
class ElfSymbol:
    name: str
    binding: int
    kind: int
    visibility: int
    section_index: int
    value: int
    byte_count: int


@dataclasses.dataclass(frozen=True)
class DebugElf:
    byte_count: int
    sha256: str
    sections: tuple[ElfSection, ...]
    symbols: tuple[ElfSymbol, ...]
    dwarf_versions: tuple[int, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "ascii"
    )


def _digest_bytes(value: str) -> bytes:
    if len(value) != 64:
        raise SymbolError("psym_identity")
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise SymbolError("psym_identity") from error
    if result == bytes(32):
        raise SymbolError("psym_identity")
    return result


def _name_allowed(data: bytes) -> bool:
    return bool(data) and all(
        48 <= byte <= 57
        or 65 <= byte <= 90
        or 97 <= byte <= 122
        or byte in b"_.$@-"
        for byte in data
    ) and data[0] not in b".$@-"


def _name_fingerprint(data: bytes) -> int:
    return int.from_bytes(hashlib.sha256(data).digest()[:4], "little")


def _checked_end(start: int, size: int, maximum: int, code: str) -> int:
    if start < 0 or size <= 0 or start > maximum or size > maximum - start:
        raise SymbolError(code)
    return start + size


def _is_canonical_x86_64(value: int) -> bool:
    value &= 0xFFFF_FFFF_FFFF_FFFF
    upper = value >> 48
    sign = (value >> 47) & 1
    return upper == (0xFFFF if sign else 0)


def encode(
    *,
    identity: Identity,
    segments: Iterable[Segment],
    symbols: Iterable[Symbol],
    image_bytes: int,
    entry_offset: int,
    preferred_virtual_base: int = PREFERRED_VIRTUAL_BASE,
    virtual_window_end_exclusive: int = VIRTUAL_WINDOW_END_EXCLUSIVE,
    slide_alignment: int = SLIDE_ALIGNMENT,
) -> bytes:
    segment_items = tuple(segments)
    symbol_items = tuple(symbols)
    if not 1 <= len(segment_items) <= MAX_SEGMENTS or not 1 <= len(symbol_items) <= MAX_SYMBOLS:
        raise SymbolError("psym_counts")

    names = bytearray()
    symbol_rows = bytearray(len(symbol_items) * SYMBOL_BYTES)
    for index, symbol in enumerate(symbol_items):
        try:
            name = symbol.name.encode("ascii")
        except UnicodeEncodeError as error:
            raise SymbolError("psym_symbol_name_ascii") from error
        name_offset = len(names)
        names.extend(name)
        struct.pack_into(
            "<IHBBBBHIHHIQQQ",
            symbol_rows,
            index * SYMBOL_BYTES,
            symbol.symbol_id,
            symbol.segment_id,
            symbol.kind,
            symbol.binding,
            symbol.visibility,
            symbol.privacy,
            symbol.flags,
            name_offset,
            len(name),
            0,
            _name_fingerprint(name),
            symbol.start_offset,
            symbol.byte_count,
            0,
        )

    segment_rows = bytearray(len(segment_items) * SEGMENT_BYTES)
    for index, segment in enumerate(segment_items):
        struct.pack_into(
            "<HHIQQQ",
            segment_rows,
            index * SEGMENT_BYTES,
            segment.segment_id,
            segment.kind,
            segment.flags,
            segment.start_offset,
            segment.byte_count,
            0,
        )

    segment_offset = HEADER_BYTES
    symbol_offset = segment_offset + len(segment_rows)
    string_offset = symbol_offset + len(symbol_rows)
    total_bytes = string_offset + len(names)
    if not names or len(names) > MAX_STRING_BYTES or total_bytes > MAX_BUNDLE_BYTES:
        raise SymbolError("psym_string_size")
    output = bytearray(total_bytes)
    output[:8] = MAGIC
    struct.pack_into("<HHHHHH", output, 8, MAJOR_VERSION, MINOR_VERSION, HEADER_BYTES, SEGMENT_BYTES, SYMBOL_BYTES, 0)
    struct.pack_into("<I", output, 20, REQUIRED_FLAGS)
    struct.pack_into(
        "<HHHHII",
        output,
        24,
        PROFILE_PUBLIC_DIAGNOSTIC,
        ADDRESS_IMAGE_RELATIVE,
        NAME_ASCII_OPAQUE,
        PRIVACY_PUBLIC,
        len(segment_items),
        len(symbol_items),
    )
    struct.pack_into(
        "<QQQQQQQQQQ",
        output,
        40,
        total_bytes,
        segment_offset,
        symbol_offset,
        string_offset,
        len(names),
        image_bytes,
        preferred_virtual_base,
        virtual_window_end_exclusive,
        slide_alignment,
        entry_offset,
    )
    struct.pack_into(
        "<IIIIHHHH",
        output,
        120,
        MAX_SEGMENTS,
        MAX_SYMBOLS,
        MAX_NAME_BYTES,
        MAX_LOOKUP_STEPS,
        LOOKUP_BINARY_SEARCH,
        MANGLING_OPAQUE_LINKER,
        POINTER_REDACT_RUNTIME,
        0,
    )
    output[144:176] = _digest_bytes(identity.canonical_file_sha256)
    output[176:208] = _digest_bytes(identity.preferred_loaded_sha256)
    output[208:240] = _digest_bytes(identity.build_id_sha256)
    output[240:272] = _digest_bytes(identity.debug_file_sha256)
    output[272:304] = _digest_bytes(identity.source_manifest_sha256)
    output[segment_offset:symbol_offset] = segment_rows
    output[symbol_offset:string_offset] = symbol_rows
    output[string_offset:] = names
    output[304:336] = hashlib.sha256(output[HEADER_BYTES:]).digest()
    result = bytes(output)
    parse(result)
    return result


def parse(data: bytes) -> Bundle:
    if len(data) < HEADER_BYTES:
        raise SymbolError("psym_truncated")
    if len(data) > MAX_BUNDLE_BYTES:
        raise SymbolError("psym_oversized")
    if data[:8] != MAGIC:
        raise SymbolError("psym_magic")
    major, minor = struct.unpack_from("<HH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        raise SymbolError("psym_version")
    header_bytes, segment_bytes, symbol_bytes, header_reserved = struct.unpack_from("<HHHH", data, 12)
    if header_bytes != HEADER_BYTES:
        raise SymbolError("psym_header_size")
    if (segment_bytes, symbol_bytes) != (SEGMENT_BYTES, SYMBOL_BYTES):
        raise SymbolError("psym_record_size")
    if header_reserved != 0:
        raise SymbolError("psym_reserved")
    flags = struct.unpack_from("<I", data, 20)[0]
    if flags != REQUIRED_FLAGS:
        raise SymbolError("psym_flags")
    profile, address_model, name_encoding, privacy = struct.unpack_from("<HHHH", data, 24)
    if profile != PROFILE_PUBLIC_DIAGNOSTIC:
        raise SymbolError("psym_profile")
    if address_model != ADDRESS_IMAGE_RELATIVE:
        raise SymbolError("psym_address_model")
    if name_encoding != NAME_ASCII_OPAQUE:
        raise SymbolError("psym_name_encoding")
    if privacy != PRIVACY_PUBLIC:
        raise SymbolError("psym_privacy")
    segment_count, symbol_count = struct.unpack_from("<II", data, 32)
    if not 1 <= segment_count <= MAX_SEGMENTS or not 1 <= symbol_count <= MAX_SYMBOLS:
        raise SymbolError("psym_counts")
    (
        total_bytes,
        segment_offset,
        symbol_offset,
        string_offset,
        string_bytes,
        image_bytes,
        preferred_base,
        window_end,
        slide_alignment,
        entry_offset,
    ) = struct.unpack_from("<QQQQQQQQQQ", data, 40)
    if total_bytes != len(data):
        raise SymbolError("psym_total_size")
    expected_symbol_offset = HEADER_BYTES + segment_count * SEGMENT_BYTES
    expected_string_offset = expected_symbol_offset + symbol_count * SYMBOL_BYTES
    if (
        segment_offset != HEADER_BYTES
        or symbol_offset != expected_symbol_offset
        or string_offset != expected_string_offset
        or string_offset > len(data)
    ):
        raise SymbolError("psym_table_layout")
    if string_bytes == 0 or string_bytes > MAX_STRING_BYTES or string_bytes != len(data) - string_offset:
        raise SymbolError("psym_string_size")
    max_segments, max_symbols, max_name, max_steps = struct.unpack_from("<IIII", data, 120)
    if (max_segments, max_symbols, max_name, max_steps) != (
        MAX_SEGMENTS,
        MAX_SYMBOLS,
        MAX_NAME_BYTES,
        MAX_LOOKUP_STEPS,
    ):
        raise SymbolError("psym_bounds")
    lookup, mangling, pointer_policy, policy_reserved = struct.unpack_from("<HHHH", data, 136)
    if (lookup, mangling, pointer_policy) != (
        LOOKUP_BINARY_SEARCH,
        MANGLING_OPAQUE_LINKER,
        POINTER_REDACT_RUNTIME,
    ):
        raise SymbolError("psym_lookup_policy")
    if policy_reserved != 0:
        raise SymbolError("psym_reserved")
    if image_bytes == 0 or image_bytes > MAX_IMAGE_BYTES:
        raise SymbolError("psym_image_size")
    if (
        not _is_canonical_x86_64(preferred_base)
        or not _is_canonical_x86_64(window_end - 1)
        or preferred_base >= window_end
        or image_bytes > window_end - preferred_base
    ):
        raise SymbolError("psym_virtual_window")
    if (
        slide_alignment < 4096
        or slide_alignment & (slide_alignment - 1)
        or preferred_base % slide_alignment
    ):
        raise SymbolError("psym_slide_alignment")
    if entry_offset >= image_bytes:
        raise SymbolError("psym_entry_offset")
    identity_bytes = (data[144:176], data[176:208], data[208:240], data[240:272], data[272:304])
    if any(value == bytes(32) for value in identity_bytes):
        raise SymbolError("psym_identity")
    if any(data[336:HEADER_BYTES]):
        raise SymbolError("psym_reserved")
    if hashlib.sha256(data[HEADER_BYTES:]).digest() != data[304:336]:
        raise SymbolError("psym_body_digest")

    segments: list[Segment] = []
    previous_end = 0
    for index in range(segment_count):
        offset = segment_offset + index * SEGMENT_BYTES
        segment_id, kind, segment_flags, start, size, reserved = struct.unpack_from("<HHIQQQ", data, offset)
        if segment_id != index + 1:
            raise SymbolError("psym_segment_id")
        if kind not in SEGMENT_FLAGS_BY_KIND:
            raise SymbolError("psym_segment_kind")
        if segment_flags & ~SEGMENT_KNOWN_FLAGS or segment_flags != SEGMENT_FLAGS_BY_KIND[kind]:
            raise SymbolError("psym_segment_flags")
        if segment_flags & SEGMENT_WRITE and segment_flags & SEGMENT_EXECUTE:
            raise SymbolError("psym_segment_flags")
        if start != previous_end:
            raise SymbolError("psym_segment_order")
        end = _checked_end(start, size, image_bytes, "psym_segment_range")
        if reserved != 0:
            raise SymbolError("psym_reserved")
        segments.append(Segment(segment_id, kind, segment_flags, start, size))
        previous_end = end
    if previous_end != image_bytes:
        raise SymbolError("psym_segment_coverage")

    symbols: list[Symbol] = []
    expected_name_offset = 0
    previous_symbol_end = 0
    entry_count = 0
    for index in range(symbol_count):
        offset = symbol_offset + index * SYMBOL_BYTES
        (
            symbol_id,
            segment_id,
            kind,
            binding,
            visibility,
            symbol_privacy,
            symbol_flags,
            name_offset,
            name_bytes,
            record_reserved,
            name_fingerprint,
            start,
            size,
            trailing_reserved,
        ) = struct.unpack_from("<IHBBBBHIHHIQQQ", data, offset)
        if symbol_id != index + 1:
            raise SymbolError("psym_symbol_id")
        if not 1 <= segment_id <= segment_count:
            raise SymbolError("psym_symbol_segment")
        if kind not in (SYMBOL_FUNCTION, SYMBOL_OBJECT):
            raise SymbolError("psym_symbol_kind")
        if binding != BIND_GLOBAL:
            raise SymbolError("psym_symbol_binding")
        if visibility != VISIBILITY_DEFAULT:
            raise SymbolError("psym_symbol_visibility")
        if symbol_privacy != PRIVACY_PUBLIC:
            raise SymbolError("psym_symbol_privacy")
        if symbol_flags & ~SYMBOL_KNOWN_FLAGS or not symbol_flags & SYMBOL_DIAGNOSTIC_PUBLIC:
            raise SymbolError("psym_symbol_flags")
        if name_offset != expected_name_offset:
            raise SymbolError("psym_symbol_name_layout")
        if name_bytes == 0 or name_bytes > MAX_NAME_BYTES or name_bytes > string_bytes - name_offset:
            raise SymbolError("psym_symbol_name_size")
        if record_reserved != 0 or trailing_reserved != 0:
            raise SymbolError("psym_reserved")
        name_data = data[string_offset + name_offset : string_offset + name_offset + name_bytes]
        if not _name_allowed(name_data):
            raise SymbolError("psym_symbol_name_ascii")
        if _name_fingerprint(name_data) != name_fingerprint:
            raise SymbolError("psym_symbol_name_fingerprint")
        end = _checked_end(start, size, image_bytes, "psym_symbol_range")
        if index and start < previous_symbol_end:
            raise SymbolError("psym_symbol_order")
        segment = segments[segment_id - 1]
        segment_end = segment.start_offset + segment.byte_count
        if start < segment.start_offset or end > segment_end:
            raise SymbolError("psym_symbol_segment_range")
        executable = bool(segment.flags & SEGMENT_EXECUTE)
        if kind == SYMBOL_FUNCTION:
            if not executable or not symbol_flags & SYMBOL_EXECUTABLE:
                raise SymbolError("psym_symbol_permissions")
        elif executable or symbol_flags & SYMBOL_EXECUTABLE:
            raise SymbolError("psym_symbol_permissions")
        try:
            name = name_data.decode("ascii")
        except UnicodeDecodeError as error:
            raise SymbolError("psym_symbol_name_ascii") from error
        if symbol_flags & SYMBOL_ENTRY:
            entry_count += 1
            if start != entry_offset or kind != SYMBOL_FUNCTION or name != "poole_kernel_entry":
                raise SymbolError("psym_entry_symbol")
        symbols.append(
            Symbol(
                symbol_id,
                segment_id,
                kind,
                binding,
                visibility,
                symbol_privacy,
                symbol_flags,
                start,
                size,
                name,
            )
        )
        expected_name_offset += name_bytes
        previous_symbol_end = end
    if expected_name_offset != string_bytes:
        raise SymbolError("psym_string_coverage")
    if entry_count != 1:
        raise SymbolError("psym_entry_symbol")

    return Bundle(
        bytes(data),
        flags,
        image_bytes,
        preferred_base,
        window_end,
        slide_alignment,
        entry_offset,
        Identity(*(value.hex().upper() for value in identity_bytes)),
        tuple(segments),
        tuple(symbols),
    )


def summary(bundle: Bundle) -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "version": f"{MAJOR_VERSION}.{MINOR_VERSION}",
        "bundle_bytes": len(bundle.raw),
        "segment_count": len(bundle.segments),
        "symbol_count": len(bundle.symbols),
        "string_bytes": sum(len(item.name) for item in bundle.symbols),
        "image_bytes": bundle.image_bytes,
        "entry_offset": bundle.entry_offset,
        "preferred_virtual_base": bundle.preferred_virtual_base,
        "virtual_window_end_exclusive": bundle.virtual_window_end_exclusive,
        "slide_alignment": bundle.slide_alignment,
        "canonical_file_sha256": bundle.identity.canonical_file_sha256,
        "preferred_loaded_sha256": bundle.identity.preferred_loaded_sha256,
        "build_id_sha256": bundle.identity.build_id_sha256,
        "debug_file_sha256": bundle.identity.debug_file_sha256,
        "source_manifest_sha256": bundle.identity.source_manifest_sha256,
        "body_sha256": bundle.raw[304:336].hex().upper(),
    }


def lookup(bundle: Bundle, runtime_base: int, runtime_address: int) -> LookupResult | None:
    if (
        runtime_base < bundle.preferred_virtual_base
        or runtime_base > bundle.virtual_window_end_exclusive - bundle.image_bytes
        or (runtime_base - bundle.preferred_virtual_base) % bundle.slide_alignment
        or not _is_canonical_x86_64(runtime_base)
    ):
        raise SymbolError("psym_lookup_base")
    if (
        runtime_address < runtime_base
        or runtime_address >= runtime_base + bundle.image_bytes
        or not _is_canonical_x86_64(runtime_address)
    ):
        raise SymbolError("psym_lookup_address")
    target = runtime_address - runtime_base
    low = 0
    high = len(bundle.symbols)
    steps = 0
    while low < high:
        steps += 1
        if steps > MAX_LOOKUP_STEPS:
            raise SymbolError("psym_lookup_bound")
        middle = low + (high - low) // 2
        symbol = bundle.symbols[middle]
        if target < symbol.start_offset:
            high = middle
        elif target >= symbol.start_offset + symbol.byte_count:
            low = middle + 1
        else:
            return LookupResult(symbol, target - symbol.start_offset, steps)
    return None


def format_lookup(result: LookupResult | None) -> str:
    if result is None:
        return "unknown"
    return f"{result.symbol.name}+0x{result.symbol_offset:X}"


def development_consumption_context(bundle: Bundle, *, outer_file_sha256: str = "0" * 64) -> ConsumptionContext:
    payload = sha256_bytes(bundle.raw)
    return ConsumptionContext(
        4,
        1,
        payload,
        outer_file_sha256,
        outer_file_sha256,
        False,
        False,
        False,
        False,
        bundle.identity.canonical_file_sha256,
        bundle.identity.preferred_loaded_sha256,
        bundle.identity.build_id_sha256,
        bundle.identity.debug_file_sha256,
        bundle.identity.source_manifest_sha256,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        bundle.preferred_virtual_base,
        len(bundle.symbols),
        sum(len(item.name) for item in bundle.symbols),
        MAX_LOOKUP_STEPS,
        False,
    )


def synthetic_qualified_consumption_context(
    bundle: Bundle, *, outer_file_sha256: str = "A" * 64
) -> ConsumptionContext:
    return dataclasses.replace(
        development_consumption_context(bundle, outer_file_sha256=outer_file_sha256),
        outer_signature_verified=True,
        inner_signature_verified=True,
        manifest_signature_verified=True,
        kernel_signature_verified=True,
        identity_evidence_verified=True,
        stripped_correspondence_verified=True,
        dwarf5_verified=True,
        public_policy_verified=True,
        source_paths_absent=True,
        pointer_redaction_enabled=True,
        diagnostics_authorized=True,
    )


def consumption_errors(bundle: Bundle, context: ConsumptionContext) -> list[str]:
    checks = (
        (context.outer_signature_verified, "psym_activation_outer_signature"),
        (context.inner_signature_verified, "psym_activation_inner_signature"),
        (context.manifest_signature_verified, "psym_activation_manifest_signature"),
        (context.kernel_signature_verified, "psym_activation_kernel_signature"),
        (context.outer_role == 4, "psym_activation_outer_role"),
        (context.outer_version == MAJOR_VERSION, "psym_activation_outer_version"),
        (context.outer_payload_sha256 == sha256_bytes(bundle.raw), "psym_activation_outer_payload_digest"),
        (
            context.outer_file_sha256 == context.expected_outer_file_sha256
            and context.outer_file_sha256 != "0" * 64,
            "psym_activation_outer_file_digest",
        ),
        (
            context.canonical_file_sha256 == bundle.identity.canonical_file_sha256,
            "psym_activation_canonical_identity",
        ),
        (
            context.preferred_loaded_sha256 == bundle.identity.preferred_loaded_sha256,
            "psym_activation_loaded_identity",
        ),
        (context.build_id_sha256 == bundle.identity.build_id_sha256, "psym_activation_build_id"),
        (context.debug_file_sha256 == bundle.identity.debug_file_sha256, "psym_activation_debug_identity"),
        (
            context.source_manifest_sha256 == bundle.identity.source_manifest_sha256,
            "psym_activation_source_identity",
        ),
        (context.identity_evidence_verified, "psym_activation_identity_evidence"),
        (context.stripped_correspondence_verified, "psym_activation_stripped_correspondence"),
        (context.dwarf5_verified, "psym_activation_dwarf5"),
        (context.public_policy_verified, "psym_activation_public_policy"),
        (context.source_paths_absent, "psym_activation_source_paths"),
        (context.pointer_redaction_enabled, "psym_activation_pointer_redaction"),
        (context.diagnostics_authorized, "psym_activation_diagnostics_authority"),
        (
            bundle.preferred_virtual_base
            <= context.runtime_base
            <= bundle.virtual_window_end_exclusive - bundle.image_bytes
            and (context.runtime_base - bundle.preferred_virtual_base) % bundle.slide_alignment == 0,
            "psym_activation_runtime_base",
        ),
        (context.symbol_capacity >= len(bundle.symbols), "psym_activation_symbol_capacity"),
        (
            context.string_capacity >= sum(len(item.name) for item in bundle.symbols),
            "psym_activation_string_capacity",
        ),
        (context.lookup_step_capacity >= MAX_LOOKUP_STEPS, "psym_activation_lookup_capacity"),
        (not context.authority_effect_requested, "psym_activation_authority_effect"),
    )
    return [code for passed, code in checks if not passed]


def authorize_consumption(bundle: Bundle, context: ConsumptionContext) -> None:
    errors = consumption_errors(bundle, context)
    if errors:
        raise SymbolError(errors[0])


def canonical_segments() -> tuple[Segment, ...]:
    return (
        Segment(1, SEGMENT_RODATA, SEGMENT_READ, 0, 0x8000),
        Segment(2, SEGMENT_TEXT, SEGMENT_READ | SEGMENT_EXECUTE, 0x8000, 0x25000),
        Segment(3, SEGMENT_RELRO_DATA, SEGMENT_READ | SEGMENT_RELRO, 0x2D000, 0x5000),
        Segment(4, SEGMENT_DATA_BSS, SEGMENT_READ | SEGMENT_WRITE, 0x32000, 0xE000),
    )


def canonical_symbols() -> tuple[Symbol, ...]:
    public = SYMBOL_EXECUTABLE | SYMBOL_DIAGNOSTIC_PUBLIC
    return (
        Symbol(1, 2, SYMBOL_FUNCTION, BIND_GLOBAL, VISIBILITY_DEFAULT, PRIVACY_PUBLIC, public | SYMBOL_ENTRY, 0x8000, 71, "poole_kernel_entry"),
        Symbol(2, 2, SYMBOL_FUNCTION, BIND_GLOBAL, VISIBILITY_DEFAULT, PRIVACY_PUBLIC, public | SYMBOL_PANIC_SAFE, 0xB773, 198, "poole_kernel_emergency_panic"),
        Symbol(3, 2, SYMBOL_FUNCTION, BIND_GLOBAL, VISIBILITY_DEFAULT, PRIVACY_PUBLIC, public, 0xB839, 16238, "poole_kernel_rust_entry"),
    )


def canonical_identity() -> Identity:
    return Identity(
        CANONICAL_FILE_SHA256,
        CANONICAL_LOADED_SHA256,
        CANONICAL_BUILD_ID_SHA256,
        CANONICAL_DEBUG_SHA256,
        CANONICAL_SOURCE_MANIFEST_SHA256,
    )


def canonical_bundle() -> bytes:
    return encode(
        identity=canonical_identity(),
        segments=canonical_segments(),
        symbols=canonical_symbols(),
        image_bytes=CANONICAL_IMAGE_BYTES,
        entry_offset=CANONICAL_ENTRY_OFFSET,
    )


def _fixture_digest(label: str) -> str:
    return sha256_bytes(("PSYM1-FIXTURE/" + label).encode("ascii"))


def minimal_bundle() -> bytes:
    identity = Identity(*(_fixture_digest(f"minimal/{index}") for index in range(5)))
    return encode(
        identity=identity,
        segments=(Segment(1, SEGMENT_TEXT, SEGMENT_READ | SEGMENT_EXECUTE, 0, 4096),),
        symbols=(
            Symbol(
                1,
                1,
                SYMBOL_FUNCTION,
                BIND_GLOBAL,
                VISIBILITY_DEFAULT,
                PRIVACY_PUBLIC,
                SYMBOL_EXECUTABLE | SYMBOL_ENTRY | SYMBOL_DIAGNOSTIC_PUBLIC,
                0,
                64,
                "poole_kernel_entry",
            ),
        ),
        image_bytes=4096,
        entry_offset=0,
    )


def boundary_bundle() -> bytes:
    identity = Identity(*(_fixture_digest(f"boundary/{index}") for index in range(5)))
    max_name = "P" + "A" * (MAX_NAME_BYTES - 1)
    return encode(
        identity=identity,
        segments=(
            Segment(1, SEGMENT_TEXT, SEGMENT_READ | SEGMENT_EXECUTE, 0, 8192),
            Segment(2, SEGMENT_DATA_BSS, SEGMENT_READ | SEGMENT_WRITE, 8192, 4096),
        ),
        symbols=(
            Symbol(1, 1, SYMBOL_FUNCTION, BIND_GLOBAL, VISIBILITY_DEFAULT, PRIVACY_PUBLIC, SYMBOL_EXECUTABLE | SYMBOL_ENTRY | SYMBOL_DIAGNOSTIC_PUBLIC, 0, 32, "poole_kernel_entry"),
            Symbol(2, 1, SYMBOL_FUNCTION, BIND_GLOBAL, VISIBILITY_DEFAULT, PRIVACY_PUBLIC, SYMBOL_EXECUTABLE | SYMBOL_DIAGNOSTIC_PUBLIC, 4096, 128, max_name),
            Symbol(3, 2, SYMBOL_OBJECT, BIND_GLOBAL, VISIBILITY_DEFAULT, PRIVACY_PUBLIC, SYMBOL_DIAGNOSTIC_PUBLIC, 8192, 64, "POOLE_PUBLIC_STATE"),
        ),
        image_bytes=12_288,
        entry_offset=0,
    )


def expected_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_symbol_contract",
        "contract_id": CONTRACT_ID,
        "status": "candidate_pre_abi_non_promoting",
        "production_ready": False,
        "layout": {
            "byte_order": "little_endian",
            "header_bytes": HEADER_BYTES,
            "segment_record_bytes": SEGMENT_BYTES,
            "symbol_record_bytes": SYMBOL_BYTES,
            "maximum_bundle_bytes": MAX_BUNDLE_BYTES,
            "maximum_image_bytes": MAX_IMAGE_BYTES,
            "maximum_segments": MAX_SEGMENTS,
            "maximum_symbols": MAX_SYMBOLS,
            "maximum_name_bytes": MAX_NAME_BYTES,
            "maximum_string_bytes": MAX_STRING_BYTES,
            "body_digest": "SHA-256",
        },
        "address_model": {
            "architecture": "x86_64",
            "encoding": "image_relative_virtual_offset",
            "preferred_virtual_base": PREFERRED_VIRTUAL_BASE,
            "virtual_window_end_exclusive": VIRTUAL_WINDOW_END_EXCLUSIVE,
            "slide_alignment": SLIDE_ALIGNMENT,
            "runtime_base_required_for_lookup": True,
        },
        "identity_policy": {
            "bound_digests": [
                "canonical_stripped_PKELF1",
                "preferred_loaded_image",
                "kernel_build_id",
                "full_split_debug_ELF",
                "source_manifest",
            ],
            "zero_digest_prohibited": True,
            "outer_inner_manifest_and_kernel_signatures_required_for_consumption": True,
        },
        "debug_policy": {
            "pooleos_compilation_units": "DWARF_5",
            "prebuilt_rust_sysroot_units_observed": "DWARF_4",
            "required_sections": list(REQUIRED_DWARF5_SECTIONS),
            "stripped_product_correspondence_required": True,
            "full_debug_file_on_boot_media": False,
        },
        "name_policy": {
            "encoding": "ASCII",
            "interpretation": "opaque_linker_name",
            "demangling_in_target": False,
            "source_paths_prohibited": True,
            "allowed_characters": "A-Z a-z 0-9 _ . $ @ -",
        },
        "privacy_policy": {
            "on_media_profile": "public_diagnostic_only",
            "private_and_local_symbols_excluded": True,
            "runtime_pointer_redaction_default": True,
            "diagnostic_authorization_required": True,
        },
        "lookup_policy": {
            "algorithm": "bounded_binary_search",
            "maximum_steps": MAX_LOOKUP_STEPS,
            "sorted_nonoverlapping_symbols": True,
            "gaps_return_unknown": True,
            "lookup_grants_authority": False,
        },
        "activation_preconditions": [
            "outer role, version, payload digest, and file digest match",
            "outer, inner, manifest, and kernel signatures verify",
            "all five kernel and debug identities match qualified evidence",
            "stripped-product correspondence and owned DWARF 5 units verify",
            "public-only policy and source-path absence verify",
            "pointer redaction is enabled and diagnostics are authorized",
            "runtime base is aligned and inside the declared virtual window",
            "symbol, string, and lookup capacities satisfy declared bounds",
            "no authority effect is requested",
        ],
        "research_basis": [
            "https://gabi.xinuos.com/elf/05-symtab.html",
            "https://gabi.xinuos.com/elf/04-strtab.html",
            "https://dwarfstd.org/doc/DWARF5.pdf",
            "https://sourceware.org/gdb/current/onlinedocs/gdb.html/Separate-Debug-Files.html",
            "https://doc.rust-lang.org/beta/rustc/symbol-mangling/v0.html",
        ],
        "claims": {
            "format_frozen": True,
            "python_oracle_implemented": True,
            "no_std_parser_implemented": True,
            "bounded_lookup_implemented": True,
            "split_debug_correspondence_qualified": False,
            "symbol_consumption_enabled": False,
            "kernel_export_authority_created": False,
            "runtime_addresses_disclosed_by_default": False,
            "full_debug_file_on_boot_media": False,
            "pooleboot_enforcement": False,
            "poolekernel_enforcement": False,
            "production_ready": False,
        },
        "claim_boundary": [
            "PSYM1 is not owner-ratified and is not yet a stable ABI.",
            "The bundle is a public diagnostic index, not a kernel export or executable loader table.",
            "Parsing and lookup grant no capability, authority, or execution right.",
            "Runtime addresses remain redacted unless an authorized diagnostic path opts in.",
            "The full split-debug ELF remains a private build artifact and is excluded from boot media.",
            "Development artifacts are unsigned and fail the consumption gate.",
            "No key is generated or used and no artifact is signed.",
            "No firmware setting, driver, physical disk, or boot state is modified.",
            "Synthetic qualification cannot authorize production promotion.",
        ],
    }


def _lookup_sample(bundle: Bundle, offset: int) -> dict[str, Any]:
    runtime_base = bundle.preferred_virtual_base
    try:
        observed = format_lookup(lookup(bundle, runtime_base, runtime_base + offset))
    except SymbolError as error:
        observed = f"ERR:{error.code}"
    return {
        "runtime_base": runtime_base,
        "runtime_address": runtime_base + offset,
        "result": observed,
    }


def make_golden_vectors() -> dict[str, Any]:
    definitions = (
        ("PSYM1-CANONICAL", "real PooleKernel public diagnostic profile", canonical_bundle()),
        ("PSYM1-MINIMAL", "minimum valid single-segment profile", minimal_bundle()),
        ("PSYM1-BOUNDARY", "maximum-name and mixed-permission boundary profile", boundary_bundle()),
    )
    vectors = []
    for vector_id, purpose, data in definitions:
        bundle = parse(data)
        offsets = {
            "PSYM1-CANONICAL": (
                0x7FFF,
                0x8000,
                0x8046,
                0x8047,
                0x98FD,
                0x98FE,
                0x99C3,
                0x99C4,
                0xD3A0,
                0xD3A1,
            ),
            "PSYM1-MINIMAL": (0, 63, 64, 4095),
            "PSYM1-BOUNDARY": (0, 31, 32, 4096, 4223, 8192, 8255),
        }[vector_id]
        vectors.append(
            {
                "id": vector_id,
                "purpose": purpose,
                "bundle_byte_count": len(data),
                "bundle_sha256": sha256_bytes(data),
                "summary": summary(bundle),
                "lookup_samples": [_lookup_sample(bundle, offset) for offset in offsets],
                "bundle_hex": data.hex().upper(),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_symbol_golden_vectors",
        "contract_id": CONTRACT_ID,
        "status": "synthetic_non_promoting_golden_bytes",
        "production_ready": False,
        "vectors": vectors,
        "claim_boundary": [
            "Golden vectors are finite synthetic parser evidence.",
            "The canonical vector binds one development kernel build and is unsigned.",
            "Vector success does not enable target consumption or production promotion.",
        ],
    }


def _cstring(data: bytes, offset: int, code: str) -> str:
    if offset < 0 or offset >= len(data):
        raise SymbolError(code)
    end = data.find(b"\0", offset)
    if end < 0:
        raise SymbolError(code)
    try:
        return data[offset:end].decode("ascii")
    except UnicodeDecodeError as error:
        raise SymbolError(code) from error


def _dwarf_versions(data: bytes) -> tuple[int, ...]:
    versions: list[int] = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 6:
            raise SymbolError("psym_dwarf_unit")
        initial_length = struct.unpack_from("<I", data, offset)[0]
        if initial_length == 0xFFFF_FFFF:
            if len(data) - offset < 14:
                raise SymbolError("psym_dwarf_unit")
            unit_length = struct.unpack_from("<Q", data, offset + 4)[0]
            header_bytes = 12
        elif initial_length >= 0xFFFF_FFF0 or initial_length == 0:
            raise SymbolError("psym_dwarf_unit")
        else:
            unit_length = initial_length
            header_bytes = 4
        end = offset + header_bytes + unit_length
        if end > len(data) or unit_length < 2:
            raise SymbolError("psym_dwarf_unit")
        versions.append(struct.unpack_from("<H", data, offset + header_bytes)[0])
        offset = end
    if not versions:
        raise SymbolError("psym_dwarf_unit")
    return tuple(versions)


def inspect_debug_elf(data: bytes) -> DebugElf:
    if len(data) < 64 or len(data) > 16 * 1024 * 1024:
        raise SymbolError("psym_debug_elf_size")
    if data[:4] != b"\x7fELF" or data[4:7] != b"\x02\x01\x01":
        raise SymbolError("psym_debug_elf_ident")
    elf_type, machine, version = struct.unpack_from("<HHI", data, 16)
    if (elf_type, machine, version) != (3, 62, 1):
        raise SymbolError("psym_debug_elf_header")
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    header_bytes = struct.unpack_from("<H", data, 52)[0]
    section_entry_bytes = struct.unpack_from("<H", data, 58)[0]
    section_count = struct.unpack_from("<H", data, 60)[0]
    string_index = struct.unpack_from("<H", data, 62)[0]
    if header_bytes != 64 or section_entry_bytes != 64 or not 1 <= section_count <= 1024:
        raise SymbolError("psym_debug_section_geometry")
    if string_index >= section_count or section_offset > len(data) or section_count * 64 > len(data) - section_offset:
        raise SymbolError("psym_debug_section_geometry")
    raw_sections = [
        struct.unpack_from("<IIQQQQIIQQ", data, section_offset + index * 64)
        for index in range(section_count)
    ]
    string_section = raw_sections[string_index]
    if string_section[1] != 3 or string_section[4] > len(data) or string_section[5] > len(data) - string_section[4]:
        raise SymbolError("psym_debug_section_names")
    section_names = data[string_section[4] : string_section[4] + string_section[5]]
    sections: list[ElfSection] = []
    names_seen: set[str] = set()
    for index, row in enumerate(raw_sections):
        name = "" if index == 0 else _cstring(section_names, row[0], "psym_debug_section_names")
        if name in names_seen and name:
            raise SymbolError("psym_debug_duplicate_section")
        names_seen.add(name)
        section_type, offset, byte_count, link, entry_bytes = row[1], row[4], row[5], row[6], row[9]
        if section_type != 8 and (offset > len(data) or byte_count > len(data) - offset):
            raise SymbolError("psym_debug_section_bounds")
        if link >= section_count and link != 0:
            raise SymbolError("psym_debug_section_link")
        sections.append(ElfSection(name, section_type, offset, byte_count, link, entry_bytes))
    by_name = {item.name: item for item in sections}
    if any(name not in by_name for name in REQUIRED_DWARF5_SECTIONS):
        raise SymbolError("psym_debug_required_sections")
    if any(name in by_name for name in (".gnu_debuglink", ".note.gnu.build-id")):
        raise SymbolError("psym_debug_legacy_identity")

    symtab = by_name[".symtab"]
    if symtab.section_type != 2 or symtab.entry_bytes != 24 or symtab.byte_count % 24:
        raise SymbolError("psym_debug_symtab_geometry")
    string_table = sections[symtab.link]
    if string_table.name != ".strtab" or string_table.section_type != 3:
        raise SymbolError("psym_debug_symtab_link")
    strings = data[string_table.offset : string_table.offset + string_table.byte_count]
    symbols: list[ElfSymbol] = []
    for offset in range(symtab.offset, symtab.offset + symtab.byte_count, 24):
        name_offset, info, other, section_index, value, byte_count = struct.unpack_from("<IBBHQQ", data, offset)
        name = "" if name_offset == 0 else _cstring(strings, name_offset, "psym_debug_symbol_name")
        symbols.append(ElfSymbol(name, info >> 4, info & 0x0F, other & 0x07, section_index, value, byte_count))
    debug_info = by_name[".debug_info"]
    versions = _dwarf_versions(data[debug_info.offset : debug_info.offset + debug_info.byte_count])
    # Rust's prebuilt sysroot contributes DWARF 4 units. The PooleOS crates are
    # rebuilt as the leading DWARF 5 units and are the units this contract owns.
    if any(version not in (4, 5) for version in versions) or versions[:3] != (5, 5, 5):
        raise SymbolError("psym_debug_dwarf_version")
    if any(marker in data for marker in (b"C:\\Users", b"rookp", b"\\\\?\\")):
        raise SymbolError("psym_debug_host_path")
    return DebugElf(len(data), sha256_bytes(data), tuple(sections), tuple(symbols), versions)


def public_symbols_from_debug(debug: DebugElf) -> tuple[Symbol, ...]:
    selected: list[ElfSymbol] = []
    for name in PUBLIC_SYMBOL_NAMES:
        matches = [item for item in debug.symbols if item.name == name]
        if len(matches) != 1:
            raise SymbolError("psym_debug_public_symbol")
        item = matches[0]
        if (
            item.binding != BIND_GLOBAL
            or item.kind != 2
            or item.visibility != VISIBILITY_DEFAULT
            or item.section_index == 0
            or item.byte_count == 0
        ):
            raise SymbolError("psym_debug_public_symbol")
        selected.append(item)
    selected.sort(key=lambda item: item.value)
    result = []
    public_flags = SYMBOL_EXECUTABLE | SYMBOL_DIAGNOSTIC_PUBLIC
    for index, item in enumerate(selected, start=1):
        flags = public_flags
        if item.name == "poole_kernel_entry":
            flags |= SYMBOL_ENTRY
        if item.name == "poole_kernel_emergency_panic":
            flags |= SYMBOL_PANIC_SAFE
        result.append(
            Symbol(
                index,
                2,
                SYMBOL_FUNCTION,
                BIND_GLOBAL,
                VISIBILITY_DEFAULT,
                PRIVACY_PUBLIC,
                flags,
                item.value,
                item.byte_count,
                item.name,
            )
        )
    return tuple(result)


def bundle_from_debug(
    debug_data: bytes,
    canonical_file_data: bytes,
    preferred_loaded_sha256: str,
    source_manifest_data: bytes,
    build_id: str,
) -> bytes:
    debug = inspect_debug_elf(debug_data)
    identity = Identity(
        sha256_bytes(canonical_file_data),
        preferred_loaded_sha256,
        sha256_bytes(build_id.encode("ascii")),
        debug.sha256,
        sha256_bytes(source_manifest_data),
    )
    return encode(
        identity=identity,
        segments=canonical_segments(),
        symbols=public_symbols_from_debug(debug),
        image_bytes=CANONICAL_IMAGE_BYTES,
        entry_offset=CANONICAL_ENTRY_OFFSET,
    )


def _binding_record(path: Path) -> dict[str, Any]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    data = path.read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def binding_matches(value: Any, root: Path, relative: str | Path) -> bool:
    if not isinstance(value, dict):
        return False
    path = root / Path(relative)
    if not path.is_file():
        return False
    data = path.read_bytes()
    return (
        value.get("path") == Path(relative).as_posix()
        and value.get("byte_count") == len(data)
        and value.get("sha256") == sha256_bytes(data)
    )


def implementation_bindings(root: Path = ROOT) -> list[dict[str, Any]]:
    return [_binding_record(root / path) for path in IMPLEMENTATION_INPUTS]


def contract_errors(value: dict[str, Any]) -> list[str]:
    errors = validate_json(value, read_json(ROOT / CONTRACT_SCHEMA_RELATIVE))
    if value.get("contract_id") != CONTRACT_ID:
        errors.append("PSYM1 contract identifier changed")
    layout = value.get("layout", {})
    expected = {
        "header_bytes": HEADER_BYTES,
        "segment_record_bytes": SEGMENT_BYTES,
        "symbol_record_bytes": SYMBOL_BYTES,
        "maximum_bundle_bytes": MAX_BUNDLE_BYTES,
        "maximum_segments": MAX_SEGMENTS,
        "maximum_symbols": MAX_SYMBOLS,
        "maximum_name_bytes": MAX_NAME_BYTES,
        "maximum_string_bytes": MAX_STRING_BYTES,
    }
    for name, expected_value in expected.items():
        if layout.get(name) != expected_value:
            errors.append(f"PSYM1 layout {name} changed")
    if value.get("address_model", {}).get("encoding") != "image_relative_virtual_offset":
        errors.append("PSYM1 address model changed")
    if value.get("privacy_policy", {}).get("on_media_profile") != "public_diagnostic_only":
        errors.append("PSYM1 public-only profile changed")
    claims = value.get("claims", {})
    for name in (
        "symbol_consumption_enabled",
        "kernel_export_authority_created",
        "runtime_addresses_disclosed_by_default",
        "full_debug_file_on_boot_media",
        "pooleboot_enforcement",
        "poolekernel_enforcement",
        "production_ready",
    ):
        if claims.get(name) is not False:
            errors.append(f"PSYM1 claim {name} must remain false")
    return errors


def golden_errors(value: dict[str, Any]) -> list[str]:
    errors = validate_json(value, read_json(ROOT / GOLDEN_SCHEMA_RELATIVE))
    vectors = value.get("vectors", [])
    expected = (canonical_bundle(), minimal_bundle(), boundary_bundle())
    if len(vectors) != len(expected):
        errors.append("PSYM1 golden vector count changed")
        return errors
    for index, (item, expected_bytes) in enumerate(zip(vectors, expected, strict=True)):
        try:
            data = bytes.fromhex(item.get("bundle_hex", ""))
            bundle = parse(data)
        except (ValueError, SymbolError) as error:
            errors.append(f"PSYM1 vector {index} failed parse: {error}")
            continue
        if data != expected_bytes:
            errors.append(f"PSYM1 vector {index} bytes changed")
        if item.get("bundle_sha256") != sha256_bytes(data):
            errors.append(f"PSYM1 vector {index} digest changed")
        if item.get("summary") != summary(bundle):
            errors.append(f"PSYM1 vector {index} summary changed")
        samples = item.get("lookup_samples", [])
        for sample in samples:
            try:
                result = lookup(bundle, sample["runtime_base"], sample["runtime_address"])
                observed = format_lookup(result)
            except SymbolError as error:
                observed = f"ERR:{error.code}"
            if observed != sample.get("result"):
                errors.append(f"PSYM1 vector {index} lookup changed")
    return errors


def readiness_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(value, read_json(root / READINESS_SCHEMA_RELATIVE))
    if value.get("contract_id") != CONTRACT_ID or value.get("status") != "pass":
        errors.append("PSYM1 readiness status changed")
    if value.get("production_ready") is not False or value.get("production_promotion_allowed") is not False:
        errors.append("PSYM1 readiness overclaims promotion")
    bindings = value.get("bindings", {})
    for key, relative in (
        ("contract", CONTRACT_RELATIVE),
        ("golden_vectors", GOLDEN_RELATIVE),
    ):
        if not binding_matches(bindings.get(key), root, relative):
            errors.append(f"PSYM1 stale {key} binding")
    implementation = bindings.get("implementation_inputs", [])
    if not isinstance(implementation, list) or [item.get("path") for item in implementation if isinstance(item, dict)] != list(IMPLEMENTATION_INPUTS):
        errors.append("PSYM1 implementation-input order changed")
    else:
        for item, relative in zip(implementation, IMPLEMENTATION_INPUTS, strict=True):
            if not binding_matches(item, root, relative):
                errors.append(f"PSYM1 stale implementation input {relative}")
    summary_value = value.get("summary", {})
    required_positive = (
        "rust_host_tests_passed",
        "no_std_target_builds_passed",
        "golden_vectors_matched",
        "negative_controls_passed",
        "parser_differential_cases",
        "lookup_differential_cases",
        "debug_reproducible_builds",
    )
    if any(not isinstance(summary_value.get(name), int) or summary_value[name] <= 0 for name in required_positive):
        errors.append("PSYM1 readiness summary lost qualification counts")
    if summary_value.get("differential_mismatches") != 0:
        errors.append("PSYM1 differential mismatches are nonzero")
    claims = value.get("claims", {})
    for name in (
        "symbol_consumption_enabled",
        "pooleboot_enforced",
        "poolekernel_enforced",
        "kernel_export_authority_created",
        "full_debug_file_on_boot_media",
        "runtime_addresses_disclosed_by_default",
        "n5_exit_gate_satisfied",
        "production_ready",
    ):
        if claims.get(name) is not False:
            errors.append(f"PSYM1 readiness claim {name} must remain false")
    return errors
