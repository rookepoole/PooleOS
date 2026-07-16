#!/usr/bin/env python3
"""Emit a kernel PGVM2 loader evidence boundary artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kernel_pgvm2_loader_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a kernel PGVM2 loader evidence boundary artifact.")
    parser.add_argument("--kernel-boot-handoff", type=Path, default=ROOT / "runs" / "kernel_boot_handoff.json")
    parser.add_argument("--kernel-loader-output", type=Path, default=ROOT / "runs" / "kernel_pgvm2_loader_output.json")
    parser.add_argument("--pooleglyph-source-anchor", type=Path, default=ROOT / "runs" / "pooleglyph_source_anchor.json")
    parser.add_argument(
        "--parser-kernel-promotion-receipt",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_parser_kernel_promotion_receipt.json",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "kernel_pgvm2_loader_evidence.json")
    args = parser.parse_args(argv)

    evidence = kernel_pgvm2_loader_evidence.make_kernel_pgvm2_loader_evidence(
        kernel_boot_handoff_path=args.kernel_boot_handoff,
        kernel_loader_output_path=args.kernel_loader_output,
        pooleglyph_source_anchor_path=args.pooleglyph_source_anchor,
        parser_kernel_promotion_receipt_path=args.parser_kernel_promotion_receipt,
    )
    schema = json.loads((ROOT / "specs" / "kernel-pgvm2-loader-evidence.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(evidence, schema)
    if errors:
        for error in errors:
            print(f"FAIL kernel PGVM2 loader evidence {error.path}: {error.message}")
        return 1
    kernel_pgvm2_loader_evidence.write_evidence(evidence, args.out)
    print(args.out)
    return 0 if evidence["status"] in {"blocked", "ready_for_kernel_loader", "kernel_enforced"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
