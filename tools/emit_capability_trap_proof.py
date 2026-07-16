#!/usr/bin/env python3
"""Emit PGB2-style capability trap proof evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import capability_traps  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit PooleOS capability trap proof evidence.")
    parser.add_argument("--isolation-proof", type=Path)
    parser.add_argument("--permission-capability-matrix", type=Path)
    parser.add_argument("--capability-trap-fuzz", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "capability_trap_proof.json")
    args = parser.parse_args(argv)

    proof = capability_traps.make_capability_trap_proof(
        policy_artifact=args.isolation_proof,
        permission_matrix_artifact=args.permission_capability_matrix,
        trap_fuzz_artifact=args.capability_trap_fuzz,
    )
    schema = json.loads((ROOT / "specs" / "capability-trap-proof.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(proof, schema)
    if errors:
        for error in errors:
            print(f"FAIL capability_trap_proof {error.path}: {error.message}")
        return 1
    capability_traps.write_proof(proof, args.out)
    print(args.out)
    return 0 if proof["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
