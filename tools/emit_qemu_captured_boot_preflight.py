#!/usr/bin/env python3
"""Emit QEMU captured boot preflight evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_captured_boot_preflight  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit QEMU captured boot preflight evidence.")
    parser.add_argument("--image", default="")
    parser.add_argument("--kernel", default="")
    parser.add_argument("--serial-log", default="")
    parser.add_argument("--shared-output", default="")
    parser.add_argument("--boot-validation-output", default="")
    parser.add_argument("--qemu-boot-evidence-output", default="")
    parser.add_argument("--qemu-captured-boot-receipt-output", default="")
    parser.add_argument("--qemu-command", default="qemu-system-x86_64")
    parser.add_argument("--require-kernel", action="store_true")
    parser.add_argument("--no-virtfs", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_captured_boot_preflight.json")
    args = parser.parse_args(argv)

    report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
        root=ROOT,
        image_path=optional_path(args.image),
        kernel_path=optional_path(args.kernel),
        serial_log_path=optional_path(args.serial_log),
        shared_output_path=optional_path(args.shared_output),
        boot_validation_output=optional_path(args.boot_validation_output),
        qemu_boot_evidence_output=optional_path(args.qemu_boot_evidence_output),
        qemu_captured_boot_receipt_output=optional_path(args.qemu_captured_boot_receipt_output),
        qemu_command=args.qemu_command,
        require_kernel=args.require_kernel,
        no_virtfs=args.no_virtfs,
    )
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-preflight.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(report, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu captured boot preflight {error.path}: {error.message}")
        return 1
    qemu_captured_boot_preflight.write_preflight(report, args.out)
    print(args.out)
    return 0 if report["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
