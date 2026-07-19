"""Independent PBTRUST1 boot-policy and monotonic-state oracle."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Final

from runtime.schema_validation import validate_json


CONTRACT_ID: Final = "PBTRUST1"
BACKEND_CONTRACT_ID: Final = "PBSTATE1"
LOGICAL_DIGEST_DOMAIN: Final = b"POOLEOS/PBTS1/LOGICAL/V1\0"
POLICY_MAGIC: Final = b"PBTP1\0\0\0"
STATE_MAGIC: Final = b"PBTS1\0\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
POLICY_BYTES: Final = 320
STATE_BYTES: Final = 256
POLICY_BODY_BYTES: Final = 224
STATE_BODY_BYTES: Final = 224
SIGNATURE_CAPACITY: Final = 64
ARTIFACT_ROLE_MASK: Final = 0x7F
MAX_SIGNERS: Final = 8

POLICY_FLAG_DEVELOPMENT_UNSIGNED: Final = 1 << 0
POLICY_FLAG_SIGNED: Final = 1 << 1
POLICY_KNOWN_FLAGS: Final = (
    POLICY_FLAG_DEVELOPMENT_UNSIGNED | POLICY_FLAG_SIGNED
)

STATE_FLAG_DEVELOPMENT_CANDIDATE: Final = 1 << 0
STATE_FLAG_COMMITTED: Final = 1 << 1
STATE_FLAG_AUTHENTICATED_BACKEND: Final = 1 << 2
STATE_KNOWN_FLAGS: Final = (
    STATE_FLAG_DEVELOPMENT_CANDIDATE
    | STATE_FLAG_COMMITTED
    | STATE_FLAG_AUTHENTICATED_BACKEND
)
COPY_COUNT: Final = 2
COMMIT_COMPLETE: Final = 1
REDUNDANT_COPY_MASK: Final = 0b11
TRANSITION_STEP_COUNT: Final = 9
BACKEND_TRANSITION_STEPS: Final = (
    "write_target_uncommitted",
    "flush_target_data",
    "write_target_commit_and_authentication",
    "flush_target_commit",
    "advance_monotonic_anchor",
    "verify_monotonic_anchor",
    "repair_other_copy",
    "flush_repaired_copy",
    "verify_redundant_copies",
)

POLICY_PATH: Final = "EFI/POOLEOS/TRUST.PBT"
STATE_PATH: Final = "EFI/POOLEOS/TRUSTST.PBS"
CONTRACT_RELATIVE: Final = "specs/native-boot-trust-contract.json"
CONTRACT_SCHEMA_RELATIVE: Final = "specs/native-boot-trust-contract.schema.json"
READINESS_RELATIVE: Final = "runs/native_boot_trust_readiness.json"
READINESS_SCHEMA_RELATIVE: Final = "specs/native-boot-trust-readiness.schema.json"

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/trust/Cargo.toml",
    "native/trust/src/lib.rs",
    "native/trust/src/backend.rs",
    "native/trust/src/bin/pbtrust1_probe.rs",
    "native/boot/Cargo.toml",
    "native/boot/src/kload.rs",
    "native/boot/src/main.rs",
    "native/bootload/src/lib.rs",
    "runtime/native_boot_trust.py",
    "tests/test_native_boot_trust.py",
    "tools/qualify_native_boot_trust.py",
    "docs/native-boot-trust.md",
    CONTRACT_SCHEMA_RELATIVE,
    READINESS_SCHEMA_RELATIVE,
)

POLICY_ERROR_ORDER: Final = (
    "pbtrust_policy_truncated",
    "pbtrust_policy_size",
    "pbtrust_policy_magic",
    "pbtrust_policy_version",
    "pbtrust_policy_flags",
    "pbtrust_policy_numbers",
    "pbtrust_policy_role_mask",
    "pbtrust_policy_signer_shape",
    "pbtrust_policy_digest",
    "pbtrust_policy_body_digest",
    "pbtrust_policy_signature",
)
STATE_ERROR_ORDER: Final = (
    "pbtrust_state_truncated",
    "pbtrust_state_size",
    "pbtrust_state_magic",
    "pbtrust_state_version",
    "pbtrust_state_flags",
    "pbtrust_state_copy",
    "pbtrust_state_commit",
    "pbtrust_state_auth_profile",
    "pbtrust_state_numbers",
    "pbtrust_state_digest",
    "pbtrust_state_previous",
    "pbtrust_state_body_digest",
)
AUTHORIZATION_ERROR_ORDER: Final = (
    "pbtrust_binding_manifest",
    "pbtrust_binding_kernel",
    "pbtrust_binding_retained_set",
    "pbtrust_binding_revocation_set",
    "pbtrust_binding_role_mask",
    "pbtrust_binding_policy_state",
    "pbtrust_binding_state_manifest",
    "pbtrust_binding_state_kernel",
    "pbtrust_binding_state_retained_set",
    "pbtrust_binding_policy_version",
    "pbtrust_rollback_manifest_version",
    "pbtrust_rollback_secure_version",
    "pbtrust_rollback_state_generation",
    "pbtrust_rollback_trust_epoch",
    "pbtrust_policy_unsigned",
    "pbtrust_policy_authentication",
    "pbtrust_policy_threshold",
    "pbtrust_policy_revocation",
    "pbtrust_state_development_candidate",
    "pbtrust_state_authentication",
    "pbtrust_state_monotonicity",
    "pbtrust_state_backend_writable",
    "pbtrust_secure_boot_state",
    "pbtrust_unexpected_authority",
)
BACKEND_ERROR_ORDER: Final = (
    "pbtrust_backend_anchor_authentication",
    "pbtrust_backend_anchor_monotonicity",
    "pbtrust_backend_anchor_numbers",
    "pbtrust_backend_requirements",
    "pbtrust_backend_anchor_rollback",
    "pbtrust_backend_no_authenticated_copy",
    "pbtrust_backend_previous_state",
    "pbtrust_backend_anchor_digest",
    "pbtrust_backend_future_state",
    "pbtrust_backend_state_rollback",
    "pbtrust_backend_writable",
    "pbtrust_backend_repair_capacity",
    "pbtrust_backend_generation_overflow",
    "pbtrust_backend_migration_rollback",
)

TRUE_CLAIMS: Final = (
    "allocation_free_no_std_parser",
    "fixed_policy_record_validated",
    "fixed_state_record_validated",
    "boot_artifact_cross_bindings_modeled",
    "rollback_floor_order_modeled",
    "redundant_copy_shape_validated",
    "previous_state_chain_shape_validated",
    "external_evidence_required",
    "unsigned_development_policy_denied",
    "esp_candidate_rejected_as_persistent_authority",
    "authenticated_anchor_required",
    "redundant_backend_selection_modeled",
    "logical_copy_identity_bound",
    "rollback_and_future_state_rejected",
    "deterministic_repair_plan_modeled",
    "migration_plan_modeled",
    "power_loss_recovery_corpus_passed",
)
FALSE_CLAIMS: Final = (
    "policy_signature_verified",
    "policy_threshold_verified",
    "revocation_state_authenticated",
    "state_authenticated",
    "state_monotonic",
    "state_backend_writable",
    "secure_boot_state_verified",
    "trust_authority_granted",
    "state_written",
    "private_key_used",
    "poolekernel_revalidated",
    "physical_media_written",
    "backend_crypto_verified",
    "monotonic_provider_implemented",
    "persistent_backend_io_implemented",
    "repair_or_migration_executed",
    "production_ready",
)


class BootTrustError(RuntimeError):
    """Raised when a PBTRUST1 input fails closed."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> None:
    raise BootTrustError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _digest(value: str, code: str) -> bytes:
    if len(value) != 64 or value != value.upper():
        _fail(code)
    try:
        decoded = bytes.fromhex(value)
    except ValueError as error:
        raise BootTrustError(code) from error
    if decoded == bytes(32):
        _fail(code)
    return decoded


@dataclasses.dataclass(frozen=True)
class Policy:
    flags: int
    policy_version: int
    trust_epoch: int
    minimum_secure_version: int
    minimum_state_generation: int
    artifact_role_mask: int
    signer_threshold: int
    signer_count: int
    auth_profile: int
    signature_bytes: int
    manifest_sha256: str
    kernel_sha256: str
    retained_set_sha256: str
    revocation_set_sha256: str
    root_set_id: bytes
    signer_set_id: bytes
    body_sha256: str
    raw: bytes


@dataclasses.dataclass(frozen=True)
class State:
    flags: int
    copy_index: int
    auth_profile: int
    state_generation: int
    store_epoch: int
    minimum_secure_version: int
    accepted_manifest_version: int
    accepted_policy_version: int
    policy_sha256: str
    manifest_sha256: str
    kernel_sha256: str
    retained_set_sha256: str
    previous_state_sha256: str
    body_sha256: str
    raw: bytes


@dataclasses.dataclass(frozen=True)
class MonotonicAnchor:
    authenticated: bool
    monotonic: bool
    state_generation: int
    store_epoch: int
    auth_profile: int
    logical_state_sha256: str
    previous_state_sha256: str


@dataclasses.dataclass(frozen=True)
class BackendRequirements:
    minimum_state_generation: int
    minimum_store_epoch: int
    target_store_epoch: int
    target_auth_profile: int


@dataclasses.dataclass(frozen=True)
class BackendAccess:
    writable: bool
    repair_capacity: bool


@dataclasses.dataclass(frozen=True)
class BackendCopy:
    data: bytes | None
    authentication_verified: bool


@dataclasses.dataclass(frozen=True)
class BackendSelection:
    selected_copy: int
    present_copy_mask: int
    parsed_copy_mask: int
    authenticated_copy_mask: int
    anchored_copy_mask: int
    repair_copy_mask: int
    stale_copy_mask: int
    future_copy_mask: int
    state_generation: int
    store_epoch: int
    auth_profile: int
    logical_state_sha256: str
    previous_state_sha256: str
    target_store_epoch: int
    target_auth_profile: int
    migration_required: bool
    authority_grants: int = 0
    state_writes: int = 0


@dataclasses.dataclass(frozen=True)
class BackendTransitionPlan:
    source_copy: int
    target_copy: int
    next_generation: int
    target_store_epoch: int
    target_auth_profile: int
    previous_state_sha256: str
    ordered_step_count: int = TRANSITION_STEP_COUNT
    state_writes_performed: int = 0
    anchor_writes_performed: int = 0
    authority_grants: int = 0


@dataclasses.dataclass(frozen=True)
class ObservedBoot:
    manifest_sha256: str
    kernel_sha256: str
    retained_set_sha256: str
    revocation_set_sha256: str
    manifest_version: int
    minimum_secure_version: int
    artifact_role_mask: int = ARTIFACT_ROLE_MASK


@dataclasses.dataclass(frozen=True)
class VerificationEvidence:
    policy_signature_verified: bool
    policy_threshold_verified: bool
    revocation_state_authenticated: bool
    policy_not_revoked: bool
    state_authenticated: bool
    state_monotonic: bool
    state_backend_writable: bool
    secure_boot_state_verified: bool

    @classmethod
    def development(cls) -> "VerificationEvidence":
        return cls(*(False for _ in range(8)))

    @classmethod
    def synthetic_qualified(cls) -> "VerificationEvidence":
        return cls(*(True for _ in range(8)))


def encode_policy(
    *,
    manifest_sha256: str,
    kernel_sha256: str,
    retained_set_sha256: str,
    revocation_set_sha256: str,
    policy_version: int = 1,
    trust_epoch: int = 1,
    minimum_secure_version: int = 1,
    minimum_state_generation: int = 1,
    signed: bool = False,
    signer_threshold: int = 1,
    signer_count: int = 1,
    auth_profile: int = 1,
    root_set_id: bytes = bytes([0x55]) * 16,
    signer_set_id: bytes = bytes([0x66]) * 16,
    signature: bytes = bytes([0x77]) * SIGNATURE_CAPACITY,
) -> bytes:
    output = bytearray(POLICY_BYTES)
    output[:8] = POLICY_MAGIC
    struct.pack_into("<HHHH", output, 8, MAJOR_VERSION, MINOR_VERSION, POLICY_BYTES, POLICY_FLAG_SIGNED if signed else POLICY_FLAG_DEVELOPMENT_UNSIGNED)
    struct.pack_into(
        "<QQQQI",
        output,
        16,
        policy_version,
        trust_epoch,
        minimum_secure_version,
        minimum_state_generation,
        ARTIFACT_ROLE_MASK,
    )
    if signed:
        if len(root_set_id) != 16 or len(signer_set_id) != 16 or not 1 <= len(signature) <= SIGNATURE_CAPACITY:
            _fail("pbtrust_policy_signer_shape")
        struct.pack_into("<HHHH", output, 52, signer_threshold, signer_count, auth_profile, len(signature))
        output[192:208] = root_set_id
        output[208:224] = signer_set_id
        output[256 : 256 + len(signature)] = signature
    output[64:96] = _digest(manifest_sha256, "pbtrust_policy_digest")
    output[96:128] = _digest(kernel_sha256, "pbtrust_policy_digest")
    output[128:160] = _digest(retained_set_sha256, "pbtrust_policy_digest")
    output[160:192] = _digest(revocation_set_sha256, "pbtrust_policy_digest")
    output[224:256] = hashlib.sha256(output[:POLICY_BODY_BYTES]).digest()
    return bytes(output)


def parse_policy(data: bytes) -> Policy:
    if len(data) < POLICY_BYTES:
        _fail("pbtrust_policy_truncated")
    if len(data) != POLICY_BYTES:
        _fail("pbtrust_policy_size")
    if struct.unpack_from("<H", data, 12)[0] != POLICY_BYTES:
        _fail("pbtrust_policy_size")
    if data[:8] != POLICY_MAGIC:
        _fail("pbtrust_policy_magic")
    major, minor, _record_bytes, flags = struct.unpack_from("<HHHH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        _fail("pbtrust_policy_version")
    if flags & ~POLICY_KNOWN_FLAGS or flags.bit_count() != 1:
        _fail("pbtrust_policy_flags")
    policy_version, trust_epoch, minimum_secure_version, minimum_state_generation, role_mask = struct.unpack_from("<QQQQI", data, 16)
    if not all((policy_version, trust_epoch, minimum_secure_version, minimum_state_generation)):
        _fail("pbtrust_policy_numbers")
    if role_mask != ARTIFACT_ROLE_MASK:
        _fail("pbtrust_policy_role_mask")
    signer_threshold, signer_count, auth_profile, signature_bytes = struct.unpack_from("<HHHH", data, 52)
    if struct.unpack_from("<I", data, 60)[0] != 0:
        _fail("pbtrust_policy_signer_shape")
    digests = tuple(data[offset : offset + 32] for offset in (64, 96, 128, 160))
    if any(value == bytes(32) for value in digests):
        _fail("pbtrust_policy_digest")
    root_set_id = data[192:208]
    signer_set_id = data[208:224]
    body_sha256 = data[224:256]
    if hashlib.sha256(data[:POLICY_BODY_BYTES]).digest() != body_sha256:
        _fail("pbtrust_policy_body_digest")
    signature = data[256:]
    if flags == POLICY_FLAG_DEVELOPMENT_UNSIGNED:
        if any((signer_threshold, signer_count, auth_profile, signature_bytes)) or root_set_id != bytes(16) or signer_set_id != bytes(16) or signature != bytes(SIGNATURE_CAPACITY):
            _fail("pbtrust_policy_signer_shape")
    else:
        if not (1 <= signer_threshold <= signer_count <= MAX_SIGNERS) or auth_profile == 0 or not 1 <= signature_bytes <= SIGNATURE_CAPACITY or root_set_id == bytes(16) or signer_set_id == bytes(16):
            _fail("pbtrust_policy_signer_shape")
        if signature[:signature_bytes] == bytes(signature_bytes) or signature[signature_bytes:] != bytes(SIGNATURE_CAPACITY - signature_bytes):
            _fail("pbtrust_policy_signature")
    return Policy(
        flags,
        policy_version,
        trust_epoch,
        minimum_secure_version,
        minimum_state_generation,
        role_mask,
        signer_threshold,
        signer_count,
        auth_profile,
        signature_bytes,
        *(value.hex().upper() for value in digests),
        root_set_id,
        signer_set_id,
        body_sha256.hex().upper(),
        data,
    )


def encode_state(
    *,
    policy_sha256: str,
    manifest_sha256: str,
    kernel_sha256: str,
    retained_set_sha256: str,
    state_generation: int = 1,
    store_epoch: int = 1,
    minimum_secure_version: int = 1,
    accepted_manifest_version: int = 1,
    accepted_policy_version: int = 1,
    authenticated_backend: bool = False,
    copy_index: int = 0,
    auth_profile: int = 1,
    previous_state_sha256: str | None = None,
) -> bytes:
    output = bytearray(STATE_BYTES)
    output[:8] = STATE_MAGIC
    flags = STATE_FLAG_COMMITTED | (
        STATE_FLAG_AUTHENTICATED_BACKEND
        if authenticated_backend
        else STATE_FLAG_DEVELOPMENT_CANDIDATE
    )
    struct.pack_into("<HHHH", output, 8, MAJOR_VERSION, MINOR_VERSION, STATE_BYTES, flags)
    output[16] = copy_index
    output[17] = COPY_COUNT
    struct.pack_into("<HHH", output, 18, COMMIT_COMPLETE, auth_profile if authenticated_backend else 0, 0)
    struct.pack_into(
        "<QQQQQ",
        output,
        24,
        state_generation,
        store_epoch,
        minimum_secure_version,
        accepted_manifest_version,
        accepted_policy_version,
    )
    output[64:96] = _digest(policy_sha256, "pbtrust_state_digest")
    output[96:128] = _digest(manifest_sha256, "pbtrust_state_digest")
    output[128:160] = _digest(kernel_sha256, "pbtrust_state_digest")
    output[160:192] = _digest(retained_set_sha256, "pbtrust_state_digest")
    if previous_state_sha256 is not None:
        output[192:224] = _digest(previous_state_sha256, "pbtrust_state_previous")
    output[224:256] = hashlib.sha256(output[:STATE_BODY_BYTES]).digest()
    return bytes(output)


def parse_state(data: bytes) -> State:
    if len(data) < STATE_BYTES:
        _fail("pbtrust_state_truncated")
    if len(data) != STATE_BYTES:
        _fail("pbtrust_state_size")
    if struct.unpack_from("<H", data, 12)[0] != STATE_BYTES:
        _fail("pbtrust_state_size")
    if data[:8] != STATE_MAGIC:
        _fail("pbtrust_state_magic")
    major, minor, _record_bytes, flags = struct.unpack_from("<HHHH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        _fail("pbtrust_state_version")
    profile_flags = flags & (STATE_FLAG_DEVELOPMENT_CANDIDATE | STATE_FLAG_AUTHENTICATED_BACKEND)
    if flags & ~STATE_KNOWN_FLAGS or not flags & STATE_FLAG_COMMITTED or profile_flags.bit_count() != 1:
        _fail("pbtrust_state_flags")
    copy_index, copy_count = data[16:18]
    if copy_index >= COPY_COUNT or copy_count != COPY_COUNT:
        _fail("pbtrust_state_copy")
    commit, auth_profile, reserved = struct.unpack_from("<HHH", data, 18)
    if commit != COMMIT_COMPLETE:
        _fail("pbtrust_state_commit")
    if reserved or (profile_flags == STATE_FLAG_DEVELOPMENT_CANDIDATE and auth_profile) or (profile_flags == STATE_FLAG_AUTHENTICATED_BACKEND and not auth_profile):
        _fail("pbtrust_state_auth_profile")
    numbers = struct.unpack_from("<QQQQQ", data, 24)
    generation, store_epoch, minimum_secure_version, manifest_version, policy_version = numbers
    if not all(numbers) or manifest_version < minimum_secure_version:
        _fail("pbtrust_state_numbers")
    digests = tuple(data[offset : offset + 32] for offset in (64, 96, 128, 160))
    if any(value == bytes(32) for value in digests):
        _fail("pbtrust_state_digest")
    previous = data[192:224]
    if (generation == 1) != (previous == bytes(32)):
        _fail("pbtrust_state_previous")
    body = data[224:256]
    if hashlib.sha256(data[:STATE_BODY_BYTES]).digest() != body:
        _fail("pbtrust_state_body_digest")
    return State(
        flags,
        copy_index,
        auth_profile,
        generation,
        store_epoch,
        minimum_secure_version,
        manifest_version,
        policy_version,
        *(value.hex().upper() for value in digests),
        previous.hex().upper(),
        body.hex().upper(),
        data,
    )


def logical_state_sha256(state: State) -> str:
    hasher = hashlib.sha256()
    hasher.update(LOGICAL_DIGEST_DOMAIN)
    hasher.update(struct.pack("<HH", MAJOR_VERSION, MINOR_VERSION))
    hasher.update(
        struct.pack(
            "<HHQQQQQ",
            STATE_FLAG_COMMITTED | STATE_FLAG_AUTHENTICATED_BACKEND,
            state.auth_profile,
            state.state_generation,
            state.store_epoch,
            state.minimum_secure_version,
            state.accepted_manifest_version,
            state.accepted_policy_version,
        )
    )
    for digest in (
        state.policy_sha256,
        state.manifest_sha256,
        state.kernel_sha256,
        state.retained_set_sha256,
        state.previous_state_sha256,
    ):
        hasher.update(bytes.fromhex(digest))
    return hasher.hexdigest().upper()


def _anchor_digest(value: str, *, allow_zero: bool) -> bytes | None:
    if len(value) != 64 or value != value.upper():
        return None
    try:
        decoded = bytes.fromhex(value)
    except ValueError:
        return None
    if not allow_zero and decoded == bytes(32):
        return None
    return decoded


def _validate_anchor(
    anchor: MonotonicAnchor, requirements: BackendRequirements
) -> None:
    if not anchor.authenticated:
        _fail("pbtrust_backend_anchor_authentication")
    if not anchor.monotonic:
        _fail("pbtrust_backend_anchor_monotonicity")
    current = _anchor_digest(anchor.logical_state_sha256, allow_zero=False)
    previous = _anchor_digest(anchor.previous_state_sha256, allow_zero=True)
    if (
        anchor.state_generation <= 0
        or anchor.store_epoch <= 0
        or anchor.auth_profile <= 0
        or current is None
        or previous is None
        or ((anchor.state_generation == 1) != (previous == bytes(32)))
    ):
        _fail("pbtrust_backend_anchor_numbers")
    if (
        requirements.minimum_state_generation <= 0
        or requirements.minimum_store_epoch <= 0
        or requirements.target_store_epoch <= 0
        or requirements.target_auth_profile <= 0
        or requirements.target_store_epoch < requirements.minimum_store_epoch
        or requirements.target_store_epoch < anchor.store_epoch
    ):
        _fail("pbtrust_backend_requirements")
    if (
        anchor.state_generation < requirements.minimum_state_generation
        or anchor.store_epoch < requirements.minimum_store_epoch
    ):
        _fail("pbtrust_backend_anchor_rollback")


def select_backend_state(
    copies: tuple[BackendCopy, BackendCopy],
    anchor: MonotonicAnchor,
    requirements: BackendRequirements,
    access: BackendAccess,
) -> BackendSelection:
    _validate_anchor(anchor, requirements)
    candidates: list[tuple[State, str] | None] = [None, None]
    present_mask = 0
    parsed_mask = 0
    authenticated_mask = 0
    anchored_mask = 0
    stale_mask = 0
    future_mask = 0
    previous_mismatch_mask = 0
    digest_mismatch_mask = 0

    for index, copy in enumerate(copies):
        bit = 1 << index
        if copy.data is None:
            continue
        present_mask |= bit
        try:
            state = parse_state(copy.data)
        except BootTrustError:
            continue
        if state.copy_index != index:
            continue
        parsed_mask |= bit
        if (
            not copy.authentication_verified
            or not state.flags & STATE_FLAG_AUTHENTICATED_BACKEND
        ):
            continue
        authenticated_mask |= bit
        logical = logical_state_sha256(state)
        candidates[index] = (state, logical)
        if (
            state.state_generation < anchor.state_generation
            or state.store_epoch < anchor.store_epoch
        ):
            stale_mask |= bit
            continue
        if (
            state.state_generation > anchor.state_generation
            or state.store_epoch > anchor.store_epoch
        ):
            future_mask |= bit
            continue
        if state.previous_state_sha256 != anchor.previous_state_sha256:
            previous_mismatch_mask |= bit
            continue
        if (
            state.auth_profile != anchor.auth_profile
            or logical != anchor.logical_state_sha256
        ):
            digest_mismatch_mask |= bit
            continue
        anchored_mask |= bit

    if not anchored_mask:
        if previous_mismatch_mask:
            _fail("pbtrust_backend_previous_state")
        if digest_mismatch_mask:
            _fail("pbtrust_backend_anchor_digest")
        if future_mask:
            _fail("pbtrust_backend_future_state")
        if stale_mask:
            _fail("pbtrust_backend_state_rollback")
        _fail("pbtrust_backend_no_authenticated_copy")
    if not access.writable:
        _fail("pbtrust_backend_writable")
    repair_mask = REDUNDANT_COPY_MASK & ~anchored_mask
    if repair_mask and not access.repair_capacity:
        _fail("pbtrust_backend_repair_capacity")

    selected_copy = 0 if anchored_mask & 1 else 1
    selected = candidates[selected_copy]
    if selected is None:
        _fail("pbtrust_backend_anchor_digest")
    state, logical = selected
    return BackendSelection(
        selected_copy=selected_copy,
        present_copy_mask=present_mask,
        parsed_copy_mask=parsed_mask,
        authenticated_copy_mask=authenticated_mask,
        anchored_copy_mask=anchored_mask,
        repair_copy_mask=repair_mask,
        stale_copy_mask=stale_mask,
        future_copy_mask=future_mask,
        state_generation=state.state_generation,
        store_epoch=state.store_epoch,
        auth_profile=state.auth_profile,
        logical_state_sha256=logical,
        previous_state_sha256=state.previous_state_sha256,
        target_store_epoch=requirements.target_store_epoch,
        target_auth_profile=requirements.target_auth_profile,
        migration_required=(
            state.store_epoch < requirements.target_store_epoch
            or state.auth_profile != requirements.target_auth_profile
        ),
    )


def plan_backend_transition(selection: BackendSelection) -> BackendTransitionPlan:
    anchored_mask = selection.anchored_copy_mask
    expected_repair_mask = REDUNDANT_COPY_MASK & ~anchored_mask
    expected_migration = (
        selection.store_epoch < selection.target_store_epoch
        or selection.auth_profile != selection.target_auth_profile
    )
    if (
        selection.selected_copy not in (0, 1)
        or anchored_mask <= 0
        or anchored_mask & ~REDUNDANT_COPY_MASK
        or not anchored_mask & (1 << selection.selected_copy)
        or selection.repair_copy_mask != expected_repair_mask
        or selection.state_generation <= 0
        or selection.store_epoch <= 0
        or selection.auth_profile <= 0
        or _anchor_digest(selection.logical_state_sha256, allow_zero=False) is None
        or _anchor_digest(selection.previous_state_sha256, allow_zero=True) is None
        or (
            (selection.state_generation == 1)
            != (selection.previous_state_sha256 == "00" * 32)
        )
        or selection.migration_required != expected_migration
        or selection.authority_grants != 0
        or selection.state_writes != 0
    ):
        _fail("pbtrust_backend_requirements")
    if (
        selection.target_store_epoch < selection.store_epoch
        or selection.target_auth_profile <= 0
    ):
        _fail("pbtrust_backend_migration_rollback")
    if selection.state_generation >= (1 << 64) - 1:
        _fail("pbtrust_backend_generation_overflow")
    if selection.anchored_copy_mask == 0b01:
        target_copy = 1
    elif selection.anchored_copy_mask == 0b10:
        target_copy = 0
    else:
        target_copy = 1 - selection.selected_copy
    return BackendTransitionPlan(
        source_copy=selection.selected_copy,
        target_copy=target_copy,
        next_generation=selection.state_generation + 1,
        target_store_epoch=selection.target_store_epoch,
        target_auth_profile=selection.target_auth_profile,
        previous_state_sha256=selection.logical_state_sha256,
    )


def authorize(
    policy: Policy,
    state: State,
    observed: ObservedBoot,
    evidence: VerificationEvidence,
) -> dict[str, Any]:
    checks = (
        (policy.manifest_sha256 == observed.manifest_sha256, "pbtrust_binding_manifest"),
        (policy.kernel_sha256 == observed.kernel_sha256, "pbtrust_binding_kernel"),
        (policy.retained_set_sha256 == observed.retained_set_sha256, "pbtrust_binding_retained_set"),
        (policy.revocation_set_sha256 == observed.revocation_set_sha256, "pbtrust_binding_revocation_set"),
        (policy.artifact_role_mask == observed.artifact_role_mask, "pbtrust_binding_role_mask"),
        (state.policy_sha256 == sha256_bytes(policy.raw), "pbtrust_binding_policy_state"),
        (state.manifest_sha256 == observed.manifest_sha256, "pbtrust_binding_state_manifest"),
        (state.kernel_sha256 == observed.kernel_sha256, "pbtrust_binding_state_kernel"),
        (state.retained_set_sha256 == observed.retained_set_sha256, "pbtrust_binding_state_retained_set"),
        (state.accepted_policy_version == policy.policy_version, "pbtrust_binding_policy_version"),
        (state.accepted_manifest_version == observed.manifest_version, "pbtrust_rollback_manifest_version"),
        (
            observed.minimum_secure_version >= policy.minimum_secure_version
            and observed.minimum_secure_version >= state.minimum_secure_version
            and observed.manifest_version >= observed.minimum_secure_version,
            "pbtrust_rollback_secure_version",
        ),
        (state.state_generation >= policy.minimum_state_generation, "pbtrust_rollback_state_generation"),
        (state.store_epoch >= policy.trust_epoch, "pbtrust_rollback_trust_epoch"),
    )
    for accepted, code in checks:
        if not accepted:
            _fail(code)
    if policy.flags == POLICY_FLAG_DEVELOPMENT_UNSIGNED:
        _fail("pbtrust_policy_unsigned")
    evidence_checks = (
        (evidence.policy_signature_verified, "pbtrust_policy_authentication"),
        (evidence.policy_threshold_verified, "pbtrust_policy_threshold"),
        (evidence.revocation_state_authenticated and evidence.policy_not_revoked, "pbtrust_policy_revocation"),
        (not state.flags & STATE_FLAG_DEVELOPMENT_CANDIDATE, "pbtrust_state_development_candidate"),
        (evidence.state_authenticated, "pbtrust_state_authentication"),
        (evidence.state_monotonic, "pbtrust_state_monotonicity"),
        (evidence.state_backend_writable, "pbtrust_state_backend_writable"),
        (evidence.secure_boot_state_verified, "pbtrust_secure_boot_state"),
    )
    for accepted, code in evidence_checks:
        if not accepted:
            _fail(code)
    return {
        "policy_sha256": sha256_bytes(policy.raw),
        "state_sha256": sha256_bytes(state.raw),
        "policy_version": policy.policy_version,
        "state_generation": state.state_generation,
        "trust_epoch": policy.trust_epoch,
    }


def validate_development(
    policy_data: bytes, state_data: bytes, observed: ObservedBoot
) -> dict[str, Any]:
    policy = parse_policy(policy_data)
    state = parse_state(state_data)
    try:
        authorize(policy, state, observed, VerificationEvidence.development())
    except BootTrustError as error:
        if error.code != "pbtrust_policy_unsigned":
            raise
    else:
        _fail("pbtrust_unexpected_authority")
    return {
        "contract_id": CONTRACT_ID,
        "policy_bytes": POLICY_BYTES,
        "state_bytes": STATE_BYTES,
        "binding_count": 14,
        "denial_count": 1,
        "denial": "pbtrust_policy_unsigned",
        "policy_sha256": sha256_bytes(policy_data),
        "state_sha256": sha256_bytes(state_data),
        "development_unsigned": True,
        "state_source": "esp_candidate_not_persistent_authority",
        "state_authenticated": False,
        "state_monotonic": False,
        "state_backend_writable": False,
        "authority_grants": 0,
        "state_writes": 0,
        "signature_verifications": 0,
        "monotonic_backend_observations": 0,
    }


def canonical_development_records(
    *,
    manifest_data: bytes,
    kernel_data: bytes,
    retained_set_sha256: str,
    manifest_version: int,
    minimum_secure_version: int,
) -> tuple[bytes, bytes, ObservedBoot]:
    observed = ObservedBoot(
        manifest_sha256=sha256_bytes(manifest_data),
        kernel_sha256=sha256_bytes(kernel_data),
        retained_set_sha256=retained_set_sha256,
        revocation_set_sha256=sha256_bytes(b""),
        manifest_version=manifest_version,
        minimum_secure_version=minimum_secure_version,
    )
    policy = encode_policy(
        manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256,
        retained_set_sha256=observed.retained_set_sha256,
        revocation_set_sha256=observed.revocation_set_sha256,
        minimum_secure_version=minimum_secure_version,
    )
    state = encode_state(
        policy_sha256=sha256_bytes(policy),
        manifest_sha256=observed.manifest_sha256,
        kernel_sha256=observed.kernel_sha256,
        retained_set_sha256=observed.retained_set_sha256,
        minimum_secure_version=minimum_secure_version,
        accepted_manifest_version=manifest_version,
    )
    validate_development(policy, state, observed)
    return policy, state, observed


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        _fail("pbtrust_json_root")
    return value


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def file_binding(root: Path, relative_path: str) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise BootTrustError("pbtrust_binding_escape") from error
    data = path.read_bytes()
    return {
        "path": relative_path.replace("\\", "/"),
        "byte_count": len(data),
        "sha256": sha256_bytes(data),
    }


def binding_matches(binding: Any, root: Path, expected_path: str) -> bool:
    if not isinstance(binding, dict) or binding.get("path") != expected_path:
        return False
    try:
        return binding == file_binding(root, expected_path)
    except (OSError, BootTrustError):
        return False


def expected_claims() -> dict[str, bool]:
    return {
        **{name: True for name in TRUE_CLAIMS},
        **{name: False for name in FALSE_CLAIMS},
    }


def expected_backend_contract() -> dict[str, Any]:
    return {
        "contract_id": BACKEND_CONTRACT_ID,
        "logical_digest_domain": LOGICAL_DIGEST_DOMAIN.rstrip(b"\0").decode("ascii"),
        "anchor_fields": [
            "authenticated",
            "monotonic",
            "state_generation",
            "store_epoch",
            "auth_profile",
            "logical_state_sha256",
            "previous_state_sha256",
        ],
        "selection_rule": (
            "select the lowest-index externally authenticated committed copy "
            "whose generation, epoch, profile, previous-state link, and logical "
            "digest exactly match the authenticated monotonic anchor"
        ),
        "transition_steps": list(BACKEND_TRANSITION_STEPS),
        "power_loss_case_count": 9,
        "model_only": True,
    }


def _schema_errors(
    value: dict[str, Any], root: Path, schema_relative: str
) -> list[str]:
    schema = read_json(root / schema_relative)
    return [
        f"schema {item.path}: {item.message}"
        for item in validate_json(value, schema)
    ]


def contract_errors(contract: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(contract, root, CONTRACT_SCHEMA_RELATIVE)
    if contract.get("phase_mapping") != ["N5.1", "N5.4", "N5.5", "N5.8", "N5.9"]:
        errors.append("PBTRUST1 phase mapping changed")
    if contract.get("policy_error_order") != list(POLICY_ERROR_ORDER):
        errors.append("PBTRUST1 policy error order changed")
    if contract.get("state_error_order") != list(STATE_ERROR_ORDER):
        errors.append("PBTRUST1 state error order changed")
    if contract.get("authorization_error_order") != list(AUTHORIZATION_ERROR_ORDER):
        errors.append("PBTRUST1 authorization error order changed")
    if contract.get("backend_error_order") != list(BACKEND_ERROR_ORDER):
        errors.append("PBSTATE1 backend error order changed")
    if contract.get("backend_contract") != expected_backend_contract():
        errors.append("PBSTATE1 backend contract changed")
    formats = contract.get("formats", {})
    if (
        formats.get("policy_bytes") != POLICY_BYTES
        or formats.get("state_bytes") != STATE_BYTES
        or formats.get("policy_body_bytes") != POLICY_BODY_BYTES
        or formats.get("state_body_bytes") != STATE_BODY_BYTES
        or formats.get("signature_capacity") != SIGNATURE_CAPACITY
        or formats.get("artifact_role_mask") != ARTIFACT_ROLE_MASK
        or formats.get("copy_count") != COPY_COUNT
    ):
        errors.append("PBTRUST1 fixed format changed")
    if contract.get("claims") != expected_claims():
        errors.append("PBTRUST1 claim boundary changed")
    bindings = contract.get("implementation_bindings", [])
    if not isinstance(bindings, list) or [
        item.get("path") for item in bindings if isinstance(item, dict)
    ] != list(IMPLEMENTATION_INPUTS):
        errors.append("PBTRUST1 implementation binding order changed")
    else:
        for item, relative_path in zip(bindings, IMPLEMENTATION_INPUTS, strict=True):
            if not binding_matches(item, root, relative_path):
                errors.append(f"stale PBTRUST1 implementation binding: {relative_path}")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
    except (OSError, json.JSONDecodeError, BootTrustError) as error:
        return errors + [f"PBTRUST1 contract cannot be read: {error}"]
    errors.extend(contract_errors(contract, root))
    inputs = readiness.get("inputs", {})
    expected_inputs = {
        "contract": CONTRACT_RELATIVE,
        "toolchain_lock": "specs/native-toolchain-lock.json",
        "toolchain_qualification": "runs/native_toolchain_qualification.json",
        "tier1_profile": "runs/hardware_target_readiness.json",
    }
    for name, relative_path in expected_inputs.items():
        if not binding_matches(inputs.get(name), root, relative_path):
            errors.append(f"stale PBTRUST1 input binding: {name}")
    implementation = inputs.get("implementation_inputs", [])
    if not isinstance(implementation, list) or [
        item.get("path") for item in implementation if isinstance(item, dict)
    ] != list(IMPLEMENTATION_INPUTS):
        errors.append("PBTRUST1 readiness implementation-input order changed")
    else:
        for item, relative_path in zip(
            implementation, IMPLEMENTATION_INPUTS, strict=True
        ):
            if not binding_matches(item, root, relative_path):
                errors.append(
                    f"stale PBTRUST1 readiness implementation input: {relative_path}"
                )
    build = readiness.get("build", {})
    if (
        build.get("rust_host_tests_passed") != 12
        or build.get("rust_host_tests_total") != 12
        or build.get("rustfmt_packages") != 1
        or build.get("clippy_targets") != 1
        or build.get("no_std_targets")
        != ["x86_64-unknown-none", "x86_64-unknown-uefi"]
        or build.get("pooleboot_uefi_integration_builds_passed") != 1
        or build.get("pooleboot_uefi_integration_builds_total") != 1
    ):
        errors.append("PBTRUST1 build evidence changed")
    qualification = contract.get("qualification", {})
    differential = readiness.get("differential", {})
    for name in (
        "policy_parser",
        "state_parser",
        "authorization",
        "backend_selection",
    ):
        item = differential.get(name, {})
        expected_cases = qualification.get(f"{name}_cases")
        if (
            item.get("cases") != expected_cases
            or item.get("mismatches") != 0
            or not isinstance(item.get("seed"), int)
        ):
            errors.append(f"PBTRUST1 {name} differential evidence changed")
    controls = readiness.get("negative_controls", [])
    required_control_count = qualification.get("negative_control_count")
    if (
        not isinstance(controls, list)
        or len(controls) != required_control_count
        or any(item.get("status") != "pass" for item in controls if isinstance(item, dict))
        or len([item for item in controls if isinstance(item, dict)]) != len(controls)
        or len({item.get("id") for item in controls}) != len(controls)
    ):
        errors.append("PBTRUST1 hostile-control evidence changed")
    development = readiness.get("development_integration", {})
    if (
        development.get("binding_count") != 14
        or development.get("denial") != "pbtrust_policy_unsigned"
        or development.get("state_source")
        != "esp_candidate_not_persistent_authority"
        or development.get("authority_grants") != 0
        or development.get("state_writes") != 0
    ):
        errors.append("PBTRUST1 development-denial boundary changed")
    backend = readiness.get("backend_model", {})
    if (
        backend.get("contract_id") != BACKEND_CONTRACT_ID
        or backend.get("logical_digest_domain")
        != LOGICAL_DIGEST_DOMAIN.rstrip(b"\0").decode("ascii")
        or backend.get("selected_copy") != 0
        or backend.get("anchored_copy_mask") != REDUNDANT_COPY_MASK
        or backend.get("repair_copy_mask") != 0
        or backend.get("migration_required") is not True
        or backend.get("next_generation") != 2
        or backend.get("target_copy") != 1
        or backend.get("ordered_transition_steps")
        != list(BACKEND_TRANSITION_STEPS)
        or backend.get("authority_grants") != 0
        or backend.get("state_writes_performed") != 0
        or backend.get("anchor_writes_performed") != 0
    ):
        errors.append("PBSTATE1 backend-model boundary changed")
    power_loss = backend.get("power_loss", {})
    expected_power_cases = (
        ("before_target_write", 1, 0, 0),
        ("after_target_body_write", 1, 0, 0b10),
        ("after_target_data_flush", 1, 0, 0b10),
        ("after_target_commit_auth", 1, 0, 0b10),
        ("after_target_commit_flush", 1, 0, 0b10),
        ("after_anchor_advance", 2, 1, 0b01),
        ("after_anchor_verify", 2, 1, 0b01),
        ("after_repair_write", 2, 1, 0b01),
        ("after_final_verify", 2, 0, 0),
    )
    observed_power_cases = power_loss.get("cases", [])
    normalized_power_cases = [
        (
            item.get("id"),
            item.get("selected_generation"),
            item.get("selected_copy"),
            item.get("repair_copy_mask"),
        )
        for item in observed_power_cases
        if isinstance(item, dict)
    ]
    if (
        power_loss.get("case_count") != len(expected_power_cases)
        or power_loss.get("all_cases_passed") is not True
        or power_loss.get("storage_io_performed") is not False
        or power_loss.get("anchor_writes_performed") != 0
        or power_loss.get("state_writes_performed") != 0
        or normalized_power_cases != list(expected_power_cases)
        or len(normalized_power_cases) != len(observed_power_cases)
        or any(
            item.get("authority_grants") != 0
            or item.get("state_writes") != 0
            or item.get("status") != "pass"
            for item in observed_power_cases
            if isinstance(item, dict)
        )
    ):
        errors.append("PBSTATE1 power-loss recovery evidence changed")
    if readiness.get("claims") != expected_claims():
        errors.append("PBTRUST1 readiness claim boundary changed")
    if readiness.get("non_claims") != contract.get("non_claims"):
        errors.append("PBTRUST1 readiness non-claim boundary changed")
    if readiness.get("production_ready") is not False:
        errors.append("PBTRUST1 overclaims production readiness")
    return errors
