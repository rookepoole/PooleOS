#!/usr/bin/env python3
"""Emit PooleGlyph parser-to-kernel promotion receipt evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_parser_kernel_promotion_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit PooleGlyph parser-to-kernel promotion receipt evidence.")
    parser.add_argument(
        "--core-ir-executable-audit",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_core_ir_executable_audit.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "runs" / "pooleglyph_parser_kernel_promotion_receipt.json",
    )
    args = parser.parse_args(argv)

    receipt = pooleglyph_parser_kernel_promotion_receipt.make_pooleglyph_parser_kernel_promotion_receipt(
        core_ir_executable_audit_path=args.core_ir_executable_audit,
    )
    schema = json.loads(
        (ROOT / "specs" / "pooleglyph-parser-kernel-promotion-receipt.schema.json").read_text(encoding="utf-8")
    )
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors[:10]:
            print(f"FAIL pooleglyph_parser_kernel_promotion_receipt {error.path}: {error.message}")
        return 1
    pooleglyph_parser_kernel_promotion_receipt.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt.get("status") != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
