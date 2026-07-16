"""Preflight checks for captured QEMU boot evidence launch."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_captured_boot_preflight"


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    required: bool
    ok: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "ok": self.ok,
            "detail": self.detail,
        }


def _path_string(path: Path | None) -> str:
    return str(path) if path else ""


def _parent_exists(path: Path) -> bool:
    return path.parent.exists() and path.parent.is_dir()


def _same_path(left: Path | None, right: Path | None) -> bool:
    if left is None or right is None:
        return False
    return left.resolve() == right.resolve()


def _check_path(name: str, path: Path, *, required: bool, expects_file: bool | None = None) -> PreflightCheck:
    exists = path.exists()
    ok = exists
    if exists and expects_file is True:
        ok = path.is_file()
    elif exists and expects_file is False:
        ok = path.is_dir()
    return PreflightCheck(name, required, ok, str(path) if ok else f"missing {path}")


def _check_parent(name: str, path: Path, *, required: bool) -> PreflightCheck:
    ok = _parent_exists(path)
    return PreflightCheck(name, required, ok, str(path.parent) if ok else f"missing parent {path.parent}")


def _check_command(command: str) -> tuple[PreflightCheck, str]:
    found = shutil.which(command)
    return (
        PreflightCheck(
            "qemu_command_found",
            True,
            bool(found),
            found or f"{command} not found on PATH",
        ),
        found or "",
    )


def default_image_path(root: Path) -> Path:
    return root / "output" / "images" / "rootfs.ext4"


def default_shared_output_path(root: Path) -> Path:
    return root / "runs" / "qemu_shared"


def default_serial_log_path(root: Path) -> Path:
    return root / "runs" / "pooleos-lab-serial.log"


def default_boot_validation_output(root: Path) -> Path:
    return root / "runs" / "boot_log_validation.captured.json"


def default_qemu_boot_evidence_output(root: Path) -> Path:
    return root / "runs" / "qemu_boot_evidence.captured.json"


def default_qemu_captured_boot_receipt_output(root: Path) -> Path:
    return root / "runs" / "qemu_captured_boot_receipt.json"


def make_qemu_captured_boot_preflight(
    *,
    root: Path,
    image_path: Path | None = None,
    kernel_path: Path | None = None,
    serial_log_path: Path | None = None,
    shared_output_path: Path | None = None,
    boot_validation_output: Path | None = None,
    qemu_boot_evidence_output: Path | None = None,
    qemu_captured_boot_receipt_output: Path | None = None,
    qemu_command: str = "qemu-system-x86_64",
    require_kernel: bool = False,
    no_virtfs: bool = False,
) -> dict[str, Any]:
    image = image_path or default_image_path(root)
    shared = shared_output_path or default_shared_output_path(root)
    serial_log = serial_log_path or default_serial_log_path(root)
    boot_validation = boot_validation_output or default_boot_validation_output(root)
    boot_evidence = qemu_boot_evidence_output or default_qemu_boot_evidence_output(root)
    captured_receipt = qemu_captured_boot_receipt_output or default_qemu_captured_boot_receipt_output(root)
    qemu_check, qemu_found_path = _check_command(qemu_command)

    checks = [
        PreflightCheck("execution_not_performed", True, True, "preflight is non-mutating"),
        _check_path("pooleos_root", root, required=True, expects_file=False),
        _check_path("qemu_launch_script", root / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1", required=True, expects_file=True),
        qemu_check,
        _check_path("image_path_exists", image, required=True, expects_file=True),
        _check_path("shared_output_path_exists", shared, required=not no_virtfs, expects_file=False),
        _check_parent("serial_log_parent_exists", serial_log, required=True),
        _check_parent("boot_validation_output_parent_exists", boot_validation, required=True),
        _check_parent("qemu_boot_evidence_output_parent_exists", boot_evidence, required=True),
        _check_parent("qemu_captured_boot_receipt_output_parent_exists", captured_receipt, required=True),
        PreflightCheck("boot_validation_and_evidence_paths_separate", True, not _same_path(boot_validation, boot_evidence), f"{boot_validation} != {boot_evidence}"),
        PreflightCheck("captured_receipt_separate_from_evidence", True, not _same_path(captured_receipt, boot_evidence), f"{captured_receipt} != {boot_evidence}"),
    ]
    if kernel_path is not None:
        checks.append(_check_path("kernel_path_exists", kernel_path, required=require_kernel, expects_file=True))
    else:
        checks.append(PreflightCheck("kernel_path_optional", False, not require_kernel, "no kernel path supplied"))

    safety_check_names = {
        "execution_not_performed",
        "boot_validation_and_evidence_paths_separate",
        "captured_receipt_separate_from_evidence",
    }
    safety_failures = [check for check in checks if check.name in safety_check_names and not check.ok]
    blocking_checks = [check for check in checks if check.required and not check.ok and check.name not in safety_check_names]
    warning_checks = [check for check in checks if not check.required and not check.ok]
    launch_ready = not safety_failures and not blocking_checks
    status = "fail" if safety_failures else "blocked" if blocking_checks else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "launch_ready": launch_ready,
        "execution_performed": False,
        "qemu": {
            "command": qemu_command,
            "found_path": qemu_found_path,
            "no_virtfs": bool(no_virtfs),
            "shared_mount_tag": "pooleos_output",
        },
        "paths": {
            "image_path": str(image),
            "kernel_path": _path_string(kernel_path),
            "serial_log_path": str(serial_log),
            "shared_output_path": str(shared),
            "boot_validation_output": str(boot_validation),
            "qemu_boot_evidence_output": str(boot_evidence),
            "qemu_captured_boot_receipt_output": str(captured_receipt),
        },
        "checks": [check.to_json() for check in checks],
        "summary": {
            "safety_failure_count": len(safety_failures),
            "blocking_check_count": len(blocking_checks),
            "warning_check_count": len(warning_checks),
            "image_exists": image.is_file(),
            "kernel_required": bool(require_kernel),
            "kernel_exists": bool(kernel_path and kernel_path.is_file()),
            "shared_output_exists": shared.is_dir(),
            "serial_log_parent_exists": _parent_exists(serial_log),
            "captured_outputs_separate": not _same_path(boot_validation, boot_evidence) and not _same_path(captured_receipt, boot_evidence),
        },
        "limitations": [
            "This preflight does not launch QEMU, build an image, create directories, or claim boot evidence.",
            "A blocked status is expected until the image, QEMU command, and shared folder are available.",
            "Captured boot evidence is still proven only by qemu_boot_evidence.captured.json after a real serial log is validated.",
        ],
        "next_steps": [
            "Build the Lab image or point --image at an existing rootfs image.",
            "Prepare the QEMU shared folder with pooleos_qemu_prepare_inputs.py.",
            "Run run-pooleos-lab.ps1 with BootValidationOutput and QemuBootEvidenceOutput paths after this preflight passes.",
        ],
    }


def write_preflight(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
