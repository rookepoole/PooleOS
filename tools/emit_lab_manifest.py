#!/usr/bin/env python3
"""Emit a PooleOS Lab image manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import lab_manifest  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS Lab image manifest.")
    parser.add_argument("--buildroot-path", default="")
    parser.add_argument("--image", default="")
    parser.add_argument("--kernel", default="")
    parser.add_argument("--serial-log", default="")
    parser.add_argument("--boot-validation", default="")
    parser.add_argument("--release-gate", default="")
    parser.add_argument("--buildroot-probe", default="")
    parser.add_argument("--buildroot-configure", default="")
    parser.add_argument("--buildroot-build", default="")
    parser.add_argument("--wsl-prerequisites", default="")
    parser.add_argument("--qemu-command", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "lab_image_manifest.json")
    args = parser.parse_args(argv)

    manifest = lab_manifest.make_lab_manifest(
        root=ROOT,
        buildroot_path=optional_path(args.buildroot_path),
        image_path=optional_path(args.image),
        kernel_path=optional_path(args.kernel),
        serial_log_path=optional_path(args.serial_log),
        boot_log_validation_path=optional_path(args.boot_validation),
        release_gate_path=optional_path(args.release_gate),
        buildroot_probe_path=optional_path(args.buildroot_probe),
        buildroot_configure_path=optional_path(args.buildroot_configure),
        buildroot_build_path=optional_path(args.buildroot_build),
        wsl_prerequisites_path=optional_path(args.wsl_prerequisites),
        qemu_command=args.qemu_command,
    )
    schema = json.loads((ROOT / "specs" / "lab-image-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL manifest {error.path}: {error.message}")
        return 1
    lab_manifest.write_lab_manifest(manifest, args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
