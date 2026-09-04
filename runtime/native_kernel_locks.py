"""Independent PKLOCK1 lock-family, host-probe, and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKLOCK1"
SELECTED_MOVE_ID = "N12-CONCURRENCY-LOCKS-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-locks-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-locks-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-locks-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-locks-readiness.schema.json"
FEATURE = "development-locks"
SELECTOR = 22
MARKER_COUNT = 35
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:LOCKS-RESULT PASS contract=PKLOCK1"

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
    "native/kernel/src/atomics.rs",
    "native/kernel/src/locks.rs",
    "native/kernel/src/scheduler.rs",
    "native/kernel/src/smp_ipi.rs",
    "native/kernel/src/bin/pklock1_probe.rs",
    "runtime/native_kernel_locks.py",
    "specs/native-kernel-locks-contract.json",
    "specs/native-kernel-locks-contract.schema.json",
    "specs/native-kernel-locks-readiness.schema.json",
    "tools/qualify_native_kernel_locks.py",
    "tools/qualify_native_pooleboot.py",
    "tests/test_native_kernel_locks.py",
    "docs/native-kernel-locks.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKLOCK1-MARKER-OMISSION",
    "NEG-N12-PKLOCK1-MARKER-ORDER",
    "NEG-N12-PKLOCK1-MARKER-DUPLICATE",
    "NEG-N12-PKLOCK1-SELECTOR",
    "NEG-N12-PKLOCK1-FAMILY-FIELD-MATRIX",
    "NEG-N12-PKLOCK1-POLICY-FIELD-MATRIX",
    "NEG-N12-PKLOCK1-LIVE-FIELD-MATRIX",
    "NEG-N12-PKLOCK1-HOST-FIELD-MATRIX",
    "NEG-N12-PKLOCK1-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKLOCK1-PROBE-OMISSION",
    "NEG-N12-PKLOCK1-PROBE-ORDER",
    "NEG-N12-PKLOCK1-PROBE-STATUS-MATRIX",
    "NEG-N12-PKLOCK1-TICKET-FIFO",
    "NEG-N12-PKLOCK1-IRQ-RESTORE",
    "NEG-N12-PKLOCK1-IRQ-NESTING",
    "NEG-N12-PKLOCK1-MUTEX-FAIRNESS",
    "NEG-N12-PKLOCK1-PRIORITY-INHERITANCE",
    "NEG-N12-PKLOCK1-OWNER-DEATH",
    "NEG-N12-PKLOCK1-NOTIFICATION-FIFO",
    "NEG-N12-PKLOCK1-NOTIFICATION-TIMEOUT-CANCEL",
    "NEG-N12-PKLOCK1-RW-FINAL",
    "NEG-N12-PKLOCK1-WRITER-PREFERENCE",
    "NEG-N12-PKLOCK1-SEQ-FINAL",
    "NEG-N12-PKLOCK1-SEQ-ODD-SNAPSHOT",
    "NEG-N12-PKLOCK1-ORDER-CYCLE",
    "NEG-N12-PKLOCK1-RECURSION",
    "NEG-N12-PKLOCK1-TIMEOUT-ROLLBACK",
    "NEG-N12-PKLOCK1-DYNAMIC-STORAGE",
    "NEG-N12-PKLOCK1-INPUT-BINDING",
    "NEG-N12-PKLOCK1-PRODUCTION-OVERCLAIM",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:LOCKS-EARLY PASS contract=PKLOCK1 selector=(?P<selector>[0-9]+) "
    r"parent_atomics=(?P<atomics>PKATOM1) parent_sched=(?P<sched>PKSCHED6) "
    r"parent_smp=(?P<smp>PKSMP5) bsp=(?P<bsp>[01]) if=(?P<iflag>[01]) "
    r"stack=validated_by_wrapper serial=initialized$"
)
FAMILY = re.compile(
    r"^POOLEOS:KERNEL:LOCKS-FAMILY PASS contract=PKLOCK1 raw_spin=(?P<raw>[a-z]+) "
    r"irqsave_spin=(?P<irq>[01]) sleeping_mutex=(?P<mutex>[01]) notification=(?P<notify>[01]) "
    r"rwlock=(?P<rw>[a-z_]+) seqlock=(?P<seq>[01]) allocation=(?P<allocation>[a-z]+) "
    r"rank_count=(?P<ranks>[0-9]+)$"
)
POLICY = re.compile(
    r"^POOLEOS:KERNEL:LOCKS-POLICY PASS contract=PKLOCK1 try=(?P<try_path>[01]) "
    r"timed=(?P<timed>[01]) owner=(?P<owner>[01]) recursion_rejected=(?P<recursion>[01]) "
    r"irq_nesting_rejected=(?P<irq>[01]) preempt_nesting_rejected=(?P<preempt>[01]) "
    r"priority_inheritance=(?P<pi>[a-z]+) maximum_bypass=(?P<bypass>[0-9]+) "
    r"deadlock_graph=(?P<graph>[01]) owner_death=(?P<death>[01]) exact_rollback=(?P<rollback>[01])$"
)
LIVE = re.compile(
    r"^POOLEOS:KERNEL:LOCKS-LIVE PASS contract=PKLOCK1 "
    r"profile=(?P<profile>sandybridge_four_vcpu_ticket_contention) next=(?P<next>[0-9]+) "
    r"serving=(?P<serving>[0-9]+) acquisitions=(?P<acquisitions>[0-9]+) "
    r"cpu_mask=(?P<mask>0x[0-9A-F]{16}) tickets=(?P<tickets>[0-9,]+) "
    r"mappings_installed=(?P<installed>[0-9]+) mappings_revoked=(?P<revoked>[0-9]+) "
    r"queue_drained=(?P<drained>[01]) owner=(?P<owner>[0-9]+) "
    r"unique_tickets=(?P<unique>[0-9]+) exact_topology=(?P<topology>[01])$"
)
HOST = re.compile(
    r"^POOLEOS:KERNEL:LOCKS-HOST PASS contract=PKLOCK1 "
    r"exact_four_thread=(?P<threads>[a-z]+) scheduler_sleep_path=(?P<scheduler>[a-z]+) "
    r"fairness=(?P<fairness>[a-z]+) rw_contention=(?P<rw>[a-z]+) "
    r"seqlock_contention=(?P<seq>[a-z]+) hostile_controls=(?P<controls>[a-z]+)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:LOCKS-RESULT PASS contract=PKLOCK1 "
    r"profile=(?P<profile>bounded_x86_64_four_vcpu) lock_family=(?P<family>[01]) "
    r"live_multi_ap_contention=(?P<live>[01]) host_concurrency=(?P<host>[a-z]+) "
    r"scheduler_sleep=(?P<scheduler>[a-z]+) reclamation=(?P<reclamation>[01]) "
    r"general_smp=(?P<smp>[01]) ring3=(?P<ring3>[01]) address_spaces=(?P<spaces>[0-9]+) "
    r"target=(?P<target>[01]) signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) "
    r"actions=(?P<actions>[0-9]+) n12_exit=(?P<n12>[01]) production=(?P<production>[01]) "
    r"terminal=(?P<terminal>halt)$"
)

PROBE_PATTERNS = (
    re.compile(
        r"^PKLOCK1:SURFACE PASS primitives=raw_spin,irqsave_spin,sleep_mutex,notification,rwlock,seqlock "
        r"allocation=none atomics=PKATOM1$"
    ),
    re.compile(
        r"^PKLOCK1:TICKET PASS threads=4 rounds=2048 acquisitions=8192 protected=8192 "
        r"fifo_mismatches=0 forced_contention=1 timeouts=0$"
    ),
    re.compile(
        r"^PKLOCK1:IRQSAVE PASS interrupts_restored=1 preemption_restored=1 "
        r"nested_irq_rejected=1 nested_preemption_rejected=1$"
    ),
    re.compile(
        r"^PKLOCK1:MUTEX PASS waiters=8 maximum_bypass=7 priority_inheritance=1 "
        r"handoff_order=3,4,5,6,7,8,9,2 owner_deaths=1 owner_death_wakes=2$"
    ),
    re.compile(r"^PKLOCK1:NOTIFY PASS waiters=4 wakes=4 fifo=1 sequence=4 timeout=1 cancel=1$"),
    re.compile(
        r"^PKLOCK1:RWLOCK PASS readers=3 writers=1 rounds=1024 final=1024 concurrent=1 "
        r"writer_timeouts=0 writer_preference=1$"
    ),
    re.compile(
        r"^PKLOCK1:SEQLOCK PASS readers=3 writers=1 rounds=2048 final=2048 sequence=4096 "
        r"concurrent=1 odd_snapshots=0$"
    ),
    re.compile(
        r"^PKLOCK1:ORDER PASS ranks=5 edges=4 cycles_rejected=1 inversion_rejected=1 "
        r"recursion_rejected=1$"
    ),
    re.compile(
        r"^PKLOCK1:ROLLBACK PASS next=2 serving=2 owner=0 cancelled=0 timeouts=1 exact=1$"
    ),
)


class KernelLocksError(RuntimeError):
    """Raised when PKLOCK1 evidence violates its bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelLocksError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKLOCK1 {label} violates its contract")
    assert match is not None
    return match


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelLocksError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelLocksError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_lock_family_implemented": True,
        "fifo_ticket_spinlock_verified": True,
        "irqsave_and_preemption_restore_verified": True,
        "sleeping_mutex_scheduler_path_verified": True,
        "bounded_priority_inheritance_and_fairness_verified": True,
        "notification_wait_wake_timeout_cancel_verified": True,
        "writer_preferred_reader_writer_lock_verified": True,
        "sequence_lock_retry_protocol_verified": True,
        "lock_order_recursion_and_nesting_rejection_verified": True,
        "owner_death_and_exact_rollback_verified": True,
        "host_four_thread_contention_verified": True,
        "live_four_vcpu_ticket_contention_verified": True,
        "deferred_reclamation_implemented": False,
        "general_smp_or_hotplug_implemented": False,
        "non_x86_portability_verified": False,
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
    if contract.get("production_ready") is not False:
        errors.append("contract overclaims production")
    if contract.get("production_promotion_allowed") is not False:
        errors.append("contract overclaims promotion")
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


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [
        line.strip()
        for line in output.replace("\r\n", "\n").splitlines()
        if line.startswith("PKLOCK1:")
    ]
    _require(len(lines) == len(PROBE_PATTERNS), "PKLOCK1 host probe line count changed")
    for index, (pattern, line) in enumerate(zip(PROBE_PATTERNS, lines, strict=True), 1):
        _match(pattern, line, f"probe line {index}")
    return {
        "lines": lines,
        "receipt_count": len(lines),
        "ticket_acquisitions": 8192,
        "maximum_mutex_bypass": 7,
        "reader_writer_rounds": 1024,
        "sequence_rounds": 2048,
        "rust_python_exact_agreement": True,
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
        raise KernelLocksError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKLOCK1 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10)) == SELECTOR, "PKLOCK1 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early marker")
    family = _match(FAMILY, markers[30], "family marker")
    policy = _match(POLICY, markers[31], "policy marker")
    live = _match(LIVE, markers[32], "live marker")
    host = _match(HOST, markers[33], "host marker")
    result = _match(RESULT, markers[34], "result marker")

    _require(
        tuple(int(early.group(name)) for name in ("selector", "bsp", "iflag")) == (22, 1, 0),
        "PKLOCK1 early state changed",
    )
    _require(
        (family.group("raw"), family.group("rw"), family.group("allocation"))
        == ("ticket", "writer_preferred", "none")
        and tuple(int(family.group(name)) for name in ("irq", "mutex", "notify", "seq", "ranks"))
        == (1, 1, 1, 1, 5),
        "PKLOCK1 family changed",
    )
    _require(
        tuple(
            int(policy.group(name))
            for name in ("try_path", "timed", "owner", "recursion", "irq", "preempt", "bypass", "graph", "death", "rollback")
        )
        == (1, 1, 1, 1, 1, 1, 7, 1, 1, 1)
        and policy.group("pi") == "bounded",
        "PKLOCK1 policy changed",
    )
    tickets = tuple(int(value) for value in live.group("tickets").split(","))
    _require(
        tuple(
            int(live.group(name))
            for name in ("next", "serving", "acquisitions", "installed", "revoked", "drained", "owner", "unique", "topology")
        )
        == (4, 4, 4, 3, 3, 1, 0, 4, 1)
        and live.group("mask") == "0x000000000000000F"
        and tickets == (0, 1, 2, 3),
        "PKLOCK1 live ticket receipt changed",
    )
    _require(
        tuple(host.group(name) for name in ("threads", "scheduler", "fairness", "rw", "seq", "controls"))
        == ("external",) * 6,
        "PKLOCK1 host evidence boundary changed",
    )
    _require(
        tuple(
            int(result.group(name))
            for name in ("family", "live", "reclamation", "smp", "ring3", "spaces", "target", "signatures", "authority", "actions", "n12", "production")
        )
        == (1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0)
        and (result.group("host"), result.group("scheduler"), result.group("terminal"))
        == ("external", "external", "halt"),
        "PKLOCK1 claim boundary changed",
    )
    return {
        "transfer_prefix": prefix,
        "family": {
            "raw_spin": "ticket",
            "irqsave_spin": True,
            "sleeping_mutex": True,
            "notification": True,
            "reader_writer": "writer_preferred",
            "sequence_lock": True,
        },
        "policy": {"maximum_bypass": 7, "rank_count": 5, "priority_inheritance": "bounded"},
        "live": {
            "virtual_cpu_count": 4,
            "application_processor_count": 3,
            "acquisitions": 4,
            "tickets": list(tickets),
            "mappings_installed": 3,
            "mappings_revoked": 3,
        },
        "result": {"reclamation": 0, "general_smp": 0, "physical_target": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
