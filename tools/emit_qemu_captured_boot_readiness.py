#!/usr/bin/env python3
"""Emit captured-QEMU promotion readiness evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_captured_boot_readiness  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit captured-QEMU promotion readiness evidence.")
    parser.add_argument("--rootfs-extraction-receipt", type=Path, default=ROOT / "runs" / "rootfs_extraction_receipt.json")
    parser.add_argument("--qemu-captured-boot-receipt", type=Path, default=ROOT / "runs" / "qemu_captured_boot_receipt.json")
    parser.add_argument("--qemu-captured-boot-evidence", type=Path, default=ROOT / "runs" / "qemu_boot_evidence.captured.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_captured_boot_readiness.json")
    args = parser.parse_args(argv)

    readiness = qemu_captured_boot_readiness.make_qemu_captured_boot_readiness(
        rootfs_extraction_receipt_path=args.rootfs_extraction_receipt,
        qemu_captured_boot_receipt_path=args.qemu_captured_boot_receipt,
        qemu_captured_boot_evidence_path=args.qemu_captured_boot_evidence,
    )
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-readiness.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(readiness, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu captured boot readiness {error.path}: {error.message}")
        return 1
    qemu_captured_boot_readiness.write_readiness(readiness, args.out)
    print(args.out)
    return 0 if readiness["status"] in {"blocked", "ready_for_promotion"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
