"""PooleOS Lab scaffold readiness checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def required_lab_paths(root: Path) -> list[Path]:
    return [
        root / "docs" / "lab-os-decision.md",
        root / "docs" / "boot-readiness-checklist.md",
        root / "lab-os" / "README.md",
        root / "lab-os" / "buildroot" / "external" / "external.desc",
        root / "lab-os" / "buildroot" / "external" / "Config.in",
        root / "lab-os" / "buildroot" / "external" / "external.mk",
        root / "lab-os" / "buildroot" / "external" / "configs" / "pooleos_lab_x86_64_defconfig",
        root / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "post-build.sh",
        root / "lab-os" / "buildroot" / "scripts" / "run-build.ps1",
        root / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1",
    ]


def lab_scaffold_status(root: Path) -> dict[str, Any]:
    required = required_lab_paths(root)
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]

    defconfig = root / "lab-os" / "buildroot" / "external" / "configs" / "pooleos_lab_x86_64_defconfig"
    defconfig_text = defconfig.read_text(encoding="utf-8") if defconfig.exists() else ""
    qemu_script = root / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1"
    qemu_text = qemu_script.read_text(encoding="utf-8") if qemu_script.exists() else ""
    build_script = root / "lab-os" / "buildroot" / "scripts" / "run-build.ps1"
    build_text = build_script.read_text(encoding="utf-8") if build_script.exists() else ""

    semantic_failures: list[str] = []
    if "BR2_PACKAGE_PYTHON3=y" not in defconfig_text:
        semantic_failures.append("defconfig missing Python 3")
    if "BR2_ROOTFS_OVERLAY" not in defconfig_text:
        semantic_failures.append("defconfig missing rootfs overlay")
    if "ttyS0" not in defconfig_text:
        semantic_failures.append("defconfig missing serial console getty")
    if "BuildrootPath does not exist" not in build_text:
        semantic_failures.append("build script missing guarded Buildroot failure")
    if "ImagePath does not exist" not in qemu_text:
        semantic_failures.append("QEMU script missing guarded image failure")

    return {
        "ok": not missing and not semantic_failures,
        "missing": missing,
        "semantic_failures": semantic_failures,
        "boot_image_built": False,
        "boot_image_reason": "Scaffold exists, but no Buildroot image has been built or booted yet.",
    }

