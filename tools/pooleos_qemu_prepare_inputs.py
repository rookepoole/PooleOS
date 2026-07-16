#!/usr/bin/env python3
"""Stage PooleOS Lab QEMU shared-folder inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_shared_folder_contract  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare PooleOS Lab QEMU shared-folder inputs.")
    parser.add_argument("--shared-dir", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--replay-proof", type=Path, required=True)
    parser.add_argument("--boot-trap-bundle-manifest", type=Path, required=True)
    parser.add_argument("--pgb2-trap-abi-boundary-receipt", type=Path)
    parser.add_argument("--mount-tag", default=qemu_shared_folder_contract.DEFAULT_MOUNT_TAG)
    parser.add_argument("--no-copy", action="store_true", help="Validate only; do not copy files.")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "qemu_shared_folder_contract.json")
    args = parser.parse_args(argv)

    contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
        shared_dir=args.shared_dir,
        bundle_path=args.bundle,
        replay_proof_path=args.replay_proof,
        boot_trap_manifest_path=args.boot_trap_bundle_manifest,
        specs_dir=ROOT / "specs",
        trap_abi_boundary_receipt_path=args.pgb2_trap_abi_boundary_receipt,
        mount_tag=args.mount_tag,
        perform_copy=not args.no_copy,
    )
    schema = json.loads((ROOT / "specs" / "qemu-shared-folder-contract.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(contract, schema)
    if errors:
        for error in errors:
            print(f"FAIL qemu_shared_folder_contract {error.path}: {error.message}")
        return 1
    qemu_shared_folder_contract.write_contract(contract, args.out)
    print(args.out)
    return 0 if contract["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
