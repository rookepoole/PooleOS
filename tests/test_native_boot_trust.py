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


def backend_state(
    copy_index: int,
    generation: int = 1,
    *,
    epoch: int = 1,
    auth_profile: int = 1,
    previous: str | None = None,
) -> bytes:
    return trust.encode_state(
        policy_sha256="55" * 32,
        manifest_sha256=MANIFEST,
        kernel_sha256=KERNEL,
        retained_set_sha256=RETAINED,
        state_generation=generation,
        store_epoch=epoch,
        authenticated_backend=True,
        copy_index=copy_index,
        auth_profile=auth_profile,
        previous_state_sha256=previous,
    )


def backend_anchor(data: bytes) -> trust.MonotonicAnchor:
    state = trust.parse_state(data)
    return trust.MonotonicAnchor(
        authenticated=True,
        monotonic=True,
        state_generation=state.state_generation,
        store_epoch=state.store_epoch,
        auth_profile=state.auth_profile,
        logical_state_sha256=trust.logical_state_sha256(state),
        previous_state_sha256=state.previous_state_sha256,
    )


def backend_requirements(**changes: int) -> trust.BackendRequirements:
    values = {
        "minimum_state_generation": 1,
        "minimum_store_epoch": 1,
        "target_store_epoch": 1,
        "target_auth_profile": 1,
        **changes,
    }
    return trust.BackendRequirements(**values)


BACKEND_ACCESS = trust.BackendAccess(writable=True, repair_capacity=True)


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

    def test_backend_logical_digest_ignores_only_copy_identity(self) -> None:
        copy0 = backend_state(0)
        copy1 = backend_state(1)
        self.assertNotEqual(trust.sha256_bytes(copy0), trust.sha256_bytes(copy1))
        self.assertEqual(
            trust.logical_state_sha256(trust.parse_state(copy0)),
            trust.logical_state_sha256(trust.parse_state(copy1)),
        )

    def test_backend_healthy_pair_selects_copy_zero_without_effects(self) -> None:
        copy0 = backend_state(0)
        copy1 = backend_state(1)
        selected = trust.select_backend_state(
            (
                trust.BackendCopy(copy0, True),
                trust.BackendCopy(copy1, True),
            ),
            backend_anchor(copy0),
            backend_requirements(),
            BACKEND_ACCESS,
        )
        self.assertEqual(0, selected.selected_copy)
        self.assertEqual(0b11, selected.anchored_copy_mask)
        self.assertEqual(0, selected.repair_copy_mask)
        self.assertEqual(0, selected.authority_grants)
        self.assertEqual(0, selected.state_writes)

    def test_backend_future_copy_waits_for_anchor_commit(self) -> None:
        old0 = backend_state(0)
        old_digest = trust.logical_state_sha256(trust.parse_state(old0))
        new1 = backend_state(1, 2, previous=old_digest)
        selected_old = trust.select_backend_state(
            (
                trust.BackendCopy(old0, True),
                trust.BackendCopy(new1, True),
            ),
            backend_anchor(old0),
            backend_requirements(),
            BACKEND_ACCESS,
        )
        self.assertEqual(0, selected_old.selected_copy)
        self.assertEqual(0b10, selected_old.future_copy_mask)
        self.assertEqual(0b10, selected_old.repair_copy_mask)

        selected_new = trust.select_backend_state(
            (
                trust.BackendCopy(old0, True),
                trust.BackendCopy(new1, True),
            ),
            backend_anchor(new1),
            backend_requirements(),
            BACKEND_ACCESS,
        )
        self.assertEqual(1, selected_new.selected_copy)
        self.assertEqual(0b01, selected_new.stale_copy_mask)
        self.assertEqual(0b01, selected_new.repair_copy_mask)

    def test_backend_anchor_and_copy_authentication_fail_closed(self) -> None:
        copy0 = backend_state(0)
        copy1 = backend_state(1)
        anchor = dataclasses.replace(backend_anchor(copy0), authenticated=False)
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.select_backend_state(
                (
                    trust.BackendCopy(copy0, True),
                    trust.BackendCopy(copy1, True),
                ),
                anchor,
                backend_requirements(),
                BACKEND_ACCESS,
            )
        self.assertEqual(
            "pbtrust_backend_anchor_authentication", caught.exception.code
        )

        with self.assertRaises(trust.BootTrustError) as caught:
            trust.select_backend_state(
                (
                    trust.BackendCopy(copy0, False),
                    trust.BackendCopy(copy1, False),
                ),
                backend_anchor(copy0),
                backend_requirements(),
                BACKEND_ACCESS,
            )
        self.assertEqual(
            "pbtrust_backend_no_authenticated_copy", caught.exception.code
        )

    def test_backend_repair_requires_writable_capacity(self) -> None:
        copy0 = backend_state(0)
        copies = (
            trust.BackendCopy(copy0, True),
            trust.BackendCopy(None, False),
        )
        for access, expected in (
            (
                trust.BackendAccess(writable=False, repair_capacity=True),
                "pbtrust_backend_writable",
            ),
            (
                trust.BackendAccess(writable=True, repair_capacity=False),
                "pbtrust_backend_repair_capacity",
            ),
        ):
            with self.subTest(expected=expected):
                with self.assertRaises(trust.BootTrustError) as caught:
                    trust.select_backend_state(
                        copies,
                        backend_anchor(copy0),
                        backend_requirements(),
                        access,
                    )
                self.assertEqual(expected, caught.exception.code)

    def test_backend_transition_models_migration_without_writes(self) -> None:
        copy0 = backend_state(0)
        copy1 = backend_state(1)
        selected = trust.select_backend_state(
            (
                trust.BackendCopy(copy0, True),
                trust.BackendCopy(copy1, True),
            ),
            backend_anchor(copy0),
            backend_requirements(target_store_epoch=2, target_auth_profile=2),
            BACKEND_ACCESS,
        )
        self.assertTrue(selected.migration_required)
        plan = trust.plan_backend_transition(selected)
        self.assertEqual(2, plan.next_generation)
        self.assertEqual(9, plan.ordered_step_count)
        self.assertEqual(selected.logical_state_sha256, plan.previous_state_sha256)
        self.assertEqual(0, plan.state_writes_performed)
        self.assertEqual(0, plan.anchor_writes_performed)
        self.assertEqual(0, plan.authority_grants)

        with self.assertRaises(trust.BootTrustError) as caught:
            trust.plan_backend_transition(
                dataclasses.replace(selected, selected_copy=2)
            )
        self.assertEqual("pbtrust_backend_requirements", caught.exception.code)

        with self.assertRaises(trust.BootTrustError) as caught:
            trust.plan_backend_transition(
                dataclasses.replace(selected, target_store_epoch=0)
            )
        self.assertEqual(
            "pbtrust_backend_migration_rollback", caught.exception.code
        )

    def test_backend_transition_rejects_generation_overflow(self) -> None:
        previous = "66" * 32
        copy0 = backend_state(0, (1 << 64) - 1, previous=previous)
        copy1 = backend_state(1, (1 << 64) - 1, previous=previous)
        selected = trust.select_backend_state(
            (
                trust.BackendCopy(copy0, True),
                trust.BackendCopy(copy1, True),
            ),
            backend_anchor(copy0),
            backend_requirements(),
            BACKEND_ACCESS,
        )
        with self.assertRaises(trust.BootTrustError) as caught:
            trust.plan_backend_transition(selected)
        self.assertEqual(
            "pbtrust_backend_generation_overflow", caught.exception.code
        )


if __name__ == "__main__":
    unittest.main()
