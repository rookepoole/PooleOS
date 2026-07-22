from __future__ import annotations

import copy
import unittest

from runtime import native_kernel_virtual_memory as virtual_memory
from tools import qualify_native_kernel_virtual_memory


class NativeKernelVirtualMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = virtual_memory.read_json(
            virtual_memory.ROOT / virtual_memory.CONTRACT_RELATIVE
        )
        cls.readiness = virtual_memory.read_json(
            virtual_memory.ROOT / virtual_memory.READINESS_RELATIVE
        )
        cls.live_run = cls.readiness["execution"]["runs"][0]
        cls.markers = cls.live_run["markers"]

    def test_contract_and_readiness_are_exact_and_non_promoting(self) -> None:
        self.assertEqual([], virtual_memory.contract_errors(self.contract))
        self.assertEqual([], virtual_memory.readiness_errors(self.readiness))
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n9_exit_gate_satisfied"])

    def test_live_tables_bind_to_pbp1_first_fit(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        derived = virtual_memory.validate_observation_binding(
            observation, self.live_run["pbp1_transcript"]
        )
        candidate = observation["candidate"]
        self.assertEqual(10, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(derived["first_free_address"][1], candidate["candidate_root"])
        self.assertEqual(8, virtual_memory.TABLE_PAGES)
        self.assertEqual(candidate["candidate_root"] + 8 * virtual_memory.PAGE_BYTES, candidate["data"])
        self.assertEqual(
            virtual_memory.DIRECT_MAP_START + candidate["candidate_root"],
            candidate["direct_first"],
        )
        self.assertEqual(8720, observation["result"]["physical_writes"])
        self.assertEqual(5336, observation["result"]["temporary_pte_writes"])

    def test_active_root_restores_cr3_and_binds_leaf_receipts(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        self.assertEqual(2, observation["activation"]["cr3_writes"])
        self.assertEqual("exact", observation["activation"]["candidate_readback"])
        self.assertEqual("exact", observation["activation"]["original_restore"])
        self.assertEqual(3, observation["invalidation"]["active_receipts"])
        self.assertEqual(0xA5, observation["invalidation"]["probe"])
        self.assertEqual(1, observation["invalidation"]["premature_reuse_rejected"])
        self.assertEqual(3, observation["result"]["active_invlpg"])
        self.assertEqual(5336, observation["result"]["bootstrap_invlpg"])
        for key in ("shootdown", "smp", "ring3", "production"):
            self.assertEqual(0, observation["result"][key])

    def test_oracle_rejects_pbp1_first_fit_drift(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        hostile = copy.deepcopy(observation)
        hostile["candidate"]["candidate_root"] += virtual_memory.PAGE_BYTES
        with self.assertRaises(virtual_memory.KernelVirtualMemoryError):
            virtual_memory.validate_observation_binding(
                hostile, self.live_run["pbp1_transcript"]
            )

    def test_all_hostile_controls_are_exact_and_pass(self) -> None:
        controls = qualify_native_kernel_virtual_memory._negative_controls(
            self.markers, self.live_run["pbp1_transcript"]
        )
        self.assertEqual(
            list(virtual_memory.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls]
        )
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_source_audit_binds_core_and_privileged_adapter(self) -> None:
        audit = qualify_native_kernel_virtual_memory._source_audit()
        self.assertEqual(0, audit["heap_api_token_count"])
        self.assertEqual(2, audit["active_cr3_write_count"])
        self.assertEqual(3, audit["active_local_invalidation_count"])
        self.assertEqual(8, audit["fixed_capacity_table_page_count"])
        self.assertTrue(audit["volatile_physical_adapter"])
        self.assertTrue(audit["bootstrap_temporary_mapping_uses_invlpg"])
        self.assertTrue(audit["live_cpuid_physical_width_validated"])


if __name__ == "__main__":
    unittest.main()
