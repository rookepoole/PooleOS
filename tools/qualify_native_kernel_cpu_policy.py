#!/usr/bin/env python3
"""Build and qualify the bounded PKCPU1 read-only CPU policy profile."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_kernel_cpu_policy,
    native_kernel_load,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / native_kernel_cpu_policy.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKCPU1 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKCPU1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _hex(value: int) -> str:
    return f"0x{value & ((1 << 64) - 1):016X}"


def _require_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    try:
        native_kernel_cpu_policy.validate_markers(candidate)
    except native_kernel_cpu_policy.KernelCpuPolicyError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKCPU1 hostile control did not reject: {control_id}")


def _negative_controls(markers: list[str]) -> list[dict[str, str]]:
    summary = native_kernel_cpu_policy.validate_markers(markers)
    discovery = summary["discovery"]
    topology = summary["topology"]
    features = summary["features"]
    xsave = summary["xsave"]
    state = summary["state"]

    candidates: dict[str, list[str]] = {}
    candidates["NEG-N7-PKCPU-MARKER-OMISSION"] = markers[:-1]
    ordered = markers.copy()
    ordered[29], ordered[30] = ordered[30], ordered[29]
    candidates["NEG-N7-PKCPU-MARKER-ORDER"] = ordered
    candidates["NEG-N7-PKCPU-MARKER-DUPLICATE"] = [*markers, markers[-1]]

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    candidates["NEG-N7-PKCPU-SELECTOR"] = changed(23, "trap_scenario", "0")
    candidates["NEG-N7-PKCPU-CONTRACT"] = changed(29, "contract", "PKCPU2")
    candidates["NEG-N7-PKCPU-VENDOR"] = changed(29, "vendor_hex", b"UnknownCPU00".hex().upper())
    candidates["NEG-N7-PKCPU-BRAND"] = changed(29, "brand_hex", "00" * 48)
    candidates["NEG-N7-PKCPU-MAX-BASIC"] = changed(29, "max_basic", _hex(6))
    candidates["NEG-N7-PKCPU-MAX-EXTENDED"] = changed(29, "max_extended", _hex(0x80000007))
    candidates["NEG-N7-PKCPU-IDENTITY-FAMILY"] = changed(29, "family", str(discovery["family"] + 1))
    candidates["NEG-N7-PKCPU-IDENTITY-MODEL"] = changed(29, "model", str(discovery["model"] + 1))
    candidates["NEG-N7-PKCPU-IDENTITY-STEPPING"] = changed(29, "stepping", str(discovery["stepping"] ^ 1))
    candidates["NEG-N7-PKCPU-LOGICAL-COUNT"] = changed(29, "logical", "0")
    candidates["NEG-N7-PKCPU-PHYSICAL-WIDTH"] = changed(29, "physical_width", "35")
    candidates["NEG-N7-PKCPU-LINEAR-WIDTH"] = changed(29, "linear_width", "57")
    topology_id = markers.copy()
    topology_id[30] = _set_field(topology_id[30], "leafb0_ebx", _hex(1))
    topology_id[30] = _set_field(topology_id[30], "leafb0_edx", _hex(discovery["apic_id"] ^ 1))
    candidates["NEG-N7-PKCPU-TOPOLOGY-ID"] = topology_id
    candidates["NEG-N7-PKCPU-LEAF1-REQUIRED"] = changed(
        31, "leaf1_edx", _hex(features["leaf1_edx"] & ~(1 << 26))
    )
    candidates["NEG-N7-PKCPU-EXT1-REQUIRED"] = changed(
        31, "ext1_edx", _hex(features["ext1_edx"] & ~(1 << 20))
    )
    candidates["NEG-N7-PKCPU-CR0-REQUIRED"] = changed(33, "cr0", _hex(state["cr0"] & ~(1 << 16)))
    candidates["NEG-N7-PKCPU-CR0-FORBIDDEN"] = changed(33, "cr0", _hex(state["cr0"] | (1 << 30)))
    candidates["NEG-N7-PKCPU-CR4-REQUIRED"] = changed(33, "cr4", _hex(state["cr4"] & ~(1 << 5)))
    candidates["NEG-N7-PKCPU-CR4-FORBIDDEN"] = changed(33, "cr4", _hex(state["cr4"] | (1 << 13)))
    feature_gate = markers.copy()
    feature_gate[31] = _set_field(feature_gate[31], "leaf7_ebx", _hex(features["leaf7_ebx"] & ~1))
    feature_gate[33] = _set_field(feature_gate[33], "cr4", _hex(state["cr4"] | (1 << 16)))
    candidates["NEG-N7-PKCPU-FEATURE-GATE"] = feature_gate
    candidates["NEG-N7-PKCPU-OSXSAVE-CONSISTENCY"] = changed(
        31, "leaf1_ecx", _hex(features["leaf1_ecx"] ^ (1 << 27))
    )
    xcr0_baseline = markers.copy()
    xcr0_baseline[31] = _set_field(
        xcr0_baseline[31], "leaf1_ecx", _hex(features["leaf1_ecx"] | (1 << 26) | (1 << 27))
    )
    xcr0_baseline[32] = _set_field(xcr0_baseline[32], "leafd0_eax", _hex(xsave["leafd0_eax"] | 3))
    xcr0_baseline[32] = _set_field(xcr0_baseline[32], "xcr0", _hex(1))
    xcr0_baseline[33] = _set_field(xcr0_baseline[33], "cr4", _hex(state["cr4"] | (1 << 18)))
    candidates["NEG-N7-PKCPU-XCR0-BASELINE"] = xcr0_baseline
    candidates["NEG-N7-PKCPU-EFER-REQUIRED"] = changed(33, "efer", _hex(state["efer"] & ~(1 << 11)))
    candidates["NEG-N7-PKCPU-EFER-RESERVED"] = changed(33, "efer", _hex(state["efer"] | (1 << 63)))
    candidates["NEG-N7-PKCPU-MSR-READ-ALLOWLIST"] = changed(33, "msr_read_mask", _hex(state["msr_read_mask"] & ~(1 << 2)))
    candidates["NEG-N7-PKCPU-APIC-ENABLE"] = changed(33, "apic_base", _hex(state["apic_base"] & ~(1 << 11)))
    candidates["NEG-N7-PKCPU-APIC-RESERVED"] = changed(33, "apic_base", _hex(state["apic_base"] | 1))
    candidates["NEG-N7-PKCPU-PAT-TYPE"] = changed(33, "pat", _hex((state["pat"] & ~0xFF) | 3))
    candidates["NEG-N7-PKCPU-MTRR-CAP"] = changed(33, "mtrr_cap", _hex(state["mtrr_cap"] | (1 << 9)))
    candidates["NEG-N7-PKCPU-MTRR-DEFAULT"] = changed(33, "mtrr_def", _hex(state["mtrr_def"] & ~(1 << 11)))
    candidates["NEG-N7-PKCPU-RESULT-PROFILE"] = changed(34, "profile", "host")
    candidates["NEG-N7-PKCPU-RESULT-READS"] = changed(34, "reads", "cpuid_only")
    candidates["NEG-N7-PKCPU-RESULT-WRITES"] = changed(34, "writes", "1")
    candidates["NEG-N7-PKCPU-RESULT-SIGNATURES"] = changed(34, "signatures", "1")
    candidates["NEG-N7-PKCPU-RESULT-AUTHORITY"] = changed(34, "authority", "1")
    candidates["NEG-N7-PKCPU-RESULT-ACTIONS"] = changed(34, "actions", "1")
    candidates["NEG-N7-PKCPU-RESULT-INTERRUPTS"] = changed(34, "interrupts", "1")
    candidates["NEG-N7-PKCPU-RESULT-TERMINAL"] = changed(34, "terminal", "return")

    if set(candidates) != set(native_kernel_cpu_policy.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKCPU1 hostile-control implementation is incomplete")
    controls = [
        _require_rejection(control_id, candidates[control_id])
        for control_id in native_kernel_cpu_policy.NEGATIVE_CONTROL_IDS
    ]
    if topology["leafb0_ebx"] and topology["leafb0_edx"] != discovery["apic_id"]:
        raise QualificationError("PKCPU1 source observation has contradictory topology")
    return controls


def _source_audit() -> dict[str, Any]:
    source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
    start = source.index("const IA32_APIC_BASE")
    end = source.index("#[derive(Clone, Copy, Debug)]", start)
    observer = source[start:end].lower()
    forbidden = ("wrmsr", "xsetbv", 'mov cr0,', 'mov cr4,')
    hits = [instruction for instruction in forbidden if instruction in observer]
    if hits:
        raise QualificationError(f"PKCPU1 observer contains a forbidden write instruction: {hits}")
    return {
        "scope": "PKCPU1 observer and typed register helpers",
        "forbidden_instructions": list(forbidden),
        "forbidden_instruction_hits": [],
        "result": "pass_no_cpu_state_write_instruction",
    }


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> dict[str, Any]:
    contract = native_kernel_cpu_policy.read_json(ROOT / native_kernel_cpu_policy.CONTRACT_RELATIVE)
    errors = native_kernel_cpu_policy.contract_errors(contract)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)

    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifact_files)

    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkcpu1-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        cpu_boot, cpu_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "cpu-boot",
            development_feature=native_kernel_cpu_policy.FEATURE,
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if native_kernel_cpu_policy.sha256_bytes(default_boot) == native_kernel_cpu_policy.sha256_bytes(cpu_boot):
            raise QualificationError("default and PKCPU1 PooleBoot profiles are not distinct")

        media_one = native_kernel_load.build_media_bytes(cpu_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(cpu_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKCPU1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKCPU1 media kernel differs from PKENTRY1")
        media_path = temporary_root / "pkcpu1.img"
        media_path.write_bytes(media_one)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkcpu1-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"cpu-policy-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=native_kernel_cpu_policy.validate_markers,
                        marker_extractor=native_kernel_cpu_policy.extract_markers,
                        completion_marker=native_kernel_cpu_policy.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    debug_tail = []
                    if debug_path.is_file():
                        debug_text = debug_path.read_bytes().decode("ascii", errors="ignore")
                        debug_tail = [
                            line.strip()
                            for line in debug_text.replace("\r", "\n").splitlines()
                            if line.strip().startswith("POOLE")
                        ][-5:]
                    raise QualificationError(
                        f"{error}; synthetic_debug_tail={debug_tail!r}"
                    ) from error
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
            raise QualificationError("two PKCPU1 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKCPU1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKCPU1 runs produced different PBP1 bytes")

    controls = _negative_controls(runs[0]["markers"])
    observation = native_kernel_cpu_policy.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_cpu_policy_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_read_only_non_promoting",
        "contract_id": native_kernel_cpu_policy.CONTRACT_ID,
        "selected_move_id": native_kernel_cpu_policy.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n7_exit_gate_satisfied": False,
        "phase_status": {"N7": "partial", "N7.1": "partial", "N7.3": "partial"},
        "inputs": native_kernel_cpu_policy.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "cpu_policy_pooleboot": cpu_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "source_audit": _source_audit(),
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": native_kernel_cpu_policy.sha256_bytes(media_one),
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
            "cpu_model": "qemu64",
            "acceleration": "tcg_single_thread",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": native_kernel_cpu_policy.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": {
                key: observation[key]
                for key in ("discovery", "topology", "features", "xsave", "state", "result")
            },
        },
        "negative_controls": controls,
        "claims": native_kernel_cpu_policy.expected_claims(),
        "non_claims": contract["non_claims"],
        "summary": {
            "qemu_run_count": 2,
            "marker_count": native_kernel_cpu_policy.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "cpuid_vendor": observation["discovery"]["vendor"],
            "cpuid_family": observation["discovery"]["family"],
            "cpuid_model": observation["discovery"]["model"],
            "cpuid_stepping": observation["discovery"]["stepping"],
            "physical_width": observation["discovery"]["physical_width"],
            "linear_width": observation["discovery"]["linear_width"],
            "msr_read_count": observation["state"]["msr_read_mask"].bit_count(),
            "state_writes": 0,
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "firmware_calls_after_exit": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Freeze AMD Ryzen 7 9800X3D family/model/stepping and native CPUID acceptance from qualified physical evidence.",
            "Acquire an applicable Granite Ridge revision guide or retain a documented vendor-source gap and build the target errata matrix.",
            "Add privileged microcode revision observation and fail-closed minimum revision policy after mechanism qualification.",
            "Implement x87/SSE/AVX/XSAVE ownership, context switching, restore validation, and hostile state tests in N7.4.",
            "Extend discovery and policy to AP-local state, target firmware, physical hardware, and second-host reproduction.",
            "Complete the remaining N7 descriptor, vector, NMI, machine-check, crash-retention, and exit-gate work.",
        ],
    }
    errors = native_kernel_cpu_policy.readiness_errors(report, ROOT)
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
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        native_kernel_cpu_policy.KernelCpuPolicyError,
        native_tier0.Tier0Error,
    ) as error:
        parser.exit(1, f"PKCPU1 qualification failed: {error}\n")
    print(
        "PKCPU1 qualification passed: "
        f"runs={report['summary']['qemu_run_count']}; "
        f"negative={report['summary']['negative_controls_passed']}; "
        f"vendor={report['summary']['cpuid_vendor']}; "
        f"family={report['summary']['cpuid_family']}; "
        f"model={report['summary']['cpuid_model']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
