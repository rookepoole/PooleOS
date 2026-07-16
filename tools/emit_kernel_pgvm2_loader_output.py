#!/usr/bin/env python3
"""Emit a non-claiming kernel PGVM2 loader output fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kernel_pgvm2_loader_output  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a non-claiming kernel PGVM2 loader output fixture.")
    parser.add_argument("--kernel-boot-handoff", type=Path, default=ROOT / "runs" / "kernel_boot_handoff.json")
    parser.add_argument("--pooleglyph-source-anchor", type=Path, default=ROOT / "runs" / "pooleglyph_source_anchor.json")
    parser.add_argument(
        "--parser-kernel-promotion-receipt",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_parser_kernel_promotion_receipt.json",
    )
    parser.add_argument("--kernel-build-id", default="pending-kernel-loader")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "kernel_pgvm2_loader_output.json")
    args = parser.parse_args(argv)

    output = kernel_pgvm2_loader_output.make_kernel_pgvm2_loader_output(
        kernel_boot_handoff_path=args.kernel_boot_handoff,
        pooleglyph_source_anchor_path=args.pooleglyph_source_anchor,
        parser_kernel_promotion_receipt_path=args.parser_kernel_promotion_receipt,
        kernel_build_id=args.kernel_build_id,
        mode="negative_fixture",
    )
    schema = json.loads((ROOT / "specs" / "kernel-pgvm2-loader-output.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(output, schema)
    if errors:
        for error in errors:
            print(f"FAIL kernel PGVM2 loader output {error.path}: {error.message}")
        return 1
    kernel_pgvm2_loader_output.write_output(output, args.out)
    print(args.out)
    return 0 if output["status"] == "blocked" and output["kernel_enforcement_claimed"] is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
