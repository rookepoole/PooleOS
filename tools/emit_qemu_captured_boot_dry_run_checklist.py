#!/usr/bin/env python3
"""Emit a QEMU captured boot dry-run checklist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_captured_boot_dry_run_checklist  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a QEMU captured boot dry-run checklist.")
    parser.add_argument("--launch-bundle", type=Path, default=ROOT / "runs" / "qemu_captured_boot_launch_bundle.json")
    parser.add_argument("--release-gate-output", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_captured_boot_dry_run_checklist.json")
    args = parser.parse_args(argv)

    checklist = qemu_captured_boot_dry_run_checklist.make_qemu_captured_boot_dry_run_checklist(
        root=ROOT,
        launch_bundle_path=args.launch_bundle,
        checklist_output_path=args.out,
        release_gate_output_path=optional_path(args.release_gate_output),
    )
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-dry-run-checklist.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(checklist, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu captured boot dry-run checklist {error.path}: {error.message}")
        return 1
    qemu_captured_boot_dry_run_checklist.write_checklist(checklist, args.out)
    print(args.out)
    return 0 if checklist["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
