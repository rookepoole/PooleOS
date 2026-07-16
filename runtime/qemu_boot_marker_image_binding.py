"""Bind QEMU boot marker emitters to Buildroot image scaffold files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_boot_marker_image_binding"
OVERLAY_PARTS = ("lab-os", "buildroot", "external", "board", "pooleos_lab", "rootfs_overlay")
SUPPORT_RELATIVE_PATHS = [
    "usr/bin/pooleos-lab-verify-input",
    "usr/bin/pooleos-lab-doctor",
    "usr/bin/pooleos-lab-release-gate",
    "usr/bin/pooleos-kernel-pgvm2-transcript-contract",
]
BUILDROOT_MANIFEST_FILES = [
    "external.desc",
    "external.mk",
    "Config.in",
    "configs/pooleos_lab_x86_64_defconfig",
    "board/pooleos_lab/post-build.sh",
]


@dataclass(frozen=True)
class BindingCheck:
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


def _check(name: str, ok: bool, detail: str, *, severity: str = "fail") -> BindingCheck:
    return BindingCheck(name=name, severity=severity, ok=ok, detail=detail)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _overlay_root(root: Path) -> Path:
    path = root
    for part in OVERLAY_PARTS:
        path /= part
    return path


def _external_root(root: Path) -> Path:
    return root / "lab-os" / "buildroot" / "external"


def _relative_to(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return ""


def _guest_path_for_overlay_file(path: Path, overlay: Path) -> str:
    rel = _relative_to(path, overlay)
    return "/" + rel if rel else ""


def _unique_marker_sources(marker_contract: dict[str, Any]) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for mapping in marker_contract.get("marker_mappings", []):
        if not isinstance(mapping, dict):
            continue
        source = str(mapping.get("source_file", ""))
        if not source:
            continue
        entry = sources.setdefault(
            source,
            {
                "source_file": source,
                "markers": [],
                "source_marker_texts": [],
            },
        )
        entry["markers"].append(str(mapping.get("marker", "")))
        entry["source_marker_texts"].append(str(mapping.get("source_marker_text", "")))
    return list(sources.values())


def _file_binding(path: Path, *, overlay: Path, role: str, markers: list[str] | None = None, marker_texts: list[str] | None = None) -> dict[str, Any]:
    text = _read_text(path)
    marker_texts = marker_texts or []
    return {
        "role": role,
        "path": str(path),
        "exists": path.exists(),
        "sha256": _sha256(path),
        "byte_count": path.stat().st_size if path.exists() and path.is_file() else 0,
        "overlay_relative_path": _relative_to(path, overlay),
        "guest_path": _guest_path_for_overlay_file(path, overlay),
        "markers": markers or [],
        "marker_texts_present": all(marker_text in text for marker_text in marker_texts),
    }


def _buildroot_file_binding(path: Path, *, external: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path),
        "exists": path.exists(),
        "sha256": _sha256(path),
        "byte_count": path.stat().st_size if path.exists() and path.is_file() else 0,
        "external_relative_path": _relative_to(path, external),
    }


def make_qemu_boot_marker_image_binding(
    *,
    root: Path,
    marker_contract_path: Path | None = None,
    lab_image_manifest_path: Path | None = None,
) -> dict[str, Any]:
    marker_contract = _read_json(marker_contract_path)
    lab_manifest = _read_json(lab_image_manifest_path)
    overlay = _overlay_root(root)
    external = _external_root(root)
    defconfig = external / "configs" / "pooleos_lab_x86_64_defconfig"
    post_build = external / "board" / "pooleos_lab" / "post-build.sh"
    config_in = external / "Config.in"
    external_desc = external / "external.desc"
    external_mk = external / "external.mk"
    defconfig_text = _read_text(defconfig)
    post_build_text = _read_text(post_build)
    config_in_text = _read_text(config_in)
    external_desc_text = _read_text(external_desc)

    marker_source_records = _unique_marker_sources(marker_contract)
    marker_file_bindings = [
        _file_binding(
            Path(record["source_file"]),
            overlay=overlay,
            role="marker_emitter",
            markers=[marker for marker in record["markers"] if marker],
            marker_texts=[text for text in record["source_marker_texts"] if text],
        )
        for record in marker_source_records
    ]
    support_file_bindings = [
        _file_binding(overlay / rel, overlay=overlay, role="guest_support")
        for rel in SUPPORT_RELATIVE_PATHS
    ]
    buildroot_manifest_files = [
        _buildroot_file_binding(external / rel, external=external, role="buildroot_external_manifest")
        for rel in BUILDROOT_MANIFEST_FILES
    ]
    lab_manifest_defconfig_sha = ""
    lab_manifest_external_path = ""
    lab_manifest_status = str(lab_manifest.get("status", ""))
    if isinstance(lab_manifest.get("buildroot"), dict):
        lab_manifest_defconfig_sha = str(lab_manifest["buildroot"].get("defconfig_sha256", ""))
        lab_manifest_external_path = str(lab_manifest["buildroot"].get("external_tree_path", ""))

    marker_contract_status = str(marker_contract.get("status", ""))
    marker_summary = marker_contract.get("summary", {}) if isinstance(marker_contract.get("summary"), dict) else {}
    all_marker_texts_bound = all(binding["marker_texts_present"] for binding in marker_file_bindings)
    marker_hash_count = sum(1 for binding in marker_file_bindings if binding["sha256"])
    marker_count = int(marker_summary.get("marker_count", 0) or 0)
    bound_marker_count = sum(len(binding["markers"]) for binding in marker_file_bindings)
    support_hash_count = sum(1 for binding in support_file_bindings if binding["sha256"])
    buildroot_hash_count = sum(1 for binding in buildroot_manifest_files if binding["sha256"])
    all_sources_in_overlay = all(bool(binding["overlay_relative_path"]) for binding in marker_file_bindings + support_file_bindings)
    chmod_targets = [
        "S99pooleos-lab",
        "pooleos-lab-doctor",
        "pooleos-kernel-pgvm2-transcript-contract",
        "pooleos-lab-release-gate",
        "pooleos-lab-smoke",
        "pooleos-lab-verify-input",
    ]
    runtime_copy_targets = ["specs", "runtime", "tools", "tests", "docs", "lab-os"]
    checks = [
        _check("execution_not_performed", True, "binding assembly is non-mutating"),
        _check("boot_evidence_not_claimed", True, "boot_evidence_claimed=False"),
        _check("security_boundary_not_claimed", True, "security_boundary_claimed=False"),
        _check("marker_contract_present", bool(marker_contract) and marker_contract_path is not None and marker_contract_path.exists(), str(marker_contract_path or "")),
        _check("marker_contract_artifact_kind", marker_contract.get("artifact_kind") == "pooleos.qemu_boot_marker_contract", str(marker_contract.get("artifact_kind", ""))),
        _check("marker_contract_status_usable", marker_contract_status in {"pass", "blocked"}, f"status={marker_contract_status}"),
        _check("marker_contract_has_no_failed_checks", marker_summary.get("failed_check_count") == 0, f"failed={marker_summary.get('failed_check_count')}"),
        _check("marker_contract_blockers_preserved", marker_contract_status != "blocked", f"status={marker_contract_status}", severity="block"),
        _check("lab_image_manifest_present", bool(lab_manifest) and lab_image_manifest_path is not None and lab_image_manifest_path.exists(), str(lab_image_manifest_path or "")),
        _check("lab_image_manifest_artifact_kind", lab_manifest.get("artifact_kind") == "pooleos.lab_image_manifest", str(lab_manifest.get("artifact_kind", ""))),
        _check("lab_image_manifest_status_usable", lab_manifest_status in {"scaffold", "built", "boot_validated"}, f"status={lab_manifest_status}"),
        _check("lab_manifest_defconfig_hash_matches", lab_manifest_defconfig_sha == _sha256(defconfig), f"manifest={lab_manifest_defconfig_sha}; current={_sha256(defconfig)}"),
        _check("lab_manifest_external_tree_matches", Path(lab_manifest_external_path) == external if lab_manifest_external_path else False, f"manifest={lab_manifest_external_path}; current={external}"),
        _check("marker_sources_exist", bool(marker_file_bindings) and all(binding["exists"] for binding in marker_file_bindings), f"sources={len(marker_file_bindings)}"),
        _check("marker_sources_hashed", marker_hash_count == len(marker_file_bindings) and bool(marker_file_bindings), f"hashed={marker_hash_count}; sources={len(marker_file_bindings)}"),
        _check("marker_contract_count_bound", marker_count > 0 and bound_marker_count == marker_count, f"bound={bound_marker_count}; marker_count={marker_count}"),
        _check("marker_texts_bound_to_sources", all_marker_texts_bound and bool(marker_file_bindings), "marker echo text is present in hashed source files"),
        _check("support_files_hashed", support_hash_count == len(support_file_bindings), f"hashed={support_hash_count}; support={len(support_file_bindings)}"),
        _check("sources_are_overlay_files", all_sources_in_overlay, "marker and support files live under rootfs_overlay"),
        _check("defconfig_references_overlay", "BR2_ROOTFS_OVERLAY" in defconfig_text and "rootfs_overlay" in defconfig_text, str(defconfig)),
        _check("defconfig_references_post_build", "BR2_ROOTFS_POST_BUILD_SCRIPT" in defconfig_text and "post-build.sh" in defconfig_text, str(defconfig)),
        _check("defconfig_enables_python3", "BR2_PACKAGE_PYTHON3=y" in defconfig_text, str(defconfig)),
        _check("defconfig_serial_getty", 'BR2_TARGET_GENERIC_GETTY_PORT="ttyS0"' in defconfig_text, str(defconfig)),
        _check("post_build_copies_runtime_tree", all(target in post_build_text for target in runtime_copy_targets), f"targets={runtime_copy_targets}"),
        _check("post_build_chmods_guest_scripts", all(target in post_build_text for target in chmod_targets), f"targets={chmod_targets}"),
        _check("buildroot_marker_config_present", "BR2_PACKAGE_POOLEOS_LAB_MARKER" in config_in_text, str(config_in)),
        _check("external_desc_names_pooleos", "name: POOLEOS" in external_desc_text, str(external_desc)),
        _check("buildroot_manifest_files_hashed", buildroot_hash_count == len(buildroot_manifest_files), f"hashed={buildroot_hash_count}; files={len(buildroot_manifest_files)}"),
        _check("external_mk_present", external_mk.exists(), str(external_mk)),
    ]
    failed_checks = [check for check in checks if check.severity == "fail" and not check.ok]
    blocking_checks = [check for check in checks if check.severity == "block" and not check.ok]
    status = "fail" if failed_checks else "blocked" if blocking_checks else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "execution_performed": False,
        "boot_evidence_claimed": False,
        "security_boundary_claimed": False,
        "source_inputs": {
            "marker_contract_path": str(marker_contract_path or ""),
            "marker_contract_status": marker_contract_status,
            "lab_image_manifest_path": str(lab_image_manifest_path or ""),
            "lab_image_manifest_status": lab_manifest_status,
        },
        "buildroot_binding": {
            "external_tree_path": str(external),
            "overlay_path": str(overlay),
            "defconfig_path": str(defconfig),
            "post_build_path": str(post_build),
            "config_option": "BR2_PACKAGE_POOLEOS_LAB_MARKER",
            "overlay_defconfig_key": "BR2_ROOTFS_OVERLAY",
            "post_build_defconfig_key": "BR2_ROOTFS_POST_BUILD_SCRIPT",
        },
        "marker_file_bindings": marker_file_bindings,
        "support_file_bindings": support_file_bindings,
        "buildroot_manifest_files": buildroot_manifest_files,
        "lab_image_manifest_binding": {
            "defconfig_sha256": lab_manifest_defconfig_sha,
            "current_defconfig_sha256": _sha256(defconfig),
            "external_tree_path": lab_manifest_external_path,
            "current_external_tree_path": str(external),
        },
        "checks": [check.to_json() for check in checks],
        "summary": {
            "failed_check_count": len(failed_checks),
            "blocking_check_count": len(blocking_checks),
            "marker_count": marker_count,
            "marker_source_file_count": len(marker_file_bindings),
            "support_file_count": len(support_file_bindings),
            "buildroot_manifest_file_count": len(buildroot_manifest_files),
            "hashed_file_count": marker_hash_count + support_hash_count + buildroot_hash_count,
            "marker_contract_status": marker_contract_status,
            "lab_image_manifest_status": lab_manifest_status,
            "execution_performed": False,
            "boot_evidence_claimed": False,
            "security_boundary_claimed": False,
        },
        "limitations": [
            "This binding hashes source and scaffold files only; it does not prove a Buildroot image was built.",
            "A blocked marker contract remains blocked here until QEMU/rootfs preflight blockers are resolved.",
            "Kernel or PGVM2 enforcement still requires captured boot evidence and kernel-owned loader evidence.",
        ],
        "next_steps": [
            "Compare these hashes with the built rootfs contents after the first successful Buildroot image build.",
            "Require captured serial evidence to match the bound marker contract before promoting boot claims.",
            "Move marker enforcement from lab shell scripts into the PGVM2 loader when kernel evidence exists.",
        ],
    }


def write_binding(binding: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
