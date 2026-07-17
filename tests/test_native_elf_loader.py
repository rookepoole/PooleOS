import copy
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_elf_loader as elf  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


class NativeElfLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = elf.read_json(ROOT / elf.CONTRACT_RELATIVE)
        cls.golden = elf.read_json(ROOT / elf.GOLDEN_RELATIVE)
        cls.readiness = elf.read_json(ROOT / elf.READINESS_RELATIVE)

    def test_contract_golden_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, elf.CONTRACT_SCHEMA_RELATIVE),
            (self.golden, elf.GOLDEN_SCHEMA_RELATIVE),
            (self.readiness, elf.READINESS_SCHEMA_RELATIVE),
        )
        for value, relative in cases:
            with self.subTest(schema=str(relative)):
                self.assertEqual([], validate_json(value, elf.read_json(ROOT / relative)))

    def test_semantic_contracts_and_bindings_pass(self) -> None:
        self.assertEqual([], elf.contract_errors(self.contract))
        self.assertEqual([], elf.golden_errors(self.golden))
        self.assertEqual([], elf.readiness_errors(self.readiness))

    def test_generator_reproduces_exact_golden_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "golden.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/generate_native_elf_loader_vectors.py"),
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout)
            self.assertEqual((ROOT / elf.GOLDEN_RELATIVE).read_bytes(), output.read_bytes())

    def test_all_golden_vectors_match_exact_file_and_loaded_bytes(self) -> None:
        for vector in self.golden["vectors"]:
            with self.subTest(vector=vector["id"]):
                data = bytes.fromhex(vector["file_hex"])
                plan, loaded = elf.load(data, vector["physical_base"], vector["virtual_base"])
                self.assertEqual(vector["file_byte_count"], len(data))
                self.assertEqual(vector["file_sha256"], elf.sha256_bytes(data))
                self.assertEqual(vector["image_byte_count"], plan.image_size)
                self.assertEqual(vector["loaded_sha256"], elf.sha256_bytes(loaded[: plan.image_size]))
                self.assertEqual(vector["semantic_summary"], elf.semantic_summary(plan, loaded))

    def test_relative_relocations_and_bss_are_exact(self) -> None:
        profile = elf.vector_profiles()[0]
        data = elf.build_fixture(str(profile["id"]))
        plan, loaded = elf.load(data, int(profile["physical_base"]), int(profile["virtual_base"]))
        target_a, _, addend_a = struct.unpack_from("<QQq", data, plan.relocation_address)
        target_b, _, addend_b = struct.unpack_from("<QQq", data, plan.relocation_address + 24)
        self.assertEqual(plan.virtual_base + addend_a, struct.unpack_from("<Q", loaded, target_a)[0])
        self.assertEqual(plan.virtual_base + addend_b, struct.unpack_from("<Q", loaded, target_b)[0])
        self.assertEqual(bytes(elf.PAGE_SIZE), loaded[-elf.PAGE_SIZE :])

    def test_upper_bound_vector_exercises_all_4096_relocations(self) -> None:
        profile = elf.vector_profiles()[2]
        data = elf.build_fixture(str(profile["id"]))
        plan, _ = elf.load(data, int(profile["physical_base"]), int(profile["virtual_base"]))
        self.assertEqual(elf.MAX_RELOCATIONS, plan.relocation_count)
        self.assertLessEqual(len(data), elf.MAX_FILE_BYTES)
        self.assertLessEqual(plan.image_size, elf.MAX_IMAGE_BYTES)

    def test_mapping_plan_is_page_exact_and_wx_free(self) -> None:
        profile = elf.vector_profiles()[1]
        plan = elf.inspect(
            elf.build_fixture(str(profile["id"])), int(profile["physical_base"]), int(profile["virtual_base"])
        )
        self.assertEqual(("r", "rx", "r", "rw"), tuple(mapping.permissions for mapping in plan.mappings))
        self.assertEqual(plan.image_size, sum(mapping.memory_size for mapping in plan.mappings))
        for mapping in plan.mappings:
            self.assertEqual(0, mapping.virtual_offset % elf.PAGE_SIZE)
            self.assertEqual(0, mapping.memory_size % elf.PAGE_SIZE)
            self.assertNotEqual("rwx", mapping.permissions)

    def test_general_dynamic_linker_features_fail_closed(self) -> None:
        base = elf.build_fixture("minimal_relative_v1")
        cases = []
        for segment_type in (3, 4, 5, 7):
            changed = bytearray(base)
            struct.pack_into("<I", changed, 64 + 6 * 56, segment_type)
            cases.append(bytes(changed))
        for data in cases:
            with self.subTest(segment_type=struct.unpack_from("<I", data, 64 + 6 * 56)[0]):
                with self.assertRaisesRegex(elf.ElfError, "unsupported_segment"):
                    elf.inspect(data, 0x0200_0000, elf.MIN_VIRTUAL_BASE)

    def test_readiness_records_complete_campaign(self) -> None:
        summary = self.readiness["summary"]
        self.assertEqual(12, summary["rust_host_tests_passed"])
        self.assertEqual(3, summary["clippy_runs_passed"])
        self.assertEqual(2, summary["no_std_target_builds_passed"])
        self.assertEqual(2, summary["pooleboot_integration_builds_passed"])
        self.assertEqual(3, summary["exact_loaded_byte_vectors_matched"])
        self.assertEqual(4096, summary["maximum_relocations_exercised"])
        self.assertEqual(129, summary["negative_controls_passed"])
        self.assertEqual(16_384, summary["differential_fuzz_cases"])
        self.assertEqual(0, summary["differential_mismatches"])

    def test_pooleboot_compile_time_dependency_is_explicit(self) -> None:
        manifest = (ROOT / "native/boot/Cargo.toml").read_text(encoding="utf-8")
        library = (ROOT / "native/boot/src/lib.rs").read_text(encoding="utf-8")
        self.assertIn('poole-elf = { path = "../elf" }', manifest)
        self.assertIn("pub use poole_elf as elf;", library)
        self.assertEqual(2, self.readiness["summary"]["pooleboot_integration_builds_passed"])
        self.assertFalse(self.readiness["claims"]["live_uefi_file_read"])

    def test_production_library_is_no_std_allocation_free_and_unsafe_free(self) -> None:
        source = (ROOT / "native/elf/src/lib.rs").read_text(encoding="utf-8")
        manifest = (ROOT / "native/elf/Cargo.toml").read_text(encoding="utf-8")
        self.assertIn("#![no_std]", source)
        self.assertNotIn("extern crate std", source.split("#[cfg(test)]", 1)[0])
        self.assertNotIn("Vec<", source.split("#[cfg(test)]", 1)[0])
        self.assertNotIn("unsafe", source.split("#[cfg(test)]", 1)[0])
        self.assertTrue(manifest.rstrip().endswith("[dependencies]"))

    def test_claim_boundary_remains_non_promoting(self) -> None:
        self.assertEqual(elf.expected_claims(), self.readiness["claims"])
        for key in (
            "live_uefi_file_read",
            "uefi_page_allocation",
            "page_table_mapping",
            "signed_manifest_verification",
            "exit_boot_services",
            "kernel_entry_transfer",
            "poolekernel_execution",
            "target_firmware_tested",
            "physical_media_written",
            "production_ready",
        ):
            self.assertFalse(self.readiness["claims"][key])
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n5_exit_gate_satisfied"])

    def test_readiness_stales_when_implementation_binding_changes(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertIn("readiness input bindings are stale", elf.readiness_errors(changed))

    def test_public_receipt_has_no_host_path_or_corpus(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertNotIn("C:\\Users", encoded)
        self.assertFalse(self.readiness["differential_fuzz"]["corpus_published"])
        self.assertFalse(self.readiness["parser_qualification"]["host_probe_artifact_identity_recorded"])


if __name__ == "__main__":
    unittest.main()
