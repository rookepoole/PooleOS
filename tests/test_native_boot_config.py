import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_config as pbc1  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeBootConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = pbc1.read_json(ROOT / pbc1.CONTRACT_RELATIVE)
        cls.golden = pbc1.read_json(ROOT / pbc1.GOLDEN_RELATIVE)
        cls.readiness = pbc1.read_json(ROOT / pbc1.READINESS_RELATIVE)

    def test_contract_golden_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, pbc1.CONTRACT_SCHEMA_RELATIVE),
            (self.golden, pbc1.GOLDEN_SCHEMA_RELATIVE),
            (self.readiness, pbc1.READINESS_SCHEMA_RELATIVE),
        )
        for value, relative in cases:
            with self.subTest(schema=str(relative)):
                self.assertEqual([], validate_json(value, pbc1.read_json(ROOT / relative)))

    def test_semantic_contracts_and_bindings_pass(self) -> None:
        self.assertEqual([], pbc1.contract_errors(self.contract))
        self.assertEqual([], pbc1.golden_errors(self.golden))
        self.assertEqual([], pbc1.readiness_errors(self.readiness))

    def test_generator_reproduces_contract_and_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            contract = Path(temporary) / "contract.json"
            vectors = Path(temporary) / "vectors.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/generate_native_boot_config_vectors.py"),
                    "--contract-out",
                    str(contract),
                    "--vectors-out",
                    str(vectors),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout)
            self.assertEqual((ROOT / pbc1.CONTRACT_RELATIVE).read_bytes(), contract.read_bytes())
            self.assertEqual((ROOT / pbc1.GOLDEN_RELATIVE).read_bytes(), vectors.read_bytes())

    def test_all_golden_vectors_have_exact_semantics(self) -> None:
        for item in self.golden["vectors"]:
            with self.subTest(vector=item["id"]):
                data = bytes.fromhex(item["hex"])
                self.assertEqual(item["byte_count"], len(data))
                self.assertEqual(item["sha256"], pbc1.sha256_bytes(data))
                self.assertEqual(item["summary"], pbc1.summarize(pbc1.parse(data)))

    def test_python_parser_rejects_key_and_path_ambiguity(self) -> None:
        minimal = pbc1.build_fixture("minimal_v1")
        cases = (
            minimal.replace(b"timeout_ms=0", b"entry_count=0"),
            minimal.replace(b"timeout_ms=0", b"delay_ms=0"),
            minimal.replace(b"MANIFEST_A.PBM", b"..\\MANIFEST_A.PBM"),
            minimal[:-1],
        )
        for data in cases:
            with self.subTest(result=pbc1.parse_result(data)):
                self.assertTrue(pbc1.parse_result(data).startswith("ERR:"))

    def test_readiness_records_complete_differential_campaign(self) -> None:
        summary = self.readiness["summary"]
        self.assertEqual(12, summary["rust_host_tests_passed"])
        self.assertEqual(2, summary["no_std_target_builds_passed"])
        self.assertEqual(3, summary["golden_vectors_matched"])
        self.assertEqual(64, summary["negative_controls_passed"])
        self.assertEqual(16_384, summary["differential_fuzz_cases"])
        self.assertEqual(0, summary["differential_mismatches"])

    def test_pooleboot_compile_time_dependency_is_explicit(self) -> None:
        manifest = (ROOT / "native/boot/Cargo.toml").read_text(encoding="utf-8")
        library = (ROOT / "native/boot/src/lib.rs").read_text(encoding="utf-8")
        self.assertIn('poole-boot-config = { path = "../bootcfg" }', manifest)
        self.assertIn("pub use poole_boot_config as boot_config;", library)
        self.assertTrue(self.readiness["claims"]["pooleboot_compile_time_dependency"])
        self.assertFalse(self.readiness["claims"]["live_config_parsed_by_pooleboot"])

    def test_claim_boundary_remains_non_promoting(self) -> None:
        self.assertEqual(pbc1.expected_claims(), self.readiness["claims"])
        for key in (
            "live_config_file_opened",
            "live_config_parsed_by_pooleboot",
            "boot_entry_selected",
            "artifact_loaded",
            "artifact_signature_verified",
            "target_firmware_tested",
            "n5_exit_gate_satisfied",
            "production_ready",
        ):
            self.assertFalse(self.readiness["claims"][key])
        self.assertFalse(self.readiness["production_ready"])

    def test_readiness_stales_when_implementation_binding_changes(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertIn("readiness input bindings are stale", pbc1.readiness_errors(changed))

    def test_release_gate_accepts_exact_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_boot_config_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("negative=64", check["detail"])
        self.assertIn("fuzz=16384", check["detail"])
        self.assertIn("production_ready=false", check["detail"])

    def test_public_receipt_exposes_no_host_path_or_fuzz_corpus(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertNotIn("C:\\Users", encoded)
        self.assertFalse(self.readiness["differential_fuzz"]["corpus_published"])
        self.assertFalse(self.readiness["parser_qualification"]["host_probe_artifact_identity_recorded"])


if __name__ == "__main__":
    unittest.main()
