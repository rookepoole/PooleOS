#!/usr/bin/env python3
"""Build exact development media and run two PKUSER6 probes plus ordinary denial."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_user_root as probe, native_kernel_load as load, native_kernel_transfer as transfer, native_tier0 as tier0
from tools import qualify_native_kernel_entry as entry, qualify_native_pooleboot as boot
from tools.qualify_native_elf_loader import _toolchain


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", type=Path, required=True)
    args = p.parse_args()
    work = args.work_dir.resolve()
    if not work.is_relative_to(ROOT): p.error("work directory must be inside repository")
    work.mkdir(parents=True, exist_ok=False)
    report = {"cycle": 240, "contract_id": "PKUSER6", "status": "fail", "guest_runs": [],
              "ring3_executed": False, "iso_built": False, "production_ready": False}
    try:
        lock, profile = tier0.validate_contracts(ROOT)
        qemu = tier0._require_workspace_tool_path(tier0.DEFAULT_QEMU_ROOT, ROOT)
        tier0.verify_local_launch_runtime(lock, qemu, ROOT)
        toolchain = ROOT / ".toolchains/rust-1.97.0"
        cargo, _, env = _toolchain(toolchain)
        print("Building exact kernel and default/development PooleBoot", flush=True)
        linked, kernel, plan = entry._build_product(cargo, env, work / "kernel")
        (work / "kernel.elf").write_bytes(kernel)
        report["kernel"] = {"linked_sha256": hashlib.sha256(linked).hexdigest().upper(),
            "sha256": hashlib.sha256(kernel).hexdigest().upper(), "bytes": len(kernel),
            "image_pages": plan.image_byte_count // 4096}
        default, default_build = boot._build_and_test(toolchain, work / "default")
        development, dev_build = boot._build_and_test(toolchain, work / "development", development_feature=probe.FEATURE)
        if default == development or b"POOLEBOOT/0.1 TRANSFER_ARM PASS" in default:
            raise ValueError("default/development boundary not distinct")
        report["boot_builds"] = {"default": default_build, "development": dev_build}
        files = load.canonical_artifact_files()
        config = load.canonical_config_bytes()
        manifest = load.canonical_manifest_bytes(kernel, files)
        retained = transfer.canonical_retained_files(manifest, kernel, files)
        media = load.build_media_bytes(development, config, manifest, kernel, files)
        if media != load.build_media_bytes(development, config, manifest, kernel, files):
            raise ValueError("development media nondeterministic")
        inspected = load.inspect_media_bytes(media)
        media_path = work / "user-root.img"
        media_path.write_bytes(media)
        report["media_sha256"] = hashlib.sha256(media).hexdigest().upper()
        for i in (1, 2):
            run_dir = work / f"guest-{i}"
            run_dir.mkdir()
            print(f"PKUSER6 guest {i}/2, 45-second bound", flush=True)
            run, _, handoff = boot._execute_once(f"user-root-{i}", lock, profile, qemu,
                media_path, run_dir, 45, marker_validator=probe.validate_markers,
                marker_extractor=transfer.extract_markers, completion_marker=probe.COMPLETION)
            prefix = run["marker_summary"]["transfer_prefix"]
            load.validate_oracle_binding(prefix["boot_prefix"], inspected, run["pbp1_transcript"])
            run["transcript_binding"] = transfer.validate_transcript_binding(prefix, run["pbp1_transcript"])
            run["independent_revalidation"] = transfer.validate_revalidation_binding(prefix, handoff, retained)
            run["hostile_marker_cases_rejected"] = probe.negative_controls(run["markers"])
            report["guest_runs"].append(run)
        default_media = load.build_media_bytes(default, config, manifest, kernel, files)
        default_path = work / "ordinary-denial.img"
        default_path.write_bytes(default_media)
        run_dir = work / "ordinary-denial"
        run_dir.mkdir()
        print("Ordinary boot denial control, 45-second bound", flush=True)
        run, _, _ = boot._execute_once("ordinary-denial", lock, profile, qemu, default_path, run_dir, 45,
            marker_validator=load.validate_markers, marker_extractor=transfer.extract_markers)
        if any("USER-ROOT" in m or "POOLEOS:KERNEL:ENTRY" in m for m in run["markers"]):
            raise ValueError("ordinary boot entered kernel development path")
        load.validate_oracle_binding(run["marker_summary"], load.inspect_media_bytes(default_media), run["pbp1_transcript"])
        report["ordinary_denial"] = run
        report["ring3_executed"] = True
        report["status"] = "pass"
    except Exception as e:
        report["failure"] = f"{type(e).__name__}: {e}"
        print(report["failure"], flush=True)
    (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PKUSER6 live {report['status']}; ring3={report['ring3_executed']} production=0", flush=True)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
