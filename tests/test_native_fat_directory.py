"""FAT directory-link conformance for generated native boot media, not boot evidence."""
from pathlib import Path
import json
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_elf_loader, native_iso_media, native_kernel_load, native_pooleboot
from tests.test_native_pooleboot import synthetic_pooleboot


class NativeFatDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.efi = synthetic_pooleboot()
        cls.image = native_pooleboot.build_media_bytes(cls.efi)
        sectors, _ = native_pooleboot._fat_sector_count()
        cls.start = (native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
                     + native_pooleboot.FAT_COUNT * sectors) * 512

    def independent_files(self, image):
        start = native_pooleboot.ESP_START_LBA * 512
        esp = bytearray(image[start:start + native_pooleboot.ESP_SECTORS * 512])
        for offset in (28, 6 * 512 + 28):
            struct.pack_into("<I", esp, offset, 0)
        files, issues = native_iso_media.fat_files(bytes(esp))
        self.assertEqual(issues, [])
        return {name: entry["data"] for name, entry in files.items() if entry["data"] is not None}

    def test_writer_uses_zero_root_parent_and_preserves_other_links(self):
        for relative, cluster in ((512, 3), (544, 0), (1024, 4), (1056, 3)):
            entry = self.image[self.start + relative:self.start + relative + 32]
            with self.subTest(relative=relative):
                self.assertEqual(struct.unpack_from("<H", entry, 20)[0], 0)
                self.assertEqual(struct.unpack_from("<H", entry, 26)[0], cluster)
                self.assertEqual(entry[11], 0x10)
                self.assertEqual(struct.unpack_from("<I", entry, 28)[0], 0)

    def test_media_is_reproducible_and_independent_inventory_matches_payload(self):
        self.assertEqual(self.image, native_pooleboot.build_media_bytes(self.efi))
        self.assertEqual(self.independent_files(self.image), {"EFI/BOOT/BOOTX64.EFI": self.efi})
        inspection = native_pooleboot.inspect_media_bytes(self.image)
        self.assertEqual(inspection["esp"]["label"], "POOLEOS ESP")
        json.dumps(inspection)
        self.assertEqual(inspection["files"][0]["sha256"], native_pooleboot.sha256_bytes(self.efi))

    def test_inspector_rejects_dot_field_corruption_and_old_root_parent(self):
        cases = [(relative + offset, payload) for relative in (512, 544, 1024, 1056)
                 for offset, payload in ((20, b"\x01\x00"), (26, b"\xff\xff"),
                                         (11, b"\x20"), (28, b"\x01\x00\x00\x00"))]
        cases.append((544 + 26, b"\x02\x00"))
        for relative, payload in cases:
            with self.subTest(relative=relative, payload=payload):
                image = bytearray(self.image)
                at = self.start + relative
                image[at:at + len(payload)] = payload
                with self.assertRaises(native_pooleboot.PooleBootError):
                    native_pooleboot.inspect_media_bytes(bytes(image))

    def test_dot_entries_must_occupy_first_two_slots(self):
        for relative in (512, 1024):
            for mutation in ("swapped", "deleted_prefix"):
                with self.subTest(relative=relative, mutation=mutation):
                    image = bytearray(self.image)
                    at = self.start + relative
                    original = bytes(image[at:at + 96])
                    if mutation == "swapped":
                        image[at:at + 64] = original[32:64] + original[:32]
                    else:
                        image[at + 32:at + 128] = original
                        image[at:at + 32] = b"\xe5" + bytes(31)
                    with self.assertRaises(native_pooleboot.PooleBootError):
                        native_pooleboot.inspect_media_bytes(bytes(image))

    def test_extended_loader_inherits_fix_and_rejects_parent_regression(self):
        kernel = native_elf_loader.build_fixture("minimal_relative_v1")
        image = native_kernel_load.build_media_bytes(self.efi,
            native_kernel_load.canonical_config_bytes(),
            native_kernel_load.canonical_manifest_bytes(kernel), kernel)
        self.assertEqual(struct.unpack_from("<H", image, self.start + 544 + 26)[0], 0)
        inspection = native_kernel_load.inspect_media_bytes(image)
        self.assertEqual(inspection["esp"]["label"], "POOLEOS ESP")
        json.dumps(inspection)
        files = self.independent_files(image)
        self.assertEqual(len(files), len(inspection["files"]))
        for record in inspection["files"]:
            self.assertEqual(native_pooleboot.sha256_bytes(files[record["path"]]), record["sha256"])
        changed = bytearray(image)
        struct.pack_into("<H", changed, self.start + 544 + 26, 2)
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.inspect_media_bytes(bytes(changed))


if __name__ == "__main__":
    unittest.main()
