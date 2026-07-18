from __future__ import annotations

import copy
import dataclasses
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_firmware as pfwm1  # noqa: E402


class NativeFirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = pfwm1.read_json(ROOT / pfwm1.CONTRACT_RELATIVE)
        cls.golden = pfwm1.read_json(ROOT / pfwm1.GOLDEN_RELATIVE)
        cls.readiness = pfwm1.read_json(ROOT / pfwm1.READINESS_RELATIVE)

    def test_contract_vectors_and_readiness_validate(self) -> None:
        self.assertEqual([], pfwm1.contract_errors(self.contract, ROOT))
        self.assertEqual([], pfwm1.golden_errors(self.golden, ROOT))
        self.assertEqual([], pfwm1.readiness_errors(self.readiness, ROOT))

    def test_generated_contract_and_vectors_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_native_firmware_vectors.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_canonical_manifest_round_trips(self) -> None:
        first = pfwm1.canonical_bundle()
        second = pfwm1.canonical_bundle()
        self.assertEqual(first, second)
        bundle = pfwm1.parse(first)
        self.assertEqual((100, 200, 300), tuple(item.component_id for item in bundle.components))
        self.assertEqual(2, len(bundle.dependencies))
        self.assertEqual(1, bundle.maximum_transaction_components)

    def test_minimal_and_boundary_vectors_cover_limits(self) -> None:
        minimal = pfwm1.parse(pfwm1.minimal_bundle())
        boundary = pfwm1.parse(pfwm1.boundary_bundle())
        self.assertEqual(1, len(minimal.components))
        self.assertEqual(pfwm1.MAX_COMPONENTS, len(boundary.components))
        self.assertEqual(pfwm1.MAX_COMPONENTS - 1, len(boundary.dependencies))

    def test_header_and_body_substitution_fail_closed(self) -> None:
        original = pfwm1.canonical_bundle()
        magic = bytearray(original)
        magic[0] ^= 1
        with self.assertRaisesRegex(pfwm1.FirmwareError, "pfwm_magic"):
            pfwm1.parse(bytes(magic))
        body = bytearray(original)
        body[-1] ^= 1
        with self.assertRaisesRegex(pfwm1.FirmwareError, "pfwm_body_digest"):
            pfwm1.parse(bytes(body))

    def test_exact_identity_and_version_floors_fail_closed(self) -> None:
        original = pfwm1.canonical_bundle()
        guid = bytearray(original)
        guid[pfwm1.HEADER_BYTES + 24 : pfwm1.HEADER_BYTES + 40] = b"\0" * 16
        guid[376:408] = __import__("hashlib").sha256(guid[pfwm1.HEADER_BYTES :]).digest()
        with self.assertRaisesRegex(pfwm1.FirmwareError, "pfwm_component_guid"):
            pfwm1.parse(bytes(guid))
        floor = bytearray(original)
        struct.pack_into("<Q", floor, pfwm1.HEADER_BYTES + 72, 0xFFFF_FFFF_FFFF_FFFF)
        floor[376:408] = __import__("hashlib").sha256(floor[pfwm1.HEADER_BYTES :]).digest()
        with self.assertRaisesRegex(pfwm1.FirmwareError, "pfwm_component_versions"):
            pfwm1.parse(bytes(floor))

    def test_dependency_order_is_exact_and_acyclic(self) -> None:
        original = bytearray(pfwm1.canonical_bundle())
        dependency_offset = pfwm1.HEADER_BYTES + 3 * pfwm1.COMPONENT_RECORD_BYTES
        struct.pack_into("<Q", original, dependency_offset + 8, 1)
        original[376:408] = __import__("hashlib").sha256(original[pfwm1.HEADER_BYTES :]).digest()
        with self.assertRaisesRegex(pfwm1.FirmwareError, "pfwm_dependency_version"):
            pfwm1.parse(bytes(original))

    def test_development_context_denies_at_outer_signature(self) -> None:
        bundle = pfwm1.parse(pfwm1.canonical_bundle())
        context = pfwm1.development_activation_context(bundle)
        errors = pfwm1.activation_errors(bundle, context)
        self.assertEqual("pfwm_activation_outer_signature", errors[0])
        with self.assertRaisesRegex(pfwm1.FirmwareError, errors[0]):
            pfwm1.authorize_dry_run_plan(bundle, context)

    def test_qualified_context_returns_only_a_dry_run_plan(self) -> None:
        bundle = pfwm1.parse(pfwm1.canonical_bundle())
        context = pfwm1.synthetic_qualified_activation_context(bundle)
        plan = pfwm1.authorize_dry_run_plan(bundle, context)
        self.assertTrue(plan.qualification_only)
        self.assertEqual(1, plan.maximum_parallel_components)
        self.assertEqual((100, 200, 300), plan.component_order)
        mutation = dataclasses.replace(context, firmware_mutation_requested=True)
        with self.assertRaisesRegex(
            pfwm1.FirmwareError, "pfwm_activation_firmware_mutation_requested"
        ):
            pfwm1.authorize_dry_run_plan(bundle, mutation)

    def test_post_reset_requires_receipt_before_driver_rebind(self) -> None:
        bundle = pfwm1.parse(pfwm1.canonical_bundle())
        records = list(pfwm1.synthetic_post_reset_records(bundle))
        pfwm1.verify_post_reset(bundle, records, qualification_only=True)
        records[0] = dataclasses.replace(records[0], receipt_persisted=False)
        with self.assertRaisesRegex(pfwm1.FirmwareError, "pfwm_post_reset_receipt"):
            pfwm1.verify_post_reset(bundle, records, qualification_only=True)

    def test_readiness_records_deep_differential_and_no_overclaim(self) -> None:
        differential = self.readiness["differential"]
        self.assertEqual(32_768, sum(item["cases"] for item in differential.values()))
        self.assertTrue(all(item["mismatches"] == 0 for item in differential.values()))
        self.assertGreaterEqual(len(self.readiness["negative_controls"]), 80)
        self.assertEqual(0, self.readiness["payloads"]["embedded_payload_count"])
        self.assertFalse(self.readiness["claims"]["firmware_mutated"])
        self.assertFalse(self.readiness["production_ready"])


if __name__ == "__main__":
    unittest.main()
