"""Independent PKSMP2 AP-local runtime and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSMP2"
SELECTED_MOVE_ID = "N8-SMP-PERCPU-RUNTIME-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-smp-percpu-runtime-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-smp-percpu-runtime-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-smp-percpu-runtime-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-smp-percpu-runtime-readiness.schema.json"
FEATURE = "development-smp-percpu-runtime"
SELECTOR = 13
MARKER_COUNT = 42
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SMP-RUNTIME-RESULT PASS contract=PKSMP2"

PAGE_BYTES = 4096
RESOURCE_PAGE_COUNT = 32
TRAMPOLINE_BYTES = 836
IDENTITY_MAPPED_PAGE_COUNT = 13
GUARD_PAGE_COUNT = 14
MAILBOX_MAGIC = 0x504B_534D_5032_4D42
MAILBOX_VERSION = 2
RUNTIME_MAGIC = 0x504B_5254_5032_4355
RUNTIME_VERSION = 1
MAILBOX_STATE_QUIESCED = 3
MAILBOX_COMMAND_STOP = 1
RUNTIME_STATE_QUIESCED = 5
REQUIRED_LEAF1_ECX = (1 << 26) | (1 << 27)
REQUIRED_LEAF1_EDX = (1 << 9) | (1 << 24) | (1 << 25) | (1 << 26)
CR0_REQUIRED = (1 << 0) | (1 << 1) | (1 << 5) | (1 << 16) | (1 << 31)
CR0_FORBIDDEN = (1 << 2) | (1 << 3)
CR4_REQUIRED = (1 << 5) | (1 << 9) | (1 << 10) | (1 << 18)
EFER_REQUIRED = (1 << 8) | (1 << 10) | (1 << 11)
SELECTED_XCR0 = 3
XSTATE_AREA_BYTES = 4096
FNV_OFFSET = 0xCBF2_9CE4_8422_2325
FNV_PRIME = 0x0000_0100_0000_01B3

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
    "native/kernel/src/virtual_memory.rs",
    "native/kernel/src/xstate.rs",
    "native/kmap/src/lib.rs",
    "runtime/native_kernel_smp_percpu_runtime.py",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-map-contract.json",
    "specs/native-kernel-smp-percpu-runtime-contract.json",
    "specs/native-kernel-smp-percpu-runtime-contract.schema.json",
    "specs/native-kernel-smp-percpu-runtime-readiness.schema.json",
    "tools/qualify_native_kernel_smp_percpu_runtime.py",
    "tests/test_native_kernel_smp_percpu_runtime.py",
    "docs/native-kernel-smp-percpu-runtime.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N8-PKSMP2-MARKER-OMISSION",
    "NEG-N8-PKSMP2-MARKER-ORDER",
    "NEG-N8-PKSMP2-MARKER-DUPLICATE",
    "NEG-N8-PKSMP2-TRANSFER-PREFIX-SELECTOR-MATRIX",
    "NEG-N8-PKSMP2-TOPOLOGY-FIELD-MATRIX",
    "NEG-N8-PKSMP2-RESOURCE-GEOMETRY-FIELD-MATRIX",
    "NEG-N8-PKSMP2-TABLE-PERMISSION-FIELD-MATRIX",
    "NEG-N8-PKSMP2-STARTUP-FIELD-MATRIX",
    "NEG-N8-PKSMP2-DESCRIPTOR-FIELD-MATRIX",
    "NEG-N8-PKSMP2-STACK-FIELD-MATRIX",
    "NEG-N8-PKSMP2-XSTATE-FIELD-MATRIX",
    "NEG-N8-PKSMP2-VECTOR-FIELD-MATRIX",
    "NEG-N8-PKSMP2-ONLINE-CONTROL-FIELD-MATRIX",
    "NEG-N8-PKSMP2-STOP-CHECKSUM-FIELD-MATRIX",
    "NEG-N8-PKSMP2-RELEASE-FIELD-MATRIX",
    "NEG-N8-PKSMP2-CLAIM-BOUNDARY-FIELD-MATRIX",
    "NEG-N8-PKSMP2-SOURCE-AUDIT",
    "NEG-N8-PKSMP2-RESOURCE-LAYOUT-MODEL",
    "NEG-N8-PKSMP2-X2APIC-MISSING-TARGET-MODEL",
)

HEX = r"0x(?P<{}>[0-9A-F]{{16}})"

EARLY = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-EARLY PASS contract=(?P<contract>PKSMP2) selector=(?P<selector>[0-9]+) bsp=(?P<bsp>[0-9]+) if=(?P<iflag>[0-9]+) stack=validated_by_wrapper serial=initialized$")
TOPOLOGY = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-TOPOLOGY PASS contract=(?P<contract>PKSMP2) madt_bytes=(?P<madt>[0-9]+) processors=(?P<processors>[0-9]+) enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) target_apic_id=(?P<target>[0-9]+) apic_physical=0x(?P<apic>[0-9A-F]{16}) hpet_physical=0x(?P<hpet>[0-9A-F]{16}) x2apic=(?P<x2apic>[0-9]+) selection=(?P<selection>[a-z_]+) retained_snapshot=(?P<snapshot>[0-9]+)$")
RESOURCES = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-RESOURCES PASS contract=(?P<contract>PKSMP2) physical_start=0x(?P<start>[0-9A-F]{16}) pages=(?P<pages>[0-9]+) sipi_vector=(?P<vector>[0-9]+) trampoline_bytes=(?P<trampoline>[0-9]+) allocation_sequence=(?P<sequence>[0-9]+) tables=(?P<tables>[0-9]+) mapped_pages=(?P<mapped>[0-9]+) guard_pages=(?P<guards>[0-9]+) reserved_absent=(?P<reserved>[0-9]+) below_1mib=(?P<below>[0-9]+) allocation_scrubbed=(?P<scrubbed>[0-9]+)$")
TABLES = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-TABLES PASS contract=(?P<contract>PKSMP2) pml4=0x(?P<pml4>[0-9A-F]{16}) pdpt=0x(?P<pdpt>[0-9A-F]{16}) pd=0x(?P<pd>[0-9A-F]{16}) pt=0x(?P<pt>[0-9A-F]{16}) identity_pages=(?P<identity>[0-9]+) trampoline=(?P<trampoline>[a-z_]+) idt=(?P<idt>[a-z_]+) mutable=(?P<mutable>[a-z_]+) guards=(?P<guards>[a-z_]+) reserved=(?P<reserved>[a-z_]+) high_alias=(?P<alias>[a-z_]+)$")
START = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-START PASS contract=(?P<contract>PKSMP2) init_asserts=(?P<asserts>[0-9]+) init_deasserts=(?P<deasserts>[0-9]+) sipis=(?P<sipis>[0-9]+) delivery_timeouts=(?P<timeouts>[0-9]+) sequence=(?P<sequence>[a-z_]+)$")
DESCRIPTORS = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-DESCRIPTORS PASS contract=(?P<contract>PKSMP2) gdt=0x(?P<gdt>[0-9A-F]{16}) gdt_limit=(?P<gdt_limit>[0-9]+) tss=0x(?P<tss>[0-9A-F]{16}) tr=0x(?P<tr>[0-9A-F]{16}) code_selector=0x(?P<code>[0-9A-F]{16}) data_selector=0x(?P<data>[0-9A-F]{16}) idt=0x(?P<idt>[0-9A-F]{16}) idt_limit=(?P<idt_limit>[0-9]+) gates=(?P<gates>[0-9]+) tss_busy=(?P<busy>[0-9]+) idt_verified=(?P<verified>[0-9]+) ltr=(?P<ltr>[a-z_]+) lidt=(?P<lidt>[a-z_]+)$")
STACKS = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-STACKS PASS contract=(?P<contract>PKSMP2) rsp0_bottom=0x(?P<rsp0_bottom>[0-9A-F]{16}) rsp0_top=0x(?P<rsp0_top>[0-9A-F]{16}) observed_rsp=0x(?P<observed_rsp>[0-9A-F]{16}) ist1_bottom=0x(?P<ist1_bottom>[0-9A-F]{16}) ist1_top=0x(?P<ist1_top>[0-9A-F]{16}) ist2_bottom=0x(?P<ist2_bottom>[0-9A-F]{16}) ist2_top=0x(?P<ist2_top>[0-9A-F]{16}) rsp0_pages=(?P<rsp0_pages>[0-9]+) ist_pages_each=(?P<ist_pages>[0-9]+) guards=(?P<guards>[0-9]+)$")
XSTATE = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-XSTATE PASS contract=(?P<contract>PKSMP2) base=0x(?P<base>[0-9A-F]{16}) bytes=(?P<bytes>[0-9]+) supported_xcr0=0x(?P<supported>[0-9A-F]{16}) enabled_bytes=(?P<enabled>[0-9]+) maximum_bytes=(?P<maximum>[0-9]+) xcr0=0x(?P<xcr0>[0-9A-F]{16}) xstate_bv=0x(?P<bv>[0-9A-F]{16}) fcw=0x(?P<fcw>[0-9A-F]{16}) mxcsr=0x(?P<mxcsr>[0-9A-F]{16}) owner_initial=0x(?P<owner_initial>[0-9A-F]{16}) owner_final=0x(?P<owner_final>[0-9A-F]{16}) saves=(?P<saves>[0-9]+) restores=(?P<restores>[0-9]+) image_verified=(?P<verified>[0-9]+) policy=(?P<policy>[a-z_]+)$")
VECTORS = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-VECTORS PASS contract=(?P<contract>PKSMP2) exceptions=(?P<exceptions>[0-9]+) interrupts=(?P<interrupts>[0-9]+) timer=(?P<timer>[0-9]+) ipi_first=(?P<ipi_first>[0-9]+) ipi_last=(?P<ipi_last>[0-9]+) error=(?P<error>[0-9]+) spurious=(?P<spurious>[0-9]+) if=(?P<iflag>[0-9]+) fault=(?P<fault>[0-9]+)$")
ONLINE = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-ONLINE PASS contract=(?P<contract>PKSMP2) state=(?P<state>[0-9]+) runtime_state=(?P<runtime_state>[0-9]+) observed_apic_id=(?P<apic>[0-9]+) leaf1_ecx=0x(?P<ecx>[0-9A-F]{16}) leaf1_edx=0x(?P<edx>[0-9A-F]{16}) cr0=0x(?P<cr0>[0-9A-F]{16}) cr3=0x(?P<cr3>[0-9A-F]{16}) cr4=0x(?P<cr4>[0-9A-F]{16}) efer=0x(?P<efer>[0-9A-F]{16}) rflags=0x(?P<rflags>[0-9A-F]{16}) mode=(?P<mode>[a-zA-Z0-9_]+) tsc_order=(?P<order>[a-z_]+)$")
STOP = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-STOP PASS contract=(?P<contract>PKSMP2) command=(?P<command>[0-9]+) state=(?P<state>[0-9]+) runtime_state=(?P<runtime_state>[0-9]+) tsc_online=0x(?P<online>[0-9A-F]{16}) tsc_stop=0x(?P<stop>[0-9A-F]{16}) baseline_checksum=0x(?P<baseline>[0-9A-F]{16}) runtime_checksum=0x(?P<runtime>[0-9A-F]{16}) final_init=(?P<final_init>[0-9]+) parked=(?P<parked>[0-9]+) mailbox_validated=(?P<mailbox>[0-9]+) resources_validated=(?P<resources>[0-9]+)$")
RELEASE = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-RELEASE PASS contract=(?P<contract>PKSMP2) release_sequence=(?P<sequence>[0-9]+) zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) resources_released=(?P<released>[0-9]+) runtime_revoked=(?P<runtime>[0-9]+) mmio_revoked=(?P<mmio>[0-9]+) pic_restored=(?P<pic>[0-9]+) hpet_restored=(?P<hpet>[0-9]+) apic_base_restored=(?P<apic>[a-z_]+)$")
RESULT = re.compile(r"^POOLEOS:KERNEL:SMP-RUNTIME-RESULT PASS contract=(?P<contract>PKSMP2) profile=(?P<profile>sandybridge_x87_sse_two_vcpu) bsp=(?P<bsp>[0-9]+) ap_started=(?P<started>[0-9]+) ap_online=(?P<online>[0-9]+) descriptors=(?P<descriptors>[0-9]+) stacks=(?P<stacks>[0-9]+) xstate=(?P<xstate>[0-9]+) vectors=(?P<vectors>[0-9]+) ap_quiesced=(?P<quiesced>[0-9]+) ap_parked=(?P<parked>[0-9]+) resources_released=(?P<released>[0-9]+) rollback=(?P<rollback>[a-z_]+) ipi_service=(?P<ipi>[0-9]+) shootdown=(?P<shootdown>[0-9]+) scheduler=(?P<scheduler>[0-9]+) target=(?P<target>[0-9]+) signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) actions=(?P<actions>[0-9]+) production=(?P<production>[0-9]+) terminal=(?P<terminal>[a-z_]+)$")


class KernelSmpPerCpuRuntimeError(RuntimeError):
    """Raised when PKSMP2 data or evidence violates the frozen contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSmpPerCpuRuntimeError(message)


def _match(pattern: re.Pattern[str], marker: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    _require(match is not None, f"PKSMP2 {label} marker violates its contract")
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
        raise KernelSmpPerCpuRuntimeError(f"{path} is not a JSON object")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    data = (root / relative).read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, path) for path in IMPLEMENTATION_INPUTS]}


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = list(validate_json(contract, read_json(root / CONTRACT_SCHEMA_RELATIVE)))
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("required negative controls diverge")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = list(validate_json(readiness, read_json(root / READINESS_SCHEMA_RELATIVE)))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("readiness input bindings are stale")
    controls = readiness.get("negative_controls", [])
    ids = [item.get("id") for item in controls if isinstance(item, dict)]
    if ids != list(NEGATIVE_CONTROL_IDS):
        errors.append("readiness negative-control order diverges")
    return errors


def resource_layout(start_page: int, page_count: int) -> dict[str, Any]:
    _require(start_page > 0 and page_count == RESOURCE_PAGE_COUNT, "PKSMP2 resource geometry changed")
    start = start_page * PAGE_BYTES
    end = start + page_count * PAGE_BYTES
    _require(end <= 0x10_0000 and start_page <= 0xFF, "PKSMP2 resources escaped SIPI memory")
    roles = {
        "trampoline": [0], "tables": [1, 2, 3, 4], "rsp0": [6, 7, 8, 9],
        "local": [12], "descriptors": [15], "idt": [18], "ist1": [21, 22],
        "ist2": [25, 26], "xstate": [29], "reserved": [31],
        "guards": [5, 10, 11, 13, 14, 16, 17, 19, 20, 23, 24, 27, 28, 30],
    }
    flattened = sorted(offset for values in roles.values() for offset in values)
    _require(flattened == list(range(RESOURCE_PAGE_COUNT)), "PKSMP2 resource roles are incomplete")
    address = lambda offset: start + offset * PAGE_BYTES
    return {
        "start": start, "end": end, "sipi_vector": start_page,
        "pml4": address(1), "pdpt": address(2), "pd": address(3), "pt": address(4),
        "rsp0_bottom": address(6), "rsp0_top": address(10), "local": address(12),
        "gdt": address(15), "tss": address(15) + 64, "idt": address(18),
        "ist1_bottom": address(21), "ist1_top": address(23),
        "ist2_bottom": address(25), "ist2_top": address(27), "xstate": address(29),
        "roles": roles,
    }


def select_first_ap(processors: list[dict[str, Any]], bsp_apic_id: int) -> dict[str, Any]:
    enabled = [item for item in processors if item.get("enabled") is True]
    bsp = [item for item in enabled if item.get("apic_id") == bsp_apic_id]
    _require(len(bsp) == 1 and not bsp[0].get("x2apic", False), "PKSMP2 BSP identity is invalid")
    targets = [item for item in enabled if item.get("apic_id") != bsp_apic_id]
    _require(targets, "PKSMP2 has no application processor")
    target = min(targets, key=lambda item: int(item["apic_id"]))
    _require(not target.get("x2apic", False) and 0 <= int(target["apic_id"]) <= 0xFF, "PKSMP2 target mode is unsupported")
    return target


def _fnv(values: tuple[int, ...]) -> int:
    state = FNV_OFFSET
    for value in values:
        for byte in value.to_bytes(8, "little"):
            state = ((state ^ byte) * FNV_PRIME) & 0xFFFF_FFFF_FFFF_FFFF
    return state


def baseline_checksum(values: dict[str, int]) -> int:
    return _fnv((MAILBOX_MAGIC, MAILBOX_VERSION, values["state"], values["command"], 1, 0, 1,
                 values["leaf1_ecx"], values["leaf1_edx"], values["cr0"], values["cr3"],
                 values["cr4"], values["efer"], values["tsc_online"], values["tsc_stop"]))


def runtime_checksum(values: dict[str, int]) -> int:
    names = (
        "baseline_checksum", "runtime_magic", "runtime_version", "runtime_state",
        "expected_gdt", "expected_idt", "expected_tss", "rsp0", "ist1_bottom", "ist1_top",
        "ist2_bottom", "ist2_top", "xstate_base", "xstate_bytes", "owner_initial",
        "observed_gdt", "observed_idt", "observed_rsp", "xcr0", "xstate_bv", "rflags",
        "gdt_limit", "idt_limit", "task_selector", "code_selector", "data_selector",
        "gate_count", "owned_interrupt_count", "interrupts_enabled", "fcw", "mxcsr",
        "owner_final", "save_count", "restore_count", "fault_code", "supported_xcr0",
        "enabled_area_bytes", "maximum_area_bytes",
    )
    return _fnv(tuple(values[name] for name in names))


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [*markers[:BOOT_TRANSFER_MARKER_COUNT], *markers[COMMON_KERNEL_MARKER_START:COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT]]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSmpPerCpuRuntimeError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSMP2 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10), 10) == SELECTOR, "PKSMP2 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    topology = _match(TOPOLOGY, markers[30], "topology")
    resources = _match(RESOURCES, markers[31], "resources")
    tables = _match(TABLES, markers[32], "tables")
    start = _match(START, markers[33], "start")
    descriptors = _match(DESCRIPTORS, markers[34], "descriptors")
    stacks = _match(STACKS, markers[35], "stacks")
    xstate = _match(XSTATE, markers[36], "xstate")
    vectors = _match(VECTORS, markers[37], "vectors")
    online = _match(ONLINE, markers[38], "online")
    stop = _match(STOP, markers[39], "stop")
    release = _match(RELEASE, markers[40], "release")
    result = _match(RESULT, markers[41], "result")

    _require((_dec(early, "selector"), _dec(early, "bsp"), _dec(early, "iflag")) == (13, 1, 0), "PKSMP2 early state changed")
    _require(tuple(_dec(topology, name) for name in ("madt", "processors", "enabled", "bsp", "target")) == (128, 2, 2, 0, 1), "PKSMP2 topology changed")
    _require((_hex(topology, "apic"), _hex(topology, "hpet"), _dec(topology, "x2apic"), topology.group("selection"), _dec(topology, "snapshot")) == (0xFEE0_0000, 0xFED0_0000, 0, "lowest_enabled_non_bsp", 1), "PKSMP2 topology policy changed")

    layout = resource_layout(_hex(resources, "start") // PAGE_BYTES, _dec(resources, "pages"))
    _require(_hex(resources, "start") == layout["start"] == 0x1000, "PKSMP2 low-memory start changed")
    _require(tuple(_dec(resources, name) for name in ("vector", "trampoline", "sequence", "tables", "mapped", "guards", "reserved", "below", "scrubbed")) == (1, TRAMPOLINE_BYTES, 2, 4, 13, 14, 1, 1, 1), "PKSMP2 resource receipt changed")
    _require(tuple(_hex(tables, name) for name in ("pml4", "pdpt", "pd", "pt")) == tuple(layout[name] for name in ("pml4", "pdpt", "pd", "pt")), "PKSMP2 table addresses changed")
    _require((_dec(tables, "identity"), tables.group("trampoline"), tables.group("idt"), tables.group("mutable"), tables.group("guards"), tables.group("reserved"), tables.group("alias")) == (13, "rx", "ro_nx", "rw_nx", "absent", "absent", "revocable"), "PKSMP2 table policy changed")
    _require(tuple(_dec(start, name) for name in ("asserts", "deasserts", "sipis", "timeouts")) == (1, 1, 2, 0) and start.group("sequence") == "init_sipi_sipi", "PKSMP2 startup receipt changed")

    _require(tuple(_hex(descriptors, name) for name in ("gdt", "tss", "tr", "code", "data", "idt")) == (layout["gdt"], layout["tss"], 0x18, 0x8, 0x10, layout["idt"]), "PKSMP2 descriptor addresses changed")
    _require(tuple(_dec(descriptors, name) for name in ("gdt_limit", "idt_limit", "gates", "busy", "verified")) == (39, 4095, 27, 1, 1) and (descriptors.group("ltr"), descriptors.group("lidt")) == ("hardware", "hardware"), "PKSMP2 descriptor state changed")
    _require(tuple(_hex(stacks, name) for name in ("rsp0_bottom", "rsp0_top", "observed_rsp", "ist1_bottom", "ist1_top", "ist2_bottom", "ist2_top")) == tuple(layout[name] for name in ("rsp0_bottom", "rsp0_top", "rsp0_top", "ist1_bottom", "ist1_top", "ist2_bottom", "ist2_top")), "PKSMP2 stack addresses changed")
    _require(tuple(_dec(stacks, name) for name in ("rsp0_pages", "ist_pages", "guards")) == (4, 2, 14), "PKSMP2 stack geometry changed")

    xstate_values = {name: _hex(xstate, name) for name in ("base", "supported", "xcr0", "bv", "fcw", "mxcsr", "owner_initial", "owner_final")}
    _require(xstate_values["base"] == layout["xstate"] and tuple(_dec(xstate, name) for name in ("bytes", "enabled", "maximum", "saves", "restores", "verified")) == (4096, 576, 576, 1, 1, 1), "PKSMP2 xstate geometry changed")
    _require((xstate_values["supported"] & SELECTED_XCR0, xstate_values["xcr0"], xstate_values["bv"] & ~SELECTED_XCR0, xstate_values["fcw"], xstate_values["mxcsr"], xstate_values["owner_initial"], xstate_values["owner_final"], xstate.group("policy")) == (SELECTED_XCR0, SELECTED_XCR0, 0, 0x37F, 0x1F80, 0x5058_0001, 0, "eager"), "PKSMP2 xstate policy changed")
    _require(tuple(_dec(vectors, name) for name in ("exceptions", "interrupts", "timer", "ipi_first", "ipi_last", "error", "spurious", "iflag", "fault")) == (8, 19, 64, 224, 239, 240, 255, 0, 0), "PKSMP2 vector policy changed")

    online_values = {name: _hex(online, name) for name in ("ecx", "edx", "cr0", "cr3", "cr4", "efer", "rflags")}
    _require((_dec(online, "state"), _dec(online, "runtime_state"), _dec(online, "apic"), online.group("mode"), online.group("order")) == (2, 4, 1, "x86_64", "validated"), "PKSMP2 AP online state changed")
    _require((online_values["ecx"], online_values["edx"], online_values["cr0"], online_values["cr3"], online_values["cr4"], online_values["efer"], online_values["rflags"]) == (0x8EB8_2203, 0x178B_FBFD, 0xE001_0033, layout["pml4"], 0x40620, 0xD00, 0x6), "PKSMP2 Sandy Bridge control profile changed")
    _require(online_values["ecx"] & REQUIRED_LEAF1_ECX == REQUIRED_LEAF1_ECX and online_values["edx"] & REQUIRED_LEAF1_EDX == REQUIRED_LEAF1_EDX, "PKSMP2 required AP features are absent")
    _require(online_values["cr0"] & CR0_REQUIRED == CR0_REQUIRED and online_values["cr0"] & CR0_FORBIDDEN == 0 and online_values["cr4"] & CR4_REQUIRED == CR4_REQUIRED and online_values["efer"] & EFER_REQUIRED == EFER_REQUIRED and online_values["rflags"] & 0x200 == 0, "PKSMP2 AP control state is incomplete")

    stop_values = {"tsc_online": _hex(stop, "online"), "tsc_stop": _hex(stop, "stop")}
    _require(stop_values["tsc_online"] > 0 and stop_values["tsc_stop"] >= stop_values["tsc_online"], "PKSMP2 AP TSC order failed")
    baseline_values = {"state": 3, "command": 1, "leaf1_ecx": online_values["ecx"], "leaf1_edx": online_values["edx"], "cr0": online_values["cr0"], "cr3": online_values["cr3"], "cr4": online_values["cr4"], "efer": online_values["efer"], **stop_values}
    computed_baseline = baseline_checksum(baseline_values)
    _require(_hex(stop, "baseline") == computed_baseline, "PKSMP2 baseline checksum changed")
    runtime_values = {
        "baseline_checksum": computed_baseline, "runtime_magic": RUNTIME_MAGIC, "runtime_version": RUNTIME_VERSION, "runtime_state": 5,
        "expected_gdt": layout["gdt"], "expected_idt": layout["idt"], "expected_tss": layout["tss"], "rsp0": layout["rsp0_top"],
        "ist1_bottom": layout["ist1_bottom"], "ist1_top": layout["ist1_top"], "ist2_bottom": layout["ist2_bottom"], "ist2_top": layout["ist2_top"],
        "xstate_base": xstate_values["base"], "xstate_bytes": _dec(xstate, "bytes"), "owner_initial": xstate_values["owner_initial"],
        "observed_gdt": _hex(descriptors, "gdt"), "observed_idt": _hex(descriptors, "idt"), "observed_rsp": _hex(stacks, "observed_rsp"),
        "xcr0": xstate_values["xcr0"], "xstate_bv": xstate_values["bv"], "rflags": online_values["rflags"],
        "gdt_limit": _dec(descriptors, "gdt_limit"), "idt_limit": _dec(descriptors, "idt_limit"), "task_selector": _hex(descriptors, "tr"),
        "code_selector": _hex(descriptors, "code"), "data_selector": _hex(descriptors, "data"), "gate_count": _dec(descriptors, "gates"),
        "owned_interrupt_count": _dec(vectors, "interrupts"), "interrupts_enabled": _dec(vectors, "iflag"), "fcw": xstate_values["fcw"],
        "mxcsr": xstate_values["mxcsr"], "owner_final": xstate_values["owner_final"], "save_count": _dec(xstate, "saves"),
        "restore_count": _dec(xstate, "restores"), "fault_code": _dec(vectors, "fault"), "supported_xcr0": xstate_values["supported"],
        "enabled_area_bytes": _dec(xstate, "enabled"), "maximum_area_bytes": _dec(xstate, "maximum"),
    }
    computed_runtime = runtime_checksum(runtime_values)
    _require(_hex(stop, "runtime") == computed_runtime, "PKSMP2 runtime checksum changed")
    _require(tuple(_dec(stop, name) for name in ("command", "state", "runtime_state", "final_init", "parked", "mailbox", "resources")) == (1, 3, 5, 1, 1, 1, 1), "PKSMP2 stop receipt changed")
    _require(tuple(_dec(release, name) for name in ("sequence", "zeroed", "verified", "released", "runtime", "mmio", "pic", "hpet")) == (3, 131072, 131072, 32, 1, 1, 1, 1) and release.group("apic") == "unchanged", "PKSMP2 release receipt changed")
    _require(tuple(_dec(result, name) for name in ("bsp", "started", "online", "descriptors", "stacks", "xstate", "vectors", "quiesced", "parked", "released")) == (1, 1, 1, 1, 3, 1, 27, 1, 1, 32), "PKSMP2 lifecycle result changed")
    _require((result.group("rollback"), *tuple(_dec(result, name) for name in ("ipi", "shootdown", "scheduler", "target", "signatures", "authority", "actions", "production")), result.group("terminal")) == ("host_verified", 0, 0, 0, 0, 0, 0, 0, 0, "halt"), "PKSMP2 claim boundary changed")

    return {
        "transfer_prefix": prefix,
        "topology": {"madt_bytes": 128, "processors": 2, "enabled": 2, "bsp_apic_id": 0, "target_apic_id": 1},
        "resources": {"physical_start": layout["start"], "page_count": 32, "mapped_pages": 13, "guard_pages": 14, "trampoline_bytes": TRAMPOLINE_BYTES},
        "descriptors": {"gdt": layout["gdt"], "tss": layout["tss"], "idt": layout["idt"], "gates": 27, "tss_busy": True},
        "stacks": {"rsp0": layout["rsp0_top"], "ist1": layout["ist1_top"], "ist2": layout["ist2_top"], "guard_pages": 14},
        "xstate": {"base": layout["xstate"], "xcr0": SELECTED_XCR0, "enabled_bytes": 576, "owner_cleared": True},
        "online": {"state": 2, "runtime_state": 4, "observed_apic_id": 1, **online_values},
        "stop": {**stop_values, "baseline_checksum": computed_baseline, "runtime_checksum": computed_runtime, "parked": True},
        "release": {"sequence": 3, "zeroed_bytes": 131072, "verified_bytes": 131072, "resources_released": 32},
        "result": {"ap_started": 1, "ap_online": 1, "descriptors": 1, "stack_classes": 3, "xstate": 1, "vectors": 27, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    normalized = markers.copy()
    for field in ("tsc_online", "tsc_stop", "baseline_checksum", "runtime_checksum"):
        normalized[39] = re.sub(rf"{field}=0x[0-9A-F]{{16}}", f"{field}=<validated-dynamic>", normalized[39], count=1)
    return normalized
