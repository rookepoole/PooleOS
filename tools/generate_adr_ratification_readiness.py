#!/usr/bin/env python3
"""Generate the deterministic, non-promoting PooleOS ADR readiness ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import adr_ratification  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / adr_ratification.READINESS_RELATIVE)
    args = parser.parse_args(argv)
    try:
        readiness = adr_ratification.build_readiness(ROOT)
        schema = json.loads((ROOT / adr_ratification.READINESS_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    errors = validate_json(readiness, schema)
    if errors:
        for error in errors:
            print(f"FAIL adr_ratification_readiness {error.path}: {error.message}")
        return 1
    adr_ratification.write_json(readiness, args.out)
    summary = readiness["summary"]
    print(
        f"wrote {args.out}: status={readiness['status']} adrs={readiness['adr_set']['present_count']} "
        f"trusted_signers={readiness['trust_bootstrap']['trusted_signer_count']} "
        f"owner_actions={summary['blocking_owner_action_count']} promotion=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
