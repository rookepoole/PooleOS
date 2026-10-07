import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_locks as locks
from tests.test_native_cpu_entry_provenance import control_mutations, pair_mutations
from tools import pooleos_release_gate as gate, qualify_native_kernel_locks as qualifier

ROOT = Path(__file__).resolve().parents[1]


def corrupted_records(baseline):
    yield from control_mutations(baseline)
    for family in ("exit", "coverage", "evidence"):
        for label, pair in pair_mutations(baseline["execution"], family):
            candidate = copy.deepcopy(baseline)
            candidate["execution"] = pair
            yield family + ":" + label, candidate
    paths = (
        ("observation",), ("build", "host_probe"), ("build", "source_audit"),
        ("build", "default_pooleboot"), ("build", "locks_pooleboot"),
        ("media",), ("media", "inspection"), ("execution", "normalized_command"),
    )
    for path in paths:
        for value in (None, {}, [], "invalid"):
            candidate = copy.deepcopy(baseline)
            target = candidate
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            yield ".".join(path) + "=" + repr(value), candidate
    for path, value in (
        (("status_date",), "2026-02-30"), (("status_date",), "20261007"),
        (("nonclaims",), ["invalid"] * 4),
        (("observation", "live", "tickets"), [0, 1, 1, 3]),
        (("observation", "live", "acquisitions"), 4.0),
        (("build", "host_probe", "lines"), baseline["build"]["host_probe"]["lines"][:-1]),
        (("build", "host_probe", "output_sha256"), "0" * 64),
        (("build", "host_probe", "thread_count"), 4.0),
        (("build", "source_audit", "files", "core", "sha256"), "0" * 64),
        (("build", "default_pooleboot", "sha256"), "0" * 64),
        (("build", "locks_pooleboot", "selected_development_feature"), None),
        (("build", "all_profile_binaries_distinct"), 1),
        (("execution", "qemu_sha256"), "0" * 64),
        (("execution", "firmware_code_sha256"), "0" * 64),
        (("execution", "vars_template_sha256"), "0" * 64),
        (("execution", "normalized_command_sha256"), "0" * 64),
        (("execution", "virtual_cpu_count"), 4.0),
        (("execution", "application_processor_count"), 3.0),
        (("media", "byte_count"), 1), (("media", "sha256"), "0" * 64),
        (("media", "physical_media_write_performed"), 0),
        (("media", "inspection", "kernel", "loaded_sha256"), "0" * 64),
    ):
        candidate = copy.deepcopy(baseline)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert json.dumps(candidate, sort_keys=True) != json.dumps(baseline, sort_keys=True)
        yield ".".join(path), candidate
    candidate = copy.deepcopy(baseline)
    candidate["negative_controls"][0]["case_count"] += 1
    candidate["negative_controls"][4]["case_count"] -= 1
    yield "redistributed-control-total", candidate


class NativeLocksAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = locks.read_json(ROOT / locks.READINESS_RELATIVE)

    def test_genuine_receipt_reconstructs_without_rebinding(self):
        self.assertEqual(locks.readiness_errors(self.receipt, ROOT), [])
        self.assertTrue(gate.check_native_kernel_locks_readiness()["ok"])
        self.assertEqual(self.receipt["negative_controls"], locks.expected_controls())

    def test_corrupted_record_admission_rejects_without_exceptions(self):
        self.assertEqual(locks.readiness_errors(self.receipt, ROOT), [])
        cases = list(corrupted_records(self.receipt))
        self.assertEqual(len(cases), 631)
        for label, candidate in cases:
            with self.subTest(case=label):
                self.assertTrue(locks.readiness_errors(candidate, ROOT))
                with mock.patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                    self.assertFalse(gate.check_native_kernel_locks_readiness()["ok"])

    def test_controls_execute_and_detect_disabled_validators(self):
        markers = self.receipt["execution"]["runs"][0]["markers"]
        lines = self.receipt["build"]["host_probe"]["lines"]
        _, source = qualifier._source_audit()
        self.assertEqual(qualifier._negative_controls(markers, lines, source), locks.expected_controls())
        for module, name in ((locks, "validate_markers"), (locks, "parse_probe_output"),
                             (qualifier, "_audit_lock_source")):
            with self.subTest(disabled=name), mock.patch.object(module, name, return_value={}):
                with self.assertRaises(qualifier.QualificationError):
                    qualifier._negative_controls(markers, lines, source)

    def test_empty_controls_reject(self):
        with self.assertRaises(qualifier.QualificationError):
            qualifier._require_rejections("empty", [])

    def test_host_probe_has_a_bounded_subprocess(self):
        process = mock.Mock(pid=4321)
        process.wait.side_effect = [subprocess.TimeoutExpired("cargo", 180), 0]
        with mock.patch.object(qualifier.qualify_native_kernel_entry, "_toolchain", return_value=(Path("cargo"), None, {})), \
             mock.patch.object(qualifier.sys, "platform", "win32"), \
             mock.patch.object(qualifier.subprocess, "Popen", return_value=process), \
             mock.patch.object(qualifier.subprocess, "run", return_value=mock.Mock(returncode=0)) as cleanup:
            with self.assertRaisesRegex(qualifier.QualificationError, "exceeded 180"):
                qualifier._run_host_probe(ROOT, ROOT / "tmp")
        self.assertEqual(process.wait.call_args_list, [mock.call(timeout=180), mock.call(timeout=10)])
        self.assertEqual(cleanup.call_args.args[0][1:], ["/PID", "4321", "/T", "/F"])
        self.assertEqual(cleanup.call_args.kwargs["timeout"], 10)
        process.kill.assert_not_called()

        process = mock.Mock(pid=4322)
        process.wait.side_effect = subprocess.TimeoutExpired("cargo", 180)
        with mock.patch.object(qualifier.qualify_native_kernel_entry, "_toolchain", return_value=(Path("cargo"), None, {})), \
             mock.patch.object(qualifier.sys, "platform", "win32"), \
             mock.patch.object(qualifier.subprocess, "Popen", return_value=process), \
             mock.patch.object(qualifier.subprocess, "run", return_value=mock.Mock(returncode=1)):
            with self.assertRaisesRegex(qualifier.QualificationError, "cleanup unconfirmed"):
                qualifier._run_host_probe(ROOT, ROOT / "tmp")


if __name__ == "__main__":
    unittest.main()
