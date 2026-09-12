"""Shared provenance checks for native execution-profile receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime import native_kernel_entry


def kernel_entry_errors(build: Any, root: Path) -> list[str]:
    if not isinstance(build, dict) or not isinstance(build.get("kernel_entry"), dict):
        return ["embedded kernel entry evidence is missing or malformed"]
    try:
        current = native_kernel_entry.read_json(root / native_kernel_entry.READINESS_RELATIVE)
        issues = native_kernel_entry.readiness_errors(current, root)
        if issues:
            return ["embedded kernel entry dependency is invalid: " + "; ".join(issues)]
        # JSON identity also rejects bool/int and float/int equality substitutions.
        embedded_json = json.dumps(build["kernel_entry"], sort_keys=True, allow_nan=False)
        current_json = json.dumps(current, sort_keys=True, allow_nan=False)
        if embedded_json != current_json:
            return ["embedded kernel entry evidence differs from the current validated receipt"]
        return []
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return [f"embedded kernel entry dependency cannot be validated: {type(error).__name__}"]
