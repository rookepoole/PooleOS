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
        # Synthetic PKUSER10 parser case built on an immutable historical prefix.
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
        self.markers[35] = self.markers[35].replace("cr3_writes=2", "cr3_writes=365").replace(
            "released_pages=13 scrubbed_data_pages=6", "released_pages=590 scrubbed_data_pages=271")
        for index,(kind,value,calls) in enumerate((("exit",42,2),("fault",6,0),("fault",13,0),("fault",14,0))):
            self.markers.insert(35+index, f"POOLEOS:KERNEL:USER-TASK PASS contract=PKUSER8 slot=0 generation={index+1} "
                f"root={root} reason={kind} value={value} syscalls={calls} cpl=3 stale_denials={int(index>0)} "
                "restart_denied=1 repeat_reap_denied=1 retained_free_denials=5 entry_quiesced=1 root_restored=1 "
                "released_pages=13 scrubbed_data_pages=6 production=0")
        for index,(kind,value,vector) in enumerate((("exit",42,0),("fault",6,0),("cancel",0,0),("limit",64,0),
                ("return",2,256),("return",2,256),("return",3,256),("return",3,256),("return",1,256),("return",2,64),
                ("fault",0,0),("fault",1,0),("fault",3,0),("fault",13,0))):
            cancel = int(index == 2)
            self.markers.insert(39+index, f"POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER10 scheduler=PKSCHED1 "
                f"round={index} first={kind} value={value} root0={root} root1=0x0000000005000000 "
                f"dispatches={11-cancel} preempt0=3 preempt1=6 progress0=100 progress1=200 "
                f"ticks0={350-50*cancel} ticks1=650 survivor_after_stop=2 cr3_writes={22-cancel} return_vector={vector} "
                "survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
        self.markers.insert(53, f"POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER10 scheduler=PKSCHED1 round=14 first=quarantine value=0 root0={root} root1=0x0000000005000000 dispatches=8 preempt0=0 preempt1=6 progress0=0 progress1=200 ticks0=100 ticks1=650 survivor_after_stop=6 cr3_writes=16 return_vector=0 survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
        self.markers.insert(54, f"POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER10 scheduler=PKSCHED1 round=15 first=watchdog value=65 root0={root} root1=0x0000000005000000 dispatches=8 preempt0=0 preempt1=6 progress0=0 progress1=200 ticks0=500 ticks1=650 survivor_after_stop=6 cr3_writes=16 return_vector=0 survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
        self.markers.insert(55, "POOLEOS:KERNEL:USER-TIMER-DRAIN PASS contract=PKUSER12 pending=1 late=1 quarantines=1 retries=1 retained_pages=13 free_denials=5 restart_denials=2 reap_denials=1 peer_exit=84 deliveries=3 eois=3 empty_irr_isr=1 kernel_window=1 detached_after_shutdown=1 if=0 production=0")
        self.markers.insert(55, "POOLEOS:KERNEL:USER-SPAWN PASS contract=PKUSER11 quota_failures=1 quota_released_pages=5 quota_scrubbed_pages=5 after_effect_failures=6 cleanup_quarantines=6 cleanup_retries=6 retained_free_denials=30 released_pages=83 scrubbed_pages=83 peer_resumed=1 peer_exit=84 cpu_exposures=0 production=0")
        self.markers.insert(57, "POOLEOS:KERNEL:USER-RUNTIME PASS contract=PKUSER13 samples=169 terminal_samples=30 duplicate_denials=169 ticks=15850 preempt_ticks=13800 terminal_ticks=1950 failed_cleanup_ticks=100 failed_cleanup_samples=1 scheduler_match=1 pending=0 unknown=0 clock=hpet charge_window=arm_to_event production=0")
        self.markers.insert(58, "POOLEOS:KERNEL:USER-WATCHDOG PASS contract=PKUSER14 source=hpet_msi local_masked=1 recoveries=1 arms=169 stops=169 restores=169 ticks=500 deadline_ns=50000000 peer_exit=84 shared_apic=1 requires_if=1 nmi=0 production=0")
        self.markers.insert(59, f"POOLEOS:KERNEL:USER-UNKNOWN PASS contract=PKUSER15 injection=returned_sample_loss unmeasured=1 measured0=0 total0=unknown pending=0 duplicate_denied=1 stale_denied=1 cpu_denied=1 zero_charge_denied=1 requeue_denied=1 outcome_denied=1 cleanup_retry=1 retained_pages=13 free_denials=5 root0={root} root1=0x0000000005000000 dispatches=8 peer_preemptions=6 peer_progress=200 peer_ticks=650 cr3_writes=16 peer_exit=84 scheduler_match=1 retired_unknown=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
        self.summary = probe.validate_markers(self.markers)

    def test_unknown_time_is_null_not_zero_and_recovery_requires_retired_debt(self):
        self.assertTrue(self.summary["unknown_runtime_recovery"])
        self.assertIsNone(self.summary["unknown_task_total_ticks"])
        self.assertEqual(self.summary["unmeasured_dispatches"],1)
        self.assertFalse(self.summary["complete_runtime_tick_accounting"])
        self.assertFalse(self.summary["physical_clock_failure_recovery"])
        for field in ("unmeasured","duplicate_denied","stale_denied","cpu_denied","zero_charge_denied",
                "requeue_denied","outcome_denied","cleanup_retry","retained_pages","free_denials",
                "peer_exit","scheduler_match","retired_unknown","released_pages","scrubbed_data_pages"):
            self.reject(59,field,"0")
        for field,value in (("total0","0"),("total0","estimated"),("measured0","1"),("pending","1"),
                ("injection","hardware_clock_failure"),("production","1"),("root0","0x0000000000000000"),
                ("root1",f"0x{self.summary['original_root']:016X}"),("root1","0x0000000100000000"),
                ("dispatches","7"),("peer_preemptions","5"),("peer_progress","0"),("peer_ticks","0"),
                ("cr3_writes","15")):
            self.reject(59,field,value)
        with self.assertRaises(ValueError):
            probe.validate_markers(self.markers[:59]+self.markers[60:])

    def test_unknown_constructor_runs_after_measured_suite_releases_its_stack_frame(self):
        parent = (ROOT/"native/kernel/src/user_root_probe.rs").read_text(encoding="utf-8")
        measured = (ROOT/"native/kernel/src/user_root_probe/peer_driver.rs").read_text(encoding="utf-8")
        recovery = (ROOT/"native/kernel/src/user_root_probe/peer_driver/unknown.rs").read_text(encoding="utf-8")
        self.assertLess(parent.index("peer_driver::run_all("), parent.index("peer_driver::unknown::run("))
        self.assertNotIn("unknown::run(", measured)
        self.assertIn("#[inline(never)]\npub fn run_all(", measured)
        self.assertIn("#[inline(never)]\npub(crate) fn run(", recovery)

    def test_runtime_settlement_requires_all_dispatches_terminal_and_failed_cleanup_charges(self):
        self.assertTrue(self.summary["bounded_runtime_accounting"])
        self.assertFalse(self.summary["pure_user_instruction_time"])
        self.assertEqual(self.summary["runtime_failed_cleanup_ticks"],100)
        for field in ("samples","terminal_samples","duplicate_denials","ticks","preempt_ticks",
                "terminal_ticks","failed_cleanup_ticks","failed_cleanup_samples","scheduler_match"):
            self.reject(57,field,"0")
        for field in ("pending","unknown","production"):
            self.reject(57,field,"1")
        self.reject(57,"clock","tsc")
        self.reject(57,"charge_window","user_only")
        self.reject(53,"ticks0","0")
        with self.assertRaises(ValueError):
            probe.validate_markers(self.markers[:57]+self.markers[59:])

    def test_hpet_backup_proof_requires_exact_owner_accounting_and_surviving_peer(self):
        self.assertTrue(self.summary["bounded_hpet_backup_recovery"])
        self.assertFalse(self.summary["independent_missing_interrupt_watchdog"])
        self.assertFalse(self.summary["nmi_recovery"])
        for field in ("local_masked","recoveries","arms","stops","restores","ticks","deadline_ns",
                "peer_exit","shared_apic","requires_if"):
            self.reject(58,field,"0")
        for field in ("nmi","production"):
            self.reject(58,field,"1")
        for field,value in (("preempt0","1"),("ticks0","499"),("value","64"),("first","exit"),
                ("survivor_after_stop","5"),("progress0","1")):
            self.reject(54,field,value)
        with self.assertRaises(ValueError):
            probe.validate_markers(self.markers[:58]+self.markers[59:])

    def test_hpet_msi_launch_option_is_explicit_allowlisted_and_boolean(self):
        from tools.qualify_native_pooleboot import _hpet_msi_options
        self.assertEqual(_hpet_msi_options(False), [])
        self.assertEqual(_hpet_msi_options(True), ["-global","hpet.msi=on"])
        for invalid in (0, 1, None, "on", ["-global","anything"]):
            with self.assertRaises(ValueError):
                _hpet_msi_options(invalid)

    def reject(self, index, field, value):
        changed = self.markers.copy()
        changed[index], count = re.subn(r"\b" + field + r"=[^ ]+", field + "=" + value, changed[index])
        self.assertEqual(count, 1)
        with self.assertRaises((ValueError, KernelTransferError)):
            probe.validate_markers(changed)

    def test_synthetic_trace_has_only_bounded_user_entry_claims(self):
        self.assertEqual((self.summary["root_probe_cpl"], self.summary["cpl"]), (0, 3))
        self.assertEqual(self.summary["cr3_writes"], 365)
        self.assertTrue(self.summary["ring3_executed"])
        self.assertTrue(self.summary["user_timer_preemption"])
        self.assertFalse(self.summary["production_ready"])

    def test_order_missing_duplicate_and_every_live_field_rejected(self):
        self.assertGreaterEqual(probe.negative_controls(self.markers), 25)

    def test_wrong_selector_rejected(self):
        for value in ("0", "22", "24", "255"):
            self.reject(23, "trap_scenario", value)

    def test_spawn_failures_quarantine_retries_and_peer_continuation_are_required(self):
        self.assertEqual(self.summary["spawn_cleanup_retries"], 6)
        self.assertTrue(self.summary["spawn_peer_continuation"])
        for field in ("quota_failures", "quota_released_pages", "quota_scrubbed_pages", "after_effect_failures", "cleanup_quarantines", "cleanup_retries",
                "retained_free_denials", "released_pages", "scrubbed_pages", "peer_resumed", "peer_exit"):
            self.reject(55, field, "0")
        self.reject(55, "cpu_exposures", "1")
        self.reject(55, "production", "1")
        for changed in (self.markers[:55] + self.markers[56:],
                self.markers[:55] + [self.markers[56], self.markers[55]] + self.markers[57:]):
            with self.assertRaises(ValueError): probe.validate_markers(changed)


    def test_timer_recovery_requires_owned_drain_quarantine_and_survivor(self):
        self.assertEqual(self.summary["timer_quarantine_retries"], 1)
        self.assertEqual(self.summary["timer_quarantine_retained_pages"], 13)
        for field in ("pending","late","quarantines","retries","retained_pages","free_denials",
                "restart_denials","reap_denials","peer_exit","empty_irr_isr","kernel_window","detached_after_shutdown"):
            self.reject(56, field, "0")
        for field in ("deliveries","eois"):
            for value in ("0","2","4","257",str(1<<64)):
                self.reject(56,field,value)
        self.reject(56,"if","1")
        self.reject(56,"production","1")
        for field,value in (("preempt0","1"),("progress0","1"),("ticks0","1"),
                ("survivor_after_stop","5"),("first","exit"),("dispatches","7")):
            self.reject(53,field,value)
        with self.assertRaises(ValueError):
            probe.validate_markers(self.markers[:56]+self.markers[57:])

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
        self.reject(60, "restored", f"0x{self.summary['candidate_root']:016X}")

    def test_sentinel_binds_candidate_and_generation(self):
        self.reject(30, "stack_probe", f"0x{self.summary['stack_probe'] ^ 1:016X}")
        self.reject(29, "generation", str(self.summary["generation"] + 1))

    def test_generation_has_u64_nonzero_bounds(self):
        for value in ("0", str(1 << 64)):
            self.reject(29, "generation", value)

    def test_numeric_claims_cannot_be_promoted(self):
        for index, field, value in ((29, "pages", "14"), (29, "temporary_aliases", "1"),
                (30, "cpl", "3"), (30, "if", "1"), (30, "ring3", "1"),
                (60, "cr3_writes", "1"), (60, "allocated_pages", "0"),
                (60, "released_pages", "12"), (60, "scrubbed_data_pages", "5"),
                (60, "production", "1")):
            self.reject(index, field, value)

    def test_timer_root_delivery_eoi_quiescence_and_mmio_claims_cannot_change(self):
        for field, value in (("cr3", f"0x{self.summary['original_root']:016X}"),
                ("deliveries", "0"), ("eois", "2"), ("quiesced", "0"),
                ("mmio_pages", "3"), ("if", "1"), ("ring3", "1")):
            self.reject(31, field, value)

    def test_retained_acpi_accounting_has_nonzero_bounded_equality(self):
        for value in ("0", "2", "20", str(1 << 64)):
            self.reject(60, "retained_acpi_pages", value)

    def test_user_entry_cpl_traps_state_cleanup_and_return_cannot_change(self):
        for field,value in (("cpl","0"),("traps","6"),("private_rsp0","0"),("gpr_zero","14"),
                ("fp_cleared","0"),("cli_denied","0"),("io_denied","0"),("syscall_denied","0"),
                ("supervisor_fault","0"),("nx_fault","0"),("kernel_return","0"),
                ("descriptors_detached","0"),("if","1"),("production","1")):
            self.reject(32,field,value)

    def test_user_entry_root_is_bound_to_candidate(self):
        self.reject(32,"cr3",f"0x{self.summary['original_root']:016X}")

    def test_missing_user_entry_and_old_cpl0_final_cannot_claim_execution(self):
        self.reject(60,"ring3","0")
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

    def test_task_identity_generations_and_roots_cannot_be_replayed(self):
        for index in range(35,39):
            for field,value in (("generation","0"),("generation","5"),("slot","1"),("root","0x0000000000000000"),
                                ("root","0x0000000000000001"),("root","0x0000000100000000")):
                self.reject(index,field,value)
        changed=self.markers.copy();changed[36]=changed[35]
        with self.assertRaises(ValueError):probe.validate_markers(changed)

    def test_task_termination_cleanup_and_accounting_cannot_be_promoted(self):
        self.assertEqual((self.summary["normal_exits"],self.summary["fault_terminations"]),(1,3))
        self.assertTrue(self.summary["peer_scheduling"])
        for index in range(35,39):
            for field,value in (("syscalls","3"),("value","99"),("cpl","0"),("restart_denied","0"),
                    ("repeat_reap_denied","0"),("retained_free_denials","4"),("entry_quiesced","0"),
                    ("root_restored","0"),("released_pages","12"),("scrubbed_data_pages","5"),("production","1")):
                self.reject(index,field,value)
        self.reject(35,"reason","fault");self.reject(36,"reason","exit")

    def test_missing_reordered_or_old_syscall_trace_cannot_claim_task_termination(self):
        for changed in (self.markers[:35]+self.markers[39:],self.markers[:36]+self.markers[37:],
                self.markers[:36]+[self.markers[37],self.markers[36]]+self.markers[38:]):
            with self.assertRaises(ValueError):probe.validate_markers(changed)

    def test_peer_roots_are_distinct_owned_shape_and_ordered(self):
        for index in range(39,53):
            for field,value in (("root0","0x0000000000000000"),("root1","0x0000000000000001"),
                    ("root1","0x0000000100000000"),("root1",f"0x{self.summary['candidate_root']:016X}"),
                    ("root0",f"0x{self.summary['original_root']:016X}"),("round","99")):
                self.reject(index,field,value)
        changed=self.markers.copy(); changed[40],changed[41]=changed[41],changed[40]
        with self.assertRaises(ValueError): probe.validate_markers(changed)
        with self.assertRaises(ValueError): probe.validate_markers(self.markers[:39]+self.markers[53:])

    def test_peer_dispatch_preemption_and_root_writes_are_conserved(self):
        self.assertEqual(self.summary["peer_preemptions"],138)
        for index in range(39,53):
            for field,value in (("dispatches","65"),("dispatches","1"),("preempt0","0"),
                    ("preempt1","1"),("cr3_writes","0"),("progress0","0"),("progress1",str(1<<64)),
                    ("ticks0","0"),("ticks1",str(1<<64))):
                self.reject(index,field,value)
        self.reject(41,"preempt0","4")
        self.reject(60,"cr3_writes","96")

    def test_invalid_return_reason_vector_and_peer_survival_are_bound(self):
        self.assertEqual(self.summary["invalid_return_terminations"], 6)
        self.assertEqual(self.summary["additional_user_exception_terminations"], 4)
        for index in range(43,49):
            for field, value in (("first", "fault"), ("value", "99"), ("return_vector", "0")):
                self.reject(index, field, value)
        self.reject(48, "return_vector", "256")
        for index in range(49,53):
            self.reject(index, "return_vector", "64")
            self.reject(index, "value", "8")

    def test_private_stack_exception_routes_keep_system_faults_out(self):
        source = (ROOT / "native/kernel/src/arch/x86_64/user.rs").read_text()
        table = source.split("for (vector, handler) in [",1)[1].split("] {",1)[0]
        vectors = set(map(int, re.findall(r"\(\s*([0-9]+),", table)))
        self.assertEqual(vectors, {0,1,3,4,5,6,11,12,13,14,16,17,19})
        self.assertIn("IdtGate::interrupt(handler, 0)", source)
        self.assertIn("if vector == 3 {", source)
        self.assertIn("gate.attributes |= 0x60;", source)
        self.assertIn("read_rflags() & syscall::FMASK != 0", source)

    def test_tcg_stack_access_deviation_never_claims_architectural_ss_delivery(self):
        self.assertFalse(self.summary["architectural_stack_fault_qualified"])
        self.assertEqual(self.summary["observed_stack_access_vector"], 13)
        self.assertEqual(self.summary["new_native_exception_vectors"], [0,1,3])
        self.assertEqual(self.summary["peer_rounds"][13]["value"], 13)
        self.reject(52, "value", "12")

    def test_trap_entry_clears_inherited_ac_before_rust_and_preserves_saved_frame(self):
        source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text()
        entry = source.split("poole_trap_common:",1)[1].split(".size poole_trap_common",1)[0]
        self.assertLess(entry.index("push r15"), entry.index("pushfq"))
        self.assertLess(entry.index("and qword ptr [rsp], -262145"), entry.index("popfq"))
        self.assertLess(entry.index("popfq"), entry.index("call poole_kernel_trap_dispatch"))
        self.assertLess(entry.index("cld"), entry.index("call poole_kernel_trap_dispatch"))

    def test_peer_survivor_progress_after_each_stop_is_required(self):
        self.assertEqual(self.summary["peer_survival_cases"],17)
        for index in range(39,53):
            for field,value in (("survivor_after_stop","0"),("survivor_after_stop","7"),
                    ("survivor_exit","255"),("states_preserved","0"),("root_restored","0"),
                    ("released_pages","25"),("scrubbed_data_pages","11"),("production","1")):
                self.reject(index,field,value)
        self.reject(42,"first","exit");self.reject(42,"value","65")


if __name__ == "__main__":
    unittest.main()
