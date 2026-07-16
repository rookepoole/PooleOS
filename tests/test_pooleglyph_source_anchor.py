import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_source_anchor  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pooleglyph_source_anchor  # noqa: E402


class PooleGlyphSourceAnchorTests(unittest.TestCase):
    def _make_fake_pooleglyph(self, tmp_path: Path) -> Path:
        root = tmp_path / "PooleGlyph"
        (root / "docs").mkdir(parents=True)
        (root / "checkpoints").mkdir()
        for relative in pooleglyph_source_anchor.REQUIRED_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test\n", encoding="utf-8")
        manifest = {
            "checkpoint": "Phase 19 - import/export enforcement",
            "sha256": "A" * 64,
            "zip_path": str(root / "checkpoints" / "phase19.zip"),
            "handoff_markdown": str(root / "checkpoints" / "PHASE19.md"),
            "next_recommended_phase": "Phase 20 - version declarations",
            "created_local_time": "2026-06-29 23:53:51",
        }
        (root / "checkpoints" / "phase19.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def test_anchor_schema_accepts_live_shape_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_fake_pooleglyph(Path(tmp))
            anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=root)
            schema = json.loads((ROOT / "specs" / "pooleglyph-source-anchor.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(anchor, schema), [])
            self.assertEqual(anchor["latest_checkpoint"]["checkpoint"], "Phase 19 - import/export enforcement")
            self.assertEqual(anchor["summary"]["checkpoint_manifest_count"], 1)
            self.assertEqual(anchor["summary"]["missing_required_file_count"], 0)

    def test_default_path_prefers_home_pooleglyph_when_present(self) -> None:
        selected = pooleglyph_source_anchor.default_pooleglyph_path(workspace_root=ROOT.parent)
        if (Path.home() / "PooleGlyph").exists():
            self.assertEqual(selected, Path.home() / "PooleGlyph")
        else:
            self.assertEqual(selected, ROOT.parent / "PooleGlyph")

    def test_cli_writes_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_fake_pooleglyph(Path(tmp))
            out = Path(tmp) / "anchor.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pooleglyph_source_anchor.main(["--pooleglyph", str(root), "--out", str(out)])
            self.assertEqual(code, 1)
            anchor = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(anchor["artifact_kind"], "pooleos.pooleglyph_source_anchor")
            self.assertEqual(anchor["status"], "fail")


if __name__ == "__main__":
    unittest.main()
