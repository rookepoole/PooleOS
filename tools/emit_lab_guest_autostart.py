#!/usr/bin/env python3
"""Emit PooleOS Lab guest autostart evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import lab_guest_autostart  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit PooleOS Lab guest autostart evidence.")
    parser.add_argument("--qemu-shared-folder-contract", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "lab_guest_autostart.json")
    args = parser.parse_args(argv)

    manifest = lab_guest_autostart.make_lab_guest_autostart(
        root=ROOT,
        qemu_shared_folder_contract_path=args.qemu_shared_folder_contract,
    )
    schema = json.loads((ROOT / "specs" / "lab-guest-autostart.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL lab_guest_autostart {error.path}: {error.message}")
        return 1
    lab_guest_autostart.write_manifest(manifest, args.out)
    print(args.out)
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
