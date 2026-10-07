#!/usr/bin/env python3
"""Bind retained execution snapshots without rewriting original profile receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_execution_sources as sources


def qualify(captures: dict[str, Path], root: Path = ROOT) -> dict:
    if set(captures) != set(sources.PROFILES):
        raise sources.SourceEvidenceError("exact fourteen-profile capture set required")
    result = {"format": "POOLEOS-STATIC-EXECUTION-SOURCES-1",
              "profiles": [sources.captured_profile(p, captures[p], root) for p in sources.PROFILES],
              "boundaries": dict(sources.BOUNDARIES)}
    errors = sources.evidence_errors(result, root)
    if errors:
        raise sources.SourceEvidenceError("; ".join(errors))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", required=True, metavar="PROFILE=PATH")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        captures = {}
        for item in args.capture:
            profile, path = item.split("=", 1)
            if profile in captures:
                raise sources.SourceEvidenceError("duplicate capture profile")
            captures[profile] = Path(path)
        result = qualify(captures)
        with args.out.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print("EXECUTION_SOURCE_CLOSURE PASS profiles=14 fresh_boots=0 production_ready=false")
        return 0
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(f"EXECUTION_SOURCE_CLOSURE FAIL {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
