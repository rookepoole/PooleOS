import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_core_ir_boundary_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


PUBLIC_NOTES = [
    "Public-safe Core IR structural validator.",
    "No private PooleMath optimization, scheduling, compression, hardware, transfer/hash, or commercial acceleration methods are encoded.",
]


class PooleGlyphCoreIrBoundaryReceiptTests(unittest.TestCase):
    def _write_json(self, path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")

    def _make_bridge(self, path: Path, pooleglyph: Path, *, phase: int = 65) -> None:
        self._write_json(
            path,
            {
                "artifact_kind": "pooleos.pooleglyph_bridge_manifest",
                "status": "warn",
                "source_anchor": {
                    "pooleglyph_path": str(pooleglyph),
                    "latest_phase": phase,
                    "failed_check_count": 0,
                },
                "language_surface": {
                    "stack": ["capability", "permission", "ruleset"],
                },
                "core_ir_boundary": {
                    "status": "phase66_audit_present" if phase >= 66 else "phase66_pending",
                    "receipt_artifact_kind": "pooleos.pooleglyph_core_ir_boundary_receipt",
                    "phase66_audit_present": phase >= 66,
                    "parser_to_kernel_promotion_allowed": False,
                    "boundary_rule": "metadata remains metadata-only until receipt promotion",
                },
                "summary": {
                    "failed_check_count": 0,
                    "bridge_map_count": 6,
                },
            },
        )

    def _make_pooleglyph(self, root: Path, *, unexpected_invalid: bool = False) -> Path:
        pooleglyph = root / "PooleGlyph"
        package_root = pooleglyph / "pooleglyph_v0_5_parser_ast_scaffold_package"
        validator = package_root / "src" / "pooleglyph_parser" / "core_ir_validator.py"
        verifier = package_root / "tools" / "verify_coreir_validator.py"
        validator.parent.mkdir(parents=True, exist_ok=True)
        verifier.parent.mkdir(parents=True, exist_ok=True)
        validator.write_text("# validator\n", encoding="utf-8")
        verifier.write_text("# verifier\n", encoding="utf-8")

        self._write_json(
            package_root / "outputs_rulesets" / "ruleset_life.coreir.validate.json",
            {
                "version": "pg-coreir-validator-v0.1",
                "ok": True,
                "module": "tests.ruleset",
                "program_count": 1,
                "instruction_count": 4,
                "diagnostics": [],
                "notes": PUBLIC_NOTES,
            },
        )
        self._write_json(
            package_root / "outputs_capabilities" / "capability_meta.coreir.validate.json",
            {
                "version": "pg-coreir-validator-v0.1",
                "ok": True,
                "module": "tests.capability",
                "program_count": 0,
                "instruction_count": 0,
                "diagnostics": [],
                "notes": PUBLIC_NOTES,
            },
        )
        for name, code in {
            "invalid_k_high.validate.json": "PGCORE100",
            "missing_halt.validate.json": "PGCORE110",
            "unknown_instruction.validate.json": "PGCORE900",
        }.items():
            self._write_json(
                package_root / "outputs_coreir" / name,
                {
                    "version": "pg-coreir-validator-v0.1",
                    "ok": False,
                    "module": "tests.bad",
                    "program_count": 1,
                    "instruction_count": 4,
                    "diagnostics": [{"code": code}],
                    "notes": PUBLIC_NOTES,
                },
            )

        if unexpected_invalid:
            self._write_json(
                package_root / "outputs_rulesets" / "bad.coreir.validate.json",
                {
                    "version": "pg-coreir-validator-v0.1",
                    "ok": False,
                    "module": "tests.bad",
                    "program_count": 1,
                    "instruction_count": 4,
                    "diagnostics": [{"code": "PGCORE999"}],
                    "notes": PUBLIC_NOTES,
                },
            )
        return pooleglyph

    def test_phase66_pending_receipt_validates_and_blocks_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pooleglyph = self._make_pooleglyph(tmp_path)
            bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
            self._make_bridge(bridge_path, pooleglyph, phase=65)

            receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
                bridge_manifest_path=bridge_path,
                pooleglyph_path=pooleglyph,
            )
            schema = json.loads((ROOT / "specs" / "pooleglyph-core-ir-boundary-receipt.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(receipt, schema), [])
            self.assertEqual(receipt["status"], "phase66_pending")
            self.assertFalse(receipt["parser_to_kernel_promotion_allowed"])
            self.assertEqual(receipt["summary"]["failed_check_count"], 0)
            self.assertEqual(receipt["summary"]["failed_promotion_gate_count"], 1)
            self.assertEqual(receipt["core_ir_validation_summary"]["validated_executable_candidate_count"], 1)
            self.assertEqual(receipt["core_ir_validation_summary"]["validated_metadata_zero_program_count"], 1)
            self.assertEqual(receipt["core_ir_validation_summary"]["expected_negative_fixture_count"], 3)

            receipt_path = tmp_path / "receipt.json"
            pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, receipt_path)
            check = pooleos_release_gate.check_pooleglyph_core_ir_boundary_receipt(receipt_path)
            self.assertEqual(check["name"], "pooleglyph_core_ir_boundary_receipt")
            self.assertTrue(check["ok"], check)

    def test_unexpected_invalid_core_ir_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pooleglyph = self._make_pooleglyph(tmp_path, unexpected_invalid=True)
            bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
            self._make_bridge(bridge_path, pooleglyph, phase=65)

            receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
                bridge_manifest_path=bridge_path,
                pooleglyph_path=pooleglyph,
            )
            self.assertEqual(receipt["status"], "fail")
            self.assertEqual(receipt["summary"]["failed_check_count"], 1)
            self.assertEqual(receipt["core_ir_validation_summary"]["unexpected_invalid_count"], 1)

    def test_phase66_receipt_can_promote_when_all_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pooleglyph = self._make_pooleglyph(tmp_path)
            bridge_path = tmp_path / "pooleglyph_bridge_manifest.json"
            self._make_bridge(bridge_path, pooleglyph, phase=66)

            receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
                bridge_manifest_path=bridge_path,
                pooleglyph_path=pooleglyph,
            )
            self.assertEqual(receipt["status"], "parser_to_kernel_ready")
            self.assertTrue(receipt["parser_to_kernel_promotion_allowed"])
            self.assertFalse(receipt["kernel_enforcement_claimed"])


if __name__ == "__main__":
    unittest.main()
