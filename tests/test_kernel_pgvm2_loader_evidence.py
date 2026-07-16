import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kernel_pgvm2_loader_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_kernel_pgvm2_loader_evidence, pooleos_release_gate  # noqa: E402


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _handoff(tmp_path: Path, *, ready: bool) -> Path:
    return _write_json(
        tmp_path / "kernel_boot_handoff.json",
        {
            "artifact_kind": "pooleos.kernel_boot_handoff",
            "status": "ready_for_kernel_handoff" if ready else "blocked",
            "kernel_handoff_allowed": ready,
            "kernel_boundary_claimed": False,
            "pgvm2_execution_claimed": False,
            "guest_loader_outputs": [
                {
                    "expected_executed_instruction_count": 29,
                    "actual_executed_instruction_count": 29 if ready else 0,
                }
            ],
            "summary": {
                "failed_check_count": 0,
                "unmet_requirement_count": 0 if ready else 4,
            },
        },
    )


def _source_anchor(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "pooleglyph_source_anchor.json",
        {
            "artifact_kind": "pooleos.pooleglyph_source_anchor",
            "status": "warn",
            "summary": {
                "dirty_file_count": 1,
                "failed_check_count": 0,
            },
        },
    )


def _loader_output(
    tmp_path: Path,
    *,
    handoff_path: Path,
    source_anchor_path: Path,
    promotion_receipt_path: Path,
    valid: bool = True,
    booted_kernel_path: bool = True,
    hash_matches: bool = True,
    source_hash_matches: bool = True,
    promotion_hash_matches: bool = True,
) -> Path:
    names = [check["name"] for check in kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS]
    return _write_json(
        tmp_path / "kernel_pgvm2_loader_output.json",
        {
            "artifact_kind": "pooleos.kernel_pgvm2_loader_output",
            "status": "pass" if valid else "blocked",
            "booted_kernel_path": booted_kernel_path,
            "kernel_enforcement_claimed": True,
            "pgvm2_execution_claimed": True,
            "source_handoff_sha256": _sha256(handoff_path) if hash_matches else "wrong",
            "pooleglyph_source_anchor_sha256": _sha256(source_anchor_path) if source_hash_matches else "wrong",
            "pooleglyph_parser_kernel_promotion_receipt_sha256": (
                _sha256(promotion_receipt_path) if promotion_hash_matches else "wrong"
            ),
            "kernel_build_id": "test-kernel",
            "kernel_checks": [
                {"name": name, "ok": valid, "detail": "synthetic booted kernel check"}
                for name in names
            ],
            "summary": {
                "failed_check_count": 0 if valid else 1,
                "kernel_check_count": len(names),
                "satisfied_kernel_check_count": len(names) if valid else 0,
                "expected_executed_instruction_count": 29,
                "actual_executed_instruction_count": 29,
            },
        },
    )


def _promotion_receipt(tmp_path: Path, *, ready: bool) -> Path:
    return _write_json(
        tmp_path / ("parser_kernel_promotion_ready.json" if ready else "parser_kernel_promotion_blocked.json"),
        {
            "artifact_kind": "pooleos.pooleglyph_parser_kernel_promotion_receipt",
            "status": "parser_to_kernel_ready" if ready else "blocked_until_phase66",
            "summary": {
                "failed_check_count": 0,
                "phase66_audit_present": ready,
                "parser_to_kernel_promotion_allowed": ready,
                "kernel_handoff_allowed": ready,
                "kernel_enforcement_claimed": False,
            },
        },
    )


class KernelPgvm2LoaderEvidenceTests(unittest.TestCase):
    def test_loader_evidence_blocks_when_handoff_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=_handoff(tmp_path, ready=False),
                kernel_loader_output_path=tmp_path / "missing_loader_output.json",
                pooleglyph_source_anchor_path=_source_anchor(tmp_path),
                parser_kernel_promotion_receipt_path=_promotion_receipt(tmp_path, ready=False),
            )
            schema = json.loads(
                (ROOT / "specs" / "kernel-pgvm2-loader-evidence.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_json(evidence, schema), [])
            self.assertEqual(evidence["status"], "blocked")
            self.assertFalse(evidence["kernel_loader_ready"])
            self.assertFalse(evidence["kernel_enforcement_claimed"])
            self.assertFalse(evidence["pgvm2_execution_claimed"])
            self.assertGreater(evidence["summary"]["unmet_requirement_count"], 0)

    def test_loader_evidence_ready_when_handoff_ready_but_kernel_output_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=_handoff(tmp_path, ready=True),
                kernel_loader_output_path=tmp_path / "missing_loader_output.json",
                pooleglyph_source_anchor_path=_source_anchor(tmp_path),
                parser_kernel_promotion_receipt_path=_promotion_receipt(tmp_path, ready=False),
            )
            self.assertEqual(evidence["status"], "ready_for_kernel_loader")
            self.assertTrue(evidence["kernel_loader_ready"])
            self.assertFalse(evidence["kernel_enforcement_claimed"])
            self.assertEqual(evidence["summary"]["failed_check_count"], 0)
            self.assertEqual(evidence["summary"]["planned_kernel_check_count"], len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS))
            self.assertEqual(evidence["parser_promotion_summary"]["status"], "blocked_until_phase66")
            self.assertFalse(evidence["parser_promotion_summary"]["parser_promotion_ready_for_enforcement"])

    def test_loader_evidence_claims_enforcement_only_with_valid_booted_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff_path = _handoff(tmp_path, ready=True)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=True)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=handoff_path,
                kernel_loader_output_path=_loader_output(
                    tmp_path,
                    handoff_path=handoff_path,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(evidence["status"], "kernel_enforced")
            self.assertTrue(evidence["kernel_enforcement_claimed"])
            self.assertTrue(evidence["pgvm2_execution_claimed"])
            self.assertEqual(evidence["summary"]["unmet_requirement_count"], 0)
            self.assertTrue(evidence["summary"]["output_handoff_hash_matches"])
            self.assertTrue(evidence["summary"]["all_kernel_checks_satisfied"])

    def test_loader_evidence_invalid_when_output_claims_without_booted_kernel_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff_path = _handoff(tmp_path, ready=True)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=True)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=handoff_path,
                kernel_loader_output_path=_loader_output(
                    tmp_path,
                    handoff_path=handoff_path,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                    booted_kernel_path=False,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(evidence["status"], "invalid")
            failed = [check["name"] for check in evidence["checks"] if not check["ok"]]
            self.assertIn("kernel_loader_output_absent_or_booted_kernel_source", failed)
            self.assertIn("no_enforcement_claim_without_valid_output", failed)

    def test_loader_evidence_invalid_when_output_claims_with_blocked_parser_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff_path = _handoff(tmp_path, ready=True)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=False)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=handoff_path,
                kernel_loader_output_path=_loader_output(
                    tmp_path,
                    handoff_path=handoff_path,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(evidence["status"], "invalid")
            self.assertFalse(evidence["kernel_enforcement_claimed"])
            self.assertEqual(evidence["summary"]["parser_promotion_receipt_status"], "blocked_until_phase66")
            failed = [check["name"] for check in evidence["checks"] if not check["ok"]]
            self.assertIn("no_enforcement_claim_without_parser_promotion_ready", failed)

    def test_loader_evidence_invalid_when_output_uses_wrong_pooleglyph_anchor_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff_path = _handoff(tmp_path, ready=True)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=True)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=handoff_path,
                kernel_loader_output_path=_loader_output(
                    tmp_path,
                    handoff_path=handoff_path,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                    source_hash_matches=False,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(evidence["status"], "invalid")
            self.assertFalse(evidence["summary"]["pooleglyph_source_anchor_digest_matches"])
            failed = [check["name"] for check in evidence["checks"] if not check["ok"]]
            self.assertIn("kernel_loader_output_absent_or_pooleglyph_source_anchor_hash_matches", failed)

    def test_cli_writes_ready_stub_without_enforcement_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "kernel_pgvm2_loader_evidence.json"
            with redirect_stdout(io.StringIO()):
                code = emit_kernel_pgvm2_loader_evidence.main(
                    [
                        "--kernel-boot-handoff",
                        str(_handoff(tmp_path, ready=True)),
                        "--kernel-loader-output",
                        str(tmp_path / "missing.json"),
                        "--pooleglyph-source-anchor",
                        str(_source_anchor(tmp_path)),
                        "--parser-kernel-promotion-receipt",
                        str(_promotion_receipt(tmp_path, ready=False)),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            evidence = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(evidence["artifact_kind"], "pooleos.kernel_pgvm2_loader_evidence")
            self.assertEqual(evidence["status"], "ready_for_kernel_loader")
            self.assertFalse(evidence["kernel_enforcement_claimed"])

    def test_release_gate_accepts_blocked_loader_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=_handoff(tmp_path, ready=False),
                kernel_loader_output_path=tmp_path / "missing.json",
                pooleglyph_source_anchor_path=_source_anchor(tmp_path),
                parser_kernel_promotion_receipt_path=_promotion_receipt(tmp_path, ready=False),
            )
            out = tmp_path / "kernel_pgvm2_loader_evidence.json"
            kernel_pgvm2_loader_evidence.write_evidence(evidence, out)
            check = pooleos_release_gate.check_kernel_pgvm2_loader_evidence(out)
            self.assertTrue(check["ok"], check)
            self.assertEqual(check["name"], "kernel_pgvm2_loader_evidence")
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
