"""ABI boundary receipt for draft PGB2 trap byte evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime import pgb2_bundle
from runtime import pgb2_trap_encoding
from runtime import pgb2_trap_execution


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pgb2_trap_abi_boundary_receipt"
BOUNDARY_VERSION = "PGB2_TRAP_ABI_BOUNDARY_V0"

BOOT_MANIFEST_KIND = "pooleos.boot_trap_bundle_manifest"
QEMU_CONTRACT_KIND = "pooleos.qemu_shared_folder_contract"

OVERCLAIM_KEYS = {
    "abi_frozen",
    "frozen_abi_claimed",
    "kernel_abi_promotion_allowed",
    "kernel_enforcement_claimed",
    "security_boundary_claimed",
}


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _source(path: Path | None, artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_path": str(path or ""),
        "exists": bool(path and path.exists()),
        "sha256": _sha256(path),
        "artifact_kind": str(artifact.get("artifact_kind", "")),
        "status": str(artifact.get("status", "")),
        "failed_check_count": _int(artifact.get("summary", {}).get("failed_check_count"))
        if isinstance(artifact.get("summary"), dict)
        else 0,
    }


def _claim_paths(value: Any, *, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}"
            if key in OVERCLAIM_KEYS and item is True:
                paths.append(child)
            paths.extend(_claim_paths(item, prefix=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_claim_paths(item, prefix=f"{prefix}[{index}]"))
    return paths


def _program_meta(artifact: dict[str, Any]) -> dict[str, Any]:
    program = artifact.get("program", {}) if isinstance(artifact.get("program"), dict) else {}
    summary = artifact.get("summary", {}) if isinstance(artifact.get("summary"), dict) else {}
    return {
        "sha256": str(program.get("sha256", "")),
        "byte_length": _int(program.get("byte_length", summary.get("byte_length"))),
        "instruction_count": _int(program.get("instruction_count", program.get("decoded_instruction_count"))),
    }


def _trap_execution_summary(execution: dict[str, Any]) -> dict[str, Any]:
    summary = execution.get("summary", {}) if isinstance(execution.get("summary"), dict) else {}
    program = execution.get("program", {}) if isinstance(execution.get("program"), dict) else {}
    encoding = execution.get("encoding_artifact", {}) if isinstance(execution.get("encoding_artifact"), dict) else {}
    return {
        "execution_version": str(execution.get("execution_version", "")),
        "encoding_version": str(encoding.get("encoding_version", "")),
        "encoded_instruction_count": _int(summary.get("encoded_instruction_count")),
        "executed_instruction_count": _int(summary.get("executed_instruction_count")),
        "byte_length": _int(summary.get("byte_length", program.get("byte_length"))),
        "program_sha256": str(program.get("sha256", "")),
        "decode_error_count": _int(summary.get("decode_error_count")),
        "outcome_mismatch_count": _int(summary.get("outcome_mismatch_count")),
        "failed_check_count": _int(summary.get("failed_check_count")),
        "security_boundary_claimed": execution.get("security_boundary_claimed") is True,
        "all_bytes_consumed": program.get("all_bytes_consumed") is True,
        "core_ir_binding_mode": str(encoding.get("core_ir_binding_mode", "")),
        "parser_to_kernel_promotion_allowed": encoding.get("parser_to_kernel_promotion_allowed") is True,
        "kernel_enforcement_claimed": encoding.get("kernel_enforcement_claimed") is True,
    }


def _bundle_section_hash(bundle: dict[str, Any], section_name: str) -> tuple[str, str, dict[str, Any]]:
    try:
        section = pgb2_bundle.section_by_name(bundle, section_name)
    except Exception:
        return "", "", {}
    body = section.get("body", {}) if isinstance(section.get("body"), dict) else {}
    return str(section.get("sha256", "")), pgb2_bundle.body_hash(body) if body else "", body


def make_pgb2_trap_abi_boundary_receipt(
    *,
    trap_encoding_path: Path,
    trap_execution_path: Path,
    bundle_path: Path,
    boot_trap_bundle_manifest_path: Path,
    qemu_shared_folder_contract_path: Path,
    specs_dir: Path,
) -> dict[str, Any]:
    encoding = _read_json(trap_encoding_path)
    execution = _read_json(trap_execution_path)
    bundle = _read_json(bundle_path)
    boot_manifest = _read_json(boot_trap_bundle_manifest_path)
    qemu_contract = _read_json(qemu_shared_folder_contract_path)

    encoding_summary = encoding.get("summary", {}) if isinstance(encoding.get("summary"), dict) else {}
    encoding_source = encoding.get("source_trap_proof", {}) if isinstance(encoding.get("source_trap_proof"), dict) else {}
    execution_summary = _trap_execution_summary(execution)
    execution_encoding = execution.get("encoding_artifact", {}) if isinstance(execution.get("encoding_artifact"), dict) else {}
    boot_summary = boot_manifest.get("summary", {}) if isinstance(boot_manifest.get("summary"), dict) else {}
    boot_trap = boot_manifest.get("trap_execution", {}).get("expected_summary", {}) if isinstance(boot_manifest.get("trap_execution"), dict) else {}
    qemu_summary = qemu_contract.get("summary", {}) if isinstance(qemu_contract.get("summary"), dict) else {}

    bundle_result = (
        pgb2_bundle.validate_bundle(bundle, specs_dir=specs_dir)
        if bundle
        else pgb2_bundle.BundleValidationResult(False, ["missing bundle"])
    )
    section_names = [str(section.get("name", "")) for section in bundle.get("sections", []) if isinstance(section, dict)]
    trap_encoding_section_sha, trap_encoding_body_sha, embedded_encoding = _bundle_section_hash(bundle, "TRAP_ENCODING")
    trap_execution_section_sha, trap_execution_body_sha, embedded_execution = _bundle_section_hash(bundle, "TRAP_EXECUTION")

    encoding_program = _program_meta(encoding)
    execution_program = _program_meta(execution)
    embedded_encoding_program = _program_meta(embedded_encoding)
    embedded_execution_summary = _trap_execution_summary(embedded_execution)
    staged_roles = {
        str(file.get("role", ""))
        for file in qemu_contract.get("staged_files", [])
        if isinstance(file, dict)
    }
    qemu_args = qemu_contract.get("shared_folder", {}).get("qemu_args", []) if isinstance(qemu_contract.get("shared_folder"), dict) else []

    source_overclaims: list[str] = []
    for label, artifact in (
        ("trap_encoding", encoding),
        ("trap_execution", execution),
        ("bundle", bundle),
        ("boot_trap_bundle_manifest", boot_manifest),
        ("qemu_shared_folder_contract", qemu_contract),
    ):
        source_overclaims.extend(f"{label}:{path}" for path in _claim_paths(artifact))

    checks = [
        _check("trap_encoding_present", trap_encoding_path.exists(), str(trap_encoding_path)),
        _check(
            "trap_encoding_kind_valid",
            encoding.get("artifact_kind") == pgb2_trap_encoding.ARTIFACT_KIND,
            str(encoding.get("artifact_kind", "")),
        ),
        _check(
            "trap_encoding_passed",
            encoding.get("status") == "pass" and _int(encoding_summary.get("failed_check_count")) == 0,
            f"status={encoding.get('status', '')}; failed={encoding_summary.get('failed_check_count', '')}",
        ),
        _check(
            "trap_encoding_version_is_draft",
            encoding.get("encoding_version") == pgb2_trap_encoding.ENCODING_VERSION,
            str(encoding.get("encoding_version", "")),
        ),
        _check(
            "trap_encoding_program_ready",
            encoding_program["instruction_count"] > 0 and encoding_program["byte_length"] > 0 and bool(encoding_program["sha256"]),
            f"instructions={encoding_program['instruction_count']}; bytes={encoding_program['byte_length']}",
        ),
        _check(
            "trap_encoding_source_non_claiming",
            encoding_source.get("kernel_enforcement_claimed") is False,
            f"kernel_enforcement_claimed={encoding_source.get('kernel_enforcement_claimed')}",
        ),
        _check("trap_execution_present", trap_execution_path.exists(), str(trap_execution_path)),
        _check(
            "trap_execution_kind_valid",
            execution.get("artifact_kind") == pgb2_trap_execution.ARTIFACT_KIND,
            str(execution.get("artifact_kind", "")),
        ),
        _check(
            "trap_execution_passed",
            execution.get("status") == "pass" and execution_summary["failed_check_count"] == 0,
            f"status={execution.get('status', '')}; failed={execution_summary['failed_check_count']}",
        ),
        _check(
            "trap_execution_version_is_draft",
            execution.get("execution_version") == pgb2_trap_execution.EXECUTION_VERSION,
            str(execution.get("execution_version", "")),
        ),
        _check(
            "trap_execution_matches_encoding_artifact",
            execution_encoding.get("encoding_version") == pgb2_trap_encoding.ENCODING_VERSION
            and _int(execution_encoding.get("instruction_count")) == encoding_program["instruction_count"]
            and _int(execution_encoding.get("byte_length")) == encoding_program["byte_length"]
            and str(execution_encoding.get("sha256", "")) == encoding_program["sha256"],
            (
                f"encoding_version={execution_encoding.get('encoding_version', '')}; "
                f"instructions={execution_encoding.get('instruction_count', '')}/{encoding_program['instruction_count']}; "
                f"bytes={execution_encoding.get('byte_length', '')}/{encoding_program['byte_length']}"
            ),
        ),
        _check(
            "trap_execution_program_matches_encoding",
            execution_program["sha256"] == encoding_program["sha256"]
            and execution_program["byte_length"] == encoding_program["byte_length"]
            and execution_summary["executed_instruction_count"] == encoding_program["instruction_count"]
            and execution_summary["encoded_instruction_count"] == encoding_program["instruction_count"],
            (
                f"encoding_sha={encoding_program['sha256']}; execution_sha={execution_program['sha256']}; "
                f"executed={execution_summary['executed_instruction_count']}; encoded={encoding_program['instruction_count']}"
            ),
        ),
        _check(
            "trap_execution_non_claiming",
            execution_summary["security_boundary_claimed"] is False and execution_summary["kernel_enforcement_claimed"] is False,
            (
                f"security_boundary_claimed={execution_summary['security_boundary_claimed']}; "
                f"kernel_enforcement_claimed={execution_summary['kernel_enforcement_claimed']}"
            ),
        ),
        _check(
            "trap_execution_no_decode_or_outcome_failures",
            execution_summary["decode_error_count"] == 0
            and execution_summary["outcome_mismatch_count"] == 0
            and execution_summary["all_bytes_consumed"] is True,
            (
                f"decode={execution_summary['decode_error_count']}; "
                f"outcomes={execution_summary['outcome_mismatch_count']}; "
                f"all_bytes={execution_summary['all_bytes_consumed']}"
            ),
        ),
        _check("bundle_present", bundle_path.exists(), str(bundle_path)),
        _check("bundle_valid", bundle_result.ok, "valid" if bundle_result.ok else "; ".join(bundle_result.errors[:5])),
        _check(
            "bundle_trap_sections_present",
            "TRAP_ENCODING" in section_names and "TRAP_EXECUTION" in section_names,
            f"sections={section_names}",
        ),
        _check(
            "bundle_section_hashes_match_bodies",
            trap_encoding_section_sha == trap_encoding_body_sha and trap_execution_section_sha == trap_execution_body_sha,
            f"encoding={trap_encoding_section_sha}/{trap_encoding_body_sha}; execution={trap_execution_section_sha}/{trap_execution_body_sha}",
        ),
        _check(
            "bundle_embedded_encoding_matches_external",
            embedded_encoding_program == encoding_program,
            f"embedded={embedded_encoding_program}; external={encoding_program}",
        ),
        _check(
            "bundle_embedded_execution_matches_external",
            embedded_execution_summary["program_sha256"] == execution_summary["program_sha256"]
            and embedded_execution_summary["executed_instruction_count"] == execution_summary["executed_instruction_count"]
            and embedded_execution_summary["security_boundary_claimed"] == execution_summary["security_boundary_claimed"],
            (
                f"embedded_sha={embedded_execution_summary['program_sha256']}; "
                f"external_sha={execution_summary['program_sha256']}"
            ),
        ),
        _check("boot_manifest_present", boot_trap_bundle_manifest_path.exists(), str(boot_trap_bundle_manifest_path)),
        _check(
            "boot_manifest_kind_valid",
            boot_manifest.get("artifact_kind") == BOOT_MANIFEST_KIND,
            str(boot_manifest.get("artifact_kind", "")),
        ),
        _check(
            "boot_manifest_passed",
            boot_manifest.get("status") == "pass" and _int(boot_summary.get("failed_check_count")) == 0,
            f"status={boot_manifest.get('status', '')}; failed={boot_summary.get('failed_check_count', '')}",
        ),
        _check(
            "boot_manifest_trap_summary_matches_execution",
            str(boot_trap.get("program_sha256", "")) == execution_summary["program_sha256"]
            and _int(boot_trap.get("executed_instruction_count")) == execution_summary["executed_instruction_count"]
            and _int(boot_trap.get("failed_check_count")) == 0
            and boot_trap.get("security_boundary_claimed") is False,
            f"boot_sha={boot_trap.get('program_sha256', '')}; execution_sha={execution_summary['program_sha256']}",
        ),
        _check("qemu_contract_present", qemu_shared_folder_contract_path.exists(), str(qemu_shared_folder_contract_path)),
        _check(
            "qemu_contract_kind_valid",
            qemu_contract.get("artifact_kind") == QEMU_CONTRACT_KIND,
            str(qemu_contract.get("artifact_kind", "")),
        ),
        _check(
            "qemu_contract_passed",
            qemu_contract.get("status") == "pass" and _int(qemu_summary.get("failed_check_count")) == 0,
            f"status={qemu_contract.get('status', '')}; failed={qemu_summary.get('failed_check_count', '')}",
        ),
        _check(
            "qemu_contract_stages_trap_bundle_inputs",
            _int(qemu_summary.get("staged_file_count")) >= 3
            and {"trap_bundle", "replay_proof", "boot_trap_bundle_manifest"}.issubset(staged_roles)
            and "-virtfs" in qemu_args,
            f"staged={qemu_summary.get('staged_file_count')}; roles={sorted(staged_roles)}",
        ),
        _check(
            "no_source_abi_or_kernel_overclaims",
            not source_overclaims,
            "none" if not source_overclaims else "; ".join(source_overclaims[:8]),
        ),
        _check(
            "receipt_keeps_kernel_abi_promotion_blocked",
            True,
            "kernel_abi_promotion_allowed=False; abi_frozen=False",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]
    missing_or_kind_failed = [
        check
        for check in checks
        if not check["ok"] and (check["name"].endswith("_present") or check["name"].endswith("_kind_valid"))
    ]

    if missing_or_kind_failed:
        status = "invalid"
    elif failed:
        status = "verification_failed"
    else:
        status = "draft_verified"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "boundary_version": BOUNDARY_VERSION,
        "abi_boundary": {
            "encoding_version": str(encoding.get("encoding_version", "")),
            "execution_version": str(execution.get("execution_version", "")),
            "byte_format_classification": "draft_trap_bytes",
            "abi_frozen": False,
            "kernel_abi_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
            "security_boundary_claimed": False,
        },
        "evidence_sources": {
            "trap_encoding": {
                **_source(trap_encoding_path, encoding),
                "encoding_version": str(encoding.get("encoding_version", "")),
                "program_sha256": encoding_program["sha256"],
                "instruction_count": encoding_program["instruction_count"],
                "byte_length": encoding_program["byte_length"],
                "matrix_bound": encoding_source.get("matrix_bound") is True,
                "fuzz_bound": encoding_source.get("fuzz_bound") is True,
                "core_ir_binding_mode": str(encoding_source.get("core_ir_binding_mode", "")),
                "parser_to_kernel_promotion_allowed": encoding_source.get("parser_to_kernel_promotion_allowed") is True,
                "kernel_enforcement_claimed": encoding_source.get("kernel_enforcement_claimed") is True,
            },
            "trap_execution": {
                **_source(trap_execution_path, execution),
                **execution_summary,
            },
            "bundle": {
                **_source(bundle_path, bundle),
                "section_names": section_names,
                "trap_encoding_section_sha256": trap_encoding_section_sha,
                "trap_execution_section_sha256": trap_execution_section_sha,
                "trap_encoding_body_sha256": trap_encoding_body_sha,
                "trap_execution_body_sha256": trap_execution_body_sha,
            },
            "boot_trap_bundle_manifest": {
                **_source(boot_trap_bundle_manifest_path, boot_manifest),
                "expected_program_sha256": str(boot_trap.get("program_sha256", "")),
                "expected_executed_instruction_count": _int(boot_trap.get("executed_instruction_count")),
                "security_boundary_claimed": boot_trap.get("security_boundary_claimed") is True,
            },
            "qemu_shared_folder_contract": {
                **_source(qemu_shared_folder_contract_path, qemu_contract),
                "staged_file_count": _int(qemu_summary.get("staged_file_count")),
                "perform_copy": qemu_summary.get("perform_copy") is True,
                "staged_roles": sorted(staged_roles),
                "qemu_mount_tag": str(qemu_contract.get("shared_folder", {}).get("mount_tag", ""))
                if isinstance(qemu_contract.get("shared_folder"), dict)
                else "",
            },
        },
        "claim_boundaries": {
            "source_overclaim_count": len(source_overclaims),
            "source_overclaim_paths": source_overclaims,
            "draft_bytes_release_gate_usable": status == "draft_verified",
            "abi_freeze_evidence_present": False,
            "kernel_abi_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
        },
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "source_overclaim_count": len(source_overclaims),
            "instruction_count": encoding_program["instruction_count"],
            "byte_length": encoding_program["byte_length"],
            "draft_encoding_version": pgb2_trap_encoding.ENCODING_VERSION,
            "draft_execution_version": pgb2_trap_execution.EXECUTION_VERSION,
            "bundle_trap_sections_present": "TRAP_ENCODING" in section_names and "TRAP_EXECUTION" in section_names,
            "boot_manifest_bound": boot_manifest.get("status") == "pass",
            "qemu_contract_bound": qemu_contract.get("status") == "pass",
            "abi_frozen": False,
            "kernel_abi_promotion_allowed": False,
            "kernel_enforcement_claimed": False,
        },
        "limitations": [
            "This receipt verifies continuity for PGB2_TRAP_DRAFT_V0 and PGB2_TRAP_EXEC_DRAFT_V0 only.",
            "Draft trap bytes may be release-gate evidence, but they are not a frozen PooleOS kernel ABI.",
            "QEMU shared-folder staging and boot-trap manifests do not prove a booted guest mounted or executed the artifacts.",
            "kernel_abi_promotion_allowed remains false until a future frozen ABI receipt is implemented and release-gated.",
        ],
        "next_steps": [
            "Run the same trap byte program inside a booted PooleOS Lab guest and collect serial-backed evidence.",
            "Define a frozen PGB2 trap ABI version only after kernel-owned trap handlers exist.",
            "Add a separate promotion receipt for frozen ABI evidence instead of upgrading draft byte evidence in place.",
        ],
    }


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
