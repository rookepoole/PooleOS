"""Independent PFWM1 firmware-manifest codec and qualification oracle.

PFWM1 v1 is deliberately a synthetic, dry-run-only contract.  It normalizes
firmware inventory and update intent without carrying payload bytes, invoking
firmware services, loading updater drivers, or granting update authority.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import struct
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID: Final = "PFWM1"
MAGIC: Final = b"PFWM1\0\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 512
COMPONENT_RECORD_BYTES: Final = 256
DEPENDENCY_RECORD_BYTES: Final = 16
MAX_MANIFEST_BYTES: Final = 64 * 1024
MAX_COMPONENTS: Final = 32
MAX_DEPENDENCIES: Final = 128
MAX_EXTERNAL_PAYLOAD_BYTES: Final = 64 * 1024 * 1024
MAX_APPLY_TIMEOUT_MS: Final = 30 * 60 * 1000
MAX_RESET_TIMEOUT_MS: Final = 15 * 60 * 1000
MAX_RETRY_LIMIT: Final = 3

PROFILE_SYNTHETIC_QUALIFICATION: Final = 1

KIND_PLATFORM_FIRMWARE: Final = 1
KIND_CONTROLLER_FIRMWARE: Final = 2
KIND_DEVICE_FIRMWARE: Final = 3
KINDS: Final = (
    KIND_PLATFORM_FIRMWARE,
    KIND_CONTROLLER_FIRMWARE,
    KIND_DEVICE_FIRMWARE,
)

TRANSPORT_UEFI_CAPSULE_ESRT: Final = 1
TRANSPORT_DEVICE_PLUGIN: Final = 2
TRANSPORT_PLDM: Final = 3
TRANSPORTS: Final = (
    TRANSPORT_UEFI_CAPSULE_ESRT,
    TRANSPORT_DEVICE_PLUGIN,
    TRANSPORT_PLDM,
)

FLAG_TARGET_PROFILE_BOUND: Final = 1 << 0
FLAG_EXACT_IDENTITIES: Final = 1 << 1
FLAG_EXTERNAL_PAYLOAD_DIGESTS: Final = 1 << 2
FLAG_MANIFEST_SIGNATURE_REQUIRED: Final = 1 << 3
FLAG_PACKAGE_SIGNATURE_REQUIRED: Final = 1 << 4
FLAG_VENDOR_SIGNATURE_REQUIRED: Final = 1 << 5
FLAG_LICENSE_POLICY_REQUIRED: Final = 1 << 6
FLAG_REVOCATION_REQUIRED: Final = 1 << 7
FLAG_ANTI_ROLLBACK: Final = 1 << 8
FLAG_DEPENDENCY_DAG: Final = 1 << 9
FLAG_SINGLE_COMPONENT_TRANSACTION: Final = 1 << 10
FLAG_PROTECTED_STAGING: Final = 1 << 11
FLAG_POWER_GUARD: Final = 1 << 12
FLAG_RECOVERY_REQUIRED: Final = 1 << 13
FLAG_PHYSICAL_CONFIRMATION: Final = 1 << 14
FLAG_POST_RESET_VERIFY: Final = 1 << 15
FLAG_DURABLE_RECEIPT: Final = 1 << 16
FLAG_NO_GENERIC_FLASH: Final = 1 << 17
FLAG_NO_AUTHORITY_FROM_PARSE: Final = 1 << 18
FLAG_SYNTHETIC_QUALIFICATION: Final = 1 << 19
REQUIRED_FLAGS: Final = (1 << 20) - 1

COMPONENT_EXACT_TARGET: Final = 1 << 0
COMPONENT_UPDATABLE_REQUIRED: Final = 1 << 1
COMPONENT_AUTHENTICATION_REQUIRED: Final = 1 << 2
COMPONENT_RESET_REQUIRED: Final = 1 << 3
COMPONENT_DEPENDENCY_ENFORCED: Final = 1 << 4
COMPONENT_POWER_GUARD: Final = 1 << 5
COMPONENT_QUIESCE_REQUIRED: Final = 1 << 6
COMPONENT_STORAGE_GUARD: Final = 1 << 7
COMPONENT_SUSPEND_GUARD: Final = 1 << 8
COMPONENT_SHUTDOWN_GUARD: Final = 1 << 9
COMPONENT_REENUMERATE_REQUIRED: Final = 1 << 10
COMPONENT_SELF_TEST_REQUIRED: Final = 1 << 11
COMPONENT_RECOVERY_ROUTE_REQUIRED: Final = 1 << 12
COMPONENT_PHYSICAL_CONFIRMATION: Final = 1 << 13
COMPONENT_NO_GENERIC_FLASH: Final = 1 << 14
COMPONENT_POST_RESET_VERIFY: Final = 1 << 15
COMPONENT_RECEIPT_REQUIRED: Final = 1 << 16
COMPONENT_REBIND_AFTER_VERIFY: Final = 1 << 17
COMPONENT_HARDWARE_INSTANCE_MANIFEST_BOUND: Final = 1 << 18
COMPONENT_REQUIRED_FLAGS: Final = (1 << 19) - 1

OUTER_ROLE_FIRMWARE_MANIFEST: Final = 6
EXPECTED_LAST_ATTEMPT_SUCCESS: Final = 0

CONTRACT_RELATIVE: Final = Path("specs/native-firmware-contract.json")
CONTRACT_SCHEMA_RELATIVE: Final = Path("specs/native-firmware-contract.schema.json")
GOLDEN_RELATIVE: Final = Path("specs/native-firmware-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE: Final = Path("specs/native-firmware-golden-vectors.schema.json")
READINESS_RELATIVE: Final = Path("runs/native_firmware_readiness.json")
READINESS_SCHEMA_RELATIVE: Final = Path("specs/native-firmware-readiness.schema.json")

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/firmware/Cargo.toml",
    "native/firmware/src/lib.rs",
    "native/firmware/src/bin/pfwm1_probe.rs",
    "runtime/native_firmware.py",
    "tools/generate_native_firmware_vectors.py",
    "tools/qualify_native_firmware.py",
    "tests/test_native_firmware.py",
    "docs/native-firmware-manifest.md",
)

HEADER_FLAG_NAMES: Final = (
    "target_profile_bound",
    "exact_identities",
    "external_payload_digests",
    "manifest_signature_required",
    "package_signature_required",
    "vendor_signature_required",
    "license_policy_required",
    "revocation_required",
    "anti_rollback",
    "dependency_dag",
    "single_component_transaction",
    "protected_staging",
    "power_guard",
    "recovery_required",
    "physical_confirmation",
    "post_reset_verify",
    "durable_receipt",
    "no_generic_flash",
    "no_authority_from_parse",
    "synthetic_qualification",
)

COMPONENT_FLAG_NAMES: Final = (
    "exact_target",
    "updatable_required",
    "authentication_required",
    "reset_required",
    "dependency_enforced",
    "power_guard",
    "quiesce_required",
    "storage_guard",
    "suspend_guard",
    "shutdown_guard",
    "reenumerate_required",
    "self_test_required",
    "recovery_route_required",
    "physical_confirmation",
    "no_generic_flash",
    "post_reset_verify",
    "receipt_required",
    "rebind_after_verify",
    "hardware_instance_manifest_bound",
)

ACTIVATION_ERROR_ORDER: Final = (
    "pfwm_activation_outer_signature",
    "pfwm_activation_outer_role",
    "pfwm_activation_outer_version",
    "pfwm_activation_outer_payload_digest",
    "pfwm_activation_outer_file_digest",
    "pfwm_activation_manifest_signature",
    "pfwm_activation_package_signature",
    "pfwm_activation_vendor_signature",
    "pfwm_activation_target_profile",
    "pfwm_activation_hardware_inventory",
    "pfwm_activation_device_identity",
    "pfwm_activation_current_versions",
    "pfwm_activation_transport_support",
    "pfwm_activation_firmware_services",
    "pfwm_activation_updater_plugins",
    "pfwm_activation_plugin_authority",
    "pfwm_activation_external_payloads",
    "pfwm_activation_payload_digests",
    "pfwm_activation_license_policy",
    "pfwm_activation_redistribution",
    "pfwm_activation_revocation_state",
    "pfwm_activation_component_revoked",
    "pfwm_activation_anti_rollback",
    "pfwm_activation_recovery",
    "pfwm_activation_recovery_backup",
    "pfwm_activation_staging",
    "pfwm_activation_staging_capacity",
    "pfwm_activation_power",
    "pfwm_activation_ac_power",
    "pfwm_activation_battery",
    "pfwm_activation_transaction_journal",
    "pfwm_activation_quiescence",
    "pfwm_activation_storage_guard",
    "pfwm_activation_suspend_shutdown_guard",
    "pfwm_activation_reset_authority",
    "pfwm_activation_reboot_authority",
    "pfwm_activation_user_confirmation",
    "pfwm_activation_physical_presence",
    "pfwm_activation_post_reset_verifier",
    "pfwm_activation_receipt_storage",
    "pfwm_activation_firmware_change_authority",
    "pfwm_activation_not_qualification_only",
    "pfwm_activation_live_firmware_call_requested",
    "pfwm_activation_driver_load_requested",
    "pfwm_activation_physical_media_write_requested",
    "pfwm_activation_firmware_mutation_requested",
)

POST_RESET_ERROR_ORDER: Final = (
    "pfwm_post_reset_not_qualification_only",
    "pfwm_post_reset_record_count",
    "pfwm_post_reset_record_order",
    "pfwm_post_reset_resource_identity",
    "pfwm_post_reset_hardware_instance",
    "pfwm_post_reset_version",
    "pfwm_post_reset_last_attempt_version",
    "pfwm_post_reset_last_attempt_status",
    "pfwm_post_reset_reenumeration",
    "pfwm_post_reset_self_test",
    "pfwm_post_reset_recovery",
    "pfwm_post_reset_receipt",
    "pfwm_post_reset_boot_loop_guard",
    "pfwm_post_reset_state_commit",
    "pfwm_post_reset_driver_rebind",
)

_MANIFEST_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,38}$")


class FirmwareError(RuntimeError):
    """Raised when PFWM1 bytes or pure qualification evidence fail closed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Component:
    component_id: int
    kind: int
    transport: int
    phase: int
    dependency_start: int
    dependency_count: int
    flags: int
    resource_guid: bytes
    hardware_instance: int
    current_version: int
    target_version: int
    lowest_supported_version: int
    rollback_floor: int
    known_good_version: int
    external_payload_bytes: int
    device_identity_sha256: str
    external_payload_sha256: str
    vendor_signer_sha256: str
    updater_plugin_sha256: str
    recovery_identity_sha256: str


@dataclasses.dataclass(frozen=True)
class Dependency:
    component_id: int
    required_component_id: int
    minimum_version: int


@dataclasses.dataclass(frozen=True)
class Bundle:
    raw: bytes
    manifest_version: int
    manifest_id: str
    profile: int
    flags: int
    maximum_external_payload_bytes: int
    maximum_transaction_components: int
    required_battery_percent: int
    retry_limit: int
    apply_timeout_ms: int
    reset_timeout_ms: int
    target_profile_sha256: str
    inventory_schema_sha256: str
    package_policy_sha256: str
    license_manifest_sha256: str
    revocation_state_sha256: str
    recovery_profile_sha256: str
    updater_allowlist_sha256: str
    trust_policy_sha256: str
    receipt_schema_sha256: str
    body_sha256: str
    components: tuple[Component, ...]
    dependencies: tuple[Dependency, ...]


@dataclasses.dataclass(frozen=True)
class ObservedVersion:
    component_id: int
    version: int


@dataclasses.dataclass(frozen=True)
class ActivationContext:
    outer_role: int
    outer_version: int
    outer_payload_sha256: str
    outer_file_sha256: str
    expected_outer_file_sha256: str
    observed_versions: tuple[ObservedVersion, ...]
    staging_capacity_bytes: int
    battery_percent: int
    outer_signature_verified: bool
    manifest_signature_verified: bool
    package_signature_verified: bool
    vendor_signatures_verified: bool
    target_profile_verified: bool
    hardware_inventory_observed: bool
    exact_device_identities_verified: bool
    current_versions_observed: bool
    transport_support_verified: bool
    firmware_service_inventory_verified: bool
    updater_plugins_verified: bool
    plugin_authority_granted: bool
    external_payloads_present: bool
    payload_digests_verified: bool
    license_policy_satisfied: bool
    redistribution_authorized: bool
    revocation_state_authenticated: bool
    no_components_revoked: bool
    anti_rollback_state_authenticated: bool
    recovery_ready: bool
    recovery_backup_verified: bool
    protected_staging_ready: bool
    stable_power: bool
    ac_power_present: bool
    transaction_journal_ready: bool
    quiescence_ready: bool
    storage_guard_ready: bool
    suspend_shutdown_guard_ready: bool
    reset_authorized: bool
    reboot_authorized: bool
    user_confirmed: bool
    physical_presence_verified: bool
    post_reset_verifier_ready: bool
    receipt_storage_ready: bool
    firmware_change_authorized: bool
    qualification_only: bool
    live_firmware_call_requested: bool
    driver_load_requested: bool
    physical_media_write_requested: bool
    firmware_mutation_requested: bool


@dataclasses.dataclass(frozen=True)
class DryRunPlan:
    component_order: tuple[int, ...]
    maximum_parallel_components: int
    external_payload_bytes: int
    reset_required: bool
    qualification_only: bool


@dataclasses.dataclass(frozen=True)
class PostResetRecord:
    component_id: int
    resource_guid: bytes
    hardware_instance: int
    observed_version: int
    last_attempt_version: int
    last_attempt_status: int
    reenumerated: bool
    self_test_passed: bool
    recovery_intact: bool
    receipt_persisted: bool
    boot_loop_prevented: bool
    state_committed: bool
    driver_rebound_after_validation: bool


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _digest(label: str) -> str:
    return sha256_bytes(label.encode("ascii"))


def _digest_bytes(value: str) -> bytes:
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise FirmwareError("pfwm_component_digest") from error
    if len(result) != 32:
        raise FirmwareError("pfwm_component_digest")
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
        raise FirmwareError(code)
    return value.hex().upper()


def _manifest_id(data: bytes) -> str:
    field = data[408:448]
    nul = field.find(b"\0")
    if nul <= 0 or any(field[nul:]):
        raise FirmwareError("pfwm_manifest_id")
    try:
        value = field[:nul].decode("ascii")
    except UnicodeDecodeError as error:
        raise FirmwareError("pfwm_manifest_id") from error
    if not _MANIFEST_ID.fullmatch(value):
        raise FirmwareError("pfwm_manifest_id")
    return value


def _transport_allowed(kind: int, transport: int) -> bool:
    return (
        (kind == KIND_PLATFORM_FIRMWARE and transport == TRANSPORT_UEFI_CAPSULE_ESRT)
        or (
            kind == KIND_CONTROLLER_FIRMWARE
            and transport == TRANSPORT_DEVICE_PLUGIN
        )
        or (
            kind == KIND_DEVICE_FIRMWARE
            and transport in (TRANSPORT_DEVICE_PLUGIN, TRANSPORT_PLDM)
        )
    )


def _parse_component(data: bytes, offset: int) -> Component:
    record = data[offset : offset + COMPONENT_RECORD_BYTES]
    if len(record) != COMPONENT_RECORD_BYTES:
        raise FirmwareError("pfwm_truncated")
    component_id = _u32(record, 0)
    kind = _u16(record, 4)
    transport = _u16(record, 6)
    phase = _u16(record, 8)
    dependency_count = _u16(record, 10)
    dependency_start = _u32(record, 12)
    flags = _u32(record, 16)
    if component_id == 0:
        raise FirmwareError("pfwm_component_id")
    if kind not in KINDS:
        raise FirmwareError("pfwm_component_kind")
    if transport not in TRANSPORTS:
        raise FirmwareError("pfwm_component_transport")
    if not _transport_allowed(kind, transport):
        raise FirmwareError("pfwm_component_mapping")
    if flags != COMPONENT_REQUIRED_FLAGS:
        raise FirmwareError("pfwm_component_flags")
    if _u32(record, 20) != 0:
        raise FirmwareError("pfwm_component_reserved")
    resource_guid = record[24:40]
    if not any(resource_guid):
        raise FirmwareError("pfwm_component_guid")
    hardware_instance = _u64(record, 40)
    if hardware_instance == 0:
        raise FirmwareError("pfwm_component_hardware_instance")
    current_version = _u64(record, 48)
    target_version = _u64(record, 56)
    lowest_supported_version = _u64(record, 64)
    rollback_floor = _u64(record, 72)
    known_good_version = _u64(record, 80)
    if not (
        0 < lowest_supported_version
        <= rollback_floor
        <= known_good_version
        <= current_version
        < target_version
    ):
        raise FirmwareError("pfwm_component_versions")
    external_payload_bytes = _u64(record, 88)
    if external_payload_bytes == 0 or external_payload_bytes > MAX_EXTERNAL_PAYLOAD_BYTES:
        raise FirmwareError("pfwm_component_payload_size")
    return Component(
        component_id=component_id,
        kind=kind,
        transport=transport,
        phase=phase,
        dependency_start=dependency_start,
        dependency_count=dependency_count,
        flags=flags,
        resource_guid=resource_guid,
        hardware_instance=hardware_instance,
        current_version=current_version,
        target_version=target_version,
        lowest_supported_version=lowest_supported_version,
        rollback_floor=rollback_floor,
        known_good_version=known_good_version,
        external_payload_bytes=external_payload_bytes,
        device_identity_sha256=_nonzero_digest(record, 96, "pfwm_component_digest"),
        external_payload_sha256=_nonzero_digest(record, 128, "pfwm_component_digest"),
        vendor_signer_sha256=_nonzero_digest(record, 160, "pfwm_component_digest"),
        updater_plugin_sha256=_nonzero_digest(record, 192, "pfwm_component_digest"),
        recovery_identity_sha256=_nonzero_digest(record, 224, "pfwm_component_digest"),
    )


def parse(data: bytes) -> Bundle:
    if len(data) < HEADER_BYTES:
        raise FirmwareError("pfwm_truncated")
    if len(data) > MAX_MANIFEST_BYTES:
        raise FirmwareError("pfwm_oversized")
    if data[:8] != MAGIC:
        raise FirmwareError("pfwm_magic")
    if (_u16(data, 8), _u16(data, 10)) != (MAJOR_VERSION, MINOR_VERSION):
        raise FirmwareError("pfwm_version")
    if _u16(data, 12) != HEADER_BYTES:
        raise FirmwareError("pfwm_header_size")
    if (
        _u16(data, 14) != COMPONENT_RECORD_BYTES
        or _u16(data, 16) != DEPENDENCY_RECORD_BYTES
    ):
        raise FirmwareError("pfwm_record_size")
    profile = _u16(data, 18)
    if profile != PROFILE_SYNTHETIC_QUALIFICATION:
        raise FirmwareError("pfwm_profile")
    flags = _u32(data, 20)
    if flags != REQUIRED_FLAGS:
        raise FirmwareError("pfwm_flags")
    manifest_version = _u64(data, 24)
    if manifest_version == 0:
        raise FirmwareError("pfwm_manifest_version")
    component_count = _u32(data, 32)
    dependency_count = _u32(data, 36)
    if not 1 <= component_count <= MAX_COMPONENTS or dependency_count > MAX_DEPENDENCIES:
        raise FirmwareError("pfwm_counts")
    component_offset = _u64(data, 40)
    dependency_offset = _u64(data, 48)
    total_bytes = _u64(data, 56)
    expected_dependency_offset = HEADER_BYTES + component_count * COMPONENT_RECORD_BYTES
    expected_total = expected_dependency_offset + dependency_count * DEPENDENCY_RECORD_BYTES
    if component_offset != HEADER_BYTES or dependency_offset != expected_dependency_offset:
        raise FirmwareError("pfwm_table_layout")
    if total_bytes != expected_total or len(data) < total_bytes:
        raise FirmwareError("pfwm_truncated")
    if len(data) > total_bytes:
        raise FirmwareError("pfwm_trailing_bytes")
    maximum_external_payload_bytes = _u64(data, 64)
    maximum_transaction_components = _u32(data, 72)
    required_battery_percent = _u16(data, 76)
    retry_limit = _u16(data, 78)
    apply_timeout_ms = _u32(data, 80)
    reset_timeout_ms = _u32(data, 84)
    if (
        maximum_external_payload_bytes == 0
        or maximum_external_payload_bytes > MAX_EXTERNAL_PAYLOAD_BYTES
        or maximum_transaction_components != 1
        or not 1 <= required_battery_percent <= 100
        or retry_limit > MAX_RETRY_LIMIT
        or not 1 <= apply_timeout_ms <= MAX_APPLY_TIMEOUT_MS
        or not 1 <= reset_timeout_ms <= MAX_RESET_TIMEOUT_MS
    ):
        raise FirmwareError("pfwm_limits")
    target_profile_sha256 = _nonzero_digest(data, 88, "pfwm_digest_zero")
    inventory_schema_sha256 = _nonzero_digest(data, 120, "pfwm_digest_zero")
    package_policy_sha256 = _nonzero_digest(data, 152, "pfwm_digest_zero")
    license_manifest_sha256 = _nonzero_digest(data, 184, "pfwm_digest_zero")
    revocation_state_sha256 = _nonzero_digest(data, 216, "pfwm_digest_zero")
    recovery_profile_sha256 = _nonzero_digest(data, 248, "pfwm_digest_zero")
    updater_allowlist_sha256 = _nonzero_digest(data, 280, "pfwm_digest_zero")
    trust_policy_sha256 = _nonzero_digest(data, 312, "pfwm_digest_zero")
    receipt_schema_sha256 = _nonzero_digest(data, 344, "pfwm_digest_zero")
    body_sha256 = _nonzero_digest(data, 376, "pfwm_digest_zero")
    manifest_id = _manifest_id(data)
    if any(data[448:HEADER_BYTES]):
        raise FirmwareError("pfwm_reserved")
    body = data[HEADER_BYTES:]
    if sha256_bytes(body) != body_sha256:
        raise FirmwareError("pfwm_body_digest")

    components = tuple(
        _parse_component(data, HEADER_BYTES + index * COMPONENT_RECORD_BYTES)
        for index in range(component_count)
    )
    previous_key: tuple[int, int] | None = None
    resource_keys: set[tuple[bytes, int]] = set()
    component_ids: set[int] = set()
    expected_dependency_start = 0
    seen_phases: set[int] = set()
    for component in components:
        key = (component.phase, component.component_id)
        if previous_key is not None and key <= previous_key:
            raise FirmwareError("pfwm_component_order")
        previous_key = key
        if component.phase >= MAX_COMPONENTS:
            raise FirmwareError("pfwm_phase_order")
        if component.component_id in component_ids:
            raise FirmwareError("pfwm_component_id")
        component_ids.add(component.component_id)
        resource_key = (component.resource_guid, component.hardware_instance)
        if resource_key in resource_keys:
            raise FirmwareError("pfwm_component_guid")
        resource_keys.add(resource_key)
        if component.dependency_start != expected_dependency_start:
            raise FirmwareError("pfwm_dependency_layout")
        expected_dependency_start += component.dependency_count
        if expected_dependency_start > dependency_count:
            raise FirmwareError("pfwm_dependency_layout")
        seen_phases.add(component.phase)
        if component.external_payload_bytes > maximum_external_payload_bytes:
            raise FirmwareError("pfwm_component_payload_size")
    if expected_dependency_start != dependency_count:
        raise FirmwareError("pfwm_dependency_layout")
    if seen_phases != set(range(max(seen_phases) + 1)):
        raise FirmwareError("pfwm_phase_order")

    component_by_id = {item.component_id: item for item in components}
    dependencies: list[Dependency] = []
    for index in range(dependency_count):
        offset = expected_dependency_offset + index * DEPENDENCY_RECORD_BYTES
        dependency = Dependency(_u32(data, offset), _u32(data, offset + 4), _u64(data, offset + 8))
        source = component_by_id.get(dependency.component_id)
        required = component_by_id.get(dependency.required_component_id)
        if source is None or required is None or source is required:
            raise FirmwareError("pfwm_dependency_id")
        local_index = index - source.dependency_start
        if not 0 <= local_index < source.dependency_count:
            raise FirmwareError("pfwm_dependency_layout")
        if local_index and dependencies[-1].required_component_id >= dependency.required_component_id:
            raise FirmwareError("pfwm_dependency_order")
        if dependency.minimum_version != required.target_version:
            raise FirmwareError("pfwm_dependency_version")
        if required.phase >= source.phase:
            raise FirmwareError("pfwm_dependency_phase")
        dependencies.append(dependency)

    return Bundle(
        raw=data,
        manifest_version=manifest_version,
        manifest_id=manifest_id,
        profile=profile,
        flags=flags,
        maximum_external_payload_bytes=maximum_external_payload_bytes,
        maximum_transaction_components=maximum_transaction_components,
        required_battery_percent=required_battery_percent,
        retry_limit=retry_limit,
        apply_timeout_ms=apply_timeout_ms,
        reset_timeout_ms=reset_timeout_ms,
        target_profile_sha256=target_profile_sha256,
        inventory_schema_sha256=inventory_schema_sha256,
        package_policy_sha256=package_policy_sha256,
        license_manifest_sha256=license_manifest_sha256,
        revocation_state_sha256=revocation_state_sha256,
        recovery_profile_sha256=recovery_profile_sha256,
        updater_allowlist_sha256=updater_allowlist_sha256,
        trust_policy_sha256=trust_policy_sha256,
        receipt_schema_sha256=receipt_schema_sha256,
        body_sha256=body_sha256,
        components=components,
        dependencies=tuple(dependencies),
    )


def make_component(
    component_id: int,
    *,
    kind: int,
    transport: int,
    phase: int,
    dependency_start: int,
    dependency_count: int,
    version_base: int,
) -> Component:
    label = f"PFWM1-SYNTHETIC-COMPONENT/{component_id}"
    return Component(
        component_id=component_id,
        kind=kind,
        transport=transport,
        phase=phase,
        dependency_start=dependency_start,
        dependency_count=dependency_count,
        flags=COMPONENT_REQUIRED_FLAGS,
        resource_guid=hashlib.sha256(f"{label}/RESOURCE".encode("ascii")).digest()[:16],
        hardware_instance=component_id,
        lowest_supported_version=version_base,
        rollback_floor=version_base,
        known_good_version=version_base,
        current_version=version_base,
        target_version=version_base + 1,
        external_payload_bytes=4096 + component_id,
        device_identity_sha256=_digest(f"{label}/DEVICE-IDENTITY"),
        external_payload_sha256=_digest(f"{label}/EXTERNAL-PAYLOAD-IDENTITY"),
        vendor_signer_sha256=_digest(f"{label}/VENDOR-SIGNER"),
        updater_plugin_sha256=_digest(f"{label}/UPDATER-PLUGIN"),
        recovery_identity_sha256=_digest(f"{label}/RECOVERY"),
    )


def encode(
    components: Sequence[Component],
    dependencies: Sequence[Dependency],
    *,
    manifest_id: str = "PFWM1-SYNTHETIC",
    manifest_version: int = 1,
    maximum_external_payload_bytes: int = MAX_EXTERNAL_PAYLOAD_BYTES,
    required_battery_percent: int = 80,
    retry_limit: int = 1,
    apply_timeout_ms: int = 300_000,
    reset_timeout_ms: int = 300_000,
) -> bytes:
    component_count = len(components)
    dependency_count = len(dependencies)
    total = HEADER_BYTES + component_count * COMPONENT_RECORD_BYTES + dependency_count * DEPENDENCY_RECORD_BYTES
    output = bytearray(total)
    output[:8] = MAGIC
    struct.pack_into(
        "<HHHHHHIQIIQQQQIHHII",
        output,
        8,
        MAJOR_VERSION,
        MINOR_VERSION,
        HEADER_BYTES,
        COMPONENT_RECORD_BYTES,
        DEPENDENCY_RECORD_BYTES,
        PROFILE_SYNTHETIC_QUALIFICATION,
        REQUIRED_FLAGS,
        manifest_version,
        component_count,
        dependency_count,
        HEADER_BYTES,
        HEADER_BYTES + component_count * COMPONENT_RECORD_BYTES,
        total,
        maximum_external_payload_bytes,
        1,
        required_battery_percent,
        retry_limit,
        apply_timeout_ms,
        reset_timeout_ms,
    )
    header_digests = (
        _digest("PFWM1/TARGET-PROFILE/TIER1-B650M-9800X3D-RTX5070-001"),
        _digest("PFWM1/NORMALIZED-INVENTORY-SCHEMA/1"),
        _digest("PFWM1/PACKAGE-POLICY/1"),
        _digest("PFWM1/LICENSE-MANIFEST/SYNTHETIC/1"),
        _digest("PFWM1/REVOCATION-STATE/SYNTHETIC/1"),
        _digest("PFWM1/RECOVERY-PROFILE/SYNTHETIC/1"),
        _digest("PFWM1/UPDATER-ALLOWLIST/SYNTHETIC/1"),
        _digest("PFWM1/TRUST-POLICY/SYNTHETIC/1"),
        _digest("PFWM1/RECEIPT-SCHEMA/1"),
    )
    for offset, digest in zip(range(88, 376, 32), header_digests, strict=True):
        output[offset : offset + 32] = bytes.fromhex(digest)
    try:
        encoded_id = manifest_id.encode("ascii")
    except UnicodeEncodeError as error:
        raise FirmwareError("pfwm_manifest_id") from error
    if not _MANIFEST_ID.fullmatch(manifest_id):
        raise FirmwareError("pfwm_manifest_id")
    output[408 : 408 + len(encoded_id)] = encoded_id

    for index, component in enumerate(components):
        offset = HEADER_BYTES + index * COMPONENT_RECORD_BYTES
        struct.pack_into(
            "<IHHHHIII16sQQQQQQQ",
            output,
            offset,
            component.component_id,
            component.kind,
            component.transport,
            component.phase,
            component.dependency_count,
            component.dependency_start,
            component.flags,
            0,
            component.resource_guid,
            component.hardware_instance,
            component.current_version,
            component.target_version,
            component.lowest_supported_version,
            component.rollback_floor,
            component.known_good_version,
            component.external_payload_bytes,
        )
        output[offset + 96 : offset + 128] = _digest_bytes(component.device_identity_sha256)
        output[offset + 128 : offset + 160] = _digest_bytes(component.external_payload_sha256)
        output[offset + 160 : offset + 192] = _digest_bytes(component.vendor_signer_sha256)
        output[offset + 192 : offset + 224] = _digest_bytes(component.updater_plugin_sha256)
        output[offset + 224 : offset + 256] = _digest_bytes(component.recovery_identity_sha256)
    dependency_offset = HEADER_BYTES + component_count * COMPONENT_RECORD_BYTES
    for index, dependency in enumerate(dependencies):
        struct.pack_into(
            "<IIQ",
            output,
            dependency_offset + index * DEPENDENCY_RECORD_BYTES,
            dependency.component_id,
            dependency.required_component_id,
            dependency.minimum_version,
        )
    output[376:408] = hashlib.sha256(output[HEADER_BYTES:]).digest()
    result = bytes(output)
    parse(result)
    return result


def canonical_components() -> tuple[tuple[Component, ...], tuple[Dependency, ...]]:
    platform = make_component(
        100,
        kind=KIND_PLATFORM_FIRMWARE,
        transport=TRANSPORT_UEFI_CAPSULE_ESRT,
        phase=0,
        dependency_start=0,
        dependency_count=0,
        version_base=0xF112_0001,
    )
    controller = make_component(
        200,
        kind=KIND_CONTROLLER_FIRMWARE,
        transport=TRANSPORT_DEVICE_PLUGIN,
        phase=1,
        dependency_start=0,
        dependency_count=1,
        version_base=0xF112_1001,
    )
    device = make_component(
        300,
        kind=KIND_DEVICE_FIRMWARE,
        transport=TRANSPORT_PLDM,
        phase=2,
        dependency_start=1,
        dependency_count=1,
        version_base=0xF112_2001,
    )
    dependencies = (
        Dependency(controller.component_id, platform.component_id, platform.target_version),
        Dependency(device.component_id, controller.component_id, controller.target_version),
    )
    return (platform, controller, device), dependencies


def canonical_bundle() -> bytes:
    components, dependencies = canonical_components()
    return encode(
        components,
        dependencies,
        manifest_id="PFWM1-CYCLE112-SYNTHETIC",
    )


def minimal_bundle() -> bytes:
    component = make_component(
        1,
        kind=KIND_PLATFORM_FIRMWARE,
        transport=TRANSPORT_UEFI_CAPSULE_ESRT,
        phase=0,
        dependency_start=0,
        dependency_count=0,
        version_base=0xF112_3001,
    )
    return encode((component,), (), manifest_id="PFWM1-MINIMAL-SYNTHETIC")


def boundary_bundle() -> bytes:
    components: list[Component] = []
    dependencies: list[Dependency] = []
    for index in range(MAX_COMPONENTS):
        component_id = 1000 + index
        kind = KIND_PLATFORM_FIRMWARE if index == 0 else KIND_DEVICE_FIRMWARE
        transport = TRANSPORT_UEFI_CAPSULE_ESRT if index == 0 else TRANSPORT_PLDM
        component = make_component(
            component_id,
            kind=kind,
            transport=transport,
            phase=index,
            dependency_start=len(dependencies),
            dependency_count=0 if index == 0 else 1,
            version_base=0xF113_0000 + index * 2,
        )
        if index:
            previous = components[-1]
            dependencies.append(
                Dependency(component_id, previous.component_id, previous.target_version)
            )
        components.append(component)
    return encode(components, dependencies, manifest_id="PFWM1-BOUNDARY-SYNTHETIC")


def summary(bundle: Bundle) -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "version": f"{MAJOR_VERSION}.{MINOR_VERSION}",
        "manifest_id": bundle.manifest_id,
        "manifest_version": bundle.manifest_version,
        "profile": "synthetic_qualification",
        "file_bytes": len(bundle.raw),
        "component_count": len(bundle.components),
        "dependency_count": len(bundle.dependencies),
        "external_payload_bytes": sum(item.external_payload_bytes for item in bundle.components),
        "maximum_transaction_components": bundle.maximum_transaction_components,
        "body_sha256": bundle.body_sha256,
        "file_sha256": sha256_bytes(bundle.raw),
    }


def development_activation_context(
    bundle: Bundle, *, outer_file_sha256: str | None = None
) -> ActivationContext:
    payload_digest = sha256_bytes(bundle.raw)
    file_digest = outer_file_sha256 or _digest("PFWM1/UNSIGNED-OUTER-FILE")
    observed = tuple(ObservedVersion(item.component_id, item.current_version) for item in bundle.components)
    return ActivationContext(
        outer_role=OUTER_ROLE_FIRMWARE_MANIFEST,
        outer_version=MAJOR_VERSION,
        outer_payload_sha256=payload_digest,
        outer_file_sha256=file_digest,
        expected_outer_file_sha256=file_digest,
        observed_versions=observed,
        staging_capacity_bytes=bundle.maximum_external_payload_bytes,
        battery_percent=100,
        outer_signature_verified=False,
        manifest_signature_verified=False,
        package_signature_verified=False,
        vendor_signatures_verified=False,
        target_profile_verified=False,
        hardware_inventory_observed=False,
        exact_device_identities_verified=False,
        current_versions_observed=False,
        transport_support_verified=False,
        firmware_service_inventory_verified=False,
        updater_plugins_verified=False,
        plugin_authority_granted=False,
        external_payloads_present=False,
        payload_digests_verified=False,
        license_policy_satisfied=False,
        redistribution_authorized=False,
        revocation_state_authenticated=False,
        no_components_revoked=False,
        anti_rollback_state_authenticated=False,
        recovery_ready=False,
        recovery_backup_verified=False,
        protected_staging_ready=False,
        stable_power=False,
        ac_power_present=False,
        transaction_journal_ready=False,
        quiescence_ready=False,
        storage_guard_ready=False,
        suspend_shutdown_guard_ready=False,
        reset_authorized=False,
        reboot_authorized=False,
        user_confirmed=False,
        physical_presence_verified=False,
        post_reset_verifier_ready=False,
        receipt_storage_ready=False,
        firmware_change_authorized=False,
        qualification_only=True,
        live_firmware_call_requested=False,
        driver_load_requested=False,
        physical_media_write_requested=False,
        firmware_mutation_requested=False,
    )


def synthetic_qualified_activation_context(bundle: Bundle) -> ActivationContext:
    context = development_activation_context(bundle)
    enabled = {
        field.name: True
        for field in dataclasses.fields(ActivationContext)
        if field.type == "bool" or field.type is bool
    }
    enabled.update(
        {
            "qualification_only": True,
            "live_firmware_call_requested": False,
            "driver_load_requested": False,
            "physical_media_write_requested": False,
            "firmware_mutation_requested": False,
        }
    )
    return dataclasses.replace(context, **enabled)


def _versions_match(bundle: Bundle, observed: Sequence[ObservedVersion]) -> bool:
    return len(observed) == len(bundle.components) and all(
        actual.component_id == expected.component_id and actual.version == expected.current_version
        for actual, expected in zip(observed, bundle.components, strict=True)
    )


def activation_errors(bundle: Bundle, context: ActivationContext) -> list[str]:
    checks = (
        (context.outer_signature_verified, "pfwm_activation_outer_signature"),
        (context.outer_role == OUTER_ROLE_FIRMWARE_MANIFEST, "pfwm_activation_outer_role"),
        (context.outer_version == bundle.manifest_version, "pfwm_activation_outer_version"),
        (context.outer_payload_sha256 == sha256_bytes(bundle.raw), "pfwm_activation_outer_payload_digest"),
        (
            context.outer_file_sha256 == context.expected_outer_file_sha256
            and len(context.outer_file_sha256) == 64,
            "pfwm_activation_outer_file_digest",
        ),
        (context.manifest_signature_verified, "pfwm_activation_manifest_signature"),
        (context.package_signature_verified, "pfwm_activation_package_signature"),
        (context.vendor_signatures_verified, "pfwm_activation_vendor_signature"),
        (context.target_profile_verified, "pfwm_activation_target_profile"),
        (context.hardware_inventory_observed, "pfwm_activation_hardware_inventory"),
        (context.exact_device_identities_verified, "pfwm_activation_device_identity"),
        (
            context.current_versions_observed and _versions_match(bundle, context.observed_versions),
            "pfwm_activation_current_versions",
        ),
        (context.transport_support_verified, "pfwm_activation_transport_support"),
        (context.firmware_service_inventory_verified, "pfwm_activation_firmware_services"),
        (context.updater_plugins_verified, "pfwm_activation_updater_plugins"),
        (context.plugin_authority_granted, "pfwm_activation_plugin_authority"),
        (context.external_payloads_present, "pfwm_activation_external_payloads"),
        (context.payload_digests_verified, "pfwm_activation_payload_digests"),
        (context.license_policy_satisfied, "pfwm_activation_license_policy"),
        (context.redistribution_authorized, "pfwm_activation_redistribution"),
        (context.revocation_state_authenticated, "pfwm_activation_revocation_state"),
        (context.no_components_revoked, "pfwm_activation_component_revoked"),
        (context.anti_rollback_state_authenticated, "pfwm_activation_anti_rollback"),
        (context.recovery_ready, "pfwm_activation_recovery"),
        (context.recovery_backup_verified, "pfwm_activation_recovery_backup"),
        (context.protected_staging_ready, "pfwm_activation_staging"),
        (
            context.staging_capacity_bytes
            >= sum(item.external_payload_bytes for item in bundle.components),
            "pfwm_activation_staging_capacity",
        ),
        (context.stable_power, "pfwm_activation_power"),
        (context.ac_power_present, "pfwm_activation_ac_power"),
        (context.battery_percent >= bundle.required_battery_percent, "pfwm_activation_battery"),
        (context.transaction_journal_ready, "pfwm_activation_transaction_journal"),
        (context.quiescence_ready, "pfwm_activation_quiescence"),
        (context.storage_guard_ready, "pfwm_activation_storage_guard"),
        (context.suspend_shutdown_guard_ready, "pfwm_activation_suspend_shutdown_guard"),
        (context.reset_authorized, "pfwm_activation_reset_authority"),
        (context.reboot_authorized, "pfwm_activation_reboot_authority"),
        (context.user_confirmed, "pfwm_activation_user_confirmation"),
        (context.physical_presence_verified, "pfwm_activation_physical_presence"),
        (context.post_reset_verifier_ready, "pfwm_activation_post_reset_verifier"),
        (context.receipt_storage_ready, "pfwm_activation_receipt_storage"),
        (context.firmware_change_authorized, "pfwm_activation_firmware_change_authority"),
        (context.qualification_only, "pfwm_activation_not_qualification_only"),
        (not context.live_firmware_call_requested, "pfwm_activation_live_firmware_call_requested"),
        (not context.driver_load_requested, "pfwm_activation_driver_load_requested"),
        (not context.physical_media_write_requested, "pfwm_activation_physical_media_write_requested"),
        (not context.firmware_mutation_requested, "pfwm_activation_firmware_mutation_requested"),
    )
    return [code for passed, code in checks if not passed]


def authorize_dry_run_plan(bundle: Bundle, context: ActivationContext) -> DryRunPlan:
    errors = activation_errors(bundle, context)
    if errors:
        raise FirmwareError(errors[0])
    return DryRunPlan(
        component_order=tuple(item.component_id for item in bundle.components),
        maximum_parallel_components=1,
        external_payload_bytes=sum(item.external_payload_bytes for item in bundle.components),
        reset_required=True,
        qualification_only=True,
    )


def synthetic_post_reset_records(bundle: Bundle) -> tuple[PostResetRecord, ...]:
    return tuple(
        PostResetRecord(
            component_id=item.component_id,
            resource_guid=item.resource_guid,
            hardware_instance=item.hardware_instance,
            observed_version=item.target_version,
            last_attempt_version=item.target_version,
            last_attempt_status=EXPECTED_LAST_ATTEMPT_SUCCESS,
            reenumerated=True,
            self_test_passed=True,
            recovery_intact=True,
            receipt_persisted=True,
            boot_loop_prevented=True,
            state_committed=True,
            driver_rebound_after_validation=True,
        )
        for item in bundle.components
    )


def post_reset_errors(
    bundle: Bundle,
    records: Sequence[PostResetRecord],
    *,
    qualification_only: bool,
) -> list[str]:
    errors: list[str] = []
    if not qualification_only:
        errors.append("pfwm_post_reset_not_qualification_only")
    if len(records) != len(bundle.components):
        errors.append("pfwm_post_reset_record_count")
        return errors
    for component, record in zip(bundle.components, records, strict=True):
        if record.component_id != component.component_id:
            errors.append("pfwm_post_reset_record_order")
        if record.resource_guid != component.resource_guid:
            errors.append("pfwm_post_reset_resource_identity")
        if record.hardware_instance != component.hardware_instance:
            errors.append("pfwm_post_reset_hardware_instance")
        if record.observed_version != component.target_version:
            errors.append("pfwm_post_reset_version")
        if record.last_attempt_version != component.target_version:
            errors.append("pfwm_post_reset_last_attempt_version")
        if record.last_attempt_status != EXPECTED_LAST_ATTEMPT_SUCCESS:
            errors.append("pfwm_post_reset_last_attempt_status")
        if not record.reenumerated:
            errors.append("pfwm_post_reset_reenumeration")
        if not record.self_test_passed:
            errors.append("pfwm_post_reset_self_test")
        if not record.recovery_intact:
            errors.append("pfwm_post_reset_recovery")
        if not record.receipt_persisted:
            errors.append("pfwm_post_reset_receipt")
        if not record.boot_loop_prevented:
            errors.append("pfwm_post_reset_boot_loop_guard")
        if not record.state_committed:
            errors.append("pfwm_post_reset_state_commit")
        if not record.driver_rebound_after_validation:
            errors.append("pfwm_post_reset_driver_rebind")
    return list(dict.fromkeys(errors))


def verify_post_reset(
    bundle: Bundle,
    records: Sequence[PostResetRecord],
    *,
    qualification_only: bool,
) -> None:
    errors = post_reset_errors(bundle, records, qualification_only=qualification_only)
    if errors:
        raise FirmwareError(errors[0])


def _vector(vector_id: str, data: bytes) -> dict[str, Any]:
    bundle = parse(data)
    return {
        "id": vector_id,
        "hex": data.hex().upper(),
        "sha256": sha256_bytes(data),
        "summary": summary(bundle),
    }


def make_golden_vectors() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_firmware_golden_vectors",
        "contract_id": CONTRACT_ID,
        "vectors": [
            _vector("canonical", canonical_bundle()),
            _vector("minimal", minimal_bundle()),
            _vector("boundary", boundary_bundle()),
        ],
    }


def _binding_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def implementation_bindings(root: Path = ROOT) -> list[dict[str, Any]]:
    return [_binding_record(root / relative) for relative in IMPLEMENTATION_INPUTS]


def expected_claims() -> dict[str, bool]:
    return {
        "allocation_free_no_std_parser": True,
        "exact_identity_and_version_floor_validation": True,
        "dependency_order_and_single_transaction_model": True,
        "dry_run_prerequisite_gating": True,
        "post_reset_receipt_validation": True,
        "synthetic_manifest_only": True,
        "external_payload_bytes_included": False,
        "live_fmp_or_esrt_inventory_observed": False,
        "uefi_capsule_submitted": False,
        "device_updater_driver_loaded": False,
        "vendor_payload_validated": False,
        "firmware_mutated": False,
        "physical_media_written": False,
        "production_apply_authority_created": False,
        "physical_hardware_qualified": False,
        "production_ready": False,
    }


def expected_contract(root: Path = ROOT) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_kind": "pooleos_native_firmware_contract",
        "contract_id": CONTRACT_ID,
        "version": {"major": MAJOR_VERSION, "minor": MINOR_VERSION},
        "profile": "synthetic_qualification_never_apply",
        "format": {
            "header_bytes": HEADER_BYTES,
            "component_record_bytes": COMPONENT_RECORD_BYTES,
            "dependency_record_bytes": DEPENDENCY_RECORD_BYTES,
            "tables_are_contiguous": True,
            "external_payload_bytes_embedded": False,
            "hardware_instance_bound_by_manifest_signature": True,
        },
        "limits": {
            "manifest_bytes": MAX_MANIFEST_BYTES,
            "components": MAX_COMPONENTS,
            "dependencies": MAX_DEPENDENCIES,
            "external_payload_bytes_per_component": MAX_EXTERNAL_PAYLOAD_BYTES,
            "maximum_transaction_components": 1,
            "apply_timeout_ms": MAX_APPLY_TIMEOUT_MS,
            "reset_timeout_ms": MAX_RESET_TIMEOUT_MS,
            "retry_limit": MAX_RETRY_LIMIT,
        },
        "header_flags": list(HEADER_FLAG_NAMES),
        "component_flags": list(COMPONENT_FLAG_NAMES),
        "transports": [
            "uefi_capsule_esrt_normalized",
            "exact_device_updater_plugin",
            "pldm_firmware_update_normalized",
        ],
        "activation_error_order": list(ACTIVATION_ERROR_ORDER),
        "post_reset_error_order": list(POST_RESET_ERROR_ORDER),
        "claims": expected_claims(),
        "non_claims": [
            "No live UEFI FMP, ESRT, capsule, or PLDM parser is implemented or invoked.",
            "No vendor firmware payload, updater driver, private key, or signature is included.",
            "No firmware service call, reset, driver load, device detach, or media write occurs.",
            "A valid parse or dry-run plan creates no production update authority.",
            "The canonical profile is synthetic and prohibited from applying to hardware.",
        ],
        "primary_references": [
            "https://uefi.org/specs/UEFI/2.11/23_Firmware_Update_and_Reporting.html",
            "https://csrc.nist.gov/pubs/sp/800/193/final",
            "https://www.dmtf.org/sites/default/files/standards/documents/DSP0267_1.3.0.pdf",
            "https://trustedcomputinggroup.org/resource/tcg-pc-client-reference-integrity-manifest-specification/",
        ],
        "implementation_bindings": implementation_bindings(root),
    }


def read_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _schema_errors(value: dict[str, Any], root: Path, relative: Path) -> list[str]:
    return validate_json(value, read_json(root / relative))


def contract_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, CONTRACT_SCHEMA_RELATIVE)
    if value != expected_contract(root):
        errors.append("PFWM1 contract differs from the implementation-derived contract")
    return errors


def golden_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, GOLDEN_SCHEMA_RELATIVE)
    if value != make_golden_vectors():
        errors.append("PFWM1 golden vectors differ from the canonical encoder")
    return errors


def _binding_matches(value: Any, root: Path) -> bool:
    if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
        return False
    path = root / str(value["path"])
    return path.is_file() and value == _binding_record(path)


def readiness_errors(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = _schema_errors(value, root, READINESS_SCHEMA_RELATIVE)
    if value.get("status") != "pass":
        errors.append("PFWM1 readiness status is not pass")
    if value.get("contract_id") != CONTRACT_ID:
        errors.append("PFWM1 readiness contract identifier changed")
    if value.get("claims") != expected_claims():
        errors.append("PFWM1 readiness claims changed")
    if value.get("production_ready") is not False:
        errors.append("PFWM1 readiness overclaims production readiness")
    if value.get("activation", {}).get("development_first_error") != "pfwm_activation_outer_signature":
        errors.append("PFWM1 development activation boundary changed")
    if value.get("activation", {}).get("production_apply_authority_created") is not False:
        errors.append("PFWM1 readiness created production apply authority")
    if value.get("payloads", {}).get("embedded_payload_count") != 0:
        errors.append("PFWM1 readiness unexpectedly embeds payload bytes")
    for binding in value.get("inputs", {}).values():
        if isinstance(binding, list):
            if not all(_binding_matches(item, root) for item in binding):
                errors.append("PFWM1 readiness has stale implementation bindings")
        elif not _binding_matches(binding, root):
            errors.append("PFWM1 readiness has a stale input binding")
    controls = value.get("negative_controls", [])
    if not controls or any(item.get("status") != "pass" for item in controls):
        errors.append("PFWM1 negative controls are incomplete or failing")
    differential = value.get("differential", {})
    for name in ("parser", "activation", "post_reset"):
        item = differential.get(name, {})
        if item.get("cases", 0) <= 0 or item.get("mismatches") != 0:
            errors.append(f"PFWM1 {name} differential evidence is incomplete")
    return errors
