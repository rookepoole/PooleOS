import copy
import sys
import unittest
from pathlib import Path


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

    def test_observer_source_has_no_cpu_state_write_instruction(self) -> None:
        audit = self.readiness["build"]["source_audit"]
        self.assertEqual([], audit["forbidden_instruction_hits"])
        self.assertEqual(
            "pass_no_cpu_state_write_instruction", audit["result"]
        )

    def test_target_errata_and_xsave_ownership_remain_open(self) -> None:
        claims = self.readiness["claims"]
        self.assertFalse(claims["target_cpu_qualified"])
        self.assertFalse(claims["microcode_or_errata_policy_complete"])
        self.assertFalse(claims["xsave_context_ownership_complete"])
        self.assertFalse(self.readiness["n7_exit_gate_satisfied"])


if __name__ == "__main__":
    unittest.main()
