"""Static microkernel isolation spike for PooleOS region/capability checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.microkernel_isolation_spike"
POLICY_VERSION = "0.1"


DEFAULT_COMPARTMENTS: list[dict[str, Any]] = [
    {
        "id": "pgvm_guest",
        "trust_level": "untrusted",
        "role": "Runs PGB1/PGB2 candidate programs without direct artifact or host authority.",
        "owns": ["guest_instruction_stream", "guest_register_view"],
    },
    {
        "id": "geometry_kernel",
        "trust_level": "trusted",
        "role": "Owns staged lattice updates, support counts, typed channel telemetry, and traps.",
        "owns": ["lattice_state", "support_counts", "staged_updates", "channel_buffer", "trace_events"],
    },
    {
        "id": "provenance_service",
        "trust_level": "trusted",
        "role": "Owns claim lanes, source hashes, artifact manifests, and replay proof records.",
        "owns": ["claim_lane_records", "artifact_hashes", "release_manifests"],
    },
    {
        "id": "signed_metric_service",
        "trust_level": "restricted",
        "role": "Computes signed-state benchmark descriptors from mediated geometry projections.",
        "owns": ["signed_projection_inputs", "benchmark_descriptors"],
    },
    {
        "id": "operator_shell",
        "trust_level": "operator",
        "role": "Boot, diagnostics, and explicitly approved host-preparation workflow surface.",
        "owns": ["operator_commands", "boot_diagnostics"],
    },
    {
        "id": "host_bridge",
        "trust_level": "untrusted",
        "role": "External Buildroot/QEMU and host integration surface; never owns kernel state.",
        "owns": ["host_paths", "qemu_invocation_records"],
    },
]


DEFAULT_CHANNELS: list[dict[str, Any]] = [
    {
        "source": "operator_shell",
        "target": "geometry_kernel",
        "capability": "load_program",
        "direction": "request",
        "purpose": "Load a bounded PooleGlyph/PGB program into the mediated execution surface.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "pgvm_guest",
        "target": "geometry_kernel",
        "capability": "invoke_rule",
        "direction": "request",
        "purpose": "Ask the geometry kernel to apply a local rule under staged-write semantics.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "geometry_kernel",
        "target": "pgvm_guest",
        "capability": "return_trap_or_state",
        "direction": "reply",
        "purpose": "Return bounded execution state or trap status to the guest program.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "geometry_kernel",
        "target": "provenance_service",
        "capability": "append_trace_hash",
        "direction": "append",
        "purpose": "Append trace and source hashes after geometry execution completes.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "geometry_kernel",
        "target": "signed_metric_service",
        "capability": "submit_projection",
        "direction": "append",
        "purpose": "Submit a bounded projection for signed-state benchmark descriptor computation.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "signed_metric_service",
        "target": "provenance_service",
        "capability": "append_benchmark_record",
        "direction": "append",
        "purpose": "Attach signed metric descriptors with benchmark-lane limitations.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "operator_shell",
        "target": "provenance_service",
        "capability": "read_manifest",
        "direction": "read",
        "purpose": "Inspect release-gate, replay, and host-prep evidence without mutating it.",
        "allowed": True,
        "requires_mediation": True,
    },
    {
        "source": "host_bridge",
        "target": "operator_shell",
        "capability": "provide_boot_artifact",
        "direction": "request",
        "purpose": "Present external Buildroot/QEMU paths for operator-mediated validation.",
        "allowed": True,
        "requires_mediation": True,
    },
]


DEFAULT_DENIED_CHANNELS: list[dict[str, str]] = [
    {
        "source": "pgvm_guest",
        "target": "provenance_service",
        "capability": "write_claim_lane",
        "reason": "Guest code cannot directly write theorem, verifier, benchmark, atlas, or bridge-open records.",
    },
    {
        "source": "pgvm_guest",
        "target": "signed_metric_service",
        "capability": "set_benchmark_result",
        "reason": "Guest code cannot directly set signed membrane metrics or benchmark summaries.",
    },
    {
        "source": "host_bridge",
        "target": "geometry_kernel",
        "capability": "mutate_lattice_state",
        "reason": "Host integration cannot mutate lattice state or staged writes.",
    },
    {
        "source": "signed_metric_service",
        "target": "geometry_kernel",
        "capability": "mutate_region",
        "reason": "Benchmark descriptor service receives projections but cannot feed state changes back into geometry execution.",
    },
    {
        "source": "provenance_service",
        "target": "geometry_kernel",
        "capability": "rewrite_trace",
        "reason": "Provenance records can append hashes and manifests but cannot rewrite kernel trace events.",
    },
]


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _edge(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("source", "")), str(record.get("target", "")), str(record.get("capability", "")))


def make_default_policy() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "fail",
        "policy_version": POLICY_VERSION,
        "kernel_surface": "PGVM2.Rg region/capability map",
        "security_boundary_claimed": False,
        "source_basis": [
            "specs/pooleos-kernel-charter.md: PGVM2 Rg region/capability map",
            "specs/pooleos-kernel-charter.md: Deep Kernel Fix Tracks item 4",
            "specs/pgb2-draft.md: region/capability trap behavior requirement",
        ],
        "compartments": [dict(compartment) for compartment in DEFAULT_COMPARTMENTS],
        "channels": [dict(channel) for channel in DEFAULT_CHANNELS],
        "denied_channels": [dict(channel) for channel in DEFAULT_DENIED_CHANNELS],
        "checks": [],
        "summary": {
            "compartment_count": 0,
            "allowed_channel_count": 0,
            "denied_channel_count": 0,
            "failed_check_count": 0,
        },
        "limitations": [
            "Static policy spike only; it is not an enforced hardware, OS, or production security boundary.",
            "Does not prove memory isolation, scheduler isolation, timing behavior, side-channel resistance, or host integrity.",
            "Intended to make region/capability assumptions explicit before a bootable or native kernel substrate exists.",
        ],
        "next_steps": [
            "Bind this static policy to PGB2 region/capability opcodes and trap behavior.",
            "Add dynamic negative tests that attempt denied guest and host mutations.",
            "Re-run the proof inside the PooleOS Lab image after QEMU boot evidence exists.",
        ],
    }


def evaluate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    compartments = policy.get("compartments", [])
    channels = policy.get("channels", [])
    denied_channels = policy.get("denied_channels", [])

    ids = [str(compartment.get("id", "")) for compartment in compartments]
    id_set = set(ids)
    allowed_edges = {_edge(channel) for channel in DEFAULT_CHANNELS}
    channel_edges = {_edge(channel) for channel in channels}
    denied_edges = {_edge(channel) for channel in denied_channels}
    endpoint_edges = [*channels, *denied_channels]
    missing_endpoints = sorted(
        {
            endpoint
            for edge_record in endpoint_edges
            for endpoint in (str(edge_record.get("source", "")), str(edge_record.get("target", "")))
            if endpoint not in id_set
        }
    )
    unknown_allowed_edges = sorted(channel_edges.difference(allowed_edges))
    denied_allowed_overlap = sorted(denied_edges.intersection(channel_edges))
    guest_direct_writes = sorted(
        edge
        for edge in channel_edges
        if edge[0] == "pgvm_guest"
        and edge[1] in {"provenance_service", "signed_metric_service"}
        and edge[2] not in {"read_manifest"}
    )
    host_kernel_mutations = sorted(
        edge
        for edge in channel_edges
        if edge[0] == "host_bridge" and edge[1] == "geometry_kernel"
    )
    unmediated_channels = sorted(
        _edge(channel)
        for channel in channels
        if channel.get("requires_mediation") is not True
    )
    channels_marked_denied = sorted(_edge(channel) for channel in channels if channel.get("allowed") is not True)

    checks = [
        _check(
            "unique_compartment_ids",
            len(ids) == len(id_set) and all(ids),
            f"compartments={len(ids)}; unique={len(id_set)}",
        ),
        _check(
            "channel_endpoints_exist",
            not missing_endpoints,
            "all endpoints known" if not missing_endpoints else f"missing={missing_endpoints}",
        ),
        _check(
            "allowed_channels_match_policy_table",
            not unknown_allowed_edges,
            "all allowed channels are in the policy table" if not unknown_allowed_edges else f"unknown={unknown_allowed_edges}",
        ),
        _check(
            "declared_denials_are_not_allowed",
            not denied_allowed_overlap,
            "denied channels do not overlap allowed channels" if not denied_allowed_overlap else f"overlap={denied_allowed_overlap}",
        ),
        _check(
            "guest_has_no_direct_provenance_or_metric_write",
            not guest_direct_writes,
            "guest writes must pass through geometry kernel mediation" if not guest_direct_writes else f"bad={guest_direct_writes}",
        ),
        _check(
            "host_bridge_cannot_mutate_geometry_kernel",
            not host_kernel_mutations,
            "host bridge has no direct geometry-kernel channel" if not host_kernel_mutations else f"bad={host_kernel_mutations}",
        ),
        _check(
            "all_allowed_channels_require_mediation",
            not unmediated_channels,
            "all allowed channels require mediation" if not unmediated_channels else f"unmediated={unmediated_channels}",
        ),
        _check(
            "channels_are_marked_allowed",
            not channels_marked_denied,
            "all entries in channels are allowed edges" if not channels_marked_denied else f"bad={channels_marked_denied}",
        ),
        _check(
            "security_boundary_not_claimed",
            policy.get("security_boundary_claimed") is False,
            f"security_boundary_claimed={policy.get('security_boundary_claimed')}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    evaluated = dict(policy)
    evaluated["checks"] = checks
    evaluated["status"] = "pass" if not failed else "fail"
    evaluated["summary"] = {
        "compartment_count": len(compartments),
        "allowed_channel_count": len(channels),
        "denied_channel_count": len(denied_channels),
        "failed_check_count": len(failed),
    }
    return evaluated


def make_isolation_proof() -> dict[str, Any]:
    return evaluate_policy(make_default_policy())


def write_proof(proof: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
