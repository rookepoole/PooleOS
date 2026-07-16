#!/usr/bin/env python3
"""Emit a QEMU boot marker image-binding artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_boot_marker_image_binding  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a QEMU boot marker image-binding artifact.")
    parser.add_argument("--marker-contract", type=Path, default=ROOT / "runs" / "qemu_boot_marker_contract.json")
    parser.add_argument("--lab-image-manifest", type=Path, default=ROOT / "runs" / "lab_image_manifest.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_boot_marker_image_binding.json")
    args = parser.parse_args(argv)

    binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
        root=ROOT,
        marker_contract_path=args.marker_contract,
        lab_image_manifest_path=args.lab_image_manifest,
    )
    schema = json.loads((ROOT / "specs" / "qemu-boot-marker-image-binding.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(binding, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu boot marker image binding {error.path}: {error.message}")
        return 1
    qemu_boot_marker_image_binding.write_binding(binding, args.out)
    print(args.out)
    return 0 if binding["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
