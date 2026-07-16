#!/usr/bin/env python3
"""Emit a PooleOS operator action receipt from post-action evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import operator_action  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS operator action receipt.")
    parser.add_argument("--operator-action", type=Path, required=True)
    parser.add_argument("--wsl-prerequisites", type=Path, required=True)
    parser.add_argument("--operator-executed", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "operator_action_receipt.json")
    args = parser.parse_args(argv)

    receipt = operator_action.make_wsl_package_install_receipt(
        operator_action_path=args.operator_action,
        verification_prerequisites_path=args.wsl_prerequisites,
        operator_executed=args.operator_executed,
    )
    schema = json.loads((ROOT / "specs" / "operator-action-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors:
            print(f"FAIL operator_receipt {error.path}: {error.message}")
        return 1
    operator_action.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt["status"] in {"pending_operator_action", "verified"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
