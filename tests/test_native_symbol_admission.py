from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_symbols as symbols
from tools import pooleos_release_gate as gate
from tools import qualify_native_symbols as qualifier


def recorded_receipt_mutations(receipt):
    def replace(path, replacement):
        result = copy.deepcopy(receipt)
        node = result
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = replacement
        return result

    def leaves(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from leaves(value, (*path, key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from leaves(value, (*path, index))
        else:
            yield path, node

    for family in ('summary', 'validator_qualification', 'debug_correspondence',
                   'activation_qualification', 'parser_differential', 'lookup_differential',
                   'golden_vectors', 'claims', 'phase_status', 'bindings'):
        for path, value in leaves(receipt[family], (family,)):
            changed = not value if type(value) is bool else value + 1 if type(value) is int else 'corrupt'
            yield family, str(path), replace(path, changed)
            if type(value) in (bool, int):
                wrong_type = int(value) if type(value) is bool else str(value)
                yield family, str(path) + '/type', replace(path, wrong_type)
        yield family, 'wrong_shape', replace((family,), None)
        if isinstance(receipt[family], dict):
            yield family, 'missing_fields', replace((family,), {})
            yield family, 'extra_field', replace((family,), dict(receipt[family], unrecorded=True))
    for index, control in enumerate(receipt['negative_controls']):
        yield 'controls', f'{index}/observed', replace(('negative_controls', index, 'observed'), 'accepted')
        forged = dict(control, expected='ERR:forged', observed='ERR:forged')
        yield 'controls', f'{index}/coherent_wrong_error', replace(('negative_controls', index), forged)
    for key in receipt['negative_controls'][0]:
        yield 'controls', key, replace(('negative_controls', 0, key), None)
    controls = receipt['negative_controls']
    for name, value in (('duplicate', [controls[0], *controls[:-1]]), ('reverse', list(reversed(controls))),
                        ('missing', controls[:-1]), ('extra', [*controls, controls[0]]), ('malformed', [None] * len(controls))):
        yield 'controls', name, replace(('negative_controls',), value)
    for field in ('production_ready', 'production_promotion_allowed', 'n5_exit_gate_satisfied'):
        yield 'boundary', field, replace((field,), 0)
    for name, value in (('null', None), ('list', []), ('boolean', True), ('empty', {})):
        yield 'root', name, value


class NativeSymbolAdmissionTests(unittest.TestCase):
    def test_recorded_results_are_required_by_runtime_and_actual_gate(self):
        receipt = symbols.read_json(ROOT / symbols.READINESS_RELATIVE)
        self.assertEqual(symbols.readiness_errors(receipt), [])
        with tempfile.TemporaryDirectory(prefix='psym-admission-', dir=ROOT / 'tmp') as directory:
            candidate = Path(directory) / 'receipt.json'
            candidate.write_text(json.dumps(receipt), encoding='utf-8')
            self.assertTrue(gate.check_native_symbol_readiness(candidate)['ok'])
            for family, name, changed in recorded_receipt_mutations(receipt):
                with self.subTest(family=family, case=name):
                    self.assertTrue(symbols.readiness_errors(changed))
                    candidate.write_text(json.dumps(changed), encoding='utf-8')
                    self.assertFalse(gate.check_native_symbol_readiness(candidate)['ok'])

    def test_rejected_results_cannot_overwrite_or_create_receipts(self):
        receipt = symbols.read_json(ROOT / symbols.READINESS_RELATIVE)
        receipt['debug_correspondence']['debug_file_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory(prefix='psym-output-', dir=ROOT / 'tmp') as directory:
            output = Path(directory) / 'readiness.json'
            for existing in (False, True):
                with self.subTest(existing=existing):
                    if existing:
                        output.write_bytes(b'preserve existing evidence\n')
                    with mock.patch.object(qualifier, 'make_readiness', return_value=receipt):
                        with self.assertRaises(qualifier.QualificationError):
                            qualifier.main(['--out', str(output)])
                    if existing:
                        self.assertEqual(output.read_bytes(), b'preserve existing evidence\n')
                    else:
                        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
