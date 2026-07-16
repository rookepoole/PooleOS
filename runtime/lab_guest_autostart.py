"""Static evidence for PooleOS Lab guest autostart and shared-folder mount."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime import boot_log


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.lab_guest_autostart"
MOUNT_TAG = "pooleos_output"
MOUNT_POINT = "/mnt/pooleos-output"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def make_lab_guest_autostart(
    *,
    root: Path,
    qemu_shared_folder_contract_path: Path | None = None,
) -> dict[str, Any]:
    overlay = root / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "rootfs_overlay"
    init_script = overlay / "etc" / "init.d" / "S99pooleos-lab"
    smoke_script = overlay / "usr" / "bin" / "pooleos-lab-smoke"
    verify_wrapper = overlay / "usr" / "bin" / "pooleos-lab-verify-input"
    post_build = root / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "post-build.sh"
    defconfig = root / "lab-os" / "buildroot" / "external" / "configs" / "pooleos_lab_x86_64_defconfig"
    init_text = _read_text(init_script)
    smoke_text = _read_text(smoke_script)
    wrapper_text = _read_text(verify_wrapper)
    post_build_text = _read_text(post_build)
    defconfig_text = _read_text(defconfig)
    qemu_contract = _read_json(qemu_shared_folder_contract_path)
    qemu_shared = qemu_contract.get("shared_folder", {}) if isinstance(qemu_contract.get("shared_folder", {}), dict) else {}

    trap_profile_markers = boot_log.required_markers_for_profile("trap-input")
    init_markers = ["POOLEOS_LAB_AUTOSTART_START", "POOLEOS_LAB_SHARED_MOUNT_PASS", "POOLEOS_LAB_AUTOSTART_DONE"]
    checks = [
        _check("init_script_present", init_script.exists(), str(init_script)),
        _check("init_script_mounts_9p", "mount -t 9p" in init_text and MOUNT_TAG in init_text, f"mount_tag={MOUNT_TAG}"),
        _check("init_script_runs_smoke", "pooleos-lab-smoke" in init_text, str(init_script)),
        _check(
            "init_script_markers_present",
            all(marker in init_text for marker in init_markers),
            f"markers={init_markers}",
        ),
        _check("smoke_input_verify_present", "pooleos-lab-verify-input" in smoke_text, str(smoke_script)),
        _check("smoke_input_verify_marker", "POOLEOS_LAB_INPUT_VERIFY_PASS" in smoke_text, str(smoke_script)),
        _check("smoke_abi_boundary_marker", "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in smoke_text, str(smoke_script)),
        _check("verify_wrapper_present", verify_wrapper.exists() and "pooleos_lab_verify_input.py" in wrapper_text, str(verify_wrapper)),
        _check("post_build_chmods_init", "S99pooleos-lab" in post_build_text and "chmod +x" in post_build_text, str(post_build)),
        _check("defconfig_uses_overlay", "BR2_ROOTFS_OVERLAY" in defconfig_text, str(defconfig)),
        _check(
            "boot_log_trap_input_profile_ready",
            "POOLEOS_LAB_INPUT_VERIFY_PASS" in trap_profile_markers
            and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in trap_profile_markers
            and "POOLEOS_LAB_SHARED_MOUNT_PASS" in trap_profile_markers
            and "POOLEOS_LAB_AUTOSTART_DONE" in trap_profile_markers,
            f"profile_markers={trap_profile_markers}",
        ),
        _check(
            "qemu_contract_mount_tag_matches",
            not qemu_contract or (qemu_contract.get("status") == "pass" and qemu_shared.get("mount_tag") == MOUNT_TAG),
            "not provided" if not qemu_contract else f"status={qemu_contract.get('status')}; mount_tag={qemu_shared.get('mount_tag')}",
        ),
        _check("boot_evidence_not_claimed", True, "boot_evidence_claimed=False"),
    ]
    failed = [check for check in checks if not check["ok"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "boot_evidence_claimed": False,
        "guest_autostart": {
            "init_script_path": str(init_script),
            "init_order": "S99",
            "smoke_command": "pooleos-lab-smoke",
            "mount_tag": MOUNT_TAG,
            "mount_point": MOUNT_POINT,
            "mount_type": "9p",
            "mount_options": "trans=virtio,version=9p2000.L",
        },
        "qemu_shared_folder_contract": {
            "artifact_path": str(qemu_shared_folder_contract_path or ""),
            "status": str(qemu_contract.get("status", "")),
            "mount_tag": str(qemu_shared.get("mount_tag", "")),
            "host_path": str(qemu_shared.get("host_path", "")),
        },
        "boot_log_profile": {
            "profile": "trap-input",
            "required_markers": trap_profile_markers,
        },
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "required_marker_count": len(trap_profile_markers),
            "autostart_marker_count": len(init_markers),
            "qemu_contract_bound": bool(qemu_contract),
        },
        "limitations": [
            "This is static overlay evidence; it does not prove a QEMU guest has booted.",
            "Shared-folder mount success still requires a real QEMU launch with the matching virtfs tag.",
            "Trap input verification becomes boot evidence only after serial logs contain the trap-input profile markers.",
        ],
        "next_steps": [
            "Build the Lab image and boot it with the staged QEMU shared folder.",
            "Validate the serial log with --profile trap-input.",
            "Collect boot_trap_bundle_verification.json from the shared output folder.",
        ],
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
