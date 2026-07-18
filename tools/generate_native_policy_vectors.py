#!/usr/bin/env python3
"""Generate or verify PPOL1 fixtures, contract, and golden vectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_initial_system as pinit1  # noqa: E402
from runtime import native_policy as ppol1  # noqa: E402


FIXTURES = {
    ROOT / "specs/fixtures/ppol1-canonical.bin": ppol1.canonical_bundle,
    ROOT / "specs/fixtures/ppol1-minimal.bin": ppol1.minimal_bundle,
    ROOT / "specs/fixtures/ppol1-boundary.bin": ppol1.boundary_bundle,
    ROOT / "specs/fixtures/ppol1-canonical-pinit.bin": pinit1.canonical_bundle,
}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _outputs() -> dict[Path, bytes]:
    values = {path: factory() for path, factory in FIXTURES.items()}
    values[ROOT / ppol1.CONTRACT_RELATIVE] = _json_bytes(ppol1.expected_contract(ROOT))
    values[ROOT / ppol1.GOLDEN_RELATIVE] = _json_bytes(ppol1.make_golden_vectors())
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fixtures-only", action="store_true")
    args = parser.parse_args(argv)
    outputs = {path: factory() for path, factory in FIXTURES.items()} if args.fixtures_only else _outputs()
    stale = [path for path, data in outputs.items() if not path.is_file() or path.read_bytes() != data]
    if args.check:
        if stale:
            for path in stale:
                print(f"stale: {path.relative_to(ROOT).as_posix()}")
            return 1
        print("PPOL1 fixtures, contract, and golden vectors are current")
        return 0
    for path, data in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
