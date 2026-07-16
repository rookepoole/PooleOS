#!/usr/bin/env python3
"""Verify mounted PooleOS Lab input bundle files against a boot manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_trap_bundle_manifest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify mounted PooleOS Lab trap-bundle inputs.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR) / boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME,
    )
    parser.add_argument("--out", type=Path, default=Path(boot_trap_bundle_manifest.DEFAULT_RESULT_PATH))
    args = parser.parse_args(argv)

    result = boot_trap_bundle_manifest.verify_mounted_manifest(args.manifest)
    boot_trap_bundle_manifest.write_verification(result, args.out)
    print(args.out)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
