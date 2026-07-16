#!/usr/bin/env python3
"""Generate the deterministic non-promoting PooleOS v1 objectives ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_v1_objectives  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / native_v1_objectives.READINESS_RELATIVE)
    args = parser.parse_args(argv)
    try:
        readiness = native_v1_objectives.build_readiness(ROOT)
        schema = json.loads(
            (ROOT / native_v1_objectives.READINESS_SCHEMA_RELATIVE).read_text(encoding="utf-8")
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, native_v1_objectives.ObjectivesError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    errors = validate_json(readiness, schema)
    if errors:
        for error in errors:
            print(f"FAIL native_v1_objectives_readiness {error.path}: {error.message}")
        return 1
    native_v1_objectives.write_json(readiness, args.out)
    summary = readiness["summary"]
    print(
        f"wrote {args.out}: status={readiness['status']} targets={summary['target_count']} "
        f"measured={summary['measured_target_count']} negatives={summary['negative_control_pass_count']}/10 "
        "promotion=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
