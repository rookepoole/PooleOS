#!/usr/bin/env python3
"""Build and qualify the bounded PKLOCK1 native lock family."""

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
    native_kernel_locks as locks,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / locks.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"


class QualificationError(RuntimeError):
    """Raised when PKLOCK1 qualification fails closed."""


def _progress(stage: str) -> None:
    print(f"PKLOCK1_QUALIFICATION stage={stage}", flush=True)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(native_pooleboot.canonical_json_bytes(value))


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKLOCK1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKLOCK1 mutation field is missing: {field}")
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
        except (locks.KernelLocksError, QualificationError):
            continue
        raise QualificationError(f"PKLOCK1 hostile control did not reject: {control_id}")
    return {
        "id": control_id,
        "status": "pass",
        "expected": "rejected",
        "case_count": len(operations),
    }


def _marker_operation(markers: list[str]) -> Callable[[], Any]:
    return lambda: locks.validate_markers(markers)


def _probe_operation(lines: list[str]) -> Callable[[], Any]:
    return lambda: locks.parse_probe_output("\n".join(lines) + "\n")


def _field_matrix(
    control_id: str, markers: list[str], marker_index: int, fields: tuple[str, ...]
) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        candidate = markers.copy()
        candidate[marker_index] = _set_field(
            candidate[marker_index], field, _invalid_value(candidate[marker_index], field)
        )
        operations.append(_marker_operation(candidate))
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
            "pklock1-probe",
            "--target",
            HOST_TARGET,
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
        raise QualificationError(f"PKLOCK1 host probe failed: {output[-3000:]}")
    result = locks.parse_probe_output(output)
    result.update(
        {
            "output_sha256": locks.sha256_bytes(output.encode("utf-8")),
            "target": HOST_TARGET,
            "thread_count": 4,
        }
    )
    return result


def _audit_lock_source(
    core: str,
    main: str,
    arch: str,
    scheduler: str,
    smp: str,
    boot_exit: str,
    boot_manifest: str,
    bootexit: str,
) -> dict[str, Any]:
    production_core = core.split("#[cfg(test)]", 1)[0]
    forbidden = tuple(
        token
        for token in ("alloc::", "Vec<", "Box<", "String", "HashMap", "dyn ", "std::")
        if token in production_core
    )
    core_required = (
        "pub struct LockContext",
        "pub struct LockOrderGraph",
        "pub struct TicketSpinLock",
        "pub struct IrqSaveSpinLock",
        "pub struct SleepMutex",
        "pub struct Notification",
        "pub struct ReaderWriterLock",
        "pub struct SequenceLock",
        "pub fn try_lock",
        "pub fn lock_bounded",
        "pub fn owner_died",
        "pub fn notify_all",
        "pub fn try_read",
        "pub fn try_write",
        "fn reserve_waiting_writer",
        "lock_address",
        "compare_exchange",
    )
    main_required = (
        "PKLOCK1_EARLY",
        "PKLOCK1_FAMILY",
        "PKLOCK1_POLICY",
        "PKLOCK1_LIVE",
        "PKLOCK1_HOST",
        "PKLOCK1_RESULT",
        "smp_lock_live_profile",
        "DevelopmentTrapScenario::Locks",
        "locks::LIVE_PROBE_PAGE_TABLE_INDEX",
    )
    arch_required = (
        "lock xadd dword ptr [rbx + {lock_next_offset}], eax",
        "lock cmpxchg dword ptr [rbx + {lock_owner_offset}], edx",
        "lock inc dword ptr [rbx + {lock_acquisitions_offset}]",
        "lock bts dword ptr [rbx + {lock_cpu_mask_offset}], ecx",
        "lock inc dword ptr [rbx + {lock_serving_offset}]",
        "invlpg [rbx]",
        "mfence",
    )
    scheduler_required = (
        "ExternalLock = 3",
        "pub fn block_current_for_lock",
        "pub fn wake_lock_waiter",
        "pub fn donate_priority",
        "pub fn revoke_priority_donation",
    )
    smp_required = (
        "pub fn validate_lock_final",
        "SHOOTDOWN_RESERVED_OFFSET",
    )
    boot_required = (
        'development-locks = ["development-transfer"]',
        'feature = "development-locks"',
        'cfg!(feature = "development-locks")',
        "MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = 22",
    )
    missing = {
        "core": [token for token in core_required if token not in core],
        "main": [token for token in main_required if token not in main],
        "arch": [token for token in arch_required if token not in arch],
        "scheduler": [token for token in scheduler_required if token not in scheduler],
        "smp": [token for token in smp_required if token not in smp],
        "boot": [
            token
            for token in boot_required
            if token not in "\n".join((boot_manifest, boot_exit, bootexit))
        ],
    }
    unit_test_count = core.count("#[test]")
    if forbidden or any(missing.values()) or unit_test_count != 10:
        raise QualificationError(
            f"PKLOCK1 source scope changed: forbidden={forbidden}; missing={missing}; "
            f"tests={unit_test_count}"
        )
    return {
        "heap_api_token_count": 0,
        "lock_primitive_count": 6,
        "rank_class_count": 5,
        "focused_unit_test_count": unit_test_count,
        "live_locked_instruction_class_count": 5,
        "result": "pass_allocation_free_bounded_lock_source_audit",
    }


def _source_audit() -> tuple[dict[str, Any], dict[str, str]]:
    paths = {
        "core": ROOT / "native/kernel/src/locks.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "scheduler": ROOT / "native/kernel/src/scheduler.rs",
        "smp": ROOT / "native/kernel/src/smp_ipi.rs",
        "boot_exit": ROOT / "native/boot/src/exit.rs",
        "boot_manifest": ROOT / "native/boot/Cargo.toml",
        "bootexit": ROOT / "native/bootexit/src/lib.rs",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    result = _audit_lock_source(
        texts["core"],
        texts["main"],
        texts["arch"],
        texts["scheduler"],
        texts["smp"],
        texts["boot_exit"],
        texts["boot_manifest"],
        texts["bootexit"],
    )
    result["files"] = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": locks.sha256_bytes(path.read_bytes()),
        }
        for name, path in paths.items()
    }
    return result, texts


def _source_operation(texts: dict[str, str]) -> Callable[[], Any]:
    return lambda: _audit_lock_source(
        texts["core"],
        texts["main"],
        texts["arch"],
        texts["scheduler"],
        texts["smp"],
        texts["boot_exit"],
        texts["boot_manifest"],
        texts["bootexit"],
    )


def _negative_controls(
    markers: list[str], probe_lines: list[str], source_texts: dict[str, str]
) -> list[dict[str, Any]]:
    locks.validate_markers(markers)
    locks.parse_probe_output("\n".join(probe_lines) + "\n")
    ids = locks.NEGATIVE_CONTROL_IDS
    controls: list[dict[str, Any]] = []
    controls.append(_require_rejections(ids[0], [_marker_operation(markers[:-1])]))
    reordered = markers.copy()
    reordered[31], reordered[32] = reordered[32], reordered[31]
    controls.append(_require_rejections(ids[1], [_marker_operation(reordered)]))
    controls.append(_require_rejections(ids[2], [_marker_operation([*markers, markers[-1]])]))
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "21")
    controls.append(_require_rejections(ids[3], [_marker_operation(selector)]))
    controls.append(
        _field_matrix(
            ids[4],
            markers,
            30,
            ("raw_spin", "irqsave_spin", "sleeping_mutex", "notification", "rwlock", "seqlock", "allocation", "rank_count"),
        )
    )
    controls.append(
        _field_matrix(
            ids[5],
            markers,
            31,
            (
                "try", "timed", "owner", "recursion_rejected", "irq_nesting_rejected",
                "preempt_nesting_rejected", "priority_inheritance", "maximum_bypass",
                "deadlock_graph", "owner_death", "exact_rollback",
            ),
        )
    )
    controls.append(
        _field_matrix(
            ids[6],
            markers,
            32,
            (
                "profile", "next", "serving", "acquisitions", "cpu_mask", "tickets",
                "mappings_installed", "mappings_revoked", "queue_drained", "owner",
                "unique_tickets", "exact_topology",
            ),
        )
    )
    controls.append(
        _field_matrix(
            ids[7],
            markers,
            33,
            (
                "exact_four_thread", "scheduler_sleep_path", "fairness", "rw_contention",
                "seqlock_contention", "hostile_controls",
            ),
        )
    )
    controls.append(
        _field_matrix(
            ids[8],
            markers,
            34,
            (
                "profile", "lock_family", "live_multi_ap_contention", "host_concurrency",
                "scheduler_sleep", "reclamation", "general_smp", "ring3", "address_spaces",
                "target", "signatures", "authority", "actions", "n12_exit", "production", "terminal",
            ),
        )
    )
    controls.append(_require_rejections(ids[9], [_probe_operation(probe_lines[:-1])]))
    probe_reordered = probe_lines.copy()
    probe_reordered[0], probe_reordered[1] = probe_reordered[1], probe_reordered[0]
    controls.append(_require_rejections(ids[10], [_probe_operation(probe_reordered)]))
    controls.append(
        _require_rejections(
            ids[11],
            [
                _probe_operation(
                    [
                        *probe_lines[:index],
                        line.replace(" PASS ", " FAIL ", 1),
                        *probe_lines[index + 1 :],
                    ]
                )
                for index, line in enumerate(probe_lines)
            ],
        )
    )

    def probe_field(line_index: int, field: str, value: str) -> Callable[[], Any]:
        candidate = probe_lines.copy()
        candidate[line_index] = _set_field(candidate[line_index], field, value)
        return _probe_operation(candidate)

    controls.append(_require_rejections(ids[12], [probe_field(1, "fifo_mismatches", "1")]))
    controls.append(
        _require_rejections(
            ids[13],
            [probe_field(2, "interrupts_restored", "0"), probe_field(2, "preemption_restored", "0")],
        )
    )
    controls.append(
        _require_rejections(
            ids[14],
            [probe_field(2, "nested_irq_rejected", "0"), probe_field(2, "nested_preemption_rejected", "0")],
        )
    )
    controls.append(
        _require_rejections(
            ids[15],
            [probe_field(3, "maximum_bypass", "8"), probe_field(3, "handoff_order", "2,3,4,5,6,7,8,9")],
        )
    )
    controls.append(_require_rejections(ids[16], [probe_field(3, "priority_inheritance", "0")]))
    controls.append(
        _require_rejections(
            ids[17],
            [probe_field(3, "owner_deaths", "0"), probe_field(3, "owner_death_wakes", "0")],
        )
    )
    controls.append(
        _require_rejections(
            ids[18],
            [probe_field(4, "fifo", "0"), probe_field(4, "sequence", "3")],
        )
    )
    controls.append(
        _require_rejections(
            ids[19],
            [probe_field(4, "timeout", "0"), probe_field(4, "cancel", "0")],
        )
    )
    controls.append(_require_rejections(ids[20], [probe_field(5, "final", "1023")]))
    controls.append(_require_rejections(ids[21], [probe_field(5, "writer_preference", "0")]))
    controls.append(
        _require_rejections(
            ids[22],
            [probe_field(6, "final", "2047"), probe_field(6, "sequence", "4094")],
        )
    )
    controls.append(_require_rejections(ids[23], [probe_field(6, "odd_snapshots", "1")]))
    controls.append(
        _require_rejections(
            ids[24],
            [probe_field(7, "cycles_rejected", "0"), probe_field(7, "inversion_rejected", "0")],
        )
    )
    controls.append(_require_rejections(ids[25], [probe_field(7, "recursion_rejected", "0")]))
    controls.append(
        _require_rejections(
            ids[26],
            [
                probe_field(8, "next", "3"),
                probe_field(8, "serving", "1"),
                probe_field(8, "owner", "1"),
                probe_field(8, "cancelled", "1"),
                probe_field(8, "timeouts", "0"),
                probe_field(8, "exact", "0"),
            ],
        )
    )
    dynamic = source_texts.copy()
    dynamic["core"] = "use alloc::vec::Vec;\n" + dynamic["core"]
    controls.append(_require_rejections(ids[27], [_source_operation(dynamic)]))
    controls.append(_require_rejections(ids[28], [lambda: locks.file_binding(ROOT, "../escape")]))
    overclaims: list[Callable[[], Any]] = []
    for field in ("reclamation", "general_smp", "target", "n12_exit", "production"):
        candidate = markers.copy()
        candidate[34] = _set_field(candidate[34], field, "1")
        overclaims.append(_marker_operation(candidate))
    controls.append(_require_rejections(ids[29], overclaims))
    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKLOCK1 hostile-control order changed")
    return controls


def _sandybridge_four_vcpu_profile(profile: dict[str, Any]) -> dict[str, Any]:
    derived = copy.deepcopy(profile)
    arguments = derived["base_argument_template"]
    for option, value in (
        ("-smp", "4,sockets=1,dies=1,clusters=1,cores=4,threads=1,maxcpus=4"),
        ("-cpu", "SandyBridge,-avx"),
        ("-accel", "tcg,thread=multi"),
    ):
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
    derived["machine"].update(
        {"cpu_model": "SandyBridge,-avx", "vcpus": 4, "cores": 4, "tcg_thread_mode": "multi"}
    )
    return derived


def make_readiness(
    toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int
) -> dict[str, Any]:
    _progress("contracts")
    contract = locks.read_json(ROOT / locks.CONTRACT_RELATIVE)
    errors = locks.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = _sandybridge_four_vcpu_profile(base_profile)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    _progress("kernel_entry")
    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(
        manifest, kernel, artifact_files
    )
    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pklock1-qualification-", dir=temporary_parent
    ) as temporary:
        temporary_root = Path(temporary)
        _progress("host_probe")
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        _progress("source_audit")
        source_audit, source_texts = _source_audit()
        _progress("boot_builds")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        lock_boot, lock_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "lock-boot",
            development_feature=locks.FEATURE,
        )
        if (
            b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot
            or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot
        ):
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if default_boot == lock_boot:
            raise QualificationError("default and PKLOCK1 PooleBoot binaries are not distinct")
        _progress("media")
        media_one = native_kernel_load.build_media_bytes(
            lock_boot, config, manifest, kernel, artifact_files
        )
        media_two = native_kernel_load.build_media_bytes(
            lock_boot, config, manifest, kernel, artifact_files
        )
        if media_one != media_two:
            raise QualificationError("two PKLOCK1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pklock1.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            _progress(f"qemu_run_{run_index}")
            with tempfile.TemporaryDirectory(
                prefix=f"pklock1-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"locks-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=locks.validate_markers,
                        marker_extractor=locks.extract_markers,
                        completion_marker=locks.COMPLETION_MARKER,
                    )
                except (
                    qualify_native_pooleboot.QualificationError,
                    locks.KernelLocksError,
                ) as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(
                                encoding="ascii", errors="ignore"
                            ).splitlines()
                            if line.strip().startswith("POOLE")
                        ][-18:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
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
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKLOCK1 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKLOCK1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKLOCK1 runs produced different PBP1 bytes")
        _progress("negative_controls")
        controls = _negative_controls(runs[0]["markers"], host_probe["lines"], source_texts)

    observation = locks.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_locks_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_sandybridge_four_vcpu_lock_family_non_promoting",
        "contract_id": locks.CONTRACT_ID,
        "selected_move_id": locks.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "flag_n12_concurrency_locks_001_closed": True,
        "phase_status": {"N12": "partial", "N12.2": "complete"},
        "inputs": locks.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "locks_pooleboot": lock_build,
            "host_probe": host_probe,
            "source_audit": source_audit,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": locks.sha256_bytes(media_one),
            "byte_count": len(media_one),
            "inspection": media_inspection,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "sandybridge-x87-sse-four-vcpu-ticket-contention",
            "machine": "pc-q35-11.0",
            "cpu_model": "SandyBridge,-avx",
            "virtual_cpu_count": 4,
            "application_processor_count": 3,
            "acceleration": "tcg_multi_thread",
            "deterministic_instruction_clock": False,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": locks.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "fresh_vars_each_run": True,
            "media_read_only": True,
            "guest_network": False,
            "host_acceleration": False,
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "markers_per_run": locks.MARKER_COUNT,
            "runs": runs,
        },
        "observation": observation,
        "negative_controls": controls,
        "claims": contract["claims"],
        "nonclaims": contract["nonclaims"],
    }
    errors = list(validate_json(report, locks.read_json(ROOT / locks.READINESS_SCHEMA_RELATIVE)))
    if errors:
        raise QualificationError(
            "; ".join(f"{issue.path}: {issue.message}" for issue in errors)
        )
    _progress("report_validated")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-09-04")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        report = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        _write_json(args.out, report)
        errors = locks.readiness_errors(locks.read_json(args.out), ROOT)
        if errors:
            raise QualificationError("; ".join(errors))
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        locks.KernelLocksError,
        native_kernel_load.KernelLoadError,
        native_kernel_transfer.KernelTransferError,
        native_tier0.Tier0Error,
    ) as error:
        print(f"NATIVE_KERNEL_LOCKS_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    hostile_cases = sum(item["case_count"] for item in report["negative_controls"])
    host_probe = report["build"]["host_probe"]
    print(
        "NATIVE_KERNEL_LOCKS_QUALIFICATION PASS "
        f"host_tests={report['build']['kernel_entry']['host_tests']['test_pass_count']}/"
        f"{report['build']['kernel_entry']['host_tests']['test_count']} "
        f"probe_receipts={host_probe['receipt_count']} ticket_acquisitions={host_probe['ticket_acquisitions']} "
        f"runs={report['execution']['run_count']}/2 markers={report['execution']['markers_per_run']} "
        f"controls={len(report['negative_controls'])}/{len(locks.NEGATIVE_CONTROL_IDS)} "
        f"cases={hostile_cases} live_vcpus=4 reclamation=0 general_smp=0 "
        "n12_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
