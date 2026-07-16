#!/usr/bin/env python3
"""Validate a PooleOS Lab QEMU serial boot log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_log  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate PooleOS Lab boot-log markers.")
    parser.add_argument("log", type=Path)
    parser.add_argument("--profile", choices=["base", "trap-input"], default="base")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    result = boot_log.validate_boot_log_file(args.log, profile=args.profile)
    schema = json.loads((ROOT / "specs" / "boot-log.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(result, schema)
    if errors:
        for error in errors:
            print(f"FAIL schema {error.path}: {error.message}")
        return 1
    if args.out:
        boot_log.write_validation(result, args.out)
    if not result["ok"]:
        print(f"FAIL missing markers: {', '.join(result['missing_markers'])}")
        return 1
    print(f"PASS {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
