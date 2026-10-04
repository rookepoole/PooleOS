"""Independent PKSCHED5 AP-local typed-worker and marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json
from runtime.native_kernel_profile_evidence import kernel_entry_errors, recorded_pair_errors


CONTRACT_ID = "PKSCHED5"
SELECTED_MOVE_ID = "N12-SCHED-AP-WORKERS-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-scheduler-ap-workers-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-ap-workers-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-scheduler-ap-workers-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-ap-workers-readiness.schema.json"
FEATURE = "development-scheduler-ap-workers"
SELECTOR = 19
MARKER_COUNT = 37
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SCHED-AP-WORK-RESULT PASS contract=PKSCHED5"

IMPLEMENTATION_INPUTS = (
    "runtime/native_kernel_profile_evidence.py",
    "tests/test_native_memory_entry_provenance.py",
    "runs/native_kernel_entry_readiness.json",
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/scheduler_ap_workers.rs",
    "native/kernel/src/smp_ipi.rs",
    "native/kernel/src/smp_runtime.rs",
    "native/kernel/src/bin/pksched5_probe.rs",
    "runtime/native_kernel_scheduler_ap_workers.py",
    "specs/native-kernel-scheduler-ap-workers-contract.json",
    "specs/native-kernel-scheduler-ap-workers-contract.schema.json",
    "specs/native-kernel-scheduler-ap-workers-readiness.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_scheduler_ap_workers.py",
    "tests/test_native_kernel_scheduler_ap_workers.py",
    "tests/test_native_ap_worker_controls.py",
    "tests/fixtures/pksched5_control_probe.rs",
    "docs/native-kernel-scheduler-ap-workers.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKSCHED5-MARKER-OMISSION",
    "NEG-N12-PKSCHED5-MARKER-ORDER",
    "NEG-N12-PKSCHED5-MARKER-DUPLICATE",
    "NEG-N12-PKSCHED5-SELECTOR",
    "NEG-N12-PKSCHED5-TOPOLOGY-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-QUEUE-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-DISPATCH-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-CANCEL-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-FLUSH-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-CLEANUP-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-PROBE-OMISSION",
    "NEG-N12-PKSCHED5-PROBE-ORDER",
    "NEG-N12-PKSCHED5-PROBE-FIELD-MATRIX",
    "NEG-N12-PKSCHED5-INDEPENDENT-ORACLE",
    "NEG-N12-PKSCHED5-TYPED-CALL-ALLOWLIST",
    "NEG-N12-PKSCHED5-ARBITRARY-CALLBACK",
    "NEG-N12-PKSCHED5-TOP-HALF-CONTEXT",
    "NEG-N12-PKSCHED5-DISPATCH-BEFORE-EOI",
    "NEG-N12-PKSCHED5-DUPLICATE-WORK",
    "NEG-N12-PKSCHED5-QUEUED-CANCEL",
    "NEG-N12-PKSCHED5-REMOTE-CANCEL",
    "NEG-N12-PKSCHED5-ACK-BINDING",
    "NEG-N12-PKSCHED5-OFFLINE-TIMEOUT",
    "NEG-N12-PKSCHED5-SOURCE-QUEUE-ROLLBACK",
    "NEG-N12-PKSCHED5-LATE-ACK",
    "NEG-N12-PKSCHED5-FAIRNESS-BOUND",
    "NEG-N12-PKSCHED5-FLUSH-WATERMARK",
    "NEG-N12-PKSCHED5-RECLAIM-GENERATION",
    "NEG-N12-PKSCHED5-STALE-ID",
    "NEG-N12-PKSCHED5-IST1-STACK-GATE",
    "NEG-N12-PKSCHED5-AP-REGISTER-RESTORE",
    "NEG-N12-PKSCHED5-PARK-SCRUB-RELEASE",
    "NEG-N12-PKSCHED5-INPUT-BINDING",
)

NATIVE_CONTROL_INDICES = (15, *range(17, 30))
NATIVE_CONTROL_CASE_COUNTS = (8, 5, 4, 3, 3, 3, 8, 4, 3, 3, 3, 3, 5, 4)
SOURCE_CONTROL_INDICES = (16, 30, 31, 32)
NEGATIVE_CONTROL_CASE_COUNTS = (
    37, 36, 37, 1, 10, 8, 9, 10, 9, 18, 17, 6, 2, 6, 1,
    8, 6, 5, 4, 3, 3, 3, 8, 4, 3, 3, 3, 3, 5, 4, 5, 35, 12, 1,
)
NATIVE_CONTROL_SOURCES = (
    "tests/fixtures/pksched5_control_probe.rs", "native/kernel/src/scheduler_ap_workers.rs",
    "native/kernel/src/smp_ipi.rs",
)
SOURCE_AUDIT_PATHS = {
    "workers": "native/kernel/src/scheduler_ap_workers.rs",
    "ipi": "native/kernel/src/smp_ipi.rs",
    "runtime": "native/kernel/src/smp_runtime.rs",
    "arch": "native/kernel/src/arch/x86_64.rs",
    "main": "native/kernel/src/main.rs",
    "boot_exit": "native/boot/src/exit.rs",
    "boot_manifest": "native/boot/Cargo.toml",
    "bootexit": "native/bootexit/src/lib.rs",
    "pooleboot_qualifier": "tools/qualify_native_pooleboot.py",
}


def expected_controls() -> list[dict[str, Any]]:
    return [{"id": name, "status": "pass", "expected": "native_boundary_verified" if i in NATIVE_CONTROL_INDICES else "rejected",
             "case_count": count}
            for i, (name, count) in enumerate(zip(NEGATIVE_CONTROL_IDS, NEGATIVE_CONTROL_CASE_COUNTS))]


def parse_native_control_output(output: str) -> list[dict[str, Any]]:
    lines = output.replace("\r\n", "\n").splitlines()
    controls = [expected_controls()[i] for i in NATIVE_CONTROL_INDICES]
    expected = [f"PKSCHED5:CONTROL PASS group={item['id'].removeprefix('NEG-N12-PKSCHED5-')} verified={item['case_count']}" for item in controls]
    _require(lines == expected, "native AP-worker control output is incomplete or divergent")
    return controls

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-EARLY PASS contract=PKSCHED5 selector=(?P<selector>[0-9]+) "
    r"parent_deferred=PKSCHED3 parent_smp=PKSCHED4 parent_ipi=PKSMP5 bsp=(?P<bsp>[01]) "
    r"if=(?P<iflag>[01]) stack=validated_by_wrapper serial=initialized$"
)
TOPOLOGY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-TOPOLOGY PASS contract=PKSCHED5 processors=(?P<processors>[0-9]+) "
    r"enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) target_apic_ids=(?P<targets>[0-9,]+) "
    r"online_mask=(?P<mask>0x[0-9A-F]{16}) workers=(?P<workers>[0-9]+) queues=(?P<queues>[0-9]+) "
    r"capacity=(?P<capacity>[0-9]+) stack_bytes_each=(?P<stack>[0-9]+) stack_gate=(?P<gate>[a-z0-9_]+)$"
)
QUEUE = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-QUEUE PASS contract=PKSCHED5 top_half_enqueued=(?P<enqueued>[0-9]+) "
    r"duplicate_suppressed=(?P<duplicate>[0-9]+) eois=(?P<eois>[0-9]+) "
    r"flush_watermark=(?P<watermark>[0-9]+) queued_cancelled=(?P<queued>[0-9]+) "
    r"driver_consumer=(?P<driver>timer_vector_64) service_consumer=(?P<service>generation_reclaim) "
    r"arbitrary_callbacks=(?P<callbacks>[01])$"
)
DISPATCH = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-DISPATCH PASS contract=PKSCHED5 trace=(?P<trace>[0-9:,;]+) "
    r"worker_entries=(?P<entries>[0-9,]+) call_function_executions=(?P<calls>[0-9]+) "
    r"typed_driver_calls=(?P<drivers>[0-9]+) typed_service_calls=(?P<services>[0-9]+) "
    r"maximum_high_bypass=(?P<bypass>[0-9]+) eoi_balanced=(?P<eoi>[01]) "
    r"registers_restored=(?P<registers>[01]) stack_gate=(?P<gate>[a-z0-9_]+)$"
)
CANCEL = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-CANCEL PASS contract=PKSCHED5 offline_cpu=(?P<cpu>[0-9]+) "
    r"timeouts=(?P<timeouts>[0-9]+) rollbacks=(?P<rollbacks>[0-9]+) queued=(?P<queued>[0-9]+) "
    r"remote_requests=(?P<requests>[0-9]+) remote_completions=(?P<completions>[0-9]+) "
    r"stale_rejections=(?P<stale>[0-9]+) late_ack_rejected=(?P<late>[01]) "
    r"source_queue_restored=(?P<source>[01]) result_discarded=(?P<discarded>[01])$"
)
FLUSH = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-FLUSH PASS contract=PKSCHED5 complete=(?P<complete>[01]) "
    r"completed=(?P<completed>[0-9]+) cancelled=(?P<cancelled>[0-9]+) driver_sum=(?P<sum>[0-9]+) "
    r"service_generation=(?P<generation>[0-9]+) reclaimed=(?P<reclaimed>[0-9]+) "
    r"stale_id_rejected=(?P<stale>[01]) flush_before_reclaim=(?P<ordered>[01]) exact_once=(?P<once>[01])$"
)
CLEANUP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-CLEANUP PASS contract=PKSCHED5 online_after=(?P<online>0x[0-9A-F]{16}) "
    r"workers_retired=(?P<workers>[0-9]+) free=(?P<free>[0-9]+) stack_bytes_cleared=(?P<stack>[0-9]+) "
    r"resource_pages=(?P<resource>[0-9]+) frame_pages=(?P<frames>[0-9]+) total_pages=(?P<total>[0-9]+) "
    r"zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) queues=(?P<queues>[0-9]+) "
    r"dispatching=(?P<dispatching>[0-9]+) terminal=(?P<terminal>[0-9]+) worker_authority_revoked=(?P<worker_auth>[01]) "
    r"capability_revoked=(?P<capability>[01]) runtime_revoked=(?P<runtime>[01]) mmio_revoked=(?P<mmio>[01]) "
    r"pic_restored=(?P<pic>[01]) hpet_restored=(?P<hpet>[01])$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-AP-WORK-RESULT PASS contract=PKSCHED5 profile=(?P<profile>sandybridge_three_ap_typed_workers) "
    r"ap_local_workers=(?P<workers>[01]) driver_consumer=(?P<driver>[01]) service_consumer=(?P<service>[01]) "
    r"remote_cancel=(?P<cancel>[01]) flush=(?P<flush>[01]) reclamation=(?P<reclaim>[01]) "
    r"offline_rollback=(?P<rollback>[01]) arbitrary_callbacks=(?P<callbacks>[01]) general_smp=(?P<general>[01]) "
    r"ring3=(?P<ring3>[01]) address_spaces=(?P<spaces>[0-9]+) target=(?P<target>[01]) "
    r"signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) "
    r"n12_exit=(?P<n12>[01]) production=(?P<production>[01]) terminal=(?P<terminal>halt)$"
)

PROBE_PATTERNS = (
    re.compile(r"^PKSCHED5:TOPOLOGY PASS cpus=(?P<cpus>[0-9]+) aps=(?P<aps>[0-9]+) online_mask=(?P<online>0x[0-9A-F]{2}) ap_mask=(?P<ap>0x[0-9A-F]{2}) workers=(?P<workers>[0-9]+) queues=(?P<queues>[0-9]+) capacity=(?P<capacity>[0-9]+) stack_bytes_each=(?P<stack>[0-9]+)$"),
    re.compile(r"^PKSCHED5:QUEUE PASS enqueued=(?P<enqueued>[0-9]+) duplicate_suppressed=(?P<duplicate>[0-9]+) eoi_epoch=(?P<eoi>[0-9]+) flush_watermark=(?P<watermark>[0-9]+) queued_cancelled=(?P<queued>[0-9]+)$"),
    re.compile(r"^PKSCHED5:DISPATCH PASS trace=(?P<trace>[0-9:,;]+) worker_entries=(?P<entries>[0-9,]+) ap_calls=(?P<calls>[0-9]+) driver_calls=(?P<drivers>[0-9]+) service_calls=(?P<services>[0-9]+) maximum_high_bypass=(?P<bypass>[0-9]+)$"),
    re.compile(r"^PKSCHED5:CANCEL PASS offline_cpu=(?P<cpu>[0-9]+) timeouts=(?P<timeouts>[0-9]+) rollbacks=(?P<rollbacks>[0-9]+) queued=(?P<queued>[0-9]+) remote_requests=(?P<requests>[0-9]+) remote_completions=(?P<completions>[0-9]+) stale_rejections=(?P<stale>[0-9]+) source_queue_restored=(?P<source>[01])$"),
    re.compile(r"^PKSCHED5:FLUSH PASS complete=(?P<complete>[01]) completed=(?P<completed>[0-9]+) cancelled=(?P<cancelled>[0-9]+) driver_sum=(?P<sum>[0-9]+) service_generation=(?P<generation>[0-9]+) reclaimed=(?P<reclaimed>[0-9]+) stale_id_rejected=(?P<stale>[01])$"),
    re.compile(r"^PKSCHED5:CLEANUP PASS online_after=(?P<online>0x[0-9A-F]{2}) workers_retired=(?P<workers>[0-9]+) free=(?P<free>[0-9]+) queued=(?P<queued>[0-9]+) dispatching=(?P<dispatching>[0-9]+) terminal=(?P<terminal>[0-9]+) stack_bytes_cleared=(?P<stack>[0-9]+) valid=(?P<valid>[01])$"),
)


class KernelSchedulerApWorkersError(RuntimeError):
    """Raised when PKSCHED5 evidence violates its bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSchedulerApWorkersError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKSCHED5 {label} violates its contract")
    assert match is not None
    return match


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSchedulerApWorkersError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelSchedulerApWorkersError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_ap_local_deferred_workers_implemented": True,
        "three_private_guarded_worker_stacks_verified": True,
        "typed_timer_driver_consumer_verified": True,
        "typed_generation_reclaim_service_verified": True,
        "live_remote_cancellation_verified": True,
        "flush_gated_generation_reclamation_verified": True,
        "offline_timeout_and_source_rollback_verified": True,
        "bounded_priority_starvation_verified": True,
        "complete_worker_park_scrub_release_verified": True,
        "arbitrary_callbacks_implemented": False,
        "general_topology_or_hotplug_implemented": False,
        "general_smp_preemption_implemented": False,
        "ring3_or_address_space_switch_implemented": False,
        "physical_target_tested": False,
        "n12_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    issues = validate_json(contract, read_json(root / CONTRACT_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("required negative controls diverge")
    if contract.get("claims") != expected_claims():
        errors.append("claim boundary diverges")
    if contract.get("production_ready") is not False or contract.get("production_promotion_allowed") is not False:
        errors.append("contract overclaims production")
    return errors


def readiness_errors(readiness: Any, root: Path = ROOT) -> list[str]:
    if not isinstance(readiness, dict):
        return ["PKSCHED5 readiness is not an object"]
    issues = validate_json(readiness, read_json(root / READINESS_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    errors.extend(kernel_entry_errors(readiness.get("build"), root))
    status_date = readiness.get("status_date")
    try:
        if not isinstance(status_date, str) or len(status_date) != 10 or date.fromisoformat(status_date).isoformat() != status_date:
            raise ValueError("noncanonical date")
    except ValueError:
        errors.append("readiness status_date is not a canonical calendar date")
    if errors:
        return errors
    try:
        _typed_equal(readiness.get("inputs"), expected_inputs(root), "input bindings")
        _typed_equal(readiness.get("negative_controls"), expected_controls(), "per-control accounting")
        _typed_equal(readiness.get("claims"), expected_claims(), "claim boundary")
        _typed_equal(readiness.get("nonclaims"), read_json(root / CONTRACT_RELATIVE)["nonclaims"], "nonclaims")
        _typed_equal(readiness.get("phase_status"), {n: "partial" for n in ("N12", *(f"N12.{i}" for i in range(1, 8)))}, "phase status")
        _typed_equal(readiness.get("status"), "pass_single_host_two_run_sandybridge_four_vcpu_typed_ap_workers_non_promoting", "status")
    except (KernelSchedulerApWorkersError, TypeError, ValueError) as error:
        errors.append(str(error))
    if errors:
        return errors
    errors.extend(recorded_worker_errors(readiness["execution"], readiness["observation"], readiness["build"], root))
    return errors


def _typed_equal(actual: Any, expected: Any, label: str) -> None:
    _require(json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False),
             f"recorded {label} differs from parsed evidence or exact types")


def recorded_worker_errors(execution: Any, observation: Any, build: Any, root: Path = ROOT) -> list[str]:
    """Reconstruct recorded consistency without inferring freshness or authenticity."""
    if not isinstance(execution, dict):
        return ["PKSCHED5 recorded execution is not an object"]

    def parsed(markers):
        try:
            return validate_markers(markers)
        except KernelSchedulerApWorkersError as error:
            raise ValueError(str(error)) from error

    pair = dict(execution, exact_marker_match=execution.get("static_markers_exact_match"))
    try:
        errors = recorded_pair_errors(pair, "scheduler-ap-workers-run", parsed, CONTRACT_ID)
        if errors:
            return errors
        for key, expected in (("host_environment_count", 1), ("virtual_cpu_count", 4),
                              ("application_processor_count", 3), ("worker_count", 3),
                              ("dynamic_fields_revalidated", True), ("deterministic_instruction_clock", False),
                              ("cpu_model", "SandyBridge,-avx"), ("acceleration", "tcg_multi_thread"),
                              ("machine", "pc-q35-11.0"), ("profile_id", "sandybridge-four-vcpu-typed-ap-workers")):
            _typed_equal(execution.get(key), expected, "execution " + key)
        _require("bsp_only" not in execution, "AP-worker profile cannot declare BSP-only execution")
        lock = read_json(root / "specs/native-tier0-lock.json")
        firmware = {item["role"]: item for item in lock["firmware"]["files"]}
        for key, digest in (("qemu_sha256", lock["windows_runner"]["qemu_system_x86_64"]["sha256"]),
                            ("firmware_code_sha256", firmware["debug_code_read_only"]["sha256"]),
                            ("vars_template_sha256", firmware["vars_template_copy_only"]["sha256"])):
            _typed_equal(execution.get(key), digest, "execution " + key)
        _typed_equal(observation, parsed(execution["runs"][0]["markers"]), "observation")
        host = build["host_probe"]
        lines = host["lines"]
        _require(isinstance(lines, list) and len(lines) == 6 and all(isinstance(s, str) for s in lines), "host probe lines malformed")
        output = "\n".join(lines) + "\n"
        _typed_equal(host, dict(parse_probe_output(output), output_sha256=sha256_bytes(output.encode("utf-8"))), "host probe")
        native = build["native_control_probe"]
        lines = native["lines"]
        _require(isinstance(lines, list) and all(isinstance(s, str) for s in lines), "native control lines malformed")
        output = "\n".join(lines) + "\n"
        controls = parse_native_control_output(output)
        _require(isinstance(native["executable_sha256"], str) and re.fullmatch(r"[0-9A-F]{64}", native["executable_sha256"]) is not None,
                 "native executable digest malformed")
        _typed_equal(native, {
            "scope": "host_execution_of_native_AP_workers_not_privileged_guest_execution",
            "exit_code": 0, "lines": lines, "output_sha256": sha256_bytes(output.encode("utf-8")),
            "executable_sha256": native["executable_sha256"], "controls": controls,
            "verified_cases_total": sum(NATIVE_CONTROL_CASE_COUNTS),
            "sources": [file_binding(root, p) for p in NATIVE_CONTROL_SOURCES],
        }, "native control probe")
        files = {n: {k: v for k, v in file_binding(root, p).items() if k != "byte_count"} for n, p in SOURCE_AUDIT_PATHS.items()}
        maximum = re.search(r"MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = (\d+);", (root / SOURCE_AUDIT_PATHS["bootexit"]).read_text(encoding="utf-8"))
        _require(maximum is not None, "development selector maximum missing")
        _typed_equal(build["source_audit"], {
            "max_development_trap_scenario": int(maximum.group(1)), "focused_rust_test_count": 10,
            "fixed_worker_count": 3, "fixed_work_capacity": 15, "allocation_free_controller": True,
            "typed_consumer_count": 2, "arbitrary_callback_count": 0, "ap_handler_saved_register_count": 15,
            "live_marker_count": MARKER_COUNT, "files": files,
        }, "source audit")
        tool_path = ".toolchains/rust-1.97.0/rustup/toolchains/1.97.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/llvm-objdump.exe"
        _typed_equal(build["linked_invlpg_audit"], {
            "scope": "poole_ap_ipi_trampoline_start..poole_ap_ipi_trampoline_end",
            "invlpg_instruction_count": 2, "remote_shootdown_invlpg_instruction_count": 1,
            "runtime_execution_count": 3, "operand": "(%rax)",
            "successor_profile_invlpg_instruction_count": 1, "successor_profile_operand": "(%rbx)",
            "successor_profile_executed": False, "status": "pass",
            **{key: build["kernel_entry"]["product"][key] for key in (
                "canonical_sha256", "canonical_byte_count", "linked_sha256", "linked_byte_count", "relocation_count")},
            "llvm_objdump_path": tool_path, "llvm_objdump_sha256": sha256_bytes((root / tool_path).read_bytes()),
        }, "linked audit")
        _typed_equal(build["audit_controls"], {
            "scope": "mutated_callback_stack_register_cleanup_source_not_hardware_fault_injection",
            "files": files, "controls": [expected_controls()[i] for i in SOURCE_CONTROL_INDICES],
        }, "source audit controls")
    except (KernelSchedulerApWorkersError, native_kernel_transfer.KernelTransferError, KeyError, TypeError, ValueError, AttributeError, OSError) as error:
        return [f"PKSCHED5 recorded accounting is invalid: {error}"]
    return []


def trace_oracle() -> dict[str, Any]:
    queues = {
        1: [(0, "normal"), (1, "high"), (2, "high"), (3, "high"), (12, "high")],
        2: [(4, "normal"), (5, "high"), (6, "high"), (7, "high")],
        3: [(8, "normal"), (9, "high"), (10, "high"), (11, "high")],
    }
    queues[1] = [item for item in queues[1] if item[0] != 12]
    traces: dict[int, tuple[int, ...]] = {}
    for cpu, queue in queues.items():
        trace: list[int] = []
        bypass = 0
        while queue:
            high = next((item for item in queue if item[1] == "high"), None)
            normal = next((item for item in queue if item[1] == "normal"), None)
            if high is not None and normal is not None and bypass < 2:
                selected = high
                bypass += 1
            elif normal is not None:
                selected = normal
                bypass = 0
            else:
                assert high is not None
                selected = high
            queue.remove(selected)
            trace.append(selected[0])
        traces[cpu] = tuple(trace)
    trace_text = ";".join(",".join(f"{cpu}:{slot}" for slot in traces[cpu]) for cpu in (1, 2, 3))
    return {
        "trace": trace_text,
        "worker_entries": (4, 4, 4),
        "driver_calls": 9,
        "service_calls": 3,
        "driver_sum": 177,
        "service_generation": 4,
        "maximum_high_bypass": 2,
    }


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.replace("\r\n", "\n").splitlines() if line.startswith("PKSCHED5:")]
    _require(len(lines) == 6, "PKSCHED5 host probe line count changed")
    values = [_match(pattern, line, f"probe line {index}") for index, (pattern, line) in enumerate(zip(PROBE_PATTERNS, lines), 1)]
    topology, queue, dispatch, cancel, flush, cleanup = values
    oracle = trace_oracle()
    _require(tuple(int(topology.group(name)) for name in ("cpus", "aps", "workers", "queues", "capacity", "stack")) == (4, 3, 3, 3, 15, 8192), "probe topology changed")
    _require((topology.group("online"), topology.group("ap")) == ("0x0F", "0x0E"), "probe masks changed")
    _require(tuple(int(queue.group(name)) for name in ("enqueued", "duplicate", "eoi", "watermark", "queued")) == (13, 1, 1, 13, 1), "probe queue changed")
    _require(dispatch.group("trace") == oracle["trace"], "Rust AP-worker trace diverges from Python oracle")
    _require(tuple(int(item) for item in dispatch.group("entries").split(",")) == oracle["worker_entries"], "probe worker entries changed")
    _require(tuple(int(dispatch.group(name)) for name in ("calls", "drivers", "services", "bypass")) == (12, 9, 3, 2), "probe dispatch changed")
    _require(tuple(int(cancel.group(name)) for name in ("cpu", "timeouts", "rollbacks", "queued", "requests", "completions", "stale", "source")) == (4, 1, 1, 1, 1, 1, 1, 1), "probe cancellation changed")
    _require(tuple(int(flush.group(name)) for name in ("complete", "completed", "cancelled", "sum", "generation", "reclaimed", "stale")) == (1, 11, 2, 177, 4, 13, 1), "probe flush changed")
    _require(tuple(int(cleanup.group(name)) for name in ("workers", "free", "queued", "dispatching", "terminal", "stack", "valid")) == (3, 15, 0, 0, 0, 24576, 1) and cleanup.group("online") == "0x01", "probe cleanup changed")
    return {"lines": lines, "trace": oracle, "receipt_count": 6, "rust_python_exact_agreement": True}


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [*markers[:BOOT_TRANSFER_MARKER_COUNT], *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT]]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSchedulerApWorkersError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSCHED5 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10)) == SELECTOR, "PKSCHED5 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    topology = _match(TOPOLOGY, markers[30], "topology marker")
    queue = _match(QUEUE, markers[31], "queue marker")
    dispatch = _match(DISPATCH, markers[32], "dispatch marker")
    cancel = _match(CANCEL, markers[33], "cancel marker")
    flush = _match(FLUSH, markers[34], "flush marker")
    cleanup = _match(CLEANUP, markers[35], "cleanup marker")
    result = _match(RESULT, markers[36], "result marker")
    oracle = trace_oracle()
    _require(tuple(int(early.group(name)) for name in ("selector", "bsp", "iflag")) == (19, 1, 0), "PKSCHED5 early state changed")
    _require(tuple(int(topology.group(name)) for name in ("processors", "enabled", "bsp", "workers", "queues", "capacity", "stack")) == (4, 4, 0, 3, 3, 15, 8192), "PKSCHED5 topology changed")
    _require((topology.group("targets"), topology.group("mask"), topology.group("gate")) == ("1,2,3", "0x000000000000000F", "ist1"), "PKSCHED5 topology binding changed")
    _require(tuple(int(queue.group(name)) for name in ("enqueued", "duplicate", "eois", "watermark", "queued", "callbacks")) == (13, 1, 1, 13, 1, 0), "PKSCHED5 queue receipt changed")
    _require(dispatch.group("trace") == oracle["trace"] and tuple(int(item) for item in dispatch.group("entries").split(",")) == oracle["worker_entries"], "PKSCHED5 dispatch trace changed")
    _require(tuple(int(dispatch.group(name)) for name in ("calls", "drivers", "services", "bypass", "eoi", "registers")) == (12, 9, 3, 2, 1, 1) and dispatch.group("gate") == "ist1", "PKSCHED5 dispatch receipt changed")
    _require(tuple(int(cancel.group(name)) for name in ("cpu", "timeouts", "rollbacks", "queued", "requests", "completions", "stale", "late", "source", "discarded")) == (4, 1, 1, 1, 1, 1, 1, 1, 1, 1), "PKSCHED5 cancellation receipt changed")
    _require(tuple(int(flush.group(name)) for name in ("complete", "completed", "cancelled", "sum", "generation", "reclaimed", "stale", "ordered", "once")) == (1, 11, 2, 177, 4, 13, 1, 1, 1), "PKSCHED5 flush receipt changed")
    _require(tuple(int(cleanup.group(name)) for name in ("workers", "free", "stack", "resource", "frames", "total", "zeroed", "verified", "queues", "dispatching", "terminal", "worker_auth", "capability", "runtime", "mmio", "pic", "hpet")) == (3, 15, 24576, 96, 6, 102, 417792, 417792, 0, 0, 0, 1, 1, 1, 1, 1, 1) and cleanup.group("online") == "0x0000000000000001", "PKSCHED5 cleanup receipt changed")
    _require(tuple(int(result.group(name)) for name in ("workers", "driver", "service", "cancel", "flush", "reclaim", "rollback", "callbacks", "general", "ring3", "spaces", "target", "signatures", "authority", "actions", "n12", "production")) == (1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0), "PKSCHED5 claim boundary changed")
    return {
        "transfer_prefix": prefix,
        "topology": {"processor_count": 4, "target_apic_ids": [1, 2, 3], "worker_stack_bytes_each": 8192},
        "queue": {"enqueued": 13, "queued_cancelled": 1, "flush_watermark": 13},
        "dispatch": {"trace": oracle, "call_function_executions": 12, "driver_calls": 9, "service_calls": 3},
        "cancellation": {"queued": 1, "remote": 1, "offline_timeouts": 1, "rollbacks": 1},
        "flush": {"completed": 11, "cancelled": 2, "reclaimed": 13, "driver_sum": 177, "service_generation": 4},
        "cleanup": {"workers_retired": 3, "stack_bytes_cleared": 24576, "pages_released": 102, "bytes_verified": 417792},
        "result": {"bounded_ap_local_workers": 1, "general_smp": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
