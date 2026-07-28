from __future__ import annotations

import copy
import unittest

from runtime import native_kernel_smp_first_ap as smp_first_ap
from tools import pooleos_release_gate, qualify_native_kernel_smp_first_ap


class NativeKernelSmpFirstApTests(unittest.TestCase):
    def test_contract_is_exact_and_non_promoting(self) -> None:
        contract = smp_first_ap.read_json(smp_first_ap.ROOT / smp_first_ap.CONTRACT_RELATIVE)
        self.assertEqual([], smp_first_ap.contract_errors(contract))
        self.assertTrue(contract["claims"]["one_application_processor_started"])
        self.assertFalse(contract["claims"]["general_smp_implemented"])
        self.assertFalse(contract["claims"]["n8_exit_gate_satisfied"])
        self.assertFalse(contract["production_ready"])

    def test_resource_layout_is_complete_guarded_and_below_one_mib(self) -> None:
        layout = smp_first_ap.resource_layout(1, 14)
        self.assertEqual(0x1000, layout["start"])
        self.assertEqual(0xF000, layout["end"])
        self.assertEqual(1, layout["sipi_vector"])
        self.assertEqual([5, 10], layout["roles"]["stack_guards"])
        self.assertEqual([11, 13], layout["roles"]["per_cpu_guards"])
        self.assertEqual([6, 7, 8, 9], layout["roles"]["stack"])
        for start, pages in ((0, 14), (1, 13), (0x100, 14)):
            with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
                smp_first_ap.resource_layout(start, pages)

    def test_first_ap_selection_rejects_missing_and_x2apic_targets(self) -> None:
        processors = [
            {"apic_id": 0, "enabled": True, "x2apic": False},
            {"apic_id": 2, "enabled": True, "x2apic": False},
            {"apic_id": 1, "enabled": True, "x2apic": False},
        ]
        self.assertEqual(1, smp_first_ap.select_first_ap(processors, 0)["apic_id"])
        with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
            smp_first_ap.select_first_ap(processors[:1], 0)
        hostile = copy.deepcopy(processors)
        hostile[2]["x2apic"] = True
        hostile[1]["enabled"] = False
        with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
            smp_first_ap.select_first_ap(hostile, 0)

    def test_rx_gdt_requires_every_descriptor_accessed_bit_pre_set(self) -> None:
        descriptors = [
            0x00CF_9B00_0000_FFFF,
            0x00CF_9300_0000_FFFF,
            0x00AF_9B00_0000_FFFF,
            0x00CF_9300_0000_FFFF,
        ]
        smp_first_ap.require_preaccessed_gdt(descriptors)
        descriptors[3] &= ~(1 << 40)
        with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
            smp_first_ap.require_preaccessed_gdt(descriptors)

    def test_mailbox_checksum_matches_the_first_live_qemu_receipt(self) -> None:
        values = {
            "state": 3,
            "command": 1,
            "target_apic_id": 1,
            "bsp_apic_id": 0,
            "observed_apic_id": 1,
            "leaf1_ecx": 0x8000_2001,
            "leaf1_edx": 0x178B_FBFD,
            "cr0": 0xE001_0011,
            "cr3": 0x2000,
            "cr4": 0x20,
            "efer": 0xD00,
            "tsc_online": 0x73D5_BF42,
            "tsc_stop": 0x73D8_CCEE,
        }
        self.assertEqual(0xA4C5_8217_BC17_0831, smp_first_ap.mailbox_checksum(values))
        values["tsc_stop"] += 1
        self.assertNotEqual(0xA4C5_8217_BC17_0831, smp_first_ap.mailbox_checksum(values))

    def test_source_audit_binds_preaccessed_gdt_and_removes_probes(self) -> None:
        audit = qualify_native_kernel_smp_first_ap._source_audit()
        self.assertEqual(4, audit["gdt_preaccessed_descriptor_count"])
        self.assertEqual(3, audit["trampoline_mode_count"])
        self.assertEqual(0, audit["transient_diagnostic_token_count"])

    def test_live_readiness_and_all_hostile_controls(self) -> None:
        path = smp_first_ap.ROOT / smp_first_ap.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP1 readiness has not been generated yet")
        readiness = smp_first_ap.read_json(path)
        self.assertEqual([], smp_first_ap.readiness_errors(readiness))
        markers = readiness["execution"]["runs"][0]["markers"]
        observation = smp_first_ap.validate_markers(markers)
        self.assertEqual(1, observation["result"]["ap_online"])
        self.assertTrue(observation["stop"]["parked"])
        self.assertEqual(57_344, observation["release"]["verified_bytes"])
        controls = qualify_native_kernel_smp_first_ap._negative_controls(markers)
        self.assertEqual(list(smp_first_ap.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])

    def test_release_gate_accepts_only_the_bound_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_smp_first_ap_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("qemu64_vcpus=2", check["detail"])
        self.assertIn("ap=1/1", check["detail"])
        self.assertIn("parked=1/1", check["detail"])
        self.assertIn("n8_exit=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
