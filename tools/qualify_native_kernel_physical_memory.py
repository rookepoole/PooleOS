#!/usr/bin/env python3
"""Build and qualify the bounded PKPMM6 automatic-growth transaction."""

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
    native_kernel_physical_memory as physical_memory,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / physical_memory.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKPMM6 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKPMM6 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _require_marker_rejection(
    control_id: str, candidate: list[str], transcript: dict[str, Any]
) -> dict[str, str]:
    try:
        observation = physical_memory.validate_markers(candidate)
        physical_memory.validate_observation_binding(observation, transcript)
    except physical_memory.KernelPhysicalMemoryError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKPMM6 hostile marker control did not reject: {control_id}")


def _require_pbp1_rejection(
    control_id: str, observation: dict[str, Any], transcript: dict[str, Any]
) -> dict[str, str]:
    try:
        physical_memory.validate_observation_binding(observation, transcript)
    except physical_memory.KernelPhysicalMemoryError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKPMM6 hostile PBP1 control did not reject: {control_id}")


def _negative_controls(
    markers: list[str], transcript: dict[str, Any]
) -> list[dict[str, str]]:
    observation = physical_memory.validate_markers(markers)
    candidates: list[tuple[str, list[str]]] = []
    candidates.append((physical_memory.NEGATIVE_CONTROL_IDS[0], markers[:-1]))
    reordered = markers.copy()
    reordered[35], reordered[36] = reordered[36], reordered[35]
    candidates.append((physical_memory.NEGATIVE_CONTROL_IDS[1], reordered))
    candidates.append((physical_memory.NEGATIVE_CONTROL_IDS[2], [*markers, markers[-1]]))

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    mutations = (
        (23, "trap_scenario", "0"),
        (35, "contract", "PKPMM2"),
        (35, "entries", str(observation["map"]["entries"] + 1)),
        (35, "usable_pages", str(observation["map"]["usable_pages"] + 1)),
        (35, "boot_reclaimable_pages", str(observation["map"]["boot_reclaimable_pages"] + 1)),
        (35, "loader_reserved_pages", str(observation["map"]["loader_reserved_pages"] + 1)),
        (35, "null_guard_pages", "0"),
        (36, "dma_source", str(observation["zones"]["dma_source"] + 1)),
        (36, "dma_managed", str(observation["zones"]["dma_managed"] + 1)),
        (36, "dma32_source", str(observation["zones"]["dma32_source"] + 1)),
        (36, "dma32_managed", str(observation["zones"]["dma32_managed"] + 1)),
        (36, "normal_source", str(observation["zones"]["normal_source"] + 1)),
        (36, "normal_managed", str(observation["zones"]["normal_managed"] + 1)),
        (36, "extents", str(observation["zones"]["extents"] + 1)),
        (36, "largest_dma", str(observation["zones"]["largest_dma"] + 1)),
        (36, "largest_dma32", str(observation["zones"]["largest_dma32"] + 1)),
        (36, "largest_normal", str(observation["zones"]["largest_normal"] + 1)),
        (37, "kernel_base", "0x0000000000001000"),
        (37, "kernel_pages", str(observation["ownership"]["kernel_pages"] + 1)),
        (37, "handoff_base", "0x0000000000001000"),
        (37, "handoff_pages", str(observation["ownership"]["handoff_pages"] + 1)),
        (37, "root", "0x0000000000001000"),
        (37, "protected", "0"),
        (38, "pages", "4"),
        (38, "physical_start", "0x0000000000001000"),
        (38, "virtual_start", "0x0000000000001000"),
        (38, "generation", "0"),
        (38, "owner", "0"),
        (38, "manager_bytes", "0"),
        (38, "source_records", str(observation["metadata"]["source_records"] + 1)),
        (38, "free_extents", str(observation["metadata"]["free_extents"] + 1)),
        (38, "allocation_records", "2"),
        (38, "receipt_records", "2"),
        (38, "handoff_checksum", "0x0000000000000000"),
        (38, "final_checksum", "0x0000000000000000"),
        (38, "guard_pages", "1"),
        (38, "mappings", "4"),
        (38, "pte_writes", "4"),
        (38, "release_excluded", "0"),
        (38, "release_rejected", "0"),
        (38, "integrity", "0"),
        (38, "reservation_rollbacks", "1"),
        (38, "mapping_rollbacks", "1"),
        (38, "handoff", "unvalidated"),
        (38, "corruption", "unverified"),
        (38, "rollback", "unverified"),
        (39, "initial_generation", "0"),
        (39, "final_generation", "0"),
        (39, "initial_pages", "0"),
        (39, "final_pages", "0"),
        (39, "free_capacity", "0"),
        (39, "allocation_capacity", "0"),
        (39, "source_capacity", "0"),
        (39, "scrub_capacity", "0"),
        (39, "reclaim_capacity", "0"),
        (39, "retired_generation", "0"),
        (39, "retired_pages", "0"),
        (39, "mapped_pages", "0"),
        (39, "pte_writes", "0"),
        (39, "checksum", "0x0000000000000000"),
        (39, "guard_pages", "0"),
        (39, "mapping_events", "0"),
        (39, "revoked", "0"),
        (39, "integrity", "0"),
        (39, "atomic", "0"),
        (39, "rollbacks", "1"),
        (39, "retirement_failures", "1"),
        (39, "retirement_retry", "1"),
        (39, "pressure_checks", "0"),
        (39, "pressure_triggers", "0"),
        (39, "automatic_growths", "0"),
        (39, "pressure_cycles", "0"),
        (39, "soft_fallbacks", "0"),
        (39, "hard_rejections", "0"),
        (39, "growth_headroom_scrub", "0"),
        (39, "window_capacity", "31"),
        (39, "next_pages", "57"),
        (39, "pre_effect", "unverified"),
        (39, "concurrency", "1"),
        (39, "smp", "1"),
        (39, "authority", "1"),
        (39, "actions", "1"),
        (39, "production", "1"),
        (40, "stage", "pre_exit_boot_services"),
        (40, "class", "acpi"),
        (40, "sequence", "0"),
        (40, "source_records", str(observation["reclaim"]["source_records"] + 1)),
        (40, "ranges", str(observation["reclaim"]["ranges"] + 1)),
        (40, "pages", str(observation["reclaim"]["pages"] + 1)),
        (40, "dma_pages", str(observation["reclaim"]["dma_pages"] + 1)),
        (40, "dma32_pages", str(observation["reclaim"]["dma32_pages"] + 1)),
        (40, "normal_pages", "1"),
        (40, "pre_extents", str(observation["reclaim"]["pre_extents"] + 1)),
        (40, "post_extents", str(observation["reclaim"]["post_extents"] + 1)),
        (40, "scrub_bytes", str(observation["reclaim"]["scrub_bytes"] + 4096)),
        (40, "verified_bytes", str(observation["reclaim"]["verified_bytes"] + 4096)),
        (40, "range_checksum", "0x0000000000000000"),
        (40, "receipt_checksum", "0x0000000000000000"),
        (40, "idempotent", "0"),
        (40, "acpi_held_pages", str(observation["reclaim"]["acpi_held_pages"] + 1)),
        (40, "acpi_early_rejected", "0"),
        (40, "retained_excluded", "0"),
        (40, "atomic", "0"),
        (40, "rollback", "unverified"),
        (41, "allocations", "2"),
        (41, "frees", "1"),
        (41, "start", "0x0000000000001000"),
        (41, "first_generation", "0"),
        (41, "reuse_generation", "1"),
        (41, "allocation_receipts", "1"),
        (41, "release_receipts", "1"),
        (41, "scrub_pages", "12"),
        (41, "scrub_bytes", "49152"),
        (41, "verified_bytes", "49152"),
        (41, "stale_pattern", "0x0000000000000000"),
        (41, "stale_absent", "0"),
        (41, "double_free_rejected", "0"),
        (41, "quota_rejected", "0"),
        (41, "unavailable_rejected", "0"),
        (41, "metadata_poison", "0"),
        (41, "coalesces", "0"),
        (41, "rollback", "unverified"),
        (42, "managed_pages", str(observation["result"]["managed_pages"] + 1)),
        (42, "allocated_pages", "0"),
        (42, "physical_writes", "1"),
        (42, "physical_reads", "1"),
        (42, "temporary_pte_writes", "1"),
        (42, "bootstrap_invlpg", "1"),
        (42, "alias_revoked", "0"),
        (42, "metadata_retained", "0"),
        (42, "ledger_generation_retained", "0"),
        (42, "mappings", "complete_direct_map"),
        (42, "reclaim", "0"),
        (42, "acpi_reclaim", "1"),
        (42, "concurrency", "1"),
        (42, "smp", "1"),
        (42, "signatures", "1"),
        (42, "authority", "1"),
        (42, "actions", "1"),
        (42, "production", "1"),
        (42, "terminal", "return"),
    )
    marker_control_ids = physical_memory.NEGATIVE_CONTROL_IDS[3:-3]
    if len(mutations) != len(marker_control_ids):
        raise QualificationError("PKPMM6 hostile-control inventory and mutations disagree")
    for control_id, (marker_index, field, value) in zip(marker_control_ids, mutations):
        candidates.append((control_id, changed(marker_index, field, value)))
    controls = [
        _require_marker_rejection(control_id, candidate, transcript)
        for control_id, candidate in candidates
    ]

    overlap = copy.deepcopy(transcript)
    overlap["memory_entries"][1]["physical_start"] = overlap["memory_entries"][0]["physical_start"]
    controls.append(_require_pbp1_rejection(physical_memory.NEGATIVE_CONTROL_IDS[-3], observation, overlap))
    source_kind = copy.deepcopy(transcript)
    source_kind["memory_entries"][0]["source_type"] = 1
    controls.append(_require_pbp1_rejection(physical_memory.NEGATIVE_CONTROL_IDS[-2], observation, source_kind))
    ownership = copy.deepcopy(transcript)
    ownership["core"]["kernel_physical_base"] = ownership["memory_entries"][0]["physical_start"]
    controls.append(_require_pbp1_rejection(physical_memory.NEGATIVE_CONTROL_IDS[-1], observation, ownership))
    if [item["id"] for item in controls] != list(physical_memory.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKPMM6 hostile-control order changed")
    return controls


def _source_audit() -> dict[str, Any]:
    core_path = ROOT / "native/kernel/src/physical_memory.rs"
    adapter_path = ROOT / "native/kernel/src/main.rs"
    source = core_path.read_text(encoding="utf-8")
    adapter_source = adapter_path.read_text(encoding="utf-8")
    implementation = source.split("#[cfg(test)]", 1)[0]
    authorized = (
        ('#[unsafe(link_section = ".text.pkpmm_labels")]', 1),
        ("unsafe { core::str::from_utf8_unchecked(bytes) }", 1),
        ("unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) }", 1),
        ("unsafe { core::ptr::write(pointer.add(index), empty) }", 1),
        ("unsafe { core::ptr::copy_nonoverlapping(source.as_ptr(), pointer, source.len()) }", 1),
        ("unsafe { core::slice::from_raw_parts(pointer, capacity as usize) }", 1),
        ("unsafe { core::slice::from_raw_parts_mut(pointer, capacity as usize) }", 1),
        ("unsafe { core::ptr::write(pointer, self.ledger_header) }", 1),
        ("unsafe { core::ptr::read(pointer) }", 1),
        ("unsafe { core::ptr::copy_nonoverlapping(self as *const Self, mapped_pointer, 1) }", 1),
        ("unsafe { &mut *mapped_pointer }", 2),
        ("unsafe { core::ptr::write(header_pointer, header) }", 1),
    )
    audited = implementation
    for token, expected_count in authorized:
        if implementation.count(token) != expected_count:
            raise QualificationError(f"PKPMM6 authorized source token changed: {token}")
        audited = audited.replace(token, "")
    forbidden = tuple(
        token
        for token in (
            "unsafe",
            "from_raw_parts",
            "read_volatile",
            "write_volatile",
            "alloc::",
            "[Extent; MAX_RECLAIM_EXTENTS]",
        )
        if token in audited
    )
    required = (
        "[Extent; MAX_FREE_EXTENTS]",
        "[Allocation; MAX_ALLOCATIONS]",
        "[SourceRecord; MAX_MEMORY_ENTRIES]",
        "[Option<ScrubReceipt>; MAX_SCRUB_RECEIPTS]",
        "[Option<ReclaimReceipt>; MAX_RECLAIM_RECEIPTS]",
        "MEMORY_USABLE",
        "MEMORY_LOADER_RESERVED",
        "pub trait PhysicalPageAccess",
        "pub trait MetadataArenaAccess",
        "pub fn allocate_scrubbed",
        "pub fn free_scrubbed",
        "pub fn allocate_scrubbed_automatic",
        "pub fn free_scrubbed_automatic",
        "pub fn ensure_ledger_capacity",
        "struct LedgerDemand",
        "pub struct LedgerPressureOutcome",
        "LEDGER_GROWTH_ALLOCATION_HEADROOM",
        "LEDGER_GROWTH_SCRUB_HEADROOM",
        "fn scrub_range",
        "pub fn advance_reclaim_stage",
        "pub fn reclaim_held",
        "fn plan_reclaim",
        "struct ReclaimCursor",
        "fn next_reclaim_extent",
        "fn commit_preflighted_extent",
        "fn scrub_extent",
        "fn preflight_insert",
        "fn migrate_to_metadata",
        "pub fn grow_metadata_ledgers",
        "pub fn retry_metadata_retirement",
        "fn populate_ledger_generation",
        "fn ledger_checksum",
        "fn logical_checksum",
        "release_excluded",
        "SCRUB_WORDS_PER_PAGE",
    )
    missing = tuple(token for token in required if token not in implementation)
    if forbidden or missing:
        raise QualificationError(f"PKPMM6 source scope changed: forbidden={forbidden}; missing={missing}")
    adapter_required = (
        "impl PhysicalPageAccess for BootstrapTableMemory",
        "impl MetadataArenaAccess for BootstrapTableMemory",
        "self.ensure_mapped(physical_address)",
        "write_volatile(pointer, value)",
        "read_volatile(pointer)",
        "page_access\n                .finish()",
        "self.metadata_guards_absent()?",
        "self.ledger_guards_absent(slot)?",
        "metadata_retained=1",
        "ledger_generation_retained=1",
        "reclaim=1",
        "acpi_reclaim=0",
    )
    adapter_missing = tuple(token for token in adapter_required if token not in adapter_source)
    if adapter_missing:
        raise QualificationError(f"PKPMM6 live adapter scope changed: missing={adapter_missing}")
    adapter_implementation = adapter_source.split("struct BootstrapTableMemory", 1)[1].split(
        "struct LiveActiveHardware", 1
    )[0]
    return {
        "core_path": core_path.relative_to(ROOT).as_posix(),
        "core_sha256": physical_memory.sha256_bytes(source.encode("utf-8")),
        "adapter_path": adapter_path.relative_to(ROOT).as_posix(),
        "adapter_sha256": physical_memory.sha256_bytes(adapter_source.encode("utf-8")),
        "implementation_unauthorized_unsafe_token_count": 0,
        "authorized_utf8_and_mapped_read_unsafe_site_count": 3,
        "authorized_metadata_migration_unsafe_site_count": 4,
        "authorized_generation_storage_unsafe_site_count": 5,
        "live_adapter_volatile_read_site_count": adapter_implementation.count("read_volatile"),
        "live_adapter_volatile_write_site_count": adapter_implementation.count("write_volatile"),
        "final_temporary_alias_revocation_required": True,
        "final_guarded_metadata_mapping_retention_required": True,
        "heap_api_token_count": 0,
        "bootstrap_fixed_capacity_ledger_count": 5,
        "active_fixed_capacity_ledger_count": 0,
        "result": "pass_checked_pressure_triggered_repeated_growth_with_audited_live_page_adapter",
    }


def make_readiness(
    toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int
) -> dict[str, Any]:
    contract = physical_memory.read_json(ROOT / physical_memory.CONTRACT_RELATIVE)
    errors = physical_memory.contract_errors(contract, ROOT)
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
    with tempfile.TemporaryDirectory(prefix="pkpmm6-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        pmm_boot, pmm_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "pmm-boot",
            development_feature=physical_memory.FEATURE,
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if physical_memory.sha256_bytes(default_boot) == physical_memory.sha256_bytes(pmm_boot):
            raise QualificationError("default and PKPMM6 PooleBoot profiles are not distinct")
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(pmm_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(pmm_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKPMM6 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKPMM6 media kernel differs from PKENTRY1")
        media_path = temporary_root / "pkpmm6.img"
        media_path.write_bytes(media_one)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pkpmm6-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"physical-memory-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=physical_memory.validate_markers,
                        marker_extractor=physical_memory.extract_markers,
                        completion_marker=physical_memory.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    trace_path = run_directory / "qemu.trace.log"
                    tail = []
                    trace_tail = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(encoding="ascii", errors="ignore").splitlines()
                            if line.strip().startswith("POOLE")
                        ][-12:]
                    if trace_path.is_file():
                        trace_tail = trace_path.read_text(
                            encoding="ascii", errors="ignore"
                        ).splitlines()[-20:]
                    raise QualificationError(
                        f"{error}; debug_tail={tail!r}; trace_tail={trace_tail!r}"
                    ) from error
                prefix = run["marker_summary"]["transfer_prefix"]
                try:
                    native_kernel_load.validate_oracle_binding(
                        prefix["boot_prefix"], media_inspection, run["pbp1_transcript"]
                    )
                    run["transcript_binding"] = native_kernel_transfer.validate_transcript_binding(
                        prefix, run["pbp1_transcript"]
                    )
                    run["independent_kernel_revalidation"] = native_kernel_transfer.validate_revalidation_binding(
                        prefix, handoff, retained_files
                    )
                    run["independent_physical_memory"] = physical_memory.validate_observation_binding(
                        run["marker_summary"], run["pbp1_transcript"]
                    )
                except (
                    native_kernel_load.KernelLoadError,
                    native_kernel_transfer.KernelTransferError,
                    physical_memory.KernelPhysicalMemoryError,
                ) as error:
                    raise QualificationError(str(error)) from error
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKPMM6 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKPMM6 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKPMM6 runs produced different PBP1 bytes")

    controls = _negative_controls(runs[0]["markers"], runs[0]["pbp1_transcript"])
    observation = physical_memory.validate_markers(runs[0]["markers"])
    derived = physical_memory.validate_observation_binding(observation, runs[0]["pbp1_transcript"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_physical_memory_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_checked_automatic_repeated_ledger_growth_non_promoting",
        "contract_id": physical_memory.CONTRACT_ID,
        "selected_move_id": physical_memory.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n9_exit_gate_satisfied": False,
        "phase_status": {"N9": "partial", "N9.1": "partial", "N9.2": "partial"},
        "inputs": physical_memory.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "physical_memory_pooleboot": pmm_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "source_audit": source_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": physical_memory.sha256_bytes(media_one),
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
            "normalized_command_sha256": physical_memory.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": {
                key: observation[key]
                for key in (
                    "map", "zones", "ownership", "metadata", "growth", "reclaim", "scrub", "result"
                )
            },
            "independent_memory_summary": derived,
        },
        "negative_controls": controls,
        "claims": physical_memory.expected_claims(),
        "non_claims": contract["non_claims"],
        "summary": {
            "qemu_run_count": 2,
            "marker_count": physical_memory.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "memory_entry_count": derived["entry_count"],
            "source_usable_pages": derived["kind_pages"][1],
            "managed_pages": sum(derived["managed_pages"]) + derived["boot_reclaim"]["page_count"],
            "boot_reclaimable_pages_reclaimed": derived["boot_reclaim"]["page_count"],
            "boot_reclaim_source_records": observation["reclaim"]["source_records"],
            "boot_reclaim_ranges": observation["reclaim"]["ranges"],
            "boot_reclaim_pages_by_zone": [
                observation["reclaim"]["dma_pages"],
                observation["reclaim"]["dma32_pages"],
                observation["reclaim"]["normal_pages"],
            ],
            "boot_reclaim_receipts": 1,
            "boot_reclaim_idempotent": observation["reclaim"]["idempotent"] == 1,
            "acpi_reclaimable_pages_held": observation["reclaim"]["acpi_held_pages"],
            "acpi_early_reclaim_rejected": observation["reclaim"]["acpi_early_rejected"] == 1,
            "loader_reserved_pages_protected": derived["kind_pages"][10],
            "allocator_operations": observation["scrub"]["allocations"] + observation["scrub"]["frees"],
            "scrub_receipts": observation["growth"]["scrub_capacity"],
            "sample_scrub_receipts": observation["scrub"]["allocation_receipts"] + observation["scrub"]["release_receipts"],
            "metadata_scrub_receipts": 1,
            "scrub_page_count": observation["scrub"]["scrub_pages"],
            "scrubbed_bytes": observation["scrub"]["scrub_bytes"],
            "verified_bytes": observation["scrub"]["verified_bytes"],
            "physical_word_writes": observation["result"]["physical_writes"],
            "physical_word_reads": observation["result"]["physical_reads"],
            "bootstrap_temporary_pte_writes": observation["result"]["temporary_pte_writes"],
            "bootstrap_invalidations": observation["result"]["bootstrap_invlpg"],
            "final_temporary_alias_revoked": observation["result"]["alias_revoked"] == 1,
            "metadata_arena_pages": observation["metadata"]["pages"],
            "metadata_guard_pages": observation["metadata"]["guard_pages"],
            "metadata_manager_bytes": observation["metadata"]["manager_bytes"],
            "metadata_source_records": observation["metadata"]["source_records"],
            "metadata_free_extents": observation["metadata"]["free_extents"],
            "metadata_allocation_records_at_handoff": observation["metadata"]["allocation_records"],
            "metadata_receipt_records_at_handoff": observation["metadata"]["receipt_records"],
            "metadata_pte_writes": observation["metadata"]["pte_writes"],
            "metadata_mapping_retained": observation["result"]["metadata_retained"] == 1,
            "metadata_release_excluded": observation["metadata"]["release_excluded"] == 1,
            "metadata_integrity_verified": observation["metadata"]["integrity"] == 1,
            "ledger_generation_growth": {
                key: observation["growth"][key]
                for key in (
                    "initial_generation",
                    "final_generation",
                    "initial_pages",
                    "final_pages",
                    "free_capacity",
                    "allocation_capacity",
                    "source_capacity",
                    "scrub_capacity",
                    "reclaim_capacity",
                    "retired_generation",
                    "retired_pages",
                    "mapped_pages",
                    "pte_writes",
                    "guard_pages",
                    "mapping_events",
                    "revoked",
                    "integrity",
                    "atomic",
                    "rollbacks",
                    "retirement_failures",
                    "retirement_retry",
                    "pressure_checks",
                    "pressure_triggers",
                    "automatic_growths",
                    "pressure_cycles",
                    "soft_fallbacks",
                    "hard_rejections",
                    "growth_headroom_allocation",
                    "growth_headroom_scrub",
                    "window_capacity",
                    "next_pages",
                    "pre_effect",
                )
            },
            "complete_address_space_mapping_operations": 0,
            "reclaim_operations": 1,
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Integrate the positive ACPI reclaim transition only after N10 owns ACPI table parsing and explicit table-release evidence.",
            "Implement N9.3/N9.4 virtual layout, page-table ownership, map/unmap, TLB, PCID, guard, and huge-page contracts.",
            "Implement randomized, concurrent, interrupt-context, SMP, fragmentation, quota, and OOM allocator stress.",
            "Implement heap, object caches, kernel stacks, cacheability policy, target hardware, and second-host qualification.",
            "Replace the bounded retained-leaf growth windows with the later N9.3 generation-owned virtual mapping policy before production scale is claimed.",
        ],
    }
    errors = physical_memory.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-23")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 300:
        parser.error("--timeout must be between 5 and 300 seconds")
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
        physical_memory.KernelPhysicalMemoryError,
        native_tier0.Tier0Error,
    ) as error:
        print(f"PKPMM6 qualification failed: {error}", file=sys.stderr)
        return 1
    print(
        "PKPMM6 qualification passed: "
        f"runs={report['summary']['qemu_run_count']}; "
        f"markers={report['summary']['marker_count']}; "
        f"controls={report['summary']['negative_controls_passed']}; "
        f"managed_pages={report['summary']['managed_pages']}; production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
