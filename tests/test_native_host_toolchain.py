from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import native_host_toolchain as host


class NativeHostToolchainTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pooleos-host-msvc-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.msvc, self.sdk = self.root / "msvc", self.root / "sdk"
        self.files = []
        for role, source, relative in host.GROUPS:
            directory = {"msvc": self.msvc, "sdk": self.sdk}[source] / relative
            directory.mkdir(parents=True)
            path = directory / ("link.exe" if source == "msvc" and "bin/" in relative else "input.lib")
            path.write_bytes(role.encode("ascii"))
            self.files.append(path)
        self.profile = {
            "schema_version": "1.0", "profile_id": host.PROFILE_ID,
            "msvc_version": host.MSVC_VERSION, "windows_sdk_version": host.SDK_VERSION,
            "production_ready": False, "input_trees": host.input_bindings(self.msvc, self.sdk),
        }
        (self.root / "specs").mkdir()
        self.write_profile()
        self.environment = {
            "POOLEOS_HOST_MSVC_ROOT": str(self.msvc), "POOLEOS_HOST_WINDOWS_SDK_ROOT": str(self.sdk),
            "PATH": "controlled-rust-and-system-path", "CARGO_HOME": "controlled-cargo-home",
        }

    def write_profile(self):
        (self.root / host.PROFILE_PATH).write_text(json.dumps(self.profile), encoding="utf-8")

    def verify(self):
        return host.verified_environment(self.environment, self.root)

    def test_explicit_linker_and_exact_library_order(self):
        result = self.verify()
        self.assertEqual(result["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"], str(self.files[0]))
        self.assertEqual(result["LIB"].split(os.pathsep), [str(p.parent) for p in self.files[1:]])
        self.assertEqual(result["VCTOOLSVERSION"], host.MSVC_VERSION)
        self.assertEqual(result["WINDOWSSDKVERSION"], host.SDK_VERSION + "\\")

    def test_environment_and_global_path_are_not_mutated(self):
        before = dict(self.environment)
        global_before = dict(os.environ)
        result = self.verify()
        self.assertEqual(self.environment, before)
        self.assertEqual(dict(os.environ), global_before)
        self.assertEqual(result["PATH"], before["PATH"])
        self.assertEqual(result["CARGO_HOME"], before["CARGO_HOME"])

    def test_case_insensitive_ambient_overrides_are_removed(self):
        hostile = ("link", "_LiNk_", "LiBpAtH", "INCLUDE", "CL", "_CL_", "VSINSTALLDIR",
                   "CARGO_PROFILE_RELEASE_OPT_LEVEL", "CARGO_BUILD_RUSTFLAGS",
                   "CARGO_BUILD_RUSTDOCFLAGS", "RUSTC_WORKSPACE_WRAPPER",
                   "CARGO_BUILD_RUSTC_WRAPPER", "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
                   "cargo_target_x86_64_pc_windows_msvc_rustflags",
                   "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_RUNNER")
        self.environment.update(dict.fromkeys(hostile, "untrusted-override"))
        self.environment.update(LIB="untrusted", CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER="untrusted")
        result = self.verify()
        for key in hostile:
            self.assertNotIn(key.upper(), result)
        self.assertNotIn("untrusted", result["LIB"])
        self.assertEqual(result["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"], str(self.files[0]))

    def test_each_tree_content_mutation_is_rejected(self):
        for path in self.files:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                with self.assertRaisesRegex(host.QualificationError, "fingerprint mismatch"):
                    self.verify()
                path.write_bytes(original)

    def test_added_file_is_rejected(self):
        (self.files[1].parent / "injected.lib").write_bytes(b"unexpected")
        with self.assertRaisesRegex(host.QualificationError, "fingerprint mismatch"):
            self.verify()

    def test_deleted_file_is_rejected(self):
        self.files[1].unlink()
        with self.assertRaises(host.QualificationError):
            self.verify()

    def test_renamed_file_is_rejected(self):
        self.files[1].rename(self.files[1].with_name("renamed.lib"))
        with self.assertRaisesRegex(host.QualificationError, "fingerprint mismatch"):
            self.verify()

    def test_missing_root_is_rejected(self):
        self.environment["POOLEOS_HOST_MSVC_ROOT"] = str(self.root / "missing")
        with self.assertRaises(host.QualificationError):
            self.verify()

    def test_relative_roots_are_rejected(self):
        for key in ("POOLEOS_HOST_MSVC_ROOT", "POOLEOS_HOST_WINDOWS_SDK_ROOT"):
            with self.subTest(key=key):
                original = self.environment[key]
                self.environment[key] = "relative"
                with self.assertRaisesRegex(host.QualificationError, "must be absolute"):
                    self.verify()
                self.environment[key] = original

    def test_reparse_file_is_rejected(self):
        original = Path.is_symlink
        with mock.patch.object(Path, "is_symlink", lambda path: path == self.files[1] or original(path)):
            with self.assertRaisesRegex(host.QualificationError, "reparse entry"):
                self.verify()

    def test_reparse_directory_is_rejected(self):
        original = Path.is_symlink
        with mock.patch.object(Path, "is_symlink", lambda path: path == self.files[1].parent or original(path)):
            with self.assertRaisesRegex(host.QualificationError, "reparse entry"):
                self.verify()

    def test_version_or_promotion_changes_are_rejected(self):
        for field, value in (("schema_version", "2.0"), ("profile_id", "other"),
                             ("msvc_version", "latest"), ("windows_sdk_version", "latest"),
                             ("production_ready", True), ("production_ready", 0)):
            with self.subTest(field=field, value=value):
                original = self.profile[field]
                self.profile[field] = value
                self.write_profile()
                with self.assertRaisesRegex(host.QualificationError, "unsupported"):
                    self.verify()
                self.profile[field] = original

    def test_typed_binding_and_role_mutations_are_rejected(self):
        frozen = copy.deepcopy(self.profile)
        for field, value in (("file_count", True), ("file_count", 1.0), ("byte_count", 1),
                             ("role", "wrong"), ("tree_sha256", "0" * 64)):
            with self.subTest(field=field):
                self.profile = copy.deepcopy(frozen)
                self.profile["input_trees"][0][field] = value
                self.write_profile()
                with self.assertRaisesRegex(host.QualificationError, "fingerprint mismatch"):
                    self.verify()

    def test_missing_or_reordered_binding_is_rejected(self):
        frozen = copy.deepcopy(self.profile["input_trees"])
        for bindings in (None, [], frozen[:-1], list(reversed(frozen))):
            with self.subTest(bindings=bindings):
                self.profile["input_trees"] = bindings
                self.write_profile()
                with self.assertRaises(host.QualificationError):
                    self.verify()

    def test_malformed_profile_is_rejected(self):
        for data in (b"[", b"null", b"[]", b"{}"):
            with self.subTest(data=data):
                (self.root / host.PROFILE_PATH).write_bytes(data)
                with self.assertRaises(host.QualificationError):
                    self.verify()

    def test_profile_receipt_has_no_host_paths_or_complete_attestation_claim(self):
        receipt = host.profile_receipt(self.root)
        self.assertEqual(receipt["profile_id"], host.PROFILE_ID)
        self.assertEqual(len(receipt["profile_sha256"]), 64)
        self.assertNotIn(str(self.root), json.dumps(receipt))
        self.assertEqual(receipt["scope"], "host_linker_and_library_trees_not_complete_host_attestation")


if __name__ == "__main__":
    unittest.main()
