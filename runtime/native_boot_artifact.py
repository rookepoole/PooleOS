"""Independent PBART1 development-artifact codec and oracle."""

from __future__ import annotations

import dataclasses
import hashlib
import struct
from typing import Final


CONTRACT_ID: Final = "PBART1"
MAGIC: Final = b"PBART1\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 96
MAX_FILE_BYTES: Final = 1024 * 1024
MAX_PAYLOAD_BYTES: Final = MAX_FILE_BYTES - HEADER_BYTES

ROLE_INITIAL_SYSTEM: Final = 2
ROLE_RECOVERY: Final = 3
ROLE_SYMBOLS: Final = 4
ROLE_MICROCODE: Final = 5
ROLE_FIRMWARE_MANIFEST: Final = 6
ROLE_POLICY_BUNDLE: Final = 7
ROLES: Final = (
    ROLE_INITIAL_SYSTEM,
    ROLE_RECOVERY,
    ROLE_SYMBOLS,
    ROLE_MICROCODE,
    ROLE_FIRMWARE_MANIFEST,
    ROLE_POLICY_BUNDLE,
)
ROLE_NAMES: Final = {
    ROLE_INITIAL_SYSTEM: "initial_system",
    ROLE_RECOVERY: "recovery",
    ROLE_SYMBOLS: "symbols",
    ROLE_MICROCODE: "microcode",
    ROLE_FIRMWARE_MANIFEST: "firmware",
    ROLE_POLICY_BUNDLE: "policy",
}


class BootArtifactError(RuntimeError):
    """Raised when bytes violate the PBART1 contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Artifact:
    role: int
    version: int
    payload: bytes
    payload_sha256: str
    file_sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def parse(data: bytes) -> Artifact:
    if len(data) < HEADER_BYTES:
        raise BootArtifactError("artifact_truncated")
    if len(data) > MAX_FILE_BYTES:
        raise BootArtifactError("artifact_oversized")
    if data[:8] != MAGIC:
        raise BootArtifactError("artifact_magic")
    major, minor, header_bytes, reserved = struct.unpack_from("<HHHH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        raise BootArtifactError("artifact_version")
    if header_bytes != HEADER_BYTES:
        raise BootArtifactError("artifact_header_size")
    if reserved != 0 or any(data[80:HEADER_BYTES]):
        raise BootArtifactError("artifact_reserved")
    role, flags = struct.unpack_from("<II", data, 16)
    if role not in ROLES:
        raise BootArtifactError("artifact_role")
    if flags != 0:
        raise BootArtifactError("artifact_flags")
    version, payload_bytes, image_bytes = struct.unpack_from("<QQQ", data, 24)
    if version == 0:
        raise BootArtifactError("artifact_payload_version")
    if payload_bytes == 0 or payload_bytes > MAX_PAYLOAD_BYTES:
        raise BootArtifactError("artifact_payload_size")
    if image_bytes != 0:
        raise BootArtifactError("artifact_image_size")
    expected_bytes = HEADER_BYTES + payload_bytes
    if len(data) < expected_bytes:
        raise BootArtifactError("artifact_truncated")
    if len(data) > expected_bytes:
        raise BootArtifactError("artifact_trailing_bytes")
    payload = data[HEADER_BYTES:]
    payload_digest = data[48:80].hex().upper()
    if sha256_bytes(payload) != payload_digest:
        raise BootArtifactError("artifact_digest")
    return Artifact(role, version, payload, payload_digest, sha256_bytes(data))


def parse_bound(data: bytes, role: int, version: int) -> Artifact:
    artifact = parse(data)
    if artifact.role != role:
        raise BootArtifactError("artifact_role_binding")
    if artifact.version != version:
        raise BootArtifactError("artifact_version_binding")
    return artifact


def encode(role: int, version: int, payload: bytes) -> bytes:
    if role not in ROLES:
        raise BootArtifactError("artifact_role")
    if version == 0:
        raise BootArtifactError("artifact_payload_version")
    if not payload or len(payload) > MAX_PAYLOAD_BYTES:
        raise BootArtifactError("artifact_payload_size")
    output = bytearray(HEADER_BYTES + len(payload))
    output[:8] = MAGIC
    struct.pack_into(
        "<HHHHIIQQQ",
        output,
        8,
        MAJOR_VERSION,
        MINOR_VERSION,
        HEADER_BYTES,
        0,
        role,
        0,
        version,
        len(payload),
        0,
    )
    output[48:80] = hashlib.sha256(payload).digest()
    output[HEADER_BYTES:] = payload
    result = bytes(output)
    parse_bound(result, role, version)
    return result


def canonical_payload(role: int) -> bytes:
    if role not in ROLES:
        raise BootArtifactError("artifact_role")
    return (
        "POOLEOS-PBART1-DEVELOPMENT/1\n"
        f"role={ROLE_NAMES[role]}\n"
        "semantics=not_applied\n"
    ).encode("ascii")


def canonical_artifacts(version: int = 1) -> dict[int, bytes]:
    return {role: encode(role, version, canonical_payload(role)) for role in ROLES}


def summary(data: bytes) -> dict[str, object]:
    artifact = parse(data)
    return {
        "contract_id": CONTRACT_ID,
        "role": artifact.role,
        "role_name": ROLE_NAMES[artifact.role],
        "version": artifact.version,
        "file_bytes": len(data),
        "payload_bytes": len(artifact.payload),
        "payload_sha256": artifact.payload_sha256,
        "file_sha256": artifact.file_sha256,
    }
