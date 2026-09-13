#!/usr/bin/env python3
"""Qualify the host-executed PKRECLAIM1 core without claiming live integration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import qualify_native_kernel_entry as entry  # noqa: E402

SOURCES = (
    "native/kernel/src/reclamation.rs",
    "native/kernel/src/reclamation/ap_resources.rs",
    "native/kernel/src/reclamation/execution.rs",
    "native/kernel/src/reclamation/task_lifetimes.rs",
    "native/kernel/src/lib.rs",
    "native/kernel/src/atomics.rs",
    "native/kernel/src/locks.rs",
    "native/kernel/tests/reclamation_core.rs",
    "native/kernel/tests/task_lifetimes.rs",
    "native/kernel/src/scheduler_smp.rs",
    "native/kernel/src/virtual_memory.rs",
    "native/kernel/src/active_virtual_memory.rs",
    "native/kernel/src/physical_memory.rs",
    "native/kernel/src/physical_memory/retention.rs",
    "native/kernel/src/physical_memory/tests/retention.rs",
    "native/kernel/src/physical_memory/tests/ap_resources.rs",
    "tests/test_native_reclamation_core.py",
    "native/kernel/src/main.rs",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-entry-contract.schema.json",
    "native/kmap/src/lib.rs",
    "native/handoff/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/Cargo.lock",
    "specs/native-toolchain-lock.json",
    "tools/qualify_native_reclamation_core.py",
    "tools/qualify_native_kernel_entry.py",
    "runtime/native_kernel_image.py",
)
REPORT = ROOT / "runs/native-kernel-reclamation-core-readiness.json"
TEST_COUNT = 19
LIFETIME_TEST_COUNT = 40
EXECUTION_TESTS = (
    "dispatch_execution_holds_actual_stack_until_architectural_release",
    "dispatch_execution_loss_never_fabricates_quiescence",
    "dispatch_execution_pin_exhaustion_precedes_queue_mutation",
    "dispatch_execution_invalid_admission_does_not_consume_pins",
    "dispatch_execution_cpu_holds_retire_independently",
    "dispatch_execution_reuse_rejects_prior_generation_ack",
)
STACK_TESTS = (
    "task_execution_stack_cannot_be_freed_through_a_copied_handle",
    "stack_retention_survives_task_reclaim_until_full_scrubbed_release",
    "invalid_stack_layout_returns_every_input_without_retaining_tables",
    "stale_stack_handle_cannot_retain_a_replacement_allocation",
    "late_stack_retention_conflict_leaves_all_tables_and_frames_unretained",
    "failed_stack_scrub_keeps_owner_and_allocation_for_retry",
    "stack_release_on_wrong_manager_is_rejected_before_physical_access",
    "losing_stack_owner_never_silently_releases_pages",
    "overlapping_stacks_from_distinct_manager_namespaces_cannot_share_scheduler",
    "full_scrub_receipt_ledger_retains_the_next_stack_without_writes",
)
KERNEL_SHA256 = "563ED1976CAB4DA773BAE9BCE49F370242C893760E7C221239C1B31F44D969CA"
STAGES = (
    "format", "host-build-debug", "test-build-debug", "tests-debug",
    "lifetime-build-debug", "lifetime-tests-debug",
    "host-build-release", "test-build-release", "tests-release",
    "lifetime-build-release", "lifetime-tests-release", "kernel-regressions-release", "borrow-doctests",
    "kernel-regressions", "host-clippy", "freestanding-clippy", "linked-kernel-build",
)


def bind_sources(root: Path = ROOT) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest().upper() for name in SOURCES}


def require_test_result(output: str, count: int) -> None:
    results = re.findall(r"^test result: (.*)$", output.replace("\r\n", "\n"), re.MULTILINE)
    expected = rf"ok\. {count} passed; 0 failed; 0 ignored; 0 measured; 0 filtered out(?:; finished in [0-9.]+s)?"
    if len(results) != 1 or re.fullmatch(expected, results[0]) is None:
        raise ValueError(f"expected exactly {count} passing tests, no failures/skips/filters")


def require_named_test_result(output: str, prefix: str, count: int) -> None:
    records = re.findall(
        rf"^test ({re.escape(prefix)}[A-Za-z0-9_]+) \.\.\. (.*)$",
        output.replace("\r\n", "\n"), re.MULTILINE,
    )
    if (len(records) != count or len({name for name, _ in records}) != count
            or any(status != "ok" for _, status in records)):
        raise ValueError(f"expected {count} unique passing {prefix} tests")


def require_ownership_test_results(output: str) -> None:
    # Retention includes two identity-exhaustion tests in its private module.
    require_named_test_result(output, "physical_memory::tests::retention::", 18)
    require_named_test_result(output, "physical_memory::retention::tests::", 2)
    require_named_test_result(output, "physical_memory::tests::ap_resources::", 11)


def require_explicit_test_results(output: str, names: tuple[str, ...]) -> None:
    records = re.findall(r"^test ([A-Za-z0-9_]+) \.\.\. (.*)$", output.replace("\r\n", "\n"), re.MULTILINE)
    for name in names:
        if [status for case, status in records if case == name] != ["ok"]:
            raise ValueError(f"expected exactly one passing ownership test: {name}")


def require_stack_test_results(output: str) -> None:
    require_explicit_test_results(output, STACK_TESTS)


def require_execution_test_results(output: str) -> None:
    require_explicit_test_results(output, EXECUTION_TESTS)


def validate_report(report: dict, root: Path = ROOT) -> None:
    expected = {
        "schema_version": "1.6", "contract_id": "PKRECLAIM1-CORE",
        "selected_move_id": "N12-CONCURRENCY-RECLAMATION-001", "phase": "N12.3",
        "status": "host_verified_live_integration_pending", "production_ready": False,
        "live_integration_verified": False, "cross_cpu_quiescence_verified": False,
        "n12_3_complete": False, "focused_test_count": TEST_COUNT,
        "kernel_regression_count": 245, "compile_fail_borrow_tests": 15,
        "physical_retention_contract_id": "PKRETAIN1",
        "physical_retention_scope": "allocator_enforced_for_explicitly_retained_allocations",
        "physical_retention_test_count": 20, "physical_retention_live_verified": False,
        "ap_resource_contract_id": "PKAPOWN1",
        "ap_resource_test_count": 11,
        "ap_resource_scope": "mandatory_three_ap_runtime_and_two_frames",
        "ap_resource_live_verified": False,
        "task_lifetime_contract_id": "PKLIFE1",
        "task_lifetime_test_count": LIFETIME_TEST_COUNT,
        "task_lifetime_scope": "mandatory_inactive_resources_and_dispatch_execution_hold",
        "task_execution_contract_id": "PKEXEC1",
        "task_execution_test_count": len(EXECUTION_TESTS),
        "task_execution_scope": "mandatory_dispatch_hold_architecture_quiescence_boundary",
        "task_execution_live_verified": False,
        "task_stack_contract_id": "PKSTACK1", "task_stack_page_count": 4,
        "task_stack_test_count": len(STACK_TESTS), "task_stack_live_verified": False,
        "linked_kernel_sha256": KERNEL_SHA256, "linked_kernel_byte_count": 530072,
    }
    if not isinstance(report, dict) or set(report) != set(expected) | {"sources", "stages"}:
        raise ValueError("reclamation report fields changed")
    for key, value in expected.items():
        if type(report[key]) is not type(value) or report[key] != value:
            raise ValueError(f"reclamation report field changed: {key}")
    if report["sources"] != bind_sources(root):
        raise ValueError("reclamation source binding is stale")
    stages = report["stages"]
    if not isinstance(stages, list) or len(stages) != len(STAGES):
        raise ValueError("reclamation stages missing")
    for stage, name in zip(stages, STAGES, strict=True):
        if (
            not isinstance(stage, dict) or set(stage) != {"name", "status", "output_sha256"}
            or stage["name"] != name or stage["status"] != "pass"
            or not isinstance(stage["output_sha256"], str)
            or re.fullmatch(r"[0-9A-F]{64}", stage["output_sha256"]) is None
        ):
            raise ValueError("reclamation stage changed")


def qualify(work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    before = bind_sources()
    cargo, rustc, env = entry._toolchain(entry.DEFAULT_TOOLCHAIN_ROOT)
    stages = []

    def run(name: str, command: list[str], count: int | None = None) -> None:
        print(f"PKRECLAIM1_CORE stage={name}", flush=True)
        log = work / f"{name}.log"
        with log.open("wb") as stream:
            try:
                process = subprocess.run(
                    command, cwd=entry.NATIVE_ROOT, env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=180, check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(f"{name} exceeded 180s; see {log}") from error
        raw = log.read_bytes()
        output = raw.decode("utf-8", errors="replace")
        if process.returncode:
            raise RuntimeError(f"{name} failed; see {log}\n{output[-5000:]}")
        if count is not None:
            require_test_result(output, count)
        if name in {"kernel-regressions", "kernel-regressions-release"}:
            require_ownership_test_results(output)
        if name in {"lifetime-tests-debug", "lifetime-tests-release"}:
            require_stack_test_results(output)
            require_execution_test_results(output)
        stages.append({"name": name, "status": "pass", "output_sha256": hashlib.sha256(raw).hexdigest().upper()})

    base = ["--manifest-path", str(entry.NATIVE_ROOT / "Cargo.toml"), "--package", "poolekernel"]
    target = work / "target"
    host = ["--target", entry.HOST_TARGET, "--locked", "--offline", "--target-dir", str(target)]
    run("format", [str(cargo), "fmt", *base, "--", "--check"])
    for profile, flags, opt in (("debug", [], "0"), ("release", ["--release"], "3")):
        # libtest requires unwind in this host-only optimized harness. Restore
        # the release profile before any freestanding check below.
        if profile == "release":
            env["CARGO_PROFILE_RELEASE_PANIC"] = "unwind"
        run(f"host-build-{profile}", [str(cargo), "build", *base, "--lib", *host, *flags])
        artifacts = target / entry.HOST_TARGET / profile
        binary = work / f"reclamation-core-{profile}.exe"
        # Cargo integration tests also try to link the freestanding kernel bin
        # for Windows. Compile this standalone test harness against the exact
        # Cargo-built rlib instead; do not change the production panic profile.
        run(f"test-build-{profile}", [
            str(rustc), "--test", str(ROOT / "native/kernel/tests/reclamation_core.rs"),
            "--edition=2024", "--target", entry.HOST_TARGET, "-C", f"opt-level={opt}",
            "--extern", f"poolekernel={artifacts / 'libpoolekernel.rlib'}",
            "-L", f"dependency={artifacts / 'deps'}", "-o", str(binary),
        ])
        run(f"tests-{profile}", [str(binary), "--test-threads=1"], TEST_COUNT)
        handoff_libraries = sorted((artifacts / "deps").glob("libpoole_handoff-*.rlib"))
        if len(handoff_libraries) != 1:
            raise ValueError("expected one exact host handoff library")
        lifetime_binary = work / f"task-lifetimes-{profile}.exe"
        run(f"lifetime-build-{profile}", [
            str(rustc), "--test", str(ROOT / "native/kernel/tests/task_lifetimes.rs"),
            "--edition=2024", "--target", entry.HOST_TARGET, "-C", f"opt-level={opt}",
            "--extern", f"poolekernel={artifacts / 'libpoolekernel.rlib'}",
            "--extern", f"poole_handoff={handoff_libraries[0]}",
            "-L", f"dependency={artifacts / 'deps'}", "-o", str(lifetime_binary),
        ])
        run(f"lifetime-tests-{profile}", [str(lifetime_binary), "--test-threads=1"], LIFETIME_TEST_COUNT)
        if profile == "release":
            run("kernel-regressions-release", [str(cargo), "test", *base, "--lib", *host,
                "--release", "--", "--test-threads=1"], 245)
    env.pop("CARGO_PROFILE_RELEASE_PANIC", None)
    run("borrow-doctests", [str(cargo), "test", *base, "--doc", *host], 15)
    run("kernel-regressions", [str(cargo), "test", *base, "--lib", *host, "--", "--test-threads=1"], 245)
    run("host-clippy", [str(cargo), "clippy", *base, "--lib", *host, "--", "-D", "warnings"])
    run("freestanding-clippy", [str(cargo), "clippy", *base, "--lib", "--release",
        "--target", entry.PRODUCT_TARGET, "--locked", "--offline", "--target-dir", str(target),
        "--", "-D", "warnings"])
    host_env = env
    env = entry._product_environment(env)
    try:
        run("linked-kernel-build", [str(cargo), "build", *base, "--bin", "PooleKernelLinked",
            "--release", "--target", entry.PRODUCT_TARGET, "--locked", "--offline",
            "--target-dir", str(target)])
    finally:
        env = host_env
    linked = (target / entry.PRODUCT_TARGET / "release/PooleKernelLinked").read_bytes()
    canonical, _ = entry.kernel_image.canonicalize_linked_image(linked)
    if len(canonical) != 530072 or hashlib.sha256(canonical).hexdigest().upper() != KERNEL_SHA256:
        raise ValueError("linked kernel changed; existing live receipts cannot be inherited")
    if before != bind_sources():
        raise ValueError("source changed during qualification")
    report = {
        "schema_version": "1.6", "contract_id": "PKRECLAIM1-CORE",
        "selected_move_id": "N12-CONCURRENCY-RECLAMATION-001", "phase": "N12.3",
        "status": "host_verified_live_integration_pending", "production_ready": False,
        "live_integration_verified": False, "cross_cpu_quiescence_verified": False,
        "n12_3_complete": False, "focused_test_count": TEST_COUNT,
        "kernel_regression_count": 245, "compile_fail_borrow_tests": 15,
        "physical_retention_contract_id": "PKRETAIN1",
        "physical_retention_scope": "allocator_enforced_for_explicitly_retained_allocations",
        "physical_retention_test_count": 20, "physical_retention_live_verified": False,
        "ap_resource_contract_id": "PKAPOWN1",
        "ap_resource_test_count": 11,
        "ap_resource_scope": "mandatory_three_ap_runtime_and_two_frames",
        "ap_resource_live_verified": False,
        "task_lifetime_contract_id": "PKLIFE1",
        "task_lifetime_test_count": LIFETIME_TEST_COUNT,
        "task_lifetime_scope": "mandatory_inactive_resources_and_dispatch_execution_hold",
        "task_execution_contract_id": "PKEXEC1",
        "task_execution_test_count": len(EXECUTION_TESTS),
        "task_execution_scope": "mandatory_dispatch_hold_architecture_quiescence_boundary",
        "task_execution_live_verified": False,
        "task_stack_contract_id": "PKSTACK1", "task_stack_page_count": 4,
        "task_stack_test_count": len(STACK_TESTS), "task_stack_live_verified": False,
        "linked_kernel_sha256": KERNEL_SHA256, "linked_kernel_byte_count": len(canonical),
        "sources": before, "stages": stages,
    }
    validate_report(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=ROOT / "outputs/reclamation-core-qualification")
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    report = qualify(args.work.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PKRECLAIM1_CORE PASS tests={TEST_COUNT} lifecycle={LIFETIME_TEST_COUNT} stack={len(STACK_TESTS)} execution={len(EXECUTION_TESTS)} retention=20 ap_resources=11 profiles=2 regressions=245 live=0 production=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
