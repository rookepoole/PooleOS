"""Deterministic, non-promoting N0 owner decision packet for PooleOS."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from runtime import adr_ratification, native_v1_objectives
from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
PACKET_RELATIVE = "runs/n0_owner_decision_packet.json"
PACKET_SCHEMA_RELATIVE = "specs/n0-owner-decision-packet.schema.json"
PACKET_DOCUMENT_RELATIVE = "docs/n0-owner-decision-packet.md"
CEREMONY_RELATIVE = "docs/adr-ratification-ceremony.md"
CONSTITUTION_RELATIVE = "specs/native-architecture-constitution.json"
OWNER_RESPONSE_RELATIVE = "specs/n0-owner-response.json"

DISPOSITIONS = ["accept_exactly_as_written", "amend_before_acceptance", "reject_and_supersede"]
OBJECTIVE_DISPOSITIONS = ["accept_exactly_as_written", "amend_before_acceptance", "reject"]
HARDWARE_AVAILABILITY_OPTIONS = ["have", "do_not_have", "unsure"]
PROVISIONAL_KEY_RISK_OPTIONS = ["yes", "no", "not_applicable"]
PUBLIC_KEY_OPTIONS = ["approve_after_fingerprint_review", "not_yet"]
UNSELECTED = "UNSELECTED"

NEGATIVE_CONTROL_IDS = (
    "N0-PACKET-NEG-STALE-SOURCE",
    "N0-PACKET-NEG-MISSING-ADR",
    "N0-PACKET-NEG-MISSING-TARGET",
    "N0-PACKET-NEG-CHANGED-TARGET",
    "N0-PACKET-NEG-MEASUREMENT-OVERCLAIM",
    "N0-PACKET-NEG-INFERRED-ACCEPTANCE",
    "N0-PACKET-NEG-INFERRED-KEY-SELECTION",
    "N0-PACKET-NEG-PRIVATE-MATERIAL",
    "N0-PACKET-NEG-SIGNING-AUTHORIZATION",
    "N0-PACKET-NEG-PUBLICATION-AUTHORIZATION",
    "N0-PACKET-NEG-PRODUCTION-PROMOTION",
    "N0-PACKET-NEG-DROPPED-OWNER-ACTION",
)


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _source_paths(policy: dict[str, Any]) -> list[str]:
    paths = [f"docs/adr/{name}" for name in adr_ratification.ADR_NAMES]
    paths.extend(policy["required_bound_sources"])
    paths.extend(
        [
            adr_ratification.POLICY_RELATIVE,
            adr_ratification.READINESS_RELATIVE,
            CEREMONY_RELATIVE,
        ]
    )
    return list(dict.fromkeys(paths))


def _target_snapshot(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": target["id"],
        "category": target["category"],
        "metric": target["metric"],
        "operator": target["operator"],
        "value": target["value"],
        "unit": target["unit"],
        "minimum_sample_count": target["minimum_sample_count"],
        "minimum_duration_hours": target["minimum_duration_hours"],
        "percentile": target["percentile"],
        "zero_tolerance": target["zero_tolerance"],
        "applies_to": target["applies_to"],
        "evidence_phase_ids": target["evidence_phase_ids"],
        "evidence_requirement": target["evidence_requirement"],
        "definition_status": target["definition_status"],
        "evidence_status": target["evidence_status"],
    }


def _decision_source(adrs: dict[str, dict[str, Any]], adr_id: str) -> dict[str, Any]:
    item = adrs[adr_id]
    return {
        "id": item["id"],
        "title": item["title"],
        "path": item["path"],
        "sha256": item["sha256"],
        "byte_count": item["byte_count"],
        "source_status": item["source_status"],
        "source_ratification": item["source_ratification"],
    }


def _build_core(root: Path) -> dict[str, Any]:
    policy = adr_ratification.load_policy(root)
    readiness = adr_ratification.build_readiness(root)
    readiness_path = root / adr_ratification.READINESS_RELATIVE
    if readiness_path.read_bytes() != canonical_json_bytes(readiness):
        raise ValueError("stored ADR readiness is not the exact deterministic regeneration")

    objectives = _read_json(root / native_v1_objectives.OBJECTIVES_RELATIVE)
    objective_errors = native_v1_objectives.rejection_reasons(objectives, root)
    if objective_errors:
        raise ValueError("native v1 objectives are invalid: " + "; ".join(objective_errors[:8]))

    constitution = _read_json(root / CONSTITUTION_RELATIVE)
    parsed_adrs = {item["id"]: item for item in adr_ratification.parse_adr_set(root)}
    source_bindings = [adr_ratification.bind_file(root, path) for path in _source_paths(policy)]
    source_set_sha256 = sha256_bytes(canonical_json_bytes(source_bindings))
    targets = [_target_snapshot(target) for target in objectives["targets"]]
    category_counts = [
        {"category": category, "count": count}
        for category, count in sorted(Counter(target["category"] for target in targets).items())
    ]
    objective_target_set_sha256 = sha256_bytes(canonical_json_bytes(targets))

    owner_actions = [
        {
            "id": action["id"],
            "status": action["status"],
            "description": action["description"],
        }
        for action in readiness["owner_actions"]
    ]

    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_n0_owner_decision_packet",
        "packet_version": "1.0.0",
        "status_date": policy["status_date"],
        "status": "awaiting_owner_response",
        "selected_move_id": "N0-RATIFY-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "owner_acceptance_recorded": False,
        "signature_authorized": False,
        "publication_authorized": False,
        "source_set": {
            "binding_count": len(source_bindings),
            "sha256": source_set_sha256,
            "bindings": source_bindings,
        },
        "current_state": {
            "ready_for_owner_action": readiness["summary"]["ready_for_owner_action"],
            "ready_for_signature": readiness["summary"]["ready_for_signature"],
            "pending_owner_action_count": sum(action["status"] == "pending" for action in owner_actions),
            "pending_owner_actions": owner_actions,
            "proposed_adr_ids": readiness["adr_set"]["pending_owner_disposition"],
            "trusted_signer_count": readiness["trust_bootstrap"]["trusted_signer_count"],
            "objective_target_count": readiness["summary"]["objectives_target_count"],
            "measured_target_count": readiness["summary"]["objectives_measured_target_count"],
            "owner_acceptance_pending": readiness["summary"]["objectives_owner_acceptance_pending"],
        },
        "decisions": {
            "adr_0003": {
                "decision_id": "OWNER-ADR-0003-DISPOSITION",
                "status": "pending_owner_selection",
                "selection": UNSELECTED,
                "source": _decision_source(parsed_adrs, "ADR-0003"),
                "question": "Adopt the proposed implementation-language and toolchain split?",
                "available_dispositions": DISPOSITIONS,
                "recommendation": "accept_exactly_as_written",
                "recommendation_is_advisory": True,
                "plain_language_summary": "Use Rust 2024 no_std for PooleBoot, PooleKernel, privileged services, and drivers; keep assembly minimal; use freestanding C17 for portable PDC and ABI probes; and keep Python outside production images as a host oracle and harness.",
                "recommendation_basis": [
                    "The split reduces memory-safety exposure in privileged code while keeping explicit stable wire and disk ABIs.",
                    "The one-host Rust and LLD qualification already exercises the selected PE32+ and ELF64 target families without claiming a functional boot.",
                    "C17 remains available for independent portable PDC and ABI checks, and Python cannot become a production-image dependency.",
                ],
                "tradeoffs": [
                    "Rust, LLVM, LLD, core, alloc, and compiler builtins become reviewed external build inputs.",
                    "Unsafe Rust, assembly, generated bindings, and C interoperability require continuing inventory and independent ABI fixtures.",
                    "A later language change requires a reviewed superseding ADR and new toolchain evidence.",
                ],
                "structured_snapshot": constitution["language_split"],
            },
            "adr_0004": {
                "decision_id": "OWNER-ADR-0004-DISPOSITION",
                "status": "pending_owner_selection",
                "selection": UNSELECTED,
                "source": _decision_source(parsed_adrs, "ADR-0004"),
                "question": "Adopt the proposed product names and independent version namespaces?",
                "available_dispositions": DISPOSITIONS,
                "recommendation": "accept_exactly_as_written",
                "recommendation_is_advisory": True,
                "plain_language_summary": "Keep PooleOS component names coherent while versioning boot, kernel, syscall, IPC, driver, filesystem, package, update, recovery, desktop, receipt, crash, PGB2, and PGVM2 contracts independently.",
                "recommendation_basis": [
                    "Independent namespaces prevent an unrelated product version from silently changing wire, disk, recovery, or executable compatibility.",
                    "The names match the native architecture constitution and the current PooleGlyph PGB2 and PGVM2 integration boundary.",
                    "Unknown major versions fail closed and persistent layouts never use the unstable native Rust ABI.",
                ],
                "tradeoffs": [
                    "Each public namespace needs its own compatibility, migration, test-corpus, and deprecation policy.",
                    "Renaming a namespace after publication requires explicit migration and compatibility handling.",
                    "PGB2 and PGVM2 remain unfrozen until PooleGlyph Phase 66 and later N34 evidence pass.",
                ],
                "structured_snapshot": {
                    "core_names": {
                        "product": constitution["architecture"]["product"],
                        "bootloader": constitution["architecture"]["bootloader"],
                        "kernel": constitution["architecture"]["kernel"],
                    },
                    "component_names": constitution["component_names"],
                    "version_namespaces": constitution["version_namespaces"],
                },
            },
            "objectives": {
                "decision_id": "OWNER-OBJECTIVES-DISPOSITION-001",
                "status": "pending_owner_selection",
                "selection": UNSELECTED,
                "question": "Adopt the candidate PooleOS Workstation v1 profile and all 38 target definitions?",
                "available_dispositions": OBJECTIVE_DISPOSITIONS,
                "recommendation": "accept_exactly_as_written",
                "recommendation_is_advisory": True,
                "plain_language_summary": "Freeze a measurable workstation release profile across reliability, accessibility, compatibility, privacy, and performance without claiming that any target has been measured or met.",
                "recommendation_basis": [
                    "The targets are explicit, testable, evidence-bound, and fail closed instead of relying on broad quality claims.",
                    "Acceptance freezes definitions only; all 38 implementation measurements remain open.",
                    "Future evidence may justify a reviewed amendment, but measurements must not be weakened after results are observed merely to manufacture a pass.",
                ],
                "tradeoffs": [
                    "The reliability and fault-injection sample counts require substantial lab and automation time.",
                    "Accessibility and privacy targets apply to installer and recovery paths, not only the normal desktop.",
                    "Performance gates require retained raw distributions and exact hardware, firmware, workload, and clock bindings.",
                ],
                "profile": objectives["release_profile"],
                "threat_model": objectives["threat_model"],
                "compatibility_policy": objectives["compatibility_policy"],
                "measurement_policy": objectives["measurement_policy"],
                "category_counts": category_counts,
                "target_count": len(targets),
                "measured_target_count": sum(target["evidence_status"] != "not_measured" for target in targets),
                "target_set_sha256": objective_target_set_sha256,
                "targets": targets,
                "measurement_evidence_accepted": False,
            },
            "custody": {
                "decision_id": "OWNER-SIGNING-CUSTODY-001",
                "status": "pending_owner_selection",
                "selection": UNSELECTED,
                "hardware_key_availability": UNSELECTED,
                "hardware_key_availability_options": HARDWARE_AVAILABILITY_OPTIONS,
                "provisional_software_key_risk_acceptance": UNSELECTED,
                "provisional_software_key_risk_acceptance_options": PROVISIONAL_KEY_RISK_OPTIONS,
                "question": "Which owner-controlled governance-key profile will protect architecture ratification?",
                "available_profiles": policy["signature"]["key_profiles"],
                "recommendation": "hardware_fido2_ed25519_sk",
                "recommendation_is_advisory": True,
                "recommendation_basis": [
                    "The recommended profile keeps private signing operations hardware-backed and owner-presence gated.",
                    "A passphrase Ed25519 software key is an explicit provisional fallback and requires separate risk acceptance.",
                    "Governance signing remains separate from future Secure Boot, package, update, recovery, and ISO release keys.",
                ],
                "custody_rules": policy["custody"],
                "private_material_included": False,
                "private_material_requested": False,
            },
            "public_key_publication": {
                "decision_id": "OWNER-PUBLIC-KEY-PUBLICATION-001",
                "status": "pending_owner_selection",
                "selection": UNSELECTED,
                "question": "After independently reviewing the generated fingerprint, may Codex publish only the public key and fingerprint to the repository and GitHub signing-key registry?",
                "available_dispositions": PUBLIC_KEY_OPTIONS,
                "recommendation": "approve_after_fingerprint_review",
                "recommendation_is_advisory": True,
                "private_material_included": False,
                "registration_scope_may_require_interactive_owner_approval": True,
            },
        },
        "execution_boundary": {
            "standing_authority_recorded": True,
            "standing_authority_allows": [
                "read_edit_build_test_and_document_pooleos",
                "install_workspace_local_non_administrative_tools",
                "update_roadmap_and_evidence_artifacts",
                "create_commits_and_topic_branches",
                "push_topic_branches",
                "open_or_update_pull_requests",
            ],
            "separate_explicit_approval_required": [
                "merge_to_main",
                "change_repository_governance",
                "generate_or_use_private_keys",
                "sign_or_publish_tags_or_releases",
                "run_privileged_hardware_probes",
                "load_drivers",
                "modify_firmware",
                "write_physical_media_or_disks",
            ],
            "prohibited_in_this_packet_cycle": [
                "owner_acceptance_inference",
                "private_key_generation_or_access",
                "manifest_signing",
                "tag_creation_or_signing",
                "merge_to_main",
                "publication_receipt",
                "repository_governance_change",
                "privileged_or_destructive_hardware_action",
            ],
        },
        "owner_response_template": {
            "response_status": "UNFILLED",
            "fields": [
                {
                    "id": "OWNER-ADR-0003-DISPOSITION",
                    "selection": UNSELECTED,
                    "allowed_values": DISPOSITIONS,
                },
                {
                    "id": "OWNER-ADR-0004-DISPOSITION",
                    "selection": UNSELECTED,
                    "allowed_values": DISPOSITIONS,
                },
                {
                    "id": "OWNER-OBJECTIVES-DISPOSITION-001",
                    "selection": UNSELECTED,
                    "allowed_values": OBJECTIVE_DISPOSITIONS,
                },
                {
                    "id": "OWNER-FIDO2-HARDWARE-AVAILABILITY",
                    "selection": UNSELECTED,
                    "allowed_values": HARDWARE_AVAILABILITY_OPTIONS,
                },
                {
                    "id": "OWNER-SIGNING-CUSTODY-001",
                    "selection": UNSELECTED,
                    "allowed_values": [profile["id"] for profile in policy["signature"]["key_profiles"]],
                },
                {
                    "id": "OWNER-PROVISIONAL-SOFTWARE-KEY-RISK-ACCEPTANCE",
                    "selection": UNSELECTED,
                    "allowed_values": PROVISIONAL_KEY_RISK_OPTIONS,
                    "consistency_rule": "yes is required only for passphrase_ed25519_provisional; hardware profiles require not_applicable",
                },
                {
                    "id": "OWNER-PUBLIC-KEY-PUBLICATION-001",
                    "selection": UNSELECTED,
                    "allowed_values": PUBLIC_KEY_OPTIONS,
                },
            ],
            "amendment_details": "UNFILLED",
            "understanding_confirmations": [
                "Definition acceptance does not accept measurements or claim that PooleOS meets any target.",
                "This response does not authorize key generation, signing, merging, tagging, or publication.",
                "Any amendment or rejection stops manifest preparation until revised sources are reviewed again.",
            ],
        },
        "claim_boundary": [
            "This packet is unsigned preparation evidence and is not owner acceptance or cryptographic ratification.",
            "Recommendations are advisory; every owner selection remains explicitly unselected.",
            "All 38 objective definitions are listed, but all 38 implementation measurements remain open.",
            "No public key, private key, credential, recovery secret, hardware-key stub, signature, tag, or publication receipt is included.",
            "The packet does not authorize Codex to merge, sign, publish, change governance, probe privileged hardware, load a driver, modify firmware, or write physical media.",
            "Architecture disposition does not prove PooleBoot, PooleKernel, native services, PooleGlass, PGB2, PGVM2, PDC backends, or a production ISO.",
        ],
    }


def _core_rejection_reasons(value: dict[str, Any], root: Path) -> list[str]:
    try:
        expected = _build_core(root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return [f"live source regeneration failed: {type(error).__name__}: {error}"]

    errors: list[str] = []
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            errors.append(f"{key} does not match the exact live decision-packet source")
    return errors


def _frozen_packet_rejection_reasons(value: dict[str, Any], root: Path) -> list[str]:
    """Validate the accepted pre-response packet without comparing it to changed live sources."""
    errors: list[str] = []
    try:
        response = _read_json(root / OWNER_RESPONSE_RELATIVE)
        binding = response["decision_packet"]
        stored_raw = (root / PACKET_RELATIVE).read_bytes()
        stored = json.loads(stored_raw.decode("utf-8"))
        if not isinstance(stored, dict):
            raise ValueError("stored decision packet root is not an object")
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError) as error:
        return [f"frozen packet binding is unavailable: {type(error).__name__}: {error}"]

    candidate_raw = canonical_json_bytes(value)
    if binding.get("path") != PACKET_RELATIVE:
        errors.append("owner response binds an unexpected decision-packet path")
    if sha256_bytes(candidate_raw) != binding.get("sha256"):
        errors.append("packet does not match the owner-accepted historical SHA-256")
    if len(candidate_raw) != binding.get("byte_count"):
        errors.append("packet does not match the owner-accepted historical byte count")
    if stored_raw != canonical_json_bytes(stored):
        errors.append("stored historical packet is not canonical JSON")
    if sha256_bytes(stored_raw) != binding.get("sha256"):
        errors.append("stored historical packet digest does not match the owner response")
    if value != stored:
        errors.append("packet differs from the frozen historical packet artifact")
    if value.get("source_set", {}).get("sha256") != binding.get("source_set_sha256"):
        errors.append("packet source-set digest differs from the owner response")
    if value.get("decisions", {}).get("objectives", {}).get("target_set_sha256") != binding.get("target_set_sha256"):
        errors.append("packet target-set digest differs from the owner response")
    return errors


def _run_negative_controls(core: dict[str, Any], root: Path) -> list[dict[str, str]]:
    mutations: list[tuple[str, Any]] = []

    def add(control_id: str, mutate: Any) -> None:
        mutations.append((control_id, mutate))

    add("N0-PACKET-NEG-STALE-SOURCE", lambda value: value["source_set"]["bindings"][0].__setitem__("sha256", "0" * 64))
    add("N0-PACKET-NEG-MISSING-ADR", lambda value: value["decisions"].pop("adr_0004"))
    add("N0-PACKET-NEG-MISSING-TARGET", lambda value: value["decisions"]["objectives"]["targets"].pop())
    add("N0-PACKET-NEG-CHANGED-TARGET", lambda value: value["decisions"]["objectives"]["targets"][0].__setitem__("value", 99))
    add("N0-PACKET-NEG-MEASUREMENT-OVERCLAIM", lambda value: value["decisions"]["objectives"].__setitem__("measured_target_count", 1))
    add("N0-PACKET-NEG-INFERRED-ACCEPTANCE", lambda value: value.__setitem__("owner_acceptance_recorded", True))
    add("N0-PACKET-NEG-INFERRED-KEY-SELECTION", lambda value: value["decisions"]["custody"].__setitem__("selection", "hardware_fido2_ed25519_sk"))
    add("N0-PACKET-NEG-PRIVATE-MATERIAL", lambda value: value["decisions"]["custody"].__setitem__("private_key_material", "FORBIDDEN"))
    add("N0-PACKET-NEG-SIGNING-AUTHORIZATION", lambda value: value.__setitem__("signature_authorized", True))
    add("N0-PACKET-NEG-PUBLICATION-AUTHORIZATION", lambda value: value.__setitem__("publication_authorized", True))
    add("N0-PACKET-NEG-PRODUCTION-PROMOTION", lambda value: value.__setitem__("production_promotion_allowed", True))
    add("N0-PACKET-NEG-DROPPED-OWNER-ACTION", lambda value: value["current_state"]["pending_owner_actions"].pop())

    if tuple(control_id for control_id, _ in mutations) != NEGATIVE_CONTROL_IDS:
        raise ValueError("negative-control implementation does not match the frozen inventory")

    results: list[dict[str, str]] = []
    for control_id, mutate in mutations:
        mutant = copy.deepcopy(core)
        mutate(mutant)
        rejected = bool(_core_rejection_reasons(mutant, root))
        results.append(
            {
                "id": control_id,
                "status": "pass" if rejected else "fail",
                "expected": "reject",
                "observed": "reject" if rejected else "accept",
            }
        )
    return results


def packet_rejection_reasons(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        schema = _read_json(root / PACKET_SCHEMA_RELATIVE)
        errors.extend(f"{error.path}: {error.message}" for error in validate_json(value, schema))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"packet schema unavailable: {type(error).__name__}: {error}")

    if (root / OWNER_RESPONSE_RELATIVE).is_file():
        errors.extend(_frozen_packet_rejection_reasons(value, root))
    else:
        errors.extend(_core_rejection_reasons(value, root))
    validation = value.get("validation", {})
    controls = validation.get("negative_controls", []) if isinstance(validation, dict) else []
    if validation.get("schema_and_semantics_valid") is not True:
        errors.append("validation must record schema_and_semantics_valid=true")
    if validation.get("negative_control_count") != len(NEGATIVE_CONTROL_IDS):
        errors.append("negative-control count does not match the frozen inventory")
    if validation.get("negative_control_pass_count") != len(NEGATIVE_CONTROL_IDS):
        errors.append("not every negative control passed")
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("negative-control ordering or identifiers changed")
    if any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("negative-control status is not pass")
    return errors


def build_packet(root: Path = ROOT) -> dict[str, Any]:
    if (root / OWNER_RESPONSE_RELATIVE).is_file():
        packet = _read_json(root / PACKET_RELATIVE)
        errors = packet_rejection_reasons(packet, root)
        if errors:
            raise ValueError("invalid frozen N0 owner decision packet: " + "; ".join(errors[:8]))
        return packet
    packet = _build_core(root)
    controls = _run_negative_controls(packet, root)
    packet["validation"] = {
        "schema_and_semantics_valid": True,
        "negative_control_count": len(controls),
        "negative_control_pass_count": sum(item["status"] == "pass" for item in controls),
        "negative_controls": controls,
    }
    errors = packet_rejection_reasons(packet, root)
    if errors:
        raise ValueError("invalid N0 owner decision packet: " + "; ".join(errors[:8]))
    return packet


def _display_value(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _target_gate(target: dict[str, Any]) -> str:
    relation = "at least" if target["operator"] == "minimum" else "no more than"
    gate = f"{relation} {_display_value(target['value'])} {target['unit'].replace('_', ' ')}"
    if target["percentile"]:
        gate += f" at p{target['percentile']}"
    if target["zero_tolerance"]:
        gate += "; zero tolerance"
    return gate


def _minimum_run(target: dict[str, Any]) -> str:
    parts = [f"{target['minimum_sample_count']} sample(s)"]
    if target["minimum_duration_hours"]:
        parts.append(f"{_display_value(target['minimum_duration_hours'])} hour(s)")
    return ", ".join(parts)


def _markdown_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def render_markdown(packet: dict[str, Any]) -> str:
    errors = packet_rejection_reasons(packet, ROOT)
    if errors:
        raise ValueError("cannot render invalid decision packet: " + "; ".join(errors[:8]))

    decisions = packet["decisions"]
    objectives = decisions["objectives"]
    profile = objectives["profile"]
    lines: list[str] = [
        "# PooleOS N0 Owner Decision Packet",
        "",
        f"- Packet version: {packet['packet_version']}",
        f"- Status date: {packet['status_date']}",
        f"- Move: `{packet['selected_move_id']}`",
        "- Status: awaiting Rooke Poole's explicit selections; unsigned and non-promoting",
        "",
        "## Read This First",
        "",
        "This packet turns the current N0 owner gate into five bounded decisions. It lists the exact proposed ADR bytes, all 38 objective definitions, and every allowed governance-key profile. Nothing is pre-accepted.",
        "",
        "Completing the response form authorizes only the selected source dispositions and the next preparation step. It does not generate a key, sign a manifest, merge a branch, create or publish a tag, change repository governance, or claim that PooleOS meets any objective.",
        "",
        "## Current Gate",
        "",
        f"- Pending owner actions: `{packet['current_state']['pending_owner_action_count']}`.",
        f"- Proposed ADRs: {_markdown_list(packet['current_state']['proposed_adr_ids'])}.",
        f"- Objective definitions: `{packet['current_state']['objective_target_count']}` total, `{packet['current_state']['measured_target_count']}` measured.",
        f"- Trusted public governance signers: `{packet['current_state']['trusted_signer_count']}`.",
        "- Ready for owner review: `true`; ready for signature: `false`.",
        "",
        "## Exact Source Set",
        "",
        f"The packet binds `{packet['source_set']['binding_count']}` exact files. Binding-list SHA-256: `{packet['source_set']['sha256']}`.",
        "",
        "| Path | Bytes | SHA-256 |",
        "|---|---:|---|",
    ]
    for binding in packet["source_set"]["bindings"]:
        lines.append(f"| `{binding['path']}` | {binding['byte_count']} | `{binding['sha256']}` |")

    for key, heading in (("adr_0003", "Decision 1: ADR-0003 Language and Toolchain"), ("adr_0004", "Decision 2: ADR-0004 Names and Namespaces")):
        decision = decisions[key]
        lines.extend(
            [
                "",
                f"## {heading}",
                "",
                f"Exact source: `{decision['source']['path']}` at SHA-256 `{decision['source']['sha256']}`.",
                "",
                decision["plain_language_summary"],
                "",
                f"Recommendation: `{decision['recommendation']}`. This is advisory, not an owner selection.",
                "",
                "Why this is recommended:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in decision["recommendation_basis"])
        lines.extend(["", "Tradeoffs:", ""])
        lines.extend(f"- {item}" for item in decision["tradeoffs"])
        lines.extend(["", f"Allowed response: {_markdown_list(decision['available_dispositions'])}."])

    language = decisions["adr_0003"]["structured_snapshot"]
    lines.extend(
        [
            "",
            "### ADR-0003 Structured Snapshot",
            "",
            "| Boundary | Proposed implementation |",
            "|---|---|",
        ]
    )
    for key in ("pooleboot", "poolekernel", "privileged_user_space", "portable_pdc_reference", "host_evidence"):
        lines.append(f"| `{key}` | {language[key]} |")
    lines.extend(
        [
            f"| `native_rust_abi_on_wire_or_disk` | `{str(language['native_rust_abi_on_wire_or_disk']).lower()}` |",
            f"| `cxx_in_v1_tcb` | `{str(language['cxx_in_v1_tcb']).lower()}` |",
            f"| `third_party_dependencies_default` | `{language['third_party_dependencies_default']}` |",
            "",
            "### ADR-0004 Structured Snapshot",
            "",
            "| Role | Namespace |",
            "|---|---|",
        ]
    )
    namespace_snapshot = decisions["adr_0004"]["structured_snapshot"]
    for item in namespace_snapshot["version_namespaces"]:
        lines.append(f"| `{item['role']}` | `{item['id']}` |")

    lines.extend(
        [
            "",
            "## Decision 3: Workstation v1 Profile and 38 Targets",
            "",
            objectives["plain_language_summary"],
            "",
            f"- Profile ID: `{profile['id']}`",
            f"- Edition: `{profile['edition']}`",
            f"- Architecture and firmware: `{profile['architecture']}` / `{profile['firmware']}`",
            f"- Support profiles: {_markdown_list(profile['support_profiles'])}",
            f"- Required modes: {_markdown_list(profile['required_modes'])}",
            "",
            f"Recommendation: `{objectives['recommendation']}`. This freezes definitions only. `measurement_evidence_accepted` remains `false`.",
            "",
            "Why this is recommended:",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in objectives["recommendation_basis"])
    lines.extend(["", "Tradeoffs:", ""])
    lines.extend(f"- {item}" for item in objectives["tradeoffs"])
    lines.extend(
        [
            "",
            f"Target-set SHA-256: `{objectives['target_set_sha256']}`.",
            "",
        ]
    )

    category_order = ["reliability", "accessibility", "compatibility", "privacy", "performance"]
    for category in category_order:
        category_targets = [target for target in objectives["targets"] if target["category"] == category]
        lines.extend(
            [
                f"### {category.title()} Targets ({len(category_targets)})",
                "",
                "| ID | Metric | Gate | Minimum run | Applies to | Required evidence |",
                "|---|---|---|---|---|---|",
            ]
        )
        for target in category_targets:
            metric = target["metric"].replace("_", " ")
            applies = ", ".join(target["applies_to"])
            evidence = target["evidence_requirement"].replace("|", "\\|")
            lines.append(
                f"| `{target['id']}` | {metric} | {_target_gate(target)} | {_minimum_run(target)} | {applies} | {evidence} |"
            )
        lines.append("")

    custody = decisions["custody"]
    lines.extend(
        [
            "## Decision 4: Governance-Key Custody",
            "",
            "Recommendation: `hardware_fido2_ed25519_sk`. The hardware-key availability placeholder in the owner's prior authorization was not resolved, so availability remains explicitly unselected.",
            "",
            "| Profile | Key type | Assurance | Separate risk acceptance |",
            "|---|---|---|---|",
        ]
    )
    for profile_item in custody["available_profiles"]:
        lines.append(
            f"| `{profile_item['id']}` | `{profile_item['key_type']}` | {profile_item['assurance'].replace('_', ' ')} | `{str(profile_item['owner_risk_acceptance_required']).lower()}` |"
        )
    lines.extend(
        [
            "",
            "Private material must stay outside the PooleOS tree, outputs, handoffs, cloud sync, Git history, and this conversation. The primary governance key remains separate from recovery, Secure Boot, package, update, and release keys.",
            "",
            "## Decision 5: Public-Key Publication",
            "",
            "After a key exists, independently inspect its fingerprint. The recommended disposition is `approve_after_fingerprint_review`, which permits publishing only the public key and fingerprint to `security/owner-adr-signers.allowed` and GitHub's SSH signing-key registry. It does not authorize any signature.",
            "",
            "## Owner Response Form",
            "",
            "Reply with this block completed. Use only one allowed value per field. Leave amendment details as `none` when accepting exact text.",
            "",
            "```text",
            "POOLEOS-N0-OWNER-RESPONSE-V1",
            "ADR-0003: <accept_exactly_as_written | amend_before_acceptance | reject_and_supersede>",
            "ADR-0004: <accept_exactly_as_written | amend_before_acceptance | reject_and_supersede>",
            "WORKSTATION-V1-AND-38-TARGETS: <accept_exactly_as_written | amend_before_acceptance | reject>",
            "FIDO2-HARDWARE-KEY-AVAILABLE: <have | do_not_have | unsure>",
            "GOVERNANCE-KEY-PROFILE: <hardware_fido2_ed25519_sk | hardware_fido2_ecdsa_sk | passphrase_ed25519_provisional>",
            "PROVISIONAL-SOFTWARE-KEY-RISK-ACCEPTED: <yes | no | not_applicable>",
            "PUBLIC-KEY-PUBLICATION: <approve_after_fingerprint_review | not_yet>",
            "AMENDMENT-DETAILS: <none | exact requested changes>",
            "I-CONFIRM-DEFINITION-ACCEPTANCE-IS-NOT-MEASUREMENT-ACCEPTANCE: <yes>",
            "I-CONFIRM-THIS-DOES-NOT-AUTHORIZE-KEY-GENERATION-SIGNING-MERGING-TAGGING-OR-PUBLICATION: <yes>",
            "```",
            "",
            "## What Happens After the Response",
            "",
            "1. Codex validates that every selection is explicit and internally consistent.",
            "2. An amendment or rejection stops the ceremony while the affected source is revised or superseded and the packet is regenerated.",
            "3. Exact acceptance permits a separate source-status and unsigned-manifest preparation change.",
            "4. Key generation, public-key registration, detached signing, merge, signed tagging, and publication remain separately approved checkpoints.",
            "",
            "## Validation",
            "",
            f"- Schema and semantic validation: `{str(packet['validation']['schema_and_semantics_valid']).lower()}`.",
            f"- Negative controls: `{packet['validation']['negative_control_pass_count']}/{packet['validation']['negative_control_count']}` pass.",
            "- Owner acceptance recorded: `false`.",
            "- Signature authorized: `false`.",
            "- Publication authorized: `false`.",
            "- Production promotion allowed: `false`.",
            "",
            "## Claim Boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in packet["claim_boundary"])
    return "\n".join(lines) + "\n"


def write_packet(packet: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(canonical_json_bytes(packet))
    markdown_path.write_text(render_markdown(packet), encoding="utf-8", newline="\n")
