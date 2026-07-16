#!/usr/bin/env python3
"""Emit a human-facing host prep note and matching JSON manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import host_prep_note  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS host preparation note.")
    parser.add_argument("--operator-action", type=Path, required=True)
    parser.add_argument("--operator-receipt", type=Path, required=True)
    parser.add_argument("--note-out", type=Path, default=ROOT / "runs" / "host_prep_note.md")
    parser.add_argument("--manifest-out", type=Path, default=ROOT / "runs" / "host_prep_note.json")
    args = parser.parse_args(argv)

    manifest = host_prep_note.make_host_prep_note_manifest(
        operator_action_path=args.operator_action,
        operator_receipt_path=args.operator_receipt,
        note_path=args.note_out,
    )
    schema = json.loads((ROOT / "specs" / "host-prep-note.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL host_prep_note {error.path}: {error.message}")
        return 1

    host_prep_note.write_note(host_prep_note.render_host_prep_markdown(manifest), args.note_out)
    host_prep_note.write_manifest(manifest, args.manifest_out)
    print(args.note_out)
    print(args.manifest_out)
    return 0 if manifest["status"] != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
