"""Bounded read-only ISO9660/El Torito/FAT32 inventory for architecture review."""

from __future__ import annotations

import hashlib
import re
import struct
import unicodedata

BLOCK = 2048
MAX_IMAGE = 128 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_DEPTH = 16


class MediaError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MediaError(message)


def take(data: bytes, offset: int, size: int) -> bytes:
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset, "out-of-bounds media extent")
    return data[offset:offset + size]


def number(data: bytes, offset: int, size: int, order: str = "little") -> int:
    return int.from_bytes(take(data, offset, size), order)


def paired(data: bytes, offset: int, size: int) -> int:
    value = number(data, offset, size)
    require(value == number(data, offset + size, size, "big"), "dual-endian field mismatch")
    return value


def component(name: str) -> str:
    require(0 < len(name) <= 255 and name not in (".", ".."), "invalid path component")
    require(name == unicodedata.normalize("NFC", name) and not name.endswith((" ", ".")), "noncanonical path component")
    require(all(ord(c) >= 32 and c not in '\\/:*?"<>|\x7f' for c in name), "unsafe path component")
    return name


def add_entry(entries: dict, path: str, content: bytes | None, aliases: tuple[str, ...] = ()) -> None:
    require(len(entries) < MAX_ENTRIES and len(path.split("/")) <= MAX_DEPTH, "inventory limit exceeded")
    require(path.casefold() not in {p.casefold() for p in entries}, "duplicate or case-colliding path")
    entries[path] = {"data": content, "aliases": aliases}


def iso_files(data: bytes) -> tuple[dict, str]:
    require(20 * BLOCK <= len(data) <= MAX_IMAGE and len(data) % BLOCK == 0, "invalid ISO size")
    require(not any(data[:16 * BLOCK]), "hybrid/system-area content is unsupported")
    pvd = boot = None
    end = 0
    for lba in range(16, min(48, len(data) // BLOCK)):
        vd = take(data, lba * BLOCK, BLOCK)
        require(vd[1:7] == b"CD001\x01", "invalid ISO descriptor")
        if vd[0] == 1:
            require(pvd is None, "duplicate primary descriptor")
            pvd = vd
        elif vd[0] == 0:
            require(boot is None and vd[7:39].rstrip(b"\0") == b"EL TORITO SPECIFICATION", "unsupported boot descriptor")
            boot = vd
        elif vd[0] == 255:
            require(not any(vd[7:]), "nonzero descriptor terminator")
            end = (lba + 1) * BLOCK
            break
        else:
            raise MediaError("alternative ISO namespace/descriptor is unsupported")
    require(pvd is not None and boot is not None and end != 0, "missing ISO descriptors")
    require(paired(pvd, 80, 4) * BLOCK == len(data), "ISO volume size mismatch")
    require(paired(pvd, 128, 2) == BLOCK and paired(pvd, 120, 2) == paired(pvd, 124, 2) == 1, "unsupported ISO volume geometry")
    spans = [(0, end)]

    def extent(lba: int, size: int) -> bytes:
        require(0 < size <= MAX_FILE, "empty or oversized extent")
        start, stop = lba * BLOCK, (lba + (size + BLOCK - 1) // BLOCK) * BLOCK
        raw = take(data, start, stop - start)
        require(not any(start < right and left < stop for left, right in spans), "overlapping ISO extents")
        require(not any(raw[size:]), "nonzero extent padding")
        spans.append((start, stop))
        return raw[:size]

    def record(raw: bytes) -> tuple[bytes, int, int, bool]:
        require(len(raw) >= 34 and raw[0] == len(raw) and len(raw) % 2 == 0, "invalid directory record length")
        n = raw[32]
        require(n > 0 and 33 + n <= len(raw) and not any(raw[33 + n:]), "unsupported directory system-use data")
        require(raw[1] == 0 and raw[25] & ~3 == 0 and raw[26:28] == b"\0\0", "unsupported file record flags")
        require(paired(raw, 28, 2) == 1, "wrong directory volume sequence")
        return raw[33:33 + n], paired(raw, 2, 4), paired(raw, 10, 4), bool(raw[25] & 2)

    root_name, root_lba, root_size, is_dir = record(take(pvd, 156, pvd[156]))
    require(root_name == b"\0" and is_dir, "invalid root record")
    entries, dirs, sizes, file_lbas = {}, {"": root_lba}, {"": root_size}, {}
    queue = [("", root_lba, root_size, "")]
    for path, lba, size, parent in queue:
        require(len(queue) <= MAX_ENTRIES and len(path.split("/")) <= MAX_DEPTH, "directory limit exceeded")
        require(size <= 2 * 1024 * 1024 and size % BLOCK == 0, "invalid directory allocation")
        raw = extent(lba, size)
        offset, ordinal = 0, 0
        while offset < len(raw):
            length = raw[offset]
            if not length:
                stop = min((offset // BLOCK + 1) * BLOCK, len(raw))
                require(not any(raw[offset:stop]), "nonzero directory padding")
                offset = stop
                continue
            require(offset % BLOCK + length <= BLOCK, "directory record crosses a sector")
            name, child_lba, child_size, directory = record(take(raw, offset, length))
            offset += length
            if ordinal < 2:
                expected = path if ordinal == 0 else parent
                require(name == bytes([ordinal]) and directory and child_lba == dirs[expected] and child_size == sizes[expected], "invalid dot directory record")
            else:
                require(name not in (b"\0", b"\1"), "duplicate dot record")
                try:
                    decoded = name.decode("ascii")
                except UnicodeDecodeError as error:
                    raise MediaError("non-ASCII ISO identifier is unsupported") from error
                if not directory:
                    require(decoded.endswith(";1"), "unsupported file version")
                    decoded = decoded[:-2].removesuffix(".")
                require(re.fullmatch(r"[A-Z0-9_.-]+", decoded) is not None, "unsupported ISO identifier")
                child = (path + "/" if path else "") + component(decoded)
                if directory:
                    add_entry(entries, child, None)
                    dirs[child], sizes[child] = child_lba, child_size
                    queue.append((child, child_lba, child_size, path))
                else:
                    require(child_size <= MAX_FILE, "file exceeds size limit")
                    content = extent(child_lba, child_size) if child_size else b""
                    add_entry(entries, child, content)
                    file_lbas[child] = child_lba
            ordinal += 1
        require(ordinal >= 2, "missing dot records")

    table_size = paired(pvd, 132, 4)
    require(0 < table_size <= MAX_ENTRIES * 264, "path-table limit exceeded")
    for offset, order, optional in ((140, "little", False), (144, "little", True), (148, "big", False), (152, "big", True)):
        lba = number(pvd, offset, 4, order)
        if optional and not lba:
            continue
        table, pos, names, found = extent(lba, table_size), 0, [], {}
        while pos < len(table):
            header = take(table, pos, 8)
            n, xattr = header[:2]
            require(n > 0 and xattr == 0 and len(names) < MAX_ENTRIES, "invalid path-table entry")
            name = take(table, pos + 8, n)
            parent_id = number(header, 6, 2, order)
            require(1 <= parent_id <= max(1, len(names)), "invalid path-table parent")
            if not names:
                require(name == b"\0" and parent_id == 1, "invalid path-table root")
                path = ""
            else:
                try:
                    name_text = component(name.decode("ascii"))
                except UnicodeDecodeError as error:
                    raise MediaError("invalid path-table name") from error
                path = (names[parent_id - 1] + "/" if names[parent_id - 1] else "") + name_text
            require(path not in found, "duplicate path-table entry")
            found[path] = number(header, 2, 4, order)
            names.append(path)
            if n % 2:
                require(take(table, pos + 8 + n, 1) == b"\0", "invalid path-table padding")
            pos += 8 + n + n % 2
        require(found == dirs, "path table disagrees with directory hierarchy")
    for (_, stop), (start, _) in zip(sorted(spans), sorted(spans)[1:] + [(len(data), len(data))]):
        require(not any(data[stop:start]), "unreferenced nonzero ISO content")
    catalog_lba = number(boot, 71, 4)
    catalogs = [p for p, lba in file_lbas.items() if lba == catalog_lba]
    require(len(catalogs) == 1, "boot catalog must have one visible file binding")
    cat = entries[catalogs[0]]["data"]
    require(len(cat) == BLOCK and cat[:4] == b"\x01\xef\0\0" and cat[30:32] == b"\x55\xaa", "invalid EFI catalog validation entry")
    require(sum(struct.unpack("<16H", cat[:32])) & 0xFFFF == 0, "boot catalog checksum mismatch")
    require(cat[32:38] == b"\x88\0\0\0\0\0" and not any(cat[44:]), "unsupported or multiple boot entries")
    boot_lba = number(cat, 40, 4)
    boot_paths = [p for p, lba in file_lbas.items() if lba == boot_lba]
    require(len(boot_paths) == 1 and boot_paths[0] != catalogs[0], "EFI image binding mismatch")
    esp_path = boot_paths[0]
    sector_count = number(cat, 38, 2)
    require(sector_count in (0, 1) or sector_count * 512 == len(entries[esp_path]["data"]), "EFI boot size disagreement")
    return entries, esp_path


def fat_files(data: bytes) -> tuple[dict, list[str]]:
    require(512 <= len(data) <= MAX_FILE and len(data) % 512 == 0, "invalid EFI filesystem size")
    bpb = data[:512]
    require(bpb[510:] == b"\x55\xaa" and number(bpb, 11, 2) == 512, "invalid FAT sector")
    spc, reserved, copies = bpb[13], number(bpb, 14, 2), bpb[16]
    total, fat_sectors, root = number(bpb, 32, 4), number(bpb, 36, 4), number(bpb, 44, 4)
    require(spc in (1, 2, 4, 8, 16, 32, 64) and reserved == 32 and copies == 2, "unsupported FAT32 geometry")
    require(number(bpb, 17, 2) == number(bpb, 19, 2) == number(bpb, 22, 2) == number(bpb, 28, 4) == number(bpb, 40, 2) == number(bpb, 42, 2) == 0, "unsupported FAT32 BPB fields")
    require(total * 512 == len(data) and fat_sectors > 0 and bpb[21] == 0xF8, "FAT volume size/media mismatch")
    require(number(bpb, 48, 2) == 1 and number(bpb, 50, 2) == 6 and not any(bpb[52:64]), "unsupported FAT reserved layout")
    require(take(data, 6 * 512, 512) == bpb, "FAT boot-sector copies disagree")
    fsinfo = take(data, 512, 512)
    require(fsinfo == take(data, 7 * 512, 512) and fsinfo[:4] == b"RRaA" and fsinfo[484:488] == b"rrAa" and fsinfo[508:] == b"\0\0\x55\xaa", "FAT FSInfo mismatch")
    require(not any(fsinfo[4:484]) and not any(fsinfo[496:508]), "nonzero FSInfo reserved bytes")
    for sector in set(range(reserved)) - {0, 1, 6, 7}:
        require(not any(take(data, sector * 512, 512)), "nonzero FAT reserved sectors")
    start = (reserved + copies * fat_sectors) * 512
    cluster_size = spc * 512
    count = (len(data) - start) // cluster_size
    require(65525 <= count < 0x0FFFFFF5 and count + 2 <= fat_sectors * 128, "volume is not a bounded FAT32 filesystem")
    fat = take(data, reserved * 512, fat_sectors * 512)
    require(fat == take(data, (reserved + fat_sectors) * 512, len(fat)), "FAT copies disagree")
    require(number(fat, 0, 4) == 0x0FFFFFF8 and number(fat, 4, 4) == 0x0FFFFFFF, "invalid FAT reserved entries")
    require(not any(fat[(count + 2) * 4:]) and not any(data[start + count * cluster_size:]), "nonzero FAT trailing space")
    owned, entries, issues = set(), {}, []

    def chain(first: int) -> bytes:
        blocks = []
        current = first
        while True:
            require(2 <= current < count + 2 and current not in owned, "FAT chain cycle, cross-link or out-of-range cluster")
            owned.add(current)
            blocks.append(take(data, start + (current - 2) * cluster_size, cluster_size))
            next_cluster = number(fat, current * 4, 4)
            require(next_cluster < 0x10000000, "nonzero reserved FAT entry bits")
            if next_cluster >= 0x0FFFFFF8:
                break
            current = next_cluster
        return b"".join(blocks)

    queue = [("", root, 0)]
    for path, first, parent in queue:
        require(len(queue) <= MAX_ENTRIES and len(path.split("/")) <= MAX_DEPTH, "FAT directory limit exceeded")
        raw = chain(first)
        require(len(raw) <= 2 * 1024 * 1024, "oversized FAT directory")
        require(not path or (raw[:11] == b".          " and raw[32:43] == b"..         "), "missing FAT dot entries")
        lfns, names, label_count = [], set(), 0
        for offset in range(0, len(raw), 32):
            item = raw[offset:offset + 32]
            if item[0] == 0:
                require(not lfns and not any(raw[offset:]), "dangling LFN or hidden trailing directory entry")
                break
            require(item[0] != 0xE5, "deleted FAT entries are unsupported")
            if item[11] == 0x0F:
                require(len(lfns) < 20 and item[12] == 0 and item[26:28] == b"\0\0", "invalid long-name entry")
                lfns.append(item)
                continue
            attrs = item[11]
            require(attrs & ~0x3F == 0 and item[12] & ~0x18 == 0, "invalid FAT entry attributes")
            cluster = number(item, 20, 2) * 65536 + number(item, 26, 2)
            size = number(item, 28, 4)
            if path and offset in (0, 32):
                expected = b".          " if offset == 0 else b"..         "
                require(not lfns and item[:11] == expected and attrs == 0x10 and size == 0, "missing FAT dot entries")
                expected_cluster = first if offset == 0 else (0 if parent == root else parent)
                if cluster != expected_cluster:
                    if offset == 32 and parent == root and cluster == root:
                        issues.append(path + ": root-parent dotdot must be cluster zero")
                    else:
                        raise MediaError("incorrect FAT dot-entry cluster")
                continue
            if attrs & 8:
                require(not path and not lfns and attrs == 8 and cluster == size == 0 and label_count == 0, "invalid FAT volume label")
                label_count += 1
                continue
            try:
                base, ext = item[:8].decode("ascii").rstrip(" "), item[8:11].decode("ascii").rstrip(" ")
            except UnicodeDecodeError as error:
                raise MediaError("non-ASCII short names are unsupported") from error
            require(re.fullmatch(r"[A-Z0-9_$~!#%&'()@^`{}-]+", base) is not None and (not ext or re.fullmatch(r"[A-Z0-9_$~!#%&'()@^`{}-]+", ext)), "invalid FAT short name")
            short = component(base + ("." + ext if ext else ""))
            name = short
            if lfns:
                checksum = 0
                for value in item[:11]:
                    checksum = (((checksum & 1) << 7) + (checksum >> 1) + value) & 255
                for index, lfn in enumerate(lfns):
                    require(lfn[0] == len(lfns) - index + (0x40 if index == 0 else 0) and lfn[13] == checksum, "LFN ordinal/checksum mismatch")
                encoded = b"".join(v[1:11] + v[14:26] + v[28:32] for v in reversed(lfns))
                units = list(struct.unpack("<" + "H" * (len(encoded) // 2), encoded))
                if 0 in units:
                    stop = units.index(0)
                    require(all(x == 0xFFFF for x in units[stop + 1:]), "invalid LFN padding")
                    encoded = encoded[:stop * 2]
                try:
                    name = component(encoded.decode("utf-16-le"))
                except UnicodeDecodeError as error:
                    raise MediaError("invalid LFN encoding") from error
                require("\uffff" not in name, "invalid LFN character")
            require(name.casefold() not in names and short.casefold() not in names, "FAT name/alias collision")
            names.update((name.casefold(), short.casefold()))
            child = (path + "/" if path else "") + name
            alias = (path + "/" if path else "") + short
            if attrs & 0x10:
                require(size == 0 and name.casefold() == short.casefold(), "long directory aliases are unsupported")
                add_entry(entries, child, None)
                queue.append((child, cluster, first))
            else:
                require(size <= MAX_FILE and (size > 0 or cluster == 0), "invalid file length/cluster")
                content = chain(cluster) if size else b""
                require(len(content) == ((size + cluster_size - 1) // cluster_size) * cluster_size and not any(content[size:]), "FAT file size or slack mismatch")
                add_entry(entries, child, content[:size], (alias,) if alias.casefold() != child.casefold() else ())
            lfns = []
        require(not lfns, "unterminated long filename")
    free = 0
    for cluster in range(2, count + 2):
        value = number(fat, cluster * 4, 4)
        if cluster not in owned:
            require(value == 0, "unreferenced FAT allocation")
            require(not any(take(data, start + (cluster - 2) * cluster_size, cluster_size)), "nonzero free FAT cluster")
            free += 1
    require(number(fsinfo, 488, 4) in (0xFFFFFFFF, free), "FSInfo free count mismatch")
    return entries, issues


def inspect(data: bytes) -> dict:
    outer, esp_path = iso_files(data)
    inner, issues = fat_files(outer[esp_path]["data"])
    return {"iso_sha256": hashlib.sha256(data).hexdigest().upper(), "byte_count": len(data),
            "esp_path": esp_path, "iso": outer, "esp": inner, "structural_issues": issues}
