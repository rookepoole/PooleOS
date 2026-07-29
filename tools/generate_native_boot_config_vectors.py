#!/usr/bin/env python3
"""Generate the canonical PBC1 contract and golden vectors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_boot_config as pbc1  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-out", type=Path, default=ROOT / pbc1.CONTRACT_RELATIVE)
    parser.add_argument("--vectors-out", type=Path, default=ROOT / pbc1.GOLDEN_RELATIVE)
    args = parser.parse_args()
    pbc1.write_json(pbc1.expected_contract(), args.contract_out)
    pbc1.write_json(pbc1.make_golden_vectors(), args.vectors_out)
    print(f"wrote {args.contract_out}")
    print(f"wrote {args.vectors_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
