#!/usr/bin/env python3
"""Qualify PMCU1 parsing, selection, apply gating, and post-apply verification."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_microcode as pmcu1  # noqa: E402


NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / pmcu1.READINESS_RELATIVE
HOST_TARGET = "x86_64-pc-windows-msvc"
PARSER_DIFFERENTIAL_CASES = 16_384
SELECTION_DIFFERENTIAL_CASES = 16_384
POST_APPLY_DIFFERENTIAL_CASES = 8_192
PARSER_SEED = 0x504D_4355_3101
SELECTION_SEED = 0x504D_4355_3102
POST_APPLY_SEED = 0x504D_4355_3103


class QualificationError(RuntimeError):
    """Raised when PMCU1 qualification fails closed."""


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    input_text: str | None = None,
) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.replace("\r\n", "\n")
    if completed.returncode != 0:
        raise QualificationError(
            f"command failed ({completed.returncode}): {' '.join(command[:8])}\n"
            + "\n".join(output.splitlines()[-80:])
        )
    return output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = pmcu1.read_json(ROOT / "specs/native-toolchain-lock.json")
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
                [
                    str(installed / "bin"),
                    str(toolchain_root / "cargo" / "bin"),
                    str(system_root / "System32"),
                ]
            ),
            "RUSTC": str(rustc),
            "RUSTUP_HOME": str(toolchain_root / "rustup"),
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
        }
    )
    remap = f"--remap-path-prefix={NATIVE_ROOT.resolve()}=/pooleos/native"
    for target in ("X86_64_UNKNOWN_UEFI", "X86_64_UNKNOWN_NONE"):
        env[f"CARGO_TARGET_{target}_RUSTFLAGS"] = " ".join(
            (
                "-Cpanic=abort",
                '--cfg=sha2_backend="soft"',
                '--cfg=sha2_backend_soft="compact"',
                remap,
            )
        )
    version = _run([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _cargo(cargo: Path, *arguments: str) -> list[str]:
    command, *remaining = arguments
    return [
        str(cargo),
        command,
        "--manifest-path",
        str(NATIVE_ROOT / "Cargo.toml"),
        *remaining,
    ]


def _build_validators(
    toolchain_root: Path, temporary_root: Path
) -> tuple[Path, dict[str, Any]]:
    cargo, rustc, env = _toolchain(toolchain_root)
    test_output = _run(
        _cargo(
            cargo,
            "test",
            "--package",
            "poole-microcode",
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
    if match is None or int(match.group(1)) != 4:
        raise QualificationError("expected exactly four PMCU1 Rust host tests")
    _run(
        _cargo(cargo, "fmt", "--package", "poole-microcode", "--", "--check"),
        cwd=NATIVE_ROOT,
        env=env,
    )
    _run(
        _cargo(
            cargo,
            "clippy",
            "--package",
            "poole-microcode",
            "--lib",
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
                "poole-microcode",
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
            "poole-microcode",
            "--features",
            "host-probe",
            "--bin",
            "pmcu1-probe",
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
    probe = temporary_root / "probe" / HOST_TARGET / "debug" / "pmcu1-probe.exe"
    if not probe.is_file():
        raise QualificationError("PMCU1 host probe is missing")
    return probe, {
        "status": "pass",
        "rustc": _run([str(rustc), "--version"], cwd=ROOT, env=env).strip(),
        "host_tests": 4,
        "rustfmt_packages": 1,
        "clippy_targets": 1,
        "no_std_targets": ["x86_64-unknown-none", "x86_64-unknown-uefi"],
    }


def _probe_lines(probe: Path, requests: list[str]) -> list[str]:
    completed = subprocess.run(
        [str(probe)],
        input="\n".join(requests) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise QualificationError(f"PMCU1 probe failed: {completed.stderr[-2000:]}")
    lines = completed.stdout.replace("\r\n", "\n").splitlines()
    if len(lines) != len(requests):
        raise QualificationError(
            f"PMCU1 probe response count mismatch: expected={len(requests)} observed={len(lines)}"
        )
    return lines


def _parse_result(data: bytes) -> str:
    try:
        bundle = pmcu1.parse(data)
    except pmcu1.MicrocodeError as error:
        return f"ERR:{error.code}"
    return (
        f"OK;version=1.0;bytes={len(data)};patches={len(bundle.patches)};"
        f"floor={bundle.security_revision_floor:X};known={bundle.known_good_revision:X};"
        f"preferred={bundle.preferred_revision:X};body={bundle.body_sha256}"
    )


def _selection_result(
    data: bytes,
    cpuid_signature: int,
    platform_id: int,
    current_revision: int,
    rollback_floor: int,
    boot_mode: int,
    revoked: Iterable[int],
) -> str:
    try:
        bundle = pmcu1.parse(data)
        selection = pmcu1.select_patch(
            bundle,
            cpuid_signature=cpuid_signature,
            platform_id=platform_id,
            current_revision=current_revision,
            authenticated_rollback_floor=rollback_floor,
            boot_mode=boot_mode,
            revoked_revisions=revoked,
        )
    except pmcu1.MicrocodeError as error:
        return f"ERR:{error.code}"
    labels = {
        pmcu1.DECISION_APPLY: "apply",
        pmcu1.DECISION_SKIP_CURRENT: "skip_current",
        pmcu1.DECISION_RESET_FOR_KNOWN_GOOD: "reset_for_known_good",
    }
    patch_id = str(selection.patch.patch_id) if selection.patch else "-"
    revision = f"{selection.patch.revision:X}" if selection.patch else "-"
    return (
        f"OK;decision={labels[selection.decision]};id={patch_id};revision={revision};"
        f"current={selection.current_revision:X};floor={selection.required_floor:X}"
    )


def _request_selection(
    data: bytes,
    cpuid_signature: int,
    platform_id: int,
    current_revision: int,
    rollback_floor: int,
    boot_mode: int,
    revoked: Iterable[int],
) -> str:
    revoked_text = ",".join(f"{value:X}" for value in revoked) or "-"
    return (
        f"S:{data.hex().upper()}:{cpuid_signature:X}:{platform_id:X}:"
        f"{current_revision:X}:{rollback_floor:X}:{boot_mode:X}:{revoked_text}"
    )


def _verify_result(
    data: bytes,
    current: int,
    after: tuple[int, ...],
    feature_policy: bool,
    mitigation_policy: bool,
    receipt: bool,
    quarantine: bool,
    scheduling: bool,
) -> str:
    try:
        bundle = pmcu1.parse(data)
        selection = pmcu1.select_patch(
            bundle,
            cpuid_signature=bundle.target_cpuid_signature,
            platform_id=bundle.target_platform_id,
            current_revision=current,
            authenticated_rollback_floor=bundle.security_revision_floor,
            boot_mode=pmcu1.MODE_NORMAL,
        )
        if selection.patch is None:
            raise pmcu1.MicrocodeError("pmcu_verify_decision")
        observation = pmcu1.PostApplyObservation(
            selection.patch.patch_id,
            selection.patch.revision,
            (current,) * len(after),
            after,
            bundle.target_cpuid_signature,
            bundle.target_cpuid_signature,
            "01" * 32,
            "02" * 32,
            feature_policy,
            mitigation_policy,
            receipt,
            quarantine,
            scheduling,
        )
        pmcu1.verify_post_apply(bundle, selection, observation)
    except pmcu1.MicrocodeError as error:
        return f"ERR:{error.code}"
    return "OK:verified"


def _request_verify(
    data: bytes,
    current: int,
    after: tuple[int, ...],
    feature_policy: bool,
    mitigation_policy: bool,
    receipt: bool,
    quarantine: bool,
    scheduling: bool,
) -> str:
    after_text = ",".join(f"{value:X}" for value in after)
    bits = tuple("1" if value else "0" for value in (feature_policy, mitigation_policy, receipt, quarantine, scheduling))
    return f"V:{data.hex().upper()}:{current:X}:{after_text}:{':'.join(bits)}:-"


def _qualify_golden(probe: Path, golden: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[str] = []
    expected: list[str] = []
    for vector in golden["vectors"]:
        data = bytes.fromhex(vector["bundle_hex"])
        requests.append(f"P:{data.hex().upper()}")
        expected.append(_parse_result(data))
        for sample in vector["selection_samples"]:
            revoked = sample["revoked_revisions"]
            requests.append(
                _request_selection(
                    data,
                    sample["cpuid_signature"],
                    sample["platform_id"],
                    sample["current_revision"],
                    sample["authenticated_rollback_floor"],
                    sample["boot_mode"],
                    revoked,
                )
            )
            expected.append(
                _selection_result(
                    data,
                    sample["cpuid_signature"],
                    sample["platform_id"],
                    sample["current_revision"],
                    sample["authenticated_rollback_floor"],
                    sample["boot_mode"],
                    revoked,
                )
            )
    observed = _probe_lines(probe, requests)
    if observed != expected:
        index = next(
            index
            for index, pair in enumerate(zip(expected, observed, strict=True))
            if pair[0] != pair[1]
        )
        raise QualificationError(
            f"PMCU1 golden mismatch {index}: Python={expected[index]} Rust={observed[index]}"
        )
    return [
        {
            "id": vector["id"],
            "bundle_sha256": vector["bundle_sha256"],
            "selection_sample_count": len(vector["selection_samples"]),
            "python_result": "pass",
            "rust_result": "pass",
            "status": "pass",
        }
        for vector in golden["vectors"]
    ]


def _repair_header_and_body(data: bytearray) -> None:
    if len(data) < pmcu1.HEADER_BYTES:
        return
    data[288:320] = hashlib.sha256(data[pmcu1.HEADER_BYTES :]).digest()
    data[320:352] = bytes(32)
    data[320:352] = hashlib.sha256(data[: pmcu1.HEADER_BYTES]).digest()


def _mutated_bundle(rng: random.Random, case: int) -> bytes:
    templates = (pmcu1.canonical_bundle(), pmcu1.minimal_bundle(), pmcu1.boundary_bundle())
    output = bytearray(templates[case % len(templates)])
    if case % 257 == 0:
        return bytes(output)
    operation = rng.randrange(9)
    if operation == 0:
        return bytes(output[: rng.randrange(len(output))])
    if operation == 1:
        output.extend(rng.randbytes(1 + rng.randrange(4)))
        return bytes(output)
    if operation == 2:
        return rng.randbytes(rng.randrange(pmcu1.HEADER_BYTES + 64))
    positions = [rng.randrange(len(output))]
    for _ in range(rng.randrange(3)):
        positions.append(rng.randrange(len(output)))
    for position in positions:
        output[position] ^= 1 << rng.randrange(8)
    if operation >= 6:
        _repair_header_and_body(output)
    return bytes(output)


def _qualify_parser_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(PARSER_SEED)
    requests: list[str] = []
    expected: list[str] = []
    accepted = 0
    rejected = 0
    for case in range(PARSER_DIFFERENTIAL_CASES):
        data = _mutated_bundle(rng, case)
        result = _parse_result(data)
        requests.append(f"P:{data.hex().upper()}")
        expected.append(result)
        accepted += int(result.startswith("OK;"))
        rejected += int(result.startswith("ERR:"))
    observed = _probe_lines(probe, requests)
    for index, (python_result, rust_result) in enumerate(zip(expected, observed, strict=True)):
        if python_result != rust_result:
            raise QualificationError(
                f"PMCU1 parser differential mismatch {index}: Python={python_result} Rust={rust_result}"
            )
    if accepted == 0 or rejected == 0:
        raise QualificationError("PMCU1 parser campaign lacks acceptance or rejection coverage")
    return {
        "campaign_id": "PMCU1-PARSER-DIFF-1",
        "seed": f"0x{PARSER_SEED:X}",
        "case_count": len(requests),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "digest_repaired_deep_mutations": True,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def _qualify_selection_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(SELECTION_SEED)
    bundles = tuple(pmcu1.parse(data) for data in (pmcu1.canonical_bundle(), pmcu1.minimal_bundle(), pmcu1.boundary_bundle()))
    requests: list[str] = []
    expected: list[str] = []
    apply_count = skip_count = reset_count = reject_count = 0
    for case in range(SELECTION_DIFFERENTIAL_CASES):
        bundle = bundles[case % len(bundles)]
        cpuid = bundle.target_cpuid_signature
        platform = bundle.target_platform_id
        floor = bundle.security_revision_floor
        mode = pmcu1.MODE_NORMAL if rng.randrange(4) else pmcu1.MODE_PREVIOUS_KNOWN_GOOD
        current = max(0, bundle.security_revision_floor - rng.randrange(0, 32))
        if rng.randrange(3) == 0:
            current = rng.choice(bundle.patches).revision
        if rng.randrange(10) == 0:
            current = bundle.preferred_revision + rng.randrange(1, 8)
        revoked: tuple[int, ...] = ()
        mutation = rng.randrange(12)
        if mutation == 0:
            cpuid ^= 1
        elif mutation == 1:
            mode = 0
        elif mutation == 2:
            floor = bundle.preferred_revision + 1
        elif mutation == 3:
            revoked = (bundle.preferred_revision,)
        result = _selection_result(bundle.raw, cpuid, platform, current, floor, mode, revoked)
        requests.append(_request_selection(bundle.raw, cpuid, platform, current, floor, mode, revoked))
        expected.append(result)
        apply_count += int("decision=apply" in result)
        skip_count += int("decision=skip_current" in result)
        reset_count += int("decision=reset_for_known_good" in result)
        reject_count += int(result.startswith("ERR:"))
    observed = _probe_lines(probe, requests)
    for index, (python_result, rust_result) in enumerate(zip(expected, observed, strict=True)):
        if python_result != rust_result:
            raise QualificationError(
                f"PMCU1 selection differential mismatch {index}: Python={python_result} Rust={rust_result}"
            )
    if min(apply_count, skip_count, reset_count, reject_count) == 0:
        raise QualificationError("PMCU1 selection campaign lacks a decision class")
    return {
        "campaign_id": "PMCU1-SELECTION-DIFF-1",
        "seed": f"0x{SELECTION_SEED:X}",
        "case_count": len(requests),
        "apply_count": apply_count,
        "skip_count": skip_count,
        "reset_required_count": reset_count,
        "rejected_count": reject_count,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


def _qualify_post_apply_differential(probe: Path) -> dict[str, Any]:
    rng = random.Random(POST_APPLY_SEED)
    bundle = pmcu1.parse(pmcu1.canonical_bundle())
    requests: list[str] = []
    expected: list[str] = []
    accepted = rejected = mixed = 0
    current = pmcu1.SYNTHETIC_REVISION_BASE + 0x10
    for case in range(POST_APPLY_DIFFERENTIAL_CASES):
        processor_count = 1 + rng.randrange(8)
        after = (bundle.preferred_revision,) * processor_count
        feature = mitigation = receipt = True
        quarantine = scheduling = False
        mutation = rng.randrange(10)
        if mutation == 0 and processor_count > 1:
            after = after[:-1] + (bundle.known_good_revision,)
            mixed += 1
        elif mutation == 1:
            after = (current,) * processor_count
        elif mutation == 2:
            feature = False
        elif mutation == 3:
            mitigation = False
        elif mutation == 4:
            receipt = False
        elif mutation == 5:
            scheduling = True
        elif mutation == 6 and processor_count > 1:
            after = after[:-1] + (bundle.known_good_revision,)
            quarantine = True
            mixed += 1
        result = _verify_result(bundle.raw, current, after, feature, mitigation, receipt, quarantine, scheduling)
        requests.append(_request_verify(bundle.raw, current, after, feature, mitigation, receipt, quarantine, scheduling))
        expected.append(result)
        accepted += int(result == "OK:verified")
        rejected += int(result.startswith("ERR:"))
    observed = _probe_lines(probe, requests)
    for index, (python_result, rust_result) in enumerate(zip(expected, observed, strict=True)):
        if python_result != rust_result:
            raise QualificationError(
                f"PMCU1 post-apply differential mismatch {index}: Python={python_result} Rust={rust_result}"
            )
    if accepted == 0 or rejected == 0 or mixed == 0:
        raise QualificationError("PMCU1 post-apply campaign lacks required coverage")
    return {
        "campaign_id": "PMCU1-POST-APPLY-DIFF-1",
        "seed": f"0x{POST_APPLY_SEED:X}",
        "case_count": len(requests),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "mixed_revision_case_count": mixed,
        "mismatch_count": 0,
        "corpus_published": False,
        "status": "pass",
    }


ACTIVATION_MODES = (
    "development",
    "outer-signature",
    "inner-signature",
    "manifest-signature",
    "vendor-signature",
    "vendor-container",
    "vendor-source",
    "redistribution",
    "revocation-state",
    "hardware-evidence",
    "cpuid-observation",
    "revision-observation",
    "role",
    "version",
    "payload-digest",
    "file-digest",
    "vendor-id",
    "cpuid",
    "platform",
    "processor-count",
    "mixed-before",
    "rollback-floor",
    "boot-mode",
    "stage",
    "feature-timing",
    "schedule-timing",
    "processor-inventory",
    "quiescence",
    "payload-capacity",
    "patch-capacity",
    "processor-capacity",
    "receipt-capacity",
    "apply-authority",
    "firmware-mutation",
    "physical-media",
    "implemented",
)


def _activation_expected(mode: str, data: bytes) -> str:
    bundle = pmcu1.parse(data)
    context = pmcu1.synthetic_qualified_apply_context(bundle)
    mutations: dict[str, dict[str, Any]] = {
        "outer-signature": {"outer_signature_verified": False},
        "inner-signature": {"inner_signature_verified": False},
        "manifest-signature": {"manifest_signature_verified": False},
        "vendor-signature": {"vendor_signature_verified": False},
        "vendor-container": {"vendor_container_validated": False},
        "vendor-source": {"vendor_source_trusted": False},
        "redistribution": {"redistribution_authorized": False},
        "revocation-state": {"revocation_state_authenticated": False},
        "hardware-evidence": {"target_hardware_evidence_verified": False},
        "cpuid-observation": {"cpuid_observation_trusted": False},
        "revision-observation": {"revision_observation_trusted": False},
        "role": {"outer_role": 4},
        "version": {"outer_version": 2},
        "payload-digest": {"outer_payload_sha256": "00" * 32},
        "file-digest": {"expected_outer_file_sha256": "11" * 32},
        "vendor-id": {"vendor_id": b"X" + bundle.vendor_id[1:]},
        "cpuid": {"cpuid_signature": bundle.target_cpuid_signature ^ 1},
        "platform": {"platform_id": 1},
        "processor-count": {"current_revisions": ()},
        "mixed-before": {"current_revisions": (pmcu1.SYNTHETIC_REVISION_BASE + 0x10, pmcu1.SYNTHETIC_REVISION_BASE + 0x11), "processor_capacity": 2, "receipt_capacity": 2},
        "rollback-floor": {"authenticated_rollback_floor": 0},
        "boot-mode": {"boot_mode": 0},
        "stage": {"executor_stage": 0},
        "feature-timing": {"before_affected_features": False},
        "schedule-timing": {"before_user_scheduling": False},
        "processor-inventory": {"processor_inventory_complete": False},
        "quiescence": {"processor_set_quiesced": False},
        "payload-capacity": {"payload_capacity": 0},
        "patch-capacity": {"patch_capacity": 0},
        "processor-capacity": {"processor_capacity": 0},
        "receipt-capacity": {"receipt_capacity": 0},
        "apply-authority": {"apply_authority_granted": False},
        "firmware-mutation": {"firmware_mutation_requested": True},
        "physical-media": {"physical_media_write_requested": True},
        "implemented": {"qualification_only": False},
    }
    if mode == "development":
        context = pmcu1.development_apply_context(bundle)
    elif mode != "qualified":
        context = dataclasses.replace(context, **mutations[mode])
    try:
        selection = pmcu1.authorize_apply_plan(bundle, context)
    except pmcu1.MicrocodeError as error:
        return f"ERR:{error.code}"
    return _selection_result(
        bundle.raw,
        context.cpuid_signature,
        context.platform_id,
        context.current_revisions[0],
        context.authenticated_rollback_floor,
        context.boot_mode,
        (),
    ) if selection else "ERR:transport"


def _qualify_negative_controls(probe: Path) -> list[dict[str, Any]]:
    canonical = pmcu1.canonical_bundle()
    controls: list[tuple[str, str, str]] = []
    requests: list[str] = []
    rng = random.Random(0x504D_4355_31FF)
    attempts = 0
    while len(controls) < 128:
        attempts += 1
        if attempts > 4096:
            raise QualificationError("could not construct 128 rejecting PMCU1 parser controls")
        mutated = bytearray(canonical)
        position = rng.randrange(len(mutated))
        mutated[position] ^= 1 << rng.randrange(8)
        if attempts % 3 == 0:
            _repair_header_and_body(mutated)
        data = bytes(mutated)
        expected = _parse_result(data)
        if not expected.startswith("ERR:"):
            continue
        requests.append(f"P:{data.hex().upper()}")
        controls.append((f"NEG-PMCU1-PARSER-{len(controls)+1:03d}", "parser", expected))
    for index, mode in enumerate(ACTIVATION_MODES, start=1):
        expected = _activation_expected(mode, canonical)
        if not expected.startswith("ERR:"):
            raise QualificationError(f"negative activation mode {mode} remained valid")
        requests.append(f"A:{mode}:{canonical.hex().upper()}")
        controls.append((f"NEG-PMCU1-ACTIVATION-{index:03d}", "activation", expected))
    selection_controls = (
        ("cpuid", pmcu1.TARGET_CPUID_SIGNATURE ^ 1, 0, pmcu1.SYNTHETIC_REVISION_BASE, pmcu1.CANONICAL_SECURITY_FLOOR, pmcu1.MODE_NORMAL, ()),
        ("mode", pmcu1.TARGET_CPUID_SIGNATURE, 0, pmcu1.SYNTHETIC_REVISION_BASE, pmcu1.CANONICAL_SECURITY_FLOOR, 0, ()),
        ("rollback", pmcu1.TARGET_CPUID_SIGNATURE, 0, pmcu1.SYNTHETIC_REVISION_BASE, pmcu1.CANONICAL_PREFERRED_REVISION + 1, pmcu1.MODE_NORMAL, ()),
        ("no-eligible", pmcu1.TARGET_CPUID_SIGNATURE, 0, pmcu1.SYNTHETIC_REVISION_BASE, pmcu1.CANONICAL_SECURITY_FLOOR, pmcu1.MODE_NORMAL, (pmcu1.CANONICAL_KNOWN_GOOD_REVISION, pmcu1.CANONICAL_PREFERRED_REVISION)),
    )
    for index, (_, cpuid, platform, current, floor, mode, revoked) in enumerate(selection_controls, start=1):
        expected = _selection_result(canonical, cpuid, platform, current, floor, mode, revoked)
        if not expected.startswith("ERR:"):
            raise QualificationError("negative selection control remained valid")
        requests.append(_request_selection(canonical, cpuid, platform, current, floor, mode, revoked))
        controls.append((f"NEG-PMCU1-SELECTION-{index:03d}", "selection", expected))
    verify_controls = (
        ((pmcu1.CANONICAL_KNOWN_GOOD_REVISION,), True, True, True, False, False),
        ((pmcu1.CANONICAL_PREFERRED_REVISION, pmcu1.CANONICAL_KNOWN_GOOD_REVISION), True, True, True, False, False),
        ((pmcu1.CANONICAL_PREFERRED_REVISION,), False, True, True, False, False),
        ((pmcu1.CANONICAL_PREFERRED_REVISION,), True, False, True, False, False),
        ((pmcu1.CANONICAL_PREFERRED_REVISION,), True, True, False, False, False),
        ((pmcu1.CANONICAL_PREFERRED_REVISION,), True, True, True, False, True),
    )
    current = pmcu1.SYNTHETIC_REVISION_BASE + 0x10
    for index, (after, feature, mitigation, receipt, quarantine, scheduling) in enumerate(verify_controls, start=1):
        expected = _verify_result(canonical, current, after, feature, mitigation, receipt, quarantine, scheduling)
        if not expected.startswith("ERR:"):
            raise QualificationError("negative post-apply control remained valid")
        requests.append(_request_verify(canonical, current, after, feature, mitigation, receipt, quarantine, scheduling))
        controls.append((f"NEG-PMCU1-VERIFY-{index:03d}", "post_apply", expected))
    observed = _probe_lines(probe, requests)
    output: list[dict[str, Any]] = []
    for index, ((control_id, surface, expected), result) in enumerate(zip(controls, observed, strict=True)):
        if result != expected:
            raise QualificationError(
                f"{control_id} mismatch {index}: expected={expected} observed={result}"
            )
        output.append(
            {
                "id": control_id,
                "surface": surface,
                "expected": expected,
                "observed": result,
                "status": "pass",
            }
        )
    return output


def expected_readiness_claims() -> dict[str, bool]:
    return {
        "format_frozen": True,
        "python_oracle_implemented": True,
        "no_std_parser_implemented": True,
        "bounded_selection_implemented": True,
        "post_apply_verification_model_implemented": True,
        "development_activation_denied": True,
        "vendor_container_parser_implemented": False,
        "vendor_payload_included": False,
        "privileged_revision_observed": False,
        "microcode_applied": False,
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }


def make_readiness(toolchain_root: Path) -> dict[str, Any]:
    contract = pmcu1.read_json(ROOT / pmcu1.CONTRACT_RELATIVE)
    golden = pmcu1.read_json(ROOT / pmcu1.GOLDEN_RELATIVE)
    errors = pmcu1.contract_errors(contract) + pmcu1.golden_errors(golden)
    if errors:
        raise QualificationError("; ".join(str(error) for error in errors))
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pmcu1-", dir=ROOT / "tmp") as temporary:
        probe, validators = _build_validators(toolchain_root, Path(temporary))
        golden_results = _qualify_golden(probe, golden)
        controls = _qualify_negative_controls(probe)
        parser_diff = _qualify_parser_differential(probe)
        selection_diff = _qualify_selection_differential(probe)
        post_diff = _qualify_post_apply_differential(probe)
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_microcode_readiness",
        "status_date": "2026-07-18",
        "status": "pass",
        "contract_id": pmcu1.CONTRACT_ID,
        "selected_move_id": "N5-MICROCODE-SEMANTICS-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.6": "partial", "N7.2": "partial", "N24.4": "partial"},
        "bindings": {
            "contract": pmcu1._binding_record(ROOT / pmcu1.CONTRACT_RELATIVE),
            "contract_schema": pmcu1._binding_record(ROOT / pmcu1.CONTRACT_SCHEMA_RELATIVE),
            "golden_vectors": pmcu1._binding_record(ROOT / pmcu1.GOLDEN_RELATIVE),
            "golden_schema": pmcu1._binding_record(ROOT / pmcu1.GOLDEN_SCHEMA_RELATIVE),
            "readiness_schema": pmcu1._binding_record(ROOT / pmcu1.READINESS_SCHEMA_RELATIVE),
            "implementation_inputs": pmcu1.implementation_bindings(),
        },
        "validator_qualification": validators,
        "golden_vectors": golden_results,
        "negative_controls": controls,
        "parser_differential": parser_diff,
        "selection_differential": selection_diff,
        "post_apply_differential": post_diff,
        "activation_qualification": {
            "status": "pass",
            "synthetic_all_true_result": "apply_plan_only",
            "synthetic_all_true_context_is_trust_evidence": False,
            "current_unsigned_development_activation_allowed": False,
            "individual_rejecting_context_count": len(ACTIVATION_MODES),
            "privileged_apply_function_present": False,
        },
        "claims": expected_readiness_claims(),
        "summary": {
            "rust_host_tests_passed": 4,
            "rust_host_tests_total": 4,
            "no_std_target_builds_passed": 2,
            "no_std_target_builds_total": 2,
            "golden_vectors_matched": len(golden_results),
            "golden_vectors_total": len(golden_results),
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "parser_differential_cases": parser_diff["case_count"],
            "selection_differential_cases": selection_diff["case_count"],
            "post_apply_differential_cases": post_diff["case_count"],
            "differential_mismatches": 0,
            "synthetic_payload_count": sum(len(pmcu1.parse(bytes.fromhex(item["bundle_hex"])).patches) for item in golden["vectors"]),
            "production_vendor_payload_count": 0,
            "production_claim_count": 0,
        },
        "open_items": [
            "Ratify or replace PMCU1 before declaring a stable microcode ABI.",
            "Obtain exact AMD Family 1Ah Model 44h vendor update guidance and redistribution terms.",
            "Acquire approved vendor microcode through a trusted source or user-supplied intake path.",
            "Implement and independently review the exact AMD vendor-container validator.",
            "Capture the current revision through a separately approved privileged native observation.",
            "Bind real security floors, errata, revocation state, firmware revision, and reset behavior.",
            "Sign PBART1 role 5, PMCU1, its manifest, and policy under approved roots.",
            "Implement PMCU1 parsing and fail-closed staging inside PooleBoot.",
            "Implement the minimal PooleKernel BSP/AP apply mechanism and per-CPU rendezvous.",
            "Prove apply timing before affected features and before application processors enter scheduling.",
            "Prove per-CPU post-apply revision, CPUID, mitigation, mixed-state, and retained-receipt behavior.",
            "Qualify reset-based previous-known-good recovery without in-session downgrade.",
            "Reproduce qualification on an independent builder and target firmware.",
            "Complete physical-hardware, signed-media, production ISO, and N5-N39 exit gates.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    readiness = make_readiness(args.toolchain_root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(readiness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    errors = pmcu1.readiness_errors(readiness)
    if errors:
        raise QualificationError("; ".join(str(error) for error in errors))
    print(
        f"PMCU1 qualification passed: tests={readiness['summary']['rust_host_tests_passed']}; "
        f"negative={readiness['summary']['negative_controls_passed']}; "
        f"parser_differential={readiness['summary']['parser_differential_cases']}; "
        f"selection_differential={readiness['summary']['selection_differential_cases']}; "
        f"post_apply_differential={readiness['summary']['post_apply_differential_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
