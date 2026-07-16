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
from runtime import qemu_captured_boot_launch_bundle  # noqa: E402
from runtime import qemu_captured_boot_preflight  # noqa: E402
from runtime import qemu_captured_boot_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_captured_boot_launch_bundle  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


def _write_shared_contract(path: Path, shared: Path, *, host_path: Path | None = None) -> None:
    contract = {
        "schema_version": "0.1",
        "artifact_kind": "pooleos.qemu_shared_folder_contract",
        "status": "pass",
        "shared_folder": {
            "host_path": str(host_path or shared),
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


def _write_launch_inputs(tmp_path: Path, *, launch_ready: bool = True, shared_override: Path | None = None) -> dict[str, Path]:
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
    _write_shared_contract(shared_contract_path, shared, host_path=shared_override)
    qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
    receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
        fixture_evidence_path=fixture_path,
        captured_evidence_path=captured_path,
    )
    qemu_captured_boot_receipt.write_receipt(receipt, receipt_path)
    return {
        "preflight": preflight_path,
        "shared_contract": shared_contract_path,
        "receipt": receipt_path,
        "fixture": fixture_path,
        "out": tmp_path / "qemu_captured_boot_launch_bundle.json",
    }


class QemuCapturedBootLaunchBundleTests(unittest.TestCase):
    def test_launch_bundle_passes_when_inputs_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_inputs(tmp_path)
            bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
                root=ROOT,
                preflight_path=paths["preflight"],
                qemu_shared_folder_contract_path=paths["shared_contract"],
                qemu_captured_boot_receipt_path=paths["receipt"],
                fixture_evidence_path=paths["fixture"],
                launch_bundle_output_path=paths["out"],
            )
            schema = json.loads((ROOT / "specs" / "qemu-captured-boot-launch-bundle.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(bundle, schema), [])
            self.assertEqual(bundle["status"], "pass")
            self.assertTrue(bundle["launch_ready"])
            self.assertFalse(bundle["execution_performed"])
            roles = {command["role"] for command in bundle["command_plan"]}
            self.assertIn("qemu_launch", roles)
            self.assertIn("--qemu-captured-boot-launch-bundle", bundle["release_gate_arguments"])

    def test_launch_bundle_blocks_when_preflight_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_inputs(tmp_path, launch_ready=False)
            bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
                root=ROOT,
                preflight_path=paths["preflight"],
                qemu_shared_folder_contract_path=paths["shared_contract"],
                qemu_captured_boot_receipt_path=paths["receipt"],
                fixture_evidence_path=paths["fixture"],
                launch_bundle_output_path=paths["out"],
            )
            self.assertEqual(bundle["status"], "blocked")
            self.assertEqual(bundle["summary"]["failed_check_count"], 0)
            self.assertGreater(bundle["summary"]["blocking_check_count"], 0)

    def test_release_gate_accepts_blocked_launch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_inputs(tmp_path, launch_ready=False)
            bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
                root=ROOT,
                preflight_path=paths["preflight"],
                qemu_shared_folder_contract_path=paths["shared_contract"],
                qemu_captured_boot_receipt_path=paths["receipt"],
                fixture_evidence_path=paths["fixture"],
                launch_bundle_output_path=paths["out"],
            )
            qemu_captured_boot_launch_bundle.write_bundle(bundle, paths["out"])
            check = pooleos_release_gate.check_qemu_captured_boot_launch_bundle(paths["out"])
            self.assertEqual(check["name"], "qemu_captured_boot_launch_bundle")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])

    def test_release_gate_accepts_ready_launch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_inputs(tmp_path)
            bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
                root=ROOT,
                preflight_path=paths["preflight"],
                qemu_shared_folder_contract_path=paths["shared_contract"],
                qemu_captured_boot_receipt_path=paths["receipt"],
                fixture_evidence_path=paths["fixture"],
                launch_bundle_output_path=paths["out"],
            )
            qemu_captured_boot_launch_bundle.write_bundle(bundle, paths["out"])
            check = pooleos_release_gate.check_qemu_captured_boot_launch_bundle(paths["out"])
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pass", check["detail"])
            self.assertIn("commands=5", check["detail"])

    def test_launch_bundle_fails_when_shared_path_does_not_match_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_inputs(tmp_path, shared_override=tmp_path / "different_shared")
            bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
                root=ROOT,
                preflight_path=paths["preflight"],
                qemu_shared_folder_contract_path=paths["shared_contract"],
                qemu_captured_boot_receipt_path=paths["receipt"],
                fixture_evidence_path=paths["fixture"],
                launch_bundle_output_path=paths["out"],
            )
            self.assertEqual(bundle["status"], "fail")
            self.assertGreater(bundle["summary"]["failed_check_count"], 0)

    def test_cli_writes_valid_launch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = _write_launch_inputs(tmp_path)
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_captured_boot_launch_bundle.main(
                    [
                        "--preflight",
                        str(paths["preflight"]),
                        "--qemu-shared-folder-contract",
                        str(paths["shared_contract"]),
                        "--qemu-captured-boot-receipt",
                        str(paths["receipt"]),
                        "--fixture-evidence",
                        str(paths["fixture"]),
                        "--out",
                        str(paths["out"]),
                    ]
                )
            self.assertEqual(code, 0)
            bundle = json.loads(paths["out"].read_text(encoding="utf-8"))
            self.assertEqual(bundle["artifact_kind"], "pooleos.qemu_captured_boot_launch_bundle")
            self.assertEqual(bundle["status"], "pass")


if __name__ == "__main__":
    unittest.main()
