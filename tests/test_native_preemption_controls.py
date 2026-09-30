"""Execute native PKSCHED2 controls and prove disabled checks are detected."""

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_scheduler_preempt as preempt
from tools import qualify_native_kernel_scheduler_preempt as qualifier
from tests.test_native_kernel_scheduler import linked_switch_fixture


ROOT = Path(__file__).resolve().parents[1]


class NativePreemptionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="pksched2-controls-test-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.receipt = qualifier._run_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT, cls.work / "baseline")

    def test_actual_native_modules_reject_all_fifty_cases(self) -> None:
        self.assertEqual(0, self.receipt["exit_code"])
        self.assertEqual(50, self.receipt["hostile_cases_total"])
        self.assertEqual(list(preempt.NEGATIVE_CONTROL_IDS[15:22]), [c["id"] for c in self.receipt["controls"]])
        self.assertEqual(list(preempt.NATIVE_CONTROL_CASE_COUNTS), [c["case_count"] for c in self.receipt["controls"]])
        self.assertEqual(self.receipt["controls"], preempt.parse_native_control_output("\n".join(self.receipt["lines"]) + "\n"))
        for source in self.receipt["sources"]:
            self.assertEqual(preempt.file_binding(ROOT, source["path"]), source)

    def test_parser_rejects_missing_reordered_and_fabricated_group_counts(self) -> None:
        lines = self.receipt["lines"]
        hostile = [[], lines[:-1], lines + lines[:1], list(reversed(lines)), ["unrelated"] + lines]
        for index in range(7):
            changed = copy.deepcopy(lines)
            changed[index] = changed[index].replace("rejected=", "rejected=0")
            hostile.append(changed)
        for candidate in hostile:
            with self.subTest(candidate=candidate), self.assertRaises(preempt.KernelSchedulerPreemptError):
                preempt.parse_native_control_output("\n".join(candidate) + "\n")

    def test_each_disabled_native_boundary_is_detected(self) -> None:
        source = (ROOT / "native/kernel/src/scheduler_preempt.rs").read_text(encoding="utf-8")
        mutations = (
            ("INTERRUPT-FRAME-CONTRACT", "return Err(Error::InterruptDepth);", "return Ok(());"),
            ("CONTEXT-OWNERSHIP", "return Err(Error::StackAlignment);", "return Ok(());"),
            ("EVENT-CAPACITY", "return Err(Error::EventCapacity);", "return Ok(());"),
            ("EVENT-DEADLINE", "return Err(Error::EventDeadline);", "return Ok(());"),
            ("EVENT-DUPLICATE", "return Err(Error::EventDuplicate);", "return Ok(());"),
            ("QUANTUM-BOUNDARY", "if !(MIN_QUANTUM_TICKS..=MAX_QUANTUM_TICKS).contains(&quantum_ticks) {", "if false {"),
            ("TRANSACTIONAL-ROLLBACK", "*self = before;", "// Fault injection: omit state restoration."),
        )
        for group, old, new in mutations:
            with self.subTest(group=group):
                self.assertEqual(1, source.count(old))
                work = self.work / group
                fixture = work / "tests/fixtures/pksched2_control_probe.rs"
                fixture.parent.mkdir(parents=True)
                fixture.write_bytes((ROOT / "tests/fixtures/pksched2_control_probe.rs").read_bytes())
                native = work / "native/kernel/src"
                native.mkdir(parents=True)
                (native / "scheduler.rs").write_bytes((ROOT / "native/kernel/src/scheduler.rs").read_bytes())
                (native / "scheduler_preempt.rs").write_text(source.replace(old, new), encoding="utf-8")
                executable, env = qualifier._build_native_control_probe(qualifier.DEFAULT_TOOLCHAIN_ROOT, work / "build", fixture)
                result = subprocess.run(
                    [str(executable), group], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, check=False, timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                output = result.stdout.decode("utf-8", errors="replace")
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("panicked", output)
                self.assertIn("assertion", output)
                self.assertNotIn("PKSCHED2:CONTROL PASS", output)

    def test_empty_or_disabled_python_rejection_control_cannot_pass(self) -> None:
        with self.assertRaises(qualifier.QualificationError):
            qualifier._require_rejections("empty", [])
        with self.assertRaises(qualifier.QualificationError):
            qualifier._require_rejections("disabled", [lambda: None])

    def test_linked_scope_mutations_execute_and_detect_disabled_auditor(self) -> None:
        symbols = (
            "0000000000001000 g F .text 0000000000000024 poole_scheduler_context_switch\n"
            "0000000000001024 g .text 0000000000000000 poole_scheduler_context_switch_end\n"
            "0000000000001024 g F .text 0000000000000010 poole_scheduler_task_a_entry\n"
        )
        receipt = qualifier._linked_scope_controls(linked_switch_fixture(), symbols)
        self.assertEqual(3, receipt["case_count"])
        with patch.object(qualifier.qualify_native_kernel_scheduler, "_linked_switch_scope", return_value={}):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._linked_scope_controls(linked_switch_fixture(), symbols)

    def test_retained_stack_mutations_execute_and_detect_disabled_auditor(self) -> None:
        sources = qualifier._source_audit()["files"]
        texts = {name: (ROOT / entry["path"]).read_text(encoding="utf-8") for name, entry in sources.items()}
        self.assertEqual(4, qualifier._retained_stack_controls(texts)["case_count"])
        with patch.object(qualifier, "_audit_source_text", return_value={}):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._retained_stack_controls(texts)


if __name__ == "__main__":
    unittest.main()
