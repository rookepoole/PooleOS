from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_boot_trust, native_firmware, native_kernel_revalidation, native_policy, native_pooleboot, native_symbols
from tools import (
    qualify_native_boot_trust,
    qualify_native_firmware,
    qualify_native_kernel_revalidation,
    qualify_native_policy,
    qualify_native_pooleboot,
    qualify_native_symbols,
)
from tools.qualify_native_toolchain import QualificationError as HostToolchainError


ROOT = Path(__file__).resolve().parents[1]
PROFILES = (
    (qualify_native_symbols, native_symbols, "validator_qualification", "bindings", native_symbols.readiness_errors),
    (qualify_native_policy, native_policy, "build", "inputs", native_policy.readiness_errors),
    (qualify_native_pooleboot, native_pooleboot, "build", "bindings", native_pooleboot.readiness_contract_errors),
    (qualify_native_kernel_revalidation, native_kernel_revalidation, "build", "inputs", native_kernel_revalidation.readiness_errors),
    (qualify_native_firmware, native_firmware, "build", "inputs", native_firmware.readiness_errors),
    (qualify_native_boot_trust, native_boot_trust, "build", "inputs", native_boot_trust.readiness_errors),
)
HOST_INPUTS = (
    "native/.cargo/config.toml", "native/rust-toolchain.toml", "specs/native-host-msvc-profile.json",
    "tools/native_host_toolchain.py", "tools/qualify_native_toolchain.py",
    "tests/test_native_boot_host_toolchain.py",
)


class NativeBootHostToolchainTests(unittest.TestCase):
    def test_ambient_overrides_are_removed_before_pinned_host_selection(self) -> None:
        lock = json.loads((ROOT / "specs/native-toolchain-lock.json").read_bytes())
        version = lock["channel_manifest"]["rust_version"] + " " + lock["host"]["triple"]
        hostile = {key: "untrusted-override" for key in (
            "LINK", "_LINK_", "LIB", "LIBPATH", "INCLUDE", "CL", "_CL_",
            "CARGO_BUILD_RUSTC", "CARGO_PROFILE_RELEASE_OPT_LEVEL", "RUSTC_WORKSPACE_WRAPPER",
            "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER",
            "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_RUSTFLAGS",
            "CARGO_TARGET_X86_64_UNKNOWN_UEFI_RUSTFLAGS",
        )}
        for qualifier, _, _, _, _ in PROFILES:
            run_name = "_run_checked" if qualifier is qualify_native_pooleboot else "_run"
            output = (0, version) if qualifier is qualify_native_kernel_revalidation else version

            def verify(env, root):
                self.assertEqual(root, ROOT)
                self.assertTrue(set(hostile).isdisjoint(env))
                return dict(env, CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER="pinned-linker")

            with self.subTest(qualifier=qualifier.__name__), \
                 mock.patch.dict(os.environ, hostile), \
                 mock.patch.object(Path, "is_file", return_value=True), \
                 mock.patch.object(qualifier, run_name, return_value=output), \
                 mock.patch.object(qualifier, "verified_environment", side_effect=verify) as pin:
                _, _, env = qualifier._toolchain(ROOT / "tmp" / "unit-toolchain")
                pin.assert_called_once()
                self.assertEqual(env["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"], "pinned-linker")
                self.assertIn("--remap-path-prefix=", env["CARGO_TARGET_X86_64_UNKNOWN_UEFI_RUSTFLAGS"])
                self.assertIn("-Cpanic=abort", env["CARGO_TARGET_X86_64_UNKNOWN_NONE_RUSTFLAGS"])
                self.assertNotIn("untrusted-override", env.values())

    def test_host_profile_failure_stops_before_running_the_compiler(self) -> None:
        for qualifier, _, _, _, _ in PROFILES:
            run_name = "_run_checked" if qualifier is qualify_native_pooleboot else "_run"
            with self.subTest(qualifier=qualifier.__name__), \
                 mock.patch.object(Path, "is_file", return_value=True), \
                 mock.patch.object(qualifier, run_name) as run, \
                 mock.patch.object(qualifier, "verified_environment", side_effect=HostToolchainError("host input changed")):
                with self.assertRaisesRegex(qualifier.QualificationError, "host input changed"):
                    qualifier._toolchain(ROOT / "tmp" / "unit-toolchain")
                run.assert_not_called()

    def test_generated_receipts_reject_missing_and_wrong_typed_host_profiles(self) -> None:
        for _, runtime, build_key, _, validate in PROFILES:
            receipt = json.loads((ROOT / runtime.READINESS_RELATIVE).read_bytes())
            self.assertEqual(validate(receipt, ROOT), [])
            variants = []
            for field, value in (("profile_id", "other"), ("profile_sha256", "0" * 64),
                                 ("verified_before_build", False), ("verified_before_build", 1),
                                 ("scope", "complete_host_attestation")):
                host = copy.deepcopy(receipt[build_key]["host_toolchain"])
                host[field] = value
                variants.append(host)
            variants.extend((None, {}, [], "verified", True))
            for host in variants:
                with self.subTest(runtime=runtime.__name__, host=host):
                    changed = copy.deepcopy(receipt)
                    changed[build_key]["host_toolchain"] = host
                    self.assertTrue(validate(changed, ROOT))
            missing = copy.deepcopy(receipt)
            del missing[build_key]["host_toolchain"]
            self.assertTrue(validate(missing, ROOT))

    def test_host_build_input_bindings_are_present_unique_and_enforced(self) -> None:
        for _, runtime, _, bindings_key, validate in PROFILES:
            receipt = json.loads((ROOT / runtime.READINESS_RELATIVE).read_bytes())
            self.assertEqual(validate(receipt, ROOT), [])
            inputs = receipt[bindings_key]["implementation_inputs"]
            paths = [binding["path"] for binding in inputs]
            self.assertEqual(len(paths), len(set(paths)))
            self.assertTrue(set(HOST_INPUTS).issubset(paths))
            for relative in HOST_INPUTS:
                with self.subTest(runtime=runtime.__name__, path=relative):
                    changed = copy.deepcopy(receipt)
                    binding = next(b for b in changed[bindings_key]["implementation_inputs"] if b["path"] == relative)
                    binding["sha256"] = "0" * 64
                    self.assertTrue(validate(changed, ROOT))

    def test_symbol_and_policy_rejection_never_creates_or_overwrites_output(self) -> None:
        for qualifier, runtime, build_key, _, validate in PROFILES[:2]:
            receipt = json.loads((ROOT / runtime.READINESS_RELATIVE).read_bytes())
            self.assertEqual(validate(receipt, ROOT), [])
            factory = "make_readiness" if qualifier is qualify_native_symbols else "qualify"
            for mutation in ("production", "host"):
                for existing in (False, True):
                    with self.subTest(profile=runtime.__name__, mutation=mutation, existing=existing), \
                         tempfile.TemporaryDirectory() as temporary:
                        output = Path(temporary) / "nested" / "receipt.json"
                        if existing:
                            output.parent.mkdir()
                            output.write_bytes(b"keep-existing-receipt")
                        changed = copy.deepcopy(receipt)
                        if mutation == "production":
                            changed["production_ready"] = True
                        else:
                            del changed[build_key]["host_toolchain"]
                        with mock.patch.object(qualifier, factory, return_value=changed):
                            with self.assertRaises(qualifier.QualificationError):
                                qualifier.main(["--out", str(output)])
                        if existing:
                            self.assertEqual(output.read_bytes(), b"keep-existing-receipt")
                        else:
                            self.assertFalse(output.parent.exists())


if __name__ == "__main__":
    unittest.main()
