from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import n0_owner_decision_packet as owner_packet  # noqa: E402


class N0OwnerDecisionPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.packet_path = ROOT / owner_packet.PACKET_RELATIVE
        cls.markdown_path = ROOT / owner_packet.PACKET_DOCUMENT_RELATIVE
        cls.packet = json.loads(cls.packet_path.read_text(encoding="utf-8"))

    def test_packet_is_exact_valid_regeneration(self) -> None:
        regenerated = owner_packet.build_packet(ROOT)
        self.assertEqual(self.packet_path.read_bytes(), owner_packet.canonical_json_bytes(regenerated))
        self.assertEqual(owner_packet.packet_rejection_reasons(self.packet, ROOT), [])

    def test_markdown_is_exact_valid_regeneration(self) -> None:
        rendered = owner_packet.render_markdown(self.packet)
        self.assertEqual(self.markdown_path.read_text(encoding="utf-8"), rendered)

    def test_generator_reproduces_both_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            json_out = Path(temp) / "packet.json"
            markdown_out = Path(temp) / "packet.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "generate_n0_owner_decision_packet.py"),
                    "--out-json",
                    str(json_out),
                    "--out-markdown",
                    str(markdown_out),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(json_out.read_bytes(), self.packet_path.read_bytes())
            self.assertEqual(markdown_out.read_bytes(), self.markdown_path.read_bytes())

    def test_every_objective_target_is_present_exactly_once(self) -> None:
        source = json.loads((ROOT / "specs" / "native-v1-objectives.json").read_text(encoding="utf-8"))
        packet_targets = self.packet["decisions"]["objectives"]["targets"]
        self.assertEqual([item["id"] for item in packet_targets], [item["id"] for item in source["targets"]])
        self.assertEqual(len({item["id"] for item in packet_targets}), 38)
        self.assertTrue(all(item["evidence_status"] == "not_measured" for item in packet_targets))
        self.assertFalse(self.packet["decisions"]["objectives"]["measurement_evidence_accepted"])

    def test_all_owner_selections_remain_unselected(self) -> None:
        decisions = self.packet["decisions"]
        self.assertEqual(decisions["adr_0003"]["selection"], owner_packet.UNSELECTED)
        self.assertEqual(decisions["adr_0004"]["selection"], owner_packet.UNSELECTED)
        self.assertEqual(decisions["objectives"]["selection"], owner_packet.UNSELECTED)
        self.assertEqual(decisions["custody"]["selection"], owner_packet.UNSELECTED)
        self.assertEqual(decisions["custody"]["hardware_key_availability"], owner_packet.UNSELECTED)
        self.assertEqual(decisions["custody"]["provisional_software_key_risk_acceptance"], owner_packet.UNSELECTED)
        self.assertEqual(decisions["public_key_publication"]["selection"], owner_packet.UNSELECTED)
        self.assertTrue(all(field["selection"] == owner_packet.UNSELECTED for field in self.packet["owner_response_template"]["fields"]))

    def test_packet_preserves_separate_approval_boundaries(self) -> None:
        self.assertFalse(self.packet["owner_acceptance_recorded"])
        self.assertFalse(self.packet["signature_authorized"])
        self.assertFalse(self.packet["publication_authorized"])
        self.assertFalse(self.packet["production_promotion_allowed"])
        separate = self.packet["execution_boundary"]["separate_explicit_approval_required"]
        for required in (
            "merge_to_main",
            "generate_or_use_private_keys",
            "sign_or_publish_tags_or_releases",
            "run_privileged_hardware_probes",
            "write_physical_media_or_disks",
        ):
            self.assertIn(required, separate)

    def test_frozen_negative_controls_all_pass(self) -> None:
        validation = self.packet["validation"]
        self.assertEqual(validation["negative_control_count"], len(owner_packet.NEGATIVE_CONTROL_IDS))
        self.assertEqual(validation["negative_control_pass_count"], len(owner_packet.NEGATIVE_CONTROL_IDS))
        self.assertEqual([item["id"] for item in validation["negative_controls"]], list(owner_packet.NEGATIVE_CONTROL_IDS))
        self.assertTrue(all(item["status"] == "pass" for item in validation["negative_controls"]))

    def test_missing_target_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.packet)
        mutant["decisions"]["objectives"]["targets"].pop()
        self.assertTrue(owner_packet.packet_rejection_reasons(mutant, ROOT))

    def test_inferred_owner_acceptance_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.packet)
        mutant["owner_acceptance_recorded"] = True
        self.assertTrue(owner_packet.packet_rejection_reasons(mutant, ROOT))

    def test_private_material_field_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.packet)
        mutant["decisions"]["custody"]["private_key_material"] = "FORBIDDEN"
        self.assertTrue(owner_packet.packet_rejection_reasons(mutant, ROOT))

    def test_markdown_contains_every_decision_and_target(self) -> None:
        markdown = self.markdown_path.read_text(encoding="utf-8")
        for marker in (
            "ADR-0003",
            "ADR-0004",
            "hardware_fido2_ed25519_sk",
            "passphrase_ed25519_provisional",
            "POOLEOS-N0-OWNER-RESPONSE-V1",
            "does not generate a key",
        ):
            self.assertIn(marker, markdown)
        for target in self.packet["decisions"]["objectives"]["targets"]:
            self.assertEqual(markdown.count(f"`{target['id']}`"), 1)


if __name__ == "__main__":
    unittest.main()
