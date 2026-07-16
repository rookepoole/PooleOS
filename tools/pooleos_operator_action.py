#!/usr/bin/env python3
"""Emit PooleOS operator action request artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import operator_action  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS operator action request.")
    parser.add_argument("--wsl-prerequisites", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "operator_action_request.json")
    args = parser.parse_args(argv)

    request = operator_action.make_wsl_package_install_request(prerequisites_path=args.wsl_prerequisites)
    schema = json.loads((ROOT / "specs" / "operator-action-request.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(request, schema)
    if errors:
        for error in errors:
            print(f"FAIL operator_action {error.path}: {error.message}")
        return 1
    operator_action.write_request(request, args.out)
    print(args.out)
    return 0 if request["status"] != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
