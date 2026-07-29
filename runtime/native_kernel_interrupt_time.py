"""Independent PKIRQ1 MADT, vector, clock, and live-marker oracle."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime import native_kernel_transfer
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKIRQ1"
SELECTED_MOVE_ID = "N8-IRQ-001"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = "specs/native-kernel-interrupt-time-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-interrupt-time-contract.schema.json"
READINESS_RELATIVE = "runs/native-kernel-interrupt-time-readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-interrupt-time-readiness.schema.json"
FEATURE = "development-interrupt-time"
SELECTOR = 11
MARKER_COUNT = 36
BOOT_TRANSFER_MARKER_COUNT = 25
COMMON_KERNEL_MARKER_START = 26
COMMON_KERNEL_MARKER_COUNT = 4
COMPLETION_MARKER = b"POOLEOS:KERNEL:IRQ-RESULT PASS contract=PKIRQ1"
PAGE_BYTES = 4096
MAX_PROCESSORS = 32
MAX_IO_APICS = 8
MAX_OVERRIDES = 24
MAX_NMI_SOURCES = 16
MAX_LOCAL_NMIS = 32
TIMER_VECTOR = 0x40
IPI_VECTOR_FIRST = 0xE0
IPI_VECTOR_LAST = 0xEF
APIC_ERROR_VECTOR = 0xF0
SPURIOUS_VECTOR = 0xFF
EXPECTED_DELIVERIES = 8

IMPLEMENTATION_INPUTS = (
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/exit.rs",
    "native/bootexit/src/lib.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kernel/src/arch/x86_64.rs",
    "native/kernel/src/acpi.rs",
    "native/kernel/src/interrupt_time.rs",
    "native/kernel/src/physical_memory.rs",
    "native/kernel/src/virtual_memory.rs",
    "native/kmap/src/lib.rs",
    "native/kmap/src/bin/pkmap2_probe.rs",
    "runtime/native_kernel_interrupt_time.py",
    "runtime/native_kernel_map.py",
    "specs/native-kernel-entry-contract.json",
    "specs/native-kernel-map-contract.json",
    "specs/native-kernel-interrupt-time-contract.json",
    "specs/native-kernel-interrupt-time-contract.schema.json",
    "specs/native-kernel-interrupt-time-readiness.schema.json",
    "tools/qualify_native_kernel_interrupt_time.py",
    "tests/test_native_kernel_interrupt_time.py",
    "docs/native-kernel-interrupt-time.md",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N8-PKIRQ-MARKER-OMISSION",
    "NEG-N8-PKIRQ-MARKER-ORDER",
    "NEG-N8-PKIRQ-MARKER-DUPLICATE",
    "NEG-N8-PKIRQ-SELECTOR",
    "NEG-N8-PKIRQ-CONTRACT",
    "NEG-N8-PKIRQ-MADT-LENGTH",
    "NEG-N8-PKIRQ-PROCESSOR-COUNT",
    "NEG-N8-PKIRQ-ENABLED-COUNT",
    "NEG-N8-PKIRQ-IOAPIC-COUNT",
    "NEG-N8-PKIRQ-OVERRIDE-COUNT",
    "NEG-N8-PKIRQ-PCAT",
    "NEG-N8-PKIRQ-APIC-ADDRESS",
    "NEG-N8-PKIRQ-HPET-ADDRESS",
    "NEG-N8-PKIRQ-SNAPSHOT",
    "NEG-N8-PKIRQ-COMPLETE-WALK",
    "NEG-N8-PKIRQ-APIC-ID",
    "NEG-N8-PKIRQ-APIC-VERSION",
    "NEG-N8-PKIRQ-MAX-LVT",
    "NEG-N8-PKIRQ-GLOBAL-ENABLE",
    "NEG-N8-PKIRQ-MSR-WRITES",
    "NEG-N8-PKIRQ-SVR",
    "NEG-N8-PKIRQ-PIC-MASK",
    "NEG-N8-PKIRQ-MMIO-CACHE",
    "NEG-N8-PKIRQ-MMIO-GUARDS",
    "NEG-N8-PKIRQ-VECTOR-COUNT",
    "NEG-N8-PKIRQ-TIMER-VECTOR",
    "NEG-N8-PKIRQ-IPI-RANGE",
    "NEG-N8-PKIRQ-VECTOR-COLLISION",
    "NEG-N8-PKIRQ-CLOCK-SOURCE",
    "NEG-N8-PKIRQ-COUNTER-WIDTH",
    "NEG-N8-PKIRQ-HPET-PERIOD",
    "NEG-N8-PKIRQ-SAMPLE-ARITHMETIC",
    "NEG-N8-PKIRQ-APIC-FREQUENCY",
    "NEG-N8-PKIRQ-TIMER-COUNT",
    "NEG-N8-PKIRQ-MONOTONIC",
    "NEG-N8-PKIRQ-OVERFLOW-POLICY",
    "NEG-N8-PKIRQ-DELIVERY-COUNT",
    "NEG-N8-PKIRQ-EOI-COUNT",
    "NEG-N8-PKIRQ-APIC-ERROR",
    "NEG-N8-PKIRQ-SPURIOUS",
    "NEG-N8-PKIRQ-IN-SERVICE",
    "NEG-N8-PKIRQ-ONE-SHOT",
    "NEG-N8-PKIRQ-ROLLBACK",
    "NEG-N8-PKIRQ-MMIO-REVOKE",
    "NEG-N8-PKIRQ-PIC-RESTORE",
    "NEG-N8-PKIRQ-INTERRUPT-STATE",
    "NEG-N8-PKIRQ-SMP-OVERCLAIM",
    "NEG-N8-PKIRQ-AP-OVERCLAIM",
    "NEG-N8-PKIRQ-SHOOTDOWN-OVERCLAIM",
    "NEG-N8-PKIRQ-TARGET-OVERCLAIM",
    "NEG-N8-PKIRQ-AUTHORITY-OVERCLAIM",
    "NEG-N8-PKIRQ-PRODUCTION-OVERCLAIM",
    "NEG-N8-PKIRQ-MADT-STRUCTURE-LENGTH",
    "NEG-N8-PKIRQ-MADT-DUPLICATE-PROCESSOR",
    "NEG-N8-PKIRQ-MADT-RESERVED-FLAGS",
    "NEG-N8-PKIRQ-VECTOR-LEDGER-COLLISION",
    "NEG-N8-PKIRQ-HPET-WRAP-AMBIGUITY",
    "NEG-N8-PKIRQ-CALIBRATION-RANGE",
)

EARLY = re.compile(
    r"^POOLEOS:KERNEL:IRQ-EARLY PASS contract=(PKIRQ1) selector=([0-9]+) "
    r"bsp=([0-9]+) if=([0-9]+) stack=validated_by_wrapper serial=initialized$"
)
ACPI = re.compile(
    r"^POOLEOS:KERNEL:IRQ-ACPI PASS contract=(PKIRQ1) madt_bytes=([0-9]+) "
    r"processors=([0-9]+) enabled=([0-9]+) ioapics=([0-9]+) overrides=([0-9]+) "
    r"nmi_sources=([0-9]+) local_nmis=([0-9]+) unknown=([0-9]+) pcat=([0-9]+) "
    r"apic_physical=0x([0-9A-F]{16}) hpet_physical=0x([0-9A-F]{16}) "
    r"retained_snapshot=([0-9]+) complete_walk=([0-9]+)$"
)
APIC = re.compile(
    r"^POOLEOS:KERNEL:IRQ-APIC PASS contract=(PKIRQ1) apic_id=([0-9]+) version=([0-9]+) "
    r"max_lvt=([0-9]+) global_enable=([0-9]+) msr_writes=([0-9]+) svr_vector=([0-9]+) "
    r"software_enable=([0-9]+) pic_masked=([0-9]+) mmio=([a-z]+) guarded=([0-9]+)$"
)
VECTORS = re.compile(
    r"^POOLEOS:KERNEL:IRQ-VECTORS PASS contract=(PKIRQ1) owned=([0-9]+) timer=([0-9]+) "
    r"ipi_first=([0-9]+) ipi_last=([0-9]+) error=([0-9]+) spurious=([0-9]+) "
    r"collisions=([a-z_]+)$"
)
CLOCK = re.compile(
    r"^POOLEOS:KERNEL:IRQ-CLOCK PASS contract=(PKIRQ1) source=([a-z]+) counter_bits=([0-9]+) "
    r"period_fs=([0-9]+) sample_ticks=([0-9]+) sample_ns=([0-9]+) apic_ticks=([0-9]+) "
    r"apic_hz=([0-9]+) one_shot_initial=([0-9]+) monotonic_ns=([0-9]+) "
    r"overflow=([a-z]+) wrap=([a-z]+)$"
)
DELIVERY = re.compile(
    r"^POOLEOS:KERNEL:IRQ-DELIVERY PASS contract=(PKIRQ1) timer_deliveries=([0-9]+) "
    r"eois=([0-9]+) apic_errors=([0-9]+) spurious=([0-9]+) in_service_after=([0-9]+) "
    r"exact_one_shot=([0-9]+) unacknowledged=([0-9]+)$"
)
RESULT = re.compile(
    r"^POOLEOS:KERNEL:IRQ-RESULT PASS contract=(PKIRQ1) profile=(qemu64_tier0) bsp=([0-9]+) "
    r"madt=([0-9]+) local_apic=([0-9]+) hpet=([0-9]+) vectors=([0-9]+) timer=([0-9]+) "
    r"deliveries=([0-9]+) rollback=([0-9]+) mmio_revoked=([0-9]+) pic_restored=([0-9]+) "
    r"interrupts=([a-z]+) smp=([0-9]+) ap_start=([0-9]+) shootdown=([0-9]+) target=([0-9]+) "
    r"signatures=([0-9]+) authority=([0-9]+) actions=([0-9]+) production=([0-9]+) terminal=(halt)$"
)


class KernelInterruptTimeError(RuntimeError):
    """Raised when PKIRQ1 data or evidence violates the frozen contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KernelInterruptTimeError(message)


def _match(pattern: re.Pattern[str], marker: str, label: str) -> re.Match[str]:
    match = pattern.fullmatch(marker)
    _require(match is not None, f"PKIRQ1 {label} marker violates its contract")
    assert match is not None
    return match


def _dec(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 10)


def _hex(match: re.Match[str], group: int) -> int:
    return int(match.group(group), 16)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise KernelInterruptTimeError(f"{path} is not a JSON object")
    return value


def file_binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    data = path.read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def expected_inputs(root: Path = ROOT) -> dict[str, Any]:
    return {"implementation": [file_binding(root, path) for path in IMPLEMENTATION_INPUTS]}


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = list(validate_json(contract, schema))
    expected = list(NEGATIVE_CONTROL_IDS)
    if contract.get("required_negative_controls") != expected:
        errors.append("required negative controls diverge")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors = list(validate_json(readiness, schema))
    if readiness.get("inputs") != expected_inputs(root):
        errors.append("readiness input bindings are stale")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("readiness negative-control order diverges")
    return errors


def expected_claims(root: Path = ROOT) -> dict[str, bool]:
    return read_json(root / CONTRACT_RELATIVE)["claims"]


def _mps_flags(flags: int) -> None:
    _require(flags & ~0xF == 0, "MADT MPS flags contain reserved bits")
    _require(flags & 0x3 != 0x2, "MADT polarity encoding is reserved")
    _require(flags & 0xC != 0x8, "MADT trigger encoding is reserved")


def parse_madt_table(data: bytes) -> dict[str, Any]:
    _require(len(data) >= 44, "MADT is shorter than its fixed header")
    _require(data[:4] == b"APIC", "MADT signature changed")
    _require(struct.unpack_from("<I", data, 4)[0] == len(data), "MADT length changed")
    flags = struct.unpack_from("<I", data, 40)[0]
    _require(flags & ~1 == 0, "MADT flags contain reserved bits")
    local_apic = struct.unpack_from("<I", data, 36)[0]
    processors: list[tuple[int, int, bool, bool, bool]] = []
    io_apics: list[tuple[int, int, int]] = []
    overrides: list[tuple[int, int, int, int]] = []
    nmi_sources: list[tuple[int, int]] = []
    local_nmis: list[tuple[int, int, int, bool]] = []
    address_overrides = 0
    unknown = 0
    cursor = 44
    lengths = {0: 8, 1: 12, 2: 10, 3: 8, 4: 6, 5: 12, 9: 16, 10: 12}
    while cursor < len(data):
        _require(len(data) - cursor >= 2, "MADT structure header is truncated")
        kind, length = data[cursor], data[cursor + 1]
        _require(length >= 2 and cursor + length <= len(data), "MADT structure length is invalid")
        if kind in lengths:
            _require(length == lengths[kind], "MADT known structure length changed")
        if kind == 0:
            uid, apic_id = data[cursor + 2], data[cursor + 3]
            local_flags = struct.unpack_from("<I", data, cursor + 4)[0]
            _require(local_flags & ~3 == 0, "MADT processor flags contain reserved bits")
            item = (uid, apic_id, bool(local_flags & 1), bool(local_flags & 2), False)
            _require(all(old[0] != uid and old[1] != apic_id for old in processors), "duplicate MADT processor")
            _require(len(processors) < MAX_PROCESSORS, "MADT processor capacity exceeded")
            processors.append(item)
        elif kind == 1:
            _require(data[cursor + 3] == 0, "MADT I/O APIC reserved byte changed")
            item = (data[cursor + 2], *struct.unpack_from("<II", data, cursor + 4))
            _require(item[1] != 0 and item[1] % PAGE_BYTES == 0, "MADT I/O APIC address is invalid")
            _require(all(old[0] != item[0] for old in io_apics), "duplicate MADT I/O APIC")
            _require(len(io_apics) < MAX_IO_APICS, "MADT I/O APIC capacity exceeded")
            io_apics.append(item)
        elif kind == 2:
            item = (data[cursor + 2], data[cursor + 3], *struct.unpack_from("<IH", data, cursor + 4))
            _mps_flags(item[3])
            _require(all(old[:2] != item[:2] for old in overrides), "duplicate MADT interrupt override")
            _require(len(overrides) < MAX_OVERRIDES, "MADT override capacity exceeded")
            overrides.append(item)
        elif kind == 3:
            item = struct.unpack_from("<HI", data, cursor + 2)
            _mps_flags(item[0])
            _require(len(nmi_sources) < MAX_NMI_SOURCES, "MADT NMI-source capacity exceeded")
            nmi_sources.append(item)
        elif kind == 4:
            local_flags = struct.unpack_from("<H", data, cursor + 3)[0]
            _mps_flags(local_flags)
            _require(data[cursor + 5] <= 1, "MADT local NMI LINT is invalid")
            _require(len(local_nmis) < MAX_LOCAL_NMIS, "MADT local-NMI capacity exceeded")
            local_nmis.append((data[cursor + 2], data[cursor + 5], local_flags, False))
        elif kind == 5:
            _require(address_overrides == 0, "duplicate MADT LAPIC address override")
            _require(struct.unpack_from("<H", data, cursor + 2)[0] == 0, "MADT address override reserved bits changed")
            local_apic = struct.unpack_from("<Q", data, cursor + 4)[0]
            _require(local_apic != 0 and local_apic % PAGE_BYTES == 0, "MADT LAPIC address is invalid")
            address_overrides = 1
        elif kind == 9:
            _require(struct.unpack_from("<H", data, cursor + 2)[0] == 0, "MADT x2APIC reserved bits changed")
            apic_id, local_flags, uid = struct.unpack_from("<III", data, cursor + 4)
            _require(local_flags & ~3 == 0, "MADT x2APIC flags contain reserved bits")
            item = (uid, apic_id, bool(local_flags & 1), bool(local_flags & 2), True)
            _require(all(old[0] != uid and old[1] != apic_id for old in processors), "duplicate MADT processor")
            _require(len(processors) < MAX_PROCESSORS, "MADT processor capacity exceeded")
            processors.append(item)
        elif kind == 10:
            _require(struct.unpack_from("<H", data, cursor + 2)[0] == 0, "MADT x2APIC NMI reserved bits changed")
            uid = struct.unpack_from("<I", data, cursor + 4)[0]
            local_flags = struct.unpack_from("<H", data, cursor + 8)[0]
            _mps_flags(local_flags)
            _require(data[cursor + 10] <= 1 and data[cursor + 11] == 0, "MADT x2APIC NMI shape changed")
            _require(len(local_nmis) < MAX_LOCAL_NMIS, "MADT local-NMI capacity exceeded")
            local_nmis.append((uid, data[cursor + 10], local_flags, True))
        else:
            unknown += 1
        cursor += length
    _require(local_apic != 0 and local_apic % PAGE_BYTES == 0, "MADT LAPIC address is invalid")
    _require(processors and any(item[2] for item in processors), "MADT has no enabled processor")
    return {
        "local_apic_address": local_apic,
        "pcat_compatible": bool(flags & 1),
        "processor_count": len(processors),
        "enabled_processor_count": sum(item[2] for item in processors),
        "io_apic_count": len(io_apics),
        "override_count": len(overrides),
        "nmi_source_count": len(nmi_sources),
        "local_nmi_count": len(local_nmis),
        "unknown_structure_count": unknown,
        "address_override_count": address_overrides,
        "processors": processors,
        "io_apics": io_apics,
        "overrides": overrides,
    }


def reserve_vector(owners: dict[int, str], vector: int, owner: str) -> None:
    _require(0 <= vector <= 255 and owner != "free", "vector reservation is invalid")
    _require(vector not in owners, "vector is already owned")
    owners[vector] = owner


def vector_ledger() -> dict[int, str]:
    owners: dict[int, str] = {}

    for vector in range(32):
        reserve_vector(owners, vector, "exception")
    reserve_vector(owners, TIMER_VECTOR, "timer")
    for vector in range(IPI_VECTOR_FIRST, IPI_VECTOR_LAST + 1):
        reserve_vector(owners, vector, "future_ipi")
    reserve_vector(owners, APIC_ERROR_VECTOR, "apic_error")
    reserve_vector(owners, SPURIOUS_VECTOR, "spurious")
    return owners


@dataclass
class HpetClock:
    counter_bits: int
    period_femtoseconds: int
    last_raw: int
    max_sample_delta: int
    elapsed_ticks: int = 0

    def __post_init__(self) -> None:
        _require(self.counter_bits in (32, 64), "HPET counter width is unsupported")
        _require(100_000 <= self.period_femtoseconds <= 100_000_000, "HPET period is invalid")
        mask = (1 << self.counter_bits) - 1
        _require(self.last_raw & ~mask == 0, "HPET initial counter exceeds its width")
        _require(0 < self.max_sample_delta <= mask // 2, "HPET sample bound is invalid")

    def sample(self, raw: int) -> int:
        mask = (1 << self.counter_bits) - 1
        _require(raw & ~mask == 0, "HPET sample exceeds its width")
        delta = (raw - self.last_raw) & mask
        if self.counter_bits == 64 and raw < self.last_raw:
            raise KernelInterruptTimeError("64-bit HPET counter regressed")
        _require(0 < delta <= self.max_sample_delta, "HPET sample delta is zero or ambiguous")
        self.elapsed_ticks += delta
        self.last_raw = raw
        nanoseconds = self.elapsed_ticks * self.period_femtoseconds // 1_000_000
        _require(nanoseconds <= 0xFFFF_FFFF_FFFF_FFFF, "HPET nanoseconds overflowed u64")
        return nanoseconds


def calibrate_apic_timer(
    initial_count: int, current_count: int, hpet_ticks: int, period_femtoseconds: int
) -> dict[str, int]:
    _require(0 <= current_count < initial_count <= 0xFFFF_FFFF, "APIC calibration sample is invalid")
    _require(hpet_ticks > 0, "HPET calibration sample is empty")
    _require(100_000 <= period_femtoseconds <= 100_000_000, "HPET period is invalid")
    elapsed = initial_count - current_count
    sample_fs = hpet_ticks * period_femtoseconds
    sample_ns = sample_fs // 1_000_000
    _require(1_000_000 <= sample_ns <= 1_000_000_000, "APIC calibration interval is out of range")
    frequency = elapsed * 1_000_000_000_000_000 // sample_fs
    _require(100_000 <= frequency <= 10_000_000_000, "APIC frequency is out of range")
    return {"elapsed_apic_ticks": elapsed, "sample_nanoseconds": sample_ns, "apic_ticks_per_second": frequency}


def timer_initial_count(frequency: int, interval_nanoseconds: int) -> int:
    _require(frequency > 0 and interval_nanoseconds > 0, "timer request is empty")
    return min(max(frequency * interval_nanoseconds // 1_000_000_000, 1), 0xFFFF_FFFF)


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
        raise KernelInterruptTimeError(str(error)) from error
    summary["transfer_arm"]["trap_scenario"] = SELECTOR
    summary.pop("kernel_terminal", None)
    summary["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    return summary


def validate_markers(markers: list[str]) -> dict[str, Any]:
    _require(len(markers) == MARKER_COUNT, f"expected {MARKER_COUNT} PKIRQ1 markers")
    arm = native_kernel_transfer.TRANSFER_ARM.fullmatch(markers[23])
    _require(arm is not None and int(arm.group(10), 10) == SELECTOR, "PKIRQ1 transfer selector changed")
    prefix = _prefix(markers)
    early = _match(EARLY, markers[25], "early")
    acpi_match = _match(ACPI, markers[30], "ACPI")
    apic_match = _match(APIC, markers[31], "APIC")
    vector_match = _match(VECTORS, markers[32], "vectors")
    clock_match = _match(CLOCK, markers[33], "clock")
    delivery_match = _match(DELIVERY, markers[34], "delivery")
    result_match = _match(RESULT, markers[35], "result")
    _require((_dec(early, 2), _dec(early, 3), _dec(early, 4)) == (SELECTOR, 1, 0), "PKIRQ1 early state changed")

    acpi = {
        "madt_bytes": _dec(acpi_match, 2),
        "processors": _dec(acpi_match, 3),
        "enabled": _dec(acpi_match, 4),
        "ioapics": _dec(acpi_match, 5),
        "overrides": _dec(acpi_match, 6),
        "nmi_sources": _dec(acpi_match, 7),
        "local_nmis": _dec(acpi_match, 8),
        "unknown": _dec(acpi_match, 9),
        "pcat": _dec(acpi_match, 10),
        "apic_physical": _hex(acpi_match, 11),
        "hpet_physical": _hex(acpi_match, 12),
        "retained_snapshot": _dec(acpi_match, 13),
        "complete_walk": _dec(acpi_match, 14),
    }
    _require(acpi == {
        "madt_bytes": 120, "processors": 1, "enabled": 1, "ioapics": 1,
        "overrides": 5, "nmi_sources": 0, "local_nmis": 1, "unknown": 0,
        "pcat": 1, "apic_physical": 0xFEE0_0000, "hpet_physical": 0xFED0_0000,
        "retained_snapshot": 1, "complete_walk": 1,
    }, "PKIRQ1 Tier-0 ACPI observation changed")

    apic = {
        "apic_id": _dec(apic_match, 2), "version": _dec(apic_match, 3),
        "max_lvt": _dec(apic_match, 4), "global_enable": _dec(apic_match, 5),
        "msr_writes": _dec(apic_match, 6), "svr_vector": _dec(apic_match, 7),
        "software_enable": _dec(apic_match, 8), "pic_masked": _dec(apic_match, 9),
        "mmio": apic_match.group(10), "guarded": _dec(apic_match, 11),
    }
    _require(apic == {
        "apic_id": 0, "version": 20, "max_lvt": 5, "global_enable": 1,
        "msr_writes": 0, "svr_vector": SPURIOUS_VECTOR, "software_enable": 1,
        "pic_masked": 1, "mmio": "uncacheable", "guarded": 3,
    }, "PKIRQ1 APIC observation changed")

    vectors = {
        "owned": _dec(vector_match, 2), "timer": _dec(vector_match, 3),
        "ipi_first": _dec(vector_match, 4), "ipi_last": _dec(vector_match, 5),
        "error": _dec(vector_match, 6), "spurious": _dec(vector_match, 7),
        "collisions": vector_match.group(8),
    }
    _require(vectors == {
        "owned": len(vector_ledger()), "timer": TIMER_VECTOR,
        "ipi_first": IPI_VECTOR_FIRST, "ipi_last": IPI_VECTOR_LAST,
        "error": APIC_ERROR_VECTOR, "spurious": SPURIOUS_VECTOR,
        "collisions": "host_verified",
    }, "PKIRQ1 vector ownership changed")

    clock = {
        "source": clock_match.group(2), "counter_bits": _dec(clock_match, 3),
        "period_fs": _dec(clock_match, 4), "sample_ticks": _dec(clock_match, 5),
        "sample_ns": _dec(clock_match, 6), "apic_ticks": _dec(clock_match, 7),
        "apic_hz": _dec(clock_match, 8), "one_shot_initial": _dec(clock_match, 9),
        "monotonic_ns": _dec(clock_match, 10), "overflow": clock_match.group(11),
        "wrap": clock_match.group(12),
    }
    _require(clock["source"] == "hpet" and clock["counter_bits"] == 64, "PKIRQ1 clock source changed")
    _require(clock["period_fs"] == 10_000_000, "PKIRQ1 HPET period changed")
    _require(clock["sample_ticks"] * clock["period_fs"] // 1_000_000 == clock["sample_ns"], "PKIRQ1 HPET arithmetic diverges")
    _require(clock["apic_ticks"] * 1_000_000_000 // clock["sample_ns"] == clock["apic_hz"], "PKIRQ1 APIC calibration diverges")
    _require(timer_initial_count(clock["apic_hz"], 10_000_000) == clock["one_shot_initial"], "PKIRQ1 one-shot count diverges")
    _require(80_000_000 <= clock["monotonic_ns"] <= 100_000_000 and clock["monotonic_ns"] % 10 == 0, "PKIRQ1 monotonic sample is out of bounds")
    _require((clock["overflow"], clock["wrap"]) == ("checked", "bounded"), "PKIRQ1 overflow policy changed")

    delivery = {
        "timer_deliveries": _dec(delivery_match, 2), "eois": _dec(delivery_match, 3),
        "apic_errors": _dec(delivery_match, 4), "spurious": _dec(delivery_match, 5),
        "in_service_after": _dec(delivery_match, 6), "exact_one_shot": _dec(delivery_match, 7),
        "unacknowledged": _dec(delivery_match, 8),
    }
    _require(delivery == {
        "timer_deliveries": EXPECTED_DELIVERIES, "eois": EXPECTED_DELIVERIES,
        "apic_errors": 0, "spurious": 0, "in_service_after": 0,
        "exact_one_shot": 1, "unacknowledged": 0,
    }, "PKIRQ1 delivery accounting changed")

    result = {
        "profile": result_match.group(2), "bsp": _dec(result_match, 3),
        "madt": _dec(result_match, 4), "local_apic": _dec(result_match, 5),
        "hpet": _dec(result_match, 6), "vectors": _dec(result_match, 7),
        "timer": _dec(result_match, 8), "deliveries": _dec(result_match, 9),
        "rollback": _dec(result_match, 10), "mmio_revoked": _dec(result_match, 11),
        "pic_restored": _dec(result_match, 12), "interrupts": result_match.group(13),
        "smp": _dec(result_match, 14), "ap_start": _dec(result_match, 15),
        "shootdown": _dec(result_match, 16), "target": _dec(result_match, 17),
        "signatures": _dec(result_match, 18), "authority": _dec(result_match, 19),
        "actions": _dec(result_match, 20), "production": _dec(result_match, 21),
        "terminal": result_match.group(22),
    }
    _require(result == {
        "profile": "qemu64_tier0", "bsp": 1, "madt": 1, "local_apic": 1,
        "hpet": 1, "vectors": 1, "timer": 1, "deliveries": EXPECTED_DELIVERIES,
        "rollback": 1, "mmio_revoked": 1, "pic_restored": 1,
        "interrupts": "disabled", "smp": 0, "ap_start": 0, "shootdown": 0,
        "target": 0, "signatures": 0, "authority": 0, "actions": 0,
        "production": 0, "terminal": "halt",
    }, "PKIRQ1 result or nonclaim boundary changed")
    return {"transfer_prefix": prefix, "acpi": acpi, "apic": apic, "vectors": vectors, "clock": clock, "delivery": delivery, "result": result}
