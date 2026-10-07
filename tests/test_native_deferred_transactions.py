"""Execute real native deferred-controller fault and exhaustion regressions."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import qualify_native_kernel_entry


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/pksched3_transaction_probe.rs"
TOOLCHAIN = ROOT / ".toolchains/rust-1.97.0"


def run_probe(source: Path, target: Path, optimization: int = 0) -> subprocess.CompletedProcess:
    _, rustc, env = qualify_native_kernel_entry._toolchain(TOOLCHAIN)
    executable = target / "pksched3-transactions.exe"
    build = subprocess.run(
        [str(rustc), "--edition=2021", "--test", "--crate-name", "pksched3_transactions",
         "-C", f"opt-level={optimization}", str(source), "-o", str(executable)], cwd=ROOT, env=env,
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


class NativeDeferredTransactionTests(unittest.TestCase):
    def test_native_controller_transactions_and_existing_regressions(self) -> None:
        for optimization in (0, 3):
            with self.subTest(optimization=optimization):
                with tempfile.TemporaryDirectory(prefix="pksched3-transactions-", dir=ROOT / "tmp") as work:
                    result = run_probe(SOURCE, Path(work), optimization)
                output = result.stdout.decode("utf-8", errors="replace")
                print(output)
                self.assertEqual(0, result.returncode, output)
                self.assertIn("21 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out", output)

    def test_disabled_shutdown_fairness_and_transaction_boundaries_are_detected(self) -> None:
        source = (ROOT / "native/kernel/src/scheduler_deferred.rs").read_text(encoding="utf-8")
        mutations = (
            ("shutdown-order", "if self.intake_open\n            || self.active_worker", "if false\n            || self.active_worker"),
            ("fault-fairness", "if fault == FaultPoint::BeforeExecute", "if false && fault == FaultPoint::BeforeExecute"),
            ("cancel-transaction", "next.cancel_inner(id)?;", "let result = next.cancel_inner(id); *self = next; result?;"),
            ("retirement-transaction", "let retired = next.retire_all_terminal_inner()?;", "let result = next.retire_all_terminal_inner(); *self = next; let retired = result?;"),
        )
        for name, old, new in mutations:
            with self.subTest(boundary=name):
                self.assertEqual(1, source.count(old))
                with tempfile.TemporaryDirectory(prefix="pksched3-disabled-", dir=ROOT / "tmp") as work:
                    root = Path(work)
                    fixture = root / "tests/fixtures/pksched3_transaction_probe.rs"
                    native = root / "native/kernel/src/scheduler_deferred.rs"
                    fixture.parent.mkdir(parents=True)
                    native.parent.mkdir(parents=True)
                    fixture.write_bytes(SOURCE.read_bytes())
                    native.write_text(source.replace(old, new), encoding="utf-8")
                    result = run_probe(fixture, root)
                output = result.stdout.decode("utf-8", errors="replace")
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("test result: FAILED", output)
                self.assertIn("assertion", output)


if __name__ == "__main__":
    unittest.main()
