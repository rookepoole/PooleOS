import copy
import csv
import io
import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_verifier_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PdcVerifierReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_intake_path = ROOT / "runs" / "pdc_source_intake.json"
        cls.math_contract_path = ROOT / "runs" / "pdc_math_contract.json"
        cls.verifier_intake_path = ROOT / "runs" / "pdc_verifier_intake.json"
        cls.reproduction_path = ROOT / "runs" / "pdc_verifier_reproduction.json"
        cls.verifier_intake = json.loads(cls.verifier_intake_path.read_text(encoding="utf-8"))
        cls.reproduction = json.loads(cls.reproduction_path.read_text(encoding="utf-8"))

    def test_artifacts_validate_and_bind_to_exact_parents(self) -> None:
        for artifact, schema_name in (
            (self.verifier_intake, "pdc-verifier-intake.schema.json"),
            (self.reproduction, "pdc-verifier-reproduction.schema.json"),
        ):
            schema = json.loads((ROOT / "specs" / schema_name).read_text(encoding="utf-8"))
            self.assertEqual(validate_json(artifact, schema), [], schema_name)

        intake_bindings = self.verifier_intake["bindings"]
        self.assertEqual(
            intake_bindings["source_intake_sha256"],
            pdc_verifier_intake.sha256_file(self.source_intake_path),
        )
        self.assertEqual(
            intake_bindings["math_contract_sha256"],
            pdc_verifier_intake.sha256_file(self.math_contract_path),
        )
        reproduction_bindings = self.reproduction["bindings"]
        self.assertEqual(
            reproduction_bindings["verifier_intake_sha256"],
            pdc_verifier_intake.sha256_file(self.verifier_intake_path),
        )
        self.assertEqual(
            reproduction_bindings["selected_source_set_sha256"],
            self.verifier_intake["digests"]["selected_source_set_sha256"],
        )

    def test_selected_sources_and_preserved_outputs_match_receipt_hashes(self) -> None:
        self.assertEqual(self.verifier_intake["summary"]["verified_copy_count"], 4)
        for source in self.verifier_intake["selected_sources"]:
            stored = ROOT / source["stored_path"]
            self.assertTrue(stored.is_file(), stored)
            self.assertEqual(pdc_verifier_intake.sha256_file(stored), source["sha256"])
            self.assertIn(source["sha256"].lower(), stored.name)

        outputs = [
            output
            for execution in self.reproduction["source_executions"]
            for output in execution["required_outputs"]
        ]
        self.assertEqual(len(outputs), 6)
        for output in outputs:
            preserved = ROOT / output["preserved_path"]
            self.assertTrue(preserved.is_file(), preserved)
            self.assertEqual(pdc_verifier_intake.sha256_file(preserved), output["sha256"])

    def test_archive_manifests_and_lineage_are_complete(self) -> None:
        summary = self.verifier_intake["summary"]
        self.assertEqual(summary["safe_archive_count"], 3)
        self.assertEqual(summary["manifest_entry_count"], 46)
        self.assertEqual(summary["verified_manifest_entry_count"], 46)
        self.assertEqual(summary["failed_check_count"], 0)
        self.assertTrue(all(item["status"] == "pass" for item in self.verifier_intake["archive_security"]))
        self.assertTrue(all(item["status"] == "pass" for item in self.verifier_intake["embedded_manifests"]))
        self.assertTrue(all(item["ok"] for item in self.verifier_intake["lineage_checks"]))
        self.assertEqual(
            self.verifier_intake["errata"],
            [
                {
                    "id": "ERR-PLANAR-MANIFEST-PATH-001",
                    "severity": "documented_nonblocking",
                    "description": (
                        "The v1.1 manifest declares data/empirical_planar_relaxation_timeseries_scaffold.csv, "
                        "while the archive member omits _scaffold; declared bytes and SHA-256 match that member exactly."
                    ),
                    "affected_closed_family": False,
                    "status": "resolved_by_exact_hash_alias",
                }
            ],
        )

    def test_all_six_exact_family_domains_are_reproduced(self) -> None:
        expected = {
            "rectangle": 841,
            "line_hole": 80,
            "arbitrary_mask": 720,
            "inversion": 1225,
            "solid_cuboid": 729,
            "surface_shell": 729,
        }
        actual = {item["id"]: item for item in self.reproduction["family_results"]}
        self.assertEqual(set(actual), set(expected))
        for family_id, case_count in expected.items():
            family = actual[family_id]
            self.assertEqual(family["status"], "pass")
            for field in (
                "declared_case_count",
                "published_case_count",
                "source_execution_case_count",
                "independent_case_count",
            ):
                self.assertEqual(family[field], case_count, (family_id, field))
            self.assertTrue(family["source_execution_canonical_lf_match"])
            self.assertFalse(family["source_execution_raw_byte_match"])
            self.assertEqual(family["source_execution_semantic_mismatch_count"], 0)
            self.assertEqual(family["independent_source_mismatch_count"], 0)
            self.assertEqual(family["formula_mismatch_count"], 0)
            self.assertEqual(family["secondary_oracle_mismatch_count"], 0)

        summary = self.reproduction["summary"]
        self.assertEqual(sum(expected.values()), 4324)
        self.assertEqual(summary["independent_case_count"], 4324)
        self.assertEqual(summary["source_execution_case_count"], 4324)
        self.assertEqual(summary["mismatch_count"], 0)

    def test_serialization_drift_is_only_newline_normalization(self) -> None:
        outputs = [
            output
            for execution in self.reproduction["source_executions"]
            for output in execution["required_outputs"]
        ]
        self.assertEqual(self.reproduction["summary"]["exact_byte_match_file_count"], 0)
        self.assertEqual(self.reproduction["summary"]["canonical_lf_match_file_count"], 6)
        self.assertEqual(self.reproduction["summary"]["serialization_drift_file_count"], 6)
        for output in outputs:
            raw = (ROOT / output["preserved_path"]).read_bytes()
            self.assertIn(b"\r\n", raw)
            self.assertFalse(output["byte_match"])
            self.assertTrue(output["canonical_lf_match"])
            self.assertEqual(output["canonical_lf_sha256"], output["published_canonical_lf_sha256"])

    def test_archive_safety_rejects_traversal_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "unsafe.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with ZipFile(archive_path, "w") as archive:
                    archive.writestr("../escape.txt", b"bad")
                    archive.writestr("duplicate.txt", b"first")
                    archive.writestr("duplicate.txt", b"second")
            result = pdc_verifier_intake.inspect_zip_safety(archive_path)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["unsafe_names"], ["../escape.txt"])
            self.assertEqual(result["duplicate_names"], ["duplicate.txt"])

    def test_manifest_verification_rejects_a_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "manifest-mismatch.zip"
            rows = io.StringIO(newline="")
            writer = csv.DictWriter(rows, fieldnames=("relative_path", "sha256", "bytes"), lineterminator="\n")
            writer.writeheader()
            writer.writerow({"relative_path": "data.csv", "sha256": "0" * 64, "bytes": 7})
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("manifest.csv", rows.getvalue().encode("ascii"))
                archive.writestr("data.csv", b"actual\n")
            result = pdc_verifier_intake.verify_zip_manifest(
                archive_path,
                manifest_member="manifest.csv",
            )
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["failed_entry_count"], 1)
            self.assertFalse(result["entries"][0]["hash_match"])

    def test_release_gate_accepts_exact_verifier_chain(self) -> None:
        intake = pooleos_release_gate.check_pdc_verifier_intake(
            self.verifier_intake_path,
            self.source_intake_path,
            self.math_contract_path,
        )
        reproduction = pooleos_release_gate.check_pdc_verifier_reproduction(
            self.reproduction_path,
            self.verifier_intake_path,
            self.math_contract_path,
        )
        self.assertTrue(intake["ok"], intake)
        self.assertTrue(reproduction["ok"], reproduction)

    def test_release_gate_rejects_tampered_verifier_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_intake = copy.deepcopy(self.verifier_intake)
            bad_intake["bindings"]["source_intake_sha256"] = "0" * 64
            bad_intake_path = root / "bad-intake.json"
            bad_intake_path.write_text(json.dumps(bad_intake), encoding="utf-8")
            self.assertFalse(
                pooleos_release_gate.check_pdc_verifier_intake(
                    bad_intake_path,
                    self.source_intake_path,
                    self.math_contract_path,
                )["ok"]
            )

            bad_reproduction = copy.deepcopy(self.reproduction)
            bad_reproduction["summary"]["mismatch_count"] = 1
            bad_reproduction_path = root / "bad-reproduction.json"
            bad_reproduction_path.write_text(json.dumps(bad_reproduction), encoding="utf-8")
            self.assertFalse(
                pooleos_release_gate.check_pdc_verifier_reproduction(
                    bad_reproduction_path,
                    self.verifier_intake_path,
                    self.math_contract_path,
                )["ok"]
            )


if __name__ == "__main__":
    unittest.main()
