"""Bind built rootfs contents back to marker image-binding source hashes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.rootfs_content_manifest"


@dataclass(frozen=True)
class ManifestCheck:
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


def _check(name: str, ok: bool, detail: str, *, severity: str = "fail") -> ManifestCheck:
    return ManifestCheck(name=name, severity=severity, ok=ok, detail=detail)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_image_path(root: Path) -> Path:
    return root / "output" / "images" / "rootfs.ext4"


def _guest_path_to_rootfs_path(extracted_rootfs_path: Path | None, guest_path: str) -> Path | None:
    if extracted_rootfs_path is None or not guest_path:
        return None
    parts = [part for part in guest_path.replace("\\", "/").lstrip("/").split("/") if part]
    return extracted_rootfs_path.joinpath(*parts) if parts else extracted_rootfs_path


def _source_file_bindings(image_binding: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for key in ("marker_file_bindings", "support_file_bindings"):
        group = image_binding.get(key, [])
        if isinstance(group, list):
            files.extend(item for item in group if isinstance(item, dict))
    return files


def _content_file_binding(source: dict[str, Any], extracted_rootfs_path: Path | None) -> dict[str, Any]:
    guest_path = str(source.get("guest_path", ""))
    rootfs_path = _guest_path_to_rootfs_path(extracted_rootfs_path, guest_path)
    rootfs_sha = _sha256(rootfs_path) if rootfs_path is not None else ""
    source_sha = str(source.get("sha256", ""))
    rootfs_exists = bool(rootfs_path and rootfs_path.exists() and rootfs_path.is_file())
    return {
        "role": str(source.get("role", "")),
        "guest_path": guest_path,
        "source_path": str(source.get("path", "")),
        "source_sha256": source_sha,
        "source_byte_count": int(source.get("byte_count", 0) or 0),
        "rootfs_path": str(rootfs_path or ""),
        "rootfs_exists": rootfs_exists,
        "rootfs_sha256": rootfs_sha,
        "rootfs_byte_count": rootfs_path.stat().st_size if rootfs_exists and rootfs_path is not None else 0,
        "matches_source_sha256": bool(rootfs_sha and source_sha and rootfs_sha == source_sha),
    }


def make_rootfs_content_manifest(
    *,
    root: Path,
    image_binding_path: Path | None = None,
    image_path: Path | None = None,
    extracted_rootfs_path: Path | None = None,
) -> dict[str, Any]:
    image = image_path or default_image_path(root)
    image_binding = _read_json(image_binding_path)
    binding_summary = image_binding.get("summary", {}) if isinstance(image_binding.get("summary"), dict) else {}
    binding_status = str(image_binding.get("status", ""))
    source_files = _source_file_bindings(image_binding)
    content_files = [_content_file_binding(source, extracted_rootfs_path) for source in source_files]
    extracted_exists = bool(extracted_rootfs_path and extracted_rootfs_path.exists() and extracted_rootfs_path.is_dir())
    image_sha = _sha256(image)
    guest_paths = [str(item.get("guest_path", "")) for item in source_files if item.get("guest_path")]
    source_sha_count = sum(1 for item in source_files if item.get("sha256"))
    rootfs_file_count = sum(1 for item in content_files if item.get("rootfs_exists") is True)
    matched_count = sum(1 for item in content_files if item.get("matches_source_sha256") is True)

    checks = [
        _check("execution_not_performed", True, "manifest assembly is read-only"),
        _check("rootfs_extraction_not_performed", True, "tool records an extracted tree but does not mount or extract images"),
        _check("boot_evidence_not_claimed", True, "boot_evidence_claimed=False"),
        _check("security_boundary_not_claimed", True, "security_boundary_claimed=False"),
        _check("rootfs_image_path_recorded", bool(str(image)), str(image), severity="block"),
        _check("rootfs_image_exists", image.exists() and image.is_file(), str(image), severity="block"),
        _check("rootfs_image_hashed", bool(image_sha), f"sha256={image_sha}", severity="block"),
        _check("image_binding_present", bool(image_binding) and image_binding_path is not None and image_binding_path.exists(), str(image_binding_path or "")),
        _check("image_binding_artifact_kind", image_binding.get("artifact_kind") == "pooleos.qemu_boot_marker_image_binding", str(image_binding.get("artifact_kind", ""))),
        _check("image_binding_status_usable", binding_status in {"pass", "blocked"}, f"status={binding_status}"),
        _check("image_binding_has_no_failed_checks", binding_summary.get("failed_check_count") == 0, f"failed={binding_summary.get('failed_check_count')}"),
        _check("image_binding_blockers_preserved", binding_status != "blocked", f"status={binding_status}", severity="block"),
        _check("source_file_bindings_present", len(source_files) >= 5, f"source_files={len(source_files)}"),
        _check("source_files_have_guest_paths", len(guest_paths) == len(source_files) and bool(source_files), f"guest_paths={len(guest_paths)}; source_files={len(source_files)}"),
        _check("source_files_have_hashes", source_sha_count == len(source_files) and bool(source_files), f"source_hashes={source_sha_count}; source_files={len(source_files)}"),
        _check("source_guest_paths_unique", len(guest_paths) == len(set(guest_paths)) and bool(guest_paths), f"guest_paths={len(guest_paths)}; unique={len(set(guest_paths))}"),
        _check("extracted_rootfs_path_recorded", extracted_rootfs_path is not None and bool(str(extracted_rootfs_path)), str(extracted_rootfs_path or ""), severity="block"),
        _check("extracted_rootfs_exists", extracted_exists, str(extracted_rootfs_path or ""), severity="block"),
    ]
    if extracted_exists:
        checks.extend(
            [
                _check("rootfs_files_exist", rootfs_file_count == len(content_files) and bool(content_files), f"rootfs_files={rootfs_file_count}; expected={len(content_files)}"),
                _check("rootfs_files_hashed", sum(1 for item in content_files if item.get("rootfs_sha256")) == len(content_files), f"hashed={sum(1 for item in content_files if item.get('rootfs_sha256'))}; expected={len(content_files)}"),
                _check("rootfs_hashes_match_sources", matched_count == len(content_files) and bool(content_files), f"matched={matched_count}; expected={len(content_files)}"),
            ]
        )
    else:
        checks.extend(
            [
                _check("rootfs_files_exist", True, "not evaluated until extracted_rootfs_exists"),
                _check("rootfs_files_hashed", True, "not evaluated until extracted_rootfs_exists"),
                _check("rootfs_hashes_match_sources", True, "not evaluated until extracted_rootfs_exists"),
            ]
        )

    failed_checks = [check for check in checks if check.severity == "fail" and not check.ok]
    blocking_checks = [check for check in checks if check.severity == "block" and not check.ok]
    status = "fail" if failed_checks else "blocked" if blocking_checks else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "execution_performed": False,
        "rootfs_extraction_performed": False,
        "boot_evidence_claimed": False,
        "security_boundary_claimed": False,
        "source_inputs": {
            "image_binding_path": str(image_binding_path or ""),
            "image_binding_status": binding_status,
        },
        "rootfs_image": {
            "path": str(image),
            "exists": image.exists() and image.is_file(),
            "sha256": image_sha,
            "byte_count": image.stat().st_size if image.exists() and image.is_file() else 0,
        },
        "extracted_rootfs": {
            "path": str(extracted_rootfs_path or ""),
            "exists": extracted_exists,
        },
        "content_file_bindings": content_files,
        "checks": [check.to_json() for check in checks],
        "summary": {
            "failed_check_count": len(failed_checks),
            "blocking_check_count": len(blocking_checks),
            "source_file_count": len(source_files),
            "source_hashed_file_count": source_sha_count,
            "rootfs_file_count": rootfs_file_count,
            "matched_source_file_count": matched_count,
            "image_exists": image.exists() and image.is_file(),
            "image_sha256": image_sha,
            "extracted_rootfs_exists": extracted_exists,
            "image_binding_status": binding_status,
            "execution_performed": False,
            "rootfs_extraction_performed": False,
            "boot_evidence_claimed": False,
            "security_boundary_claimed": False,
        },
        "limitations": [
            "This artifact hashes an existing image file and optional extracted rootfs files; it does not build, mount, or extract rootfs.ext4.",
            "A blocked status is expected until output/images/rootfs.ext4 and an extracted rootfs tree are available.",
            "Matching rootfs file hashes do not prove QEMU booted or that PGVM2/kernel enforcement happened.",
        ],
        "next_steps": [
            "Build output/images/rootfs.ext4 with the PooleOS Buildroot external tree.",
            "Extract or mount the rootfs read-only and rerun this manifest with --extracted-rootfs.",
            "Use captured QEMU serial evidence only after rootfs contents match the source binding.",
        ],
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
