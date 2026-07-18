"""Independent PREC1 recovery-policy, state, and transition reference model."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Final

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("specs/native-recovery-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-recovery-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-recovery-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-recovery-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_recovery_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-recovery-readiness.schema.json")

CONTRACT_ID: Final = "PREC1"
MAGIC: Final = b"PREC1\0\0\0"
STATE_MAGIC: Final = b"PRECST1\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 256
TOTAL_BYTES: Final = 992
STATE_BYTES: Final = 128
STATE_CHECKSUM_BYTES: Final = 16
RECORD_ALIGNMENT: Final = 8
SLOT_COUNT: Final = 2
SLOT_BYTES: Final = 96
FAILURE_COUNT: Final = 10
FAILURE_BYTES: Final = 32
AUTHORITY_COUNT: Final = 7
AUTHORITY_BYTES: Final = 32
SLOT_OFFSET: Final = HEADER_BYTES
FAILURE_OFFSET: Final = SLOT_OFFSET + SLOT_COUNT * SLOT_BYTES
AUTHORITY_OFFSET: Final = FAILURE_OFFSET + FAILURE_COUNT * FAILURE_BYTES
MAX_ATTEMPTS_LIMIT: Final = 7
MAX_SUCCESS_DEADLINE_SECONDS: Final = 3600

FLAG_FAIL_CLOSED: Final = 1 << 0
FLAG_AB_SLOTS: Final = 1 << 1
FLAG_DECREMENT_BEFORE_HANDOFF: Final = 1 << 2
FLAG_KNOWN_GOOD_FALLBACK: Final = 1 << 3
FLAG_AUTHENTICATED_STATE: Final = 1 << 4
FLAG_OUTER_SIGNATURE: Final = 1 << 5
FLAG_INNER_SIGNATURE: Final = 1 << 6
FLAG_VERSION_FLOOR: Final = 1 << 7
FLAG_OFFLINE_RECOVERY: Final = 1 << 8
FLAG_PDC_DISABLED: Final = 1 << 9
FLAG_POOLEGLYPH_INDEPENDENT: Final = 1 << 10
FLAG_BOUNDED_DISPLAY_PATH: Final = 1 << 11
FLAG_PRESERVE_EVIDENCE: Final = 1 << 12
FLAG_PHYSICAL_PRESENCE_DESTRUCTIVE: Final = 1 << 13
REQUIRED_FLAGS: Final = (
    FLAG_FAIL_CLOSED
    | FLAG_AB_SLOTS
    | FLAG_DECREMENT_BEFORE_HANDOFF
    | FLAG_KNOWN_GOOD_FALLBACK
    | FLAG_AUTHENTICATED_STATE
    | FLAG_OUTER_SIGNATURE
    | FLAG_INNER_SIGNATURE
    | FLAG_VERSION_FLOOR
    | FLAG_OFFLINE_RECOVERY
    | FLAG_PDC_DISABLED
    | FLAG_POOLEGLYPH_INDEPENDENT
    | FLAG_BOUNDED_DISPLAY_PATH
    | FLAG_PRESERVE_EVIDENCE
    | FLAG_PHYSICAL_PRESENCE_DESTRUCTIVE
)

MODE_NORMAL: Final = 1
MODE_SAFE: Final = 2
MODE_PREVIOUS: Final = 3
MODE_RECOVERY: Final = 4
MODE_DIAGNOSTIC: Final = 5
MODE_FIRMWARE: Final = 6
MODE_NAMES: Final = {
    MODE_NORMAL: "normal",
    MODE_SAFE: "safe",
    MODE_PREVIOUS: "previous",
    MODE_RECOVERY: "recovery",
    MODE_DIAGNOSTIC: "diagnostic",
    MODE_FIRMWARE: "firmware",
}
MODE_MASK_ALL: Final = sum(1 << (mode - 1) for mode in MODE_NAMES)

FAIL_CONFIG_INVALID: Final = 1
FAIL_STATE_INVALID: Final = 2
FAIL_SIGNATURE_INVALID: Final = 3
FAIL_VERSION_ROLLBACK: Final = 4
FAIL_ARTIFACT_INTEGRITY: Final = 5
FAIL_KERNEL_ENTRY: Final = 6
FAIL_INITIAL_HEALTH_TIMEOUT: Final = 7
FAIL_ATTEMPT_EXHAUSTED: Final = 8
FAIL_KNOWN_GOOD_RUNTIME: Final = 9
FAIL_OPERATOR_REQUEST: Final = 10
FAILURE_NAMES: Final = {
    FAIL_CONFIG_INVALID: "config_invalid",
    FAIL_STATE_INVALID: "state_invalid",
    FAIL_SIGNATURE_INVALID: "signature_invalid",
    FAIL_VERSION_ROLLBACK: "version_rollback",
    FAIL_ARTIFACT_INTEGRITY: "artifact_integrity",
    FAIL_KERNEL_ENTRY: "kernel_entry",
    FAIL_INITIAL_HEALTH_TIMEOUT: "initial_health_timeout",
    FAIL_ATTEMPT_EXHAUSTED: "attempt_exhausted",
    FAIL_KNOWN_GOOD_RUNTIME: "known_good_runtime",
    FAIL_OPERATOR_REQUEST: "operator_request",
}
FAILURE_MASK_ALL: Final = (1 << FAILURE_COUNT) - 1

ACTION_RETRY_CANDIDATE: Final = 1
ACTION_SAFE: Final = 2
ACTION_PREVIOUS: Final = 3
ACTION_RECOVERY: Final = 4
ACTION_FIRMWARE: Final = 5
ACTION_HALT: Final = 6
ACTION_NAMES: Final = {
    ACTION_RETRY_CANDIDATE: "retry_candidate",
    ACTION_SAFE: "safe",
    ACTION_PREVIOUS: "previous",
    ACTION_RECOVERY: "recovery",
    ACTION_FIRMWARE: "firmware",
    ACTION_HALT: "halt",
}
ACTION_MASK_ALL: Final = (1 << len(ACTION_NAMES)) - 1

SLOT_BOOTABLE: Final = 1 << 0
SLOT_CANDIDATE_ALLOWED: Final = 1 << 1
SLOT_SAFE_ELIGIBLE: Final = 1 << 2
SLOT_FALLBACK_ELIGIBLE: Final = 1 << 3
SLOT_REQUIRED_FLAGS: Final = (
    SLOT_BOOTABLE | SLOT_CANDIDATE_ALLOWED | SLOT_SAFE_ELIGIBLE | SLOT_FALLBACK_ELIGIBLE
)

FAILURE_PRESERVE_EVIDENCE: Final = 1 << 0
FAILURE_CLEAR_PENDING: Final = 1 << 1
FAILURE_MARK_UNBOOTABLE: Final = 1 << 2
FAILURE_REQUIRE_PHYSICAL_PRESENCE: Final = 1 << 3
FAILURE_KNOWN_FLAGS: Final = (
    FAILURE_PRESERVE_EVIDENCE
    | FAILURE_CLEAR_PENDING
    | FAILURE_MARK_UNBOOTABLE
    | FAILURE_REQUIRE_PHYSICAL_PRESENCE
)

AUTH_INSPECT: Final = 1
AUTH_EXPORT_EVIDENCE: Final = 2
AUTH_SELECT_FALLBACK: Final = 3
AUTH_REQUEST_REBOOT: Final = 4
AUTH_UNLOCK_VOLUME: Final = 5
AUTH_REPAIR: Final = 6
AUTH_REINSTALL: Final = 7
AUTHORITY_NAMES: Final = {
    AUTH_INSPECT: "inspect",
    AUTH_EXPORT_EVIDENCE: "export_evidence",
    AUTH_SELECT_FALLBACK: "select_fallback",
    AUTH_REQUEST_REBOOT: "request_reboot",
    AUTH_UNLOCK_VOLUME: "unlock_encrypted_volume",
    AUTH_REPAIR: "repair",
    AUTH_REINSTALL: "reinstall",
}
AUTH_READ_ONLY: Final = 1 << 0
AUTH_DESTRUCTIVE: Final = 1 << 1
AUTH_OFFLINE_ONLY: Final = 1 << 2
AUTH_AUDITED: Final = 1 << 3
AUTH_KNOWN_FLAGS: Final = AUTH_READ_ONLY | AUTH_DESTRUCTIVE | AUTH_OFFLINE_ONLY | AUTH_AUDITED
FACTOR_PHYSICAL_PRESENCE: Final = 1 << 0
FACTOR_OPERATOR_AUTH: Final = 1 << 1
FACTOR_VERIFIED_BACKUP: Final = 1 << 2
FACTOR_SIGNATURE_VERIFIED: Final = 1 << 3
FACTOR_VOLUME_UNLOCKED: Final = 1 << 4
FACTOR_KNOWN_MASK: Final = (1 << 5) - 1
PROHIBIT_FIRMWARE: Final = 1 << 0
PROHIBIT_RAW_DISK: Final = 1 << 1
PROHIBIT_NETWORK: Final = 1 << 2
PROHIBIT_AMBIENT_ALL: Final = PROHIBIT_FIRMWARE | PROHIBIT_RAW_DISK | PROHIBIT_NETWORK
AUTHORITY_CEILING: Final = AUTHORITY_COUNT

STATE_WRITE_RECOVERY: Final = 1
TRANSPORT_SERIAL: Final = 1 << 0
TRANSPORT_GOP_SOFTWARE: Final = 1 << 1
REQUIRED_TRANSPORTS: Final = TRANSPORT_SERIAL | TRANSPORT_GOP_SOFTWARE
HANDOFF_SLOT: Final = 1 << 0
HANDOFF_MODE: Final = 1 << 1
HANDOFF_NONCE: Final = 1 << 2
HANDOFF_STATE_GENERATION: Final = 1 << 3
HANDOFF_POLICY_VERSION: Final = 1 << 4
HANDOFF_LAST_FAILURE: Final = 1 << 5
REQUIRED_HANDOFF_FIELDS: Final = (
    HANDOFF_SLOT
    | HANDOFF_MODE
    | HANDOFF_NONCE
    | HANDOFF_STATE_GENERATION
    | HANDOFF_POLICY_VERSION
    | HANDOFF_LAST_FAILURE
)

STATE_RECOVERY_REQUESTED: Final = 1 << 0
STATE_SAFE_REQUESTED: Final = 1 << 1
STATE_INFLIGHT: Final = 1 << 2
STATE_KNOWN_FLAGS: Final = STATE_RECOVERY_REQUESTED | STATE_SAFE_REQUESTED | STATE_INFLIGHT

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/recovery/Cargo.toml",
    "native/recovery/src/lib.rs",
    "native/recovery/src/bin/prec1_probe.rs",
    "runtime/native_recovery.py",
    "runtime/native_boot_artifact.py",
    "tools/generate_native_recovery_vectors.py",
    "tools/qualify_native_recovery.py",
    "tests/test_native_recovery.py",
    "docs/native-recovery-bundle.md",
)


class RecoveryError(RuntimeError):
    """Raised when bytes or transitions violate the PREC1 contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Slot:
    slot_id: int
    flags: int
    priority: int
    version: int
    minimum_recovery_version: int
    manifest_sha256: str
    kernel_sha256: str


@dataclasses.dataclass(frozen=True)
class FailureRule:
    failure_id: int
    primary_action: int
    fallback_action: int
    flags: int
    max_retries: int
    evidence_code: int
    allowed_modes: int


@dataclasses.dataclass(frozen=True)
class AuthorityRule:
    authority_id: int
    flags: int
    required_factors: int
    prohibited_ambient: int
    allowed_modes: int
    max_operations: int
    evidence_code: int


@dataclasses.dataclass(frozen=True)
class Bundle:
    bundle_version: int
    minimum_secure_version: int
    required_pbp_major: int
    minimum_pbp_minor: int
    required_kernel_abi_major: int
    minimum_kernel_abi_minor: int
    max_attempts: int
    max_safe_attempts: int
    success_deadline_seconds: int
    state_generation_floor: int
    recovery_component_sha256: str
    state_store_id: str
    slots: tuple[Slot, ...]
    failure_rules: tuple[FailureRule, ...]
    authority_rules: tuple[AuthorityRule, ...]
    body_sha256: str
    raw: bytes


@dataclasses.dataclass(frozen=True)
class RecoveryState:
    flags: int
    generation: int
    minimum_secure_version: int
    active_slot: int
    pending_slot: int
    known_good_mask: int
    unbootable_mask: int
    attempts_a: int
    attempts_b: int
    safe_attempted_mask: int
    current_mode: int
    last_failure: int
    transaction_id: int
    boot_nonce: int
    inflight_generation: int
    inflight_slot: int
    inflight_mode: int
    last_success_slot: int
    last_success_generation: int
    policy_version: int
    state_store_epoch: int
    evidence_sequence: int
    raw: bytes = b""


@dataclasses.dataclass(frozen=True)
class BootDecision:
    mode: int
    slot: int
    trial: bool
    persistence_required: bool
    reason: int
    state: RecoveryState


@dataclasses.dataclass(frozen=True)
class FailureDecision:
    action: int
    state: RecoveryState


@dataclasses.dataclass(frozen=True)
class SuccessReceipt:
    authenticated: bool
    generation: int
    slot: int
    mode: int
    boot_nonce: int


@dataclasses.dataclass(frozen=True)
class ActivationContext:
    outer_role: int
    outer_artifact_version: int
    outer_payload_digest_verified: bool
    outer_file_digest_verified: bool
    outer_signature_verified: bool
    inner_signature_verified: bool
    manifest_signature_verified: bool
    state_authenticated: bool
    state_generation_monotonic: bool
    version_floor_persisted: bool
    manifest_and_components_verified: bool
    pbp_major: int
    pbp_minor: int
    kernel_abi_major: int
    kernel_abi_minor: int
    offline_path: bool
    pdc_disabled: bool
    pooleglyph_independent: bool
    serial_or_gop_software_path: bool
    transaction_capacity_verified: bool
    evidence_preservation_ready: bool
    rollback_available: bool
    state_writable: bool


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "byte_count": len(data),
        "sha256": sha256_bytes(data),
    }


def _fail(code: str) -> None:
    raise RecoveryError(code)


def _mode_bit(mode: int) -> int:
    if mode not in MODE_NAMES:
        _fail("prec_mode")
    return 1 << (mode - 1)


def _digest(label: str) -> bytes:
    return hashlib.sha256(label.encode("ascii")).digest()


def _expected_failure_rows() -> tuple[tuple[int, int, int, int, int], ...]:
    preserve = FAILURE_PRESERVE_EVIDENCE
    retire = preserve | FAILURE_CLEAR_PENDING | FAILURE_MARK_UNBOOTABLE
    return (
        (ACTION_RECOVERY, ACTION_HALT, preserve, 0, MODE_MASK_ALL),
        (ACTION_RECOVERY, ACTION_HALT, preserve, 0, MODE_MASK_ALL),
        (ACTION_RECOVERY, ACTION_HALT, retire, 0, MODE_MASK_ALL),
        (ACTION_PREVIOUS, ACTION_RECOVERY, retire, 0, MODE_MASK_ALL),
        (ACTION_PREVIOUS, ACTION_RECOVERY, retire, 0, MODE_MASK_ALL),
        (ACTION_SAFE, ACTION_PREVIOUS, preserve, 1, MODE_MASK_ALL),
        (ACTION_RETRY_CANDIDATE, ACTION_PREVIOUS, preserve, 2, MODE_MASK_ALL),
        (ACTION_PREVIOUS, ACTION_RECOVERY, retire, 0, MODE_MASK_ALL),
        (ACTION_SAFE, ACTION_RECOVERY, preserve, 1, MODE_MASK_ALL),
        (ACTION_RECOVERY, ACTION_FIRMWARE, preserve, 0, MODE_MASK_ALL),
    )


def _expected_authority_rows() -> tuple[tuple[int, int, int, int, int], ...]:
    offline_audited = AUTH_OFFLINE_ONLY | AUTH_AUDITED
    read_only = AUTH_READ_ONLY | offline_audited
    recovery_diag = _mode_bit(MODE_RECOVERY) | _mode_bit(MODE_DIAGNOSTIC)
    recovery_only = _mode_bit(MODE_RECOVERY)
    destructive_factors = (
        FACTOR_PHYSICAL_PRESENCE
        | FACTOR_OPERATOR_AUTH
        | FACTOR_VERIFIED_BACKUP
        | FACTOR_SIGNATURE_VERIFIED
    )
    return (
        (read_only, 0, recovery_diag, 0, 201),
        (read_only, FACTOR_OPERATOR_AUTH, recovery_only, 0, 202),
        (offline_audited, FACTOR_PHYSICAL_PRESENCE | FACTOR_OPERATOR_AUTH, recovery_only, 1, 203),
        (offline_audited, FACTOR_OPERATOR_AUTH, recovery_only, 1, 204),
        (
            offline_audited,
            FACTOR_PHYSICAL_PRESENCE | FACTOR_OPERATOR_AUTH | FACTOR_VOLUME_UNLOCKED,
            recovery_only,
            3,
            205,
        ),
        (AUTH_DESTRUCTIVE | offline_audited, destructive_factors, recovery_only, 1, 206),
        (AUTH_DESTRUCTIVE | offline_audited, destructive_factors, recovery_only, 1, 207),
    )


def parse(data: bytes) -> Bundle:
    if len(data) < HEADER_BYTES:
        _fail("prec_truncated")
    if len(data) != TOTAL_BYTES:
        _fail("prec_total_size")
    if data[:8] != MAGIC:
        _fail("prec_magic")
    major, minor, header_bytes, alignment = struct.unpack_from("<HHHH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        _fail("prec_version")
    if header_bytes != HEADER_BYTES:
        _fail("prec_header_size")
    if alignment != RECORD_ALIGNMENT:
        _fail("prec_alignment")
    total_bytes, flags = struct.unpack_from("<II", data, 16)
    if total_bytes != TOTAL_BYTES:
        _fail("prec_total_size")
    if flags != REQUIRED_FLAGS:
        _fail("prec_flags")
    bundle_version, minimum_secure_version = struct.unpack_from("<QQ", data, 24)
    if bundle_version == 0 or minimum_secure_version == 0 or bundle_version < minimum_secure_version:
        _fail("prec_version_floor")
    required_pbp_major, minimum_pbp_minor, required_kernel_abi_major, minimum_kernel_abi_minor = struct.unpack_from(
        "<HHHH", data, 40
    )
    if required_pbp_major == 0 or required_kernel_abi_major == 0:
        _fail("prec_abi")
    max_attempts, max_safe_attempts = struct.unpack_from("<HH", data, 48)
    success_deadline_seconds = struct.unpack_from("<I", data, 52)[0]
    if not 1 <= max_attempts <= MAX_ATTEMPTS_LIMIT or max_safe_attempts != 1:
        _fail("prec_attempt_policy")
    if not 1 <= success_deadline_seconds <= MAX_SUCCESS_DEADLINE_SECONDS:
        _fail("prec_success_deadline")
    state_bytes, checksum_bytes, slot_count, failure_count, authority_count, write_policy = struct.unpack_from(
        "<HHHHHH", data, 56
    )
    if (state_bytes, checksum_bytes) != (STATE_BYTES, STATE_CHECKSUM_BYTES):
        _fail("prec_state_geometry")
    if (slot_count, failure_count, authority_count) != (SLOT_COUNT, FAILURE_COUNT, AUTHORITY_COUNT):
        _fail("prec_record_count")
    if write_policy != STATE_WRITE_RECOVERY:
        _fail("prec_state_write_policy")
    slot_offset, failure_offset, authority_offset = struct.unpack_from("<III", data, 68)
    if (slot_offset, failure_offset, authority_offset) != (SLOT_OFFSET, FAILURE_OFFSET, AUTHORITY_OFFSET):
        _fail("prec_table_layout")
    allowed_modes, failure_mask, action_mask, handoff_fields = struct.unpack_from("<IIII", data, 80)
    if allowed_modes != MODE_MASK_ALL:
        _fail("prec_modes")
    if failure_mask != FAILURE_MASK_ALL or action_mask != ACTION_MASK_ALL:
        _fail("prec_failure_action_mask")
    if handoff_fields != REQUIRED_HANDOFF_FIELDS:
        _fail("prec_handoff_fields")
    state_generation_floor = struct.unpack_from("<Q", data, 96)[0]
    if state_generation_floor == 0:
        _fail("prec_state_generation_floor")
    expected_body = data[104:136]
    if hashlib.sha256(data[HEADER_BYTES:]).digest() != expected_body:
        _fail("prec_body_digest")
    recovery_component = data[136:168]
    if not any(recovery_component):
        _fail("prec_recovery_component_digest")
    state_store_id = data[168:184]
    if not any(state_store_id):
        _fail("prec_state_store_id")
    normal_fallback, safe_fallback, no_known_good, write_failure = struct.unpack_from("<HHHH", data, 184)
    if (normal_fallback, safe_fallback, no_known_good, write_failure) != (
        ACTION_PREVIOUS,
        ACTION_RECOVERY,
        ACTION_RECOVERY,
        ACTION_RECOVERY,
    ):
        _fail("prec_fallback_policy")
    authority_ceiling, required_transports = struct.unpack_from("<II", data, 192)
    if authority_ceiling != AUTHORITY_CEILING:
        _fail("prec_authority_ceiling")
    if required_transports != REQUIRED_TRANSPORTS:
        _fail("prec_transport_policy")
    if any(data[200:HEADER_BYTES]):
        _fail("prec_reserved")

    slots: list[Slot] = []
    seen_manifests: set[bytes] = set()
    seen_kernels: set[bytes] = set()
    for index in range(SLOT_COUNT):
        offset = SLOT_OFFSET + index * SLOT_BYTES
        slot_id, slot_flags, priority = struct.unpack_from("<HHI", data, offset)
        version, minimum_recovery = struct.unpack_from("<QQ", data, offset + 8)
        manifest = data[offset + 24 : offset + 56]
        kernel = data[offset + 56 : offset + 88]
        if slot_id != index + 1:
            _fail("prec_slot_id")
        if slot_flags != SLOT_REQUIRED_FLAGS:
            _fail("prec_slot_flags")
        if priority == 0 or (index and priority >= slots[index - 1].priority):
            _fail("prec_slot_priority")
        if version < minimum_secure_version or minimum_recovery == 0 or minimum_recovery > bundle_version:
            _fail("prec_slot_version")
        if not any(manifest) or not any(kernel) or manifest in seen_manifests or kernel in seen_kernels:
            _fail("prec_slot_digest")
        if any(data[offset + 88 : offset + SLOT_BYTES]):
            _fail("prec_slot_reserved")
        seen_manifests.add(manifest)
        seen_kernels.add(kernel)
        slots.append(
            Slot(
                slot_id,
                slot_flags,
                priority,
                version,
                minimum_recovery,
                manifest.hex().upper(),
                kernel.hex().upper(),
            )
        )

    failure_rules: list[FailureRule] = []
    for index, expected in enumerate(_expected_failure_rows()):
        offset = FAILURE_OFFSET + index * FAILURE_BYTES
        failure_id, primary, fallback, rule_flags, max_retries, evidence_code = struct.unpack_from(
            "<HHHHHH", data, offset
        )
        allowed = struct.unpack_from("<I", data, offset + 12)[0]
        if failure_id != index + 1:
            _fail("prec_failure_id")
        if (primary, fallback, rule_flags, max_retries, allowed) != expected:
            _fail("prec_failure_rule")
        if evidence_code != 100 + failure_id:
            _fail("prec_failure_evidence")
        if rule_flags & ~FAILURE_KNOWN_FLAGS:
            _fail("prec_failure_rule")
        if any(data[offset + 16 : offset + FAILURE_BYTES]):
            _fail("prec_failure_reserved")
        failure_rules.append(
            FailureRule(failure_id, primary, fallback, rule_flags, max_retries, evidence_code, allowed)
        )

    authority_rules: list[AuthorityRule] = []
    for index, expected in enumerate(_expected_authority_rows()):
        offset = AUTHORITY_OFFSET + index * AUTHORITY_BYTES
        authority_id, authority_flags = struct.unpack_from("<HH", data, offset)
        factors, prohibited, allowed = struct.unpack_from("<III", data, offset + 4)
        max_operations, reserved = struct.unpack_from("<HH", data, offset + 16)
        evidence_code = struct.unpack_from("<I", data, offset + 20)[0]
        if authority_id != index + 1:
            _fail("prec_authority_id")
        expected_flags, expected_factors, expected_modes, expected_max, expected_evidence = expected
        if (
            authority_flags,
            factors,
            allowed,
            max_operations,
            evidence_code,
        ) != (expected_flags, expected_factors, expected_modes, expected_max, expected_evidence):
            _fail("prec_authority_rule")
        if authority_flags & ~AUTH_KNOWN_FLAGS or factors & ~FACTOR_KNOWN_MASK:
            _fail("prec_authority_rule")
        if prohibited != PROHIBIT_AMBIENT_ALL:
            _fail("prec_authority_ambient")
        if any(data[offset + 24 : offset + AUTHORITY_BYTES]) or reserved != 0:
            _fail("prec_authority_reserved")
        authority_rules.append(
            AuthorityRule(authority_id, authority_flags, factors, prohibited, allowed, max_operations, evidence_code)
        )

    return Bundle(
        bundle_version,
        minimum_secure_version,
        required_pbp_major,
        minimum_pbp_minor,
        required_kernel_abi_major,
        minimum_kernel_abi_minor,
        max_attempts,
        max_safe_attempts,
        success_deadline_seconds,
        state_generation_floor,
        recovery_component.hex().upper(),
        state_store_id.hex().upper(),
        tuple(slots),
        tuple(failure_rules),
        tuple(authority_rules),
        expected_body.hex().upper(),
        data,
    )


def encode(
    *,
    bundle_version: int,
    minimum_secure_version: int,
    state_generation_floor: int,
    max_attempts: int = 3,
    success_deadline_seconds: int = 300,
    slot_versions: tuple[int, int] = (2, 1),
    label: str = "canonical",
) -> bytes:
    output = bytearray(TOTAL_BYTES)
    output[:8] = MAGIC
    struct.pack_into(
        "<HHHHIIQQHHHHHHIHHHHHHIII",
        output,
        8,
        MAJOR_VERSION,
        MINOR_VERSION,
        HEADER_BYTES,
        RECORD_ALIGNMENT,
        TOTAL_BYTES,
        REQUIRED_FLAGS,
        bundle_version,
        minimum_secure_version,
        1,
        0,
        1,
        0,
        max_attempts,
        1,
        success_deadline_seconds,
        STATE_BYTES,
        STATE_CHECKSUM_BYTES,
        SLOT_COUNT,
        FAILURE_COUNT,
        AUTHORITY_COUNT,
        STATE_WRITE_RECOVERY,
        SLOT_OFFSET,
        FAILURE_OFFSET,
        AUTHORITY_OFFSET,
    )
    struct.pack_into(
        "<IIIIQ",
        output,
        80,
        MODE_MASK_ALL,
        FAILURE_MASK_ALL,
        ACTION_MASK_ALL,
        REQUIRED_HANDOFF_FIELDS,
        state_generation_floor,
    )
    output[136:168] = _digest(f"PREC1:{label}:recovery-component")
    output[168:184] = _digest(f"PREC1:{label}:state-store")[:16]
    struct.pack_into(
        "<HHHHII",
        output,
        184,
        ACTION_PREVIOUS,
        ACTION_RECOVERY,
        ACTION_RECOVERY,
        ACTION_RECOVERY,
        AUTHORITY_CEILING,
        REQUIRED_TRANSPORTS,
    )
    for index, version in enumerate(slot_versions):
        offset = SLOT_OFFSET + index * SLOT_BYTES
        struct.pack_into(
            "<HHIQQ",
            output,
            offset,
            index + 1,
            SLOT_REQUIRED_FLAGS,
            15 - index,
            version,
            minimum_secure_version,
        )
        output[offset + 24 : offset + 56] = _digest(f"PREC1:{label}:slot-{index + 1}:manifest")
        output[offset + 56 : offset + 88] = _digest(f"PREC1:{label}:slot-{index + 1}:kernel")
    for index, row in enumerate(_expected_failure_rows()):
        offset = FAILURE_OFFSET + index * FAILURE_BYTES
        primary, fallback, rule_flags, max_retries, allowed = row
        struct.pack_into(
            "<HHHHHHI",
            output,
            offset,
            index + 1,
            primary,
            fallback,
            rule_flags,
            max_retries,
            101 + index,
            allowed,
        )
    for index, row in enumerate(_expected_authority_rows()):
        offset = AUTHORITY_OFFSET + index * AUTHORITY_BYTES
        flags, factors, allowed, max_operations, evidence_code = row
        struct.pack_into(
            "<HHIIIHHI",
            output,
            offset,
            index + 1,
            flags,
            factors,
            PROHIBIT_AMBIENT_ALL,
            allowed,
            max_operations,
            0,
            evidence_code,
        )
    output[104:136] = hashlib.sha256(output[HEADER_BYTES:]).digest()
    result = bytes(output)
    parse(result)
    return result


def canonical_bundle() -> bytes:
    return encode(
        bundle_version=1,
        minimum_secure_version=1,
        state_generation_floor=11,
        slot_versions=(2, 1),
        label="canonical",
    )


def minimal_bundle() -> bytes:
    return encode(
        bundle_version=1,
        minimum_secure_version=1,
        state_generation_floor=1,
        max_attempts=1,
        success_deadline_seconds=60,
        slot_versions=(1, 1),
        label="minimal",
    )


def versioned_bundle() -> bytes:
    return encode(
        bundle_version=7,
        minimum_secure_version=6,
        state_generation_floor=41,
        max_attempts=5,
        success_deadline_seconds=600,
        slot_versions=(9, 8),
        label="versioned",
    )


def summary(bundle: Bundle) -> str:
    return (
        f"OK;version={bundle.bundle_version};minimum_secure_version={bundle.minimum_secure_version};"
        f"slots={len(bundle.slots)};failures={len(bundle.failure_rules)};authorities={len(bundle.authority_rules)};"
        f"max_attempts={bundle.max_attempts};state_floor={bundle.state_generation_floor};"
        f"body_sha256={bundle.body_sha256}"
    )


def parse_result(data: bytes) -> str:
    try:
        return summary(parse(data))
    except RecoveryError as error:
        return f"ERR:{error.code}"


def state_checksum(data: bytes) -> bytes:
    if len(data) < STATE_BYTES - STATE_CHECKSUM_BYTES:
        _fail("prec_state_truncated")
    return hashlib.sha256(data[: STATE_BYTES - STATE_CHECKSUM_BYTES]).digest()[:STATE_CHECKSUM_BYTES]


def encode_state(state: RecoveryState) -> bytes:
    output = bytearray(STATE_BYTES)
    output[:8] = STATE_MAGIC
    struct.pack_into("<HHHH", output, 8, MAJOR_VERSION, MINOR_VERSION, STATE_BYTES, state.flags)
    struct.pack_into("<QQ", output, 16, state.generation, state.minimum_secure_version)
    struct.pack_into(
        "<BBBBBBBB",
        output,
        32,
        state.active_slot,
        state.pending_slot,
        state.known_good_mask,
        state.unbootable_mask,
        state.attempts_a,
        state.attempts_b,
        state.safe_attempted_mask,
        state.current_mode,
    )
    struct.pack_into("<HH", output, 40, state.last_failure, 0)
    struct.pack_into("<QQQ", output, 44, state.transaction_id, state.boot_nonce, state.inflight_generation)
    struct.pack_into(
        "<BBBB",
        output,
        68,
        state.inflight_slot,
        state.inflight_mode,
        state.last_success_slot,
        0,
    )
    struct.pack_into(
        "<QQQQQ",
        output,
        72,
        state.last_success_generation,
        state.policy_version,
        state.state_store_epoch,
        state.evidence_sequence,
        0,
    )
    output[112:128] = state_checksum(bytes(output))
    result = bytes(output)
    parse_state(result)
    return result


def parse_state(data: bytes, policy: Bundle | None = None) -> RecoveryState:
    if len(data) < STATE_BYTES:
        _fail("prec_state_truncated")
    if len(data) != STATE_BYTES:
        _fail("prec_state_size")
    if data[:8] != STATE_MAGIC:
        _fail("prec_state_magic")
    major, minor, state_bytes, flags = struct.unpack_from("<HHHH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        _fail("prec_state_version")
    if state_bytes != STATE_BYTES:
        _fail("prec_state_size")
    if flags & ~STATE_KNOWN_FLAGS:
        _fail("prec_state_flags")
    generation, minimum_secure_version = struct.unpack_from("<QQ", data, 16)
    if generation == 0 or minimum_secure_version == 0:
        _fail("prec_state_floor")
    active_slot, pending_slot, known_good, unbootable, attempts_a, attempts_b, safe_mask, current_mode = struct.unpack_from(
        "<BBBBBBBB", data, 32
    )
    if active_slot not in (1, 2) or pending_slot not in (0, 1, 2) or pending_slot == active_slot:
        _fail("prec_state_slot")
    if known_good == 0 or known_good & ~0b11 or unbootable & ~0b11 or safe_mask & ~0b11:
        _fail("prec_state_mask")
    if known_good & unbootable:
        _fail("prec_state_mask_conflict")
    if not known_good & (1 << (active_slot - 1)):
        _fail("prec_state_active_known_good")
    attempt_limit = policy.max_attempts if policy else MAX_ATTEMPTS_LIMIT
    if attempts_a > attempt_limit or attempts_b > attempt_limit:
        _fail("prec_state_attempts")
    if current_mode not in (0, *MODE_NAMES):
        _fail("prec_state_mode")
    last_failure, reserved = struct.unpack_from("<HH", data, 40)
    if last_failure not in (0, *FAILURE_NAMES) or reserved != 0:
        _fail("prec_state_failure")
    transaction_id, boot_nonce, inflight_generation = struct.unpack_from("<QQQ", data, 44)
    inflight_slot, inflight_mode, last_success_slot, reserved_byte = struct.unpack_from("<BBBB", data, 68)
    last_success_generation, policy_version, state_store_epoch, evidence_sequence, reserved_qword = struct.unpack_from(
        "<QQQQQ", data, 72
    )
    if last_success_slot not in (1, 2) or last_success_generation == 0 or last_success_generation > generation:
        _fail("prec_state_success")
    if policy_version == 0 or state_store_epoch == 0 or evidence_sequence == 0:
        _fail("prec_state_metadata")
    if policy and (
        generation < policy.state_generation_floor
        or minimum_secure_version < policy.minimum_secure_version
        or policy_version != policy.bundle_version
    ):
        _fail("prec_state_policy_binding")
    inflight = bool(flags & STATE_INFLIGHT)
    if inflight:
        if (
            boot_nonce == 0
            or inflight_generation != generation
            or inflight_slot not in (1, 2)
            or inflight_mode not in MODE_NAMES
            or current_mode != inflight_mode
        ):
            _fail("prec_state_inflight")
    elif boot_nonce or inflight_generation or inflight_slot or inflight_mode:
        _fail("prec_state_inflight")
    if reserved_byte != 0 or reserved_qword != 0:
        _fail("prec_state_reserved")
    if data[112:128] != state_checksum(data):
        _fail("prec_state_checksum")
    return RecoveryState(
        flags,
        generation,
        minimum_secure_version,
        active_slot,
        pending_slot,
        known_good,
        unbootable,
        attempts_a,
        attempts_b,
        safe_mask,
        current_mode,
        last_failure,
        transaction_id,
        boot_nonce,
        inflight_generation,
        inflight_slot,
        inflight_mode,
        last_success_slot,
        last_success_generation,
        policy_version,
        state_store_epoch,
        evidence_sequence,
        data,
    )


def state_summary(state: RecoveryState) -> str:
    return (
        f"OK;generation={state.generation};active={state.active_slot};pending={state.pending_slot};"
        f"known_good={state.known_good_mask};unbootable={state.unbootable_mask};"
        f"attempts={state.attempts_a},{state.attempts_b};mode={state.current_mode};"
        f"failure={state.last_failure};inflight={int(bool(state.flags & STATE_INFLIGHT))}"
    )


def parse_state_result(data: bytes) -> str:
    try:
        return state_summary(parse_state(data))
    except RecoveryError as error:
        return f"ERR:{error.code}"


def _base_state(
    policy: Bundle,
    *,
    generation: int,
    active_slot: int,
    pending_slot: int,
    known_good_mask: int,
    attempts: tuple[int, int],
    flags: int = 0,
    safe_attempted_mask: int = 0,
) -> RecoveryState:
    state = RecoveryState(
        flags=flags,
        generation=generation,
        minimum_secure_version=policy.minimum_secure_version,
        active_slot=active_slot,
        pending_slot=pending_slot,
        known_good_mask=known_good_mask,
        unbootable_mask=0,
        attempts_a=attempts[0],
        attempts_b=attempts[1],
        safe_attempted_mask=safe_attempted_mask,
        current_mode=0,
        last_failure=0,
        transaction_id=0x504F4F4C00000000 | generation,
        boot_nonce=0,
        inflight_generation=0,
        inflight_slot=0,
        inflight_mode=0,
        last_success_slot=active_slot,
        last_success_generation=generation,
        policy_version=policy.bundle_version,
        state_store_epoch=1,
        evidence_sequence=1,
    )
    return parse_state(encode_state(state), policy)


def canonical_state(policy: Bundle | None = None) -> RecoveryState:
    selected = policy or parse(canonical_bundle())
    return _base_state(
        selected,
        generation=selected.state_generation_floor,
        active_slot=2,
        pending_slot=1,
        known_good_mask=0b10,
        attempts=(selected.max_attempts, selected.max_attempts),
    )


def minimal_state(policy: Bundle | None = None) -> RecoveryState:
    selected = policy or parse(minimal_bundle())
    return _base_state(
        selected,
        generation=selected.state_generation_floor,
        active_slot=1,
        pending_slot=0,
        known_good_mask=0b01,
        attempts=(selected.max_attempts, selected.max_attempts),
    )


def _slot_bit(slot: int) -> int:
    if slot not in (1, 2):
        _fail("prec_transition_slot")
    return 1 << (slot - 1)


def _slot_record(policy: Bundle, slot: int) -> Slot:
    return policy.slots[slot - 1]


def _eligible(policy: Bundle, state: RecoveryState, slot: int, *, known_good: bool) -> bool:
    bit = _slot_bit(slot)
    record = _slot_record(policy, slot)
    if not record.flags & SLOT_BOOTABLE or state.unbootable_mask & bit:
        return False
    if record.version < max(policy.minimum_secure_version, state.minimum_secure_version):
        return False
    return not known_good or bool(state.known_good_mask & bit)


def _attempts(state: RecoveryState, slot: int) -> int:
    return state.attempts_a if slot == 1 else state.attempts_b


def _with_attempts(state: RecoveryState, slot: int, attempts: int) -> RecoveryState:
    return dataclasses.replace(state, attempts_a=attempts) if slot == 1 else dataclasses.replace(state, attempts_b=attempts)


def _next_generation(state: RecoveryState) -> int:
    if state.generation == (1 << 64) - 1:
        _fail("prec_transition_generation")
    return state.generation + 1


def _recovery_decision(state: RecoveryState, reason: int) -> BootDecision:
    generation = _next_generation(state)
    next_state = dataclasses.replace(
        state,
        flags=state.flags & ~(STATE_INFLIGHT | STATE_SAFE_REQUESTED),
        generation=generation,
        current_mode=MODE_RECOVERY,
        last_failure=reason,
        boot_nonce=0,
        inflight_generation=0,
        inflight_slot=0,
        inflight_mode=0,
        evidence_sequence=state.evidence_sequence + 1,
        raw=b"",
    )
    next_state = parse_state(encode_state(next_state))
    return BootDecision(MODE_RECOVERY, 0, False, True, reason, next_state)


def _select_slot(
    state: RecoveryState,
    *,
    slot: int,
    mode: int,
    trial: bool,
    nonce: int,
    safe_attempted_mask: int | None = None,
) -> BootDecision:
    if nonce == 0:
        _fail("prec_transition_nonce")
    generation = _next_generation(state)
    next_state = dataclasses.replace(
        state,
        flags=(state.flags | STATE_INFLIGHT) & ~(STATE_RECOVERY_REQUESTED | STATE_SAFE_REQUESTED),
        generation=generation,
        current_mode=mode,
        boot_nonce=nonce,
        inflight_generation=generation,
        inflight_slot=slot,
        inflight_mode=mode,
        safe_attempted_mask=state.safe_attempted_mask if safe_attempted_mask is None else safe_attempted_mask,
        evidence_sequence=state.evidence_sequence + 1,
        raw=b"",
    )
    next_state = parse_state(encode_state(next_state))
    return BootDecision(mode, slot, trial, True, 0, next_state)


def select_boot(
    policy: Bundle,
    state: RecoveryState,
    requested_mode: int = 0,
    *,
    physical_presence: bool = False,
    boot_nonce: int = 1,
    state_authenticated: bool = True,
    state_writable: bool = True,
) -> BootDecision:
    parse(policy.raw)
    parse_state(encode_state(state), policy)
    if not state_authenticated:
        _fail("prec_transition_state_auth")
    if state.flags & STATE_INFLIGHT:
        _fail("prec_transition_inflight")
    if not state_writable:
        return BootDecision(MODE_RECOVERY, 0, False, False, FAIL_STATE_INVALID, state)
    mode = requested_mode
    if state.flags & STATE_RECOVERY_REQUESTED:
        mode = MODE_RECOVERY
    elif state.flags & STATE_SAFE_REQUESTED:
        mode = MODE_SAFE
    elif mode == 0:
        mode = MODE_NORMAL
    _mode_bit(mode)
    if not MODE_MASK_ALL & _mode_bit(mode):
        _fail("prec_transition_mode")
    if mode == MODE_FIRMWARE:
        if not physical_presence:
            _fail("prec_transition_physical_presence")
        generation = _next_generation(state)
        next_state = dataclasses.replace(
            state,
            generation=generation,
            current_mode=MODE_FIRMWARE,
            evidence_sequence=state.evidence_sequence + 1,
            raw=b"",
        )
        next_state = parse_state(encode_state(next_state))
        return BootDecision(mode, 0, False, True, 0, next_state)
    if mode == MODE_RECOVERY:
        return _recovery_decision(state, state.last_failure)

    if mode == MODE_NORMAL and state.pending_slot:
        slot = state.pending_slot
        if _eligible(policy, state, slot, known_good=False) and _attempts(state, slot) > 0:
            decremented = _with_attempts(state, slot, _attempts(state, slot) - 1)
            return _select_slot(decremented, slot=slot, mode=mode, trial=True, nonce=boot_nonce)
        retired = dataclasses.replace(
            state,
            pending_slot=0,
            unbootable_mask=state.unbootable_mask | _slot_bit(slot),
            known_good_mask=state.known_good_mask & ~_slot_bit(slot),
            last_failure=FAIL_ATTEMPT_EXHAUSTED,
        )
        state = retired
        mode = MODE_PREVIOUS

    if mode == MODE_SAFE:
        candidates = (state.active_slot, 3 - state.active_slot)
        for slot in candidates:
            bit = _slot_bit(slot)
            if _eligible(policy, state, slot, known_good=True) and not state.safe_attempted_mask & bit:
                return _select_slot(
                    state,
                    slot=slot,
                    mode=mode,
                    trial=False,
                    nonce=boot_nonce,
                    safe_attempted_mask=state.safe_attempted_mask | bit,
                )
        return _recovery_decision(state, FAIL_ATTEMPT_EXHAUSTED)

    if mode == MODE_PREVIOUS:
        candidates = (3 - state.active_slot, state.active_slot)
    else:
        candidates = (state.active_slot, 3 - state.active_slot)
    for slot in candidates:
        if _eligible(policy, state, slot, known_good=True):
            return _select_slot(state, slot=slot, mode=mode, trial=False, nonce=boot_nonce)
    return _recovery_decision(state, FAIL_ATTEMPT_EXHAUSTED)


def decision_summary(decision: BootDecision) -> str:
    return (
        f"OK;mode={decision.mode};slot={decision.slot};trial={int(decision.trial)};"
        f"persist={int(decision.persistence_required)};reason={decision.reason};"
        f"generation={decision.state.generation};attempts={decision.state.attempts_a},{decision.state.attempts_b};"
        f"known_good={decision.state.known_good_mask};unbootable={decision.state.unbootable_mask}"
    )


def report_boot_success(policy: Bundle, state: RecoveryState, receipt: SuccessReceipt) -> RecoveryState:
    parse_state(encode_state(state), policy)
    if not receipt.authenticated:
        _fail("prec_receipt_auth")
    if not state.flags & STATE_INFLIGHT:
        _fail("prec_receipt_inflight")
    if (
        receipt.generation != state.inflight_generation
        or receipt.slot != state.inflight_slot
        or receipt.mode != state.inflight_mode
        or receipt.boot_nonce != state.boot_nonce
    ):
        _fail("prec_receipt_binding")
    bit = _slot_bit(receipt.slot)
    pending_success = state.pending_slot == receipt.slot
    generation = _next_generation(state)
    next_state = dataclasses.replace(
        state,
        flags=state.flags & ~(STATE_INFLIGHT | STATE_RECOVERY_REQUESTED | STATE_SAFE_REQUESTED),
        generation=generation,
        minimum_secure_version=max(state.minimum_secure_version, policy.minimum_secure_version),
        active_slot=receipt.slot,
        pending_slot=0 if pending_success else state.pending_slot,
        known_good_mask=state.known_good_mask | bit,
        unbootable_mask=state.unbootable_mask & ~bit,
        attempts_a=policy.max_attempts if receipt.slot == 1 else state.attempts_a,
        attempts_b=policy.max_attempts if receipt.slot == 2 else state.attempts_b,
        current_mode=receipt.mode,
        last_failure=0,
        boot_nonce=0,
        inflight_generation=0,
        inflight_slot=0,
        inflight_mode=0,
        last_success_slot=receipt.slot,
        last_success_generation=generation,
        policy_version=policy.bundle_version,
        evidence_sequence=state.evidence_sequence + 1,
        raw=b"",
    )
    return parse_state(encode_state(next_state), policy)


def report_boot_failure(
    policy: Bundle,
    state: RecoveryState,
    failure_id: int,
    *,
    authenticated: bool,
) -> FailureDecision:
    parse_state(encode_state(state), policy)
    if not authenticated:
        _fail("prec_failure_receipt_auth")
    if not state.flags & STATE_INFLIGHT:
        _fail("prec_failure_receipt_inflight")
    if failure_id not in FAILURE_NAMES:
        _fail("prec_failure_receipt_id")
    rule = policy.failure_rules[failure_id - 1]
    slot = state.inflight_slot
    bit = _slot_bit(slot)
    trial = state.pending_slot == slot and not state.known_good_mask & bit
    action = rule.primary_action
    pending_slot = state.pending_slot
    known_good = state.known_good_mask
    unbootable = state.unbootable_mask
    if rule.flags & FAILURE_MARK_UNBOOTABLE:
        unbootable |= bit
        known_good &= ~bit
    if rule.flags & FAILURE_CLEAR_PENDING and pending_slot == slot:
        pending_slot = 0
    if action == ACTION_RETRY_CANDIDATE and (not trial or _attempts(state, slot) == 0):
        action = rule.fallback_action
    if action == ACTION_SAFE and state.safe_attempted_mask & bit:
        action = rule.fallback_action
    if action == ACTION_PREVIOUS:
        other = 3 - slot
        if not _eligible(policy, dataclasses.replace(state, known_good_mask=known_good, unbootable_mask=unbootable), other, known_good=True):
            action = ACTION_RECOVERY
    generation = _next_generation(state)
    mode = {
        ACTION_RETRY_CANDIDATE: MODE_NORMAL,
        ACTION_SAFE: MODE_SAFE,
        ACTION_PREVIOUS: MODE_PREVIOUS,
        ACTION_RECOVERY: MODE_RECOVERY,
        ACTION_FIRMWARE: MODE_FIRMWARE,
        ACTION_HALT: MODE_RECOVERY,
    }[action]
    next_state = dataclasses.replace(
        state,
        flags=state.flags & ~STATE_INFLIGHT,
        generation=generation,
        pending_slot=pending_slot,
        known_good_mask=known_good,
        unbootable_mask=unbootable,
        current_mode=mode,
        last_failure=failure_id,
        boot_nonce=0,
        inflight_generation=0,
        inflight_slot=0,
        inflight_mode=0,
        evidence_sequence=state.evidence_sequence + 1,
        raw=b"",
    )
    return FailureDecision(action, parse_state(encode_state(next_state)))


def development_activation_context() -> ActivationContext:
    return ActivationContext(
        outer_role=3,
        outer_artifact_version=1,
        outer_payload_digest_verified=True,
        outer_file_digest_verified=True,
        outer_signature_verified=False,
        inner_signature_verified=False,
        manifest_signature_verified=False,
        state_authenticated=False,
        state_generation_monotonic=False,
        version_floor_persisted=False,
        manifest_and_components_verified=False,
        pbp_major=1,
        pbp_minor=0,
        kernel_abi_major=1,
        kernel_abi_minor=0,
        offline_path=True,
        pdc_disabled=True,
        pooleglyph_independent=True,
        serial_or_gop_software_path=True,
        transaction_capacity_verified=False,
        evidence_preservation_ready=False,
        rollback_available=False,
        state_writable=False,
    )


def synthetic_qualified_activation_context(bundle: Bundle | None = None) -> ActivationContext:
    policy = bundle or parse(canonical_bundle())
    return ActivationContext(
        outer_role=3,
        outer_artifact_version=policy.bundle_version,
        outer_payload_digest_verified=True,
        outer_file_digest_verified=True,
        outer_signature_verified=True,
        inner_signature_verified=True,
        manifest_signature_verified=True,
        state_authenticated=True,
        state_generation_monotonic=True,
        version_floor_persisted=True,
        manifest_and_components_verified=True,
        pbp_major=policy.required_pbp_major,
        pbp_minor=policy.minimum_pbp_minor,
        kernel_abi_major=policy.required_kernel_abi_major,
        kernel_abi_minor=policy.minimum_kernel_abi_minor,
        offline_path=True,
        pdc_disabled=True,
        pooleglyph_independent=True,
        serial_or_gop_software_path=True,
        transaction_capacity_verified=True,
        evidence_preservation_ready=True,
        rollback_available=True,
        state_writable=True,
    )


ACTIVATION_MODES: Final = (
    "development",
    "role",
    "version",
    "payload-digest",
    "file-digest",
    "outer-signature",
    "inner-signature",
    "manifest-signature",
    "state-auth",
    "state-generation",
    "version-floor",
    "components",
    "pbp",
    "kernel-abi",
    "offline",
    "pdc-disabled",
    "pooleglyph-independent",
    "display-path",
    "transaction-capacity",
    "evidence",
    "rollback",
    "state-writable",
)


def activation_context(mode: str, bundle: Bundle | None = None) -> ActivationContext:
    policy = bundle or parse(canonical_bundle())
    if mode == "development":
        return development_activation_context()
    context = synthetic_qualified_activation_context(policy)
    changes: dict[str, Any] = {
        "role": {"outer_role": 2},
        "version": {"outer_artifact_version": policy.bundle_version + 1},
        "payload-digest": {"outer_payload_digest_verified": False},
        "file-digest": {"outer_file_digest_verified": False},
        "outer-signature": {"outer_signature_verified": False},
        "inner-signature": {"inner_signature_verified": False},
        "manifest-signature": {"manifest_signature_verified": False},
        "state-auth": {"state_authenticated": False},
        "state-generation": {"state_generation_monotonic": False},
        "version-floor": {"version_floor_persisted": False},
        "components": {"manifest_and_components_verified": False},
        "pbp": {"pbp_major": policy.required_pbp_major + 1},
        "kernel-abi": {"kernel_abi_major": policy.required_kernel_abi_major + 1},
        "offline": {"offline_path": False},
        "pdc-disabled": {"pdc_disabled": False},
        "pooleglyph-independent": {"pooleglyph_independent": False},
        "display-path": {"serial_or_gop_software_path": False},
        "transaction-capacity": {"transaction_capacity_verified": False},
        "evidence": {"evidence_preservation_ready": False},
        "rollback": {"rollback_available": False},
        "state-writable": {"state_writable": False},
    }
    if mode not in changes:
        _fail("prec_activation_mode")
    return dataclasses.replace(context, **changes[mode])


def activation_errors(bundle: Bundle, context: ActivationContext) -> tuple[str, ...]:
    errors: list[str] = []
    checks = (
        (context.outer_role == 3, "prec_activation_role"),
        (context.outer_artifact_version == bundle.bundle_version, "prec_activation_version"),
        (context.outer_payload_digest_verified, "prec_activation_outer_payload_digest"),
        (context.outer_file_digest_verified, "prec_activation_outer_file_digest"),
        (context.outer_signature_verified, "prec_activation_outer_signature"),
        (context.inner_signature_verified, "prec_activation_inner_signature"),
        (context.manifest_signature_verified, "prec_activation_manifest_signature"),
        (context.state_authenticated, "prec_activation_state_auth"),
        (context.state_generation_monotonic, "prec_activation_state_generation"),
        (context.version_floor_persisted, "prec_activation_version_floor"),
        (context.manifest_and_components_verified, "prec_activation_components"),
        (
            context.pbp_major == bundle.required_pbp_major and context.pbp_minor >= bundle.minimum_pbp_minor,
            "prec_activation_pbp",
        ),
        (
            context.kernel_abi_major == bundle.required_kernel_abi_major
            and context.kernel_abi_minor >= bundle.minimum_kernel_abi_minor,
            "prec_activation_kernel_abi",
        ),
        (context.offline_path, "prec_activation_offline"),
        (context.pdc_disabled, "prec_activation_pdc_disabled"),
        (context.pooleglyph_independent, "prec_activation_pooleglyph_independent"),
        (context.serial_or_gop_software_path, "prec_activation_display_path"),
        (context.transaction_capacity_verified, "prec_activation_transaction_capacity"),
        (context.evidence_preservation_ready, "prec_activation_evidence"),
        (context.rollback_available, "prec_activation_rollback"),
        (context.state_writable, "prec_activation_state_writable"),
    )
    for passed, code in checks:
        if not passed:
            errors.append(code)
    return tuple(errors)


def authorize_activation(bundle: Bundle, context: ActivationContext) -> None:
    errors = activation_errors(bundle, context)
    if errors:
        _fail(errors[0])


def build_fixture(vector_id: str) -> tuple[bytes, RecoveryState, int]:
    if vector_id == "minimal-known-good":
        policy_bytes = minimal_bundle()
        policy = parse(policy_bytes)
        return policy_bytes, minimal_state(policy), MODE_NORMAL
    if vector_id == "canonical-trial":
        policy_bytes = canonical_bundle()
        policy = parse(policy_bytes)
        return policy_bytes, canonical_state(policy), MODE_NORMAL
    if vector_id == "versioned-safe":
        policy_bytes = versioned_bundle()
        policy = parse(policy_bytes)
        state = _base_state(
            policy,
            generation=policy.state_generation_floor,
            active_slot=1,
            pending_slot=2,
            known_good_mask=0b01,
            attempts=(policy.max_attempts, policy.max_attempts),
            flags=STATE_SAFE_REQUESTED,
        )
        return policy_bytes, state, MODE_NORMAL
    _fail("prec_fixture")


def make_golden_vectors() -> dict[str, Any]:
    vectors = []
    for index, vector_id in enumerate(("minimal-known-good", "canonical-trial", "versioned-safe"), start=1):
        policy_bytes, state, requested = build_fixture(vector_id)
        policy = parse(policy_bytes)
        state_bytes = encode_state(state)
        decision = select_boot(policy, state, requested, boot_nonce=0xA000 + index)
        vectors.append(
            {
                "id": vector_id,
                "purpose": {
                    "minimal-known-good": "Smallest accepted attempt budget with a successful known-good selection.",
                    "canonical-trial": "Canonical pending-slot trial decremented before handoff.",
                    "versioned-safe": "Version-floor policy whose authenticated safe request overrides normal selection.",
                }[vector_id],
                "policy_byte_count": len(policy_bytes),
                "policy_sha256": sha256_bytes(policy_bytes),
                "policy_summary": summary(policy),
                "policy_hex": policy_bytes.hex().upper(),
                "state_byte_count": len(state_bytes),
                "state_sha256": sha256_bytes(state_bytes),
                "state_summary": state_summary(state),
                "state_hex": state_bytes.hex().upper(),
                "requested_mode": requested,
                "boot_nonce": 0xA000 + index,
                "decision_summary": decision_summary(decision),
                "next_state_hex": encode_state(decision.state).hex().upper(),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_recovery_golden_vectors",
        "contract_id": CONTRACT_ID,
        "status": "synthetic_non_promoting_golden_bytes",
        "production_ready": False,
        "vectors": vectors,
        "claim_boundary": [
            "Vectors contain synthetic unsigned policy and state bytes only.",
            "The state checksum detects accidental corruption but is not an authenticator.",
            "Transition summaries do not prove firmware persistence or kernel handoff.",
        ],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "policy_format_frozen": True,
        "mutable_state_format_frozen": True,
        "attempt_decrement_before_handoff_modeled": True,
        "known_good_fallback_modeled": True,
        "safe_loop_bounded": True,
        "destructive_authority_requires_physical_presence": True,
        "development_activation_denied": True,
        "parsing_confers_authority": False,
        "state_checksum_is_authentication": False,
        "uefi_variable_io_implemented": False,
        "pooleboot_enforces_prec1": False,
        "poolekernel_executes_recovery": False,
        "recovery_authority_granted": False,
        "physical_disk_write_performed": False,
        "production_ready": False,
    }


def expected_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_recovery_contract",
        "contract_id": CONTRACT_ID,
        "status": "candidate_pre_abi_non_promoting",
        "production_ready": False,
        "encoding": {
            "byte_order": "little_endian",
            "policy_bytes": TOTAL_BYTES,
            "header_bytes": HEADER_BYTES,
            "state_bytes": STATE_BYTES,
            "record_alignment": RECORD_ALIGNMENT,
            "body_digest": "SHA-256",
            "state_checksum": "truncated_SHA-256_first_16_bytes_not_authentication",
        },
        "policy_tables": {
            "slots": {"count": SLOT_COUNT, "record_bytes": SLOT_BYTES, "offset": SLOT_OFFSET},
            "failures": {"count": FAILURE_COUNT, "record_bytes": FAILURE_BYTES, "offset": FAILURE_OFFSET},
            "authorities": {"count": AUTHORITY_COUNT, "record_bytes": AUTHORITY_BYTES, "offset": AUTHORITY_OFFSET},
        },
        "slot_policy": {
            "slot_ids": [1, 2],
            "attempts_decremented_before_handoff": True,
            "candidate_never_overwrites_known_good": True,
            "success_requires_authenticated_matching_receipt": True,
            "fallback_requires_eligible_known_good_at_or_above_floor": True,
        },
        "state_policy": {
            "external_authentication_required": True,
            "monotonic_generation_required": True,
            "state_write_failure_action": "recovery",
            "uefi_variable_transport_frozen": False,
            "file_fallback_may_never_carry_security_state": True,
        },
        "failure_policy": {
            "ordered_failure_ids": list(FAILURE_NAMES.values()),
            "actions": list(ACTION_NAMES.values()),
            "evidence_preserved": True,
            "safe_attempts_per_slot": 1,
        },
        "authority_policy": {
            "ordered_authorities": list(AUTHORITY_NAMES.values()),
            "declarative_only": True,
            "ambient_firmware_raw_disk_network_prohibited": True,
            "repair_and_reinstall_require": [
                "physical_presence",
                "operator_authentication",
                "verified_backup",
                "verified_signature",
            ],
        },
        "activation_preconditions": [
            "outer role, version, payload digest, and file digest match",
            "outer, inner, and manifest signatures verify",
            "state authentication and monotonic generation verify",
            "version floor is durably persisted",
            "manifest and recovery components verify",
            "PBP1 and PooleKernel ABI versions match",
            "offline path is available with PDC disabled",
            "recovery is independent of PooleGlyph",
            "serial or GOP/software display path is available",
            "transaction capacity and evidence preservation are ready",
            "rollback is available and authenticated state is writable",
        ],
        "research_basis": [
            "https://uefi.org/specs/UEFI/2.11/03_Boot_Manager.html",
            "https://source.android.com/docs/core/ota/ab",
            "https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/android16-qpr2-release/boot/1.0/IBootControl.hal",
            "https://theupdateframework.github.io/specification/v1.0.26/",
            "https://www.chromium.org/chromium-os/chromiumos-design-docs/filesystem-autoupdate/",
            "https://www.chromium.org/chromium-os/developer-library/reference/device/disk-format/",
        ],
        "production_claims": expected_claims(),
        "claim_boundary": [
            "PREC1 is not owner-ratified or a stable ABI.",
            "Policy and state parsers run on the host; PooleBoot and PooleKernel do not enforce PREC1.",
            "The 16-byte state checksum is corruption detection, not authentication or anti-rollback storage.",
            "Authority records are requirements and never capability grants.",
            "No UEFI variable, firmware setting, driver, or physical disk is modified.",
            "No recovery component is loaded or executed.",
            "No key is generated or used and no artifact is signed.",
            "Synthetic qualification cannot authorize production promotion.",
            "Recovery UI and installer workflows remain unimplemented.",
        ],
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(contract, read_json(root / CONTRACT_SCHEMA_RELATIVE))
    if contract != expected_contract():
        errors.append("contract does not equal the canonical PREC1 contract")
    return errors


def golden_errors(golden: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(golden, read_json(root / GOLDEN_SCHEMA_RELATIVE))
    if golden != make_golden_vectors():
        errors.append("golden vectors do not equal canonical PREC1 vectors")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_json(readiness, read_json(root / READINESS_SCHEMA_RELATIVE))
    bindings = readiness.get("bindings", {}).get("implementation_inputs", [])
    expected = [file_binding(root / relative, root) for relative in IMPLEMENTATION_INPUTS]
    if bindings != expected:
        errors.append("readiness input bindings are stale")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary is stale")
    if readiness.get("production_ready") is not False or readiness.get("production_promotion_allowed") is not False:
        errors.append("readiness overclaims production status")
    return errors
