from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from runtime import native_kernel_physical_memory as physical_memory
from runtime import native_kernel_virtual_memory as virtual_memory
from tools import pooleos_release_gate as gate


class NativeMemoryReleaseGateTests(unittest.TestCase):
    def test_current_accounting_and_stale_summary_rejection(self) -> None:
        receipt = physical_memory.read_json(physical_memory.ROOT / physical_memory.READINESS_RELATIVE)
        summary = receipt["summary"]
        check = gate.check_native_kernel_physical_memory_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn(f"usable={summary['source_usable_pages']};", check["detail"])
        self.assertIn(f"managed={summary['managed_pages']};", check["detail"])
        for field, stale in (
            ("loader_reserved_pages_protected", 922),
            ("managed_pages", 129082),
            ("source_usable_pages", 117822),
        ):
            for wrong in (stale, summary[field] - 1, summary[field] + 1):
                with self.subTest(field=field, wrong=wrong):
                    self.assertNotEqual(summary[field], wrong)
                    candidate = copy.deepcopy(receipt)
                    candidate["summary"][field] = wrong
                    with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                        result = gate.check_native_kernel_physical_memory_readiness()
                    self.assertFalse(result["ok"])
                    self.assertIn("readiness summary changed", result["detail"])

    def test_virtual_memory_accounting_rejects_changed_counts_and_digest(self) -> None:
        receipt = virtual_memory.read_json(virtual_memory.ROOT / virtual_memory.READINESS_RELATIVE)
        positive = gate.check_native_kernel_virtual_memory_readiness()
        self.assertTrue(positive["ok"], positive["detail"])
        fields = ("bootstrap_hardware_tlb_invalidations", "direct_map_gap_pages",
                  "mapped_owned_pages", "physical_table_writes", "temporary_pte_writes",
                  "coverage_checksum")
        for field in fields:
            value = receipt["summary"][field]
            wrong_values = ("0x0000000000000000",) if isinstance(value, str) else (value - 1, value + 1)
            for wrong in wrong_values:
                with self.subTest(field=field, wrong=wrong):
                    candidate = copy.deepcopy(receipt)
                    candidate["summary"][field] = wrong
                    with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                        result = gate.check_native_kernel_virtual_memory_readiness()
                    self.assertFalse(result["ok"])
                    self.assertIn("readiness summary changed", result["detail"])


if __name__ == "__main__":
    unittest.main()
