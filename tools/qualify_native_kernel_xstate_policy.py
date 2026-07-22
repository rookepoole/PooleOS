#!/usr/bin/env python3
"""Build and qualify the bounded PKXSTATE1 x87/SSE XSAVE profile."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_kernel_load,
    native_kernel_transfer,
    native_kernel_xstate_policy as xstate,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains/rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / xstate.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKXSTATE1 qualification fails closed."""


def _hex(value: int) -> str:
    return f"0x{value & ((1 << 64) - 1):016X}"


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKXSTATE1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _require_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    try:
        xstate.validate_markers(candidate)
    except xstate.KernelXstatePolicyError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKXSTATE1 hostile control did not reject: {control_id}")


def _negative_controls(markers: list[str]) -> list[dict[str, str]]:
    summary = xstate.validate_markers(markers)
    cap = summary["capability"]
    config = summary["config"]

    candidates: dict[str, list[str]] = {}
    candidates["NEG-N7-PKXSTATE-MARKER-OMISSION"] = markers[:-1]
    ordered = markers.copy()
    ordered[29], ordered[30] = ordered[30], ordered[29]
    candidates["NEG-N7-PKXSTATE-MARKER-ORDER"] = ordered
    candidates["NEG-N7-PKXSTATE-MARKER-DUPLICATE"] = [*markers, markers[-1]]

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    candidates["NEG-N7-PKXSTATE-SELECTOR"] = changed(23, "trap_scenario", "4")
    candidates["NEG-N7-PKXSTATE-CONTRACT"] = changed(29, "contract", "PKXSTATE2")
    candidates["NEG-N7-PKXSTATE-XSAVE-FEATURE"] = changed(
        29, "leaf1_ecx", _hex(cap["leaf1_ecx"] & ~(1 << 26))
    )
    candidates["NEG-N7-PKXSTATE-OSXSAVE-FEATURE"] = changed(
        29, "leaf1_ecx", _hex(cap["leaf1_ecx"] & ~(1 << 27))
    )
    candidates["NEG-N7-PKXSTATE-SSE2-FEATURE"] = changed(
        29, "leaf1_edx", _hex(cap["leaf1_edx"] & ~(1 << 26))
    )
    candidates["NEG-N7-PKXSTATE-XCR0-SUPPORT"] = changed(29, "supported_xcr0", _hex(1))
    candidates["NEG-N7-PKXSTATE-XSAVES"] = changed(
        29, "leafd1_eax", _hex(cap["leaf_d1_eax"] | (1 << 3))
    )
    candidates["NEG-N7-PKXSTATE-ENABLED-SIZE-LOW"] = changed(29, "enabled_bytes", "575")
    candidates["NEG-N7-PKXSTATE-ENABLED-SIZE-HIGH"] = changed(29, "enabled_bytes", "4097")
    candidates["NEG-N7-PKXSTATE-MAXIMUM-SIZE"] = changed(
        29, "maximum_bytes", str(cap["enabled_area_bytes"] - 1)
    )
    candidates["NEG-N7-PKXSTATE-CR0-TS"] = changed(
        30, "cr0_after", _hex(config["cr0_after"] | (1 << 3))
    )
    candidates["NEG-N7-PKXSTATE-CR0-EM"] = changed(
        30, "cr0_after", _hex(config["cr0_after"] | (1 << 2))
    )
    candidates["NEG-N7-PKXSTATE-CR4-OSXSAVE"] = changed(
        30, "cr4_after", _hex(config["cr4_after"] & ~(1 << 18))
    )
    candidates["NEG-N7-PKXSTATE-XCR0-SELECTED"] = changed(30, "xcr0_after", _hex(1))
    candidates["NEG-N7-PKXSTATE-XSS"] = changed(30, "xss", _hex(1))
    candidates["NEG-N7-PKXSTATE-STRATEGY"] = changed(30, "strategy", "lazy")
    candidates["NEG-N7-PKXSTATE-FORMAT"] = changed(30, "format", "compacted")
    candidates["NEG-N7-PKXSTATE-AREA-SIZE"] = changed(30, "area_bytes", "2048")
    candidates["NEG-N7-PKXSTATE-ALIGNMENT"] = changed(30, "alignment", "16")
    candidates["NEG-N7-PKXSTATE-FCW"] = changed(31, "fcw", _hex(0x027F))
    candidates["NEG-N7-PKXSTATE-MXCSR"] = changed(31, "mxcsr", _hex(0x1F00))
    candidates["NEG-N7-PKXSTATE-MXCSR-MASK"] = changed(31, "mxcsr_mask_raw", _hex(0x80))
    candidates["NEG-N7-PKXSTATE-SAVE-COUNT"] = changed(32, "saves", "1")
    candidates["NEG-N7-PKXSTATE-RESTORE-COUNT"] = changed(32, "restores", "3")
    candidates["NEG-N7-PKXSTATE-XSTATE-BV"] = changed(32, "xstate_bv_a", _hex(4))
    candidates["NEG-N7-PKXSTATE-CONTEXT-MATCH"] = changed(32, "match_b", "0")
    candidates["NEG-N7-PKXSTATE-SCHEDULER-LOCK"] = changed(32, "scheduler_lock", "0")
    candidates["NEG-N7-PKXSTATE-INTERRUPTS"] = changed(32, "interrupts", "1")
    candidates["NEG-N7-PKXSTATE-CPU-MIGRATION"] = changed(32, "same_cpu", "0")
    candidates["NEG-N7-PKXSTATE-KERNEL-SIMD"] = changed(32, "kernel_simd", "1")
    candidates["NEG-N7-PKXSTATE-CANONICAL-CLEAR"] = changed(33, "canonical_xmm0_zero", "0")
    candidates["NEG-N7-PKXSTATE-IMAGE-CLEAR"] = changed(33, "image_zero_bytes", "4096")
    candidates["NEG-N7-PKXSTATE-NM"] = changed(33, "unexpected_nm", "1")
    candidates["NEG-N7-PKXSTATE-WRITES"] = changed(34, "writes", "2")
    candidates["NEG-N7-PKXSTATE-SIGNATURES"] = changed(34, "signatures", "1")
    candidates["NEG-N7-PKXSTATE-AUTHORITY"] = changed(34, "authority", "1")
    candidates["NEG-N7-PKXSTATE-ACTIONS"] = changed(34, "actions", "1")
    candidates["NEG-N7-PKXSTATE-SCHEDULER-CLAIM"] = changed(34, "scheduler", "1")
    candidates["NEG-N7-PKXSTATE-SMP-CLAIM"] = changed(34, "smp", "1")
    candidates["NEG-N7-PKXSTATE-TARGET-CLAIM"] = changed(34, "target", "1")

    if set(candidates) != set(xstate.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKXSTATE1 hostile-control implementation is incomplete")
    return [
        _require_rejection(control_id, candidates[control_id])
        for control_id in xstate.NEGATIVE_CONTROL_IDS
    ]


def _source_audit() -> dict[str, Any]:
    source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
    start = source.index("unsafe fn write_cr0")
    end = source.index("pub unsafe fn observe_cpu_policy", start)
    segment = source[start:end].lower()
    outside = (source[:start] + source[end:]).lower()
    required = {
        "cr0_write": '"mov cr0, {}"',
        "cr4_write": '"mov cr4, {}"',
        "xcr0_write": '"xsetbv"',
        "standard_save": '"xsave64 [{}]"',
        "standard_restore": '"xrstor64 [{}]"',
    }
    counts = {name: segment.count(token) for name, token in required.items()}
    if any(count != 1 for count in counts.values()):
        raise QualificationError(f"PKXSTATE1 required instruction audit failed: {counts}")
    forbidden = ("wrmsr", "xsaves64", "xrstors64", "ymm", "zmm")
    hits = [token for token in forbidden if token in segment]
    if hits or "xmm0" in outside:
        raise QualificationError(f"PKXSTATE1 source restriction audit failed: {hits}")
    return {
        "scope": "dedicated PKXSTATE1 architectural helpers and proof path",
        "required_instruction_counts": counts,
        "state_write_instruction_count": 3,
        "forbidden_tokens": list(forbidden),
        "forbidden_token_hits": [],
        "xmm0_occurrences_outside_scope": 0,
        "result": "pass_bounded_source_instruction_audit",
    }


def _profile_overlay(profile: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(profile)
    arguments = value["base_argument_template"]
    index = arguments.index("-cpu")
    if arguments[index + 1] != "qemu64":
        raise QualificationError("Tier 0 CPU argument changed before PKXSTATE1 overlay")
    arguments[index + 1] = xstate.CPU_MODEL
    value["machine"]["cpu_model"] = xstate.CPU_MODEL
    value["profile_set_id"] = "POOLEOS-PKXSTATE1-Q35-1"
    return value


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> dict[str, Any]:
    contract = xstate.read_json(ROOT / xstate.CONTRACT_RELATIVE)
    contract_schema = xstate.read_json(ROOT / xstate.CONTRACT_SCHEMA_RELATIVE)
    schema_errors = [
        f"contract schema {item.path}: {item.message}"
        for item in xstate.validate_json(contract, contract_schema)
    ]
    errors = [*schema_errors, *xstate.contract_errors(contract)]
    if errors:
        raise QualificationError("; ".join(errors))
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = _profile_overlay(base_profile)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)

    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifact_files)

    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs/native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkxstate1-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        xstate_boot, xstate_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "xstate-boot",
            development_feature=xstate.FEATURE,
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if xstate.sha256_bytes(default_boot) == xstate.sha256_bytes(xstate_boot):
            raise QualificationError("default and PKXSTATE1 PooleBoot profiles are not distinct")

        media_one = native_kernel_load.build_media_bytes(
            xstate_boot, config, manifest, kernel, artifact_files
        )
        media_two = native_kernel_load.build_media_bytes(
            xstate_boot, config, manifest, kernel, artifact_files
        )
        if media_one != media_two:
            raise QualificationError("two PKXSTATE1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pkxstate1.img"
        media_path.write_bytes(media_one)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkxstate1-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"xstate-policy-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=xstate.validate_markers,
                        marker_extractor=xstate.extract_markers,
                        completion_marker=xstate.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(encoding="ascii", errors="ignore").splitlines()
                            if line.strip().startswith("POOLE")
                        ][-8:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                try:
                    native_kernel_load.validate_oracle_binding(
                        prefix["boot_prefix"], media_inspection, run["pbp1_transcript"]
                    )
                    run["transcript_binding"] = native_kernel_transfer.validate_transcript_binding(
                        prefix, run["pbp1_transcript"]
                    )
                    run["independent_kernel_revalidation"] = (
                        native_kernel_transfer.validate_revalidation_binding(
                            prefix, handoff, retained_files
                        )
                    )
                except (
                    native_kernel_load.KernelLoadError,
                    native_kernel_transfer.KernelTransferError,
                ) as error:
                    raise QualificationError(str(error)) from error
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKXSTATE1 runs emitted different markers")
        if screenshots[0] != screenshots[1] or handoffs[0] != handoffs[1]:
            raise QualificationError("two PKXSTATE1 visual or handoff receipts differ")

    controls = _negative_controls(runs[0]["markers"])
    observation = xstate.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_xstate_policy_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_bsp_x87_sse_non_promoting",
        "contract_id": xstate.CONTRACT_ID,
        "selected_move_id": xstate.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n7_exit_gate_satisfied": False,
        "phase_status": {"N7": "partial", "N7.4": "partial", "ADD-N7-XSTATE-001": "partial"},
        "inputs": xstate.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "xstate_pooleboot": xstate_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "source_audit": _source_audit(),
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": xstate.sha256_bytes(media_one),
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
            "cpu_model": xstate.CPU_MODEL,
            "base_tier0_cpu_model": "qemu64",
            "base_tier0_profile_modified": False,
            "acceleration": "tcg_single_thread",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": xstate.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": {
                key: observation[key]
                for key in ("capability", "config", "initialization", "switch", "clear", "result")
            },
        },
        "negative_controls": controls,
        "claims": xstate.expected_claims(),
        "non_claims": contract["non_claims"],
        "summary": {
            "qemu_run_count": 2,
            "marker_count": xstate.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "selected_xcr0": observation["config"]["xcr0_after"],
            "enabled_area_bytes": observation["capability"]["enabled_area_bytes"],
            "context_save_count": observation["switch"]["saves"],
            "context_restore_count": observation["switch"]["restores"],
            "context_image_zero_bytes": observation["clear"]["image_zero_bytes"],
            "privileged_configuration_writes": observation["result"]["writes"],
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "firmware_calls_after_exit": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Qualify AVX and other selected extended components with exact XCR0/XSS dependencies.",
            "Qualify deliberate #MF, #XM, and any selected #NM delivery and recovery path.",
            "Integrate bounded image allocation and ownership with real thread lifecycle and scheduling.",
            "Qualify AP initialization, SMP homogeneity, and CPU migration behavior.",
            "Add final linked-machine-code auditing for unintended compiler vector instructions.",
            "Qualify the exact Ryzen 7 9800X3D target and complete the remaining N7 exit gate.",
        ],
    }
    errors = xstate.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-21")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, QualificationError) as error:
        print(f"PKXSTATE1 qualification failed: {error}", file=sys.stderr)
        return 1
    print(
        "PKXSTATE1 qualification passed: "
        f"runs={report['summary']['qemu_run_count']} "
        f"controls={report['summary']['negative_controls_passed']} "
        f"control_writes={report['summary']['privileged_configuration_writes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
