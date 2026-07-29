"""Independent PSM1 parser, encoder, digest oracle, and receipt validation."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID = "PSM1"
MAGIC = "POOLEOS-SYSTEM-MANIFEST/1.0"
END_MARKER = "end=PSM1"
MANIFEST_ROOT = "\\EFI\\POOLEOS\\"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_LINE_BYTES = 384
MAX_LINES = 192
MAX_ARTIFACTS = 16
MAX_IDENTIFIER_BYTES = 31
MAX_MANIFEST_ID_BYTES = 63
MAX_PATH_BYTES = 240
MAX_FORMAT_BYTES = 16
MAX_ENTRY_CONTRACT_BYTES = 16
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 512 * 1024 * 1024
MAX_SLOT = 4
ARTIFACT_TYPES = (
    "kernel",
    "initial_system",
    "recovery",
    "symbols",
    "microcode",
    "firmware",
    "policy",
    "pooleglyph",
)
FIELDS = (
    "type",
    "format",
    "version",
    "path",
    "file_bytes",
    "image_bytes",
    "sha256",
    "entry_contract",
)
CONTRACT_RELATIVE = "specs/native-system-manifest-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-system-manifest-contract.schema.json"
READINESS_RELATIVE = "runs/native_system_manifest_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-system-manifest-readiness.schema.json"
DIGEST_PROVIDER_RELATIVE = "specs/native-boot-digest-provider.json"
DIGEST_PROVIDER_SCHEMA_RELATIVE = "specs/native-boot-digest-provider.schema.json"
GOLDEN_RELATIVE = "specs/native-system-manifest-golden-vectors.json"
GOLDEN_SCHEMA_RELATIVE = "specs/native-system-manifest-golden-vectors.schema.json"

IMPLEMENTATION_INPUTS = (
    "native/.cargo/config.toml",
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/manifest/Cargo.toml",
    "native/manifest/src/lib.rs",
    "native/manifest/src/bin/psm1_probe.rs",
    "native/bootload/Cargo.toml",
    "native/bootload/src/lib.rs",
    "native/boot/src/kload.rs",
    "runtime/native_system_manifest.py",
    "specs/native-boot-digest-provider.json",
    "specs/native-boot-digest-provider.schema.json",
    "specs/native-system-manifest-contract.json",
    "specs/native-system-manifest-contract.schema.json",
    "specs/native-system-manifest-golden-vectors.json",
    "specs/native-system-manifest-golden-vectors.schema.json",
    "specs/native-system-manifest-readiness.schema.json",
    "tools/generate_native_system_manifest_vectors.py",
    "tools/qualify_native_boot_config.py",
    "tools/qualify_native_system_manifest.py",
    "tests/test_native_system_manifest.py",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N5-PSM1-EMPTY",
    "NEG-N5-PSM1-OVERSIZED",
    "NEG-N5-PSM1-FINAL-LF",
    "NEG-N5-PSM1-NUL",
    "NEG-N5-PSM1-BOM",
    "NEG-N5-PSM1-CRLF",
    "NEG-N5-PSM1-NON-ASCII",
    "NEG-N5-PSM1-WHITESPACE",
    "NEG-N5-PSM1-EMPTY-LINE",
    "NEG-N5-PSM1-LINE-OVERSIZED",
    "NEG-N5-PSM1-LINE-COUNT",
    "NEG-N5-PSM1-MAGIC",
    "NEG-N5-PSM1-MAJOR-VERSION",
    "NEG-N5-PSM1-MINOR-VERSION",
    "NEG-N5-PSM1-NO-EQUALS",
    "NEG-N5-PSM1-EMPTY-KEY",
    "NEG-N5-PSM1-EMPTY-VALUE",
    "NEG-N5-PSM1-MULTIPLE-EQUALS",
    "NEG-N5-PSM1-DUPLICATE-STATIC",
    "NEG-N5-PSM1-DUPLICATE-ARTIFACT",
    "NEG-N5-PSM1-UNKNOWN-STATIC",
    "NEG-N5-PSM1-UNKNOWN-ARTIFACT",
    "NEG-N5-PSM1-HEADER-ORDER",
    "NEG-N5-PSM1-ARTIFACT-FIELD-ORDER",
    "NEG-N5-PSM1-TRUNCATED-HEADER",
    "NEG-N5-PSM1-TRUNCATED-ARTIFACT",
    "NEG-N5-PSM1-END-MISSING",
    "NEG-N5-PSM1-END-WRONG",
    "NEG-N5-PSM1-MANIFEST-ID",
    "NEG-N5-PSM1-SLOT-ZERO",
    "NEG-N5-PSM1-SLOT-HIGH",
    "NEG-N5-PSM1-SLOT-LEADING-ZERO",
    "NEG-N5-PSM1-MANIFEST-VERSION-ZERO",
    "NEG-N5-PSM1-VERSION-FLOOR",
    "NEG-N5-PSM1-COUNT-ZERO",
    "NEG-N5-PSM1-COUNT-HIGH",
    "NEG-N5-PSM1-COUNT-SHORT",
    "NEG-N5-PSM1-COUNT-EXTRA",
    "NEG-N5-PSM1-ARTIFACT-ID-START",
    "NEG-N5-PSM1-ARTIFACT-ID-LENGTH",
    "NEG-N5-PSM1-ARTIFACT-ORDER",
    "NEG-N5-PSM1-ARTIFACT-TYPE",
    "NEG-N5-PSM1-FORMAT",
    "NEG-N5-PSM1-ARTIFACT-VERSION-FLOOR",
    "NEG-N5-PSM1-PATH-RELATIVE",
    "NEG-N5-PSM1-PATH-ROOT",
    "NEG-N5-PSM1-PATH-SLASH",
    "NEG-N5-PSM1-PATH-TRAVERSAL",
    "NEG-N5-PSM1-PATH-EMPTY-SEGMENT",
    "NEG-N5-PSM1-PATH-LOWERCASE",
    "NEG-N5-PSM1-PATH-LENGTH",
    "NEG-N5-PSM1-FILE-ZERO",
    "NEG-N5-PSM1-FILE-HIGH",
    "NEG-N5-PSM1-IMAGE-HIGH",
    "NEG-N5-PSM1-DIGEST-LENGTH",
    "NEG-N5-PSM1-DIGEST-LOWERCASE",
    "NEG-N5-PSM1-ENTRY-CONTRACT",
    "NEG-N5-PSM1-KERNEL-FORMAT",
    "NEG-N5-PSM1-KERNEL-ENTRY",
    "NEG-N5-PSM1-KERNEL-IMAGE-ZERO",
    "NEG-N5-PSM1-KERNEL-MISSING",
    "NEG-N5-PSM1-KERNEL-DUPLICATE",
    "NEG-N5-PSM1-DUPLICATE-PATH",
    "NEG-N5-PSM1-OUTPUT-CAPACITY",
)


class ManifestError(ValueError):
    """Raised when bytes violate the canonical PSM1 contract."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Artifact:
    id: str
    type: str
    format: str
    version: int
    path: str
    file_bytes: int
    image_bytes: int
    sha256: str
    entry_contract: str


@dataclasses.dataclass(frozen=True)
class SystemManifest:
    manifest_id: str
    slot: int
    manifest_version: int
    minimum_secure_version: int
    artifacts: tuple[Artifact, ...]

    @property
    def kernel(self) -> Artifact:
        kernels = tuple(item for item in self.artifacts if item.type == "kernel")
        if len(kernels) != 1:
            raise ManifestError("manifest_kernel_count")
        return kernels[0]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _parse_number(value: str, minimum: int, maximum: int) -> int:
    if not value or not value.isascii() or not value.isdigit():
        raise ManifestError("manifest_number")
    if len(value) > 1 and value.startswith("0"):
        raise ManifestError("manifest_number_canonical")
    number = int(value)
    if not minimum <= number <= maximum:
        raise ManifestError("manifest_range")
    return number


def _valid_lower_identifier(value: str) -> bool:
    return bool(
        0 < len(value) <= MAX_IDENTIFIER_BYTES
        and re.fullmatch(r"[a-z][a-z0-9_]*", value)
    )


def _valid_upper_identifier(value: str, maximum: int) -> bool:
    return bool(0 < len(value) <= maximum and re.fullmatch(r"[A-Z][A-Z0-9_-]*", value))


def _validate_path(value: str) -> None:
    if len(value) > MAX_PATH_BYTES or not value.startswith(MANIFEST_ROOT) or "/" in value:
        raise ManifestError("manifest_path")
    components = value[len(MANIFEST_ROOT) :].split("\\")
    if not components or any(not component or len(component) > 64 for component in components):
        raise ManifestError("manifest_path")
    for index, component in enumerate(components):
        if component in (".", ".."):
            raise ManifestError("manifest_path")
        last = index + 1 == len(components)
        if last:
            if component.count(".") != 1 or component.startswith(".") or component.endswith("."):
                raise ManifestError("manifest_path")
            allowed = r"[A-Z0-9_-]+\.[A-Z0-9_-]+"
        else:
            if "." in component:
                raise ManifestError("manifest_path")
            allowed = r"[A-Z0-9_-]+"
        if re.fullmatch(allowed, component) is None:
            raise ManifestError("manifest_path")


def _classify_key(key: str) -> str:
    if key in {
        "manifest_id",
        "slot",
        "manifest_version",
        "minimum_secure_version",
        "artifact_count",
    }:
        return "known"
    if not key.startswith("artifact."):
        return "unknown"
    parts = key.split(".")
    if len(parts) != 3:
        return "unknown"
    if not _valid_lower_identifier(parts[1]):
        return "identifier"
    return "known" if parts[2] in FIELDS else "unknown"


def _expected(entries: list[tuple[str, str]], index: int, key: str) -> str:
    if index >= len(entries):
        raise ManifestError("manifest_truncated")
    observed, value = entries[index]
    if observed == key:
        return value
    classification = _classify_key(observed)
    if classification == "identifier":
        raise ManifestError("manifest_identifier")
    if classification == "unknown":
        raise ManifestError("manifest_unknown_key")
    raise ManifestError("manifest_key_order")


def parse(data: bytes) -> SystemManifest:
    if not data:
        raise ManifestError("manifest_empty")
    if len(data) > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest_too_large")
    if not data.endswith(b"\n"):
        raise ManifestError("manifest_missing_final_lf")
    if any(byte != 0x0A and not 0x21 <= byte <= 0x7E for byte in data):
        raise ManifestError("manifest_character")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ManifestError("manifest_character") from error
    lines = text[:-1].split("\n")
    if any(not line for line in lines):
        raise ManifestError("manifest_empty_line")
    if any(len(line.encode("ascii")) > MAX_LINE_BYTES for line in lines):
        raise ManifestError("manifest_line_too_long")
    if len(lines) > MAX_LINES:
        raise ManifestError("manifest_too_many_lines")
    if lines[0] != MAGIC:
        raise ManifestError(
            "manifest_version" if lines[0].startswith("POOLEOS-SYSTEM-MANIFEST/") else "manifest_magic"
        )
    if len(lines) < 15:
        raise ManifestError("manifest_truncated")
    if lines[-1] != END_MARKER:
        raise ManifestError("manifest_end_marker")

    entries: list[tuple[str, str]] = []
    keys: set[str] = set()
    for line in lines[1:-1]:
        if line.count("=") != 1:
            raise ManifestError("manifest_syntax")
        key, value = line.split("=", 1)
        if not key or not value:
            raise ManifestError("manifest_syntax")
        if key in keys:
            raise ManifestError("manifest_duplicate_key")
        keys.add(key)
        entries.append((key, value))

    manifest_id = _expected(entries, 0, "manifest_id")
    if not _valid_upper_identifier(manifest_id, MAX_MANIFEST_ID_BYTES):
        raise ManifestError("manifest_identifier")
    slot = _parse_number(_expected(entries, 1, "slot"), 1, MAX_SLOT)
    manifest_version = _parse_number(
        _expected(entries, 2, "manifest_version"), 1, 2**64 - 1
    )
    minimum_secure_version = _parse_number(
        _expected(entries, 3, "minimum_secure_version"), 0, 2**64 - 1
    )
    if minimum_secure_version > manifest_version:
        raise ManifestError("manifest_version_floor")
    artifact_count = _parse_number(
        _expected(entries, 4, "artifact_count"), 1, MAX_ARTIFACTS
    )
    if len(lines) != 7 + artifact_count * 8:
        if len(lines) < 7 + artifact_count * 8:
            raise ManifestError("manifest_truncated")
        extra_index = 5 + artifact_count * 8
        classification = _classify_key(entries[extra_index][0]) if extra_index < len(entries) else "known"
        if classification == "identifier":
            raise ManifestError("manifest_identifier")
        if classification == "unknown":
            raise ManifestError("manifest_unknown_key")
        raise ManifestError("manifest_key_order")

    artifacts: list[Artifact] = []
    previous_id = ""
    paths: set[str] = set()
    for artifact_index in range(artifact_count):
        base = 5 + artifact_index * 8
        first_key, type_value = entries[base]
        parts = first_key.split(".")
        if len(parts) != 3 or parts[0] != "artifact" or not _valid_lower_identifier(parts[1]):
            classification = _classify_key(first_key)
            raise ManifestError(
                "manifest_identifier" if classification == "identifier" else "manifest_unknown_key"
            )
        artifact_id = parts[1]
        if parts[2] != "type":
            raise ManifestError("manifest_key_order")
        if previous_id and artifact_id <= previous_id:
            raise ManifestError("manifest_artifact_order")
        previous_id = artifact_id
        values = {"type": type_value}
        for field_index, field in enumerate(FIELDS[1:], start=1):
            values[field] = _expected(
                entries, base + field_index, f"artifact.{artifact_id}.{field}"
            )
        if type_value not in ARTIFACT_TYPES:
            raise ManifestError("manifest_artifact_type")
        if not _valid_upper_identifier(values["format"], MAX_FORMAT_BYTES):
            raise ManifestError("manifest_format")
        version = _parse_number(values["version"], 1, 2**64 - 1)
        if version < minimum_secure_version:
            raise ManifestError("manifest_version_floor")
        _validate_path(values["path"])
        if values["path"] in paths:
            raise ManifestError("manifest_duplicate_path")
        paths.add(values["path"])
        file_bytes = _parse_number(values["file_bytes"], 1, MAX_FILE_BYTES)
        image_bytes = _parse_number(values["image_bytes"], 0, MAX_IMAGE_BYTES)
        digest = values["sha256"]
        if re.fullmatch(r"[0-9A-F]{64}", digest) is None:
            raise ManifestError("manifest_digest")
        entry_contract = values["entry_contract"]
        if entry_contract != "none" and not _valid_upper_identifier(
            entry_contract, MAX_ENTRY_CONTRACT_BYTES
        ):
            raise ManifestError("manifest_entry_contract")
        if type_value == "kernel":
            if values["format"] != "PKELF1" or entry_contract != "PKENTRY1" or image_bytes == 0:
                raise ManifestError("manifest_binding")
        elif entry_contract != "none":
            raise ManifestError("manifest_entry_contract")
        artifacts.append(
            Artifact(
                id=artifact_id,
                type=type_value,
                format=values["format"],
                version=version,
                path=values["path"],
                file_bytes=file_bytes,
                image_bytes=image_bytes,
                sha256=digest,
                entry_contract=entry_contract,
            )
        )
    manifest = SystemManifest(
        manifest_id=manifest_id,
        slot=slot,
        manifest_version=manifest_version,
        minimum_secure_version=minimum_secure_version,
        artifacts=tuple(artifacts),
    )
    _ = manifest.kernel
    return manifest


def encode(
    artifacts: Iterable[Artifact],
    *,
    manifest_id: str,
    slot: int,
    manifest_version: int,
    minimum_secure_version: int,
) -> bytes:
    ordered = tuple(artifacts)
    lines = [
        MAGIC,
        f"manifest_id={manifest_id}",
        f"slot={slot}",
        f"manifest_version={manifest_version}",
        f"minimum_secure_version={minimum_secure_version}",
        f"artifact_count={len(ordered)}",
    ]
    for artifact in ordered:
        prefix = f"artifact.{artifact.id}"
        lines.extend(
            (
                f"{prefix}.type={artifact.type}",
                f"{prefix}.format={artifact.format}",
                f"{prefix}.version={artifact.version}",
                f"{prefix}.path={artifact.path}",
                f"{prefix}.file_bytes={artifact.file_bytes}",
                f"{prefix}.image_bytes={artifact.image_bytes}",
                f"{prefix}.sha256={artifact.sha256}",
                f"{prefix}.entry_contract={artifact.entry_contract}",
            )
        )
    lines.append(END_MARKER)
    result = ("\n".join(lines) + "\n").encode("ascii")
    if parse(result) != SystemManifest(
        manifest_id,
        slot,
        manifest_version,
        minimum_secure_version,
        ordered,
    ):
        raise ManifestError("manifest_binding")
    return result


def canonical_kernel_manifest(
    kernel_data: bytes,
    image_bytes: int,
    *,
    slot: int = 1,
    manifest_version: int = 1,
    minimum_secure_version: int = 1,
    kernel_version: int = 1,
    kernel_path: str = r"\EFI\POOLEOS\KERNEL.ELF",
) -> bytes:
    return encode(
        (
            Artifact(
                id="kernel",
                type="kernel",
                format="PKELF1",
                version=kernel_version,
                path=kernel_path,
                file_bytes=len(kernel_data),
                image_bytes=image_bytes,
                sha256=sha256_bytes(kernel_data),
                entry_contract="PKENTRY1",
            ),
        ),
        manifest_id=f"PSM-CYCLE103-SLOT{slot}",
        slot=slot,
        manifest_version=manifest_version,
        minimum_secure_version=minimum_secure_version,
    )


def verify_file(artifact: Artifact, data: bytes) -> str:
    if len(data) != artifact.file_bytes:
        raise ManifestError("manifest_size")
    digest = sha256_bytes(data)
    if digest != artifact.sha256:
        raise ManifestError("manifest_digest")
    return digest


def summary(manifest: SystemManifest) -> dict[str, Any]:
    return {
        "manifest_id": manifest.manifest_id,
        "slot": manifest.slot,
        "manifest_version": manifest.manifest_version,
        "minimum_secure_version": manifest.minimum_secure_version,
        "artifact_count": len(manifest.artifacts),
        "artifacts": [dataclasses.asdict(item) for item in manifest.artifacts],
    }


def summarize(manifest: SystemManifest) -> str:
    result = (
        f"OK;manifest_id={manifest.manifest_id};slot={manifest.slot};"
        f"manifest_version={manifest.manifest_version};"
        f"minimum_secure_version={manifest.minimum_secure_version};"
        f"artifact_count={len(manifest.artifacts)}"
    )
    for artifact in manifest.artifacts:
        result += (
            f";artifact={artifact.id},{artifact.type},{artifact.format},{artifact.version},"
            f"{artifact.path},{artifact.file_bytes},{artifact.image_bytes},"
            f"{artifact.sha256},{artifact.entry_contract}"
        )
    return result


def parse_result(data: bytes, capacity: int = MAX_ARTIFACTS) -> str:
    if not 0 <= capacity <= MAX_ARTIFACTS:
        return "ERR:transport"
    try:
        manifest = parse(data)
        if len(manifest.artifacts) > capacity:
            raise ManifestError("manifest_output_capacity")
        return summarize(manifest)
    except ManifestError as error:
        return f"ERR:{error.code}"


def digest_result(data: bytes) -> str:
    return f"OK;sha256={sha256_bytes(data)}"


def build_fixture(vector_id: str) -> bytes:
    abc_sha = sha256_bytes(b"abc")
    if vector_id == "minimal_kernel_v1":
        return encode(
            (
                Artifact(
                    "kernel",
                    "kernel",
                    "PKELF1",
                    1,
                    MANIFEST_ROOT + "KERNEL.ELF",
                    3,
                    4096,
                    abc_sha,
                    "PKENTRY1",
                ),
            ),
            manifest_id="PSM-GOLDEN-SLOT1",
            slot=1,
            manifest_version=1,
            minimum_secure_version=1,
        )
    if vector_id == "multi_artifact_v1":
        return encode(
            (
                Artifact(
                    "kernel",
                    "kernel",
                    "PKELF1",
                    7,
                    MANIFEST_ROOT + "KERNEL_A.ELF",
                    3,
                    4096,
                    abc_sha,
                    "PKENTRY1",
                ),
                Artifact(
                    "policy",
                    "policy",
                    "PPOL1",
                    6,
                    MANIFEST_ROOT + "POLICY_A.POL",
                    1,
                    0,
                    sha256_bytes(b"p"),
                    "none",
                ),
            ),
            manifest_id="PSM-GOLDEN-MULTI-SLOT2",
            slot=2,
            manifest_version=7,
            minimum_secure_version=6,
        )
    if vector_id == "bounded_maxima_v1":
        artifacts = [
            Artifact(
                f"a{index:02d}",
                "policy",
                "PPOL1",
                2**64 - 1,
                MANIFEST_ROOT + f"BOUND_{index:02d}.POL",
                MAX_FILE_BYTES,
                0,
                sha256_bytes(f"policy-{index}".encode("ascii")),
                "none",
            )
            for index in range(MAX_ARTIFACTS - 1)
        ]
        artifacts.append(
            Artifact(
                "kernel",
                "kernel",
                "PKELF1",
                2**64 - 1,
                MANIFEST_ROOT + "KERNEL_MAX.ELF",
                MAX_FILE_BYTES,
                MAX_IMAGE_BYTES,
                abc_sha,
                "PKENTRY1",
            )
        )
        return encode(
            artifacts,
            manifest_id="P" + "A" * (MAX_MANIFEST_ID_BYTES - 1),
            slot=MAX_SLOT,
            manifest_version=2**64 - 1,
            minimum_secure_version=2**64 - 1,
        )
    raise ManifestError("manifest_binding")


def make_golden_vectors() -> dict[str, Any]:
    definitions = (
        ("minimal_kernel_v1", "Smallest canonical kernel-only PSM1 manifest."),
        ("multi_artifact_v1", "Canonical kernel and policy manifest with a secure-version floor."),
        ("bounded_maxima_v1", "Sixteen artifacts and maximum numeric contract values."),
    )
    vectors = []
    for vector_id, purpose in definitions:
        data = build_fixture(vector_id)
        manifest = parse(data)
        vectors.append(
            {
                "id": vector_id,
                "purpose": purpose,
                "artifact_count": len(manifest.artifacts),
                "byte_count": len(data),
                "sha256": sha256_bytes(data),
                "summary": summarize(manifest),
                "hex": data.hex().upper(),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_system_manifest_golden_vectors",
        "contract_id": CONTRACT_ID,
        "status": "synthetic_non_promoting_golden_bytes",
        "production_ready": False,
        "vectors": vectors,
        "claim_boundary": [
            "Vectors qualify canonical PSM1 codec behavior and do not represent signed release manifests.",
            "Synthetic paths and digests do not prove firmware discovery, trust, rollback state, or artifact execution.",
            "The bounded vector exercises parser limits without allocating or loading the declared artifact sizes.",
        ],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "canonical_manifest_grammar_defined": True,
        "rust_no_std_parser_executed": True,
        "independent_python_parser_executed": True,
        "pooleboot_compile_time_dependency": True,
        "sha256_standard_vectors_matched": True,
        "golden_semantic_agreement": True,
        "hostile_controls_executed": True,
        "deterministic_differential_fuzz_executed": True,
        "live_manifest_file_opened": False,
        "live_manifest_parsed_by_pooleboot": False,
        "manifest_selected_kernel_path": False,
        "kernel_digest_verified": False,
        "manifest_signature_verified": False,
        "manifest_trusted": False,
        "rollback_enforced": False,
        "secure_boot_enforced": False,
        "measured_boot_performed": False,
        "kernel_pages_retained": False,
        "page_tables_activated": False,
        "exit_boot_services_called": False,
        "kernel_entry_called": False,
        "target_firmware_tested": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }


def expected_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_system_manifest_contract",
        "contract_id": CONTRACT_ID,
        "status": "candidate_pre_abi_pre_signature_non_promoting",
        "selected_move_id": "N5-MANIFEST-001",
        "production_ready": False,
        "encoding": {
            "character_set": "ASCII bytes 0x21..0x7E plus LF line terminators",
            "line_ending": "LF",
            "final_lf_required": True,
            "bom_allowed": False,
            "comments_allowed": False,
            "blank_lines_allowed": False,
            "whitespace_allowed": False,
        },
        "grammar": {
            "magic": MAGIC,
            "fixed_keys": [
                "manifest_id",
                "slot",
                "manifest_version",
                "minimum_secure_version",
                "artifact_count",
            ],
            "artifact_key_template": "artifact.<id>.<field>",
            "artifact_field_order": list(FIELDS),
            "terminal": END_MARKER,
            "artifact_order": "strict ascending ASCII identifier order",
            "duplicate_policy": "reject repeated full keys and repeated artifact paths",
            "unknown_key_policy": "reject",
            "number_policy": "canonical unsigned decimal u64; no sign or leading zero except zero",
        },
        "limits": {
            "manifest_bytes": MAX_MANIFEST_BYTES,
            "line_bytes": MAX_LINE_BYTES,
            "lines": MAX_LINES,
            "artifacts": MAX_ARTIFACTS,
            "identifier_bytes": MAX_IDENTIFIER_BYTES,
            "manifest_id_bytes": MAX_MANIFEST_ID_BYTES,
            "path_bytes": MAX_PATH_BYTES,
            "format_bytes": MAX_FORMAT_BYTES,
            "entry_contract_bytes": MAX_ENTRY_CONTRACT_BYTES,
            "file_bytes": MAX_FILE_BYTES,
            "image_bytes": MAX_IMAGE_BYTES,
            "slot": MAX_SLOT,
        },
        "artifact_types": list(ARTIFACT_TYPES),
        "path_policy": {
            "root": MANIFEST_ROOT,
            "case": "uppercase ASCII path components",
            "component_bytes": 64,
            "final_component_requires_one_extension_dot": True,
            "dot_components_allowed": False,
            "forward_slash_allowed": False,
        },
        "kernel_binding": {
            "exact_kernel_artifact_count": 1,
            "format": "PKELF1",
            "entry_contract": "PKENTRY1",
            "image_bytes_nonzero": True,
            "file_size_exact": True,
            "sha256_exact": True,
        },
        "version_policy": {
            "manifest_version_minimum": 1,
            "artifact_version_minimum": 1,
            "minimum_secure_version_may_be_zero": True,
            "manifest_and_artifact_versions_must_meet_floor": True,
            "persistent_rollback_state_enforced": False,
        },
        "digest_provider_contract": "PBDIGEST1",
        "phase_mapping": ["N5.1", "N5.4", "N5.5"],
        "required_golden_vector_count": 3,
        "required_negative_controls": list(NEGATIVE_CONTROL_IDS),
        "required_differential_cases": 16384,
        "claims": expected_claims(),
        "claim_boundary": [
            "PSM1 is a candidate parser and binding contract, not an owner-ratified stable ABI.",
            "A SHA-256 match proves equality to manifest bytes only; this contract has no signature or trust anchor.",
            "The minimum secure version is parsed and compared inside one manifest but no persistent rollback state is enforced.",
            "Parser qualification does not prove live firmware file I/O; the separate PKLOAD2 receipt owns that claim.",
            "No receipt here proves retained mappings, ExitBootServices, kernel entry, target firmware, or physical media.",
            "No key is generated or used, and no signing, merge, tag, release, firmware mutation, or media write is authorized.",
            "N5 and production readiness remain false.",
        ],
    }


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ManifestError("manifest_binding")
    return value


def file_binding(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    data = path.read_bytes()
    return {"path": relative_path, "sha256": sha256_bytes(data), "byte_count": len(data)}


def binding_matches(binding: Any, root: Path, expected_path: str) -> bool:
    return bool(
        isinstance(binding, dict)
        and binding.get("path") == expected_path
        and binding == file_binding(root, expected_path)
    )


def _schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    schema = read_json(root / schema_relative)
    return [f"schema {item.path}: {item.message}" for item in validate_json(value, schema)]


def contract_errors(contract: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(contract, root, CONTRACT_SCHEMA_RELATIVE)
    if contract != expected_contract():
        errors.append("contract differs from executable PSM1 constants")
    return errors


def golden_errors(golden: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(golden, root, GOLDEN_SCHEMA_RELATIVE)
    if golden != make_golden_vectors():
        errors.append("golden vectors do not reproduce exactly")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)
    bindings = readiness.get("bindings", {})
    for field, path in (
        ("contract", CONTRACT_RELATIVE),
        ("contract_schema", CONTRACT_SCHEMA_RELATIVE),
        ("golden_vectors", GOLDEN_RELATIVE),
        ("golden_schema", GOLDEN_SCHEMA_RELATIVE),
        ("readiness_schema", READINESS_SCHEMA_RELATIVE),
        ("digest_provider", DIGEST_PROVIDER_RELATIVE),
        ("digest_provider_schema", DIGEST_PROVIDER_SCHEMA_RELATIVE),
    ):
        if not binding_matches(bindings.get(field), root, path):
            errors.append(f"PSM1 {field} binding changed")
    inputs = bindings.get("implementation_inputs", [])
    expected_inputs = [file_binding(root, path) for path in IMPLEMENTATION_INPUTS]
    if inputs != expected_inputs:
        errors.append("PSM1 implementation input bindings changed")
    if readiness.get("production_ready") is not False:
        errors.append("PSM1 production readiness changed")
    claims = readiness.get("claims", {})
    expected = expected_claims()
    if claims != expected:
        errors.append("PSM1 claim set contains an omission or overreach")
        for name, value in expected.items():
            if claims.get(name) is not value:
                errors.append(f"PSM1 claim changed: {name}")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(
        NEGATIVE_CONTROL_IDS
    ):
        errors.append("PSM1 negative-control order changed")
    if any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("PSM1 readiness has a failing negative control")
    if readiness.get("summary", {}).get("differential_cases") != 16384:
        errors.append("PSM1 differential campaign count changed")
    return errors
