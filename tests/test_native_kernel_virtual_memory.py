from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_virtual_memory as virtual_memory
from tools import pooleos_release_gate, qualify_native_kernel_virtual_memory


def recorded_receipt_mutations(baseline):
    def changed(path, value, remove=False):
        candidate = copy.deepcopy(baseline)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        if remove:
            target.pop(path[-1])
        else:
            target[path[-1]] = copy.deepcopy(value)
        return candidate

    pair = baseline["execution"]
    for index in range(2):
        for label, value in (("failure", 1), ("negative", -1), ("boolean", False),
                             ("float", 0.0), ("string", "0"), ("null", None), ("missing", None)):
            yield "exit", f"{index}-{label}", changed(
                ("execution", "runs", index, "qemu_exit_code"), value, label == "missing")
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
        yield "coverage", label, changed(("execution", key), value, label.startswith("missing-"))
    for path, value in (
        (("markers",), None), (("markers",), []), (("markers",), [None]),
        (("markers",), ["invalid"]), (("marker_sha256",), "0" * 64),
        (("marker_summary",), None), (("marker_summary", "layout", "table_pages"), 243.0),
        (("marker_summary", "transfer_prefix", "ordered_contract_match"), 1),
        (("pbp1_transcript",), None), (("pbp1_transcript", "core"), None),
        (("pbp1_transcript", "core"), {}), (("transcript_binding",), None),
        (("transcript_binding", "exact_transfer_fields_bound"), 1),
        (("independent_kernel_revalidation",), None),
        (("independent_kernel_revalidation", "contract_id"), "invalid"),
        (("independent_kernel_revalidation", "guest_host_exact_match"), 1),
        (("independent_kernel_revalidation", "parser_count"), 6.0),
        (("serial_debugcon_exact_match",), 1), (("pbp1_serial_debugcon_exact_match",), 1),
        (("screenshot",), None), (("screenshot", "nonblank"), 1),
        (("screenshot", "sha256"), None), (("screenshot", "sha256"), "invalid"),
        (("independent_virtual_memory",), None),
        (("independent_virtual_memory",), {}),
        (("independent_virtual_memory", "entry_count"), 98.0),
        (("independent_virtual_memory", "direct_map", "mapped_pages"), 0),
        (("pbp1_transcript", "memory_entries", 0, "source_type"), 1),
    ):
        # Identical corruption in both runs must not be accepted as corroboration.
        candidate = copy.deepcopy(baseline)
        for run in candidate["execution"]["runs"]:
            target = run
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = copy.deepcopy(value)
        yield "evidence", str(path) + "=" + repr(value), candidate
    for path, value in (
        (("execution", "observation"), None),
        (("execution", "observation", "result", "allocated_pages"), 1),
        (("execution", "observation", "candidate", "direct_generation"), True),
        (("execution", "independent_memory_summary"), None),
        (("execution", "independent_memory_summary", "entry_count"), 0),
        (("execution", "independent_memory_summary", "entry_count"), 98.0),
        (("summary",), None),
    ):
        yield "accounting", str(path), changed(path, value)

    def leaves(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from leaves(child, (*path, key))
        elif isinstance(value, list):
            for key, child in enumerate(value):
                yield from leaves(child, (*path, key))
        else:
            yield path, value

    for path, value in leaves(baseline["summary"], ("summary",)):
        substitute = int(value) if isinstance(value, bool) else float(value) if isinstance(value, int) else "invalid"
        for label, replacement in (("null", None), ("type-or-value", substitute)):
            yield "summary", str(path) + label, changed(path, replacement)


class NativeKernelVirtualMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = virtual_memory.read_json(
            virtual_memory.ROOT / virtual_memory.CONTRACT_RELATIVE
        )
        cls.readiness = virtual_memory.read_json(
            virtual_memory.ROOT / virtual_memory.READINESS_RELATIVE
        )
        cls.live_run = cls.readiness["execution"]["runs"][0]
        cls.markers = cls.live_run["markers"]

    def test_contract_and_readiness_are_exact_and_non_promoting(self) -> None:
        self.assertEqual([], virtual_memory.contract_errors(self.contract))
        self.assertEqual([], virtual_memory.readiness_errors(self.readiness))
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n9_exit_gate_satisfied"])

    def test_live_sparse_tables_bind_to_complete_pmm_ownership(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        derived = virtual_memory.validate_observation_binding(
            observation, self.live_run["pbp1_transcript"]
        )
        candidate = observation["candidate"]
        self.assertEqual(10, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(derived["first_free_address"][1], candidate["candidate_root"])
        direct_map = derived["direct_map"]
        self.assertEqual(direct_map["table_pages"], observation["layout"]["table_pages"])
        self.assertEqual(
            candidate["candidate_root"] + direct_map["table_pages"] * virtual_memory.PAGE_BYTES,
            candidate["data"],
        )
        self.assertEqual(
            virtual_memory.DIRECT_MAP_START
            + direct_map["first_page"] * virtual_memory.PAGE_BYTES,
            candidate["direct_first"],
        )
        self.assertEqual(direct_map["mapped_pages"], observation["layout"]["mapped_pages"])
        self.assertEqual(direct_map["coverage_checksum"], candidate["coverage_checksum"])
        self.assertGreater(observation["result"]["physical_writes"], direct_map["mapped_pages"])
        self.assertGreater(observation["result"]["temporary_pte_writes"], direct_map["mapped_pages"])

    def test_active_root_restores_cr3_and_binds_leaf_receipts(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        self.assertEqual(2, observation["activation"]["cr3_writes"])
        self.assertEqual("exact", observation["activation"]["candidate_readback"])
        self.assertEqual("exact", observation["activation"]["original_restore"])
        self.assertEqual(3, observation["invalidation"]["active_receipts"])
        self.assertEqual(0xA5, observation["invalidation"]["probe"])
        self.assertEqual(1, observation["invalidation"]["premature_reuse_rejected"])
        self.assertEqual(1, observation["invalidation"]["generation_retirement_receipts"])
        self.assertEqual(1, observation["invalidation"]["local_context_flushes"])
        self.assertEqual(0, observation["invalidation"]["remote_shootdowns_pending"])
        self.assertEqual(1, observation["invalidation"]["future_smp_shootdown_required"])
        self.assertEqual(1, observation["invalidation"]["old_generation_reclaim_deferred"])
        self.assertEqual(1, observation["invalidation"]["exact_release_receipt"])
        self.assertEqual(6, observation["invalidation"]["retained_free_rejections"])
        self.assertEqual(3, observation["result"]["active_invlpg"])
        self.assertEqual(
            observation["result"]["temporary_pte_writes"],
            observation["result"]["bootstrap_invlpg"],
        )
        for key in ("shootdown", "smp", "ring3", "production"):
            self.assertEqual(0, observation["result"][key])

    def test_oracle_rejects_pbp1_first_fit_drift(self) -> None:
        observation = virtual_memory.validate_markers(self.markers)
        hostile = copy.deepcopy(observation)
        hostile["candidate"]["candidate_root"] += virtual_memory.PAGE_BYTES
        with self.assertRaises(virtual_memory.KernelVirtualMemoryError):
            virtual_memory.validate_observation_binding(
                hostile, self.live_run["pbp1_transcript"]
            )

    def test_all_hostile_controls_are_exact_and_pass(self) -> None:
        controls = qualify_native_kernel_virtual_memory._negative_controls(
            self.markers, self.live_run["pbp1_transcript"]
        )
        self.assertEqual(
            list(virtual_memory.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls]
        )
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_source_audit_binds_core_and_privileged_adapter(self) -> None:
        audit = qualify_native_kernel_virtual_memory._source_audit()
        self.assertEqual(0, audit["heap_api_token_count"])
        self.assertEqual(2, audit["active_cr3_write_count"])
        self.assertEqual(3, audit["active_local_invalidation_count"])
        self.assertEqual(512, audit["max_direct_page_table_count"])
        self.assertEqual(4, audit["max_direct_directory_table_count"])
        self.assertTrue(audit["table_page_count_derived_from_manifest"])
        self.assertTrue(audit["volatile_physical_adapter"])
        self.assertTrue(audit["bootstrap_temporary_mapping_uses_invlpg"])
        self.assertTrue(audit["live_cpuid_physical_width_validated"])

    def test_recorded_retention_cannot_be_inferred_from_summary_only(self) -> None:
        for case in ("missing_runs", "one_run", "wrong_count", "missing_count",
                     "summary", "observation"):
            with self.subTest(case=case):
                receipt = copy.deepcopy(self.readiness)
                execution = receipt["execution"]
                if case == "missing_runs":
                    execution.pop("runs")
                elif case == "one_run":
                    execution["runs"].pop()
                elif case in ("wrong_count", "missing_count"):
                    marker = execution["runs"][1]["markers"][38]
                    execution["runs"][1]["markers"][38] = marker.replace(
                        " retained_free_rejections=6",
                        " retained_free_rejections=5" if case == "wrong_count" else "",
                    )
                elif case == "summary":
                    receipt["summary"]["retained_free_rejections"] = 5
                else:
                    execution["observation"]["invalidation"]["retained_free_rejections"] = 5
                self.assertTrue(virtual_memory.readiness_errors(receipt))


    def test_recorded_vm_rejects_inconsistent_payloads(self) -> None:
        # Historical payload consistency is not a current-source qualification.
        self.assertEqual([], virtual_memory.recorded_virtual_memory_errors(
            self.readiness["execution"], self.readiness["summary"]))
        for family, label, candidate in recorded_receipt_mutations(self.readiness):
            with self.subTest(family=family, case=label):
                self.assertTrue(virtual_memory.recorded_virtual_memory_errors(
                    candidate["execution"], candidate["summary"]))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        self.assertEqual([], virtual_memory.readiness_errors(self.readiness))
        self.assertTrue(pooleos_release_gate.check_native_kernel_virtual_memory_readiness()["ok"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.json"
            for family, label, candidate in recorded_receipt_mutations(self.readiness):
                with self.subTest(family=family, case=label):
                    errors = virtual_memory.readiness_errors(candidate)
                    self.assertTrue(any("recorded" in error for error in errors), errors)
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    check = pooleos_release_gate.check_native_kernel_virtual_memory_readiness(path)
                    self.assertFalse(check["ok"], check)

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        self.assertEqual([], virtual_memory.readiness_errors(self.readiness))
        candidate = copy.deepcopy(self.readiness)
        candidate["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with mock.patch.object(qualify_native_kernel_virtual_memory, "make_readiness", return_value=candidate):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(1, qualify_native_kernel_virtual_memory.main(["--out", str(path)]))
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
