"""Independent PKSMP4 remote TLB-shootdown and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSMP4"
SELECTED_MOVE_ID = "N9-SMP-SHOOTDOWN-001"
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
COMPLETION_MARKER = b"POOLEOS:KERNEL:SMP-IPI-RESULT PASS contract=PKSMP4"

PAGE_BYTES = 4096
RESOURCE_PAGE_COUNT = 32
TRAMPOLINE_BYTES = 2564
IDENTITY_MAPPED_PAGE_COUNT = 13
GUARD_PAGE_COUNT = 14
APIC_PAGE_TABLE_OFFSET = 31
APIC_PHYSICAL_ADDRESS = 0xFEE0_0000
APIC_PDPT_INDEX = 3
APIC_PAGE_DIRECTORY_INDEX = 503
APIC_PAGE_TABLE_INDEX = 0
EXTENSION_MAGIC = 0x504B_534D_5034_4950
EXTENSION_VERSION = 2
EXTENSION_BASE_OFFSET = 352
EXTENSION_BYTES = 344
MAILBOX_BYTES = 696
CAPABILITY_HIGH = 0x504F_4F4C_454F_5349
CAPABILITY_LOW = 0x504B_534D_5034_0001
REQUEST_CHECKSUM_SEED = 0x4950_4952_4551_0001
RESPONSE_CHECKSUM_SEED = 0x4950_4952_5350_0001
ACK_ACCEPTED = 1
ACK_DENIED = 2
SERVICE_STATE_QUIESCED = 4
MAILBOX_STATE_QUIESCED = 3
RUNTIME_STATE_QUIESCED = 5

SHOOTDOWN_MAGIC = 0x504B_534D_5034_544C
SHOOTDOWN_VERSION = 1
SHOOTDOWN_STATE_ACKED = 3
SHOOTDOWN_STATE_TIMED_OUT = 4
SHOOTDOWN_ERROR_NONE = 0
SHOOTDOWN_REQUEST_CHECKSUM_SEED = 0x5348_4F4F_5452_4551
SHOOTDOWN_RESPONSE_CHECKSUM_SEED = 0x5348_4F4F_5452_5350
RETIRED_GENERATION = 1
ACTIVE_GENERATION = 2
TARGET_CPU_MASK = 1 << 1
OFFLINE_CPU_MASK = 1 << 2
PROBE_VIRTUAL_ADDRESS = 0x001F_F000
OLD_FRAME_VALUE = 0x504B_534D_5034_4F4C
NEW_FRAME_VALUE = 0x504B_534D_5034_4E57
RECLAIM_BLOCKED = 1
RECLAIM_AUTHORIZED = 2
RECLAIM_RELEASED = 3

OPERATIONS = {
    1: {"name": "reschedule", "vector": 224, "payload": 0x0, "result": 0x5253_4348_4544_0001},
    2: {"name": "shootdown_remote_invlpg", "vector": 225, "payload": ACTIVE_GENERATION, "result": 0x5348_4F4F_5400_0002},
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
    "NEG-N9-PKSMP4-MARKER-OMISSION",
    "NEG-N9-PKSMP4-MARKER-ORDER",
    "NEG-N9-PKSMP4-MARKER-DUPLICATE",
    "NEG-N9-PKSMP4-TRANSFER-PREFIX-SELECTOR-MATRIX",
    "NEG-N9-PKSMP4-TOPOLOGY-FIELD-MATRIX",
    "NEG-N9-PKSMP4-RESOURCE-GEOMETRY-FIELD-MATRIX",
    "NEG-N9-PKSMP4-ONLINE-FIELD-MATRIX",
    "NEG-N9-PKSMP4-ACCEPTED-FIELD-MATRIX",
    "NEG-N9-PKSMP4-DENIAL-FIELD-MATRIX",
    "NEG-N9-PKSMP4-TIMEOUT-FIELD-MATRIX",
    "NEG-N9-PKSMP4-SHOOTDOWN-FIELD-MATRIX",
    "NEG-N9-PKSMP4-STOP-CHECKSUM-FIELD-MATRIX",
    "NEG-N9-PKSMP4-RELEASE-FIELD-MATRIX",
    "NEG-N9-PKSMP4-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N9-PKSMP4-SOURCE-AUDIT",
    "NEG-N9-PKSMP4-LINKED-INVLPG-SCOPE",
    "NEG-N9-PKSMP4-RESOURCE-LAYOUT-MODEL",
    "NEG-N9-PKSMP4-REQUEST-CAPABILITY-MODEL",
    "NEG-N9-PKSMP4-REQUEST-VECTOR-MODEL",
    "NEG-N9-PKSMP4-REQUEST-SEQUENCE-MODEL",
    "NEG-N9-PKSMP4-SHOOTDOWN-REQUEST-BINDING-MODEL",
    "NEG-N9-PKSMP4-SHOOTDOWN-ACK-BINDING-MODEL",
    "NEG-N9-PKSMP4-STALE-GENERATION-MODEL",
    "NEG-N9-PKSMP4-TARGET-MASK-MODEL",
    "NEG-N9-PKSMP4-PREACK-RECLAIM-MODEL",
)

EARLY = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-EARLY PASS contract=(?P<contract>PKSMP4) selector=(?P<selector>[0-9]+) bsp=(?P<bsp>[0-9]+) if=(?P<iflag>[0-9]+) stack=validated_by_wrapper serial=initialized$")
TOPOLOGY = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-TOPOLOGY PASS contract=(?P<contract>PKSMP4) processors=(?P<processors>[0-9]+) enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) target_apic_id=(?P<target>[0-9]+) apic_physical=0x(?P<apic>[0-9A-F]{16}) selection=(?P<selection>[a-z_]+)$")
RESOURCES = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-RESOURCES PASS contract=(?P<contract>PKSMP4) physical_start=0x(?P<start>[0-9A-F]{16}) pages=(?P<pages>[0-9]+) sipi_vector=(?P<vector>[0-9]+) trampoline_bytes=(?P<trampoline>[0-9]+) allocation_sequence=(?P<sequence>[0-9]+) tables=(?P<tables>[0-9]+) mapped_pages=(?P<mapped>[0-9]+) guard_pages=(?P<guards>[0-9]+) apic_pt_offset=(?P<apic_pt>[0-9]+) apic_leaf=(?P<leaf>[a-z_]+) below_1mib=(?P<below>[0-9]+)$")
ONLINE = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-ONLINE PASS contract=(?P<contract>PKSMP4) service_state=(?P<state>[0-9]+) if=(?P<iflag>[0-9]+) vectors=(?P<vectors>[0-9,]+) apic_mmio=0x(?P<apic>[0-9A-F]{16}) apic_table=(?P<table>[0-9]+)$")
ACCEPTED = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-ACCEPTED PASS contract=(?P<contract>PKSMP4) operations=(?P<operations>[a-z_,]+) sequences=(?P<sequences>[0-9,]+) accepted=(?P<accepted>[0-9]+) reschedule=(?P<reschedule>[0-9]+) shootdown=(?P<shootdown>[0-9]+) call_function=(?P<call>[0-9]+) diagnostic=(?P<diagnostic>[0-9]+) panic=(?P<panic>[0-9]+) stop=(?P<stop>[0-9]+)$")
CONTROLS = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-CONTROLS PASS contract=(?P<contract>PKSMP4) invalid_capability=(?P<capability>[0-9]+) vector_mismatch=(?P<vector>[0-9]+) stale_sequence=(?P<stale>[0-9]+) duplicate_sequence=(?P<duplicate>[0-9]+) denied=(?P<denied>[0-9]+) delivery_count=(?P<delivery>[0-9]+) eoi_count=(?P<eoi>[0-9]+) spurious=(?P<spurious>[0-9]+) apic_error=(?P<apic_error>[0-9]+)$")
TIMEOUT = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-TIMEOUT PASS contract=(?P<contract>PKSMP4) operation=(?P<operation>shootdown) target_apic_id=(?P<target>[0-9]+) target_mask=0x(?P<mask>[0-9A-F]{16}) attempt=(?P<attempt>[0-9]+) bounded=(?P<bounded>[0-9]+) offline_cpu=(?P<offline>[0-9]+) retry_same_attempt=(?P<retry>[0-9]+) timeout_count=(?P<count>[0-9]+)$")
SHOOTDOWN = re.compile(r"^POOLEOS:KERNEL:SMP-SHOOTDOWN PASS contract=(?P<contract>PKSMP4) root=0x(?P<root>[0-9A-F]{16}) probe=0x(?P<probe>[0-9A-F]{16}) retired_generation=(?P<retired>[0-9]+) active_generation=(?P<active>[0-9]+) target_mask=0x(?P<target>[0-9A-F]{16}) ack_mask=0x(?P<ack>[0-9A-F]{16}) old_frame=0x(?P<old>[0-9A-F]{16}) new_frame=0x(?P<new>[0-9A-F]{16}) observed_before=0x(?P<before>[0-9A-F]{16}) observed_after=0x(?P<after>[0-9A-F]{16}) invalidations=(?P<invalidations>[0-9]+) last_ack_generation=(?P<last>[0-9]+) premature_reclaim_rejected=(?P<premature>[0-9]+) reclaim_state=(?P<reclaim>[0-9]+) shootdown_checksum=0x(?P<checksum>[0-9A-F]{16})$")
STOP = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-STOP PASS contract=(?P<contract>PKSMP4) ack_attempt=(?P<attempt>[0-9]+) ack_sequence=(?P<sequence>[0-9]+) last_accepted_sequence=(?P<last>[0-9]+) service_state=(?P<service>[0-9]+) mailbox_state=(?P<mailbox>[0-9]+) runtime_state=(?P<runtime>[0-9]+) panic_latched=(?P<panic>[0-9]+) response_checksum=0x(?P<response>[0-9A-F]{16}) baseline_checksum=0x(?P<baseline>[0-9A-F]{16}) runtime_checksum=0x(?P<runtime_checksum>[0-9A-F]{16}) init_asserts=(?P<asserts>[0-9]+) init_deasserts=(?P<deasserts>[0-9]+) sipis=(?P<sipis>[0-9]+) tss_busy=(?P<tss>[0-9]+) idt_verified=(?P<idt>[0-9]+) xstate_verified=(?P<xstate>[0-9]+) apic_table_verified=(?P<apic_table>[0-9]+) final_init=(?P<final_init>[0-9]+) parked=(?P<parked>[0-9]+)$")
RELEASE = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-RELEASE PASS contract=(?P<contract>PKSMP4) release_sequence=(?P<sequence>[0-9]+) zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) frame_allocation_sequences=(?P<frame_allocations>[0-9,]+) frame_release_sequences=(?P<frame_releases>[0-9,]+) frame_zeroed_bytes=(?P<frame_zeroed>[0-9]+) frame_verified_bytes=(?P<frame_verified>[0-9]+) resources_released=(?P<released>[0-9]+) capability_revoked=(?P<capability>[0-9]+) runtime_revoked=(?P<runtime>[0-9]+) mmio_revoked=(?P<mmio>[0-9]+) pic_restored=(?P<pic>[0-9]+) hpet_restored=(?P<hpet>[0-9]+) apic_base_restored=(?P<apic>[a-z_]+)$")
RESULT = re.compile(r"^POOLEOS:KERNEL:SMP-IPI-RESULT PASS contract=(?P<contract>PKSMP4) profile=(?P<profile>sandybridge_x87_sse_two_vcpu) capability_gate=(?P<gate>[a-z_]+) operation_classes=(?P<classes>[0-9]+) valid_deliveries=(?P<valid>[0-9]+) denied_deliveries=(?P<denied>[0-9]+) offline_timeouts=(?P<timeouts>[0-9]+) eois=(?P<eois>[0-9]+) panic_latched=(?P<panic>[0-9]+) stop_quiesced=(?P<quiesced>[0-9]+) ap_parked=(?P<parked>[0-9]+) resources_released=(?P<released>[0-9]+) rollback=(?P<rollback>[a-z_]+) shootdown_remote_invlpg=(?P<shootdown>[0-9]+) tlb_invalidations=(?P<tlb>[0-9]+) generation_retirement=(?P<retirement>[0-9]+) no_reuse_before_retirement=(?P<no_reuse>[0-9]+) call_allowlist_noop=(?P<call>[0-9]+) arbitrary_callback=(?P<callback>[0-9]+) scheduler=(?P<scheduler>[0-9]+) target=(?P<target>[0-9]+) signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) production=(?P<production>[0-9]+) terminal=(?P<terminal>[a-z_]+)$")


class KernelSmpIpiError(RuntimeError):
    """Raised when PKSMP4 data or evidence violates the frozen contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSmpIpiError(message)


def _match(pattern: re.Pattern[str], marker: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    _require(match is not None, f"PKSMP4 {label} marker violates its contract")
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
    _require(start_page > 0 and page_count == RESOURCE_PAGE_COUNT, "PKSMP4 resource geometry changed")
    start = start_page * PAGE_BYTES
    end = start + page_count * PAGE_BYTES
    _require(end <= 0x10_0000 and start_page <= 0xFF, "PKSMP4 resources escaped SIPI memory")
    roles = {
        "trampoline": [0],
        "tables": [1, 2, 3, 4],
        "rsp0": [6, 7, 8, 9],
        "local": [12],
        "descriptors": [15],
        "idt": [18],
        "ist1": [21, 22],
        "ist2": [25, 26],
        "xstate": [29],
        "apic_page_table": [31],
        "guards": [5, 10, 11, 13, 14, 16, 17, 19, 20, 23, 24, 27, 28, 30],
    }
    flattened = sorted(offset for values in roles.values() for offset in values)
    _require(flattened == list(range(RESOURCE_PAGE_COUNT)), "PKSMP4 resource roles are incomplete")
    address = lambda offset: start + offset * PAGE_BYTES
    return {
        "start": start,
        "end": end,
        "sipi_vector": start_page,
        "pml4": address(1),
        "pdpt": address(2),
        "pd": address(3),
        "pt": address(4),
        "local": address(12),
        "idt": address(18),
        "xstate": address(29),
        "apic_page_table": address(31),
        "roles": roles,
    }


def request_checksum(request: dict[str, int]) -> int:
    return (
        REQUEST_CHECKSUM_SEED
        ^ request["capability_high"]
        ^ request["capability_low"]
        ^ request["attempt"]
        ^ request["sequence"]
        ^ request["payload"]
        ^ request["operation"]
        ^ request["vector"]
        ^ request["target_apic_id"]
    )


def canonical_request(attempt: int, sequence: int, operation: int, target_apic_id: int) -> dict[str, int]:
    _require(operation in OPERATIONS, "PKSMP4 operation is not allowlisted")
    request = {
        "capability_high": CAPABILITY_HIGH,
        "capability_low": CAPABILITY_LOW,
        "attempt": attempt,
        "sequence": sequence,
        "operation": operation,
        "vector": int(OPERATIONS[operation]["vector"]),
        "target_apic_id": target_apic_id,
        "status": 1,
        "payload": int(OPERATIONS[operation]["payload"]),
    }
    request["checksum"] = request_checksum(request)
    return request


def validate_request(
    request: dict[str, int],
    handler_operation: int,
    target_apic_id: int,
    prior_attempt: int,
    last_sequence: int,
) -> None:
    _require(request["status"] == 1, "PKSMP4 request is not armed")
    _require((request["capability_high"], request["capability_low"]) == (CAPABILITY_HIGH, CAPABILITY_LOW), "PKSMP4 capability mismatch")
    _require(request["attempt"] == prior_attempt + 1, "PKSMP4 attempt replay control failed")
    _require(request["operation"] == handler_operation and handler_operation in OPERATIONS, "PKSMP4 operation mismatch")
    _require(request["vector"] == OPERATIONS[handler_operation]["vector"], "PKSMP4 vector mismatch")
    _require(request["target_apic_id"] == target_apic_id, "PKSMP4 target mismatch")
    _require(request["checksum"] == request_checksum(request), "PKSMP4 request checksum mismatch")
    _require(request["sequence"] == last_sequence + 1, "PKSMP4 stale or duplicate sequence")
    _require(request["payload"] == OPERATIONS[handler_operation]["payload"], "PKSMP4 payload mismatch")


def response_checksum(values: dict[str, int]) -> int:
    names = (
        "ack_attempt",
        "ack_sequence",
        "result",
        "last_accepted_sequence",
        "ack_operation",
        "ack_status",
        "ack_error",
        "delivery_count",
        "accepted_count",
        "denied_count",
    )
    value = RESPONSE_CHECKSUM_SEED
    for name in names:
        value ^= values[name]
    return value


def shootdown_request_checksum(request: dict[str, int]) -> int:
    return (
        SHOOTDOWN_REQUEST_CHECKSUM_SEED
        ^ request["root_physical"]
        ^ request["virtual_address"]
        ^ request["retired_generation"]
        ^ request["active_generation"]
        ^ request["target_mask"]
        ^ request["old_frame_physical"]
        ^ request["new_frame_physical"]
    )


def canonical_shootdown_request(
    root_physical: int,
    old_frame_physical: int,
    new_frame_physical: int,
) -> dict[str, int]:
    request = {
        "root_physical": root_physical,
        "virtual_address": PROBE_VIRTUAL_ADDRESS,
        "retired_generation": RETIRED_GENERATION,
        "active_generation": ACTIVE_GENERATION,
        "target_mask": TARGET_CPU_MASK,
        "old_frame_physical": old_frame_physical,
        "new_frame_physical": new_frame_physical,
    }
    request["checksum"] = shootdown_request_checksum(request)
    return request


def validate_shootdown_request(
    request: dict[str, int],
    expected_root: int,
    last_ack_generation: int,
) -> None:
    _require(
        request["root_physical"] == expected_root
        and request["root_physical"] != 0
        and request["root_physical"] % PAGE_BYTES == 0,
        "PKSMP4 shootdown root is invalid",
    )
    _require(
        request["virtual_address"] == PROBE_VIRTUAL_ADDRESS
        and request["virtual_address"] % PAGE_BYTES == 0,
        "PKSMP4 shootdown virtual address is invalid",
    )
    _require(
        request["retired_generation"] == RETIRED_GENERATION
        and request["active_generation"] == request["retired_generation"] + 1
        and request["active_generation"] > last_ack_generation,
        "PKSMP4 shootdown generation is stale or malformed",
    )
    _require(request["target_mask"] == TARGET_CPU_MASK, "PKSMP4 shootdown target mask changed")
    _require(
        request["old_frame_physical"] != request["new_frame_physical"]
        and request["old_frame_physical"] != 0
        and request["new_frame_physical"] != 0
        and request["old_frame_physical"] % PAGE_BYTES == 0
        and request["new_frame_physical"] % PAGE_BYTES == 0,
        "PKSMP4 shootdown frame binding is invalid",
    )
    _require(
        request["checksum"] == shootdown_request_checksum(request),
        "PKSMP4 shootdown request checksum mismatch",
    )


def shootdown_response_checksum(snapshot: dict[str, int]) -> int:
    names = (
        "root_physical",
        "virtual_address",
        "active_generation",
        "target_mask",
        "ack_mask",
        "observed_before",
        "observed_after",
        "invalidation_count",
        "last_ack_generation",
        "state",
        "error",
    )
    value = SHOOTDOWN_RESPONSE_CHECKSUM_SEED
    for name in names:
        value ^= snapshot[name]
    return value


def canonical_shootdown_snapshot(request: dict[str, int]) -> dict[str, int]:
    snapshot = {
        "magic": SHOOTDOWN_MAGIC,
        "version": SHOOTDOWN_VERSION,
        "state": SHOOTDOWN_STATE_ACKED,
        "error": SHOOTDOWN_ERROR_NONE,
        **{name: request[name] for name in (
            "root_physical",
            "virtual_address",
            "retired_generation",
            "active_generation",
            "target_mask",
            "old_frame_physical",
            "new_frame_physical",
        )},
        "ack_mask": request["target_mask"],
        "observed_before": OLD_FRAME_VALUE,
        "observed_after": NEW_FRAME_VALUE,
        "invalidation_count": 1,
        "request_checksum": request["checksum"],
        "response_checksum": 0,
        "last_ack_generation": request["active_generation"],
        "timeout_count": 1,
        "reclaim_state": RECLAIM_RELEASED,
    }
    snapshot["response_checksum"] = shootdown_response_checksum(snapshot)
    return snapshot


def validate_shootdown_ack(snapshot: dict[str, int], request: dict[str, int]) -> None:
    _require(
        (snapshot["magic"], snapshot["version"], snapshot["state"], snapshot["error"])
        == (SHOOTDOWN_MAGIC, SHOOTDOWN_VERSION, SHOOTDOWN_STATE_ACKED, SHOOTDOWN_ERROR_NONE),
        "PKSMP4 shootdown acknowledgement state changed",
    )
    for name in (
        "root_physical",
        "virtual_address",
        "retired_generation",
        "active_generation",
        "target_mask",
        "old_frame_physical",
        "new_frame_physical",
    ):
        _require(snapshot[name] == request[name], f"PKSMP4 shootdown acknowledgement {name} mismatch")
    _require(snapshot["ack_mask"] == request["target_mask"], "PKSMP4 shootdown acknowledgement mask mismatch")
    _require(
        snapshot["observed_before"] == OLD_FRAME_VALUE
        and snapshot["observed_after"] == NEW_FRAME_VALUE
        and snapshot["invalidation_count"] == 1
        and snapshot["last_ack_generation"] == request["active_generation"],
        "PKSMP4 shootdown invalidation receipt changed",
    )
    _require(snapshot["request_checksum"] == request["checksum"], "PKSMP4 shootdown request receipt mismatch")
    _require(
        snapshot["response_checksum"] == shootdown_response_checksum(snapshot),
        "PKSMP4 shootdown response checksum mismatch",
    )


class DeferredReclaimModel:
    """Independent state model for the one-generation PKSMP4 retirement proof."""

    def __init__(self, request: dict[str, int]) -> None:
        validate_shootdown_request(request, request["root_physical"], 0)
        self.request = request.copy()
        self.stage = "prepared"

    def arm(self) -> None:
        _require(self.stage == "prepared", "PKSMP4 reclaim arm transition changed")
        self.stage = "armed"

    def timeout(self) -> None:
        _require(self.stage == "armed", "PKSMP4 reclaim timeout transition changed")
        self.stage = "timed_out"

    def retry(self) -> None:
        _require(self.stage == "timed_out", "PKSMP4 reclaim retry transition changed")
        self.stage = "armed"

    def acknowledge(self, snapshot: dict[str, int]) -> None:
        _require(self.stage == "armed", "PKSMP4 reclaim acknowledgement arrived out of state")
        validate_shootdown_ack(snapshot, self.request)
        self.stage = "acknowledged"

    def authorize(self) -> None:
        _require(self.stage == "acknowledged", "PKSMP4 reclaim authorization preceded acknowledgement")
        self.stage = "authorized"

    def release(self) -> None:
        _require(self.stage == "authorized", "PKSMP4 reclaim release preceded authorization")
        self.stage = "released"


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [
        *markers[:BOOT_TRANSFER_MARKER_COUNT],
        *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT],
    ]
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


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSMP4 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10), 10) == SELECTOR, "PKSMP4 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    topology = _match(TOPOLOGY, markers[30], "topology")
    resources = _match(RESOURCES, markers[31], "resources")
    online = _match(ONLINE, markers[32], "online")
    accepted = _match(ACCEPTED, markers[33], "accepted")
    controls = _match(CONTROLS, markers[34], "controls")
    timeout = _match(TIMEOUT, markers[35], "timeout")
    shootdown = _match(SHOOTDOWN, markers[36], "shootdown")
    stop = _match(STOP, markers[37], "stop")
    release = _match(RELEASE, markers[38], "release")
    result = _match(RESULT, markers[39], "result")

    _require(tuple(_dec(early, name) for name in ("selector", "bsp", "iflag")) == (14, 1, 0), "PKSMP4 early state changed")
    _require(tuple(_dec(topology, name) for name in ("processors", "enabled", "bsp", "target")) == (2, 2, 0, 1), "PKSMP4 topology changed")
    _require((_hex(topology, "apic"), topology.group("selection")) == (APIC_PHYSICAL_ADDRESS, "lowest_enabled_non_bsp"), "PKSMP4 topology policy changed")

    layout = resource_layout(_hex(resources, "start") // PAGE_BYTES, _dec(resources, "pages"))
    _require(_hex(resources, "start") == layout["start"] == 0x1000, "PKSMP4 low-memory start changed")
    _require(tuple(_dec(resources, name) for name in ("vector", "trampoline", "sequence", "tables", "mapped", "guards", "apic_pt", "below")) == (1, TRAMPOLINE_BYTES, 2, 5, 13, 14, 31, 1), "PKSMP4 resource receipt changed")
    _require(resources.group("leaf") == "pwt_pcd_rw_nx", "PKSMP4 APIC leaf policy changed")
    _require((APIC_PHYSICAL_ADDRESS >> 30) & 0x1FF == APIC_PDPT_INDEX and (APIC_PHYSICAL_ADDRESS >> 21) & 0x1FF == APIC_PAGE_DIRECTORY_INDEX, "PKSMP4 APIC hierarchy model changed")

    _require((_dec(online, "state"), _dec(online, "iflag"), online.group("vectors"), _hex(online, "apic"), _dec(online, "table")) == (2, 1, "224,225,226,227,228,229", APIC_PHYSICAL_ADDRESS, 1), "PKSMP4 online IPI service changed")
    expected_operations = ",".join(str(OPERATIONS[index]["name"]) for index in sorted(OPERATIONS))
    _require(accepted.group("operations") == expected_operations and accepted.group("sequences") == "1,2,3,4,5,6", "PKSMP4 operation order changed")
    _require(tuple(_dec(accepted, name) for name in ("accepted", "reschedule", "shootdown", "call", "diagnostic", "panic", "stop")) == (6, 1, 1, 1, 1, 1, 1), "PKSMP4 accepted-operation receipt changed")
    _require(tuple(_dec(controls, name) for name in ("capability", "vector", "stale", "duplicate", "denied", "delivery", "eoi", "spurious", "apic_error")) == (1, 1, 1, 1, 4, 10, 10, 0, 0), "PKSMP4 denial or EOI accounting changed")
    _require(tuple(_dec(timeout, name) for name in ("target", "mask", "attempt", "bounded", "offline", "retry", "count")) == (2, OFFLINE_CPU_MASK, 6, 1, 1, 1, 1), "PKSMP4 offline shootdown timeout changed")

    root = _hex(shootdown, "root")
    old_frame = _hex(shootdown, "old")
    new_frame = _hex(shootdown, "new")
    shootdown_request = canonical_shootdown_request(root, old_frame, new_frame)
    validate_shootdown_request(shootdown_request, layout["pml4"], 0)
    shootdown_snapshot = {
        "magic": SHOOTDOWN_MAGIC,
        "version": SHOOTDOWN_VERSION,
        "state": SHOOTDOWN_STATE_ACKED,
        "error": SHOOTDOWN_ERROR_NONE,
        "root_physical": root,
        "virtual_address": _hex(shootdown, "probe"),
        "retired_generation": _dec(shootdown, "retired"),
        "active_generation": _dec(shootdown, "active"),
        "target_mask": _hex(shootdown, "target"),
        "ack_mask": _hex(shootdown, "ack"),
        "old_frame_physical": old_frame,
        "new_frame_physical": new_frame,
        "observed_before": _hex(shootdown, "before"),
        "observed_after": _hex(shootdown, "after"),
        "invalidation_count": _dec(shootdown, "invalidations"),
        "request_checksum": shootdown_request["checksum"],
        "response_checksum": _hex(shootdown, "checksum"),
        "last_ack_generation": _dec(shootdown, "last"),
        "timeout_count": _dec(timeout, "count"),
        "reclaim_state": _dec(shootdown, "reclaim"),
    }
    validate_shootdown_ack(shootdown_snapshot, shootdown_request)
    _require(_dec(shootdown, "premature") == 1, "PKSMP4 premature reclaim rejection disappeared")
    _require(shootdown_snapshot["reclaim_state"] == RECLAIM_RELEASED, "PKSMP4 retired generation was not released")

    stop_values = {name: _dec(stop, name) for name in ("attempt", "sequence", "last", "service", "mailbox", "runtime", "panic", "asserts", "deasserts", "sipis", "tss", "idt", "xstate", "apic_table", "final_init", "parked")}
    _require(tuple(stop_values.values()) == (10, 6, 6, 4, 3, 5, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1), "PKSMP4 stop lifecycle changed")
    expected_response = response_checksum({
        "ack_attempt": 10,
        "ack_sequence": 6,
        "result": int(OPERATIONS[6]["result"]),
        "last_accepted_sequence": 6,
        "ack_operation": 6,
        "ack_status": ACK_ACCEPTED,
        "ack_error": 0,
        "delivery_count": 10,
        "accepted_count": 6,
        "denied_count": 4,
    })
    _require(_hex(stop, "response") == expected_response, "PKSMP4 response checksum changed")
    baseline_checksum = _hex(stop, "baseline")
    runtime_checksum = _hex(stop, "runtime_checksum")
    _require(baseline_checksum != 0 and runtime_checksum != 0 and baseline_checksum != runtime_checksum, "PKSMP4 inherited runtime checksums are invalid")

    _require(tuple(_dec(release, name) for name in ("sequence", "zeroed", "verified", "frame_zeroed", "frame_verified", "released", "capability", "runtime", "mmio", "pic", "hpet")) == (7, 131072, 131072, 8192, 8192, 34, 1, 1, 1, 1, 1), "PKSMP4 release receipt changed")
    _require(release.group("frame_allocations") == "3,4" and release.group("frame_releases") == "5,6", "PKSMP4 frame generation sequence changed")
    _require(release.group("apic") == "unchanged", "PKSMP4 APIC base changed")
    _require((result.group("gate"), result.group("rollback"), result.group("terminal")) == ("development_fixed_token", "host_verified", "halt"), "PKSMP4 bounded profile changed")
    _require(tuple(_dec(result, name) for name in ("classes", "valid", "denied", "timeouts", "eois", "panic", "quiesced", "parked", "released", "shootdown", "tlb", "retirement", "no_reuse", "call", "callback", "scheduler", "target", "signatures", "authority", "actions", "production")) == (6, 6, 4, 1, 10, 1, 1, 1, 34, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0), "PKSMP4 claim boundary changed")

    return {
        "transfer_prefix": prefix,
        "topology": {"processors": 2, "enabled": 2, "bsp_apic_id": 0, "target_apic_id": 1},
        "resources": {"physical_start": layout["start"], "page_count": 32, "mapped_pages": 13, "guard_pages": 14, "apic_page_table": layout["apic_page_table"], "trampoline_bytes": TRAMPOLINE_BYTES},
        "service": {"vectors": list(range(224, 230)), "interrupts_enabled": True, "capability_gate": "development_fixed_token"},
        "operations": {"accepted": 6, "denied": 4, "deliveries": 10, "eois": 10, "timeout_count": 1, "timeout_attempt": 6, "retry_same_attempt": True},
        "shootdown": {
            "root_physical": root,
            "virtual_address": PROBE_VIRTUAL_ADDRESS,
            "retired_generation": RETIRED_GENERATION,
            "active_generation": ACTIVE_GENERATION,
            "target_mask": TARGET_CPU_MASK,
            "ack_mask": TARGET_CPU_MASK,
            "old_frame_physical": old_frame,
            "new_frame_physical": new_frame,
            "observed_before": OLD_FRAME_VALUE,
            "observed_after": NEW_FRAME_VALUE,
            "invalidation_count": 1,
            "premature_reclaim_rejected": True,
            "reclaim_state": RECLAIM_RELEASED,
            "response_checksum": shootdown_snapshot["response_checksum"],
        },
        "stop": {**stop_values, "response_checksum": expected_response, "baseline_checksum": baseline_checksum, "runtime_checksum": runtime_checksum},
        "release": {"sequence": 7, "zeroed_bytes": 131072, "verified_bytes": 131072, "frame_zeroed_bytes": 8192, "frame_verified_bytes": 8192, "resources_released": 34},
        "result": {"shootdown_remote_invlpg": 1, "tlb_invalidations": 1, "generation_retirement": 1, "no_reuse_before_retirement": 1, "call_allowlist_noop": 1, "arbitrary_callback": 0, "scheduler": 0, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    normalized = markers.copy()
    for field in ("baseline_checksum", "runtime_checksum"):
        normalized[37] = re.sub(rf"{field}=0x[0-9A-F]{{16}}", f"{field}=<validated-dynamic>", normalized[37], count=1)
    return normalized
