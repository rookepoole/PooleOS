"""Independent PMCU1 microcode package, selection, and verification oracle.

PMCU1 binds opaque processor-vendor patch bytes to exact CPU identity and
PooleOS policy.  This module deliberately has no privileged probe, MSR write,
firmware mutation, or physical-media path.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("specs/native-microcode-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-microcode-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-microcode-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-microcode-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_microcode_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-microcode-readiness.schema.json")

CONTRACT_ID: Final = "PMCU1"
MAGIC: Final = b"PMCU1\0\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 512
PATCH_RECORD_BYTES: Final = 128
MAX_BUNDLE_BYTES: Final = 1024 * 1024 - 128
MAX_PATCHES: Final = 32
MAX_PATCH_BYTES: Final = 512 * 1024
MAX_PROCESSORS: Final = 256
PAYLOAD_ALIGNMENT: Final = 16

PROFILE_EARLY_CPU_MICROCODE: Final = 1
ARCH_X86_64: Final = 1
VENDOR_AMD: Final = 1
CONTAINER_AMD_OPAQUE_SIGNED_PATCH: Final = 1
SELECTION_HIGHEST_ELIGIBLE: Final = 1
APPLY_KERNEL_EARLY: Final = 1
APPLY_EACH_PROCESSOR_BEFORE_ONLINE: Final = 1
RESUME_REAPPLY_IF_REQUIRED: Final = 1
ROLLBACK_RESET_THEN_KNOWN_GOOD: Final = 1
MIXED_REVISION_FATAL_OR_QUARANTINE: Final = 1
VERIFY_ALL_REVISIONS_AND_CPUID: Final = 1
FAIL_NO_USER_SCHEDULING: Final = 1

MODE_NORMAL: Final = 1
MODE_PREVIOUS_KNOWN_GOOD: Final = 2
DECISION_APPLY: Final = 1
DECISION_SKIP_CURRENT: Final = 2
DECISION_RESET_FOR_KNOWN_GOOD: Final = 3

FLAG_EXACT_CPU_IDENTITY: Final = 1 << 0
FLAG_OPAQUE_VENDOR_PAYLOAD: Final = 1 << 1
FLAG_PAYLOAD_DIGESTS: Final = 1 << 2
FLAG_SORTED_REVISIONS: Final = 1 << 3
FLAG_MONOTONIC_FLOOR: Final = 1 << 4
FLAG_OUTER_SIGNATURE: Final = 1 << 5
FLAG_INNER_SIGNATURE: Final = 1 << 6
FLAG_MANIFEST_SIGNATURE: Final = 1 << 7
FLAG_VENDOR_SIGNATURE: Final = 1 << 8
FLAG_EARLY_APPLY_ONLY: Final = 1 << 9
FLAG_ALL_PROCESSORS: Final = 1 << 10
FLAG_POST_APPLY_VERIFY: Final = 1 << 11
FLAG_CPUID_REEVALUATE: Final = 1 << 12
FLAG_NO_IN_SESSION_DOWNGRADE: Final = 1 << 13
FLAG_KNOWN_GOOD_RESET_FALLBACK: Final = 1 << 14
FLAG_MIXED_REVISION_FAIL_CLOSED: Final = 1 << 15
FLAG_RECEIPT_REQUIRED: Final = 1 << 16
FLAG_NO_AUTHORITY_FROM_PARSE: Final = 1 << 17
REQUIRED_FLAGS: Final = (1 << 18) - 1

PATCH_KNOWN_GOOD: Final = 1 << 0
PATCH_PREFERRED: Final = 1 << 1
PATCH_VENDOR_AUTH_REQUIRED: Final = 1 << 2
PATCH_EARLY_BSP: Final = 1 << 3
PATCH_EACH_AP: Final = 1 << 4
PATCH_REAPPLY_RESUME: Final = 1 << 5
PATCH_POST_VERIFY: Final = 1 << 6
PATCH_CPUID_REEVALUATE: Final = 1 << 7
PATCH_RECEIPT_REQUIRED: Final = 1 << 8
PATCH_REQUIRED_FLAGS: Final = (
    PATCH_VENDOR_AUTH_REQUIRED
    | PATCH_EARLY_BSP
    | PATCH_EACH_AP
    | PATCH_REAPPLY_RESUME
    | PATCH_POST_VERIFY
    | PATCH_CPUID_REEVALUATE
    | PATCH_RECEIPT_REQUIRED
)
PATCH_KNOWN_FLAGS: Final = PATCH_REQUIRED_FLAGS | PATCH_KNOWN_GOOD | PATCH_PREFERRED

TARGET_VENDOR_ID: Final = b"AuthenticAMD"
TARGET_CPUID_SIGNATURE: Final = 0x00B40F40
TARGET_CPUID_MASK: Final = 0xFFFF_FFFF
TARGET_PLATFORM_ID: Final = 0
TARGET_PLATFORM_MASK: Final = 0

# These revisions and payloads are visibly synthetic qualification data.  They
# are not observations or vendor releases and must never be applied.
SYNTHETIC_REVISION_BASE: Final = 0xF1A4_4000
CANONICAL_SECURITY_FLOOR: Final = SYNTHETIC_REVISION_BASE + 0x20
CANONICAL_KNOWN_GOOD_REVISION: Final = SYNTHETIC_REVISION_BASE + 0x20
CANONICAL_PREFERRED_REVISION: Final = SYNTHETIC_REVISION_BASE + 0x40

SOURCE_MANIFEST_SHA256: Final = hashlib.sha256(
    b"PMCU1 source-policy placeholder; production source intake remains open\n"
).hexdigest().upper()
TRUST_POLICY_SHA256: Final = hashlib.sha256(
    b"PMCU1 trust-policy placeholder; owner-approved trust roots remain open\n"
).hexdigest().upper()
LICENSE_POLICY_SHA256: Final = hashlib.sha256(
    b"PMCU1 redistribution unresolved; synthetic fixtures only\n"
).hexdigest().upper()
REVOCATION_POLICY_SHA256: Final = hashlib.sha256(
    b"PMCU1 revocation policy requires authenticated monotonic state\n"
).hexdigest().upper()
HARDWARE_PROFILE_SHA256: Final = hashlib.sha256(
    b"TIER1-B650M-9800X3D-RTX5070-001|AuthenticAMD|1A|44|0\n"
).hexdigest().upper()

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/microcode/Cargo.toml",
    "native/microcode/src/lib.rs",
    "native/microcode/src/bin/pmcu1_probe.rs",
    "runtime/native_microcode.py",
    "runtime/native_boot_artifact.py",
    "tools/generate_native_microcode_vectors.py",
    "tools/qualify_native_microcode.py",
    "tests/test_native_microcode.py",
    "docs/native-microcode-bundle.md",
)


class MicrocodeError(RuntimeError):
    """Raised when PMCU1 or its pure planning boundary fails closed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class PackageIdentity:
    source_manifest_sha256: str
    trust_policy_sha256: str
    license_policy_sha256: str
    revocation_policy_sha256: str
    hardware_profile_sha256: str


@dataclasses.dataclass(frozen=True)
class Patch:
    patch_id: int
    flags: int
    cpuid_signature: int
    cpuid_mask: int
    platform_id: int
    platform_mask: int
    revision: int
    minimum_current_revision: int
    security_revision_floor: int
    payload_offset: int
    payload_bytes: int
    payload_alignment: int
    vendor_header_bytes: int
    payload_sha256: str
    vendor_metadata_sha256: str
    payload: bytes


@dataclasses.dataclass(frozen=True)
class Bundle:
    raw: bytes
    flags: int
    profile: int
    architecture: int
    vendor: int
    container_profile: int
    target_cpuid_signature: int
    target_cpuid_mask: int
    vendor_id: bytes
    target_platform_id: int
    target_platform_mask: int
    security_revision_floor: int
    known_good_revision: int
    preferred_revision: int
    identity: PackageIdentity
    body_sha256: str
    header_sha256: str
    patches: tuple[Patch, ...]


@dataclasses.dataclass(frozen=True)
class Selection:
    decision: int
    patch: Patch | None
    current_revision: int
    required_floor: int


@dataclasses.dataclass(frozen=True)
class ApplyContext:
    outer_role: int
    outer_version: int
    outer_payload_sha256: str
    outer_file_sha256: str
    expected_outer_file_sha256: str
    outer_signature_verified: bool
    inner_signature_verified: bool
    manifest_signature_verified: bool
    vendor_signature_verified: bool
    vendor_container_validated: bool
    vendor_source_trusted: bool
    redistribution_authorized: bool
    revocation_state_authenticated: bool
    target_hardware_evidence_verified: bool
    cpuid_observation_trusted: bool
    revision_observation_trusted: bool
    vendor_id: bytes
    cpuid_signature: int
    platform_id: int
    current_revisions: tuple[int, ...]
    authenticated_rollback_floor: int
    boot_mode: int
    executor_stage: int
    before_affected_features: bool
    before_user_scheduling: bool
    processor_inventory_complete: bool
    processor_set_quiesced: bool
    payload_capacity: int
    patch_capacity: int
    processor_capacity: int
    receipt_capacity: int
    apply_authority_granted: bool
    firmware_mutation_requested: bool
    physical_media_write_requested: bool
    qualification_only: bool


@dataclasses.dataclass(frozen=True)
class PostApplyObservation:
    patch_id: int
    target_revision: int
    before_revisions: tuple[int, ...]
    after_revisions: tuple[int, ...]
    cpuid_signature_before: int
    cpuid_signature_after: int
    cpuid_evidence_before_sha256: str
    cpuid_evidence_after_sha256: str
    feature_policy_revalidated: bool
    mitigation_policy_revalidated: bool
    receipt_persisted: bool
    mixed_failure_quarantined: bool
    user_scheduling_started: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _digest_bytes(value: str) -> bytes:
    if len(value) != 64:
        raise MicrocodeError("pmcu_identity")
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise MicrocodeError("pmcu_identity") from error
    if result == bytes(32):
        raise MicrocodeError("pmcu_identity")
    return result


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _checked_end(offset: int, size: int, limit: int, code: str) -> int:
    if offset < 0 or size < 0 or offset > limit or size > limit - offset:
        raise MicrocodeError(code)
    return offset + size


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _metadata_digest(record: bytes) -> str:
    return _sha256(record[:96])


def _synthetic_payload(label: str, byte_count: int) -> bytes:
    prefix = (
        b"POOLEOS PMCU1 SYNTHETIC TEST PAYLOAD - NEVER APPLY\0"
        + label.encode("ascii")
        + b"\0"
    )
    output = bytearray(prefix)
    counter = 0
    while len(output) < byte_count:
        output.extend(hashlib.sha256(prefix + struct.pack("<I", counter)).digest())
        counter += 1
    return bytes(output[:byte_count])


def make_patch(
    patch_id: int,
    revision: int,
    payload: bytes,
    *,
    known_good: bool = False,
    preferred: bool = False,
    minimum_current_revision: int = 0,
    security_revision_floor: int = CANONICAL_SECURITY_FLOOR,
) -> Patch:
    flags = PATCH_REQUIRED_FLAGS
    if known_good:
        flags |= PATCH_KNOWN_GOOD
    if preferred:
        flags |= PATCH_PREFERRED
    return Patch(
        patch_id=patch_id,
        flags=flags,
        cpuid_signature=TARGET_CPUID_SIGNATURE,
        cpuid_mask=TARGET_CPUID_MASK,
        platform_id=TARGET_PLATFORM_ID,
        platform_mask=TARGET_PLATFORM_MASK,
        revision=revision,
        minimum_current_revision=minimum_current_revision,
        security_revision_floor=security_revision_floor,
        payload_offset=0,
        payload_bytes=len(payload),
        payload_alignment=PAYLOAD_ALIGNMENT,
        vendor_header_bytes=0,
        payload_sha256=_sha256(payload),
        vendor_metadata_sha256="0" * 64,
        payload=payload,
    )


def canonical_patches() -> tuple[Patch, ...]:
    return (
        make_patch(
            1,
            CANONICAL_KNOWN_GOOD_REVISION,
            _synthetic_payload("known-good", 256),
            known_good=True,
        ),
        make_patch(
            2,
            CANONICAL_PREFERRED_REVISION,
            _synthetic_payload("preferred", 384),
            preferred=True,
        ),
    )


def encode(
    patches: Sequence[Patch],
    *,
    security_revision_floor: int,
    known_good_revision: int,
    preferred_revision: int,
    identity: PackageIdentity | None = None,
) -> bytes:
    if not 1 <= len(patches) <= MAX_PATCHES:
        raise MicrocodeError("pmcu_counts")
    identity = identity or PackageIdentity(
        SOURCE_MANIFEST_SHA256,
        TRUST_POLICY_SHA256,
        LICENSE_POLICY_SHA256,
        REVOCATION_POLICY_SHA256,
        HARDWARE_PROFILE_SHA256,
    )
    records_offset = HEADER_BYTES
    payload_offset = records_offset + len(patches) * PATCH_RECORD_BYTES
    payload_cursor = payload_offset
    records = bytearray(len(patches) * PATCH_RECORD_BYTES)
    payload_region = bytearray()
    for index, source in enumerate(patches):
        if source.payload_bytes != len(source.payload) or not source.payload:
            raise MicrocodeError("pmcu_patch_size")
        if len(source.payload) > MAX_PATCH_BYTES:
            raise MicrocodeError("pmcu_patch_size")
        if payload_cursor % PAYLOAD_ALIGNMENT:
            padding = PAYLOAD_ALIGNMENT - payload_cursor % PAYLOAD_ALIGNMENT
            payload_region.extend(bytes(padding))
            payload_cursor += padding
        offset = index * PATCH_RECORD_BYTES
        struct.pack_into(
            "<IIIIIIIII IQQII",
            records,
            offset,
            source.patch_id,
            source.flags,
            source.cpuid_signature,
            source.cpuid_mask,
            source.platform_id,
            source.platform_mask,
            source.revision,
            source.minimum_current_revision,
            source.security_revision_floor,
            0,
            payload_cursor,
            len(source.payload),
            source.payload_alignment,
            source.vendor_header_bytes,
        )
        payload_digest = hashlib.sha256(source.payload).digest()
        records[offset + 64 : offset + 96] = payload_digest
        records[offset + 96 : offset + 128] = hashlib.sha256(
            records[offset : offset + 96]
        ).digest()
        payload_region.extend(source.payload)
        payload_cursor += len(source.payload)
    total_bytes = payload_offset + len(payload_region)
    if total_bytes > MAX_BUNDLE_BYTES:
        raise MicrocodeError("pmcu_oversized")
    body = bytes(records) + bytes(payload_region)
    header = bytearray(HEADER_BYTES)
    header[:8] = MAGIC
    struct.pack_into("<HHIII", header, 8, MAJOR_VERSION, MINOR_VERSION, HEADER_BYTES, PATCH_RECORD_BYTES, REQUIRED_FLAGS)
    struct.pack_into(
        "<HHHHIIQQQQII",
        header,
        24,
        PROFILE_EARLY_CPU_MICROCODE,
        ARCH_X86_64,
        VENDOR_AMD,
        CONTAINER_AMD_OPAQUE_SIGNED_PATCH,
        len(patches),
        MAX_PATCHES,
        total_bytes,
        records_offset,
        payload_offset,
        len(payload_region),
        TARGET_CPUID_SIGNATURE,
        TARGET_CPUID_MASK,
    )
    header[80:92] = TARGET_VENDOR_ID
    struct.pack_into(
        "<IIIIIHHHHHHHH",
        header,
        92,
        TARGET_PLATFORM_ID,
        TARGET_PLATFORM_MASK,
        security_revision_floor,
        known_good_revision,
        preferred_revision,
        SELECTION_HIGHEST_ELIGIBLE,
        APPLY_KERNEL_EARLY,
        APPLY_EACH_PROCESSOR_BEFORE_ONLINE,
        RESUME_REAPPLY_IF_REQUIRED,
        ROLLBACK_RESET_THEN_KNOWN_GOOD,
        MIXED_REVISION_FATAL_OR_QUARANTINE,
        VERIFY_ALL_REVISIONS_AND_CPUID,
        FAIL_NO_USER_SCHEDULING,
    )
    for offset, value in zip(
        (128, 160, 192, 224, 256),
        dataclasses.astuple(identity),
        strict=True,
    ):
        header[offset : offset + 32] = _digest_bytes(value)
    header[288:320] = hashlib.sha256(body).digest()
    header[320:352] = bytes(32)
    header[320:352] = hashlib.sha256(header).digest()
    return bytes(header) + body


def _parse_patch(data: bytes, offset: int, bundle_limit: int) -> Patch:
    (
        patch_id,
        flags,
        cpuid_signature,
        cpuid_mask,
        platform_id,
        platform_mask,
        revision,
        minimum_current_revision,
        security_revision_floor,
        reserved,
        payload_offset,
        payload_bytes,
        payload_alignment,
        vendor_header_bytes,
    ) = struct.unpack_from("<IIIIIIIII IQQII", data, offset)
    if reserved:
        raise MicrocodeError("pmcu_reserved")
    if flags & ~PATCH_KNOWN_FLAGS or flags & PATCH_REQUIRED_FLAGS != PATCH_REQUIRED_FLAGS:
        raise MicrocodeError("pmcu_patch_flags")
    if cpuid_signature != TARGET_CPUID_SIGNATURE or cpuid_mask != TARGET_CPUID_MASK:
        raise MicrocodeError("pmcu_patch_identity")
    if platform_id != TARGET_PLATFORM_ID or platform_mask != TARGET_PLATFORM_MASK:
        raise MicrocodeError("pmcu_patch_identity")
    if revision == 0 or minimum_current_revision >= revision:
        raise MicrocodeError("pmcu_patch_revision")
    if security_revision_floor == 0 or security_revision_floor > revision:
        raise MicrocodeError("pmcu_patch_floor")
    if payload_alignment != PAYLOAD_ALIGNMENT or not _is_power_of_two(payload_alignment):
        raise MicrocodeError("pmcu_patch_alignment")
    if payload_offset % payload_alignment:
        raise MicrocodeError("pmcu_patch_alignment")
    if payload_bytes == 0 or payload_bytes > MAX_PATCH_BYTES:
        raise MicrocodeError("pmcu_patch_size")
    payload_end = _checked_end(payload_offset, payload_bytes, bundle_limit, "pmcu_patch_layout")
    payload = data[payload_offset:payload_end]
    payload_sha256 = data[offset + 64 : offset + 96].hex().upper()
    if _sha256(payload) != payload_sha256:
        raise MicrocodeError("pmcu_patch_digest")
    vendor_metadata_sha256 = data[offset + 96 : offset + 128].hex().upper()
    if _metadata_digest(data[offset : offset + PATCH_RECORD_BYTES]) != vendor_metadata_sha256:
        raise MicrocodeError("pmcu_patch_metadata_digest")
    return Patch(
        patch_id,
        flags,
        cpuid_signature,
        cpuid_mask,
        platform_id,
        platform_mask,
        revision,
        minimum_current_revision,
        security_revision_floor,
        payload_offset,
        payload_bytes,
        payload_alignment,
        vendor_header_bytes,
        payload_sha256,
        vendor_metadata_sha256,
        payload,
    )


def parse(data: bytes) -> Bundle:
    if len(data) < HEADER_BYTES:
        raise MicrocodeError("pmcu_truncated")
    if len(data) > MAX_BUNDLE_BYTES:
        raise MicrocodeError("pmcu_oversized")
    if data[:8] != MAGIC:
        raise MicrocodeError("pmcu_magic")
    if (_u16(data, 8), _u16(data, 10)) != (MAJOR_VERSION, MINOR_VERSION):
        raise MicrocodeError("pmcu_version")
    if _u32(data, 12) != HEADER_BYTES:
        raise MicrocodeError("pmcu_header_size")
    if _u32(data, 16) != PATCH_RECORD_BYTES:
        raise MicrocodeError("pmcu_record_size")
    flags = _u32(data, 20)
    if flags != REQUIRED_FLAGS:
        raise MicrocodeError("pmcu_flags")
    profile, architecture, vendor, container_profile = struct.unpack_from("<HHHH", data, 24)
    if profile != PROFILE_EARLY_CPU_MICROCODE:
        raise MicrocodeError("pmcu_profile")
    if architecture != ARCH_X86_64:
        raise MicrocodeError("pmcu_architecture")
    if vendor != VENDOR_AMD:
        raise MicrocodeError("pmcu_vendor")
    if container_profile != CONTAINER_AMD_OPAQUE_SIGNED_PATCH:
        raise MicrocodeError("pmcu_container_profile")
    patch_count = _u32(data, 32)
    if not 1 <= patch_count <= MAX_PATCHES or _u32(data, 36) != MAX_PATCHES:
        raise MicrocodeError("pmcu_counts")
    total_bytes = _u64(data, 40)
    records_offset = _u64(data, 48)
    payload_offset = _u64(data, 56)
    payload_bytes = _u64(data, 64)
    if total_bytes != len(data):
        raise MicrocodeError("pmcu_total_size")
    expected_payload_offset = HEADER_BYTES + patch_count * PATCH_RECORD_BYTES
    if records_offset != HEADER_BYTES or payload_offset != expected_payload_offset:
        raise MicrocodeError("pmcu_table_layout")
    if payload_bytes != len(data) - payload_offset or payload_bytes == 0:
        raise MicrocodeError("pmcu_payload_size")
    target_cpuid_signature = _u32(data, 72)
    target_cpuid_mask = _u32(data, 76)
    vendor_id = data[80:92]
    target_platform_id = _u32(data, 92)
    target_platform_mask = _u32(data, 96)
    if (target_cpuid_signature, target_cpuid_mask) != (
        TARGET_CPUID_SIGNATURE,
        TARGET_CPUID_MASK,
    ):
        raise MicrocodeError("pmcu_target_identity")
    if vendor_id != TARGET_VENDOR_ID:
        raise MicrocodeError("pmcu_vendor_id")
    if (target_platform_id, target_platform_mask) != (
        TARGET_PLATFORM_ID,
        TARGET_PLATFORM_MASK,
    ):
        raise MicrocodeError("pmcu_platform")
    security_revision_floor = _u32(data, 100)
    known_good_revision = _u32(data, 104)
    preferred_revision = _u32(data, 108)
    if (
        security_revision_floor == 0
        or known_good_revision < security_revision_floor
        or preferred_revision < known_good_revision
    ):
        raise MicrocodeError("pmcu_floor")
    policies = struct.unpack_from("<HHHHHHHH", data, 112)
    if policies != (
        SELECTION_HIGHEST_ELIGIBLE,
        APPLY_KERNEL_EARLY,
        APPLY_EACH_PROCESSOR_BEFORE_ONLINE,
        RESUME_REAPPLY_IF_REQUIRED,
        ROLLBACK_RESET_THEN_KNOWN_GOOD,
        MIXED_REVISION_FATAL_OR_QUARANTINE,
        VERIFY_ALL_REVISIONS_AND_CPUID,
        FAIL_NO_USER_SCHEDULING,
    ):
        raise MicrocodeError("pmcu_policy")
    identity_values = tuple(data[offset : offset + 32].hex().upper() for offset in (128, 160, 192, 224, 256))
    if any(value == "0" * 64 for value in identity_values):
        raise MicrocodeError("pmcu_identity")
    if data[352:HEADER_BYTES] != bytes(HEADER_BYTES - 352):
        raise MicrocodeError("pmcu_reserved")
    if _sha256(data[HEADER_BYTES:]) != data[288:320].hex().upper():
        raise MicrocodeError("pmcu_body_digest")
    header = bytearray(data[:HEADER_BYTES])
    observed_header_digest = bytes(header[320:352])
    header[320:352] = bytes(32)
    if hashlib.sha256(header).digest() != observed_header_digest:
        raise MicrocodeError("pmcu_header_digest")
    patches = tuple(
        _parse_patch(data, HEADER_BYTES + index * PATCH_RECORD_BYTES, len(data))
        for index in range(patch_count)
    )
    previous_revision = 0
    expected_payload_cursor = payload_offset
    known_good_count = 0
    preferred_count = 0
    for index, patch in enumerate(patches, start=1):
        if patch.patch_id != index:
            raise MicrocodeError("pmcu_patch_id")
        if patch.revision <= previous_revision:
            raise MicrocodeError("pmcu_patch_order")
        if patch.security_revision_floor != security_revision_floor:
            raise MicrocodeError("pmcu_patch_floor")
        if patch.payload_offset != expected_payload_cursor:
            raise MicrocodeError("pmcu_payload_coverage")
        expected_payload_cursor += patch.payload_bytes
        previous_revision = patch.revision
        known_good_count += int(bool(patch.flags & PATCH_KNOWN_GOOD))
        preferred_count += int(bool(patch.flags & PATCH_PREFERRED))
        if patch.flags & PATCH_KNOWN_GOOD and patch.revision != known_good_revision:
            raise MicrocodeError("pmcu_patch_role")
        if patch.flags & PATCH_PREFERRED and patch.revision != preferred_revision:
            raise MicrocodeError("pmcu_patch_role")
    if expected_payload_cursor != len(data):
        raise MicrocodeError("pmcu_payload_coverage")
    if known_good_count != 1 or preferred_count != 1:
        raise MicrocodeError("pmcu_patch_role")
    return Bundle(
        data,
        flags,
        profile,
        architecture,
        vendor,
        container_profile,
        target_cpuid_signature,
        target_cpuid_mask,
        vendor_id,
        target_platform_id,
        target_platform_mask,
        security_revision_floor,
        known_good_revision,
        preferred_revision,
        PackageIdentity(*identity_values),
        data[288:320].hex().upper(),
        data[320:352].hex().upper(),
        patches,
    )


def _matches(patch: Patch, cpuid_signature: int, platform_id: int) -> bool:
    return (
        cpuid_signature & patch.cpuid_mask
        == patch.cpuid_signature & patch.cpuid_mask
        and (
            patch.platform_mask == 0
            or platform_id & patch.platform_mask == patch.platform_id & patch.platform_mask
        )
    )


def select_patch(
    bundle: Bundle,
    *,
    cpuid_signature: int,
    platform_id: int,
    current_revision: int,
    authenticated_rollback_floor: int,
    boot_mode: int,
    revoked_revisions: Iterable[int] = (),
) -> Selection:
    if cpuid_signature != bundle.target_cpuid_signature:
        raise MicrocodeError("pmcu_select_cpuid")
    if bundle.target_platform_mask and (
        platform_id & bundle.target_platform_mask
        != bundle.target_platform_id & bundle.target_platform_mask
    ):
        raise MicrocodeError("pmcu_select_platform")
    if boot_mode not in (MODE_NORMAL, MODE_PREVIOUS_KNOWN_GOOD):
        raise MicrocodeError("pmcu_select_mode")
    revoked = frozenset(revoked_revisions)
    required_floor = max(bundle.security_revision_floor, authenticated_rollback_floor)
    if required_floor > bundle.preferred_revision:
        raise MicrocodeError("pmcu_select_rollback_floor")
    matching = tuple(
        patch
        for patch in bundle.patches
        if _matches(patch, cpuid_signature, platform_id)
        and patch.revision >= required_floor
        and patch.revision not in revoked
        and current_revision >= patch.minimum_current_revision
    )
    if not matching:
        if current_revision >= required_floor and current_revision not in revoked:
            return Selection(DECISION_SKIP_CURRENT, None, current_revision, required_floor)
        raise MicrocodeError("pmcu_select_no_eligible")
    if boot_mode == MODE_PREVIOUS_KNOWN_GOOD:
        known_good = next(
            (patch for patch in matching if patch.flags & PATCH_KNOWN_GOOD), None
        )
        if known_good is None:
            raise MicrocodeError("pmcu_select_no_known_good")
        if current_revision > known_good.revision:
            return Selection(
                DECISION_RESET_FOR_KNOWN_GOOD, known_good, current_revision, required_floor
            )
        if current_revision == known_good.revision:
            return Selection(DECISION_SKIP_CURRENT, known_good, current_revision, required_floor)
        return Selection(DECISION_APPLY, known_good, current_revision, required_floor)
    preferred = max(matching, key=lambda patch: patch.revision)
    if current_revision >= preferred.revision:
        if current_revision in revoked:
            raise MicrocodeError("pmcu_select_current_revoked")
        return Selection(DECISION_SKIP_CURRENT, preferred, current_revision, required_floor)
    return Selection(DECISION_APPLY, preferred, current_revision, required_floor)


def summary(bundle: Bundle) -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "version": f"{MAJOR_VERSION}.{MINOR_VERSION}",
        "bundle_bytes": len(bundle.raw),
        "patch_count": len(bundle.patches),
        "vendor_id": bundle.vendor_id.decode("ascii"),
        "target_cpuid_signature": f"0x{bundle.target_cpuid_signature:08X}",
        "security_revision_floor": bundle.security_revision_floor,
        "known_good_revision": bundle.known_good_revision,
        "preferred_revision": bundle.preferred_revision,
        "body_sha256": bundle.body_sha256,
    }


def development_apply_context(
    bundle: Bundle,
    *,
    outer_file_sha256: str = "0" * 64,
) -> ApplyContext:
    return ApplyContext(
        outer_role=5,
        outer_version=1,
        outer_payload_sha256=_sha256(bundle.raw),
        outer_file_sha256=outer_file_sha256,
        expected_outer_file_sha256=outer_file_sha256,
        outer_signature_verified=False,
        inner_signature_verified=False,
        manifest_signature_verified=False,
        vendor_signature_verified=False,
        vendor_container_validated=False,
        vendor_source_trusted=False,
        redistribution_authorized=False,
        revocation_state_authenticated=False,
        target_hardware_evidence_verified=False,
        cpuid_observation_trusted=False,
        revision_observation_trusted=False,
        vendor_id=bundle.vendor_id,
        cpuid_signature=bundle.target_cpuid_signature,
        platform_id=bundle.target_platform_id,
        current_revisions=(SYNTHETIC_REVISION_BASE + 0x10,),
        authenticated_rollback_floor=bundle.security_revision_floor,
        boot_mode=MODE_NORMAL,
        executor_stage=APPLY_KERNEL_EARLY,
        before_affected_features=True,
        before_user_scheduling=True,
        processor_inventory_complete=True,
        processor_set_quiesced=True,
        payload_capacity=len(bundle.raw),
        patch_capacity=len(bundle.patches),
        processor_capacity=1,
        receipt_capacity=1,
        apply_authority_granted=False,
        firmware_mutation_requested=False,
        physical_media_write_requested=False,
        qualification_only=True,
    )


def synthetic_qualified_apply_context(
    bundle: Bundle,
    *,
    outer_file_sha256: str | None = None,
) -> ApplyContext:
    file_digest = outer_file_sha256 or _sha256(b"synthetic-pbart1:" + bundle.raw)
    return ApplyContext(
        outer_role=5,
        outer_version=1,
        outer_payload_sha256=_sha256(bundle.raw),
        outer_file_sha256=file_digest,
        expected_outer_file_sha256=file_digest,
        outer_signature_verified=True,
        inner_signature_verified=True,
        manifest_signature_verified=True,
        vendor_signature_verified=True,
        vendor_container_validated=True,
        vendor_source_trusted=True,
        redistribution_authorized=True,
        revocation_state_authenticated=True,
        target_hardware_evidence_verified=True,
        cpuid_observation_trusted=True,
        revision_observation_trusted=True,
        vendor_id=bundle.vendor_id,
        cpuid_signature=bundle.target_cpuid_signature,
        platform_id=bundle.target_platform_id,
        current_revisions=(SYNTHETIC_REVISION_BASE + 0x10,),
        authenticated_rollback_floor=bundle.security_revision_floor,
        boot_mode=MODE_NORMAL,
        executor_stage=APPLY_KERNEL_EARLY,
        before_affected_features=True,
        before_user_scheduling=True,
        processor_inventory_complete=True,
        processor_set_quiesced=True,
        payload_capacity=len(bundle.raw),
        patch_capacity=len(bundle.patches),
        processor_capacity=1,
        receipt_capacity=1,
        apply_authority_granted=True,
        firmware_mutation_requested=False,
        physical_media_write_requested=False,
        qualification_only=True,
    )


def apply_plan_errors(bundle: Bundle, context: ApplyContext) -> list[str]:
    errors: list[str] = []
    checks = (
        (context.outer_signature_verified, "pmcu_activation_outer_signature"),
        (context.inner_signature_verified, "pmcu_activation_inner_signature"),
        (context.manifest_signature_verified, "pmcu_activation_manifest_signature"),
        (context.vendor_signature_verified, "pmcu_activation_vendor_signature"),
        (context.vendor_container_validated, "pmcu_activation_vendor_container"),
        (context.vendor_source_trusted, "pmcu_activation_vendor_source"),
        (context.redistribution_authorized, "pmcu_activation_redistribution"),
        (context.revocation_state_authenticated, "pmcu_activation_revocation_state"),
        (context.target_hardware_evidence_verified, "pmcu_activation_hardware_evidence"),
        (context.cpuid_observation_trusted, "pmcu_activation_cpuid_observation"),
        (context.revision_observation_trusted, "pmcu_activation_revision_observation"),
    )
    errors.extend(code for passed, code in checks if not passed)
    if context.outer_role != 5:
        errors.append("pmcu_activation_outer_role")
    if context.outer_version != 1:
        errors.append("pmcu_activation_outer_version")
    if context.outer_payload_sha256 != _sha256(bundle.raw):
        errors.append("pmcu_activation_outer_payload_digest")
    if context.outer_file_sha256 != context.expected_outer_file_sha256:
        errors.append("pmcu_activation_outer_file_digest")
    if context.vendor_id != bundle.vendor_id:
        errors.append("pmcu_activation_vendor_id")
    if context.cpuid_signature != bundle.target_cpuid_signature:
        errors.append("pmcu_activation_cpuid")
    if context.platform_id != bundle.target_platform_id:
        errors.append("pmcu_activation_platform")
    if not 1 <= len(context.current_revisions) <= MAX_PROCESSORS:
        errors.append("pmcu_activation_processor_count")
    elif len(set(context.current_revisions)) != 1:
        errors.append("pmcu_activation_mixed_before")
    if context.authenticated_rollback_floor < bundle.security_revision_floor:
        errors.append("pmcu_activation_rollback_floor")
    if context.boot_mode not in (MODE_NORMAL, MODE_PREVIOUS_KNOWN_GOOD):
        errors.append("pmcu_activation_boot_mode")
    if context.executor_stage != APPLY_KERNEL_EARLY:
        errors.append("pmcu_activation_stage")
    if not context.before_affected_features:
        errors.append("pmcu_activation_feature_timing")
    if not context.before_user_scheduling:
        errors.append("pmcu_activation_schedule_timing")
    if not context.processor_inventory_complete:
        errors.append("pmcu_activation_processor_inventory")
    if not context.processor_set_quiesced:
        errors.append("pmcu_activation_quiescence")
    if context.payload_capacity < len(bundle.raw):
        errors.append("pmcu_activation_payload_capacity")
    if context.patch_capacity < len(bundle.patches):
        errors.append("pmcu_activation_patch_capacity")
    if context.processor_capacity < len(context.current_revisions):
        errors.append("pmcu_activation_processor_capacity")
    if context.receipt_capacity < len(context.current_revisions):
        errors.append("pmcu_activation_receipt_capacity")
    if not context.apply_authority_granted:
        errors.append("pmcu_activation_apply_authority")
    if context.firmware_mutation_requested:
        errors.append("pmcu_activation_firmware_mutation")
    if context.physical_media_write_requested:
        errors.append("pmcu_activation_physical_media")
    if not context.qualification_only:
        errors.append("pmcu_activation_not_implemented")
    return errors


def authorize_apply_plan(
    bundle: Bundle,
    context: ApplyContext,
    *,
    revoked_revisions: Iterable[int] = (),
) -> Selection:
    errors = apply_plan_errors(bundle, context)
    if errors:
        raise MicrocodeError(errors[0])
    return select_patch(
        bundle,
        cpuid_signature=context.cpuid_signature,
        platform_id=context.platform_id,
        current_revision=context.current_revisions[0],
        authenticated_rollback_floor=context.authenticated_rollback_floor,
        boot_mode=context.boot_mode,
        revoked_revisions=revoked_revisions,
    )


def post_apply_errors(
    bundle: Bundle,
    selection: Selection,
    observation: PostApplyObservation,
    *,
    revoked_revisions: Iterable[int] = (),
) -> list[str]:
    errors: list[str] = []
    if selection.decision != DECISION_APPLY or selection.patch is None:
        return ["pmcu_verify_decision"]
    patch = selection.patch
    if (observation.patch_id, observation.target_revision) != (
        patch.patch_id,
        patch.revision,
    ):
        errors.append("pmcu_verify_patch")
    if not 1 <= len(observation.before_revisions) <= MAX_PROCESSORS:
        errors.append("pmcu_verify_processor_count")
    if len(observation.before_revisions) != len(observation.after_revisions):
        errors.append("pmcu_verify_processor_count")
    if len(set(observation.before_revisions)) != 1:
        errors.append("pmcu_verify_mixed_before")
    after_mixed = len(set(observation.after_revisions)) != 1
    if after_mixed and not observation.mixed_failure_quarantined:
        errors.append("pmcu_verify_mixed_quarantine")
    if after_mixed:
        errors.append("pmcu_verify_mixed_after")
    required_floor = max(bundle.security_revision_floor, selection.required_floor)
    revoked = frozenset(revoked_revisions)
    for before, after in zip(
        observation.before_revisions, observation.after_revisions, strict=False
    ):
        if after < before or after < patch.revision or after < required_floor:
            errors.append("pmcu_verify_revision")
            break
        if after in revoked:
            errors.append("pmcu_verify_revoked")
            break
    if observation.cpuid_signature_before != bundle.target_cpuid_signature:
        errors.append("pmcu_verify_cpuid_before")
    if observation.cpuid_signature_after != bundle.target_cpuid_signature:
        errors.append("pmcu_verify_cpuid_after")
    for value, code in (
        (observation.cpuid_evidence_before_sha256, "pmcu_verify_cpuid_evidence_before"),
        (observation.cpuid_evidence_after_sha256, "pmcu_verify_cpuid_evidence_after"),
    ):
        try:
            _digest_bytes(value)
        except MicrocodeError:
            errors.append(code)
    if not observation.feature_policy_revalidated:
        errors.append("pmcu_verify_feature_policy")
    if not observation.mitigation_policy_revalidated:
        errors.append("pmcu_verify_mitigation_policy")
    if not observation.receipt_persisted:
        errors.append("pmcu_verify_receipt")
    if observation.user_scheduling_started:
        errors.append("pmcu_verify_schedule_started")
    return errors


def verify_post_apply(
    bundle: Bundle,
    selection: Selection,
    observation: PostApplyObservation,
    *,
    revoked_revisions: Iterable[int] = (),
) -> None:
    errors = post_apply_errors(
        bundle, selection, observation, revoked_revisions=revoked_revisions
    )
    if errors:
        raise MicrocodeError(errors[0])


def canonical_bundle() -> bytes:
    return encode(
        canonical_patches(),
        security_revision_floor=CANONICAL_SECURITY_FLOOR,
        known_good_revision=CANONICAL_KNOWN_GOOD_REVISION,
        preferred_revision=CANONICAL_PREFERRED_REVISION,
    )


def minimal_bundle() -> bytes:
    revision = SYNTHETIC_REVISION_BASE + 1
    patch = make_patch(
        1,
        revision,
        _synthetic_payload("minimal", 128),
        known_good=True,
        preferred=True,
        security_revision_floor=revision,
    )
    return encode(
        (patch,),
        security_revision_floor=revision,
        known_good_revision=revision,
        preferred_revision=revision,
    )


def boundary_bundle() -> bytes:
    floor = SYNTHETIC_REVISION_BASE + 1
    patches = tuple(
        make_patch(
            index,
            SYNTHETIC_REVISION_BASE + index,
            _synthetic_payload(f"boundary-{index:02d}", 16),
            known_good=index == 16,
            preferred=index == MAX_PATCHES,
            security_revision_floor=floor,
        )
        for index in range(1, MAX_PATCHES + 1)
    )
    return encode(
        patches,
        security_revision_floor=floor,
        known_good_revision=SYNTHETIC_REVISION_BASE + 16,
        preferred_revision=SYNTHETIC_REVISION_BASE + MAX_PATCHES,
    )


def _selection_summary(selection: Selection) -> dict[str, Any]:
    labels = {
        DECISION_APPLY: "apply",
        DECISION_SKIP_CURRENT: "skip_current",
        DECISION_RESET_FOR_KNOWN_GOOD: "reset_for_known_good",
    }
    return {
        "decision": labels[selection.decision],
        "patch_id": selection.patch.patch_id if selection.patch else None,
        "revision": selection.patch.revision if selection.patch else None,
        "current_revision": selection.current_revision,
        "required_floor": selection.required_floor,
    }


def _vector(bundle_id: str, data: bytes, samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    parsed = parse(data)
    output_samples: list[dict[str, Any]] = []
    for sample in samples:
        selection = select_patch(
            parsed,
            cpuid_signature=sample["cpuid_signature"],
            platform_id=sample["platform_id"],
            current_revision=sample["current_revision"],
            authenticated_rollback_floor=sample["authenticated_rollback_floor"],
            boot_mode=sample["boot_mode"],
            revoked_revisions=sample.get("revoked_revisions", ()),
        )
        output_samples.append({**sample, "expected": _selection_summary(selection)})
    return {
        "id": bundle_id,
        "bundle_bytes": len(data),
        "bundle_sha256": _sha256(data),
        "bundle_hex": data.hex().upper(),
        "patch_count": len(parsed.patches),
        "security_revision_floor": parsed.security_revision_floor,
        "known_good_revision": parsed.known_good_revision,
        "preferred_revision": parsed.preferred_revision,
        "selection_samples": output_samples,
    }


def make_golden_vectors() -> dict[str, Any]:
    canonical = canonical_bundle()
    minimal = minimal_bundle()
    boundary = boundary_bundle()
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_microcode_golden_vectors",
        "contract_id": CONTRACT_ID,
        "synthetic_test_payloads_only": True,
        "vectors": [
            _vector(
                "PMCU1-CANONICAL",
                canonical,
                (
                    {
                        "cpuid_signature": TARGET_CPUID_SIGNATURE,
                        "platform_id": 0,
                        "current_revision": SYNTHETIC_REVISION_BASE + 0x10,
                        "authenticated_rollback_floor": CANONICAL_SECURITY_FLOOR,
                        "boot_mode": MODE_NORMAL,
                        "revoked_revisions": [],
                    },
                    {
                        "cpuid_signature": TARGET_CPUID_SIGNATURE,
                        "platform_id": 0,
                        "current_revision": CANONICAL_PREFERRED_REVISION,
                        "authenticated_rollback_floor": CANONICAL_SECURITY_FLOOR,
                        "boot_mode": MODE_NORMAL,
                        "revoked_revisions": [],
                    },
                    {
                        "cpuid_signature": TARGET_CPUID_SIGNATURE,
                        "platform_id": 0,
                        "current_revision": CANONICAL_PREFERRED_REVISION,
                        "authenticated_rollback_floor": CANONICAL_SECURITY_FLOOR,
                        "boot_mode": MODE_PREVIOUS_KNOWN_GOOD,
                        "revoked_revisions": [CANONICAL_PREFERRED_REVISION],
                    },
                ),
            ),
            _vector(
                "PMCU1-MINIMAL",
                minimal,
                (
                    {
                        "cpuid_signature": TARGET_CPUID_SIGNATURE,
                        "platform_id": 0,
                        "current_revision": SYNTHETIC_REVISION_BASE,
                        "authenticated_rollback_floor": SYNTHETIC_REVISION_BASE + 1,
                        "boot_mode": MODE_NORMAL,
                        "revoked_revisions": [],
                    },
                ),
            ),
            _vector(
                "PMCU1-BOUNDARY",
                boundary,
                (
                    {
                        "cpuid_signature": TARGET_CPUID_SIGNATURE,
                        "platform_id": 0,
                        "current_revision": SYNTHETIC_REVISION_BASE,
                        "authenticated_rollback_floor": SYNTHETIC_REVISION_BASE + 1,
                        "boot_mode": MODE_NORMAL,
                        "revoked_revisions": [],
                    },
                    {
                        "cpuid_signature": TARGET_CPUID_SIGNATURE,
                        "platform_id": 0,
                        "current_revision": SYNTHETIC_REVISION_BASE + 20,
                        "authenticated_rollback_floor": SYNTHETIC_REVISION_BASE + 1,
                        "boot_mode": MODE_PREVIOUS_KNOWN_GOOD,
                        "revoked_revisions": [],
                    },
                ),
            ),
        ],
    }


def expected_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_microcode_contract",
        "contract_id": CONTRACT_ID,
        "status": "candidate_pre_abi_non_promoting",
        "production_ready": False,
        "target": {
            "architecture": "x86_64",
            "vendor_id": TARGET_VENDOR_ID.decode("ascii"),
            "cpuid_signature": f"0x{TARGET_CPUID_SIGNATURE:08X}",
            "decoded_family": "0x1A",
            "decoded_model": "0x44",
            "decoded_stepping": "0x0",
            "hardware_profile": "TIER1-B650M-9800X3D-RTX5070-001",
            "identity_status": "user_mode_cpuid_observed_privileged_revision_open",
        },
        "layout": {
            "byte_order": "little_endian",
            "header_bytes": HEADER_BYTES,
            "patch_record_bytes": PATCH_RECORD_BYTES,
            "maximum_bundle_bytes": MAX_BUNDLE_BYTES,
            "maximum_patch_count": MAX_PATCHES,
            "maximum_patch_bytes": MAX_PATCH_BYTES,
            "payload_alignment": PAYLOAD_ALIGNMENT,
            "header_digest": "SHA-256 with self field zeroed",
            "body_digest": "SHA-256",
            "payload_digest": "SHA-256 per opaque vendor payload",
        },
        "vendor_container_policy": {
            "profile": "amd_opaque_signed_patch",
            "vendor_bytes_interpreted_by_pmcu1_parser": False,
            "vendor_container_validator_required_before_apply": True,
            "vendor_signature_or_processor_authentication_required": True,
            "redistribution_or_user_supplied_intake_must_be_approved": True,
            "checked_in_payloads": "synthetic_test_only_never_apply",
        },
        "selection_policy": {
            "normal": "highest eligible non-revoked revision at or above authenticated floors",
            "previous_known_good": "exact known-good record only",
            "already_equal_or_newer": "verify and skip",
            "downgrade": "never in session",
            "recovery_from_newer_revision": "reset then select authenticated known-good package when platform behavior permits",
            "mixed_revision": "fatal or quarantined before user scheduling",
        },
        "apply_sequence": [
            "verify outer, inner, manifest, vendor, revocation, license, and hardware evidence",
            "stage immutable aligned bytes without granting authority",
            "PooleKernel revalidates identity, digest, revision, capacity, and apply authority",
            "apply on the bootstrap processor before affected features are enabled",
            "apply on every application processor before it enters the online scheduling set",
            "read every processor revision and reject mixed, lower, revoked, or failed state",
            "rerun CPUID and mitigation policy before user scheduling",
            "persist an exact receipt and preserve reset-based known-good recovery",
        ],
        "activation_preconditions": [
            "outer role, version, payload digest, and file digest match",
            "outer, inner, manifest, and vendor trust checks pass",
            "redistribution or user-supplied intake is approved",
            "revocation and rollback state is authenticated and monotonic",
            "exact trusted CPU identity and per-processor revision observations exist",
            "all processors are inventoried, homogeneous, and quiesced",
            "execution is the early PooleKernel stage before affected features and user work",
            "payload, patch, processor, and receipt capacities are sufficient",
            "an explicit kernel apply authority exists",
            "no firmware mutation or physical-media write is requested",
        ],
        "research_basis": [
            "https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9800x3d.html",
            "https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/design-guides/25481.pdf",
            "https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/programmer-references/24593.pdf",
            "https://www.amd.com/en/resources/product-security/bulletin/amd-sb-7033.html",
            "https://www.amd.com/en/resources/product-security/bulletin/amd-sb-7055.html",
            "https://uefi.org/specs/PI/1.8/V2_DXE_Boot_Services_Protocols.html",
        ],
        "claims": {
            "format_frozen": True,
            "python_oracle_implemented": True,
            "no_std_parser_implemented": True,
            "bounded_selection_implemented": True,
            "post_apply_verification_model_implemented": True,
            "vendor_container_parser_implemented": False,
            "vendor_payload_included": False,
            "privileged_revision_observed": False,
            "microcode_applied": False,
            "pooleboot_enforcement": False,
            "poolekernel_enforcement": False,
            "production_ready": False,
        },
        "claim_boundary": [
            "PMCU1 is not owner-ratified and is not a stable ABI.",
            "Parsing, selection, and verification planning grant no CPU or kernel authority.",
            "Opaque vendor bytes are not interpreted or authenticated by the PMCU1 parser.",
            "All checked-in payloads and revisions are synthetic and must never be applied.",
            "No privileged MSR or microcode-revision probe is performed.",
            "No WRMSR, firmware call, driver load, CPU rendezvous, or update is implemented.",
            "Rollback means reset-based known-good selection, never in-session downgrade.",
            "Development artifacts are unsigned and fail the apply-plan gate.",
            "No firmware setting, physical disk, media, or boot state is modified.",
            "Synthetic all-true qualification is test scaffolding, not trust evidence.",
            "N5 exit, physical qualification, ISO, and production readiness remain open.",
        ],
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _binding_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "byte_count": len(data),
        "sha256": _sha256(data),
    }


def implementation_bindings(root: Path = ROOT) -> list[dict[str, Any]]:
    return [_binding_record(root / relative) for relative in IMPLEMENTATION_INPUTS]


def contract_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(value, read_json(root / CONTRACT_SCHEMA_RELATIVE))
    if value != expected_contract():
        errors.append("PMCU1 contract differs from the canonical oracle")
    return errors


def golden_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(value, read_json(root / GOLDEN_SCHEMA_RELATIVE))
    if value != make_golden_vectors():
        errors.append("PMCU1 golden vectors differ from the canonical oracle")
    return errors


def readiness_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(value, read_json(root / READINESS_SCHEMA_RELATIVE))
    if value.get("contract_id") != CONTRACT_ID:
        errors.append("PMCU1 readiness contract mismatch")
    bindings = value.get("bindings", {})
    expected_paths = (
        ("contract", CONTRACT_RELATIVE),
        ("contract_schema", CONTRACT_SCHEMA_RELATIVE),
        ("golden_vectors", GOLDEN_RELATIVE),
        ("golden_schema", GOLDEN_SCHEMA_RELATIVE),
        ("readiness_schema", READINESS_SCHEMA_RELATIVE),
    )
    for key, relative in expected_paths:
        if bindings.get(key) != _binding_record(root / relative):
            errors.append(f"PMCU1 readiness binding mismatch: {key}")
    try:
        expected_inputs = implementation_bindings(root)
    except FileNotFoundError as error:
        errors.append(f"PMCU1 implementation input missing: {error.filename}")
    else:
        if bindings.get("implementation_inputs") != expected_inputs:
            errors.append("PMCU1 implementation bindings mismatch")
    claims = value.get("claims", {})
    for prohibited in (
        "vendor_container_parser_implemented",
        "vendor_payload_included",
        "privileged_revision_observed",
        "microcode_applied",
        "pooleboot_enforced",
        "poolekernel_enforced",
        "n5_exit_gate_satisfied",
        "production_ready",
    ):
        if claims.get(prohibited) is not False:
            errors.append(f"PMCU1 readiness overclaim: {prohibited}")
    if value.get("production_ready") is not False:
        errors.append("PMCU1 readiness must remain non-promoting")
    return errors
