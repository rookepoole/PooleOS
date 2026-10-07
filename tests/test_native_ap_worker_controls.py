"""Execute native AP-worker boundaries and challenge recorded qualification."""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_scheduler_ap_workers as workers
from tools import qualify_native_kernel_scheduler_ap_workers as qualifier
from tools import pooleos_release_gate as gate
from tests.test_native_deferred_controls import recorded_deferred_mutations

ROOT = Path(__file__).resolve().parents[1]


class NativeApWorkerControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pksched5-controls-test-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.receipt = qualifier._run_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT, cls.work / "baseline")
        cls.library = qualifier._build_native_control_library(qualifier.DEFAULT_TOOLCHAIN_ROOT, cls.work / "library")

    def test_actual_native_module_verifies_fifty_nine_boundary_cases(self):
        self.assertEqual(0, self.receipt["exit_code"])
        self.assertEqual(59, self.receipt["verified_cases_total"])
        self.assertEqual([workers.expected_controls()[i] for i in workers.NATIVE_CONTROL_INDICES], self.receipt["controls"])
        self.assertEqual(self.receipt["controls"], workers.parse_native_control_output("\n".join(self.receipt["lines"]) + "\n"))
        for source in self.receipt["sources"]:
            self.assertEqual(workers.file_binding(ROOT, source["path"]), source)

    def test_parser_rejects_missing_reordered_or_fabricated_results(self):
        lines = self.receipt["lines"]
        hostile = [[], lines[:-1], lines + lines[:1], list(reversed(lines)), ["unrelated"] + lines]
        for i in range(14):
            changed = list(lines)
            changed[i] = changed[i].replace("verified=", "verified=0")
            hostile.append(changed)
        for candidate in hostile:
            with self.subTest(candidate=candidate), self.assertRaises(workers.KernelSchedulerApWorkersError):
                workers.parse_native_control_output("\n".join(candidate) + "\n")

    def test_each_disabled_native_boundary_is_detected(self):
        source = (ROOT / "native/kernel/src/scheduler_ap_workers.rs").read_text(encoding="utf-8")
        mutations = (
            ("TYPED-CALL-ALLOWLIST", None, "vector == 64 && sample != 0", "sample != 0"),
            ("TOP-HALF-CONTEXT", None, "|| context.worker_context", "|| false"),
            ("DISPATCH-BEFORE-EOI", None, "|| permit.eoi_epoch != self.eoi_epoch", "|| false"),
            ("DUPLICATE-WORK", None, "&& slot.request.key == request.key", "&& false"),
            ("QUEUED-CANCEL", None, "self.complete_terminal(index, WorkState::Cancelled, 0)?;", "let _ = index;"),
            ("REMOTE-CANCEL", None, "let state = if self.slots[index].cancel_requested {", "let state = if false {"),
            ("ACK-BINDING", ("fn acknowledge_inner(", "fn commit_acknowledgement("), "|| ack.sequence != ticket.request_sequence", "|| false"),
            ("OFFLINE-TIMEOUT", None, "|| self.offline_pending != Some(ticket)", "|| false"),
            ("SOURCE-QUEUE-ROLLBACK", None, "self.slots[index].state = WorkState::Queued;", "self.slots[index].state = WorkState::Completed;"),
            ("LATE-ACK", ("pub fn reject_stale_ack(", "pub fn reclaim("), "|| ack.sequence != ticket.request_sequence", "|| false"),
            ("FAIRNESS-BOUND", None, "if self.high_bypass[target] >= MAX_HIGH_BYPASS", "if false"),
            ("FLUSH-WATERMARK", ("pub fn flush_complete(", "pub fn stage_dispatch("), "slot.state == WorkState::Free", "true"),
            ("RECLAIM-GENERATION", None, "if retired_generation != next_service_generation", "if false"),
            ("STALE-ID", None, "|| self.slots[index].generation != id.generation", "|| false"),
        )
        for group, bounds, old, new in mutations:
            with self.subTest(group=group):
                scope = qualifier._scope(source, *bounds) if bounds else source
                self.assertEqual(1, scope.count(old))
                mutated = source.replace(scope, scope.replace(old, new, 1), 1)
                executable, env = qualifier._build_native_control_probe(
                    qualifier.DEFAULT_TOOLCHAIN_ROOT, self.work / group, mutated.encode("utf-8"), self.library)
                result = subprocess.run([str(executable), group], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, check=False, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                output = result.stdout.decode("utf-8", errors="replace")
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("panicked", output)
                self.assertTrue("assertion" in output or "`Err` value: Invariant" in output, output)
                self.assertNotIn("PKSCHED5:CONTROL PASS", output)

    def test_empty_or_disabled_rejection_control_cannot_pass(self):
        for operations in ([], [lambda: None]):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._require_rejections("disabled", operations)

    def test_source_mutations_detect_disabled_auditor(self):
        audit = qualifier._source_audit()
        texts = {n: (ROOT / v["path"]).read_text(encoding="utf-8") for n, v in audit["files"].items()}
        self.assertEqual([workers.expected_controls()[i] for i in workers.SOURCE_CONTROL_INDICES], qualifier._source_controls(texts))
        with patch.object(qualifier, "_audit_source_text", return_value={}):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._source_controls(texts)


class ApWorkerReceiptTests(unittest.TestCase):
    def test_runtime_and_actual_gate_reject_all_corrupted_records(self):
        baseline = workers.read_json(ROOT / workers.READINESS_RELATIVE)
        self.assertEqual([], workers.readiness_errors(baseline))
        self.assertTrue(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])
        count = 0
        for family, label, candidate in recorded_deferred_mutations(baseline):
            with self.subTest(family=family, case=label), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(workers.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])
                count += 1
        self.assertEqual(294, count)

    def test_native_source_linked_and_profile_records_fail_closed(self):
        baseline = workers.read_json(ROOT / workers.READINESS_RELATIVE)
        self.assertEqual([], workers.readiness_errors(baseline))
        paths = [("build",), ("build", "kernel_entry")]
        for section in ("native_control_probe", "audit_controls", "source_audit", "linked_invlpg_audit"):
            paths.append(("build", section))
            paths.extend(("build", section, key) for key in baseline["build"][section])
        paths.extend(("execution", key) for key in ("application_processor_count", "worker_count", "host_environment_count",
            "qemu_sha256", "firmware_code_sha256", "vars_template_sha256"))
        for path in paths:
            candidate = copy.deepcopy(baseline)
            target = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = None
            with self.subTest(path=path), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(workers.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])

    def test_aggregate_identity_and_accounting_are_independent(self):
        baseline = workers.read_json(ROOT / workers.READINESS_RELATIVE)
        self.assertTrue(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])
        paths = [("build", "linked_invlpg_audit", key) for key in (
            "canonical_sha256", "relocation_count", "invlpg_instruction_count", "runtime_execution_count",
            "remote_shootdown_invlpg_instruction_count", "successor_profile_executed", "status")]
        for path in paths:
            candidate = copy.deepcopy(baseline)
            candidate[path[0]][path[1]][path[2]] = None
            with self.subTest(path=path), patch.object(workers, "readiness_errors", return_value=[]), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertFalse(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])
        for value in (1327, 1323.0):
            candidate = copy.deepcopy(baseline)
            candidate["build"]["linked_invlpg_audit"]["relocation_count"] = value
            with patch.object(workers, "readiness_errors", return_value=[]), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertFalse(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])
        candidate = copy.deepcopy(baseline)
        candidate["negative_controls"][0]["case_count"] += 1
        with patch.object(workers, "readiness_errors", return_value=[]), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
            self.assertFalse(gate.check_native_kernel_scheduler_ap_workers_readiness()["ok"])

    def test_valid_calendar_dates_remain_admissible(self):
        baseline = workers.read_json(ROOT / workers.READINESS_RELATIVE)
        for value in ("2026-09-30", "2024-02-29"):
            candidate = copy.deepcopy(baseline)
            candidate["status_date"] = value
            self.assertEqual([], workers.readiness_errors(candidate))
