"""Execute native PKSCHED3 boundaries and reject corrupted recorded evidence."""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_scheduler_deferred as deferred
from tools import qualify_native_kernel_scheduler_deferred as qualifier
from tools import pooleos_release_gate as gate
from tests.test_native_cpu_entry_provenance import pair_mutations

ROOT = Path(__file__).resolve().parents[1]


def recorded_deferred_mutations(baseline):
    for family in ("exit", "coverage", "evidence"):
        for label, pair in pair_mutations(baseline["execution"], family):
            if label == "exact_marker_match":
                pair["static_markers_exact_match"] = pair.pop("exact_marker_match")
            candidate = copy.deepcopy(baseline)
            candidate["execution"] = pair
            yield family, label, candidate

    def change(path, value):
        candidate = copy.deepcopy(baseline)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return candidate

    for path in (("execution",), ("observation",), ("build", "host_probe"), ("negative_controls",)):
        for value in (None, [], "invalid"):
            yield "shape", str(path) + repr(value), change(path, value)
    for key, value in (("virtual_cpu_count", 1.0), ("dynamic_fields_revalidated", 1),
                       ("cpu_model", "wrong"), ("acceleration", "wrong"),
                       ("deterministic_instruction_clock", 1), ("bsp_only", 1),
                       ("machine", "wrong"), ("profile_id", "wrong")):
        yield "profile", key, change(("execution", key), value)
    for section, fields in baseline["observation"].items():
        yield "observation", section, change(("observation", section), None)
        if section == "transfer_prefix":
            continue
        for key, value in fields.items():
            for label, replacement in (("null", None), ("type", float(value) if type(value) is int else "invalid")):
                path = ("observation", section, key)
                yield "observation", str(path) + label, change(path, replacement)
    for section, fields in baseline["build"]["host_probe"].items():
        if isinstance(fields, dict):
            for key, value in fields.items():
                yield "host-probe", section + "." + key, change(("build", "host_probe", section, key), float(value) if type(value) is int else None)
        else:
            yield "host-probe", section, change(("build", "host_probe", section), None)
    for index, control in enumerate(baseline["negative_controls"]):
        for value in (control["case_count"] + 1, float(control["case_count"])):
            yield "controls", str((index, value)), change(("negative_controls", index, "case_count"), value)
        for key, value in (("status", "fail"), ("expected", "unknown")):
            yield "controls", str((index, key)), change(("negative_controls", index, key), value)
    candidate = copy.deepcopy(baseline)
    candidate["negative_controls"][0]["case_count"] += 1
    candidate["negative_controls"][3]["case_count"] -= 1
    yield "controls", "redistributed", candidate
    for value in (None, [], "invalid"):
        yield "root", repr(value), value
    for value in (None, 7, True, "", "20260907", "2026-9-7", "2026-02-29", "2026-04-31", "2026-13-01", "2026-09-07T00:00:00"):
        yield "date", repr(value), change(("status_date",), value)


class NativeDeferredControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pksched3-controls-test-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.receipt = qualifier._run_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT, cls.work / "baseline")

    def test_actual_native_module_verifies_fifty_boundary_cases(self):
        self.assertEqual(0, self.receipt["exit_code"])
        self.assertEqual(50, self.receipt["verified_cases_total"])
        self.assertEqual(deferred.expected_controls()[15:27], self.receipt["controls"])
        self.assertEqual(self.receipt["controls"], deferred.parse_native_control_output("\n".join(self.receipt["lines"]) + "\n"))
        for source in self.receipt["sources"]:
            self.assertEqual(deferred.file_binding(ROOT, source["path"]), source)

    def test_parser_rejects_missing_reordered_or_fabricated_results(self):
        lines = self.receipt["lines"]
        hostile = [[], lines[:-1], lines + lines[:1], list(reversed(lines)), ["unrelated"] + lines]
        for index in range(12):
            changed = list(lines)
            changed[index] = changed[index].replace("verified=", "verified=0")
            hostile.append(changed)
        for candidate in hostile:
            with self.subTest(candidate=candidate), self.assertRaises(deferred.KernelSchedulerDeferredError):
                deferred.parse_native_control_output("\n".join(candidate) + "\n")

    def test_each_disabled_native_boundary_is_detected(self):
        source = (ROOT / "native/kernel/src/scheduler_deferred.rs").read_text(encoding="utf-8")
        mutations = (
            ("FIXED-CAPACITY", ".position(|slot| slot.state == WorkState::Free)", ".position(|_slot| true)"),
            ("DUPLICATE-SUPPRESSION", "&& slot.request.key == request.key", "&& false"),
            ("TOP-HALF-CONTEXT", "context.interrupt_depth != 1 || !context.interrupts_disabled || !context.queue_lock_held", "false"),
            ("RECURSION", "context.worker_context || self.active_worker != u8::MAX", "false"),
            ("EOI-PERMIT", "permit.eoi_epoch == 0 || permit.eoi_epoch != self.eoi_epoch", "false"),
            ("PRIORITY-BYPASS", "if self.high_bypass >= MAX_HIGH_BYPASS", "if false"),
            ("QUEUED-CANCEL", "self.complete_cancel(index)?;\n                self.validate()", "self.validate()"),
            ("RUNNING-CANCEL", "let cancelled = self.slots[index].cancel_requested;", "let cancelled = false;"),
            ("FLUSH-WATERMARK", "slot.enqueue_sequence == 0\n                || slot.enqueue_sequence > token.enqueue_watermark", "true\n                || slot.enqueue_sequence > token.enqueue_watermark"),
            ("STALE-GENERATION", "|| self.slots[index].generation != id.generation", "|| false"),
            ("FAULT-ROLLBACK", "if fault == FaultPoint::AfterReserve", "if false"),
            ("SHUTDOWN-ORDER", "if self.intake_open\n", "if false\n"),
        )
        for group, old, new in mutations:
            with self.subTest(group=group):
                self.assertEqual(1, source.count(old))
                work = self.work / group
                fixture = work / deferred.NATIVE_CONTROL_SOURCES[0]
                fixture.parent.mkdir(parents=True)
                fixture.write_bytes((ROOT / deferred.NATIVE_CONTROL_SOURCES[0]).read_bytes())
                native = work / deferred.NATIVE_CONTROL_SOURCES[1]
                native.parent.mkdir(parents=True)
                native.write_text(source.replace(old, new), encoding="utf-8")
                executable, env = qualifier._build_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT, work / "build", fixture)
                result = subprocess.run([str(executable), group], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, check=False, timeout=30,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                output = result.stdout.decode("utf-8", errors="replace")
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("panicked", output)
                self.assertIn("assertion", output)
                self.assertNotIn("PKSCHED3:CONTROL PASS", output)

    def test_empty_or_disabled_rejection_control_cannot_pass(self):
        with self.assertRaises(qualifier.QualificationError):
            qualifier._require_rejections("empty", [])
        with self.assertRaises(qualifier.QualificationError):
            qualifier._require_rejections("disabled", [lambda: None])

    def test_source_mutations_detect_disabled_auditor(self):
        source = qualifier._source_audit()
        texts = {name: (ROOT / entry["path"]).read_text(encoding="utf-8") for name, entry in source["files"].items()}
        self.assertEqual(deferred.expected_controls()[27:29], qualifier._source_controls(texts))
        with patch.object(qualifier, "_audit_source_text", return_value={}):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._source_controls(texts)


class DeferredReceiptTests(unittest.TestCase):
    def test_runtime_and_actual_gate_reject_all_corrupted_records(self):
        baseline = deferred.read_json(ROOT / deferred.READINESS_RELATIVE)
        self.assertEqual([], deferred.readiness_errors(baseline))
        self.assertTrue(gate.check_native_kernel_scheduler_deferred_readiness()["ok"])
        count = 0
        for family, label, candidate in recorded_deferred_mutations(baseline):
            with self.subTest(family=family, case=label), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(deferred.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_scheduler_deferred_readiness()["ok"])
                count += 1
        self.assertEqual(273, count)

    def test_new_native_and_source_control_receipts_fail_closed(self):
        baseline = deferred.read_json(ROOT / deferred.READINESS_RELATIVE)
        self.assertEqual([], deferred.readiness_errors(baseline))
        paths = [("build",), ("build", "kernel_entry"), ("build", "native_control_probe"),
                 ("build", "audit_controls"), ("build", "source_audit"), ("build", "linked_switch_audit")]
        for section in ("native_control_probe", "audit_controls", "source_audit", "linked_switch_audit"):
            paths.extend(("build", section, key) for key in baseline["build"][section])
        for path in paths:
            candidate = copy.deepcopy(baseline)
            target = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = None
            with self.subTest(path=path), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(deferred.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_scheduler_deferred_readiness()["ok"])

    def test_valid_calendar_dates_remain_admissible(self):
        baseline = deferred.read_json(ROOT / deferred.READINESS_RELATIVE)
        for value in ("2026-09-29", "2024-02-29"):
            candidate = copy.deepcopy(baseline)
            candidate["status_date"] = value
            self.assertEqual([], deferred.readiness_errors(candidate))


if __name__ == "__main__":
    unittest.main()
