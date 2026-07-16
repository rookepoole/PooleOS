#!/usr/bin/env python3
"""Prepare canonical PooleOS ADR bytes after explicit owner acceptance."""

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
    parser.add_argument(
        "--owner-accept-all-exact",
        action="store_true",
        help="Record explicit intent to accept all seven exact ADR bindings. This flag is not a signature.",
    )
    parser.add_argument(
        "--owner-accept-objectives-exact",
        action="store_true",
        help="Record explicit intent to accept the exact candidate v1 profile and all 38 target values as definitions. This flag accepts no measurement evidence and is not a signature.",
    )
    parser.add_argument(
        "--accept-software-key-risk",
        action="store_true",
        help="Explicit owner acceptance for the lower-assurance provisional ssh-ed25519 profile.",
    )
    parser.add_argument("--out", type=Path, default=ROOT / adr_ratification.MANIFEST_RELATIVE)
    args = parser.parse_args(argv)
    try:
        manifest = adr_ratification.build_manifest(
            ROOT,
            owner_accept_all_exact=args.owner_accept_all_exact,
            owner_accept_objectives_exact=args.owner_accept_objectives_exact,
            accept_software_key_risk=args.accept_software_key_risk,
        )
        schema = json.loads((ROOT / adr_ratification.MANIFEST_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    errors = validate_json(manifest, schema)
    if errors:
        for error in errors:
            print(f"FAIL adr_ratification_manifest {error.path}: {error.message}")
        return 1
    adr_ratification.write_json(manifest, args.out)
    print(
        f"wrote {args.out}: adrs={manifest['owner_acceptance']['accepted_exact_count']} "
        f"objectives={manifest['objectives_acceptance']['target_count']} "
        f"fingerprint={manifest['signer']['public_key_fingerprint']} unsigned=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
