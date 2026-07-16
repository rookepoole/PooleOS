#!/usr/bin/env python3
"""Emit source-bound PDC scalar/matrix and geometric golden vectors."""

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
    parser = argparse.ArgumentParser(description="Emit the canonical PDC golden-vector artifact.")
    parser.add_argument("--math-contract", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_golden_vectors.json")
    args = parser.parse_args(argv)

    vectors = pdc_evidence.make_golden_vectors(math_contract_path=args.math_contract, workspace=ROOT)
    schema = json.loads((ROOT / "specs" / "pdc-golden-vectors.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(vectors, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_golden_vectors {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(vectors, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
