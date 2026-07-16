#!/usr/bin/env python3
"""Emit an operator handoff for read-only rootfs extraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import rootfs_extraction_handoff  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS rootfs extraction handoff.")
    parser.add_argument("--rootfs-content-manifest", type=Path, default=ROOT / "runs" / "rootfs_content_manifest.json")
    parser.add_argument("--rootfs-content-manifest-output", default=str(ROOT / "runs" / "rootfs_content_manifest.json"))
    parser.add_argument("--note-out", type=Path, default=ROOT / "runs" / "rootfs_extraction_handoff.md")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "rootfs_extraction_handoff.json")
    args = parser.parse_args(argv)

    handoff = rootfs_extraction_handoff.make_rootfs_extraction_handoff(
        root=ROOT,
        rootfs_content_manifest_path=args.rootfs_content_manifest,
        handoff_output_path=args.out,
        note_output_path=args.note_out,
        manifest_output_path=optional_path(args.rootfs_content_manifest_output),
    )
    schema = json.loads((ROOT / "specs" / "rootfs-extraction-handoff.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(handoff, schema)
    if errors:
        for error in errors:
            print(f"FAIL rootfs extraction handoff {error.path}: {error.message}")
        return 1
    rootfs_extraction_handoff.write_note(rootfs_extraction_handoff.render_handoff_markdown(handoff), args.note_out)
    rootfs_extraction_handoff.write_handoff(handoff, args.out)
    print(args.note_out)
    print(args.out)
    return 0 if handoff["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
