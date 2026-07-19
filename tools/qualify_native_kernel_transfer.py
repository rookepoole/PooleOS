#!/usr/bin/env python3
"""Build and qualify the QEMU-only PKXFER1 PooleKernel transfer twice."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (
    native_kernel_load,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / native_kernel_transfer.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKXFER1 qualification fails closed."""


def _replace_field(marker: str, key: str, value: str) -> str:
    tokens = marker.split(" ")
    prefix = f"{key}="
    matches = [index for index, token in enumerate(tokens) if token.startswith(prefix)]
    if len(matches) != 1:
        raise QualificationError(f"field {key!r} is not unique in marker")
    tokens[matches[0]] = prefix + value
    return " ".join(tokens)


def _mutated_field(markers: list[str], index: int, key: str, value: str) -> list[str]:
    candidate = markers.copy()
    candidate[index] = _replace_field(candidate[index], key, value)
    return candidate


def _require_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    try:
        native_kernel_transfer.validate_markers(candidate)
    except native_kernel_transfer.KernelTransferError:
        return {
            "id": control_id,
            "layer": "live_transfer_marker_oracle",
            "expected": "reject",
            "observed": "rejected",
            "status": "pass",
        }
    raise QualificationError(f"PKXFER1 hostile control did not reject: {control_id}")


def _negative_controls(markers: list[str]) -> list[dict[str, str]]:
    controls = [
        _require_rejection(native_kernel_transfer.NEGATIVE_CONTROL_IDS[0], markers[:-1]),
        _require_rejection(
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[1],
            [*markers[:23], markers[24], markers[23], *markers[25:]],
        ),
        _require_rejection(
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[2],
            [*markers[:24], markers[23], *markers[24:]],
        ),
    ]
    mutations = (
        (23, "contract", "PKXFER2"),
        (23, "mode", "production"),
        (23, "emulator_only", "0"),
        (23, "entry", "FFFFFFFF80009000"),
        (23, "handoff", "FFFFFFFF80051000"),
        (23, "bytes", "5009"),
        (23, "stack_top", "FFFFFFFF80049008"),
        (23, "root", "000000001DE50000"),
        (23, "cr3", "000000001DE4F001"),
        (23, "signatures", "1"),
        (23, "authority", "1"),
        (23, "actions", "1"),
        (23, "writes", "1"),
        (23, "firmware_calls_after_exit", "1"),
    )
    for control_id, mutation in zip(
        native_kernel_transfer.NEGATIVE_CONTROL_IDS[3:17], mutations, strict=True
    ):
        controls.append(_require_rejection(control_id, _mutated_field(markers, *mutation)))
    boundary = markers.copy()
    boundary[24] = boundary[24].replace("transfer=one_way_development", "transfer=returned")
    controls.append(_require_rejection(native_kernel_transfer.NEGATIVE_CONTROL_IDS[17], boundary))

    mutation_groups = (
        (
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[18:23],
            (
                (25, "contract", "PKENTRY2"),
                (25, "transfer_contract", "PKXFER2"),
                (25, "build", "PKBUILD1-MUTATED"),
                (25, "entry_count", "2"),
                (25, "serial", "absent"),
            ),
        ),
        (
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[23:31],
            (
                (26, "handoff", "0xFFFFFFFF80051000"),
                (26, "bytes", "5009"),
                (26, "entry", "0xFFFFFFFF80009000"),
                (26, "stack_top", "0xFFFFFFFF80049008"),
                (26, "root", "0x000000001DE50000"),
                (26, "cr3", "0x000000001DE4F001"),
                (26, "rflags_if", "1"),
                (26, "rflags_df", "1"),
            ),
        ),
        (
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[31:35],
            (
                (27, "profile", "production"),
                (27, "records", "3"),
                (27, "artifacts", "9"),
                (27, "production_profile_valid", "1"),
            ),
        ),
        (
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[35:48],
            (
                (28, "contract", "PKREVAL2"),
                (28, "files", "8"),
                (28, "artifacts", "5"),
                (28, "parsers", "8"),
                (28, "manifest_bytes", "1"),
                (28, "retained_bytes", "1"),
                (28, "retained_set_sha256", "0" * 64),
                (28, "policy_sha256", "0" * 64),
                (28, "state_sha256", "0" * 64),
                (28, "denial", "none"),
                (28, "authority", "1"),
                (28, "actions", "1"),
                (28, "writes", "1"),
            ),
        ),
        (
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[48:56],
            (
                (29, "contract", "PKXFER2"),
                (29, "terminal", "return"),
                (29, "entry_count", "2"),
                (29, "post_exit_firmware_calls", "1"),
                (29, "signatures", "1"),
                (29, "authority", "1"),
                (29, "actions", "1"),
                (29, "writes", "1"),
            ),
        ),
    )
    for control_ids, group in mutation_groups:
        for control_id, mutation in zip(control_ids, group, strict=True):
            controls.append(_require_rejection(control_id, _mutated_field(markers, *mutation)))
    controls.append(
        _require_rejection(
            native_kernel_transfer.NEGATIVE_CONTROL_IDS[56],
            [*markers, "POOLEOS:KERNEL:RETURN FAIL contract=PKXFER1"],
        )
    )
    if [item["id"] for item in controls] != list(native_kernel_transfer.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKXFER1 hostile-control order changed")
    return controls


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> tuple[dict[str, Any], bytes]:
    contract = native_kernel_transfer.read_json(ROOT / native_kernel_transfer.CONTRACT_RELATIVE)
    errors = native_kernel_transfer.contract_errors(contract)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)

    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(
        manifest, kernel, artifact_files
    )

    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkxfer1-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        transfer_boot, transfer_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "transfer-boot",
            development_transfer=True,
        )
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "default-boot",
        )
        if transfer_boot == default_boot:
            raise QualificationError("feature-disabled and transfer-enabled PooleBoot binaries match")
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot:
            raise QualificationError("default PooleBoot contains the live transfer marker")
        if b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot lost its stop-before-transfer boundary")

        media_one = native_kernel_load.build_media_bytes(
            transfer_boot, config, manifest, kernel, artifact_files
        )
        media_two = native_kernel_load.build_media_bytes(
            transfer_boot, config, manifest, kernel, artifact_files
        )
        if media_one != media_two:
            raise QualificationError("two PKXFER1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKXFER1 media kernel differs from fresh PKENTRY1")
        media_path = temporary_root / "pkxfer1.img"
        media_path.write_bytes(media_one)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkxfer1-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                    f"run-{run_index}",
                    lock,
                    profile,
                    qemu_root,
                    media_path,
                    Path(run_temporary),
                    timeout,
                    marker_validator=native_kernel_transfer.validate_markers,
                    marker_extractor=native_kernel_transfer.extract_markers,
                    completion_marker=native_kernel_transfer.COMPLETION_MARKER,
                )
                marker_summary = run["marker_summary"]
                try:
                    native_kernel_load.validate_oracle_binding(
                        marker_summary["boot_prefix"],
                        media_inspection,
                        run["pbp1_transcript"],
                    )
                    transcript_binding = native_kernel_transfer.validate_transcript_binding(
                        marker_summary, run["pbp1_transcript"]
                    )
                    revalidation = native_kernel_transfer.validate_revalidation_binding(
                        marker_summary, handoff, retained_files
                    )
                except (
                    native_kernel_load.KernelLoadError,
                    native_kernel_transfer.KernelTransferError,
                ) as error:
                    raise QualificationError(str(error)) from error
                run["transcript_binding"] = transcript_binding
                run["independent_kernel_revalidation"] = revalidation
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)

    if runs[0]["markers"] != runs[1]["markers"]:
        raise QualificationError("two PKXFER1 runs emitted different marker sequences")
    if screenshots[0] != screenshots[1]:
        raise QualificationError("two PKXFER1 runs produced different GOP frame bytes")
    if handoffs[0] != handoffs[1]:
        raise QualificationError("two PKXFER1 runs produced different final PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    claims = native_kernel_transfer.expected_claims()
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_transfer_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu_only_unsigned_terminal_non_promoting",
        "contract_id": native_kernel_transfer.CONTRACT_ID,
        "selected_move_id": native_kernel_transfer.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.1": "partial", "N5.4": "partial", "N5.5": "partial", "N5.8": "partial", "N5.9": "partial"},
        "inputs": {
            "contract": native_kernel_transfer.file_binding(ROOT / native_kernel_transfer.CONTRACT_RELATIVE),
            "toolchain_lock": native_kernel_transfer.file_binding(ROOT / "specs/native-toolchain-lock.json"),
            "tier0_lock": native_kernel_transfer.file_binding(ROOT / "specs/native-tier0-lock.json"),
            "tier0_profile": native_kernel_transfer.file_binding(ROOT / "specs/native-tier0-profile.json"),
            "implementation_inputs": [
                native_kernel_transfer.file_binding(ROOT / path)
                for path in native_kernel_transfer.IMPLEMENTATION_INPUTS
            ],
        },
        "build": {
            "kernel_entry": kernel_readiness,
            "transfer_pooleboot": transfer_build,
            "default_pooleboot": default_build,
            "development_transfer_feature": True,
            "default_feature_enabled": False,
            "default_and_transfer_binaries_differ": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": native_kernel_transfer.sha256_bytes(media_one),
            "byte_count": len(media_one),
            "inspection": media_inspection,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "bootstrap-debug",
            "machine": "pc-q35-11.0",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": native_kernel_transfer.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
        },
        "negative_controls": controls,
        "claims": claims,
        "non_claims": contract["non_claims"],
        "summary": {
            "marker_count": native_kernel_transfer.MARKER_COUNT,
            "kernel_marker_count": native_kernel_transfer.KERNEL_MARKER_COUNT,
            "retained_file_count": 9,
            "negative_controls_passed": len(controls),
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "state_writes": 0,
            "firmware_calls_after_exit": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Define and qualify the authenticated production PKENTRY1 profile with trusted signatures and measured-boot evidence.",
            "Replace inherited framebuffer translation with an explicit final cache policy and revoke the temporary identity mapping.",
            "Qualify target firmware and physical hardware under a separately defined safe procedure despite the owner's broad authorization.",
            "Reproduce exact product, media, markers, PBP1 bytes, and frame on a second independent host.",
            "Implement GDT, IDT, TSS, exception containment, physical and virtual memory initialization, capabilities, scheduling, IPC, and initial user space.",
            "Complete all remaining N5-N39 gates before ISO publication or production promotion."
        ],
    }
    errors = native_kernel_transfer.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report, screenshots[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--screenshot-out", type=Path)
    parser.add_argument("--status-date", default="2026-07-18")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report, screenshot = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
        if args.screenshot_out is not None:
            args.screenshot_out.parent.mkdir(parents=True, exist_ok=True)
            args.screenshot_out.write_bytes(screenshot)
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        native_kernel_transfer.KernelTransferError,
        native_tier0.Tier0Error,
    ) as error:
        parser.exit(1, f"PKXFER1 qualification failed: {error}\n")
    print(
        "PKXFER1 qualification passed: "
        f"runs={report['execution']['run_count']}; "
        f"markers={report['summary']['marker_count']}; "
        f"negative={report['summary']['negative_controls_passed']}; "
        f"kernel_sha256={report['build']['kernel_entry']['product']['canonical_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
