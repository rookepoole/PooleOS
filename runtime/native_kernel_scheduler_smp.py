"""Independent PKSCHED4 exact-topology SMP scheduler and marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSCHED4"
SELECTED_MOVE_ID = "N12-SCHED-SMP-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-scheduler-smp-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-smp-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-scheduler-smp-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-scheduler-smp-readiness.schema.json"
FEATURE = "development-scheduler-smp"
SELECTOR = 18
MARKER_COUNT = 37
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SCHED-SMP-RESULT PASS contract=PKSCHED4"

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
    "native/kernel/src/scheduler_smp.rs",
    "native/kernel/src/smp_ipi.rs",
    "native/kernel/src/bin/pksched4_probe.rs",
    "runtime/native_kernel_scheduler_smp.py",
    "specs/native-kernel-scheduler-smp-contract.json",
    "specs/native-kernel-scheduler-smp-contract.schema.json",
    "specs/native-kernel-scheduler-smp-readiness.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_kernel_scheduler_smp.py",
    "tests/test_native_kernel_scheduler_smp.py",
    "docs/native-kernel-scheduler-smp.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKSCHED4-MARKER-OMISSION",
    "NEG-N12-PKSCHED4-MARKER-ORDER",
    "NEG-N12-PKSCHED4-MARKER-DUPLICATE",
    "NEG-N12-PKSCHED4-SELECTOR",
    "NEG-N12-PKSCHED4-TOPOLOGY-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-TRANSFER-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-DISPATCH-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-FAIRNESS-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-ROLLBACK-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-CLEANUP-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-PROBE-OMISSION",
    "NEG-N12-PKSCHED4-PROBE-ORDER",
    "NEG-N12-PKSCHED4-PROBE-FIELD-MATRIX",
    "NEG-N12-PKSCHED4-INDEPENDENT-ORACLE",
    "NEG-N12-PKSCHED4-EXACT-TOPOLOGY",
    "NEG-N12-PKSCHED4-DUPLICATE-RUNNABLE",
    "NEG-N12-PKSCHED4-STALE-GENERATION",
    "NEG-N12-PKSCHED4-OWNER-EPOCH",
    "NEG-N12-PKSCHED4-WAKE-ACK-BINDING",
    "NEG-N12-PKSCHED4-MIGRATION-ACK-BINDING",
    "NEG-N12-PKSCHED4-DISPATCH-ACK-BINDING",
    "NEG-N12-PKSCHED4-OFFLINE-TIMEOUT",
    "NEG-N12-PKSCHED4-LATE-ACK",
    "NEG-N12-PKSCHED4-SOURCE-QUEUE-ROLLBACK",
    "NEG-N12-PKSCHED4-TOPOLOGY-BALANCING",
    "NEG-N12-PKSCHED4-FAIRNESS-BOUND",
    "NEG-N12-PKSCHED4-IDLE-OWNERSHIP",
    "NEG-N12-PKSCHED4-AP-REGISTER-RESTORE",
    "NEG-N12-PKSCHED4-PARK-SCRUB-RELEASE",
    "NEG-N12-PKSCHED4-NO-HEAP-OR-CALLBACK",
    "NEG-N12-PKSCHED4-INPUT-BINDING",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-EARLY PASS contract=PKSCHED4 selector=(?P<selector>[0-9]+) "
    r"parent_smp=(?P<smp>PKSMP5) parent_scheduler=(?P<scheduler>PKSCHED1) bsp=(?P<bsp>[01]) "
    r"if=(?P<iflag>[01]) stack=validated_by_wrapper serial=initialized$"
)
TOPOLOGY = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-TOPOLOGY PASS contract=PKSCHED4 processors=(?P<processors>[0-9]+) "
    r"enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) target_apic_ids=(?P<targets>[0-9,]+) "
    r"online_mask=(?P<mask>0x[0-9A-F]{16}) queue_count=(?P<queues>[0-9]+) "
    r"task_capacity=(?P<tasks>[0-9]+) balance=(?P<balance>[0-9,]+) idle_owners=(?P<idle>[0-9]+)$"
)
TRANSFER = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-TRANSFER PASS contract=PKSCHED4 wake=(?P<wake>[0-9]+) "
    r"migrations=(?P<migrations>[0-9]+) transaction_acks=(?P<transactions>[0-9]+) "
    r"remote_acks=(?P<remote>[0-9]+) queues=(?P<queues>[0-9,]+) owner_transfer=(?P<owner>[a-z_]+) "
    r"ack_mask=(?P<mask>0x[0-9A-F]{16}) generation_safe=(?P<generation>[01])$"
)
DISPATCH = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-DISPATCH PASS contract=PKSCHED4 bsp_trace=(?P<bsp_trace>[0-9,]+) "
    r"ap_trace=(?P<ap_trace>[0-9:,]+) bsp_dispatches=(?P<bsp>[0-9]+) ap_dispatches=(?P<ap>[0-9]+) "
    r"dispatch_acks=(?P<acks>[0-9]+) call_function_executions=(?P<calls>[0-9]+) "
    r"task_entries=(?P<entries>[0-9]+) registers_restored=(?P<registers>[0-9]+)$"
)
FAIRNESS = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-FAIRNESS PASS contract=PKSCHED4 policy=(?P<policy>[a-z_]+) "
    r"priorities=(?P<priorities>[0-9-]+) maximum_equal_priority_bypass=(?P<bypass>[0-9]+) "
    r"starvation_bound=(?P<starvation>[0-9]+) lost_wake=(?P<lost>[0-9]+) "
    r"duplicate_runnable=(?P<duplicate>[0-9]+) dead_task_dispatch=(?P<dead>[0-9]+) "
    r"priority_inversion_violation=(?P<inversion>[0-9]+)$"
)
ROLLBACK = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-ROLLBACK PASS contract=PKSCHED4 offline_cpu=(?P<cpu>[0-9]+) "
    r"timeouts=(?P<timeouts>[0-9]+) rollbacks=(?P<rollbacks>[0-9]+) "
    r"stale_rejections=(?P<stale>[0-9]+) late_ack_rejected=(?P<late>[01]) "
    r"stale_generation_rejected=(?P<generation>[01]) source_queue_restored=(?P<source>[01]) "
    r"target_ownership_withheld=(?P<target>[01])$"
)
CLEANUP = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-CLEANUP PASS contract=PKSCHED4 tasks_dead=(?P<dead>[0-9]+) "
    r"idle_before=(?P<idle>[0-9]+) owner_epoch_sum=(?P<epochs>[0-9]+) "
    r"online_after=(?P<online>0x[0-9A-F]{16}) parked_mask=(?P<parked>0x[0-9A-F]{16}) "
    r"resource_pages=(?P<resource>[0-9]+) frame_pages=(?P<frames>[0-9]+) total_pages=(?P<total>[0-9]+) "
    r"zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) queues=(?P<queues>[0-9]+) "
    r"running=(?P<running>[0-9]+) scheduler_lock_released=(?P<lock>[01]) capability_revoked=(?P<capability>[01]) "
    r"runtime_revoked=(?P<runtime>[01]) mmio_revoked=(?P<mmio>[01]) pic_restored=(?P<pic>[01]) hpet_restored=(?P<hpet>[01])$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SCHED-SMP-RESULT PASS contract=PKSCHED4 profile=(?P<profile>sandybridge_four_vcpu_ack_gated_scheduler) "
    r"scheduler=(?P<scheduler>bounded_smp) ap_dispatch=(?P<ap>[01]) cross_cpu_wake=(?P<wake>[01]) "
    r"migration=(?P<migration>[01]) topology=(?P<topology>exact) general_smp=(?P<general>[01]) ring3=(?P<ring3>[01]) "
    r"address_spaces=(?P<spaces>[0-9]+) per_task_xstate=(?P<xstate>[01]) target=(?P<target>[01]) "
    r"signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) "
    r"n12_exit=(?P<n12>[01]) production=(?P<production>[01]) terminal=(?P<terminal>halt)$"
)

PROBE_TOPOLOGY = re.compile(
    r"^PKSCHED4:TOPOLOGY PASS cpus=(?P<cpus>[0-9]+) online_mask=(?P<online>0x[0-9A-F]{2}) "
    r"ap_mask=(?P<ap>0x[0-9A-F]{2}) queues=(?P<queues>[0-9]+) tasks=(?P<tasks>[0-9]+) "
    r"balance=(?P<balance>[0-9,]+) idle_owners=(?P<idle>[0-9]+)$"
)
PROBE_TRANSFER = re.compile(
    r"^PKSCHED4:TRANSFER PASS wake=(?P<wake>[0-9]+) migrations=(?P<migrations>[0-9]+) "
    r"transaction_acks=(?P<acks>[0-9]+) queues=(?P<queues>[0-9,]+) "
    r"owner_transfer=(?P<owner>[a-z_]+) timeout_target=(?P<target>[0-9]+)$"
)
PROBE_DISPATCH = re.compile(
    r"^PKSCHED4:DISPATCH PASS bsp_trace=(?P<bsp_trace>[0-9,]+) ap_trace=(?P<ap_trace>[0-9:,]+) "
    r"bsp_dispatches=(?P<bsp>[0-9]+) ap_dispatches=(?P<ap>[0-9]+) ipi_acks=(?P<acks>[0-9]+) "
    r"call_function_executions=(?P<calls>[0-9]+) max_bypass=(?P<bypass>[0-9]+)$"
)
PROBE_ROLLBACK = re.compile(
    r"^PKSCHED4:ROLLBACK PASS offline_cpu=(?P<cpu>[0-9]+) timeouts=(?P<timeouts>[0-9]+) "
    r"rollbacks=(?P<rollbacks>[0-9]+) late_ack_rejected=(?P<late>[01]) "
    r"stale_generation_rejected=(?P<generation>[01]) stale_rejections=(?P<stale>[0-9]+) "
    r"lost_wake=(?P<lost>[0-9]+) duplicate_runnable=(?P<duplicate>[0-9]+)$"
)
PROBE_CLEANUP = re.compile(
    r"^PKSCHED4:CLEANUP PASS tasks_dead=(?P<dead>[0-9]+) queues=(?P<queues>[0-9]+) "
    r"running=(?P<running>[0-9]+) idle_before=(?P<idle>[0-9]+) owner_epoch_sum=(?P<epochs>[0-9]+) "
    r"online_after=(?P<online>0x[0-9A-F]{2}) parked_mask=(?P<parked>0x[0-9A-F]{2}) "
    r"teardown=(?P<teardown>[0-9]+) valid=(?P<valid>[01])$"
)


class KernelSchedulerSmpError(RuntimeError):
    """Raised when PKSCHED4 evidence violates its bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSchedulerSmpError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKSCHED4 {label} violates its contract")
    assert match is not None
    return match


def _numbers(value: str) -> tuple[int, ...]:
    return tuple(int(item, 10) for item in value.split(","))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSchedulerSmpError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelSchedulerSmpError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_exact_topology_smp_scheduler_implemented": True,
        "four_ap_local_run_queues_and_idle_owners_verified": True,
        "live_remote_reschedule_acknowledgement_verified": True,
        "generation_safe_cross_cpu_wake_verified": True,
        "generation_safe_cross_cpu_migration_verified": True,
        "six_live_ap_dispatches_verified": True,
        "offline_timeout_and_source_rollback_verified": True,
        "topology_aware_balancing_verified": True,
        "bounded_fairness_and_no_duplicate_runnable_verified": True,
        "complete_ap_park_scrub_release_verified": True,
        "general_topology_or_hotplug_implemented": False,
        "general_smp_preemption_implemented": False,
        "ring3_or_address_space_switch_implemented": False,
        "per_task_full_architectural_state_implemented": False,
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
    queues = [[0, 7], [2, 3], [4, 5], [6]]
    blocked = [1]
    balance = (min(range(4), key=lambda cpu: (len(queues[cpu]), cpu)), min(range(1, 4), key=lambda cpu: (len(queues[cpu]), cpu)))
    blocked.remove(1)
    queues[1].append(1)
    queues[1].remove(3)
    queues[2].append(3)
    queues[2].remove(5)
    queues[3].append(5)
    ap_trace: list[tuple[int, int]] = []
    for cpu in range(1, 4):
        for _ in range(2):
            ap_trace.append((cpu, queues[cpu].pop(0)))
    bsp_trace = (queues[0].pop(0), queues[0].pop(0))
    return {
        "balance": balance,
        "queues_after_transfer": (2, 2, 2),
        "bsp_trace": bsp_trace,
        "ap_trace": tuple(ap_trace),
        "owner_epoch_sum": 19,
        "remote_acks": 9,
        "maximum_bypass": 1,
    }


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.replace("\r\n", "\n").splitlines() if line.startswith("PKSCHED4:")]
    _require(len(lines) == 5, "PKSCHED4 host probe line count changed")
    topology = _match(PROBE_TOPOLOGY, lines[0], "topology probe")
    transfer = _match(PROBE_TRANSFER, lines[1], "transfer probe")
    dispatch = _match(PROBE_DISPATCH, lines[2], "dispatch probe")
    rollback = _match(PROBE_ROLLBACK, lines[3], "rollback probe")
    cleanup = _match(PROBE_CLEANUP, lines[4], "cleanup probe")
    oracle = trace_oracle()
    _require(tuple(int(topology.group(name), 10) for name in ("cpus", "queues", "tasks", "idle")) == (4, 4, 8, 4), "probe topology changed")
    _require((topology.group("online"), topology.group("ap"), _numbers(topology.group("balance"))) == ("0x0F", "0x0E", oracle["balance"]), "probe topology masks changed")
    _require(tuple(int(transfer.group(name), 10) for name in ("wake", "migrations", "acks", "target")) == (1, 2, 3, 4), "probe transfer counts changed")
    _require(_numbers(transfer.group("queues")) == oracle["queues_after_transfer"] and transfer.group("owner") == "ack_gated", "probe transfer ownership changed")
    _require(_numbers(dispatch.group("bsp_trace")) == oracle["bsp_trace"], "Rust BSP trace diverges from Python oracle")
    _require(dispatch.group("ap_trace") == "1:2,1:1,2:4,2:3,3:6,3:5", "Rust AP trace diverges from Python oracle")
    _require(tuple(int(dispatch.group(name), 10) for name in ("bsp", "ap", "acks", "calls", "bypass")) == (2, 6, 9, 9, oracle["maximum_bypass"]), "probe dispatch receipt changed")
    _require(tuple(int(rollback.group(name), 10) for name in ("cpu", "timeouts", "rollbacks", "late", "generation", "stale", "lost", "duplicate")) == (4, 1, 1, 1, 1, 2, 0, 0), "probe rollback receipt changed")
    _require(tuple(int(cleanup.group(name), 10) for name in ("dead", "queues", "running", "idle", "epochs", "teardown", "valid")) == (8, 0, 0, 4, 19, 8, 1), "probe cleanup changed")
    _require((cleanup.group("online"), cleanup.group("parked")) == ("0x01", "0x0E"), "probe park masks changed")
    return {"lines": lines, "trace": oracle, "receipt_count": 5, "rust_python_exact_agreement": True}


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [*markers[:BOOT_TRANSFER_MARKER_COUNT], *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT]]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSchedulerSmpError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSCHED4 markers")
    arm_transfer = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm_transfer is not None and int(arm_transfer.group(10), 10) == SELECTOR, "PKSCHED4 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    topology = _match(TOPOLOGY, markers[30], "topology marker")
    transfer = _match(TRANSFER, markers[31], "transfer marker")
    dispatch = _match(DISPATCH, markers[32], "dispatch marker")
    fairness = _match(FAIRNESS, markers[33], "fairness marker")
    rollback = _match(ROLLBACK, markers[34], "rollback marker")
    cleanup = _match(CLEANUP, markers[35], "cleanup marker")
    result = _match(RESULT, markers[36], "result marker")
    oracle = trace_oracle()
    _require(tuple(int(early.group(name), 10) for name in ("selector", "bsp", "iflag")) == (18, 1, 0), "PKSCHED4 early state changed")
    _require(tuple(int(topology.group(name), 10) for name in ("processors", "enabled", "bsp", "queues", "tasks", "idle")) == (4, 4, 0, 4, 8, 4), "PKSCHED4 topology changed")
    _require((topology.group("targets"), topology.group("mask"), _numbers(topology.group("balance"))) == ("1,2,3", "0x000000000000000F", oracle["balance"]), "PKSCHED4 topology binding changed")
    _require(tuple(int(transfer.group(name), 10) for name in ("wake", "migrations", "transactions", "remote", "generation")) == (1, 2, 3, 9, 1), "PKSCHED4 transfer counts changed")
    _require((_numbers(transfer.group("queues")), transfer.group("owner"), transfer.group("mask")) == ((2, 2, 2), "ack_gated", "0x000000000000000E"), "PKSCHED4 transfer ownership changed")
    _require(_numbers(dispatch.group("bsp_trace")) == oracle["bsp_trace"] and dispatch.group("ap_trace") == "1:2,1:1,2:4,2:3,3:6,3:5", "PKSCHED4 dispatch trace changed")
    _require(tuple(int(dispatch.group(name), 10) for name in ("bsp", "ap", "acks", "calls", "entries", "registers")) == (2, 6, 6, 9, 8, 15), "PKSCHED4 dispatch receipt changed")
    _require((fairness.group("policy"), fairness.group("priorities")) == ("fixed_priority_round_robin", "1-31"), "PKSCHED4 fairness policy changed")
    _require(tuple(int(fairness.group(name), 10) for name in ("bypass", "starvation", "lost", "duplicate", "dead", "inversion")) == (1, 7, 0, 0, 0, 0), "PKSCHED4 fairness receipt changed")
    _require(tuple(int(rollback.group(name), 10) for name in ("cpu", "timeouts", "rollbacks", "stale", "late", "generation", "source", "target")) == (4, 1, 1, 2, 1, 1, 1, 1), "PKSCHED4 rollback receipt changed")
    _require(tuple(int(cleanup.group(name), 10) for name in ("dead", "idle", "epochs", "resource", "frames", "total", "zeroed", "verified", "queues", "running", "lock", "capability", "runtime", "mmio", "pic", "hpet")) == (8, 4, 19, 96, 6, 102, 417792, 417792, 0, 0, 1, 1, 1, 1, 1, 1), "PKSCHED4 cleanup receipt changed")
    _require((cleanup.group("online"), cleanup.group("parked")) == ("0x0000000000000001", "0x000000000000000E"), "PKSCHED4 cleanup masks changed")
    _require(tuple(int(result.group(name), 10) for name in ("ap", "wake", "migration", "general", "ring3", "spaces", "xstate", "target", "signatures", "authority", "actions", "n12", "production")) == (1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0), "PKSCHED4 claim boundary changed")
    return {
        "transfer_prefix": prefix,
        "topology": {"processor_count": 4, "target_apic_ids": [1, 2, 3], "online_mask": 15, "balance": list(oracle["balance"])},
        "transfers": {"remote_wakes": 1, "migrations": 2, "transaction_acks": 3, "remote_acks": 9},
        "dispatch": {"bsp": 2, "aps": 6, "trace": oracle, "call_function_executions": 9},
        "rollback": {"offline_cpu": 4, "timeouts": 1, "rollbacks": 1, "stale_rejections": 2},
        "cleanup": {"tasks_dead": 8, "idle_owners": 4, "pages_released": 102, "bytes_verified": 417792},
        "result": {"bounded_live_ap_scheduler": 1, "general_smp": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
