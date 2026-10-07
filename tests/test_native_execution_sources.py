import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_execution_sources as sources
from tools import pooleos_release_gate as gate, qualify_native_execution_sources as qualifier

ROOT = Path(__file__).resolve().parents[1]


class NativeExecutionSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("runtime", "tools", "runs", "outputs", "specs"):
            (self.root / name).mkdir()
        self.write("runtime/__init__.py", "")
        self.write("runtime/helper.py", "from . import leaf\n")
        self.write("runtime/leaf.py", "VALUE = 1\n")
        for path in {p for paths in sources.REVIEWED_DATA_INPUTS.values() for p in paths}:
            self.write(path, '{"synthetic_data": "original"}')
        self.captures = {}
        for profile in sources.PROFILES:
            receipt, roots = sources.profile_paths(profile)
            self.write(roots[0], "from runtime import helper\n")
            self.write(roots[1], "from runtime import helper\n")
            self.write(receipt, json.dumps({"synthetic_profile": profile}))
            output = f"outputs/{profile}.json"
            self.write(output, (self.root / receipt).read_text())
            capture_path = self.root / f"outputs/{profile}-capture.json"
            capture_path.with_suffix(".log").write_text("synthetic execution\n")
            snapshot = {b["path"]: b["sha256"] for b in sources.source_closure(self.root, roots)}
            snapshot.update({b["path"]: b["sha256"] for b in sources.reviewed_data_bindings(self.root, profile)})
            record = {"command": ["python", "-B", roots[1], "--out", output],
                      "return_code": 0, "source_unchanged": True, "changed_paths": [],
                      "source_before": snapshot,
                      "log_sha256": sources.digest(capture_path.with_suffix(".log").read_bytes())}
            capture_path.write_text(json.dumps(record))
            self.captures[profile] = capture_path
        self.receipt = qualifier.qualify(self.captures, self.root)

    def write(self, path, text):
        (self.root / path).write_text(text, encoding="utf-8")

    def mutate_capture(self, mutate):
        path = self.captures["locks"]
        value = json.loads(path.read_bytes())
        mutate(value)
        path.write_text(json.dumps(value))

    def test_current_real_receipt_and_aggregate_pass(self):
        value = json.loads((ROOT / sources.RECEIPT).read_bytes())
        self.assertEqual(sources.evidence_errors(value, ROOT), [])
        self.assertTrue(gate.check_native_execution_sources()["ok"])

    def test_retained_capture_projection_is_deterministic(self):
        self.assertEqual(self.receipt, qualifier.qualify(self.captures, self.root))
        self.assertEqual(sources.evidence_errors(self.receipt, self.root), [])
        self.assertEqual(len(self.receipt["profiles"]), 27)
        self.assertFalse(self.receipt["boundaries"]["fresh_guest_execution"])

    def test_relative_transitive_and_package_initializers_are_bound(self):
        files = {b["path"] for b in self.receipt["profiles"][0]["sources"]}
        self.assertTrue({"runtime/__init__.py", "runtime/helper.py", "runtime/leaf.py"} <= files)
        self.write("tools/__init__.py", "from runtime import leaf\n")
        self.write("runtime/helper.py", "import tools.qualify_native_kernel_locks\n")
        closure = sources.source_closure(self.root, ("runtime/helper.py",))
        self.assertIn("tools/__init__.py", {b["path"] for b in closure})

    def test_shared_leaf_edit_invalidates_every_affected_profile_and_capture(self):
        self.write("runtime/leaf.py", "VALUE = 2\n")
        self.assertTrue(sources.evidence_errors(self.receipt, self.root))
        for profile in sources.PROFILES:
            with self.subTest(profile=profile), self.assertRaisesRegex(sources.SourceEvidenceError, "snapshot"):
                sources.captured_profile(profile, self.captures[profile], self.root)

    def test_dynamic_import_and_missing_static_import_fail_closed(self):
        for code in ("import runtime.missing\n", "__import__('runtime.leaf')\n",
                     "import importlib\nimportlib.import_module('runtime.leaf')\n"):
            with self.subTest(code=code):
                self.write("runtime/helper.py", code)
                self.assertTrue(sources.evidence_errors(self.receipt, self.root))

    def test_source_and_receipt_mutations_fail_component_and_gate(self):
        candidates = [None, [], {}, {**self.receipt, "extra": True}]
        for field in ("profile", "receipt", "sources", "capture"):
            for value in (None, {}, [], "invalid"):
                candidate = copy.deepcopy(self.receipt)
                candidate["profiles"][0][field] = value
                candidates.append(candidate)
        for field, value in (("return_code", False), ("return_code", 0.0), ("return_code", 1),
                             ("source_unchanged", 1), ("record_sha256", "invalid"),
                             ("log_sha256", "f" * 64), ("source_snapshot_sha256", "")):
            candidate = copy.deepcopy(self.receipt)
            candidate["profiles"][0]["capture"][field] = value
            candidates.append(candidate)
        for mutate in (
            lambda v: v["profiles"].pop(),
            lambda v: v["profiles"].reverse(),
            lambda v: v["profiles"][0]["sources"].pop(),
            lambda v: v["profiles"][0]["sources"].append(v["profiles"][0]["sources"][0]),
            lambda v: v["profiles"][0]["receipt"].update(sha256="0" * 64),
            lambda v: v["boundaries"].update(authentication=True),
        ):
            candidate = copy.deepcopy(self.receipt)
            mutate(candidate)
            candidates.append(candidate)
        self.assertEqual(len(candidates), 33)
        path = self.root / "runs/corrupted.json"
        for i, candidate in enumerate(candidates):
            with self.subTest(case=i):
                self.assertTrue(sources.evidence_errors(candidate, self.root))
                path.write_text(json.dumps(candidate))
                with mock.patch.object(gate, "ROOT", self.root):
                    self.assertFalse(gate.check_native_execution_sources(path)["ok"])

    def test_failed_changed_or_wrong_qualifier_capture_rejects(self):
        path = self.captures["locks"]
        original = path.read_bytes()
        mutations = (
            lambda v: v.update(return_code=False), lambda v: v.update(return_code=1),
            lambda v: v.update(source_unchanged=False), lambda v: v.update(changed_paths=["x"]),
            lambda v: v["command"].__setitem__(2, "tools/wrong.py"),
            lambda v: v["source_before"].pop("runtime/leaf.py"),
        )
        for mutate in mutations:
            path.write_bytes(original)
            self.mutate_capture(mutate)
            with self.assertRaises(sources.SourceEvidenceError):
                qualifier.qualify(self.captures, self.root)

    def test_changed_log_or_output_cannot_be_rebound(self):
        path = self.captures["locks"]
        log = path.with_suffix(".log")
        original = log.read_bytes()
        log.write_text("different log")
        with self.assertRaisesRegex(sources.SourceEvidenceError, "log changed"):
            qualifier.qualify(self.captures, self.root)
        log.write_bytes(original)
        self.write("outputs/locks.json", "substituted receipt")
        with self.assertRaisesRegex(sources.SourceEvidenceError, "output differs"):
            qualifier.qualify(self.captures, self.root)

    def test_incomplete_capture_set_rejects(self):
        self.captures.pop("locks")
        with self.assertRaises(sources.SourceEvidenceError):
            qualifier.qualify(self.captures, self.root)

    def test_every_upstream_profile_is_required_and_bound(self):
        for index, profile in enumerate(sources.PROFILES[:13]):
            with self.subTest(profile=profile):
                captures = dict(self.captures)
                captures.pop(profile)
                with self.assertRaises(sources.SourceEvidenceError):
                    qualifier.qualify(captures, self.root)
                candidate = copy.deepcopy(self.receipt)
                candidate["profiles"][index] = candidate["profiles"][-1]
                self.assertTrue(sources.evidence_errors(candidate, self.root))
                path = self.root / sources.profile_paths(profile)[1][0]
                original = path.read_bytes()
                path.write_bytes(original + b"CHANGED = True\n")
                self.assertTrue(sources.evidence_errors(self.receipt, self.root))
                with self.assertRaisesRegex(sources.SourceEvidenceError, "snapshot"):
                    sources.captured_profile(profile, self.captures[profile], self.root)
                path.write_bytes(original)

    def test_historical_fourteen_profile_coverage_is_not_current(self):
        candidate = copy.deepcopy(self.receipt)
        candidate["profiles"] = candidate["profiles"][13:]
        self.assertEqual(len(candidate["profiles"]), 14)
        self.assertTrue(sources.evidence_errors(candidate, self.root))

    def test_windows_command_paths_preserve_original_capture_hash(self):
        self.mutate_capture(lambda v: v["command"].__setitem__(2, v["command"][2].replace("/", "\\")))
        actual = sources.captured_profile("locks", self.captures["locks"], self.root)
        self.assertEqual(actual["capture"]["record_sha256"], sources.digest(self.captures["locks"].read_bytes()))
        self.assertEqual(actual["sources"], self.receipt["profiles"][-1]["sources"])

    def test_unsafe_dependency_paths_reject(self):
        for path in ("../outside.py", "/outside.py", "C:/outside.py", "runtime\\leaf.py", "runtime//leaf.py"):
            with self.subTest(path=path), self.assertRaises(sources.SourceEvidenceError):
                sources.safe_path(self.root, path)

    def test_changed_reviewed_data_rejects_both_gates_and_cannot_rebind_original_capture(self):
        for path in sorted({p for paths in sources.REVIEWED_DATA_INPUTS.values() for p in paths}):
            with self.subTest(path=path):
                file = self.root / path
                original = file.read_bytes()
                file.write_bytes(original + b"\n")
                self.assertTrue(sources.evidence_errors(self.receipt, self.root))
                candidate = self.root / sources.RECEIPT
                candidate.write_text(json.dumps(self.receipt))
                with mock.patch.object(gate, "ROOT", self.root):
                    self.assertFalse(gate.check_native_execution_sources(candidate)["ok"])
                for profile, paths in sources.REVIEWED_DATA_INPUTS.items():
                    if path in paths:
                        with self.assertRaisesRegex(sources.SourceEvidenceError, "snapshot"):
                            sources.captured_profile(profile, self.captures[profile], self.root)
                file.write_bytes(original)
        self.assertEqual(sources.evidence_errors(self.receipt, self.root), [])

    def test_reviewed_data_is_exact_ordered_typed_and_not_optional(self):
        index = sources.PROFILES.index("policy")
        mutations = (
            lambda v: v["profiles"][index].pop("reviewed_data"),
            lambda v: v["profiles"][index].update(reviewed_data=[]),
            lambda v: v["profiles"][index].update(reviewed_data=None),
            lambda v: v["profiles"][index]["reviewed_data"].reverse(),
            lambda v: v["profiles"][index]["reviewed_data"].pop(),
            lambda v: v["profiles"][index]["reviewed_data"].append(v["profiles"][index]["reviewed_data"][0]),
            lambda v: v["profiles"][index]["reviewed_data"][0].update(sha256="0" * 64),
            lambda v: v["profiles"][index]["reviewed_data"][0].update(sha256=False),
            lambda v: v["profiles"][index]["reviewed_data"][0].update(path="../outside.json"),
            lambda v: v["profiles"][index]["reviewed_data"][0].update(extra=True),
            lambda v: v["boundaries"].update(reviewed_admission_data_bound=1),
            lambda v: v["boundaries"].update(dynamic_data_and_tool_closure=True),
            lambda v: v.update(format="POOLEOS-STATIC-EXECUTION-SOURCES-1"),
        )
        path = self.root / sources.RECEIPT
        for number, mutate in enumerate(mutations):
            with self.subTest(case=number):
                value = copy.deepcopy(self.receipt)
                mutate(value)
                self.assertTrue(sources.evidence_errors(value, self.root))
                path.write_text(json.dumps(value))
                with mock.patch.object(gate, "ROOT", self.root):
                    self.assertFalse(gate.check_native_execution_sources(path)["ok"])

    def test_missing_or_rehashed_reviewed_data_cannot_be_laundered_as_original(self):
        profile = "load"
        relative = sources.REVIEWED_DATA_INPUTS[profile][0]
        path = self.root / relative
        original = path.read_bytes()
        path.unlink()
        self.assertTrue(sources.evidence_errors(self.receipt, self.root))
        with self.assertRaises(OSError):
            sources.captured_profile(profile, self.captures[profile], self.root)
        path.write_bytes(original + b"\n")
        candidate = copy.deepcopy(self.receipt)
        candidate["profiles"][sources.PROFILES.index(profile)]["reviewed_data"] = sources.reviewed_data_bindings(self.root, profile)
        # Recorded consistency alone is not authentication; generation must also check the original snapshot.
        self.assertEqual(sources.evidence_errors(candidate, self.root), [])
        with self.assertRaisesRegex(sources.SourceEvidenceError, "snapshot"):
            qualifier.qualify(self.captures, self.root)

    def test_original_capture_requires_every_reviewed_data_hash(self):
        profile = "policy"
        path = self.captures[profile]
        original = path.read_bytes()
        for relative in sources.REVIEWED_DATA_INPUTS[profile]:
            value = json.loads(original)
            del value["source_before"][relative]
            path.write_text(json.dumps(value))
            with self.subTest(path=relative), self.assertRaisesRegex(sources.SourceEvidenceError, "snapshot"):
                sources.captured_profile(profile, path, self.root)
        path.write_bytes(original)
        with self.assertRaises(sources.SourceEvidenceError):
            sources.reviewed_data_bindings(self.root, "unknown")

    def test_current_record_preserves_original_source_and_capture_fields(self):
        old = json.loads((ROOT / "tests/fixtures/cycle228-execution-sources.json").read_bytes())
        new = json.loads((ROOT / sources.RECEIPT).read_bytes())
        self.assertEqual(len(new["profiles"]), len(old["profiles"]))
        for before, after in zip(old["profiles"], new["profiles"], strict=True):
            self.assertEqual(before, {k: v for k, v in after.items() if k != "reviewed_data"})
        self.assertEqual(sum(len(r["reviewed_data"]) for r in new["profiles"]), 18)
        self.assertEqual(len({b["path"] for r in new["profiles"] for b in r["reviewed_data"]}), 13)
        self.assertTrue(sources.evidence_errors(old, ROOT))

    def test_missing_and_malformed_aggregate_artifact_fail(self):
        path = self.root / "missing.json"
        self.assertFalse(gate.check_native_execution_sources(path)["ok"])
        path.write_text("{")
        self.assertFalse(gate.check_native_execution_sources(path)["ok"])


if __name__ == "__main__":
    unittest.main()
