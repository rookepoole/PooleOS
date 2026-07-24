from __future__ import annotations

import copy
import unittest

from runtime import native_kernel_physical_memory as physical_memory
from tools import pooleos_release_gate, qualify_native_kernel_physical_memory


class NativeKernelPhysicalMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = physical_memory.read_json(
            physical_memory.ROOT / physical_memory.CONTRACT_RELATIVE
        )
        cls.readiness = physical_memory.read_json(
            physical_memory.ROOT / physical_memory.READINESS_RELATIVE
        )
        cls.run_evidence = cls.readiness["execution"]["runs"][0]
        cls.markers = cls.run_evidence["markers"]

    def test_contract_and_readiness_are_exact_and_non_promoting(self) -> None:
        self.assertEqual([], physical_memory.contract_errors(self.contract))
        self.assertEqual([], physical_memory.readiness_errors(self.readiness))
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n9_exit_gate_satisfied"])

    def test_live_markers_bind_to_independent_pbp1_accounting(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        derived = physical_memory.validate_observation_binding(
            observation, self.run_evidence["pbp1_transcript"]
        )
        self.assertEqual(8, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(
            derived["kind_pages"][1] - 1 + derived["boot_reclaim"]["page_count"],
            observation["result"]["managed_pages"],
        )
        self.assertEqual(physical_memory.SCRUB_BYTES, observation["scrub"]["scrub_bytes"])
        self.assertEqual(physical_memory.SCRUB_BYTES, observation["scrub"]["verified_bytes"])
        self.assertEqual(physical_memory.PHYSICAL_WRITES, observation["result"]["physical_writes"])
        self.assertEqual(physical_memory.PHYSICAL_READS, observation["result"]["physical_reads"])
        self.assertEqual(
            "temporary_single_page_plus_guarded_metadata_and_repeated_ledger_generations",
            observation["result"]["mappings"],
        )
        self.assertEqual(5, observation["metadata"]["pages"])
        self.assertEqual(2, observation["metadata"]["guard_pages"])
        self.assertEqual(15376, observation["metadata"]["manager_bytes"])
        self.assertEqual(32, observation["growth"]["final_generation"])
        self.assertEqual(29, observation["growth"]["final_pages"])
        self.assertEqual([2048, 256, 2048, 128, 16], [
            observation["growth"]["free_capacity"],
            observation["growth"]["allocation_capacity"],
            observation["growth"]["source_capacity"],
            observation["growth"]["scrub_capacity"],
            observation["growth"]["reclaim_capacity"],
        ])
        self.assertEqual(3, observation["growth"]["revoked"])
        self.assertEqual(121, observation["growth"]["pressure_checks"])
        self.assertEqual(8, observation["growth"]["pressure_triggers"])
        self.assertEqual(3, observation["growth"]["automatic_growths"])
        self.assertEqual(4, observation["growth"]["soft_fallbacks"])
        self.assertEqual(1, observation["growth"]["hard_rejections"])
        self.assertEqual("host_verified", observation["growth"]["pre_effect"])
        self.assertEqual(1, observation["result"]["metadata_retained"])
        self.assertEqual(1, observation["result"]["ledger_generation_retained"])
        self.assertEqual(1, observation["result"]["alias_revoked"])
        self.assertEqual(1, observation["result"]["reclaim"])
        self.assertEqual(0, observation["result"]["acpi_reclaim"])

    def test_boot_reclaim_receipt_is_independently_derived(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        derived = physical_memory.derive_memory_summary(self.run_evidence["pbp1_transcript"])
        reclaim = derived["boot_reclaim"]
        self.assertEqual(70, reclaim["source_record_count"])
        self.assertEqual(12, reclaim["range_count"])
        self.assertEqual(11250, reclaim["page_count"])
        self.assertEqual([2018, 9232, 0], reclaim["pages_by_zone"])
        self.assertEqual(0x5A485D4A5725EED8, reclaim["range_checksum"])
        self.assertEqual(0xE1F4C87AE4009940, reclaim["receipt_checksum"])
        self.assertEqual(reclaim["receipt_checksum"], observation["reclaim"]["receipt_checksum"])
        self.assertEqual(11, observation["reclaim"]["acpi_held_pages"])
        self.assertEqual(1, observation["reclaim"]["acpi_early_rejected"])

    def test_oracle_rejects_overlap_source_kind_and_core_escape(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        candidates = []
        overlap = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        overlap["memory_entries"][1]["physical_start"] = overlap["memory_entries"][0]["physical_start"]
        candidates.append(overlap)
        source_kind = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        source_kind["memory_entries"][0]["source_type"] = 1
        candidates.append(source_kind)
        ownership = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        ownership["core"]["kernel_physical_base"] = ownership["memory_entries"][0]["physical_start"]
        candidates.append(ownership)
        for candidate in candidates:
            with self.assertRaises(physical_memory.KernelPhysicalMemoryError):
                physical_memory.validate_observation_binding(observation, candidate)

    def test_all_hostile_controls_are_exact_and_pass(self) -> None:
        controls = qualify_native_kernel_physical_memory._negative_controls(
            self.markers, self.run_evidence["pbp1_transcript"]
        )
        self.assertEqual(
            list(physical_memory.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls]
        )
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_source_audit_proves_safe_core_and_live_adapter(self) -> None:
        audit = qualify_native_kernel_physical_memory._source_audit()
        self.assertEqual(0, audit["implementation_unauthorized_unsafe_token_count"])
        self.assertEqual(0, audit["heap_api_token_count"])
        self.assertEqual(5, audit["bootstrap_fixed_capacity_ledger_count"])
        self.assertEqual(0, audit["active_fixed_capacity_ledger_count"])
        self.assertEqual(11, audit["live_adapter_volatile_read_site_count"])
        self.assertEqual(9, audit["live_adapter_volatile_write_site_count"])
        self.assertTrue(audit["final_temporary_alias_revocation_required"])
        self.assertTrue(audit["final_guarded_metadata_mapping_retention_required"])

    def test_release_gate_accepts_only_the_bound_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_physical_memory_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn(
            f"scrub={physical_memory.SCRUB_BYTES}/{physical_memory.SCRUB_BYTES}",
            check["detail"],
        )
        self.assertIn("metadata=5+2_guards", check["detail"])
        self.assertIn("boot_reclaim=11250", check["detail"])
        self.assertIn("alias_revoked=1", check["detail"])
        self.assertIn("n9_exit=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
