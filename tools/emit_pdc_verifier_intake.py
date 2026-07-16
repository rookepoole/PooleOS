#!/usr/bin/env python3
"""Import and verify the canonical exact-family PDC verifier sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_verifier_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the exact-family PDC verifier intake artifact.")
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--source-intake", type=Path, default=ROOT / "runs" / "pdc_source_intake.json")
    parser.add_argument("--math-contract", type=Path, default=ROOT / "runs" / "pdc_math_contract.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_verifier_intake.json")
    args = parser.parse_args(argv)

    try:
        artifact = pdc_verifier_intake.make_verifier_intake(
            workspace=ROOT,
            downloads=args.downloads,
            source_intake_path=args.source_intake,
            math_contract_path=args.math_contract,
            copy_files=True,
        )
    except pdc_verifier_intake.PdcVerifierIntakeError as exc:
        print(f"FAIL pdc_verifier_intake: {exc}")
        return 1

    schema = json.loads((ROOT / "specs" / "pdc-verifier-intake.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_verifier_intake {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
