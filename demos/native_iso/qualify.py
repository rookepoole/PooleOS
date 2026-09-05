"""Boot only the demo CD-ROM in the pinned, networkless QEMU profile."""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PIL import Image
from demos.native_iso import package
from runtime import native_kernel_load, native_kernel_locks as locks, native_kernel_transfer
from runtime import native_live_boot_handoff, native_pooleboot, native_tier0
from tools import qualify_native_pooleboot as boot, qualify_native_kernel_locks as lock_runner


def completion_line_observed(raw):
    return any(line.startswith(locks.COMPLETION_MARKER) and line.endswith(b"\n")
               for line in raw.splitlines(keepends=True))


def optical_profile(base):
    profile = lock_runner._sandybridge_four_vcpu_profile(base)
    args = profile["base_argument_template"]
    source = "virtio-blk-pci-non-transitional,drive=pooleos_media"
    if args.count(source) != 1:
        raise ValueError("Base media device changed")
    args[args.index(source)] = "ide-cd,drive=pooleos_media,bus=ide.0,bootindex=1"
    drive = "if=none,id=pooleos_media,format=raw,readonly=on,file=$MEDIA"
    if args.count(drive) != 1:
        raise ValueError("Base media drive changed")
    args[args.index(drive)] = drive + ",media=cdrom"
    return profile


def validate_local_package(directory: Path):
    directory = directory.resolve()
    if not directory.is_relative_to((ROOT / "outputs").resolve()) or "," in str(directory):
        raise ValueError("Demo package must be inside workspace outputs without commas")
    iso = directory / "PooleOS-Native-Demo-0.1.0.iso"
    disk = directory / "native-source.img"
    if not iso.is_file() or iso.stat().st_size > package.MAX_ISO_BYTES or not disk.is_file() or disk.stat().st_size != native_pooleboot.IMAGE_BYTES:
        raise ValueError("Missing or oversized local demo media")
    inspection = package.inspect_iso(iso.read_bytes(), disk=disk.read_bytes())
    build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
    if any(inspection[key] != build.get(key) for key in inspection):
        raise ValueError("Local build receipt does not match demo package")
    return directory, iso, disk.read_bytes(), inspection


def execute_once(lock, profile, directory, iso, run_dir, oracle, timeout, *, on_frame=None, cancel=None):
    run_dir.mkdir()
    qemu_root = native_tier0.DEFAULT_QEMU_ROOT
    firmware = {item["role"]: item for item in lock["firmware"]["files"]}
    shutil.copyfile(qemu_root / firmware["vars_template_copy_only"]["relative_path"],
                    run_dir / profile["evidence_contract"]["vars_copy"])
    command = native_tier0._actual_command(lock, profile, "bootstrap-debug", qemu_root, iso, run_dir)
    port = boot._available_port()
    command.extend(["-device", "VGA,id=poole_gop", "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"])
    client = None
    # Keep stderr on disk so a full pipe cannot deadlock the emulator.
    with (run_dir / "stderr.log").open("xb") as errors:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=errors,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            client, _ = boot._QmpClient.connect(port, process, timeout)
            client.execute("qmp_capabilities")
            debug = run_dir / profile["evidence_contract"]["debugcon_log"]
            serial = run_dir / profile["evidence_contract"]["serial_log"]
            deadline = time.monotonic() + timeout
            frame_path = run_dir / "frame.ppm"
            while time.monotonic() < deadline:
                if cancel is not None and cancel.is_set():
                    raise RuntimeError("Demo cancelled")
                raw = debug.read_bytes() if debug.exists() else b""
                if any(marker in raw for marker in (b"POOLEBOOT/0.1 ERROR", b"POOLEBOOT/0.1 PANIC", b"POOLEOS:PANIC", b"POOLEOS:NESTED-PANIC")):
                    raise ValueError("Demo guest reported a failure; see retained debug log")
                if not frame_path.exists() and b"POOLEBOOT/0.1 FRAME READY" in raw:
                    client.execute("stop")
                    client.execute("screendump", {"filename": str(frame_path), "format": "ppm"})
                    if on_frame is not None:
                        on_frame(frame_path, "Actual QEMU boot frame | Host-paused for 8 seconds")
                        if cancel is not None and cancel.wait(8):
                            raise RuntimeError("Demo cancelled")
                    client.execute("cont")
                if completion_line_observed(raw) and serial.is_file() and completion_line_observed(serial.read_bytes()):
                    break
                if process.poll() is not None:
                    raise ValueError("Demo guest exited before native completion")
                time.sleep(0.005)
            else:
                raise TimeoutError("Bounded demo boot timed out; own emulator will be stopped")
            client.execute("stop")
            if not frame_path.is_file():
                raise ValueError("Boot-stage screenshot was not captured")
            client.execute("screendump", {"filename": str(run_dir / "kernel-console.ppm"), "format": "ppm"})
            raw = debug.read_bytes()
            serial_raw = serial.read_bytes()
            markers = locks.extract_markers(raw)
            summary = locks.validate_markers(markers)
            if markers != locks.extract_markers(serial_raw):
                raise ValueError("Serial/debug marker mismatch")
            transcript = native_live_boot_handoff.extract_transcript(raw)
            if transcript.data != native_live_boot_handoff.extract_transcript(serial_raw).data:
                raise ValueError("Serial/debug PBP1 mismatch")
            frame = frame_path.read_bytes()
            with Image.open(io.BytesIO(frame)) as observed:
                width, height = observed.size
                if not (320 <= width <= 3840 and 200 <= height <= 2160):
                    raise ValueError("Unexpected display bounds")
                expected = subprocess.check_output([str(oracle), str(width), str(height)], timeout=30)
                with Image.open(io.BytesIO(expected)) as reference:
                    if observed.mode != "RGB" or observed.tobytes() != reference.tobytes():
                        raise ValueError("Actual guest frame differs from compiled pixel oracle")
                observed.save(run_dir / "frame.png")
            if on_frame is not None:
                on_frame(run_dir / "kernel-console.ppm", "Actual QEMU kernel console | PKLOCK1 PASS")
            client.execute("quit")
            process.wait(timeout=10)
            if process.returncode != 0:
                raise ValueError("QEMU did not exit cleanly")
            return {"markers": markers, "marker_summary": summary, "pbp1_transcript": transcript.summary,
                    "frame_sha256": package.sha256(frame), "exact_pixel_oracle_match": True,
                    "width": width, "height": height, "fresh_vars": True, "qemu_exit_code": 0}, frame, transcript.data
        finally:
            if client is not None:
                try:
                    client.close()
                except OSError:
                    pass
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not 10 <= args.timeout <= 300:
        raise ValueError("Timeout must be 10-300 seconds")
    directory, iso, disk, inspection = validate_local_package(args.package_dir)
    oracle = directory / "boot-builds/host/x86_64-pc-windows-msvc/debug/examples/render.exe"
    if not oracle.is_file():
        raise ValueError("Freshly compiled demo pixel oracle missing")
    lock, base = native_tier0.validate_contracts(ROOT)
    native_tier0.verify_local_launch_runtime(lock, native_tier0.DEFAULT_QEMU_ROOT, ROOT)
    profile = optical_profile(base)
    media_inspection = native_kernel_load.inspect_media_bytes(disk)
    attempt = Path(tempfile.mkdtemp(prefix="verification-", dir=directory))
    outputs = []
    for index in (1, 2):
        print(f"DEMO_ISO stage=actual_optical_boot_{index}", flush=True)
        outputs.append(execute_once(lock, profile, directory, iso, attempt / f"optical-run-{index}", oracle, args.timeout))
        run = outputs[-1][0]
        prefix = run["marker_summary"]["transfer_prefix"]
        native_kernel_load.validate_oracle_binding(prefix["boot_prefix"], media_inspection, run["pbp1_transcript"])
        native_kernel_transfer.validate_transcript_binding(prefix, run["pbp1_transcript"])
    if outputs[0] != outputs[1]:
        raise ValueError("Two fresh optical runs differ")
    report = {"contract_id": package.CONTRACT, "status": "pass_two_fresh_optical_boots",
              "iso_sha256": inspection["sha256"], "optical_only": True, "guest_network": False,
              "host_disk_attached": False, "production_ready": False, "signed": False,
              "animation_implemented": False, "native_kernel_sha256": package.KERNEL_SHA256,
              "evidence_directory": attempt.name,
              "base_profile": "native-tier0-profile.json", "argument_template": profile["base_argument_template"],
              "runs": [item[0] for item in outputs]}
    (directory / "qualification.json").write_bytes(native_pooleboot.canonical_json_bytes(report))
    print(json.dumps({"status": report["status"], "iso_sha256": report["iso_sha256"], "production_ready": False}))


if __name__ == "__main__":
    main()
