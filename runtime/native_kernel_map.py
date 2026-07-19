"""Independent PKMAP1/PKMAP2 page-table, lifecycle, and marker oracle."""

from __future__ import annotations

import copy
import dataclasses
import re
from typing import Any, Iterable


CONTRACT_ID = "PKMAP1"
RETAINED_CONTRACT_ID = "PKMAP2"
PAGE_SIZE = 4096
TABLE_ENTRIES = 512
TABLE_PAGE_COUNT = 4
WINDOW_BYTES = 2 * 1024 * 1024
MIN_VIRTUAL_BASE = 0xFFFF_FFFF_8000_0000
MAX_VIRTUAL_EXCLUSIVE = 0xFFFF_FFFF_C000_0000
MAX_MAPPINGS = 8
ENTRY_PRESENT = 1 << 0
ENTRY_WRITABLE = 1 << 1
ENTRY_PWT = 1 << 3
ENTRY_PCD = 1 << 4
ENTRY_PAGE_SIZE_OR_PAT = 1 << 7
ENTRY_LARGE_PAT = 1 << 12
ENTRY_NO_EXECUTE = 1 << 63
FNV_OFFSET = 0xCBF2_9CE4_8422_2325
FNV_PRIME = 0x0000_0100_0000_01B3
ORACLE_ORIGINAL_ROOT = 0x0010_0000
ORACLE_TABLE_BASE = 0x0300_0000
STACK_GUARD_LOW_PAGE = 64
STACK_FIRST_PAGE = 65
STACK_PAGE_COUNT = 8
STACK_GUARD_HIGH_PAGE = 73
HANDOFF_FIRST_PAGE = 80
HANDOFF_PAGE_COUNT = 256
HANDOFF_CAPACITY_BYTES = HANDOFF_PAGE_COUNT * PAGE_SIZE

PROBE_PATTERN = re.compile(
    r"^PKMAP1 PASS mappings=([0-9]+) pages=([0-9]+) ro=([0-9]+) "
    r"rx=([0-9]+) rw=([0-9]+) wx=([0-9]+) pml4=([0-9]+) "
    r"pdpt=([0-9]+) pd=([0-9]+) pt=([0-9]+) leaf_fnv1a64=([0-9A-F]{16})$"
)
RETAINED_PROBE_PATTERN = re.compile(
    r"^PKMAP2 PASS kernel_pages=([0-9]+) stack_pages=([0-9]+) "
    r"handoff_pages=([0-9]+) guards=([0-9]+) total_pages=([0-9]+) "
    r"stack_pt=([0-9]+) handoff_pt=([0-9]+) retained_fnv1a64=([0-9A-F]{16})$"
)


class KernelMapError(RuntimeError):
    """Raised when bounded PKMAP1 evidence violates the frozen contract."""


@dataclasses.dataclass(frozen=True)
class Mapping:
    virtual_offset: int
    byte_count: int
    permissions: str


@dataclasses.dataclass(frozen=True)
class Request:
    physical_base: int
    virtual_base: int
    image_bytes: int
    page_count: int
    entry_virtual: int
    mappings: tuple[Mapping, ...]
    physical_address_bits: int


@dataclasses.dataclass(frozen=True)
class RetainedRequest:
    stack_physical_base: int
    stack_page_count: int
    handoff_physical_base: int
    handoff_capacity_bytes: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelMapError(message)


def _canonical_48(address: int) -> bool:
    if not 0 <= address <= 0xFFFF_FFFF_FFFF_FFFF:
        return False
    upper = address >> 48
    return upper == (0xFFFF if address & (1 << 47) else 0)


def _pml4_index(address: int) -> int:
    return (address >> 39) & 0x1FF


def _pdpt_index(address: int) -> int:
    return (address >> 30) & 0x1FF


def _page_directory_index(address: int) -> int:
    return (address >> 21) & 0x1FF


def _page_table_index(address: int) -> int:
    return (address >> 12) & 0x1FF


def _fnv_u64(state: int, value: int) -> int:
    for byte in int(value).to_bytes(8, "little", signed=False):
        state ^= byte
        state = state * FNV_PRIME & 0xFFFF_FFFF_FFFF_FFFF
    return state


def _permission_code(value: str) -> int:
    return {"r": 1, "rw": 3, "rx": 5}.get(value, -1)


def _leaf_flags(value: str) -> int:
    flags = ENTRY_PRESENT
    if value == "rw":
        flags |= ENTRY_WRITABLE
    if value != "rx":
        flags |= ENTRY_NO_EXECUTE
    return flags


def validate_cpu(profile: dict[str, Any]) -> None:
    required_true = (
        "paging",
        "pae",
        "long_mode",
        "write_protect",
        "nx_supported",
        "nx_enabled",
    )
    for field in required_true:
        _require(profile.get(field) is True, f"CPU profile requires {field}")
    _require(profile.get("five_level_paging") is False, "five-level paging is unsupported")
    _require(profile.get("pcid_enabled") is False, "PCID is unsupported in PKMAP1")
    bits = profile.get("physical_address_bits")
    _require(isinstance(bits, int) and 36 <= bits <= 52, "physical-address width is unsupported")


def request_from_elf_plan(plan: dict[str, Any], physical_address_bits: int) -> Request:
    mappings_value = plan.get("mappings")
    _require(isinstance(mappings_value, (list, tuple)), "ELF mapping plan is missing")
    mappings: list[Mapping] = []
    for value in mappings_value:
        _require(isinstance(value, dict), "ELF mapping is malformed")
        mappings.append(
            Mapping(
                virtual_offset=value.get("virtual_offset"),
                byte_count=value.get("memory_size"),
                permissions=value.get("permissions"),
            )
        )
    return Request(
        physical_base=plan.get("physical_base"),
        virtual_base=plan.get("virtual_base"),
        image_bytes=plan.get("image_size"),
        page_count=plan.get("image_size") // PAGE_SIZE
        if isinstance(plan.get("image_size"), int)
        else -1,
        entry_virtual=plan.get("entry_virtual"),
        mappings=tuple(mappings),
        physical_address_bits=physical_address_bits,
    )


def _validate_request(request: Request) -> None:
    _require(36 <= request.physical_address_bits <= 52, "physical-address width is unsupported")
    maximum_physical = 1 << request.physical_address_bits
    _require(
        isinstance(request.physical_base, int)
        and request.physical_base > 0
        and request.physical_base % PAGE_SIZE == 0,
        "kernel physical base is invalid",
    )
    _require(
        request.physical_base + request.image_bytes <= maximum_physical,
        "kernel physical range exceeds the CPU width",
    )
    _require(
        isinstance(request.virtual_base, int)
        and MIN_VIRTUAL_BASE <= request.virtual_base < MAX_VIRTUAL_EXCLUSIVE
        and request.virtual_base % WINDOW_BYTES == 0
        and _canonical_48(request.virtual_base),
        "kernel virtual base is invalid",
    )
    _require(
        isinstance(request.image_bytes, int)
        and 0 < request.image_bytes <= WINDOW_BYTES
        and request.image_bytes % PAGE_SIZE == 0,
        "kernel image size is invalid",
    )
    _require(request.page_count == request.image_bytes // PAGE_SIZE, "kernel page count diverges")
    virtual_last = request.virtual_base + request.image_bytes - 1
    _require(
        virtual_last < MAX_VIRTUAL_EXCLUSIVE
        and _canonical_48(virtual_last)
        and _page_directory_index(request.virtual_base) == _page_directory_index(virtual_last),
        "kernel crosses its bounded 2 MiB window",
    )
    _require(0 < len(request.mappings) <= MAX_MAPPINGS, "mapping count is invalid")
    _require(
        request.virtual_base <= request.entry_virtual <= virtual_last,
        "entry address is outside the image",
    )
    expected_offset = 0
    entry_executable = False
    for mapping in request.mappings:
        _require(
            isinstance(mapping.virtual_offset, int)
            and isinstance(mapping.byte_count, int)
            and mapping.byte_count > 0
            and mapping.virtual_offset % PAGE_SIZE == 0
            and mapping.byte_count % PAGE_SIZE == 0,
            "mapping alignment is invalid",
        )
        _require(mapping.virtual_offset == expected_offset, "mapping coverage has a gap or overlap")
        _require(_permission_code(mapping.permissions) >= 0, "mapping permission is invalid")
        _require(mapping.permissions != "rwx", "writable-executable mapping is forbidden")
        mapping_end = mapping.virtual_offset + mapping.byte_count
        _require(mapping_end <= request.image_bytes, "mapping exceeds the image")
        absolute_start = request.virtual_base + mapping.virtual_offset
        absolute_end = request.virtual_base + mapping_end
        if absolute_start <= request.entry_virtual < absolute_end and mapping.permissions == "rx":
            entry_executable = True
        expected_offset = mapping_end
    _require(expected_offset == request.image_bytes, "mappings do not cover the image exactly")
    _require(entry_executable, "entry address is not in executable memory")


def build_model(
    request: Request,
    *,
    original_root: Iterable[int] | None = None,
    original_root_address: int = ORACLE_ORIGINAL_ROOT,
    table_base: int = ORACLE_TABLE_BASE,
) -> dict[str, Any]:
    _validate_request(request)
    root = list(original_root) if original_root is not None else [0] * TABLE_ENTRIES
    _require(len(root) == TABLE_ENTRIES, "original root table shape is invalid")
    addresses = {
        "original_root": original_root_address,
        "candidate_root": table_base,
        "pdpt": table_base + PAGE_SIZE,
        "page_directory": table_base + 2 * PAGE_SIZE,
        "page_table": table_base + 3 * PAGE_SIZE,
    }
    maximum_physical = 1 << request.physical_address_bits
    for value in addresses.values():
        _require(value > 0 and value % PAGE_SIZE == 0 and value < maximum_physical, "table address is invalid")
    _require(len(set(addresses.values())) == len(addresses), "table addresses overlap")
    table_end = table_base + TABLE_PAGE_COUNT * PAGE_SIZE
    kernel_end = request.physical_base + request.image_bytes
    _require(
        not (request.physical_base < table_end and table_base < kernel_end),
        "page tables overlap kernel pages",
    )
    pml4 = _pml4_index(request.virtual_base)
    pdpt = _pdpt_index(request.virtual_base)
    directory = _page_directory_index(request.virtual_base)
    first_leaf = _page_table_index(request.virtual_base)
    _require(root[pml4] == 0, "target PML4 slot is occupied")

    page_permissions: list[str] = []
    for mapping in request.mappings:
        page_permissions.extend([mapping.permissions] * (mapping.byte_count // PAGE_SIZE))
    _require(len(page_permissions) == request.page_count, "page permission expansion diverges")
    counts = {
        "read_only_page_count": page_permissions.count("r"),
        "read_execute_page_count": page_permissions.count("rx"),
        "read_write_page_count": page_permissions.count("rw"),
        "writable_executable_page_count": page_permissions.count("rwx"),
    }
    fingerprint = FNV_OFFSET
    leaves: list[dict[str, Any]] = []
    for page, permissions in enumerate(page_permissions):
        fingerprint = _fnv_u64(fingerprint, page)
        fingerprint = _fnv_u64(fingerprint, _permission_code(permissions))
        leaves.append(
            {
                "page_table_index": first_leaf + page,
                "virtual_offset": page * PAGE_SIZE,
                "physical_offset": page * PAGE_SIZE,
                "permissions": permissions,
                "normalized_flags": f"{_leaf_flags(permissions):016X}",
            }
        )
    return {
        "contract_id": CONTRACT_ID,
        "request": {
            "physical_base": request.physical_base,
            "virtual_base": request.virtual_base,
            "image_bytes": request.image_bytes,
            "page_count": request.page_count,
            "entry_virtual": request.entry_virtual,
            "physical_address_bits": request.physical_address_bits,
            "mappings": [dataclasses.asdict(value) for value in request.mappings],
        },
        "addresses": addresses,
        "indices": {
            "pml4": pml4,
            "pdpt": pdpt,
            "page_directory": directory,
            "first_page_table": first_leaf,
        },
        "mapped_page_count": request.page_count,
        **counts,
        "leaf_fingerprint": f"{fingerprint:016X}",
        "leaves": leaves,
    }


def request_from_model(model: dict[str, Any]) -> Request:
    value = model.get("request")
    _require(isinstance(value, dict), "model request is missing")
    mappings = value.get("mappings")
    _require(isinstance(mappings, list), "model mappings are missing")
    return Request(
        physical_base=value.get("physical_base"),
        virtual_base=value.get("virtual_base"),
        image_bytes=value.get("image_bytes"),
        page_count=value.get("page_count"),
        entry_virtual=value.get("entry_virtual"),
        mappings=tuple(Mapping(**item) for item in mappings),
        physical_address_bits=value.get("physical_address_bits"),
    )


def validate_model(model: dict[str, Any]) -> None:
    request = request_from_model(model)
    addresses = model.get("addresses")
    _require(isinstance(addresses, dict), "model addresses are missing")
    expected = build_model(
        request,
        original_root_address=addresses.get("original_root"),
        table_base=addresses.get("candidate_root"),
    )
    _require(model == expected, "page-table model diverges from the independent oracle")


def marker_expectation(plan: dict[str, Any], physical_address_bits: int) -> dict[str, Any]:
    model = build_model(request_from_elf_plan(plan, physical_address_bits))
    return {
        "contract_id": CONTRACT_ID,
        "mapping_count": len(model["request"]["mappings"]),
        "mapped_page_count": model["mapped_page_count"],
        "read_only_page_count": model["read_only_page_count"],
        "read_execute_page_count": model["read_execute_page_count"],
        "read_write_page_count": model["read_write_page_count"],
        "writable_executable_page_count": model["writable_executable_page_count"],
        "pml4_index": model["indices"]["pml4"],
        "pdpt_index": model["indices"]["pdpt"],
        "page_directory_index": model["indices"]["page_directory"],
        "first_page_table_index": model["indices"]["first_page_table"],
        "leaf_fingerprint": model["leaf_fingerprint"],
    }


def build_retained_model(
    request: Request,
    retained: RetainedRequest,
    *,
    original_root: Iterable[int] | None = None,
    original_root_address: int = ORACLE_ORIGINAL_ROOT,
    table_base: int = ORACLE_TABLE_BASE,
) -> dict[str, Any]:
    kernel = build_model(
        request,
        original_root=original_root,
        original_root_address=original_root_address,
        table_base=table_base,
    )
    _require(
        request.page_count <= STACK_GUARD_LOW_PAGE and kernel["indices"]["first_page_table"] == 0,
        "kernel collides with the retained stack guard",
    )
    _require(
        retained.stack_physical_base > 0
        and retained.stack_physical_base % PAGE_SIZE == 0
        and retained.stack_page_count == STACK_PAGE_COUNT,
        "retained stack range is invalid",
    )
    _require(
        retained.handoff_physical_base > 0
        and retained.handoff_physical_base % PAGE_SIZE == 0
        and retained.handoff_capacity_bytes == HANDOFF_CAPACITY_BYTES,
        "retained handoff range is invalid",
    )
    maximum_physical = 1 << request.physical_address_bits
    ranges = (
        (request.physical_base, request.image_bytes),
        (table_base, TABLE_PAGE_COUNT * PAGE_SIZE),
        (retained.stack_physical_base, retained.stack_page_count * PAGE_SIZE),
        (retained.handoff_physical_base, retained.handoff_capacity_bytes),
    )
    for start, byte_count in ranges:
        _require(start + byte_count <= maximum_physical, "retained physical range exceeds the CPU width")
    for first, (first_start, first_size) in enumerate(ranges):
        first_end = first_start + first_size
        for second_start, second_size in ranges[first + 1 :]:
            _require(
                not (first_start < second_start + second_size and second_start < first_end),
                "retained physical ranges overlap",
            )
    _require(
        STACK_FIRST_PAGE + STACK_PAGE_COUNT == STACK_GUARD_HIGH_PAGE
        and STACK_GUARD_HIGH_PAGE < HANDOFF_FIRST_PAGE
        and HANDOFF_FIRST_PAGE + HANDOFF_PAGE_COUNT <= TABLE_ENTRIES,
        "retained virtual layout is invalid",
    )
    stack_bottom = request.virtual_base + STACK_FIRST_PAGE * PAGE_SIZE
    stack_top = stack_bottom + STACK_PAGE_COUNT * PAGE_SIZE
    handoff_virtual = request.virtual_base + HANDOFF_FIRST_PAGE * PAGE_SIZE
    handoff_end = handoff_virtual + HANDOFF_CAPACITY_BYTES
    _require(
        _canonical_48(stack_bottom)
        and _canonical_48(stack_top - 1)
        and _canonical_48(handoff_virtual)
        and _canonical_48(handoff_end - 1)
        and handoff_end <= request.virtual_base + WINDOW_BYTES,
        "retained virtual range is invalid",
    )
    fingerprint = FNV_OFFSET
    retained_leaves: list[dict[str, Any]] = []
    for kind, first_page, page_count, physical_base, permissions in (
        (1, STACK_FIRST_PAGE, STACK_PAGE_COUNT, retained.stack_physical_base, "rw"),
        (2, HANDOFF_FIRST_PAGE, HANDOFF_PAGE_COUNT, retained.handoff_physical_base, "r"),
    ):
        for page in range(page_count):
            page_index = first_page + page
            physical = physical_base + page * PAGE_SIZE
            fingerprint = _fnv_u64(fingerprint, kind)
            fingerprint = _fnv_u64(fingerprint, page_index)
            fingerprint = _fnv_u64(fingerprint, physical)
            fingerprint = _fnv_u64(fingerprint, _permission_code(permissions))
            retained_leaves.append(
                {
                    "page_table_index": page_index,
                    "physical": physical,
                    "permissions": permissions,
                    "normalized_flags": f"{_leaf_flags(permissions):016X}",
                }
            )
    return {
        "contract_id": RETAINED_CONTRACT_ID,
        "kernel": kernel,
        "retained_request": dataclasses.asdict(retained),
        "stack_first_page_table_index": STACK_FIRST_PAGE,
        "stack_page_count": STACK_PAGE_COUNT,
        "stack_bottom_virtual": stack_bottom,
        "stack_top_virtual": stack_top,
        "handoff_first_page_table_index": HANDOFF_FIRST_PAGE,
        "handoff_page_count": HANDOFF_PAGE_COUNT,
        "handoff_virtual_base": handoff_virtual,
        "guard_page_indices": [STACK_GUARD_LOW_PAGE, STACK_GUARD_HIGH_PAGE],
        "guard_page_count": 2,
        "total_mapped_page_count": request.page_count + STACK_PAGE_COUNT + HANDOFF_PAGE_COUNT,
        "retained_leaf_fingerprint": f"{fingerprint:016X}",
        "retained_leaves": retained_leaves,
    }


def retained_marker_expectation(
    plan: dict[str, Any],
    physical_address_bits: int,
    *,
    kernel_physical_base: int,
    stack_physical_base: int,
    handoff_physical_base: int,
    table_base: int,
) -> dict[str, Any]:
    runtime_plan = copy.deepcopy(plan)
    runtime_plan["physical_base"] = kernel_physical_base
    model = build_retained_model(
        request_from_elf_plan(runtime_plan, physical_address_bits),
        RetainedRequest(
            stack_physical_base=stack_physical_base,
            stack_page_count=STACK_PAGE_COUNT,
            handoff_physical_base=handoff_physical_base,
            handoff_capacity_bytes=HANDOFF_CAPACITY_BYTES,
        ),
        table_base=table_base,
    )
    return {
        "contract_id": RETAINED_CONTRACT_ID,
        "table_page_count": TABLE_PAGE_COUNT,
        "stack_page_count": model["stack_page_count"],
        "handoff_page_count": model["handoff_page_count"],
        "guard_page_count": model["guard_page_count"],
        "total_mapped_page_count": model["total_mapped_page_count"],
        "stack_first_page_table_index": model["stack_first_page_table_index"],
        "handoff_first_page_table_index": model["handoff_first_page_table_index"],
        "page_table_root_physical": table_base,
        "kernel_physical_base": kernel_physical_base,
        "stack_physical_base": stack_physical_base,
        "stack_top_virtual": model["stack_top_virtual"],
        "handoff_physical_base": handoff_physical_base,
        "handoff_virtual_base": model["handoff_virtual_base"],
        "retained_leaf_fingerprint": model["retained_leaf_fingerprint"],
    }


def parse_probe_output(value: str) -> dict[str, Any]:
    match = PROBE_PATTERN.fullmatch(value.strip())
    _require(match is not None, "Rust PKMAP1 probe output is malformed")
    assert match is not None
    values = [int(item) for item in match.groups()[:-1]]
    _require(values[5] == 0, "Rust PKMAP1 probe reported writable-executable pages")
    return {
        "contract_id": CONTRACT_ID,
        "mapping_count": values[0],
        "mapped_page_count": values[1],
        "read_only_page_count": values[2],
        "read_execute_page_count": values[3],
        "read_write_page_count": values[4],
        "writable_executable_page_count": values[5],
        "pml4_index": values[6],
        "pdpt_index": values[7],
        "page_directory_index": values[8],
        "first_page_table_index": values[9],
        "leaf_fingerprint": match.group(11),
    }


def parse_retained_probe_output(value: str) -> dict[str, Any]:
    match = RETAINED_PROBE_PATTERN.fullmatch(value.strip())
    _require(match is not None, "Rust PKMAP2 probe output is malformed")
    assert match is not None
    values = [int(item) for item in match.groups()[:-1]]
    _require(
        values[1:] == [STACK_PAGE_COUNT, HANDOFF_PAGE_COUNT, 2, values[0] + STACK_PAGE_COUNT + HANDOFF_PAGE_COUNT, STACK_FIRST_PAGE, HANDOFF_FIRST_PAGE],
        "Rust PKMAP2 retained page accounting diverges",
    )
    return {
        "contract_id": RETAINED_CONTRACT_ID,
        "kernel_page_count": values[0],
        "stack_page_count": values[1],
        "handoff_page_count": values[2],
        "guard_page_count": values[3],
        "total_mapped_page_count": values[4],
        "stack_first_page_table_index": values[5],
        "handoff_first_page_table_index": values[6],
        "retained_leaf_fingerprint": match.group(8),
    }


def retained_probe_expectation(plan: dict[str, Any], physical_address_bits: int) -> dict[str, Any]:
    model = build_retained_model(
        request_from_elf_plan(plan, physical_address_bits),
        RetainedRequest(
            stack_physical_base=0x0400_0000,
            stack_page_count=STACK_PAGE_COUNT,
            handoff_physical_base=0x0500_0000,
            handoff_capacity_bytes=HANDOFF_CAPACITY_BYTES,
        ),
        table_base=ORACLE_TABLE_BASE,
    )
    return {
        "contract_id": RETAINED_CONTRACT_ID,
        "kernel_page_count": model["kernel"]["mapped_page_count"],
        "stack_page_count": model["stack_page_count"],
        "handoff_page_count": model["handoff_page_count"],
        "guard_page_count": model["guard_page_count"],
        "total_mapped_page_count": model["total_mapped_page_count"],
        "stack_first_page_table_index": model["stack_first_page_table_index"],
        "handoff_first_page_table_index": model["handoff_first_page_table_index"],
        "retained_leaf_fingerprint": model["retained_leaf_fingerprint"],
    }


def validate_lifecycle(events: list[dict[str, Any]]) -> None:
    expected_states = ["prepared", "candidate_active", "restored", "released"]
    _require(
        [item.get("state") for item in events] == expected_states,
        "mapping lifecycle order diverges",
    )
    active = events[1]
    _require(active.get("firmware_call_count") == 0, "firmware was called while candidate CR3 was active")
    _require(events[2].get("observed_cr3") == events[0].get("original_cr3"), "CR3 rollback diverges")
    _require(events[3].get("table_pages_freed") == TABLE_PAGE_COUNT, "table cleanup diverges")


def validate_retained_lifecycle(events: list[dict[str, Any]]) -> None:
    expected_states = ["prepared", "candidate_active", "restored", "retained"]
    _require(
        [item.get("state") for item in events] == expected_states,
        "retained mapping lifecycle order diverges",
    )
    _require(events[1].get("firmware_call_count") == 0, "firmware was called under candidate CR3")
    _require(events[2].get("observed_cr3") == events[0].get("original_cr3"), "CR3 restore diverges")
    _require(events[3].get("table_pages_freed") == 0, "retained page tables were released")


def validate_framebuffer_preserved(original: dict[str, Any], candidate: dict[str, Any]) -> None:
    required = ("first_physical", "last_physical", "first_page_size", "last_page_size", "cache_signature")
    _require(all(field in original and field in candidate for field in required), "framebuffer snapshot is incomplete")
    _require(original == candidate, "framebuffer translation or cache bits drifted")


def validate_kernel_page_sizes(page_sizes: Iterable[int]) -> None:
    values = list(page_sizes)
    _require(bool(values), "kernel page-size evidence is empty")
    _require(all(value == PAGE_SIZE for value in values), "kernel mapping contains a large page")


def mutated_model(model: dict[str, Any], path: tuple[str | int, ...], value: Any) -> dict[str, Any]:
    result = copy.deepcopy(model)
    target: Any = result
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    return result
