"""Synthetic, non-executable FAT fixtures; ISO authoring uses pinned pycdlib."""
import io
import struct

from demos.native_iso.bootstrap import load_library
from demos.native_iso.package import _fixed_authoring_clock

TOTAL = 34 * 1024 * 1024
FAT_SECTORS = 544
DATA_START = (32 + 2 * FAT_SECTORS) * 512
COUNT = (TOTAL - DATA_START) // 512
DEFAULT_FILES = {
    "EFI/BOOT/BOOTX64.EFI": b"fixture-not-executable-" + b"A" * 1002,
    "pooleos/PooleKernel.elf": b"fixture-kernel",
    "pooleos/system/initial-system.bundle": b"fixture-initial-system",
    "pooleos/recovery/recovery.bundle": b"fixture-recovery",
    "pooleos/manifest.json": b'{"fixture":true}',
}


def short_entry(name, attrs, cluster, size=0):
    raw = bytearray(32)
    raw[:11] = name
    raw[11] = attrs
    struct.pack_into("<H", raw, 20, cluster >> 16)
    struct.pack_into("<H", raw, 26, cluster & 65535)
    struct.pack_into("<I", raw, 28, size)
    return raw


def names(name, ordinal):
    base, dot, ext = name.rpartition(".")
    if not dot:
        base, ext = name, ""
    alias = base.upper() if len(base) <= 8 else base[:6].upper() + "~" + str(ordinal)
    alias = alias[:8].ljust(8) + ext[:3].upper().ljust(3)
    short = alias.encode("ascii")
    display = alias[:8].rstrip() + ("." + alias[8:].rstrip() if ext else "")
    if display.casefold() == name.casefold():
        return [], short
    checksum = 0
    for value in short:
        checksum = (((checksum & 1) << 7) + (checksum >> 1) + value) & 255
    units = list(struct.unpack("<" + "H" * len(name), name.encode("utf-16-le"))) + [0]
    units += [65535] * ((-len(units)) % 13)
    result = []
    for i in reversed(range(len(units) // 13)):
        raw = bytearray(32)
        raw[0] = i + 1 + (64 if i == len(units) // 13 - 1 else 0)
        raw[11], raw[13] = 15, checksum
        encoded = struct.pack("<13H", *units[i * 13:(i + 1) * 13])
        raw[1:11], raw[14:26], raw[28:32] = encoded[:10], encoded[10:22], encoded[22:]
        result.append(raw)
    return result, short


def fat_image(files=None):
    files = dict(DEFAULT_FILES if files is None else files)
    directories = {""}
    for path in files:
        parts = path.split("/")
        directories.update("/".join(parts[:i]) for i in range(1, len(parts)))
    ordered = sorted(directories, key=lambda p: (p.count("/") + bool(p), p))
    clusters = {path: i + 2 for i, path in enumerate(ordered)}
    next_cluster = len(ordered) + 2
    fat = bytearray(FAT_SECTORS * 512)
    struct.pack_into("<II", fat, 0, 0x0FFFFFF8, 0x0FFFFFFF)
    image = bytearray(TOTAL)
    locations = {}
    for path, payload in files.items():
        count = (len(payload) + 511) // 512
        clusters[path] = next_cluster if count else 0
        for i in range(count):
            c = next_cluster + i
            struct.pack_into("<I", fat, c * 4, c + 1 if i < count - 1 else 0x0FFFFFFF)
            start = DATA_START + (c - 2) * 512
            chunk = payload[i * 512:(i + 1) * 512]
            image[start:start + len(chunk)] = chunk
        next_cluster += count
    for path in ordered:
        cluster = clusters[path]
        struct.pack_into("<I", fat, cluster * 4, 0x0FFFFFFF)
        entries = []
        if path:
            parent = path.rpartition("/")[0]
            entries += [short_entry(b".          ", 16, cluster), short_entry(b"..         ", 16, clusters[parent] if parent else 0)]
        children = [p for p in [*ordered, *files] if p and p.rpartition("/")[0] == path]
        for index, child in enumerate(children, 1):
            lfns, short = names(child.rsplit("/", 1)[-1], index)
            entries.extend(lfns)
            locations[child] = DATA_START + (cluster - 2) * 512 + len(entries) * 32
            entries.append(short_entry(short, 16 if child in directories else 32, clusters[child], len(files.get(child, b""))))
        raw = b"".join(entries)
        assert len(raw) < 512
        offset = DATA_START + (cluster - 2) * 512
        image[offset:offset + len(raw)] = raw
    bpb = bytearray(512)
    bpb[:3], bpb[3:11] = b"\xeb\x58\x90", b"TESTONLY"
    struct.pack_into("<H", bpb, 11, 512)
    bpb[13], bpb[16], bpb[21] = 1, 2, 0xF8
    struct.pack_into("<H", bpb, 14, 32)
    struct.pack_into("<III", bpb, 32, TOTAL // 512, FAT_SECTORS, 0)
    struct.pack_into("<IHH", bpb, 44, 2, 1, 6)
    bpb[82:90], bpb[510:] = b"FAT32   ", b"\x55\xaa"
    info = bytearray(512)
    info[:4], info[484:488], info[508:] = b"RRaA", b"rrAa", b"\0\0\x55\xaa"
    struct.pack_into("<II", info, 488, COUNT - (next_cluster - 2), next_cluster)
    for sector, raw in ((0, bpb), (6, bpb), (1, info), (7, info)):
        image[sector * 512:(sector + 1) * 512] = raw
    for offset in (32 * 512, (32 + FAT_SECTORS) * 512):
        image[offset:offset + len(fat)] = fat
    return bytes(image), {"entries": locations, "clusters": clusters, "next_free": next_cluster}


def iso_image(esp, extra=None):
    lib = load_library()
    with _fixed_authoring_clock():
        iso = lib.PyCdlib()
        try:
            iso.new(interchange_level=3, vol_ident="POOLEOS_TEST_ONLY")
            streams = []
            for path, payload in {"/EFI.IMG;1": esp, **(extra or {})}.items():
                stream = io.BytesIO(payload)
                streams.append(stream)
                iso.add_fp(stream, len(payload), iso_path=path)
            iso.add_eltorito("/EFI.IMG;1", bootcatfile="/BOOT.CAT;1", platform_id=0xEF, efi=True, boot_load_size=1, media_name="noemul")
            output = io.BytesIO()
            iso.write_fp(output)
            return output.getvalue()
        finally:
            iso.close()
