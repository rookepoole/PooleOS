#!/usr/bin/env python3
"""Emit the source-bound canonical PDC math contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the canonical PDC math contract.")
    parser.add_argument("--source-intake", type=Path, default=ROOT / "runs" / "pdc_source_intake.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    args = parser.parse_args(argv)

    contract = pdc_evidence.make_math_contract(source_intake_path=args.source_intake, workspace=ROOT)
    schema = json.loads((ROOT / "specs" / "pdc-math-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(contract, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_math_contract {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
