"""Operator action request artifacts for PooleOS."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.operator_action_request"
RECEIPT_KIND = "pooleos.operator_action_receipt"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def make_wsl_package_install_request(*, prerequisites_path: Path) -> dict[str, Any]:
    prerequisites = _read_json(prerequisites_path)
    source_status = str(prerequisites.get("status", ""))
    command = str(prerequisites.get("install_command", ""))
    packages = [str(package) for package in prerequisites.get("missing_packages", [])]
    package_manager = str(prerequisites.get("package_manager", ""))
    distro = str(prerequisites.get("distro", ""))
    command_hash = hashlib.sha256(command.encode("utf-8")).hexdigest() if command else ""

    pending = source_status == "blocked" and bool(command) and bool(packages)
    no_action = source_status == "pass" and not packages
    status = "pending_approval" if pending else "no_action_needed" if no_action else "invalid"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "action_kind": "wsl_package_install",
        "target": {
            "environment": "wsl",
            "distro": distro,
            "package_manager": package_manager,
        },
        "source_artifact": str(prerequisites_path),
        "source_status": source_status,
        "requires_operator_approval": status == "pending_approval",
        "codex_execution_allowed": False,
        "execution_performed": False,
        "command": command,
        "command_sha256": command_hash,
        "packages": packages,
        "safety_checks": [
            _check("source_is_wsl_prerequisites", prerequisites.get("artifact_kind") == "pooleos.wsl_prerequisites", str(prerequisites.get("artifact_kind", ""))),
            _check("source_was_non_mutating", prerequisites.get("execution_performed") is False, f"execution_performed={prerequisites.get('execution_performed')}"),
            _check("command_present_when_needed", bool(command) if pending else True, "install command present" if command else "install command missing"),
            _check("codex_will_not_execute", True, "operator action request only; Codex did not run the command"),
        ],
        "next_steps": [
            "Operator reviews the command and package list.",
            "If approved, operator runs the command inside the named WSL distro.",
            "After host preparation, rerun pooleos_wsl_prereqs.py and then pooleos_wsl_configure.py.",
        ],
    }


def make_wsl_package_install_receipt(
    *,
    operator_action_path: Path,
    verification_prerequisites_path: Path,
    operator_executed: bool = False,
) -> dict[str, Any]:
    request = _read_json(operator_action_path)
    prerequisites = _read_json(verification_prerequisites_path)
    command = str(request.get("command", ""))
    command_hash = hashlib.sha256(command.encode("utf-8")).hexdigest() if command else ""
    stored_hash = str(request.get("command_sha256", ""))
    request_status = str(request.get("status", ""))
    prereq_status = str(prerequisites.get("status", ""))
    request_valid = request.get("artifact_kind") == ARTIFACT_KIND and request_status in {"pending_approval", "no_action_needed"}
    prereq_valid = prerequisites.get("artifact_kind") == "pooleos.wsl_prerequisites"
    command_hash_match = command_hash == stored_hash
    prereqs_pass = prereq_status == "pass"
    no_action_needed = request_status == "no_action_needed"
    verified = request_valid and prereq_valid and command_hash_match and prereqs_pass and (operator_executed or no_action_needed)

    if verified:
        status = "verified"
    elif not request_valid or not prereq_valid or not command_hash_match:
        status = "invalid"
    elif operator_executed and not prereqs_pass:
        status = "verification_failed"
    else:
        status = "pending_operator_action"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": RECEIPT_KIND,
        "status": status,
        "action_kind": str(request.get("action_kind", "")),
        "target": request.get("target", {"environment": "", "distro": "", "package_manager": ""}),
        "operator_action_request": str(operator_action_path),
        "verification_prerequisites": str(verification_prerequisites_path),
        "operator_executed": bool(operator_executed),
        "codex_execution_performed": False,
        "command": command,
        "command_sha256": stored_hash,
        "packages": [str(package) for package in request.get("packages", [])],
        "checks": [
            _check("request_valid", request_valid, f"status={request_status}; artifact_kind={request.get('artifact_kind')}"),
            _check("prerequisites_valid", prereq_valid, f"status={prereq_status}; artifact_kind={prerequisites.get('artifact_kind')}"),
            _check("command_hash_match", command_hash_match, f"computed={command_hash}; stored={stored_hash}"),
            _check("operator_execution_claimed", bool(operator_executed or no_action_needed), f"operator_executed={operator_executed}; request_status={request_status}"),
            _check("prerequisites_pass_after_action", prereqs_pass, f"verification_status={prereq_status}"),
            _check("codex_did_not_execute", True, "receipt only; Codex did not run the host-modifying command"),
        ],
        "next_steps": [
            "If status is pending_operator_action, operator still needs to review and run the requested command.",
            "If status is verification_failed, inspect WSL package install output and rerun pooleos_wsl_prereqs.py.",
            "If status is verified, rerun pooleos_wsl_configure.py to attempt Buildroot defconfig.",
        ],
    }


def write_request(request: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
