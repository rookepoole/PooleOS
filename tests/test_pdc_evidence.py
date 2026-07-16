import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_source_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PdcEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.intake_path = ROOT / "runs" / "pdc_source_intake.json"
        cls.contract_path = ROOT / "runs" / "pdc_math_contract.json"
        cls.vectors_path = ROOT / "runs" / "pdc_golden_vectors.json"
        cls.intake = json.loads(cls.intake_path.read_text(encoding="utf-8"))
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))
        cls.vectors = json.loads(cls.vectors_path.read_text(encoding="utf-8"))

    def test_all_pdc_artifacts_validate(self) -> None:
        pairs = (
            (self.intake, "pdc-source-intake.schema.json"),
            (self.contract, "pdc-math-contract.schema.json"),
            (self.vectors, "pdc-golden-vectors.schema.json"),
        )
        for artifact, schema_name in pairs:
            schema = json.loads((ROOT / "specs" / schema_name).read_text(encoding="utf-8"))
            self.assertEqual(validate_json(artifact, schema), [], schema_name)

    def test_designated_sources_have_verified_content_addressed_copies(self) -> None:
        self.assertEqual(self.intake["summary"]["locked_source_count"], 7)
        self.assertEqual(self.intake["summary"]["verified_copy_count"], 7)
        for source in self.intake["designated_sources"]:
            stored = ROOT / source["stored_path"]
            self.assertTrue(stored.is_file(), stored)
            self.assertEqual(pdc_source_intake.sha256_file(stored), source["sha256"])
            self.assertIn(source["sha256"].lower(), stored.name)

    def test_raw_candidates_remain_indexed_and_unpromoted(self) -> None:
        candidates = self.intake["raw_artifact_candidates"]
        self.assertEqual(self.intake["summary"]["raw_candidate_count"], len(candidates))
        self.assertGreaterEqual(len(candidates), 26)
        self.assertEqual(self.intake["summary"]["raw_imported_count"], 0)
        self.assertTrue(all(candidate["status"] == "indexed_not_imported" for candidate in candidates))
        self.assertTrue(all(Path(candidate["path"]).is_file() for candidate in candidates))

    def test_contract_is_bound_to_the_exact_intake_artifact(self) -> None:
        binding = self.contract["source_binding"]
        self.assertEqual(binding["artifact_sha256"], pdc_source_intake.sha256_file(self.intake_path))
        self.assertEqual(
            binding["designated_source_set_sha256"],
            self.intake["digests"]["designated_source_set_sha256"],
        )
        self.assertTrue(self.contract["binary_model"]["strain_is_not_acceptance_predicate"])
        self.assertTrue(self.contract["variant_policy"]["pmphi_is_distinct_model"])

    def test_golden_vectors_are_bound_and_internally_counted(self) -> None:
        binding = self.vectors["math_contract_binding"]
        self.assertEqual(binding["artifact_sha256"], pdc_source_intake.sha256_file(self.contract_path))
        cases = self.vectors["cases"]
        summary = self.vectors["summary"]
        self.assertEqual(len(cases), summary["case_count"])
        self.assertEqual(summary["case_count"], summary["passed_count"])
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertTrue(all(case["oracle"]["agreement"] for case in cases))

    def test_required_edge_and_formula_cases_are_present(self) -> None:
        cases = {case["id"]: case for case in self.vectors["cases"]}
        required = {
            "binary-empty-l3",
            "binary-full-l3",
            "binary-six-support-birth-l5",
            "binary-periodic-wrap-l5",
            "planar-singleton-l5",
            "planar-rectangle-2x2",
            "planar-rectangle-3x4",
            "planar-line-5",
            "formula-rectangle-pmphi-3x4",
            "formula-cuboid-4x5x6",
            "formula-shell-4x5x6",
        }
        self.assertTrue(required.issubset(cases))
        target = cases["binary-six-support-birth-l5"]["expected"]["selected_sites"][0]
        self.assertEqual((target["support"], target["channel"], target["accepted"]), (6, "B6", True))
        rectangle = cases["planar-rectangle-3x4"]["expected"]["first_step"]
        self.assertEqual(rectangle["birth_spectrum"], {"B5": 12, "B6": 12, "B7": 16})
        self.assertEqual(rectangle["total_births"], 40)

    def test_source_intake_rejects_a_designated_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "Downloads"
            workspace = root / "PooleOS"
            downloads.mkdir()
            workspace.mkdir()
            (downloads / "authority.md").write_text("source\n", encoding="ascii")
            definition = pdc_source_intake.SourceDefinition(
                id="SRC-TEST-1",
                filename="authority.md",
                kind="markdown",
                expected_sha256="0" * 64,
                claim_role="Negative fixture for designated source hash mismatch.",
            )
            with self.assertRaises(pdc_source_intake.PdcSourceIntakeError):
                pdc_source_intake.make_source_intake(
                    workspace=workspace,
                    downloads=downloads,
                    definitions=(definition,),
                )

    def test_source_intake_rejects_a_corrupt_content_addressed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "Downloads"
            workspace = root / "PooleOS"
            downloads.mkdir()
            workspace.mkdir()
            source = downloads / "authority.md"
            source.write_text("source\n", encoding="ascii")
            digest = pdc_source_intake.sha256_file(source)
            definition = pdc_source_intake.SourceDefinition(
                id="SRC-TEST-1",
                filename=source.name,
                kind="markdown",
                expected_sha256=digest,
                claim_role="Negative fixture for a corrupt content-addressed copy.",
            )
            stored = workspace / "sources" / "pdc" / "intake" / "sha256" / f"{digest.lower()}.md"
            stored.parent.mkdir(parents=True)
            stored.write_text("corrupt\n", encoding="ascii")
            with self.assertRaises(pdc_source_intake.PdcSourceIntakeError):
                pdc_source_intake.make_source_intake(
                    workspace=workspace,
                    downloads=downloads,
                    definitions=(definition,),
                )

    def test_release_gate_accepts_the_bound_pdc_chain(self) -> None:
        self.assertTrue(pooleos_release_gate.check_pdc_source_intake(self.intake_path)["ok"])
        self.assertTrue(pooleos_release_gate.check_pdc_math_contract(self.contract_path, self.intake_path)["ok"])
        self.assertTrue(pooleos_release_gate.check_pdc_golden_vectors(self.vectors_path, self.contract_path)["ok"])

    def test_release_gate_rejects_substituted_contract_and_vector_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_contract = dict(self.contract)
            bad_contract["source_binding"] = dict(self.contract["source_binding"])
            bad_contract["source_binding"]["artifact_sha256"] = "0" * 64
            contract_path = root / "contract.json"
            contract_path.write_text(json.dumps(bad_contract), encoding="utf-8")
            self.assertFalse(pooleos_release_gate.check_pdc_math_contract(contract_path, self.intake_path)["ok"])

            bad_vectors = dict(self.vectors)
            bad_vectors["math_contract_binding"] = dict(self.vectors["math_contract_binding"])
            bad_vectors["math_contract_binding"]["artifact_sha256"] = "0" * 64
            vectors_path = root / "vectors.json"
            vectors_path.write_text(json.dumps(bad_vectors), encoding="utf-8")
            self.assertFalse(pooleos_release_gate.check_pdc_golden_vectors(vectors_path, self.contract_path)["ok"])


if __name__ == "__main__":
    unittest.main()
