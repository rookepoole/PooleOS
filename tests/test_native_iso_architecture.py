import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

from native_iso_fixture import DATA_START, FAT_SECTORS, DEFAULT_FILES, fat_image, iso_image
from demos.native_iso.bootstrap import load_library
from runtime import native_iso_media as media
from tools.check_native_iso_architecture import scan_iso, inspect_file


class NativeIsoArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.esp, cls.positions = fat_image()
        cls.iso = iso_image(cls.esp, {"/NOTE.BIN;1": b"notes", "/KEEP.BIN;1": b"keep"})
        cls.policy = json.loads((ROOT / "specs/native-release-architecture-policy.json").read_bytes())
        cls.root_lba = media.paired(cls.iso, 16 * 2048 + 158, 4)
        cls.catalog = media.number(cls.iso, 17 * 2048 + 71, 4) * 2048

    def reject_iso(self, offset, value):
        raw = bytearray(self.iso)
        raw[offset:offset + len(value)] = value
        report = scan_iso(bytes(raw))
        self.assertFalse(report["architecture_conformance_passed"], report)
        self.assertFalse(report["production_ready"])

    def test_synthetic_policy_positive_is_not_executable_or_production_evidence(self):
        report = scan_iso(self.iso)
        self.assertEqual(report["violations"], [])
        self.assertTrue(report["structural_passed"])
        self.assertTrue(report["architecture_conformance_passed"])
        self.assertFalse(report["production_promotion_allowed"])
        self.assertEqual(len([f for f in report["files"] if f["namespace"] == "esp"]), 5)

    def test_independent_pycdlib_file_bytes_agree(self):
        library = load_library()
        iso = library.PyCdlib()
        iso.open_fp(io.BytesIO(self.iso))
        try:
            files, _ = media.iso_files(self.iso)
            for path in ("EFI.IMG", "NOTE.BIN", "KEEP.BIN"):
                output = io.BytesIO()
                iso.get_file_from_iso_fp(output, iso_path="/" + path + ";1")
                self.assertEqual(files[path]["data"], output.getvalue())
        finally:
            iso.close()

    def test_every_forbidden_marker_in_decoded_fragmented_efi_file(self):
        for marker in self.policy["forbidden_ascii_markers"]:
            with self.subTest(marker=marker):
                files = dict(DEFAULT_FILES)
                payload = bytearray(files["EFI/BOOT/BOOTX64.EFI"])
                payload[506:506 + len(marker)] = marker.encode()
                files["EFI/BOOT/BOOTX64.EFI"] = bytes(payload)
                esp, positions = fat_image(files)
                raw = bytearray(esp)
                first = positions["clusters"]["EFI/BOOT/BOOTX64.EFI"]
                replacement = positions["next_free"] + 7
                old = DATA_START + (first + 1 - 2) * 512
                new = DATA_START + (replacement - 2) * 512
                successor = struct.unpack_from("<I", raw, 32 * 512 + (first + 1) * 4)[0]
                raw[new:new + 512], raw[old:old + 512] = raw[old:old + 512], bytes(512)
                for base in (32 * 512, (32 + FAT_SECTORS) * 512):
                    struct.pack_into("<I", raw, base + first * 4, replacement)
                    struct.pack_into("<I", raw, base + (first + 1) * 4, 0)
                    struct.pack_into("<I", raw, base + replacement * 4, successor)
                report = scan_iso(iso_image(bytes(raw)))
                self.assertTrue(report["structural_passed"], report["violations"])
                self.assertTrue(any(v["type"] == "forbidden_content_marker" and v["rule"] == marker for v in report["violations"]))

    def test_unusual_extension_and_hidden_files_are_scanned(self):
        esp, positions = fat_image({**DEFAULT_FILES, "hidden.dat": b"GNU GRUB"})
        raw = bytearray(esp)
        raw[positions["entries"]["hidden.dat"] + 11] |= 2
        report = scan_iso(iso_image(bytes(raw), {"/EXTRA.XYZ;1": b"Linux version 6"}))
        self.assertTrue(report["structural_passed"])
        self.assertEqual(sum(v["type"] == "forbidden_content_marker" for v in report["violations"]), 2)

    def test_prohibited_long_and_short_paths(self):
        for path in ("boot/vmlinuz", "boot/grub/config", "EFI/VENDOR/grubx64.efi", "etc/systemd/test", "etc/debian_version", "etc/buildroot-release", "usr/lib/systemd/test", "var/lib/dpkg/status"):
            with self.subTest(path=path):
                esp, _ = fat_image({**DEFAULT_FILES, path: b"fixture"})
                report = scan_iso(iso_image(esp))
                self.assertTrue(report["structural_passed"], report["violations"])
                self.assertTrue(any(v["type"] == "forbidden_path" for v in report["violations"]), report)

    def test_required_objects_cannot_be_borrowed_from_outer_iso(self):
        files = dict(DEFAULT_FILES)
        del files["EFI/BOOT/BOOTX64.EFI"]
        esp, _ = fat_image(files)
        report = scan_iso(iso_image(esp, {"/BOOTX64.EFI;1": b"fixture"}))
        self.assertTrue(report["structural_passed"])
        self.assertTrue(any(v["path"] == "esp:/EFI/BOOT/BOOTX64.EFI" for v in report["violations"]))

    def test_wrong_root_parent_is_reported_without_losing_inventory(self):
        raw = bytearray(self.esp)
        first = self.positions["clusters"]["EFI"]
        struct.pack_into("<H", raw, DATA_START + (first - 2) * 512 + 32 + 26, 2)
        report = scan_iso(iso_image(bytes(raw)))
        self.assertFalse(report["structural_passed"])
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("root-parent", report["violations"][0]["rule"])
        self.assertEqual(len([f for f in report["files"] if f["namespace"] == "esp"]), 5)

    def test_fat_chain_cycles_crosslinks_orphans_and_copy_disagreement(self):
        first = self.positions["clusters"]["EFI/BOOT/BOOTX64.EFI"]
        cases = [(first, first), (first, 1), (first, 0x0FFFFFF7), (first, 0x0FFFFFF0),
                 (first, self.positions["clusters"]["EFI"]), (self.positions["next_free"], 0x0FFFFFFF)]
        for cluster, value in cases:
            with self.subTest(cluster=cluster, value=value):
                raw = bytearray(self.esp)
                for base in (32 * 512, (32 + FAT_SECTORS) * 512):
                    struct.pack_into("<I", raw, base + cluster * 4, value)
                with self.assertRaises(media.MediaError):
                    media.fat_files(bytes(raw))
        raw = bytearray(self.esp)
        raw[32 * 512 + first * 4] ^= 1
        with self.assertRaisesRegex(media.MediaError, "copies"):
            media.fat_files(bytes(raw))

    def test_fat_size_slack_free_clusters_and_directory_padding(self):
        entry = self.positions["entries"]["pooleos/PooleKernel.elf"]
        first = self.positions["clusters"]["pooleos/PooleKernel.elf"]
        mutations = [(entry + 28, struct.pack("<I", 0xFFFFFFFF)),
                     (DATA_START + (first - 2) * 512 + 100, b"X"),
                     (DATA_START + (self.positions["next_free"] - 2) * 512, b"X"),
                     (DATA_START + 500, b"X"), (32, struct.pack("<I", 1))]
        for offset, value in mutations:
            with self.subTest(offset=offset):
                raw = bytearray(self.esp)
                raw[offset:offset + len(value)] = value
                with self.assertRaises(media.MediaError):
                    media.fat_files(bytes(raw))

    def test_lfn_checksum_ordinal_and_alias_collision(self):
        entry = self.positions["entries"]["pooleos/PooleKernel.elf"]
        for offset in (entry - 32, entry - 32 + 13, entry - 32 + 26):
            raw = bytearray(self.esp)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(media.MediaError):
                media.fat_files(bytes(raw))

    def test_deleted_or_missing_dot_directories_reject(self):
        first = self.positions["clusters"]["EFI"]
        for value in (0, 0xE5):
            raw = bytearray(self.esp)
            raw[DATA_START + (first - 2) * 512] = value
            with self.subTest(value=value), self.assertRaises(media.MediaError):
                media.fat_files(bytes(raw))

    def test_iso_descriptor_geometry_and_hidden_system_area(self):
        for offset, value in ((0, b"X"), (16 * 2048 + 1, b"BAD!!"), (16 * 2048 + 84, bytes(4)),
                              (16 * 2048 + 128, b"\0\0"), (18 * 2048, b"\x02")):
            with self.subTest(offset=offset):
                self.reject_iso(offset, value)
        self.assertFalse(scan_iso(self.iso[:-1])["architecture_conformance_passed"])

    def test_catalog_platform_checksum_multiple_entries_and_extent(self):
        for offset, value in ((self.catalog + 1, b"\0"), (self.catalog + 28, b"\0\0"),
                              (self.catalog + 33, b"\x01"), (self.catalog + 64, b"\x91"),
                              (self.catalog + 40, bytes(4)), (self.catalog + 38, b"\x02\0")):
            with self.subTest(offset=offset):
                self.reject_iso(offset, value)

    def test_iso_path_table_and_directory_bounds(self):
        little = media.number(self.iso, 16 * 2048 + 140, 4) * 2048
        for offset, value in ((little + 2, bytes(4)), (self.root_lba * 2048, b"\x02"),
                              (self.root_lba * 2048 + 25, b"\x80"),
                              (16 * 2048 + 158, b"\xff" * 8)):
            with self.subTest(offset=offset):
                self.reject_iso(offset, value)

    def test_cli_reads_input_and_refuses_to_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            image, report = Path(directory) / "input.iso", Path(directory) / "report.json"
            image.write_bytes(self.iso)
            cmd = [sys.executable, "-B", str(ROOT / "tools/check_native_iso_architecture.py"), "--iso", str(image), "--out", str(report)]
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            original = report.read_bytes()
            self.assertEqual(subprocess.run(cmd, capture_output=True, timeout=30).returncode, 2)
            self.assertEqual(report.read_bytes(), original)
            self.assertEqual(image.read_bytes(), self.iso)
            with self.assertRaises(ValueError):
                inspect_file(Path(directory))


    def test_release_gate_inspects_actual_bytes_and_handles_missing_media(self):
        from tools.pooleos_release_gate import check_native_iso_architecture

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.iso"
            self.assertFalse(check_native_iso_architecture(path)["ok"])
            path.write_bytes(self.iso)
            self.assertTrue(check_native_iso_architecture(path)["ok"])
            path.write_bytes(b"invalid")
            self.assertFalse(check_native_iso_architecture(path)["ok"])

    def test_metadata_marker_and_duplicate_iso_name_are_not_hidden(self):
        raw = bytearray(self.iso)
        raw[16 * 2048 + 883:16 * 2048 + 891] = b"GNU GRUB"
        self.assertTrue(any(v["rule"] == "GNU GRUB" for v in scan_iso(bytes(raw))["violations"]))
        raw = bytearray(self.iso)
        at = raw.index(b"NOTE.BIN;1", self.root_lba * 2048)
        raw[at:at + 10] = b"KEEP.BIN;1"
        self.assertFalse(scan_iso(bytes(raw))["structural_passed"])

    def test_short_alias_cannot_hide_a_forbidden_loader(self):
        path = "EFI/VENDOR/harmless-long-name.efi"
        esp, positions = fat_image({**DEFAULT_FILES, path: b"fixture"})
        raw = bytearray(esp)
        entry = positions["entries"][path]
        alias, checksum = b"GRUBX64 EFI", 0
        for value in alias:
            checksum = (((checksum & 1) << 7) + (checksum >> 1) + value) & 255
        raw[entry:entry + 11] = alias
        offset = entry - 32
        while raw[offset + 11] == 15:
            raw[offset + 13] = checksum
            offset -= 32
        report = scan_iso(iso_image(bytes(raw)))
        self.assertTrue(report["structural_passed"])
        self.assertTrue(any(v["type"] == "forbidden_path" and v["path"].endswith("GRUBX64.EFI") for v in report["violations"]))

    def test_fat_alias_collision_and_unsupported_long_directory_reject(self):
        raw = bytearray(self.esp)
        first = self.positions["entries"]["EFI"]
        second = self.positions["entries"]["pooleos"]
        raw[second:second + 11] = raw[first:first + 11]
        with self.assertRaisesRegex(media.MediaError, "collision"):
            media.fat_files(bytes(raw))
        esp, _ = fat_image({**DEFAULT_FILES, "long-directory/file": b"fixture"})
        with self.assertRaisesRegex(media.MediaError, "long directory"):
            media.fat_files(esp)


if __name__ == "__main__":
    unittest.main()
