import io
import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import lab_kernel_transcript_export_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_lab_kernel_transcript_export_receipt, pooleos_release_gate  # noqa: E402


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _contract(tmp_path: Path) -> Path:
    path = tmp_path / "pooleos-kernel-pgvm2-transcript-contract"
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    return path


def _transcript(
    tmp_path: Path,
    *,
    source_anchor_sha256: str = "c" * 64,
    parser_promotion_sha256: str = "d" * 64,
    include_guest_environment: bool = True,
    duplicate_source_anchor: bool = False,
) -> Path:
    path = tmp_path / "kernel_pgvm2_loader.transcript.txt"
    lines = ["POOLEOS_KERNEL_LOADER_START"]
    if include_guest_environment:
        lines.extend(
            [
                "POOLEOS_KERNEL_GUEST_ENV "
                f"POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 {source_anchor_sha256}",
                "POOLEOS_KERNEL_GUEST_ENV "
                f"POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 {parser_promotion_sha256}",
            ]
        )
    if duplicate_source_anchor:
        lines.append(
            "POOLEOS_KERNEL_GUEST_ENV "
            f"POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 {source_anchor_sha256}"
        )
    lines.append("POOLEOS_KERNEL_LOADER_DONE")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _loader_output(
    tmp_path: Path,
    *,
    status: str = "blocked",
    claimed: bool = False,
    failed: int = 0,
) -> Path:
    blocking = 0 if status == "pass" else 10
    satisfied = 11 if status == "pass" else 1
    transcript_path = tmp_path / "kernel_pgvm2_loader.transcript.txt"
    return _write_json(
        tmp_path / "kernel_pgvm2_loader_output.json",
        {
            "artifact_kind": "pooleos.kernel_pgvm2_loader_output",
            "status": status,
            "booted_kernel_path": claimed,
            "kernel_enforcement_claimed": claimed,
            "pgvm2_execution_claimed": claimed,
            "source_handoff_sha256": "b" * 64,
            "pooleglyph_source_anchor_sha256": "c" * 64,
            "pooleglyph_parser_kernel_promotion_receipt_sha256": "d" * 64,
            "summary": {
                "failed_check_count": failed,
                "blocking_check_count": blocking,
                "kernel_check_count": 11,
                "satisfied_kernel_check_count": satisfied,
                "negative_claim_guard_held": True,
            },
            "transcript_claims": {
                "booted_kernel_path": claimed,
                "kernel_enforcement_claimed": claimed,
                "pgvm2_execution_claimed": claimed,
            },
            "transcript_source": {
                "path": str(transcript_path),
                "exists": transcript_path.exists(),
                "sha256": _sha256(transcript_path) if transcript_path.exists() else "",
                "line_count": len(transcript_path.read_text(encoding="utf-8").splitlines())
                if transcript_path.exists()
                else 0,
            },
        },
    )


class LabKernelTranscriptExportReceiptTests(unittest.TestCase):
    def test_pending_receipt_validates_and_does_not_claim_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path),
                kernel_loader_output_path=_loader_output(tmp_path),
            )
            schema = json.loads(
                (ROOT / "specs" / "lab-kernel-transcript-export-receipt.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(validate_json(receipt, schema), [])
            self.assertEqual(receipt["status"], "pending_contract_run")
            self.assertFalse(receipt["contract_run_recorded"])
            self.assertFalse(receipt["verifier_accepted_export"])
            self.assertFalse(receipt["kernel_enforcement_promotion_allowed"])
            self.assertEqual(receipt["summary"]["failed_check_count"], 0)

    def test_pending_receipt_allows_unattested_stale_transcript_without_claiming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path, include_guest_environment=False),
                kernel_loader_output_path=_loader_output(tmp_path),
            )
            self.assertEqual(receipt["status"], "pending_contract_run")
            self.assertFalse(receipt["guest_environment_digest_pair_attested"])
            self.assertFalse(receipt["verifier_accepted_export"])

    def test_disabled_verified_receipt_accepts_non_claiming_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path),
                kernel_loader_output_path=_loader_output(tmp_path),
                contract_run_recorded=True,
                contract_mode="disabled",
            )
            self.assertEqual(receipt["status"], "disabled_verified")
            self.assertTrue(receipt["verifier_accepted_export"])
            self.assertFalse(receipt["kernel_enforcement_promotion_allowed"])
            self.assertFalse(receipt["verifier_output"]["kernel_enforcement_claimed"])
            self.assertTrue(receipt["guest_environment_digest_pair_attested"])
            self.assertTrue(receipt["transcript_digest_matches_verifier"])

    def test_enabled_verified_receipt_requires_pass_loader_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path),
                kernel_loader_output_path=_loader_output(tmp_path, status="pass", claimed=True),
                contract_run_recorded=True,
                contract_mode="enabled",
            )
            self.assertEqual(receipt["status"], "enabled_verified")
            self.assertTrue(receipt["verifier_accepted_export"])
            self.assertTrue(receipt["kernel_enforcement_promotion_allowed"])

    def test_recorded_run_rejects_mismatched_guest_digest_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path, source_anchor_sha256="e" * 64),
                kernel_loader_output_path=_loader_output(tmp_path),
                contract_run_recorded=True,
                contract_mode="disabled",
            )
            self.assertEqual(receipt["status"], "verification_failed")
            self.assertFalse(receipt["guest_environment_digest_pair_attested"])
            self.assertGreater(receipt["summary"]["failed_check_count"], 0)

    def test_recorded_run_rejects_duplicate_guest_environment_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path, duplicate_source_anchor=True),
                kernel_loader_output_path=_loader_output(tmp_path),
                contract_run_recorded=True,
                contract_mode="disabled",
            )
            self.assertEqual(receipt["status"], "verification_failed")
            self.assertEqual(receipt["guest_environment"]["source_anchor"]["occurrence_count"], 2)
            self.assertFalse(receipt["guest_environment_digest_pair_attested"])

    def test_recorded_run_rejects_transcript_not_bound_to_verifier_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            transcript_path = _transcript(tmp_path)
            loader_path = _loader_output(tmp_path)
            loader = json.loads(loader_path.read_text(encoding="utf-8"))
            loader["transcript_source"]["sha256"] = "f" * 64
            _write_json(loader_path, loader)
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=transcript_path,
                kernel_loader_output_path=loader_path,
                contract_run_recorded=True,
                contract_mode="disabled",
            )
            self.assertEqual(receipt["status"], "verification_failed")
            self.assertFalse(receipt["transcript_digest_matches_verifier"])

    def test_overclaiming_disabled_receipt_is_not_release_gate_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt_path = tmp_path / "receipt.json"
            receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                contract_source_path=_contract(tmp_path),
                transcript_path=_transcript(tmp_path),
                kernel_loader_output_path=_loader_output(tmp_path, status="pass", claimed=True),
                contract_run_recorded=True,
                contract_mode="disabled",
            )
            lab_kernel_transcript_export_receipt.write_receipt(receipt, receipt_path)
            self.assertEqual(receipt["status"], "verification_failed")
            self.assertTrue(receipt["summary"]["overclaim_detected"])
            check = pooleos_release_gate.check_lab_kernel_transcript_export_receipt(receipt_path)
            self.assertFalse(check["ok"], check)

    def test_cli_writes_pending_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "receipt.json"
            with redirect_stdout(io.StringIO()):
                code = emit_lab_kernel_transcript_export_receipt.main(
                    [
                        "--contract-source",
                        str(_contract(tmp_path)),
                        "--transcript",
                        str(_transcript(tmp_path)),
                        "--kernel-loader-output",
                        str(_loader_output(tmp_path)),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_kind"], "pooleos.lab_kernel_transcript_export_receipt")
            self.assertEqual(receipt["status"], "pending_contract_run")

    def test_release_gate_accepts_pending_and_disabled_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_path = tmp_path / "pending.json"
            disabled_path = tmp_path / "disabled.json"
            lab_kernel_transcript_export_receipt.write_receipt(
                lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                    contract_source_path=_contract(tmp_path),
                    transcript_path=_transcript(tmp_path),
                    kernel_loader_output_path=_loader_output(tmp_path),
                ),
                pending_path,
            )
            lab_kernel_transcript_export_receipt.write_receipt(
                lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                    contract_source_path=_contract(tmp_path),
                    transcript_path=_transcript(tmp_path),
                    kernel_loader_output_path=_loader_output(tmp_path),
                    contract_run_recorded=True,
                    contract_mode="disabled",
                ),
                disabled_path,
            )
            self.assertTrue(pooleos_release_gate.check_lab_kernel_transcript_export_receipt(pending_path)["ok"])
            self.assertTrue(pooleos_release_gate.check_lab_kernel_transcript_export_receipt(disabled_path)["ok"])

    def test_release_gate_rejects_receipt_after_verifier_artifact_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            receipt_path = tmp_path / "receipt.json"
            transcript_path = _transcript(tmp_path)
            loader_path = _loader_output(tmp_path)
            lab_kernel_transcript_export_receipt.write_receipt(
                lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
                    contract_source_path=_contract(tmp_path),
                    transcript_path=transcript_path,
                    kernel_loader_output_path=loader_path,
                ),
                receipt_path,
            )
            loader = json.loads(loader_path.read_text(encoding="utf-8"))
            loader["kernel_build_id"] = "substituted-after-receipt"
            _write_json(loader_path, loader)
            check = pooleos_release_gate.check_lab_kernel_transcript_export_receipt(
                receipt_path,
                loader_path,
            )
            self.assertFalse(check["ok"], check)


if __name__ == "__main__":
    unittest.main()
