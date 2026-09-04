"""Independent PKATOM1 type, memory-order, litmus, and marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_interrupt_time, native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKATOM1"
SELECTED_MOVE_ID = "N12-CONCURRENCY-ATOMICS-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-atomics-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-atomics-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-atomics-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-atomics-readiness.schema.json"
FEATURE = "development-atomics"
SELECTOR = 21
MARKER_COUNT = 41
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:ATOMICS-RESULT PASS contract=PKATOM1"

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
    "native/kernel/src/atomics.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/bin/pkatom1_probe.rs",
    "native/kernel/src/interrupt_time.rs",
    "runtime/native_kernel_atomics.py",
    "runtime/native_kernel_interrupt_time.py",
    "specs/native-kernel-atomics-contract.json",
    "specs/native-kernel-atomics-contract.schema.json",
    "specs/native-kernel-atomics-readiness.schema.json",
    "tools/qualify_native_kernel_atomics.py",
    "tools/qualify_native_pooleboot.py",
    "tests/test_native_kernel_atomics.py",
    "docs/native-kernel-atomics.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N12-PKATOM1-MARKER-OMISSION",
    "NEG-N12-PKATOM1-MARKER-ORDER",
    "NEG-N12-PKATOM1-MARKER-DUPLICATE",
    "NEG-N12-PKATOM1-SELECTOR",
    "NEG-N12-PKATOM1-TYPES-FIELD-MATRIX",
    "NEG-N12-PKATOM1-ORDERS-FIELD-MATRIX",
    "NEG-N12-PKATOM1-OPS-FIELD-MATRIX",
    "NEG-N12-PKATOM1-IRQ-FIELD-MATRIX",
    "NEG-N12-PKATOM1-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N12-PKATOM1-PROBE-OMISSION",
    "NEG-N12-PKATOM1-PROBE-ORDER",
    "NEG-N12-PKATOM1-PROBE-FIELD-MATRIX",
    "NEG-N12-PKATOM1-ORDER-ORACLE",
    "NEG-N12-PKATOM1-INVALID-LOAD",
    "NEG-N12-PKATOM1-INVALID-STORE",
    "NEG-N12-PKATOM1-INVALID-FENCE",
    "NEG-N12-PKATOM1-CAS-FAILURE-STRENGTH",
    "NEG-N12-PKATOM1-PUBLICATION-STALE",
    "NEG-N12-PKATOM1-FETCH-ADD-LOSS",
    "NEG-N12-PKATOM1-CAS-LOSS",
    "NEG-N12-PKATOM1-SEQCST-FORBIDDEN",
    "NEG-N12-PKATOM1-ASSEMBLY-SYMBOL",
    "NEG-N12-PKATOM1-ASSEMBLY-INSTRUCTION",
    "NEG-N12-PKATOM1-INTERRUPT-PUBLICATION",
    "NEG-N12-PKATOM1-INTERRUPT-RMW",
    "NEG-N12-PKATOM1-INTERRUPT-EOI",
    "NEG-N12-PKATOM1-DYNAMIC-STORAGE",
    "NEG-N12-PKATOM1-PRODUCTION-OVERCLAIM",
    "NEG-N12-PKATOM1-INPUT-BINDING",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:ATOMICS-EARLY PASS contract=PKATOM1 selector=(?P<selector>[0-9]+) "
    r"parent_irq=(?P<irq>PKIRQ1) parent_sched=(?P<sched>PKSCHED6) bsp=(?P<bsp>[01]) "
    r"if=(?P<iflag>[01]) stack=validated_by_wrapper serial=initialized$"
)
TYPES = re.compile(
    r"^POOLEOS:KERNEL:ATOMICS-TYPES PASS contract=PKATOM1 integer=(?P<integer>[a-z0-9,]+) "
    r"pointer=(?P<pointer>[a-z]+) intrinsics=(?P<intrinsics>[a-z]+) target=(?P<target>[a-z0-9_]+) "
    r"widths=(?P<widths>[a-z0-9,]+)$"
)
ORDERS = re.compile(
    r"^POOLEOS:KERNEL:ATOMICS-ORDERS PASS contract=PKATOM1 load=(?P<load>[0-9]+) "
    r"store=(?P<store>[0-9]+) rmw=(?P<rmw>[0-9]+) fence=(?P<fence>[0-9]+) "
    r"cas_pairs=(?P<cas>[0-9]+) invalid_rejected=(?P<invalid>[0-9]+) "
    r"compiler_order=(?P<compiler>[a-z]+) x86_tso=(?P<tso>[a-z]+)$"
)
OPS = re.compile(
    r"^POOLEOS:KERNEL:ATOMICS-OPS PASS contract=PKATOM1 load_store=(?P<load_store>[01]) "
    r"exchange=(?P<exchange>[01]) compare_exchange=(?P<cas>[01]) fetch_add_sub=(?P<add_sub>[01]) "
    r"bit_modify=(?P<bits>[01]) pointer=(?P<pointer>[01]) refcount=(?P<refcount>[01]) "
    r"overflow_rejected=(?P<overflow>[01]) underflow_rejected=(?P<underflow>[01]) "
    r"audit_symbols=(?P<symbols>[0-9]+)$"
)
IRQ = re.compile(
    r"^POOLEOS:KERNEL:ATOMICS-IRQ PASS contract=PKATOM1 timer_deliveries=(?P<deliveries>[0-9]+) "
    r"atomic_updates=(?P<updates>[0-9]+) observed_mask=(?P<mask>0x[0-9A-F]{8}) "
    r"publication=(?P<publication>0x[0-9A-F]{16}) release_acquire=(?P<release_acquire>[01]) "
    r"eoi_ordered=(?P<eoi>[01]) cleanup=(?P<cleanup>[01])$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:ATOMICS-RESULT PASS contract=PKATOM1 profile=(?P<profile>qemu64_bsp_interrupt) "
    r"typed_atomics=(?P<typed>[01]) invalid_orders=(?P<invalid>[0-9]+) live_interrupt=(?P<interrupt>[01]) "
    r"host_smp_litmus=(?P<host>[a-z]+) linked_instruction_audit=(?P<linked>[a-z]+) "
    r"general_locks=(?P<locks>[01]) reclamation=(?P<reclamation>[01]) general_smp=(?P<smp>[01]) "
    r"ring3=(?P<ring3>[01]) target=(?P<target>[01]) signatures=(?P<signatures>[0-9]+) "
    r"authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) n12_exit=(?P<n12>[01]) "
    r"production=(?P<production>[01]) terminal=(?P<terminal>halt)$"
)

PROBE_PATTERNS = (
    re.compile(r"^PKATOM1:TYPES PASS integer=u32,u64,usize pointer=typed atomics=4 target=x86_64$"),
    re.compile(r"^PKATOM1:ORDERS PASS load=3 store=3 rmw=5 fence=4 cas_pairs=9 invalid_rejected=11$"),
    re.compile(r"^PKATOM1:OPS PASS exchange_old=9 cas_old=11 add_old=13 sub_old=18 or_old=16 xor_old=48 and_old=32 final=0 bit_set_clear=1 usize_final=5$"),
    re.compile(r"^PKATOM1:POINTER PASS typed=1 exchange=1 compare_exchange=1 null_terminal=1$"),
    re.compile(r"^PKATOM1:REFCOUNT PASS start=1 peak=2 terminal=0 overflow_rejected=1 underflow_rejected=1 max=4294967294$"),
    re.compile(r"^PKATOM1:PUBLICATION PASS rounds=4096 published=4096 stale=0 release_acquire=1$"),
    re.compile(r"^PKATOM1:CONTENTION PASS threads=4 fetch_add_rounds=4096 fetch_add_final=16384 cas_rounds=1024 cas_final=4096 lost=0$"),
    re.compile(r"^PKATOM1:SEQCST PASS rounds=2048 both_zero_forbidden=2048 observed_forbidden=0$"),
)


class KernelAtomicsError(RuntimeError):
    """Raised when PKATOM1 evidence violates the bounded contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelAtomicsError(message)


def _match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(value)
    _require(match is not None, f"PKATOM1 {label} violates its contract")
    assert match is not None
    return match


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelAtomicsError(f"JSON object required: {path.name}")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    try:
        canonical = path.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise KernelAtomicsError("binding path escapes repository") from error
    data = path.read_bytes()
    return {"path": canonical, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, item) for item in IMPLEMENTATION_INPUTS]}


def expected_claims() -> dict[str, bool]:
    return {
        "typed_integer_atomics_implemented": True,
        "typed_pointer_atomics_implemented": True,
        "invalid_memory_orders_rejected": True,
        "overflow_safe_reference_count_implemented": True,
        "release_acquire_publication_litmus_verified": True,
        "contended_rmw_and_cas_litmus_verified": True,
        "sequential_consistency_litmus_verified": True,
        "linked_x86_64_instruction_mapping_verified": True,
        "live_bsp_interrupt_context_verified": True,
        "live_multi_ap_atomic_litmus_verified": False,
        "general_lock_family_implemented": False,
        "deferred_reclamation_implemented": False,
        "non_x86_portability_verified": False,
        "physical_target_tested": False,
        "n12_exit_gate_satisfied": False,
        "production_ready": False,
    }


def order_matrix_oracle() -> dict[str, Any]:
    orders = ("relaxed", "acquire", "release", "acq_rel", "seq_cst")
    loads = {"relaxed", "acquire", "seq_cst"}
    stores = {"relaxed", "release", "seq_cst"}
    fences = {"acquire", "release", "acq_rel", "seq_cst"}
    failures = ("relaxed", "acquire", "seq_cst")
    allowed_failure = {
        "relaxed": {"relaxed"},
        "acquire": {"relaxed", "acquire"},
        "release": {"relaxed"},
        "acq_rel": {"relaxed", "acquire"},
        "seq_cst": set(failures),
    }
    cas_pairs = sum(failure in allowed_failure[success] for success in orders for failure in failures)
    rejected = (
        len(set(orders) - loads)
        + len(set(orders) - stores)
        + len(set(orders) - fences)
        + len(orders) * len(failures)
        - cas_pairs
    )
    return {
        "load_orders": len(loads),
        "store_orders": len(stores),
        "rmw_orders": len(orders),
        "fence_orders": len(fences),
        "compare_exchange_pairs": cas_pairs,
        "rejected_combinations": rejected,
        "allowed_failure": {key: sorted(value) for key, value in allowed_failure.items()},
    }


def operation_oracle() -> dict[str, int]:
    value = 9
    exchange_old, value = value, 11
    compare_old, value = value, 13
    add_old, value = value, value + 5
    sub_old, value = value, value - 2
    or_old, value = value, value | 0x20
    xor_old, value = value, value ^ 0x10
    and_old, value = value, value & 0x1F
    return {
        "exchange_old": exchange_old,
        "compare_old": compare_old,
        "add_old": add_old,
        "sub_old": sub_old,
        "or_old": or_old,
        "xor_old": xor_old,
        "and_old": and_old,
        "final": value,
    }


def validate_order_request(operation: str, success: str, failure: str | None = None) -> dict[str, str]:
    matrix = order_matrix_oracle()
    operation_orders = {
        "load": {"relaxed", "acquire", "seq_cst"},
        "store": {"relaxed", "release", "seq_cst"},
        "rmw": {"relaxed", "acquire", "release", "acq_rel", "seq_cst"},
        "fence": {"acquire", "release", "acq_rel", "seq_cst"},
    }
    _require(operation in {*operation_orders, "compare_exchange"}, "PKATOM1 operation is unknown")
    if operation == "compare_exchange":
        _require(success in operation_orders["rmw"], "PKATOM1 compare-exchange success order is invalid")
        _require(failure is not None, "PKATOM1 compare-exchange failure order is missing")
        allowed = matrix["allowed_failure"][success]
        _require(failure in allowed, "PKATOM1 compare-exchange failure order is invalid")
        return {"operation": operation, "success": success, "failure": failure}
    _require(failure is None, "PKATOM1 non-CAS operation has a failure order")
    _require(success in operation_orders[operation], f"PKATOM1 {operation} order is invalid")
    return {"operation": operation, "success": success}


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    issues = validate_json(contract, read_json(root / CONTRACT_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("required negative controls diverge")
    if contract.get("claims") != expected_claims():
        errors.append("claim boundary diverges")
    if contract.get("order_matrix") != order_matrix_oracle():
        errors.append("order matrix diverges from independent oracle")
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


def parse_probe_output(output: str) -> dict[str, Any]:
    lines = [
        line.strip()
        for line in output.replace("\r\n", "\n").splitlines()
        if line.startswith("PKATOM1:")
    ]
    _require(len(lines) == len(PROBE_PATTERNS), "PKATOM1 host probe line count changed")
    for index, (pattern, line) in enumerate(zip(PROBE_PATTERNS, lines, strict=True), 1):
        _match(pattern, line, f"probe line {index}")
    return {
        "lines": lines,
        "receipt_count": len(lines),
        "order_matrix": order_matrix_oracle(),
        "operation_oracle": operation_oracle(),
        "publication_rounds": 4096,
        "contended_operation_count": 20_480,
        "sequential_consistency_rounds": 2048,
        "forbidden_observations": 0,
        "rust_python_exact_agreement": True,
    }


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _synthetic_irq_markers(markers: list[str]) -> list[str]:
    base = markers[:36]
    base[23] = re.sub(r"trap_scenario=21", "trap_scenario=11", base[23], count=1)
    base[25] = (
        "POOLEOS:KERNEL:IRQ-EARLY PASS contract=PKIRQ1 selector=11 bsp=1 if=0 "
        "stack=validated_by_wrapper serial=initialized"
    )
    return base


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKATOM1 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10)) == SELECTOR, "PKATOM1 transfer selector changed")
    irq_summary = native_kernel_interrupt_time.validate_markers(_synthetic_irq_markers(markers))
    irq_summary["transfer_prefix"]["transfer_arm"]["trap_scenario"] = SELECTOR

    early = _match(EARLY, markers[25], "early marker")
    types = _match(TYPES, markers[36], "types marker")
    orders = _match(ORDERS, markers[37], "orders marker")
    operations = _match(OPS, markers[38], "operations marker")
    irq = _match(IRQ, markers[39], "interrupt marker")
    result = _match(RESULT, markers[40], "result marker")

    _require(
        tuple(int(early.group(name)) for name in ("selector", "bsp", "iflag")) == (21, 1, 0),
        "PKATOM1 early state changed",
    )
    _require(
        (types.group("integer"), types.group("pointer"), types.group("intrinsics"), types.group("target"), types.group("widths"))
        == ("u32,u64,usize", "typed", "core", "x86_64", "32,64,native"),
        "PKATOM1 type surface changed",
    )
    matrix = order_matrix_oracle()
    _require(
        tuple(int(orders.group(name)) for name in ("load", "store", "rmw", "fence", "cas", "invalid"))
        == (3, 3, 5, 4, 9, 11)
        and (orders.group("compiler"), orders.group("tso")) == ("explicit", "documented"),
        "PKATOM1 memory-order matrix changed",
    )
    _require(
        tuple(int(operations.group(name)) for name in ("load_store", "exchange", "cas", "add_sub", "bits", "pointer", "refcount", "overflow", "underflow", "symbols"))
        == (1, 1, 1, 1, 1, 1, 1, 1, 1, 7),
        "PKATOM1 operation coverage changed",
    )
    _require(
        tuple(int(irq.group(name)) for name in ("deliveries", "updates", "release_acquire", "eoi", "cleanup"))
        == (8, 8, 1, 1, 1)
        and irq.group("mask") == "0x000000FF"
        and irq.group("publication") == "0x00000000C0DEC0DE",
        "PKATOM1 interrupt evidence changed",
    )
    _require(
        tuple(int(result.group(name)) for name in ("typed", "invalid", "interrupt", "locks", "reclamation", "smp", "ring3", "target", "signatures", "authority", "actions", "n12", "production"))
        == (1, 11, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        and (result.group("host"), result.group("linked"), result.group("terminal"))
        == ("external", "external", "halt"),
        "PKATOM1 claim boundary changed",
    )
    return {
        "transfer_prefix": irq_summary["transfer_prefix"],
        "interrupt_parent": irq_summary,
        "types": {"integer": ["u32", "u64", "usize"], "pointer": "typed"},
        "order_matrix": matrix,
        "operations": {"families": 9, "audit_symbols": 7},
        "interrupt": {
            "timer_deliveries": 8,
            "atomic_updates": 8,
            "observed_mask": "0x000000FF",
            "publication": "0x00000000C0DEC0DE",
            "cleanup": 1,
        },
        "result": {"live_interrupt": 1, "general_smp": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    return markers.copy()
