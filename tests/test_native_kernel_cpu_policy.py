import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_kernel_cpu_policy  # noqa: E402
from tools import qualify_native_kernel_cpu_policy  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeKernelCpuPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = native_kernel_cpu_policy.read_json(
            ROOT / native_kernel_cpu_policy.CONTRACT_RELATIVE
        )
        cls.readiness = native_kernel_cpu_policy.read_json(
            ROOT / native_kernel_cpu_policy.READINESS_RELATIVE
        )
        cls.markers = cls.readiness["execution"]["runs"][0]["markers"]

    def test_contract_and_generated_readiness_are_current(self) -> None:
        self.assertEqual([], native_kernel_cpu_policy.contract_errors(self.contract))
        self.assertEqual(
            [], native_kernel_cpu_policy.readiness_errors(self.readiness, ROOT)
        )
        release_check = pooleos_release_gate.check_native_kernel_cpu_policy_readiness()
        self.assertTrue(release_check["ok"], release_check["detail"])

    def test_live_markers_cross_bind_identity_features_and_state(self) -> None:
        summary = native_kernel_cpu_policy.validate_markers(self.markers)
        self.assertEqual(4, summary["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(
            (
                summary["discovery"]["family"],
                summary["discovery"]["model"],
                summary["discovery"]["stepping"],
            ),
            native_kernel_cpu_policy._decode_identity(
                summary["discovery"]["signature"]
            ),
        )
        self.assertEqual(0x1F, summary["state"]["msr_read_mask"])
        self.assertEqual(0, summary["result"]["writes"])

    def test_amd_extended_family_model_decode_matches_target_shape(self) -> None:
        self.assertEqual(
            (0x1A, 0x44, 0),
            native_kernel_cpu_policy._decode_identity(0x00B40F40),
        )

    def test_structural_and_policy_mutations_reject(self) -> None:
        candidates = [self.markers[:-1]]
        selector = copy.deepcopy(self.markers)
        selector[23] = selector[23].replace("trap_scenario=4", "trap_scenario=0")
        candidates.append(selector)
        write = copy.deepcopy(self.markers)
        write[-1] = write[-1].replace("writes=0", "writes=1")
        candidates.append(write)
        missing_nx = copy.deepcopy(self.markers)
        state = native_kernel_cpu_policy.validate_markers(self.markers)["state"]
        missing_nx[33] = qualify_native_kernel_cpu_policy._set_field(
            missing_nx[33], "efer", qualify_native_kernel_cpu_policy._hex(state["efer"] & ~(1 << 11))
        )
        candidates.append(missing_nx)
        for candidate in candidates:
            with self.subTest(marker_count=len(candidate)):
                with self.assertRaises(native_kernel_cpu_policy.KernelCpuPolicyError):
                    native_kernel_cpu_policy.validate_markers(candidate)

    def test_exact_hostile_control_set_passes(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual(
            list(native_kernel_cpu_policy.NEGATIVE_CONTROL_IDS),
            [item["id"] for item in controls],
        )
        self.assertTrue(all(item["status"] == "pass" for item in controls))
        execution = self.readiness["execution"]
        self.assertEqual([], native_kernel_cpu_policy.recorded_execution_errors(execution))
        cases = [("execution_null", None), ("execution_empty", {})]
        for name, runs in (
            ("runs_null", None), ("runs_empty", []),
            ("one_run", execution["runs"][:1]), ("empty_run_records", [{}, {}]),
            ("run_null", [None, execution["runs"][1]]),
        ):
            changed = copy.deepcopy(execution)
            changed["runs"] = runs
            cases.append((name, changed))
        changed = copy.deepcopy(execution)
        changed["runs"][1]["run_id"] = changed["runs"][0]["run_id"]
        cases.append(("duplicate_run_id", changed))
        for field, value in (
            ("run_count", "2"), ("exact_marker_match", 1),
            ("exact_screenshot_match", False), ("exact_pbp1_match", False),
            ("observation", {}),
        ):
            changed = copy.deepcopy(execution)
            changed[field] = value
            cases.append((field, changed))
        for field, value in (
            ("markers", None), ("marker_sha256", "0" * 64), ("marker_summary", {}),
            ("transcript_binding", {}), ("pbp1_transcript", None),
            ("independent_kernel_revalidation", {}), ("screenshot", None),
            ("serial_debugcon_exact_match", False), ("pbp1_serial_debugcon_exact_match", False),
        ):
            changed = copy.deepcopy(execution)
            changed["runs"][1][field] = value
            cases.append((field, changed))
        changed = copy.deepcopy(execution)
        changed["runs"][1]["markers"][-1] += " altered"
        cases.append(("altered_marker", changed))
        changed = copy.deepcopy(execution)
        changed["observation"]["discovery"]["family"] = 99
        cases.append(("changed_observation", changed))
        changed = copy.deepcopy(execution)
        changed["runs"][1]["pbp1_transcript"]["core"] = None
        cases.append(("handoff_core_null", changed))
        changed = copy.deepcopy(execution)
        changed["runs"][1]["independent_kernel_revalidation"]["parser_count"] = 8
        cases.append(("altered_oracle", changed))
        changed = copy.deepcopy(execution)
        changed["runs"][1]["screenshot"]["sha256"] = "0" * 64
        cases.append(("mismatched_frame", changed))
        changed = copy.deepcopy(execution)
        for run in changed["runs"]:
            run["screenshot"] = {}
        cases.append(("both_frames_missing", changed))
        self.assertEqual(28, len(cases))
        for name, changed in cases:
            with self.subTest(receipt_control=name):
                self.assertTrue(native_kernel_cpu_policy.recorded_execution_errors(changed))
        changed = copy.deepcopy(self.readiness)
        changed["execution"]["runs"] = [{}, {}]
        self.assertIn(
            "PKCPU1 recorded run coverage changed",
            native_kernel_cpu_policy.readiness_errors(changed, ROOT),
        )
        gate_cases = []
        for field in ("production_ready", "production_promotion_allowed", "n7_exit_gate_satisfied"):
            changed = copy.deepcopy(self.readiness)
            changed[field] = True
            gate_cases.append((field, changed))
        for field, value in (
            ("cpuid_family", 99), ("physical_width", 63), ("msr_read_count", 0),
            ("signature_verifications", 1), ("actions_authorized", 1),
        ):
            changed = copy.deepcopy(self.readiness)
            changed["summary"][field] = value
            gate_cases.append((field, changed))
        self.assertEqual(8, len(gate_cases))
        for name, changed in gate_cases:
            with self.subTest(gate_control=name), patch.object(
                pooleos_release_gate, "_load_schema_artifact", return_value=(changed, [])
            ):
                self.assertTrue(native_kernel_cpu_policy.readiness_errors(changed, ROOT))
                self.assertFalse(pooleos_release_gate.check_native_kernel_cpu_policy_readiness()["ok"])

    def test_observer_source_has_no_cpu_state_write_instruction(self) -> None:
        audit = self.readiness["build"]["source_audit"]
        self.assertEqual([], audit["forbidden_instruction_hits"])
        self.assertEqual(
            "pass_no_cpu_state_write_instruction", audit["result"]
        )
        source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        hostile = source.replace(
            "// SAFETY: PKCPU1 calls this only at CPL0 after PKXFER1; the instruction is read-only.",
            '// SAFETY: hostile source-audit fixture.\n    unsafe { asm!("mov cr4, rax") };',
            1,
        )
        with self.assertRaises(qualify_native_kernel_cpu_policy.QualificationError):
            qualify_native_kernel_cpu_policy._audit_source_text(hostile)

    def test_target_errata_and_xsave_ownership_remain_open(self) -> None:
        claims = self.readiness["claims"]
        self.assertFalse(claims["target_cpu_qualified"])
        self.assertFalse(claims["microcode_or_errata_policy_complete"])
        self.assertFalse(claims["xsave_context_ownership_complete"])
        self.assertFalse(self.readiness["n7_exit_gate_satisfied"])


if __name__ == "__main__":
    unittest.main()
