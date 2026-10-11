"""Compile independent PooleInit/PooleCounter artifacts; never infer native execution."""
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
from runtime.native_user_program import extract
from tools.qualify_native_elf_loader import _toolchain

USER = ROOT / "native/userspace"
TARGET = "x86_64-unknown-none"

def bindings() -> dict[str, str]:
    paths = list(USER.rglob("*.rs")) + [USER / "Cargo.toml", USER / "Cargo.lock", USER / "linker.ld"]
    paths += [ROOT / p for p in ("runtime/native_user_program.py",
        "tools/qualify_native_user_programs.py", "tests/test_native_user_program.py",
        "native/.cargo/config.toml", "tools/qualify_native_elf_loader.py",
        "tools/qualify_native_toolchain.py", "tools/native_host_toolchain.py",
        "specs/native-toolchain-lock.json", "specs/native-host-msvc-profile.json")]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest().upper()
            for p in sorted(paths)}

def run(command: list[str], env: dict, log: Path) -> str:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    log.write_bytes(result.stdout)
    text = result.stdout.decode("utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"command failed ({result.returncode}): {log.name}\n{text[-5000:]}")
    return text

def build(cargo: Path, env: dict, target: Path, log: Path) -> dict:
    flags = ["-Cpanic=abort", "-Crelocation-model=pic", "-Ccode-model=small",
        "-Cno-redzone=yes", "-Csave-temps=yes", "-Clink-arg=-static", "-Clink-arg=--no-pie",
        "-Clink-arg=--no-dynamic-linker", "-Clink-arg=--no-eh-frame-hdr",
        "-Clink-arg=--build-id=none", "-Clink-arg=--gc-sections",
        f"-Clink-arg=-T{USER / 'linker.ld'}", "-Clink-arg=--entry=_start",
        f"--remap-path-prefix={ROOT.resolve()}=/pooleos"]
    env = dict(env)
    env.pop("RUSTFLAGS", None)
    env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
    command = [str(cargo), "build", "--manifest-path", str(USER / "Cargo.toml"),
        "--bins", "--release", "--target", TARGET, "--target-dir", str(target), "--locked", "--offline"]
    run(command, env, log)
    result = {}
    for name in ("PooleInit", "PooleCounter"):
        path = target / TARGET / "release" / name
        blob = path.read_bytes()
        code, record = extract(blob)
        objects = list((path.parent / "deps").glob(name + "*.rcgu.o"))
        if len(objects) != 1: raise ValueError("expected one program codegen object")
        readobj = cargo.parent.parent / "lib/rustlib/x86_64-pc-windows-msvc/bin/llvm-readobj.exe"
        audit = json.loads(run([str(readobj), "--elf-output-style=JSON", "--relocations", str(objects[0])],
            env, target.parent / f"{target.name}-{name}-relocations.json"))
        if len(audit) != 1: raise ValueError("ambiguous object audit")
        relocs = [item["Relocation"] for group in audit[0]["Relocations"] for item in group["Relocs"]]
        if not relocs or any(r["Type"]["Name"] not in ("R_X86_64_PC32", "R_X86_64_PLT32")
                or not r["Symbol"]["Name"].startswith((".text.", ".rodata.")) for r in relocs):
            raise ValueError("program object needs non-local or non-relative relocation")
        record["object_relocation_count"] = len(relocs)
        record["object_relocation_kinds"] = sorted({r["Type"]["Name"] for r in relocs})
        (target.parent / f"{target.name}-{name}.bin").write_bytes(code)
        result[name] = dict(record, source_binary=f"native/userspace/src/bin/{'init' if name == 'PooleInit' else 'counter'}.rs")
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if not work.is_relative_to(ROOT / "outputs"):
        parser.error("work directory must be under workspace outputs")
    work.mkdir(parents=True, exist_ok=False)
    before = bindings()
    report = dict(cycle=260, contract_id="PUSERBIN1", status="fail", source_bindings=before,
        source_unchanged=False, native_execution_verified=False, actual_init_service=False,
        normal_session_boot=False, iso_built=False, production_ready=False)
    try:
        cargo, rustc, env = _toolchain(ROOT / ".toolchains/rust-1.97.0")
        installed = cargo.parent.parent
        tools = installed / "lib/rustlib/x86_64-pc-windows-msvc/bin"
        libraries = installed / ("lib/rustlib/" + TARGET + "/lib")
        core = list(libraries.glob("libcore-*.rlib"))
        builtins = list(libraries.glob("libcompiler_builtins-*.rlib"))
        if len(core) != 1 or len(builtins) != 1: raise ValueError("ambiguous freestanding sysroot")
        inputs = [rustc, cargo, tools / "rust-lld.exe", tools / "llvm-readobj.exe", *core, *builtins]
        tool_bindings = {p.name: hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in inputs}
        report["toolchain"] = {
            "rustc_sha256": hashlib.sha256(rustc.read_bytes()).hexdigest().upper(),
            "cargo_sha256": hashlib.sha256(cargo.read_bytes()).hexdigest().upper(),
            "lock_path": "specs/native-toolchain-lock.json",
            "host_msvc_verified": True, "builds_offline_locked": True,
            "conventional_compilation": True, "kernel_dependency": False,
            "input_hashes": tool_bindings}
        run([str(cargo), "fmt", "--manifest-path", str(USER / "Cargo.toml"), "--", "--check"], env, work / "format.log")
        report["host_tests"] = []
        for release in (False, True):
            command=[str(cargo), "test", "--manifest-path", str(USER / "Cargo.toml"),
                "--lib", "--locked", "--offline", "--target-dir", str(work / "host")]
            if release: command.append("--release")
            output=run(command,env,work / ("release.log" if release else "debug.log"))
            match=re.search(r"test result: ok\. (\d+) passed; 0 failed; 0 ignored;",output)
            if not match or int(match[1]) != 15: raise ValueError("expected15 Rust host tests")
            report["host_tests"].append(dict(profile="release" if release else "debug", tests_passed=int(match[1])))
        first=build(cargo,env,work / "build1",work / "build1.log")
        second=build(cargo,env,work / "build2",work / "build2.log")
        if first != second: raise ValueError("independent build metadata differs")
        for name in first:
            for suffix in ("", ".bin"):
                if suffix:
                    a=work / f"build1-{name}.bin"; b=work / f"build2-{name}.bin"
                else:
                    a=work / "build1" / TARGET / "release" / name; b=work / "build2" / TARGET / "release" / name
                if a.read_bytes() != b.read_bytes(): raise ValueError("independent build bytes differ")
        report.update(programs=first, independent_builds=2, direct_byte_equality=True)
        if {p.name: hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in inputs} != tool_bindings:
            raise ValueError("toolchain inputs changed during build")
        report["toolchain"]["inputs_unchanged"] = True
        if bindings() != before: raise ValueError("source drift")
        report.update(status="pass",source_unchanged=True)
    except Exception as error:
        report["failure"]=f"{type(error).__name__}: {error}"
    report["source_unchanged"] = bindings() == before
    if not report["source_unchanged"]:
        report.update(status="fail", failure="source drift")
    (work / "receipt.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))
    return 0 if report["status"] == "pass" else 1

if __name__ == "__main__": raise SystemExit(main())
