#!/usr/bin/env python3
"""Qualify live PKLOAD1 UEFI file intake, relocation, mapping, and cleanup."""

from __future__ import annotations

import argparse
import copy
import json
import re
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_kernel_load, native_pooleboot, native_tier0  # noqa: E402
from tools import qualify_native_kernel_entry, qualify_native_pooleboot  # noqa: E402


DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "rust-1.97.0"
DEFAULT_QEMU_ROOT = native_tier0.DEFAULT_QEMU_ROOT
DEFAULT_OUT = ROOT / native_kernel_load.READINESS_RELATIVE
NATIVE_ROOT = ROOT / "native"


class QualificationError(RuntimeError):
    """Raised when the PKLOAD1 qualification fails closed."""


def _host_checks(toolchain_root: Path, temporary_root: Path) -> dict[str, Any]:
    cargo, _, environment = qualify_native_pooleboot._toolchain(toolchain_root)
    output = qualify_native_pooleboot._run_checked(
        [
            str(cargo),
            "test",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            "poole-bootload",
            "--target",
            "x86_64-pc-windows-msvc",
            "--locked",
            "--offline",
            "--target-dir",
            str(temporary_root / "bootload-tests"),
            "--",
            "--test-threads=1",
        ],
        cwd=NATIVE_ROOT,
        env=environment,
    )
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", output)
    if match is None or int(match.group(1)) < 12:
        raise QualificationError("expected at least twelve poole-bootload host tests")
    bootload_tests = int(match.group(1))
    for package in ("poole-bootload", "pooleboot"):
        qualify_native_pooleboot._run_checked(
            [
                str(cargo),
                "fmt",
                "--manifest-path",
                str(NATIVE_ROOT / "Cargo.toml"),
                "--package",
                package,
                "--",
                "--check",
            ],
            cwd=NATIVE_ROOT,
            env=environment,
        )
    clippy_profiles = (
        ("poole-bootload", "--lib", "x86_64-pc-windows-msvc", "clippy-bootload-host"),
        ("poole-bootload", "--lib", "x86_64-unknown-uefi", "clippy-bootload-uefi"),
        ("pooleboot", "--bin", "x86_64-unknown-uefi", "clippy-pooleboot-uefi"),
    )
    for package, kind, target, target_dir in clippy_profiles:
        command = [
            str(cargo),
            "clippy",
            "--manifest-path",
            str(NATIVE_ROOT / "Cargo.toml"),
            "--package",
            package,
            kind,
        ]
        if kind == "--bin":
            command.append("PooleBoot")
        command.extend(
            [
                "--target",
                target,
                "--release",
                "--locked",
                "--offline",
                "--target-dir",
                str(temporary_root / target_dir),
                "--",
                "-D",
                "warnings",
            ]
        )
        qualify_native_pooleboot._run_checked(
            command,
            cwd=NATIVE_ROOT,
            env=environment,
        )
    return {
        "bootload_tests_passed": bootload_tests,
        "bootload_tests_total": bootload_tests,
        "rustfmt_passed": True,
        "rustfmt_packages": ["poole-bootload", "pooleboot"],
        "clippy_passed": True,
        "clippy_run_count": len(clippy_profiles),
    }


def _rejected(action: Callable[[], object]) -> bool:
    try:
        action()
    except (ValueError, RuntimeError, KeyError, IndexError, struct.error):
        return True
    return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationError(message)


def _mutate(data: bytes, offset: int, value: int) -> bytes:
    changed = bytearray(data)
    changed[offset] = value
    return bytes(changed)


def _set_u32(data: bytes, offset: int, value: int) -> bytes:
    changed = bytearray(data)
    struct.pack_into("<I", changed, offset, value)
    return bytes(changed)


def _set_fat_entry_both(data: bytes, cluster: int, value: int) -> bytes:
    changed = bytearray(data)
    fat_sectors, _ = native_pooleboot._fat_sector_count()
    fat_bytes = fat_sectors * native_pooleboot.SECTOR_BYTES
    first = (
        native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
    ) * native_pooleboot.SECTOR_BYTES
    for copy_index in range(native_pooleboot.FAT_COUNT):
        struct.pack_into("<I", changed, first + copy_index * fat_bytes + cluster * 4, value)
    return bytes(changed)


def _replace_marker(markers: list[str], index: int, old: str, new: str) -> list[str]:
    changed = markers[:]
    if old not in changed[index]:
        raise QualificationError(f"marker mutation source is absent: {old}")
    changed[index] = changed[index].replace(old, new, 1)
    return changed


def _negative_controls(
    media: bytes,
    inspection: dict[str, Any],
    markers: list[str],
    claims: dict[str, bool],
) -> list[dict[str, str]]:
    fat_sectors, _ = native_pooleboot._fat_sector_count()
    data_start_lba = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + native_pooleboot.FAT_COUNT * fat_sectors
    )
    cluster_bytes = native_pooleboot.SECTOR_BYTES * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    efi_clusters = inspection["files"][0]["cluster_count"]
    pooleos_cluster = 5 + efi_clusters
    config_cluster = pooleos_cluster + 1
    kernel_cluster = config_cluster + inspection["files"][1]["cluster_count"]
    efi_directory_offset = (
        data_start_lba + (3 - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    pooleos_directory_offset = (
        data_start_lba + (pooleos_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    config_offset = (
        data_start_lba + (config_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    kernel_offset = (
        data_start_lba + (kernel_cluster - 2) * native_pooleboot.FAT_SECTORS_PER_CLUSTER
    ) * native_pooleboot.SECTOR_BYTES
    if cluster_bytes != 512:
        raise QualificationError("negative controls assume the frozen one-sector cluster profile")

    expected_config_hash = inspection["files"][1]["sha256"]
    expected_kernel_hash = inspection["files"][2]["sha256"]

    def inspect_expected(candidate: bytes) -> dict[str, Any]:
        observed = native_kernel_load.inspect_media_bytes(candidate)
        if (
            observed["files"][1]["sha256"] != expected_config_hash
            or observed["files"][2]["sha256"] != expected_kernel_hash
        ):
            raise native_kernel_load.KernelLoadError("qualified product binding changed")
        return observed

    config_missing = _mutate(media, pooleos_directory_offset + 64, 0)
    config_empty = _set_u32(media, pooleos_directory_offset + 64 + 28, 0)
    config_oversize = _set_u32(
        media,
        pooleos_directory_offset + 64 + 28,
        native_kernel_load.native_boot_config.MAX_CONFIG_BYTES + 1,
    )
    config_malformed = _mutate(media, config_offset, ord("X"))
    kernel_missing = _mutate(media, pooleos_directory_offset + 96, 0)
    kernel_empty = _set_u32(media, pooleos_directory_offset + 96 + 28, 0)
    kernel_oversize = _set_u32(
        media,
        pooleos_directory_offset + 96 + 28,
        native_kernel_load.native_elf_loader.MAX_FILE_BYTES + 1,
    )
    kernel_malformed = _mutate(media, kernel_offset, 0)
    fat_copy = bytearray(media)
    second_fat = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + fat_sectors
    ) * native_pooleboot.SECTOR_BYTES
    fat_copy[second_fat + config_cluster * 4] ^= 1
    fat_loop = _set_fat_entry_both(media, config_cluster, config_cluster)
    directory_path = _mutate(media, efi_directory_offset + 96, ord("X"))
    config_path = _mutate(media, pooleos_directory_offset + 64, ord("X"))
    kernel_path = _mutate(media, pooleos_directory_offset + 96, ord("X"))
    config_content = bytearray(media)
    timeout = config_content.find(b"timeout_ms=0", config_offset, config_offset + cluster_bytes)
    if timeout < 0:
        raise QualificationError("canonical timeout field is absent")
    config_content[timeout + len("timeout_ms=")] = ord("1")
    kernel_content = bytearray(media)
    kernel_content[kernel_offset + 0x1000] ^= 1

    marker_summary = native_kernel_load.validate_markers(markers)
    config_oracle = copy.deepcopy(inspection)
    config_oracle["config"]["timeout_ms"] += 1
    elf_oracle = copy.deepcopy(inspection)
    elf_oracle["kernel"]["plan"]["image_size"] += native_pooleboot.SECTOR_BYTES
    hash_oracle = copy.deepcopy(inspection)
    hash_oracle["kernel"]["loaded_fnv1a64"] = "0" * 16
    overreach = dict(claims)
    overreach["kernel_entry_called"] = True
    stale_binding = native_kernel_load.file_binding(ROOT, native_kernel_load.CONTRACT_RELATIVE)
    stale_binding["sha256"] = "0" * 64

    observations = [
        ("NEG-N5-KLOAD-CONFIG-MISSING", _rejected(lambda: inspect_expected(config_missing))),
        ("NEG-N5-KLOAD-CONFIG-EMPTY", _rejected(lambda: inspect_expected(config_empty))),
        ("NEG-N5-KLOAD-CONFIG-OVERSIZE", _rejected(lambda: inspect_expected(config_oversize))),
        ("NEG-N5-KLOAD-CONFIG-MALFORMED", _rejected(lambda: inspect_expected(config_malformed))),
        ("NEG-N5-KLOAD-KERNEL-MISSING", _rejected(lambda: inspect_expected(kernel_missing))),
        ("NEG-N5-KLOAD-KERNEL-EMPTY", _rejected(lambda: inspect_expected(kernel_empty))),
        ("NEG-N5-KLOAD-KERNEL-OVERSIZE", _rejected(lambda: inspect_expected(kernel_oversize))),
        ("NEG-N5-KLOAD-KERNEL-MALFORMED", _rejected(lambda: inspect_expected(kernel_malformed))),
        ("NEG-N5-KLOAD-FAT-COPY", _rejected(lambda: inspect_expected(bytes(fat_copy)))),
        ("NEG-N5-KLOAD-FAT-CHAIN-LOOP", _rejected(lambda: inspect_expected(fat_loop))),
        ("NEG-N5-KLOAD-DIRECTORY-PATH", _rejected(lambda: inspect_expected(directory_path))),
        ("NEG-N5-KLOAD-CONFIG-PATH", _rejected(lambda: inspect_expected(config_path))),
        ("NEG-N5-KLOAD-KERNEL-PATH", _rejected(lambda: inspect_expected(kernel_path))),
        ("NEG-N5-KLOAD-CONFIG-CONTENT", _rejected(lambda: inspect_expected(bytes(config_content)))),
        ("NEG-N5-KLOAD-KERNEL-CONTENT", _rejected(lambda: inspect_expected(bytes(kernel_content)))),
        ("NEG-N5-KLOAD-MARKER-OMISSION", _rejected(lambda: native_kernel_load.validate_markers(markers[:-1]))),
        ("NEG-N5-KLOAD-MARKER-ORDER", _rejected(lambda: native_kernel_load.validate_markers([markers[1], markers[0], *markers[2:]]))),
        ("NEG-N5-KLOAD-MARKER-CONFIG-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 7, "bytes=231", "bytes=16385")))),
        ("NEG-N5-KLOAD-MARKER-KERNEL-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 8, "bytes=139264", "bytes=1048577")))),
        ("NEG-N5-KLOAD-MARKER-PAGE-MATH", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 9, "pages=48", "pages=49")))),
        ("NEG-N5-KLOAD-MARKER-ENTRY-BOUND", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 9, "entry_offset=16384", "entry_offset=196608")))),
        ("NEG-N5-KLOAD-MARKER-MAPPING-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 10, "mappings=4", "mappings=3")))),
        ("NEG-N5-KLOAD-MARKER-WX", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 10, "wx=0", "wx=1")))),
        ("NEG-N5-KLOAD-MARKER-RELEASE-COUNT", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 11, "files_closed=3", "files_closed=2")))),
        ("NEG-N5-KLOAD-MARKER-BOUNDARY", _rejected(lambda: native_kernel_load.validate_markers(_replace_marker(markers, 14, "selection=fixed_untrusted", "selection=trusted")))),
        ("NEG-N5-KLOAD-CONFIG-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, config_oracle))),
        ("NEG-N5-KLOAD-ELF-ORACLE-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, elf_oracle))),
        ("NEG-N5-KLOAD-LOADED-HASH-DIVERGENCE", _rejected(lambda: native_kernel_load.validate_oracle_binding(marker_summary, hash_oracle))),
        ("NEG-N5-KLOAD-CLAIM-OVERREACH", _rejected(lambda: native_kernel_load.validate_claims(overreach))),
        ("NEG-N5-KLOAD-STALE-BINDING", _rejected(lambda: _require(native_kernel_load.binding_matches(stale_binding, ROOT, native_kernel_load.CONTRACT_RELATIVE), "stale binding accepted"))),
    ]
    controls = [
        {
            "id": control_id,
            "expected": "reject",
            "observed": "reject" if rejected else "accept",
            "status": "pass" if rejected else "fail",
        }
        for control_id, rejected in observations
    ]
    if [item["id"] for item in controls] != list(native_kernel_load.NEGATIVE_CONTROL_IDS):
        raise QualificationError("PKLOAD1 negative-control order changed")
    if any(item["status"] != "pass" for item in controls):
        failed = [item["id"] for item in controls if item["status"] != "pass"]
        raise QualificationError("PKLOAD1 negative controls failed: " + ", ".join(failed))
    return controls


def make_readiness(
    toolchain_root: Path,
    qemu_root: Path,
    status_date: str,
    timeout: int,
) -> tuple[dict[str, Any], bytes]:
    contract = native_kernel_load.read_json(ROOT / native_kernel_load.CONTRACT_RELATIVE)
    contract_failures = native_kernel_load.contract_errors(contract, ROOT)
    if contract_failures:
        raise QualificationError("; ".join(contract_failures))
    lock, profile = native_tier0.validate_contracts(ROOT)
    qemu_root = native_tier0._require_workspace_tool_path(qemu_root, ROOT)
    native_tier0.verify_local_launch_runtime(lock, qemu_root, ROOT)
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "native-tier0").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pkload1-qualification-", dir=ROOT / "tmp") as temporary:
        temporary_root = Path(temporary)
        host_tests = _host_checks(toolchain_root, temporary_root)
        binary, build = qualify_native_pooleboot._build_and_test(toolchain_root, temporary_root)
        kernel_readiness, kernel = qualify_native_kernel_entry.make_readiness(toolchain_root)
        host_tests.update(
            {
                "pooleboot_tests_passed": build["host_contract_test_pass_count"],
                "pooleboot_tests_total": build["host_contract_test_count"],
                "kernel_entry_tests_passed": kernel_readiness["host_tests"]["test_pass_count"],
                "kernel_entry_tests_total": kernel_readiness["host_tests"]["test_count"],
            }
        )
        config = native_kernel_load.canonical_config_bytes()
        media_first = native_kernel_load.build_media_bytes(binary, config, kernel)
        media_second = native_kernel_load.build_media_bytes(binary, config, kernel)
        if media_first != media_second:
            raise QualificationError("two PKLOAD1 media generations differ")
        media_inspection = native_kernel_load.inspect_media_bytes(media_first)
        if media_inspection["files"][2]["sha256"] != kernel_readiness["product"]["canonical_sha256"]:
            raise QualificationError("PKLOAD1 media kernel differs from the fresh PKENTRY1 product")
        media_path = temporary_root / "pkload1.img"
        media_path.write_bytes(media_first)

        runs: list[dict[str, Any]] = []
        screenshots: list[bytes] = []
        for run_index in (1, 2):
            with tempfile.TemporaryDirectory(
                prefix=f"pkload1-run-{run_index}-",
                dir=ROOT / "runs" / "native-tier0",
            ) as run_temporary:
                run, screenshot = qualify_native_pooleboot._execute_once(
                    f"run-{run_index}",
                    lock,
                    profile,
                    qemu_root,
                    media_path,
                    Path(run_temporary),
                    timeout,
                    native_kernel_load.validate_markers,
                )
                native_kernel_load.validate_oracle_binding(run["marker_summary"], media_inspection)
                runs.append(run)
                screenshots.append(screenshot)
    if runs[0]["markers"] != runs[1]["markers"]:
        raise QualificationError("two PKLOAD1 marker sequences differ")
    if screenshots[0] != screenshots[1]:
        raise QualificationError("two PKLOAD1 screenshots differ")

    claims = native_kernel_load.expected_claims()
    native_kernel_load.validate_claims(claims)
    controls = _negative_controls(media_first, media_inspection, runs[0]["markers"], claims)
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    command = qualify_native_pooleboot._normalized_command(profile)
    kernel_summary = runs[0]["marker_summary"]["kernel"]
    report = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_kernel_load_readiness",
        "status_date": status_date,
        "status": "pass_single_host_two_run_live_load_then_release_non_promoting",
        "contract_id": native_kernel_load.CONTRACT_ID,
        "selected_move_id": "N5-KLOAD-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "n5_exit_gate_satisfied": False,
        "phase_status": {"N5": "partial", "N5.1": "partial", "N5.4": "partial", "N5.5": "partial"},
        "bindings": {
            "contract": native_kernel_load.file_binding(ROOT, native_kernel_load.CONTRACT_RELATIVE),
            "toolchain_lock": native_kernel_load.file_binding(ROOT, "specs/native-toolchain-lock.json"),
            "toolchain_qualification": native_kernel_load.file_binding(ROOT, "runs/native_toolchain_qualification.json"),
            "tier0_lock": native_kernel_load.file_binding(ROOT, native_tier0.LOCK_RELATIVE),
            "tier0_profile": native_kernel_load.file_binding(ROOT, native_tier0.PROFILE_RELATIVE),
            "tier0_readiness": native_kernel_load.file_binding(ROOT, native_tier0.READINESS_RELATIVE),
            "kernel_entry_contract": native_kernel_load.file_binding(ROOT, "specs/native-kernel-entry-contract.json"),
            "kernel_entry_readiness": native_kernel_load.file_binding(ROOT, "runs/native_kernel_entry_readiness.json"),
            "implementation_inputs": [native_kernel_load.file_binding(ROOT, path) for path in native_kernel_load.IMPLEMENTATION_INPUTS],
        },
        "host_tests": host_tests,
        "build": build,
        "kernel_product": kernel_readiness["product"],
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
            "normalized_command_sha256": native_kernel_load.sha256_bytes(
                native_pooleboot.canonical_json_bytes(command)
            ),
            "exact_marker_match": True,
            "exact_screenshot_match": True,
            "local_paths_recorded": False,
            "runs": runs,
        },
        "oracle": {
            "pbc1_python_match": True,
            "pkelf1_python_plan_match": True,
            "loaded_fnv1a64_match": True,
            "media_reconstruction_exact": True,
        },
        "cleanup": {
            "file_handles_closed": 3,
            "pools_freed": 2,
            "pages_freed": True,
            "page_count": kernel_summary["page_count"],
            "all_resources_released": True,
        },
        "negative_controls": controls,
        "claims": claims,
        "summary": {
            "rust_host_tests_passed": host_tests["bootload_tests_passed"] + host_tests["pooleboot_tests_passed"] + host_tests["kernel_entry_tests_passed"],
            "rust_host_tests_total": host_tests["bootload_tests_total"] + host_tests["pooleboot_tests_total"] + host_tests["kernel_entry_tests_total"],
            "clean_pooleboot_builds_exact": 2,
            "clean_kernel_builds_exact": 2,
            "clean_media_generations_exact": 2,
            "guest_runs_passed": 2,
            "guest_runs_total": 2,
            "ordered_marker_count": len(runs[0]["markers"]),
            "serial_debugcon_match_count": 2,
            "gop_frame_match_count": 2,
            "oracle_match_count": 2,
            "negative_controls_passed": len(controls),
            "negative_controls_total": len(controls),
            "production_claim_count": 0,
        },
        "open_items": [
            "Replace the fixed development kernel path with manifest-driven trusted selection.",
            "Define and implement signed manifest and kernel authentication with revocation policy.",
            "Retain allocated kernel pages and install the exact r, rx, r, and rw page-table permissions.",
            "Load and authenticate the initial-system, recovery, policy, symbols, and optional microcode artifacts.",
            "Populate an immutable live PBP1 handoff from normalized firmware observations.",
            "Implement the final memory-map retry and prove no boot-service call after ExitBootServices.",
            "Transfer to PooleKernel and capture entry, panic, recovery, and reset evidence.",
            "Qualify hostile firmware behavior, target firmware, physical hardware, and a second clean builder.",
            "Complete Secure Boot, measured boot, TPM policy, signing, ISO, installer, and recovery gates.",
        ],
        "claim_boundary": contract["claim_boundary"],
    }
    errors = native_kernel_load.readiness_errors(report, ROOT)
    if errors:
        raise QualificationError("; ".join(errors))
    return report, screenshots[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--qemu-root", type=Path, default=DEFAULT_QEMU_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--screenshot-out", type=Path)
    parser.add_argument("--status-date", default="2026-07-16")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    if args.timeout < 5 or args.timeout > 120:
        parser.error("--timeout must be between 5 and 120 seconds")
    try:
        report, screenshot = make_readiness(
            args.toolchain_root.resolve(),
            args.qemu_root.resolve(),
            args.status_date,
            args.timeout,
        )
        output = args.out.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
        if args.screenshot_out is not None:
            screenshot_output = args.screenshot_out.resolve()
            screenshot_output.parent.mkdir(parents=True, exist_ok=True)
            screenshot_output.write_bytes(screenshot)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"PKLOAD1 FAIL {type(error).__name__}: {error}")
        return 1
    summary = report["summary"]
    print(
        "PKLOAD1 PASS "
        f"tests={summary['rust_host_tests_passed']}/{summary['rust_host_tests_total']} "
        f"runs={summary['guest_runs_passed']}/{summary['guest_runs_total']} "
        f"markers={summary['ordered_marker_count']} "
        f"controls={summary['negative_controls_passed']}/{summary['negative_controls_total']} "
        "transfer=false n5_exit=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
