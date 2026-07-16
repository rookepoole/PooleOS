import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_qp_stability as stability  # noqa: E402
from runtime import pdc_qp_stability_evidence as evidence  # noqa: E402
from runtime import pdc_verifier_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PdcQpStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = ROOT / "runs" / "pdc_qp_stability_contract.json"
        cls.receipt_path = ROOT / "runs" / "pdc_qp_stability_receipt.json"
        cls.qp_contract_path = ROOT / "runs" / "pdc_qp_contract.json"
        cls.qp_receipt_path = ROOT / "runs" / "pdc_qp_receipt.json"
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding="utf-8"))
        cls.contract_schema = json.loads(
            (ROOT / "specs" / "pdc-qp-stability-contract.schema.json").read_text(encoding="utf-8")
        )
        cls.receipt_schema = json.loads(
            (ROOT / "specs" / "pdc-qp-stability-receipt.schema.json").read_text(encoding="utf-8")
        )

    def test_generated_artifacts_match_schemas(self) -> None:
        self.assertEqual(validate_json(self.contract, self.contract_schema), [])
        self.assertEqual(validate_json(self.receipt, self.receipt_schema), [])

    def test_contract_binds_implementations_and_parent_qp_evidence(self) -> None:
        bindings = self.contract["bindings"]
        for path_field, hash_field in (
            ("reference_implementation_path", "reference_implementation_sha256"),
            ("qp_contract_path", "qp_contract_sha256"),
            ("qp_receipt_path", "qp_receipt_sha256"),
        ):
            self.assertEqual(pdc_verifier_intake.sha256_file(ROOT / bindings[path_field]), bindings[hash_field])
        self.assertEqual(len(bindings["source_packages"]), 2)
        self.assertEqual(sum(len(package["members"]) for package in bindings["source_packages"]), 13)

    def test_receipt_binds_contract_and_both_source_packages(self) -> None:
        bindings = self.receipt["bindings"]
        self.assertEqual(pdc_verifier_intake.sha256_file(self.contract_path), bindings["contract_sha256"])
        self.assertEqual(pdc_verifier_intake.sha256_file(ROOT / bindings["runner_package_path"]), bindings["runner_package_sha256"])
        self.assertEqual(pdc_verifier_intake.sha256_file(ROOT / bindings["result_package_path"]), bindings["result_package_sha256"])

    def test_fresh_fields_reproduce_every_published_channel_and_score(self) -> None:
        reproduction = self.receipt["benchmark_reproduction"]
        self.assertEqual(reproduction["field_count"], 550)
        self.assertEqual(reproduction["published_channel_rate_check_count"], 7150)
        self.assertEqual(reproduction["channel_rate_oracle_check_count"], 7150)
        self.assertEqual(reproduction["score_check_count"], 4400)
        self.assertEqual(reproduction["summary_check_count"], 517)
        self.assertEqual(reproduction["max_published_rate_abs_error"], 0.0)
        self.assertLessEqual(reproduction["max_score_abs_error"], evidence.SCORE_ABS_TOLERANCE)
        self.assertEqual(reproduction["mismatch_count"], 0)
        self.assertTrue(reproduction["verification"]["overall_pass"])

    def test_every_field_has_exact_density_and_independent_oracle_match(self) -> None:
        records = self.receipt["benchmark_reproduction"]["field_records"]
        self.assertEqual(len(records), 550)
        self.assertTrue(all(record["active_count"] == 1317 for record in records))
        self.assertTrue(all(record["active_count_pass"] for record in records))
        self.assertTrue(all(record["neighbor_oracle_match"] for record in records))
        self.assertEqual(self.receipt["benchmark_reproduction"]["neighbor_mismatch_voxel_count"], 0)

    def test_periodic_oracles_agree_on_adversarial_field(self) -> None:
        field = np.zeros((4, 4, 4), dtype=np.uint8)
        field[0, 0, 0] = 1
        field[3, 3, 3] = 1
        field[0, 3, 1] = 1
        self.assertTrue(np.array_equal(stability.neighbor_count_roll(field), stability.neighbor_count_indexed(field)))
        self.assertEqual(stability.channel_rates_roll(field), stability.channel_rates_indexed(field))

    def test_density_swap_is_deterministic_and_exact(self) -> None:
        field = np.zeros((4, 4, 4), dtype=np.uint8)
        field.ravel()[:16] = 1
        first = stability.deterministic_density_swap(
            field, class_name="straight_lines", sample_index=3, swaps=4
        )
        second = stability.deterministic_density_swap(
            field, class_name="straight_lines", sample_index=3, swaps=4
        )
        self.assertTrue(np.array_equal(first, second))
        self.assertEqual(int(first.sum()), int(field.sum()))
        self.assertEqual(int(np.count_nonzero(first != field)), 8)

    def test_all_perturbations_pass_density_oracle_and_classification_gates(self) -> None:
        result = self.receipt["controlled_perturbations"]
        summary = result["summary"]
        self.assertEqual(summary["case_count"], 2200)
        self.assertEqual(summary["structured_case_count"], 1000)
        self.assertEqual(summary["control_case_count"], 1200)
        self.assertEqual(summary["passed_count"], 2200)
        self.assertEqual(summary["mismatch_count"], 0)
        self.assertTrue(all(record["passed"] for record in result["records"]))

    def test_structured_and_control_null_boundaries_never_cross(self) -> None:
        records = self.receipt["controlled_perturbations"]["records"]
        for record in records:
            if record["scope"] == "structured":
                self.assertGreaterEqual(record["base_R_combined"], stability.NULL_LIKE_THRESHOLD)
                self.assertGreaterEqual(record["perturbed_R_combined"], stability.NULL_LIKE_THRESHOLD)
                self.assertIsNotNone(record["spectrum_l1_drift"])
            else:
                self.assertLess(record["base_R_combined"], stability.NULL_LIKE_THRESHOLD)
                self.assertLess(record["perturbed_R_combined"], stability.NULL_LIKE_THRESHOLD)
                self.assertIsNone(record["spectrum_l1_drift"])

    def test_level_summaries_cover_every_scope_and_swap_level(self) -> None:
        summaries = self.receipt["controlled_perturbations"]["level_summaries"]
        keys = {(record["scope"], record["swaps"]) for record in summaries}
        self.assertEqual(keys, {(scope, swaps) for scope in ("structured", "control") for swaps in (1, 4, 16, 64)})
        self.assertTrue(all(record["mismatch_count"] == 0 for record in summaries))
        self.assertTrue(all(record["passed_count"] == record["case_count"] for record in summaries))

    def test_dominant_label_changes_are_diagnostic_not_hidden(self) -> None:
        structured = [
            record
            for record in self.receipt["controlled_perturbations"]["records"]
            if record["scope"] == "structured"
        ]
        self.assertTrue(any(record["dominant_label_retained"] is False for record in structured))
        self.assertTrue(all(record["spectrum_bound_pass"] for record in structured))
        self.assertTrue(self.contract["perturbation_protocol"]["dominant_label_retention_is_diagnostic_not_gate"])

    def test_record_digests_recompute(self) -> None:
        reproduction = self.receipt["benchmark_reproduction"]
        perturbations = self.receipt["controlled_perturbations"]
        self.assertEqual(pdc_verifier_intake.sha256_json(reproduction["field_records"]), reproduction["field_record_set_sha256"])
        self.assertEqual(pdc_verifier_intake.sha256_json(perturbations["records"]), perturbations["record_set_sha256"])
        self.assertEqual(pdc_verifier_intake.sha256_json(perturbations["level_summaries"]), perturbations["summary_sha256"])

    def test_negative_checks_all_fail_closed(self) -> None:
        checks = self.receipt["negative_checks"]
        self.assertEqual(len(checks), 14)
        self.assertTrue(all(check["passed"] for check in checks))
        self.assertEqual(self.receipt["summary"]["failed_negative_check_count"], 0)

    def test_contract_protocol_substitution_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.contract)
        tampered["perturbation_protocol"]["swap_levels"] = [1, 4, 16, 63]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(evidence.PdcQpStabilityEvidenceError, "content substitution"):
                evidence.make_stability_receipt(
                    workspace=ROOT,
                    contract_path=path,
                    qp_contract_path=self.qp_contract_path,
                    qp_receipt_path=self.qp_receipt_path,
                )

    def test_result_package_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.zip"
            path.write_bytes((ROOT / evidence.RESULT_PACKAGE_RELATIVE_PATH).read_bytes() + b"substitution")
            with self.assertRaisesRegex(evidence.PdcQpStabilityEvidenceError, "package substitution"):
                evidence.make_stability_contract(
                    workspace=ROOT,
                    qp_contract_path=self.qp_contract_path,
                    qp_receipt_path=self.qp_receipt_path,
                    result_package_path=path,
                )

    def test_reference_runtime_rejects_malformed_inputs(self) -> None:
        with self.assertRaises(stability.PdcQpStabilityError):
            stability.neighbor_count_roll(np.zeros((2, 2, 2), dtype=np.uint8))
        with self.assertRaises(stability.PdcQpStabilityError):
            stability.generate_benchmark_fields(probability=float("nan"))
        with self.assertRaises(stability.PdcQpStabilityError):
            stability.stability_tolerances(hamming_fraction=0.0, control=False)

    def test_fresh_contract_is_canonically_equivalent(self) -> None:
        fresh = evidence.make_stability_contract(
            workspace=ROOT,
            qp_contract_path=self.qp_contract_path,
            qp_receipt_path=self.qp_receipt_path,
        )
        fresh["created_utc"] = self.contract["created_utc"]
        self.assertEqual(fresh, self.contract)

    def test_fresh_receipt_replays_all_evidence(self) -> None:
        fresh = evidence.make_stability_receipt(
            workspace=ROOT,
            contract_path=self.contract_path,
            qp_contract_path=self.qp_contract_path,
            qp_receipt_path=self.qp_receipt_path,
        )
        for field in ("created_utc", "environment"):
            fresh[field] = self.receipt[field]
        self.assertEqual(fresh, self.receipt)

    def test_release_gate_accepts_complete_stability_chain(self) -> None:
        contract_check = pooleos_release_gate.check_pdc_qp_stability_contract(
            self.contract_path, self.qp_contract_path, self.qp_receipt_path
        )
        receipt_check = pooleos_release_gate.check_pdc_qp_stability_receipt(
            self.receipt_path, self.contract_path, self.qp_contract_path, self.qp_receipt_path
        )
        self.assertTrue(contract_check["ok"], contract_check["detail"])
        self.assertTrue(receipt_check["ok"], receipt_check["detail"])

    def test_release_gate_rejects_perturbation_record_substitution(self) -> None:
        tampered = copy.deepcopy(self.receipt)
        tampered["controlled_perturbations"]["records"][0]["passed"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
            check = pooleos_release_gate.check_pdc_qp_stability_receipt(
                path, self.contract_path, self.qp_contract_path, self.qp_receipt_path
            )
            self.assertFalse(check["ok"])


if __name__ == "__main__":
    unittest.main()
