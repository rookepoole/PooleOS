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
        # Synthetic PKUSER7 parser case built on an immutable historical prefix.
        # Only the qualifier's fresh guest logs are native execution evidence.
        root = probe.ACTIVE.fullmatch(self.markers[30])[1]
        self.markers.insert(31, f"POOLEOS:KERNEL:USER-ROOT-TIMER PASS contract=PKUSER4 cr3={root} "
            "deliveries=3 eois=3 mmio_pages=2 quiesced=1 if=0 ring3=0")
        self.markers[32] = self.markers[32].replace("allocated_pages=0",
            "allocated_pages=1 retained_acpi_pages=1")
        self.markers[32] = self.markers[32].replace("ring3=0", "ring3=1")
        self.markers.insert(32, f"POOLEOS:KERNEL:USER-ENTRY PASS contract=PKUSER5 cr3={root} "
            "cpl=3 traps=7 private_rsp0=1 gpr_zero=15 fp_cleared=1 cli_denied=1 io_denied=1 "
            "syscall_denied=1 supervisor_fault=1 nx_fault=1 kernel_return=1 descriptors_detached=1 if=0 production=0")
        self.markers.insert(33, f"POOLEOS:KERNEL:USER-PREEMPT PASS contract=PKUSER6 cr3={root} "
            "cpl=3 deliveries=3 eois=3 resumes=2 first_progress=10 last_progress=100 "
            "private_rsp0=1 gpr_preserved=14 fp_preserved=1 timer_quiesced=1 forced_return=1 if=0 production=0")
        self.markers.insert(34, f"POOLEOS:KERNEL:USER-CALL PASS contract=PKUSER7 abi=PSABI1 profile=development version=1 cr3={root} "
            "calls=12 ok=3 version_denied=1 unknown=1 arguments=4 faults=3 read_faults=1 write_faults=2 "
            "cpl=3 entry=syscall return=iretq max_copy=256 input_atomic=1 output_prefix=1 completion_traps=1 msrs_cleared=1 if=0 production=0")
        self.summary = probe.validate_markers(self.markers)

    def reject(self, index, field, value):
        changed = self.markers.copy()
        changed[index], count = re.subn(r"\b" + field + r"=[^ ]+", field + "=" + value, changed[index])
        self.assertEqual(count, 1)
        with self.assertRaises((ValueError, KernelTransferError)):
            probe.validate_markers(changed)

    def test_synthetic_trace_has_only_bounded_user_entry_claims(self):
        self.assertEqual((self.summary["root_probe_cpl"], self.summary["cpl"]), (0, 3))
        self.assertEqual(self.summary["cr3_writes"], 2)
        self.assertTrue(self.summary["ring3_executed"])
        self.assertTrue(self.summary["user_timer_preemption"])
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
        self.reject(35, "restored", f"0x{self.summary['candidate_root']:016X}")

    def test_sentinel_binds_candidate_and_generation(self):
        self.reject(30, "stack_probe", f"0x{self.summary['stack_probe'] ^ 1:016X}")
        self.reject(29, "generation", str(self.summary["generation"] + 1))

    def test_generation_has_u64_nonzero_bounds(self):
        for value in ("0", str(1 << 64)):
            self.reject(29, "generation", value)

    def test_numeric_claims_cannot_be_promoted(self):
        for index, field, value in ((29, "pages", "14"), (29, "temporary_aliases", "1"),
                (30, "cpl", "3"), (30, "if", "1"), (30, "ring3", "1"),
                (35, "cr3_writes", "1"), (35, "allocated_pages", "0"),
                (35, "released_pages", "12"), (35, "scrubbed_data_pages", "5"),
                (35, "production", "1")):
            self.reject(index, field, value)

    def test_timer_root_delivery_eoi_quiescence_and_mmio_claims_cannot_change(self):
        for field, value in (("cr3", f"0x{self.summary['original_root']:016X}"),
                ("deliveries", "0"), ("eois", "2"), ("quiesced", "0"),
                ("mmio_pages", "3"), ("if", "1"), ("ring3", "1")):
            self.reject(31, field, value)

    def test_retained_acpi_accounting_has_nonzero_bounded_equality(self):
        for value in ("0", "2", "20", str(1 << 64)):
            self.reject(35, "retained_acpi_pages", value)

    def test_user_entry_cpl_traps_state_cleanup_and_return_cannot_change(self):
        for field,value in (("cpl","0"),("traps","6"),("private_rsp0","0"),("gpr_zero","14"),
                ("fp_cleared","0"),("cli_denied","0"),("io_denied","0"),("syscall_denied","0"),
                ("supervisor_fault","0"),("nx_fault","0"),("kernel_return","0"),
                ("descriptors_detached","0"),("if","1"),("production","1")):
            self.reject(32,field,value)

    def test_user_entry_root_is_bound_to_candidate(self):
        self.reject(32,"cr3",f"0x{self.summary['original_root']:016X}")

    def test_missing_user_entry_and_old_cpl0_final_cannot_claim_execution(self):
        self.reject(35,"ring3","0")
        changed=self.markers[:32]+self.markers[33:]
        with self.assertRaises(ValueError): probe.validate_markers(changed)

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

    def test_preemption_counts_state_and_root_cannot_be_promoted(self):
        for field,value in (("cr3",f"0x{self.summary['original_root']:016X}"),("cpl","0"),
                ("deliveries","0"),("eois","2"),("resumes","3"),("private_rsp0","0"),
                ("gpr_preserved","13"),("fp_preserved","0"),("timer_quiesced","0"),
                ("forced_return","0"),("if","1"),("production","1")):
            self.reject(33,field,value)

    def test_spinning_progress_must_be_positive_increasing_u64(self):
        for field,value in (("first_progress","0"),("first_progress","100"),
                ("last_progress","10"),("last_progress","9"),("last_progress",str(1<<64))):
            self.reject(33,field,value)

    def test_missing_preemption_marker_does_not_claim_a_user_timer(self):
        with self.assertRaises(ValueError):
            probe.validate_markers(self.markers[:33]+self.markers[34:])

    def test_user_root_exclusion_lists_all_other_development_scenarios(self):
        import tomllib
        features = tomllib.loads((ROOT / "native/boot/Cargo.toml").read_text())["features"]
        source = (ROOT / "native/boot/src/exit.rs").read_text()
        guard = source.split('feature = "development-user-root",', 1)[1].split('compile_error!', 1)[0]
        others = set(features) - {"default", "development-transfer", "development-user-root"}
        self.assertEqual(len(others), 22)
        self.assertEqual(set(re.findall(r'feature = "([^"]+)"', guard)), others)

    def test_syscall_root_version_errors_copy_and_teardown_are_bound(self):
        for field,value in (("cr3",f"0x{self.summary['original_root']:016X}"), ("version","2"),
                ("calls","11"),("ok","4"),("faults","0"),("read_faults","0"),("write_faults","1"),
                ("cpl","0"),("entry","int80"),("return","sysret"),("max_copy","4096"),
                ("input_atomic","0"),("output_prefix","0"),("completion_traps","0"),("msrs_cleared","0")):
            self.reject(34,field,value)

    def test_old_preemption_trace_cannot_claim_syscall_execution(self):
        with self.assertRaises(ValueError):
            probe.validate_markers(self.markers[:34]+self.markers[35:])


if __name__ == "__main__":
    unittest.main()
