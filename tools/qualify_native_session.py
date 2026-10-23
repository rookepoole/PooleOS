#!/usr/bin/env python3
"""Build and observe the opt-in native user-program session, never a release ISO."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_session as session, native_kernel_load as load, native_kernel_transfer as transfer, native_tier0 as tier0
from tools import qualify_native_kernel_entry as entry, qualify_native_pooleboot as boot, qualify_native_user_entry as user
from tools.qualify_native_elf_loader import _toolchain


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sources() -> dict[str, str]:
    result = user.source_bindings()
    for path in ("native/kernel/src/user_root_probe/peer_driver/session.rs",
                 "native/kernel/src/user_entry/timer/calibration.rs",
                 "tests/test_native_session.py", "runtime/native_session.py",
                 "tools/qualify_native_session.py", "specs/native-tier0-lock.json",
                 "specs/native-tier0-profile.json", "runtime/native_tier0.py"):
        result[path] = sha((ROOT / path).read_bytes())
    return dict(sorted(result.items()))


def program_inputs(directory: Path, env: dict[str, str]) -> dict:
    receipt = json.loads((directory / "receipt.json").read_bytes())
    if receipt["status"] != "pass" or not receipt["direct_byte_equality"] or not receipt["source_unchanged"]:
        raise ValueError("independent user-program qualification did not pass")
    for path, digest in receipt["source_bindings"].items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError(f"user-program source drift: {path}")
    for name, key in (("PooleInit", "POOLEOS_INIT_CODE"), ("PooleCounter", "POOLEOS_COUNTER_CODE")):
        first = directory / f"build1-{name}.bin"
        second = directory / f"build2-{name}.bin"
        data = first.read_bytes()
        if data != second.read_bytes() or sha(data) != receipt["programs"][name]["code_sha256"]:
            raise ValueError("compiled program bytes changed")
        env[key] = str(first.resolve())
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--program-dir", type=Path, required=True)
    args = parser.parse_args()
    work, programs = args.work_dir.resolve(), args.program_dir.resolve()
    if not work.is_relative_to(ROOT) or not programs.is_relative_to(ROOT):
        parser.error("work/program directories must be within the repository")
    work.mkdir(parents=True, exist_ok=False)
    before = sources()
    report = dict(cycle=261, contract_id="PSESSION1", status="fail", source_bindings=before,
                  guest_runs=[], normal_session_execution=False, user_console=False,
                  init_supervision=False, iso_built=False, production_ready=False)
    try:
        cargo, _, env = _toolchain(ROOT / ".toolchains/rust-1.97.0")
        report["program_build"] = program_inputs(programs, env)
        lock, profile = tier0.validate_contracts(ROOT)
        qemu = tier0._require_workspace_tool_path(tier0.DEFAULT_QEMU_ROOT, ROOT)
        tier0.verify_local_launch_runtime(lock, qemu, ROOT)
        print("Build two session kernels and a bad-role control", flush=True)
        linked, kernel, plan = entry._build_product(cargo, env, work / "kernel1", features=("development-session",))
        linked2, kernel2, _ = entry._build_product(cargo, env, work / "kernel2", features=("development-session",))
        if kernel != kernel2 or linked != linked2:
            raise ValueError("session kernel builds differ")
        bad_linked, bad, bad_plan = entry._build_product(cargo, env, work / "bad-kernel", features=("development-session-bad-startup",))
        if bad == kernel:
            raise ValueError("bad-startup control is not distinct")
        report["kernels"] = {}
        for name, image, link, layout in (("session", kernel, linked, plan), ("bad-startup", bad, bad_linked, bad_plan)):
            (work / f"{name}.elf").write_bytes(image)
            if image.count(Path(env["POOLEOS_INIT_CODE"]).read_bytes()) != 1 or image.count(Path(env["POOLEOS_COUNTER_CODE"]).read_bytes()) != 1:
                raise ValueError("exact independent programs not embedded once in kernel")
            report["kernels"][name] = dict(sha256=sha(image), linked_sha256=sha(link),
                bytes=len(image), image_pages=layout.image_byte_count // 4096)
        report["independent_kernel_builds_equal"] = True
        toolchain = ROOT / ".toolchains/rust-1.97.0"
        default, default_build = boot._build_and_test(toolchain, work / "default")
        development, dev_build = boot._build_and_test(toolchain, work / "development", development_feature="development-user-root")
        if default == development or b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default:
            raise ValueError("ordinary boot lost its unsigned denial")
        report["boot_builds"] = dict(default=default_build, development=dev_build)
        files, config = load.canonical_artifact_files(), load.canonical_config_bytes()
        for name, image, bad_startup in (("session-1", kernel, False), ("session-2", kernel, False), ("bad-startup", bad, True)):
            manifest = load.canonical_manifest_bytes(image, files)
            retained = transfer.canonical_retained_files(manifest, image, files)
            media = load.build_media_bytes(development, config, manifest, image, files)
            if media != load.build_media_bytes(development, config, manifest, image, files):
                raise ValueError("session media not deterministic")
            inspected = load.inspect_media_bytes(media)
            path = work / f"{name}.img"
            path.write_bytes(media)
            run_dir = work / name
            run_dir.mkdir()
            print(f"Native {name}:120-second bound", flush=True)
            run, _, handoff = boot._execute_once(name, lock, profile, qemu, path, run_dir, 120,
                marker_validator=lambda markers: session.validate_markers(markers, bad_startup=bad_startup),
                marker_extractor=session.extract_markers,
                completion_marker=session.EMPTY.encode() if bad_startup else session.COMPLETION,
                hpet_msi=True, pause_on_completion=True)
            summary = run["marker_summary"]
            expected_sizes = [report["program_build"]["programs"][n]["code_bytes"] for n in ("PooleInit", "PooleCounter")]
            if summary["program_bytes"] != expected_sizes:
                raise ValueError("live program sizes differ from exact compiled inputs")
            prefix = summary["transfer_prefix"]
            load.validate_oracle_binding(prefix["boot_prefix"], inspected, run["pbp1_transcript"])
            run["transcript_binding"] = transfer.validate_transcript_binding(prefix, run["pbp1_transcript"])
            run["independent_revalidation"] = transfer.validate_revalidation_binding(prefix, handoff, retained)
            run["hostile_marker_cases_rejected"] = session.negative_controls(run["markers"], bad_startup=bad_startup)
            run["media_sha256"] = sha(media)
            run["kernel_sha256"] = sha(image)
            report["guest_runs"].append(run)
        manifest = load.canonical_manifest_bytes(kernel, files)
        media = load.build_media_bytes(default, config, manifest, kernel, files)
        path = work / "ordinary-denial.img"
        path.write_bytes(media)
        run_dir = work / "ordinary-denial"
        run_dir.mkdir()
        print("Native ordinary unsigned-boot denial:45-second bound", flush=True)
        run, _, _ = boot._execute_once("ordinary-denial", lock, profile, qemu, path, run_dir, 45,
            marker_validator=load.validate_markers, marker_extractor=session.extract_markers, hpet_msi=True)
        load.validate_oracle_binding(run["marker_summary"], load.inspect_media_bytes(media), run["pbp1_transcript"])
        report["ordinary_denial"] = run
        if before != sources():
            raise ValueError("source drift during session capture")
        program_inputs(programs, env)
        report.update(status="pass", normal_session_execution=True)
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        print(report["failure"], flush=True)
    report["source_unchanged"] = before == sources()
    (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PSESSION1 {report['status']}; ISO=0 production=0", flush=True)
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
