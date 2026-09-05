import copy
import importlib
import json
import unittest
from unittest.mock import patch

from tools import pooleos_release_gate as gate


PROFILES = (
    "interrupt_time", "smp_first_ap", "smp_percpu_runtime", "smp_ipi",
    "scheduler", "scheduler_preempt", "scheduler_deferred", "scheduler_smp",
    "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks",
)


class NativeDependencyReleaseBoundaryTests(unittest.TestCase):
    def test_current_receipts_pass_and_production_overclaims_fail(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                module = importlib.import_module("runtime.native_kernel_" + profile)
                path = gate.ROOT / module.READINESS_RELATIVE
                if not path.is_file():
                    self.skipTest("native readiness must be generated first")
                check_name = "scheduler_preemption" if profile == "scheduler_preempt" else profile
                check = getattr(gate, "check_native_kernel_" + check_name + "_readiness")
                accepted = check(path)
                self.assertTrue(accepted["ok"], accepted["detail"])
                candidate = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
                candidate["production_ready"] = True
                with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                    rejected = check(path)
                self.assertFalse(rejected["ok"])
                self.assertIsInstance(rejected["detail"], str)
                self.assertIn("production", rejected["detail"])

    def test_schema_error_objects_are_reported_without_a_formatting_crash(self):
        for profile in ("interrupt_time", "smp_first_ap", "smp_percpu_runtime"):
            with self.subTest(profile=profile):
                module = importlib.import_module("runtime.native_kernel_" + profile)
                path = gate.ROOT / module.READINESS_RELATIVE
                if not path.is_file():
                    self.skipTest("native readiness must be generated first")
                candidate = json.loads(path.read_text(encoding="utf-8"))
                candidate["schema_version"] = "invalid"
                check = getattr(gate, "check_native_kernel_" + profile + "_readiness")
                with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                    rejected = check(path)
                self.assertFalse(rejected["ok"])
                self.assertIn("schema_version", rejected["detail"])


if __name__ == "__main__":
    unittest.main()
