#!/usr/bin/env python3
"""Build and qualify the bounded two-vCPU PKSMP2 AP-local runtime."""

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
    native_kernel_smp_percpu_runtime as smp_runtime,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / smp_runtime.READINESS_RELATIVE
HOSTILE_CASE_COUNT = 159


class QualificationError(RuntimeError):
    """Raised when PKSMP2 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSMP2 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSMP2 mutation field is missing: {field}")
    value = match.group(1)
    if value.startswith("0x"):
        return "0x0000000000000001" if int(value, 16) == 0 else "0x0000000000000000"
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    return "invalid"


def _require_rejections(control_id: str, operations: list[Callable[[], Any]]) -> dict[str, Any]:
    for operation in operations:
        try:
            operation()
        except smp_runtime.KernelSmpPerCpuRuntimeError:
            continue
        raise QualificationError(f"PKSMP2 hostile control did not reject: {control_id}")
    return {"id": control_id, "status": "pass", "expected": "rejected", "case_count": len(operations)}


def _marker_operation(candidate: list[str]) -> Callable[[], Any]:
    return lambda: smp_runtime.validate_markers(candidate)


def _field_matrix(control_id: str, markers: list[str], marker_index: int, fields: tuple[str, ...]) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        candidate = markers.copy()
        candidate[marker_index] = _set_field(candidate[marker_index], field, _invalid_value(candidate[marker_index], field))
        operations.append(_marker_operation(candidate))
    return _require_rejections(control_id, operations)


def _audit_source_text(arch_text: str, main_text: str, runtime_text: str) -> dict[str, Any]:
    runtime_arch = arch_text.split("poole_ap_runtime_trampoline_start:", 1)[1].split(
        "poole_ap_runtime_trampoline_end:", 1
    )[0]
    required_arch = (
        ".code16", ".code32", ".code64",
        "ltr ax", "lidt [rsi + poole_ap_runtime_config_idtr_offset]", "xsetbv",
        "xsave64 [rbx]", "xrstor64 [rbx]", "mov dword ptr [rdi + 280], 0",
    )
    required_main = (
        "SMP_APIC_INIT_ASSERT", "SMP_APIC_INIT_DEASSERT", "SMP_APIC_STARTUP",
        "smp_runtime::validate_mailbox", "smp_runtime::validate_post_ap_resources",
        "smp_runtime_release_resources", "transaction.parked()?", "transaction.validated()?",
    )
    required_runtime = (
        "pub const RESOURCE_PAGE_COUNT: u64 = 32", "pub const GUARD_PAGE_COUNT: u64 = 14",
        "pub const IDENTITY_MAPPED_PAGE_COUNT: u64 = 13", "pub fn baseline_checksum",
        "pub fn runtime_checksum", "pub fn validate_mailbox", "pub fn build_descriptor_page",
        "pub fn build_idt_page", "pub fn validate_post_ap_resources",
    )
    smp_runtime._require(all(token in runtime_arch for token in required_arch), "PKSMP2 trampoline source audit failed")
    smp_runtime._require(all(token in main_text for token in required_main), "PKSMP2 lifecycle source audit failed")
    smp_runtime._require(all(token in runtime_text for token in required_runtime), "PKSMP2 runtime model source audit failed")
    smp_runtime._require("PKSMP2DBG" not in arch_text + main_text + runtime_text, "PKSMP2 transient diagnostics remain")
    return {
        "trampoline_mode_count": 3,
        "hardware_descriptor_load_count": 2,
        "xsave_instruction_count": runtime_arch.count("xsave64 [rbx]"),
        "xrstor_instruction_count": runtime_arch.count("xrstor64 [rbx]"),
        "resource_page_count": 32,
        "guard_page_count": 14,
        "identity_mapped_page_count": 13,
        "transient_diagnostic_token_count": 0,
    }


def _source_audit() -> dict[str, Any]:
    paths = {
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "runtime": ROOT / "native/kernel/src/smp_runtime.rs",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    result = _audit_source_text(texts["arch"], texts["main"], texts["runtime"])
    result["files"] = {
        name: {"path": path.relative_to(ROOT).as_posix(), "sha256": smp_runtime.sha256_bytes(path.read_bytes())}
        for name, path in paths.items()
    }
    return result


def _negative_controls(markers: list[str]) -> list[dict[str, Any]]:
    smp_runtime.validate_markers(markers)
    ids = smp_runtime.NEGATIVE_CONTROL_IDS
    controls = [
        _require_rejections(ids[0], [_marker_operation(markers[:-1])]),
    ]
    reordered = markers.copy()
    reordered[34], reordered[35] = reordered[35], reordered[34]
    controls.append(_require_rejections(ids[1], [_marker_operation(reordered)]))
    controls.append(_require_rejections(ids[2], [_marker_operation([*markers, markers[-1]])]))

    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "12")
    prefix = markers.copy()
    prefix[0] += " invalid"
    controls.append(_require_rejections(ids[3], [_marker_operation(selector), _marker_operation(prefix)]))

    matrices = (
        (ids[4], 30, ("contract", "madt_bytes", "processors", "enabled", "bsp_apic_id", "target_apic_id", "apic_physical", "hpet_physical", "x2apic", "selection", "retained_snapshot")),
        (ids[5], 31, ("contract", "physical_start", "pages", "sipi_vector", "trampoline_bytes", "allocation_sequence", "tables", "mapped_pages", "guard_pages", "reserved_absent", "below_1mib", "allocation_scrubbed")),
        (ids[6], 32, ("contract", "pml4", "pdpt", "pd", "pt", "identity_pages", "trampoline", "idt", "mutable", "guards", "reserved", "high_alias")),
        (ids[7], 33, ("contract", "init_asserts", "init_deasserts", "sipis", "delivery_timeouts", "sequence")),
        (ids[8], 34, ("contract", "gdt", "gdt_limit", "tss", "tr", "code_selector", "data_selector", "idt", "idt_limit", "gates", "tss_busy", "idt_verified", "ltr", "lidt")),
        (ids[9], 35, ("contract", "rsp0_bottom", "rsp0_top", "observed_rsp", "ist1_bottom", "ist1_top", "ist2_bottom", "ist2_top", "rsp0_pages", "ist_pages_each", "guards")),
        (ids[10], 36, ("contract", "base", "bytes", "supported_xcr0", "enabled_bytes", "maximum_bytes", "xcr0", "xstate_bv", "fcw", "mxcsr", "owner_initial", "owner_final", "saves", "restores", "image_verified", "policy")),
        (ids[11], 37, ("contract", "exceptions", "interrupts", "timer", "ipi_first", "ipi_last", "error", "spurious", "if", "fault")),
        (ids[12], 38, ("contract", "state", "runtime_state", "observed_apic_id", "leaf1_ecx", "leaf1_edx", "cr0", "cr3", "cr4", "efer", "rflags", "mode", "tsc_order")),
        (ids[13], 39, ("contract", "command", "state", "runtime_state", "tsc_online", "tsc_stop", "baseline_checksum", "runtime_checksum", "final_init", "parked", "mailbox_validated", "resources_validated")),
        (ids[14], 40, ("contract", "release_sequence", "zeroed_bytes", "verified_bytes", "resources_released", "runtime_revoked", "mmio_revoked", "pic_restored", "hpet_restored", "apic_base_restored")),
        (ids[15], 41, ("contract", "profile", "bsp", "ap_started", "ap_online", "descriptors", "stacks", "xstate", "vectors", "ap_quiesced", "ap_parked", "resources_released", "rollback", "ipi_service", "shootdown", "scheduler", "target", "signatures", "authority", "actions", "production", "terminal")),
    )
    controls.extend(
        _field_matrix(control_id, markers, marker_index, fields)
        for control_id, marker_index, fields in matrices
    )

    arch = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
    main = (ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
    runtime = (ROOT / "native/kernel/src/smp_runtime.rs").read_text(encoding="utf-8")
    controls.append(_require_rejections(ids[16], [lambda: _audit_source_text(arch.replace("xrstor64 [rbx]", "xrstor64 [rax]", 1), main, runtime)]))
    controls.append(_require_rejections(ids[17], [lambda: smp_runtime.resource_layout(1, 31), lambda: smp_runtime.resource_layout(0, 32)]))
    processors = [{"apic_id": 0, "enabled": True, "x2apic": False}, {"apic_id": 1, "enabled": True, "x2apic": False}]
    x2apic = copy.deepcopy(processors)
    x2apic[1]["x2apic"] = True
    controls.append(_require_rejections(ids[18], [lambda: smp_runtime.select_first_ap(x2apic, 0), lambda: smp_runtime.select_first_ap(processors[:1], 0)]))

    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSMP2 hostile-control order diverged")
    case_count = sum(item["case_count"] for item in controls)
    if case_count != HOSTILE_CASE_COUNT:
        raise QualificationError(f"PKSMP2 hostile-case count changed: {case_count}")
    return controls


def _sandybridge_profile(profile: dict[str, Any]) -> dict[str, Any]:
    derived = copy.deepcopy(profile)
    arguments = derived["base_argument_template"]
    for option, value in (("-smp", "2,sockets=1,dies=1,clusters=1,cores=2,threads=1,maxcpus=2"), ("-cpu", "SandyBridge,-avx"), ("-accel", "tcg,thread=multi")):
        try:
            index = arguments.index(option)
        except ValueError as error:
            raise QualificationError(f"Tier 0 profile has no {option} argument") from error
        arguments[index + 1] = value
    try:
        icount = arguments.index("-icount")
    except ValueError as error:
        raise QualificationError("Tier 0 profile has no deterministic clock argument") from error
    del arguments[icount:icount + 2]
    machine = derived["machine"]
    machine.update({"cpu_model": "SandyBridge,-avx", "vcpus": 2, "cores": 2, "tcg_thread_mode": "multi"})
    return derived


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = smp_runtime.read_json(ROOT / smp_runtime.CONTRACT_RELATIVE)
    errors = smp_runtime.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = _sandybridge_profile(base_profile)
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
    with tempfile.TemporaryDirectory(prefix="pksmp2-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        runtime_boot, runtime_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "runtime-boot", development_feature=smp_runtime.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if smp_runtime.sha256_bytes(default_boot) == smp_runtime.sha256_bytes(runtime_boot):
            raise QualificationError("default and PKSMP2 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(runtime_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(runtime_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKSMP2 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksmp2.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksmp2-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"smp-percpu-runtime-run-{run_index}", lock, profile, qemu_root, media_path,
                        run_directory, timeout, marker_validator=smp_runtime.validate_markers,
                        marker_extractor=smp_runtime.extract_markers, completion_marker=smp_runtime.COMPLETION_MARKER,
                    )
                except (
                    qualify_native_pooleboot.QualificationError,
                    smp_runtime.KernelSmpPerCpuRuntimeError,
                ) as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [line.strip() for line in debug_path.read_text(encoding="ascii", errors="ignore").splitlines() if line.strip().startswith("POOLE")][-18:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                native_kernel_load.validate_oracle_binding(prefix["boot_prefix"], media_inspection, run["pbp1_transcript"])
                run["transcript_binding"] = native_kernel_transfer.validate_transcript_binding(prefix, run["pbp1_transcript"])
                run["independent_kernel_revalidation"] = native_kernel_transfer.validate_revalidation_binding(prefix, handoff, retained_files)
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        normalized_markers = [smp_runtime.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized_markers[0] != normalized_markers[1]:
            raise QualificationError("two PKSMP2 runs emitted different static markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSMP2 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSMP2 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"])
    observation = smp_runtime.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0", "artifact_kind": "pooleos_native_kernel_smp_percpu_runtime_readiness",
        "status_date": status_date, "status": "pass_single_host_two_run_sandybridge_two_vcpu_ap_local_runtime_non_promoting",
        "contract_id": smp_runtime.CONTRACT_ID, "selected_move_id": smp_runtime.SELECTED_MOVE_ID,
        "production_ready": False, "production_promotion_allowed": False, "n8_exit_gate_satisfied": False,
        "flag_n8_smp_percpu_runtime_001_closed": True,
        "phase_status": {"N8": "partial", "N8.1": "partial", "N8.2": "partial", "N8.3": "partial", "N8.5": "partial", "N8.6": "not_started"},
        "inputs": smp_runtime.expected_inputs(ROOT),
        "build": {"kernel_entry": kernel_readiness, "default_pooleboot": default_build, "smp_percpu_runtime_pooleboot": runtime_build, "profile_count": 2, "all_profile_binaries_distinct": True, "default_stop_marker_present": True, "default_transfer_marker_absent": True, "source_audit": source_audit},
        "media": {"clean_generation_count": 2, "exact_clean_generation_match": True, "sha256": smp_runtime.sha256_bytes(media_one), "byte_count": len(media_one), "inspection": media_inspection, "ordinary_workspace_file_only": True, "physical_media_write_performed": False},
        "execution": {
            "host_environment_count": 1, "run_count": 2, "profile_id": "sandybridge-x87-sse-two-vcpu",
            "machine": "pc-q35-11.0", "cpu_model": "SandyBridge,-avx", "virtual_cpu_count": 2,
            "acceleration": "tcg_multi_thread", "deterministic_instruction_clock": False,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"], "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command, "normalized_command_sha256": smp_runtime.sha256_bytes(native_pooleboot.canonical_json_bytes(command)),
            "fresh_vars_each_run": True, "media_read_only": True, "guest_network": False, "host_acceleration": False,
            "static_markers_exact_match": True, "dynamic_fields_revalidated": True,
            "exact_screenshot_match": True, "exact_pbp1_match": True, "runs": runs, "observation": observation,
        },
        "negative_controls": controls, "claims": contract["claims"], "non_claims": contract["non_claims"],
        "summary": {
            "kernel_host_tests_passed": kernel_readiness["host_tests"]["test_pass_count"], "kernel_host_tests_total": kernel_readiness["host_tests"]["test_count"],
            "qemu_runs_passed": 2, "qemu_runs_total": 2, "markers_per_run": smp_runtime.MARKER_COUNT,
            "negative_controls_passed": len(controls), "negative_controls_total": len(controls), "hostile_cases_total": sum(item["case_count"] for item in controls),
            "application_processors_started": 1, "application_processors_online": 1, "application_processors_quiesced": 1, "application_processors_parked": 1,
            "processor_local_descriptor_sets": 1, "guarded_stack_classes": 3, "xstate_round_trips": 1, "installed_gates": 27,
            "resource_pages_released": observation["release"]["resources_released"], "zeroed_bytes": observation["release"]["zeroed_bytes"],
            "verified_bytes": observation["release"]["verified_bytes"], "production_claim_count": 0,
        },
        "open_items": [
            "Inject live failures after INIT and each SIPI and prove final-INIT park before retained-resource cleanup.",
            "Implement capability-gated IPI delivery with sender, target, vector, generation, timeout, and acknowledgement checks.",
            "Implement acknowledged SMP TLB shootdown before remote PKVM3 generation retirement.",
            "Implement scheduler CPU ownership, migration barriers, idle states, and AP work dispatch.",
            "Generalize from one AP to all enabled processors with deterministic partial-start rollback.",
            "Add x2APIC, topology hierarchy, NUMA, hotplug, and multi-socket policy only under separate contracts.",
            "Qualify the exact physical target and all 16 logical processors; no target claim exists here.",
        ],
    }
    errors = list(validate_json(report, smp_runtime.read_json(ROOT / smp_runtime.READINESS_SCHEMA_RELATIVE)))
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-28")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)
    try:
        report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
        errors = smp_runtime.readiness_errors(smp_runtime.read_json(args.out), ROOT)
        if errors:
            raise QualificationError("; ".join(errors))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, QualificationError, smp_runtime.KernelSmpPerCpuRuntimeError, native_kernel_load.KernelLoadError, native_kernel_transfer.KernelTransferError, native_tier0.Tier0Error) as error:
        print(f"NATIVE_KERNEL_SMP_PERCPU_RUNTIME_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print("NATIVE_KERNEL_SMP_PERCPU_RUNTIME_QUALIFICATION PASS "
          f"host_tests={summary['kernel_host_tests_passed']}/{summary['kernel_host_tests_total']} "
          f"runs={summary['qemu_runs_passed']}/{summary['qemu_runs_total']} markers={summary['markers_per_run']} "
          f"controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} cases={summary['hostile_cases_total']} "
          f"ap={summary['application_processors_online']}/1 gates={summary['installed_gates']} scrub={summary['verified_bytes']} "
          "n8_exit=false production_ready=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
