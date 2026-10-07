import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_errata_policy as policy
from tools import pooleos_release_gate as gate, qualify_native_kernel_errata_policy as qualifier

ROOT = Path(__file__).resolve().parents[1]


def receipt_corruptions(original):
    """Single-field omissions, shape changes and typed-value substitutions."""
    cases = []

    def add(path, replacement=None, remove=False):
        value = copy.deepcopy(original)
        if not path:
            value = replacement
        else:
            parent = value
            for key in path[:-1]:
                parent = parent[key]
            if remove:
                del parent[path[-1]]
            else:
                parent[path[-1]] = replacement
        if json.dumps(value, sort_keys=True) != json.dumps(original, sort_keys=True):
            cases.append((f'{path!r}:{"remove" if remove else repr(replacement)}', value))

    def walk(value, path=()):
        if isinstance(value, dict):
            for replacement in (None, [], {**value, 'unexpected': True}):
                add(path, replacement)
            for key, child in value.items():
                add(path + (key,), remove=True)
                walk(child, path + (key,))
        elif isinstance(value, list):
            for replacement in (None, {}, [], value[:-1], list(reversed(value))):
                add(path, replacement)
            for index, child in enumerate(value):
                walk(child, path + (index,))
        elif type(value) is bool:
            for replacement in (not value, int(value), None):
                add(path, replacement)
        elif type(value) is int:
            for replacement in (value + 1, float(value), bool(value), str(value), None):
                add(path, replacement)
        elif isinstance(value, str):
            for replacement in (value + '-corrupt', 0, None):
                add(path, replacement)
        else:
            add(path, 'invalid')

    walk(original)
    return cases


class NativeErrataAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = policy.read_json(ROOT / policy.READINESS_RELATIVE)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'receipt.json'

    def assert_rejected(self, value):
        self.assertTrue(policy.readiness_errors(value), 'component admitted corrupted evidence')
        self.path.write_text(json.dumps(value), encoding='utf-8')
        self.assertFalse(gate.check_native_kernel_errata_policy_readiness(self.path)['ok'],
                         'aggregate admitted corrupted evidence')

    def test_genuine_current_receipt_passes_without_rebinding(self):
        self.assertEqual(policy.readiness_errors(self.receipt), [])
        self.assertTrue(gate.check_native_kernel_errata_policy_readiness()['ok'])

    def test_every_recorded_field_rejects_corruption_without_exceptions(self):
        cases = receipt_corruptions(self.receipt)
        self.assertGreater(len(cases), 1000)
        for name, value in cases:
            with self.subTest(case=name):
                self.assert_rejected(value)

    def test_original_eight_counterexamples_reject(self):
        edits = [
            lambda v: v.update(build_qualification={}),
            lambda v: v.update(cross_language_vectors={}),
            lambda v: v.update(windows_registry_observation={}),
            lambda v: v['source_audit'].update(cpu_or_firmware_writes=1),
            lambda v: v['synthetic_policy_decision'].update(authority_grants=1),
            lambda v: v['current_policy_decision'].update(authority_grants=1),
            lambda v: v['negative_controls'].__setitem__(0, None),
            lambda v: v.update(current_policy_decision=None),
        ]
        for index, edit in enumerate(edits):
            with self.subTest(case=index):
                candidate = copy.deepcopy(self.receipt)
                edit(candidate)
                self.assert_rejected(candidate)

    def test_date_is_calendar_valid_and_canonical_not_fixed_day(self):
        for value in ('2026-02-30', '20261007', '2026-10-07T00:00:00', ' 2026-10-07', '2026-W41-3'):
            with self.subTest(date=value):
                candidate = copy.deepcopy(self.receipt)
                candidate['status_date'] = value
                self.assert_rejected(candidate)
        candidate = copy.deepcopy(self.receipt)
        candidate['status_date'] = '2026-10-06'
        self.assertEqual(policy.readiness_errors(candidate), [])

    def test_old_receipt_is_byte_preserved_but_stale(self):
        raw = (ROOT / 'tests/fixtures/cycle226-errata-readiness.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                         '9C25E26A8C53AF2A908DE41F51887E15AC7571C7C79EDF1318BAC13539F489B0')
        self.assert_rejected(json.loads(raw))

    def test_vector_and_control_reconstruction_matches_observed_prior_payload(self):
        old = policy.read_json(ROOT / 'tests/fixtures/cycle226-errata-readiness.json')
        self.assertEqual(policy.expected_vectors(), old['cross_language_vectors'])
        self.assertEqual(policy.expected_controls(), old['negative_controls'])

    def test_toolchain_lock_changes_invalidate_recorded_inputs(self):
        root = Path(self.temporary.name) / 'source'
        paths = {*policy.IMPLEMENTATION_INPUTS, policy.CONTRACT_RELATIVE,
                 policy.CONTRACT_SCHEMA_RELATIVE, policy.READINESS_SCHEMA_RELATIVE}
        for path in paths:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, target)
        self.assertEqual(policy.readiness_errors(self.receipt, root), [])
        lock = root / 'specs/native-toolchain-lock.json'
        value = policy.read_json(lock)
        value['channel_manifest']['rust_version'] += '-changed'
        lock.write_text(json.dumps(value), encoding='utf-8')
        self.assertTrue(policy.readiness_errors(self.receipt, root))

    def test_numeric_boolean_contract_substitutions_reject(self):
        for path in (('production_ready',), ('authority_gate', 'authority_grants'),
                     ('claims', 'target_cpu_qualified')):
            value = policy.expected_contract()
            parent = value
            for key in path[:-1]:
                parent = parent[key]
            actual = parent[path[-1]]
            parent[path[-1]] = int(actual) if type(actual) is bool else False
            self.assertTrue(policy.contract_errors(value), path)

    def test_nonfinite_and_cyclic_component_inputs_reject(self):
        for replacement in (float('nan'), float('inf'), float('-inf')):
            value = copy.deepcopy(self.receipt)
            value['summary']['authority_grant_count'] = replacement
            self.assert_rejected(value)
        value = copy.deepcopy(self.receipt)
        value['claims']['cycle'] = value
        self.assertTrue(policy.readiness_errors(value))

    def test_aggregate_guards_summary_even_with_component_disabled(self):
        value = copy.deepcopy(self.receipt)
        value['summary']['authority_grant_count'] = False
        self.path.write_text(json.dumps(value), encoding='utf-8')
        with mock.patch.object(policy, 'readiness_errors', return_value=[]):
            self.assertFalse(gate.check_native_kernel_errata_policy_readiness(self.path)['ok'])

    def test_disabled_validator_variants_are_detected_by_rejection_harness(self):
        value = copy.deepcopy(self.receipt)
        value['current_policy_decision']['authority_grants'] = 1
        with mock.patch.object(policy, 'readiness_errors', return_value=[]):
            with self.assertRaisesRegex(AssertionError, 'component admitted'):
                self.assert_rejected(value)
        with mock.patch.object(gate, 'check_native_kernel_errata_policy_readiness', return_value={'ok': True}):
            with self.assertRaisesRegex(AssertionError, 'aggregate admitted'):
                self.assert_rejected(value)

    def test_executed_qualifier_controls_detect_disabled_rejection(self):
        with mock.patch.object(qualifier, '_assert_agreement',
                               return_value=policy.evaluate(policy.synthetic_qualification_fixture())):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._evaluator_control(Path('unused'), policy.NEGATIVE_CONTROL_IDS[0], {})
        with mock.patch.object(policy, 'contract_errors', return_value=[]):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._contract_control(policy.NEGATIVE_CONTROL_IDS[-1], {})


if __name__ == '__main__':
    unittest.main()
