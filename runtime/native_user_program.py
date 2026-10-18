"""Build-time extraction of a bounded original user program, not a trust loader."""
from __future__ import annotations

import hashlib
import struct

CONTRACT = "PUSERBIN1"
MAX_FILE = 65536
MAX_CODE_PAGES = 4
WINDOW_SERVICE_CONTRACT = "PWCODE1"
WINDOW_SERVICE_CODE_PAGES = 7


def profile_for(name: str) -> str:
    return WINDOW_SERVICE_CONTRACT if name in ("PooleWindowCapacity", "PooleWindowLifecycle", "PooleWindowInput") else CONTRACT


def inspect(blob: bytes, *, profile: str = CONTRACT) -> dict:
    def require(ok: bool, why: str) -> None:
        if not ok:
            raise ValueError(why)

    require(profile in (CONTRACT, WINDOW_SERVICE_CONTRACT), "unknown code profile")
    maximum = WINDOW_SERVICE_CODE_PAGES if profile == WINDOW_SERVICE_CONTRACT else MAX_CODE_PAGES
    require(type(blob) is bytes and 64 <= len(blob) <= MAX_FILE, "ELF size")
    require(blob[:16] == b"\x7fELF\x02\x01\x01" + bytes(9), "ELF identification")
    fields = struct.unpack_from("<HHIQQQIHHHHHH", blob, 16)
    kind, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, names = fields
    require((kind, machine, version, entry, flags, ehsize, phsize, phnum, shsize) ==
            (2, 62, 1, 0, 0, 64, 56, 1, 64), "ELF header contract")
    require(phoff == 64 and 2 <= shnum <= 16 and 0 < names < shnum, "ELF tables")
    require(120 <= shoff <= len(blob) - shnum * 64, "section bounds")
    segment = struct.unpack_from("<IIQQQQQQ", blob, phoff)
    ptype, permissions, offset, address, physical, size, memory, alignment = segment
    require((ptype, permissions, address, physical, alignment) == (1, 5, 0, 0, 4096),
            "single RX program segment")
    require(0 < size <= maximum * 4096 and memory == size and offset >= 120 and offset % 4096 == 0,
            "bounded code geometry")
    require(offset + size <= shoff, "segment overlaps section table")
    sections = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + i * 64) for i in range(shnum)]
    require(sections[0] == (0,) * 10, "null section")
    strings = sections[names]
    require(strings[1] == 3 and strings[2] == 0 and strings[5] <= 4096, "section names")
    require(offset + size <= strings[4] <= shoff - strings[5], "name table bounds")
    names_blob = blob[strings[4]:strings[4] + strings[5]]
    require(names_blob[:1] == b"\0" and names_blob[-1:] == b"\0", "name table encoding")
    allocated = []
    seen_names = set()
    for section in sections[1:]:
        name, stype, sflags, addr, start, length, link, info, align, entsize = section
        require(name < len(names_blob), "section name index")
        end = names_blob.find(b"\0", name)
        require(end >= name, "section name terminator")
        label = names_blob[name:end]
        require(label not in seen_names, "duplicate section")
        seen_names.add(label)
        require(stype in (1, 3) and link == info == entsize == 0, "unsupported section")
        require(align in (0, 1, 2, 4, 8, 16, 32, 64, 4096), "section alignment")
        require(start <= len(blob) and length <= len(blob) - start, "section range")
        if sflags & 2:
            # LLD propagates SHF_MERGE when constant input sections join .text.
            # It grants no runtime permission; all other flags remain forbidden.
            require(label == b".text" and stype == 1 and sflags in (6, 0x16) and addr == 0
                    and start == offset and length == size, "allocated section contract")
            allocated.append(section)
        else:
            require(section == strings and label == b".shstrtab", "extra non-code section")
    require(len(allocated) == 1, "one allocated section")
    code = blob[offset:offset + size]
    require(code[:2] == b"\x31\xed", "entry frame initialization")
    return {"contract_id": profile, "elf_bytes": len(blob),
            "elf_sha256": hashlib.sha256(blob).hexdigest().upper(),
            "code_offset": offset, "code_bytes": size,
            "code_sha256": hashlib.sha256(code).hexdigest().upper(),
            "entry_offset": entry, "load_pages": (size + 4095) // 4096, "code_section_flags": allocated[0][2],
            "writable_segments": 0, "relocations": 0, "imports": 0,
            "position_independent_source_and_flags_required": True,
            "native_execution_verified": False, "production_ready": False}


def extract(blob: bytes, *, profile: str = CONTRACT) -> tuple[bytes, dict]:
    record = inspect(blob, profile=profile)
    at = record["code_offset"]
    return blob[at:at + record["code_bytes"]], record
