import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_trust as trust  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class NativeBootTrustReleaseGateTests(unittest.TestCase):
    def test_release_gate_accepts_exact_bounded_receipt(self) -> None:
        artifact = trust.read_json(ROOT / "runs" / "native_boot_trust_readiness.json")
        self.assertEqual([], trust.readiness_errors(artifact, ROOT))
        check = pooleos_release_gate.check_native_boot_trust_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("contract=PBTRUST1/PBSTATE1", check["detail"])
        self.assertIn("power_loss=9/9", check["detail"])
        self.assertIn("backend_io=false", check["detail"])
        self.assertIn("authority=0", check["detail"])
        self.assertIn("production_ready=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
