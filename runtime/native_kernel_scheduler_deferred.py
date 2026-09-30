"""Independent PKSCHED3 deferred-work and live-marker oracle."""

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


CONTRACT_ID = "PKSCHED3"
SELECTED_MOVE_ID = "N12-SCHED-DEFERRED-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-scheduler-deferred-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-deferred-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-scheduler-deferred-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-deferred-readiness.schema.json"
FEATURE = "development-scheduler-deferred"
SELECTOR = 17
MARKER_COUNT = 37
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SCHED-DEFERRED-RESULT PASS contract=PKSCHED3"

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
    "native/kernel/src/scheduler.rs",
    "native/kernel/src/scheduler_preempt.rs",
    "native/kernel/src/scheduler_deferred.rs",
    "native/kernel/src/bin/pksched3_probe.rs",
    "runtime/native_kernel_scheduler_deferred.py",
    "specs/native-kernel-scheduler-deferred-contract.json",
    "specs/native-kernel-scheduler-deferred-contract.schema.json",
    "specs/native-kernel-scheduler-deferred-readiness.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_scheduler_deferred.py",
    "tests/test_native_kernel_scheduler_deferred.py",
    "tests/test_native_deferred_controls.py",
    "tests/fixtures/pksched3_control_probe.rs",
    "docs/native-kernel-scheduler-deferred.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKSCHED3-MARKER-OMISSION",
    "NEG-N12-PKSCHED3-MARKER-ORDER",
    "NEG-N12-PKSCHED3-MARKER-DUPLICATE",
    "NEG-N12-PKSCHED3-SELECTOR",
    "NEG-N12-PKSCHED3-ARM-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-QUEUE-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-WORK-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-FLUSH-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-FAULT-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-CLEANUP-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-PROBE-OMISSION",
    "NEG-N12-PKSCHED3-PROBE-ORDER",
    "NEG-N12-PKSCHED3-PROBE-FIELD-MATRIX",
    "NEG-N12-PKSCHED3-INDEPENDENT-ORACLE",
    "NEG-N12-PKSCHED3-FIXED-CAPACITY",
    "NEG-N12-PKSCHED3-DUPLICATE-SUPPRESSION",
    "NEG-N12-PKSCHED3-TOP-HALF-CONTEXT",
    "NEG-N12-PKSCHED3-RECURSION",
    "NEG-N12-PKSCHED3-EOI-PERMIT",
    "NEG-N12-PKSCHED3-PRIORITY-BYPASS",
    "NEG-N12-PKSCHED3-QUEUED-CANCEL",
    "NEG-N12-PKSCHED3-RUNNING-CANCEL",
    "NEG-N12-PKSCHED3-FLUSH-WATERMARK",
    "NEG-N12-PKSCHED3-STALE-GENERATION",
    "NEG-N12-PKSCHED3-FAULT-ROLLBACK",
    "NEG-N12-PKSCHED3-SHUTDOWN-ORDER",
    "NEG-N12-PKSCHED3-NO-HEAP-OR-CALLBACK",
    "NEG-N12-PKSCHED3-WORKER-STACK-OWNERSHIP",
    "NEG-N12-PKSCHED3-INPUT-BINDING",
)

NATIVE_CONTROL_CASE_COUNTS = (3, 4, 5, 2, 5, 5, 3, 4, 4, 5, 5, 5)
NEGATIVE_CONTROL_CASE_COUNTS = (
    37, 36, 37, 1, 12, 7, 9, 8, 8, 12, 13, 5, 2, 5, 1,
    *NATIVE_CONTROL_CASE_COUNTS, 6, 4, 1,
)
NATIVE_CONTROL_SOURCES = (
    "tests/fixtures/pksched3_control_probe.rs", "native/kernel/src/scheduler_deferred.rs",
)
SOURCE_AUDIT_PATHS = {
    "deferred": "native/kernel/src/scheduler_deferred.rs",
    "arch": "native/kernel/src/arch/x86_64.rs",
    "main": "native/kernel/src/main.rs",
    "boot_exit": "native/boot/src/exit.rs",
    "boot_manifest": "native/boot/Cargo.toml",
    "bootexit": "native/bootexit/src/lib.rs",
    "pooleboot_qualifier": "tools/qualify_native_pooleboot.py",
}


def expected_controls() -> list[dict[str, Any]]:
    return [{"id": control_id, "status": "pass",
             "expected": "boundary_verified" if 15 <= index < 27 else "rejected", "case_count": count}
            for index, (control_id, count) in enumerate(zip(NEGATIVE_CONTROL_IDS, NEGATIVE_CONTROL_CASE_COUNTS))]


def parse_native_control_output(output: str) -> list[dict[str, Any]]:
    """Counts describe executed scenarios, including transition invariants, not only Err returns."""
    lines = output.splitlines()
    _require(len(lines) == 12, "PKSCHED3 native control receipt count changed")
    for line, control_id, count in zip(lines, NEGATIVE_CONTROL_IDS[15:27], NATIVE_CONTROL_CASE_COUNTS):
        _require(line == f"PKSCHED3:CONTROL PASS id={control_id} cases={count} verified={count}",
                 "PKSCHED3 native control evidence changed")
    return expected_controls()[15:27]

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-EARLY PASS contract=PKSCHED3 selector=(?P<selector>[0-9]+) "
    r"parent_scheduler=PKSCHED2 parent_timer=PKIRQ1 bsp=(?P<bsp>[01]) if=(?P<iflag>[01]) "
    r"stack=validated_by_wrapper serial=initialized$"
)
ARM = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-ARM PASS contract=PKSCHED3 timer_vector=(?P<vector>[0-9]+) "
    r"one_shot_count=(?P<count>[0-9]+) apic_ticks_per_second=(?P<frequency>[0-9]+) "
    r"capacity=(?P<capacity>[0-9]+) workers=(?P<workers>[0-9]+) stack_bytes=(?P<stack_bytes>[0-9]+) "
    r"enqueue_batch=(?P<batch>[0-9]+) duplicate_attempts=(?P<duplicates>[0-9]+) "
    r"queued_cancel=(?P<queued_cancel>[0-9]+) operation_tokens=(?P<tokens>[a-z]+) "
    r"handler_if=(?P<handler_if>[01]) interrupted_if=(?P<interrupted_if>[01])$"
)
QUEUE = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-QUEUE PASS contract=PKSCHED3 "
    r"top_half_enqueued=(?P<enqueued>[0-9]+) duplicate_suppressed=(?P<duplicate>[0-9]+) "
    r"queue_trace=(?P<trace>[HN0-9,]+) queued_cancelled=(?P<cancelled>[0-9]+) "
    r"eois=(?P<eois>[0-9]+) dispatch_before_eoi=(?P<before_eoi>[0-9]+) permit_epoch=(?P<epoch>[0-9]+)$"
)
WORK = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-WORK PASS contract=PKSCHED3 "
    r"dispatch_trace=(?P<trace>[0-9:,]+) completed=(?P<completed>[0-9]+) cancelled=(?P<cancelled>[0-9]+) "
    r"running_cancel=(?P<running_cancel>[0-9]+) recursion_rejected=(?P<recursion>[0-9]+) "
    r"high_bypass=(?P<bypass>[0-9]+) worker_entries=(?P<entries>[0-9,]+) "
    r"transitions=(?P<transitions>[0-9]+) arbitrary_callbacks=(?P<callbacks>[0-9]+)$"
)
FLUSH = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-FLUSH PASS contract=PKSCHED3 watermark=(?P<watermark>[0-9]+) "
    r"complete=(?P<complete>[01]) sum_lane=(?P<sum>[0-9]+) xor_lane=(?P<xor>[0-9]+) "
    r"fence_lane=(?P<fence>[0-9]+) receipts=(?P<receipts>[0-9]+) stale_rejected=(?P<stale>[0-9]+) "
    r"generation_safe=(?P<generation>[01])$"
)
FAULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-FAULT PASS contract=PKSCHED3 rollbacks=(?P<rollbacks>[0-9]+) "
    r"reserve=(?P<reserve>[0-9]+) queue=(?P<queue>[0-9]+) execute=(?P<execute>[0-9]+) "
    r"commit=(?P<commit>[0-9]+) cleanup=(?P<cleanup>[0-9]+) invariant=(?P<invariant>[01]) "
    r"leaked_slots=(?P<leaked>[0-9]+)$"
)
CLEANUP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-CLEANUP PASS contract=PKSCHED3 intake_closed=(?P<intake>[01]) "
    r"shutdown_cancelled=(?P<shutdown_cancelled>[0-9]+) slots_free=(?P<free>[0-9]+) "
    r"workers_retired=(?P<workers>[0-9]+) stack_bytes_cleared=(?P<cleared>[0-9]+) "
    r"queue_entries=(?P<queued>[0-9]+) running=(?P<running>[0-9]+) lock_released=(?P<lock>[01]) "
    r"apic_restored=(?P<apic>[01]) pic_restored=(?P<pic>[01]) hpet_restored=(?P<hpet>[01]) "
    r"mmio_revoked=(?P<mmio>[01])$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-DEFERRED-RESULT PASS contract=PKSCHED3 "
    r"profile=(?P<profile>qemu64_bsp_interrupt_deferred) fixed_workers=(?P<fixed>[01]) "
    r"bsp=(?P<bsp>[01]) ap_dispatch=(?P<ap>[01]) drivers=(?P<drivers>[01]) services=(?P<services>[01]) "
    r"ring3=(?P<ring3>[01]) address_spaces=(?P<spaces>[0-9]+) xstate_switch=(?P<xstate>[01]) "
    r"target=(?P<target>[01]) signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) "
    r"actions=(?P<actions>[0-9]+) production=(?P<production>[01]) terminal=(?P<terminal>halt)$"
)

PROBE_QUEUE = re.compile(
    r"^PKSCHED3:QUEUE PASS enqueued=(?P<enqueued>[0-9]+) duplicate=(?P<duplicate>[0-9]+) "
    r"queued_cancelled=(?P<cancelled>[0-9]+) eoi=(?P<eoi>[0-9]+) pending=(?P<pending>[0-9]+) "
    r"flush_before=(?P<flush>[01])$"
)
PROBE_WORK = re.compile(
    r"^PKSCHED3:WORK PASS slots=(?P<slots>[0-9,]+) workers=(?P<workers>[0-9,]+) "
    r"states=(?P<states>[a-z,]+) max_bypass=(?P<bypass>[0-9]+)$"
)
PROBE_FLUSH = re.compile(
    r"^PKSCHED3:FLUSH PASS watermark=(?P<watermark>[0-9]+) completion=(?P<completion>[0-9]+) "
    r"sum=(?P<sum>[0-9]+) xor=(?P<xor>[0-9]+) fence=(?P<fence>[0-9]+) "
    r"completed=(?P<completed>[0-9]+) cancelled=(?P<cancelled>[0-9]+) "
    r"running_cancel=(?P<running_cancel>[0-9]+) retired=(?P<retired>[0-9]+) free=(?P<free>[0-9]+)$"
)
PROBE_FAULT = re.compile(
    r"^PKSCHED3:FAULT PASS rollbacks=(?P<rollbacks>[0-9]+) free=(?P<free>[0-9]+) valid=(?P<valid>[01])$"
)
PROBE_BOUNDARY = re.compile(
    r"^PKSCHED3:BOUNDARY PASS pre_eoi_rejected=(?P<pre_eoi>[01]) recursion_rejected=(?P<recursion>[01]) "
    r"stale_rejected=(?P<stale>[01]) intake_rejected=(?P<intake>[01]) arbitrary_callbacks=(?P<callbacks>[0-9]+)$"
)


class KernelSchedulerDeferredError(RuntimeError):
    """Raised when PKSCHED3 evidence violates its bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSchedulerDeferredError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKSCHED3 {label} violates its contract")
    assert match is not None
    return match


def _numbers(value: str) -> tuple[int, ...]:
    return tuple(int(item, 10) for item in value.split(","))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSchedulerDeferredError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelSchedulerDeferredError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_deferred_work_implemented": True,
        "generation_safe_work_identity_implemented": True,
        "interrupt_top_half_enqueue_verified": True,
        "eoi_before_worker_dispatch_verified": True,
        "two_private_bsp_worker_stacks_verified": True,
        "duplicate_cancellation_flush_shutdown_verified": True,
        "bounded_priority_bypass_verified": True,
        "fault_rollback_and_reclamation_verified": True,
        "arbitrary_kernel_callbacks_implemented": False,
        "driver_or_service_async_consumers_implemented": False,
        "live_ap_scheduler_dispatch_implemented": False,
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
        return ["PKSCHED3 readiness is not an object"]
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
        _typed_equal(readiness.get("phase_status"), {name: "partial" for name in ("N12", *(f"N12.{i}" for i in range(1, 8)))}, "phase status")
        _typed_equal(readiness.get("status"), "pass_single_host_two_run_qemu64_bsp_interrupt_deferred_workers_non_promoting", "qualification status")
    except (KernelSchedulerDeferredError, TypeError, ValueError) as error:
        errors.append(str(error))
    if errors:
        return errors
    errors.extend(recorded_deferred_errors(readiness.get("execution"), readiness.get("observation"), readiness["build"], root))
    return errors


def _typed_equal(actual: Any, expected: Any, label: str) -> None:
    _require(json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False),
             f"recorded {label} differs from parsed evidence or exact types")


def recorded_deferred_errors(execution: Any, observation: Any, build: Any, root: Path = ROOT) -> list[str]:
    """Reconstruct recorded consistency; this does not authenticate or freshly execute evidence."""
    if not isinstance(execution, dict):
        return ["PKSCHED3 recorded execution is not an object"]

    def parsed(markers: list[str]) -> dict[str, Any]:
        try:
            return validate_markers(markers)
        except KernelSchedulerDeferredError as error:
            raise ValueError(str(error)) from error

    pair = dict(execution, exact_marker_match=execution.get("static_markers_exact_match"))
    try:
        errors = recorded_pair_errors(pair, "scheduler-deferred-run", parsed, CONTRACT_ID)
    except (native_kernel_transfer.KernelTransferError, KeyError, TypeError, ValueError, AttributeError) as error:
        return [f"PKSCHED3 recorded run evidence is invalid: {error}"]
    if errors:
        return errors
    try:
        for key, expected in (("host_environment_count", 1), ("virtual_cpu_count", 1),
                              ("bsp_only", True), ("dynamic_fields_revalidated", True),
                              ("deterministic_instruction_clock", True), ("cpu_model", "qemu64"),
                              ("acceleration", "tcg_single_thread"), ("profile_id", "POOLEOS-TIER0-Q35-1"),
                              ("machine", "pc-q35-11.0")):
            _typed_equal(execution.get(key), expected, "execution " + key)
        _typed_equal(observation, parsed(execution["runs"][0]["markers"]), "observation")
        host = build["host_probe"]
        lines = host["lines"]
        _require(isinstance(lines, list) and len(lines) == 5 and all(isinstance(line, str) for line in lines),
                 "recorded host probe lines are malformed")
        output = "\n".join(lines) + "\n"
        _typed_equal(host, dict(parse_probe_output(output), output_sha256=sha256_bytes(output.encode("utf-8"))), "host probe")
        native = build["native_control_probe"]
        lines = native["lines"]
        _require(isinstance(lines, list) and all(isinstance(line, str) for line in lines), "native control lines are malformed")
        output = "\n".join(lines) + "\n"
        controls = parse_native_control_output(output)
        _require(isinstance(native["executable_sha256"], str) and re.fullmatch(r"[0-9A-F]{64}", native["executable_sha256"]) is not None,
                 "native control executable digest is malformed")
        _typed_equal(native, {
            "scope": "host_execution_of_native_deferred_module_not_privileged_guest_execution",
            "exit_code": 0, "lines": lines, "output_sha256": sha256_bytes(output.encode("utf-8")),
            "executable_sha256": native["executable_sha256"], "controls": controls,
            "verified_cases_total": sum(NATIVE_CONTROL_CASE_COUNTS),
            "sources": [file_binding(root, path) for path in NATIVE_CONTROL_SOURCES],
        }, "native control probe")
        source, linked, audit = build["source_audit"], build["linked_switch_audit"], build["audit_controls"]
        for key, value in (("focused_rust_test_count", 7), ("fixed_work_capacity", 8), ("worker_count", 2),
                           ("worker_stack_bytes_each", 16384), ("allocation_free_controller", True),
                           ("arbitrary_callback_count", 0), ("live_marker_count", 37)):
            _typed_equal(source.get(key), value, "source audit " + key)
        maximum = re.search(r"MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = (\d+);", (root / SOURCE_AUDIT_PATHS["bootexit"]).read_text(encoding="utf-8"))
        _require(maximum is not None, "development selector bound is missing")
        _typed_equal(source.get("max_development_trap_scenario"), int(maximum.group(1)), "selector maximum")
        files = {name: {key: value for key, value in file_binding(root, path).items() if key != "byte_count"}
                 for name, path in SOURCE_AUDIT_PATHS.items()}
        _typed_equal(source.get("files"), files, "source audit files")
        for key, value in (("instruction_count", 18), ("scope_byte_count", 36), ("forbidden_instruction_count", 0),
                           ("status", "pass"), ("end_symbol_verified", True)):
            _typed_equal(linked.get(key), value, "linked audit " + key)
        for key in ("canonical_sha256", "canonical_byte_count", "linked_sha256", "linked_byte_count", "relocation_count"):
            _typed_equal(linked.get(key), build["kernel_entry"]["product"][key], "linked product " + key)
        _typed_equal(linked.get("scope"), "poole_scheduler_context_switch..poole_scheduler_context_switch_end", "linked scope")
        _typed_equal(linked.get("mnemonics"), ["pushfq", *(["pushq"] * 6), "movq", "incq", "movq", *(["popq"] * 6), "popfq", "retq"], "linked instructions")
        for key in ("start_address", "end_address"):
            _require(isinstance(linked.get(key), str) and re.fullmatch(r"0x[0-9A-F]{16}", linked[key]) is not None,
                     "linked symbol address is malformed")
        _require(int(linked["end_address"], 16) - int(linked["start_address"], 16) == 36, "linked symbol extent changed")
        tool_path = ".toolchains/rust-1.97.0/rustup/toolchains/1.97.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/llvm-objdump.exe"
        _typed_equal(linked.get("llvm_objdump_path"), tool_path, "linked tool path")
        _typed_equal(linked.get("llvm_objdump_sha256"), sha256_bytes((root / tool_path).read_bytes()), "linked tool digest")
        _typed_equal(audit, {
            "scope": "mutated_heap_callback_and_stack_guard_source_not_hardware_fault_injection",
            "files": files, "controls": expected_controls()[27:29],
        }, "source audit controls")
    except (KernelSchedulerDeferredError, KeyError, TypeError, ValueError, AttributeError, OSError) as error:
        return [f"PKSCHED3 recorded accounting is invalid: {error}"]
    return []


def trace_oracle() -> dict[str, Any]:
    queue = [
        {"slot": 0, "priority": "H", "op": ("add", 10)},
        {"slot": 1, "priority": "N", "op": ("xor", 90)},
        {"slot": 2, "priority": "H", "op": ("add", 20)},
        {"slot": 4, "priority": "H", "op": ("add", 40)},
        {"slot": 5, "priority": "N", "op": ("add", 50)},
        {"slot": 6, "priority": "N", "op": ("fence", 7)},
        {"slot": 7, "priority": "N", "op": ("add", 60)},
    ]
    slots: list[int] = []
    workers: list[int] = []
    states: list[str] = []
    high_bypass = 0
    maximum_bypass = 0
    sum_lane = 0
    xor_lane = 0
    fence_lane = 0
    for worker in (0, 1, 0, 1, 0, 1):
        high = next((item for item in queue if item["priority"] == "H"), None)
        normal = next((item for item in queue if item["priority"] == "N"), None)
        if high is not None and normal is not None and high_bypass < 3:
            item = high
            high_bypass += 1
            maximum_bypass = max(maximum_bypass, high_bypass)
        elif high is not None and normal is None:
            item = high
            high_bypass = 0
        else:
            assert normal is not None
            item = normal
            high_bypass = 0
        queue.remove(item)
        slots.append(int(item["slot"]))
        workers.append(worker)
        operation, value = item["op"]
        if operation == "fence":
            states.append("cancelled")
            continue
        states.append("completed")
        if operation == "add":
            sum_lane += int(value)
        else:
            xor_lane ^= int(value)
    return {
        "slots": tuple(slots),
        "workers": tuple(workers),
        "states": tuple(states),
        "max_bypass": maximum_bypass,
        "sum": sum_lane,
        "xor": xor_lane,
        "fence": fence_lane,
        "remaining_slots": tuple(int(item["slot"]) for item in queue),
    }


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.replace("\r\n", "\n").splitlines() if line.startswith("PKSCHED3:")]
    _require(len(lines) == 5, "PKSCHED3 host probe line count changed")
    queue = _match(PROBE_QUEUE, lines[0], "queue probe")
    work = _match(PROBE_WORK, lines[1], "work probe")
    flush = _match(PROBE_FLUSH, lines[2], "flush probe")
    fault = _match(PROBE_FAULT, lines[3], "fault probe")
    boundary = _match(PROBE_BOUNDARY, lines[4], "boundary probe")
    oracle = trace_oracle()
    _require(tuple(int(queue.group(name), 10) for name in ("enqueued", "duplicate", "cancelled", "eoi", "pending", "flush")) == (8, 1, 1, 1, 7, 0), "queue probe changed")
    _require(_numbers(work.group("slots")) == oracle["slots"], "Rust slots diverge from Python oracle")
    _require(_numbers(work.group("workers")) == oracle["workers"], "Rust workers diverge from Python oracle")
    _require(tuple(work.group("states").split(",")) == oracle["states"], "Rust states diverge from Python oracle")
    _require(int(work.group("bypass"), 10) == oracle["max_bypass"], "priority bypass changed")
    _require(tuple(int(flush.group(name), 10) for name in ("watermark", "completion", "sum", "xor", "fence", "completed", "cancelled", "running_cancel", "retired", "free")) == (8, 8, 120, 90, 0, 5, 3, 1, 8, 8), "flush probe changed")
    _require(tuple(int(fault.group(name), 10) for name in ("rollbacks", "free", "valid")) == (5, 8, 1), "fault probe changed")
    _require(tuple(int(boundary.group(name), 10) for name in ("pre_eoi", "recursion", "stale", "intake", "callbacks")) == (1, 1, 1, 1, 0), "boundary probe changed")
    return {"lines": lines, "trace": oracle, "receipt_count": 5, "rust_python_exact_agreement": True}


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [
        *markers[:BOOT_TRANSFER_MARKER_COUNT],
        *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT],
    ]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append(
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 "
        "post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSchedulerDeferredError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSCHED3 markers")
    arm_transfer = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm_transfer is not None and int(arm_transfer.group(10), 10) == SELECTOR, "PKSCHED3 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    arm = _match(ARM, markers[30], "arm marker")
    queue = _match(QUEUE, markers[31], "queue marker")
    work = _match(WORK, markers[32], "work marker")
    flush = _match(FLUSH, markers[33], "flush marker")
    fault = _match(FAULT, markers[34], "fault marker")
    cleanup = _match(CLEANUP, markers[35], "cleanup marker")
    result = _match(RESULT, markers[36], "result marker")
    _require(tuple(int(early.group(name), 10) for name in ("selector", "bsp", "iflag")) == (17, 1, 0), "PKSCHED3 early state changed")
    arm_values = tuple(int(arm.group(name), 10) for name in ("vector", "count", "frequency", "capacity", "workers", "stack_bytes", "batch", "duplicates", "queued_cancel", "handler_if", "interrupted_if"))
    _require(arm_values[0] == 64 and arm_values[1] > 0 and arm_values[2] == arm_values[1] * 100, "PKSCHED3 timer calibration changed")
    _require(arm_values[3:] == (8, 2, 16384, 8, 1, 1, 0, 1) and arm.group("tokens") == "fixed", "PKSCHED3 arm geometry changed")
    _require(tuple(int(queue.group(name), 10) for name in ("enqueued", "duplicate", "cancelled", "eois", "before_eoi", "epoch")) == (8, 1, 1, 1, 0, 1), "PKSCHED3 queue receipt changed")
    _require(queue.group("trace") == "H1,N2,H3,H4,H5,N6,N7,N8", "PKSCHED3 queue trace changed")
    oracle = trace_oracle()
    _require(work.group("trace") == "0:0,1:2,0:4,1:1,0:5,1:6", "PKSCHED3 dispatch trace changed")
    _require(tuple(int(work.group(name), 10) for name in ("completed", "cancelled", "running_cancel", "recursion", "bypass", "transitions", "callbacks")) == (5, 2, 1, 1, 3, 12, 0), "PKSCHED3 worker receipt changed")
    _require(_numbers(work.group("entries")) == (3, 3) and oracle["slots"] == (0, 2, 4, 1, 5, 6), "PKSCHED3 worker entry count changed")
    _require(tuple(int(flush.group(name), 10) for name in ("watermark", "complete", "sum", "xor", "fence", "receipts", "stale", "generation")) == (8, 1, 120, 90, 0, 8, 1, 1), "PKSCHED3 flush receipt changed")
    _require(tuple(int(fault.group(name), 10) for name in ("rollbacks", "reserve", "queue", "execute", "commit", "cleanup", "invariant", "leaked")) == (5, 1, 1, 1, 1, 1, 1, 0), "PKSCHED3 fault receipt changed")
    _require(tuple(int(cleanup.group(name), 10) for name in ("intake", "shutdown_cancelled", "free", "workers", "cleared", "queued", "running", "lock", "apic", "pic", "hpet", "mmio")) == (1, 1, 8, 2, 32768, 0, 0, 1, 1, 1, 1, 1), "PKSCHED3 cleanup receipt changed")
    _require(tuple(int(result.group(name), 10) for name in ("fixed", "bsp", "ap", "drivers", "services", "ring3", "spaces", "xstate", "target", "signatures", "authority", "actions", "production")) == (1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0), "PKSCHED3 claim boundary changed")
    return {
        "transfer_prefix": prefix,
        "timer": {"vector": 64, "one_shot_count": arm_values[1], "apic_ticks_per_second": arm_values[2], "deliveries": 1},
        "queue": {"enqueued": 8, "duplicate_suppressed": 1, "queued_cancelled": 1},
        "workers": {"dispatches": 6, "entries": [3, 3], "transitions": 12, "trace": oracle},
        "flush": {"receipts": 8, "sum_lane": 120, "xor_lane": 90, "fence_lane": 0},
        "faults": {"rollbacks": 5, "leaked_slots": 0},
        "cleanup": {"stack_bytes_cleared": 32768, "slots_free": 8, "mmio_revoked": 1},
        "result": {"fixed_bsp_workers": 1, "live_ap_dispatch": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
