"""Independent PKSCHED6 exact-topology SMP-preemption and marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSCHED6"
SELECTED_MOVE_ID = "N12-SCHED-SMP-PREEMPT-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-scheduler-smp-preempt-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-smp-preempt-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-scheduler-smp-preempt-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-smp-preempt-readiness.schema.json"
FEATURE = "development-scheduler-smp-preempt"
SELECTOR = 20
MARKER_COUNT = 38
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SCHED-SMP-PREEMPT-RESULT PASS contract=PKSCHED6"

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
    "native/kernel/src/scheduler_preempt.rs",
    "native/kernel/src/scheduler_smp.rs",
    "native/kernel/src/scheduler_ap_workers.rs",
    "native/kernel/src/scheduler_smp_preempt.rs",
    "native/kernel/src/smp_ipi.rs",
    "native/kernel/src/smp_runtime.rs",
    "native/kernel/src/bin/pksched6_probe.rs",
    "runtime/native_kernel_scheduler_smp_preempt.py",
    "specs/native-kernel-scheduler-smp-preempt-contract.json",
    "specs/native-kernel-scheduler-smp-preempt-contract.schema.json",
    "specs/native-kernel-scheduler-smp-preempt-readiness.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_scheduler_smp_preempt.py",
    "tests/test_native_kernel_scheduler_smp_preempt.py",
    "docs/native-kernel-scheduler-smp-preempt.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKSCHED6-MARKER-OMISSION",
    "NEG-N12-PKSCHED6-MARKER-ORDER",
    "NEG-N12-PKSCHED6-MARKER-DUPLICATE",
    "NEG-N12-PKSCHED6-SELECTOR",
    "NEG-N12-PKSCHED6-TOPOLOGY-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-EVENT-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-RESCHEDULE-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-OWNERSHIP-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-ROLLBACK-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-BOUNDS-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-CLEANUP-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-PROBE-OMISSION",
    "NEG-N12-PKSCHED6-PROBE-ORDER",
    "NEG-N12-PKSCHED6-PROBE-FIELD-MATRIX",
    "NEG-N12-PKSCHED6-INDEPENDENT-ORACLE",
    "NEG-N12-PKSCHED6-FRAME-CPU",
    "NEG-N12-PKSCHED6-FRAME-APIC",
    "NEG-N12-PKSCHED6-FRAME-EPOCH",
    "NEG-N12-PKSCHED6-FRAME-STACK",
    "NEG-N12-PKSCHED6-TIMER-EPOCH",
    "NEG-N12-PKSCHED6-EVENT-DEADLINE",
    "NEG-N12-PKSCHED6-EVENT-ORDER",
    "NEG-N12-PKSCHED6-ACK-BINDING",
    "NEG-N12-PKSCHED6-ACK-GATED-OWNER",
    "NEG-N12-PKSCHED6-OFFLINE-TIMEOUT",
    "NEG-N12-PKSCHED6-SOURCE-QUEUE-ROLLBACK",
    "NEG-N12-PKSCHED6-LATE-ACK",
    "NEG-N12-PKSCHED6-WATCHDOG-BOUND",
    "NEG-N12-PKSCHED6-STARVATION-BOUND",
    "NEG-N12-PKSCHED6-DUPLICATE-RUNNABLE",
    "NEG-N12-PKSCHED6-AP-REGISTER-RESTORE",
    "NEG-N12-PKSCHED6-PARK-SCRUB-RELEASE",
    "NEG-N12-PKSCHED6-INPUT-BINDING",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-EARLY PASS contract=PKSCHED6 selector=(?P<selector>[0-9]+) "
    r"parent_preempt=PKSCHED2 parent_smp=PKSCHED4 parent_workers=PKSCHED5 parent_ipi=PKSMP5 "
    r"bsp=(?P<bsp>[01]) if=(?P<iflag>[01]) stack=validated_by_wrapper serial=initialized$"
)
TOPOLOGY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-TOPOLOGY PASS contract=PKSCHED6 processors=(?P<processors>[0-9]+) "
    r"enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) target_apic_ids=(?P<targets>[0-9,]+) "
    r"online_mask=(?P<mask>0x[0-9A-F]{16}) queues=(?P<queues>[0-9]+) tasks=(?P<tasks>[0-9]+) "
    r"timer_lanes=(?P<timers>[0-9]+) frame_lanes=(?P<frames>[0-9]+) event_capacity=(?P<capacity>[0-9]+) "
    r"quantum=(?P<quantum>[0-9]+) ist_bytes_each=(?P<ist>[0-9]+)$"
)
EVENT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-EVENT PASS contract=PKSCHED6 cpu1_order=(?P<cpu1>[0-9,]+) "
    r"cpu2_order=(?P<cpu2>[0-9]+) cancelled=(?P<cancelled>[0-9]+) wake=(?P<wake>[0-9]+) "
    r"migration=(?P<migration>[0-9]+) pending=(?P<pending>[0-9]+) deterministic=(?P<deterministic>[01]) "
    r"order=(?P<order>[a-z,]+)$"
)
RESCHEDULE = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-RESCHEDULE PASS contract=PKSCHED6 live_ipis=(?P<ipis>[0-9]+) "
    r"model_acks=(?P<acks>[0-9]+) quantum_preemptions=(?P<preemptions>[0-9]+) "
    r"context_switches=(?P<switches>[0-9]+) wake=(?P<wake>[0-9]+) migration=(?P<migration>[0-9]+) "
    r"ack_gated=(?P<gated>[01]) result=(?P<result>[a-z]+)$"
)
OWNERSHIP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-OWNERSHIP PASS contract=PKSCHED6 frame_epochs=(?P<frames>[0-9,]+) "
    r"timer_ticks=(?P<ticks>[0-9,]+) trace=(?P<trace>[0-9:;>]+) per_cpu=(?P<per_cpu>[01]) "
    r"frame_owner_exact=(?P<frame_exact>[01]) timer_owner_exact=(?P<timer_exact>[01]) "
    r"run_queue_owner_exact=(?P<queue_exact>[01])$"
)
ROLLBACK = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-ROLLBACK PASS contract=PKSCHED6 offline_cpu=(?P<cpu>[0-9]+) "
    r"timeouts=(?P<timeouts>[0-9]+) rollbacks=(?P<rollbacks>[0-9]+) stale_rejections=(?P<stale>[0-9]+) "
    r"source_queue_restored=(?P<source>[01]) late_ack_rejected=(?P<late>[01]) target_ownership_withheld=(?P<target>[01])$"
)
BOUNDS = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-BOUNDS PASS contract=PKSCHED6 quantum=(?P<quantum>[0-9]+) "
    r"event_latency=(?P<latency>[0-9]+) watchdog_age=(?P<watchdog>[0-9]+) maximum_bypass=(?P<bypass>[0-9]+) "
    r"starvation=(?P<starvation>[0-9]+) lost_wake=(?P<lost>[0-9]+) duplicate_runnable=(?P<duplicate>[0-9]+) "
    r"watchdog_tripped=(?P<tripped>[0-9]+)$"
)
CLEANUP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-CLEANUP PASS contract=PKSCHED6 online_after=(?P<online>0x[0-9A-F]{16}) "
    r"dead=(?P<dead>[0-9]+) teardown=(?P<teardown>[0-9]+) frame_owners_revoked=(?P<frames>[0-9]+) "
    r"timer_owners_revoked=(?P<timers>[0-9]+) resource_pages=(?P<resource>[0-9]+) frame_pages=(?P<frame_pages>[0-9]+) "
    r"total_pages=(?P<total>[0-9]+) zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) "
    r"pending_events=(?P<events>[0-9]+) pending_remote=(?P<remote>[0-9]+) scheduler_lock_released=(?P<lock>[01]) "
    r"capability_revoked=(?P<capability>[01]) runtime_revoked=(?P<runtime>[01]) mmio_revoked=(?P<mmio>[01]) "
    r"pic_restored=(?P<pic>[01]) hpet_restored=(?P<hpet>[01])$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-PREEMPT-RESULT PASS contract=PKSCHED6 profile=(?P<profile>sandybridge_four_vcpu_ack_gated_preemption) "
    r"per_cpu_timers=(?P<timers>bounded_model) per_cpu_frames=(?P<frames>bounded_model) live_reschedule_ipi=(?P<ipi>[01]) "
    r"deterministic_events=(?P<events>[01]) offline_rollback=(?P<rollback>[01]) watchdog_bound=(?P<watchdog>[01]) "
    r"exact_teardown=(?P<teardown>[01]) general_smp=(?P<general>[01]) ap_timer_interrupts=(?P<ap_timers>[01]) "
    r"ring3=(?P<ring3>[01]) address_spaces=(?P<spaces>[0-9]+) target=(?P<target>[01]) signatures=(?P<signatures>[0-9]+) "
    r"authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) n12_exit=(?P<n12>[01]) production=(?P<production>[01]) terminal=(?P<terminal>halt)$"
)

PROBE_PATTERNS = (
    re.compile(r"^PKSCHED6:TOPOLOGY PASS cpus=4 aps=3 online_mask=0x0F queues=4 tasks=8 timer_lanes=4 frame_lanes=4 event_capacity=16 quantum=2$"),
    re.compile(r"^PKSCHED6:EVENT PASS cpu1_order=1,2 cpu2_order=3 cancelled=1 wake=1 migration=1 pending=0 deterministic=1$"),
    re.compile(r"^PKSCHED6:RESCHEDULE PASS acks=5 wake=1 migration=1 quantum=3 context_switches=3 ack_gated=1$"),
    re.compile(r"^PKSCHED6:OWNERSHIP PASS frame_epochs=2,2,2,4 timer_ticks=2,2,2,4 trace=1:2>1;3:6>7>5 per_cpu=1$"),
    re.compile(r"^PKSCHED6:ROLLBACK PASS offline_cpu=4 timeouts=1 rollbacks=1 stale_rejections=1 source_queue_restored=1 late_ack_rejected=1$"),
    re.compile(r"^PKSCHED6:BOUNDS PASS quantum=2 event_latency=0 watchdog_age=2 maximum_bypass=2 starvation=0 lost_wake=0 duplicate_runnable=0$"),
    re.compile(r"^PKSCHED6:CLEANUP PASS online_after=0x01 dead=8 teardown=8 frame_owners_revoked=3 timer_owners_revoked=3 pending_events=0 pending_remote=0 valid=1$"),
)


class KernelSchedulerSmpPreemptError(RuntimeError):
    """Raised when PKSCHED6 evidence violates its bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSchedulerSmpPreemptError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKSCHED6 {label} violates its contract")
    assert match is not None
    return match


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSchedulerSmpPreemptError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelSchedulerSmpPreemptError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_exact_topology_preemption_model_implemented": True,
        "per_cpu_timer_event_frame_and_run_queue_ownership_verified": True,
        "live_reschedule_ipi_acknowledgement_verified": True,
        "deterministic_cancel_wake_migration_ordering_verified": True,
        "offline_timeout_and_source_rollback_verified": True,
        "bounded_quantum_starvation_and_watchdog_verified": True,
        "complete_task_owner_park_scrub_release_verified": True,
        "ap_local_timer_interrupt_delivery_implemented": False,
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
    return {
        "event_order": ((1, 2), (3,)),
        "frame_epochs": (2, 2, 2, 4),
        "timer_ticks": (2, 2, 2, 4),
        "trace": "1:2>1;3:6>7>5",
        "model_acks": 5,
        "live_ipis": 8,
        "quantum_preemptions": 3,
        "context_switches": 3,
        "maximum_event_latency": 0,
        "maximum_watchdog_age": 2,
        "maximum_bypass": 2,
    }


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.replace("\r\n", "\n").splitlines() if line.startswith("PKSCHED6:")]
    _require(len(lines) == len(PROBE_PATTERNS), "PKSCHED6 host probe line count changed")
    for index, (pattern, line) in enumerate(zip(PROBE_PATTERNS, lines), 1):
        _match(pattern, line, f"probe line {index}")
    return {"lines": lines, "trace": trace_oracle(), "receipt_count": 7, "rust_python_exact_agreement": True}


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [*markers[:BOOT_TRANSFER_MARKER_COUNT], *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT]]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSchedulerSmpPreemptError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def _numbers(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in value.split(","))


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSCHED6 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10)) == SELECTOR, "PKSCHED6 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    topology = _match(TOPOLOGY, markers[30], "topology marker")
    event = _match(EVENT, markers[31], "event marker")
    reschedule = _match(RESCHEDULE, markers[32], "reschedule marker")
    ownership = _match(OWNERSHIP, markers[33], "ownership marker")
    rollback = _match(ROLLBACK, markers[34], "rollback marker")
    bounds = _match(BOUNDS, markers[35], "bounds marker")
    cleanup = _match(CLEANUP, markers[36], "cleanup marker")
    result = _match(RESULT, markers[37], "result marker")
    oracle = trace_oracle()
    _require(tuple(int(early.group(name)) for name in ("selector", "bsp", "iflag")) == (20, 1, 0), "early state changed")
    _require(tuple(int(topology.group(name)) for name in ("processors", "enabled", "bsp", "queues", "tasks", "timers", "frames", "capacity", "quantum", "ist")) == (4, 4, 0, 4, 8, 4, 4, 16, 2, 8192), "topology changed")
    _require((topology.group("targets"), topology.group("mask")) == ("1,2,3", "0x000000000000000F"), "topology binding changed")
    _require((event.group("cpu1"), event.group("cpu2"), event.group("order")) == ("1,2", "3", "cancel,wake,migrate"), "event order changed")
    _require(tuple(int(event.group(name)) for name in ("cancelled", "wake", "migration", "pending", "deterministic")) == (1, 1, 1, 0, 1), "event receipt changed")
    _require(tuple(int(reschedule.group(name)) for name in ("ipis", "acks", "preemptions", "switches", "wake", "migration", "gated")) == (8, 5, 3, 3, 1, 1, 1) and reschedule.group("result") == "observed", "reschedule receipt changed")
    _require(_numbers(ownership.group("frames")) == oracle["frame_epochs"] and _numbers(ownership.group("ticks")) == oracle["timer_ticks"] and ownership.group("trace") == oracle["trace"], "ownership trace changed")
    _require(tuple(int(ownership.group(name)) for name in ("per_cpu", "frame_exact", "timer_exact", "queue_exact")) == (1, 1, 1, 1), "ownership boundary changed")
    _require(tuple(int(rollback.group(name)) for name in ("cpu", "timeouts", "rollbacks", "stale", "source", "late", "target")) == (4, 1, 1, 1, 1, 1, 1), "rollback receipt changed")
    _require(tuple(int(bounds.group(name)) for name in ("quantum", "latency", "watchdog", "bypass", "starvation", "lost", "duplicate", "tripped")) == (2, 0, 2, 2, 0, 0, 0, 0), "bounds receipt changed")
    _require(tuple(int(cleanup.group(name)) for name in ("dead", "teardown", "frames", "timers", "resource", "frame_pages", "total", "zeroed", "verified", "events", "remote", "lock", "capability", "runtime", "mmio", "pic", "hpet")) == (8, 8, 3, 3, 96, 6, 102, 417792, 417792, 0, 0, 1, 1, 1, 1, 1, 1) and cleanup.group("online") == "0x0000000000000001", "cleanup receipt changed")
    _require(tuple(int(result.group(name)) for name in ("ipi", "events", "rollback", "watchdog", "teardown", "general", "ap_timers", "ring3", "spaces", "target", "signatures", "authority", "actions", "n12", "production")) == (1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0), "claim boundary changed")
    return {
        "transfer_prefix": prefix,
        "topology": {"processor_count": 4, "target_apic_ids": [1, 2, 3]},
        "events": {"order": "cancel,wake,migrate", "pending": 0},
        "reschedule": {"live_ipis": 8, "model_acks": 5, "quantum_preemptions": 3},
        "ownership": {"frame_epochs": [2, 2, 2, 4], "timer_ticks": [2, 2, 2, 4], "trace": oracle["trace"]},
        "bounds": {"event_latency": 0, "watchdog_age": 2, "maximum_bypass": 2},
        "cleanup": {"dead": 8, "owners_revoked": 3, "pages_released": 102, "bytes_verified": 417792},
        "result": {"bounded_model": 1, "ap_timer_interrupts": 0, "general_smp": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
