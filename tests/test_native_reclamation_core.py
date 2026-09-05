"""Source freshness and non-promotion guards for the PKRECLAIM1 core receipt."""

import copy
import json
import unittest

from tools import qualify_native_reclamation_core as core


class ReclamationCoreTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(core.REPORT.read_text(encoding="utf-8"))

    def test_current_receipt_is_bound_to_sources(self):
        core.validate_report(self.report)

    def test_promotion_and_count_mutations_reject(self):
        for key in (
            "production_ready", "live_integration_verified", "cross_cpu_quiescence_verified",
            "n12_3_complete", "focused_test_count", "kernel_regression_count", "compile_fail_borrow_tests",
            "task_lifetime_test_count",
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.report)
                changed[key] = True if type(changed[key]) is bool else changed[key] + 1
                with self.assertRaises(ValueError):
                    core.validate_report(changed)

    def test_lifetime_scope_and_contract_mutations_reject(self):
        for key, value in (
            ("task_lifetime_scope", "live_active_address_space_quiescence"),
            ("task_lifetime_contract_id", "PKLIFE2"),
            ("schema_version", "1.0"),
        ):
            changed = copy.deepcopy(self.report)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                core.validate_report(changed)

    def test_lifetime_count_wrong_types_reject(self):
        for value in (True, float(core.LIFETIME_TEST_COUNT), str(core.LIFETIME_TEST_COUNT)):
            changed = copy.deepcopy(self.report)
            changed["task_lifetime_test_count"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.validate_report(changed)

    def test_missing_reordered_or_failed_stage_rejects(self):
        for mutation in ("missing", "reordered", "failed", "digest", "extra"):
            changed = copy.deepcopy(self.report)
            if mutation == "missing":
                changed["stages"].pop()
            elif mutation == "reordered":
                changed["stages"].reverse()
            elif mutation == "failed":
                changed["stages"][0]["status"] = "fail"
            elif mutation == "digest":
                changed["stages"][0]["output_sha256"] = "bad"
            else:
                changed["unexpected"] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                core.validate_report(changed)

    def test_stale_or_missing_source_binding_rejects(self):
        for path in core.SOURCES:
            changed = copy.deepcopy(self.report)
            changed["sources"][path] = "0" * 64
            with self.subTest(path=path), self.assertRaises(ValueError):
                core.validate_report(changed)

    def test_output_parser_rejects_skips_filters_duplicates_and_failures(self):
        good = "test result: ok. 19 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
        core.require_test_result(good, 19)
        for bad in (
            "", good + "\n" + good, good.replace("19 passed", "18 passed"),
            good.replace("0 failed", "1 failed"), good.replace("0 ignored", "1 ignored"),
            good.replace("0 filtered", "1 filtered"), good.replace("ok.", "FAILED."),
            good + "\ntest result: FAILED. 0 passed; 1 failed",
        ):
            with self.subTest(output=bad), self.assertRaises(ValueError):
                core.require_test_result(bad, 19)


if __name__ == "__main__":
    unittest.main()
