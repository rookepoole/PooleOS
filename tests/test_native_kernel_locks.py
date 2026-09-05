import copy
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from runtime import native_kernel_locks as locks  # noqa: E402
from tools import pooleos_release_gate, qualify_native_kernel_locks  # noqa: E402


class NativeKernelLocksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((ROOT / locks.CONTRACT_RELATIVE).read_text(encoding="utf-8"))
        cls.readiness = json.loads((ROOT / locks.READINESS_RELATIVE).read_text(encoding="utf-8"))

    def test_contract_is_canonical(self) -> None:
        self.assertEqual(locks.contract_errors(self.contract, ROOT), [])

    def test_readiness_is_bound_to_every_input(self) -> None:
        self.assertEqual(locks.readiness_errors(self.readiness, ROOT), [])

    def test_claims_preserve_n12_and_production_boundaries(self) -> None:
        self.assertEqual(self.contract["claims"], locks.expected_claims())
        self.assertTrue(self.readiness["flag_n12_concurrency_locks_001_closed"])
        self.assertEqual(self.readiness["phase_status"], {"N12": "partial", "N12.2": "complete"})
        self.assertFalse(self.readiness["n12_exit_gate_satisfied"])
        self.assertFalse(self.readiness["claims"]["deferred_reclamation_implemented"])
        self.assertFalse(self.readiness["claims"]["general_smp_or_hotplug_implemented"])
        self.assertFalse(self.readiness["production_ready"])

    def test_host_probe_receipts_remain_exact(self) -> None:
        probe = self.readiness["build"]["host_probe"]
        parsed = locks.parse_probe_output("\n".join(probe["lines"]) + "\n")
        self.assertEqual(parsed["receipt_count"], 9)
        self.assertEqual(parsed["ticket_acquisitions"], 8192)
        self.assertEqual(parsed["maximum_mutex_bypass"], 7)
        self.assertEqual(parsed["reader_writer_rounds"], 1024)
        self.assertEqual(parsed["sequence_rounds"], 2048)

    def test_both_exact_four_vcpu_transcripts_validate(self) -> None:
        execution = self.readiness["execution"]
        self.assertEqual(execution["virtual_cpu_count"], 4)
        self.assertEqual(execution["application_processor_count"], 3)
        self.assertEqual(execution["markers_per_run"], 35)
        self.assertEqual(len(execution["runs"]), 2)
        for run in execution["runs"]:
            observation = locks.validate_markers(run["markers"])
            self.assertEqual(observation["live"]["tickets"], [0, 1, 2, 3])
            self.assertEqual(observation["live"]["acquisitions"], 4)
            self.assertEqual(observation["live"]["mappings_installed"], 3)
            self.assertEqual(observation["live"]["mappings_revoked"], 3)

    def test_qemu_evidence_is_repeatable_and_nonphysical(self) -> None:
        execution = self.readiness["execution"]
        self.assertTrue(execution["fresh_vars_each_run"])
        self.assertTrue(execution["exact_marker_match"])
        self.assertTrue(execution["exact_screenshot_match"])
        self.assertTrue(execution["exact_pbp1_match"])
        self.assertFalse(self.readiness["media"]["physical_media_write_performed"])

    def test_source_audit_covers_lock_and_live_paths(self) -> None:
        audit, _ = qualify_native_kernel_locks._source_audit()
        self.assertEqual(audit["heap_api_token_count"], 0)
        self.assertEqual(audit["lock_primitive_count"], 6)
        self.assertEqual(audit["rank_class_count"], 5)
        self.assertEqual(audit["focused_unit_test_count"], 10)
        self.assertEqual(audit["live_locked_instruction_class_count"], 5)

    def test_all_hostile_controls_are_present_in_order(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual([item["id"] for item in controls], list(locks.NEGATIVE_CONTROL_IDS))
        self.assertTrue(all(item["status"] == "pass" and item["case_count"] >= 1 for item in controls))

    def test_marker_validator_rejects_live_and_production_drift(self) -> None:
        markers = self.readiness["execution"]["runs"][0]["markers"]
        for old, new in (("tickets=0,1,2,3", "tickets=0,1,1,3"), ("production=0", "production=1")):
            hostile = markers.copy()
            hostile[-3 if old.startswith("tickets") else -1] = hostile[
                -3 if old.startswith("tickets") else -1
            ].replace(old, new)
            with self.assertRaises(locks.KernelLocksError):
                locks.validate_markers(hostile)

    def test_probe_parser_rejects_fairness_and_rollback_drift(self) -> None:
        lines = self.readiness["build"]["host_probe"]["lines"]
        for index, old, new in (
            (3, "maximum_bypass=7", "maximum_bypass=8"),
            (8, "serving=2", "serving=1"),
        ):
            hostile = lines.copy()
            hostile[index] = hostile[index].replace(old, new)
            with self.assertRaises(locks.KernelLocksError):
                locks.parse_probe_output("\n".join(hostile) + "\n")

    def test_contract_and_input_binding_fail_closed(self) -> None:
        hostile = copy.deepcopy(self.contract)
        hostile["claims"]["production_ready"] = True
        self.assertIn("claim boundary diverges", locks.contract_errors(hostile, ROOT))
        with self.assertRaises(locks.KernelLocksError):
            locks.file_binding(ROOT, "../escape")

    def test_release_gate_accepts_only_the_bounded_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_locks_readiness()
        self.assertTrue(check["ok"], check["detail"])
        gate_source = (ROOT / "tools/pooleos_release_gate.py").read_text(encoding="utf-8")
        self.assertIn("args.native_kernel_locks_readiness,", gate_source)
        self.assertIn("kernel_tests=214/214", check["detail"])
        self.assertIn("controls=30/30", check["detail"])
        self.assertIn("reclamation=false", check["detail"])
        self.assertIn("production_ready=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
