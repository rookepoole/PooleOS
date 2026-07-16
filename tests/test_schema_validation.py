import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_channel_trace, validate_artifact  # noqa: E402


class SchemaValidationTests(unittest.TestCase):
    def test_channel_trace_schema_accepts_generated_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "trace.json"
            with redirect_stdout(io.StringIO()):
                emit_channel_trace.main(["--case", "six-support", "--out", str(out)])
            artifact = json.loads(out.read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "specs" / "channel-trace.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(artifact, schema), [])

    def test_validate_artifact_cli_rejects_bad_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"artifact_kind": "wrong"}', encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = validate_artifact.main([str(bad)])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
