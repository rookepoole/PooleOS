#!/usr/bin/env python3
"""Emit a draft PGB2 bundle containing PGB1-compatible code and channel trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK_ROOT / "PooleGlyph"))

import pooleglyph_pgvm as pg  # noqa: E402
from runtime import channel_telemetry as ct  # noqa: E402
from runtime import channel_trace as tr  # noqa: E402
from runtime import pgb2_bundle as pgb2  # noqa: E402
from runtime import signed_membrane as sm  # noqa: E402
from tools.emit_channel_trace import build_case  # noqa: E402


PGASM_BY_CASE = {
    "six-support": "MATCH_STATE void\nFILTER_K_EQ 6\nWRITE_MATCH body\nCOMMIT\nHALT\n",
    "single-body": "MATCH_STATE body\nFILTER_K_LT 5\nWRITE_MATCH void\nCOMMIT\nHALT\n",
    "rectangle-2x2": "MATCH_STATE void\nFILTER_K_RANGE 5 7\nWRITE_MATCH body\nCOMMIT\nHALT\n",
}


def normalize_case(case: str) -> str:
    normalized = case.strip().lower().replace("_", "-")
    if normalized == "six":
        return "six-support"
    if normalized == "single":
        return "single-body"
    if normalized == "rect-2x2":
        return "rectangle-2x2"
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a draft PooleOS PGB2 bundle.")
    parser.add_argument("--case", default="six-support", help="six-support, single-body, or rectangle-2x2")
    parser.add_argument("--include-signed-metrics", action="store_true", help="Attach mirrored-sheet signed membrane metrics.")
    parser.add_argument("--trap-encoding", type=Path, help="Attach a PGB2 trap encoding artifact.")
    parser.add_argument("--trap-execution", type=Path, help="Attach a PGB2 trap execution artifact.")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pooleos_bundle.pgb2.json")
    args = parser.parse_args(argv)

    case = normalize_case(args.case)
    if case not in PGASM_BY_CASE:
        raise ValueError(f"unknown bundle case {args.case!r}")

    lattice, coords, source_descriptor = build_case(case)
    summary = ct.measure_channels(lattice, coords)
    claim = tr.make_claim_record(
        claim_id="PGB2-TRACE-001",
        title=f"PGB2 bundle for {case}",
        source_descriptor=source_descriptor,
        limitations="Draft PGB2 JSON bundle for kernel telemetry validation; not a stable binary bytecode format.",
    )
    trace_artifact = tr.make_channel_trace(summary, claim=claim)

    raw_code = pg.PGAssembler().assemble_raw(PGASM_BY_CASE[case])
    code_body = pgb2.make_code_body(raw_hex=pg.hex_bytes(raw_code), source_label=f"pgasm:{case}")
    extra_sections = []
    if args.include_signed_metrics:
        signed_claim = tr.make_claim_record(
            claim_id="SIGNED-001",
            title="Mirrored signed sheet-pair smoke metrics",
            claim_lane="benchmark",
            evidence_kind="benchmark",
            rule="signed-membrane-smoke",
            model_tag="signed",
            source_descriptor="signed:mirrored-sheet-pair",
            limitations="Smoke-test benchmark descriptor only; not a physical, safety, or production-control claim.",
        )
        metrics = sm.measure_membrane(sm.mirrored_sheet_pair(size=3, gap=1))
        signed_artifact = sm.make_metrics_artifact(metrics, claim=signed_claim)
        extra_sections.append(pgb2.make_section("SIGNED_METRICS", pgb2.SIGNED_METRICS_MEDIA_TYPE, signed_artifact))
    if bool(args.trap_encoding) != bool(args.trap_execution):
        raise ValueError("--trap-encoding and --trap-execution must be provided together")
    if args.trap_encoding and args.trap_execution:
        trap_encoding = json.loads(args.trap_encoding.read_text(encoding="utf-8-sig"))
        trap_execution = json.loads(args.trap_execution.read_text(encoding="utf-8-sig"))
        extra_sections.extend(
            pgb2.make_trap_evidence_sections(
                trap_encoding=trap_encoding,
                trap_execution=trap_execution,
            )
        )
    bundle = pgb2.make_bundle(code_body=code_body, trace_artifact=trace_artifact, extra_sections=extra_sections)
    result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
    if not result.ok:
        for error in result.errors:
            print(f"FAIL {error}")
        return 1
    pgb2.write_bundle(bundle, args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
