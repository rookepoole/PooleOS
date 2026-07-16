import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import microkernel_isolation  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_isolation_proof  # noqa: E402


class MicrokernelIsolationTests(unittest.TestCase):
    def test_default_isolation_proof_validates(self) -> None:
        proof = microkernel_isolation.make_isolation_proof()
        schema = json.loads((ROOT / "specs" / "isolation-proof.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(proof, schema), [])
        self.assertEqual(proof["artifact_kind"], "pooleos.microkernel_isolation_spike")
        self.assertEqual(proof["status"], "pass")
        self.assertFalse(proof["security_boundary_claimed"])
        self.assertGreaterEqual(proof["summary"]["denied_channel_count"], 1)

    def test_direct_guest_provenance_write_fails_policy(self) -> None:
        policy = microkernel_isolation.make_default_policy()
        policy["channels"].append(
            {
                "source": "pgvm_guest",
                "target": "provenance_service",
                "capability": "write_claim_lane",
                "direction": "append",
                "purpose": "Bad test edge.",
                "allowed": True,
                "requires_mediation": True,
            }
        )
        proof = microkernel_isolation.evaluate_policy(policy)
        self.assertEqual(proof["status"], "fail")
        checks = {check["name"]: check for check in proof["checks"]}
        self.assertFalse(checks["guest_has_no_direct_provenance_or_metric_write"]["ok"])
        self.assertFalse(checks["declared_denials_are_not_allowed"]["ok"])

    def test_host_bridge_kernel_channel_fails_policy(self) -> None:
        policy = microkernel_isolation.make_default_policy()
        policy["channels"].append(
            {
                "source": "host_bridge",
                "target": "geometry_kernel",
                "capability": "mutate_lattice_state",
                "direction": "write",
                "purpose": "Bad test edge.",
                "allowed": True,
                "requires_mediation": True,
            }
        )
        proof = microkernel_isolation.evaluate_policy(policy)
        checks = {check["name"]: check for check in proof["checks"]}
        self.assertEqual(proof["status"], "fail")
        self.assertFalse(checks["host_bridge_cannot_mutate_geometry_kernel"]["ok"])

    def test_cli_writes_valid_isolation_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "microkernel_isolation.json"
            with redirect_stdout(io.StringIO()):
                code = emit_isolation_proof.main(["--out", str(out)])
            self.assertEqual(code, 0)
            proof = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(proof["status"], "pass")
            self.assertEqual(proof["summary"]["failed_check_count"], 0)


if __name__ == "__main__":
    unittest.main()
