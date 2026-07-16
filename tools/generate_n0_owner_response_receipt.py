#!/usr/bin/env python3
"""Validate the completed N0 owner response and emit its non-promoting receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import n0_owner_response  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", type=Path, default=ROOT / n0_owner_response.RECEIPT_RELATIVE)
    parser.add_argument("--out-markdown", type=Path, default=ROOT / n0_owner_response.RECEIPT_DOCUMENT_RELATIVE)
    args = parser.parse_args(argv)
    try:
        receipt = n0_owner_response.build_receipt(ROOT)
        n0_owner_response.write_receipt(receipt, args.out_json, args.out_markdown)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    validation = receipt["validation"]
    print(
        f"wrote {args.out_json} and {args.out_markdown}: "
        f"status={receipt['status']} "
        f"negatives={validation['negative_control_pass_count']}/{validation['negative_control_count']} "
        "measurements=0 signers=0 key_generation=false signing=false merge=false tagging=false publication=false promotion=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
