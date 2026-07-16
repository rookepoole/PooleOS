import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_boot_evidence  # noqa: E402
from runtime import qemu_captured_boot_dry_run_checklist  # noqa: E402
from runtime import qemu_captured_boot_launch_bundle  # noqa: E402
from runtime import qemu_captured_boot_preflight  # noqa: E402
from runtime import qemu_captured_boot_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_captured_boot_dry_run_checklist  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


def _write_shared_contract(path: Path, shared: Path) -> None:
    contract = {
        "schema_version": "0.1",
        "artifact_kind": "pooleos.qemu_shared_folder_contract",
        "status": "pass",
        "shared_folder": {
            "host_path": str(shared),
            "mount_tag": "pooleos_output",
            "guest_mount_path": "/mnt/pooleos-output",
            "qemu_args": [
                "-virtfs",
                f"local,path={shared},mount_tag=pooleos_output,security_model=none,id=pooleos_output",
            ],
            "prepared_for_launch": True,
        },
        "staged_files": [
            {
                "role": "trap_bundle",
                "source_path": str(path.parent / "input.pgb2.json"),
                "host_path": str(shared / "input.pgb2.json"),
                "guest_path": "/mnt/pooleos-output/input.pgb2.json",
                "sha256": "a" * 64,
                "expected_sha256": "a" * 64,
            },
            {
                "role": "replay_proof",
                "source_path": str(path.parent / "input.replay.json"),
                "host_path": str(shared / "input.replay.json"),
                "guest_path": "/mnt/pooleos-output/input.replay.json",
                "sha256": "b" * 64,
                "expected_sha256": "b" * 64,
            },
            {
                "role": "boot_trap_bundle_manifest",
                "source_path": str(path.parent / "pooleos_boot_trap_bundle_manifest.json"),
                "host_path": str(shared / "pooleos_boot_trap_bundle_manifest.json"),
                "guest_path": "/mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json",
                "sha256": "c" * 64,
                "expected_sha256": "c" * 64,
            },
        ],
        "expected_guest_verification": {
            "command": "pooleos-lab-verify-input",
            "result_path": "/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
            "expected_executed_instruction_count": 1,
            "expected_trapped_count": 0,
            "expected_allowed_count": 1,
            "abi_boundary_receipt_guest_path": "",
            "expected_abi_boundary_status": "",
            "expected_abi_frozen": False,
            "expected_kernel_abi_promotion_allowed": False,
            "expected_kernel_enforcement_claimed": False,
        },
        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
        "summary": {
            "staged_file_count": 3,
            "failed_check_count": 0,
            "perform_copy": True,
            "expected_executed_instruction_count": 1,
            "abi_boundary_receipt_staged": False,
            "expected_abi_boundary_status": "",
        },
        "limitations": ["unit"],
        "next_steps": ["boot"],
    }
    path.write_text(json.dumps(contract), encoding="utf-8")


def _write_launch_bundle(tmp_path: Path, *, launch_ready: bool = True) -> dict[str, Path]:
    image = tmp_path / "rootfs.ext4"
    if launch_ready:
        image.write_text("fake image", encoding="utf-8")
    shared = tmp_path / "qemu_shared"
    shared.mkdir()
    preflight_path = tmp_path / "qemu_captured_boot_preflight.json"
    shared_contract_path = tmp_path / "qemu_shared_folder_contract.json"
    receipt_path = tmp_path / "qemu_captured_boot_receipt.json"
    fixture_path = tmp_path / "qemu_boot_evidence.json"
    captured_path = tmp_path / "qemu_boot_evidence.captured.json"
    launch_bundle_path = tmp_path / "qemu_captured_boot_launch_bundle.json"
    checklist_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
    preflight = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
        root=ROOT,
        image_path=image if launch_ready else tmp_path / "missing.ext4",
        shared_output_path=shared,
        serial_log_path=tmp_path / "pooleos-lab-serial.log",
        boot_validation_output=tmp_path / "boot_log_validation.captured.json",
        qemu_boot_evidence_output=captured_path,
        qemu_captured_boot_receipt_output=receipt_path,
        qemu_command=sys.executable,
    )
    qemu_captured_boot_preflight.write_preflight(preflight, preflight_path)
    _write_shared_contract(shared_contract_path, shared)
    qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
    receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
        fixture_evidence_path=fixture_path,
        captured_evidence_path=captured_path,
    )
    qemu_captured_boot_receipt.write_receipt(receipt, receipt_path)
    bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
        root=ROOT,
        preflight_path=preflight_path,
        qemu_shared_folder_contract_path=shared_contract_path,
        qemu_captured_boot_receipt_path=receipt_path,
        fixture_evidence_path=fixture_path,
        launch_bundle_output_path=launch_bundle_path,
        release_gate_output_path=tmp_path / "release_gate.json",
    )
    qemu_captured_boot_launch_bundle.write_bundle(bundle, launch_bundle_path)
    return {
        "launch_bundle": launch_bundle_path,
        "checklist": checklist_path,
    }


class QemuCapturedBootDryRunChecklistTests(unittest.TestCase):
    def test_checklist_passes_when_launch_bundle_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_bundle(tmp_path)
            checklist = qemu_captured_boot_dry_run_checklist.make_qemu_captured_boot_dry_run_checklist(
                root=ROOT,
                launch_bundle_path=paths["launch_bundle"],
                checklist_output_path=paths["checklist"],
                release_gate_output_path=tmp_path / "release_gate.json",
            )
            schema = json.loads((ROOT / "specs" / "qemu-captured-boot-dry-run-checklist.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(checklist, schema), [])
            self.assertEqual(checklist["status"], "pass")
            self.assertTrue(checklist["launch_ready"])
            self.assertFalse(checklist["execution_performed"])
            self.assertIn("POOLEOS_LAB_INPUT_VERIFY_PASS", checklist["expected_serial_markers"])
            self.assertIn("--qemu-captured-boot-dry-run-checklist", checklist["release_gate_reconciliation"]["checklist_arguments"])
            self.assertFalse(checklist["operator_receipt_template"]["operator_executed"])

    def test_checklist_blocks_when_preflight_has_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_bundle(tmp_path, launch_ready=False)
            checklist = qemu_captured_boot_dry_run_checklist.make_qemu_captured_boot_dry_run_checklist(
                root=ROOT,
                launch_bundle_path=paths["launch_bundle"],
                checklist_output_path=paths["checklist"],
            )
            self.assertEqual(checklist["status"], "blocked")
            self.assertEqual(checklist["summary"]["failed_check_count"], 0)
            self.assertGreater(checklist["summary"]["preflight_blocker_count"], 0)

    def test_checklist_fails_for_invalid_launch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            launch_bundle_path = tmp_path / "bad_bundle.json"
            launch_bundle_path.write_text(json.dumps({"artifact_kind": "wrong"}), encoding="utf-8")
            checklist = qemu_captured_boot_dry_run_checklist.make_qemu_captured_boot_dry_run_checklist(
                root=ROOT,
                launch_bundle_path=launch_bundle_path,
                checklist_output_path=tmp_path / "checklist.json",
            )
            self.assertEqual(checklist["status"], "fail")
            self.assertGreater(checklist["summary"]["failed_check_count"], 0)

    def test_cli_writes_valid_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_bundle(tmp_path)
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_captured_boot_dry_run_checklist.main(
                    [
                        "--launch-bundle",
                        str(paths["launch_bundle"]),
                        "--release-gate-output",
                        str(tmp_path / "release_gate.json"),
                        "--out",
                        str(paths["checklist"]),
                    ]
                )
            self.assertEqual(code, 0)
            checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
            self.assertEqual(checklist["artifact_kind"], "pooleos.qemu_captured_boot_dry_run_checklist")
            self.assertEqual(checklist["status"], "pass")

    def test_release_gate_accepts_blocked_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_bundle(tmp_path, launch_ready=False)
            checklist = qemu_captured_boot_dry_run_checklist.make_qemu_captured_boot_dry_run_checklist(
                root=ROOT,
                launch_bundle_path=paths["launch_bundle"],
                checklist_output_path=paths["checklist"],
            )
            qemu_captured_boot_dry_run_checklist.write_checklist(checklist, paths["checklist"])
            check = pooleos_release_gate.check_qemu_captured_boot_dry_run_checklist(paths["checklist"])
            self.assertEqual(check["name"], "qemu_captured_boot_dry_run_checklist")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
