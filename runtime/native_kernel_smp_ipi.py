"""Independent PKSMP5 multi-AP lifecycle and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSMP5"
SELECTED_MOVE_ID = "N8-SMP-MULTI-AP-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-smp-ipi-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-smp-ipi-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-smp-ipi-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-smp-ipi-readiness.schema.json"
FEATURE = "development-smp-ipi"
SELECTOR = 14
MARKER_COUNT = 40
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SMP-MULTI-RESULT PASS contract=PKSMP5"

PAGE_BYTES = 4096
U64_MASK = (1 << 64) - 1
RESOURCE_PAGE_COUNT = 32
AP_COUNT = 3
EXPECTED_PROCESSOR_COUNT = 4
EXPECTED_APIC_IDS = (1, 2, 3)
PARTIAL_STARTED_MASK = 0x6
TARGET_CPU_MASK = 0xE
OFFLINE_APIC_ID = 4
OFFLINE_CPU_MASK = 0x10
IDENTITY_MAPPED_PAGE_COUNT = 13
GUARD_PAGE_COUNT = 14
APIC_PAGE_TABLE_OFFSET = 31
APIC_PHYSICAL_ADDRESS = 0xFEE0_0000
APIC_PDPT_INDEX = 3
APIC_PAGE_DIRECTORY_INDEX = 503
EXTENSION_MAGIC = 0x504B_534D_5035_4950
EXTENSION_VERSION = 3
CAPABILITY_HIGH = 0x504F_4F4C_454F_5349
CAPABILITY_LOW = 0x504B_534D_5035_0001
REQUEST_CHECKSUM_SEED = 0x4950_4952_4551_0001
RESPONSE_CHECKSUM_SEED = 0x4950_4952_5350_0001
SHOOTDOWN_MAGIC = 0x504B_534D_5035_544C
SHOOTDOWN_VERSION = 2
SHOOTDOWN_STATE_ACKED = 3
SHOOTDOWN_STATE_TIMED_OUT = 4
SHOOTDOWN_REQUEST_CHECKSUM_SEED = 0x5348_4F4F_5452_4551
SHOOTDOWN_RESPONSE_CHECKSUM_SEED = 0x5348_4F4F_5452_5350
AGGREGATE_FNV_OFFSET = 0xCBF2_9CE4_8422_2325
AGGREGATE_FNV_PRIME = 0x0000_0100_0000_01B3
AGGREGATE_ROOT_DOMAIN = 0x524F_4F54_0000_0001
RETIRED_GENERATION = 1
ACTIVE_GENERATION = 2
PROBE_VIRTUAL_ADDRESS = 0x001F_F000
OLD_FRAME_VALUE = 0x504B_534D_5035_4F4C
NEW_FRAME_VALUE = 0x504B_534D_5035_4E57

OPERATIONS = {
    1: {"name": "reschedule", "vector": 224, "payload": 0, "result": 0x5253_4348_4544_0001},
    2: {"name": "shootdown_remote_invlpg", "vector": 225, "payload": 2, "result": 0x5348_4F4F_5400_0002},
    3: {"name": "call_allowlist_noop", "vector": 226, "payload": 0x504B_4E4F_4F50_0001, "result": 0x4341_4C4C_4E4F_4F50},
    4: {"name": "diagnostic", "vector": 227, "payload": 0x504B_4449_4147_0001, "result": 0x4449_4147_4E4F_0001},
    5: {"name": "panic_notice", "vector": 228, "payload": 0x504B_5041_4E49_0001, "result": 0x5041_4E49_4300_0001},
    6: {"name": "stop", "vector": 229, "payload": 0x504B_5354_4F50_0001, "result": 0x5354_4F50_0000_0001},
}

IMPLEMENTATION_INPUTS = (
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/acpi.rs",
    "native/kernel/src/interrupt_time.rs",
    "native/kernel/src/physical_memory.rs",
    "native/kernel/src/smp.rs",
    "native/kernel/src/smp_runtime.rs",
    "native/kernel/src/smp_ipi.rs",
    "native/kernel/src/virtual_memory.rs",
    "native/kernel/src/xstate.rs",
    "native/kmap/src/lib.rs",
    "runtime/native_kernel_smp_ipi.py",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-map-contract.json",
    "specs/native-kernel-smp-ipi-contract.json",
    "specs/native-kernel-smp-ipi-contract.schema.json",
    "specs/native-kernel-smp-ipi-readiness.schema.json",
    "tools/qualify_native_kernel_smp_ipi.py",
    "tests/test_native_kernel_smp_ipi.py",
    "docs/native-kernel-smp-ipi.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N8-PKSMP5-MARKER-OMISSION",
    "NEG-N8-PKSMP5-MARKER-ORDER",
    "NEG-N8-PKSMP5-MARKER-DUPLICATE",
    "NEG-N8-PKSMP5-TRANSFER-PREFIX-SELECTOR-MATRIX",
    "NEG-N8-PKSMP5-TOPOLOGY-FIELD-MATRIX",
    "NEG-N8-PKSMP5-PARTIAL-ROLLBACK-FIELD-MATRIX",
    "NEG-N8-PKSMP5-RETRY-FIELD-MATRIX",
    "NEG-N8-PKSMP5-AP0-FIELD-MATRIX",
    "NEG-N8-PKSMP5-AP1-FIELD-MATRIX",
    "NEG-N8-PKSMP5-AP2-FIELD-MATRIX",
    "NEG-N8-PKSMP5-SHOOTDOWN-FIELD-MATRIX",
    "NEG-N8-PKSMP5-LIFECYCLE-FIELD-MATRIX",
    "NEG-N8-PKSMP5-RELEASE-FIELD-MATRIX",
    "NEG-N8-PKSMP5-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N8-PKSMP5-SOURCE-AUDIT",
    "NEG-N8-PKSMP5-LINKED-INVLPG-SCOPE",
    "NEG-N8-PKSMP5-RESOURCE-LAYOUT-MODEL",
    "NEG-N8-PKSMP5-REQUEST-CAPABILITY-MODEL",
    "NEG-N8-PKSMP5-REQUEST-VECTOR-MODEL",
    "NEG-N8-PKSMP5-REQUEST-SEQUENCE-MODEL",
    "NEG-N8-PKSMP5-SHOOTDOWN-REQUEST-BINDING-MODEL",
    "NEG-N8-PKSMP5-SHOOTDOWN-ACK-BINDING-MODEL",
    "NEG-N8-PKSMP5-STALE-GENERATION-MODEL",
    "NEG-N8-PKSMP5-TARGET-MASK-MODEL",
    "NEG-N8-PKSMP5-PREACK-RECLAIM-MODEL",
    "NEG-N8-PKSMP5-EXACT-TOPOLOGY-MODEL",
    "NEG-N8-PKSMP5-PARTIAL-ROLLBACK-MODEL",
    "NEG-N8-PKSMP5-DUPLICATE-ACK-MODEL",
    "NEG-N8-PKSMP5-AGGREGATE-ACK-MODEL",
    "NEG-N8-PKSMP5-RELEASE-ACCOUNTING-MODEL",
)

EARLY = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-EARLY PASS contract=(?P<contract>PKSMP5) selector=(?P<selector>[0-9]+) bsp=(?P<bsp>[0-9]+) if=(?P<iflag>[0-9]+) stack=validated_by_wrapper serial=initialized$")
TOPOLOGY = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-TOPOLOGY PASS contract=(?P<contract>PKSMP5) processors=(?P<processors>[0-9]+) enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) target_apic_ids=(?P<targets>[0-9,]+) target_mask=0x(?P<mask>[0-9A-F]{16}) apic_physical=0x(?P<apic>[0-9A-F]{16}) selection=(?P<selection>[a-z_]+)$")
PARTIAL = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-PARTIAL-ROLLBACK PASS contract=(?P<contract>PKSMP5) started_mask=0x(?P<started>[0-9A-F]{16}) timeout_apic_id=(?P<timeout_apic>[0-9]+) timeout_mask=0x(?P<timeout_mask>[0-9A-F]{16}) timeout_count=(?P<timeouts>[0-9]+) parked_mask=0x(?P<parked>[0-9A-F]{16}) released_mask=0x(?P<released>[0-9A-F]{16}) resource_pages=(?P<resource_pages>[0-9]+) frame_pages=(?P<frame_pages>[0-9]+) zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) fresh_allocation_required=(?P<fresh>[0-9]+)$")
RETRY = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-RETRY PASS contract=(?P<contract>PKSMP5) retry_count=(?P<retry>[0-9]+) partial_rollback_count=(?P<rollbacks>[0-9]+) started_mask=0x(?P<started>[0-9A-F]{16}) online_mask=0x(?P<online>[0-9A-F]{16}) simultaneous_online=(?P<simultaneous>[0-9]+)$")
AP = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-AP PASS contract=(?P<contract>PKSMP5) ap_index=(?P<index>[0-9]+) apic_id=(?P<apic_id>[0-9]+) physical_start=0x(?P<start>[0-9A-F]{16}) pages=(?P<pages>[0-9]+) sipi_vector=(?P<vector>[0-9]+) trampoline_bytes=(?P<trampoline>[0-9]+) allocation_sequence=(?P<allocation>[0-9]+) frame_allocation_sequences=(?P<frame_allocations>[0-9,]+) frame_release_sequences=(?P<frame_releases>[0-9,]+) resource_release_sequence=(?P<resource_release>[0-9]+) service_state=(?P<service>[0-9]+) mailbox_state=(?P<mailbox>[0-9]+) runtime_state=(?P<runtime>[0-9]+) deliveries=(?P<deliveries>[0-9]+) accepted=(?P<accepted>[0-9]+) denied=(?P<denied>[0-9]+) eois=(?P<eois>[0-9]+) diagnostic=(?P<diagnostic>[0-9]+) shootdown=(?P<shootdown>[0-9]+) stop=(?P<stop>[0-9]+) timeout_count=(?P<timeouts>[0-9]+) init_asserts=(?P<asserts>[0-9]+) init_deasserts=(?P<deasserts>[0-9]+) sipis=(?P<sipis>[0-9]+) target_mask=0x(?P<target>[0-9A-F]{16}) ack_mask=0x(?P<ack>[0-9A-F]{16}) invalidations=(?P<invalidations>[0-9]+) baseline_checksum=0x(?P<baseline>[0-9A-F]{16}) runtime_checksum=0x(?P<runtime_checksum>[0-9A-F]{16}) response_checksum=0x(?P<response>[0-9A-F]{16}) tss_busy=(?P<tss>[0-9]+) idt_verified=(?P<idt>[0-9]+) xstate_verified=(?P<xstate>[0-9]+) apic_table_verified=(?P<apic_table>[0-9]+) parked=(?P<parked>[0-9]+)$")
SHOOTDOWN = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-SHOOTDOWN PASS contract=(?P<contract>PKSMP5) target_mask=0x(?P<target>[0-9A-F]{16}) ack_mask=0x(?P<ack>[0-9A-F]{16}) retired_generation=(?P<retired>[0-9]+) active_generation=(?P<active>[0-9]+) invalidations=(?P<invalidations>[0-9]+) root_checksum=0x(?P<roots>[0-9A-F]{16}) old_frame_checksum=0x(?P<old>[0-9A-F]{16}) new_frame_checksum=0x(?P<new>[0-9A-F]{16}) premature_reclaim_rejections=(?P<premature>[0-9]+) reclaim_state=(?P<state>[a-z_]+)$")
LIFECYCLE = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-LIFECYCLE PASS contract=(?P<contract>PKSMP5) started_mask=0x(?P<started>[0-9A-F]{16}) online_mask=0x(?P<online>[0-9A-F]{16}) quiesced_mask=0x(?P<quiesced>[0-9A-F]{16}) parked_mask=0x(?P<parked>[0-9A-F]{16}) validated_mask=0x(?P<validated>[0-9A-F]{16}) released_mask=0x(?P<released>[0-9A-F]{16}) timeout_count=(?P<timeouts>[0-9]+) retry_count=(?P<retry>[0-9]+) partial_rollback_count=(?P<rollbacks>[0-9]+) exact_accounting=(?P<exact>[0-9]+)$")
RELEASE = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-RELEASE PASS contract=(?P<contract>PKSMP5) resource_pages=(?P<resource_pages>[0-9]+) frame_pages=(?P<frame_pages>[0-9]+) resource_zeroed_bytes=(?P<resource_zeroed>[0-9]+) resource_verified_bytes=(?P<resource_verified>[0-9]+) frame_zeroed_bytes=(?P<frame_zeroed>[0-9]+) frame_verified_bytes=(?P<frame_verified>[0-9]+) total_pages=(?P<total>[0-9]+) capability_revoked=(?P<capability>[0-9]+) runtime_revoked=(?P<runtime>[0-9]+) mmio_revoked=(?P<mmio>[0-9]+) pic_restored=(?P<pic>[0-9]+) hpet_restored=(?P<hpet>[0-9]+) apic_base_restored=(?P<apic>[a-z_]+)$")
RESULT = re.compile(r"^POOLEOS:KERNEL:SMP-MULTI-RESULT PASS contract=(?P<contract>PKSMP5) profile=(?P<profile>sandybridge_x87_sse_four_vcpu) aps=(?P<aps>[0-9]+) simultaneous_online=(?P<simultaneous>[0-9]+) partial_start_timeout=(?P<partial_timeout>[0-9]+) partial_rollback=(?P<rollback>[0-9]+) fresh_retry=(?P<retry>[0-9]+) target_mask=0x(?P<target>[0-9A-F]{16}) ack_mask=0x(?P<ack>[0-9A-F]{16}) tlb_invalidations=(?P<invalidations>[0-9]+) no_reuse_before_all_acks=(?P<no_reuse>[0-9]+) stop_quiesced=(?P<quiesced>[0-9]+) ap_parked=(?P<parked>[0-9]+) resources_released=(?P<released>[0-9]+) scheduler=(?P<scheduler>[0-9]+) general_broadcast=(?P<broadcast>[0-9]+) target_hardware=(?P<target_hardware>[0-9]+) signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) production=(?P<production>[0-9]+) terminal=(?P<terminal>[a-z_]+)$")


class KernelSmpIpiError(RuntimeError):
    """Raised when PKSMP5 data or evidence violates the frozen contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSmpIpiError(message)


def _match(pattern: re.Pattern[str], marker: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    _require(match is not None, f"PKSMP5 {label} marker violates its contract")
    assert match is not None
    return match


def _dec(match: re.Match[str], name: str) -> int:
    return int(match.group(name), 10)


def _hex(match: re.Match[str], name: str) -> int:
    return int(match.group(name), 16)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelSmpIpiError(f"{path} is not a JSON object")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    data = (root / relative).read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, path) for path in IMPLEMENTATION_INPUTS]}


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    issues = validate_json(contract, read_json(root / CONTRACT_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("required negative controls diverge")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    issues = validate_json(readiness, read_json(root / READINESS_SCHEMA_RELATIVE))
    errors = [f"schema {issue.path}: {issue.message}" for issue in issues]
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("readiness input bindings are stale")
    controls = readiness.get("negative_controls", [])
    ids = [item.get("id") for item in controls if isinstance(item, dict)]
    if ids != list(NEGATIVE_CONTROL_IDS):
        errors.append("readiness negative-control order diverges")
    return errors


def resource_layout(start_page: int, page_count: int) -> dict[str, Any]:
    _require(start_page > 0 and page_count == RESOURCE_PAGE_COUNT, "PKSMP5 resource geometry changed")
    start = start_page * PAGE_BYTES
    end = start + page_count * PAGE_BYTES
    _require(end <= 0x10_0000 and start_page <= 0xFF, "PKSMP5 resources escaped SIPI memory")
    roles = {
        "trampoline": [0], "tables": [1, 2, 3, 4], "rsp0": [6, 7, 8, 9],
        "local": [12], "descriptors": [15], "idt": [18], "ist1": [21, 22],
        "ist2": [25, 26], "xstate": [29], "apic_page_table": [31],
        "guards": [5, 10, 11, 13, 14, 16, 17, 19, 20, 23, 24, 27, 28, 30],
    }
    flattened = sorted(offset for values in roles.values() for offset in values)
    _require(flattened == list(range(RESOURCE_PAGE_COUNT)), "PKSMP5 resource roles are incomplete")
    return {
        "start": start, "end": end, "sipi_vector": start_page,
        "pml4": start + PAGE_BYTES, "local": start + 12 * PAGE_BYTES,
        "apic_page_table": start + 31 * PAGE_BYTES, "roles": roles,
    }


def local_target_mask(apic_id: int) -> int:
    _require(0 < apic_id < 64, "PKSMP5 APIC ID cannot form a target bit")
    return 1 << apic_id


def validate_exact_topology(processors: int, enabled: int, bsp_apic_id: int, targets: tuple[int, ...]) -> None:
    _require((processors, enabled, bsp_apic_id) == (4, 4, 0), "PKSMP5 exact topology changed")
    _require(targets == EXPECTED_APIC_IDS and len(set(targets)) == AP_COUNT, "PKSMP5 APIC ownership changed")
    _require(sum(local_target_mask(value) for value in targets) == TARGET_CPU_MASK, "PKSMP5 target mask changed")


def request_checksum(request: dict[str, int]) -> int:
    return REQUEST_CHECKSUM_SEED ^ request["capability_high"] ^ request["capability_low"] ^ request["attempt"] ^ request["sequence"] ^ request["payload"] ^ request["operation"] ^ request["vector"] ^ request["target_apic_id"]


def canonical_request(attempt: int, sequence: int, operation: int, target_apic_id: int) -> dict[str, int]:
    _require(operation in OPERATIONS, "PKSMP5 operation is not allowlisted")
    request = {
        "capability_high": CAPABILITY_HIGH, "capability_low": CAPABILITY_LOW,
        "attempt": attempt, "sequence": sequence, "operation": operation,
        "vector": int(OPERATIONS[operation]["vector"]), "target_apic_id": target_apic_id,
        "status": 1, "payload": int(OPERATIONS[operation]["payload"]),
    }
    request["checksum"] = request_checksum(request)
    return request


def validate_request(request: dict[str, int], handler_operation: int, target_apic_id: int, prior_attempt: int, last_sequence: int) -> None:
    _require(request["status"] == 1, "PKSMP5 request is not armed")
    _require((request["capability_high"], request["capability_low"]) == (CAPABILITY_HIGH, CAPABILITY_LOW), "PKSMP5 capability mismatch")
    _require(request["attempt"] == prior_attempt + 1, "PKSMP5 attempt replay control failed")
    _require(request["operation"] == handler_operation and handler_operation in OPERATIONS, "PKSMP5 operation mismatch")
    _require(request["vector"] == OPERATIONS[handler_operation]["vector"], "PKSMP5 vector mismatch")
    _require(request["target_apic_id"] == target_apic_id, "PKSMP5 target mismatch")
    _require(request["checksum"] == request_checksum(request), "PKSMP5 request checksum mismatch")
    _require(request["sequence"] == last_sequence + 1, "PKSMP5 stale or duplicate sequence")
    _require(request["payload"] == OPERATIONS[handler_operation]["payload"], "PKSMP5 payload mismatch")


def response_checksum(values: dict[str, int]) -> int:
    result = RESPONSE_CHECKSUM_SEED
    for name in ("ack_attempt", "ack_sequence", "result", "last_accepted_sequence", "ack_operation", "ack_status", "ack_error", "delivery_count", "accepted_count", "denied_count"):
        result ^= values[name]
    return result


def shootdown_request_checksum(request: dict[str, int]) -> int:
    return SHOOTDOWN_REQUEST_CHECKSUM_SEED ^ request["root_physical"] ^ request["virtual_address"] ^ request["retired_generation"] ^ request["active_generation"] ^ request["target_mask"] ^ request["old_frame_physical"] ^ request["new_frame_physical"]


def canonical_shootdown_request(root_physical: int, old_frame_physical: int, new_frame_physical: int, target_apic_id: int = 1) -> dict[str, int]:
    request = {
        "root_physical": root_physical, "virtual_address": PROBE_VIRTUAL_ADDRESS,
        "retired_generation": RETIRED_GENERATION, "active_generation": ACTIVE_GENERATION,
        "target_mask": local_target_mask(target_apic_id), "old_frame_physical": old_frame_physical,
        "new_frame_physical": new_frame_physical,
    }
    request["checksum"] = shootdown_request_checksum(request)
    return request


def validate_shootdown_request(request: dict[str, int], expected_root: int, last_ack_generation: int, target_apic_id: int = 1) -> None:
    _require(request["root_physical"] == expected_root and expected_root != 0 and expected_root % PAGE_BYTES == 0, "PKSMP5 shootdown root is invalid")
    _require(request["virtual_address"] == PROBE_VIRTUAL_ADDRESS and request["virtual_address"] % PAGE_BYTES == 0, "PKSMP5 shootdown address is invalid")
    _require(request["retired_generation"] == RETIRED_GENERATION and request["active_generation"] == RETIRED_GENERATION + 1 and request["active_generation"] > last_ack_generation, "PKSMP5 shootdown generation is stale")
    _require(request["target_mask"] == local_target_mask(target_apic_id), "PKSMP5 local target mask changed")
    _require(request["old_frame_physical"] != request["new_frame_physical"] and request["old_frame_physical"] != 0 and request["new_frame_physical"] != 0 and request["old_frame_physical"] % PAGE_BYTES == 0 and request["new_frame_physical"] % PAGE_BYTES == 0, "PKSMP5 frame binding is invalid")
    _require(request["checksum"] == shootdown_request_checksum(request), "PKSMP5 shootdown request checksum mismatch")


def shootdown_response_checksum(snapshot: dict[str, int]) -> int:
    result = SHOOTDOWN_RESPONSE_CHECKSUM_SEED
    for name in ("root_physical", "virtual_address", "active_generation", "target_mask", "ack_mask", "observed_before", "observed_after", "invalidation_count", "last_ack_generation", "state", "error"):
        result ^= snapshot[name]
    return result


def canonical_shootdown_snapshot(request: dict[str, int], timeout_count: int = 0) -> dict[str, int]:
    snapshot = {
        "magic": SHOOTDOWN_MAGIC, "version": SHOOTDOWN_VERSION, "state": SHOOTDOWN_STATE_ACKED,
        "error": 0, **{name: request[name] for name in ("root_physical", "virtual_address", "retired_generation", "active_generation", "target_mask", "old_frame_physical", "new_frame_physical")},
        "ack_mask": request["target_mask"], "observed_before": OLD_FRAME_VALUE,
        "observed_after": NEW_FRAME_VALUE, "invalidation_count": 1,
        "request_checksum": request["checksum"], "response_checksum": 0,
        "last_ack_generation": request["active_generation"], "timeout_count": timeout_count,
        "reclaim_state": 3,
    }
    snapshot["response_checksum"] = shootdown_response_checksum(snapshot)
    return snapshot


def validate_shootdown_ack(snapshot: dict[str, int], request: dict[str, int], target_apic_id: int = 1) -> None:
    validate_shootdown_request(request, request["root_physical"], 0, target_apic_id)
    _require((snapshot["magic"], snapshot["version"], snapshot["state"], snapshot["error"]) == (SHOOTDOWN_MAGIC, SHOOTDOWN_VERSION, SHOOTDOWN_STATE_ACKED, 0), "PKSMP5 acknowledgement state changed")
    for name in ("root_physical", "virtual_address", "retired_generation", "active_generation", "target_mask", "old_frame_physical", "new_frame_physical"):
        _require(snapshot[name] == request[name], f"PKSMP5 acknowledgement {name} mismatch")
    _require(snapshot["ack_mask"] == local_target_mask(target_apic_id), "PKSMP5 acknowledgement mask mismatch")
    _require(snapshot["observed_before"] == OLD_FRAME_VALUE and snapshot["observed_after"] == NEW_FRAME_VALUE and snapshot["invalidation_count"] == 1 and snapshot["last_ack_generation"] == ACTIVE_GENERATION, "PKSMP5 invalidation receipt changed")
    _require(snapshot["request_checksum"] == request["checksum"] and snapshot["response_checksum"] == shootdown_response_checksum(snapshot), "PKSMP5 acknowledgement checksum mismatch")


class DeferredReclaimModel:
    """Independent three-AP deferred-reclaim model."""

    def __init__(self, requests: dict[str, int] | list[dict[str, int]]) -> None:
        self.requests = [requests] if isinstance(requests, dict) else [item.copy() for item in requests]
        for index, request in enumerate(self.requests):
            validate_shootdown_request(request, request["root_physical"], 0, EXPECTED_APIC_IDS[index])
        self.stage = "prepared"
        self.ack_mask = 0

    def arm(self) -> None:
        _require(self.stage in ("prepared", "timed_out"), "PKSMP5 reclaim arm transition changed")
        self.stage = "armed"

    def timeout(self) -> None:
        _require(self.stage == "armed", "PKSMP5 reclaim timeout transition changed")
        self.stage = "timed_out"

    def retry(self) -> None:
        self.arm()

    def acknowledge(self, snapshot: dict[str, int], target_apic_id: int = 1) -> None:
        _require(self.stage in ("armed", "acknowledging"), "PKSMP5 acknowledgement arrived out of state")
        index = EXPECTED_APIC_IDS.index(target_apic_id)
        mask = local_target_mask(target_apic_id)
        _require(self.ack_mask & mask == 0, "PKSMP5 duplicate acknowledgement")
        validate_shootdown_ack(snapshot, self.requests[index], target_apic_id)
        self.ack_mask |= mask
        self.stage = "acknowledging"

    def authorize(self) -> None:
        expected = sum(request["target_mask"] for request in self.requests)
        _require(self.stage == "acknowledging" and self.ack_mask == expected, "PKSMP5 reclaim authorization preceded exact acknowledgements")
        self.stage = "authorized"

    def release(self) -> None:
        _require(self.stage == "authorized", "PKSMP5 reclaim release preceded authorization")
        self.stage = "released"


class MultiApLifecycleModel:
    """Independent partial-start rollback and fresh-retry model."""

    def __init__(self) -> None:
        self.stage = "empty"

    def partial(self, started: int, timeout_mask: int, parked: int, released: int) -> None:
        _require(self.stage == "empty" and started == PARTIAL_STARTED_MASK, "PKSMP5 partial-start mask changed")
        _require(timeout_mask == OFFLINE_CPU_MASK and parked == started and released == TARGET_CPU_MASK, "PKSMP5 partial rollback is incomplete")
        self.stage = "rolled_back"

    def retry(self, started: int, online: int) -> None:
        _require(self.stage == "rolled_back" and started == TARGET_CPU_MASK and online == TARGET_CPU_MASK, "PKSMP5 retry topology is incomplete")
        self.stage = "online"

    def complete(self, quiesced: int, parked: int, validated: int, released: int) -> None:
        _require(self.stage == "online" and (quiesced, parked, validated, released) == (TARGET_CPU_MASK,) * 4, "PKSMP5 final lifecycle mask changed")
        self.stage = "released"


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [*markers[:BOOT_TRANSFER_MARKER_COUNT], *markers[COMMON_KERNEL_MARKER_START:COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT]]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSmpIpiError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def _csv_numbers(value: str) -> tuple[int, ...]:
    return tuple(int(item, 10) for item in value.split(","))


def aggregate_address_checksum(values: list[tuple[int, int]], domain: int) -> int:
    checksum = AGGREGATE_FNV_OFFSET ^ domain
    for target_mask, address in values:
        for value in (target_mask, address):
            for byte in value.to_bytes(8, "little"):
                checksum ^= byte
                checksum = (checksum * AGGREGATE_FNV_PRIME) & U64_MASK
    return checksum or domain


def validate_receipt_sequences(aps: list[dict[str, Any]]) -> None:
    _require(len(aps) == AP_COUNT, "PKSMP5 resource receipt AP count changed")
    allocations: list[int] = []
    releases: list[int] = []
    for ap in aps:
        frame_allocations = ap["frame_allocation_sequences"]
        frame_releases = ap["frame_release_sequences"]
        resource_allocation = ap["allocation_sequence"]
        resource_release = ap["resource_release_sequence"]
        _require(len(frame_allocations) == 2 and len(frame_releases) == 2, "PKSMP5 frame receipt shape changed")
        _require(resource_allocation < min(frame_allocations), "PKSMP5 frame allocation preceded its private resource")
        _require(all(release > allocation for release, allocation in zip(frame_releases, frame_allocations, strict=True)), "PKSMP5 frame release preceded allocation")
        _require(frame_releases[0] < frame_releases[1] < resource_release, "PKSMP5 per-AP release order changed")
        allocations.extend((resource_allocation, *frame_allocations))
        releases.extend((*frame_releases, resource_release))
    _require(all(sequence > 0 for sequence in (*allocations, *releases)), "PKSMP5 receipt sequence is not positive")
    _require(len(set(allocations)) == 3 * AP_COUNT, "PKSMP5 allocation receipt sequence reused")
    _require(len(set(releases)) == 3 * AP_COUNT, "PKSMP5 release receipt sequence reused")
    _require(set(allocations).isdisjoint(releases), "PKSMP5 allocation and release receipts alias")
    _require(max(allocations) < min(releases), "PKSMP5 release preceded complete retry allocation")


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSMP5 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10), 10) == SELECTOR, "PKSMP5 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    topology = _match(TOPOLOGY, markers[30], "topology")
    partial = _match(PARTIAL, markers[31], "partial rollback")
    retry = _match(RETRY, markers[32], "retry")
    ap_matches = [_match(AP, markers[33 + index], f"AP {index}") for index in range(AP_COUNT)]
    shootdown = _match(SHOOTDOWN, markers[36], "shootdown")
    lifecycle = _match(LIFECYCLE, markers[37], "lifecycle")
    release = _match(RELEASE, markers[38], "release")
    result = _match(RESULT, markers[39], "result")

    _require(tuple(_dec(early, name) for name in ("selector", "bsp", "iflag")) == (14, 1, 0), "PKSMP5 early state changed")
    targets = _csv_numbers(topology.group("targets"))
    validate_exact_topology(_dec(topology, "processors"), _dec(topology, "enabled"), _dec(topology, "bsp"), targets)
    _require(_hex(topology, "mask") == TARGET_CPU_MASK and _hex(topology, "apic") == APIC_PHYSICAL_ADDRESS and topology.group("selection") == "exact_enabled_legacy_apic_topology", "PKSMP5 topology policy changed")

    lifecycle_model = MultiApLifecycleModel()
    lifecycle_model.partial(_hex(partial, "started"), _hex(partial, "timeout_mask"), _hex(partial, "parked"), _hex(partial, "released"))
    _require((_dec(partial, "timeout_apic"), _dec(partial, "timeouts"), _dec(partial, "resource_pages"), _dec(partial, "frame_pages"), _dec(partial, "zeroed"), _dec(partial, "verified"), _dec(partial, "fresh")) == (4, 1, 96, 6, 417792, 417792, 1), "PKSMP5 partial rollback receipt changed")
    lifecycle_model.retry(_hex(retry, "started"), _hex(retry, "online"))
    _require((_dec(retry, "retry"), _dec(retry, "rollbacks"), _dec(retry, "simultaneous")) == (1, 1, 1), "PKSMP5 retry receipt changed")

    aps: list[dict[str, Any]] = []
    layouts: list[dict[str, Any]] = []
    response_expected = response_checksum({
        "ack_attempt": 4, "ack_sequence": 3, "result": int(OPERATIONS[6]["result"]),
        "last_accepted_sequence": 3, "ack_operation": 6, "ack_status": 1, "ack_error": 0,
        "delivery_count": 4, "accepted_count": 3, "denied_count": 1,
    })
    for index, match in enumerate(ap_matches):
        _require((_dec(match, "index"), _dec(match, "apic_id")) == (index, EXPECTED_APIC_IDS[index]), "PKSMP5 AP identity changed")
        layout = resource_layout(_hex(match, "start") // PAGE_BYTES, _dec(match, "pages"))
        _require(_hex(match, "start") == layout["start"] and _dec(match, "vector") == layout["sipi_vector"], "PKSMP5 AP resource address changed")
        _require(0 < _dec(match, "trampoline") <= PAGE_BYTES, "PKSMP5 trampoline escaped one page")
        _require(tuple(_dec(match, name) for name in ("service", "mailbox", "runtime", "deliveries", "accepted", "denied", "eois", "diagnostic", "shootdown", "stop", "timeouts", "asserts", "deasserts", "sipis")) == (4, 3, 5, 4, 3, 1, 4, 1, 1, 1, int(index == 0), 1, 1, 2), "PKSMP5 AP lifecycle receipt changed")
        local_mask = local_target_mask(EXPECTED_APIC_IDS[index])
        _require((_hex(match, "target"), _hex(match, "ack"), _dec(match, "invalidations")) == (local_mask, local_mask, 1), "PKSMP5 AP acknowledgement changed")
        _require(tuple(_dec(match, name) for name in ("tss", "idt", "xstate", "apic_table", "parked")) == (1, 1, 1, 1, 1), "PKSMP5 AP validation receipt changed")
        _require(_hex(match, "baseline") != 0 and _hex(match, "runtime_checksum") != 0 and _hex(match, "baseline") != _hex(match, "runtime_checksum"), "PKSMP5 AP runtime checksums are invalid")
        _require(_hex(match, "response") == response_expected, "PKSMP5 AP response checksum changed")
        frame_allocations = _csv_numbers(match.group("frame_allocations"))
        frame_releases = _csv_numbers(match.group("frame_releases"))
        layouts.append(layout)
        aps.append({"index": index, "apic_id": EXPECTED_APIC_IDS[index], "layout": layout, "allocation_sequence": _dec(match, "allocation"), "frame_allocation_sequences": frame_allocations, "frame_release_sequences": frame_releases, "resource_release_sequence": _dec(match, "resource_release"), "trampoline_bytes": _dec(match, "trampoline"), "response_checksum": response_expected})
    validate_receipt_sequences(aps)
    _require([item["start"] for item in layouts] == [0x1000, 0x23000, 0x45000], "PKSMP5 private resource placement changed")
    _require(len({item["pml4"] for item in layouts}) == AP_COUNT, "PKSMP5 private roots alias")

    requests = [canonical_shootdown_request(layout["pml4"], layout["end"], layout["end"] + PAGE_BYTES, EXPECTED_APIC_IDS[index]) for index, layout in enumerate(layouts)]
    reclaim = DeferredReclaimModel(requests)
    reclaim.arm()
    reclaim.timeout()
    reclaim.retry()
    for index, request in enumerate(requests):
        reclaim.acknowledge(canonical_shootdown_snapshot(request, int(index == 0)), EXPECTED_APIC_IDS[index])
        if index + 1 != AP_COUNT:
            try:
                reclaim.authorize()
            except KernelSmpIpiError:
                pass
            else:
                raise KernelSmpIpiError("PKSMP5 reclaim authorized before every AP acknowledged")
    reclaim.authorize()
    reclaim.release()
    _require((_hex(shootdown, "target"), _hex(shootdown, "ack"), _dec(shootdown, "retired"), _dec(shootdown, "active"), _dec(shootdown, "invalidations"), _dec(shootdown, "premature"), shootdown.group("state")) == (TARGET_CPU_MASK, TARGET_CPU_MASK, 1, 2, 3, 2, "released"), "PKSMP5 aggregate shootdown changed")
    expected_root_checksum = aggregate_address_checksum(
        [(local_target_mask(EXPECTED_APIC_IDS[index]), layout["pml4"]) for index, layout in enumerate(layouts)],
        AGGREGATE_ROOT_DOMAIN,
    )
    _require(_hex(shootdown, "roots") == expected_root_checksum, "PKSMP5 aggregate root checksum changed")
    _require(_hex(shootdown, "old") != 0 and _hex(shootdown, "new") != 0 and _hex(shootdown, "old") != _hex(shootdown, "new"), "PKSMP5 aggregate frame checksums are invalid")

    lifecycle_model.complete(_hex(lifecycle, "quiesced"), _hex(lifecycle, "parked"), _hex(lifecycle, "validated"), _hex(lifecycle, "released"))
    _require((_hex(lifecycle, "started"), _hex(lifecycle, "online")) == (TARGET_CPU_MASK, TARGET_CPU_MASK), "PKSMP5 lifecycle start changed")
    _require(tuple(_dec(lifecycle, name) for name in ("timeouts", "retry", "rollbacks", "exact")) == (1, 1, 1, 1), "PKSMP5 lifecycle counters changed")

    _require(tuple(_dec(release, name) for name in ("resource_pages", "frame_pages", "resource_zeroed", "resource_verified", "frame_zeroed", "frame_verified", "total", "capability", "runtime", "mmio", "pic", "hpet")) == (96, 6, 393216, 393216, 24576, 24576, 102, 1, 1, 1, 1, 1), "PKSMP5 release accounting changed")
    _require(release.group("apic") == "unchanged", "PKSMP5 APIC base changed")
    _require(tuple(_dec(result, name) for name in ("aps", "simultaneous", "partial_timeout", "rollback", "retry", "invalidations", "no_reuse", "quiesced", "parked", "released", "scheduler", "broadcast", "target_hardware", "signatures", "authority", "actions", "production")) == (3, 1, 1, 1, 1, 3, 1, 3, 3, 102, 0, 0, 0, 0, 0, 0, 0), "PKSMP5 claim boundary changed")
    _require((_hex(result, "target"), _hex(result, "ack")) == (TARGET_CPU_MASK, TARGET_CPU_MASK), "PKSMP5 result mask changed")
    _require(result.group("terminal") == "halt", "PKSMP5 terminal changed")

    return {
        "transfer_prefix": prefix,
        "topology": {"processors": 4, "enabled": 4, "bsp_apic_id": 0, "target_apic_ids": list(EXPECTED_APIC_IDS), "target_mask": TARGET_CPU_MASK},
        "partial_rollback": {"started_mask": PARTIAL_STARTED_MASK, "offline_apic_id": 4, "timeout_count": 1, "parked_mask": PARTIAL_STARTED_MASK, "released_mask": TARGET_CPU_MASK, "resource_pages": 96, "frame_pages": 6},
        "retry": {"retry_count": 1, "simultaneous_online": True},
        "aps": aps,
        "shootdown": {"target_mask": TARGET_CPU_MASK, "ack_mask": TARGET_CPU_MASK, "invalidation_count": 3, "premature_reclaim_rejections": 2, "stage": reclaim.stage},
        "release": {"resource_pages": 96, "frame_pages": 6, "total_pages": 102, "verified_bytes": 417792},
        "result": {"application_processors_online": 3, "scheduler": 0, "general_broadcast": 0, "target_hardware": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    normalized = markers.copy()
    for index in range(33, 36):
        for field in ("baseline_checksum", "runtime_checksum"):
            normalized[index] = re.sub(rf"{field}=0x[0-9A-F]{{16}}", f"{field}=<validated-dynamic>", normalized[index], count=1)
    return normalized
