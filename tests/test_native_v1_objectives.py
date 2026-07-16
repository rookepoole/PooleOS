import copy
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_v1_objectives  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import generate_native_v1_objectives_readiness  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeV1ObjectivesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.objectives = native_v1_objectives.read_json(ROOT / native_v1_objectives.OBJECTIVES_RELATIVE)
        cls.objectives_schema = native_v1_objectives.read_json(
            ROOT / native_v1_objectives.OBJECTIVES_SCHEMA_RELATIVE
        )
        cls.readiness_path = ROOT / native_v1_objectives.READINESS_RELATIVE
        cls.readiness = native_v1_objectives.read_json(cls.readiness_path)
        cls.readiness_schema = native_v1_objectives.read_json(
            ROOT / native_v1_objectives.READINESS_SCHEMA_RELATIVE
        )
        cls.targets = {target["id"]: target for target in cls.objectives["targets"]}

    def test_objectives_and_readiness_match_schemas(self) -> None:
        self.assertEqual(validate_json(self.objectives, self.objectives_schema), [])
        self.assertEqual(validate_json(self.readiness, self.readiness_schema), [])
        self.assertEqual(native_v1_objectives.semantic_violations(self.objectives), [])

    def test_target_families_are_complete_and_unique(self) -> None:
        targets = self.objectives["targets"]
        self.assertEqual(len(targets), 38)
        self.assertEqual(len({target["id"] for target in targets}), 38)
        self.assertEqual(Counter(target["category"] for target in targets), Counter(native_v1_objectives.EXPECTED_CATEGORY_COUNTS))

    def test_every_target_is_measurable_but_unmeasured(self) -> None:
        for target in self.objectives["targets"]:
            self.assertGreaterEqual(target["minimum_sample_count"], 1, target["id"])
            self.assertGreaterEqual(target["minimum_duration_hours"], 0, target["id"])
            self.assertGreaterEqual(target["percentile"], 0, target["id"])
            self.assertLessEqual(target["percentile"], 100, target["id"])
            self.assertTrue(target["evidence_phase_ids"], target["id"])
            self.assertEqual(target["definition_status"], "owner_direction_accepted_signature_pending")
            self.assertEqual(target["evidence_status"], "not_measured")

    def test_profile_scope_and_modes_are_exact(self) -> None:
        profile = self.objectives["release_profile"]
        self.assertEqual(profile["edition"], "PooleOS Workstation")
        self.assertEqual(set(profile["required_modes"]), native_v1_objectives.EXPECTED_MODES)
        self.assertEqual(len(profile["support_profiles"]), 2)
        self.assertIn("windows_binary_or_driver_compatibility", profile["excluded_product_claims"])
        self.assertIn("linux_binary_kernel_module_or_driver_compatibility", profile["excluded_product_claims"])

    def test_privacy_defaults_fail_closed(self) -> None:
        for target_id in (
            "PRIV-TELEMETRY-DEFAULT-001",
            "PRIV-PRECONSENT-NETWORK-001",
            "PRIV-STABLE-ID-001",
            "PRIV-DIAGNOSTIC-REDACTION-001",
            "PRIV-CRASH-UPLOAD-001",
        ):
            target = self.targets[target_id]
            self.assertEqual(target["operator"], "maximum")
            self.assertEqual(target["value"], 0)

    def test_compatibility_does_not_reintroduce_host_abis(self) -> None:
        policy = self.objectives["compatibility_policy"]
        self.assertEqual(policy["linux_abi"], "prohibited_v1")
        self.assertEqual(policy["linux_kernel_modules"], "prohibited_v1")
        self.assertEqual(policy["windows_application_abi"], "prohibited_v1")
        self.assertEqual(policy["windows_drivers"], "prohibited_v1")
        self.assertEqual(policy["unknown_major_versions"], "reject")
        self.assertEqual(self.targets["COMP-LINUX-ABI-001"]["value"], 0)
        self.assertEqual(self.targets["COMP-WINDOWS-ABI-001"]["value"], 0)

    def test_accessibility_covers_normal_installer_and_recovery(self) -> None:
        self.assertEqual(self.targets["ACC-WCAG-AA-001"]["value"], 100)
        self.assertEqual(self.targets["ACC-KEYBOARD-001"]["value"], 100)
        recovery = self.targets["ACC-RECOVERY-001"]
        self.assertEqual(recovery["value"], 100)
        self.assertIn("recovery", recovery["applies_to"])
        self.assertIn("serial", recovery["metric"])
        self.assertEqual(self.targets["ACC-REDUCED-MOTION-001"]["value"], 100)

    def test_reliability_targets_retain_failure_and_recovery_scope(self) -> None:
        self.assertEqual(self.targets["REL-T0-BOOT-001"]["minimum_sample_count"], 10000)
        self.assertEqual(self.targets["REL-T1-BOOT-001"]["minimum_sample_count"], 1000)
        self.assertEqual(self.targets["REL-SOAK-001"]["minimum_duration_hours"], 168)
        self.assertEqual(self.targets["REL-FS-POWER-001"]["minimum_sample_count"], 10000)
        self.assertEqual(self.targets["REL-RECOVERY-RTO-001"]["value"], 900)

    def test_performance_targets_define_percentiles_and_power_boundary(self) -> None:
        self.assertEqual(self.targets["PERF-FRAME-P95-001"]["percentile"], 95)
        self.assertEqual(self.targets["PERF-FRAME-P99-001"]["percentile"], 99)
        self.assertEqual(self.targets["PERF-INPUT-LATENCY-001"]["value"], 50)
        self.assertIn("external instrumentation", self.targets["PERF-POWER-REGRESSION-001"]["evidence_requirement"])
        self.assertEqual(self.targets["PERF-IPC-001"]["minimum_sample_count"], 1000000)

    def test_all_negative_controls_are_real_and_passing(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual(len(controls), 10)
        self.assertEqual(len({control["id"] for control in controls}), 10)
        self.assertTrue(all(control["status"] == "pass" for control in controls))

        promoted = copy.deepcopy(self.objectives)
        promoted["production_promotion_allowed"] = True
        self.assertTrue(native_v1_objectives.rejection_reasons(promoted))
        regressed = copy.deepcopy(self.objectives)
        regressed["owner_ratification"]["profile_accepted"] = False
        self.assertTrue(native_v1_objectives.rejection_reasons(regressed))

    def test_readiness_reproduces_exactly(self) -> None:
        self.assertEqual(
            self.readiness_path.read_bytes(),
            native_v1_objectives.canonical_json_bytes(native_v1_objectives.build_readiness(ROOT)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "readiness.json"
            self.assertEqual(generate_native_v1_objectives_readiness.main(["--out", str(out)]), 0)
            self.assertEqual(out.read_bytes(), self.readiness_path.read_bytes())

    def test_public_bindings_match_current_bytes(self) -> None:
        for binding in self.readiness["bindings"].values():
            data = (ROOT / binding["path"]).read_bytes()
            self.assertEqual(native_v1_objectives.sha256_bytes(data), binding["sha256"])
            self.assertEqual(len(data), binding["byte_count"])

    def test_owner_boundary_and_n0_exit_remain_open(self) -> None:
        owner = self.readiness["owner_boundary"]
        self.assertTrue(owner["ratification_required"])
        self.assertFalse(owner["ready_for_owner_review"])
        self.assertTrue(owner["profile_accepted"])
        self.assertTrue(owner["target_values_accepted"])
        self.assertFalse(owner["cryptographic_signature_present"])
        self.assertFalse(owner["ready_for_signature"])
        self.assertFalse(self.readiness["n0_6_exit_gate_satisfied"])
        self.assertFalse(self.readiness["production_promotion_allowed"])

    def test_release_gate_carries_non_promoting_objectives(self) -> None:
        check = pooleos_release_gate.check_native_v1_objectives_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("targets=38", check["detail"])
        self.assertIn("measured=0", check["detail"])
        self.assertIn("owner_direction=true", check["detail"])


if __name__ == "__main__":
    unittest.main()
