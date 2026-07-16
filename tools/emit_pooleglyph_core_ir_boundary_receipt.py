#!/usr/bin/env python3
"""Emit a PooleGlyph Core IR boundary receipt for PooleOS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_core_ir_boundary_receipt  # noqa: E402
from runtime import pooleglyph_source_anchor  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleGlyph Core IR boundary receipt for PooleOS.")
    parser.add_argument(
        "--bridge-manifest",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_bridge_manifest.json",
    )
    parser.add_argument(
        "--pooleglyph",
        type=Path,
        default=pooleglyph_source_anchor.default_pooleglyph_path(workspace_root=WORK_ROOT),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_core_ir_boundary_receipt.json",
    )
    args = parser.parse_args(argv)

    receipt = pooleglyph_core_ir_boundary_receipt.make_pooleglyph_core_ir_boundary_receipt(
        bridge_manifest_path=args.bridge_manifest,
        pooleglyph_path=args.pooleglyph,
    )
    schema = json.loads((ROOT / "specs" / "pooleglyph-core-ir-boundary-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors[:10]:
            print(f"FAIL pooleglyph_core_ir_boundary_receipt {error.path}: {error.message}")
        return 1
    pooleglyph_core_ir_boundary_receipt.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt.get("status") != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
