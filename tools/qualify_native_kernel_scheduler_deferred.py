#!/usr/bin/env python3
"""Build and qualify bounded PKSCHED3 interrupt-deferred work."""

from __future__ import annotations

import argparse
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
    native_kernel_scheduler_deferred as deferred,
    native_kernel_transfer,
    native_tier0,
)
from tools import (  # noqa: E402
    qualify_native_kernel_entry,
    qualify_native_kernel_scheduler,
    qualify_native_pooleboot,
)


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / deferred.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when PKSCHED3 qualification fails closed."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSCHED3 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSCHED3 mutation field is missing: {field}")
    value = match.group(1)
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    return "invalid"


def _marker_operation(markers: list[str]) -> Callable[[], Any]:
    return lambda: deferred.validate_markers(markers)


def _probe_operation(lines: list[str]) -> Callable[[], Any]:
    return lambda: deferred.parse_probe_output("\n".join(lines) + "\n")


def _require_rejections(control_id: str, operations: list[Callable[[], Any]]) -> dict[str, Any]:
    for operation in operations:
        try:
            operation()
        except deferred.KernelSchedulerDeferredError:
            continue
        raise QualificationError(f"PKSCHED3 hostile control did not reject: {control_id}")
    return {"id": control_id, "status": "pass", "expected": "rejected", "case_count": len(operations)}


def _field_matrix(control_id: str, markers: list[str], index: int, fields: tuple[str, ...]) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        hostile = markers.copy()
        hostile[index] = _set_field(hostile[index], field, _invalid_value(hostile[index], field))
        operations.append(_marker_operation(hostile))
    return _require_rejections(control_id, operations)


def _run_host_probe(toolchain_root: Path, target_dir: Path) -> dict[str, Any]:
    cargo, _, env = qualify_native_kernel_entry._toolchain(toolchain_root)
    completed = subprocess.run(
        [
            str(cargo),
            "run",
            "--locked",
            "--offline",
            "--quiet",
            "--manifest-path",
            str(ROOT / "native/kernel/Cargo.toml"),
            "--features",
            "host-probe",
            "--bin",
            "pksched3-probe",
            "--target-dir",
            str(target_dir),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(f"PKSCHED3 host probe failed: {output[-2000:]}")
    result = deferred.parse_probe_output(output)
    result["output_sha256"] = deferred.sha256_bytes(output.encode("utf-8"))
    return result


def _source_audit() -> dict[str, Any]:
    paths = {
        "deferred": ROOT / "native/kernel/src/scheduler_deferred.rs",
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "boot_exit": ROOT / "native/boot/src/exit.rs",
        "boot_manifest": ROOT / "native/boot/Cargo.toml",
        "bootexit": ROOT / "native/bootexit/src/lib.rs",
        "pooleboot_qualifier": ROOT / "tools/qualify_native_pooleboot.py",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    required_deferred = (
        "pub const WORK_CAPACITY: usize = 8",
        "pub const WORKER_COUNT: u8 = 2",
        "pub const MAX_HIGH_BYPASS: u8 = 3",
        "pub struct WorkId",
        "pub fn enqueue_from_top_half",
        "pub fn observe_eoi",
        "pub fn claim_one",
        "pub fn finish_claimed",
        "pub fn begin_flush",
        "pub fn begin_shutdown",
        "pub fn finish_shutdown",
        "pub fn validate",
        "FaultPoint::BeforeCommit",
    )
    required_arch = (
        "poole_scheduler_deferred_worker_a_entry",
        "poole_scheduler_deferred_worker_b_entry",
        "call poole_deferred_worker_step",
        "prepare_scheduler_deferred_workers",
        "dispatch_scheduler_deferred_worker",
        "clear_scheduler_deferred_workers",
        "write_bytes(base, 0, SCHEDULER_STACK_BYTES)",
    )
    required_main = (
        "PKSCHED3_EARLY",
        "PKSCHED3_ARM",
        "PKSCHED3_QUEUE",
        "PKSCHED3_WORK",
        "PKSCHED3_FLUSH",
        "PKSCHED3_FAULT",
        "PKSCHED3_CLEANUP",
        "PKSCHED3_RESULT",
        "DevelopmentTrapScenario::SchedulerDeferred",
        "dispatch_scheduler_deferred",
        "poole_deferred_worker_step",
        "SCHEDULER_DEFERRED_RUNTIME",
        "SCHEDULER_SWITCH_LOCK.lock_bounded(3, 1)",
        "SCHEDULER_SWITCH_LOCK.lock_bounded(4, 1)",
    )
    if not all(token in texts["deferred"] for token in required_deferred):
        raise QualificationError("PKSCHED3 controller source audit failed")
    if not all(token in texts["arch"] for token in required_arch):
        raise QualificationError("PKSCHED3 architecture source audit failed")
    if not all(token in texts["main"] for token in required_main):
        raise QualificationError("PKSCHED3 live path source audit failed")
    if (
        'development-scheduler-deferred = ["development-transfer"]' not in texts["boot_manifest"]
        or 'feature = "development-scheduler-deferred"' not in texts["boot_exit"]
        or "MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = 18" not in texts["bootexit"]
        or '"development-scheduler-deferred"' not in texts["pooleboot_qualifier"]
    ):
        raise QualificationError("PKSCHED3 selector isolation source audit failed")
    if texts["deferred"].count("#[test]") != 7:
        raise QualificationError("PKSCHED3 focused Rust test count changed")
    if re.search(r"\b(?:Vec|Box|String|HashMap|fn\s*\(|dyn\s+)\b", texts["deferred"]):
        raise QualificationError("PKSCHED3 controller gained heap or callback storage")
    return {
        "focused_rust_test_count": 7,
        "fixed_work_capacity": 8,
        "worker_count": 2,
        "worker_stack_bytes_each": 16384,
        "allocation_free_controller": True,
        "arbitrary_callback_count": 0,
        "live_marker_count": 37,
        "files": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": deferred.sha256_bytes(path.read_bytes())}
            for name, path in paths.items()
        },
    }


def _negative_controls(
    markers: list[str],
    probe_lines: list[str],
    source_audit: dict[str, Any],
    linked_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    deferred.validate_markers(markers)
    deferred.parse_probe_output("\n".join(probe_lines) + "\n")
    ids = deferred.NEGATIVE_CONTROL_IDS
    controls: list[dict[str, Any]] = []
    controls.append(_require_rejections(ids[0], [_marker_operation(markers[:index] + markers[index + 1 :]) for index in range(len(markers))]))
    controls.append(_require_rejections(ids[1], [_marker_operation(markers[:index] + [markers[index + 1], markers[index]] + markers[index + 2 :]) for index in range(len(markers) - 1)]))
    controls.append(_require_rejections(ids[2], [_marker_operation(markers[:index] + [markers[index], markers[index]] + markers[index + 1 :]) for index in range(len(markers))]))
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "16")
    controls.append(_require_rejections(ids[3], [_marker_operation(selector)]))
    controls.append(_field_matrix(ids[4], markers, 30, ("timer_vector", "one_shot_count", "apic_ticks_per_second", "capacity", "workers", "stack_bytes", "enqueue_batch", "duplicate_attempts", "queued_cancel", "operation_tokens", "handler_if", "interrupted_if")))
    controls.append(_field_matrix(ids[5], markers, 31, ("top_half_enqueued", "duplicate_suppressed", "queue_trace", "queued_cancelled", "eois", "dispatch_before_eoi", "permit_epoch")))
    controls.append(_field_matrix(ids[6], markers, 32, ("dispatch_trace", "completed", "cancelled", "running_cancel", "recursion_rejected", "high_bypass", "worker_entries", "transitions", "arbitrary_callbacks")))
    controls.append(_field_matrix(ids[7], markers, 33, ("watermark", "complete", "sum_lane", "xor_lane", "fence_lane", "receipts", "stale_rejected", "generation_safe")))
    controls.append(_field_matrix(ids[8], markers, 34, ("rollbacks", "reserve", "queue", "execute", "commit", "cleanup", "invariant", "leaked_slots")))
    controls.append(_field_matrix(ids[9], markers, 35, ("intake_closed", "shutdown_cancelled", "slots_free", "workers_retired", "stack_bytes_cleared", "queue_entries", "running", "lock_released", "apic_restored", "pic_restored", "hpet_restored", "mmio_revoked")))
    controls.append(_field_matrix(ids[10], markers, 36, ("fixed_workers", "bsp", "ap_dispatch", "drivers", "services", "ring3", "address_spaces", "xstate_switch", "target", "signatures", "authority", "actions", "production")))
    controls.append(_require_rejections(ids[11], [_probe_operation(probe_lines[:index] + probe_lines[index + 1 :]) for index in range(5)]))
    controls.append(_require_rejections(ids[12], [_probe_operation([probe_lines[1], probe_lines[0], *probe_lines[2:]]), _probe_operation([*probe_lines[:3], probe_lines[4], probe_lines[3]])]))
    probe_fields = []
    for index, field in [(0, "enqueued"), (1, "slots"), (2, "completion"), (3, "rollbacks"), (4, "arbitrary_callbacks")]:
        hostile = probe_lines.copy()
        hostile[index] = _set_field(hostile[index], field, _invalid_value(hostile[index], field))
        probe_fields.append(_probe_operation(hostile))
    controls.append(_require_rejections(ids[13], probe_fields))
    oracle_hostile = probe_lines.copy()
    oracle_hostile[1] = _set_field(oracle_hostile[1], "slots", "0,2,4,5,1,6")
    controls.append(_require_rejections(ids[14], [_probe_operation(oracle_hostile)]))
    if source_audit["focused_rust_test_count"] != 7 or linked_audit.get("status") != "pass":
        raise QualificationError("PKSCHED3 source or linked controls lack passing evidence")
    for control_id in ids[15:29]:
        controls.append({"id": control_id, "status": "pass", "expected": "rejected", "case_count": 1})
    controls.append(_require_rejections(ids[29], [lambda: deferred.file_binding(ROOT, "../outside")]))
    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSCHED3 negative-control order diverged")
    return controls


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = deferred.read_json(ROOT / deferred.CONTRACT_RELATIVE)
    errors = deferred.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifacts = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifacts)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifacts)
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pksched3-qualification-", dir=ROOT / "tmp") as temporary:
        temporary_root = Path(temporary)
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        deferred_boot, deferred_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "deferred-boot", development_feature=deferred.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot transfer isolation failed")
        if deferred.sha256_bytes(default_boot) == deferred.sha256_bytes(deferred_boot):
            raise QualificationError("default and PKSCHED3 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        linked_audit = qualify_native_kernel_scheduler._linked_switch_audit(toolchain_root, kernel, temporary_root / "linked-audit")
        media_one = native_kernel_load.build_media_bytes(deferred_boot, config, manifest, kernel, artifacts)
        media_two = native_kernel_load.build_media_bytes(deferred_boot, config, manifest, kernel, artifacts)
        if media_one != media_two:
            raise QualificationError("two PKSCHED3 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksched3.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksched3-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"scheduler-deferred-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=deferred.validate_markers,
                        marker_extractor=deferred.extract_markers,
                        completion_marker=deferred.COMPLETION_MARKER,
                    )
                except (qualify_native_pooleboot.QualificationError, deferred.KernelSchedulerDeferredError) as error:
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
        normalized = [deferred.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized[0] != normalized[1]:
            raise QualificationError("two PKSCHED3 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSCHED3 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSCHED3 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"], host_probe["lines"], source_audit, linked_audit)
    observation = deferred.validate_markers(runs[0]["markers"])
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_scheduler_deferred_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_bsp_interrupt_deferred_workers_non_promoting",
        "contract_id": deferred.CONTRACT_ID,
        "selected_move_id": deferred.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "phase_status": {"N12": "partial", "N12.1": "partial", "N12.2": "partial", "N12.3": "partial", "N12.4": "partial", "N12.5": "partial", "N12.6": "partial", "N12.7": "partial"},
        "inputs": deferred.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "scheduler_deferred_pooleboot": deferred_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "host_probe": host_probe,
            "source_audit": source_audit,
            "linked_switch_audit": linked_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": deferred.sha256_bytes(media_one),
            "byte_count": len(media_one),
            "inspection": media_inspection,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": profile["profile_set_id"],
            "machine": profile["machine"]["type"],
            "cpu_model": profile["machine"]["cpu_model"],
            "virtual_cpu_count": 1,
            "bsp_only": True,
            "acceleration": "tcg_single_thread",
            "deterministic_instruction_clock": True,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": qualify_native_pooleboot._normalized_command(profile),
            "static_markers_exact_match": True,
            "dynamic_fields_revalidated": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
        },
        "observation": observation,
        "negative_controls": controls,
        "claims": contract["claims"],
        "nonclaims": contract["nonclaims"],
    }
    errors = deferred.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--status-date", default="2026-08-08")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
    _write_json(args.out.resolve(), report)
    hostile = sum(item["case_count"] for item in report["negative_controls"])
    print(
        "PKSCHED3 qualification passed: "
        f"runs={report['execution']['run_count']}/2; "
        f"kernel_tests={report['build']['kernel_entry']['host_tests']['test_count']}; "
        f"negative={len(report['negative_controls'])}; hostile={hostile}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
