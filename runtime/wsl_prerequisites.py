"""WSL prerequisite reports for PooleOS Lab Buildroot work."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime import host_preflight
from runtime import lab_manifest


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.wsl_prerequisites"


@dataclass(frozen=True)
class ToolRequirement:
    name: str
    command: str
    package: str
    role: str
    required: bool = True


BUILDROOT_MANDATORY_TOOLS = [
    ToolRequirement("which", "which", "debianutils", "buildroot_mandatory"),
    ToolRequirement("sed", "sed", "sed", "buildroot_mandatory"),
    ToolRequirement("make", "make", "make", "buildroot_mandatory"),
    ToolRequirement("binutils", "ld", "binutils", "buildroot_mandatory"),
    ToolRequirement("build_essential", "gcc", "build-essential", "buildroot_mandatory"),
    ToolRequirement("diffutils", "diff", "diffutils", "buildroot_mandatory"),
    ToolRequirement("gcc", "gcc", "gcc", "buildroot_mandatory"),
    ToolRequirement("gpp", "g++", "g++", "buildroot_mandatory"),
    ToolRequirement("bash", "bash", "bash", "buildroot_mandatory"),
    ToolRequirement("patch", "patch", "patch", "buildroot_mandatory"),
    ToolRequirement("gzip", "gzip", "gzip", "buildroot_mandatory"),
    ToolRequirement("bzip2", "bzip2", "bzip2", "buildroot_mandatory"),
    ToolRequirement("perl", "perl", "perl", "buildroot_mandatory"),
    ToolRequirement("tar", "tar", "tar", "buildroot_mandatory"),
    ToolRequirement("cpio", "cpio", "cpio", "buildroot_mandatory"),
    ToolRequirement("unzip", "unzip", "unzip", "buildroot_mandatory"),
    ToolRequirement("rsync", "rsync", "rsync", "buildroot_mandatory"),
    ToolRequirement("file", "file", "file", "buildroot_mandatory"),
    ToolRequirement("bc", "bc", "bc", "buildroot_mandatory"),
    ToolRequirement("findutils", "find", "findutils", "buildroot_mandatory"),
    ToolRequirement("awk", "awk", "gawk", "buildroot_mandatory"),
    ToolRequirement("wget", "wget", "wget", "buildroot_mandatory"),
]

POOLEOS_BOOT_EXTRA_TOOLS = [
    ToolRequirement("qemu", "qemu-system-x86_64", "qemu-system-x86", "pooleos_boot_extra"),
]


def _git_commit(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except Exception:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _check_tool(distro: str, requirement: ToolRequirement) -> dict[str, Any]:
    quoted = shlex.quote(requirement.command)
    script = (
        f"command -v {quoted} 2>/dev/null || {{ echo 'not found'; exit 127; }}; "
        f"{quoted} --version 2>&1 | head -n 1 || true"
    )
    completed = host_preflight._run_wsl_shell(distro=distro, script=script)
    if completed is None:
        ok = False
        detail = "wsl.exe not found on PATH"
    else:
        ok = completed.returncode == 0
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        detail = "; ".join(lines[:2]) if lines else "no output"
    return {
        "name": requirement.name,
        "role": requirement.role,
        "command": requirement.command,
        "package": requirement.package,
        "required": requirement.required,
        "ok": ok,
        "detail": detail,
    }


def make_prerequisite_report(
    *,
    distro: str,
    buildroot_path: Path | None = None,
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    requirements = BUILDROOT_MANDATORY_TOOLS + POOLEOS_BOOT_EXTRA_TOOLS
    live_checks = checks if checks is not None else [_check_tool(distro, requirement) for requirement in requirements]
    wsl_available = host_preflight.wsl_available_check(distro).ok if checks is None else True
    missing = [check for check in live_checks if check["required"] and not check["ok"]]
    missing_packages = sorted({check["package"] for check in missing if check["package"]})
    package_manager_check = _check_tool(distro, ToolRequirement("apt_get", "apt-get", "apt", "package_manager", False))
    package_manager = "apt-get" if package_manager_check["ok"] else ""
    install_command = ""
    if package_manager and missing_packages:
        install_command = "sudo apt-get update && sudo apt-get install -y " + " ".join(missing_packages)
    if not wsl_available:
        status = "fail"
    elif missing:
        status = "blocked"
    else:
        status = "pass"

    manual_path = buildroot_path / "docs" / "manual" / "prerequisite.adoc" if buildroot_path else Path("")
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "distro": distro,
        "source_basis": {
            "buildroot_version": lab_manifest.read_buildroot_version(buildroot_path),
            "buildroot_git_commit": _git_commit(buildroot_path),
            "buildroot_manual_path": str(manual_path),
        },
        "execution_performed": False,
        "host_modification_required": bool(missing_packages),
        "package_manager": package_manager,
        "install_command": install_command,
        "missing_packages": missing_packages,
        "checks": live_checks,
        "notes": [
            "This report is non-mutating; no package install command was executed.",
            "Buildroot mandatory tools are sourced from docs/manual/prerequisite.adoc in the pinned Buildroot tree.",
            "qemu-system-x86_64 is PooleOS Lab boot-validation tooling, not a Buildroot mandatory package.",
        ],
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
