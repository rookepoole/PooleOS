import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_artifact  # noqa: E402
from runtime import native_firmware  # noqa: E402
from runtime import native_initial_system  # noqa: E402
from runtime import native_microcode  # noqa: E402
from runtime import native_policy  # noqa: E402
from runtime import native_recovery  # noqa: E402
from runtime import native_symbols  # noqa: E402


class NativeBootArtifactTests(unittest.TestCase):
    def test_canonical_artifacts_round_trip_every_profile_role(self) -> None:
        artifacts = native_boot_artifact.canonical_artifacts()
        self.assertEqual(set(native_boot_artifact.ROLES), set(artifacts))
        for role, data in artifacts.items():
            with self.subTest(role=role):
                decoded = native_boot_artifact.parse_bound(data, role, 1)
                self.assertEqual(role, decoded.role)
                self.assertEqual(1, decoded.version)
                if role == native_boot_artifact.ROLE_INITIAL_SYSTEM:
                    _, bundle = native_boot_artifact.parse_initial_system(data)
                    self.assertEqual(native_initial_system.canonical_bundle(), bundle.raw)
                elif role == native_boot_artifact.ROLE_RECOVERY:
                    _, bundle = native_boot_artifact.parse_recovery(data)
                    self.assertEqual(native_recovery.canonical_bundle(), bundle.raw)
                elif role == native_boot_artifact.ROLE_SYMBOLS:
                    _, bundle = native_boot_artifact.parse_symbols(data)
                    self.assertEqual(native_symbols.canonical_bundle(), bundle.raw)
                elif role == native_boot_artifact.ROLE_MICROCODE:
                    _, bundle = native_boot_artifact.parse_microcode(data)
                    self.assertEqual(native_microcode.canonical_bundle(), bundle.raw)
                elif role == native_boot_artifact.ROLE_FIRMWARE_MANIFEST:
                    _, bundle = native_boot_artifact.parse_firmware(data)
                    self.assertEqual(native_firmware.canonical_bundle(), bundle.raw)
                else:
                    _, bundle = native_boot_artifact.parse_policy(data)
                    self.assertEqual(native_policy.canonical_bundle(), bundle.raw)

    def test_initial_system_outer_and_inner_versions_are_cross_bound(self) -> None:
        data = native_boot_artifact.encode(
            native_boot_artifact.ROLE_INITIAL_SYSTEM,
            2,
            native_initial_system.canonical_bundle(),
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_inner_version_binding"
        ):
            native_boot_artifact.parse_initial_system(data)

    def test_recovery_outer_and_inner_versions_are_cross_bound(self) -> None:
        data = native_boot_artifact.encode(
            native_boot_artifact.ROLE_RECOVERY,
            2,
            native_recovery.canonical_bundle(),
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_inner_version_binding"
        ):
            native_boot_artifact.parse_recovery(data)

    def test_symbols_outer_and_inner_versions_are_cross_bound(self) -> None:
        data = native_boot_artifact.encode(
            native_boot_artifact.ROLE_SYMBOLS,
            2,
            native_symbols.canonical_bundle(),
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_inner_version_binding"
        ):
            native_boot_artifact.parse_symbols(data)

    def test_microcode_outer_and_inner_versions_are_cross_bound(self) -> None:
        data = native_boot_artifact.encode(
            native_boot_artifact.ROLE_MICROCODE,
            2,
            native_microcode.canonical_bundle(),
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_inner_version_binding"
        ):
            native_boot_artifact.parse_microcode(data)

    def test_firmware_outer_and_inner_versions_are_cross_bound(self) -> None:
        data = native_boot_artifact.encode(
            native_boot_artifact.ROLE_FIRMWARE_MANIFEST,
            2,
            native_firmware.canonical_bundle(),
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_inner_version_binding"
        ):
            native_boot_artifact.parse_firmware(data)

    def test_policy_outer_and_inner_versions_are_cross_bound(self) -> None:
        data = native_boot_artifact.encode(
            native_boot_artifact.ROLE_POLICY_BUNDLE,
            2,
            native_policy.canonical_bundle(),
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_inner_version_binding"
        ):
            native_boot_artifact.parse_policy(data)

    def test_role_version_digest_and_reserved_substitution_fail_closed(self) -> None:
        data = bytearray(
            native_boot_artifact.canonical_artifacts()[
                native_boot_artifact.ROLE_INITIAL_SYSTEM
            ]
        )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_role_binding"
        ):
            native_boot_artifact.parse_bound(
                bytes(data), native_boot_artifact.ROLE_RECOVERY, 1
            )
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_version_binding"
        ):
            native_boot_artifact.parse_bound(
                bytes(data), native_boot_artifact.ROLE_INITIAL_SYSTEM, 2
            )
        data[native_boot_artifact.HEADER_BYTES] ^= 1
        with self.assertRaisesRegex(native_boot_artifact.BootArtifactError, "artifact_digest"):
            native_boot_artifact.parse(bytes(data))
        data = bytearray(
            native_boot_artifact.canonical_artifacts()[
                native_boot_artifact.ROLE_INITIAL_SYSTEM
            ]
        )
        data[95] = 1
        with self.assertRaisesRegex(native_boot_artifact.BootArtifactError, "artifact_reserved"):
            native_boot_artifact.parse(bytes(data))

    def test_truncation_trailing_bytes_flags_and_image_size_fail_closed(self) -> None:
        original = native_boot_artifact.canonical_artifacts()[
            native_boot_artifact.ROLE_POLICY_BUNDLE
        ]
        with self.assertRaisesRegex(native_boot_artifact.BootArtifactError, "artifact_truncated"):
            native_boot_artifact.parse(original[:-1])
        with self.assertRaisesRegex(
            native_boot_artifact.BootArtifactError, "artifact_trailing_bytes"
        ):
            native_boot_artifact.parse(original + b"\0")
        flags = bytearray(original)
        struct.pack_into("<I", flags, 20, 1)
        with self.assertRaisesRegex(native_boot_artifact.BootArtifactError, "artifact_flags"):
            native_boot_artifact.parse(bytes(flags))
        image = bytearray(original)
        struct.pack_into("<Q", image, 40, 1)
        with self.assertRaisesRegex(native_boot_artifact.BootArtifactError, "artifact_image_size"):
            native_boot_artifact.parse(bytes(image))


if __name__ == "__main__":
    unittest.main()
