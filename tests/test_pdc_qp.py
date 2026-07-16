import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_qp as qp  # noqa: E402
from runtime import pdc_qp_evidence as evidence  # noqa: E402
from runtime import pdc_verifier_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PdcQpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = ROOT / "runs" / "pdc_qp_contract.json"
        cls.receipt_path = ROOT / "runs" / "pdc_qp_receipt.json"
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding="utf-8"))
        cls.contract_schema = json.loads(
            (ROOT / "specs" / "pdc-qp-contract.schema.json").read_text(encoding="utf-8")
        )
        cls.receipt_schema = json.loads(
            (ROOT / "specs" / "pdc-qp-receipt.schema.json").read_text(encoding="utf-8")
        )

    def test_published_artifacts_match_schemas(self) -> None:
        self.assertEqual(validate_json(self.contract, self.contract_schema), [])
        self.assertEqual(validate_json(self.receipt, self.receipt_schema), [])

    def test_contract_binds_implementation_sources_and_case_archive(self) -> None:
        bindings = self.contract["bindings"]
        for source in bindings["formula_sources"]:
            path = ROOT / source["stored_path"]
            self.assertEqual(pdc_verifier_intake.sha256_file(path), source["sha256"])
        implementation = ROOT / bindings["reference_implementation_path"]
        self.assertEqual(pdc_verifier_intake.sha256_file(implementation), bindings["reference_implementation_sha256"])
        archive = ROOT / bindings["typed_case_archive"]["stored_path"]
        self.assertEqual(pdc_verifier_intake.sha256_file(archive), bindings["typed_case_archive"]["sha256"])
        with ZipFile(archive) as source:
            for member in bindings["typed_case_members"]:
                payload = source.read(member["member_path"])
                self.assertEqual(pdc_verifier_intake.sha256_bytes(payload), member["sha256"])
                self.assertEqual(len(payload), member["size_bytes"])

    def test_all_feature_threshold_pairs_are_disjoint_and_collapse_exactly(self) -> None:
        seen = []
        for state in (0, 1):
            for support in range(27):
                measured = qp.feature(state, support)
                channels = measured.channel_map()
                typed_accept = sum(channels[name] for name in ("B5", "B6", "B7", "S5", "S6", "S7", "S8", "S9"))
                self.assertLessEqual(typed_accept, 1)
                self.assertEqual(typed_accept, measured.collapsed_next_state)
                self.assertEqual(measured.collapsed_next_state, int(5 <= support <= 7 + 2 * state))
                seen.append((state, support))
        self.assertEqual(len(seen), 54)

    def test_feature_and_collapsed_state_use_incompatible_type_tags(self) -> None:
        measured = qp.feature(0, 5).to_dict()
        self.assertEqual(measured["type_tag"], qp.FEATURE_TYPE_TAG)
        self.assertEqual(measured["collapsed"]["type_tag"], qp.COLLAPSED_TYPE_TAG)
        self.assertFalse(measured["collapsed"]["channel_identity_preserved"])
        self.assertNotEqual(measured["type_tag"], measured["collapsed"]["type_tag"])

    def test_dp_polynomial_and_bruteforce_agree(self) -> None:
        small = (0.05, 0.15, 0.35, 0.65, 0.85, 0.95)
        dp = qp.poisson_binomial_dp(small)
        polynomial = qp.poisson_binomial_polynomial(small)
        brute = qp.poisson_binomial_bruteforce(small)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(dp, polynomial, strict=True)), 5e-13)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(dp, brute, strict=True)), 5e-13)
        self.assertTrue(math.isclose(math.fsum(dp), 1.0, rel_tol=5e-13, abs_tol=5e-13))

    def test_full_probability_layer_preserves_hysteretic_memory_band(self) -> None:
        probabilities = tuple((index + 1) / 27 for index in range(26))
        result = qp.probability_layer(0.375, probabilities)
        c57 = math.fsum(result.coefficients[5:8])
        c89 = math.fsum(result.coefficients[8:10])
        self.assertTrue(math.isclose(result.activation_probability, c57 + 0.375 * c89, abs_tol=5e-13))
        self.assertTrue(math.isclose(result.center_derivative, c89, abs_tol=5e-13))
        channel_sum = math.fsum(
            result.expected_channels[name]
            for name in ("B5", "B6", "B7", "S5", "S6", "S7", "S8", "S9")
        )
        self.assertTrue(math.isclose(channel_sum, result.activation_probability, abs_tol=5e-13))

    def test_neighbor_derivatives_match_central_difference(self) -> None:
        probabilities = [0.2 + 0.6 * index / 25 for index in range(26)]
        center = 0.4
        result = qp.probability_layer(center, probabilities)
        step = 1e-6
        for index in (0, 7, 13, 25):
            low = list(probabilities)
            high = list(probabilities)
            low[index] -= step
            high[index] += step
            low_q = qp.activation_probability(qp.poisson_binomial_polynomial(low), center)
            high_q = qp.activation_probability(qp.poisson_binomial_polynomial(high), center)
            numerical = (high_q - low_q) / (2 * step)
            self.assertAlmostEqual(numerical, result.neighbor_derivatives[index], delta=2e-8)

    def test_deterministic_supports_keep_typed_probability_channels(self) -> None:
        seven = qp.probability_layer(0.0, (1.0,) * 7 + (0.0,) * 19)
        eight = qp.probability_layer(1.0, (1.0,) * 8 + (0.0,) * 18)
        nine = qp.probability_layer(1.0, (1.0,) * 9 + (0.0,) * 17)
        self.assertEqual(seven.expected_channels["B7"], 1.0)
        self.assertEqual(eight.expected_channels["S8"], 1.0)
        self.assertEqual(nine.expected_channels["S9"], 1.0)
        self.assertEqual((seven.activation_probability, eight.activation_probability, nine.activation_probability), (1.0, 1.0, 1.0))

    def test_raw_gate_and_one_input_truth_tables(self) -> None:
        for a in (0, 1):
            for b in (0, 1):
                self.assertEqual(qp.footprint_readout((a, b), 0).raw_birth, a & b)
                self.assertEqual(qp.footprint_readout((a, b), 1).raw_birth, a | b)
                self.assertEqual(qp.footprint_readout((a, b), 3).raw_birth, 1 - (a & b))
                self.assertEqual(qp.footprint_readout((a, b), 4).raw_birth, 1 - (a | b))
        for a in (0, 1):
            self.assertEqual(qp.footprint_readout((a,), 1).raw_birth, a)
            self.assertEqual(qp.footprint_readout((a,), 4).raw_birth, 1 - a)

    def test_half_and_full_adder_typed_readouts(self) -> None:
        for a in (0, 1):
            for b in (0, 1):
                result = qp.half_adder((a, b))
                self.assertEqual(result["sum"], (a + b) % 2)
                self.assertEqual(result["carry"], int(a + b >= 2))
        for a in (0, 1):
            for b in (0, 1):
                for carry_in in (0, 1):
                    result = qp.full_adder((a, b, carry_in))
                    total = a + b + carry_in
                    self.assertEqual(result["sum"], total % 2)
                    self.assertEqual(result["carry"], int(total >= 2))
                    self.assertTrue(result["readout_requires_channel_identity"])

    def test_cardinality_map_covers_all_ten_footprint_counts(self) -> None:
        channels = []
        for defects in range(10):
            result = qp.footprint_readout((), defects)
            channels.append((result.B5, result.B6, result.B7))
            self.assertEqual(result.active_neighbor_support, 9 - defects)
            self.assertEqual(result.raw_birth, int(2 <= defects <= 4))
        self.assertEqual(channels[2], (0, 0, 1))
        self.assertEqual(channels[3], (0, 1, 0))
        self.assertEqual(channels[4], (1, 0, 0))

    def test_empirical_residue_and_poole_coherence_agree(self) -> None:
        centers = (0, 1, 0, 1)
        neighborhoods = tuple(tuple(int((sample + index) % 5 == 0) for index in range(26)) for sample in range(4))
        statistics = qp.empirical_site_statistics(centers, neighborhoods)
        coherence = qp.poole_coherence([statistics["channel_residue"]])
        self.assertTrue(math.isclose(coherence, statistics["coherence_contribution"], abs_tol=1e-15))

    def test_robust_signature_decomposes_and_null_spectrum_rejects(self) -> None:
        observed = {channel: 0.03 * (index + 1) for index, channel in enumerate(qp.COMBINED_GEOMETRY_CHANNELS)}
        means = {channel: 0.0 for channel in qp.COMBINED_GEOMETRY_CHANNELS}
        stds = {channel: 0.01 for channel in qp.COMBINED_GEOMETRY_CHANNELS}
        signature = qp.geometry_signature(observed, means, stds)
        expected = math.sqrt(signature.birth_window**2 + signature.high_support**2 + signature.strain**2)
        self.assertTrue(math.isclose(signature.combined, expected, rel_tol=1e-14, abs_tol=1e-14))
        spectrum = qp.normalized_geometry_spectrum(signature)
        self.assertTrue(spectrum["non_null"])
        self.assertLessEqual(spectrum["share_sum"], 1.0)
        with self.assertRaises(qp.PdcQpNullSignalError):
            qp.normalized_geometry_spectrum(qp.GeometrySignature(0.0, 0.0, 0.0, 0.0))

    def test_receipt_has_zero_mismatch_and_exact_case_counts(self) -> None:
        summary = self.receipt["summary"]
        self.assertEqual(summary["feature_threshold_case_count"], 54)
        self.assertEqual(summary["imported_typed_case_count"], 42)
        self.assertEqual(summary["derivative_oracle_check_count"], 260)
        self.assertEqual(summary["finite_difference_check_count"], 104)
        self.assertEqual(summary["negative_check_count"], 16)
        self.assertEqual(summary["mismatch_count"], 0)

    def test_receipt_builder_reproduces_all_result_digests_and_summary(self) -> None:
        rebuilt = evidence.make_qp_receipt(
            workspace=ROOT,
            contract_path=self.contract_path,
            source_intake_path=ROOT / "runs" / "pdc_source_intake.json",
            verifier_intake_path=ROOT / "runs" / "pdc_verifier_intake.json",
            math_contract_path=ROOT / "runs" / "pdc_math_contract.json",
        )
        self.assertEqual(rebuilt["summary"], self.receipt["summary"])
        self.assertEqual(rebuilt["digests"], self.receipt["digests"])

    def test_receipt_builder_rejects_contract_binding_substitution(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "contract.json"
            tampered = json.loads(json.dumps(self.contract))
            tampered["bindings"]["math_contract_sha256"] = "0" * 64
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(evidence.PdcQpEvidenceError):
                evidence.make_qp_receipt(
                    workspace=ROOT,
                    contract_path=path,
                    source_intake_path=ROOT / "runs" / "pdc_source_intake.json",
                    verifier_intake_path=ROOT / "runs" / "pdc_verifier_intake.json",
                    math_contract_path=ROOT / "runs" / "pdc_math_contract.json",
                )

    def test_all_negative_checks_fail_closed_with_named_errors(self) -> None:
        checks = self.receipt["negative_checks"]
        self.assertEqual(len(checks), 16)
        self.assertTrue(all(check["passed"] for check in checks))
        self.assertNotIn("no_error", {check["error_type"] for check in checks})

    def test_release_checks_verify_bindings_and_detect_receipt_substitution(self) -> None:
        contract_check = pooleos_release_gate.check_pdc_qp_contract(
            self.contract_path,
            ROOT / "runs" / "pdc_source_intake.json",
            ROOT / "runs" / "pdc_verifier_intake.json",
            ROOT / "runs" / "pdc_math_contract.json",
        )
        receipt_check = pooleos_release_gate.check_pdc_qp_receipt(
            self.receipt_path,
            self.contract_path,
            ROOT / "runs" / "pdc_source_intake.json",
            ROOT / "runs" / "pdc_verifier_intake.json",
            ROOT / "runs" / "pdc_math_contract.json",
        )
        self.assertTrue(contract_check["ok"], contract_check["detail"])
        self.assertTrue(receipt_check["ok"], receipt_check["detail"])

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "receipt.json"
            tampered = json.loads(json.dumps(self.receipt))
            tampered["typed_cases"]["summary"]["passed_count"] = 41
            path.write_text(json.dumps(tampered), encoding="utf-8")
            substituted = pooleos_release_gate.check_pdc_qp_receipt(
                path,
                self.contract_path,
                ROOT / "runs" / "pdc_source_intake.json",
                ROOT / "runs" / "pdc_verifier_intake.json",
                ROOT / "runs" / "pdc_math_contract.json",
            )
            self.assertFalse(substituted["ok"])

    def test_probability_and_footprint_malformed_inputs_fail_closed(self) -> None:
        with self.assertRaises(qp.PdcQpProbabilityError):
            qp.probability_layer(0.5, (0.5,) * 25)
        with self.assertRaises(qp.PdcQpProbabilityError):
            qp.poisson_binomial_dp((float("nan"),))
        with self.assertRaises(qp.PdcQpFootprintError):
            qp.footprint_readout((0,) * 9, 1)
        with self.assertRaises(qp.PdcQpFootprintError):
            qp.full_adder((0, 1))


if __name__ == "__main__":
    unittest.main()
