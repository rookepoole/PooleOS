import sys
import unittest
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import lab_readiness, qemu_boot_evidence, qemu_captured_boot_preflight, qemu_captured_boot_receipt  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class LabReadinessTests(unittest.TestCase):
    def test_lab_scaffold_status_passes_but_boot_image_is_false(self) -> None:
        status = lab_readiness.lab_scaffold_status(ROOT)
        self.assertTrue(status["ok"], status)
        self.assertFalse(status["boot_image_built"])
        self.assertIn("no Buildroot image", status["boot_image_reason"])

    def test_release_gate_lab_check_is_present(self) -> None:
        check = pooleos_release_gate.check_lab_scaffold()
        self.assertEqual(check["name"], "lab_scaffold")
        self.assertTrue(check["ok"], check)
        self.assertIn("boot image not built", check["detail"])

    def test_release_gate_accepts_valid_buildroot_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "buildroot_probe.json"
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_probe",
                        "status": "pass",
                        "buildroot_path": str(Path(tmp) / "buildroot"),
                        "buildroot_version": "fake",
                        "buildroot_git_commit": "",
                        "buildroot_git_tag": "",
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "defconfig_path": str(
                            ROOT
                            / "lab-os"
                            / "buildroot"
                            / "external"
                            / "configs"
                            / "pooleos_lab_x86_64_defconfig"
                        ),
                        "checks": [
                            {"name": "buildroot_path", "ok": True, "detail": str(Path(tmp) / "buildroot")},
                            {"name": "buildroot_makefile", "ok": True, "detail": "Makefile"},
                            {"name": "external_tree", "ok": True, "detail": "external"},
                            {"name": "pooleos_defconfig", "ok": True, "detail": "defconfig"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_buildroot_probe(report_path)
            self.assertEqual(check["name"], "buildroot_probe")
            self.assertTrue(check["ok"], check)
            self.assertEqual(check["detail"], "status=pass")

    def test_release_gate_accepts_blocked_configure_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "buildroot_configure.json"
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_configure",
                        "status": "blocked",
                        "buildroot_path": str(Path(tmp) / "buildroot"),
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "defconfig_name": "pooleos_lab_x86_64_defconfig",
                        "output_dir": "",
                        "command": ["make", "-C", str(Path(tmp) / "buildroot"), "pooleos_lab_x86_64_defconfig"],
                        "exit_code": -1,
                        "stdout_tail": "GNU make was not found on PATH.",
                        "checks": [{"name": "gnu_make", "ok": False, "detail": "make not found on PATH"}],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_buildroot_configure(report_path)
            self.assertEqual(check["name"], "buildroot_configure")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])

    def test_release_gate_accepts_blocked_build_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "buildroot_build.json"
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_build",
                        "status": "blocked",
                        "execution_performed": False,
                        "buildroot_path": str(Path(tmp) / "buildroot"),
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "output_dir": str(Path(tmp) / "output"),
                        "command": ["make", "-C", str(Path(tmp) / "buildroot")],
                        "exit_code": -1,
                        "stdout_tail": "blocked until configure_status_pass",
                        "source_configure": {
                            "path": "buildroot_configure.json",
                            "exists": True,
                            "status": "blocked",
                            "output_dir": "",
                            "exit_code": -1,
                        },
                        "rootfs_image": {
                            "path": str(Path(tmp) / "output" / "images" / "rootfs.ext4"),
                            "exists": False,
                            "sha256": "",
                            "byte_count": 0,
                        },
                        "checks": [{"name": "configure_status_pass", "ok": False, "detail": "blocked"}],
                        "summary": {
                            "failed_check_count": 1,
                            "execution_performed": False,
                            "configure_status": "blocked",
                            "rootfs_image_exists": False,
                            "rootfs_image_sha256": "",
                        },
                        "limitations": ["test"],
                        "next_steps": ["test"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_buildroot_build(report_path)
            self.assertEqual(check["name"], "buildroot_build")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])

    def test_release_gate_accepts_blocked_wsl_prereqs_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "wsl_prerequisites.json"
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.wsl_prerequisites",
                        "status": "blocked",
                        "distro": "Ubuntu",
                        "source_basis": {
                            "buildroot_version": "2026.05",
                            "buildroot_git_commit": "313414b92c2501a2bc123ffa1b6383dca464de05",
                            "buildroot_manual_path": "docs/manual/prerequisite.adoc",
                        },
                        "execution_performed": False,
                        "host_modification_required": True,
                        "package_manager": "apt-get",
                        "install_command": "sudo apt-get install -y make qemu-system-x86",
                        "missing_packages": ["make", "qemu-system-x86"],
                        "checks": [
                            {
                                "name": "make",
                                "role": "buildroot_mandatory",
                                "command": "make",
                                "package": "make",
                                "required": True,
                                "ok": False,
                                "detail": "not found",
                            }
                        ],
                        "notes": ["non-mutating"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_wsl_prerequisites(report_path)
            self.assertEqual(check["name"], "wsl_prerequisites")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])

    def test_release_gate_accepts_pending_operator_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request_path = Path(tmp) / "operator_action.json"
            request_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.operator_action_request",
                        "status": "pending_approval",
                        "action_kind": "wsl_package_install",
                        "target": {
                            "environment": "wsl",
                            "distro": "Ubuntu",
                            "package_manager": "apt-get",
                        },
                        "source_artifact": "wsl_prerequisites.json",
                        "source_status": "blocked",
                        "requires_operator_approval": True,
                        "codex_execution_allowed": False,
                        "execution_performed": False,
                        "command": "sudo apt-get update && sudo apt-get install -y make",
                        "command_sha256": "0" * 64,
                        "packages": ["make"],
                        "safety_checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "next_steps": ["review"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_operator_action(request_path)
            self.assertEqual(check["name"], "operator_action")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pending_approval", check["detail"])

    def test_release_gate_accepts_pending_operator_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "operator_receipt.json"
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.operator_action_receipt",
                        "status": "pending_operator_action",
                        "action_kind": "wsl_package_install",
                        "target": {
                            "environment": "wsl",
                            "distro": "Ubuntu",
                            "package_manager": "apt-get",
                        },
                        "operator_action_request": "operator_action.json",
                        "verification_prerequisites": "wsl_prerequisites.json",
                        "operator_executed": False,
                        "codex_execution_performed": False,
                        "command": "sudo apt-get install -y make",
                        "command_sha256": "0" * 64,
                        "packages": ["make"],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "next_steps": ["review"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_operator_receipt(receipt_path)
            self.assertEqual(check["name"], "operator_receipt")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pending_operator_action", check["detail"])

    def test_release_gate_accepts_ready_host_prep_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note_path = Path(tmp) / "host_prep_note.json"
            note_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.host_prep_note",
                        "status": "ready_for_operator",
                        "note_path": str(Path(tmp) / "host_prep_note.md"),
                        "operator_action_request": "operator_action.json",
                        "operator_action_receipt": "operator_receipt.json",
                        "target": {
                            "environment": "wsl",
                            "distro": "Ubuntu",
                            "package_manager": "apt-get",
                        },
                        "request_status": "pending_approval",
                        "receipt_status": "pending_operator_action",
                        "requires_operator_approval": True,
                        "codex_execution_allowed": False,
                        "execution_performed": False,
                        "codex_execution_performed": False,
                        "operator_executed": False,
                        "command": "sudo apt-get install -y make",
                        "command_sha256": "0" * 64,
                        "packages": ["make"],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "next_steps": ["review"],
                        "verification_commands": ["python .\\tools\\pooleos_wsl_prereqs.py"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_host_prep_note(note_path)
            self.assertEqual(check["name"], "host_prep_note")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=ready_for_operator", check["detail"])

    def test_release_gate_accepts_static_isolation_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proof_path = Path(tmp) / "microkernel_isolation.json"
            proof_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.microkernel_isolation_spike",
                        "status": "pass",
                        "policy_version": "0.1",
                        "kernel_surface": "PGVM2.Rg region/capability map",
                        "security_boundary_claimed": False,
                        "source_basis": ["kernel charter"],
                        "compartments": [
                            {"id": "pgvm_guest", "trust_level": "untrusted", "role": "guest", "owns": ["program"]},
                            {"id": "geometry_kernel", "trust_level": "trusted", "role": "kernel", "owns": ["lattice"]},
                        ],
                        "channels": [
                            {
                                "source": "pgvm_guest",
                                "target": "geometry_kernel",
                                "capability": "invoke_rule",
                                "direction": "request",
                                "purpose": "test",
                                "allowed": True,
                                "requires_mediation": True,
                            }
                        ],
                        "denied_channels": [
                            {
                                "source": "pgvm_guest",
                                "target": "geometry_kernel",
                                "capability": "mutate_lattice_state",
                                "reason": "test denial",
                            }
                        ],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "compartment_count": 2,
                            "allowed_channel_count": 1,
                            "denied_channel_count": 1,
                            "failed_check_count": 0,
                        },
                        "limitations": ["static proof only"],
                        "next_steps": ["bind to opcodes"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_isolation_proof(proof_path)
            self.assertEqual(check["name"], "isolation_proof")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pass", check["detail"])

    def test_release_gate_accepts_capability_trap_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proof_path = Path(tmp) / "capability_trap_proof.json"
            proof_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.capability_trap_proof",
                        "status": "pass",
                        "policy_version": "0.1",
                        "policy_artifact": "microkernel_isolation.json",
                        "matrix_artifact": "permission_capability_matrix.json",
                        "matrix_summary": {
                            "matrix_bound": True,
                            "matrix_artifact": "permission_capability_matrix.json",
                            "matrix_status": "warn",
                            "matrix_failed_check_count": 0,
                            "matrix_operation_count": 2,
                            "core_ir_receipt_artifact": "pooleglyph_core_ir_boundary_receipt.json",
                            "core_ir_boundary_status": "phase66_pending",
                            "core_ir_binding_mode": "metadata_only_non_promoting",
                            "core_ir_phase66_audit_present": False,
                            "core_ir_executable_audit_artifact": "pooleglyph_core_ir_executable_audit.json",
                            "core_ir_executable_audit_bound": True,
                            "core_ir_executable_audit_status": "audited_non_promoting",
                            "core_ir_executable_candidate_count": 56,
                            "core_ir_metadata_zero_count": 95,
                            "core_ir_kernel_handoff_allowed": False,
                            "parser_kernel_promotion_receipt_artifact": "pooleglyph_parser_kernel_promotion_receipt.json",
                            "parser_kernel_promotion_receipt_bound": True,
                            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
                            "parser_kernel_promotion_kernel_handoff_allowed": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_enforcement_claimed": False,
                        },
                        "fuzz_artifact": "capability_trap_fuzz.json",
                        "fuzz_summary": {
                            "fuzz_bound": True,
                            "fuzz_artifact": "capability_trap_fuzz.json",
                            "fuzz_status": "pass",
                            "fuzz_failed_check_count": 0,
                            "fuzz_operation_count": 1,
                        },
                        "instruction_family": "PGB2 Regions And Capabilities",
                        "security_boundary_claimed": False,
                        "operations": [
                            {
                                "opcode": "ASSERT_REGION_CAP",
                                "region": "claim_lane_store",
                                "source": "pgvm_guest",
                                "target": "provenance_service",
                                "capability": "write_claim_lane",
                                "allowed": False,
                                "expected_trap": True,
                                "actual_trapped": True,
                                "trap_code": "CAPABILITY_DENIED",
                                "reason": "test",
                            },
                            {
                                "opcode": "SNAPSHOT_REGION",
                                "region": "release_manifest",
                                "source": "operator_shell",
                                "target": "provenance_service",
                                "capability": "read_manifest",
                                "allowed": True,
                                "expected_trap": False,
                                "actual_trapped": False,
                                "trap_code": "",
                                "reason": "test",
                            },
                        ],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "operation_count": 2,
                            "allowed_count": 1,
                            "trapped_count": 1,
                            "failed_check_count": 0,
                        },
                        "limitations": ["simulated"],
                        "next_steps": ["booted kernel check"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_capability_trap_proof(proof_path)
            self.assertEqual(check["name"], "capability_trap_proof")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pass", check["detail"])

    def test_release_gate_accepts_capability_trap_fuzz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proof_path = Path(tmp) / "capability_trap_fuzz.json"
            proof_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.capability_trap_fuzz",
                        "status": "pass",
                        "seed": "unit",
                        "policy_artifact": "microkernel_isolation.json",
                        "matrix_artifact": "permission_capability_matrix.json",
                        "security_boundary_claimed": False,
                        "operations": [
                            {
                                "case_id": "unknown_capability_00",
                                "fuzz_kind": "unknown_capability",
                                "opcode": "ASSERT_REGION_CAP",
                                "region": "fuzz_region",
                                "source": "pgvm_guest",
                                "target": "geometry_kernel",
                                "capability": "unknown_power",
                                "allowed": False,
                                "expected_trap": True,
                                "actual_trapped": True,
                                "trap_code": "CAPABILITY_UNKNOWN",
                                "reason": "unit",
                            },
                            {
                                "case_id": "unknown_permission_00",
                                "fuzz_kind": "unknown_permission",
                                "opcode": "ASSERT_MATRIX_PERMISSION",
                                "region": "grid.main_grid",
                                "source": "pgvm_guest",
                                "target": "geometry_kernel",
                                "capability": "delete_grid",
                                "allowed": False,
                                "matrix_allowed": False,
                                "expected_trap": True,
                                "actual_trapped": True,
                                "trap_code": "POOLEGLYPH_PERMISSION_DENIED",
                                "reason": "unit",
                            },
                        ],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "operation_count": 2,
                            "unknown_capability_count": 1,
                            "unknown_permission_count": 1,
                            "trapped_count": 2,
                            "failed_check_count": 0,
                        },
                        "limitations": ["bounded"],
                        "next_steps": ["bind proof"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_capability_trap_fuzz(proof_path)
            self.assertEqual(check["name"], "capability_trap_fuzz")
            self.assertTrue(check["ok"], check)
            self.assertIn("operations=2", check["detail"])

    def test_release_gate_accepts_pgb2_trap_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding_path = Path(tmp) / "pgb2_trap_encoding.json"
            encoding_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.pgb2_trap_encoding",
                        "status": "pass",
                        "encoding_version": "PGB2_TRAP_DRAFT_V0",
                        "source_trap_proof": {
                            "artifact_path": "capability_trap_proof.json",
                            "status": "pass",
                            "operation_count": 2,
                            "failed_check_count": 0,
                            "matrix_bound": True,
                            "fuzz_bound": True,
                            "core_ir_boundary_status": "phase66_pending",
                            "core_ir_binding_mode": "metadata_only_non_promoting",
                            "core_ir_executable_audit_bound": True,
                            "core_ir_executable_audit_status": "audited_non_promoting",
                            "core_ir_executable_candidate_count": 56,
                            "core_ir_metadata_zero_count": 95,
                            "core_ir_kernel_handoff_allowed": False,
                            "parser_kernel_promotion_receipt_bound": True,
                            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
                            "parser_kernel_promotion_kernel_handoff_allowed": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_enforcement_claimed": False,
                        },
                        "opcode_table": [
                            {
                                "operation_opcode": "ASSERT_REGION_CAP",
                                "encoded_opcode_hex": "E0",
                                "operand_layout": ["region", "source", "target", "capability", "expected_trap", "trap_code"],
                            }
                        ],
                        "program": {
                            "instruction_count": 2,
                            "byte_length": 4,
                            "raw_hex": "E0 00 E2 00",
                            "sha256": "A" * 64,
                        },
                        "instructions": [
                            {
                                "index": 0,
                                "source_operation_index": 0,
                                "operation_opcode": "ASSERT_REGION_CAP",
                                "encoded_opcode_hex": "E0",
                                "byte_length": 2,
                                "encoded_hex": "E0 00",
                                "encoded_sha256": "B" * 64,
                                "expected_trap": True,
                                "expected_trap_code": "CAPABILITY_UNKNOWN",
                                "decoded_operands": {"expected_trap": True, "trap_code": "CAPABILITY_UNKNOWN"},
                                "roundtrip_ok": True,
                            }
                        ],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "source_operation_count": 2,
                            "instruction_count": 2,
                            "byte_length": 4,
                            "allowed_instruction_count": 0,
                            "trapped_instruction_count": 2,
                            "matrix_instruction_count": 1,
                            "fuzz_instruction_count": 1,
                            "failed_check_count": 0,
                        },
                        "limitations": ["draft"],
                        "next_steps": ["execute"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_pgb2_trap_encoding(encoding_path)
            self.assertEqual(check["name"], "pgb2_trap_encoding")
            self.assertTrue(check["ok"], check)
            self.assertIn("instructions=2", check["detail"])

    def test_release_gate_accepts_pgb2_trap_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            execution_path = Path(tmp) / "pgb2_trap_execution.json"
            execution_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.pgb2_trap_execution",
                        "status": "pass",
                        "execution_version": "PGB2_TRAP_EXEC_DRAFT_V0",
                        "encoding_artifact": {
                            "artifact_path": "pgb2_trap_encoding.json",
                            "status": "pass",
                            "encoding_version": "PGB2_TRAP_DRAFT_V0",
                            "instruction_count": 2,
                            "byte_length": 4,
                            "sha256": "A" * 64,
                            "matrix_bound": True,
                            "fuzz_bound": True,
                            "core_ir_boundary_status": "phase66_pending",
                            "core_ir_binding_mode": "metadata_only_non_promoting",
                            "parser_kernel_promotion_receipt_bound": True,
                            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
                            "parser_kernel_promotion_kernel_handoff_allowed": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "failed_check_count": 0,
                        },
                        "security_boundary_claimed": False,
                        "program": {
                            "decoded_instruction_count": 2,
                            "byte_length": 4,
                            "sha256": "A" * 64,
                            "all_bytes_consumed": True,
                        },
                        "executed_instructions": [
                            {
                                "index": 0,
                                "source_instruction_index": 0,
                                "case_id": "",
                                "fuzz_kind": "",
                                "operation_opcode": "ASSERT_REGION_CAP",
                                "region": "claim_lane_store",
                                "source": "pgvm_guest",
                                "target": "provenance_service",
                                "capability": "write_claim_lane",
                                "expected_trap": True,
                                "expected_trap_code": "CAPABILITY_DENIED",
                                "actual_trapped": True,
                                "actual_trap_code": "CAPABILITY_DENIED",
                                "outcome_match": True,
                                "instruction_order_match": True,
                                "instruction_bytes_match": True,
                                "byte_offset": 0,
                                "byte_length": 2,
                            }
                        ],
                        "decode_errors": [],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "encoded_instruction_count": 2,
                            "executed_instruction_count": 2,
                            "allowed_count": 1,
                            "trapped_count": 1,
                            "matrix_instruction_count": 1,
                            "fuzz_instruction_count": 1,
                            "byte_length": 4,
                            "decode_error_count": 0,
                            "outcome_mismatch_count": 0,
                            "failed_check_count": 0,
                        },
                        "limitations": ["draft"],
                        "next_steps": ["booted kernel check"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_pgb2_trap_execution(execution_path)
            self.assertEqual(check["name"], "pgb2_trap_execution")
            self.assertTrue(check["ok"], check)
            self.assertIn("executed=2", check["detail"])

    def test_release_gate_accepts_boot_trap_bundle_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "boot_trap_bundle_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.boot_trap_bundle_manifest",
                        "status": "pass",
                        "manifest_role": "pooleos_lab_boot_trap_bundle_loader",
                        "lab_mount": {
                            "mount_dir": "/mnt/pooleos-output",
                            "bundle_target_path": "/mnt/pooleos-output/input.pgb2.json",
                            "replay_target_path": "/mnt/pooleos-output/input.replay.json",
                            "manifest_target_path": "/mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json",
                            "verification_result_path": "/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
                            "smoke_command": "pooleos-lab-smoke",
                            "verify_command": "pooleos-lab-verify-input --manifest /mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json --out /var/lib/pooleos/runs/boot_trap_bundle_verification.json",
                        },
                        "bundle": {
                            "source_path": "PooleOS_signed_trap_evidence.pgb2.json",
                            "target_path": "/mnt/pooleos-output/input.pgb2.json",
                            "sha256": "A" * 64,
                            "artifact_kind": "pooleos.pgb2_bundle",
                            "section_count": 6,
                            "section_names": ["CODE", "TRACE", "CLAIM_LANE", "SIGNED_METRICS", "TRAP_ENCODING", "TRAP_EXECUTION"],
                            "signed_metrics_present": True,
                            "trap_encoding_section_sha256": "B" * 64,
                            "trap_execution_section_sha256": "C" * 64,
                        },
                        "replay_proof": {
                            "source_path": "PooleOS_signed_trap_evidence.replay.json",
                            "target_path": "/mnt/pooleos-output/input.replay.json",
                            "sha256": "D" * 64,
                            "bundle_sha256": "A" * 64,
                            "channel_summary_match": True,
                            "signed_metrics_present": True,
                            "section_names": ["CLAIM_LANE", "CODE", "SIGNED_METRICS", "TRACE", "TRAP_ENCODING", "TRAP_EXECUTION"],
                        },
                        "trap_execution": {
                            "source_path": "PooleOS_pgb2_trap_execution.json",
                            "embedded_in_bundle": True,
                            "section_sha256": "C" * 64,
                            "body_sha256": "C" * 64,
                            "expected_summary": {
                                "status": "pass",
                                "program_sha256": "E" * 64,
                                "byte_length": 2556,
                                "encoded_instruction_count": 29,
                                "executed_instruction_count": 29,
                                "allowed_count": 4,
                                "trapped_count": 25,
                                "matrix_instruction_count": 10,
                                "fuzz_instruction_count": 20,
                                "decode_error_count": 0,
                                "outcome_mismatch_count": 0,
                                "failed_check_count": 0,
                                "security_boundary_claimed": False,
                            },
                        },
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "bundle_section_count": 6,
                            "trap_evidence_present": True,
                            "expected_executed_instruction_count": 29,
                            "expected_trapped_count": 25,
                            "expected_allowed_count": 4,
                            "failed_check_count": 0,
                        },
                        "limitations": ["pre-boot"],
                        "next_steps": ["mount into lab image"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_boot_trap_bundle_manifest(manifest_path)
            self.assertEqual(check["name"], "boot_trap_bundle_manifest")
            self.assertTrue(check["ok"], check)
            self.assertIn("executed=29", check["detail"])

    def test_release_gate_accepts_qemu_shared_folder_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "qemu_shared_folder_contract.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.qemu_shared_folder_contract",
                        "status": "pass",
                        "shared_folder": {
                            "host_path": str(Path(tmp) / "shared"),
                            "mount_tag": "pooleos_output",
                            "guest_mount_path": "/mnt/pooleos-output",
                            "qemu_args": [
                                "-virtfs",
                                f"local,path={Path(tmp) / 'shared'},mount_tag=pooleos_output,security_model=none,id=pooleos_output",
                            ],
                            "prepared_for_launch": True,
                        },
                        "staged_files": [
                            {
                                "role": "trap_bundle",
                                "source_path": "signed_trap_evidence.pgb2.json",
                                "host_path": str(Path(tmp) / "shared" / "input.pgb2.json"),
                                "guest_path": "/mnt/pooleos-output/input.pgb2.json",
                                "sha256": "A" * 64,
                                "expected_sha256": "A" * 64,
                            },
                            {
                                "role": "replay_proof",
                                "source_path": "signed_trap_evidence.replay.json",
                                "host_path": str(Path(tmp) / "shared" / "input.replay.json"),
                                "guest_path": "/mnt/pooleos-output/input.replay.json",
                                "sha256": "B" * 64,
                                "expected_sha256": "B" * 64,
                            },
                            {
                                "role": "boot_trap_bundle_manifest",
                                "source_path": "pooleos_boot_trap_bundle_manifest.json",
                                "host_path": str(Path(tmp) / "shared" / "pooleos_boot_trap_bundle_manifest.json"),
                                "guest_path": "/mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json",
                                "sha256": "C" * 64,
                                "expected_sha256": "C" * 64,
                            },
                        ],
                        "expected_guest_verification": {
                            "command": "pooleos-lab-verify-input --manifest /mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json --out /var/lib/pooleos/runs/boot_trap_bundle_verification.json",
                            "result_path": "/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
                            "expected_executed_instruction_count": 29,
                            "expected_trapped_count": 25,
                            "expected_allowed_count": 4,
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
                            "expected_executed_instruction_count": 29,
                            "abi_boundary_receipt_staged": False,
                            "expected_abi_boundary_status": "",
                        },
                        "limitations": ["pre-boot"],
                        "next_steps": ["launch QEMU"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_qemu_shared_folder_contract(contract_path)
            self.assertEqual(check["name"], "qemu_shared_folder_contract")
            self.assertTrue(check["ok"], check)
            self.assertIn("staged=3", check["detail"])

            required_check = pooleos_release_gate.check_qemu_shared_folder_contract(
                contract_path,
                require_abi_boundary_receipt=True,
            )
            self.assertFalse(required_check["ok"], required_check)
            self.assertIn("abi_required=True", required_check["detail"])

            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["staged_files"].append(
                {
                    "role": "pgb2_trap_abi_boundary_receipt",
                    "source_path": "pgb2_trap_abi_boundary_receipt.json",
                    "host_path": str(Path(tmp) / "shared" / "pgb2_trap_abi_boundary_receipt.json"),
                    "guest_path": "/mnt/pooleos-output/pgb2_trap_abi_boundary_receipt.json",
                    "sha256": "D" * 64,
                    "expected_sha256": "D" * 64,
                }
            )
            contract["expected_guest_verification"]["abi_boundary_receipt_guest_path"] = (
                "/mnt/pooleos-output/pgb2_trap_abi_boundary_receipt.json"
            )
            contract["expected_guest_verification"]["expected_abi_boundary_status"] = "draft_verified"
            contract["summary"]["staged_file_count"] = 4
            contract["summary"]["abi_boundary_receipt_staged"] = True
            contract["summary"]["expected_abi_boundary_status"] = "draft_verified"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")

            required_check = pooleos_release_gate.check_qemu_shared_folder_contract(
                contract_path,
                require_abi_boundary_receipt=True,
            )
            self.assertTrue(required_check["ok"], required_check)
            self.assertIn("staged=4", required_check["detail"])

    def test_release_gate_accepts_lab_guest_autostart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "lab_guest_autostart.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.lab_guest_autostart",
                        "status": "pass",
                        "boot_evidence_claimed": False,
                        "guest_autostart": {
                            "init_script_path": "S99pooleos-lab",
                            "init_order": "S99",
                            "smoke_command": "pooleos-lab-smoke",
                            "mount_tag": "pooleos_output",
                            "mount_point": "/mnt/pooleos-output",
                            "mount_type": "9p",
                            "mount_options": "trans=virtio,version=9p2000.L",
                        },
                        "qemu_shared_folder_contract": {
                            "artifact_path": "qemu_shared_folder_contract.json",
                            "status": "pass",
                            "mount_tag": "pooleos_output",
                            "host_path": "runs/qemu_shared",
                        },
                        "boot_log_profile": {
                            "profile": "trap-input",
                            "required_markers": [
                                "POOLEOS_LAB_AUTOSTART_START",
                                "POOLEOS_LAB_SHARED_MOUNT_PASS",
                                "POOLEOS_LAB_INPUT_VERIFY_PASS",
                                "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS",
                                "POOLEOS_LAB_BOOT_START",
                                "POOLEOS_LAB_DOCTOR_PASS",
                                "POOLEOS_LAB_RELEASE_GATE_PASS",
                                "POOLEOS_LAB_ARTIFACT_EXPORT_PASS",
                                "POOLEOS_LAB_BOOT_DONE",
                                "POOLEOS_LAB_AUTOSTART_DONE",
                            ],
                        },
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "failed_check_count": 0,
                            "required_marker_count": 10,
                            "autostart_marker_count": 3,
                            "qemu_contract_bound": True,
                        },
                        "limitations": ["static"],
                        "next_steps": ["boot QEMU"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_lab_guest_autostart(manifest_path)
            self.assertEqual(check["name"], "lab_guest_autostart")
            self.assertTrue(check["ok"], check)
            self.assertIn("profile=trap-input", check["detail"])

    def test_release_gate_accepts_fixture_qemu_boot_evidence_without_boot_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence_path = Path(tmp) / "qemu_boot_evidence.json"
            evidence = qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT)
            qemu_boot_evidence.write_evidence(evidence, evidence_path)
            check = pooleos_release_gate.check_qemu_boot_evidence(evidence_path)
            self.assertEqual(check["name"], "qemu_boot_evidence")
            self.assertTrue(check["ok"], check)
            self.assertIn("source=fixture", check["detail"])
            self.assertIn("boot_evidence_claimed=False", check["detail"])

    def test_release_gate_rejects_captured_qemu_boot_evidence_in_fixture_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence_path = Path(tmp) / "qemu_boot_evidence.json"
            evidence = qemu_boot_evidence.make_qemu_boot_evidence(
                root=ROOT,
                evidence_source="captured_qemu_serial",
            )
            qemu_boot_evidence.write_evidence(evidence, evidence_path)
            check = pooleos_release_gate.check_qemu_boot_evidence(evidence_path)
            self.assertFalse(check["ok"], check)
            self.assertIn("source=captured_qemu_serial", check["detail"])

    def test_release_gate_accepts_captured_qemu_boot_evidence_in_captured_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence_path = Path(tmp) / "qemu_boot_evidence.captured.json"
            evidence = qemu_boot_evidence.make_qemu_boot_evidence(
                root=ROOT,
                evidence_source="captured_qemu_serial",
            )
            qemu_boot_evidence.write_evidence(evidence, evidence_path)
            check = pooleos_release_gate.check_qemu_captured_boot_evidence(evidence_path)
            self.assertEqual(check["name"], "qemu_captured_boot_evidence")
            self.assertTrue(check["ok"], check)
            self.assertIn("source=captured_qemu_serial", check["detail"])
            self.assertIn("boot_evidence_claimed=True", check["detail"])

    def test_release_gate_accepts_pending_qemu_captured_boot_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture_path = tmp_path / "qemu_boot_evidence.json"
            receipt_path = tmp_path / "qemu_captured_boot_receipt.json"
            qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
            receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
                fixture_evidence_path=fixture_path,
                captured_evidence_path=tmp_path / "qemu_boot_evidence.captured.json",
            )
            qemu_captured_boot_receipt.write_receipt(receipt, receipt_path)
            check = pooleos_release_gate.check_qemu_captured_boot_receipt(receipt_path)
            self.assertEqual(check["name"], "qemu_captured_boot_receipt")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pending_capture", check["detail"])
            self.assertIn("fixture_preserved=True", check["detail"])

    def test_release_gate_accepts_blocked_qemu_captured_boot_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            preflight_path = tmp_path / "qemu_captured_boot_preflight.json"
            report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
                root=ROOT,
                image_path=tmp_path / "missing.ext4",
                shared_output_path=tmp_path / "missing_shared",
                serial_log_path=tmp_path / "serial.log",
                boot_validation_output=tmp_path / "boot_validation.json",
                qemu_boot_evidence_output=tmp_path / "qemu_boot_evidence.captured.json",
                qemu_captured_boot_receipt_output=tmp_path / "qemu_captured_boot_receipt.json",
                qemu_command="python",
            )
            qemu_captured_boot_preflight.write_preflight(report, preflight_path)
            check = pooleos_release_gate.check_qemu_captured_boot_preflight(preflight_path)
            self.assertEqual(check["name"], "qemu_captured_boot_preflight")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])

    def test_release_gate_accepts_ready_qemu_captured_boot_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake image", encoding="utf-8")
            shared = tmp_path / "qemu_shared"
            shared.mkdir()
            preflight_path = tmp_path / "qemu_captured_boot_preflight.json"
            report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
                root=ROOT,
                image_path=image,
                shared_output_path=shared,
                serial_log_path=tmp_path / "serial.log",
                boot_validation_output=tmp_path / "boot_validation.json",
                qemu_boot_evidence_output=tmp_path / "qemu_boot_evidence.captured.json",
                qemu_captured_boot_receipt_output=tmp_path / "qemu_captured_boot_receipt.json",
                qemu_command="python",
            )
            qemu_captured_boot_preflight.write_preflight(report, preflight_path)
            check = pooleos_release_gate.check_qemu_captured_boot_preflight(preflight_path)
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pass", check["detail"])
            self.assertIn("launch_ready=True", check["detail"])

    def test_release_gate_accepts_captured_qemu_captured_boot_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture_path = tmp_path / "qemu_boot_evidence.json"
            captured_path = tmp_path / "qemu_boot_evidence.captured.json"
            receipt_path = tmp_path / "qemu_captured_boot_receipt.json"
            qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), fixture_path)
            qemu_boot_evidence.write_evidence(
                qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT, evidence_source="captured_qemu_serial"),
                captured_path,
            )
            receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
                fixture_evidence_path=fixture_path,
                captured_evidence_path=captured_path,
            )
            qemu_captured_boot_receipt.write_receipt(receipt, receipt_path)
            check = pooleos_release_gate.check_qemu_captured_boot_receipt(receipt_path)
            self.assertTrue(check["ok"], check)
            self.assertIn("status=captured", check["detail"])
            self.assertIn("ingested=True", check["detail"])

    def test_release_gate_rejects_fixture_qemu_boot_evidence_with_boot_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence_path = Path(tmp) / "qemu_boot_evidence.json"
            evidence = qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT)
            evidence["boot_evidence_claimed"] = True
            evidence["summary"]["boot_evidence_claimed"] = True
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            check = pooleos_release_gate.check_qemu_boot_evidence(evidence_path)
            self.assertEqual(check["name"], "qemu_boot_evidence")
            self.assertFalse(check["ok"], check)

    def test_release_gate_accepts_pooleglyph_source_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_path = Path(tmp) / "pooleglyph_source_anchor.json"
            anchor_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.pooleglyph_source_anchor",
                        "status": "pass",
                        "pooleglyph_path": "C:\\Users\\rookp\\PooleGlyph",
                        "git": {
                            "is_work_tree": True,
                            "commit": "f" * 40,
                            "dirty_files": [],
                        },
                        "required_files": [{"path": "pooleglyph_pgvm.py", "exists": True}],
                        "checkpoint_root": "C:\\Users\\rookp\\PooleGlyph\\checkpoints",
                        "latest_checkpoint": {
                            "manifest_path": "phase19.manifest.json",
                            "handoff_markdown": "PHASE19.md",
                            "checkpoint": "Phase 19 - import/export enforcement",
                            "sha256": "A" * 64,
                            "zip_path": "phase19.zip",
                            "next_recommended_phase": "Phase 20 - version declarations",
                            "created_local_time": "2026-06-29 23:53:51",
                        },
                        "checkpoint_lineage": [
                            {
                                "manifest_path": "phase19.manifest.json",
                                "checkpoint": "Phase 19 - import/export enforcement",
                                "sha256": "A" * 64,
                                "created_local_time": "2026-06-29 23:53:51",
                            }
                        ],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "required_file_count": 1,
                            "missing_required_file_count": 0,
                            "checkpoint_manifest_count": 1,
                            "dirty_file_count": 0,
                            "failed_check_count": 0,
                        },
                        "next_steps": ["phase20"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_pooleglyph_source_anchor(anchor_path)
            self.assertEqual(check["name"], "pooleglyph_source_anchor")
            self.assertTrue(check["ok"], check)
            self.assertIn("latest=Phase 19", check["detail"])

    def test_release_gate_accepts_pooleglyph_bridge_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "pooleglyph_bridge_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.pooleglyph_bridge_manifest",
                        "status": "warn",
                        "source_anchor": {
                            "artifact_path": "pooleglyph_source_anchor.json",
                            "status": "warn",
                            "pooleglyph_path": "C:\\Users\\rookp\\PooleGlyph",
                            "commit": "f" * 40,
                            "dirty_file_count": 1,
                            "latest_checkpoint": "Phase 65 - diagnostic hardening across all declaration kinds",
                            "latest_phase": 65,
                            "failed_check_count": 0,
                        },
                        "required_inputs": [
                            {
                                "name": "source_anchor",
                                "path": "pooleglyph_source_anchor.json",
                                "exists": True,
                                "role": "source/checkpoint anchor",
                            }
                        ],
                        "language_surface": {
                            "phase": 61,
                            "phase_name": "language surface audit / PooleOS reorientation",
                            "stack_count": 48,
                            "stack": ["capability", "permission", "policy", "contract"],
                            "source_map_node_kind_count": 1,
                            "source_map_node_kinds": ["CapabilityDecl"],
                            "semantic_root_field_count": 1,
                            "semantic_root_fields": ["capabilities"],
                        },
                        "core_ir_boundary": {
                            "status": "phase66_pending",
                            "receipt_artifact_kind": "pooleos.pooleglyph_core_ir_boundary_receipt",
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "boundary_rule": "metadata remains metadata-only until receipt promotion",
                            "current_scope": ["public Core IR structural validation"],
                            "blocked_claims": ["parser-to-kernel readiness"],
                        },
                        "bridge_maps": {
                            "capability_security": {
                                "pooleglyph_declarations": ["capability", "permission", "policy", "contract"],
                                "missing_declarations": [],
                                "pooleos_targets": ["capability trap proof policy input"],
                                "coverage": "covered",
                                "boundary": "metadata-only",
                                "next_artifact": "pooleos.permission_capability_matrix",
                            }
                        },
                        "diagnostic_summary": {
                            "phase": 65,
                            "phase_name": "diagnostic hardening across all declaration kinds",
                            "diagnostic_case_count": 466,
                            "case_file_count": 55,
                            "parse_diagnostic_code_count": 205,
                            "semantic_diagnostic_code_count": 177,
                            "lexer_diagnostic_code_count": 1,
                            "stack_case_coverage_count": 48,
                            "missing_stack_case_files": [],
                            "next_recommended_phase": "Phase 66 - Core IR boundary audit",
                        },
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "bridge_map_count": 6,
                            "fully_covered_bridge_map_count": 6,
                            "language_stack_count": 48,
                            "diagnostic_case_count": 466,
                            "failed_check_count": 0,
                            "warning_count": 1,
                        },
                        "limitations": ["metadata-only"],
                        "next_steps": ["emit permission matrix"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_pooleglyph_bridge_manifest(manifest_path)
            self.assertEqual(check["name"], "pooleglyph_bridge_manifest")
            self.assertTrue(check["ok"], check)
            self.assertIn("latest_phase=65", check["detail"])

    def test_release_gate_accepts_permission_capability_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            matrix_path = Path(tmp) / "permission_capability_matrix.json"
            matrix_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.permission_capability_matrix",
                        "status": "warn",
                        "bridge_manifest": {
                            "artifact_path": "pooleglyph_bridge_manifest.json",
                            "status": "warn",
                            "latest_phase": 65,
                            "failed_check_count": 0,
                            "pooleglyph_path": "C:\\Users\\rookp\\PooleGlyph",
                        },
                        "core_ir_boundary_receipt": {
                            "artifact_path": "pooleglyph_core_ir_boundary_receipt.json",
                            "exists": True,
                            "status": "phase66_pending",
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "failed_check_count": 0,
                            "failed_promotion_gate_count": 1,
                            "validated_executable_candidate_count": 56,
                            "validated_metadata_zero_program_count": 95,
                            "unexpected_invalid_count": 0,
                            "validation_file_count": 154,
                            "binding_mode": "metadata_only_non_promoting",
                        },
                        "core_ir_executable_audit": {
                            "artifact_path": "pooleglyph_core_ir_executable_audit.json",
                            "exists": True,
                            "status": "audited_non_promoting",
                            "source_boundary_receipt": "pooleglyph_core_ir_boundary_receipt.json",
                            "source_matches_receipt": True,
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "failed_check_count": 0,
                            "executable_candidate_count": 56,
                            "metadata_zero_count": 95,
                            "unexpected_invalid_count": 0,
                        },
                        "parser_kernel_promotion_receipt": {
                            "artifact_path": "pooleglyph_parser_kernel_promotion_receipt.json",
                            "exists": True,
                            "status": "blocked_until_phase66",
                            "source_executable_audit": "pooleglyph_core_ir_executable_audit.json",
                            "source_matches_audit": True,
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "failed_check_count": 0,
                        },
                        "symbol_sources": [
                            {
                                "kind": "permissions",
                                "path": "permission_demo.symbols.json",
                                "exists": True,
                                "module": "snapshots.permission",
                            }
                        ],
                        "capabilities": [{"name": "geometry", "source_modules": ["m"], "source_paths": ["p"]}],
                        "resources": [
                            {
                                "id": "grid.main_grid",
                                "kind": "grid",
                                "name": "main_grid",
                                "fields": {"kind": "cellular"},
                                "source_modules": ["m"],
                                "source_paths": ["p"],
                            }
                        ],
                        "permissions": [
                            {
                                "name": "read_grid",
                                "access_hint": "read",
                                "resource_kind_hint": "grid",
                                "source_modules": ["m"],
                                "source_paths": ["p"],
                            }
                        ],
                        "policies": [
                            {
                                "name": "safe_public",
                                "allowed_permissions": ["read_grid"],
                                "missing_permissions": [],
                                "source_modules": ["m"],
                                "source_paths": ["p"],
                            }
                        ],
                        "contracts": [
                            {
                                "name": "public_api",
                                "required_policies": ["safe_public"],
                                "missing_policies": [],
                                "source_modules": ["m"],
                                "source_paths": ["p"],
                            }
                        ],
                        "resource_permissions": [
                            {
                                "resource_id": "grid.main_grid",
                                "permission": "read_grid",
                                "access_hint": "read",
                                "binding_source": "unit",
                                "binding_mode": "metadata_only_non_promoting",
                                "core_ir_boundary_status": "phase66_pending",
                                "parser_to_kernel_promotion_allowed": False,
                                "policy_allowed": True,
                                "policy_names": ["safe_public"],
                                "contract_names": ["public_api"],
                                "expected_trap": False,
                                "reason": "unit",
                            },
                            {
                                "resource_id": "grid.main_grid",
                                "permission": "write_grid",
                                "access_hint": "write",
                                "binding_source": "unit",
                                "binding_mode": "metadata_only_non_promoting",
                                "core_ir_boundary_status": "phase66_pending",
                                "parser_to_kernel_promotion_allowed": False,
                                "policy_allowed": False,
                                "policy_names": [],
                                "contract_names": [],
                                "expected_trap": True,
                                "reason": "unit",
                            },
                        ],
                        "trap_operations": [
                            {
                                "opcode": "ASSERT_MATRIX_PERMISSION",
                                "region": "grid.main_grid",
                                "source": "pgvm_guest",
                                "target": "geometry_kernel",
                                "capability": "read_grid",
                                "matrix_allowed": True,
                                "expected_trap": False,
                                "binding_mode": "metadata_only_non_promoting",
                                "core_ir_boundary_status": "phase66_pending",
                                "parser_to_kernel_promotion_allowed": False,
                                "reason": "unit",
                            }
                        ],
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "capability_count": 1,
                            "resource_count": 1,
                            "permission_count": 2,
                            "policy_count": 1,
                            "contract_count": 1,
                            "resource_permission_count": 2,
                            "allowed_resource_permission_count": 1,
                            "denied_resource_permission_count": 1,
                            "trap_operation_count": 1,
                            "failed_check_count": 0,
                            "warning_count": 1,
                            "core_ir_binding_mode": "metadata_only_non_promoting",
                            "core_ir_phase66_audit_present": False,
                            "core_ir_executable_audit_bound": True,
                            "core_ir_executable_audit_status": "audited_non_promoting",
                            "core_ir_executable_candidate_count": 56,
                            "core_ir_metadata_zero_count": 95,
                            "core_ir_kernel_handoff_allowed": False,
                            "parser_kernel_promotion_receipt_bound": True,
                            "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
                            "parser_kernel_promotion_kernel_handoff_allowed": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_enforcement_claimed": False,
                        },
                        "limitations": ["metadata-only"],
                        "next_steps": ["bind trap proof"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_permission_capability_matrix(matrix_path)
            self.assertEqual(check["name"], "permission_capability_matrix")
            self.assertTrue(check["ok"], check)
            self.assertIn("trap_ops=1", check["detail"])

    def test_release_gate_accepts_pooleglyph_core_ir_executable_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "pooleglyph_core_ir_executable_audit.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.pooleglyph_core_ir_executable_audit",
                        "status": "audited_non_promoting",
                        "source_boundary_receipt": {
                            "artifact_path": "pooleglyph_core_ir_boundary_receipt.json",
                            "exists": True,
                            "artifact_kind": "pooleos.pooleglyph_core_ir_boundary_receipt",
                            "status": "phase66_pending",
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "failed_check_count": 0,
                            "failed_promotion_gate_count": 1,
                        },
                        "audit_scope": {
                            "validation_file_count": 5,
                            "valid_file_count": 2,
                            "validator_versions": ["pg-coreir-validator-v0.1"],
                            "total_program_count": 1,
                            "total_instruction_count": 3,
                            "public_safe_note_count": 5,
                        },
                        "executable_candidates": [
                            {
                                "path": "outputs_coreir/exec.validate.json",
                                "sha256": "A" * 64,
                                "classification": "validated_executable_candidate",
                                "ok": True,
                                "module": "exec",
                                "program_count": 1,
                                "instruction_count": 3,
                                "validator_version": "pg-coreir-validator-v0.1",
                                "public_safe_notes_present": True,
                                "diagnostic_codes": [],
                            }
                        ],
                        "metadata_zero_outputs": [
                            {
                                "path": "outputs_coreir/meta.validate.json",
                                "sha256": "B" * 64,
                                "classification": "validated_metadata_zero_program",
                                "ok": True,
                                "module": "meta",
                                "program_count": 0,
                                "instruction_count": 0,
                                "validator_version": "pg-coreir-validator-v0.1",
                                "public_safe_notes_present": True,
                                "diagnostic_codes": [],
                            }
                        ],
                        "expected_negative_fixtures": [],
                        "structural_anomalies": [],
                        "unexpected_invalid_outputs": [],
                        "boundary_decisions": {
                            "executable_candidate_decision": "structural_candidate_only",
                            "metadata_zero_decision": "metadata_only_not_kernel_program",
                            "parser_to_kernel_decision": "blocked_until_phase66_promotion_receipt",
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "reason": "unit",
                        },
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "failed_check_count": 0,
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "executable_candidate_count": 1,
                            "metadata_zero_count": 1,
                            "expected_negative_fixture_count": 0,
                            "structural_anomaly_count": 0,
                            "unexpected_invalid_count": 0,
                            "validation_file_count": 5,
                        },
                        "limitations": ["unit"],
                        "next_steps": ["unit"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_pooleglyph_core_ir_executable_audit(audit_path)
            self.assertEqual(check["name"], "pooleglyph_core_ir_executable_audit")
            self.assertTrue(check["ok"], check)
            self.assertIn("audited_non_promoting", check["detail"])

    def test_release_gate_accepts_pooleglyph_parser_kernel_promotion_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "pooleglyph_parser_kernel_promotion_receipt.json"
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.pooleglyph_parser_kernel_promotion_receipt",
                        "status": "blocked_until_phase66",
                        "source_executable_audit": {
                            "artifact_path": "pooleglyph_core_ir_executable_audit.json",
                            "exists": True,
                            "artifact_kind": "pooleos.pooleglyph_core_ir_executable_audit",
                            "status": "audited_non_promoting",
                            "source_boundary_receipt": "pooleglyph_core_ir_boundary_receipt.json",
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "failed_check_count": 0,
                        },
                        "promotion_decision": {
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "decision": "blocked_until_phase66_promotion",
                            "reason": "unit",
                        },
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "failed_check_count": 0,
                            "phase66_audit_present": False,
                            "parser_to_kernel_promotion_allowed": False,
                            "kernel_handoff_allowed": False,
                            "kernel_enforcement_claimed": False,
                            "executable_candidate_count": 56,
                            "metadata_zero_count": 95,
                            "unexpected_invalid_count": 0,
                        },
                        "limitations": ["blocked"],
                        "next_steps": ["bind matrix"],
                    }
                ),
                encoding="utf-8",
            )
            check = pooleos_release_gate.check_pooleglyph_parser_kernel_promotion_receipt(receipt_path)
            self.assertEqual(check["name"], "pooleglyph_parser_kernel_promotion_receipt")
            self.assertTrue(check["ok"], check)
            self.assertIn("blocked_until_phase66", check["detail"])


if __name__ == "__main__":
    unittest.main()
