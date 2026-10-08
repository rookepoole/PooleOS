#!/usr/bin/env python3
"""Run bounded host and freestanding checks for inactive PKUSER1 admission."""

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
    paths.update({
        "native/kernel/src/user_entry.rs", "native/kernel/src/user_entry/tests.rs",
        "tools/qualify_native_user_entry.py", "tools/qualify_native_elf_loader.py",
        "specs/native-toolchain-lock.json",
    })
    return {p: digest(ROOT / p) for p in sorted(paths)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/native-user-entry-readiness.json")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if not work.is_relative_to(ROOT):
        parser.error("--work-dir must be inside the repository for relative public provenance")
    work.mkdir(parents=True, exist_ok=False)
    before = source_bindings()
    owner_report = Path("C:/Users/rookp/PooleGlyph/tests/reports/conformance_report.json")
    owner_before = digest(owner_report) if owner_report.is_file() else None
    report: dict = {
        "contract_id": "PKUSER1", "cycle": 234,
        "scope": "host_executed_inactive_user_image_admission",
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
            "x86_64-pc-windows-msvc", *bounded, "--", "--test-threads=1"], 260),
        ("user_entry_host_release", [str(cargo), "test", *common, "--lib", "--release", "--target",
            "x86_64-pc-windows-msvc", *bounded, "user_entry::tests", "--", "--test-threads=1"], 14),
        ("freestanding_library", [str(cargo), "check", *common, "--lib", "--target",
            "x86_64-unknown-none", *bounded], None),
    ]
    try:
        for name, command, expected in commands:
            start = time.monotonic()
            log = work / f"{name}.log"
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=180, check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            output = log.read_text(encoding="utf-8")
            match = re.search(r"test result: ok\. (\d+) passed; 0 failed; 0 ignored;", output)
            passed = result.returncode == 0 and (expected is None or (match is not None and int(match[1]) == expected))
            public_command = [Path(arg).relative_to(ROOT).as_posix() if Path(arg).is_absolute() else arg
                              for arg in command]
            report["checks"].append(dict(name=name, command=public_command, passed=passed,
                returncode=result.returncode, tests_passed=int(match[1]) if match else None,
                elapsed_seconds=round(time.monotonic() - start, 3),
                log_path=log.relative_to(ROOT).as_posix(), log_sha256=digest(log)))
            print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
            if not passed:
                print(output[-12000:], flush=True)
                break
        report["source_unchanged"] = before == source_bindings()
        report["owner_report_unchanged"] = owner_before == (digest(owner_report) if owner_report.is_file() else None)
        if (len(report["checks"]) == len(commands) and all(c["passed"] for c in report["checks"])
                and report["source_unchanged"] and report["owner_report_unchanged"]):
            report["status"] = "pass"
    except (OSError, subprocess.TimeoutExpired) as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
    serialized = json.dumps(report, indent=2) + "\n"
    (work / "receipt.json").write_text(serialized, encoding="utf-8", newline="\n")
    if report["status"] == "pass":
        args.out.write_text(serialized, encoding="utf-8", newline="\n")
    print(f"PKUSER1 {report['status'].upper()}; guest_runs=0; production_ready=false", flush=True)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
