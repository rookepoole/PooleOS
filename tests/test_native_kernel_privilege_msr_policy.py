from __future__ import annotations

import copy
import unittest

from runtime import native_kernel_privilege_msr_policy as privilege_msr
from tools import pooleos_release_gate, qualify_native_kernel_privilege_msr_policy


class NativeKernelPrivilegeMsrPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = privilege_msr.read_json(privilege_msr.ROOT / privilege_msr.CONTRACT_RELATIVE)
        cls.readiness = privilege_msr.read_json(privilege_msr.ROOT / privilege_msr.READINESS_RELATIVE)
        cls.markers = cls.readiness["execution"]["runs"][0]["markers"]

    def test_contract_and_readiness_are_exact_and_non_promoting(self) -> None:
        self.assertEqual([], privilege_msr.contract_errors(self.contract))
        self.assertEqual([], privilege_msr.readiness_errors(self.readiness))
        self.assertFalse(self.readiness["production_ready"])
        self.assertTrue(pooleos_release_gate.check_native_kernel_privilege_msr_policy_readiness()["ok"])

    def test_live_markers_bind_support_gates_and_zero_authority(self) -> None:
        observation = privilege_msr.validate_markers(self.markers)
        self.assertEqual(7, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual("AuthenticAMD", observation["features"]["vendor"])
        self.assertEqual(0, observation["features"]["architectural_pmu_version"])
        self.assertEqual(0, observation["features"]["amd_perfmon_v2"])
        self.assertGreaterEqual(observation["machine_check"]["bank_count"], 1)
        self.assertEqual(0, observation["machine_check"]["bank_reads"])
        self.assertEqual(0, observation["result"]["msr_writes"])
        self.assertEqual(0, observation["result"]["authority"])

    def test_marker_parser_rejects_activation_reserved_bits_and_write_claims(self) -> None:
        observation = privilege_msr.validate_markers(self.markers)
        candidates = [self.markers[:-1]]
        selector = copy.deepcopy(self.markers)
        selector[23] = selector[23].replace("trap_scenario=7", "trap_scenario=0")
        candidates.append(selector)
        syscall = copy.deepcopy(self.markers)
        syscall[30] = qualify_native_kernel_privilege_msr_policy._set_field(
            syscall[30], "efer", qualify_native_kernel_privilege_msr_policy._hex(observation["linkage"]["efer"] | 1)
        )
        candidates.append(syscall)
        reserved = copy.deepcopy(self.markers)
        reserved[32] = qualify_native_kernel_privilege_msr_policy._set_field(
            reserved[32], "mcg_cap", qualify_native_kernel_privilege_msr_policy._hex(observation["machine_check"]["mcg_cap"] | (1 << 9))
        )
        candidates.append(reserved)
        write = copy.deepcopy(self.markers)
        write[34] = write[34].replace("msr_writes=0", "msr_writes=1")
        candidates.append(write)
        for candidate in candidates:
            with self.assertRaises(privilege_msr.KernelPrivilegeMsrPolicyError):
                privilege_msr.validate_markers(candidate)

    def test_all_hostile_controls_are_exact_and_pass(self) -> None:
        controls = qualify_native_kernel_privilege_msr_policy._negative_controls(self.markers)
        self.assertEqual(list(privilege_msr.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_source_audit_rejects_wrmsr(self) -> None:
        source = (privilege_msr.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        self.assertEqual("pass_read_only_support_gated_source_audit", qualify_native_kernel_privilege_msr_policy._audit_source_text(source)["result"])
        hostile = source.replace(
            "pub unsafe fn observe_privilege_msr_policy() -> PrivilegeMsrSnapshot {\n    let basic = cpuid(0, 0);",
            'pub unsafe fn observe_privilege_msr_policy() -> PrivilegeMsrSnapshot {\n    let basic = cpuid(0, 0); let _hostile = "wrmsr";',
            1,
        )
        self.assertNotEqual(source, hostile)
        with self.assertRaises(qualify_native_kernel_privilege_msr_policy.QualificationError):
            qualify_native_kernel_privilege_msr_policy._audit_source_text(hostile)

    def test_linked_audit_records_no_activation_or_write_instruction(self) -> None:
        audit = self.readiness["build"]["linked_machine_code_audit"]
        self.assertGreaterEqual(audit["instruction_counts"]["rdmsr"], 1)
        self.assertEqual(0, audit["instruction_counts"]["wrmsr"])
        self.assertEqual(0, audit["instruction_counts"]["syscall"])
        self.assertEqual(0, audit["instruction_counts"]["swapgs"])


if __name__ == "__main__":
    unittest.main()
