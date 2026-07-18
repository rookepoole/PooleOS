"""Independent PPOL1 policy-bundle codec and qualification oracle.

PPOL1 v1 is a deterministic, qualification-only policy model. It can only
attenuate authority already declared by PINIT1 and issued by a future kernel.
Parsing, cross-binding, or producing a dry-run decision never grants authority.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

from runtime import native_firmware as pfwm1
from runtime import native_initial_system as pinit1
from runtime import native_microcode as pmcu1
from runtime import native_recovery as prec1
from runtime import native_symbols as psym1
from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID: Final = "PPOL1"
MAGIC: Final = b"PPOL1\0\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 512
MODE_RECORD_BYTES: Final = 128
CAPABILITY_RECORD_BYTES: Final = 64
MAX_BUNDLE_BYTES: Final = 64 * 1024
MAX_CAPABILITY_RULES: Final = 256
MODE_COUNT: Final = 6
OUTER_ROLE_POLICY_BUNDLE: Final = 7
PROFILE_SYNTHETIC_QUALIFICATION: Final = 1

MODE_NORMAL: Final = 1
MODE_SAFE: Final = 2
MODE_PREVIOUS: Final = 3
MODE_RECOVERY: Final = 4
MODE_DIAGNOSTIC: Final = 5
MODE_FIRMWARE: Final = 6
MODES: Final = (
    MODE_NORMAL,
    MODE_SAFE,
    MODE_PREVIOUS,
    MODE_RECOVERY,
    MODE_DIAGNOSTIC,
    MODE_FIRMWARE,
)
MODE_NAMES: Final = {
    MODE_NORMAL: "normal",
    MODE_SAFE: "safe",
    MODE_PREVIOUS: "previous",
    MODE_RECOVERY: "recovery",
    MODE_DIAGNOSTIC: "diagnostic",
    MODE_FIRMWARE: "firmware",
}
ALL_MODE_MASK: Final = (1 << MODE_COUNT) - 1
PINIT_MODE_MASK: Final = (
    (1 << (MODE_NORMAL - 1))
    | (1 << (MODE_SAFE - 1))
    | (1 << (MODE_PREVIOUS - 1))
    | (1 << (MODE_DIAGNOSTIC - 1))
)

FLAG_TARGET_PROFILE_BOUND: Final = 1 << 0
FLAG_ARTIFACT_SET_BOUND: Final = 1 << 1
FLAG_EXACT_MODES: Final = 1 << 2
FLAG_DEFAULT_DENY: Final = 1 << 3
FLAG_ATTENUATION_ONLY: Final = 1 << 4
FLAG_NO_WILDCARDS: Final = 1 << 5
FLAG_CAPABILITY_ROUTE_COMPLETE: Final = 1 << 6
FLAG_PARENT_MONOTONIC: Final = 1 << 7
FLAG_SAFE_FLOOR: Final = 1 << 8
FLAG_RECOVERY_FLOOR: Final = 1 << 9
FLAG_FIRMWARE_PHYSICAL_PRESENCE: Final = 1 << 10
FLAG_FIRMWARE_SEPARATE_AUTHORITY: Final = 1 << 11
FLAG_REVOCATION_AUTHENTICATED: Final = 1 << 12
FLAG_ROLLBACK_AUTHENTICATED: Final = 1 << 13
FLAG_RECEIPT_REQUIRED: Final = 1 << 14
FLAG_DURABLE_AUDIT: Final = 1 << 15
FLAG_ZERO_TRUST: Final = 1 << 16
FLAG_MODE_TRANSITION_AUTHORIZED: Final = 1 << 17
FLAG_DENY_UNKNOWN: Final = 1 << 18
FLAG_NO_AUTHORITY_FROM_PARSE: Final = 1 << 19
FLAG_QUALIFICATION_ONLY: Final = 1 << 20
FLAG_POOLEGLYPH_NON_AUTHORITATIVE: Final = 1 << 21
REQUIRED_FLAGS: Final = (1 << 22) - 1

MODE_FLAG_DEFAULT_DENY: Final = 1 << 0
MODE_FLAG_AUDIT_REQUIRED: Final = 1 << 1
MODE_FLAG_RECEIPT_REQUIRED: Final = 1 << 2
MODE_FLAG_QUALIFICATION_ONLY: Final = 1 << 3
MODE_FLAG_SAFE_FLOOR: Final = 1 << 4
MODE_FLAG_RECOVERY_FLOOR: Final = 1 << 5
MODE_FLAG_DISABLE_PDC: Final = 1 << 6
MODE_FLAG_RECOVERY_INDEPENDENT: Final = 1 << 7
MODE_FLAG_PHYSICAL_PRESENCE: Final = 1 << 8
MODE_FLAG_SEPARATE_AUTHORITY: Final = 1 << 9
MODE_BASE_FLAGS: Final = (
    MODE_FLAG_DEFAULT_DENY
    | MODE_FLAG_AUDIT_REQUIRED
    | MODE_FLAG_RECEIPT_REQUIRED
    | MODE_FLAG_QUALIFICATION_ONLY
)
MODE_KNOWN_FLAGS: Final = (1 << 10) - 1

EFFECT_AUDIT: Final = 1 << 0
EFFECT_READ_STATE: Final = 1 << 1
EFFECT_WRITE_VOLATILE: Final = 1 << 2
EFFECT_WRITE_PERSISTENT: Final = 1 << 3
EFFECT_EXECUTE: Final = 1 << 4
EFFECT_IPC: Final = 1 << 5
EFFECT_NETWORK: Final = 1 << 6
EFFECT_DEVICE_IO: Final = 1 << 7
EFFECT_DMA: Final = 1 << 8
EFFECT_DEBUG: Final = 1 << 9
EFFECT_PDC_COMPUTE: Final = 1 << 10
EFFECT_PDC_ACTUATE: Final = 1 << 11
EFFECT_UPDATE: Final = 1 << 12
EFFECT_FIRMWARE: Final = 1 << 13
EFFECT_SECRET: Final = 1 << 14
EFFECT_POWER: Final = 1 << 15
KNOWN_EFFECTS: Final = (1 << 16) - 1
CAPABILITY_EFFECT_CEILING: Final = (
    EFFECT_AUDIT
    | EFFECT_READ_STATE
    | EFFECT_WRITE_VOLATILE
    | EFFECT_EXECUTE
    | EFFECT_IPC
)

EVIDENCE_OUTER_SIGNATURE: Final = 1 << 0
EVIDENCE_POLICY_SIGNATURE: Final = 1 << 1
EVIDENCE_MANIFEST_SIGNATURE: Final = 1 << 2
EVIDENCE_ARTIFACT_SIGNATURES: Final = 1 << 3
EVIDENCE_TARGET_PROFILE: Final = 1 << 4
EVIDENCE_REVOCATION: Final = 1 << 5
EVIDENCE_ROLLBACK: Final = 1 << 6
EVIDENCE_MODE_AUTHORITY: Final = 1 << 7
EVIDENCE_CAPABILITY_ALLOCATOR: Final = 1 << 8
EVIDENCE_RESOURCE_BROKER: Final = 1 << 9
EVIDENCE_AUDIT_SINK: Final = 1 << 10
EVIDENCE_RECEIPT_STORE: Final = 1 << 11
EVIDENCE_PHYSICAL_PRESENCE: Final = 1 << 12
EVIDENCE_SEPARATE_AUTHORITY: Final = 1 << 13
EVIDENCE_PINIT_CROSS_BINDING: Final = 1 << 14
EVIDENCE_ALL_INNER_CONTRACTS: Final = 1 << 15
EVIDENCE_PBP: Final = 1 << 16
EVIDENCE_KERNEL_ABI: Final = 1 << 17
KNOWN_EVIDENCE: Final = (1 << 18) - 1
BASE_EVIDENCE: Final = KNOWN_EVIDENCE & ~(
    EVIDENCE_PHYSICAL_PRESENCE | EVIDENCE_SEPARATE_AUTHORITY
)

ARTIFACT_ROLE_MASK: Final = sum(1 << role for role in range(2, 7))
KNOWN_RIGHTS: Final = (
    pinit1.RIGHT_READ
    | pinit1.RIGHT_WRITE
    | pinit1.RIGHT_MAP_OR_BIND
    | pinit1.RIGHT_MANAGE_OR_GRANT
    | pinit1.RIGHT_EXECUTE
)
KNOWN_CAPABILITY_FLAGS: Final = pinit1.CAP_KNOWN_FLAGS
REQUIRED_CAPABILITY_FLAGS: Final = pinit1.CAP_REVOCABLE | pinit1.CAP_LIFECYCLE_BOUND

AUDIT_DECISION: Final = 1 << 0
AUDIT_DENIAL: Final = 1 << 1
AUDIT_MODE_TRANSITION: Final = 1 << 2
AUDIT_REVOCATION: Final = 1 << 3
AUDIT_ROLLBACK: Final = 1 << 4
AUDIT_RECEIPT: Final = 1 << 5
KNOWN_AUDIT_EVENTS: Final = (1 << 6) - 1

SAFE_EFFECT_FLOOR: Final = (
    EFFECT_AUDIT
    | EFFECT_READ_STATE
    | EFFECT_WRITE_VOLATILE
    | EFFECT_EXECUTE
    | EFFECT_IPC
    | EFFECT_DEVICE_IO
)
RECOVERY_EFFECT_FLOOR: Final = (
    EFFECT_AUDIT
    | EFFECT_READ_STATE
    | EFFECT_WRITE_VOLATILE
    | EFFECT_WRITE_PERSISTENT
    | EFFECT_EXECUTE
    | EFFECT_IPC
    | EFFECT_DEVICE_IO
    | EFFECT_POWER
)

CONTRACT_RELATIVE: Final = Path("specs/native-policy-contract.json")
CONTRACT_SCHEMA_RELATIVE: Final = Path("specs/native-policy-contract.schema.json")
GOLDEN_RELATIVE: Final = Path("specs/native-policy-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE: Final = Path("specs/native-policy-golden-vectors.schema.json")
READINESS_RELATIVE: Final = Path("runs/native_policy_readiness.json")
READINESS_SCHEMA_RELATIVE: Final = Path("specs/native-policy-readiness.schema.json")

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/policy/Cargo.toml",
    "native/policy/src/lib.rs",
    "native/policy/src/bin/ppol1_probe.rs",
    "runtime/native_policy.py",
    "runtime/native_boot_artifact.py",
    "tools/generate_native_policy_vectors.py",
    "tools/qualify_native_policy.py",
    "tests/test_native_policy.py",
    "docs/native-policy-bundle.md",
)

HEADER_FLAG_NAMES: Final = (
    "target_profile_bound",
    "artifact_set_bound",
    "exact_modes",
    "default_deny",
    "attenuation_only",
    "no_wildcards",
    "capability_route_complete",
    "parent_monotonic",
    "safe_floor",
    "recovery_floor",
    "firmware_physical_presence",
    "firmware_separate_authority",
    "revocation_authenticated",
    "rollback_authenticated",
    "receipt_required",
    "durable_audit",
    "zero_trust",
    "mode_transition_authorized",
    "deny_unknown",
    "no_authority_from_parse",
    "qualification_only",
    "pooleglyph_non_authoritative",
)

ACTIVATION_ERROR_ORDER: Final = (
    "ppol_activation_outer_signature",
    "ppol_activation_outer_role",
    "ppol_activation_outer_version",
    "ppol_activation_outer_payload_digest",
    "ppol_activation_outer_file_digest",
    "ppol_activation_policy_signature",
    "ppol_activation_manifest_signature",
    "ppol_activation_artifact_signatures",
    "ppol_activation_target_profile",
    "ppol_activation_initial_system_digest",
    "ppol_activation_recovery_digest",
    "ppol_activation_symbols_digest",
    "ppol_activation_microcode_digest",
    "ppol_activation_firmware_digest",
    "ppol_activation_trust_policy",
    "ppol_activation_revocation_state",
    "ppol_activation_rollback_state",
    "ppol_activation_audit_schema",
    "ppol_activation_inner_contracts",
    "ppol_activation_initial_system_cross_binding",
    "ppol_activation_kernel_abi",
    "ppol_activation_pbp",
    "ppol_activation_mode",
    "ppol_activation_mode_authority",
    "ppol_activation_transition_authority",
    "ppol_activation_capability_allocator",
    "ppol_activation_resource_broker",
    "ppol_activation_audit_sink",
    "ppol_activation_receipt_store",
    "ppol_activation_physical_presence",
    "ppol_activation_separate_authority",
    "ppol_activation_capability",
    "ppol_activation_capability_mode",
    "ppol_activation_capability_revoked",
    "ppol_activation_generation",
    "ppol_activation_issued_rights",
    "ppol_activation_requested_rights",
    "ppol_activation_requested_effects",
    "ppol_activation_not_qualification_only",
    "ppol_activation_live_execution_requested",
    "ppol_activation_persistent_write_requested",
    "ppol_activation_firmware_call_requested",
    "ppol_activation_driver_load_requested",
    "ppol_activation_physical_media_write_requested",
    "ppol_activation_state_mutation_requested",
)

RECEIPT_ERROR_ORDER: Final = (
    "ppol_receipt_not_qualification_only",
    "ppol_receipt_policy_digest",
    "ppol_receipt_mode",
    "ppol_receipt_capability",
    "ppol_receipt_rights",
    "ppol_receipt_effects",
    "ppol_receipt_generation",
    "ppol_receipt_revocation_epoch",
    "ppol_receipt_audit_sequence",
    "ppol_receipt_not_durable",
    "ppol_receipt_decision_id",
)

_POLICY_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,38}$")


class PolicyError(RuntimeError):
    """Raised when PPOL1 bytes or pure qualification evidence fail closed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class ModePolicy:
    mode: int
    flags: int
    allowed_capability_count: int
    allowed_effects: int
    required_evidence: int
    prohibited_effects: int
    max_memory_pages: int
    max_thread_slots: int
    max_endpoint_slots: int
    max_restarts: int
    max_pdc_units: int
    max_network_sessions: int
    allowed_capability_flags: int
    allowed_rights: int
    required_artifact_mask: int
    transition_mask: int
    audit_event_mask: int
    generation: int


@dataclasses.dataclass(frozen=True)
class CapabilityRule:
    capability_id: int
    parent_id: int
    holder_service_id: int
    resource_id: int
    declared_rights: int
    ceiling_rights: int
    declared_flags: int
    ceiling_flags: int
    revoke_group: int
    allowed_mode_mask: int
    effect_mask: int
    availability: int
    max_derivations: int
    resource_generation: int


@dataclasses.dataclass(frozen=True)
class Bundle:
    raw: bytes
    policy_version: int
    minimum_secure_version: int
    policy_id: str
    profile: int
    flags: int
    max_audit_receipts: int
    max_generation_advance: int
    default_effect_ceiling: int
    target_profile_sha256: str
    initial_system_sha256: str
    recovery_sha256: str
    symbols_sha256: str
    microcode_sha256: str
    firmware_sha256: str
    trust_policy_sha256: str
    revocation_schema_sha256: str
    rollback_schema_sha256: str
    audit_schema_sha256: str
    body_sha256: str
    modes: tuple[ModePolicy, ...]
    capability_rules: tuple[CapabilityRule, ...]


@dataclasses.dataclass(frozen=True)
class ActivationContext:
    outer_role: int
    outer_version: int
    outer_payload_sha256: str
    outer_file_sha256: str
    expected_outer_file_sha256: str
    selected_mode: int
    previous_mode: int
    capability_id: int
    issued_rights: int
    requested_rights: int
    requested_effects: int
    issued_generation: int
    current_generation: int
    outer_signature_verified: bool
    policy_signature_verified: bool
    manifest_signature_verified: bool
    artifact_signatures_verified: bool
    target_profile_verified: bool
    initial_system_digest_verified: bool
    recovery_digest_verified: bool
    symbols_digest_verified: bool
    microcode_digest_verified: bool
    firmware_digest_verified: bool
    trust_policy_authenticated: bool
    revocation_state_authenticated: bool
    rollback_state_authenticated: bool
    audit_schema_verified: bool
    inner_contracts_verified: bool
    initial_system_cross_bound: bool
    kernel_abi_verified: bool
    pbp_verified: bool
    mode_authorized: bool
    transition_authorized: bool
    capability_allocator_ready: bool
    resource_broker_ready: bool
    audit_sink_ready: bool
    receipt_store_ready: bool
    physical_presence_verified: bool
    separate_authority_verified: bool
    capability_revoked: bool
    qualification_only: bool
    live_execution_requested: bool
    persistent_write_requested: bool
    firmware_call_requested: bool
    driver_load_requested: bool
    physical_media_write_requested: bool
    state_mutation_requested: bool


@dataclasses.dataclass(frozen=True)
class DryRunDecision:
    policy_sha256: str
    mode: int
    capability_id: int
    effective_rights: int
    effective_effects: int
    mode_generation: int
    capability_generation: int
    allowed_capability_count: int
    audit_receipt_required: bool
    qualification_only: bool


@dataclasses.dataclass(frozen=True)
class DecisionReceipt:
    policy_sha256: str
    mode: int
    capability_id: int
    effective_rights: int
    effective_effects: int
    mode_generation: int
    capability_generation: int
    revocation_epoch: int
    audit_sequence: int
    durable: bool
    qualification_only: bool
    decision_id: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _digest(label: str) -> str:
    return sha256_bytes(label.encode("ascii"))


def _digest_bytes(value: str) -> bytes:
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise PolicyError("ppol_digest") from error
    if len(result) != 32 or not any(result):
        raise PolicyError("ppol_digest")
    return result


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _nonzero_digest(data: bytes, offset: int, code: str) -> str:
    value = data[offset : offset + 32]
    if len(value) != 32 or not any(value):
        raise PolicyError(code)
    return value.hex().upper()


def _mode_bit(mode: int) -> int:
    if mode not in MODES:
        return 0
    return 1 << (mode - 1)


def _policy_id(data: bytes) -> str:
    field = data[448:488]
    nul = field.find(b"\0")
    if nul <= 0 or any(field[nul:]):
        raise PolicyError("ppol_policy_id")
    try:
        value = field[:nul].decode("ascii")
    except UnicodeDecodeError as error:
        raise PolicyError("ppol_policy_id") from error
    if not _POLICY_ID.fullmatch(value):
        raise PolicyError("ppol_policy_id")
    return value


def _parse_mode(record: bytes, expected_mode: int, capability_count: int) -> ModePolicy:
    if len(record) != MODE_RECORD_BYTES:
        raise PolicyError("ppol_truncated")
    mode, flags, allowed_count, reserved = struct.unpack_from("<HHHH", record, 0)
    if mode != expected_mode:
        raise PolicyError("ppol_mode_order")
    if flags & ~MODE_KNOWN_FLAGS or flags & MODE_BASE_FLAGS != MODE_BASE_FLAGS:
        raise PolicyError("ppol_mode_flags")
    if reserved != 0 or any(record[88:]):
        raise PolicyError("ppol_mode_reserved")
    if allowed_count > capability_count:
        raise PolicyError("ppol_mode_capability_count")
    allowed_effects = _u64(record, 8)
    required_evidence = _u64(record, 16)
    prohibited_effects = _u64(record, 24)
    if allowed_effects == 0 or allowed_effects & ~KNOWN_EFFECTS:
        raise PolicyError("ppol_mode_effects")
    if prohibited_effects != KNOWN_EFFECTS ^ allowed_effects:
        raise PolicyError("ppol_mode_prohibited_effects")
    firmware_evidence = EVIDENCE_PHYSICAL_PRESENCE | EVIDENCE_SEPARATE_AUTHORITY
    expected_evidence = BASE_EVIDENCE | (firmware_evidence if mode == MODE_FIRMWARE else 0)
    if required_evidence != expected_evidence:
        raise PolicyError("ppol_mode_evidence")
    ceilings = struct.unpack_from("<IIIIII", record, 32)
    if (
        ceilings[0] > pinit1.RESOURCE_MAXIMUMS[pinit1.RESOURCE_MEMORY_PAGES]
        or ceilings[1] > pinit1.RESOURCE_MAXIMUMS[pinit1.RESOURCE_THREAD_SLOTS]
        or ceilings[2] > pinit1.RESOURCE_MAXIMUMS[pinit1.RESOURCE_ENDPOINT_SLOTS]
        or ceilings[3] > 1024
        or ceilings[4] > 1024
        or ceilings[5] > 4096
    ):
        raise PolicyError("ppol_mode_resource_ceiling")
    cap_flags, rights, artifacts, transitions = struct.unpack_from("<IIII", record, 56)
    if cap_flags & ~KNOWN_CAPABILITY_FLAGS:
        raise PolicyError("ppol_mode_capability_flags")
    if rights & ~KNOWN_RIGHTS or (allowed_count == 0) != (rights == 0):
        raise PolicyError("ppol_mode_rights")
    if artifacts != ARTIFACT_ROLE_MASK:
        raise PolicyError("ppol_mode_artifacts")
    if transitions == 0 or transitions & ~ALL_MODE_MASK:
        raise PolicyError("ppol_mode_transitions")
    audit_mask = _u64(record, 72)
    generation = _u64(record, 80)
    if audit_mask != KNOWN_AUDIT_EVENTS or generation == 0:
        raise PolicyError("ppol_mode_audit")
    if mode == MODE_SAFE:
        needed = MODE_FLAG_SAFE_FLOOR | MODE_FLAG_DISABLE_PDC
        if flags & needed != needed or allowed_effects & ~SAFE_EFFECT_FLOOR:
            raise PolicyError("ppol_safe_floor")
    if mode == MODE_RECOVERY:
        needed = MODE_FLAG_RECOVERY_FLOOR | MODE_FLAG_DISABLE_PDC | MODE_FLAG_RECOVERY_INDEPENDENT
        if (
            flags & needed != needed
            or allowed_effects & ~RECOVERY_EFFECT_FLOOR
            or allowed_count != 0
            or rights != 0
        ):
            raise PolicyError("ppol_recovery_floor")
    if mode == MODE_FIRMWARE:
        needed = MODE_FLAG_PHYSICAL_PRESENCE | MODE_FLAG_SEPARATE_AUTHORITY | MODE_FLAG_DISABLE_PDC
        if flags & needed != needed or allowed_count != 0 or rights != 0:
            raise PolicyError("ppol_firmware_boundary")
    if mode != MODE_FIRMWARE and flags & (MODE_FLAG_PHYSICAL_PRESENCE | MODE_FLAG_SEPARATE_AUTHORITY):
        raise PolicyError("ppol_mode_flags")
    return ModePolicy(mode, flags, allowed_count, allowed_effects, required_evidence, prohibited_effects, *ceilings, cap_flags, rights, artifacts, transitions, audit_mask, generation)


def _parse_rule(record: bytes, expected_id: int, prior: Sequence[CapabilityRule]) -> CapabilityRule:
    if len(record) != CAPABILITY_RECORD_BYTES:
        raise PolicyError("ppol_truncated")
    capability_id, parent_id, holder, resource = struct.unpack_from("<IIII", record, 0)
    if capability_id != expected_id:
        raise PolicyError("ppol_capability_order")
    if parent_id >= capability_id:
        raise PolicyError("ppol_capability_parent")
    if holder == 0 or resource == 0:
        raise PolicyError("ppol_capability_route")
    declared_rights, ceiling_rights = struct.unpack_from("<QQ", record, 16)
    if declared_rights == 0 or declared_rights & ~KNOWN_RIGHTS:
        raise PolicyError("ppol_capability_declared_rights")
    if ceiling_rights == 0 or ceiling_rights & ~declared_rights:
        raise PolicyError("ppol_capability_ceiling_rights")
    declared_flags, ceiling_flags, revoke_group, mode_mask = struct.unpack_from("<IIII", record, 32)
    if declared_flags & ~KNOWN_CAPABILITY_FLAGS or declared_flags & REQUIRED_CAPABILITY_FLAGS != REQUIRED_CAPABILITY_FLAGS:
        raise PolicyError("ppol_capability_declared_flags")
    if (
        ceiling_flags & ~declared_flags
        or ceiling_flags & REQUIRED_CAPABILITY_FLAGS != REQUIRED_CAPABILITY_FLAGS
    ):
        raise PolicyError("ppol_capability_ceiling_flags")
    if revoke_group == 0:
        raise PolicyError("ppol_capability_revoke_group")
    if mode_mask == 0 or mode_mask & ~ALL_MODE_MASK or mode_mask & ~PINIT_MODE_MASK:
        raise PolicyError("ppol_capability_modes")
    effect_mask = _u64(record, 48)
    availability, max_derivations = struct.unpack_from("<HH", record, 56)
    generation = _u32(record, 60)
    if effect_mask == 0 or effect_mask & ~CAPABILITY_EFFECT_CEILING:
        raise PolicyError("ppol_capability_effects")
    if availability not in (pinit1.AVAILABILITY_REQUIRED, pinit1.AVAILABILITY_OPTIONAL):
        raise PolicyError("ppol_capability_availability")
    if generation == 0:
        raise PolicyError("ppol_capability_generation")
    rule = CapabilityRule(capability_id, parent_id, holder, resource, declared_rights, ceiling_rights, declared_flags, ceiling_flags, revoke_group, mode_mask, effect_mask, availability, max_derivations, generation)
    if parent_id:
        parent = prior[parent_id - 1]
        if (
            ceiling_rights & ~parent.ceiling_rights
            or ceiling_flags & ~parent.ceiling_flags
            or mode_mask & ~parent.allowed_mode_mask
            or effect_mask & ~parent.effect_mask
        ):
            raise PolicyError("ppol_capability_parent_attenuation")
    return rule


def parse(data: bytes) -> Bundle:
    if len(data) < HEADER_BYTES:
        raise PolicyError("ppol_truncated")
    if len(data) > MAX_BUNDLE_BYTES:
        raise PolicyError("ppol_oversized")
    if data[:8] != MAGIC:
        raise PolicyError("ppol_magic")
    if (_u16(data, 8), _u16(data, 10)) != (MAJOR_VERSION, MINOR_VERSION):
        raise PolicyError("ppol_version")
    if (
        _u16(data, 12) != HEADER_BYTES
        or _u16(data, 14) != MODE_RECORD_BYTES
        or _u16(data, 16) != CAPABILITY_RECORD_BYTES
    ):
        raise PolicyError("ppol_record_size")
    profile = _u16(data, 18)
    if profile != PROFILE_SYNTHETIC_QUALIFICATION:
        raise PolicyError("ppol_profile")
    flags = _u32(data, 20)
    if flags != REQUIRED_FLAGS:
        raise PolicyError("ppol_flags")
    policy_version, minimum_secure_version = struct.unpack_from("<QQ", data, 24)
    if policy_version == 0 or minimum_secure_version == 0 or policy_version < minimum_secure_version:
        raise PolicyError("ppol_version_floor")
    mode_count, capability_count = struct.unpack_from("<HH", data, 40)
    if mode_count != MODE_COUNT or not 1 <= capability_count <= MAX_CAPABILITY_RULES:
        raise PolicyError("ppol_counts")
    if _u32(data, 44) != ALL_MODE_MASK:
        raise PolicyError("ppol_required_modes")
    mode_offset, capability_offset, total_bytes = struct.unpack_from("<QQQ", data, 48)
    expected_capability_offset = HEADER_BYTES + MODE_COUNT * MODE_RECORD_BYTES
    expected_total = expected_capability_offset + capability_count * CAPABILITY_RECORD_BYTES
    if mode_offset != HEADER_BYTES or capability_offset != expected_capability_offset:
        raise PolicyError("ppol_table_layout")
    if len(data) < total_bytes:
        raise PolicyError("ppol_truncated")
    if total_bytes != expected_total:
        raise PolicyError("ppol_table_layout")
    if len(data) > total_bytes:
        raise PolicyError("ppol_trailing_bytes")
    max_audit_receipts, max_generation_advance = struct.unpack_from("<II", data, 72)
    default_effect_ceiling = _u64(data, 80)
    if not 1 <= max_audit_receipts <= 1_000_000 or max_generation_advance != 1:
        raise PolicyError("ppol_limits")
    if default_effect_ceiling != KNOWN_EFFECTS or _u64(data, 88) != 0:
        raise PolicyError("ppol_default_ceiling")
    digests = tuple(_nonzero_digest(data, offset, "ppol_digest") for offset in range(96, 416, 32))
    body_sha256 = _nonzero_digest(data, 416, "ppol_body_digest")
    if sha256_bytes(data[HEADER_BYTES:]) != body_sha256:
        raise PolicyError("ppol_body_digest")
    policy_id = _policy_id(data)
    if any(data[488:HEADER_BYTES]):
        raise PolicyError("ppol_reserved")
    modes = tuple(
        _parse_mode(
            data[HEADER_BYTES + index * MODE_RECORD_BYTES : HEADER_BYTES + (index + 1) * MODE_RECORD_BYTES],
            MODES[index],
            capability_count,
        )
        for index in range(MODE_COUNT)
    )
    rules: list[CapabilityRule] = []
    for index in range(capability_count):
        offset = expected_capability_offset + index * CAPABILITY_RECORD_BYTES
        rules.append(_parse_rule(data[offset : offset + CAPABILITY_RECORD_BYTES], index + 1, rules))
    for mode in modes:
        actual = sum(bool(rule.allowed_mode_mask & _mode_bit(mode.mode)) for rule in rules)
        if actual != mode.allowed_capability_count:
            raise PolicyError("ppol_mode_capability_count")
    return Bundle(data, policy_version, minimum_secure_version, policy_id, profile, flags, max_audit_receipts, max_generation_advance, default_effect_ceiling, *digests, body_sha256, modes, tuple(rules))


def _pack_mode(item: ModePolicy) -> bytes:
    record = bytearray(MODE_RECORD_BYTES)
    struct.pack_into("<HHHHQQQIIIIIIIIIIQQ", record, 0, item.mode, item.flags, item.allowed_capability_count, 0, item.allowed_effects, item.required_evidence, item.prohibited_effects, item.max_memory_pages, item.max_thread_slots, item.max_endpoint_slots, item.max_restarts, item.max_pdc_units, item.max_network_sessions, item.allowed_capability_flags, item.allowed_rights, item.required_artifact_mask, item.transition_mask, item.audit_event_mask, item.generation)
    return bytes(record)


def _pack_rule(item: CapabilityRule) -> bytes:
    return struct.pack("<IIIIQQIIIIQHHI", item.capability_id, item.parent_id, item.holder_service_id, item.resource_id, item.declared_rights, item.ceiling_rights, item.declared_flags, item.ceiling_flags, item.revoke_group, item.allowed_mode_mask, item.effect_mask, item.availability, item.max_derivations, item.resource_generation)


def encode(
    *,
    policy_version: int,
    minimum_secure_version: int,
    policy_id: str,
    max_audit_receipts: int,
    max_generation_advance: int,
    target_profile_sha256: str,
    initial_system_sha256: str,
    recovery_sha256: str,
    symbols_sha256: str,
    microcode_sha256: str,
    firmware_sha256: str,
    trust_policy_sha256: str,
    revocation_schema_sha256: str,
    rollback_schema_sha256: str,
    audit_schema_sha256: str,
    modes: Sequence[ModePolicy],
    capability_rules: Sequence[CapabilityRule],
) -> bytes:
    try:
        policy_id_bytes = policy_id.encode("ascii")
    except UnicodeEncodeError as error:
        raise PolicyError("ppol_policy_id") from error
    if not _POLICY_ID.fullmatch(policy_id) or len(policy_id_bytes) > 39:
        raise PolicyError("ppol_policy_id")
    body = b"".join(_pack_mode(item) for item in modes) + b"".join(_pack_rule(item) for item in capability_rules)
    header = bytearray(HEADER_BYTES)
    header[:8] = MAGIC
    struct.pack_into("<HHHHHHIQQHHIQQQIIQQ", header, 8, MAJOR_VERSION, MINOR_VERSION, HEADER_BYTES, MODE_RECORD_BYTES, CAPABILITY_RECORD_BYTES, PROFILE_SYNTHETIC_QUALIFICATION, REQUIRED_FLAGS, policy_version, minimum_secure_version, len(modes), len(capability_rules), ALL_MODE_MASK, HEADER_BYTES, HEADER_BYTES + len(modes) * MODE_RECORD_BYTES, HEADER_BYTES + len(body), max_audit_receipts, max_generation_advance, KNOWN_EFFECTS, 0)
    digest_values = (target_profile_sha256, initial_system_sha256, recovery_sha256, symbols_sha256, microcode_sha256, firmware_sha256, trust_policy_sha256, revocation_schema_sha256, rollback_schema_sha256, audit_schema_sha256)
    for offset, value in zip(range(96, 416, 32), digest_values, strict=True):
        header[offset : offset + 32] = _digest_bytes(value)
    header[416:448] = hashlib.sha256(body).digest()
    header[448 : 448 + len(policy_id_bytes)] = policy_id_bytes
    header[448 + len(policy_id_bytes)] = 0
    result = bytes(header) + body
    parse(result)
    return result


def _mode_policy(mode: int, capability_count: int) -> ModePolicy:
    base = MODE_BASE_FLAGS
    all_caps = capability_count
    values = {
        MODE_NORMAL: (base, all_caps, EFFECT_AUDIT | EFFECT_READ_STATE | EFFECT_WRITE_VOLATILE | EFFECT_WRITE_PERSISTENT | EFFECT_EXECUTE | EFFECT_IPC | EFFECT_NETWORK | EFFECT_DEVICE_IO, 65536, 1024, 4096, 64, 0, 256, KNOWN_CAPABILITY_FLAGS, KNOWN_RIGHTS, ALL_MODE_MASK),
        MODE_SAFE: (base | MODE_FLAG_SAFE_FLOOR | MODE_FLAG_DISABLE_PDC, all_caps, SAFE_EFFECT_FLOOR, 8192, 128, 512, 8, 0, 0, REQUIRED_CAPABILITY_FLAGS, pinit1.RIGHT_READ | pinit1.RIGHT_WRITE | pinit1.RIGHT_MAP_OR_BIND, _mode_bit(MODE_SAFE) | _mode_bit(MODE_RECOVERY) | _mode_bit(MODE_NORMAL)),
        MODE_PREVIOUS: (base | MODE_FLAG_DISABLE_PDC, all_caps, EFFECT_AUDIT | EFFECT_READ_STATE | EFFECT_WRITE_VOLATILE | EFFECT_WRITE_PERSISTENT | EFFECT_EXECUTE | EFFECT_IPC | EFFECT_DEVICE_IO, 32768, 512, 2048, 32, 0, 0, KNOWN_CAPABILITY_FLAGS, pinit1.RIGHT_READ | pinit1.RIGHT_WRITE | pinit1.RIGHT_MAP_OR_BIND | pinit1.RIGHT_MANAGE_OR_GRANT, _mode_bit(MODE_PREVIOUS) | _mode_bit(MODE_SAFE) | _mode_bit(MODE_RECOVERY) | _mode_bit(MODE_NORMAL)),
        MODE_RECOVERY: (base | MODE_FLAG_RECOVERY_FLOOR | MODE_FLAG_DISABLE_PDC | MODE_FLAG_RECOVERY_INDEPENDENT, 0, RECOVERY_EFFECT_FLOOR, 4096, 64, 256, 4, 0, 0, 0, 0, _mode_bit(MODE_RECOVERY) | _mode_bit(MODE_SAFE) | _mode_bit(MODE_NORMAL)),
        MODE_DIAGNOSTIC: (base | MODE_FLAG_DISABLE_PDC, all_caps, EFFECT_AUDIT | EFFECT_READ_STATE | EFFECT_WRITE_VOLATILE | EFFECT_EXECUTE | EFFECT_IPC | EFFECT_DEVICE_IO | EFFECT_DEBUG, 16384, 256, 1024, 8, 0, 0, REQUIRED_CAPABILITY_FLAGS, pinit1.RIGHT_READ | pinit1.RIGHT_WRITE | pinit1.RIGHT_MAP_OR_BIND, _mode_bit(MODE_DIAGNOSTIC) | _mode_bit(MODE_SAFE) | _mode_bit(MODE_RECOVERY)),
        MODE_FIRMWARE: (base | MODE_FLAG_PHYSICAL_PRESENCE | MODE_FLAG_SEPARATE_AUTHORITY | MODE_FLAG_DISABLE_PDC, 0, EFFECT_AUDIT | EFFECT_READ_STATE | EFFECT_WRITE_VOLATILE | EFFECT_UPDATE | EFFECT_FIRMWARE | EFFECT_POWER, 2048, 32, 128, 1, 0, 0, 0, 0, _mode_bit(MODE_FIRMWARE) | _mode_bit(MODE_RECOVERY)),
    }[mode]
    flags, count, effects, memory, threads, endpoints, restarts, pdc, network, cap_flags, rights, transitions = values
    evidence = BASE_EVIDENCE | ((EVIDENCE_PHYSICAL_PRESENCE | EVIDENCE_SEPARATE_AUTHORITY) if mode == MODE_FIRMWARE else 0)
    return ModePolicy(mode, flags, count, effects, evidence, KNOWN_EFFECTS ^ effects, memory, threads, endpoints, restarts, pdc, network, cap_flags, rights, ARTIFACT_ROLE_MASK, transitions, KNOWN_AUDIT_EVENTS, 1)


def _effects_for_capability(capability: pinit1.Capability, resource: pinit1.Resource) -> int:
    effects = 0
    if resource.kind == pinit1.RESOURCE_LOG_SINK:
        effects |= EFFECT_AUDIT
    if capability.rights & pinit1.RIGHT_READ:
        effects |= EFFECT_READ_STATE
    if capability.rights & pinit1.RIGHT_WRITE and resource.kind != pinit1.RESOURCE_LOG_SINK:
        effects |= EFFECT_WRITE_VOLATILE
    if resource.kind == pinit1.RESOURCE_THREAD_SLOTS and capability.rights & pinit1.RIGHT_MAP_OR_BIND:
        effects |= EFFECT_EXECUTE
    if resource.kind == pinit1.RESOURCE_ENDPOINT_SLOTS and capability.rights & pinit1.RIGHT_MAP_OR_BIND:
        effects |= EFFECT_IPC
    return effects or EFFECT_AUDIT


def _rules_from_initial_system(bundle: pinit1.Bundle) -> tuple[CapabilityRule, ...]:
    resources = {item.resource_id: item for item in bundle.resources}
    return tuple(
        CapabilityRule(
            item.capability_id,
            item.parent_id,
            item.holder_service_id,
            item.resource_id,
            item.rights,
            item.rights,
            item.flags,
            item.flags,
            item.revoke_group,
            PINIT_MODE_MASK,
            _effects_for_capability(item, resources[item.resource_id]),
            item.availability,
            item.max_derivations,
            resources[item.resource_id].generation,
        )
        for item in bundle.capabilities
    )


def _file_sha256(relative: str) -> str:
    return sha256_bytes((ROOT / relative).read_bytes())


def canonical_bundle() -> bytes:
    initial = pinit1.parse(pinit1.canonical_bundle())
    rules = _rules_from_initial_system(initial)
    modes = tuple(_mode_policy(mode, len(rules) if mode in (MODE_NORMAL, MODE_SAFE, MODE_PREVIOUS, MODE_DIAGNOSTIC) else 0) for mode in MODES)
    return encode(
        policy_version=1,
        minimum_secure_version=1,
        policy_id="POOLEOS-POLICY-CYCLE113",
        max_audit_receipts=4096,
        max_generation_advance=1,
        target_profile_sha256=_file_sha256("specs/tier1-hardware-target.json"),
        initial_system_sha256=sha256_bytes(initial.raw),
        recovery_sha256=sha256_bytes(prec1.canonical_bundle()),
        symbols_sha256=sha256_bytes(psym1.canonical_bundle()),
        microcode_sha256=sha256_bytes(pmcu1.canonical_bundle()),
        firmware_sha256=sha256_bytes(pfwm1.canonical_bundle()),
        trust_policy_sha256=_file_sha256("specs/native-release-architecture-policy.json"),
        revocation_schema_sha256=_digest("PooleOS PPOL1 authenticated revocation schema v1"),
        rollback_schema_sha256=_digest("PooleOS PPOL1 authenticated rollback schema v1"),
        audit_schema_sha256=_digest("PooleOS PPOL1 durable decision audit schema v1"),
        modes=modes,
        capability_rules=rules,
    )


def minimal_bundle() -> bytes:
    rule = CapabilityRule(1, 0, 1, 1, pinit1.RIGHT_READ, pinit1.RIGHT_READ, REQUIRED_CAPABILITY_FLAGS, REQUIRED_CAPABILITY_FLAGS, 1, PINIT_MODE_MASK, EFFECT_READ_STATE, pinit1.AVAILABILITY_REQUIRED, 0, 1)
    return encode(
        policy_version=1,
        minimum_secure_version=1,
        policy_id="PPOL1-MINIMAL",
        max_audit_receipts=1,
        max_generation_advance=1,
        target_profile_sha256=_digest("minimal-target"),
        initial_system_sha256=_digest("minimal-pinit"),
        recovery_sha256=_digest("minimal-prec"),
        symbols_sha256=_digest("minimal-psym"),
        microcode_sha256=_digest("minimal-pmcu"),
        firmware_sha256=_digest("minimal-pfwm"),
        trust_policy_sha256=_digest("minimal-trust"),
        revocation_schema_sha256=_digest("minimal-revocation"),
        rollback_schema_sha256=_digest("minimal-rollback"),
        audit_schema_sha256=_digest("minimal-audit"),
        modes=tuple(_mode_policy(mode, 1 if mode in (MODE_NORMAL, MODE_SAFE, MODE_PREVIOUS, MODE_DIAGNOSTIC) else 0) for mode in MODES),
        capability_rules=(rule,),
    )


def boundary_bundle() -> bytes:
    rules: list[CapabilityRule] = []
    for capability_id in range(1, MAX_CAPABILITY_RULES + 1):
        rules.append(CapabilityRule(capability_id, 0, 1, capability_id, pinit1.RIGHT_READ, pinit1.RIGHT_READ, REQUIRED_CAPABILITY_FLAGS, REQUIRED_CAPABILITY_FLAGS, capability_id, PINIT_MODE_MASK, EFFECT_READ_STATE, pinit1.AVAILABILITY_REQUIRED, 0, 1))
    return encode(
        policy_version=2,
        minimum_secure_version=1,
        policy_id="PPOL1-BOUNDARY",
        max_audit_receipts=1_000_000,
        max_generation_advance=1,
        target_profile_sha256=_digest("boundary-target"),
        initial_system_sha256=_digest("boundary-pinit"),
        recovery_sha256=_digest("boundary-prec"),
        symbols_sha256=_digest("boundary-psym"),
        microcode_sha256=_digest("boundary-pmcu"),
        firmware_sha256=_digest("boundary-pfwm"),
        trust_policy_sha256=_digest("boundary-trust"),
        revocation_schema_sha256=_digest("boundary-revocation"),
        rollback_schema_sha256=_digest("boundary-rollback"),
        audit_schema_sha256=_digest("boundary-audit"),
        modes=tuple(_mode_policy(mode, len(rules) if mode in (MODE_NORMAL, MODE_SAFE, MODE_PREVIOUS, MODE_DIAGNOSTIC) else 0) for mode in MODES),
        capability_rules=tuple(rules),
    )


def initial_system_errors(bundle: Bundle, initial: pinit1.Bundle) -> list[str]:
    errors: list[str] = []
    if bundle.initial_system_sha256 != sha256_bytes(initial.raw):
        errors.append("ppol_pinit_digest")
    if len(bundle.capability_rules) != len(initial.capabilities):
        errors.append("ppol_pinit_capability_count")
        return errors
    resources = {item.resource_id: item for item in initial.resources}
    for rule, capability in zip(bundle.capability_rules, initial.capabilities, strict=True):
        resource = resources[capability.resource_id]
        expected = (
            capability.capability_id,
            capability.parent_id,
            capability.holder_service_id,
            capability.resource_id,
            capability.rights,
            capability.flags,
            capability.revoke_group,
            capability.availability,
            capability.max_derivations,
            resource.generation,
        )
        actual = (
            rule.capability_id,
            rule.parent_id,
            rule.holder_service_id,
            rule.resource_id,
            rule.declared_rights,
            rule.declared_flags,
            rule.revoke_group,
            rule.availability,
            rule.max_derivations,
            rule.resource_generation,
        )
        if actual != expected:
            errors.append("ppol_pinit_capability_route")
            break
        if rule.ceiling_rights & ~capability.rights or rule.ceiling_flags & ~capability.flags:
            errors.append("ppol_pinit_capability_amplification")
            break
        if rule.effect_mask != _effects_for_capability(capability, resource):
            errors.append("ppol_pinit_capability_effects")
            break
    return errors


def validate_initial_system(bundle: Bundle, initial: pinit1.Bundle) -> None:
    errors = initial_system_errors(bundle, initial)
    if errors:
        raise PolicyError(errors[0])


def _rule(bundle: Bundle, capability_id: int) -> CapabilityRule | None:
    if not 1 <= capability_id <= len(bundle.capability_rules):
        return None
    return bundle.capability_rules[capability_id - 1]


def _mode(bundle: Bundle, mode: int) -> ModePolicy | None:
    if mode not in MODES:
        return None
    return bundle.modes[mode - 1]


def development_activation_context(bundle: Bundle, *, outer_file_sha256: str | None = None) -> ActivationContext:
    qualified = synthetic_qualified_activation_context(bundle)
    return dataclasses.replace(
        qualified,
        outer_file_sha256=outer_file_sha256 or sha256_bytes(bundle.raw),
        expected_outer_file_sha256=outer_file_sha256 or sha256_bytes(bundle.raw),
        outer_signature_verified=False,
        policy_signature_verified=False,
        manifest_signature_verified=False,
        artifact_signatures_verified=False,
        target_profile_verified=False,
        trust_policy_authenticated=False,
        revocation_state_authenticated=False,
        rollback_state_authenticated=False,
        audit_schema_verified=False,
        inner_contracts_verified=False,
        initial_system_cross_bound=False,
        mode_authorized=False,
        transition_authorized=False,
        capability_allocator_ready=False,
        resource_broker_ready=False,
        audit_sink_ready=False,
        receipt_store_ready=False,
    )


def synthetic_qualified_activation_context(
    bundle: Bundle,
    *,
    mode: int = MODE_NORMAL,
    capability_id: int | None = None,
) -> ActivationContext:
    mode_policy = _mode(bundle, mode)
    if mode_policy is None:
        raise PolicyError("ppol_activation_mode")
    if capability_id is None:
        capability_id = 1 if mode_policy.allowed_capability_count else 0
    rule = _rule(bundle, capability_id) if capability_id else None
    rights = 0 if rule is None else rule.ceiling_rights & mode_policy.allowed_rights
    effects = EFFECT_AUDIT if rule is None else rule.effect_mask & mode_policy.allowed_effects
    file_sha = sha256_bytes(bundle.raw)
    generation = 0 if rule is None else rule.resource_generation
    return ActivationContext(
        outer_role=OUTER_ROLE_POLICY_BUNDLE,
        outer_version=bundle.policy_version,
        outer_payload_sha256=sha256_bytes(bundle.raw),
        outer_file_sha256=file_sha,
        expected_outer_file_sha256=file_sha,
        selected_mode=mode,
        previous_mode=mode,
        capability_id=capability_id,
        issued_rights=rights,
        requested_rights=rights,
        requested_effects=effects,
        issued_generation=generation,
        current_generation=generation,
        outer_signature_verified=True,
        policy_signature_verified=True,
        manifest_signature_verified=True,
        artifact_signatures_verified=True,
        target_profile_verified=True,
        initial_system_digest_verified=True,
        recovery_digest_verified=True,
        symbols_digest_verified=True,
        microcode_digest_verified=True,
        firmware_digest_verified=True,
        trust_policy_authenticated=True,
        revocation_state_authenticated=True,
        rollback_state_authenticated=True,
        audit_schema_verified=True,
        inner_contracts_verified=True,
        initial_system_cross_bound=True,
        kernel_abi_verified=True,
        pbp_verified=True,
        mode_authorized=True,
        transition_authorized=True,
        capability_allocator_ready=True,
        resource_broker_ready=True,
        audit_sink_ready=True,
        receipt_store_ready=True,
        physical_presence_verified=mode == MODE_FIRMWARE,
        separate_authority_verified=mode == MODE_FIRMWARE,
        capability_revoked=False,
        qualification_only=True,
        live_execution_requested=False,
        persistent_write_requested=False,
        firmware_call_requested=False,
        driver_load_requested=False,
        physical_media_write_requested=False,
        state_mutation_requested=False,
    )


def activation_errors(bundle: Bundle, context: ActivationContext) -> list[str]:
    errors: list[str] = []
    checks = (
        (context.outer_signature_verified, "ppol_activation_outer_signature"),
        (context.outer_role == OUTER_ROLE_POLICY_BUNDLE, "ppol_activation_outer_role"),
        (context.outer_version == bundle.policy_version, "ppol_activation_outer_version"),
        (context.outer_payload_sha256 == sha256_bytes(bundle.raw), "ppol_activation_outer_payload_digest"),
        (context.outer_file_sha256 == context.expected_outer_file_sha256, "ppol_activation_outer_file_digest"),
        (context.policy_signature_verified, "ppol_activation_policy_signature"),
        (context.manifest_signature_verified, "ppol_activation_manifest_signature"),
        (context.artifact_signatures_verified, "ppol_activation_artifact_signatures"),
        (context.target_profile_verified, "ppol_activation_target_profile"),
        (context.initial_system_digest_verified, "ppol_activation_initial_system_digest"),
        (context.recovery_digest_verified, "ppol_activation_recovery_digest"),
        (context.symbols_digest_verified, "ppol_activation_symbols_digest"),
        (context.microcode_digest_verified, "ppol_activation_microcode_digest"),
        (context.firmware_digest_verified, "ppol_activation_firmware_digest"),
        (context.trust_policy_authenticated, "ppol_activation_trust_policy"),
        (context.revocation_state_authenticated, "ppol_activation_revocation_state"),
        (context.rollback_state_authenticated, "ppol_activation_rollback_state"),
        (context.audit_schema_verified, "ppol_activation_audit_schema"),
        (context.inner_contracts_verified, "ppol_activation_inner_contracts"),
        (context.initial_system_cross_bound, "ppol_activation_initial_system_cross_binding"),
        (context.kernel_abi_verified, "ppol_activation_kernel_abi"),
        (context.pbp_verified, "ppol_activation_pbp"),
    )
    errors.extend(code for condition, code in checks if not condition)
    mode = _mode(bundle, context.selected_mode)
    if mode is None:
        errors.append("ppol_activation_mode")
    if not context.mode_authorized:
        errors.append("ppol_activation_mode_authority")
    if (
        mode is None
        or not context.transition_authorized
        or not mode.transition_mask & _mode_bit(context.previous_mode)
    ):
        errors.append("ppol_activation_transition_authority")
    for condition, code in (
        (context.capability_allocator_ready, "ppol_activation_capability_allocator"),
        (context.resource_broker_ready, "ppol_activation_resource_broker"),
        (context.audit_sink_ready, "ppol_activation_audit_sink"),
        (context.receipt_store_ready, "ppol_activation_receipt_store"),
    ):
        if not condition:
            errors.append(code)
    if context.selected_mode == MODE_FIRMWARE and not context.physical_presence_verified:
        errors.append("ppol_activation_physical_presence")
    if context.selected_mode == MODE_FIRMWARE and not context.separate_authority_verified:
        errors.append("ppol_activation_separate_authority")
    rule = _rule(bundle, context.capability_id) if context.capability_id else None
    if context.capability_id and rule is None or not context.capability_id and mode is not None and mode.allowed_capability_count:
        errors.append("ppol_activation_capability")
    if rule is not None and mode is not None:
        if not rule.allowed_mode_mask & _mode_bit(context.selected_mode):
            errors.append("ppol_activation_capability_mode")
        if context.capability_revoked:
            errors.append("ppol_activation_capability_revoked")
        if context.issued_generation != rule.resource_generation or context.current_generation != rule.resource_generation:
            errors.append("ppol_activation_generation")
        ceiling = rule.ceiling_rights & mode.allowed_rights
        if context.issued_rights == 0 or context.issued_rights & ~ceiling:
            errors.append("ppol_activation_issued_rights")
        if context.requested_rights == 0 or context.requested_rights & ~context.issued_rights:
            errors.append("ppol_activation_requested_rights")
        if context.requested_effects == 0 or context.requested_effects & ~(rule.effect_mask & mode.allowed_effects):
            errors.append("ppol_activation_requested_effects")
    elif not context.capability_id:
        if context.capability_revoked:
            errors.append("ppol_activation_capability_revoked")
        if context.issued_generation or context.current_generation:
            errors.append("ppol_activation_generation")
        if context.issued_rights or context.requested_rights:
            errors.append("ppol_activation_issued_rights")
        if mode is None or context.requested_effects == 0 or context.requested_effects & ~mode.allowed_effects:
            errors.append("ppol_activation_requested_effects")
    for condition, code in (
        (context.qualification_only, "ppol_activation_not_qualification_only"),
        (not context.live_execution_requested, "ppol_activation_live_execution_requested"),
        (not context.persistent_write_requested, "ppol_activation_persistent_write_requested"),
        (not context.firmware_call_requested, "ppol_activation_firmware_call_requested"),
        (not context.driver_load_requested, "ppol_activation_driver_load_requested"),
        (not context.physical_media_write_requested, "ppol_activation_physical_media_write_requested"),
        (not context.state_mutation_requested, "ppol_activation_state_mutation_requested"),
    ):
        if not condition:
            errors.append(code)
    return sorted(set(errors), key=ACTIVATION_ERROR_ORDER.index)


def authorize_dry_run_decision(bundle: Bundle, context: ActivationContext) -> DryRunDecision:
    errors = activation_errors(bundle, context)
    if errors:
        raise PolicyError(errors[0])
    mode = bundle.modes[context.selected_mode - 1]
    rule = _rule(bundle, context.capability_id) if context.capability_id else None
    rights = 0 if rule is None else context.requested_rights & context.issued_rights & rule.ceiling_rights & mode.allowed_rights
    effects = context.requested_effects & mode.allowed_effects
    if rule is not None:
        effects &= rule.effect_mask
    return DryRunDecision(sha256_bytes(bundle.raw), mode.mode, context.capability_id, rights, effects, mode.generation, 0 if rule is None else rule.resource_generation, mode.allowed_capability_count, True, True)


def _decision_id(plan: DryRunDecision, revocation_epoch: int, audit_sequence: int) -> str:
    payload = struct.pack("<IIQQQQQQ", plan.mode, plan.capability_id, plan.effective_rights, plan.effective_effects, plan.mode_generation, plan.capability_generation, revocation_epoch, audit_sequence)
    return sha256_bytes(bytes.fromhex(plan.policy_sha256) + payload)


def synthetic_receipt(plan: DryRunDecision, *, revocation_epoch: int = 1, audit_sequence: int = 1) -> DecisionReceipt:
    return DecisionReceipt(plan.policy_sha256, plan.mode, plan.capability_id, plan.effective_rights, plan.effective_effects, plan.mode_generation, plan.capability_generation, revocation_epoch, audit_sequence, True, True, _decision_id(plan, revocation_epoch, audit_sequence))


def receipt_errors(plan: DryRunDecision, receipt: DecisionReceipt) -> list[str]:
    values = (
        (receipt.qualification_only, "ppol_receipt_not_qualification_only"),
        (receipt.policy_sha256 == plan.policy_sha256, "ppol_receipt_policy_digest"),
        (receipt.mode == plan.mode, "ppol_receipt_mode"),
        (receipt.capability_id == plan.capability_id, "ppol_receipt_capability"),
        (receipt.effective_rights == plan.effective_rights, "ppol_receipt_rights"),
        (receipt.effective_effects == plan.effective_effects, "ppol_receipt_effects"),
        (receipt.mode_generation == plan.mode_generation and receipt.capability_generation == plan.capability_generation, "ppol_receipt_generation"),
        (receipt.revocation_epoch > 0, "ppol_receipt_revocation_epoch"),
        (receipt.audit_sequence > 0, "ppol_receipt_audit_sequence"),
        (receipt.durable, "ppol_receipt_not_durable"),
        (receipt.decision_id == _decision_id(plan, receipt.revocation_epoch, receipt.audit_sequence), "ppol_receipt_decision_id"),
    )
    return [code for condition, code in values if not condition]


def verify_receipt(plan: DryRunDecision, receipt: DecisionReceipt) -> None:
    errors = receipt_errors(plan, receipt)
    if errors:
        raise PolicyError(errors[0])


def summary(bundle: Bundle) -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "version": f"{MAJOR_VERSION}.{MINOR_VERSION}",
        "policy_version": bundle.policy_version,
        "policy_id": bundle.policy_id,
        "bytes": len(bundle.raw),
        "mode_count": len(bundle.modes),
        "capability_rule_count": len(bundle.capability_rules),
        "body_sha256": bundle.body_sha256,
        "initial_system_sha256": bundle.initial_system_sha256,
        "qualification_only": True,
    }


def _vector(vector_id: str, data: bytes) -> dict[str, Any]:
    bundle = parse(data)
    return {"id": vector_id, "bytes": len(data), "sha256": sha256_bytes(data), "hex": data.hex().upper(), "summary": summary(bundle)}


def make_golden_vectors() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_policy_golden_vectors",
        "contract_id": CONTRACT_ID,
        "vectors": [_vector("canonical", canonical_bundle()), _vector("minimal", minimal_bundle()), _vector("boundary", boundary_bundle())],
    }


def _binding_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)}


def implementation_bindings(root: Path = ROOT) -> list[dict[str, Any]]:
    return [_binding_record(root / relative) for relative in IMPLEMENTATION_INPUTS]


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_no_std_parser": True,
        "six_mode_default_deny_model": True,
        "capability_attenuation_and_parent_monotonicity": True,
        "pinit1_route_cross_binding": True,
        "safe_and_recovery_builtin_floors": True,
        "firmware_physical_presence_and_separate_authority_modeled": True,
        "durable_decision_receipt_validation": True,
        "synthetic_policy_only": True,
        "live_policy_enforcement": False,
        "pooleboot_policy_enforced": False,
        "poolekernel_policy_enforced": False,
        "pooleglyph_executable_authority": False,
        "signature_verified": False,
        "authority_created": False,
        "state_mutated": False,
        "physical_media_written": False,
        "production_ready": False,
    }


def expected_contract(root: Path = ROOT) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_policy_contract",
        "contract_id": CONTRACT_ID,
        "version": {"major": MAJOR_VERSION, "minor": MINOR_VERSION},
        "profile": "synthetic_qualification_only",
        "format": {"header_bytes": HEADER_BYTES, "mode_record_bytes": MODE_RECORD_BYTES, "capability_record_bytes": CAPABILITY_RECORD_BYTES, "tables_are_contiguous": True, "mode_count": MODE_COUNT},
        "limits": {"bundle_bytes": MAX_BUNDLE_BYTES, "capability_rules": MAX_CAPABILITY_RULES, "audit_receipts": 1_000_000, "generation_advance": 1},
        "header_flags": list(HEADER_FLAG_NAMES),
        "modes": [MODE_NAMES[item] for item in MODES],
        "effects": ["audit", "read_state", "write_volatile", "write_persistent", "execute", "ipc", "network", "device_io", "dma", "debug", "pdc_compute", "pdc_actuate", "update", "firmware", "secret", "power"],
        "authority_equation": "builtin_ceiling & signed_policy & selected_mode & issued_capability & request",
        "activation_error_order": list(ACTIVATION_ERROR_ORDER),
        "receipt_error_order": list(RECEIPT_ERROR_ORDER),
        "claims": expected_claims(),
        "non_claims": [
            "No PPOL1 parse, cross-binding result, dry-run decision, or receipt grants authority.",
            "No signature, private key, live revocation state, rollback state, or physical-presence signal is produced.",
            "No PooleBoot or PooleKernel policy interpreter, capability allocator, resource broker, or audit store is implemented here.",
            "No firmware call, driver load, state mutation, executable transfer, or physical-media write occurs.",
            "PooleGlyph data remains non-authoritative pending its separately gated Core IR promotion evidence.",
        ],
        "primary_references": [
            "https://docs.sel4.systems/projects/capdl/lang-spec.html",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/lifecycle",
            "https://uefi.org/specs/UEFI/2.11/03_Boot_Manager.html",
            "https://theupdateframework.github.io/specification/latest/",
            "https://csrc.nist.gov/pubs/sp/800/193/final",
            "https://csrc.nist.gov/pubs/sp/800/207/final",
        ],
        "implementation_bindings": implementation_bindings(root),
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise PolicyError("ppol_json_object")
    return value


def _schema_errors(value: dict[str, Any], root: Path, relative: Path) -> list[str]:
    return validate_json(value, read_json(root / relative))


def contract_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, CONTRACT_SCHEMA_RELATIVE)
    if not errors and value != expected_contract(root):
        errors.append("PPOL1 contract differs from implementation-derived contract")
    return errors


def golden_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, GOLDEN_SCHEMA_RELATIVE)
    if not errors and value != make_golden_vectors():
        errors.append("PPOL1 golden vectors differ from implementation-derived vectors")
    return errors


def _binding_matches(value: Any, root: Path) -> bool:
    if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
        return False
    path = root / str(value["path"])
    return path.is_file() and value == _binding_record(path)


def readiness_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, READINESS_SCHEMA_RELATIVE)
    if errors:
        return errors
    if value.get("status") != "pass" or value.get("contract_id") != CONTRACT_ID:
        errors.append("PPOL1 readiness status changed")
    inputs = value.get("inputs", {})
    for name in ("contract", "golden_vectors", "toolchain_lock", "toolchain_qualification", "tier1_profile"):
        if not _binding_matches(inputs.get(name), root):
            errors.append(f"PPOL1 readiness binding stale: {name}")
    if inputs.get("implementation_inputs") != implementation_bindings(root):
        errors.append("PPOL1 readiness implementation bindings are stale")
    differential = value.get("differential", {})
    if sum(item.get("cases", 0) for item in differential.values() if isinstance(item, dict)) < 32768 or any(item.get("mismatches") != 0 for item in differential.values() if isinstance(item, dict)):
        errors.append("PPOL1 differential evidence is insufficient")
    controls = value.get("negative_controls", [])
    if len(controls) < 80 or any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("PPOL1 negative controls are insufficient")
    if value.get("claims") != expected_claims() or value.get("production_ready") is not False:
        errors.append("PPOL1 readiness claims overreach")
    return errors
