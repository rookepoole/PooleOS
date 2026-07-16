#!/usr/bin/env python3
"""Emit draft PGB2 byte encodings for capability trap proof operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pgb2_trap_encoding  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit draft PGB2 trap instruction encodings.")
    parser.add_argument("--trap-proof", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pgb2_trap_encoding.json")
    args = parser.parse_args(argv)

    encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=args.trap_proof)
    schema = json.loads((ROOT / "specs" / "pgb2-trap-encoding.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(encoding, schema)
    if errors:
        for error in errors:
            print(f"FAIL pgb2_trap_encoding {error.path}: {error.message}")
        return 1
    pgb2_trap_encoding.write_encoding(encoding, args.out)
    print(args.out)
    return 0 if encoding["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
