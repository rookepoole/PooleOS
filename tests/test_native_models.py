import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_models  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lock = native_models.read_json(ROOT / native_models.LOCK_RELATIVE)
        cls.contract = native_models.read_json(ROOT / native_models.CONTRACT_RELATIVE)
        cls.readiness_path = ROOT / native_models.READINESS_RELATIVE
        cls.readiness = native_models.read_json(cls.readiness_path)

    def test_public_contracts_match_schemas(self) -> None:
        cases = (
            (self.lock, native_models.LOCK_SCHEMA_RELATIVE),
            (self.contract, native_models.CONTRACT_SCHEMA_RELATIVE),
            (self.readiness, native_models.READINESS_SCHEMA_RELATIVE),
        )
        for artifact, schema_relative in cases:
            with self.subTest(schema=schema_relative):
                schema = native_models.read_json(ROOT / schema_relative)
                self.assertEqual([], list(validate_json(artifact, schema)))

    def test_frozen_contracts_pass_semantic_validation(self) -> None:
        lock, contract = native_models.validate_contracts()
        self.assertEqual(self.lock, lock)
        self.assertEqual(self.contract, contract)

    def test_tlc_stable_release_and_prerelease_rejection_are_explicit(self) -> None:
        self.assertEqual("v1.7.4", self.lock["tlc"]["release_tag"])
        self.assertTrue(self.lock["tlc"]["stable_release"])
        self.assertFalse(self.lock["tlc"]["prerelease"])
        self.assertEqual("v1.8.0", self.lock["tlc"]["rejected_candidate"]["release_tag"])
        self.assertTrue(self.lock["tlc"]["rejected_candidate"]["prerelease"])

    def test_unsigned_tool_inputs_are_not_overclaimed(self) -> None:
        self.assertFalse(self.lock["tlc"]["tag_or_commit_signature_verified"])
        self.assertFalse(self.lock["tlc"]["jar"]["detached_signature_available"])
        self.assertFalse(self.lock["java"]["detached_signature_verified"])

    def test_toolchain_is_workspace_local_and_non_promoting(self) -> None:
        boundary = self.lock["supply_chain_boundary"]
        self.assertTrue(boundary["workspace_local_only"])
        for key, value in boundary.items():
            if key != "workspace_local_only":
                self.assertFalse(value, key)
        self.assertFalse(self.lock["production_promotion_allowed"])
        bootstrap = (ROOT / "tools" / "bootstrap_native_models.ps1").read_text(encoding="utf-8")
        self.assertIn("must remain below the repository .toolchains directory", bootstrap)
        self.assertIn("contains a reparse point", bootstrap)

    def test_java_runtime_closure_is_exact(self) -> None:
        self.assertEqual(
            {"file_count": 315, "byte_count": 151530953, "tree_sha256": "057E582B6FAC90535C1A51A66856C7D7DCCE27B03536FA0FB019A7C7ADA56DC9"},
            self.lock["java"]["runtime_tree"],
        )
        self.assertEqual("Valid", self.lock["java"]["java_executable"]["authenticode_status"])

    def test_required_and_modeled_domain_sets_are_frozen(self) -> None:
        self.assertEqual(7, len(self.contract["required_domains"]))
        self.assertEqual(6, len(self.contract["modeled_domains"]))
        self.assertEqual(
            {"capability_derivation_revocation", "ipc_state", "scheduler_transitions", "virtual_memory_map_unmap", "boot_slot_state", "update_rollback"},
            set(self.contract["modeled_domains"]),
        )

    def test_model_identifiers_and_invariants_are_frozen(self) -> None:
        models = {item["id"]: item for item in self.contract["models"]}
        self.assertEqual(
            {"boot_slot_rollback", "capability_revocation", "virtual_memory_ownership", "capability_mediated_ipc", "bounded_scheduler"},
            set(models),
        )
        self.assertIn("Recoverable", models["boot_slot_rollback"]["invariants"])
        self.assertIn("NoLiveDescendantOfRevoked", models["capability_revocation"]["invariants"])
        self.assertIn("RetiredPendingConsistency", models["virtual_memory_ownership"]["invariants"])
        self.assertIn("AcceptedRepliesFresh", models["capability_mediated_ipc"]["invariants"])
        self.assertIn("ClosedEndpointQuiescent", models["capability_mediated_ipc"]["invariants"])
        self.assertIn("PriorityInheritanceSound", models["bounded_scheduler"]["invariants"])
        self.assertIn("BypassBound", models["bounded_scheduler"]["invariants"])
        self.assertEqual(6, len(models["boot_slot_rollback"]["invariants"]))
        self.assertEqual(6, len(models["capability_revocation"]["invariants"]))
        self.assertEqual(7, len(models["virtual_memory_ownership"]["invariants"]))
        self.assertEqual(11, len(models["capability_mediated_ipc"]["invariants"]))
        self.assertEqual(15, len(models["bounded_scheduler"]["invariants"]))

    def test_normalized_commands_are_closed_and_exact(self) -> None:
        for model in self.contract["models"]:
            for case in model["cases"]:
                command = native_models.normalized_command(self.contract, model, case)
                self.assertEqual(17, len(command))
                self.assertEqual(model["module_path"], command[-1])
                self.assertEqual(case["config_path"], command[-2])
                self.assertNotIn("-simulate", command)
                self.assertNotIn("-continue", command)

    def test_model_configs_freeze_all_case_constants(self) -> None:
        for model in self.contract["models"]:
            for case in model["cases"]:
                config = (ROOT / case["config_path"]).read_text(encoding="utf-8")
                for name, value in case["constant_assignments"].items():
                    self.assertIn(f"{name} = {value}", config)

    def test_vm_mutants_are_independent_and_named(self) -> None:
        model = next(item for item in self.contract["models"] if item["id"] == "virtual_memory_ownership")
        cases = {item["id"]: item for item in model["cases"]}
        self.assertEqual({"safe", "unsafe_stale_mapping", "unsafe_early_reuse"}, set(cases))
        self.assertEqual("PageTableSafety", cases["unsafe_stale_mapping"]["expected_invariant_violation"])
        self.assertEqual("TlbSafety", cases["unsafe_early_reuse"]["expected_invariant_violation"])
        self.assertEqual(
            {"UnsafeStaleMapping": "TRUE", "UnsafeEarlyReuse": "FALSE"},
            cases["unsafe_stale_mapping"]["constant_assignments"],
        )
        self.assertEqual(
            {"UnsafeStaleMapping": "FALSE", "UnsafeEarlyReuse": "TRUE"},
            cases["unsafe_early_reuse"]["constant_assignments"],
        )

    def test_ipc_mutants_are_independent_and_named(self) -> None:
        model = next(item for item in self.contract["models"] if item["id"] == "capability_mediated_ipc")
        cases = {item["id"]: item for item in model["cases"]}
        self.assertEqual(
            {"safe", "unsafe_unauthorized_call", "unsafe_token_reuse", "unsafe_stale_reply", "unsafe_leaky_teardown"},
            set(cases),
        )
        expected_violations = {
            "unsafe_unauthorized_call": "QueuedCallAuthorized",
            "unsafe_token_reuse": "LiveTokenConsistent",
            "unsafe_stale_reply": "AcceptedRepliesFresh",
            "unsafe_leaky_teardown": "ClosedEndpointQuiescent",
        }
        self.assertTrue(all(value == "FALSE" for value in cases["safe"]["constant_assignments"].values()))
        for case_id, invariant in expected_violations.items():
            with self.subTest(case=case_id):
                case = cases[case_id]
                self.assertEqual(invariant, case["expected_invariant_violation"])
                self.assertEqual(1, sum(value == "TRUE" for value in case["constant_assignments"].values()))

    def test_scheduler_mutants_are_independent_and_named(self) -> None:
        model = next(item for item in self.contract["models"] if item["id"] == "bounded_scheduler")
        cases = {item["id"]: item for item in model["cases"]}
        expected_violations = {
            "unsafe_lost_cancel_wake": "WakeDeliverySound",
            "unsafe_lost_timeout_wake": "WakeDeliverySound",
            "unsafe_duplicate_wakeup": "NoDuplicateRunnable",
            "unsafe_no_priority_inheritance": "PriorityInheritanceSound",
            "unsafe_priority_bypass": "DispatchPrioritySound",
            "unsafe_fairness_bypass": "BypassBound",
            "unsafe_scheduler_teardown_leak": "TerminalQuiescent",
        }
        self.assertEqual({"safe", *expected_violations}, set(cases))
        self.assertTrue(all(value == "FALSE" for value in cases["safe"]["constant_assignments"].values()))
        for case_id, invariant in expected_violations.items():
            with self.subTest(case=case_id):
                case = cases[case_id]
                self.assertEqual(invariant, case["expected_invariant_violation"])
                self.assertEqual(1, sum(value == "TRUE" for value in case["constant_assignments"].values()))

    def test_model_input_paths_are_confined(self) -> None:
        for relative in native_models.MODEL_INPUTS:
            self.assertTrue(native_models._model_input_path(relative).is_file())
        for relative in ("../README.md", "README.md", str(ROOT / "README.md")):
            with self.subTest(path=relative):
                with self.assertRaises(native_models.NativeModelError):
                    native_models._model_input_path(relative)

    def test_runtime_tree_hash_is_order_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b").write_bytes(b"second")
            (root / "a").write_bytes(b"first")
            first = native_models.runtime_tree_binding(root)
            second = native_models.runtime_tree_binding(root)
            self.assertEqual(first, second)
            self.assertEqual(2, first["file_count"])
            link = root / "linked"
            try:
                link.symlink_to(root / "a")
            except OSError:
                return
            with self.assertRaises(native_models.NativeModelError):
                native_models.runtime_tree_binding(root)

    def test_tool_message_parser_accepts_safe_result(self) -> None:
        output = """@!@!@STARTMSG 2262:0 @!@!@
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
@!@!@ENDMSG 2262 @!@!@
@!@!@STARTMSG 2193:0 @!@!@
Model checking completed. No error has been found.
@!@!@ENDMSG 2193 @!@!@
@!@!@STARTMSG 2199:0 @!@!@
46 states generated, 20 distinct states found, 0 states left on queue.
@!@!@ENDMSG 2199 @!@!@
@!@!@STARTMSG 2194:0 @!@!@
The depth of the complete state graph search is 7.
@!@!@ENDMSG 2194 @!@!@
"""
        parsed = native_models.parse_tlc_output(output, 0)
        self.assertEqual(46, parsed["generated_states"])
        self.assertIsNone(parsed["observed_invariant_violation"])
        self.assertEqual([], parsed["trace"])

    def test_tool_message_parser_normalizes_hostile_trace(self) -> None:
        output = """@!@!@STARTMSG 2262:0 @!@!@
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
@!@!@ENDMSG 2262 @!@!@
@!@!@STARTMSG 2110:1 @!@!@
Invariant Recoverable is violated.
@!@!@ENDMSG 2110 @!@!@
@!@!@STARTMSG 2217:4 @!@!@
1: <Initial predicate>
/\\ knownGood = {SlotA}
@!@!@ENDMSG 2217 @!@!@
@!@!@STARTMSG 2217:4 @!@!@
2: <TrialFailure line 1, col 1 to line 2, col 2 of module PooleBootSlots>
/\\ knownGood = {}
@!@!@ENDMSG 2217 @!@!@
@!@!@STARTMSG 2199:0 @!@!@
14 states generated, 8 distinct states found, 2 states left on queue.
@!@!@ENDMSG 2199 @!@!@
@!@!@STARTMSG 2194:0 @!@!@
The depth of the complete state graph search is 4.
@!@!@ENDMSG 2194 @!@!@
"""
        parsed = native_models.parse_tlc_output(output, 12)
        self.assertEqual("Recoverable", parsed["observed_invariant_violation"])
        self.assertEqual(["Init", "TrialFailure"], [item["action"] for item in parsed["trace"]])
        self.assertTrue(all("line" not in item["action"] for item in parsed["trace"]))

    def test_tool_message_parser_rejects_exit_message_disagreement(self) -> None:
        output = """@!@!@STARTMSG 2262:0 @!@!@
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
@!@!@ENDMSG 2262 @!@!@
@!@!@STARTMSG 2193:0 @!@!@
Model checking completed. No error has been found.
@!@!@ENDMSG 2193 @!@!@
@!@!@STARTMSG 2199:0 @!@!@
1 states generated, 1 distinct states found, 0 states left on queue.
@!@!@ENDMSG 2199 @!@!@
@!@!@STARTMSG 2194:0 @!@!@
The depth of the complete state graph search is 1.
@!@!@ENDMSG 2194 @!@!@
"""
        with self.assertRaises(native_models.NativeModelError):
            native_models.parse_tlc_output(output, 12)

    def test_readiness_passes_semantic_contract(self) -> None:
        self.assertEqual([], native_models.readiness_contract_errors(self.readiness))
        self.assertTrue(self.readiness["n4_model_slice_satisfied"])
        self.assertFalse(self.readiness["n4_exit_gate_satisfied"])
        release_check = pooleos_release_gate.check_native_model_readiness()
        self.assertTrue(release_check["ok"], release_check["detail"])

    def test_safe_state_spaces_are_completely_drained(self) -> None:
        safe = [item for item in self.readiness["runs"] if item["mode"] == "safe"]
        self.assertEqual(5, len(safe))
        self.assertTrue(all(item["observed_exit_code"] == 0 for item in safe))
        self.assertTrue(all(item["left_on_queue"] == 0 for item in safe))
        self.assertEqual({20, 621, 1316, 1422, 2391}, {item["distinct_states"] for item in safe})

    def test_hostile_counterexamples_are_exact(self) -> None:
        hostile = {item["id"]: item for item in self.readiness["runs"] if item["mode"] == "hostile"}
        boot = hostile["boot_slot_rollback.unsafe_rollback"]
        capability = hostile["capability_revocation.unsafe_local_revoke"]
        stale = hostile["virtual_memory_ownership.unsafe_stale_mapping"]
        reuse = hostile["virtual_memory_ownership.unsafe_early_reuse"]
        unauthorized = hostile["capability_mediated_ipc.unsafe_unauthorized_call"]
        token_reuse = hostile["capability_mediated_ipc.unsafe_token_reuse"]
        stale_reply = hostile["capability_mediated_ipc.unsafe_stale_reply"]
        leaky_teardown = hostile["capability_mediated_ipc.unsafe_leaky_teardown"]
        lost_cancel = hostile["bounded_scheduler.unsafe_lost_cancel_wake"]
        lost_timeout = hostile["bounded_scheduler.unsafe_lost_timeout_wake"]
        duplicate_wakeup = hostile["bounded_scheduler.unsafe_duplicate_wakeup"]
        no_inheritance = hostile["bounded_scheduler.unsafe_no_priority_inheritance"]
        priority_bypass = hostile["bounded_scheduler.unsafe_priority_bypass"]
        fairness_bypass = hostile["bounded_scheduler.unsafe_fairness_bypass"]
        scheduler_teardown = hostile["bounded_scheduler.unsafe_scheduler_teardown_leak"]
        self.assertEqual("Recoverable", boot["observed_invariant_violation"])
        self.assertEqual(["Init", "Stage", "StartTrial", "TrialFailure"], [item["action"] for item in boot["trace"]])
        self.assertEqual("NoLiveDescendantOfRevoked", capability["observed_invariant_violation"])
        self.assertEqual(["Init", "Derive", "Revoke"], [item["action"] for item in capability["trace"]])
        self.assertEqual("PageTableSafety", stale["observed_invariant_violation"])
        self.assertEqual(["Init", "Map", "BeginTransfer", "CompleteTransfer"], [item["action"] for item in stale["trace"]])
        self.assertEqual("TlbSafety", reuse["observed_invariant_violation"])
        self.assertEqual(["Init", "Map", "TlbFill", "BeginTransfer", "Unmap", "CompleteTransfer"], [item["action"] for item in reuse["trace"]])
        self.assertEqual("QueuedCallAuthorized", unauthorized["observed_invariant_violation"])
        self.assertEqual(["Init", "Enqueue"], [item["action"] for item in unauthorized["trace"]])
        self.assertEqual("LiveTokenConsistent", token_reuse["observed_invariant_violation"])
        self.assertEqual(["Init", "Enqueue", "Dispatch", "Reply"], [item["action"] for item in token_reuse["trace"]])
        self.assertEqual("AcceptedRepliesFresh", stale_reply["observed_invariant_violation"])
        self.assertEqual(["Init", "Enqueue", "Dispatch", "Cancel", "Reply"], [item["action"] for item in stale_reply["trace"]])
        self.assertEqual("ClosedEndpointQuiescent", leaky_teardown["observed_invariant_violation"])
        self.assertEqual(["Init", "Enqueue", "Teardown"], [item["action"] for item in leaky_teardown["trace"]])
        self.assertEqual("WakeDeliverySound", lost_cancel["observed_invariant_violation"])
        self.assertEqual(["Init", "Activate", "Preempt", "Dispatch", "BlockOnLock", "CancelWait"], [item["action"] for item in lost_cancel["trace"]])
        self.assertEqual("WakeDeliverySound", lost_timeout["observed_invariant_violation"])
        self.assertEqual(["Init", "Activate", "Preempt", "Dispatch", "BlockOnLock", "TimeoutWait"], [item["action"] for item in lost_timeout["trace"]])
        self.assertEqual("NoDuplicateRunnable", duplicate_wakeup["observed_invariant_violation"])
        self.assertEqual("PriorityInheritanceSound", no_inheritance["observed_invariant_violation"])
        self.assertEqual("DispatchPrioritySound", priority_bypass["observed_invariant_violation"])
        self.assertEqual("BypassBound", fairness_bypass["observed_invariant_violation"])
        self.assertEqual(["Init", "Activate", "Preempt", "Dispatch", "Preempt", "Dispatch", "Preempt", "Dispatch"], [item["action"] for item in fairness_bypass["trace"]])
        self.assertEqual("TerminalQuiescent", scheduler_teardown["observed_invariant_violation"])
        self.assertEqual(["Init", "Activate", "Teardown"], [item["action"] for item in scheduler_teardown["trace"]])

    def test_public_traces_contain_no_absolute_paths_or_timestamps(self) -> None:
        encoded = json.dumps(self.readiness["runs"], ensure_ascii=True)
        self.assertIsNone(native_models.ABSOLUTE_USER_PATH.search(encoded))
        self.assertNotIn("2026-07-16 07:", encoded)
        self.assertNotIn("tlc-metadata", encoded)

    def test_open_domains_and_trace_cross_checks_remain_explicit(self) -> None:
        coverage = self.readiness["domain_coverage"]
        self.assertEqual(1, coverage["open_count"])
        self.assertEqual({"poolefs_transaction_recovery"}, set(coverage["open_domains"]))
        self.assertEqual(0, self.readiness["summary"]["implementation_trace_cross_check_count"])
        self.assertFalse(self.readiness["claim_boundary"]["abi_freeze_authorized"])

    def test_negative_control_register_is_complete(self) -> None:
        controls = self.readiness["negative_controls"]
        self.assertEqual(list(native_models.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(25, len(controls))
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_stale_bindings_fail_closed(self) -> None:
        altered = copy.deepcopy(self.readiness)
        altered["bindings"]["lock"]["sha256"] = "0" * 64
        self.assertIn("stale lock binding", native_models.readiness_contract_errors(altered))
        altered = copy.deepcopy(self.readiness)
        altered["bindings"]["model_inputs"][0]["sha256"] = "0" * 64
        self.assertIn("stale model input bindings", native_models.readiness_contract_errors(altered))

    def test_trace_tampering_fails_closed(self) -> None:
        altered = copy.deepcopy(self.readiness)
        hostile = next(item for item in altered["runs"] if item["mode"] == "hostile")
        hostile["trace"][0]["action"] = "Forged"
        errors = native_models.readiness_contract_errors(altered)
        self.assertTrue(any("trace digest mismatch" in item for item in errors))
        hostile["trace_sha256"] = native_models.sha256_bytes(native_models.canonical_json_bytes(hostile["trace"]))
        errors = native_models.readiness_contract_errors(altered)
        self.assertTrue(any("trace action drift" in item for item in errors))

        altered = copy.deepcopy(self.readiness)
        run = altered["runs"][0]
        run["command_sha256"] = "0" * 64
        self.assertTrue(any("command digest mismatch" in item for item in native_models.readiness_contract_errors(altered)))

    def test_claim_overrides_fail_closed(self) -> None:
        for key in (
            "formal_proof_claimed",
            "fingerprint_collision_free_claimed",
            "liveness_checked",
            "implementation_trace_cross_checked",
            "abi_freeze_authorized",
            "pooleboot_executed",
            "poolekernel_executed",
            "production_promotion_allowed",
        ):
            with self.subTest(key=key):
                altered = copy.deepcopy(self.readiness)
                altered["claim_boundary"][key] = True
                self.assertTrue(native_models.readiness_contract_errors(altered))
        altered = copy.deepcopy(self.readiness)
        altered["claim_boundary"]["theorem_proved"] = True
        self.assertTrue(native_models.readiness_contract_errors(altered))

    def test_contract_mutations_fail_closed(self) -> None:
        altered = copy.deepcopy(self.contract)
        altered["models"] = None
        self.assertTrue(native_models.contract_errors(altered))
        altered = copy.deepcopy(self.contract)
        altered["engine"]["workers"] = 2
        self.assertTrue(native_models.contract_errors(altered))
        altered = copy.deepcopy(self.contract)
        altered["models"][0]["cases"][0]["expected"]["distinct_states"] += 1
        self.assertTrue(native_models.contract_errors(altered))
        altered = copy.deepcopy(self.contract)
        altered["engine"]["command_template"].insert(-1, "-simulate")
        self.assertTrue(native_models.contract_errors(altered))
        altered = copy.deepcopy(self.contract)
        altered["models"][0]["cases"][1]["expected"]["trace_sha256"] = "0" * 64
        self.assertTrue(native_models.contract_errors(altered))
        altered_lock = copy.deepcopy(self.lock)
        altered_lock["tlc"]["jar"]["sha256"] = "0" * 64
        self.assertTrue(native_models.lock_contract_errors(altered_lock))
        altered_lock = copy.deepcopy(self.lock)
        altered_lock["java"]["detached_signature_verified"] = True
        self.assertTrue(native_models.lock_contract_errors(altered_lock))

    def test_qualifier_reproduces_readiness_exactly_when_toolchain_is_present(self) -> None:
        java = native_models.DEFAULT_TOOLCHAIN_ROOT / "runtime" / "jdk-21.0.11+10-jre" / "bin" / "java.exe"
        if not java.is_file():
            self.skipTest("workspace-local native model toolchain is not provisioned")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "readiness.json"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "qualify_native_models.py"), "--out", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=120,
            )
            self.assertEqual(0, completed.returncode, completed.stdout)
            self.assertEqual(self.readiness_path.read_bytes(), output.read_bytes())


if __name__ == "__main__":
    unittest.main()
