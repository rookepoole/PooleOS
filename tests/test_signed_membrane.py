import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import signed_membrane as sm  # noqa: E402
from runtime.channel_trace import make_claim_record  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


class SignedMembraneTests(unittest.TestCase):
    def test_signed_projections(self) -> None:
        lattice = sm.mirrored_sheet_pair(size=3, gap=1)
        self.assertEqual(len(lattice.projection("plus")), 9)
        self.assertEqual(len(lattice.projection("minus")), 9)
        self.assertEqual(len(lattice.projection("abs")), 18)
        self.assertTrue(lattice.projection("interface"))

    def test_mirrored_pair_has_balanced_interface_quality(self) -> None:
        metrics = sm.measure_membrane(sm.mirrored_sheet_pair(size=3, gap=1))
        self.assertEqual(metrics.positive_count, metrics.negative_count)
        self.assertGreater(metrics.interface_support, 0)
        self.assertLess(metrics.signed_imbalance, 1e-9)
        self.assertGreater(metrics.membrane_quality, 0.0)

    def test_single_sign_sheet_has_zero_interface_quality(self) -> None:
        metrics = sm.measure_membrane(sm.single_sign_sheet(size=3))
        self.assertEqual(metrics.negative_count, 0)
        self.assertEqual(metrics.interface_support, 0)
        self.assertEqual(metrics.membrane_quality, 0.0)

    def test_signed_metrics_artifact_validates(self) -> None:
        claim = make_claim_record(
            claim_id="SIGNED-TEST-001",
            title="Signed metrics unit artifact",
            claim_lane="benchmark",
            evidence_kind="benchmark",
            rule="signed-membrane-smoke",
            model_tag="signed",
            source_descriptor="unit:signed",
            limitations="Unit-test benchmark descriptor only.",
        )
        artifact = sm.make_metrics_artifact(sm.measure_membrane(sm.mirrored_sheet_pair()), claim=claim)
        schema = __import__("json").loads((ROOT / "specs" / "signed-membrane.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(artifact, schema), [])


if __name__ == "__main__":
    unittest.main()

