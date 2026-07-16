"""Fail-closed validation for the candidate PooleOS Workstation v1 objectives."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
OBJECTIVES_RELATIVE = "specs/native-v1-objectives.json"
OBJECTIVES_SCHEMA_RELATIVE = "specs/native-v1-objectives.schema.json"
READINESS_RELATIVE = "runs/native_v1_objectives_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-v1-objectives-readiness.schema.json"
SOURCE_ADR_RELATIVE = "docs/adr/0005-v1-scope-mission-threats-and-non-goals.md"
RUNTIME_RELATIVE = "runtime/native_v1_objectives.py"

EXPECTED_CATEGORY_COUNTS = {
    "reliability": 7,
    "accessibility": 8,
    "compatibility": 6,
    "privacy": 7,
    "performance": 10,
}
EXPECTED_MODES = {
    "normal",
    "safe",
    "previous_known_good",
    "diagnostic",
    "live",
    "installer",
    "recovery",
}
PHASE_PATTERN = re.compile(r"^N(?:[0-9]|[1-3][0-9])$")


class ObjectivesError(RuntimeError):
    """Raised when the objectives contract is malformed or overclaims readiness."""


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def write_json(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ObjectivesError(f"JSON root must be an object: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ObjectivesError(f"binding escapes repository root: {relative}") from error
    data = path.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def schema_failures(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    from runtime.schema_validation import validate_json

    schema = read_json(root / OBJECTIVES_SCHEMA_RELATIVE)
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def _target_map(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    targets = value.get("targets", [])
    if not isinstance(targets, list):
        return {}
    return {
        str(target.get("id")): target
        for target in targets
        if isinstance(target, dict) and isinstance(target.get("id"), str)
    }

def semantic_violations(value: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    targets = value.get("targets", [])
    if not isinstance(targets, list):
        return ["targets must be an array"]

    target_objects = [target for target in targets if isinstance(target, dict)]
    ids = [str(target.get("id", "")) for target in target_objects]
    counts = Counter(str(target.get("category", "")) for target in target_objects)
    if len(target_objects) != 38:
        violations.append(f"target count must be 38, observed {len(target_objects)}")
    if len(ids) != len(set(ids)):
        violations.append("target identifiers must be unique")
    if dict(sorted(counts.items())) != dict(sorted(EXPECTED_CATEGORY_COUNTS.items())):
        violations.append(f"category counts must be {EXPECTED_CATEGORY_COUNTS}, observed {dict(counts)}")

    prefix_by_category = {
        "reliability": "REL-",
        "accessibility": "ACC-",
        "compatibility": "COMP-",
        "privacy": "PRIV-",
        "performance": "PERF-",
    }
    for target in target_objects:
        target_id = str(target.get("id", "<missing>"))
        category = str(target.get("category", ""))
        expected_prefix = prefix_by_category.get(category)
        if expected_prefix is None or not target_id.startswith(expected_prefix):
            violations.append(f"{target_id}: identifier/category mismatch")
        sample_count = target.get("minimum_sample_count")
        if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1:
            violations.append(f"{target_id}: minimum_sample_count must be positive")
        duration = target.get("minimum_duration_hours")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
            violations.append(f"{target_id}: minimum_duration_hours must be non-negative")
        percentile = target.get("percentile")
        if not isinstance(percentile, (int, float)) or isinstance(percentile, bool) or not 0 <= percentile <= 100:
            violations.append(f"{target_id}: percentile must be in [0, 100]")
        if target.get("definition_status") != "owner_direction_accepted_signature_pending":
            violations.append(f"{target_id}: definition status does not record the accepted owner direction")
        if target.get("evidence_status") != "not_measured":
            violations.append(f"{target_id}: evidence status must remain not_measured")
        phases = target.get("evidence_phase_ids", [])
        if not isinstance(phases, list) or not phases or any(not PHASE_PATTERN.fullmatch(str(phase)) for phase in phases):
            violations.append(f"{target_id}: evidence phases are missing or malformed")

    target_by_id = _target_map(value)

    def require_target(target_id: str) -> dict[str, Any]:
        target = target_by_id.get(target_id)
        if target is None:
            violations.append(f"required target missing: {target_id}")
            return {}
        return target

    telemetry = require_target("PRIV-TELEMETRY-DEFAULT-001")
    if telemetry and not (telemetry.get("operator") == "maximum" and telemetry.get("value") == 0):
        violations.append("telemetry must be disabled in every profile by default")
    preconsent = require_target("PRIV-PRECONSENT-NETWORK-001")
    if preconsent and not (preconsent.get("operator") == "maximum" and preconsent.get("value") == 0):
        violations.append("undeclared pre-consent outbound networking must have zero tolerance")
    linux = require_target("COMP-LINUX-ABI-001")
    if linux and not (linux.get("operator") == "maximum" and linux.get("value") == 0):
        violations.append("Linux ABI, module, or driver compatibility claims must remain prohibited")
    windows = require_target("COMP-WINDOWS-ABI-001")
    if windows and not (windows.get("operator") == "maximum" and windows.get("value") == 0):
        violations.append("Windows binary or driver compatibility claims must remain prohibited")
    recovery_access = require_target("ACC-RECOVERY-001")
    if recovery_access and recovery_access.get("value") != 100:
        violations.append("all required recovery workflows must retain declared accessibility fallbacks")
    wcag = require_target("ACC-WCAG-AA-001")
    if wcag and wcag.get("value") != 100:
        violations.append("all applicable WCAG 2.2 A/AA criteria must be mapped and passing")
    frame_p95 = require_target("PERF-FRAME-P95-001")
    if frame_p95 and frame_p95.get("percentile") != 95:
        violations.append("PERF-FRAME-P95-001 must use percentile 95")
    frame_p99 = require_target("PERF-FRAME-P99-001")
    if frame_p99 and frame_p99.get("percentile") != 99:
        violations.append("PERF-FRAME-P99-001 must use percentile 99")

    profile = value.get("release_profile", {})
    modes = set(profile.get("required_modes", [])) if isinstance(profile, dict) else set()
    if modes != EXPECTED_MODES:
        violations.append(f"required release modes must be {sorted(EXPECTED_MODES)}")
    compatibility = value.get("compatibility_policy", {})
    for field in ("linux_abi", "linux_kernel_modules", "windows_application_abi", "windows_drivers"):
        if not isinstance(compatibility, dict) or compatibility.get(field) != "prohibited_v1":
            violations.append(f"compatibility policy must prohibit {field}")
    if not isinstance(compatibility, dict) or compatibility.get("unknown_major_versions") != "reject":
        violations.append("unknown major versions must fail closed")

    measurement = value.get("measurement_policy", {})
    if not isinstance(measurement, dict) or measurement.get("independent_reproduction") is not True:
        violations.append("independent reproduction must be required")
    if not isinstance(measurement, dict) or measurement.get("raw_evidence_required") is not True:
        violations.append("raw measurement evidence must be retained")
    if not isinstance(measurement, dict) or not str(measurement.get("outlier_removal", "")).startswith("prohibited"):
        violations.append("silent outlier removal must be prohibited")

    owner = value.get("owner_ratification", {})
    if not isinstance(owner, dict) or owner.get("required") is not True:
        violations.append("owner ratification must be required")
    for field in ("profile_accepted", "target_values_accepted"):
        if not isinstance(owner, dict) or owner.get(field) is not True:
            violations.append(f"owner direction must remain recorded for: {field}")
    if not isinstance(owner, dict) or owner.get("cryptographic_signature_present") is not False:
        violations.append("owner direction must not be promoted to a cryptographic signature")
    if value.get("production_ready") is not False or value.get("production_promotion_allowed") is not False:
        violations.append("candidate objectives cannot enable production promotion")

    references = value.get("references", [])
    reference_ids = {item.get("id") for item in references if isinstance(item, dict)} if isinstance(references, list) else set()
    for required in ("REF-ADR-0005", "REF-WCAG-2.2", "REF-EN-301-549-3.2.1", "REF-NIST-PRIVACY-1.1"):
        if required not in reference_ids:
            violations.append(f"required reference missing: {required}")
    return sorted(set(violations))


def rejection_reasons(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    return schema_failures(value, root) + semantic_violations(value)


def _negative_controls(objectives: dict[str, Any], root: Path) -> list[dict[str, str]]:
    controls: list[tuple[str, Callable[[dict[str, Any]], None]]] = []

    def mutate_remove_reliability(value: dict[str, Any]) -> None:
        value["targets"] = [target for target in value["targets"] if target.get("category") != "reliability"]

    def mutate_duplicate_id(value: dict[str, Any]) -> None:
        value["targets"][1]["id"] = value["targets"][0]["id"]

    def mutate_zero_sample(value: dict[str, Any]) -> None:
        _target_map(value)["REL-T0-BOOT-001"]["minimum_sample_count"] = 0

    def mutate_bad_percentile(value: dict[str, Any]) -> None:
        _target_map(value)["PERF-FRAME-P95-001"]["percentile"] = 101

    def mutate_telemetry_default(value: dict[str, Any]) -> None:
        _target_map(value)["PRIV-TELEMETRY-DEFAULT-001"]["value"] = 1

    def mutate_linux_claim(value: dict[str, Any]) -> None:
        _target_map(value)["COMP-LINUX-ABI-001"]["value"] = 1

    def mutate_remove_recovery_access(value: dict[str, Any]) -> None:
        value["targets"] = [target for target in value["targets"] if target.get("id") != "ACC-RECOVERY-001"]

    def mutate_measured_without_evidence(value: dict[str, Any]) -> None:
        _target_map(value)["REL-SOAK-001"]["evidence_status"] = "pass"

    def mutate_promote(value: dict[str, Any]) -> None:
        value["production_promotion_allowed"] = True

    def mutate_remove_owner_acceptance(value: dict[str, Any]) -> None:
        value["owner_ratification"]["profile_accepted"] = False

    controls.extend(
        [
            ("reject_missing_target_family", mutate_remove_reliability),
            ("reject_duplicate_target_id", mutate_duplicate_id),
            ("reject_zero_sample_count", mutate_zero_sample),
            ("reject_impossible_percentile", mutate_bad_percentile),
            ("reject_telemetry_enabled_by_default", mutate_telemetry_default),
            ("reject_linux_compatibility_claim", mutate_linux_claim),
            ("reject_missing_recovery_accessibility", mutate_remove_recovery_access),
            ("reject_measured_status_without_evidence", mutate_measured_without_evidence),
            ("reject_candidate_production_promotion", mutate_promote),
            ("reject_owner_acceptance_regression", mutate_remove_owner_acceptance),
        ]
    )

    results: list[dict[str, str]] = []
    for control_id, mutate in controls:
        candidate = copy.deepcopy(objectives)
        mutate(candidate)
        observed = "reject" if rejection_reasons(candidate, root) else "accept"
        results.append(
            {
                "id": control_id,
                "expected": "reject",
                "observed": observed,
                "status": "pass" if observed == "reject" else "fail",
            }
        )
    return results


def build_readiness(root: Path = ROOT) -> dict[str, Any]:
    objectives = read_json(root / OBJECTIVES_RELATIVE)
    schema_issues = schema_failures(objectives, root)
    semantic_issues = semantic_violations(objectives)
    controls = _negative_controls(objectives, root)
    targets = [target for target in objectives.get("targets", []) if isinstance(target, dict)]
    counts = Counter(target.get("category") for target in targets)
    unmeasured = sorted(
        str(target.get("id")) for target in targets if target.get("evidence_status") == "not_measured"
    )
    consistency_pass = not schema_issues and not semantic_issues and all(item["status"] == "pass" for item in controls)
    owner = objectives["owner_ratification"]
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_v1_objectives_readiness",
        "status_date": objectives["status_date"],
        "status": "owner_direction_accepted_signature_pending" if consistency_pass else "invalid",
        "selected_move_id": objectives["selected_move_id"],
        "profile_id": objectives["release_profile"]["id"],
        "production_ready": False,
        "production_promotion_allowed": False,
        "n0_6_exit_gate_satisfied": False,
        "bindings": {
            "objectives": file_binding(root, OBJECTIVES_RELATIVE),
            "objectives_schema": file_binding(root, OBJECTIVES_SCHEMA_RELATIVE),
            "source_adr": file_binding(root, SOURCE_ADR_RELATIVE),
            "runtime": file_binding(root, RUNTIME_RELATIVE),
        },
        "validation": {
            "schema_failure_count": len(schema_issues),
            "schema_failures": schema_issues,
            "semantic_violation_count": len(semantic_issues),
            "semantic_violations": semantic_issues,
        },
        "target_coverage": {
            "target_count": len(targets),
            "category_counts": {category: counts[category] for category in EXPECTED_CATEGORY_COUNTS},
            "definition_pending_owner_count": sum(
                target.get("definition_status") == "candidate_owner_ratification_pending" for target in targets
            ),
            "measured_target_count": sum(target.get("evidence_status") != "not_measured" for target in targets),
            "unmeasured_target_ids": unmeasured,
        },
        "owner_boundary": {
            "ratification_required": owner["required"],
            "profile_accepted": owner["profile_accepted"],
            "target_values_accepted": owner["target_values_accepted"],
            "cryptographic_signature_present": owner["cryptographic_signature_present"],
            "ready_for_owner_review": False,
            "ready_for_signature": False,
        },
        "negative_controls": controls,
        "summary": {
            "consistency_pass": consistency_pass,
            "target_count": len(targets),
            "measured_target_count": sum(target.get("evidence_status") != "not_measured" for target in targets),
            "blocking_owner_action_count": 1,
            "negative_control_count": len(controls),
            "negative_control_pass_count": sum(item["status"] == "pass" for item in controls),
        },
        "open_items": objectives["open_items"],
        "claim_boundary": [
            "The profile and all 38 target definitions carry owner-directed acceptance but remain cryptographically unsigned.",
            "All 38 target definitions are unmeasured and satisfy no implementation, qualification, or release phase gate.",
            "Schema and semantic consistency do not prove reliability, accessibility, compatibility, privacy, or performance.",
            "The objectives ledger cannot authorize signatures, production promotion, hardware mutation, or destructive testing.",
            "Finite future samples remain bounded to their exact profiles, durations, workloads, firmware, and evidence.",
            "N0.6 and N0 remain partial until cryptographic ratification and implementation-bound evidence satisfy the Build Plan."
        ],
    }
