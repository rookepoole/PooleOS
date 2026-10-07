import copy
import json
import tempfile
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
from runtime.native_kernel_profile_evidence import recorded_pair_errors
from tools import pooleos_release_gate as gate

ROOT = Path(__file__).resolve().parents[1]
PROFILES = (
    native_kernel_trap, native_kernel_cpu_policy, native_kernel_xstate_policy,
    native_kernel_xstate_exception, native_kernel_privilege_msr_policy,
)
RUN_PREFIXES = {
    native_kernel_cpu_policy: "cpu-policy-run",
    native_kernel_xstate_policy: "xstate-policy-run",
    native_kernel_xstate_exception: "xstate-exception-run",
    native_kernel_privilege_msr_policy: "privilege-msr-policy-run",
}


def recorded_pairs(profile, receipt):
    if profile is native_kernel_trap:
        for index, scenario in enumerate(receipt["execution"]["scenarios"]):
            name = scenario["scenario"]
            yield (index, scenario, f"{name}-run",
                   lambda markers, selected=name: profile.validate_markers(markers, selected))
    else:
        yield None, receipt["execution"], RUN_PREFIXES[profile], profile.validate_markers


def pair_mutations(pair, family):
    if family == "exit":
        for index in range(2):
            for label, value in (
                ("failure", 1), ("negative", -1), ("boolean", False),
                ("float", 0.0), ("string", "0"), ("null", None), ("missing", None),
            ):
                candidate = copy.deepcopy(pair)
                if label == "missing":
                    candidate["runs"][index].pop("qemu_exit_code")
                else:
                    candidate["runs"][index]["qemu_exit_code"] = value
                yield f"run-{index}-{label}", candidate
    elif family == "coverage":
        for label, key, value in (
            ("missing-count", "run_count", None), ("null-count", "run_count", None),
            ("float-count", "run_count", 2.0), ("boolean-count", "run_count", True),
            *((key, key, 1) for key in ("exact_marker_match", "exact_screenshot_match", "exact_pbp1_match")),
            ("missing-runs", "runs", None), ("null-runs", "runs", None),
            ("object-runs", "runs", {}), ("empty-runs", "runs", []),
            ("one-run", "runs", pair["runs"][:1]),
            ("three-runs", "runs", [*pair["runs"], pair["runs"][0]]),
            ("duplicate-runs", "runs", [pair["runs"][0], pair["runs"][0]]),
            ("reversed-runs", "runs", list(reversed(pair["runs"]))),
            ("null-run", "runs", [pair["runs"][0], None]),
        ):
            candidate = copy.deepcopy(pair)
            if label.startswith("missing-"):
                candidate.pop(key)
            else:
                candidate[key] = copy.deepcopy(value)
            yield label, candidate
    elif family == "evidence":
        first = pair["runs"][0]
        for path, value in (
            (("markers",), None), (("markers",), []), (("markers",), [None]),
            (("markers",), ["invalid-marker"]), (("marker_sha256",), "0" * 64),
            (("marker_summary",), None),
            (("marker_summary", "transfer_prefix", "marker_count"),
             float(first["marker_summary"]["transfer_prefix"]["marker_count"])),
            (("marker_summary", "transfer_prefix", "ordered_contract_match"), 1),
            (("pbp1_transcript",), None), (("pbp1_transcript", "core"), None),
            (("pbp1_transcript", "core"), {}), (("transcript_binding",), None),
            (("transcript_binding", "exact_transfer_fields_bound"), 1),
            (("independent_kernel_revalidation",), None),
            (("independent_kernel_revalidation", "contract_id"), "invalid"),
            (("independent_kernel_revalidation", "guest_host_exact_match"), 1),
            (("independent_kernel_revalidation", "parser_count"),
             float(first["independent_kernel_revalidation"]["parser_count"])),
            (("serial_debugcon_exact_match",), 1), (("pbp1_serial_debugcon_exact_match",), 1),
            (("screenshot",), None), (("screenshot", "nonblank"), 1),
            (("screenshot", "sha256"), None), (("screenshot", "sha256"), "invalid"),
        ):
            candidate = copy.deepcopy(pair)
            # Corrupt both runs identically so pair equality alone cannot reject them.
            for run in candidate["runs"]:
                target = run
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = copy.deepcopy(value)
            yield ".".join(path) + "=" + repr(value), candidate
    else:
        raise ValueError(f"unknown mutation family: {family}")


def control_mutations(receipt):
    for index, control in enumerate(receipt["negative_controls"]):
        for field in control:
            for label, value in (("wrong", "invalid"), ("null", None), ("boolean", False), ("missing", None)):
                candidate = copy.deepcopy(receipt)
                if label == "missing":
                    candidate["negative_controls"][index].pop(field)
                else:
                    candidate["negative_controls"][index][field] = value
                yield f"{index}.{field}.{label}", candidate
        candidate = copy.deepcopy(receipt)
        candidate["negative_controls"][index]["unverified_extra_result"] = "accepted"
        yield f"{index}.extra", candidate
    for label, value in (("null", None), ("object", {}), ("empty", []), ("string", "pass"),
                         ("short", receipt["negative_controls"][:-1]),
                         ("duplicate", [receipt["negative_controls"][0]] * len(receipt["negative_controls"])),
                         ("reverse", list(reversed(receipt["negative_controls"]))),
                         ("extra", receipt["negative_controls"] + [receipt["negative_controls"][0]])):
        candidate = copy.deepcopy(receipt)
        candidate["negative_controls"] = value
        yield f"controls.{label}", candidate
    for index, value in enumerate((None, [], 1, True, "pass")):
        yield f"root.{index}", value


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

    def test_recorded_pair_consistency_rejects_malformed_evidence(self) -> None:
        # Historical payload consistency is deliberately separate from source qualification.
        for profile in PROFILES:
            for _, pair, prefix, validator in recorded_pairs(profile, self.candidate(profile)):
                self.assertEqual(recorded_pair_errors(pair, prefix, validator, profile.CONTRACT_ID), [])
                for family in ("exit", "coverage", "evidence"):
                    for label, candidate in pair_mutations(pair, family):
                        with self.subTest(profile=profile.CONTRACT_ID, pair=prefix, family=family, case=label):
                            errors = recorded_pair_errors(candidate, prefix, validator, profile.CONTRACT_ID)
                            self.assertTrue(errors)
                            if family == "exit":
                                self.assertTrue(any("recorded emulator exit" in error for error in errors))

    def assert_profile_and_gate_reject_pair_mutations(self, family):
        for profile in PROFILES:
            baseline = self.candidate(profile)
            check = getattr(gate, "check_" + profile.__name__.split(".")[-1] + "_readiness")
            self.assertEqual(profile.readiness_errors(baseline, ROOT), [])
            positive = check(ROOT / profile.READINESS_RELATIVE)
            self.assertTrue(positive["ok"], positive)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "candidate.json"
                for index, pair, prefix, _ in recorded_pairs(profile, baseline):
                    for label, mutated in pair_mutations(pair, family):
                        with self.subTest(profile=profile.CONTRACT_ID, pair=prefix, family=family, case=label):
                            candidate = copy.deepcopy(baseline)
                            if index is None:
                                candidate["execution"] = mutated
                            else:
                                candidate["execution"]["scenarios"][index] = mutated
                            errors = profile.readiness_errors(candidate, ROOT)
                            self.assertTrue(any("recorded" in error for error in errors), errors)
                            path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                            rejected = check(path)
                            self.assertFalse(rejected["ok"], rejected)
                            if family == "exit":
                                self.assertIn("recorded emulator exit", rejected["detail"])

    def test_profile_and_gate_reject_invalid_recorded_exits(self) -> None:
        self.assert_profile_and_gate_reject_pair_mutations("exit")

    def test_profile_and_gate_reject_incomplete_recorded_runs(self) -> None:
        self.assert_profile_and_gate_reject_pair_mutations("coverage")

    def test_profile_and_gate_reparse_typed_recorded_evidence(self) -> None:
        self.assert_profile_and_gate_reject_pair_mutations("evidence")

    def test_profile_and_gate_reject_malformed_control_records(self) -> None:
        for profile in PROFILES:
            baseline = self.candidate(profile)
            check = getattr(gate, "check_" + profile.__name__.split(".")[-1] + "_readiness")
            self.assertEqual(profile.readiness_errors(baseline, ROOT), [])
            self.assertTrue(check(ROOT / profile.READINESS_RELATIVE)["ok"])
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "candidate.json"
                for label, candidate in control_mutations(baseline):
                    with self.subTest(profile=profile.CONTRACT_ID, case=label):
                        errors = profile.readiness_errors(candidate, ROOT)
                        self.assertTrue(errors)
                        self.assertTrue(all(isinstance(error, str) for error in errors))
                        path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                        result = check(path)
                        self.assertFalse(result["ok"], result["detail"])

    def test_control_validator_rejects_non_json_and_wrong_typed_evidence(self) -> None:
        from runtime.native_kernel_profile_evidence import recorded_control_errors

        expected = [{"id": "test", "status": "pass", "expected": "rejected"}]
        self.assertEqual(recorded_control_errors(expected, ("test",), "TEST"), [])
        for value in (None, {"test"}, float("nan"), float("inf"),
                      [{"id": "test", "status": True, "expected": "rejected"}]):
            with self.subTest(value=value):
                self.assertTrue(recorded_control_errors(value, ("test",), "TEST"))


if __name__ == "__main__":
    unittest.main()
