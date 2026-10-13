import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402


class NativeArchitectureBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifact_path = ROOT / "runs" / "native_architecture_baseline.json"
        cls.artifact = json.loads(cls.artifact_path.read_text(encoding="utf-8-sig"))
        cls.schema = json.loads(
            (ROOT / "specs" / "native-architecture-baseline.schema.json").read_text(encoding="utf-8")
        )

    def test_artifact_matches_schema(self) -> None:
        self.assertEqual(validate_json(self.artifact, self.schema), [])

    def test_generator_reproduces_baseline_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "baseline.json"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "generate_native_architecture_baseline.py"), "--out", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(output.read_bytes(), self.artifact_path.read_bytes())

    def test_required_adr_set_is_byte_bound_and_not_overclaimed(self) -> None:
        adrs = self.artifact["adrs"]
        self.assertEqual([item["id"] for item in adrs], [f"ADR-{index:04d}" for index in range(1, 8)])
        self.assertEqual([item["status"] for item in adrs].count("accepted-owner-directed"), 7)
        self.assertEqual([item["status"] for item in adrs].count("proposed"), 0)
        for adr in adrs:
            data = (ROOT / adr["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest().upper(), adr["sha256"])
            self.assertEqual(adr["decision_owner"], "Rooke Poole")
            self.assertNotEqual(adr["status"], "accepted-signed")
        self.assertFalse(self.artifact["adr_summary"]["all_required_cryptographically_ratified"])
        self.assertFalse(self.artifact["production_promotion_allowed"])
        self.assertFalse(self.artifact["production_ready"])

    def test_native_architecture_and_version_namespaces_are_frozen_without_collisions(self) -> None:
        architecture = self.artifact["architecture"]
        self.assertEqual(architecture["bootloader"], "PooleBoot")
        self.assertEqual(architecture["kernel"], "PooleKernel")
        self.assertEqual(architecture["kernel_style"], "capability_microkernel")
        self.assertEqual(architecture["firmware"], "UEFI")
        self.assertEqual(architecture["production_base"], "original_native_pooleos")
        namespaces = self.artifact["version_namespaces"]
        self.assertEqual(len(namespaces), 20)
        self.assertEqual(len({item["id"] for item in namespaces}), 20)
        self.assertEqual(len({item["role"] for item in namespaces}), 20)
        names = self.artifact["component_names"]
        self.assertEqual(len(names.values()), len(set(names.values())))

    def test_bound_sources_reproduce_without_private_paths(self) -> None:
        bound_paths = {item["path"] for item in self.artifact["bound_sources"]}
        self.assertEqual(len(self.artifact["bound_sources"]), 751)
        self.assertTrue({"docs/checkpoints/cycle286-native-cleanup-exhaustion.md",
            "runs/native-cleanup-exhaustion-readiness.json", "runtime/native_cleanup_exhaustion.py",
            "tests/test_native_cleanup_exhaustion.py"}.issubset(bound_paths))
        self.assertTrue({"docs/checkpoints/cycle285-native-file-controls.md",
                         "runs/native-file-controls-readiness.json", "native/userspace/src/bin/file_probe.rs",
                         "native/userspace/src/files/probe.rs", "native/userspace/src/files/probe/tests.rs"}.issubset(bound_paths))
        self.assertTrue({"docs/checkpoints/cycle284-live-parent-app-recovery.md",
            "runs/native-app-recovery-readiness.json"}.issubset({item["path"] for item in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle283-native-applications.md", "docs/native-app-session.md",
            "runs/native-app-session-readiness.json", "native/kernel/src/development_apps.rs",
            "native/kernel/src/user_root_probe/peer_driver/interactive/applications.rs",
            "runtime/native_app_session.py", "tools/qualify_native_app_session.py",
            "tests/test_native_app_session.py"}.issubset({item["path"] for item in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle282-application-shell.md", "docs/native-application-shell.md",
            "runs/native-app-shell-readiness.json", "native/userspace/src/shell/applications.rs",
            "native/userspace/src/shell/applications/tests.rs", "native/userspace/src/bin/application_shell.rs",
            "native/userspace/src/bin/application_files.rs"}.issubset({item["path"] for item in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle281-startup-handoff.md", "docs/native-startup-handoff.md",
            "runs/native-startup-handoff-readiness.json", "native/kernel/src/user_entry/task/arguments.rs",
            "native/kernel/src/user_entry/startup_handoff_tests.rs"}.issubset({item["path"] for item in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle280-application-programs.md", "docs/native-application-programs.md",
                         "runs/native-app-programs-readiness.json", "native/userspace/src/apps/program.rs",
                         "native/userspace/src/apps/stats/tests.rs", "native/userspace/src/bin/text.rs",
                         "native/userspace/src/bin/numbers.rs"}.issubset({item["path"] for item in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle279-native-files.md", "docs/native-files.md",
            "runs/native-files-readiness.json", "native/userspace/src/files.rs",
            "native/userspace/src/files/rpc.rs", "native/userspace/src/shell/files.rs",
            "native/userspace/src/bin/files.rs", "native/userspace/src/bin/file_init.rs",
            "native/userspace/src/bin/file_shell.rs", "runtime/native_files.py",
            "tests/test_native_files.py"}.issubset({s["path"] for s in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle278-native-deferred-cleanup.md", "docs/native-deferred-cleanup.md",
            "runs/native-deferred-cleanup-readiness.json", "native/kernel/src/scheduler/reclamation.rs",
            "native/kernel/src/user_entry/task/cleanup.rs", "native/kernel/src/user_entry/cleanup_tests.rs",
            "runtime/native_deferred_cleanup.py", "tests/test_native_deferred_cleanup.py"}.issubset({s["path"] for s in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle277-native-owner-death.md", "docs/native-job-lifecycle.md",
            "runs/native-owner-death-readiness.json", "native/kernel/src/user_entry/task/job.rs",
            "native/kernel/src/user_entry/job_tests.rs", "runtime/native_shell_orphan.py",
            "tests/test_native_shell_orphan.py"}.issubset({s["path"] for s in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle276-prepared-cancellation.md",
            "docs/native-prepared-cleanup.md", "runs/native-prepared-cleanup-readiness.json",
            "native/kernel/src/user_entry/prepared_cancel_tests.rs", "runtime/native_prepared_cleanup.py",
            "tests/test_native_prepared_cleanup.py"}.issubset({s["path"] for s in self.artifact["bound_sources"]}))
        self.assertTrue({"docs/checkpoints/cycle268-native-process-launch.md",
            "docs/native-process-launch.md", "runs/native-process-launch-readiness.json",
            "native/kernel/src/capability_ipc/launch.rs", "native/kernel/src/capability_ipc/launch/tests.rs",
            "native/kernel/src/user_root_probe/peer_driver/launch.rs",
            "native/userspace/src/supervisor.rs", "native/userspace/src/bin/supervisor.rs",
            "runtime/native_process_launch.py", "tools/qualify_native_process_launch.py",
            "tests/test_native_process_launch.py"}.issubset({s["path"] for s in self.artifact["bound_sources"]}))
        paths = {item["path"] for item in self.artifact["bound_sources"]}
        self.assertTrue({"docs/checkpoints/cycle267-native-process-authority.md",
            "docs/native-process-authority.md", "runs/native-process-authority-readiness.json",
            "native/kernel/src/capability_ipc/process.rs", "native/kernel/src/capability_ipc/process/tests.rs",
            "native/kernel/src/arch/x86_64/user_ipc/process.rs",
            "native/kernel/src/user_root_probe/peer_driver/process_control.rs",
            "runtime/native_process_authority.py", "tools/qualify_native_process_authority.py",
            "tests/test_native_process_authority.py"}.issubset(paths))
        self.assertTrue({"docs/checkpoints/cycle266-native-session-capacity.md",
            "docs/native-session-capacity.md", "runs/native-session-capacity-readiness.json",
            "native/kernel/src/capability_ipc/tests/admission/capacity.rs",
            "runtime/native_session_capacity.py", "tools/qualify_native_session_capacity.py",
            "tests/test_native_session_capacity.py"}.issubset(paths))
        self.assertTrue({"docs/checkpoints/cycle263-console-ipc-programs.md",
            "docs/native-console-ipc.md", "runs/native-console-ipc-program-readiness.json",
            "native/userspace/src/console_ipc.rs", "native/userspace/src/console_ipc/tests.rs",
            "native/userspace/src/bin/console_service.rs", "native/userspace/src/bin/console_client.rs",
            "tools/native_build_space.py", "tests/test_native_build_space.py"}.issubset(paths))
        self.assertTrue({"docs/checkpoints/cycle262-native-user-console.md",
            "docs/native-user-console.md", "runs/native-console-readiness.json",
            "native/kernel/src/capability_ipc/console.rs",
            "native/kernel/src/capability_ipc/console/tests.rs",
            "native/kernel/src/arch/x86_64/user_ipc/console.rs",
            "native/userspace/src/console.rs", "native/userspace/src/bin/console.rs",
            "runtime/native_console.py", "tools/qualify_native_console.py",
            "tests/test_native_console.py"}.issubset(paths))
        for path in ("docs/checkpoints/cycle221-current-kernel-smp-and-ap-worker-replay.md",
                     "docs/checkpoints/cycle220-current-kernel-scheduler-replay.md",
                     "docs/checkpoints/cycle219-current-kernel-memory-replay.md",
                     "docs/checkpoints/cycle218-terminal-capture-and-cpu-replay.md",
                     "tests/test_native_boot_capture.py",
                     "docs/checkpoints/cycle217-current-kernel-boot-replay.md",
                     "docs/checkpoints/cycle216-native-smp-preempt-transactions.md",
                     "native/kernel/src/scheduler_smp_preempt.rs", "native/kernel/src/bin/pksched6_probe.rs",
                     "tests/test_native_smp_preempt_transactions.py", "tests/fixtures/pksched6_transaction_probe.rs",
                     "tests/fixtures/pksched6_event_progress_probe.rs"):
            self.assertIn(path, {item["path"] for item in self.artifact["bound_sources"]})
        for path in ("docs/checkpoints/cycle215-ap-worker-admission-and-controls.md",
                     "tests/test_native_ap_worker_controls.py", "tests/fixtures/pksched5_control_probe.rs"):
            self.assertIn(path, {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle214-current-kernel-smp-scheduler-replay.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle213-current-kernel-scheduler-replay.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle212-current-kernel-memory-and-multiprocessor-replay.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle211-current-kernel-cpu-admission-and-replay.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle210-retained-map-growth-and-boot-replay.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle191-ipi-recorded-evidence.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle190-percpu-recorded-evidence.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle189-first-ap-recorded-evidence.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle188-irq-recorded-evidence.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle187-vm-recorded-evidence.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle186-pmm-recorded-evidence.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle175-memory-entry-provenance.md", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("tests/test_native_memory_entry_provenance.py", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("runtime/native_kernel_profile_evidence.py", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("tests/test_native_cpu_entry_provenance.py", {item["path"] for item in self.artifact["bound_sources"]})
        self.assertIn("docs/checkpoints/cycle174-cpu-entry-provenance.md", {item["path"] for item in self.artifact["bound_sources"]})
        bound_paths = {binding["path"] for binding in self.artifact["bound_sources"]}
        self.assertEqual(len(bound_paths), len(self.artifact["bound_sources"]))
        for path in ("docs/checkpoints/cycle196-preemption-executed-controls.md",
                     "runtime/native_kernel_scheduler_preempt.py",
                     "specs/native-kernel-scheduler-preemption-readiness.schema.json",
                     "tests/test_native_kernel_scheduler_preempt.py", "tests/test_native_preemption_controls.py",
                     "tests/fixtures/pksched2_control_probe.rs", "docs/native-kernel-scheduler-preemption.md"):
            self.assertIn(path, bound_paths)
        for path in ("docs/checkpoints/cycle195-scheduler-recorded-evidence.md",
                     "docs/checkpoints/cycle195-scheduler-cloud-backup.md",
                     "runtime/native_kernel_scheduler.py", "tools/qualify_native_kernel_scheduler.py",
                     "tools/qualify_native_kernel_scheduler_preempt.py",
                     "tests/test_native_kernel_scheduler.py", "docs/native-kernel-scheduler.md",
                     "docs/checkpoints/cycle194-memory-runtime-replay.md",
                     "tests/test_native_kernel_physical_memory.py",
                     "docs/checkpoints/cycle193-current-kernel-cpu-replay.md",
                     "tools/qualify_native_kernel_trap.py", "tests/test_native_kernel_trap.py"):
            self.assertIn(path, bound_paths)
        for path in ("docs/checkpoints/cycle192-native-mailbox-oracle.md",
                     "docs/checkpoints/cycle192-unfinished-cloud-backup.md",
                     "docs/checkpoints/cycle192-mailbox-qualified-backup.md",
                     "runtime/native_kernel_smp_mailbox.py", "tests/test_native_kernel_smp_mailbox.py",
                     "runtime/native_kernel_smp_ipi.py", "tools/qualify_native_kernel_smp_ipi.py",
                     "tests/test_native_kernel_smp_ipi.py", "native/kernel/src/main.rs",
                     "native/kernel/src/smp_runtime.rs"):
            self.assertIn(path, bound_paths)
        for path in ("docs/checkpoints/cycle185-cpu-recorded-evidence.md",
                     "docs/checkpoints/cycle185-unfinished-cloud-backup.md",
                     "runtime/native_kernel_trap.py", "tools/pooleos_release_gate.py"):
            self.assertIn(path, bound_paths)
        for path in ("docs/checkpoints/cycle184-boot-host-provenance.md",
                     "docs/checkpoints/cycle184-unfinished-cloud-backup.md",
                     "docs/checkpoints/cycle184-validated-boot-cloud-backup.md",
                     "tests/test_native_boot_host_toolchain.py"):
            self.assertIn(path, bound_paths)
        for name in ("symbols", "policy", "pooleboot", "kernel_revalidation", "firmware", "boot_trust"):
            self.assertIn("runtime/native_" + name + ".py", bound_paths)
            self.assertIn("tools/qualify_native_" + name + ".py", bound_paths)
        self.assertIn("docs/checkpoints/cycle183-elf-loader-provenance.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle183-unfinished-cloud-backup.md", bound_paths)
        self.assertIn("runtime/native_elf_loader.py", bound_paths)
        self.assertIn("tests/test_native_elf_loader.py", bound_paths)
        self.assertIn("docs/checkpoints/cycle180-cpu-qualification.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle181-memory-qualification.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle182-host-toolchain-repair.md", bound_paths)
        self.assertIn("specs/native-host-msvc-profile.json", bound_paths)
        self.assertIn("tools/native_host_toolchain.py", bound_paths)
        self.assertIn("tests/test_native_host_toolchain.py", bound_paths)
        self.assertIn("docs/checkpoints/cycle179-boot-chain-requalification.md", bound_paths)
        for name in ("symbols", "kernel_load", "kernel_transfer", "kernel_revalidation"):
            self.assertIn("tests/test_native_" + name + ".py", bound_paths)
        self.assertIn("docs/checkpoints/cycle178-kernel-entry-requalification.md", bound_paths)
        self.assertIn("tests/test_native_kernel_entry.py", bound_paths)
        self.assertIn("tests/test_native_dependency_release_gate.py", bound_paths)
        self.assertIn("docs/checkpoints/cycle177-dispatch-execution-holds.md", bound_paths)
        self.assertIn("native/kernel/src/reclamation/execution.rs", bound_paths)
        self.assertIn("native/kernel/src/reclamation/ap_resources.rs", bound_paths)
        self.assertIn("native/kernel/src/physical_memory/tests/ap_resources.rs", bound_paths)
        self.assertIn("docs/checkpoints/cycle168-ap-ownership-qualification.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle169-boot-chain-replay.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle170-cpu-state-replay.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle172-task-stack-ownership.md", bound_paths)
        self.assertIn("docs/checkpoints/cycle173-entry-provenance-replay.md", bound_paths)
        self.assertIn("tests/test_native_boot_chain_release_gate.py", bound_paths)
        self.assertIn("docs/checkpoints/cycle171-native-dependency-replay.md", bound_paths)
        self.assertIn("native/kernel/src/reclamation.rs", bound_paths)
        self.assertIn("native/kernel/src/reclamation/task_lifetimes.rs", bound_paths)
        self.assertIn("native/kernel/tests/task_lifetimes.rs", bound_paths)
        self.assertIn("runs/native-kernel-reclamation-core-readiness.json", bound_paths)
        self.assertIn("security/governance-key-registration.json", bound_paths)
        self.assertIn("specs/governance-key-registration.schema.json", bound_paths)
        self.assertIn("security/owner-adr-signers.allowed", bound_paths)
        self.assertIn(
            "runs/adr_ratification_readiness.json",
            bound_paths,
        )
        self.assertIn("runs/n0_owner_decision_packet.json", bound_paths)
        self.assertIn("docs/n0-owner-decision-packet.md", bound_paths)
        self.assertIn("runs/n0_owner_response_receipt.json", bound_paths)
        self.assertIn("docs/n0-owner-response-receipt.md", bound_paths)
        self.assertIn("native/kernel/src/active_virtual_memory.rs", bound_paths)
        self.assertIn("specs/n0-owner-response.json", bound_paths)
        self.assertIn(
            "runs/hardware_target_readiness.json",
            bound_paths,
        )
        self.assertIn(
            "runs/native_tier0_readiness.json",
            bound_paths,
        )
        self.assertIn(
            "runs/native_v1_objectives_readiness.json",
            bound_paths,
        )
        self.assertIn(
            "runs/native_model_readiness.json",
            bound_paths,
        )
        self.assertIn("runs/native_pooleboot_readiness.json", bound_paths)
        self.assertIn("runs/native_boot_handoff_readiness.json", bound_paths)
        self.assertIn("runs/native_boot_trust_readiness.json", bound_paths)
        self.assertIn("runs/native_boot_config_readiness.json", bound_paths)
        self.assertIn("runs/native_elf_loader_readiness.json", bound_paths)
        self.assertIn("runs/native_initial_system_readiness.json", bound_paths)
        self.assertIn("runs/native_recovery_readiness.json", bound_paths)
        self.assertIn("runs/native_symbol_readiness.json", bound_paths)
        self.assertIn("runs/native_microcode_readiness.json", bound_paths)
        self.assertIn("runs/native_firmware_readiness.json", bound_paths)
        self.assertIn("runs/native_policy_readiness.json", bound_paths)
        self.assertIn("specs/native-policy-contract.json", bound_paths)
        self.assertIn("runs/native_kernel_entry_readiness.json", bound_paths)
        self.assertIn("runs/native_kernel_load_readiness.json", bound_paths)
        self.assertIn("runs/native-kernel-revalidation-readiness.json", bound_paths)
        self.assertIn("runs/native-kernel-transfer-readiness.json", bound_paths)
        self.assertIn("specs/native-kernel-transfer-contract.json", bound_paths)
        self.assertIn("docs/native-kernel-transfer.md", bound_paths)
        self.assertIn("runs/native-kernel-cpu-policy-readiness.json", bound_paths)
        self.assertIn("specs/native-kernel-cpu-policy-contract.json", bound_paths)
        self.assertIn("specs/native-kernel-cpu-policy-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-kernel-cpu-policy.md", bound_paths)
        self.assertIn("runtime/native_kernel_cpu_policy.py", bound_paths)
        self.assertIn("tools/qualify_native_kernel_cpu_policy.py", bound_paths)
        self.assertIn("tests/test_native_kernel_cpu_policy.py", bound_paths)
        self.assertIn("runs/native-kernel-xstate-exception-readiness.json", bound_paths)
        self.assertIn("specs/native-kernel-xstate-exception-contract.json", bound_paths)
        self.assertIn("runtime/native_kernel_xstate_exception.py", bound_paths)
        self.assertIn("tools/qualify_native_kernel_xstate_exception.py", bound_paths)
        self.assertIn("tests/test_native_kernel_xstate_exception.py", bound_paths)
        self.assertIn("runs/native-kernel-privilege-msr-policy-readiness.json", bound_paths)
        self.assertIn("specs/native-kernel-privilege-msr-policy-contract.json", bound_paths)
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", bound_paths)
        self.assertIn("specs/native-kernel-physical-memory-contract.json", bound_paths)
        self.assertIn("native/kernel/src/privilege_msr.rs", bound_paths)
        self.assertIn("runtime/native_kernel_privilege_msr_policy.py", bound_paths)
        self.assertIn("tools/qualify_native_kernel_privilege_msr_policy.py", bound_paths)
        self.assertIn("tests/test_native_kernel_privilege_msr_policy.py", bound_paths)
        self.assertIn("runs/native_system_manifest_readiness.json", bound_paths)
        self.assertIn("specs/native-boot-config-contract.json", bound_paths)
        self.assertIn("specs/native-boot-config-golden-vectors.json", bound_paths)
        self.assertIn("docs/native-boot-config.md", bound_paths)
        self.assertIn("specs/native-elf-loader-contract.json", bound_paths)
        self.assertIn("specs/native-elf-loader-contract.schema.json", bound_paths)
        self.assertIn("specs/native-elf-loader-golden-vectors.json", bound_paths)
        self.assertIn("specs/native-elf-loader-golden-vectors.schema.json", bound_paths)
        self.assertIn("specs/native-elf-loader-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-elf-loader.md", bound_paths)
        self.assertIn("specs/native-initial-system-contract.json", bound_paths)
        self.assertIn("specs/native-initial-system-contract.schema.json", bound_paths)
        self.assertIn("specs/native-initial-system-golden-vectors.json", bound_paths)
        self.assertIn("specs/native-initial-system-golden-vectors.schema.json", bound_paths)
        self.assertIn("specs/native-initial-system-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-initial-system-bundle.md", bound_paths)
        self.assertIn("docs/native-initial-system-profile.md", bound_paths)
        self.assertIn("specs/native-recovery-contract.json", bound_paths)
        self.assertIn("specs/native-recovery-contract.schema.json", bound_paths)
        self.assertIn("specs/native-recovery-golden-vectors.json", bound_paths)
        self.assertIn("specs/native-recovery-golden-vectors.schema.json", bound_paths)
        self.assertIn("specs/native-recovery-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-recovery-bundle.md", bound_paths)
        self.assertIn("specs/native-kernel-entry-contract.json", bound_paths)
        self.assertIn("specs/native-kernel-entry-contract.schema.json", bound_paths)
        self.assertIn("specs/native-kernel-entry-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-kernel-entry.md", bound_paths)
        self.assertIn("specs/native-kernel-load-contract.json", bound_paths)
        self.assertIn("specs/native-kernel-load-contract.schema.json", bound_paths)
        self.assertIn("specs/native-kernel-load-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-kernel-load.md", bound_paths)
        self.assertIn("specs/native-kernel-revalidation-contract.json", bound_paths)
        self.assertIn("specs/native-kernel-revalidation-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-kernel-revalidation.md", bound_paths)
        self.assertIn("specs/native-firmware-contract.json", bound_paths)
        self.assertIn("specs/native-firmware-golden-vectors.json", bound_paths)
        self.assertIn("docs/native-firmware-manifest.md", bound_paths)
        self.assertIn("specs/native-system-manifest-contract.json", bound_paths)
        self.assertIn("specs/native-system-manifest-golden-vectors.json", bound_paths)
        self.assertIn("specs/native-boot-digest-provider.json", bound_paths)
        self.assertIn("docs/native-system-manifest.md", bound_paths)
        self.assertIn("specs/native-boot-handoff-contract.json", bound_paths)
        self.assertIn("specs/native-boot-handoff-golden-vectors.json", bound_paths)
        self.assertIn("docs/native-boot-handoff.md", bound_paths)
        self.assertIn("specs/native-pooleboot-proof.json", bound_paths)
        self.assertIn("docs/native-pooleboot-proof.md", bound_paths)
        self.assertIn(
            "specs/pooleos-kernel-charter.md",
            bound_paths,
        )
        self.assertIn(
            "specs/native-v1-objectives.schema.json",
            bound_paths,
        )
        self.assertIn(
            "specs/native-tier0-lock.json",
            bound_paths,
        )
        self.assertIn(
            "specs/native-tier0-profile.json",
            bound_paths,
        )
        self.assertIn(
            "docs/native-tier0-qemu.md",
            bound_paths,
        )
        self.assertIn(
            "docs/native-formal-models.md",
            bound_paths,
        )
        self.assertIn(
            "specs/native-model-contract.json",
            bound_paths,
        )
        self.assertIn(
            "specs/native-model-toolchain-lock.json",
            bound_paths,
        )
        for binding in self.artifact["bound_sources"]:
            self.assertFalse(Path(binding["path"]).is_absolute())
            self.assertNotIn("C:\\Users", binding["path"])
            data = (ROOT / binding["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            self.assertEqual(len(data), binding["byte_count"])
        self.assertFalse(self.artifact["claim_boundary"]["private_source_content_embedded"])

    def test_repository_binding_targets_owner_public_remote(self) -> None:
        repository = self.artifact["repository"]
        self.assertTrue(repository["initialized"])
        self.assertEqual(repository["current_branch"], "main")
        self.assertEqual(repository["configured_remote"], "https://github.com/rookepoole/PooleOS.git")
        self.assertEqual(repository["visibility"], "public")
        self.assertEqual(repository["publication_state"], "initialized_published")

    def test_license_and_publication_boundary_are_explicit(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        publication = (ROOT / "docs" / "publication-boundary.md").read_text(encoding="utf-8")
        self.assertIn("PolyForm Noncommercial License 1.0.0", license_text)
        self.assertIn("Copyright (c) 2026 Rooke Poole", license_text)
        self.assertIn("must not contain", publication)
        self.assertIn("signing private keys", publication)
        self.assertIn("internal PDC GPU, CPU, RAM-lane", publication)


if __name__ == "__main__":
    unittest.main()
