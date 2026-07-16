"""Host preflight checks for PooleOS Lab builds."""

from __future__ import annotations

import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.host_preflight"


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


def command_check(name: str, command: str, *, required: bool) -> PreflightCheck:
    found = shutil.which(command)
    if not found:
        return PreflightCheck(name, required, False, f"{command} not found on PATH")
    try:
        completed = subprocess.run(
            [found, "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
        first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else found
    except Exception:
        first_line = found
    return PreflightCheck(name, required, True, first_line)


def path_check(name: str, path: Path, *, required: bool, expects_file: bool | None = None) -> PreflightCheck:
    exists = path.exists()
    ok = exists
    if exists and expects_file is True:
        ok = path.is_file()
    elif exists and expects_file is False:
        ok = path.is_dir()
    return PreflightCheck(name, required, ok, str(path) if ok else f"missing {path}")


def _wsl_executable() -> str | None:
    return shutil.which("wsl.exe") or shutil.which("wsl")


def _run_wsl_shell(*, distro: str, script: str) -> subprocess.CompletedProcess[str] | None:
    wsl = _wsl_executable()
    if not wsl:
        return None
    cmd = [wsl]
    if distro:
        cmd.extend(["-d", distro])
    cmd.extend(["--", "bash", "-lc", script])
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 1, stdout=str(exc))


def wsl_available_check(distro: str) -> PreflightCheck:
    completed = _run_wsl_shell(distro=distro, script="printf ready")
    if completed is None:
        return PreflightCheck("wsl", False, False, "wsl.exe not found on PATH")
    ok = completed.returncode == 0
    detail = completed.stdout.strip() if completed.stdout else "ready"
    return PreflightCheck("wsl", False, ok, detail if ok else f"WSL unavailable: {detail}")


def wsl_command_check(name: str, command: str, *, distro: str) -> PreflightCheck:
    quoted = shlex.quote(command)
    script = (
        f"command -v {quoted} 2>/dev/null || {{ echo 'not found'; exit 127; }}; "
        f"{quoted} --version 2>&1 | head -n 1 || true"
    )
    completed = _run_wsl_shell(distro=distro, script=script)
    if completed is None:
        return PreflightCheck(name, False, False, "wsl.exe not found on PATH")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    detail = "; ".join(lines[:2]) if lines else "no output"
    return PreflightCheck(name, False, completed.returncode == 0, detail)


def windows_path_to_wsl(path: Path) -> str:
    windows_path = PureWindowsPath(str(path))
    drive = windows_path.drive.rstrip(":").lower()
    if not drive:
        return str(path).replace("\\", "/")
    parts = [part for part in windows_path.parts[1:] if part not in {"\\", "/"}]
    return f"/mnt/{drive}/" + "/".join(parts)


def wsl_path_check(name: str, path: Path, *, distro: str, expects_file: bool) -> PreflightCheck:
    wsl_path = windows_path_to_wsl(path)
    quoted = shlex.quote(wsl_path)
    test_flag = "-f" if expects_file else "-d"
    script = (
        f"if [ {test_flag} {quoted} ]; then echo {quoted}; exit 0; fi; "
        f"echo missing {quoted}; exit 1"
    )
    completed = _run_wsl_shell(distro=distro, script=script)
    if completed is None:
        return PreflightCheck(name, False, False, "wsl.exe not found on PATH")
    detail = completed.stdout.strip() if completed.stdout else str(path)
    return PreflightCheck(name, False, completed.returncode == 0, detail)


def build_preflight_report(
    *,
    root: Path,
    buildroot_path: Path | None = None,
    qemu_command: str = "qemu-system-x86_64",
    include_wsl: bool = False,
    wsl_distro: str = "Ubuntu",
) -> dict[str, Any]:
    checks = [
        PreflightCheck("python", True, True, sys.version.split()[0]),
        command_check("gnu_make", "make", required=False),
        command_check("qemu", qemu_command, required=False),
        path_check("pooleos_root", root, required=True, expects_file=False),
        path_check(
            "buildroot_external",
            root / "lab-os" / "buildroot" / "external",
            required=True,
            expects_file=False,
        ),
        path_check(
            "buildroot_defconfig",
            root / "lab-os" / "buildroot" / "external" / "configs" / "pooleos_lab_x86_64_defconfig",
            required=True,
            expects_file=True,
        ),
        path_check(
            "qemu_launch_script",
            root / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1",
            required=True,
            expects_file=True,
        ),
    ]
    if buildroot_path is not None:
        checks.append(path_check("buildroot_tree", buildroot_path, required=True, expects_file=False))
        checks.append(path_check("buildroot_makefile", buildroot_path / "Makefile", required=True, expects_file=True))
    if include_wsl:
        checks.append(wsl_available_check(wsl_distro))
        checks.append(wsl_command_check("wsl_python3", "python3", distro=wsl_distro))
        checks.append(wsl_command_check("wsl_gnu_make", "make", distro=wsl_distro))
        checks.append(wsl_command_check("wsl_qemu", qemu_command, distro=wsl_distro))
        if buildroot_path is not None:
            checks.append(wsl_path_check("wsl_buildroot_tree", buildroot_path, distro=wsl_distro, expects_file=False))
            checks.append(wsl_path_check("wsl_buildroot_makefile", buildroot_path / "Makefile", distro=wsl_distro, expects_file=True))

    failed_required = [check for check in checks if check.required and not check.ok]
    failed_optional = [check for check in checks if not check.required and not check.ok]
    status = "fail" if failed_required else "warn" if failed_optional else "pass"
    check_by_name = {check.name: check for check in checks}
    has_buildroot_tree = check_by_name.get("buildroot_tree", PreflightCheck("", False, False, "")).ok
    wsl_buildroot_ok = check_by_name.get("wsl_buildroot_makefile", PreflightCheck("", False, buildroot_path is None, "")).ok
    has_make = check_by_name["gnu_make"].ok or (
        check_by_name.get("wsl_gnu_make", PreflightCheck("", False, False, "")).ok and wsl_buildroot_ok
    )
    has_qemu = check_by_name["qemu"].ok or check_by_name.get("wsl_qemu", PreflightCheck("", False, False, "")).ok
    if failed_required:
        readiness_stage = "blocked"
    elif has_buildroot_tree and has_make and has_qemu:
        readiness_stage = "build_ready"
    elif has_buildroot_tree and has_make:
        readiness_stage = "configure_ready"
    else:
        readiness_stage = "scaffold_ready"
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "readiness_stage": readiness_stage,
        "checks": [check.to_json() for check in checks],
    }
