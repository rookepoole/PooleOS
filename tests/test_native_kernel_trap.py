import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_kernel_trap  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeKernelTrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = native_kernel_trap.read_json(ROOT / native_kernel_trap.CONTRACT_RELATIVE)
        cls.readiness = native_kernel_trap.read_json(ROOT / native_kernel_trap.READINESS_RELATIVE)
        cls.scenarios = {
            item["scenario"]: item for item in cls.readiness["execution"]["scenarios"]
        }

    def test_contract_and_generated_readiness_are_current(self) -> None:
        self.assertEqual([], native_kernel_trap.contract_errors(self.contract))
        self.assertEqual([], native_kernel_trap.readiness_errors(self.readiness, ROOT))
        release_check = pooleos_release_gate.check_native_kernel_trap_readiness()
        self.assertTrue(release_check["ok"], release_check["detail"])

    def test_all_scenario_marker_sequences_are_cross_bound(self) -> None:
        for scenario, profile in native_kernel_trap.SCENARIOS.items():
            with self.subTest(scenario=scenario):
                markers = self.scenarios[scenario]["runs"][0]["markers"]
                summary = native_kernel_trap.validate_markers(markers, scenario)
                self.assertEqual(profile["selector"], summary["selector"])
                self.assertEqual(profile["marker_count"], summary["marker_count"])
                self.assertTrue(summary["ordered_contract_match"])

    def test_selector_setup_and_terminal_mutations_reject(self) -> None:
        for scenario, profile in native_kernel_trap.SCENARIOS.items():
            markers = self.scenarios[scenario]["runs"][0]["markers"]
            candidates = []
            selector = copy.deepcopy(markers)
            selector[23] = selector[23].replace(
                f"trap_scenario={profile['selector']}", "trap_scenario=0"
            )
            candidates.append(selector)
            setup = copy.deepcopy(markers)
            setup[29] = setup[29].replace("gdt_limit=39", "gdt_limit=40")
            candidates.append(setup)
            terminal = copy.deepcopy(markers)
            terminal[-1] = terminal[-1].replace("terminal=halt", "terminal=return")
            candidates.append(terminal)
            for candidate in candidates:
                with self.subTest(scenario=scenario, marker=candidate[-1]):
                    with self.assertRaises(native_kernel_trap.KernelTrapError):
                        native_kernel_trap.validate_markers(candidate, scenario)

    def test_returning_sequence_proves_three_exact_resumes(self) -> None:
        markers = self.scenarios["returning"]["runs"][0]["markers"]
        summary = native_kernel_trap.validate_markers(markers, "returning")
        self.assertEqual([3, 6, 14], [item["vector"] for item in summary["result"]["entries"]])
        self.assertEqual(3, summary["result"]["returned"])

    def test_double_fault_uses_separate_ist_and_is_terminal(self) -> None:
        markers = self.scenarios["double_fault"]["runs"][0]["markers"]
        summary = native_kernel_trap.validate_markers(markers, "double_fault")
        self.assertEqual(8, summary["result"]["entries"][0]["vector"])
        self.assertEqual(2, summary["result"]["entries"][0]["ist"])
        self.assertEqual("halt", summary["result"]["terminal"])

    def test_malformed_control_is_explicitly_synthetic(self) -> None:
        markers = self.scenarios["malformed_frame"]["runs"][0]["markers"]
        summary = native_kernel_trap.validate_markers(markers, "malformed_frame")
        self.assertEqual(1, summary["result"]["rejected"])
        self.assertIn("source=synthetic_semantic", markers[32])
        self.assertFalse(self.readiness["claims"]["all_256_vectors_installed"])

    def test_exact_hostile_control_set_passes(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual(list(native_kernel_trap.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertTrue(all(item["status"] == "pass" for item in controls))


if __name__ == "__main__":
    unittest.main()
