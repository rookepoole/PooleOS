#!/usr/bin/env python3
"""Regenerate the canonical PSYM1 contract, vectors, and Rust fixtures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_symbols as psym1  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = (
        (ROOT / psym1.CONTRACT_RELATIVE, psym1.canonical_json_bytes(psym1.expected_contract())),
        (ROOT / psym1.GOLDEN_RELATIVE, psym1.canonical_json_bytes(psym1.make_golden_vectors())),
        (ROOT / "specs/fixtures/psym1-canonical.bin", psym1.canonical_bundle()),
        (ROOT / "specs/fixtures/psym1-minimal.bin", psym1.minimal_bundle()),
        (ROOT / "specs/fixtures/psym1-boundary.bin", psym1.boundary_bundle()),
    )
    stale = [path for path, data in outputs if not path.is_file() or path.read_bytes() != data]
    if args.check:
        if stale:
            print("PSYM1_GENERATION FAIL " + " ".join(path.name for path in stale))
            return 1
    else:
        for path, data in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"PSYM1_GENERATION PASS outputs={len(outputs)} check={str(args.check).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
