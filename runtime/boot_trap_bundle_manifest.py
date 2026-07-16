"""Boot-readiness manifest for trap-bearing PGB2 lab inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime import pgb2_bundle
from runtime.schema_validation import validate_json


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.boot_trap_bundle_manifest"
VERIFICATION_KIND = "pooleos.boot_trap_bundle_verification"
DEFAULT_MOUNT_DIR = "/mnt/pooleos-output"
DEFAULT_BUNDLE_NAME = "input.pgb2.json"
DEFAULT_REPLAY_NAME = "input.replay.json"
DEFAULT_MANIFEST_NAME = "pooleos_boot_trap_bundle_manifest.json"
DEFAULT_ABI_BOUNDARY_RECEIPT_NAME = "pgb2_trap_abi_boundary_receipt.json"
DEFAULT_RESULT_PATH = "/var/lib/pooleos/runs/boot_trap_bundle_verification.json"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _target_path(mount_dir: str, name: str) -> str:
    return f"{mount_dir.rstrip('/')}/{name}"


def _section(bundle: dict[str, Any], name: str) -> dict[str, Any]:
    try:
        return pgb2_bundle.section_by_name(bundle, name)
    except Exception:
        return {}


def _schema_errors(value: dict[str, Any], schema_path: Path) -> list[str]:
    try:
        schema = _read_json(schema_path)
    except Exception as exc:
        return [f"schema read failed: {exc}"]
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def _trap_summary(execution: dict[str, Any]) -> dict[str, Any]:
    summary = execution.get("summary", {}) if isinstance(execution.get("summary", {}), dict) else {}
    program = execution.get("program", {}) if isinstance(execution.get("program", {}), dict) else {}
    return {
        "status": str(execution.get("status", "")),
        "program_sha256": str(program.get("sha256", "")),
        "byte_length": int(summary.get("byte_length", program.get("byte_length", 0)) or 0),
        "encoded_instruction_count": int(summary.get("encoded_instruction_count", 0) or 0),
        "executed_instruction_count": int(summary.get("executed_instruction_count", 0) or 0),
        "allowed_count": int(summary.get("allowed_count", 0) or 0),
        "trapped_count": int(summary.get("trapped_count", 0) or 0),
        "matrix_instruction_count": int(summary.get("matrix_instruction_count", 0) or 0),
        "fuzz_instruction_count": int(summary.get("fuzz_instruction_count", 0) or 0),
        "decode_error_count": int(summary.get("decode_error_count", 0) or 0),
        "outcome_mismatch_count": int(summary.get("outcome_mismatch_count", 0) or 0),
        "failed_check_count": int(summary.get("failed_check_count", 0) or 0),
        "security_boundary_claimed": execution.get("security_boundary_claimed") is True,
    }


def _abi_boundary_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    summary = receipt.get("summary", {}) if isinstance(receipt.get("summary"), dict) else {}
    boundary = receipt.get("abi_boundary", {}) if isinstance(receipt.get("abi_boundary"), dict) else {}
    claims = receipt.get("claim_boundaries", {}) if isinstance(receipt.get("claim_boundaries"), dict) else {}
    trap_execution = (
        receipt.get("evidence_sources", {}).get("trap_execution", {})
        if isinstance(receipt.get("evidence_sources"), dict)
        else {}
    )
    bundle = (
        receipt.get("evidence_sources", {}).get("bundle", {})
        if isinstance(receipt.get("evidence_sources"), dict)
        else {}
    )
    boot_manifest = (
        receipt.get("evidence_sources", {}).get("boot_trap_bundle_manifest", {})
        if isinstance(receipt.get("evidence_sources"), dict)
        else {}
    )
    return {
        "status": str(receipt.get("status", "")),
        "encoding_version": str(boundary.get("encoding_version", "")),
        "execution_version": str(boundary.get("execution_version", "")),
        "program_sha256": str(trap_execution.get("program_sha256", "")),
        "bundle_sha256": str(bundle.get("sha256", "")),
        "boot_manifest_sha256": str(boot_manifest.get("sha256", "")),
        "instruction_count": int(summary.get("instruction_count", 0) or 0),
        "byte_length": int(summary.get("byte_length", 0) or 0),
        "failed_check_count": int(summary.get("failed_check_count", 0) or 0),
        "source_overclaim_count": int(summary.get("source_overclaim_count", 0) or 0),
        "abi_frozen": boundary.get("abi_frozen") is True or summary.get("abi_frozen") is True,
        "kernel_abi_promotion_allowed": boundary.get("kernel_abi_promotion_allowed") is True
        or summary.get("kernel_abi_promotion_allowed") is True
        or claims.get("kernel_abi_promotion_allowed") is True,
        "kernel_enforcement_claimed": boundary.get("kernel_enforcement_claimed") is True
        or summary.get("kernel_enforcement_claimed") is True
        or claims.get("kernel_enforcement_claimed") is True,
        "security_boundary_claimed": boundary.get("security_boundary_claimed") is True,
        "draft_bytes_release_gate_usable": claims.get("draft_bytes_release_gate_usable") is True,
    }


def make_boot_trap_bundle_manifest(
    *,
    bundle_path: Path,
    replay_proof_path: Path,
    specs_dir: Path,
    trap_execution_path: Path | None = None,
    mount_dir: str = DEFAULT_MOUNT_DIR,
    bundle_target_path: str = "",
    replay_target_path: str = "",
    manifest_target_path: str = "",
    verification_result_path: str = DEFAULT_RESULT_PATH,
) -> dict[str, Any]:
    bundle = _read_json(bundle_path) if bundle_path.exists() else {}
    replay = _read_json(replay_proof_path) if replay_proof_path.exists() else {}
    trap_execution_file = _read_json(trap_execution_path) if trap_execution_path and trap_execution_path.exists() else {}
    trap_encoding_section = _section(bundle, "TRAP_ENCODING")
    trap_execution_section = _section(bundle, "TRAP_EXECUTION")
    embedded_trap_execution = trap_execution_section.get("body", {}) if isinstance(trap_execution_section.get("body"), dict) else {}
    trap_execution = trap_execution_file or embedded_trap_execution
    section_names = [str(section.get("name", "")) for section in bundle.get("sections", []) if isinstance(section, dict)]
    bundle_result = pgb2_bundle.validate_bundle(bundle, specs_dir=specs_dir) if bundle else pgb2_bundle.BundleValidationResult(False, ["missing bundle"])
    replay_errors = _schema_errors(replay, specs_dir / "replay-proof.schema.json") if replay else ["missing replay proof"]
    trap_errors = (
        _schema_errors(trap_execution, specs_dir / "pgb2-trap-execution.schema.json")
        if trap_execution
        else ["missing trap execution"]
    )
    bundle_sha = file_sha256(bundle_path)
    replay_sha = file_sha256(replay_proof_path)
    trap_section_sha = str(trap_execution_section.get("sha256", ""))
    embedded_body_hash = (
        pgb2_bundle.body_hash(embedded_trap_execution)
        if embedded_trap_execution
        else ""
    )
    external_body_hash = pgb2_bundle.body_hash(trap_execution_file) if trap_execution_file else embedded_body_hash
    trap = _trap_summary(trap_execution)

    bundle_target = bundle_target_path or _target_path(mount_dir, DEFAULT_BUNDLE_NAME)
    replay_target = replay_target_path or _target_path(mount_dir, DEFAULT_REPLAY_NAME)
    manifest_target = manifest_target_path or _target_path(mount_dir, DEFAULT_MANIFEST_NAME)

    checks = [
        _check("bundle_present", bundle_path.exists(), str(bundle_path)),
        _check("bundle_valid", bundle_result.ok, "valid" if bundle_result.ok else "; ".join(bundle_result.errors[:5])),
        _check("replay_present", replay_proof_path.exists(), str(replay_proof_path)),
        _check("replay_schema_valid", not replay_errors, "valid" if not replay_errors else "; ".join(replay_errors[:5])),
        _check(
            "replay_hash_matches_bundle",
            replay.get("bundle_sha256") == bundle_sha,
            f"replay={replay.get('bundle_sha256', '')}; bundle={bundle_sha}",
        ),
        _check(
            "trap_sections_present",
            "TRAP_ENCODING" in section_names and "TRAP_EXECUTION" in section_names,
            f"sections={section_names}",
        ),
        _check(
            "trap_execution_schema_valid",
            not trap_errors,
            "valid" if not trap_errors else "; ".join(trap_errors[:5]),
        ),
        _check(
            "trap_execution_matches_bundle_section",
            bool(trap_section_sha) and trap_section_sha == embedded_body_hash and external_body_hash == embedded_body_hash,
            f"section={trap_section_sha}; embedded={embedded_body_hash}; external={external_body_hash}",
        ),
        _check(
            "trap_execution_summary_ready",
            trap["status"] == "pass"
            and trap["failed_check_count"] == 0
            and trap["decode_error_count"] == 0
            and trap["outcome_mismatch_count"] == 0
            and trap["executed_instruction_count"] == trap["encoded_instruction_count"]
            and trap["executed_instruction_count"] > 0,
            f"status={trap['status']}; executed={trap['executed_instruction_count']}; outcomes={trap['outcome_mismatch_count']}",
        ),
        _check(
            "target_paths_match_lab_smoke",
            Path(bundle_target).name == DEFAULT_BUNDLE_NAME and Path(replay_target).name == DEFAULT_REPLAY_NAME,
            f"bundle={bundle_target}; replay={replay_target}",
        ),
        _check(
            "no_security_boundary_claimed",
            trap["security_boundary_claimed"] is False,
            f"security_boundary_claimed={trap['security_boundary_claimed']}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "manifest_role": "pooleos_lab_boot_trap_bundle_loader",
        "lab_mount": {
            "mount_dir": mount_dir,
            "bundle_target_path": bundle_target,
            "replay_target_path": replay_target,
            "manifest_target_path": manifest_target,
            "verification_result_path": verification_result_path,
            "smoke_command": "pooleos-lab-smoke",
            "verify_command": f"pooleos-lab-verify-input --manifest {manifest_target} --out {verification_result_path}",
        },
        "bundle": {
            "source_path": str(bundle_path),
            "target_path": bundle_target,
            "sha256": bundle_sha,
            "artifact_kind": str(bundle.get("artifact_kind", "")),
            "section_count": len(section_names),
            "section_names": section_names,
            "signed_metrics_present": "SIGNED_METRICS" in section_names,
            "trap_encoding_section_sha256": str(trap_encoding_section.get("sha256", "")),
            "trap_execution_section_sha256": trap_section_sha,
        },
        "replay_proof": {
            "source_path": str(replay_proof_path),
            "target_path": replay_target,
            "sha256": replay_sha,
            "bundle_sha256": str(replay.get("bundle_sha256", "")),
            "channel_summary_match": replay.get("channel_summary_match") is True,
            "signed_metrics_present": replay.get("signed_metrics_present") is True,
            "section_names": sorted(str(name) for name in replay.get("sections", {}).keys()) if isinstance(replay.get("sections"), dict) else [],
        },
        "trap_execution": {
            "source_path": str(trap_execution_path or ""),
            "embedded_in_bundle": bool(embedded_trap_execution),
            "section_sha256": trap_section_sha,
            "body_sha256": embedded_body_hash,
            "expected_summary": trap,
        },
        "checks": checks,
        "summary": {
            "bundle_section_count": len(section_names),
            "trap_evidence_present": "TRAP_ENCODING" in section_names and "TRAP_EXECUTION" in section_names,
            "expected_executed_instruction_count": trap["executed_instruction_count"],
            "expected_trapped_count": trap["trapped_count"],
            "expected_allowed_count": trap["allowed_count"],
            "failed_check_count": len(failed),
        },
        "limitations": [
            "This manifest prepares QEMU lab inputs but does not prove the lab image has booted.",
            "Trap execution remains draft byte-simulator evidence, not booted kernel enforcement.",
            "The mounted shared-folder paths must be populated by the operator or QEMU launch wrapper.",
        ],
        "next_steps": [
            "Copy the bundle, replay proof, and this manifest into the QEMU shared output mount.",
            "Run pooleos-lab-smoke inside the lab image and collect boot_trap_bundle_verification.json.",
            "Promote manifest verification into a boot-log marker once a real QEMU boot is available.",
        ],
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_mounted_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    bundle_path = Path(manifest.get("bundle", {}).get("target_path", ""))
    replay_path = Path(manifest.get("replay_proof", {}).get("target_path", ""))
    abi_receipt_path = manifest_path.parent / DEFAULT_ABI_BOUNDARY_RECEIPT_NAME
    expected_bundle_sha = str(manifest.get("bundle", {}).get("sha256", ""))
    expected_replay_sha = str(manifest.get("replay_proof", {}).get("sha256", ""))
    expected_trap = manifest.get("trap_execution", {}).get("expected_summary", {})
    checks = [
        _check("manifest_present", manifest_path.exists(), str(manifest_path)),
        _check("manifest_status_pass", manifest.get("status") == "pass", f"status={manifest.get('status', '')}"),
        _check("bundle_mounted", bundle_path.exists(), str(bundle_path)),
        _check("bundle_hash_matches", file_sha256(bundle_path) == expected_bundle_sha, f"expected={expected_bundle_sha}; actual={file_sha256(bundle_path)}"),
        _check("replay_mounted", replay_path.exists(), str(replay_path)),
        _check("replay_hash_matches", file_sha256(replay_path) == expected_replay_sha, f"expected={expected_replay_sha}; actual={file_sha256(replay_path)}"),
    ]
    bundle = _read_json(bundle_path) if bundle_path.is_file() else {}
    replay = _read_json(replay_path) if replay_path.is_file() else {}
    abi_receipt = _read_json(abi_receipt_path) if abi_receipt_path.is_file() else {}
    trap_execution = _section(bundle, "TRAP_EXECUTION").get("body", {}) if bundle else {}
    actual_trap = _trap_summary(trap_execution) if isinstance(trap_execution, dict) else {}
    abi_summary = _abi_boundary_summary(abi_receipt) if isinstance(abi_receipt, dict) else {}
    abi_present = bool(abi_receipt)
    abi_verified = (
        abi_present
        and abi_receipt.get("artifact_kind") == "pooleos.pgb2_trap_abi_boundary_receipt"
        and abi_summary.get("status") == "draft_verified"
        and abi_summary.get("failed_check_count") == 0
        and abi_summary.get("source_overclaim_count") == 0
        and abi_summary.get("abi_frozen") is False
        and abi_summary.get("kernel_abi_promotion_allowed") is False
        and abi_summary.get("kernel_enforcement_claimed") is False
        and abi_summary.get("security_boundary_claimed") is False
        and abi_summary.get("draft_bytes_release_gate_usable") is True
        and abi_summary.get("bundle_sha256") == expected_bundle_sha
        and abi_summary.get("boot_manifest_sha256") == file_sha256(manifest_path)
        and abi_summary.get("program_sha256") == actual_trap.get("program_sha256")
    )
    checks.extend(
        [
            _check(
                "replay_points_to_bundle",
                replay.get("bundle_sha256") == expected_bundle_sha,
                f"replay={replay.get('bundle_sha256', '')}; bundle={expected_bundle_sha}",
            ),
            _check(
                "bundle_has_trap_sections",
                bool(_section(bundle, "TRAP_ENCODING")) and bool(_section(bundle, "TRAP_EXECUTION")),
                "TRAP_ENCODING/TRAP_EXECUTION present" if bundle else "bundle missing",
            ),
            _check(
                "trap_summary_matches_manifest",
                actual_trap == expected_trap,
                f"expected={expected_trap}; actual={actual_trap}",
            ),
            _check(
                "trap_summary_passed",
                actual_trap.get("status") == "pass"
                and actual_trap.get("failed_check_count") == 0
                and actual_trap.get("outcome_mismatch_count") == 0
                and actual_trap.get("security_boundary_claimed") is False,
                f"status={actual_trap.get('status')}; failed={actual_trap.get('failed_check_count')}; outcomes={actual_trap.get('outcome_mismatch_count')}",
            ),
            _check(
                "abi_boundary_receipt_optional_or_mounted",
                (not abi_present) or abi_receipt_path.exists(),
                str(abi_receipt_path),
            ),
            _check(
                "abi_boundary_receipt_draft_verified_when_present",
                (not abi_present) or abi_verified,
                "not present" if not abi_present else f"status={abi_summary.get('status')}; promotion={abi_summary.get('kernel_abi_promotion_allowed')}",
            ),
        ]
    )
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": VERIFICATION_KIND,
        "status": "pass" if not failed else "fail",
        "manifest_path": str(manifest_path),
        "abi_boundary_receipt": {
            "path": str(abi_receipt_path),
            "exists": abi_receipt_path.exists(),
            "verified": abi_verified,
            "expected_name": DEFAULT_ABI_BOUNDARY_RECEIPT_NAME,
            "summary": abi_summary,
        },
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "failed_check_count": len(failed),
            "expected_executed_instruction_count": int(expected_trap.get("executed_instruction_count", 0) or 0)
            if isinstance(expected_trap, dict)
            else 0,
            "abi_boundary_receipt_present": abi_present,
            "abi_boundary_receipt_verified": abi_verified,
        },
    }


def write_verification(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
