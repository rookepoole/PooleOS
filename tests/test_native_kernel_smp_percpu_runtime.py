import copy
import unittest

from runtime import native_kernel_smp_percpu_runtime as smp_runtime
from runtime import native_tier0
from tools import qualify_native_kernel_smp_percpu_runtime as qualify
from tools import pooleos_release_gate


class NativeKernelSmpPerCpuRuntimeTests(unittest.TestCase):
    def test_contract_schema_and_negative_control_order(self) -> None:
        contract = smp_runtime.read_json(smp_runtime.ROOT / smp_runtime.CONTRACT_RELATIVE)
        self.assertEqual([], smp_runtime.contract_errors(contract))
        self.assertEqual(19, len(smp_runtime.NEGATIVE_CONTROL_IDS))
        self.assertEqual(159, contract["qualification"]["hostile_case_count"])

    def test_resource_layout_freezes_all_32_page_roles(self) -> None:
        layout = smp_runtime.resource_layout(1, 32)
        self.assertEqual(0x1000, layout["start"])
        self.assertEqual(0x21000, layout["end"])
        self.assertEqual(0x10000, layout["gdt"])
        self.assertEqual(0x10040, layout["tss"])
        self.assertEqual(0x13000, layout["idt"])
        self.assertEqual(0x1E000, layout["xstate"])
        self.assertEqual(list(range(32)), sorted(offset for values in layout["roles"].values() for offset in values))
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.resource_layout(1, 31)
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.resource_layout(0, 32)

    def test_first_ap_selection_rejects_x2apic_and_missing_target(self) -> None:
        processors = [
            {"apic_id": 0, "enabled": True, "x2apic": False},
            {"apic_id": 1, "enabled": True, "x2apic": False},
        ]
        self.assertEqual(1, smp_runtime.select_first_ap(processors, 0)["apic_id"])
        x2apic = copy.deepcopy(processors)
        x2apic[1]["x2apic"] = True
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.select_first_ap(x2apic, 0)
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.select_first_ap(processors[:1], 0)

    def test_sandybridge_profile_is_two_cpu_multi_tcg_without_icount(self) -> None:
        _, base = native_tier0.validate_contracts(smp_runtime.ROOT)
        profile = qualify._sandybridge_profile(base)
        arguments = profile["base_argument_template"]
        self.assertEqual("SandyBridge,-avx", arguments[arguments.index("-cpu") + 1])
        self.assertEqual("tcg,thread=multi", arguments[arguments.index("-accel") + 1])
        self.assertEqual("2,sockets=1,dies=1,clusters=1,cores=2,threads=1,maxcpus=2", arguments[arguments.index("-smp") + 1])
        self.assertNotIn("-icount", arguments)

    def test_source_audit_fails_if_runtime_xrestore_disappears(self) -> None:
        audit = qualify._source_audit()
        self.assertEqual(1, audit["xsave_instruction_count"])
        self.assertEqual(1, audit["xrstor_instruction_count"])
        self.assertEqual(14, audit["guard_page_count"])
        arch = (smp_runtime.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        main = (smp_runtime.ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
        runtime = (smp_runtime.ROOT / "native/kernel/src/smp_runtime.rs").read_text(encoding="utf-8")
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            qualify._audit_source_text(arch.replace("xrstor64 [rbx]", "xrstor64 [rax]", 1), main, runtime)

    def test_live_readiness_and_all_hostile_cases(self) -> None:
        path = smp_runtime.ROOT / smp_runtime.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP2 readiness has not been generated yet")
        readiness = smp_runtime.read_json(path)
        self.assertEqual([], smp_runtime.readiness_errors(readiness))
        markers = readiness["execution"]["runs"][0]["markers"]
        observation = smp_runtime.validate_markers(markers)
        self.assertEqual(27, observation["result"]["vectors"])
        self.assertTrue(observation["xstate"]["owner_cleared"])
        controls = qualify._negative_controls(markers)
        self.assertEqual(list(smp_runtime.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(159, sum(item["case_count"] for item in controls))
        check = pooleos_release_gate.check_native_kernel_smp_percpu_runtime_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("gates=27/27", check["detail"])
        self.assertIn("n8_exit=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
