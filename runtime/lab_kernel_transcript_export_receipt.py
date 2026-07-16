"""Receipt for lab-side kernel PGVM2 transcript exports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.2"
ARTIFACT_KIND = "pooleos.lab_kernel_transcript_export_receipt"
LOADER_OUTPUT_KIND = "pooleos.kernel_pgvm2_loader_output"
GUEST_ENV_MARKER = "POOLEOS_KERNEL_GUEST_ENV"
SOURCE_ANCHOR_ENV = "POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256"
PARSER_PROMOTION_ENV = "POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256"


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_count(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8-sig").splitlines())


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _claims(loader_output: dict[str, Any]) -> bool:
    return (
        loader_output.get("booted_kernel_path") is True
        or loader_output.get("kernel_enforcement_claimed") is True
        or loader_output.get("pgvm2_execution_claimed") is True
    )


def _infer_mode(loader_output: dict[str, Any]) -> str:
    status = str(loader_output.get("status", ""))
    if status == "pass" and _claims(loader_output):
        return "enabled"
    if status == "blocked" and not _claims(loader_output):
        return "disabled"
    return "unknown"


def _source(path: Path | None) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "sha256": _sha256(path),
        "line_count": _line_count(path),
    }


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def _guest_environment_values(path: Path) -> dict[str, list[str]]:
    values = {SOURCE_ANCHOR_ENV: [], PARSER_PROMOTION_ENV: []}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = raw_line.strip().split()
        if len(parts) == 3 and parts[0] == GUEST_ENV_MARKER and parts[1] in values:
            values[parts[1]].append(parts[2])
    return values


def _guest_environment_attestation(
    *,
    variable_name: str,
    observed_values: list[str],
    expected_value: str,
) -> dict[str, Any]:
    observed_value = observed_values[0] if len(observed_values) == 1 else ""
    valid_sha256 = _is_sha256(observed_value)
    return {
        "variable_name": variable_name,
        "transcript_marker": GUEST_ENV_MARKER,
        "occurrence_count": len(observed_values),
        "observed_value": observed_value,
        "expected_value": expected_value,
        "valid_sha256": valid_sha256,
        "matches_verifier": bool(valid_sha256 and _is_sha256(expected_value) and observed_value == expected_value),
    }


def make_lab_kernel_transcript_export_receipt(
    *,
    contract_source_path: Path,
    transcript_path: Path,
    kernel_loader_output_path: Path,
    contract_run_recorded: bool = False,
    contract_mode: str = "auto",
    operator_notes: str = "",
) -> dict[str, Any]:
    if contract_mode not in {"auto", "disabled", "enabled"}:
        raise ValueError(f"unsupported contract_mode: {contract_mode}")

    loader_output = _read_json(kernel_loader_output_path)
    loader_summary = loader_output.get("summary", {}) if isinstance(loader_output.get("summary"), dict) else {}
    transcript_claims = (
        loader_output.get("transcript_claims", {})
        if isinstance(loader_output.get("transcript_claims"), dict)
        else {}
    )
    transcript_export = _source(transcript_path)
    contract_source = _source(contract_source_path)
    output_exists = kernel_loader_output_path.exists()
    output_kind_valid = not output_exists or loader_output.get("artifact_kind") == LOADER_OUTPUT_KIND
    output_status = str(loader_output.get("status", ""))
    output_failed_count = _int(loader_summary.get("failed_check_count"))
    output_blocking_count = _int(loader_summary.get("blocking_check_count"))
    kernel_check_count = _int(loader_summary.get("kernel_check_count"))
    satisfied_kernel_check_count = _int(loader_summary.get("satisfied_kernel_check_count"))
    negative_claim_guard_held = loader_summary.get("negative_claim_guard_held") is True
    source_handoff_sha256 = str(loader_output.get("source_handoff_sha256", ""))
    source_anchor_sha256 = str(loader_output.get("pooleglyph_source_anchor_sha256", ""))
    parser_promotion_sha256 = str(loader_output.get("pooleglyph_parser_kernel_promotion_receipt_sha256", ""))
    output_digest_bound = all(
        _is_sha256(value)
        for value in (source_handoff_sha256, source_anchor_sha256, parser_promotion_sha256)
    )
    transcript_source = (
        loader_output.get("transcript_source", {})
        if isinstance(loader_output.get("transcript_source"), dict)
        else {}
    )
    verifier_transcript_sha256 = str(transcript_source.get("sha256", ""))
    transcript_digest_matches_verifier = bool(
        transcript_export["sha256"]
        and verifier_transcript_sha256 == transcript_export["sha256"]
    )
    guest_values = _guest_environment_values(transcript_path)
    guest_source_anchor = _guest_environment_attestation(
        variable_name=SOURCE_ANCHOR_ENV,
        observed_values=guest_values[SOURCE_ANCHOR_ENV],
        expected_value=source_anchor_sha256,
    )
    guest_parser_promotion = _guest_environment_attestation(
        variable_name=PARSER_PROMOTION_ENV,
        observed_values=guest_values[PARSER_PROMOTION_ENV],
        expected_value=parser_promotion_sha256,
    )
    guest_environment_digest_pair_attested = (
        guest_source_anchor["matches_verifier"] is True
        and guest_parser_promotion["matches_verifier"] is True
    )
    inferred_mode = _infer_mode(loader_output) if output_exists else "unknown"
    effective_mode = inferred_mode if contract_mode == "auto" else contract_mode
    claims = _claims(loader_output)
    output_accepted = (
        output_exists
        and output_kind_valid
        and output_status in {"blocked", "pass"}
        and output_failed_count == 0
        and negative_claim_guard_held
        and output_digest_bound
    )
    recorded_export_bound = (
        transcript_digest_matches_verifier
        and guest_environment_digest_pair_attested
    )
    disabled_verified = (
        bool(contract_run_recorded)
        and transcript_path.exists()
        and output_accepted
        and effective_mode == "disabled"
        and output_status == "blocked"
        and not claims
        and output_blocking_count > 0
        and recorded_export_bound
    )
    enabled_verified = (
        bool(contract_run_recorded)
        and transcript_path.exists()
        and output_accepted
        and effective_mode == "enabled"
        and output_status == "pass"
        and claims
        and output_blocking_count == 0
        and kernel_check_count >= 11
        and satisfied_kernel_check_count >= kernel_check_count
        and recorded_export_bound
    )
    verifier_accepted_export = disabled_verified or enabled_verified
    overclaim = (
        claims
        and not enabled_verified
        and (bool(contract_run_recorded) or output_status == "invalid")
    )
    kernel_enforcement_promotion_allowed = enabled_verified

    checks = [
        _check("codex_execution_not_performed", True, "codex_execution_performed=False"),
        _check("contract_source_present", contract_source_path.exists(), str(contract_source_path)),
        _check(
            "contract_run_recorded_or_pending",
            isinstance(contract_run_recorded, bool),
            f"contract_run_recorded={contract_run_recorded}",
        ),
        _check(
            "transcript_export_available_when_contract_run",
            (not contract_run_recorded) or transcript_path.exists(),
            str(transcript_path),
        ),
        _check(
            "loader_output_available_when_contract_run",
            (not contract_run_recorded) or output_exists,
            str(kernel_loader_output_path),
        ),
        _check(
            "loader_output_kind_valid_when_present",
            output_kind_valid,
            "pending loader output" if not output_exists else str(loader_output.get("artifact_kind", "")),
        ),
        _check(
            "loader_output_status_accepted_when_contract_run",
            (not contract_run_recorded) or output_accepted,
            f"status={output_status}; failed={output_failed_count}; negative_claim_guard={negative_claim_guard_held}",
        ),
        _check(
            "verifier_transcript_digest_bound_when_contract_run",
            (not contract_run_recorded) or transcript_digest_matches_verifier,
            f"transcript={transcript_export['sha256']}; verifier={verifier_transcript_sha256}",
        ),
        _check(
            "guest_source_anchor_environment_attested_when_contract_run",
            (not contract_run_recorded) or guest_source_anchor["matches_verifier"],
            (
                f"occurrences={guest_source_anchor['occurrence_count']}; "
                f"observed={guest_source_anchor['observed_value']}; expected={source_anchor_sha256}"
            ),
        ),
        _check(
            "guest_parser_promotion_environment_attested_when_contract_run",
            (not contract_run_recorded) or guest_parser_promotion["matches_verifier"],
            (
                f"occurrences={guest_parser_promotion['occurrence_count']}; "
                f"observed={guest_parser_promotion['observed_value']}; expected={parser_promotion_sha256}"
            ),
        ),
        _check(
            "guest_environment_digest_pair_matches_verifier_when_contract_run",
            (not contract_run_recorded) or guest_environment_digest_pair_attested,
            f"digest_pair_attested={guest_environment_digest_pair_attested}",
        ),
        _check(
            "no_enforcement_overclaim",
            not overclaim,
            f"claims={claims}; output_status={output_status}; effective_mode={effective_mode}",
        ),
        _check(
            "disabled_mode_non_claiming_when_verified",
            (not contract_run_recorded) or effective_mode != "disabled" or disabled_verified,
            f"mode={effective_mode}; status={output_status}; claims={claims}",
        ),
        _check(
            "enabled_mode_claims_only_when_pass",
            (not contract_run_recorded) or effective_mode != "enabled" or enabled_verified,
            f"mode={effective_mode}; status={output_status}; checks={satisfied_kernel_check_count}/{kernel_check_count}",
        ),
        _check(
            "kernel_promotion_blocked_unless_enabled_verified",
            kernel_enforcement_promotion_allowed is enabled_verified,
            f"promotion_allowed={kernel_enforcement_promotion_allowed}; enabled_verified={enabled_verified}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    if failed and (not contract_source_path.exists() or not output_kind_valid):
        status = "invalid"
    elif not contract_run_recorded:
        status = "pending_contract_run"
    elif enabled_verified:
        status = "enabled_verified"
    elif disabled_verified:
        status = "disabled_verified"
    else:
        status = "verification_failed"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "operator_executed": bool(contract_run_recorded),
        "contract_run_recorded": bool(contract_run_recorded),
        "codex_execution_performed": False,
        "contract_mode": contract_mode,
        "inferred_contract_mode": inferred_mode,
        "contract_source": contract_source,
        "transcript_export": transcript_export,
        "guest_environment": {
            "source_anchor": guest_source_anchor,
            "parser_promotion_receipt": guest_parser_promotion,
            "digest_pair_attested": guest_environment_digest_pair_attested,
        },
        "verifier_output": {
            "path": str(kernel_loader_output_path),
            "exists": output_exists,
            "sha256": _sha256(kernel_loader_output_path),
            "line_count": _line_count(kernel_loader_output_path),
            "artifact_kind": str(loader_output.get("artifact_kind", "")),
            "status": output_status,
            "booted_kernel_path": loader_output.get("booted_kernel_path") is True,
            "kernel_enforcement_claimed": loader_output.get("kernel_enforcement_claimed") is True,
            "pgvm2_execution_claimed": loader_output.get("pgvm2_execution_claimed") is True,
            "failed_check_count": output_failed_count,
            "blocking_check_count": output_blocking_count,
            "kernel_check_count": kernel_check_count,
            "satisfied_kernel_check_count": satisfied_kernel_check_count,
            "negative_claim_guard_held": negative_claim_guard_held,
            "source_handoff_sha256": source_handoff_sha256,
            "pooleglyph_source_anchor_sha256": source_anchor_sha256,
            "pooleglyph_parser_kernel_promotion_receipt_sha256": parser_promotion_sha256,
            "transcript_source_sha256": verifier_transcript_sha256,
            "transcript_claims": transcript_claims,
        },
        "guest_environment_digest_pair_attested": guest_environment_digest_pair_attested,
        "transcript_digest_matches_verifier": transcript_digest_matches_verifier,
        "verifier_accepted_export": verifier_accepted_export,
        "kernel_enforcement_promotion_allowed": kernel_enforcement_promotion_allowed,
        "operator_notes": operator_notes,
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "contract_run_recorded": bool(contract_run_recorded),
            "codex_execution_performed": False,
            "contract_mode": contract_mode,
            "inferred_contract_mode": inferred_mode,
            "transcript_exists": transcript_path.exists(),
            "verifier_output_exists": output_exists,
            "verifier_output_status": output_status,
            "transcript_digest_matches_verifier": transcript_digest_matches_verifier,
            "guest_environment_digest_pair_attested": guest_environment_digest_pair_attested,
            "verifier_accepted_export": verifier_accepted_export,
            "overclaim_detected": overclaim,
            "kernel_enforcement_promotion_allowed": kernel_enforcement_promotion_allowed,
        },
        "limitations": [
            "This receipt records transcript export continuity; it does not run the lab script or boot a kernel.",
            "pending_contract_run is non-claiming evidence that the receipt slot exists but no contract execution is recorded.",
            "Guest environment values are transcript-derived and accepted only when each audit marker occurs exactly once.",
            "disabled_verified proves a non-claiming transcript/export path only; it does not prove kernel PGVM2 enforcement.",
            "kernel_enforcement_promotion_allowed is true only for enabled_verified receipts backed by a pass loader output.",
        ],
        "next_steps": [
            "Run pooleos-kernel-pgvm2-transcript-contract in the Lab environment when a real kernel loader path exists.",
            "Run verify_kernel_pgvm2_loader_transcript.py against the exported transcript.",
            "Regenerate this receipt with --contract-run-recorded and the observed --contract-mode.",
        ],
    }


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
