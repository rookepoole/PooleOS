"""Independent PBEXIT1 lifecycle and live-marker oracle."""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Iterable


CONTRACT_ID = "PBEXIT1"
MAX_EXIT_ATTEMPTS = 4
RAW_MEMORY_MAP_CAPACITY = 1024 * 1024
HANDOFF_CAPACITY_BYTES = 1024 * 1024
PAGE_SIZE = 4096
TABLE_PAGE_COUNT = 4
STACK_PAGE_COUNT = 8
HANDOFF_PAGE_COUNT = 256

EXIT_MARKER = re.compile(
    r"^POOLEBOOT/0\.1 EXIT_BOOT_SERVICES PASS contract=(PBEXIT1) attempts=([0-9]+) "
    r"map_bytes=([0-9]+) descriptor_bytes=([0-9]+) descriptors=([0-9]+)$"
)
BOUNDARY_MARKER = re.compile(
    r"^POOLEBOOT/0\.1 FIRMWARE_BOUNDARY PASS calls_after_exit=([0-9]+) "
    r"kernel_pages=([0-9]+) table_pages=([0-9]+) stack_pages=([0-9]+) "
    r"handoff_pages=([0-9]+)$"
)
DEVELOPMENT_BOUNDARY = (
    "POOLEBOOT/0.1 BOUNDARY unsigned=1 secure_boot=not_tested "
    "selection=manifest_digest_untrusted kernel=retained handoff=retained "
    "mappings=retained entry=not_called exit_boot_services=called transfer=stopped"
)
STOP_MARKER = "POOLEBOOT/0.1 STOP BEFORE TRANSFER"


class BootExitError(RuntimeError):
    """Raised when PBEXIT1 ordering, state, or marker evidence fails closed."""


@dataclasses.dataclass(frozen=True)
class FinalMap:
    map_key: int
    map_bytes: int
    descriptor_size: int
    descriptor_version: int


@dataclasses.dataclass(frozen=True)
class HandoffCandidate:
    byte_count: int
    boot_services_exited: bool
    development_mode: bool
    stack_top_virtual: int
    page_table_root_physical: int
    kernel_signature_verified: bool
    kernel_entry_profile_valid: bool


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BootExitError(message)


def validate_final_map(value: FinalMap) -> None:
    _require(isinstance(value.map_key, int) and value.map_key >= 0, "memory-map key is invalid")
    _require(
        isinstance(value.descriptor_size, int)
        and 40 <= value.descriptor_size <= 256
        and value.descriptor_size % 8 == 0,
        "memory-map descriptor size is invalid",
    )
    _require(
        isinstance(value.map_bytes, int)
        and 0 < value.map_bytes <= RAW_MEMORY_MAP_CAPACITY
        and value.map_bytes % value.descriptor_size == 0,
        "memory-map byte shape is invalid",
    )
    _require(value.descriptor_version == 1, "memory-map descriptor version is unsupported")


def validate_handoff_candidate(value: HandoffCandidate) -> None:
    _require(0 < value.byte_count <= HANDOFF_CAPACITY_BYTES, "handoff byte count is invalid")
    _require(value.boot_services_exited is True, "handoff omits the exited-boot-services state")
    _require(value.development_mode is True, "handoff is not development-scoped")
    _require(
        isinstance(value.stack_top_virtual, int)
        and value.stack_top_virtual > 0
        and value.stack_top_virtual % 16 == 0,
        "handoff stack state is invalid",
    )
    _require(
        isinstance(value.page_table_root_physical, int)
        and value.page_table_root_physical > 0
        and value.page_table_root_physical % PAGE_SIZE == 0,
        "handoff page-table root is invalid",
    )
    _require(value.kernel_signature_verified is False, "unsigned kernel was promoted")
    _require(value.kernel_entry_profile_valid is False, "development handoff became transferable")


def validate_trace(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = list(events)
    _require(bool(values), "PBEXIT1 trace is empty")
    cursor = 0
    attempts = 0
    while cursor < len(values):
        _require(attempts < MAX_EXIT_ATTEMPTS, "ExitBootServices retry bound was exceeded")
        map_event = values[cursor]
        _require(map_event.get("operation") == "get_memory_map", "fresh final map is missing")
        validate_final_map(FinalMap(**map_event.get("map", {})))
        cursor += 1
        _require(cursor < len(values), "final PBP1 candidate is missing")
        handoff_event = values[cursor]
        _require(handoff_event.get("operation") == "finalize_handoff", "final PBP1 ordering differs")
        validate_handoff_candidate(HandoffCandidate(**handoff_event.get("handoff", {})))
        cursor += 1
        _require(cursor < len(values), "ExitBootServices call is missing")
        exit_event = values[cursor]
        _require(exit_event.get("operation") == "exit_boot_services", "firmware call ordering differs")
        result = exit_event.get("result")
        _require(result in {"success", "invalid_parameter"}, "non-retryable exit status was accepted")
        attempts += 1
        cursor += 1
        if result == "success":
            _require(cursor == len(values), "firmware or transfer activity followed successful exit")
            return {
                "contract_id": CONTRACT_ID,
                "attempt_count": attempts,
                "fresh_map_per_attempt": True,
                "firmware_calls_after_exit": 0,
                "transfer_allowed": False,
                "stopped_before_transfer": True,
            }
        _require(attempts < MAX_EXIT_ATTEMPTS, "ExitBootServices retry bound was exhausted")
    raise BootExitError("PBEXIT1 trace ended without successful ExitBootServices")


def validate_live_markers(
    exit_marker: str,
    boundary_marker: str,
    development_boundary: str,
    stop_marker: str,
) -> dict[str, Any]:
    exit_match = EXIT_MARKER.fullmatch(exit_marker)
    _require(exit_match is not None, "ExitBootServices marker is malformed")
    assert exit_match is not None
    attempts = int(exit_match.group(2))
    map_bytes = int(exit_match.group(3))
    descriptor_size = int(exit_match.group(4))
    descriptor_count = int(exit_match.group(5))
    validate_final_map(FinalMap(0, map_bytes, descriptor_size, 1))
    _require(1 <= attempts <= MAX_EXIT_ATTEMPTS, "ExitBootServices attempt count is invalid")
    _require(map_bytes == descriptor_size * descriptor_count, "final memory-map count diverges")

    boundary_match = BOUNDARY_MARKER.fullmatch(boundary_marker)
    _require(boundary_match is not None, "firmware boundary marker is malformed")
    assert boundary_match is not None
    values = [int(item) for item in boundary_match.groups()]
    _require(values[0] == 0, "firmware call followed successful ExitBootServices")
    _require(values[1] > 0, "kernel pages were not retained")
    _require(values[2:] == [TABLE_PAGE_COUNT, STACK_PAGE_COUNT, HANDOFF_PAGE_COUNT], "retained page accounting diverges")
    _require(development_boundary == DEVELOPMENT_BOUNDARY, "development claim boundary changed")
    _require(stop_marker == STOP_MARKER, "permanent pre-transfer stop marker is missing")
    return {
        "contract_id": CONTRACT_ID,
        "attempt_count": attempts,
        "map_byte_count": map_bytes,
        "descriptor_size": descriptor_size,
        "descriptor_count": descriptor_count,
        "firmware_calls_after_exit": 0,
        "kernel_page_count": values[1],
        "table_page_count": values[2],
        "stack_page_count": values[3],
        "handoff_page_count": values[4],
        "transfer_allowed": False,
        "stopped_before_transfer": True,
    }
