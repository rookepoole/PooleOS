import copy
import importlib
import json
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_entry as entry

ROOT = Path(__file__).resolve().parents[1]
PROFILE_NAMES = (
    "physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap",
    "smp_percpu_runtime", "smp_ipi", "scheduler", "scheduler_preempt",
    "scheduler_deferred", "scheduler_smp", "scheduler_ap_workers",
    "scheduler_smp_preempt", "atomics", "locks",
)
PROFILES = tuple(importlib.import_module("runtime.native_kernel_" + name) for name in PROFILE_NAMES)


def entry_location(profile):
    return ("kernel_summary", "entry_readiness") if profile.CONTRACT_ID == "PKATOM1" else ("build", "kernel_entry")


class NativeMemoryEntryProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = entry.read_json(ROOT / entry.READINESS_RELATIVE)

    def candidate(self, profile):
        # Synthetic provenance input, never a substituted execution receipt.
        report = json.loads((ROOT / profile.READINESS_RELATIVE).read_text(encoding="utf-8"))
        report["inputs"] = profile.expected_inputs(ROOT)
        section, field = entry_location(profile)
        report[section][field] = copy.deepcopy(self.entry)
        return report

    def test_current_entry_passes_the_provenance_check(self) -> None:
        self.assertEqual(entry.readiness_errors(self.entry, ROOT), [])
        for profile in PROFILES:
            with self.subTest(profile=profile.CONTRACT_ID):
                errors = profile.readiness_errors(self.candidate(profile), ROOT)
                self.assertFalse(any("embedded kernel entry" in str(error) for error in errors), errors)

    def test_stale_malformed_and_type_substituted_embedded_entry_rejects(self) -> None:
        for profile in PROFILES:
            baseline = self.candidate(profile)
            section, field = entry_location(profile)
            cases = []
            for value in (None, [], "invalid", {}):
                candidate = copy.deepcopy(baseline)
                candidate[section] = value
                cases.append(candidate)
                candidate = copy.deepcopy(baseline)
                candidate[section][field] = value
                cases.append(candidate)
            for part, key, value in (
                ("product", "linked_sha256", "0" * 64),
                ("product", "canonical_sha256", "0" * 64),
                ("host_tests", "test_pass_count", 0),
                ("bindings", "implementation_inputs", []),
                ("product", "linked_byte_count", float(self.entry["product"]["linked_byte_count"])),
            ):
                candidate = copy.deepcopy(baseline)
                candidate[section][field][part][key] = value
                cases.append(candidate)
            for value in (True, 0):
                candidate = copy.deepcopy(baseline)
                candidate[section][field]["production_ready"] = value
                cases.append(candidate)
            candidate = copy.deepcopy(baseline)
            candidate.pop(section)
            cases.append(candidate)
            for index, candidate in enumerate(cases):
                with self.subTest(profile=profile.CONTRACT_ID, case=index):
                    errors = profile.readiness_errors(candidate, ROOT)
                    self.assertTrue(any("embedded kernel entry" in str(error) for error in errors), errors)

    def test_invalid_current_dependency_rejects(self) -> None:
        original = entry.read_json
        stale = copy.deepcopy(self.entry)
        stale["bindings"]["implementation_inputs"] = []
        for profile in PROFILES:
            for invalid in (None, [], {"summary": None}, stale):
                with self.subTest(profile=profile.CONTRACT_ID, dependency=invalid):
                    candidate = self.candidate(profile)

                    def read(path):
                        return invalid if path == ROOT / entry.READINESS_RELATIVE else original(path)

                    with mock.patch.object(entry, "read_json", side_effect=read):
                        errors = profile.readiness_errors(candidate, ROOT)
                    self.assertTrue(any("embedded kernel entry" in str(error) for error in errors), errors)

    def test_provenance_inputs_are_bound(self) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile.CONTRACT_ID):
                for path in (
                    "runtime/native_kernel_profile_evidence.py",
                    "tests/test_native_memory_entry_provenance.py",
                    "runs/native_kernel_entry_readiness.json",
                ):
                    self.assertIn(path, profile.IMPLEMENTATION_INPUTS)


if __name__ == "__main__":
    unittest.main()
