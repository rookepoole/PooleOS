from __future__ import annotations

import copy
import json
import unittest

from runtime import native_kernel_xstate_policy as xstate


class NativeKernelXstatePolicyTests(unittest.TestCase):
    @staticmethod
    def markers() -> list[str]:
        readiness = json.loads(
            (xstate.ROOT / "runs/native-kernel-cpu-policy-readiness.json").read_text(
                encoding="utf-8"
            )
        )
        markers = list(readiness["execution"]["runs"][0]["markers"][:29])
        markers[23] = markers[23].replace("trap_scenario=4", "trap_scenario=5")
        markers[25] = markers[25].replace(
            "PKBUILD1-CYCLE122-N7-XSTATE-POLICY-001",
            "PKBUILD1-CYCLE129-N9-PMM-METADATA-001",
        )
        markers.extend(
            [
                "POOLEOS:KERNEL:XSTATE-CAPABILITY PASS contract=PKXSTATE1 "
                "leaf1_ecx=0x000000000C000000 leaf1_edx=0x0000000007000001 "
                "supported_xcr0=0x0000000000000003 leafd1_eax=0x0000000000000001 "
                "enabled_bytes=576 maximum_bytes=576",
                "POOLEOS:KERNEL:XSTATE-CONFIG PASS contract=PKXSTATE1 "
                "cr0_before=0x0000000080010033 cr0_after=0x0000000080010033 "
                "cr4_before=0x0000000000040668 cr4_after=0x0000000000040668 "
                "xcr0_before=0x0000000000000003 xcr0_after=0x0000000000000003 "
                "xss=0x0000000000000000 strategy=eager format=standard area_bytes=4096 alignment=64",
                "POOLEOS:KERNEL:XSTATE-INIT PASS contract=PKXSTATE1 "
                "fcw=0x000000000000037F mxcsr=0x0000000000001F80 "
                "mxcsr_mask_raw=0x000000000000FFFF mxcsr_mask_effective=0x000000000000FFFF "
                "exceptions=masked nm_policy=unexpected_fail_closed",
                "POOLEOS:KERNEL:XSTATE-SWITCH PASS contract=PKXSTATE1 owners=10,11 "
                "saves=2 restores=4 xstate_bv_a=0x0000000000000002 "
                "xstate_bv_b=0x0000000000000002 match_a=1 match_b=1 scheduler_lock=1 "
                "interrupts=0 same_cpu=1 kernel_simd=0",
                "POOLEOS:KERNEL:XSTATE-CLEAR PASS contract=PKXSTATE1 "
                "canonical_xmm0_zero=1 image_zero_bytes=8192 unexpected_nm=0 "
                "all_selected_components=canonical_image kernel_simd_policy=forbidden",
                "POOLEOS:KERNEL:XSTATE-RESULT PASS contract=PKXSTATE1 "
                "profile=epyc_rome_v4_x87_sse bsp=1 writes=3 signatures=0 authority=0 "
                "actions=0 scheduler=0 smp=0 target=0 terminal=halt",
            ]
        )
        return markers

    def test_contract_and_schema_are_frozen(self) -> None:
        contract = xstate.read_json(xstate.ROOT / xstate.CONTRACT_RELATIVE)
        self.assertEqual(xstate.contract_errors(contract), [])
        schema = xstate.read_json(xstate.ROOT / xstate.CONTRACT_SCHEMA_RELATIVE)
        self.assertEqual(schema["properties"]["contract_id"]["const"], "PKXSTATE1")
        changed = copy.deepcopy(contract)
        changed["authority_gate"]["privileged_configuration_writes"] = 4
        self.assertIn("PKXSTATE1 authority boundary changed", xstate.contract_errors(changed))

    def test_accepts_bounded_xstate_receipt(self) -> None:
        summary = xstate.validate_markers(self.markers())
        self.assertEqual(summary["config"]["xcr0_after"], 3)
        self.assertEqual(summary["switch"]["restores"], 4)
        self.assertEqual(summary["clear"]["image_zero_bytes"], 8192)
        self.assertEqual(summary["result"]["writes"], 3)

    def test_rejects_marker_shape_selector_and_order(self) -> None:
        markers = self.markers()
        for candidate in (markers[:-1], [*markers, markers[-1]]):
            with self.assertRaises(xstate.KernelXstatePolicyError):
                xstate.validate_markers(candidate)
        candidate = markers.copy()
        candidate[29], candidate[30] = candidate[30], candidate[29]
        with self.assertRaises(xstate.KernelXstatePolicyError):
            xstate.validate_markers(candidate)
        candidate = markers.copy()
        candidate[23] = candidate[23].replace("trap_scenario=5", "trap_scenario=4")
        with self.assertRaises(xstate.KernelXstatePolicyError):
            xstate.validate_markers(candidate)

    def test_rejects_feature_control_and_supervisor_faults(self) -> None:
        mutations = (
            (29, "leaf1_ecx=0x000000000C000000", "leaf1_ecx=0x0000000008000000"),
            (29, "leafd1_eax=0x0000000000000001", "leafd1_eax=0x0000000000000011"),
            (30, "cr0_after=0x0000000080010033", "cr0_after=0x000000008001003B"),
            (30, "xcr0_after=0x0000000000000003", "xcr0_after=0x0000000000000001"),
            (30, "xss=0x0000000000000000", "xss=0x0000000000000001"),
        )
        for index, old, new in mutations:
            candidate = self.markers()
            candidate[index] = candidate[index].replace(old, new)
            with self.assertRaises(xstate.KernelXstatePolicyError):
                xstate.validate_markers(candidate)

    def test_rejects_context_clear_and_claim_faults(self) -> None:
        mutations = (
            (31, "fcw=0x000000000000037F", "fcw=0x000000000000027F"),
            (32, "match_b=1", "match_b=0"),
            (32, "kernel_simd=0", "kernel_simd=1"),
            (33, "image_zero_bytes=8192", "image_zero_bytes=4096"),
            (33, "unexpected_nm=0", "unexpected_nm=1"),
            (34, "scheduler=0", "scheduler=1"),
            (34, "target=0", "target=1"),
        )
        for index, old, new in mutations:
            candidate = self.markers()
            candidate[index] = candidate[index].replace(old, new)
            with self.assertRaises(xstate.KernelXstatePolicyError):
                xstate.validate_markers(candidate)

    def test_claim_boundary_rejects_promotion(self) -> None:
        contract = xstate.read_json(xstate.ROOT / xstate.CONTRACT_RELATIVE)
        promoted = copy.deepcopy(contract)
        promoted["claims"]["production_ready"] = True
        self.assertIn("PKXSTATE1 claim boundary changed", xstate.contract_errors(promoted))


if __name__ == "__main__":
    unittest.main()
