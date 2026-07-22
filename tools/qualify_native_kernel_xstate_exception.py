#!/usr/bin/env python3
"""Build and qualify the bounded PKXEXC1 x87/SSE exception profile."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_kernel_load,
    native_kernel_transfer,
    native_kernel_xstate_exception as xstate_exception,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains/rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / xstate_exception.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKXEXC1 qualification fails closed."""


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(
            f"command failed ({completed.returncode}): {' '.join(command[:6])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return output


def _hex(value: int) -> str:
    return f"0x{value & ((1 << 64) - 1):016X}"


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKXEXC1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _require_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    try:
        xstate_exception.validate_markers(candidate)
    except xstate_exception.KernelXstateExceptionError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKXEXC1 hostile control did not reject: {control_id}")


def _source_audit(source: str | None = None) -> dict[str, Any]:
    if source is None:
        source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(
            encoding="utf-8"
        )
    lower = source.lower()
    parent_start = lower.index("unsafe fn write_cr0")
    parent_end = lower.index("pub unsafe fn observe_cpu_policy", parent_start)
    parent = lower[parent_start:parent_end]
    exception_start = lower.index("pub fn x87_exception_fault_address")
    exception_end = lower.index("core::arch::global_asm!", exception_start)
    helpers = lower[exception_start:exception_end]
    assembly_start = lower.index(".global poole_trigger_x87_exception", exception_end)
    assembly = lower[assembly_start:]
    outside = (
        lower[:parent_start]
        + lower[parent_end:exception_start]
        + lower[exception_end:assembly_start]
    )

    parent_required = {
        "cr0_write": '"mov cr0, {}"',
        "cr4_write": '"mov cr4, {}"',
        "xcr0_write": '"xsetbv"',
        "standard_save": '"xsave64 [{}]"',
        "standard_restore": '"xrstor64 [{}]"',
    }
    parent_counts = {
        name: parent.count(token) for name, token in parent_required.items()
    }
    if any(count != 1 for count in parent_counts.values()):
        raise QualificationError(
            f"PKXEXC1 parent source instruction audit failed: {parent_counts}"
        )
    exception_required = {
        "x87_fault": "fwait",
        "simd_fault": "divss xmm0, xmm1",
        "nm_fault": "fnop",
        "test_only_ts_write": "mov cr0, rax",
    }
    exception_counts = {
        name: assembly.count(token) for name, token in exception_required.items()
    }
    if any(count != 1 for count in exception_counts.values()):
        raise QualificationError(
            f"PKXEXC1 exception source instruction audit failed: {exception_counts}"
        )
    helper_required = {
        "x87_recovery": 'asm!("fninit"',
        "simd_recovery": "write_mxcsr(&canonical)",
    }
    helper_counts = {
        name: helpers.count(token) for name, token in helper_required.items()
    }
    if any(count != 1 for count in helper_counts.values()):
        raise QualificationError(
            f"PKXEXC1 recovery source instruction audit failed: {helper_counts}"
        )
    nm_start = assembly.index("poole_trigger_device_not_available_rejection:")
    nm_scope = assembly[nm_start:]
    if nm_scope.count("mov cr0, rax") != 1 or any(
        token in nm_scope
        for token in ("xsave", "xrstor", "fxsave", "fxrstor", "ldmxcsr", "stmxcsr")
    ):
        raise QualificationError("PKXEXC1 #NM source scope is not fail-closed")
    forbidden = ("wrmsr", "xsaves64", "xrstors64", "ymm", "zmm", "clts")
    hits = [token for token in forbidden if token in helpers + assembly]
    exception_vector_tokens: dict[str, int] = {}
    for token in re.findall(r"\bxmm[0-9]+\b", assembly):
        exception_vector_tokens[token] = exception_vector_tokens.get(token, 0) + 1
    if exception_vector_tokens != {"xmm0": 3, "xmm1": 3}:
        raise QualificationError(
            f"PKXEXC1 source vector scope changed: {exception_vector_tokens}"
        )
    vector_outside_hits = sorted(set(re.findall(r"\bxmm[0-9]+\b", outside)))
    if hits or vector_outside_hits:
        raise QualificationError(
            f"PKXEXC1 source restriction audit failed: {hits + vector_outside_hits}"
        )
    return {
        "scope": "PKXSTATE1 parent plus dedicated PKXEXC1 helpers and assembly",
        "parent_required_instruction_counts": parent_counts,
        "exception_required_instruction_counts": exception_counts,
        "recovery_required_instruction_counts": helper_counts,
        "forbidden_tokens": list(forbidden),
        "forbidden_token_hits": [],
        "vector_occurrences_outside_allowlisted_source_scopes": 0,
        "exception_vector_token_counts": exception_vector_tokens,
        "result": "pass_bounded_source_instruction_audit",
    }


FUNCTION = re.compile(r"^[0-9a-f]+ <(.+)>:$")
INSTRUCTION = re.compile(r"^\s*[0-9a-f]+:\s+\t([a-z0-9.]+)(?:\s+(.*))?$")


def _parse_disassembly(disassembly: str) -> dict[str, list[tuple[str, str]]]:
    functions: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for line in disassembly.splitlines():
        header = FUNCTION.fullmatch(line.strip())
        if header is not None:
            current = header.group(1)
            functions.setdefault(current, [])
            continue
        instruction = INSTRUCTION.fullmatch(line)
        if instruction is not None and current is not None:
            functions[current].append(
                (instruction.group(1), (instruction.group(2) or "").strip())
            )
    if "poole_kernel_entry" not in functions:
        raise QualificationError("PKXEXC1 disassembly has no kernel entry symbol")
    return functions


def _machine_code_audit(disassembly: str) -> dict[str, Any]:
    functions = _parse_disassembly(disassembly)

    def mnemonics(symbol: str) -> list[str]:
        if symbol not in functions:
            raise QualificationError(f"PKXEXC1 disassembly symbol missing: {symbol}")
        return [item[0] for item in functions[symbol]]

    required = {
        "poole_trigger_x87_exception": ["fninit", "fldcw", "fldz", "fldz", "fdivrp"],
        "poole_x87_exception_fault": ["wait"],
        "poole_trigger_simd_exception": ["ldmxcsr", "pxor", "pxor"],
        "poole_simd_exception_fault": ["divss"],
        "poole_trigger_device_not_available_rejection": ["movq", "orq", "movq"],
        "poole_device_not_available_fault": ["fnop", "ud2"],
    }
    observed: dict[str, list[str]] = {}
    for symbol, sequence in required.items():
        values = mnemonics(symbol)
        observed[symbol] = values
        position = 0
        for mnemonic in values:
            if position < len(sequence) and mnemonic == sequence[position]:
                position += 1
        if position != len(sequence):
            raise QualificationError(
                f"PKXEXC1 required machine sequence missing in {symbol}: {values}"
            )

    nm_operands = " ".join(
        operand
        for _, operand in functions["poole_trigger_device_not_available_rejection"]
    ).lower()
    if "%cr0" not in nm_operands or "$0x8" not in nm_operands:
        raise QualificationError("PKXEXC1 machine #NM arm does not set CR0.TS")

    dispatch_symbol = "poole_kernel_trap_dispatch"
    dispatch_mnemonics = mnemonics(dispatch_symbol)
    if dispatch_mnemonics.count("fninit") != 1 or dispatch_mnemonics.count("ldmxcsr") != 1:
        raise QualificationError("PKXEXC1 linked recovery writes changed")

    parent_symbol = "PooleKernelLinked::arch::x86_64::run_xstate_policy"
    allowed_vector_symbols = {parent_symbol, "poole_trigger_simd_exception", "poole_simd_exception_fault"}
    vector_instructions: list[dict[str, str]] = []
    for symbol, instructions in functions.items():
        for mnemonic, operands in instructions:
            lowered = operands.lower()
            if "%ymm" in lowered or "%zmm" in lowered:
                raise QualificationError(
                    f"PKXEXC1 linked extended-vector instruction in {symbol}: {mnemonic} {operands}"
                )
            if "%xmm" in lowered:
                if symbol not in allowed_vector_symbols:
                    raise QualificationError(
                        f"PKXEXC1 linked vector instruction outside allowlist in {symbol}: "
                        f"{mnemonic} {operands}"
                    )
                vector_instructions.append(
                    {"symbol": symbol, "mnemonic": mnemonic, "operands": operands}
                )
    if not any(item["symbol"] == parent_symbol for item in vector_instructions):
        raise QualificationError("PKXEXC1 parent linked XMM proof disappeared")
    if [
        item["mnemonic"]
        for item in vector_instructions
        if item["symbol"] in {"poole_trigger_simd_exception", "poole_simd_exception_fault"}
    ] != ["pxor", "pxor", "divss"]:
        raise QualificationError("PKXEXC1 SIMD injection machine scope changed")
    return {
        "disassembler": xstate_exception.LLVM_OBJDUMP_VERSION,
        "required_symbol_sequences": observed,
        "handler_recovery_instruction_counts": {"fninit": 1, "ldmxcsr": 1},
        "allowlisted_vector_symbols": sorted(allowed_vector_symbols),
        "vector_instruction_count": len(vector_instructions),
        "vector_instructions": vector_instructions,
        "extended_vector_instruction_count": 0,
        "result": "pass_exact_linked_machine_code_scope_audit",
    }


def _llvm_observation(toolchain_root: Path) -> tuple[Path, dict[str, Any]]:
    relative_inside_root = Path(xstate_exception.LLVM_OBJDUMP_RELATIVE).relative_to(
        ".toolchains/rust-1.97.0"
    )
    executable = toolchain_root / relative_inside_root
    if not executable.is_file():
        raise QualificationError("workspace-local llvm-objdump is missing")
    data = executable.read_bytes()
    version_output = _run([str(executable), "--version"], ROOT)
    version_line = next(
        (line.strip() for line in version_output.splitlines() if "LLVM version" in line),
        "",
    )
    observation = {
        "component": "llvm-tools-preview",
        "relative_path": xstate_exception.LLVM_OBJDUMP_RELATIVE,
        "version": version_line,
        "byte_count": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "archive_url": xstate_exception.LLVM_TOOLS_ARCHIVE_URL,
        "archive_sha256": xstate_exception.LLVM_TOOLS_ARCHIVE_SHA256,
        "license": "Apache-2.0 WITH LLVM-exception",
        "installation_scope": "workspace_local_non_administrative_untracked",
        "global_path_modified": False,
        "provenance": "official Rust 1.97.0 distribution component installed by workspace-local rustup",
    }
    _validate_llvm_observation(observation)
    return executable, observation


def _validate_llvm_observation(observation: dict[str, Any]) -> None:
    expected = {
        "component": "llvm-tools-preview",
        "relative_path": xstate_exception.LLVM_OBJDUMP_RELATIVE,
        "version": xstate_exception.LLVM_OBJDUMP_VERSION,
        "byte_count": xstate_exception.LLVM_OBJDUMP_BYTES,
        "sha256": xstate_exception.LLVM_OBJDUMP_SHA256,
        "archive_url": xstate_exception.LLVM_TOOLS_ARCHIVE_URL,
        "archive_sha256": xstate_exception.LLVM_TOOLS_ARCHIVE_SHA256,
        "license": "Apache-2.0 WITH LLVM-exception",
        "installation_scope": "workspace_local_non_administrative_untracked",
        "global_path_modified": False,
        "provenance": "official Rust 1.97.0 distribution component installed by workspace-local rustup",
    }
    if observation != expected:
        raise QualificationError("PKXEXC1 llvm-objdump binding changed")


def _linked_machine_audit(
    toolchain_root: Path,
    temporary_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    executable, tool = _llvm_observation(toolchain_root)
    cargo, _, environment = qualify_native_kernel_entry._toolchain(toolchain_root)
    linked, canonical, plan = qualify_native_kernel_entry._build_product(
        cargo, environment, temporary_root / "linked-machine-audit"
    )
    linked_path = (
        temporary_root
        / "linked-machine-audit"
        / qualify_native_kernel_entry.PRODUCT_TARGET
        / "release"
        / "PooleKernelLinked"
    )
    disassembly = _run(
        [
            str(executable),
            "--disassemble",
            "--demangle",
            "--no-show-raw-insn",
            str(linked_path),
        ],
        ROOT,
    )
    audit = _machine_code_audit(disassembly)
    audit.update(
        {
            "linked_byte_count": len(linked),
            "linked_sha256": xstate_exception.sha256_bytes(linked),
            "canonical_byte_count": len(canonical),
            "canonical_sha256": xstate_exception.sha256_bytes(canonical),
            "relocation_count": plan.relocation_count,
            "disassembly_byte_count": len(disassembly.encode("utf-8")),
            "disassembly_sha256": xstate_exception.sha256_bytes(
                disassembly.encode("utf-8")
            ),
        }
    )
    return audit, tool


def _negative_controls(
    markers: list[str],
    source: str,
    disassembly: str,
    llvm_observation: dict[str, Any],
) -> list[dict[str, str]]:
    candidates: dict[str, list[str]] = {}
    candidates["NEG-N7-PKXEXC-MARKER-OMISSION"] = markers[:-1]
    ordered = markers.copy()
    ordered[31], ordered[34] = ordered[34], ordered[31]
    candidates["NEG-N7-PKXEXC-MARKER-ORDER"] = ordered
    candidates["NEG-N7-PKXEXC-MARKER-DUPLICATE"] = [*markers, markers[-1]]

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    candidates["NEG-N7-PKXEXC-SELECTOR"] = changed(23, "trap_scenario", "5")
    candidates["NEG-N7-PKXEXC-CONTRACT"] = changed(29, "contract", "PKXEXC2")
    candidates["NEG-N7-PKXEXC-PARENT"] = changed(29, "parent", "PKXSTATE2")
    candidates["NEG-N7-PKXEXC-GATES"] = changed(29, "gates", "7")
    candidates["NEG-N7-PKXEXC-VECTORS"] = changed(29, "vectors", "7,16,18")
    candidates["NEG-N7-PKXEXC-IST"] = changed(29, "ist", "2")
    candidates["NEG-N7-PKXEXC-XCR0"] = changed(29, "xcr0", _hex(1))
    candidates["NEG-N7-PKXEXC-CR0"] = changed(29, "cr0", _hex(1 << 3))
    candidates["NEG-N7-PKXEXC-CR4"] = changed(29, "cr4", _hex(1 << 9))
    candidates["NEG-N7-PKXEXC-PARENT-WRITES"] = changed(
        29, "parent_control_writes", "4"
    )
    candidates["NEG-N7-PKXEXC-DEFAULT-MASKS"] = changed(
        29, "exceptions_masked_default", "0"
    )
    candidates["NEG-N7-PKXEXC-SEQUENCE"] = changed(30, "sequence", "19,16,7")
    candidates["NEG-N7-PKXEXC-X87-FCW-ARM"] = changed(30, "fcw", _hex(0x037F))
    candidates["NEG-N7-PKXEXC-SIMD-MXCSR-ARM"] = changed(
        30, "mxcsr", _hex(0x1F80)
    )
    candidates["NEG-N7-PKXEXC-NM-STRATEGY"] = changed(
        30, "nm_strategy", "lazy_restore"
    )
    candidates["NEG-N7-PKXEXC-X87-VECTOR"] = changed(31, "vector", "19")
    candidates["NEG-N7-PKXEXC-X87-ERROR"] = changed(31, "error", _hex(1))
    candidates["NEG-N7-PKXEXC-X87-STATUS"] = changed(32, "fsw_before", _hex(0))
    candidates["NEG-N7-PKXEXC-X87-RECOVERY"] = changed(
        32, "fcw_after", _hex(0x037E)
    )
    candidates["NEG-N7-PKXEXC-X87-RETURN"] = changed(33, "returned", "0")
    candidates["NEG-N7-PKXEXC-SIMD-VECTOR"] = changed(34, "vector", "16")
    candidates["NEG-N7-PKXEXC-SIMD-STATUS"] = changed(
        35, "mxcsr_before", _hex(0x1F81)
    )
    candidates["NEG-N7-PKXEXC-SIMD-RECOVERY"] = changed(
        35, "mxcsr_after", _hex(0x1F81)
    )
    candidates["NEG-N7-PKXEXC-SIMD-RETURN"] = changed(36, "returned", "1")
    candidates["NEG-N7-PKXEXC-NM-ARM"] = changed(37, "cr0_ts", "0")
    candidates["NEG-N7-PKXEXC-NM-VECTOR"] = changed(38, "vector", "6")
    candidates["NEG-N7-PKXEXC-NM-INJECTION"] = changed(
        39, "injection", "production"
    )
    candidates["NEG-N7-PKXEXC-NM-SAMPLING"] = changed(
        39, "state_sampled", "1"
    )
    candidates["NEG-N7-PKXEXC-NM-RECOVERY"] = changed(
        39, "recovery", "allowed"
    )
    candidates["NEG-N7-PKXEXC-DELIVERY-COUNT"] = changed(40, "deliveries", "2")
    candidates["NEG-N7-PKXEXC-RECOVERY-COUNT"] = changed(40, "recovered", "1")
    candidates["NEG-N7-PKXEXC-WRITE-COUNT"] = changed(
        40, "privileged_writes", "3"
    )
    candidates["NEG-N7-PKXEXC-UNEXPECTED"] = changed(40, "unexpected", "1")
    candidates["NEG-N7-PKXEXC-AUTHORITY"] = changed(40, "authority", "1")
    candidates["NEG-N7-PKXEXC-SCHEDULER-CLAIM"] = changed(40, "scheduler", "1")
    candidates["NEG-N7-PKXEXC-SMP-CLAIM"] = changed(40, "smp", "1")
    candidates["NEG-N7-PKXEXC-TARGET-CLAIM"] = changed(40, "target", "1")

    marker_ids = xstate_exception.NEGATIVE_CONTROL_IDS[:-3]
    if set(candidates) != set(marker_ids):
        raise QualificationError("PKXEXC1 marker hostile-control implementation is incomplete")
    controls = [
        _require_rejection(control_id, candidates[control_id])
        for control_id in marker_ids
    ]
    try:
        _source_audit(source + '\nasm!("movaps xmm2, xmm3");\n')
    except QualificationError:
        controls.append(
            {
                "id": "NEG-N7-PKXEXC-SOURCE-AUDIT",
                "status": "pass",
                "expected": "rejected",
            }
        )
    else:
        raise QualificationError("PKXEXC1 source-audit mutation was accepted")
    synthetic = (
        disassembly
        + "\n0000000000027000 <synthetic_outside_allowlist>:\n"
        + "   27000:      \tpxor\t%xmm2, %xmm2\n"
    )
    try:
        _machine_code_audit(synthetic)
    except QualificationError:
        controls.append(
            {
                "id": "NEG-N7-PKXEXC-MACHINE-CODE-AUDIT",
                "status": "pass",
                "expected": "rejected",
            }
        )
    else:
        raise QualificationError("PKXEXC1 machine-code mutation was accepted")
    changed_tool = dict(llvm_observation)
    changed_tool["sha256"] = "0" * 64
    try:
        _validate_llvm_observation(changed_tool)
    except QualificationError:
        controls.append(
            {
                "id": "NEG-N7-PKXEXC-LLVM-BINDING",
                "status": "pass",
                "expected": "rejected",
            }
        )
    else:
        raise QualificationError("PKXEXC1 LLVM mutation was accepted")
    if [item["id"] for item in controls] != list(xstate_exception.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKXEXC1 hostile-control order changed")
    return controls


def _profile_overlay(profile: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(profile)
    arguments = value["base_argument_template"]
    acceleration_index = arguments.index("-accel")
    if arguments[acceleration_index + 1] != "tcg,thread=single":
        raise QualificationError("Tier 0 accelerator changed before PKXEXC1 overlay")
    arguments[acceleration_index + 1] = "whpx"
    icount_index = arguments.index("-icount")
    del arguments[icount_index : icount_index + 2]
    index = arguments.index("-cpu")
    if arguments[index + 1] != "qemu64":
        raise QualificationError("Tier 0 CPU argument changed before PKXEXC1 overlay")
    arguments[index + 1] = xstate_exception.CPU_MODEL
    value["machine"]["accelerator"] = "whpx"
    value["machine"]["tcg_thread_mode"] = "not_applicable"
    value["machine"]["host_acceleration_enabled"] = True
    value["machine"]["cpu_model"] = xstate_exception.CPU_MODEL
    value["profile_set_id"] = "POOLEOS-PKXEXC1-Q35-1"
    return value


def _tcg_limitation_profile(profile: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(profile)
    arguments = value["base_argument_template"]
    index = arguments.index("-cpu")
    if arguments[index + 1] != "qemu64":
        raise QualificationError("Tier 0 CPU argument changed before PKXEXC1 TCG probe")
    arguments[index + 1] = xstate_exception.CPU_MODEL
    value["machine"]["cpu_model"] = xstate_exception.CPU_MODEL
    value["profile_set_id"] = "POOLEOS-PKXEXC1-TCG-LIMITATION-1"
    return value


TCG_DIAGNOSTIC = re.compile(
    r"^POOLEOS:KERNEL:XSTATE-EXCEPTION-SIMD-DELIVERY-ERROR returned=([0-9]+) "
    r"mxcsr=(0x[0-9A-F]{16}) cr4=(0x[0-9A-F]{16})$"
)


def _tcg_limitation_probe(
    lock: dict[str, Any],
    profile: dict[str, Any],
    qemu_root: Path,
    media_path: Path,
    run_directory: Path,
    timeout: int,
) -> dict[str, Any]:
    try:
        qualify_native_pooleboot._execute_once(
            "xstate-exception-tcg-limitation",
            lock,
            profile,
            qemu_root,
            media_path,
            run_directory,
            timeout,
            marker_validator=xstate_exception.validate_markers,
            marker_extractor=xstate_exception.extract_markers,
            completion_marker=xstate_exception.COMPLETION_MARKER,
        )
    except qualify_native_pooleboot.QualificationError:
        pass
    else:
        raise QualificationError("PKXEXC1 TCG unexpectedly delivered the complete exception matrix")
    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
    if not debug_path.is_file():
        raise QualificationError("PKXEXC1 TCG limitation debug log is missing")
    raw = debug_path.read_bytes()
    lines = [line.strip() for line in raw.decode("ascii", errors="ignore").splitlines()]
    diagnostics = [line for line in lines if TCG_DIAGNOSTIC.fullmatch(line)]
    panic = "POOLEOS:PANIC:0x000000000000100E"
    if len(diagnostics) != 1 or lines.count(panic) != 1:
        raise QualificationError("PKXEXC1 TCG limitation signature changed")
    match = TCG_DIAGNOSTIC.fullmatch(diagnostics[0])
    if match is None:
        raise QualificationError("PKXEXC1 TCG limitation diagnostic is malformed")
    returned = int(match.group(1))
    mxcsr = int(match.group(2), 16)
    cr4 = int(match.group(3), 16)
    if (
        returned != 1
        or mxcsr != 0x1F01
        or mxcsr & (1 << 7)
        or cr4 & (1 << 10) == 0
    ):
        raise QualificationError("PKXEXC1 TCG limitation state changed")
    return {
        "status": "pass_expected_tcg_non_delivery_fail_closed",
        "run_count": 1,
        "acceleration": "tcg_single_thread",
        "cpu_model": xstate_exception.CPU_MODEL,
        "returned_recovery_count": returned,
        "mxcsr_after_undelivered_divss": mxcsr,
        "mxcsr_invalid_status_set": True,
        "mxcsr_invalid_mask_clear": True,
        "cr4_osxmmexcpt_set": True,
        "vector_19_delivered": False,
        "panic_code": "0x100E",
        "debugcon_byte_count": len(raw),
        "debugcon_sha256": xstate_exception.sha256_bytes(raw),
        "source": "https://gitlab.com/qemu-project/qemu/-/issues/215",
        "production_promotion_allowed": False,
    }


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> dict[str, Any]:
    contract = xstate_exception.read_json(ROOT / xstate_exception.CONTRACT_RELATIVE)
    contract_schema = xstate_exception.read_json(
        ROOT / xstate_exception.CONTRACT_SCHEMA_RELATIVE
    )
    schema_errors = [
        f"contract schema {item.path}: {item.message}"
        for item in xstate_exception.validate_json(contract, contract_schema)
    ]
    errors = [*schema_errors, *xstate_exception.contract_errors(contract)]
    if errors:
        raise QualificationError("; ".join(errors))
    lock, base_profile = native_tier0.validate_contracts(ROOT)
    profile = _profile_overlay(base_profile)
    tcg_profile = _tcg_limitation_profile(base_profile)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)

    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(
        manifest, kernel, artifact_files
    )

    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs/native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pkxexc1-qualification-", dir=temporary_parent
    ) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        exception_boot, exception_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "exception-boot",
            development_feature=xstate_exception.FEATURE,
        )
        if (
            b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot
            or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot
        ):
            raise QualificationError("default PooleBoot transfer isolation failed")
        if xstate_exception.sha256_bytes(default_boot) == xstate_exception.sha256_bytes(
            exception_boot
        ):
            raise QualificationError("default and PKXEXC1 PooleBoot profiles are not distinct")

        machine_audit, llvm_observation = _linked_machine_audit(
            toolchain_root, temporary_root
        )
        linked_path = (
            temporary_root
            / "linked-machine-audit"
            / qualify_native_kernel_entry.PRODUCT_TARGET
            / "release"
            / "PooleKernelLinked"
        )
        llvm_path, _ = _llvm_observation(toolchain_root)
        disassembly = _run(
            [
                str(llvm_path),
                "--disassemble",
                "--demangle",
                "--no-show-raw-insn",
                str(linked_path),
            ],
            ROOT,
        )
        source = (ROOT / "native/kernel/src/arch/x86_64.rs").read_text(
            encoding="utf-8"
        )
        source_audit = _source_audit(source)

        media_one = native_kernel_load.build_media_bytes(
            exception_boot, config, manifest, kernel, artifact_files
        )
        media_two = native_kernel_load.build_media_bytes(
            exception_boot, config, manifest, kernel, artifact_files
        )
        if media_one != media_two:
            raise QualificationError("two PKXEXC1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pkxexc1.img"
        media_path.write_bytes(media_one)

        with tempfile.TemporaryDirectory(
            prefix="pkxexc1-tcg-limitation-", dir=run_parent
        ) as tcg_temporary:
            tcg_limitation = _tcg_limitation_probe(
                lock,
                tcg_profile,
                qemu_root,
                media_path,
                Path(tcg_temporary),
                timeout,
            )
        tcg_limitation["normalized_command"] = (
            qualify_native_pooleboot._normalized_command(tcg_profile)
        )
        tcg_limitation["normalized_command_sha256"] = (
            xstate_exception.sha256_bytes(
                native_pooleboot.canonical_json_bytes(
                    tcg_limitation["normalized_command"]
                )
            )
        )

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkxexc1-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"xstate-exception-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=xstate_exception.validate_markers,
                        marker_extractor=xstate_exception.extract_markers,
                        completion_marker=xstate_exception.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"][
                        "debugcon_log"
                    ]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(
                                encoding="ascii", errors="ignore"
                            ).splitlines()
                            if line.strip().startswith("POOLE")
                        ][-12:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                try:
                    native_kernel_load.validate_oracle_binding(
                        prefix["boot_prefix"],
                        media_inspection,
                        run["pbp1_transcript"],
                    )
                    run["transcript_binding"] = (
                        native_kernel_transfer.validate_transcript_binding(
                            prefix, run["pbp1_transcript"]
                        )
                    )
                    run["independent_kernel_revalidation"] = (
                        native_kernel_transfer.validate_revalidation_binding(
                            prefix, handoff, retained_files
                        )
                    )
                except (
                    native_kernel_load.KernelLoadError,
                    native_kernel_transfer.KernelTransferError,
                ) as error:
                    raise QualificationError(str(error)) from error
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKXEXC1 runs emitted different markers")
        if screenshots[0] != screenshots[1] or handoffs[0] != handoffs[1]:
            raise QualificationError("two PKXEXC1 visual or handoff receipts differ")

    controls = _negative_controls(
        runs[0]["markers"], source, disassembly, llvm_observation
    )
    observation = xstate_exception.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_xstate_exception_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_bsp_x87_simd_exception_non_promoting",
        "contract_id": xstate_exception.CONTRACT_ID,
        "selected_move_id": xstate_exception.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n7_exit_gate_satisfied": False,
        "phase_status": {
            "N7": "partial",
            "N7.4": "partial",
            "ADD-N7-XSTATE-001": "partial",
        },
        "inputs": xstate_exception.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "exception_pooleboot": exception_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "source_audit": source_audit,
            "machine_code_audit_tool": llvm_observation,
            "linked_machine_code_audit": machine_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": xstate_exception.sha256_bytes(media_one),
            "byte_count": len(media_one),
            "inspection": media_inspection,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "bootstrap-debug",
            "machine": "pc-q35-11.0",
            "cpu_model": xstate_exception.CPU_MODEL,
            "base_tier0_cpu_model": "qemu64",
            "base_tier0_profile_modified": False,
            "acceleration": "whpx_hardware_accelerated",
            "host_cpu": "AMD Ryzen 7 9800X3D 8-Core Processor",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": xstate_exception.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "tcg_limitation_probe": tcg_limitation,
            "runs": runs,
            "observation": {
                key: observation[key]
                for key in ("setup", "arm", "x87", "simd", "nm_arm", "nm", "result")
            },
        },
        "negative_controls": controls,
        "claims": xstate_exception.expected_claims(),
        "non_claims": contract["non_claims"],
        "summary": {
            "qemu_run_count": 2,
            "tcg_limitation_probe_count": 1,
            "marker_count": xstate_exception.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "exception_deliveries": observation["result"]["deliveries"],
            "recovered_returns": observation["result"]["recovered"],
            "nm_rejections": observation["result"]["nm_rejected"],
            "privileged_configuration_writes": observation["result"][
                "privileged_writes"
            ],
            "recovery_state_writes": observation["result"]["recovery_writes"],
            "machine_code_audit_passed": True,
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "firmware_calls_after_exit": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Define and qualify user-task floating-point exception delivery semantics.",
            "Integrate bounded xstate image ownership with real thread lifecycle and scheduling.",
            "Qualify AP initialization, SMP homogeneity, and CPU migration behavior.",
            "Qualify AVX and every subsequently selected extended component.",
            "Qualify the exact Ryzen 7 9800X3D target and complete the remaining N7 exit gate.",
        ],
    }
    errors = xstate_exception.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-21")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
    ) as error:
        print(f"PKXEXC1 qualification failed: {error}", file=sys.stderr)
        return 1
    print(
        "PKXEXC1 qualification passed: "
        f"runs={report['summary']['qemu_run_count']} "
        f"controls={report['summary']['negative_controls_passed']} "
        f"deliveries={report['summary']['exception_deliveries']} "
        f"recoveries={report['summary']['recovered_returns']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
