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
    "native/kernel/src/lib.rs",
    "native/kernel/src/atomics.rs",
    "native/kernel/src/locks.rs",
    "native/kernel/tests/reclamation_core.rs",
    "native/kernel/Cargo.toml",
    "native/Cargo.lock",
    "specs/native-toolchain-lock.json",
    "tools/qualify_native_reclamation_core.py",
)
REPORT = ROOT / "runs/native-kernel-reclamation-core-readiness.json"
TEST_COUNT = 19
KERNEL_SHA256 = "9029AEE51A4D557EF5B29945985E4A1F07C67DDE9C8C367C80BD1B9EDD9D409E"
STAGES = (
    "format", "host-build-debug", "test-build-debug", "tests-debug",
    "host-build-release", "test-build-release", "tests-release", "borrow-doctests",
    "kernel-regressions", "host-clippy", "freestanding-clippy", "linked-kernel-build",
)


def bind_sources(root: Path = ROOT) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest().upper() for name in SOURCES}


def require_test_result(output: str, count: int) -> None:
    results = re.findall(r"^test result: (.*)$", output.replace("\r\n", "\n"), re.MULTILINE)
    expected = rf"ok\. {count} passed; 0 failed; 0 ignored; 0 measured; 0 filtered out(?:; finished in [0-9.]+s)?"
    if len(results) != 1 or re.fullmatch(expected, results[0]) is None:
        raise ValueError(f"expected exactly {count} passing tests, no failures/skips/filters")


def validate_report(report: dict, root: Path = ROOT) -> None:
    expected = {
        "schema_version": "1.0", "contract_id": "PKRECLAIM1-CORE",
        "selected_move_id": "N12-CONCURRENCY-RECLAMATION-001", "phase": "N12.3",
        "status": "host_verified_live_integration_pending", "production_ready": False,
        "live_integration_verified": False, "cross_cpu_quiescence_verified": False,
        "n12_3_complete": False, "focused_test_count": TEST_COUNT,
        "kernel_regression_count": 206, "compile_fail_borrow_tests": 1,
        "linked_kernel_sha256": KERNEL_SHA256, "linked_kernel_byte_count": 513680,
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
    env.pop("CARGO_PROFILE_RELEASE_PANIC", None)
    run("borrow-doctests", [str(cargo), "test", *base, "--doc", *host], 1)
    run("kernel-regressions", [str(cargo), "test", *base, "--lib", *host, "--", "--test-threads=1"], 206)
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
    if len(canonical) != 513680 or hashlib.sha256(canonical).hexdigest().upper() != KERNEL_SHA256:
        raise ValueError("linked kernel changed; existing live receipts cannot be inherited")
    if before != bind_sources():
        raise ValueError("source changed during qualification")
    report = {
        "schema_version": "1.0", "contract_id": "PKRECLAIM1-CORE",
        "selected_move_id": "N12-CONCURRENCY-RECLAMATION-001", "phase": "N12.3",
        "status": "host_verified_live_integration_pending", "production_ready": False,
        "live_integration_verified": False, "cross_cpu_quiescence_verified": False,
        "n12_3_complete": False, "focused_test_count": TEST_COUNT,
        "kernel_regression_count": 206, "compile_fail_borrow_tests": 1,
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
    print(f"PKRECLAIM1_CORE PASS tests={TEST_COUNT} profiles=2 regressions=206 live=0 production=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
