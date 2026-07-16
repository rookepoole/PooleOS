#!/usr/bin/env python3
"""Run or block the WSL Buildroot defconfig step with structured evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import wsl_configure  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PooleOS Lab Buildroot defconfig through WSL.")
    parser.add_argument("--buildroot-path", type=Path, required=True)
    parser.add_argument("--prerequisites", type=Path, required=True)
    parser.add_argument("--distro", default="Ubuntu")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "buildroot_configure_wsl.json")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args(argv)

    report = wsl_configure.make_configure_report(
        buildroot_path=args.buildroot_path,
        external_path=ROOT / "lab-os" / "buildroot" / "external",
        prerequisites_path=args.prerequisites,
        distro=args.distro,
        output_dir=optional_path(args.output_dir),
        timeout_seconds=args.timeout_seconds,
    )
    schema = json.loads((ROOT / "specs" / "buildroot-configure.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        for error in errors:
            print(f"FAIL wsl_configure {error.path}: {error.message}")
        return 1
    wsl_configure.write_configure_report(report, args.out)
    print(args.out)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
