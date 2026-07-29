import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_kernel_errata_policy as pkerr1  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeKernelErrataPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = pkerr1.read_json(ROOT / pkerr1.CONTRACT_RELATIVE)
        cls.readiness = pkerr1.read_json(ROOT / pkerr1.READINESS_RELATIVE)

    def test_contract_and_readiness_are_current(self) -> None:
        self.assertEqual([], pkerr1.contract_errors(self.contract))
        self.assertEqual([], pkerr1.readiness_errors(self.readiness))

    def test_current_target_denies_for_exact_frozen_reasons(self) -> None:
        decision = pkerr1.evaluate(pkerr1.current_observation())
        self.assertEqual(pkerr1.CURRENT_EXPECTED_FAILURES, decision["failure_mask"])
        self.assertEqual(
            [
                "board_lineage",
                "bios_floor",
                "agesa_floor",
                "microcode_evidence",
                "microcode_floor_source",
                "errata_guide",
            ],
            decision["failure_codes"],
        )
        self.assertFalse(decision["policy_satisfied"])

    def test_direct_product_firmware_floors_are_not_lowered(self) -> None:
        policy = self.contract["firmware_policy"]
        self.assertEqual("1.2.0.3c", policy["amd_sb_7033_minimum"].split()[-1])
        self.assertEqual("1.2.0.3i", policy["combined_comparison_floor"])
        self.assertEqual(["F39", "FA7"], [item["minimum_stable_bios"] for item in policy["lineages"]])
        self.assertEqual("deny", policy["unknown_board_revision_policy"])

    def test_wrong_revision_guide_and_invented_floor_are_forbidden(self) -> None:
        errata = self.contract["errata_policy"]
        self.assertEqual("AMD Family 1Ah Models 40h-4Fh", errata["required_target_range"])
        self.assertEqual("AMD Family 1Ah Models 00h-0Fh", errata["document_58251_range"])
        self.assertFalse(errata["document_58251_target_applicable"])
        self.assertIsNone(self.contract["microcode_policy"]["amd_published_client_numeric_floor"])
        self.assertFalse(self.contract["microcode_policy"]["observed_revision_is_security_floor"])

    def test_registry_observation_is_bounded_and_homogeneous(self) -> None:
        observation = self.readiness["windows_registry_observation"]
        self.assertEqual("pass_read_only_unprivileged_os_report", observation["status"])
        self.assertEqual(16, observation["record_count"])
        self.assertEqual(1, observation["unique_revision_count"])
        self.assertEqual("0x0B404023", observation["normalized_revision"])
        self.assertEqual(0, observation["msr_reads"])
        self.assertEqual(0, observation["writes"])

    def test_mandatory_features_and_rdseed_fail_closed(self) -> None:
        evidence = pkerr1.synthetic_qualification_fixture()
        evidence["feature_mask"] &= ~pkerr1.FEATURE_SMAP
        self.assertEqual(pkerr1.FAILURE_FEATURES, pkerr1.evaluate(evidence)["failure_mask"])
        evidence = pkerr1.synthetic_qualification_fixture()
        evidence["rdseed_policy"] = pkerr1.RDSEED_UNKNOWN
        self.assertEqual(pkerr1.FAILURE_RDSEED_POLICY, pkerr1.evaluate(evidence)["failure_mask"])

    def test_contract_mutations_reject(self) -> None:
        candidates = []
        value = copy.deepcopy(self.contract)
        value["source_register"][4]["target_applicable"] = True
        candidates.append(value)
        value = copy.deepcopy(self.contract)
        value["firmware_policy"]["combined_comparison_floor"] = "1.2.0.2b"
        candidates.append(value)
        value = copy.deepcopy(self.contract)
        value["production_ready"] = True
        candidates.append(value)
        for candidate in candidates:
            with self.subTest(candidate=candidate["firmware_policy"]["combined_comparison_floor"]):
                self.assertTrue(pkerr1.contract_errors(candidate))

    def test_cross_language_and_hostile_evidence_passes_without_authority(self) -> None:
        vectors = self.readiness["cross_language_vectors"]
        self.assertEqual(128, vectors["case_count"])
        self.assertEqual(0, vectors["mismatch_count"])
        self.assertEqual(10, vectors["failure_bit_coverage"])
        controls = self.readiness["negative_controls"]
        self.assertEqual(list(pkerr1.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertTrue(all(item["status"] == "pass" for item in controls))
        summary = self.readiness["summary"]
        self.assertEqual(0, summary["privileged_read_count"])
        self.assertEqual(0, summary["cpu_or_firmware_write_count"])
        self.assertEqual(0, summary["authority_grant_count"])
        self.assertTrue(pooleos_release_gate.check_native_kernel_errata_policy_readiness()["ok"])


if __name__ == "__main__":
    unittest.main()
