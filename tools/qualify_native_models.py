#!/usr/bin/env python3
"""Execute and qualify the frozen PooleOS N4 bounded TLC model slice."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_models  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=native_models.DEFAULT_TOOLCHAIN_ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / native_models.READINESS_RELATIVE)
    args = parser.parse_args(argv)
    try:
        readiness = native_models.build_readiness(args.toolchain_root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError, native_models.NativeModelError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 2
    native_models.write_json(readiness, args.out)
    summary = readiness["summary"]
    print(
        f"wrote {args.out}: models={summary['model_count']} safe={summary['safe_run_pass_count']}/{summary['safe_run_count']} "
        f"counterexamples={summary['hostile_counterexample_count']}/{summary['hostile_run_count']} "
        f"repeats={summary['repeat_match_count']}/{summary['run_case_count']} "
        f"negatives={summary['negative_control_pass_count']}/{summary['negative_control_count']} "
        "trace_cross_checks=0 n4_exit=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
