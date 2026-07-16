#!/usr/bin/env python3
"""Emit PooleGlyph executable Core IR audit evidence for PooleOS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_core_ir_executable_audit  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit PooleGlyph executable Core IR audit evidence.")
    parser.add_argument(
        "--core-ir-boundary-receipt",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_core_ir_boundary_receipt.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_core_ir_executable_audit.json",
    )
    args = parser.parse_args(argv)

    audit = pooleglyph_core_ir_executable_audit.make_pooleglyph_core_ir_executable_audit(
        core_ir_boundary_receipt_path=args.core_ir_boundary_receipt,
    )
    schema = json.loads((ROOT / "specs" / "pooleglyph-core-ir-executable-audit.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(audit, schema)
    if errors:
        for error in errors[:10]:
            print(f"FAIL pooleglyph_core_ir_executable_audit {error.path}: {error.message}")
        return 1
    pooleglyph_core_ir_executable_audit.write_audit(audit, args.out)
    print(args.out)
    return 0 if audit.get("status") != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
