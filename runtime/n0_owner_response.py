"""Deterministic validation and receipt generation for the PooleOS N0 owner response."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from runtime import adr_ratification, n0_owner_decision_packet, native_v1_objectives
from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
RESPONSE_RELATIVE = "specs/n0-owner-response.json"
RESPONSE_SCHEMA_RELATIVE = "specs/n0-owner-response.schema.json"
RECEIPT_RELATIVE = "runs/n0_owner_response_receipt.json"
RECEIPT_SCHEMA_RELATIVE = "specs/n0-owner-response-receipt.schema.json"
RECEIPT_DOCUMENT_RELATIVE = "docs/n0-owner-response-receipt.md"

EXPECTED_SELECTIONS = {
    "adr_0003": "accept_exactly_as_written",
    "adr_0004": "accept_exactly_as_written",
    "workstation_v1_and_38_targets": "accept_exactly_as_written",
    "fido2_hardware_key_available": "do_not_have",
    "governance_key_profile": "hardware_fido2_ed25519_sk",
    "provisional_software_key_risk_accepted": "not_applicable",
    "public_key_publication": "not_yet",
}

NEGATIVE_CONTROL_IDS = (
    "N0-RESPONSE-NEG-STALE-PACKET",
    "N0-RESPONSE-NEG-MISSING-SELECTION",
    "N0-RESPONSE-NEG-UNRESOLVED-PLACEHOLDER",
    "N0-RESPONSE-NEG-INVALID-DISPOSITION",
    "N0-RESPONSE-NEG-PROVISIONAL-RISK-MISMATCH",
    "N0-RESPONSE-NEG-MEASUREMENT-OVERCLAIM",
    "N0-RESPONSE-NEG-UNDECLARED-AMENDMENT",
    "N0-RESPONSE-NEG-MISSING-CONFIRMATION",
    "N0-RESPONSE-NEG-PRIVATE-MATERIAL",
    "N0-RESPONSE-NEG-KEY-GENERATION-AUTHORIZATION",
    "N0-RESPONSE-NEG-PRIVATE-KEY-USE-AUTHORIZATION",
    "N0-RESPONSE-NEG-SIGNING-AUTHORIZATION",
    "N0-RESPONSE-NEG-MERGE-AUTHORIZATION",
    "N0-RESPONSE-NEG-TAGGING-AUTHORIZATION",
    "N0-RESPONSE-NEG-PUBLICATION-AUTHORIZATION",
    "N0-RESPONSE-NEG-PRODUCTION-PROMOTION",
)

FORBIDDEN_FIELD_NAMES = {
    "credential",
    "hardware_key_handle",
    "passphrase",
    "private_key",
    "private_key_material",
    "recovery_secret",
    "secret",
    "seed",
}


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _schema_errors(value: dict[str, Any], root: Path, relative: str) -> list[str]:
    schema = _read_json(root / relative)
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def _binding_only(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": binding["path"],
        "sha256": binding["sha256"],
        "byte_count": binding["byte_count"],
    }


def _forbidden_field_paths(value: object, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_FIELD_NAMES:
                paths.append(child_path)
            paths.extend(_forbidden_field_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_forbidden_field_paths(child, f"{path}[{index}]"))
    return paths


def _frozen_packet_errors(response: dict[str, Any], packet: dict[str, Any], raw: bytes, root: Path) -> list[str]:
    errors = _schema_errors(packet, root, n0_owner_decision_packet.PACKET_SCHEMA_RELATIVE)
    binding = response.get("decision_packet", {})
    if raw != canonical_json_bytes(packet):
        errors.append("decision packet is not canonical sorted UTF-8 JSON")
    if sha256_bytes(raw) != binding.get("sha256"):
        errors.append("decision packet SHA-256 does not match the owner response")
    if len(raw) != binding.get("byte_count"):
        errors.append("decision packet byte count does not match the owner response")
    if packet.get("source_set", {}).get("sha256") != binding.get("source_set_sha256"):
        errors.append("decision packet source-set digest does not match the owner response")
    if packet.get("decisions", {}).get("objectives", {}).get("target_set_sha256") != binding.get("target_set_sha256"):
        errors.append("decision packet target-set digest does not match the owner response")
    if packet.get("artifact_kind") != "pooleos_n0_owner_decision_packet":
        errors.append("bound decision packet has the wrong artifact kind")
    if packet.get("status") != "awaiting_owner_response":
        errors.append("historical decision packet must retain its pre-response status")
    for field in (
        "owner_acceptance_recorded",
        "signature_authorized",
        "publication_authorized",
        "production_promotion_allowed",
        "production_ready",
    ):
        if packet.get(field) is not False:
            errors.append(f"historical decision packet overclaims {field}")
    current = packet.get("current_state", {})
    if current.get("objective_target_count") != 38 or current.get("measured_target_count") != 0:
        errors.append("historical decision packet must bind 38 targets and zero measurements")
    fields = packet.get("owner_response_template", {}).get("fields", [])
    if len(fields) != 7 or any(item.get("selection") != n0_owner_decision_packet.UNSELECTED for item in fields):
        errors.append("historical decision packet must retain all seven unselected fields")
    validation = packet.get("validation", {})
    if validation.get("negative_control_count") != 12 or validation.get("negative_control_pass_count") != 12:
        errors.append("historical decision packet does not retain 12/12 controls")
    return errors


def response_rejection_reasons(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, RESPONSE_SCHEMA_RELATIVE)
    if value.get("selections") != EXPECTED_SELECTIONS:
        errors.append("response selections do not match the complete owner direction")
    if value.get("amendment_details") != "none":
        errors.append("exact acceptance cannot carry an undeclared amendment")
    confirmations = value.get("confirmations", {})
    if confirmations.get("definition_acceptance_is_not_measurement_acceptance") is not True:
        errors.append("definition-versus-measurement confirmation is required")
    if confirmations.get("no_key_generation_signing_merging_tagging_or_publication_authorized") is not True:
        errors.append("non-authorization confirmation is required")
    authorizations = value.get("execution_authorization", {})
    if not isinstance(authorizations, dict) or any(item is not False for item in authorizations.values()):
        errors.append("the response must not authorize a gated execution action")
    if value.get("production_promotion_allowed") is not False:
        errors.append("the response cannot grant production promotion")
    forbidden = _forbidden_field_paths(value)
    if forbidden:
        errors.append("response contains forbidden private-material fields: " + ", ".join(forbidden))

    selections = value.get("selections", {})
    selected_profile = selections.get("governance_key_profile")
    risk = selections.get("provisional_software_key_risk_accepted")
    if selected_profile == "passphrase_ed25519_provisional" and risk != "yes":
        errors.append("the provisional software profile requires explicit risk acceptance")
    if selected_profile in {"hardware_fido2_ed25519_sk", "hardware_fido2_ecdsa_sk"} and risk != "not_applicable":
        errors.append("hardware key profiles require software-key risk to be not_applicable")

    try:
        packet_path = root / n0_owner_decision_packet.PACKET_RELATIVE
        raw = packet_path.read_bytes()
        packet = json.loads(raw.decode("utf-8"))
        if not isinstance(packet, dict):
            raise ValueError("decision packet root is not an object")
        errors.extend(_frozen_packet_errors(value, packet, raw, root))
        template = {
            item["id"]: set(item["allowed_values"])
            for item in packet["owner_response_template"]["fields"]
        }
        field_map = {
            "adr_0003": "OWNER-ADR-0003-DISPOSITION",
            "adr_0004": "OWNER-ADR-0004-DISPOSITION",
            "workstation_v1_and_38_targets": "OWNER-OBJECTIVES-DISPOSITION-001",
            "fido2_hardware_key_available": "OWNER-FIDO2-HARDWARE-AVAILABILITY",
            "governance_key_profile": "OWNER-SIGNING-CUSTODY-001",
            "provisional_software_key_risk_accepted": "OWNER-PROVISIONAL-SOFTWARE-KEY-RISK-ACCEPTANCE",
            "public_key_publication": "OWNER-PUBLIC-KEY-PUBLICATION-001",
        }
        for key, template_id in field_map.items():
            if selections.get(key) not in template.get(template_id, set()):
                errors.append(f"{key} is not an allowed decision-packet selection")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        errors.append(f"bound decision packet cannot be validated: {type(error).__name__}: {error}")
    return sorted(set(errors))


def _pre_disposition_binding(packet: dict[str, Any], path: str) -> dict[str, Any]:
    binding = next((item for item in packet["source_set"]["bindings"] if item["path"] == path), None)
    if binding is None:
        raise ValueError(f"decision packet omits accepted source: {path}")
    return _binding_only(binding)


def _build_core(root: Path) -> dict[str, Any]:
    response_path = root / RESPONSE_RELATIVE
    response_raw = response_path.read_bytes()
    response = json.loads(response_raw.decode("utf-8"))
    if not isinstance(response, dict):
        raise ValueError("owner response root must be an object")
    if response_raw != canonical_json_bytes(response):
        raise ValueError("owner response source is not canonical sorted UTF-8 JSON")
    response_errors = response_rejection_reasons(response, root)
    if response_errors:
        raise ValueError("owner response is invalid: " + "; ".join(response_errors[:8]))

    packet_path = root / n0_owner_decision_packet.PACKET_RELATIVE
    packet_raw = packet_path.read_bytes()
    packet = json.loads(packet_raw.decode("utf-8"))
    if not isinstance(packet, dict):
        raise ValueError("decision packet root must be an object")

    adrs = {item["id"]: item for item in adr_ratification.parse_adr_set(root)}
    objectives = native_v1_objectives.read_json(root / native_v1_objectives.OBJECTIVES_RELATIVE)
    objective_errors = native_v1_objectives.rejection_reasons(objectives, root)
    if objective_errors:
        raise ValueError("live objectives source is invalid: " + "; ".join(objective_errors[:8]))
    objective_owner = objectives["owner_ratification"]
    measured_count = sum(target.get("evidence_status") != "not_measured" for target in objectives["targets"])
    signers, signer_errors = adr_ratification.parse_allowed_signers(root)
    if signer_errors:
        raise ValueError("public signer store is invalid: " + "; ".join(signer_errors))

    def live_adr(adr_id: str) -> dict[str, Any]:
        item = adrs[adr_id]
        return {
            "binding": _binding_only(item),
            "source_status": item["source_status"],
            "cryptographically_ratified": False,
        }

    execution = response["execution_authorization"]
    selections = response["selections"]
    receipt = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_n0_owner_response_receipt",
        "status_date": response["status_date"],
        "status": "owner_direction_recorded_hardware_key_unavailable",
        "selected_move_id": "N0-OWNER-RESPONSE-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "response_source": adr_ratification.bind_file(root, RESPONSE_RELATIVE),
        "decision_packet": {
            **adr_ratification.bind_file(root, n0_owner_decision_packet.PACKET_RELATIVE),
            "source_set_sha256": response["decision_packet"]["source_set_sha256"],
            "target_set_sha256": response["decision_packet"]["target_set_sha256"],
            "repository_commit": response["decision_packet"]["repository_commit"],
            "repository_tree": response["decision_packet"]["repository_tree"],
            "historical_snapshot_frozen": True,
        },
        "accepted_decisions": {
            "adr_0003": {
                "selection": selections["adr_0003"],
                "owner_direction_recorded": True,
                "pre_disposition_source": _pre_disposition_binding(packet, adrs["ADR-0003"]["path"]),
            },
            "adr_0004": {
                "selection": selections["adr_0004"],
                "owner_direction_recorded": True,
                "pre_disposition_source": _pre_disposition_binding(packet, adrs["ADR-0004"]["path"]),
            },
            "objectives": {
                "selection": selections["workstation_v1_and_38_targets"],
                "profile_id": objectives["release_profile"]["id"],
                "target_count": len(objectives["targets"]),
                "measured_target_count": measured_count,
                "target_set_sha256": response["decision_packet"]["target_set_sha256"],
                "definition_acceptance_recorded": True,
                "measurement_evidence_accepted": False,
                "pre_disposition_source": _pre_disposition_binding(packet, native_v1_objectives.OBJECTIVES_RELATIVE),
            },
            "custody": {
                "selected_profile": selections["governance_key_profile"],
                "hardware_key_availability": selections["fido2_hardware_key_available"],
                "provisional_software_key_risk": selections["provisional_software_key_risk_accepted"],
                "profile_selection_recorded": True,
                "key_generation_authorized": execution["key_generation"],
                "private_material_present": False,
            },
            "public_key_publication": {
                "selection": selections["public_key_publication"],
                "public_key_present": False,
                "publication_authorized": execution["publication"],
            },
        },
        "effective_source_state": {
            "adr_0003": live_adr("ADR-0003"),
            "adr_0004": live_adr("ADR-0004"),
            "objectives": {
                "binding": adr_ratification.bind_file(root, native_v1_objectives.OBJECTIVES_RELATIVE),
                "profile_accepted": objective_owner["profile_accepted"],
                "target_values_accepted": objective_owner["target_values_accepted"],
                "cryptographic_signature_present": objective_owner["cryptographic_signature_present"],
                "measured_target_count": measured_count,
            },
            "all_selected_source_dispositions_recorded": (
                adrs["ADR-0003"]["source_status"] == "accepted-owner-directed"
                and adrs["ADR-0004"]["source_status"] == "accepted-owner-directed"
                and objective_owner["profile_accepted"] is True
                and objective_owner["target_values_accepted"] is True
            ),
        },
        "trust_state": {
            "selected_key_profile": selections["governance_key_profile"],
            "hardware_key_available": False,
            "hardware_acquisition_required": True,
            "trusted_signer_count": len(signers),
            "public_key_present": False,
            "detached_signature_present": (root / adr_ratification.SIGNATURE_RELATIVE).is_file(),
            "signed_tag_present": False,
            "remote_publication_receipt_present": (root / adr_ratification.RECEIPT_RELATIVE).is_file(),
        },
        "execution_boundary": {
            "key_generation_authorized": execution["key_generation"],
            "private_key_use_authorized": execution["private_key_use"],
            "signing_authorized": execution["signing"],
            "merge_to_main_authorized": execution["merge_to_main"],
            "tagging_authorized": execution["tagging"],
            "publication_authorized": execution["publication"],
        },
        "owner_actions": [
            {
                "id": "OWNER-ADR-DISPOSITION-001",
                "status": "satisfied_owner_direction_recorded",
                "description": "ADR-0003 and ADR-0004 exact-acceptance direction is recorded in source status without a signature claim.",
            },
            {
                "id": "OWNER-OBJECTIVES-DISPOSITION-001",
                "status": "satisfied_definitions_only",
                "description": "The Workstation v1 profile and all 38 target definitions are accepted; every target remains unmeasured.",
            },
            {
                "id": "OWNER-SIGNING-CUSTODY-001",
                "status": "blocked_hardware_key_unavailable",
                "description": "hardware_fido2_ed25519_sk is selected, but the owner reports no FIDO2 hardware key is currently available.",
            },
            {
                "id": "OWNER-PUBLIC-KEY-PUBLICATION-001",
                "status": "deferred_by_owner",
                "description": "Public-key publication remains not_yet and no public key or fingerprint is recorded.",
            },
            {
                "id": "OWNER-KEY-GENERATION-001",
                "status": "not_authorized",
                "description": "Key generation or private-key use requires a separate explicit approval after compatible hardware is available.",
            },
            {
                "id": "OWNER-DETACHED-SIGN-001",
                "status": "not_authorized",
                "description": "No manifest signing is authorized or performed by this response.",
            },
            {
                "id": "OWNER-SIGNED-TAG-001",
                "status": "not_authorized",
                "description": "No signed architecture tag is authorized or present.",
            },
            {
                "id": "OWNER-PUBLISH-RECEIPT-001",
                "status": "not_authorized",
                "description": "Merge, public-key registration, tag publication, and release publication remain separately gated.",
            },
        ],
        "next_gate": {
            "move_id": "N0-HW-KEY-ACQUIRE-001",
            "blocked": True,
            "blocking_condition": "selected_fido2_hardware_key_not_available",
            "separate_approval_still_required": True,
            "owner_step": "Obtain a compatible FIDO2 security key; do not generate or register any key material until a separate explicit approval is recorded.",
        },
        "claim_boundary": [
            "This receipt validates an unsigned conversational owner-direction record; it is not an owner cryptographic signature.",
            "The historical decision packet remains byte-frozen with every original selection unselected so the reviewed input is not rewritten.",
            "Owner-directed source status does not satisfy the required detached-signature, signed-tag, or remote-publication gates.",
            "All 38 target definitions are accepted, but all 38 measurements remain open and zero targets are proven met.",
            "No public key, private key, key handle, passphrase, credential, recovery secret, signature, or publication receipt is present.",
            "The selected hardware-backed profile cannot be executed because the owner reports no FIDO2 hardware key is available.",
            "Key generation, private-key use, signing, merge to main, tagging, and publication each remain explicitly unauthorized.",
            "This receipt does not prove PooleBoot, PooleKernel, native services, PooleGlass, PooleGlyph, PDC backends, hardware support, or a production ISO.",
        ],
    }
    return receipt


def _run_negative_controls(response: dict[str, Any], root: Path) -> list[dict[str, str]]:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("N0-RESPONSE-NEG-STALE-PACKET", lambda value: value["decision_packet"].__setitem__("sha256", "0" * 64)),
        ("N0-RESPONSE-NEG-MISSING-SELECTION", lambda value: value["selections"].pop("adr_0004")),
        ("N0-RESPONSE-NEG-UNRESOLVED-PLACEHOLDER", lambda value: value["selections"].__setitem__("adr_0003", "UNSELECTED")),
        ("N0-RESPONSE-NEG-INVALID-DISPOSITION", lambda value: value["selections"].__setitem__("adr_0003", "reject")),
        ("N0-RESPONSE-NEG-PROVISIONAL-RISK-MISMATCH", lambda value: value["selections"].__setitem__("provisional_software_key_risk_accepted", "yes")),
        ("N0-RESPONSE-NEG-MEASUREMENT-OVERCLAIM", lambda value: value.__setitem__("measurement_evidence_accepted", True)),
        ("N0-RESPONSE-NEG-UNDECLARED-AMENDMENT", lambda value: value.__setitem__("amendment_details", "change ADR")),
        ("N0-RESPONSE-NEG-MISSING-CONFIRMATION", lambda value: value["confirmations"].__setitem__("definition_acceptance_is_not_measurement_acceptance", False)),
        ("N0-RESPONSE-NEG-PRIVATE-MATERIAL", lambda value: value.__setitem__("private_key_material", "FORBIDDEN")),
        ("N0-RESPONSE-NEG-KEY-GENERATION-AUTHORIZATION", lambda value: value["execution_authorization"].__setitem__("key_generation", True)),
        ("N0-RESPONSE-NEG-PRIVATE-KEY-USE-AUTHORIZATION", lambda value: value["execution_authorization"].__setitem__("private_key_use", True)),
        ("N0-RESPONSE-NEG-SIGNING-AUTHORIZATION", lambda value: value["execution_authorization"].__setitem__("signing", True)),
        ("N0-RESPONSE-NEG-MERGE-AUTHORIZATION", lambda value: value["execution_authorization"].__setitem__("merge_to_main", True)),
        ("N0-RESPONSE-NEG-TAGGING-AUTHORIZATION", lambda value: value["execution_authorization"].__setitem__("tagging", True)),
        ("N0-RESPONSE-NEG-PUBLICATION-AUTHORIZATION", lambda value: value["execution_authorization"].__setitem__("publication", True)),
        ("N0-RESPONSE-NEG-PRODUCTION-PROMOTION", lambda value: value.__setitem__("production_promotion_allowed", True)),
    ]
    if tuple(control_id for control_id, _ in mutations) != NEGATIVE_CONTROL_IDS:
        raise ValueError("negative-control implementation does not match the frozen inventory")
    results: list[dict[str, str]] = []
    for control_id, mutate in mutations:
        mutant = copy.deepcopy(response)
        mutate(mutant)
        rejected = bool(response_rejection_reasons(mutant, root))
        results.append(
            {
                "id": control_id,
                "status": "pass" if rejected else "fail",
                "expected": "reject",
                "observed": "reject" if rejected else "accept",
            }
        )
    return results


def receipt_rejection_reasons(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, RECEIPT_SCHEMA_RELATIVE)
    try:
        expected = _build_core(root)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        errors.append(f"live receipt regeneration failed: {type(error).__name__}: {error}")
    else:
        for key, expected_value in expected.items():
            if value.get(key) != expected_value:
                errors.append(f"{key} does not match the deterministic owner-response receipt")
    validation = value.get("validation", {})
    controls = validation.get("negative_controls", []) if isinstance(validation, dict) else []
    if validation.get("schema_and_semantics_valid") is not True:
        errors.append("validation must record schema_and_semantics_valid=true")
    if validation.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS):
        errors.append("negative-control count does not match the frozen inventory")
    if validation.get("negative_control_pass_count") != len(NEGATIVE_CONTROL_IDS):
        errors.append("not every owner-response negative control passed")
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("owner-response negative-control ordering or identifiers changed")
    if any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("an owner-response negative control is not passing")
    return sorted(set(errors))


def build_receipt(root: Path = ROOT) -> dict[str, Any]:
    response = _read_json(root / RESPONSE_RELATIVE)
    receipt = _build_core(root)
    controls = _run_negative_controls(response, root)
    receipt["validation"] = {
        "schema_and_semantics_valid": True,
        "negative_control_count": len(controls),
        "negative_control_pass_count": sum(item["status"] == "pass" for item in controls),
        "negative_controls": controls,
    }
    errors = receipt_rejection_reasons(receipt, root)
    if errors:
        raise ValueError("invalid N0 owner response receipt: " + "; ".join(errors[:8]))
    return receipt


def render_markdown(receipt: dict[str, Any], root: Path = ROOT) -> str:
    errors = receipt_rejection_reasons(receipt, root)
    if errors:
        raise ValueError("cannot render invalid owner-response receipt: " + "; ".join(errors[:8]))
    packet = receipt["decision_packet"]
    objectives = receipt["accepted_decisions"]["objectives"]
    trust = receipt["trust_state"]
    lines = [
        "# PooleOS N0 Owner Response Receipt",
        "",
        f"- Status date: {receipt['status_date']}",
        f"- Completed move: `{receipt['selected_move_id']}`",
        f"- Status: `{receipt['status']}`",
        "- Cryptographic owner signature: `false`",
        "- Production promotion: `false`",
        "",
        "## Frozen Input",
        "",
        f"The original unselected packet remains frozen at SHA-256 `{packet['sha256']}` and repository commit `{packet['repository_commit']}`.",
        f"It binds source-set SHA-256 `{packet['source_set_sha256']}` and target-set SHA-256 `{packet['target_set_sha256']}`.",
        "",
        "## Recorded Direction",
        "",
        "- `ADR-0003`: accept exactly as written; live source status is `accepted-owner-directed`.",
        "- `ADR-0004`: accept exactly as written; live source status is `accepted-owner-directed`.",
        f"- Workstation v1: accept `{objectives['target_count']}` target definitions; measured targets remain `{objectives['measured_target_count']}`.",
        "- Governance key: `hardware_fido2_ed25519_sk` selected; FIDO2 hardware key available: `false`.",
        "- Provisional software-key risk: `not_applicable`.",
        "- Public-key publication: `not_yet`.",
        "",
        "## Closed Authority Boundary",
        "",
        "No key generation, private-key use, signing, merge to main, tagging, or publication is authorized. No public or private key material is present.",
        "",
        "## Current Gate",
        "",
        f"- Trusted governance signers: `{trust['trusted_signer_count']}`.",
        "- Detached signature, signed tag, and remote publication receipt: all absent.",
        f"- Next move: `{receipt['next_gate']['move_id']}`; blocked because the selected hardware key is unavailable.",
        "- After compatible hardware is obtained, key generation still requires a separate explicit approval.",
        "",
        "## Owner Actions",
        "",
        "| ID | Status | Detail |",
        "|---|---|---|",
    ]
    for action in receipt["owner_actions"]:
        lines.append(f"| `{action['id']}` | `{action['status']}` | {action['description']} |")
    validation = receipt["validation"]
    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"All `{validation['negative_control_pass_count']}/{validation['negative_control_count']}` fail-closed response controls pass.",
            "",
            "## Claim Boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in receipt["claim_boundary"])
    return "\n".join(lines) + "\n"


def write_receipt(receipt: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(canonical_json_bytes(receipt))
    markdown_path.write_text(render_markdown(receipt), encoding="utf-8", newline="\n")
