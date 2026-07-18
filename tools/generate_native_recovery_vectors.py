#!/usr/bin/env python3
"""Regenerate the canonical PREC1 contract, vectors, and Rust fixtures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_recovery as prec1  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    policy = prec1.canonical_bundle()
    state = prec1.encode_state(prec1.canonical_state(prec1.parse(policy)))
    outputs = (
        (ROOT / prec1.CONTRACT_RELATIVE, prec1.canonical_json_bytes(prec1.expected_contract())),
        (ROOT / prec1.GOLDEN_RELATIVE, prec1.canonical_json_bytes(prec1.make_golden_vectors())),
        (ROOT / "specs/fixtures/prec1-canonical.bin", policy),
        (ROOT / "specs/fixtures/prec1-canonical-state.bin", state),
    )
    stale = [path for path, data in outputs if not path.is_file() or path.read_bytes() != data]
    if args.check:
        if stale:
            print("PREC1_GENERATION FAIL " + " ".join(path.name for path in stale))
            return 1
    else:
        for path, data in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"PREC1_GENERATION PASS outputs={len(outputs)} check={str(args.check).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
