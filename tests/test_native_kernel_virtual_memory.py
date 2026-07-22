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
        self.assertEqual(9, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(derived["first_free_address"][1], observation["tables"]["root"])
        self.assertEqual(4, observation["tables"]["materialized"])
        self.assertEqual(4, observation["tables"]["temporary_verified"])
        self.assertEqual(4104, observation["result"]["physical_writes"])
        self.assertEqual(40, observation["result"]["temporary_pte_writes"])

    def test_transaction_boundary_separates_bootstrap_tlb_from_inactive_root(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        self.assertEqual(2, observation["transaction"]["inactive_receipts"])
        self.assertEqual(1, observation["transaction"]["cache_alias_rejected"])
        self.assertEqual(1, observation["transaction"]["premature_reuse_rejected"])
        self.assertEqual(40, observation["result"]["invlpg"])
        for key in ("active_cr3_writes", "shootdown", "smp", "production"):
            self.assertEqual(0, observation["result"][key])

    def test_oracle_rejects_pbp1_first_fit_drift(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        hostile = copy.deepcopy(observation)
        hostile["tables"]["root"] += virtual_memory.PAGE_BYTES
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
        self.assertEqual(0, audit["active_cr3_or_invlpg_token_count"])
        self.assertEqual(3, audit["fixed_capacity_ledger_count"])
        self.assertTrue(audit["volatile_physical_adapter"])
        self.assertTrue(audit["bootstrap_temporary_mapping_uses_invlpg"])


if __name__ == "__main__":
    unittest.main()
