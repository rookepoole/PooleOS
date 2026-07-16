#!/usr/bin/env python3
"""Emit an operator-facing QEMU captured boot launch bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_captured_boot_launch_bundle  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a QEMU captured boot launch bundle.")
    parser.add_argument("--preflight", type=Path, default=ROOT / "runs" / "qemu_captured_boot_preflight.json")
    parser.add_argument("--qemu-shared-folder-contract", type=Path, default=ROOT / "runs" / "qemu_shared_folder_contract.json")
    parser.add_argument("--qemu-captured-boot-receipt", type=Path, default=ROOT / "runs" / "qemu_captured_boot_receipt.json")
    parser.add_argument("--fixture-evidence", type=Path, default=ROOT / "runs" / "qemu_boot_evidence.json")
    parser.add_argument("--release-gate-output", default="")
    parser.add_argument("--launcher-script", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_captured_boot_launch_bundle.json")
    args = parser.parse_args(argv)

    bundle = qemu_captured_boot_launch_bundle.make_qemu_captured_boot_launch_bundle(
        root=ROOT,
        preflight_path=args.preflight,
        qemu_shared_folder_contract_path=args.qemu_shared_folder_contract,
        qemu_captured_boot_receipt_path=args.qemu_captured_boot_receipt,
        fixture_evidence_path=args.fixture_evidence,
        launch_bundle_output_path=args.out,
        release_gate_output_path=optional_path(args.release_gate_output),
        launcher_script=optional_path(args.launcher_script),
    )
    schema = json.loads((ROOT / "specs" / "qemu-captured-boot-launch-bundle.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(bundle, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu captured boot launch bundle {error.path}: {error.message}")
        return 1
    qemu_captured_boot_launch_bundle.write_bundle(bundle, args.out)
    print(args.out)
    return 0 if bundle["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
