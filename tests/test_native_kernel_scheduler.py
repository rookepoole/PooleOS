import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_scheduler as scheduler
from runtime import native_pooleboot
from tests.test_native_cpu_entry_provenance import pair_mutations
from tools import pooleos_release_gate, qualify_native_kernel_scheduler as qualify


PROBE_OUTPUT = """\
PKSCHED1:STRESS PASS sequence=6660 tasks=8 runnable=4 running=4 blocked=0 dead=0 dispatches=1761 migrations=2334 wakes=0 teardowns=0 inheritance=0 checksum=0x23B76E2F80E2B747 task_dispatches=87,165,245,420,78,133,230,403 runtime_ticks=53,99,127,261,30,90,187,256
PKSCHED1:WAIT PASS sequence=14 wakes=2 cancel_reason=1 timeout_reason=2 duplicate_rejected=1
PKSCHED1:INHERIT PASS owner_slot=0 waiter_slot=1 inherited=30 restored=2 granted_slot=1 inheritance_events=1
PKSCHED1:CONTEXT PASS valid=1 hostile_rejected=8 alignment=16 callee_saved=6
"""


def linked_switch_fixture() -> str:
    instructions = (
        "    1000: 9c pushfq",
        "    1001: 55 pushq %rbp",
        "    1002: 53 pushq %rbx",
        "    1003: 41 54 pushq %r12",
        "    1005: 41 55 pushq %r13",
        "    1007: 41 56 pushq %r14",
        "    1009: 41 57 pushq %r15",
        "    100b: 48 89 27 movq %rsp, (%rdi)",
        "    100e: 48 ff 05 00 00 00 00 incq 0x0(%rip)",
        "    1015: 48 8b 26 movq (%rsi), %rsp",
        "    1018: 41 5f popq %r15",
        "    101a: 41 5e popq %r14",
        "    101c: 41 5d popq %r13",
        "    101e: 41 5c popq %r12",
        "    1020: 5b popq %rbx",
        "    1021: 5d popq %rbp",
        "    1022: 9d popfq",
        "    1023: c3 retq",
    )
    return (
        "0000000000001000 <poole_scheduler_context_switch>:\n"
        + "\n".join(instructions)
        + "\n0000000000001024 <poole_scheduler_context_switch_end>:\n"
    )


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

    for path in (("execution",), ("execution", "observation"), ("summary",), ("build", "host_probe")):
        yield "shape", str(path), changed(path, None)
    for key, value in (("virtual_cpu_count", 1.0), ("dynamic_fields_revalidated", 1),
                       ("cpu_model", "wrong"), ("acceleration", "wrong"),
                       ("deterministic_instruction_clock", 1), ("bsp_only", 1),
                       ("machine", "wrong"), ("profile_id", "wrong")):
        yield "profile", key, changed(("execution", key), value)
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
    for section, fields in baseline["build"]["host_probe"].items():
        if isinstance(fields, dict):
            for key, value in fields.items():
                substitute = float(value) if type(value) is int else None
                yield "host-probe", section + "." + key, changed(("build", "host_probe", section, key), substitute)
        else:
            yield "host-probe", section, changed(("build", "host_probe", section), None)
    for index, control in enumerate(baseline["negative_controls"]):
        for value in (control["case_count"] + 1, float(control["case_count"])):
            yield "controls", str((index, value)), changed(("negative_controls", index, "case_count"), value)
    candidate = copy.deepcopy(baseline)
    candidate["negative_controls"][0]["case_count"] += 1
    candidate["negative_controls"][3]["case_count"] -= 1
    yield "controls", "redistribution-same-total", candidate
    for value in (None, [], "invalid"):
        yield "root-shape", repr(value), value
        yield "control-shape", repr(value), changed(("negative_controls",), value)


class NativeKernelSchedulerTests(unittest.TestCase):
    def test_readiness_writer_emits_canonical_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "readiness.json"
            qualify._write_readiness(path, {"status": "pass", "values": [1, 2]})
            data = path.read_bytes()
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(data.endswith(b"\n"))

    def test_contract_schema_claims_and_hostile_count(self) -> None:
        contract = scheduler.read_json(scheduler.ROOT / scheduler.CONTRACT_RELATIVE)
        self.assertEqual([], scheduler.contract_errors(contract))
        self.assertEqual(28, len(scheduler.NEGATIVE_CONTROL_IDS))
        self.assertEqual(115, contract["qualification"]["hostile_case_count"])
        self.assertFalse(contract["production_ready"])
        self.assertFalse(contract["claims"]["general_scheduler_implemented"])
        baseline = scheduler.read_json(scheduler.ROOT / scheduler.READINESS_RELATIVE)
        for value in ("2026-09-05", "2026-09-07", "2024-02-29"):
            candidate = copy.deepcopy(baseline)
            candidate["status_date"] = value
            with self.subTest(valid_date=value):
                self.assertFalse(any("status_date" in item for item in scheduler.readiness_errors(candidate)))
        invalid_dates = (
            None, 7, True, "", "20260907", "2026-9-7", "2026-02-29",
            "2026-04-31", "2026-13-01", "2026-09-07T00:00:00",
        )
        self.assertEqual(10, len(invalid_dates))
        for value in invalid_dates:
            candidate = copy.deepcopy(baseline)
            candidate["status_date"] = value
            with self.subTest(invalid_date=value), patch.object(
                pooleos_release_gate, "_load_schema_artifact", return_value=(candidate, [])
            ):
                expected = "readiness status_date is not a canonical calendar date"
                self.assertIn(expected, scheduler.readiness_errors(candidate))
                check = pooleos_release_gate.check_native_kernel_scheduler_readiness()
                self.assertFalse(check["ok"])
                self.assertIn(expected, check["detail"])

    def test_independent_stress_oracle_is_frozen(self) -> None:
        receipt = scheduler.stress_oracle()
        self.assertEqual(6660, receipt["sequence"])
        self.assertEqual(1761, receipt["dispatches"])
        self.assertEqual(2334, receipt["migrations"])
        self.assertEqual(0x23B7_6E2F_80E2_B747, receipt["checksum"])
        self.assertEqual((87, 165, 245, 420, 78, 133, 230, 403), receipt["task_dispatches"])

    def test_probe_parser_requires_exact_rust_python_agreement(self) -> None:
        observed = scheduler.parse_probe_output(PROBE_OUTPUT)
        self.assertEqual(4, len(observed["lines"]))
        self.assertEqual(8, observed["context"]["hostile_rejected"])
        with self.assertRaises(scheduler.KernelSchedulerError):
            scheduler.parse_probe_output(PROBE_OUTPUT.replace("dispatches=1761", "dispatches=1760", 1))

    def test_neutral_oracle_rejects_generation_priority_and_queue_drift(self) -> None:
        model = scheduler.NeutralSchedulerOracle()
        model.create(0, 10)
        with self.assertRaises(scheduler.KernelSchedulerError):
            model.create(0, 10)
        with self.assertRaises(scheduler.KernelSchedulerError):
            scheduler.NeutralSchedulerOracle().create(0, 0)
        model.activate(0, 0)
        model.queues[0].append(0)
        with self.assertRaises(scheduler.KernelSchedulerError):
            model.validate()

    def test_source_audit_binds_core_switch_and_selector(self) -> None:
        audit = qualify._source_audit()
        self.assertEqual(14, audit["scheduler_test_count"])
        self.assertTrue(audit["allocation_free_core"])
        self.assertEqual(1, audit["context_switch_source_scope_count"])
        self.assertEqual(5, audit["live_marker_count"])

    def test_linked_switch_scope_has_exact_instruction_boundary(self) -> None:
        fixture = linked_switch_fixture()
        audit = qualify._linked_switch_scope(fixture)
        self.assertEqual(18, audit["instruction_count"])
        self.assertEqual(0, audit["forbidden_instruction_count"])
        with self.assertRaises(scheduler.KernelSchedulerError):
            qualify._linked_switch_scope(fixture.replace(" retq", " sti", 1))
        with self.assertRaises(scheduler.KernelSchedulerError):
            qualify._linked_switch_scope(fixture.replace("\n0000000000001024", "\n    1024: 90 nop\n0000000000001025", 1))

    def test_input_bindings_cover_implementation_and_proof_sources(self) -> None:
        inputs = scheduler.expected_inputs()
        paths = {item["path"] for item in inputs["implementation"]}
        self.assertIn("native/kernel/src/scheduler.rs", paths)
        self.assertIn("native/bootexit/src/lib.rs", paths)
        self.assertIn("tools/qualify_native_kernel_scheduler.py", paths)
        self.assertIn("tests/test_native_kernel_scheduler.py", paths)
        self.assertIn("models/tla/PooleScheduler.tla", paths)

    def test_generated_readiness_when_available(self) -> None:
        path = scheduler.ROOT / scheduler.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSCHED1 readiness has not been generated yet")
        readiness = scheduler.read_json(path)
        self.assertEqual([], scheduler.readiness_errors(readiness))
        observation = scheduler.validate_markers(readiness["execution"]["runs"][0]["markers"])
        self.assertEqual(16, observation["switch"]["transitions"])
        controls = qualify._negative_controls(
            readiness["execution"]["runs"][0]["markers"],
            readiness["build"]["host_probe"]["lines"],
        )
        self.assertEqual(list(scheduler.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(115, sum(item["case_count"] for item in controls))

    def test_recorded_scheduler_rejects_inconsistent_payloads(self) -> None:
        baseline = scheduler.read_json(scheduler.ROOT / scheduler.READINESS_RELATIVE)
        self.assertEqual([], scheduler.recorded_scheduler_errors(baseline["execution"], baseline["summary"], baseline["build"]))
        for family, label, candidate in recorded_receipt_mutations(baseline):
            if family in ("controls", "root-shape", "control-shape"):
                continue
            with self.subTest(family=family, case=label):
                self.assertTrue(scheduler.recorded_scheduler_errors(candidate["execution"], candidate["summary"], candidate["build"]))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        baseline = scheduler.read_json(scheduler.ROOT / scheduler.READINESS_RELATIVE)
        self.assertEqual([], scheduler.readiness_errors(baseline))
        self.assertTrue(pooleos_release_gate.check_native_kernel_scheduler_readiness()["ok"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.json"
            for family, label, candidate in recorded_receipt_mutations(baseline):
                with self.subTest(family=family, case=label):
                    self.assertTrue(scheduler.readiness_errors(candidate))
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    self.assertFalse(pooleos_release_gate.check_native_kernel_scheduler_readiness(path)["ok"])

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        baseline = scheduler.read_json(scheduler.ROOT / scheduler.READINESS_RELATIVE)
        self.assertEqual([], scheduler.readiness_errors(baseline))
        baseline["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with patch.object(qualify, "make_readiness", return_value=baseline):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(1, qualify.main(["--out", str(path)]))
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())

    def test_hostile_controls_detect_disabled_validators(self) -> None:
        baseline = scheduler.read_json(scheduler.ROOT / scheduler.READINESS_RELATIVE)
        markers = baseline["execution"]["runs"][0]["markers"]
        lines = baseline["build"]["host_probe"]["lines"]
        controls = qualify._negative_controls(markers, lines)
        self.assertEqual(tuple(c["case_count"] for c in controls), scheduler.NEGATIVE_CONTROL_CASE_COUNTS)
        for target, name, result in (
            (scheduler, "validate_markers", scheduler.validate_markers(markers)),
            (scheduler, "parse_probe_output", scheduler.parse_probe_output("\n".join(lines))),
            (qualify, "_audit_source_text", {}),
        ):
            with self.subTest(disabled=name), patch.object(target, name, return_value=result):
                with self.assertRaisesRegex(qualify.QualificationError, "did not reject"):
                    qualify._negative_controls(markers, lines)

    def test_pair_validation_rejects_coherent_marker_and_host_probe_corruption(self) -> None:
        baseline = scheduler.read_json(scheduler.ROOT / scheduler.READINESS_RELATIVE)
        self.assertEqual([], scheduler.recorded_scheduler_errors(baseline["execution"], baseline["summary"], baseline["build"]))
        candidate = copy.deepcopy(baseline)
        for run in candidate["execution"]["runs"]:
            run["markers"][31] = qualify._set_field(run["markers"][31], "dispatches", "9")
            run["marker_sha256"] = scheduler.sha256_bytes(native_pooleboot.canonical_json_bytes(run["markers"]))
            run["marker_summary"]["switch"]["dispatches"] = 9
        candidate["execution"]["observation"]["switch"]["dispatches"] = 9
        candidate["summary"]["live_dispatches"] = 9
        self.assertTrue(scheduler.recorded_scheduler_errors(candidate["execution"], candidate["summary"], candidate["build"]))
        candidate = copy.deepcopy(baseline)
        host = candidate["build"]["host_probe"]
        host["lines"][0] = qualify._set_field(host["lines"][0], "dispatches", "1762")
        host["stress"]["dispatches"] = 1762
        host["output_sha256"] = scheduler.sha256_bytes(("\n".join(host["lines"]) + "\n").encode())
        candidate["summary"]["trace_dispatches"] = 1762
        self.assertTrue(scheduler.recorded_scheduler_errors(candidate["execution"], candidate["summary"], candidate["build"]))


if __name__ == "__main__":
    unittest.main()
