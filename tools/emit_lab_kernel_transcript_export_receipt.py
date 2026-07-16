#!/usr/bin/env python3
"""Emit a receipt for lab kernel transcript contract exports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import lab_kernel_transcript_export_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402


DEFAULT_CONTRACT_SOURCE = (
    ROOT
    / "lab-os"
    / "buildroot"
    / "external"
    / "board"
    / "pooleos_lab"
    / "rootfs_overlay"
    / "usr"
    / "bin"
    / "pooleos-kernel-pgvm2-transcript-contract"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a PooleOS lab kernel transcript export receipt.")
    parser.add_argument("--contract-source", type=Path, default=DEFAULT_CONTRACT_SOURCE)
    parser.add_argument("--transcript", type=Path, default=ROOT / "runs" / "kernel_pgvm2_loader.transcript.txt")
    parser.add_argument("--kernel-loader-output", type=Path, default=ROOT / "runs" / "kernel_pgvm2_loader_output.json")
    parser.add_argument("--contract-run-recorded", action="store_true")
    parser.add_argument("--contract-mode", choices=["auto", "disabled", "enabled"], default="auto")
    parser.add_argument("--operator-notes", default="")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "lab_kernel_transcript_export_receipt.json")
    args = parser.parse_args(argv)

    receipt = lab_kernel_transcript_export_receipt.make_lab_kernel_transcript_export_receipt(
        contract_source_path=args.contract_source,
        transcript_path=args.transcript,
        kernel_loader_output_path=args.kernel_loader_output,
        contract_run_recorded=args.contract_run_recorded,
        contract_mode=args.contract_mode,
        operator_notes=args.operator_notes,
    )
    schema = json.loads((ROOT / "specs" / "lab-kernel-transcript-export-receipt.schema.json").read_text(encoding="utf-8"))
    errors = validate_json(receipt, schema)
    if errors:
        for error in errors:
            print(f"FAIL lab kernel transcript export receipt {error.path}: {error.message}")
        return 1
    lab_kernel_transcript_export_receipt.write_receipt(receipt, args.out)
    print(args.out)
    return 0 if receipt["status"] in {"pending_contract_run", "disabled_verified", "enabled_verified"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
