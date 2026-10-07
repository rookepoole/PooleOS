"""Independent PKATOM1 type, memory-order, litmus, and marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from runtime import native_kernel_interrupt_time, native_kernel_load, native_kernel_transfer, native_pooleboot
from runtime.schema_validation import validate_json
from runtime.native_kernel_profile_evidence import kernel_entry_errors, recorded_pair_errors


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
    "runtime/native_kernel_profile_evidence.py",
    "tests/test_native_memory_entry_provenance.py",
    "tests/test_native_cpu_entry_provenance.py",
    "tests/test_native_atomics_admission.py",
    "runs/native_kernel_entry_readiness.json",
    "runs/native_pooleboot_readiness.json",
    "specs/native-tier0-lock.json",
    "runtime/native_pooleboot.py",
    "runtime/native_kernel_load.py",
    "runtime/native_kernel_transfer.py",
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

CONTROL_CASE_COUNTS = (1, 1, 1, 1, 5, 8, 10, 7, 17, 1, 1, 8, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
SOURCE_AUDIT_PATHS = {
    "core": "native/kernel/src/atomics.rs", "main": "native/kernel/src/main.rs",
    "kernel_lib": "native/kernel/src/lib.rs", "boot_exit": "native/boot/src/exit.rs",
    "boot_manifest": "native/boot/Cargo.toml", "bootexit": "native/bootexit/src/lib.rs",
}
INSTRUCTION_RULES = {
    "poole_atomic_audit_load_acquire": (("movq", "retq"), ("lock", "xchg", "cmpxchg")),
    "poole_atomic_audit_store_release": (("movq", "retq"), ("lock", "xchg", "cmpxchg")),
    "poole_atomic_audit_exchange_seqcst": (("xchgq", "retq"), ("call",)),
    "poole_atomic_audit_compare_exchange_acqrel": (("lock", "cmpxchgq", "retq"), ("call",)),
    "poole_atomic_audit_fetch_add_relaxed": (("lock", "xaddq", "retq"), ("call",)),
    "poole_atomic_audit_fetch_or_acqrel": (("orq", "lock", "cmpxchgq", "jne", "retq"), ("call",)),
    "poole_atomic_audit_fence_seqcst": (("lock", "orl", "retq"), ("call",)),
}

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


def _typed_equal(actual: Any, expected: Any, label: str) -> None:
    _require(json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False),
             f"recorded {label} differs from parsed evidence or exact types")


def expected_controls() -> list[dict[str, Any]]:
    return [{"id": name, "status": "pass", "expected": "rejected", "case_count": count}
            for name, count in zip(NEGATIVE_CONTROL_IDS, CONTROL_CASE_COUNTS, strict=True)]


def audit_instruction_bodies(bodies: dict[str, str]) -> dict[str, Any]:
    """Check the pinned LLVM lowering, including bytes, operands and control flow."""
    _require(set(bodies) == set(INSTRUCTION_RULES), "PKATOM1 linked symbol set changed")
    prologue = [("55", "pushq", "%rbp"), ("4889e5", "movq", "%rsp, %rbp")]
    epilogue = [("5d", "popq", "%rbp"), ("c3", "retq", "")]
    accumulator = ("4889f0", "movq", "%rsi, %rax")
    lock = ("f0", "lock", "")
    middles = {
        "load_acquire": [("488b07", "movq", "(%rdi), %rax")],
        "store_release": [("488937", "movq", "%rsi, (%rdi)")],
        "exchange_seqcst": [accumulator, ("488707", "xchgq", "%rax, (%rdi)")],
        "compare_exchange_acqrel": [accumulator, lock, ("480fb117", "cmpxchgq", "%rdx, (%rdi)")],
        "fetch_add_relaxed": [accumulator, lock, ("480fc107", "xaddq", "%rax, (%rdi)")],
        "fetch_or_acqrel": [("488b07", "movq", "(%rdi), %rax"), ("4889c1", "movq", "%rax, %rcx"),
                            ("4809f1", "orq", "%rsi, %rcx"), lock, ("480fb10f", "cmpxchgq", "%rcx, (%rdi)"),
                            ("75f3", "jne", "retry")],
        "fence_seqcst": [lock, ("830c2400", "orl", "$0x0, (%rsp)")],
    }
    line_pattern = re.compile(r"\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)([a-z][a-z0-9]*)\s*(.*?)\s*", re.I)
    observations = []
    for symbol, (required, forbidden) in INSTRUCTION_RULES.items():
        body = bodies[symbol]
        _require(isinstance(body, str) and bool(body), "PKATOM1 missing instruction body")
        parsed = []
        end = None
        for line in body.splitlines():
            match = line_pattern.fullmatch(line)
            _require(match is not None, f"PKATOM1 non-instruction line in {symbol}")
            assert match is not None
            address = int(match[1], 16)
            encoded = bytes.fromhex(match[2])
            _require(end is None or address == end, f"PKATOM1 discontinuous instructions in {symbol}")
            end = address + len(encoded)
            parsed.append((address, encoded.hex(), match[3], match[4]))
        expected = prologue + middles[symbol.removeprefix("poole_atomic_audit_")] + epilogue
        _require(len(parsed) == len(expected), f"PKATOM1 instruction count changed for {symbol}")
        for (address, encoded, mnemonic, operands), (wanted_bytes, wanted_mnemonic, wanted_operands) in zip(parsed, expected, strict=True):
            if wanted_operands == "retry":
                target = parsed[0][0] + 7
                wanted_operands = f"0x{target:x} <{symbol}+0x7>"
                _require(address + 2 - 13 == target, "PKATOM1 retry branch displacement changed")
            _require((encoded, mnemonic, operands) == (wanted_bytes, wanted_mnemonic, wanted_operands),
                     f"PKATOM1 instruction bytes, operation or operands changed for {symbol}")
        observations.append({"symbol": symbol, "required_instruction_classes": list(required),
                             "forbidden_instruction_classes": list(forbidden), "body": body,
                             "body_sha256": sha256_bytes(body.encode("utf-8"))})
    return {"target": "x86_64-unknown-none", "symbol_count": len(observations), "symbols": observations,
            "all_instruction_rules_passed": True}


def canonical_disassembly_bytes(symbols: list[dict[str, Any]]) -> bytes:
    return native_pooleboot.canonical_json_bytes([{k: s[k] for k in ("symbol", "body")} for s in symbols])


def readiness_errors(readiness: Any, root: Path = ROOT) -> list[str]:
    if not isinstance(readiness, dict):
        return ["PKATOM1 readiness is not an object"]
    issues = validate_json(readiness, read_json(root / READINESS_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    summary = readiness.get("kernel_summary")
    embedded = summary.get("entry_readiness") if isinstance(summary, dict) else None
    errors.extend(kernel_entry_errors({"kernel_entry": embedded}, root))
    status_date = readiness.get("status_date")
    try:
        if not isinstance(status_date, str) or len(status_date) != 10 or date.fromisoformat(status_date).isoformat() != status_date:
            raise ValueError("noncanonical date")
    except ValueError:
        errors.append("readiness status_date is not a canonical calendar date")
    if errors:
        return errors
    try:
        _typed_equal(readiness["inputs"], expected_inputs(root), "input bindings")
        _typed_equal(readiness["negative_controls"], expected_controls(), "per-control accounting")
        _typed_equal(readiness["claims"], expected_claims(), "claim boundary")
        for key, value in (("production_ready", False), ("production_promotion_allowed", False),
                           ("n12_exit_gate_satisfied", False), ("flag_n12_concurrency_atomics_001_closed", True)):
            _typed_equal(readiness[key], value, key)
    except (KernelAtomicsError, TypeError, ValueError) as error:
        return [str(error)]
    errors.extend(recorded_atomics_errors(readiness, root))
    return errors


def recorded_atomics_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Reconstruct recorded consistency, not authentication or fresh execution."""
    def parsed(markers):
        try:
            return validate_markers(markers)
        except (KernelAtomicsError, native_kernel_interrupt_time.KernelInterruptTimeError) as error:
            raise ValueError(str(error)) from error

    try:
        execution = readiness["execution"]
        errors = recorded_pair_errors(execution, "atomics-run", parsed, CONTRACT_ID)
        if errors:
            return errors
        lock = read_json(root / "specs/native-tier0-lock.json")
        firmware = {item["role"]: item for item in lock["firmware"]["files"]}
        for key, expected in {
            "host_environment_count": 1, "run_count": 2, "machine": "pc-q35-11.0", "cpu_model": "qemu64",
            "acceleration": "tcg_single_thread", "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "fresh_vars_each_run": True, "media_read_only": True, "physical_media_write_performed": False,
            "guest_network": False, "host_acceleration": False, "markers_per_run": MARKER_COUNT,
        }.items():
            _typed_equal(execution.get(key), expected, "execution " + key)
        _typed_equal(execution["observation"], parsed(execution["runs"][0]["markers"]), "observation")
        probe = readiness["host_probe"]
        lines = probe["lines"]
        _require(isinstance(lines, list) and len(lines) == 8 and all(isinstance(s, str) for s in lines), "host lines malformed")
        output = "\n".join(lines) + "\n"
        _typed_equal(probe, dict(parse_probe_output(output), output_sha256=sha256_bytes(output.encode("utf-8")),
                                 target="x86_64-pc-windows-msvc"), "host probe")
        summary = readiness["kernel_summary"]
        entry = summary["entry_readiness"]
        for key, expected in (("host_tests_passed", entry["host_tests"]["test_pass_count"]),
                              ("host_tests_total", entry["host_tests"]["test_count"]),
                              ("canonical_sha256", entry["product"]["canonical_sha256"])):
            _typed_equal(summary.get(key), expected, "kernel " + key)
        files = {name: {k: v for k, v in file_binding(root, p).items() if k != "byte_count"}
                 for name, p in SOURCE_AUDIT_PATHS.items()}
        maximum = re.search(r"MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = (\d+);", (root / SOURCE_AUDIT_PATHS["bootexit"]).read_text())
        _require(maximum is not None, "development selector maximum missing")
        _typed_equal(summary["source_audit"], {
            "heap_api_token_count": 0, "typed_order_enum_count": 4, "atomic_wrapper_count": 4,
            "audit_symbol_count": 7, "unit_test_count": 7, "interrupt_retry_loop_count": 0,
            "atomics_selector": SELECTOR, "max_development_trap_scenario": int(maximum.group(1)),
            "result": "pass_allocation_free_typed_atomic_source_audit", "files": files,
        }, "source audit")
        linked = readiness["linked_instruction_audit"]
        symbols = linked["symbols"]
        _require(isinstance(symbols, list) and len(symbols) == 7, "linked symbol count changed")
        audit = audit_instruction_bodies({s["symbol"]: s["body"] for s in symbols})
        tool = "lib/rustlib/x86_64-pc-windows-msvc/bin/llvm-objdump.exe"
        tool_path = root / ".toolchains/rust-1.97.0/rustup/toolchains/1.97.0-x86_64-pc-windows-msvc" / tool
        _typed_equal(linked, {**audit, **{k: entry["product"][k] for k in (
            "canonical_sha256", "canonical_byte_count", "linked_sha256", "linked_byte_count", "image_byte_count")},
            "tool": {"path": "$RUST_TOOLCHAIN/" + tool, "sha256": sha256_bytes(tool_path.read_bytes())},
            "disassembly_scope": "canonical_symbol_bodies_not_raw_tool_header",
            "disassembly_sha256": sha256_bytes(canonical_disassembly_bytes(audit["symbols"])),
        }, "linked instruction audit")
        default = read_json(root / "runs/native_pooleboot_readiness.json")
        _require(not native_pooleboot.readiness_contract_errors(default, root), "default PooleBoot dependency invalid")
        _typed_equal(summary["default_pooleboot"], default["build"], "default PooleBoot")
        boot = summary["atomics_pooleboot"]
        inspection = execution["media"]["inspection"]
        expected_boot = dict(default["build"], development_transfer_feature=True, selected_development_feature=FEATURE,
                             inspection=inspection["embedded_efi"], sha256=inspection["embedded_efi"]["sha256"],
                             byte_count=inspection["embedded_efi"]["byte_count"])
        _typed_equal(boot, expected_boot, "atomics PooleBoot")
        _require(boot["sha256"] != default["build"]["sha256"], "atomic and default binaries are identical")
        media = execution["media"]
        _typed_equal(media, {"inspection": inspection, "clean_generation_count": 2, "exact_clean_generation_match": True,
                             "sha256": inspection["image"]["sha256"], "byte_count": inspection["image"]["byte_count"]}, "media")
        _require(re.fullmatch(r"[0-9A-F]{64}", media["sha256"]) is not None, "media digest malformed")
        for key, expected in (("byte_count", 67108864), ("sector_count", 131072), ("sector_bytes", 512), ("protective_mbr_valid", True)):
            _typed_equal(inspection["image"][key], expected, "media image " + key)
        kernel_files = [item for item in inspection["files"] if item["path"] == "EFI/POOLEOS/KERNEL.ELF"]
        _require(len(kernel_files) == 1, "media kernel coverage changed")
        for key, field in (("sha256", "canonical_sha256"), ("byte_count", "canonical_byte_count")):
            _typed_equal(kernel_files[0][key], entry["product"][field], "media kernel " + key)
        _typed_equal(inspection["kernel"]["loaded_sha256"], entry["product"]["loaded_sha256"], "loaded kernel")
        for run in execution["runs"]:
            native_kernel_load.validate_oracle_binding(parsed(run["markers"])["transfer_prefix"]["boot_prefix"],
                                                       inspection, run["pbp1_transcript"])
    except (KernelAtomicsError, native_kernel_load.KernelLoadError, native_kernel_transfer.KernelTransferError,
            KeyError, TypeError, ValueError, AttributeError, OSError) as error:
        return [f"PKATOM1 recorded accounting is invalid: {error}"]
    return []


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
