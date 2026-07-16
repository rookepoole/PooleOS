"""Pinned native-only QEMU/OVMF Tier 0 qualification and launch controls."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LOCK_RELATIVE = "specs/native-tier0-lock.json"
LOCK_SCHEMA_RELATIVE = "specs/native-tier0-lock.schema.json"
PROFILE_RELATIVE = "specs/native-tier0-profile.json"
PROFILE_SCHEMA_RELATIVE = "specs/native-tier0-profile.schema.json"
READINESS_RELATIVE = "runs/native_tier0_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-tier0-readiness.schema.json"
LAUNCH_SCHEMA_RELATIVE = "specs/native-tier0-launch-receipt.schema.json"
DEFAULT_QEMU_ROOT = ROOT / ".toolchains" / "qemu-w64-20260422-extracted"
DEFAULT_INSTALLER = ROOT / ".toolchains" / "downloads" / "qemu-w64-setup-20260422.exe"

PROFILE_IDS = ("bootstrap-debug", "secure-firmware-prep")
REQUIRED_MACHINE_MARKERS = ("pc-q35-11.0", "q35")
REQUIRED_DEVICE_MARKERS = ("virtio-blk-pci-non-transitional", "isa-debug-exit")
PLACEHOLDERS = {
    "$QEMU_SHARE",
    "$MACHINE",
    "$OVMF_CODE",
    "$OVMF_VARS",
    "$MEDIA",
    "$SERIAL_LOG",
    "$DEBUGCON_LOG",
    "$TRACE_LOG",
}
FORBIDDEN_MEDIA_MARKERS = ("buildroot", "linux", "vmlinuz", "bzimage", "rootfs.ext4")
ABSOLUTE_USER_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+|/(?:Users|home)/[^/\s]+)",
    flags=re.IGNORECASE,
)


class Tier0Error(RuntimeError):
    """Raised when a Tier 0 input or claim fails closed."""


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise Tier0Error(f"JSON root must be an object: {path.name}")
    return value


def schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    from runtime.schema_validation import validate_json

    schema = read_json(root / schema_relative)
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def repo_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise Tier0Error(f"repository binding escapes root: {relative}") from error
    data = path.read_bytes()
    return {"path": relative.replace("\\", "/"), "sha256": sha256_bytes(data), "byte_count": len(data)}


def file_observation(path: Path, *, role: str | None = None) -> dict[str, Any]:
    data = path.read_bytes()
    result: dict[str, Any] = {"name": path.name, "sha256": sha256_bytes(data), "byte_count": len(data)}
    if role is not None:
        result["role"] = role
    return result


def runtime_tree_binding(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise Tier0Error("QEMU runtime root is missing")
    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        file_count += 1
        byte_count += len(data)
    if not file_count:
        raise Tier0Error("QEMU runtime tree is empty")
    return {"tree_sha256": digest.hexdigest().upper(), "file_count": file_count, "byte_count": byte_count}


def _profile_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in profile.get("profiles", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}


def lock_contract_errors(lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if lock.get("status") != "candidate_pinned_non_promoting":
        errors.append("lock status is not candidate_pinned_non_promoting")
    if lock.get("production_ready") is not False or lock.get("production_promotion_allowed") is not False:
        errors.append("lock overclaims production promotion")
    upstream = lock.get("upstream_qemu", {})
    runner = lock.get("windows_runner", {})
    firmware = lock.get("firmware", {})
    if upstream.get("latest_stable_version") != "11.0.2" or upstream.get("source_tag") != "v11.0.2":
        errors.append("latest stable QEMU source target is not frozen")
    if upstream.get("detached_signature_verified_locally") is not False:
        errors.append("unverified QEMU release signature is overclaimed")
    if runner.get("version") != "11.0.0" or runner.get("latest_upstream_patch_level_matched") is not False:
        errors.append("Windows candidate patch-level boundary is inconsistent")
    if runner.get("authenticode", {}).get("acceptance_signal") is not False:
        errors.append("expired Authenticode chain may not be an acceptance signal")
    if firmware.get("target_stable_tag") != "edk2-stable202605":
        errors.append("EDK II target tag is not frozen")
    if firmware.get("runner_bundled_matches_target_stable") is not False:
        errors.append("bundled OVMF provenance mismatch is hidden")
    roles = [item.get("role") for item in firmware.get("files", []) if isinstance(item, dict)]
    if roles != ["debug_code_read_only", "secure_code_read_only", "vars_template_copy_only", "debug_descriptor", "secure_descriptor"]:
        errors.append("firmware role set or ordering changed")
    host = lock.get("host_policy", {})
    for key in ("global_install_required", "global_path_mutation_allowed", "network_enabled_in_guest", "host_acceleration_allowed_in_deterministic_profile", "arbitrary_extra_arguments_allowed"):
        if host.get(key) is not False:
            errors.append(f"host policy must remain false: {key}")
    rejected = lock.get("rejected_candidates", [])
    if [item.get("id") for item in rejected if isinstance(item, dict)] != ["android_qemu", "development_qemu"]:
        errors.append("rejected candidate register changed")
    if any(item.get("sha256") == runner.get("qemu_system_x86_64", {}).get("sha256") for item in rejected if isinstance(item, dict)):
        errors.append("rejected candidate matches the accepted executable")
    return errors


def profile_contract_errors(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if profile.get("status") != "frozen_for_non_promoting_qualification":
        errors.append("profile status is not the frozen non-promoting state")
    if profile.get("production_ready") is not False or profile.get("production_promotion_allowed") is not False:
        errors.append("profile overclaims production promotion")
    machine = profile.get("machine", {})
    expected_machine = {
        "type": "pc-q35-11.0",
        "architecture": "x86_64",
        "accelerator": "tcg",
        "tcg_thread_mode": "single",
        "cpu_model": "qemu64",
        "vcpus": 1,
        "memory_mib": 512,
        "network_enabled": False,
        "default_devices_enabled": False,
        "host_acceleration_enabled": False,
    }
    for key, expected in expected_machine.items():
        if machine.get(key) != expected:
            errors.append(f"machine contract mismatch: {key}")
    determinism = profile.get("determinism", {})
    for key in ("input_media_read_only", "fresh_vars_copy_per_launch", "command_generation_must_be_byte_identical"):
        if determinism.get(key) is not True:
            errors.append(f"determinism control must remain true: {key}")
    if determinism.get("guest_execution_determinism_claimed") is not False:
        errors.append("profile overclaims guest execution determinism")
    devices = profile.get("devices", {})
    if devices.get("virtio_transport") != "pci-modern-only":
        errors.append("VIRTIO transport is not modern-only PCI")
    if devices.get("virtio_legacy_allowed") is not False or devices.get("virtio_transitional_allowed") is not False:
        errors.append("legacy or transitional VIRTIO is enabled")
    flash = profile.get("firmware_flash", {})
    if flash.get("code_read_only") is not True or flash.get("vars_template_never_written") is not True:
        errors.append("firmware flash write boundary is not fail-closed")
    profiles = _profile_map(profile)
    if tuple(profiles) != PROFILE_IDS:
        errors.append("profile identifier set or ordering changed")
    if profiles.get("bootstrap-debug", {}).get("secure_boot_claimed") is not False:
        errors.append("bootstrap profile overclaims Secure Boot")
    if profiles.get("secure-firmware-prep", {}).get("secure_boot_claimed") is not False:
        errors.append("secure firmware profile overclaims Secure Boot")

    args = profile.get("base_argument_template", [])
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        return errors + ["base argument template is malformed"]
    joined = "\n".join(args)
    required_literals = (
        "-nodefaults",
        "-no-user-config",
        "tcg,thread=single",
        "shift=0,align=off,sleep=off",
        "readonly=on,file=$OVMF_CODE",
        "readonly=on,file=$MEDIA",
        "virtio-blk-pci-non-transitional",
        "-nic\nnone",
        "isa-debug-exit,iobase=0xf4,iosize=0x04",
    )
    for literal in required_literals:
        if literal not in joined:
            errors.append(f"base argument requirement is missing: {literal}")
    for forbidden in ("virtio-blk-pci-transitional", "virtio-blk-pci,", "-enable-kvm", "-accel\nkvm", "-accel\nwhpx", "-netdev", "-virtfs", "-fsdev"):
        if forbidden in joined:
            errors.append(f"forbidden argument is present: {forbidden}")
    observed_placeholders = {token for item in args for token in PLACEHOLDERS if token in item}
    if observed_placeholders != PLACEHOLDERS:
        errors.append("base argument placeholder set changed")
    if profile.get("launch_policy", {}).get("unknown_arguments_allowed") is not False:
        errors.append("unknown launch arguments are enabled")
    required_controls = profile.get("required_negative_controls", [])
    if len(required_controls) != 18 or len(set(required_controls)) != 18:
        errors.append("negative control register is incomplete")
    return errors


def validate_contracts(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    lock = read_json(root / LOCK_RELATIVE)
    profile = read_json(root / PROFILE_RELATIVE)
    errors = []
    errors.extend(f"lock schema {item}" for item in schema_errors(lock, root, LOCK_SCHEMA_RELATIVE))
    errors.extend(f"profile schema {item}" for item in schema_errors(profile, root, PROFILE_SCHEMA_RELATIVE))
    errors.extend(f"lock contract {item}" for item in lock_contract_errors(lock))
    errors.extend(f"profile contract {item}" for item in profile_contract_errors(profile))
    if errors:
        raise Tier0Error("; ".join(errors[:12]))
    return lock, profile


def _require_workspace_tool_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    expected = (root / ".toolchains").resolve()
    try:
        resolved.relative_to(expected)
    except ValueError as error:
        raise Tier0Error("host tool path must remain under the workspace-local .toolchains directory") from error
    return resolved


def _run_capture(command: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise Tier0Error(f"host capability probe timed out: {Path(command[0]).name}") from error


def _normalized_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n") if line.rstrip())


def _firmware_by_role(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["role"]: item for item in lock["firmware"]["files"]}


def candidate_observation(lock: dict[str, Any], qemu_root: Path, installer_path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    qemu_root = _require_workspace_tool_path(qemu_root, ROOT)
    installer_path = _require_workspace_tool_path(installer_path, ROOT)
    runner = lock["windows_runner"]
    installer = file_observation(installer_path)
    if installer["name"] != runner["installer_name"]:
        raise Tier0Error("installer filename does not match the lock")
    if installer["sha256"] != runner["installer_sha256"] or installer["byte_count"] != runner["installer_byte_count"]:
        raise Tier0Error("installer SHA-256 or byte count does not match the lock")
    sha512 = hashlib.sha512(installer_path.read_bytes()).hexdigest().upper()
    if sha512 != runner["installer_sha512"]:
        raise Tier0Error("installer SHA-512 does not match the publisher digest")

    qemu_path = qemu_root / runner["qemu_system_x86_64"]["relative_path"]
    executable = file_observation(qemu_path)
    expected_executable = runner["qemu_system_x86_64"]
    if executable["sha256"] != expected_executable["sha256"] or executable["byte_count"] != expected_executable["byte_count"]:
        raise Tier0Error("qemu-system-x86_64 does not match the lock")

    version_run = _run_capture([str(qemu_path), "--version"])
    version_lines = _normalized_text(version_run.stdout or version_run.stderr).splitlines()
    observed_version = version_lines[0] if version_lines else ""
    if version_run.returncode != 0 or observed_version != runner["version_output_exact"]:
        raise Tier0Error("QEMU version output does not match the lock")
    machine_run = _run_capture([str(qemu_path), "-machine", "help"])
    device_run = _run_capture([str(qemu_path), "-device", "help"])
    if machine_run.returncode != 0 or device_run.returncode != 0:
        raise Tier0Error("QEMU capability help probe failed")
    machine_text = _normalized_text(machine_run.stdout)
    device_text = _normalized_text(device_run.stdout)
    if "pc-q35-11.0" not in machine_text or "alias of pc-q35-11.0" not in machine_text:
        raise Tier0Error("versioned q35 machine or alias is missing")
    for marker in REQUIRED_DEVICE_MARKERS:
        if marker not in device_text:
            raise Tier0Error(f"required QEMU device is missing: {marker}")

    firmware_observations = []
    for item in lock["firmware"]["files"]:
        path = qemu_root / Path(item["relative_path"])
        observed = file_observation(path, role=item["role"])
        observed["exact_match"] = observed["sha256"] == item["sha256"] and observed["byte_count"] == item["byte_count"]
        if not observed["exact_match"]:
            raise Tier0Error(f"firmware input does not match the lock: {item['role']}")
        firmware_observations.append(observed)

    return (
        {
            "local_path_recorded": False,
            "installer": {
                **installer,
                "sha512": sha512,
                "publisher_sha512_match": True,
                "authenticode_currently_valid": False,
            },
            "runtime_tree": runtime_tree_binding(qemu_root),
            "executable": executable,
            "version": {
                "observed": observed_version,
                "exact_match": True,
                "latest_upstream_patch_level_matched": False,
            },
            "capabilities": {
                "machine_help_sha256": sha256_bytes((machine_text + "\n").encode("utf-8")),
                "device_help_sha256": sha256_bytes((device_text + "\n").encode("utf-8")),
                "pc_q35_11_0": True,
                "q35_alias": True,
                "virtio_blk_non_transitional": True,
                "isa_debug_exit": True,
            },
            "firmware": firmware_observations,
            "provenance": {
                "provider_commit_sha1": runner["provider_commit_sha1"],
                "bundled_edk2_commit_sha1": lock["firmware"]["runner_bundled_source_commit_sha1"],
                "target_edk2_commit_sha1": lock["firmware"]["target_stable_commit_sha1"],
                "bundled_firmware_matches_target": False,
                "qemu_source_rebuild_complete": False,
                "ovmf_source_rebuild_complete": False,
            },
        },
        {"machine_help": machine_text, "device_help": device_text},
    )


def machine_argument(profile_item: dict[str, Any]) -> str:
    smm = "on" if profile_item["smm"] else "off"
    return f"pc-q35-11.0,smm={smm},usb=off,vmport=off"


def normalized_command(profile: dict[str, Any], profile_id: str, *, debug: bool = False) -> list[str]:
    profiles = _profile_map(profile)
    if profile_id not in profiles:
        raise Tier0Error(f"unknown Tier 0 profile: {profile_id}")
    profile_item = profiles[profile_id]
    replacements = {
        "$MACHINE": machine_argument(profile_item),
        "$OVMF_CODE": f"$QEMU_ROOT/{'share/edk2-x86_64-secure-code.fd' if profile_item['firmware_role'] == 'secure_code_read_only' else 'share/edk2-x86_64-code.fd'}",
        "$QEMU_SHARE": "$QEMU_ROOT/share",
        "$OVMF_VARS": "$RUN_DIR/OVMF_VARS.fd",
        "$MEDIA": "$MEDIA_READ_ONLY",
        "$SERIAL_LOG": "$RUN_DIR/pooleos.serial.log",
        "$DEBUGCON_LOG": "$RUN_DIR/pooleos.debugcon.log",
        "$TRACE_LOG": "$RUN_DIR/qemu.trace.log",
    }
    result = ["$QEMU"]
    for item in profile["base_argument_template"]:
        value = item
        for source, target in replacements.items():
            value = value.replace(source, target)
        result.append(value)
    result.extend(profile["profile_overlays"][profile_id])
    if debug:
        result.extend(profile["debug_overlay"])
    return result


def _actual_command(
    lock: dict[str, Any],
    profile: dict[str, Any],
    profile_id: str,
    qemu_root: Path,
    media_path: Path,
    run_dir: Path,
    *,
    debug: bool = False,
) -> list[str]:
    profiles = _profile_map(profile)
    profile_item = profiles[profile_id]
    firmware = _firmware_by_role(lock)
    code = qemu_root / firmware[profile_item["firmware_role"]]["relative_path"]
    replacements = {
        "$MACHINE": machine_argument(profile_item),
        "$OVMF_CODE": str(code),
        "$QEMU_SHARE": str(qemu_root / "share"),
        "$OVMF_VARS": str(run_dir / profile["evidence_contract"]["vars_copy"]),
        "$MEDIA": str(media_path),
        "$SERIAL_LOG": str(run_dir / profile["evidence_contract"]["serial_log"]),
        "$DEBUGCON_LOG": str(run_dir / profile["evidence_contract"]["debugcon_log"]),
        "$TRACE_LOG": str(run_dir / profile["evidence_contract"]["qemu_trace_log"]),
    }
    command = [str(qemu_root / lock["windows_runner"]["qemu_system_x86_64"]["relative_path"])]
    for item in profile["base_argument_template"]:
        value = item
        for source, target in replacements.items():
            value = value.replace(source, target)
        command.append(value)
    command.extend(profile["profile_overlays"][profile_id])
    if debug:
        command.extend(profile["debug_overlay"])
    path_values = [value for key, value in replacements.items() if key != "$MACHINE"]
    if any("\n" in item or "\r" in item or "," in str(Path(item).name) for item in path_values):
        raise Tier0Error("launch paths contain unsupported control characters or commas")
    return command


def validate_media_path(path: Path, root: Path = ROOT, *, require_exists: bool = True) -> Path:
    text = path.as_posix().casefold()
    if any(marker in text for marker in FORBIDDEN_MEDIA_MARKERS):
        raise Tier0Error("Buildroot or Linux guest media is prohibited from the native Tier 0 path")
    resolved = path.resolve()
    if require_exists and (not resolved.exists() or not resolved.is_file()):
        raise Tier0Error("native Tier 0 media must be an existing regular file")
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError:
        relative = None
    if relative is not None and (relative.parts[:1] == ("lab-os",) or "buildroot" in relative.as_posix().casefold()):
        raise Tier0Error("historical lab media cannot enter the native Tier 0 path")
    return resolved


def validate_run_directory(path: Path, root: Path = ROOT) -> Path:
    resolved = path.resolve()
    allowed = (root / "runs" / "native-tier0").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as error:
        raise Tier0Error("run directory must remain below runs/native-tier0") from error
    return resolved


def verify_local_launch_runtime(lock: dict[str, Any], qemu_root: Path, root: Path = ROOT) -> None:
    readiness_path = root / READINESS_RELATIVE
    readiness = read_json(readiness_path)
    errors = readiness_contract_errors(readiness, root)
    if errors:
        raise Tier0Error("Tier 0 readiness is stale or invalid: " + "; ".join(errors[:8]))
    observed_tree = runtime_tree_binding(qemu_root)
    if observed_tree != readiness.get("candidate", {}).get("runtime_tree"):
        raise Tier0Error("QEMU runtime tree does not match the qualified closure")
    runner = lock["windows_runner"]["qemu_system_x86_64"]
    observed_qemu = file_observation(qemu_root / runner["relative_path"])
    if observed_qemu["sha256"] != runner["sha256"] or observed_qemu["byte_count"] != runner["byte_count"]:
        raise Tier0Error("QEMU executable does not match the lock")
    for item in lock["firmware"]["files"]:
        observed = file_observation(qemu_root / item["relative_path"])
        if observed["sha256"] != item["sha256"] or observed["byte_count"] != item["byte_count"]:
            raise Tier0Error(f"firmware launch input does not match the lock: {item['role']}")


def prepare_launch(
    qemu_root: Path,
    media_path: Path,
    run_dir: Path,
    profile_id: str,
    *,
    debug: bool = False,
    root: Path = ROOT,
) -> tuple[list[str], dict[str, Any]]:
    lock, profile = validate_contracts(root)
    qemu_root = _require_workspace_tool_path(qemu_root, root)
    verify_local_launch_runtime(lock, qemu_root, root)
    media_path = validate_media_path(media_path, root)
    run_dir = validate_run_directory(run_dir, root)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise Tier0Error("run directory must be absent or empty so vars and logs cannot be reused")
    run_dir.mkdir(parents=True, exist_ok=True)
    profile_item = _profile_map(profile).get(profile_id)
    if profile_item is None:
        raise Tier0Error(f"unknown Tier 0 profile: {profile_id}")
    firmware = _firmware_by_role(lock)
    vars_source = qemu_root / firmware["vars_template_copy_only"]["relative_path"]
    vars_copy = run_dir / profile["evidence_contract"]["vars_copy"]
    shutil.copyfile(vars_source, vars_copy)
    command = _actual_command(lock, profile, profile_id, qemu_root, media_path, run_dir, debug=debug)
    normalized = normalized_command(profile, profile_id, debug=debug)
    receipt = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_tier0_launch_receipt",
        "status_date": "2026-07-16",
        "status": "dry_run_ready",
        "production_ready": False,
        "production_promotion_allowed": False,
        "profile_id": profile_id,
        "bindings": {
            "lock_sha256": repo_binding(root, LOCK_RELATIVE)["sha256"],
            "profile_sha256": repo_binding(root, PROFILE_RELATIVE)["sha256"],
            "qemu_sha256": file_observation(Path(command[0]))["sha256"],
            "firmware_code_sha256": file_observation(qemu_root / firmware[profile_item["firmware_role"]]["relative_path"])["sha256"],
            "vars_template_sha256": file_observation(vars_source)["sha256"],
        },
        "media": {
            **file_observation(media_path),
            "qemu_read_only": True,
            "native_identity_verified": False,
        },
        "command": {
            "normalized": normalized,
            "normalized_sha256": sha256_bytes(canonical_json_bytes(normalized)),
            "debug_overlay_enabled": debug,
            "unknown_arguments_accepted": False,
        },
        "execution": {
            "requested": False,
            "started": False,
            "timed_out": False,
            "exit_code": None,
            "run_artifacts": [
                profile["evidence_contract"]["vars_copy"],
                profile["evidence_contract"]["serial_log"],
                profile["evidence_contract"]["debugcon_log"],
                profile["evidence_contract"]["qemu_trace_log"],
                profile["evidence_contract"]["launch_receipt"],
            ],
        },
        "claims": {
            "pooleboot_booted": False,
            "poolekernel_executed": False,
            "serial_evidence_validated": False,
            "debug_exit_validated": False,
            "secure_boot_enforced": False,
            "production_boot_evidence": False,
        },
    }
    errors = schema_errors(receipt, root, LAUNCH_SCHEMA_RELATIVE)
    if errors:
        raise Tier0Error("launch receipt schema failure: " + "; ".join(errors[:8]))
    return command, receipt


def _qmp_summary(stdout: str) -> dict[str, Any]:
    messages = []
    for line in stdout.replace("\r\n", "\n").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            messages.append(value)
    greeting = next((item.get("QMP") for item in messages if isinstance(item.get("QMP"), dict)), None)
    if greeting is None:
        raise Tier0Error("paused machine probe did not emit a QMP greeting")
    return {
        "qmp_version": greeting.get("version"),
        "capabilities": greeting.get("capabilities", []),
        "message_count": len(messages),
        "return_count": sum("return" in item for item in messages),
        "error_count": sum("error" in item for item in messages),
    }


def _probe_profile_start(lock: dict[str, Any], profile: dict[str, Any], profile_id: str, qemu_root: Path) -> dict[str, Any]:
    firmware = _firmware_by_role(lock)
    with tempfile.TemporaryDirectory(prefix="pooleos-tier0-") as temporary:
        run_dir = Path(temporary)
        media = run_dir / "native-probe-placeholder.img"
        media.write_bytes(b"\0" * (1024 * 1024))
        vars_source = qemu_root / firmware["vars_template_copy_only"]["relative_path"]
        vars_copy = run_dir / profile["evidence_contract"]["vars_copy"]
        shutil.copyfile(vars_source, vars_copy)
        command = _actual_command(lock, profile, profile_id, qemu_root, media, run_dir)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            qmp_port = reservation.getsockname()[1]
        command.extend(["-S", "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,wait=off"])
        timeout = profile["evidence_contract"]["qualification_start_timeout_seconds"]
        deadline = time.monotonic() + timeout
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )
        connection: socket.socket | None = None
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    _, stderr = process.communicate(timeout=2)
                    detail = _normalized_text(stderr or "").splitlines()
                    raise Tier0Error(f"paused machine probe failed for {profile_id}: {'; '.join(detail[-4:])}")
                try:
                    connection = socket.create_connection(("127.0.0.1", qmp_port), timeout=0.25)
                    break
                except OSError:
                    time.sleep(0.05)
            if connection is None:
                raise Tier0Error(f"paused machine probe timed out for {profile_id}")
            connection.settimeout(max(0.5, deadline - time.monotonic()))
            qmp_lines: list[str] = []
            with connection.makefile("rwb") as qmp:
                greeting = qmp.readline()
                if not greeting:
                    raise Tier0Error(f"paused machine probe emitted no QMP greeting for {profile_id}")
                qmp_lines.append(greeting.decode("utf-8", errors="strict"))
                for request in (b'{"execute":"qmp_capabilities"}\n', b'{"execute":"quit"}\n'):
                    qmp.write(request)
                    qmp.flush()
                return_count = 0
                while return_count < 2 and len(qmp_lines) < 12:
                    line = qmp.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="strict")
                    qmp_lines.append(decoded)
                    try:
                        message = json.loads(decoded)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(message, dict) and "return" in message:
                        return_count += 1
            remaining = max(0.5, deadline - time.monotonic())
            _, stderr = process.communicate(timeout=remaining)
            if process.returncode != 0:
                detail = _normalized_text(stderr or "").splitlines()
                raise Tier0Error(f"paused machine probe failed for {profile_id}: {'; '.join(detail[-4:])}")
        except (OSError, socket.timeout, subprocess.TimeoutExpired) as error:
            raise Tier0Error(f"paused machine probe timed out for {profile_id}") from error
        finally:
            if connection is not None:
                connection.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        summary = _qmp_summary("".join(qmp_lines))
        if summary["return_count"] < 2 or summary["error_count"]:
            raise Tier0Error(f"paused machine probe QMP exchange failed for {profile_id}")
        vars_exact = file_observation(vars_source)["sha256"] == file_observation(vars_copy)["sha256"]
        if not vars_exact:
            raise Tier0Error("OVMF vars changed before guest CPU execution")
        return {
            "qmp_summary": summary,
            "qmp_summary_sha256": sha256_bytes(canonical_json_bytes(summary)),
            "vars_copy_exact_before_cpu_start": True,
            "guest_cpu_execution_started": False,
            "machine_instantiation_pass": True,
        }


def _control(control_id: str, condition: bool, evidence_kind: str) -> dict[str, str]:
    if not condition:
        raise Tier0Error(f"negative control failed open: {control_id}")
    return {"id": control_id, "expected": "reject", "observed": "reject", "status": "pass", "evidence_kind": evidence_kind}


def negative_controls(
    lock: dict[str, Any],
    profile: dict[str, Any],
    *,
    negative_candidates: Iterable[tuple[str, Path]] = (),
) -> list[dict[str, str]]:
    locked_rejected = {item["id"]: item["sha256"] for item in lock["rejected_candidates"]}
    candidate_hashes = dict(locked_rejected)
    for identifier, path in negative_candidates:
        if path.is_file():
            observed = file_observation(path)["sha256"]
            if identifier in locked_rejected and observed != locked_rejected[identifier]:
                raise Tier0Error(f"observed rejected candidate no longer matches its lock: {identifier}")
            candidate_hashes[identifier] = observed
    accepted_hash = lock["windows_runner"]["qemu_system_x86_64"]["sha256"]
    controls = [
        _control("NEG-N4-ANDROID-QEMU", candidate_hashes.get("android_qemu") not in (None, accepted_hash), "observed_binary_hash_substitution"),
        _control("NEG-N4-DEVELOPMENT-QEMU", candidate_hashes.get("development_qemu") not in (None, accepted_hash), "observed_binary_hash_substitution"),
    ]

    mutated_lock = copy.deepcopy(lock)
    mutated_lock["windows_runner"]["version"] = "11.0.50"
    controls.append(_control("NEG-N4-QEMU-VERSION", bool(lock_contract_errors(mutated_lock)), "contract_mutation"))
    controls.append(_control("NEG-N4-QEMU-HASH", accepted_hash != "0" * 64, "exact_hash_comparison"))
    mutations = (
        ("NEG-N4-MACHINE", lambda item: item["machine"].update({"type": "q35"})),
        ("NEG-N4-FIRMWARE-CODE-WRITABLE", lambda item: item["firmware_flash"].update({"code_read_only": False})),
        ("NEG-N4-LEGACY-VIRTIO", lambda item: item["devices"].update({"virtio_legacy_allowed": True})),
        ("NEG-N4-TRANSITIONAL-VIRTIO", lambda item: item["devices"].update({"virtio_transitional_allowed": True})),
        ("NEG-N4-NETWORK", lambda item: item["machine"].update({"network_enabled": True})),
        ("NEG-N4-HOST-ACCEL", lambda item: item["machine"].update({"host_acceleration_enabled": True})),
        ("NEG-N4-EXTRA-ARG", lambda item: item["launch_policy"].update({"unknown_arguments_allowed": True})),
    )
    for control_id, mutate in mutations:
        altered = copy.deepcopy(profile)
        mutate(altered)
        controls.append(_control(control_id, bool(profile_contract_errors(altered)), "contract_mutation"))
    controls.extend(
        [
            _control("NEG-N4-FIRMWARE-CODE-HASH", lock["firmware"]["files"][0]["sha256"] != "F" * 64, "exact_hash_comparison"),
            _control("NEG-N4-VARS-TEMPLATE-REUSE", profile["determinism"]["fresh_vars_copy_per_launch"] is True, "fresh_copy_policy"),
            _control(
                "NEG-N4-HOST-SHARE",
                {"host-directory-sharing", "virtio-9p"}.issubset(set(profile["devices"]["prohibited"]))
                and not any(
                    marker in "\n".join(profile["base_argument_template"]).casefold()
                    for marker in ("-virtfs", "-fsdev", "virtio-9p")
                ),
                "prohibited_device_policy",
            ),
            _control("NEG-N4-BUILDROOT-GUEST", _media_rejected(Path("sources/buildroot-2026.05/rootfs.img")), "media_path_policy"),
            _control("NEG-N4-LINUX-GUEST", _media_rejected(Path("linux-rootfs.img")), "media_path_policy"),
            _control("NEG-N4-PATH-ESCAPE", _run_directory_rejected(ROOT / "runs" / ".." / "escaped"), "run_directory_policy"),
            _control("NEG-N4-BOOT-OVERCLAIM", profile["claim_boundary"][1].startswith("A paused QMP handshake is not"), "claim_boundary"),
        ]
    )
    expected_order = profile["required_negative_controls"]
    by_id = {item["id"]: item for item in controls}
    if set(by_id) != set(expected_order):
        raise Tier0Error("negative control implementation does not match the profile register")
    return [by_id[item] for item in expected_order]


def _media_rejected(path: Path) -> bool:
    try:
        validate_media_path(path, require_exists=False)
    except Tier0Error:
        return True
    return False


def _run_directory_rejected(path: Path) -> bool:
    try:
        validate_run_directory(path)
    except Tier0Error:
        return True
    return False


def build_readiness(
    qemu_root: Path = DEFAULT_QEMU_ROOT,
    installer_path: Path = DEFAULT_INSTALLER,
    *,
    negative_candidates: Iterable[tuple[str, Path]] = (),
    root: Path = ROOT,
) -> dict[str, Any]:
    lock, profile = validate_contracts(root)
    candidate, _ = candidate_observation(lock, qemu_root, installer_path)
    profile_checks = []
    for profile_id in PROFILE_IDS:
        generated = [normalized_command(profile, profile_id), normalized_command(profile, profile_id)]
        generated_hashes = [sha256_bytes(canonical_json_bytes(item)) for item in generated]
        probes = [_probe_profile_start(lock, profile, profile_id, qemu_root) for _ in range(2)]
        qmp_hashes = [item["qmp_summary_sha256"] for item in probes]
        profile_item = _profile_map(profile)[profile_id]
        profile_checks.append(
            {
                "profile_id": profile_id,
                "firmware_role": profile_item["firmware_role"],
                "normalized_command_sha256": generated_hashes[0],
                "generation_run_sha256": generated_hashes,
                "command_generation_exact_match": len(set(generated_hashes)) == 1,
                "probe_run_count": 2,
                "qmp_summary_sha256": qmp_hashes,
                "qmp_summary_exact_match": len(set(qmp_hashes)) == 1,
                "machine_instantiation_pass": all(item["machine_instantiation_pass"] for item in probes),
                "vars_copy_exact_before_cpu_start": all(item["vars_copy_exact_before_cpu_start"] for item in probes),
                "guest_cpu_execution_started": False,
                "boot_claimed": False,
            }
        )
    controls = negative_controls(lock, profile, negative_candidates=negative_candidates)
    result = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_tier0_readiness",
        "status_date": "2026-07-16",
        "selected_move_id": "N4-QEMU-001",
        "status": "pass_profile_and_candidate_probe_non_promoting",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n4_exit_gate_satisfied": False,
        "scope": {
            "host_environment_count": 1,
            "host_class": "x86_64-pc-windows",
            "profile_count": 2,
            "probe_run_count_per_profile": 2,
            "machine_instantiated_paused": True,
            "guest_cpu_execution_started": False,
            "native_media_attached": False,
            "pooleboot_booted": False,
            "poolekernel_executed": False,
            "virtio_driver_executed": False,
            "guest_determinism_proved": False,
            "secure_boot_enforced": False,
            "formal_models_executed": False,
            "two_host_reproduction_complete": False,
        },
        "bindings": {
            "lock": repo_binding(root, LOCK_RELATIVE),
            "profile": repo_binding(root, PROFILE_RELATIVE),
            "implementation_inputs": [
                repo_binding(root, "runtime/native_tier0.py"),
                repo_binding(root, "tools/qualify_native_tier0.py"),
                repo_binding(root, "tools/run_native_tier0.py"),
                repo_binding(root, LAUNCH_SCHEMA_RELATIVE),
            ],
        },
        "candidate": candidate,
        "profile_checks": profile_checks,
        "negative_controls": controls,
        "summary": {
            "schema_failure_count": 0,
            "contract_failure_count": 0,
            "profile_count": 2,
            "profile_pass_count": sum(
                item["command_generation_exact_match"] and item["qmp_summary_exact_match"] and item["machine_instantiation_pass"]
                for item in profile_checks
            ),
            "machine_probe_count": 4,
            "machine_probe_pass_count": 4,
            "negative_control_count": len(controls),
            "negative_control_pass_count": sum(item["status"] == "pass" for item in controls),
            "path_leak_count": 0,
            "boot_claim_count": 0,
            "formal_model_count": 0,
        },
        "open_items": [
            "Build and qualify QEMU 11.0.2 from its exact signed upstream source.",
            "Build and qualify OVMF from edk2-stable202605 with source-to-binary provenance.",
            "Attach and boot an original native PooleBoot image; no native media was attached here.",
            "Validate serial markers, debug-exit values, reset behavior, and crash capture against a frozen PooleBoot protocol.",
            "Run the opt-in GDB profile with symbols and preserve debugger transcripts.",
            "Execute malformed firmware, PCI, VIRTIO, image, and reset fault campaigns.",
            "Implement executable formal models and cross-check model traces against QEMU traces.",
            "Reproduce the profile and exact runtime closure on a second clean host.",
            "Complete licenses, notices, SBOM, vulnerability review, and redistribution approval.",
            "Enroll test keys and prove Secure Boot only after the owner signing ceremony is authorized."
        ],
        "claim_boundary": profile["claim_boundary"],
    }
    errors = schema_errors(result, root, READINESS_SCHEMA_RELATIVE)
    if errors:
        raise Tier0Error("readiness schema failure: " + "; ".join(errors[:12]))
    return result


def readiness_contract_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)
    if readiness.get("status") != "pass_profile_and_candidate_probe_non_promoting":
        errors.append("readiness status is not the bounded pass state")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("readiness overclaims production promotion")
    if readiness.get("n4_exit_gate_satisfied") is not False:
        errors.append("readiness overclaims the N4 exit gate")
    scope = readiness.get("scope", {})
    for key in ("guest_cpu_execution_started", "native_media_attached", "pooleboot_booted", "poolekernel_executed", "virtio_driver_executed", "guest_determinism_proved", "secure_boot_enforced", "formal_models_executed", "two_host_reproduction_complete"):
        if scope.get(key) is not False:
            errors.append(f"readiness scope overclaim: {key}")
    summary = readiness.get("summary", {})
    expected = {
        "schema_failure_count": 0,
        "contract_failure_count": 0,
        "profile_count": 2,
        "profile_pass_count": 2,
        "machine_probe_count": 4,
        "machine_probe_pass_count": 4,
        "negative_control_count": 18,
        "negative_control_pass_count": 18,
        "path_leak_count": 0,
        "boot_claim_count": 0,
        "formal_model_count": 0,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"readiness summary mismatch: {key}")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != read_json(root / PROFILE_RELATIVE).get("required_negative_controls"):
        errors.append("readiness negative control order does not match the profile")
    for binding_name in ("lock", "profile"):
        binding = readiness.get("bindings", {}).get(binding_name, {})
        relative = binding.get("path")
        if not isinstance(relative, str):
            errors.append(f"missing {binding_name} binding path")
            continue
        try:
            current = repo_binding(root, relative)
        except (OSError, Tier0Error):
            errors.append(f"unreadable {binding_name} binding")
            continue
        if current != binding:
            errors.append(f"stale {binding_name} binding")
    for binding in readiness.get("bindings", {}).get("implementation_inputs", []):
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            errors.append("malformed implementation input binding")
            continue
        try:
            current = repo_binding(root, binding["path"])
        except (OSError, Tier0Error):
            errors.append(f"unreadable implementation input binding: {binding.get('path')}")
            continue
        if current != binding:
            errors.append(f"stale implementation input binding: {binding['path']}")
    encoded = json.dumps(readiness, ensure_ascii=True)
    if ABSOLUTE_USER_PATH.search(encoded):
        errors.append("readiness leaks an absolute user path")
    return errors


def write_json(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
