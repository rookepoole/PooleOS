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
            "physical_retention_test_count", "physical_retention_live_verified",
            "ap_resource_test_count", "ap_resource_live_verified",
            "task_stack_test_count", "task_stack_page_count", "task_stack_live_verified",
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.report)
                changed[key] = True if type(changed[key]) is bool else changed[key] + 1
                with self.assertRaises(ValueError):
                    core.validate_report(changed)

    def test_lifetime_scope_and_contract_mutations_reject(self):
        for key, value in (
            ("task_lifetime_scope", "live_active_address_space_quiescence"),
            ("task_lifetime_scope", "host_executed_scheduler_and_inactive_address_space_ownership"),
            ("task_lifetime_contract_id", "PKLIFE2"),
            ("schema_version", "1.0"),
            ("schema_version", "1.2"),
            ("physical_retention_scope", "global_active_address_space_ownership"),
            ("physical_retention_contract_id", "PKRETAIN2"),
            ("ap_resource_contract_id", "PKAPOWN2"),
            ("ap_resource_scope", "general_cpu_retirement"),
            ("schema_version", "1.3"),
            ("schema_version", "1.4"),
            ("task_lifetime_scope", "mandatory_inactive_table_and_bound_frame_retention"),
            ("task_stack_contract_id", "PKSTACK2"),
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

    def test_stack_test_evidence_rejects_missing_duplicate_failed_and_ignored_cases(self):
        good = "\n".join(f"test {name} ... ok" for name in core.STACK_TESTS)
        core.require_stack_test_results(good)
        for name in core.STACK_TESTS:
            line = f"test {name} ... ok"
            for bad in (good.replace(line, ""), good + "\n" + line,
                        good.replace(line, f"test {name} ... FAILED"),
                        good.replace(line, f"test {name} ... ignored")):
                with self.subTest(name=name, output=bad), self.assertRaises(ValueError):
                    core.require_stack_test_results(bad)

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


    def test_named_cases_reject_missing_duplicate_and_failed_tests(self):
        prefix = "physical_memory::tests::ap_resources::"
        good = f"test {prefix}one ... ok\ntest {prefix}two ... ok\n"
        core.require_named_test_result(good, prefix, 2)
        for bad in (
            "", good.replace("two", "one"), good.replace("two ... ok", "two ... FAILED"),
            good + f"test {prefix}three ... ok\n", good.replace(prefix, "unrelated::"),
            good + f"test {prefix}three ... FAILED\n",
            good + f"test {prefix}three ... ignored\n",
        ):
            with self.subTest(output=bad), self.assertRaises(ValueError):
                core.require_named_test_result(bad, prefix, 2)


    def test_ownership_groups_require_both_retention_modules_and_ap_cases(self):
        public = "physical_memory::tests::retention::"
        internal = "physical_memory::retention::tests::"
        ap = "physical_memory::tests::ap_resources::"
        good = "".join(
            f"test {prefix}case_{number} ... ok\n"
            for prefix, count in ((public, 18), (internal, 2), (ap, 11))
            for number in range(count)
        )
        core.require_ownership_test_results(good)
        core.require_ownership_test_results(good.replace("\n", "\r\n"))
        for prefix in (public, internal, ap):
            line = f"test {prefix}case_0 ... ok\n"
            for mutation, bad in (
                ("missing", good.replace(line, "")),
                ("duplicate", good + line),
                ("failed", good.replace(line, line.replace("ok", "FAILED"))),
                ("ignored", good.replace(line, line.replace("ok", "ignored"))),
                ("relocated", good.replace(line, line.replace(prefix, "unrelated::"))),
            ):
                with self.subTest(prefix=prefix, mutation=mutation), self.assertRaises(ValueError):
                    core.require_ownership_test_results(bad)
        # An unchanged total cannot conceal loss of either retention module.
        for bad in (good.replace(internal, public), good.replace(public, internal)):
            with self.subTest(output=bad), self.assertRaises(ValueError):
                core.require_ownership_test_results(bad)


if __name__ == "__main__":
    unittest.main()
