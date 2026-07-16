import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_verifier_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PdcRepresentationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.math_path = ROOT / "runs" / "pdc_math_contract.json"
        cls.golden_path = ROOT / "runs" / "pdc_golden_vectors.json"
        cls.verifier_path = ROOT / "runs" / "pdc_verifier_reproduction.json"
        cls.contract_path = ROOT / "runs" / "pdc_representation_contract.json"
        cls.receipt_path = ROOT / "runs" / "pdc_representation_receipt.json"
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding="utf-8"))

    def test_contract_and_receipt_are_schema_valid_and_parent_bound(self) -> None:
        for artifact, schema_name in (
            (self.contract, "pdc-representation-contract.schema.json"),
            (self.receipt, "pdc-representation-receipt.schema.json"),
        ):
            schema = json.loads((ROOT / "specs" / schema_name).read_text(encoding="utf-8"))
            self.assertEqual(validate_json(artifact, schema), [], schema_name)
        bindings = self.contract["bindings"]
        self.assertEqual(
            bindings["reference_implementation_sha256"],
            pdc_verifier_intake.sha256_file(ROOT / bindings["reference_implementation_path"]),
        )
        self.assertEqual(bindings["math_contract_sha256"], pdc_verifier_intake.sha256_file(self.math_path))
        self.assertEqual(bindings["golden_vectors_sha256"], pdc_verifier_intake.sha256_file(self.golden_path))
        self.assertEqual(bindings["verifier_reproduction_sha256"], pdc_verifier_intake.sha256_file(self.verifier_path))
        receipt_bindings = self.receipt["bindings"]
        self.assertEqual(
            receipt_bindings["reference_implementation_sha256"],
            pdc_verifier_intake.sha256_file(ROOT / receipt_bindings["reference_implementation_path"]),
        )
        self.assertEqual(
            receipt_bindings["representation_contract_sha256"],
            pdc_verifier_intake.sha256_file(self.contract_path),
        )
        self.assertEqual(receipt_bindings["math_contract_sha256"], pdc_verifier_intake.sha256_file(self.math_path))
        self.assertEqual(receipt_bindings["golden_vectors_sha256"], pdc_verifier_intake.sha256_file(self.golden_path))
        self.assertEqual(receipt_bindings["verifier_reproduction_sha256"], pdc_verifier_intake.sha256_file(self.verifier_path))

    def test_contract_freezes_all_representation_and_conversion_domains(self) -> None:
        self.assertEqual(
            {item["id"] for item in self.contract["representations"]},
            {"dense_binary", "sparse_binary", "bitpacked_binary", "probability_field", "native_buffer_snapshot"},
        )
        self.assertEqual(len({item["id"] for item in self.contract["conversion_paths"]}), 10)
        self.assertEqual(self.contract["coordinate_contract"]["axis_order"], "x_fastest_then_y_then_z")
        self.assertEqual(self.contract["coordinate_contract"]["boundary"], "periodic")
        self.assertEqual(self.contract["native_buffer_contract"]["mutable_output"], "unsupported_in_rep_0_1")
        self.assertFalse(self.contract["canonical_hash_contract"]["native_padding_bytes_hashed"])
        self.assertEqual(len(self.contract["failure_modes"]), 16)

    def test_receipt_accounts_for_every_applicable_and_formula_only_case(self) -> None:
        summary = self.receipt["summary"]
        self.assertEqual(summary["golden_declared_case_count"], 13)
        self.assertEqual(summary["golden_applicable_case_count"], 10)
        self.assertEqual(summary["golden_excluded_formula_case_count"], 3)
        self.assertEqual(summary["exact_declared_case_count"], 4324)
        self.assertEqual(summary["exact_applicable_case_count"], 3099)
        self.assertEqual(summary["exact_excluded_formula_case_count"], 1225)
        self.assertEqual(summary["differential_case_count"], 3109)
        self.assertEqual(summary["round_trip_count"], 12436)
        self.assertEqual(summary["pdc_result_match_count"], 3109)
        self.assertEqual(summary["mismatch_count"], 0)

        expected = {
            "rectangle": (841, 841, 0, "pass"),
            "line_hole": (80, 80, 0, "pass"),
            "arbitrary_mask": (720, 720, 0, "pass"),
            "inversion": (1225, 0, 1225, "excluded_non_field_formula_family"),
            "solid_cuboid": (729, 729, 0, "pass"),
            "surface_shell": (729, 729, 0, "pass"),
        }
        actual = {item["id"]: item for item in self.receipt["exact_family_results"]}
        self.assertEqual(set(actual), set(expected))
        for family, values in expected.items():
            declared, tested, excluded, status = values
            self.assertEqual(actual[family]["declared_case_count"], declared)
            self.assertEqual(actual[family]["tested_case_count"], tested)
            self.assertEqual(actual[family]["excluded_case_count"], excluded)
            self.assertEqual(actual[family]["round_trip_count"], tested * 4)
            self.assertEqual(actual[family]["source_result_match_count"], declared)
            self.assertEqual(actual[family]["mismatch_count"], 0)
            self.assertEqual(actual[family]["status"], status)

    def test_negative_checks_and_probability_native_probe_pass(self) -> None:
        negative = self.receipt["negative_checks"]
        self.assertEqual(len(negative), 13)
        self.assertEqual(len({item["id"] for item in negative}), 13)
        self.assertTrue(all(item["passed"] for item in negative))
        self.assertTrue(all(item["error_type"] != "none" for item in negative))
        self.assertEqual(self.receipt["summary"]["failed_negative_check_count"], 0)
        self.assertEqual(self.receipt["probability_native_probe"]["status"], "pass")
        self.assertTrue(self.receipt["probability_native_probe"]["round_trip_match"])
        self.assertTrue(self.receipt["probability_native_probe"]["semantic_hash_match"])

    def test_formula_exclusions_are_explicit_and_do_not_hide_mismatches(self) -> None:
        exclusions = " ".join(self.receipt["exclusions"])
        self.assertIn("Three golden formula-only cases", exclusions)
        self.assertIn("1,225 inversion rows", exclusions)
        inversion = next(item for item in self.receipt["exact_family_results"] if item["id"] == "inversion")
        self.assertEqual(inversion["source_result_match_count"], inversion["declared_case_count"])
        self.assertEqual(inversion["mismatch_count"], 0)
        self.assertRegex(inversion["cases_digest_sha256"], r"^[0-9A-F]{64}$")

    def test_release_gate_accepts_the_representation_chain(self) -> None:
        contract = pooleos_release_gate.check_pdc_representation_contract(
            self.contract_path,
            self.math_path,
            self.golden_path,
            self.verifier_path,
        )
        receipt = pooleos_release_gate.check_pdc_representation_receipt(
            self.receipt_path,
            self.contract_path,
            self.math_path,
            self.golden_path,
            self.verifier_path,
        )
        self.assertTrue(contract["ok"], contract)
        self.assertTrue(receipt["ok"], receipt)

    def test_release_gate_rejects_substituted_contract_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_contract = copy.deepcopy(self.contract)
            bad_contract["bindings"]["math_contract_sha256"] = "0" * 64
            bad_contract_path = root / "bad-contract.json"
            bad_contract_path.write_text(json.dumps(bad_contract), encoding="utf-8")
            self.assertFalse(
                pooleos_release_gate.check_pdc_representation_contract(
                    bad_contract_path,
                    self.math_path,
                    self.golden_path,
                    self.verifier_path,
                )["ok"]
            )

            bad_receipt = copy.deepcopy(self.receipt)
            bad_receipt["summary"]["mismatch_count"] = 1
            bad_receipt_path = root / "bad-receipt.json"
            bad_receipt_path.write_text(json.dumps(bad_receipt), encoding="utf-8")
            self.assertFalse(
                pooleos_release_gate.check_pdc_representation_receipt(
                    bad_receipt_path,
                    self.contract_path,
                    self.math_path,
                    self.golden_path,
                    self.verifier_path,
                )["ok"]
            )


if __name__ == "__main__":
    unittest.main()
