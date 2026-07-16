import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import hardware_target  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


def synthetic_capture() -> dict:
    collector_data = (ROOT / hardware_target.COLLECTOR_RELATIVE).read_bytes()
    required_prefixes = json.loads((ROOT / hardware_target.TARGET_RELATIVE).read_text(encoding="utf-8"))["verification_contract"][-1]["expected"]
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_tier1_hardware_private_capture",
        "collected_at_utc": "2026-07-16T00:00:00Z",
        "collection_mode": "read_only",
        "collector": {"version": "1.0.0", "script_sha256": hashlib.sha256(collector_data).hexdigest().upper()},
        "mutation_guard": {
            "firmware_write": False,
            "disk_write": False,
            "tpm_write": False,
            "boot_configuration_write": False,
            "device_configuration_write": False,
            "power_action": False,
            "stress_load": False,
        },
        "privacy_guard": {
            "serial_numbers_collected": False,
            "mac_addresses_collected": False,
            "uuids_collected": False,
            "full_pnp_instance_paths_collected": False,
            "user_or_host_names_collected": False,
            "tpm_ek_or_certificate_material_collected": False,
            "raw_firmware_table_bytes_retained": False,
        },
        "host_context": {
            "architecture": "X64",
            "firmware_type": {"status": "observed", "value": "UEFI"},
            "hypervisor_present": True,
        },
        "security": {
            "secure_boot": {"status": "permission_limited", "value": None, "error_type": "UnauthorizedAccessException"},
            "tpm": {"status": "permission_limited", "present": None, "enabled": None, "activated": None, "error_type": "CimException"},
        },
        "system": {
            "baseboard": [{"manufacturer": "Gigabyte Technology Co., Ltd.", "product": "B650M GAMING PLUS WIFI", "version": "x.x", "serial_number": "PRIVATE-SAMPLE"}],
            "bios": [{"manufacturer": "American Megatrends International, LLC.", "version": "F32", "smbios_version": "3.7", "release_date_utc": "2025-02-05"}],
            "computer_system": [{"hypervisor_present": True, "total_physical_memory_bytes": 17179869184}],
        },
        "processor": [{"name": "AMD Ryzen 7 9800X3D 8-Core Processor", "manufacturer": "AuthenticAMD", "cim_family_code": 107, "cim_stepping": "0", "cim_revision": 17408, "core_count": 8, "logical_processor_count": 16, "socket": "AM5"}],
        "memory": [
            {"manufacturer": "TeamGroup", "part_number": "UD5-6000", "capacity_bytes": 8589934592, "configured_speed_mt_s": 6000},
            {"manufacturer": "TeamGroup", "part_number": "UD5-6000", "capacity_bytes": 8589934592, "configured_speed_mt_s": 6000},
        ],
        "storage": [
            {"model": "CT2000BX500SSD1", "firmware_revision": "M6CR061", "size_bytes": 2000396321280, "interface_type": "IDE"},
            {"model": "Samsung SSD 970 PRO 512GB", "firmware_revision": "1B2QEXP7", "size_bytes": 512105932800, "interface_type": "SCSI"},
        ],
        "display": [{"name": "NVIDIA GeForce RTX 5070", "horizontal_resolution": 2560, "vertical_resolution": 1440}],
        "network": [{"name": "Realtek", "current_link_speed_bps": 1000000000, "mac_address": "00:11:22:33:44:55"}],
        "pnp_devices": [{"name": "required", "class_guid": "not-published", "hardware_prefix": prefix, "status": "OK"} for prefix in required_prefixes],
        "monitor": {"status": "observed", "records": [{"manufacturer": "GSM", "friendly_name": "Display"}], "serial_field_collected": False},
        "firmware_tables": {
            "acpi": {
                "status": "observed",
                "enumerated_signature_count": 2,
                "tables": [
                    {"signature": "IVRS", "byte_count": 128, "sha256": "A" * 64},
                    {"signature": "TPM2", "byte_count": 64, "sha256": "B" * 64},
                ],
                "duplicate_signature_reads_complete": False,
            },
            "smbios": {"status": "observed", "byte_count": 256, "sha256": "C" * 64},
        },
        "sensors_power": {"status": "unavailable", "temperature_probe_count": 0, "battery_count": 0, "ups_count": 0, "active_probe_performed": False},
        "collector_errors": [],
    }


class HardwareTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = hardware_target.read_json(ROOT / hardware_target.POLICY_RELATIVE)
        cls.standards = hardware_target.read_json(ROOT / hardware_target.STANDARDS_RELATIVE)
        cls.target = hardware_target.read_json(ROOT / hardware_target.TARGET_RELATIVE)
        cls.observation = hardware_target.read_json(ROOT / hardware_target.OBSERVATION_RELATIVE)
        cls.readiness = hardware_target.read_json(ROOT / hardware_target.READINESS_RELATIVE)

    def test_public_artifacts_match_all_schemas(self) -> None:
        cases = (
            (self.policy, hardware_target.POLICY_SCHEMA_RELATIVE),
            (self.standards, hardware_target.STANDARDS_SCHEMA_RELATIVE),
            (self.target, hardware_target.TARGET_SCHEMA_RELATIVE),
            (self.observation, hardware_target.OBSERVATION_SCHEMA_RELATIVE),
            (self.readiness, hardware_target.READINESS_SCHEMA_RELATIVE),
        )
        for artifact, schema_relative in cases:
            with self.subTest(schema=schema_relative):
                schema = hardware_target.read_json(ROOT / schema_relative)
                self.assertEqual(validate_json(artifact, schema), [])

    def test_readiness_reproduces_exactly_from_public_inputs(self) -> None:
        rebuilt = hardware_target.build_readiness(ROOT)
        self.assertEqual(hardware_target.canonical_json_bytes(rebuilt), (ROOT / hardware_target.READINESS_RELATIVE).read_bytes())

    def test_every_public_binding_matches_current_bytes(self) -> None:
        for binding in self.readiness["bindings"].values():
            with self.subTest(path=binding["path"]):
                data = (ROOT / binding["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
                self.assertEqual(len(data), binding["byte_count"])

    def test_exact_target_matches_but_n2_remains_open(self) -> None:
        summary = self.readiness["summary"]
        self.assertTrue(summary["consistency_pass"])
        self.assertEqual(summary["matched_required_target_check_count"], 24)
        self.assertEqual(summary["required_target_check_count"], 24)
        self.assertEqual(self.readiness["target_verification"]["required_failure_count"], 0)
        self.assertFalse(self.readiness["n2_exit_gate_satisfied"])
        self.assertFalse(self.readiness["production_promotion_allowed"])
        self.assertEqual(summary["pending_evidence_channel_count"], 7)
        self.assertEqual(summary["pending_lab_safety_count"], 10)
        self.assertGreater(summary["unresolved_standard_count"], 0)

    def test_observation_exposes_hashes_without_private_identifiers(self) -> None:
        self.assertEqual(hardware_target.scan_public_privacy(self.observation), [])
        self.assertFalse(self.observation["bindings"]["private_capture"]["path_recorded"])
        self.assertFalse(self.observation["bindings"]["private_capture"]["content_publication_allowed"])
        self.assertFalse(self.observation["firmware_table_evidence"]["raw_table_bytes_published"])
        self.assertEqual(self.observation["privacy"]["privacy_violation_count"], 0)
        self.assertIn("IVRS", {item["signature"] for item in self.observation["firmware_table_evidence"]["acpi_tables"]})

    def test_whitelist_sanitizer_drops_sensitive_raw_extras(self) -> None:
        capture = synthetic_capture()
        capture_bytes = hardware_target.canonical_json_bytes(capture)
        observation = hardware_target.sanitize_capture(capture, capture_bytes, ROOT)
        encoded = hardware_target.canonical_json_bytes(observation).decode("ascii")
        self.assertNotIn("PRIVATE-SAMPLE", encoded)
        self.assertNotIn("00:11:22:33:44:55", encoded)
        self.assertNotIn('"mac_address":', encoded)
        self.assertNotIn('"serial_number":', encoded)
        self.assertEqual(hardware_target.scan_public_privacy(observation), [])

    def test_sensitive_values_and_instance_paths_fail_privacy_scan(self) -> None:
        cases = (
            ({"serial_number": "sample"}, "prohibited_field"),
            ({"value": "00:11:22:33:44:55"}, "mac_address"),
            ({"value": r"C:\Users\sample\capture.json"}, "absolute_user_path"),
            ({"value": r"PCI\VEN_1234&DEV_5678\INSTANCE"}, "full_pnp_instance"),
        )
        for value, expected_type in cases:
            with self.subTest(expected_type=expected_type):
                self.assertIn(expected_type, {item["type"] for item in hardware_target.scan_public_privacy(value)})

    def test_substitution_and_missing_fact_fail_closed(self) -> None:
        substituted = copy.deepcopy(self.observation)
        substituted["facts"]["baseboard.product"] = "SUBSTITUTED"
        checks = hardware_target.compare_target(self.target, substituted)
        self.assertTrue(any(item["id"] == "HW-ID-BOARD-PRODUCT" and item["status"] == "mismatch" for item in checks))
        missing = copy.deepcopy(self.observation)
        missing["facts"].pop("cpu.name")
        checks = hardware_target.compare_target(self.target, missing)
        self.assertTrue(any(item["id"] == "HW-ID-CPU-NAME" and item["status"] == "missing" for item in checks))

    def test_all_negative_controls_are_real_and_passing(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual(len(controls), 10)
        self.assertTrue(all(item["expected"] == "reject" for item in controls))
        self.assertTrue(all(item["observed"] == "reject" and item["status"] == "pass" for item in controls))

    def test_release_gate_carries_bounded_hardware_readiness(self) -> None:
        check = pooleos_release_gate.check_hardware_target_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("identity=24/24", check["detail"])
        self.assertIn("n2_exit=false", check["detail"])

    def test_support_tiers_and_destructive_boundary_are_fail_closed(self) -> None:
        self.assertEqual([item["ordinal"] for item in self.policy["tiers"]], list(range(7)))
        self.assertEqual(self.policy["default_disposition"]["unlisted_hardware"], "unsupported")
        self.assertFalse(self.policy["destructive_safety"]["current_approval"])
        self.assertEqual({item["status"] for item in self.policy["destructive_safety"]["prerequisites"]}, {"pending"})
        self.assertFalse(self.target["destructive_authorization"]["approved"])

    def test_standards_register_preserves_supersession_and_access_gaps(self) -> None:
        entries = {item["id"]: item for item in self.standards["entries"]}
        self.assertEqual(len(entries), 15)
        self.assertEqual(entries["STD-NVME-BASE"]["lock_status"], "supersession_review_required")
        self.assertIn("2.2", entries["STD-NVME-BASE"]["candidate_revision"])
        self.assertIn("2.3", entries["STD-NVME-BASE"]["candidate_revision"])
        self.assertIn("Committee Specification Draft 01", entries["STD-VIRTIO-1.3-CSD01"]["candidate_revision"])
        self.assertEqual(self.standards["summary"]["artifact_hash_verified_count"], 0)
        self.assertFalse(self.standards["summary"]["n2_standards_exit_ready"])

    def test_collector_contains_no_hardware_mutation_cmdlets(self) -> None:
        source = (ROOT / hardware_target.COLLECTOR_RELATIVE).read_text(encoding="utf-8")
        prohibited = (
            "Clear-Disk",
            "Format-Volume",
            "Initialize-Disk",
            "Restart-Computer",
            "Set-Disk",
            "Set-Partition",
            "Set-SecureBootUEFI",
            "Set-Tpm",
            "Stop-Computer",
        )
        for command in prohibited:
            with self.subTest(command=command):
                self.assertNotIn(command, source)

    def test_private_capture_is_ignored_and_public_ledgers_are_not(self) -> None:
        private = subprocess.run(["git", "check-ignore", "--quiet", "runs/tier1_hardware_capture.private.json"], cwd=ROOT, check=False)
        self.assertEqual(private.returncode, 0)
        for relative in (hardware_target.OBSERVATION_RELATIVE, hardware_target.READINESS_RELATIVE):
            with self.subTest(path=relative):
                public = subprocess.run(["git", "check-ignore", "--quiet", relative], cwd=ROOT, check=False)
                self.assertEqual(public.returncode, 1)


if __name__ == "__main__":
    unittest.main()
