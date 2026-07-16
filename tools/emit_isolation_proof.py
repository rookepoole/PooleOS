#!/usr/bin/env python3
"""Emit a static PooleOS microkernel isolation proof artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import microkernel_isolation  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS microkernel isolation spike proof.")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "microkernel_isolation.json")
    args = parser.parse_args(argv)

    proof = microkernel_isolation.make_isolation_proof()
    schema = json.loads((ROOT / "specs" / "isolation-proof.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(proof, schema)
    if errors:
        for error in errors:
            print(f"FAIL isolation_proof {error.path}: {error.message}")
        return 1
    microkernel_isolation.write_proof(proof, args.out)
    print(args.out)
    return 0 if proof["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
