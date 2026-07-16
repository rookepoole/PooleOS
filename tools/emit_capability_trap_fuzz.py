#!/usr/bin/env python3
"""Emit deterministic PooleOS capability trap fuzz evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import capability_trap_fuzz  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit deterministic capability trap fuzz proof evidence.")
    parser.add_argument("--isolation-proof", type=Path)
    parser.add_argument("--permission-capability-matrix", type=Path, required=True)
    parser.add_argument("--unknown-capability-count", type=int, default=12)
    parser.add_argument("--unknown-permission-count", type=int, default=8)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "capability_trap_fuzz.json")
    args = parser.parse_args(argv)

    fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
        policy_artifact=args.isolation_proof,
        permission_matrix_artifact=args.permission_capability_matrix,
        unknown_capability_count=args.unknown_capability_count,
        unknown_permission_count=args.unknown_permission_count,
    )
    schema = json.loads((ROOT / "specs" / "capability-trap-fuzz.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(fuzz, schema)
    if errors:
        for error in errors:
            print(f"FAIL capability_trap_fuzz {error.path}: {error.message}")
        return 1
    capability_trap_fuzz.write_fuzz(fuzz, args.out)
    print(args.out)
    return 0 if fuzz["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
