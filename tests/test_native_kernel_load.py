import copy
import json
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_elf_loader, native_kernel_load, native_pooleboot  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


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


def valid_markers() -> list[str]:
    return [
        "POOLEBOOT/0.1 ENTRY",
        "POOLEBOOT/0.1 SYSTEM_TABLE PASS revision=0x00020046",
        "POOLEBOOT/0.1 BOOT_SERVICES PASS",
        "POOLEBOOT/0.1 WATCHDOG status=0x0000000000000000",
        "POOLEBOOT/0.1 CONSOLE PASS",
        "POOLEBOOT/0.1 CONFIG PASS count=10 acpi20=1 smbios3=0 smbios2=1",
        "POOLEBOOT/0.1 FILESYSTEM PASS loaded_image=1 simple_fs=1 root=1",
        "POOLEBOOT/0.1 BOOTCFG PASS bytes=229 entries=1 default_hash=61053F0E3EBBD272 timeout_ms=0 attempts=3 slot=1 manifest_max_bytes=65536",
        "POOLEBOOT/0.1 MANIFEST PASS bytes=2611 artifacts=7 id_hash=4A2625333244591C slot=1 version=1 minimum_secure_version=1",
        "POOLEBOOT/0.1 KERNEL_BINDING PASS version=1 file_bytes=139264 image_bytes=196608 sha256_prefix=BF1176019E9E4AF1 path=manifest",
        "POOLEBOOT/0.1 KERNEL_FILE PASS bytes=139264 path=manifest_development",
        "POOLEBOOT/0.1 KERNEL_LOAD PASS image_bytes=196608 pages=48 entry_offset=16384 relocations=40 files_closed=10 pools_freed=9 fnv1a64=80F8CD80B30B2EBA",
        "POOLEBOOT/0.1 ARTIFACT_SET PASS contract=PBART1 count=6 file_bytes=2663 pages=6 roles=2-7 fnv1a64=82B3843AECD6EEE5 retained=1 signatures=0 measured=0",
        "POOLEBOOT/0.1 GOP PASS width=1280 height=800 stride=1280 mode=0 format=BGR",
        "POOLEBOOT/0.1 FRAME READY",
        "POOLEBOOT/0.1 KERNEL_MAP_PLAN PASS contract=PKMAP2 mappings=4 kernel_pages=48 ro=6 rx=28 rw=14 wx=0 pml4=511 pdpt=510 pd=0 pt=0 leaf_fnv1a64=A671D0D8901064A5",
        "POOLEBOOT/0.1 KERNEL_MAP_ACTIVE PASS table_pages=4 kernel_pages=48 physical_bits=40 mapped_fnv1a64=80F8CD80B30B2EBA framebuffer=preserved cache_signature=00 first_page_bytes=2097152 last_page_bytes=2097152",
        "POOLEBOOT/0.1 KERNEL_MAP_RETAIN PASS table_pages=4 stack_pages=8 handoff_pages=256 guards=2 total_pages=312 stack_pt=49 handoff_pt=64 kernel_phys=000000001DDD9000 root=000000001DE52000 stack_phys=000000001DE56000 stack_top=FFFFFFFF80039000 handoff_phys=000000001DB37000 handoff_virt=FFFFFFFF80040000 retained_fnv1a64=0104C7FCE5941135 original_cr3=restored firmware_calls_while_active=0",
        "POOLEBOOT/0.1 PBP1_FINAL PASS bytes=4728 records=4 memory_entries=95 framebuffer=1 artifacts=7 descriptor_bytes=48 exit_attempts=1 message_crc32=7B4BF0F1 fnv1a64=D627368957E5654B state=boot_services_exited bytes_unchanged=1",
        "POOLEBOOT/0.1 EXIT_BOOT_SERVICES PASS contract=PBEXIT1 attempts=1 map_bytes=4560 descriptor_bytes=48 descriptors=95",
        "POOLEBOOT/0.1 FIRMWARE_BOUNDARY PASS calls_after_exit=0 kernel_pages=48 artifact_pages=6 table_pages=4 stack_pages=8 handoff_pages=256",
        "POOLEBOOT/0.1 BOUNDARY unsigned=1 secure_boot=not_tested selection=manifest_digest_untrusted artifacts=digest_verified_untrusted semantics=not_applied kernel=retained handoff=retained mappings=retained entry=not_called exit_boot_services=called transfer=stopped",
        "POOLEBOOT/0.1 STOP BEFORE TRANSFER",
    ]


class NativeKernelLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = native_kernel_load.read_json(ROOT / native_kernel_load.CONTRACT_RELATIVE)
        cls.readiness = native_kernel_load.read_json(ROOT / native_kernel_load.READINESS_RELATIVE)

    def test_contract_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, native_kernel_load.CONTRACT_SCHEMA_RELATIVE),
            (self.readiness, native_kernel_load.READINESS_SCHEMA_RELATIVE),
        )
        for value, schema_relative in cases:
            with self.subTest(schema=schema_relative):
                schema = native_kernel_load.read_json(ROOT / schema_relative)
                self.assertEqual([], list(validate_json(value, schema)))

    def test_contract_and_readiness_pass_semantic_validation(self) -> None:
        self.assertEqual([], native_kernel_load.contract_errors(self.contract, ROOT))
        self.assertEqual([], native_kernel_load.readiness_errors(self.readiness, ROOT))

    def test_canonical_config_is_exact_pbc1(self) -> None:
        data = native_kernel_load.canonical_config_bytes()
        self.assertEqual(229, len(data))
        self.assertTrue(data.endswith(b"end=PBC1\n"))
        self.assertIn(b"default_entry=normal\n", data)

    def test_extended_media_is_deterministic_and_exactly_inspected(self) -> None:
        efi = synthetic_pooleboot()
        config = native_kernel_load.canonical_config_bytes()
        kernel = native_elf_loader.build_fixture("minimal_relative_v1")
        manifest = native_kernel_load.canonical_manifest_bytes(kernel)
        first = native_kernel_load.build_media_bytes(efi, config, manifest, kernel)
        second = native_kernel_load.build_media_bytes(efi, config, manifest, kernel)
        self.assertEqual(first, second)
        inspection = native_kernel_load.inspect_media_bytes(first)
        self.assertEqual(
            [
                native_pooleboot.FALLBACK_PATH,
                native_kernel_load.CONFIG_PATH,
                native_kernel_load.MANIFEST_PATH,
                native_kernel_load.KERNEL_PATH,
                native_kernel_load.INITIAL_SYSTEM_PATH,
                native_kernel_load.RECOVERY_PATH,
                native_kernel_load.SYMBOLS_PATH,
                native_kernel_load.MICROCODE_PATH,
                native_kernel_load.FIRMWARE_PATH,
                native_kernel_load.POLICY_PATH,
            ],
            [item["path"] for item in inspection["files"]],
        )
        self.assertEqual("normal", inspection["config"]["default_entry"])
        self.assertEqual(4, len(inspection["kernel"]["plan"]["mappings"]))
        self.assertEqual("PINIT1", inspection["initial_system"]["contract_id"])
        self.assertEqual("PREC1", inspection["recovery"]["contract_id"])
        self.assertFalse(inspection["recovery"]["activation_allowed"])
        self.assertFalse(inspection["recovery"]["pooleboot_enforced"])
        self.assertFalse(inspection["recovery"]["poolekernel_enforced"])
        self.assertFalse(inspection["recovery"]["recovery_executed"])

    def test_extended_media_rejects_fat_and_config_mutations(self) -> None:
        media = bytearray(
            native_kernel_load.build_media_bytes(
                synthetic_pooleboot(),
                native_kernel_load.canonical_config_bytes(),
                native_kernel_load.canonical_manifest_bytes(
                    native_elf_loader.build_fixture("minimal_relative_v1")
                ),
                native_elf_loader.build_fixture("minimal_relative_v1"),
            )
        )
        inspection = native_kernel_load.inspect_media_bytes(bytes(media))
        fat_sectors = inspection["fat32"]["fat_sector_count"]
        second_fat = (
            native_pooleboot.ESP_START_LBA
            + native_pooleboot.FAT_RESERVED_SECTORS
            + fat_sectors
        ) * native_pooleboot.SECTOR_BYTES
        changed_fat = media[:]
        changed_fat[second_fat + 8] ^= 1
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.inspect_media_bytes(bytes(changed_fat))

        config_cluster = 5 + inspection["files"][0]["cluster_count"] + 1
        data_start_lba = (
            native_pooleboot.ESP_START_LBA
            + native_pooleboot.FAT_RESERVED_SECTORS
            + native_pooleboot.FAT_COUNT * fat_sectors
        )
        config_offset = (data_start_lba + config_cluster - 2) * native_pooleboot.SECTOR_BYTES
        changed_config = media[:]
        changed_config[config_offset] = ord("X")
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.inspect_media_bytes(bytes(changed_config))

    def test_marker_contract_captures_load_mapping_and_cleanup(self) -> None:
        summary = native_kernel_load.validate_markers(valid_markers())
        self.assertEqual(23, summary["marker_count"])
        self.assertEqual(6, summary["artifact_set"]["artifact_count"])
        self.assertEqual(48, summary["kernel"]["page_count"])
        self.assertEqual(0, summary["kernel_map"]["writable_executable_page_count"])
        self.assertEqual(48, summary["kernel_map"]["mapped_page_count"])
        self.assertTrue(summary["kernel_map"]["original_cr3_restored"])
        self.assertTrue(summary["kernel_map"]["tables_retained"])
        self.assertTrue(summary["kernel"]["pages_retained"])
        self.assertFalse(summary["pbp1"]["pre_exit"])
        self.assertTrue(summary["pbp1"]["boot_services_exited"])
        self.assertTrue(summary["boot_exit"]["stopped_before_transfer"])

    def test_marker_contract_rejects_omission_wx_and_page_mismatch(self) -> None:
        markers = valid_markers()
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.validate_markers(markers[:-1])
        writable = markers[:]
        writable[15] = writable[15].replace("wx=0", "wx=1")
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.validate_markers(writable)
        page_mismatch = markers[:]
        page_mismatch[11] = page_mismatch[11].replace("pages=48", "pages=49")
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.validate_markers(page_mismatch)
        active_mismatch = markers[:]
        active_mismatch[16] = active_mismatch[16].replace(
            "mapped_fnv1a64=80F8CD80B30B2EBA",
            "mapped_fnv1a64=0000000000000000",
        )
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.validate_markers(active_mismatch)
        retained_mismatch = markers[:]
        retained_mismatch[17] = retained_mismatch[17].replace(
            "firmware_calls_while_active=0", "firmware_calls_while_active=1"
        )
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.validate_markers(retained_mismatch)

    def test_claim_overreach_is_rejected(self) -> None:
        claims = native_kernel_load.expected_claims()
        native_kernel_load.validate_claims(claims)
        claims["kernel_entry_called"] = True
        with self.assertRaises(native_kernel_load.KernelLoadError):
            native_kernel_load.validate_claims(claims)

    def test_readiness_detects_stale_input_and_oracle_divergence(self) -> None:
        stale = copy.deepcopy(self.readiness)
        stale["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertTrue(
            any(
                "stale implementation input" in item
                for item in native_kernel_load.readiness_errors(stale, ROOT)
            )
        )
        divergent = copy.deepcopy(self.readiness)
        divergent["media"]["inspection"]["kernel"]["loaded_fnv1a64"] = "0" * 16
        self.assertTrue(
            any(
                "oracle" in item.lower()
                for item in native_kernel_load.readiness_errors(divergent, ROOT)
            )
        )
        command_drift = copy.deepcopy(self.readiness)
        command_drift["execution"]["normalized_command"][0] = "$WRONG_QEMU"
        self.assertTrue(
            any(
                "normalized command digest mismatch" in item
                for item in native_kernel_load.readiness_errors(command_drift, ROOT)
            )
        )

    def test_public_readiness_has_no_absolute_user_path(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertIsNone(native_pooleboot.ABSOLUTE_USER_PATH.search(encoded))


if __name__ == "__main__":
    unittest.main()
