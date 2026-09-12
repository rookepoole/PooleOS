import hashlib
import importlib
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


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

    def test_current_governance_gaps_preserve_registration_and_pending_recovery(self) -> None:
        readiness = json.loads((ROOT / "runs/adr_ratification_readiness.json").read_text(encoding="utf-8"))
        self.assertEqual(readiness["trust_bootstrap"]["trusted_signer_count"], 1)
        self.assertEqual(readiness["trust_bootstrap"]["public_key_publication"], "registered")
        for gap in (self.roadmap["gap_summary"]["native_program_gaps"][0], pooleos_release_gate.DEFAULT_GAPS[0]):
            with self.subTest(gap=gap):
                self.assertIn("key is enrolled and registered", gap)
                self.assertIn("Enrollment signature verification, independent recovery custody", gap)
                self.assertIn("No alternate recovery-key profile is accepted or provisioned", gap)
                self.assertNotIn("key is unavailable", gap)
        n0 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N0")
        evidence = next(item for item in n0["current_evidence"] if item.startswith("runs/adr_ratification_readiness.json:"))
        self.assertIn("one registered hardware-backed public signer", evidence)
        self.assertNotIn("zero trusted signers", evidence)
        self.assertFalse(readiness["summary"]["ready_for_signature"])
        self.assertFalse(self.roadmap["production_ready"])

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
        self.assertEqual(checklist["added_requirement_count"], 57)

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
        self.assertEqual(self.roadmap["baseline"]["pooleos_cycle"], 173)
        self.assertEqual(self.roadmap["baseline"]["pooleos_test_count"], 950)
        n36 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N36")
        self.assertIn("Cycle 173 source inventory: 950 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertFalse(any(item.startswith("Cycle 150 host baseline:") for item in n36["current_evidence"]))
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
        self.assertEqual(current["historical_cycle172_n36_host_summary"], {
            "text": "Cycle 150 host baseline: 945 tests with three expected environment skips",
            "status": "superseded_mislabeled_dynamic_test_inventory_not_execution_evidence",
        })
        self.assertEqual(current["qualification_status"], "entry_and_boot_replay_pass_downstream_provenance_replay_pending")
        self.assertEqual(current["current_candidate_audit"]["cycle"], 173)
        self.assertEqual(current["current_candidate_audit"]["status"], "not_run")
        self.assertFalse(current["current_candidate_audit"]["aggregate_suite_passed"])
        audit = current["historical_cycle162_candidate_audit"]
        self.assertEqual(audit["cycle"], 162)
        self.assertFalse(audit["applies_to_current_source"])
        self.assertFalse(current["current_cycle_full_canonical_audit_performed"])
        self.assertFalse(audit["production_ready"])
        self.assertEqual(audit["status"], "fail")
        self.assertEqual(current["passed_checks"], 105)
        self.assertEqual(audit["passed_checks"], 81)
        self.assertEqual(audit["failed_checks"], 24)
        self.assertEqual(audit["doctor_passed_checks"], 683)
        self.assertEqual(audit["doctor_total_checks"], 706)
        self.assertFalse(audit["aggregate_suite_passed"])
        self.assertFalse(audit["include_runtime"])
        self.assertTrue(audit["both_bundle_and_replay_inputs_supplied"])
        self.assertEqual(audit["separate_pooleglyph_runtime_checks_passed"], 2)
        self.assertTrue(audit["separate_runtime_checks_do_not_change_audit_counts"])
        self.assertEqual(current["passed_check_count_scope"], "historical_cycle171_exact_final_canonical_audit")
        audit = current["historical_cycle161_candidate_audit"]
        self.assertEqual(audit["cycle"], 161)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["failed_checks"], 0)
        self.assertTrue(audit["aggregate_suite_passed"])
        self.assertTrue(audit["both_bundle_and_replay_inputs_supplied"])
        failed = current["historical_failed_candidate_audit"]
        self.assertEqual(failed["cycle"], 158)
        self.assertEqual(failed["status"], "fail")
        self.assertEqual(failed["passed_checks"], 80)
        self.assertEqual(failed["failed_checks"], 25)
        self.assertFalse(failed["aggregate_suite_passed"])
        self.assertEqual(current["last_fully_qualified_cycle"], 171)
        self.assertEqual(current["last_fully_qualified_passed_checks"], 105)
        replay = current["historical_cycle171_canonical_replay"]
        self.assertEqual((replay["passed_checks"], replay["doctor_passed_checks"], replay["pooleos_test_count"]), (105, 708, 943))
        self.assertEqual(replay["tracked_file_count"], 1527)
        self.assertTrue(replay["tracked_source_unchanged"])
        self.assertTrue(replay["include_runtime"])
        self.assertTrue(replay["both_bundle_and_replay_inputs_supplied"])
        self.assertFalse(replay["applies_to_current_source"])
        self.assertFalse(replay["production_ready"])
        self.assertEqual(replay["final_receipt_sha256"], "4F140A6AFD8EB92B65C6F3A2083D77C023E94B1FAB10BDDE7E4B27CC69F9F077")
        self.assertEqual(replay["initial_failed_receipt_sha256"], "DCF4E94EB215A07E22A1AC0D5F2179C28C30B54596C5A1FA5DEA8EF77388C792")
        self.assertEqual(replay["merged_main_commit"], "8006c7be3a8fdbe314fa049f7161285f4def03cb")
        self.assertEqual(replay["merged_tree"], "1499017b20234037b55663b413cb9469a696260d")
        replay = current["historical_cycle165_canonical_replay"]
        self.assertEqual((replay["passed_checks"], replay["doctor_passed_checks"], replay["pooleos_test_count"]), (105, 708, 924))
        self.assertEqual(replay["tracked_file_count"], 1519)
        self.assertTrue(replay["tracked_source_unchanged"])
        self.assertTrue(replay["include_runtime"])
        self.assertFalse(replay["applies_to_current_source"])
        self.assertEqual(replay["final_receipt_sha256"], "621EFC831F7FB4F29990D2E27CD26FC6BB78B6AE11453FAB856BF7615B7DED34")
        self.assertEqual(replay["merged_main_commit"], "6f9399c3cd70ebef2f7610f8b6fdb40ae262e27f")
        self.assertEqual(replay["merged_tree"], "c20156f18d2727f7e3c1df73ac05ad8126b9f470")
        replay = current["historical_cycle161_canonical_replay"]
        self.assertEqual(replay["cycle"], 161)
        self.assertEqual(replay["doctor_passed_checks"], 708)
        self.assertEqual(replay["pooleos_test_count"], 917)
        self.assertTrue(replay["both_bundle_and_replay_inputs_supplied"])
        self.assertFalse(replay["production_ready"])
        self.assertEqual(replay["final_receipt_sha256"], "B41996D9D9725C767B232C1E191A5C364B958E1DD1A516C070A071AB0BDEAD39")
        self.assertEqual(replay["merged_main_commit"], "a4c3c27fdfb5447e2a458066f97c62e5634962d4")
        self.assertEqual(current["historical_canonical_replay"]["cycle"], 157)
        self.assertEqual(current["historical_cycle160_source_projection"]["passed_checks"], 12)
        focused = current["current_focused_source_projection"]
        self.assertEqual(focused["cycle"], 173)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (22, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 5)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 6)
        self.assertTrue(focused["passing_selected_checks_do_not_requalify_old_embedded_entry_evidence"])
        self.assertEqual(focused["revalidated_dependency_execution_cycle"], 171)
        self.assertEqual(focused["core_qualification_stage_count"], 17)
        self.assertEqual((focused["lifetime_tests_per_host_profile"], focused["compile_fail_tests"]), (34, 11))
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle171_source_projection"]
        encoded = json.dumps(focused, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "51C760B3208EF8F09ABAC09F517F235DE0557A9BA2E75C4F3F56799D0A433176")
        self.assertEqual(focused["cycle"], 171)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (27, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 0)
        self.assertFalse(focused["prior_smp_new_boot_artifact_set_replay_pending"])
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["superseded_initial_runs"]), (28, 4))
        self.assertEqual((focused["negative_control_groups"], focused["negative_control_cases"]), (660, 2126))
        self.assertEqual((focused["focused_python_tests"], focused["focused_python_passed"], focused["focused_python_skipped"]), (155, 153, 2))
        self.assertEqual(focused["aggregate_gate_regression_cases"], 58)
        self.assertEqual(focused["boot_dependency_rejection_cases"], 9)
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertEqual(focused["next_dependency_move_id"], "N12-CONCURRENCY-RECLAMATION-001")
        focused = current["historical_cycle170_source_projection"]
        self.assertEqual(focused["cycle"], 170)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (14, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 13)
        self.assertTrue(focused["prior_smp_new_boot_artifact_set_replay_pending"])
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["expected_tcg_limitation_probes"]), (14, 1))
        self.assertEqual((focused["superseded_initial_runs"], focused["failed_guest_validation_runs"]), (0, 0))
        self.assertEqual((focused["negative_control_groups"], focused["aggregate_gate_regression_cases"]), (225, 17))
        self.assertEqual((focused["focused_python_tests"], focused["focused_python_passed"], focused["focused_python_skipped"]), (42, 42, 0))
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertEqual(focused["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        focused = current["historical_cycle169_source_projection"]
        self.assertEqual(focused["cycle"], 169)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (9, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 18)
        self.assertTrue(focused["prior_smp_new_boot_artifact_set_replay_pending"])
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["kernel_entry_runs"]), (6, 2))
        self.assertEqual((focused["superseded_initial_runs"], focused["failed_guest_validation_runs"]), (0, 0))
        self.assertEqual((focused["negative_controls_total"], focused["differential_cases_total"]), (678, 98304))
        self.assertEqual((focused["focused_python_tests"], focused["focused_python_passed"], focused["focused_python_skipped"]), (83, 83, 0))
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertEqual(focused["next_dependency_move_id"], "N7-TRAP-001")
        focused = current["historical_cycle168_source_projection"]
        self.assertEqual(focused["cycle"], 168)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (4, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 23)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 2)
        self.assertEqual(focused["superseded_initial_runs"], 4)
        self.assertEqual(focused["failed_guest_validation_runs"], 1)
        self.assertEqual((focused["negative_control_groups"], focused["negative_control_cases"]), (30, 249))
        self.assertEqual((focused["focused_python_tests"], focused["focused_python_passed"], focused["focused_python_skipped"]), (56, 56, 0))
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertEqual(focused["next_dependency_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        focused = current["historical_cycle165_source_projection"]
        self.assertEqual(focused["cycle"], 165)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (27, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 0)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 28)
        self.assertEqual(focused["superseded_initial_runs"], 6)
        self.assertEqual(focused["negative_control_groups"], 660)
        self.assertEqual(focused["negative_control_cases"], 2120)
        self.assertEqual(focused["focused_python_tests"], 142)
        self.assertEqual((focused["focused_python_passed"], focused["focused_python_skipped"]), (140, 2))
        self.assertEqual(focused["release_boundary_controls"], 14)
        self.assertEqual(focused["stale_acceptance_pin_controls"], 25)
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertEqual(focused["required_next_gate"], "runtime_inclusive_exact_final_qualification_publication_and_merge_review")
        self.assertEqual(focused["next_dependency_move_id"], "N12-CONCURRENCY-RECLAMATION-001")
        focused = current["historical_cycle164_source_projection"]
        self.assertEqual(focused["cycle"], 164)
        self.assertEqual(focused["passed_checks"], 13)
        self.assertEqual(focused["total_checks"], 27)
        self.assertEqual(focused["pending_downstream_native_checks"], 14)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 14)
        self.assertEqual(focused["kernel_host_tests"], 228)
        self.assertEqual(focused["focused_python_tests"], 41)
        self.assertEqual(focused["expected_tcg_limitation_probes"], 1)
        self.assertEqual(focused["negative_control_groups"], 225)
        self.assertEqual(focused["n7_live_component_gates_passed"], 5)
        self.assertEqual(focused["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle163_source_projection"]
        self.assertEqual(focused["cycle"], 163)
        self.assertEqual(focused["passed_checks"], 8)
        self.assertEqual(focused["pending_downstream_native_checks"], 19)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 6)
        self.assertEqual(focused["focused_python_tests"], 70)
        self.assertEqual(focused["valid_calendar_date_cases"], 6)
        self.assertEqual(focused["invalid_calendar_date_cases"], 20)
        self.assertFalse(focused["canonical_full_replay_performed"])
        focused = current["historical_cycle162_source_projection"]
        self.assertEqual(focused["cycle"], 162)
        self.assertEqual(focused["passed_checks"], 4)
        self.assertEqual(focused["total_checks"], 27)
        self.assertEqual(focused["pending_downstream_native_checks"], 23)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 2)
        self.assertEqual(focused["negative_control_groups"], 48)
        self.assertEqual(focused["retained_free_rejections_per_run"], 6)
        self.assertEqual(focused["kernel_host_tests"], 228)
        self.assertEqual(focused["next_dependency_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle161_source_projection"]
        self.assertEqual(focused["cycle"], 161)
        self.assertEqual(focused["passed_checks"], 26)
        self.assertEqual(focused["total_checks"], 26)
        self.assertEqual(focused["pending_downstream_native_checks"], 0)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 28)
        self.assertEqual(focused["fresh_qemu_run_count_scope"], "fourteen_requalified_memory_through_lock_profiles_in_cycle161")
        self.assertEqual(focused["excluded_overlapping_scheduler_runs"], 2)
        self.assertEqual(focused["negative_control_groups"], 658)
        self.assertEqual(focused["negative_control_cases"], 2118)
        self.assertEqual(focused["kernel_host_tests"], 219)
        self.assertEqual(focused["production_overclaim_controls"], 14)
        self.assertEqual(focused["valid_calendar_date_cases"], 6)
        self.assertEqual(focused["invalid_calendar_date_cases"], 20)
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        self.assertEqual(focused["next_dependency_move_id"], "N12-CONCURRENCY-RECLAMATION-001")
        projection = current["historical_focused_source_projection"]
        self.assertEqual(projection["cycle"], 157)
        self.assertEqual(projection["passed_checks"], 26)
        self.assertEqual(projection["pending_downstream_native_checks"], 0)
        self.assertFalse(projection["canonical_full_replay_performed"])
        self.assertEqual(projection["next_dependency_move_id"], "N12-CONCURRENCY-RECLAMATION-001")
        ownership = current["historical_cycle165_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 162)
        self.assertFalse(ownership["live_receipt_source_current"])
        self.assertEqual(ownership["live_replay_cycle"], 165)
        self.assertEqual(ownership["live_receipt_scope"], "historical_cycle165_VM_replay")
        self.assertEqual(ownership["kernel_tests_per_host_profile"], 228)
        self.assertEqual(ownership["retention_test_count"], 16)
        self.assertEqual(ownership["lifetime_tests_per_host_profile"], 24)
        self.assertEqual(ownership["pool_tests_per_host_profile"], 19)
        self.assertEqual(ownership["compile_fail_tests"], 7)
        self.assertEqual(ownership["qemu_run_count"], 2)
        self.assertEqual(ownership["retained_free_rejections_per_run"], 6)
        self.assertTrue(ownership["active_root_live_integration_verified"])
        self.assertFalse(ownership["general_task_CPU_retirement_integration_verified"])
        self.assertFalse(ownership["current_candidate_full_gate_passed"])
        for key, expected in (
            ("entry_receipt_sha256", "2A1F81312A64FF28CD7CDB4888BCBB5500FD6BCB6941248C60FFAFF390DC4A86"),
            ("virtual_memory_receipt_sha256", "C14722C1C88F853915391A9AAA648DB3CD8A9DF58C70BE7B71D94C953AC05908"),
            ("reclamation_receipt_sha256", "81FB5AA16D11CDF180433A6A11E97F357F418D6471A353A0D89348F8B485FACD"),
        ):
            self.assertEqual(ownership[key], expected)
        ownership = current["historical_cycle170_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 168)
        self.assertTrue(ownership["live_receipt_source_current"])
        self.assertEqual(ownership["source_current_scope"], "declared_inputs_only_prior_boot_artifact_set")
        self.assertTrue(ownership["current_boot_artifact_set_replay_pending"])
        self.assertTrue(ownership["ap_runtime_live_integration_verified"])
        self.assertFalse(ownership["active_root_current_image_replay_complete"])
        self.assertFalse(ownership["general_task_CPU_retirement_integration_verified"])
        self.assertFalse(ownership["current_candidate_full_gate_passed"])
        self.assertEqual((ownership["kernel_tests_per_host_profile"], ownership["retention_test_count"], ownership["ap_resource_test_count"], ownership["compile_fail_tests"]), (243, 20, 11, 9))
        self.assertEqual((ownership["attempts_per_run"], ownership["retained_free_rejections_per_attempt"], ownership["owner_release_rejections_per_attempt"]), (2, 27, 18))
        encoded = json.dumps(ownership, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "CD9119C7DDAAC0C3EFC831BC655AF48BF5A70B86A85DB68C5F41A79AECCABBCA")
        ownership = current["historical_cycle171_ownership_qualification"]
        encoded = json.dumps(ownership, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "1CD690484C5F74A5A8973F082343024719EB6219D063BB7758F222596D6A0B1E")
        ownership = current["current_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 173)
        self.assertEqual(ownership["host_qualification_cycle"], 172)
        self.assertEqual(ownership["fresh_current_cycle_qemu_runs"], 0)
        self.assertEqual((ownership["lifetime_tests_per_host_profile"], ownership["compile_fail_tests"]), (34, 11))
        self.assertFalse(ownership["task_stack_live_integration_verified"])
        self.assertEqual(ownership["live_replay_cycle"], 171)
        self.assertFalse(ownership["live_receipt_source_current"])
        self.assertEqual(ownership["source_current_scope"], "declared_inputs_current_boot_artifact_set_and_transfer_dependency")
        self.assertTrue(ownership["current_boot_artifact_set_replay_pending"])
        self.assertFalse(ownership["active_root_current_image_replay_complete"])
        self.assertFalse(ownership["general_task_CPU_retirement_integration_verified"])
        self.assertFalse(ownership["current_candidate_full_gate_passed"])
        for key, path in (
            ("entry_receipt_sha256", "runs/native_kernel_entry_readiness.json"),
            ("smp_receipt_sha256", "runs/native-kernel-smp-ipi-readiness.json"),
            ("reclamation_receipt_sha256", "runs/native-kernel-reclamation-core-readiness.json"),
        ):
            self.assertEqual(ownership[key], hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper())
        boot_chain = current["historical_cycle163_boot_chain_qualification"]
        self.assertEqual(boot_chain["cycle"], 163)
        self.assertEqual(boot_chain["fresh_qemu_runs"], 6)
        self.assertEqual(boot_chain["kernel_entry_runs"], 2)
        self.assertEqual(boot_chain["retained_file_count"], 9)
        self.assertEqual(boot_chain["focused_python_tests"], 70)
        self.assertEqual(len(boot_chain["receipt_bindings"]), 6)
        encoded = json.dumps(boot_chain, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "CD89D92692C81AD3A1B9589168DFC88167A35E924142EE48A7CA6BD598DE89C1")
        self.assertFalse(boot_chain["production_ready"])
        ownership = current["historical_cycle158_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 158)
        self.assertEqual(ownership["kernel_tests_per_host_profile"], 219)
        self.assertEqual(ownership["lifetime_tests_per_host_profile"], 24)
        self.assertTrue(ownership["current_candidate_full_gate_passed"])
        self.assertFalse(ownership["live_integration_verified"])
        self.assertEqual(current["total_checks"], 105)
        self.assertEqual(current["artifact_count"], 62)
        self.assertEqual(current["explicit_gap_count"], 20)
        self.assertFalse(current["production_ready"])
        diagnostic = current["candidate_replay_diagnostic"]
        self.assertEqual(diagnostic["status"], "failed_noncanonical_invocation")
        self.assertEqual(diagnostic["stale_downstream_native_checks"], 19)
        self.assertEqual(diagnostic["omitted_input_flags"], ["--bundle", "--replay-proof"])
        self.assertEqual(diagnostic["corrected_input_checks_passed_separately"], 2)
        self.assertFalse(diagnostic["canonical_full_replay_passed"])
        self.assertEqual(self.roadmap["immediate_next_move"]["id"], "N0-GOVERNANCE-CUSTODY-001")
        self.assertTrue(self.roadmap["immediate_next_move"]["blocked"])

    def test_dependency_replay_is_bound_to_fourteen_final_receipts(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        historical = current["historical_cycle165_dependency_qualification"]
        # Historical bindings must not be repointed at newly generated receipts.
        encoded = json.dumps(historical, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "C26860AA5A0876AA4C6D89A51FBDB54D98715EC6D7A492F78BDCCE277BE46032")
        self.assertEqual(historical["cycle"], 165)
        self.assertEqual(len(historical["receipt_bindings"]), 14)
        self.assertEqual((historical["fresh_qemu_runs"], historical["negative_control_groups"], historical["negative_control_cases"]), (28, 660, 2120))
        self.assertEqual(sum(b["fresh_runs"] for b in historical["receipt_bindings"]), 28)
        self.assertEqual(sum(b["negative_cases"] for b in historical["receipt_bindings"]), 2120)
        self.assertFalse(historical["production_ready"])

        qualification = current["historical_cycle168_dependency_qualification"]
        self.assertEqual(qualification["cycle"], 168)
        self.assertEqual(qualification["qualified_profiles"], ["smp_ipi"])
        self.assertTrue(qualification["boot_chain_replay_pending"])
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["negative_control_groups"], qualification["negative_control_cases"]), (2, 30, 249))
        self.assertEqual(len(qualification["receipt_bindings"]), 1)
        binding = qualification["receipt_bindings"][0]
        self.assertEqual(binding["sha256"], "E9C8A4A81AFF9C5BD9266C481C60012249228CA56E26399A6B99B5A8AF42FE24")
        encoded = json.dumps(qualification, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "35CB203F63B59344DEBC346DFF1DA8F426D4BD65BF108C9D845CAC7C56822D0A")
        self.assertFalse(qualification["production_ready"])

        boot = current["current_boot_chain_qualification"]
        self.assertEqual(boot["cycle"], 173)
        self.assertEqual((boot["fresh_qemu_runs"], boot["kernel_entry_runs"], boot["focused_python_tests"]), (6, 2, 71))
        self.assertEqual((boot["kernel_host_tests"], boot["loader_host_tests"]), (243, 328))
        self.assertEqual((boot["retained_file_count"], boot["inner_artifact_bytes"], boot["retained_bytes"]), (9, 8761, 11952))
        self.assertEqual(boot["inner_set_sha256"], "E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A")
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        for binding in boot["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        for name in ("symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"):
            check = getattr(pooleos_release_gate, "check_native_" + name + "_readiness")()
            self.assertTrue(check["ok"], check["detail"])
        self.assertFalse(boot["current_candidate_full_gate_passed"])
        self.assertFalse(boot["production_ready"])

    def test_entry_provenance_replay_is_source_bound_and_preserves_failed_audit(self) -> None:
        from runtime import native_kernel_entry as entry

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = current["current_entry_provenance_qualification"]
        raw = (ROOT / entry.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual(record["cycle"], 173)
        self.assertEqual(record["entry_receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual(entry.readiness_errors(receipt, ROOT), [])
        for field in ("linked_byte_count", "linked_sha256", "canonical_byte_count", "canonical_sha256"):
            self.assertEqual(record[field], receipt["product"][field])
        sources = {p.relative_to(ROOT).as_posix() for p in (ROOT / "native/kernel/src").rglob("*.rs")}
        inputs = receipt["bindings"]["implementation_inputs"]
        self.assertEqual((len(sources), len(inputs)), (38, 54))
        self.assertTrue(sources.issubset({item["path"] for item in inputs}))
        self.assertEqual(record["kernel_crate_rust_source_count"], len(sources))
        self.assertEqual(record["source_binding_count"], len(inputs))
        self.assertTrue(record["exact_receipt_and_product_reproduction_passed"])
        self.assertTrue(record["single_host_only"])
        self.assertFalse(record["transitive_workspace_provenance_complete"])
        self.assertFalse(record["production_ready"])
        failed = current["historical_cycle172_candidate_audit"]
        self.assertEqual((failed["status"], failed["passed_checks"], failed["total_checks"]), ("fail", 104, 105))
        self.assertEqual((failed["doctor_passed_checks"], failed["doctor_total_checks"]), (707, 708))
        self.assertEqual(failed["receipt_sha256"], "D5AF0E1BCA6C6278ED9E506DB2EBBA1E464AED74177DDC73C8EF30B977D52DD4")
        self.assertFalse(failed["applies_to_current_source"])
        self.assertFalse(failed["aggregate_suite_passed"])
        self.assertEqual(current["historical_cycle172_source_projection"]["passed_checks"], 27)
        self.assertEqual(current["current_focused_source_projection"]["passed_checks"], 22)
        self.assertFalse(current["current_candidate_audit"]["aggregate_suite_passed"])

    def test_task_stack_qualification_is_host_only_and_source_bound(self) -> None:
        from tools import qualify_native_reclamation_core as core

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        stack = current["current_task_stack_qualification"]
        self.assertEqual(stack["cycle"], 172)
        self.assertEqual(stack["contract_id"], "PKSTACK1")
        self.assertEqual(stack["scope"], "prepared_inactive_task_stack_retention_and_scrubbed_release")
        self.assertEqual(stack["receipt_path"], core.REPORT.relative_to(ROOT).as_posix())
        raw = core.REPORT.read_bytes()
        self.assertEqual(stack["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        receipt = json.loads(raw)
        core.validate_report(receipt)
        for key, receipt_key in (
            ("receipt_schema_version", "schema_version"),
            ("contract_id", "task_stack_contract_id"),
            ("page_count", "task_stack_page_count"),
            ("stack_test_methods", "task_stack_test_count"),
            ("lifetime_tests_per_host_profile", "task_lifetime_test_count"),
            ("pool_tests_per_host_profile", "focused_test_count"),
            ("kernel_tests_per_host_profile", "kernel_regression_count"),
            ("compile_fail_tests", "compile_fail_borrow_tests"),
        ):
            with self.subTest(key=key):
                self.assertEqual(stack[key], receipt[receipt_key])
                self.assertIs(type(stack[key]), type(receipt[receipt_key]))
        self.assertEqual((stack["page_count"], stack["byte_count"], stack["host_profile_count"]), (4, 16384, 2))
        self.assertEqual((stack["stack_test_methods"], stack["evidence_parser_rejection_cases"], stack["scrub_fault_cases"]), (10, 40, 7))
        self.assertEqual((stack["single_manager_scrub_receipt_capacity_tested"], stack["rejected_receipt_ordinal"]), (16, 17))
        self.assertEqual((stack["scheduler_generations_tested"], stack["fresh_manager_every_task_batch"]), (128, 8))
        self.assertEqual(stack["fresh_qemu_runs"], 0)
        self.assertTrue(stack["linked_kernel_byte_identical"])
        for key in (
            "task_stack_live_verified", "guarded_stack_mappings_verified",
            "architectural_context_activation_verified", "cross_cpu_quiescence_verified",
            "automatic_scrub_receipt_growth_integrated", "n12_3_complete", "production_ready",
        ):
            with self.subTest(key=key):
                self.assertIs(stack[key], False)
        for flag_id in ("FLAG-N12-CONCURRENCY-RECLAMATION-001", "FLAG-N36-RECEIPT-COVERAGE-001"):
            flag = next(item for item in self.roadmap["implementation_flags"] if item["id"] == flag_id)
            self.assertEqual(flag["status"], "open")
            self.assertIn("docs/checkpoints/cycle172-task-stack-ownership.md", flag["evidence"])

    def test_current_dependency_replay_binds_all_fourteen_live_receipts(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        qualification = current["current_dependency_qualification"]
        self.assertEqual(qualification["cycle"], 171)
        self.assertEqual(qualification["source_validation_cycle"], 173)
        self.assertTrue(qualification["embedded_entry_provenance_replay_pending"])
        self.assertEqual(qualification["readiness_replay_required_profiles"], ["physical_memory", "virtual_memory", "smp_ipi"])
        self.assertEqual(len(qualification["receipt_bindings"]), 14)
        self.assertEqual(len(set(qualification["qualified_profiles"])), 14)
        self.assertFalse(qualification["boot_chain_replay_pending"])
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        self.assertFalse(qualification["production_ready"])
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["superseded_initial_runs"]), (28, 4))
        self.assertEqual((qualification["negative_control_groups"], qualification["negative_control_cases"]), (660, 2126))
        self.assertEqual((qualification["memory_gate_rejection_cases"], qualification["host_identity_gate_rejection_cases"]), (20, 38))
        for profile, binding in zip(qualification["qualified_profiles"], qualification["receipt_bindings"], strict=True):
            with self.subTest(profile=profile):
                module = importlib.import_module("runtime.native_kernel_" + profile)
                self.assertEqual(binding["path"], module.READINESS_RELATIVE)
                raw = (ROOT / binding["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                receipt = json.loads(raw)
                issues = module.readiness_errors(receipt, ROOT)
                self.assertEqual(bool(issues), profile in qualification["readiness_replay_required_profiles"], issues)
                entry = receipt["kernel_summary"]["entry_readiness"] if profile == "atomics" else receipt["build"]["kernel_entry"]
                current_entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_text(encoding="utf-8"))
                self.assertNotEqual(entry["bindings"], current_entry["bindings"])
                self.assertEqual(entry["product"]["canonical_sha256"], qualification["kernel_sha256"])
                self.assertEqual((entry["host_tests"]["test_count"], entry["host_tests"]["test_pass_count"]), (243, 243))
                self.assertEqual(len(receipt["execution"]["runs"]), binding["fresh_runs"])
                for run in receipt["execution"]["runs"]:
                    self.assertEqual(run["qemu_exit_code"], 0)
                    self.assertEqual(len(run["markers"]), binding["marker_count"])
                    if "marker_summary" in run:
                        self.assertEqual(json.loads(json.dumps(module.validate_markers(run["markers"]))), run["marker_summary"])
                self.assertEqual(len(receipt["negative_controls"]), binding["negative_groups"])
                self.assertEqual(sum(c.get("case_count", 1) for c in receipt["negative_controls"]), binding["negative_cases"])
                name = "scheduler_preemption" if profile == "scheduler_preempt" else profile
                check = getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")()
                self.assertEqual(check["ok"], profile not in qualification["readiness_replay_required_profiles"], check["detail"])
        previous = current["historical_cycle170_source_projection"]
        encoded = json.dumps(previous, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "8CA7E27C2F2631C173FF285A144499299705731773D17F609DE4CF520A487EA2")

    def test_cpu_qualification_is_bound_to_five_live_receipts(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        historical = current["historical_cycle164_cpu_qualification"]
        encoded = json.dumps(historical, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "9F2C995FE12537F9405D2502916E81229F0221C46457FF859BD53094FF757ABA")
        self.assertEqual(historical["cycle"], 164)
        expected_paths = {
            f"runs/native-kernel-{profile}-readiness.json"
            for profile in ("trap", "cpu-policy", "xstate-policy", "xstate-exception", "privilege-msr-policy")
        }
        bindings = historical["receipt_bindings"]
        self.assertEqual(len(bindings), 5)
        self.assertEqual({b["path"] for b in bindings}, expected_paths)
        self.assertTrue(all(re.fullmatch("[0-9A-F]{64}", b["sha256"]) for b in bindings))
        self.assertEqual((historical["fresh_qemu_runs"], historical["negative_control_groups"]), (14, 225))
        self.assertEqual(historical["whpx_exception_runs"], 2)
        self.assertEqual(historical["expected_tcg_limitation_probes"], 1)
        self.assertFalse(historical["production_ready"])
        self.assertFalse(current["current_cycle_full_canonical_audit_performed"])
        self.assertEqual(current["current_focused_source_projection"]["pending_downstream_native_checks"], 5)
        qualification = current["current_cpu_qualification"]
        self.assertEqual(qualification["cycle"], 170)
        self.assertEqual(qualification["source_validation_cycle"], 173)
        self.assertTrue(qualification["embedded_entry_provenance_replay_pending"])
        self.assertEqual(qualification["readiness_replay_required_profiles"], ["cpu_policy", "privilege_msr_policy"])
        self.assertEqual(qualification["kernel_sha256"], current["current_boot_chain_qualification"]["kernel_sha256"])
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["negative_control_groups"]), (14, 225))
        self.assertEqual((qualification["focused_python_tests"], qualification["aggregate_gate_regression_cases"]), (42, 17))
        self.assertEqual(qualification["kernel_host_tests_per_qualifier"], 243)
        self.assertEqual(qualification["whpx_exception_runs"], 2)
        self.assertEqual(qualification["expected_tcg_limitation_probes"], 1)
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        self.assertFalse(qualification["production_ready"])
        self.assertEqual({b["path"] for b in qualification["receipt_bindings"]}, expected_paths)
        self.assertEqual(len(qualification["receipt_bindings"]), 5)
        runs = controls = 0
        from tools import pooleos_release_gate as gate

        for binding in qualification["receipt_bindings"]:
            data = (ROOT / binding["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(data)
            self.assertEqual(receipt["build"]["kernel_entry"]["product"]["canonical_sha256"], qualification["kernel_sha256"])
            self.assertEqual(receipt["build"]["kernel_entry"]["summary"]["rust_host_tests_total"], 243)
            runs += receipt["summary"]["qemu_run_count"]
            controls += receipt["summary"]["negative_controls_passed"]
            profile = binding["path"].removeprefix("runs/native-kernel-").removesuffix("-readiness.json").replace("-", "_")
            check = getattr(gate, "check_native_kernel_" + profile + "_readiness")()
            self.assertEqual(check["ok"], profile not in qualification["readiness_replay_required_profiles"], check["detail"])
            current_entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_text(encoding="utf-8"))
            self.assertNotEqual(receipt["build"]["kernel_entry"]["bindings"], current_entry["bindings"])
            if profile == "xstate_exception":
                self.assertEqual(receipt["execution"]["acceleration"], "whpx_hardware_accelerated")
                self.assertEqual(receipt["execution"]["tcg_limitation_probe"]["run_count"], 1)
                self.assertFalse(receipt["execution"]["tcg_limitation_probe"]["vector_19_delivered"])
                self.assertEqual(receipt["summary"]["exception_deliveries"], qualification["exception_deliveries_per_run"])
                self.assertEqual(receipt["summary"]["recovered_returns"], qualification["exception_recoveries_per_run"])
                self.assertTrue(receipt["summary"]["machine_code_audit_passed"])
        self.assertEqual((runs, controls), (14, 225))

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
        self.assertEqual(protocol["selected_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        self.assertIn("docs/checkpoints/cycle172-task-stack-ownership.md", protocol["required_records"])
        self.assertEqual(
            protocol["owner_independent_next_move_id"],
            "N7-TRAP-001",
        )
        self.assertIn("runs/hardware_target_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_tier0_readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-atomics-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-locks-readiness.json", protocol["required_records"])
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
        self.assertIn("runs/native-kernel-smp-first-ap-readiness.json", protocol["required_records"])
        self.assertIn(
            "runs/native-kernel-smp-percpu-runtime-readiness.json",
            protocol["required_records"],
        )
        self.assertIn(
            "runs/native-kernel-smp-ipi-readiness.json",
            protocol["required_records"],
        )
        self.assertIn(
            "runs/native-kernel-scheduler-readiness.json",
            protocol["required_records"],
        )
        self.assertIn(
            "runs/native-kernel-scheduler-preemption-readiness.json",
            protocol["required_records"],
        )
        self.assertIn(
            "runs/native-kernel-scheduler-smp-readiness.json",
            protocol["required_records"],
        )
        self.assertIn(
            "runs/native-kernel-scheduler-ap-workers-readiness.json",
            protocol["required_records"],
        )
        self.assertIn("runs/native-kernel-errata-policy-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-xstate-policy-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-xstate-exception-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-privilege-msr-policy-readiness.json", protocol["required_records"])
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", protocol["required_records"])
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
        self.assertEqual(len(flags), 94)
        self.assertEqual(len({flag["id"] for flag in flags}), 94)
        receipt_flag = next(flag for flag in flags if flag["id"] == "FLAG-N36-RECEIPT-COVERAGE-001")
        self.assertEqual(receipt_flag["phase_id"], "N36")
        self.assertEqual(receipt_flag["status"], "open")
        self.assertIn("runtime/native_kernel_trap.py", receipt_flag["evidence"])
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
        pmm_flag = next(flag for flag in flags if flag["id"] == "FLAG-N9-PMM-FOUNDATION-001")
        self.assertEqual(pmm_flag["class"], "REQUIRED")
        self.assertEqual(pmm_flag["status"], "closed")
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", pmm_flag["evidence"])
        scrub_flag = next(flag for flag in flags if flag["id"] == "FLAG-N9-PMM-SCRUB-001")
        self.assertEqual(scrub_flag["class"], "REQUIRED")
        self.assertEqual(scrub_flag["status"], "closed")
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", scrub_flag["evidence"])
        metadata_flag = next(flag for flag in flags if flag["id"] == "FLAG-N9-PMM-METADATA-001")
        self.assertEqual(metadata_flag["class"], "REQUIRED")
        self.assertEqual(metadata_flag["status"], "closed")
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", metadata_flag["evidence"])
        reclaim_flag = next(flag for flag in flags if flag["id"] == "FLAG-N9-PMM-RECLAIM-001")
        self.assertEqual(reclaim_flag["class"], "REQUIRED")
        self.assertEqual(reclaim_flag["status"], "closed")
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", reclaim_flag["evidence"])
        growth_flag = next(flag for flag in flags if flag["id"] == "FLAG-N9-PMM-GROWTH-001")
        self.assertEqual(growth_flag["class"], "REQUIRED")
        self.assertEqual(growth_flag["status"], "closed")
        self.assertIn("runs/native-kernel-physical-memory-readiness.json", growth_flag["evidence"])
        growth_automation_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N9-PMM-GROWTH-AUTOMATION-001"
        )
        self.assertEqual(growth_automation_flag["class"], "REQUIRED")
        self.assertEqual(growth_automation_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-physical-memory-readiness.json",
            growth_automation_flag["evidence"],
        )
        acpi_consumer_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N9-PMM-ACPI-CONSUMER-001"
        )
        self.assertEqual(acpi_consumer_flag["class"], "REQUIRED")
        self.assertEqual(acpi_consumer_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-physical-memory-readiness.json",
            acpi_consumer_flag["evidence"],
        )
        self.assertIn("native/kernel/src/acpi.rs", acpi_consumer_flag["evidence"])
        direct_map_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N9-VM-DIRECT-MAP-001"
        )
        self.assertEqual(direct_map_flag["class"], "REQUIRED")
        self.assertEqual(direct_map_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-virtual-memory-readiness.json",
            direct_map_flag["evidence"],
        )
        irq_flag = next(flag for flag in flags if flag["id"] == "FLAG-N8-IRQ-001")
        self.assertEqual(irq_flag["class"], "REQUIRED")
        self.assertEqual(irq_flag["status"], "open")
        self.assertIn("docs/pdc-production-build-plan.md", irq_flag["evidence"])
        self.assertIn("runs/native-kernel-interrupt-time-readiness.json", irq_flag["evidence"])
        smp_flag = next(flag for flag in flags if flag["id"] == "FLAG-N8-SMP-FIRST-AP-001")
        self.assertEqual(smp_flag["class"], "REQUIRED")
        self.assertEqual(smp_flag["status"], "closed")
        self.assertIn("runs/native-kernel-smp-first-ap-readiness.json", smp_flag["evidence"])
        percpu_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N8-SMP-PERCPU-RUNTIME-001"
        )
        self.assertEqual(percpu_flag["class"], "REQUIRED")
        self.assertEqual(percpu_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-smp-percpu-runtime-readiness.json",
            percpu_flag["evidence"],
        )
        ipi_flag = next(flag for flag in flags if flag["id"] == "FLAG-N8-SMP-IPI-001")
        self.assertEqual(ipi_flag["class"], "REQUIRED")
        self.assertEqual(ipi_flag["status"], "closed")
        self.assertIn("runs/native-kernel-smp-ipi-readiness.json", ipi_flag["evidence"])
        shootdown_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N9-SMP-SHOOTDOWN-001"
        )
        self.assertEqual(shootdown_flag["class"], "REQUIRED")
        self.assertEqual(shootdown_flag["status"], "closed")
        self.assertIn("runs/native-kernel-smp-ipi-readiness.json", shootdown_flag["evidence"])
        multi_ap_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N8-SMP-MULTI-AP-001"
        )
        self.assertEqual(multi_ap_flag["class"], "REQUIRED")
        self.assertEqual(multi_ap_flag["status"], "closed")
        self.assertIn("runs/native-kernel-smp-ipi-readiness.json", multi_ap_flag["evidence"])
        scheduler_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-FOUNDATION-001"
        )
        self.assertEqual(scheduler_flag["class"], "REQUIRED")
        self.assertEqual(scheduler_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-scheduler-readiness.json", scheduler_flag["evidence"]
        )
        preemption_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-PREEMPT-001"
        )
        self.assertEqual(preemption_flag["class"], "REQUIRED")
        self.assertEqual(preemption_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-scheduler-preemption-readiness.json",
            preemption_flag["evidence"],
        )
        deferred_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-DEFERRED-001"
        )
        self.assertEqual(deferred_flag["class"], "REQUIRED")
        self.assertEqual(deferred_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-scheduler-deferred-readiness.json",
            deferred_flag["evidence"],
        )
        smp_scheduler_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-SMP-001"
        )
        self.assertEqual(smp_scheduler_flag["class"], "REQUIRED")
        self.assertEqual(smp_scheduler_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-scheduler-smp-readiness.json",
            smp_scheduler_flag["evidence"],
        )
        ap_workers_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-AP-WORKERS-001"
        )
        self.assertEqual(ap_workers_flag["class"], "REQUIRED")
        self.assertEqual(ap_workers_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-scheduler-ap-workers-readiness.json",
            ap_workers_flag["evidence"],
        )
        smp_preemption_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-SMP-PREEMPT-001"
        )
        self.assertEqual(smp_preemption_flag["class"], "REQUIRED")
        self.assertEqual(smp_preemption_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-scheduler-smp-preempt-readiness.json",
            smp_preemption_flag["evidence"],
        )
        atomics_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-CONCURRENCY-ATOMICS-001"
        )
        self.assertEqual(atomics_flag["class"], "REQUIRED")
        self.assertEqual(atomics_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-atomics-readiness.json", atomics_flag["evidence"]
        )
        locks_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-CONCURRENCY-LOCKS-001"
        )
        self.assertEqual(locks_flag["class"], "REQUIRED")
        self.assertEqual(locks_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-locks-readiness.json", locks_flag["evidence"]
        )
        reclamation_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-CONCURRENCY-RECLAMATION-001"
        )
        self.assertEqual(reclamation_flag["class"], "REQUIRED")
        self.assertEqual(reclamation_flag["status"], "open")
        self.assertIn("runs/native-kernel-reclamation-core-readiness.json", reclamation_flag["evidence"])
        self.assertFalse(self.roadmap["production_ready"])
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
        xstate_exception_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N7-XSTATE-EXCEPTION-001"
        )
        self.assertEqual(xstate_exception_flag["class"], "REQUIRED")
        self.assertEqual(xstate_exception_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-xstate-exception-readiness.json",
            xstate_exception_flag["evidence"],
        )
        privilege_msr_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N7-PRIVILEGE-MSR-POLICY-001"
        )
        self.assertEqual(privilege_msr_flag["class"], "REQUIRED")
        self.assertEqual(privilege_msr_flag["status"], "closed")
        self.assertIn(
            "runs/native-kernel-privilege-msr-policy-readiness.json",
            privilege_msr_flag["evidence"],
        )
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
        self.assertEqual(n7_statuses["N7.4"], "partial")
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
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-xstate-policy-readiness.json:")
                for item in n7["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-xstate-exception-readiness.json:")
                for item in n7["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-privilege-msr-policy-readiness.json:")
                for item in n7["current_evidence"]
            )
        )
        self.assertIn("ADD-N7-ERRATA-SOURCE-001", n7["added_requirement_ids"])
        self.assertIn("ADD-N7-XSTATE-001", n7["added_requirement_ids"])
        self.assertTrue(any("Models 40h-4Fh" in item for item in n7["current_gaps"]))

        n8 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N8")
        self.assertEqual(n8["status"], "partial")
        n8_statuses = {subphase["id"]: subphase["status"] for subphase in n8["subphases"]}
        for subphase_id in ("N8.1", "N8.3", "N8.5"):
            self.assertEqual(n8_statuses[subphase_id], "partial")
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-smp-first-ap-readiness.json:")
                for item in n8["current_evidence"]
            )
        )

        n9 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N9")
        self.assertEqual(n9["status"], "partial")
        n9_statuses = {subphase["id"]: subphase["status"] for subphase in n9["subphases"]}
        self.assertEqual(n9_statuses["N9.1"], "partial")
        self.assertEqual(n9_statuses["N9.2"], "partial")
        self.assertEqual(n9_statuses["N9.3"], "partial")
        self.assertEqual(n9_statuses["N9.4"], "partial")
        for subphase_id in ("N9.5", "N9.6", "N9.7"):
            self.assertEqual(n9_statuses[subphase_id], "not_started")
        self.assertIn("ADD-MEM-001", n9["added_requirement_ids"])
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-physical-memory-readiness.json:")
                for item in n9["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-virtual-memory-readiness.json:")
                for item in n9["current_evidence"]
            )
        )

        n12 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N12")
        self.assertEqual(n12["status"], "partial")
        n12_statuses = {
            subphase["id"]: subphase["status"] for subphase in n12["subphases"]
        }
        self.assertEqual(n12_statuses["N12.1"], "complete")
        self.assertEqual(n12_statuses["N12.2"], "complete")
        for subphase_id in (
            "N12.3",
            "N12.4",
            "N12.5",
            "N12.6",
            "N12.7",
        ):
            self.assertEqual(n12_statuses[subphase_id], "partial")
        for subphase_id in ("N12.8",):
            self.assertEqual(n12_statuses[subphase_id], "not_started")
        self.assertIn("ADD-N12-SCHED-FOUNDATION-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-SCHED-PREEMPT-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-SCHED-DEFERRED-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-SCHED-SMP-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-SCHED-AP-WORKERS-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-SCHED-SMP-PREEMPT-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-CONCURRENCY-ATOMICS-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-CONCURRENCY-LOCKS-001", n12["added_requirement_ids"])
        self.assertIn("ADD-N12-CONCURRENCY-RECLAMATION-001", n12["added_requirement_ids"])
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-scheduler-readiness.json:")
                for item in n12["current_evidence"]
            )
        )
        self.assertTrue(any("AP-local timer interrupt delivery" in item for item in n12["current_gaps"]))
        self.assertTrue(any("deferred reclamation and ABA-safe" in item for item in n12["current_gaps"]))
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-atomics-readiness.json:")
                for item in n12["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-locks-readiness.json:")
                for item in n12["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith(
                    "runs/native-kernel-scheduler-preemption-readiness.json:"
                )
                for item in n12["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith(
                    "runs/native-kernel-scheduler-deferred-readiness.json:"
                )
                for item in n12["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-scheduler-smp-readiness.json:")
                for item in n12["current_evidence"]
            )
        )
        self.assertTrue(
            any(
                item.startswith("runs/native-kernel-scheduler-ap-workers-readiness.json:")
                for item in n12["current_evidence"]
            )
        )

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
