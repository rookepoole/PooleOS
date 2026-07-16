import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK_ROOT / "PooleGlyph"))

import pooleglyph_pgvm as pg  # noqa: E402
from runtime import channel_telemetry as ct  # noqa: E402


def defective_sheet_lattice(radius: int, defects: set[ct.Coord2]) -> pg.SparseLattice:
    body = {
        (x, y, 0)
        for x in range(-radius, radius + 1)
        for y in range(-radius, radius + 1)
        if (x, y) not in defects
    }
    return pg.SparseLattice.from_active(body)


class ChannelTelemetryTests(unittest.TestCase):
    def test_six_support_center_is_b6_birth(self) -> None:
        lattice = pg.six_support_demo_lattice()
        event = ct.channel_for_site(lattice, (0, 0, 0))
        self.assertEqual(event.raw_channel, "B6")
        self.assertTrue(event.accepted)
        self.assertEqual(event.next_state, ct.BODY)
        self.assertEqual(event.psi, 0)

    def test_channel_collapse_matches_pgvm_step(self) -> None:
        lattice = pg.six_support_demo_lattice()
        summary = ct.measure_channels(lattice)
        next_lattice, report = lattice.step()
        self.assertEqual(ct.collapsed_body(summary), next_lattice.body)
        self.assertEqual(summary.births, report["births"])
        self.assertEqual(summary.deaths, report["deaths"])
        self.assertEqual(summary.survivors, report["survivors"])

    def test_single_body_death_is_rejected_survival_channel(self) -> None:
        lattice = pg.single_body_demo_lattice()
        event = ct.channel_for_site(lattice, (0, 0, 0))
        self.assertEqual(event.raw_channel, "S0")
        self.assertFalse(event.accepted)
        self.assertEqual(event.next_state, ct.VOID)
        self.assertLess(event.psi, 0)

    def test_rectangle_2x2_defect_first_response_birth_spectrum(self) -> None:
        defects = ct.rectangular_defects(2, 2)
        lattice = defective_sheet_lattice(5, defects)
        coords = ct.normal_layer_candidate_coords(defects) | {(x, y, 0) for x, y in defects}
        summary = ct.measure_channels(lattice, coords)
        accepted = summary.accepted_counts()
        expected = ct.expected_rectangle_birth_spectrum(2, 2)
        self.assertEqual({k: accepted.get(k, 0) for k in expected}, expected)
        self.assertEqual(sum(expected.values()), 28)

    def test_defect_channel_identity_labels_normal_layer_candidates(self) -> None:
        defects = ct.rectangular_defects(2, 2)
        lattice = defective_sheet_lattice(5, defects)
        for coord in ct.normal_layer_candidate_coords(defects):
            event = ct.channel_for_site(lattice, coord)
            self.assertEqual(event.raw_channel, ct.defect_channel_label(coord, defects))


if __name__ == "__main__":
    unittest.main()
