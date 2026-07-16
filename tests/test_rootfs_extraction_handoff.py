import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import rootfs_extraction_handoff  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_rootfs_extraction_handoff, pooleos_release_gate  # noqa: E402


def _write_rootfs_content_manifest(tmp_path: Path, *, image_exists: bool = True, status: str = "blocked", failed: int = 0) -> Path:
    image = tmp_path / "rootfs.ext4"
    if image_exists:
        image.write_text("fake rootfs image", encoding="utf-8")
    image_binding = tmp_path / "qemu_boot_marker_image_binding.json"
    image_binding.write_text('{"artifact_kind":"pooleos.qemu_boot_marker_image_binding"}\n', encoding="utf-8")
    extracted = tmp_path / "rootfs_extracted"
    manifest_path = tmp_path / "rootfs_content_manifest.json"
    manifest = {
        "schema_version": "0.1",
        "artifact_kind": "pooleos.rootfs_content_manifest",
        "status": status,
        "execution_performed": False,
        "rootfs_extraction_performed": False,
        "boot_evidence_claimed": False,
        "security_boundary_claimed": False,
        "source_inputs": {
            "image_binding_path": str(image_binding),
            "image_binding_status": "pass",
        },
        "rootfs_image": {
            "path": str(image),
            "exists": image_exists,
            "sha256": "a" * 64 if image_exists else "",
            "byte_count": image.stat().st_size if image_exists else 0,
        },
        "extracted_rootfs": {
            "path": str(extracted),
            "exists": False,
        },
        "content_file_bindings": [],
        "checks": [],
        "summary": {
            "failed_check_count": failed,
            "blocking_check_count": 1 if status == "blocked" else 0,
            "source_file_count": 5,
            "source_hashed_file_count": 5,
            "rootfs_file_count": 0,
            "matched_source_file_count": 0,
            "image_exists": image_exists,
            "image_sha256": "a" * 64 if image_exists else "",
            "extracted_rootfs_exists": False,
            "image_binding_status": "pass",
            "execution_performed": False,
            "rootfs_extraction_performed": False,
            "boot_evidence_claimed": False,
            "security_boundary_claimed": False,
        },
        "limitations": ["unit"],
        "next_steps": ["extract"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


class RootfsExtractionHandoffTests(unittest.TestCase):
    def test_handoff_blocks_when_rootfs_image_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _write_rootfs_content_manifest(tmp_path, image_exists=False)
            handoff = rootfs_extraction_handoff.make_rootfs_extraction_handoff(
                root=ROOT,
                rootfs_content_manifest_path=source,
                handoff_output_path=tmp_path / "handoff.json",
                note_output_path=tmp_path / "handoff.md",
            )
            schema = json.loads((ROOT / "specs" / "rootfs-extraction-handoff.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(handoff, schema), [])
            self.assertEqual(handoff["status"], "blocked")
            self.assertEqual(handoff["summary"]["failed_check_count"], 0)
            self.assertGreater(handoff["summary"]["blocking_check_count"], 0)
            self.assertFalse(handoff["execution_performed"])
            self.assertFalse(handoff["rootfs_extraction_performed"])

    def test_handoff_passes_with_existing_image_and_safe_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _write_rootfs_content_manifest(tmp_path, image_exists=True)
            handoff = rootfs_extraction_handoff.make_rootfs_extraction_handoff(
                root=ROOT,
                rootfs_content_manifest_path=source,
                handoff_output_path=tmp_path / "handoff.json",
                note_output_path=tmp_path / "handoff.md",
            )
            self.assertEqual(handoff["status"], "pass")
            self.assertEqual(handoff["summary"]["failed_check_count"], 0)
            self.assertEqual(handoff["summary"]["blocking_check_count"], 0)
            self.assertIn("mount -o ro,loop", handoff["bash_script"])
            self.assertIn("emit_rootfs_content_manifest.py", handoff["bash_script"])
            self.assertNotIn("rm -rf", handoff["bash_script"])
            self.assertNotIn("--delete", handoff["bash_script"])
            self.assertEqual(handoff["summary"]["command_count"], 7)
            markdown = rootfs_extraction_handoff.render_handoff_markdown(handoff)
            self.assertIn(handoff["bash_script_sha256"], markdown)
            self.assertIn("Codex did not execute", markdown)

    def test_handoff_fails_when_source_manifest_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _write_rootfs_content_manifest(tmp_path, image_exists=True, status="fail", failed=1)
            handoff = rootfs_extraction_handoff.make_rootfs_extraction_handoff(
                root=ROOT,
                rootfs_content_manifest_path=source,
            )
            self.assertEqual(handoff["status"], "fail")
            self.assertGreater(handoff["summary"]["failed_check_count"], 0)

    def test_cli_writes_note_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _write_rootfs_content_manifest(tmp_path, image_exists=True)
            note_out = tmp_path / "rootfs_extraction_handoff.md"
            out = tmp_path / "rootfs_extraction_handoff.json"
            with redirect_stdout(io.StringIO()):
                code = emit_rootfs_extraction_handoff.main(
                    [
                        "--rootfs-content-manifest",
                        str(source),
                        "--note-out",
                        str(note_out),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(note_out.exists())
            handoff = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(handoff["artifact_kind"], "pooleos.rootfs_extraction_handoff")
            self.assertEqual(handoff["status"], "pass")

    def test_release_gate_accepts_blocked_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = _write_rootfs_content_manifest(tmp_path, image_exists=False)
            out = tmp_path / "rootfs_extraction_handoff.json"
            handoff = rootfs_extraction_handoff.make_rootfs_extraction_handoff(
                root=ROOT,
                rootfs_content_manifest_path=source,
                handoff_output_path=out,
            )
            rootfs_extraction_handoff.write_handoff(handoff, out)
            check = pooleos_release_gate.check_rootfs_extraction_handoff(out)
            self.assertEqual(check["name"], "rootfs_extraction_handoff")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
