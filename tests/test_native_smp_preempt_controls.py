"""Execute native SMP-preemption boundaries and reject corrupted evidence."""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_scheduler_smp_preempt as profile
from tools import qualify_native_kernel_scheduler_smp_preempt as qualifier
from tools import pooleos_release_gate as gate
from tests.test_native_deferred_controls import recorded_deferred_mutations

ROOT = Path(__file__).resolve().parents[1]


class NativePreemptControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pksched6-controls-test-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.receipt = qualifier._run_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT, cls.work / "baseline")
        cls.library = qualifier._build_native_control_library(qualifier.DEFAULT_TOOLCHAIN_ROOT, cls.work / "library")

    def test_actual_native_controller_verifies_all_boundaries(self):
        self.assertEqual(0, self.receipt["exit_code"])
        self.assertEqual(61, self.receipt["verified_cases_total"])
        self.assertEqual([profile.expected_controls()[i] for i in profile.NATIVE_CONTROL_INDICES], self.receipt["controls"])
        for source in self.receipt["sources"]:
            self.assertEqual(profile.file_binding(ROOT, source["path"]), source)

    def test_parser_rejects_missing_reordered_or_fabricated_results(self):
        lines = self.receipt["lines"]
        hostile = [[], lines[:-1], lines + lines[:1], list(reversed(lines)), ["unrelated"] + lines]
        for i in range(15):
            changed = list(lines)
            changed[i] = changed[i].replace("verified=", "verified=0")
            hostile.append(changed)
        for candidate in hostile:
            with self.subTest(candidate=candidate), self.assertRaises(profile.KernelSchedulerSmpPreemptError):
                profile.parse_native_control_output("\n".join(candidate) + "\n")

    def test_disabled_native_safeguards_are_detected(self):
        source = (ROOT / "native/kernel/src/scheduler_smp_preempt.rs").read_text(encoding="utf-8")
        mutations = (
            ("FRAME-CPU", "if !lane.online || lane.cpu != frame.cpu {", "if false {"),
            ("FRAME-APIC", "if frame.apic_id != lane.apic_id {", "if false {"),
            ("FRAME-EPOCH", "frame.frame_epoch != next_frame_epoch ||", "false ||"),
            ("TIMER-EPOCH", "frame.timer_epoch != next_timer_epoch", "false"),
            ("FRAME-STACK", "|| frame.frame_bytes == 0", "|| false"),
            ("EVENT-DEADLINE", "if event.due_tick <= lane.timer_ticks {", "if false {"),
            ("EVENT-ORDER", "if prior_key <= event_key {", "if true {"),
            ("ACK-BINDING", "self.scheduler.acknowledge_reschedule(ticket, ack)?;", "self.scheduler.acknowledge_reschedule(ticket, canonical_reschedule_ack(ticket))?;"),
            ("ACK-GATED-OWNER", "self.remote_reschedule_acks = increment(self.remote_reschedule_acks)?;", "return Ok(());"),
            ("OFFLINE-TIMEOUT", "self.timeout_rollbacks = increment(self.timeout_rollbacks)?;", "self.timeout_rollbacks = 0;"),
            ("SOURCE-QUEUE-ROLLBACK", "self.scheduler.timeout(ticket)?;", "let _ = ticket;"),
            ("LATE-ACK", "let mut next = *self;\n        next.acknowledge_reschedule_inner(ticket, ack)?;", "if self.pending_remote.is_none() { return Ok(()); }\n        let mut next = *self;\n        next.acknowledge_reschedule_inner(ticket, ack)?;"),
            ("WATCHDOG-BOUND", "|| self.maximum_watchdog_age > MAX_WATCHDOG_TICKS", "|| false"),
            ("STARVATION-BOUND", "if ticket.is_none() && self.lanes[cpu.index()].quantum_remaining == 0 {", "if false {"),
            ("DUPLICATE-RUNNABLE", ".any(|e| e.sequence == event.sequence)", ".any(|_| false)"),
        )
        for group, old, new in mutations:
            with self.subTest(group=group):
                self.assertEqual(1, source.count(old))
                executable, env = qualifier._build_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT,
                    self.work / group, source.replace(old, new, 1).encode("utf-8"), self.library)
                result = subprocess.run([str(executable), group], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, check=False, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                output = result.stdout.decode("utf-8", errors="replace")
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("panicked", output)
                self.assertNotIn("PKSCHED6:CONTROL PASS", output)

    def test_empty_or_disabled_rejection_control_cannot_pass(self):
        for operations in ([], [lambda: None]):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._require_rejections("disabled", operations)

    def test_source_controls_detect_disabled_auditor(self):
        audit = qualifier._source_audit()
        texts = {n: (ROOT / v["path"]).read_text(encoding="utf-8") for n, v in audit["files"].items()}
        self.assertEqual([profile.expected_controls()[i] for i in profile.SOURCE_CONTROL_INDICES], qualifier._source_controls(texts))
        with patch.object(qualifier, "_audit_source_text", return_value={}):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._source_controls(texts)


class PreemptReceiptTests(unittest.TestCase):
    def test_runtime_and_gate_reject_corrupted_records(self):
        baseline = profile.read_json(ROOT / profile.READINESS_RELATIVE)
        self.assertEqual([], profile.readiness_errors(baseline))
        self.assertTrue(gate.check_native_kernel_scheduler_smp_preempt_readiness()["ok"])
        count = 0
        for family, label, candidate in recorded_deferred_mutations(baseline):
            with self.subTest(family=family, case=label), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(profile.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_scheduler_smp_preempt_readiness()["ok"])
                count += 1
        self.assertEqual(288, count)

    def test_native_audit_and_profile_records_fail_closed(self):
        baseline = profile.read_json(ROOT / profile.READINESS_RELATIVE)
        self.assertEqual([], profile.readiness_errors(baseline))
        paths = [("build",), ("build", "kernel_entry")]
        for section in ("native_control_probe", "audit_controls", "source_audit", "linked_invlpg_audit"):
            paths.append(("build", section))
            paths.extend(("build", section, key) for key in baseline["build"][section])
        paths.extend(("execution", key) for key in ("application_processor_count", "timer_lane_count", "frame_lane_count",
            "live_reschedule_ipi_count", "host_environment_count", "qemu_sha256", "firmware_code_sha256", "vars_template_sha256"))
        for path in paths:
            candidate = copy.deepcopy(baseline)
            target = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = None
            with self.subTest(path=path), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(profile.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_scheduler_smp_preempt_readiness()["ok"])

    def test_aggregate_identity_and_accounting_are_independent(self):
        baseline = profile.read_json(ROOT / profile.READINESS_RELATIVE)
        self.assertTrue(gate.check_native_kernel_scheduler_smp_preempt_readiness()["ok"])
        candidates = []
        for key in ("canonical_sha256", "relocation_count", "invlpg_instruction_count", "runtime_execution_count",
                    "remote_shootdown_invlpg_instruction_count", "successor_profile_executed", "status"):
            candidate = copy.deepcopy(baseline)
            candidate["build"]["linked_invlpg_audit"][key] = None
            candidates.append(candidate)
        for value in (1327, 1326.0, True):
            candidate = copy.deepcopy(baseline)
            candidate["build"]["linked_invlpg_audit"]["relocation_count"] = value
            candidates.append(candidate)
        candidate = copy.deepcopy(baseline)
        candidate["negative_controls"][0]["case_count"] += 1
        candidates.append(candidate)
        for candidate in candidates:
            with patch.object(profile, "readiness_errors", return_value=[]), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertFalse(gate.check_native_kernel_scheduler_smp_preempt_readiness()["ok"])

    def test_canonical_calendar_dates_remain_admissible(self):
        baseline = profile.read_json(ROOT / profile.READINESS_RELATIVE)
        for value in ("2026-10-04", "2024-02-29"):
            candidate = copy.deepcopy(baseline)
            candidate["status_date"] = value
            self.assertEqual([], profile.readiness_errors(candidate))
