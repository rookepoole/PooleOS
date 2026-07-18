import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_trust as trust  # noqa: E402


MANIFEST = "11" * 32
KERNEL = "22" * 32
RETAINED = "33" * 32
REVOCATION = "44" * 32


def records(*, signed: bool = False, authenticated: bool = False):
    policy = trust.encode_policy(
        manifest_sha256=MANIFEST,
        kernel_sha256=KERNEL,
        retained_set_sha256=RETAINED,
        revocation_set_sha256=REVOCATION,
        signed=signed,
    )
    state = trust.encode_state(
        policy_sha256=trust.sha256_bytes(policy),
        manifest_sha256=MANIFEST,
        kernel_sha256=KERNEL,
        retained_set_sha256=RETAINED,
        authenticated_backend=authenticated,
    )
    observed = trust.ObservedBoot(MANIFEST, KERNEL, RETAINED, REVOCATION, 1, 1)
    return policy, state, observed


def rehash_policy(data: bytearray) -> bytes:
    data[224:256] = hashlib.sha256(data[:224]).digest()
    return bytes(data)


def rehash_state(data: bytearray) -> bytes:
    data[224:256] = hashlib.sha256(data[:224]).digest()
    return bytes(data)


class NativeBootTrustTests(unittest.TestCase):
    def test_development_records_cross_bind_then_deny_without_effects(self) -> None:
        policy, state, observed = records()
        summary = trust.validate_development(policy, state, observed)
        self.assertEqual("pbtrust_policy_unsigned", summary["denial"])
        self.assertEqual(14, summary["binding_count"])
        self.assertEqual(0, summary["authority_grants"])
        self.assertEqual(0, summary["state_writes"])
        self.assertEqual(0, summary["signature_verifications"])

    def test_exact_corruption_fails_before_authorization(self) -> None:
        policy, _, _ = records()
        changed = bytearray(policy)
        changed[100] ^= 1
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.parse_policy(bytes(changed))
        self.assertEqual("pbtrust_policy_body_digest", caught.exception.code)

    def test_recomputed_policy_cannot_substitute_kernel(self) -> None:
        policy, state, observed = records()
        changed = bytearray(policy)
        changed[96] ^= 1
        changed = rehash_policy(changed)
        changed_state = bytearray(state)
        changed_state[64:96] = hashlib.sha256(changed).digest()
        changed_state = rehash_state(changed_state)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.validate_development(changed, changed_state, observed)
        self.assertEqual("pbtrust_binding_kernel", caught.exception.code)

    def test_state_cannot_substitute_manifest(self) -> None:
        policy, state, observed = records()
        changed = bytearray(state)
        changed[96] ^= 1
        changed = rehash_state(changed)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.validate_development(policy, changed, observed)
        self.assertEqual("pbtrust_binding_state_manifest", caught.exception.code)

    def test_state_cannot_bind_another_policy(self) -> None:
        policy, state, observed = records()
        changed = bytearray(state)
        changed[64] ^= 1
        changed = rehash_state(changed)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.validate_development(policy, changed, observed)
        self.assertEqual("pbtrust_binding_policy_state", caught.exception.code)

    def test_manifest_rollback_precedes_authentication(self) -> None:
        policy, state, observed = records()
        changed = bytearray(state)
        changed[48:56] = (2).to_bytes(8, "little")
        changed = rehash_state(changed)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.validate_development(policy, changed, observed)
        self.assertEqual("pbtrust_rollback_manifest_version", caught.exception.code)

    def test_state_generation_rollback_precedes_authentication(self) -> None:
        policy, _, observed = records()
        changed_policy = bytearray(policy)
        changed_policy[40:48] = (2).to_bytes(8, "little")
        changed_policy = rehash_policy(changed_policy)
        state = trust.encode_state(
            policy_sha256=trust.sha256_bytes(changed_policy),
            manifest_sha256=MANIFEST,
            kernel_sha256=KERNEL,
            retained_set_sha256=RETAINED,
        )
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.validate_development(changed_policy, state, observed)
        self.assertEqual("pbtrust_rollback_state_generation", caught.exception.code)

    def test_incomplete_copy_is_never_accepted(self) -> None:
        _, state, _ = records()
        changed = bytearray(state)
        changed[18:20] = (0).to_bytes(2, "little")
        changed = rehash_state(changed)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.parse_state(changed)
        self.assertEqual("pbtrust_state_commit", caught.exception.code)

    def test_generation_two_requires_previous_state_digest(self) -> None:
        policy, _, _ = records()
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.parse_state(
                trust.encode_state(
                    policy_sha256=trust.sha256_bytes(policy),
                    manifest_sha256=MANIFEST,
                    kernel_sha256=KERNEL,
                    retained_set_sha256=RETAINED,
                    state_generation=2,
                )
            )
        self.assertEqual("pbtrust_state_previous", caught.exception.code)

    def test_signed_shape_does_not_self_authenticate(self) -> None:
        policy, state, observed = records(signed=True, authenticated=True)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.authorize(
                trust.parse_policy(policy),
                trust.parse_state(state),
                observed,
                trust.VerificationEvidence.development(),
            )
        self.assertEqual("pbtrust_policy_authentication", caught.exception.code)

    def test_each_external_evidence_gate_fails_closed(self) -> None:
        policy, state, observed = records(signed=True, authenticated=True)
        parsed_policy = trust.parse_policy(policy)
        parsed_state = trust.parse_state(state)
        qualified = trust.VerificationEvidence.synthetic_qualified()
        fields = (
            ("policy_signature_verified", "pbtrust_policy_authentication"),
            ("policy_threshold_verified", "pbtrust_policy_threshold"),
            ("revocation_state_authenticated", "pbtrust_policy_revocation"),
            ("policy_not_revoked", "pbtrust_policy_revocation"),
            ("state_authenticated", "pbtrust_state_authentication"),
            ("state_monotonic", "pbtrust_state_monotonicity"),
            ("state_backend_writable", "pbtrust_state_backend_writable"),
            ("secure_boot_state_verified", "pbtrust_secure_boot_state"),
        )
        for field, expected in fields:
            with self.subTest(field=field):
                evidence = dataclasses.replace(qualified, **{field: False})
                with self.assertRaises(trust.BootTrustError) as caught:
                    trust.authorize(parsed_policy, parsed_state, observed, evidence)
                self.assertEqual(expected, caught.exception.code)

    def test_synthetic_qualified_model_is_not_a_crypto_claim(self) -> None:
        policy, state, observed = records(signed=True, authenticated=True)
        result = trust.authorize(
            trust.parse_policy(policy),
            trust.parse_state(state),
            observed,
            trust.VerificationEvidence.synthetic_qualified(),
        )
        self.assertEqual(1, result["policy_version"])
        self.assertEqual(1, result["state_generation"])


if __name__ == "__main__":
    unittest.main()
