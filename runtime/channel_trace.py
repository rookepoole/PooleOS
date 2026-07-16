"""PooleOS channel trace artifact helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .channel_telemetry import (
    BASE_BIRTH_WINDOW,
    BASE_SURVIVAL_WINDOW,
    ChannelEvent,
    ChannelSummary,
)


TRACE_SCHEMA_VERSION = "0.1"
TRACE_KIND = "pooleos.channel_trace"


def stable_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def event_to_json(event: ChannelEvent) -> dict[str, Any]:
    return {
        "coord": list(event.coord),
        "previous_state": event.previous_state,
        "active_previous_state": event.active_previous_state,
        "support_count": event.support_count,
        "raw_channel": event.raw_channel,
        "accepted": event.accepted,
        "next_state": event.next_state,
        "psi": event.psi,
    }


def summary_to_json(summary: ChannelSummary) -> dict[str, Any]:
    return {
        "event_count": len(summary.events),
        "counts": dict(sorted(summary.counts.items())),
        "accepted_counts": dict(sorted(summary.accepted_counts().items())),
        "births": summary.births,
        "survivors": summary.survivors,
        "deaths": summary.deaths,
        "void_stays": summary.void_stays,
        "psi_total": summary.psi_total,
    }


def make_claim_record(
    *,
    claim_id: str,
    title: str,
    owner: str = "Rooke Poole",
    claim_lane: str = "verifier",
    evidence_kind: str = "trace",
    rule: str = "B5-7/S5-9",
    model_tag: str = "raw",
    source_descriptor: str,
    limitations: str,
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "title": title,
        "owner": owner,
        "claim_lane": claim_lane,
        "evidence_kind": evidence_kind,
        "rule": rule,
        "model_tag": model_tag,
        "source_hash": stable_hash(source_descriptor),
        "inputs": [source_descriptor],
        "outputs": [TRACE_KIND],
        "limitations": limitations,
        "created_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def make_channel_trace(
    summary: ChannelSummary,
    *,
    claim: dict[str, Any],
    birth_window: tuple[int, int] = BASE_BIRTH_WINDOW,
    survival_window: tuple[int, int] = BASE_SURVIVAL_WINDOW,
) -> dict[str, Any]:
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "artifact_kind": TRACE_KIND,
        "rule": {
            "birth": list(birth_window),
            "survival": list(survival_window),
            "neighborhood": "3D_MOORE_N26",
        },
        "claim": claim,
        "summary": summary_to_json(summary),
        "events": [event_to_json(event) for event in summary.events],
    }


def write_channel_trace(trace: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")

