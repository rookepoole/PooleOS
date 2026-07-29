import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_handoff as pbp1  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeBootHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = pbp1.read_json(ROOT / pbp1.CONTRACT_RELATIVE)
        cls.golden = pbp1.read_json(ROOT / pbp1.GOLDEN_RELATIVE)
        cls.readiness = pbp1.read_json(ROOT / pbp1.READINESS_RELATIVE)

    def test_contract_golden_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, pbp1.CONTRACT_SCHEMA_RELATIVE),
            (self.golden, pbp1.GOLDEN_SCHEMA_RELATIVE),
            (self.readiness, pbp1.READINESS_SCHEMA_RELATIVE),
        )
        for value, relative in cases:
            with self.subTest(schema=str(relative)):
                self.assertEqual([], validate_json(value, pbp1.read_json(ROOT / relative)))

    def test_semantic_contracts_and_bindings_pass(self) -> None:
        self.assertEqual([], pbp1.contract_errors(self.contract))
        self.assertEqual([], pbp1.golden_errors(self.golden))
        self.assertEqual([], pbp1.readiness_errors(self.readiness))

    def test_golden_generator_reproduces_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "golden.json"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools/generate_native_boot_handoff_vectors.py"), "--out", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout)
            self.assertEqual((ROOT / pbp1.GOLDEN_RELATIVE).read_bytes(), output.read_bytes())

    def test_all_golden_vectors_decode_and_match_profile_expectation(self) -> None:
        for item in self.golden["vectors"]:
            with self.subTest(vector=item["id"]):
                data = bytes.fromhex(item["hex"])
                handoff = pbp1.decode(data)
                self.assertEqual(item["byte_count"], len(data))
                self.assertEqual(item["sha256"], pbp1.sha256_bytes(data))
                if item["kernel_entry_profile"]:
                    pbp1.validate_kernel_entry_profile(handoff)
                else:
                    with self.assertRaises(pbp1.BootHandoffError):
                        pbp1.validate_kernel_entry_profile(handoff)

    def test_minor_compatibility_is_fail_closed_and_forward_optional(self) -> None:
        forward = pbp1.decode(pbp1.build_fixture("forward_optional_v1_1"))
        self.assertEqual(1, forward.writer_minor)
        self.assertEqual(0, forward.minimum_reader_minor)
        changed = bytearray(pbp1.build_fixture("minimal_v1"))
        changed[10:14] = b"\x01\x00\x01\x00"
        changed[48:52] = b"\0" * 4
        changed[48:52] = pbp1._message_crc(bytes(changed)).to_bytes(4, "little")
        with self.assertRaises(pbp1.BootHandoffError):
            pbp1.decode(bytes(changed))

    def test_readiness_records_complete_differential_campaign(self) -> None:
        summary = self.readiness["summary"]
        self.assertEqual(8, summary["rust_host_tests_passed"])
        self.assertEqual(2, summary["no_std_target_builds_passed"])
        self.assertEqual(3, summary["golden_vectors_matched"])
        self.assertEqual(32, summary["negative_controls_passed"])
        self.assertEqual(16_384, summary["differential_fuzz_cases"])
        self.assertEqual(0, summary["differential_mismatches"])

    def test_claim_boundary_remains_non_promoting(self) -> None:
        self.assertEqual(pbp1.expected_claims(), self.readiness["claims"])
        for key in (
            "pooleboot_populates_handoff",
            "exit_boot_services_executed",
            "poolekernel_consumes_handoff",
            "poolekernel_executed",
            "target_firmware_tested",
            "n5_exit_gate_satisfied",
            "production_ready",
        ):
            self.assertFalse(self.readiness["claims"][key])
        self.assertFalse(self.readiness["production_ready"])

    def test_readiness_stales_when_an_implementation_binding_changes(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertIn("readiness input bindings are stale", pbp1.readiness_errors(changed))

    def test_release_gate_accepts_exact_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_boot_handoff_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("fuzz=16384", check["detail"])
        self.assertIn("production_ready=false", check["detail"])

    def test_public_artifacts_do_not_expose_operational_seed_or_host_path(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertNotIn("C:\\Users", encoded)
        self.assertNotIn("seed_bytes", encoded)
        self.assertFalse(self.readiness["differential_fuzz"]["corpus_published"])


if __name__ == "__main__":
    unittest.main()
