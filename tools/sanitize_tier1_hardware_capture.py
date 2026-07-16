#!/usr/bin/env python3
"""Sanitize a private read-only Tier-1 capture into a public observation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import hardware_target  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / hardware_target.OBSERVATION_RELATIVE)
    parser.add_argument("--status-date", default="2026-07-16")
    args = parser.parse_args(argv)
    if not args.capture.name.endswith(".private.json"):
        print("FAIL private capture filename must end with .private.json")
        return 2
    try:
        capture_bytes = args.capture.read_bytes()
        capture = json.loads(capture_bytes.decode("utf-8-sig"))
        if not isinstance(capture, dict):
            raise hardware_target.HardwareEvidenceError("capture root must be an object")
        observation = hardware_target.sanitize_capture(capture, capture_bytes, ROOT, status_date=args.status_date)
        schema = hardware_target.read_json(ROOT / hardware_target.OBSERVATION_SCHEMA_RELATIVE)
        errors = validate_json(observation, schema)
    except (OSError, UnicodeError, json.JSONDecodeError, hardware_target.HardwareEvidenceError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    if errors:
        for error in errors:
            print(f"FAIL tier1_hardware_observation {error.path}: {error.message}")
        return 1
    hardware_target.write_json(observation, args.out)
    print(
        f"wrote {args.out}: facts={len(observation['facts'])} "
        f"channels={len(observation['evidence_channels'])} privacy_violations=0 promotion=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
