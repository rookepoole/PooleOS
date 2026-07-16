import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kernel_boot_handoff  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_kernel_boot_handoff, pooleos_release_gate  # noqa: E402


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _readiness(tmp_path: Path, *, ready: bool) -> Path:
    return _write_json(
        tmp_path / "qemu_captured_boot_readiness.json",
        {
            "artifact_kind": "pooleos.qemu_captured_boot_readiness",
            "status": "ready_for_promotion" if ready else "blocked",
            "promotion_language_allowed": ready,
            "summary": {
                "failed_check_count": 0,
                "unmet_requirement_count": 0 if ready else 3,
                "captured_evidence_valid": ready,
            },
        },
    )


def _marker_contract(tmp_path: Path, *, ready: bool, kernel_claimed: bool = False) -> Path:
    return _write_json(
        tmp_path / "qemu_boot_marker_contract.json",
        {
            "artifact_kind": "pooleos.qemu_boot_marker_contract",
            "status": "pass" if ready else "blocked",
            "boot_evidence_claimed": False,
            "security_boundary_claimed": False,
            "kernel_pgvm2_boundary": {
                "kernel_boundary_claimed": kernel_claimed,
                "pgvm2_execution_claimed": False,
            },
            "summary": {
                "failed_check_count": 0,
                "blocking_check_count": 0 if ready else 1,
                "marker_count": 10,
                "expected_marker_count": 10,
                "boundary_count": 10,
            },
        },
    )


def _boot_manifest(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "pooleos_boot_trap_bundle_manifest.json",
        {
            "artifact_kind": "pooleos.boot_trap_bundle_manifest",
            "status": "pass",
            "lab_mount": {
                "verification_result_path": "/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
            },
            "summary": {
                "failed_check_count": 0,
                "trap_evidence_present": True,
                "expected_executed_instruction_count": 29,
            },
        },
    )


def _guest_verification(tmp_path: Path, *, valid: bool = True) -> Path:
    return _write_json(
        tmp_path / "boot_trap_bundle_verification.json",
        {
            "artifact_kind": "pooleos.boot_trap_bundle_verification" if valid else "wrong.kind",
            "status": "pass",
            "summary": {
                "failed_check_count": 0,
                "expected_executed_instruction_count": 29,
            },
        },
    )


class KernelBootHandoffTests(unittest.TestCase):
    def test_handoff_blocks_until_capture_and_guest_loader_output_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = kernel_boot_handoff.make_kernel_boot_handoff(
                qemu_captured_boot_readiness_path=_readiness(tmp_path, ready=False),
                qemu_boot_marker_contract_path=_marker_contract(tmp_path, ready=False),
                boot_trap_bundle_manifest_path=_boot_manifest(tmp_path),
                guest_loader_verification_path=tmp_path / "missing_verification.json",
            )
            schema = json.loads((ROOT / "specs" / "kernel-boot-handoff.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(handoff, schema), [])
            self.assertEqual(handoff["status"], "blocked")
            self.assertFalse(handoff["kernel_handoff_allowed"])
            self.assertFalse(handoff["kernel_boundary_claimed"])
            self.assertGreater(handoff["summary"]["unmet_requirement_count"], 0)

    def test_handoff_ready_when_all_inputs_are_present_and_agree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = kernel_boot_handoff.make_kernel_boot_handoff(
                qemu_captured_boot_readiness_path=_readiness(tmp_path, ready=True),
                qemu_boot_marker_contract_path=_marker_contract(tmp_path, ready=True),
                boot_trap_bundle_manifest_path=_boot_manifest(tmp_path),
                guest_loader_verification_path=_guest_verification(tmp_path),
            )
            self.assertEqual(handoff["status"], "ready_for_kernel_handoff")
            self.assertTrue(handoff["kernel_handoff_allowed"])
            self.assertFalse(handoff["pgvm2_execution_claimed"])
            self.assertEqual(handoff["summary"]["unmet_requirement_count"], 0)

    def test_handoff_invalid_when_present_loader_output_has_wrong_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = kernel_boot_handoff.make_kernel_boot_handoff(
                qemu_captured_boot_readiness_path=_readiness(tmp_path, ready=True),
                qemu_boot_marker_contract_path=_marker_contract(tmp_path, ready=True),
                boot_trap_bundle_manifest_path=_boot_manifest(tmp_path),
                guest_loader_verification_path=_guest_verification(tmp_path, valid=False),
            )
            self.assertEqual(handoff["status"], "invalid")
            failed = [check["name"] for check in handoff["checks"] if not check["ok"]]
            self.assertIn("guest_loader_output_absent_or_structural", failed)

    def test_cli_writes_blocked_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "kernel_boot_handoff.json"
            with redirect_stdout(io.StringIO()):
                code = emit_kernel_boot_handoff.main(
                    [
                        "--qemu-captured-boot-readiness",
                        str(_readiness(tmp_path, ready=False)),
                        "--qemu-boot-marker-contract",
                        str(_marker_contract(tmp_path, ready=False)),
                        "--boot-trap-bundle-manifest",
                        str(_boot_manifest(tmp_path)),
                        "--guest-loader-verification",
                        str(tmp_path / "missing.json"),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            handoff = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(handoff["artifact_kind"], "pooleos.kernel_boot_handoff")
            self.assertEqual(handoff["status"], "blocked")

    def test_release_gate_accepts_blocked_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = kernel_boot_handoff.make_kernel_boot_handoff(
                qemu_captured_boot_readiness_path=_readiness(tmp_path, ready=False),
                qemu_boot_marker_contract_path=_marker_contract(tmp_path, ready=False),
                boot_trap_bundle_manifest_path=_boot_manifest(tmp_path),
                guest_loader_verification_path=tmp_path / "missing.json",
            )
            out = tmp_path / "kernel_boot_handoff.json"
            kernel_boot_handoff.write_handoff(handoff, out)
            check = pooleos_release_gate.check_kernel_boot_handoff(out)
            self.assertTrue(check["ok"], check)
            self.assertEqual(check["name"], "kernel_boot_handoff")
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
