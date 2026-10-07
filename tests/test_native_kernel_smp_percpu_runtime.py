import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_smp_percpu_runtime as smp_runtime
from runtime import native_tier0
from tests.test_native_cpu_entry_provenance import pair_mutations
from tools import qualify_native_kernel_smp_percpu_runtime as qualify
from tools import pooleos_release_gate


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
    for key, value in (("virtual_cpu_count", 2.0), ("dynamic_fields_revalidated", 1),
                       ("cpu_model", "qemu64"), ("acceleration", "tcg_single_thread"),
                       ("deterministic_instruction_clock", 0), ("machine", "wrong"), ("profile_id", "wrong")):
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
    for field in ("baseline_checksum", "runtime_checksum", "parked"):
        candidate = copy.deepcopy(baseline)
        for run in candidate["execution"]["runs"]:
            run["markers"][39] = qualify._set_field(run["markers"][39], field, "0" if field == "parked" else "0x0000000000000000")
        yield "raw-stop", field, candidate
    for index, control in enumerate(baseline["negative_controls"]):
        for value in (control["case_count"] + 1, float(control["case_count"])):
            yield "controls", str((index, value)), changed(("negative_controls", index, "case_count"), value)
    candidate = copy.deepcopy(baseline)
    candidate["negative_controls"][0]["case_count"] += 1
    candidate["negative_controls"][3]["case_count"] -= 1
    yield "controls", "redistribution-same-total", candidate


class NativeKernelSmpPerCpuRuntimeTests(unittest.TestCase):
    def test_contract_schema_and_negative_control_order(self) -> None:
        contract = smp_runtime.read_json(smp_runtime.ROOT / smp_runtime.CONTRACT_RELATIVE)
        self.assertEqual([], smp_runtime.contract_errors(contract))
        self.assertEqual(19, len(smp_runtime.NEGATIVE_CONTROL_IDS))
        self.assertEqual(159, contract["qualification"]["hostile_case_count"])

    def test_resource_layout_freezes_all_32_page_roles(self) -> None:
        layout = smp_runtime.resource_layout(1, 32)
        self.assertEqual(0x1000, layout["start"])
        self.assertEqual(0x21000, layout["end"])
        self.assertEqual(0x10000, layout["gdt"])
        self.assertEqual(0x10040, layout["tss"])
        self.assertEqual(0x13000, layout["idt"])
        self.assertEqual(0x1E000, layout["xstate"])
        self.assertEqual(list(range(32)), sorted(offset for values in layout["roles"].values() for offset in values))
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.resource_layout(1, 31)
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.resource_layout(0, 32)

    def test_first_ap_selection_rejects_x2apic_and_missing_target(self) -> None:
        processors = [
            {"apic_id": 0, "enabled": True, "x2apic": False},
            {"apic_id": 1, "enabled": True, "x2apic": False},
        ]
        self.assertEqual(1, smp_runtime.select_first_ap(processors, 0)["apic_id"])
        x2apic = copy.deepcopy(processors)
        x2apic[1]["x2apic"] = True
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.select_first_ap(x2apic, 0)
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            smp_runtime.select_first_ap(processors[:1], 0)

    def test_sandybridge_profile_is_two_cpu_multi_tcg_without_icount(self) -> None:
        _, base = native_tier0.validate_contracts(smp_runtime.ROOT)
        profile = qualify._sandybridge_profile(base)
        arguments = profile["base_argument_template"]
        self.assertEqual("SandyBridge,-avx", arguments[arguments.index("-cpu") + 1])
        self.assertEqual("tcg,thread=multi", arguments[arguments.index("-accel") + 1])
        self.assertEqual("2,sockets=1,dies=1,clusters=1,cores=2,threads=1,maxcpus=2", arguments[arguments.index("-smp") + 1])
        self.assertNotIn("-icount", arguments)

    def test_source_audit_fails_if_runtime_xrestore_disappears(self) -> None:
        audit = qualify._source_audit()
        self.assertEqual(1, audit["xsave_instruction_count"])
        self.assertEqual(1, audit["xrstor_instruction_count"])
        self.assertEqual(14, audit["guard_page_count"])
        arch = (smp_runtime.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        main = (smp_runtime.ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
        runtime = (smp_runtime.ROOT / "native/kernel/src/smp_runtime.rs").read_text(encoding="utf-8")
        with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
            qualify._audit_source_text(arch.replace("xrstor64 [rbx]", "xrstor64 [rax]", 1), main, runtime)

    def test_live_readiness_and_all_hostile_cases(self) -> None:
        path = smp_runtime.ROOT / smp_runtime.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP2 readiness has not been generated yet")
        readiness = smp_runtime.read_json(path)
        self.assertEqual([], smp_runtime.readiness_errors(readiness))
        markers = readiness["execution"]["runs"][0]["markers"]
        observation = smp_runtime.validate_markers(markers)
        self.assertEqual(27, observation["result"]["vectors"])
        self.assertTrue(observation["xstate"]["owner_cleared"])
        controls = qualify._negative_controls(markers)
        self.assertEqual(list(smp_runtime.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(159, sum(item["case_count"] for item in controls))
        check = pooleos_release_gate.check_native_kernel_smp_percpu_runtime_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("gates=27/27", check["detail"])
        self.assertIn("n8_exit=false", check["detail"])

    def test_recorded_runtime_rejects_inconsistent_payloads(self) -> None:
        # This payload check alone never establishes current-source qualification.
        baseline = smp_runtime.read_json(smp_runtime.ROOT / smp_runtime.READINESS_RELATIVE)
        host = baseline["build"]["kernel_entry"]["host_tests"]
        self.assertEqual([], smp_runtime.recorded_percpu_runtime_errors(baseline["execution"], baseline["summary"], host))
        for family, label, candidate in recorded_receipt_mutations(baseline):
            if family == "controls":
                continue
            with self.subTest(family=family, case=label):
                self.assertTrue(smp_runtime.recorded_percpu_runtime_errors(candidate["execution"], candidate["summary"], host))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        baseline = smp_runtime.read_json(smp_runtime.ROOT / smp_runtime.READINESS_RELATIVE)
        self.assertEqual([], smp_runtime.readiness_errors(baseline))
        self.assertTrue(pooleos_release_gate.check_native_kernel_smp_percpu_runtime_readiness()["ok"])
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
                    self.assertTrue(smp_runtime.readiness_errors(candidate))
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    self.assertFalse(pooleos_release_gate.check_native_kernel_smp_percpu_runtime_readiness(path)["ok"])

    def test_dynamic_comparison_checks_raw_clocks_and_both_checksums(self) -> None:
        baseline = smp_runtime.read_json(smp_runtime.ROOT / smp_runtime.READINESS_RELATIVE)
        pair = baseline["execution"]
        host = baseline["build"]["kernel_entry"]["host_tests"]
        self.assertEqual([], smp_runtime.recorded_percpu_runtime_errors(pair, baseline["summary"], host))
        normalized = [smp_runtime.normalize_dynamic_markers(run["markers"]) for run in pair["runs"]]
        self.assertEqual(normalized[0], normalized[1])
        for field in ("tsc_online", "tsc_stop", "baseline_checksum", "runtime_checksum"):
            markers = pair["runs"][1]["markers"].copy()
            markers[39] = qualify._set_field(markers[39], field, "0x0000000000000000")
            with self.subTest(field=field):
                with self.assertRaises(smp_runtime.KernelSmpPerCpuRuntimeError):
                    smp_runtime.normalize_dynamic_markers(markers)
        different_frame = copy.deepcopy(pair)
        different_frame["runs"][1]["screenshot"]["sha256"] = "0" * 64
        self.assertTrue(smp_runtime.recorded_percpu_runtime_errors(different_frame, baseline["summary"], host))

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        baseline = smp_runtime.read_json(smp_runtime.ROOT / smp_runtime.READINESS_RELATIVE)
        self.assertEqual([], smp_runtime.readiness_errors(baseline))
        baseline["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with mock.patch.object(qualify, "make_readiness", return_value=baseline):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(1, qualify.main(["--out", str(path)]))
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
