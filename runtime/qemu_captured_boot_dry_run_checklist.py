"""Dry-run checklist for operator-managed captured QEMU boots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime import boot_log


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_captured_boot_dry_run_checklist"


@dataclass(frozen=True)
class ChecklistCheck:
    name: str
    severity: str
    ok: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "ok": bool(self.ok),
            "detail": self.detail,
        }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str, *, severity: str = "fail") -> ChecklistCheck:
    return ChecklistCheck(name=name, severity=severity, ok=ok, detail=detail)


def _command_by_role(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    commands: dict[str, dict[str, Any]] = {}
    for command in bundle.get("command_plan", []):
        if isinstance(command, dict):
            role = str(command.get("role", ""))
            if role:
                commands[role] = command
    return commands


def _preflight_blockers(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for check in preflight.get("checks", []):
        if not isinstance(check, dict):
            continue
        if check.get("required") is True and check.get("ok") is not True:
            blockers.append(
                {
                    "name": str(check.get("name", "")),
                    "detail": str(check.get("detail", "")),
                    "resolved": False,
                }
            )
    return blockers


def _step(
    *,
    step_id: str,
    title: str,
    phase: str,
    readiness: str,
    required: bool,
    operator_receipt_field: str,
    command: dict[str, Any] | None = None,
    expected_outputs: list[str] | None = None,
    expected_markers: list[str] | None = None,
    blockers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "phase": phase,
        "readiness": readiness,
        "required": bool(required),
        "command_role": str(command.get("role", "")) if command else "",
        "powershell": str(command.get("powershell", "")) if command else "",
        "operator_receipt_field": operator_receipt_field,
        "expected_outputs": expected_outputs or [],
        "expected_markers": expected_markers or [],
        "blockers": blockers or [],
    }


def _path_exists_for_template(root: Path, value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.exists()


def _post_capture_files(root: Path, expected_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    roles = [
        ("serial_log", "serial_log_path", "QEMU serial log captured from the real boot."),
        ("boot_validation", "boot_validation_output", "Trap-input boot log validation output."),
        ("captured_boot_evidence", "qemu_boot_evidence_output", "Captured QEMU serial boot evidence artifact."),
        ("captured_boot_receipt", "qemu_captured_boot_receipt_output", "Receipt after captured evidence slot is reserved or ingested."),
        ("release_gate", "release_gate_output", "Release-gate report after captured slot reconciliation."),
    ]
    files = []
    for role, key, description in roles:
        path = str(expected_outputs.get(key, ""))
        files.append(
            {
                "role": role,
                "path": path,
                "required_after_capture": role != "release_gate",
                "exists_at_template_time": _path_exists_for_template(root, path),
                "description": description,
            }
        )
    return files


def _operator_receipt_template(
    *,
    checklist_output_path: Path | None,
    launch_bundle_path: Path,
    checklist_steps: list[dict[str, Any]],
    expected_markers: list[str],
    post_capture_files: list[dict[str, Any]],
    release_gate_arguments: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "pooleos.qemu_captured_boot_operator_receipt_template",
        "operator_executed": False,
        "codex_execution_performed": False,
        "checklist": str(checklist_output_path or ""),
        "launch_bundle": str(launch_bundle_path),
        "commands": [
            {
                "step_id": step["id"],
                "command_role": step["command_role"],
                "operator_checked": False,
                "exit_code": "",
                "notes": "",
            }
            for step in checklist_steps
            if step["command_role"]
        ],
        "preflight_blockers_resolved": False,
        "expected_serial_markers": [
            {
                "marker": marker,
                "observed": False,
            }
            for marker in expected_markers
        ],
        "post_capture_files": [
            {
                "role": file["role"],
                "path": file["path"],
                "operator_verified": False,
            }
            for file in post_capture_files
        ],
        "release_gate": {
            "arguments": release_gate_arguments,
            "operator_reconciled": False,
        },
    }


def make_qemu_captured_boot_dry_run_checklist(
    *,
    root: Path,
    launch_bundle_path: Path,
    checklist_output_path: Path | None = None,
    release_gate_output_path: Path | None = None,
) -> dict[str, Any]:
    bundle = _read_json(launch_bundle_path)
    inputs = bundle.get("inputs", {}) if isinstance(bundle.get("inputs"), dict) else {}
    expected_outputs = bundle.get("expected_outputs", {}) if isinstance(bundle.get("expected_outputs"), dict) else {}
    preflight_value = str(inputs.get("preflight", ""))
    preflight_path = Path(preflight_value) if preflight_value else None
    if preflight_path is not None and not preflight_path.is_absolute():
        preflight_path = root / preflight_path
    preflight = _read_json(preflight_path) if preflight_path is not None else {}
    commands = _command_by_role(bundle)
    expected_markers = boot_log.required_markers_for_profile("trap-input")
    blockers = _preflight_blockers(preflight)
    post_capture_files = _post_capture_files(root, expected_outputs)
    base_release_args = [str(arg) for arg in bundle.get("release_gate_arguments", [])]
    release_gate_arguments = list(base_release_args)
    if checklist_output_path is not None and "--qemu-captured-boot-dry-run-checklist" not in release_gate_arguments:
        release_gate_arguments.extend(["--qemu-captured-boot-dry-run-checklist", str(checklist_output_path)])
    if release_gate_output_path is not None and "--out" not in release_gate_arguments:
        release_gate_arguments.extend(["--out", str(release_gate_output_path)])

    bundle_status = str(bundle.get("status", ""))
    bundle_launch_ready = bundle.get("launch_ready") is True
    launch_readiness = "ready" if bundle_launch_ready else "blocked"
    blocker_readiness = "blocked" if blockers else "ready"
    post_capture_paths = [file["path"] for file in post_capture_files if file["required_after_capture"]]

    checklist_steps = [
        _step(
            step_id="resolve_preflight_blockers",
            title="Resolve captured boot preflight blockers",
            phase="preflight",
            readiness=blocker_readiness,
            required=True,
            operator_receipt_field="preflight_blockers_resolved",
            command=commands.get("captured_preflight"),
            blockers=blockers,
        ),
        _step(
            step_id="stage_shared_folder",
            title="Stage the QEMU shared folder inputs",
            phase="host_prepare",
            readiness="ready" if commands.get("prepare_shared_folder") else "blocked",
            required=True,
            operator_receipt_field="prepare_shared_folder_checked",
            command=commands.get("prepare_shared_folder"),
        ),
        _step(
            step_id="rerun_captured_preflight",
            title="Regenerate the captured boot preflight",
            phase="host_prepare",
            readiness="ready" if commands.get("captured_preflight") else "blocked",
            required=True,
            operator_receipt_field="captured_preflight_checked",
            command=commands.get("captured_preflight"),
        ),
        _step(
            step_id="launch_qemu",
            title="Launch the PooleOS Lab VM",
            phase="qemu_launch",
            readiness=launch_readiness,
            required=True,
            operator_receipt_field="qemu_launch_checked",
            command=commands.get("qemu_launch"),
            expected_outputs=[str(expected_outputs.get("serial_log_path", ""))],
            blockers=blockers if not bundle_launch_ready else [],
        ),
        _step(
            step_id="verify_serial_markers",
            title="Verify trap-input serial boot markers",
            phase="guest_verify",
            readiness="post_capture",
            required=True,
            operator_receipt_field="serial_markers_verified",
            expected_markers=expected_markers,
        ),
        _step(
            step_id="emit_captured_evidence",
            title="Emit captured QEMU boot evidence from the serial log",
            phase="post_capture",
            readiness="post_capture",
            required=True,
            operator_receipt_field="captured_evidence_checked",
            command=commands.get("emit_captured_evidence_only"),
            expected_outputs=[str(expected_outputs.get("boot_validation_output", "")), str(expected_outputs.get("qemu_boot_evidence_output", ""))],
        ),
        _step(
            step_id="emit_captured_receipt",
            title="Emit or refresh the captured boot receipt",
            phase="post_capture",
            readiness="post_capture",
            required=True,
            operator_receipt_field="captured_receipt_checked",
            command=commands.get("captured_receipt"),
            expected_outputs=[str(expected_outputs.get("qemu_captured_boot_receipt_output", ""))],
        ),
        _step(
            step_id="reconcile_release_gate",
            title="Reconcile the captured boot lane in the release gate",
            phase="release_gate",
            readiness="post_capture",
            required=True,
            operator_receipt_field="release_gate_reconciled",
            expected_outputs=[str(expected_outputs.get("release_gate_output", ""))],
        ),
    ]

    expected_roles = {
        "prepare_shared_folder",
        "captured_preflight",
        "qemu_launch",
        "emit_captured_evidence_only",
        "captured_receipt",
    }
    command_roles = set(commands)
    checks = [
        _check("execution_not_performed", True, "dry-run checklist assembly is non-mutating"),
        _check("launch_bundle_present", launch_bundle_path.exists(), str(launch_bundle_path)),
        _check("launch_bundle_artifact_kind", bundle.get("artifact_kind") == "pooleos.qemu_captured_boot_launch_bundle", str(bundle.get("artifact_kind", ""))),
        _check("launch_bundle_status_usable", bundle_status in {"pass", "blocked"}, f"status={bundle_status}"),
        _check("launch_bundle_has_no_failed_checks", bundle.get("summary", {}).get("failed_check_count") == 0, f"failed={bundle.get('summary', {}).get('failed_check_count')}"),
        _check("preflight_present", bool(preflight) and preflight_path is not None and preflight_path.exists(), str(preflight_path or "")),
        _check("preflight_artifact_kind", preflight.get("artifact_kind") == "pooleos.qemu_captured_boot_preflight", str(preflight.get("artifact_kind", ""))),
        _check("preflight_has_no_safety_failures", preflight.get("summary", {}).get("safety_failure_count") == 0, f"safety={preflight.get('summary', {}).get('safety_failure_count')}"),
        _check("preflight_ready_for_launch", bundle_launch_ready, f"launch_ready={bundle.get('launch_ready')}", severity="block"),
        _check("preflight_blockers_recorded", bundle_launch_ready or bool(blockers), f"blockers={len(blockers)}"),
        _check("command_plan_complete", expected_roles.issubset(command_roles), f"roles={sorted(command_roles)}"),
        _check(
            "expected_serial_markers_present",
            {
                "POOLEOS_LAB_INPUT_VERIFY_PASS",
                "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS",
                "POOLEOS_LAB_SHARED_MOUNT_PASS",
                "POOLEOS_LAB_AUTOSTART_DONE",
            }.issubset(expected_markers),
            f"markers={len(expected_markers)}",
        ),
        _check("post_capture_files_listed", all(post_capture_paths), f"files={len(post_capture_paths)}"),
        _check("release_gate_arguments_reference_launch_bundle", "--qemu-captured-boot-launch-bundle" in release_gate_arguments, "launch bundle argument present"),
        _check("release_gate_arguments_reference_checklist", "--qemu-captured-boot-dry-run-checklist" in release_gate_arguments, "dry-run checklist argument present"),
        _check("operator_authority_preserved", True, "operator receipt template starts unchecked and Codex does not claim execution"),
    ]
    failed_checks = [check for check in checks if check.severity == "fail" and not check.ok]
    blocking_checks = [check for check in checks if check.severity == "block" and not check.ok]
    status = "fail" if failed_checks else "blocked" if blocking_checks else "pass"
    receipt_template = _operator_receipt_template(
        checklist_output_path=checklist_output_path,
        launch_bundle_path=launch_bundle_path,
        checklist_steps=checklist_steps,
        expected_markers=expected_markers,
        post_capture_files=post_capture_files,
        release_gate_arguments=release_gate_arguments,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "launch_ready": status == "pass",
        "execution_performed": False,
        "source_launch_bundle": str(launch_bundle_path),
        "preflight": {
            "path": str(preflight_path or ""),
            "status": str(preflight.get("status", "")),
            "launch_ready": preflight.get("launch_ready") is True,
            "blocking_checks": blockers,
        },
        "checklist_steps": checklist_steps,
        "expected_serial_markers": expected_markers,
        "post_capture_files": post_capture_files,
        "operator_receipt_template": receipt_template,
        "release_gate_reconciliation": {
            "base_arguments": base_release_args,
            "checklist_arguments": release_gate_arguments,
            "output_path": str(release_gate_output_path or expected_outputs.get("release_gate_output", "")),
        },
        "checks": [check.to_json() for check in checks],
        "summary": {
            "failed_check_count": len(failed_checks),
            "blocking_check_count": len(blocking_checks),
            "checklist_step_count": len(checklist_steps),
            "command_count": len(command_roles),
            "preflight_blocker_count": len(blockers),
            "expected_marker_count": len(expected_markers),
            "post_capture_file_count": len(post_capture_files),
            "release_gate_argument_count": len(release_gate_arguments),
            "operator_executed": False,
            "execution_performed": False,
        },
        "limitations": [
            "This checklist is a dry run and receipt template; it does not launch QEMU or modify host state.",
            "A blocked checklist can still be valid when the launch bundle is blocked by missing image or QEMU prerequisites.",
            "Operator receipt fields remain unchecked until a human runs the command plan and records outcomes.",
        ],
        "next_steps": [
            "Resolve any preflight blockers recorded in this checklist.",
            "Run the checklist steps in order when a real Lab image and QEMU executable are available.",
            "After capture, fill the operator receipt template and rerun the release gate with checklist_arguments.",
        ],
    }


def write_checklist(checklist: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
