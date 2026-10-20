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
            "runs/native-user-entry-private.json",
            "runs/native-user-program-private.json",
            "runs/native-user-program-readiness-raw.json",
            "runs/native-session-readiness-raw.json",
            "runs/native-console-readiness-raw.json",
            "runs/native-console-private.json",
            "runs/native-console-ipc-program-readiness-raw.json",
            "runs/native-console-ipc-readiness-raw.json",
            "runs/native-console-ipc-readiness-private.json",
            "runs/native-console-rpc-readiness-raw.json",
            "runs/native-console-rpc-readiness-private.json",
            "runs/native-session-capacity-readiness-raw.json",
            "runs/native-session-capacity-readiness-private.json",
            "runs/native-process-authority-readiness-raw.json",
            "runs/native-process-authority-readiness-private.json",
            "runs/native-process-launch-readiness-raw.json",
            "runs/native-process-launch-readiness-private.json",
            "runs/native-kernel-budget-readiness-raw.json",
            "runs/native-kernel-budget-readiness-private.json",
            "runs/native-shell-readiness-raw.json",
            "runs/native-shell-readiness-private.json",
            "runs/native-process-completion-readiness-raw.json",
            "runs/native-process-completion-readiness-private.json",
            "runs/native-vm-allocation-pages-readiness-raw.json",
            "runs/native-vm-allocation-pages-readiness-private.json",
            "runs/native-multipage-program-readiness-raw.json",
            "runs/native-multipage-program-readiness-private.json",
            "runs/native-shell-process-readiness-raw.json",
            "runs/native-shell-process-readiness-private.json",
            "runs/native-retained-cleanup-readiness-raw.json",
            "runs/native-retained-cleanup-readiness-private.json",
            "runs/native-prepared-cleanup-readiness-raw.json",
            "runs/native-prepared-cleanup-readiness-private.json",
            "runs/native-owner-death-readiness-raw.json",
            "runs/native-owner-death-readiness-private.json",
            "runs/native-deferred-cleanup-readiness-raw.json",
            "runs/native-deferred-cleanup-readiness-private.json",
            "runs/native-files-readiness-raw.json",
            "runs/native-files-readiness-private.json",
            "runs/native-app-programs-readiness-raw.json",
            "runs/native-app-programs-readiness-private.json",
            "runs/native-startup-handoff-readiness-raw.json",
            "runs/native-startup-handoff-readiness-private.json",
            "runs/native-app-shell-readiness-raw.json",
            "runs/native-app-shell-readiness-private.json",
            "runs/native-app-session-readiness-raw.json",
            "runs/native-app-session-readiness-private.json",
            "runs/native-app-recovery-readiness-raw.json",
            "runs/native-app-recovery-readiness-private.json",
            "runs/native-file-controls-readiness-raw.json",
            "runs/native-file-controls-readiness-private.json",
            "runs/native-cleanup-exhaustion-readiness-raw.json",
            "runs/native-cleanup-exhaustion-readiness-private.json",
            "runs/native-claimed-requester-readiness-raw.json",
            "runs/native-claimed-requester-readiness-private.json",
            "runs/native-userspace-iso-readiness-raw.json",
            "runs/native-userspace-iso-readiness-private.json",
            "runs/native-app-file-wait-readiness-raw.json",
            "runs/native-app-file-wait-readiness-private.json",
            "runs/native-ioapic-watchdog-readiness-raw.json",
            "runs/native-ioapic-watchdog-readiness-private.json",
            "runs/native-virtualbox-launcher-readiness-raw.json",
            "runs/native-virtualbox-launcher-readiness-private.json",
            "runs/native-local-console-readiness-raw.json",
            "runs/native-local-console-readiness-private.json",
            "runs/native-window-manager-readiness-raw.json",
            "runs/native-window-manager-readiness-private.json",
            "runs/native-window-input-readiness-raw.json",
            "runs/native-window-input-readiness-private.json",
            "runs/native-rendering-readiness-raw.json",
            "runs/native-rendering-readiness-private.json",
            "runs/native-virtualbox-mouse-readiness-raw.json",
            "runs/native-virtualbox-mouse-readiness-private.json",
            "runs/native-window-capacity-readiness-raw.json",
            "runs/native-window-capacity-readiness-private.json",
            "runs/native-surface-lifecycle-readiness-raw.json",
            "runs/native-surface-lifecycle-readiness-private.json",
            "runs/native-application-input-readiness-raw.json",
            "runs/native-application-input-readiness-private.json",
            "runs/native-input-lifetime-readiness-raw.json",
            "runs/native-input-lifetime-readiness-private.json",
            "runs/native-bounded-serial-readiness-raw.json",
            "runs/native-bounded-serial-readiness-private.json",
            "runs/native-launch-control-readiness-raw.json",
            "runs/native-launch-control-readiness-private.json",
            "runs/native-launch-session-readiness-raw.json",
            "runs/native-launch-session-readiness-private.json",
            "runs/native-launch-admission-readiness-raw.json",
            "runs/native-launch-admission-readiness-private.json",
            "runs/native-window-launch-readiness-raw.json",
            "runs/native-window-launch-readiness-private.json",
            "runs/native-launch-desktop-readiness-raw.json",
            "runs/native-launch-desktop-readiness-private.json",
            "runs/native-connected-desktop-readiness-raw.json",
            "runs/native-connected-desktop-readiness-private.json",
            "runs/native-console-ipc-private.json",
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
        for path in ("runs/native-console-readiness.json", "runs/native-console-ipc-program-readiness.json",
                     "runs/native-console-ipc-readiness.json",
                     "runs/native-console-rpc-readiness.json", "runs/native-session-capacity-readiness.json",
                     "runs/native-process-authority-readiness.json",
                     "runs/native-process-launch-readiness.json", "runs/native-kernel-budget-readiness.json",
                     "runs/native-shell-readiness.json", "runs/native-process-completion-readiness.json",
                     "runs/native-vm-allocation-pages-readiness.json", "runs/native-multipage-program-readiness.json",
                     "runs/native-shell-process-readiness.json", "runs/native-retained-cleanup-readiness.json",
                     "runs/native-prepared-cleanup-readiness.json", "runs/native-owner-death-readiness.json",
                     "runs/native-deferred-cleanup-readiness.json", "runs/native-files-readiness.json",
                     "runs/native-app-programs-readiness.json", "runs/native-startup-handoff-readiness.json",
                     "runs/native-app-shell-readiness.json", "runs/native-app-session-readiness.json",
                     "runs/native-app-recovery-readiness.json", "runs/native-file-controls-readiness.json",
                     "runs/native-cleanup-exhaustion-readiness.json", "runs/native-claimed-requester-readiness.json",
                     "runs/native-userspace-iso-readiness.json",
                     "runs/native-app-file-wait-readiness.json",
                     "runs/native-ioapic-watchdog-readiness.json",
                     "runs/native-virtualbox-launcher-readiness.json",
                     "runs/native-local-console-readiness.json", "runs/native-window-manager-readiness.json",
                     "runs/native-window-input-readiness.json", "runs/native-rendering-readiness.json",
                     "runs/native-virtualbox-mouse-readiness.json", "runs/native-window-capacity-readiness.json",
                     "runs/native-surface-lifecycle-readiness.json", "runs/native-application-input-readiness.json",
                     "runs/native-input-lifetime-readiness.json",
                     "runs/native-bounded-serial-readiness.json", "runs/native-launch-control-readiness.json",
                     "runs/native-launch-session-readiness.json",
                     "runs/native-launch-admission-readiness.json",
                     "runs/native-window-launch-readiness.json",
                     "runs/native-launch-desktop-readiness.json",
                     "runs/native-connected-desktop-readiness.json"):
            for data, kind in ((fake_token, "secret_pattern"), (user_path, "absolute_user_path")):
                self.assertTrue(any(item["type"] == kind for item in publication.inspect_public_blob(path, data)))

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
            "runs/native-ioapic-watchdog-readiness.json",
            "runs/native-virtualbox-launcher-readiness.json",
            "runs/native-local-console-readiness.json",
            "runs/native-window-manager-readiness.json",
            "runs/native-window-input-readiness.json",
            "runs/native-rendering-readiness.json",
            "runs/native-virtualbox-mouse-readiness.json",
            "runs/native-window-capacity-readiness.json",
            "runs/native-surface-lifecycle-readiness.json",
            "runs/native-application-input-readiness.json",
            "runs/native-input-lifetime-readiness.json",
            "runs/native-bounded-serial-readiness.json",
            "runs/native-launch-control-readiness.json",
            "runs/native-launch-session-readiness.json",
            "runs/native-launch-admission-readiness.json",
            "runs/native-window-launch-readiness.json",
            "runs/native-launch-desktop-readiness.json",
            "runs/native-connected-desktop-readiness.json",
            "runs/native-userspace-iso-readiness.json",
            "runs/native-app-file-wait-readiness.json",
            "runs/native_toolchain_qualification.json",
            "runs/native_model_readiness.json",
            "runs/native_pooleboot_readiness.json",
            "runs/native_boot_config_readiness.json",
            "runs/native_boot_handoff_readiness.json",
            "runs/native_boot_trust_readiness.json",
            "runs/native_elf_loader_readiness.json",
            "runs/native_firmware_readiness.json",
            "runs/native_policy_readiness.json",
            "runs/native_initial_system_readiness.json",
            "runs/native_kernel_entry_readiness.json",
            "runs/native_kernel_load_readiness.json",
            "runs/native-kernel-revalidation-readiness.json",
            "runs/native-kernel-transfer-readiness.json",
            "runs/native-kernel-trap-readiness.json",
            "runs/native-kernel-cpu-policy-readiness.json",
            "runs/native-kernel-interrupt-time-readiness.json",
            "runs/native-kernel-smp-first-ap-readiness.json",
            "runs/native-kernel-smp-percpu-runtime-readiness.json",
            "runs/native-kernel-smp-ipi-readiness.json",
            "runs/native-kernel-scheduler-readiness.json",
            "runs/native-kernel-scheduler-preemption-readiness.json",
            "runs/native-kernel-scheduler-deferred-readiness.json",
            "runs/native-kernel-scheduler-smp-readiness.json",
            "runs/native-kernel-scheduler-ap-workers-readiness.json",
            "runs/native-kernel-scheduler-smp-preempt-readiness.json",
            "runs/native-kernel-atomics-readiness.json",
            "runs/native-kernel-locks-readiness.json",
            "runs/native-kernel-reclamation-core-readiness.json",
            "runs/native-user-entry-readiness.json",
            "runs/native-user-entry-gate-projection.json",
            "runs/native-user-program-readiness.json",
            "runs/native-session-readiness.json",
            "runs/native-console-readiness.json",
            "runs/native-console-ipc-program-readiness.json",
            "runs/native-console-ipc-readiness.json",
            "runs/native-console-rpc-readiness.json",
            "runs/native-session-capacity-readiness.json",
            "runs/native-process-authority-readiness.json",
            "runs/native-process-launch-readiness.json",
            "runs/native-kernel-budget-readiness.json",
            "runs/native-shell-readiness.json",
            "runs/native-process-completion-readiness.json",
            "runs/native-vm-allocation-pages-readiness.json",
            "runs/native-multipage-program-readiness.json",
            "runs/native-shell-process-readiness.json",
            "runs/native-retained-cleanup-readiness.json",
            "runs/native-prepared-cleanup-readiness.json",
            "runs/native-owner-death-readiness.json",
            "runs/native-deferred-cleanup-readiness.json",
            "runs/native-files-readiness.json",
            "runs/native-app-programs-readiness.json",
            "runs/native-startup-handoff-readiness.json",
            "runs/native-app-shell-readiness.json",
            "runs/native-app-session-readiness.json",
            "runs/native-app-recovery-readiness.json",
            "runs/native-file-controls-readiness.json",
            "runs/native-cleanup-exhaustion-readiness.json",
            "runs/native-claimed-requester-readiness.json",
            "runs/native_microcode_readiness.json",
            "runs/native_recovery_readiness.json",
            "runs/native_system_manifest_readiness.json",
            "runs/n0_owner_decision_packet.json",
            "runs/n0_owner_response_receipt.json",
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
