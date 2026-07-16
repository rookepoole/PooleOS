"""Operator handoff for read-only rootfs extraction."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.rootfs_extraction_handoff"


@dataclass(frozen=True)
class HandoffCheck:
    name: str
    severity: str
    ok: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "ok": bool(self.ok),
            "detail": self.detail,
        }


def _check(name: str, ok: bool, detail: str, *, severity: str = "fail") -> HandoffCheck:
    return HandoffCheck(name=name, severity=severity, ok=ok, detail=detail)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _linux_path(path: Path) -> str:
    value = str(path).replace("\\", "/")
    match = re.match(r"^([A-Za-z]):/(.*)$", value)
    if match:
        return f"/mnt/{match.group(1).lower()}/{match.group(2)}"
    return value


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _command(role: str, description: str, bash: str, *, requires_sudo: bool = False, mutates_host: bool = False) -> dict[str, Any]:
    return {
        "role": role,
        "description": description,
        "bash": bash,
        "requires_sudo": bool(requires_sudo),
        "mutates_host": bool(mutates_host),
    }


def _source_paths(root: Path, manifest: dict[str, Any], manifest_output_path: Path | None) -> dict[str, Path]:
    rootfs_image = manifest.get("rootfs_image", {}) if isinstance(manifest.get("rootfs_image"), dict) else {}
    extracted = manifest.get("extracted_rootfs", {}) if isinstance(manifest.get("extracted_rootfs"), dict) else {}
    source_inputs = manifest.get("source_inputs", {}) if isinstance(manifest.get("source_inputs"), dict) else {}
    image_path = _resolve(root, str(rootfs_image.get("path", "") or root / "output" / "images" / "rootfs.ext4"))
    extracted_path = _resolve(root, str(extracted.get("path", "") or root / "runs" / "rootfs_extracted"))
    image_binding_path = _resolve(root, str(source_inputs.get("image_binding_path", "") or root / "runs" / "qemu_boot_marker_image_binding.json"))
    output_path = manifest_output_path or root / "runs" / "rootfs_content_manifest.json"
    return {
        "image": image_path,
        "extracted": extracted_path,
        "image_binding": image_binding_path,
        "output": output_path,
        "mount": root / "runs" / "rootfs_mount_ro",
    }


def _build_script(*, root: Path, paths: dict[str, Path]) -> str:
    linux_root = _linux_path(root)
    linux_image = _linux_path(paths["image"])
    linux_extracted = _linux_path(paths["extracted"])
    linux_mount = _linux_path(paths["mount"])
    linux_image_binding = _linux_path(paths["image_binding"])
    linux_output = _linux_path(paths["output"])
    lines = [
        "set -euo pipefail",
        f"POOLEOS_ROOT={_sh_quote(linux_root)}",
        f"POOLEOS_ROOTFS_IMAGE={_sh_quote(linux_image)}",
        f"POOLEOS_ROOTFS_EXTRACTED={_sh_quote(linux_extracted)}",
        f"POOLEOS_ROOTFS_MOUNT={_sh_quote(linux_mount)}",
        f"POOLEOS_IMAGE_BINDING={_sh_quote(linux_image_binding)}",
        f"POOLEOS_ROOTFS_MANIFEST_OUT={_sh_quote(linux_output)}",
        'cd "$POOLEOS_ROOT"',
        'test -f "$POOLEOS_ROOTFS_IMAGE"',
        'test -f "$POOLEOS_IMAGE_BINDING"',
        'mkdir -p "$(dirname "$POOLEOS_ROOTFS_MOUNT")" "$POOLEOS_ROOTFS_EXTRACTED"',
        'if mountpoint -q "$POOLEOS_ROOTFS_MOUNT"; then echo "mount point is already active: $POOLEOS_ROOTFS_MOUNT" >&2; exit 2; fi',
        'if find "$POOLEOS_ROOTFS_EXTRACTED" -mindepth 1 -maxdepth 1 | grep -q .; then echo "extraction directory is not empty: $POOLEOS_ROOTFS_EXTRACTED" >&2; exit 3; fi',
        'mkdir -p "$POOLEOS_ROOTFS_MOUNT"',
        'sudo mount -o ro,loop "$POOLEOS_ROOTFS_IMAGE" "$POOLEOS_ROOTFS_MOUNT"',
        'trap \'sudo umount "$POOLEOS_ROOTFS_MOUNT" 2>/dev/null || true\' EXIT',
        'sudo rsync -a --numeric-ids "$POOLEOS_ROOTFS_MOUNT"/ "$POOLEOS_ROOTFS_EXTRACTED"/',
        'sudo umount "$POOLEOS_ROOTFS_MOUNT"',
        "trap - EXIT",
        'rmdir "$POOLEOS_ROOTFS_MOUNT" 2>/dev/null || true',
        'python3 "$POOLEOS_ROOT/tools/emit_rootfs_content_manifest.py" --image-binding "$POOLEOS_IMAGE_BINDING" --image "$POOLEOS_ROOTFS_IMAGE" --extracted-rootfs "$POOLEOS_ROOTFS_EXTRACTED" --out "$POOLEOS_ROOTFS_MANIFEST_OUT"',
    ]
    return "\n".join(lines) + "\n"


def _command_plan(script: str) -> list[dict[str, Any]]:
    lines = script.splitlines()
    return [
        _command("set_variables", "Set PooleOS rootfs extraction variables.", "\n".join(lines[0:7]) + "\n"),
        _command("preflight_paths", "Check that the rootfs image and image-binding artifact exist.", "\n".join(lines[7:10]) + "\n"),
        _command("prepare_directories", "Create the mount and extraction directories and refuse a non-empty extraction target.", "\n".join(lines[10:14]) + "\n", mutates_host=True),
        _command("mount_read_only", "Mount rootfs.ext4 read-only through a loop device.", "\n".join(lines[14:16]) + "\n", requires_sudo=True, mutates_host=True),
        _command("copy_contents", "Copy rootfs contents into the dedicated extraction directory.", lines[16] + "\n", requires_sudo=True, mutates_host=True),
        _command("unmount_cleanup", "Unmount the read-only image and remove the empty mount point.", "\n".join(lines[17:20]) + "\n", requires_sudo=True, mutates_host=True),
        _command("emit_manifest", "Regenerate the rootfs content manifest against the extracted directory.", lines[20] + "\n", mutates_host=True),
    ]


def make_rootfs_extraction_handoff(
    *,
    root: Path,
    rootfs_content_manifest_path: Path,
    handoff_output_path: Path | None = None,
    note_output_path: Path | None = None,
    manifest_output_path: Path | None = None,
) -> dict[str, Any]:
    source_manifest = _read_json(rootfs_content_manifest_path)
    source_status = str(source_manifest.get("status", ""))
    source_summary = source_manifest.get("summary", {}) if isinstance(source_manifest.get("summary"), dict) else {}
    paths = _source_paths(root, source_manifest, manifest_output_path)
    script = _build_script(root=root, paths=paths)
    command_plan = _command_plan(script)
    script_hash = _sha256_text(script)
    rootfs_image_exists = paths["image"].exists() and paths["image"].is_file()
    image_binding_exists = paths["image_binding"].exists() and paths["image_binding"].is_file()
    extracted_exists = paths["extracted"].exists() and paths["extracted"].is_dir()
    source_failed = int(source_summary.get("failed_check_count", 0) or 0)
    source_files = int(source_summary.get("source_file_count", 0) or 0)

    checks = [
        _check("execution_not_performed", True, "handoff assembly is non-mutating"),
        _check("codex_execution_disallowed", True, "operator handoff only; Codex must not run sudo mount or rsync"),
        _check("rootfs_extraction_not_performed", True, "rootfs_extraction_performed=False"),
        _check("source_manifest_present", bool(source_manifest) and rootfs_content_manifest_path.exists(), str(rootfs_content_manifest_path)),
        _check("source_manifest_artifact_kind", source_manifest.get("artifact_kind") == "pooleos.rootfs_content_manifest", str(source_manifest.get("artifact_kind", ""))),
        _check("source_manifest_status_usable", source_status in {"pass", "blocked"}, f"status={source_status}"),
        _check("source_manifest_has_no_failed_checks", source_failed == 0, f"failed={source_failed}"),
        _check("source_manifest_has_bound_files", source_files >= 5, f"source_files={source_files}"),
        _check("rootfs_image_path_recorded", bool(str(paths["image"])), str(paths["image"])),
        _check("rootfs_image_exists_for_operator", rootfs_image_exists, str(paths["image"]), severity="block"),
        _check("extracted_rootfs_path_recorded", bool(str(paths["extracted"])), str(paths["extracted"])),
        _check("image_binding_path_recorded", bool(str(paths["image_binding"])), str(paths["image_binding"])),
        _check("image_binding_exists_for_operator", image_binding_exists, str(paths["image_binding"]), severity="block"),
        _check("bash_script_present", bool(script.strip()), f"sha256={script_hash}"),
        _check("bash_script_mounts_read_only", "mount -o ro,loop" in script, "read-only loop mount command present"),
        _check("bash_script_refuses_nonempty_extraction", "extraction directory is not empty" in script, "non-empty extraction target guard present"),
        _check("bash_script_has_no_recursive_delete", "rm -rf" not in script and "--delete" not in script, "no recursive delete or rsync --delete"),
        _check("bash_script_unmounts", "umount" in script and "trap" in script, "unmount and trap cleanup present"),
        _check("bash_script_reruns_manifest", "emit_rootfs_content_manifest.py" in script, "rootfs content manifest command present"),
    ]
    failed_checks = [check for check in checks if check.severity == "fail" and not check.ok]
    blocking_checks = [check for check in checks if check.severity == "block" and not check.ok]
    status = "fail" if failed_checks else "blocked" if blocking_checks else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "execution_performed": False,
        "codex_execution_allowed": False,
        "rootfs_extraction_performed": False,
        "source_artifact": str(rootfs_content_manifest_path),
        "source_status": source_status,
        "handoff_output_path": str(handoff_output_path or ""),
        "note_output_path": str(note_output_path or ""),
        "rootfs_image": {
            "path": str(paths["image"]),
            "linux_path": _linux_path(paths["image"]),
            "exists": rootfs_image_exists,
        },
        "extracted_rootfs": {
            "path": str(paths["extracted"]),
            "linux_path": _linux_path(paths["extracted"]),
            "exists": extracted_exists,
        },
        "mount": {
            "path": str(paths["mount"]),
            "linux_path": _linux_path(paths["mount"]),
            "read_only": True,
            "loop": True,
        },
        "image_binding": {
            "path": str(paths["image_binding"]),
            "linux_path": _linux_path(paths["image_binding"]),
        },
        "rootfs_content_manifest_output": {
            "path": str(paths["output"]),
            "linux_path": _linux_path(paths["output"]),
        },
        "command_plan": command_plan,
        "bash_script": script,
        "bash_script_sha256": script_hash,
        "operator_receipt_template": {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "pooleos.rootfs_extraction_operator_receipt_template",
            "operator_executed": False,
            "codex_execution_performed": False,
            "rootfs_image": str(paths["image"]),
            "extracted_rootfs": str(paths["extracted"]),
            "rootfs_content_manifest_output": str(paths["output"]),
            "commands": [
                {
                    "role": command["role"],
                    "operator_checked": False,
                    "exit_code": "",
                    "notes": "",
                }
                for command in command_plan
            ],
            "post_extraction_verification": {
                "manifest_status": "",
                "matched_source_file_count": "",
                "source_file_count": "",
                "operator_verified": False,
            },
        },
        "checks": [check.to_json() for check in checks],
        "summary": {
            "failed_check_count": len(failed_checks),
            "blocking_check_count": len(blocking_checks),
            "command_count": len(command_plan),
            "source_manifest_status": source_status,
            "source_manifest_failed_check_count": source_failed,
            "source_file_count": source_files,
            "rootfs_image_exists": rootfs_image_exists,
            "extracted_rootfs_exists": extracted_exists,
            "bash_script_sha256": script_hash,
            "operator_executed": False,
            "execution_performed": False,
            "rootfs_extraction_performed": False,
        },
        "limitations": [
            "This handoff emits commands only; it does not mount, extract, copy, or delete files.",
            "The script requires operator review and sudo inside WSL/Linux before it can mount rootfs.ext4.",
            "A completed extraction still proves only source-to-rootfs file continuity, not QEMU boot or kernel enforcement.",
        ],
        "next_steps": [
            "Build output/images/rootfs.ext4 if this handoff is blocked by a missing image.",
            "Run the bash script in WSL/Linux from a reviewed operator session.",
            "After the script emits rootfs_content_manifest.json, rerun the release gate with --rootfs-content-manifest.",
        ],
    }


def render_handoff_markdown(handoff: dict[str, Any]) -> str:
    checks = handoff.get("checks", [])
    lines = [
        "# PooleOS Rootfs Extraction Handoff",
        "",
        f"Status: `{handoff.get('status')}`",
        "",
        "## Safety Boundary",
        "",
        "Codex did not execute the rootfs extraction. The commands below are for operator review inside WSL/Linux.",
        "",
        f"- Codex execution allowed: `{str(handoff.get('codex_execution_allowed')).lower()}`",
        f"- Execution performed by Codex: `{str(handoff.get('execution_performed')).lower()}`",
        f"- Rootfs extraction performed: `{str(handoff.get('rootfs_extraction_performed')).lower()}`",
        f"- Bash script SHA-256: `{handoff.get('bash_script_sha256')}`",
        "",
        "## Paths",
        "",
        f"- Rootfs image: `{handoff.get('rootfs_image', {}).get('path')}`",
        f"- Extracted rootfs: `{handoff.get('extracted_rootfs', {}).get('path')}`",
        f"- Mount point: `{handoff.get('mount', {}).get('path')}`",
        f"- Manifest output: `{handoff.get('rootfs_content_manifest_output', {}).get('path')}`",
        "",
        "## Bash Script",
        "",
        "```bash",
        str(handoff.get("bash_script", "")).rstrip(),
        "```",
        "",
        "## Receipt Template",
        "",
        f"- Operator executed: `{str(handoff.get('operator_receipt_template', {}).get('operator_executed')).lower()}`",
        f"- Codex execution performed: `{str(handoff.get('operator_receipt_template', {}).get('codex_execution_performed')).lower()}`",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        state = "PASS" if check.get("ok") else "BLOCK" if check.get("severity") == "block" else "FAIL"
        lines.append(f"- {state} `{check.get('name')}`: {check.get('detail')}")
    lines.extend(["", "## Next Steps", ""])
    for step in handoff.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_handoff(handoff: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_note(markdown: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
