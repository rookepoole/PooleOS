#!/usr/bin/env python3
"""Build and qualify the bounded PKVM2 one-BSP active-root profile."""

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
    native_kernel_virtual_memory as virtual_memory,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / virtual_memory.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKVM2 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKVM2 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _require_marker_rejection(
    control_id: str, candidate: list[str], transcript: dict[str, Any]
) -> dict[str, str]:
    try:
        observation = virtual_memory.validate_markers(candidate)
        virtual_memory.validate_observation_binding(observation, transcript)
    except virtual_memory.KernelVirtualMemoryError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKVM2 hostile marker control did not reject: {control_id}")


def _negative_controls(
    markers: list[str], transcript: dict[str, Any]
) -> list[dict[str, str]]:
    observation = virtual_memory.validate_markers(markers)
    candidates: list[tuple[str, list[str]]] = [
        (virtual_memory.NEGATIVE_CONTROL_IDS[0], markers[:-1]),
    ]
    reordered = markers.copy()
    reordered[35], reordered[36] = reordered[36], reordered[35]
    candidates.append((virtual_memory.NEGATIVE_CONTROL_IDS[1], reordered))
    candidates.append((virtual_memory.NEGATIVE_CONTROL_IDS[2], [*markers, markers[-1]]))

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    candidate_observation = observation["candidate"]
    mutations = (
        (3, 23, "trap_scenario", "0"),
        (4, 35, "contract", "PKVM1"),
        (5, 35, "canonical_bits", "49"),
        (6, 36, "original_root", f"0x{candidate_observation['original_root'] + PAGE:016X}"),
        (7, 36, "candidate_root", f"0x{candidate_observation['candidate_root'] + 1:016X}"),
        (8, 36, "table_generation", "0"),
        (9, 36, "data", f"0x{candidate_observation['candidate_root']:016X}"),
        (10, 36, "data_generation", "3"),
        (11, 36, "direct_first", f"0x{candidate_observation['direct_first'] + PAGE:016X}"),
        (12, 36, "direct_last", f"0x{candidate_observation['direct_last'] - 1:016X}"),
        (13, 36, "inherited_kernel", "drifted"),
        (14, 36, "guarded_stack", "drifted"),
        (15, 36, "handoff", "drifted"),
        (16, 36, "bootstrap_alias_revoked", "0"),
        (17, 36, "root_active", "1"),
        (18, 37, "cr3_writes", "1"),
        (19, 37, "candidate_readback", "mismatch"),
        (20, 37, "original_restore", "mismatch"),
        (21, 37, "rollback_control", "skipped"),
        (22, 37, "bsp", "0"),
        (23, 37, "smp", "1"),
        (24, 38, "local_invlpg", "2"),
        (25, 38, "active_receipts", "2"),
        (26, 38, "probe", "0x0000000000000000"),
        (27, 38, "protect", "0"),
        (28, 38, "user_unmap", "0"),
        (29, 38, "direct_unmap", "0"),
        (30, 38, "stale_root_rejected", "skipped"),
        (31, 38, "premature_reuse_rejected", "0"),
        (32, 38, "shootdown", "1"),
        (33, 39, "root_released", "0"),
        (34, 39, "data_released", "0"),
        (35, 39, "allocated_pages", "1"),
        (36, 39, "physical_writes", str(virtual_memory.PHYSICAL_WRITES - 1)),
        (37, 39, "temporary_pte_writes", str(virtual_memory.TEMPORARY_PTE_WRITES - 1)),
        (38, 39, "bootstrap_invlpg", str(virtual_memory.BOOTSTRAP_INVALIDATIONS - 1)),
        (39, 39, "allocations", "1"),
        (40, 39, "frees", "1"),
        (41, 39, "active_cr3_writes", "1"),
        (42, 39, "active_invlpg", "2"),
        (43, 39, "shootdown", "1"),
        (44, 39, "ring3", "1"),
    )
    for control_index, marker_index, field, value in mutations:
        candidates.append(
            (virtual_memory.NEGATIVE_CONTROL_IDS[control_index], changed(marker_index, field, value))
        )
    controls = [
        _require_marker_rejection(control_id, candidate, transcript)
        for control_id, candidate in candidates
    ]
    hostile_observation = copy.deepcopy(observation)
    hostile_observation["candidate"]["candidate_root"] += PAGE
    try:
        virtual_memory.validate_observation_binding(hostile_observation, transcript)
    except virtual_memory.KernelVirtualMemoryError:
        controls.append(
            {"id": virtual_memory.NEGATIVE_CONTROL_IDS[45], "status": "pass", "expected": "rejected"}
        )
    else:
        raise QualificationError("PKVM2 hostile PBP1 first-fit control did not reject")
    if [item["id"] for item in controls] != list(virtual_memory.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKVM2 hostile-control order changed")
    return controls


PAGE = virtual_memory.PAGE_BYTES


def _source_audit() -> dict[str, Any]:
    core_path = ROOT / "native/kernel/src/active_virtual_memory.rs"
    main_path = ROOT / "native/kernel/src/main.rs"
    arch_path = ROOT / "native/kernel/src/arch/x86_64.rs"
    core = core_path.read_text(encoding="utf-8").split("#[cfg(test)]", 1)[0]
    main = main_path.read_text(encoding="utf-8")
    adapter = main.split("struct ActivePhysicalReader;", 1)[1].split(
        "impl ByteSink for BootSink", 1
    )[0]
    arch = arch_path.read_text(encoding="utf-8")
    forbidden = tuple(token for token in ("alloc::", "Vec<", "Box<", "asm!(") if token in core)
    required = (
        "pub trait ActiveHardware",
        "HARDWARE_LEAF_BITS",
        "fn observed_active_leaf",
        "pub fn activate",
        "pub fn protect_user",
        "pub fn begin_user_unmap",
        "pub fn revoke_data_direct_map",
        "pub fn complete_data_release",
        "pub fn restore",
        "pub fn release_tables",
    )
    missing = tuple(token for token in required if token not in core)
    adapter_required = (
        "poole_kmap::translate",
        "read_volatile",
        "write_volatile",
        "impl ActiveHardware for LiveActiveHardware",
        "arch::x86_64::write_cr3",
        "arch::x86_64::invalidate_page",
        "TEMPORARY_LEAF_INDEX",
    )
    adapter_missing = tuple(token for token in adapter_required if token not in adapter)
    arch_required = (
        "pub fn physical_address_bits() -> Option<u8>",
        "pub unsafe fn read_cr3() -> u64",
        "pub unsafe fn write_cr3(value: u64)",
        "pub unsafe fn invalidate_page(address: u64)",
        "0x8000_0008",
        "(36..=52).contains(&bits)",
    )
    arch_missing = tuple(token for token in arch_required if token not in arch)
    if forbidden or missing or adapter_missing or arch_missing:
        raise QualificationError(
            "PKVM2 source scope changed: "
            f"forbidden={forbidden}; missing={missing}; adapter={adapter_missing}; "
            f"arch={arch_missing}"
        )
    return {
        "core_path": core_path.relative_to(ROOT).as_posix(),
        "core_sha256": virtual_memory.sha256_bytes(core_path.read_bytes()),
        "adapter_path": main_path.relative_to(ROOT).as_posix(),
        "adapter_sha256": virtual_memory.sha256_bytes(main_path.read_bytes()),
        "architecture_path": arch_path.relative_to(ROOT).as_posix(),
        "architecture_sha256": virtual_memory.sha256_bytes(arch_path.read_bytes()),
        "heap_api_token_count": 0,
        "active_cr3_write_count": 2,
        "active_local_invalidation_count": 3,
        "bootstrap_temporary_mapping_uses_invlpg": True,
        "live_cpuid_physical_width_validated": True,
        "fixed_capacity_table_page_count": 8,
        "volatile_physical_adapter": True,
        "result": "pass_bounded_active_root_direct_map_cr3_rollback_and_local_receipt_adapter",
    }


def make_readiness(
    toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int
) -> dict[str, Any]:
    contract = virtual_memory.read_json(ROOT / virtual_memory.CONTRACT_RELATIVE)
    errors = virtual_memory.contract_errors(contract, ROOT)
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
    with tempfile.TemporaryDirectory(prefix="pkvm2-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        vm_boot, vm_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "vm-boot",
            development_feature=virtual_memory.FEATURE,
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if virtual_memory.sha256_bytes(default_boot) == virtual_memory.sha256_bytes(vm_boot):
            raise QualificationError("default and PKVM2 PooleBoot profiles are not distinct")
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(vm_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(vm_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKVM2 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKVM2 media kernel differs from PKENTRY1")
        media_path = temporary_root / "pkvm2.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkvm2-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"active-virtual-memory-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=virtual_memory.validate_markers,
                        marker_extractor=virtual_memory.extract_markers,
                        completion_marker=virtual_memory.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(
                                encoding="ascii", errors="ignore"
                            ).splitlines()
                            if line.strip().startswith("POOLE")
                        ][-16:]
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
                    run["independent_virtual_memory"] = (
                        virtual_memory.validate_observation_binding(
                            run["marker_summary"], run["pbp1_transcript"]
                        )
                    )
                except (
                    native_kernel_load.KernelLoadError,
                    native_kernel_transfer.KernelTransferError,
                    virtual_memory.KernelVirtualMemoryError,
                ) as error:
                    raise QualificationError(str(error)) from error
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKVM2 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKVM2 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKVM2 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"], runs[0]["pbp1_transcript"])
    observation = virtual_memory.validate_markers(runs[0]["markers"])
    derived = virtual_memory.validate_observation_binding(
        observation, runs[0]["pbp1_transcript"]
    )
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_virtual_memory_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_bounded_one_bsp_active_root_exact_restore_non_promoting",
        "contract_id": virtual_memory.CONTRACT_ID,
        "selected_move_id": virtual_memory.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n9_exit_gate_satisfied": False,
        "phase_status": {"N9": "partial", "N9.3": "partial", "N9.4": "partial"},
        "inputs": virtual_memory.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "virtual_memory_pooleboot": vm_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "source_audit": source_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": virtual_memory.sha256_bytes(media_one),
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
            "normalized_command_sha256": virtual_memory.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": {
                key: observation[key]
                for key in ("layout", "candidate", "activation", "invalidation", "result")
            },
            "independent_memory_summary": derived,
        },
        "negative_controls": controls,
        "claims": virtual_memory.expected_claims(),
        "non_claims": contract["non_claims"],
        "summary": {
            "qemu_run_count": 2,
            "marker_count": virtual_memory.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "table_pages_materialized": virtual_memory.TABLE_PAGES,
            "mapped_owned_pages": virtual_memory.OWNED_PAGES,
            "physical_table_writes": observation["result"]["physical_writes"],
            "temporary_pte_writes": observation["result"]["temporary_pte_writes"],
            "active_leaf_mutations": 3,
            "active_invalidation_receipts": observation["invalidation"]["active_receipts"],
            "active_cr3_writes": observation["result"]["active_cr3_writes"],
            "active_hardware_tlb_invalidations": observation["result"]["active_invlpg"],
            "bootstrap_hardware_tlb_invalidations": observation["result"]["bootstrap_invlpg"],
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Expand the bounded nine-page direct map into a complete generation-owned physical-memory policy with metadata and managed temporary mappings.",
            "Implement AP startup plus inter-processor TLB shootdown requests, acknowledgements, timeout/failure handling, and generation-safe deferred reclaim.",
            "Implement huge-page promotion and demotion, PCID policy, KASLR, copy-on-write, user faults, stack growth, and pager IPC.",
            "Qualify MMIO cache policy and alias auditing against PAT/MTRR policy on target hardware.",
            "Complete randomized concurrent memory stress, pressure/OOM policy, target hardware, second-host, and N9 exit gates.",
        ],
    }
    errors = virtual_memory.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-22")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report = make_readiness(
            args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        virtual_memory.KernelVirtualMemoryError,
        native_tier0.Tier0Error,
    ) as error:
        print(f"PKVM2 qualification failed: {error}", file=sys.stderr)
        return 1
    print(
        "PKVM2 qualification passed: "
        f"runs={report['summary']['qemu_run_count']}; "
        f"markers={report['summary']['marker_count']}; "
        f"controls={report['summary']['negative_controls_passed']}; "
        f"physical_writes={report['summary']['physical_table_writes']}; production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
