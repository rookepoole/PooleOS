from __future__ import annotations

import copy
import json
import unittest

from runtime import native_kernel_xstate_exception as xstate_exception


class NativeKernelXstateExceptionTests(unittest.TestCase):
    @staticmethod
    def markers() -> list[str]:
        readiness = json.loads(
            (
                xstate_exception.ROOT
                / "runs/native-kernel-cpu-policy-readiness.json"
            ).read_text(encoding="utf-8")
        )
        markers = list(readiness["execution"]["runs"][0]["markers"][:29])
        markers[23] = markers[23].replace("trap_scenario=4", "trap_scenario=6")
        markers[25] = markers[25].replace(
            "PKBUILD1-CYCLE122-N7-XSTATE-POLICY-001",
            "PKBUILD1-CYCLE124-N7-PRIVILEGE-MSR-POLICY-001",
        )
        markers.extend(
            [
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-SETUP PASS contract=PKXEXC1 "
                "parent=PKXSTATE1 selector=6 bsp=1 gates=8 vectors=7,16,19 ist=1 "
                "xcr0=0x0000000000000003 cr0=0x0000000080010033 "
                "cr4=0x0000000000040668 parent_control_writes=3 "
                "exceptions_masked_default=1 if=0",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-ARM PASS contract=PKXEXC1 "
                "sequence=16,19,7 x87=invalid fcw=0x000000000000037E "
                "simd=invalid mxcsr=0x0000000000001F00 nm_strategy=eager_reject",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-ENTER PASS contract=PKXEXC1 "
                "kind=x87_invalid vector=16 error=0x0000000000000000 depth=1 ist=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-STATE PASS contract=PKXEXC1 "
                "kind=x87_invalid fcw_before=0x000000000000037E "
                "fsw_before=0x000000000000B081 mxcsr_before=0x0000000000001F80 "
                "fcw_after=0x000000000000037F fsw_after=0x0000000000000000 "
                "mxcsr_after=0x0000000000001F80 state_sampled=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-RETURN PASS contract=PKXEXC1 "
                "vector=16 resume=exact returned=1 recovery_write=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-ENTER PASS contract=PKXEXC1 "
                "kind=simd_invalid vector=19 error=0x0000000000000000 depth=1 ist=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-STATE PASS contract=PKXEXC1 "
                "kind=simd_invalid fcw_before=0x000000000000037F "
                "fsw_before=0x0000000000000000 mxcsr_before=0x0000000000001F01 "
                "fcw_after=0x000000000000037F fsw_after=0x0000000000000000 "
                "mxcsr_after=0x0000000000001F80 state_sampled=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-RETURN PASS contract=PKXEXC1 "
                "vector=19 resume=exact returned=2 recovery_write=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-ARM PASS contract=PKXEXC1 "
                "vector=7 injection=test_only cr0_ts=1 recovery=forbidden terminal=reject",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-ENTER PASS contract=PKXEXC1 "
                "kind=device_not_available vector=7 error=0x0000000000000000 "
                "depth=1 ist=1",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-NM-REJECT PASS contract=PKXEXC1 "
                "vector=7 strategy=eager reason=ts_set injection=test_only "
                "state_sampled=0 recovery=forbidden terminal=halt",
                "POOLEOS:KERNEL:XSTATE-EXCEPTION-RESULT PASS contract=PKXEXC1 "
                "deliveries=3 recovered=2 nm_rejected=1 privileged_writes=4 "
                "recovery_writes=2 unexpected=0 signatures=0 authority=0 actions=0 "
                "scheduler=0 smp=0 target=0 terminal=halt",
            ]
        )
        return markers

    def test_contract_and_schema_are_frozen(self) -> None:
        contract = xstate_exception.read_json(
            xstate_exception.ROOT / xstate_exception.CONTRACT_RELATIVE
        )
        self.assertEqual(xstate_exception.contract_errors(contract), [])
        schema = xstate_exception.read_json(
            xstate_exception.ROOT / xstate_exception.CONTRACT_SCHEMA_RELATIVE
        )
        self.assertEqual(schema["properties"]["contract_id"]["const"], "PKXEXC1")
        changed = copy.deepcopy(contract)
        changed["authority_gate"]["privileged_configuration_writes"] = 5
        self.assertIn(
            "PKXEXC1 authority boundary changed",
            xstate_exception.contract_errors(changed),
        )

    def test_accepts_exact_exception_receipt(self) -> None:
        summary = xstate_exception.validate_markers(self.markers())
        self.assertEqual(summary["x87"]["return"]["returned"], 1)
        self.assertEqual(summary["simd"]["state"]["mxcsr_before"], 0x1F01)
        self.assertEqual(summary["nm"]["state_sampled"], 0)
        self.assertEqual(summary["result"]["deliveries"], 3)

    def test_rejects_marker_shape_selector_and_order(self) -> None:
        markers = self.markers()
        for candidate in (markers[:-1], [*markers, markers[-1]]):
            with self.assertRaises(xstate_exception.KernelXstateExceptionError):
                xstate_exception.validate_markers(candidate)
        candidate = markers.copy()
        candidate[31], candidate[34] = candidate[34], candidate[31]
        with self.assertRaises(xstate_exception.KernelXstateExceptionError):
            xstate_exception.validate_markers(candidate)
        candidate = markers.copy()
        candidate[23] = candidate[23].replace("trap_scenario=6", "trap_scenario=5")
        with self.assertRaises(xstate_exception.KernelXstateExceptionError):
            xstate_exception.validate_markers(candidate)

    def test_rejects_pending_and_recovery_state_faults(self) -> None:
        mutations = (
            (32, "fsw_before=0x000000000000B081", "fsw_before=0x000000000000B000"),
            (32, "fcw_after=0x000000000000037F", "fcw_after=0x000000000000037E"),
            (35, "mxcsr_before=0x0000000000001F01", "mxcsr_before=0x0000000000001F81"),
            (35, "mxcsr_after=0x0000000000001F80", "mxcsr_after=0x0000000000001F81"),
        )
        for index, old, new in mutations:
            candidate = self.markers()
            candidate[index] = candidate[index].replace(old, new)
            with self.assertRaises(xstate_exception.KernelXstateExceptionError):
                xstate_exception.validate_markers(candidate)

    def test_rejects_nm_recovery_and_authority_overclaims(self) -> None:
        mutations = (
            (37, "cr0_ts=1", "cr0_ts=0"),
            (39, "state_sampled=0", "state_sampled=1"),
            (39, "recovery=forbidden", "recovery=allowed"),
            (40, "authority=0", "authority=1"),
            (40, "scheduler=0", "scheduler=1"),
        )
        for index, old, new in mutations:
            candidate = self.markers()
            candidate[index] = candidate[index].replace(old, new)
            with self.assertRaises(xstate_exception.KernelXstateExceptionError):
                xstate_exception.validate_markers(candidate)

    def test_claim_boundary_rejects_promotion(self) -> None:
        contract = xstate_exception.read_json(
            xstate_exception.ROOT / xstate_exception.CONTRACT_RELATIVE
        )
        promoted = copy.deepcopy(contract)
        promoted["claims"]["production_ready"] = True
        self.assertIn(
            "PKXEXC1 claim boundary changed",
            xstate_exception.contract_errors(promoted),
        )


if __name__ == "__main__":
    unittest.main()
