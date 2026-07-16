import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import check_publication_boundary as publication  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PublicationBoundaryTests(unittest.TestCase):
    def test_exact_git_index_passes_publication_scan(self) -> None:
        report = publication.audit_git_index()
        self.assertTrue(report["publication_allowed"], report["violations"])
        self.assertEqual(report["status"], "pass")
        self.assertGreater(report["summary"]["indexed_path_count"], 300)
        self.assertEqual(report["summary"]["violation_count"], 0)

    def test_private_and_historical_paths_are_rejected(self) -> None:
        examples = (
            "sources/pdc/intake/internal.md",
            "sources/buildroot-2026.05/README",
            "lab-os/buildroot/config",
            "runs/private_benchmark.json",
            "firmware/private/device.bin",
        )
        for path in examples:
            with self.subTest(path=path):
                self.assertTrue(publication.inspect_public_blob(path, b"data"))

    def test_secrets_and_user_paths_are_rejected(self) -> None:
        fake_token = ("gh" + "p_" + "A" * 40).encode("ascii")
        token_violations = publication.inspect_public_blob("docs/example.md", fake_token)
        self.assertTrue(any(item["type"] == "secret_pattern" for item in token_violations))
        user_path = b"local path: " + b"C:" + b"\\Users\\example\\private.json"
        path_violations = publication.inspect_public_blob("docs/example.md", user_path)
        self.assertTrue(any(item["type"] == "absolute_user_path" for item in path_violations))
        self.assertFalse(any(item["type"] == "absolute_user_path" for item in publication.inspect_public_blob("tests/example.py", user_path)))

    def test_private_vault_paths_are_git_ignored(self) -> None:
        paths = (
            "sources/pdc/intake/example.md",
            "sources/buildroot-2026.05/README",
            "lab-os/README.md",
            "runs/pdc_source_intake.json",
            "docs/cycle_log.md",
        )
        for path in paths:
            with self.subTest(path=path):
                completed = subprocess.run(
                    ["git", "check-ignore", "--quiet", path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0)

    def test_native_toolchain_ledger_remains_explicitly_public(self) -> None:
        paths = (
            "runs/native_toolchain_qualification.json",
            "runs/native_model_readiness.json",
            "runs/n0_owner_decision_packet.json",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(path, publication.ALLOWED_RUNS)
                completed = subprocess.run(
                    ["git", "check-ignore", "--quiet", path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(publication.inspect_public_blob(path, b"{}"), [])

    def test_native_v1_objectives_readiness_remains_explicitly_public(self) -> None:
        path = "runs/native_v1_objectives_readiness.json"
        self.assertIn(path, publication.ALLOWED_RUNS)
        completed = subprocess.run(
            ["git", "check-ignore", "--quiet", path],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(publication.inspect_public_blob(path, b"candidate objectives evidence"), [])

    def test_adr_ratification_public_evidence_paths_are_explicitly_allowlisted(self) -> None:
        paths = (
            "runs/adr_ratification_readiness.json",
            "runs/adr_ratification_manifest.json",
            "runs/adr_ratification_manifest.json.sig",
            "runs/adr_ratification_receipt.json",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(path, publication.ALLOWED_RUNS)
                completed = subprocess.run(
                    ["git", "check-ignore", "--quiet", path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(publication.inspect_public_blob(path, b"public ratification evidence"), [])

    def test_sanitized_hardware_evidence_paths_are_explicitly_allowlisted(self) -> None:
        paths = (
            "runs/tier1_hardware_observation.json",
            "runs/hardware_target_readiness.json",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(path, publication.ALLOWED_RUNS)
                completed = subprocess.run(
                    ["git", "check-ignore", "--quiet", path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(publication.inspect_public_blob(path, b"sanitized hardware evidence"), [])

    def test_release_gate_carries_publication_boundary(self) -> None:
        check = pooleos_release_gate.check_publication_boundary()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("violations=0", check["detail"])


if __name__ == "__main__":
    unittest.main()
