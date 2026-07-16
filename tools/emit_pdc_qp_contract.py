#!/usr/bin/env python3
"""Emit the source-bound PDC-QP-0.1 contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_qp_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the PDC-QP-0.1 contract.")
    parser.add_argument("--source-intake", type=Path, default=ROOT / "runs" / "pdc_source_intake.json")
    parser.add_argument("--verifier-intake", type=Path, default=ROOT / "runs" / "pdc_verifier_intake.json")
    parser.add_argument("--math-contract", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_qp_contract.json")
    args = parser.parse_args(argv)
    try:
        artifact = pdc_qp_evidence.make_qp_contract(
            workspace=ROOT,
            source_intake_path=args.source_intake,
            verifier_intake_path=args.verifier_intake,
            math_contract_path=args.math_contract,
        )
    except pdc_qp_evidence.PdcQpEvidenceError as exc:
        print(f"FAIL pdc_qp_contract: {exc}")
        return 1
    schema = json.loads((ROOT / "specs" / "pdc-qp-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_qp_contract {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
