#!/usr/bin/env python3
"""Generate or verify canonical PMCU1 contracts, vectors, and fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_microcode as pmcu1  # noqa: E402


def _json_bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _outputs() -> dict[Path, bytes]:
    vectors = pmcu1.make_golden_vectors()
    return {
        ROOT / pmcu1.CONTRACT_RELATIVE: _json_bytes(pmcu1.expected_contract()),
        ROOT / pmcu1.GOLDEN_RELATIVE: _json_bytes(vectors),
        ROOT / "specs/fixtures/pmcu1-canonical.bin": pmcu1.canonical_bundle(),
        ROOT / "specs/fixtures/pmcu1-minimal.bin": pmcu1.minimal_bundle(),
        ROOT / "specs/fixtures/pmcu1-boundary.bin": pmcu1.boundary_bundle(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    mismatches: list[str] = []
    for path, expected in _outputs().items():
        if args.check:
            if not path.is_file() or path.read_bytes() != expected:
                mismatches.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if mismatches:
        print("PMCU1_GENERATION FAIL " + ",".join(mismatches))
        return 1
    print("PMCU1_GENERATION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
