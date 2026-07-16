import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_reference  # noqa: E402
from runtime import pdc_representation as rep  # noqa: E402


class PdcRepresentationTests(unittest.TestCase):
    def _field(self, shape=(5, 5, 5)) -> rep.DenseBinaryField:
        count = math.prod(shape)
        values = [0] * count
        for index in (0, 3, 17, count // 2, count - 1):
            values[index] = 1
        return rep.dense_binary_field(values, shape)

    def test_binary_representations_round_trip_and_share_semantic_hash(self) -> None:
        dense = self._field()
        sparse = rep.sparse_from_dense(dense)
        packed = rep.bitpacked_from_dense(dense)
        native = rep.native_snapshot_from_dense(
            dense,
            byte_offset=3,
            row_padding_bytes=2,
            slice_padding_bytes=5,
        )
        self.assertEqual(rep.dense_from_sparse(sparse), dense)
        self.assertEqual(rep.dense_from_bitpacked(packed), dense)
        self.assertEqual(rep.dense_from_bitpacked(rep.bitpacked_from_sparse(sparse)), dense)
        self.assertEqual(rep.dense_from_native(native), dense)

        expected = pdc_reference.canonical_array_hash(dense.payload, dense.shape, dtype="u8")
        for representation in (dense, sparse, packed, native):
            self.assertEqual(rep.dense_binary_semantic_hash(representation), expected)
        storage_hashes = {rep.representation_storage_hash(item) for item in (dense, sparse, packed, native)}
        self.assertEqual(len(storage_hashes), 4)

    def test_bit_order_and_padding_are_canonical(self) -> None:
        dense = rep.dense_binary_field((1, 0, 1) + (0,) * 22, (5, 5))
        packed = rep.bitpacked_from_dense(dense)
        self.assertEqual(packed.payload[0], 0b00000101)
        self.assertEqual(rep.dense_from_bitpacked(packed), dense)
        with self.assertRaises(rep.PdcRepresentationError):
            rep.BitPackedBinaryField((5, 5), packed.payload[:-1] + bytes((packed.payload[-1] | 0b10000000,)))
        with self.assertRaises(pdc_reference.PdcShapeError):
            rep.BitPackedBinaryField((5, 5), packed.payload + b"\x00")

    def test_sparse_form_rejects_noncanonical_indices(self) -> None:
        for indices in ((2, 2), (3, 2), (-1,), (125,), (True,)):
            with self.subTest(indices=indices):
                with self.assertRaises(pdc_reference.PdcContractError):
                    rep.SparseBinaryField((5, 5, 5), indices)

    def test_probability_embedding_round_trips_only_exact_binary_values(self) -> None:
        dense = self._field((5, 5))
        probability = rep.probability_from_dense(dense)
        self.assertEqual(rep.dense_from_probability(probability), dense)
        self.assertRegex(rep.probability_semantic_hash(probability), r"^[0-9A-F]{64}$")
        self.assertNotEqual(
            rep.probability_semantic_hash(probability),
            rep.dense_binary_semantic_hash(dense),
        )
        nonbinary = rep.ProbabilityField((5, 5), (0.5,) + (0.0,) * 24)
        with self.assertRaises(rep.PdcConversionError):
            rep.dense_from_probability(nonbinary)
        for invalid in (float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(invalid=invalid):
                with self.assertRaises(rep.PdcRepresentationError):
                    rep.ProbabilityField((5, 5), (invalid,) + (0.0,) * 24)

    def test_probability_native_buffer_round_trip_with_padding(self) -> None:
        probability = rep.ProbabilityField((5, 5), tuple(index / 24 for index in range(25)))
        native = rep.native_snapshot_from_probability(
            probability,
            byte_offset=8,
            row_padding_bytes=16,
            declared_base_alignment=16,
        )
        restored = rep.probability_from_native(native)
        self.assertEqual(restored, probability)
        self.assertEqual(rep.probability_semantic_hash(native), rep.probability_semantic_hash(probability))
        self.assertEqual(native.strides, (8, 56))
        self.assertEqual(native.source_mutability, "mutable_snapshotted")

    def test_probability_negative_zero_is_canonical_across_native_snapshot(self) -> None:
        probability = rep.ProbabilityField((5, 5), (-0.0,) + (0.0,) * 24)
        self.assertEqual(probability.values[0], 0.0)
        native = rep.native_snapshot_from_probability(probability)
        self.assertEqual(native.logical_payload[:8], b"\x00" * 8)
        self.assertEqual(rep.probability_from_native(native).values[0], 0.0)

    def test_borrowed_storage_requires_snapshot_and_detaches_mutation(self) -> None:
        backing = bytearray((0, 1, 0, 1) + (0,) * 21)
        with self.assertRaises(rep.PdcOwnershipError):
            rep.make_native_buffer_snapshot(
                backing,
                shape=(5, 5),
                dtype="u8",
                source_ownership="caller_borrowed",
                declared_base_alignment=1,
            )
        snapshot = rep.make_native_buffer_snapshot(
            backing,
            shape=(5, 5),
            dtype="u8",
            source_ownership="caller_borrowed",
            declared_base_alignment=1,
            snapshot_borrowed=True,
        )
        before = snapshot.logical_payload
        backing[1] = 0
        self.assertEqual(snapshot.logical_payload, before)
        self.assertEqual(snapshot.source_mutability, "mutable_snapshotted")

    def test_native_descriptor_rejects_overlap_alignment_span_and_noncontiguous_backing(self) -> None:
        backing = bytearray(512)
        cases = (
            {"dtype": "u8", "strides": (1, 4), "declared_base_alignment": 1},
            {"dtype": "f64", "strides": (8, 40), "byte_offset": 1, "declared_base_alignment": 8},
            {"dtype": "f64", "strides": (8, 40), "declared_base_alignment": 4},
            {"dtype": "u8", "strides": (1, 200), "declared_base_alignment": 1},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(pdc_reference.PdcContractError):
                    rep.make_native_buffer_snapshot(
                        backing,
                        shape=(5, 5),
                        source_ownership="runtime_owned",
                        **kwargs,
                    )
        with self.assertRaises(rep.PdcStrideError):
            rep.make_native_buffer_snapshot(
                memoryview(backing)[::2],
                shape=(5, 5),
                dtype="u8",
                source_ownership="runtime_owned",
                declared_base_alignment=1,
            )

    def test_checked_u64_arithmetic_and_span_fail_before_wrap(self) -> None:
        self.assertEqual(rep.checked_u64_add(7, 9), 16)
        self.assertEqual(rep.checked_u64_multiply(7, 9), 63)
        with self.assertRaises(pdc_reference.PdcOverflowError):
            rep.checked_u64_add(rep.MAX_U64, 1)
        with self.assertRaises(pdc_reference.PdcOverflowError):
            rep.checked_u64_multiply(2**63, 2)
        with self.assertRaises(pdc_reference.PdcOverflowError):
            rep.required_native_span((3, 3), "u8", rep.MAX_U64, (1, 3))

    def test_planar_pdc_result_survives_every_binary_conversion(self) -> None:
        shape = (9, 8)
        dense = rep.DenseBinaryField(shape, bytes(pdc_reference.rectangle_defect_field(3, 4, shape, origin=(3, 2))))
        expected = pdc_reference.planar_first_step_summary(dense.payload, shape)
        round_trips = (
            rep.dense_from_sparse(rep.sparse_from_dense(dense)),
            rep.dense_from_bitpacked(rep.bitpacked_from_dense(dense)),
            rep.dense_from_probability(rep.probability_from_dense(dense)),
            rep.dense_from_native(rep.native_snapshot_from_dense(dense, row_padding_bytes=3)),
        )
        for restored in round_trips:
            self.assertEqual(restored, dense)
            self.assertEqual(pdc_reference.planar_first_step_summary(restored.payload, shape), expected)

    def test_3d_pdc_result_survives_every_binary_conversion(self) -> None:
        shape = (5, 5, 5)
        dense = self._field(shape)
        expected = pdc_reference.binary_next_state(dense.payload, shape)
        round_trips = (
            rep.dense_from_sparse(rep.sparse_from_dense(dense)),
            rep.dense_from_bitpacked(rep.bitpacked_from_dense(dense)),
            rep.dense_from_probability(rep.probability_from_dense(dense)),
            rep.dense_from_native(rep.native_snapshot_from_dense(dense, row_padding_bytes=2, slice_padding_bytes=3)),
        )
        for restored in round_trips:
            self.assertEqual(restored, dense)
            self.assertEqual(pdc_reference.binary_next_state(restored.payload, shape), expected)


if __name__ == "__main__":
    unittest.main()
