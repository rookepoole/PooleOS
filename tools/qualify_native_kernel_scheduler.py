#!/usr/bin/env python3
"""Build and qualify the bounded PKSCHED1 scheduler foundation."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (  # noqa: E402
    native_kernel_load,
    native_kernel_scheduler as scheduler,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / scheduler.READINESS_RELATIVE
HOSTILE_CASE_COUNT = 115


class QualificationError(RuntimeError):
    """Raised when PKSCHED1 qualification fails closed."""


def _write_readiness(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKSCHED1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKSCHED1 mutation field is missing: {field}")
    value = match.group(1)
    if value.startswith("0x"):
        return "0x0000000000000001" if int(value, 16) == 0 else "0x0000000000000000"
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    return "invalid"


def _require_rejections(
    control_id: str, operations: list[Callable[[], Any]]
) -> dict[str, Any]:
    for operation in operations:
        try:
            operation()
        except scheduler.KernelSchedulerError:
            continue
        raise QualificationError(f"PKSCHED1 hostile control did not reject: {control_id}")
    return {
        "id": control_id,
        "status": "pass",
        "expected": "rejected",
        "case_count": len(operations),
    }


def _marker_operation(candidate: list[str]) -> Callable[[], Any]:
    return lambda: scheduler.validate_markers(candidate)


def _probe_operation(candidate: str) -> Callable[[], Any]:
    return lambda: scheduler.parse_probe_output(candidate)


def _field_matrix(
    control_id: str,
    values: list[str],
    value_index: int,
    fields: tuple[str, ...],
    validator: Callable[[list[str]], Any] = scheduler.validate_markers,
) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        candidate = values.copy()
        candidate[value_index] = _set_field(
            candidate[value_index], field, _invalid_value(candidate[value_index], field)
        )
        operations.append(lambda candidate=candidate: validator(candidate))
    return _require_rejections(control_id, operations)


def _audit_source_text(
    scheduler_text: str,
    arch_text: str,
    main_text: str,
    boot_exit_text: str,
    boot_manifest_text: str,
) -> dict[str, Any]:
    required_scheduler = (
        "pub const MAX_CPUS: usize = 4",
        "pub const MAX_TASKS: usize = 8",
        "pub const MAX_BYPASS: u8 = (MAX_TASKS - 1) as u8",
        "pub struct Scheduler {",
        "pub fn create_task(",
        "pub fn dispatch(&mut self",
        "pub fn cancel_wait(&mut self",
        "pub fn timeout_wait(&mut self",
        "pub fn migrate(&mut self",
        "pub fn lock_mutex(&mut self",
        "pub fn teardown(&mut self",
        "pub struct RefCount",
        ".fetch_update(Ordering::AcqRel, Ordering::Acquire",
        "value.checked_add(1)",
        "value.checked_sub(1)",
        "pub struct RawSpinLock",
        ".compare_exchange(0, owner, Ordering::Acquire, Ordering::Relaxed)",
        ".compare_exchange(owner, 0, Ordering::Release, Ordering::Relaxed)",
        "pub fn validate_context_switch_contract",
    )
    required_arch = (
        "poole_scheduler_context_switch:\n    pushfq",
        "poole_scheduler_context_switch_end:",
        "pushfq",
        "push rbp",
        "push r15",
        "mov qword ptr [rdi], rsp",
        "mov rsp, qword ptr [rsi]",
        "pop r15",
        "pop rbp",
        "popfq",
        "poole_scheduler_task_a_entry:",
        "poole_scheduler_task_b_entry:",
        "read_msr(IA32_FS_BASE)",
        "read_msr(IA32_KERNEL_GS_BASE)",
        "write_bytes(base, 0, SCHEDULER_STACK_BYTES)",
        "run_scheduler_context_switch_probe",
    )
    required_main = (
        "PKSCHED1_EARLY",
        "PKSCHED1_CORE",
        "PKSCHED1_SWITCH",
        "PKSCHED1_CLEANUP",
        "pksched1_fragment!(PKSCHED1_RESULT",
        "DevelopmentTrapScenario::Scheduler",
        ".lock_bounded(1, 1)",
        "scheduler_lock_held: SCHEDULER_SWITCH_LOCK.owner() == 1",
        "run_scheduler_context_switch_probe(&trace)",
        ".unlock(1)",
    )
    scheduler._require(
        all(token in scheduler_text for token in required_scheduler),
        "PKSCHED1 scheduler source audit failed",
    )
    scheduler._require(
        all(token in arch_text for token in required_arch),
        "PKSCHED1 context-switch source audit failed",
    )
    scheduler._require(
        all(token in main_text for token in required_main),
        "PKSCHED1 live lifecycle source audit failed",
    )
    scheduler._require(
        "development-scheduler = [\"development-transfer\"]" in boot_manifest_text
        and "feature = \"development-scheduler\"" in boot_exit_text
        and "15" in boot_exit_text,
        "PKSCHED1 boot selector source audit failed",
    )
    scheduler._require(
        scheduler_text.count("#[test]") == 14,
        "PKSCHED1 scheduler test count changed",
    )
    scheduler._require(
        not re.search(r"\b(?:Vec|Box|String|HashMap)\b", scheduler_text),
        "PKSCHED1 scheduler core gained heap-backed storage",
    )
    diagnostics = ("PKSCHED1DBG", "SCHEDULER_FORCE_PASS", "SCHEDULER_DEBUG")
    scheduler._require(
        not any(token in scheduler_text + arch_text + main_text for token in diagnostics),
        "PKSCHED1 transient diagnostics remain",
    )
    return {
        "scheduler_test_count": 14,
        "fixed_cpu_capacity": 4,
        "fixed_task_capacity": 8,
        "allocation_free_core": True,
        "context_switch_source_scope_count": arch_text.count(
            "poole_scheduler_context_switch:"
        ),
        "live_marker_count": 5,
        "transient_diagnostic_token_count": 0,
    }


def _source_audit() -> dict[str, Any]:
    paths = {
        "scheduler": ROOT / "native/kernel/src/scheduler.rs",
        "arch": ROOT / "native/kernel/src/arch/x86_64.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "boot_exit": ROOT / "native/boot/src/exit.rs",
        "boot_manifest": ROOT / "native/boot/Cargo.toml",
        "bootexit": ROOT / "native/bootexit/src/lib.rs",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    result = _audit_source_text(
        texts["scheduler"],
        texts["arch"],
        texts["main"],
        texts["boot_exit"],
        texts["boot_manifest"],
    )
    scheduler._require(
        "pub const MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = 21;" in texts["bootexit"],
        "PKSCHED1 transfer-state selector ceiling changed",
    )
    result["files"] = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": scheduler.sha256_bytes(path.read_bytes()),
        }
        for name, path in paths.items()
    }
    return result


def _linked_switch_scope(
    disassembly: str, symbol_table: str | None = None
) -> dict[str, Any]:
    matches = re.findall(
        r"(?ms)^[0-9a-f]+ <poole_scheduler_context_switch>:\n"
        r"(?P<body>.*?)^[0-9a-f]+ <(?:poole_scheduler_context_switch_end|"
        r"poole_scheduler_task_a_entry)>:",
        disassembly,
    )
    scheduler._require(len(matches) == 1, "PKSCHED1 linked switch scope changed")
    body = matches[0]
    instructions = re.findall(
        r"(?m)^[ \t]*[0-9a-f]+:[ \t]+(?:[0-9a-f]{2}[ \t]+)+"
        r"(?P<mnemonic>[a-z0-9]+)(?:[ \t]+(?P<operands>[^\r\n]+))?$",
        body,
    )
    scheduler._require(len(instructions) == 18, "PKSCHED1 linked instruction count changed")
    mnemonics = [item[0] for item in instructions]
    normalized = []
    for value in mnemonics:
        if value == "pushfq":
            normalized.append("pushf")
        elif value == "popfq":
            normalized.append("popf")
        else:
            normalized.append(value[:-1] if value.endswith("q") else value)
    scheduler._require(
        normalized
        == [
            "pushf",
            "push",
            "push",
            "push",
            "push",
            "push",
            "push",
            "mov",
            "inc",
            "mov",
            "pop",
            "pop",
            "pop",
            "pop",
            "pop",
            "pop",
            "popf",
            "ret",
        ],
        "PKSCHED1 linked instruction sequence changed",
    )
    lowered = body.lower()
    forbidden_patterns = (
        r"\b(?:xsave|xrstor|fxsave|fxrstor|wrmsr|rdmsr|sti|syscall|sysret|iret|in|out)\b",
        r"%(?:xmm|ymm|zmm|mm|st|cr|dr)[0-9]*",
        r"\b(?:call|jmp)[a-z]*\s+\*",
    )
    forbidden = sum(len(re.findall(pattern, lowered)) for pattern in forbidden_patterns)
    scheduler._require(forbidden == 0, "PKSCHED1 linked switch contains forbidden state")
    result = {
        "scope": "poole_scheduler_context_switch..poole_scheduler_context_switch_end",
        "instruction_count": len(instructions),
        "forbidden_instruction_count": forbidden,
        "mnemonics": mnemonics,
        "status": "pass",
    }
    if symbol_table is not None:
        symbols: dict[str, tuple[int, int]] = {}
        for name in (
            "poole_scheduler_context_switch",
            "poole_scheduler_context_switch_end",
            "poole_scheduler_task_a_entry",
        ):
            lines = [line for line in symbol_table.splitlines() if line.rstrip().endswith(name)]
            scheduler._require(len(lines) == 1, f"PKSCHED1 linked symbol changed: {name}")
            fields = lines[0].split()
            scheduler._require(len(fields) >= 5, f"PKSCHED1 linked symbol malformed: {name}")
            symbols[name] = (int(fields[0], 16), int(fields[-2], 16))
        start, size = symbols["poole_scheduler_context_switch"]
        end, end_size = symbols["poole_scheduler_context_switch_end"]
        task_a, _ = symbols["poole_scheduler_task_a_entry"]
        scheduler._require(
            size == 0x24 and end_size == 0 and end == start + size and task_a == end,
            "PKSCHED1 linked symbol boundary changed",
        )
        result.update(
            {
                "start_address": f"0x{start:016X}",
                "end_address": f"0x{end:016X}",
                "scope_byte_count": size,
                "end_symbol_verified": True,
            }
        )
    return result


def _linked_switch_audit(
    toolchain_root: Path, expected_kernel: bytes, target_dir: Path
) -> dict[str, Any]:
    cargo, _, env = qualify_native_kernel_entry._toolchain(toolchain_root)
    linked, canonical, plan = qualify_native_kernel_entry._build_product(
        cargo, env, target_dir
    )
    if canonical != expected_kernel:
        raise QualificationError("PKSCHED1 linked-audit build diverged from qualified kernel")
    installed = cargo.parent.parent
    candidates = sorted((installed / "lib" / "rustlib").glob("*/bin/llvm-objdump.exe"))
    if len(candidates) != 1:
        raise QualificationError("PKSCHED1 workspace-local llvm-objdump is missing or ambiguous")
    artifact = (
        target_dir
        / qualify_native_kernel_entry.PRODUCT_TARGET
        / "release"
        / "PooleKernelLinked"
    )
    completed = subprocess.run(
        [str(candidates[0]), "-d", str(artifact)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise QualificationError("PKSCHED1 linked disassembly failed")
    symbols = subprocess.run(
        [str(candidates[0]), "-t", str(artifact)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if symbols.returncode != 0:
        raise QualificationError("PKSCHED1 linked symbol-table audit failed")
    result = _linked_switch_scope(
        completed.stdout.decode("ascii", errors="replace").replace("\r\n", "\n"),
        symbols.stdout.decode("ascii", errors="replace").replace("\r\n", "\n"),
    )
    llvm_objdump = candidates[0]
    try:
        llvm_objdump_path = llvm_objdump.relative_to(ROOT)
    except ValueError:
        logical_toolchain_root = ROOT / ".toolchains"
        try:
            tool_relative = llvm_objdump.resolve(strict=True).relative_to(
                logical_toolchain_root.resolve(strict=True)
            )
        except ValueError as error:
            raise QualificationError(
                "PKSCHED1 llvm-objdump escaped the workspace-local toolchain"
            ) from error
        llvm_objdump_path = logical_toolchain_root.relative_to(ROOT) / tool_relative
    result.update(
        {
            "linked_sha256": scheduler.sha256_bytes(linked),
            "linked_byte_count": len(linked),
            "canonical_sha256": scheduler.sha256_bytes(canonical),
            "canonical_byte_count": len(canonical),
            "relocation_count": plan.relocation_count,
            "llvm_objdump_path": llvm_objdump_path.as_posix(),
            "llvm_objdump_sha256": scheduler.sha256_bytes(llvm_objdump.read_bytes()),
        }
    )
    return result


def _run_host_probe(toolchain_root: Path, target_dir: Path) -> dict[str, Any]:
    cargo, _, env = qualify_native_kernel_entry._toolchain(toolchain_root)
    completed = subprocess.run(
        [
            str(cargo),
            "run",
            "--locked",
            "--offline",
            "--quiet",
            "--manifest-path",
            str(ROOT / "native/kernel/Cargo.toml"),
            "--features",
            "host-probe",
            "--bin",
            "pksched1-probe",
            "--target-dir",
            str(target_dir),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(f"PKSCHED1 host probe failed: {output[-2000:]}")
    result = scheduler.parse_probe_output(output)
    result["output_sha256"] = scheduler.sha256_bytes(output.encode("utf-8"))
    result["receipt_count"] = 4
    result["rust_python_exact_agreement"] = True
    return result


def _negative_controls(markers: list[str], probe_lines: list[str]) -> list[dict[str, Any]]:
    scheduler.validate_markers(markers)
    probe_output = "\n".join(probe_lines) + "\n"
    scheduler.parse_probe_output(probe_output)
    ids = scheduler.NEGATIVE_CONTROL_IDS
    controls = [_require_rejections(ids[0], [_marker_operation(markers[:-1])])]

    reordered = markers.copy()
    reordered[31], reordered[32] = reordered[32], reordered[31]
    controls.append(_require_rejections(ids[1], [_marker_operation(reordered)]))
    controls.append(
        _require_rejections(ids[2], [_marker_operation([*markers, markers[-1]])])
    )
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "14")
    prefix = markers.copy()
    prefix[0] += " invalid"
    controls.append(
        _require_rejections(ids[3], [_marker_operation(selector), _marker_operation(prefix)])
    )
    controls.append(
        _field_matrix(
            ids[4],
            markers,
            30,
            (
                "contract",
                "cpu_capacity",
                "task_capacity",
                "active_tasks",
                "queue_count",
                "policy",
                "priorities",
                "dispatches",
                "migrations",
                "wakes",
                "teardowns",
                "max_bypass",
                "trace",
            ),
        )
    )
    controls.append(
        _field_matrix(
            ids[5],
            markers,
            31,
            (
                "contract",
                "tasks",
                "dispatches",
                "transitions",
                "task0_runs",
                "task1_runs",
                "callee_saved",
                "rflags",
                "same_cr3",
                "fs_gs_unchanged",
                "xstate_unused",
                "debug_unused",
                "pmu_unused",
                "stacks_distinct",
                "stack_bytes",
                "alignment",
                "errors",
            ),
        )
    )
    controls.append(
        _field_matrix(
            ids[6],
            markers,
            32,
            (
                "contract",
                "scheduler_lock_released",
                "stack_bytes_cleared",
                "task_contexts_retired",
                "queue_entries",
                "running",
                "blocked",
                "dead",
            ),
        )
    )
    controls.append(
        _field_matrix(
            ids[7],
            markers,
            33,
            (
                "contract",
                "profile",
                "core",
                "hardware_switch",
                "bsp",
                "smp_dispatch",
                "preemption",
                "ring3",
                "address_spaces",
                "xstate_switch",
                "target",
                "signatures",
                "authority",
                "actions",
                "production",
                "terminal",
            ),
        )
    )

    source_paths = (
        ROOT / "native/kernel/src/scheduler.rs",
        ROOT / "native/kernel/src/arch/x86_64.rs",
        ROOT / "native/kernel/src/main.rs",
        ROOT / "native/boot/src/exit.rs",
        ROOT / "native/boot/Cargo.toml",
    )
    sources = [path.read_text(encoding="utf-8") for path in source_paths]
    controls.append(
        _require_rejections(
            ids[8],
            [
                lambda: _audit_source_text(
                    sources[0].replace("pub struct Scheduler {", "struct Scheduler {", 1),
                    sources[1], sources[2], sources[3], sources[4]
                ),
                lambda: _audit_source_text(
                    sources[0],
                    sources[1].replace(
                        "poole_scheduler_context_switch:\n    pushfq",
                        "poole_scheduler_context_switch:\n    nop",
                        1,
                    ),
                    sources[2], sources[3], sources[4]
                ),
                lambda: _audit_source_text(
                    sources[0], sources[1],
                    sources[2].replace(
                        "pksched1_fragment!(PKSCHED1_RESULT",
                        "pksched1_fragment!(PKSCHED1_REMOVED",
                        1,
                    ),
                    sources[3], sources[4]
                ),
            ],
        )
    )
    linked_fixture = (
        "0000000000001000 <poole_scheduler_context_switch>:\n"
        "    1000: 9c pushfq\n"
        "    1001: 55 pushq %rbp\n"
        "    1002: 53 pushq %rbx\n"
        "    1003: 41 54 pushq %r12\n"
        "    1005: 41 55 pushq %r13\n"
        "    1007: 41 56 pushq %r14\n"
        "    1009: 41 57 pushq %r15\n"
        "    100b: 48 89 27 movq %rsp, (%rdi)\n"
        "    100e: 48 ff 05 00 00 00 00 incq 0x0(%rip)\n"
        "    1015: 48 8b 26 movq (%rsi), %rsp\n"
        "    1018: 41 5f popq %r15\n"
        "    101a: 41 5e popq %r14\n"
        "    101c: 41 5d popq %r13\n"
        "    101e: 41 5c popq %r12\n"
        "    1020: 5b popq %rbx\n"
        "    1021: 5d popq %rbp\n"
        "    1022: 9d popfq\n"
        "    1023: c3 retq\n"
        "0000000000001024 <poole_scheduler_context_switch_end>:\n"
    )
    controls.append(
        _require_rejections(
            ids[9],
            [
                lambda: _linked_switch_scope(linked_fixture.replace(" retq", " sti", 1)),
                lambda: _linked_switch_scope(linked_fixture.replace("\n0000000000001024", "\n    1024: 90 nop\n0000000000001025", 1)),
                lambda: _linked_switch_scope(linked_fixture.replace("poole_scheduler_context_switch_end", "removed", 1)),
            ],
        )
    )
    controls.append(
        _require_rejections(ids[10], [_probe_operation("\n".join(probe_lines[:-1]))])
    )
    probe_reordered = probe_lines.copy()
    probe_reordered[1], probe_reordered[2] = probe_reordered[2], probe_reordered[1]
    controls.append(
        _require_rejections(ids[11], [_probe_operation("\n".join(probe_reordered))])
    )

    def probe_mutations(index: int, fields: tuple[str, ...]) -> list[Callable[[], Any]]:
        operations: list[Callable[[], Any]] = []
        for field in fields:
            candidate = probe_lines.copy()
            candidate[index] = _set_field(
                candidate[index], field, _invalid_value(candidate[index], field)
            )
            operations.append(_probe_operation("\n".join(candidate)))
        return operations

    controls.append(
        _require_rejections(
            ids[12], probe_mutations(0, ("checksum", "dispatches", "task_dispatches"))
        )
    )
    controls.append(
        _require_rejections(
            ids[13],
            probe_mutations(
                1, ("wakes", "cancel_reason", "timeout_reason", "duplicate_rejected")
            ),
        )
    )
    controls.append(
        _require_rejections(
            ids[14],
            probe_mutations(
                2,
                (
                    "owner_slot",
                    "inherited",
                    "restored",
                    "granted_slot",
                    "inheritance_events",
                ),
            ),
        )
    )
    controls.append(
        _require_rejections(
            ids[15],
            probe_mutations(3, ("valid", "hostile_rejected", "alignment", "callee_saved")),
        )
    )

    def duplicate_generation() -> None:
        model = scheduler.NeutralSchedulerOracle()
        model.create(0, 10)
        model.create(0, 10)

    controls.append(
        _require_rejections(
            ids[16],
            [duplicate_generation, lambda: scheduler.NeutralSchedulerOracle()._task(0)],
        )
    )
    controls.append(
        _require_rejections(
            ids[17],
            [
                lambda: scheduler.NeutralSchedulerOracle().create(0, 0),
                lambda: scheduler.NeutralSchedulerOracle().create(0, 32),
            ],
        )
    )

    def invalid_affinity(cpu: int) -> None:
        model = scheduler.NeutralSchedulerOracle()
        model.create(0, 10)
        model._task(0).affinity = 0
        model.activate(0, cpu)

    controls.append(
        _require_rejections(ids[18], [lambda: invalid_affinity(0), lambda: invalid_affinity(3)])
    )

    def duplicate_runnable() -> None:
        model = scheduler.NeutralSchedulerOracle()
        model.create(0, 10)
        model.activate(0, 0)
        model.queues[0].append(0)
        model.validate()

    controls.append(_require_rejections(ids[19], [duplicate_runnable]))

    def invalid_migration(target: int) -> None:
        model = scheduler.NeutralSchedulerOracle()
        model.create(0, 10)
        model.activate(0, 0)
        model._task(0).queued = None
        model.migrate(0, target)

    controls.append(
        _require_rejections(ids[20], [lambda: invalid_migration(1), lambda: invalid_migration(2)])
    )
    controls.append(
        _require_rejections(
            ids[21],
            probe_mutations(
                1, ("wakes", "cancel_reason", "timeout_reason", "duplicate_rejected")
            ),
        )
    )
    controls.append(
        _require_rejections(
            ids[22],
            probe_mutations(
                2,
                (
                    "owner_slot",
                    "waiter_slot",
                    "inherited",
                    "restored",
                    "granted_slot",
                ),
            ),
        )
    )
    controls.append(
        _require_rejections(
            ids[23],
            [
                lambda: _audit_source_text(
                    sources[0].replace("value.checked_add(1)", "value", 1),
                    sources[1], sources[2], sources[3], sources[4]
                ),
                lambda: _audit_source_text(
                    sources[0].replace("value.checked_sub(1)", "value", 1),
                    sources[1], sources[2], sources[3], sources[4]
                ),
            ],
        )
    )
    controls.append(
        _require_rejections(
            ids[24],
            [
                lambda: _audit_source_text(
                    sources[0].replace(".compare_exchange(0, owner, Ordering::Acquire, Ordering::Relaxed)", ".store(owner, Ordering::Relaxed)", 1),
                    sources[1], sources[2], sources[3], sources[4]
                ),
                lambda: _audit_source_text(
                    sources[0].replace(".compare_exchange(owner, 0, Ordering::Release, Ordering::Relaxed)", ".store(0, Ordering::Relaxed)", 1),
                    sources[1], sources[2], sources[3], sources[4]
                ),
            ],
        )
    )
    controls.append(
        _require_rejections(
            ids[25],
            probe_mutations(3, ("valid", "hostile_rejected", "alignment", "callee_saved")),
        )
    )
    stack_operations = []
    for marker_index, field in (
        (31, "transitions"),
        (31, "errors"),
        (31, "stack_bytes"),
        (32, "stack_bytes_cleared"),
    ):
        candidate = markers.copy()
        candidate[marker_index] = _set_field(
            candidate[marker_index], field, _invalid_value(candidate[marker_index], field)
        )
        stack_operations.append(_marker_operation(candidate))
    controls.append(_require_rejections(ids[26], stack_operations))

    contract = scheduler.read_json(ROOT / scheduler.CONTRACT_RELATIVE)
    stale_controls = copy.deepcopy(contract)
    stale_controls["required_negative_controls"] = stale_controls[
        "required_negative_controls"
    ][:-1]
    stale_claims = copy.deepcopy(contract)
    stale_claims["claims"]["production_ready"] = True
    controls.append(
        _require_rejections(
            ids[27],
            [
                lambda: scheduler._require(
                    not scheduler.contract_errors(stale_controls, ROOT),
                    "stale input binding accepted",
                ),
                lambda: scheduler._require(
                    not scheduler.contract_errors(stale_claims, ROOT),
                    "stale claim binding accepted",
                ),
            ],
        )
    )

    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKSCHED1 hostile-control order diverged")
    case_count = sum(item["case_count"] for item in controls)
    if case_count != HOSTILE_CASE_COUNT:
        raise QualificationError(f"PKSCHED1 hostile-case count changed: {case_count}")
    return controls


def make_readiness(
    toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int
) -> dict[str, Any]:
    contract = scheduler.read_json(ROOT / scheduler.CONTRACT_RELATIVE)
    errors = scheduler.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    if contract["qualification"]["hostile_case_count"] != HOSTILE_CASE_COUNT:
        raise QualificationError("PKSCHED1 contract hostile-case count is stale")
    lock, profile = native_tier0.validate_contracts(ROOT)
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
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pksched1-qualification-", dir=temporary_parent
    ) as temporary:
        temporary_root = Path(temporary)
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        scheduler_boot, scheduler_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "scheduler-boot",
            development_feature=scheduler.FEATURE,
        )
        if (
            b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot
            or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot
        ):
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if scheduler.sha256_bytes(default_boot) == scheduler.sha256_bytes(scheduler_boot):
            raise QualificationError("default and PKSCHED1 PooleBoot binaries are not distinct")
        source_audit = _source_audit()
        linked_switch_audit = _linked_switch_audit(
            toolchain_root, kernel, temporary_root / "linked-audit"
        )
        media_one = native_kernel_load.build_media_bytes(
            scheduler_boot, config, manifest, kernel, artifact_files
        )
        media_two = native_kernel_load.build_media_bytes(
            scheduler_boot, config, manifest, kernel, artifact_files
        )
        if media_one != media_two:
            raise QualificationError("two PKSCHED1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pksched1.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pksched1-run-{run_index}-", dir=run_parent
            ) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"scheduler-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=scheduler.validate_markers,
                        marker_extractor=scheduler.extract_markers,
                        completion_marker=scheduler.COMPLETION_MARKER,
                    )
                except (
                    qualify_native_pooleboot.QualificationError,
                    scheduler.KernelSchedulerError,
                ) as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(
                                encoding="ascii", errors="ignore"
                            ).splitlines()
                            if line.strip().startswith("POOLE")
                        ][-18:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                native_kernel_load.validate_oracle_binding(
                    prefix["boot_prefix"], media_inspection, run["pbp1_transcript"]
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
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        normalized_markers = [
            scheduler.normalize_dynamic_markers(run["markers"]) for run in runs
        ]
        if normalized_markers[0] != normalized_markers[1]:
            raise QualificationError("two PKSCHED1 runs emitted different static markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKSCHED1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKSCHED1 runs produced different PBP1 bytes")
    controls = _negative_controls(runs[0]["markers"], host_probe["lines"])
    observation = scheduler.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_scheduler_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_bsp_cooperative_scheduler_foundation_non_promoting",
        "contract_id": scheduler.CONTRACT_ID,
        "selected_move_id": scheduler.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "phase_status": {
            "N12": "partial",
            "N12.1": "partial",
            "N12.2": "partial",
            "N12.5": "partial",
            "N12.6": "partial",
            "N12.7": "partial",
        },
        "inputs": scheduler.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "scheduler_pooleboot": scheduler_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "host_probe": host_probe,
            "source_audit": source_audit,
            "linked_switch_audit": linked_switch_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": scheduler.sha256_bytes(media_one),
            "byte_count": len(media_one),
            "inspection": media_inspection,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": profile["profile_set_id"],
            "machine": profile["machine"]["type"],
            "cpu_model": profile["machine"]["cpu_model"],
            "virtual_cpu_count": 1,
            "bsp_only": True,
            "acceleration": "tcg_single_thread",
            "deterministic_instruction_clock": True,
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "static_markers_exact_match": True,
            "dynamic_fields_revalidated": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": observation,
        },
        "negative_controls": controls,
        "claims": contract["claims"],
        "non_claims": contract["non_claims"],
        "summary": {
            "scheduler_tests": 14,
            "kernel_host_tests": kernel_readiness["host_tests"]["test_count"],
            "host_probe_receipts": 4,
            "trace_steps": 4096,
            "trace_dispatches": 1761,
            "trace_migrations": 2334,
            "live_tasks": 2,
            "live_dispatches": 8,
            "machine_transitions": 16,
            "stack_bytes_cleared": 32768,
            "negative_controls_total": len(controls),
            "hostile_cases_total": sum(item["case_count"] for item in controls),
            "production_claim_count": 0,
        },
        "open_items": [
            "interrupt-driven timer and wakeup preemption",
            "live application-processor dispatch and cross-CPU migration",
            "per-CPU idle tasks and topology-aware balancing",
            "ring-3 task and address-space switching",
            "per-task FS/GS and full xstate debug and PMU ownership",
            "chained priority inheritance and general sleeping locks",
            "IRQ-save NMI-safe production spinlocks and lock dependency checking",
            "tickless idle latency watchdog and starvation targets",
            "PDC policy hook and scheduler capability authority",
            "physical-target scheduler evidence",
            "N12 exit gate",
            "production signing and promotion",
        ],
    }
    errors = scheduler.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--status-date", default="2026-07-30")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = make_readiness(
        args.toolchain_root, args.qemu_root, args.status_date, args.timeout
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _write_readiness(args.out, report)
    print(f"PKSCHED1 qualification PASS: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
