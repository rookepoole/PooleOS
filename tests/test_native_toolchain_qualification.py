import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.native_binary import (  # noqa: E402
    BinaryFormatError,
    inspect_binary,
    scan_forbidden_markers,
    validate_binary,
)
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


def synthetic_pe32_plus() -> bytes:
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 0, 0, 0, 0, 240, 0x22)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<II", data, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", data, optional + 56, 0x2000, 0x200)
    struct.pack_into("<H", data, optional + 68, 10)
    struct.pack_into("<I", data, optional + 108, 16)
    return bytes(data)


def synthetic_elf64() -> bytes:
    ident = b"\x7fELF\x02\x01\x01" + b"\0" * 9
    header = struct.pack("<HHIQQQIHHHHHH", 2, 62, 1, 0x200000, 0, 0, 0, 64, 0, 0, 0, 0, 0)
    return ident + header


class NativeToolchainQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lock_path = ROOT / "specs" / "native-toolchain-lock.json"
        cls.contract_path = ROOT / "specs" / "native-target-contract.json"
        cls.report_path = ROOT / "runs" / "native_toolchain_qualification.json"
        cls.lock = json.loads(cls.lock_path.read_text(encoding="utf-8"))
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))
        cls.report = json.loads(cls.report_path.read_text(encoding="utf-8"))

    def test_all_three_native_artifacts_match_their_schemas(self) -> None:
        cases = (
            (self.lock, "native-toolchain-lock.schema.json"),
            (self.contract, "native-target-contract.schema.json"),
            (self.report, "native-toolchain-qualification.schema.json"),
        )
        for artifact, schema_name in cases:
            with self.subTest(schema=schema_name):
                schema = json.loads((ROOT / "specs" / schema_name).read_text(encoding="utf-8"))
                self.assertEqual(validate_json(artifact, schema), [])

    def test_lock_freezes_exact_official_distribution_inputs(self) -> None:
        self.assertEqual(self.lock["toolchain"]["channel"], "1.97.0-x86_64-pc-windows-msvc")
        self.assertEqual(self.lock["channel_manifest"]["date"], "2026-07-09")
        self.assertEqual(
            self.lock["channel_manifest"]["sha256"],
            "3804D2666F7C12CE64205BAA69B6BE52F910B45B158091013264BEB7AA1DE7F5",
        )
        components = {(item["package"], item["target"]) for item in self.lock["toolchain"]["components"]}
        self.assertEqual(
            components,
            {
                ("rustc", "x86_64-pc-windows-msvc"),
                ("cargo", "x86_64-pc-windows-msvc"),
                ("rust-std", "x86_64-pc-windows-msvc"),
                ("rust-std", "x86_64-unknown-uefi"),
                ("rust-std", "x86_64-unknown-none"),
            },
        )
        self.assertFalse(self.lock["channel_manifest"]["detached_signature_verified"])

    def test_target_contract_freezes_uefi_and_kernel_assumptions(self) -> None:
        boot, kernel = self.contract["targets"]
        self.assertEqual((boot["triple"], boot["object_format"], boot["calling_convention"]), ("x86_64-unknown-uefi", "PE32+", "efiapi"))
        self.assertEqual((kernel["triple"], kernel["object_format"], kernel["code_model"]), ("x86_64-unknown-none", "ELF64", "kernel"))
        for target in (boot, kernel):
            self.assertFalse(target["red_zone"])
            self.assertFalse(target["floating_or_vector_before_explicit_state_support"])
            self.assertTrue(target["static_link"])
            self.assertEqual(target["linker"], "rust-lld")

    def test_report_bindings_match_every_declared_source(self) -> None:
        bindings = [
            self.report["bindings"]["toolchain_lock"],
            self.report["bindings"]["target_contract"],
            *self.report["bindings"]["build_inputs"],
        ]
        for binding in bindings:
            with self.subTest(path=binding["path"]):
                path = ROOT / binding["path"]
                data = path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest().upper(), binding["sha256"])
                self.assertEqual(len(data), binding["byte_count"])
                self.assertFalse(path.is_absolute() and binding["path"].startswith(str(ROOT)))

    def test_real_fixture_evidence_is_reproducible_static_and_non_promoting(self) -> None:
        self.assertFalse(self.report["production_ready"])
        self.assertFalse(self.report["production_promotion_allowed"])
        self.assertFalse(self.report["scope"]["functional_boot_tested"])
        self.assertFalse(self.report["scope"]["kernel_execution_tested"])
        self.assertFalse(self.report["scope"]["two_host_reproduction_complete"])
        builds = {item["target_triple"]: item for item in self.report["builds"]}
        boot = builds["x86_64-unknown-uefi"]
        kernel = builds["x86_64-unknown-none"]
        for build in (boot, kernel):
            self.assertEqual(len(set(build["run_sha256"])), 1)
            self.assertEqual(len(set(build["run_byte_count"])), 1)
            self.assertTrue(build["exact_byte_match"])
            self.assertTrue(build["binary_contract_pass"])
            self.assertEqual(build["host_leakage_hit_count"], 0)
        self.assertEqual(boot["inspection"]["format"], "PE32+")
        self.assertEqual(boot["inspection"]["timestamp"], 0)
        self.assertFalse(boot["inspection"]["imports_present"])
        self.assertFalse(boot["inspection"]["debug_directory_present"])
        self.assertEqual(kernel["inspection"]["format"], "ELF64")
        self.assertFalse(kernel["inspection"]["dynamic_segment_present"])
        self.assertFalse(kernel["inspection"]["interpreter_segment_present"])
        encoded = self.report_path.read_text(encoding="utf-8")
        self.assertNotIn(str(ROOT), encoded)
        self.assertNotIn(str(Path.home()), encoded)

    def test_binary_inspector_accepts_minimal_structures_and_rejects_substitution(self) -> None:
        pe = synthetic_pe32_plus()
        elf = synthetic_elf64()
        self.assertEqual(inspect_binary(pe)["format"], "PE32+")
        self.assertEqual(inspect_binary(elf)["format"], "ELF64")
        _, errors = validate_binary(pe, {"format": "ELF64", "machine": 62})
        self.assertTrue(errors)
        with self.assertRaises(BinaryFormatError):
            inspect_binary(elf[:24])

    def test_host_leakage_scanner_detects_ascii_and_utf16_without_exposing_values(self) -> None:
        marker = "private-host-path"
        data = marker.encode("ascii") + b"\0" + marker.encode("utf-16le")
        hits = scan_forbidden_markers(data, {"synthetic_path": marker})
        self.assertEqual(
            hits,
            [
                {"marker_id": "synthetic_path", "encoding": "utf16le"},
                {"marker_id": "synthetic_path", "encoding": "utf8_or_ascii"},
            ],
        )

    def test_generator_reproduces_public_ledger_when_local_toolchain_is_available(self) -> None:
        toolchain = ROOT / ".toolchains" / "rust-1.97.0"
        if not (toolchain / "cargo" / "bin" / "rustup.exe").is_file():
            self.skipTest("workspace-local qualification toolchain is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "qualification.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "qualify_native_toolchain.py"),
                    "--toolchain-root",
                    str(toolchain),
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                env={**os.environ, "PYTHONHASHSEED": "0"},
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(output.read_bytes(), self.report_path.read_bytes())

    def test_release_gate_carries_bounded_native_toolchain_evidence(self) -> None:
        check = pooleos_release_gate.check_native_toolchain_qualification(self.report_path)
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("byte_identical=2/2", check["detail"])
        self.assertIn("two_host=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
