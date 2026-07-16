import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import n0_owner_decision_packet, n0_owner_response  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import generate_n0_owner_response_receipt  # noqa: E402


class N0OwnerResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.response_path = ROOT / n0_owner_response.RESPONSE_RELATIVE
        cls.receipt_path = ROOT / n0_owner_response.RECEIPT_RELATIVE
        cls.packet_path = ROOT / n0_owner_decision_packet.PACKET_RELATIVE
        cls.response = json.loads(cls.response_path.read_text(encoding="utf-8"))
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding="utf-8"))
        cls.packet = json.loads(cls.packet_path.read_text(encoding="utf-8"))

    def test_response_and_receipt_match_schemas(self) -> None:
        response_schema = json.loads((ROOT / n0_owner_response.RESPONSE_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
        receipt_schema = json.loads((ROOT / n0_owner_response.RECEIPT_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(validate_json(self.response, response_schema), [])
        self.assertEqual(validate_json(self.receipt, receipt_schema), [])
        self.assertEqual(n0_owner_response.response_rejection_reasons(self.response, ROOT), [])
        self.assertEqual(n0_owner_response.receipt_rejection_reasons(self.receipt, ROOT), [])

    def test_response_records_every_exact_selection(self) -> None:
        self.assertEqual(self.response["selections"], n0_owner_response.EXPECTED_SELECTIONS)
        self.assertEqual(self.response["amendment_details"], "none")
        self.assertTrue(self.response["confirmations"]["definition_acceptance_is_not_measurement_acceptance"])
        self.assertTrue(
            self.response["confirmations"]["no_key_generation_signing_merging_tagging_or_publication_authorized"]
        )

    def test_response_binds_the_frozen_unselected_packet(self) -> None:
        binding = self.response["decision_packet"]
        raw = self.packet_path.read_bytes()
        self.assertEqual(n0_owner_response.sha256_bytes(raw), binding["sha256"])
        self.assertEqual(len(raw), binding["byte_count"])
        self.assertEqual(self.packet["source_set"]["sha256"], binding["source_set_sha256"])
        self.assertEqual(self.packet["decisions"]["objectives"]["target_set_sha256"], binding["target_set_sha256"])
        self.assertTrue(
            all(
                field["selection"] == n0_owner_decision_packet.UNSELECTED
                for field in self.packet["owner_response_template"]["fields"]
            )
        )

    def test_packet_builder_returns_the_frozen_historical_bytes(self) -> None:
        rebuilt = n0_owner_decision_packet.build_packet(ROOT)
        self.assertEqual(n0_owner_decision_packet.canonical_json_bytes(rebuilt), self.packet_path.read_bytes())
        self.assertEqual(n0_owner_decision_packet.packet_rejection_reasons(rebuilt, ROOT), [])

    def test_receipt_generator_reproduces_exact_bytes(self) -> None:
        self.assertEqual(
            self.receipt_path.read_bytes(),
            n0_owner_response.canonical_json_bytes(n0_owner_response.build_receipt(ROOT)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "receipt.json"
            markdown_out = Path(tmp) / "receipt.md"
            code = generate_n0_owner_response_receipt.main(
                ["--out-json", str(json_out), "--out-markdown", str(markdown_out)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(json_out.read_bytes(), self.receipt_path.read_bytes())
            self.assertEqual(markdown_out.read_bytes(), (ROOT / n0_owner_response.RECEIPT_DOCUMENT_RELATIVE).read_bytes())

    def test_live_source_dispositions_are_recorded_without_measurements(self) -> None:
        state = self.receipt["effective_source_state"]
        self.assertEqual(state["adr_0003"]["source_status"], "accepted-owner-directed")
        self.assertEqual(state["adr_0004"]["source_status"], "accepted-owner-directed")
        self.assertTrue(state["objectives"]["profile_accepted"])
        self.assertTrue(state["objectives"]["target_values_accepted"])
        self.assertFalse(state["objectives"]["cryptographic_signature_present"])
        self.assertEqual(state["objectives"]["measured_target_count"], 0)

    def test_hardware_profile_is_selected_but_unavailable(self) -> None:
        custody = self.receipt["accepted_decisions"]["custody"]
        trust = self.receipt["trust_state"]
        self.assertEqual(custody["selected_profile"], "hardware_fido2_ed25519_sk")
        self.assertEqual(custody["hardware_key_availability"], "do_not_have")
        self.assertEqual(custody["provisional_software_key_risk"], "not_applicable")
        self.assertFalse(trust["hardware_key_available"])
        self.assertTrue(trust["hardware_acquisition_required"])
        self.assertEqual(trust["trusted_signer_count"], 0)

    def test_every_gated_execution_authority_remains_false(self) -> None:
        self.assertTrue(all(value is False for value in self.response["execution_authorization"].values()))
        self.assertTrue(all(value is False for value in self.receipt["execution_boundary"].values()))
        self.assertFalse(self.receipt["production_promotion_allowed"])
        self.assertFalse(self.receipt["production_ready"])

    def test_all_sixteen_negative_controls_pass(self) -> None:
        validation = self.receipt["validation"]
        self.assertEqual(validation["negative_control_count"], len(n0_owner_response.NEGATIVE_CONTROL_IDS))
        self.assertEqual(validation["negative_control_pass_count"], len(n0_owner_response.NEGATIVE_CONTROL_IDS))
        self.assertEqual(
            [item["id"] for item in validation["negative_controls"]],
            list(n0_owner_response.NEGATIVE_CONTROL_IDS),
        )
        self.assertTrue(all(item["status"] == "pass" for item in validation["negative_controls"]))

    def test_stale_packet_binding_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.response)
        mutant["decision_packet"]["sha256"] = "0" * 64
        self.assertTrue(n0_owner_response.response_rejection_reasons(mutant, ROOT))

    def test_placeholder_and_software_risk_mismatch_fail_closed(self) -> None:
        placeholder = copy.deepcopy(self.response)
        placeholder["selections"]["adr_0003"] = "UNSELECTED"
        self.assertTrue(n0_owner_response.response_rejection_reasons(placeholder, ROOT))
        mismatch = copy.deepcopy(self.response)
        mismatch["selections"]["provisional_software_key_risk_accepted"] = "yes"
        self.assertTrue(n0_owner_response.response_rejection_reasons(mismatch, ROOT))

    def test_private_material_and_authorization_mutations_fail_closed(self) -> None:
        private = copy.deepcopy(self.response)
        private["private_key_material"] = "FORBIDDEN"
        self.assertTrue(n0_owner_response.response_rejection_reasons(private, ROOT))
        for field in self.response["execution_authorization"]:
            mutant = copy.deepcopy(self.response)
            mutant["execution_authorization"][field] = True
            self.assertTrue(n0_owner_response.response_rejection_reasons(mutant, ROOT), field)


if __name__ == "__main__":
    unittest.main()
