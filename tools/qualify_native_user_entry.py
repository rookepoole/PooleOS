#!/usr/bin/env python3
"""Run bounded host, freestanding and optional PKIPC1 native request/reply guests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qualify_native_elf_loader import _toolchain  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def source_bindings() -> dict[str, str]:
    tracked = subprocess.check_output(
        ["git", "ls-files", "native"], cwd=ROOT, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).splitlines()
    paths = {p for p in tracked if Path(p).suffix in {".rs", ".toml", ".lock", ".ld"}}
    # Bind the Python oracle/build dependencies as well as the native image.
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "runtime").glob("*.py"))
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("qualify_native_*.py"))
    paths.update({
        "native/kernel/src/capability_ipc.rs", "native/kernel/src/capability_ipc/tests.rs",
        "native/kernel/src/capability_ipc/wait.rs",
        "native/kernel/src/arch/x86_64/user_ipc.rs", "native/kernel/src/user_root_probe/peer_driver/ipc.rs",
        "native/kernel/src/user_entry.rs", "native/kernel/src/user_entry/tests.rs",
        "native/kernel/src/user_entry/prepared.rs", "native/kernel/src/user_entry/prepared_tests.rs",
        "native/kernel/src/user_entry/cpu.rs", "native/kernel/src/user_entry/cpu_tests.rs",
        "native/kernel/src/user_entry/bootstrap.rs", "native/kernel/src/user_root_probe.rs",
        "native/kernel/src/user_entry/timer.rs", "native/kernel/src/user_root_probe/timer_driver.rs",
        "native/kernel/src/user_entry/privilege.rs", "native/kernel/src/arch/x86_64/user.rs",
        "native/kernel/src/user_entry/preemption.rs", "native/kernel/src/arch/x86_64/user_preempt.rs",
        "native/kernel/src/user_entry/syscall.rs", "native/kernel/src/arch/x86_64/user_syscall.rs",
        "native/kernel/src/user_entry/task.rs", "native/kernel/src/arch/x86_64/user_task.rs",
        "native/kernel/src/user_root_probe/task_driver.rs",
        "native/kernel/src/user_entry/context.rs", "native/kernel/src/arch/x86_64/user_slice.rs",
        "native/kernel/src/user_root_probe/peer_driver.rs",
        "native/kernel/src/user_root_probe/peer_driver/unknown.rs",
        "native/kernel/src/user_entry/spawn.rs", "native/kernel/src/user_entry/spawn_tests.rs",
        "native/kernel/src/user_root_probe/spawn_driver.rs",
        "native/kernel/src/user_entry/timer/watchdog.rs", "native/kernel/src/user_entry/timer/watchdog/tests.rs",
        "native/kernel/src/arch/x86_64/user_watchdog.rs",
        "native/kernel/src/user_entry/timer/drain.rs", "native/kernel/src/user_entry/timer/drain/tests.rs",
        "native/kernel/src/user_root_probe/timer_driver/drain.rs",
        "tools/qualify_native_user_root.py", "runtime/native_user_root.py",
        "tools/qualify_native_pooleboot.py", "tools/qualify_native_kernel_entry.py",
        "tools/qualify_native_user_entry.py", "tools/qualify_native_elf_loader.py",
        "specs/native-toolchain-lock.json",
        "tests/test_native_user_root.py", "tests/fixtures/cycle237-user-root-markers.json",
    })
    return {p: digest(ROOT / p) for p in sorted(paths)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/native-user-entry-readiness.json")
    parser.add_argument("--live-work-dir", type=Path)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if not work.is_relative_to(ROOT):
        parser.error("--work-dir must be inside the repository for relative public provenance")
    work.mkdir(parents=True, exist_ok=False)
    before = source_bindings()
    owner_report = Path("C:/Users/rookp/PooleGlyph/tests/reports/conformance_report.json")
    owner_before = digest(owner_report) if owner_report.is_file() else None
    report: dict = {
        "contract_id": "PKIPC1", "cycle": 251,
        "scope": "host_and_optional_bounded_IPC_readiness_wait_cancel_retirement_guest",
        "status": "fail", "source_bindings": before, "checks": [],
        "guest_runs": 0, "ring3_executed": False, "iso_built": False,
        "n13_exit_passed": False, "production_ready": False,
    }
    cargo, _, env = _toolchain(ROOT / ".toolchains/rust-1.97.0")
    common = ["--manifest-path", str(ROOT / "native/Cargo.toml"), "--package", "poolekernel"]
    bounded = ["--locked", "--offline", "--target-dir", str(work / "target")]
    commands = [
        ("format", [str(cargo), "fmt", *common, "--", "--check"], None),
        ("kernel_host_debug", [str(cargo), "test", *common, "--lib", "--target",
            "x86_64-pc-windows-msvc", *bounded, "--", "--test-threads=1"], 401),
        ("user_entry_host_release", [str(cargo), "test", *common, "--lib", "--release", "--target",
            "x86_64-pc-windows-msvc", *bounded, "user_entry::", "--", "--test-threads=1"], 128),
        ("ipc_host_release", [str(cargo), "test", *common, "--lib", "--release", "--target",
            "x86_64-pc-windows-msvc", *bounded, "capability_ipc::", "--", "--test-threads=1"], 17),
        ("vm_host_release", [str(cargo), "test", *common, "--lib", "--release", "--target",
            "x86_64-pc-windows-msvc", *bounded, "virtual_memory::", "--", "--test-threads=1"], None),
        ("freestanding_library", [str(cargo), "check", *common, "--lib", "--target",
            "x86_64-unknown-none", *bounded], None),
        ("freestanding_kernel_adapter", [str(cargo), "check", *common, "--bin",
            "PooleKernelLinked", "--target", "x86_64-unknown-none", *bounded], None),
        ("prepared_ownership_compile_fail", [str(cargo), "test", *common, "--doc", "--target",
            "x86_64-pc-windows-msvc", *bounded, "user_entry::prepared", "--", "--test-threads=1"], 5),
        ("task_ownership_compile_fail", [str(cargo), "test", *common, "--doc", "--target",
            "x86_64-pc-windows-msvc", *bounded, "user_entry::task", "--", "--test-threads=1"], 2),
        ("spawn_ownership_compile_fail", [str(cargo), "test", *common, "--doc", "--target",
            "x86_64-pc-windows-msvc", *bounded, "user_entry::spawn", "--", "--test-threads=1"], 1),
        ("boot_exit_host", [str(cargo), "test", "--manifest-path", str(ROOT / "native/Cargo.toml"),
            "--package", "poole-boot-exit", "--lib", "--target", "x86_64-pc-windows-msvc",
            *bounded, "--", "--test-threads=1"], None),
        ("user_root_oracle", [sys.executable, "-B", "-m", "unittest", "tests.test_native_user_root", "-v"], None),
    ]
    for feature in ("development-trap-returning", "development-locks"):
        commands.append(("reject_" + feature, [str(cargo), "check", "--manifest-path",
            str(ROOT / "native/Cargo.toml"), "--package", "pooleboot", "--bin", "PooleBoot",
            "--target", "x86_64-unknown-uefi", *bounded, "--features",
            "development-user-root," + feature], "user-root development scenario must be selected alone"))
    if args.live_work_dir is not None:
        live_work = args.live_work_dir.resolve()
        if not live_work.is_relative_to(ROOT) or live_work.exists():
            parser.error("live work directory must be new and inside the repository")
        commands.append(("live_user_root", [sys.executable, "-B", "tools/qualify_native_user_root.py",
            "--work-dir", str(live_work)], None))
    try:
        for name, command, expected in commands:
            start = time.monotonic()
            log = work / f"{name}.log"
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=360 if name == "live_user_root" else 180, check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            output = log.read_text(encoding="utf-8")
            match = re.search(r"test result: ok\. (\d+) passed; 0 failed; 0 ignored;", output)
            passed = result.returncode == 0 and (expected is None or (match is not None and int(match[1]) == expected))
            if isinstance(expected, str):
                passed = result.returncode != 0 and expected in output
            public_command = [(Path(arg).relative_to(ROOT).as_posix() if Path(arg).is_relative_to(ROOT) else "python") if Path(arg).is_absolute() else arg
                              for arg in command]
            report["checks"].append(dict(name=name, command=public_command, passed=passed,
                returncode=result.returncode, tests_passed=int(match[1]) if match else None,
                elapsed_seconds=round(time.monotonic() - start, 3),
                log_path=log.relative_to(ROOT).as_posix(), log_sha256=digest(log)))
            print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
            if not passed:
                print(output[-12000:], flush=True)
                break
            if name == "live_user_root":
                live = json.loads((live_work / "receipt.json").read_bytes())
                if live["status"] != "pass" or len(live["guest_runs"]) != 2:
                    raise ValueError("live user-root evidence incomplete")
                report["live_user_root"] = live
                report["guest_runs"] = 3
                report["user_root_guest_runs"] = 2
                report["ordinary_denial_guest_runs"] = 1
                report["ring3_executed"] = all(g["marker_summary"]["ring3_executed"] for g in live["guest_runs"])
                report["user_timer_preemption"] = all(g["marker_summary"]["user_timer_preemption"] for g in live["guest_runs"])
                report["development_syscall_abi"] = all(g["marker_summary"]["syscall_abi"] == "PSABI1_development" for g in live["guest_runs"])
                report["user_task_termination"] = all(g["marker_summary"]["normal_exits"] == 1 and g["marker_summary"]["fault_terminations"] == 3 for g in live["guest_runs"])
                report["peer_scheduling"] = all(g["marker_summary"]["peer_scheduling"] and g["marker_summary"]["peer_survival_cases"] == 17 for g in live["guest_runs"])
                report["transactional_construction"] = all(g["marker_summary"]["spawn_cleanup_retries"] == 6 and g["marker_summary"]["spawn_peer_continuation"] for g in live["guest_runs"])
                report["timer_shutdown_recovery"] = all(g["marker_summary"]["timer_quarantine_retries"] == 1 and g["marker_summary"]["timer_quarantine_peer_survived"] for g in live["guest_runs"])
                report["bounded_runtime_accounting"] = all(g["marker_summary"]["bounded_runtime_accounting"] for g in live["guest_runs"])
                report["bounded_hpet_backup_recovery"] = all(g["marker_summary"]["bounded_hpet_backup_recovery"] for g in live["guest_runs"])
                report["unknown_runtime_recovery"] = all(g["marker_summary"]["unknown_runtime_recovery"] for g in live["guest_runs"])
                report["bounded_capability_ipc"] = all(g["marker_summary"]["bounded_capability_ipc"] for g in live["guest_runs"])
        report["source_unchanged"] = before == source_bindings()
        report["owner_report_unchanged"] = owner_before == (digest(owner_report) if owner_report.is_file() else None)
        if (len(report["checks"]) == len(commands) and all(c["passed"] for c in report["checks"])
                and report["source_unchanged"] and report["owner_report_unchanged"]):
            report["status"] = "pass"
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
    serialized = json.dumps(report, indent=2) + "\n"
    (work / "receipt.json").write_text(serialized, encoding="utf-8", newline="\n")
    if report["status"] == "pass":
        args.out.write_text(serialized, encoding="utf-8", newline="\n")
    print(f"PKIPC1 {report['status'].upper()}; guest_runs={report['guest_runs']}; ring3={report['ring3_executed']}; production_ready=false", flush=True)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
