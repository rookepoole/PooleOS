from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from runtime import native_kernel_physical_memory as physical_memory
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
            for wrong in (stale, summary[field] + 1):
                with self.subTest(field=field, wrong=wrong):
                    self.assertNotEqual(summary[field], wrong)
                    candidate = copy.deepcopy(receipt)
                    candidate["summary"][field] = wrong
                    with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                        result = gate.check_native_kernel_physical_memory_readiness()
                    self.assertFalse(result["ok"])
                    self.assertIn("readiness summary changed", result["detail"])


if __name__ == "__main__":
    unittest.main()
