#!/usr/bin/env python3
"""Build and inspect the pinned empty PooleBoot/PooleKernel qualification fixtures twice."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.native_binary import (  # noqa: E402
    BinaryFormatError,
    inspect_binary,
    scan_forbidden_markers,
    validate_binary,
)


LOCK_PATH = ROOT / "specs" / "native-toolchain-lock.json"
TARGET_CONTRACT_PATH = ROOT / "specs" / "native-target-contract.json"
NATIVE_ROOT = ROOT / "native"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_OUT = ROOT / "runs" / "native_toolchain_qualification.json"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 300
MAX_TREE_FILES = 4096
MAX_TREE_BYTES = 1024 * 1024 * 1024
MAX_TREE_FILE_BYTES = 512 * 1024 * 1024
BUILD_INPUTS = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/rust-toolchain.toml",
    "native/.cargo/config.toml",
    "native/fixtures/pooleboot/Cargo.toml",
    "native/fixtures/pooleboot/src/main.rs",
    "native/fixtures/poolekernel/Cargo.toml",
    "native/fixtures/poolekernel/src/main.rs",
    "runtime/native_binary.py",
    "tools/bootstrap_native_toolchain.ps1",
    "tools/qualify_native_toolchain.py",
)


class QualificationError(RuntimeError):
    """Raised when a qualification prerequisite or assertion fails."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_binding(relative_path: str) -> dict[str, Any]:
    data = (ROOT / relative_path).read_bytes()
    return {"path": relative_path, "sha256": sha256_bytes(data), "byte_count": len(data)}


def _is_reparse_directory(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _bounded_file_digest(path: Path, *, max_file_bytes: int) -> tuple[bytes, int]:
    byte_count = path.stat().st_size
    if byte_count > max_file_bytes:
        raise QualificationError(f"toolchain file exceeds byte limit: {path.name}")
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            observed += len(chunk)
            if observed > max_file_bytes:
                raise QualificationError(f"toolchain file grew beyond byte limit: {path.name}")
            digest.update(chunk)
    if observed != byte_count:
        raise QualificationError(f"toolchain file changed while hashing: {path.name}")
    return digest.digest(), observed


def tree_binding(
    path: Path,
    role: str,
    *,
    max_files: int = MAX_TREE_FILES,
    max_bytes: int = MAX_TREE_BYTES,
    max_file_bytes: int = MAX_TREE_FILE_BYTES,
) -> dict[str, Any]:
    if not path.is_dir():
        raise QualificationError(f"missing toolchain directory for {role}")
    root = path.resolve()
    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    files: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        children = sorted(current.iterdir(), key=lambda item: item.name)
        for item in children:
            if item.is_dir():
                if _is_reparse_directory(item):
                    raise QualificationError(f"reparse directory in toolchain tree for {role}: {item.name}")
                pending.append(item)
            elif item.is_file():
                files.append(item)
                if len(files) > max_files:
                    raise QualificationError(f"toolchain tree exceeds file limit for {role}")
    for item in sorted(files, key=lambda candidate: candidate.relative_to(root).as_posix()):
        relative = item.relative_to(root).as_posix().encode("utf-8")
        file_digest, file_bytes = _bounded_file_digest(item, max_file_bytes=max_file_bytes)
        byte_count += file_bytes
        if byte_count > max_bytes:
            raise QualificationError(f"toolchain tree exceeds byte limit for {role}")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(file_digest)
        file_count += 1
    if not file_count:
        raise QualificationError(f"empty toolchain directory for {role}")
    return {
        "role": role,
        "tree_sha256": digest.hexdigest().upper(),
        "file_count": file_count,
        "byte_count": byte_count,
    }


def executable_binding(path: Path, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise QualificationError(f"missing executable for {role}")
    data = path.read_bytes()
    return {"role": role, "sha256": sha256_bytes(data), "byte_count": len(data)}


def normalized_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(line.rstrip() for line in completed.stdout.replace("\r\n", "\n").split("\n") if line.rstrip())


def _terminate_process_tree(process: subprocess.Popen[str], env: dict[str, str]) -> None:
    if process.poll() is not None:
        return
    if os.name != "nt":
        process.kill()
        return
    system_root = Path(env.get("SystemRoot", r"C:\Windows"))
    taskkill = system_root / "System32" / "taskkill.exe"

    def request_tree_termination() -> None:
        try:
            subprocess.Popen(
                [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            pass

    threading.Thread(target=request_tree_termination, daemon=True).start()
    try:
        process.kill()
    except OSError:
        pass


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> str:
    state: dict[str, Any] = {}
    finished = threading.Event()
    cancelled = threading.Event()
    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0

    def worker() -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            state["process"] = process
            if cancelled.is_set():
                _terminate_process_tree(process, env)
                return
            stdout, _ = process.communicate()
            state["stdout"] = stdout
            state["returncode"] = process.returncode
        except BaseException as error:  # pragma: no cover - OS launch failure path
            state["error"] = error
        finally:
            finished.set()

    threading.Thread(target=worker, daemon=True).start()
    if not finished.wait(timeout_seconds):
        cancelled.set()
        process = state.get("process")
        if isinstance(process, subprocess.Popen):
            _terminate_process_tree(process, env)
        raise QualificationError(
            f"command timed out after {timeout_seconds}s: {Path(command[0]).name}"
        )
    error = state.get("error")
    if isinstance(error, BaseException):
        raise QualificationError(f"command failed to start: {Path(command[0]).name}: {error}") from error
    completed = subprocess.CompletedProcess(command, int(state["returncode"]), str(state["stdout"]))
    output = normalized_output(completed)
    if completed.returncode != 0:
        tail = "\n".join(output.splitlines()[-20:])
        raise QualificationError(f"command failed with exit code {completed.returncode}: {tail}")
    return output


def isolated_environment(toolchain_root: Path, toolchain_bin: Path, rustc: Path) -> dict[str, str]:
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
    path_parts = [str(toolchain_bin), str(toolchain_root / "cargo" / "bin"), str(system_root / "System32")]
    env.update(
        {
            "CARGO_HOME": str(toolchain_root / "cargo"),
            "CARGO_INCREMENTAL": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": os.pathsep.join(path_parts),
            "RUSTC": str(rustc),
            "RUSTUP_HOME": str(toolchain_root / "rustup"),
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
        }
    )
    return env


def build_command(cargo: Path, target: dict[str, Any], target_dir: Path) -> list[str]:
    return [
        str(cargo),
        "build",
        "--manifest-path",
        str(NATIVE_ROOT / "Cargo.toml"),
        "--package",
        target["package"],
        "--target",
        target["triple"],
        "--release",
        "--locked",
        "--offline",
        "--target-dir",
        str(target_dir),
    ]


def normalized_build_command(channel: str, target: dict[str, Any]) -> list[str]:
    return [
        "$CARGO",
        f"toolchain={channel}",
        "build",
        "--manifest-path",
        "$REPO/native/Cargo.toml",
        "--package",
        target["package"],
        "--target",
        target["triple"],
        "--release",
        "--locked",
        "--offline",
        "--target-dir",
        "$CLEAN_TARGET_DIR",
    ]


def forbidden_markers() -> dict[str, str]:
    values = {
        "workspace_absolute_windows": str(ROOT),
        "workspace_absolute_forward_slash": ROOT.as_posix(),
        "user_profile_absolute_windows": str(Path.home()),
        "user_profile_absolute_forward_slash": Path.home().as_posix(),
        "windows_account_name": os.environ.get("USERNAME", ""),
        "host_library_kernel32": "kernel32.dll",
        "host_library_ntdll": "ntdll.dll",
        "host_library_msvcrt": "msvcrt",
        "host_library_ucrtbase": "ucrtbase",
        "host_library_vcruntime": "vcruntime",
        "host_library_msvcp": "msvcp",
        "host_sdk_windows_kits": "Windows Kits",
    }
    return {key: value for key, value in values.items() if value}


def negative_controls(boot_data: bytes, kernel_data: bytes, markers: dict[str, str], contract: dict[str, Any]) -> list[dict[str, Any]]:
    injected = b"prefix\0C:\\Users\\qualification-user\\source\0suffix"
    injected_hits = scan_forbidden_markers(
        injected,
        {"synthetic_absolute_user_path": r"C:\Users\qualification-user"},
    )
    kernel_expected = contract["targets"][1]["expected_binary"]
    _, substitution_errors = validate_binary(boot_data, kernel_expected)
    malformed_rejected = False
    try:
        inspect_binary(kernel_data[:24])
    except BinaryFormatError:
        malformed_rejected = True
    controls = [
        {
            "id": "injected_host_path_detection",
            "expected": "reject",
            "observed": "reject" if injected_hits else "accept",
            "status": "pass" if injected_hits else "fail",
        },
        {
            "id": "pe_as_elf_target_substitution",
            "expected": "reject",
            "observed": "reject" if substitution_errors else "accept",
            "status": "pass" if substitution_errors else "fail",
        },
        {
            "id": "truncated_elf_header",
            "expected": "reject",
            "observed": "reject" if malformed_rejected else "accept",
            "status": "pass" if malformed_rejected else "fail",
        },
    ]
    if any(item["status"] != "pass" for item in controls):
        raise QualificationError("one or more negative controls failed")
    if not markers:
        raise QualificationError("host-leakage marker set is empty")
    return controls


def make_report(
    toolchain_root: Path,
    status_date: str,
    *,
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    contract = json.loads(TARGET_CONTRACT_PATH.read_text(encoding="utf-8"))
    channel = lock["toolchain"]["channel"]
    host = lock["host"]["triple"]
    installed = toolchain_root / "rustup" / "toolchains" / channel
    toolchain_bin = installed / "bin"
    cargo = toolchain_bin / "cargo.exe"
    rustc = toolchain_bin / "rustc.exe"
    lld = installed / "lib" / "rustlib" / host / "bin" / "rust-lld.exe"
    rustup = toolchain_root / "cargo" / "bin" / "rustup.exe"
    for path, role in ((cargo, "cargo"), (rustc, "rustc"), (lld, "rust-lld"), (rustup, "rustup")):
        if not path.is_file():
            raise QualificationError(f"{role} is missing; run tools/bootstrap_native_toolchain.ps1")

    env = isolated_environment(toolchain_root, toolchain_bin, rustc)
    print("NATIVE_TOOLCHAIN_QUALIFICATION STAGE versions", flush=True)
    version_timeout = min(command_timeout_seconds, 30)
    versions = {
        "rustc": run_checked([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env, timeout_seconds=version_timeout),
        "cargo": run_checked([str(cargo), "--version", "--verbose"], cwd=ROOT, env=env, timeout_seconds=version_timeout),
        "rust_lld": run_checked([str(lld), "-flavor", "gnu", "--version"], cwd=ROOT, env=env, timeout_seconds=version_timeout),
        "rustup": run_checked([str(rustup), "--version"], cwd=ROOT, env=env, timeout_seconds=version_timeout).splitlines()[0],
    }
    if lock["channel_manifest"]["rust_version"] not in versions["rustc"]:
        raise QualificationError("installed rustc does not match the locked channel manifest")

    tmp_root = ROOT / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    built: dict[str, list[bytes]] = {target["id"]: [] for target in contract["targets"]}
    with tempfile.TemporaryDirectory(prefix="native-toolchain-qualification-", dir=tmp_root) as temp:
        temp_root = Path(temp)
        for run_index in (1, 2):
            target_dir = temp_root / f"run-{run_index}" / "target"
            for target in contract["targets"]:
                print(
                    f"NATIVE_TOOLCHAIN_QUALIFICATION STAGE build run={run_index} target={target['id']}",
                    flush=True,
                )
                command = build_command(cargo, target, target_dir)
                run_checked(
                    command,
                    cwd=NATIVE_ROOT,
                    env=env,
                    timeout_seconds=command_timeout_seconds,
                )
                binary = target_dir / target["triple"] / "release" / target["binary_name"]
                if not binary.is_file():
                    raise QualificationError(f"expected build output is missing for {target['id']}")
                built[target["id"]].append(binary.read_bytes())

    markers = forbidden_markers()
    builds: list[dict[str, Any]] = []
    retained: dict[str, bytes] = {}
    for target in contract["targets"]:
        first, second = built[target["id"]]
        if first != second:
            raise QualificationError(f"clean builds are not byte-identical for {target['id']}")
        inspection, errors = validate_binary(first, target["expected_binary"])
        if errors or inspection is None:
            raise QualificationError(f"binary contract failed for {target['id']}: {'; '.join(errors)}")
        leakage_hits = scan_forbidden_markers(first, markers)
        if leakage_hits:
            hit_ids = ", ".join(sorted({item["marker_id"] for item in leakage_hits}))
            raise QualificationError(f"host leakage found in {target['id']}: {hit_ids}")
        digest = sha256_bytes(first)
        builds.append(
            {
                "id": target["id"],
                "package": target["package"],
                "target_triple": target["triple"],
                "binary_name": target["binary_name"],
                "normalized_command": normalized_build_command(channel, target),
                "clean_run_count": 2,
                "run_sha256": [digest, sha256_bytes(second)],
                "run_byte_count": [len(first), len(second)],
                "exact_byte_match": True,
                "binary_contract_pass": True,
                "host_leakage_marker_count": len(markers),
                "host_leakage_hit_count": 0,
                "inspection": inspection,
            }
        )
        retained[target["binary_name"]] = first

    controls = negative_controls(
        built[contract["targets"][0]["id"]][0],
        built[contract["targets"][1]["id"]][0],
        markers,
        contract,
    )
    tool_files = [
        executable_binding(rustup, "rustup_proxy"),
        executable_binding(rustc, "rustc"),
        executable_binding(cargo, "cargo"),
        executable_binding(lld, "rust_lld"),
    ]
    print("NATIVE_TOOLCHAIN_QUALIFICATION STAGE target_tree_hashes", flush=True)
    target_trees = [
        tree_binding(installed / "lib" / "rustlib" / "x86_64-unknown-uefi" / "lib", "rust_std_uefi"),
        tree_binding(installed / "lib" / "rustlib" / "x86_64-unknown-none" / "lib", "rust_std_none"),
    ]
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_toolchain_qualification",
        "status_date": status_date,
        "status": "pass_single_windows_host_non_promoting",
        "production_ready": False,
        "production_promotion_allowed": False,
        "scope": {
            "host_environment_count": 1,
            "host_class": "x86_64-pc-windows-msvc",
            "clean_run_count_per_fixture": 2,
            "fixture_count": len(builds),
            "functional_boot_tested": False,
            "kernel_execution_tested": False,
            "two_host_reproduction_complete": False,
        },
        "bindings": {
            "toolchain_lock": file_binding("specs/native-toolchain-lock.json"),
            "target_contract": file_binding("specs/native-target-contract.json"),
            "build_inputs": [file_binding(path) for path in BUILD_INPUTS],
        },
        "toolchain": {
            "channel": channel,
            "profile": lock["toolchain"]["profile"],
            "versions": versions,
            "executables": tool_files,
            "target_library_trees": target_trees,
            "toolchain_root_recorded": False,
            "global_path_mutated": False,
        },
        "environment": {
            "cargo_locked": True,
            "cargo_offline": True,
            "source_date_epoch": "0",
            "timezone": "UTC",
            "locale": "C",
            "incremental_compilation": False,
            "clean_target_directory_per_run": True,
            "external_crate_count": 0,
        },
        "builds": builds,
        "negative_controls": controls,
        "summary": {
            "fixture_count": len(builds),
            "byte_identical_fixture_count": sum(item["exact_byte_match"] for item in builds),
            "binary_contract_pass_count": sum(item["binary_contract_pass"] for item in builds),
            "host_leakage_hit_count": sum(item["host_leakage_hit_count"] for item in builds),
            "negative_control_count": len(controls),
            "negative_control_pass_count": sum(item["status"] == "pass" for item in controls),
        },
        "open_items": lock["open_items"],
        "claim_boundary": [
            "This is one-host compiler, linker, format, reproducibility, and leakage qualification evidence.",
            "The fixtures do not implement or boot PooleBoot or PooleKernel.",
            "The report does not accept ADR-0003 or close the N3 two-clean-host exit gate.",
            "No fixture, tool binary, or host path is embedded in this public JSON ledger.",
            "Production and release promotion remain prohibited.",
        ],
    }
    return report, retained


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--status-date", default="2026-07-16")
    parser.add_argument(
        "--command-timeout-seconds",
        type=int,
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
    )
    args = parser.parse_args(argv)
    if not 1 <= args.command_timeout_seconds <= 3600:
        parser.error("--command-timeout-seconds must be between 1 and 3600")
    try:
        report, artifacts = make_report(
            args.toolchain_root.resolve(),
            args.status_date,
            command_timeout_seconds=args.command_timeout_seconds,
        )
    except (OSError, QualificationError, BinaryFormatError, json.JSONDecodeError) as error:
        print(f"NATIVE_TOOLCHAIN_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    if args.artifacts_dir:
        args.artifacts_dir.mkdir(parents=True, exist_ok=True)
        for name, data in artifacts.items():
            destination = args.artifacts_dir / name
            destination.write_bytes(data)
    summary = report["summary"]
    print(
        "NATIVE_TOOLCHAIN_QUALIFICATION PASS "
        f"fixtures={summary['binary_contract_pass_count']}/{summary['fixture_count']} "
        f"byte_identical={summary['byte_identical_fixture_count']} "
        f"negative_controls={summary['negative_control_pass_count']}/{summary['negative_control_count']} "
        "two_host=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
