#!/usr/bin/env python3
"""Emit a PooleGlyph source anchor for tandem PooleOS development."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from runtime import pooleglyph_source_anchor  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleGlyph source anchor artifact.")
    parser.add_argument(
        "--pooleglyph",
        type=Path,
        default=pooleglyph_source_anchor.default_pooleglyph_path(workspace_root=WORK_ROOT),
    )
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pooleglyph_source_anchor.json")
    args = parser.parse_args(argv)

    anchor = pooleglyph_source_anchor.make_source_anchor(pooleglyph_path=args.pooleglyph)
    schema = json.loads((ROOT / "specs" / "pooleglyph-source-anchor.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(anchor, schema)
    if errors:
        for error in errors:
            print(f"FAIL pooleglyph_source_anchor {error.path}: {error.message}")
        return 1
    pooleglyph_source_anchor.write_anchor(anchor, args.out)
    print(args.out)
    return 0 if anchor["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
