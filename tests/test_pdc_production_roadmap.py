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
        self.assertEqual(summary["subphase_total"], 287)

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
        self.assertEqual(checklist["added_requirement_count"], 26)

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
        self.assertEqual(self.roadmap["baseline"]["pooleos_cycle"], 87)
        self.assertEqual(self.roadmap["baseline"]["pooleos_test_count"], 431)
        native = self.roadmap["baseline"]["native"]
        self.assertTrue(native["source_controlled"])
        self.assertTrue(all(value is False for key, value in native.items() if key != "source_controlled"))
        historical = self.roadmap["baseline"]["historical_consistency_release_gate"]
        self.assertFalse(historical["production_ready"])
        self.assertEqual(historical["native_promotion_role"], "historical_non_promoting")
        current = self.roadmap["baseline"]["native_consistency_release_gate"]
        self.assertEqual(current["passed_checks"], 65)
        self.assertEqual(current["total_checks"], 65)
        self.assertEqual(current["artifact_count"], 60)
        self.assertEqual(current["explicit_gap_count"], 20)
        self.assertFalse(current["production_ready"])
        self.assertEqual(self.roadmap["immediate_next_move"]["id"], "N0-RATIFY-001")
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
        self.assertEqual(protocol["selected_move_id"], "N2-HW-002")
        self.assertIn("runs/hardware_target_readiness.json", protocol["required_records"])
        self.assertIn("runs/native_v1_objectives_readiness.json", protocol["required_records"])
        for record in protocol["required_records"]:
            self.assertTrue((ROOT / record).is_file(), record)

    def test_flags_and_gaps_are_native_and_traceable(self) -> None:
        phase_ids = {phase["id"] for phase in self.roadmap["phases"]}
        flags = self.roadmap["implementation_flags"]
        self.assertEqual(len(flags), 23)
        self.assertEqual(len({flag["id"] for flag in flags}), 23)
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
        cpuid_flag = next(flag for flag in flags if flag["id"] == "FLAG-N2-CPUID-001")
        self.assertEqual(cpuid_flag["class"], "REQUIRED")
        self.assertEqual(cpuid_flag["status"], "closed")
        self.assertIn("tools/collect_tier1_hardware.ps1", cpuid_flag["evidence"])
        self.assertIn("runs/tier1_hardware_observation.json", cpuid_flag["evidence"])
        privileged_flag = next(flag for flag in flags if flag["id"] == "FLAG-N2-PRIVILEGED-PROBE-001")
        self.assertEqual(privileged_flag["class"], "BLOCKER")
        self.assertEqual(privileged_flag["status"], "open")
        self.assertIn("specs/tier1-hardware-capture.schema.json", privileged_flag["evidence"])
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
