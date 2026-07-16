#!/usr/bin/env python3
"""Emit a PooleOS rootfs extraction operator receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import rootfs_extraction_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS rootfs extraction operator receipt.")
    parser.add_argument("--handoff", type=Path, default=ROOT / "runs" / "rootfs_extraction_handoff.json")
    parser.add_argument("--rootfs-content-manifest", type=Path, default=ROOT / "runs" / "rootfs_content_manifest.json")
    parser.add_argument("--operator-executed", action="store_true")
    parser.add_argument("--operator-notes", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "rootfs_extraction_receipt.json")
    args = parser.parse_args(argv)

    receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
        handoff_path=args.handoff,
        rootfs_content_manifest_path=args.rootfs_content_manifest,
        operator_executed=args.operator_executed,
        operator_notes=args.operator_notes,
    )
    schema = json.loads((ROOT / "specs" / "rootfs-extraction-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors:
            print(f"FAIL rootfs extraction receipt {error.path}: {error.message}")
        return 1
    rootfs_extraction_receipt.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt["status"] in {"pending_operator_action", "verified", "verification_failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
