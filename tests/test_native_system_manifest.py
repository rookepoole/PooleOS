from __future__ import annotations

import copy
import unittest

from runtime import native_system_manifest as psm


class NativeSystemManifestTests(unittest.TestCase):
    def canonical(self) -> bytes:
        return psm.canonical_kernel_manifest(b"abc", 4096)

    def rejected(self, data: bytes, code: str) -> None:
        with self.assertRaisesRegex(psm.ManifestError, f"^{code}$"):
            psm.parse(data)

    def replace(self, old: bytes, new: bytes) -> bytes:
        self.assertIn(old, self.canonical())
        return self.canonical().replace(old, new, 1)

    def test_canonical_round_trip_and_file_binding(self) -> None:
        data = self.canonical()
        manifest = psm.parse(data)
        self.assertEqual(data, psm.encode(manifest.artifacts, manifest_id=manifest.manifest_id, slot=1, manifest_version=1, minimum_secure_version=1))
        self.assertEqual(manifest.kernel.path, r"\EFI\POOLEOS\KERNEL.ELF")
        self.assertEqual(psm.verify_file(manifest.kernel, b"abc"), manifest.kernel.sha256)

    def test_sha256_standard_vectors(self) -> None:
        self.assertEqual(psm.sha256_bytes(b""), "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855")
        self.assertEqual(psm.sha256_bytes(b"abc"), "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD")

    def test_rejects_lexical_and_version_drift(self) -> None:
        self.rejected(b"", "manifest_empty")
        self.rejected(self.canonical()[:-1], "manifest_missing_final_lf")
        self.rejected(self.replace(b"MANIFEST/1.0", b"MANIFEST/2.0"), "manifest_version")
        self.rejected(self.replace(b"manifest_id=", b"unknown="), "manifest_unknown_key")
        self.rejected(self.replace(b"slot=1", b"slot=01"), "manifest_number_canonical")

    def test_rejects_slot_version_path_and_format_drift(self) -> None:
        self.rejected(self.replace(b"slot=1", b"slot=5"), "manifest_range")
        self.rejected(self.replace(b"minimum_secure_version=1", b"minimum_secure_version=2"), "manifest_version_floor")
        self.rejected(self.replace(b"path=\\EFI", b"path=\\efi"), "manifest_path")
        self.rejected(self.replace(b"format=PKELF1", b"format=pkelf1"), "manifest_format")

    def test_rejects_kernel_binding_and_digest_drift(self) -> None:
        self.rejected(self.replace(b"format=PKELF1", b"format=PXABI1"), "manifest_binding")
        self.rejected(self.replace(b"entry_contract=PKENTRY1", b"entry_contract=none"), "manifest_binding")
        manifest = psm.parse(self.canonical())
        with self.assertRaisesRegex(psm.ManifestError, "^manifest_size$"):
            psm.verify_file(manifest.kernel, b"ab")
        with self.assertRaisesRegex(psm.ManifestError, "^manifest_digest$"):
            psm.verify_file(manifest.kernel, b"abd")

    def test_readiness_validator_rejects_claim_overreach(self) -> None:
        readiness = {"claims": {"manifest_trusted": False}, "production_ready": False, "bindings": {}}
        mutated = copy.deepcopy(readiness)
        mutated["claims"]["manifest_trusted"] = True
        errors = psm.readiness_errors(mutated, __import__("pathlib").Path(__file__).resolve().parents[1])
        self.assertTrue(any("manifest_trusted" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
