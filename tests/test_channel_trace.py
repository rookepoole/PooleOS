import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK_ROOT / "PooleGlyph"))

import pooleglyph_pgvm as pg  # noqa: E402
from runtime import channel_telemetry as ct  # noqa: E402
from runtime import channel_trace as tr  # noqa: E402
from tools import emit_channel_trace  # noqa: E402


class ChannelTraceTests(unittest.TestCase):
    def test_trace_artifact_contains_claim_and_summary(self) -> None:
        lattice = pg.six_support_demo_lattice()
        summary = ct.measure_channels(lattice)
        claim = tr.make_claim_record(
            claim_id="TRACE-999",
            title="Unit trace",
            source_descriptor="unit:six-support",
            limitations="Unit-test trace only; not a production safety claim.",
        )
        artifact = tr.make_channel_trace(summary, claim=claim)
        self.assertEqual(artifact["artifact_kind"], tr.TRACE_KIND)
        self.assertEqual(artifact["claim"]["claim_lane"], "verifier")
        self.assertEqual(artifact["summary"]["accepted_counts"]["B6"], 1)
        self.assertEqual(len(artifact["events"]), artifact["summary"]["event_count"])

    def test_emit_channel_trace_cli_writes_rectangle_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rect_trace.json"
            with redirect_stdout(io.StringIO()):
                code = emit_channel_trace.main(["--case", "rectangle-2x2", "--out", str(out)])
            self.assertEqual(code, 0)
            artifact = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(artifact["summary"]["accepted_counts"]["B5"], 12)
            self.assertEqual(artifact["summary"]["accepted_counts"]["B7"], 16)
            self.assertEqual(artifact["summary"]["births"], 28)


if __name__ == "__main__":
    unittest.main()
