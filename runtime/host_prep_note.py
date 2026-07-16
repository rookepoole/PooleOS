"""Human and machine-readable host preparation handoff artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.host_prep_note"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _verification_commands() -> list[str]:
    return [
        r"python .\tools\pooleos_wsl_prereqs.py --buildroot-path C:\path\to\buildroot --out .\runs\wsl_prerequisites.json",
        r"python .\tools\pooleos_operator_receipt.py --operator-action .\runs\operator_action_request.json --wsl-prerequisites .\runs\wsl_prerequisites.json --operator-executed --out .\runs\operator_action_receipt.json",
        r"python .\tools\pooleos_wsl_configure.py --buildroot-path C:\path\to\buildroot --prerequisites .\runs\wsl_prerequisites.json --out .\runs\buildroot_configure.json",
    ]


def make_host_prep_note_manifest(
    *,
    operator_action_path: Path,
    operator_receipt_path: Path,
    note_path: Path,
) -> dict[str, Any]:
    request = _read_json(operator_action_path)
    receipt = _read_json(operator_receipt_path)

    command = str(request.get("command", ""))
    computed_hash = hashlib.sha256(command.encode("utf-8")).hexdigest() if command else ""
    request_hash = str(request.get("command_sha256", ""))
    receipt_hash = str(receipt.get("command_sha256", ""))
    request_status = str(request.get("status", ""))
    receipt_status = str(receipt.get("status", ""))
    request_kind_ok = request.get("artifact_kind") == "pooleos.operator_action_request"
    receipt_kind_ok = receipt.get("artifact_kind") == "pooleos.operator_action_receipt"
    command_match = command == str(receipt.get("command", ""))
    command_present = bool(command) if request_status == "pending_approval" else True
    hash_match = computed_hash == request_hash and request_hash == receipt_hash
    codex_execution_allowed = bool(request.get("codex_execution_allowed", True))
    execution_performed = bool(request.get("execution_performed", True))
    codex_execution_performed = bool(receipt.get("codex_execution_performed", True))
    request_valid = request_kind_ok and request_status in {"pending_approval", "no_action_needed"}
    receipt_valid = receipt_kind_ok and receipt_status in {"pending_operator_action", "verified"}

    checks = [
        _check("request_valid", request_valid, f"status={request_status}; artifact_kind={request.get('artifact_kind')}"),
        _check("receipt_valid", receipt_valid, f"status={receipt_status}; artifact_kind={receipt.get('artifact_kind')}"),
        _check("command_present_when_needed", command_present, "command present" if command else "command empty"),
        _check("command_matches_receipt", command_match, "request command matches receipt command" if command_match else "request command differs from receipt command"),
        _check("command_hash_match", hash_match, f"computed={computed_hash}; request={request_hash}; receipt={receipt_hash}"),
        _check("codex_did_not_execute", not codex_execution_allowed and not execution_performed and not codex_execution_performed, f"codex_execution_allowed={codex_execution_allowed}; execution_performed={execution_performed}; codex_execution_performed={codex_execution_performed}"),
    ]
    checks_ok = all(check["ok"] for check in checks)

    if not checks_ok:
        status = "invalid"
    elif request_status == "no_action_needed" or receipt_status == "verified":
        status = "no_action_needed"
    else:
        status = "ready_for_operator"

    if status == "ready_for_operator":
        next_steps = [
            "Review the exact command and command SHA-256 before running anything.",
            "If approved, run the command inside the named WSL distro.",
            "Rerun WSL prerequisites, emit the operator receipt with --operator-executed, then run the WSL-gated configure step.",
        ]
    elif status == "no_action_needed":
        next_steps = [
            "No package-install action is pending from this note.",
            "Run the WSL-gated configure step if prerequisites are verified.",
        ]
    else:
        next_steps = [
            "Do not run the command from this note.",
            "Regenerate the operator action request, receipt, and host prep note from current prerequisite evidence.",
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "note_path": str(note_path),
        "operator_action_request": str(operator_action_path),
        "operator_action_receipt": str(operator_receipt_path),
        "target": request.get("target", {"environment": "", "distro": "", "package_manager": ""}),
        "request_status": request_status,
        "receipt_status": receipt_status,
        "requires_operator_approval": bool(request.get("requires_operator_approval", False)),
        "codex_execution_allowed": codex_execution_allowed,
        "execution_performed": execution_performed,
        "codex_execution_performed": codex_execution_performed,
        "operator_executed": bool(receipt.get("operator_executed", False)),
        "command": command,
        "command_sha256": request_hash,
        "packages": [str(package) for package in request.get("packages", [])],
        "checks": checks,
        "next_steps": next_steps,
        "verification_commands": _verification_commands(),
    }


def render_host_prep_markdown(manifest: dict[str, Any]) -> str:
    target = manifest.get("target", {})
    packages = manifest.get("packages", [])
    checks = manifest.get("checks", [])
    verification_commands = manifest.get("verification_commands", [])
    command = str(manifest.get("command", ""))
    command_hash = str(manifest.get("command_sha256", ""))

    lines = [
        "# PooleOS Host Preparation Note",
        "",
        f"Status: `{manifest.get('status')}`",
        "",
        "## Safety Boundary",
        "",
        "Codex did not execute the host-modifying command. This note is an operator handoff for review inside the named WSL distro.",
        "",
        f"- Codex execution allowed: `{str(manifest.get('codex_execution_allowed')).lower()}`",
        f"- Execution performed by Codex: `{str(manifest.get('execution_performed')).lower()}`",
        f"- Receipt says Codex execution performed: `{str(manifest.get('codex_execution_performed')).lower()}`",
        f"- Operator executed: `{str(manifest.get('operator_executed')).lower()}`",
        "",
        "## Target",
        "",
        f"- Environment: `{target.get('environment', '')}`",
        f"- Distro: `{target.get('distro', '')}`",
        f"- Package manager: `{target.get('package_manager', '')}`",
        "",
        "## Requested Packages",
        "",
    ]

    if packages:
        lines.extend(f"- `{package}`" for package in packages)
    else:
        lines.append("- No packages pending from this note.")

    lines.extend(
        [
            "",
            "## Command",
            "",
            f"SHA-256: `{command_hash}`",
            "",
        ]
    )

    if command:
        lines.extend(["```bash", command, "```"])
    else:
        lines.append("No install command is required by the current operator action request.")

    lines.extend(["", "## Evidence Links", ""])
    lines.append(f"- Operator action request: `{manifest.get('operator_action_request')}`")
    lines.append(f"- Operator action receipt: `{manifest.get('operator_action_receipt')}`")

    lines.extend(["", "## Verification Commands", ""])
    if verification_commands:
        lines.extend(["```powershell", *[str(command_text) for command_text in verification_commands], "```"])
    else:
        lines.append("No verification commands were emitted.")

    lines.extend(["", "## Checks", ""])
    for check in checks:
        state = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"- {state} `{check.get('name')}`: {check.get('detail')}")

    lines.extend(["", "## Next Steps", ""])
    for step in manifest.get("next_steps", []):
        lines.append(f"- {step}")

    return "\n".join(lines) + "\n"


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_note(markdown: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
