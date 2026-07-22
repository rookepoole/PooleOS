from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime import native_kernel_entry as entry
from runtime.schema_validation import validate_json
from tools import pooleos_release_gate


ROOT = Path(__file__).resolve().parents[1]


class NativeKernelEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((ROOT / entry.CONTRACT_RELATIVE).read_text(encoding="utf-8"))
        cls.readiness = json.loads((ROOT / entry.READINESS_RELATIVE).read_text(encoding="utf-8"))

    def test_contract_and_readiness_match_schemas(self) -> None:
        contract_schema = json.loads(
            (ROOT / entry.CONTRACT_SCHEMA_RELATIVE).read_text(encoding="utf-8")
        )
        readiness_schema = json.loads(
            (ROOT / entry.READINESS_SCHEMA_RELATIVE).read_text(encoding="utf-8")
        )
        self.assertEqual(validate_json(self.contract, contract_schema), [])
        self.assertEqual(validate_json(self.readiness, readiness_schema), [])

    def test_contract_and_receipt_bindings_are_current(self) -> None:
        self.assertEqual(entry.contract_errors(self.contract), [])
        self.assertEqual(entry.readiness_errors(self.readiness), [])
        release_check = pooleos_release_gate.check_native_kernel_entry_readiness()
        self.assertTrue(release_check["ok"], release_check["detail"])

    def test_product_identity_and_entry_prefix_are_frozen(self) -> None:
        product = self.readiness["product"]
        self.assertEqual(product["canonical_byte_count"], 180224)
        self.assertEqual(product["image_byte_count"], 262144)
        self.assertEqual(product["entry_offset"], 0x8000)
        self.assertEqual(product["relocation_count"], 361)
        self.assertEqual(
            product["canonical_sha256"],
            "062D4EE10BA27F4D0A943D97206ADB5B3761770B6DD9EEC2C281605B2693B883",
        )
        self.assertTrue(product["entry_prefix_hex"].startswith("FAFC4889E14885C9"))

    def test_manifest_binds_all_three_contracts(self) -> None:
        fields = self.readiness["product"]["manifest_fields"]
        self.assertEqual(fields["entry_contract"], "PKENTRY1")
        self.assertEqual(fields["image_contract"], "PKELF1")
        self.assertEqual(fields["handoff_contract"], "PBP1")
        for field, path in (
            ("pkentry1_contract_sha256", entry.CONTRACT_RELATIVE),
            ("pkelf1_contract_sha256", Path("specs/native-elf-loader-contract.json")),
            ("pbp1_contract_sha256", Path("specs/native-boot-handoff-contract.json")),
        ):
            digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper()
            self.assertEqual(fields[field], digest)

    def test_framebuffer_mapping_gap_is_explicit(self) -> None:
        coverage = json.loads(
            (ROOT / "runs/pooleos_native_checklist_coverage.json").read_text(encoding="utf-8")
        )
        additions = {item["id"]: item for item in coverage["added_requirements"]}
        self.assertIn("ADD-KERNEL-001", additions)
        self.assertEqual(additions["ADD-KERNEL-001"]["phase_id"], "N6")
        mapping = self.contract["mapping_preconditions"]["framebuffer"]
        self.assertIn("identity-mapped", mapping["presence_rule"])
        self.assertIn("revoke", mapping["revocation"])

    def test_legacy_fixture_cannot_replace_the_product(self) -> None:
        product_manifest = (ROOT / "native/kernel/Cargo.toml").read_text(encoding="utf-8")
        fixture_manifest = (ROOT / "native/fixtures/poolekernel/Cargo.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn('name = "poolekernel"', product_manifest)
        self.assertIn('name = "PooleKernelLinked"', product_manifest)
        self.assertIn('name = "poolekernel-fixture"', fixture_manifest)
        self.assertIn('name = "PooleKernelFixture"', fixture_manifest)

    def test_receipt_never_promotes_the_bounded_product(self) -> None:
        claims = self.readiness["claims"]
        for claim in (
            "live_pooleboot_transfer",
            "exit_boot_services_executed",
            "page_tables_installed",
            "final_wx_permissions_installed",
            "hardware_serial_executed",
            "hardware_framebuffer_executed",
            "kernel_runtime_initialized",
            "qemu_kernel_execution",
            "target_firmware_tested",
            "second_host_reproduced",
            "bootable_iso",
            "n6_exit_gate_satisfied",
            "production_ready",
        ):
            self.assertFalse(claims[claim], claim)
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["production_promotion_allowed"])
        self.assertFalse(self.readiness["n6_exit_gate_satisfied"])

    def test_qualifier_reproduces_receipt_and_product_exactly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pooleos-pkentry1-test-") as temporary:
            out = Path(temporary) / "readiness.json"
            artifact = Path(temporary) / "PooleKernel.pkelf"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/qualify_native_kernel_entry.py"),
                    "--out",
                    str(out),
                    "--artifact-out",
                    str(artifact),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(out.read_bytes(), (ROOT / entry.READINESS_RELATIVE).read_bytes())
            self.assertEqual(
                hashlib.sha256(artifact.read_bytes()).hexdigest().upper(),
                self.readiness["product"]["canonical_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
