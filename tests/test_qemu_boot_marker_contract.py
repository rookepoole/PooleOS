import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_log, qemu_boot_marker_contract  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_boot_marker_contract, pooleos_release_gate  # noqa: E402


def _write_inputs(tmp_path: Path, *, dry_run_status: str = "pass", marker_drop: str = "") -> dict[str, Path]:
    markers = boot_log.required_markers_for_profile("trap-input")
    if marker_drop:
        markers = [marker for marker in markers if marker != marker_drop]
    dry_run_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
    autostart_path = tmp_path / "lab_guest_autostart.json"
    dry_run_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.qemu_captured_boot_dry_run_checklist",
                "status": dry_run_status,
                "launch_ready": dry_run_status == "pass",
                "execution_performed": False,
                "expected_serial_markers": markers,
                "post_capture_files": [
                    {"role": "serial_log", "path": str(tmp_path / "pooleos-lab-serial.log")},
                    {"role": "boot_validation", "path": str(tmp_path / "boot_log_validation.captured.json")},
                    {"role": "captured_boot_evidence", "path": str(tmp_path / "qemu_boot_evidence.captured.json")},
                    {"role": "captured_boot_receipt", "path": str(tmp_path / "qemu_captured_boot_receipt.json")},
                    {"role": "release_gate", "path": str(tmp_path / "release_gate.json")},
                ],
                "summary": {
                    "failed_check_count": 0,
                    "blocking_check_count": 1 if dry_run_status == "blocked" else 0,
                },
            }
        ),
        encoding="utf-8",
    )
    autostart_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.lab_guest_autostart",
                "status": "pass",
                "boot_evidence_claimed": False,
                "boot_log_profile": {
                    "profile": "trap-input",
                    "required_markers": boot_log.required_markers_for_profile("trap-input"),
                },
                "summary": {
                    "failed_check_count": 0,
                    "required_marker_count": len(boot_log.required_markers_for_profile("trap-input")),
                },
            }
        ),
        encoding="utf-8",
    )
    return {"dry_run": dry_run_path, "autostart": autostart_path}


class QemuBootMarkerContractTests(unittest.TestCase):
    def test_contract_passes_with_ready_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_inputs(Path(tmp))
            contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
                root=ROOT,
                dry_run_checklist_path=paths["dry_run"],
                lab_guest_autostart_path=paths["autostart"],
            )
            schema = json.loads((ROOT / "specs" / "qemu-boot-marker-contract.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(contract, schema), [])
            self.assertEqual(contract["status"], "pass")
            self.assertFalse(contract["execution_performed"])
            self.assertFalse(contract["boot_evidence_claimed"])
            self.assertFalse(contract["security_boundary_claimed"])
            self.assertEqual(contract["summary"]["marker_count"], len(boot_log.required_markers_for_profile("trap-input")))
            self.assertEqual(contract["summary"]["boundary_count"], len(boot_log.required_markers_for_profile("trap-input")))
            self.assertEqual(
                [mapping["marker"] for mapping in contract["marker_mappings"]],
                boot_log.required_markers_for_profile("trap-input"),
            )

    def test_contract_blocks_when_dry_run_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_inputs(Path(tmp), dry_run_status="blocked")
            contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
                root=ROOT,
                dry_run_checklist_path=paths["dry_run"],
                lab_guest_autostart_path=paths["autostart"],
            )
            self.assertEqual(contract["status"], "blocked")
            self.assertEqual(contract["summary"]["failed_check_count"], 0)
            self.assertGreater(contract["summary"]["blocking_check_count"], 0)

    def test_contract_fails_when_marker_sequence_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_inputs(Path(tmp), marker_drop="POOLEOS_LAB_INPUT_VERIFY_PASS")
            contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
                root=ROOT,
                dry_run_checklist_path=paths["dry_run"],
                lab_guest_autostart_path=paths["autostart"],
            )
            self.assertEqual(contract["status"], "fail")
            self.assertGreater(contract["summary"]["failed_check_count"], 0)

    def test_cli_writes_valid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_inputs(tmp_path)
            out = tmp_path / "qemu_boot_marker_contract.json"
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_boot_marker_contract.main(
                    [
                        "--dry-run-checklist",
                        str(paths["dry_run"]),
                        "--lab-guest-autostart",
                        str(paths["autostart"]),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            contract = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(contract["artifact_kind"], "pooleos.qemu_boot_marker_contract")
            self.assertEqual(contract["status"], "pass")

    def test_release_gate_accepts_blocked_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_inputs(Path(tmp), dry_run_status="blocked")
            contract_path = Path(tmp) / "qemu_boot_marker_contract.json"
            contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
                root=ROOT,
                dry_run_checklist_path=paths["dry_run"],
                lab_guest_autostart_path=paths["autostart"],
            )
            qemu_boot_marker_contract.write_contract(contract, contract_path)
            check = pooleos_release_gate.check_qemu_boot_marker_contract(contract_path)
            self.assertEqual(check["name"], "qemu_boot_marker_contract")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
