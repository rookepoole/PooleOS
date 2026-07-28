#!/usr/bin/env python3
"""Build and qualify the bounded two-vCPU PKSMP1 first-AP profile."""

from __future__ import annotations

import argparse
import copy
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
    native_kernel_smp_first_ap as smp_first_ap,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / smp_first_ap.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when PKSMP1 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSMP1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _require_rejection(control_id: str, operation: Callable[[], Any]) -> dict[str, str]:
    try:
        operation()
    except smp_first_ap.KernelSmpFirstApError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKSMP1 hostile control did not reject: {control_id}")


def _marker_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    return _require_rejection(control_id, lambda: smp_first_ap.validate_markers(candidate))


def _audit_source_text(arch_text: str, main_text: str, smp_text: str) -> dict[str, Any]:
    try:
        gdt_block = arch_text.split("poole_ap_trampoline_gdt:", 1)[1].split(".Lpoole_ap_gdt_end:", 1)[0]
    except IndexError as error:
        raise smp_first_ap.KernelSmpFirstApError("PKSMP1 AP GDT block is missing") from error
    descriptors = [int(value, 16) for value in re.findall(r"\.quad 0x([0-9a-fA-F]{16})", gdt_block)]
    smp_first_ap._require(len(descriptors) == 5 and descriptors[0] == 0, "PKSMP1 AP GDT shape changed")
    smp_first_ap.require_preaccessed_gdt(descriptors[1:])
    required_arch = (
        "poole_ap_trampoline_start:",
        ".code16",
        ".code32",
        ".code64",
        "or eax, 0x00000900",
        "or eax, 0x80010001",
        "mov dword ptr [rdi + 12], 2",
        "mov dword ptr [rdi + 12], 3",
    )
    required_main = (
        "SMP_APIC_INIT_ASSERT",
        "SMP_APIC_INIT_DEASSERT",
        "SMP_APIC_STARTUP",
        "advance_reclaim_stage(ReclaimStage::PostExitBootServices)",
        "smp_release_resources",
        "transaction.parked()?",
    )
    required_smp = (
        "RESOURCE_PAGE_COUNT: u64 = 14",
        "GUARD_PAGE_COUNT: u64 = 4",
        "pub fn validate_mailbox",
        "pub fn rollback",
    )
    smp_first_ap._require(all(token in arch_text for token in required_arch), "PKSMP1 trampoline source audit failed")
    smp_first_ap._require(all(token in main_text for token in required_main), "PKSMP1 live lifecycle source audit failed")
    smp_first_ap._require(all(token in smp_text for token in required_smp), "PKSMP1 model source audit failed")
    smp_first_ap._require("PKSMPDBG" not in arch_text + main_text + smp_text, "PKSMP1 transient diagnostics remain")
    return {
        "gdt_descriptor_count": 4,
        "gdt_preaccessed_descriptor_count": 4,
        "trampoline_mode_count": 3,
        "resource_page_count": 14,
        "guard_page_count": 4,
        "transient_diagnostic_token_count": 0,
    }


def _source_audit() -> dict[str, Any]:
    paths = {
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "smp": ROOT / "native/kernel/src/smp.rs",
    }
    result = _audit_source_text(*(paths[name].read_text(encoding="utf-8") for name in ("arch", "main", "smp")))
    result["files"] = {
        name: {"path": path.relative_to(ROOT).as_posix(), "sha256": smp_first_ap.sha256_bytes(path.read_bytes())}
        for name, path in paths.items()
    }
    return result


def _negative_controls(markers: list[str]) -> list[dict[str, str]]:
    observation = smp_first_ap.validate_markers(markers)
    controls: list[dict[str, str]] = []
    controls.append(_marker_rejection(smp_first_ap.NEGATIVE_CONTROL_IDS[0], markers[:-1]))
    reordered = markers.copy()
    reordered[30], reordered[31] = reordered[31], reordered[30]
    controls.append(_marker_rejection(smp_first_ap.NEGATIVE_CONTROL_IDS[1], reordered))
    controls.append(_marker_rejection(smp_first_ap.NEGATIVE_CONTROL_IDS[2], [*markers, markers[-1]]))

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    mutations = (
        (3, 23, "trap_scenario", "11"),
        (4, 30, "contract", "PKSMP0"),
        (5, 30, "processors", "1"),
        (6, 30, "enabled", "1"),
        (7, 30, "bsp_apic_id", "1"),
        (8, 30, "target_apic_id", "0"),
        (9, 30, "x2apic", "1"),
        (10, 30, "selection", "first_non_bsp"),
        (11, 30, "retained_snapshot", "0"),
        (12, 31, "physical_start", "0x0000000000000000"),
        (13, 31, "pages", "13"),
        (14, 31, "sipi_vector", "2"),
        (15, 31, "trampoline_bytes", str(smp_first_ap.TRAMPOLINE_BYTES - 1)),
        (16, 31, "allocation_sequence", "3"),
        (17, 31, "tables", "3"),
        (18, 31, "stack_pages", "3"),
        (19, 31, "per_cpu_pages", "2"),
        (20, 31, "guard_pages", "3"),
        (21, 31, "below_1mib", "0"),
        (22, 31, "allocation_scrubbed", "0"),
        (23, 32, "pml4", "0x0000000000003000"),
        (24, 32, "identity_pages", "5"),
        (25, 32, "trampoline", "rwx"),
        (26, 32, "stack", "rw"),
        (27, 32, "per_cpu", "rw"),
        (28, 32, "guards", "present"),
        (29, 32, "high_alias", "retained"),
        (30, 33, "init_asserts", "0"),
        (31, 33, "init_deasserts", "0"),
        (32, 33, "sipis", "1"),
        (33, 33, "delivery_timeouts", "1"),
        (34, 33, "sequence", "sipi_only"),
        (35, 34, "state", "3"),
        (36, 34, "observed_apic_id", "0"),
        (37, 34, "leaf1_ecx", "0x0000000080002000"),
        (38, 34, "leaf1_edx", "0x00000000178BF9FD"),
        (39, 34, "cr0", "0x00000000E0000011"),
        (40, 34, "cr3", "0x0000000000003000"),
        (41, 34, "cr4", "0x0000000000000000"),
        (42, 34, "efer", "0x0000000000000500"),
        (43, 34, "mode", "x86_32"),
        (44, 34, "tsc_order", "unchecked"),
        (45, 35, "command", "0"),
        (46, 35, "state", "2"),
        (47, 35, "tsc_stop", f"0x{observation['stop']['tsc_online'] - 1:016X}"),
        (48, 35, "checksum", "0x0000000000000000"),
        (49, 35, "final_init", "0"),
        (50, 35, "parked", "0"),
        (51, 35, "mailbox_validated", "0"),
        (52, 36, "release_sequence", "4"),
        (53, 36, "zeroed_bytes", "0"),
        (54, 36, "verified_bytes", "0"),
        (55, 36, "resources_released", "13"),
        (56, 36, "mailbox_revoked", "0"),
        (57, 36, "mmio_revoked", "0"),
        (58, 36, "pic_restored", "0"),
        (59, 36, "hpet_restored", "0"),
        (60, 36, "apic_base_restored", "changed"),
        (61, 37, "ap_online", "0"),
        (62, 37, "ipi_service", "1"),
        (63, 37, "shootdown", "1"),
        (64, 37, "scheduler", "1"),
        (65, 37, "target", "1"),
        (66, 37, "authority", "1"),
        (67, 37, "production", "1"),
        (68, 37, "terminal", "resume"),
    )
    for control_index, marker_index, field, value in mutations:
        controls.append(_marker_rejection(smp_first_ap.NEGATIVE_CONTROL_IDS[control_index], changed(marker_index, field, value)))

    arch = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
    main = (ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
    smp = (ROOT / "native/kernel/src/smp.rs").read_text(encoding="utf-8")
    controls.append(
        _require_rejection(
            smp_first_ap.NEGATIVE_CONTROL_IDS[69],
            lambda: _audit_source_text(arch.replace("0x00cf9b000000ffff", "0x00cf9a000000ffff", 1), main, smp),
        )
    )
    processors = [
        {"apic_id": 0, "enabled": True, "x2apic": False},
        {"apic_id": 1, "enabled": True, "x2apic": False},
    ]
    x2apic = copy.deepcopy(processors)
    x2apic[1]["x2apic"] = True
    controls.append(_require_rejection(smp_first_ap.NEGATIVE_CONTROL_IDS[70], lambda: smp_first_ap.select_first_ap(x2apic, 0)))
    controls.append(_require_rejection(smp_first_ap.NEGATIVE_CONTROL_IDS[71], lambda: smp_first_ap.select_first_ap(processors[:1], 0)))
    if [item["id"] for item in controls] != list(smp_first_ap.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKSMP1 hostile-control order diverged")
    return controls


def _two_cpu_profile(profile: dict[str, Any]) -> dict[str, Any]:
    derived = copy.deepcopy(profile)
    arguments = derived["base_argument_template"]
    try:
        index = arguments.index("-smp")
    except ValueError as error:
        raise QualificationError("Tier 0 profile has no SMP argument") from error
    arguments[index + 1] = "2,sockets=1,dies=1,clusters=1,cores=2,threads=1,maxcpus=2"
    derived["machine"]["vcpus"] = 2
    derived["machine"]["cores"] = 2
    return derived


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = smp_first_ap.read_json(ROOT / smp_first_ap.CONTRACT_RELATIVE)
    errors = smp_first_ap.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = _two_cpu_profile(base_profile)
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
    with tempfile.TemporaryDirectory(prefix="pksmp1-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        smp_boot, smp_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "smp-boot", development_feature=smp_first_ap.FEATURE
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if smp_first_ap.sha256_bytes(default_boot) == smp_first_ap.sha256_bytes(smp_boot):
            raise QualificationError("default and PKSMP1 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(smp_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(smp_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKSMP1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksmp1.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksmp1-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"smp-first-ap-run-{run_index}", lock, profile, qemu_root, media_path,
                        run_directory, timeout, marker_validator=smp_first_ap.validate_markers,
                        marker_extractor=smp_first_ap.extract_markers,
                        completion_marker=smp_first_ap.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [line.strip() for line in debug_path.read_text(encoding="ascii", errors="ignore").splitlines() if line.strip().startswith("POOLE")][-16:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                native_kernel_load.validate_oracle_binding(prefix["boot_prefix"], media_inspection, run["pbp1_transcript"])
                run["transcript_binding"] = native_kernel_transfer.validate_transcript_binding(prefix, run["pbp1_transcript"])
                run["independent_kernel_revalidation"] = native_kernel_transfer.validate_revalidation_binding(prefix, handoff, retained_files)
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        normalized_markers = [smp_first_ap.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized_markers[0] != normalized_markers[1]:
            raise QualificationError("two PKSMP1 runs emitted different static markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSMP1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSMP1 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"])
    observation = smp_first_ap.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_smp_first_ap_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_two_vcpu_first_ap_non_promoting",
        "contract_id": smp_first_ap.CONTRACT_ID,
        "selected_move_id": smp_first_ap.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n8_exit_gate_satisfied": False,
        "flag_n8_smp_first_ap_001_closed": True,
        "phase_status": {"N8": "partial", "N8.1": "partial", "N8.3": "partial", "N8.5": "partial", "N8.6": "not_started"},
        "inputs": smp_first_ap.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "smp_first_ap_pooleboot": smp_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "source_audit": source_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": smp_first_ap.sha256_bytes(media_one),
            "byte_count": len(media_one),
            "inspection": media_inspection,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "bootstrap-debug-derived-two-vcpu",
            "machine": "pc-q35-11.0",
            "cpu_model": "qemu64",
            "virtual_cpu_count": 2,
            "acceleration": "tcg_single_thread",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": smp_first_ap.sha256_bytes(native_pooleboot.canonical_json_bytes(command)),
            "fresh_vars_each_run": True,
            "media_read_only": True,
            "guest_network": False,
            "host_acceleration": False,
            "static_markers_exact_match": True,
            "dynamic_tsc_and_checksum_fields_revalidated": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": observation,
        },
        "negative_controls": controls,
        "claims": contract["claims"],
        "non_claims": contract["non_claims"],
        "summary": {
            "kernel_host_tests_passed": kernel_readiness["host_tests"]["test_pass_count"],
            "kernel_host_tests_total": kernel_readiness["host_tests"]["test_count"],
            "qemu_runs_passed": 2,
            "qemu_runs_total": 2,
            "markers_per_run": smp_first_ap.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "application_processors_started": 1,
            "application_processors_online": 1,
            "application_processors_quiesced": 1,
            "application_processors_parked": 1,
            "resource_pages_released": observation["release"]["resources_released"],
            "zeroed_bytes": observation["release"]["zeroed_bytes"],
            "verified_bytes": observation["release"]["verified_bytes"],
            "production_claim_count": 0,
        },
        "open_items": [
            "Inject live failures after INIT and each SIPI and prove final-INIT park before retained-resource cleanup.",
            "Install complete per-CPU GDT, TSS, IDT, kernel stack, fault stacks, and processor-local state.",
            "Implement capability-gated IPI delivery and acknowledged SMP TLB shootdown before remote PKVM3 retirement.",
            "Implement scheduler CPU ownership, migration barriers, idle states, and AP work dispatch.",
            "Add x2APIC, topology hierarchy, NUMA, hotplug, and multi-socket policy only under separate contracts.",
            "Qualify the exact physical target and all 16 logical processors; no target claim exists here.",
        ],
    }
    errors = list(validate_json(report, smp_first_ap.read_json(ROOT / smp_first_ap.READINESS_SCHEMA_RELATIVE)))
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-28")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)
    try:
        report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
        errors = smp_first_ap.readiness_errors(smp_first_ap.read_json(args.out), ROOT)
        if errors:
            raise QualificationError("; ".join(errors))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, QualificationError, smp_first_ap.KernelSmpFirstApError, native_kernel_load.KernelLoadError, native_kernel_transfer.KernelTransferError, native_tier0.Tier0Error) as error:
        print(f"NATIVE_KERNEL_SMP_FIRST_AP_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "NATIVE_KERNEL_SMP_FIRST_AP_QUALIFICATION PASS "
        f"host_tests={summary['kernel_host_tests_passed']}/{summary['kernel_host_tests_total']} "
        f"runs={summary['qemu_runs_passed']}/{summary['qemu_runs_total']} "
        f"markers={summary['markers_per_run']} controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} "
        f"ap={summary['application_processors_online']}/1 parked={summary['application_processors_parked']}/1 "
        f"scrub={summary['verified_bytes']} n8_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
