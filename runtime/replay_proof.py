"""Deterministic replay proof records for PooleOS bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import pgb2_bundle as pgb2
from .channel_trace import make_claim_record, summary_to_json


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.replay_proof"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bundle_section_hashes(bundle: dict[str, Any]) -> dict[str, str]:
    return {section["name"]: section["sha256"] for section in bundle.get("sections", [])}


def make_replay_proof(
    *,
    case: str,
    bundle_path: Path,
    bundle: dict[str, Any],
    pgvm_report: dict[str, Any],
    recomputed_channel_summary: dict[str, Any],
) -> dict[str, Any]:
    trace_summary = pgb2.section_by_name(bundle, "TRACE")["body"]["summary"]
    channel_summary_match = trace_summary == recomputed_channel_summary
    signed_present = any(section.get("name") == "SIGNED_METRICS" for section in bundle.get("sections", []))
    claim = make_claim_record(
        claim_id="REPLAY-001",
        title=f"Replay proof for {case}",
        claim_lane="verifier",
        evidence_kind="trace",
        rule="B5-7/S5-9",
        model_tag="raw",
        source_descriptor=f"bundle:{bundle_path.name}:{case}",
        limitations="Replay proof covers the declared reference case only; it is not a production safety claim.",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "case": case,
        "bundle_sha256": file_sha256(bundle_path),
        "sections": bundle_section_hashes(bundle),
        "pgvm_report": {
            "halted": bool(pgvm_report.get("halted")),
            "trap": str(pgvm_report.get("trap") or ""),
            "final_body_count": int(pgvm_report.get("final_body_count", 0)),
            "instruction_count": int(pgvm_report.get("instruction_count", 0)),
        },
        "channel_summary_match": channel_summary_match,
        "signed_metrics_present": signed_present,
        "claim": claim,
    }


def write_replay_proof(proof: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def recomputed_summary_json(summary: Any) -> dict[str, Any]:
    return summary_to_json(summary)

