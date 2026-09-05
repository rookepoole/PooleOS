"""Bounded UEFI optical-media packaging, isolated from production image policy."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import struct
import threading
import time

from demos.native_iso.bootstrap import load_library
from runtime import native_kernel_load, native_pooleboot

BLOCK = 2048
EPOCH = 1788480000
VOLUME = "POOLEOS_DEMO_001"
CONTRACT = "POOLEOS-NATIVE-DEMO-ISO-1"
NATIVE_COMMIT = "73cfdb1a903c73f5e20c4b4cc78ccf9cab150d78"
KERNEL_SHA256 = "9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E"
MAX_ISO_BYTES = 70 * 1024 * 1024
FILES = {"BOOT.CAT;1", "EFI.IMG;1", "README.TXT;1", "MANIFEST.JSON;1", "LICENSE.TXT;1"}
_CLOCK_LOCK = threading.RLock()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


class _AuthoringClock:
    """Freeze only the pinned ISO library's clock; never change host time/TZ."""

    def time(self):
        return EPOCH

    def localtime(self, seconds=None):
        return time.gmtime(EPOCH if seconds is None else seconds)

    def __getattr__(self, name):
        return getattr(time, name)


@contextlib.contextmanager
def _fixed_authoring_clock():
    from pycdlib import dates, headervd, pycdlib

    modules = (dates, headervd, pycdlib)
    with _CLOCK_LOCK:
        original = [module.time for module in modules]
        try:
            for module in modules:
                module.time = _AuthoringClock()
            yield
        finally:
            for module, previous in zip(modules, original, strict=True):
                module.time = previous


def manifest_for(disk: bytes, inspection: dict) -> dict:
    files = {item["path"]: {key: item[key] for key in ("sha256", "byte_count")} for item in inspection["files"]}
    kernel = files["EFI/POOLEOS/KERNEL.ELF"]
    if kernel["sha256"] != KERNEL_SHA256:
        raise ValueError("Demo must retain the qualified native kernel bytes")
    return {
        "contract_id": CONTRACT,
        "demo_version": "0.1.0",
        "visual_variant": "pooleglass_static_demo_v1",
        "native_source_commit": NATIVE_COMMIT,
        "profile": "qemu_ovmf_sandybridge_four_vcpu_pklock1",
        "boot_medium": "uefi_el_torito_optical_only",
        "production_ready": False,
        "signed": False,
        "installer": False,
        "physical_hardware_qualified": False,
        "desktop_present": False,
        "live_reclamation_present": False,
        "source_disk_sha256": sha256(disk),
        "native_files": files,
    }


def build_iso(disk: bytes, readme: bytes, license_text: bytes) -> tuple[bytes, dict]:
    inspection = native_kernel_load.inspect_media_bytes(disk)
    manifest = manifest_for(disk, inspection)
    start = native_pooleboot.ESP_START_LBA * 512
    end = (native_pooleboot.ESP_END_LBA + 1) * 512
    esp = bytearray(disk[start:end])
    # A partition image starts at its own LBA zero, unlike the source GPT disk.
    for offset in (28, 6 * 512 + 28):
        struct.pack_into("<I", esp, offset, 0)
    payloads = {
        "EFI.IMG;1": bytes(esp),
        "README.TXT;1": readme,
        "MANIFEST.JSON;1": native_pooleboot.canonical_json_bytes(manifest),
        "LICENSE.TXT;1": license_text,
    }
    library = load_library()
    with _fixed_authoring_clock():
        iso = library.PyCdlib()
        try:
            iso.new(interchange_level=3, sys_ident="POOLEOS", vol_ident=VOLUME,
                    pub_ident_str="ROOKE POOLE", preparer_ident_str="POOLEOS DEMO TOOLING",
                    app_ident_str=CONTRACT)
            streams = []
            for name, data in sorted(payloads.items()):
                stream = io.BytesIO(data)
                streams.append(stream)
                iso.add_fp(stream, len(data), iso_path="/" + name)
            iso.add_eltorito("/EFI.IMG;1", bootcatfile="/BOOT.CAT;1",
                             platform_id=0xEF, efi=True, boot_load_size=1, media_name="noemul")
            output = io.BytesIO()
            iso.write_fp(output)
            result = output.getvalue()
        finally:
            iso.close()
    inspect_iso(result, disk=disk)
    return result, manifest


def _both32(data: bytes, offset: int) -> int:
    little = struct.unpack_from("<I", data, offset)[0]
    if little != struct.unpack_from(">I", data, offset + 4)[0]:
        raise ValueError("ISO dual-endian field mismatch")
    return little


def inspect_iso(data: bytes, *, disk: bytes | None = None) -> dict:
    """Independent raw checks for this exact five-file, single-boot-entry profile."""
    if not 20 * BLOCK <= len(data) <= MAX_ISO_BYTES or len(data) % BLOCK:
        raise ValueError("ISO size or block alignment is invalid")
    if any(data[:16 * BLOCK]):
        raise ValueError("Demo must have no hybrid MBR or legacy system-area code")
    descriptors = [data[index * BLOCK:(index + 1) * BLOCK] for index in (16, 17, 18)]
    if [block[0] for block in descriptors] != [1, 0, 255] or any(block[1:7] != b"CD001\x01" for block in descriptors):
        raise ValueError("ISO primary/boot/terminator descriptors changed")
    pvd, boot, _ = descriptors
    if pvd[40:72].rstrip(b" ") != VOLUME.encode("ascii") or _both32(pvd, 80) * BLOCK != len(data):
        raise ValueError("ISO volume identity or declared size changed")
    if pvd[128:132] != struct.pack("<H", BLOCK) + struct.pack(">H", BLOCK):
        raise ValueError("ISO logical block size changed")
    if boot[7:39].rstrip(b"\x00") != b"EL TORITO SPECIFICATION":
        raise ValueError("El Torito boot-system identifier missing")
    root_lba, root_size = _both32(pvd, 158), _both32(pvd, 166)
    if root_size != BLOCK or not 19 <= root_lba < len(data) // BLOCK:
        raise ValueError("Unexpected root directory bounds")
    directory = data[root_lba * BLOCK:(root_lba + 1) * BLOCK]
    files = {}
    offset = 0
    while offset < len(directory) and directory[offset]:
        length = directory[offset]
        if length < 34 or offset + length > len(directory):
            raise ValueError("Malformed ISO directory record")
        record = directory[offset:offset + length]
        name_len = record[32]
        if 33 + name_len > length:
            raise ValueError("Malformed ISO filename length")
        name_raw = record[33:33 + name_len]
        if name_raw not in (b"\x00", b"\x01"):
            name = name_raw.decode("ascii")
            lba, size = _both32(record, 2), _both32(record, 10)
            if name not in FILES or name in files or record[25] != 0 or lba <= root_lba or not 0 < size <= len(data) - lba * BLOCK:
                raise ValueError("Unexpected, duplicate, overlapping or out-of-bounds ISO file")
            files[name] = {"lba": lba, "byte_count": size}
        offset += length
    if set(files) != FILES or any(directory[offset:]):
        raise ValueError("ISO root file set or padding changed")
    spans = sorted((item["lba"] * BLOCK, item["lba"] * BLOCK + item["byte_count"]) for item in files.values())
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError("ISO file extents overlap")

    def payload(name):
        item = files[name]
        return data[item["lba"] * BLOCK:item["lba"] * BLOCK + item["byte_count"]]

    catalog_lba = struct.unpack_from("<I", boot, 71)[0]
    if catalog_lba != files["BOOT.CAT;1"]["lba"]:
        raise ValueError("Catalog extent does not match its directory entry")
    catalog = payload("BOOT.CAT;1")
    if len(catalog) != BLOCK or catalog[:4] != b"\x01\xef\x00\x00" or catalog[30:32] != b"\x55\xaa":
        raise ValueError("Not a UEFI validation entry")
    if sum(struct.unpack("<16H", catalog[:32])) & 0xFFFF:
        raise ValueError("El Torito catalog checksum mismatch")
    if catalog[32:40] != b"\x88\x00\x00\x00\x00\x00\x01\x00" or any(catalog[44:]):
        raise ValueError("Not the single no-emulation EFI entry")
    if struct.unpack_from("<I", catalog, 40)[0] != files["EFI.IMG;1"]["lba"]:
        raise ValueError("EFI boot extent mismatch")
    esp = payload("EFI.IMG;1")
    if len(esp) != native_pooleboot.ESP_SECTORS * 512 or esp[82:90] != b"FAT32   " or esp[510:512] != b"\x55\xaa":
        raise ValueError("EFI volume geometry or FAT signature changed")
    if any(esp[index:index + 4] != b"\x00" * 4 for index in (28, 6 * 512 + 28)):
        raise ValueError("Optical partition must have zero hidden-sector offset")
    manifest = json.loads(payload("MANIFEST.JSON;1"))
    if manifest.get("contract_id") != CONTRACT or manifest.get("native_source_commit") != NATIVE_COMMIT:
        raise ValueError("Demo manifest identity changed")
    for key in ("production_ready", "signed", "installer", "physical_hardware_qualified", "desktop_present", "live_reclamation_present"):
        if manifest.get(key) is not False:
            raise ValueError("Demo manifest attempted unsupported promotion")
    if disk is not None:
        inspection = native_kernel_load.inspect_media_bytes(disk)
        if manifest != manifest_for(disk, inspection):
            raise ValueError("Demo manifest does not bind the native source disk")
        source_esp = bytearray(esp)
        for index in (28, 6 * 512 + 28):
            struct.pack_into("<I", source_esp, index, native_pooleboot.ESP_START_LBA)
        start = native_pooleboot.ESP_START_LBA * 512
        if bytes(source_esp) != disk[start:start + len(source_esp)]:
            raise ValueError("Embedded EFI volume differs from the qualified native payload")
    return {"contract_id": CONTRACT, "sha256": sha256(data), "byte_count": len(data),
            "volume_id": VOLUME, "catalog_lba": catalog_lba, "files": files,
            "manifest": manifest, "uefi_platform_id": "EF", "production_ready": False}
