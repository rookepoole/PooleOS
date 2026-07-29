#!/usr/bin/env python3
"""Regenerate the canonical PINIT1 contract and golden vectors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_initial_system as pinit1  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = (
        (ROOT / pinit1.CONTRACT_RELATIVE, pinit1.canonical_json_bytes(pinit1.expected_contract())),
        (ROOT / pinit1.GOLDEN_RELATIVE, pinit1.canonical_json_bytes(pinit1.make_golden_vectors())),
    )
    stale = [path for path, data in outputs if not path.is_file() or path.read_bytes() != data]
    if args.check:
        if stale:
            print("PINIT1_GENERATION FAIL " + " ".join(path.name for path in stale))
            return 1
    else:
        for path, data in outputs:
            path.write_bytes(data)
    print(f"PINIT1_GENERATION PASS outputs={len(outputs)} check={str(args.check).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
