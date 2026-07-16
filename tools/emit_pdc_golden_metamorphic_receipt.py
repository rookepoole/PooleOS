#!/usr/bin/env python3
"""Emit independent scalar/matrix/direct/representation evidence for PDC-GOLDEN-0.2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_golden_metamorphic  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the PDC-GOLDEN-0.2 verification receipt.")
    parser.add_argument("--corpus", type=Path, default=ROOT / "runs" / "pdc_golden_metamorphic_corpus.json")
    parser.add_argument("--math-contract", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    parser.add_argument("--predecessor-golden", type=Path, default=ROOT / "runs" / "pdc_golden_vectors.json")
    parser.add_argument("--representation-contract", type=Path, default=ROOT / "runs" / "pdc_representation_contract.json")
    parser.add_argument("--representation-receipt", type=Path, default=ROOT / "runs" / "pdc_representation_receipt.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_golden_metamorphic_receipt.json")
    args = parser.parse_args(argv)
    try:
        artifact = pdc_golden_metamorphic.make_golden_metamorphic_receipt(
            workspace=ROOT,
            corpus_path=args.corpus,
            math_contract_path=args.math_contract,
            predecessor_golden_path=args.predecessor_golden,
            representation_contract_path=args.representation_contract,
            representation_receipt_path=args.representation_receipt,
        )
    except pdc_golden_metamorphic.PdcGoldenMetamorphicError as exc:
        print(f"FAIL pdc_golden_metamorphic_receipt: {exc}")
        return 1
    schema = json.loads((ROOT / "specs" / "pdc-golden-metamorphic-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_golden_metamorphic_receipt {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
