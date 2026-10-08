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
        frozen = (ROOT / "tests/fixtures/cycle229-execution-sources.json").read_bytes()
        if hashlib.sha256(frozen).hexdigest().upper() != "9C64EC020BD4D98182DAB38EF65EA7ABBFC15EC3EFD98BA188D6E005C2AE5295":
            raise AssertionError("historical execution ledger changed")
        cls.historical_receipts = {r["receipt"]["path"]: r["receipt"]["sha256"]
                                   for r in json.loads(frozen)["profiles"]}
        cls.current_receipts = {r["receipt"]["path"]: r["receipt"]["sha256"]
                                for r in json.loads((ROOT / "runs/native_execution_sources.json").read_bytes())["profiles"]}

    def assert_replayed_receipt_binding(self, binding: dict, raw: bytes) -> None:
        # The frozen ledger checks history; the current ledger checks the replayed bytes.
        self.assertEqual(binding["sha256"], self.historical_receipts[binding["path"]])
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), self.current_receipts[binding["path"]])

    def assert_current_gate_projection(self, check: dict) -> None:
        # Historical receipt integrity does not establish current-image readiness.
        projection = self.roadmap["baseline"]["native_consistency_release_gate"]["current_focused_source_projection"]
        unchanged_prerequisites = {"native_firmware_readiness"}
        self.assertEqual(check["ok"], check["name"] in set(projection["passing_profiles"]) | unchanged_prerequisites, check["detail"])

    def assert_retained_receipt_admission(self, module, receipt: dict) -> None:
        # Preserve exact receipt bytes; admission is separately tied to current source.
        path = Path(module.READINESS_RELATIVE).as_posix()
        raw = (ROOT / path).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), self.current_receipts[path])
        self.assertEqual(receipt, json.loads(raw))
        name = Path(path).stem.replace("-", "_")
        recorded = json.loads((ROOT / "runs/native-user-entry-gate-projection.json").read_bytes())
        expected = next(c for c in recorded["checks"] if c["name"] == name)
        check = getattr(pooleos_release_gate, "check_" + name)()
        self.assertEqual(check, expected)
        self.assert_current_gate_projection(check)
        errors = module.readiness_errors(receipt, ROOT)
        if check["ok"]:
            self.assertEqual(errors, [])
        else:
            self.assertTrue(errors)
            self.assertEqual("; ".join(errors), expected["detail"])

    def assert_reclamation_admission(self, receipt: dict) -> None:
        from tools import qualify_native_reclamation_core as core
        raw = core.REPORT.read_bytes()
        binding = self.roadmap["baseline"]["native_consistency_release_gate"]["current_execution_qualification"]
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["receipt_sha256"])
        self.assertEqual(receipt, json.loads(raw))
        if receipt["sources"] == core.bind_sources(ROOT):
            core.validate_report(receipt)
        else:
            with self.assertRaisesRegex(ValueError, "^reclamation source binding is stale$"):
                core.validate_report(receipt)

    def test_roadmap_matches_schema(self) -> None:
        self.assertEqual(validate_json(self.roadmap, self.schema), [])

    def test_generation_is_repeatable_without_mutating_prior_results(self) -> None:
        from tools.generate_native_production_roadmap import make_roadmap

        count = self.roadmap["baseline"]["pooleos_test_count"]
        date = self.roadmap["status_date"]
        first = make_roadmap(count, date)
        frozen = json.dumps(first, sort_keys=True)
        second = make_roadmap(count, date)
        self.assertEqual(json.dumps(first, sort_keys=True), frozen)
        self.assertEqual(json.dumps(second, sort_keys=True), frozen)

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
        self.assertEqual(checklist["added_requirement_count"], 59)

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
        self.assertEqual(self.roadmap["baseline"]["pooleos_cycle"], 249)
        self.assertEqual(self.roadmap["baseline"]["pooleos_test_count"], 1292)
        n36 = next(phase for phase in self.roadmap["phases"] if phase["id"] == "N36")
        self.assertIn("Cycle 173 source inventory: 950 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 174 source inventory: 954 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 175 source inventory: 958 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 182 source inventory: 981 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 183 source inventory: 986 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 184 source inventory: 994 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 185 source inventory: 998 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 186 source inventory: 1002 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 187 source inventory: 1006 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 188 source inventory: 1011 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 189 source inventory: 1016 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 190 source inventory: 1021 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 191 source inventory: 1028 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 192 source inventory: 1041 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 193 source inventory: 1042 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 194 source inventory: 1044 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 195 source inventory: 1050 Python tests discovered; full qualification pending", n36["current_evidence"])
        self.assertIn("Cycle 196 source inventory: 1060 Python tests discovered; full qualification pending", n36["current_evidence"])
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
        self.assertEqual(current["qualification_status"], "bounded_unknown_runtime_pass_capability_IPC_and_full_candidate_pending")
        self.assertEqual(current["current_candidate_audit"]["cycle"], 249)
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
        self.assertEqual(current["passed_check_count_scope"], "historical_cycle176_exact_final_canonical_audit")
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
        self.assertEqual(current["last_fully_qualified_cycle"], 176)
        self.assertEqual(current["last_fully_qualified_passed_checks"], 105)
        replay = current["historical_cycle176_canonical_replay"]
        self.assertEqual((replay["passed_checks"], replay["doctor_passed_checks"], replay["pooleos_test_count"]), (105, 708, 958))
        self.assertEqual(replay["tracked_file_count"], 1535)
        self.assertTrue(replay["include_runtime"])
        self.assertTrue(replay["both_bundle_and_replay_inputs_supplied"])
        self.assertFalse(replay["applies_to_current_source"])
        self.assertFalse(replay["production_ready"])
        self.assertEqual(replay["final_receipt_sha256"], "57C7C95D0EA982FB16763C8440A24103E5C6E0F21C133C56E6EEDC9AA7A4AA0A")
        self.assertEqual(replay["execution_receipt_sha256"], "1368149CCC695ACDEE91AD662430C497B929BAA66CBE414DCCE43A5AEF70CD6F")
        self.assertEqual(replay["merged_main_commit"], "ac15d1da5304eab19ae3ed098d26cdcadfa78156")
        self.assertEqual(replay["merged_tree"], "1bce3ce5317a9202e80f4df482ce0b4766093d44")
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
        focused = current["historical_cycle185_source_projection"]
        self.assertEqual(focused["cycle"], 185)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (13, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 14)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 14)
        self.assertEqual(focused["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        self.assertEqual((focused["kernel_entry_runs"], focused["superseded_initial_qemu_runs"]), (14, 6))
        self.assertEqual(focused["focused_python_tests_passed"], 50)
        self.assertEqual(current["historical_cycle184_source_projection"]["passed_checks"], 8)
        self.assertEqual(current["historical_cycle183_source_projection"]["passed_checks"], 3)
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle181_source_projection"]
        self.assertEqual(focused["cycle"], 181)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (27, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 0)
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["superseded_initial_runs"]), (28, 4))
        self.assertEqual(focused["failed_pre_guest_attempts"], 1)
        self.assertEqual((focused["negative_control_groups"], focused["negative_control_cases"]), (660, 2126))
        self.assertTrue(focused["reported_case_count_is_not_executed_rejection_count"])
        self.assertEqual(focused["unproven_per_control_rejection_groups_at_least"], 65)
        self.assertEqual((focused["aggregate_gate_regression_cases"], focused["source_audit_rejection_cases"]), (79, 4))
        self.assertEqual((focused["focused_python_tests"], focused["focused_python_passed"], focused["focused_python_skipped"]), (166, 164, 2))
        self.assertEqual(focused["focused_test_log_sha256"], "F3433D8B55D3FDF95A7B3C75633657CFDB1A4C9FD7E2748A9CC153860FFCE915")
        self.assertEqual(focused["next_dependency_move_id"], "N6-KENTRY-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle180_source_projection"]
        self.assertEqual(focused["cycle"], 180)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (13, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 14)
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["expected_tcg_limitation_probes"]), (14, 1))
        self.assertEqual((focused["negative_control_groups"], focused["aggregate_gate_regression_cases"]), (225, 19))
        self.assertEqual(focused["focused_python_tests_passed"], 46)
        self.assertEqual(focused["focused_test_log_sha256"], "5F0968C7EA5288C3E189D04E06EEB246951C6AF40EB59C89307EC3301B92754D")
        self.assertEqual(focused["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle179_source_projection"]
        self.assertEqual(focused["cycle"], 179)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (8, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 19)
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["superseded_initial_qemu_runs"]), (6, 2))
        self.assertEqual(focused["kernel_entry_runs"], 2)
        self.assertEqual(focused["focused_python_tests_passed"], 71)
        self.assertEqual(focused["focused_test_log_sha256"], "BF2D89D92750BF5192042F8719DAD48F9DE94C28864269E6441A5F4C685212EE")
        self.assertEqual(focused["boot_identity_rejection_cases"], 13)
        self.assertEqual(focused["qualifier_admission_rejection_cases"], 3)
        self.assertEqual(focused["next_dependency_move_id"], "N7-TRAP-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle178_source_projection"]
        self.assertEqual(focused["cycle"], 178)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (3, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 24)
        self.assertEqual(focused["entry_kernel_host_tests"], 245)
        self.assertEqual(focused["entry_source_binding_count"], 55)
        self.assertEqual(focused["entry_release_gate_controls"], 12)
        self.assertEqual(focused["focused_python_tests_passed"], 57)
        self.assertEqual(focused["focused_test_log_sha256"], "4AC7C41FDFE2CF79F96A1BB6E25C6313D84A65DC620BA62BF4B737256142D009")
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 0)
        self.assertEqual(focused["next_dependency_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle177_source_projection"]
        self.assertEqual(focused["cycle"], 177)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (2, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 25)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 0)
        self.assertIsNone(focused["revalidated_dependency_execution_cycle"])
        self.assertEqual((focused["lifetime_tests_per_host_profile"], focused["compile_fail_tests"]), (40, 15))
        self.assertEqual(focused["next_dependency_move_id"], "N6-KENTRY-001")
        self.assertEqual(focused["reconciliation_python_tests_passed"], 37)
        self.assertEqual((focused["expanded_python_test_methods"], focused["expanded_python_passed_methods"],
                          focused["expanded_python_failed_methods"], focused["expanded_python_failure_reports"]), (60, 55, 5, 9))
        self.assertFalse(focused["expanded_python_suite_passed"])
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        focused = current["historical_cycle175_source_projection"]
        self.assertEqual(focused["cycle"], 175)
        self.assertEqual((focused["passed_checks"], focused["total_checks"]), (27, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 0)
        self.assertEqual(focused["final_receipt_fresh_qemu_runs"], 28)
        self.assertEqual(focused["superseded_initial_runs"], 2)
        self.assertEqual((focused["focused_python_tests"], focused["focused_python_passed"], focused["focused_python_skipped"]), (163, 161, 2))
        self.assertTrue(focused["passing_selected_checks_do_not_requalify_old_embedded_entry_evidence"])
        self.assertEqual(focused["revalidated_dependency_execution_cycle"], 175)
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
        ownership = current["historical_cycle175_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 175)
        self.assertEqual(ownership["host_qualification_cycle"], 172)
        self.assertEqual(ownership["fresh_current_cycle_qemu_runs"], 2)
        self.assertEqual((ownership["lifetime_tests_per_host_profile"], ownership["compile_fail_tests"]), (34, 11))
        self.assertFalse(ownership["task_stack_live_integration_verified"])
        self.assertEqual(ownership["live_replay_cycle"], 175)
        self.assertTrue(ownership["live_receipt_source_current"])
        self.assertEqual(ownership["source_current_scope"], "declared_inputs_current_boot_artifact_set_and_transfer_dependency")
        self.assertFalse(ownership["current_boot_artifact_set_replay_pending"])
        self.assertTrue(ownership["active_root_current_image_replay_complete"])
        self.assertFalse(ownership["general_task_CPU_retirement_integration_verified"])
        self.assertFalse(ownership["current_candidate_full_gate_passed"])
        self.assertEqual(ownership["smp_receipt_sha256"], "33AC859F22E4D973B44B69C33C1F135FDC281DDDC7AB14833157BCC0616AC93F")
        self.assertEqual(ownership["entry_receipt_sha256"], "9998F12E922201BA60C46521444BD1AD6CB641A0172B36F4A3552DCF66434A0B")
        self.assertEqual(ownership["reclamation_receipt_sha256"], "AFD1ABBE7EB217A132C0D9596004EC20AB2910CC23AEBD64D52E55EE645EF1D5")
        self.assertFalse(current["historical_cycle190_ownership_qualification"]["live_receipt_source_current"])
        self.assertTrue(current["historical_cycle190_ownership_qualification"]["current_boot_artifact_set_replay_pending"])
        ownership = current["historical_cycle181_ownership_qualification"]
        self.assertEqual((ownership["cycle"], ownership["host_qualification_cycle"]), (181, 177))
        self.assertEqual((ownership["kernel_tests_per_host_profile"], ownership["lifetime_tests_per_host_profile"], ownership["compile_fail_tests"]), (245, 40, 15))
        self.assertEqual(ownership["fresh_current_cycle_qemu_runs"], 4)
        self.assertEqual(ownership["live_replay_cycle"], 181)
        self.assertFalse(ownership["current_boot_artifact_set_replay_pending"])
        for key in ("live_receipt_source_current", "active_root_current_image_replay_complete",
                    "ap_runtime_live_integration_verified"):
            self.assertIs(ownership[key], True)
        for key in ("task_stack_live_integration_verified",
                    "general_task_CPU_retirement_integration_verified", "current_candidate_full_gate_passed"):
            self.assertIs(ownership[key], False)
        for key, path in (
            ("virtual_memory_receipt_sha256", "runs/native-kernel-virtual-memory-readiness.json"),
            ("smp_receipt_sha256", "runs/native-kernel-smp-ipi-readiness.json"),
        ):
            if key == "virtual_memory_receipt_sha256":
                self.assertEqual(ownership[key], "4AFEA30E25DB4DCD0D9038E01D3FE1CC6EE5D82DBAB4595A4631D34902460BB7")
                self.assertNotEqual(ownership[key], hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper())
                continue
            self.assertEqual(ownership[key], "2B1F8D623D31476F2C8886DFD583BE9514C68A2B3D0DA36BC75DDD13D6823CCA")
            self.assertNotEqual(ownership[key], hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper())
        self.assertEqual(ownership["entry_receipt_sha256"], current["historical_cycle181_entry_provenance_qualification"]["entry_receipt_sha256"])
        self.assertEqual(ownership["reclamation_receipt_sha256"], current["historical_cycle191_execution_qualification"]["receipt_sha256"])
        self.assertNotEqual(ownership["reclamation_receipt_sha256"], hashlib.sha256(
            (ROOT / "runs/native-kernel-reclamation-core-readiness.json").read_bytes()).hexdigest().upper())
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
        self.assertEqual(self.roadmap["immediate_next_move"]["id"], "N13-CAPABILITY-IPC-001")
        self.assertFalse(self.roadmap["immediate_next_move"]["blocked"])
        blocker = self.roadmap["baseline"]["retained_production_owner_blocker"]
        self.assertEqual(blocker["id"], "N0-GOVERNANCE-CUSTODY-001")
        self.assertTrue(blocker["blocked"])

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

        boot = current["historical_cycle175_boot_chain_qualification"]
        self.assertEqual(boot["cycle"], 173)
        self.assertEqual((boot["fresh_qemu_runs"], boot["kernel_entry_runs"], boot["focused_python_tests"]), (6, 2, 71))
        self.assertEqual((boot["kernel_host_tests"], boot["loader_host_tests"]), (243, 328))
        self.assertEqual((boot["retained_file_count"], boot["inner_artifact_bytes"], boot["retained_bytes"]), (9, 8761, 11952))
        self.assertEqual(boot["inner_set_sha256"], "E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A")
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        encoded = json.dumps(boot, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "5B7D09973A51BBA363C6498F538321AD6DE6FEE90FC8EB09C38D9787D80AEC64")
        self.assertFalse(boot["current_candidate_full_gate_passed"])
        self.assertFalse(boot["production_ready"])
        self.assertFalse(current["current_boot_chain_qualification"]["applies_to_current_source"])
        boot = current["historical_cycle181_boot_chain_qualification"]
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (179, 181))
        self.assertEqual(boot["status"], "single_host_replay_pass")
        self.assertTrue(boot["applies_to_current_source"])
        self.assertEqual((boot["fresh_qemu_runs"], boot["superseded_initial_runs"], boot["kernel_entry_runs"]), (6, 2, 2))
        self.assertEqual((boot["kernel_host_tests"], boot["loader_host_tests"], boot["focused_python_tests"]), (245, 330, 71))
        self.assertEqual((boot["retained_file_count"], boot["inner_artifact_bytes"], boot["retained_bytes"]), (9, 8761, 11952))
        self.assertEqual(boot["inner_set_sha256"], "A3078488088B2BF11B8D88F48862FA8D80957D610EB1F3FF4411AD5E4729FEAF")
        self.assertEqual((boot["boot_identity_rejection_cases"], boot["qualifier_admission_rejection_cases"]), (13, 3))
        self.assertTrue(boot["receipt_generation_semantically_validated"])
        self.assertTrue(boot["receipt_write_semantically_validated"])
        self.assertEqual(boot["readiness_replay_required_profiles"], [])
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        self.assertEqual(sum(b["fresh_runs"] for b in boot["receipt_bindings"]), 6)
        self.assertEqual({b["profile"] for b in boot["receipt_bindings"]}, set(boot["qualified_profiles"]))
        boot = current["historical_cycle191_boot_chain_qualification"]
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (184, 185))
        self.assertEqual((boot["fresh_qemu_runs"], boot["superseded_initial_runs"], boot["kernel_entry_runs"]), (6, 8, 2))
        self.assertEqual((boot["kernel_host_tests"], boot["loader_host_tests"], boot["pooleboot_host_tests"]), (245, 330, 8))
        self.assertEqual((boot["focused_python_tests"], boot["focused_python_passed"], boot["focused_python_skipped"]), (109, 109, 0))
        self.assertEqual((boot["host_pinned_qualifier_count"], boot["host_profile_rejection_cases"],
                          boot["host_input_binding_mutation_cases"], boot["symbol_policy_invalid_output_cases"],
                          boot["forged_PooleBoot_host_test_count_rejections"]), (6, 66, 36, 8, 12))
        self.assertEqual(boot["preserved_failed_runner_attempts"], 13)
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        self.assertEqual(len(boot["prerequisite_receipt_bindings"]), 2)
        self.assertEqual({b["profile"] for b in boot["receipt_bindings"]}, set(boot["qualified_profiles"]))
        self.assertFalse(boot["n5_exit_gate_satisfied"])
        self.assertFalse(boot["complete_host_attestation"])
        self.assertFalse(boot["second_builder_reproduced"])
        self.assertFalse(current["historical_cycle183_boot_chain_qualification"]["applies_to_current_source"])
        boot = current["historical_cycle196_boot_chain_qualification"]
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (192, 192))
        self.assertEqual((boot["fresh_qemu_runs"], boot["kernel_entry_runs"]), (6, 2))
        self.assertEqual((boot["kernel_host_tests"], boot["loader_host_tests"], boot["pooleboot_host_tests"]), (246, 331, 8))
        self.assertEqual((boot["retained_bytes"], boot["manifest_bytes"]), (11952, 2615))
        self.assertTrue(boot["real_image_trust_independently_reconstructed"])
        self.assertFalse(boot["golden_fixture_is_actual_kernel"])
        actual_boot = json.loads((ROOT / "runs/native_pooleboot_readiness.json").read_bytes())
        for field in ("trust_policy_sha256", "trust_state_sha256"):
            self.assertNotEqual(boot[field], actual_boot["summary"][field])
        self.assertNotEqual(boot["inner_set_sha256"], actual_boot["summary"]["inner_set_retained_set_sha256"])
        self.assertFalse(boot["n5_exit_gate_satisfied"])
        self.assertFalse(boot["second_builder_reproduced"])
        total_runs = 0
        for binding in boot["receipt_bindings"] + boot["prerequisite_receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            if binding in boot["receipt_bindings"]:
                self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            else:
                self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            runs = receipt.get("execution", {}).get("runs", [])
            self.assertEqual(binding["fresh_runs"], len(runs))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in runs))
            total_runs += len(runs)
        self.assertEqual(total_runs, boot["fresh_qemu_runs"])
        for name in ("symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer", "firmware", "boot_trust"):
            check = getattr(pooleos_release_gate, "check_native_" + name + "_readiness")()
            self.assert_current_gate_projection(check)
        self.assertFalse(boot["current_candidate_full_gate_passed"])
        self.assertFalse(boot["production_ready"])

    def test_entry_provenance_replay_is_source_bound_and_preserves_failed_audit(self) -> None:
        from runtime import native_kernel_entry as entry

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = current["historical_cycle233_entry_provenance_qualification"]
        self.assertFalse(current["current_entry_provenance_qualification"]["applies_to_current_source"])
        raw = (ROOT / entry.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual(record["cycle"], 216)
        self.assertEqual(record["source_validation_cycle"], 216)
        self.assertEqual(record["entry_receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assert_retained_receipt_admission(entry, receipt)
        embedded_entry = json.loads((ROOT / "runs/native-kernel-smp-ipi-readiness.json").read_bytes())["build"]["kernel_entry"]
        self.assertEqual(json.dumps(embedded_entry, sort_keys=True, allow_nan=False), json.dumps(receipt, sort_keys=True, allow_nan=False))
        self.assert_retained_receipt_admission(entry, embedded_entry)
        for profile in ("scheduler-smp", "scheduler-ap-workers", "scheduler-smp-preempt"):
            embedded_entry = json.loads((ROOT / f"runs/native-kernel-{profile}-readiness.json").read_bytes())["build"]["kernel_entry"]
            self.assert_retained_receipt_admission(entry, embedded_entry)
            self.assertEqual(json.dumps(embedded_entry, sort_keys=True, allow_nan=False),
                             json.dumps(receipt, sort_keys=True, allow_nan=False))
        self.assertNotEqual(record["entry_receipt_sha256"], current["historical_cycle208_entry_provenance_qualification"]["entry_receipt_sha256"])
        current_lock_entry = json.loads((ROOT / "runs/native-kernel-locks-readiness.json").read_bytes())["build"]["kernel_entry"]
        self.assertEqual(json.dumps(current_lock_entry, sort_keys=True), json.dumps(receipt, sort_keys=True))
        # Retain the exact old entry instead of repurposing current evidence as history.
        embedded_entry = json.loads((ROOT / "tests/fixtures/cycle181-locks-readiness.json").read_bytes())["build"]["kernel_entry"]
        self.assertIn("readiness input bindings are stale", entry.readiness_errors(embedded_entry, ROOT))
        self.assertNotEqual(json.dumps(embedded_entry, sort_keys=True, allow_nan=False), json.dumps(receipt, sort_keys=True, allow_nan=False))
        retained = (json.dumps(embedded_entry, indent=2, sort_keys=True) + "\n").encode()
        self.assertEqual(hashlib.sha256(retained).hexdigest().upper(), current["historical_cycle181_entry_provenance_qualification"]["entry_receipt_sha256"])
        self.assertEqual(current["historical_cycle175_entry_provenance_qualification"]["entry_receipt_sha256"], "9998F12E922201BA60C46521444BD1AD6CB641A0172B36F4A3552DCF66434A0B")
        for field in ("linked_byte_count", "linked_sha256", "canonical_byte_count", "canonical_sha256"):
            self.assertEqual(record[field], receipt["product"][field])
        sources = {p.relative_to(ROOT).as_posix() for p in (ROOT / "native/kernel/src").rglob("*.rs")}
        inputs = receipt["bindings"]["implementation_inputs"]
        self.assertEqual((len(sources), len(inputs)), (71, 79))
        self.assertEqual(sources - {item["path"] for item in inputs},
                         {"native/kernel/src/user_entry.rs", "native/kernel/src/user_entry/tests.rs",
                          "native/kernel/src/user_entry/prepared.rs", "native/kernel/src/user_entry/prepared_tests.rs",
                          "native/kernel/src/user_entry/cpu.rs", "native/kernel/src/user_entry/cpu_tests.rs",
                          "native/kernel/src/user_entry/bootstrap.rs", "native/kernel/src/user_root_probe.rs",
                          "native/kernel/src/user_root_probe/peer_driver/unknown.rs",
                          "native/kernel/src/user_entry/timer.rs", "native/kernel/src/user_root_probe/timer_driver.rs",
                          "native/kernel/src/user_entry/privilege.rs", "native/kernel/src/arch/x86_64/user.rs",
                          "native/kernel/src/user_entry/preemption.rs", "native/kernel/src/arch/x86_64/user_preempt.rs",
                          "native/kernel/src/user_entry/syscall.rs", "native/kernel/src/arch/x86_64/user_syscall.rs",
                          "native/kernel/src/user_entry/task.rs", "native/kernel/src/arch/x86_64/user_task.rs",
                          "native/kernel/src/user_root_probe/task_driver.rs",
                          "native/kernel/src/user_entry/context.rs", "native/kernel/src/arch/x86_64/user_slice.rs",
                          "native/kernel/src/user_root_probe/peer_driver.rs",
                          "native/kernel/src/user_entry/spawn.rs", "native/kernel/src/user_entry/spawn_tests.rs",
                          "native/kernel/src/user_root_probe/spawn_driver.rs",
                          "native/kernel/src/user_entry/timer/drain.rs",
                          "native/kernel/src/user_entry/timer/drain/tests.rs",
                          "native/kernel/src/user_entry/timer/watchdog.rs",
                          "native/kernel/src/user_entry/timer/watchdog/tests.rs",
                          "native/kernel/src/arch/x86_64/user_watchdog.rs",
                          "native/kernel/src/user_root_probe/timer_driver/drain.rs"})
        self.assertEqual(record["kernel_crate_rust_source_count"], 39)
        self.assertEqual(record["release_gate_rejection_cases"], 12)
        self.assertTrue(record["applies_to_current_source"])
        self.assertEqual(record["source_binding_count"], len(inputs))
        self.assertTrue(record["exact_receipt_and_product_reproduction_passed"])
        self.assertEqual(record["latest_reproduction_cycle"], 224)
        repaired = current["historical_cycle185_closeout_regression"]
        self.assertEqual((repaired["tests_run"], repaired["tests_passed"], repaired["tests_failed"]), (50, 50, 0))
        self.assertEqual(repaired["initial_combined_closeout"]["tests_failed"], 2)
        self.assertEqual(repaired["combined_regression"]["status"], "pass")
        self.assertEqual((repaired["combined_regression"]["tests_run"], repaired["combined_regression"]["tests_passed"],
                          repaired["combined_regression"]["tests_skipped"]), (221, 221, 0))
        self.assertEqual(current["historical_cycle183_closeout_regression"]["tests_passed"], 59)
        self.assertEqual(current["historical_cycle184_closeout_regression"]["tests_passed"], 109)
        metadata_failure = current["historical_cycle184_closeout_regression"]["initial_metadata_closeout"]
        self.assertEqual((metadata_failure["tests_run"], metadata_failure["tests_passed"], metadata_failure["tests_failed"]), (46, 43, 3))
        self.assertEqual(metadata_failure["status"], "fail")
        self.assertTrue(repaired["hostile_environment"])
        self.assertFalse(repaired["merge_qualified"])
        host = current["current_host_toolchain_qualification"]
        profile_data = (ROOT / host["profile_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(profile_data).hexdigest().upper(), host["profile_sha256"])
        profile = json.loads(profile_data)
        self.assertEqual(sum(t["file_count"] for t in profile["input_trees"]), host["pinned_files"])
        self.assertEqual(sum(t["byte_count"] for t in profile["input_trees"]), host["pinned_bytes"])
        self.assertEqual(host["initial_hostile_regression"]["tests_failed"], 1)
        self.assertFalse(host["complete_host_attestation"])
        self.assertFalse(host["second_builder_reproduced"])
        from runtime import native_elf_loader as elf

        shared = current["current_shared_loader_qualification"]
        raw_shared = (ROOT / shared["receipt_path"]).read_bytes()
        shared_receipt = json.loads(raw_shared)
        self.assertEqual(elf.readiness_errors(shared_receipt), ["readiness input bindings are stale"])
        self.assertFalse(shared["applies_to_current_source"])
        self.assertEqual(shared["receipt_sha256"], hashlib.sha256(raw_shared).hexdigest().upper())
        self.assertEqual(shared["implementation_input_count"], len(shared_receipt["bindings"]["implementation_inputs"]))
        self.assertEqual(shared["implementation_input_count"], 19)
        for key in ("rust_host_tests_passed", "clippy_runs_passed", "no_std_target_builds_passed",
                    "pooleboot_integration_builds_passed", "exact_loaded_byte_vectors_matched",
                    "maximum_relocations_exercised", "negative_controls_passed",
                    "differential_fuzz_cases", "differential_mismatches"):
            self.assertEqual(shared[key], shared_receipt["summary"][key])
        self.assertEqual(shared["host_profile_sha256"], host["profile_sha256"])
        self.assertEqual(record["inherited_shared_loader_input_count"], 19)
        self.assertTrue({p.as_posix() for p in elf.IMPLEMENTATION_INPUTS}.issubset({b["path"] for b in inputs}))
        self.assertEqual((shared["host_profile_rejection_cases"], shared["build_input_mutation_cases"],
                          shared["entry_shared_input_mutation_cases"], shared["invalid_output_admission_cases"]),
                         (10, 8, 19, 2))
        self.assertFalse(shared["invalid_output_created_or_replaced"])
        self.assertTrue(shared["exact_receipt_reproduction_passed"])
        self.assertFalse(shared["production_ready"])
        self.assertEqual(current["historical_cycle182_entry_provenance_qualification"]["source_binding_count"], 61)
        self.assertEqual(current["historical_cycle182_source_projection"]["next_dependency_move_id"], "N5-ELF-001")
        self.assertEqual(current["historical_cycle182_closeout_regression"]["tests_passed"], 39)
        audit = current["historical_cycle181_closeout_regression"]
        self.assertEqual(audit["status"], "fail")
        self.assertEqual((audit["tests_run"], audit["tests_passed"], audit["tests_failed"], audit["tests_skipped"]), (334, 331, 1, 2))
        self.assertFalse(audit["merge_qualified"])
        self.assertFalse(audit["canonical_full_replay_performed"])
        drift = audit["preserved_entry_diagnostic"]
        self.assertEqual((drift["recorded_value"], drift["observed_value"]), (148480, 147968))
        self.assertEqual(drift["differing_path"], "$.toolchain.pkelf1_probe_qualification.host_probe_byte_count")
        self.assertEqual(drift["recorded_receipt_sha256"], current["historical_cycle181_entry_provenance_qualification"]["entry_receipt_sha256"])
        self.assertEqual(drift["canonical_kernel_sha256"], current["historical_cycle191_entry_provenance_qualification"]["canonical_sha256"])
        self.assertNotEqual(drift["canonical_kernel_sha256"], receipt["product"]["canonical_sha256"])
        self.assertTrue(drift["all_kernel_product_fields_equal"])
        self.assertFalse(drift["host_probe_root_cause_established"])
        self.assertFalse(drift["public_receipt_replaced"])
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
        self.assertEqual(current["historical_cycle173_source_projection"]["passed_checks"], 22)
        self.assertEqual(current["historical_cycle174_source_projection"]["passed_checks"], 24)
        self.assertEqual(current["historical_cycle180_source_projection"]["passed_checks"], 13)
        self.assertEqual(current["historical_cycle192_source_projection"]["passed_checks"], 9)
        self.assertEqual(current["current_focused_source_projection"]["passed_checks"], 2)
        self.assertFalse(current["current_candidate_audit"]["aggregate_suite_passed"])

    def test_task_stack_qualification_is_host_only_and_source_bound(self) -> None:
        from tools import qualify_native_reclamation_core as core

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        stack = current["current_task_stack_qualification"]
        self.assertEqual(stack["cycle"], 216)
        self.assertEqual(stack["contract_id"], "PKSTACK1")
        self.assertEqual(stack["scope"], "prepared_inactive_task_stack_retention_and_scrubbed_release")
        self.assertEqual(stack["receipt_path"], core.REPORT.relative_to(ROOT).as_posix())
        raw = core.REPORT.read_bytes()
        self.assertEqual(stack["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        receipt = json.loads(raw)
        self.assert_reclamation_admission(receipt)
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
        self.assertFalse(stack["linked_kernel_byte_identical"])
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
            self.assertIn("docs/checkpoints/cycle177-dispatch-execution-holds.md", flag["evidence"])
        execution = current["current_execution_qualification"]
        self.assertEqual(execution["cycle"], 216)
        for key, receipt_key in (("contract_id", "task_execution_contract_id"),
                                 ("scope", "task_execution_scope"),
                                 ("execution_test_methods", "task_execution_test_count"),
                                 ("kernel_sha256", "linked_kernel_sha256")):
            self.assertEqual(execution[key], receipt[receipt_key])
            self.assertIs(type(execution[key]), type(receipt[receipt_key]))
        self.assertEqual(execution["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual(execution["evidence_parser_rejection_cases"], 30)
        self.assertEqual(execution["loss_modes"], ["drop", "forget", "unwind"])
        self.assertEqual(execution["scheduler_exhaustion_regressions"], 2)
        self.assertEqual(execution["fresh_qemu_runs"], 0)
        for key in ("task_execution_live_verified", "storage_address_stability_guaranteed",
                    "cross_cpu_quiescence_verified", "n12_3_complete", "production_ready"):
            self.assertIs(execution[key], False)
        for name in ("dependency",):
            pending = current["historical_cycle180_" + name + "_qualification"]
            self.assertEqual((pending["cycle"], pending["source_validation_cycle"]), (180, 180))
            self.assertEqual(pending["status"], "source_requalification_required")
            self.assertFalse(pending["applies_to_current_source"])
            self.assertEqual(pending["historical_record"], "historical_cycle175_" + name + "_qualification")
            self.assertTrue(pending["readiness_replay_required_profiles"])
            self.assertEqual(pending["qualified_profiles"], [])
            self.assertEqual(pending["fresh_qemu_runs"], 0)
            self.assertFalse(pending["production_ready"])

    def test_historical_dependency_replay_preserves_fourteen_receipts_without_current_promotion(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        qualification = current["historical_cycle175_dependency_qualification"]
        pending = current["historical_cycle180_dependency_qualification"]
        self.assertEqual(pending["readiness_replay_required_profiles"], qualification["qualified_profiles"])
        self.assertEqual(qualification["cycle"], 175)
        self.assertEqual(qualification["source_validation_cycle"], 175)
        self.assertFalse(qualification["embedded_entry_provenance_replay_pending"])
        self.assertEqual(qualification["readiness_replay_required_profiles"], [])
        self.assertEqual(qualification["superseded_profiles"], ["smp_ipi"])
        self.assertEqual((qualification["embedded_entry_rejection_cases"], qualification["invalid_current_entry_dependency_cases"]), (224, 56))
        self.assertEqual(qualification["smp_non_object_regression_cases"], 4)
        self.assertEqual(len(qualification["receipt_bindings"]), 14)
        self.assertEqual(len(set(qualification["qualified_profiles"])), 14)
        self.assertFalse(qualification["boot_chain_replay_pending"])
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        self.assertFalse(qualification["production_ready"])
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["superseded_initial_runs"]), (28, 2))
        self.assertEqual((qualification["negative_control_groups"], qualification["negative_control_cases"]), (660, 2126))
        self.assertEqual((qualification["memory_gate_rejection_cases"], qualification["host_identity_gate_rejection_cases"]), (20, 38))
        encoded = json.dumps(qualification, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "EE9761DF55364B20C4AB55877816B41E54C11AC460D01348A4C22CC7101173DB")
        self.assertFalse(current["current_dependency_qualification"]["applies_to_current_source"])
        qualification = current["historical_cycle181_dependency_qualification"]
        self.assertEqual((qualification["cycle"], qualification["source_validation_cycle"]), (181, 181))
        self.assertEqual(qualification["status"], "live_replay_pass_control_execution_incomplete")
        self.assertTrue(qualification["applies_to_current_source"])
        self.assertFalse(qualification["positive_receipts_rebound_in_tests"])
        self.assertFalse(qualification["control_execution_complete"])
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        self.assertFalse(qualification["production_ready"])
        self.assertTrue(qualification["reported_case_count_is_not_executed_rejection_count"])
        self.assertEqual(qualification["unproven_per_control_rejection_groups_at_least"], 65)
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["superseded_initial_runs"]), (28, 4))
        self.assertEqual(qualification["superseded_profiles"], ["atomics", "locks"])
        self.assertEqual((qualification["memory_gate_rejection_cases"], qualification["host_identity_gate_rejection_cases"]), (20, 59))
        self.assertEqual((qualification["focused_python_tests"], qualification["focused_python_passed"], qualification["focused_python_skipped"]), (166, 164, 2))
        self.assertEqual(len(qualification["receipt_bindings"]), 14)
        for profile, binding in zip(qualification["qualified_profiles"], qualification["receipt_bindings"], strict=True):
            with self.subTest(profile=profile):
                module = importlib.import_module("runtime.native_kernel_" + profile)
                self.assertEqual(binding["path"], module.READINESS_RELATIVE)
                raw = (ROOT / binding["path"]).read_bytes()
                if profile == "physical_memory":
                    self.assertEqual(binding["sha256"], "EEFD0E8592CB98E8D0EDBCB480FFD6DDEF761C5432AE0ED4FB3C95C73E10D008")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "virtual_memory":
                    self.assertEqual(binding["sha256"], "4AFEA30E25DB4DCD0D9038E01D3FE1CC6EE5D82DBAB4595A4631D34902460BB7")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "interrupt_time":
                    self.assertEqual(binding["sha256"], "19FB9DA0B525064D56126E9EEE159C887A46B4FD1EB6B6DA3646C5F88182E7B2")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "smp_first_ap":
                    self.assertEqual(binding["sha256"], "58F0EBEEA6C844714D4E57568C56987C0A9E03D92A9D29421974A6D7C91FD5AC")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "smp_percpu_runtime":
                    self.assertEqual(binding["sha256"], "03B2E751984D8FADBB64302748E3D4CBB025F5DF285D665AAD8399CDA9DC07C2")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "smp_ipi":
                    self.assertEqual(binding["sha256"], "2B1F8D623D31476F2C8886DFD583BE9514C68A2B3D0DA36BC75DDD13D6823CCA")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "scheduler":
                    self.assertEqual(binding["sha256"], "CC340D6AFAD07D3A17A3E63AC296A228E8366EC48D623B277DAAFEF588B4E6D2")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "scheduler_preempt":
                    self.assertEqual(binding["sha256"], "D1F027454CDE978D504FFA232A427ABC7992D92193B593DBF9261EF2C9E190BE")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    continue
                if profile == "scheduler_deferred":
                    self.assertEqual(binding["sha256"], "05F5250DD497E0803959AA67939362DBA19023A97089C06AA1B66837AF6C64AC")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    self.assert_retained_receipt_admission(module, json.loads(raw))
                    continue
                if profile == "scheduler_smp":
                    self.assertEqual(binding["sha256"], "47382C39021EB7BF6580844B6E4B1F2BAC53C05FD56ECB2313E036C81A1A391C")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    self.assert_retained_receipt_admission(module, json.loads(raw))
                    continue
                if profile == "scheduler_ap_workers":
                    self.assertEqual(binding["sha256"], "828E48B8EBBFF8472A9BD27B7EA7BCD2DA64E418B58E38F9FD375B640CA365C0")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    self.assert_retained_receipt_admission(module, json.loads(raw))
                    continue
                if profile == "scheduler_smp_preempt":
                    self.assertEqual(binding["sha256"], "269B22A60B6E5B7D512EC18BF1EC30396C6E0AB41B2182303BF4E89A3AF18076")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    self.assert_retained_receipt_admission(module, json.loads(raw))
                    continue
                if profile == "atomics":
                    self.assertEqual(binding["sha256"], "7DB057751A677EE46115146E84FCE19EDD3F49B5E7B699948B13307DA1ACA986")
                    self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                    self.assert_retained_receipt_admission(module, json.loads(raw))
                    self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_atomics_readiness())
                    continue
                self.assertEqual(profile, "locks")
                self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                self.assert_retained_receipt_admission(module, json.loads(raw))
                raw = (ROOT / "tests/fixtures/cycle181-locks-readiness.json").read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
                receipt = json.loads(raw)
                self.assertTrue(module.readiness_errors(receipt, ROOT))
                entry = receipt["kernel_summary"]["entry_readiness"] if profile == "atomics" else receipt["build"]["kernel_entry"]
                current_entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_text(encoding="utf-8"))
                self.assertNotEqual(json.dumps(entry, sort_keys=True, allow_nan=False), json.dumps(current_entry, sort_keys=True, allow_nan=False))
                self.assertEqual(entry["product"]["canonical_sha256"], qualification["kernel_sha256"])
                self.assertEqual((entry["host_tests"]["test_count"], entry["host_tests"]["test_pass_count"]), (245, 245))
                self.assertEqual(binding["kernel_host_tests"], 245)
                self.assertEqual(len(receipt["execution"]["runs"]), binding["fresh_runs"])
                for run in receipt["execution"]["runs"]:
                    self.assertEqual(run["qemu_exit_code"], 0)
                    self.assertEqual(len(run["markers"]), binding["marker_count"])
                    self.assertIn(entry["product"]["manifest_fields"]["build_id"], "\n".join(run["markers"]))
                    self.assertNotIn(current_entry["product"]["manifest_fields"]["build_id"], "\n".join(run["markers"]))
                self.assertEqual(len(receipt["negative_controls"]), binding["negative_groups"])
                self.assertEqual(sum(c.get("case_count", 1) for c in receipt["negative_controls"]), binding["negative_cases"])
                name = "scheduler_preemption" if profile == "scheduler_preempt" else profile
                check = getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")()
                self.assert_current_gate_projection(check)
        audit = current["current_control_execution_audit"]
        self.assertEqual((audit["cycle"], audit["status"]), (229, "open"))
        self.assertFalse(audit["blocks_merge_qualification"])
        self.assertFalse(audit["production_ready"])
        self.assertEqual(audit["requirement_id"], "ADD-N36-RECEIPT-COVERAGE-001")
        self.assertEqual(audit["next_profile"], "full_exact_candidate_qualification")
        self.assertEqual(len(audit["source_control_gaps"]), 0)
        self.assertEqual(sum(g["reported_case_count"] for g in audit["source_control_gaps"]), 0)
        for gap in audit["source_control_gaps"]:
            module = importlib.import_module("runtime.native_kernel_" + gap["profile"])
            self.assertEqual(gap["control_ids"], list(module.NEGATIVE_CONTROL_IDS[gap["slice_start"]:gap["slice_end"]]))
            self.assertEqual(len(gap["control_ids"]), gap["reported_case_count"])
            self.assertEqual(hashlib.sha256((ROOT / gap["source_path"]).read_bytes()).hexdigest().upper(), gap["source_sha256"])
        previous = current["historical_cycle170_source_projection"]
        encoded = json.dumps(previous, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "8CA7E27C2F2631C173FF285A144499299705731773D17F609DE4CF520A487EA2")

    def test_historical_memory_runtime_replay_binds_retained_receipts_and_preserves_history(self) -> None:
        from collections import Counter

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        projection = current["historical_cycle194_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["total_checks"]), (194, 19, 27))
        self.assertEqual(projection["pending_downstream_native_checks"], 8)
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-001")
        self.assertEqual(projection["final_receipt_fresh_qemu_runs"], 10)
        record = current["historical_cycle194_dependency_qualification"]
        fresh = ("physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime")
        self.assertEqual(record["newly_qualified_profiles"], list(fresh))
        self.assertEqual(record["qualified_profiles"], list(fresh) + ["smp_ipi"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 8)
        self.assertEqual((record["fresh_qemu_runs"], record["negative_control_groups"], record["negative_control_cases"]), (10, 388, 528))
        self.assertEqual(record["recorded_evidence_case_total"], 990)
        self.assertTrue(record["disabled_PMM_parser_and_memory_oracle_detected"])
        self.assertEqual(record["PMM_marker_validator_calls"], 189)
        self.assertFalse(record["control_execution_complete"])
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 65)
        self.assertFalse(record["current_candidate_full_gate_passed"])
        self.assertFalse(record["positive_receipts_rebound_in_tests"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["production_ready"])
        current_entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        for binding in record["receipt_bindings"]:
            profile = binding["profile"]
            raw = (ROOT / binding["path"]).read_bytes()
            receipt = json.loads(raw)
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            module = importlib.import_module("runtime.native_kernel_" + profile)
            self.assert_retained_receipt_admission(module, receipt)
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")())
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True), json.dumps(current_entry, sort_keys=True))
            self.assertNotEqual(receipt["build"]["kernel_entry"]["product"]["canonical_sha256"], record["kernel_sha256"])
            self.assertEqual(binding["kernel_host_tests"], 246)
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertEqual(binding["hostile_cases"], sum(c.get("case_count", 1) for c in receipt["negative_controls"]))
            if profile in fresh:
                mutations = importlib.import_module("tests.test_native_kernel_" + profile).recorded_receipt_mutations
                self.assertEqual(binding["recorded_evidence_cases"], dict(Counter(f for f, _, _ in mutations(receipt))))
            else:
                self.assertEqual(binding, current["historical_cycle193_dependency_qualification"]["receipt_bindings"][0])
        for cycle, digest in (
            (186, "94A088DB840E5E8B90ADBF627B026F1456224401D2F05E4EF802BD3C27A5FF21"),
            (187, "729588FB4D23ABD3A5BA60D2640407A7010330391ADE8658C81F02FC5413FF10"),
            (188, "C3F8015A7E0633280F497802AD5FAAD8EED72FC36E2B86621A506CD75B76D6A4"),
            (189, "27E325960A5D483FFC5C4B02C475FE9DAFD4F00C16BA8597ED441DEAED623236"),
            (190, "0B7AC33BB417D05D5D77DEE1E3C3CFA1CFD61FB3457B627D2431F61315706E71"),
        ):
            historical = current[f"historical_cycle{cycle}_dependency_qualification"]
            self.assertEqual(hashlib.sha256(json.dumps(historical, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper(), digest)
        ownership = current["historical_cycle196_ownership_qualification"]
        self.assertEqual((ownership["cycle"], ownership["host_qualification_cycle"], ownership["live_replay_cycle"], ownership["virtual_memory_live_replay_cycle"]), (194, 192, 192, 194))
        self.assertEqual(ownership["virtual_memory_receipt_sha256"], record["receipt_bindings"][1]["sha256"])
        self.assertTrue(ownership["active_root_current_image_replay_complete"])
        self.assertTrue(ownership["virtual_memory_live_receipt_source_current"])
        self.assertFalse(ownership["task_stack_live_integration_verified"])
        self.assertFalse(ownership["general_task_CPU_retirement_integration_verified"])
        closeout = current["historical_cycle194_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (57, 57, 0))
        combined = closeout["combined_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_skipped"]), (307, 307, 0))
        self.assertEqual(closeout["initial_combined_invocation"]["tests_run"], 0)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])

    def test_current_scheduler_evidence_binds_genuine_receipt_and_preserves_history(self) -> None:
        import ast
        from collections import Counter
        from runtime import native_kernel_scheduler as scheduler
        from runtime import native_kernel_scheduler_preempt as preempt
        from tests.test_native_kernel_scheduler import recorded_receipt_mutations

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("focused_source_projection", "dependency_qualification", "closeout_regression", "preemption_control_execution_audit"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle195_" + suffix]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["total_checks"]), (195, 20, 27))
        self.assertEqual(projection["pending_downstream_native_checks"], 7)
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-PREEMPT-001")
        self.assertEqual((projection["final_receipt_fresh_qemu_runs"], projection["superseded_initial_qemu_runs"]), (2, 2))
        old = gate["historical_cycle194_dependency_qualification"]
        self.assertEqual(hashlib.sha256(json.dumps(old, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper(),
                         "78C00CD3D6C8D153C6427F5ED9D008D8E55F9B419DBC5F37D20545F49D52F399")
        record = gate["current_dependency_qualification"]
        self.assertEqual(record["newly_qualified_profiles"], ["scheduler"])
        self.assertEqual(record["qualified_profiles"], old["qualified_profiles"] + ["scheduler"])
        self.assertEqual(record["receipt_bindings"][:-1], old["receipt_bindings"])
        self.assertEqual(record["readiness_replay_required_profiles"], [p for p in old["readiness_replay_required_profiles"] if p != "scheduler"])
        self.assertEqual((record["fresh_qemu_runs"], record["negative_control_groups"], record["negative_control_cases"]), (2, 28, 115))
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["current_candidate_full_gate_passed"])
        self.assertFalse(record["positive_receipts_rebound_in_tests"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["control_execution_complete"])
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 74)
        binding = record["receipt_bindings"][-1]
        self.assertEqual(binding["path"], scheduler.READINESS_RELATIVE)
        raw = (ROOT / binding["path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual(binding["sha256"], "0CA89C0F579FB5BA086ED61FF7D56B0F68E6C82A974B4698CFEA84F621B83363")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assert_retained_receipt_admission(scheduler, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_readiness())
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                         json.dumps(entry, sort_keys=True, allow_nan=False))
        self.assertNotEqual(receipt["build"]["kernel_entry"]["product"]["canonical_sha256"], record["kernel_sha256"])
        self.assertEqual(binding["kernel_host_tests"], entry["host_tests"]["test_count"])
        self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
        self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
        self.assertEqual(binding["hostile_cases"], sum(c["case_count"] for c in receipt["negative_controls"]))
        counts = dict(Counter(f for f, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(record["recorded_evidence_cases"], counts)
        self.assertEqual(record["recorded_evidence_case_total"], sum(counts.values()))
        self.assertEqual(sum(counts.values()), 221)
        self.assertTrue(record["per_control_case_counts_bound"])
        self.assertTrue(record["raw_host_probe_independently_reparsed"])
        self.assertTrue(record["typed_observation_and_summary_rederived"])
        self.assertEqual((record["disabled_validator_checks"], record["rejected_output_preservation_cases"]), (3, 2))
        before, after = record["pre_repair_counterexample"], record["post_repair_counterexample_replay"]
        self.assertEqual((before["cases"], before["runtime_accepted"], before["aggregate_gate_accepted"],
                          before["runtime_exceptions"], before["aggregate_gate_exceptions"]), (219, 172, 100, 4, 9))
        self.assertEqual(after["cases"], 219)
        for key in ("runtime_accepted", "aggregate_gate_accepted", "runtime_exceptions", "aggregate_gate_exceptions"):
            self.assertEqual(after[key], 0)
        closeout = gate["current_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (14, 14, 0))
        self.assertEqual(closeout["initial_payload_regression"]["tests_failed"], 1)
        self.assertEqual(closeout["initial_payload_regression"]["tests_errored"], 1)
        self.assertEqual(closeout["cloud_backup_regression"]["tests_passed"], 23)
        self.assertEqual(closeout["initial_metadata_regression"]["tests_failed"], 1)
        self.assertEqual(closeout["corrected_metadata_regression"]["tests_passed"], 43)
        combined = closeout["combined_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_skipped"]), (322, 322, 0))
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(record["production_ready"])
        audit = gate["current_preemption_control_execution_audit"]
        self.assertEqual((audit["cycle"], audit["status"], audit["reported_case_count"]), (195, "open", 9))
        self.assertEqual(audit["aggregate_unproven_groups_at_least"], 74)
        self.assertEqual(audit["prior_audit_groups"], current["historical_cycle201_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"])
        self.assertTrue(audit["blocks_merge_qualification"])
        self.assertFalse(audit["native_preemption_defect_proved"])
        self.assertFalse(audit["all_profile_control_execution_audited"])
        self.assertEqual(audit["control_ids"], list(preempt.NEGATIVE_CONTROL_IDS[15:24]))
        prior_ids = {i for gap in current["historical_cycle201_control_execution_audit"]["source_control_gaps"] for i in gap["control_ids"]}
        self.assertFalse(prior_ids & set(audit["control_ids"]))
        source = (ROOT / audit["source_path"]).read_bytes()
        self.assertEqual(audit["source_sha256"], "9461C3A0DE65CDEA1C9F1E31FAF7518225293E5B1DAFE2238C85D33DB6783473")
        self.assertNotEqual(hashlib.sha256(source).hexdigest().upper(), audit["source_sha256"])
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "_negative_controls")
        loops = [n for n in function.body if isinstance(n, ast.For) and ast.unparse(n.iter) == "ids[15:24]"]
        self.assertEqual(loops, [])
        self.assertEqual(audit["loop_calls"], ["controls.append"])
        repaired = current["historical_cycle200_preemption_control_execution_audit"]
        self.assertEqual((repaired["cycle"], repaired["repaired_groups"], repaired["aggregate_unproven_groups_at_least"]), (196, 9, 65))
        projection = current["historical_cycle196_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (21, 6))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-DEFERRED-001")
        now = current["historical_cycle196_dependency_qualification"]
        self.assertEqual(now["receipt_bindings"][:-1], record["receipt_bindings"])
        self.assertEqual(now["newly_qualified_profiles"], ["scheduler_preempt"])
        self.assertEqual(now["recorded_evidence_case_total"], 232)
        raw = (ROOT / repaired["receipt_path"]).read_bytes()
        self.assertEqual(repaired["receipt_sha256"], "2DFF24BCF02069ADB74E78F53F63A1F3EBF2C1EB478F2DBFF7D27D31E9FD757B")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), repaired["receipt_sha256"])
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(preempt, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_preemption_readiness())
        self.assertEqual(now["recorded_evidence_cases"], dict(Counter(f for f, _, _ in recorded_receipt_mutations(receipt))))
        self.assertEqual(now["additional_control_receipt_corruptions"], 26)
        self.assertEqual(now["negative_control_cases"], sum(item["case_count"] for item in receipt["negative_controls"]))
        self.assertEqual(now["native_control_cases"], receipt["build"]["native_control_probe"]["hostile_cases_total"])
        self.assertFalse(now["control_execution_complete"])
        self.assertFalse(current["current_closeout_regression"]["canonical_full_replay_performed"])

    def test_historical_pmm_replay_is_distinct_from_current_kernel_replay(self) -> None:
        from runtime import native_kernel_physical_memory as pmm
        from tests.test_native_kernel_physical_memory import recorded_receipt_mutations
        from collections import Counter

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        focused = current["historical_cycle186_source_projection"]
        self.assertEqual((focused["cycle"], focused["passed_checks"], focused["total_checks"]), (186, 14, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 13)
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["superseded_initial_qemu_runs"]), (2, 2))
        self.assertEqual(focused["focused_python_tests_passed"], 12)
        self.assertEqual(focused["next_dependency_move_id"], "N9-VM-DIRECT-MAP-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        record = current["historical_cycle186_dependency_qualification"]
        self.assertEqual(record["qualified_profiles"], ["physical_memory"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 13)
        self.assertTrue(record["applies_to_current_source"])
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["positive_receipts_rebound_in_tests"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["current_candidate_full_gate_passed"])
        self.assertFalse(record["production_ready"])
        binding, = record["receipt_bindings"]
        raw = (ROOT / pmm.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assertEqual(binding["sha256"], "3FD215CB703F8DF55A8EAB4D5716EF9466F33384A89F805FCF704DE395BF8F16")
        self.assert_retained_receipt_admission(pmm, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_physical_memory_readiness())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["kernel_host_tests"]), (2, 191, 245))
        self.assertNotEqual(record["kernel_sha256"], receipt["build"]["kernel_entry"]["product"]["canonical_sha256"])
        counts = dict(Counter(family for family, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(counts, record["recorded_evidence_cases"])
        self.assertEqual(sum(counts.values()), 234)
        old = record["pre_repair_counterexample"]
        self.assertEqual((old["cases"], old["runtime_accepted"], old["aggregate_gate_accepted"]), (65, 62, 61))

    def test_historical_vm_replay_is_distinct_from_current_kernel_replay(self) -> None:
        from runtime import native_kernel_virtual_memory as vm
        from tests.test_native_kernel_virtual_memory import recorded_receipt_mutations
        from collections import Counter

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        focused = current["historical_cycle187_source_projection"]
        self.assertEqual((focused["cycle"], focused["passed_checks"], focused["total_checks"]), (187, 15, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 12)
        self.assertEqual((focused["final_receipt_fresh_qemu_runs"], focused["superseded_initial_qemu_runs"]), (2, 2))
        self.assertEqual(focused["focused_python_tests_passed"], 10)
        self.assertEqual(focused["next_dependency_move_id"], "N8-IRQ-001")
        self.assertFalse(focused["canonical_full_replay_performed"])
        self.assertFalse(focused["production_ready"])
        record = current["historical_cycle187_dependency_qualification"]
        self.assertEqual(record["qualified_profiles"], ["physical_memory", "virtual_memory"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 12)
        self.assertTrue(record["applies_to_current_source"])
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["positive_receipts_rebound_in_tests"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["current_candidate_full_gate_passed"])
        self.assertFalse(record["production_ready"])
        binding = next(item for item in record["receipt_bindings"] if item["profile"] == "virtual_memory")
        raw = (ROOT / vm.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assertEqual(binding["sha256"], "F2CC0C55F09600DE728D2BDAB1F26855EF7BE624AF9F6B1D00B4F16D9418A1FC")
        self.assert_retained_receipt_admission(vm, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_virtual_memory_readiness())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["kernel_host_tests"]), (2, 48, 245))
        self.assertNotEqual(record["kernel_sha256"], receipt["build"]["kernel_entry"]["product"]["canonical_sha256"])
        counts = dict(Counter(family for family, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(counts, record["recorded_evidence_cases"])
        self.assertEqual(sum(counts.values()), 115)
        old = record["pre_repair_counterexample"]
        self.assertEqual((old["cases"], old["runtime_accepted"], old["aggregate_gate_accepted"]), (65, 46, 45))
        ownership = current["historical_cycle190_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 187)
        self.assertEqual(ownership["virtual_memory_receipt_sha256"], binding["sha256"])
        self.assertTrue(ownership["active_root_current_image_replay_complete"])
        self.assertTrue(ownership["virtual_memory_live_receipt_source_current"])
        self.assertFalse(ownership["live_receipt_source_current"])
        self.assertFalse(ownership["ap_runtime_live_integration_verified"])
        self.assertFalse(ownership["current_candidate_full_gate_passed"])

    def test_historical_irq_replay_binds_recorded_evidence_without_current_promotion(self) -> None:
        from collections import Counter
        from runtime import native_kernel_interrupt_time as irq
        from tests.test_native_kernel_interrupt_time import recorded_receipt_mutations

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        focused = current["historical_cycle188_source_projection"]
        self.assertEqual((focused["cycle"], focused["passed_checks"], focused["total_checks"]), (188, 16, 27))
        self.assertEqual(focused["pending_downstream_native_checks"], 11)
        self.assertEqual(focused["next_dependency_move_id"], "N8-SMP-FIRST-AP-001")
        self.assertEqual((focused["focused_python_tests_passed"], focused["focused_python_tests_skipped"]), (12, 0))
        self.assertFalse(focused["canonical_full_replay_performed"])
        record = current["historical_cycle188_dependency_qualification"]
        self.assertEqual(record["qualified_profiles"], ["physical_memory", "virtual_memory", "interrupt_time"])
        self.assertEqual(record["newly_qualified_profiles"], ["interrupt_time"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 11)
        self.assertTrue(record["applies_to_current_source"])
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["positive_receipts_rebound_in_tests"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["current_candidate_full_gate_passed"])
        self.assertFalse(record["production_ready"])
        binding = next(item for item in record["receipt_bindings"] if item["profile"] == "interrupt_time")
        raw = (ROOT / irq.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assertEqual(binding["sha256"], "A8812EE8F48CBA157554EB3264EA945082641014D9E2FE1C7A3982D648FF046B")
        self.assert_retained_receipt_admission(irq, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_interrupt_time_readiness())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["kernel_host_tests"]), (2, 58, 245))
        counts = dict(Counter(family for family, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(counts, record["recorded_evidence_cases"])
        self.assertEqual(sum(counts.values()), 229)
        self.assertEqual(record["malformed_root_and_control_cases"], 6)
        old = record["pre_repair_counterexample"]
        self.assertEqual((old["cases"], old["runtime_accepted"], old["aggregate_gate_accepted"]), (64, 52, 44))
        self.assertEqual((old["runtime_exceptions"], old["aggregate_gate_exceptions"]), (1, 4))
        repaired = current["historical_cycle188_closeout_regression"]["original_counterexample_replay"]
        self.assertEqual((repaired["runtime_accepted"], repaired["aggregate_gate_accepted"],
                          repaired["runtime_exceptions"], repaired["aggregate_gate_exceptions"]), (0, 0, 0, 0))

    def test_historical_first_ap_replay_binds_dynamic_evidence_without_current_promotion(self) -> None:
        from collections import Counter
        from runtime import native_kernel_smp_first_ap as ap
        from tests.test_native_kernel_smp_first_ap import recorded_receipt_mutations

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        focused = current["historical_cycle189_source_projection"]
        self.assertEqual((focused["cycle"], focused["passed_checks"], focused["pending_downstream_native_checks"]), (189, 17, 10))
        self.assertEqual(focused["next_dependency_move_id"], "N8-SMP-PERCPU-RUNTIME-001")
        self.assertEqual(focused["focused_python_tests_passed"], 12)
        record = current["historical_cycle189_dependency_qualification"]
        self.assertEqual(record["qualified_profiles"], ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap"])
        self.assertEqual(record["newly_qualified_profiles"], ["smp_first_ap"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 10)
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["current_candidate_full_gate_passed"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / ap.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assertEqual(binding["sha256"], "5777FF2F8C1FC296FF4C4C1CB2233B4674DF5B1BBA15C9A7F06300DD25946841")
        self.assert_retained_receipt_admission(ap, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_smp_first_ap_readiness())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["kernel_host_tests"]), (2, 72, 245))
        counts = dict(Counter(family for family, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(counts, record["recorded_evidence_cases"])
        self.assertEqual(sum(counts.values()), 159)
        self.assertEqual(record["malformed_root_and_control_cases"], 6)
        self.assertEqual(record["dynamic_comparison_scope"], "validated_TSC_online_TSC_stop_and_dependent_checksum_only")
        old = record["pre_repair_counterexample"]
        self.assertEqual((old["cases"], old["runtime_accepted"], old["aggregate_gate_accepted"]), (67, 55, 46))
        closeout = current["historical_cycle189_closeout_regression"]
        self.assertEqual(len(closeout["preserved_intake_helper_failures"]), 2)
        self.assertFalse(closeout["synthetic_consistency_is_fresh_execution"])
        self.assertFalse(current["historical_cycle190_ownership_qualification"]["ap_runtime_live_integration_verified"])

    def test_historical_percpu_replay_binds_counts_without_current_promotion(self) -> None:
        from collections import Counter
        from runtime import native_kernel_smp_percpu_runtime as ap
        from tests.test_native_kernel_smp_percpu_runtime import recorded_receipt_mutations

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        focused = current["historical_cycle190_source_projection"]
        self.assertEqual((focused["cycle"], focused["passed_checks"], focused["pending_downstream_native_checks"]), (190, 18, 9))
        self.assertEqual(focused["next_dependency_move_id"], "N8-SMP-IPI-001")
        self.assertEqual(focused["focused_python_tests_passed"], 10)
        record = current["historical_cycle190_dependency_qualification"]
        self.assertEqual(record["qualified_profiles"], ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime"])
        self.assertEqual(record["newly_qualified_profiles"], ["smp_percpu_runtime"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 9)
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        self.assertFalse(record["current_candidate_full_gate_passed"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / ap.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assertEqual(binding["sha256"], "1E1778C2E204F40D8D12C992BFF7DCEFC20067D16F9DFE1BC83CCCECFE8BD9B7")
        self.assert_retained_receipt_admission(ap, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_smp_percpu_runtime_readiness())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"], binding["kernel_host_tests"]), (2, 19, 159, 245))
        counts = dict(Counter(family for family, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(counts, record["recorded_evidence_cases"])
        self.assertEqual(sum(counts.values()), 253)
        self.assertTrue(record["per_control_case_counts_bound"])
        self.assertEqual(tuple(item["case_count"] for item in receipt["negative_controls"]), ap.NEGATIVE_CONTROL_CASE_COUNTS)
        self.assertEqual(record["dynamic_comparison_scope"], "validated_TSC_online_TSC_stop_and_both_dependent_checksums_only")
        old = record["pre_repair_counterexample"]
        self.assertEqual((old["cases"], old["runtime_accepted"], old["aggregate_gate_accepted"]), (69, 57, 48))
        repaired = current["historical_cycle190_closeout_regression"]["original_counterexample_replay"]
        self.assertEqual((repaired["runtime_accepted"], repaired["aggregate_gate_accepted"], repaired["runtime_exceptions"], repaired["aggregate_gate_exceptions"]), (0, 0, 0, 0))
        self.assertFalse(current["historical_cycle190_ownership_qualification"]["ap_runtime_live_integration_verified"])

    def test_historical_ipi_replay_preserves_mailbox_oracle_gap(self) -> None:
        from runtime import native_kernel_smp_ipi as ipi

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        focused = current["historical_cycle191_source_projection"]
        self.assertEqual((focused["cycle"], focused["passed_checks"], focused["pending_downstream_native_checks"]), (191, 19, 8))
        self.assertEqual(focused["next_dependency_move_id"], "N8-SMP-MAILBOX-ORACLE-001")
        record = current["historical_cycle191_dependency_qualification"]
        self.assertEqual(record["newly_qualified_profiles"], ["smp_ipi"])
        self.assertEqual(len(record["qualified_profiles"]), 6)
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 8)
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / ipi.READINESS_RELATIVE).read_bytes()
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assertEqual(binding["sha256"], "7ADC371664FB3778A02688DBB521211237A4788CA01EF61B48C410CEF5898B44")
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"], binding["kernel_host_tests"]), (2, 30, 249, 245))
        self.assertEqual(sum(record["recorded_evidence_cases"].values()), 528)
        self.assertTrue(record["host_recomputed_frame_checksums"])
        self.assertEqual(record["constant_only_release_controls_replaced"], 3)
        self.assertTrue(record["prior_claimed_249_cases_included_constant_only_controls"])
        self.assertFalse(record["pair_validation_is_freshness_or_authentication"])
        old = record["pre_repair_counterexample"]
        self.assertEqual((old["cases"], old["runtime_accepted"], old["aggregate_gate_accepted"]), (66, 48, 40))
        repaired = current["historical_cycle191_closeout_regression"]["original_counterexample_replay"]
        self.assertEqual((repaired["runtime_accepted"], repaired["aggregate_gate_accepted"], repaired["runtime_exceptions"], repaired["aggregate_gate_exceptions"]), (0, 0, 0, 0))
        gap = current["historical_cycle191_ipi_mailbox_oracle_gap"]
        self.assertEqual(gap["requirement_id"], "ADD-N36-RECEIPT-COVERAGE-001")
        self.assertEqual(gap["flag_id"], "FLAG-N36-RECEIPT-COVERAGE-001")
        self.assertEqual(gap["move_id"], focused["next_dependency_move_id"])
        self.assertEqual(gap["status"], "open")
        self.assertTrue(gap["blocks_merge_qualification"])
        self.assertFalse(gap["export_complete"])
        self.assertFalse(gap["host_independently_recomputes_checksums"])
        self.assertEqual(len(gap["implementation_tasks"]), 5)
        ownership = current["historical_cycle191_ownership_qualification"]
        self.assertEqual(ownership["cycle"], 191)
        self.assertTrue(ownership["live_receipt_source_current"])
        self.assertTrue(ownership["ap_runtime_live_integration_verified"])
        self.assertFalse(ownership["current_boot_artifact_set_replay_pending"])
        self.assertFalse(ownership["independent_AP_mailbox_checksum_oracle_complete"])
        self.assertFalse(ownership["task_stack_live_integration_verified"])
        self.assertFalse(ownership["general_task_CPU_retirement_integration_verified"])
        self.assertFalse(ownership["current_candidate_full_gate_passed"])
        self.assertEqual(ownership["smp_receipt_sha256"], binding["sha256"])
        self.assertEqual((ownership["attempts_per_run"], ownership["retained_free_rejections_per_attempt"], ownership["owner_release_rejections_per_attempt"]), (2, 27, 18))

    def test_current_mailbox_oracle_binds_native_receipt_without_promoting_stale_dependencies(self) -> None:
        from collections import Counter
        from runtime import native_kernel_smp_ipi as ipi
        from runtime import native_kernel_smp_mailbox as mailbox
        from tests.test_native_kernel_smp_ipi import recorded_receipt_mutations

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        projection = current["historical_cycle192_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["total_checks"]), (192, 9, 27))
        self.assertEqual(projection["pending_downstream_native_checks"], 18)
        self.assertEqual(projection["next_dependency_move_id"], "N7-TRAP-001")
        self.assertEqual((projection["final_receipt_fresh_qemu_runs"], projection["kernel_entry_runs"]), (8, 4))
        self.assertEqual(projection["superseded_initial_qemu_runs"], 2)
        record = current["historical_cycle193_dependency_qualification"]
        self.assertEqual(record["qualified_profiles"], ["smp_ipi"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 13)
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["control_execution_complete"])
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 65)
        binding, = record["receipt_bindings"]
        raw = (ROOT / ipi.READINESS_RELATIVE).read_bytes()
        receipt = json.loads(raw)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assert_retained_receipt_admission(ipi, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_smp_ipi_readiness())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"], binding["kernel_host_tests"]), (2, 33, 609, 246))
        self.assertNotEqual(record["kernel_sha256"], receipt["build"]["kernel_entry"]["product"]["canonical_sha256"])
        counts = dict(Counter(family for family, _, _ in recorded_receipt_mutations(receipt)))
        self.assertEqual(counts, record["recorded_evidence_cases"])
        self.assertEqual(sum(counts.values()), record["recorded_evidence_case_total"])
        self.assertEqual(record["recorded_evidence_case_total"], 906)
        self.assertEqual(record["raw_mailbox_rejection_cases"], 360)
        self.assertEqual(tuple(c["case_count"] for c in receipt["negative_controls"]), ipi.NEGATIVE_CONTROL_CASE_COUNTS)
        self.assertEqual(sum(c["case_count"] for c in receipt["negative_controls"]), 609)
        contract = ipi.read_json(ROOT / ipi.CONTRACT_RELATIVE)
        self.assertEqual(contract["mailbox_evidence"], mailbox.CONTRACT)
        gap = current["current_ipi_mailbox_oracle_gap"]
        self.assertEqual(gap["status"], "bounded_oracle_verified_affected_dependency_replay_complete")
        self.assertTrue(gap["export_complete"])
        self.assertTrue(gap["host_independently_recomputes_checksums"])
        self.assertEqual((gap["context_word_count"], gap["baseline_word_count"], gap["runtime_word_count"]),
                         (len(mailbox.CONTEXT_FIELDS), len(mailbox.BASELINE_FIELDS), len(mailbox.RUNTIME_FIELDS)))
        self.assertTrue(gap["disabled_oracle_detected"])
        self.assertFalse(gap["blocks_merge_qualification"])
        self.assertFalse(gap["authentication_proved"])
        self.assertFalse(gap["all_coherent_forgeries_excluded"])
        self.assertEqual(gap["remaining_affected_profiles"], 0)
        ownership = current["historical_cycle193_ownership_qualification"]
        self.assertEqual((ownership["cycle"], ownership["host_qualification_cycle"], ownership["live_replay_cycle"]), (192, 192, 192))
        self.assertEqual(ownership["smp_receipt_sha256"], binding["sha256"])
        self.assertEqual(ownership["reclamation_receipt_sha256"], current["historical_cycle196_execution_qualification"]["receipt_sha256"])
        self.assertTrue(ownership["ap_runtime_live_integration_verified"])
        self.assertTrue(ownership["independent_AP_mailbox_checksum_oracle_complete"])
        for key in ("active_root_current_image_replay_complete", "virtual_memory_live_receipt_source_current",
                    "task_stack_live_integration_verified", "general_task_CPU_retirement_integration_verified",
                    "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(ownership[key], key)
        observed = receipt["execution"]["observation"]["execution_ownership"]
        self.assertEqual((observed["attempt_count"], observed["retained_free_rejections_per_attempt"], observed["owner_release_rejections_per_attempt"]), (2, 27, 18))
        self.assertEqual(ownership["virtual_memory_live_replay_cycle"], 187)
        closeout = current["historical_cycle192_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (57, 57, 0))
        self.assertEqual(closeout["initial_gate_pin_regression"]["tests_failed"], 2)
        self.assertEqual(closeout["corrected_gate_pin_regression"]["tests_failed"], 0)
        self.assertEqual(closeout["initial_metadata_regression"]["tests_failed"], 3)
        self.assertEqual(closeout["corrected_metadata_regression"]["tests_failed"], 0)
        self.assertEqual((closeout["combined_regression"]["tests_run"], closeout["combined_regression"]["tests_passed"],
                          closeout["combined_regression"]["tests_skipped"]), (189, 189, 0))
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        for profile in projection["passing_profiles"]:
            self.assertEqual(getattr(pooleos_release_gate, "check_" + profile)()["ok"],
                             profile in current["current_focused_source_projection"]["passing_profiles"], profile)
        pending = current["current_focused_source_projection"]["failed_profiles"]
        self.assertEqual(len(pending), 25)
        for name in pending:
            self.assertFalse(getattr(pooleos_release_gate, "check_" + name)()["ok"], name)

    def test_historical_cpu_qualification_is_bound_but_replay_is_required(self) -> None:
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
        self.assertEqual(current["current_focused_source_projection"]["pending_downstream_native_checks"], 25)
        qualification = current["historical_cycle175_cpu_qualification"]
        encoded = json.dumps(qualification, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "7636441DA8B930B2AC164056A6AE31E21BBB707074360FEDAF3885DB295D6B4C")
        self.assertEqual(qualification["cycle"], 174)
        self.assertEqual(qualification["source_validation_cycle"], 174)
        self.assertFalse(qualification["embedded_entry_provenance_replay_pending"])
        self.assertEqual(qualification["readiness_replay_required_profiles"], [])
        self.assertEqual(qualification["embedded_entry_rejection_cases"], 80)
        self.assertEqual(qualification["invalid_current_entry_dependency_cases"], 20)
        self.assertEqual(qualification["entry_identity_comparison"], "canonical_JSON_typed_equality")
        self.assertEqual(current["historical_cycle173_cpu_qualification"]["cycle"], 170)
        self.assertEqual(qualification["kernel_sha256"], current["historical_cycle175_boot_chain_qualification"]["kernel_sha256"])
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["negative_control_groups"]), (14, 225))
        self.assertEqual((qualification["focused_python_tests"], qualification["aggregate_gate_regression_cases"]), (47, 17))
        self.assertEqual(qualification["kernel_host_tests_per_qualifier"], 243)
        self.assertEqual(qualification["whpx_exception_runs"], 2)
        self.assertEqual(qualification["expected_tcg_limitation_probes"], 1)
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        self.assertFalse(qualification["production_ready"])
        self.assertEqual({b["path"] for b in qualification["receipt_bindings"]}, expected_paths)
        self.assertEqual(len(qualification["receipt_bindings"]), 5)
        self.assertFalse(current["historical_cycle184_cpu_qualification"]["applies_to_current_source"])
        qualification = current["historical_cycle181_cpu_qualification"]
        self.assertEqual((qualification["cycle"], qualification["source_validation_cycle"]), (180, 181))
        self.assertEqual(qualification["status"], "single_host_cpu_replay_pass")
        self.assertTrue(qualification["applies_to_current_source"])
        self.assertFalse(qualification["positive_receipts_rebound_in_tests"])
        self.assertTrue(qualification["recorded_marker_replay_verified"])
        self.assertEqual(qualification["readiness_replay_required_profiles"], [])
        self.assertEqual(qualification["kernel_sha256"], current["historical_cycle191_boot_chain_qualification"]["kernel_sha256"])
        self.assertEqual((qualification["focused_python_tests"], qualification["aggregate_gate_regression_cases"]), (46, 19))
        self.assertEqual((qualification["embedded_entry_rejection_cases"], qualification["invalid_current_entry_dependency_cases"]), (80, 20))
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["negative_control_groups"]), (14, 225))
        self.assertEqual((qualification["expected_tcg_limitation_probes"], qualification["whpx_exception_runs"]), (1, 2))
        self.assertEqual({b["path"] for b in qualification["receipt_bindings"]}, expected_paths)
        self.assertEqual({b["profile"] for b in qualification["receipt_bindings"]}, set(qualification["qualified_profiles"]))
        self.assertFalse(qualification["production_ready"])
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        qualification = current["historical_cycle191_cpu_qualification"]
        self.assertEqual((qualification["cycle"], qualification["source_validation_cycle"]), (185, 185))
        self.assertTrue(qualification["applies_to_current_source"])
        self.assertEqual(qualification["focused_python_tests"], 50)
        self.assertEqual(qualification["superseded_initial_runs"], 6)
        self.assertEqual((qualification["recorded_exit_rejection_cases"],
                          qualification["recorded_coverage_rejection_cases"],
                          qualification["recorded_evidence_rejection_cases"]), (98, 112, 161))
        self.assertEqual(qualification["recorded_evidence_total_rejection_cases"], 371)
        self.assertEqual(qualification["recorded_pair_count"], 7)
        self.assertEqual(qualification["malformed_gate_exception_repairs"], 2)
        self.assertTrue(qualification["recorded_evidence_rejections_exercised_through_runtime_and_gate"])
        self.assertFalse(qualification["positive_receipts_rebound_in_tests"])
        self.assertFalse(qualification["pair_validation_is_freshness_or_authentication"])
        self.assertEqual(qualification["pre_repair_exit_counterexample"]["aggregate_gate_accepted"], 42)
        self.assertFalse(qualification["production_ready"])
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        encoded = json.dumps(qualification, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest().upper(), "621BF34E0ABEF1B47214D831408AE8F5094D3EE119A84166943F73E384A36A18")
        historical_bindings = {b["profile"]: b for b in qualification["receipt_bindings"]}
        qualification = current["historical_cycle196_cpu_qualification"]
        self.assertEqual((qualification["cycle"], qualification["source_validation_cycle"]), (193, 193))
        self.assertEqual(qualification["status"], "single_host_cpu_replay_pass")
        self.assertTrue(qualification["applies_to_current_source"])
        self.assertFalse(qualification["embedded_entry_provenance_replay_pending"])
        self.assertEqual(qualification["readiness_replay_required_profiles"], [])
        self.assertEqual((qualification["focused_python_tests"], qualification["kernel_host_tests_per_qualifier"]), (51, 246))
        self.assertEqual((qualification["fresh_qemu_runs"], qualification["negative_control_groups"]), (14, 225))
        self.assertEqual(qualification["recorded_evidence_total_rejection_cases"], 371)
        self.assertTrue(qualification["recorded_evidence_rejections_exercised_through_runtime_and_gate"])
        self.assertEqual(qualification["trap_control_validator_calls"], 51)
        self.assertTrue(qualification["disabled_trap_validator_detected"])
        self.assertFalse(qualification["positive_receipts_rebound_in_tests"])
        self.assertFalse(qualification["canonical_kernel_changed_this_cycle"])
        self.assertFalse(qualification["current_candidate_full_gate_passed"])
        self.assertFalse(qualification["production_ready"])
        projection = current["historical_cycle193_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["total_checks"]), (193, 14, 27))
        self.assertEqual(projection["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        self.assertEqual(projection["expected_tcg_limitation_probes"], 1)
        self.assertEqual(current["historical_cycle193_closeout_regression"]["tests_passed"], 51)
        closeout = current["historical_cycle193_closeout_regression"]
        self.assertEqual(closeout["initial_metadata_regression"]["tests_failed"], 1)
        self.assertEqual(closeout["corrected_metadata_regression"]["tests_failed"], 0)
        self.assertEqual((closeout["combined_regression"]["tests_run"],
                          closeout["combined_regression"]["tests_passed"],
                          closeout["combined_regression"]["tests_skipped"]), (249, 249, 0))
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        for profile in projection["passing_profiles"]:
            self.assertEqual(getattr(pooleos_release_gate, "check_" + profile)()["ok"],
                             profile in current["current_focused_source_projection"]["passing_profiles"], profile)
        runs = controls = 0
        from tools import pooleos_release_gate as gate

        for binding in qualification["receipt_bindings"]:
            data = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(data)
            self.assertNotEqual(receipt["build"]["kernel_entry"]["product"]["canonical_sha256"], qualification["kernel_sha256"])
            self.assertEqual(receipt["build"]["kernel_entry"]["summary"]["rust_host_tests_total"], 246)
            runs += receipt["summary"]["qemu_run_count"]
            controls += receipt["summary"]["negative_controls_passed"]
            profile = binding["path"].removeprefix("runs/native-kernel-").removesuffix("-readiness.json").replace("-", "_")
            check = getattr(gate, "check_native_kernel_" + profile + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertIn(profile, qualification["qualified_profiles"])
            current_entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False), json.dumps(current_entry, sort_keys=True, allow_nan=False))
            self.assertNotEqual(binding["sha256"], historical_bindings[profile]["sha256"])
            self.assertEqual(historical_bindings[profile]["kernel_host_tests"], 245)
            self.assertEqual(binding["kernel_host_tests"], 246)
            self.assertEqual(binding["fresh_runs"], receipt["summary"]["qemu_run_count"])
            self.assertEqual(binding["negative_controls"], receipt["summary"]["negative_controls_passed"])
            module = importlib.import_module("runtime.native_kernel_" + profile)
            self.assert_retained_receipt_admission(module, receipt)
            if profile == "trap":
                selected = [(scenario["scenario"], run) for scenario in receipt["execution"]["scenarios"] for run in scenario["runs"]]
            else:
                selected = [(None, run) for run in receipt["execution"]["runs"]]
            self.assertEqual(len(selected), binding["fresh_runs"])
            for scenario, run in selected:
                self.assertIn(receipt["build"]["kernel_entry"]["product"]["manifest_fields"]["build_id"], "\n".join(run["markers"]))
                self.assertIn(current_entry["product"]["manifest_fields"]["build_id"], "\n".join(run["markers"]))
                self.assertEqual(run["qemu_exit_code"], 0)
            if profile == "xstate_exception":
                self.assertEqual(receipt["execution"]["acceleration"], "whpx_hardware_accelerated")
                self.assertEqual(receipt["execution"]["tcg_limitation_probe"]["run_count"], 1)
                self.assertFalse(receipt["execution"]["tcg_limitation_probe"]["vector_19_delivered"])
                self.assertEqual(receipt["summary"]["exception_deliveries"], qualification["exception_deliveries_per_run"])
                self.assertEqual(receipt["summary"]["recovered_returns"], qualification["exception_recoveries_per_run"])
                self.assertTrue(receipt["summary"]["machine_code_audit_passed"])
        self.assertEqual((runs, controls), (14, 225))
        pending = current["historical_cycle192_cpu_qualification"]
        self.assertEqual((pending["cycle"], pending["status"]), (192, "source_requalification_required"))
        self.assertEqual(pending["qualified_profiles"], [])
        self.assertEqual(pending["readiness_replay_required_profiles"], qualification["qualified_profiles"])
        self.assertEqual(pending["fresh_qemu_runs"], 0)
        self.assertFalse(pending["applies_to_current_source"])

    def test_native_deferred_repair_preserves_failure_history_and_invalidates_old_image(self) -> None:
        from tools import qualify_native_reclamation_core as core

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = current["historical_cycle202_deferred_transaction_qualification"]
        self.assertEqual(record["cycle"], 197)
        self.assertEqual((record["initial_native_tests"], record["initial_native_passed"], record["initial_native_failed"]), (19, 8, 11))
        self.assertEqual(record["same_tests_after_repair_passed"], 19)
        self.assertEqual(record["final_native_tests_per_profile"], 21)
        self.assertEqual(record["host_optimization_levels"], [0, 3])
        self.assertEqual(record["disabled_native_variants_detected"], 4)
        self.assertTrue(record["kernel_bytes_changed"])
        for path, digest in record["sources"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper(), digest)
        self.assertEqual(record["core_receipt_sha256"], current["historical_cycle202_execution_qualification"]["receipt_sha256"])
        self.assertNotEqual(record["core_receipt_sha256"], hashlib.sha256(core.REPORT.read_bytes()).hexdigest().upper())
        self.assert_reclamation_admission(json.loads(core.REPORT.read_bytes()))
        self.assertEqual(record["kernel_sha256"], current["historical_cycle202_execution_qualification"]["kernel_sha256"])
        self.assertNotEqual(record["kernel_sha256"], core.KERNEL_SHA256)
        before = record["genuine_before_audit"]
        self.assertTrue(before["positive_runtime_and_gate"])
        self.assertEqual((before["cases"], before["runtime_accepted"], before["gate_accepted"]), (121, 114, 47))
        self.assertEqual((before["runtime_exceptions"], before["gate_exceptions"]), (4, 1))
        self.assertFalse(before["admitted_as_final"])
        self.assertFalse(record["recorded_evidence_admission_repaired"])
        self.assertEqual(record["constant_only_control_groups_replaced"], 0)
        self.assertEqual(record["new_kernel_qemu_runs"], 0)
        historical = current["historical_cycle197_source_projection"]
        self.assertEqual((historical["passed_checks"], historical["pending_downstream_native_checks"]), (3, 24))
        projection = current["current_focused_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (2, 25))
        previous = current["historical_cycle196_source_projection"]
        self.assertEqual((previous["passed_checks"], previous["pending_downstream_native_checks"]), (21, 6))
        names = previous["passing_profiles"] + ["native_kernel_" + p + "_readiness" for p in
            ("scheduler_deferred", "scheduler_smp", "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks")]
        self.assertEqual(len(set(names)), 27)
        for name in names:
            self.assertEqual(getattr(pooleos_release_gate, "check_" + name)()["ok"], name in projection["passing_profiles"], name)
        for group, count in (("dependency", 14),):
            pending = current["historical_cycle199_" + group + "_qualification"]
            self.assertEqual(len(pending["readiness_replay_required_profiles"]), count)
            self.assertFalse(pending["applies_to_current_source"])
            self.assertEqual(pending["fresh_qemu_runs"], 0)
        ownership = current["historical_cycle199_ownership_qualification"]
        self.assertEqual(ownership["host_qualification_cycle"], 197)
        self.assertFalse(ownership["live_receipt_source_current"])
        self.assertFalse(ownership["ap_runtime_live_integration_verified"])
        self.assertFalse(ownership["active_root_current_image_replay_complete"])
        self.assertEqual(sum(f["status"] == "open" for f in self.roadmap["implementation_flags"]), 42)
        closeout = current["historical_cycle197_closeout_regression"]
        initial = closeout["initial_metadata_regression"]
        self.assertEqual((initial["tests_run"], initial["tests_passed"], initial["tests_failed"]), (36, 31, 5))
        corrected = closeout["corrected_metadata_regression"]
        self.assertEqual((corrected["tests_run"], corrected["tests_passed"], corrected["tests_failed"], corrected["tests_skipped"]), (44, 44, 0, 0))
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(record["production_ready"])

    def test_symbol_admission_and_boot_replay_are_bound_without_merge_promotion(self) -> None:
        from runtime import native_symbols as symbols
        from tests.test_native_symbol_admission import recorded_receipt_mutations

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = current["historical_cycle202_symbol_admission_qualification"]
        self.assertEqual(record["cycle"], 198)
        before = record["pre_repair_counterexample"]
        self.assertTrue(before["genuine_source_current_positive"])
        self.assertEqual((before["cases"], before["runtime_accepted"], before["aggregate_gate_accepted"]), (646, 494, 467))
        self.assertEqual((before["runtime_exceptions"], before["aggregate_gate_exceptions"]), (6, 11))
        after = record["post_repair_counterexample_replay"]
        self.assertTrue(after["genuine_source_current_positive"])
        self.assertEqual((after["cases"], after["additional_bound_test_source_cases"]), (650, 4))
        for field in ("runtime_accepted", "aggregate_gate_accepted", "runtime_exceptions", "aggregate_gate_exceptions"):
            self.assertEqual(after[field], 0)
        for field in ("runtime_rejected", "aggregate_gate_rejected"):
            self.assertEqual(after[field], 650)
        raw = (ROOT / "runs/native_symbol_readiness.json").read_bytes()
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), record["symbol_receipt_sha256"])
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(symbols, receipt)
        self.assertEqual(sum(1 for _ in recorded_receipt_mutations(receipt)), 650)
        self.assertEqual((record["native_parser_tests"], record["native_control_cases"], record["debug_builds_byte_identical"]), (4, 158, 2))
        self.assertEqual((record["parser_differential_cases"], record["lookup_differential_cases"]), (16384, 16384))
        self.assertEqual(record["rejected_output_preservation_cases"], 2)
        self.assertFalse(record["coherent_forgery_excluded"])
        self.assertFalse(record["recorded_consistency_is_freshness_or_authentication"])
        boot = current["historical_cycle202_boot_chain_qualification"]
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (198, 198))
        self.assertTrue(boot["applies_to_current_source"])
        self.assertEqual(boot["readiness_replay_required_profiles"], [])
        self.assertEqual((boot["fresh_qemu_runs"], boot["kernel_entry_runs"]), (6, 2))
        self.assertEqual((boot["retained_bytes"], boot["manifest_bytes"]), (11952, 2615))
        self.assertTrue(boot["real_image_trust_independently_reconstructed"])
        self.assertFalse(boot["golden_fixture_is_actual_kernel"])
        total_runs = 0
        for binding in boot["receipt_bindings"] + boot["prerequisite_receipt_bindings"]:
            data = (ROOT / binding["path"]).read_bytes()
            if binding in boot["receipt_bindings"]:
                self.assertNotEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            else:
                self.assertEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            runs = json.loads(data).get("execution", {}).get("runs", [])
            self.assertEqual(binding["fresh_runs"], len(runs))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in runs))
            total_runs += len(runs)
            check = getattr(pooleos_release_gate, "check_native_" + binding["profile"] + "_readiness")()
            self.assert_current_gate_projection(check)
        self.assertEqual(total_runs, 6)
        actual = json.loads((ROOT / "runs/native_pooleboot_readiness.json").read_bytes())["summary"]
        for field in ("trust_policy_sha256", "trust_state_sha256"):
            self.assertNotEqual(boot[field], actual[field])
        self.assertNotEqual(boot["inner_set_sha256"], actual["inner_set_retained_set_sha256"])
        for field in ("complete_host_attestation", "second_builder_reproduced", "n5_exit_gate_satisfied",
                      "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(boot[field], field)
        closeout = current["historical_cycle198_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (80, 80, 0))
        self.assertEqual(closeout["failed_initial_transfer"]["attempts"], 1)
        self.assertFalse(closeout["failed_initial_transfer"]["counted_as_final"])
        self.assertEqual(closeout["failed_identity_regression"]["tests_failed"], 1)
        self.assertEqual(closeout["corrected_identity_regression"]["tests_passed"], 3)
        self.assertEqual(closeout["corrected_transfer"]["runs_passed"], 2)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])

    def test_historical_cpu_control_admission_is_bound_without_merge_promotion(self) -> None:
        from tests.test_native_cpu_entry_provenance import control_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle202_cpu_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (199, 199))
        self.assertTrue(record["applies_to_current_source"])
        self.assertEqual(record["readiness_replay_required_profiles"], [])
        self.assertEqual((record["fresh_qemu_runs"], record["superseded_initial_runs"]), (14, 6))
        self.assertEqual((record["negative_control_groups"], record["kernel_host_tests_per_qualifier"]), (225, 246))
        self.assertEqual((record["whpx_exception_runs"], record["expected_tcg_limitation_probes"]), (2, 1))
        self.assertEqual((record["focused_python_tests"], record["aggregate_gate_regression_cases"]), (54, 21))
        self.assertEqual((record["embedded_entry_rejection_cases"], record["invalid_current_entry_dependency_cases"]), (80, 20))
        self.assertEqual(record["recorded_evidence_total_rejection_cases"], 371)
        self.assertEqual(record["recorded_control_total_rejection_cases"], 3398)
        self.assertEqual(sum(record["recorded_control_rejection_cases"].values()), 3398)
        self.assertTrue(record["control_corpus_matches_before_generator"])
        before = record["pre_repair_control_counterexample"]
        self.assertTrue(before["genuine_source_current_positive"])
        self.assertEqual((before["cases"], before["runtime_accepted"], before["aggregate_gate_accepted"]), (1084, 663, 663))
        self.assertEqual((before["runtime_exceptions"], before["aggregate_gate_exceptions"]), (5, 0))
        after = record["post_repair_control_counterexample_replay"]
        self.assertTrue(after["genuine_source_current_positive"])
        self.assertEqual((after["cases"], after["runtime_rejected"], after["aggregate_gate_rejected"]), (1084, 1084, 1084))
        for field in ("runtime_accepted", "aggregate_gate_accepted", "runtime_exceptions", "aggregate_gate_exceptions"):
            self.assertEqual(after[field], 0)
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual(len(record["receipt_bindings"]), 5)
        runs = controls = 0
        for binding in record["receipt_bindings"]:
            data = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(data)
            profile = binding["profile"]
            module = importlib.import_module("runtime.native_kernel_" + profile)
            self.assert_retained_receipt_admission(module, receipt)
            actual = getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")()
            self.assert_current_gate_projection(actual)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertEqual(sum(1 for _ in control_mutations(receipt)), record["recorded_control_rejection_cases"][profile])
            self.assertEqual(binding["fresh_runs"], receipt["summary"]["qemu_run_count"])
            self.assertEqual(binding["negative_controls"], receipt["summary"]["negative_controls_passed"])
            runs += binding["fresh_runs"]
            controls += binding["negative_controls"]
        self.assertEqual((runs, controls), (14, 225))
        projection = gate["historical_cycle199_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (13, 27, 14))
        self.assertEqual(projection["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        closeout = gate["historical_cycle199_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (54, 54, 0))
        self.assertEqual(closeout["initial_gate_pin_regression"]["tests_failed"], 1)
        self.assertTrue(closeout["corrected_gate_pin_verified_in_focused_regression"])
        combined = closeout["combined_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_failed"], combined["tests_skipped"]), (233, 233, 0, 0))
        self.assertTrue(combined["source_unchanged_during_execution"])
        self.assertEqual(closeout["initial_metadata_regression"]["tests_passed"], 46)
        self.assertEqual(closeout["initial_conservation"]["archived_records"], 17)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        for field in ("positive_receipts_rebound_in_tests", "pair_validation_is_freshness_or_authentication",
                      "coherent_forgery_excluded", "canonical_kernel_changed_this_cycle",
                      "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)

    def test_historical_memory_multiprocessor_replay_binds_six_receipts(self) -> None:
        from collections import Counter

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("dependency_qualification", "focused_source_projection", "ownership_qualification", "closeout_regression"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle200_" + suffix]
        record = gate["current_dependency_qualification"]
        expected = ["physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime", "smp_ipi"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (200, 200))
        self.assertEqual(record["qualified_profiles"], expected)
        self.assertEqual(record["newly_qualified_profiles"], expected)
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 8)
        self.assertTrue(record["applies_to_current_source"])
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertEqual((record["fresh_qemu_runs"], record["negative_control_groups"], record["negative_control_cases"]), (12, 421, 1137))
        self.assertEqual(record["superseded_initial_runs"], 0)
        self.assertEqual(record["recorded_evidence_case_total"], 1896)
        self.assertEqual((record["raw_mailbox_rejection_cases"], record["independent_IPI_pin_rejection_cases"], record["memory_gate_rejection_cases"]), (360, 4, 20))
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 65)
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual([b["profile"] for b in record["receipt_bindings"]], expected)
        total = 0
        for binding in record["receipt_bindings"]:
            data = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(data)
            profile = binding["profile"]
            module = importlib.import_module("runtime.native_kernel_" + profile)
            self.assert_retained_receipt_admission(module, receipt)
            check = getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c.get("case_count", 1) for c in receipt["negative_controls"]))
            mutations = importlib.import_module("tests.test_native_kernel_" + profile).recorded_receipt_mutations
            counts = dict(Counter(f for f, _, _ in mutations(receipt)))
            self.assertEqual(counts, binding["recorded_evidence_cases"])
            total += sum(counts.values())
        self.assertEqual(total, 1896)
        ownership = gate["current_ownership_qualification"]
        self.assertEqual((ownership["host_qualification_cycle"], ownership["live_replay_cycle"], ownership["virtual_memory_live_replay_cycle"]), (197, 200, 200))
        self.assertEqual(ownership["fresh_current_cycle_qemu_runs"], 4)
        self.assertEqual(ownership["virtual_memory_receipt_sha256"], record["receipt_bindings"][1]["sha256"])
        self.assertEqual(ownership["smp_receipt_sha256"], record["receipt_bindings"][5]["sha256"])
        for field in ("live_receipt_source_current", "virtual_memory_live_receipt_source_current",
                      "active_root_current_image_replay_complete", "ap_runtime_live_integration_verified"):
            self.assertTrue(ownership[field], field)
        for field in ("task_stack_live_integration_verified", "general_task_CPU_retirement_integration_verified"):
            self.assertFalse(ownership[field], field)
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (19, 27, 8))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-001")
        closeout = gate["current_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (93, 93, 0))
        before = closeout["initial_IPI_admission"]
        self.assertEqual(before["status"], "rejected")
        self.assertTrue(before["runtime_validated"])
        self.assertTrue(before["guest_qualifier_passed"])
        self.assertEqual(before["failed_guest_runs"], 0)
        self.assertFalse(before["guest_evidence_rewritten_or_rerun"])
        self.assertEqual(before["candidate_sha256"], closeout["corrected_IPI_admission"]["same_candidate_sha256"])
        initial = closeout["initial_metadata_regression"]
        self.assertEqual((initial["tests_run"], initial["tests_passed"], initial["tests_failed"]), (47, 41, 6))
        for field, expected_count in (("corrected_metadata_regression", 47), ("combined_scoped_regression", 327)):
            result = closeout[field]
            self.assertEqual(result["status"], "pass")
            self.assertEqual((result["tests_run"], result["tests_passed"], result["tests_failed"], result["tests_skipped"]),
                             (expected_count, expected_count, 0, 0))
        self.assertTrue(closeout["combined_scoped_regression"]["executed_before_result_recording"])
        conservation = closeout["initial_conservation"]
        self.assertEqual(conservation["status"], "pass")
        self.assertEqual((conservation["archived_parent_current_records"], conservation["architecture_bindings"],
                          conservation["test_inventory"], conservation["selected_checks"]), (17, 326, 1071, "19/27"))
        self.assertFalse(gate["historical_cycle202_ipi_mailbox_oracle_gap"]["current_kernel_live_replay_pending"])
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        for field in ("positive_receipts_rebound_in_tests", "pair_validation_is_freshness_or_authentication",
                      "canonical_kernel_changed_this_cycle", "control_execution_complete",
                      "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)

    def test_historical_cycle201_replay_preserves_retained_runs_and_binds_two_receipts(self) -> None:
        from tests.test_native_kernel_scheduler import recorded_receipt_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        previous = gate["historical_cycle200_dependency_qualification"]
        current = gate["historical_cycle201_dependency_qualification"]
        self.assertEqual((current["cycle"], current["source_validation_cycle"]), (201, 201))
        self.assertEqual(current["newly_qualified_profiles"], ["scheduler", "scheduler_preempt"])
        self.assertEqual(current["qualified_profiles"], previous["qualified_profiles"] + current["newly_qualified_profiles"])
        self.assertEqual(current["receipt_bindings"][:6], previous["receipt_bindings"])
        self.assertEqual(current["readiness_replay_required_profiles"], [p for p in previous["readiness_replay_required_profiles"] if p not in current["newly_qualified_profiles"]])
        self.assertEqual((current["fresh_qemu_runs"], current["negative_control_groups"], current["negative_control_cases"]), (4, 53, 341))
        self.assertEqual((current["generic_recorded_evidence_cases"], current["additional_preemption_control_receipt_corruptions"], current["recorded_evidence_case_total"]), (427, 26, 453))
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        total = 0
        for binding in current["receipt_bindings"][6:]:
            data = (ROOT / binding["path"]).read_bytes()
            receipt = json.loads(data)
            self.assertEqual(binding["sha256"], {
                "scheduler": "FF5A23F5D19B5D009BC5D9823CBB29D0B74343684D5AE4D051345D3AF0A5D7E8",
                "scheduler_preempt": "00F89E715A57EB75F734C8C4E26E5867614E061EF1BD4DF3575FDA439F4D0750",
            }[binding["profile"]])
            self.assertNotEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            name = "scheduler_preemption" if binding["profile"] == "scheduler_preempt" else binding["profile"]
            check = getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c["case_count"] for c in receipt["negative_controls"]))
            cases = dict(Counter(f for f, _, _ in recorded_receipt_mutations(receipt)))
            self.assertEqual(binding["recorded_evidence_cases"], cases)
            total += sum(cases.values())
            if binding["profile"] == "scheduler_preempt":
                self.assertEqual(16 + len(receipt["build"]["native_control_probe"]) + 2, 26)
                self.assertEqual(receipt["build"]["native_control_probe"]["hostile_cases_total"], 50)
        self.assertEqual(total, 427)
        self.assertNotEqual(current["kernel_sha256"], entry["product"]["canonical_sha256"])
        audit = gate["historical_cycle202_preemption_control_execution_audit"]
        self.assertEqual((audit["cycle"], audit["original_repair_cycle"], audit["source_validation_cycle"]), (201, 196, 201))
        self.assertEqual(audit["receipt_sha256"], current["receipt_bindings"][-1]["sha256"])
        self.assertTrue(audit["current_receipt_admitted"])
        self.assertFalse(audit["current_kernel_live_replay_pending"])
        self.assertEqual((audit["repaired_groups"], audit["disabled_native_variants_detected"], audit["aggregate_unproven_groups_at_least"]), (9, 7, 65))
        self.assertEqual(gate["historical_cycle202_ownership_qualification"], gate["historical_cycle200_ownership_qualification"])
        projection = gate["historical_cycle201_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (201, 21, 27, 6))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-DEFERRED-001")
        self.assertEqual(gate["historical_cycle201_ipi_mailbox_oracle_gap"]["remaining_affected_profiles"], 6)
        closeout = gate["historical_cycle201_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_failed"], closeout["tests_skipped"]), (31, 31, 0, 0))
        initial = closeout["initial_metadata_regression"]
        self.assertEqual((initial["tests_run"], initial["tests_passed"], initial["tests_failed"]), (48, 45, 3))
        self.assertEqual(closeout["intermediate_metadata_regression"]["tests_failed"], 1)
        for name, expected in (("repaired_metadata_regression", 48), ("combined_scoped_regression", 128)):
            result = closeout[name]
            self.assertEqual(result["status"], "pass")
            self.assertEqual((result["tests_run"], result["tests_passed"], result["tests_failed"], result["tests_skipped"]),
                             (expected, expected, 0, 0))
        self.assertTrue(closeout["combined_scoped_regression"]["executed_before_result_recording"])
        self.assertEqual(closeout["initial_conservation"]["archived_parent_current_records"], 17)
        self.assertEqual(closeout["initial_conservation"]["architecture_bindings"], 327)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        for field in ("all_fourteen_profiles_current", "positive_receipts_rebound_in_tests",
                      "pair_validation_is_freshness_or_authentication", "canonical_kernel_changed_this_cycle",
                      "control_execution_complete", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(current[field], field)

    def test_historical_deferred_admission_controls_and_replay_are_source_bound(self) -> None:
        from runtime import native_kernel_scheduler_deferred as deferred
        from tests.test_native_deferred_controls import recorded_deferred_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        previous = gate["historical_cycle201_dependency_qualification"]
        current = gate["historical_cycle202_dependency_qualification"]
        self.assertEqual((current["cycle"], current["source_validation_cycle"]), (202, 202))
        self.assertEqual(current["receipt_bindings"][:-1], previous["receipt_bindings"])
        self.assertEqual(current["qualified_profiles"], previous["qualified_profiles"] + ["scheduler_deferred"])
        self.assertEqual(len(current["readiness_replay_required_profiles"]), 5)
        self.assertEqual((current["fresh_qemu_runs"], current["negative_control_groups"], current["negative_control_cases"]), (2, 30, 254))
        self.assertEqual(current["diagnostic_pre_repair_runs_not_admitted"], 2)
        self.assertEqual(current["recorded_evidence_case_total"], 315)
        binding = current["receipt_bindings"][-1]
        raw = (ROOT / binding["path"]).read_bytes()
        self.assertEqual(binding["sha256"], "5DEB81D744D08EC14895631699B64A9573F57587F6D3520476A7A57E01262F3A")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(deferred, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_deferred_readiness())
        self.assertEqual(len(list(recorded_deferred_mutations(receipt))), 273)
        self.assertEqual(receipt["negative_controls"], deferred.expected_controls())
        self.assertEqual(receipt["build"]["native_control_probe"]["verified_cases_total"], 50)
        self.assertEqual(sum(c["case_count"] for c in receipt["build"]["audit_controls"]["controls"]), 10)
        audit = gate["historical_cycle202_deferred_control_qualification"]
        self.assertEqual((audit["repaired_groups"], audit["disabled_native_variants_detected"], audit["aggregate_unproven_groups_at_least"]), (14, 12, 51))
        before, after = audit["genuine_before_audit"], audit["after_audit"]
        self.assertEqual((before["runtime_accepted"], before["gate_accepted"], before["runtime_exceptions"], before["gate_exceptions"]), (258, 164, 4, 19))
        self.assertFalse(before["admitted_as_final"])
        self.assertEqual((after["runtime_rejected"], after["gate_rejected"], after["runtime_exceptions"], after["gate_exceptions"]), (273, 273, 0, 0))
        self.assertEqual(after["additional_control_receipt_cases_rejected_by_both"], 42)
        self.assertFalse(audit["initial_control_test"]["native_runtime_failure"])
        self.assertEqual(audit["repaired_control_test"]["tests_passed"], 5)
        projection = gate["historical_cycle202_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (22, 5))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-SMP-001")
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)
        for field in ("all_fourteen_profiles_current", "positive_receipts_rebound_in_tests",
                      "pair_validation_is_freshness_or_authentication", "canonical_kernel_changed_this_cycle",
                      "control_execution_complete", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(current[field], field)

    def test_historical_cycle215_smp_transactions_bind_native_repair_and_invalidate_prior_image(self) -> None:
        from runtime import native_kernel_entry as entry
        from tools import qualify_native_reclamation_core as core

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle215_smp_transaction_qualification"]
        self.assertEqual(record["cycle"], 203)
        self.assertEqual(record["requirements"], ["ADD-N12-SCHED-SMP-001", "ADD-N36-RECEIPT-COVERAGE-001"])
        self.assertEqual((record["initial_native_tests"], record["initial_native_passed"], record["initial_native_failed"]), (18, 11, 7))
        self.assertEqual(record["same_tests_after_repair_passed"], 18)
        self.assertEqual(record["final_native_tests_per_profile"], 19)
        self.assertEqual(record["host_optimization_levels"], [0, 3])
        self.assertEqual(record["disabled_native_variants_detected"], 9)
        self.assertEqual(record["combined_transaction_methods_passed"], 4)
        self.assertTrue(record["kernel_bytes_changed"])
        for path, digest in record["sources"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper(), digest)
        entry_raw = (ROOT / entry.READINESS_RELATIVE).read_bytes()
        entry_receipt = json.loads(entry_raw)
        self.assert_retained_receipt_admission(entry, entry_receipt)
        self.assertNotEqual(hashlib.sha256(entry_raw).hexdigest().upper(), record["entry_receipt_sha256"])
        self.assertEqual(record["entry_receipt_sha256"], gate["historical_cycle203_entry_provenance_qualification"]["entry_receipt_sha256"])
        self.assert_reclamation_admission(json.loads(core.REPORT.read_bytes()))
        self.assertNotEqual(hashlib.sha256(core.REPORT.read_bytes()).hexdigest().upper(), record["core_receipt_sha256"])
        self.assertEqual(record["core_receipt_sha256"], gate["historical_cycle203_execution_qualification"]["receipt_sha256"])
        self.assertNotEqual(record["kernel_sha256"], core.KERNEL_SHA256)
        self.assertNotEqual(record["kernel_sha256"], entry_receipt["product"]["canonical_sha256"])
        self.assertNotEqual(record["kernel_sha256"], gate["historical_cycle202_entry_provenance_qualification"]["canonical_sha256"])
        projection = gate["historical_cycle203_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (2, 25))
        self.assertEqual(projection["next_dependency_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        for group, count in (("boot_chain", 6), ("cpu", 5), ("dependency", 14)):
            pending = gate["historical_cycle203_" + group + "_qualification"]
            self.assertFalse(pending["applies_to_current_source"])
            self.assertEqual(len(pending["readiness_replay_required_profiles"]), count)
            self.assertEqual(pending["receipt_bindings"], [])
            self.assertEqual(pending["qualified_profiles"], [])
            self.assertEqual(pending["fresh_qemu_runs"], 0)
            self.assertEqual(pending["kernel_sha256"], record["kernel_sha256"])
        ownership = gate["historical_cycle215_ownership_qualification"]
        self.assertTrue(ownership["live_receipt_source_current"])
        self.assertTrue(ownership["virtual_memory_live_receipt_source_current"])
        self.assertFalse(gate["historical_cycle215_ipi_mailbox_oracle_gap"]["current_kernel_live_replay_pending"])
        for field in ("remote_ack_synthesized_or_accepted_by_preflight", "recorded_evidence_admission_repaired",
                      "cross_cpu_atomicity_proved", "production_ready"):
            self.assertIs(record[field], False)
        self.assertEqual((record["constant_only_control_groups_replaced"], record["new_kernel_qemu_runs"]), (0, 0))
        self.assertEqual((record["remaining_SMP_control_groups"], record["remaining_global_control_groups_at_least"]), (16, 51))
        self.assertEqual(len(record["entry_attempts_rejected"]), 2)
        self.assertEqual(gate["historical_cycle203_closeout_regression"]["initial_focused"]["tests_failed"], 1)
        self.assertFalse(gate["historical_cycle215_closeout_regression"]["merge_qualified"])

    def test_historical_boot_replay_preserves_six_receipts_without_promotion(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        boot = gate["historical_cycle208_boot_chain_qualification"]
        projection = gate["historical_cycle204_source_projection"]
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (204, 204))
        self.assertTrue(boot["applies_to_current_source"])
        self.assertEqual(boot["readiness_replay_required_profiles"], [])
        self.assertEqual((projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (8, 27, 19))
        self.assertEqual(projection["next_dependency_move_id"], "N7-TRAP-001")
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        self.assertEqual([b["profile"] for b in boot["receipt_bindings"]], boot["qualified_profiles"])
        total_runs = 0
        for binding in boot["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            total_runs += binding["fresh_runs"]
            check = getattr(pooleos_release_gate, "check_native_" + binding["profile"] + "_readiness")()
            self.assert_current_gate_projection(check)
        self.assertEqual(boot, gate["historical_cycle204_boot_chain_qualification"])
        self.assertEqual([b["sha256"] for b in boot["receipt_bindings"]], [
            "C9FF1E5347A831045E46BCF8DCF2CD77D25497D68BD48B177B80162026901C99",
            "56E724804B70A4B530D7410D651DF1E88773273C501EE65A7E7DF8D4A659B8B5",
            "AC8B3954741AB689BD07B5875949B2437B63664CD47E09E055C04A65E99701B7",
            "48A507A2059BC400EA5A2A9F37626874A267870BF946A34E3B0069213787CCDE",
            "2A1230B151E1494B3C6C9EFF712A7529194B5F27180A1CE5D882D1B98733450E",
            "95AEEF7FF80A960096D8FC236017C9789ACD7B96DF085E73F857EEADB047AB85",
        ])
        self.assertEqual((total_runs, boot["fresh_qemu_runs"], boot["kernel_entry_runs"]), (6, 6, 2))
        actual = json.loads((ROOT / "runs/native_pooleboot_readiness.json").read_bytes())["summary"]
        for field in ("trust_policy_sha256", "trust_state_sha256"):
            self.assertNotEqual(boot[field], actual[field])
        self.assertNotEqual(boot["inner_set_sha256"], actual["inner_set_retained_set_sha256"])
        self.assertEqual(boot["kernel_sha256"], gate["historical_cycle208_entry_provenance_qualification"]["canonical_sha256"])
        self.assertNotEqual(boot["kernel_sha256"], gate["current_entry_provenance_qualification"]["canonical_sha256"])
        self.assertEqual((boot["independent_previous_identity_rejection_cases"], boot["focused_python_tests"]), (20, 81))
        self.assertTrue(boot["entry_and_core_receipts_unchanged"])
        self.assertEqual(boot["terminal"], "unsigned-denial-halt")
        self.assertEqual((boot["authority_created"], boot["state_writes"], boot["firmware_calls_after_exit"]), (0, 0, 0))
        for field in ("kernel_bytes_changed_this_cycle", "complete_host_attestation", "second_builder_reproduced",
                      "n5_exit_gate_satisfied", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(boot[field], field)
        symbols = gate["historical_cycle209_symbol_admission_qualification"]
        self.assertEqual(symbols["symbol_receipt_sha256"], boot["receipt_bindings"][0]["sha256"])
        self.assertEqual((symbols["runtime_rejected"], symbols["aggregate_gate_rejected"]), (650, 650))
        self.assertFalse(symbols["pre_repair_audit_reexecuted_this_cycle"])
        closeout = gate["historical_cycle204_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (81, 81, 0))
        self.assertEqual(len(closeout["failed_symbol_attempts"]), 2)
        self.assertFalse(closeout["failed_receipts_admitted"])
        self.assertFalse(closeout["merge_qualified"])
        combined = closeout["combined_scoped_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_failed"], combined["tests_skipped"]), (188, 188, 0, 0))
        self.assertTrue(combined["executed_before_result_recording"])
        self.assertEqual(closeout["initial_metadata"]["tests_passed"], 43)
        self.assertEqual(closeout["initial_conservation"]["archived_parent_current_records"], 19)
        self.assertEqual(closeout["initial_conservation"]["architecture_bindings"], 345)
        for group, count in (("cpu", 5), ("dependency", 14)):
            pending = gate["historical_cycle204_" + group + "_qualification"]
            self.assertFalse(pending["applies_to_current_source"])
            self.assertEqual(len(pending["readiness_replay_required_profiles"]), count)
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)

    def test_historical_cpu_replay_preserves_runs_and_admission_history(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle208_cpu_qualification"]
        projection = gate["historical_cycle205_source_projection"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (205, 205))
        self.assertTrue(record["applies_to_current_source"])
        self.assertEqual(record["readiness_replay_required_profiles"], [])
        self.assertEqual((projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (13, 27, 14))
        self.assertEqual(projection["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual(len(record["receipt_bindings"]), 5)
        expected_hashes = (
            "6CCBE079A996F2257D9605047331DD7FFCF51130F97B4F173E50A68911208674",
            "9EA8402056FB8A83F37AA8A541043B79F55A9AE656AA4B442D6E94AA7FEE8014",
            "48095CE52295F2C8512DD2CBAA7581FE4C1F3DA2EEA5194843299901D35CC551",
            "5EEA8DA366205957DF6C735D54A46A6B80EC7264D700F80A5F7D775B02EEAAE0",
            "2C4F4AD1A98C3626182DCFEDB1D9C2664BD34E9090905E5C4D96A054CCD11CD7",
        )
        for binding, digest in zip(record["receipt_bindings"], expected_hashes, strict=True):
            self.assertEqual(binding["sha256"], digest)
            self.assertNotEqual(hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest().upper(), digest)
        self.assertEqual(sum(b["fresh_runs"] for b in record["receipt_bindings"]), 14)
        self.assertEqual(sum(b["negative_controls"] for b in record["receipt_bindings"]), 225)
        self.assertEqual(record["recorded_pair_count"], 7)
        self.assertEqual([record["recorded_" + family + "_rejection_cases"] for family in
                          ("exit", "coverage", "evidence")], [98, 112, 161])
        self.assertEqual(sum(record["recorded_control_rejection_cases"].values()), 3398)
        self.assertEqual((record["aggregate_gate_regression_cases"], record["new_previous_image_and_wrong_typed_pin_rejection_cases"]), (26, 5))
        self.assertEqual((record["whpx_exception_runs"], record["expected_tcg_limitation_probes"]), (2, 1))
        self.assertEqual(record["trap_control_validator_calls"], 51)
        self.assertTrue(record["disabled_trap_validator_detected"])
        self.assertTrue(record["entry_and_core_receipts_unchanged"])
        for field in ("pre_repair_audit_reexecuted_this_cycle", "positive_receipts_rebound_in_tests",
                      "pair_validation_is_freshness_or_authentication", "coherent_forgery_excluded",
                      "canonical_kernel_changed_this_cycle", "second_builder_reproduced", "target_hardware_qualified",
                      "n7_exit_gate_satisfied", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)
        historical = gate[record["historical_admission_repair_record"]]
        self.assertEqual(historical["cycle"], 199)
        self.assertEqual(historical["pre_repair_control_counterexample"]["aggregate_gate_accepted"], 663)
        self.assertEqual(gate["historical_cycle208_boot_chain_qualification"], gate["historical_cycle204_boot_chain_qualification"])
        closeout = gate["historical_cycle205_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (54, 54, 0))
        self.assertTrue(closeout["obsolete_trap_aggregate_pin_observed_rejecting_current_receipt"])
        combined = closeout["combined_scoped_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_skipped"]), (242, 242, 0))
        self.assertTrue(combined["includes_focused_and_metadata_tests"])
        self.assertTrue(combined["source_unchanged_during_execution"])
        self.assertEqual(closeout["initial_metadata_regression"]["tests_passed"], 52)
        self.assertEqual(closeout["initial_conservation"]["archived_parent_current_records"], 19)
        self.assertEqual(closeout["initial_conservation"]["architecture_source_bindings"], 346)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(gate["historical_cycle205_dependency_qualification"]["applies_to_current_source"])
        self.assertEqual(len(gate["historical_cycle205_dependency_qualification"]["readiness_replay_required_profiles"]), 14)
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)

    def test_historical_memory_replay_preserves_six_receipts_and_partial_ownership(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle206_dependency_qualification"]
        self.assertEqual(hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper(),
                         "07E1D69B67EE3EA667DE07EC247798FA05DD887297C7BA5FF3C1B655873B1624")
        projection = gate["historical_cycle206_source_projection"]
        expected = ("physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime", "smp_ipi")
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (206, 206))
        self.assertEqual(record["qualified_profiles"], list(expected))
        self.assertEqual((projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (19, 27, 8))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-001")
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 8)
        self.assertTrue(record["applies_to_current_source"])
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        runs = controls = cases = mutations = 0
        self.assertEqual(len(record["receipt_bindings"]), 6)
        for profile, binding in zip(expected, record["receipt_bindings"], strict=True):
            self.assertEqual(binding["profile"], profile)
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + profile)
            self.assert_retained_receipt_admission(module, receipt)
            check = getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertNotEqual(receipt["build"]["kernel_entry"]["product"]["canonical_sha256"], record["kernel_sha256"])
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c.get("case_count", 1) for c in receipt["negative_controls"]))
            corpus = importlib.import_module("tests.test_native_kernel_" + profile).recorded_receipt_mutations
            counts = dict(Counter(f for f, _, _ in corpus(receipt)))
            self.assertEqual(counts, binding["recorded_evidence_cases"])
            self.assertEqual(binding["kernel_host_tests"], 246)
            runs += binding["fresh_runs"]
            controls += binding["negative_controls"]
            cases += binding["hostile_cases"]
            mutations += sum(counts.values())
        self.assertEqual((runs, controls, cases, mutations), (12, 421, 1137, 1896))
        self.assertEqual((record["raw_mailbox_rejection_cases"], record["independent_IPI_pin_rejection_cases"],
                          record["memory_gate_rejection_cases"]), (360, 7, 20))
        self.assertTrue(record["disabled_PMM_parser_and_memory_oracle_detected"])
        self.assertEqual(record["PMM_marker_validator_calls"], 189)
        ownership = gate["historical_cycle208_ownership_qualification"]
        self.assertEqual((ownership["host_qualification_cycle"], ownership["live_replay_cycle"]), (203, 206))
        self.assertEqual(ownership["virtual_memory_receipt_sha256"], record["receipt_bindings"][1]["sha256"])
        self.assertEqual(ownership["smp_receipt_sha256"], record["receipt_bindings"][5]["sha256"])
        for field in ("live_receipt_source_current", "virtual_memory_live_receipt_source_current",
                      "active_root_current_image_replay_complete", "ap_runtime_live_integration_verified"):
            self.assertTrue(ownership[field], field)
        for field in ("task_stack_live_integration_verified", "general_task_CPU_retirement_integration_verified"):
            self.assertFalse(ownership[field], field)
        self.assertEqual(gate["historical_cycle208_cpu_qualification"], gate["historical_cycle205_cpu_qualification"])
        self.assertEqual(gate["historical_cycle208_boot_chain_qualification"], gate["historical_cycle205_boot_chain_qualification"])
        closeout = gate["historical_cycle206_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (93, 93, 0))
        self.assertEqual(closeout["initial_IPI_admission"]["candidate_sha256"], closeout["corrected_IPI_admission"]["same_candidate_sha256"])
        self.assertEqual(closeout["initial_IPI_admission"]["failed_guest_runs"], 0)
        self.assertFalse(closeout["initial_IPI_admission"]["guest_evidence_rewritten_or_rerun"])
        self.assertEqual(closeout["initial_metadata_regression"]["tests_failed"], 3)
        self.assertEqual(closeout["corrected_metadata_regression"]["tests_passed"], 53)
        combined = closeout["combined_scoped_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_skipped"]), (283, 283, 0))
        self.assertTrue(combined["source_unchanged_during_execution"])
        self.assertTrue(combined["includes_focused_and_metadata_tests"])
        self.assertEqual(closeout["initial_conservation"]["archived_parent_current_records"], 19)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(gate["historical_cycle215_ipi_mailbox_oracle_gap"]["current_kernel_live_replay_pending"])
        self.assertEqual(gate["historical_cycle215_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        for field in ("all_fourteen_profiles_current", "positive_receipts_rebound_in_tests",
                      "pair_validation_is_freshness_or_authentication", "canonical_kernel_changed_this_cycle",
                      "control_execution_complete", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)

    def test_historical_scheduler_replay_preserves_memory_and_binds_fresh_kernel_evidence(self) -> None:
        from tests.test_native_kernel_scheduler import recorded_receipt_mutations
        from tests.test_native_deferred_controls import recorded_deferred_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record, previous = gate["historical_cycle207_dependency_qualification"], gate["historical_cycle206_dependency_qualification"]
        self.assertEqual(hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper(),
                         "87E727DBA61E74FF6F79814201951F1DAF5796698D373F1ED81D83BDF7F9B94B")
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (207, 207))
        self.assertEqual(record["newly_qualified_profiles"], ["scheduler", "scheduler_preempt", "scheduler_deferred"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + record["newly_qualified_profiles"])
        self.assertEqual(record["receipt_bindings"][:6], previous["receipt_bindings"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_smp", "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"])
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        counts = [0, 0, 0, 0]
        for binding in record["receipt_bindings"][6:]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            name = "scheduler_preemption" if binding["profile"] == "scheduler_preempt" else binding["profile"]
            check = getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertNotEqual(receipt["build"]["kernel_entry"]["product"]["canonical_sha256"], record["kernel_sha256"])
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c["case_count"] for c in receipt["negative_controls"]))
            corpus = recorded_deferred_mutations if binding["profile"] == "scheduler_deferred" else recorded_receipt_mutations
            mutations = dict(Counter(f for f, _, _ in corpus(receipt)))
            self.assertEqual(binding["recorded_evidence_cases"], mutations)
            self.assertEqual(binding["kernel_host_tests"], 246)
            for index, value in enumerate((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"], sum(mutations.values()))):
                counts[index] += value
        self.assertEqual(counts, [6, 83, 595, 700])
        self.assertEqual((record["executed_rejection_cases"], record["native_boundary_cases"]), (545, 50))
        self.assertEqual(record["recorded_evidence_case_total"], 700 + 26 + 42)
        self.assertEqual(record["independent_deferred_linked_identity_cases"], 11)
        self.assertEqual((record["disabled_preemption_native_variants_detected"], record["disabled_deferred_native_variants_detected"]), (7, 12))
        projection = gate["historical_cycle207_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["total_checks"], projection["pending_downstream_native_checks"]), (22, 27, 5))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-SMP-001")
        for group in ("boot_chain", "cpu", "ownership"):
            self.assertEqual(gate["historical_cycle208_" + group + "_qualification"], gate["historical_cycle206_" + group + "_qualification"])
        for key, binding in (("historical_cycle208_preemption_control_execution_audit", record["receipt_bindings"][-2]),
                             ("historical_cycle208_deferred_control_qualification", record["receipt_bindings"][-1])):
            self.assertEqual(gate[key]["receipt_sha256"], binding["sha256"])
            self.assertTrue(gate[key]["current_receipt_admitted"])
            self.assertFalse(gate[key]["current_kernel_live_replay_pending"])
            self.assertFalse(gate[key]["original_failure_audits_reexecuted_this_cycle"])
        closeout = gate["historical_cycle207_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (47, 47, 0))
        self.assertEqual(closeout["initial_deferred_admission"]["candidate_sha256"], closeout["corrected_deferred_admission"]["same_candidate_sha256"])
        self.assertEqual(closeout["initial_deferred_admission"]["failed_guest_runs"], 0)
        self.assertFalse(closeout["initial_deferred_admission"]["guest_evidence_rewritten_or_rerun"])
        self.assertEqual(closeout["initial_metadata_regression"]["tests_failed"], 4)
        self.assertEqual(closeout["intermediate_metadata_regression"]["tests_failed"], 2)
        self.assertEqual(closeout["repaired_metadata_regression"]["tests_passed"], 54)
        combined = closeout["combined_scoped_regression"]
        self.assertEqual((combined["tests_run"], combined["tests_passed"], combined["tests_skipped"]), (166, 166, 0))
        self.assertTrue(combined["source_unchanged_during_execution"])
        self.assertTrue(combined["includes_focused_and_metadata_tests"])
        self.assertEqual(closeout["initial_conservation"]["archived_parent_current_records"], 19)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertEqual(gate["historical_cycle215_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        for field in ("all_fourteen_profiles_current", "positive_receipts_rebound_in_tests",
                      "pair_validation_is_freshness_or_authentication", "canonical_kernel_changed_this_cycle",
                      "control_execution_complete", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)

    def test_historical_smp_admission_controls_and_replay_are_bound(self) -> None:
        from runtime import native_kernel_scheduler_smp as smp
        from tests.test_native_deferred_controls import recorded_deferred_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record, previous = gate["historical_cycle208_dependency_qualification"], gate["historical_cycle207_dependency_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (208, 208))
        self.assertEqual(record["newly_qualified_profiles"], ["scheduler_smp"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + ["scheduler_smp"])
        self.assertEqual(record["receipt_bindings"][:-1], previous["receipt_bindings"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / binding["path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual(binding["sha256"], "31C084B5C7AEA66051FD8E36785C4CE8E2C8FF5FEA2701023CCBDE41BC2540F0")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        self.assert_retained_receipt_admission(smp, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_smp_readiness())
        self.assertEqual(len(list(recorded_deferred_mutations(receipt))), 279)
        self.assertEqual(receipt["negative_controls"], smp.expected_controls())
        self.assertEqual(sum(c["case_count"] for c in receipt["negative_controls"]), 303)
        self.assertEqual(receipt["build"]["native_control_probe"]["verified_cases_total"], 59)
        self.assertEqual(sum(c["case_count"] for c in receipt["build"]["audit_controls"]["controls"]), 51)
        self.assertEqual((record["fresh_qemu_runs"], record["superseded_initial_runs"]), (2, 4))
        self.assertEqual((record["executed_rejection_cases"], record["native_boundary_cases"]), (244, 59))
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_aggregate_cases"]), (326, 8))
        audit = gate["historical_cycle208_smp_control_qualification"]
        self.assertEqual((audit["repaired_groups"], audit["disabled_native_variants_detected"]), (16, 13))
        self.assertEqual(audit["receipt_sha256"], binding["sha256"])
        before, after = audit["genuine_before_audit"], audit["after_audit"]
        self.assertEqual((before["runtime_accepted"], before["gate_accepted"], before["runtime_exceptions"], before["gate_exceptions"]), (264, 168, 4, 18))
        self.assertFalse(before["admitted_as_final"])
        self.assertEqual((after["runtime_rejected"], after["gate_rejected"], after["runtime_exceptions"], after["gate_exceptions"]), (279, 279, 0, 0))
        self.assertFalse(audit["source_mutations_are_hardware_fault_injection"])
        self.assertFalse(audit["recorded_consistency_is_authentication"])
        projection = gate["historical_cycle208_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (23, 4))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-AP-WORKERS-001")
        for group in ("boot_chain", "cpu", "ownership"):
            self.assertEqual(gate["historical_cycle208_" + group + "_qualification"], gate["historical_cycle207_" + group + "_qualification"])
        self.assertEqual(gate["historical_cycle213_smp_transaction_qualification"]["latest_live_receipt_sha256"], binding["sha256"])
        closeout = gate["historical_cycle208_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (18, 18, 0))
        self.assertEqual(len(closeout["initial_control_test_failures"]), 2)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)
        for field in ("all_fourteen_profiles_current", "positive_receipts_rebound_in_tests",
                      "pair_validation_is_freshness_or_authentication", "canonical_kernel_changed_this_cycle",
                      "control_execution_complete", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)

    def test_historical_ap_worker_transactions_preserve_failure_and_changed_image_boundaries(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle209_ap_worker_transaction_qualification"]
        self.assertEqual(record["cycle"], 209)
        self.assertEqual(record["move_id"], "N12-SCHED-AP-WORKERS-001")
        self.assertEqual((record["initial_native_tests_per_profile"], record["initial_native_passed"], record["initial_native_failed"]), (28, 12, 16))
        self.assertEqual((record["final_native_tests_per_profile"], record["new_private_state_tests"], record["disabled_native_variants_detected"]), (30, 20, 15))
        self.assertEqual(record["host_optimization_levels"], [0, 3])
        self.assertEqual(len(record["preserved_rejected_attempts"]), 6)
        for path, digest in record["sources"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper(), digest)
        for field, path in (("entry_receipt_sha256", "runs/native_kernel_entry_readiness.json"),
                            ("core_receipt_sha256", "runs/native-kernel-reclamation-core-readiness.json")):
            self.assertNotEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper(), record[field])
        self.assertEqual(record["entry_receipt_sha256"], gate["historical_cycle209_entry_provenance_qualification"]["entry_receipt_sha256"])
        self.assertEqual(record["core_receipt_sha256"], gate["historical_cycle209_execution_qualification"]["receipt_sha256"])
        self.assertEqual(record["kernel_sha256"], gate["historical_cycle209_entry_provenance_qualification"]["canonical_sha256"])
        self.assertNotEqual(record["kernel_sha256"], gate["historical_cycle215_entry_provenance_qualification"]["canonical_sha256"])
        self.assertNotEqual(record["kernel_sha256"], gate["historical_cycle208_entry_provenance_qualification"]["canonical_sha256"])
        self.assertEqual(gate["historical_cycle215_entry_provenance_qualification"]["source_binding_count"], 76)
        self.assertEqual((record["remaining_AP_worker_control_groups"], record["remaining_global_control_groups_at_least"]), (18, 35))
        self.assertEqual((record["constant_only_control_groups_replaced"], record["new_kernel_qemu_runs"]), (0, 0))
        for field in ("remote_ack_synthesized_or_accepted_by_preflight", "recorded_evidence_admission_repaired",
                      "cross_cpu_atomicity_proved", "production_ready"):
            self.assertFalse(record[field], field)
        projection = gate["historical_cycle209_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (3, 24))
        self.assertEqual(projection["next_dependency_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        for name in projection["passing_profiles"]:
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_" + name)())
        for group in ("boot_chain", "cpu", "dependency"):
            self.assertFalse(gate["historical_cycle209_" + group + "_qualification"]["applies_to_current_source"])
        for name in ("smp", "deferred"):
            self.assertFalse(gate["historical_cycle215_" + name + "_control_qualification"]["current_kernel_live_replay_pending"])
            self.assertTrue(gate["historical_cycle215_" + name + "_control_qualification"]["current_receipt_admitted"])
        self.assertFalse(gate["historical_cycle215_smp_transaction_qualification"]["current_kernel_live_replay_pending"])
        self.assertEqual(next(f for f in self.roadmap["implementation_flags"] if f["id"] == "FLAG-N12-SCHED-AP-WORKERS-001")["status"], "open")
        self.assertFalse(gate["historical_cycle215_closeout_regression"]["merge_qualified"])

    def test_historical_cycle215_guard_repair_and_boot_receipts_are_bound_without_promotion(self) -> None:
        from runtime import native_kernel_map as kmap

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        repair = gate["historical_cycle215_retained_map_qualification"]
        boot = gate["historical_cycle215_boot_chain_qualification"]
        self.assertEqual((repair["cycle"], repair["move_id"]), (210, "N5-KMAP-001"))
        self.assertEqual((kmap.KERNEL_PAGE_CAPACITY, kmap.STACK_FIRST_PAGE, kmap.HANDOFF_FIRST_PAGE), (192, 193, 230))
        self.assertEqual((repair["kernel_pages"], repair["rejected_pages"]), (148, 193))
        self.assertEqual(repair["accepted_boundary_pages"], [148, 192])
        self.assertTrue(repair["rejected_before_table_writes"])
        self.assertLessEqual(kmap.HANDOFF_FIRST_PAGE + kmap.HANDOFF_PAGE_COUNT, 512)
        self.assertEqual(repair["kernel_sha256"], gate["historical_cycle215_entry_provenance_qualification"]["canonical_sha256"])
        for field, path in (("entry_receipt_sha256", "runs/native_kernel_entry_readiness.json"),
                            ("core_receipt_sha256", "runs/native-kernel-reclamation-core-readiness.json")):
            self.assertNotEqual(repair[field], hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper())
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (210, 210))
        self.assertTrue(boot["applies_to_current_source"])
        self.assertTrue(boot["kernel_bytes_changed_this_cycle"])
        self.assertTrue(boot["entry_and_core_freshly_qualified"])
        self.assertFalse(boot["entry_and_core_receipts_unchanged"])
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        runs = 0
        for binding in boot["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            executions = receipt.get("execution", {}).get("runs", [])
            self.assertEqual(len(executions), binding["fresh_runs"])
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in executions))
            self.assertEqual(len(receipt["negative_controls"]), binding["negative_controls"])
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_" + binding["profile"] + "_readiness")())
            runs += len(executions)
        self.assertEqual((runs, boot["fresh_qemu_runs"], boot["kernel_entry_runs"]), (6, 6, 2))
        self.assertEqual((boot["authority_created"], boot["state_writes"], boot["firmware_calls_after_exit"]), (0, 0, 0))
        self.assertEqual((boot["loader_rust_tests"], boot["focused_python_tests"], boot["independent_previous_identity_rejection_cases"]), (332, 97, 25))
        self.assertEqual(boot["terminal"], "unsigned-denial-halt")
        for field in ("second_builder_reproduced", "complete_host_attestation", "n5_exit_gate_satisfied",
                      "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(boot[field])
        projection = gate["historical_cycle215_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (24, 3))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-SMP-PREEMPT-001")
        self.assertEqual(gate["historical_cycle215_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        self.assertTrue(gate["historical_cycle215_ap_worker_transaction_qualification"]["current_receipt_admitted"])
        self.assertFalse(gate["historical_cycle215_closeout_regression"]["merge_qualified"])

    def test_historical_cycle215_cpu_replay_and_nested_admission_are_bound_without_promotion(self) -> None:
        from tests.test_native_cpu_entry_provenance import recorded_pairs, pair_mutations, control_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle215_cpu_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (211, 211))
        self.assertTrue(record["applies_to_current_source"])
        self.assertEqual(record["readiness_replay_required_profiles"], [])
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual(len(record["receipt_bindings"]), 5)
        runs = controls = pairs = 0
        pair_counts = {"exit": 0, "coverage": 0, "evidence": 0}
        for binding in record["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + binding["profile"] + "_readiness")())
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertEqual(binding["fresh_runs"], receipt["summary"]["qemu_run_count"])
            self.assertEqual(binding["negative_controls"], receipt["summary"]["negative_controls_passed"])
            self.assertEqual(sum(1 for _ in control_mutations(receipt)), record["recorded_control_rejection_cases"][binding["profile"]])
            for _, pair, _, _ in recorded_pairs(module, receipt):
                pairs += 1
                self.assertTrue(all(run["qemu_exit_code"] == 0 for run in pair["runs"]))
                for family in pair_counts:
                    pair_counts[family] += sum(1 for _ in pair_mutations(pair, family))
            runs += binding["fresh_runs"]
            controls += binding["negative_controls"]
        self.assertEqual((runs, controls, pairs), (14, 225, 7))
        self.assertEqual(pair_counts, {"exit": 98, "coverage": 112, "evidence": 161})
        self.assertEqual(sum(record["recorded_control_rejection_cases"].values()), 3398)
        self.assertEqual((record["aggregate_gate_regression_cases"], record["focused_python_tests"]), (32, 55))
        audit = record["nested_build_admission_audit"]
        self.assertEqual((audit["before_rejected"], audit["before_exceptions"], audit["before_accepted"]), (68, 12, 0))
        self.assertEqual((audit["after_rejected"], audit["after_exceptions"], audit["after_accepted"]), (80, 0, 0))
        self.assertTrue(audit["isolated_float_relocation_accepted_before"])
        self.assertFalse(audit["isolated_float_relocation_accepted_after"])
        self.assertTrue(audit["schema_and_component_bypassed_only_for_isolated_pin_case"])
        projection = gate["historical_cycle211_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (211, 13, 14))
        self.assertEqual(gate["historical_cycle215_boot_chain_qualification"], gate["historical_cycle210_boot_chain_qualification"])
        self.assertEqual(gate["historical_cycle215_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        for field in ("canonical_kernel_changed_this_cycle", "second_builder_reproduced", "target_hardware_qualified",
                      "n7_exit_gate_satisfied", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(record[field], field)
        closeout = gate["historical_cycle211_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (55, 55, 0))
        self.assertEqual(closeout["initial_combined_scoped_regression"]["tests_failed"], 1)
        self.assertFalse(closeout["initial_combined_scoped_regression"]["admitted_as_passing_suite"])
        self.assertEqual(closeout["corrected_metadata_regression"]["tests_passed"], 58)
        self.assertFalse(closeout["corrected_metadata_regression"]["full_combined_suite_rerun_after_metadata_only_fix"])
        self.assertFalse(closeout["merge_qualified"])

    def test_historical_cycle215_memory_replay_binds_six_receipts_and_limits_ownership(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle212_dependency_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (212, 212))
        expected = ("physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap", "smp_percpu_runtime", "smp_ipi")
        self.assertEqual(record["qualified_profiles"], list(expected))
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 8)
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        runs = controls = cases = mutations = 0
        for profile, binding in zip(expected, record["receipt_bindings"], strict=True):
            self.assertEqual(binding["profile"], profile)
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + profile)
            self.assert_retained_receipt_admission(module, receipt)
            check = getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            for run in receipt["execution"]["runs"]:
                self.assertEqual(run["qemu_exit_code"], 0)
                self.assertIn(entry["product"]["manifest_fields"]["build_id"], "\n".join(run["markers"]))
                self.assertIn(receipt["build"]["kernel_entry"]["product"]["manifest_fields"]["build_id"], "\n".join(run["markers"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c.get("case_count", 1) for c in receipt["negative_controls"]))
            corpus = importlib.import_module("tests.test_native_kernel_" + profile).recorded_receipt_mutations
            counts = dict(Counter(f for f, _, _ in corpus(receipt)))
            self.assertEqual(counts, binding["recorded_evidence_cases"])
            runs += binding["fresh_runs"]
            controls += binding["negative_controls"]
            cases += binding["hostile_cases"]
            mutations += sum(counts.values())
        self.assertEqual((runs, controls, cases, mutations), (12, 421, 1137, 1896))
        self.assertEqual((record["raw_mailbox_rejection_cases"], record["independent_IPI_pin_rejection_cases"],
                          record["memory_gate_rejection_cases"]), (360, 8, 23))
        projection = gate["historical_cycle212_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (212, 19, 8))
        ownership = gate["historical_cycle215_ownership_qualification"]
        self.assertEqual((ownership["host_qualification_cycle"], ownership["live_replay_cycle"],
                          ownership["virtual_memory_live_replay_cycle"], ownership["boot_artifact_replay_cycle"]), (210, 212, 212, 210))
        self.assertEqual(ownership["fresh_current_cycle_qemu_runs"], 4)
        self.assertEqual(ownership["virtual_memory_receipt_sha256"], record["receipt_bindings"][1]["sha256"])
        self.assertEqual(ownership["smp_receipt_sha256"], record["receipt_bindings"][5]["sha256"])
        for field in ("live_receipt_source_current", "virtual_memory_live_receipt_source_current",
                      "active_root_current_image_replay_complete", "ap_runtime_live_integration_verified"):
            self.assertTrue(ownership[field], field)
        for field in ("task_stack_live_integration_verified", "general_task_CPU_retirement_integration_verified",
                      "current_boot_artifact_set_replay_pending", "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(ownership[field], field)
        self.assertEqual(gate["historical_cycle215_cpu_qualification"], gate["historical_cycle211_cpu_qualification"])
        self.assertEqual(gate["historical_cycle215_boot_chain_qualification"], gate["historical_cycle211_boot_chain_qualification"])
        self.assertEqual(gate["historical_cycle215_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        closeout = gate["historical_cycle212_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (93, 93, 0))
        self.assertEqual(sum(f["reconciled_pins"] for f in closeout["initial_admission_failures"]), 10)
        self.assertFalse(closeout["guest_evidence_rewritten_or_rerun_for_pin_repair"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["control_execution_complete"])
        self.assertFalse(record["production_ready"])

    def test_historical_cycle215_scheduler_replay_binds_receipts_and_isolated_pin_repair(self) -> None:
        from tests.test_native_kernel_scheduler import recorded_receipt_mutations
        from tests.test_native_deferred_controls import recorded_deferred_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle213_dependency_qualification"]
        previous = gate["historical_cycle212_dependency_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (213, 213))
        self.assertEqual(record["receipt_bindings"][:6], previous["receipt_bindings"])
        self.assertEqual(record["newly_qualified_profiles"], ["scheduler", "scheduler_preempt", "scheduler_deferred"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + record["newly_qualified_profiles"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_smp", "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"])
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        counts = [0, 0, 0, 0]
        for binding in record["receipt_bindings"][6:]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            name = "scheduler_preemption" if binding["profile"] == "scheduler_preempt" else binding["profile"]
            check = getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")()
            self.assert_current_gate_projection(check)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c["case_count"] for c in receipt["negative_controls"]))
            corpus = recorded_deferred_mutations if binding["profile"] == "scheduler_deferred" else recorded_receipt_mutations
            mutations = dict(Counter(f for f, _, _ in corpus(receipt)))
            self.assertEqual(binding["recorded_evidence_cases"], mutations)
            for index, value in enumerate((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"], sum(mutations.values()))):
                counts[index] += value
        self.assertEqual(counts, [6, 83, 595, 700])
        self.assertEqual(record["recorded_evidence_case_total"], 700 + 26 + 42)
        self.assertEqual(record["independent_deferred_linked_identity_cases"], 14)
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 35)
        projection = gate["historical_cycle213_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (213, 22, 5))
        for group in ("boot_chain", "cpu", "ownership"):
            self.assertEqual(gate["historical_cycle215_" + group + "_qualification"], gate["historical_cycle212_" + group + "_qualification"])
        for key, binding in (("historical_cycle215_preemption_control_execution_audit", record["receipt_bindings"][-2]),
                             ("historical_cycle215_deferred_control_qualification", record["receipt_bindings"][-1])):
            self.assertEqual(gate[key]["receipt_sha256"], binding["sha256"])
            self.assertEqual(gate[key]["source_validation_cycle"], 213)
            self.assertTrue(gate[key]["current_receipt_admitted"])
            self.assertFalse(gate[key]["current_kernel_live_replay_pending"])
            self.assertFalse(gate[key]["original_failure_audits_reexecuted_this_cycle"])
        self.assertEqual(gate["historical_cycle215_deferred_transaction_qualification"]["latest_live_replay_cycle"], 213)
        closeout = gate["historical_cycle213_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (47, 47, 0))
        self.assertEqual(closeout["initial_deferred_admission"]["candidate_sha256"], closeout["corrected_deferred_admission"]["same_candidate_sha256"])
        self.assertFalse(closeout["initial_deferred_admission"]["guest_evidence_rewritten_or_rerun"])
        audit = closeout["isolated_relocation_type_audit"]
        self.assertTrue(audit["isolated_pin_accepted_before"])
        for field in ("isolated_pin_accepted_after", "full_gate_accepted_before", "full_gate_accepted_after"):
            self.assertFalse(audit[field], field)
        self.assertTrue(audit["component_bypassed_only_for_isolated_diagnostic"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(closeout["canonical_full_replay_performed"])
        for field in ("all_fourteen_profiles_current", "control_execution_complete", "production_ready"):
            self.assertFalse(record[field], field)

    def test_historical_smp_replay_binds_current_image_and_preserves_failed_attempts(self) -> None:
        from runtime import native_kernel_scheduler_smp as smp
        from tests.test_native_deferred_controls import recorded_deferred_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record, previous = gate["historical_cycle214_dependency_qualification"], gate["historical_cycle213_dependency_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (214, 214))
        self.assertEqual(record["receipt_bindings"][:-1], previous["receipt_bindings"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + ["scheduler_smp"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / binding["path"]).read_bytes()
        self.assertEqual(binding["sha256"], "6A7EDCA3DCC42389D55170584C975D9DEAEBA8DBE790A21E13A7E243298FE527")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(smp, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_smp_readiness())
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                         json.dumps(entry, sort_keys=True, allow_nan=False))
        self.assertNotEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual(len(receipt["execution"]["runs"]), 2)
        self.assertTrue(all(run["qemu_exit_code"] == 0 for run in receipt["execution"]["runs"]))
        self.assertEqual((len(receipt["negative_controls"]), sum(c["case_count"] for c in receipt["negative_controls"])), (32, 303))
        self.assertEqual(len(list(recorded_deferred_mutations(receipt))), 279)
        self.assertEqual(receipt["build"]["native_control_probe"]["verified_cases_total"], 59)
        self.assertEqual(sum(c["case_count"] for c in receipt["build"]["audit_controls"]["controls"]), 51)
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_aggregate_cases"]), (326, 11))
        self.assertEqual((record["fresh_qemu_runs"], record["superseded_initial_runs"]), (2, 0))
        projection = gate["historical_cycle214_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (214, 23, 4))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-AP-WORKERS-001")
        for group in ("boot_chain", "cpu", "ownership", "deferred_control", "deferred_transaction"):
            self.assertEqual(gate["historical_cycle215_" + group + "_qualification"], gate["historical_cycle213_" + group + "_qualification"])
        audit = gate["historical_cycle215_smp_control_qualification"]
        self.assertEqual((audit["source_validation_cycle"], audit["original_repair_cycle"], audit["measured_relocation_count"]), (214, 208, 1323))
        self.assertEqual(audit["receipt_sha256"], binding["sha256"])
        self.assertTrue(audit["current_receipt_admitted"])
        self.assertFalse(audit["current_kernel_live_replay_pending"])
        self.assertFalse(audit["original_failure_audits_reexecuted_this_cycle"])
        self.assertEqual(audit["genuine_before_audit"], gate["historical_cycle213_smp_control_qualification"]["genuine_before_audit"])
        transaction = gate["historical_cycle215_smp_transaction_qualification"]
        self.assertEqual((transaction["cycle"], transaction["latest_live_replay_cycle"]), (203, 214))
        self.assertEqual(transaction["latest_live_receipt_sha256"], binding["sha256"])
        self.assertNotEqual(transaction["kernel_sha256"], transaction["latest_live_kernel_sha256"])
        closeout = gate["historical_cycle214_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (19, 19, 0))
        self.assertEqual(closeout["initial_SMP_admission"]["candidate_sha256"], closeout["corrected_SMP_admission"]["same_candidate_sha256"])
        self.assertEqual(closeout["initial_focused_regression"]["tests_failed"], 5)
        self.assertTrue(closeout["source_binding_workflow_failure"]["original_bound_test_restored_byte_exactly"])
        self.assertFalse(closeout["source_binding_workflow_failure"]["positive_receipt_rebound_or_validation_bypassed"])
        self.assertFalse(closeout["corrected_SMP_admission"]["guest_evidence_rewritten_or_rerun"])
        self.assertTrue(closeout["isolated_relocation_type_audit"]["isolated_pin_accepted_before"])
        self.assertFalse(closeout["isolated_relocation_type_audit"]["isolated_pin_accepted_after"])
        self.assertFalse(closeout["isolated_relocation_type_audit"]["full_gate_accepted_before"])
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 35)
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertFalse(record["production_ready"])

    def test_ap_worker_admission_controls_preserve_history_and_merge_boundaries(self) -> None:
        from runtime import native_kernel_scheduler_ap_workers as workers
        from tests.test_native_deferred_controls import recorded_deferred_mutations

        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle215_dependency_qualification"]
        previous = gate["historical_cycle214_dependency_qualification"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (215, 215))
        self.assertEqual(record["receipt_bindings"][:-1], previous["receipt_bindings"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + ["scheduler_ap_workers"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_smp_preempt", "atomics", "locks"])
        binding = record["receipt_bindings"][-1]
        self.assertEqual(binding["path"], workers.READINESS_RELATIVE)
        raw = (ROOT / binding["path"]).read_bytes()
        self.assertEqual(binding["sha256"], "30B59312AF639F6E0B55391FCB33474A9B999E351BCC414E5A8B0384B53A82B4")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(workers, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_ap_workers_readiness())
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                         json.dumps(entry, sort_keys=True, allow_nan=False))
        self.assertEqual(record["kernel_sha256"], previous["kernel_sha256"])
        self.assertEqual((len(receipt["negative_controls"]), sum(c["case_count"] for c in receipt["negative_controls"])), (34, 325))
        self.assertEqual(len(list(recorded_deferred_mutations(receipt))), 294)
        self.assertEqual(receipt["build"]["native_control_probe"]["verified_cases_total"], 59)
        self.assertEqual(sum(c["case_count"] for c in receipt["build"]["audit_controls"]["controls"]), 58)
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_aggregate_cases"]), (343, 10))
        self.assertEqual((record["fresh_qemu_runs"], record["superseded_initial_runs"]), (2, 2))
        projection = gate["historical_cycle215_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (215, 24, 3))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-SMP-PREEMPT-001")
        audit = gate["historical_cycle215_ap_worker_control_qualification"]
        self.assertEqual(audit["receipt_sha256"], binding["sha256"])
        self.assertEqual((audit["constant_only_groups_replaced"], audit["native_groups"], audit["source_groups"]), (18, 14, 4))
        self.assertTrue(audit["current_receipt_admitted"])
        self.assertFalse(audit["current_kernel_live_replay_pending"])
        before, after = audit["diagnostic_baseline"], audit["after_audit"]
        self.assertEqual((before["runtime_corruptions_accepted"], before["gate_corruptions_accepted_after_pin_repair"]), (279, 178))
        self.assertEqual((before["runtime_exceptions"], before["gate_exceptions"]), (4, 19))
        self.assertFalse(before["qualified_after_repair"])
        self.assertEqual((after["case_count"], after["runtime_corruptions_accepted"], after["gate_corruptions_accepted"],
                          after["runtime_exceptions"], after["gate_exceptions"]), (294, 0, 0, 0, 0))
        transaction = gate["historical_cycle215_ap_worker_transaction_qualification"]
        self.assertEqual((transaction["cycle"], transaction["latest_live_replay_cycle"]), (209, 215))
        self.assertNotEqual(transaction["kernel_sha256"], transaction["latest_live_kernel_sha256"])
        self.assertEqual(transaction["latest_live_receipt_sha256"], binding["sha256"])
        self.assertEqual(transaction["remaining_AP_worker_control_groups"], 0)
        self.assertEqual(gate["historical_cycle215_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        for name in ("boot_chain", "cpu", "ownership", "deferred_control", "smp_control", "smp_transaction"):
            self.assertEqual(gate["historical_cycle215_" + name + "_qualification"], gate["historical_cycle214_" + name + "_qualification"])
        closeout = gate["historical_cycle215_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (19, 19, 0))
        self.assertEqual(closeout["initial_control_harness"]["failure_records"], 4)
        self.assertFalse(closeout["initial_control_harness"]["admitted_as_pass"])
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])
        for key in ("pair_validation_is_freshness_or_authentication", "positive_receipt_rebound_in_tests",
                    "native_kernel_changed", "full_hardware_fault_injection", "production_ready"):
            self.assertFalse(audit[key], key)
        self.assertEqual(next(f for f in self.roadmap["implementation_flags"]
                              if f["id"] == "FLAG-N12-SCHED-AP-WORKERS-001")["status"], "open")

    def test_native_smp_preemption_transactions_require_changed_image_replay(self) -> None:
        from runtime import native_kernel_entry as entry
        from tools import qualify_native_reclamation_core as core

        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("focused_source_projection", "boot_chain_qualification", "cpu_qualification",
                     "dependency_qualification", "closeout_regression"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle216_" + suffix]
        record = gate["historical_cycle221_smp_preempt_transaction_qualification"]
        self.assertEqual(record["cycle"], 216)
        self.assertEqual(record["initial_failures_by_optimization"], {"0": 8, "3": 7})
        self.assertEqual((record["final_native_tests_per_profile"], record["disabled_native_variants_detected"],
                          record["redundant_guard_positive_controls"]), (27, 14, 1))
        self.assertEqual(record["host_optimization_levels"], [0, 3])
        self.assertEqual(record["maximum_remote_operations_per_tick"], 5)
        self.assertEqual(record["timer_epoch_increments_per_tick"], 1)
        self.assertTrue(record["completion_preview_uses_discarded_copy"])
        self.assertFalse(record["hypothetical_ack_confers_live_authority"])
        self.assertTrue(record["live_ack_still_required"])
        for name, digest in record["sources"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper(), digest)
        for name, field in ((entry.READINESS_RELATIVE, "entry_receipt_sha256"),
                            (core.REPORT.relative_to(ROOT), "core_receipt_sha256")):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper(), record[field])
        self.assert_retained_receipt_admission(entry, json.loads((ROOT / entry.READINESS_RELATIVE).read_bytes()))
        self.assert_reclamation_admission(json.loads(core.REPORT.read_bytes()))
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (216, 3, 24))
        self.assertEqual(projection["next_dependency_move_id"], "N5-SYMBOLS-SEMANTICS-001")
        for group in ("boot_chain", "cpu", "dependency"):
            current = gate["current_" + group + "_qualification"]
            self.assertFalse(current["applies_to_current_source"])
            self.assertEqual(current["receipt_bindings"], [])
            self.assertEqual(current["fresh_qemu_runs"], 0)
            self.assertTrue(current["readiness_replay_required_profiles"])
        old = gate["historical_cycle215_dependency_qualification"]
        self.assertEqual(len(old["qualified_profiles"]), 11)
        self.assertEqual(old["readiness_replay_required_profiles"], ["scheduler_smp_preempt", "atomics", "locks"])
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)
        self.assertEqual(record["new_kernel_qemu_runs"], 0)
        self.assertFalse(record["cross_cpu_atomicity_proved"])
        self.assertFalse(record["recorded_evidence_admission_repaired"])
        self.assertFalse(record["production_ready"])
        self.assertEqual(next(f["status"] for f in self.roadmap["implementation_flags"]
                              if f["id"] == "FLAG-N12-SCHED-SMP-PREEMPT-001"), "open")
        closeout = gate["current_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (43, 43, 0))
        self.assertTrue(closeout["excluded_live_test_remains_a_merge_blocker"])
        self.assertFalse(closeout["canonical_full_replay_performed"])
        self.assertFalse(closeout["merge_qualified"])

    def test_cycle217_boot_replay_binds_fresh_evidence_without_promoting_downstream(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        projection = current["historical_cycle217_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (217, 8, 19))
        self.assertEqual(projection["next_dependency_move_id"], "N7-TRAP-001")
        previous = current["historical_cycle216_source_projection"]
        self.assertEqual((previous["cycle"], previous["passed_checks"], previous["pending_downstream_native_checks"]), (216, 3, 24))
        boot = current["historical_cycle217_boot_chain_qualification"]
        self.assertEqual((boot["cycle"], boot["source_validation_cycle"]), (217, 217))
        self.assertTrue(boot["applies_to_current_source"])
        self.assertEqual(boot["readiness_replay_required_profiles"], [])
        self.assertEqual((boot["fresh_qemu_runs"], boot["kernel_entry_runs"], boot["focused_python_tests"]), (6, 2, 97))
        self.assertEqual((boot["map_probe_kernel_pages"], boot["map_reserved_kernel_pages"]), (149, 192))
        self.assertEqual(boot["kernel_sha256"], "FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1")
        self.assertEqual(len(boot["receipt_bindings"]), 6)
        for binding in boot["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            actual = hashlib.sha256(raw).hexdigest().upper()
            if binding["profile"] in ("kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"):
                self.assertNotEqual(actual, binding["sha256"])
            else:
                self.assertEqual(actual, binding["sha256"])
            check = getattr(pooleos_release_gate, "check_native_" + binding["profile"] + "_readiness")()
            self.assert_current_gate_projection(check)
            receipt = json.loads(raw)
            self.assertEqual(binding["fresh_runs"], len(receipt.get("execution", {}).get("runs", [])))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
        for group, count in (("cpu", 5), ("dependency", 14)):
            pending = current["historical_cycle217_" + group + "_qualification"]
            self.assertFalse(pending["applies_to_current_source"])
            self.assertEqual(len(pending["readiness_replay_required_profiles"]), count)
        closeout = current["historical_cycle217_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (97, 97, 0))
        self.assertTrue(closeout["previously_failing_live_transfer_test_now_passes"])
        self.assertEqual(closeout["known_failure_exclusions"], [])
        self.assertEqual(len(closeout["preserved_failures"]), 2)
        for field in ("canonical_full_replay_performed", "merge_qualified", "production_ready"):
            self.assertFalse(closeout[field])
        self.assertEqual(current["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)
        for field in ("kernel_bytes_changed_this_cycle", "second_builder_reproduced", "production_ready"):
            self.assertFalse(boot[field])
        self.assertEqual(boot["terminal"], "unsigned-denial-halt")
        for field in ("authority_created", "state_writes", "firmware_calls_after_exit"):
            self.assertEqual(boot[field], 0)

    def test_cycle218_capture_and_cpu_replay_bind_only_final_evidence(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("cpu_qualification", "boot_chain_qualification", "focused_source_projection", "dependency_qualification", "ownership_qualification", "closeout_regression"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle218_" + suffix]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (218, 13, 14))
        self.assertEqual((projection["final_receipt_fresh_qemu_runs"], projection["kernel_entry_runs"]), (20, 16))
        self.assertEqual(projection["next_dependency_move_id"], "N9-PMM-ACPI-CONSUMER-001")
        cpu = gate["current_cpu_qualification"]
        capture = gate["current_capture_qualification"]
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(cpu["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual((cpu["cycle"], cpu["source_validation_cycle"], cpu["fresh_qemu_runs"]), (218, 218, 14))
        self.assertEqual(cpu["readiness_replay_required_profiles"], [])
        self.assertTrue(cpu["applies_to_current_source"])
        self.assertEqual((cpu["focused_python_tests"], cpu["aggregate_gate_regression_cases"], cpu["nested_build_regression_cases"]), (64, 33, 80))
        self.assertEqual((cpu["superseded_initial_runs"], cpu["negative_control_groups"]), (8, 225))
        self.assertEqual(cpu["recorded_control_total_rejection_cases"], 3398)
        self.assertEqual(cpu["recorded_evidence_total_rejection_cases"], 371)
        self.assertNotIn("nested_build_admission_audit", cpu)
        bindings = cpu["receipt_bindings"] + capture["boot_receipt_bindings"]
        self.assertEqual((len(bindings), sum(b["fresh_runs"] for b in bindings)), (8, 20))
        for binding in bindings:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assert_replayed_receipt_binding(binding, raw)
            if binding in cpu["receipt_bindings"]:
                receipt = json.loads(raw)
                self.assertEqual(receipt["build"]["kernel_entry"], entry)
                module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
                self.assert_retained_receipt_admission(module, receipt)
        for name in projection["passing_profiles"]:
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_" + name)())
        self.assertEqual((capture["unit_tests"], capture["before_failed_tests"], capture["after_failed_tests"]), (9, 4, 0))
        self.assertTrue(capture["capture_after_validated_terminal"])
        self.assertFalse(capture["delays_added"])
        self.assertFalse(capture["frame_equality_relaxed"])
        self.assertFalse(capture["initial_trap_failure"]["exact_original_pixel_cause_proved"])
        self.assertFalse(capture["initial_trap_failure"]["original_differing_frames_retained"])
        self.assertFalse(capture["diagnostic_pre_repair_replay"]["admitted_after_repair"])
        self.assertFalse(capture["shared_helper_transitive_binding_audit_complete"])
        self.assertEqual(capture["early_vs_terminal_changed_pixel_bounds"], [0, 0, 299, 23])
        trap = json.loads((ROOT / "runs/native-kernel-trap-readiness.json").read_bytes())
        for scenario in trap["execution"]["scenarios"]:
            for run in scenario["runs"]:
                self.assertEqual(capture["terminal_frame_sha256"], run["screenshot"]["sha256"])
        boot = gate["current_boot_chain_qualification"]
        self.assertEqual(boot["cycle"], 218)
        self.assertEqual(boot["fresh_profiles"], ["kernel_load", "pooleboot", "kernel_transfer"])
        self.assertEqual(boot["retained_component_execution_cycle"], 217)
        self.assertNotIn("focused_python_tests", boot)
        for binding in boot["receipt_bindings"]:
            self.assert_replayed_receipt_binding(binding, (ROOT / binding["path"]).read_bytes())
        self.assertFalse(gate["current_dependency_qualification"]["applies_to_current_source"])
        self.assertEqual(len(gate["current_dependency_qualification"]["readiness_replay_required_profiles"]), 14)
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)
        self.assertFalse(gate["current_ownership_qualification"]["ap_runtime_live_integration_verified"])
        self.assertFalse(gate["current_closeout_regression"]["merge_qualified"])
        self.assertFalse(cpu["production_ready"])
        self.assertFalse(capture["production_ready"])

    def test_cycle219_memory_replay_preserves_history_and_bounds_ownership(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("cpu_qualification", "boot_chain_qualification", "ownership_qualification", "capture_qualification", "focused_source_projection", "dependency_qualification", "closeout_regression"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle219_" + suffix]
        record = gate["current_dependency_qualification"]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (219, 19, 8))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-001")
        self.assertEqual((record["cycle"], record["source_validation_cycle"], record["fresh_qemu_runs"]), (219, 219, 12))
        self.assertEqual((record["negative_control_groups"], record["negative_control_cases"]), (421, 1137))
        self.assertEqual((record["independent_IPI_pin_rejection_cases"], record["memory_gate_rejection_cases"]), (9, 29))
        self.assertEqual(record["recorded_evidence_case_total"], 1896)
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 17)
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        self.assertEqual(len(record["receipt_bindings"]), 6)
        for binding in record["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assert_replayed_receipt_binding(binding, raw)
            receipt = json.loads(raw)
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + binding["profile"] + "_readiness")())
            self.assertEqual((binding["fresh_runs"], len(receipt["execution"]["runs"])), (2, 2))
        for name in ("cpu_qualification", "boot_chain_qualification", "capture_qualification"):
            self.assertEqual(gate["current_" + name], gate["historical_cycle218_" + name])
        ownership = gate["current_ownership_qualification"]
        self.assertEqual((ownership["cycle"], ownership["host_qualification_cycle"], ownership["live_replay_cycle"]), (219, 216, 219))
        self.assertEqual((ownership["fresh_current_cycle_qemu_runs"], ownership["boot_artifact_replay_cycle"]), (4, 218))
        for key in ("live_receipt_source_current", "virtual_memory_live_receipt_source_current",
                    "active_root_current_image_replay_complete", "ap_runtime_live_integration_verified"):
            self.assertTrue(ownership[key], key)
        for key in ("task_stack_live_integration_verified", "general_task_CPU_retirement_integration_verified", "production_ready"):
            self.assertFalse(ownership[key], key)
        closeout = gate["current_closeout_regression"]
        self.assertEqual((closeout["tests_run"], closeout["tests_passed"], closeout["tests_skipped"]), (93, 93, 0))
        self.assertEqual(sum(item["reconciled_pins"] for item in closeout["initial_admission_failures"]), 10)
        self.assertEqual(closeout["failed_guest_runs"], 0)
        self.assertFalse(closeout["guest_evidence_rewritten_or_rerun_for_pin_repair"])
        self.assertEqual((closeout["initial_metadata_regression"]["tests_passed"],
                          closeout["initial_metadata_regression"]["tests_failed"]), (56, 10))
        self.assertEqual((closeout["corrected_metadata_regression"]["tests_passed"],
                          closeout["corrected_metadata_regression"]["tests_failed"],
                          closeout["corrected_metadata_regression"]["tests_skipped"]), (66, 0, 0))
        self.assertEqual((closeout["initial_conservation"]["archived_records"],
                          closeout["initial_conservation"]["architecture_bindings"]), (25, 372))
        self.assertFalse(closeout["merge_qualified"])
        self.assertEqual(len(record["readiness_replay_required_profiles"]), 8)
        for profile in record["readiness_replay_required_profiles"]:
            name = "scheduler_preemption" if profile == "scheduler_preempt" else profile
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")())
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["production_ready"])

    def test_cycle220_scheduler_replay_preserves_memory_and_current_image_boundaries(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("cpu_qualification", "boot_chain_qualification", "ownership_qualification", "capture_qualification", "focused_source_projection", "dependency_qualification", "closeout_regression"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle220_" + suffix]
        record = gate["current_dependency_qualification"]
        previous = gate["historical_cycle219_dependency_qualification"]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (220, 220))
        self.assertEqual((projection["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (220, 22, 5))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-SMP-001")
        self.assertEqual(record["receipt_bindings"][:6], previous["receipt_bindings"])
        self.assertEqual(record["newly_qualified_profiles"], ["scheduler", "scheduler_preempt", "scheduler_deferred"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + record["newly_qualified_profiles"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_smp", "scheduler_ap_workers", "scheduler_smp_preempt", "atomics", "locks"])
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        counts = [0, 0, 0]
        for binding in record["receipt_bindings"][6:]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assert_replayed_receipt_binding(binding, raw)
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            name = "scheduler_preemption" if binding["profile"] == "scheduler_preempt" else binding["profile"]
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + name + "_readiness")())
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in receipt["execution"]["runs"]))
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c["case_count"] for c in receipt["negative_controls"]))
            for index, field in enumerate(("fresh_runs", "negative_controls", "hostile_cases")):
                counts[index] += binding[field]
        self.assertEqual(counts, [6, 83, 595])
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_deferred_linked_identity_cases"]), (768, 16))
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 17)
        for name in ("cpu_qualification", "boot_chain_qualification", "ownership_qualification", "capture_qualification"):
            self.assertEqual(gate["current_" + name], gate["historical_cycle219_" + name])
        for key, binding in (("current_preemption_control_execution_audit", record["receipt_bindings"][-2]),
                             ("current_deferred_control_qualification", record["receipt_bindings"][-1])):
            self.assertEqual(gate[key]["receipt_sha256"], binding["sha256"])
            self.assertEqual(gate[key]["source_validation_cycle"], 220)
            self.assertTrue(gate[key]["current_receipt_admitted"])
            self.assertFalse(gate[key]["current_kernel_live_replay_pending"])
            self.assertEqual(gate[key]["aggregate_unproven_groups_at_least"], 17)
        self.assertEqual(gate["current_deferred_transaction_qualification"]["latest_live_replay_cycle"], 220)
        closeout = gate["current_closeout_regression"]
        self.assertEqual((closeout["tests_passed"], closeout["tests_failed"], closeout["tests_skipped"]), (47, 0, 0))
        self.assertEqual(closeout["initial_deferred_admission"]["candidate_sha256"], closeout["corrected_deferred_admission"]["same_candidate_sha256"])
        self.assertEqual(closeout["corrected_deferred_admission"]["independently_measured_relocation_count"], 1326)
        self.assertFalse(closeout["initial_deferred_admission"]["guest_evidence_rewritten_or_rerun"])
        self.assertEqual((closeout["metadata_regression"]["tests_passed"],
                          closeout["metadata_regression"]["tests_failed"],
                          closeout["metadata_regression"]["tests_skipped"]), (67, 0, 0))
        self.assertEqual((closeout["initial_conservation"]["archived_records"],
                          closeout["initial_conservation"]["architecture_bindings"]), (25, 373))
        self.assertFalse(closeout["merge_qualified"])
        for profile in record["readiness_replay_required_profiles"]:
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")())
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["production_ready"])

    def test_cycle221_SMP_workers_replay_binds_current_image_and_preserves_history(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for key in current:
            if key.startswith("current_") and isinstance(current[key], dict):
                suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
                if "historical_cycle221_" + suffix in current:
                    gate[key] = current["historical_cycle221_" + suffix]
        record = gate["current_dependency_qualification"]
        previous = gate["historical_cycle220_dependency_qualification"]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((record["cycle"], record["source_validation_cycle"]), (221, 221))
        self.assertEqual((projection["passed_checks"], projection["pending_downstream_native_checks"]), (24, 3))
        self.assertEqual(projection["next_dependency_move_id"], "N12-SCHED-SMP-PREEMPT-001")
        self.assertEqual(record["receipt_bindings"][:-2], previous["receipt_bindings"])
        self.assertEqual(record["newly_qualified_profiles"], ["scheduler_smp", "scheduler_ap_workers"])
        self.assertEqual(record["qualified_profiles"], previous["qualified_profiles"] + record["newly_qualified_profiles"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["scheduler_smp_preempt", "atomics", "locks"])
        entry = json.loads((ROOT / "runs/native_kernel_entry_readiness.json").read_bytes())
        self.assertEqual(record["kernel_sha256"], entry["product"]["canonical_sha256"])
        totals = [0, 0, 0]
        for name, binding in zip(("smp", "ap_worker"), record["receipt_bindings"][-2:], strict=True):
            raw = (ROOT / binding["path"]).read_bytes()
            self.assert_replayed_receipt_binding(binding, raw)
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assert_retained_receipt_admission(module, receipt)
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + binding["profile"] + "_readiness")())
            self.assertEqual(json.dumps(receipt["build"]["kernel_entry"], sort_keys=True, allow_nan=False),
                             json.dumps(entry, sort_keys=True, allow_nan=False))
            self.assertTrue(all(run["qemu_exit_code"] == 0 for run in receipt["execution"]["runs"]))
            self.assertEqual(binding["fresh_runs"], len(receipt["execution"]["runs"]))
            self.assertEqual(binding["negative_controls"], len(receipt["negative_controls"]))
            self.assertEqual(binding["hostile_cases"], sum(c["case_count"] for c in receipt["negative_controls"]))
            for index, field in enumerate(("fresh_runs", "negative_controls", "hostile_cases")):
                totals[index] += binding[field]
            audit = gate["current_" + name + "_control_qualification"]
            self.assertEqual((audit["source_validation_cycle"], audit["measured_relocation_count"]), (221, 1326))
            self.assertEqual(audit["receipt_sha256"], binding["sha256"])
            self.assertTrue(audit["current_receipt_admitted"])
            self.assertFalse(audit["current_kernel_live_replay_pending"])
            transaction = gate["current_" + name + "_transaction_qualification"]
            self.assertEqual(transaction["latest_live_replay_cycle"], 221)
            self.assertEqual(transaction["latest_live_receipt_sha256"], binding["sha256"])
        self.assertEqual(totals, [4, 66, 628])
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_aggregate_cases"], record["independent_current_image_pin_cases"]), (669, 30, 12))
        for name in ("cpu_qualification", "boot_chain_qualification", "ownership_qualification", "capture_qualification",
                     "deferred_control_qualification", "deferred_transaction_qualification"):
            self.assertEqual(gate["current_" + name], gate["historical_cycle220_" + name])
        closeout = gate["current_closeout_regression"]
        self.assertEqual((closeout["tests_passed"], closeout["tests_failed"], closeout["tests_skipped"]), (39, 0, 0))
        self.assertEqual(sum(f["reconciled_pins"] for f in closeout["initial_admission_failures"]), 4)
        self.assertEqual((closeout["initial_metadata_regression"]["tests_failed"],
                          closeout["second_metadata_regression"]["tests_failed"],
                          closeout["corrected_metadata_regression"]["tests_passed"]), (5, 1, 68))
        self.assertTrue(all(f["same_candidate_admitted_after_repair"] for f in closeout["initial_admission_failures"]))
        self.assertFalse(closeout["guest_evidence_rewritten_or_rerun_for_pin_repair"])
        self.assertFalse(closeout["merge_qualified"])
        self.assertEqual(record["unproven_per_control_rejection_groups_at_least"], 17)
        for profile in record["readiness_replay_required_profiles"]:
            self.assert_current_gate_projection(getattr(pooleos_release_gate, "check_native_kernel_" + profile + "_readiness")())
        self.assertFalse(record["all_fourteen_profiles_current"])
        self.assertFalse(record["production_ready"])

    def test_cycle222_smp_preemption_controls_preserve_source_and_history(self) -> None:
        from runtime import native_kernel_scheduler_smp_preempt as profile
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for key in current:
            if key.startswith("current_"):
                suffix = "source_projection" if key == "current_focused_source_projection" else key.removeprefix("current_")
                if "historical_cycle222_" + suffix in current:
                    gate[key] = current["historical_cycle222_" + suffix]
        record = gate["current_dependency_qualification"]
        previous = gate["historical_cycle221_dependency_qualification"]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((record["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (222, 25, 2))
        self.assertEqual(record["receipt_bindings"][:-1], previous["receipt_bindings"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["atomics", "locks"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / binding["path"]).read_bytes()
        self.assert_replayed_receipt_binding(binding, raw)
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(profile, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_scheduler_smp_preempt_readiness())
        self.assertEqual(receipt["negative_controls"], profile.expected_controls())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"]), (2, 34, 322))
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_aggregate_cases"]), (339, 11))
        audit = gate["current_smp_preempt_control_qualification"]
        self.assertEqual((audit["constant_only_groups_replaced"], audit["native_cases"], audit["source_rejections"]), (17, 61, 46))
        self.assertEqual(audit["diagnostic_baseline"]["runtime_corruptions_accepted"], 273)
        self.assertEqual(audit["after_audit"]["runtime_exceptions"], 0)
        self.assertFalse(audit["native_kernel_changed"])
        self.assertEqual(gate["current_control_execution_audit"]["source_control_gaps"], [])
        self.assertEqual(gate["current_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 0)
        self.assertEqual(gate["historical_cycle221_control_execution_audit"]["unproven_per_control_rejection_groups_at_least"], 17)
        self.assertEqual(projection["next_dependency_move_id"], "N12-CONCURRENCY-ATOMICS-001")
        self.assertFalse(gate["current_closeout_regression"]["merge_qualified"])
        self.assertFalse(record["production_ready"])

    def test_cycle223_atomics_admission_preserves_native_image_and_prior_evidence(self) -> None:
        from runtime import native_kernel_atomics as profile
        from tests.test_native_atomics_admission import recorded_atomics_mutations
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle223_dependency_qualification"]
        old = gate["historical_cycle222_dependency_qualification"]
        projection = gate["historical_cycle223_source_projection"]
        self.assertEqual((record["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (223, 26, 1))
        self.assertEqual(record["receipt_bindings"][:-1], old["receipt_bindings"])
        self.assertEqual(record["qualified_profiles"], old["qualified_profiles"] + ["atomics"])
        self.assertEqual(record["readiness_replay_required_profiles"], ["locks"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / binding["path"]).read_bytes()
        self.assert_replayed_receipt_binding(binding, raw)
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(profile, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_atomics_readiness())
        self.assertEqual(receipt["negative_controls"], profile.expected_controls())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"]), (2, 29, 78))
        self.assertEqual(len(list(recorded_atomics_mutations(receipt))), record["recorded_evidence_case_total"])
        self.assertEqual((record["recorded_evidence_case_total"], record["independent_aggregate_cases"]), (356, 8))
        audit = gate["current_atomics_admission_qualification"]
        self.assertEqual((audit["diagnostic_baseline"]["runtime_corruptions_accepted"], audit["diagnostic_baseline"]["gate_corruptions_accepted"]), (168, 91))
        self.assertTrue(audit["diagnostic_baseline"]["comment_only_assembly_accepted"])
        self.assertEqual(audit["after_audit"]["runtime_exceptions"], 0)
        self.assertEqual((audit["disabled_native_guard_variants"], audit["native_guard_mutant_executions"]), (8, 16))
        self.assertFalse(audit["native_kernel_changed"])
        self.assertFalse(audit["positive_receipt_rebound_in_tests"])
        self.assertFalse(gate["current_closeout_regression"]["merge_qualified"])
        self.assertEqual(projection["next_dependency_move_id"], "N12-CONCURRENCY-LOCKS-001")
        self.assertFalse(record["production_ready"])

    def test_cycle224_lock_replay_preserves_history_and_closes_profile_replay(self) -> None:
        from runtime import native_kernel_locks as profile
        from tests.test_native_locks_admission import corrupted_records
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle224_dependency_qualification"]
        prior = gate["historical_cycle223_dependency_qualification"]
        projection = gate["historical_cycle230_focused_source_projection"]
        self.assertEqual((record["cycle"], projection["passed_checks"], projection["pending_downstream_native_checks"]), (224, 27, 0))
        self.assertEqual(record["receipt_bindings"][:-1], prior["receipt_bindings"])
        self.assertEqual(record["qualified_profiles"], prior["qualified_profiles"] + ["locks"])
        self.assertEqual(record["readiness_replay_required_profiles"], [])
        self.assertTrue(record["all_fourteen_profiles_current"])
        self.assertFalse(record["embedded_entry_provenance_replay_pending"])
        binding = record["receipt_bindings"][-1]
        raw = (ROOT / binding["path"]).read_bytes()
        self.assert_replayed_receipt_binding(binding, raw)
        receipt = json.loads(raw)
        self.assert_retained_receipt_admission(profile, receipt)
        self.assert_current_gate_projection(pooleos_release_gate.check_native_kernel_locks_readiness())
        self.assertEqual(receipt["negative_controls"], profile.expected_controls())
        self.assertEqual((binding["fresh_runs"], binding["negative_controls"], binding["hostile_cases"]), (2, 30, 103))
        self.assertEqual(len(list(corrupted_records(receipt))), record["recorded_evidence_case_total"])
        self.assertEqual(record["recorded_evidence_case_total"], 631)
        audit = gate["current_locks_admission_qualification"]
        self.assertEqual((audit["diagnostic_baseline"]["runtime_corruptions_accepted"], audit["diagnostic_baseline"]["gate_corruptions_accepted"]), (53, 32))
        self.assertEqual((audit["diagnostic_baseline"]["runtime_exceptions"], audit["diagnostic_baseline"]["gate_exceptions"]), (6, 64))
        self.assertEqual(hashlib.sha256((ROOT / audit["historical_fixture_path"]).read_bytes()).hexdigest().upper(), audit["historical_fixture_sha256"])
        self.assertEqual(audit["disabled_validator_variants_detected"], 3)
        self.assertFalse(audit["native_kernel_changed"])
        self.assertFalse(audit["positive_receipt_rebound_in_tests"])
        self.assertFalse(gate["current_closeout_regression"]["merge_qualified"])
        self.assertEqual(projection["next_dependency_move_id"], "N36-RECEIPT-COVERAGE-001")
        self.assertFalse(record["production_ready"])

    def test_cycle225_static_sources_preserve_original_execution_receipts(self) -> None:
        from runtime import native_execution_sources as sources
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle225_execution_source_qualification"]
        raw = (ROOT / "tests/fixtures/cycle225-execution-sources.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), record["receipt_sha256"])
        self.assertTrue(sources.evidence_errors(json.loads(raw)))
        current = json.loads((ROOT / "tests/fixtures/cycle229-execution-sources.json").read_bytes())
        self.assertEqual([{k: v for k, v in row.items() if k != "reviewed_data"}
                          for row in current["profiles"][13:]], json.loads(raw)["profiles"])
        self.assertEqual((record["profiles"], record["unique_python_sources"], record["fresh_qemu_runs"]), (14, 62, 0))
        self.assertEqual(gate["historical_cycle231_dependency_qualification"], gate["historical_cycle224_dependency_qualification"])
        self.assertTrue(gate["historical_cycle225_control_execution_audit"]["blocks_merge_qualification"])
        self.assertFalse(record["authentication_or_complete_dependency_closure"])
        self.assertFalse(record["production_ready"])

    def test_cycle226_source_coverage_does_not_hide_errata_admission_gap(self) -> None:
        from runtime import native_execution_sources as sources
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle226_execution_source_qualification"]
        raw = (ROOT / "tests/fixtures/cycle226-execution-sources.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), record["receipt_sha256"])
        self.assertTrue(sources.evidence_errors(json.loads(raw)))
        self.assertEqual((record["profiles"], record["unique_python_sources"], record["fresh_qemu_runs"]), (27, 78, 0))
        self.assertEqual(record["errata_host_qualification"]["receipt_sha256"],
                         hashlib.sha256((ROOT / "tests/fixtures/cycle226-errata-readiness.json").read_bytes()).hexdigest().upper())
        diagnostic = gate["historical_cycle226_control_execution_audit"]["errata_recorded_admission"]
        self.assertEqual((diagnostic["case_count"], diagnostic["invalid_accepted_per_path"],
                          diagnostic["exceptions_per_path"]), (8, 6, 2))
        self.assertFalse(diagnostic["repaired"])
        self.assertTrue(gate["historical_cycle226_control_execution_audit"]["blocks_merge_qualification"])
        self.assertFalse(record["authentication_or_complete_dependency_closure"])
        self.assertFalse(gate["current_closeout_regression"]["merge_qualified"])

    def test_cycle227_errata_admission_preserves_target_denial_and_other_sources(self) -> None:
        from runtime import native_execution_sources as sources
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle232_execution_source_qualification"]
        raw = (ROOT / "tests/fixtures/cycle229-execution-sources.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), record["receipt_sha256"])
        self.assertTrue(sources.evidence_errors(json.loads(raw)))
        self.assertFalse(pooleos_release_gate.check_native_execution_sources()["ok"])
        old = json.loads((ROOT / "tests/fixtures/cycle226-execution-sources.json").read_bytes())
        for before, after in zip(old["profiles"], json.loads(raw)["profiles"], strict=True):
            if before["profile"] != "errata_policy":
                self.assertEqual(before, {k: v for k, v in after.items() if k != "reviewed_data"})
        errata = record["errata_host_qualification"]
        self.assertTrue(errata["recorded_admission_repaired"])
        self.assertEqual(errata["target_denial_reasons"], 6)
        self.assertEqual(errata["receipt_sha256"],
                         hashlib.sha256((ROOT / "runs/native-kernel-errata-policy-readiness.json").read_bytes()).hexdigest().upper())
        audit = gate["current_control_execution_audit"]["errata_recorded_admission"]
        self.assertEqual(audit["after"]["case_count"], 1742)
        self.assertEqual(audit["after"]["invalid_accepted_per_path"], 0)
        self.assertEqual(audit["after"]["exceptions_per_path"], 0)
        self.assertTrue(audit["repaired"])
        self.assertTrue(gate["historical_cycle227_control_execution_audit"]["blocks_merge_qualification"])
        self.assertFalse(gate["current_closeout_regression"]["canonical_full_replay_performed"])

        attempt = gate["historical_cycle227_candidate_audit"]["latest_completed_attempt"]
        self.assertEqual(attempt["status"], "fail")
        self.assertEqual(attempt["commit"], "79adf4aa452daf36f52e24b99c176c49b2523935")
        self.assertEqual((attempt["checks_passed"], attempt["checks_total"]), (105, 106))
        self.assertEqual((attempt["doctor_checks_passed"], attempt["doctor_checks_total"]), (707, 708))
        self.assertEqual(attempt["failed_doctor_check"], "pooleos:unittest")
        self.assertFalse(attempt["failed_test_names_retained"])
        self.assertFalse(attempt["applies_to_later_metadata_edits"])
        self.assertFalse(attempt["merge_qualified"])

    def test_cycle228_host_reproduction_and_diagnostics_do_not_promote_fixtures(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        repair = gate["current_host_reproduction_repair"]
        self.assertEqual(repair["cycle"], 228)
        self.assertEqual(repair["diagnostic"]["scope"], "failfast_not_full_suite")
        self.assertEqual((repair["diagnostic"]["tests_run"], repair["diagnostic"]["failures"],
                          repair["diagnostic"]["skips"]), (882, 1, 1))
        self.assertFalse(repair["diagnostic"]["complete_original_canonical_failure_set_known"])
        reproduction = repair["reproduction"]
        self.assertEqual(reproduction["observed_windows_version"], [10, 0, 26300])
        self.assertTrue(reproduction["historical_ledger_unchanged"])
        self.assertTrue(reproduction["shared_qualifier_unchanged"])
        self.assertTrue(reproduction["all_other_report_bytes_exact"])
        self.assertTrue(all(repair["reporting"].values()))
        self.assertEqual(repair["initial_repair_failure"]["failing_timeout_subtests"], 3)
        self.assertEqual(repair["fresh_guest_boots"], 0)
        self.assertFalse(repair["native_bytes_changed"])
        self.assertFalse(repair["production_ready"])
        self.assertEqual(gate["historical_cycle230_closeout_regression"]["tests_passed"], 19)
        self.assertFalse(gate["current_closeout_regression"]["canonical_full_replay_performed"])
        self.assertTrue(gate["historical_cycle228_control_execution_audit"]["blocks_merge_qualification"])

    def test_cycle229_reviewed_inputs_clear_only_the_bounded_development_hold(self) -> None:
        from runtime import native_execution_sources as sources
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        review = gate["current_data_dependency_review"]
        record = gate["historical_cycle236_execution_source_qualification"]
        raw = (ROOT / sources.RECEIPT).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), record["receipt_sha256"])
        self.assertTrue(sources.evidence_errors(json.loads(raw)))
        self.assertEqual((review["reviewed_data_bindings"], review["unique_data_paths"]), (18, 13))
        self.assertEqual(review["original_profile_core_fields_preserved"], 27)
        self.assertEqual(review["remaining_observed_data_reads_unbound"], 0)
        self.assertEqual(review["after"]["changed_data_files_rejected"], 13)
        self.assertFalse(review["after"]["recorded_consistency_is_authentication"])
        self.assertEqual(review["media_review"]["logical_pairs"], 462)
        self.assertEqual(review["media_review"]["generated_or_retained_byte_pairs"], 438)
        self.assertEqual(review["media_review"]["historical_boot_build_record_pairs"], 24)
        self.assertFalse(review["complete_dynamic_subprocess_or_host_closure"])
        self.assertFalse(review["production_supply_chain_gate_closed"])
        self.assertFalse(gate["current_control_execution_audit"]["blocks_merge_qualification"])
        self.assertEqual(gate["current_control_execution_audit"]["status"], "open")
        attempt = gate["historical_cycle229_candidate_audit"]["latest_completed_attempt"]
        self.assertEqual(attempt["commit"], "293383d9cdf47240bcf32ef3373da49bac1006dc")
        self.assertEqual((attempt["status"], attempt["checks_passed"], attempt["checks_total"]), ("pass", 106, 106))
        self.assertFalse(attempt["applies_to_later_metadata_edits"])
        self.assertFalse(gate["current_candidate_audit"]["aggregate_suite_passed"])
        self.assertFalse(gate["current_closeout_regression"]["merge_qualified"])
        self.assertFalse(self.roadmap["production_ready"])

    def test_cycle230_iso_inspection_preserves_historical_merge_and_demo_rejection(self) -> None:
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        merged = gate["historical_cycle230_main_merge"]
        self.assertEqual(merged["main_commit"], "08d4dbe707e546ffb33e0db102ff76dbf8f6daeb")
        self.assertEqual((merged["checks_passed"], merged["doctor_checks_passed"]), (106, 708))
        self.assertTrue(merged["tree_equality_verified"])
        self.assertFalse(merged["applies_to_later_metadata_edits"])
        record = gate["current_iso_inspection"]
        self.assertEqual((record["new_tests_passed"], record["combined_tests_passed"], record["combined_tests_skipped"]), (19, 27, 1))
        self.assertEqual((record["inventory_files"], record["inner_payload_hashes_match_original_manifest"]), (17, 12))
        self.assertEqual((record["structural_violations"], record["missing_production_objects"]), (1, 4))
        self.assertFalse(record["demo_architecture_conformance_passed"])
        self.assertFalse(record["writer_repaired"])
        self.assertTrue(record["original_iso_unchanged"])
        self.assertEqual(record["fresh_guest_boots"], 0)
        self.assertFalse(record["production_ready"])
        flags = {f["id"]: f for f in self.roadmap["implementation_flags"]}
        for flag in ("FLAG-N0-ISO-INSPECTION-001", "FLAG-N5-FAT32-PARENT-001"):
            self.assertEqual(flags[flag]["status"], "open")
        self.assertEqual(gate["current_candidate_audit"]["status"], "not_run")
        self.assertFalse(gate["current_candidate_audit"]["aggregate_suite_passed"])

    def test_cycle231_fat_repair_keeps_incomplete_source_replay_blocked(self) -> None:
        from runtime import native_execution_sources as sources
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("candidate_audit", "focused_source_projection", "execution_source_qualification", "closeout_regression"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle231_" + suffix]
        merged = gate["current_main_merge"]
        self.assertEqual(merged["main_commit"], "bb5e43c3e655db5b8c5676572135471bfd843880")
        self.assertEqual((merged["checks_passed"], merged["doctor_checks_passed"]), (106, 708))
        self.assertFalse(merged["applies_to_later_metadata_edits"])
        repair = gate["current_fat_directory_repair"]
        self.assertTrue(repair["blocks_merge_qualification"])
        self.assertEqual(repair["source_test_inventory"], 1233)
        self.assertEqual((repair["root_parent_cluster"], repair["dot_entries_checked"]), (0, 4))
        for name, path in (("load", "runs/native_kernel_load_readiness.json"),
                           ("pooleboot", "runs/native_pooleboot_readiness.json")):
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper(),
                             repair[name]["receipt_sha256"])
            self.assertEqual((repair[name]["guest_runs"], repair[name]["negative_controls_passed"]), (2, 155))
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["total_checks"]), (20, 27))
        self.assertEqual(len(projection["passing_profiles"]), 20)
        self.assertEqual(len(projection["failed_profiles"]), 7)
        self.assertEqual(projection["source_current_profiles"], 6)
        self.assertEqual(len(projection["pending_source_profiles"]), 21)
        self.assertEqual(projection["pending_source_profiles"][:2], ["revalidation", "transfer"])
        record = gate["current_execution_source_qualification"]
        raw = (ROOT / "tests/fixtures/cycle229-execution-sources.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), record["receipt_sha256"])
        self.assertEqual(record["receipt_sha256"],
                         gate["historical_cycle230_execution_source_qualification"]["receipt_sha256"])
        self.assertTrue(sources.evidence_errors(json.loads(raw)))
        self.assertFalse(pooleos_release_gate.check_native_execution_sources(ROOT / "tests/fixtures/cycle229-execution-sources.json")["ok"])
        self.assertFalse(gate["current_candidate_audit"]["aggregate_suite_passed"])
        self.assertEqual(gate["current_closeout_regression"]["tests_passed"], 26)
        for field in ("native_kernel_changed", "retained_demo_changed", "transfer_performed", "n5_exit", "production_ready"):
            self.assertFalse(repair[field], field)

    def test_cycle232_corrected_media_boot_cpu_replay_preserves_downstream_hold(self) -> None:
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        gate = dict(current)
        for name in ("candidate_audit", "focused_source_projection", "execution_source_qualification",
                     "closeout_regression", "dependency_qualification", "ownership_qualification",
                     "corrected_media_replay"):
            suffix = "source_projection" if name == "focused_source_projection" else name
            gate["current_" + name] = current["historical_cycle232_" + suffix]
        record = gate["current_corrected_media_replay"]
        self.assertEqual(record["cycle"], 232)
        self.assertEqual((record["broad_regression"]["tests_run"], record["broad_regression"]["tests_failed"]), (71, 17))
        self.assertFalse(record["broad_regression"]["guards_relaxed"])
        self.assertTrue(record["conservation_repair"]["historical_inventory_frozen"])
        self.assertEqual((record["fresh_successful_guest_runs"], record["negative_control_groups"]), (16, 319))
        self.assertEqual(record["revalidation_differential_cases"], 32768)
        self.assertEqual((record["whpx_exception_runs"], record["expected_tcg_limitation_probes"]), (2, 1))
        self.assertEqual(len(record["receipt_bindings"]), 7)
        for binding in record["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            self.assertTrue(module.readiness_errors(receipt, ROOT))
            self.assertEqual(len(receipt["negative_controls"]), binding["negative_controls"])
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["total_checks"]), (22, 27))
        self.assertEqual((projection["source_current_profiles"], len(projection["pending_source_profiles"])), (13, 14))
        self.assertEqual(projection["pending_source_profiles"][:2], ["physical_memory", "virtual_memory"])
        for name in projection["passing_profiles"] + projection["failed_profiles"]:
            self.assertEqual(getattr(pooleos_release_gate, "check_" + name)()["ok"],
                             name in current["current_focused_source_projection"]["passing_profiles"], name)
        for name in ("boot_chain_qualification", "cpu_qualification"):
            self.assertEqual(gate["historical_cycle233_" + name]["source_validation_cycle"], 232)
            self.assertEqual(gate["historical_cycle231_" + name]["source_validation_cycle"], 218)
        self.assertFalse(gate["current_dependency_qualification"]["all_fourteen_profiles_current"])
        self.assertEqual(gate["current_dependency_qualification"]["readiness_replay_required_profiles"], projection["pending_source_profiles"])
        self.assertFalse(gate["current_ownership_qualification"]["live_receipt_source_current"])
        self.assertFalse(pooleos_release_gate.check_native_execution_sources(ROOT / "tests/fixtures/cycle229-execution-sources.json")["ok"])
        self.assertTrue(record["blocks_merge_qualification"])
        self.assertEqual(gate["current_closeout_regression"]["tests_passed"], 77)
        for field in ("native_kernel_changed", "native_EFI_products_changed", "retained_demo_changed", "production_ready"):
            self.assertFalse(record[field], field)

    def test_cycle233_replay_binds_current_receipts_and_immutable_parent(self) -> None:
        from runtime import native_execution_sources as sources
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]
        record = gate["historical_cycle233_corrected_media_replay"]
        self.assertEqual((record["cycle"], record["fresh_successful_guest_runs"],
                          record["negative_control_groups"], record["hostile_cases"]), (233, 28, 663, 2863))
        self.assertEqual(len(record["receipt_bindings"]), 14)
        self.assertEqual(record["original_capture_projections_validated"], 27)
        self.assertEqual(record["unaffected_profile_records_retained"], 4)
        self.assertEqual(record["affected_profiles_replayed_across_cycles"], 23)
        for binding in record["receipt_bindings"]:
            raw = (ROOT / binding["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), binding["sha256"])
            receipt = json.loads(raw)
            module = importlib.import_module("runtime.native_kernel_" + binding["profile"])
            # Receipt integrity survives; native source admission must now reject.
            self.assertTrue(module.readiness_errors(receipt, ROOT))
            self.assertEqual(len(receipt["negative_controls"]), binding["negative_controls"])
            self.assertEqual(sum(c.get("case_count", 1) for c in receipt["negative_controls"]), binding["hostile_cases"])
        current = json.loads((ROOT / sources.RECEIPT).read_bytes())
        self.assertEqual(hashlib.sha256((ROOT / sources.RECEIPT).read_bytes()).hexdigest().upper(),
                         "65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D")
        self.assertTrue(sources.evidence_errors(current, ROOT))
        self.assertFalse(pooleos_release_gate.check_native_execution_sources()["ok"])
        self.assertEqual(len(gate["current_focused_source_projection"]["pending_source_profiles"]), 22)
        self.assertTrue(gate["historical_cycle233_dependency_qualification"]["all_fourteen_profiles_current"])
        self.assertFalse(gate["current_dependency_qualification"]["applies_to_current_source"])
        ownership = gate["historical_cycle233_ownership_qualification"]
        self.assertEqual((ownership["live_replay_cycle"], ownership["fresh_current_cycle_qemu_runs"]), (233, 4))
        self.assertEqual(ownership["virtual_memory_receipt_sha256"], record["receipt_bindings"][1]["sha256"])
        self.assertEqual(ownership["smp_receipt_sha256"], record["receipt_bindings"][5]["sha256"])
        for key in ("task_stack_live_integration_verified", "general_task_CPU_retirement_integration_verified",
                    "current_candidate_full_gate_passed", "production_ready"):
            self.assertFalse(ownership[key], key)
        pins = {
            "candidate_audit": "38EC28F3934283C71E93381B0588BCF6436B16EBB6B0FF0F95CAC9502FA47467",
            "source_projection": "FE68A20DDB02BEC701669AC172956A70E55241ADF119D4F8B0A6FC9BAF8F512F",
            "execution_source_qualification": "BCCA4A71B221B4143AE3FA31410B962C969A2B49A4207FA88FB8735E9C703B9F",
            "closeout_regression": "5CB611EA4DE288F57094E799C70D718A5D22761AEB308D1CCD13927E2591E18D",
            "dependency_qualification": "6AA2A707D0783F49A8ADFBE3E29269C8B842A5B1E5C352791809906C5F077BAB",
            "ownership_qualification": "5C91919813029ACFF9BB8DF06E71F4286CF3C01C94832F2A6F09ED1503C1B6F9",
            "corrected_media_replay": "B22BD2D7DCBE6C2884656EE753B726C975AC965EBF1681E29B15C6D93553D01B",
        }
        for name, digest in pins.items():
            value = gate["historical_cycle232_" + name]
            raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), digest, name)
        for field in ("native_kernel_changed", "native_EFI_products_changed", "retained_demo_changed", "production_ready"):
            self.assertFalse(record[field], field)
        self.assertTrue(record["blocks_merge_qualification"])

    def test_cycle234_userspace_milestone_is_host_only_and_retains_production_goal(self) -> None:
        from unittest.mock import patch
        from runtime import native_kernel_entry as entry
        baseline = self.roadmap["baseline"]
        lane = baseline["historical_cycle234_user_space_integration"]
        self.assertEqual(lane["selected_stage"], "USI-1")
        self.assertEqual(lane["host_status"], "pass")
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        self.assertEqual(lane["guest_runs"], 0)
        for key in ("ring3_executed", "iso_built", "production_ready"):
            self.assertFalse(lane[key])
        receipt = json.loads((ROOT / lane["receipt_path"]).read_bytes())
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual([c["tests_passed"] for c in receipt["checks"]], [None, 260, 14, None])
        self.assertTrue(all(c["passed"] and c["returncode"] == 0 for c in receipt["checks"]))
        self.assertTrue(receipt["source_unchanged"])
        self.assertTrue(receipt["owner_report_unchanged"])
        self.assertEqual(hashlib.sha256((ROOT / lane["receipt_path"]).read_bytes()).hexdigest().upper(),
                         "196D6F2966213FB1B996D9A9B8A0647104449104330464ECCB1A1421B94F3351")
        for key in ("ring3_executed", "iso_built", "n13_exit_passed", "production_ready"):
            self.assertFalse(receipt[key])
        gate = baseline["native_consistency_release_gate"]
        projection = gate["current_focused_source_projection"]
        self.assertEqual((projection["passed_checks"], projection["total_checks"]), (2, 27))
        self.assertEqual(len(projection["failed_profiles"]), 25)
        self.assertFalse(gate["current_candidate_audit"]["aggregate_suite_passed"])
        parent = gate["current_candidate_audit"]["latest_completed_attempt"]
        self.assertEqual(parent["main_commit"], "507782dfde4a554434173fdae7a1b25a170414ce")
        self.assertEqual((parent["checks_passed"], parent["doctor_checks_passed"]), (106, 708))
        self.assertFalse(parent["applies_to_later_source_edits"])
        n13 = next(p for p in self.roadmap["phases"] if p["id"] == "N13")
        self.assertEqual(n13["status"], "partial")
        self.assertEqual(next(p for p in n13["subphases"] if p["id"] == "N13.3")["status"], "partial")
        self.assertEqual(self.roadmap["immediate_next_move"]["id"], "N13-CAPABILITY-IPC-001")
        flag = next(f for f in self.roadmap["implementation_flags"] if f["id"] == "FLAG-N13-USERSPACE-ISO-001")
        self.assertEqual(flag["status"], "open")
        retained_entry = json.loads((ROOT / entry.READINESS_RELATIVE).read_bytes())
        with self.assertRaises(AssertionError):
            self.assert_retained_receipt_admission(entry, dict(retained_entry, forged=True))
        with patch.object(entry, "readiness_errors", return_value=[]), self.assertRaises(AssertionError):
            self.assert_retained_receipt_admission(entry, retained_entry)

    def test_historical_replay_binding_rejects_forged_history_and_current_bytes(self) -> None:
        path = "runs/native-kernel-physical-memory-readiness.json"
        binding = dict(path=path, sha256=self.historical_receipts[path])
        raw = (ROOT / path).read_bytes()
        self.assert_replayed_receipt_binding(binding, raw)
        for changed, candidate in (
            (dict(binding, sha256="0" * 64), raw),
            (dict(binding, path="runs/native-kernel-virtual-memory-readiness.json"), raw),
            (binding, raw + b" "),
        ):
            with self.subTest(binding=changed), self.assertRaises(AssertionError):
                self.assert_replayed_receipt_binding(changed, candidate)

    def test_cycle235_prepared_root_preserves_immutable_host_only_history(self) -> None:
        baseline = self.roadmap["baseline"]
        lane = baseline["historical_cycle235_user_space_integration"]
        self.assertEqual(lane["cycle"], 235)
        self.assertTrue(lane["owned_inactive_supervisor_attachment"])
        self.assertEqual(lane["entry_stack_bytes"], 16384)
        self.assertEqual(lane["stages"]["USI-1"], "partial_host_prepared_root_only")
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        for key in ("live_adapter_implemented", "ring3_executed", "iso_built", "production_ready"):
            self.assertFalse(lane[key])
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        self.assertNotIn(b"\r", raw)
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (235, "PKUSER2", "pass"))
        self.assertEqual([c["tests_passed"] for c in receipt["checks"]], [None, 272, 26, None, 2])
        self.assertTrue(all(c["passed"] and c["returncode"] == 0 for c in receipt["checks"]))
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "967233D0AFDAD3B8485A93EE74AB759E2BC6E2E1EEA6690499F8DF97E5B22EFD")
        for check in receipt["checks"]:
            self.assertFalse(Path(check["log_path"]).is_absolute())
            self.assertFalse(any(Path(arg).is_absolute() for arg in check["command"]))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertEqual(receipt["guest_runs"], 0)
        self.assertFalse(receipt["n13_exit_passed"])
        gate = baseline["native_consistency_release_gate"]
        current = gate["historical_cycle235_closeout_regression"]
        self.assertEqual(current["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual(current["tests_passed"], 300)
        self.assertFalse(current["merge_qualified"])
        self.assertFalse(gate["current_candidate_audit"]["aggregate_suite_passed"])
        self.assertEqual(gate["historical_cycle234_closeout_regression"]["tests_passed"], 274)

    def test_cycle236_cpu_lifecycle_is_historical_host_evidence_not_guest_execution(self) -> None:
        baseline = self.roadmap["baseline"]
        lane = baseline["historical_cycle236_user_space_integration"]
        self.assertEqual(lane["cycle"], 236)
        self.assertEqual(lane["stages"]["USI-1"], "partial_host_cpu_lifecycle_adapter_compile_only")
        self.assertTrue(lane["live_adapter_implemented"])
        self.assertTrue(lane["cpu_exposure_lifecycle_implemented"])
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        for key in ("live_adapter_wired", "actual_cr3_switch_executed", "ring3_executed", "iso_built", "production_ready"):
            self.assertFalse(lane[key])
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        self.assertNotIn(b"\r", raw)
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (236, "PKUSER3", "pass"))
        self.assertEqual([c["tests_passed"] for c in receipt["checks"]], [None, 284, 38, None, None, 5])
        self.assertTrue(all(c["passed"] and c["returncode"] == 0 for c in receipt["checks"]))
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "0CE9612DEF69AA63110F6E5A6D4D016DDE8D8F2D7E62A95E36938930D873CAE8")
        for check in receipt["checks"]:
            self.assertFalse(Path(check["log_path"]).is_absolute())
            self.assertFalse(any(Path(arg).is_absolute() for arg in check["command"]))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertEqual(receipt["guest_runs"], 0)
        self.assertFalse(receipt["n13_exit_passed"])
        current = baseline["native_consistency_release_gate"]["historical_cycle236_closeout_regression"]
        self.assertEqual(current["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual(current["tests_passed"], 327)
        self.assertFalse(current["merge_qualified"])
        self.assertEqual(lane["receipt_path"], "tests/fixtures/cycle236-user-entry-readiness.json")

    def test_cycle237_live_user_root_is_cpl0_not_user_entry_or_iso(self) -> None:
        from runtime import native_execution_sources as sources
        baseline = self.roadmap["baseline"]
        lane = baseline["historical_cycle237_user_space_integration"]
        self.assertEqual(lane["cycle"], 237)
        self.assertEqual(lane["stages"]["USI-1"], "partial_live_cpl0_root_restore_no_ring3")
        for key in ("live_adapter_wired", "actual_cr3_switch_executed", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[key])
        for key in ("ring3_executed", "iso_built", "production_ready"):
            self.assertFalse(lane[key])
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        self.assertNotIn(b"\r", raw)
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["status"], receipt["guest_runs"]), (237, "pass", 3))
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 11)
        for name, count in (("kernel_host_debug", 288), ("user_entry_host_release", 42),
                            ("prepared_ownership_compile_fail", 5), ("boot_exit_host", 10)):
            self.assertEqual(checks[name]["tests_passed"], count)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, c in checks.items():
            self.assertEqual(c["returncode"] != 0, name.startswith("reject_"))
            self.assertFalse(Path(c["log_path"]).is_absolute())
            self.assertFalse(any(Path(arg).is_absolute() for arg in c["command"]))
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "9D4AF96F0267010526F7BED917CF12546410379AB2EF97432244349E90AD3BCA")
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["ring3_executed"] or receipt["n13_exit_passed"] or receipt["iso_built"])
        live = receipt["live_user_root"]
        self.assertEqual((live["status"], live["kernel"]["image_pages"]), ("pass", 160))
        self.assertEqual(len(live["guest_runs"]), 2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            self.assertEqual(len(run["markers"]), 32)
            self.assertEqual(run["hostile_marker_cases_rejected"], 26)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        current = baseline["native_consistency_release_gate"]["historical_cycle237_closeout_regression"]
        self.assertEqual(current["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((current["tests_passed"], current["guest_runs"]), (345, 3))
        self.assertFalse(current["merge_qualified"])
        self.assertEqual(lane["receipt_path"], "tests/fixtures/cycle237-user-entry-readiness.json")
        projection = json.loads((ROOT / "runs/native-user-entry-gate-projection.json").read_bytes())
        self.assertEqual(projection["static_source_current_profiles"],
                         ["entry", "symbols", "policy", "revalidation", "errata_policy"])
        for row in json.loads((ROOT / sources.RECEIPT).read_bytes())["profiles"]:
            path, roots = sources.profile_paths(row["profile"])
            current = (row["sources"] == sources.source_closure(ROOT, roots)
                       and row["reviewed_data"] == sources.reviewed_data_bindings(ROOT, row["profile"])
                       and row["receipt"] == sources.binding(ROOT, path))
            self.assertEqual(current, row["profile"] in projection["static_source_current_profiles"])
        self.assertFalse(projection["source_guard"]["ok"])
        self.assertEqual([(c["name"], c["ok"]) for c in projection["prerequisite_checks"]],
                         [("native_firmware_readiness", True), ("native_boot_trust_readiness", False),
                          ("native_elf_loader_readiness", False)])

    def test_cycle238_timer_recovery_binds_current_sources_without_user_mode_promotion(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle238_user_space_integration"]
        self.assertEqual((lane["cycle"], lane["stages"]["USI-1"]),
                         (238, "partial_live_cpl0_root_timer_restore_no_ring3"))
        self.assertTrue(lane["timer_under_candidate_root_executed"])
        self.assertTrue(lane["verified_timer_shutdown_before_retirement"])
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (238, "PKUSER4", "pass"))
        self.assertFalse(receipt["ring3_executed"] or receipt["iso_built"] or receipt["production_ready"])
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "73D1664F988357FC457006627277FFFC3B1036808566476B7DB5B1E55A0ED45F")
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 11)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, count in (("kernel_host_debug", 300), ("user_entry_host_release", 54),
                            ("prepared_ownership_compile_fail", 5), ("boot_exit_host", 10)):
            self.assertEqual(checks[name]["tests_passed"], count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"], live["kernel"]["image_pages"]), ("pass", 160))
        self.assertEqual(len(live["guest_runs"]), 2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]), 33)
            self.assertEqual((summary["timer_deliveries"], summary["timer_eois"], summary["retained_acpi_pages"]), (3, 3, 1))
            self.assertTrue(summary["timer_quiesced"])
            self.assertEqual(run["hostile_marker_cases_rejected"], 35)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle238_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"], gate["guest_runs"]), (369, 3))
        self.assertFalse(gate["merge_qualified"])

    def test_cycle239_real_user_entry_keeps_preemption_iso_and_production_open(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle239_user_space_integration"]
        self.assertEqual((lane["cycle"], lane["stages"]["USI-1"]),
                         (239, "partial_live_cpl3_fault_return_cleanup_no_user_preemption"))
        self.assertTrue(lane["ring3_executed"] and lane["private_tss_rsp0_executed"])
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        self.assertFalse(lane["user_timer_preemption"] or lane["general_user_program_admission"] or lane["syscall_abi"])
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (239, "PKUSER5", "pass"))
        self.assertTrue(receipt["ring3_executed"] and receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["iso_built"] or receipt["production_ready"] or receipt["n13_exit_passed"])
        self.assertEqual(len(receipt["source_bindings"]), 738)
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "7E55C1665BA04CD484B7F2E652F3014B168EF750FA5A244BD9CD535FB03D0616")
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 12)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, count in (("kernel_host_debug", 315), ("user_entry_host_release", 65),
                            ("vm_host_release", 24), ("prepared_ownership_compile_fail", 5), ("boot_exit_host", 10)):
            self.assertEqual(checks[name]["tests_passed"], count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"], live["kernel"]["image_pages"]), ("pass", 164))
        self.assertEqual(len(live["guest_runs"]), 2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]), 34)
            self.assertEqual((summary["cpl"], summary["user_traps"], summary["timer_deliveries"]), (3, 7, 3))
            self.assertTrue(summary["private_rsp0"] and summary["timer_quiesced"])
            self.assertFalse(summary["user_timer_preemption"])
            self.assertEqual(run["hostile_marker_cases_rejected"], 51)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle239_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"], gate["guest_runs"]), (419, 3))
        self.assertFalse(gate["merge_qualified"])

    def test_cycle240_user_timer_preemption_binds_live_state_without_syscall_or_iso_promotion(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle240_user_space_integration"]
        self.assertEqual((lane["cycle"], lane["stages"]["USI-1"]),
                         (240, "partial_live_cpl3_timer_recovery_no_syscall_or_peer_scheduling"))
        self.assertTrue(lane["ring3_executed"] and lane["user_timer_preemption"])
        self.assertTrue(lane["timer_shutdown_precedes_descriptor_detachment"])
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        for name in ("independent_missing_interrupt_watchdog", "multi_application_scheduling",
                     "general_user_program_admission", "syscall_abi", "iso_built"):
            self.assertFalse(lane[name], name)
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (240, "PKUSER6", "pass"))
        self.assertTrue(receipt["ring3_executed"] and receipt["user_timer_preemption"])
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["iso_built"] or receipt["production_ready"] or receipt["n13_exit_passed"])
        self.assertEqual(len(receipt["source_bindings"]), 740)
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "719E8C31F62451FC9CA485B7D7975BA4CF9388294B5B535CAA1B7775C3A1C097")
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 12)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, count in (("kernel_host_debug", 320), ("user_entry_host_release", 70),
                            ("vm_host_release", 24), ("prepared_ownership_compile_fail", 5), ("boot_exit_host", 10)):
            self.assertEqual(checks[name]["tests_passed"], count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"], live["kernel"]["image_pages"]), ("pass", 164))
        self.assertEqual(len(live["guest_runs"]), 2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]), 35)
            self.assertEqual((summary["cpl"], summary["user_traps"], summary["user_timer_deliveries"],
                              summary["user_timer_eois"], summary["user_resumes"]), (3, 7, 3, 3, 2))
            self.assertTrue(summary["private_rsp0"] and summary["timer_quiesced"] and summary["user_timer_preemption"])
            self.assertGreater(summary["first_progress"], 0)
            self.assertGreater(summary["last_progress"], summary["first_progress"])
            self.assertEqual(run["hostile_marker_cases_rejected"], 66)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle240_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"], gate["guest_runs"]), (429, 3))
        self.assertFalse(gate["merge_qualified"] or gate["canonical_full_replay_performed"])

    def test_cycle241_syscall_copy_binds_live_faults_without_task_or_iso_promotion(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle241_user_space_integration"]
        self.assertEqual((lane["cycle"], lane["stages"]["USI-1"]),
                         (241, "partial_live_cpl3_syscall_copy_timer_no_task_exit_or_peer_scheduling"))
        for name in ("ring3_executed", "user_timer_preemption", "syscall_abi", "bounded_user_copy",
                     "copy_input_failure_atomic", "copy_output_failure_reports_prefix",
                     "syscall_msrs_cleared_before_retirement", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[name], name)
        for name in ("production_syscall_abi_frozen", "general_smap_qualification", "concurrent_user_copy_pinning",
                     "task_exit_and_reaping", "multi_application_scheduling", "general_user_program_admission",
                     "independent_missing_interrupt_watchdog", "iso_built", "production_ready"):
            self.assertFalse(lane[name], name)
        self.assertEqual(lane["development_syscall_abi"], "PSABI1")
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (241, "PKUSER7", "pass"))
        self.assertTrue(receipt["development_syscall_abi"] and receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["iso_built"] or receipt["production_ready"] or receipt["n13_exit_passed"])
        self.assertEqual(len(receipt["source_bindings"]), 742)
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         "A1D8F9AF64D05DEBC88757CA1C8D8C84BC6B292F97E07B7FEF14889614416FE5")
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 12)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, count in (("kernel_host_debug", 326), ("user_entry_host_release", 76),
                            ("vm_host_release", 24), ("prepared_ownership_compile_fail", 5), ("boot_exit_host", 10)):
            self.assertEqual(checks[name]["tests_passed"], count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"], live["kernel"]["image_pages"]), ("pass", 164))
        self.assertEqual(len(live["guest_runs"]), 2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]), 36)
            self.assertEqual((summary["user_calls"], summary["copy_faults"], summary["copy_read_faults"],
                              summary["copy_write_faults"]), (12, 3, 1, 2))
            self.assertEqual(summary["syscall_abi"], "PSABI1_development")
            self.assertTrue(summary["syscall_msrs_cleared"] and summary["timer_quiesced"])
            self.assertEqual((summary["user_timer_deliveries"], summary["user_resumes"]), (3, 2))
            self.assertEqual(run["hostile_marker_cases_rejected"], 89)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle241_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"], gate["guest_runs"]), (441, 3))
        self.assertFalse(gate["merge_qualified"] or gate["canonical_full_replay_performed"])
        phase = next(p for p in self.roadmap["phases"] if p["id"] == "N13")
        self.assertEqual(next(s for s in phase["subphases"] if s["id"] == "N13.4")["status"], "partial")

    def test_cycle242_owned_task_termination_binds_live_cleanup_without_peer_or_iso_promotion(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle242_user_space_integration"]
        self.assertEqual((lane["cycle"], lane["stages"]["USI-1"]),
                         (242, "partial_live_owned_task_exit_fault_reap_no_peer_scheduling"))
        for name in ("ring3_executed", "user_timer_preemption", "syscall_abi", "bounded_user_copy",
                     "task_exit_and_reaping", "failed_cleanup_retains_memory", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[name], name)
        for name in ("production_syscall_abi_frozen", "general_smap_qualification", "concurrent_user_copy_pinning",
                     "complete_spawn_allocation_rollback", "multi_application_scheduling", "general_user_program_admission",
                     "independent_missing_interrupt_watchdog", "iso_built", "production_ready"):
            self.assertFalse(lane[name], name)
        self.assertEqual(lane["task_identity_scope"], "persistent_slot_local_generation_not_capability")
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), "DC81C8D1361A0E1460E8154B688C28F3BB06DB7B259FB7EF63F99A703A26C2C3")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"], receipt["contract_id"], receipt["status"]), (242, "PKUSER8", "pass"))
        self.assertTrue(receipt["user_task_termination"] and receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["iso_built"] or receipt["production_ready"] or receipt["n13_exit_passed"])
        self.assertEqual(len(receipt["source_bindings"]), 745)
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 13)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, count in (("kernel_host_debug", 336), ("user_entry_host_release", 86),
                            ("vm_host_release", 24), ("prepared_ownership_compile_fail", 5),
                            ("task_ownership_compile_fail", 2), ("boot_exit_host", 10)):
            self.assertEqual(checks[name]["tests_passed"], count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"], live["kernel"]["image_pages"]), ("pass", 168))
        self.assertEqual(len(live["guest_runs"]), 2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]), 40)
            self.assertEqual((summary["normal_exits"], summary["fault_terminations"], summary["task_stale_denials"]), (1, 3, 3))
            self.assertEqual([(t["generation"], t["reason"], t["value"], t["syscalls"]) for t in summary["terminated_tasks"]],
                             [(1, "exit", 42, 2), (2, "fault", 6, 0), (3, "fault", 13, 0), (4, "fault", 14, 0)])
            self.assertEqual((summary["cr3_writes"], summary["released_pages"], summary["scrubbed_data_pages"]), (10, 65, 30))
            self.assertFalse(summary["peer_scheduling"] or summary["production_ready"])
            self.assertEqual((summary["user_calls"], summary["copy_faults"], summary["user_timer_deliveries"], summary["user_resumes"]), (12, 3, 3, 2))
            self.assertTrue(summary["syscall_msrs_cleared"] and summary["timer_quiesced"])
            self.assertEqual(run["hostile_marker_cases_rejected"], 157)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle242_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"], gate["guest_runs"]), (463, 3))
        self.assertFalse(gate["merge_qualified"] or gate["canonical_full_replay_performed"])
        phase = next(p for p in self.roadmap["phases"] if p["id"] == "N13")
        for name in ("N13.1", "N13.2", "N13.3", "N13.4", "N13.6"):
            self.assertEqual(next(s for s in phase["subphases"] if s["id"] == name)["status"], "partial")

    def test_cycle243_native_peers_bind_live_survival_without_general_admission_or_iso_promotion(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle243_user_space_integration"]
        self.assertEqual((lane["cycle"],lane["stages"]["USI-1"]),
                         (243,"partial_live_preemptive_peer_tasks_no_general_admission_or_ipc"))
        for field in ("bounded_peer_scheduling","legacy_user_state_saved_restored","suspended_owner_retains_memory",
                "syscall_stack_within_owned_page","syscall_budget_terminates_only_task","continue_full_microkernel_after_iso"):
            self.assertTrue(lane[field],field)
        for field in ("invalid_user_frame_containment","timer_pending_race_qualification","complete_runtime_tick_accounting",
                "complete_spawn_allocation_rollback","general_user_program_admission","multi_application_scheduling",
                "independent_missing_interrupt_watchdog","iso_built","production_ready"):
            self.assertFalse(lane[field],field)
        raw = (ROOT/lane["receipt_path"]).read_bytes()
        receipt = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),"AD4EAA1FD5D80FD564F603D69A083EF2F904452767C1F416F6E6D477C48C8F1E")
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]),(243,"PKUSER9","pass"))
        self.assertTrue(receipt["peer_scheduling"] and receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["production_ready"] or receipt["iso_built"] or receipt["n13_exit_passed"])
        self.assertEqual(len(receipt["source_bindings"]),748)
        checks = {c["name"]:c for c in receipt["checks"]}
        self.assertEqual(len(checks),13)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name,count in (("kernel_host_debug",345),("user_entry_host_release",95),("vm_host_release",24),
                ("prepared_ownership_compile_fail",5),("task_ownership_compile_fail",2),("boot_exit_host",10)):
            self.assertEqual(checks[name]["tests_passed"],count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"]),("pass",172))
        self.assertEqual(live["kernel"]["sha256"],"8D34D5807B660A88D4D819A6723109FC463D3D582419FA40E9A3C98CBB10C41E")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]),44)
            self.assertTrue(summary["peer_scheduling"])
            self.assertFalse(summary["production_ready"])
            self.assertEqual((summary["peer_preemptions"],summary["peer_survival_cases"]),(33,4))
            self.assertEqual([p["first"] for p in summary["peer_rounds"]],["exit","fault","cancel","limit"])
            self.assertEqual(sum(p["dispatches"] for p in summary["peer_rounds"]),40)
            self.assertEqual(sum(p["survivor_after_stop"] for p in summary["peer_rounds"]),16)
            self.assertEqual((summary["cr3_writes"],summary["released_pages"],summary["scrubbed_data_pages"]),(91,169,78))
            self.assertEqual(run["hostile_marker_cases_rejected"],249)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle243_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"],hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"]),(481,3))
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])

    def test_cycle244_user_state_containment_keeps_ss_and_general_admission_unqualified(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle244_user_space_integration"]
        self.assertEqual((lane["cycle"], lane["stages"]["USI-1"]),
                         (244, "partial_live_invalid_return_containment_no_general_admission_or_ipc"))
        for field in ("bounded_peer_scheduling", "invalid_user_frame_containment", "kernel_entry_ac_cleared",
                      "legacy_user_state_saved_restored", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[field], field)
        for field in ("architectural_stack_fault_qualified", "general_user_exception_delivery_qualified",
                      "complete_spawn_allocation_rollback", "timer_pending_race_qualification",
                      "complete_runtime_tick_accounting", "independent_missing_interrupt_watchdog",
                      "general_user_program_admission", "multi_application_scheduling", "iso_built", "production_ready"):
            self.assertFalse(lane[field], field)
        self.assertEqual(lane["new_native_user_exception_vectors"], [0,1,3])
        self.assertEqual(lane["observed_stack_access_vector"], 13)
        raw = (ROOT / lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), "3D6D3860572C99A08B6E0322D61C92BADBC9D0D71ED513D40DAB06AEE6891271")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]), (244,"PKUSER10","pass"))
        self.assertTrue(receipt["peer_scheduling"] and receipt["source_unchanged"] and receipt["owner_report_unchanged"])
        self.assertFalse(receipt["production_ready"] or receipt["iso_built"] or receipt["n13_exit_passed"])
        self.assertEqual(len(receipt["source_bindings"]), 748)
        checks = {c["name"]: c for c in receipt["checks"]}
        self.assertEqual(len(checks), 13)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name, count in (("kernel_host_debug",349),("user_entry_host_release",99),("vm_host_release",24),
                            ("prepared_ownership_compile_fail",5),("task_ownership_compile_fail",2),("boot_exit_host",10)):
            self.assertEqual(checks[name]["tests_passed"],count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"]), ("pass",172))
        self.assertEqual(live["kernel"]["sha256"], "572B391DA29A204F22A21B1777A185449A114100735D0571FFCE0AB96D1DBC87")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]),54)
            self.assertFalse(summary["production_ready"] or summary["architectural_stack_fault_qualified"])
            self.assertEqual((summary["peer_preemptions"],summary["peer_survival_cases"]), (113,14))
            self.assertEqual((summary["invalid_return_terminations"],summary["additional_user_exception_terminations"]), (6,4))
            self.assertEqual(sum(p["dispatches"] for p in summary["peer_rounds"]),140)
            self.assertEqual(sum(p["survivor_after_stop"] for p in summary["peer_rounds"]),56)
            self.assertEqual((summary["cr3_writes"],summary["released_pages"],summary["scrubbed_data_pages"]), (291,429,198))
            self.assertEqual(run["hostile_marker_cases_rejected"],493)
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle244_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"]), (489,3))
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])
        self.assertEqual(len(gate["initial_attempts"]),3)

    def test_cycle245_transactional_construction_binds_live_retry_without_general_admission(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle245_user_space_integration"]
        self.assertEqual((lane["cycle"],lane["stages"]["USI-1"]),
            (245,"partial_live_transactional_construction_no_general_admission_or_ipc"))
        for field in ("bounded_transactional_construction", "construction_peer_continuation",
                "kernel_stack_guard_regression_repaired", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[field],field)
        for field in ("general_quarantine_recovery", "complete_kernel_stack_bound_qualified",
                "general_user_program_admission", "timer_pending_race_qualification",
                "complete_runtime_tick_accounting", "independent_missing_interrupt_watchdog",
                "architectural_stack_fault_qualified", "iso_built", "production_ready"):
            self.assertFalse(lane[field],field)
        raw = (ROOT/lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), "AC96D028977F357C41318AB2CF33E761B0552E82FAB30B5637835681A6CE8346")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]),(245,"PKUSER11","pass"))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"] and receipt["transactional_construction"])
        self.assertEqual(len(receipt["source_bindings"]),751)
        checks = {c["name"]:c for c in receipt["checks"]}
        self.assertEqual(len(checks),14)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name,count in (("kernel_host_debug",356),("user_entry_host_release",106),("vm_host_release",24),
                ("prepared_ownership_compile_fail",5),("task_ownership_compile_fail",2),("spawn_ownership_compile_fail",1),("boot_exit_host",10)):
            self.assertEqual(checks[name]["tests_passed"],count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"]),("pass",177))
        self.assertEqual(live["kernel"]["sha256"],"3CC7704CD01464D666D773966C9752D5F9C8CF0C9E308F45E6A8B3E9017358BD")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]),55)
            self.assertEqual((summary["spawn_quota_failures"],summary["spawn_quota_released_pages"]),(1,5))
            self.assertEqual((summary["spawn_after_effect_failures"],summary["spawn_cleanup_quarantines"],summary["spawn_cleanup_retries"]),(6,6,6))
            self.assertEqual((summary["spawn_released_pages"],summary["spawn_scrubbed_pages"]),(83,83))
            self.assertTrue(summary["spawn_peer_continuation"])
            self.assertEqual((summary["peer_preemptions"],summary["peer_survival_cases"],summary["cr3_writes"]),(113,14,291))
            self.assertEqual((summary["released_pages"],summary["scrubbed_data_pages"]),(512,235))
            self.assertEqual(run["hostile_marker_cases_rejected"],507)
            self.assertFalse(summary["production_ready"] or summary["architectural_stack_fault_qualified"])
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle245_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"],hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"],len(gate["initial_attempts"])),(504,3,7))
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])

    def test_cycle246_timer_shutdown_binds_pending_quarantine_retry_without_complete_accounting(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle246_user_space_integration"]
        self.assertEqual((lane["cycle"],lane["stages"]["USI-1"]),
            (246,"partial_live_bounded_timer_shutdown_no_general_admission_or_ipc"))
        for field in ("bounded_timer_shutdown_recovery", "timer_quarantine_peer_survived",
                "bounded_transactional_construction", "construction_peer_continuation",
                "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[field],field)
        for field in ("general_quarantine_recovery", "complete_kernel_stack_bound_qualified",
                "general_user_program_admission", "timer_pending_race_qualification",
                "complete_runtime_tick_accounting", "failed_cleanup_quantum_accounted",
                "independent_missing_interrupt_watchdog", "architectural_stack_fault_qualified",
                "iso_built", "production_ready"):
            self.assertFalse(lane[field],field)
        self.assertEqual((lane["timer_drain_max_windows"],lane["timer_drain_max_new_deliveries_per_shutdown"]),(32,2))
        self.assertEqual(lane["timer_shutdown_contract"],"PKUSER12")
        raw = (ROOT/lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), "A77030BD8C2557C85D5670D7EDE5C17876C6B05F5EF5E303BC8C82126FC3A6F8")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]),(246,"PKUSER12","pass"))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"] and receipt["timer_shutdown_recovery"])
        self.assertEqual(len(receipt["source_bindings"]),754)
        checks = {c["name"]:c for c in receipt["checks"]}
        self.assertEqual(len(checks),14)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name,count in (("kernel_host_debug",361),("user_entry_host_release",111),("vm_host_release",24),
                ("prepared_ownership_compile_fail",5),("task_ownership_compile_fail",2),("spawn_ownership_compile_fail",1),("boot_exit_host",10)):
            self.assertEqual(checks[name]["tests_passed"],count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"],live["guest_bound_seconds"]),("pass",178,120))
        self.assertEqual(live["kernel"]["sha256"],"92107CE1F169C5E2069161F8F04C2E3613705F7825D4A545C1C9814C2E9A57D1")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]),57)
            self.assertEqual((summary["timer_drain_deliveries"],summary["timer_drain_eois"]),(3,3))
            self.assertEqual((summary["timer_pending_cases"],summary["timer_late_cases"],summary["timer_quarantine_retries"]),(1,1,1))
            self.assertEqual(summary["timer_quarantine_retained_pages"],13)
            self.assertTrue(summary["timer_quarantine_peer_survived"] and summary["spawn_peer_continuation"])
            self.assertEqual((summary["spawn_released_pages"],summary["spawn_scrubbed_pages"]),(83,83))
            self.assertEqual((summary["peer_preemptions"],summary["peer_survival_cases"],summary["cr3_writes"]),(119,15,307))
            self.assertEqual(sum(r["dispatches"] for r in summary["peer_rounds"]),148)
            self.assertEqual((summary["released_pages"],summary["scrubbed_data_pages"]),(538,247))
            last = summary["peer_rounds"][14]
            self.assertEqual((last["first"],last["preemptions"][0],last["ticks"][0]),("quarantine",0,0))
            self.assertEqual(run["hostile_marker_cases_rejected"],548)
            self.assertFalse(summary["production_ready"] or summary["architectural_stack_fault_qualified"])
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle246_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"],hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"],len(gate["initial_attempts"])),(514,3,2))
        self.assertEqual(gate["initial_attempts"][1]["guest_bound_seconds"],90)
        self.assertEqual(gate["diagnostic"]["status"],"pass_diagnostic_not_qualification")
        self.assertEqual(gate["qualification_guest_bound_seconds"],120)
        self.assertTrue(gate["bound_frozen_before_fresh_qualification"])
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])

    def test_cycle247_runtime_accounting_binds_all_returned_quanta_without_unknown_recovery_claim(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle247_user_space_integration"]
        self.assertEqual((lane["cycle"],lane["stages"]["USI-1"]),
            (247,"partial_live_bounded_quantum_accounting_no_general_admission_or_ipc"))
        for field in ("bounded_runtime_accounting", "failed_cleanup_quantum_accounted",
                "bounded_timer_shutdown_recovery", "timer_quarantine_peer_survived",
                "bounded_transactional_construction", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[field],field)
        for field in ("complete_runtime_tick_accounting", "pure_user_instruction_time",
                "unknown_runtime_recovery_qualified", "physical_clock_coherent_read_qualified",
                "independent_missing_interrupt_watchdog", "general_user_program_admission",
                "general_quarantine_recovery", "complete_kernel_stack_bound_qualified",
                "architectural_stack_fault_qualified", "iso_built", "production_ready"):
            self.assertFalse(lane[field],field)
        self.assertEqual(lane["runtime_accounting_contract"],"PKUSER13")
        raw = (ROOT/lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),"A406DF5C9EE84C48DCEB9B560A05A33A96AAF19D847FF9B86E30D8583E82BB8B")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]),(247,"PKUSER13","pass"))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"] and receipt["bounded_runtime_accounting"])
        self.assertEqual(len(receipt["source_bindings"]),754)
        checks = {c["name"]:c for c in receipt["checks"]}
        self.assertEqual(len(checks),14)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name,count in (("kernel_host_debug",368),("user_entry_host_release",115),("vm_host_release",24),
                ("prepared_ownership_compile_fail",5),("task_ownership_compile_fail",2),("spawn_ownership_compile_fail",1),("boot_exit_host",10)):
            self.assertEqual(checks[name]["tests_passed"],count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"],live["guest_bound_seconds"]),("pass",180,120))
        self.assertEqual(live["kernel"]["sha256"],"5C999DC4AA3A23E470548C38082E4F3489324AD760A280C130CFDC8FF92C261D")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertEqual(len(run["markers"]),58)
            self.assertEqual((summary["runtime_samples"],summary["runtime_terminal_samples"],summary["runtime_duplicate_denials"]),(148,28,148))
            self.assertEqual(summary["runtime_failed_cleanup_samples"],1)
            self.assertEqual(summary["runtime_ticks"], sum(summary[k] for k in (
                "runtime_preempt_ticks", "runtime_terminal_ticks", "runtime_failed_cleanup_ticks")))
            self.assertGreater(summary["runtime_terminal_ticks"],0)
            self.assertGreater(summary["runtime_failed_cleanup_ticks"],0)
            self.assertEqual(summary["peer_rounds"][14]["ticks"][0],summary["runtime_failed_cleanup_ticks"])
            self.assertTrue(summary["bounded_runtime_accounting"] and summary["timer_quarantine_peer_survived"])
            self.assertEqual((summary["peer_preemptions"],summary["peer_survival_cases"],summary["cr3_writes"]),(119,15,307))
            self.assertEqual((summary["released_pages"],summary["scrubbed_data_pages"]),(538,247))
            self.assertEqual((summary["spawn_released_pages"],summary["spawn_scrubbed_pages"]),(83,83))
            self.assertEqual(run["hostile_marker_cases_rejected"],563)
            self.assertFalse(summary["pure_user_instruction_time"] or summary["production_ready"])
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle247_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"],hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"],len(gate["initial_attempts"])),(525,3,2))
        self.assertEqual(gate["qualification_guest_bound_seconds"],120)
        self.assertTrue(gate["qualification_bound_unchanged"])
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])

    def test_cycle248_hpet_backup_requires_owned_recovery_without_general_watchdog_claim(self) -> None:
        lane = self.roadmap["baseline"]["historical_cycle248_user_space_integration"]
        self.assertEqual((lane["cycle"],lane["stages"]["USI-1"]),
            (248,"partial_live_bounded_hpet_backup_no_general_admission_or_ipc"))
        for field in ("bounded_hpet_backup_recovery", "bounded_runtime_accounting", "failed_cleanup_quantum_accounted",
                "bounded_timer_shutdown_recovery", "timer_quarantine_peer_survived",
                "bounded_transactional_construction", "continue_full_microkernel_after_iso"):
            self.assertTrue(lane[field],field)
        for field in ("nmi_recovery_qualified", "native_simultaneous_pending_sources_qualified", "ioapic_backup_qualified", "complete_runtime_tick_accounting", "pure_user_instruction_time",
                "unknown_runtime_recovery_qualified", "physical_clock_coherent_read_qualified",
                "independent_missing_interrupt_watchdog", "general_user_program_admission",
                "general_quarantine_recovery", "complete_kernel_stack_bound_qualified",
                "architectural_stack_fault_qualified", "iso_built", "production_ready"):
            self.assertFalse(lane[field],field)
        self.assertEqual(lane["runtime_accounting_contract"],"PKUSER13")
        self.assertEqual(lane["watchdog_contract"],"PKUSER14")
        self.assertEqual(lane["watchdog_deadline_ns"],50000000)
        self.assertEqual(lane["timer_drain_max_new_deliveries_per_shutdown"],4)
        self.assertTrue(lane["hpet_msi_launch_opt_in"])
        raw = (ROOT/lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),"1182CB4054D0882F07AD51DD96097CC5C49E4AC999D9E1621D47E547FB91CE15")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]),(248,"PKUSER14","pass"))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"] and receipt["bounded_runtime_accounting"])
        self.assertEqual(len(receipt["source_bindings"]),757)
        checks = {c["name"]:c for c in receipt["checks"]}
        self.assertEqual(len(checks),14)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        for name,count in (("kernel_host_debug",375),("user_entry_host_release",122),("vm_host_release",24),
                ("prepared_ownership_compile_fail",5),("task_ownership_compile_fail",2),("spawn_ownership_compile_fail",1),("boot_exit_host",10)):
            self.assertEqual(checks[name]["tests_passed"],count)
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"],live["guest_bound_seconds"]),("pass",181,120))
        self.assertEqual(live["kernel"]["sha256"],"A26606833AC1B53FD9AB1824F16C13BDA7B5DB7904C144F82CD7FD99CEBCEAC1")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = run["marker_summary"]
            self.assertTrue(run["hpet_msi"])
            self.assertTrue(summary["bounded_hpet_backup_recovery"] and summary["watchdog_shared_apic"])
            self.assertFalse(summary["independent_missing_interrupt_watchdog"] or summary["nmi_recovery"])
            self.assertEqual((summary["watchdog_recoveries"],summary["watchdog_arms"],
                summary["watchdog_stops"],summary["watchdog_restores"]),(1,156,156,156))
            self.assertEqual(summary["watchdog_ticks"],summary["peer_rounds"][15]["ticks"][0])
            self.assertEqual(summary["peer_rounds"][15]["preemptions"][0],0)
            self.assertEqual(summary["peer_rounds"][15]["first"],"watchdog")
            self.assertGreater(summary["watchdog_ticks"],0)
            self.assertEqual(len(run["markers"]),60)
            self.assertEqual((summary["runtime_samples"],summary["runtime_terminal_samples"],summary["runtime_duplicate_denials"]),(156,30,156))
            self.assertEqual(summary["runtime_failed_cleanup_samples"],1)
            self.assertEqual(summary["runtime_ticks"], sum(summary[k] for k in (
                "runtime_preempt_ticks", "runtime_terminal_ticks", "runtime_failed_cleanup_ticks")))
            self.assertGreater(summary["runtime_terminal_ticks"],0)
            self.assertGreater(summary["runtime_failed_cleanup_ticks"],0)
            self.assertEqual(summary["peer_rounds"][14]["ticks"][0],summary["runtime_failed_cleanup_ticks"])
            self.assertTrue(summary["bounded_runtime_accounting"] and summary["timer_quarantine_peer_survived"])
            self.assertEqual((summary["peer_preemptions"],summary["peer_survival_cases"],summary["cr3_writes"]),(125,16,323))
            self.assertEqual((summary["released_pages"],summary["scrubbed_data_pages"]),(564,259))
            self.assertEqual((summary["spawn_released_pages"],summary["spawn_scrubbed_pages"]),(83,83))
            self.assertEqual(run["hostile_marker_cases_rejected"],601)
            self.assertFalse(summary["pure_user_instruction_time"] or summary["production_ready"])
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["historical_cycle248_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"],hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"],len(gate["initial_attempts"])),(539,3,2))
        self.assertEqual(gate["qualification_guest_bound_seconds"],120)
        self.assertTrue(gate["qualification_bound_unchanged"])
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])

    def test_cycle249_unknown_runtime_requires_retired_debt_and_fresh_peer_survival(self) -> None:
        from runtime import native_user_root as probe
        lane = self.roadmap["baseline"]["user_space_integration"]
        self.assertEqual((lane["cycle"],lane["unknown_runtime_contract"]),(249,"PKUSER15"))
        self.assertTrue(lane["bounded_unknown_runtime_recovery"])
        self.assertEqual(lane["stages"]["USI-1"],"partial_live_bounded_unknown_recovery_no_general_admission_or_ipc")
        self.assertEqual(lane["unmeasured_dispatches_per_probe"],[1,1])
        self.assertEqual(lane["unknown_task_total_ticks_per_probe"],[None,None])
        for name in ("unknown_runtime_recovery_qualified", "physical_clock_failure_recovery",
                "persistent_per_generation_runtime_audit", "complete_runtime_tick_accounting",
                "general_quarantine_recovery", "general_user_program_admission",
                "complete_kernel_stack_bound_qualified", "iso_built", "production_ready"):
            self.assertFalse(lane[name],name)
        self.assertTrue(lane["continue_full_microkernel_after_iso"])
        raw = (ROOT/lane["receipt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),"08F3170877F13DD5A0171AFB26DCF959B1597D2AA7AC3BFCFBAAA1A774519185")
        receipt = json.loads(raw)
        self.assertEqual((receipt["cycle"],receipt["contract_id"],receipt["status"]),(249,"PKUSER15","pass"))
        self.assertTrue(receipt["source_unchanged"] and receipt["owner_report_unchanged"] and receipt["unknown_runtime_recovery"])
        self.assertEqual(len(receipt["source_bindings"]),758)
        for path,expected in receipt["source_bindings"].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest().upper(),expected,path)
        checks = {c["name"]:c for c in receipt["checks"]}
        self.assertEqual(len(checks),14)
        self.assertTrue(all(c["passed"] for c in checks.values()))
        self.assertEqual((checks["kernel_host_debug"]["tests_passed"],checks["user_entry_host_release"]["tests_passed"]),(379,124))
        live = receipt["live_user_root"]
        self.assertEqual((live["status"],live["kernel"]["image_pages"],live["guest_bound_seconds"]),("pass",182,120))
        self.assertEqual(live["kernel"]["sha256"],"88CE0AD89B9EEF10680FFFA453B891F88197E3845C26F6DC7F6CD99726CCC4DB")
        self.assertEqual(len(live["guest_runs"]),2)
        for run in live["guest_runs"]:
            self.assertTrue(run["fresh_vars_copy"] and run["media_read_only"] and run["serial_debugcon_exact_match"])
            self.assertFalse(run["guest_network"] or run["host_acceleration"])
            summary = probe.validate_markers(run["markers"])
            self.assertEqual(summary,run["marker_summary"])
            self.assertTrue(summary["unknown_runtime_recovery"])
            self.assertIsNone(summary["unknown_task_total_ticks"])
            self.assertEqual((summary["unmeasured_dispatches"],summary["unknown_task_measured_ticks"]),(1,0))
            self.assertFalse(summary["complete_runtime_tick_accounting"] or summary["physical_clock_failure_recovery"])
            self.assertEqual((summary["unknown_recovery_dispatches"],summary["unknown_peer_preemptions"],summary["unknown_recovery_cr3_writes"]),(8,6,16))
            self.assertGreater(summary["unknown_peer_progress"],0)
            self.assertGreater(summary["unknown_peer_ticks"],0)
            self.assertEqual((len(run["markers"]),summary["peer_survival_cases"],summary["cr3_writes"]),(61,17,339))
            self.assertEqual((summary["released_pages"],summary["scrubbed_data_pages"]),(590,271))
            self.assertEqual((summary["runtime_samples"],summary["runtime_terminal_samples"],summary["runtime_duplicate_denials"]),(156,30,156))
            self.assertEqual((probe.negative_controls(run["markers"]),run["hostile_marker_cases_rejected"]),(630,630))
        self.assertFalse(any("POOLEOS:KERNEL:ENTRY" in m or "USER-ROOT" in m for m in live["ordinary_denial"]["markers"]))
        gate = self.roadmap["baseline"]["native_consistency_release_gate"]["current_closeout_regression"]
        self.assertEqual(gate["receipt_sha256"],hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual((gate["tests_passed"],gate["guest_runs"],len(gate["initial_attempts"])),(545,3,2))
        self.assertFalse(gate["canonical_full_replay_performed"] or gate["merge_qualified"])
        self.assertEqual(self.roadmap["immediate_next_move"]["phase_ids"],["N13","N14"])

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
        self.assertEqual(protocol["selected_move_id"], "N13-USER-ENTRY-LIVE-001")
        self.assertIn("docs/checkpoints/cycle225-retained-execution-source-closure.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle224-locks-admission-and-current-kernel-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle223-atomics-admission-and-instruction-audit.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle221-current-kernel-smp-and-ap-worker-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle220-current-kernel-scheduler-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle219-current-kernel-memory-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle218-terminal-capture-and-cpu-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle217-current-kernel-boot-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle215-ap-worker-admission-and-controls.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle214-current-kernel-smp-scheduler-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle213-current-kernel-scheduler-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle212-current-kernel-memory-and-multiprocessor-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle211-current-kernel-cpu-admission-and-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle210-retained-map-growth-and-boot-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle209-native-ap-worker-transactions.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle208-smp-admission-and-controls.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle207-current-kernel-scheduler-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle206-memory-and-multiprocessor-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle205-current-kernel-cpu-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle204-current-kernel-boot-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle203-native-smp-transactions.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle202-deferred-admission-and-controls.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle201-scheduler-and-preemption-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle200-memory-and-multiprocessor-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle199-cpu-control-admission-and-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle198-symbol-admission-and-boot-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle197-native-deferred-transactions.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle196-preemption-executed-controls.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle195-scheduler-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle195-scheduler-cloud-backup.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle194-memory-runtime-replay.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle193-current-kernel-cpu-replay.md", protocol["required_records"])
        for path in ("docs/checkpoints/cycle192-native-mailbox-oracle.md",
                     "docs/checkpoints/cycle192-unfinished-cloud-backup.md",
                     "docs/checkpoints/cycle192-mailbox-qualified-backup.md"):
            self.assertIn(path, protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle190-percpu-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle191-ipi-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle189-first-ap-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle188-irq-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle187-vm-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle186-pmm-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle185-cpu-recorded-evidence.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle185-unfinished-cloud-backup.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle184-boot-host-provenance.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle184-unfinished-cloud-backup.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle184-validated-boot-cloud-backup.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle183-elf-loader-provenance.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle183-unfinished-cloud-backup.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle182-host-toolchain-repair.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle181-memory-qualification.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle180-cpu-qualification.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle179-boot-chain-requalification.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle178-kernel-entry-requalification.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle177-dispatch-execution-holds.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle175-memory-entry-provenance.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle174-cpu-entry-provenance.md", protocol["required_records"])
        self.assertIn("docs/checkpoints/cycle172-task-stack-ownership.md", protocol["required_records"])
        self.assertEqual(
            protocol["owner_independent_next_move_id"],
            "N13-CAPABILITY-IPC-001",
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
        self.assertEqual(len(flags), 97)
        self.assertEqual(len({flag["id"] for flag in flags}), 97)
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
        self.assertEqual(deferred_flag["status"], "open")
        self.assertIn(
            "runs/native-kernel-scheduler-deferred-readiness.json",
            deferred_flag["evidence"],
        )
        smp_scheduler_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-SMP-001"
        )
        self.assertEqual(smp_scheduler_flag["class"], "REQUIRED")
        self.assertEqual(smp_scheduler_flag["status"], "open")
        self.assertIn("docs/checkpoints/cycle203-native-smp-transactions.md", smp_scheduler_flag["evidence"])
        self.assertIn(
            "runs/native-kernel-scheduler-smp-readiness.json",
            smp_scheduler_flag["evidence"],
        )
        ap_workers_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-AP-WORKERS-001"
        )
        self.assertEqual(ap_workers_flag["class"], "REQUIRED")
        self.assertEqual(ap_workers_flag["status"], "open")
        self.assertIn(
            "runs/native-kernel-scheduler-ap-workers-readiness.json",
            ap_workers_flag["evidence"],
        )
        smp_preemption_flag = next(
            flag for flag in flags if flag["id"] == "FLAG-N12-SCHED-SMP-PREEMPT-001"
        )
        self.assertEqual(smp_preemption_flag["class"], "REQUIRED")
        self.assertEqual(smp_preemption_flag["status"], "open")
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
