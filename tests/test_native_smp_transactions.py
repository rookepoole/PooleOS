"""Run actual SMP scheduler transaction regressions, including private counters."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import qualify_native_kernel_entry


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/kernel/src/scheduler_smp.rs"
FIXTURE = ROOT / "tests/fixtures/pksched4_transaction_probe.rs"
TOOLCHAIN = ROOT / ".toolchains/rust-1.97.0"


def run_probe(target: Path, optimization: int = 0, source: bytes | None = None) -> subprocess.CompletedProcess:
    _, rustc, env = qualify_native_kernel_entry._toolchain(TOOLCHAIN)
    combined = target / "pksched4_transactions.rs"
    combined.write_bytes((SOURCE.read_bytes() if source is None else source) + b"\n" + FIXTURE.read_bytes())
    executable = target / "pksched4-transactions.exe"
    build = subprocess.run(
        [str(rustc), "--edition=2021", "--test", "--crate-name", "pksched4_transactions",
         "-C", f"opt-level={optimization}", str(combined), "-o", str(executable)], cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if build.returncode:
        raise RuntimeError(build.stdout.decode("utf-8", errors="replace"))
    return subprocess.run(
        [str(executable), "--test-threads=1"], cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class NativeSmpTransactionTests(unittest.TestCase):
    def test_native_smp_transactions_and_existing_regressions(self) -> None:
        for optimization in (0, 3):
            with self.subTest(optimization=optimization):
                with tempfile.TemporaryDirectory(prefix="pksched4-transactions-", dir=ROOT / "tmp") as work:
                    result = run_probe(Path(work), optimization)
                output = result.stdout.decode("utf-8", errors="replace")
                print(output)
                self.assertEqual(0, result.returncode, output)
                self.assertIn("19 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out", output)

    def test_each_disabled_transaction_boundary_is_detected(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        mutations = (
            ("ack", "next.commit_acknowledgement(ticket)?;",
             "let result = next.commit_acknowledgement(ticket); *self = next; result?;"),
            ("cancel", "next.cancel_task_inner(id)?;",
             "let result = next.cancel_task_inner(id); *self = next; result?;"),
            ("timeout", "next.timeout_inner(ticket)?;",
             "let result = next.timeout_inner(ticket); *self = next; result?;"),
            ("complete", "let id = next.complete_current_inner(cpu)?;",
             "let result = next.complete_current_inner(cpu); *self = next; let id = result?;"),
            ("local", "let id = next.dispatch_local_inner(cpu)?;",
             "let result = next.dispatch_local_inner(cpu); *self = next; let id = result?;"),
            ("stage", "let ticket = next.stage_dispatch_inner(cpu, attempt, sequence)?;",
             "let result = next.stage_dispatch_inner(cpu, attempt, sequence); *self = next; let ticket = result?;"),
            ("ack-preflight", "trial.commit_acknowledgement(ticket)?;", "let _ = ticket;"),
            ("timeout-preflight", "trial.timeout_inner(ticket)?;", "let _ = ticket;"),
            ("pending-publication", "let mut trial = next;", "*self = next; let mut trial = next;"),
        )
        for name, old, new in mutations:
            with self.subTest(boundary=name):
                self.assertEqual(1, source.count(old))
                with tempfile.TemporaryDirectory(prefix="pksched4-disabled-", dir=ROOT / "tmp") as work:
                    result = run_probe(Path(work), source=source.replace(old, new).encode("utf-8"))
                output = result.stdout.decode("utf-8", errors="replace")
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("test result: FAILED", output)
                self.assertIn("assertion", output)


if __name__ == "__main__":
    unittest.main()
