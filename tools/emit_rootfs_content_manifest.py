#!/usr/bin/env python3
"""Emit a PooleOS rootfs content manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import rootfs_content_manifest  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS rootfs content manifest.")
    parser.add_argument("--image-binding", type=Path, default=ROOT / "runs" / "qemu_boot_marker_image_binding.json")
    parser.add_argument("--image", type=Path, default=ROOT / "output" / "images" / "rootfs.ext4")
    parser.add_argument("--extracted-rootfs", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "rootfs_content_manifest.json")
    args = parser.parse_args(argv)

    manifest = rootfs_content_manifest.make_rootfs_content_manifest(
        root=ROOT,
        image_binding_path=args.image_binding,
        image_path=args.image,
        extracted_rootfs_path=optional_path(args.extracted_rootfs),
    )
    schema = json.loads((ROOT / "specs" / "rootfs-content-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL rootfs content manifest {error.path}: {error.message}")
        return 1
    rootfs_content_manifest.write_manifest(manifest, args.out)
    print(args.out)
    return 0 if manifest["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
