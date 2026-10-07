#!/usr/bin/env python3
"""Build and qualify bounded PKSCHED6 exact-topology SMP preemption."""

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

from runtime import native_kernel_load  # noqa: E402
from runtime import native_kernel_scheduler_smp_preempt as smp_preempt  # noqa: E402
from runtime import native_kernel_transfer, native_tier0  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_kernel_smp_ipi  # noqa: E402
from tools import qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / smp_preempt.READINESS_RELATIVE
HOSTILE_CASE_COUNT = sum(smp_preempt.NEGATIVE_CONTROL_CASE_COUNTS)


class QualificationError(RuntimeError):
    """Raised when PKSCHED6 qualification fails closed."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSCHED6 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSCHED6 mutation field is missing: {field}")
    value = match.group(1)
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    if value.startswith("0x"):
        return "0x0000000000000000" if len(value) == 18 else "0x00"
    return "invalid"


def _marker_operation(markers: list[str]) -> Callable[[], Any]:
    return lambda: smp_preempt.validate_markers(markers)


def _probe_operation(lines: list[str]) -> Callable[[], Any]:
    return lambda: smp_preempt.parse_probe_output("\n".join(lines) + "\n")


def _require_rejections(
    control_id: str, operations: list[Callable[[], Any]]
) -> dict[str, Any]:
    if not operations:
        raise QualificationError("PKSCHED6 empty rejection control")
    for operation in operations:
        try:
            operation()
        except (smp_preempt.KernelSchedulerSmpPreemptError, QualificationError):
            continue
        raise QualificationError(f"PKSCHED6 hostile control did not reject: {control_id}")
    return {
        "id": control_id,
        "status": "pass",
        "expected": "rejected",
        "case_count": len(operations),
    }


def _field_matrix(
    control_id: str, markers: list[str], index: int, fields: tuple[str, ...]
) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        hostile = markers.copy()
        hostile[index] = _set_field(
            hostile[index], field, _invalid_value(hostile[index], field)
        )
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
            "pksched6-probe",
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
        raise QualificationError(f"PKSCHED6 host probe failed: {output[-2000:]}")
    result = smp_preempt.parse_probe_output(output)
    result["output_sha256"] = smp_preempt.sha256_bytes(output.encode("utf-8"))
    return result


def _build_native_control_library(toolchain_root: Path, target: Path):
    cargo, rustc, env = qualify_native_kernel_entry._toolchain(toolchain_root)
    result = subprocess.run(
        [str(cargo), "build", "--locked", "--offline", "--lib", "--package", "poolekernel",
         "--manifest-path", str(ROOT / "native/Cargo.toml"), "--target", qualify_native_kernel_entry.HOST_TARGET,
         "--target-dir", str(target)], cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise QualificationError(f"PKSCHED6 native library build failed: {result.stdout.decode('utf-8', errors='replace')[-3000:]}")
    return target / qualify_native_kernel_entry.HOST_TARGET / "debug", rustc, env


def _build_native_control_probe(toolchain_root: Path, target: Path, source: bytes | None = None, library=None):
    artifacts, rustc, env = library or _build_native_control_library(toolchain_root, target / "library")
    target.mkdir(parents=True, exist_ok=True)
    fixture, native, _ = (ROOT / p for p in smp_preempt.NATIVE_CONTROL_SOURCES)
    (target / "preempt.rs").write_bytes((native.read_bytes() if source is None else source) + b"\n" + fixture.read_bytes())
    harness = target / "harness.rs"
    harness.write_text('pub use poolekernel::scheduler_smp;\nmod preempt;\nfn main() { preempt::controls_main(); }\n', encoding="utf-8")
    executable = target / "pksched6-controls.exe"
    result = subprocess.run(
        [str(rustc), "--edition=2024", "--crate-name", "pksched6_controls", str(harness),
         "--extern", f"poolekernel={artifacts / 'libpoolekernel.rlib'}", "-L", f"dependency={artifacts / 'deps'}",
         "-o", str(executable)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise QualificationError(f"PKSCHED6 native control build failed: {result.stdout.decode('utf-8', errors='replace')[-3000:]}")
    return executable, env


def _run_native_control_probe(toolchain_root: Path, target: Path) -> dict[str, Any]:
    executable, env = _build_native_control_probe(toolchain_root, target)
    result = subprocess.run([str(executable)], cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    output = result.stdout.decode("utf-8", errors="strict").replace("\r\n", "\n")
    if result.returncode:
        raise QualificationError(f"PKSCHED6 native controls failed: {output[-3000:]}")
    controls = smp_preempt.parse_native_control_output(output)
    return {"scope": "host_execution_of_native_SMP_preemption_not_privileged_guest_execution",
        "exit_code": result.returncode, "lines": output.splitlines(),
        "output_sha256": smp_preempt.sha256_bytes(output.encode("utf-8")),
        "executable_sha256": smp_preempt.sha256_bytes(executable.read_bytes()),
        "controls": controls, "verified_cases_total": sum(c["case_count"] for c in controls),
        "sources": [smp_preempt.file_binding(ROOT, p) for p in smp_preempt.NATIVE_CONTROL_SOURCES]}


def _source_audit() -> dict[str, Any]:
    paths = {name: ROOT / path for name, path in smp_preempt.SOURCE_AUDIT_PATHS.items()}
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    return dict(_audit_source_text(texts), files={name: {
        "path": path.relative_to(ROOT).as_posix(), "sha256": smp_preempt.sha256_bytes(path.read_bytes())
    } for name, path in paths.items()})


def _scope(text: str, start: str, end: str) -> str:
    if text.count(start) != 1:
        raise QualificationError("PKSCHED6 source scope start is missing or ambiguous")
    body = text.split(start, 1)[1]
    if end not in body:
        raise QualificationError("PKSCHED6 source scope end is missing")
    return body.split(end, 1)[0]


AP_ENTRIES = ("reschedule", "shootdown", "call_function", "diagnostic", "panic", "stop")
AP_REGISTERS = ("rbx", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15")
LIFECYCLE_GUARDS = tuple(f"proof.lifecycle.{name}_mask != smp_ipi::TARGET_CPU_MASK"
                         for name in ("online", "quiesced", "parked", "released")) + (
    "preempt.after_park.online_mask != 1",
    "preempt.after_park.scheduler.dead_count as usize != scheduler_smp::TASK_CAPACITY")
SCRUB_GUARDS = ("receipt.kind != ScrubKind::Release", "receipt.page_count != smp_runtime::RESOURCE_PAGE_COUNT",
    "receipt.zeroed_bytes != expected_bytes", "receipt.verified_bytes != expected_bytes", ".free_scrubbed_automatic(allocation, access)")


def _audit_source_text(texts: dict[str, str]) -> dict[str, Any]:
    required_controller = (
        "pub const EVENT_CAPACITY_PER_CPU: usize = 4",
        "pub const QUANTUM_TICKS: u32 = 2",
        "pub const MAX_EVENT_LATENCY_TICKS: u64 = 1",
        "pub const MAX_WATCHDOG_TICKS: u32 = QUANTUM_TICKS",
        "pub enum EventKind",
        "pub struct FrameContract",
        "pub struct SmpPreemption",
        "pub fn queue_event",
        "pub fn handle_tick",
        "pub fn acknowledge_reschedule",
        "pub fn stage_offline_probe",
        "pub fn timeout_offline",
        "pub fn finish_shutdown",
        "pub fn validate",
    )
    required_main = (
        "PKSCHED6_EARLY",
        "PKSCHED6_TOPOLOGY",
        "PKSCHED6_EVENT",
        "PKSCHED6_RESCHEDULE",
        "PKSCHED6_OWNERSHIP",
        "PKSCHED6_ROLLBACK",
        "PKSCHED6_BOUNDS",
        "PKSCHED6_CLEANUP",
        "PKSCHED6_RESULT",
        "DevelopmentTrapScenario::SchedulerSmpPreempt",
        "scheduler_smp_preempt_live_profile",
        "run_smp_ipi_preempt",
    )
    required_ipi = (
        "RESULT_RESCHEDULE_OBSERVED",
        "Operation::Reschedule",
        "pub fn validate_smp_preempt_final",
    )
    required_arch = (
        "poole_ap_ipi_reschedule",
        ".Lpoole_ap_ipi_common",
        ".Lpoole_ap_ipi_payload_reschedule",
        ".Lpoole_ap_ipi_result_reschedule",
        "push r15",
        "pop r15",
        "iretq",
    )
    if not all(token in texts["controller"] for token in required_controller):
        raise QualificationError("PKSCHED6 controller source audit failed")
    if not all(token in texts["main"] for token in required_main):
        raise QualificationError("PKSCHED6 live-path source audit failed")
    if not all(token in texts["ipi"] for token in required_ipi):
        raise QualificationError("PKSCHED6 reschedule IPI source audit failed")
    if not all(token in texts["arch"] for token in required_arch):
        raise QualificationError("PKSCHED6 AP handler source audit failed")
    maximum_match = re.search(r"MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = (\d+);", texts["bootexit"])
    if (
        'development-scheduler-smp-preempt = ["development-transfer"]'
        not in texts["boot_manifest"]
        or 'feature = "development-scheduler-smp-preempt"' not in texts["boot_exit"]
        or maximum_match is None
        or int(maximum_match.group(1)) < 20
        or '"development-scheduler-smp-preempt"' not in texts["pooleboot_qualifier"]
    ):
        raise QualificationError("PKSCHED6 selector isolation source audit failed")
    if texts["controller"].count("#[test]") != 5:
        raise QualificationError("PKSCHED6 focused Rust test count changed")
    if re.search(r"\b(?:Vec|Box|String|HashMap|dyn)\b", texts["controller"]):
        raise QualificationError("PKSCHED6 controller gained heap or dynamic storage")
    arch = texts["arch"]
    for name in AP_ENTRIES:
        entry = _scope(arch, f"poole_ap_ipi_{name}:\n", ".Lpoole_ap_ipi_common")
        if entry.splitlines()[0].strip() != "push rax":
            raise QualificationError("PKSCHED6 AP entry does not save RAX")
    common = _scope(arch, ".Lpoole_ap_ipi_common:\n", ".Lpoole_ap_ipi_return:\n")
    if [s.strip() for s in common.splitlines()[:13]] != ["push " + r for r in AP_REGISTERS]:
        raise QualificationError("PKSCHED6 AP register save order changed")
    restore = _scope(arch, ".Lpoole_ap_ipi_return:\n", ".Lpoole_ap_ipi_terminal_stop:")
    if [s.strip() for s in restore.splitlines() if s.strip()] != [*("pop " + r for r in reversed(AP_REGISTERS)), "pop rax", "iretq"]:
        raise QualificationError("PKSCHED6 AP register restore order changed")
    if re.search(r"\b(?:rbp|ebp|bp|bpl)\b", common):
        raise QualificationError("PKSCHED6 unsaved RBP is touched")
    lifecycle = _scope(texts["main"], "let preempt = proof.smp_preempt.unwrap_or_else(|| {", "logger.write_bytes(&PKSCHED6_TOPOLOGY);")
    scrub = _scope(texts["main"], "fn smp_runtime_release_resources_with_live_mmio(", "\nfn ")
    if not all(t in lifecycle for t in LIFECYCLE_GUARDS) or not all(t in scrub for t in SCRUB_GUARDS):
        raise QualificationError("PKSCHED6 park/scrub/release changed")
    return {
        "max_development_trap_scenario": int(maximum_match.group(1)),
        "focused_rust_test_count": 5,
        "cpu_lane_count": 4,
        "event_capacity": 16,
        "allocation_free_controller": True,
        "live_reschedule_count": 8,
        "ap_timer_interrupt_delivery": False,
        "ap_handler_saved_register_count": 15,
        "live_marker_count": smp_preempt.MARKER_COUNT,
    }


def _source_controls(texts: dict[str, str]) -> list[dict[str, Any]]:
    _audit_source_text(texts)

    def mutation(key, scope, old, new):
        if scope.count(old) != 1 or texts[key].count(scope) != 1:
            raise QualificationError("PKSCHED6 source mutation is not uniquely scoped")
        changed = dict(texts)
        changed[key] = texts[key].replace(scope, scope.replace(old, new, 1), 1)
        return lambda: _audit_source_text(changed)

    arch = texts["arch"]
    operations = []
    for name in AP_ENTRIES:
        scope = f"poole_ap_ipi_{name}:\n" + _scope(arch, f"poole_ap_ipi_{name}:\n", ".Lpoole_ap_ipi_common")
        operations.append(mutation("arch", scope, "push rax", "nop"))
    common = _scope(arch, ".Lpoole_ap_ipi_common:\n", ".Lpoole_ap_ipi_return:\n")
    operations.extend(mutation("arch", common, "push " + r + "\n", "nop\n") for r in AP_REGISTERS)
    restore = _scope(arch, ".Lpoole_ap_ipi_return:\n", ".Lpoole_ap_ipi_terminal_stop:")
    operations.extend(mutation("arch", restore, "pop " + r + "\n", "nop\n") for r in (*AP_REGISTERS, "rax"))
    operations.extend((mutation("arch", restore, "iretq", "ret"), mutation("arch", common, "mov r15d, eax", "mov rbp, rax")))
    controls = [_require_rejections(smp_preempt.NEGATIVE_CONTROL_IDS[31], operations)]
    lifecycle = _scope(texts["main"], "let preempt = proof.smp_preempt.unwrap_or_else(|| {", "logger.write_bytes(&PKSCHED6_TOPOLOGY);")
    scrub = _scope(texts["main"], "fn smp_runtime_release_resources_with_live_mmio(", "\nfn ")
    operations = [mutation("main", lifecycle, t, "false") for t in LIFECYCLE_GUARDS]
    operations.extend(mutation("main", scrub, t, "false") for t in SCRUB_GUARDS)
    controls.append(_require_rejections(smp_preempt.NEGATIVE_CONTROL_IDS[32], operations))
    return controls


def _negative_controls(
    markers: list[str], probe_lines: list[str], native_controls: dict[str, Any], audit_controls: dict[str, Any]
) -> list[dict[str, Any]]:
    smp_preempt.validate_markers(markers)
    smp_preempt.parse_probe_output("\n".join(probe_lines) + "\n")
    ids = smp_preempt.NEGATIVE_CONTROL_IDS
    controls: list[dict[str, Any]] = []
    controls.append(_require_rejections(ids[0], [_marker_operation(markers[:i] + markers[i + 1 :]) for i in range(len(markers))]))
    controls.append(_require_rejections(ids[1], [_marker_operation(markers[:i] + [markers[i + 1], markers[i]] + markers[i + 2 :]) for i in range(len(markers) - 1)]))
    controls.append(_require_rejections(ids[2], [_marker_operation(markers[:i] + [markers[i], markers[i]] + markers[i + 1 :]) for i in range(len(markers))]))
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "18")
    controls.append(_require_rejections(ids[3], [_marker_operation(selector)]))
    controls.append(_field_matrix(ids[4], markers, 30, ("processors", "enabled", "bsp_apic_id", "target_apic_ids", "online_mask", "queues", "tasks", "timer_lanes", "frame_lanes", "event_capacity", "quantum", "ist_bytes_each")))
    controls.append(_field_matrix(ids[5], markers, 31, ("cpu1_order", "cpu2_order", "cancelled", "wake", "migration", "pending", "deterministic", "order")))
    controls.append(_field_matrix(ids[6], markers, 32, ("live_ipis", "model_acks", "quantum_preemptions", "context_switches", "wake", "migration", "ack_gated", "result")))
    controls.append(_field_matrix(ids[7], markers, 33, ("frame_epochs", "timer_ticks", "trace", "per_cpu", "frame_owner_exact", "timer_owner_exact", "run_queue_owner_exact")))
    controls.append(_field_matrix(ids[8], markers, 34, ("offline_cpu", "timeouts", "rollbacks", "stale_rejections", "source_queue_restored", "late_ack_rejected", "target_ownership_withheld")))
    controls.append(_field_matrix(ids[9], markers, 35, ("quantum", "event_latency", "watchdog_age", "maximum_bypass", "starvation", "lost_wake", "duplicate_runnable", "watchdog_tripped")))
    controls.append(_field_matrix(ids[10], markers, 36, ("online_after", "dead", "teardown", "frame_owners_revoked", "timer_owners_revoked", "resource_pages", "frame_pages", "total_pages", "zeroed_bytes", "verified_bytes", "pending_events", "pending_remote", "scheduler_lock_released", "capability_revoked", "runtime_revoked", "mmio_revoked", "pic_restored", "hpet_restored")))
    controls.append(_field_matrix(ids[11], markers, 37, ("live_reschedule_ipi", "deterministic_events", "offline_rollback", "watchdog_bound", "exact_teardown", "general_smp", "ap_timer_interrupts", "ring3", "address_spaces", "target", "signatures", "authority", "actions", "n12_exit", "production")))
    controls.append(_require_rejections(ids[12], [_probe_operation(probe_lines[:i] + probe_lines[i + 1 :]) for i in range(7)]))
    controls.append(_require_rejections(ids[13], [_probe_operation([probe_lines[1], probe_lines[0], *probe_lines[2:]]), _probe_operation([*probe_lines[:5], probe_lines[6], probe_lines[5]])]))
    probe_fields: list[Callable[[], Any]] = []
    for index, field in ((0, "quantum"), (1, "cpu1_order"), (2, "acks"), (3, "frame_epochs"), (4, "rollbacks"), (5, "watchdog_age"), (6, "frame_owners_revoked")):
        hostile = probe_lines.copy()
        hostile[index] = _set_field(hostile[index], field, _invalid_value(hostile[index], field))
        probe_fields.append(_probe_operation(hostile))
    controls.append(_require_rejections(ids[14], probe_fields))
    oracle_hostile = probe_lines.copy()
    oracle_hostile[3] = _set_field(oracle_hostile[3], "trace", "1:2>1;3:6>5>7")
    controls.append(_require_rejections(ids[15], [_probe_operation(oracle_hostile)]))
    executed = {c["id"]: c for c in [*native_controls["controls"], *audit_controls["controls"]]}
    controls.extend(executed[name] for name in ids[16:33])
    controls.append(_require_rejections(ids[33], [lambda: smp_preempt.file_binding(ROOT, "../outside")]))
    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSCHED6 negative-control order diverged")
    case_count = sum(item["case_count"] for item in controls)
    if case_count != HOSTILE_CASE_COUNT:
        raise QualificationError(f"PKSCHED6 hostile-case count changed: {case_count}")
    if controls != smp_preempt.expected_controls():
        raise QualificationError("PKSCHED6 exact control accounting diverged")
    return controls


def make_readiness(
    toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int
) -> dict[str, Any]:
    contract = smp_preempt.read_json(ROOT / smp_preempt.CONTRACT_RELATIVE)
    errors = smp_preempt.contract_errors(contract, ROOT)
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
    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pksched6-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        native_controls = _run_native_control_probe(toolchain_root, temporary_root / "native-controls")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "default-boot")
        preempt_boot, preempt_build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root / "scheduler-smp-preempt-boot", development_feature=smp_preempt.FEATURE)
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot transfer isolation failed")
        if smp_preempt.sha256_bytes(default_boot) == smp_preempt.sha256_bytes(preempt_boot):
            raise QualificationError("default and PKSCHED6 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        texts = {name: (ROOT / value["path"]).read_text(encoding="utf-8") for name, value in source_audit["files"].items()}
        audit_controls = {"scope": "mutated_AP_register_and_cleanup_source_not_hardware_fault_injection",
                          "files": source_audit["files"], "controls": _source_controls(texts)}
        linked_invlpg_audit = qualify_native_kernel_smp_ipi._linked_invlpg_audit(toolchain_root, kernel, temporary_root / "linked-audit")
        media_one = native_kernel_load.build_media_bytes(preempt_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(preempt_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKSCHED6 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksched6.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pksched6-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"scheduler-smp-preempt-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=smp_preempt.validate_markers,
                        marker_extractor=smp_preempt.extract_markers,
                        completion_marker=smp_preempt.COMPLETION_MARKER,
                    )
                except (qualify_native_pooleboot.QualificationError, smp_preempt.KernelSchedulerSmpPreemptError) as error:
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
        normalized = [smp_preempt.normalize_dynamic_markers(run["markers"]) for run in runs]
        if normalized[0] != normalized[1]:
            raise QualificationError("two PKSCHED6 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSCHED6 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSCHED6 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"], host_probe["lines"], native_controls, audit_controls)
    observation = smp_preempt.validate_markers(runs[0]["markers"])
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_scheduler_smp_preempt_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_sandybridge_four_vcpu_ack_gated_preemption_non_promoting",
        "contract_id": smp_preempt.CONTRACT_ID,
        "selected_move_id": smp_preempt.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "flag_n12_sched_smp_preempt_001_closed": True,
        "phase_status": {"N12": "partial", "N12.1": "partial", "N12.2": "partial", "N12.3": "partial", "N12.4": "partial", "N12.5": "partial", "N12.6": "partial", "N12.7": "partial"},
        "inputs": smp_preempt.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "scheduler_smp_preempt_pooleboot": preempt_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "host_probe": host_probe,
            "native_control_probe": native_controls,
            "audit_controls": audit_controls,
            "source_audit": source_audit,
            "linked_invlpg_audit": linked_invlpg_audit,
        },
        "media": {"clean_generation_count": 2, "exact_clean_generation_match": True, "sha256": smp_preempt.sha256_bytes(media_one), "byte_count": len(media_one), "inspection": media_inspection, "ordinary_workspace_file_only": True, "physical_media_write_performed": False},
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "sandybridge-four-vcpu-ack-gated-smp-preemption",
            "machine": "pc-q35-11.0",
            "cpu_model": "SandyBridge,-avx",
            "virtual_cpu_count": 4,
            "application_processor_count": 3,
            "timer_lane_count": 4,
            "frame_lane_count": 4,
            "live_reschedule_ipi_count": 8,
            "acceleration": "tcg_multi_thread",
            "deterministic_instruction_clock": False,
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
    errors = smp_preempt.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--status-date", default="2026-08-12")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
    _write_json(args.out.resolve(), report)
    print(
        "PKSCHED6 qualification passed: "
        f"runs={report['execution']['run_count']}/2; "
        f"kernel_tests={report['build']['kernel_entry']['host_tests']['test_count']}; "
        f"negative={len(report['negative_controls'])}; hostile={HOSTILE_CASE_COUNT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
