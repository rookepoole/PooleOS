import copy
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_pooleboot  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


def synthetic_pooleboot() -> bytes:
    data = bytearray(512)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 0, 0, 0, 0, 240, 0x22)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<II", data, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", data, optional + 56, 0x2000, 0x200)
    struct.pack_into("<H", data, optional + 68, 10)
    struct.pack_into("<I", data, optional + 108, 0)
    return bytes(data)


class NativePooleBootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = native_pooleboot.read_json(ROOT / native_pooleboot.CONTRACT_RELATIVE)
        cls.readiness = native_pooleboot.read_json(ROOT / native_pooleboot.READINESS_RELATIVE)

    def test_contract_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, native_pooleboot.CONTRACT_SCHEMA_RELATIVE),
            (self.readiness, native_pooleboot.READINESS_SCHEMA_RELATIVE),
        )
        for value, schema_relative in cases:
            with self.subTest(schema=schema_relative):
                schema = native_pooleboot.read_json(ROOT / schema_relative)
                self.assertEqual([], list(validate_json(value, schema)))

    def test_contract_and_readiness_pass_semantic_validation(self) -> None:
        self.assertEqual([], native_pooleboot.proof_contract_errors(self.contract, ROOT))
        self.assertEqual([], native_pooleboot.readiness_contract_errors(self.readiness, ROOT))

    def test_readiness_is_stale_when_an_input_binding_changes(self) -> None:
        altered = copy.deepcopy(self.readiness)
        altered["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        errors = native_pooleboot.readiness_contract_errors(altered, ROOT)
        self.assertTrue(any("stale implementation input" in item for item in errors))

    def test_report_records_reproducible_binary_media_and_guest_runs(self) -> None:
        build = self.readiness["build"]
        media = self.readiness["media"]["inspection"]
        execution = self.readiness["execution"]
        self.assertEqual((2, True), (build["clean_build_count"], build["exact_clean_build_match"]))
        self.assertGreater(build["byte_count"], 13_312)
        self.assertEqual(build["sha256"], media["files"][0]["sha256"])
        self.assertEqual("EFI/BOOT/BOOTX64.EFI", media["files"][0]["path"])
        self.assertEqual(67_108_864, media["image"]["byte_count"])
        self.assertTrue(media["gpt"]["primary_backup_entries_exact_match"])
        self.assertTrue(media["fat32"]["fat_copies_exact_match"])
        self.assertEqual(2, execution["run_count"])
        self.assertTrue(execution["exact_marker_match"])
        self.assertTrue(execution["exact_screenshot_match"])

    def test_report_preserves_all_nonclaims(self) -> None:
        self.assertEqual(native_pooleboot.expected_claims(), self.readiness["claims"])
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n5_exit_gate_satisfied"])
        self.assertEqual(0, self.readiness["summary"]["production_claim_count"])

    def test_release_gate_accepts_exact_bounded_receipt(self) -> None:
        check = pooleos_release_gate.check_native_pooleboot_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("production_claims=0", check["detail"])

    def test_negative_control_register_is_complete_and_passing(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual(list(native_pooleboot.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_marker_parser_rejects_omission_order_and_bad_geometry(self) -> None:
        markers = self.readiness["execution"]["runs"][0]["markers"]
        summary = native_pooleboot.validate_markers(markers)
        self.assertEqual(24, summary["marker_count"])
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.validate_markers(markers[:-1])
        reordered = markers[:]
        reordered[0], reordered[1] = reordered[1], reordered[0]
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.validate_markers(reordered)
        malformed = markers[:]
        malformed[12] = "POOLEBOOT/0.1 GOP PASS width=1 height=1 stride=1 mode=0 format=BGR"
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.validate_markers(malformed)

    def test_claim_validator_rejects_production_overreach(self) -> None:
        claims = native_pooleboot.expected_claims()
        native_pooleboot.validate_claims(claims)
        claims["production_ready"] = True
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.validate_claims(claims)

    def test_media_builder_and_independent_inspector_are_deterministic(self) -> None:
        binary = synthetic_pooleboot()
        first = native_pooleboot.build_media_bytes(binary)
        second = native_pooleboot.build_media_bytes(binary)
        self.assertEqual(first, second)
        inspection = native_pooleboot.inspect_media_bytes(first)
        self.assertEqual(native_pooleboot.FALLBACK_PATH, inspection["files"][0]["path"])
        self.assertEqual(native_pooleboot.sha256_bytes(binary), inspection["files"][0]["sha256"])

    def test_media_path_policy_accepts_safe_files_and_rejects_unsafe_targets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pooleboot-path-policy-") as temporary:
            root = Path(temporary) / "repo"
            efi = root / "native" / "target" / "PooleBoot.efi"
            efi.parent.mkdir(parents=True)
            efi.write_bytes(synthetic_pooleboot())
            (root / "tmp").mkdir()
            (root / "runs" / "native-tier0").mkdir(parents=True)

            self.assertEqual(
                efi.resolve(),
                native_pooleboot.validate_workspace_input_file(
                    root, efi, ".efi", native_pooleboot.MAX_EFI_BYTES
                ),
            )
            oversized_efi = efi.with_name("Oversized.efi")
            oversized_efi.write_bytes(b"MZ" + bytes(native_pooleboot.MAX_EFI_BYTES - 1))
            with self.assertRaises(native_pooleboot.PooleBootError):
                native_pooleboot.validate_workspace_input_file(
                    root, oversized_efi, ".efi", native_pooleboot.MAX_EFI_BYTES
                )
            safe_image = root / "tmp" / "proof.img"
            safe_inspection = root / "runs" / "native-tier0" / "proof.json"
            self.assertEqual(
                safe_image.resolve(),
                native_pooleboot.validate_workspace_output_path(root, safe_image, ".img"),
            )
            self.assertEqual(
                safe_inspection.resolve(),
                native_pooleboot.validate_workspace_output_path(
                    root, safe_inspection, ".json"
                ),
            )

            rejected = (
                Path(r"\\.\PhysicalDrive0"),
                root.parent / "outside.img",
                root / "docs" / "clobber.img",
                root / "tmp" / "NUL.img",
                root / "tmp" / "proof.img:stream",
                root / "tmp" / "proof.txt",
            )
            for candidate in rejected:
                with self.subTest(candidate=str(candidate)):
                    with self.assertRaises(native_pooleboot.PooleBootError):
                        native_pooleboot.validate_workspace_output_path(
                            root, candidate, ".img"
                        )

    def test_media_inspector_rejects_crc_fat_and_path_mutations(self) -> None:
        media = bytearray(native_pooleboot.build_media_bytes(synthetic_pooleboot()))
        primary_crc = media[:]
        primary_crc[native_pooleboot.PRIMARY_HEADER_LBA * 512 + 24] ^= 1
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.inspect_media_bytes(bytes(primary_crc))

        inspection = native_pooleboot.inspect_media_bytes(bytes(media))
        fat_sectors = inspection["fat32"]["fat_sector_count"]
        first_fat = (native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS) * 512
        fat_copy = media[:]
        fat_copy[first_fat + fat_sectors * 512 + 8] ^= 1
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.inspect_media_bytes(bytes(fat_copy))

        data_lba = (
            native_pooleboot.ESP_START_LBA
            + native_pooleboot.FAT_RESERVED_SECTORS
            + native_pooleboot.FAT_COUNT * fat_sectors
        )
        wrong_path = media[:]
        wrong_path[(data_lba + 2) * 512 + 64] = ord("X")
        with self.assertRaises(native_pooleboot.PooleBootError):
            native_pooleboot.inspect_media_bytes(bytes(wrong_path))

    def test_public_receipt_has_no_absolute_user_path(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertIsNone(native_pooleboot.ABSOLUTE_USER_PATH.search(encoded))


if __name__ == "__main__":
    unittest.main()
