"""Build the demo from unchanged native source; do not update native receipts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from demos.native_iso import package, build_boot
from runtime import native_kernel_load, native_pooleboot
from tools import qualify_native_kernel_entry as entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs/native-demo-iso")
    args = parser.parse_args()
    output = args.out_dir.resolve()
    if not output.is_relative_to((ROOT / "outputs").resolve()):
        raise ValueError("Demo output must be an ordinary workspace outputs directory")
    if output.exists():
        raise ValueError("Use a new demo output directory; do not overwrite earlier evidence")
    subprocess.run(["git", "diff", "--exit-code", package.NATIVE_COMMIT, "--", "native"], cwd=ROOT, check=True)
    output.mkdir(parents=True)
    print("DEMO_ISO stage=native_kernel_clean_builds", flush=True)
    kernel_readiness, kernel = entry.make_readiness(entry.DEFAULT_TOOLCHAIN_ROOT)
    if package.sha256(kernel) != package.KERNEL_SHA256:
        raise ValueError("Native kernel identity changed")
    print("DEMO_ISO stage=native_pooleboot_clean_builds", flush=True)
    efi, boot_readiness = build_boot.build(output / "boot-builds")
    artifacts = native_kernel_load.canonical_artifact_files()
    config = native_kernel_load.canonical_config_bytes()
    manifest = native_kernel_load.canonical_manifest_bytes(kernel, artifacts)
    disk = native_kernel_load.build_media_bytes(efi, config, manifest, kernel, artifacts)
    (output / "native-source.img").write_bytes(disk)
    readme = Path(__file__).with_name("README.txt").read_bytes()
    license_text = (ROOT / "LICENSE").read_bytes() + b"\n\nBOOT TYPOGRAPHY NOTICE\n\n" + (build_boot.MANIFEST.parent / "assets/FONT-LICENSE.txt").read_bytes()
    print("DEMO_ISO stage=optical_packaging", flush=True)
    iso, _ = package.build_iso(disk, readme, license_text)
    second, _ = package.build_iso(disk, readme, license_text)
    if iso != second:
        raise ValueError("Two demo ISO authoring passes differ")
    target = output / "PooleOS-Native-Demo-0.1.0.iso"
    target.write_bytes(iso)
    report = package.inspect_iso(target.read_bytes(), disk=disk)
    report["native_builds"] = {"kernel": kernel_readiness, "pooleboot": boot_readiness}
    report["two_authoring_passes_exact"] = True
    report["optical_boot_verified"] = False
    (output / "build.json").write_bytes(native_pooleboot.canonical_json_bytes(report))
    (output / "SHA256SUMS.txt").write_text(f"{package.sha256(iso)}  {target.name}\n", encoding="ascii", newline="\n")
    print(json.dumps({"iso": str(target), "sha256": package.sha256(iso), "bytes": len(iso), "boot_verified": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
