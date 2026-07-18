#!/usr/bin/env python3
"""Build, adversarially inspect, and execute the bounded PooleBoot UEFI proof twice."""

from __future__ import annotations

import argparse
import binascii
import copy
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_live_boot_handoff, native_pooleboot, native_tier0  # noqa: E402
from runtime.native_binary import inspect_binary, scan_forbidden_markers, validate_binary  # noqa: E402


CONTRACT_RELATIVE = native_pooleboot.CONTRACT_RELATIVE
CONTRACT_PATH = ROOT / CONTRACT_RELATIVE
DEFAULT_OUT = ROOT / "runs" / "native_pooleboot_readiness.json"
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
NATIVE_ROOT = ROOT / "native"
BUILD_INPUTS = native_pooleboot.PROOF_IMPLEMENTATION_INPUTS
EXPECTED_PE = {
    "format": "PE32+",
    "machine": 0x8664,
    "subsystem": 10,
    "timestamp": 0,
    "entry_nonzero": True,
    "imports_present": False,
    "debug_directory_present": False,
}


class QualificationError(RuntimeError):
    """Raised when PooleBoot qualification fails closed."""


def _normalized_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        line.rstrip()
        for line in completed.stdout.replace("\r\n", "\n").split("\n")
        if line.rstrip()
    )


def _run_checked(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
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
    output = _normalized_output(completed)
    if completed.returncode != 0:
        raise QualificationError(
            f"command failed with exit code {completed.returncode}: "
            + "\n".join(output.splitlines()[-30:])
        )
    return output


def _toolchain(toolchain_root: Path) -> tuple[Path, Path, dict[str, str]]:
    lock = json.loads((ROOT / "specs/native-toolchain-lock.json").read_text(encoding="utf-8"))
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
    native_root = NATIVE_ROOT.resolve()
    env["CARGO_TARGET_X86_64_UNKNOWN_UEFI_RUSTFLAGS"] = " ".join(
        (
            "-Cpanic=abort",
            "-Clink-arg=/debug:none",
            "-Clink-arg=/timestamp:0",
            '--cfg=sha2_backend="soft"',
            '--cfg=sha2_backend_soft="compact"',
            f"--remap-path-prefix={native_root}=/pooleos/native",
        )
    )
    env["CARGO_TARGET_X86_64_UNKNOWN_NONE_RUSTFLAGS"] = " ".join(
        (
            "-Cpanic=abort",
            "-Crelocation-model=static",
            "-Clink-arg=--entry=_start",
            "-Clink-arg=--build-id=none",
            "-Clink-arg=--gc-sections",
            "-Clink-arg=-static",
            f"--remap-path-prefix={native_root}=/pooleos/native",
        )
    )
    version = _run_checked([str(rustc), "--version", "--verbose"], cwd=ROOT, env=env)
    if lock["channel_manifest"]["rust_version"] not in version or host not in version:
        raise QualificationError("workspace-local rustc does not match the native toolchain lock")
    return cargo, rustc, env


def _build_and_test(toolchain_root: Path, temporary_root: Path) -> tuple[bytes, dict[str, Any]]:
    cargo, _, env = _toolchain(toolchain_root)
    test_target = temporary_root / "host-contract-tests"
    test_output = _run_checked(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "pooleboot",
            "--lib",
            "--target",
            "x86_64-pc-windows-msvc",
            "--locked",
            "--offline",
            "--target-dir",
            str(test_target),
            "--",
            "--test-threads=1",
        ],
        cwd=NATIVE_ROOT,
        env=env,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test_output)
    if match is None:
        raise QualificationError("PooleBoot host contract test summary is missing")
    test_count = int(match.group(1))
    if test_count < 8:
        raise QualificationError("PooleBoot host contract test set unexpectedly shrank")

    builds: list[bytes] = []
    for run_index in (1, 2):
        target_dir = temporary_root / f"clean-build-{run_index}"
        _run_checked(
            [
                str(cargo),
                "build",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                "pooleboot",
                "--target",
                "x86_64-unknown-uefi",
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(target_dir),
            ],
            cwd=NATIVE_ROOT,
            env=env,
        )
        path = target_dir / "x86_64-unknown-uefi" / "release" / "PooleBoot.efi"
        if not path.is_file():
            raise QualificationError("clean PooleBoot build output is missing")
        builds.append(path.read_bytes())
    if builds[0] != builds[1]:
        raise QualificationError("two clean PooleBoot builds are not byte-identical")
    inspection, errors = validate_binary(builds[0], EXPECTED_PE)
    if errors or inspection is None:
        raise QualificationError("PooleBoot PE32+ contract failed: " + "; ".join(errors))
    if len(builds[0]) > 262_144:
        raise QualificationError("PooleBoot proof exceeds its binary size budget")
    forbidden = {
        "workspace_absolute_windows": str(ROOT),
        "workspace_absolute_forward_slash": ROOT.as_posix(),
        "user_profile_absolute_windows": str(Path.home()),
        "user_profile_absolute_forward_slash": Path.home().as_posix(),
        "host_library_kernel32": "kernel32.dll",
        "host_library_msvcrt": "msvcrt",
        "host_library_vcruntime": "vcruntime",
    }
    leakage = scan_forbidden_markers(builds[0], forbidden)
    if leakage:
        raise QualificationError("host marker leaked into PooleBoot PE32+")
    return builds[0], {
        "host_contract_test_count": test_count,
        "host_contract_test_pass_count": test_count,
        "clean_build_count": 2,
        "exact_clean_build_match": True,
        "sha256": native_pooleboot.sha256_bytes(builds[0]),
        "byte_count": len(builds[0]),
        "inspection": inspection,
        "host_leakage_marker_count": len(forbidden),
        "host_leakage_hit_count": 0,
    }


class _QmpClient:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.stream = sock.makefile("rwb", buffering=0)
        self.event_count = 0

    @classmethod
    def connect(cls, port: int, process: subprocess.Popen[bytes], timeout: int) -> tuple[_QmpClient, dict[str, Any]]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise QualificationError(f"QEMU exited before QMP connected: {process.returncode}")
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=1)
                sock.settimeout(5)
                client = cls(sock)
                greeting = client._read_message()
                if not isinstance(greeting.get("QMP"), dict):
                    raise QualificationError("QMP greeting is missing")
                return client, greeting["QMP"]
            except (OSError, socket.timeout):
                time.sleep(0.05)
        raise QualificationError("QMP connection timed out")

    def _read_message(self) -> dict[str, Any]:
        line = self.stream.readline()
        if not line:
            raise QualificationError("QMP connection closed unexpectedly")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise QualificationError("QMP emitted malformed JSON") from error
        if not isinstance(value, dict):
            raise QualificationError("QMP message root is not an object")
        return value

    def execute(self, command: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        request: dict[str, Any] = {"execute": command}
        if arguments is not None:
            request["arguments"] = arguments
        self.stream.write((json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8"))
        while True:
            response = self._read_message()
            if "event" in response:
                self.event_count += 1
                continue
            if "error" in response:
                raise QualificationError(f"QMP command failed: {command}: {response['error']}")
            if "return" in response:
                return response

    def close(self) -> None:
        try:
            self.stream.close()
        finally:
            self.sock.close()


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _execute_once(
    run_id: str,
    lock: dict[str, Any],
    profile: dict[str, Any],
    qemu_root: Path,
    media_path: Path,
    run_dir: Path,
    timeout: int,
    marker_validator: Callable[[list[str]], dict[str, Any]] = native_pooleboot.validate_markers,
) -> tuple[dict[str, Any], bytes, bytes]:
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    vars_source = qemu_root / firmware["vars_template_copy_only"]["relative_path"]
    shutil.copyfile(vars_source, run_dir / profile["evidence_contract"]["vars_copy"])
    command = native_tier0._actual_command(
        lock,
        profile,
        "bootstrap-debug",
        qemu_root,
        media_path,
        run_dir,
    )
    port = _available_port()
    command.extend(
        [
            "-device",
            "VGA,id=poole_gop",
            "-qmp",
            f"tcp:127.0.0.1:{port},server=on,wait=off",
        ]
    )
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    client: _QmpClient | None = None
    try:
        client, greeting = _QmpClient.connect(port, process, timeout)
        client.execute("qmp_capabilities")
        debug_path = run_dir / profile["evidence_contract"]["debugcon_log"]
        serial_path = run_dir / profile["evidence_contract"]["serial_log"]
        screenshot_path = run_dir / "pooleboot-frame.ppm"
        deadline = time.monotonic() + timeout
        screenshot_captured = False
        completion_marker_observed = False
        while time.monotonic() < deadline:
            raw_debug = debug_path.read_bytes() if debug_path.is_file() else b""
            if b"POOLEBOOT/0.1 ERROR" in raw_debug or b"POOLEBOOT/0.1 PANIC" in raw_debug:
                raise QualificationError("PooleBoot emitted an error or panic marker")
            if not screenshot_captured and b"POOLEBOOT/0.1 FRAME READY" in raw_debug:
                client.execute(
                    "screendump",
                    {"filename": str(screenshot_path.resolve()), "format": "ppm"},
                )
                if not screenshot_path.is_file():
                    raise QualificationError("QMP screendump did not create the proof frame")
                screenshot_captured = True
            if b"POOLEBOOT/0.1 STOP BEFORE TRANSFER" in raw_debug:
                completion_marker_observed = True
                break
            if process.poll() is not None:
                raise QualificationError(f"QEMU exited before the stop marker: {process.returncode}")
            time.sleep(0.02)
        if not screenshot_captured or not completion_marker_observed:
            raise QualificationError("PooleBoot frame or permanent stop marker timed out")
        time.sleep(0.05)
        debug_raw = debug_path.read_bytes()
        serial_raw = serial_path.read_bytes()
        debug_markers = native_pooleboot.extract_markers(debug_raw)
        serial_markers = native_pooleboot.extract_markers(serial_raw)
        marker_summary = marker_validator(debug_markers)
        if serial_markers != debug_markers:
            raise QualificationError("serial and debugcon PooleBoot marker sequences differ")
        try:
            debug_transcript = native_live_boot_handoff.extract_transcript(debug_raw)
            serial_transcript = native_live_boot_handoff.extract_transcript(serial_raw)
        except native_live_boot_handoff.LiveHandoffError as error:
            raise QualificationError(str(error)) from error
        if debug_transcript.data != serial_transcript.data:
            raise QualificationError("serial and debugcon PBP1 transcripts differ")
        screenshot_data = screenshot_path.read_bytes()
        screenshot = native_pooleboot.inspect_ppm(screenshot_data)
        client.execute("quit")
        process.wait(timeout=10)
        if process.returncode != 0:
            raise QualificationError(f"QEMU QMP quit returned exit code {process.returncode}")
        stderr = process.stderr.read() if process.stderr is not None else b""
        marker_bytes = native_pooleboot.canonical_json_bytes(debug_markers)
        return (
            {
                "run_id": run_id,
                "fresh_vars_copy": True,
                "media_read_only": True,
                "guest_network": False,
                "host_acceleration": False,
                "qmp_loopback_only": True,
                "qmp_greeting": greeting,
                "timestamped_qmp_events_excluded_from_equality": True,
                "qmp_quit_requested": True,
                "qemu_exit_code": process.returncode,
                "markers": debug_markers,
                "marker_sha256": native_pooleboot.sha256_bytes(marker_bytes),
                "serial_debugcon_exact_match": True,
                "marker_summary": marker_summary,
                "pbp1_transcript": debug_transcript.summary,
                "pbp1_serial_debugcon_exact_match": True,
                "screenshot": screenshot,
                "stderr_sha256": native_pooleboot.sha256_bytes(stderr),
                "stderr_byte_count": len(stderr),
                "local_paths_recorded": False,
            },
            screenshot_data,
            debug_transcript.data,
        )
    finally:
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
        if process.poll() is None:
            process.kill()
            process.wait()


def _recalculate_gpt_header(image: bytearray, header_lba: int, entries_crc: int) -> None:
    offset = header_lba * native_pooleboot.SECTOR_BYTES
    struct.pack_into("<I", image, offset + 88, entries_crc)
    struct.pack_into("<I", image, offset + 16, 0)
    crc = binascii.crc32(image[offset : offset + native_pooleboot.GPT_HEADER_BYTES]) & 0xFFFFFFFF
    struct.pack_into("<I", image, offset + 16, crc)


def _rejected(action: Any) -> bool:
    try:
        action()
    except (ValueError, native_pooleboot.PooleBootError):
        return True
    return False


def _negative_controls(
    binary: bytes,
    media: bytes,
    markers: list[str],
    screenshot: bytes,
    claims: dict[str, bool],
) -> list[dict[str, str]]:
    pe_offset = struct.unpack_from("<I", binary, 0x3C)[0]
    optional = pe_offset + 24

    wrong_subsystem = bytearray(binary)
    struct.pack_into("<H", wrong_subsystem, optional + 68, 3)
    _, subsystem_errors = validate_binary(bytes(wrong_subsystem), EXPECTED_PE)
    wrong_machine = bytearray(binary)
    struct.pack_into("<H", wrong_machine, pe_offset + 4, 0x14C)
    _, machine_errors = validate_binary(bytes(wrong_machine), EXPECTED_PE)
    debug_directory = bytearray(binary)
    struct.pack_into("<II", debug_directory, optional + 160, 0x1000, 28)
    _, debug_errors = validate_binary(bytes(debug_directory), EXPECTED_PE)

    primary_crc = bytearray(media)
    primary_crc[native_pooleboot.PRIMARY_HEADER_LBA * 512 + 24] ^= 1
    backup_crc = bytearray(media)
    backup_crc[native_pooleboot.BACKUP_HEADER_LBA * 512 + 24] ^= 1
    entry_crc = bytearray(media)
    entry_crc[native_pooleboot.PRIMARY_ENTRIES_LBA * 512 + 56] ^= 1

    esp_type = bytearray(media)
    primary_entries_offset = native_pooleboot.PRIMARY_ENTRIES_LBA * 512
    backup_entries_offset = native_pooleboot.BACKUP_ENTRIES_LBA * 512
    entry_bytes = native_pooleboot.GPT_ENTRY_COUNT * native_pooleboot.GPT_ENTRY_BYTES
    for offset in (primary_entries_offset, backup_entries_offset):
        esp_type[offset] ^= 1
    entries_crc = binascii.crc32(esp_type[primary_entries_offset : primary_entries_offset + entry_bytes]) & 0xFFFFFFFF
    _recalculate_gpt_header(esp_type, native_pooleboot.PRIMARY_HEADER_LBA, entries_crc)
    _recalculate_gpt_header(esp_type, native_pooleboot.BACKUP_HEADER_LBA, entries_crc)

    inspection = native_pooleboot.inspect_media_bytes(media)
    fat_sectors = inspection["fat32"]["fat_sector_count"]
    first_fat_offset = (native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS) * 512
    fat_bytes = fat_sectors * 512
    fat_copy = bytearray(media)
    fat_copy[first_fat_offset + fat_bytes + 8] ^= 1
    fat_loop = bytearray(media)
    for offset in (first_fat_offset, first_fat_offset + fat_bytes):
        struct.pack_into("<I", fat_loop, offset + 5 * 4, 5)
    data_start_lba = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + native_pooleboot.FAT_COUNT * fat_sectors
    )
    fallback_path = bytearray(media)
    boot_directory_offset = (data_start_lba + 2) * 512
    fallback_path[boot_directory_offset + 64] = ord("X")
    unsafe_output_paths = (
        Path(r"\\.\PhysicalDrive0"),
        ROOT.parent / "pooleboot-outside.img",
        ROOT / "docs" / "pooleboot-clobber.img",
        ROOT / "tmp" / "NUL.img",
        ROOT / "tmp" / "pooleboot.img:stream",
    )
    unsafe_output_paths_rejected = all(
        _rejected(
            lambda candidate=candidate: native_pooleboot.validate_workspace_output_path(
                ROOT, candidate, ".img"
            )
        )
        for candidate in unsafe_output_paths
    )

    omitted = markers[:]
    omitted.pop(6)
    reordered = markers[:]
    reordered[1], reordered[2] = reordered[2], reordered[1]
    ppm_parts = screenshot.split(b"\n", 3)
    blank_screenshot = b"\n".join(ppm_parts[:3]) + b"\n" + bytes(len(ppm_parts[3]))
    overclaim = copy.deepcopy(claims)
    overclaim["production_ready"] = True

    observations = (
        ("NEG-N5-PE-SUBSYSTEM", bool(subsystem_errors)),
        ("NEG-N5-PE-MACHINE", bool(machine_errors)),
        ("NEG-N5-PE-DEBUG-DIRECTORY", bool(debug_errors)),
        ("NEG-N5-GPT-PRIMARY-CRC", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(primary_crc)))),
        ("NEG-N5-GPT-BACKUP-CRC", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(backup_crc)))),
        ("NEG-N5-GPT-ENTRY-CRC", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(entry_crc)))),
        ("NEG-N5-ESP-TYPE", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(esp_type)))),
        ("NEG-N5-FAT-COPY", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(fat_copy)))),
        ("NEG-N5-FAT-CHAIN-LOOP", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(fat_loop)))),
        ("NEG-N5-FALLBACK-PATH", _rejected(lambda: native_pooleboot.inspect_media_bytes(bytes(fallback_path)))),
        ("NEG-N5-MEDIA-OUTPUT-PATH", unsafe_output_paths_rejected),
        ("NEG-N5-MARKER-OMISSION", _rejected(lambda: native_pooleboot.validate_markers(omitted))),
        ("NEG-N5-MARKER-ORDER", _rejected(lambda: native_pooleboot.validate_markers(reordered))),
        ("NEG-N5-SCREENSHOT-BLANK", _rejected(lambda: native_pooleboot.inspect_ppm(blank_screenshot))),
        ("NEG-N5-CLAIM-OVERREACH", _rejected(lambda: native_pooleboot.validate_claims(overclaim))),
    )
    controls = [
        {
            "id": control_id,
            "expected": "reject",
            "observed": "reject" if rejected else "accept",
            "status": "pass" if rejected else "fail",
        }
        for control_id, rejected in observations
    ]
    if any(item["status"] != "pass" for item in controls):
        raise QualificationError("one or more PooleBoot negative controls failed")
    return controls


def _normalized_command(profile: dict[str, Any]) -> list[str]:
    command = native_tier0.normalized_command(profile, "bootstrap-debug")
    command.extend(
        [
            "-device",
            "VGA,id=poole_gop",
            "-qmp",
            "tcp:127.0.0.1:$QMP_PORT,server=on,wait=off",
        ]
    )
    return command


def _make_legacy_report(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> tuple[dict[str, Any], bytes]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    tmp_root = ROOT / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    run_root = ROOT / "runs" / "native-tier0"
    run_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pooleboot-qualification-", dir=tmp_root) as temporary:
        temporary_root = Path(temporary)
        binary, build = _build_and_test(toolchain_root, temporary_root)
        media_first = native_pooleboot.build_media_bytes(binary)
        media_second = native_pooleboot.build_media_bytes(binary)
        if media_first != media_second:
            raise QualificationError("two PooleBoot proof-media generations are not byte-identical")
        media_inspection = native_pooleboot.inspect_media_bytes(media_first)
        media_path = temporary_root / "pooleboot-proof.img"
        media_path.write_bytes(media_first)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(prefix=f"pooleboot-run-{run_index}-", dir=run_root) as run_temporary:
                run, screenshot, _ = _execute_once(
                    f"run-{run_index}",
                    lock,
                    profile,
                    qemu_root,
                    media_path,
                    Path(run_temporary),
                    timeout,
                )
                runs.append(run)
                screenshots.append(screenshot)
    if runs[0]["markers"] != runs[1]["markers"]:
        raise QualificationError("two PooleBoot runs emitted different marker sequences")
    if screenshots[0] != screenshots[1]:
        raise QualificationError("two PooleBoot runs produced different GOP frame bytes")
    claims = native_pooleboot.expected_claims()
    native_pooleboot.validate_claims(claims)
    controls = _negative_controls(binary, media_first, runs[0]["markers"], screenshots[0], claims)
    required_controls = contract["required_negative_controls"]
    if [item["id"] for item in controls] != required_controls:
        raise QualificationError("negative-control order differs from the frozen PooleBoot contract")

    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    command = _normalized_command(profile)
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_pooleboot_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_unsigned_non_promoting",
        "contract_id": contract["contract_id"],
        "selected_move_id": contract["selected_move_id"],
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {
            "N5": "partial",
            "N5.1": "partial",
            "N5.2": "partial",
            "N5.3": "partial",
            "N5.7": "partial",
        },
        "bindings": {
            "contract": native_pooleboot.file_binding(ROOT, CONTRACT_RELATIVE),
            "toolchain_lock": native_pooleboot.file_binding(ROOT, "specs/native-toolchain-lock.json"),
            "toolchain_qualification": native_pooleboot.file_binding(
                ROOT, "runs/native_toolchain_qualification.json"
            ),
            "tier0_lock": native_pooleboot.file_binding(ROOT, native_tier0.LOCK_RELATIVE),
            "tier0_profile": native_pooleboot.file_binding(ROOT, native_tier0.PROFILE_RELATIVE),
            "tier0_readiness": native_pooleboot.file_binding(ROOT, native_tier0.READINESS_RELATIVE),
            "implementation_inputs": [native_pooleboot.file_binding(ROOT, path) for path in BUILD_INPUTS],
        },
        "build": build,
        "media": {
            "clean_generation_count": 2,
            "exact_clean_generation_match": True,
            "ordinary_workspace_file_only": True,
            "physical_media_write_performed": False,
            "inspection": media_inspection,
        },
        "execution": {
            "host_environment_count": 1,
            "run_count": 2,
            "profile_id": "bootstrap-debug",
            "machine": "pc-q35-11.0",
            "qemu_sha256": lock["windows_runner"]["qemu_system_x86_64"]["sha256"],
            "firmware_code_sha256": firmware["debug_code_read_only"]["sha256"],
            "vars_template_sha256": firmware["vars_template_copy_only"]["sha256"],
            "normalized_command": command,
            "normalized_command_sha256": native_pooleboot.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "local_paths_recorded": False,
            "runs": runs,
        },
        "negative_controls": controls,
        "claims": claims,
        "summary": {
            "host_contract_tests_passed": build["host_contract_test_pass_count"],
            "host_contract_tests_total": build["host_contract_test_count"],
            "clean_builds_exact": 2,
            "clean_media_generations_exact": 2,
            "guest_runs_passed": 2,
            "guest_runs_total": 2,
            "ordered_marker_count": len(runs[0]["markers"]),
            "serial_debugcon_match_count": 2,
            "gop_frame_match_count": 2,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "production_claim_count": 0,
        },
        "open_items": [
            "Complete boot configuration parsing, signed artifact verification, and hostile loader corpus coverage.",
            "Define and freeze ADD-BOOT-001 canonical handoff bytes before PooleKernel entry depends on them.",
            "Load and validate PooleKernel ELF64 plus initial-system and recovery bundles.",
            "Implement final memory-map retry, ExitBootServices, and a no-later-boot-service proof.",
            "Qualify target firmware and physical media only under separately approved lab procedures.",
            "Replace the non-promoting QEMU/OVMF candidates with source-built, provenance-complete inputs.",
            "Reproduce exact build, media, markers, and frame on a second clean host.",
            "Implement animated, static, reduced-motion, recovery, and software-rendered PooleGlass boot identities.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }
    encoded = json.dumps(report, ensure_ascii=True)
    if native_tier0.ABSOLUTE_USER_PATH.search(encoded):
        raise QualificationError("absolute user path leaked into the public PooleBoot readiness report")
    return report, screenshots[0]


def make_report(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> tuple[dict[str, Any], bytes]:
    from runtime import native_kernel_load
    from tools import qualify_native_kernel_load

    contract = native_pooleboot.read_json(CONTRACT_PATH)
    contract_errors = native_pooleboot.proof_contract_errors(contract, ROOT)
    if contract_errors:
        raise QualificationError("; ".join(contract_errors))
    kernel_load_readiness_path = ROOT / native_kernel_load.READINESS_RELATIVE
    if not kernel_load_readiness_path.is_file():
        raise QualificationError(
            "current PKLOAD6 readiness is required before the aggregate PooleBoot receipt"
        )
    current_kernel_load = native_kernel_load.read_json(kernel_load_readiness_path)
    current_errors = native_kernel_load.readiness_errors(current_kernel_load, ROOT)
    if current_errors:
        raise QualificationError("current PKLOAD6 readiness is stale: " + "; ".join(current_errors))
    kernel_load, screenshot = qualify_native_kernel_load.make_readiness(
        toolchain_root,
        qemu_root,
        status_date,
        timeout,
    )
    claims = native_pooleboot.expected_claims()
    native_pooleboot.validate_claims(claims)
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_pooleboot_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_unsigned_live_profile_artifacts_post_exit_pbp1_retained_pkmap2_stop_before_transfer_non_promoting",
        "contract_id": contract["contract_id"],
        "selected_move_id": contract["selected_move_id"],
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {
            "N5": "partial",
            "N5.1": "partial",
            "N5.2": "partial",
            "N5.3": "partial",
            "N5.4": "partial",
            "N5.5": "partial",
            "N5.6": "partial",
            "N5.7": "partial",
            "N5.8": "partial",
            "N5.9": "partial",
        },
        "bindings": {
            "contract": native_pooleboot.file_binding(ROOT, CONTRACT_RELATIVE),
            "toolchain_lock": native_pooleboot.file_binding(
                ROOT, "specs/native-toolchain-lock.json"
            ),
            "toolchain_qualification": native_pooleboot.file_binding(
                ROOT, "runs/native_toolchain_qualification.json"
            ),
            "tier0_lock": native_pooleboot.file_binding(ROOT, native_tier0.LOCK_RELATIVE),
            "tier0_profile": native_pooleboot.file_binding(
                ROOT, native_tier0.PROFILE_RELATIVE
            ),
            "tier0_readiness": native_pooleboot.file_binding(
                ROOT, native_tier0.READINESS_RELATIVE
            ),
            "kernel_entry_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_kernel_entry_readiness.json"
            ),
            "kernel_load_contract": native_pooleboot.file_binding(
                ROOT, native_kernel_load.CONTRACT_RELATIVE
            ),
            "kernel_load_readiness": native_pooleboot.file_binding(
                ROOT, native_kernel_load.READINESS_RELATIVE
            ),
            "system_manifest_contract": native_pooleboot.file_binding(
                ROOT, "specs/native-system-manifest-contract.json"
            ),
            "system_manifest_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_system_manifest_readiness.json"
            ),
            "initial_system_contract": native_pooleboot.file_binding(
                ROOT, "specs/native-initial-system-contract.json"
            ),
            "initial_system_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_initial_system_readiness.json"
            ),
            "recovery_contract": native_pooleboot.file_binding(
                ROOT, "specs/native-recovery-contract.json"
            ),
            "recovery_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_recovery_readiness.json"
            ),
            "symbols_contract": native_pooleboot.file_binding(
                ROOT, "specs/native-symbol-contract.json"
            ),
            "symbols_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_symbol_readiness.json"
            ),
            "microcode_contract": native_pooleboot.file_binding(
                ROOT, "specs/native-microcode-contract.json"
            ),
            "microcode_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_microcode_readiness.json"
            ),
            "firmware_contract": native_pooleboot.file_binding(
                ROOT, "specs/native-firmware-contract.json"
            ),
            "firmware_readiness": native_pooleboot.file_binding(
                ROOT, "runs/native_firmware_readiness.json"
            ),
            "implementation_inputs": [
                native_pooleboot.file_binding(ROOT, path) for path in BUILD_INPUTS
            ],
        },
        "build": kernel_load["build"],
        "media": kernel_load["media"],
        "execution": kernel_load["execution"],
        "negative_controls": kernel_load["negative_controls"],
        "claims": claims,
        "summary": {
            "host_contract_tests_passed": kernel_load["build"][
                "host_contract_test_pass_count"
            ],
            "host_contract_tests_total": kernel_load["build"]["host_contract_test_count"],
            "clean_builds_exact": 2,
            "clean_media_generations_exact": 2,
            "guest_runs_passed": 2,
            "guest_runs_total": 2,
            "ordered_marker_count": len(kernel_load["execution"]["runs"][0]["markers"]),
            "serial_debugcon_match_count": 2,
            "gop_frame_match_count": 2,
            "negative_controls_passed": len(kernel_load["negative_controls"]),
            "negative_controls_total": len(kernel_load["negative_controls"]),
            "microcode_patch_count": kernel_load["media"]["inspection"]["microcode"][
                "patch_count"
            ],
            "microcode_payload_profile": "synthetic_test_only_never_apply",
            "firmware_component_count": kernel_load["media"]["inspection"]["firmware"][
                "component_count"
            ],
            "firmware_dependency_count": kernel_load["media"]["inspection"]["firmware"][
                "dependency_count"
            ],
            "firmware_manifest_profile": "synthetic_qualification_never_apply",
            "production_claim_count": 0,
        },
        "open_items": kernel_load["open_items"],
        "claim_boundary": contract["claim_boundary"],
    }
    errors = native_pooleboot.readiness_contract_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report, screenshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--screenshot-out", type=Path)
    parser.add_argument("--status-date", default="2026-07-18")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    if args.timeout < 5 or args.timeout > 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report, screenshot = make_report(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(native_pooleboot.canonical_json_bytes(report))
        if args.screenshot_out:
            args.screenshot_out.parent.mkdir(parents=True, exist_ok=True)
            args.screenshot_out.write_bytes(screenshot)
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        socket.timeout,
        subprocess.TimeoutExpired,
        QualificationError,
        native_pooleboot.PooleBootError,
        native_tier0.Tier0Error,
    ) as error:
        print(f"NATIVE_POOLEBOOT_QUALIFICATION FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "NATIVE_POOLEBOOT_QUALIFICATION PASS "
        f"host_tests={summary['host_contract_tests_passed']}/{summary['host_contract_tests_total']} "
        f"builds={summary['clean_builds_exact']} media={summary['clean_media_generations_exact']} "
        f"runs={summary['guest_runs_passed']}/{summary['guest_runs_total']} "
        f"markers={summary['ordered_marker_count']} controls={summary['negative_controls_passed']}/"
        f"{summary['negative_controls_total']} exit_called=true n5_gate=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
