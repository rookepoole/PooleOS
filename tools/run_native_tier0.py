#!/usr/bin/env python3
"""Prepare or execute one pinned native-only PooleOS Tier 0 launch."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_tier0  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu-root", type=Path, default=native_tier0.DEFAULT_QEMU_ROOT)
    parser.add_argument("--profile", choices=native_tier0.PROFILE_IDS, required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    if args.timeout < 1 or args.timeout > 600:
        parser.error("--timeout must be between 1 and 600 seconds")
    try:
        command, receipt = native_tier0.prepare_launch(
            args.qemu_root,
            args.media,
            args.run_dir,
            args.profile,
            debug=args.debug,
        )
        if args.execute:
            receipt["execution"]["requested"] = True
            receipt["execution"]["started"] = True
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                completed = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=args.timeout,
                    creationflags=creationflags,
                )
                receipt["status"] = "process_exited_non_promoting"
                receipt["execution"]["exit_code"] = completed.returncode
            except subprocess.TimeoutExpired:
                receipt["status"] = "process_timeout_non_promoting"
                receipt["execution"]["timed_out"] = True
        schema_errors = native_tier0.schema_errors(receipt, ROOT, native_tier0.LAUNCH_SCHEMA_RELATIVE)
        if schema_errors:
            raise native_tier0.Tier0Error("launch receipt schema failure: " + "; ".join(schema_errors[:8]))
        receipt_path = args.run_dir.resolve() / "native_tier0_launch_receipt.json"
        native_tier0.write_json(receipt, receipt_path)
    except (OSError, ValueError, KeyError, native_tier0.Tier0Error) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 2
    print(
        f"wrote {receipt_path}: profile={args.profile} status={receipt['status']} "
        "boot_claimed=false production_promotion_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
