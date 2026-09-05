"""Compile the isolated visual variant against unchanged production loader code."""

from __future__ import annotations

import re
from pathlib import Path

from demos.native_iso import package
from tools import qualify_native_pooleboot as boot

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "demos/native_iso/boot/Cargo.toml"


def build(temporary_root: Path) -> tuple[bytes, dict]:
    cargo, _, env = boot._toolchain(boot.DEFAULT_TOOLCHAIN_ROOT)
    env["CARGO_TARGET_X86_64_UNKNOWN_UEFI_RUSTFLAGS"] += f" --remap-path-prefix={MANIFEST.parent}=/pooleos/demo/boot"
    base = [str(cargo), "--manifest-path", str(MANIFEST), "--locked", "--offline"]
    test = boot._run_checked([base[0], "test", *base[1:], "--lib", "--target", "x86_64-pc-windows-msvc",
                              "--target-dir", str(temporary_root / "host")], cwd=boot.NATIVE_ROOT, env=env)
    match = re.search(r"test result: ok\. ([0-9]+) passed; 0 failed", test)
    if match is None or int(match[1]) < 4:
        raise ValueError("Demo renderer tests failed or shrank")
    binaries = []
    for index in (1, 2):
        target = temporary_root / f"clean-{index}"
        boot._run_checked([base[0], "build", *base[1:], "--bin", "PooleGlassDemo", "--features", "development-locks",
                           "--release", "--target", "x86_64-unknown-uefi", "--target-dir", str(target)],
                          cwd=boot.NATIVE_ROOT, env=env)
        binaries.append((target / "x86_64-unknown-uefi/release/PooleGlassDemo.efi").read_bytes())
    if binaries[0] != binaries[1] or len(binaries[0]) > 262_144:
        raise ValueError("Demo clean builds differ or exceed the unchanged loader size bound")
    inspection, errors = boot.validate_binary(binaries[0], boot.EXPECTED_PE)
    if errors or inspection is None:
        raise ValueError(f"Invalid demo EFI executable: {errors}")
    markers = {"root": str(ROOT), "root_posix": ROOT.as_posix(), "home": str(Path.home()),
               "home_posix": Path.home().as_posix(), "host_dll": "kernel32.dll"}
    if boot.scan_forbidden_markers(binaries[0], markers):
        raise ValueError("Host marker in demo EFI executable")
    # Build the exact same pixel function as a host oracle; it is not shipped on media.
    boot._run_checked([base[0], "build", *base[1:], "--example", "render", "--target", "x86_64-pc-windows-msvc",
                       "--target-dir", str(temporary_root / "host")], cwd=boot.NATIVE_ROOT, env=env)
    return binaries[0], {"variant": "pooleglass-demo-only", "host_tests_passed": int(match[1]),
                          "clean_builds": 2, "exact_clean_build_match": True,
                          "byte_count": len(binaries[0]), "sha256": package.sha256(binaries[0]),
                          "inspection": inspection, "production_loader_source_changed": False}
