"""Independent PKSMP1 first-AP lifecycle and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKSMP1"
SELECTED_MOVE_ID = "N8-SMP-FIRST-AP-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-smp-first-ap-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-smp-first-ap-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-smp-first-ap-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-smp-first-ap-readiness.schema.json"
FEATURE = "development-smp-first-ap"
SELECTOR = 12
MARKER_COUNT = 38
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:SMP-RESULT PASS contract=PKSMP1"

PAGE_BYTES = 4096
RESOURCE_PAGE_COUNT = 14
TRAMPOLINE_BYTES = 336
MAILBOX_MAGIC = 0x504B_534D_5031_4D42
MAILBOX_VERSION = 1
MAILBOX_STATE_ONLINE = 2
MAILBOX_STATE_QUIESCED = 3
MAILBOX_COMMAND_STOP = 1
REQUIRED_LEAF1_EDX = (1 << 9) | (1 << 24) | (1 << 25) | (1 << 26)
CR0_REQUIRED = (1 << 0) | (1 << 16) | (1 << 31)
CR4_REQUIRED = 1 << 5
EFER_REQUIRED = (1 << 8) | (1 << 10) | (1 << 11)
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
    "native/kernel/src/virtual_memory.rs",
    "native/kmap/src/lib.rs",
    "runtime/native_kernel_smp_first_ap.py",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-map-contract.json",
    "specs/native-kernel-smp-first-ap-contract.json",
    "specs/native-kernel-smp-first-ap-contract.schema.json",
    "specs/native-kernel-smp-first-ap-readiness.schema.json",
    "tools/qualify_native_kernel_smp_first_ap.py",
    "tests/test_native_kernel_smp_first_ap.py",
    "docs/native-kernel-smp-first-ap.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N8-PKSMP-MARKER-OMISSION",
    "NEG-N8-PKSMP-MARKER-ORDER",
    "NEG-N8-PKSMP-MARKER-DUPLICATE",
    "NEG-N8-PKSMP-SELECTOR",
    "NEG-N8-PKSMP-CONTRACT",
    "NEG-N8-PKSMP-PROCESSOR-COUNT",
    "NEG-N8-PKSMP-ENABLED-COUNT",
    "NEG-N8-PKSMP-BSP-IDENTITY",
    "NEG-N8-PKSMP-TARGET-IDENTITY",
    "NEG-N8-PKSMP-X2APIC",
    "NEG-N8-PKSMP-SELECTION",
    "NEG-N8-PKSMP-ACPI-SNAPSHOT",
    "NEG-N8-PKSMP-LOW-MEMORY-START",
    "NEG-N8-PKSMP-RESOURCE-PAGES",
    "NEG-N8-PKSMP-SIPI-VECTOR",
    "NEG-N8-PKSMP-TRAMPOLINE-SIZE",
    "NEG-N8-PKSMP-ALLOCATION-SEQUENCE",
    "NEG-N8-PKSMP-TABLE-COUNT",
    "NEG-N8-PKSMP-STACK-PAGES",
    "NEG-N8-PKSMP-PERCPU-PAGES",
    "NEG-N8-PKSMP-GUARD-PAGES",
    "NEG-N8-PKSMP-BELOW-1MIB",
    "NEG-N8-PKSMP-ALLOCATION-SCRUB",
    "NEG-N8-PKSMP-TABLE-GEOMETRY",
    "NEG-N8-PKSMP-IDENTITY-COVERAGE",
    "NEG-N8-PKSMP-TRAMPOLINE-WX",
    "NEG-N8-PKSMP-STACK-NX",
    "NEG-N8-PKSMP-PERCPU-NX",
    "NEG-N8-PKSMP-GUARD-PRESENCE",
    "NEG-N8-PKSMP-ALIAS-REVOCATION",
    "NEG-N8-PKSMP-INIT-ASSERT",
    "NEG-N8-PKSMP-INIT-DEASSERT",
    "NEG-N8-PKSMP-SIPI-COUNT",
    "NEG-N8-PKSMP-DELIVERY-TIMEOUT",
    "NEG-N8-PKSMP-START-SEQUENCE",
    "NEG-N8-PKSMP-ONLINE-STATE",
    "NEG-N8-PKSMP-OBSERVED-APIC",
    "NEG-N8-PKSMP-LEAF1-ECX",
    "NEG-N8-PKSMP-LEAF1-EDX",
    "NEG-N8-PKSMP-CR0",
    "NEG-N8-PKSMP-CR3",
    "NEG-N8-PKSMP-CR4",
    "NEG-N8-PKSMP-EFER",
    "NEG-N8-PKSMP-LONG-MODE",
    "NEG-N8-PKSMP-TSC-ORDER-CLAIM",
    "NEG-N8-PKSMP-STOP-COMMAND",
    "NEG-N8-PKSMP-QUIESCED-STATE",
    "NEG-N8-PKSMP-TSC-ORDER",
    "NEG-N8-PKSMP-MAILBOX-CHECKSUM",
    "NEG-N8-PKSMP-FINAL-INIT",
    "NEG-N8-PKSMP-PARKED",
    "NEG-N8-PKSMP-MAILBOX-VALIDATION",
    "NEG-N8-PKSMP-RELEASE-SEQUENCE",
    "NEG-N8-PKSMP-ZEROED-BYTES",
    "NEG-N8-PKSMP-VERIFIED-BYTES",
    "NEG-N8-PKSMP-RESOURCE-RELEASE",
    "NEG-N8-PKSMP-MAILBOX-REVOKE",
    "NEG-N8-PKSMP-MMIO-REVOKE",
    "NEG-N8-PKSMP-PIC-RESTORE",
    "NEG-N8-PKSMP-HPET-RESTORE",
    "NEG-N8-PKSMP-APIC-BASE-DRIFT",
    "NEG-N8-PKSMP-AP-ONLINE-OVERCLAIM",
    "NEG-N8-PKSMP-IPI-SERVICE-OVERCLAIM",
    "NEG-N8-PKSMP-SHOOTDOWN-OVERCLAIM",
    "NEG-N8-PKSMP-SCHEDULER-OVERCLAIM",
    "NEG-N8-PKSMP-TARGET-OVERCLAIM",
    "NEG-N8-PKSMP-AUTHORITY-OVERCLAIM",
    "NEG-N8-PKSMP-PRODUCTION-OVERCLAIM",
    "NEG-N8-PKSMP-TERMINAL-DRIFT",
    "NEG-N8-PKSMP-GDT-ACCESSED-BIT",
    "NEG-N8-PKSMP-X2APIC-TARGET-MODEL",
    "NEG-N8-PKSMP-MISSING-TARGET-MODEL",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:SMP-EARLY PASS contract=(?P<contract>PKSMP1) selector=(?P<selector>[0-9]+) "
    r"bsp=(?P<bsp>[0-9]+) if=(?P<iflag>[0-9]+) stack=validated_by_wrapper serial=initialized$"
)
TOPOLOGY = re.compile(
    r"^POOLEOS:KERNEL:SMP-TOPOLOGY PASS contract=(?P<contract>PKSMP1) madt_bytes=(?P<madt>[0-9]+) "
    r"processors=(?P<processors>[0-9]+) enabled=(?P<enabled>[0-9]+) bsp_apic_id=(?P<bsp>[0-9]+) "
    r"target_apic_id=(?P<target>[0-9]+) apic_physical=0x(?P<apic>[0-9A-F]{16}) "
    r"hpet_physical=0x(?P<hpet>[0-9A-F]{16}) x2apic=(?P<x2apic>[0-9]+) "
    r"selection=(?P<selection>[a-z_]+) retained_snapshot=(?P<snapshot>[0-9]+)$"
)
RESOURCES = re.compile(
    r"^POOLEOS:KERNEL:SMP-RESOURCES PASS contract=(?P<contract>PKSMP1) physical_start=0x(?P<start>[0-9A-F]{16}) "
    r"pages=(?P<pages>[0-9]+) sipi_vector=(?P<vector>[0-9]+) trampoline_bytes=(?P<trampoline>[0-9]+) "
    r"allocation_sequence=(?P<sequence>[0-9]+) tables=(?P<tables>[0-9]+) stack_pages=(?P<stack>[0-9]+) "
    r"per_cpu_pages=(?P<percpu>[0-9]+) guard_pages=(?P<guards>[0-9]+) below_1mib=(?P<below>[0-9]+) "
    r"allocation_scrubbed=(?P<scrubbed>[0-9]+)$"
)
TABLES = re.compile(
    r"^POOLEOS:KERNEL:SMP-TABLES PASS contract=(?P<contract>PKSMP1) pml4=0x(?P<pml4>[0-9A-F]{16}) "
    r"pdpt=0x(?P<pdpt>[0-9A-F]{16}) pd=0x(?P<pd>[0-9A-F]{16}) pt=0x(?P<pt>[0-9A-F]{16}) "
    r"identity_pages=(?P<identity>[0-9]+) trampoline=(?P<trampoline>[a-z_]+) stack=(?P<stack>[a-z_]+) "
    r"per_cpu=(?P<percpu>[a-z_]+) guards=(?P<guards>[a-z_]+) high_alias=(?P<alias>[a-z_]+)$"
)
START = re.compile(
    r"^POOLEOS:KERNEL:SMP-START PASS contract=(?P<contract>PKSMP1) init_asserts=(?P<asserts>[0-9]+) "
    r"init_deasserts=(?P<deasserts>[0-9]+) sipis=(?P<sipis>[0-9]+) delivery_timeouts=(?P<timeouts>[0-9]+) "
    r"sequence=(?P<sequence>[a-z_]+)$"
)
ONLINE = re.compile(
    r"^POOLEOS:KERNEL:SMP-ONLINE PASS contract=(?P<contract>PKSMP1) state=(?P<state>[0-9]+) "
    r"observed_apic_id=(?P<apic>[0-9]+) leaf1_ecx=0x(?P<ecx>[0-9A-F]{16}) leaf1_edx=0x(?P<edx>[0-9A-F]{16}) "
    r"cr0=0x(?P<cr0>[0-9A-F]{16}) cr3=0x(?P<cr3>[0-9A-F]{16}) cr4=0x(?P<cr4>[0-9A-F]{16}) "
    r"efer=0x(?P<efer>[0-9A-F]{16}) mode=(?P<mode>[a-zA-Z0-9_]+) tsc_order=(?P<order>[a-z]+)$"
)
STOP = re.compile(
    r"^POOLEOS:KERNEL:SMP-STOP PASS contract=(?P<contract>PKSMP1) command=(?P<command>[0-9]+) state=(?P<state>[0-9]+) "
    r"tsc_online=0x(?P<online>[0-9A-F]{16}) tsc_stop=0x(?P<stop>[0-9A-F]{16}) checksum=0x(?P<checksum>[0-9A-F]{16}) "
    r"final_init=(?P<final_init>[0-9]+) parked=(?P<parked>[0-9]+) mailbox_validated=(?P<validated>[0-9]+)$"
)
RELEASE = re.compile(
    r"^POOLEOS:KERNEL:SMP-RELEASE PASS contract=(?P<contract>PKSMP1) release_sequence=(?P<sequence>[0-9]+) "
    r"zeroed_bytes=(?P<zeroed>[0-9]+) verified_bytes=(?P<verified>[0-9]+) resources_released=(?P<released>[0-9]+) "
    r"mailbox_revoked=(?P<mailbox>[0-9]+) mmio_revoked=(?P<mmio>[0-9]+) pic_restored=(?P<pic>[0-9]+) "
    r"hpet_restored=(?P<hpet>[0-9]+) apic_base_restored=(?P<apic>[a-z]+)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:SMP-RESULT PASS contract=(?P<contract>PKSMP1) profile=(?P<profile>qemu64_tier0_two_vcpu) "
    r"bsp=(?P<bsp>[0-9]+) ap_started=(?P<started>[0-9]+) ap_online=(?P<online>[0-9]+) "
    r"ap_quiesced=(?P<quiesced>[0-9]+) ap_parked=(?P<parked>[0-9]+) per_cpu=(?P<percpu>[0-9]+) "
    r"stack_pages=(?P<stack>[0-9]+) guards=(?P<guards>[0-9]+) rollback=(?P<rollback>[a-z_]+) "
    r"ipi_service=(?P<ipi>[0-9]+) shootdown=(?P<shootdown>[0-9]+) scheduler=(?P<scheduler>[0-9]+) "
    r"target=(?P<target>[0-9]+) signatures=(?P<signatures>[0-9]+) authority=(?P<authority>[0-9]+) "
    r"actions=(?P<actions>[0-9]+) production=(?P<production>[0-9]+) terminal=(?P<terminal>[a-z]+)$"
)


class KernelSmpFirstApError(RuntimeError):
    """Raised when PKSMP1 data or evidence violates the frozen contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelSmpFirstApError(message)


def _match(pattern: re.Pattern[str], marker: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    _require(match is not None, f"PKSMP1 {label} marker violates its contract")
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
        raise KernelSmpFirstApError(f"{path} is not a JSON object")
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
    _require(start_page > 0 and page_count == RESOURCE_PAGE_COUNT, "PKSMP1 resource geometry changed")
    start = start_page * PAGE_BYTES
    end = start + page_count * PAGE_BYTES
    _require(end <= 0x10_0000 and start_page <= 0xFF, "PKSMP1 resources escaped SIPI memory")
    roles = {
        "trampoline": [0],
        "tables": [1, 2, 3, 4],
        "stack_guards": [5, 10],
        "stack": [6, 7, 8, 9],
        "per_cpu_guards": [11, 13],
        "per_cpu": [12],
    }
    flattened = sorted(offset for values in roles.values() for offset in values)
    _require(flattened == list(range(RESOURCE_PAGE_COUNT)), "PKSMP1 resource roles are incomplete")
    return {
        "start": start,
        "end": end,
        "sipi_vector": start_page,
        "pml4": start + PAGE_BYTES,
        "pdpt": start + 2 * PAGE_BYTES,
        "pd": start + 3 * PAGE_BYTES,
        "pt": start + 4 * PAGE_BYTES,
        "stack_top": start + 10 * PAGE_BYTES,
        "per_cpu": start + 12 * PAGE_BYTES,
        "roles": roles,
    }


def select_first_ap(processors: list[dict[str, Any]], bsp_apic_id: int) -> dict[str, Any]:
    enabled = [item for item in processors if item.get("enabled") is True]
    bsp = [item for item in enabled if item.get("apic_id") == bsp_apic_id]
    _require(len(bsp) == 1 and not bsp[0].get("x2apic", False), "PKSMP1 BSP identity is invalid")
    targets = [item for item in enabled if item.get("apic_id") != bsp_apic_id]
    _require(targets, "PKSMP1 has no application processor")
    target = min(targets, key=lambda item: int(item["apic_id"]))
    _require(not target.get("x2apic", False) and 0 <= int(target["apic_id"]) <= 0xFF, "PKSMP1 target mode is unsupported")
    return target


def require_preaccessed_gdt(descriptors: list[int]) -> None:
    _require(len(descriptors) == 4, "PKSMP1 GDT descriptor count changed")
    _require(all(descriptor & (1 << 40) for descriptor in descriptors), "PKSMP1 RX GDT would require an accessed-bit write")


def mailbox_checksum(values: dict[str, int]) -> int:
    ordered = (
        MAILBOX_MAGIC,
        MAILBOX_VERSION,
        values["state"],
        values["command"],
        values["target_apic_id"],
        values["bsp_apic_id"],
        values["observed_apic_id"],
        values["leaf1_ecx"],
        values["leaf1_edx"],
        values["cr0"],
        values["cr3"],
        values["cr4"],
        values["efer"],
        values["tsc_online"],
        values["tsc_stop"],
    )
    state = FNV_OFFSET
    for value in ordered:
        for byte in value.to_bytes(8, "little"):
            state = ((state ^ byte) * FNV_PRIME) & 0xFFFF_FFFF_FFFF_FFFF
    return state


def extract_markers(raw: bytes) -> list[str]:
    return native_kernel_transfer.extract_markers(raw)


def _prefix(markers: list[str]) -> dict[str, Any]:
    baseline = [
        *markers[:BOOT_TRANSFER_MARKER_COUNT],
        *markers[COMMON_KERNEL_MARKER_START : COMMON_KERNEL_MARKER_START + COMMON_KERNEL_MARKER_COUNT],
    ]
    baseline[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", baseline[23], count=1)
    baseline.append(
        "POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
        "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0"
    )
    try:
        summary = native_kernel_transfer.validate_markers(baseline)
    except native_kernel_transfer.KernelTransferError as error:
        raise KernelSmpFirstApError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKSMP1 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10), 10) == SELECTOR, "PKSMP1 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    topology = _match(TOPOLOGY, markers[30], "topology")
    resources = _match(RESOURCES, markers[31], "resources")
    tables = _match(TABLES, markers[32], "tables")
    start = _match(START, markers[33], "start")
    online = _match(ONLINE, markers[34], "online")
    stop = _match(STOP, markers[35], "stop")
    release = _match(RELEASE, markers[36], "release")
    result = _match(RESULT, markers[37], "result")

    _require((_dec(early, "selector"), _dec(early, "bsp"), _dec(early, "iflag")) == (12, 1, 0), "PKSMP1 early state changed")
    _require(
        (_dec(topology, "madt"), _dec(topology, "processors"), _dec(topology, "enabled"), _dec(topology, "bsp"), _dec(topology, "target"))
        == (128, 2, 2, 0, 1),
        "PKSMP1 qemu64 topology changed",
    )
    _require((_hex(topology, "apic"), _hex(topology, "hpet")) == (0xFEE0_0000, 0xFED0_0000), "PKSMP1 controller addresses changed")
    _require((_dec(topology, "x2apic"), topology.group("selection"), _dec(topology, "snapshot")) == (0, "lowest_enabled_non_bsp", 1), "PKSMP1 topology policy changed")

    layout = resource_layout(_hex(resources, "start") // PAGE_BYTES, _dec(resources, "pages"))
    _require(_hex(resources, "start") == layout["start"] == 0x1000, "PKSMP1 low-memory start changed")
    _require(
        (_dec(resources, "vector"), _dec(resources, "trampoline"), _dec(resources, "sequence"), _dec(resources, "tables"), _dec(resources, "stack"), _dec(resources, "percpu"), _dec(resources, "guards"), _dec(resources, "below"), _dec(resources, "scrubbed"))
        == (1, TRAMPOLINE_BYTES, 2, 4, 4, 1, 4, 1, 1),
        "PKSMP1 resource receipt changed",
    )
    _require((_hex(tables, "pml4"), _hex(tables, "pdpt"), _hex(tables, "pd"), _hex(tables, "pt")) == (layout["pml4"], layout["pdpt"], layout["pd"], layout["pt"]), "PKSMP1 table addresses changed")
    _require((_dec(tables, "identity"), tables.group("trampoline"), tables.group("stack"), tables.group("percpu"), tables.group("guards"), tables.group("alias")) == (6, "rx", "rw_nx", "rw_nx", "absent", "revocable"), "PKSMP1 table policy changed")
    _require((_dec(start, "asserts"), _dec(start, "deasserts"), _dec(start, "sipis"), _dec(start, "timeouts"), start.group("sequence")) == (1, 1, 2, 0, "init_sipi_sipi"), "PKSMP1 startup receipt changed")

    online_values = {name: _hex(online, name) for name in ("ecx", "edx", "cr0", "cr3", "cr4", "efer")}
    _require((_dec(online, "state"), _dec(online, "apic"), online.group("mode"), online.group("order")) == (MAILBOX_STATE_ONLINE, 1, "x86_64", "validated"), "PKSMP1 AP online identity changed")
    _require(online_values["ecx"] == 0x8000_2001 and online_values["edx"] == 0x178B_FBFD, "PKSMP1 qemu64 CPUID changed")
    _require(online_values["edx"] & REQUIRED_LEAF1_EDX == REQUIRED_LEAF1_EDX, "PKSMP1 required AP features are absent")
    _require(online_values["cr0"] & CR0_REQUIRED == CR0_REQUIRED, "PKSMP1 AP CR0 is incomplete")
    _require(online_values["cr3"] == layout["pml4"] and online_values["cr4"] & CR4_REQUIRED, "PKSMP1 AP paging state changed")
    _require(online_values["efer"] & EFER_REQUIRED == EFER_REQUIRED, "PKSMP1 AP EFER is incomplete")

    stop_values = {"tsc_online": _hex(stop, "online"), "tsc_stop": _hex(stop, "stop")}
    _require(stop_values["tsc_online"] > 0 and stop_values["tsc_stop"] >= stop_values["tsc_online"], "PKSMP1 AP TSC order failed")
    mailbox = {
        "state": MAILBOX_STATE_QUIESCED,
        "command": MAILBOX_COMMAND_STOP,
        "target_apic_id": 1,
        "bsp_apic_id": 0,
        "observed_apic_id": 1,
        "leaf1_ecx": online_values["ecx"],
        "leaf1_edx": online_values["edx"],
        "cr0": online_values["cr0"],
        "cr3": online_values["cr3"],
        "cr4": online_values["cr4"],
        "efer": online_values["efer"],
        **stop_values,
    }
    _require(_hex(stop, "checksum") == mailbox_checksum(mailbox), "PKSMP1 mailbox checksum changed")
    _require((_dec(stop, "command"), _dec(stop, "state"), _dec(stop, "final_init"), _dec(stop, "parked"), _dec(stop, "validated")) == (1, 3, 1, 1, 1), "PKSMP1 stop receipt changed")
    _require((_dec(release, "sequence"), _dec(release, "zeroed"), _dec(release, "verified"), _dec(release, "released"), _dec(release, "mailbox"), _dec(release, "mmio"), _dec(release, "pic"), _dec(release, "hpet"), release.group("apic")) == (3, 57_344, 57_344, 14, 1, 1, 1, 1, "unchanged"), "PKSMP1 release receipt changed")
    _require(
        tuple(_dec(result, name) for name in ("bsp", "started", "online", "quiesced", "parked", "percpu", "stack", "guards")) == (1, 1, 1, 1, 1, 1, 4, 4),
        "PKSMP1 lifecycle result changed",
    )
    _require((result.group("rollback"), _dec(result, "ipi"), _dec(result, "shootdown"), _dec(result, "scheduler"), _dec(result, "target"), _dec(result, "signatures"), _dec(result, "authority"), _dec(result, "actions"), _dec(result, "production"), result.group("terminal")) == ("host_verified", 0, 0, 0, 0, 0, 0, 0, 0, "halt"), "PKSMP1 claim boundary changed")

    return {
        "transfer_prefix": prefix,
        "topology": {"madt_bytes": 128, "processors": 2, "enabled": 2, "bsp_apic_id": 0, "target_apic_id": 1},
        "resources": {"physical_start": layout["start"], "page_count": 14, "sipi_vector": 1, "trampoline_bytes": TRAMPOLINE_BYTES, "guard_pages": 4},
        "online": {"state": 2, "observed_apic_id": 1, **online_values},
        "stop": {**stop_values, "checksum": _hex(stop, "checksum"), "parked": True},
        "release": {"sequence": 3, "zeroed_bytes": 57_344, "verified_bytes": 57_344, "resources_released": 14},
        "result": {"ap_started": 1, "ap_online": 1, "ap_quiesced": 1, "ap_parked": 1, "production": 0},
    }


def normalize_dynamic_markers(markers: list[str]) -> list[str]:
    validate_markers(markers)
    normalized = markers.copy()
    for field in ("tsc_online", "tsc_stop", "checksum"):
        normalized[35] = re.sub(rf"{field}=0x[0-9A-F]{{16}}", f"{field}=<validated-dynamic>", normalized[35], count=1)
    return normalized
