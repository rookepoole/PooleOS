import copy
import dataclasses
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_initial_system as pinit1  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_release_gate, qualify_native_initial_system  # noqa: E402


class NativeInitialSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = pinit1.read_json(ROOT / pinit1.CONTRACT_RELATIVE)
        cls.golden = pinit1.read_json(ROOT / pinit1.GOLDEN_RELATIVE)
        cls.readiness = pinit1.read_json(ROOT / pinit1.READINESS_RELATIVE)

    def test_contract_golden_and_readiness_match_schemas(self) -> None:
        cases = (
            (self.contract, pinit1.CONTRACT_SCHEMA_RELATIVE),
            (self.golden, pinit1.GOLDEN_SCHEMA_RELATIVE),
            (self.readiness, pinit1.READINESS_SCHEMA_RELATIVE),
        )
        for value, relative in cases:
            with self.subTest(schema=str(relative)):
                self.assertEqual([], validate_json(value, pinit1.read_json(ROOT / relative)))

    def test_semantic_contracts_and_bindings_pass(self) -> None:
        self.assertEqual([], pinit1.contract_errors(self.contract))
        self.assertEqual([], pinit1.golden_errors(self.golden))
        self.assertEqual([], pinit1.readiness_errors(self.readiness))

    def test_generator_reproduces_contract_and_vectors(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_native_initial_system_vectors.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("PINIT1_GENERATION PASS", completed.stdout)

    def test_all_golden_vectors_have_exact_semantics(self) -> None:
        for item in self.golden["vectors"]:
            with self.subTest(vector=item["id"]):
                data = bytes.fromhex(item["hex"])
                self.assertEqual(item["byte_count"], len(data))
                self.assertEqual(item["sha256"], pinit1.sha256_bytes(data))
                self.assertEqual(item["summary"], pinit1.summary(pinit1.parse(data)))

    def test_service_cannot_target_data_component(self) -> None:
        data = bytearray(pinit1.minimal_bundle())
        component = pinit1.HEADER_BYTES
        struct.pack_into("<H", data, component + 4, pinit1.COMPONENT_DATA)
        struct.pack_into(
            "<H",
            data,
            component + 6,
            pinit1.COMPONENT_REQUIRED | pinit1.COMPONENT_READ_ONLY,
        )
        data[component + 16 : component + 24] = pinit1.PINITD1
        struct.pack_into("<I", data, component + 32, 0)
        data[120:152] = __import__("hashlib").sha256(data[pinit1.HEADER_BYTES :]).digest()
        self.assertEqual("ERR:pinit_service_record", pinit1.parse_result(bytes(data)))

    def test_names_resources_and_capabilities_are_declarations_only(self) -> None:
        bundle = pinit1.parse(pinit1.canonical_bundle())
        self.assertEqual((1, 2, 3), bundle.start_order)
        self.assertEqual(4, len(bundle.resources))
        self.assertEqual(11, len(bundle.capabilities))
        self.assertFalse(self.contract["capability_policy"]["declaration_ids_are_kernel_handles"])
        self.assertFalse(self.contract["component_policy"]["physical_or_virtual_addresses_allowed"])

    def test_activation_is_separate_and_unsigned_development_fails(self) -> None:
        bundle = pinit1.parse(pinit1.canonical_bundle())
        with self.assertRaisesRegex(pinit1.InitialSystemError, "pinit_activation_outer_signature_verified"):
            pinit1.authorize_activation(bundle, pinit1.development_activation_context())
        pinit1.authorize_activation(bundle, pinit1.synthetic_qualified_activation_context(bundle))
        self.assertFalse(self.readiness["activation_qualification"]["synthetic_all_true_context_is_trust_evidence"])
        self.assertFalse(self.readiness["activation_qualification"]["current_unsigned_development_activation_allowed"])

    def test_every_activation_precondition_has_a_rejecting_control(self) -> None:
        bundle = pinit1.parse(pinit1.canonical_bundle())
        for mode in pinit1.ACTIVATION_MODES:
            with self.subTest(mode=mode):
                with self.assertRaises(pinit1.InitialSystemError):
                    pinit1.authorize_activation(bundle, pinit1.activation_context(mode, bundle))

    def test_all_registered_hostile_controls_reject_in_python(self) -> None:
        controls = qualify_native_initial_system._controls()
        self.assertEqual(120, len(controls))
        self.assertEqual(list(pinit1.NEGATIVE_CONTROL_IDS), [item.control_id for item in controls])
        for control in controls:
            with self.subTest(control=control.control_id):
                _, result = qualify_native_initial_system._control_request(control)
                self.assertTrue(result.startswith("ERR:"), result)

    def test_readiness_records_complete_cross_language_campaign(self) -> None:
        summary = self.readiness["summary"]
        self.assertEqual(3, summary["rust_host_tests_passed"])
        self.assertEqual(2, summary["no_std_target_builds_passed"])
        self.assertEqual(3, summary["golden_vectors_matched"])
        self.assertEqual(120, summary["negative_controls_passed"])
        self.assertEqual(16_384, summary["differential_fuzz_cases"])
        self.assertEqual(0, summary["differential_mismatches"])

    def test_release_gate_accepts_non_promoting_readiness(self) -> None:
        check = pooleos_release_gate.check_native_initial_system_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("pooleboot_enforcement=false", check["detail"])
        self.assertIn("production_ready=false", check["detail"])

    def test_claim_boundary_remains_non_promoting(self) -> None:
        self.assertEqual(pinit1.expected_claims(), self.readiness["claims"])
        for key in (
            "pooleboot_inner_semantics_enforced",
            "poolekernel_activation_enforced",
            "outer_signature_verified",
            "manifest_signature_verified",
            "persistent_rollback_state_enforced",
            "component_abi_verified",
            "kernel_capabilities_allocated",
            "resources_allocated",
            "component_executed",
            "initial_system_active",
            "n5_exit_gate_satisfied",
            "production_ready",
        ):
            self.assertFalse(self.readiness["claims"][key])
        self.assertFalse(self.readiness["production_ready"])

    def test_readiness_stales_when_an_implementation_binding_changes(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["bindings"]["implementation_inputs"][0]["sha256"] = "0" * 64
        self.assertIn("readiness input bindings are stale", pinit1.readiness_errors(changed))

    def test_component_encoder_ignores_untrusted_declared_digest_field(self) -> None:
        base = pinit1.parse(pinit1.minimal_bundle())
        changed = dataclasses.replace(base.components[0], sha256="0" * 64)
        data = pinit1.encode(
            bundle_version=base.bundle_version,
            minimum_secure_version=base.minimum_secure_version,
            root_service_id=base.root_service_id,
            allowed_boot_modes=base.allowed_boot_modes,
            required_kernel_abi_major=base.required_kernel_abi_major,
            minimum_kernel_abi_minor=base.minimum_kernel_abi_minor,
            required_pbp_major=base.required_pbp_major,
            minimum_pbp_minor=base.minimum_pbp_minor,
            start_timeout_ms=base.start_timeout_ms,
            rollback_timeout_ms=base.rollback_timeout_ms,
            max_total_restarts=base.max_total_restarts,
            components=(changed,),
            services=base.services,
            dependencies=base.dependencies,
            resources=base.resources,
            capabilities=base.capabilities,
        )
        self.assertNotEqual("0" * 64, pinit1.parse(data).components[0].sha256)

    def test_public_receipt_exposes_no_host_path_or_differential_corpus(self) -> None:
        encoded = json.dumps(self.readiness, ensure_ascii=True)
        self.assertNotIn("C:\\Users", encoded)
        self.assertFalse(self.readiness["differential_fuzz"]["corpus_published"])
        self.assertFalse(self.readiness["validator_qualification"]["host_probe_artifact_identity_recorded"])


if __name__ == "__main__":
    unittest.main()
