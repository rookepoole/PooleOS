import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_smp_ipi as smp_ipi
from runtime import native_tier0
from tests.test_native_cpu_entry_provenance import pair_mutations
from tools import qualify_native_kernel_smp_ipi as qualify
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

    def leaves(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                yield from leaves(item, (*path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from leaves(item, (*path, index))
        else:
            yield path, value

    for path in (("execution",), ("execution", "observation"), ("summary",)):
        yield "shape", str(path), changed(path, None)
    for key, value in (("virtual_cpu_count", 4.0), ("application_processor_count", 3.0),
                       ("dynamic_fields_revalidated", 1), ("cpu_model", "qemu64"),
                       ("acceleration", "tcg_single_thread"), ("deterministic_instruction_clock", 0),
                       ("machine", "wrong"), ("profile_id", "wrong")):
        yield "dynamic-policy", key, changed(("execution", key), value)
    for section, fields in baseline["execution"]["observation"].items():
        path = ("execution", "observation", section)
        yield "observation", section, changed(path, None)
        if section == "transfer_prefix":
            continue
        for leaf, value in leaves(fields, path):
            substitute = int(value) if type(value) is bool else float(value) if type(value) is int else "invalid"
            for label, replacement in (("null", None), ("type-or-value", substitute)):
                yield "observation", str(leaf) + label, changed(leaf, replacement)
    for key, value in baseline["summary"].items():
        for label, replacement in (("null", None), ("type", float(value))):
            yield "summary", key + label, changed(("summary", key), replacement)
    for field in ("old_frame_checksum", "new_frame_checksum"):
        candidate = copy.deepcopy(baseline)
        for run in candidate["execution"]["runs"]:
            run["markers"][36] = qualify._set_field(run["markers"][36], field, "0x0000000000000001")
            run["marker_sha256"] = smp_ipi.sha256_bytes(smp_ipi.native_pooleboot.canonical_json_bytes(run["markers"]))
        yield "raw-frame", field, candidate
    for index, control in enumerate(baseline["negative_controls"]):
        for value in (control["case_count"] + 1, float(control["case_count"])):
            yield "controls", str((index, value)), changed(("negative_controls", index, "case_count"), value)
    candidate = copy.deepcopy(baseline)
    candidate["negative_controls"][0]["case_count"] += 1
    candidate["negative_controls"][3]["case_count"] -= 1
    yield "controls", "redistribution-same-total", candidate


class NativeKernelSmpIpiTests(unittest.TestCase):
    def test_inputs_bind_current_transfer_and_six_boot_artifacts(self) -> None:
        inputs = smp_ipi.expected_inputs()
        self.assertEqual(smp_ipi.native_kernel_transfer.READINESS_RELATIVE,
                         inputs["boot_transfer"]["path"])
        self.assertEqual(6, len(inputs["boot_artifacts"]))
        self.assertEqual(6, len({item["path"] for item in inputs["boot_artifacts"]}))

    def test_relabelled_consistent_boot_digests_cannot_pass_current_readiness(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(report))
        fields = ("retained_set_sha256", "policy_sha256", "state_sha256")
        original = report["execution"]["observation"]["transfer_prefix"]["kernel_revalidation"]
        for field in fields:
            changed = copy.deepcopy(report)
            replacement = smp_ipi.sha256_bytes(original[field].encode("ascii"))
            for run in changed["execution"]["runs"]:
                run["markers"] = [line.replace(original[field], replacement) for line in run["markers"]]
                run["marker_summary"] = smp_ipi.validate_markers(run["markers"])
            changed["execution"]["observation"] = changed["execution"]["runs"][0]["marker_summary"]
            with self.subTest(field=field):
                errors = smp_ipi.readiness_errors(changed)
                self.assertTrue(any("current boot" in error for error in errors), errors)

    def test_stale_transfer_dependency_is_rejected(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(report))
        with patch.object(smp_ipi.native_kernel_transfer, "readiness_errors", return_value=["stale dependency"]):
            errors = smp_ipi.readiness_errors(report)
        self.assertTrue(any("transfer dependency" in error for error in errors), errors)

    def test_malformed_transfer_dependency_returns_errors(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(report))
        read_json = smp_ipi.read_json
        dependency = smp_ipi.ROOT / smp_ipi.native_kernel_transfer.READINESS_RELATIVE
        for malformed in (None, [], "receipt", 1):
            with self.subTest(value=malformed), patch.object(
                smp_ipi, "read_json",
                side_effect=lambda path: malformed if path == dependency else read_json(path),
            ):
                errors = smp_ipi.readiness_errors(report)
                self.assertTrue(any("transfer dependency" in error for error in errors), errors)

    def test_regenerated_boot_bytes_cannot_disagree_with_transfer(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(report))
        files = smp_ipi.native_kernel_load.canonical_artifact_files()
        first = next(iter(files))
        files[first] = bytes([files[first][0] ^ 1]) + files[first][1:]
        with patch.object(smp_ipi.native_kernel_load, "canonical_artifact_files", return_value=files):
            report["inputs"] = smp_ipi.expected_inputs()
            errors = smp_ipi.readiness_errors(report)
        self.assertTrue(any("current boot artifacts" in error for error in errors), errors)

    def test_readiness_writer_emits_canonical_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "readiness.json"
            qualify._write_readiness(path, {"status": "pass", "values": [1, 2]})
            data = path.read_bytes()
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(data.endswith(b"\n"))

    def test_contract_schema_and_negative_control_order(self) -> None:
        contract = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.CONTRACT_RELATIVE)
        self.assertEqual([], smp_ipi.contract_errors(contract))
        self.assertEqual(33, len(smp_ipi.NEGATIVE_CONTROL_IDS))
        self.assertEqual(609, contract["qualification"]["hostile_case_count"])
        for field in smp_ipi.mailbox_evidence.CONTRACT:
            changed = copy.deepcopy(contract)
            del changed["mailbox_evidence"][field]
            with self.subTest(missing_mailbox_field=field):
                self.assertTrue(smp_ipi.contract_errors(changed))

    def test_three_private_resource_layouts_fit_below_one_mib(self) -> None:
        layouts = [smp_ipi.resource_layout(page, 32) for page in (1, 35, 69)]
        self.assertEqual([0x1000, 0x23000, 0x45000], [item["start"] for item in layouts])
        self.assertEqual([0x20000, 0x42000, 0x64000], [item["apic_page_table"] for item in layouts])
        self.assertEqual(3, len({item["pml4"] for item in layouts}))
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.resource_layout(1, 31)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.resource_layout(0, 32)

    def test_exact_topology_and_local_masks_fail_closed(self) -> None:
        smp_ipi.validate_exact_topology(4, 4, 0, (1, 2, 3))
        self.assertEqual([2, 4, 8], [smp_ipi.local_target_mask(value) for value in (1, 2, 3)])
        self.assertEqual(14, sum(smp_ipi.local_target_mask(value) for value in (1, 2, 3)))
        for value in ((3, 3, 0, (1, 2, 3)), (4, 3, 0, (1, 2, 3)), (4, 4, 1, (1, 2, 3)), (4, 4, 0, (1, 2, 4))):
            with self.assertRaises(smp_ipi.KernelSmpIpiError):
                smp_ipi.validate_exact_topology(*value)

    def test_request_model_accepts_canonical_and_rejects_controls(self) -> None:
        request = smp_ipi.canonical_request(1, 1, 4, 2)
        smp_ipi.validate_request(request, 4, 2, 0, 0)
        invalid = request.copy()
        invalid["capability_high"] ^= 1
        invalid["checksum"] = smp_ipi.request_checksum(invalid)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(invalid, 4, 2, 0, 0)
        wrong_vector = request.copy()
        wrong_vector["vector"] = 225
        wrong_vector["checksum"] = smp_ipi.request_checksum(wrong_vector)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_request(wrong_vector, 4, 2, 0, 0)

    def test_response_checksum_is_independent_and_frozen(self) -> None:
        checksum = smp_ipi.response_checksum({
            "ack_attempt": 4,
            "ack_sequence": 3,
            "result": int(smp_ipi.OPERATIONS[6]["result"]),
            "last_accepted_sequence": 3,
            "ack_operation": 6,
            "ack_status": 1,
            "ack_error": 0,
            "delivery_count": 4,
            "accepted_count": 3,
            "denied_count": 1,
        })
        self.assertEqual(0x1A04_0602_5350_0005, checksum)

    def test_aggregate_address_checksum_is_ordered_and_nonzero(self) -> None:
        values = [(2, 0x20000), (4, 0x42000), (8, 0x64000)]
        checksum = smp_ipi.aggregate_address_checksum(values, smp_ipi.AGGREGATE_ROOT_DOMAIN)
        self.assertNotEqual(0, checksum)
        self.assertNotEqual(
            checksum,
            smp_ipi.aggregate_address_checksum(list(reversed(values)), smp_ipi.AGGREGATE_ROOT_DOMAIN),
        )

    def test_multi_reclaim_waits_for_three_unique_acknowledgements(self) -> None:
        requests = qualify._multi_requests()
        model = smp_ipi.DeferredReclaimModel(requests)
        model.arm()
        model.timeout()
        model.retry()
        for index, request in enumerate(requests):
            model.acknowledge(
                smp_ipi.canonical_shootdown_snapshot(request, int(index == 0)),
                smp_ipi.EXPECTED_APIC_IDS[index],
            )
            if index < 2:
                with self.assertRaises(smp_ipi.KernelSmpIpiError):
                    model.authorize()
        model.authorize()
        model.release()
        self.assertEqual("released", model.stage)

        duplicate = smp_ipi.DeferredReclaimModel(requests)
        duplicate.arm()
        ack = smp_ipi.canonical_shootdown_snapshot(requests[0])
        duplicate.acknowledge(ack, 1)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            duplicate.acknowledge(ack, 1)

    def test_partial_lifecycle_requires_complete_park_release_and_retry(self) -> None:
        model = smp_ipi.MultiApLifecycleModel()
        model.partial(0x6, 0x10, 0x6, 0xE)
        model.retry(0xE, 0xE)
        model.complete(0xE, 0xE, 0xE, 0xE)
        self.assertEqual("released", model.stage)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.MultiApLifecycleModel().partial(0x2, 0x10, 0x2, 0xE)

    def test_multi_ap_receipts_allow_metadata_growth_gaps_but_reject_aliases(self) -> None:
        receipts = [
            {"allocation_sequence": 24, "frame_allocation_sequences": (25, 26), "frame_release_sequences": (35, 42), "resource_release_sequence": 43},
            {"allocation_sequence": 27, "frame_allocation_sequences": (28, 31), "frame_release_sequences": (36, 40), "resource_release_sequence": 41},
            {"allocation_sequence": 32, "frame_allocation_sequences": (33, 34), "frame_release_sequences": (37, 38), "resource_release_sequence": 39},
        ]
        smp_ipi.validate_receipt_sequences(receipts)
        hostile = [item.copy() for item in receipts]
        hostile[1]["frame_allocation_sequences"] = (28, 33)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_receipt_sequences(hostile)
        zero_sequence = [item.copy() for item in receipts]
        zero_sequence[0]["allocation_sequence"] = 0
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_receipt_sequences(zero_sequence)

    def test_sandybridge_profile_is_four_cpu_multi_tcg_without_icount(self) -> None:
        _, base = native_tier0.validate_contracts(smp_ipi.ROOT)
        profile = qualify._sandybridge_profile(base)
        arguments = profile["base_argument_template"]
        self.assertEqual("SandyBridge,-avx", arguments[arguments.index("-cpu") + 1])
        self.assertEqual("tcg,thread=multi", arguments[arguments.index("-accel") + 1])
        self.assertEqual("4,sockets=1,dies=1,clusters=1,cores=4,threads=1,maxcpus=4", arguments[arguments.index("-smp") + 1])
        self.assertNotIn("-icount", arguments)

    def test_source_audit_requires_dynamic_local_mask_and_coordinator(self) -> None:
        audit = qualify._source_audit()
        self.assertGreaterEqual(audit["xsave_instruction_count"], 2)
        self.assertEqual(6, audit["operation_handler_count"])
        self.assertEqual(1, audit["remote_shootdown_invlpg_source_count"])
        self.assertEqual(3, audit["application_processor_count"])
        arch = (smp_ipi.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        main = (smp_ipi.ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
        ipi = (smp_ipi.ROOT / "native/kernel/src/smp_ipi.rs").read_text(encoding="utf-8")
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._audit_source_text(arch.replace("shl rbx, cl", "shl rbx, 1", 1), main, ipi)
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._audit_source_text(arch.replace(".Lpoole_ap_ipi_count_stop:", ".Lpoole_ap_ipi_count_terminal:", 1), main, ipi)
        for token in (
            "mailbox_evidence=PKMBX1 snapshot=quiesced context_words=",
            "operation.mailbox_context.iter()", "smp_runtime::baseline_checksum_words(&mailbox)",
            "smp_runtime::runtime_checksum_words(&mailbox)",
        ):
            with self.subTest(omitted=token), self.assertRaisesRegex(smp_ipi.KernelSmpIpiError, "PKMBX1"):
                qualify._audit_source_text(arch, main.replace(token, "omitted", 1), ipi)

    def test_linked_invlpg_scope_separates_ipi_and_successor_profile(self) -> None:
        disassembly = (
            "0000000000001000 <poole_ap_ipi_trampoline_start>:\n"
            "    1000: 0f 01 38\tinvlpg\t(%rax)\n"
            "    1003: 0f 01 3b\tinvlpg\t(%rbx)\n"
            "0000000000001006 <poole_ap_ipi_trampoline_end>:\n"
        )
        audit = qualify._linked_invlpg_scope(disassembly)
        self.assertEqual(2, audit["invlpg_instruction_count"])
        self.assertEqual(1, audit["remote_shootdown_invlpg_instruction_count"])
        self.assertEqual(3, audit["runtime_execution_count"])
        self.assertEqual(1, audit["successor_profile_invlpg_instruction_count"])
        self.assertFalse(audit["successor_profile_executed"])
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            qualify._linked_invlpg_scope(disassembly.replace("invlpg", "nop", 1))

    def test_live_readiness_and_hostile_cases_when_generated(self) -> None:
        path = smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSMP5 readiness has not been generated yet")
        readiness = smp_ipi.read_json(path)
        if readiness.get("contract_id") != "PKSMP5":
            self.skipTest("PKSMP5 readiness has not replaced the predecessor receipt yet")
        self.assertEqual([], smp_ipi.readiness_errors(readiness))
        observation = smp_ipi.validate_markers(readiness["execution"]["runs"][0]["markers"])
        self.assertEqual(3, observation["result"]["application_processors_online"])
        controls = qualify._negative_controls(readiness["execution"]["runs"][0]["markers"])
        self.assertEqual(list(smp_ipi.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(609, sum(item["case_count"] for item in controls))
        check = pooleos_release_gate.check_native_kernel_smp_ipi_readiness()
        self.assertTrue(check["ok"], check["detail"])


    def test_ownership_contract_rejects_missing_or_changed_fields(self) -> None:
        contract = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.CONTRACT_RELATIVE)
        for field in contract["execution_ownership"]:
            changed = copy.deepcopy(contract)
            del changed["execution_ownership"][field]
            with self.subTest(missing=field):
                self.assertTrue(smp_ipi.contract_errors(changed))
        for field, value in (
            ("retained_regions_per_ap", 1), ("retained_free_rejections_per_attempt", 9),
            ("owner_release_rejections_per_attempt", 0), ("attempt_count", 1),
            ("park_boundary", "mailbox_only"), ("general_cpu_retirement_verified", True),
        ):
            changed = copy.deepcopy(contract)
            changed["execution_ownership"][field] = value
            with self.subTest(changed=field):
                self.assertTrue(smp_ipi.contract_errors(changed))

    def test_source_audit_requires_live_ownership_controls(self) -> None:
        arch = (smp_ipi.ROOT / "native/kernel/src/arch/x86_64.rs").read_text(encoding="utf-8")
        main = (smp_ipi.ROOT / "native/kernel/src/main.rs").read_text(encoding="utf-8")
        ipi = (smp_ipi.ROOT / "native/kernel/src/smp_ipi.rs").read_text(encoding="utf-8")
        qualify._audit_source_text(arch, main, ipi)
        probe = main.partition("fn smp_ipi_probe_retained_resources(")[2].split("\nfn ", 1)[0]
        for token in (
            "ApResourcePart::Runtime", "ApResourcePart::OldFrame", "ApResourcePart::NewFrame",
            "manager.free(handle)", "manager.free_scrubbed(handle, access)",
            "manager.free_scrubbed_automatic(handle, access)",
            "release_scrubbed(part, manager, access)",
            "release_scrubbed_automatic(part, manager, access)",
            "manager.summary() != before",
        ):
            with self.subTest(omitted=token), self.assertRaises(smp_ipi.KernelSmpIpiError):
                qualify._audit_source_text(arch, main.replace(probe, probe.replace(token, "omitted", 1), 1), ipi)

    def test_recorded_ownership_cannot_disagree_with_live_markers(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(report))
        for mode in ("missing_run", "run_summary", "aggregate"):
            changed = copy.deepcopy(report)
            if mode == "missing_run":
                changed["execution"]["runs"].pop()
            elif mode == "run_summary":
                changed["execution"]["runs"][1]["marker_summary"]["execution_ownership"]["owner_release_rejections_per_attempt"] = 0
            else:
                changed["execution"]["observation"]["execution_ownership"]["general_cpu_retirement_verified"] = True
            with self.subTest(mode=mode):
                self.assertTrue(smp_ipi.readiness_errors(changed))


    def test_marker_observations_survive_json_round_trip(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        for run in report["execution"]["runs"]:
            observed = smp_ipi.validate_markers(run["markers"])
            self.assertEqual(observed, json.loads(json.dumps(observed)))

    def test_malformed_receipt_shapes_return_errors(self) -> None:
        for value in (None, [], "receipt", 1, {"execution": None}, {"negative_controls": None}):
            with self.subTest(value=value):
                self.assertTrue(smp_ipi.readiness_errors(value))


    def test_release_gate_rejects_stale_kernel_and_ownership_summaries(self) -> None:
        report = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        check = pooleos_release_gate.check_native_kernel_smp_ipi_readiness()
        self.assertTrue(check["ok"], check["detail"])
        for field in ("kernel", "count", "ownership", "retirement_type"):
            changed = copy.deepcopy(report)
            if field == "kernel":
                changed["build"]["kernel_entry"]["product"]["canonical_sha256"] = "D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4"
            elif field == "count":
                changed["summary"]["hostile_cases_total"] = 243
            elif field == "ownership":
                changed["execution"]["observation"]["execution_ownership"]["owner_release_rejections_per_attempt"] = 0
            else:
                changed["execution"]["observation"]["execution_ownership"]["general_cpu_retirement_verified"] = 0
            with self.subTest(field=field), patch.object(pooleos_release_gate, "_load_schema_artifact", return_value=(changed, [])):
                self.assertFalse(pooleos_release_gate.check_native_kernel_smp_ipi_readiness()["ok"])


    def test_recorded_payload_rejects_inconsistent_execution(self) -> None:
        # Payload consistency alone never establishes current-source qualification.
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.recorded_ipi_errors(baseline["execution"], baseline["summary"]))
        for family, label, candidate in recorded_receipt_mutations(baseline):
            if family == "controls":
                continue
            with self.subTest(family=family, case=label):
                self.assertTrue(smp_ipi.recorded_ipi_errors(candidate["execution"], candidate["summary"]))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(baseline))
        self.assertTrue(pooleos_release_gate.check_native_kernel_smp_ipi_readiness()["ok"])
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
                    self.assertTrue(smp_ipi.readiness_errors(candidate))
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    self.assertFalse(pooleos_release_gate.check_native_kernel_smp_ipi_readiness(path)["ok"])

    def test_frame_checksum_oracle_uses_addresses_order_and_domain(self) -> None:
        old = [(2, 0x21000), (4, 0x43000), (8, 0x65000)]
        new = [(2, 0x22000), (4, 0x44000), (8, 0x66000)]
        self.assertEqual(0xBE1E07C6144BC01A, smp_ipi.aggregate_address_checksum(old, smp_ipi.AGGREGATE_OLD_FRAME_DOMAIN))
        self.assertEqual(0xE351D68DF0864FAA, smp_ipi.aggregate_address_checksum(new, smp_ipi.AGGREGATE_NEW_FRAME_DOMAIN))
        self.assertNotEqual(smp_ipi.aggregate_address_checksum(old, smp_ipi.AGGREGATE_OLD_FRAME_DOMAIN),
                            smp_ipi.aggregate_address_checksum(old, smp_ipi.AGGREGATE_NEW_FRAME_DOMAIN))
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        markers = baseline["execution"]["runs"][0]["markers"]
        smp_ipi.validate_markers(markers)
        for field, values, domain in (("old_frame_checksum", old, smp_ipi.AGGREGATE_OLD_FRAME_DOMAIN),
                                      ("new_frame_checksum", new, smp_ipi.AGGREGATE_NEW_FRAME_DOMAIN)):
            for altered in (list(reversed(values)), [(mask, address + 4096) for mask, address in values]):
                candidate = markers.copy()
                checksum = smp_ipi.aggregate_address_checksum(altered, domain)
                candidate[36] = qualify._set_field(candidate[36], field, f"0x{checksum:016X}")
                with self.subTest(field=field, altered=altered), self.assertRaises(smp_ipi.KernelSmpIpiError):
                    smp_ipi.validate_markers(candidate)

    def test_ap_checksums_are_recomputed_before_normalization(self) -> None:
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        markers = baseline["execution"]["runs"][0]["markers"]
        normalized = smp_ipi.normalize_dynamic_markers(markers)
        for index in range(33, 36):
            for field in ("baseline_checksum", "runtime_checksum"):
                candidate = markers.copy()
                candidate[index] = qualify._set_field(candidate[index], field, "0x0000000000000000")
                with self.subTest(index=index, field=field), self.assertRaises(smp_ipi.KernelSmpIpiError):
                    smp_ipi.normalize_dynamic_markers(candidate)
        synthetic = markers.copy()
        for index in range(33, 36):
            synthetic[index] = qualify._set_field(synthetic[index], "baseline_checksum", "0x0000000000000001")
            synthetic[index] = qualify._set_field(synthetic[index], "runtime_checksum", "0x0000000000000002")
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.normalize_dynamic_markers(synthetic)
        self.assertIn("<validated-dynamic>", normalized[33])
        self.assertNotIn("guest-checked", normalized[33])

    def test_complete_mailbox_mutations_reject_before_normalization(self) -> None:
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(baseline))
        markers = baseline["execution"]["runs"][0]["markers"]
        self.assertTrue(pooleos_release_gate.check_native_kernel_smp_ipi_readiness()["ok"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.json"
            for index in range(3):
                candidates = list(qualify.mailbox_mutations(markers, index))
                self.assertEqual(120, len(candidates))
                for case, candidate in enumerate(candidates):
                    with self.subTest(ap=index, case=case):
                        with self.assertRaises(smp_ipi.KernelSmpIpiError):
                            smp_ipi.normalize_dynamic_markers(candidate)
                        changed = copy.deepcopy(baseline)
                        run = changed["execution"]["runs"][0]
                        run["markers"] = candidate
                        run["marker_sha256"] = smp_ipi.sha256_bytes(
                            smp_ipi.native_pooleboot.canonical_json_bytes(candidate))
                        self.assertTrue(smp_ipi.readiness_errors(changed))
                        path.write_text(json.dumps(changed, allow_nan=False), encoding="utf-8")
                        self.assertFalse(pooleos_release_gate.check_native_kernel_smp_ipi_readiness(path)["ok"])

    def test_opaque_historical_marker_and_inconsistent_context_rejected(self) -> None:
        import re
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        markers = baseline["execution"]["runs"][0]["markers"]
        smp_ipi.validate_markers(markers)
        old = markers.copy()
        old[33] = re.sub(r" mailbox_evidence=.*?(?= tss_busy=)", "", old[33])
        with self.assertRaises(smp_ipi.KernelSmpIpiError):
            smp_ipi.validate_markers(old)
        changed = markers.copy()
        match = smp_ipi.AP.fullmatch(changed[34])
        context = match.group("context_words").split(",")
        context[-1] = f"0x{int(context[-1], 16) + 1:016X}"
        changed[34] = qualify._set_field(changed[34], "context_words", ",".join(context))
        with self.assertRaisesRegex(smp_ipi.KernelSmpIpiError, "context differs"):
            smp_ipi.normalize_dynamic_markers(changed)

    def test_release_accounting_controls_execute_real_validator(self) -> None:
        smp_ipi.validate_release_accounting(96, 6, 417792)
        for values in ((95, 6, 417792), (96, 5, 417792), (96, 6, 413696),
                       (96.0, 6, 417792), (96, 6.0, 417792), (96, 6, 417792.0)):
            with self.subTest(values=values), self.assertRaises(smp_ipi.KernelSmpIpiError):
                smp_ipi.validate_release_accounting(*values)
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        markers = baseline["execution"]["runs"][0]["markers"]
        controls = qualify._negative_controls(markers)
        self.assertEqual(list(smp_ipi.NEGATIVE_CONTROL_CASE_COUNTS), [item["case_count"] for item in controls])
        with patch.object(smp_ipi, "validate_release_accounting", return_value=None):
            with self.assertRaisesRegex(qualify.QualificationError, "RELEASE-ACCOUNTING-MODEL"):
                qualify._negative_controls(markers)
        by_ap = {ap["apic_id"]: ap["mailbox_evidence"] for ap in smp_ipi.validate_markers(markers)["aps"]}
        with patch.object(smp_ipi.mailbox_evidence, "validate",
                          side_effect=lambda *args: copy.deepcopy(by_ap[args[-2]])):
            with self.assertRaisesRegex(qualify.QualificationError, "PKMBX1-AP0-ORACLE"):
                qualify._negative_controls(markers)

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        baseline = smp_ipi.read_json(smp_ipi.ROOT / smp_ipi.READINESS_RELATIVE)
        self.assertEqual([], smp_ipi.readiness_errors(baseline))
        baseline["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with patch.object(qualify, "make_readiness", return_value=baseline):
                    with self.assertRaises(qualify.QualificationError):
                        qualify.main(["--out", str(path)])
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
