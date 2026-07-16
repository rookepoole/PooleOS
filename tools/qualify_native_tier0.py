#!/usr/bin/env python3
"""Qualify the exact workspace-local native Tier 0 QEMU/OVMF candidate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_tier0  # noqa: E402


DEFAULT_ANDROID_QEMU = (
    ROOT.parent.parent.parent.parent
    / "android_toolchain"
    / "android-sdk"
    / "emulator"
    / "qemu"
    / "windows-x86_64"
    / "qemu-system-x86_64.exe"
)
DEFAULT_DEVELOPMENT_QEMU = ROOT / ".toolchains" / "qemu-w64-20260501-extracted" / "qemu-system-x86_64.exe"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu-root", type=Path, default=native_tier0.DEFAULT_QEMU_ROOT)
    parser.add_argument("--installer", type=Path, default=native_tier0.DEFAULT_INSTALLER)
    parser.add_argument("--android-qemu", type=Path, default=DEFAULT_ANDROID_QEMU)
    parser.add_argument("--development-qemu", type=Path, default=DEFAULT_DEVELOPMENT_QEMU)
    parser.add_argument("--out", type=Path, default=ROOT / native_tier0.READINESS_RELATIVE)
    args = parser.parse_args(argv)
    negative_candidates = (
        ("android_qemu", args.android_qemu),
        ("development_qemu", args.development_qemu),
    )
    try:
        readiness = native_tier0.build_readiness(
            args.qemu_root,
            args.installer,
            negative_candidates=negative_candidates,
        )
    except (OSError, ValueError, KeyError, native_tier0.Tier0Error) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 2
    native_tier0.write_json(readiness, args.out)
    summary = readiness["summary"]
    print(
        f"wrote {args.out}: profiles={summary['profile_pass_count']}/{summary['profile_count']} "
        f"machine_probes={summary['machine_probe_pass_count']}/{summary['machine_probe_count']} "
        f"negatives={summary['negative_control_pass_count']}/{summary['negative_control_count']} "
        "boot_claims=0 n4_exit=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
