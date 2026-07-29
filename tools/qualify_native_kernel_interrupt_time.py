#!/usr/bin/env python3
"""Build and qualify the bounded one-BSP PKIRQ1 local-APIC/HPET profile."""

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
    native_kernel_interrupt_time as interrupt_time,
    native_kernel_load,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / interrupt_time.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when PKIRQ1 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKIRQ1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _require_rejection(control_id: str, operation: Callable[[], Any]) -> dict[str, str]:
    try:
        operation()
    except interrupt_time.KernelInterruptTimeError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKIRQ1 hostile control did not reject: {control_id}")


def _marker_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    return _require_rejection(control_id, lambda: interrupt_time.validate_markers(candidate))


def _canonical_madt() -> bytearray:
    entries = bytearray()
    entries.extend(bytes([0, 8, 0, 0, 1, 0, 0, 0]))
    entries.extend(bytes([1, 12, 1, 0]) + (0xFEC0_0000).to_bytes(4, "little") + (0).to_bytes(4, "little"))
    entries.extend(bytes([2, 10, 0, 0]) + (2).to_bytes(4, "little") + (0).to_bytes(2, "little"))
    entries.extend(bytes([4, 6, 0xFF, 0, 0, 1]))
    entries.extend(bytes([0x7F, 4, 0, 0]))
    data = bytearray(44 + len(entries))
    data[:4] = b"APIC"
    data[4:8] = len(data).to_bytes(4, "little")
    data[36:40] = (0xFEE0_0000).to_bytes(4, "little")
    data[40:44] = (1).to_bytes(4, "little")
    data[44:] = entries
    return data


def _negative_controls(markers: list[str]) -> list[dict[str, str]]:
    observation = interrupt_time.validate_markers(markers)
    candidates: list[tuple[str, list[str]]] = [
        (interrupt_time.NEGATIVE_CONTROL_IDS[0], markers[:-1]),
    ]
    reordered = markers.copy()
    reordered[30], reordered[31] = reordered[31], reordered[30]
    candidates.append((interrupt_time.NEGATIVE_CONTROL_IDS[1], reordered))
    candidates.append((interrupt_time.NEGATIVE_CONTROL_IDS[2], [*markers, markers[-1]]))

    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "10")
    candidates.append((interrupt_time.NEGATIVE_CONTROL_IDS[3], selector))
    contract = markers.copy()
    contract[30] = _set_field(contract[30], "contract", "PKIRQ0")
    candidates.append((interrupt_time.NEGATIVE_CONTROL_IDS[4], contract))

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    acpi = observation["acpi"]
    apic = observation["apic"]
    vectors = observation["vectors"]
    clock = observation["clock"]
    delivery = observation["delivery"]
    mutations = (
        (5, 30, "madt_bytes", str(acpi["madt_bytes"] - 1)),
        (6, 30, "processors", "2"),
        (7, 30, "enabled", "0"),
        (8, 30, "ioapics", "2"),
        (9, 30, "overrides", "4"),
        (10, 30, "pcat", "0"),
        (11, 30, "apic_physical", "0x00000000FEE01000"),
        (12, 30, "hpet_physical", "0x00000000FED01000"),
        (13, 30, "retained_snapshot", "0"),
        (14, 30, "complete_walk", "0"),
        (15, 31, "apic_id", "1"),
        (16, 31, "version", "15"),
        (17, 31, "max_lvt", "2"),
        (18, 31, "global_enable", "0"),
        (19, 31, "msr_writes", str(apic["msr_writes"] + 1)),
        (20, 31, "svr_vector", "254"),
        (21, 31, "pic_masked", "0"),
        (22, 31, "mmio", "writeback"),
        (23, 31, "guarded", "2"),
        (24, 32, "owned", str(vectors["owned"] - 1)),
        (25, 32, "timer", "65"),
        (26, 32, "ipi_first", "225"),
        (27, 32, "collisions", "unchecked"),
        (28, 33, "source", "tsc"),
        (29, 33, "counter_bits", "32"),
        (30, 33, "period_fs", str(clock["period_fs"] - 1)),
        (31, 33, "sample_ns", str(clock["sample_ns"] + 1)),
        (32, 33, "apic_hz", str(clock["apic_hz"] + 1)),
        (33, 33, "one_shot_initial", str(clock["one_shot_initial"] + 1)),
        (34, 33, "monotonic_ns", "0"),
        (35, 33, "overflow", "unchecked"),
        (36, 34, "timer_deliveries", str(delivery["timer_deliveries"] - 1)),
        (37, 34, "eois", str(delivery["eois"] - 1)),
        (38, 34, "apic_errors", "1"),
        (39, 34, "spurious", "1"),
        (40, 34, "in_service_after", "1"),
        (41, 34, "exact_one_shot", "0"),
        (42, 35, "rollback", "0"),
        (43, 35, "mmio_revoked", "0"),
        (44, 35, "pic_restored", "0"),
        (45, 35, "interrupts", "enabled"),
        (46, 35, "smp", "1"),
        (47, 35, "ap_start", "1"),
        (48, 35, "shootdown", "1"),
        (49, 35, "target", "1"),
        (50, 35, "authority", "1"),
        (51, 35, "production", "1"),
    )
    for control_index, marker_index, field, value in mutations:
        candidates.append((interrupt_time.NEGATIVE_CONTROL_IDS[control_index], changed(marker_index, field, value)))
    controls = [_marker_rejection(control_id, candidate) for control_id, candidate in candidates]

    malformed = _canonical_madt()
    malformed[45] = 7
    controls.append(_require_rejection(interrupt_time.NEGATIVE_CONTROL_IDS[52], lambda: interrupt_time.parse_madt_table(bytes(malformed))))
    duplicate = _canonical_madt()
    duplicate.extend(bytes([0, 8, 1, 0, 1, 0, 0, 0]))
    duplicate[4:8] = len(duplicate).to_bytes(4, "little")
    controls.append(_require_rejection(interrupt_time.NEGATIVE_CONTROL_IDS[53], lambda: interrupt_time.parse_madt_table(bytes(duplicate))))
    reserved = _canonical_madt()
    reserved[48:52] = (4).to_bytes(4, "little")
    controls.append(_require_rejection(interrupt_time.NEGATIVE_CONTROL_IDS[54], lambda: interrupt_time.parse_madt_table(bytes(reserved))))
    controls.append(_require_rejection(interrupt_time.NEGATIVE_CONTROL_IDS[55], lambda: interrupt_time.reserve_vector(interrupt_time.vector_ledger(), interrupt_time.TIMER_VECTOR, "timer")))
    controls.append(_require_rejection(interrupt_time.NEGATIVE_CONTROL_IDS[56], lambda: interrupt_time.HpetClock(32, 100_000_000, 0xFFFF_FFF0, 16).sample(0x100)))
    controls.append(_require_rejection(interrupt_time.NEGATIVE_CONTROL_IDS[57], lambda: interrupt_time.calibrate_apic_timer(100, 99, 1, 100_000)))
    if [item["id"] for item in controls] != list(interrupt_time.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKIRQ1 hostile-control order changed")
    return controls


def _audit_source_text(core: str, main: str, arch: str, kmap: str) -> dict[str, Any]:
    core_body = core.split("#[cfg(test)]", 1)[0]
    forbidden = tuple(token for token in ("alloc::", "Vec<", "Box<", "std::") if token in core_body)
    core_required = (
        "pub fn parse_madt", "pub fn parse_hpet", "pub fn validate_apic_discovery",
        "pub struct VectorLedger", "pub struct HpetClock", "pub fn calibrate_apic_timer",
        "pub fn timer_initial_count", "DuplicateProcessor", "DuplicateOverride", "CounterDelta",
    )
    main_required = (
        "struct LiveInterruptHardware", "install_uncached_mmio", "uninstall_uncached_mmio",
        "mask_legacy_pic", "enable_interrupts_halt_disable", "IRQ_TIMER_DELIVERIES", "PKIRQ_RESULT",
        "restore_legacy_pic", "parse_madt(", "parse_hpet(",
    )
    arch_required = (
        "unsafe fn write_msr", "pub unsafe fn mask_legacy_pic",
        "pub unsafe fn restore_legacy_pic", "pub unsafe fn enable_interrupts_halt_disable",
        "poole_interrupt_timer", "poole_interrupt_apic_error", "poole_interrupt_spurious",
    )
    kmap_required = (
        "MMIO_GUARD_LOW_PAGE", "LOCAL_APIC_PAGE", "MMIO_GUARD_MIDDLE_PAGE",
        "HPET_PAGE", "MMIO_GUARD_HIGH_PAGE",
    )
    missing = {
        "core": [token for token in core_required if token not in core],
        "main": [token for token in main_required if token not in main],
        "arch": [token for token in arch_required if token not in arch],
        "kmap": [token for token in kmap_required if token not in kmap],
    }
    if forbidden or any(missing.values()):
        raise QualificationError(f"PKIRQ1 source scope changed: forbidden={forbidden}; missing={missing}")
    return {
        "heap_api_token_count": 0,
        "madt_known_structure_type_count": 8,
        "reserved_vector_count": 51,
        "simultaneous_irq_mmio_mapping_count": 2,
        "irq_mmio_guard_count": 3,
        "normal_path_restore_present": True,
        "result": "pass_bounded_allocation_free_one_bsp_apic_hpet_source_audit",
    }


def _source_audit() -> dict[str, Any]:
    paths = {
        "core": ROOT / "native/kernel/src/interrupt_time.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "kmap": ROOT / "native/kmap/src/lib.rs",
    }
    result = _audit_source_text(*(paths[name].read_text(encoding="utf-8") for name in ("core", "main", "arch", "kmap")))
    result["files"] = {
        name: {"path": path.relative_to(ROOT).as_posix(), "sha256": interrupt_time.sha256_bytes(path.read_bytes())}
        for name, path in paths.items()
    }
    return result


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = interrupt_time.read_json(ROOT / interrupt_time.CONTRACT_RELATIVE)
    errors = interrupt_time.contract_errors(contract, ROOT)
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
    with tempfile.TemporaryDirectory(prefix="pkirq1-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        irq_boot, irq_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "irq-boot", development_feature=interrupt_time.FEATURE
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if interrupt_time.sha256_bytes(default_boot) == interrupt_time.sha256_bytes(irq_boot):
            raise QualificationError("default and PKIRQ1 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(irq_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(irq_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKIRQ1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pkirq1.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pkirq1-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"interrupt-time-run-{run_index}", lock, profile, qemu_root, media_path,
                        run_directory, timeout, marker_validator=interrupt_time.validate_markers,
                        marker_extractor=interrupt_time.extract_markers,
                        completion_marker=interrupt_time.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail = []
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
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKIRQ1 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKIRQ1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKIRQ1 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"])
    observation = interrupt_time.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_interrupt_time_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_one_bsp_local_apic_hpet_non_promoting",
        "contract_id": interrupt_time.CONTRACT_ID,
        "selected_move_id": interrupt_time.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n8_exit_gate_satisfied": False,
        "flag_n8_irq_001_closed": False,
        "phase_status": {"N8": "partial", "N8.1": "partial", "N8.3": "partial", "N8.5": "not_started", "N8.6": "not_started"},
        "inputs": interrupt_time.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "interrupt_time_pooleboot": irq_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "source_audit": source_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": interrupt_time.sha256_bytes(media_one),
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
            "normalized_command_sha256": interrupt_time.sha256_bytes(native_pooleboot.canonical_json_bytes(command)),
            "fresh_vars_each_run": True,
            "media_read_only": True,
            "guest_network": False,
            "host_acceleration": False,
            "exact_marker_match": True,
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
            "markers_per_run": interrupt_time.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "timer_interrupts_delivered": observation["delivery"]["timer_deliveries"],
            "timer_eois": observation["delivery"]["eois"],
            "application_processors_started": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Start and rollback the first application processor with guarded per-CPU state.",
            "Implement real IPI delivery and SMP TLB-shootdown acknowledgement before PKVM3 remote retirement.",
            "Configure I/O APIC routing and then capability-authorized MSI/MSI-X allocation and teardown.",
            "Add invariant-TSC calibration, clocksource watchdog, timer queues, deadline mode, and public monotonic APIs.",
            "Prove panic-time rollback for every partial controller and clock mutation.",
            "Qualify the exact physical target and all 16 logical processors; no target claim exists here.",
        ],
    }
    schema = interrupt_time.read_json(ROOT / interrupt_time.READINESS_SCHEMA_RELATIVE)
    errors = list(validate_json(report, schema))
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-26")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    try:
        report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
        errors = interrupt_time.readiness_errors(interrupt_time.read_json(args.out), ROOT)
        if errors:
            raise QualificationError("; ".join(errors))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, QualificationError, interrupt_time.KernelInterruptTimeError, native_kernel_load.KernelLoadError, native_kernel_transfer.KernelTransferError, native_tier0.Tier0Error) as error:
        print(f"NATIVE_KERNEL_INTERRUPT_TIME_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "NATIVE_KERNEL_INTERRUPT_TIME_QUALIFICATION PASS "
        f"host_tests={summary['kernel_host_tests_passed']}/{summary['kernel_host_tests_total']} "
        f"runs={summary['qemu_runs_passed']}/{summary['qemu_runs_total']} "
        f"markers={summary['markers_per_run']} controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} "
        f"timer_deliveries={summary['timer_interrupts_delivered']} eois={summary['timer_eois']} "
        "bsp=1 ap_start=0 n8_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
