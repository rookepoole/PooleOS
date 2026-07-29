#!/usr/bin/env python3
"""Generate or verify the exact public PBP1 golden byte vectors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_handoff as pbp1  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / pbp1.GOLDEN_RELATIVE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        value = pbp1.make_golden_vectors()
        encoded = pbp1.canonical_json_bytes(value)
        if args.check:
            if not args.out.is_file() or args.out.read_bytes() != encoded:
                print("FAIL PBP1 golden vectors are missing or stale")
                return 1
            print(
                f"PASS PBP1 golden vectors exact: vectors={len(value['vectors'])} "
                f"bytes={sum(item['byte_count'] for item in value['vectors'])}"
            )
            return 0
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(encoded)
        print(f"wrote {args.out}: vectors={len(value['vectors'])}")
        return 0
    except (OSError, ValueError, pbp1.BootHandoffError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
