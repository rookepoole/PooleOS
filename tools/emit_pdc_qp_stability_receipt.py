#!/usr/bin/env python3
"""Emit the PDC-QP-STABILITY-0.1 reproduction and perturbation receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_qp_stability_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the PDC-QP-STABILITY-0.1 receipt.")
    parser.add_argument("--contract", type=Path, default=ROOT / "runs" / "pdc_qp_stability_contract.json")
    parser.add_argument("--qp-contract", type=Path, default=ROOT / "runs" / "pdc_qp_contract.json")
    parser.add_argument("--qp-receipt", type=Path, default=ROOT / "runs" / "pdc_qp_receipt.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_qp_stability_receipt.json")
    args = parser.parse_args(argv)
    try:
        artifact = pdc_qp_stability_evidence.make_stability_receipt(
            workspace=ROOT,
            contract_path=args.contract,
            qp_contract_path=args.qp_contract,
            qp_receipt_path=args.qp_receipt,
        )
    except pdc_qp_stability_evidence.PdcQpStabilityEvidenceError as exc:
        print(f"FAIL pdc_qp_stability_receipt: {exc}")
        return 1
    schema = json.loads((ROOT / "specs" / "pdc-qp-stability-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_qp_stability_receipt {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
