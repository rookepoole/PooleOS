"""Content-addressed intake and lineage checks for exact PDC verifier sources."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from zipfile import ZipFile


PLANAR_ROOT = "poole_defect_calculus_public_release_v1_1_clean/"
PLANAR_SCRIPT_MEMBER = PLANAR_ROOT + "evidence/scripts/poole_defect_verifier.py"
PLANAR_MANIFEST_MEMBER = PLANAR_ROOT + "evidence/reports/sha256_manifest.csv"
NONPLANAR_MANIFEST_MEMBER = "manifest_v1_3_3.csv"
ANCILLARY_RESULTS_MEMBER = (
    "data/limitation_closure_v1_3_4/poole_limitation_closure_v1_3_3_results.zip"
)
ANCILLARY_NONPLANAR_TABLE_MEMBER = (
    "data/limitation_closure_v1_3_4/nonplanar_exact_formula_verifier_v1_3_3.csv"
)
ANCILLARY_MANIFEST_MEMBER = (
    "data/limitation_closure_v1_3_4/limitation_closure_manifest_v1_3_4.csv"
)
RESULTS_NONPLANAR_TABLE_MEMBER = "nonplanar_exact_formula_verifier.csv"

MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2_000_000_000


class PdcVerifierIntakeError(ValueError):
    """Raised when a selected verifier source fails intake or lineage checks."""


@dataclass(frozen=True)
class VerifierSourceDefinition:
    id: str
    relative_path: Path
    expected_sha256: str
    role: str
    cycle74_candidate_id: str | None = None


VERIFIER_SOURCES = (
    VerifierSourceDefinition(
        id="VER-SRC-PLANAR-V1_1",
        relative_path=Path("poole_defect_calculus_public_release_v1_1_clean_package.zip"),
        expected_sha256="4B676EA7FF96B8FD513A474C59B988EEED2F2CED845E33FD2EFABE90ABE51D7E",
        role="Canonical executable source and published rows for rectangle, line-hole, arbitrary-mask, and inversion families.",
        cycle74_candidate_id="RAW-PDC-035",
    ),
    VerifierSourceDefinition(
        id="VER-SRC-NONPLANAR-RUNNER-V1_3_3",
        relative_path=Path("poole_limitation_closure_v1_3_3_COLAB_READY.py"),
        expected_sha256="80001A009DB955DBEB4D5B39C28C6602F7086F1C0BA45F8235D9FF856A8732B8",
        role="Canonical executable runner for the 729 solid-cuboid and 729 closed-surface-shell cases.",
    ),
    VerifierSourceDefinition(
        id="VER-SRC-NONPLANAR-RESULTS-V1_3_3",
        relative_path=Path("poole_limitation_closure_v1_3_3_results.zip"),
        expected_sha256="7F49D35D6851CCC977696F1C10E2EA9BB3479B52FD30BD201C7C9BA7F2E6BDFB",
        role="Manifest-bound published rows for the exact nonplanar formula verifier.",
    ),
    VerifierSourceDefinition(
        id="VER-SRC-LOCAL-GEOMETRY-ANCILLARY-V1_7_1",
        relative_path=Path("arxiv_upload_source_v1_7_1") / "anc" / "poole_local_geometry_data_and_code_v1_7_1.zip",
        expected_sha256="09374EDCFEB3063225E2D60B75D8EE317CC5766AD036729CD77C8F6E63C1B441",
        role="Later ancillary bundle that embeds the exact v1.3.3 results bytes and v1.3.4 manifest lineage.",
    ),
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return sha256_bytes(encoded)


def _copy_content_addressed(source: Path, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != expected_sha256:
            raise PdcVerifierIntakeError(f"existing verifier copy has the wrong hash: {destination}")
        return
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        shutil.copyfile(source, temporary)
        if sha256_file(temporary) != expected_sha256:
            raise PdcVerifierIntakeError(f"verifier source changed during copy: {source}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_verified_bytes(payload: bytes, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != expected_sha256:
            raise PdcVerifierIntakeError(f"existing extracted verifier has the wrong hash: {destination}")
        return
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        if sha256_file(temporary) != expected_sha256:
            raise PdcVerifierIntakeError("extracted verifier bytes changed during write")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _safe_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(normalized) and not path.is_absolute() and ".." not in path.parts and ":" not in path.parts[0]


def inspect_zip_safety(path: Path) -> dict[str, object]:
    with ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        unsafe_names = sorted({name for name in names if not _safe_member_name(name)})
        duplicate_names = sorted({name for name in names if names.count(name) > 1})
        symlinks = []
        for info in infos:
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(info.filename)
        total_uncompressed = sum(info.file_size for info in infos)
        corrupt_member = archive.testzip()
    failed = bool(
        len(infos) > MAX_ARCHIVE_ENTRIES
        or total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES
        or unsafe_names
        or duplicate_names
        or symlinks
        or corrupt_member
    )
    return {
        "entry_count": len(infos),
        "total_uncompressed_bytes": total_uncompressed,
        "unsafe_names": unsafe_names,
        "duplicate_names": duplicate_names,
        "symlink_members": sorted(symlinks),
        "corrupt_member": corrupt_member,
        "status": "fail" if failed else "pass",
    }


def _manifest_rows(archive: ZipFile, member: str) -> list[dict[str, str]]:
    try:
        payload = archive.read(member).decode("utf-8-sig")
    except KeyError as exc:
        raise PdcVerifierIntakeError(f"archive is missing manifest {member}") from exc
    return list(csv.DictReader(io.StringIO(payload)))


def verify_zip_manifest(
    path: Path,
    *,
    manifest_member: str,
    member_prefix: str = "",
    aliases: dict[str, str] | None = None,
) -> dict[str, object]:
    aliases = aliases or {}
    with ZipFile(path) as archive:
        rows = _manifest_rows(archive, manifest_member)
        names = set(archive.namelist())
        details: list[dict[str, object]] = []
        for row in rows:
            declared = row.get("relative_path") or row.get("path")
            expected_hash = (row.get("sha256") or "").upper()
            expected_bytes = int(row.get("bytes") or -1)
            if not declared:
                raise PdcVerifierIntakeError(f"manifest {manifest_member} has a row without a path")
            resolved_relative = aliases.get(declared, declared)
            member = member_prefix + resolved_relative
            if member not in names:
                details.append(
                    {
                        "declared_path": declared,
                        "resolved_member": member,
                        "alias_applied": declared in aliases,
                        "hash_match": False,
                        "size_match": False,
                        "status": "missing",
                    }
                )
                continue
            payload = archive.read(member)
            hash_match = sha256_bytes(payload) == expected_hash
            size_match = len(payload) == expected_bytes
            details.append(
                {
                    "declared_path": declared,
                    "resolved_member": member,
                    "alias_applied": declared in aliases,
                    "hash_match": hash_match,
                    "size_match": size_match,
                    "status": "verified" if hash_match and size_match else "mismatch",
                }
            )
        manifest_payload = archive.read(manifest_member)
    verified = sum(item["status"] == "verified" for item in details)
    return {
        "manifest_member": manifest_member,
        "manifest_sha256": sha256_bytes(manifest_payload),
        "entry_count": len(details),
        "verified_entry_count": verified,
        "failed_entry_count": len(details) - verified,
        "alias_count": sum(bool(item["alias_applied"]) for item in details),
        "entries": details,
        "status": "pass" if verified == len(details) else "fail",
    }


def _source_records(
    *, workspace: Path, downloads: Path, definitions: Iterable[VerifierSourceDefinition], copy_files: bool
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for definition in definitions:
        source = downloads / definition.relative_path
        if not source.is_file():
            raise PdcVerifierIntakeError(f"selected verifier source is missing: {source}")
        digest = sha256_file(source)
        if digest != definition.expected_sha256:
            raise PdcVerifierIntakeError(
                f"verifier hash mismatch for {definition.id}: expected {definition.expected_sha256}, got {digest}"
            )
        suffix = source.suffix.lower()
        relative_copy = Path("sources") / "pdc" / "verifiers" / "sha256" / f"{digest.lower()}{suffix}"
        destination = workspace / relative_copy
        if copy_files:
            _copy_content_addressed(source, destination, digest)
        if not destination.is_file() or sha256_file(destination) != digest:
            raise PdcVerifierIntakeError(f"verifier copy is not present and verified: {destination}")
        records.append(
            {
                "id": definition.id,
                "original_name": source.name,
                "original_path": str(source),
                "stored_path": relative_copy.as_posix(),
                "sha256": digest,
                "size_bytes": source.stat().st_size,
                "role": definition.role,
                "cycle74_candidate_id": definition.cycle74_candidate_id,
                "discovery_status": (
                    "selected_from_cycle74_index" if definition.cycle74_candidate_id else "discovered_outside_cycle74_scan"
                ),
                "status": "imported_read_only_copy_verified",
            }
        )
    return records


def make_verifier_intake(
    *,
    workspace: Path,
    downloads: Path,
    source_intake_path: Path,
    math_contract_path: Path,
    definitions: Iterable[VerifierSourceDefinition] = VERIFIER_SOURCES,
    copy_files: bool = True,
) -> dict[str, object]:
    workspace = workspace.resolve()
    downloads = downloads.resolve()
    source_intake_path = source_intake_path.resolve()
    math_contract_path = math_contract_path.resolve()
    source_intake = json.loads(source_intake_path.read_text(encoding="utf-8"))
    math_contract = json.loads(math_contract_path.read_text(encoding="utf-8"))
    source_intake_hash = sha256_file(source_intake_path)
    if math_contract["source_binding"]["artifact_sha256"] != source_intake_hash:
        raise PdcVerifierIntakeError("math contract is not bound to the supplied Cycle 74 source intake")

    definitions = tuple(definitions)
    sources = _source_records(
        workspace=workspace, downloads=downloads, definitions=definitions, copy_files=copy_files
    )
    by_id = {item["id"]: item for item in sources}

    indexed = {item["id"]: item for item in source_intake["raw_artifact_candidates"]}
    planar_index = indexed.get("RAW-PDC-035")
    if not planar_index or planar_index["sha256"] != by_id["VER-SRC-PLANAR-V1_1"]["sha256"]:
        raise PdcVerifierIntakeError("RAW-PDC-035 does not bind the selected planar package")

    archive_security = []
    for item in sources:
        if Path(item["stored_path"]).suffix == ".zip":
            safety = inspect_zip_safety(workspace / item["stored_path"])
            safety["source_id"] = item["id"]
            archive_security.append(safety)
    if any(item["status"] != "pass" for item in archive_security):
        raise PdcVerifierIntakeError("one or more selected verifier archives failed safety checks")

    planar_path = workspace / by_id["VER-SRC-PLANAR-V1_1"]["stored_path"]
    planar_manifest = verify_zip_manifest(
        planar_path,
        manifest_member=PLANAR_MANIFEST_MEMBER,
        member_prefix=PLANAR_ROOT + "evidence/",
        aliases={
            "data/empirical_planar_relaxation_timeseries_scaffold.csv":
                "data/empirical_planar_relaxation_timeseries.csv"
        },
    )
    nonplanar_results_path = workspace / by_id["VER-SRC-NONPLANAR-RESULTS-V1_3_3"]["stored_path"]
    nonplanar_manifest = verify_zip_manifest(
        nonplanar_results_path,
        manifest_member=NONPLANAR_MANIFEST_MEMBER,
    )
    ancillary_path = workspace / by_id["VER-SRC-LOCAL-GEOMETRY-ANCILLARY-V1_7_1"]["stored_path"]
    ancillary_manifest = verify_zip_manifest(
        ancillary_path,
        manifest_member=ANCILLARY_MANIFEST_MEMBER,
    )
    manifests = [planar_manifest, nonplanar_manifest, ancillary_manifest]
    if any(item["status"] != "pass" for item in manifests):
        raise PdcVerifierIntakeError("one or more embedded verifier manifests failed verification")

    with ZipFile(planar_path) as archive:
        planar_script = archive.read(PLANAR_SCRIPT_MEMBER)
    planar_script_hash = sha256_bytes(planar_script)
    planar_script_relative = (
        Path("sources")
        / "pdc"
        / "verifiers"
        / "extracted"
        / by_id["VER-SRC-PLANAR-V1_1"]["sha256"].lower()
        / "poole_defect_verifier.py"
    )
    if copy_files:
        _write_verified_bytes(planar_script, workspace / planar_script_relative, planar_script_hash)

    with ZipFile(ancillary_path) as archive:
        embedded_results = archive.read(ANCILLARY_RESULTS_MEMBER)
        ancillary_table = archive.read(ANCILLARY_NONPLANAR_TABLE_MEMBER)
    with ZipFile(nonplanar_results_path) as archive:
        results_table = archive.read(RESULTS_NONPLANAR_TABLE_MEMBER)
    lineage_checks = [
        {
            "name": "planar_package_matches_cycle74_index",
            "ok": True,
            "detail": "RAW-PDC-035 hash equals the imported v1.1-clean package hash.",
        },
        {
            "name": "ancillary_embedded_results_match_standalone",
            "ok": sha256_bytes(embedded_results) == by_id["VER-SRC-NONPLANAR-RESULTS-V1_3_3"]["sha256"],
            "detail": "The v1.7.1 ancillary bundle embeds the exact standalone v1.3.3 results ZIP bytes.",
        },
        {
            "name": "ancillary_nonplanar_table_matches_results",
            "ok": ancillary_table == results_table,
            "detail": "The v1.7.1 flat nonplanar verifier table equals the manifest-bound v1.3.3 results member.",
        },
    ]
    if not all(item["ok"] for item in lineage_checks):
        raise PdcVerifierIntakeError("selected verifier source lineage does not close")

    by_id["VER-SRC-PLANAR-V1_1"]["executable_path"] = planar_script_relative.as_posix()
    by_id["VER-SRC-PLANAR-V1_1"]["executable_sha256"] = planar_script_hash
    nonplanar_runner = by_id["VER-SRC-NONPLANAR-RUNNER-V1_3_3"]
    nonplanar_runner["executable_path"] = nonplanar_runner["stored_path"]
    nonplanar_runner["executable_sha256"] = nonplanar_runner["sha256"]

    errata = [
        {
            "id": "ERR-PLANAR-MANIFEST-PATH-001",
            "severity": "documented_nonblocking",
            "description": (
                "The v1.1 manifest declares data/empirical_planar_relaxation_timeseries_scaffold.csv, "
                "while the archive member omits _scaffold; declared bytes and SHA-256 match that member exactly."
            ),
            "affected_closed_family": False,
            "status": "resolved_by_exact_hash_alias",
        }
    ]
    source_digest = sha256_json([{"id": item["id"], "sha256": item["sha256"]} for item in sources])
    manifest_entry_count = sum(item["entry_count"] for item in manifests)
    verified_manifest_count = sum(item["verified_entry_count"] for item in manifests)
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_verifier_intake",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pass_with_documented_erratum",
        "bindings": {
            "source_intake_path": source_intake_path.relative_to(workspace).as_posix(),
            "source_intake_sha256": source_intake_hash,
            "math_contract_path": math_contract_path.relative_to(workspace).as_posix(),
            "math_contract_sha256": sha256_file(math_contract_path),
            "math_contract_version": math_contract["contract_version"],
        },
        "selected_sources": sources,
        "archive_security": archive_security,
        "embedded_manifests": manifests,
        "lineage_checks": lineage_checks,
        "errata": errata,
        "digests": {"selected_source_set_sha256": source_digest},
        "summary": {
            "selected_source_count": len(sources),
            "verified_copy_count": len(sources),
            "cycle74_indexed_import_count": sum(item["cycle74_candidate_id"] is not None for item in sources),
            "newly_discovered_source_count": sum(item["cycle74_candidate_id"] is None for item in sources),
            "safe_archive_count": len(archive_security),
            "embedded_manifest_count": len(manifests),
            "manifest_entry_count": manifest_entry_count,
            "verified_manifest_entry_count": verified_manifest_count,
            "documented_erratum_count": len(errata),
            "failed_check_count": 0,
        },
        "limitations": [
            "The Cycle 74 raw index remains an immutable point-in-time inventory; this intake records later selected imports separately.",
            "Only the six declared exact verifier families are promoted by the reproduction phase; empirical, signed, bridge, and piecewise-atlas rows remain outside this claim.",
            "Finite family reproduction supports the stated bounded domains and does not establish arbitrary-mask reconstruction or all-size nonplanar laws.",
        ],
    }
