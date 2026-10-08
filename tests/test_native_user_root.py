"""Historical marker replay is parser coverage, never fresh guest execution."""
import json
import re
import unittest
from pathlib import Path

from runtime import native_user_root as probe
from runtime.native_kernel_transfer import KernelTransferError

ROOT = Path(__file__).resolve().parents[1]


class UserRootTests(unittest.TestCase):
    def setUp(self):
        self.markers = json.loads((ROOT / "tests/fixtures/cycle237-user-root-markers.json").read_bytes())["markers"]
        self.summary = probe.validate_markers(self.markers)

    def reject(self, index, field, value):
        changed = self.markers.copy()
        changed[index], count = re.subn(r"\b" + field + r"=[^ ]+", field + "=" + value, changed[index])
        self.assertEqual(count, 1)
        with self.assertRaises((ValueError, KernelTransferError)):
            probe.validate_markers(changed)

    def test_captured_trace_has_only_bounded_cpl0_claims(self):
        self.assertEqual(self.summary["cpl"], 0)
        self.assertEqual(self.summary["cr3_writes"], 2)
        self.assertFalse(self.summary["ring3_executed"])
        self.assertFalse(self.summary["production_ready"])

    def test_order_missing_duplicate_and_every_live_field_rejected(self):
        self.assertGreaterEqual(probe.negative_controls(self.markers), 25)

    def test_wrong_selector_rejected(self):
        for value in ("0", "22", "24", "255"):
            self.reject(23, "trap_scenario", value)

    def test_ordinary_unsigned_terminal_is_not_user_root_execution(self):
        altered = self.markers[:29] + ["POOLEOS:KERNEL:TRANSFER-DENIED PASS"]
        with self.assertRaises(ValueError):
            probe.validate_markers(altered)

    def test_original_must_match_observed_boot_root(self):
        self.reject(29, "original", "0x0000000010000000")

    def test_candidate_must_be_distinct_aligned_dma32_and_nonzero(self):
        for value in (0, 1, 1 << 32, self.summary["original_root"]):
            self.reject(29, "candidate", f"0x{value:016X}")

    def test_active_root_must_match_prepared_candidate(self):
        self.reject(30, "cr3", f"0x{self.summary['original_root']:016X}")

    def test_restoration_must_match_original(self):
        self.reject(31, "restored", f"0x{self.summary['candidate_root']:016X}")

    def test_sentinel_binds_candidate_and_generation(self):
        self.reject(30, "stack_probe", f"0x{self.summary['stack_probe'] ^ 1:016X}")
        self.reject(29, "generation", str(self.summary["generation"] + 1))

    def test_generation_has_u64_nonzero_bounds(self):
        for value in ("0", str(1 << 64)):
            self.reject(29, "generation", value)

    def test_numeric_claims_cannot_be_promoted(self):
        for index, field, value in ((29, "pages", "14"), (29, "temporary_aliases", "1"),
                (30, "cpl", "3"), (30, "if", "1"), (30, "ring3", "1"),
                (31, "cr3_writes", "1"), (31, "allocated_pages", "1"),
                (31, "released_pages", "12"), (31, "scrubbed_data_pages", "5"),
                (31, "production", "1")):
            self.reject(index, field, value)

    def test_cpu_adapter_uses_apic_register_accessor_not_capability_mask(self):
        source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text()
        adapter = source.split("impl poolekernel::user_entry::prepared::cpu::Cpu for UserRootCpu", 1)[1]
        snapshot = adapter.split("fn write_root", 1)[0]
        self.assertIn("read_apic_base()", snapshot)
        self.assertNotIn("read_msr(CPU_MSR_APIC_BASE)", source)
        self.assertIn("const IA32_APIC_BASE: u32 = 0x0000_001b;", source)
        self.assertIn("read_msr(IA32_APIC_BASE)", source)
        self.assertIn("0x101f => PanicCode::UserRoot,",
                      (ROOT / "native/kernel/src/main.rs").read_text())

    def test_user_root_exclusion_lists_all_other_development_scenarios(self):
        import tomllib
        features = tomllib.loads((ROOT / "native/boot/Cargo.toml").read_text())["features"]
        source = (ROOT / "native/boot/src/exit.rs").read_text()
        guard = source.split('feature = "development-user-root",', 1)[1].split('compile_error!', 1)[0]
        others = set(features) - {"default", "development-transfer", "development-user-root"}
        self.assertEqual(len(others), 22)
        self.assertEqual(set(re.findall(r'feature = "([^"]+)"', guard)), others)


if __name__ == "__main__":
    unittest.main()
