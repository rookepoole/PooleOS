#!/usr/bin/env python3
"""Emit PooleOS QEMU serial boot evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_boot_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit PooleOS QEMU serial boot evidence.")
    parser.add_argument("--log", default="", help="Serial log path. Defaults to the trap-input fixture.")
    parser.add_argument("--boot-validation", default="", help="Optional precomputed boot-log validation artifact.")
    parser.add_argument("--profile", choices=["base", "trap-input"], default="trap-input")
    parser.add_argument("--source", choices=sorted(qemu_boot_evidence.EVIDENCE_SOURCES), default=qemu_boot_evidence.FIXTURE_SOURCE)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_boot_evidence.json")
    args = parser.parse_args(argv)

    evidence = qemu_boot_evidence.make_qemu_boot_evidence(
        root=ROOT,
        log_path=optional_path(args.log),
        boot_log_validation_path=optional_path(args.boot_validation),
        evidence_source=args.source,
        profile=args.profile,
    )
    schema = json.loads((ROOT / "specs" / "qemu-boot-evidence.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(evidence, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu boot evidence {error.path}: {error.message}")
        return 1
    qemu_boot_evidence.write_evidence(evidence, args.out)
    if evidence["status"] != "pass":
        failed = [check["name"] for check in evidence["checks"] if not check["ok"]]
        print(f"FAIL qemu boot evidence checks: {', '.join(failed)}")
        return 1
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
