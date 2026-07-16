#!/usr/bin/env python3
"""Emit a QEMU captured boot receipt for PooleOS release handoff."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_captured_boot_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a QEMU captured boot receipt.")
    parser.add_argument("--fixture-evidence", type=Path, default=ROOT / "runs" / "qemu_boot_evidence.json")
    parser.add_argument("--captured-evidence", type=Path, default=ROOT / "runs" / "qemu_boot_evidence.captured.json")
    parser.add_argument("--operator-executed", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_captured_boot_receipt.json")
    args = parser.parse_args(argv)

    receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
        fixture_evidence_path=args.fixture_evidence,
        captured_evidence_path=args.captured_evidence,
        operator_executed=args.operator_executed,
    )
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu captured boot receipt {error.path}: {error.message}")
        return 1
    qemu_captured_boot_receipt.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt["status"] in {"pending_capture", "captured"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
