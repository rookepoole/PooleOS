from __future__ import annotations

import dataclasses
import hashlib
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_policy as ppol1  # noqa: E402


class NativePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = ppol1.read_json(ROOT / ppol1.CONTRACT_RELATIVE)
        cls.golden = ppol1.read_json(ROOT / ppol1.GOLDEN_RELATIVE)
        cls.readiness = ppol1.read_json(ROOT / ppol1.READINESS_RELATIVE)

    def test_contract_vectors_and_readiness_validate(self) -> None:
        self.assertEqual([], ppol1.contract_errors(self.contract, ROOT))
        self.assertEqual([], ppol1.golden_errors(self.golden, ROOT))
        self.assertEqual([], ppol1.readiness_errors(self.readiness, ROOT))

    def test_generated_outputs_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_native_policy_vectors.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_canonical_bundle_is_deterministic_and_cross_bound(self) -> None:
        first = ppol1.canonical_bundle()
        self.assertEqual(first, ppol1.canonical_bundle())
        bundle = ppol1.parse(first)
        initial = ppol1.pinit1.parse(ppol1.pinit1.canonical_bundle())
        ppol1.validate_initial_system(bundle, initial)
        self.assertEqual(6, len(bundle.modes))
        self.assertEqual(11, len(bundle.capability_rules))

    def test_minimal_and_boundary_vectors_cover_rule_limits(self) -> None:
        self.assertEqual(1, len(ppol1.parse(ppol1.minimal_bundle()).capability_rules))
        self.assertEqual(
            ppol1.MAX_CAPABILITY_RULES,
            len(ppol1.parse(ppol1.boundary_bundle()).capability_rules),
        )

    def test_header_and_body_substitution_fail_closed(self) -> None:
        original = ppol1.canonical_bundle()
        magic = bytearray(original)
        magic[0] ^= 1
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_magic"):
            ppol1.parse(bytes(magic))
        body = bytearray(original)
        body[-1] ^= 1
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_body_digest"):
            ppol1.parse(bytes(body))

    def test_safe_floor_cannot_be_widened(self) -> None:
        original = bytearray(ppol1.canonical_bundle())
        safe = ppol1.HEADER_BYTES + ppol1.MODE_RECORD_BYTES
        struct.pack_into("<Q", original, safe + 8, ppol1.KNOWN_EFFECTS)
        struct.pack_into("<Q", original, safe + 24, 0)
        original[416:448] = hashlib.sha256(original[ppol1.HEADER_BYTES :]).digest()
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_safe_floor"):
            ppol1.parse(bytes(original))

    def test_parent_capability_cannot_amplify(self) -> None:
        original = bytearray(ppol1.canonical_bundle())
        rules = ppol1.HEADER_BYTES + ppol1.MODE_COUNT * ppol1.MODE_RECORD_BYTES
        child = rules + 3 * ppol1.CAPABILITY_RECORD_BYTES
        struct.pack_into("<Q", original, child + 24, ppol1.KNOWN_RIGHTS)
        original[416:448] = hashlib.sha256(original[ppol1.HEADER_BYTES :]).digest()
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_capability_ceiling_rights"):
            ppol1.parse(bytes(original))

    def test_development_denies_at_outer_signature(self) -> None:
        bundle = ppol1.parse(ppol1.canonical_bundle())
        errors = ppol1.activation_errors(bundle, ppol1.development_activation_context(bundle))
        self.assertEqual("ppol_activation_outer_signature", errors[0])

    def test_all_six_modes_produce_only_dry_run_decisions(self) -> None:
        bundle = ppol1.parse(ppol1.canonical_bundle())
        for mode in ppol1.MODES:
            decision = ppol1.authorize_dry_run_decision(
                bundle, ppol1.synthetic_qualified_activation_context(bundle, mode=mode)
            )
            self.assertTrue(decision.qualification_only)
            self.assertTrue(decision.audit_receipt_required)

    def test_firmware_mode_requires_physical_presence_and_separate_authority(self) -> None:
        bundle = ppol1.parse(ppol1.canonical_bundle())
        context = ppol1.synthetic_qualified_activation_context(bundle, mode=ppol1.MODE_FIRMWARE)
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_activation_physical_presence"):
            ppol1.authorize_dry_run_decision(
                bundle, dataclasses.replace(context, physical_presence_verified=False)
            )
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_activation_separate_authority"):
            ppol1.authorize_dry_run_decision(
                bundle, dataclasses.replace(context, separate_authority_verified=False)
            )

    def test_receipt_substitution_and_nondurable_storage_fail_closed(self) -> None:
        bundle = ppol1.parse(ppol1.canonical_bundle())
        plan = ppol1.authorize_dry_run_decision(
            bundle, ppol1.synthetic_qualified_activation_context(bundle)
        )
        receipt = ppol1.synthetic_receipt(plan)
        ppol1.verify_receipt(plan, receipt)
        with self.assertRaisesRegex(ppol1.PolicyError, "ppol_receipt_not_durable"):
            ppol1.verify_receipt(plan, dataclasses.replace(receipt, durable=False))

    def test_readiness_records_differential_depth_without_overclaim(self) -> None:
        self.assertGreaterEqual(
            sum(item["cases"] for item in self.readiness["differential"].values()),
            32_768,
        )
        self.assertTrue(
            all(item["mismatches"] == 0 for item in self.readiness["differential"].values())
        )
        self.assertGreaterEqual(len(self.readiness["negative_controls"]), 80)
        self.assertFalse(self.readiness["claims"]["live_policy_enforcement"])
        self.assertFalse(self.readiness["claims"]["pooleglyph_executable_authority"])
        self.assertFalse(self.readiness["production_ready"])


if __name__ == "__main__":
    unittest.main()
