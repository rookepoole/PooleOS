import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeChecklistCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifact_path = ROOT / "runs" / "pooleos_native_checklist_coverage.json"
        cls.artifact = json.loads(cls.artifact_path.read_text(encoding="utf-8"))
        cls.schema = json.loads(
            (ROOT / "specs" / "pooleos-native-checklist-coverage.schema.json").read_text(encoding="utf-8")
        )
        cls.source_path = ROOT / cls.artifact["source"]["path"]
        cls.source_bytes = cls.source_path.read_bytes()
        cls.lines = cls.source_bytes.decode("utf-8").splitlines()

    def test_artifact_matches_schema(self) -> None:
        self.assertEqual(validate_json(self.artifact, self.schema), [])

    def test_locked_source_hash_and_counts_are_exact(self) -> None:
        source = self.artifact["source"]
        self.assertEqual(hashlib.sha256(self.source_bytes).hexdigest().upper(), source["sha256"])
        self.assertEqual(source["sha256"], "A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D")
        self.assertEqual(len(self.source_bytes), source["byte_count"])
        self.assertEqual(len(self.lines), source["line_count"])
        checkbox_count = sum(bool(re.match(r"^\s*- \[[ xX~-]\]", line)) for line in self.lines)
        self.assertEqual(checkbox_count, 8998)
        self.assertEqual(source["declared_generated_implementation_item_count"], checkbox_count - 2)
        self.assertEqual(source["governing_preamble_checkbox_count"], 10)
        self.assertEqual(source["section_checkbox_count"], 8986)

    def test_all_source_lines_are_partitioned_without_gaps_or_overlap(self) -> None:
        sections = self.artifact["section_coverage"]
        self.assertEqual(sections[0]["start_line"], 17)
        self.assertEqual(sections[-1]["end_line"], 10512)
        previous_end = 16
        covered = set(range(1, 17))
        for expected_id, section in zip((f"{index:03d}" for index in range(171)), sections, strict=True):
            self.assertEqual(section["section_id"], expected_id)
            self.assertEqual(section["start_line"], previous_end + 1)
            self.assertEqual(section["line_count"], section["end_line"] - section["start_line"] + 1)
            section_lines = set(range(section["start_line"], section["end_line"] + 1))
            self.assertTrue(covered.isdisjoint(section_lines))
            covered.update(section_lines)
            previous_end = section["end_line"]
        self.assertEqual(covered, set(range(1, 10513)))
        self.assertEqual(self.artifact["unmapped_source_lines"], [])

    def test_every_section_and_checkbox_is_mapped_once(self) -> None:
        sections = self.artifact["section_coverage"]
        phase_records = self.artifact["phase_coverage"]
        mapped_ids = [section_id for phase in phase_records for section_id in phase["source_section_ids"]]
        self.assertEqual(sorted(mapped_ids), [f"{index:03d}" for index in range(171)])
        self.assertEqual(len(mapped_ids), len(set(mapped_ids)))
        section_phase = {section["section_id"]: section["phase_id"] for section in sections}
        for phase in phase_records:
            for section_id in phase["source_section_ids"]:
                self.assertEqual(section_phase[section_id], phase["phase_id"])
        self.assertEqual(sum(section["checkbox_count"] for section in sections), 8986)
        self.assertTrue(self.artifact["coverage_policy"]["every_checkbox_inherited"])
        self.assertFalse(any(section["completion_inferred"] for section in sections))

    def test_phase_and_added_requirement_inventories_are_complete(self) -> None:
        phases = self.artifact["phase_coverage"]
        self.assertEqual([phase["phase_id"] for phase in phases], [f"N{index}" for index in range(40)])
        self.assertEqual(sum(phase["source_line_count"] for phase in phases) + 16, 10512)
        self.assertEqual(sum(phase["source_checkbox_count"] for phase in phases) + 10, 8996)
        additions = self.artifact["added_requirements"]
        self.assertEqual(len(additions), 39)
        self.assertEqual(len({item["id"] for item in additions}), 39)
        digest_provider = next(item for item in additions if item["id"] == "ADD-BOOT-003")
        self.assertEqual(digest_provider["phase_id"], "N6")
        artifact_profile = next(item for item in additions if item["id"] == "ADD-BOOT-004")
        self.assertEqual(artifact_profile["phase_id"], "N5")
        initial_system = next(item for item in additions if item["id"] == "ADD-BOOT-005")
        self.assertEqual(initial_system["phase_id"], "N5")
        recovery = next(item for item in additions if item["id"] == "ADD-BOOT-006")
        self.assertEqual(recovery["phase_id"], "N5")
        self.assertIn("authenticated monotonic state", recovery["requirement"])
        symbols = next(item for item in additions if item["id"] == "ADD-BOOT-007")
        self.assertEqual(symbols["phase_id"], "N5")
        self.assertIn("image-relative diagnostic index", symbols["requirement"])
        microcode = next(item for item in additions if item["id"] == "ADD-BOOT-008")
        self.assertEqual(microcode["phase_id"], "N5")
        self.assertIn("reset-based exact known-good recovery", microcode["requirement"])
        phase_ids = {phase["phase_id"] for phase in phases}
        self.assertTrue(all(item["phase_id"] in phase_ids for item in additions))
        classes = Counter(item["id"].split("-")[1] for item in additions)
        self.assertGreaterEqual(classes["NATIVE"], 2)
        self.assertGreaterEqual(classes["ASSURE"], 2)
        self.assertGreaterEqual(classes["VIRTIO"], 2)
        self.assertEqual(classes["KERNEL"], 1)
        self.assertEqual(classes["TIER0"], 1)
        self.assertEqual(classes["PGL"], 6)

    def test_canonical_generator_reproduces_artifact_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "coverage.json"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "generate_native_checklist_coverage.py"), "--out", str(out)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(out.read_bytes(), self.artifact_path.read_bytes())

    def test_release_gate_accepts_the_native_plan_binding(self) -> None:
        check = pooleos_release_gate.check_native_architecture_plan()
        self.assertTrue(check["ok"], check["detail"])

    def test_release_gate_rejects_a_substituted_coverage_digest(self) -> None:
        roadmap = json.loads((ROOT / "runs" / "pdc_production_roadmap.json").read_text(encoding="utf-8"))
        roadmap["master_checklist"]["coverage_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            check = pooleos_release_gate.check_native_architecture_plan(roadmap_path, self.artifact_path)
        self.assertFalse(check["ok"])
        self.assertIn("coverage digest", check["detail"])


if __name__ == "__main__":
    unittest.main()
