import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pgb2_bundle, emit_replay_proof  # noqa: E402


class ReplayProofTests(unittest.TestCase):
    def test_emit_replay_proof_for_valid_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle.pgb2.json"
            proof_path = Path(tmp) / "proof.json"
            with redirect_stdout(io.StringIO()):
                bundle_code = emit_pgb2_bundle.main(["--case", "six-support", "--out", str(bundle)])
                proof_code = emit_replay_proof.main([
                    "--bundle",
                    str(bundle),
                    "--case",
                    "six-support",
                    "--out",
                    str(proof_path),
                ])
            self.assertEqual(bundle_code, 0)
            self.assertEqual(proof_code, 0)
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertTrue(proof["channel_summary_match"])
            self.assertTrue(proof["pgvm_report"]["halted"])
            self.assertEqual(proof["pgvm_report"]["final_body_count"], 7)
            schema = json.loads((ROOT / "specs" / "replay-proof.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(proof, schema), [])

    def test_replay_proof_detects_case_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle.pgb2.json"
            proof_path = Path(tmp) / "proof.json"
            with redirect_stdout(io.StringIO()):
                emit_pgb2_bundle.main(["--case", "six-support", "--out", str(bundle)])
                proof_code = emit_replay_proof.main([
                    "--bundle",
                    str(bundle),
                    "--case",
                    "single-body",
                    "--out",
                    str(proof_path),
                ])
            self.assertEqual(proof_code, 1)
            self.assertFalse(proof_path.exists())


if __name__ == "__main__":
    unittest.main()

