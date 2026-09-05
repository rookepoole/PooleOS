"""Local demo acceptance tests; build and qualify the default package first."""

import json
import struct
import unittest
from pathlib import Path

from demos.native_iso import package, qualify

ROOT = Path(__file__).resolve().parents[2]


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory, path, cls.disk, cls.report = qualify.validate_local_package(ROOT / "outputs/native-demo-iso-pooleglass-v1")
        cls.iso = path.read_bytes()

    def reject(self, offset, replacement):
        data = bytearray(self.iso)
        data[offset:offset + len(replacement)] = replacement
        with self.assertRaises(ValueError):
            package.inspect_iso(bytes(data), disk=self.disk)

    def at(self, name):
        return self.report["files"][name]["lba"] * package.BLOCK

    def test_exact_payload_and_nonpromotion(self):
        self.assertEqual(package.inspect_iso(self.iso, disk=self.disk), self.report)
        for key in ("signed", "production_ready", "installer", "desktop_present", "physical_hardware_qualified"):
            self.assertIs(self.report["manifest"][key], False)

    def test_no_hybrid_mbr(self):
        self.reject(510, b"\x55\xaa")

    def test_truncation(self):
        with self.assertRaises(ValueError):
            package.inspect_iso(self.iso[:-1], disk=self.disk)

    def test_primary_signature(self):
        self.reject(16 * package.BLOCK + 1, b"XD001")

    def test_volume_endianness(self):
        self.reject(16 * package.BLOCK + 84, b"\x00\x00\x00\x01")

    def test_catalog_checksum(self):
        self.reject(self.at("BOOT.CAT;1") + 28, b"\x00\x00")

    def test_catalog_platform_even_with_valid_checksum(self):
        start = self.at("BOOT.CAT;1")
        catalog = bytearray(self.iso[start:start + 32])
        catalog[1] = 0
        catalog[28:30] = b"\x00\x00"
        struct.pack_into("<H", catalog, 28, -sum(struct.unpack("<16H", catalog)) & 0xFFFF)
        self.reject(start, catalog)

    def test_emulated_boot_entry(self):
        self.reject(self.at("BOOT.CAT;1") + 33, b"\x01")

    def test_wrong_efi_extent(self):
        self.reject(self.at("BOOT.CAT;1") + 40, b"\x00" * 4)

    def test_extra_catalog_entry(self):
        self.reject(self.at("BOOT.CAT;1") + 64, b"\x91")

    def test_optical_hidden_sector_primary(self):
        self.reject(self.at("EFI.IMG;1") + 28, struct.pack("<I", 2048))

    def test_optical_hidden_sector_backup(self):
        self.reject(self.at("EFI.IMG;1") + 6 * 512 + 28, struct.pack("<I", 2048))

    def test_esp_substitution(self):
        self.reject(self.at("EFI.IMG;1") + 66043391, b"\x7f")

    def test_manifest_promotion(self):
        start = self.at("MANIFEST.JSON;1")
        position = self.iso.index(b'"production_ready": false', start)
        self.reject(position, b'"production_ready": true ')

    def test_manifest_kernel_identity(self):
        start = self.at("MANIFEST.JSON;1")
        self.reject(self.iso.index(package.KERNEL_SHA256.encode(), start), b"0" * 64)

    def test_manifest_wrong_renderer(self):
        self.reject(self.iso.index(b"pooleglass_static_demo_v1", self.at("MANIFEST.JSON;1")), b"x" * 24)

    def test_authoring_reproducibility(self):
        def file_bytes(name):
            start = self.at(name)
            return self.iso[start:start + self.report["files"][name]["byte_count"]]
        first, _ = package.build_iso(self.disk, file_bytes("README.TXT;1"), file_bytes("LICENSE.TXT;1"))
        second, _ = package.build_iso(self.disk, file_bytes("README.TXT;1"), file_bytes("LICENSE.TXT;1"))
        self.assertEqual(first, second)
        self.assertEqual(first, self.iso)

    def test_clock_restoration_on_error(self):
        package.load_library()
        from pycdlib import dates, headervd, pycdlib
        modules = (dates, headervd, pycdlib)
        clocks = [module.time for module in modules]
        with self.assertRaises(RuntimeError):
            with package._fixed_authoring_clock():
                raise RuntimeError("test cleanup")
        self.assertEqual(clocks, [module.time for module in modules])

    def test_profile_only_optical_device_changes(self):
        _, base = qualify.native_tier0.validate_contracts(ROOT)
        original = json.dumps(base, sort_keys=True)
        result = qualify.optical_profile(base)
        args = result["base_argument_template"]
        self.assertEqual(json.dumps(base, sort_keys=True), original)
        self.assertEqual(args.count("-drive"), 3)
        self.assertIn("ide-cd,drive=pooleos_media,bus=ide.0,bootindex=1", args)
        self.assertEqual(args[args.index("-nic") + 1], "none")
        self.assertNotIn("-netdev", args)
        self.assertNotIn("-virtfs", args)

    def test_asset_receipt_exact(self):
        assets = ROOT / "demos/native_iso/boot/assets"
        receipt = json.loads((assets / "encoding.json").read_text())
        self.assertEqual(package.sha256((assets / "pooleglass-emblem.png").read_bytes()), receipt["source"]["pooleglass-emblem.png"])
        for name, binding in receipt["encoded"].items():
            data = (assets / name).read_bytes()
            self.assertEqual(len(data), binding["bytes"])
            self.assertEqual(package.sha256(data), binding["sha256"])

    def test_font_license_on_iso(self):
        notice = (ROOT / "demos/native_iso/boot/assets/FONT-LICENSE.txt").read_bytes()
        self.assertIn(notice, self.iso)

    def test_outside_package_rejected(self):
        with self.assertRaises(ValueError):
            qualify.validate_local_package(ROOT / "docs")

    def test_partial_completion_line_waits_for_delimiter(self):
        marker = qualify.locks.COMPLETION_MARKER
        self.assertFalse(qualify.completion_line_observed(marker))
        self.assertFalse(qualify.completion_line_observed(marker + b" terminal=halt"))
        self.assertTrue(qualify.completion_line_observed(marker + b" terminal=halt\r\n"))

    def test_embedded_completion_prefix_is_not_a_line(self):
        self.assertFalse(qualify.completion_line_observed(b"unrelated " + qualify.locks.COMPLETION_MARKER + b"\n"))


if __name__ == "__main__":
    unittest.main()
