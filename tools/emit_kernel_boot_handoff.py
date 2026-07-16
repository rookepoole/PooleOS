#!/usr/bin/env python3
"""Emit a kernel-owned boot handoff boundary artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kernel_boot_handoff  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a kernel-owned boot handoff boundary artifact.")
    parser.add_argument("--qemu-captured-boot-readiness", type=Path, default=ROOT / "runs" / "qemu_captured_boot_readiness.json")
    parser.add_argument("--qemu-boot-marker-contract", type=Path, default=ROOT / "runs" / "qemu_boot_marker_contract.json")
    parser.add_argument("--boot-trap-bundle-manifest", type=Path, default=ROOT / "runs" / "pooleos_boot_trap_bundle_manifest.json")
    parser.add_argument("--guest-loader-verification", type=Path, default=ROOT / "runs" / "boot_trap_bundle_verification.json")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "kernel_boot_handoff.json")
    args = parser.parse_args(argv)

    handoff = kernel_boot_handoff.make_kernel_boot_handoff(
        qemu_captured_boot_readiness_path=args.qemu_captured_boot_readiness,
        qemu_boot_marker_contract_path=args.qemu_boot_marker_contract,
        boot_trap_bundle_manifest_path=args.boot_trap_bundle_manifest,
        guest_loader_verification_path=args.guest_loader_verification,
    )
    schema = json.loads((ROOT / "specs" / "kernel-boot-handoff.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(handoff, schema)
    if errors:
        for error in errors:
            print(f"FAIL kernel boot handoff {error.path}: {error.message}")
        return 1
    kernel_boot_handoff.write_handoff(handoff, args.out)
    print(args.out)
    return 0 if handoff["status"] in {"blocked", "ready_for_kernel_handoff"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
