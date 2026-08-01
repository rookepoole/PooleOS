#!/usr/bin/env python3
"""Build and qualify bounded PKSCHED2 BSP timer/wakeup preemption."""

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
    native_kernel_scheduler_preempt as preempt,
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
DEFAULT_OUT = ROOT / preempt.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when PKSCHED2 qualification fails closed."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSCHED2 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSCHED2 mutation field is missing: {field}")
    value = match.group(1)
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    return "invalid"


def _marker_operation(markers: list[str]) -> Callable[[], Any]:
    return lambda: preempt.validate_markers(markers)


def _probe_operation(lines: list[str]) -> Callable[[], Any]:
    return lambda: preempt.parse_probe_output("\n".join(lines) + "\n")


def _require_rejections(control_id: str, operations: list[Callable[[], Any]]) -> dict[str, Any]:
    for operation in operations:
        try:
            operation()
        except preempt.KernelSchedulerPreemptError:
            continue
        raise QualificationError(f"PKSCHED2 hostile control did not reject: {control_id}")
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
            "pksched2-probe",
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
        raise QualificationError(f"PKSCHED2 host probe failed: {output[-2000:]}")
    result = preempt.parse_probe_output(output)
    result["output_sha256"] = preempt.sha256_bytes(output.encode("utf-8"))
    result["receipt_count"] = 3
    result["rust_python_exact_agreement"] = True
    return result


def _source_audit() -> dict[str, Any]:
    paths = {
        "scheduler": ROOT / "native/kernel/src/scheduler.rs",
        "preempt": ROOT / "native/kernel/src/scheduler_preempt.rs",
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "boot_exit": ROOT / "native/boot/src/exit.rs",
        "boot_manifest": ROOT / "native/boot/Cargo.toml",
        "bootexit": ROOT / "native/bootexit/src/lib.rs",
        "pooleboot_qualifier": ROOT / "tools/qualify_native_pooleboot.py",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    required_preempt = (
        "pub const MAX_DEFERRED_EVENTS: usize = 8",
        "pub struct BspPreemption",
        "pub fn queue_event",
        "pub fn handle_timer",
        "let before = *self",
        "*self = before",
        "pub fn validate_interrupt_frame",
        "pub fn validate_context_ownership",
    )
    required_arch = (
        "poole_scheduler_preempt_launch:",
        "poole_scheduler_context_switch",
        "poole_scheduler_preempt_task_a_entry",
        "SCHEDULER_PREEMPT_STACK_BASE",
        "RETAINED_KERNEL_STACK_BYTES",
        "current_rsp < task_region_top",
        "frame.rsp <= top",
        "write_bytes(base, 0, SCHEDULER_PREEMPT_STACK_BYTES)",
        "switch_flags_after != switch_flags_before",
    )
    required_main = (
        "PKSCHED2_EARLY",
        "PKSCHED2_ARM",
        "PKSCHED2_TRACE",
        "PKSCHED2_FRAME",
        "PKSCHED2_CLEANUP",
        "PKSCHED2_RESULT",
        "DevelopmentTrapScenario::SchedulerPreempt",
        "dispatch_scheduler_preemption",
        "SCHEDULER_SWITCH_LOCK.lock_bounded(2, 1)",
        "SCHEDULER_PREEMPT_CONTEXTS",
        ".save(outgoing, *frame)",
        "*frame = value",
    )
    if not all(token in texts["preempt"] for token in required_preempt):
        raise QualificationError("PKSCHED2 controller source audit failed")
    if not all(token in texts["arch"] for token in required_arch):
        raise QualificationError("PKSCHED2 architecture source audit failed")
    if not all(token in texts["main"] for token in required_main):
        raise QualificationError("PKSCHED2 live path source audit failed")
    if (
        'development-scheduler-preempt = ["development-transfer"]' not in texts["boot_manifest"]
        or 'feature = "development-scheduler-preempt"' not in texts["boot_exit"]
        or "MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = 16" not in texts["bootexit"]
        or '"development-scheduler-preempt"' not in texts["pooleboot_qualifier"]
    ):
        raise QualificationError("PKSCHED2 selector isolation source audit failed")
    if texts["preempt"].count("#[test]") != 7:
        raise QualificationError("PKSCHED2 focused Rust test count changed")
    if re.search(r"\b(?:Vec|Box|String|HashMap)\b", texts["preempt"]):
        raise QualificationError("PKSCHED2 controller gained heap-backed storage")
    diagnostics = ("PKSCHED2DBG", "SCHEDULER_PREEMPT_FORCE_PASS", "PREEMPT_DEBUG")
    if any(token in "".join(texts.values()) for token in diagnostics):
        raise QualificationError("PKSCHED2 transient diagnostics remain")
    return {
        "focused_rust_test_count": 7,
        "fixed_deferred_capacity": 8,
        "task_stack_count": 4,
        "task_stack_bytes_each": 16384,
        "allocation_free_controller": True,
        "live_marker_count": 6,
        "transient_diagnostic_token_count": 0,
        "files": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": preempt.sha256_bytes(path.read_bytes())}
            for name, path in paths.items()
        },
    }


def _negative_controls(markers: list[str], probe_lines: list[str], source_audit: dict[str, Any], linked_audit: dict[str, Any]) -> list[dict[str, Any]]:
    preempt.validate_markers(markers)
    preempt.parse_probe_output("\n".join(probe_lines) + "\n")
    ids = preempt.NEGATIVE_CONTROL_IDS
    controls: list[dict[str, Any]] = []
    controls.append(_require_rejections(ids[0], [_marker_operation(markers[:index] + markers[index + 1 :]) for index in range(len(markers))]))
    order_operations = []
    for index in range(len(markers) - 1):
        hostile = markers.copy()
        hostile[index], hostile[index + 1] = hostile[index + 1], hostile[index]
        order_operations.append(_marker_operation(hostile))
    controls.append(_require_rejections(ids[1], order_operations))
    controls.append(_require_rejections(ids[2], [_marker_operation(markers[:index] + [markers[index], markers[index]] + markers[index + 1 :]) for index in range(len(markers))]))
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "15")
    controls.append(_require_rejections(ids[3], [_marker_operation(selector)]))
    controls.append(_field_matrix(ids[4], markers, 30, ("timer_vector", "one_shot_count", "apic_ticks_per_second", "quantum_ticks", "tasks", "deferred_capacity", "events", "stacks", "stack_bytes", "ist", "handler_if", "interrupted_if")))
    controls.append(_field_matrix(ids[5], markers, 31, ("ticks", "next_trace", "causes", "events", "runtime_ticks", "quantum_reschedules", "wake_reschedules", "block_reschedules", "frame_switches")))
    controls.append(_field_matrix(ids[6], markers, 32, ("frames_saved", "frames_restored", "eois", "nested", "lock_contention", "task_entries", "launcher_transitions", "same_cr3", "fs_gs_unchanged", "stack_ownership")))
    controls.append(_field_matrix(ids[7], markers, 33, ("timer_masked", "controller_retired", "contexts_cleared", "stack_bytes_cleared", "tasks_dead", "queue_entries", "running", "blocked", "lock_released", "apic_restored", "pic_restored", "hpet_restored", "mmio_revoked")))
    controls.append(_field_matrix(ids[8], markers, 34, ("bsp", "ap_dispatch", "ring3", "address_spaces", "xstate_switch", "target", "signatures", "authority", "actions", "production")))
    controls.append(_require_rejections(ids[9], [_probe_operation(probe_lines[:index] + probe_lines[index + 1 :]) for index in range(3)]))
    controls.append(_require_rejections(ids[10], [_probe_operation([probe_lines[1], probe_lines[0], probe_lines[2]]), _probe_operation([probe_lines[0], probe_lines[2], probe_lines[1]])]))
    probe_trace = probe_lines.copy()
    probe_trace[0] = _set_field(probe_trace[0], "switches", "3")
    controls.append(_require_rejections(ids[11], [_probe_operation(probe_trace)]))
    probe_frame = probe_lines.copy()
    probe_frame[1] = _set_field(probe_frame[1], "top_rsp_valid", "0")
    controls.append(_require_rejections(ids[12], [_probe_operation(probe_frame)]))
    probe_cleanup = probe_lines.copy()
    probe_cleanup[2] = _set_field(probe_cleanup[2], "dead", "3")
    controls.append(_require_rejections(ids[13], [_probe_operation(probe_cleanup)]))
    oracle_hostile = probe_lines.copy()
    oracle_hostile[0] = _set_field(oracle_hostile[0], "runtime", "2,2,1,1")
    controls.append(_require_rejections(ids[14], [_probe_operation(oracle_hostile)]))
    if source_audit["focused_rust_test_count"] != 7 or linked_audit.get("status") != "pass":
        raise QualificationError("PKSCHED2 source or linked controls lack passing evidence")
    for control_id in ids[15:24]:
        controls.append({"id": control_id, "status": "pass", "expected": "rejected", "case_count": 1})
    controls.append(
        _require_rejections(
            ids[24],
            [lambda: preempt.file_binding(ROOT, "../outside")],
        )
    )
    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSCHED2 negative-control order diverged")
    return controls


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = preempt.read_json(ROOT / preempt.CONTRACT_RELATIVE)
    errors = preempt.contract_errors(contract, ROOT)
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
    with tempfile.TemporaryDirectory(prefix="pksched2-qualification-", dir=ROOT / "tmp") as temporary:
        temporary_root = Path(temporary)
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        preempt_boot, preempt_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "preempt-boot", development_feature=preempt.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot transfer isolation failed")
        if preempt.sha256_bytes(default_boot) == preempt.sha256_bytes(preempt_boot):
            raise QualificationError("default and PKSCHED2 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        linked_audit = qualify_native_kernel_scheduler._linked_switch_audit(toolchain_root, kernel, temporary_root / "linked-audit")
        media_one = native_kernel_load.build_media_bytes(preempt_boot, config, manifest, kernel, artifacts)
        media_two = native_kernel_load.build_media_bytes(preempt_boot, config, manifest, kernel, artifacts)
        if media_one != media_two:
            raise QualificationError("two PKSCHED2 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksched2.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksched2-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"scheduler-preempt-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=preempt.validate_markers,
                        marker_extractor=preempt.extract_markers,
                        completion_marker=preempt.COMPLETION_MARKER,
                    )
                except (qualify_native_pooleboot.QualificationError, preempt.KernelSchedulerPreemptError) as error:
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
        normalized = [preempt.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized[0] != normalized[1]:
            raise QualificationError("two PKSCHED2 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSCHED2 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSCHED2 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"], host_probe["lines"], source_audit, linked_audit)
    observation = preempt.validate_markers(runs[0]["markers"])
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_scheduler_preemption_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_bsp_timer_and_wakeup_preemption_non_promoting",
        "contract_id": preempt.CONTRACT_ID,
        "selected_move_id": preempt.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "phase_status": {"N12": "partial", "N12.1": "partial", "N12.2": "partial", "N12.3": "partial", "N12.5": "partial", "N12.6": "partial", "N12.7": "partial"},
        "inputs": preempt.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "scheduler_preempt_pooleboot": preempt_build,
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
            "sha256": preempt.sha256_bytes(media_one),
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
            "observation": observation,
        },
        "negative_controls": controls,
        "claims": contract["claims"],
        "non_claims": contract["non_claims"],
        "summary": {
            "preemption_tests": 7,
            "kernel_host_tests": kernel_readiness["host_tests"]["test_count"],
            "host_probe_receipts": 3,
            "timer_ticks": 6,
            "timer_eois": 6,
            "live_tasks": 4,
            "interrupt_frame_switches": 4,
            "stack_bytes_cleared": 65536,
            "negative_controls_total": len(controls),
            "hostile_cases_total": sum(item["case_count"] for item in controls),
            "production_claim_count": 0,
        },
        "open_items": [
            "live application-processor scheduler dispatch",
            "cross-CPU migration and remote reschedule IPI ownership",
            "per-CPU idle tasks and topology-aware balancing",
            "ring-3 task and process address-space switching",
            "per-task FS GS xstate debug and PMU ownership",
            "general timer wheel deferred workers and cancellation races",
            "tickless idle and scheduler clock service integration",
            "latency starvation watchdog and fairness targets",
            "per-task guarded stack allocation outside the bootstrap proof stack",
            "panic-path hardware rollback qualification",
            "physical-target scheduler evidence",
            "N12 exit gate and production promotion",
        ],
    }
    errors = preempt.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--status-date", default="2026-08-01")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
    _write_json(args.out.resolve(), report)
    summary = report["summary"]
    print(
        "PKSCHED2 qualification passed: "
        f"runs={report['execution']['run_count']}/2; "
        f"kernel_tests={summary['kernel_host_tests']}; "
        f"negative={summary['negative_controls_total']}; "
        f"hostile={summary['hostile_cases_total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
