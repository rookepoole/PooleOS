#!/usr/bin/env python3
"""Emit PooleOS permission/capability/resource matrix evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import permission_capability_matrix  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS permission/capability/resource matrix.")
    parser.add_argument("--bridge-manifest", type=Path, required=True)
    parser.add_argument("--core-ir-boundary-receipt", type=Path, required=True)
    parser.add_argument("--core-ir-executable-audit", type=Path)
    parser.add_argument("--parser-kernel-promotion-receipt", type=Path, required=True)
    parser.add_argument("--pooleglyph", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "permission_capability_matrix.json")
    args = parser.parse_args(argv)

    matrix = permission_capability_matrix.make_permission_capability_matrix(
        bridge_manifest_path=args.bridge_manifest,
        core_ir_boundary_receipt_path=args.core_ir_boundary_receipt,
        core_ir_executable_audit_path=args.core_ir_executable_audit,
        parser_kernel_promotion_receipt_path=args.parser_kernel_promotion_receipt,
        pooleglyph_path=args.pooleglyph,
    )
    schema = json.loads((ROOT / "specs" / "permission-capability-matrix.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(matrix, schema)
    if errors:
        for error in errors:
            print(f"FAIL permission_capability_matrix {error.path}: {error.message}")
        return 1
    permission_capability_matrix.write_matrix(matrix, args.out)
    print(args.out)
    return 0 if matrix["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
