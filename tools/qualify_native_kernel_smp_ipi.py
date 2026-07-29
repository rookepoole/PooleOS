#!/usr/bin/env python3
"""Build and qualify the bounded two-vCPU PKSMP3 IPI transport."""

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
    native_kernel_smp_ipi as smp_ipi,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / smp_ipi.READINESS_RELATIVE
HOSTILE_CASE_COUNT = 120


class QualificationError(RuntimeError):
    """Raised when PKSMP3 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSMP3 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSMP3 mutation field is missing: {field}")
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
        except smp_ipi.KernelSmpIpiError:
            continue
        raise QualificationError(f"PKSMP3 hostile control did not reject: {control_id}")
    return {"id": control_id, "status": "pass", "expected": "rejected", "case_count": len(operations)}


def _marker_operation(candidate: list[str]) -> Callable[[], Any]:
    return lambda: smp_ipi.validate_markers(candidate)


def _field_matrix(control_id: str, markers: list[str], marker_index: int, fields: tuple[str, ...]) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        candidate = markers.copy()
        candidate[marker_index] = _set_field(candidate[marker_index], field, _invalid_value(candidate[marker_index], field))
        operations.append(_marker_operation(candidate))
    return _require_rejections(control_id, operations)


def _audit_source_text(arch_text: str, main_text: str, ipi_text: str) -> dict[str, Any]:
    required_arch = (
        "poole_ap_ipi_trampoline_start:",
        ".code16",
        ".code32",
        ".code64",
        "poole_ap_ipi_reschedule:",
        "poole_ap_ipi_shootdown:",
        "poole_ap_ipi_call_function:",
        "poole_ap_ipi_diagnostic:",
        "poole_ap_ipi_panic:",
        "poole_ap_ipi_stop:",
        "poole_ap_ipi_apic_error:",
        "poole_ap_ipi_spurious:",
        "xsave64 [rbx]",
        "xrstor64 [rbx]",
    )
    required_main = (
        "smp_ipi_prepare_resources",
        "smp_ipi_publish_request",
        "smp_ipi_wait_ack",
        "smp_ipi_deliver",
        "smp_ipi_validate_post_ap_resources",
        "SMP_IPI_ENTRY_ACCESSED",
        "SMP_IPI_ENTRY_DIRTY",
        "transaction.exercised()?",
        "transaction.quiesced()?",
        "transaction.parked()?",
        "transaction.validated()?",
        "transaction.released()?",
    )
    required_ipi = (
        "pub const EXTENSION_BYTES: usize",
        "pub const MAILBOX_BYTES: usize",
        "pub const CAPABILITY_HIGH",
        "pub const CAPABILITY_LOW",
        "pub const REQUEST_CHECKSUM_SEED",
        "pub const RESPONSE_CHECKSUM_SEED",
        "pub fn validate_request",
        "pub fn validate_final",
        "pub struct IpiTransaction",
    )
    smp_ipi._require(all(token in arch_text for token in required_arch), "PKSMP3 trampoline source audit failed")
    smp_ipi._require(
        arch_text.count("xsave64 [rbx]") >= 2 and arch_text.count("xrstor64 [rbx]") >= 2,
        "PKSMP3 inherited and IPI xstate paths are incomplete",
    )
    smp_ipi._require(all(token in main_text for token in required_main), "PKSMP3 lifecycle source audit failed")
    smp_ipi._require(all(token in ipi_text for token in required_ipi), "PKSMP3 transport source audit failed")
    diagnostic_tokens = ("PKSMP3_DENIED_STAGE", "PKSMP3_DENIED_MAILBOX", "PKSMP3_DENIED_DETAIL", "PKSMP3DBG")
    smp_ipi._require(not any(token in arch_text + main_text + ipi_text for token in diagnostic_tokens), "PKSMP3 transient diagnostics remain")
    return {
        "trampoline_mode_count": 3,
        "operation_handler_count": 6,
        "controller_handler_count": 2,
        "xsave_instruction_count": arch_text.count("xsave64 [rbx]"),
        "xrstor_instruction_count": arch_text.count("xrstor64 [rbx]"),
        "resource_page_count": 32,
        "guard_page_count": 14,
        "identity_mapped_page_count": 13,
        "apic_page_table_offset": 31,
        "transient_diagnostic_token_count": 0,
    }


def _source_audit() -> dict[str, Any]:
    paths = {
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "ipi": ROOT / "native/kernel/src/smp_ipi.rs",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    result = _audit_source_text(texts["arch"], texts["main"], texts["ipi"])
    result["files"] = {
        name: {"path": path.relative_to(ROOT).as_posix(), "sha256": smp_ipi.sha256_bytes(path.read_bytes())}
        for name, path in paths.items()
    }
    return result


def _negative_controls(markers: list[str]) -> list[dict[str, Any]]:
    smp_ipi.validate_markers(markers)
    ids = smp_ipi.NEGATIVE_CONTROL_IDS
    controls = [_require_rejections(ids[0], [_marker_operation(markers[:-1])])]
    reordered = markers.copy()
    reordered[33], reordered[34] = reordered[34], reordered[33]
    controls.append(_require_rejections(ids[1], [_marker_operation(reordered)]))
    controls.append(_require_rejections(ids[2], [_marker_operation([*markers, markers[-1]])]))
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "13")
    prefix = markers.copy()
    prefix[0] += " invalid"
    controls.append(_require_rejections(ids[3], [_marker_operation(selector), _marker_operation(prefix)]))

    matrices = (
        (ids[4], 30, ("contract", "processors", "enabled", "bsp_apic_id", "target_apic_id", "apic_physical", "selection")),
        (ids[5], 31, ("contract", "physical_start", "pages", "sipi_vector", "trampoline_bytes", "allocation_sequence", "tables", "mapped_pages", "guard_pages", "apic_pt_offset", "apic_leaf", "below_1mib")),
        (ids[6], 32, ("contract", "service_state", "if", "vectors", "apic_mmio", "apic_table")),
        (ids[7], 33, ("contract", "operations", "sequences", "accepted", "reschedule", "shootdown", "call_function", "diagnostic", "panic", "stop")),
        (ids[8], 34, ("contract", "invalid_capability", "vector_mismatch", "stale_sequence", "duplicate_sequence", "denied", "delivery_count", "eoi_count", "spurious", "apic_error")),
        (ids[9], 35, ("contract", "target_apic_id", "attempt", "bounded", "offline_cpu", "timeout_count")),
        (ids[10], 36, ("contract", "ack_attempt", "ack_sequence", "last_accepted_sequence", "service_state", "mailbox_state", "runtime_state", "panic_latched", "response_checksum", "baseline_checksum", "runtime_checksum", "init_asserts", "init_deasserts", "sipis", "tss_busy", "idt_verified", "xstate_verified", "apic_table_verified", "final_init", "parked")),
        (ids[11], 37, ("contract", "release_sequence", "zeroed_bytes", "verified_bytes", "resources_released", "capability_revoked", "runtime_revoked", "mmio_revoked", "pic_restored", "hpet_restored", "apic_base_restored")),
        (ids[12], 38, ("contract", "profile", "capability_gate", "operation_classes", "valid_deliveries", "denied_deliveries", "offline_timeouts", "eois", "panic_latched", "stop_quiesced", "ap_parked", "resources_released", "rollback", "shootdown_transport_only", "tlb_invalidations", "call_allowlist_noop", "arbitrary_callback", "scheduler", "target", "signatures", "authority", "actions", "production", "terminal")),
    )
    controls.extend(_field_matrix(control_id, markers, marker_index, fields) for control_id, marker_index, fields in matrices)

    arch = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
    main = (ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
    ipi = (ROOT / "native/kernel/src/smp_ipi.rs").read_text(encoding="utf-8")
    controls.append(_require_rejections(ids[13], [lambda: _audit_source_text(arch.replace("xrstor64 [rbx]", "xrstor64 [rax]", 1), main, ipi)]))
    controls.append(_require_rejections(ids[14], [lambda: smp_ipi.resource_layout(1, 31), lambda: smp_ipi.resource_layout(0, 32)]))

    request = smp_ipi.canonical_request(1, 1, 1, 1)
    invalid_high = request.copy()
    invalid_high["capability_high"] ^= 1
    invalid_high["checksum"] = smp_ipi.request_checksum(invalid_high)
    invalid_low = request.copy()
    invalid_low["capability_low"] ^= 1
    invalid_low["checksum"] = smp_ipi.request_checksum(invalid_low)
    controls.append(_require_rejections(ids[15], [lambda: smp_ipi.validate_request(invalid_high, 1, 1, 0, 0), lambda: smp_ipi.validate_request(invalid_low, 1, 1, 0, 0)]))

    wrong_vector = request.copy()
    wrong_vector["vector"] = 225
    wrong_vector["checksum"] = smp_ipi.request_checksum(wrong_vector)
    controls.append(_require_rejections(ids[16], [lambda: smp_ipi.validate_request(wrong_vector, 1, 1, 0, 0), lambda: smp_ipi.validate_request(request, 2, 1, 0, 0)]))

    stale = smp_ipi.canonical_request(2, 1, 2, 1)
    duplicate = smp_ipi.canonical_request(2, 2, 2, 1)
    controls.append(_require_rejections(ids[17], [lambda: smp_ipi.validate_request(stale, 2, 1, 1, 1), lambda: smp_ipi.validate_request(duplicate, 2, 1, 1, 2)]))

    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSMP3 hostile-control order diverged")
    case_count = sum(item["case_count"] for item in controls)
    if case_count != HOSTILE_CASE_COUNT:
        raise QualificationError(f"PKSMP3 hostile-case count changed: {case_count}")
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
    del arguments[icount : icount + 2]
    derived["machine"].update({"cpu_model": "SandyBridge,-avx", "vcpus": 2, "cores": 2, "tcg_thread_mode": "multi"})
    return derived


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = smp_ipi.read_json(ROOT / smp_ipi.CONTRACT_RELATIVE)
    errors = smp_ipi.contract_errors(contract, ROOT)
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
    with tempfile.TemporaryDirectory(prefix="pksmp3-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        ipi_boot, ipi_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "ipi-boot", development_feature=smp_ipi.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if smp_ipi.sha256_bytes(default_boot) == smp_ipi.sha256_bytes(ipi_boot):
            raise QualificationError("default and PKSMP3 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(ipi_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(ipi_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKSMP3 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksmp3.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksmp3-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"smp-ipi-run-{run_index}", lock, profile, qemu_root, media_path,
                        run_directory, timeout, marker_validator=smp_ipi.validate_markers,
                        marker_extractor=smp_ipi.extract_markers, completion_marker=smp_ipi.COMPLETION_MARKER,
                    )
                except (qualify_native_pooleboot.QualificationError, smp_ipi.KernelSmpIpiError) as error:
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
        normalized_markers = [smp_ipi.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized_markers[0] != normalized_markers[1]:
            raise QualificationError("two PKSMP3 runs emitted different static markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSMP3 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSMP3 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"])
    observation = smp_ipi.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_smp_ipi_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_sandybridge_two_vcpu_capability_ipi_transport_non_promoting",
        "contract_id": smp_ipi.CONTRACT_ID,
        "selected_move_id": smp_ipi.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n8_exit_gate_satisfied": False,
        "flag_n8_smp_ipi_001_closed": True,
        "phase_status": {"N8": "partial", "N8.1": "partial", "N8.2": "partial", "N8.3": "partial", "N8.5": "partial", "N8.6": "not_started"},
        "inputs": smp_ipi.expected_inputs(ROOT),
        "build": {"kernel_entry": kernel_readiness, "default_pooleboot": default_build, "smp_ipi_pooleboot": ipi_build, "profile_count": 2, "all_profile_binaries_distinct": True, "default_stop_marker_present": True, "default_transfer_marker_absent": True, "source_audit": source_audit},
        "media": {"clean_generation_count": 2, "exact_clean_generation_match": True, "sha256": smp_ipi.sha256_bytes(media_one), "byte_count": len(media_one), "inspection": media_inspection, "ordinary_workspace_file_only": True, "physical_media_write_performed": False},
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "sandybridge-x87-sse-two-vcpu",
            "machine": "pc-q35-11.0",
            "cpu_model": "SandyBridge,-avx",
            "virtual_cpu_count": 2,
            "acceleration": "tcg_multi_thread",
            "deterministic_instruction_clock": False,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "static_markers_exact_match": True,
            "dynamic_fields_revalidated": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": observation,
        },
        "negative_controls": controls,
        "claims": contract["claims"],
        "non_claims": contract["non_claims"],
        "summary": {"application_processors_online": 1, "operation_classes": 6, "accepted_deliveries": 6, "denied_deliveries": 4, "offline_timeouts": 1, "eois": 10, "resource_pages_released": 32, "verified_bytes": 131072, "negative_controls_total": len(controls), "hostile_cases_total": sum(item["case_count"] for item in controls), "production_claim_count": 0},
        "open_items": ["general multi-AP SMP", "real TLB shootdown and generation retirement", "scheduler CPU ownership", "capability minting and revocation authority", "live partial-start fault injection", "x2APIC and topology matrix", "physical-target evidence", "N8 exit gate", "production signing and promotion"],
    }
    errors = smp_ipi.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--status-date", default="2026-07-29")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(args.toolchain_root, args.qemu_root, args.status_date, args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PKSMP3 qualification PASS: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
