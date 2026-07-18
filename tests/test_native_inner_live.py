import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_boot_artifact as pbart1,
    native_initial_system as pinit1,
    native_inner_live,
)


def canonical_files() -> list[bytes]:
    artifacts = pbart1.canonical_artifacts()
    return [artifacts[role] for role in pbart1.ROLES]


class NativeInnerLiveTests(unittest.TestCase):
    def test_canonical_set_parses_cross_binds_and_denies(self) -> None:
        files = canonical_files()
        summary = native_inner_live.validate_development_set(files)
        self.assertEqual(native_inner_live.PROOF_ID, summary["proof_id"])
        self.assertEqual(6, summary["artifact_count"])
        self.assertEqual(6, summary["parser_count"])
        self.assertEqual(6, summary["cross_binding_count"])
        self.assertEqual(6, summary["development_denial_count"])
        self.assertEqual(
            list(native_inner_live.EXPECTED_DENIALS),
            summary["development_denials"],
        )
        self.assertEqual(0, summary["authority_grants"])
        self.assertEqual(0, summary["actions_authorized"])
        self.assertEqual(0, summary["state_writes"])
        self.assertEqual(0, summary["hardware_observations"])

    def test_reordered_outer_roles_fail_closed(self) -> None:
        files = canonical_files()
        files[0], files[1] = files[1], files[0]
        with self.assertRaises(pbart1.BootArtifactError) as caught:
            native_inner_live.validate_development_set(files)
        self.assertEqual("artifact_role_binding", caught.exception.code)

    def test_exact_outer_mutation_fails_before_inner_parse(self) -> None:
        files = canonical_files()
        changed = bytearray(files[2])
        changed[-1] ^= 1
        files[2] = bytes(changed)
        with self.assertRaises(pbart1.BootArtifactError) as caught:
            native_inner_live.validate_development_set(files)
        self.assertEqual("artifact_digest", caught.exception.code)

    def test_recomputed_outer_cannot_hide_invalid_inner_bytes(self) -> None:
        files = canonical_files()
        payload = bytearray(pinit1.canonical_bundle())
        payload[-1] ^= 1
        files[0] = pbart1.encode(pbart1.ROLE_INITIAL_SYSTEM, 1, bytes(payload))
        with self.assertRaises(pinit1.InitialSystemError) as caught:
            native_inner_live.validate_development_set(files)
        self.assertEqual("pinit_body_digest", caught.exception.code)

    def test_valid_policy_with_substituted_digest_fails_cross_binding(self) -> None:
        files = canonical_files()
        policy = bytearray(pbart1.parse(files[5]).payload)
        policy[160] ^= 1
        files[5] = pbart1.encode(pbart1.ROLE_POLICY_BUNDLE, 1, bytes(policy))
        with self.assertRaises(native_inner_live.InnerLiveError):
            native_inner_live.validate_development_set(files)


if __name__ == "__main__":
    unittest.main()
