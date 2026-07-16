#!/usr/bin/env python3
"""Verify detached ADR acceptance, signed tag, and optional remote publication."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import adr_ratification  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / adr_ratification.MANIFEST_RELATIVE)
    parser.add_argument("--signature", type=Path, default=ROOT / adr_ratification.SIGNATURE_RELATIVE)
    parser.add_argument("--verify-remote", action="store_true")
    parser.add_argument("--allow-publication-pending", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / adr_ratification.RECEIPT_RELATIVE)
    args = parser.parse_args(argv)
    try:
        receipt = adr_ratification.build_receipt(
            ROOT,
            manifest_path=args.manifest,
            signature_path=args.signature,
            verify_remote=args.verify_remote,
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    adr_ratification.write_json(receipt, args.out)
    print(
        f"wrote {args.out}: status={receipt['status']} "
        f"detached={str(receipt['detached_signature']['verified']).lower()} "
        f"tag={str(receipt['signed_tag']['signature_verified']).lower()} "
        f"remote={str(receipt['remote_publication']['published']).lower()} "
        f"promotion={str(receipt['production_promotion_allowed']).lower()}"
    )
    if receipt["status"] == "verified":
        return 0
    if args.allow_publication_pending and receipt["status"] in {
        "detached_signature_verified_tag_pending",
        "local_tag_verified_publication_pending",
    }:
        return 0
    return 2 if receipt["status"] == "pending_owner_action" else 1


if __name__ == "__main__":
    raise SystemExit(main())
