#!/usr/bin/env python3
"""Lock the designated PDC sources and index raw evidence candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pdc_source_intake  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the locked PDC source-intake artifact.")
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "pdc_source_intake.json")
    args = parser.parse_args(argv)

    try:
        artifact = pdc_source_intake.make_source_intake(
            workspace=ROOT,
            downloads=args.downloads,
            copy_files=True,
        )
    except pdc_source_intake.PdcSourceIntakeError as exc:
        print(f"FAIL pdc_source_intake: {exc}")
        return 1

    schema = json.loads((ROOT / "specs" / "pdc-source-intake.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(artifact, schema)
    if errors:
        for error in errors:
            print(f"FAIL pdc_source_intake {error.path}: {error.message}")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
