"""PooleOS Lab image manifest helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.lab_image_manifest"


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_buildroot_version(buildroot_path: Path | None) -> str:
    if buildroot_path is None:
        return ""
    makefile = buildroot_path / "Makefile"
    if not makefile.exists():
        return ""
    text = makefile.read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"^(?:export\s+)?BR2_VERSION\s*[:?]?=\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _read_boot_ok(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("ok") is True
    except Exception:
        return False


def _read_release_status(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("status", ""))
    except Exception:
        return ""


def _read_buildroot_probe(path: Path | None) -> tuple[bool, str]:
    if path is None or not path.exists():
        return False, ""
    try:
        status = str(json.loads(path.read_text(encoding="utf-8-sig")).get("status", ""))
    except Exception:
        return False, ""
    return status == "pass", status


def _read_status(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8-sig")).get("status", ""))
    except Exception:
        return ""


def _read_wsl_missing_package_count(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return 0
    missing = data.get("missing_packages", [])
    return len(missing) if isinstance(missing, list) else 0


def _read_build_rootfs_path(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    rootfs = data.get("rootfs_image", {}) if isinstance(data.get("rootfs_image"), dict) else {}
    return str(rootfs.get("path", ""))


def make_lab_manifest(
    *,
    root: Path,
    buildroot_path: Path | None = None,
    image_path: Path | None = None,
    kernel_path: Path | None = None,
    serial_log_path: Path | None = None,
    boot_log_validation_path: Path | None = None,
    release_gate_path: Path | None = None,
    buildroot_probe_path: Path | None = None,
    buildroot_configure_path: Path | None = None,
    buildroot_build_path: Path | None = None,
    wsl_prerequisites_path: Path | None = None,
    qemu_command: str = "",
) -> dict[str, Any]:
    external_tree = root / "lab-os" / "buildroot" / "external"
    defconfig = external_tree / "configs" / "pooleos_lab_x86_64_defconfig"
    boot_ok = _read_boot_ok(boot_log_validation_path)
    probe_ok, probe_status = _read_buildroot_probe(buildroot_probe_path)
    configure_status = _read_status(buildroot_configure_path)
    build_status = _read_status(buildroot_build_path)
    build_rootfs_path = _read_build_rootfs_path(buildroot_build_path)
    wsl_prerequisites_status = _read_status(wsl_prerequisites_path)
    image_exists = image_path is not None and image_path.exists()
    status = "boot_validated" if image_exists and boot_ok else "built" if image_exists else "scaffold"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "buildroot": {
            "external_tree_path": str(external_tree),
            "defconfig_path": str(defconfig),
            "defconfig_sha256": file_sha256(defconfig),
            "buildroot_path": str(buildroot_path or ""),
            "buildroot_version": read_buildroot_version(buildroot_path),
        },
        "qemu": {
            "command": qemu_command,
            "image_path": str(image_path or ""),
            "kernel_path": str(kernel_path or ""),
            "serial_log_path": str(serial_log_path or ""),
        },
        "validations": {
            "boot_log_validation_path": str(boot_log_validation_path or ""),
            "boot_log_ok": boot_ok,
            "release_gate_path": str(release_gate_path or ""),
            "release_gate_status": _read_release_status(release_gate_path),
            "buildroot_probe_path": str(buildroot_probe_path or ""),
            "buildroot_probe_ok": probe_ok,
            "buildroot_probe_status": probe_status,
            "buildroot_configure_path": str(buildroot_configure_path or ""),
            "buildroot_configure_ok": configure_status == "pass",
            "buildroot_configure_status": configure_status,
            "buildroot_build_path": str(buildroot_build_path or ""),
            "buildroot_build_ok": build_status == "pass",
            "buildroot_build_status": build_status,
            "buildroot_build_rootfs_image_path": build_rootfs_path,
            "wsl_prerequisites_path": str(wsl_prerequisites_path or ""),
            "wsl_prerequisites_status": wsl_prerequisites_status,
            "wsl_missing_package_count": _read_wsl_missing_package_count(wsl_prerequisites_path),
        },
    }


def write_lab_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
