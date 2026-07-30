"""Independent PKSCHED1 scheduler trace and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSCHED1"
SELECTED_MOVE_ID = "N12-SCHED-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-scheduler-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-scheduler-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-readiness.schema.json"
FEATURE = "development-scheduler"
SELECTOR = 15
MARKER_COUNT = 34
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
MAX_CPUS = 4
MAX_TASKS = 8
MAX_BYPASS = MAX_TASKS - 1
COMPLETE_CPU_MASK = (1 << MAX_CPUS) - 1
U64_MASK = (1 << 64) - 1
FNV_OFFSET = 0xCBF2_9CE4_8422_2325
FNV_PRIME = 0x0000_0100_0000_01B3
COMPLETION_MARKER = b"POOLEOS:KERNEL:SCHED-RESULT PASS contract=PKSCHED1"

IMPLEMENTATION_INPUTS = (
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/scheduler.rs",
    "native/kernel/src/bin/pksched1_probe.rs",
    "models/tla/PooleScheduler.tla",
    "models/tla/PooleScheduler.safe.cfg",
    "runtime/native_kernel_scheduler.py",
    "specs/native-kernel-scheduler-contract.json",
    "specs/native-kernel-scheduler-contract.schema.json",
    "specs/native-kernel-scheduler-readiness.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_scheduler.py",
    "tests/test_native_kernel_scheduler.py",
    "docs/native-kernel-scheduler.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKSCHED1-MARKER-OMISSION",
    "NEG-N12-PKSCHED1-MARKER-ORDER",
    "NEG-N12-PKSCHED1-MARKER-DUPLICATE",
    "NEG-N12-PKSCHED1-SELECTOR",
    "NEG-N12-PKSCHED1-CORE-FIELD-MATRIX",
    "NEG-N12-PKSCHED1-SWITCH-FIELD-MATRIX",
    "NEG-N12-PKSCHED1-CLEANUP-FIELD-MATRIX",
    "NEG-N12-PKSCHED1-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKSCHED1-SOURCE-AUDIT",
    "NEG-N12-PKSCHED1-LINKED-SWITCH-SCOPE",
    "NEG-N12-PKSCHED1-PROBE-OMISSION",
    "NEG-N12-PKSCHED1-PROBE-ORDER",
    "NEG-N12-PKSCHED1-STRESS-ORACLE",
    "NEG-N12-PKSCHED1-WAIT-ORACLE",
    "NEG-N12-PKSCHED1-INHERIT-ORACLE",
    "NEG-N12-PKSCHED1-CONTEXT-ORACLE",
    "NEG-N12-PKSCHED1-GENERATION-MODEL",
    "NEG-N12-PKSCHED1-PRIORITY-MODEL",
    "NEG-N12-PKSCHED1-AFFINITY-MODEL",
    "NEG-N12-PKSCHED1-DUPLICATE-RUNNABLE-MODEL",
    "NEG-N12-PKSCHED1-MIGRATION-MODEL",
    "NEG-N12-PKSCHED1-WAKE-DELIVERY-MODEL",
    "NEG-N12-PKSCHED1-INHERITANCE-MODEL",
    "NEG-N12-PKSCHED1-REFCOUNT-BOUNDARY",
    "NEG-N12-PKSCHED1-SPINLOCK-OWNERSHIP",
    "NEG-N12-PKSCHED1-CONTEXT-PRECONDITIONS",
    "NEG-N12-PKSCHED1-STACK-AND-TRANSITION-ACCOUNTING",
    "NEG-N12-PKSCHED1-INPUT-BINDING",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-EARLY PASS contract=(?P<contract>PKSCHED1) "
    r"selector=(?P<selector>[0-9]+) bsp=(?P<bsp>[01]) if=(?P<iflag>[01]) "
    r"stack=validated_by_wrapper serial=initialized$"
)
CORE = re.compile(
    r"^POOLEOS:KERNEL:SCHED-CORE PASS contract=(?P<contract>PKSCHED1) "
    r"cpu_capacity=(?P<cpus>[0-9]+) task_capacity=(?P<capacity>[0-9]+) "
    r"active_tasks=(?P<active>[0-9]+) queue_count=(?P<queues>[0-9]+) "
    r"policy=(?P<policy>[a-z_]+) priorities=(?P<minimum>[0-9]+)-(?P<maximum>[0-9]+) "
    r"dispatches=(?P<dispatches>[0-9]+) migrations=(?P<migrations>[0-9]+) "
    r"wakes=(?P<wakes>[0-9]+) teardowns=(?P<teardowns>[0-9]+) "
    r"max_bypass=(?P<bypass>[0-9]+) trace=(?P<trace>[0-9,]+)$"
)
SWITCH = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SWITCH PASS contract=(?P<contract>PKSCHED1) "
    r"tasks=(?P<tasks>[0-9]+) dispatches=(?P<dispatches>[0-9]+) "
    r"transitions=(?P<transitions>[0-9]+) task0_runs=(?P<task0>[0-9]+) "
    r"task1_runs=(?P<task1>[0-9]+) callee_saved=(?P<callee>[0-9]+) "
    r"rflags=(?P<rflags>[01]) same_cr3=(?P<cr3>[01]) "
    r"fs_gs_unchanged=(?P<fsgs>[01]) xstate_unused=(?P<xstate>[01]) "
    r"debug_unused=(?P<debug>[01]) pmu_unused=(?P<pmu>[01]) "
    r"stacks_distinct=(?P<distinct>[01]) stack_bytes=(?P<stack_bytes>[0-9]+) "
    r"alignment=(?P<alignment>[0-9]+) errors=(?P<errors>[0-9]+)$"
)
CLEANUP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-CLEANUP PASS contract=(?P<contract>PKSCHED1) "
    r"scheduler_lock_released=(?P<lock>[01]) stack_bytes_cleared=(?P<cleared>[0-9]+) "
    r"task_contexts_retired=(?P<retired>[0-9]+) queue_entries=(?P<queued>[0-9]+) "
    r"running=(?P<running>[0-9]+) blocked=(?P<blocked>[0-9]+) dead=(?P<dead>[0-9]+)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-RESULT PASS contract=(?P<contract>PKSCHED1) "
    r"profile=(?P<profile>qemu64_bsp_cooperative) core=(?P<core>[01]) "
    r"hardware_switch=(?P<hardware>[01]) bsp=(?P<bsp>[01]) "
    r"smp_dispatch=(?P<smp>[01]) preemption=(?P<preemption>[01]) "
    r"ring3=(?P<ring3>[01]) address_spaces=(?P<spaces>[0-9]+) "
    r"xstate_switch=(?P<xstate>[01]) target=(?P<target>[01]) "
    r"signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) "
    r"actions=(?P<actions>[0-9]+) production=(?P<production>[01]) "
    r"terminal=(?P<terminal>halt)$"
)

STRESS = re.compile(
    r"^PKSCHED1:STRESS PASS sequence=(?P<sequence>[0-9]+) tasks=(?P<tasks>[0-9]+) "
    r"runnable=(?P<runnable>[0-9]+) running=(?P<running>[0-9]+) "
    r"blocked=(?P<blocked>[0-9]+) dead=(?P<dead>[0-9]+) "
    r"dispatches=(?P<dispatches>[0-9]+) migrations=(?P<migrations>[0-9]+) "
    r"wakes=(?P<wakes>[0-9]+) teardowns=(?P<teardowns>[0-9]+) "
    r"inheritance=(?P<inheritance>[0-9]+) checksum=0x(?P<checksum>[0-9A-F]{16}) "
    r"task_dispatches=(?P<task_dispatches>[0-9,]+) runtime_ticks=(?P<runtime_ticks>[0-9,]+)$"
)
WAIT = re.compile(
    r"^PKSCHED1:WAIT PASS sequence=(?P<sequence>[0-9]+) wakes=(?P<wakes>[0-9]+) "
    r"cancel_reason=(?P<cancel>[0-9]+) timeout_reason=(?P<timeout>[0-9]+) "
    r"duplicate_rejected=(?P<duplicate>[01])$"
)
INHERIT = re.compile(
    r"^PKSCHED1:INHERIT PASS owner_slot=(?P<owner>[0-9]+) waiter_slot=(?P<waiter>[0-9]+) "
    r"inherited=(?P<inherited>[0-9]+) restored=(?P<restored>[0-9]+) "
    r"granted_slot=(?P<granted>[0-9]+) inheritance_events=(?P<events>[0-9]+)$"
)
CONTEXT = re.compile(
    r"^PKSCHED1:CONTEXT PASS valid=(?P<valid>[01]) hostile_rejected=(?P<rejected>[0-9]+) "
    r"alignment=(?P<alignment>[0-9]+) callee_saved=(?P<callee>[0-9]+)$"
)


class KernelSchedulerError(RuntimeError):
    """Raised when PKSCHED1 data violates its frozen bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSchedulerError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKSCHED1 {label} violates its contract")
    assert match is not None
    return match


def _numbers(value: str) -> tuple[int, ...]:
    return tuple(int(item, 10) for item in value.split(","))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSchedulerError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelSchedulerError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "bounded_scheduler_foundation_implemented": True,
        "allocation_free_fixed_capacity_core": True,
        "generation_safe_task_identity": True,
        "fixed_priority_round_robin_neutral_policy": True,
        "bounded_affinity_and_migration_model": True,
        "exact_cancel_and_timeout_wake_delivery": True,
        "one_mutex_direct_priority_inheritance": True,
        "raw_spinlock_and_refcount_primitives": True,
        "live_bsp_kernel_context_switch_verified": True,
        "rust_python_trace_agreement": True,
        "tla_full_refinement_proved": False,
        "scheduler_liveness_proved": False,
        "interrupt_driven_preemption_implemented": False,
        "live_smp_dispatch_implemented": False,
        "ring3_or_address_space_switch_implemented": False,
        "full_xstate_debug_pmu_switch_implemented": False,
        "general_scheduler_implemented": False,
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
    controls = readiness.get("negative_controls", [])
    ids = [item.get("id") for item in controls if isinstance(item, dict)]
    if ids != list(NEGATIVE_CONTROL_IDS):
        errors.append("readiness negative-control order diverges")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary diverges")
    return errors


@dataclass
class _Task:
    slot: int
    generation: int
    state: int
    base_priority: int
    effective_priority: int
    affinity: int
    assigned: int | None = None
    queued: int | None = None
    wake_reason: int = 0
    wait_kind: int = 0
    bypass: int = 0
    dispatches: int = 0
    runtime: int = 0


class NeutralSchedulerOracle:
    """Independent fixed-capacity model for the deterministic Rust stress trace."""

    def __init__(self) -> None:
        self.tasks: list[_Task | None] = [None] * MAX_TASKS
        self.queues: list[list[int]] = [[] for _ in range(MAX_CPUS)]
        self.current: list[int | None] = [None] * MAX_CPUS
        self.sequence = 0
        self.dispatches = 0
        self.migrations = 0

    def create(self, slot: int, priority: int) -> None:
        _require(0 <= slot < MAX_TASKS and self.tasks[slot] is None, "oracle task identity")
        _require(1 <= priority <= 31, "oracle priority")
        self.tasks[slot] = _Task(slot, 1, 0, priority, priority, COMPLETE_CPU_MASK)
        self.sequence += 1

    def activate(self, slot: int, cpu: int) -> None:
        task = self._task(slot)
        _require(task.state == 0 and task.affinity & (1 << cpu), "oracle activation")
        task.state = 1
        task.assigned = cpu
        task.queued = cpu
        self.queues[cpu].append(slot)
        self.sequence += 1

    def dispatch(self, cpu: int) -> bool:
        if self.current[cpu] is not None or not self.queues[cpu]:
            return False
        queue = self.queues[cpu]
        selected_index = 0
        for index in range(1, len(queue)):
            candidate = self._task(queue[index])
            incumbent = self._task(queue[selected_index])
            if candidate.effective_priority > incumbent.effective_priority or (
                candidate.effective_priority == incumbent.effective_priority
                and candidate.bypass > incumbent.bypass
            ):
                selected_index = index
        slot = queue.pop(selected_index)
        task = self._task(slot)
        for other_slot in queue:
            other = self._task(other_slot)
            if other.effective_priority == task.effective_priority:
                other.bypass += 1
                _require(other.bypass <= MAX_BYPASS, "oracle bypass overflow")
        task.state = 2
        task.queued = None
        task.assigned = cpu
        task.bypass = 0
        task.dispatches += 1
        self.current[cpu] = slot
        self.dispatches += 1
        self.sequence += 1
        return True

    def account(self, cpu: int, ticks: int) -> bool:
        slot = self.current[cpu]
        if slot is None or ticks <= 0:
            return False
        self._task(slot).runtime += ticks
        self.sequence += 1
        return True

    def yield_current(self, cpu: int) -> bool:
        slot = self.current[cpu]
        if slot is None:
            return False
        self.current[cpu] = None
        task = self._task(slot)
        task.state = 1
        task.assigned = cpu
        task.queued = cpu
        self.queues[cpu].append(slot)
        self.sequence += 1
        return True

    def migrate(self, slot: int, target: int) -> bool:
        task = self._task(slot)
        if task.state != 1 or not task.affinity & (1 << target) or task.queued == target:
            return False
        _require(task.queued is not None, "oracle queued CPU missing")
        source = task.queued
        try:
            self.queues[source].remove(slot)
        except ValueError as error:
            raise KernelSchedulerError("oracle queue ownership") from error
        self.queues[target].append(slot)
        task.queued = target
        task.assigned = target
        self.migrations += 1
        self.sequence += 1
        return True

    def validate(self) -> None:
        seen = [0] * MAX_TASKS
        running = [0] * MAX_TASKS
        for cpu, queue in enumerate(self.queues):
            _require(len(queue) <= MAX_TASKS and len(queue) == len(set(queue)), "oracle queue shape")
            for slot in queue:
                task = self._task(slot)
                _require(task.state == 1 and task.queued == cpu and task.assigned == cpu, "oracle runnable")
                _require(task.affinity & (1 << cpu) and task.bypass <= MAX_BYPASS, "oracle placement")
                seen[slot] += 1
            slot = self.current[cpu]
            if slot is not None:
                task = self._task(slot)
                _require(task.state == 2 and task.assigned == cpu and task.queued is None, "oracle running")
                running[slot] += 1
        for slot, task in enumerate(self.tasks):
            _require(task is not None, "oracle task missing")
            assert task is not None
            _require((task.state == 1) == (seen[slot] == 1), "oracle runnable count")
            _require((task.state == 2) == (running[slot] == 1), "oracle running count")

    def _task(self, slot: int) -> _Task:
        task = self.tasks[slot]
        _require(task is not None, "oracle task missing")
        assert task is not None
        return task

    def receipt(self) -> dict[str, Any]:
        checksum = FNV_OFFSET
        dispatches: list[int] = []
        runtime: list[int] = []
        for slot in range(MAX_TASKS):
            task = self._task(slot)
            dispatches.append(task.dispatches)
            runtime.append(task.runtime)
            values = (
                task.slot,
                task.generation,
                task.state,
                task.base_priority,
                task.effective_priority,
                task.affinity,
                0 if task.assigned is None else task.assigned + 1,
                task.wake_reason,
                task.wait_kind,
                task.bypass,
                task.dispatches,
                task.runtime,
            )
            for value in values:
                for byte in int(value).to_bytes(8, "little"):
                    checksum ^= byte
                    checksum = (checksum * FNV_PRIME) & U64_MASK
        states = [self._task(slot).state for slot in range(MAX_TASKS)]
        return {
            "sequence": self.sequence,
            "tasks": MAX_TASKS,
            "runnable": states.count(1),
            "running": states.count(2),
            "blocked": states.count(3),
            "dead": states.count(4),
            "dispatches": self.dispatches,
            "migrations": self.migrations,
            "wakes": 0,
            "teardowns": 0,
            "inheritance": 0,
            "checksum": checksum,
            "task_dispatches": tuple(dispatches),
            "runtime_ticks": tuple(runtime),
        }


def stress_oracle() -> dict[str, Any]:
    scheduler = NeutralSchedulerOracle()
    for slot in range(MAX_TASKS):
        scheduler.create(slot, slot % MAX_CPUS + 8)
        scheduler.activate(slot, slot % MAX_CPUS)
    random = 0x5A17_91D3_6C8E_204F
    for _ in range(4096):
        random ^= (random << 13) & U64_MASK
        random &= U64_MASK
        random ^= random >> 7
        random &= U64_MASK
        random ^= (random << 17) & U64_MASK
        random &= U64_MASK
        cpu = random % MAX_CPUS
        if scheduler.current[cpu] is None:
            scheduler.dispatch(cpu)
        elif random & 3 == 0:
            scheduler.account(cpu, 1)
            scheduler.yield_current(cpu)
        elif random & 7 == 1:
            scheduler.account(cpu, 2)
        else:
            scheduler.yield_current(cpu)
        slot = ((random << 9) | (random >> 55)) & U64_MASK
        target = ((random >> 11) | (random << 53)) & U64_MASK
        scheduler.migrate(slot % MAX_TASKS, target % MAX_CPUS)
        scheduler.validate()
    return scheduler.receipt()


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.replace("\r\n", "\n").splitlines() if line.startswith("PKSCHED1:")]
    _require(len(lines) == 4, "PKSCHED1 host probe line count changed")
    stress = _match(STRESS, lines[0], "stress probe")
    wait = _match(WAIT, lines[1], "wait probe")
    inherit = _match(INHERIT, lines[2], "inheritance probe")
    context = _match(CONTEXT, lines[3], "context probe")
    stress_receipt = {
        name: int(stress.group(name), 10)
        for name in (
            "sequence",
            "tasks",
            "runnable",
            "running",
            "blocked",
            "dead",
            "dispatches",
            "migrations",
            "wakes",
            "teardowns",
            "inheritance",
        )
    }
    stress_receipt.update(
        {
            "checksum": int(stress.group("checksum"), 16),
            "task_dispatches": _numbers(stress.group("task_dispatches")),
            "runtime_ticks": _numbers(stress.group("runtime_ticks")),
        }
    )
    expected = stress_oracle()
    _require(stress_receipt == expected, "Rust stress receipt diverges from independent oracle")
    wait_receipt = tuple(int(wait.group(name), 10) for name in ("sequence", "wakes", "cancel", "timeout", "duplicate"))
    _require(wait_receipt == (14, 2, 1, 2, 1), "wait-delivery receipt changed")
    inherit_receipt = tuple(int(inherit.group(name), 10) for name in ("owner", "waiter", "inherited", "restored", "granted", "events"))
    _require(inherit_receipt == (0, 1, 30, 2, 1, 1), "priority-inheritance receipt changed")
    context_receipt = tuple(int(context.group(name), 10) for name in ("valid", "rejected", "alignment", "callee"))
    _require(context_receipt == (1, 8, 16, 6), "context-contract receipt changed")
    return {
        "lines": lines,
        "stress": stress_receipt,
        "wait": {"sequence": 14, "wake_count": 2, "cancel_reason": 1, "timeout_reason": 2},
        "inheritance": {"owner_slot": 0, "waiter_slot": 1, "inherited": 30, "restored": 2},
        "context": {"valid": 1, "hostile_rejected": 8, "alignment": 16, "callee_saved": 6},
    }


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
        raise KernelSchedulerError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSCHED1 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10), 10) == SELECTOR, "PKSCHED1 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    core = _match(CORE, markers[30], "core marker")
    switch = _match(SWITCH, markers[31], "switch marker")
    cleanup = _match(CLEANUP, markers[32], "cleanup marker")
    result = _match(RESULT, markers[33], "result marker")
    _require(tuple(int(early.group(name), 10) for name in ("selector", "bsp", "iflag")) == (15, 1, 0), "PKSCHED1 early state changed")
    _require(
        tuple(int(core.group(name), 10) for name in ("cpus", "capacity", "active", "queues", "minimum", "maximum", "dispatches", "migrations", "wakes", "teardowns", "bypass"))
        == (4, 8, 2, 4, 1, 31, 8, 0, 0, 2, 7),
        "PKSCHED1 core receipt changed",
    )
    _require(core.group("policy") == "fixed_priority_round_robin", "PKSCHED1 neutral policy changed")
    trace = _numbers(core.group("trace"))
    _require(trace == (0, 1, 0, 1, 0, 1, 0, 1), "PKSCHED1 dispatch trace changed")
    _require(
        tuple(int(switch.group(name), 10) for name in ("tasks", "dispatches", "transitions", "task0", "task1", "callee", "rflags", "cr3", "fsgs", "xstate", "debug", "pmu", "distinct", "stack_bytes", "alignment", "errors"))
        == (2, 8, 16, 4, 4, 6, 1, 1, 1, 1, 1, 1, 1, 16384, 16, 0),
        "PKSCHED1 live switch receipt changed",
    )
    _require(
        tuple(int(cleanup.group(name), 10) for name in ("lock", "cleared", "retired", "queued", "running", "blocked", "dead"))
        == (1, 32768, 2, 0, 0, 0, 2),
        "PKSCHED1 cleanup receipt changed",
    )
    _require(
        tuple(int(result.group(name), 10) for name in ("core", "hardware", "bsp", "smp", "preemption", "ring3", "spaces", "xstate", "target", "signatures", "authority", "actions", "production"))
        == (1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0),
        "PKSCHED1 claim boundary changed",
    )
    return {
        "transfer_prefix": prefix,
        "core": {"cpu_capacity": 4, "task_capacity": 8, "active_tasks": 2, "dispatches": 8, "trace": list(trace)},
        "switch": {"tasks": 2, "dispatches": 8, "transitions": 16, "task_runs": [4, 4], "stack_bytes": 16384},
        "cleanup": {"stack_bytes_cleared": 32768, "task_contexts_retired": 2},
        "result": {"bounded_core": 1, "hardware_switch": 1, "live_smp_dispatch": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
