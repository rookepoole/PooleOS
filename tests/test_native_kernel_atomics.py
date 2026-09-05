import copy
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from runtime import native_kernel_atomics as atomics  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeKernelAtomicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((ROOT / atomics.CONTRACT_RELATIVE).read_text(encoding="utf-8"))
        cls.readiness = json.loads((ROOT / atomics.READINESS_RELATIVE).read_text(encoding="utf-8"))

    def test_contract_is_canonical(self) -> None:
        self.assertEqual(atomics.contract_errors(self.contract, ROOT), [])

    def test_readiness_is_bound_to_every_input(self) -> None:
        self.assertEqual(atomics.readiness_errors(self.readiness, ROOT), [])

    def test_order_matrix_is_independently_reconstructed(self) -> None:
        self.assertEqual(self.contract["order_matrix"], atomics.order_matrix_oracle())
        self.assertEqual(self.contract["order_matrix"]["compare_exchange_pairs"], 9)
        self.assertEqual(self.contract["order_matrix"]["rejected_combinations"], 11)

    def test_typed_order_oracle_accepts_only_declared_requests(self) -> None:
        self.assertEqual(atomics.validate_order_request("load", "acquire")["success"], "acquire")
        self.assertEqual(
            atomics.validate_order_request("compare_exchange", "acq_rel", "acquire")["failure"],
            "acquire",
        )
        for operation, success, failure in (
            ("load", "release", None),
            ("store", "acquire", None),
            ("fence", "relaxed", None),
            ("compare_exchange", "release", "acquire"),
        ):
            with self.assertRaises(atomics.KernelAtomicsError):
                atomics.validate_order_request(operation, success, failure)

    def test_operation_oracle_matches_probe_receipt(self) -> None:
        self.assertEqual(
            atomics.operation_oracle(),
            {
                "exchange_old": 9,
                "compare_old": 11,
                "add_old": 13,
                "sub_old": 18,
                "or_old": 16,
                "xor_old": 48,
                "and_old": 32,
                "final": 0,
            },
        )

    def test_host_probe_receipts_remain_exact(self) -> None:
        parsed = atomics.parse_probe_output("\n".join(self.readiness["host_probe"]["lines"]) + "\n")
        self.assertEqual(parsed["receipt_count"], 8)
        self.assertEqual(parsed["contended_operation_count"], 20_480)
        self.assertEqual(parsed["forbidden_observations"], 0)

    def test_both_qemu_transcripts_validate(self) -> None:
        runs = self.readiness["execution"]["runs"]
        self.assertEqual(len(runs), 2)
        for run in runs:
            summary = atomics.validate_markers(run["markers"])
            self.assertEqual(summary["interrupt"]["timer_deliveries"], 8)
            self.assertEqual(summary["interrupt"]["atomic_updates"], 8)

    def test_qemu_evidence_is_repeatable_and_nonphysical(self) -> None:
        execution = self.readiness["execution"]
        self.assertTrue(execution["fresh_vars_each_run"])
        self.assertTrue(execution["exact_marker_match"])
        self.assertTrue(execution["exact_screenshot_match"])
        self.assertTrue(execution["exact_pbp1_match"])
        self.assertFalse(execution["physical_media_write_performed"])

    def test_linked_instruction_review_covers_all_symbols(self) -> None:
        audit = self.readiness["linked_instruction_audit"]
        self.assertEqual(audit["target"], "x86_64-unknown-none")
        self.assertEqual(audit["symbol_count"], 7)
        self.assertTrue(audit["all_instruction_rules_passed"])
        self.assertEqual(
            [item["symbol"] for item in audit["symbols"]],
            self.contract["assembly_contract"]["symbols"],
        )

    def test_all_hostile_controls_are_present_in_order(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual([item["id"] for item in controls], list(atomics.NEGATIVE_CONTROL_IDS))
        self.assertTrue(all(item["status"] == "pass" and item["case_count"] >= 1 for item in controls))

    def test_production_and_n12_claims_remain_false(self) -> None:
        claims = self.readiness["claims"]
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n12_exit_gate_satisfied"])
        self.assertFalse(claims["general_lock_family_implemented"])
        self.assertFalse(claims["deferred_reclamation_implemented"])
        self.assertFalse(claims["live_multi_ap_atomic_litmus_verified"])
        self.assertFalse(claims["production_ready"])

    def test_contract_rejects_order_drift(self) -> None:
        hostile = copy.deepcopy(self.contract)
        hostile["order_matrix"]["compare_exchange_pairs"] = 10
        self.assertIn("order matrix diverges from independent oracle", atomics.contract_errors(hostile, ROOT))

    def test_marker_validator_rejects_production_overclaim(self) -> None:
        hostile = self.readiness["execution"]["runs"][0]["markers"].copy()
        hostile[-1] = hostile[-1].replace("production=0", "production=1")
        with self.assertRaises(atomics.KernelAtomicsError):
            atomics.validate_markers(hostile)

    def test_input_binding_rejects_repository_escape(self) -> None:
        with self.assertRaises(atomics.KernelAtomicsError):
            atomics.file_binding(ROOT, "../escape")

    def test_release_gate_accepts_only_the_bounded_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_atomics_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("kernel_tests=214/214", check["detail"])
        self.assertIn("linked_symbols=7", check["detail"])
        self.assertIn("general_locks=false", check["detail"])
        self.assertIn("production_ready=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
