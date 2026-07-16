"""Kernel PGVM2 loader output fixtures and future booted output shape."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.kernel_pgvm2_loader_evidence import PLANNED_KERNEL_CHECKS


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.kernel_pgvm2_loader_output"


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _handoff_expected_count(handoff: dict[str, Any]) -> int:
    outputs = handoff.get("guest_loader_outputs", [])
    if not isinstance(outputs, list) or not outputs:
        return 0
    first = outputs[0] if isinstance(outputs[0], dict) else {}
    return _int(first.get("expected_executed_instruction_count"))


def _kernel_check(name: str, ok: bool, detail: str, observed_value: str | None = None) -> dict[str, Any]:
    planned = next((check for check in PLANNED_KERNEL_CHECKS if check["name"] == name), {})
    return {
        "name": name,
        "ok": bool(ok),
        "required_input": str(planned.get("required_input", "")),
        "observed_value": observed_value if observed_value is not None else ("satisfied" if ok else "pending"),
        "detail": detail,
    }


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "pass", "passed"}


def _transcript_source(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "sha256": "", "line_count": 0}
    return {
        "path": str(path),
        "exists": True,
        "sha256": _sha256(path),
        "line_count": len(path.read_text(encoding="utf-8-sig").splitlines()),
    }


def _parse_transcript(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "kernel_build_id": "",
        "source_handoff_sha256": "",
        "pooleglyph_source_anchor_sha256": "",
        "pooleglyph_parser_kernel_promotion_receipt_sha256": "",
        "booted_kernel_path": False,
        "kernel_enforcement_claimed": False,
        "pgvm2_execution_claimed": False,
        "expected_executed_instruction_count": 0,
        "actual_executed_instruction_count": 0,
        "kernel_checks": {},
    }
    if not path.exists():
        return parsed
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        marker = parts[0]
        if marker == "POOLEOS_KERNEL_BUILD_ID" and len(parts) >= 2:
            parsed["kernel_build_id"] = parts[1]
        elif marker == "POOLEOS_KERNEL_HANDOFF_SHA256" and len(parts) >= 2:
            parsed["source_handoff_sha256"] = parts[1]
        elif marker == "POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256" and len(parts) >= 2:
            parsed["pooleglyph_source_anchor_sha256"] = parts[1]
        elif marker == "POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256" and len(parts) >= 2:
            parsed["pooleglyph_parser_kernel_promotion_receipt_sha256"] = parts[1]
        elif marker == "POOLEOS_KERNEL_BOOTED_PATH" and len(parts) >= 2:
            parsed["booted_kernel_path"] = _bool(parts[1])
        elif marker == "POOLEOS_KERNEL_ENFORCEMENT_CLAIM" and len(parts) >= 2:
            parsed["kernel_enforcement_claimed"] = _bool(parts[1])
        elif marker == "POOLEOS_PGVM2_EXECUTION_CLAIM" and len(parts) >= 2:
            parsed["pgvm2_execution_claimed"] = _bool(parts[1])
        elif marker == "POOLEOS_KERNEL_EXPECTED_INSTRUCTIONS" and len(parts) >= 2:
            parsed["expected_executed_instruction_count"] = _int(parts[1])
        elif marker == "POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS" and len(parts) >= 2:
            parsed["actual_executed_instruction_count"] = _int(parts[1])
        elif marker == "POOLEOS_KERNEL_CHECK" and len(parts) >= 3:
            parsed["kernel_checks"][parts[1]] = _bool(parts[2])
    return parsed


def make_kernel_pgvm2_loader_output(
    *,
    kernel_boot_handoff_path: Path,
    pooleglyph_source_anchor_path: Path | None = None,
    parser_kernel_promotion_receipt_path: Path | None = None,
    kernel_build_id: str = "pending-kernel-loader",
    mode: str = "negative_fixture",
) -> dict[str, Any]:
    if mode not in {"negative_fixture", "synthetic_pass"}:
        raise ValueError(f"unsupported mode: {mode}")

    handoff = _read_json(kernel_boot_handoff_path)
    expected_count = _handoff_expected_count(handoff)
    handoff_sha256 = _sha256(kernel_boot_handoff_path)
    source_anchor_sha256 = _sha256(pooleglyph_source_anchor_path)
    parser_promotion_sha256 = _sha256(parser_kernel_promotion_receipt_path)
    synthetic_pass = mode == "synthetic_pass"
    booted_kernel_path = synthetic_pass
    kernel_enforcement_claimed = synthetic_pass
    actual_count = expected_count if synthetic_pass else 0

    checks: list[dict[str, Any]] = []
    for planned in PLANNED_KERNEL_CHECKS:
        name = planned["name"]
        ok = synthetic_pass or name == "negative_claim_guard"
        detail = (
            "synthetic booted kernel check satisfied"
            if synthetic_pass
            else "enforcement claim withheld until booted kernel evidence satisfies this check"
        )
        if name == "negative_claim_guard" and not synthetic_pass:
            detail = "enforcement claims are false while booted kernel evidence is pending"
        checks.append(_kernel_check(name, ok, detail))

    satisfied = sum(1 for check in checks if check["ok"])
    blocking = len(checks) - satisfied
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if synthetic_pass else "blocked",
        "booted_kernel_path": booted_kernel_path,
        "kernel_enforcement_claimed": kernel_enforcement_claimed,
        "pgvm2_execution_claimed": kernel_enforcement_claimed,
        "source_handoff_sha256": handoff_sha256,
        "pooleglyph_source_anchor_sha256": source_anchor_sha256,
        "pooleglyph_parser_kernel_promotion_receipt_sha256": parser_promotion_sha256,
        "kernel_build_id": kernel_build_id,
        "kernel_checks": checks,
        "summary": {
            "failed_check_count": 0,
            "blocking_check_count": blocking,
            "kernel_check_count": len(checks),
            "satisfied_kernel_check_count": satisfied,
            "expected_executed_instruction_count": expected_count,
            "actual_executed_instruction_count": actual_count,
            "enforcement_claim_allowed": synthetic_pass,
            "negative_claim_guard_held": (not kernel_enforcement_claimed) or satisfied == len(checks),
        },
        "limitations": [
            "negative_fixture mode is a schema and claim-guard fixture, not booted kernel evidence.",
            "kernel_enforcement_claimed stays false unless a booted kernel path satisfies every kernel check.",
            "synthetic_pass is for verifier tests only and must not be used as production boot evidence.",
        ],
    }


def make_kernel_pgvm2_loader_output_from_transcript(
    *,
    kernel_boot_handoff_path: Path,
    transcript_path: Path,
    pooleglyph_source_anchor_path: Path | None = None,
    parser_kernel_promotion_receipt_path: Path | None = None,
    kernel_build_id: str = "pending-kernel-loader",
) -> dict[str, Any]:
    handoff = _read_json(kernel_boot_handoff_path)
    expected_count = _handoff_expected_count(handoff)
    handoff_sha256 = _sha256(kernel_boot_handoff_path)
    source_anchor_sha256 = _sha256(pooleglyph_source_anchor_path)
    parser_promotion_sha256 = _sha256(parser_kernel_promotion_receipt_path)
    transcript = _parse_transcript(transcript_path)
    transcript_checks = transcript["kernel_checks"] if isinstance(transcript.get("kernel_checks"), dict) else {}
    transcript_handoff_sha256 = str(transcript.get("source_handoff_sha256", ""))
    transcript_source_anchor_sha256 = str(transcript.get("pooleglyph_source_anchor_sha256", ""))
    transcript_parser_promotion_sha256 = str(
        transcript.get("pooleglyph_parser_kernel_promotion_receipt_sha256", "")
    )
    transcript_expected_count = _int(transcript.get("expected_executed_instruction_count"))
    transcript_actual_count = _int(transcript.get("actual_executed_instruction_count"))
    transcript_build_id = str(transcript.get("kernel_build_id", "")) or kernel_build_id

    handoff_matches = bool(handoff_sha256 and transcript_handoff_sha256 == handoff_sha256)
    source_anchor_matches = bool(source_anchor_sha256 and transcript_source_anchor_sha256 == source_anchor_sha256)
    parser_promotion_matches = bool(
        parser_promotion_sha256 and transcript_parser_promotion_sha256 == parser_promotion_sha256
    )
    count_matches = expected_count > 0 and transcript_expected_count == expected_count and transcript_actual_count == expected_count
    booted_claim = transcript.get("booted_kernel_path") is True
    enforcement_claim = transcript.get("kernel_enforcement_claimed") is True
    pgvm2_claim = transcript.get("pgvm2_execution_claimed") is True

    checks: list[dict[str, Any]] = []
    for planned in PLANNED_KERNEL_CHECKS:
        name = planned["name"]
        transcript_check_ok = transcript_checks.get(name) is True
        if name == "handoff_digest_lock":
            ok = transcript_check_ok and handoff_matches
            detail = f"transcript_hash={transcript_handoff_sha256}; expected={handoff_sha256}"
            observed = "hash_match" if ok else "hash_missing_or_mismatch"
        elif name == "pooleglyph_source_anchor_digest_bind":
            ok = transcript_check_ok and source_anchor_matches
            detail = f"transcript_hash={transcript_source_anchor_sha256}; expected={source_anchor_sha256}"
            observed = "source_anchor_hash_match" if ok else "source_anchor_hash_missing_or_mismatch"
        elif name == "parser_promotion_receipt_digest_bind":
            ok = transcript_check_ok and parser_promotion_matches
            detail = f"transcript_hash={transcript_parser_promotion_sha256}; expected={parser_promotion_sha256}"
            observed = "parser_promotion_hash_match" if ok else "parser_promotion_hash_missing_or_mismatch"
        elif name == "trap_instruction_execution":
            ok = transcript_check_ok and count_matches
            detail = f"expected={transcript_expected_count}/{expected_count}; actual={transcript_actual_count}/{expected_count}"
            observed = "instruction_count_match" if ok else "instruction_count_missing_or_mismatch"
        elif name == "negative_claim_guard":
            non_guard_checks_ok = all(
                check["ok"] for check in checks if check["name"] != "negative_claim_guard"
            )
            ok = transcript_check_ok and ((not enforcement_claim and not pgvm2_claim) or non_guard_checks_ok)
            detail = f"claim={enforcement_claim or pgvm2_claim}; non_guard_checks_ok={non_guard_checks_ok}"
            observed = "claim_guard_held" if ok else "claim_guard_missing_or_failed"
        else:
            ok = transcript_check_ok
            detail = "transcript check passed" if ok else "missing or failed transcript check"
            observed = "transcript_pass" if ok else "transcript_missing_or_fail"
        checks.append(_kernel_check(name, ok, detail, observed))

    satisfied = sum(1 for check in checks if check["ok"])
    blocking = len(checks) - satisfied
    all_checks_ok = satisfied == len(checks)
    pass_ready = (
        transcript_path.exists()
        and booted_claim
        and enforcement_claim
        and pgvm2_claim
        and handoff_matches
        and source_anchor_matches
        and parser_promotion_matches
        and count_matches
        and all_checks_ok
    )
    contradictory_claim = (enforcement_claim or pgvm2_claim) and not pass_ready
    status = "pass" if pass_ready else "invalid" if contradictory_claim else "blocked"
    claimed = status == "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "booted_kernel_path": claimed,
        "kernel_enforcement_claimed": claimed,
        "pgvm2_execution_claimed": claimed,
        "source_handoff_sha256": handoff_sha256,
        "pooleglyph_source_anchor_sha256": source_anchor_sha256,
        "pooleglyph_parser_kernel_promotion_receipt_sha256": parser_promotion_sha256,
        "kernel_build_id": transcript_build_id,
        "kernel_checks": checks,
        "transcript_source": _transcript_source(transcript_path),
        "transcript_claims": {
            "kernel_build_id": transcript_build_id,
            "source_handoff_sha256": transcript_handoff_sha256,
            "pooleglyph_source_anchor_sha256": transcript_source_anchor_sha256,
            "pooleglyph_parser_kernel_promotion_receipt_sha256": transcript_parser_promotion_sha256,
            "booted_kernel_path": booted_claim,
            "kernel_enforcement_claimed": enforcement_claim,
            "pgvm2_execution_claimed": pgvm2_claim,
            "expected_executed_instruction_count": transcript_expected_count,
            "actual_executed_instruction_count": transcript_actual_count,
        },
        "summary": {
            "failed_check_count": 1 if contradictory_claim else 0,
            "blocking_check_count": blocking,
            "kernel_check_count": len(checks),
            "satisfied_kernel_check_count": satisfied,
            "expected_executed_instruction_count": expected_count,
            "actual_executed_instruction_count": transcript_actual_count if transcript_path.exists() else 0,
            "enforcement_claim_allowed": claimed,
            "negative_claim_guard_held": next(
                (check["ok"] for check in checks if check["name"] == "negative_claim_guard"),
                False,
            ),
        },
        "limitations": [
            "Transcript verification only promotes pass when every required kernel marker and check is present.",
            "Kernel and PGVM2 enforcement claims are withheld from the output unless the transcript is complete and self-consistent.",
            "This verifier consumes a transcript/export file; it does not itself boot a kernel.",
        ],
    }


def write_output(output: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
