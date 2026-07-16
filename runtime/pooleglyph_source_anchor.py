"""PooleGlyph source anchor evidence for tandem PooleOS development."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pooleglyph_source_anchor"
REQUIRED_FILES = [
    "pooleglyph_pgvm.py",
    "pooleglyph_pgvm_conformance.py",
    "pooleglyph_source_compiler_tests.py",
    "pooleglyph_gallery.py",
    "conformance_cases_v0_1.json",
    "docs/PGVM_BYTECODE_SPEC.md",
    "docs/LANGUAGE_SPEC.md",
]


def default_pooleglyph_path(*, workspace_root: Path) -> Path:
    home_live = Path.home() / "PooleGlyph"
    if home_live.exists():
        return home_live
    return workspace_root / "PooleGlyph"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _run_git(path: Path, args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.returncode, completed.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _phase_number(text: str) -> int:
    match = re.search(r"Phase\s+(\d+)", text)
    return int(match.group(1)) if match else 0


def _manifest_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _normalize_manifest(data: dict[str, Any], manifest_path: Path) -> dict[str, str]:
    phase = data.get("phase")
    phase_name = str(data.get("phase_name", ""))
    checkpoint = str(data.get("checkpoint", ""))
    if not checkpoint and phase:
        checkpoint = f"Phase {phase} - {phase_name}".strip()
    handoff_markdown = str(
        data.get("handoff_markdown")
        or data.get("checkpoint_handoff_markdown_path")
        or data.get("handoff_markdown_path")
        or ""
    )
    return {
        "manifest_path": str(manifest_path),
        "handoff_markdown": handoff_markdown,
        "checkpoint": checkpoint,
        "sha256": str(data.get("sha256") or data.get("checkpoint_zip_sha256") or "").upper(),
        "zip_path": str(data.get("zip_path") or data.get("checkpoint_zip_path") or ""),
        "next_recommended_phase": str(data.get("next_recommended_phase", "")),
        "created_local_time": str(data.get("created_local_time") or _manifest_time(manifest_path)),
    }


def _checkpoint_lineage(checkpoint_root: Path) -> list[dict[str, str]]:
    manifests = sorted(checkpoint_root.glob("*.manifest.json"), key=lambda path: path.stat().st_mtime)
    lineage: list[dict[str, str]] = []
    for manifest_path in manifests:
        data = _read_json(manifest_path)
        normalized = _normalize_manifest(data, manifest_path)
        lineage.append(
            {
                "manifest_path": normalized["manifest_path"],
                "checkpoint": normalized["checkpoint"],
                "sha256": normalized["sha256"],
                "created_local_time": normalized["created_local_time"],
            }
        )
    return lineage


def _latest_checkpoint(checkpoint_root: Path) -> dict[str, str]:
    manifests = sorted(checkpoint_root.glob("*.manifest.json"), key=lambda path: path.stat().st_mtime)
    if not manifests:
        return {
            "manifest_path": "",
            "handoff_markdown": "",
            "checkpoint": "",
            "sha256": "",
            "zip_path": "",
            "next_recommended_phase": "",
            "created_local_time": "",
        }
    manifest_path = manifests[-1]
    data = _read_json(manifest_path)
    return _normalize_manifest(data, manifest_path)


def make_source_anchor(*, pooleglyph_path: Path) -> dict[str, Any]:
    checkpoint_root = pooleglyph_path / "checkpoints"
    required_files = [
        {"path": str(pooleglyph_path / relative), "exists": (pooleglyph_path / relative).exists()}
        for relative in REQUIRED_FILES
    ]
    missing_required = [record for record in required_files if not record["exists"]]

    git_tree_code, git_tree = _run_git(pooleglyph_path, ["rev-parse", "--is-inside-work-tree"]) if pooleglyph_path.exists() else (1, "")
    commit_code, commit = _run_git(pooleglyph_path, ["rev-parse", "HEAD"]) if pooleglyph_path.exists() else (1, "")
    status_code, status = _run_git(pooleglyph_path, ["status", "--short"]) if pooleglyph_path.exists() else (1, "")
    dirty_files = [line for line in status.splitlines() if line.strip()]
    checkpoint_lineage = _checkpoint_lineage(checkpoint_root) if checkpoint_root.exists() else []
    latest = _latest_checkpoint(checkpoint_root) if checkpoint_root.exists() else _latest_checkpoint(checkpoint_root)

    checks = [
        _check("pooleglyph_path_exists", pooleglyph_path.exists(), str(pooleglyph_path)),
        _check("git_work_tree", git_tree_code == 0 and git_tree == "true", git_tree or "not a git work tree"),
        _check("git_commit_present", commit_code == 0 and bool(commit), commit if commit else "missing commit"),
        _check("required_files_present", not missing_required, f"missing={len(missing_required)}"),
        _check("checkpoint_root_exists", checkpoint_root.exists(), str(checkpoint_root)),
        _check("checkpoint_manifests_present", bool(checkpoint_lineage), f"count={len(checkpoint_lineage)}"),
        _check("latest_checkpoint_manifest_present", bool(latest["manifest_path"]), latest["manifest_path"] or "missing"),
        _check("phase19_or_later_checkpoint_seen", _phase_number(latest["checkpoint"]) >= 19, latest["checkpoint"] or "missing"),
    ]
    latest_zip_path = Path(latest["zip_path"]) if latest["zip_path"] else Path()
    latest_zip_exists = bool(latest["zip_path"]) and latest_zip_path.exists()
    latest_zip_hash = _sha256_file(latest_zip_path) if latest_zip_exists else ""
    expected_hash = latest["sha256"].upper()
    checks.extend(
        [
            _check("latest_checkpoint_zip_exists", latest_zip_exists, latest["zip_path"] or "missing"),
            _check(
                "latest_checkpoint_zip_hash_match",
                latest_zip_exists and bool(expected_hash) and latest_zip_hash == expected_hash,
                f"computed={latest_zip_hash}; expected={expected_hash}",
            ),
        ]
    )
    failed = [check for check in checks if not check["ok"]]
    warn = dirty_files and not failed

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "fail" if failed else "warn" if warn else "pass",
        "pooleglyph_path": str(pooleglyph_path),
        "git": {
            "is_work_tree": git_tree_code == 0 and git_tree == "true",
            "commit": commit if commit_code == 0 else "",
            "dirty_files": dirty_files,
        },
        "required_files": required_files,
        "checkpoint_root": str(checkpoint_root),
        "latest_checkpoint": latest,
        "checkpoint_lineage": checkpoint_lineage,
        "checks": checks,
        "summary": {
            "required_file_count": len(required_files),
            "missing_required_file_count": len(missing_required),
            "checkpoint_manifest_count": len(checkpoint_lineage),
            "dirty_file_count": len(dirty_files),
            "failed_check_count": len(failed),
        },
        "next_steps": [
            "Use this live PooleGlyph root for tandem PooleOS evidence unless an explicit override is supplied.",
            f"After {latest['next_recommended_phase'] or 'the next PooleGlyph checkpoint'} lands, regenerate this anchor so PooleOS sees the updated language surface.",
            "Bind PooleOS PGB2 region/capability proof cases to the live PooleGlyph parser/Core IR checkpoints.",
        ],
    }


def write_anchor(anchor: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
