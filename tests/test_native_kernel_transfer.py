import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_elf_loader,
    native_kernel_load,
    native_kernel_revalidation,
    native_kernel_transfer,
)
from tools import pooleos_release_gate  # noqa: E402


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
        "POOLEBOOT/0.1 MANIFEST PASS bytes=2615 artifacts=7 id_hash=4A2625333244591C slot=1 version=1 minimum_secure_version=1",
        "POOLEBOOT/0.1 KERNEL_BINDING PASS version=1 file_bytes=278528 image_bytes=319488 sha256_prefix=CDF33067B2421550 path=manifest",
        "POOLEBOOT/0.1 KERNEL_FILE PASS bytes=278528 path=manifest_development",
        "POOLEBOOT/0.1 KERNEL_LOAD PASS image_bytes=319488 pages=78 entry_offset=36864 relocations=667 files_closed=12 pools_freed=11 fnv1a64=149A9B2B3302281F",
        "POOLEBOOT/0.1 ARTIFACT_SET PASS contract=PBART1 count=6 file_bytes=8761 pages=6 roles=2-7 fnv1a64=7D1A0D1884A3F865 retained=1 signatures=0 measured=0",
        "POOLEBOOT/0.1 INNER_SET PASS proof=N5-INNER-LIVE-PARSE-001 artifacts=6 parsers=6 bindings=6 denials=6 file_bytes=8761 payload_bytes=8185 sha256=6C2A46E350F151689E043CE8E0EF3275FB984F1355D691A651AA044E659F201F retained=1 authority_grants=0 actions=0 state_writes=0 hardware_observations=0",
        "POOLEBOOT/0.1 TRUST_STATE DENY contract=PBTRUST1 policy_bytes=320 state_bytes=256 bindings=14 denials=1 denial=pbtrust_policy_unsigned policy_sha256=24CDE834B654F3F40244E3CA70C6893BA5E5F511434F28B237FC76D220B6C139 state_sha256=721C920FDF7E341EEE137E5E26EA90AE8FD6419B0125E2B0A32310FD546D33D8 source=esp_candidate auth=missing monotonic=missing signatures=0 authority_grants=0 state_writes=0",
        "POOLEBOOT/0.1 GOP PASS width=1280 height=800 stride=1280 mode=0 format=BGR",
        "POOLEBOOT/0.1 FRAME READY",
        "POOLEBOOT/0.1 KERNEL_MAP_PLAN PASS contract=PKMAP2 mappings=4 kernel_pages=78 ro=16 rx=52 rw=10 wx=0 pml4=511 pdpt=510 pd=0 pt=0 leaf_fnv1a64=8809E8C8C7F7BBE4",
        "POOLEBOOT/0.1 KERNEL_MAP_ACTIVE PASS table_pages=4 kernel_pages=78 physical_bits=40 mapped_fnv1a64=149A9B2B3302281F framebuffer=preserved cache_signature=00 first_page_bytes=2097152 last_page_bytes=2097152",
        "POOLEBOOT/0.1 KERNEL_MAP_RETAIN PASS table_pages=4 stack_pages=14 handoff_pages=256 guards=2 total_pages=348 stack_pt=79 handoff_pt=94 kernel_phys=000000001DD6C000 root=000000001DE49000 stack_phys=000000001DE4D000 stack_top=FFFFFFFF8005D000 handoff_phys=000000001DACA000 handoff_virt=FFFFFFFF8005E000 retained_fnv1a64=F8B7A67F2DC7D6E7 original_cr3=restored firmware_calls_while_active=0",
        "POOLEBOOT/0.1 PBP1_FINAL PASS bytes=5048 records=4 memory_entries=97 framebuffer=1 artifacts=10 descriptor_bytes=48 exit_attempts=1 message_crc32=2A9AF4FC fnv1a64=BD0E37040D3F3FA8 state=boot_services_exited bytes_unchanged=1",
        "POOLEBOOT/0.1 EXIT_BOOT_SERVICES PASS contract=PBEXIT1 attempts=1 map_bytes=4656 descriptor_bytes=48 descriptors=97",
        "POOLEBOOT/0.1 FIRMWARE_BOUNDARY PASS calls_after_exit=0 kernel_pages=78 artifact_pages=9 table_pages=4 stack_pages=14 handoff_pages=256",
        "POOLEBOOT/0.1 TRANSFER_ARM PASS contract=PKXFER1 mode=development emulator_only=1 entry=FFFFFFFF80009000 handoff=FFFFFFFF8005E000 bytes=5048 stack_top=FFFFFFFF8005D000 root=000000001DE49000 cr3=000000001DE49000 trap_scenario=0 signatures=0 authority=0 actions=0 writes=0 firmware_calls_after_exit=0",
        native_kernel_transfer.TRANSFER_BOUNDARY,
        "POOLEOS:KERNEL:ENTRY PASS contract=PKENTRY1 transfer_contract=PKXFER1 build=PKBUILD1-CYCLE132-N9-PMM-GROWTH-AUTOMATION-001 entry_count=1 serial=present",
        "POOLEOS:KERNEL:STATE PASS handoff=0xFFFFFFFF8005E000 bytes=5048 entry=0xFFFFFFFF80009000 stack_top=0xFFFFFFFF8005D000 root=0x000000001DE49000 cr3=0x000000001DE49000 rflags_if=0 rflags_df=0",
        "POOLEOS:KERNEL:PBP1 PASS profile=development records=4 artifacts=10 production_profile_valid=0",
        "POOLEOS:KERNEL:PKREVAL PASS contract=PKREVAL1 files=9 artifacts=6 parsers=9 manifest_bytes=2615 retained_bytes=11952 retained_set_sha256=6C2A46E350F151689E043CE8E0EF3275FB984F1355D691A651AA044E659F201F policy_sha256=24CDE834B654F3F40244E3CA70C6893BA5E5F511434F28B237FC76D220B6C139 state_sha256=721C920FDF7E341EEE137E5E26EA90AE8FD6419B0125E2B0A32310FD546D33D8 denial=pbtrust_policy_unsigned authority=0 actions=0 writes=0",
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0",
    ]


class NativeKernelTransferTests(unittest.TestCase):
    def test_contract_and_generated_readiness_are_current(self) -> None:
        contract = native_kernel_transfer.read_json(ROOT / native_kernel_transfer.CONTRACT_RELATIVE)
        readiness = native_kernel_transfer.read_json(ROOT / native_kernel_transfer.READINESS_RELATIVE)
        self.assertEqual([], native_kernel_transfer.contract_errors(contract))
        self.assertEqual([], native_kernel_transfer.readiness_errors(readiness, ROOT))
        release_check = pooleos_release_gate.check_native_kernel_transfer_readiness()
        self.assertTrue(release_check["ok"], release_check["detail"])

    def test_complete_marker_sequence_is_cross_bound(self) -> None:
        summary = native_kernel_transfer.validate_markers(valid_markers())
        self.assertEqual(30, summary["marker_count"])
        self.assertEqual(0xFFFF_FFFF_8000_9000, summary["kernel_state"]["entry"])
        self.assertEqual(9, summary["kernel_revalidation"]["retained_file_count"])
        self.assertEqual("halt", summary["kernel_terminal"]["terminal"])

    def test_extractor_keeps_only_boot_and_kernel_evidence(self) -> None:
        raw = b"noise\r\n" + b"\r\n".join(item.encode("ascii") for item in valid_markers())
        self.assertEqual(valid_markers(), native_kernel_transfer.extract_markers(raw))

    def test_transfer_address_and_cpu_state_mutations_reject(self) -> None:
        cases = ((23, "entry=FFFFFFFF80009000", "entry=FFFFFFFF8000A000"), (26, "rflags_if=0", "rflags_if=1"), (26, "cr3=0x000000001DE49000", "cr3=0x000000001DE49001"))
        for index, old, new in cases:
            with self.subTest(field=old):
                candidate = valid_markers()
                candidate[index] = candidate[index].replace(old, new)
                with self.assertRaises(native_kernel_transfer.KernelTransferError):
                    native_kernel_transfer.validate_markers(candidate)

    def test_profile_revalidation_and_authority_mutations_reject(self) -> None:
        cases = ((27, "production_profile_valid=0", "production_profile_valid=1"), (28, "files=9", "files=8"), (28, "authority=0", "authority=1"), (29, "writes=0", "writes=1"))
        for index, old, new in cases:
            with self.subTest(field=old):
                candidate = valid_markers()
                candidate[index] = candidate[index].replace(old, new)
                with self.assertRaises(native_kernel_transfer.KernelTransferError):
                    native_kernel_transfer.validate_markers(candidate)

    def test_marker_omission_order_duplicate_and_return_reject(self) -> None:
        candidates = [valid_markers()[:-1], valid_markers(), valid_markers(), valid_markers()]
        candidates[1][23], candidates[1][24] = candidates[1][24], candidates[1][23]
        candidates[2].insert(23, candidates[2][23])
        candidates[3].append("POOLEOS:KERNEL:RETURN FAIL contract=PKXFER1")
        for candidate in candidates:
            with self.assertRaises(native_kernel_transfer.KernelTransferError):
                native_kernel_transfer.validate_markers(candidate)

    def test_transcript_binding_covers_transfer_critical_core(self) -> None:
        marker_summary = native_kernel_transfer.validate_markers(valid_markers())
        transcript = {
            "boot_services_exited": True,
            "exit_development_profile_validated": True,
            "kernel_entry_profile_rejected": True,
            "record_count": 4,
            "artifact_count": 10,
            "byte_count": 5048,
            "core": {
                "kernel_entry_virtual": "FFFFFFFF80009000",
                "initial_stack_top_virtual": "FFFFFFFF8005D000",
                "page_table_root_physical": "000000001DE49000",
                "handoff_virtual_base": "FFFFFFFF8005E000",
                "handoff_byte_count": 5048,
            },
        }
        self.assertTrue(
            native_kernel_transfer.validate_transcript_binding(marker_summary, transcript)[
                "exact_transfer_fields_bound"
            ]
        )
        mutated = copy.deepcopy(transcript)
        mutated["core"]["page_table_root_physical"] = "000000001DE4A000"
        with self.assertRaises(native_kernel_transfer.KernelTransferError):
            native_kernel_transfer.validate_transcript_binding(marker_summary, mutated)

    def test_independent_revalidation_binding_matches_exact_oracle(self) -> None:
        bundle = native_kernel_revalidation.canonical_bundle()
        oracle = native_kernel_revalidation.revalidate_development(
            bundle.handoff, bundle.files, bundle.physical_bases
        )
        marker_summary = {"kernel_revalidation": oracle.copy()}
        result = native_kernel_transfer.validate_revalidation_binding(
            marker_summary, bundle.handoff, bundle.files
        )
        self.assertTrue(result["guest_host_exact_match"])
        marker_summary["kernel_revalidation"]["parser_count"] = 8
        with self.assertRaises(native_kernel_transfer.KernelTransferError):
            native_kernel_transfer.validate_revalidation_binding(
                marker_summary, bundle.handoff, bundle.files
            )

    def test_canonical_media_inputs_form_nine_retained_files(self) -> None:
        kernel = native_elf_loader.build_fixture("minimal_relative_v1")
        artifacts = native_kernel_load.canonical_artifact_files()
        manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifacts)
        files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifacts)
        self.assertEqual(9, len(files))
        self.assertEqual(manifest, files[6])


if __name__ == "__main__":
    unittest.main()
