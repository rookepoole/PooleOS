import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_bridge_manifest  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pooleglyph_bridge_manifest  # noqa: E402


class PooleGlyphBridgeManifestTests(unittest.TestCase):
    def _make_fake_inputs(self, tmp_path: Path) -> tuple[Path, Path]:
        pooleglyph = tmp_path / "PooleGlyph"
        package_root = pooleglyph / "pooleglyph_v0_5_parser_ast_scaffold_package"
        (package_root / "tests").mkdir(parents=True)
        (package_root / "docs").mkdir()

        stack = [
            "stateset",
            "ruleset",
            "pass",
            "pipeline",
            "system",
            "export",
            "import exposing",
            "version",
            "requires",
            "capability",
            "feature",
            "profile",
            "environment",
            "target",
            "deployment",
            "package",
            "package surface export/import",
            "entrypoint",
            "config",
            "resource",
            "permission",
            "service",
            "lifecycle",
            "schedule",
            "policy",
            "contract",
            "interface",
            "adapter",
            "binding",
            "route",
            "channel",
            "endpoint",
            "port",
            "gateway",
            "node",
            "cluster",
            "mesh",
            "fabric",
            "domain",
            "realm",
            "space",
            "universe",
            "multiverse",
            "omniverse",
            "cosmos",
            "macrocosm",
            "metacosm",
            "hypercosm",
        ]
        inventory = {
            "phase": 61,
            "phase_name": "language surface audit / PooleOS reorientation",
            "language_stack_through_phase_60": stack,
            "required_source_map_node_kinds": ["ModuleDecl", "CapabilityDecl"],
            "semantic_root_fields_to_audit": ["capabilities", "services"],
        }
        diagnostics = {
            "phase": 65,
            "phase_name": "diagnostic hardening across all declaration kinds",
            "diagnostic_case_count": 466,
            "case_file_count": 55,
            "parse_diagnostic_code_count": 205,
            "semantic_diagnostic_code_count": 177,
            "lexer_diagnostic_code_count": 1,
            "stack_to_case_file": {name: f"{name}.json" for name in stack},
            "next_recommended_phase": "Phase 66 - Core IR boundary audit",
        }
        anchor = {
            "artifact_kind": "pooleos.pooleglyph_source_anchor",
            "status": "warn",
            "pooleglyph_path": str(pooleglyph),
            "git": {"commit": "f" * 40, "dirty_files": ["M tests/reports/conformance_report.json"]},
            "latest_checkpoint": {"checkpoint": "Phase 65 - diagnostic hardening across all declaration kinds"},
            "summary": {"dirty_file_count": 1, "failed_check_count": 0},
        }

        (package_root / "tests" / "language_surface_inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
        (package_root / "tests" / "diagnostic_hardening_manifest.json").write_text(json.dumps(diagnostics), encoding="utf-8")
        (package_root / "docs" / "POOLEGLYPH_V0_5_DEV_LANGUAGE_SPEC.md").write_text("# spec\n", encoding="utf-8")
        (package_root / "docs" / "POOLEGLYPH_V0_5_SPEC_SYNC_MATRIX.md").write_text(
            "# matrix\n\nMetadata-only boundary\n",
            encoding="utf-8",
        )
        (package_root / "docs" / "POOLEGLYPH_POOLEOS_REORIENTED_PLAN.md").write_text(
            "public-safe metadata-only bridge layer\n",
            encoding="utf-8",
        )
        anchor_path = tmp_path / "anchor.json"
        anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
        return anchor_path, pooleglyph

    def test_bridge_manifest_validates_and_preserves_warn_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_path, pooleglyph = self._make_fake_inputs(Path(tmp))
            manifest = pooleglyph_bridge_manifest.make_bridge_manifest(
                source_anchor_path=anchor_path,
                pooleglyph_path=pooleglyph,
            )
            schema = json.loads((ROOT / "specs" / "pooleglyph-bridge-manifest.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])
            self.assertEqual(manifest["status"], "warn")
            self.assertEqual(manifest["summary"]["failed_check_count"], 0)
            self.assertEqual(manifest["summary"]["bridge_map_count"], 6)
            self.assertEqual(manifest["diagnostic_summary"]["diagnostic_case_count"], 466)
            self.assertEqual(manifest["bridge_maps"]["capability_security"]["coverage"], "covered")
            self.assertEqual(manifest["core_ir_boundary"]["status"], "phase66_pending")
            self.assertFalse(manifest["core_ir_boundary"]["parser_to_kernel_promotion_allowed"])

    def test_cli_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_path, pooleglyph = self._make_fake_inputs(Path(tmp))
            out = Path(tmp) / "bridge.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pooleglyph_bridge_manifest.main(
                    ["--source-anchor", str(anchor_path), "--pooleglyph", str(pooleglyph), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            manifest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_kind"], "pooleos.pooleglyph_bridge_manifest")


if __name__ == "__main__":
    unittest.main()
