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

from runtime import native_symbols as psym1  # noqa: E402


class NativeSymbolTests(unittest.TestCase):
    def test_contract_and_golden_vectors_are_canonical(self) -> None:
        contract = psym1.read_json(ROOT / psym1.CONTRACT_RELATIVE)
        golden = psym1.read_json(ROOT / psym1.GOLDEN_RELATIVE)
        self.assertEqual(psym1.contract_errors(contract), [])
        self.assertEqual(psym1.golden_errors(golden), [])
        self.assertEqual(contract, psym1.expected_contract())
        self.assertEqual(golden, psym1.make_golden_vectors())

    def test_generator_check_passes_without_writing(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_native_symbol_vectors.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("PSYM1_GENERATION PASS", completed.stdout)

    def test_checked_in_fixtures_match_oracle(self) -> None:
        expected = {
            "psym1-canonical.bin": psym1.canonical_bundle(),
            "psym1-minimal.bin": psym1.minimal_bundle(),
            "psym1-boundary.bin": psym1.boundary_bundle(),
        }
        for name, data in expected.items():
            self.assertEqual((ROOT / "specs/fixtures" / name).read_bytes(), data)
            self.assertEqual(psym1.parse(data).raw, data)

    def test_canonical_identity_and_public_symbols_are_exact(self) -> None:
        bundle = psym1.parse(psym1.canonical_bundle())
        self.assertEqual(bundle.identity, psym1.canonical_identity())
        self.assertEqual(bundle.segments, psym1.canonical_segments())
        self.assertEqual(bundle.symbols, psym1.canonical_symbols())
        self.assertEqual(bundle.image_bytes, 0x42000)
        self.assertEqual(bundle.entry_offset, 0x8000)

    def test_lookup_handles_hits_gaps_slides_and_bounds(self) -> None:
        bundle = psym1.parse(psym1.canonical_bundle())
        base = bundle.preferred_virtual_base + 5 * bundle.slide_alignment
        rust_entry = next(
            symbol for symbol in bundle.symbols if symbol.name == "poole_kernel_rust_entry"
        )
        result = psym1.lookup(bundle, base, base + rust_entry.start_offset + 37)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.symbol.name, "poole_kernel_rust_entry")
        self.assertEqual(result.symbol_offset, 37)
        self.assertLessEqual(result.steps, psym1.MAX_LOOKUP_STEPS)
        entry = bundle.symbols[0]
        self.assertIsNone(
            psym1.lookup(bundle, base, base + entry.start_offset + entry.byte_count)
        )
        with self.assertRaisesRegex(psym1.SymbolError, "psym_lookup_base"):
            psym1.lookup(bundle, base + 1, base + 0x8000)
        with self.assertRaisesRegex(psym1.SymbolError, "psym_lookup_address"):
            psym1.lookup(bundle, base, base + bundle.image_bytes)

    def test_body_and_name_integrity_fail_closed(self) -> None:
        body = bytearray(psym1.canonical_bundle())
        body[psym1.HEADER_BYTES] ^= 1
        with self.assertRaisesRegex(psym1.SymbolError, "psym_body_digest"):
            psym1.parse(bytes(body))

        name = bytearray(psym1.canonical_bundle())
        string_offset = struct.unpack_from("<Q", name, 64)[0]
        name[string_offset] = ord("/")
        name[304:336] = hashlib.sha256(name[psym1.HEADER_BYTES :]).digest()
        with self.assertRaisesRegex(psym1.SymbolError, "psym_symbol_name_ascii"):
            psym1.parse(bytes(name))

    def test_segments_are_dense_wx_exclusive_and_symbols_nonoverlapping(self) -> None:
        bundle = psym1.parse(psym1.canonical_bundle())
        previous_end = 0
        for segment in bundle.segments:
            self.assertEqual(segment.start_offset, previous_end)
            self.assertFalse(
                segment.flags & psym1.SEGMENT_WRITE
                and segment.flags & psym1.SEGMENT_EXECUTE
            )
            previous_end += segment.byte_count
        self.assertEqual(previous_end, bundle.image_bytes)
        for left, right in zip(bundle.symbols, bundle.symbols[1:], strict=False):
            self.assertLessEqual(left.start_offset + left.byte_count, right.start_offset)

    def test_unsigned_development_context_is_denied(self) -> None:
        bundle = psym1.parse(psym1.canonical_bundle())
        development = psym1.development_consumption_context(bundle)
        errors = psym1.consumption_errors(bundle, development)
        self.assertIn("psym_activation_outer_signature", errors)
        self.assertIn("psym_activation_inner_signature", errors)
        self.assertIn("psym_activation_manifest_signature", errors)
        with self.assertRaisesRegex(psym1.SymbolError, "psym_activation_outer_signature"):
            psym1.authorize_consumption(bundle, development)

    def test_each_consumption_precondition_fails_independently(self) -> None:
        bundle = psym1.parse(psym1.canonical_bundle())
        qualified = psym1.synthetic_qualified_consumption_context(bundle)
        self.assertEqual(psym1.consumption_errors(bundle, qualified), [])
        mutations = (
            {"outer_signature_verified": False},
            {"inner_signature_verified": False},
            {"manifest_signature_verified": False},
            {"kernel_signature_verified": False},
            {"identity_evidence_verified": False},
            {"stripped_correspondence_verified": False},
            {"dwarf5_verified": False},
            {"public_policy_verified": False},
            {"source_paths_absent": False},
            {"pointer_redaction_enabled": False},
            {"diagnostics_authorized": False},
            {"authority_effect_requested": True},
        )
        for mutation in mutations:
            self.assertTrue(
                psym1.consumption_errors(bundle, dataclasses.replace(qualified, **mutation))
            )

    def test_debug_elf_oracle_rejects_non_elf_and_host_paths(self) -> None:
        with self.assertRaisesRegex(psym1.SymbolError, "psym_debug_elf_size"):
            psym1.inspect_debug_elf(b"not an elf")
        synthetic = bytearray(64)
        synthetic[:7] = b"\x7fELF\x02\x01\x01"
        with self.assertRaises(psym1.SymbolError):
            psym1.inspect_debug_elf(bytes(synthetic) + b"C:\\Users\\private")

    def test_readiness_receipt_remains_bound_and_non_promoting(self) -> None:
        path = ROOT / psym1.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PSYM1 qualification receipt has not been generated")
        readiness = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(psym1.readiness_errors(readiness), [])
        self.assertFalse(readiness["production_ready"])
        self.assertFalse(readiness["production_promotion_allowed"])
        self.assertFalse(readiness["claims"]["symbol_consumption_enabled"])


if __name__ == "__main__":
    unittest.main()
