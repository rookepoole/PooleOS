import hashlib
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402


class PdcProductionRoadmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roadmap_path = ROOT / "runs" / "pdc_production_roadmap.json"
        cls.roadmap = json.loads(cls.roadmap_path.read_text(encoding="utf-8"))
        cls.schema = json.loads(
            (ROOT / "specs" / "pdc-production-roadmap.schema.json").read_text(encoding="utf-8")
        )
        cls.coverage_path = ROOT / "runs" / "pooleos_native_checklist_coverage.json"
        cls.coverage = json.loads(cls.coverage_path.read_text(encoding="utf-8"))

    def test_roadmap_matches_schema(self) -> None:
        self.assertEqual(validate_json(self.roadmap, self.schema), [])

    def test_native_architecture_is_unambiguous(self) -> None:
        architecture = self.roadmap["architecture"]
        self.assertEqual(architecture["mode"], "native_capability_microkernel")
        self.assertEqual(architecture["bootloader"], "PooleBoot")
        self.assertEqual(architecture["kernel"], "PooleKernel")
        self.assertEqual(architecture["production_base"], "original_pooleos")
        self.assertEqual(architecture["completion_phase_range"], "N0-N39")
        self.assertFalse(architecture["legacy_bios_required"])
        self.assertFalse(architecture["production_kernel_modules_v1"])
        for forbidden in ("Linux", "Debian", "Buildroot", "GRUB", "Limine", "systemd"):
            self.assertIn(forbidden, architecture["forbidden_production_substitutes"])

    def test_phase_summary_subphases_and_dependencies_are_consistent(self) -> None:
        phases = self.roadmap["phases"]
        phase_ids = [phase["id"] for phase in phases]
        self.assertEqual(phase_ids, [f"N{index}" for index in range(40)])
        self.assertEqual(len({item for item in phase_ids}), 40)

        status_counts = Counter(phase["status"] for phase in phases)
        summary = self.roadmap["phase_summary"]
        self.assertEqual(summary["total"], 40)
        self.assertEqual(summary["complete"], status_counts["complete"])
        self.assertEqual(summary["partial"], status_counts["partial"])
        self.assertEqual(summary["blocked"], status_counts["blocked"])
        self.assertEqual(summary["not_started"], status_counts["not_started"])
        self.assertEqual(summary["subphase_total"], sum(len(phase["subphases"]) for phase in phases))
        self.assertEqual(summary["subphase_total"], 301)

        phase_id_set = set(phase_ids)
        all_subphase_ids = []
        for phase in phases:
            self.assertNotIn(phase["id"], phase["depends_on"])
            self.assertTrue(set(phase["depends_on"]).issubset(phase_id_set))
            for subphase in phase["subphases"]:
                self.assertTrue(subphase["id"].startswith(f"{phase['id']}."))
                all_subphase_ids.append(subphase["id"])
        self.assertEqual(len(all_subphase_ids), len(set(all_subphase_ids)))

        graph = {phase["id"]: phase["depends_on"] for phase in phases}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(phase_id: str) -> None:
            self.assertNotIn(phase_id, visiting, f"dependency cycle through {phase_id}")
            if phase_id in visited:
                return
            visiting.add(phase_id)
            for dependency in graph[phase_id]:
                visit(dependency)
            visiting.remove(phase_id)
            visited.add(phase_id)

        for phase_id in phase_ids:
            visit(phase_id)

    def test_build_plan_and_machine_phase_surfaces_match(self) -> None:
        plan = (ROOT / "docs" / "pdc-production-build-plan.md").read_text(encoding="utf-8")
        plan_phases = re.findall(r"^### (N\d+) - (.+) \(`([^`]+)`\)$", plan, flags=re.MULTILINE)
        machine_phases = [(phase["id"], phase["title"], phase["status"]) for phase in self.roadmap["phases"]]
        self.assertEqual(plan_phases, machine_phases)
        plan_subphases = re.findall(r"^- (N\d+\.\d+) ", plan, flags=re.MULTILINE)
        machine_subphases = [subphase["id"] for phase in self.roadmap["phases"] for subphase in phase["subphases"]]
        self.assertEqual(plan_subphases, machine_subphases)

    def test_master_checklist_binding_is_exact(self) -> None:
        checklist = self.roadmap["master_checklist"]
        source_path = ROOT / checklist["source_path"]
        source_bytes = source_path.read_bytes()
        self.assertEqual(hashlib.sha256(source_bytes).hexdigest().upper(), checklist["source_sha256"])
        self.assertEqual(len(source_bytes), 416063)
        self.assertEqual(len(source_bytes.decode("utf-8").splitlines()), 10512)
        self.assertEqual(checklist["checkbox_line_count"], 8998)
        self.assertEqual(checklist["implementation_item_count"], 8996)
        self.assertEqual(checklist["section_count"], 171)
        self.assertEqual(checklist["coverage_status"], "pass")
        self.assertEqual(checklist["coverage_sha256"], hashlib.sha256(self.coverage_path.read_bytes()).hexdigest().upper())
        self.assertEqual(checklist["added_requirement_count"], 44)

    def test_phase_checklist_mapping_matches_coverage(self) -> None:
        coverage_by_phase = {item["phase_id"]: item for item in self.coverage["phase_coverage"]}
        mapped_sections = []
        for phase in self.roadmap["phases"]:
            expected = coverage_by_phase[phase["id"]]
            self.assertEqual(phase["source_section_ids"], expected["source_section_ids"])
            self.assertEqual(phase["source_checkbox_count"], expected["source_checkbox_count"])
            self.assertEqual(phase["added_requirement_ids"], expected["added_requirement_ids"])
            mapped_sections.extend(phase["source_section_ids"])
        self.assertEqual(sorted(mapped_sections), [f"{index:03d}" for index in range(171)])

    def test_production_boundary_and_next_move_are_explicit(self) -> None:
        self.assertFalse(self.roadmap["production_ready"])
        self.assertEqual(self.roadmap["baseline"]["pooleos_cycle"], 121)
        self.assertEqual(self.roadmap["baseline"]["pooleos_test_count"], 755)
        native = self.roadmap["baseline"]["native"]
        self.assertTrue(native["source_controlled"])
        self.assertTrue(native["pooleboot_exists"])
        self.assertTrue(native["poolekernel_exists"])
        self.assertTrue(
            all(
                value is False
                for key, value in native.items()
                if key not in {"source_controlled", "pooleboot_exists", "poolekernel_exists"}
            )
        )
        historical = self.roadmap["baseline"]["historical_consistency_release_gate"]
        self.assertFalse(historical["production_ready"])
        self.assertEqual(historical["native_promotion_role"], "historical_non_promoting")
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        self.assertEqual(current["passed_checks"], 88)
        self.assertEqual(current["total_checks"], 88)
        self.assertEqual(current["artifact_count"], 83)
        self.assertEqual(current["explicit_gap_count"], 20)
        self.assertFalse(current["production_ready"])
        self.assertEqual(self.roadmap["immediate_next_move"]["id"], "N0-HW-KEY-ACQUIRE-001")
        self.assertTrue(self.roadmap["immediate_next_move"]["blocked"])

    def test_goal_charter_and_turn_protocol_are_bound(self) -> None:
        charter = self.roadmap["goal_charter"]
        charter_text = (ROOT / charter["path"]).read_text(encoding="utf-8")
        self.assertEqual(charter["version"], "2.0.0-native-reset")
        self.assertEqual(charter["completion_phase_range"], "N0-N39")
        self.assertIn("Poole-authored `PooleBoot.efi`", charter_text)
        self.assertIn("PooleKernel microkernel", charter_text)
        self.assertIn("Per-Turn Next-Best-Move Loop", charter_text)
        self.assertIn("not the production foundation", charter_text)

        protocol = self.roadmap["execution_protocol"]
        self.assertTrue(protocol["updates_required_each_goal_turn"])
        self.assertTrue(protocol["inspect_live_pooleglyph_each_turn"])
        self.assertTrue(protocol["verify_master_checklist_coverage_each_turn"])
        self.assertTrue(protocol["new_work_must_be_flagged"])
        self.assertEqual(protocol["last_updated_cycle"], self.roadmap["baseline"]["pooleos_cycle"])
        self.assertEqual(protocol["selected_move_id"], "N7-ERRATA-POLICY-001")
        self.assertEqual(
            protocol["owner_independent_next_move_id"],
            "N7-XSTATE-POLICY-001",
        )
        self.assertIn("runs/hardware_target_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_tier0_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_model_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_boot_trust_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_pooleboot_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_boot_handoff_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_boot_config_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_elf_loader_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_kernel_entry_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_kernel_load_readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-revalidation-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-transfer-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-trap-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-cpu-policy-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-errata-policy-readiness.json", protocol["required_records"])
        self.assertIn("runs/native_initial_system_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_recovery_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_symbol_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_microcode_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_firmware_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_policy_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_system_manifest_readiness.json", protocol["required_records"])
        self.assertIn("runs/n0_owner_decision_packet.json", protocol["required_records"])
        self.assertIn("runs/n0_owner_response_receipt.json", protocol["required_records"])
        self.assertIn("runs/native_v1_objectives_readiness.json", protocol["required_records"])
        for record in protocol["required_records"]:
            self.assertTrue((ROOT / record).is_file(), record)

    def test_flags_and_gaps_are_native_and_traceable(self) -> None:
        phase_ids = {phase["id"] for phase in self.roadmap["phases"]}
        flags = self.roadmap["implementation_flags"]
        self.assertEqual(len(flags), 65)
        self.assertEqual(len({flag["id"] for flag in flags}), 65)
        self.assertTrue(any(flag["class"] == "STOP_SHIP" and flag["status"] == "open" for flag in flags))
        self.assertEqual(next(flag for flag in flags if flag["id"] == "FLAG-BUILDROOT-LEGACY-001")["status"], "closed")
        objectives_flag = next(flag for flag in flags if flag["id"] == "FLAG-N0-OBJECTIVES-001")
        self.assertEqual(objectives_flag["class"], "REQUIRED")
        self.assertIn("runs/native_v1_objectives_readiness.json", objectives_flag["evidence"])
        scope_flag = next(flag for flag in flags if flag["id"] == "FLAG-N0-RATIFICATION-SCOPE-001")
        self.assertEqual(scope_flag["class"], "REQUIRED")
        self.assertEqual(scope_flag["status"], "closed")
        self.assertIn("specs/native-v1-objectives.schema.json", scope_flag["evidence"])
        self.assertIn("runs/adr_ratification_readiness.json", scope_flag["evidence"])
        key_flag = next(flag for flag in flags if flag["id"] == "FLAG-N0-GOVERNANCE-KEY-001")
        self.assertEqual(key_flag["class"], "BLOCKER")
        self.assertEqual(key_flag["status"], "open")
        self.assertIn("runs/n0_owner_response_receipt.json", key_flag["evidence"])
        cpuid_flag = next(flag for flag in flags if flag["id"] == "FLAG-N2-CPUID-001")
        self.assertEqual(cpuid_flag["class"], "REQUIRED")
        self.assertEqual(cpuid_flag["status"], "closed")
        self.assertIn("tools/collect_tier1_hardware.ps1", cpuid_flag["evidence"])
        self.assertIn("runs/tier1_hardware_observation.json", cpuid_flag["evidence"])
        privileged_flag = next(flag for flag in flags if flag["id"] == "FLAG-N2-PRIVILEGED-PROBE-001")
        self.assertEqual(privileged_flag["class"], "BLOCKER")
        self.assertEqual(privileged_flag["status"], "open")
        self.assertIn("specs/tier1-hardware-capture.schema.json", privileged_flag["evidence"])
        tier0_profile_flag = next(flag for flag in flags if flag["id"] == "FLAG-N4-PROFILE-001")
        self.assertEqual(tier0_profile_flag["class"], "REQUIRED")
        self.assertEqual(tier0_profile_flag["status"], "closed")
        self.assertIn("runs/native_tier0_readiness.json", tier0_profile_flag["evidence"])
        model_flag = next(flag for flag in flags if flag["id"] == "FLAG-N4-MODELS-001")
        self.assertEqual(model_flag["class"], "BLOCKER")
        self.assertEqual(model_flag["status"], "open")
        self.assertIn("runs/native_model_readiness.json", model_flag["evidence"])
        ipc_model_flag = next(flag for flag in flags if flag["id"] == "FLAG-N4-IPC-MODEL-001")
        self.assertEqual(ipc_model_flag["class"], "REQUIRED")
        self.assertEqual(ipc_model_flag["status"], "closed")
        self.assertIn("models/tla/PooleIPC.tla", ipc_model_flag["evidence"])
        scheduler_model_flag = next(flag for flag in flags if flag["id"] == "FLAG-N4-SCHEDULER-MODEL-001")
        self.assertEqual(scheduler_model_flag["class"], "REQUIRED")
        self.assertEqual(scheduler_model_flag["status"], "closed")
        self.assertIn("models/tla/PooleScheduler.tla", scheduler_model_flag["evidence"])
        poolefs_model_flag = next(flag for flag in flags if flag["id"] == "FLAG-N4-POOLEFS-MODEL-001")
        self.assertEqual(poolefs_model_flag["class"], "REQUIRED")
        self.assertEqual(poolefs_model_flag["status"], "closed")
        self.assertIn("models/tla/PooleFS.tla", poolefs_model_flag["evidence"])
        pooleboot_proof_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-POOLEBOOT-PROOF-001")
        self.assertEqual(pooleboot_proof_flag["class"], "REQUIRED")
        self.assertEqual(pooleboot_proof_flag["status"], "closed")
        self.assertIn("runs/native_pooleboot_readiness.json", pooleboot_proof_flag["evidence"])
        bootproto_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-BOOTPROTO-001")
        self.assertEqual(bootproto_flag["class"], "REQUIRED")
        self.assertEqual(bootproto_flag["status"], "closed")
        self.assertIn("runs/native_boot_handoff_readiness.json", bootproto_flag["evidence"])
        bootcfg_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-BOOTCFG-001")
        self.assertEqual(bootcfg_flag["class"], "REQUIRED")
        self.assertEqual(bootcfg_flag["status"], "closed")
        self.assertIn("runs/native_boot_config_readiness.json", bootcfg_flag["evidence"])
        elf_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-ELF-001")
        self.assertEqual(elf_flag["class"], "REQUIRED")
        self.assertEqual(elf_flag["status"], "closed")
        self.assertIn("runs/native_elf_loader_readiness.json", elf_flag["evidence"])
        self.assertIn("tools/qualify_native_elf_loader.py", elf_flag["evidence"])
        kernel_load_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-KLOAD-001")
        self.assertEqual(kernel_load_flag["class"], "REQUIRED")
        self.assertEqual(kernel_load_flag["status"], "closed")
        self.assertIn("runs/native_kernel_load_readiness.json", kernel_load_flag["evidence"])
        self.assertIn("tools/qualify_native_kernel_load.py", kernel_load_flag["evidence"])
        initial_bundle_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-INIT-BUNDLE-001"
        )
        self.assertEqual(initial_bundle_flag["class"], "REQUIRED")
        self.assertEqual(initial_bundle_flag["status"], "closed")
        self.assertIn("runs/native_initial_system_readiness.json", initial_bundle_flag["evidence"])
        self.assertIn("tools/qualify_native_initial_system.py", initial_bundle_flag["evidence"])
        recovery_bundle_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-RECOVERY-BUNDLE-001"
        )
        self.assertEqual(recovery_bundle_flag["class"], "REQUIRED")
        self.assertEqual(recovery_bundle_flag["status"], "closed")
        self.assertIn("runs/native_recovery_readiness.json", recovery_bundle_flag["evidence"])
        self.assertIn("tools/qualify_native_recovery.py", recovery_bundle_flag["evidence"])
        symbol_bundle_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-SYMBOL-BUNDLE-001"
        )
        self.assertEqual(symbol_bundle_flag["class"], "REQUIRED")
        self.assertEqual(symbol_bundle_flag["status"], "closed")
        self.assertIn("runs/native_symbol_readiness.json", symbol_bundle_flag["evidence"])
        self.assertIn("tools/qualify_native_symbols.py", symbol_bundle_flag["evidence"])
        microcode_bundle_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-MICROCODE-BUNDLE-001"
        )
        self.assertEqual(microcode_bundle_flag["class"], "REQUIRED")
        self.assertEqual(microcode_bundle_flag["status"], "closed")
        self.assertIn("runs/native_microcode_readiness.json", microcode_bundle_flag["evidence"])
        self.assertIn("tools/qualify_native_microcode.py", microcode_bundle_flag["evidence"])
        firmware_bundle_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-FIRMWARE-BUNDLE-001"
        )
        self.assertEqual(firmware_bundle_flag["class"], "REQUIRED")
        self.assertEqual(firmware_bundle_flag["status"], "closed")
        self.assertIn("runs/native_firmware_readiness.json", firmware_bundle_flag["evidence"])
        self.assertIn("tools/qualify_native_firmware.py", firmware_bundle_flag["evidence"])
        policy_bundle_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-POLICY-BUNDLE-001"
        )
        self.assertEqual(policy_bundle_flag["class"], "REQUIRED")
        self.assertEqual(policy_bundle_flag["status"], "closed")
        self.assertIn("runs/native_policy_readiness.json", policy_bundle_flag["evidence"])
        self.assertIn("tools/qualify_native_policy.py", policy_bundle_flag["evidence"])
        inner_semantics_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-INIT-SEMANTICS-001"
        )
        self.assertEqual(inner_semantics_flag["status"], "closed")
        inner_parse_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-INNER-PARSE-001"
        )
        self.assertEqual(inner_parse_flag["class"], "REQUIRED")
        self.assertEqual(inner_parse_flag["status"], "closed")
        self.assertIn("runtime/native_inner_live.py", inner_parse_flag["evidence"])
        inner_trust_contract_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-INNER-TRUST-CONTRACT-001"
        )
        self.assertEqual(inner_trust_contract_flag["class"], "REQUIRED")
        self.assertEqual(inner_trust_contract_flag["status"], "closed")
        self.assertIn("runs/native_boot_trust_readiness.json", inner_trust_contract_flag["evidence"])
        backend_model_flag = next(
            flag
            for flag in flags
            if flag["id"] == "FLAG-N5-INNER-TRUST-BACKEND-MODEL-001"
        )
        self.assertEqual(backend_model_flag["class"], "REQUIRED")
        self.assertEqual(backend_model_flag["status"], "closed")
        self.assertIn("native/trust/src/backend.rs", backend_model_flag["evidence"])
        self.assertIn(
            "runs/native_boot_trust_readiness.json",
            backend_model_flag["evidence"],
        )
        kernel_revalidation_flag = next(
            flag
            for flag in flags
            if flag["id"] == "FLAG-N5-INNER-KERNEL-REVALIDATE-001"
        )
        self.assertEqual(kernel_revalidation_flag["class"], "REQUIRED")
        self.assertEqual(kernel_revalidation_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-revalidation-readiness.json",
            kernel_revalidation_flag["evidence"],
        )
        kernel_transfer_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-KERNEL-TRANSFER-001"
        )
        self.assertEqual(kernel_transfer_flag["class"], "REQUIRED")
        self.assertEqual(kernel_transfer_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-transfer-readiness.json",
            kernel_transfer_flag["evidence"],
        )
        inner_trust_state_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-INNER-TRUST-STATE-001"
        )
        self.assertEqual(inner_trust_state_flag["class"], "BLOCKER")
        self.assertEqual(inner_trust_state_flag["status"], "open")
        inner_enforcement_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-INNER-ENFORCEMENT-001"
        )
        self.assertEqual(inner_enforcement_flag["status"], "open")
        self.assertIn("runs/native_policy_readiness.json", inner_enforcement_flag["evidence"])
        manifest_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-MANIFEST-001")
        self.assertEqual(manifest_flag["class"], "REQUIRED")
        self.assertEqual(manifest_flag["status"], "closed")
        self.assertIn("runs/native_system_manifest_readiness.json", manifest_flag["evidence"])
        self.assertIn("tools/qualify_native_system_manifest.py", manifest_flag["evidence"])
        live_pbp1_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-PBP1-LIVE-001")
        self.assertEqual(live_pbp1_flag["class"], "REQUIRED")
        self.assertEqual(live_pbp1_flag["status"], "closed")
        self.assertIn("native/livehandoff/src/lib.rs", live_pbp1_flag["evidence"])
        self.assertIn("runtime/native_live_boot_handoff.py", live_pbp1_flag["evidence"])
        kmap_flag = next(flag for flag in flags if flag["id"] == "FLAG-N5-KMAP-001")
        self.assertEqual(kmap_flag["class"], "REQUIRED")
        self.assertEqual(kmap_flag["status"], "closed")
        self.assertIn("native/boot/src/kmap.rs", kmap_flag["evidence"])
        self.assertIn("runtime/native_kernel_map.py", kmap_flag["evidence"])
        handoff_exit_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N5-HANDOFF-EXIT-001"
        )
        self.assertEqual(handoff_exit_flag["class"], "REQUIRED")
        self.assertEqual(handoff_exit_flag["status"], "closed")
        self.assertIn("native/boot/src/exit.rs", handoff_exit_flag["evidence"])
        self.assertIn("runtime/native_boot_exit.py", handoff_exit_flag["evidence"])
        kernel_entry_flag = next(flag for flag in flags if flag["id"] == "FLAG-N6-KENTRY-001")
        self.assertEqual(kernel_entry_flag["class"], "REQUIRED")
        self.assertEqual(kernel_entry_flag["status"], "closed")
        self.assertIn("runs/native_kernel_entry_readiness.json", kernel_entry_flag["evidence"])
        framebuffer_mapping_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N6-FRAMEBUFFER-MAP-001"
        )
        self.assertEqual(framebuffer_mapping_flag["class"], "REQUIRED")
        self.assertEqual(framebuffer_mapping_flag["status"], "open")
        self.assertIn("specs/native-kernel-entry-contract.json", framebuffer_mapping_flag["evidence"])
        digest_flag = next(flag for flag in flags if flag["id"] == "FLAG-N6-BOOT-DIGEST-001")
        self.assertEqual(digest_flag["class"], "REQUIRED")
        self.assertEqual(digest_flag["status"], "open")
        self.assertIn("specs/native-boot-digest-provider.json", digest_flag["evidence"])
        trap_flag = next(flag for flag in flags if flag["id"] == "FLAG-N7-TRAP-001")
        self.assertEqual(trap_flag["class"], "REQUIRED")
        self.assertEqual(trap_flag["status"], "closed")
        self.assertIn("runs/native-kernel-trap-readiness.json", trap_flag["evidence"])
        cpu_flag = next(flag for flag in flags if flag["id"] == "FLAG-N7-CPU-POLICY-001")
        self.assertEqual(cpu_flag["class"], "REQUIRED")
        self.assertEqual(cpu_flag["status"], "closed")
        self.assertIn("runs/native-kernel-cpu-policy-readiness.json", cpu_flag["evidence"])
        errata_flag = next(flag for flag in flags if flag["id"] == "FLAG-N7-ERRATA-POLICY-001")
        self.assertEqual(errata_flag["class"], "REQUIRED")
        self.assertEqual(errata_flag["status"], "closed")
        self.assertIn("runs/native-kernel-errata-policy-readiness.json", errata_flag["evidence"])
        errata_source_flag = next(flag for flag in flags if flag["id"] == "FLAG-N7-ERRATA-SOURCE-001")
        self.assertEqual(errata_source_flag["class"], "STOP_SHIP")
        self.assertEqual(errata_source_flag["status"], "open")
        microcode_floor_flag = next(flag for flag in flags if flag["id"] == "FLAG-N7-MICROCODE-FLOOR-001")
        self.assertEqual(microcode_floor_flag["class"], "STOP_SHIP")
        self.assertEqual(microcode_floor_flag["status"], "open")
        codev_flag = next(flag for flag in flags if flag["id"] == "FLAG-PGL-CODEV-001")
        self.assertEqual(codev_flag["class"], "REQUIRED")
        self.assertEqual(codev_flag["status"], "open")
        self.assertIn("runs/pooleglyph_source_anchor.json", codev_flag["evidence"])
        core_ir_flag = next(flag for flag in flags if flag["id"] == "FLAG-PGL-CORE-IR-001")
        self.assertEqual(core_ir_flag["class"], "BLOCKER")
        self.assertEqual(core_ir_flag["status"], "open")
        ip_flag = next(flag for flag in flags if flag["id"] == "FLAG-PGL-IP-001")
        self.assertEqual(ip_flag["class"], "REQUIRED")
        self.assertEqual(ip_flag["status"], "open")
        for flag in flags:
            self.assertIn(flag["phase_id"], phase_ids)
        gaps = self.roadmap["gap_summary"]
        self.assertEqual(gaps["native_program_gap_count"], len(gaps["native_program_gaps"]))
        self.assertEqual(gaps["native_program_gap_count"], 20)
        self.assertTrue(gaps["historical_release_gaps_are_non_promoting"])

        n2 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N2")
        n2_statuses = {subphase["id"]: subphase["status"] for subphase in n2["subphases"]}
        self.assertEqual(n2_statuses["N2.1"], "partial")
        self.assertEqual(n2_statuses["N2.2"], "partial")
        self.assertEqual(n2_statuses["N2.3"], "not_started")
        self.assertEqual(n2_statuses["N2.4"], "partial")
        self.assertEqual(n2_statuses["N2.5"], "partial")
        self.assertEqual(n2_statuses["N2.6"], "partial")
        self.assertTrue(
            any(item.startswith("runs/hardware_target_readiness.json:") for item in n2["current_evidence"])
        )
        self.assertTrue(any("16 CPUID records" in item for item in n2["current_evidence"]))
        self.assertTrue(any("MSR access remains pending" in item for item in n2["current_gaps"]))

        n4 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N4")
        n4_statuses = {subphase["id"]: subphase["status"] for subphase in n4["subphases"]}
        for subphase_id in ("N4.1", "N4.2", "N4.3", "N4.4", "N4.5", "N4.6"):
            self.assertEqual(n4_statuses[subphase_id], "partial")
        self.assertTrue(any(item.startswith("runs/native_tier0_readiness.json:") for item in n4["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_model_readiness.json:") for item in n4["current_evidence"]))
        self.assertTrue(any("PooleVirtualMemory.tla" in item for item in n4["current_evidence"]))
        self.assertTrue(any("PooleIPC.tla" in item for item in n4["current_evidence"]))
        self.assertTrue(any("PooleScheduler.tla" in item for item in n4["current_evidence"]))
        self.assertTrue(any("PooleFS.tla" in item for item in n4["current_evidence"]))
        self.assertTrue(any("implementation-trace cross-checks" in item for item in n4["current_gaps"]))

        n5 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N5")
        self.assertEqual(n5["status"], "partial")
        n5_statuses = {subphase["id"]: subphase["status"] for subphase in n5["subphases"]}
        for subphase_id in ("N5.1", "N5.2", "N5.3", "N5.4", "N5.5", "N5.7"):
            self.assertEqual(n5_statuses[subphase_id], "partial")
        self.assertEqual(n5_statuses["N5.6"], "partial")
        self.assertEqual(n5_statuses["N5.8"], "partial")
        self.assertEqual(n5_statuses["N5.9"], "partial")
        self.assertTrue(any(item.startswith("runs/native_pooleboot_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_boot_handoff_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_boot_config_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_elf_loader_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_kernel_load_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-transfer-readiness.json:")
                for item in n5["current_evidence"]
            )
        )
        self.assertTrue(any(item.startswith("runs/native_initial_system_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_recovery_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_symbol_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_microcode_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_firmware_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_policy_readiness.json:") for item in n5["current_evidence"]))
        self.assertTrue(any(item.startswith("runs/native_boot_trust_readiness.json:") for item in n5["current_evidence"]))
        self.assertIn("ADD-BOOT-007", n5["added_requirement_ids"])
        self.assertIn("ADD-BOOT-008", n5["added_requirement_ids"])
        self.assertIn("ADD-BOOT-009", n5["added_requirement_ids"])
        self.assertIn("ADD-BOOT-010", n5["added_requirement_ids"])
        self.assertIn("ADD-BOOT-011", n5["added_requirement_ids"])
        self.assertIn("ADD-BOOT-012", n5["added_requirement_ids"])
        self.assertTrue(any("signature-backed trusted selection" in item for item in n5["current_gaps"]))

        n6 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N6")
        self.assertEqual(n6["status"], "partial")
        n6_statuses = {subphase["id"]: subphase["status"] for subphase in n6["subphases"]}
        for subphase_id in ("N6.4", "N6.5", "N6.6"):
            self.assertEqual(n6_statuses[subphase_id], "partial")
        for subphase_id in ("N6.1", "N6.2", "N6.3", "N6.7"):
            self.assertEqual(n6_statuses[subphase_id], "not_started")
        self.assertIn("ADD-KERNEL-001", n6["added_requirement_ids"])
        self.assertIn("ADD-BOOT-003", n6["added_requirement_ids"])
        self.assertTrue(
            any(item.startswith("runs/native_kernel_entry_readiness.json:") for item in n6["current_evidence"])
        )
        self.assertTrue(any("production transfer" in item for item in n6["current_gaps"]))

        n7 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N7")
        self.assertEqual(n7["status"], "partial")
        n7_statuses = {subphase["id"]: subphase["status"] for subphase in n7["subphases"]}
        for subphase_id in ("N7.1", "N7.2", "N7.3", "N7.5", "N7.6"):
            self.assertEqual(n7_statuses[subphase_id], "partial")
        self.assertEqual(n7_statuses["N7.4"], "not_started")
        self.assertTrue(
            any(item.startswith("runs/native-kernel-trap-readiness.json:") for item in n7["current_evidence"])
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-cpu-policy-readiness.json:")
                for item in n7["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-errata-policy-readiness.json:")
                for item in n7["current_evidence"]
            )
        )
        self.assertIn("ADD-N7-ERRATA-SOURCE-001", n7["added_requirement_ids"])
        self.assertTrue(any("Models 40h-4Fh" in item for item in n7["current_gaps"]))

        n0 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N0")
        n0_statuses = {subphase["id"]: subphase["status"] for subphase in n0["subphases"]}
        self.assertEqual(n0_statuses["N0.6"], "partial")
        self.assertTrue(any(item.startswith("runs/native_v1_objectives_readiness.json:") for item in n0["current_evidence"]))

    def test_cycle79_pdc_evidence_is_preserved_without_native_promotion(self) -> None:
        pdc = self.roadmap["baseline"]["pdc"]
        self.assertEqual(pdc["pdc_math"]["contract_version"], "PDC-MATH-0.1")
        self.assertEqual(pdc["pdc_verifiers"]["independent_case_count"], 4324)
        self.assertEqual(pdc["pdc_verifiers"]["mismatch_count"], 0)
        self.assertEqual(pdc["pdc_representation"]["abi_version"], "PDC-REP-0.1")
        self.assertEqual(pdc["pdc_representation"]["round_trip_count"], 12436)
        self.assertEqual(pdc["pdc_golden_metamorphic"]["corpus_version"], "PDC-GOLDEN-0.2")
        self.assertEqual(pdc["pdc_qp"]["contract_version"], "PDC-QP-0.1")
        self.assertEqual(pdc["pdc_qp_stability"]["contract_version"], "PDC-QP-STABILITY-0.1")
        self.assertEqual(pdc["pdc_qp_stability"]["fresh_field_count"], 550)
        self.assertEqual(pdc["pdc_qp_stability"]["perturbation_case_count"], 2200)
        self.assertEqual(pdc["pdc_qp_stability"]["mismatch_count"], 0)
        n32 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N32")
        self.assertEqual(n32["status"], "partial")
        self.assertIn("Signed dynamics and portable/native C/CPU/RAM/GPU execution remain open", n32["current_gaps"])

    def test_live_pooleglyph_boundary_is_preserved(self) -> None:
        pooleglyph = self.roadmap["baseline"]["pooleglyph"]
        self.assertEqual(pooleglyph["checkpoint_phase"], 65)
        self.assertEqual(pooleglyph["next_required_phase"], 66)
        self.assertEqual(pooleglyph["conformance_passed"], 97)
        self.assertEqual(pooleglyph["conformance_total"], 97)
        self.assertEqual(pooleglyph["parser_kernel_promotion_status"], "blocked_until_phase66")
        self.assertEqual(
            pooleglyph["checkpoint_zip_sha256"],
            "F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC",
        )
        n34 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N34")
        self.assertEqual(n34["status"], "blocked")
        self.assertEqual(len(n34["subphases"]), 22)
        self.assertEqual(n34["added_requirement_ids"], [f"ADD-PGL-{index:03d}" for index in range(1, 7)])
        n34_statuses = {subphase["id"]: subphase["status"] for subphase in n34["subphases"]}
        self.assertEqual(n34_statuses["N34.1"], "partial")
        self.assertEqual(n34_statuses["N34.3"], "blocked")
        self.assertEqual(n34_statuses["N34.4"], "partial")
        self.assertEqual(n34_statuses["N34.6"], "partial")

    def test_source_set_preserves_prior_sources_and_adds_master_checklist(self) -> None:
        sources = self.roadmap["source_set"]
        self.assertEqual(len(sources), 8)
        self.assertEqual(len({source["id"] for source in sources}), 8)
        for source in sources:
            self.assertRegex(source["sha256"], re.compile(r"^[0-9A-F]{64}$"))
        checklist = next(source for source in sources if source["id"] == "SRC-NATIVE-CHECKLIST-1")
        self.assertEqual(checklist["sha256"], self.roadmap["master_checklist"]["source_sha256"])


if __name__ == "__main__":
    unittest.main()
