from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_physical_memory as physical_memory
from tools import pooleos_release_gate, qualify_native_kernel_physical_memory


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
        (("marker_summary",), None), (("marker_summary", "map", "entries"), 98.0),
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
        (("independent_physical_memory",), None),
        (("independent_physical_memory",), {}),
        (("independent_physical_memory", "entry_count"), 98.0),
        (("independent_physical_memory", "acpi_reclaim", "page_count"), 0),
        (("pbp1_transcript", "memory_entries", 0, "source_type"), 1),
        (("pbp1_transcript", "firmware_tables", 0, "physical"), False),
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
        (("execution", "observation", "result", "managed_pages"), 0),
        (("execution", "observation", "acpi_snapshot", "snapshot_pages"), True),
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


class NativeKernelPhysicalMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = physical_memory.read_json(
            physical_memory.ROOT / physical_memory.CONTRACT_RELATIVE
        )
        cls.readiness = physical_memory.read_json(
            physical_memory.ROOT / physical_memory.READINESS_RELATIVE
        )
        cls.run_evidence = cls.readiness["execution"]["runs"][0]
        cls.markers = cls.run_evidence["markers"]

    def test_contract_and_readiness_are_exact_and_non_promoting(self) -> None:
        self.assertEqual([], physical_memory.contract_errors(self.contract))
        self.assertEqual([], physical_memory.readiness_errors(self.readiness))
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n9_exit_gate_satisfied"])
        stale_layout = copy.deepcopy(self.contract)
        stale_layout["metadata_arena"]["manager_byte_count"] = 15376
        self.assertTrue(physical_memory.contract_errors(stale_layout))

    def test_live_markers_bind_to_independent_pbp1_accounting(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        derived = physical_memory.validate_observation_binding(
            observation, self.run_evidence["pbp1_transcript"]
        )
        self.assertEqual(8, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(
            (
                derived["kind_pages"][1]
                - 1
                + derived["boot_reclaim"]["page_count"]
                + derived["acpi_reclaim"]["page_count"]
            ),
            observation["result"]["managed_pages"],
        )
        self.assertEqual(physical_memory.SCRUB_BYTES, observation["scrub"]["scrub_bytes"])
        self.assertEqual(physical_memory.SCRUB_BYTES, observation["scrub"]["verified_bytes"])
        self.assertEqual(physical_memory.PHYSICAL_WRITES, observation["result"]["physical_writes"])
        self.assertEqual(physical_memory.PHYSICAL_READS, observation["result"]["physical_reads"])
        self.assertEqual(
            "temporary_single_page_plus_guarded_metadata_and_repeated_ledger_generations",
            observation["result"]["mappings"],
        )
        self.assertEqual(5, observation["metadata"]["pages"])
        self.assertEqual(2, observation["metadata"]["guard_pages"])
        self.assertEqual(15632, observation["metadata"]["manager_bytes"])
        stale_markers = list(self.markers)
        stale_markers[38] = stale_markers[38].replace(
            "manager_bytes=15632", "manager_bytes=15376", 1
        )
        with self.assertRaisesRegex(
            physical_memory.KernelPhysicalMemoryError, "metadata arena boundary changed"
        ):
            physical_memory.validate_markers(stale_markers)
        self.assertEqual(33, observation["growth"]["final_generation"])
        self.assertEqual(29, observation["growth"]["final_pages"])
        self.assertEqual([2048, 256, 2048, 128, 16], [
            observation["growth"]["free_capacity"],
            observation["growth"]["allocation_capacity"],
            observation["growth"]["source_capacity"],
            observation["growth"]["scrub_capacity"],
            observation["growth"]["reclaim_capacity"],
        ])
        self.assertEqual(3, observation["growth"]["revoked"])
        self.assertEqual(119, observation["growth"]["pressure_checks"])
        self.assertEqual(7, observation["growth"]["pressure_triggers"])
        self.assertEqual(3, observation["growth"]["automatic_growths"])
        self.assertEqual(3, observation["growth"]["soft_fallbacks"])
        self.assertEqual(1, observation["growth"]["hard_rejections"])
        self.assertEqual("host_verified", observation["growth"]["pre_effect"])
        self.assertEqual(1, observation["result"]["metadata_retained"])
        self.assertEqual(1, observation["result"]["ledger_generation_retained"])
        self.assertEqual(1, observation["result"]["alias_revoked"])
        self.assertEqual(1, observation["result"]["reclaim"])
        self.assertEqual(1, observation["result"]["acpi_snapshot_retained"])
        self.assertEqual(1, observation["result"]["acpi_reclaim"])

    def test_boot_reclaim_receipt_is_independently_derived(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        derived = physical_memory.derive_memory_summary(self.run_evidence["pbp1_transcript"])
        reclaim = derived["boot_reclaim"]
        self.assertEqual(70, reclaim["source_record_count"])
        self.assertEqual(12, reclaim["range_count"])
        self.assertEqual(11250, reclaim["page_count"])
        self.assertEqual([2018, 9232, 0], reclaim["pages_by_zone"])
        self.assertEqual(0xFDAB689F085C3287, reclaim["range_checksum"])
        self.assertEqual(0x5DEA9A3BC9E10C18, reclaim["receipt_checksum"])
        self.assertEqual(reclaim["receipt_checksum"], observation["reclaim"]["receipt_checksum"])
        self.assertEqual(11, observation["reclaim"]["acpi_held_pages"])
        self.assertEqual(1, observation["reclaim"]["acpi_early_rejected"])

    def test_acpi_snapshot_and_reclaim_are_independently_bound(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        derived = physical_memory.derive_memory_summary(self.run_evidence["pbp1_transcript"])
        snapshot = observation["acpi_snapshot"]
        reclaim = derived["acpi_reclaim"]
        self.assertEqual("PKACPI1", snapshot["contract_id"])
        self.assertEqual(["APIC", "FACP", "HPET", "MCFG"], snapshot["required"].split(","))
        self.assertEqual([120, 244, 56, 60], [
            snapshot["apic_bytes"],
            snapshot["facp_bytes"],
            snapshot["hpet_bytes"],
            snapshot["mcfg_bytes"],
        ])
        self.assertEqual(1, snapshot["snapshot_pages"])
        self.assertEqual(616, snapshot["snapshot_bytes"])
        self.assertEqual(600, snapshot["copied_bytes"])
        self.assertEqual(derived["acpi_snapshot"]["physical_address"], snapshot["snapshot"])
        self.assertEqual(1, reclaim["source_record_count"])
        self.assertEqual(1, reclaim["range_count"])
        self.assertEqual(11, reclaim["page_count"])
        self.assertEqual([0, 11, 0], reclaim["pages_by_zone"])
        self.assertEqual(0xC718FB26B45257F2, reclaim["range_checksum"])
        self.assertEqual(0x60DAA52A8A05ABD6, reclaim["receipt_checksum"])
        self.assertEqual(
            reclaim["receipt_checksum"], observation["acpi_reclaim"]["receipt_checksum"]
        )

    def test_oracle_rejects_overlap_source_kind_and_core_escape(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        candidates = []
        overlap = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        overlap["memory_entries"][1]["physical_start"] = overlap["memory_entries"][0]["physical_start"]
        candidates.append(overlap)
        source_kind = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        source_kind["memory_entries"][0]["source_type"] = 1
        candidates.append(source_kind)
        ownership = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        ownership["core"]["kernel_physical_base"] = ownership["memory_entries"][0]["physical_start"]
        candidates.append(ownership)
        for candidate in candidates:
            with self.assertRaises(physical_memory.KernelPhysicalMemoryError):
                physical_memory.validate_observation_binding(observation, candidate)

    def test_all_hostile_controls_are_exact_and_pass(self) -> None:
        controls = qualify_native_kernel_physical_memory._negative_controls(
            self.markers, self.run_evidence["pbp1_transcript"]
        )
        self.assertEqual(
            list(physical_memory.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls]
        )
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_source_audit_proves_safe_core_and_live_adapter(self) -> None:
        audit = qualify_native_kernel_physical_memory._source_audit()
        self.assertEqual(0, audit["implementation_unauthorized_unsafe_token_count"])
        self.assertEqual(0, audit["heap_api_token_count"])
        self.assertEqual(5, audit["bootstrap_fixed_capacity_ledger_count"])
        self.assertEqual(0, audit["active_fixed_capacity_ledger_count"])
        self.assertEqual(15, audit["live_adapter_volatile_read_site_count"])
        self.assertEqual(13, audit["live_adapter_volatile_write_site_count"])
        self.assertEqual(2, audit["pksmp1_mailbox_volatile_read_site_count"])
        self.assertEqual(2, audit["pksmp1_mailbox_volatile_write_site_count"])
        self.assertEqual(2, audit["pksmp2_mailbox_volatile_read_site_count"])
        self.assertEqual(2, audit["pksmp2_mailbox_volatile_write_site_count"])
        self.assertEqual(2, audit["pksmp3_mailbox_volatile_read_site_count"])
        self.assertEqual(2, audit["pksmp3_mailbox_volatile_write_site_count"])
        self.assertTrue(audit["final_temporary_alias_revocation_required"])
        self.assertTrue(audit["final_guarded_metadata_mapping_retention_required"])

    def test_hostile_controls_detect_disabled_parser_and_memory_oracle(self) -> None:
        transcript = self.run_evidence["pbp1_transcript"]
        observation = physical_memory.validate_markers(self.markers)
        with mock.patch.object(physical_memory, "validate_markers", wraps=physical_memory.validate_markers) as parser:
            controls = qualify_native_kernel_physical_memory._negative_controls(self.markers, transcript)
        self.assertEqual(len(controls), 191)
        self.assertEqual(parser.call_count, 189)
        self.assertEqual([item["id"] for item in controls], list(physical_memory.NEGATIVE_CONTROL_IDS))
        with mock.patch.object(physical_memory, "validate_markers", return_value=observation):
            with self.assertRaisesRegex(qualify_native_kernel_physical_memory.QualificationError, "did not reject"):
                qualify_native_kernel_physical_memory._negative_controls(self.markers, transcript)
        with mock.patch.object(physical_memory, "validate_observation_binding", return_value={}):
            with self.assertRaisesRegex(qualify_native_kernel_physical_memory.QualificationError, "did not reject"):
                qualify_native_kernel_physical_memory._negative_controls(self.markers, transcript)

    def test_source_audit_rejects_missing_multi_ap_boundary(self) -> None:
        source = (physical_memory.ROOT / "native/kernel/src/main.rs").read_text(
            encoding="utf-8"
        )
        hostile = source.replace("enum SmpIpiLiveError", "enum RemovedSmpIpiLiveError", 1)
        with self.assertRaisesRegex(
            qualify_native_kernel_physical_memory.QualificationError,
            "PKSMP5 live adapter start boundary is missing",
        ):
            qualify_native_kernel_physical_memory._source_audit(hostile)

    def test_release_gate_accepts_only_the_bound_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_physical_memory_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn(
            f"scrub={physical_memory.SCRUB_BYTES}/{physical_memory.SCRUB_BYTES}",
            check["detail"],
        )
        self.assertIn("metadata=5+2_guards", check["detail"])
        self.assertIn("boot_reclaim=11250", check["detail"])
        self.assertIn("alias_revoked=1", check["detail"])
        self.assertIn("n9_exit=false", check["detail"])

    def test_recorded_memory_rejects_inconsistent_payloads(self) -> None:
        # Historical payload consistency is not a current-source qualification.
        self.assertEqual([], physical_memory.recorded_memory_errors(
            self.readiness["execution"], self.readiness["summary"]))
        for family, label, candidate in recorded_receipt_mutations(self.readiness):
            with self.subTest(family=family, case=label):
                self.assertTrue(physical_memory.recorded_memory_errors(
                    candidate["execution"], candidate["summary"]))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        self.assertEqual([], physical_memory.readiness_errors(self.readiness))
        self.assertTrue(pooleos_release_gate.check_native_kernel_physical_memory_readiness()["ok"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.json"
            for family, label, candidate in recorded_receipt_mutations(self.readiness):
                with self.subTest(family=family, case=label):
                    errors = physical_memory.readiness_errors(candidate)
                    self.assertTrue(any("recorded" in error for error in errors), errors)
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    check = pooleos_release_gate.check_native_kernel_physical_memory_readiness(path)
                    self.assertFalse(check["ok"], check)

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        self.assertEqual([], physical_memory.readiness_errors(self.readiness))
        candidate = copy.deepcopy(self.readiness)
        candidate["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with mock.patch.object(qualify_native_kernel_physical_memory, "make_readiness", return_value=candidate):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(1, qualify_native_kernel_physical_memory.main(["--out", str(path)]))
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
