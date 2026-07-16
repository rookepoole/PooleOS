import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_tier0  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeTier0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lock = native_tier0.read_json(ROOT / native_tier0.LOCK_RELATIVE)
        cls.profile = native_tier0.read_json(ROOT / native_tier0.PROFILE_RELATIVE)
        cls.readiness = native_tier0.read_json(ROOT / native_tier0.READINESS_RELATIVE)

    def test_public_contracts_match_schemas(self) -> None:
        cases = (
            (self.lock, native_tier0.LOCK_SCHEMA_RELATIVE),
            (self.profile, native_tier0.PROFILE_SCHEMA_RELATIVE),
            (self.readiness, native_tier0.READINESS_SCHEMA_RELATIVE),
        )
        for artifact, schema_relative in cases:
            with self.subTest(schema=schema_relative):
                schema = native_tier0.read_json(ROOT / schema_relative)
                self.assertEqual([], list(validate_json(artifact, schema)))

    def test_frozen_contracts_pass_semantic_validation(self) -> None:
        lock, profile = native_tier0.validate_contracts()
        self.assertEqual(self.lock, lock)
        self.assertEqual(self.profile, profile)

    def test_qemu_and_edk2_provenance_gaps_remain_explicit(self) -> None:
        self.assertEqual("11.0.2", self.lock["upstream_qemu"]["latest_stable_version"])
        self.assertEqual("11.0.0", self.lock["windows_runner"]["version"])
        self.assertFalse(self.lock["windows_runner"]["latest_upstream_patch_level_matched"])
        self.assertEqual("edk2-stable202605", self.lock["firmware"]["target_stable_tag"])
        self.assertFalse(self.lock["firmware"]["runner_bundled_matches_target_stable"])
        self.assertFalse(self.lock["windows_runner"]["authenticode"]["acceptance_signal"])

    def test_normalized_command_generation_is_exact(self) -> None:
        for profile_id in native_tier0.PROFILE_IDS:
            with self.subTest(profile=profile_id):
                first = native_tier0.normalized_command(self.profile, profile_id)
                second = native_tier0.normalized_command(self.profile, profile_id)
                self.assertEqual(first, second)
                self.assertEqual(
                    native_tier0.sha256_bytes(native_tier0.canonical_json_bytes(first)),
                    native_tier0.sha256_bytes(native_tier0.canonical_json_bytes(second)),
                )

    def test_base_profile_is_q35_tcg_and_modern_virtio_only(self) -> None:
        command = native_tier0.normalized_command(self.profile, "bootstrap-debug")
        joined = "\n".join(command)
        self.assertIn("pc-q35-11.0,smm=off,usb=off,vmport=off", command)
        self.assertIn("tcg,thread=single", command)
        self.assertIn("virtio-blk-pci-non-transitional,drive=pooleos_media", command)
        self.assertIn("readonly=on,file=$MEDIA_READ_ONLY", joined)
        self.assertIn("readonly=on,file=$QEMU_ROOT/share/edk2-x86_64-code.fd", joined)
        self.assertNotIn("virtio-blk-pci-transitional", joined)
        self.assertNotIn("-netdev", command)
        self.assertNotIn("-virtfs", command)

    def test_secure_firmware_profile_does_not_claim_secure_boot(self) -> None:
        command = native_tier0.normalized_command(self.profile, "secure-firmware-prep")
        self.assertIn("pc-q35-11.0,smm=on,usb=off,vmport=off", command)
        self.assertIn("driver=cfi.pflash01,property=secure,value=on", command)
        secure = {item["id"]: item for item in self.profile["profiles"]}["secure-firmware-prep"]
        self.assertFalse(secure["secure_boot_enabled"])
        self.assertFalse(secure["secure_boot_claimed"])

    def test_gdb_is_loopback_and_opt_in(self) -> None:
        normal = native_tier0.normalized_command(self.profile, "bootstrap-debug")
        debug = native_tier0.normalized_command(self.profile, "bootstrap-debug", debug=True)
        self.assertNotIn("-gdb", normal)
        self.assertIn("-gdb", debug)
        self.assertIn("tcp:127.0.0.1:1234,server=on,wait=off", debug)
        self.assertEqual("127.0.0.1", self.profile["evidence_contract"]["gdb_bind_address"])

    def test_profile_mutations_fail_closed(self) -> None:
        cases = (
            ("machine", lambda value: value["machine"].update({"type": "q35"})),
            ("network", lambda value: value["machine"].update({"network_enabled": True})),
            ("host_accel", lambda value: value["machine"].update({"host_acceleration_enabled": True})),
            ("legacy_virtio", lambda value: value["devices"].update({"virtio_legacy_allowed": True})),
            ("transitional_virtio", lambda value: value["devices"].update({"virtio_transitional_allowed": True})),
            ("writable_code", lambda value: value["firmware_flash"].update({"code_read_only": False})),
            ("vars_reuse", lambda value: value["firmware_flash"].update({"vars_template_never_written": False})),
            ("unknown_args", lambda value: value["launch_policy"].update({"unknown_arguments_allowed": True})),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                altered = copy.deepcopy(self.profile)
                mutate(altered)
                self.assertTrue(native_tier0.profile_contract_errors(altered))

    def test_lock_mutations_fail_closed(self) -> None:
        altered = copy.deepcopy(self.lock)
        altered["windows_runner"]["version"] = "11.0.50"
        self.assertTrue(native_tier0.lock_contract_errors(altered))
        altered = copy.deepcopy(self.lock)
        altered["firmware"]["runner_bundled_matches_target_stable"] = True
        self.assertTrue(native_tier0.lock_contract_errors(altered))
        altered = copy.deepcopy(self.lock)
        altered["windows_runner"]["authenticode"]["acceptance_signal"] = True
        self.assertTrue(native_tier0.lock_contract_errors(altered))

    def test_negative_control_register_is_complete_and_ordered(self) -> None:
        controls = native_tier0.negative_controls(self.lock, self.profile)
        self.assertEqual(self.profile["required_negative_controls"], [item["id"] for item in controls])
        self.assertEqual(18, len(controls))
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_rejected_candidates_cannot_equal_accepted_qemu(self) -> None:
        accepted = self.lock["windows_runner"]["qemu_system_x86_64"]["sha256"]
        rejected = {item["id"]: item["sha256"] for item in self.lock["rejected_candidates"]}
        self.assertEqual({"android_qemu", "development_qemu"}, set(rejected))
        self.assertNotIn(accepted, rejected.values())

    def test_buildroot_and_linux_media_paths_are_rejected(self) -> None:
        for path in (
            Path("sources/buildroot-2026.05/rootfs.img"),
            Path("linux-rootfs.img"),
            Path("vmlinuz"),
            Path("boot/bzImage"),
        ):
            with self.subTest(path=path):
                with self.assertRaises(native_tier0.Tier0Error):
                    native_tier0.validate_media_path(path, require_exists=False)

    def test_native_media_name_is_accepted_without_claiming_identity(self) -> None:
        path = native_tier0.validate_media_path(Path("runs/native-tier0/pooleboot-native.img"), require_exists=False)
        self.assertEqual("pooleboot-native.img", path.name)

    def test_run_directory_is_confined(self) -> None:
        accepted = native_tier0.validate_run_directory(ROOT / "runs" / "native-tier0" / "case-001")
        self.assertEqual("case-001", accepted.name)
        for path in (ROOT / "runs" / "escaped", ROOT / "native-tier0", ROOT.parent / "outside"):
            with self.subTest(path=path):
                with self.assertRaises(native_tier0.Tier0Error):
                    native_tier0.validate_run_directory(path)

    def test_external_tool_path_is_rejected(self) -> None:
        with self.assertRaises(native_tier0.Tier0Error):
            native_tier0._require_workspace_tool_path(ROOT.parent / "qemu", ROOT)

    def test_runtime_tree_hash_is_order_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b").write_bytes(b"second")
            (root / "a").write_bytes(b"first")
            first = native_tier0.runtime_tree_binding(root)
            second = native_tier0.runtime_tree_binding(root)
            self.assertEqual(first, second)
            self.assertEqual(2, first["file_count"])

    def test_qmp_summary_ignores_event_timestamps(self) -> None:
        greeting = '{"QMP":{"version":{"qemu":{"major":11,"minor":0,"micro":0},"package":"locked"},"capabilities":[]}}\n'
        first = greeting + '{"return":{}}\n{"timestamp":{"seconds":1},"event":"SHUTDOWN"}\n{"return":{}}\n'
        second = greeting + '{"return":{}}\n{"timestamp":{"seconds":999},"event":"SHUTDOWN"}\n{"return":{}}\n'
        self.assertEqual(native_tier0._qmp_summary(first), native_tier0._qmp_summary(second))

    def test_readiness_passes_bounded_contract(self) -> None:
        self.assertEqual([], native_tier0.readiness_contract_errors(self.readiness))
        self.assertEqual("N4-QEMU-001", self.readiness["selected_move_id"])
        self.assertFalse(self.readiness["n4_exit_gate_satisfied"])
        self.assertTrue(pooleos_release_gate.check_native_tier0_readiness()["ok"])

    def test_readiness_overclaims_fail_closed(self) -> None:
        for key in ("pooleboot_booted", "poolekernel_executed", "secure_boot_enforced", "formal_models_executed"):
            with self.subTest(key=key):
                altered = copy.deepcopy(self.readiness)
                altered["scope"][key] = True
                self.assertTrue(native_tier0.readiness_contract_errors(altered))

    def test_stale_readiness_binding_fails_closed(self) -> None:
        altered = copy.deepcopy(self.readiness)
        altered["bindings"]["lock"]["sha256"] = "0" * 64
        self.assertIn("stale lock binding", native_tier0.readiness_contract_errors(altered))
        altered = copy.deepcopy(self.readiness)
        altered["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        errors = native_tier0.readiness_contract_errors(altered)
        self.assertTrue(any("stale implementation input binding" in item for item in errors))

    def test_readiness_records_real_runtime_closure_without_paths(self) -> None:
        tree = self.readiness["candidate"]["runtime_tree"]
        self.assertEqual(3368, tree["file_count"])
        self.assertEqual(1180772298, tree["byte_count"])
        self.assertEqual("A4CAF423F71E629B839298B35CAE17995865298CF7B29B16C0DD75437B6C0971", tree["tree_sha256"])
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertIsNone(native_tier0.ABSOLUTE_USER_PATH.search(encoded))

    def test_readiness_records_four_paused_probes_and_zero_boot_claims(self) -> None:
        summary = self.readiness["summary"]
        self.assertEqual(4, summary["machine_probe_count"])
        self.assertEqual(4, summary["machine_probe_pass_count"])
        self.assertEqual(0, summary["boot_claim_count"])
        self.assertEqual(0, summary["formal_model_count"])
        for item in self.readiness["profile_checks"]:
            self.assertTrue(item["qmp_summary_exact_match"])
            self.assertFalse(item["guest_cpu_execution_started"])
            self.assertFalse(item["boot_claimed"])

    def test_launch_receipt_schema_rejects_boot_claim(self) -> None:
        receipt = {
            "schema_version": "1.0",
            "artifact_kind": "pooleos_native_tier0_launch_receipt",
            "status_date": "2026-07-16",
            "status": "dry_run_ready",
            "production_ready": False,
            "production_promotion_allowed": False,
            "profile_id": "bootstrap-debug",
            "bindings": {"lock_sha256": "A" * 64, "profile_sha256": "B" * 64, "qemu_sha256": "C" * 64, "firmware_code_sha256": "D" * 64, "vars_template_sha256": "E" * 64},
            "media": {"name": "pooleboot.img", "sha256": "F" * 64, "byte_count": 1, "qemu_read_only": True, "native_identity_verified": False},
            "command": {"normalized": ["$QEMU"], "normalized_sha256": "0" * 64, "debug_overlay_enabled": False, "unknown_arguments_accepted": False},
            "execution": {"requested": False, "started": False, "timed_out": False, "exit_code": None, "run_artifacts": []},
            "claims": {"pooleboot_booted": False, "poolekernel_executed": False, "serial_evidence_validated": False, "debug_exit_validated": False, "secure_boot_enforced": False, "production_boot_evidence": False},
        }
        schema = native_tier0.read_json(ROOT / native_tier0.LAUNCH_SCHEMA_RELATIVE)
        self.assertEqual([], list(validate_json(receipt, schema)))
        receipt["production_ready"] = True
        self.assertTrue(list(validate_json(receipt, schema)))

    def test_launcher_rejects_unknown_arguments(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "run_native_tier0.py"),
                "--profile",
                "bootstrap-debug",
                "--media",
                "missing.img",
                "--run-dir",
                "runs/native-tier0/test",
                "--unknown-option",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(2, completed.returncode)
        self.assertIn("unrecognized arguments", completed.stdout)


if __name__ == "__main__":
    unittest.main()
