import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from runtime import (
    native_kernel_entry as entry,
    native_kernel_trap,
    native_kernel_cpu_policy,
    native_kernel_xstate_policy,
    native_kernel_xstate_exception,
    native_kernel_privilege_msr_policy,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILES = (
    native_kernel_trap, native_kernel_cpu_policy, native_kernel_xstate_policy,
    native_kernel_xstate_exception, native_kernel_privilege_msr_policy,
)


class NativeCpuEntryProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = entry.read_json(ROOT / entry.READINESS_RELATIVE)

    def candidate(self, profile):
        return json.loads((ROOT / profile.READINESS_RELATIVE).read_text(encoding="utf-8"))

    def test_profiles_accept_current_entry_provenance(self) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile.CONTRACT_ID):
                self.assertEqual(profile.readiness_errors(self.candidate(profile), ROOT), [])

    def test_profiles_reject_stale_or_malformed_embedded_entry(self) -> None:
        for profile in PROFILES:
            baseline = self.candidate(profile)
            self.assertEqual(profile.readiness_errors(baseline, ROOT), [])
            cases = []
            for value in (None, [], "invalid", {}):
                candidate = copy.deepcopy(baseline)
                candidate["build"] = value
                cases.append(candidate)
                candidate = copy.deepcopy(baseline)
                candidate["build"]["kernel_entry"] = value
                cases.append(candidate)
            for section, key, value in (
                ("product", "linked_sha256", "0" * 64),
                ("product", "canonical_sha256", "0" * 64),
                ("host_tests", "test_pass_count", 0),
                ("bindings", "implementation_inputs", []),
                ("product", "linked_byte_count", float(self.entry["product"]["linked_byte_count"])),
            ):
                candidate = copy.deepcopy(baseline)
                candidate["build"]["kernel_entry"][section][key] = value
                cases.append(candidate)
            candidate = copy.deepcopy(baseline)
            candidate["build"]["kernel_entry"]["production_ready"] = True
            cases.append(candidate)
            candidate = copy.deepcopy(baseline)
            candidate["build"]["kernel_entry"]["production_ready"] = 0
            cases.append(candidate)
            candidate = copy.deepcopy(baseline)
            candidate.pop("build")
            cases.append(candidate)
            for index, candidate in enumerate(cases):
                with self.subTest(profile=profile.CONTRACT_ID, case=index):
                    errors = profile.readiness_errors(candidate, ROOT)
                    self.assertTrue(any("embedded kernel entry" in error for error in errors), errors)

    def test_current_entry_dependency_must_itself_validate(self) -> None:
        original = entry.read_json
        stale = copy.deepcopy(self.entry)
        stale["bindings"]["implementation_inputs"] = []
        for profile in PROFILES:
            baseline = self.candidate(profile)
            self.assertEqual(profile.readiness_errors(baseline, ROOT), [])
            for invalid in (None, [], {"summary": None}, stale):
                with self.subTest(profile=profile.CONTRACT_ID, dependency=invalid):
                    candidate = copy.deepcopy(baseline)
                    def read(path):
                        return invalid if path == ROOT / entry.READINESS_RELATIVE else original(path)
                    with mock.patch.object(entry, "read_json", side_effect=read):
                        errors = profile.readiness_errors(candidate, ROOT)
                    self.assertTrue(any("embedded kernel entry" in error for error in errors), errors)

    def test_shared_validation_sources_are_bound(self) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile.CONTRACT_ID):
                self.assertIn("runtime/native_kernel_profile_evidence.py", profile.IMPLEMENTATION_INPUTS)
                self.assertIn("tests/test_native_cpu_entry_provenance.py", profile.IMPLEMENTATION_INPUTS)
                self.assertIn("runs/native_kernel_entry_readiness.json", profile.IMPLEMENTATION_INPUTS)


if __name__ == "__main__":
    unittest.main()
