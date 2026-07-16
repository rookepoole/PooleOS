#!/usr/bin/env python3
"""Emit a PGB2 trap ABI boundary receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pgb2_trap_abi_boundary_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a non-promoting ABI boundary receipt for draft PGB2 trap bytes.")
    parser.add_argument("--trap-encoding", type=Path, required=True)
    parser.add_argument("--trap-execution", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--boot-trap-bundle-manifest", type=Path, required=True)
    parser.add_argument("--qemu-shared-folder-contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pgb2_trap_abi_boundary_receipt.json")
    args = parser.parse_args(argv)

    receipt = pgb2_trap_abi_boundary_receipt.make_pgb2_trap_abi_boundary_receipt(
        trap_encoding_path=args.trap_encoding,
        trap_execution_path=args.trap_execution,
        bundle_path=args.bundle,
        boot_trap_bundle_manifest_path=args.boot_trap_bundle_manifest,
        qemu_shared_folder_contract_path=args.qemu_shared_folder_contract,
        specs_dir=ROOT / "specs",
    )
    schema = json.loads((ROOT / "specs" / "pgb2-trap-abi-boundary-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors:
            print(f"FAIL pgb2_trap_abi_boundary_receipt {error.path}: {error.message}")
        return 1
    pgb2_trap_abi_boundary_receipt.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt["status"] == "draft_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
