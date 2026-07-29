import copy
import dataclasses
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_recovery as prec1  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate, qualify_native_recovery  # noqa: E402


class NativeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = prec1.read_json(ROOT / prec1.CONTRACT_RELATIVE)
        cls.golden = prec1.read_json(ROOT / prec1.GOLDEN_RELATIVE)
        cls.readiness = prec1.read_json(ROOT / prec1.READINESS_RELATIVE)

    def test_contract_golden_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, prec1.CONTRACT_SCHEMA_RELATIVE),
            (self.golden, prec1.GOLDEN_SCHEMA_RELATIVE),
            (self.readiness, prec1.READINESS_SCHEMA_RELATIVE),
        )
        for value, schema in cases:
            with self.subTest(schema=str(schema)):
                self.assertEqual([], validate_json(value, prec1.read_json(ROOT / schema)))

    def test_semantic_contracts_and_bindings_pass(self) -> None:
        self.assertEqual([], prec1.contract_errors(self.contract))
        self.assertEqual([], prec1.golden_errors(self.golden))
        self.assertEqual([], prec1.readiness_errors(self.readiness))

    def test_generator_reproduces_contract_vectors_and_rust_fixtures(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_native_recovery_vectors.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("PREC1_GENERATION PASS", completed.stdout)

    def test_all_golden_vectors_have_exact_policy_state_and_transition_semantics(self) -> None:
        for item in self.golden["vectors"]:
            with self.subTest(vector=item["id"]):
                policy_bytes = bytes.fromhex(item["policy_hex"])
                state_bytes = bytes.fromhex(item["state_hex"])
                policy = prec1.parse(policy_bytes)
                state = prec1.parse_state(state_bytes, policy)
                decision = prec1.select_boot(
                    policy,
                    state,
                    item["requested_mode"],
                    boot_nonce=item["boot_nonce"],
                )
                self.assertEqual(prec1.TOTAL_BYTES, len(policy_bytes))
                self.assertEqual(prec1.STATE_BYTES, len(state_bytes))
                self.assertEqual(item["policy_summary"], prec1.summary(policy))
                self.assertEqual(item["state_summary"], prec1.state_summary(state))
                self.assertEqual(item["decision_summary"], prec1.decision_summary(decision))
                self.assertEqual(item["next_state_hex"], prec1.encode_state(decision.state).hex().upper())

    def test_candidate_attempt_is_persisted_before_handoff(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        state = prec1.canonical_state(policy)
        decision = prec1.select_boot(policy, state, prec1.MODE_NORMAL, boot_nonce=100)
        self.assertTrue(decision.trial)
        self.assertTrue(decision.persistence_required)
        self.assertEqual(1, decision.slot)
        self.assertEqual(state.attempts_a - 1, decision.state.attempts_a)
        self.assertTrue(decision.state.flags & prec1.STATE_INFLIGHT)

    def test_authenticated_matching_success_promotes_candidate(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        selected = prec1.select_boot(policy, prec1.canonical_state(policy), 1, boot_nonce=101)
        receipt = prec1.SuccessReceipt(
            True,
            selected.state.inflight_generation,
            selected.slot,
            selected.mode,
            selected.state.boot_nonce,
        )
        promoted = prec1.report_boot_success(policy, selected.state, receipt)
        self.assertEqual(1, promoted.active_slot)
        self.assertEqual(0, promoted.pending_slot)
        self.assertEqual(0b11, promoted.known_good_mask)
        self.assertFalse(promoted.flags & prec1.STATE_INFLIGHT)

    def test_success_receipt_requires_authentication_and_exact_binding(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        selected = prec1.select_boot(policy, prec1.canonical_state(policy), 1, boot_nonce=102)
        receipt = prec1.SuccessReceipt(
            True,
            selected.state.inflight_generation,
            selected.slot,
            selected.mode,
            selected.state.boot_nonce,
        )
        with self.assertRaisesRegex(prec1.RecoveryError, "prec_receipt_auth"):
            prec1.report_boot_success(policy, selected.state, dataclasses.replace(receipt, authenticated=False))
        for changed in (
            dataclasses.replace(receipt, generation=receipt.generation + 1),
            dataclasses.replace(receipt, slot=2),
            dataclasses.replace(receipt, mode=prec1.MODE_SAFE),
            dataclasses.replace(receipt, boot_nonce=receipt.boot_nonce + 1),
        ):
            with self.assertRaisesRegex(prec1.RecoveryError, "prec_receipt_binding"):
                prec1.report_boot_success(policy, selected.state, changed)

    def test_exhausted_trial_falls_back_to_known_good(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        state = dataclasses.replace(prec1.canonical_state(policy), attempts_a=0)
        decision = prec1.select_boot(policy, state, prec1.MODE_NORMAL, boot_nonce=103)
        self.assertEqual(prec1.MODE_PREVIOUS, decision.mode)
        self.assertEqual(2, decision.slot)
        self.assertEqual(0, decision.state.pending_slot)
        self.assertTrue(decision.state.unbootable_mask & 0b01)

    def test_safe_request_overrides_normal_and_cannot_loop(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        state = dataclasses.replace(prec1.canonical_state(policy), flags=prec1.STATE_SAFE_REQUESTED)
        first = prec1.select_boot(policy, state, prec1.MODE_NORMAL, boot_nonce=104)
        self.assertEqual(prec1.MODE_SAFE, first.mode)
        repeated = dataclasses.replace(
            state,
            safe_attempted_mask=state.known_good_mask,
        )
        second = prec1.select_boot(policy, repeated, prec1.MODE_NORMAL, boot_nonce=105)
        self.assertEqual(prec1.MODE_RECOVERY, second.mode)
        self.assertEqual(0, second.slot)

    def test_firmware_setup_requires_physical_presence(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        state = prec1.canonical_state(policy)
        with self.assertRaisesRegex(prec1.RecoveryError, "prec_transition_physical_presence"):
            prec1.select_boot(policy, state, prec1.MODE_FIRMWARE, boot_nonce=106)
        decision = prec1.select_boot(
            policy,
            state,
            prec1.MODE_FIRMWARE,
            physical_presence=True,
            boot_nonce=106,
        )
        self.assertEqual(prec1.MODE_FIRMWARE, decision.mode)
        self.assertEqual(0, decision.slot)

    def test_state_write_failure_cannot_authorize_normal_handoff(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        state = prec1.canonical_state(policy)
        decision = prec1.select_boot(policy, state, state_writable=False)
        self.assertEqual(prec1.MODE_RECOVERY, decision.mode)
        self.assertFalse(decision.persistence_required)
        self.assertEqual(prec1.FAIL_STATE_INVALID, decision.reason)
        self.assertEqual(state, decision.state)

    def test_checksum_and_authority_rows_do_not_overclaim(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        self.assertEqual(7, len(policy.authority_rules))
        self.assertFalse(self.contract["authority_policy"]["declarative_only"] is False)
        self.assertIn("not_authentication", self.contract["encoding"]["state_checksum"])
        self.assertFalse(self.readiness["claims"]["state_checksum_is_authentication"])
        self.assertFalse(self.readiness["claims"]["recovery_authority_granted"])

    def test_unsigned_development_activation_is_denied(self) -> None:
        policy = prec1.parse(prec1.canonical_bundle())
        with self.assertRaisesRegex(prec1.RecoveryError, "prec_activation_outer_signature"):
            prec1.authorize_activation(policy, prec1.development_activation_context())
        prec1.authorize_activation(policy, prec1.synthetic_qualified_activation_context(policy))
        for mode in prec1.ACTIVATION_MODES:
            with self.subTest(mode=mode):
                with self.assertRaises(prec1.RecoveryError):
                    prec1.authorize_activation(policy, prec1.activation_context(mode, policy))

    def test_control_registry_and_receipt_are_complete(self) -> None:
        controls = qualify_native_recovery._controls()
        self.assertEqual(144, len(controls))
        self.assertEqual(144, len({item.control_id for item in controls}))
        self.assertEqual(
            [item.control_id for item in controls],
            [item["id"] for item in self.readiness["negative_controls"]],
        )
        self.assertTrue(all(item["status"] == "pass" for item in self.readiness["negative_controls"]))

    def test_readiness_records_complete_cross_language_campaign(self) -> None:
        summary = self.readiness["summary"]
        self.assertEqual(3, summary["rust_host_tests_passed"])
        self.assertEqual(2, summary["no_std_target_builds_passed"])
        self.assertEqual(3, summary["golden_vectors_matched"])
        self.assertEqual(144, summary["negative_controls_passed"])
        self.assertEqual(16_384, summary["parser_differential_cases"])
        self.assertEqual(8_192, summary["transition_differential_cases"])
        self.assertEqual(0, summary["differential_mismatches"])

    def test_release_gate_carries_bounded_recovery_readiness(self) -> None:
        check = pooleos_release_gate.check_native_recovery_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("contract=PREC1", check["detail"])

    def test_readiness_stales_when_an_implementation_binding_changes(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertIn("readiness input bindings are stale", prec1.readiness_errors(changed))

    def test_public_receipt_contains_no_host_path_or_private_corpus(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertNotIn("C:\\Users", encoded)
        self.assertFalse(self.readiness["differential_fuzz"]["corpus_published"])
        self.assertFalse(self.readiness["transition_qualification"]["corpus_published"])
        self.assertFalse(self.readiness["validator_qualification"]["host_probe_artifact_identity_recorded"])


if __name__ == "__main__":
    unittest.main()
