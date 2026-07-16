"""Content-addressed intake for the designated PDC authorities and raw candidate index."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


RAW_EXTENSIONS = {".zip", ".py", ".csv", ".json"}
RAW_NAME_PATTERN = re.compile(
    r"^(pdc_bench_|poole_signed_reaction|poole_qp|poole.*local.*geometry|.*defect.*calculus|.*bridge.*benchmark)",
    re.IGNORECASE,
)


class PdcSourceIntakeError(RuntimeError):
    """Raised when a designated source cannot be locked exactly."""


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    filename: str
    kind: str
    expected_sha256: str
    claim_role: str


DESIGNATED_SOURCES = (
    SourceDefinition(
        "SRC-TAX-1",
        "PooleTaxOptimizer_INTERNAL_TECHNICAL_IMPLEMENTATION_v1_0_0.md",
        "markdown",
        "AC76CC589925CE1BF1EF8E60F78663F776294F093A0C7C55263E3BA43716985C",
        "Receipt locks, rollback discipline, deterministic sidecar cache, and app-local product evidence.",
    ),
    SourceDefinition(
        "SRC-GPU-1",
        "PDC_GPU_Route_Selector_Internal_Implementation_Document.md",
        "markdown",
        "68326C4A97E82F10C650522DE8CC29D6EBFFE812209B16E2D8C764AA8C0DA373",
        "GPU resident-chain selection, shape bins, calibration, hard guards, and bounded-regret promotion.",
    ),
    SourceDefinition(
        "SRC-CPU-1",
        "PDC_CPU_Internal_Implementation_Document_v1.md",
        "markdown",
        "929009DDF302BE959BCC8D22ADA7183E09A68839C66CC8E62A677E1716D7089F",
        "CPU route candidates, controls, setup accounting, repeat gates, and promotion/demotion policy.",
    ),
    SourceDefinition(
        "SRC-RAM-1",
        "PDC_RAM_Data_Lane_Implementation_Document_v1.md",
        "markdown",
        "C3AABECADC49E3E9385E6A9F5B109E9CEC28EAD08E0BB83D0B0BB945478F0E6C",
        "Persistent live/scratch buffer pooling, ownership hazards, controls, and memory promotion gates.",
    ),
    SourceDefinition(
        "SRC-HASH-1",
        "poole_defect_calculus_hashrate_implementation.md",
        "markdown",
        "2140DCD1164C582433C520EDAD37E40B0CF7D4B6F2296BF61E200DED54284D97",
        "Optional valid SHA-256d OpenCL application benchmark and explicit non-shortcut boundary.",
    ),
    SourceDefinition(
        "SRC-LG-1",
        "The Poole Local-Geometry Program.pdf",
        "pdf",
        "D3772D9A79A33AB7D19CBA9D68C32CBCE5C72B780CBABBF6B9C7A69D354D8075",
        "Local-geometry definitions, theorem program, reconstruction limits, and open questions.",
    ),
    SourceDefinition(
        "SRC-MAG-1",
        "Poole_Local_Geometry_Magnum_Opus_v1_4_Bridge_Benchmark_Deep_Cleanup.pdf",
        "pdf",
        "8B1CE6183C7576BA823E7A88D29B82C3F2259070367ECBA4BF3C346A60DAC865",
        "Consolidated algebra, exact verifiers, Q/P, signed benchmarks, and bridge boundaries.",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(payload).hexdigest().upper()


def _copy_content_addressed(source: Path, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != expected_sha256:
            raise PdcSourceIntakeError(f"existing content-addressed copy has wrong hash: {destination}")
        return
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        shutil.copyfile(source, temporary)
        if sha256_file(temporary) != expected_sha256:
            raise PdcSourceIntakeError(f"copied source hash changed during intake: {source}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _source_record(
    definition: SourceDefinition,
    *,
    downloads: Path,
    workspace: Path,
    copy_files: bool,
) -> dict[str, object]:
    source = downloads / definition.filename
    if not source.is_file():
        raise PdcSourceIntakeError(f"designated source is missing: {source}")
    actual_hash = sha256_file(source)
    if actual_hash != definition.expected_sha256:
        raise PdcSourceIntakeError(
            f"designated source hash mismatch for {definition.id}: expected {definition.expected_sha256}, got {actual_hash}"
        )
    suffix = source.suffix.lower()
    relative_copy = Path("sources") / "pdc" / "intake" / "sha256" / f"{actual_hash.lower()}{suffix}"
    destination = workspace / relative_copy
    if copy_files:
        _copy_content_addressed(source, destination, actual_hash)
    if not destination.is_file() or sha256_file(destination) != actual_hash:
        raise PdcSourceIntakeError(f"content-addressed copy is not verified: {destination}")
    stat = source.stat()
    return {
        "id": definition.id,
        "original_name": source.name,
        "original_path": str(source),
        "stored_path": relative_copy.as_posix(),
        "kind": definition.kind,
        "size_bytes": stat.st_size,
        "modified_utc": _iso_utc(stat.st_mtime),
        "sha256": actual_hash,
        "claim_role": definition.claim_role,
        "status": "locked_copy_verified",
    }


def discover_raw_candidates(downloads: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                path
                for path in downloads.iterdir()
                if path.is_file() and path.suffix.lower() in RAW_EXTENSIONS and RAW_NAME_PATTERN.search(path.name)
            ),
            key=lambda path: path.name.casefold(),
        )
    )


def _raw_candidate_records(paths: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    first_by_hash: dict[str, str] = {}
    for index, path in enumerate(paths, start=1):
        digest = sha256_file(path)
        first_name = first_by_hash.setdefault(digest, path.name)
        stat = path.stat()
        records.append(
            {
                "id": f"RAW-PDC-{index:03d}",
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_utc": _iso_utc(stat.st_mtime),
                "sha256": digest,
                "duplicate_of": None if first_name == path.name else first_name,
                "status": "indexed_not_imported",
            }
        )
    return records


def make_source_intake(
    *,
    workspace: Path,
    downloads: Path,
    definitions: Iterable[SourceDefinition] = DESIGNATED_SOURCES,
    copy_files: bool = True,
) -> dict[str, object]:
    workspace = workspace.resolve()
    downloads = downloads.resolve()
    designated = [
        _source_record(definition, downloads=downloads, workspace=workspace, copy_files=copy_files)
        for definition in definitions
    ]
    raw_candidates = _raw_candidate_records(discover_raw_candidates(downloads))
    source_digest_input = [{"id": item["id"], "sha256": item["sha256"]} for item in designated]
    raw_digest_input = [{"name": item["name"], "sha256": item["sha256"]} for item in raw_candidates]
    duplicate_count = sum(item["duplicate_of"] is not None for item in raw_candidates)
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_source_intake",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pass",
        "scope": {
            "designated_authority_count": len(designated),
            "raw_scan_root": str(downloads),
            "raw_scan_depth": 1,
            "raw_extensions": sorted(RAW_EXTENSIONS),
            "raw_name_pattern": RAW_NAME_PATTERN.pattern,
            "raw_candidates_are_authoritative": False,
        },
        "designated_sources": designated,
        "raw_artifact_candidates": raw_candidates,
        "digests": {
            "designated_source_set_sha256": sha256_json(source_digest_input),
            "raw_candidate_index_sha256": sha256_json(raw_digest_input),
        },
        "summary": {
            "locked_source_count": len(designated),
            "verified_copy_count": sum(item["status"] == "locked_copy_verified" for item in designated),
            "raw_candidate_count": len(raw_candidates),
            "raw_duplicate_count": duplicate_count,
            "raw_imported_count": 0,
            "failed_count": 0,
        },
        "limitations": [
            "Raw candidates are name-filtered one-level inventory entries, not promoted evidence.",
            "Raw candidate packages remain outside the trusted source set until imported and rerun by their owning phase.",
            "The intake records content identity and source role; it does not prove manuscript claims or benchmark reproduction.",
        ],
    }
