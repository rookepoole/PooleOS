"""QEMU shared-folder staging contract for PooleOS Lab inputs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from runtime import boot_trap_bundle_manifest
from runtime.schema_validation import validate_json


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_shared_folder_contract"
DEFAULT_MOUNT_TAG = "pooleos_output"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _schema_errors(value: dict[str, Any], schema_path: Path) -> list[str]:
    try:
        schema = _read_json(schema_path)
    except Exception as exc:
        return [f"schema read failed: {exc}"]
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def _copy_file(source: Path, target: Path, *, perform_copy: bool) -> None:
    if perform_copy:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def make_qemu_shared_folder_contract(
    *,
    shared_dir: Path,
    bundle_path: Path,
    replay_proof_path: Path,
    boot_trap_manifest_path: Path,
    specs_dir: Path,
    trap_abi_boundary_receipt_path: Path | None = None,
    mount_tag: str = DEFAULT_MOUNT_TAG,
    perform_copy: bool = True,
) -> dict[str, Any]:
    manifest = _read_json(boot_trap_manifest_path) if boot_trap_manifest_path.exists() else {}
    abi_receipt = (
        _read_json(trap_abi_boundary_receipt_path)
        if trap_abi_boundary_receipt_path is not None and trap_abi_boundary_receipt_path.exists()
        else {}
    )
    manifest_errors = (
        _schema_errors(manifest, specs_dir / "boot-trap-bundle-manifest.schema.json")
        if manifest
        else ["missing boot trap bundle manifest"]
    )
    abi_errors = (
        _schema_errors(abi_receipt, specs_dir / "pgb2-trap-abi-boundary-receipt.schema.json")
        if abi_receipt
        else []
    )
    staged_bundle = shared_dir / boot_trap_bundle_manifest.DEFAULT_BUNDLE_NAME
    staged_replay = shared_dir / boot_trap_bundle_manifest.DEFAULT_REPLAY_NAME
    staged_manifest = shared_dir / boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME
    staged_abi_receipt = shared_dir / boot_trap_bundle_manifest.DEFAULT_ABI_BOUNDARY_RECEIPT_NAME
    expected_bundle_sha = str(manifest.get("bundle", {}).get("sha256", ""))
    expected_replay_sha = str(manifest.get("replay_proof", {}).get("sha256", ""))
    expected_manifest_status = str(manifest.get("status", ""))
    abi_summary = abi_receipt.get("summary", {}) if isinstance(abi_receipt.get("summary"), dict) else {}
    abi_boundary = abi_receipt.get("abi_boundary", {}) if isinstance(abi_receipt.get("abi_boundary"), dict) else {}
    abi_claims = abi_receipt.get("claim_boundaries", {}) if isinstance(abi_receipt.get("claim_boundaries"), dict) else {}
    abi_receipt_provided = trap_abi_boundary_receipt_path is not None

    copy_errors: list[str] = []
    copy_pairs = [
        (bundle_path, staged_bundle),
        (replay_proof_path, staged_replay),
        (boot_trap_manifest_path, staged_manifest),
    ]
    if trap_abi_boundary_receipt_path is not None:
        copy_pairs.append((trap_abi_boundary_receipt_path, staged_abi_receipt))
    for source, target in copy_pairs:
        try:
            _copy_file(source, target, perform_copy=perform_copy)
        except Exception as exc:
            copy_errors.append(f"{source} -> {target}: {exc}")

    actual_bundle_sha = boot_trap_bundle_manifest.file_sha256(staged_bundle)
    actual_replay_sha = boot_trap_bundle_manifest.file_sha256(staged_replay)
    actual_manifest_sha = boot_trap_bundle_manifest.file_sha256(staged_manifest)
    actual_abi_receipt_sha = boot_trap_bundle_manifest.file_sha256(staged_abi_receipt)
    source_manifest_sha = boot_trap_bundle_manifest.file_sha256(boot_trap_manifest_path)
    source_abi_receipt_sha = boot_trap_bundle_manifest.file_sha256(trap_abi_boundary_receipt_path) if trap_abi_boundary_receipt_path is not None else ""
    qemu_args = [
        "-virtfs",
        f"local,path={shared_dir},mount_tag={mount_tag},security_model=none,id={mount_tag}",
    ]
    abi_receipt_non_promoting = (
        bool(abi_receipt)
        and abi_receipt.get("artifact_kind") == "pooleos.pgb2_trap_abi_boundary_receipt"
        and abi_receipt.get("status") == "draft_verified"
        and int(abi_summary.get("failed_check_count", 0) or 0) == 0
        and int(abi_summary.get("source_overclaim_count", 0) or 0) == 0
        and abi_boundary.get("abi_frozen") is False
        and abi_boundary.get("kernel_abi_promotion_allowed") is False
        and abi_boundary.get("kernel_enforcement_claimed") is False
        and abi_boundary.get("security_boundary_claimed") is False
        and abi_claims.get("draft_bytes_release_gate_usable") is True
    )

    checks = [
        _check("shared_dir_ready", shared_dir.exists() or perform_copy, str(shared_dir)),
        _check("bundle_source_present", bundle_path.exists(), str(bundle_path)),
        _check("replay_source_present", replay_proof_path.exists(), str(replay_proof_path)),
        _check("manifest_source_present", boot_trap_manifest_path.exists(), str(boot_trap_manifest_path)),
        _check(
            "abi_boundary_receipt_source_present_when_provided",
            (not abi_receipt_provided) or (trap_abi_boundary_receipt_path is not None and trap_abi_boundary_receipt_path.exists()),
            str(trap_abi_boundary_receipt_path or ""),
        ),
        _check("manifest_schema_valid", not manifest_errors, "valid" if not manifest_errors else "; ".join(manifest_errors[:5])),
        _check(
            "abi_boundary_receipt_schema_valid_when_provided",
            (not abi_receipt_provided) or (bool(abi_receipt) and not abi_errors),
            "not provided" if not abi_receipt_provided else "valid" if not abi_errors else "; ".join(abi_errors[:5]),
        ),
        _check("manifest_status_pass", expected_manifest_status == "pass", f"status={expected_manifest_status}"),
        _check(
            "abi_boundary_receipt_non_promoting_when_provided",
            (not abi_receipt_provided) or abi_receipt_non_promoting,
            "not provided" if not abi_receipt_provided else f"status={abi_receipt.get('status', '')}; promotion={abi_boundary.get('kernel_abi_promotion_allowed')}",
        ),
        _check("copy_completed", not copy_errors, "copied" if not copy_errors else "; ".join(copy_errors[:5])),
        _check("staged_bundle_hash_matches", actual_bundle_sha == expected_bundle_sha, f"expected={expected_bundle_sha}; actual={actual_bundle_sha}"),
        _check("staged_replay_hash_matches", actual_replay_sha == expected_replay_sha, f"expected={expected_replay_sha}; actual={actual_replay_sha}"),
        _check("staged_manifest_hash_matches", actual_manifest_sha == source_manifest_sha, f"expected={source_manifest_sha}; actual={actual_manifest_sha}"),
        _check(
            "staged_abi_boundary_receipt_hash_matches_when_provided",
            (not abi_receipt_provided) or (actual_abi_receipt_sha == source_abi_receipt_sha and bool(actual_abi_receipt_sha)),
            "not provided" if not abi_receipt_provided else f"expected={source_abi_receipt_sha}; actual={actual_abi_receipt_sha}",
        ),
        _check(
            "staged_names_match_lab_contract",
            staged_bundle.name == boot_trap_bundle_manifest.DEFAULT_BUNDLE_NAME
            and staged_replay.name == boot_trap_bundle_manifest.DEFAULT_REPLAY_NAME
            and staged_manifest.name == boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME,
            f"bundle={staged_bundle.name}; replay={staged_replay.name}; manifest={staged_manifest.name}",
        ),
        _check(
            "manifest_expected_targets_match",
            Path(manifest.get("bundle", {}).get("target_path", "")).name == staged_bundle.name
            and Path(manifest.get("replay_proof", {}).get("target_path", "")).name == staged_replay.name
            and Path(manifest.get("lab_mount", {}).get("manifest_target_path", "")).name == staged_manifest.name,
            "manifest target filenames match staged filenames",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]
    staged_files = [
        {
            "role": "trap_bundle",
            "source_path": str(bundle_path),
            "host_path": str(staged_bundle),
            "guest_path": manifest.get("bundle", {}).get("target_path", boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR + "/" + boot_trap_bundle_manifest.DEFAULT_BUNDLE_NAME),
            "sha256": actual_bundle_sha,
            "expected_sha256": expected_bundle_sha,
        },
        {
            "role": "replay_proof",
            "source_path": str(replay_proof_path),
            "host_path": str(staged_replay),
            "guest_path": manifest.get("replay_proof", {}).get("target_path", boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR + "/" + boot_trap_bundle_manifest.DEFAULT_REPLAY_NAME),
            "sha256": actual_replay_sha,
            "expected_sha256": expected_replay_sha,
        },
        {
            "role": "boot_trap_bundle_manifest",
            "source_path": str(boot_trap_manifest_path),
            "host_path": str(staged_manifest),
            "guest_path": manifest.get("lab_mount", {}).get("manifest_target_path", boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR + "/" + boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME),
            "sha256": actual_manifest_sha,
            "expected_sha256": source_manifest_sha,
        },
    ]
    if abi_receipt_provided:
        staged_files.append(
            {
                "role": "pgb2_trap_abi_boundary_receipt",
                "source_path": str(trap_abi_boundary_receipt_path or ""),
                "host_path": str(staged_abi_receipt),
                "guest_path": boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR + "/" + boot_trap_bundle_manifest.DEFAULT_ABI_BOUNDARY_RECEIPT_NAME,
                "sha256": actual_abi_receipt_sha,
                "expected_sha256": source_abi_receipt_sha,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "shared_folder": {
            "host_path": str(shared_dir),
            "mount_tag": mount_tag,
            "guest_mount_path": boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR,
            "qemu_args": qemu_args,
            "prepared_for_launch": perform_copy,
        },
        "staged_files": staged_files,
        "expected_guest_verification": {
            "command": manifest.get("lab_mount", {}).get("verify_command", ""),
            "result_path": manifest.get("lab_mount", {}).get("verification_result_path", ""),
            "expected_executed_instruction_count": int(manifest.get("summary", {}).get("expected_executed_instruction_count", 0) or 0),
            "expected_trapped_count": int(manifest.get("summary", {}).get("expected_trapped_count", 0) or 0),
            "expected_allowed_count": int(manifest.get("summary", {}).get("expected_allowed_count", 0) or 0),
            "abi_boundary_receipt_guest_path": boot_trap_bundle_manifest.DEFAULT_MOUNT_DIR + "/" + boot_trap_bundle_manifest.DEFAULT_ABI_BOUNDARY_RECEIPT_NAME if abi_receipt_provided else "",
            "expected_abi_boundary_status": str(abi_receipt.get("status", "")),
            "expected_abi_frozen": abi_boundary.get("abi_frozen") is True,
            "expected_kernel_abi_promotion_allowed": abi_boundary.get("kernel_abi_promotion_allowed") is True,
            "expected_kernel_enforcement_claimed": abi_boundary.get("kernel_enforcement_claimed") is True,
        },
        "checks": checks,
        "summary": {
            "staged_file_count": len(staged_files),
            "failed_check_count": len(failed),
            "perform_copy": perform_copy,
            "expected_executed_instruction_count": int(manifest.get("summary", {}).get("expected_executed_instruction_count", 0) or 0),
            "abi_boundary_receipt_staged": abi_receipt_provided,
            "expected_abi_boundary_status": str(abi_receipt.get("status", "")),
        },
        "limitations": [
            "This contract stages host files for QEMU; it does not prove QEMU launched or the guest mounted the folder.",
            "The QEMU -virtfs argument is recorded for launch tooling and may require guest 9p mount support.",
            "Boot enforcement remains unproven until serial boot evidence includes the lab input and ABI boundary verification markers.",
        ],
        "next_steps": [
            "Use run-pooleos-lab.ps1 with the staged shared folder and a real Lab image.",
            "Capture the serial log and boot_trap_bundle_verification.json after QEMU boot.",
            "Confirm POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS appears in captured serial evidence before relying on guest-observed ABI receipt continuity.",
        ],
    }


def write_contract(contract: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
