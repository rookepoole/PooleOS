#!/usr/bin/env python3
"""Emit a PooleOS Lab boot trap-bundle loader manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_trap_bundle_manifest  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a boot-readiness manifest for a trap-bearing PGB2 bundle.")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--replay-proof", type=Path, required=True)
    parser.add_argument("--trap-execution", type=Path)
    parser.add_argument("--mount-dir", default=boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR)
    parser.add_argument("--bundle-target-path", default="")
    parser.add_argument("--replay-target-path", default="")
    parser.add_argument("--manifest-target-path", default="")
    parser.add_argument("--verification-result-path", default=boot_trap_bundle_manifest.DEFAULT_RESULT_PATH)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "boot_trap_bundle_manifest.json")
    args = parser.parse_args(argv)

    manifest = boot_trap_bundle_manifest.make_boot_trap_bundle_manifest(
        bundle_path=args.bundle,
        replay_proof_path=args.replay_proof,
        trap_execution_path=args.trap_execution,
        specs_dir=ROOT / "specs",
        mount_dir=args.mount_dir,
        bundle_target_path=args.bundle_target_path,
        replay_target_path=args.replay_target_path,
        manifest_target_path=args.manifest_target_path,
        verification_result_path=args.verification_result_path,
    )
    schema = json.loads((ROOT / "specs" / "boot-trap-bundle-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL boot_trap_bundle_manifest {error.path}: {error.message}")
        return 1
    boot_trap_bundle_manifest.write_manifest(manifest, args.out)
    print(args.out)
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
