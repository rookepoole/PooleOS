#!/usr/bin/env python3
"""Emit the PDC-REP-0.1 representation and conversion contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_representation_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the PDC representation ABI contract.")
    parser.add_argument("--math-contract", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    parser.add_argument("--golden-vectors", type=Path, default=ROOT / "runs" / "pdc_golden_vectors.json")
    parser.add_argument(
        "--verifier-reproduction",
        type=Path,
        default=ROOT / "runs" / "pdc_verifier_reproduction.json",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_representation_contract.json")
    args = parser.parse_args(argv)
    try:
        artifact = pdc_representation_evidence.make_representation_contract(
            workspace=ROOT,
            math_contract_path=args.math_contract,
            golden_vectors_path=args.golden_vectors,
            verifier_reproduction_path=args.verifier_reproduction,
        )
    except pdc_representation_evidence.PdcRepresentationEvidenceError as exc:
        print(f"FAIL pdc_representation_contract: {exc}")
        return 1
    schema = json.loads((ROOT / "specs" / "pdc-representation-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_representation_contract {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
