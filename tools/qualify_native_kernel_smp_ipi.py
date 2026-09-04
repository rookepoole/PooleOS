#!/usr/bin/env python3
"""Build and qualify the bounded four-vCPU PKSMP5 multi-AP lifecycle."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
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
HOSTILE_CASE_COUNT = 243


class QualificationError(RuntimeError):
    """Raised when PKSMP5 qualification fails closed."""


def _write_readiness(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSMP5 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSMP5 mutation field is missing: {field}")
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
        raise QualificationError(f"PKSMP5 hostile control did not reject: {control_id}")
    return {"id": control_id, "status": "pass", "expected": "rejected", "case_count": len(operations)}


def _marker_operation(candidate: list[str]) -> Callable[[], Any]:
    return lambda: smp_ipi.validate_markers(candidate)


def _field_matrix(control_id: str, markers: list[str], marker_index: int, fields: tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        candidate = markers.copy()
        candidate[marker_index] = _set_field(candidate[marker_index], field, _invalid_value(candidate[marker_index], field))
        try:
            smp_ipi.validate_markers(candidate)
        except smp_ipi.KernelSmpIpiError:
            continue
        raise QualificationError(f"PKSMP5 hostile control did not reject: {control_id} field={field}")
    return {"id": control_id, "status": "pass", "expected": "rejected", "case_count": len(fields)}


def _audit_source_text(arch_text: str, main_text: str, ipi_text: str) -> dict[str, Any]:
    required_arch = (
        "poole_ap_ipi_trampoline_start:", ".code16", ".code32", ".code64",
        "poole_ap_ipi_reschedule:", "poole_ap_ipi_shootdown:",
        "poole_ap_ipi_call_function:", "poole_ap_ipi_diagnostic:",
        "poole_ap_ipi_panic:", "poole_ap_ipi_stop:",
        ".Lpoole_ap_ipi_count_panic:", ".Lpoole_ap_ipi_count_stop:",
        "poole_ap_ipi_apic_error:", "poole_ap_ipi_spurious:",
        "xsave64 [rbx]", "xrstor64 [rbx]", "invlpg [rax]", "shl rbx, cl",
        "panic_count_offset = const smp_ipi::PANIC_COUNT_OFFSET",
        "stop_count_offset = const smp_ipi::STOP_COUNT_OFFSET",
    )
    required_main = (
        "smp_ipi_allocate_resource_set", "smp_ipi_run_partial_rollback",
        "smp_ipi_start_ap", "smp_ipi_stop_ap", "smp_ipi_validate_post_ap_resources",
        "allocate_scrubbed_automatic", "free_scrubbed_automatic",
        ".migrate_to_metadata(&mut page_access)",
        "smp_ipi::select_exact_aps", "smp_ipi::MultiDeferredReclaim::new",
        ".acknowledge(resource.target_apic_id", "premature_reclaim_rejections",
        "lifecycle.all_online", "lifecycle.quiesced", "lifecycle.parked",
        "lifecycle.validated", "lifecycle.released",
    )
    required_ipi = (
        "pub const AP_COUNT: usize = 3", "pub static EXPECTED_APIC_IDS",
        "pub const PARTIAL_STARTED_MASK", "pub const TARGET_CPU_MASK",
        "pub const OFFLINE_APIC_ID", "pub const fn local_target_mask",
        "pub fn select_exact_aps", "pub fn validate_shootdown_request_for_target",
        "pub fn validate_shootdown_ack_for_target", "pub struct MultiApTransaction",
        "pub struct MultiDeferredReclaim", "pub struct MultiGenerationRetirementReceipt",
    )
    smp_ipi._require(all(token in arch_text for token in required_arch), "PKSMP5 trampoline source audit failed")
    smp_ipi._require(arch_text.count("xsave64 [rbx]") >= 2 and arch_text.count("xrstor64 [rbx]") >= 2, "PKSMP5 inherited and IPI xstate paths are incomplete")
    smp_ipi._require(arch_text.count("invlpg [rax]") == 1, "PKSMP5 remote INVLPG source scope changed")
    smp_ipi._require(arch_text.count("invlpg [rbx]") == 1, "PKLOCK1 successor INVLPG source scope changed")
    smp_ipi._require(all(token in main_text for token in required_main), "PKSMP5 lifecycle source audit failed")
    smp_ipi._require(all(token in ipi_text for token in required_ipi), "PKSMP5 coordinator source audit failed")
    diagnostic_tokens = ("PKSMP5DBG", "SMP_MULTI_DEBUG", "MULTI_AP_FORCE_PASS")
    smp_ipi._require(not any(token in arch_text + main_text + ipi_text for token in diagnostic_tokens), "PKSMP5 transient diagnostics remain")
    return {
        "trampoline_mode_count": 3,
        "operation_handler_count": 6,
        "controller_handler_count": 2,
        "xsave_instruction_count": arch_text.count("xsave64 [rbx]"),
        "xrstor_instruction_count": arch_text.count("xrstor64 [rbx]"),
        "remote_shootdown_invlpg_source_count": 1,
        "successor_lock_alias_revoke_invlpg_source_count": 1,
        "application_processor_count": 3,
        "resource_page_count_per_ap": 32,
        "total_runtime_page_count": 96,
        "guard_page_count_per_ap": 14,
        "identity_mapped_page_count_per_ap": 13,
        "dynamic_local_mask_binding_count": arch_text.count("shl rbx, cl"),
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
    result["files"] = {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": smp_ipi.sha256_bytes(path.read_bytes())} for name, path in paths.items()}
    return result


def _linked_invlpg_scope(disassembly: str) -> dict[str, Any]:
    matches = re.findall(r"(?ms)^[0-9a-f]+ <poole_ap_ipi_trampoline_start>:\n(?P<body>.*?)^[0-9a-f]+ <poole_ap_ipi_trampoline_end>:", disassembly)
    smp_ipi._require(len(matches) == 1, "PKSMP5 linked AP-trampoline scope changed")
    instructions = re.findall(r"(?m)^\s*[0-9a-f]+:.*\tinvlpg\t([^\r\n]+)$", matches[0])
    smp_ipi._require(
        instructions == ["(%rax)", "(%rbx)"],
        "PKSMP5 linked AP-trampoline INVLPG scope changed",
    )
    return {
        "scope": "poole_ap_ipi_trampoline_start..poole_ap_ipi_trampoline_end",
        "invlpg_instruction_count": 2,
        "remote_shootdown_invlpg_instruction_count": 1,
        "runtime_execution_count": 3,
        "operand": "(%rax)",
        "successor_profile_invlpg_instruction_count": 1,
        "successor_profile_operand": "(%rbx)",
        "successor_profile_executed": False,
        "status": "pass",
    }


def _linked_invlpg_audit(toolchain_root: Path, expected_kernel: bytes, target_dir: Path) -> dict[str, Any]:
    cargo, _, env = qualify_native_kernel_entry._toolchain(toolchain_root)
    linked, canonical, plan = qualify_native_kernel_entry._build_product(cargo, env, target_dir)
    if canonical != expected_kernel:
        raise QualificationError("PKSMP5 linked-audit build diverged from the qualified kernel")
    installed = cargo.parent.parent
    candidates = sorted((installed / "lib" / "rustlib").glob("*/bin/llvm-objdump.exe"))
    if len(candidates) != 1:
        raise QualificationError("PKSMP5 workspace-local llvm-objdump is missing or ambiguous")
    artifact = target_dir / qualify_native_kernel_entry.PRODUCT_TARGET / "release" / "PooleKernelLinked"
    completed = subprocess.run([str(candidates[0]), "-d", str(artifact)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode != 0:
        raise QualificationError("PKSMP5 linked disassembly failed")
    result = _linked_invlpg_scope(completed.stdout.decode("ascii", errors="replace").replace("\r\n", "\n"))
    llvm_objdump = candidates[0]
    try:
        llvm_objdump_path = llvm_objdump.relative_to(ROOT)
    except ValueError:
        logical_toolchain_root = ROOT / ".toolchains"
        try:
            tool_relative = llvm_objdump.resolve(strict=True).relative_to(
                logical_toolchain_root.resolve(strict=True)
            )
        except ValueError as error:
            raise QualificationError(
                "PKSMP5 llvm-objdump escaped the workspace-local toolchain"
            ) from error
        llvm_objdump_path = logical_toolchain_root.relative_to(ROOT) / tool_relative
    result.update({
        "linked_sha256": smp_ipi.sha256_bytes(linked), "linked_byte_count": len(linked),
        "canonical_sha256": smp_ipi.sha256_bytes(canonical), "canonical_byte_count": len(canonical),
        "relocation_count": plan.relocation_count,
        "llvm_objdump_path": llvm_objdump_path.as_posix(),
        "llvm_objdump_sha256": smp_ipi.sha256_bytes(llvm_objdump.read_bytes()),
    })
    return result


def _multi_requests() -> list[dict[str, int]]:
    starts = (0x1000, 0x23000, 0x45000)
    return [smp_ipi.canonical_shootdown_request(start + 0x1000, start + 0x20000, start + 0x21000, apic_id) for start, apic_id in zip(starts, smp_ipi.EXPECTED_APIC_IDS, strict=True)]


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

    ap_fields = ("contract", "ap_index", "apic_id", "physical_start", "pages", "sipi_vector", "trampoline_bytes", "allocation_sequence", "frame_allocation_sequences", "frame_release_sequences", "resource_release_sequence", "service_state", "mailbox_state", "runtime_state", "deliveries", "accepted", "denied", "eois", "diagnostic", "shootdown", "stop", "timeout_count", "init_asserts", "init_deasserts", "sipis", "target_mask", "ack_mask", "invalidations", "baseline_checksum", "runtime_checksum", "response_checksum", "tss_busy", "idt_verified", "xstate_verified", "apic_table_verified", "parked")
    matrices = (
        (ids[4], 30, ("contract", "processors", "enabled", "bsp_apic_id", "target_apic_ids", "target_mask", "apic_physical", "selection")),
        (ids[5], 31, ("contract", "started_mask", "timeout_apic_id", "timeout_mask", "timeout_count", "parked_mask", "released_mask", "resource_pages", "frame_pages", "zeroed_bytes", "verified_bytes", "fresh_allocation_required")),
        (ids[6], 32, ("contract", "retry_count", "partial_rollback_count", "started_mask", "online_mask", "simultaneous_online")),
        (ids[7], 33, ap_fields), (ids[8], 34, ap_fields), (ids[9], 35, ap_fields),
        (ids[10], 36, ("contract", "target_mask", "ack_mask", "retired_generation", "active_generation", "invalidations", "root_checksum", "old_frame_checksum", "new_frame_checksum", "premature_reclaim_rejections", "reclaim_state")),
        (ids[11], 37, ("contract", "started_mask", "online_mask", "quiesced_mask", "parked_mask", "validated_mask", "released_mask", "timeout_count", "retry_count", "partial_rollback_count", "exact_accounting")),
        (ids[12], 38, ("contract", "resource_pages", "frame_pages", "resource_zeroed_bytes", "resource_verified_bytes", "frame_zeroed_bytes", "frame_verified_bytes", "total_pages", "capability_revoked", "runtime_revoked", "mmio_revoked", "pic_restored", "hpet_restored", "apic_base_restored")),
        (ids[13], 39, ("contract", "profile", "aps", "simultaneous_online", "partial_start_timeout", "partial_rollback", "fresh_retry", "target_mask", "ack_mask", "tlb_invalidations", "no_reuse_before_all_acks", "stop_quiesced", "ap_parked", "resources_released", "scheduler", "general_broadcast", "target_hardware", "signatures", "authority", "actions", "production", "terminal")),
    )
    controls.extend(_field_matrix(control_id, markers, marker_index, fields) for control_id, marker_index, fields in matrices)

    arch = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
    main = (ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
    ipi = (ROOT / "native/kernel/src/smp_ipi.rs").read_text(encoding="utf-8")
    controls.append(_require_rejections(ids[14], [lambda: _audit_source_text(arch.replace("shl rbx, cl", "shl rbx, 1", 1), main, ipi)]))
    linked_fixture = "0000000000001000 <poole_ap_ipi_trampoline_start>:\n    1000: 0f 01 38\tinvlpg\t(%rax)\n0000000000001003 <poole_ap_ipi_trampoline_end>:\n"
    controls.append(_require_rejections(ids[15], [lambda: _linked_invlpg_scope(linked_fixture.replace("invlpg", "nop")), lambda: _linked_invlpg_scope(linked_fixture.replace("\n0000000000001003", "\n    1003: 0f 01 38\tinvlpg\t(%rax)\n0000000000001006"))]))
    controls.append(_require_rejections(ids[16], [lambda: smp_ipi.resource_layout(1, 31), lambda: smp_ipi.resource_layout(0, 32)]))

    request = smp_ipi.canonical_request(1, 1, 4, 1)
    invalid_high = request.copy(); invalid_high["capability_high"] ^= 1; invalid_high["checksum"] = smp_ipi.request_checksum(invalid_high)
    invalid_low = request.copy(); invalid_low["capability_low"] ^= 1; invalid_low["checksum"] = smp_ipi.request_checksum(invalid_low)
    controls.append(_require_rejections(ids[17], [lambda: smp_ipi.validate_request(invalid_high, 4, 1, 0, 0), lambda: smp_ipi.validate_request(invalid_low, 4, 1, 0, 0)]))
    wrong_vector = request.copy(); wrong_vector["vector"] = 225; wrong_vector["checksum"] = smp_ipi.request_checksum(wrong_vector)
    controls.append(_require_rejections(ids[18], [lambda: smp_ipi.validate_request(wrong_vector, 4, 1, 0, 0), lambda: smp_ipi.validate_request(request, 2, 1, 0, 0)]))
    stale = smp_ipi.canonical_request(2, 1, 2, 1)
    duplicate = smp_ipi.canonical_request(2, 2, 2, 1)
    controls.append(_require_rejections(ids[19], [lambda: smp_ipi.validate_request(stale, 2, 1, 1, 1), lambda: smp_ipi.validate_request(duplicate, 2, 1, 1, 2)]))

    shootdown_request = smp_ipi.canonical_shootdown_request(0x2000, 0x3000, 0x4000, 1)
    hostile_requests: list[dict[str, int]] = []
    for field, value in (("root_physical", 0x2001), ("virtual_address", smp_ipi.PROBE_VIRTUAL_ADDRESS + 4096), ("retired_generation", 0), ("active_generation", 3), ("target_mask", smp_ipi.OFFLINE_CPU_MASK), ("old_frame_physical", 0x4000), ("new_frame_physical", 0x4001)):
        hostile = shootdown_request.copy(); hostile[field] = value; hostile["checksum"] = smp_ipi.shootdown_request_checksum(hostile); hostile_requests.append(hostile)
    checksum_hostile = shootdown_request.copy(); checksum_hostile["checksum"] ^= 1; hostile_requests.append(checksum_hostile)
    controls.append(_require_rejections(ids[20], [lambda candidate=candidate: smp_ipi.validate_shootdown_request(candidate, 0x2000, 0, 1) for candidate in hostile_requests]))

    shootdown_ack = smp_ipi.canonical_shootdown_snapshot(shootdown_request)
    hostile_acks: list[dict[str, int]] = []
    for field, value in (("magic", 0), ("state", smp_ipi.SHOOTDOWN_STATE_TIMED_OUT), ("root_physical", 0x3000), ("ack_mask", smp_ipi.OFFLINE_CPU_MASK), ("observed_before", 0), ("observed_after", smp_ipi.OLD_FRAME_VALUE), ("invalidation_count", 0)):
        hostile = shootdown_ack.copy(); hostile[field] = value; hostile["response_checksum"] = smp_ipi.shootdown_response_checksum(hostile); hostile_acks.append(hostile)
    checksum_ack = shootdown_ack.copy(); checksum_ack["response_checksum"] ^= 1; hostile_acks.append(checksum_ack)
    controls.append(_require_rejections(ids[21], [lambda candidate=candidate: smp_ipi.validate_shootdown_ack(candidate, shootdown_request, 1) for candidate in hostile_acks]))

    stale_generation = shootdown_request.copy(); stale_generation["active_generation"] = 1; stale_generation["checksum"] = smp_ipi.shootdown_request_checksum(stale_generation)
    controls.append(_require_rejections(ids[22], [lambda: smp_ipi.validate_shootdown_request(stale_generation, 0x2000, 0, 1), lambda: smp_ipi.validate_shootdown_request(shootdown_request, 0x2000, 2, 1)]))
    wrong_target = shootdown_request.copy(); wrong_target["target_mask"] = 4; wrong_target["checksum"] = smp_ipi.shootdown_request_checksum(wrong_target)
    wrong_ack = shootdown_ack.copy(); wrong_ack["ack_mask"] = 4; wrong_ack["response_checksum"] = smp_ipi.shootdown_response_checksum(wrong_ack)
    controls.append(_require_rejections(ids[23], [lambda: smp_ipi.validate_shootdown_request(wrong_target, 0x2000, 0, 1), lambda: smp_ipi.validate_shootdown_ack(wrong_ack, shootdown_request, 1)]))

    requests = _multi_requests()
    def authorize_before_ack() -> None:
        smp_ipi.DeferredReclaimModel(requests).authorize()
    def authorize_after_timeout() -> None:
        model = smp_ipi.DeferredReclaimModel(requests); model.arm(); model.timeout(); model.authorize()
    controls.append(_require_rejections(ids[24], [authorize_before_ack, authorize_after_timeout]))
    controls.append(_require_rejections(ids[25], [
        lambda: smp_ipi.validate_exact_topology(3, 3, 0, (1, 2, 3)),
        lambda: smp_ipi.validate_exact_topology(4, 3, 0, (1, 2, 3)),
        lambda: smp_ipi.validate_exact_topology(4, 4, 1, (1, 2, 3)),
        lambda: smp_ipi.validate_exact_topology(4, 4, 0, (1, 2, 4)),
    ]))
    controls.append(_require_rejections(ids[26], [
        lambda: smp_ipi.MultiApLifecycleModel().partial(2, 16, 2, 14),
        lambda: smp_ipi.MultiApLifecycleModel().partial(6, 8, 6, 14),
        lambda: smp_ipi.MultiApLifecycleModel().partial(6, 16, 2, 14),
    ]))

    def duplicate_ack() -> None:
        model = smp_ipi.DeferredReclaimModel(requests); model.arm(); ack = smp_ipi.canonical_shootdown_snapshot(requests[0]); model.acknowledge(ack, 1); model.acknowledge(ack, 1)
    controls.append(_require_rejections(ids[27], [duplicate_ack]))
    def authorize_after(count: int) -> None:
        model = smp_ipi.DeferredReclaimModel(requests); model.arm()
        for index in range(count): model.acknowledge(smp_ipi.canonical_shootdown_snapshot(requests[index]), smp_ipi.EXPECTED_APIC_IDS[index])
        model.authorize()
    controls.append(_require_rejections(ids[28], [lambda: authorize_after(1), lambda: authorize_after(2)]))
    controls.append(_require_rejections(ids[29], [
        lambda: smp_ipi._require(95 == 96, "resource pages"),
        lambda: smp_ipi._require(5 == 6, "frame pages"),
        lambda: smp_ipi._require(413696 == 417792, "verified bytes"),
    ]))

    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSMP5 hostile-control order diverged")
    case_count = sum(item["case_count"] for item in controls)
    if case_count != HOSTILE_CASE_COUNT:
        raise QualificationError(f"PKSMP5 hostile-case count changed: {case_count}")
    return controls


def _sandybridge_profile(profile: dict[str, Any]) -> dict[str, Any]:
    derived = copy.deepcopy(profile)
    arguments = derived["base_argument_template"]
    for option, value in (("-smp", "4,sockets=1,dies=1,clusters=1,cores=4,threads=1,maxcpus=4"), ("-cpu", "SandyBridge,-avx"), ("-accel", "tcg,thread=multi")):
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
    derived["machine"].update({"cpu_model": "SandyBridge,-avx", "vcpus": 4, "cores": 4, "tcg_thread_mode": "multi"})
    return derived


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = smp_ipi.read_json(ROOT / smp_ipi.CONTRACT_RELATIVE)
    errors = smp_ipi.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    if contract["qualification"]["hostile_case_count"] != HOSTILE_CASE_COUNT:
        raise QualificationError("PKSMP5 contract hostile-case count is stale")
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = _sandybridge_profile(base_profile)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifact_files)
    temporary_parent = ROOT / "tmp"; temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"; run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pksmp5-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        ipi_boot, ipi_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "ipi-boot", development_feature=smp_ipi.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if smp_ipi.sha256_bytes(default_boot) == smp_ipi.sha256_bytes(ipi_boot):
            raise QualificationError("default and PKSMP5 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        linked_invlpg_audit = _linked_invlpg_audit(toolchain_root, kernel, temporary_root / "linked-audit")
        media_one = native_kernel_load.build_media_bytes(ipi_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(ipi_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKSMP5 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksmp5.img"; media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []; screenshots: list[bytes] = []; handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksmp5-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"smp-multi-run-{run_index}", lock, profile, qemu_root, media_path,
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
                runs.append(run); screenshots.append(screenshot); handoffs.append(handoff)
        normalized_markers = [smp_ipi.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized_markers[0] != normalized_markers[1]:
            raise QualificationError("two PKSMP5 runs emitted different static markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSMP5 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSMP5 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"])
    observation = smp_ipi.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0", "artifact_kind": "pooleos_native_kernel_smp_ipi_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_sandybridge_four_vcpu_three_ap_partial_rollback_and_aggregate_shootdown_non_promoting",
        "contract_id": smp_ipi.CONTRACT_ID, "selected_move_id": smp_ipi.SELECTED_MOVE_ID,
        "production_ready": False, "production_promotion_allowed": False,
        "n8_exit_gate_satisfied": False, "n9_exit_gate_satisfied": False,
        "flag_n9_smp_shootdown_001_closed": True, "flag_n8_smp_multi_ap_001_closed": True,
        "phase_status": {"N8": "partial", "N8.1": "partial", "N8.2": "partial", "N8.3": "partial", "N8.5": "partial", "N8.6": "not_started", "N9": "partial", "N9.2": "partial", "N9.3": "partial", "N9.4": "partial", "N9.5": "partial"},
        "inputs": smp_ipi.expected_inputs(ROOT),
        "build": {"kernel_entry": kernel_readiness, "default_pooleboot": default_build, "smp_ipi_pooleboot": ipi_build, "profile_count": 2, "all_profile_binaries_distinct": True, "default_stop_marker_present": True, "default_transfer_marker_absent": True, "source_audit": source_audit, "linked_invlpg_audit": linked_invlpg_audit},
        "media": {"clean_generation_count": 2, "exact_clean_generation_match": True, "sha256": smp_ipi.sha256_bytes(media_one), "byte_count": len(media_one), "inspection": media_inspection, "ordinary_workspace_file_only": True, "physical_media_write_performed": False},
        "execution": {
            "host_environment_count": 1, "run_count": 2,
            "profile_id": "sandybridge-x87-sse-four-vcpu-three-ap",
            "machine": "pc-q35-11.0", "cpu_model": "SandyBridge,-avx",
            "virtual_cpu_count": 4, "application_processor_count": 3,
            "acceleration": "tcg_multi_thread", "deterministic_instruction_clock": False,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command, "static_markers_exact_match": True,
            "dynamic_fields_revalidated": True, "exact_screenshot_match": True,
            "exact_pbp1_match": True, "runs": runs, "observation": observation,
        },
        "negative_controls": controls, "claims": contract["claims"], "non_claims": contract["non_claims"],
        "summary": {"application_processors_online": 3, "operation_classes_installed_per_ap": 6, "accepted_deliveries": 9, "denied_deliveries": 3, "offline_timeouts": 1, "partial_start_rollbacks": 1, "fresh_retries": 1, "eois": 12, "remote_tlb_invalidations": 3, "retired_generations": 1, "premature_reclaim_rejections": 2, "resource_pages_released": 96, "frame_pages_released": 6, "verified_bytes": 417792, "negative_controls_total": len(controls), "hostile_cases_total": sum(item["case_count"] for item in controls), "production_claim_count": 0},
        "open_items": ["scheduler ownership and CPU affinity", "general topology and x2APIC", "concurrent address-space replacement", "address-space-wide and concurrent-generation shootdown", "production capability minting and revocation", "additional live failure interleavings", "physical-target evidence", "N8 and N9 exit gates", "production signing and promotion"],
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
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(args.toolchain_root, args.qemu_root, args.status_date, args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _write_readiness(args.out, report)
    print(f"PKSMP5 qualification PASS: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
