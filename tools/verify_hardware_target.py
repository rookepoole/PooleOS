#!/usr/bin/env python3
"""Verify checked-in Tier-1 hardware evidence and exact readiness reproduction."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import hardware_target  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main() -> int:
    try:
        expected = hardware_target.read_json(ROOT / hardware_target.READINESS_RELATIVE)
        rebuilt = hardware_target.build_readiness(ROOT)
        schema = hardware_target.read_json(ROOT / hardware_target.READINESS_SCHEMA_RELATIVE)
        errors = validate_json(expected, schema)
    except (OSError, ValueError, KeyError, hardware_target.HardwareEvidenceError) as error:
        print(f"HARDWARE_TARGET FAIL {type(error).__name__}: {error}")
        return 1
    if errors:
        for error in errors:
            print(f"HARDWARE_TARGET FAIL {error.path}: {error.message}")
        return 1
    if hardware_target.canonical_json_bytes(expected) != hardware_target.canonical_json_bytes(rebuilt):
        print("HARDWARE_TARGET FAIL checked readiness does not reproduce from public inputs")
        return 1
    summary = expected["summary"]
    if not summary["consistency_pass"] or expected["production_promotion_allowed"]:
        print("HARDWARE_TARGET FAIL bounded consistency or claim boundary is invalid")
        return 1
    print(
        "HARDWARE_TARGET PASS "
        f"checks={summary['matched_required_target_check_count']}/{summary['required_target_check_count']} "
        f"privacy={summary['privacy_violation_count']} n2_exit={str(expected['n2_exit_gate_satisfied']).lower()} "
        "production_ready=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
