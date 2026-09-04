import tempfile
import unittest
from pathlib import Path

from runtime import native_kernel_smp_ipi as smp_ipi
from runtime import native_tier0
from tools import qualify_native_kernel_smp_ipi as qualify
from tools import pooleos_release_gate


class NativeKernelSmpIpiTests(unittest.TestCase):
    def test_readiness_writer_emits_canonical_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "readiness.json"
            qualify._write_readiness(path, {"status": "pass", "values": [1, 2]})
            data = path.read_bytes()
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(data.endswith(b"\n"))

    def test_contract_schema_and_negative_control_order(self) -> None:
        contract = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.CONTRACT_RELATIVE)
        self.assertEqual([], smp_ipi.contract_errors(contract))
        self.assertEqual(30, len(smp_ipi.NEGATIVE_CONTROL_IDS))
        self.assertEqual(243, contract["qualification"]["hostile_case_count"])

    def test_three_private_resource_layouts_fit_below_one_mib(self) -> None:
        layouts = [smp_ipi.resource_layout(page, 32) for page in (1, 35, 69)]
        self.assertEqual([0x1000, 0x23000, 0x45000], [item["start"] for item in layouts])
        self.assertEqual([0x20000, 0x42000, 0x64000], [item["apic_page_table"] for item in layouts])
        self.assertEqual(3, len({item["pml4"] for item in layouts}))
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.resource_layout(1, 31)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.resource_layout(0, 32)

    def test_exact_topology_and_local_masks_fail_closed(self) -> None:
        smp_ipi.validate_exact_topology(4, 4, 0, (1, 2, 3))
        self.assertEqual([2, 4, 8], [smp_ipi.local_target_mask(value) for value in (1, 2, 3)])
        self.assertEqual(14, sum(smp_ipi.local_target_mask(value) for value in (1, 2, 3)))
        for value in ((3, 3, 0, (1, 2, 3)), (4, 3, 0, (1, 2, 3)), (4, 4, 1, (1, 2, 3)), (4, 4, 0, (1, 2, 4))):
            with self.assertRaises(smp_ipi.KernelSmpIpiError):
                smp_ipi.validate_exact_topology(*value)

    def test_request_model_accepts_canonical_and_rejects_controls(self) -> None:
        request = smp_ipi.canonical_request(1, 1, 4, 2)
        smp_ipi.validate_request(request, 4, 2, 0, 0)
        invalid = request.copy()
        invalid["capability_high"] ^= 1
        invalid["checksum"] = smp_ipi.request_checksum(invalid)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(invalid, 4, 2, 0, 0)
        wrong_vector = request.copy()
        wrong_vector["vector"] = 225
        wrong_vector["checksum"] = smp_ipi.request_checksum(wrong_vector)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(wrong_vector, 4, 2, 0, 0)

    def test_response_checksum_is_independent_and_frozen(self) -> None:
        checksum = smp_ipi.response_checksum({
            "ack_attempt": 4,
            "ack_sequence": 3,
            "result": int(smp_ipi.OPERATIONS[6]["result"]),
            "last_accepted_sequence": 3,
            "ack_operation": 6,
            "ack_status": 1,
            "ack_error": 0,
            "delivery_count": 4,
            "accepted_count": 3,
            "denied_count": 1,
        })
        self.assertEqual(0x1A04_0602_5350_0005, checksum)

    def test_aggregate_address_checksum_is_ordered_and_nonzero(self) -> None:
        values = [(2, 0x20000), (4, 0x42000), (8, 0x64000)]
        checksum = smp_ipi.aggregate_address_checksum(values, smp_ipi.AGGREGATE_ROOT_DOMAIN)
        self.assertNotEqual(0, checksum)
        self.assertNotEqual(
            checksum,
            smp_ipi.aggregate_address_checksum(list(reversed(values)), smp_ipi.AGGREGATE_ROOT_DOMAIN),
        )

    def test_multi_reclaim_waits_for_three_unique_acknowledgements(self) -> None:
        requests = qualify._multi_requests()
        model = smp_ipi.DeferredReclaimModel(requests)
        model.arm()
        model.timeout()
        model.retry()
        for index, request in enumerate(requests):
            model.acknowledge(
                smp_ipi.canonical_shootdown_snapshot(request, int(index == 0)),
                smp_ipi.EXPECTED_APIC_IDS[index],
            )
            if index < 2:
                with self.assertRaises(smp_ipi.KernelSmpIpiError):
                    model.authorize()
        model.authorize()
        model.release()
        self.assertEqual("released", model.stage)

        duplicate = smp_ipi.DeferredReclaimModel(requests)
        duplicate.arm()
        ack = smp_ipi.canonical_shootdown_snapshot(requests[0])
        duplicate.acknowledge(ack, 1)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            duplicate.acknowledge(ack, 1)

    def test_partial_lifecycle_requires_complete_park_release_and_retry(self) -> None:
        model = smp_ipi.MultiApLifecycleModel()
        model.partial(0x6, 0x10, 0x6, 0xE)
        model.retry(0xE, 0xE)
        model.complete(0xE, 0xE, 0xE, 0xE)
        self.assertEqual("released", model.stage)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.MultiApLifecycleModel().partial(0x2, 0x10, 0x2, 0xE)

    def test_multi_ap_receipts_allow_metadata_growth_gaps_but_reject_aliases(self) -> None:
        receipts = [
            {"allocation_sequence": 24, "frame_allocation_sequences": (25, 26), "frame_release_sequences": (35, 42), "resource_release_sequence": 43},
            {"allocation_sequence": 27, "frame_allocation_sequences": (28, 31), "frame_release_sequences": (36, 40), "resource_release_sequence": 41},
            {"allocation_sequence": 32, "frame_allocation_sequences": (33, 34), "frame_release_sequences": (37, 38), "resource_release_sequence": 39},
        ]
        smp_ipi.validate_receipt_sequences(receipts)
        hostile = [item.copy() for item in receipts]
        hostile[1]["frame_allocation_sequences"] = (28, 33)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_receipt_sequences(hostile)
        zero_sequence = [item.copy() for item in receipts]
        zero_sequence[0]["allocation_sequence"] = 0
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_receipt_sequences(zero_sequence)

    def test_sandybridge_profile_is_four_cpu_multi_tcg_without_icount(self) -> None:
        _, base = native_tier0.validate_contracts(smp_ipi.ROOT)
        profile = qualify._sandybridge_profile(base)
        arguments = profile["base_argument_template"]
        self.assertEqual("SandyBridge,-avx", arguments[arguments.index("-cpu") + 1])
        self.assertEqual("tcg,thread=multi", arguments[arguments.index("-accel") + 1])
        self.assertEqual("4,sockets=1,dies=1,clusters=1,cores=4,threads=1,maxcpus=4", arguments[arguments.index("-smp") + 1])
        self.assertNotIn("-icount", arguments)

    def test_source_audit_requires_dynamic_local_mask_and_coordinator(self) -> None:
        audit = qualify._source_audit()
        self.assertGreaterEqual(audit["xsave_instruction_count"], 2)
        self.assertEqual(6, audit["operation_handler_count"])
        self.assertEqual(1, audit["remote_shootdown_invlpg_source_count"])
        self.assertEqual(3, audit["application_processor_count"])
        arch = (smp_ipi.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        main = (smp_ipi.ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
        ipi = (smp_ipi.ROOT / "native/kernel/src/smp_ipi.rs").read_text(encoding="utf-8")
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._audit_source_text(arch.replace("shl rbx, cl", "shl rbx, 1", 1), main, ipi)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._audit_source_text(arch.replace(".Lpoole_ap_ipi_count_stop:", ".Lpoole_ap_ipi_count_terminal:", 1), main, ipi)

    def test_linked_invlpg_scope_separates_ipi_and_successor_profile(self) -> None:
        disassembly = (
            "0000000000001000 <poole_ap_ipi_trampoline_start>:\n"
            "    1000: 0f 01 38\tinvlpg\t(%rax)\n"
            "    1003: 0f 01 3b\tinvlpg\t(%rbx)\n"
            "0000000000001006 <poole_ap_ipi_trampoline_end>:\n"
        )
        audit = qualify._linked_invlpg_scope(disassembly)
        self.assertEqual(2, audit["invlpg_instruction_count"])
        self.assertEqual(1, audit["remote_shootdown_invlpg_instruction_count"])
        self.assertEqual(3, audit["runtime_execution_count"])
        self.assertEqual(1, audit["successor_profile_invlpg_instruction_count"])
        self.assertFalse(audit["successor_profile_executed"])
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._linked_invlpg_scope(disassembly.replace("invlpg", "nop", 1))

    def test_live_readiness_and_hostile_cases_when_generated(self) -> None:
        path = smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP5 readiness has not been generated yet")
        readiness = smp_ipi.read_json(path)
        if readiness.get("contract_id") != "PKSMP5":
            self.skipTest("PKSMP5 readiness has not replaced the predecessor receipt yet")
        self.assertEqual([], smp_ipi.readiness_errors(readiness))
        observation = smp_ipi.validate_markers(readiness["execution"]["runs"][0]["markers"])
        self.assertEqual(3, observation["result"]["application_processors_online"])
        controls = qualify._negative_controls(readiness["execution"]["runs"][0]["markers"])
        self.assertEqual(list(smp_ipi.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(243, sum(item["case_count"] for item in controls))
        check = pooleos_release_gate.check_native_kernel_smp_ipi_readiness()
        self.assertTrue(check["ok"], check["detail"])


if __name__ == "__main__":
    unittest.main()
