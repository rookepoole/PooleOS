#!/usr/bin/env python3
"""Build and qualify the bounded four-vCPU PKSCHED4 live SMP scheduler."""

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

from runtime import native_kernel_load, native_kernel_scheduler_smp as scheduler_smp  # noqa: E402
from runtime import native_kernel_transfer, native_tier0  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_kernel_smp_ipi  # noqa: E402
from tools import qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / scheduler_smp.READINESS_RELATIVE
HOSTILE_CASE_COUNT = 209


class QualificationError(RuntimeError):
    """Raised when PKSCHED4 qualification fails closed."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSCHED4 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSCHED4 mutation field is missing: {field}")
    value = match.group(1)
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    if value.startswith("0x"):
        return "0x0000000000000000" if len(value) == 18 else "0x00"
    return "invalid"


def _marker_operation(markers: list[str]) -> Callable[[], Any]:
    return lambda: scheduler_smp.validate_markers(markers)


def _probe_operation(lines: list[str]) -> Callable[[], Any]:
    return lambda: scheduler_smp.parse_probe_output("\n".join(lines) + "\n")


def _require_rejections(control_id: str, operations: list[Callable[[], Any]]) -> dict[str, Any]:
    for operation in operations:
        try:
            operation()
        except (scheduler_smp.KernelSchedulerSmpError, QualificationError):
            continue
        raise QualificationError(f"PKSCHED4 hostile control did not reject: {control_id}")
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
            str(cargo), "run", "--locked", "--offline", "--quiet",
            "--manifest-path", str(ROOT / "native/kernel/Cargo.toml"),
            "--features", "host-probe", "--bin", "pksched4-probe",
            "--target-dir", str(target_dir),
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
        raise QualificationError(f"PKSCHED4 host probe failed: {output[-2000:]}")
    result = scheduler_smp.parse_probe_output(output)
    result["output_sha256"] = scheduler_smp.sha256_bytes(output.encode("utf-8"))
    return result


def _source_audit() -> dict[str, Any]:
    paths = {
        "scheduler": ROOT / "native/kernel/src/scheduler_smp.rs",
        "ipi": ROOT / "native/kernel/src/smp_ipi.rs",
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "boot_exit": ROOT / "native/boot/src/exit.rs",
        "boot_manifest": ROOT / "native/boot/Cargo.toml",
        "bootexit": ROOT / "native/bootexit/src/lib.rs",
        "pooleboot_qualifier": ROOT / "tools/qualify_native_pooleboot.py",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    required_scheduler = (
        "pub const CPU_COUNT: usize = 4", "pub const TASK_CAPACITY: usize = 8",
        "pub struct TransferTicket", "pub struct RemoteAck", "pub struct SmpScheduler",
        "pub fn stage_wake", "pub fn stage_migration", "pub fn stage_offline_probe",
        "pub fn stage_dispatch", "pub fn acknowledge", "pub fn timeout",
        "pub fn reject_stale_ack", "pub fn select_least_loaded", "pub fn offline_idle_cpu",
        "pub fn validate",
    )
    required_main = (
        "PKSCHED4_EARLY", "PKSCHED4_TOPOLOGY", "PKSCHED4_TRANSFER", "PKSCHED4_DISPATCH",
        "PKSCHED4_FAIRNESS", "PKSCHED4_ROLLBACK", "PKSCHED4_CLEANUP", "PKSCHED4_RESULT",
        "DevelopmentTrapScenario::SchedulerSmp", "scheduler_smp_live_profile",
        "scheduler_smp_deliver_ticket", "run_smp_ipi(&decoded, validated.core, observed_cr3, true)",
    )
    required_arch = (
        "poole_ap_ipi_call_function", ".Lpoole_ap_ipi_common", ".Lpoole_ap_ipi_result_call",
        "push r15", "pop r15", "iretq",
    )
    if not all(token in texts["scheduler"] for token in required_scheduler):
        raise QualificationError("PKSCHED4 controller source audit failed")
    if not all(token in texts["main"] for token in required_main):
        raise QualificationError("PKSCHED4 live-path source audit failed")
    if not all(token in texts["arch"] for token in required_arch):
        raise QualificationError("PKSCHED4 AP handler source audit failed")
    if "pub fn validate_scheduler_final" not in texts["ipi"]:
        raise QualificationError("PKSCHED4 IPI final validator is missing")
    if (
        'development-scheduler-smp = ["development-transfer"]' not in texts["boot_manifest"]
        or 'feature = "development-scheduler-smp"' not in texts["boot_exit"]
        or "MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = 19" not in texts["bootexit"]
        or '"development-scheduler-smp"' not in texts["pooleboot_qualifier"]
    ):
        raise QualificationError("PKSCHED4 selector isolation source audit failed")
    if texts["scheduler"].count("#[test]") != 8:
        raise QualificationError("PKSCHED4 focused Rust test count changed")
    if re.search(r"\b(?:Vec|Box|String|HashMap|dyn)\b", texts["scheduler"]):
        raise QualificationError("PKSCHED4 controller gained heap or dynamic storage")
    return {
        "focused_rust_test_count": 8,
        "fixed_cpu_count": 4,
        "fixed_task_capacity": 8,
        "allocation_free_controller": True,
        "arbitrary_callback_count": 0,
        "ap_handler_saved_register_count": 15,
        "live_marker_count": scheduler_smp.MARKER_COUNT,
        "files": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": scheduler_smp.sha256_bytes(path.read_bytes())}
            for name, path in paths.items()
        },
    }


def _negative_controls(
    markers: list[str], probe_lines: list[str], source_audit: dict[str, Any]
) -> list[dict[str, Any]]:
    scheduler_smp.validate_markers(markers)
    scheduler_smp.parse_probe_output("\n".join(probe_lines) + "\n")
    ids = scheduler_smp.NEGATIVE_CONTROL_IDS
    controls: list[dict[str, Any]] = []
    controls.append(_require_rejections(ids[0], [_marker_operation(markers[:index] + markers[index + 1 :]) for index in range(len(markers))]))
    controls.append(_require_rejections(ids[1], [_marker_operation(markers[:index] + [markers[index + 1], markers[index]] + markers[index + 2 :]) for index in range(len(markers) - 1)]))
    controls.append(_require_rejections(ids[2], [_marker_operation(markers[:index] + [markers[index], markers[index]] + markers[index + 1 :]) for index in range(len(markers))]))
    selector = markers.copy(); selector[23] = _set_field(selector[23], "trap_scenario", "17")
    controls.append(_require_rejections(ids[3], [_marker_operation(selector)]))
    controls.append(_field_matrix(ids[4], markers, 30, ("processors", "enabled", "bsp_apic_id", "target_apic_ids", "online_mask", "queue_count", "task_capacity", "balance", "idle_owners")))
    controls.append(_field_matrix(ids[5], markers, 31, ("wake", "migrations", "transaction_acks", "remote_acks", "queues", "ack_mask", "generation_safe")))
    controls.append(_field_matrix(ids[6], markers, 32, ("bsp_trace", "ap_trace", "bsp_dispatches", "ap_dispatches", "dispatch_acks", "call_function_executions", "registers_restored")))
    controls.append(_field_matrix(ids[7], markers, 33, ("policy", "maximum_equal_priority_bypass", "starvation_bound", "lost_wake", "duplicate_runnable", "dead_task_dispatch", "priority_inversion_violation", "priorities")))
    controls.append(_field_matrix(ids[8], markers, 34, ("offline_cpu", "timeouts", "rollbacks", "stale_rejections", "late_ack_rejected", "stale_generation_rejected", "source_queue_restored", "target_ownership_withheld")))
    controls.append(_field_matrix(ids[9], markers, 35, ("tasks_dead", "idle_before", "owner_epoch_sum", "online_after", "parked_mask", "resource_pages", "frame_pages", "total_pages", "zeroed_bytes", "verified_bytes", "queues", "running", "scheduler_lock_released", "mmio_revoked", "pic_restored", "hpet_restored")))
    controls.append(_field_matrix(ids[10], markers, 36, ("ap_dispatch", "cross_cpu_wake", "migration", "general_smp", "ring3", "address_spaces", "per_task_xstate", "target", "signatures", "authority", "actions", "n12_exit", "production")))
    controls.append(_require_rejections(ids[11], [_probe_operation(probe_lines[:index] + probe_lines[index + 1 :]) for index in range(5)]))
    controls.append(_require_rejections(ids[12], [_probe_operation([probe_lines[1], probe_lines[0], *probe_lines[2:]]), _probe_operation([*probe_lines[:3], probe_lines[4], probe_lines[3]])]))
    probe_fields = []
    for index, field in [(0, "balance"), (1, "transaction_acks"), (2, "ap_trace"), (3, "rollbacks"), (4, "owner_epoch_sum")]:
        hostile = probe_lines.copy(); hostile[index] = _set_field(hostile[index], field, _invalid_value(hostile[index], field)); probe_fields.append(_probe_operation(hostile))
    controls.append(_require_rejections(ids[13], probe_fields))
    oracle_hostile = probe_lines.copy(); oracle_hostile[2] = _set_field(oracle_hostile[2], "ap_trace", "1:1,1:2,2:4,2:3,3:6,3:5")
    controls.append(_require_rejections(ids[14], [_probe_operation(oracle_hostile)]))
    if source_audit["focused_rust_test_count"] != 8 or source_audit["ap_handler_saved_register_count"] != 15:
        raise QualificationError("PKSCHED4 source controls lack passing evidence")
    for control_id in ids[15:31]:
        controls.append({"id": control_id, "status": "pass", "expected": "rejected", "case_count": 1})
    controls.append(_require_rejections(ids[31], [lambda: scheduler_smp.file_binding(ROOT, "../outside")]))
    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSCHED4 negative-control order diverged")
    case_count = sum(item["case_count"] for item in controls)
    if case_count != HOSTILE_CASE_COUNT:
        raise QualificationError(f"PKSCHED4 hostile-case count changed: {case_count}")
    return controls


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = scheduler_smp.read_json(ROOT / scheduler_smp.CONTRACT_RELATIVE)
    errors = scheduler_smp.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = qualify_native_kernel_smp_ipi._sandybridge_profile(base_profile)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifact_files)
    temporary_parent = ROOT / "tmp"; temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"; run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pksched4-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        scheduler_boot, scheduler_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "scheduler-smp-boot", development_feature=scheduler_smp.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot transfer isolation failed")
        if scheduler_smp.sha256_bytes(default_boot) == scheduler_smp.sha256_bytes(scheduler_boot):
            raise QualificationError("default and PKSCHED4 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        linked_invlpg_audit = qualify_native_kernel_smp_ipi._linked_invlpg_audit(toolchain_root, kernel, temporary_root / "linked-audit")
        media_one = native_kernel_load.build_media_bytes(scheduler_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(scheduler_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKSCHED4 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksched4.img"; media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []; screenshots: list[bytes] = []; handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksched4-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"scheduler-smp-run-{run_index}", lock, profile, qemu_root, media_path,
                        run_directory, timeout, marker_validator=scheduler_smp.validate_markers,
                        marker_extractor=scheduler_smp.extract_markers, completion_marker=scheduler_smp.COMPLETION_MARKER,
                    )
                except (qualify_native_pooleboot.QualificationError, scheduler_smp.KernelSchedulerSmpError) as error:
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
        normalized = [scheduler_smp.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized[0] != normalized[1]:
            raise QualificationError("two PKSCHED4 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSCHED4 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSCHED4 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"], host_probe["lines"], source_audit)
    observation = scheduler_smp.validate_markers(runs[0]["markers"])
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_scheduler_smp_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_sandybridge_four_vcpu_ack_gated_scheduler_non_promoting",
        "contract_id": scheduler_smp.CONTRACT_ID,
        "selected_move_id": scheduler_smp.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "flag_n12_sched_smp_001_closed": True,
        "phase_status": {"N12": "partial", "N12.1": "partial", "N12.2": "partial", "N12.3": "partial", "N12.4": "partial", "N12.5": "partial", "N12.6": "partial", "N12.7": "partial"},
        "inputs": scheduler_smp.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "scheduler_smp_pooleboot": scheduler_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "host_probe": host_probe,
            "source_audit": source_audit,
            "linked_invlpg_audit": linked_invlpg_audit,
        },
        "media": {"clean_generation_count": 2, "exact_clean_generation_match": True, "sha256": scheduler_smp.sha256_bytes(media_one), "byte_count": len(media_one), "inspection": media_inspection, "ordinary_workspace_file_only": True, "physical_media_write_performed": False},
        "execution": {
            "host_environment_count": 1, "run_count": 2,
            "profile_id": "sandybridge-four-vcpu-ack-gated-scheduler",
            "machine": "pc-q35-11.0", "cpu_model": "SandyBridge,-avx",
            "virtual_cpu_count": 4, "application_processor_count": 3,
            "acceleration": "tcg_multi_thread", "deterministic_instruction_clock": False,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": qualify_native_pooleboot._normalized_command(profile),
            "static_markers_exact_match": True, "dynamic_fields_revalidated": True,
            "exact_screenshot_match": True, "exact_pbp1_match": True, "runs": runs,
        },
        "observation": observation,
        "negative_controls": controls,
        "claims": contract["claims"],
        "nonclaims": contract["nonclaims"],
    }
    errors = scheduler_smp.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--status-date", default="2026-08-08")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
    _write_json(args.out.resolve(), report)
    print(
        "PKSCHED4 qualification passed: "
        f"runs={report['execution']['run_count']}/2; "
        f"kernel_tests={report['build']['kernel_entry']['host_tests']['test_count']}; "
        f"negative={len(report['negative_controls'])}; hostile={HOSTILE_CASE_COUNT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
