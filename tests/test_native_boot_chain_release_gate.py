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

    def test_independent_boot_gates_reject_previous_image_pins(self) -> None:
        previous_inner = "A50F908DB5C6C4119FDECD0D267E4D06BEE3626F9AE209B94B5A99DC3453F5EE"
        cases = (
            ("pooleboot", "native_pooleboot_readiness.json", gate.native_pooleboot,
             "readiness_contract_errors", "summary", "inner_set_retained_set_sha256", previous_inner),
            ("pooleboot", "native_pooleboot_readiness.json", gate.native_pooleboot,
             "readiness_contract_errors", "summary", "trust_policy_sha256",
             "B8B49BBD847C28832458B9B375067191AA204620411D9ADBDAD653F757EFB7AD"),
            ("pooleboot", "native_pooleboot_readiness.json", gate.native_pooleboot,
             "readiness_contract_errors", "summary", "trust_state_sha256",
             "6D5A23B7DAD78CF9659AD4F839BCA96CF0D6A5E74FEFC4C364542BF98E2D4B30"),
            ("kernel_load", "native_kernel_load_readiness.json", gate.native_kernel_load,
             "readiness_errors", "summary", "inner_retained_set_sha256", previous_inner),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", gate.native_kernel_revalidation,
             "readiness_errors", "golden", "retained_set_sha256", previous_inner),
        )
        for profile, filename, module, validator, section, field, previous in cases:
            receipt = json.loads((ROOT / "runs" / filename).read_bytes())
            check = getattr(gate, "check_native_" + profile + "_readiness")
            self.assertTrue(check()["ok"])
            self.assertNotEqual(receipt[section][field], previous)
            with mock.patch.object(module, validator, return_value=[]):
                with mock.patch.object(gate, "_load_schema_artifact", return_value=(receipt, [])):
                    self.assertTrue(check()["ok"])
                latest_previous = {
                    "inner_set_retained_set_sha256": "C48B7C41E73F79F0326B9E0146BF9DC001B902E5A95F5560400FE854530C9B58",
                    "inner_retained_set_sha256": "C48B7C41E73F79F0326B9E0146BF9DC001B902E5A95F5560400FE854530C9B58",
                    "retained_set_sha256": "C48B7C41E73F79F0326B9E0146BF9DC001B902E5A95F5560400FE854530C9B58",
                    "trust_policy_sha256": "DF9BD076267061F731263B86BDE62EBE161B8666605EDC3AA32606870EEE2049",
                    "trust_state_sha256": "073CEB317F1B6314274452846AC1959F988EFE9537A72456AEFB493F1DEB69CE",
                }[field]
                cycle210 = {
                    "inner_set_retained_set_sha256": "163EDAC3648C52267DAD983A6283D0860668B04B2E9B077A40F1855046A81DB1",
                    "inner_retained_set_sha256": "163EDAC3648C52267DAD983A6283D0860668B04B2E9B077A40F1855046A81DB1",
                    "retained_set_sha256": "163EDAC3648C52267DAD983A6283D0860668B04B2E9B077A40F1855046A81DB1",
                    "trust_policy_sha256": "957F07706B7B7CA495B9745CB50721B0698AAE79EBFE87A4BDB8B10F6892CEDC",
                    "trust_state_sha256": "CC015F3A79444B1BB91B1F7BEB985BEC9024759CAC2A688BA62339CCD48CAEF2",
                }[field]
                for value in (previous, latest_previous, cycle210, "0" * 64, None, False):
                    with self.subTest(profile=profile, field=field, value=value):
                        candidate = copy.deepcopy(receipt)
                        candidate[section][field] = value
                        with mock.patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                            result = check()
                        self.assertFalse(result["ok"], result["detail"])

    def test_boot_chain_rejects_superseded_artifact_and_trust_identities(self) -> None:
        old_inner = "2DC54F8C02425C44DEB80A0F6285CAF4687A90537114902D39BB338C14BD7664"
        cases = (
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "inner_set_retained_set_sha256",
             "FE35AE51B905BDFE7CB59F32CB2AF69A56910DA24DA83A74A9D92BB1BE5C7F0B"),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "inner_retained_set_sha256",
             "FE35AE51B905BDFE7CB59F32CB2AF69A56910DA24DA83A74A9D92BB1BE5C7F0B"),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "golden", "retained_set_sha256",
             "FE35AE51B905BDFE7CB59F32CB2AF69A56910DA24DA83A74A9D92BB1BE5C7F0B"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_policy_sha256",
             "7FD68927AECC739F8459ED6C6B2AB154318B357929F478A2D5B4B6D8C306C6B3"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_state_sha256",
             "5F8AE1BE86EE3DC024C332D5CA3BA5D5B8ED09B60BAB17855A410A16A64634AD"),
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
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "inner_set_retained_set_sha256",
             "A3078488088B2BF11B8D88F48862FA8D80957D610EB1F3FF4411AD5E4729FEAF"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_policy_sha256",
             "DDECB7E8BE1EEA8B491FDA3AA04AB56F81510BFBA69E1C0F30A93DC17C012803"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_state_sha256",
             "C3C4C6412480A4C715C91F059A35EFBAA5E9D4A003916D8B8580C9C04A6B59BC"),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "inner_retained_set_sha256",
             "A3078488088B2BF11B8D88F48862FA8D80957D610EB1F3FF4411AD5E4729FEAF"),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "golden", "retained_set_sha256",
             "A3078488088B2BF11B8D88F48862FA8D80957D610EB1F3FF4411AD5E4729FEAF"),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "rust_host_tests_passed", 330),
            ("kernel_load", "native_kernel_load_readiness.json", "summary", "rust_host_tests_total", 330),
            ("kernel_revalidation", "native-kernel-revalidation-readiness.json", "build", "host_test_count", 245),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_policy_sha256",
             "5DB6ACF8D65D1483E3F313526A2E1D4DBB37E942F004D8CDE863C7FA2FAAA41C"),
            ("pooleboot", "native_pooleboot_readiness.json", "summary", "trust_state_sha256",
             "3A31DF48162FA95E125A5F30C5214B71C5D38AFF5550A8FD6DD5308EF14A7777"),
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
