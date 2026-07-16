#!/usr/bin/env python3
"""Generate the deterministic public Tier-1 hardware readiness ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import hardware_target  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / hardware_target.READINESS_RELATIVE)
    args = parser.parse_args(argv)
    try:
        readiness = hardware_target.build_readiness(ROOT)
        schema = hardware_target.read_json(ROOT / hardware_target.READINESS_SCHEMA_RELATIVE)
        errors = validate_json(readiness, schema)
    except (OSError, ValueError, KeyError, hardware_target.HardwareEvidenceError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    if errors:
        for error in errors:
            print(f"FAIL hardware_target_readiness {error.path}: {error.message}")
        return 1
    hardware_target.write_json(readiness, args.out)
    summary = readiness["summary"]
    print(
        f"wrote {args.out}: status={readiness['status']} "
        f"target_checks={summary['matched_required_target_check_count']}/{summary['required_target_check_count']} "
        f"pending_channels={summary['pending_evidence_channel_count']} "
        f"pending_safety={summary['pending_lab_safety_count']} promotion=false"
    )
    return 0 if summary["consistency_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
