#!/usr/bin/env python3
"""Generate the byte-bound PooleOS native architecture baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ADR_NAMES = (
    "0001-native-pooleos-constitution.md",
    "0002-reuse-clean-room-and-publication-boundary.md",
    "0003-language-and-toolchain-split.md",
    "0004-product-names-and-version-namespaces.md",
    "0005-v1-scope-mission-threats-and-non-goals.md",
    "0006-tcb-and-component-placement.md",
    "0007-repository-governance-and-source-tree.md",
)
BOUND_SOURCE_PATHS = (
    "LICENSE",
    "docs/adr-ratification-ceremony.md",
    "docs/hardware-target-and-lab-safety.md",
    "docs/native-formal-models.md",
    "docs/native-boot-config.md",
    "docs/native-boot-handoff.md",
    "docs/native-pooleboot-proof.md",
    "docs/native-tier0-qemu.md",
    "docs/native-v1-objectives.md",
    "docs/n0-owner-decision-packet.md",
    "docs/n0-owner-response-receipt.md",
    "specs/pooleos-kernel-charter.md",
    "docs/production-goal-charter.md",
    "docs/pdc-production-build-plan.md",
    "docs/publication-boundary.md",
    "runs/pooleos_native_checklist_coverage.json",
    "runs/adr_ratification_readiness.json",
    "runs/hardware_target_readiness.json",
    "runs/native_model_readiness.json",
    "runs/native_boot_config_readiness.json",
    "runs/native_boot_handoff_readiness.json",
    "runs/native_pooleboot_readiness.json",
    "runs/n0_owner_decision_packet.json",
    "runs/n0_owner_response_receipt.json",
    "runs/native_tier0_readiness.json",
    "runs/native_v1_objectives_readiness.json",
    "runs/tier1_hardware_observation.json",
    "specs/adr-ratification-policy.json",
    "specs/hardware-support-policy.json",
    "specs/native-architecture-constitution.json",
    "specs/native-model-contract.json",
    "specs/native-model-toolchain-lock.json",
    "specs/native-boot-config-contract.json",
    "specs/native-boot-config-contract.schema.json",
    "specs/native-boot-config-golden-vectors.json",
    "specs/native-boot-config-golden-vectors.schema.json",
    "specs/native-boot-config-readiness.schema.json",
    "specs/native-boot-handoff-contract.json",
    "specs/native-boot-handoff-contract.schema.json",
    "specs/native-boot-handoff-golden-vectors.json",
    "specs/native-boot-handoff-golden-vectors.schema.json",
    "specs/native-boot-handoff-readiness.schema.json",
    "specs/native-pooleboot-proof.json",
    "specs/native-pooleboot-proof.schema.json",
    "specs/native-pooleboot-readiness.schema.json",
    "specs/native-tier0-lock.json",
    "specs/native-tier0-profile.json",
    "specs/native-v1-objectives.json",
    "specs/native-v1-objectives.schema.json",
    "specs/n0-owner-response.json",
    "specs/n0-owner-response-receipt.schema.json",
    "specs/n0-owner-response.schema.json",
    "specs/native-release-architecture-policy.json",
    "specs/native-standards-register.json",
    "specs/tier1-hardware-target.json",
)
HEADER_PATTERN = re.compile(r"^# ADR-(\d{4}): (.+)$")
FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z ]+):\s*(.*?)\s*$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _bind_file(root: Path, relative_path: str) -> dict[str, Any]:
    data = (root / relative_path).read_bytes()
    return {
        "path": relative_path,
        "sha256": _sha256(data),
        "byte_count": len(data),
        "line_count": len(data.decode("utf-8-sig").splitlines()),
    }


def _parse_adr(root: Path, name: str) -> dict[str, Any]:
    relative_path = f"docs/adr/{name}"
    path = root / relative_path
    data = path.read_bytes()
    lines = data.decode("utf-8-sig").splitlines()
    heading = HEADER_PATTERN.fullmatch(lines[0]) if lines else None
    if heading is None:
        raise ValueError(f"invalid ADR heading in {relative_path}")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.startswith("## "):
            break
        match = FIELD_PATTERN.fullmatch(line.rstrip())
        if match:
            fields[match.group(1).casefold().replace(" ", "_")] = match.group(2).strip()

    required = ("status", "date", "decision_owner", "ratification", "supersedes", "superseded_by", "requirement_mappings")
    missing = [field for field in required if field not in fields]
    if missing:
        raise ValueError(f"missing ADR header fields in {relative_path}: {', '.join(missing)}")
    return {
        "id": f"ADR-{heading.group(1)}",
        "title": heading.group(2),
        "path": relative_path,
        "status": fields["status"],
        "date": fields["date"],
        "decision_owner": fields["decision_owner"],
        "ratification": fields["ratification"],
        "supersedes": fields["supersedes"],
        "superseded_by": fields["superseded_by"],
        "requirement_mappings": [item.strip() for item in fields["requirement_mappings"].split(",")],
        "sha256": _sha256(data),
        "byte_count": len(data),
        "line_count": len(lines),
    }


def _git_value(root: Path, *args: str, fallback: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else fallback


def build_baseline(root: Path = ROOT) -> dict[str, Any]:
    constitution = json.loads((root / "specs/native-architecture-constitution.json").read_text(encoding="utf-8-sig"))
    adrs = [_parse_adr(root, name) for name in ADR_NAMES]
    status_counts = Counter(adr["status"] for adr in adrs)
    git_initialized = (root / ".git").exists()
    current_branch = constitution["repository"]["default_branch"] if git_initialized else "not_initialized"
    configured_remote = _git_value(root, "remote", "get-url", "origin", fallback="not_configured") if git_initialized else "not_configured"
    all_signed = bool(adrs) and all(adr["status"] == "accepted-signed" for adr in adrs)
    promotion_allowed = bool(constitution["ratification"]["production_promotion_allowed"] and all_signed)

    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_architecture_baseline",
        "status_date": constitution["status_date"],
        "status": "ratified" if promotion_allowed else "partial_owner_directed_signature_pending",
        "production_ready": False,
        "production_promotion_allowed": promotion_allowed,
        "owner": constitution["owner"],
        "repository": {
            "initialized": git_initialized,
            "current_branch": current_branch,
            "configured_remote": configured_remote,
            "expected_remote": constitution["repository"]["remote"],
            "default_branch": constitution["repository"]["default_branch"],
            "visibility": constitution["repository"]["visibility"],
            "publication_state": constitution["repository"]["local_source_control_status"],
        },
        "architecture": constitution["architecture"],
        "component_names": constitution["component_names"],
        "version_namespaces": constitution["version_namespaces"],
        "language_split": constitution["language_split"],
        "tcb_domains": constitution["tcb_domains"],
        "scope": constitution["scope"],
        "adr_summary": {
            "required_count": len(ADR_NAMES),
            "present_count": len(adrs),
            "accepted_owner_directed_count": status_counts["accepted-owner-directed"],
            "proposed_count": status_counts["proposed"],
            "accepted_signed_count": status_counts["accepted-signed"],
            "all_required_cryptographically_ratified": all_signed,
        },
        "adrs": adrs,
        "bound_sources": [_bind_file(root, path) for path in BOUND_SOURCE_PATHS],
        "primary_toolchain_references": [
            {
                "topic": "PooleBoot UEFI target",
                "url": "https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html",
                "authority": "official Rust compiler documentation",
            },
            {
                "topic": "PooleKernel freestanding x86-64 target",
                "url": "https://doc.rust-lang.org/rustc/platform-support/x86_64-unknown-none.html",
                "authority": "official Rust compiler documentation",
            },
            {
                "topic": "UEFI calling convention",
                "url": "https://doc.rust-lang.org/reference/items/external-blocks.html",
                "authority": "official Rust language reference",
            },
        ],
        "open_items": constitution["open_items"],
        "claim_boundary": {
            "owner_direction_is_not_a_cryptographic_signature": True,
            "architecture_baseline_is_not_a_bootable_system": True,
            "passing_release_tree_policy_is_not_n39_release_acceptance": True,
            "private_source_content_embedded": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "native_architecture_baseline.json")
    args = parser.parse_args(argv)
    try:
        baseline = build_baseline()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(baseline, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {args.out}: adrs={baseline['adr_summary']['present_count']} "
        f"signed={baseline['adr_summary']['accepted_signed_count']} status={baseline['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
