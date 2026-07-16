#!/usr/bin/env python3
"""Emit a replay proof for a draft PGB2 bundle."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK_ROOT / "PooleGlyph"))

import pooleglyph_pgvm as pg  # noqa: E402
from runtime import channel_telemetry as ct  # noqa: E402
from runtime import pgb2_bundle as pgb2  # noqa: E402
from runtime import replay_proof as rp  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools.emit_channel_trace import build_case  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS replay proof for a PGB2 bundle.")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--case", default="six-support")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "replay_proof.json")
    args = parser.parse_args(argv)

    bundle = pgb2.read_bundle(args.bundle)
    bundle_result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
    if not bundle_result.ok:
        for error in bundle_result.errors:
            print(f"FAIL bundle {error}")
        return 1

    lattice, coords, _source_descriptor = build_case(args.case)
    raw_hex = pgb2.section_by_name(bundle, "CODE")["body"]["raw_hex"]
    vm = pg.PGVM(lattice.copy())
    final_lattice, report = vm.run(pg.bytes_from_hex(raw_hex), input_mode="raw-stream")
    report_obj = asdict(report)
    report_obj["final_body_count"] = len(final_lattice.body)

    recomputed = rp.recomputed_summary_json(ct.measure_channels(lattice, coords))
    proof = rp.make_replay_proof(
        case=args.case,
        bundle_path=args.bundle,
        bundle=bundle,
        pgvm_report=report_obj,
        recomputed_channel_summary=recomputed,
    )
    schema = json.loads((ROOT / "specs" / "replay-proof.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(proof, schema)
    if errors:
        for error in errors:
            print(f"FAIL proof {error.path}: {error.message}")
        return 1
    if not proof["channel_summary_match"]:
        print("FAIL proof channel summary mismatch")
        return 1
    rp.write_replay_proof(proof, args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
