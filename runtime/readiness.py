"""Release-readiness report helpers for PooleOS."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPORT_VERSION = "0.1"
REPORT_KIND = "pooleos.readiness_report"


def make_check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def make_readiness_report(
    *,
    checks: list[dict[str, Any]],
    artifacts: list[str],
    remaining_gaps: list[str] | None = None,
) -> dict[str, Any]:
    failed = [check for check in checks if not check.get("ok")]
    gaps = remaining_gaps or []
    return {
        "schema_version": REPORT_VERSION,
        "artifact_kind": REPORT_KIND,
        "created_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "pass" if not failed else "fail",
        "production_ready": False,
        "production_ready_reason": "Native PooleOS remains in architecture and kernel-bootstrap development; consistency gates track evidence but do not satisfy the N0-N39 production contract.",
        "summary": {
            "total_checks": len(checks),
            "failed_checks": len(failed),
            "artifact_count": len(artifacts),
            "remaining_gap_count": len(gaps),
        },
        "checks": checks,
        "artifacts": artifacts,
        "remaining_gaps": gaps,
    }


def write_readiness_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
