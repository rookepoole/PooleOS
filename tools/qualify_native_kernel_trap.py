#!/usr/bin/env python3
"""Build and qualify the bounded PKTRAP1 BSP exception scenarios."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_kernel_load,
    native_kernel_transfer,
    native_kernel_trap,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / native_kernel_trap.READINESS_RELATIVE
DEFAULT_FRAME_OUT = ROOT / native_kernel_trap.FRAME_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKTRAP1 qualification fails closed."""


def _replace(marker: str, old: str, new: str) -> str:
    if marker.count(old) != 1:
        raise QualificationError(f"mutation source {old!r} is not unique")
    return marker.replace(old, new, 1)


def _mutated(markers: list[str], index: int, old: str, new: str) -> list[str]:
    candidate = markers.copy()
    candidate[index] = _replace(candidate[index], old, new)
    return candidate


def _require_rejection(control_id: str, scenario: str, candidate: list[str]) -> dict[str, str]:
    try:
        native_kernel_trap.validate_markers(candidate, scenario)
    except native_kernel_trap.KernelTrapError:
        return {
            "id": control_id,
            "layer": "live_trap_marker_oracle",
            "expected": "reject",
            "observed": "rejected",
            "status": "pass",
        }
    raise QualificationError(f"PKTRAP1 hostile control did not reject: {control_id}")


def _negative_controls(markers_by_scenario: dict[str, list[str]]) -> list[dict[str, str]]:
    controls: list[dict[str, str]] = []
    ids = iter(native_kernel_trap.NEGATIVE_CONTROL_IDS)
    replacement_scenarios = {
        "returning": "double_fault",
        "double_fault": "malformed_frame",
        "malformed_frame": "returning",
    }
    for scenario, profile in native_kernel_trap.SCENARIOS.items():
        markers = markers_by_scenario[scenario]
        controls.append(_require_rejection(next(ids), scenario, markers[:-1]))
        reordered = markers.copy()
        reordered[29], reordered[30] = reordered[30], reordered[29]
        controls.append(_require_rejection(next(ids), scenario, reordered))
        controls.append(
            _require_rejection(next(ids), scenario, [*markers[:29], markers[29], *markers[29:]])
        )
        controls.append(
            _require_rejection(
                next(ids),
                scenario,
                _mutated(
                    markers,
                    23,
                    f"trap_scenario={profile['selector']}",
                    "trap_scenario=0",
                ),
            )
        )
        controls.append(
            _require_rejection(
                next(ids),
                scenario,
                _mutated(
                    markers,
                    29,
                    f"scenario={scenario}",
                    f"scenario={replacement_scenarios[scenario]}",
                ),
            )
        )
        for old, new in (
            ("gdt_limit=39", "gdt_limit=40"),
            ("idt_limit=4095", "idt_limit=4094"),
            ("gates=5", "gates=4"),
            ("stack_bytes=8192", "stack_bytes=4096"),
            ("if=0", "if=1"),
        ):
            controls.append(
                _require_rejection(next(ids), scenario, _mutated(markers, 29, old, new))
            )

    returning = markers_by_scenario["returning"]
    for index, old, new in (
        (30, "sequence=3,6,14", "sequence=3,14,6"),
        (31, "vector=3", "vector=6"),
        (31, "error=0x0000000000000000", "error=0x0000000000000001"),
        (31, "depth=1", "depth=2"),
        (31, "ist=1", "ist=2"),
        (32, "resume=exact", "resume=skip"),
        (32, "returned=1", "returned=2"),
        (37, "returned=3", "returned=2"),
        (37, "terminal=halt", "terminal=return"),
    ):
        controls.append(
            _require_rejection(next(ids), "returning", _mutated(returning, index, old, new))
        )

    double_fault = markers_by_scenario["double_fault"]
    for index, old, new in (
        (30, "trigger=gp_delivery_failure", "trigger=software_int"),
        (31, "vector=8", "vector=13"),
        (31, "error=0x0000000000000000", "error=0x0000000000000001"),
        (31, "depth=1", "depth=2"),
        (31, "ist=2", "ist=1"),
        (32, "terminal=halt", "terminal=return"),
    ):
        controls.append(
            _require_rejection(
                next(ids), "double_fault", _mutated(double_fault, index, old, new)
            )
        )

    malformed = markers_by_scenario["malformed_frame"]
    for index, old, new in (
        (30, "control=code_selector", "control=error_code"),
        (31, "vector=3", "vector=6"),
        (32, "source=synthetic_semantic", "source=hardware_frame"),
        (32, "control=code_selector", "control=error_code"),
        (33, "rejected=1", "rejected=0"),
        (33, "terminal=halt", "terminal=return"),
    ):
        controls.append(
            _require_rejection(
                next(ids), "malformed_frame", _mutated(malformed, index, old, new)
            )
        )

    try:
        next(ids)
    except StopIteration:
        pass
    else:
        raise QualificationError("PKTRAP1 hostile-control implementation is incomplete")
    if [item["id"] for item in controls] != list(native_kernel_trap.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKTRAP1 hostile-control order changed")
    return controls


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> tuple[dict[str, Any], bytes]:
    contract = native_kernel_trap.read_json(ROOT / native_kernel_trap.CONTRACT_RELATIVE)
    errors = native_kernel_trap.contract_errors(contract)
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
    with tempfile.TemporaryDirectory(
        prefix="pktrap1-qualification-", dir=temporary_parent
    ) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "default-boot",
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot:
            raise QualificationError("default PooleBoot contains the live transfer marker")
        if b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot lost its stop-before-transfer boundary")

        scenario_boots: dict[str, bytes] = {}
        scenario_builds: dict[str, dict[str, Any]] = {}
        for scenario, scenario_profile in native_kernel_trap.SCENARIOS.items():
            boot, build = qualify_native_pooleboot._build_and_test(
                toolchain_root,
                temporary_root / f"{scenario}-boot",
                development_feature=scenario_profile["feature"],
            )
            scenario_boots[scenario] = boot
            scenario_builds[scenario] = build
        all_boot_hashes = {
            native_kernel_trap.sha256_bytes(default_boot),
            *(native_kernel_trap.sha256_bytes(value) for value in scenario_boots.values()),
        }
        if len(all_boot_hashes) != 4:
            raise QualificationError("default and PKTRAP1 PooleBoot profiles are not distinct")

        scenario_evidence: list[dict[str, Any]] = []
        media_evidence: list[dict[str, Any]] = []
        markers_by_scenario: dict[str, list[str]] = {}
        representative_frame = b""
        for scenario, scenario_profile in native_kernel_trap.SCENARIOS.items():
            boot = scenario_boots[scenario]
            media_one = native_kernel_load.build_media_bytes(
                boot, config, manifest, kernel, artifact_files
            )
            media_two = native_kernel_load.build_media_bytes(
                boot, config, manifest, kernel, artifact_files
            )
            if media_one != media_two:
                raise QualificationError(f"two PKTRAP1 {scenario} media generations differ")
            media_inspection = native_kernel_load.inspect_media_bytes(media_one)
            if (
                media_inspection["files"][3]["sha256"]
                != kernel_readiness["product"]["canonical_sha256"]
            ):
                raise QualificationError(f"PKTRAP1 {scenario} media kernel differs from PKENTRY1")
            media_path = temporary_root / f"pktrap1-{scenario}.img"
            media_path.write_bytes(media_one)

            runs: list[dict[str, Any]] = []
            screenshots: list[bytes] = []
            handoffs: list[bytes] = []
            validator: Callable[[list[str]], dict[str, Any]] = (
                lambda markers, selected=scenario: native_kernel_trap.validate_markers(
                    markers, selected
                )
            )
            for run_index in (1, 2):
                with tempfile.TemporaryDirectory(
                    prefix=f"pktrap1-{scenario}-run-{run_index}-", dir=run_parent
                ) as run_temporary:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"{scenario}-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        Path(run_temporary),
                        timeout,
                        marker_validator=validator,
                        marker_extractor=native_kernel_trap.extract_markers,
                        completion_marker=scenario_profile["completion"],
                    )
                    prefix = run["marker_summary"]["transfer_prefix"]
                    try:
                        native_kernel_load.validate_oracle_binding(
                            prefix["boot_prefix"], media_inspection, run["pbp1_transcript"]
                        )
                        transcript_binding = native_kernel_transfer.validate_transcript_binding(
                            prefix, run["pbp1_transcript"]
                        )
                        revalidation = native_kernel_transfer.validate_revalidation_binding(
                            prefix, handoff, retained_files
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
                raise QualificationError(f"two PKTRAP1 {scenario} runs emitted different markers")
            if screenshots[0] != screenshots[1]:
                raise QualificationError(f"two PKTRAP1 {scenario} runs produced different frames")
            if handoffs[0] != handoffs[1]:
                raise QualificationError(f"two PKTRAP1 {scenario} runs produced different PBP1")
            markers_by_scenario[scenario] = runs[0]["markers"]
            if not representative_frame:
                representative_frame = screenshots[0]
            scenario_evidence.append(
                {
                    "scenario": scenario,
                    "selector": scenario_profile["selector"],
                    "feature": scenario_profile["feature"],
                    "run_count": 2,
                    "marker_count": scenario_profile["marker_count"],
                    "exact_marker_match": True,
                    "exact_screenshot_match": True,
                    "exact_pbp1_match": True,
                    "runs": runs,
                }
            )
            media_evidence.append(
                {
                    "scenario": scenario,
                    "clean_generation_count": 2,
                    "exact_clean_generation_match": True,
                    "sha256": native_kernel_trap.sha256_bytes(media_one),
                    "byte_count": len(media_one),
                    "inspection": media_inspection,
                    "ordinary_workspace_file_only": True,
                    "physical_media_write_performed": False,
                }
            )

    controls = _negative_controls(markers_by_scenario)
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    claims = native_kernel_trap.expected_claims()
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_trap_readiness",
        "status_date": status_date,
        "status": "pass_single_host_six_run_qemu_only_bsp_non_promoting",
        "contract_id": native_kernel_trap.CONTRACT_ID,
        "selected_move_id": native_kernel_trap.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n7_exit_gate_satisfied": False,
        "phase_status": {"N7": "partial", "N7.5": "partial", "N7.6": "partial"},
        "inputs": native_kernel_trap.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "scenario_pooleboot": scenario_builds,
            "profile_count": 4,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
        },
        "media": {
            "scenario_count": 3,
            "clean_generation_count": 6,
            "scenarios": media_evidence,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 6,
            "profile_id": "bootstrap-debug",
            "machine": "pc-q35-11.0",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": native_kernel_trap.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "scenarios": scenario_evidence,
        },
        "negative_controls": controls,
        "claims": claims,
        "non_claims": contract["non_claims"],
        "summary": {
            "scenario_count": 3,
            "qemu_run_count": 6,
            "returning_exception_count": 3,
            "terminal_double_fault_count": 1,
            "malformed_frame_rejection_count": 1,
            "negative_controls_passed": len(controls),
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "state_writes": 0,
            "firmware_calls_after_exit": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Install guarded per-CPU RSP0/IST stacks and descriptor tables during AP bring-up.",
            "Install and qualify all architected exception vectors, external interrupts, NMI, and machine check.",
            "Preserve and validate complete asynchronous integer, SIMD, FPU, debug, and extended state.",
            "Add recursion policy, persistent crash records, recovery routing, and adversarial stack exhaustion.",
            "Complete N7.1-N7.4 CPU feature, errata, control-register, MSR, and extended-state policy.",
            "Reproduce on a second host, target firmware, and physical hardware before any N7 exit claim.",
        ],
    }
    errors = native_kernel_trap.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report, representative_frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--frame-out", type=Path, default=DEFAULT_FRAME_OUT)
    parser.add_argument("--status-date", default="2026-07-21")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report, frame = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
        args.frame_out.parent.mkdir(parents=True, exist_ok=True)
        args.frame_out.write_bytes(frame)
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        native_kernel_trap.KernelTrapError,
        native_tier0.Tier0Error,
    ) as error:
        parser.exit(1, f"PKTRAP1 qualification failed: {error}\n")
    print(
        "PKTRAP1 qualification passed: "
        f"scenarios={report['summary']['scenario_count']}; "
        f"runs={report['summary']['qemu_run_count']}; "
        f"negative={report['summary']['negative_controls_passed']}; "
        f"kernel_sha256={report['build']['kernel_entry']['product']['canonical_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
