"""Operator-facing captured QEMU boot launch bundle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_captured_boot_launch_bundle"


@dataclass(frozen=True)
class BundleCheck:
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


def _check(name: str, ok: bool, detail: str, *, severity: str = "fail") -> BundleCheck:
    return BundleCheck(name=name, severity=severity, ok=ok, detail=detail)


def _resolve_for_compare(root: Path, value: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _same_path(root: Path, left: str, right: str) -> bool:
    left_path = _resolve_for_compare(root, left)
    right_path = _resolve_for_compare(root, right)
    return bool(left_path and right_path and left_path == right_path)


def _ps_quote(arg: str) -> str:
    if arg == "":
        return "''"
    if any(ch.isspace() for ch in arg) or any(ch in arg for ch in "'\"&()[]{};"):
        return "'" + arg.replace("'", "''") + "'"
    return arg


def _command(role: str, description: str, argv: list[str]) -> dict[str, Any]:
    return {
        "role": role,
        "description": description,
        "argv": argv,
        "powershell": " ".join(_ps_quote(str(arg)) for arg in argv),
    }


def _staged_sources(shared_contract: dict[str, Any]) -> dict[str, str]:
    sources: dict[str, str] = {
        "trap_bundle": "",
        "replay_proof": "",
        "boot_trap_bundle_manifest": "",
        "pgb2_trap_abi_boundary_receipt": "",
    }
    for staged in shared_contract.get("staged_files", []):
        if isinstance(staged, dict) and staged.get("role") in sources:
            sources[str(staged["role"])] = str(staged.get("source_path", ""))
    return sources


def _launcher(root: Path, launcher_script: Path | None) -> str:
    if launcher_script is not None:
        return str(launcher_script)
    script = root / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1"
    try:
        return ".\\" + str(script.relative_to(root))
    except ValueError:
        return str(script)


def _make_command_plan(
    *,
    root: Path,
    launcher_script: Path | None,
    preflight_path: Path,
    shared_contract_path: Path,
    receipt_path: Path,
    fixture_evidence_path: Path,
    preflight: dict[str, Any],
    shared_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    paths = preflight.get("paths", {}) if isinstance(preflight.get("paths"), dict) else {}
    qemu = preflight.get("qemu", {}) if isinstance(preflight.get("qemu"), dict) else {}
    staged = _staged_sources(shared_contract)
    launcher = _launcher(root, launcher_script)
    image = str(paths.get("image_path", ""))
    shared = str(paths.get("shared_output_path", ""))
    serial = str(paths.get("serial_log_path", ""))
    boot_validation = str(paths.get("boot_validation_output", ""))
    captured_evidence = str(paths.get("qemu_boot_evidence_output", ""))
    kernel = str(paths.get("kernel_path", ""))
    qemu_command = str(qemu.get("command", "qemu-system-x86_64"))
    no_virtfs = bool(qemu.get("no_virtfs", False))

    prepare_args = [
        launcher,
        "-PrepareInputsOnly",
        "-SharedOutputPath",
        shared,
        "-TrapBundlePath",
        staged["trap_bundle"],
        "-ReplayProofPath",
        staged["replay_proof"],
        "-BootTrapBundleManifestPath",
        staged["boot_trap_bundle_manifest"],
        "-QemuSharedFolderContract",
        str(shared_contract_path),
    ]
    if staged.get("pgb2_trap_abi_boundary_receipt"):
        prepare_args.extend(["-Pgb2TrapAbiBoundaryReceiptPath", staged["pgb2_trap_abi_boundary_receipt"]])

    preflight_args = [
        "python",
        ".\\tools\\emit_qemu_captured_boot_preflight.py",
        "--image",
        image,
        "--shared-output",
        shared,
        "--serial-log",
        serial,
        "--boot-validation-output",
        boot_validation,
        "--qemu-boot-evidence-output",
        captured_evidence,
        "--qemu-captured-boot-receipt-output",
        str(receipt_path),
        "--qemu-command",
        qemu_command,
        "--out",
        str(preflight_path),
    ]
    if kernel:
        preflight_args[4:4] = ["--kernel", kernel]
    if no_virtfs:
        preflight_args.append("--no-virtfs")

    launch_args = [
        launcher,
        "-ImagePath",
        image,
        "-SharedOutputPath",
        shared,
        "-TrapBundlePath",
        staged["trap_bundle"],
        "-ReplayProofPath",
        staged["replay_proof"],
        "-BootTrapBundleManifestPath",
        staged["boot_trap_bundle_manifest"],
        "-QemuSharedFolderContract",
        str(shared_contract_path),
        "-SerialLog",
        serial,
        "-BootValidationOutput",
        boot_validation,
        "-QemuBootEvidenceOutput",
        captured_evidence,
        "-QemuExe",
        qemu_command,
    ]
    if staged.get("pgb2_trap_abi_boundary_receipt"):
        launch_args.extend(["-Pgb2TrapAbiBoundaryReceiptPath", staged["pgb2_trap_abi_boundary_receipt"]])
    if kernel:
        launch_args.extend(["-KernelPath", kernel])
    if no_virtfs:
        launch_args.append("-NoVirtfs")

    evidence_only_args = [
        launcher,
        "-EmitCapturedEvidenceOnly",
        "-SerialLog",
        serial,
        "-BootValidationOutput",
        boot_validation,
        "-QemuBootEvidenceOutput",
        captured_evidence,
    ]

    receipt_args = [
        "python",
        ".\\tools\\emit_qemu_captured_boot_receipt.py",
        "--fixture-evidence",
        str(fixture_evidence_path),
        "--captured-evidence",
        captured_evidence,
        "--out",
        str(receipt_path),
    ]

    return [
        _command("prepare_shared_folder", "Stage the trap bundle, replay proof, manifest, and optional ABI boundary receipt for the QEMU shared folder.", prepare_args),
        _command("captured_preflight", "Regenerate the non-mutating captured boot preflight.", preflight_args),
        _command("qemu_launch", "Run the real QEMU Lab boot after the preflight status is pass.", launch_args),
        _command("emit_captured_evidence_only", "Rebuild captured evidence from an existing serial log without relaunching QEMU.", evidence_only_args),
        _command("captured_receipt", "Reserve or ingest the captured evidence slot after boot.", receipt_args),
    ]


def make_qemu_captured_boot_launch_bundle(
    *,
    root: Path,
    preflight_path: Path,
    qemu_shared_folder_contract_path: Path,
    qemu_captured_boot_receipt_path: Path,
    fixture_evidence_path: Path,
    launch_bundle_output_path: Path | None = None,
    release_gate_output_path: Path | None = None,
    launcher_script: Path | None = None,
) -> dict[str, Any]:
    preflight = _read_json(preflight_path)
    shared_contract = _read_json(qemu_shared_folder_contract_path)
    receipt = _read_json(qemu_captured_boot_receipt_path)
    launcher = launcher_script or root / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1"

    paths = preflight.get("paths", {}) if isinstance(preflight.get("paths"), dict) else {}
    qemu = preflight.get("qemu", {}) if isinstance(preflight.get("qemu"), dict) else {}
    shared_folder = shared_contract.get("shared_folder", {}) if isinstance(shared_contract.get("shared_folder"), dict) else {}
    receipt_fixture = receipt.get("fixture_boot_evidence", {}) if isinstance(receipt.get("fixture_boot_evidence"), dict) else {}
    receipt_captured = receipt.get("captured_boot_evidence", {}) if isinstance(receipt.get("captured_boot_evidence"), dict) else {}
    staged_sources = _staged_sources(shared_contract)

    preflight_status = str(preflight.get("status", ""))
    receipt_status = str(receipt.get("status", ""))
    shared_status = str(shared_contract.get("status", ""))
    captured_evidence_path = str(paths.get("qemu_boot_evidence_output", ""))
    receipt_output_path = str(paths.get("qemu_captured_boot_receipt_output", ""))
    shared_output_path = str(paths.get("shared_output_path", ""))
    launch_bundle_output = str(launch_bundle_output_path or "")
    release_gate_output = str(release_gate_output_path or "")

    checks = [
        _check("execution_not_performed", True, "bundle assembly is non-mutating"),
        _check("launcher_script_present", launcher.exists(), str(launcher)),
        _check("preflight_present", preflight_path.exists(), str(preflight_path)),
        _check("preflight_artifact_kind", preflight.get("artifact_kind") == "pooleos.qemu_captured_boot_preflight", str(preflight.get("artifact_kind", ""))),
        _check("preflight_status_usable", preflight_status in {"pass", "blocked"}, f"status={preflight_status}"),
        _check("preflight_has_no_safety_failures", preflight.get("summary", {}).get("safety_failure_count") == 0, f"safety={preflight.get('summary', {}).get('safety_failure_count')}"),
        _check("preflight_launch_ready", preflight.get("launch_ready") is True, f"launch_ready={preflight.get('launch_ready')}", severity="block"),
        _check("shared_contract_present", qemu_shared_folder_contract_path.exists(), str(qemu_shared_folder_contract_path)),
        _check("shared_contract_artifact_kind", shared_contract.get("artifact_kind") == "pooleos.qemu_shared_folder_contract", str(shared_contract.get("artifact_kind", ""))),
        _check("shared_contract_status_pass", shared_status == "pass", f"status={shared_status}", severity="block"),
        _check("shared_contract_prepared", shared_folder.get("prepared_for_launch") is True, f"prepared={shared_folder.get('prepared_for_launch')}", severity="block"),
        _check("shared_mount_tag_matches_preflight", str(shared_folder.get("mount_tag", "")) == str(qemu.get("shared_mount_tag", "")), f"shared={shared_folder.get('mount_tag', '')}; preflight={qemu.get('shared_mount_tag', '')}"),
        _check("shared_path_matches_preflight", _same_path(root, str(shared_folder.get("host_path", "")), shared_output_path), f"shared={shared_folder.get('host_path', '')}; preflight={shared_output_path}"),
        _check(
            "staged_sources_present",
            all(value for role, value in staged_sources.items() if role != "pgb2_trap_abi_boundary_receipt"),
            f"roles={sorted(role for role, value in staged_sources.items() if value)}",
            severity="block",
        ),
        _check("receipt_present", qemu_captured_boot_receipt_path.exists(), str(qemu_captured_boot_receipt_path)),
        _check("receipt_artifact_kind", receipt.get("artifact_kind") == "pooleos.qemu_captured_boot_receipt", str(receipt.get("artifact_kind", ""))),
        _check("receipt_status_usable", receipt_status in {"pending_capture", "captured"}, f"status={receipt_status}"),
        _check("receipt_fixture_preserved", receipt.get("summary", {}).get("fixture_preserved") is True, f"fixture_preserved={receipt.get('summary', {}).get('fixture_preserved')}"),
        _check("receipt_path_matches_preflight", _same_path(root, str(qemu_captured_boot_receipt_path), receipt_output_path), f"receipt={qemu_captured_boot_receipt_path}; preflight={receipt_output_path}"),
        _check("receipt_captured_path_matches_preflight", _same_path(root, str(receipt_captured.get("path", "")), captured_evidence_path), f"receipt={receipt_captured.get('path', '')}; preflight={captured_evidence_path}"),
        _check("receipt_fixture_path_matches_input", _same_path(root, str(receipt_fixture.get("path", "")), str(fixture_evidence_path)), f"receipt={receipt_fixture.get('path', '')}; input={fixture_evidence_path}"),
        _check("captured_outputs_separate", preflight.get("summary", {}).get("captured_outputs_separate") is True, f"separate={preflight.get('summary', {}).get('captured_outputs_separate')}"),
    ]

    command_plan = _make_command_plan(
        root=root,
        launcher_script=launcher_script,
        preflight_path=preflight_path,
        shared_contract_path=qemu_shared_folder_contract_path,
        receipt_path=qemu_captured_boot_receipt_path,
        fixture_evidence_path=fixture_evidence_path,
        preflight=preflight,
        shared_contract=shared_contract,
    )
    command_roles = {command["role"] for command in command_plan}
    required_roles = {
        "prepare_shared_folder",
        "captured_preflight",
        "qemu_launch",
        "emit_captured_evidence_only",
        "captured_receipt",
    }
    checks.append(_check("command_plan_complete", required_roles.issubset(command_roles), f"roles={sorted(command_roles)}"))
    checks.append(_check("operator_authority_preserved", True, "commands are emitted for operator execution; QEMU is not launched"))

    failed_checks = [check for check in checks if check.severity == "fail" and not check.ok]
    blocking_checks = [check for check in checks if check.severity == "block" and not check.ok]
    status = "fail" if failed_checks else "blocked" if blocking_checks else "pass"

    release_gate_arguments = [
        "--qemu-captured-boot-preflight",
        str(preflight_path),
        "--qemu-captured-boot-launch-bundle",
        launch_bundle_output,
        "--qemu-captured-boot-evidence",
        captured_evidence_path,
        "--qemu-captured-boot-receipt",
        str(qemu_captured_boot_receipt_path),
    ]
    if release_gate_output:
        release_gate_arguments.extend(["--out", release_gate_output])

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "launch_ready": status == "pass",
        "execution_performed": False,
        "pooleos_root": str(root),
        "inputs": {
            "preflight": str(preflight_path),
            "qemu_shared_folder_contract": str(qemu_shared_folder_contract_path),
            "qemu_captured_boot_receipt": str(qemu_captured_boot_receipt_path),
            "fixture_evidence": str(fixture_evidence_path),
            "launcher_script": str(launcher),
        },
        "expected_outputs": {
            "serial_log_path": str(paths.get("serial_log_path", "")),
            "boot_validation_output": str(paths.get("boot_validation_output", "")),
            "qemu_boot_evidence_output": captured_evidence_path,
            "qemu_captured_boot_receipt_output": str(qemu_captured_boot_receipt_path),
            "launch_bundle_output": launch_bundle_output,
            "release_gate_output": release_gate_output,
        },
        "command_plan": command_plan,
        "release_gate_arguments": release_gate_arguments,
        "checks": [check.to_json() for check in checks],
        "summary": {
            "failed_check_count": len(failed_checks),
            "blocking_check_count": len(blocking_checks),
            "command_count": len(command_plan),
            "preflight_status": preflight_status,
            "preflight_launch_ready": bool(preflight.get("launch_ready", False)),
            "shared_folder_status": shared_status,
            "shared_folder_ready": shared_status == "pass" and shared_folder.get("prepared_for_launch") is True,
            "receipt_status": receipt_status,
            "captured_outputs_separate": preflight.get("summary", {}).get("captured_outputs_separate") is True,
            "execution_performed": False,
        },
        "limitations": [
            "This bundle assembles operator commands only; it does not launch QEMU or mutate host state.",
            "A blocked bundle can still be valid when the captured boot preflight is blocked by missing QEMU or image prerequisites.",
            "Captured boot proof requires qemu_boot_evidence.captured.json from a validated real serial log.",
        ],
        "next_steps": [
            "Resolve any blocking preflight checks, then run the qemu_launch command from this bundle.",
            "After QEMU exits, run captured_receipt or emit_captured_evidence_only if the serial log already exists.",
            "Add the release_gate_arguments from this bundle to the full release-gate command.",
        ],
    }


def write_bundle(bundle: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
