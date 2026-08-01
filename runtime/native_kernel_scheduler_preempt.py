"""Independent PKSCHED2 timer/wakeup preemption and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSCHED2"
SELECTED_MOVE_ID = "N12-SCHED-PREEMPT-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-scheduler-preemption-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-preemption-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-scheduler-preemption-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-preemption-readiness.schema.json"
FEATURE = "development-scheduler-preempt"
SELECTOR = 16
MARKER_COUNT = 35
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SCHED-PREEMPT-RESULT PASS contract=PKSCHED2"

IMPLEMENTATION_INPUTS = (
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
    "native/kernel/src/bin/pksched2_probe.rs",
    "native/kmap/src/lib.rs",
    "runtime/native_kernel_map.py",
    "runtime/native_kernel_scheduler_preempt.py",
    "specs/native-kernel-scheduler-preemption-contract.json",
    "specs/native-kernel-scheduler-preemption-contract.schema.json",
    "specs/native-kernel-scheduler-preemption-readiness.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_scheduler_preempt.py",
    "tests/test_native_kernel_scheduler_preempt.py",
    "docs/native-kernel-scheduler-preemption.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKSCHED2-MARKER-OMISSION",
    "NEG-N12-PKSCHED2-MARKER-ORDER",
    "NEG-N12-PKSCHED2-MARKER-DUPLICATE",
    "NEG-N12-PKSCHED2-SELECTOR",
    "NEG-N12-PKSCHED2-ARM-FIELD-MATRIX",
    "NEG-N12-PKSCHED2-TRACE-FIELD-MATRIX",
    "NEG-N12-PKSCHED2-FRAME-FIELD-MATRIX",
    "NEG-N12-PKSCHED2-CLEANUP-FIELD-MATRIX",
    "NEG-N12-PKSCHED2-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKSCHED2-PROBE-OMISSION",
    "NEG-N12-PKSCHED2-PROBE-ORDER",
    "NEG-N12-PKSCHED2-PROBE-TRACE",
    "NEG-N12-PKSCHED2-PROBE-FRAME",
    "NEG-N12-PKSCHED2-PROBE-CLEANUP",
    "NEG-N12-PKSCHED2-INDEPENDENT-TRACE-ORACLE",
    "NEG-N12-PKSCHED2-INTERRUPT-FRAME-CONTRACT",
    "NEG-N12-PKSCHED2-CONTEXT-OWNERSHIP",
    "NEG-N12-PKSCHED2-EVENT-CAPACITY",
    "NEG-N12-PKSCHED2-EVENT-DEADLINE",
    "NEG-N12-PKSCHED2-EVENT-DUPLICATE",
    "NEG-N12-PKSCHED2-QUANTUM-BOUNDARY",
    "NEG-N12-PKSCHED2-TRANSACTIONAL-ROLLBACK",
    "NEG-N12-PKSCHED2-LINKED-SWITCH-SCOPE",
    "NEG-N12-PKSCHED2-RETAINED-STACK-PARTITION",
    "NEG-N12-PKSCHED2-INPUT-BINDING",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-PREEMPT-EARLY PASS contract=PKSCHED2 selector=(?P<selector>[0-9]+) "
    r"parent_scheduler=PKSCHED1 parent_timer=PKIRQ1 bsp=(?P<bsp>[01]) if=(?P<iflag>[01]) "
    r"stack=validated_by_wrapper serial=initialized$"
)
ARM = re.compile(
    r"^POOLEOS:KERNEL:SCHED-PREEMPT-ARM PASS contract=PKSCHED2 timer_vector=(?P<vector>[0-9]+) "
    r"one_shot_count=(?P<count>[0-9]+) apic_ticks_per_second=(?P<frequency>[0-9]+) "
    r"quantum_ticks=(?P<quantum>[0-9]+) tasks=(?P<tasks>[0-9]+) "
    r"deferred_capacity=(?P<capacity>[0-9]+) events=(?P<events>[0-9]+) "
    r"stacks=(?P<stacks>[0-9]+) stack_bytes=(?P<stack_bytes>[0-9]+) ist=(?P<ist>[0-9]+) "
    r"handler_if=(?P<handler_if>[01]) interrupted_if=(?P<interrupted_if>[01])$"
)
TRACE = re.compile(
    r"^POOLEOS:KERNEL:SCHED-PREEMPT-TRACE PASS contract=PKSCHED2 ticks=(?P<ticks>[0-9]+) "
    r"next_trace=(?P<next>[0-9,]+) causes=(?P<causes>[a-z,]+) "
    r"events=(?P<events>[^ ]+) runtime_ticks=(?P<runtime>[0-9,]+) "
    r"quantum_reschedules=(?P<quantum>[0-9]+) wake_reschedules=(?P<wake>[0-9]+) "
    r"block_reschedules=(?P<block>[0-9]+) frame_switches=(?P<switches>[0-9]+)$"
)
FRAME = re.compile(
    r"^POOLEOS:KERNEL:SCHED-PREEMPT-FRAME PASS contract=PKSCHED2 frames_saved=(?P<saved>[0-9]+) "
    r"frames_restored=(?P<restored>[0-9]+) eois=(?P<eois>[0-9]+) nested=(?P<nested>[0-9]+) "
    r"lock_contention=(?P<contention>[0-9]+) task_entries=(?P<entries>[0-9,]+) "
    r"launcher_transitions=(?P<transitions>[0-9]+) same_cr3=(?P<cr3>[01]) "
    r"fs_gs_unchanged=(?P<fsgs>[01]) stack_ownership=(?P<ownership>[a-z_]+)$"
)
CLEANUP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-PREEMPT-CLEANUP PASS contract=PKSCHED2 timer_masked=(?P<masked>[01]) "
    r"controller_retired=(?P<controller>[01]) contexts_cleared=(?P<contexts>[0-9]+) "
    r"stack_bytes_cleared=(?P<cleared>[0-9]+) tasks_dead=(?P<dead>[0-9]+) "
    r"queue_entries=(?P<queued>[0-9]+) running=(?P<running>[0-9]+) blocked=(?P<blocked>[0-9]+) "
    r"lock_released=(?P<lock>[01]) apic_restored=(?P<apic>[01]) pic_restored=(?P<pic>[01]) "
    r"hpet_restored=(?P<hpet>[01]) mmio_revoked=(?P<mmio>[01])$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-PREEMPT-RESULT PASS contract=PKSCHED2 "
    r"profile=(?P<profile>qemu64_bsp_interrupt_return) preemption=(?P<preemption>timer_and_wakeup) "
    r"bsp=(?P<bsp>[01]) ap_dispatch=(?P<ap>[01]) ring3=(?P<ring3>[01]) "
    r"address_spaces=(?P<spaces>[0-9]+) xstate_switch=(?P<xstate>[01]) target=(?P<target>[01]) "
    r"signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) "
    r"production=(?P<production>[01]) terminal=(?P<terminal>halt)$"
)

PROBE_TRACE = re.compile(
    r"^PKSCHED2:TRACE PASS ticks=(?P<ticks>[0-9]+) next=(?P<next>[0-9,]+) "
    r"causes=(?P<causes>[a-z,]+) events=(?P<events>[0-9,]+) runtime=(?P<runtime>[0-9,]+) "
    r"switches=(?P<switches>[0-9]+) pending=(?P<pending>[0-9]+)$"
)
PROBE_FRAME = re.compile(
    r"^PKSCHED2:FRAME PASS valid=(?P<valid>[01]) hostile_rejected=(?P<rejected>[0-9]+) "
    r"top_rsp_valid=(?P<top>[01]) frame_bytes=(?P<bytes>[0-9]+) alignment=(?P<alignment>[0-9]+)$"
)
PROBE_CLEANUP = re.compile(
    r"^PKSCHED2:CLEANUP PASS dead=(?P<dead>[0-9]+) runnable=(?P<runnable>[0-9]+) "
    r"running=(?P<running>[0-9]+) blocked=(?P<blocked>[0-9]+) "
    r"teardowns=(?P<teardowns>[0-9]+) queue_entries=(?P<queued>[0-9]+)$"
)


class KernelSchedulerPreemptError(RuntimeError):
    """Raised when PKSCHED2 data violates its bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSchedulerPreemptError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKSCHED2 {label} violates its contract")
    assert match is not None
    return match


def _numbers(value: str) -> tuple[int, ...]:
    return tuple(int(item, 10) for item in value.split(","))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSchedulerPreemptError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelSchedulerPreemptError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "bounded_bsp_timer_preemption_implemented": True,
        "bounded_bsp_wakeup_preemption_implemented": True,
        "complete_interrupt_frame_switch_verified": True,
        "bounded_deferred_event_queue_implemented": True,
        "transactional_scheduler_rollback_implemented": True,
        "private_task_stack_ownership_verified": True,
        "exact_timer_controller_cleanup_verified": True,
        "rust_python_trace_agreement": True,
        "live_ap_scheduler_dispatch_implemented": False,
        "cross_cpu_scheduler_migration_implemented": False,
        "ring3_or_address_space_switch_implemented": False,
        "per_task_xstate_debug_pmu_switch_implemented": False,
        "general_timer_wheel_or_deferred_workers_implemented": False,
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


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    issues = validate_json(readiness, read_json(root / READINESS_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("readiness input bindings are stale")
    ids = [item.get("id") for item in readiness.get("negative_controls", []) if isinstance(item, dict)]
    if ids != list(NEGATIVE_CONTROL_IDS):
        errors.append("readiness negative-control order diverges")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary diverges")
    return errors


def trace_oracle() -> dict[str, Any]:
    priorities = {0: 10, 1: 10, 2: 30, 3: 25}
    ready = [1]
    current: int | None = 0
    blocked = {2, 3}
    runtime = [0, 0, 0, 0]
    next_trace: list[int] = []
    causes: list[str] = []
    processed: list[int] = []
    quantum = 2
    remaining = quantum
    events = {3: ("signal", 2), 4: ("block", None), 5: ("cancel", 3)}

    def dispatch() -> int:
        nonlocal ready
        maximum = max(priorities[item] for item in ready)
        index = next(index for index, item in enumerate(ready) if priorities[item] == maximum)
        return ready.pop(index)

    for tick in range(1, 7):
        assert current is not None
        runtime[current] += 1
        remaining -= 1
        cause = "none"
        event_count = 0
        if tick in events:
            kind, task = events[tick]
            event_count = 1
            if kind in ("signal", "cancel"):
                assert task is not None and task in blocked
                blocked.remove(task)
                ready.append(task)
                if priorities[task] > priorities[current]:
                    cause = "wake"
            else:
                blocked.add(current)
                current = None
                cause = "block"
        if cause == "none" and remaining == 0:
            cause = "quantum"
        if cause != "none":
            if current is not None:
                ready.append(current)
            current = dispatch()
            remaining = quantum
        next_trace.append(current)
        causes.append(cause)
        processed.append(event_count)
    return {
        "ticks": 6,
        "next": tuple(next_trace),
        "causes": tuple(causes),
        "events": tuple(processed),
        "runtime": tuple(runtime),
        "switches": 4,
        "pending": 0,
    }


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.replace("\r\n", "\n").splitlines() if line.startswith("PKSCHED2:")]
    _require(len(lines) == 3, "PKSCHED2 host probe line count changed")
    trace = _match(PROBE_TRACE, lines[0], "trace probe")
    frame = _match(PROBE_FRAME, lines[1], "frame probe")
    cleanup = _match(PROBE_CLEANUP, lines[2], "cleanup probe")
    observed = {
        "ticks": int(trace.group("ticks"), 10),
        "next": _numbers(trace.group("next")),
        "causes": tuple(trace.group("causes").split(",")),
        "events": _numbers(trace.group("events")),
        "runtime": _numbers(trace.group("runtime")),
        "switches": int(trace.group("switches"), 10),
        "pending": int(trace.group("pending"), 10),
    }
    _require(observed == trace_oracle(), "Rust trace diverges from independent Python oracle")
    _require(
        tuple(int(frame.group(name), 10) for name in ("valid", "rejected", "top", "bytes", "alignment"))
        == (1, 8, 1, 176, 16),
        "frame probe changed",
    )
    _require(
        tuple(int(cleanup.group(name), 10) for name in ("dead", "runnable", "running", "blocked", "teardowns", "queued"))
        == (4, 0, 0, 0, 4, 0),
        "cleanup probe changed",
    )
    return {"lines": lines, "trace": observed, "frame_hostile_rejections": 8, "cleanup": {"tasks_dead": 4, "queue_entries": 0}}


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
        raise KernelSchedulerPreemptError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSCHED2 markers")
    arm_transfer = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm_transfer is not None and int(arm_transfer.group(10), 10) == SELECTOR, "PKSCHED2 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    arm = _match(ARM, markers[30], "arm marker")
    trace = _match(TRACE, markers[31], "trace marker")
    frame = _match(FRAME, markers[32], "frame marker")
    cleanup = _match(CLEANUP, markers[33], "cleanup marker")
    result = _match(RESULT, markers[34], "result marker")
    _require(tuple(int(early.group(name), 10) for name in ("selector", "bsp", "iflag")) == (16, 1, 0), "PKSCHED2 early state changed")
    arm_values = tuple(int(arm.group(name), 10) for name in ("vector", "count", "frequency", "quantum", "tasks", "capacity", "events", "stacks", "stack_bytes", "ist", "handler_if", "interrupted_if"))
    _require(arm_values[0] == 64 and arm_values[1] > 0 and arm_values[2] == arm_values[1] * 100, "PKSCHED2 timer calibration changed")
    _require(arm_values[3:] == (2, 4, 8, 3, 4, 16384, 1, 0, 1), "PKSCHED2 arm geometry changed")
    oracle = trace_oracle()
    _require(int(trace.group("ticks"), 10) == oracle["ticks"], "PKSCHED2 tick count changed")
    _require(_numbers(trace.group("next")) == oracle["next"], "PKSCHED2 next trace changed")
    _require(tuple(trace.group("causes").split(",")) == oracle["causes"], "PKSCHED2 cause trace changed")
    _require(trace.group("events") == "signal:2@3,block@4,cancel:3@5", "PKSCHED2 event trace changed")
    _require(_numbers(trace.group("runtime")) == oracle["runtime"], "PKSCHED2 runtime accounting changed")
    _require(tuple(int(trace.group(name), 10) for name in ("quantum", "wake", "block", "switches")) == (1, 2, 1, 4), "PKSCHED2 reschedule accounting changed")
    _require(tuple(int(frame.group(name), 10) for name in ("saved", "restored", "eois", "nested", "contention", "transitions", "cr3", "fsgs")) == (6, 4, 6, 0, 0, 2, 1, 1), "PKSCHED2 frame receipt changed")
    _require(_numbers(frame.group("entries")) == (1, 1, 1, 1) and frame.group("ownership") == "exact", "PKSCHED2 context ownership changed")
    _require(tuple(int(cleanup.group(name), 10) for name in ("masked", "controller", "contexts", "cleared", "dead", "queued", "running", "blocked", "lock", "apic", "pic", "hpet", "mmio")) == (1, 1, 4, 65536, 4, 0, 0, 0, 1, 1, 1, 1, 1), "PKSCHED2 cleanup receipt changed")
    _require(tuple(int(result.group(name), 10) for name in ("bsp", "ap", "ring3", "spaces", "xstate", "target", "signatures", "authority", "actions", "production")) == (1, 0, 0, 1, 0, 0, 0, 0, 0, 0), "PKSCHED2 claim boundary changed")
    return {
        "transfer_prefix": prefix,
        "timer": {"vector": 64, "one_shot_count": arm_values[1], "apic_ticks_per_second": arm_values[2], "deliveries": 6},
        "trace": oracle,
        "frames": {"saved": 6, "restored": 4, "eois": 6, "task_entries": [1, 1, 1, 1]},
        "cleanup": {"stack_bytes_cleared": 65536, "tasks_dead": 4, "mmio_revoked": 1},
        "result": {"timer_and_wakeup_preemption": 1, "live_ap_dispatch": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
