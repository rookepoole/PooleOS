from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_smp_first_ap as smp_first_ap
from runtime import native_pooleboot
from tests.test_native_cpu_entry_provenance import pair_mutations
from tools import pooleos_release_gate, qualify_native_kernel_smp_first_ap


def recorded_receipt_mutations(baseline):
    for family in ("exit", "coverage", "evidence"):
        for label, pair in pair_mutations(baseline["execution"], family):
            if label == "exact_marker_match":
                pair["static_markers_exact_match"] = pair.pop("exact_marker_match")
            candidate = copy.deepcopy(baseline)
            candidate["execution"] = pair
            yield family, label, candidate

    def changed(path, value):
        candidate = copy.deepcopy(baseline)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return candidate

    for path in (("execution",), ("execution", "observation"), ("summary",)):
        yield "shape", str(path), changed(path, None)
    for key, value in (("virtual_cpu_count", 2.0), ("dynamic_tsc_and_checksum_fields_revalidated", 1)):
        yield "dynamic-policy", key, changed(("execution", key), value)
    for section, fields in baseline["execution"]["observation"].items():
        yield "observation", section, changed(("execution", "observation", section), None)
        if section == "transfer_prefix":
            continue
        for key, value in fields.items():
            substitute = int(value) if type(value) is bool else float(value) if type(value) is int else "invalid"
            for label, replacement in (("null", None), ("type-or-value", substitute)):
                path = ("execution", "observation", section, key)
                yield "observation", str(path) + label, changed(path, replacement)
    for key, value in baseline["summary"].items():
        for label, replacement in (("null", None), ("type", float(value))):
            yield "summary", key + label, changed(("summary", key), replacement)
    for field, value in (("checksum", "0x0000000000000000"), ("parked", "0")):
        candidate = copy.deepcopy(baseline)
        for run in candidate["execution"]["runs"]:
            run["markers"][35] = qualify_native_kernel_smp_first_ap._set_field(run["markers"][35], field, value)
        yield "raw-stop", field, candidate


class NativeKernelSmpFirstApTests(unittest.TestCase):
    def test_contract_is_exact_and_non_promoting(self) -> None:
        contract = smp_first_ap.read_json(smp_first_ap.ROOT / smp_first_ap.CONTRACT_RELATIVE)
        self.assertEqual([], smp_first_ap.contract_errors(contract))
        self.assertTrue(contract["claims"]["one_application_processor_started"])
        self.assertFalse(contract["claims"]["general_smp_implemented"])
        self.assertFalse(contract["claims"]["n8_exit_gate_satisfied"])
        self.assertFalse(contract["production_ready"])

    def test_resource_layout_is_complete_guarded_and_below_one_mib(self) -> None:
        layout = smp_first_ap.resource_layout(1, 14)
        self.assertEqual(0x1000, layout["start"])
        self.assertEqual(0xF000, layout["end"])
        self.assertEqual(1, layout["sipi_vector"])
        self.assertEqual([5, 10], layout["roles"]["stack_guards"])
        self.assertEqual([11, 13], layout["roles"]["per_cpu_guards"])
        self.assertEqual([6, 7, 8, 9], layout["roles"]["stack"])
        for start, pages in ((0, 14), (1, 13), (0x100, 14)):
            with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
                smp_first_ap.resource_layout(start, pages)

    def test_first_ap_selection_rejects_missing_and_x2apic_targets(self) -> None:
        processors = [
            {"apic_id": 0, "enabled": True, "x2apic": False},
            {"apic_id": 2, "enabled": True, "x2apic": False},
            {"apic_id": 1, "enabled": True, "x2apic": False},
        ]
        self.assertEqual(1, smp_first_ap.select_first_ap(processors, 0)["apic_id"])
        with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
            smp_first_ap.select_first_ap(processors[:1], 0)
        hostile = copy.deepcopy(processors)
        hostile[2]["x2apic"] = True
        hostile[1]["enabled"] = False
        with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
            smp_first_ap.select_first_ap(hostile, 0)

    def test_rx_gdt_requires_every_descriptor_accessed_bit_pre_set(self) -> None:
        descriptors = [
            0x00CF_9B00_0000_FFFF,
            0x00CF_9300_0000_FFFF,
            0x00AF_9B00_0000_FFFF,
            0x00CF_9300_0000_FFFF,
        ]
        smp_first_ap.require_preaccessed_gdt(descriptors)
        descriptors[3] &= ~(1 << 40)
        with self.assertRaises(smp_first_ap.KernelSmpFirstApError):
            smp_first_ap.require_preaccessed_gdt(descriptors)

    def test_mailbox_checksum_matches_the_first_live_qemu_receipt(self) -> None:
        values = {
            "state": 3,
            "command": 1,
            "target_apic_id": 1,
            "bsp_apic_id": 0,
            "observed_apic_id": 1,
            "leaf1_ecx": 0x8000_2001,
            "leaf1_edx": 0x178B_FBFD,
            "cr0": 0xE001_0011,
            "cr3": 0x2000,
            "cr4": 0x20,
            "efer": 0xD00,
            "tsc_online": 0x73D5_BF42,
            "tsc_stop": 0x73D8_CCEE,
        }
        self.assertEqual(0xA4C5_8217_BC17_0831, smp_first_ap.mailbox_checksum(values))
        values["tsc_stop"] += 1
        self.assertNotEqual(0xA4C5_8217_BC17_0831, smp_first_ap.mailbox_checksum(values))

    def test_source_audit_binds_preaccessed_gdt_and_removes_probes(self) -> None:
        audit = qualify_native_kernel_smp_first_ap._source_audit()
        self.assertEqual(4, audit["gdt_preaccessed_descriptor_count"])
        self.assertEqual(3, audit["trampoline_mode_count"])
        self.assertEqual(0, audit["transient_diagnostic_token_count"])

    def test_live_readiness_and_all_hostile_controls(self) -> None:
        path = smp_first_ap.ROOT / smp_first_ap.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP1 readiness has not been generated yet")
        readiness = smp_first_ap.read_json(path)
        self.assertEqual([], smp_first_ap.readiness_errors(readiness))
        markers = readiness["execution"]["runs"][0]["markers"]
        observation = smp_first_ap.validate_markers(markers)
        self.assertEqual(1, observation["result"]["ap_online"])
        self.assertTrue(observation["stop"]["parked"])
        self.assertEqual(57_344, observation["release"]["verified_bytes"])
        controls = qualify_native_kernel_smp_first_ap._negative_controls(markers)
        self.assertEqual(list(smp_first_ap.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])

    def test_release_gate_accepts_only_the_bound_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_smp_first_ap_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("qemu64_vcpus=2", check["detail"])
        self.assertIn("ap=1/1", check["detail"])
        self.assertIn("parked=1/1", check["detail"])
        self.assertIn("n8_exit=false", check["detail"])

    def test_recorded_first_ap_rejects_inconsistent_payloads(self) -> None:
        # Payload-only validation deliberately does not establish fresh execution.
        baseline = smp_first_ap.read_json(smp_first_ap.ROOT / smp_first_ap.READINESS_RELATIVE)
        host = baseline["build"]["kernel_entry"]["host_tests"]
        self.assertEqual([], smp_first_ap.recorded_first_ap_errors(baseline["execution"], baseline["summary"], host))
        for family, label, candidate in recorded_receipt_mutations(baseline):
            with self.subTest(family=family, case=label):
                self.assertTrue(smp_first_ap.recorded_first_ap_errors(candidate["execution"], candidate["summary"], host))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        baseline = smp_first_ap.read_json(smp_first_ap.ROOT / smp_first_ap.READINESS_RELATIVE)
        self.assertEqual([], smp_first_ap.readiness_errors(baseline))
        self.assertTrue(pooleos_release_gate.check_native_kernel_smp_first_ap_readiness()["ok"])
        candidates = list(recorded_receipt_mutations(baseline))
        for value in (None, [], "invalid"):
            candidates.append(("root-shape", repr(value), value))
            candidate = copy.deepcopy(baseline)
            candidate["negative_controls"] = value
            candidates.append(("control-shape", repr(value), candidate))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.json"
            for family, label, candidate in candidates:
                with self.subTest(family=family, case=label):
                    self.assertTrue(smp_first_ap.readiness_errors(candidate))
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    self.assertFalse(pooleos_release_gate.check_native_kernel_smp_first_ap_readiness(path)["ok"])

    def test_dynamic_normalization_preserves_only_validated_clock_fields(self) -> None:
        baseline = smp_first_ap.read_json(smp_first_ap.ROOT / smp_first_ap.READINESS_RELATIVE)
        host = baseline["build"]["kernel_entry"]["host_tests"]
        pair = copy.deepcopy(baseline["execution"])
        run = pair["runs"][1]
        observation = smp_first_ap.validate_markers(run["markers"])
        online, stop = observation["online"], observation["stop"]
        values = {"state": 3, "command": 1, "target_apic_id": 1, "bsp_apic_id": 0,
                  "observed_apic_id": 1, "leaf1_ecx": online["ecx"], "leaf1_edx": online["edx"],
                  **{key: online[key] for key in ("cr0", "cr3", "cr4", "efer")},
                  "tsc_online": stop["tsc_online"] + 1, "tsc_stop": stop["tsc_stop"] + 1}

        def bind_synthetic_run():
            for field in ("tsc_online", "tsc_stop", "checksum"):
                value = smp_first_ap.mailbox_checksum(values) if field == "checksum" else values[field]
                run["markers"][35] = qualify_native_kernel_smp_first_ap._set_field(run["markers"][35], field, f"0x{value:016X}")
            run["marker_summary"] = smp_first_ap.validate_markers(run["markers"])
            run["marker_sha256"] = smp_first_ap.sha256_bytes(native_pooleboot.canonical_json_bytes(run["markers"]))

        bind_synthetic_run()
        # A synthetic consistency test, never passed off as a current live receipt.
        self.assertEqual([], smp_first_ap.recorded_first_ap_errors(pair, baseline["summary"], host))
        valid = copy.deepcopy(pair)
        run["markers"][35] = qualify_native_kernel_smp_first_ap._set_field(run["markers"][35], "checksum", "0x0000000000000000")
        self.assertTrue(smp_first_ap.recorded_first_ap_errors(pair, baseline["summary"], host))
        pair = copy.deepcopy(valid)
        run = pair["runs"][1]
        values["cr0"] ^= 1 << 5
        run["markers"][34] = qualify_native_kernel_smp_first_ap._set_field(run["markers"][34], "cr0", f"0x{values['cr0']:016X}")
        bind_synthetic_run()
        errors = smp_first_ap.recorded_first_ap_errors(pair, baseline["summary"], host)
        self.assertTrue(any("static markers differ" in error for error in errors), errors)
        pair = copy.deepcopy(valid)
        pair["runs"][1]["screenshot"]["sha256"] = "0" * 64
        self.assertTrue(smp_first_ap.recorded_first_ap_errors(pair, baseline["summary"], host))

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        baseline = smp_first_ap.read_json(smp_first_ap.ROOT / smp_first_ap.READINESS_RELATIVE)
        self.assertEqual([], smp_first_ap.readiness_errors(baseline))
        baseline["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with mock.patch.object(qualify_native_kernel_smp_first_ap, "make_readiness", return_value=baseline):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(1, qualify_native_kernel_smp_first_ap.main(["--out", str(path)]))
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
