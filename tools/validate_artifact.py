#!/usr/bin/env python3
"""Validate a PooleOS JSON artifact against a local schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a PooleOS JSON artifact.")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--schema", type=Path, default=ROOT / "specs" / "channel-trace.schema.json")
    args = parser.parse_args(argv)

    artifact = json.loads(args.artifact.read_text(encoding="utf-8-sig"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL {error.path}: {error.message}")
        return 1
    print(f"PASS {args.artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
