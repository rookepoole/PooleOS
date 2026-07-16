#!/usr/bin/env python3
"""Run PooleOS host preflight checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import host_preflight  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PooleOS host preflight checks.")
    parser.add_argument("--buildroot-path", type=Path)
    parser.add_argument("--qemu-command", default="qemu-system-x86_64")
    parser.add_argument("--include-wsl", action="store_true", help="Also inspect WSL for Linux build tools.")
    parser.add_argument("--wsl-distro", default="Ubuntu")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "host_preflight.json")
    parser.add_argument("--strict", action="store_true", help="Return nonzero on warning as well as failure.")
    args = parser.parse_args(argv)

    report = host_preflight.build_preflight_report(
        root=ROOT,
        buildroot_path=args.buildroot_path,
        qemu_command=args.qemu_command,
        include_wsl=args.include_wsl,
        wsl_distro=args.wsl_distro,
    )
    schema = json.loads((ROOT / "specs" / "host-preflight.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        for error in errors:
            print(f"FAIL preflight {error.path}: {error.message}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out)
    if report["status"] == "fail":
        return 1
    if args.strict and report["status"] == "warn":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
