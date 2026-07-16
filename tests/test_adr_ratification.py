import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import adr_ratification  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import generate_adr_ratification_readiness  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


CONTRACT_PATHS = (
    "specs/adr-ratification-policy.json",
    "specs/adr-ratification-policy.schema.json",
    "specs/adr-ratification-manifest.schema.json",
    "specs/adr-ratification-readiness.schema.json",
    "specs/adr-ratification-receipt.schema.json",
    "specs/native-architecture-constitution.json",
    "specs/native-v1-objectives.json",
    "specs/native-v1-objectives.schema.json",
    "specs/pooleos-kernel-charter.md",
    "specs/native-release-architecture-policy.json",
    "docs/publication-boundary.md",
    "security/owner-adr-signers.allowed",
    "security/revoked-adr-signers",
    *(f"docs/adr/{name}" for name in adr_ratification.ADR_NAMES),
)


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class AdrRatificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readiness_path = ROOT / adr_ratification.READINESS_RELATIVE
        cls.readiness = json.loads(cls.readiness_path.read_text(encoding="utf-8"))
        cls.readiness_schema = json.loads(
            (ROOT / adr_ratification.READINESS_SCHEMA_RELATIVE).read_text(encoding="utf-8")
        )
        cls.policy = adr_ratification.load_policy(ROOT)

    def _copy_contract(self, destination: Path) -> None:
        for relative in CONTRACT_PATHS:
            source = ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def _generate_test_signer(self, parent: Path, repo: Path) -> Path:
        key = parent / "untrusted_test_only_ed25519"
        completed = run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "PooleOS untrusted test only", "-f", str(key)],
            cwd=parent,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        public_key = key.with_suffix(".pub").read_text(encoding="utf-8").strip()
        namespace = self.policy["signature"]["namespace"]
        (repo / "security" / "owner-adr-signers.allowed").write_text(
            f'rookepoole namespaces="git,{namespace}" {public_key}\n',
            encoding="utf-8",
            newline="\n",
        )
        return key

    def _prepare_and_sign(self, parent: Path, repo: Path, *, namespace: str | None = None) -> tuple[Path, Path, Path]:
        key = self._generate_test_signer(parent, repo)
        manifest = adr_ratification.build_manifest(
            repo,
            owner_accept_all_exact=True,
            owner_accept_objectives_exact=True,
            accept_software_key_risk=True,
        )
        manifest_path = repo / adr_ratification.MANIFEST_RELATIVE
        adr_ratification.write_json(manifest, manifest_path)
        namespace = namespace or self.policy["signature"]["namespace"]
        completed = run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(key),
                "-n",
                namespace,
                "-O",
                "hashalg=sha512",
                str(manifest_path),
            ],
            cwd=repo,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        signature_path = repo / adr_ratification.SIGNATURE_RELATIVE
        self.assertTrue(signature_path.is_file())
        return key, manifest_path, signature_path

    def test_policy_and_current_readiness_are_schema_valid_and_non_promoting(self) -> None:
        policy_schema = json.loads((ROOT / adr_ratification.POLICY_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(validate_json(self.policy, policy_schema), [])
        self.assertEqual(validate_json(self.readiness, self.readiness_schema), [])
        self.assertEqual(self.readiness["status"], "pending_owner_action")
        self.assertEqual(self.readiness["adr_set"]["present_count"], 7)
        self.assertEqual(self.readiness["adr_set"]["pending_owner_disposition"], ["ADR-0003", "ADR-0004"])
        self.assertEqual(self.readiness["decision_inputs"]["required_bound_source_count"], 6)
        self.assertEqual(self.readiness["decision_inputs"]["objectives"]["target_count"], 38)
        self.assertEqual(self.readiness["decision_inputs"]["objectives"]["measured_target_count"], 0)
        self.assertTrue(self.readiness["decision_inputs"]["objectives"]["owner_ratification_pending"])
        self.assertEqual(self.readiness["trust_bootstrap"]["trusted_signer_count"], 0)
        self.assertTrue(self.readiness["summary"]["ready_for_owner_action"])
        self.assertFalse(self.readiness["summary"]["ready_for_signature"])
        self.assertEqual(self.readiness["summary"]["blocking_owner_action_count"], 6)
        self.assertEqual(self.readiness["summary"]["defined_negative_control_count"], 12)
        self.assertFalse(self.readiness["production_promotion_allowed"])
        self.assertFalse(self.readiness["production_ready"])
        gate = pooleos_release_gate.check_adr_ratification_readiness()
        self.assertTrue(gate["ok"], gate["detail"])
        self.assertIn("status=pending_owner_action", gate["detail"])

    def test_readiness_generator_reproduces_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "readiness.json"
            code = generate_adr_ratification_readiness.main(["--out", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(out.read_bytes(), self.readiness_path.read_bytes())

    def test_manifest_requires_explicit_acceptance_and_one_scoped_signer(self) -> None:
        with self.assertRaisesRegex(ValueError, "owner_accept_all_exact"):
            adr_ratification.build_manifest(
                ROOT,
                owner_accept_all_exact=False,
                owner_accept_objectives_exact=False,
            )
        with self.assertRaisesRegex(ValueError, "owner_accept_objectives_exact"):
            adr_ratification.build_manifest(
                ROOT,
                owner_accept_all_exact=True,
                owner_accept_objectives_exact=False,
            )
        with self.assertRaisesRegex(ValueError, "exactly one owner bootstrap signer"):
            adr_ratification.build_manifest(
                ROOT,
                owner_accept_all_exact=True,
                owner_accept_objectives_exact=True,
            )

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            self._generate_test_signer(parent, repo)
            manifest = adr_ratification.build_manifest(
                repo,
                owner_accept_all_exact=True,
                owner_accept_objectives_exact=True,
                accept_software_key_risk=True,
            )
            self.assertEqual(len(manifest["bound_sources"]), 6)
            self.assertEqual(manifest["objectives_acceptance"]["target_count"], 38)
            self.assertFalse(manifest["objectives_acceptance"]["measurement_evidence_accepted"])
            self.assertEqual(
                {binding["path"] for binding in manifest["bound_sources"]},
                set(adr_ratification.REQUIRED_BOUND_SOURCES),
            )

    def test_current_receipt_state_is_pending_and_never_promotes(self) -> None:
        receipt = adr_ratification.build_receipt(ROOT, observed_at_utc="2026-07-16T00:00:00Z")
        self.assertEqual(receipt["status"], "pending_owner_action")
        self.assertFalse(receipt["detached_signature"]["verified"])
        self.assertFalse(receipt["ratification"]["all_required_cryptographically_ratified"])
        self.assertFalse(receipt["ratification"]["objectives_definitions_cryptographically_ratified"])
        self.assertFalse(receipt["architecture_ratification_verified"])
        self.assertFalse(receipt["production_promotion_allowed"])
        self.assertFalse(receipt["production_ready"])

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            policy_path = repo / adr_ratification.POLICY_RELATIVE
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["required_bound_sources"].remove("specs/native-v1-objectives.schema.json")
            policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8", newline="\n")
            invalid = adr_ratification.build_receipt(repo, observed_at_utc="2026-07-16T00:00:00Z")
            self.assertEqual(invalid["status"], "invalid")
            self.assertFalse(next(check for check in invalid["checks"] if check["name"] == "policy_schema_valid")["ok"])

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH ssh-keygen is unavailable")
    def test_real_detached_signature_verifies_but_tag_gate_stays_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            _, manifest_path, signature_path = self._prepare_and_sign(parent, repo)
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "detached_signature_verified_tag_pending")
            self.assertTrue(receipt["detached_signature"]["verified"])
            self.assertEqual(receipt["ratification"]["accepted_exact_count"], 7)
            self.assertTrue(receipt["ratification"]["objectives_definitions_cryptographically_ratified"])
            self.assertFalse(receipt["ratification"]["objectives_measurements_complete"])
            self.assertFalse(receipt["signed_tag"]["present"])
            self.assertFalse(receipt["production_promotion_allowed"])

    @unittest.skipUnless(shutil.which("ssh-keygen") and shutil.which("git"), "Git/OpenSSH signing is unavailable")
    def test_real_signed_annotated_tag_binds_manifest_and_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            key, manifest_path, signature_path = self._prepare_and_sign(parent, repo)
            commands = (
                ["git", "init", "-b", "main"],
                ["git", "config", "user.name", "PooleOS Test Only"],
                ["git", "config", "user.email", "pooleos-test-only@example.invalid"],
                ["git", "add", "-A"],
                ["git", "commit", "-m", "Untrusted ADR ratification verifier fixture"],
                [
                    "git",
                    "-c",
                    "gpg.format=ssh",
                    "-c",
                    f"user.signingkey={key}",
                    "tag",
                    "-s",
                    self.policy["tag"]["name"],
                    "-m",
                    "Untrusted PooleOS test-only ratification tag",
                ],
            )
            for command in commands:
                completed = run(command, cwd=repo)
                self.assertEqual(completed.returncode, 0, completed.stdout)
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "local_tag_verified_publication_pending")
            self.assertTrue(receipt["signed_tag"]["signature_verified"])
            self.assertTrue(receipt["signed_tag"]["contains_manifest"])
            self.assertTrue(receipt["signed_tag"]["contains_signature"])
            self.assertFalse(receipt["remote_publication"]["published"])
            self.assertFalse(receipt["production_promotion_allowed"])
            remote_receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                verify_remote=True,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(remote_receipt["status"], "invalid")
            self.assertFalse(remote_receipt["remote_publication"]["remote_url_match"])
            self.assertFalse(remote_receipt["production_promotion_allowed"])

            target_commit = receipt["signed_tag"]["target_commit"]
            published = {
                "required": True,
                "checked": True,
                "remote": self.policy["remote_publication"]["remote"],
                "expected_remote_url": self.policy["repository"]["remote_url"],
                "configured_remote_url": self.policy["repository"]["remote_url"],
                "remote_url_match": True,
                "default_branch": self.policy["repository"]["default_branch"],
                "main_commit": target_commit,
                "tag_object": "A" * 40,
                "peeled_commit": target_commit,
                "exact_main_tip_match": True,
                "published": True,
            }
            with mock.patch.object(adr_ratification, "verify_remote_publication", return_value=published):
                verified = adr_ratification.build_receipt(
                    repo,
                    manifest_path=manifest_path,
                    signature_path=signature_path,
                    verify_remote=True,
                    observed_at_utc="2026-07-16T00:00:00Z",
                )
            self.assertEqual(verified["status"], "verified")
            self.assertTrue(verified["architecture_ratification_verified"])
            self.assertFalse(verified["production_promotion_allowed"])
            self.assertFalse(verified["ratification"]["objectives_measurements_complete"])
            self.assertFalse(verified["ratification"]["full_n0_exit_evidence_present"])

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH ssh-keygen is unavailable")
    def test_tampered_adr_is_rejected_after_manifest_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            _, manifest_path, signature_path = self._prepare_and_sign(parent, repo)
            adr = repo / "docs" / "adr" / adr_ratification.ADR_NAMES[0]
            adr.write_text(adr.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")
            self.assertTrue(any("does not match" in error for error in receipt["errors"]))
            self.assertFalse(receipt["production_promotion_allowed"])

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH ssh-keygen is unavailable")
    def test_tampered_objectives_or_schema_are_rejected_after_manifest_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            _, manifest_path, signature_path = self._prepare_and_sign(parent, repo)
            objectives_path = repo / "specs" / "native-v1-objectives.json"
            schema_path = repo / "specs" / "native-v1-objectives.schema.json"
            objectives_bytes = objectives_path.read_bytes()

            objectives = json.loads(objectives_path.read_text(encoding="utf-8"))
            objectives["targets"][0]["evidence_requirement"] += " Changed after manifest."
            objectives_path.write_text(json.dumps(objectives, indent=2) + "\n", encoding="utf-8", newline="\n")
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")
            self.assertTrue(any("does not match" in error for error in receipt["errors"]))

            objectives_path.write_bytes(objectives_bytes)
            schema_path.write_bytes(schema_path.read_bytes() + b"\n")
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")
            self.assertTrue(any("does not match" in error for error in receipt["errors"]))
            self.assertFalse(receipt["production_promotion_allowed"])

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH ssh-keygen is unavailable")
    def test_wrong_namespace_signature_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            _, manifest_path, signature_path = self._prepare_and_sign(parent, repo, namespace="wrong-test-namespace")
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")
            self.assertFalse(receipt["detached_signature"]["verified"])

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH ssh-keygen is unavailable")
    def test_unknown_signer_and_malformed_signature_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            _, manifest_path, signature_path = self._prepare_and_sign(parent, repo)
            second_key = parent / "unknown_test_key"
            completed = run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(second_key)],
                cwd=parent,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            second_public = second_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
            namespace = self.policy["signature"]["namespace"]
            (repo / "security" / "owner-adr-signers.allowed").write_text(
                f'rookepoole namespaces="git,{namespace}" {second_public}\n', encoding="utf-8"
            )
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")
            signature_path.write_text("not an SSH signature\n", encoding="utf-8")
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH ssh-keygen is unavailable")
    def test_noncanonical_manifest_and_revoked_key_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            repo = parent / "repo"
            repo.mkdir()
            self._copy_contract(repo)
            _, manifest_path, signature_path = self._prepare_and_sign(parent, repo)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            _, errors = adr_ratification.validate_manifest(repo, manifest_path)
            self.assertTrue(any("not canonical" in error for error in errors))

            adr_ratification.write_json(manifest, manifest_path)
            public_key = (repo / "security" / "owner-adr-signers.allowed").read_text(encoding="utf-8").split()
            key_index = next(index for index, token in enumerate(public_key) if token == "ssh-ed25519")
            (repo / "security" / "revoked-adr-signers").write_text(
                f"{public_key[key_index]} {public_key[key_index + 1]}\n", encoding="utf-8"
            )
            receipt = adr_ratification.build_receipt(
                repo,
                manifest_path=manifest_path,
                signature_path=signature_path,
                observed_at_utc="2026-07-16T00:00:00Z",
            )
            self.assertEqual(receipt["status"], "invalid")
            self.assertFalse(receipt["detached_signature"]["verified"])


if __name__ == "__main__":
    unittest.main()
