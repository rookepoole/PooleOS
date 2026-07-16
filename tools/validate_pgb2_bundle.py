#!/usr/bin/env python3
"""Validate a draft PGB2 JSON bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pgb2_bundle as pgb2  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a PooleOS PGB2 draft bundle.")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)

    bundle = pgb2.read_bundle(args.bundle)
    result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
    if not result.ok:
        for error in result.errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

