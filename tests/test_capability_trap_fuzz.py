import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import capability_trap_fuzz  # noqa: E402
from runtime import microkernel_isolation  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_capability_trap_fuzz  # noqa: E402


class CapabilityTrapFuzzTests(unittest.TestCase):
    def _matrix(self) -> dict:
        return {
            "status": "warn",
            "summary": {"failed_check_count": 0},
            "resources": [{"id": "grid.main_grid"}],
        }

    def test_fuzz_proof_validates_and_traps_all_cases(self) -> None:
        fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
            policy=microkernel_isolation.make_isolation_proof(),
            permission_matrix=self._matrix(),
            unknown_capability_count=6,
            unknown_permission_count=4,
        )
        schema = json.loads((ROOT / "specs" / "capability-trap-fuzz.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(fuzz, schema), [])
        self.assertEqual(fuzz["status"], "pass")
        self.assertEqual(fuzz["summary"]["operation_count"], 10)
        self.assertEqual(fuzz["summary"]["trapped_count"], 10)
        self.assertEqual(fuzz["summary"]["failed_check_count"], 0)
        self.assertTrue(
            all(operation["trap_code"] == "CAPABILITY_UNKNOWN" for operation in fuzz["operations"] if operation["fuzz_kind"] == "unknown_capability")
        )
        self.assertTrue(
            all(operation["trap_code"] == "POOLEGLYPH_PERMISSION_DENIED" for operation in fuzz["operations"] if operation["fuzz_kind"] == "unknown_permission")
        )

    def test_cli_writes_fuzz_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "microkernel_isolation.json"
            matrix_path = tmp_path / "permission_capability_matrix.json"
            out = tmp_path / "capability_trap_fuzz.json"
            microkernel_isolation.write_proof(microkernel_isolation.make_isolation_proof(), policy_path)
            matrix_path.write_text(json.dumps(self._matrix()), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = emit_capability_trap_fuzz.main(
                    [
                        "--isolation-proof",
                        str(policy_path),
                        "--permission-capability-matrix",
                        str(matrix_path),
                        "--unknown-capability-count",
                        "3",
                        "--unknown-permission-count",
                        "2",
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            fuzz = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(fuzz["artifact_kind"], "pooleos.capability_trap_fuzz")
            self.assertEqual(fuzz["summary"]["operation_count"], 5)


if __name__ == "__main__":
    unittest.main()
