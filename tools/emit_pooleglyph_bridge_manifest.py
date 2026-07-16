#!/usr/bin/env python3
"""Emit a PooleGlyph-to-PooleOS bridge manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_bridge_manifest  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleGlyph bridge manifest for PooleOS.")
    parser.add_argument("--source-anchor", type=Path, required=True)
    parser.add_argument("--pooleglyph", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pooleglyph_bridge_manifest.json")
    args = parser.parse_args(argv)

    manifest = pooleglyph_bridge_manifest.make_bridge_manifest(
        source_anchor_path=args.source_anchor,
        pooleglyph_path=args.pooleglyph,
    )
    schema = json.loads((ROOT / "specs" / "pooleglyph-bridge-manifest.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL pooleglyph_bridge_manifest {error.path}: {error.message}")
        return 1
    pooleglyph_bridge_manifest.write_bridge_manifest(manifest, args.out)
    print(args.out)
    return 0 if manifest["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
