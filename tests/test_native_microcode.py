from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_microcode as pmcu1  # noqa: E402


class NativeMicrocodeTests(unittest.TestCase):
    def test_contract_and_vectors_are_canonical(self) -> None:
        contract = pmcu1.read_json(ROOT / pmcu1.CONTRACT_RELATIVE)
        golden = pmcu1.read_json(ROOT / pmcu1.GOLDEN_RELATIVE)
        self.assertEqual(pmcu1.contract_errors(contract), [])
        self.assertEqual(pmcu1.golden_errors(golden), [])
        self.assertEqual(contract, pmcu1.expected_contract())
        self.assertEqual(golden, pmcu1.make_golden_vectors())

    def test_generator_check_passes_without_writing(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_native_microcode_vectors.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("PMCU1_GENERATION PASS", completed.stdout)

    def test_checked_in_fixtures_match_oracle(self) -> None:
        expected = {
            "pmcu1-canonical.bin": pmcu1.canonical_bundle(),
            "pmcu1-minimal.bin": pmcu1.minimal_bundle(),
            "pmcu1-boundary.bin": pmcu1.boundary_bundle(),
        }
        for name, data in expected.items():
            self.assertEqual((ROOT / "specs/fixtures" / name).read_bytes(), data)
            self.assertEqual(pmcu1.parse(data).raw, data)

    def test_normal_selection_is_exact_and_monotonic(self) -> None:
        bundle = pmcu1.parse(pmcu1.canonical_bundle())
        selected = pmcu1.select_patch(
            bundle,
            cpuid_signature=pmcu1.TARGET_CPUID_SIGNATURE,
            platform_id=0,
            current_revision=pmcu1.SYNTHETIC_REVISION_BASE + 0x10,
            authenticated_rollback_floor=pmcu1.CANONICAL_SECURITY_FLOOR,
            boot_mode=pmcu1.MODE_NORMAL,
        )
        self.assertEqual(selected.decision, pmcu1.DECISION_APPLY)
        self.assertEqual(selected.patch.revision, pmcu1.CANONICAL_PREFERRED_REVISION)

    def test_recovery_requires_reset_instead_of_downgrade(self) -> None:
        bundle = pmcu1.parse(pmcu1.canonical_bundle())
        selected = pmcu1.select_patch(
            bundle,
            cpuid_signature=pmcu1.TARGET_CPUID_SIGNATURE,
            platform_id=0,
            current_revision=pmcu1.CANONICAL_PREFERRED_REVISION,
            authenticated_rollback_floor=pmcu1.CANONICAL_SECURITY_FLOOR,
            boot_mode=pmcu1.MODE_PREVIOUS_KNOWN_GOOD,
            revoked_revisions=(pmcu1.CANONICAL_PREFERRED_REVISION,),
        )
        self.assertEqual(selected.decision, pmcu1.DECISION_RESET_FOR_KNOWN_GOOD)
        self.assertEqual(selected.patch.revision, pmcu1.CANONICAL_KNOWN_GOOD_REVISION)

    def test_payload_and_header_mutations_fail_closed(self) -> None:
        payload = bytearray(pmcu1.canonical_bundle())
        payload[-1] ^= 1
        with self.assertRaisesRegex(pmcu1.MicrocodeError, "pmcu_body_digest"):
            pmcu1.parse(bytes(payload))
        header = bytearray(pmcu1.canonical_bundle())
        header[224] ^= 1
        with self.assertRaisesRegex(pmcu1.MicrocodeError, "pmcu_header_digest"):
            pmcu1.parse(bytes(header))

    def test_unsigned_development_context_is_denied(self) -> None:
        bundle = pmcu1.parse(pmcu1.canonical_bundle())
        development = pmcu1.development_apply_context(bundle)
        errors = pmcu1.apply_plan_errors(bundle, development)
        self.assertIn("pmcu_activation_outer_signature", errors)
        self.assertIn("pmcu_activation_vendor_signature", errors)
        self.assertIn("pmcu_activation_apply_authority", errors)
        with self.assertRaisesRegex(pmcu1.MicrocodeError, "pmcu_activation_outer_signature"):
            pmcu1.authorize_apply_plan(bundle, development)

    def test_each_apply_precondition_fails_independently(self) -> None:
        bundle = pmcu1.parse(pmcu1.canonical_bundle())
        qualified = pmcu1.synthetic_qualified_apply_context(bundle)
        self.assertEqual(pmcu1.apply_plan_errors(bundle, qualified), [])
        mutations = (
            {"vendor_container_validated": False},
            {"redistribution_authorized": False},
            {"revocation_state_authenticated": False},
            {"cpuid_observation_trusted": False},
            {"revision_observation_trusted": False},
            {"processor_set_quiesced": False},
            {"before_affected_features": False},
            {"before_user_scheduling": False},
            {"apply_authority_granted": False},
            {"qualification_only": False},
        )
        for mutation in mutations:
            self.assertTrue(
                pmcu1.apply_plan_errors(bundle, dataclasses.replace(qualified, **mutation))
            )

    def test_post_apply_requires_all_processors_and_policy_recheck(self) -> None:
        bundle = pmcu1.parse(pmcu1.canonical_bundle())
        selected = pmcu1.select_patch(
            bundle,
            cpuid_signature=pmcu1.TARGET_CPUID_SIGNATURE,
            platform_id=0,
            current_revision=pmcu1.SYNTHETIC_REVISION_BASE + 0x10,
            authenticated_rollback_floor=pmcu1.CANONICAL_SECURITY_FLOOR,
            boot_mode=pmcu1.MODE_NORMAL,
        )
        observation = pmcu1.PostApplyObservation(
            selected.patch.patch_id,
            selected.patch.revision,
            (pmcu1.SYNTHETIC_REVISION_BASE + 0x10,) * 2,
            (selected.patch.revision,) * 2,
            pmcu1.TARGET_CPUID_SIGNATURE,
            pmcu1.TARGET_CPUID_SIGNATURE,
            hashlib.sha256(b"before").hexdigest().upper(),
            hashlib.sha256(b"after").hexdigest().upper(),
            True,
            True,
            True,
            False,
            False,
        )
        self.assertEqual(pmcu1.post_apply_errors(bundle, selected, observation), [])
        mixed = dataclasses.replace(
            observation,
            after_revisions=(selected.patch.revision, pmcu1.CANONICAL_KNOWN_GOOD_REVISION),
        )
        self.assertIn("pmcu_verify_mixed_after", pmcu1.post_apply_errors(bundle, selected, mixed))

    def test_readiness_receipt_remains_bound_and_non_promoting(self) -> None:
        path = ROOT / pmcu1.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PMCU1 qualification receipt has not been generated")
        readiness = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(pmcu1.readiness_errors(readiness), [])
        self.assertFalse(readiness["production_ready"])
        self.assertFalse(readiness["production_promotion_allowed"])
        self.assertFalse(readiness["claims"]["microcode_applied"])


if __name__ == "__main__":
    unittest.main()
