"""Export a small public demo receipt from already-qualified local artifacts."""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from demos.native_iso import package, qualify
from runtime import native_pooleboot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--tests-log", type=Path, required=True)
    parser.add_argument("--viewer-log", type=Path, required=True)
    args = parser.parse_args()
    directory, _, _, inspected = qualify.validate_local_package(args.package_dir)
    for path in (args.tests_log, args.viewer_log):
        if not path.resolve().is_relative_to((ROOT / "outputs").resolve()):
            raise ValueError("Evidence inputs must stay in workspace outputs")
    tests = args.tests_log.read_text(encoding="utf-8")
    viewer = args.viewer_log.read_text(encoding="utf-8")
    if "Ran 24 tests" not in tests or not tests.rstrip().endswith("OK"):
        raise ValueError("Expected passing 24-test demo log")
    if "Demo finished. No firmware or physical media was modified." not in viewer:
        raise ValueError("Passing capture-viewer log missing")
    result = json.loads((directory / "qualification.json").read_text())
    if result["iso_sha256"] != inspected["sha256"] or result["status"] != "pass_two_fresh_optical_boots":
        raise ValueError("Optical qualification identity mismatch")
    source = (directory / result["evidence_directory"] / "optical-run-1/frame.png").resolve()
    if not source.is_relative_to(directory):
        raise ValueError("Frame evidence escaped the demo package")
    demo = Path(__file__).resolve().parent
    shutil.copyfile(source, demo / "boot-preview.png")
    sources = [path for path in demo.rglob("*") if path.is_file() and path.name != "evidence.json"
               and "__pycache__" not in path.parts]
    receipt = {
        "contract_id": package.CONTRACT, "cycle": 151, "status": "pass_demo_only_single_host",
        "production_ready": False, "signed": False, "desktop_present": False, "animation_implemented": False,
        "physical_hardware_qualified": False, "native_source_commit": package.NATIVE_COMMIT,
        "iso_sha256": inspected["sha256"], "iso_bytes": inspected["byte_count"],
        "kernel": inspected["manifest"]["native_files"]["EFI/POOLEOS/KERNEL.ELF"],
        "demo_efi": inspected["manifest"]["native_files"]["EFI/BOOT/BOOTX64.EFI"],
        "optical_runs": [{"frame_sha256": run["frame_sha256"], "marker_count": len(run["markers"]),
                          "marker_sha256": package.sha256(native_pooleboot.canonical_json_bytes(run["markers"])),
                          "size": [run["width"], run["height"]], "exact_pixel_oracle_match": run["exact_pixel_oracle_match"]}
                         for run in result["runs"]],
        "rust_renderer_tests": 4, "local_demo_tests": 24, "headless_capture_viewer_test": "pass",
        "qemu_sdl_display": "disabled_after_host_crash_root_cause_unresolved",
        "test_log_sha256": package.sha256(args.tests_log.read_bytes()),
        "viewer_log_sha256": package.sha256(args.viewer_log.read_bytes()),
        "inputs": [native_pooleboot.file_binding(ROOT, path.relative_to(ROOT).as_posix()) for path in sorted(sources)],
        "claim_boundary": "Local demo build and optical evidence only; not a production gate, signature, second-host result or new kernel feature."
    }
    (demo / "evidence.json").write_bytes(native_pooleboot.canonical_json_bytes(receipt))
    print(json.dumps({"status": receipt["status"], "inputs": len(sources), "iso_sha256": receipt["iso_sha256"]}))


if __name__ == "__main__":
    main()
