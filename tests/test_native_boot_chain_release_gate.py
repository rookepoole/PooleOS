import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import pooleos_release_gate as gate

ROOT = Path(__file__).resolve().parents[1]


class NativeBootChainReleaseGateTests(unittest.TestCase):
    def test_pooleboot_gate_rejects_forged_host_test_counts(self) -> None:
        self.assertTrue(gate.check_native_pooleboot_readiness()["ok"])
        receipt = json.loads((ROOT / "runs/native_pooleboot_readiness.json").read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            for field in ("host_contract_test_count", "host_contract_test_pass_count"):
                self.assertEqual(receipt["build"][field], 8)
                for value in (0, 7, 9, True, "8", None):
                    with self.subTest(field=field, value=value):
                        candidate = copy.deepcopy(receipt)
                        candidate["build"][field] = value
                        path.write_text(json.dumps(candidate), encoding="utf-8")
                        check = gate.check_native_pooleboot_readiness(path)
                        self.assertFalse(check["ok"], check["detail"])

    def test_exact_input_schema_counts_match_declared_source_sets(self) -> None:
        from runtime import native_boot_trust, native_kernel_load, native_pooleboot

        for module, section, inputs in (
            (native_boot_trust, "inputs", native_boot_trust.IMPLEMENTATION_INPUTS),
            (native_kernel_load, "bindings", native_kernel_load.IMPLEMENTATION_INPUTS),
            (native_pooleboot, "bindings", native_pooleboot.PROOF_IMPLEMENTATION_INPUTS),
        ):
            with self.subTest(module=module.__name__):
                schema = json.loads((ROOT / module.READINESS_SCHEMA_RELATIVE).read_bytes())
                declaration = schema["properties"][section]["properties"]["implementation_inputs"]
                self.assertEqual(declaration["minItems"], len(inputs))
                self.assertEqual(declaration["maxItems"], len(inputs))
                self.assertEqual(len(inputs), len(set(inputs)))
                if module is not native_kernel_load:
                    self.assertIn("host_toolchain", schema["properties"]["build"]["required"])
        contract = json.loads((ROOT / native_boot_trust.CONTRACT_SCHEMA_RELATIVE).read_bytes())
        self.assertEqual(contract["properties"]["implementation_bindings"]["minItems"], len(native_boot_trust.IMPLEMENTATION_INPUTS))
        self.assertEqual(contract["properties"]["implementation_bindings"]["maxItems"], len(native_boot_trust.IMPLEMENTATION_INPUTS))

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
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "inner_set_retained_set_sha256",
             "E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_policy_sha256",
             "99F5A46405B7E9357273AA84DEE23D5CC4B364585BDD8864D1A5DA6B0EB94376"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_state_sha256",
             "D25686B146654E89130263B8CF17567842DF929C5CB7C3006E85D55F6546ADF6"),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "inner_retained_set_sha256",
             "E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A"),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "golden", "retained_set_sha256",
             "E4B88EAF9B322531292D03EBA9FDCFA6ECABF6EEF7A5210C29D130C8AE321D3A"),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "rust_host_tests_passed", 328),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "rust_host_tests_total", 328),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "build", "host_test_count", 243),
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
