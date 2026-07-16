#!/usr/bin/env python3
"""Emit a QEMU boot marker responsibility contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_boot_marker_contract  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a QEMU boot marker responsibility contract.")
    parser.add_argument("--dry-run-checklist", type=Path, default=ROOT / "runs" / "qemu_captured_boot_dry_run_checklist.json")
    parser.add_argument("--lab-guest-autostart", type=Path, default=ROOT / "runs" / "lab_guest_autostart.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_boot_marker_contract.json")
    args = parser.parse_args(argv)

    contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
        root=ROOT,
        dry_run_checklist_path=args.dry_run_checklist,
        lab_guest_autostart_path=args.lab_guest_autostart,
    )
    schema = json.loads((ROOT / "specs" / "qemu-boot-marker-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(contract, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu boot marker contract {error.path}: {error.message}")
        return 1
    qemu_boot_marker_contract.write_contract(contract, args.out)
    print(args.out)
    return 0 if contract["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
