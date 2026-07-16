#!/usr/bin/env python3
"""Verify the committed PooleOS v1 objectives and deterministic readiness ledger."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_v1_objectives  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main() -> int:
    try:
        objectives = native_v1_objectives.read_json(ROOT / native_v1_objectives.OBJECTIVES_RELATIVE)
        readiness_path = ROOT / native_v1_objectives.READINESS_RELATIVE
        readiness = native_v1_objectives.read_json(readiness_path)
        expected = native_v1_objectives.build_readiness(ROOT)
        schema = native_v1_objectives.read_json(ROOT / native_v1_objectives.READINESS_SCHEMA_RELATIVE)
        errors = validate_json(readiness, schema)
        failures = native_v1_objectives.rejection_reasons(objectives, ROOT)
        if failures:
            raise native_v1_objectives.ObjectivesError("; ".join(failures))
        if errors:
            raise native_v1_objectives.ObjectivesError(
                "; ".join(f"{error.path}: {error.message}" for error in errors)
            )
        if readiness_path.read_bytes() != native_v1_objectives.canonical_json_bytes(expected):
            raise native_v1_objectives.ObjectivesError("readiness ledger does not reproduce exactly")
        if not readiness["owner_boundary"]["profile_accepted"] or readiness["production_promotion_allowed"]:
            raise native_v1_objectives.ObjectivesError("objectives omit owner direction or overclaim production promotion")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, native_v1_objectives.ObjectivesError) as error:
        print(f"NATIVE_V1_OBJECTIVES FAIL {type(error).__name__}: {error}")
        return 1
    summary = readiness["summary"]
    print(
        f"NATIVE_V1_OBJECTIVES PASS targets={summary['target_count']} measured=0 "
        f"negatives={summary['negative_control_pass_count']}/10 owner_direction=true signature=false production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
