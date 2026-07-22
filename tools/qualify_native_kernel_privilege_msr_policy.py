#!/usr/bin/env python3
"""Build and qualify the bounded PKMSR1 privileged-MSR policy profile."""

from __future__ import annotations

import argparse
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
    native_kernel_privilege_msr_policy as privilege_msr,
    native_kernel_transfer,
    native_pooleboot,
    native_tier0,
)
from tools import (  # noqa: E402
    qualify_native_kernel_entry,
    qualify_native_kernel_xstate_exception,
    qualify_native_pooleboot,
)


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / privilege_msr.READINESS_RELATIVE


class QualificationError(RuntimeError):
    """Raised when live PKMSR1 qualification fails closed."""


def _set_field(marker: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\b{re.escape(name)}=)([^ ]+)")
    if len(pattern.findall(marker)) != 1:
        raise QualificationError(f"PKMSR1 mutation field is not unique: {name}")
    return pattern.sub(rf"\g<1>{value}", marker, count=1)


def _hex(value: int) -> str:
    return f"0x{value & ((1 << 64) - 1):016X}"


def _require_rejection(control_id: str, candidate: list[str]) -> dict[str, str]:
    try:
        privilege_msr.validate_markers(candidate)
    except privilege_msr.KernelPrivilegeMsrPolicyError:
        return {"id": control_id, "status": "pass", "expected": "rejected"}
    raise QualificationError(f"PKMSR1 hostile control did not reject: {control_id}")


def _negative_controls(markers: list[str]) -> list[dict[str, str]]:
    observation = privilege_msr.validate_markers(markers)
    features = observation["features"]
    linkage = observation["linkage"]
    machine_check = observation["machine_check"]

    candidates: dict[str, list[str]] = {}
    candidates["NEG-N7-PKMSR-MARKER-OMISSION"] = markers[:-1]
    ordered = markers.copy()
    ordered[29], ordered[30] = ordered[30], ordered[29]
    candidates["NEG-N7-PKMSR-MARKER-ORDER"] = ordered
    candidates["NEG-N7-PKMSR-MARKER-DUPLICATE"] = [*markers, markers[-1]]

    def changed(index: int, field: str, value: str) -> list[str]:
        candidate = markers.copy()
        candidate[index] = _set_field(candidate[index], field, value)
        return candidate

    candidates["NEG-N7-PKMSR-SELECTOR"] = changed(23, "trap_scenario", "0")
    candidates["NEG-N7-PKMSR-CONTRACT"] = changed(29, "contract", "PKMSR2")
    candidates["NEG-N7-PKMSR-VENDOR"] = changed(29, "vendor_hex", b"GenuineIntel".hex().upper())
    candidates["NEG-N7-PKMSR-MAX-BASIC"] = changed(29, "max_basic", _hex(9))
    candidates["NEG-N7-PKMSR-MAX-EXTENDED"] = changed(29, "max_extended", _hex(0x80000007))
    candidates["NEG-N7-PKMSR-MCE-FEATURE"] = changed(29, "leaf1_edx", _hex(features["leaf1_edx"] & ~(1 << 7)))
    candidates["NEG-N7-PKMSR-MCA-FEATURE"] = changed(29, "leaf1_edx", _hex(features["leaf1_edx"] & ~(1 << 14)))
    candidates["NEG-N7-PKMSR-SYSCALL-FEATURE"] = changed(29, "ext1_edx", _hex(features["ext1_edx"] & ~(1 << 11)))
    candidates["NEG-N7-PKMSR-RDTSCP-FEATURE"] = changed(29, "ext1_edx", _hex(features["ext1_edx"] | (1 << 27)))
    candidates["NEG-N7-PKMSR-LONG-MODE-FEATURE"] = changed(29, "ext1_edx", _hex(features["ext1_edx"] & ~(1 << 29)))
    candidates["NEG-N7-PKMSR-FEATURE-MARKER"] = changed(29, "syscall", "0")
    arch_pmu = markers.copy()
    arch_pmu[29] = _set_field(arch_pmu[29], "leafa_eax", _hex(1))
    arch_pmu[29] = _set_field(arch_pmu[29], "arch_pmu_version", "1")
    candidates["NEG-N7-PKMSR-ARCH-PMU"] = arch_pmu
    amd_pmu = markers.copy()
    amd_pmu[29] = _set_field(amd_pmu[29], "max_extended", _hex(0x80000022))
    amd_pmu[29] = _set_field(amd_pmu[29], "ext22_eax", _hex(1))
    amd_pmu[29] = _set_field(amd_pmu[29], "amd_perfmon_v2", "1")
    candidates["NEG-N7-PKMSR-AMD-PERFMON-V2"] = amd_pmu
    candidates["NEG-N7-PKMSR-CR4-PCE"] = changed(29, "cr4", _hex(features["cr4"] | (1 << 8)))
    candidates["NEG-N7-PKMSR-EFER-REQUIRED"] = changed(30, "efer", _hex(linkage["efer"] & ~(1 << 11)))
    candidates["NEG-N7-PKMSR-EFER-SCE"] = changed(30, "efer", _hex(linkage["efer"] | 1))
    candidates["NEG-N7-PKMSR-EFER-RESERVED"] = changed(30, "efer", _hex(linkage["efer"] | (1 << 63)))
    candidates["NEG-N7-PKMSR-STAR-ACTIVE"] = changed(30, "star", _hex(1))
    candidates["NEG-N7-PKMSR-LSTAR-CANONICAL"] = changed(30, "lstar", _hex(0x0000800000000000))
    candidates["NEG-N7-PKMSR-SFMASK-ACTIVE"] = changed(30, "sfmask", _hex(1 << 9))
    candidates["NEG-N7-PKMSR-FS-BASE-ACTIVE"] = changed(31, "fs_base", _hex(0x1000))
    candidates["NEG-N7-PKMSR-GS-BASE-CANONICAL"] = changed(31, "gs_base", _hex(0x0000800000000000))
    candidates["NEG-N7-PKMSR-TSC-AUX-ACTIVE"] = changed(31, "tsc_aux", _hex(1))
    candidates["NEG-N7-PKMSR-TSC-AUX-READ"] = changed(31, "tsc_aux_read", "1")
    candidates["NEG-N7-PKMSR-MCG-CAP-RESERVED"] = changed(32, "mcg_cap", _hex(machine_check["mcg_cap"] | (1 << 9)))
    zero_banks = markers.copy()
    zero_banks[32] = _set_field(zero_banks[32], "mcg_cap", _hex(machine_check["mcg_cap"] & ~0xFF))
    zero_banks[32] = _set_field(zero_banks[32], "bank_count", "0")
    candidates["NEG-N7-PKMSR-MCG-BANK-COUNT"] = zero_banks
    candidates["NEG-N7-PKMSR-MCG-STATUS-ACTIVE"] = changed(32, "mcg_status", _hex(1))
    candidates["NEG-N7-PKMSR-MCG-STATUS-RESERVED"] = changed(32, "mcg_status", _hex(1 << 3))
    candidates["NEG-N7-PKMSR-MCG-CTL-BANK"] = changed(32, "mcg_ctl", _hex(machine_check["mcg_ctl"] ^ 1))
    candidates["NEG-N7-PKMSR-MCG-READ-COUNT"] = changed(32, "reads", str(machine_check["reads"] + 1))
    candidates["NEG-N7-PKMSR-MCG-BANK-READ"] = changed(32, "bank_reads", "1")
    candidates["NEG-N7-PKMSR-PMU-MSR-READ"] = changed(33, "msr_reads", "1")
    candidates["NEG-N7-PKMSR-RDPMC"] = changed(33, "rdpmc", "1")
    candidates["NEG-N7-PKMSR-RESULT-READ-COUNT"] = changed(34, "msr_reads", "0")
    candidates["NEG-N7-PKMSR-MSR-WRITE"] = changed(34, "msr_writes", "1")
    candidates["NEG-N7-PKMSR-CONTROL-WRITE"] = changed(34, "control_writes", "1")
    candidates["NEG-N7-PKMSR-SIGNATURE"] = changed(34, "signatures", "1")
    candidates["NEG-N7-PKMSR-AUTHORITY"] = changed(34, "authority", "1")
    candidates["NEG-N7-PKMSR-ACTION"] = changed(34, "actions", "1")
    candidates["NEG-N7-PKMSR-INTERRUPT"] = changed(34, "interrupts", "1")
    candidates["NEG-N7-PKMSR-SYSCALL-ACTIVE"] = changed(34, "syscall_active", "1")
    candidates["NEG-N7-PKMSR-MCE-HANDLER"] = changed(34, "mce_handler", "1")
    candidates["NEG-N7-PKMSR-PMU-OWNER"] = changed(34, "pmu_owner", "1")
    candidates["NEG-N7-PKMSR-TERMINAL"] = changed(34, "terminal", "return")

    if set(candidates) != set(privilege_msr.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKMSR1 hostile-control implementation is incomplete")
    return [
        _require_rejection(control_id, candidates[control_id])
        for control_id in privilege_msr.NEGATIVE_CONTROL_IDS
    ]


def _function_source(source: str, name: str) -> str:
    matches = list(re.finditer(rf"(?m)^pub unsafe fn {re.escape(name)}\(", source))
    if len(matches) != 1:
        raise QualificationError(f"PKMSR1 source-audit function changed: {name}")
    start = matches[0].start()
    opening = source.find("{", matches[0].end())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise QualificationError(f"PKMSR1 source-audit function is unterminated: {name}")


def _audit_source_text(source: str) -> dict[str, Any]:
    observer = _function_source(source, "observe_privilege_msr_policy").lower()
    forbidden = ("wrmsr", "rdpmc", "syscall", "sysret", "swapgs", "xsetbv", "mov cr0,", "mov cr4,")
    instruction_patterns = {
        instruction: re.compile(rf'"[^"\n]*\b{re.escape(instruction)}\b[^"\n]*"')
        for instruction in forbidden
    }
    hits = [instruction for instruction, pattern in instruction_patterns.items() if pattern.search(observer)]
    required_msr_constants = (
        "ia32_efer",
        "ia32_star",
        "ia32_lstar",
        "ia32_cstar",
        "ia32_sfmask",
        "ia32_fs_base",
        "ia32_gs_base",
        "ia32_kernel_gs_base",
        "ia32_tsc_aux",
        "ia32_mcg_cap",
        "ia32_mcg_status",
        "ia32_mcg_ctl",
    )
    missing = [name for name in required_msr_constants if name not in observer]
    if hits or missing:
        raise QualificationError(f"PKMSR1 source audit changed: forbidden={hits}; missing={missing}")
    return {
        "scope": "observe_privilege_msr_policy support gates and allowlisted reads",
        "required_msr_constant_count": len(required_msr_constants),
        "forbidden_instructions": list(forbidden),
        "forbidden_instruction_hits": [],
        "result": "pass_read_only_support_gated_source_audit",
    }


def _source_audit() -> dict[str, Any]:
    return _audit_source_text((ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8"))


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        raise QualificationError(f"command failed ({completed.returncode}): {' '.join(command)}; {completed.stderr[-2000:]}")
    return completed.stdout


def _linked_machine_audit(toolchain_root: Path, temporary_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    llvm, tool = qualify_native_kernel_xstate_exception._llvm_observation(toolchain_root)
    cargo, _, environment = qualify_native_kernel_entry._toolchain(toolchain_root)
    linked, canonical, plan = qualify_native_kernel_entry._build_product(
        cargo, environment, temporary_root / "pkmsr1-linked-audit"
    )
    linked_path = (
        temporary_root
        / "pkmsr1-linked-audit"
        / qualify_native_kernel_entry.PRODUCT_TARGET
        / "release"
        / "PooleKernelLinked"
    )
    disassembly = _run(
        [str(llvm), "--disassemble", "--demangle", "--no-show-raw-insn", str(linked_path)], ROOT
    )
    functions = qualify_native_kernel_xstate_exception._parse_disassembly(disassembly)
    mnemonics = [
        mnemonic.lower()
        for instructions in functions.values()
        for mnemonic, _ in instructions
    ]
    counts = {
        mnemonic: mnemonics.count(mnemonic)
        for mnemonic in ("rdmsr", "wrmsr", "rdpmc", "syscall", "sysret", "swapgs")
    }
    expected_counts = {
        "rdmsr": 17,
        "wrmsr": 0,
        "rdpmc": 0,
        "syscall": 0,
        "sysret": 0,
        "swapgs": 0,
    }
    if counts != expected_counts:
        raise QualificationError(f"PKMSR1 linked privileged instruction scope changed: {counts}")
    audit = {
        "linked_byte_count": len(linked),
        "linked_sha256": privilege_msr.sha256_bytes(linked),
        "canonical_byte_count": len(canonical),
        "canonical_sha256": privilege_msr.sha256_bytes(canonical),
        "relocation_count": plan.relocation_count,
        "disassembly_byte_count": len(disassembly.encode("utf-8")),
        "disassembly_sha256": privilege_msr.sha256_bytes(disassembly.encode("utf-8")),
        "instruction_record_count": len(mnemonics),
        "instruction_counts": counts,
        "result": "pass_linked_rdmsr_present_no_activation_or_write_instruction",
    }
    return audit, tool


def make_readiness(toolchain_root: Path, qemu_root: Path, status_date: str, timeout: int) -> dict[str, Any]:
    contract = privilege_msr.read_json(ROOT / privilege_msr.CONTRACT_RELATIVE)
    errors = privilege_msr.contract_errors(contract, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)

    kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
    artifact_files = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifact_files)
    retained_files = native_kernel_transfer.canonical_retained_files(manifest, kernel, artifact_files)

    temporary_parent = ROOT / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    run_parent = ROOT / "runs" / "native-tier0"
    run_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkmsr1-qualification-", dir=temporary_parent) as temporary:
        temporary_root = Path(temporary)
        default_boot, default_build = qualify_native_pooleboot._build_and_test(
            toolchain_root, temporary_root / "default-boot"
        )
        policy_boot, policy_build = qualify_native_pooleboot._build_and_test(
            toolchain_root,
            temporary_root / "policy-boot",
            development_feature=privilege_msr.FEATURE,
        )
        if b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default_boot or b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" not in default_boot:
            raise QualificationError("default PooleBoot development-transfer isolation failed")
        if privilege_msr.sha256_bytes(default_boot) == privilege_msr.sha256_bytes(policy_boot):
            raise QualificationError("default and PKMSR1 PooleBoot profiles are not distinct")

        linked_audit, llvm_tool = _linked_machine_audit(toolchain_root, temporary_root)
        source_audit = _source_audit()
        media_one = native_kernel_load.build_media_bytes(policy_boot, config, manifest, kernel, artifact_files)
        media_two = native_kernel_load.build_media_bytes(policy_boot, config, manifest, kernel, artifact_files)
        if media_one != media_two:
            raise QualificationError("two PKMSR1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_one)
        if media_inspection["files"][3]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKMSR1 media kernel differs from PKENTRY1")
        media_path = temporary_root / "pkmsr1.img"
        media_path.write_bytes(media_one)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        handoffs: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pkmsr1-run-{run_index}-", dir=run_parent) as run_temporary:
                run_directory = Path(run_temporary)
                try:
                    run, screenshot, handoff = qualify_native_pooleboot._execute_once(
                        f"privilege-msr-policy-run-{run_index}",
                        lock,
                        profile,
                        qemu_root,
                        media_path,
                        run_directory,
                        timeout,
                        marker_validator=privilege_msr.validate_markers,
                        marker_extractor=privilege_msr.extract_markers,
                        completion_marker=privilege_msr.COMPLETION_MARKER,
                    )
                except qualify_native_pooleboot.QualificationError as error:
                    debug_path = run_directory / profile["evidence_contract"]["debugcon_log"]
                    tail: list[str] = []
                    if debug_path.is_file():
                        tail = [
                            line.strip()
                            for line in debug_path.read_text(encoding="ascii", errors="ignore").splitlines()
                            if line.strip().startswith("POOLE")
                        ][-12:]
                    raise QualificationError(f"{error}; debug_tail={tail!r}") from error
                prefix = run["marker_summary"]["transfer_prefix"]
                try:
                    native_kernel_load.validate_oracle_binding(prefix["boot_prefix"], media_inspection, run["pbp1_transcript"])
                    run["transcript_binding"] = native_kernel_transfer.validate_transcript_binding(prefix, run["pbp1_transcript"])
                    run["independent_kernel_revalidation"] = native_kernel_transfer.validate_revalidation_binding(
                        prefix, handoff, retained_files
                    )
                except (native_kernel_load.KernelLoadError, native_kernel_transfer.KernelTransferError) as error:
                    raise QualificationError(str(error)) from error
                runs.append(run)
                screenshots.append(screenshot)
                handoffs.append(handoff)
        if runs[0]["markers"] != runs[1]["markers"]:
            raise QualificationError("two PKMSR1 runs emitted different markers")
        if screenshots[0] != screenshots[1]:
            raise QualificationError("two PKMSR1 runs produced different frames")
        if handoffs[0] != handoffs[1]:
            raise QualificationError("two PKMSR1 runs produced different PBP1 bytes")

    controls = _negative_controls(runs[0]["markers"])
    observation = privilege_msr.validate_markers(runs[0]["markers"])
    command = qualify_native_pooleboot._normalized_command(profile)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_privilege_msr_policy_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_qemu64_read_only_non_promoting",
        "contract_id": privilege_msr.CONTRACT_ID,
        "selected_move_id": privilege_msr.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n7_exit_gate_satisfied": False,
        "phase_status": {"N7": "partial", "N7.3": "partial"},
        "inputs": privilege_msr.expected_inputs(ROOT),
        "build": {
            "kernel_entry": kernel_readiness,
            "default_pooleboot": default_build,
            "privilege_msr_policy_pooleboot": policy_build,
            "profile_count": 2,
            "all_profile_binaries_distinct": True,
            "default_stop_marker_present": True,
            "default_transfer_marker_absent": True,
            "source_audit": source_audit,
            "machine_code_audit_tool": llvm_tool,
            "linked_machine_code_audit": linked_audit,
        },
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "sha256": privilege_msr.sha256_bytes(media_one),
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
            "cpu_model": "qemu64",
            "acceleration": "tcg_single_thread",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": privilege_msr.sha256_bytes(native_pooleboot.canonical_json_bytes(command)),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "exact_pbp1_match": True,
            "runs": runs,
            "observation": {
                key: observation[key]
                for key in ("features", "linkage", "bases", "machine_check", "performance_monitoring", "result")
            },
        },
        "negative_controls": controls,
        "claims": privilege_msr.expected_claims(),
        "non_claims": contract["non_claims"],
        "summary": {
            "qemu_run_count": 2,
            "marker_count": privilege_msr.MARKER_COUNT,
            "negative_controls_passed": len(controls),
            "msr_read_count": observation["result"]["msr_reads"],
            "machine_check_bank_count": observation["machine_check"]["bank_count"],
            "machine_check_bank_reads": 0,
            "pmu_msr_reads": 0,
            "msr_writes": 0,
            "control_writes": 0,
            "signature_verifications": 0,
            "authority_grants": 0,
            "actions_authorized": 0,
            "firmware_calls_after_exit": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Implement and qualify transactional syscall entry/return only after ring-3 ABI, per-CPU stack, selector, and fault-containment contracts freeze.",
            "Bind exact target CPU product-specific MCA bank semantics and retained machine-check crash handling before any bank clear or handler activation.",
            "Define and qualify Intel architectural PMU and AMD PerfMonV2 ownership on profiles that actually enumerate those facilities.",
            "Extend privileged-MSR initialization and validation to every AP, CPU migration, suspend/resume, hotplug, and target hardware.",
            "Close applicable target errata and numeric microcode-floor stop-ship gaps before N7 exit.",
        ],
    }
    errors = privilege_msr.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-22")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report = make_readiness(args.toolchain_root.resolve(), args.qemu_root.resolve(), args.status_date, args.timeout)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        QualificationError,
        privilege_msr.KernelPrivilegeMsrPolicyError,
        native_tier0.Tier0Error,
    ) as error:
        parser.exit(1, f"PKMSR1 qualification failed: {error}\n")
    print(
        "PKMSR1 qualification passed: "
        f"runs={report['summary']['qemu_run_count']}; "
        f"negative={report['summary']['negative_controls_passed']}; "
        f"msr_reads={report['summary']['msr_read_count']}; "
        f"mca_banks={report['summary']['machine_check_bank_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
