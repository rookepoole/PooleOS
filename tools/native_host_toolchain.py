"""Verify and select the host MSVC inputs used by native qualification probes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from tools.qualify_native_toolchain import QualificationError, tree_binding


PROFILE_PATH = Path("specs/native-host-msvc-profile.json")
PROFILE_ID = "POOLEOS-HOST-MSVC-1"
MSVC_VERSION = "14.44.35207"
SDK_VERSION = "10.0.18362.0"
GROUPS = (
    ("msvc_linker_tree", "msvc", "bin/Hostx64/x64"),
    ("msvc_library_tree", "msvc", "lib/x64"),
    ("sdk_ucrt_library_tree", "sdk", f"Lib/{SDK_VERSION}/ucrt/x64"),
    ("sdk_um_library_tree", "sdk", f"Lib/{SDK_VERSION}/um/x64"),
)


def _plain_tree(path: Path) -> None:
    pending = [path]
    entries = 0
    while pending:
        item = pending.pop()
        entries += 1
        if entries > 8192:
            raise QualificationError("host MSVC tree exceeds entry bound")
        junction = getattr(item, "is_junction", None)
        if item.is_symlink() or (junction and junction()):
            raise QualificationError("host MSVC tree contains a reparse entry")
        if item.is_dir():
            pending.extend(item.iterdir())
        elif not item.is_file():
            raise QualificationError("host MSVC tree contains a missing or non-file entry")


def input_bindings(msvc: Path, sdk: Path) -> list[dict[str, Any]]:
    """Use the existing bounded, ordered relative-name/content tree fingerprint."""
    roots = {"msvc": msvc, "sdk": sdk}
    result = []
    for role, source, relative in GROUPS:
        path = roots[source] / relative
        _plain_tree(path)
        result.append(tree_binding(path, role))
    return result


def verified_environment(environment: dict[str, str], root: Path) -> dict[str, str]:
    """Fail closed on drift; never alter the caller or the machine environment."""
    try:
        profile = json.loads((root / PROFILE_PATH).read_bytes())
        if (
            profile.get("profile_id") != PROFILE_ID
            or profile.get("schema_version") != "1.0"
            or profile.get("msvc_version") != MSVC_VERSION
            or profile.get("windows_sdk_version") != SDK_VERSION
            or profile.get("production_ready") is not False
        ):
            raise QualificationError("unsupported host MSVC profile")
        # Windows environment names are case-insensitive, including in injected tests.
        env = {key.upper(): value for key, value in environment.items()}
        program_files = Path(env.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        msvc = Path(env.get("POOLEOS_HOST_MSVC_ROOT", str(
            program_files / "Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC" / MSVC_VERSION
        )))
        sdk = Path(env.get("POOLEOS_HOST_WINDOWS_SDK_ROOT", str(program_files / "Windows Kits/10")))
        if not msvc.is_absolute() or not sdk.is_absolute():
            raise QualificationError("host MSVC and SDK roots must be absolute")
        observed = input_bindings(msvc, sdk)
        # JSON-typed equality rejects True/1 and float/integer substitutions.
        if json.dumps(observed, sort_keys=True) != json.dumps(profile.get("input_trees"), sort_keys=True):
            raise QualificationError("host MSVC input fingerprint mismatch; requalification required")
        linker = msvc / "bin/Hostx64/x64/link.exe"
        if not linker.is_file():
            raise QualificationError("host MSVC linker is missing")
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise QualificationError(f"invalid or unavailable host MSVC inputs: {exc}") from exc

    removed = {
        "LINK", "_LINK_", "LIB", "LIBPATH", "INCLUDE", "CL", "_CL_",
        "VCINSTALLDIR", "VCTOOLSINSTALLDIR", "VCTOOLSVERSION", "VSINSTALLDIR",
        "WINDOWSSDKDIR", "WINDOWSSDKVERSION", "WINDOWSSDKLIBVERSION", "UNIVERSALCRTSDKDIR",
        "UCRTVERSION", "VSCMD_ARG_TGT_ARCH", "VSCMD_ARG_HOST_ARCH", "VSLANG",
        "CARGO_BUILD_RUSTFLAGS", "CARGO_BUILD_RUSTDOCFLAGS", "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER", "RUSTC_WORKSPACE_WRAPPER",
    }
    for key in list(env):
        if key in removed or key.startswith(("CARGO_PROFILE_", "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_")):
            del env[key]
    env.update({
        "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER": str(linker),
        "LIB": os.pathsep.join(str(path) for path in (
            msvc / "lib/x64", sdk / f"Lib/{SDK_VERSION}/ucrt/x64", sdk / f"Lib/{SDK_VERSION}/um/x64",
        )),
        "VSCMD_ARG_TGT_ARCH": "x64", "VSCMD_ARG_HOST_ARCH": "x64", "VSLANG": "1033",
        "VCTOOLSINSTALLDIR": str(msvc) + "\\", "VCTOOLSVERSION": MSVC_VERSION,
        "VCINSTALLDIR": str(msvc.parent.parent) + "\\",
        "WINDOWSSDKDIR": str(sdk) + "\\", "WINDOWSSDKVERSION": SDK_VERSION + "\\",
        "WINDOWSSDKLIBVERSION": SDK_VERSION + "\\",
        "UNIVERSALCRTSDKDIR": str(sdk) + "\\", "UCRTVERSION": SDK_VERSION,
    })
    return env


def profile_receipt(root: Path) -> dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "profile_sha256": hashlib.sha256((root / PROFILE_PATH).read_bytes()).hexdigest().upper(),
        "verified_before_build": True,
        "scope": "host_linker_and_library_trees_not_complete_host_attestation",
    }
