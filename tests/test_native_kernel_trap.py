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
        execution = self.readiness["execution"]
        self.assertEqual([], native_kernel_trap.recorded_execution_errors(execution))
        cases = [("execution_null", None), ("scenarios_null", {"scenarios": None})]
        changed = copy.deepcopy(execution)
        changed["scenarios"][0] = None
        cases.append(("scenario_null", changed))
        for field, value in (("scenario", "returning"), ("selector", 1), ("run_count", "2")):
            changed = copy.deepcopy(execution)
            changed["scenarios"][1][field] = value
            cases.append((field, changed))
        for count in (0, 1):
            changed = copy.deepcopy(execution)
            changed["scenarios"][0]["runs"] = changed["scenarios"][0]["runs"][:count]
            cases.append((f"run_count_{count}", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["selector"] = True
        cases.append(("boolean_selector", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][0] = None
        cases.append(("run_null", changed))
        for field, value in (
            ("run_id", "returning-run-1"),
            ("marker_sha256", "0" * 64),
            ("markers", None),
            ("transcript_binding", {}),
            ("serial_debugcon_exact_match", False),
            ("pbp1_serial_debugcon_exact_match", False),
        ):
            changed = copy.deepcopy(execution)
            changed["scenarios"][0]["runs"][1][field] = value
            cases.append((field, changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["markers"][-1] += " altered"
        cases.append(("altered_markers", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["marker_summary"]["result"]["returned"] = 4
        cases.append(("altered_summary", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["pbp1_transcript"]["core"]["page_table_root_physical"] = "0"
        cases.append(("altered_handoff", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["pbp1_transcript"]["core"] = None
        cases.append(("handoff_core_null", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["independent_kernel_revalidation"]["parser_count"] = 8
        cases.append(("altered_oracle", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["independent_kernel_revalidation"]["contract_id"] = "wrong"
        cases.append(("altered_oracle_contract", changed))
        changed = copy.deepcopy(execution)
        changed["scenarios"][0]["runs"][1]["screenshot"]["sha256"] = "0" * 64
        cases.append(("two_run_frame_mismatch", changed))
        for name, value in (("both_frames_missing", None), ("both_frames_empty", {})):
            changed = copy.deepcopy(execution)
            for run in changed["scenarios"][0]["runs"]:
                run["screenshot"] = value
            cases.append((name, changed))
        for name, changed in cases:
            with self.subTest(control=name):
                self.assertTrue(native_kernel_trap.recorded_execution_errors(changed))
        changed_readiness = copy.deepcopy(self.readiness)
        changed_readiness["execution"]["scenarios"][0]["runs"] = []
        self.assertIn(
            "PKTRAP1 returning recorded run coverage changed",
            native_kernel_trap.readiness_errors(changed_readiness, ROOT),
        )


if __name__ == "__main__":
    unittest.main()
