"""Independent PINIT1 initial-system launch-bundle codec and validator."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("specs/native-initial-system-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-initial-system-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-initial-system-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-initial-system-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_initial_system_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-initial-system-readiness.schema.json")


CONTRACT_ID: Final = "PINIT1"
MAGIC: Final = b"PINIT1\0\0"
MAJOR_VERSION: Final = 1
MINOR_VERSION: Final = 0
HEADER_BYTES: Final = 192
RECORD_ALIGNMENT: Final = 8
COMPONENT_BYTES: Final = 80
SERVICE_BYTES: Final = 96
DEPENDENCY_BYTES: Final = 16
RESOURCE_BYTES: Final = 48
CAPABILITY_BYTES: Final = 48
MAX_BUNDLE_BYTES: Final = 1024 * 1024 - 96
MAX_COMPONENTS: Final = 32
MAX_SERVICES: Final = 32
MAX_DEPENDENCIES: Final = 128
MAX_RESOURCES: Final = 128
MAX_CAPABILITIES: Final = 256
MAX_STRING_BYTES: Final = 8192
MAX_NAME_BYTES: Final = 63
MAX_COMPONENT_BLOB_BYTES: Final = 512 * 1024
MAX_COMPONENT_IMAGE_BYTES: Final = 64 * 1024 * 1024

FLAG_TRANSACTIONAL_START: Final = 1 << 0
FLAG_REVERSE_ROLLBACK: Final = 1 << 1
FLAG_DEFAULT_DENY: Final = 1 << 2
FLAG_ROOT_DROPS_BOOTSTRAP: Final = 1 << 3
FLAG_OUTER_SIGNATURE_REQUIRED: Final = 1 << 4
FLAG_MANIFEST_SIGNATURE_REQUIRED: Final = 1 << 5
FLAG_ROLLBACK_STATE_REQUIRED: Final = 1 << 6
FLAG_COMPONENT_ABI_REQUIRED: Final = 1 << 7
REQUIRED_FLAGS: Final = (
    FLAG_TRANSACTIONAL_START
    | FLAG_REVERSE_ROLLBACK
    | FLAG_DEFAULT_DENY
    | FLAG_ROOT_DROPS_BOOTSTRAP
    | FLAG_OUTER_SIGNATURE_REQUIRED
    | FLAG_MANIFEST_SIGNATURE_REQUIRED
    | FLAG_ROLLBACK_STATE_REQUIRED
    | FLAG_COMPONENT_ABI_REQUIRED
)

BOOT_NORMAL: Final = 1 << 0
BOOT_SAFE: Final = 1 << 1
BOOT_PREVIOUS: Final = 1 << 2
BOOT_DIAGNOSTIC: Final = 1 << 3
KNOWN_BOOT_MODES: Final = BOOT_NORMAL | BOOT_SAFE | BOOT_PREVIOUS | BOOT_DIAGNOSTIC

COMPONENT_EXECUTABLE: Final = 1
COMPONENT_DATA: Final = 2
COMPONENT_REQUIRED: Final = 1 << 0
COMPONENT_READ_ONLY: Final = 1 << 1
COMPONENT_EXECUTABLE_FLAG: Final = 1 << 2
PXABI1: Final = b"PXABI1\0\0"
PINITD1: Final = b"PINITD1\0"

SERVICE_REQUIRED: Final = 1 << 0
SERVICE_CRITICAL: Final = 1 << 1
SERVICE_BOOTSTRAP: Final = 1 << 2
SERVICE_DROP_BOOTSTRAP: Final = 1 << 3
SERVICE_ALLOW_DEGRADED: Final = 1 << 4
SERVICE_STATELESS: Final = 1 << 5
SERVICE_KNOWN_FLAGS: Final = (
    SERVICE_REQUIRED
    | SERVICE_CRITICAL
    | SERVICE_BOOTSTRAP
    | SERVICE_DROP_BOOTSTRAP
    | SERVICE_ALLOW_DEGRADED
    | SERVICE_STATELESS
)

RESTART_NEVER: Final = 0
RESTART_ON_FAILURE: Final = 1
RESTART_ALWAYS: Final = 2
FAILURE_ROLLBACK_BUNDLE: Final = 1
FAILURE_CONTINUE_DEGRADED: Final = 2
READINESS_IMMEDIATE: Final = 0
READINESS_EXPLICIT: Final = 1
SHUTDOWN_REVERSE_DEPENDENCY: Final = 1

DEPENDENCY_STRONG: Final = 1
DEPENDENCY_WEAK: Final = 2

RESOURCE_MEMORY_PAGES: Final = 1
RESOURCE_THREAD_SLOTS: Final = 2
RESOURCE_ENDPOINT_SLOTS: Final = 3
RESOURCE_ADDRESS_SPACE: Final = 4
RESOURCE_LOG_SINK: Final = 5
RESOURCE_KINDS: Final = {
    RESOURCE_MEMORY_PAGES,
    RESOURCE_THREAD_SLOTS,
    RESOURCE_ENDPOINT_SLOTS,
    RESOURCE_ADDRESS_SPACE,
    RESOURCE_LOG_SINK,
}
RESOURCE_REQUIRED: Final = 1 << 0
RESOURCE_REVOCABLE: Final = 1 << 1
RESOURCE_ZERO_ON_REVOKE: Final = 1 << 2
RESOURCE_SHAREABLE: Final = 1 << 3
RESOURCE_EXCLUSIVE: Final = 1 << 4
RESOURCE_KNOWN_FLAGS: Final = (
    RESOURCE_REQUIRED
    | RESOURCE_REVOCABLE
    | RESOURCE_ZERO_ON_REVOKE
    | RESOURCE_SHAREABLE
    | RESOURCE_EXCLUSIVE
)
RESOURCE_MAXIMUMS: Final = {
    RESOURCE_MEMORY_PAGES: 65536,
    RESOURCE_THREAD_SLOTS: 1024,
    RESOURCE_ENDPOINT_SLOTS: 4096,
    RESOURCE_ADDRESS_SPACE: 1,
    RESOURCE_LOG_SINK: 1,
}

RIGHT_READ: Final = 1 << 0
RIGHT_WRITE: Final = 1 << 1
RIGHT_MAP_OR_BIND: Final = 1 << 2
RIGHT_MANAGE_OR_GRANT: Final = 1 << 3
RIGHT_EXECUTE: Final = 1 << 4
RESOURCE_RIGHTS: Final = {
    RESOURCE_MEMORY_PAGES: RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND | RIGHT_MANAGE_OR_GRANT,
    RESOURCE_THREAD_SLOTS: RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND | RIGHT_MANAGE_OR_GRANT,
    RESOURCE_ENDPOINT_SLOTS: RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND | RIGHT_MANAGE_OR_GRANT,
    RESOURCE_ADDRESS_SPACE: RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND,
    RESOURCE_LOG_SINK: RIGHT_WRITE,
}

CAP_REVOCABLE: Final = 1 << 0
CAP_DERIVABLE: Final = 1 << 1
CAP_TRANSFERABLE: Final = 1 << 2
CAP_LIFECYCLE_BOUND: Final = 1 << 3
CAP_KNOWN_FLAGS: Final = CAP_REVOCABLE | CAP_DERIVABLE | CAP_TRANSFERABLE | CAP_LIFECYCLE_BOUND
AVAILABILITY_REQUIRED: Final = 1
AVAILABILITY_OPTIONAL: Final = 2

NEGATIVE_CONTROL_IDS: Final = (
    "NEG-N5-PINIT1-EMPTY",
    "NEG-N5-PINIT1-TRUNCATED-HEADER",
    "NEG-N5-PINIT1-OVERSIZED",
    "NEG-N5-PINIT1-MAGIC",
    "NEG-N5-PINIT1-MAJOR-VERSION",
    "NEG-N5-PINIT1-MINOR-VERSION",
    "NEG-N5-PINIT1-HEADER-BYTES",
    "NEG-N5-PINIT1-ALIGNMENT",
    "NEG-N5-PINIT1-TOTAL-SIZE",
    "NEG-N5-PINIT1-FLAGS-MISSING",
    "NEG-N5-PINIT1-FLAGS-UNKNOWN",
    "NEG-N5-PINIT1-BUNDLE-VERSION-ZERO",
    "NEG-N5-PINIT1-SECURE-VERSION-ZERO",
    "NEG-N5-PINIT1-ROLLBACK-FLOOR",
    "NEG-N5-PINIT1-ROOT-ZERO",
    "NEG-N5-PINIT1-ROOT-OUT-OF-RANGE",
    "NEG-N5-PINIT1-BOOT-MODES-ZERO",
    "NEG-N5-PINIT1-BOOT-MODES-UNKNOWN",
    "NEG-N5-PINIT1-KERNEL-ABI-ZERO",
    "NEG-N5-PINIT1-PBP-ABI-ZERO",
    "NEG-N5-PINIT1-HEADER-RESERVED",
    "NEG-N5-PINIT1-COMPONENT-COUNT-ZERO",
    "NEG-N5-PINIT1-SERVICE-COUNT-HIGH",
    "NEG-N5-PINIT1-DEPENDENCY-COUNT-HIGH",
    "NEG-N5-PINIT1-RESOURCE-COUNT-ZERO",
    "NEG-N5-PINIT1-CAPABILITY-COUNT-ZERO",
    "NEG-N5-PINIT1-STRING-BYTES-ZERO",
    "NEG-N5-PINIT1-BLOB-BYTES-ZERO",
    "NEG-N5-PINIT1-BLOB-BYTES-HIGH",
    "NEG-N5-PINIT1-TABLE-OFFSET",
    "NEG-N5-PINIT1-BLOB-OFFSET",
    "NEG-N5-PINIT1-PADDING",
    "NEG-N5-PINIT1-BODY-DIGEST",
    "NEG-N5-PINIT1-COMPONENT-ID",
    "NEG-N5-PINIT1-COMPONENT-KIND",
    "NEG-N5-PINIT1-COMPONENT-FLAGS",
    "NEG-N5-PINIT1-COMPONENT-FORMAT",
    "NEG-N5-PINIT1-COMPONENT-IMAGE-SIZE",
    "NEG-N5-PINIT1-COMPONENT-ALIGNMENT-ZERO",
    "NEG-N5-PINIT1-COMPONENT-ALIGNMENT-NONPOWER",
    "NEG-N5-PINIT1-COMPONENT-BLOB-OFFSET",
    "NEG-N5-PINIT1-COMPONENT-BLOB-ZERO",
    "NEG-N5-PINIT1-COMPONENT-DIGEST",
    "NEG-N5-PINIT1-COMPONENT-RESERVED",
    "NEG-N5-PINIT1-COMPONENT-NAME",
    "NEG-N5-PINIT1-COMPONENT-NAME-DUPLICATE",
    "NEG-N5-PINIT1-STRING-TABLE",
    "NEG-N5-PINIT1-SERVICE-ID",
    "NEG-N5-PINIT1-SERVICE-COMPONENT",
    "NEG-N5-PINIT1-SERVICE-FLAGS-UNKNOWN",
    "NEG-N5-PINIT1-SERVICE-CRITICAL-OPTIONAL",
    "NEG-N5-PINIT1-SERVICE-REQUIRED-DEGRADED",
    "NEG-N5-PINIT1-SERVICE-START-TIMEOUT",
    "NEG-N5-PINIT1-SERVICE-STOP-TIMEOUT",
    "NEG-N5-PINIT1-SERVICE-RESTART-POLICY",
    "NEG-N5-PINIT1-SERVICE-RESTART-PARAMETERS",
    "NEG-N5-PINIT1-SERVICE-FAILURE-POLICY",
    "NEG-N5-PINIT1-SERVICE-REQUIRED-FAILURE",
    "NEG-N5-PINIT1-SERVICE-READINESS-POLICY",
    "NEG-N5-PINIT1-SERVICE-SHUTDOWN-POLICY",
    "NEG-N5-PINIT1-SERVICE-HEALTH-TIMEOUT",
    "NEG-N5-PINIT1-SERVICE-READY-RESOURCE",
    "NEG-N5-PINIT1-SERVICE-STATE-SCHEMA",
    "NEG-N5-PINIT1-SERVICE-RESERVED",
    "NEG-N5-PINIT1-DEPENDENCY-ORDER",
    "NEG-N5-PINIT1-DEPENDENCY-SELF",
    "NEG-N5-PINIT1-DEPENDENCY-KIND",
    "NEG-N5-PINIT1-DEPENDENCY-CYCLE",
    "NEG-N5-PINIT1-DEPENDENCY-REACHABILITY",
    "NEG-N5-PINIT1-DEPENDENCY-AVAILABILITY",
    "NEG-N5-PINIT1-STARTUP-RANK",
    "NEG-N5-PINIT1-RESOURCE-ID",
    "NEG-N5-PINIT1-RESOURCE-PROVIDER",
    "NEG-N5-PINIT1-RESOURCE-KIND",
    "NEG-N5-PINIT1-RESOURCE-FLAGS-UNKNOWN",
    "NEG-N5-PINIT1-RESOURCE-NOT-REVOCABLE",
    "NEG-N5-PINIT1-RESOURCE-SHARE-EXCLUSIVE",
    "NEG-N5-PINIT1-RESOURCE-ZERO-ON-ENDPOINT",
    "NEG-N5-PINIT1-RESOURCE-MINIMUM-ZERO",
    "NEG-N5-PINIT1-RESOURCE-MAXIMUM-LIMIT",
    "NEG-N5-PINIT1-RESOURCE-GENERATION",
    "NEG-N5-PINIT1-CAPABILITY-ID",
    "NEG-N5-PINIT1-CAPABILITY-PARENT-FORWARD",
    "NEG-N5-PINIT1-CAPABILITY-HOLDER",
    "NEG-N5-PINIT1-CAPABILITY-RESOURCE",
    "NEG-N5-PINIT1-CAPABILITY-RIGHTS-ZERO",
    "NEG-N5-PINIT1-CAPABILITY-RIGHTS-UNKNOWN",
    "NEG-N5-PINIT1-CAPABILITY-FLAGS-UNKNOWN",
    "NEG-N5-PINIT1-CAPABILITY-NOT-REVOCABLE",
    "NEG-N5-PINIT1-CAPABILITY-NOT-LIFECYCLE",
    "NEG-N5-PINIT1-CAPABILITY-REVOKE-GROUP",
    "NEG-N5-PINIT1-CAPABILITY-LEASE",
    "NEG-N5-PINIT1-CAPABILITY-DERIVATION-LIMIT",
    "NEG-N5-PINIT1-CAPABILITY-AVAILABILITY",
    "NEG-N5-PINIT1-CAPABILITY-SOURCE",
    "NEG-N5-PINIT1-CAPABILITY-ATTENUATION-RIGHTS",
    "NEG-N5-PINIT1-CAPABILITY-ATTENUATION-RESOURCE",
    "NEG-N5-PINIT1-CAPABILITY-REVOCATION",
    "NEG-N5-PINIT1-CAPABILITY-AVAILABILITY-UPGRADE",
    "NEG-N5-PINIT1-CAPABILITY-ROUTE",
    "NEG-N5-PINIT1-SERVICE-CAPABILITY-BUDGET",
    "NEG-N5-PINIT1-SERVICE-RESOURCE-BUDGET",
    "NEG-N5-PINIT1-SERVICE-DEPENDENCY-BUDGET",
    "NEG-N5-PINIT1-TOTAL-RESTART-BUDGET",
    "NEG-N5-PINIT1-ACTIVATION-DEVELOPMENT",
    "NEG-N5-PINIT1-ACTIVATION-ROLE",
    "NEG-N5-PINIT1-ACTIVATION-VERSION",
    "NEG-N5-PINIT1-ACTIVATION-PAYLOAD-DIGEST",
    "NEG-N5-PINIT1-ACTIVATION-FILE-DIGEST",
    "NEG-N5-PINIT1-ACTIVATION-OUTER-SIGNATURE",
    "NEG-N5-PINIT1-ACTIVATION-MANIFEST-SIGNATURE",
    "NEG-N5-PINIT1-ACTIVATION-ROLLBACK-STATE",
    "NEG-N5-PINIT1-ACTIVATION-ROLLBACK-FLOOR",
    "NEG-N5-PINIT1-ACTIVATION-KERNEL-ABI",
    "NEG-N5-PINIT1-ACTIVATION-PBP",
    "NEG-N5-PINIT1-ACTIVATION-BOOT-MODE",
    "NEG-N5-PINIT1-ACTIVATION-CAPABILITY-ALLOCATOR",
    "NEG-N5-PINIT1-ACTIVATION-RESOURCE-BROKER",
    "NEG-N5-PINIT1-ACTIVATION-COMPONENT-CONTRACTS",
    "NEG-N5-PINIT1-ACTIVATION-TRANSACTION-CAPACITY",
)

ACTIVATION_MODES: Final = (
    "development",
    "role",
    "version",
    "payload-digest",
    "file-digest",
    "outer-signature",
    "manifest-signature",
    "rollback-state",
    "rollback-floor",
    "kernel-abi",
    "pbp",
    "boot-mode",
    "capability-allocator",
    "resource-broker",
    "component-contracts",
    "transaction-capacity",
)

IMPLEMENTATION_INPUTS: Final = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/initsys/Cargo.toml",
    "native/initsys/src/lib.rs",
    "native/initsys/src/bin/pinit1_probe.rs",
    "runtime/native_initial_system.py",
    "runtime/native_boot_artifact.py",
    "tools/generate_native_initial_system_vectors.py",
    "tools/qualify_native_initial_system.py",
    "tests/test_native_initial_system.py",
    "docs/native-initial-system-bundle.md",
)


class InitialSystemError(RuntimeError):
    """Raised when bytes violate the PINIT1 contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Component:
    component_id: int
    kind: int
    flags: int
    name: str
    format_id: bytes
    blob: bytes
    image_bytes: int
    destination_alignment: int
    sha256: str = ""


@dataclasses.dataclass(frozen=True)
class Service:
    service_id: int
    component_id: int
    name: str
    flags: int
    startup_timeout_ms: int
    stop_timeout_ms: int
    restart_policy: int
    failure_policy: int
    readiness_policy: int
    shutdown_policy: int
    max_restarts: int
    restart_window_ms: int
    backoff_initial_ms: int
    backoff_max_ms: int
    health_timeout_ms: int
    ready_resource_id: int
    capability_count: int
    resource_count: int
    dependency_count: int
    startup_rank: int
    state_schema_version: int


@dataclasses.dataclass(frozen=True, order=True)
class Dependency:
    dependent_service_id: int
    prerequisite_service_id: int
    kind: int


@dataclasses.dataclass(frozen=True)
class Resource:
    resource_id: int
    provider_service_id: int
    name: str
    kind: int
    flags: int
    minimum: int
    maximum: int
    generation: int


@dataclasses.dataclass(frozen=True)
class Capability:
    capability_id: int
    parent_id: int
    holder_service_id: int
    resource_id: int
    rights: int
    flags: int
    revoke_group: int
    lease_ms: int
    max_derivations: int
    availability: int


@dataclasses.dataclass(frozen=True)
class Bundle:
    bundle_version: int
    minimum_secure_version: int
    root_service_id: int
    allowed_boot_modes: int
    required_kernel_abi_major: int
    minimum_kernel_abi_minor: int
    required_pbp_major: int
    minimum_pbp_minor: int
    start_timeout_ms: int
    rollback_timeout_ms: int
    max_total_restarts: int
    components: tuple[Component, ...]
    services: tuple[Service, ...]
    dependencies: tuple[Dependency, ...]
    resources: tuple[Resource, ...]
    capabilities: tuple[Capability, ...]
    start_order: tuple[int, ...]
    body_sha256: str
    raw: bytes


@dataclasses.dataclass(frozen=True)
class ActivationContext:
    outer_role: int
    outer_artifact_version: int
    outer_payload_digest_verified: bool
    outer_file_digest_verified: bool
    outer_signature_verified: bool
    manifest_signature_verified: bool
    rollback_state_authenticated: bool
    trusted_minimum_secure_version: int
    kernel_abi_major: int
    kernel_abi_minor: int
    pbp_major: int
    pbp_minor: int
    boot_mode: int
    capability_allocator_ready: bool
    resource_broker_ready: bool
    component_contracts_verified: bool
    transaction_capacity_verified: bool


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        _fail("pinit_json_object")
    return value


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        _fail("pinit_binding_escape")
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def _align(value: int, alignment: int = RECORD_ALIGNMENT) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _fail(code: str) -> None:
    raise InitialSystemError(code)


def _name_bytes(name: str) -> bytes:
    try:
        data = name.encode("ascii")
    except UnicodeEncodeError:
        _fail("pinit_name")
    if not data or len(data) > MAX_NAME_BYTES:
        _fail("pinit_name")
    if not (97 <= data[0] <= 122) or not (48 <= data[-1] <= 57 or 97 <= data[-1] <= 122):
        _fail("pinit_name")
    if any(not (48 <= byte <= 57 or 97 <= byte <= 122 or byte in b"._-") for byte in data):
        _fail("pinit_name")
    if b".." in data or b"/" in data or b"\\" in data:
        _fail("pinit_name")
    return data


def _read_name(table: bytes, offset: int, length: int) -> str:
    if length == 0 or length > MAX_NAME_BYTES or offset + length >= len(table):
        _fail("pinit_string_bounds")
    data = table[offset : offset + length]
    if table[offset + length] != 0:
        _fail("pinit_string_terminator")
    try:
        name = data.decode("ascii")
    except UnicodeDecodeError:
        _fail("pinit_name")
    if _name_bytes(name) != data:
        _fail("pinit_name")
    return name


def _bounded_count(value: int, minimum: int, maximum: int) -> None:
    if value < minimum or value > maximum:
        _fail("pinit_count")


def _table(data: bytes, offset: int, count: int, size: int) -> bytes:
    end = offset + count * size
    if offset < HEADER_BYTES or end > len(data):
        _fail("pinit_table_bounds")
    return data[offset:end]


def _parse_header(data: bytes) -> dict[str, int | bytes]:
    if len(data) < HEADER_BYTES:
        _fail("pinit_truncated")
    if len(data) > MAX_BUNDLE_BYTES:
        _fail("pinit_oversized")
    if data[:8] != MAGIC:
        _fail("pinit_magic")
    major, minor, header_bytes, alignment = struct.unpack_from("<HHHH", data, 8)
    if (major, minor) != (MAJOR_VERSION, MINOR_VERSION):
        _fail("pinit_version")
    if header_bytes != HEADER_BYTES or alignment != RECORD_ALIGNMENT:
        _fail("pinit_header_size")
    total_bytes, flags = struct.unpack_from("<II", data, 16)
    if total_bytes != len(data):
        _fail("pinit_total_size")
    if flags != REQUIRED_FLAGS:
        _fail("pinit_flags")
    values = struct.unpack_from("<QQIIHHHHHHHHHH", data, 24)
    (
        bundle_version,
        minimum_secure_version,
        root_service_id,
        allowed_boot_modes,
        kernel_major,
        kernel_minor,
        pbp_major,
        pbp_minor,
        component_count,
        service_count,
        dependency_count,
        resource_count,
        capability_count,
        reserved0,
    ) = values
    if bundle_version == 0 or minimum_secure_version == 0 or bundle_version < minimum_secure_version:
        _fail("pinit_version_floor")
    if root_service_id == 0:
        _fail("pinit_root_service")
    if allowed_boot_modes == 0 or allowed_boot_modes & ~KNOWN_BOOT_MODES:
        _fail("pinit_boot_modes")
    if kernel_major == 0 or pbp_major == 0:
        _fail("pinit_abi")
    if reserved0 != 0:
        _fail("pinit_reserved")
    _bounded_count(component_count, 1, MAX_COMPONENTS)
    _bounded_count(service_count, 1, MAX_SERVICES)
    _bounded_count(dependency_count, 0, MAX_DEPENDENCIES)
    _bounded_count(resource_count, 1, MAX_RESOURCES)
    _bounded_count(capability_count, 1, MAX_CAPABILITIES)
    offsets = struct.unpack_from("<IIIIIIIII", data, 68)
    (
        component_offset,
        service_offset,
        dependency_offset,
        resource_offset,
        capability_offset,
        string_offset,
        string_bytes,
        blob_offset,
        blob_bytes,
    ) = offsets
    start_timeout_ms, rollback_timeout_ms, max_total_restarts, reserved1 = struct.unpack_from(
        "<IIII", data, 104
    )
    if not (1 <= start_timeout_ms <= 300_000 and 1 <= rollback_timeout_ms <= 300_000):
        _fail("pinit_timeout")
    if max_total_restarts > 1024:
        _fail("pinit_lifecycle")
    if reserved1 != 0:
        _fail("pinit_reserved")
    if any(data[152:HEADER_BYTES]):
        _fail("pinit_reserved")
    if string_bytes == 0 or string_bytes > MAX_STRING_BYTES or blob_bytes == 0:
        _fail("pinit_table_size")
    if blob_bytes > MAX_COMPONENT_BLOB_BYTES:
        _fail("pinit_component_blob_size")
    expected_offsets = [
        HEADER_BYTES,
        HEADER_BYTES + component_count * COMPONENT_BYTES,
        HEADER_BYTES + component_count * COMPONENT_BYTES + service_count * SERVICE_BYTES,
    ]
    expected_offsets.append(expected_offsets[-1] + dependency_count * DEPENDENCY_BYTES)
    expected_offsets.append(expected_offsets[-1] + resource_count * RESOURCE_BYTES)
    expected_offsets.append(expected_offsets[-1] + capability_count * CAPABILITY_BYTES)
    expected_blob = _align(expected_offsets[-1] + string_bytes)
    if [component_offset, service_offset, dependency_offset, resource_offset, capability_offset, string_offset] != expected_offsets:
        _fail("pinit_table_layout")
    if blob_offset != expected_blob or blob_offset + blob_bytes != total_bytes:
        _fail("pinit_table_layout")
    if any(data[string_offset + string_bytes : blob_offset]):
        _fail("pinit_padding")
    body_digest = data[120:152]
    if hashlib.sha256(data[HEADER_BYTES:]).digest() != body_digest:
        _fail("pinit_body_digest")
    return {
        "bundle_version": bundle_version,
        "minimum_secure_version": minimum_secure_version,
        "root_service_id": root_service_id,
        "allowed_boot_modes": allowed_boot_modes,
        "kernel_major": kernel_major,
        "kernel_minor": kernel_minor,
        "pbp_major": pbp_major,
        "pbp_minor": pbp_minor,
        "component_count": component_count,
        "service_count": service_count,
        "dependency_count": dependency_count,
        "resource_count": resource_count,
        "capability_count": capability_count,
        "component_offset": component_offset,
        "service_offset": service_offset,
        "dependency_offset": dependency_offset,
        "resource_offset": resource_offset,
        "capability_offset": capability_offset,
        "string_offset": string_offset,
        "string_bytes": string_bytes,
        "blob_offset": blob_offset,
        "blob_bytes": blob_bytes,
        "start_timeout_ms": start_timeout_ms,
        "rollback_timeout_ms": rollback_timeout_ms,
        "max_total_restarts": max_total_restarts,
        "body_digest": body_digest,
    }


def _topological_order(
    service_ids: tuple[int, ...], dependencies: tuple[Dependency, ...]
) -> tuple[int, ...]:
    outgoing: dict[int, list[int]] = defaultdict(list)
    indegree = {service_id: 0 for service_id in service_ids}
    for dependency in dependencies:
        outgoing[dependency.prerequisite_service_id].append(dependency.dependent_service_id)
        indegree[dependency.dependent_service_id] += 1
    order: list[int] = []
    while len(order) < len(service_ids):
        ready = min((service_id for service_id in service_ids if indegree[service_id] == 0 and service_id not in order), default=0)
        if ready == 0:
            _fail("pinit_dependency_cycle")
        order.append(ready)
        for dependent in outgoing[ready]:
            indegree[dependent] -= 1
    return tuple(order)


def parse(data: bytes) -> Bundle:
    header = _parse_header(data)
    string_offset = int(header["string_offset"])
    string_table = data[string_offset : string_offset + int(header["string_bytes"])]
    blob_offset = int(header["blob_offset"])
    blob = data[blob_offset : blob_offset + int(header["blob_bytes"])]
    referenced_names: set[str] = set()

    components: list[Component] = []
    expected_blob_offset = 0
    component_table = _table(data, int(header["component_offset"]), int(header["component_count"]), COMPONENT_BYTES)
    for index in range(int(header["component_count"])):
        record = component_table[index * COMPONENT_BYTES : (index + 1) * COMPONENT_BYTES]
        component_id, kind, flags, name_offset, name_bytes, reserved = struct.unpack_from("<IHHIHH", record, 0)
        format_id = record[16:24]
        relative_offset, blob_bytes, image_bytes, destination_alignment = struct.unpack_from("<IIII", record, 24)
        digest = record[40:72]
        if component_id != index + 1 or reserved != 0 or any(record[72:]):
            _fail("pinit_component_record")
        if kind == COMPONENT_EXECUTABLE:
            if flags != COMPONENT_REQUIRED | COMPONENT_READ_ONLY | COMPONENT_EXECUTABLE_FLAG or format_id != PXABI1:
                _fail("pinit_component_kind")
            if image_bytes == 0 or image_bytes > MAX_COMPONENT_IMAGE_BYTES:
                _fail("pinit_component_image_size")
        elif kind == COMPONENT_DATA:
            if flags != COMPONENT_REQUIRED | COMPONENT_READ_ONLY or format_id != PINITD1 or image_bytes != 0:
                _fail("pinit_component_kind")
        else:
            _fail("pinit_component_kind")
        if destination_alignment == 0 or destination_alignment > 4096 or destination_alignment & (destination_alignment - 1):
            _fail("pinit_component_alignment")
        expected_blob_offset = _align(expected_blob_offset)
        if relative_offset != expected_blob_offset or blob_bytes == 0 or relative_offset + blob_bytes > len(blob):
            _fail("pinit_component_blob_bounds")
        component_blob = blob[relative_offset : relative_offset + blob_bytes]
        if hashlib.sha256(component_blob).digest() != digest:
            _fail("pinit_component_digest")
        name = _read_name(string_table, name_offset, name_bytes)
        if name in referenced_names:
            _fail("pinit_name_duplicate")
        referenced_names.add(name)
        components.append(
            Component(
                component_id,
                kind,
                flags,
                name,
                format_id,
                component_blob,
                image_bytes,
                destination_alignment,
                digest.hex().upper(),
            )
        )
        expected_blob_offset += blob_bytes
        next_offset = _align(expected_blob_offset)
        if any(blob[expected_blob_offset:next_offset]):
            _fail("pinit_padding")
    if expected_blob_offset != len(blob):
        _fail("pinit_component_blob_bounds")

    services: list[Service] = []
    service_table = _table(data, int(header["service_offset"]), int(header["service_count"]), SERVICE_BYTES)
    for index in range(int(header["service_count"])):
        record = service_table[index * SERVICE_BYTES : (index + 1) * SERVICE_BYTES]
        service_id, component_id, name_offset, name_bytes, flags = struct.unpack_from("<IIIHH", record, 0)
        timings = struct.unpack_from("<IIHHHHIIIIIIHHHHI", record, 16)
        (
            startup_timeout_ms,
            stop_timeout_ms,
            restart_policy,
            failure_policy,
            readiness_policy,
            shutdown_policy,
            max_restarts,
            restart_window_ms,
            backoff_initial_ms,
            backoff_max_ms,
            health_timeout_ms,
            ready_resource_id,
            capability_count,
            resource_count,
            dependency_count,
            startup_rank,
            state_schema_version,
        ) = timings
        if (
            service_id != index + 1
            or component_id == 0
            or component_id > len(components)
            or components[component_id - 1].kind != COMPONENT_EXECUTABLE
            or any(record[68:])
        ):
            _fail("pinit_service_record")
        if flags & ~SERVICE_KNOWN_FLAGS:
            _fail("pinit_service_flags")
        required = bool(flags & SERVICE_REQUIRED)
        critical = bool(flags & SERVICE_CRITICAL)
        degraded = bool(flags & SERVICE_ALLOW_DEGRADED)
        stateless = bool(flags & SERVICE_STATELESS)
        if critical and not required or required and degraded:
            _fail("pinit_service_flags")
        if not (1 <= startup_timeout_ms <= int(header["start_timeout_ms"])) or not (
            1 <= stop_timeout_ms <= int(header["rollback_timeout_ms"])
        ):
            _fail("pinit_timeout")
        if restart_policy not in (RESTART_NEVER, RESTART_ON_FAILURE, RESTART_ALWAYS):
            _fail("pinit_restart_policy")
        if failure_policy not in (FAILURE_ROLLBACK_BUNDLE, FAILURE_CONTINUE_DEGRADED):
            _fail("pinit_failure_policy")
        if readiness_policy not in (READINESS_IMMEDIATE, READINESS_EXPLICIT) or shutdown_policy != SHUTDOWN_REVERSE_DEPENDENCY:
            _fail("pinit_lifecycle")
        if required and failure_policy != FAILURE_ROLLBACK_BUNDLE or not required and failure_policy != FAILURE_CONTINUE_DEGRADED:
            _fail("pinit_failure_policy")
        if restart_policy == RESTART_NEVER:
            if any((max_restarts, restart_window_ms, backoff_initial_ms, backoff_max_ms)):
                _fail("pinit_restart_policy")
        elif not (
            1 <= max_restarts <= 64
            and 1 <= backoff_initial_ms <= backoff_max_ms <= restart_window_ms <= 3_600_000
        ):
            _fail("pinit_restart_policy")
        if not (1 <= health_timeout_ms <= startup_timeout_ms):
            _fail("pinit_health_policy")
        if readiness_policy == READINESS_EXPLICIT and ready_resource_id == 0:
            _fail("pinit_health_policy")
        if stateless != (state_schema_version == 0):
            _fail("pinit_state_schema")
        name = _read_name(string_table, name_offset, name_bytes)
        if name in referenced_names:
            _fail("pinit_name_duplicate")
        referenced_names.add(name)
        services.append(
            Service(
                service_id,
                component_id,
                name,
                flags,
                startup_timeout_ms,
                stop_timeout_ms,
                restart_policy,
                failure_policy,
                readiness_policy,
                shutdown_policy,
                max_restarts,
                restart_window_ms,
                backoff_initial_ms,
                backoff_max_ms,
                health_timeout_ms,
                ready_resource_id,
                capability_count,
                resource_count,
                dependency_count,
                startup_rank,
                state_schema_version,
            )
        )

    dependencies: list[Dependency] = []
    dependency_table = _table(data, int(header["dependency_offset"]), int(header["dependency_count"]), DEPENDENCY_BYTES)
    previous_pair = (0, 0)
    for index in range(int(header["dependency_count"])):
        record = dependency_table[index * DEPENDENCY_BYTES : (index + 1) * DEPENDENCY_BYTES]
        dependent, prerequisite, kind, flags, reserved = struct.unpack_from("<IIHHI", record)
        pair = (dependent, prerequisite)
        if pair <= previous_pair or dependent == prerequisite or not (1 <= dependent <= len(services)) or not (1 <= prerequisite <= len(services)):
            _fail("pinit_dependency_record")
        if kind not in (DEPENDENCY_STRONG, DEPENDENCY_WEAK) or flags != 0 or reserved != 0:
            _fail("pinit_dependency_kind")
        dependencies.append(Dependency(dependent, prerequisite, kind))
        previous_pair = pair

    resources: list[Resource] = []
    resource_table = _table(data, int(header["resource_offset"]), int(header["resource_count"]), RESOURCE_BYTES)
    for index in range(int(header["resource_count"])):
        record = resource_table[index * RESOURCE_BYTES : (index + 1) * RESOURCE_BYTES]
        resource_id, provider, name_offset, name_bytes, kind, flags, reserved = struct.unpack_from("<IIIHHII", record, 0)
        minimum, maximum, generation, reserved2 = struct.unpack_from("<QQII", record, 24)
        if resource_id != index + 1 or provider > len(services) or kind not in RESOURCE_KINDS or reserved or reserved2:
            _fail("pinit_resource_record")
        if flags & ~RESOURCE_KNOWN_FLAGS or not flags & RESOURCE_REVOCABLE:
            _fail("pinit_resource_flags")
        if bool(flags & RESOURCE_SHAREABLE) == bool(flags & RESOURCE_EXCLUSIVE):
            _fail("pinit_resource_flags")
        if kind != RESOURCE_MEMORY_PAGES and flags & RESOURCE_ZERO_ON_REVOKE:
            _fail("pinit_resource_flags")
        if minimum == 0 or minimum > maximum or maximum > RESOURCE_MAXIMUMS[kind] or generation == 0:
            _fail("pinit_resource_bounds")
        if kind in (RESOURCE_ADDRESS_SPACE, RESOURCE_LOG_SINK) and (minimum, maximum) != (1, 1):
            _fail("pinit_resource_bounds")
        name = _read_name(string_table, name_offset, name_bytes)
        if name in referenced_names:
            _fail("pinit_name_duplicate")
        referenced_names.add(name)
        resources.append(Resource(resource_id, provider, name, kind, flags, minimum, maximum, generation))

    capabilities: list[Capability] = []
    capability_table = _table(data, int(header["capability_offset"]), int(header["capability_count"]), CAPABILITY_BYTES)
    for index in range(int(header["capability_count"])):
        record = capability_table[index * CAPABILITY_BYTES : (index + 1) * CAPABILITY_BYTES]
        capability_id, parent_id, holder, resource_id = struct.unpack_from("<IIII", record, 0)
        rights, flags, revoke_group, lease_ms, max_derivations, availability = struct.unpack_from("<QIIIHH", record, 16)
        if capability_id != index + 1 or holder == 0 or holder > len(services) or resource_id == 0 or resource_id > len(resources) or any(record[40:]):
            _fail("pinit_capability_record")
        if parent_id >= capability_id:
            _fail("pinit_capability_parent")
        if rights == 0 or rights & ~RESOURCE_RIGHTS[resources[resource_id - 1].kind]:
            _fail("pinit_capability_rights")
        if flags & ~CAP_KNOWN_FLAGS or flags & (CAP_REVOCABLE | CAP_LIFECYCLE_BOUND) != CAP_REVOCABLE | CAP_LIFECYCLE_BOUND:
            _fail("pinit_capability_flags")
        if revoke_group == 0 or lease_ms != 0 or max_derivations > MAX_CAPABILITIES:
            _fail("pinit_capability_lifecycle")
        if availability not in (AVAILABILITY_REQUIRED, AVAILABILITY_OPTIONAL):
            _fail("pinit_capability_availability")
        resource = resources[resource_id - 1]
        if parent_id == 0:
            if holder not in (int(header["root_service_id"]), resource.provider_service_id) or (
                resource.provider_service_id == 0 and holder != int(header["root_service_id"])
            ):
                _fail("pinit_capability_source")
        else:
            parent = capabilities[parent_id - 1]
            if not parent.flags & CAP_DERIVABLE or parent.resource_id != resource_id or rights & ~parent.rights:
                _fail("pinit_capability_attenuation")
            if revoke_group != parent.revoke_group:
                _fail("pinit_capability_revocation")
            if availability == AVAILABILITY_REQUIRED and parent.availability != AVAILABILITY_REQUIRED:
                _fail("pinit_capability_availability")
        capabilities.append(
            Capability(
                capability_id,
                parent_id,
                holder,
                resource_id,
                rights,
                flags,
                revoke_group,
                lease_ms,
                max_derivations,
                availability,
            )
        )

    canonical_strings = b"".join(_name_bytes(name) + b"\0" for name in sorted(referenced_names))
    if string_table != canonical_strings:
        _fail("pinit_string_table")

    root = services[int(header["root_service_id"]) - 1] if int(header["root_service_id"]) <= len(services) else None
    root_flags = SERVICE_REQUIRED | SERVICE_CRITICAL | SERVICE_BOOTSTRAP | SERVICE_DROP_BOOTSTRAP | SERVICE_STATELESS
    if root is None or root.flags != root_flags or root.restart_policy != RESTART_NEVER:
        _fail("pinit_root_service")
    if any(service.service_id != root.service_id and service.flags & (SERVICE_BOOTSTRAP | SERVICE_DROP_BOOTSTRAP) for service in services):
        _fail("pinit_root_service")
    if any(dependency.dependent_service_id == root.service_id for dependency in dependencies):
        _fail("pinit_root_service")

    start_order = _topological_order(tuple(service.service_id for service in services), tuple(dependencies))
    ranks = {service_id: index for index, service_id in enumerate(start_order)}
    if any(service.startup_rank != ranks[service.service_id] for service in services):
        _fail("pinit_startup_rank")
    strong_reachable = {root.service_id}
    changed = True
    while changed:
        changed = False
        for dependency in dependencies:
            if dependency.kind == DEPENDENCY_STRONG and dependency.prerequisite_service_id in strong_reachable and dependency.dependent_service_id not in strong_reachable:
                strong_reachable.add(dependency.dependent_service_id)
                changed = True
    if strong_reachable != {service.service_id for service in services}:
        _fail("pinit_dependency_reachability")
    for dependency in dependencies:
        dependent = services[dependency.dependent_service_id - 1]
        prerequisite = services[dependency.prerequisite_service_id - 1]
        if dependency.kind == DEPENDENCY_STRONG and dependent.flags & SERVICE_REQUIRED and not prerequisite.flags & SERVICE_REQUIRED:
            _fail("pinit_dependency_availability")

    dependency_pairs = {(item.dependent_service_id, item.prerequisite_service_id) for item in dependencies}
    resource_ids = {resource.resource_id for resource in resources}
    for service in services:
        held = [capability for capability in capabilities if capability.holder_service_id == service.service_id]
        held_resources = {capability.resource_id for capability in held}
        incoming = [dependency for dependency in dependencies if dependency.dependent_service_id == service.service_id]
        if (service.capability_count, service.resource_count, service.dependency_count) != (
            len(held),
            len(held_resources),
            len(incoming),
        ):
            _fail("pinit_service_budget")
        if service.ready_resource_id not in resource_ids or resources[service.ready_resource_id - 1].kind != RESOURCE_ENDPOINT_SLOTS:
            _fail("pinit_health_policy")
    for capability in capabilities:
        resource = resources[capability.resource_id - 1]
        provider = resource.provider_service_id
        if provider and provider != capability.holder_service_id:
            if (capability.holder_service_id, provider) not in dependency_pairs or ranks[provider] >= ranks[capability.holder_service_id]:
                _fail("pinit_capability_route")
    if sum(service.max_restarts for service in services) != int(header["max_total_restarts"]):
        _fail("pinit_lifecycle")

    return Bundle(
        int(header["bundle_version"]),
        int(header["minimum_secure_version"]),
        int(header["root_service_id"]),
        int(header["allowed_boot_modes"]),
        int(header["kernel_major"]),
        int(header["kernel_minor"]),
        int(header["pbp_major"]),
        int(header["pbp_minor"]),
        int(header["start_timeout_ms"]),
        int(header["rollback_timeout_ms"]),
        int(header["max_total_restarts"]),
        tuple(components),
        tuple(services),
        tuple(dependencies),
        tuple(resources),
        tuple(capabilities),
        start_order,
        bytes(header["body_digest"]).hex().upper(),
        data,
    )


def _pack_name_map(names: Iterable[str]) -> tuple[bytes, dict[str, tuple[int, int]]]:
    table = bytearray()
    mapping: dict[str, tuple[int, int]] = {}
    for name in sorted(set(names)):
        encoded = _name_bytes(name)
        mapping[name] = (len(table), len(encoded))
        table.extend(encoded)
        table.append(0)
    if not table or len(table) > MAX_STRING_BYTES:
        _fail("pinit_string_table")
    return bytes(table), mapping


def encode(
    *,
    bundle_version: int,
    minimum_secure_version: int,
    root_service_id: int,
    allowed_boot_modes: int,
    required_kernel_abi_major: int,
    minimum_kernel_abi_minor: int,
    required_pbp_major: int,
    minimum_pbp_minor: int,
    start_timeout_ms: int,
    rollback_timeout_ms: int,
    max_total_restarts: int,
    components: Iterable[Component],
    services: Iterable[Service],
    dependencies: Iterable[Dependency],
    resources: Iterable[Resource],
    capabilities: Iterable[Capability],
) -> bytes:
    components = tuple(components)
    services = tuple(services)
    dependencies = tuple(dependencies)
    resources = tuple(resources)
    capabilities = tuple(capabilities)
    strings, name_map = _pack_name_map(
        [item.name for item in components] + [item.name for item in services] + [item.name for item in resources]
    )
    component_table = bytearray()
    blob = bytearray()
    for item in components:
        while len(blob) % RECORD_ALIGNMENT:
            blob.append(0)
        relative_offset = len(blob)
        blob.extend(item.blob)
        name_offset, name_bytes = name_map[item.name]
        record = bytearray(COMPONENT_BYTES)
        struct.pack_into("<IHHIHH", record, 0, item.component_id, item.kind, item.flags, name_offset, name_bytes, 0)
        record[16:24] = item.format_id
        struct.pack_into("<IIII", record, 24, relative_offset, len(item.blob), item.image_bytes, item.destination_alignment)
        record[40:72] = hashlib.sha256(item.blob).digest()
        component_table.extend(record)
    service_table = bytearray()
    for item in services:
        name_offset, name_bytes = name_map[item.name]
        record = bytearray(SERVICE_BYTES)
        struct.pack_into("<IIIHH", record, 0, item.service_id, item.component_id, name_offset, name_bytes, item.flags)
        struct.pack_into(
            "<IIHHHHIIIIIIHHHHI",
            record,
            16,
            item.startup_timeout_ms,
            item.stop_timeout_ms,
            item.restart_policy,
            item.failure_policy,
            item.readiness_policy,
            item.shutdown_policy,
            item.max_restarts,
            item.restart_window_ms,
            item.backoff_initial_ms,
            item.backoff_max_ms,
            item.health_timeout_ms,
            item.ready_resource_id,
            item.capability_count,
            item.resource_count,
            item.dependency_count,
            item.startup_rank,
            item.state_schema_version,
        )
        service_table.extend(record)
    dependency_table = bytearray()
    for item in dependencies:
        dependency_table.extend(struct.pack("<IIHHI", item.dependent_service_id, item.prerequisite_service_id, item.kind, 0, 0))
    resource_table = bytearray()
    for item in resources:
        name_offset, name_bytes = name_map[item.name]
        resource_table.extend(
            struct.pack(
                "<IIIHHIIQQII",
                item.resource_id,
                item.provider_service_id,
                name_offset,
                name_bytes,
                item.kind,
                item.flags,
                0,
                item.minimum,
                item.maximum,
                item.generation,
                0,
            )
        )
    capability_table = bytearray()
    for item in capabilities:
        record = bytearray(CAPABILITY_BYTES)
        struct.pack_into(
            "<IIIIQIIIHH",
            record,
            0,
            item.capability_id,
            item.parent_id,
            item.holder_service_id,
            item.resource_id,
            item.rights,
            item.flags,
            item.revoke_group,
            item.lease_ms,
            item.max_derivations,
            item.availability,
        )
        capability_table.extend(record)
    body = bytearray(component_table + service_table + dependency_table + resource_table + capability_table + strings)
    while (HEADER_BYTES + len(body)) % RECORD_ALIGNMENT:
        body.append(0)
    body.extend(blob)
    total_bytes = HEADER_BYTES + len(body)
    if total_bytes > MAX_BUNDLE_BYTES:
        _fail("pinit_oversized")
    component_offset = HEADER_BYTES
    service_offset = component_offset + len(component_table)
    dependency_offset = service_offset + len(service_table)
    resource_offset = dependency_offset + len(dependency_table)
    capability_offset = resource_offset + len(resource_table)
    string_offset = capability_offset + len(capability_table)
    blob_offset = _align(string_offset + len(strings))
    header = bytearray(HEADER_BYTES)
    header[:8] = MAGIC
    struct.pack_into("<HHHHII", header, 8, MAJOR_VERSION, MINOR_VERSION, HEADER_BYTES, RECORD_ALIGNMENT, total_bytes, REQUIRED_FLAGS)
    struct.pack_into(
        "<QQIIHHHHHHHHHH",
        header,
        24,
        bundle_version,
        minimum_secure_version,
        root_service_id,
        allowed_boot_modes,
        required_kernel_abi_major,
        minimum_kernel_abi_minor,
        required_pbp_major,
        minimum_pbp_minor,
        len(components),
        len(services),
        len(dependencies),
        len(resources),
        len(capabilities),
        0,
    )
    struct.pack_into(
        "<IIIIIIIII",
        header,
        68,
        component_offset,
        service_offset,
        dependency_offset,
        resource_offset,
        capability_offset,
        string_offset,
        len(strings),
        blob_offset,
        len(blob),
    )
    struct.pack_into("<IIII", header, 104, start_timeout_ms, rollback_timeout_ms, max_total_restarts, 0)
    header[120:152] = hashlib.sha256(body).digest()
    encoded = bytes(header + body)
    parse(encoded)
    return encoded


def canonical_bundle() -> bytes:
    components = (
        Component(1, COMPONENT_EXECUTABLE, 7, "poole.init", PXABI1, b"PooleOS PINIT1 candidate init component\n", 4096, 4096),
        Component(2, COMPONENT_EXECUTABLE, 7, "poole.log", PXABI1, b"PooleOS PINIT1 candidate log component\n", 4096, 4096),
        Component(3, COMPONENT_EXECUTABLE, 7, "poole.resource", PXABI1, b"PooleOS PINIT1 candidate resource component\n", 4096, 4096),
    )
    services = (
        Service(1, 1, "service.init", 47, 1000, 1000, RESTART_NEVER, FAILURE_ROLLBACK_BUNDLE, READINESS_EXPLICIT, SHUTDOWN_REVERSE_DEPENDENCY, 0, 0, 0, 0, 500, 3, 3, 3, 0, 0, 0),
        Service(2, 2, "service.log", SERVICE_ALLOW_DEGRADED | SERVICE_STATELESS, 2000, 1000, RESTART_ON_FAILURE, FAILURE_CONTINUE_DEGRADED, READINESS_EXPLICIT, SHUTDOWN_REVERSE_DEPENDENCY, 3, 60_000, 100, 5000, 1000, 3, 4, 4, 1, 1, 0),
        Service(3, 3, "service.resource", SERVICE_REQUIRED | SERVICE_CRITICAL, 3000, 2000, RESTART_ON_FAILURE, FAILURE_ROLLBACK_BUNDLE, READINESS_EXPLICIT, SHUTDOWN_REVERSE_DEPENDENCY, 3, 60_000, 100, 5000, 1000, 3, 4, 4, 2, 2, 1),
    )
    dependencies = (
        Dependency(2, 1, DEPENDENCY_STRONG),
        Dependency(3, 1, DEPENDENCY_STRONG),
        Dependency(3, 2, DEPENDENCY_WEAK),
    )
    resources = (
        Resource(1, 0, "bootstrap.memory", RESOURCE_MEMORY_PAGES, RESOURCE_REQUIRED | RESOURCE_REVOCABLE | RESOURCE_ZERO_ON_REVOKE | RESOURCE_EXCLUSIVE, 64, 256, 1),
        Resource(2, 0, "bootstrap.threads", RESOURCE_THREAD_SLOTS, RESOURCE_REQUIRED | RESOURCE_REVOCABLE | RESOURCE_EXCLUSIVE, 3, 16, 1),
        Resource(3, 0, "bootstrap.endpoints", RESOURCE_ENDPOINT_SLOTS, RESOURCE_REQUIRED | RESOURCE_REVOCABLE | RESOURCE_EXCLUSIVE, 3, 32, 1),
        Resource(4, 2, "service.log.sink", RESOURCE_LOG_SINK, RESOURCE_REVOCABLE | RESOURCE_SHAREABLE, 1, 1, 1),
    )
    source_flags = CAP_REVOCABLE | CAP_DERIVABLE | CAP_LIFECYCLE_BOUND
    child_flags = CAP_REVOCABLE | CAP_LIFECYCLE_BOUND
    capabilities = (
        Capability(1, 0, 1, 1, 15, source_flags, 1, 0, 8, AVAILABILITY_REQUIRED),
        Capability(2, 0, 1, 2, 15, source_flags, 2, 0, 8, AVAILABILITY_REQUIRED),
        Capability(3, 0, 1, 3, 15, source_flags, 3, 0, 8, AVAILABILITY_REQUIRED),
        Capability(4, 1, 2, 1, 7, child_flags, 1, 0, 0, AVAILABILITY_REQUIRED),
        Capability(5, 1, 3, 1, 7, child_flags, 1, 0, 0, AVAILABILITY_REQUIRED),
        Capability(6, 2, 2, 2, 14, child_flags, 2, 0, 0, AVAILABILITY_REQUIRED),
        Capability(7, 2, 3, 2, 14, child_flags, 2, 0, 0, AVAILABILITY_REQUIRED),
        Capability(8, 3, 2, 3, 7, child_flags, 3, 0, 0, AVAILABILITY_REQUIRED),
        Capability(9, 3, 3, 3, 7, child_flags, 3, 0, 0, AVAILABILITY_REQUIRED),
        Capability(10, 0, 2, 4, RIGHT_WRITE, source_flags, 4, 0, 2, AVAILABILITY_OPTIONAL),
        Capability(11, 10, 3, 4, RIGHT_WRITE, child_flags, 4, 0, 0, AVAILABILITY_OPTIONAL),
    )
    return encode(
        bundle_version=1,
        minimum_secure_version=1,
        root_service_id=1,
        allowed_boot_modes=BOOT_NORMAL | BOOT_SAFE | BOOT_PREVIOUS,
        required_kernel_abi_major=1,
        minimum_kernel_abi_minor=0,
        required_pbp_major=1,
        minimum_pbp_minor=0,
        start_timeout_ms=10_000,
        rollback_timeout_ms=10_000,
        max_total_restarts=6,
        components=components,
        services=services,
        dependencies=dependencies,
        resources=resources,
        capabilities=capabilities,
    )


def summary(bundle: Bundle) -> str:
    order = ",".join(str(value) for value in bundle.start_order)
    return (
        f"OK;version={bundle.bundle_version};minimum_secure_version={bundle.minimum_secure_version};"
        f"components={len(bundle.components)};services={len(bundle.services)};"
        f"dependencies={len(bundle.dependencies)};resources={len(bundle.resources)};"
        f"capabilities={len(bundle.capabilities)};root={bundle.root_service_id};"
        f"start_order={order};body_sha256={bundle.body_sha256}"
    )


def parse_result(data: bytes) -> str:
    try:
        return summary(parse(data))
    except InitialSystemError as error:
        return f"ERR:{error.code}"


def activation_errors(bundle: Bundle, context: ActivationContext) -> tuple[str, ...]:
    errors: list[str] = []
    if context.outer_role != 2:
        errors.append("pinit_activation_role")
    if context.outer_artifact_version != bundle.bundle_version:
        errors.append("pinit_activation_version")
    for name in (
        "outer_payload_digest_verified",
        "outer_file_digest_verified",
        "outer_signature_verified",
        "manifest_signature_verified",
        "rollback_state_authenticated",
        "capability_allocator_ready",
        "resource_broker_ready",
        "component_contracts_verified",
        "transaction_capacity_verified",
    ):
        if not getattr(context, name):
            errors.append(f"pinit_activation_{name}")
    if context.trusted_minimum_secure_version > bundle.bundle_version or bundle.bundle_version < bundle.minimum_secure_version:
        errors.append("pinit_activation_rollback")
    if context.kernel_abi_major != bundle.required_kernel_abi_major or context.kernel_abi_minor < bundle.minimum_kernel_abi_minor:
        errors.append("pinit_activation_kernel_abi")
    if context.pbp_major != bundle.required_pbp_major or context.pbp_minor < bundle.minimum_pbp_minor:
        errors.append("pinit_activation_pbp")
    if context.boot_mode == 0 or context.boot_mode & (context.boot_mode - 1) or not bundle.allowed_boot_modes & context.boot_mode:
        errors.append("pinit_activation_boot_mode")
    return tuple(errors)


def authorize_activation(bundle: Bundle, context: ActivationContext) -> None:
    errors = activation_errors(bundle, context)
    if errors:
        raise InitialSystemError(errors[0])


def development_activation_context() -> ActivationContext:
    return ActivationContext(2, 1, True, True, False, False, False, 0, 1, 0, 1, 0, BOOT_NORMAL, False, False, False, False)


def synthetic_qualified_activation_context(bundle: Bundle | None = None) -> ActivationContext:
    version = 1 if bundle is None else bundle.bundle_version
    kernel_major = 1 if bundle is None else bundle.required_kernel_abi_major
    kernel_minor = 0 if bundle is None else bundle.minimum_kernel_abi_minor
    pbp_major = 1 if bundle is None else bundle.required_pbp_major
    pbp_minor = 0 if bundle is None else bundle.minimum_pbp_minor
    boot_mode = BOOT_NORMAL if bundle is None else next(
        mode for mode in (BOOT_NORMAL, BOOT_SAFE, BOOT_PREVIOUS, BOOT_DIAGNOSTIC) if bundle.allowed_boot_modes & mode
    )
    return ActivationContext(
        2,
        version,
        True,
        True,
        True,
        True,
        True,
        1,
        kernel_major,
        kernel_minor,
        pbp_major,
        pbp_minor,
        boot_mode,
        True,
        True,
        True,
        True,
    )


def activation_context(mode: str, bundle: Bundle | None = None) -> ActivationContext:
    if mode == "development":
        return development_activation_context()
    context = synthetic_qualified_activation_context(bundle)
    replacements: dict[str, Any] = {
        "role": {"outer_role": 7},
        "version": {"outer_artifact_version": context.outer_artifact_version + 1},
        "payload-digest": {"outer_payload_digest_verified": False},
        "file-digest": {"outer_file_digest_verified": False},
        "outer-signature": {"outer_signature_verified": False},
        "manifest-signature": {"manifest_signature_verified": False},
        "rollback-state": {"rollback_state_authenticated": False},
        "rollback-floor": {"trusted_minimum_secure_version": context.outer_artifact_version + 1},
        "kernel-abi": {"kernel_abi_major": context.kernel_abi_major + 1},
        "pbp": {"pbp_major": context.pbp_major + 1},
        "boot-mode": {"boot_mode": BOOT_DIAGNOSTIC},
        "capability-allocator": {"capability_allocator_ready": False},
        "resource-broker": {"resource_broker_ready": False},
        "component-contracts": {"component_contracts_verified": False},
        "transaction-capacity": {"transaction_capacity_verified": False},
    }
    if mode == "qualified":
        return context
    if mode not in replacements:
        _fail("pinit_activation_mode")
    return dataclasses.replace(context, **replacements[mode])


def minimal_bundle() -> bytes:
    return encode(
        bundle_version=1,
        minimum_secure_version=1,
        root_service_id=1,
        allowed_boot_modes=BOOT_NORMAL,
        required_kernel_abi_major=1,
        minimum_kernel_abi_minor=0,
        required_pbp_major=1,
        minimum_pbp_minor=0,
        start_timeout_ms=10_000,
        rollback_timeout_ms=10_000,
        max_total_restarts=0,
        components=(
            Component(
                1,
                COMPONENT_EXECUTABLE,
                COMPONENT_REQUIRED | COMPONENT_READ_ONLY | COMPONENT_EXECUTABLE_FLAG,
                "poole.init",
                PXABI1,
                b"PooleOS minimal PINIT1 candidate component\n",
                4096,
                4096,
            ),
        ),
        services=(
            Service(
                1,
                1,
                "service.init",
                SERVICE_REQUIRED | SERVICE_CRITICAL | SERVICE_BOOTSTRAP | SERVICE_DROP_BOOTSTRAP | SERVICE_STATELESS,
                1000,
                1000,
                RESTART_NEVER,
                FAILURE_ROLLBACK_BUNDLE,
                READINESS_EXPLICIT,
                SHUTDOWN_REVERSE_DEPENDENCY,
                0,
                0,
                0,
                0,
                500,
                1,
                1,
                1,
                0,
                0,
                0,
            ),
        ),
        dependencies=(),
        resources=(
            Resource(
                1,
                0,
                "bootstrap.endpoints",
                RESOURCE_ENDPOINT_SLOTS,
                RESOURCE_REQUIRED | RESOURCE_REVOCABLE | RESOURCE_EXCLUSIVE,
                1,
                8,
                1,
            ),
        ),
        capabilities=(
            Capability(
                1,
                0,
                1,
                1,
                RIGHT_READ | RIGHT_WRITE | RIGHT_MAP_OR_BIND,
                CAP_REVOCABLE | CAP_LIFECYCLE_BOUND,
                1,
                0,
                0,
                AVAILABILITY_REQUIRED,
            ),
        ),
    )


def data_component_bundle() -> bytes:
    base = parse(minimal_bundle())
    components = (
        base.components[0],
        Component(
            2,
            COMPONENT_DATA,
            COMPONENT_REQUIRED | COMPONENT_READ_ONLY,
            "poole.init.config",
            PINITD1,
            b"PINIT1 deterministic bootstrap data\n",
            0,
            8,
        ),
    )
    return encode(
        bundle_version=7,
        minimum_secure_version=6,
        root_service_id=base.root_service_id,
        allowed_boot_modes=BOOT_NORMAL | BOOT_SAFE,
        required_kernel_abi_major=base.required_kernel_abi_major,
        minimum_kernel_abi_minor=base.minimum_kernel_abi_minor,
        required_pbp_major=base.required_pbp_major,
        minimum_pbp_minor=base.minimum_pbp_minor,
        start_timeout_ms=base.start_timeout_ms,
        rollback_timeout_ms=base.rollback_timeout_ms,
        max_total_restarts=base.max_total_restarts,
        components=components,
        services=base.services,
        dependencies=base.dependencies,
        resources=base.resources,
        capabilities=base.capabilities,
    )


def build_fixture(vector_id: str) -> bytes:
    if vector_id == "minimal_v1":
        return minimal_bundle()
    if vector_id == "canonical_launch_v1":
        return canonical_bundle()
    if vector_id == "data_component_v1":
        return data_component_bundle()
    _fail("pinit_unknown_fixture")


def make_golden_vectors() -> dict[str, Any]:
    definitions = (
        ("minimal_v1", "Smallest valid one-service PINIT1 declaration bundle."),
        ("canonical_launch_v1", "Three-service canonical bootstrap launch declaration with attenuated routes."),
        ("data_component_v1", "Executable root plus a non-launchable PINITD1 data component and secure-version floor."),
    )
    vectors = []
    for vector_id, purpose in definitions:
        data = build_fixture(vector_id)
        bundle = parse(data)
        vectors.append(
            {
                "id": vector_id,
                "purpose": purpose,
                "byte_count": len(data),
                "sha256": sha256_bytes(data),
                "summary": summary(bundle),
                "component_count": len(bundle.components),
                "service_count": len(bundle.services),
                "hex": data.hex().upper(),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_initial_system_golden_vectors",
        "contract_id": CONTRACT_ID,
        "status": "synthetic_non_promoting_golden_bytes",
        "production_ready": False,
        "vectors": vectors,
        "claim_boundary": [
            "Vectors are synthetic declarations and are not authenticated boot artifacts.",
            "A valid PINIT1 bundle confers no kernel capability and authorizes no component execution.",
            "The all-true activation fixture is test-only logic coverage and is not trust evidence.",
        ],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "canonical_binary_format_defined": True,
        "rust_no_std_validator_executed": True,
        "independent_python_validator_executed": True,
        "golden_semantic_agreement": True,
        "hostile_controls_executed": True,
        "deterministic_differential_fuzz_executed": True,
        "declaration_activation_separation_enforced": True,
        "unsigned_development_activation_denied": True,
        "pooleboot_inner_semantics_enforced": False,
        "poolekernel_activation_enforced": False,
        "outer_signature_verified": False,
        "manifest_signature_verified": False,
        "persistent_rollback_state_enforced": False,
        "component_abi_verified": False,
        "kernel_capabilities_allocated": False,
        "resources_allocated": False,
        "component_executed": False,
        "initial_system_active": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }


def expected_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_initial_system_contract",
        "contract_id": CONTRACT_ID,
        "status": "candidate_pre_abi_non_promoting",
        "production_ready": False,
        "encoding": {
            "byte_order": "little-endian",
            "header_bytes": HEADER_BYTES,
            "record_alignment": RECORD_ALIGNMENT,
            "total_bytes_maximum": MAX_BUNDLE_BYTES,
            "body_digest": "SHA-256 over bytes from header_bytes through total_bytes",
            "canonical_layout": "fixed tables, canonical NUL-terminated ASCII name table, zero alignment padding, component blobs",
        },
        "header": {
            "magic_hex": MAGIC.hex().upper(),
            "version": [MAJOR_VERSION, MINOR_VERSION],
            "required_flags": REQUIRED_FLAGS,
            "record_sizes": {
                "component": COMPONENT_BYTES,
                "service": SERVICE_BYTES,
                "dependency": DEPENDENCY_BYTES,
                "resource": RESOURCE_BYTES,
                "capability": CAPABILITY_BYTES,
            },
        },
        "limits": {
            "components": MAX_COMPONENTS,
            "services": MAX_SERVICES,
            "dependencies": MAX_DEPENDENCIES,
            "resources": MAX_RESOURCES,
            "capabilities": MAX_CAPABILITIES,
            "string_bytes": MAX_STRING_BYTES,
            "name_bytes": MAX_NAME_BYTES,
            "component_blob_bytes": MAX_COMPONENT_BLOB_BYTES,
            "component_image_bytes": MAX_COMPONENT_IMAGE_BYTES,
        },
        "component_policy": {
            "executable_format": PXABI1.rstrip(b"\0").decode("ascii"),
            "data_format": PINITD1.rstrip(b"\0").decode("ascii"),
            "service_targets_must_be_executable": True,
            "embedded_component_bytes_are_opaque_until_separate_abi_verification": True,
            "physical_or_virtual_addresses_allowed": False,
        },
        "dependency_policy": {
            "kinds": {"strong": DEPENDENCY_STRONG, "weak": DEPENDENCY_WEAK},
            "full_graph_must_be_acyclic": True,
            "canonical_start_order": "lowest service ID deterministic Kahn order",
            "every_service_strongly_reachable_from_root": True,
            "required_service_may_require_optional_prerequisite": False,
            "shutdown_order": "reverse dependency order",
        },
        "resource_policy": {
            "kinds": {
                "memory_pages": RESOURCE_MEMORY_PAGES,
                "thread_slots": RESOURCE_THREAD_SLOTS,
                "endpoint_slots": RESOURCE_ENDPOINT_SLOTS,
                "address_space": RESOURCE_ADDRESS_SPACE,
                "log_sink": RESOURCE_LOG_SINK,
            },
            "abstract_declaration_only": True,
            "physical_addresses_allowed": False,
            "all_resources_revocable": True,
            "exactly_one_of_shareable_or_exclusive": True,
        },
        "capability_policy": {
            "declaration_ids_are_kernel_handles": False,
            "ambient_authority_allowed": False,
            "parent_must_precede_child": True,
            "rights_amplification_allowed": False,
            "availability_upgrade_allowed": False,
            "revoke_group_changes_across_derivation_allowed": False,
            "all_capabilities_revocable_and_lifecycle_bound": True,
            "provider_route_requires_direct_dependency_and_earlier_start": True,
        },
        "transaction_policy": {
            "start": "validate all declarations and preconditions before allocation or launch",
            "failure": "stop started services in reverse dependency order, revoke all issued capabilities, release all resources",
            "root_bootstrap_authority": "must be dropped after successful commit",
            "partial_commit_allowed": False,
        },
        "activation_preconditions": [
            "outer role and artifact version match",
            "outer payload and whole-file digests verified",
            "outer artifact and manifest signatures verified",
            "persistent rollback state authenticated and version floor satisfied",
            "kernel ABI and PBP compatibility satisfied",
            "one allowed boot mode selected",
            "capability allocator and resource broker ready",
            "every component contract independently verified",
            "transaction and rollback capacity verified",
        ],
        "research_basis": [
            "https://docs.sel4.systems/projects/capdl/lang-spec.html",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities/availability",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/lifecycle",
            "https://theupdateframework.github.io/specification/v1.0.26/",
        ],
        "production_claims": expected_claims(),
        "claim_boundary": [
            "PINIT1 is a candidate declaration and activation-precondition contract, not an owner-ratified stable ABI.",
            "PINIT1 declaration IDs are not PooleKernel object handles and confer no authority.",
            "The Rust and Python validators execute on the host; PooleBoot and PooleKernel do not yet interpret PINIT1.",
            "The current PBART1 and PSM1 development media are unsigned and attacker-controllable, so activation must fail.",
            "The synthetic all-true activation context proves branch behavior only; it is not signature, rollback, ABI, allocator, broker, or capacity evidence.",
            "No component ABI is frozen, no component instruction executes, and no capability or resource is allocated.",
            "Recovery, symbols, microcode, firmware-manifest, and policy inner formats remain outside this slice.",
            "No key is generated or used and no signing, merge, tag, release, firmware mutation, or media write is authorized.",
            "N5.6, N5, the broad initial-semantics flag, and production readiness remain incomplete.",
        ],
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if contract != expected_contract():
        errors.append("contract differs from executable PINIT1 constants")
    return errors


def golden_errors(golden: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / GOLDEN_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(golden, schema)]
    try:
        expected = make_golden_vectors()
    except (InitialSystemError, ValueError, OverflowError) as error:
        return errors + [f"unable to construct vectors: {error}"]
    if golden != expected:
        errors.append("golden vectors do not reproduce exactly")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
        golden = read_json(root / GOLDEN_RELATIVE)
    except (OSError, json.JSONDecodeError, InitialSystemError) as error:
        return errors + [f"unable to read bound PINIT1 artifact: {error}"]
    errors.extend(f"contract {item}" for item in contract_errors(contract, root))
    errors.extend(f"golden {item}" for item in golden_errors(golden, root))
    expected_bindings = {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "golden_vectors": file_binding(root / GOLDEN_RELATIVE, root),
        "golden_schema": file_binding(root / GOLDEN_SCHEMA_RELATIVE, root),
        "readiness_schema": file_binding(root / READINESS_SCHEMA_RELATIVE, root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }
    if readiness.get("bindings") != expected_bindings:
        errors.append("readiness input bindings are stale")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary changed")
    expected_summary = {
        "rust_host_tests_passed": 3,
        "rust_host_tests_total": 3,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": len(NEGATIVE_CONTROL_IDS),
        "negative_controls_total": len(NEGATIVE_CONTROL_IDS),
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "development_activation_denied": True,
        "synthetic_activation_passed": True,
        "production_claim_count": 0,
    }
    if readiness.get("summary") != expected_summary:
        errors.append("readiness summary changed")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("negative control register changed")
    if any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("negative control did not pass")
    if readiness.get("production_ready") is not False or readiness.get("n5_exit_gate_satisfied") is not False:
        errors.append("readiness overclaims production or N5 exit")
    return errors
