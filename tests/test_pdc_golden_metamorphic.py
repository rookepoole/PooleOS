import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_golden_metamorphic as golden  # noqa: E402
from runtime import pdc_reference  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PdcGoldenMetamorphicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus_path = ROOT / "runs" / "pdc_golden_metamorphic_corpus.json"
        cls.receipt_path = ROOT / "runs" / "pdc_golden_metamorphic_receipt.json"
        cls.corpus = json.loads(cls.corpus_path.read_text(encoding="utf-8"))
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding="utf-8"))
        cls.corpus_schema = json.loads(
            (ROOT / "specs" / "pdc-golden-metamorphic-corpus.schema.json").read_text(encoding="utf-8")
        )
        cls.receipt_schema = json.loads(
            (ROOT / "specs" / "pdc-golden-metamorphic-receipt.schema.json").read_text(encoding="utf-8")
        )

    def test_published_artifacts_match_strict_schemas(self) -> None:
        self.assertEqual(validate_json(self.corpus, self.corpus_schema), [])
        self.assertEqual(validate_json(self.receipt, self.receipt_schema), [])

    def test_all_state_support_threshold_pairs_are_published_once(self) -> None:
        pairs = [(record["state"], record["support"]) for record in self.corpus["threshold_records"]]
        self.assertEqual(pairs, [(state, support) for state in (0, 1) for support in range(27)])
        self.assertEqual(len(set(pairs)), 54)

    def test_threshold_measurements_match_the_frozen_formula(self) -> None:
        for record in self.corpus["threshold_records"]:
            expected = golden.independent_measurement(record["state"], record["support"])
            self.assertEqual(record["expected"]["measurement"], expected)
            accepted_supports = range(5, 10) if record["state"] else range(5, 8)
            self.assertEqual(expected["accepted"], record["support"] in accepted_supports)
            self.assertEqual(expected["next_state"], int(record["support"] in accepted_supports))

    def test_adversarial_cases_cover_empty_full_singleton_wrap_and_padding(self) -> None:
        focus = {record["boundary_focus"] for record in self.corpus["adversarial_records"]}
        self.assertEqual(
            focus,
            {
                "empty",
                "full",
                "singleton_wrap_corner",
                "wrap_face",
                "wrap_edge",
                "wrap_corner",
                "zero_bit_padding",
                "nonzero_bit_padding_width",
            },
        )
        self.assertEqual(sum(record["wraparound_probe"] is not None for record in self.corpus["adversarial_records"]), 4)
        self.assertTrue(any(record["expected"]["bitpacked_padding_bit_count"] == 0 for record in self.corpus["adversarial_records"]))
        self.assertTrue(any(record["expected"]["bitpacked_padding_bit_count"] > 0 for record in self.corpus["adversarial_records"]))

    def test_every_declared_metamorphic_relation_has_locked_cardinality(self) -> None:
        relations = self.corpus["metamorphic_records"]
        self.assertEqual(sum(record["relation"] == "periodic_translation_equivariance" for record in relations), 32)
        self.assertEqual(sum(record["relation"] == "axis_permutation_equivariance" for record in relations), 40)
        self.assertTrue(all(record["expected"]["support_equivariant"] for record in relations))
        self.assertTrue(all(record["expected"]["next_state_equivariant"] for record in relations))

    def test_translation_and_axis_transformations_round_trip(self) -> None:
        shape = (3, 4, 5)
        field = tuple(int((index * 7 + 3) % 11 in (0, 1, 4)) for index in range(60))
        shift = (2, 3, 4)
        translated = golden.translate_values(field, shape, shift)
        self.assertEqual(golden.translate_values(translated, shape, tuple(-value for value in shift)), field)

        order = (2, 0, 1)
        permuted, permuted_shape = golden.permute_axes(field, shape, order)
        inverse = tuple(order.index(axis) for axis in range(3))
        restored, restored_shape = golden.permute_axes(permuted, permuted_shape, inverse)
        self.assertEqual(restored_shape, shape)
        self.assertEqual(restored, field)

    def test_non_relations_keep_counterexamples_and_exclusions_distinct(self) -> None:
        records = {record["id"]: record for record in self.corpus["non_relations"]}
        self.assertEqual(sum(record["evidence_type"] == "finite_counterexample" for record in records.values()), 2)
        self.assertEqual(sum(record["evidence_type"] == "contract_exclusion" for record in records.values()), 4)
        self.assertGreater(records["complement-is-not-a-symmetry"]["witness"]["mismatch_count"], 0)
        self.assertEqual(records["pmphi-is-not-a-representation-transform"]["witness"]["removed_b7_events"], 16)
        self.assertTrue(all(record["expected_relation"] is False for record in records.values()))

    def test_receipt_builder_reproduces_all_summary_counts(self) -> None:
        rebuilt = golden.make_golden_metamorphic_receipt(
            workspace=ROOT,
            corpus_path=self.corpus_path,
            math_contract_path=ROOT / "runs" / "pdc_math_contract.json",
            predecessor_golden_path=ROOT / "runs" / "pdc_golden_vectors.json",
            representation_contract_path=ROOT / "runs" / "pdc_representation_contract.json",
            representation_receipt_path=ROOT / "runs" / "pdc_representation_receipt.json",
        )
        self.assertEqual(rebuilt["summary"], self.receipt["summary"])
        self.assertEqual(rebuilt["summary"]["oracle_field_evaluation_count"], 206)
        self.assertEqual(rebuilt["summary"]["representation_round_trip_count"], 824)
        self.assertEqual(rebuilt["summary"]["mismatch_count"], 0)

    def test_all_ten_negative_checks_fail_closed_with_expected_errors(self) -> None:
        checks = self.receipt["negative_checks"]
        self.assertEqual(len(checks), 10)
        self.assertTrue(all(check["passed"] for check in checks))
        self.assertNotIn("no_error", {check["error_type"] for check in checks})

    def test_corpus_builder_rejects_a_mismatching_representation_receipt(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "representation_receipt.json"
            tampered = json.loads((ROOT / "runs" / "pdc_representation_receipt.json").read_text(encoding="utf-8"))
            tampered["summary"]["mismatch_count"] = 1
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(golden.PdcGoldenMetamorphicError):
                golden.make_golden_metamorphic_corpus(
                    workspace=ROOT,
                    math_contract_path=ROOT / "runs" / "pdc_math_contract.json",
                    predecessor_golden_path=ROOT / "runs" / "pdc_golden_vectors.json",
                    representation_contract_path=ROOT / "runs" / "pdc_representation_contract.json",
                    representation_receipt_path=path,
                )

    def test_receipt_builder_rejects_record_tampering(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "corpus.json"
            tampered = json.loads(json.dumps(self.corpus))
            tampered["threshold_records"][0]["expected"]["measurement"]["strain"] = 0
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(golden.PdcGoldenMetamorphicError):
                golden.make_golden_metamorphic_receipt(
                    workspace=ROOT,
                    corpus_path=path,
                    math_contract_path=ROOT / "runs" / "pdc_math_contract.json",
                    predecessor_golden_path=ROOT / "runs" / "pdc_golden_vectors.json",
                    representation_contract_path=ROOT / "runs" / "pdc_representation_contract.json",
                    representation_receipt_path=ROOT / "runs" / "pdc_representation_receipt.json",
                )

    def test_release_checks_verify_bindings_and_detect_substitution(self) -> None:
        corpus_check = pooleos_release_gate.check_pdc_golden_metamorphic_corpus(
            self.corpus_path,
            ROOT / "runs" / "pdc_math_contract.json",
            ROOT / "runs" / "pdc_golden_vectors.json",
            ROOT / "runs" / "pdc_representation_contract.json",
            ROOT / "runs" / "pdc_representation_receipt.json",
        )
        receipt_check = pooleos_release_gate.check_pdc_golden_metamorphic_receipt(
            self.receipt_path,
            self.corpus_path,
            ROOT / "runs" / "pdc_math_contract.json",
            ROOT / "runs" / "pdc_golden_vectors.json",
            ROOT / "runs" / "pdc_representation_contract.json",
            ROOT / "runs" / "pdc_representation_receipt.json",
        )
        self.assertTrue(corpus_check["ok"], corpus_check["detail"])
        self.assertTrue(receipt_check["ok"], receipt_check["detail"])

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "corpus.json"
            tampered = json.loads(json.dumps(self.corpus))
            tampered["threshold_records"][0]["expected"]["field_sha256"] = "0" * 64
            path.write_text(json.dumps(tampered), encoding="utf-8")
            substituted = pooleos_release_gate.check_pdc_golden_metamorphic_corpus(
                path,
                ROOT / "runs" / "pdc_math_contract.json",
                ROOT / "runs" / "pdc_golden_vectors.json",
                ROOT / "runs" / "pdc_representation_contract.json",
                ROOT / "runs" / "pdc_representation_receipt.json",
            )
            self.assertFalse(substituted["ok"])


if __name__ == "__main__":
    unittest.main()
