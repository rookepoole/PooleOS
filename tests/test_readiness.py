import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import readiness  # noqa: E402


class ReadinessTests(unittest.TestCase):
    def test_readiness_report_keeps_production_ready_false(self) -> None:
        report = readiness.make_readiness_report(
            checks=[readiness.make_check("unit", True, "ok")],
            artifacts=["artifact.json"],
            remaining_gaps=["bootable image missing"],
        )
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["summary"]["remaining_gap_count"], 1)

    def test_readiness_report_fails_on_failed_check(self) -> None:
        report = readiness.make_readiness_report(
            checks=[readiness.make_check("unit", False, "bad")],
            artifacts=[],
        )
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["summary"]["failed_checks"], 1)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()

