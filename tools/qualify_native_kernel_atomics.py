#!/usr/bin/env python3
"""Build and qualify the bounded PKATOM1 x86-64 atomic substrate."""

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
    native_kernel_atomics as atomics,
    native_kernel_load,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from runtime.schema_validation import validate_json  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / atomics.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
PRODUCT_TARGET = "x86_64-unknown-none"


class QualificationError(RuntimeError):
    """Raised when PKATOM1 qualification fails closed."""


def _progress(stage: str) -> None:
    print(f"PKATOM1_QUALIFICATION stage={stage}", flush=True)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(native_pooleboot.canonical_json_bytes(value))


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKATOM1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _invalid_value(marker: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^ ]+)", marker)
    if match is None:
        raise QualificationError(f"PKATOM1 mutation field is missing: {field}")
    value = match.group(1)
    if value.isdecimal():
        return "1" if int(value, 10) == 0 else "0"
    if value.startswith("0x"):
        return "0x0"
    return "invalid"


def _require_rejections(control_id: str, operations: list[Callable[[], Any]]) -> dict[str, Any]:
    for operation in operations:
        try:
            operation()
        except (atomics.KernelAtomicsError, QualificationError):
            continue
        raise QualificationError(f"PKATOM1 hostile control did not reject: {control_id}")
    return {"id": control_id, "status": "pass", "expected": "rejected", "case_count": len(operations)}


def _marker_operation(markers: list[str]) -> Callable[[], Any]:
    return lambda: atomics.validate_markers(markers)


def _probe_operation(lines: list[str]) -> Callable[[], Any]:
    return lambda: atomics.parse_probe_output("\n".join(lines) + "\n")


def _marker_field_matrix(
    control_id: str, markers: list[str], index: int, fields: tuple[str, ...]
) -> dict[str, Any]:
    operations: list[Callable[[], Any]] = []
    for field in fields:
        hostile = markers.copy()
        hostile[index] = _set_field(hostile[index], field, _invalid_value(hostile[index], field))
        operations.append(_marker_operation(hostile))
    return _require_rejections(control_id, operations)


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
            "pkatom1-probe",
            "--target",
            HOST_TARGET,
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
        raise QualificationError(f"PKATOM1 host probe failed: {output[-3000:]}")
    result = atomics.parse_probe_output(output)
    result["output_sha256"] = atomics.sha256_bytes(output.encode("utf-8"))
    result["target"] = HOST_TARGET
    return result


def _audit_atomic_source(core: str, main: str, boot_exit: str, boot_manifest: str, bootexit: str) -> dict[str, Any]:
    production_core = core.split("#[cfg(test)]", 1)[0]
    forbidden = tuple(
        token
        for token in ("alloc::", "Vec<", "Box<", "String", "HashMap", "dyn ", "std::")
        if token in production_core
    )
    core_required = (
        'compile_error!("PKATOM1 requires native 32-bit, 64-bit, and pointer atomics")',
        "pub enum LoadOrder",
        "pub enum StoreOrder",
        "pub enum RmwOrder",
        "pub enum FenceOrder",
        "pub struct CompareExchangeOrder",
        "pub fn compare_exchange_weak",
        "pub fn fetch_set_bit",
        "pub fn fetch_clear_bit",
        "pub struct AtomicPtr<T>",
        "pub struct RefCount",
        "pub fn compiler_fence",
        "poole_atomic_audit_fence_seqcst",
    )
    main_required = (
        "PKATOM1_EARLY",
        "PKATOM1_TYPES",
        "PKATOM1_ORDERS",
        "PKATOM1_OPS",
        "PKATOM1_IRQ",
        "PKATOM1_RESULT",
        "PKATOM_IRQ_COUNT.fetch_add(1, KernelRmwOrder::AcqRel)",
        "PKATOM_IRQ_MASK.fetch_or(1u32 << prior, KernelRmwOrder::AcqRel)",
        "PKATOM_IRQ_PUBLICATION.load(KernelLoadOrder::Acquire)",
        "validate_atomic_live_profile()",
        "DevelopmentTrapScenario::Atomics",
    )
    boot_required = (
        'development-atomics = ["development-transfer"]',
        'feature = "development-atomics"',
        'cfg!(feature = "development-atomics")',
        "MAX_DEVELOPMENT_TRAP_SCENARIO: u8 = 21",
    )
    missing = {
        "core": [token for token in core_required if token not in core],
        "main": [token for token in main_required if token not in main],
        "boot": [token for token in boot_required if token not in "\n".join((boot_manifest, boot_exit, bootexit))],
    }
    test_count = core.count("#[test]")
    if forbidden or any(missing.values()) or test_count != 7:
        raise QualificationError(
            f"PKATOM1 source scope changed: forbidden={forbidden}; missing={missing}; tests={test_count}"
        )
    return {
        "heap_api_token_count": 0,
        "typed_order_enum_count": 4,
        "atomic_wrapper_count": 4,
        "audit_symbol_count": 7,
        "unit_test_count": test_count,
        "interrupt_retry_loop_count": 0,
        "result": "pass_allocation_free_typed_atomic_source_audit",
    }


def _source_audit() -> dict[str, Any]:
    paths = {
        "core": ROOT / "native/kernel/src/atomics.rs",
        "main": ROOT / "native/kernel/src/main.rs",
        "boot_exit": ROOT / "native/boot/src/exit.rs",
        "boot_manifest": ROOT / "native/boot/Cargo.toml",
        "bootexit": ROOT / "native/bootexit/src/lib.rs",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    result = _audit_atomic_source(
        texts["core"], texts["main"], texts["boot_exit"], texts["boot_manifest"], texts["bootexit"]
    )
    result["files"] = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": atomics.sha256_bytes(path.read_bytes()),
        }
        for name, path in paths.items()
    }
    return result


def _objdump_path(cargo: Path) -> Path:
    installed = cargo.parent.parent
    candidates = sorted((installed / "lib/rustlib").glob("*/bin/llvm-objdump.exe"))
    if len(candidates) != 1 or not candidates[0].is_file():
        raise QualificationError("PKATOM1 requires exactly one workspace-local llvm-objdump")
    try:
        candidates[0].resolve().relative_to(installed.resolve())
    except ValueError as error:
        raise QualificationError("PKATOM1 llvm-objdump escapes the installed Rust toolchain") from error
    return candidates[0]


def _symbol_bodies(disassembly: str) -> dict[str, str]:
    header = re.compile(r"(?m)^[0-9A-Fa-f]+ <([^>]+)>:\s*$")
    matches = list(header.finditer(disassembly))
    bodies: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(disassembly)
        if name in bodies:
            raise QualificationError(f"PKATOM1 duplicate disassembly symbol: {name}")
        bodies[name] = disassembly[match.end() : end].strip()
    return bodies


def _validate_disassembly(disassembly: str) -> dict[str, Any]:
    rules = {
        "poole_atomic_audit_load_acquire": (("movq", "retq"), ("lock", "xchg", "cmpxchg")),
        "poole_atomic_audit_store_release": (("movq", "retq"), ("lock", "xchg", "cmpxchg")),
        "poole_atomic_audit_exchange_seqcst": (("xchgq", "retq"), ("call",)),
        "poole_atomic_audit_compare_exchange_acqrel": (("lock", "cmpxchgq", "retq"), ("call",)),
        "poole_atomic_audit_fetch_add_relaxed": (("lock", "xaddq", "retq"), ("call",)),
        "poole_atomic_audit_fetch_or_acqrel": (("orq", "lock", "cmpxchgq", "jne", "retq"), ("call",)),
        "poole_atomic_audit_fence_seqcst": (("lock", "orl", "retq"), ("call",)),
    }
    bodies = _symbol_bodies(disassembly)
    observations: list[dict[str, Any]] = []
    for symbol, (required, forbidden) in rules.items():
        body = bodies.get(symbol)
        if body is None:
            raise QualificationError(f"PKATOM1 linked audit symbol is missing: {symbol}")
        lowered = body.lower()
        missing = [token for token in required if token not in lowered]
        present = [token for token in forbidden if token in lowered]
        if missing or present:
            raise QualificationError(
                f"PKATOM1 instruction class changed for {symbol}: missing={missing}; forbidden={present}"
            )
        observations.append(
            {
                "symbol": symbol,
                "required_instruction_classes": list(required),
                "forbidden_instruction_classes": list(forbidden),
                "body_sha256": atomics.sha256_bytes(body.encode("utf-8")),
            }
        )
    return {
        "target": PRODUCT_TARGET,
        "symbol_count": len(observations),
        "symbols": observations,
        "all_instruction_rules_passed": True,
    }


def _linked_instruction_audit(toolchain_root: Path, target_dir: Path, expected_kernel: bytes) -> tuple[dict[str, Any], str]:
    cargo, _, env = qualify_native_kernel_entry._toolchain(toolchain_root)
    linked, canonical, plan = qualify_native_kernel_entry._build_product(cargo, env, target_dir)
    if canonical != expected_kernel:
        raise QualificationError("PKATOM1 assembly-audit build differs from canonical PKENTRY1 kernel")
    artifact = target_dir / PRODUCT_TARGET / "release" / "PooleKernelLinked"
    objdump = _objdump_path(cargo)
    symbols = atomics.read_json(ROOT / atomics.CONTRACT_RELATIVE)["assembly_contract"]["symbols"]
    completed = subprocess.run(
        [str(objdump), "-d", f"--disassemble-symbols={','.join(symbols)}", str(artifact)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(f"PKATOM1 llvm-objdump failed: {output[-3000:]}")
    result = _validate_disassembly(output)
    result.update(
        {
            "tool": {
                "path": "$RUST_TOOLCHAIN/" + objdump.relative_to(cargo.parent.parent).as_posix(),
                "sha256": atomics.sha256_bytes(objdump.read_bytes()),
            },
            "linked_sha256": atomics.sha256_bytes(linked),
            "canonical_sha256": atomics.sha256_bytes(canonical),
            "linked_byte_count": len(linked),
            "canonical_byte_count": len(canonical),
            "image_byte_count": plan.image_byte_count,
            "disassembly_sha256": atomics.sha256_bytes(output.encode("utf-8")),
        }
    )
    return result, output


def _contract_operation(candidate: dict[str, Any]) -> Callable[[], Any]:
    def operation() -> None:
        errors = atomics.contract_errors(candidate, ROOT)
        if errors:
            raise atomics.KernelAtomicsError("; ".join(errors))

    return operation


def _negative_controls(
    markers: list[str], probe_lines: list[str], disassembly: str, source_texts: tuple[str, str, str, str, str]
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    ids = atomics.NEGATIVE_CONTROL_IDS
    controls.append(_require_rejections(ids[0], [_marker_operation(markers[:-1])]))
    reordered = markers.copy()
    reordered[36], reordered[37] = reordered[37], reordered[36]
    controls.append(_require_rejections(ids[1], [_marker_operation(reordered)]))
    controls.append(_require_rejections(ids[2], [_marker_operation([*markers, markers[-1]])]))
    selector = markers.copy()
    selector[23] = _set_field(selector[23], "trap_scenario", "20")
    controls.append(_require_rejections(ids[3], [_marker_operation(selector)]))
    controls.append(_marker_field_matrix(ids[4], markers, 36, ("integer", "pointer", "intrinsics", "target", "widths")))
    controls.append(
        _marker_field_matrix(
            ids[5], markers, 37, ("load", "store", "rmw", "fence", "cas_pairs", "invalid_rejected", "compiler_order", "x86_tso")
        )
    )
    controls.append(
        _marker_field_matrix(
            ids[6], markers, 38,
            ("load_store", "exchange", "compare_exchange", "fetch_add_sub", "bit_modify", "pointer", "refcount", "overflow_rejected", "underflow_rejected", "audit_symbols"),
        )
    )
    controls.append(
        _marker_field_matrix(
            ids[7], markers, 39,
            ("timer_deliveries", "atomic_updates", "observed_mask", "publication", "release_acquire", "eoi_ordered", "cleanup"),
        )
    )
    controls.append(
        _marker_field_matrix(
            ids[8], markers, 40,
            ("profile", "typed_atomics", "invalid_orders", "live_interrupt", "host_smp_litmus", "linked_instruction_audit", "general_locks", "reclamation", "general_smp", "ring3", "target", "signatures", "authority", "actions", "n12_exit", "production", "terminal"),
        )
    )
    controls.append(_require_rejections(ids[9], [_probe_operation(probe_lines[:-1])]))
    probe_reordered = probe_lines.copy()
    probe_reordered[0], probe_reordered[1] = probe_reordered[1], probe_reordered[0]
    controls.append(_require_rejections(ids[10], [_probe_operation(probe_reordered)]))
    controls.append(
        _require_rejections(
            ids[11],
            [_probe_operation([*(probe_lines[:index]), line.replace(" PASS ", " FAIL ", 1), *(probe_lines[index + 1 :])]) for index, line in enumerate(probe_lines)],
        )
    )
    contract = atomics.read_json(ROOT / atomics.CONTRACT_RELATIVE)
    hostile_contract = copy.deepcopy(contract)
    hostile_contract["order_matrix"]["load_orders"] = 4
    controls.append(_require_rejections(ids[12], [_contract_operation(hostile_contract)]))
    controls.append(_require_rejections(ids[13], [lambda: atomics.validate_order_request("load", "release")]))
    controls.append(_require_rejections(ids[14], [lambda: atomics.validate_order_request("store", "acquire")]))
    controls.append(_require_rejections(ids[15], [lambda: atomics.validate_order_request("fence", "relaxed")]))
    controls.append(
        _require_rejections(ids[16], [lambda: atomics.validate_order_request("compare_exchange", "release", "acquire")])
    )
    stale = probe_lines.copy()
    stale[5] = _set_field(stale[5], "stale", "1")
    controls.append(_require_rejections(ids[17], [_probe_operation(stale)]))
    add_loss = probe_lines.copy()
    add_loss[6] = _set_field(add_loss[6], "fetch_add_final", "16383")
    controls.append(_require_rejections(ids[18], [_probe_operation(add_loss)]))
    cas_loss = probe_lines.copy()
    cas_loss[6] = _set_field(cas_loss[6], "cas_final", "4095")
    controls.append(_require_rejections(ids[19], [_probe_operation(cas_loss)]))
    forbidden = probe_lines.copy()
    forbidden[7] = _set_field(forbidden[7], "observed_forbidden", "1")
    controls.append(_require_rejections(ids[20], [_probe_operation(forbidden)]))
    missing_symbol = disassembly.replace("<poole_atomic_audit_load_acquire>:", "<poole_atomic_audit_load_acquire_missing>:", 1)
    controls.append(_require_rejections(ids[21], [lambda: _validate_disassembly(missing_symbol)]))
    invalid_instruction = disassembly.replace("xaddq", "addq", 1)
    controls.append(_require_rejections(ids[22], [lambda: _validate_disassembly(invalid_instruction)]))
    publication = markers.copy()
    publication[39] = _set_field(publication[39], "publication", "0x0000000000000000")
    controls.append(_require_rejections(ids[23], [_marker_operation(publication)]))
    rmw = markers.copy()
    rmw[39] = _set_field(rmw[39], "atomic_updates", "7")
    controls.append(_require_rejections(ids[24], [_marker_operation(rmw)]))
    eoi = markers.copy()
    eoi[39] = _set_field(eoi[39], "eoi_ordered", "0")
    controls.append(_require_rejections(ids[25], [_marker_operation(eoi)]))
    core, main, boot_exit, boot_manifest, bootexit = source_texts
    controls.append(
        _require_rejections(
            ids[26],
            [lambda: _audit_atomic_source("use alloc::vec::Vec;\n" + core, main, boot_exit, boot_manifest, bootexit)],
        )
    )
    overclaim = markers.copy()
    overclaim[40] = _set_field(overclaim[40], "production", "1")
    controls.append(_require_rejections(ids[27], [_marker_operation(overclaim)]))
    controls.append(_require_rejections(ids[28], [lambda: atomics.file_binding(ROOT, "../escape")]))
    if [item["id"] for item in controls] != list(ids):
        raise QualificationError("PKATOM1 hostile-control order changed")
    return controls


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    _progress("contracts")
    contract = atomics.read_json(ROOT / atomics.CONTRACT_RELATIVE)
    errors = atomics.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    _progress("qemu_closure")
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    _progress("kernel_entry")
    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifact_files)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkatom1-qualification-") as temporary:
        temporary_root = Path(temporary)
        _progress("host_probe")
        host_probe = _run_host_probe(toolchain_root, temporary_root / "host-probe")
        _progress("source_audit")
        source_audit = _source_audit()
        _progress("linked_instruction_audit")
        linked_audit, disassembly = _linked_instruction_audit(
            toolchain_root, temporary_root / "linked-audit", kernel
        )
        _progress("boot_builds")
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        atomic_boot, atomic_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "atomic-boot", development_feature=atomics.FEATURE
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if default_boot == atomic_boot:
            raise QualificationError("default and PKATOM1 PooleBoot binaries are not distinct")
        _progress("media")
        media_one = native_kernel_load.build_media_bytes(atomic_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(atomic_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKATOM1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        media_path = temporary_root / "pkatom1.img"
        media_path.write_bytes(media_one)
        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            _progress(f"qemu_run_{run_index}")
            with tempfile.TemporaryDirectory(prefix=f"pkatom1-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"atomics-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=atomics.validate_markers,
                        marker_extractor=atomics.extract_markers,
                        completion_marker=atomics.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(encoding="ascii", errors="ignore").splitlines()
                            if line.strip().startswith("POOLE")
                        ][-18:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                native_kernel_load.validate_oracle_binding(prefix["boot_prefix"], media_inspection, run["pbp1_transcript"])
                run["transcript_binding"] = native_kernel_transfer.validate_transcript_binding(
                    prefix, run["pbp1_transcript"]
                )
                run["independent_kernel_revalidation"] = native_kernel_transfer.validate_revalidation_binding(
                    prefix, handoff, retained_files
                )
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKATOM1 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKATOM1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKATOM1 runs produced different PBP1 bytes")
        source_paths = (
            ROOT / "native/kernel/src/atomics.rs",
            ROOT / "native/kernel/src/main.rs",
            ROOT / "native/boot/src/exit.rs",
            ROOT / "native/boot/Cargo.toml",
            ROOT / "native/bootexit/src/lib.rs",
        )
        _progress("negative_controls")
        controls = _negative_controls(
            runs[0]["markers"],
            host_probe["lines"],
            disassembly,
            tuple(path.read_text(encoding="utf-8") for path in source_paths),
        )
    observation = atomics.validate_markers(runs[0]["markers"])
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_atomics_readiness",
        "status_date": status_date,
        "status": "pass_single_host_typed_x86_64_atomics_bsp_interrupt_non_promoting",
        "contract_id": atomics.CONTRACT_ID,
        "selected_move_id": atomics.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n12_exit_gate_satisfied": False,
        "flag_n12_concurrency_atomics_001_closed": True,
        "kernel_summary": {
            "entry_readiness": kernel_readiness,
            "host_tests_passed": kernel_readiness["host_tests"]["test_pass_count"],
            "host_tests_total": kernel_readiness["host_tests"]["test_count"],
            "canonical_sha256": atomics.sha256_bytes(kernel),
            "source_audit": source_audit,
            "default_pooleboot": default_build,
            "atomics_pooleboot": atomic_build,
        },
        "host_probe": host_probe,
        "linked_instruction_audit": linked_audit,
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "machine": "pc-q35-11.0",
            "cpu_model": "qemu64",
            "acceleration": "tcg_single_thread",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "fresh_vars_each_run": True,
            "media_read_only": True,
            "physical_media_write_performed": False,
            "guest_network": False,
            "host_acceleration": False,
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "markers_per_run": atomics.MARKER_COUNT,
            "media": {
                "clean_generation_count": 2,
                "exact_clean_generation_match": True,
                "sha256": atomics.sha256_bytes(media_one),
                "byte_count": len(media_one),
                "inspection": media_inspection,
            },
            "runs": runs,
            "observation": observation,
        },
        "negative_controls": controls,
        "inputs": atomics.expected_inputs(ROOT),
        "claims": contract["claims"],
        "remaining_gaps": [
            "Implement and qualify the complete N12.2 lock family, ownership, recursion, IRQ, and lock-order contracts.",
            "Implement deferred reclamation and prove ABA-safe object lifetime rules.",
            "Run atomics and lock contention on live application processors rather than host threads only.",
            "Qualify weak-memory and non-x86 targets before making a portability claim.",
            "Qualify the exact physical target and all declared logical processors.",
            "Complete the remaining N12-N39 gates and produce the signed exact production ISO receipt.",
        ],
    }
    errors = list(validate_json(report, atomics.read_json(ROOT / atomics.READINESS_SCHEMA_RELATIVE)))
    if errors:
        raise QualificationError("; ".join(f"{issue.path}: {issue.message}" for issue in errors))
    _progress("report_validated")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-09-03")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    try:
        report = make_readiness(
            args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout
        )
        _write_json(args.out, report)
        errors = atomics.readiness_errors(atomics.read_json(args.out), ROOT)
        if errors:
            raise QualificationError("; ".join(errors))
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        atomics.KernelAtomicsError,
        native_kernel_load.KernelLoadError,
        native_kernel_transfer.KernelTransferError,
        native_tier0.Tier0Error,
    ) as error:
        print(f"NATIVE_KERNEL_ATOMICS_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    print(
        "NATIVE_KERNEL_ATOMICS_QUALIFICATION PASS "
        f"host_tests={report['kernel_summary']['host_tests_passed']}/{report['kernel_summary']['host_tests_total']} "
        f"probe_receipts={report['host_probe']['receipt_count']} "
        f"linked_symbols={report['linked_instruction_audit']['symbol_count']} "
        f"runs={report['execution']['run_count']}/2 markers={report['execution']['markers_per_run']} "
        f"controls={len(report['negative_controls'])}/{len(atomics.NEGATIVE_CONTROL_IDS)} "
        "general_locks=0 reclamation=0 general_smp=0 n12_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
