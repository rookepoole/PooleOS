#!/usr/bin/env python3
"""Generate or verify the implementation-derived PFWM1 contract and vectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_firmware as pfwm1  # noqa: E402


def _bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = {
        ROOT / "specs/fixtures/pfwm1-canonical.bin": pfwm1.canonical_bundle(),
        ROOT / pfwm1.CONTRACT_RELATIVE: _bytes(pfwm1.expected_contract(ROOT)),
        ROOT / pfwm1.GOLDEN_RELATIVE: _bytes(pfwm1.make_golden_vectors()),
    }
    stale = [path for path, data in outputs.items() if not path.is_file() or path.read_bytes() != data]
    if args.check:
        if stale:
            for path in stale:
                print(f"stale: {path.relative_to(ROOT).as_posix()}")
            return 1
        print("PFWM1 contract and golden vectors are current")
        return 0
    for path, data in outputs.items():
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
