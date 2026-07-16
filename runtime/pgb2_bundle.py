"""PGB2 draft JSON bundle helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema_validation import ValidationError, validate_json


BUNDLE_SCHEMA_VERSION = "0.1"
BUNDLE_KIND = "pooleos.pgb2_bundle"
CODE_MEDIA_TYPE = "application/vnd.pooleglyph.pgb1.raw-hex+json"
TRACE_MEDIA_TYPE = "application/vnd.pooleos.channel-trace+json"
CLAIM_MEDIA_TYPE = "application/vnd.pooleos.claim+json"
SIGNED_METRICS_MEDIA_TYPE = "application/vnd.pooleos.signed-membrane+json"
TRAP_ENCODING_MEDIA_TYPE = "application/vnd.pooleos.pgb2-trap-encoding+json"
TRAP_EXECUTION_MEDIA_TYPE = "application/vnd.pooleos.pgb2-trap-execution+json"


@dataclass(frozen=True)
class BundleValidationResult:
    ok: bool
    errors: list[str]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def body_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def make_section(name: str, media_type: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "media_type": media_type,
        "sha256": body_hash(body),
        "body": body,
    }


def make_trap_evidence_sections(
    *,
    trap_encoding: dict[str, Any],
    trap_execution: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        make_section("TRAP_ENCODING", TRAP_ENCODING_MEDIA_TYPE, trap_encoding),
        make_section("TRAP_EXECUTION", TRAP_EXECUTION_MEDIA_TYPE, trap_execution),
    ]


def make_code_body(*, raw_hex: str, source_label: str) -> dict[str, Any]:
    normalized = " ".join(raw_hex.strip().upper().split())
    bytes.fromhex(normalized)
    return {
        "encoding": "PGB1_RAW_HEX",
        "source_label": source_label,
        "raw_hex": normalized,
    }


def make_bundle(
    *,
    code_body: dict[str, Any],
    trace_artifact: dict[str, Any],
    extra_sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    claim = trace_artifact["claim"]
    sections = [
        make_section("CODE", CODE_MEDIA_TYPE, code_body),
        make_section("TRACE", TRACE_MEDIA_TYPE, trace_artifact),
        make_section("CLAIM_LANE", CLAIM_MEDIA_TYPE, claim),
    ]
    if extra_sections:
        sections.extend(extra_sections)
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "artifact_kind": BUNDLE_KIND,
        "header": {
            "magic": "PGB2",
            "compatibility": ["PGB1"],
            "byte_order": "little",
        },
        "sections": sections,
    }


def write_bundle(bundle: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def section_by_name(bundle: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [section for section in bundle.get("sections", []) if section.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} section, found {len(matches)}")
    return matches[0]


def _schema_errors(value: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: list[ValidationError] = validate_json(value, schema)
    return [f"{error.path}: {error.message}" for error in errors]


def validate_bundle(bundle: dict[str, Any], *, specs_dir: Path) -> BundleValidationResult:
    errors: list[str] = []
    errors.extend(_schema_errors(bundle, specs_dir / "pgb2-bundle.schema.json"))

    section_names = [section.get("name") for section in bundle.get("sections", [])]
    for required in ("CODE", "TRACE", "CLAIM_LANE"):
        if section_names.count(required) != 1:
            errors.append(f"expected exactly one {required} section")

    for section in bundle.get("sections", []):
        body = section.get("body")
        expected = section.get("sha256")
        if isinstance(body, dict) and isinstance(expected, str):
            actual = body_hash(body)
            if actual != expected:
                errors.append(f"{section.get('name')}: sha256 mismatch")

    try:
        code = section_by_name(bundle, "CODE")["body"]
        if code.get("encoding") != "PGB1_RAW_HEX":
            errors.append("CODE: unsupported encoding")
        else:
            bytes.fromhex(code.get("raw_hex", ""))
    except Exception as exc:
        errors.append(f"CODE: invalid raw hex: {exc}")

    try:
        trace = section_by_name(bundle, "TRACE")["body"]
        errors.extend(f"TRACE {msg}" for msg in _schema_errors(trace, specs_dir / "channel-trace.schema.json"))
    except Exception as exc:
        errors.append(f"TRACE: {exc}")

    try:
        claim = section_by_name(bundle, "CLAIM_LANE")["body"]
        errors.extend(f"CLAIM_LANE {msg}" for msg in _schema_errors(claim, specs_dir / "claim-lanes.schema.json"))
        trace_claim = section_by_name(bundle, "TRACE")["body"].get("claim")
        if claim != trace_claim:
            errors.append("CLAIM_LANE: does not match trace claim")
    except Exception as exc:
        errors.append(f"CLAIM_LANE: {exc}")

    signed_sections = [section for section in bundle.get("sections", []) if section.get("name") == "SIGNED_METRICS"]
    for section in signed_sections:
        try:
            errors.extend(
                f"SIGNED_METRICS {msg}"
                for msg in _schema_errors(section["body"], specs_dir / "signed-membrane.schema.json")
            )
        except Exception as exc:
            errors.append(f"SIGNED_METRICS: {exc}")

    trap_encoding_sections = [section for section in bundle.get("sections", []) if section.get("name") == "TRAP_ENCODING"]
    trap_execution_sections = [section for section in bundle.get("sections", []) if section.get("name") == "TRAP_EXECUTION"]
    if len(trap_encoding_sections) > 1:
        errors.append("TRAP_ENCODING: expected at most one section")
    if len(trap_execution_sections) > 1:
        errors.append("TRAP_EXECUTION: expected at most one section")
    if len(trap_encoding_sections) != len(trap_execution_sections):
        errors.append("TRAP_EVIDENCE: TRAP_ENCODING and TRAP_EXECUTION must appear together")

    trap_encoding_body: dict[str, Any] | None = None
    trap_execution_body: dict[str, Any] | None = None
    if trap_encoding_sections:
        section = trap_encoding_sections[0]
        if section.get("media_type") != TRAP_ENCODING_MEDIA_TYPE:
            errors.append("TRAP_ENCODING: unexpected media type")
        try:
            body = section["body"]
            if not isinstance(body, dict):
                errors.append("TRAP_ENCODING: body is not an object")
                body = {}
            trap_encoding_body = body
            errors.extend(
                f"TRAP_ENCODING {msg}"
                for msg in _schema_errors(trap_encoding_body, specs_dir / "pgb2-trap-encoding.schema.json")
            )
            if trap_encoding_body.get("status") != "pass":
                errors.append(f"TRAP_ENCODING: status={trap_encoding_body.get('status')}")
            if trap_encoding_body.get("summary", {}).get("failed_check_count") != 0:
                errors.append("TRAP_ENCODING: failed checks present")
        except Exception as exc:
            errors.append(f"TRAP_ENCODING: {exc}")

    if trap_execution_sections:
        section = trap_execution_sections[0]
        if section.get("media_type") != TRAP_EXECUTION_MEDIA_TYPE:
            errors.append("TRAP_EXECUTION: unexpected media type")
        try:
            body = section["body"]
            if not isinstance(body, dict):
                errors.append("TRAP_EXECUTION: body is not an object")
                body = {}
            trap_execution_body = body
            errors.extend(
                f"TRAP_EXECUTION {msg}"
                for msg in _schema_errors(trap_execution_body, specs_dir / "pgb2-trap-execution.schema.json")
            )
            if trap_execution_body.get("status") != "pass":
                errors.append(f"TRAP_EXECUTION: status={trap_execution_body.get('status')}")
            if trap_execution_body.get("summary", {}).get("failed_check_count") != 0:
                errors.append("TRAP_EXECUTION: failed checks present")
            if trap_execution_body.get("security_boundary_claimed") is not False:
                errors.append("TRAP_EXECUTION: must not claim a security boundary")
        except Exception as exc:
            errors.append(f"TRAP_EXECUTION: {exc}")

    if trap_encoding_body and trap_execution_body:
        encoding_program = trap_encoding_body.get("program", {})
        execution_program = trap_execution_body.get("program", {})
        execution_encoding = trap_execution_body.get("encoding_artifact", {})
        if encoding_program.get("sha256") != execution_program.get("sha256"):
            errors.append("TRAP_EVIDENCE: execution program hash does not match encoding program hash")
        if encoding_program.get("sha256") != execution_encoding.get("sha256"):
            errors.append("TRAP_EVIDENCE: execution encoding hash does not match encoding program hash")
        if encoding_program.get("byte_length") != execution_program.get("byte_length"):
            errors.append("TRAP_EVIDENCE: execution byte length does not match encoding byte length")
        if encoding_program.get("byte_length") != execution_encoding.get("byte_length"):
            errors.append("TRAP_EVIDENCE: execution encoding byte length does not match encoding byte length")
        if encoding_program.get("instruction_count") != execution_program.get("decoded_instruction_count"):
            errors.append("TRAP_EVIDENCE: executed instruction count does not match encoded instruction count")
        if encoding_program.get("instruction_count") != execution_encoding.get("instruction_count"):
            errors.append("TRAP_EVIDENCE: execution encoding instruction count does not match encoding count")
        if trap_execution_body.get("program", {}).get("all_bytes_consumed") is not True:
            errors.append("TRAP_EVIDENCE: execution did not consume all bytes")
        if trap_execution_body.get("summary", {}).get("outcome_mismatch_count") != 0:
            errors.append("TRAP_EVIDENCE: execution outcome mismatches present")

    return BundleValidationResult(ok=not errors, errors=errors)
