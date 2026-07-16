import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import channel_telemetry  # noqa: E402
from runtime import pdc_reference  # noqa: E402


class PdcReferenceTests(unittest.TestCase):
    def _field_with_target_support(self, state: int, support: int) -> tuple[tuple[int, ...], pdc_reference.Shape3, int]:
        shape = (5, 5, 5)
        target = (2, 2, 2)
        field = [0] * 125
        target_index = pdc_reference.flat_index_3d(target, shape)
        field[target_index] = state
        for coord in pdc_reference.moore_neighbor_coords(target, shape)[:support]:
            field[pdc_reference.flat_index_3d(coord, shape)] = 1
        return tuple(field), shape, target_index

    def test_flattening_is_x_fastest_and_round_trips(self) -> None:
        shape3 = (4, 5, 6)
        self.assertEqual(pdc_reference.flat_index_3d((0, 0, 0), shape3), 0)
        self.assertEqual(pdc_reference.flat_index_3d((1, 0, 0), shape3), 1)
        self.assertEqual(pdc_reference.flat_index_3d((0, 1, 0), shape3), 4)
        self.assertEqual(pdc_reference.flat_index_3d((0, 0, 1), shape3), 20)
        for index in range(4 * 5 * 6):
            self.assertEqual(pdc_reference.flat_index_3d(pdc_reference.unflatten_3d(index, shape3), shape3), index)

        shape2 = (7, 8)
        for index in range(7 * 8):
            self.assertEqual(pdc_reference.flat_index_2d(pdc_reference.unflatten_2d(index, shape2), shape2), index)

    def test_scalar_and_matrix_support_agree_for_deterministic_random_fields(self) -> None:
        rng = random.Random(0x504443)
        for shape in ((3, 3, 3), (4, 3, 3), (5, 4, 3)):
            count = shape[0] * shape[1] * shape[2]
            for _ in range(4):
                field = tuple(rng.randrange(2) for _ in range(count))
                self.assertEqual(
                    pdc_reference.scalar_moore_support(field, shape),
                    pdc_reference.matrix_moore_support(field, shape),
                )

    def test_matrix_invariants_match_neighborhood_sizes(self) -> None:
        a26 = pdc_reference.moore_matrix_3d((3, 3, 3))
        self.assertTrue(all(sum(row) == 26 for row in a26))
        self.assertTrue(all(row[index] == 0 for index, row in enumerate(a26)))

        a8, a9 = pdc_reference.planar_matrices_2d((5, 4))
        self.assertTrue(all(sum(row) == 8 for row in a8))
        self.assertTrue(all(sum(row) == 9 for row in a9))
        self.assertTrue(all(row[index] == 0 for index, row in enumerate(a8)))
        self.assertTrue(all(row[index] == 1 for index, row in enumerate(a9)))

    def test_threshold_edges_and_defect_components_are_exact(self) -> None:
        expected = {
            (0, 4): (False, "B4", 7, 1, 0, -1, 0),
            (0, 5): (True, "B5", 7, 0, 0, 0, 1),
            (0, 7): (True, "B7", 7, 0, 0, 0, 1),
            (0, 8): (False, "B8", 7, 0, 1, 1, 0),
            (0, 26): (False, "B26", 7, 0, 19, 19, 0),
            (1, 4): (False, "S4", 9, 1, 0, -1, 0),
            (1, 5): (True, "S5", 9, 0, 0, 0, 1),
            (1, 9): (True, "S9", 9, 0, 0, 0, 1),
            (1, 10): (False, "O10+", 9, 0, 1, 1, 0),
            (1, 26): (False, "O10+", 9, 0, 17, 17, 0),
        }
        for key, values in expected.items():
            state, support = key
            field, shape, target_index = self._field_with_target_support(state, support)
            measured = pdc_reference.measure_binary_field(field, shape)[target_index]
            self.assertEqual(
                (
                    measured.accepted,
                    measured.channel,
                    measured.capacity,
                    measured.deficit,
                    measured.excess,
                    measured.strain,
                    measured.next_state,
                ),
                values,
                key,
            )
            self.assertEqual(measured.strain, channel_telemetry.support_strain(support, bool(state)))

    def test_periodic_wrap_support_is_counted(self) -> None:
        shape = (5, 5, 5)
        field = [0] * 125
        field[pdc_reference.flat_index_3d((4, 0, 0), shape)] = 1
        support = pdc_reference.scalar_moore_support(field, shape)
        self.assertEqual(support[pdc_reference.flat_index_3d((0, 0, 0), shape)], 1)
        self.assertEqual(support[pdc_reference.flat_index_3d((4, 0, 0), shape)], 0)

    def test_planar_scalar_and_matrix_counts_agree(self) -> None:
        rng = random.Random(0x5139)
        for shape in ((3, 3), (5, 4), (7, 6)):
            count = shape[0] * shape[1]
            for _ in range(5):
                defects = tuple(rng.randrange(2) for _ in range(count))
                self.assertEqual(
                    pdc_reference.scalar_planar_counts(defects, shape),
                    pdc_reference.matrix_planar_counts(defects, shape),
                )

    def test_rectangle_planar_summary_matches_formula_family(self) -> None:
        for width in range(2, 7):
            for height in range(2, 7):
                shape = (width + 4, height + 4)
                defects = pdc_reference.rectangle_defect_field(width, height, shape, origin=(2, 2))
                summary = pdc_reference.planar_first_step_summary(defects, shape)
                formula = pdc_reference.rectangle_formula(width, height)
                self.assertEqual(summary.total_births, formula["births"])
                self.assertEqual(summary.deaths, formula["deaths"])
                self.assertEqual(summary.birth_spectrum, formula["birth_spectrum"])

    def test_line_planar_summary_matches_formula_family(self) -> None:
        for length in range(1, 9):
            shape = (length + 4, 5)
            defects = pdc_reference.line_defect_field(length, shape, origin=(2, 2))
            summary = pdc_reference.planar_first_step_summary(defects, shape)
            formula = pdc_reference.line_hole_formula(length)
            self.assertEqual(summary.total_births, formula["births"])
            self.assertEqual(summary.deaths, formula["deaths"])
            self.assertEqual(summary.birth_spectrum, formula["birth_spectrum"])

    def test_model_variants_and_geometric_formulas_remain_distinct(self) -> None:
        raw = pdc_reference.rectangle_formula(3, 4)
        pmphi = pdc_reference.rectangle_formula(3, 4, model_tag="PMphi.default.remove_B7")
        self.assertEqual(raw["births"] - pmphi["births"], 16)
        self.assertEqual(raw["birth_spectrum"]["B7"], 16)
        self.assertEqual(pmphi["birth_spectrum"]["B7"], 0)

        cuboid = pdc_reference.cuboid_formula(4, 5, 6)
        self.assertEqual(cuboid, {
            "active_0": 120,
            "births": 72,
            "deaths": 112,
            "active_1": 80,
            "birth_spectrum": {"B5": 0, "B6": 72, "B7": 0},
        })
        shell = pdc_reference.closed_shell_formula(4, 5, 6)
        self.assertEqual(shell, {
            "active_0": 96,
            "births": 72,
            "deaths": 48,
            "active_1": 120,
            "birth_spectrum": {"B5": 0, "B6": 72, "B7": 0},
        })

    def test_sparse_cuboid_and_shell_oracle_matches_formulas(self) -> None:
        shape = (20, 20, 20)
        for dimensions in ((4, 4, 4), (4, 5, 6), (7, 6, 5)):
            a, b, c = dimensions
            for coords, formula in (
                (pdc_reference.solid_cuboid_coords(a, b, c, shape), pdc_reference.cuboid_formula(a, b, c)),
                (
                    pdc_reference.closed_surface_shell_coords(a, b, c, shape),
                    pdc_reference.closed_shell_formula(a, b, c),
                ),
            ):
                observed = pdc_reference.sparse_first_response(coords, shape)
                self.assertEqual(observed.initial_active, formula["active_0"])
                self.assertEqual(observed.births, formula["births"])
                self.assertEqual(observed.deaths, formula["deaths"])
                self.assertEqual(observed.final_active, formula["active_1"])
                self.assertEqual(observed.birth_spectrum, formula["birth_spectrum"])
                self.assertEqual(observed.death_spectrum["D_low"], 0)

    def test_sparse_oracle_agrees_with_dense_scalar_path(self) -> None:
        shape = (7, 7, 7)
        coords = ((2, 2, 2), (2, 2, 3), (2, 3, 2), (3, 2, 2), (3, 3, 3))
        field = [0] * (7 * 7 * 7)
        for coord in coords:
            field[pdc_reference.flat_index_3d(coord, shape)] = 1
        measurements = pdc_reference.measure_binary_field(field, shape)
        sparse = pdc_reference.sparse_first_response(coords, shape)
        next_state = [item.next_state for item in measurements]
        self.assertEqual(sparse.births, sum(1 for before, after in zip(field, next_state) if not before and after))
        self.assertEqual(sparse.deaths, sum(1 for before, after in zip(field, next_state) if before and not after))
        self.assertEqual(sparse.final_active, sum(next_state))

    def test_sparse_geometry_validation_fails_closed(self) -> None:
        with self.assertRaises(pdc_reference.PdcShapeError):
            pdc_reference.solid_cuboid_coords(4, 4, 4, (5, 8, 8))
        with self.assertRaises(pdc_reference.PdcContractError):
            pdc_reference.sparse_first_response(((1, 1, 1), (1, 1, 1)), (5, 5, 5))
        with self.assertRaises(pdc_reference.PdcShapeError):
            pdc_reference.sparse_first_response(((5, 1, 1),), (5, 5, 5))

    def test_invalid_shapes_fields_coordinates_and_limits_fail_closed(self) -> None:
        with self.assertRaises(pdc_reference.PdcShapeError):
            pdc_reference.scalar_moore_support((0,) * 18, (2, 3, 3))
        with self.assertRaises(pdc_reference.PdcShapeError):
            pdc_reference.scalar_moore_support((0,) * 26, (3, 3, 3))
        with self.assertRaises(pdc_reference.PdcContractError):
            pdc_reference.scalar_moore_support((2,) * 27, (3, 3, 3))
        with self.assertRaises(pdc_reference.PdcOverflowError):
            pdc_reference.checked_product((2**32, 2**32), limit=2**63 - 1)
        with self.assertRaises(pdc_reference.PdcMatrixLimitError):
            pdc_reference.moore_matrix_3d((9, 9, 9))
        with self.assertRaises(pdc_reference.PdcShapeError):
            pdc_reference.flat_index_3d((3, 0, 0), (3, 3, 3))
        with self.assertRaises(pdc_reference.PdcShapeError):
            pdc_reference.rectangle_formula(1, 3)
        with self.assertRaises(pdc_reference.PdcContractError):
            pdc_reference.rectangle_formula(3, 4, model_tag="untagged")

    def test_canonical_hash_binds_shape_dtype_and_axis_contract(self) -> None:
        values = (0,) * 27
        digest = pdc_reference.canonical_array_hash(values, (3, 3, 3), dtype="u8")
        self.assertRegex(digest, r"^[0-9A-F]{64}$")
        self.assertNotEqual(digest, pdc_reference.canonical_array_hash(values, (9, 3), dtype="u8"))
        self.assertNotEqual(digest, pdc_reference.canonical_array_hash(values, (3, 3, 3), dtype="i8"))
        with self.assertRaises(pdc_reference.PdcContractError):
            pdc_reference.canonical_array_hash((256,) * 27, (3, 3, 3), dtype="u8")


if __name__ == "__main__":
    unittest.main()
