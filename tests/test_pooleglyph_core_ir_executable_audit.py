import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_core_ir_executable_audit  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pooleglyph_core_ir_executable_audit  # noqa: E402


def _record(name: str, classification: str, *, ok: bool = True, programs: int = 0, instructions: int = 0) -> dict:
    return {
        "path": f"outputs_coreir/{name}.validate.json",
        "exists": True,
        "sha256": "a" * 64,
        "ok": ok,
        "classification": classification,
        "validator_version": "pg-coreir-validator-v0.1",
        "module": name,
        "program_count": programs,
        "instruction_count": instructions,
        "diagnostic_codes": ["PGCORE100"] if not ok else [],
        "public_safe_notes_present": True,
    }


class PooleGlyphCoreIrExecutableAuditTests(unittest.TestCase):
    def _write_receipt(self, path: Path) -> None:
        receipt = {
            "artifact_kind": "pooleos.pooleglyph_core_ir_boundary_receipt",
            "status": "phase66_pending",
            "kernel_enforcement_claimed": False,
            "summary": {
                "failed_check_count": 0,
                "failed_promotion_gate_count": 1,
                "phase66_audit_present": False,
                "parser_to_kernel_promotion_allowed": False,
                "kernel_enforcement_claimed": False,
                "validated_executable_candidate_count": 1,
                "validated_metadata_zero_program_count": 1,
                "unexpected_invalid_count": 0,
            },
            "core_ir_validation_summary": {
                "validation_file_count": 5,
                "valid_file_count": 2,
                "validator_versions": ["pg-coreir-validator-v0.1"],
                "total_program_count": 1,
                "total_instruction_count": 3,
                "public_safe_note_count": 5,
            },
            "validation_records": [
                _record("exec", "validated_executable_candidate", programs=1, instructions=3),
                _record("metadata", "validated_metadata_zero_program"),
                _record("invalid_k_high", "expected_negative_fixture", ok=False),
                _record("missing_halt", "expected_negative_fixture", ok=False),
                _record("unknown_instruction", "expected_negative_fixture", ok=False),
            ],
        }
        path.write_text(json.dumps(receipt), encoding="utf-8")

    def test_audit_validates_and_blocks_kernel_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            self._write_receipt(receipt_path)
            audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
                core_ir_boundary_receipt_path=receipt_path,
            )
            schema = json.loads((ROOT / "specs" / "pooleglyph-core-ir-executable-audit.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(audit, schema), [])
            self.assertEqual(audit["status"], "audited_non_promoting")
            self.assertEqual(audit["summary"]["executable_candidate_count"], 1)
            self.assertEqual(audit["summary"]["metadata_zero_count"], 1)
            self.assertFalse(audit["summary"]["parser_to_kernel_promotion_allowed"])
            self.assertFalse(audit["boundary_decisions"]["kernel_handoff_allowed"])

    def test_cli_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            out = Path(tmp) / "audit.json"
            self._write_receipt(receipt_path)
            with redirect_stdout(io.StringIO()):
                code = emit_pooleglyph_core_ir_executable_audit.main(
                    ["--core-ir-boundary-receipt", str(receipt_path), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            audit = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(audit["artifact_kind"], "pooleos.pooleglyph_core_ir_executable_audit")

    def test_missing_receipt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
                core_ir_boundary_receipt_path=Path(tmp) / "missing.json",
            )
            self.assertEqual(audit["status"], "fail")
            self.assertGreater(audit["summary"]["failed_check_count"], 0)


if __name__ == "__main__":
    unittest.main()
