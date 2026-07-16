"""WSL Buildroot image build runner for PooleOS Lab."""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable

from runtime import host_preflight
from runtime import lab_manifest
from runtime import wsl_configure


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.buildroot_build"


CompletedRunner = Callable[[list[str], int], subprocess.CompletedProcess[str]]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _text_tail(text: str, *, lines: int = 60) -> str:
    if not text:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rootfs_image_path(output_dir: Path) -> Path:
    return output_dir / "images" / "rootfs.ext4"


def _wsl_build_command(
    *,
    distro: str,
    buildroot_path: Path,
    external_path: Path,
    output_dir: Path,
) -> list[str]:
    wsl = host_preflight._wsl_executable() or "wsl.exe"
    buildroot_wsl = host_preflight.windows_path_to_wsl(buildroot_path)
    external_wsl = host_preflight.windows_path_to_wsl(external_path)
    output_wsl = host_preflight.windows_path_to_wsl(output_dir)
    script = " ".join(
        [
            f"BR2_EXTERNAL={shlex.quote(external_wsl)}",
            "make",
            "-C",
            shlex.quote(buildroot_wsl),
            "O=" + shlex.quote(output_wsl),
        ]
    )
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


def make_build_report(
    *,
    buildroot_path: Path,
    external_path: Path,
    configure_report_path: Path,
    distro: str = "Ubuntu",
    output_dir: Path,
    timeout_seconds: int = 7200,
    runner: CompletedRunner | None = None,
) -> dict[str, Any]:
    configure = _read_json(configure_report_path) if configure_report_path.exists() else {}
    configured_output = str(configure.get("output_dir", ""))
    rootfs_image = _rootfs_image_path(output_dir)
    command = _wsl_build_command(
        distro=distro,
        buildroot_path=buildroot_path,
        external_path=external_path,
        output_dir=output_dir,
    )
    checks = [
        _check("buildroot_path", buildroot_path.exists() and buildroot_path.is_dir(), str(buildroot_path)),
        _check("buildroot_makefile", (buildroot_path / "Makefile").exists(), str(buildroot_path / "Makefile")),
        _check("buildroot_version", lab_manifest.read_buildroot_version(buildroot_path) != "", lab_manifest.read_buildroot_version(buildroot_path)),
        _check("external_tree", external_path.exists() and external_path.is_dir(), str(external_path)),
        _check("pooleos_defconfig", (external_path / "configs" / wsl_configure.DEFCONFIG_NAME).exists(), str(external_path / "configs" / wsl_configure.DEFCONFIG_NAME)),
        _check("configure_report_present", configure_report_path.exists(), str(configure_report_path)),
        _check("configure_artifact_kind", configure.get("artifact_kind") == "pooleos.buildroot_configure", str(configure.get("artifact_kind", ""))),
        _check("configure_status_pass", configure.get("status") == "pass", f"status={configure.get('status', '')}"),
        _check(
            "configure_output_dir_matches",
            configured_output == str(output_dir),
            f"configure={configured_output}; build={output_dir}",
        ),
        _check("rootfs_image_path_planned", bool(str(rootfs_image)), str(rootfs_image)),
    ]
    failed_preconditions = [check for check in checks if not check["ok"]]
    if failed_preconditions:
        reason = "blocked until " + ", ".join(check["name"] for check in failed_preconditions)
        return _report(
            status="blocked",
            buildroot_path=buildroot_path,
            external_path=external_path,
            configure_report_path=configure_report_path,
            configure=configure,
            output_dir=output_dir,
            rootfs_image=rootfs_image,
            command=command,
            exit_code=-1,
            stdout_tail=reason,
            execution_performed=False,
            checks=checks,
        )

    active_runner = runner or _default_runner
    try:
        completed = active_runner(command, timeout_seconds)
        output = completed.stdout or ""
        exit_code = int(completed.returncode)
    except Exception as exc:
        output = str(exc)
        exit_code = 1

    image_exists = rootfs_image.exists() and rootfs_image.is_file()
    checks.append(_check("rootfs_image_exists_after_build", image_exists, str(rootfs_image)))
    checks.append(_check("rootfs_image_hashed_after_build", bool(_sha256(rootfs_image)), f"sha256={_sha256(rootfs_image)}"))
    failed_checks = [check for check in checks if not check["ok"]]
    status = "pass" if exit_code == 0 and image_exists and not failed_checks else "fail"
    return _report(
        status=status,
        buildroot_path=buildroot_path,
        external_path=external_path,
        configure_report_path=configure_report_path,
        configure=configure,
        output_dir=output_dir,
        rootfs_image=rootfs_image,
        command=command,
        exit_code=exit_code,
        stdout_tail=_text_tail(output),
        execution_performed=True,
        checks=checks,
    )


def _report(
    *,
    status: str,
    buildroot_path: Path,
    external_path: Path,
    configure_report_path: Path,
    configure: dict[str, Any],
    output_dir: Path,
    rootfs_image: Path,
    command: list[str],
    exit_code: int,
    stdout_tail: str,
    execution_performed: bool,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    failed_check_count = sum(1 for check in checks if not check["ok"])
    rootfs_exists = rootfs_image.exists() and rootfs_image.is_file()
    rootfs_sha = _sha256(rootfs_image)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "execution_performed": execution_performed,
        "buildroot_path": str(buildroot_path),
        "external_path": str(external_path),
        "output_dir": str(output_dir),
        "command": command,
        "exit_code": exit_code,
        "stdout_tail": stdout_tail,
        "source_configure": {
            "path": str(configure_report_path),
            "exists": configure_report_path.exists(),
            "status": str(configure.get("status", "")),
            "output_dir": str(configure.get("output_dir", "")),
            "exit_code": int(configure.get("exit_code", -1) or -1),
        },
        "rootfs_image": {
            "path": str(rootfs_image),
            "exists": rootfs_exists,
            "sha256": rootfs_sha,
            "byte_count": rootfs_image.stat().st_size if rootfs_exists else 0,
        },
        "checks": checks,
        "summary": {
            "failed_check_count": failed_check_count,
            "execution_performed": execution_performed,
            "configure_status": str(configure.get("status", "")),
            "rootfs_image_exists": rootfs_exists,
            "rootfs_image_sha256": rootfs_sha,
        },
        "limitations": [
            "A blocked report does not invoke Buildroot make.",
            "A passing build report proves an image file was emitted, not that QEMU booted it.",
            "Kernel/PGVM2 enforcement still requires captured boot and loader evidence.",
        ],
        "next_steps": [
            "Run rootfs content manifest against the reported rootfs image.",
            "Extract the rootfs read-only and compare marker/support file hashes.",
            "Only then proceed to captured QEMU boot evidence.",
        ],
    }


def write_build_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
