import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_parser_kernel_promotion_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pooleglyph_parser_kernel_promotion_receipt  # noqa: E402


def _audit(*, ready: bool = False) -> dict:
    return {
        "artifact_kind": "pooleos.pooleglyph_core_ir_executable_audit",
        "status": "parser_to_kernel_ready" if ready else "audited_non_promoting",
        "source_boundary_receipt": {
            "artifact_path": "pooleglyph_core_ir_boundary_receipt.json",
        },
        "summary": {
            "failed_check_count": 0,
            "phase66_audit_present": ready,
            "parser_to_kernel_promotion_allowed": ready,
            "kernel_handoff_allowed": ready,
            "kernel_enforcement_claimed": False,
            "executable_candidate_count": 2,
            "metadata_zero_count": 1,
            "unexpected_invalid_count": 0,
        },
    }


class PooleGlyphParserKernelPromotionReceiptTests(unittest.TestCase):
    def test_receipt_blocks_without_phase66_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            audit_path.write_text(json.dumps(_audit()), encoding="utf-8")
            receipt = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
                core_ir_executable_audit_path=audit_path,
            )
            schema = json.loads(
                (ROOT / "specs" / "pooleglyph-parser-kernel-promotion-receipt.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_json(receipt, schema), [])
            self.assertEqual(receipt["status"], "blocked_until_phase66")
            self.assertFalse(receipt["summary"]["parser_to_kernel_promotion_allowed"])
            self.assertFalse(receipt["summary"]["kernel_handoff_allowed"])
            self.assertEqual(receipt["summary"]["failed_check_count"], 0)

    def test_receipt_allows_ready_phase66_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            audit_path.write_text(json.dumps(_audit(ready=True)), encoding="utf-8")
            receipt = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
                core_ir_executable_audit_path=audit_path,
            )
            self.assertEqual(receipt["status"], "parser_to_kernel_ready")
            self.assertTrue(receipt["summary"]["phase66_audit_present"])
            self.assertTrue(receipt["summary"]["parser_to_kernel_promotion_allowed"])
            self.assertTrue(receipt["summary"]["kernel_handoff_allowed"])

    def test_cli_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            out = Path(tmp) / "promotion_receipt.json"
            audit_path.write_text(json.dumps(_audit()), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = emit_pooleglyph_parser_kernel_promotion_receipt.main(
                    ["--core-ir-executable-audit", str(audit_path), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_kind"], "pooleos.pooleglyph_parser_kernel_promotion_receipt")

    def test_missing_audit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
                core_ir_executable_audit_path=Path(tmp) / "missing.json",
            )
            self.assertEqual(receipt["status"], "fail")
            self.assertGreater(receipt["summary"]["failed_check_count"], 0)


if __name__ == "__main__":
    unittest.main()
