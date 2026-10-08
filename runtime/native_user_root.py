"""Independent marker checks for the bounded PKUSER6 user-preemption probe."""
from __future__ import annotations

import re
from runtime import native_kernel_transfer as transfer

FEATURE = "development-user-root"
SELECTOR = 23
COMPLETION = b"POOLEOS:KERNEL:USER-ROOT-RESULT PASS"
PREPARED = re.compile(r"POOLEOS:KERNEL:USER-ROOT-PREPARED PASS contract=PKUSER3 original=(0x[0-9A-F]{16}) candidate=(0x[0-9A-F]{16}) generation=([0-9]+) pages=13 allocations=5 retained_free_denials=5 temporary_aliases=0 ring3=0")
ACTIVE = re.compile(r"POOLEOS:KERNEL:USER-ROOT-ACTIVE PASS cr3=(0x[0-9A-F]{16}) stack_probe=(0x[0-9A-F]{16}) cpl=0 if=0 ring3=0")
TIMER = re.compile(r"POOLEOS:KERNEL:USER-ROOT-TIMER PASS contract=PKUSER4 cr3=(0x[0-9A-F]{16}) deliveries=3 eois=3 mmio_pages=2 quiesced=1 if=0 ring3=0")
ENTRY = re.compile(r"POOLEOS:KERNEL:USER-ENTRY PASS contract=PKUSER5 cr3=(0x[0-9A-F]{16}) cpl=3 traps=7 private_rsp0=1 gpr_zero=15 fp_cleared=1 cli_denied=1 io_denied=1 syscall_denied=1 supervisor_fault=1 nx_fault=1 kernel_return=1 descriptors_detached=1 if=0 production=0")
PREEMPT = re.compile(r"POOLEOS:KERNEL:USER-PREEMPT PASS contract=PKUSER6 cr3=(0x[0-9A-F]{16}) cpl=3 deliveries=3 eois=3 resumes=2 first_progress=([0-9]+) last_progress=([0-9]+) private_rsp0=1 gpr_preserved=14 fp_preserved=1 timer_quiesced=1 forced_return=1 if=0 production=0")
RESULT = re.compile(r"POOLEOS:KERNEL:USER-ROOT-RESULT PASS restored=(0x[0-9A-F]{16}) cr3_writes=2 allocated_pages=([0-9]+) retained_acpi_pages=([0-9]+) released_pages=13 scrubbed_data_pages=6 ring3=1 production=0 terminal=halt")


def validate_markers(markers: list[str]) -> dict:
    if len(markers) != 35:
        raise ValueError("PKUSER6 requires exactly 35 markers")
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != SELECTOR:
        raise ValueError("PKUSER3 wrong development selector")
    prefix = markers[:29]
    prefix[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", prefix[23], count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt "
                  "entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common = transfer.validate_markers(prefix)
    common["transfer_arm"]["trap_scenario"] = SELECTOR
    common.pop("kernel_terminal", None)
    common["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    prepared, active, timer, entry, preempt, result = [pattern.fullmatch(marker) for pattern, marker in
                                zip((PREPARED, ACTIVE, TIMER, ENTRY, PREEMPT, RESULT), markers[29:])]
    if any(m is None for m in (prepared, active, timer, entry, preempt, result)):
        raise ValueError("PKUSER6 marker layout or bounded claims changed")
    original, candidate = (int(prepared[i], 16) for i in (1, 2))
    generation = int(prepared[3])
    probe = int(active[2], 16)
    if (original != common["transfer_arm"]["root"] or original == candidate
            or candidate == 0 or candidate & 4095 or candidate >= (1 << 32)
            or generation == 0 or generation >= (1 << 64)
            or int(active[1], 16) != candidate or int(timer[1], 16) != candidate or int(entry[1], 16) != candidate
            or int(preempt[1], 16) != candidate or not (0 < int(preempt[2]) < int(preempt[3]) < (1 << 64))
            or int(result[1], 16) != original
            or not (0 < int(result[2]) == int(result[3]) <= 19)
            or probe != candidate ^ generation ^ 0x504B555345523300):
        raise ValueError("PKUSER3 live root/probe/restoration binding changed")
    return {"transfer_prefix": common, "original_root": original, "candidate_root": candidate,
            "generation": generation, "stack_probe": probe, "root_probe_cpl": 0, "cpl": 3,
            "cr3_writes": 2, "timer_deliveries": 3, "timer_eois": 3,
            "timer_quiesced": True, "retained_acpi_pages": int(result[3]),
            "ring3_executed": True, "user_traps": 7, "private_rsp0": True,
            "user_timer_preemption": True, "user_timer_deliveries": 3, "user_timer_eois": 3,
            "user_resumes": 2, "first_progress": int(preempt[2]), "last_progress": int(preempt[3]),
            "production_ready": False}


def negative_controls(markers: list[str]) -> int:
    """Mutate every field in each live marker, plus sequencing and selector."""
    validate_markers(markers)
    candidates = [markers[:-1], [*markers, markers[-1]],
                  [*markers[:29], markers[30], markers[29], *markers[31:]]]
    wrong = markers.copy()
    wrong[23] = wrong[23].replace("trap_scenario=23", "trap_scenario=0")
    candidates.append(wrong)
    for i in range(29, 35):
        for match in re.finditer(r"\b[a-zA-Z_0-9]+=[^ ]+", markers[i]):
            changed = markers.copy()
            changed[i] = markers[i][:match.start()] + "invalid=invalid" + markers[i][match.end():]
            candidates.append(changed)
    for candidate in candidates:
        try:
            validate_markers(candidate)
        except (ValueError, transfer.KernelTransferError):
            continue
        raise ValueError("PKUSER3 corrupted evidence was accepted")
    return len(candidates)
