from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import pooleos_release_gate as gate


class NativeDependencyReleaseGateTests(unittest.TestCase):
    def test_entry_gate_rejects_stale_and_wrong_typed_image_pins(self) -> None:
        module = gate.native_kernel_entry
        receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
        positive = gate.check_native_kernel_entry_readiness()
        self.assertTrue(positive["ok"], positive["detail"])
        mutations = [
            (("summary", "rust_host_tests_passed"), 243),
            (("summary", "rust_host_tests_total"), 243),
            (("product", "relocation_count"), 1321),
            (("product", "canonical_sha256"), "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625"),
            (("summary", "rust_host_tests_passed"), 246.0),
            (("summary", "production_claim_count"), False),
            (("product", "canonical_byte_count"), 530072.0),
            (("product", "image_byte_count"), 602112.0),
            (("product", "entry_offset"), 40960.0),
            (("product", "relocation_count"), 1327.0),
            (("summary",), None),
            (("product",), None),
        ]
        for fields, value in mutations:
            with self.subTest(fields=fields, value=value):
                candidate = copy.deepcopy(receipt)
                target = candidate
                for field in fields[:-1]:
                    target = target[field]
                target[fields[-1]] = value
                # Exercise the release gate independently of the component validator.
                with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])), \
                     patch.object(module, "readiness_errors", return_value=[]):
                    result = gate.check_native_kernel_entry_readiness()
                self.assertFalse(result["ok"], result["detail"])

    def test_current_cpu_gates_reject_stale_identity_and_promotion(self) -> None:
        rejected = 0
        for profile in ("trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"):
            module = importlib.import_module("runtime.native_kernel_" + profile)
            receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
            check_fn = getattr(gate, "check_native_kernel_" + profile + "_readiness")
            positive = check_fn()
            self.assertTrue(positive["ok"], positive["detail"])
            mutations = [
                (("production_ready",), True),
                (("production_promotion_allowed",), True),
                (("summary", "authority_grants"), 1),
            ]
            if profile == "trap":
                mutations.extend([
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4"),
                    (("build", "kernel_entry", "product", "relocation_count"), 1319),
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625"),
                    (("build", "kernel_entry", "product", "relocation_count"), 1321),
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8"),
                    (("build", "kernel_entry", "product", "relocation_count"), 1327),
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1"),
                    (("build", "kernel_entry", "product", "canonical_sha256"), "0" * 64),
                    (("build", "kernel_entry", "product", "canonical_sha256"), None),
                    (("build", "kernel_entry", "product", "canonical_sha256"), False),
                    (("build", "kernel_entry", "product", "canonical_sha256"), ""),
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31"),
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "72C37783A5729229E6A259E38DC8DF55034FD467B77839FFFC4AA62B66E33EBF"),
                    (("build", "kernel_entry", "product", "canonical_sha256"),
                     "AE3422B2D44E6EC87AB1D5B51414C023E46F2EE3461A0D0895B9D1242E10D25A"),
                    (("build", "kernel_entry", "product", "relocation_count"), 1323),
                    (("build", "kernel_entry", "product", "relocation_count"), 1326.0),
                    (("build", "kernel_entry", "product", "relocation_count"), None),
                    (("build", "kernel_entry", "product", "relocation_count"), False),
                ])
            for field_path, value in mutations:
                with self.subTest(profile=profile, field=field_path):
                    candidate = copy.deepcopy(receipt)
                    target = candidate
                    for key in field_path[:-1]:
                        target = target[key]
                    self.assertTrue(type(target[field_path[-1]]) is not type(value)
                                    or target[field_path[-1]] != value)
                    target[field_path[-1]] = value
                    with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                        if field_path[0] == "build":
                            # Isolate the aggregate identity gate after its genuine positive baseline.
                            with patch.object(module, "readiness_errors", return_value=[]):
                                result = check_fn()
                        else:
                            result = check_fn()
                    self.assertFalse(result["ok"], result["detail"])
                    rejected += 1
        self.assertEqual(rejected, 33)

    def test_cpu_gates_reject_malformed_nested_build_without_exceptions(self) -> None:
        rejected = 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            for profile in ("trap", "cpu_policy", "xstate_policy", "xstate_exception", "privilege_msr_policy"):
                module = importlib.import_module("runtime.native_kernel_" + profile)
                receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
                check_fn = getattr(gate, "check_native_kernel_" + profile + "_readiness")
                positive = check_fn()
                self.assertTrue(positive["ok"], positive["detail"])
                fields = [("build",), ("build", "kernel_entry"),
                          ("build", "kernel_entry", "product")]
                if profile == "cpu_policy":
                    fields.append(("build", "source_audit"))
                for field_path in fields:
                    for value in (None, [], False, "invalid", {}):
                        with self.subTest(profile=profile, field=field_path, value=value):
                            candidate = copy.deepcopy(receipt)
                            target = candidate
                            for key in field_path[:-1]:
                                target = target[key]
                            target[field_path[-1]] = value
                            path.write_text(json.dumps(candidate), encoding="utf-8")
                            result = check_fn(path)
                            self.assertFalse(result["ok"], result["detail"])
                            rejected += 1
        self.assertEqual(rejected, 80)

    def test_current_ipi_gate_independently_rejects_prior_kernel_pins(self) -> None:
        module = gate.native_kernel_smp_ipi
        receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
        positive = gate.check_native_kernel_smp_ipi_readiness()
        self.assertTrue(positive["ok"], positive["detail"])
        self.assertEqual(module.readiness_errors(receipt), [])
        current = receipt["build"]["kernel_entry"]["product"]["canonical_sha256"]
        for wrong in (
            "A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31",
            "B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8",
            "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625",
            "B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1",
            "0" * 64, False, None, "",
        ):
            with self.subTest(wrong=wrong):
                self.assertNotEqual(wrong, current)
                candidate = copy.deepcopy(receipt)
                candidate["build"]["kernel_entry"]["product"]["canonical_sha256"] = wrong
                # Isolate the aggregate pin after validating the genuine positive.
                with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])), \
                     patch.object(module, "readiness_errors", return_value=[]), \
                     patch.object(gate.native_kernel_entry, "readiness_errors", return_value=[]):
                    result = gate.check_native_kernel_smp_ipi_readiness()
                self.assertFalse(result["ok"], result["detail"])
                self.assertIn("embedded kernel identity changed", result["detail"])

    def test_current_deferred_gate_independently_rejects_stale_linked_identity(self) -> None:
        module = gate.native_kernel_scheduler_deferred
        receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
        positive = gate.check_native_kernel_scheduler_deferred_readiness()
        self.assertTrue(positive["ok"], positive["detail"])
        self.assertEqual(module.readiness_errors(receipt), [])
        mutations = [("canonical_sha256", wrong) for wrong in (
            "B19D4F7E854ECED3495D88C00F7379061B913EF00477FBD3701929B2F77D80F1",
            "B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8",
            "A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31",
            "0" * 64, None, False, "",
        )]
        mutations.extend(("relocation_count", wrong) for wrong in (1305, 1319, 1321, 1326, 1323.0, None, False))
        for field, wrong in mutations:
            with self.subTest(field=field, wrong=wrong):
                candidate = copy.deepcopy(receipt)
                actual = candidate["build"]["linked_switch_audit"][field]
                self.assertTrue(type(actual) is not type(wrong) or actual != wrong)
                candidate["build"]["linked_switch_audit"][field] = wrong
                # Isolate aggregate admission only after the genuine positive passes.
                with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])), \
                     patch.object(module, "readiness_errors", return_value=[]):
                    result = gate.check_native_kernel_scheduler_deferred_readiness()
                self.assertFalse(result["ok"], result["detail"])
                self.assertIn("host oracle, source, or linked switch audit changed", result["detail"])

    def test_current_smp_gate_independently_rejects_stale_and_wrong_typed_pins(self) -> None:
        module = gate.native_kernel_scheduler_smp
        receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
        positive = gate.check_native_kernel_scheduler_smp_readiness()
        self.assertTrue(positive["ok"], positive["detail"])
        self.assertEqual(module.readiness_errors(receipt), [])
        for field, wrong in (("canonical_sha256", "A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31"),
                             ("relocation_count", 1326), ("relocation_count", 1323.0)):
            candidate = copy.deepcopy(receipt)
            actual = candidate["build"]["linked_invlpg_audit"][field]
            self.assertTrue(type(actual) is not type(wrong) or actual != wrong)
            candidate["build"]["linked_invlpg_audit"][field] = wrong
            with self.subTest(field=field, wrong=wrong), patch.object(module, "readiness_errors", return_value=[]), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                result = gate.check_native_kernel_scheduler_smp_readiness()
                self.assertFalse(result["ok"], result["detail"])
                self.assertIn("host oracle, source, or linked INVLPG audit changed", result["detail"])

    def test_stale_host_and_linked_image_pins_are_rejected(self) -> None:
        rejected = 0
        profiles = {
            "interrupt_time": ("summary", "kernel_host_tests_total"),
            "smp_first_ap": ("summary", "kernel_host_tests_total"),
            "smp_percpu_runtime": ("summary", "kernel_host_tests_total"),
            "scheduler": ("summary", "kernel_host_tests"),
            "scheduler_preempt": ("summary", "kernel_host_tests"),
            "scheduler_deferred": ("build", "kernel_entry", "summary", "rust_host_tests_total"),
            "scheduler_smp": ("build", "kernel_entry", "summary", "rust_host_tests_total"),
            "scheduler_ap_workers": ("build", "kernel_entry", "summary", "rust_host_tests_total"),
            "scheduler_smp_preempt": ("build", "kernel_entry", "summary", "rust_host_tests_total"),
            "atomics": ("kernel_summary", "host_tests_total"),
            "locks": ("build", "kernel_entry", "host_tests", "test_count"),
        }
        for profile, path in profiles.items():
            module = importlib.import_module("runtime.native_kernel_" + profile)
            receipt = module.read_json(module.ROOT / module.READINESS_RELATIVE)
            name = "scheduler_preemption" if profile == "scheduler_preempt" else profile
            check_fn = getattr(gate, "check_native_kernel_" + name + "_readiness")
            positive = check_fn()
            self.assertTrue(positive["ok"], positive["detail"])
            mutations = [(path, 219), (path, 228), (path, 243)]
            if profile in {"scheduler_deferred", "scheduler_smp", "scheduler_ap_workers", "scheduler_smp_preempt"}:
                audit_name = "linked_switch_audit" if profile == "scheduler_deferred" else "linked_invlpg_audit"
                audit = receipt.get("build", {}).get(audit_name)
                self.assertIsInstance(audit, dict)
                mutations.extend([
                    (("build", audit_name, "relocation_count"), 1305),
                    (("build", audit_name, "relocation_count"), 1319),
                    (("build", audit_name, "relocation_count"), 1321),
                    (("build", audit_name, "canonical_sha256"),
                     "18EDADA10E141DBADA8C95C1C0B3454696122C5E96C528F45E0AECE6ADD2F07D"),
                    (("build", audit_name, "canonical_sha256"),
                     "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4"),
                    (("build", audit_name, "canonical_sha256"),
                     "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625"),
                ])
            if profile == "scheduler_smp":
                mutations.append((("build", "source_audit", "focused_rust_test_count"), 8))
            for field_path, stale in mutations:
                with self.subTest(profile=profile, field=field_path):
                    candidate = copy.deepcopy(receipt)
                    target = candidate
                    for key in field_path[:-1]:
                        target = target[key]
                    self.assertNotEqual(target[field_path[-1]], stale)
                    target[field_path[-1]] = stale
                    # Isolate acceptance pins after validating the genuine generated baseline.
                    with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])), \
                         patch.object(module, "readiness_errors", return_value=[]):
                        result = check_fn()
                    self.assertFalse(result["ok"], result["detail"])
                    rejected += 1
        module = gate.native_kernel_smp_ipi
        candidate = module.read_json(module.ROOT / module.READINESS_RELATIVE)
        self.assertTrue(gate.check_native_kernel_smp_ipi_readiness()["ok"])
        candidate["build"]["kernel_entry"]["product"]["canonical_sha256"] = (
            "8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625"
        )
        with patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])), \
             patch.object(module, "readiness_errors", return_value=[]), \
             patch.object(gate.native_kernel_entry, "readiness_errors", return_value=[]):
            result = gate.check_native_kernel_smp_ipi_readiness()
        self.assertFalse(result["ok"], result["detail"])
        self.assertIn("embedded kernel identity changed", result["detail"])
        self.assertEqual(rejected + 1, 59)


if __name__ == "__main__":
    unittest.main()
