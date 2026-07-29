import copy
import hashlib
import unittest

from runtime import native_boot_handoff as pbp1
from runtime import native_kernel_revalidation as revalidation


class NativeKernelRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = revalidation.canonical_bundle()

    def assert_rejects(self, code: str, handoff: bytes, files, bases=None) -> None:
        with self.assertRaises(revalidation.KernelRevalidationError) as caught:
            revalidation.revalidate_development(
                handoff,
                files,
                self.bundle.physical_bases if bases is None else bases,
            )
        self.assertEqual(code, caught.exception.code)

    def test_canonical_exact_bytes_end_at_unsigned_denial(self) -> None:
        summary = revalidation.revalidate_development(
            self.bundle.handoff,
            self.bundle.files,
            self.bundle.physical_bases,
        )
        self.assertEqual("PKREVAL1", summary["contract_id"])
        self.assertEqual(9, summary["retained_file_count"])
        self.assertEqual(9, summary["parser_count"])
        self.assertEqual("pbtrust_policy_unsigned", summary["denial"])
        self.assertEqual(0, summary["authority_grants"])
        self.assertEqual(0, summary["actions_authorized"])
        self.assertEqual(0, summary["state_writes"])

    def test_each_post_loader_file_mutation_is_detected_before_reparse(self) -> None:
        for index, source in enumerate(self.bundle.files):
            with self.subTest(index=index):
                files = list(self.bundle.files)
                mutated = bytearray(source)
                mutated[len(mutated) // 2] ^= 0x80
                files[index] = bytes(mutated)
                self.assert_rejects(
                    "pkreval_file_digest", self.bundle.handoff, tuple(files)
                )

    def test_order_size_and_physical_locator_substitution_fail_closed(self) -> None:
        reordered = list(self.bundle.files)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        self.assert_rejects(
            "pkreval_file_size", self.bundle.handoff, tuple(reordered)
        )
        shortened = list(self.bundle.files)
        shortened[0] = shortened[0][:-1]
        self.assert_rejects(
            "pkreval_file_size", self.bundle.handoff, tuple(shortened)
        )
        bases = list(self.bundle.physical_bases)
        bases[0] += pbp1.PAGE_BYTES
        self.assert_rejects(
            "pkreval_file_locator",
            self.bundle.handoff,
            self.bundle.files,
            tuple(bases),
        )

    def test_profile_flags_and_cross_range_overlap_fail_closed(self) -> None:
        writable = revalidation.rewrite_profile_descriptor(
            self.bundle.handoff,
            1,
            flags=pbp1.ARTIFACT_HASH_VERIFIED | pbp1.ARTIFACT_WRITABLE,
        )
        self.assert_rejects(
            "pkreval_artifact_flags", writable, self.bundle.files
        )
        overlap = revalidation.rewrite_profile_descriptor(
            self.bundle.handoff,
            2,
            physical_base=self.bundle.physical_bases[0],
        )
        self.assert_rejects(
            "pkreval_artifact_overlap", overlap, self.bundle.files
        )

    def test_repaired_outer_digest_cannot_replace_manifest_or_inner_authority(self) -> None:
        for index, source in enumerate(self.bundle.files):
            with self.subTest(index=index):
                files = list(self.bundle.files)
                mutated = bytearray(source)
                mutated[-1] ^= 1
                files[index] = bytes(mutated)
                handoff = revalidation.rewrite_file_digest(
                    self.bundle.handoff, index, files[index]
                )
                with self.assertRaises(revalidation.KernelRevalidationError) as caught:
                    revalidation.revalidate_development(
                        handoff, tuple(files), self.bundle.physical_bases
                    )
                self.assertNotEqual("pkreval_file_digest", caught.exception.code)

    def test_descriptor_digest_substitution_without_bytes_is_rejected(self) -> None:
        handoff = revalidation.rewrite_profile_descriptor(
            self.bundle.handoff,
            1,
            sha256=hashlib.sha256(b"substituted loader summary").digest(),
        )
        self.assert_rejects("pkreval_file_digest", handoff, self.bundle.files)

    def test_deterministic_mutation_campaign_covers_every_retained_role(self) -> None:
        summary = revalidation.mutation_campaign(self.bundle, 512)
        self.assertEqual(512, summary["reject_count"])
        self.assertEqual(512, summary["expected_file_digest_count"])
        self.assertEqual(9, summary["role_coverage"])

    def test_contract_and_readiness_remain_exactly_bound(self) -> None:
        contract = revalidation.read_json(
            revalidation.ROOT / revalidation.CONTRACT_RELATIVE
        )
        readiness = revalidation.read_json(
            revalidation.ROOT / revalidation.READINESS_RELATIVE
        )
        self.assertEqual([], revalidation.contract_errors(contract))
        self.assertEqual([], revalidation.readiness_errors(readiness))
        stale = copy.deepcopy(readiness)
        stale["inputs"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertIn(
            "PKREVAL1 readiness input bindings are stale",
            revalidation.readiness_errors(stale),
        )


if __name__ == "__main__":
    unittest.main()
