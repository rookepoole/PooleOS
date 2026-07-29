import unittest

from runtime import native_kernel_smp_ipi as smp_ipi
from runtime import native_tier0
from tools import qualify_native_kernel_smp_ipi as qualify
from tools import pooleos_release_gate


class NativeKernelSmpIpiTests(unittest.TestCase):
    def test_contract_schema_and_negative_control_order(self) -> None:
        contract = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.CONTRACT_RELATIVE)
        self.assertEqual([], smp_ipi.contract_errors(contract))
        self.assertEqual(18, len(smp_ipi.NEGATIVE_CONTROL_IDS))
        self.assertEqual(120, contract["qualification"]["hostile_case_count"])

    def test_resource_layout_repurposes_only_page_31_for_apic_table(self) -> None:
        layout = smp_ipi.resource_layout(1, 32)
        self.assertEqual(0x1000, layout["start"])
        self.assertEqual(0x21000, layout["end"])
        self.assertEqual(0x20000, layout["apic_page_table"])
        self.assertEqual([31], layout["roles"]["apic_page_table"])
        self.assertEqual(
            list(range(32)),
            sorted(offset for values in layout["roles"].values() for offset in values),
        )
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.resource_layout(1, 31)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.resource_layout(0, 32)

    def test_request_model_accepts_canonical_and_rejects_controls(self) -> None:
        request = smp_ipi.canonical_request(1, 1, 1, 1)
        smp_ipi.validate_request(request, 1, 1, 0, 0)
        invalid_capability = request.copy()
        invalid_capability["capability_high"] ^= 1
        invalid_capability["checksum"] = smp_ipi.request_checksum(invalid_capability)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(invalid_capability, 1, 1, 0, 0)
        wrong_vector = request.copy()
        wrong_vector["vector"] = 225
        wrong_vector["checksum"] = smp_ipi.request_checksum(wrong_vector)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(wrong_vector, 1, 1, 0, 0)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(request, 1, 1, 0, 1)

    def test_response_checksum_is_independent_and_frozen(self) -> None:
        checksum = smp_ipi.response_checksum(
            {
                "ack_attempt": 10,
                "ack_sequence": 6,
                "result": int(smp_ipi.OPERATIONS[6]["result"]),
                "last_accepted_sequence": 6,
                "ack_operation": 6,
                "ack_status": 1,
                "ack_error": 0,
                "delivery_count": 10,
                "accepted_count": 6,
                "denied_count": 4,
            }
        )
        self.assertEqual(0x1A04_0602_5350_0005, checksum)

    def test_sandybridge_profile_is_two_cpu_multi_tcg_without_icount(self) -> None:
        _, base = native_tier0.validate_contracts(smp_ipi.ROOT)
        profile = qualify._sandybridge_profile(base)
        arguments = profile["base_argument_template"]
        self.assertEqual("SandyBridge,-avx", arguments[arguments.index("-cpu") + 1])
        self.assertEqual("tcg,thread=multi", arguments[arguments.index("-accel") + 1])
        self.assertEqual(
            "2,sockets=1,dies=1,clusters=1,cores=2,threads=1,maxcpus=2",
            arguments[arguments.index("-smp") + 1],
        )
        self.assertNotIn("-icount", arguments)

    def test_source_audit_fails_if_ipi_xrestore_disappears(self) -> None:
        audit = qualify._source_audit()
        self.assertGreaterEqual(audit["xsave_instruction_count"], 2)
        self.assertGreaterEqual(audit["xrstor_instruction_count"], 2)
        self.assertEqual(6, audit["operation_handler_count"])
        arch = (smp_ipi.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        main = (smp_ipi.ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
        ipi = (smp_ipi.ROOT / "native/kernel/src/smp_ipi.rs").read_text(encoding="utf-8")
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._audit_source_text(
                arch.replace("xrstor64 [rbx]", "xrstor64 [rax]", 1), main, ipi
            )

    def test_live_readiness_and_hostile_cases_when_generated(self) -> None:
        path = smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP3 readiness has not been generated yet")
        readiness = smp_ipi.read_json(path)
        self.assertEqual([], smp_ipi.readiness_errors(readiness))
        markers = readiness["execution"]["runs"][0]["markers"]
        observation = smp_ipi.validate_markers(markers)
        self.assertEqual(6, observation["operations"]["accepted"])
        self.assertEqual(4, observation["operations"]["denied"])
        controls = qualify._negative_controls(markers)
        self.assertEqual(list(smp_ipi.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(120, sum(item["case_count"] for item in controls))
        check = pooleos_release_gate.check_native_kernel_smp_ipi_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("accepted=6/6", check["detail"])
        self.assertIn("tlb_invalidations=0", check["detail"])


if __name__ == "__main__":
    unittest.main()
