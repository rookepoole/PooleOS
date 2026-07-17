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
        self.assertEqual(len(self.artifact["bound_sources"]), 62)
        bound_paths = {binding["path"] for binding in self.artifact["bound_sources"]}
        self.assertIn(
            "runs/adr_ratification_readiness.json",
            bound_paths,
        )
        self.assertIn("runs/n0_owner_decision_packet.json", bound_paths)
        self.assertIn("docs/n0-owner-decision-packet.md", bound_paths)
        self.assertIn("runs/n0_owner_response_receipt.json", bound_paths)
        self.assertIn("docs/n0-owner-response-receipt.md", bound_paths)
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
        self.assertIn("runs/native_boot_config_readiness.json", bound_paths)
        self.assertIn("runs/native_elf_loader_readiness.json", bound_paths)
        self.assertIn("specs/native-boot-config-contract.json", bound_paths)
        self.assertIn("specs/native-boot-config-golden-vectors.json", bound_paths)
        self.assertIn("docs/native-boot-config.md", bound_paths)
        self.assertIn("specs/native-elf-loader-contract.json", bound_paths)
        self.assertIn("specs/native-elf-loader-contract.schema.json", bound_paths)
        self.assertIn("specs/native-elf-loader-golden-vectors.json", bound_paths)
        self.assertIn("specs/native-elf-loader-golden-vectors.schema.json", bound_paths)
        self.assertIn("specs/native-elf-loader-readiness.schema.json", bound_paths)
        self.assertIn("docs/native-elf-loader.md", bound_paths)
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
