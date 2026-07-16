#!/usr/bin/env python3
"""Emit a non-mutating WSL prerequisite report for PooleOS Lab."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import wsl_prerequisites  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a non-mutating WSL prerequisite report.")
    parser.add_argument("--distro", default="Ubuntu")
    parser.add_argument("--buildroot-path", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "wsl_prerequisites.json")
    args = parser.parse_args(argv)

    report = wsl_prerequisites.make_prerequisite_report(
        distro=args.distro,
        buildroot_path=args.buildroot_path,
    )
    schema = json.loads((ROOT / "specs" / "wsl-prerequisites.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        for error in errors:
            print(f"FAIL wsl_prerequisites {error.path}: {error.message}")
        return 1
    wsl_prerequisites.write_report(report, args.out)
    print(args.out)
    return 0 if report["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
