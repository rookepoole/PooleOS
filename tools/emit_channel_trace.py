#!/usr/bin/env python3
"""Emit PooleOS channel trace artifacts for reference lattice cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK_ROOT / "PooleGlyph"))

import pooleglyph_pgvm as pg  # noqa: E402
from runtime import channel_telemetry as ct  # noqa: E402
from runtime import channel_trace as trace  # noqa: E402


def defective_sheet_lattice(radius: int, defects: set[ct.Coord2]) -> pg.SparseLattice:
    body = {
        (x, y, 0)
        for x in range(-radius, radius + 1)
        for y in range(-radius, radius + 1)
        if (x, y) not in defects
    }
    return pg.SparseLattice.from_active(body)


def build_case(case: str) -> tuple[pg.SparseLattice, set[ct.Coord] | None, str]:
    normalized = case.strip().lower().replace("_", "-")
    if normalized in {"six-support", "six"}:
        return pg.six_support_demo_lattice(), None, "pooleglyph:six-support"
    if normalized in {"single", "single-body"}:
        return pg.single_body_demo_lattice(), None, "pooleglyph:single-body"
    if normalized in {"rectangle-2x2", "rect-2x2"}:
        defects = ct.rectangular_defects(2, 2)
        coords = ct.normal_layer_candidate_coords(defects) | {(x, y, 0) for x, y in defects}
        return defective_sheet_lattice(5, defects), coords, "defective-sheet:rectangle-2x2"
    raise ValueError(f"unknown trace case {case!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS channel trace JSON artifact.")
    parser.add_argument("--case", default="six-support", help="six-support, single-body, or rectangle-2x2")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "channel_trace.json")
    args = parser.parse_args(argv)

    lattice, coords, source_descriptor = build_case(args.case)
    summary = ct.measure_channels(lattice, coords)
    claim = trace.make_claim_record(
        claim_id="TRACE-001",
        title=f"Channel trace for {args.case}",
        source_descriptor=source_descriptor,
        limitations="Reference trace artifact for PooleOS kernel telemetry; not a physical or safety claim.",
    )
    artifact = trace.make_channel_trace(summary, claim=claim)
    trace.write_channel_trace(artifact, args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

