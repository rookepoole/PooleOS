"""Run fault cases against the actual PKSCHED6 module and native scheduler."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_native_ap_worker_transactions import build_library

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/kernel/src/scheduler_smp_preempt.rs"
FIXTURE = ROOT / "tests/fixtures/pksched6_transaction_probe.rs"
EVENT_FIXTURE = ROOT / "tests/fixtures/pksched6_event_progress_probe.rs"


def run_probe(target: Path, library: tuple, optimization: int = 0,
              source: bytes | None = None) -> subprocess.CompletedProcess:
    artifacts, rustc, env = library
    target.mkdir(parents=True, exist_ok=True)
    (target / "preempt.rs").write_bytes((SOURCE.read_bytes() if source is None else source)
        + b"\n" + FIXTURE.read_bytes() + b"\n" + EVENT_FIXTURE.read_bytes())
    harness = target / "harness.rs"
    harness.write_text('pub use poolekernel::scheduler_smp;\nmod preempt;\n', encoding="utf-8")
    executable = target / "pksched6-transactions.exe"
    result = subprocess.run(
        [str(rustc), "--edition=2024", "--test", "--crate-name", "pksched6_transactions",
         "-C", f"opt-level={optimization}", str(harness), "--extern",
         f"poolekernel={artifacts / 'libpoolekernel.rlib'}", "-L", f"dependency={artifacts / 'deps'}",
         "-o", str(executable)], cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stdout.decode("utf-8", errors="replace"))
    return subprocess.run([str(executable), "--test-threads=1"], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                          timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class NativeSmpPreemptTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pksched6-transactions-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.library = build_library(cls.work / "library")

    def test_native_transactions_and_existing_regressions(self):
        for optimization in (0, 3):
            with self.subTest(optimization=optimization):
                result = run_probe(self.work / str(optimization), self.library, optimization)
                output = result.stdout.decode("utf-8", errors="replace")
                print(output)
                self.assertEqual(0, result.returncode, output)
                self.assertIn("27 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out", output)

    def test_disabled_transaction_epoch_and_capacity_guards_are_detected(self):
        source = SOURCE.read_text(encoding="utf-8")
        mutations = (
            ("event", None, "next.queue_event_inner(owner, event)?;",
             "let result = next.queue_event_inner(owner, event); *self = next; result?;"),
            ("ack", None, "next.acknowledge_reschedule_inner(ticket, ack)?;",
             "let result = next.acknowledge_reschedule_inner(ticket, ack); *self = next; result?;"),
            ("timeout", "pub fn timeout_offline", "next.timeout_offline_inner(ticket)?;",
             "let result = next.timeout_offline_inner(ticket); *self = next; result?;"),
            ("shutdown", None, "next.finish_shutdown_inner(tasks)?;",
             "let result = next.finish_shutdown_inner(tasks); *self = next; result?;"),
            ("offline", "pub fn stage_offline_probe", "let ticket = next.stage_offline_probe_inner(task, attempt, sequence)?;",
             "let result = next.stage_offline_probe_inner(task, attempt, sequence); *self = next; let ticket = result?;"),
            ("combined", "pub fn prove_offline_rollback", "let ticket = next.stage_offline_probe_inner(task, attempt, sequence)?;",
             "let result = next.stage_offline_probe_inner(task, attempt, sequence); *self = next; let ticket = result?;"),
            ("frame-epoch", "fn validate_frame", "lane.frame_epoch.checked_add(1).ok_or(Error::Counter)?", "lane.frame_epoch + 1"),
            ("timer-epoch", "fn validate_frame", "lane.timer_ticks.checked_add(1).ok_or(Error::Counter)?", "lane.timer_ticks + 1"),
            ("tick-rollback", None, "*self = before;", "let _ = before;"),
            ("query", None, "snapshot.task_snapshot(task).map_err(Into::into)", "self.scheduler.task_snapshot(task).map_err(Into::into)"),
            ("tick-completion", "pub fn handle_tick", "self.preflight_tick_completion()?;", "// completion preview disabled"),
            ("resume-transaction", "pub fn resume_tick", "let outcome = next.advance_tick(attempt, sequence, false)?;",
             "let result = next.advance_tick(attempt, sequence, false); *self = next; let outcome = result?;"),
            ("resume-sequence", "pub fn resume_tick", "attempt < progress.attempt || sequence <= progress.sequence", "false"),
        )
        for name, start, old, new in mutations:
            scope = source
            if start:
                scope = start + source.split(start, 1)[1].split("\n    }", 1)[0]
            with self.subTest(boundary=name):
                self.assertEqual(1, scope.count(old))
                self._require_detected(name, source.replace(scope, scope.replace(old, new, 1), 1))
        old = "self.preflight_pending_commit(ticket)?;"
        self.assertEqual(2, source.count(old))
        for index, name in enumerate(("tick-capacity", "offline-capacity")):
            parts = source.split(old)
            mutated = old.join(parts[:index + 1]) + "let _ = ticket;" + old.join(parts[index + 1:])
            with self.subTest(boundary=name):
                if index == 0:
                    # Full-tick preview independently reserves the same first-ack capacity.
                    result = run_probe(self.work / name, self.library, source=mutated.encode("utf-8"))
                    self.assertEqual(0, result.returncode, result.stdout.decode("utf-8", errors="replace"))
                else:
                    self._require_detected(name, mutated)

    def _require_detected(self, name, source):
        result = run_probe(self.work / name, self.library, source=source.encode("utf-8"))
        output = result.stdout.decode("utf-8", errors="replace")
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("test result: FAILED", output)


if __name__ == "__main__":
    unittest.main()
