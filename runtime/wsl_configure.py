"""WSL Buildroot configure runner for PooleOS Lab."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable

from runtime import host_preflight
from runtime import lab_manifest


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.buildroot_configure"
DEFCONFIG_NAME = "pooleos_lab_x86_64_defconfig"


CompletedRunner = Callable[[list[str], int], subprocess.CompletedProcess[str]]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _text_tail(text: str, *, lines: int = 40) -> str:
    if not text:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def _base_checks(*, buildroot_path: Path, external_path: Path, prerequisites: dict[str, Any]) -> list[dict[str, Any]]:
    makefile = buildroot_path / "Makefile"
    defconfig = external_path / "configs" / DEFCONFIG_NAME
    return [
        _check("buildroot_path", buildroot_path.exists() and buildroot_path.is_dir(), str(buildroot_path)),
        _check("buildroot_makefile", makefile.exists() and makefile.is_file(), str(makefile)),
        _check("buildroot_version", lab_manifest.read_buildroot_version(buildroot_path) != "", lab_manifest.read_buildroot_version(buildroot_path)),
        _check("external_tree", external_path.exists() and external_path.is_dir(), str(external_path)),
        _check("pooleos_defconfig", defconfig.exists() and defconfig.is_file(), str(defconfig)),
        _check(
            "wsl_prerequisites",
            prerequisites.get("status") == "pass",
            f"status={prerequisites.get('status')}; missing_packages={len(prerequisites.get('missing_packages', []))}",
        ),
    ]


def _wsl_configure_command(
    *,
    distro: str,
    buildroot_path: Path,
    external_path: Path,
    output_dir: Path | None,
) -> list[str]:
    wsl = host_preflight._wsl_executable() or "wsl.exe"
    buildroot_wsl = host_preflight.windows_path_to_wsl(buildroot_path)
    external_wsl = host_preflight.windows_path_to_wsl(external_path)
    script_parts = [
        f"BR2_EXTERNAL={shlex.quote(external_wsl)}",
        "make",
        "-C",
        shlex.quote(buildroot_wsl),
    ]
    if output_dir is not None:
        script_parts.append("O=" + shlex.quote(host_preflight.windows_path_to_wsl(output_dir)))
    script_parts.append(DEFCONFIG_NAME)
    script = " ".join(script_parts)
    return [wsl, "-d", distro, "--", "bash", "-lc", script]


def _default_runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )


def make_configure_report(
    *,
    buildroot_path: Path,
    external_path: Path,
    prerequisites_path: Path,
    distro: str = "Ubuntu",
    output_dir: Path | None = None,
    timeout_seconds: int = 600,
    runner: CompletedRunner | None = None,
) -> dict[str, Any]:
    prerequisites = _read_json(prerequisites_path)
    checks = _base_checks(buildroot_path=buildroot_path, external_path=external_path, prerequisites=prerequisites)
    command = _wsl_configure_command(
        distro=distro,
        buildroot_path=buildroot_path,
        external_path=external_path,
        output_dir=output_dir,
    )
    failed_checks = [check for check in checks if not check["ok"]]
    prereq_status = prerequisites.get("status")
    if failed_checks or prereq_status != "pass":
        missing = ", ".join(prerequisites.get("missing_packages", []))
        reason = f"WSL prerequisites status={prereq_status}; missing_packages={missing or 'none'}"
        if failed_checks:
            reason += "; failed_checks=" + ", ".join(check["name"] for check in failed_checks)
        return {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": ARTIFACT_KIND,
            "status": "blocked",
            "buildroot_path": str(buildroot_path),
            "external_path": str(external_path),
            "defconfig_name": DEFCONFIG_NAME,
            "output_dir": str(output_dir or ""),
            "command": command,
            "exit_code": -1,
            "stdout_tail": reason,
            "checks": checks,
        }

    active_runner = runner or _default_runner
    try:
        completed = active_runner(command, timeout_seconds)
        output = completed.stdout or ""
        exit_code = int(completed.returncode)
    except Exception as exc:
        output = str(exc)
        exit_code = 1
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if exit_code == 0 else "fail",
        "buildroot_path": str(buildroot_path),
        "external_path": str(external_path),
        "defconfig_name": DEFCONFIG_NAME,
        "output_dir": str(output_dir or ""),
        "command": command,
        "exit_code": exit_code,
        "stdout_tail": _text_tail(output),
        "checks": checks,
    }


def write_configure_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
