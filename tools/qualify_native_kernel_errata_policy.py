#!/usr/bin/env python3
"""Qualify the non-promoting PKERR1 Ryzen target policy."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_kernel_errata_policy as pkerr1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / pkerr1.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
VECTOR_COUNT = 128
VECTOR_SEED = 0x504B_4552_5231_0121


class QualificationError(RuntimeError):
    """Raised when PKERR1 qualification fails closed."""


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(
            f"command failed ({completed.returncode}): {' '.join(command[:10])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = pkerr1.read_json(ROOT / "specs/native-toolchain-lock.json")
    channel = lock["toolchain"]["channel"]
    host = lock["host"]["triple"]
    installed = toolchain_root / "rustup" / "toolchains" / channel
    cargo = installed / "bin" / "cargo.exe"
    rustc = installed / "bin" / "rustc.exe"
    if not cargo.is_file() or not rustc.is_file():
        raise QualificationError("workspace-local Rust toolchain is missing")
    env = dict(os.environ)
    for key in (
        "CARGO_BUILD_RUSTC",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_HOME",
        "CARGO_INCREMENTAL",
        "CARGO_TARGET_DIR",
        "RUSTC",
        "RUSTC_BOOTSTRAP",
        "RUSTC_WRAPPER",
        "RUSTDOCFLAGS",
        "RUSTFLAGS",
        "RUSTUP_HOME",
        "RUSTUP_TOOLCHAIN",
    ):
        env.pop(key, None)
    system_root = Path(env.get("SystemRoot", r"C:\Windows"))
    env.update(
        {
            "CARGO_HOME": str(toolchain_root / "cargo"),
            "CARGO_INCREMENTAL": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": os.pathsep.join(
                [str(installed / "bin"), str(toolchain_root / "cargo" / "bin"), str(system_root / "System32")]
            ),
            "RUSTC": str(rustc),
            "RUSTUP_HOME": str(toolchain_root / "rustup"),
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
        }
    )
    remap = f"--remap-path-prefix={NATIVE_ROOT.resolve()}=/pooleos/native"
    for target in ("X86_64_UNKNOWN_UEFI", "X86_64_UNKNOWN_NONE"):
        env[f"CARGO_TARGET_{target}_RUSTFLAGS"] = " ".join(("-Cpanic=abort", remap))
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _cargo(cargo: Path, *arguments: str) -> list[str]:
    command, *remaining = arguments
    return [str(cargo), command, "--manifest-path", str(NATIVE_ROOT / "Cargo.toml"), *remaining]


def _build_validators(toolchain_root: Path, temporary_root: Path) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    test_output = _run(
        _cargo(
            cargo,
            "test",
            "--package",
            "poole-cpu-policy",
            "--lib",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "host-tests"),
            "--",
            "--test-threads=1",
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test_output)
    if match is None or int(match.group(1)) != 6:
        raise QualificationError("expected exactly six PKERR1 Rust host tests")
    _run(
        _cargo(cargo, "fmt", "--package", "poole-cpu-policy", "--", "--check"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        _cargo(
            cargo,
            "clippy",
            "--package",
            "poole-cpu-policy",
            "--all-targets",
            "--features",
            "host-probe",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "clippy"),
            "--",
            "-D",
            "warnings",
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    for target in ("x86_64-unknown-none", "x86_64-unknown-uefi"):
        _run(
            _cargo(
                cargo,
                "build",
                "--package",
                "poole-cpu-policy",
                "--lib",
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(temporary_root / f"target-{target}"),
            ),
            cwd=NATIVE_ROOT,
            env=env,
        )
    _run(
        _cargo(
            cargo,
            "build",
            "--package",
            "poole-cpu-policy",
            "--features",
            "host-probe",
            "--bin",
            "pkerr1-probe",
            "--target",
            HOST_TARGET,
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "probe"),
        ),
        cwd=NATIVE_ROOT,
        env=env,
    )
    probe = temporary_root / "probe" / HOST_TARGET / "debug" / "pkerr1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PKERR1 host probe is missing")
    return probe, {
        "status": "pass",
        "rustc": _run([str(rustc), "--version"], cwd=ROOT, env=env).strip(),
        "host_tests_passed": 6,
        "host_tests_total": 6,
        "rustfmt_packages": 1,
        "clippy_targets": 1,
        "no_std_targets": ["x86_64-unknown-none", "x86_64-unknown-uefi"],
    }


PROBE_RESULT = re.compile(
    r"^PKERR1 DECISION failures=0x([0-9A-F]{8}) satisfied=([01]) authority=([0-9]+) actions=([0-9]+) writes=([0-9]+)$"
)


def _probe(probe: Path, evidence: dict[str, Any]) -> dict[str, int | bool]:
    completed = subprocess.run(
        [str(probe), *pkerr1.probe_arguments(evidence)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    match = PROBE_RESULT.fullmatch(completed.stdout.strip())
    if completed.returncode != 0 or match is None:
        raise QualificationError(f"PKERR1 probe failed: {completed.stderr[-1000:]}")
    return {
        "failure_mask": int(match.group(1), 16),
        "policy_satisfied": bool(int(match.group(2))),
        "authority_grants": int(match.group(3)),
        "actions_authorized": int(match.group(4)),
        "state_writes": int(match.group(5)),
    }


def _assert_agreement(probe: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    python = pkerr1.evaluate(evidence)
    rust = _probe(probe, evidence)
    comparable = {
        key: python[key]
        for key in ("failure_mask", "policy_satisfied", "authority_grants", "actions_authorized", "state_writes")
    }
    if rust != comparable:
        raise QualificationError(f"PKERR1 Rust/Python mismatch: rust={rust} python={comparable}")
    return python


def _xorshift64(value: int) -> int:
    value ^= (value << 13) & ((1 << 64) - 1)
    value ^= value >> 7
    return (value ^ (value << 17)) & ((1 << 64) - 1)


def _cross_language_vectors(probe: Path) -> dict[str, Any]:
    state = VECTOR_SEED
    outcome = hashlib.sha256()
    failure_union = 0
    satisfied_count = 0
    for index in range(VECTOR_COUNT):
        evidence = pkerr1.synthetic_qualification_fixture()
        state = _xorshift64(state)
        selector = state % 15
        if selector == 0:
            evidence["cpuid_signature"] ^= 1
        elif selector == 1:
            evidence["feature_mask"] &= ~(1 << ((state >> 8) % 9))
        elif selector == 2:
            evidence["board_lineage"] = pkerr1.BOARD_UNKNOWN
        elif selector == 3:
            evidence["bios_number"] = 38
        elif selector == 4:
            evidence["bios_is_stable"] = False
        elif selector == 5:
            evidence["agesa"] = pkerr1.parse_agesa("1.2.0.3h")
        elif selector == 6:
            evidence["microcode_revision"] = 0
        elif selector == 7:
            evidence["all_processors_same_revision"] = False
        elif selector == 8:
            evidence["native_revision_evidence_trusted"] = False
        elif selector == 9:
            evidence["vendor_numeric_microcode_floor_available"] = False
        elif selector == 10:
            evidence["model44_revision_guide_available"] = False
        elif selector == 11:
            evidence["model44_revision_guide_applicable"] = False
        elif selector == 12:
            evidence["rdseed_policy"] = pkerr1.RDSEED_UNKNOWN
        elif selector == 13:
            evidence["direct_product_sources_only"] = False
        decision = _assert_agreement(probe, evidence)
        failure_union |= decision["failure_mask"]
        satisfied_count += int(decision["policy_satisfied"])
        outcome.update(index.to_bytes(4, "little"))
        outcome.update(decision["failure_mask"].to_bytes(4, "little"))
    if failure_union != sum(pkerr1.FAILURE_NAMES):
        raise QualificationError(f"PKERR1 vector failure coverage incomplete: 0x{failure_union:08X}")
    return {
        "status": "pass",
        "case_count": VECTOR_COUNT,
        "mismatch_count": 0,
        "satisfied_case_count": satisfied_count,
        "failure_bit_coverage": len(pkerr1.FAILURE_NAMES),
        "outcome_sha256": outcome.hexdigest().upper(),
    }


def _evaluator_control(
    probe: Path,
    control_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    decision = _assert_agreement(probe, evidence)
    if decision["policy_satisfied"] or decision["failure_mask"] == 0:
        raise QualificationError(f"PKERR1 hostile control did not reject: {control_id}")
    return {
        "id": control_id,
        "status": "pass",
        "expected": "deny",
        "failure_mask": f"0x{decision['failure_mask']:08X}",
        "failure_codes": decision["failure_codes"],
    }


def _contract_control(control_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    errors = pkerr1.contract_errors(contract)
    if not errors:
        raise QualificationError(f"PKERR1 contract control did not reject: {control_id}")
    return {"id": control_id, "status": "pass", "expected": "contract_rejected"}


def _negative_controls(probe: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    base = pkerr1.synthetic_qualification_fixture()
    candidates: dict[str, dict[str, Any]] = {}

    def changed(**updates: Any) -> dict[str, Any]:
        value = copy.deepcopy(base)
        value.update(updates)
        return value

    candidates["NEG-N7-PKERR-IDENTITY"] = changed(cpuid_signature=pkerr1.TARGET_CPUID_SIGNATURE ^ 1)
    candidates["NEG-N7-PKERR-FEATURE"] = changed(feature_mask=pkerr1.REQUIRED_FEATURES & ~pkerr1.FEATURE_SMAP)
    candidates["NEG-N7-PKERR-BOARD-UNKNOWN"] = changed(board_lineage=pkerr1.BOARD_UNKNOWN)
    candidates["NEG-N7-PKERR-BIOS-BELOW-FLOOR"] = changed(bios_number=38)
    candidates["NEG-N7-PKERR-BIOS-PRERELEASE"] = changed(bios_is_stable=False)
    candidates["NEG-N7-PKERR-AGESA-BELOW-SB7033"] = changed(
        agesa=pkerr1.parse_agesa("1.2.0.3b"), rdseed_policy=pkerr1.RDSEED_MASKED
    )
    candidates["NEG-N7-PKERR-AGESA-BELOW-SB7055"] = changed(agesa=pkerr1.parse_agesa("1.2.0.3h"))
    candidates["NEG-N7-PKERR-MICROCODE-ZERO"] = changed(microcode_revision=0)
    candidates["NEG-N7-PKERR-MICROCODE-MIXED"] = changed(all_processors_same_revision=False)
    candidates["NEG-N7-PKERR-MICROCODE-UNTRUSTED"] = changed(native_revision_evidence_trusted=False)
    candidates["NEG-N7-PKERR-MICROCODE-FLOOR-MISSING"] = changed(vendor_numeric_microcode_floor_available=False)
    candidates["NEG-N7-PKERR-ERRATA-GUIDE-MISSING"] = changed(model44_revision_guide_available=False)
    candidates["NEG-N7-PKERR-ERRATA-GUIDE-WRONG-RANGE"] = changed(model44_revision_guide_applicable=False)
    candidates["NEG-N7-PKERR-RDSEED-UNKNOWN"] = changed(rdseed_policy=pkerr1.RDSEED_UNKNOWN)
    candidates["NEG-N7-PKERR-RDSEED-PATCH-STALE"] = changed(
        agesa=pkerr1.parse_agesa("1.2.0.3h"), rdseed_policy=pkerr1.RDSEED_PATCHED_FIRMWARE
    )
    candidates["NEG-N7-PKERR-CROSS-SEGMENT-SOURCE"] = changed(direct_product_sources_only=False)
    controls = [
        _evaluator_control(probe, control_id, candidates[control_id])
        for control_id in pkerr1.NEGATIVE_CONTROL_IDS[:16]
    ]

    mutations: dict[str, dict[str, Any]] = {}
    value = copy.deepcopy(contract)
    value["source_register"][0]["captured_sha256"] = "00" * 32
    mutations["NEG-N7-PKERR-SOURCE-HASH"] = value
    value = copy.deepcopy(contract)
    value["source_register"][4]["target_applicable"] = True
    mutations["NEG-N7-PKERR-58251-APPLICABILITY"] = value
    value = copy.deepcopy(contract)
    value["current_observation"]["decision"] = "pass"
    mutations["NEG-N7-PKERR-CURRENT-OVERCLAIM"] = value
    value = copy.deepcopy(contract)
    value["microcode_policy"]["amd_published_client_numeric_floor"] = "0x0B404023"
    mutations["NEG-N7-PKERR-NUMERIC-FLOOR-INVENTED"] = value
    value = copy.deepcopy(contract)
    value["firmware_policy"]["lineages"][0]["minimum_stable_bios"] = "F32"
    mutations["NEG-N7-PKERR-FIRMWARE-FLOOR-LOWERED"] = value
    value = copy.deepcopy(contract)
    value["authority_gate"]["authority_grants"] = 1
    mutations["NEG-N7-PKERR-AUTHORITY-OVERCLAIM"] = value
    value = copy.deepcopy(contract)
    value["authority_gate"]["actions_authorized"] = 1
    mutations["NEG-N7-PKERR-ACTION-OVERCLAIM"] = value
    value = copy.deepcopy(contract)
    value["production_ready"] = True
    mutations["NEG-N7-PKERR-PRODUCTION-OVERCLAIM"] = value
    controls.extend(
        _contract_control(control_id, mutations[control_id])
        for control_id in pkerr1.NEGATIVE_CONTROL_IDS[16:]
    )
    if [item["id"] for item in controls] != list(pkerr1.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKERR1 hostile-control ordering changed")
    return controls


def _windows_registry_observation() -> dict[str, Any]:
    if os.name != "nt":
        return {"status": "unavailable_non_windows", "read_only": True, "record_count": 0}
    import winreg

    path = r"HARDWARE\DESCRIPTION\System\CentralProcessor"
    records: list[dict[str, Any]] = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as root:
        index = 0
        while True:
            try:
                child = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            with winreg.OpenKey(root, child, 0, winreg.KEY_READ) as key:
                identifier = str(winreg.QueryValueEx(key, "Identifier")[0])
                raw = bytes(winreg.QueryValueEx(key, "Update Revision")[0])
                if len(raw) < 4:
                    raise QualificationError("Windows microcode revision record is truncated")
                revision = int.from_bytes(raw[:4], "little")
                records.append(
                    {
                        "processor": int(child),
                        "identifier": identifier,
                        "revision_bytes_little_endian": raw[:4].hex().upper(),
                        "normalized_revision": f"0x{revision:08X}",
                    }
                )
    records.sort(key=lambda item: item["processor"])
    revisions = {item["normalized_revision"] for item in records}
    identifiers = {item["identifier"] for item in records}
    expected_identifier = "AMD64 Family 26 Model 68 Stepping 0"
    if (
        len(records) != 16
        or revisions != {"0x0B404023"}
        or identifiers != {expected_identifier}
    ):
        raise QualificationError("live Windows CPU registry observation differs from the frozen snapshot")
    return {
        "status": "pass_read_only_unprivileged_os_report",
        "read_only": True,
        "record_count": len(records),
        "unique_revision_count": len(revisions),
        "normalized_revision": "0x0B404023",
        "identifier": expected_identifier,
        "raw_registers_read": False,
        "msr_reads": 0,
        "privileged_reads": 0,
        "driver_loaded": False,
        "writes": 0,
        "records": records,
    }


def _source_audit() -> dict[str, Any]:
    source = (ROOT / "native/cpupolicy/src/lib.rs").read_text(encoding="utf-8").lower()
    forbidden = ("unsafe", "asm!", "wrmsr", "xsetbv", "write_volatile", "std::")
    hits = [token for token in forbidden if token in source]
    if hits:
        raise QualificationError(f"PKERR1 no_std policy source contains forbidden mechanism: {hits}")
    return {
        "status": "pass_pure_policy_no_cpu_or_firmware_io",
        "forbidden_tokens": list(forbidden),
        "forbidden_hits": [],
        "privileged_reads": 0,
        "cpu_or_firmware_writes": 0,
    }


def make_readiness(toolchain_root: Path, status_date: str) -> dict[str, Any]:
    contract = pkerr1.read_json(ROOT / pkerr1.CONTRACT_RELATIVE)
    errors = pkerr1.contract_errors(contract)
    if errors:
        raise QualificationError("; ".join(errors))
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkerr1-", dir=ROOT / "tmp") as temporary:
        probe, build = _build_validators(toolchain_root, Path(temporary))
        current = pkerr1.current_observation()
        current_decision = _assert_agreement(probe, current)
        synthetic_decision = _assert_agreement(probe, pkerr1.synthetic_qualification_fixture())
        vectors = _cross_language_vectors(probe)
        controls = _negative_controls(probe, contract)
    if current_decision["failure_mask"] != pkerr1.CURRENT_EXPECTED_FAILURES:
        raise QualificationError("PKERR1 current target did not fail for the exact frozen reasons")
    if not synthetic_decision["policy_satisfied"]:
        raise QualificationError("PKERR1 synthetic all-true policy fixture did not pass")
    current_record = {
        **current_decision,
        "failure_mask": f"0x{current_decision['failure_mask']:08X}",
        "decision": "deny",
    }
    synthetic_record = {
        **synthetic_decision,
        "failure_mask": f"0x{synthetic_decision['failure_mask']:08X}",
        "decision": "policy_satisfied_without_authority",
        "is_hardware_or_trust_evidence": False,
    }
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_errata_policy_readiness",
        "status_date": status_date,
        "status": "pass_policy_denies_current_target",
        "contract_id": pkerr1.CONTRACT_ID,
        "selected_move_id": pkerr1.SELECTED_MOVE_ID,
        "production_ready": False,
        "production_promotion_allowed": False,
        "n7_exit_gate_satisfied": False,
        "phase_status": {"N7": "partial", "N7.2": "partial", "N15.1": "partial"},
        "inputs": pkerr1.expected_inputs(),
        "build_qualification": build,
        "source_audit": _source_audit(),
        "windows_registry_observation": _windows_registry_observation(),
        "current_policy_decision": current_record,
        "synthetic_policy_decision": synthetic_record,
        "cross_language_vectors": vectors,
        "negative_controls": controls,
        "claims": pkerr1.expected_claims(),
        "summary": {
            "rust_host_tests_passed": 6,
            "rust_host_tests_total": 6,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "cross_language_vector_count": VECTOR_COUNT,
            "cross_language_mismatch_count": 0,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "current_failure_count": len(current_decision["failure_codes"]),
            "source_register_count": len(contract["source_register"]),
            "applicable_source_count": sum(item["target_applicable"] for item in contract["source_register"]),
            "privileged_read_count": 0,
            "cpu_or_firmware_write_count": 0,
            "authority_grant_count": 0,
            "actions_authorized_count": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Physically confirm the exact B650M GAMING PLUS WIFI board revision before selecting the F or FA firmware lineage.",
            "Acquire and hash an applicable AMD Family 1Ah Models 40h-4Fh revision guide or retain a reviewed vendor-response gap.",
            "Obtain a direct AMD numeric client microcode floor or ratify a replacement rule that does not invent one.",
            "Hash the exact stable board firmware image selected after board-revision confirmation and complete supersession review.",
            "Perform reviewed native per-processor read-only CPUID and MSR_PATCH_LEVEL observation on a separately safe target path.",
            "Prove all processors are homogeneous and bind the result to the exact firmware, reset state, and target identity.",
            "Integrate PKERR1 into PooleKernel before feature activation and application-processor online transitions.",
            "Implement and test RDSEED masking or the reviewed 64-bit-only fallback until remediated firmware is qualified.",
            "Complete the broader transient-execution, branch, return-stack, store-bypass, SMT, and control-flow matrix.",
            "Obtain a cryptographically retained GIGABYTE support-page or exact firmware metadata snapshot.",
            "Reproduce the policy and target evidence on a second clean builder and target-firmware boot.",
            "Complete N7 and every signed-media, physical-hardware, release, and production gate.",
        ],
        "non_claims": contract["non_claims"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--status-date", default="2026-07-21")
    args = parser.parse_args(argv)
    readiness = make_readiness(args.toolchain_root.resolve(), args.status_date)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    errors = pkerr1.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(errors))
    print(
        "PKERR1 qualification passed: "
        f"tests={readiness['summary']['rust_host_tests_passed']}; "
        f"vectors={readiness['summary']['cross_language_vector_count']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"current_failures={readiness['summary']['current_failure_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
