import io
import json
import hashlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kernel_pgvm2_loader_evidence  # noqa: E402
from runtime import kernel_pgvm2_loader_output  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_kernel_pgvm2_loader_output, pooleos_release_gate, verify_kernel_pgvm2_loader_transcript  # noqa: E402


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _handoff(tmp_path: Path, *, ready: bool = True) -> Path:
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


def _write_transcript(
    path: Path,
    handoff_path: Path,
    *,
    source_anchor_path: Path,
    promotion_receipt_path: Path,
    complete: bool,
    overclaim: bool = False,
    wrong_source_anchor_hash: bool = False,
) -> Path:
    names = [check["name"] for check in kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS]
    lines = [
        "POOLEOS_KERNEL_LOADER_START",
        "POOLEOS_KERNEL_BUILD_ID transcript-test-kernel",
        f"POOLEOS_KERNEL_HANDOFF_SHA256 {_sha256(handoff_path)}",
        "POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 "
        f"{'wrong' if wrong_source_anchor_hash else _sha256(source_anchor_path)}",
        f"POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 {_sha256(promotion_receipt_path)}",
        "POOLEOS_KERNEL_BOOTED_PATH true" if complete or overclaim else "POOLEOS_KERNEL_BOOTED_PATH false",
        "POOLEOS_KERNEL_ENFORCEMENT_CLAIM true" if complete or overclaim else "POOLEOS_KERNEL_ENFORCEMENT_CLAIM false",
        "POOLEOS_PGVM2_EXECUTION_CLAIM true" if complete or overclaim else "POOLEOS_PGVM2_EXECUTION_CLAIM false",
        "POOLEOS_KERNEL_EXPECTED_INSTRUCTIONS 29",
        "POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS 29" if complete else "POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS 0",
    ]
    for name in names:
        if complete or name in {"handoff_digest_lock", "negative_claim_guard"}:
            lines.append(f"POOLEOS_KERNEL_CHECK {name} PASS")
        else:
            lines.append(f"POOLEOS_KERNEL_CHECK {name} FAIL")
    lines.append("POOLEOS_KERNEL_LOADER_DONE")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _promotion_receipt(tmp_path: Path, *, ready: bool = False) -> Path:
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


class KernelPgvm2LoaderOutputTests(unittest.TestCase):
    def test_negative_fixture_validates_and_refuses_enforcement_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
                kernel_boot_handoff_path=_handoff(tmp_path),
                pooleglyph_source_anchor_path=_source_anchor(tmp_path),
                parser_kernel_promotion_receipt_path=_promotion_receipt(tmp_path),
            )
            schema = json.loads(
                (ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_json(output, schema), [])
            self.assertEqual(output["status"], "blocked")
            self.assertFalse(output["booted_kernel_path"])
            self.assertFalse(output["kernel_enforcement_claimed"])
            self.assertFalse(output["pgvm2_execution_claimed"])
            self.assertTrue(output["summary"]["negative_claim_guard_held"])
            self.assertEqual(output["summary"]["kernel_check_count"], len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS))
            self.assertEqual(output["summary"]["satisfied_kernel_check_count"], 1)

    def test_synthetic_pass_validates_future_booted_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
                kernel_boot_handoff_path=_handoff(tmp_path),
                pooleglyph_source_anchor_path=_source_anchor(tmp_path),
                parser_kernel_promotion_receipt_path=_promotion_receipt(tmp_path, ready=True),
                kernel_build_id="synthetic-kernel",
                mode="synthetic_pass",
            )
            schema = json.loads(
                (ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_json(output, schema), [])
            self.assertEqual(output["status"], "pass")
            self.assertTrue(output["booted_kernel_path"])
            self.assertTrue(output["kernel_enforcement_claimed"])
            self.assertEqual(
                output["summary"]["satisfied_kernel_check_count"],
                len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS),
            )
            self.assertEqual(output["summary"]["actual_executed_instruction_count"], 29)

    def test_evidence_accepts_present_negative_fixture_without_invalidating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _handoff(tmp_path)
            output_path = tmp_path / "kernel_pgvm2_loader_output.json"
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path)
            kernel_pgvm2_loader_output.write_output(
                kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
                    kernel_boot_handoff_path=handoff,
                    pooleglyph_source_anchor_path=source_anchor,
                    parser_kernel_promotion_receipt_path=promotion_receipt,
                ),
                output_path,
            )
            evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
                kernel_boot_handoff_path=handoff,
                kernel_loader_output_path=output_path,
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(evidence["status"], "ready_for_kernel_loader")
            self.assertEqual(evidence["summary"]["failed_check_count"], 0)
            self.assertTrue(evidence["summary"]["kernel_loader_output_exists"])
            self.assertTrue(evidence["summary"]["output_handoff_hash_matches"])
            self.assertFalse(evidence["kernel_enforcement_claimed"])

    def test_cli_writes_negative_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "kernel_pgvm2_loader_output.json"
            with redirect_stdout(io.StringIO()):
                code = emit_kernel_pgvm2_loader_output.main(
                    [
                        "--kernel-boot-handoff",
                        str(_handoff(tmp_path)),
                        "--pooleglyph-source-anchor",
                        str(_source_anchor(tmp_path)),
                        "--parser-kernel-promotion-receipt",
                        str(_promotion_receipt(tmp_path)),
                        "--kernel-build-id",
                        "pending-test-kernel",
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            output = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(output["artifact_kind"], "pooleos.kernel_pgvm2_loader_output")
            self.assertEqual(output["status"], "blocked")
            self.assertFalse(output["kernel_enforcement_claimed"])

    def test_release_gate_accepts_negative_fixture_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "kernel_pgvm2_loader_output.json"
            kernel_pgvm2_loader_output.write_output(
                kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
                    kernel_boot_handoff_path=_handoff(tmp_path),
                    pooleglyph_source_anchor_path=_source_anchor(tmp_path),
                    parser_kernel_promotion_receipt_path=_promotion_receipt(tmp_path),
                ),
                out,
            )
            check = pooleos_release_gate.check_kernel_pgvm2_loader_output(out)
            self.assertTrue(check["ok"], check)
            self.assertEqual(check["name"], "kernel_pgvm2_loader_output")
            self.assertIn("status=blocked", check["detail"])

    def test_transcript_verifier_promotes_complete_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _handoff(tmp_path)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=True)
            output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output_from_transcript(
                kernel_boot_handoff_path=handoff,
                transcript_path=_write_transcript(
                    tmp_path / "loader.transcript.txt",
                    handoff,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                    complete=True,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            schema = json.loads(
                (ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_json(output, schema), [])
            self.assertEqual(output["status"], "pass")
            self.assertTrue(output["booted_kernel_path"])
            self.assertTrue(output["kernel_enforcement_claimed"])
            self.assertTrue(output["pgvm2_execution_claimed"])
            self.assertEqual(output["summary"]["blocking_check_count"], 0)
            self.assertEqual(
                output["summary"]["satisfied_kernel_check_count"],
                len(kernel_pgvm2_loader_evidence.PLANNED_KERNEL_CHECKS),
            )
            self.assertTrue(output["transcript_source"]["exists"])

    def test_transcript_verifier_blocks_incomplete_non_claiming_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _handoff(tmp_path)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path)
            output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output_from_transcript(
                kernel_boot_handoff_path=handoff,
                transcript_path=_write_transcript(
                    tmp_path / "loader.transcript.txt",
                    handoff,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                    complete=False,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(output["status"], "blocked")
            self.assertFalse(output["kernel_enforcement_claimed"])
            self.assertEqual(output["summary"]["failed_check_count"], 0)
            self.assertGreater(output["summary"]["blocking_check_count"], 0)

    def test_transcript_verifier_invalidates_overclaiming_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _handoff(tmp_path)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path)
            output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output_from_transcript(
                kernel_boot_handoff_path=handoff,
                transcript_path=_write_transcript(
                    tmp_path / "loader.transcript.txt",
                    handoff,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                    complete=False,
                    overclaim=True,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(output["status"], "invalid")
            self.assertFalse(output["kernel_enforcement_claimed"])
            self.assertEqual(output["summary"]["failed_check_count"], 1)

    def test_transcript_verifier_invalidates_mismatched_pooleglyph_anchor_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _handoff(tmp_path)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=True)
            output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output_from_transcript(
                kernel_boot_handoff_path=handoff,
                transcript_path=_write_transcript(
                    tmp_path / "loader.transcript.txt",
                    handoff,
                    source_anchor_path=source_anchor,
                    promotion_receipt_path=promotion_receipt,
                    complete=True,
                    wrong_source_anchor_hash=True,
                ),
                pooleglyph_source_anchor_path=source_anchor,
                parser_kernel_promotion_receipt_path=promotion_receipt,
            )
            self.assertEqual(output["status"], "invalid")
            failed = [check["name"] for check in output["kernel_checks"] if not check["ok"]]
            self.assertIn("pooleglyph_source_anchor_digest_bind", failed)
            self.assertFalse(output["kernel_enforcement_claimed"])

    def test_transcript_cli_writes_pass_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _handoff(tmp_path)
            source_anchor = _source_anchor(tmp_path)
            promotion_receipt = _promotion_receipt(tmp_path, ready=True)
            transcript = _write_transcript(
                tmp_path / "loader.transcript.txt",
                handoff,
                source_anchor_path=source_anchor,
                promotion_receipt_path=promotion_receipt,
                complete=True,
            )
            out = tmp_path / "kernel_pgvm2_loader_output.json"
            with redirect_stdout(io.StringIO()):
                code = verify_kernel_pgvm2_loader_transcript.main(
                    [
                        "--kernel-boot-handoff",
                        str(handoff),
                        "--transcript",
                        str(transcript),
                        "--pooleglyph-source-anchor",
                        str(source_anchor),
                        "--parser-kernel-promotion-receipt",
                        str(promotion_receipt),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            output = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(output["status"], "pass")
            self.assertTrue(output["kernel_enforcement_claimed"])


if __name__ == "__main__":
    unittest.main()
