"""Exercise the actual AP-worker controller with counter and ownership faults."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import qualify_native_kernel_entry as entry

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/kernel/src/scheduler_ap_workers.rs"
FIXTURE = ROOT / "tests/fixtures/pksched5_transaction_probe.rs"


def build_library(target: Path) -> tuple[Path, Path, dict[str, str]]:
    cargo, rustc, env = entry._toolchain(entry.DEFAULT_TOOLCHAIN_ROOT)
    result = subprocess.run(
        [str(cargo), "build", "--locked", "--offline", "--lib", "--package", "poolekernel",
         "--manifest-path", str(ROOT / "native/Cargo.toml"), "--target", entry.HOST_TARGET,
         "--target-dir", str(target)], cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stdout.decode("utf-8", errors="replace"))
    return target / entry.HOST_TARGET / "debug", rustc, env


def run_probe(target: Path, library: tuple, optimization: int = 0,
              source: bytes | None = None) -> subprocess.CompletedProcess:
    artifacts, rustc, env = library
    target.mkdir(parents=True, exist_ok=True)
    (target / "ap_workers.rs").write_bytes((SOURCE.read_bytes() if source is None else source) + b"\n" + FIXTURE.read_bytes())
    harness = target / "harness.rs"
    harness.write_text('pub use poolekernel::smp_ipi;\nmod ap_workers;\n', encoding="utf-8")
    executable = target / "pksched5-transactions.exe"
    result = subprocess.run(
        [str(rustc), "--edition=2024", "--test", "--crate-name", "pksched5_transactions",
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


class NativeApWorkerTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pksched5-transactions-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.library = build_library(cls.work / "library")

    def test_native_ap_worker_transactions_and_existing_regressions(self):
        for optimization in (0, 3):
            with self.subTest(optimization=optimization):
                result = run_probe(self.work / str(optimization), self.library, optimization)
                output = result.stdout.decode("utf-8", errors="replace")
                print(output)
                self.assertEqual(0, result.returncode, output)
                self.assertIn("30 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out", output)

    def test_disabled_commit_capacity_and_validation_boundaries_are_detected(self):
        source = SOURCE.read_text(encoding="utf-8")
        mutations = (
            ("enqueue", "let result = next.enqueue_from_top_half_inner(context, request);",
             "let result = next.enqueue_from_top_half_inner(context, request); *self = next;"),
            ("dispatch", "let ticket =\n            next.stage_dispatch_inner(target_cpu, permit, request_attempt, request_sequence)?;",
             "let result = next.stage_dispatch_inner(target_cpu, permit, request_attempt, request_sequence); *self = next; let ticket = result?;"),
            ("cancel", "next.cancel_inner(id)?;", "let result = next.cancel_inner(id); *self = next; result?;"),
            ("ack", "let receipt = next.acknowledge_inner(ticket, ack)?;",
             "let result = next.acknowledge_inner(ticket, ack); *self = next; let receipt = result?;"),
            ("timeout", "next.timeout_inner(ticket)?;", "let result = next.timeout_inner(ticket); *self = next; result?;"),
            ("reclaim", "next.reclaim_inner(id, token)?;", "let result = next.reclaim_inner(id, token); *self = next; result?;"),
            ("retire", "let retired = next.retire_all_terminal_inner(token)?;",
             "let result = next.retire_all_terminal_inner(token); *self = next; let retired = result?;"),
            ("offline", "next.offline_worker_inner(cpu)?;", "let result = next.offline_worker_inner(cpu); *self = next; result?;"),
            ("shutdown", "next.finish_shutdown_inner()?;", "let result = next.finish_shutdown_inner(); *self = next; result?;"),
            ("generation", "None => false,", "None => true,"),
            ("wide-total", "u64::from(self.completed) + u64::from(self.cancelled) > u64::from(self.enqueued)",
             "self.completed + self.cancelled > self.enqueued"),
            ("pending-order", ".min_by_key(|t| t.transaction)", ".next()"),
        )
        for name, old, new in mutations:
            with self.subTest(boundary=name):
                self.assertEqual(1, source.count(old))
                self._require_detected(name, source.replace(old, new))
        old = "next.preflight_pending_commits()?;"
        self.assertEqual(2, source.count(old))
        for index, name in enumerate(("dispatch-capacity", "offline-capacity")):
            parts = source.split(old)
            parts[index] += "let _ = &next;"
            mutated = old.join(parts[:index + 1]) + old.join(parts[index + 1:])
            with self.subTest(boundary=name):
                self._require_detected(name, mutated)
        self._require_detected("early-publication", source.replace(old, "*self = next; " + old, 1))

    def _require_detected(self, name, source):
        result = run_probe(self.work / name, self.library, source=source.encode("utf-8"))
        output = result.stdout.decode("utf-8", errors="replace")
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("test result: FAILED", output)


if __name__ == "__main__":
    unittest.main()
