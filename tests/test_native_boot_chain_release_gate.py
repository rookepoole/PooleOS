import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from tools import pooleos_release_gate as gate

ROOT = Path(__file__).resolve().parents[1]


class NativeBootChainReleaseGateTests(unittest.TestCase):
    def test_boot_chain_accepts_source_current_receipts(self) -> None:
        for profile in ("symbol", "policy", "kernel_load", "pooleboot", "kernel_revalidation", "kernel_transfer"):
            with self.subTest(profile=profile):
                check = getattr(gate, "check_native_" + profile + "_readiness")()
                self.assertTrue(check["ok"], check["detail"])

    def test_boot_chain_rejects_superseded_artifact_and_trust_identities(self) -> None:
        old_inner = "2DC54F8C02425C44DEB80A0F6285CAF4687A90537114902D39BB338C14BD7664"
        cases = (
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "inner_set_retained_set_sha256", old_inner),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_policy_sha256",
             "6D8C4B9F295FB032D33777E80F3BE7320AB1DAECD46EBBF4F873AFE5D101E7F9"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_state_sha256",
             "463B058E2CFB4FEAD916C5C69D4A8EDC447F16D31D50444896965D76827C478C"),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "inner_retained_set_sha256", old_inner),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "golden", "retained_set_sha256", old_inner),
        )
        for profile, filename, section, field, superseded in cases:
            with self.subTest(profile=profile, field=field):
                receipt = json.loads((ROOT / "runs" / filename).read_text(encoding="utf-8"))
                self.assertNotEqual(receipt[section][field], superseded)
                candidate = copy.deepcopy(receipt)
                candidate[section][field] = superseded
                with mock.patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                    check = getattr(gate, "check_native_" + profile + "_readiness")()
                self.assertFalse(check["ok"], check["detail"])


if __name__ == "__main__":
    unittest.main()
