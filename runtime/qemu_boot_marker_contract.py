"""Kernel-facing QEMU boot marker contract for PooleOS Lab."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime import boot_log


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_boot_marker_contract"
PROFILE = "trap-input"


@dataclass(frozen=True)
class ContractCheck:
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


def _check(name: str, ok: bool, detail: str, *, severity: str = "fail") -> ContractCheck:
    return ContractCheck(name=name, severity=severity, ok=ok, detail=detail)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _post_capture_by_role(dry_run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for item in dry_run.get("post_capture_files", []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        if role:
            files[role] = item
    return files


def _file_roles(files_by_role: dict[str, dict[str, Any]], roles: list[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for role in roles:
        item = files_by_role.get(role, {})
        result.append(
            {
                "role": role,
                "path": str(item.get("path", "")),
            }
        )
    return result


def _kernel_boundary(owner: str) -> dict[str, Any]:
    return {
        "owner": owner,
        "kernel_boundary_claimed": False,
        "pgvm2_execution_claimed": False,
        "contract_claim": "serial_marker_and_artifact_routing_only",
        "handoff_rule": (
            "A marker proves only that the lab guest script emitted that string on the serial path; "
            "PooleOS kernel or PGVM2 enforcement requires separate captured boot and kernel evidence."
        ),
    }


def _marker_map(
    *,
    marker: str,
    sequence: int,
    phase: str,
    emitter: str,
    source_file: Path,
    marker_text: str,
    owner: str,
    trap_bundle_role: str,
    evidence_roles: list[str],
    files_by_role: dict[str, dict[str, Any]],
    guest_evidence_path: str = "",
) -> dict[str, Any]:
    return {
        "marker": marker,
        "sequence": sequence,
        "phase": phase,
        "emitter": emitter,
        "source_file": str(source_file),
        "source_marker_text": marker_text,
        "source_file_exists": source_file.exists(),
        "trap_bundle_role": trap_bundle_role,
        "guest_evidence_path": guest_evidence_path,
        "captured_evidence_files": _file_roles(files_by_role, evidence_roles),
        "responsibility_boundary": _kernel_boundary(owner),
    }


def make_qemu_boot_marker_contract(
    *,
    root: Path,
    dry_run_checklist_path: Path | None = None,
    lab_guest_autostart_path: Path | None = None,
) -> dict[str, Any]:
    dry_run = _read_json(dry_run_checklist_path)
    autostart = _read_json(lab_guest_autostart_path)
    overlay = root / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "rootfs_overlay"
    init_script = overlay / "etc" / "init.d" / "S99pooleos-lab"
    smoke_script = overlay / "usr" / "bin" / "pooleos-lab-smoke"
    verify_wrapper = overlay / "usr" / "bin" / "pooleos-lab-verify-input"
    doctor_wrapper = overlay / "usr" / "bin" / "pooleos-lab-doctor"
    release_gate_wrapper = overlay / "usr" / "bin" / "pooleos-lab-release-gate"

    expected_markers = boot_log.required_markers_for_profile(PROFILE)
    dry_run_markers = [str(marker) for marker in dry_run.get("expected_serial_markers", [])]
    autostart_markers = (
        autostart.get("boot_log_profile", {}).get("required_markers", [])
        if isinstance(autostart.get("boot_log_profile"), dict)
        else []
    )
    autostart_markers = [str(marker) for marker in autostart_markers]
    files_by_role = _post_capture_by_role(dry_run)

    init_text = _read_text(init_script)
    smoke_text = _read_text(smoke_script)
    marker_mappings = [
        _marker_map(
            marker="POOLEOS_LAB_AUTOSTART_START",
            sequence=1,
            phase="guest_init_start",
            emitter="/etc/init.d/S99pooleos-lab",
            source_file=init_script,
            marker_text='echo "POOLEOS_LAB_AUTOSTART_START"',
            owner="guest_init_overlay",
            trap_bundle_role="none",
            evidence_roles=["serial_log"],
            files_by_role=files_by_role,
        ),
        _marker_map(
            marker="POOLEOS_LAB_SHARED_MOUNT_PASS",
            sequence=2,
            phase="shared_folder_mount",
            emitter="/etc/init.d/S99pooleos-lab",
            source_file=init_script,
            marker_text='echo "POOLEOS_LAB_SHARED_MOUNT_PASS"',
            owner="guest_init_shared_folder_mount",
            trap_bundle_role="mounts_host_staged_trap_bundle_channel",
            evidence_roles=["serial_log", "captured_boot_evidence"],
            files_by_role=files_by_role,
        ),
        _marker_map(
            marker="POOLEOS_LAB_INPUT_VERIFY_PASS",
            sequence=3,
            phase="trap_bundle_verification",
            emitter="/usr/bin/pooleos-lab-smoke -> pooleos-lab-verify-input",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_INPUT_VERIFY_PASS"',
            owner="guest_trap_bundle_verifier",
            trap_bundle_role="verifies input.pgb2.json, input.replay.json, and pooleos_boot_trap_bundle_manifest.json",
            evidence_roles=["serial_log", "boot_validation", "captured_boot_evidence"],
            files_by_role=files_by_role,
            guest_evidence_path="/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
        ),
        _marker_map(
            marker="POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS",
            sequence=4,
            phase="trap_abi_boundary_verification",
            emitter="/usr/bin/pooleos-lab-smoke -> pooleos-lab-verify-input",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS"',
            owner="guest_trap_abi_boundary_verifier",
            trap_bundle_role="verifies staged pgb2_trap_abi_boundary_receipt.json remains draft/non-promoting",
            evidence_roles=["serial_log", "boot_validation", "captured_boot_evidence"],
            files_by_role=files_by_role,
            guest_evidence_path="/var/lib/pooleos/runs/boot_trap_bundle_verification.json",
        ),
        _marker_map(
            marker="POOLEOS_LAB_BOOT_START",
            sequence=5,
            phase="guest_smoke_start",
            emitter="/usr/bin/pooleos-lab-smoke",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_BOOT_START"',
            owner="guest_smoke_script",
            trap_bundle_role="none",
            evidence_roles=["serial_log"],
            files_by_role=files_by_role,
        ),
        _marker_map(
            marker="POOLEOS_LAB_DOCTOR_PASS",
            sequence=6,
            phase="guest_doctor",
            emitter="/usr/bin/pooleos-lab-smoke -> pooleos-lab-doctor",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_DOCTOR_PASS"',
            owner="guest_doctor_wrapper",
            trap_bundle_role="none",
            evidence_roles=["serial_log", "captured_boot_evidence"],
            files_by_role=files_by_role,
            guest_evidence_path=str(doctor_wrapper),
        ),
        _marker_map(
            marker="POOLEOS_LAB_RELEASE_GATE_PASS",
            sequence=7,
            phase="guest_release_gate",
            emitter="/usr/bin/pooleos-lab-smoke -> pooleos-lab-release-gate",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_RELEASE_GATE_PASS"',
            owner="guest_release_gate_wrapper",
            trap_bundle_role="validates staged trap bundle and replay proof when present",
            evidence_roles=["serial_log", "release_gate", "captured_boot_evidence"],
            files_by_role=files_by_role,
            guest_evidence_path=str(release_gate_wrapper),
        ),
        _marker_map(
            marker="POOLEOS_LAB_ARTIFACT_EXPORT_PASS",
            sequence=8,
            phase="guest_artifact_export",
            emitter="/usr/bin/pooleos-lab-smoke",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_ARTIFACT_EXPORT_PASS"',
            owner="guest_artifact_export",
            trap_bundle_role="exports guest run artifacts to mounted host folder",
            evidence_roles=["serial_log", "boot_validation", "captured_boot_evidence", "captured_boot_receipt", "release_gate"],
            files_by_role=files_by_role,
        ),
        _marker_map(
            marker="POOLEOS_LAB_BOOT_DONE",
            sequence=9,
            phase="guest_smoke_done",
            emitter="/usr/bin/pooleos-lab-smoke",
            source_file=smoke_script,
            marker_text='echo "POOLEOS_LAB_BOOT_DONE"',
            owner="guest_smoke_script",
            trap_bundle_role="none",
            evidence_roles=["serial_log", "captured_boot_evidence"],
            files_by_role=files_by_role,
        ),
        _marker_map(
            marker="POOLEOS_LAB_AUTOSTART_DONE",
            sequence=10,
            phase="guest_init_done",
            emitter="/etc/init.d/S99pooleos-lab",
            source_file=init_script,
            marker_text='echo "POOLEOS_LAB_AUTOSTART_DONE"',
            owner="guest_init_overlay",
            trap_bundle_role="none",
            evidence_roles=["serial_log", "captured_boot_evidence"],
            files_by_role=files_by_role,
        ),
    ]

    mapped_markers = [mapping["marker"] for mapping in marker_mappings]
    marker_sources_ok = all(
        (mapping["source_marker_text"] in init_text or mapping["source_marker_text"] in smoke_text)
        for mapping in marker_mappings
    )
    boundary_count = sum(1 for mapping in marker_mappings if mapping.get("responsibility_boundary"))
    post_capture_roles = set(files_by_role)
    required_post_capture_roles = {"serial_log", "boot_validation", "captured_boot_evidence", "captured_boot_receipt"}
    dry_run_status = str(dry_run.get("status", ""))
    autostart_status = str(autostart.get("status", ""))

    checks = [
        _check("execution_not_performed", True, "contract assembly is non-mutating"),
        _check("boot_evidence_not_claimed", True, "boot_evidence_claimed=False"),
        _check("security_boundary_not_claimed", True, "security_boundary_claimed=False"),
        _check("dry_run_checklist_present", bool(dry_run) and dry_run_checklist_path is not None and dry_run_checklist_path.exists(), str(dry_run_checklist_path or "")),
        _check("dry_run_checklist_artifact_kind", dry_run.get("artifact_kind") == "pooleos.qemu_captured_boot_dry_run_checklist", str(dry_run.get("artifact_kind", ""))),
        _check("dry_run_checklist_status_usable", dry_run_status in {"pass", "blocked"}, f"status={dry_run_status}"),
        _check("dry_run_has_no_failed_checks", dry_run.get("summary", {}).get("failed_check_count") == 0, f"failed={dry_run.get('summary', {}).get('failed_check_count')}"),
        _check("dry_run_blockers_preserved", dry_run_status != "blocked", f"status={dry_run_status}", severity="block"),
        _check("lab_guest_autostart_present", bool(autostart) and lab_guest_autostart_path is not None and lab_guest_autostart_path.exists(), str(lab_guest_autostart_path or "")),
        _check("lab_guest_autostart_artifact_kind", autostart.get("artifact_kind") == "pooleos.lab_guest_autostart", str(autostart.get("artifact_kind", ""))),
        _check("lab_guest_autostart_status_pass", autostart_status == "pass", f"status={autostart_status}"),
        _check("expected_marker_sequence_complete", mapped_markers == expected_markers, f"mapped={len(mapped_markers)} expected={len(expected_markers)}"),
        _check("dry_run_marker_sequence_matches", dry_run_markers == expected_markers, f"dry_run={len(dry_run_markers)} expected={len(expected_markers)}"),
        _check("autostart_marker_sequence_matches", autostart_markers == expected_markers, f"autostart={len(autostart_markers)} expected={len(expected_markers)}"),
        _check("source_files_present", init_script.exists() and smoke_script.exists() and verify_wrapper.exists(), f"init={init_script.exists()}; smoke={smoke_script.exists()}; verifier={verify_wrapper.exists()}"),
        _check("source_marker_text_present", marker_sources_ok, "all marker echo lines found in init or smoke scripts"),
        _check("post_capture_roles_present", required_post_capture_roles.issubset(post_capture_roles), f"roles={sorted(post_capture_roles)}"),
        _check("boundary_record_per_marker", boundary_count == len(expected_markers), f"boundaries={boundary_count}"),
    ]
    failed_checks = [check for check in checks if check.severity == "fail" and not check.ok]
    blocking_checks = [check for check in checks if check.severity == "block" and not check.ok]
    status = "fail" if failed_checks else "blocked" if blocking_checks else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "profile": PROFILE,
        "execution_performed": False,
        "boot_evidence_claimed": False,
        "security_boundary_claimed": False,
        "source_inputs": {
            "dry_run_checklist_path": str(dry_run_checklist_path or ""),
            "dry_run_status": dry_run_status,
            "lab_guest_autostart_path": str(lab_guest_autostart_path or ""),
            "lab_guest_autostart_status": autostart_status,
        },
        "kernel_pgvm2_boundary": {
            "current_contract_owner": "Buildroot lab overlay plus host validators",
            "future_contract_owner": "PooleOS kernel PGVM2 loader and enforcement boundary",
            "kernel_boundary_claimed": False,
            "pgvm2_execution_claimed": False,
            "claim_boundary": "This artifact maps marker ownership and evidence flow only.",
            "required_before_kernel_claim": [
                "Captured QEMU serial evidence with trap-input profile validation.",
                "Guest-exported boot_trap_bundle_verification.json tied to the captured boot.",
                "Kernel or PGVM2 loader evidence showing enforcement, not only lab shell scripts.",
            ],
        },
        "marker_contract": {
            "profile": PROFILE,
            "sequence_source": "runtime.boot_log.required_markers_for_profile('trap-input')",
            "required_markers": expected_markers,
        },
        "marker_mappings": marker_mappings,
        "checks": [check.to_json() for check in checks],
        "summary": {
            "failed_check_count": len(failed_checks),
            "blocking_check_count": len(blocking_checks),
            "marker_count": len(marker_mappings),
            "expected_marker_count": len(expected_markers),
            "boundary_count": boundary_count,
            "post_capture_file_count": len(files_by_role),
            "dry_run_status": dry_run_status,
            "execution_performed": False,
            "boot_evidence_claimed": False,
            "security_boundary_claimed": False,
        },
        "limitations": [
            "This is a marker responsibility contract, not a QEMU launch.",
            "Serial markers prove lab script path reachability only when tied to captured serial evidence.",
            "PooleGlyph and PGVM2 runtime semantics remain separate from this marker map until bridge and kernel evidence are generated.",
        ],
        "next_steps": [
            "Bind marker emitters to Buildroot overlay file hashes.",
            "After real QEMU capture, compare observed serial marker order against this contract.",
            "Promote only kernel-owned checks once PGVM2 loader evidence exists.",
        ],
    }


def write_contract(contract: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
