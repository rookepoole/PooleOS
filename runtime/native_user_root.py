"""Independent marker checks for the bounded PKUSER3 CPL0 root probe."""
from __future__ import annotations

import re
from runtime import native_kernel_transfer as transfer

FEATURE = "development-user-root"
SELECTOR = 23
COMPLETION = b"POOLEOS:KERNEL:USER-ROOT-RESULT PASS"
PREPARED = re.compile(r"POOLEOS:KERNEL:USER-ROOT-PREPARED PASS contract=PKUSER3 original=(0x[0-9A-F]{16}) candidate=(0x[0-9A-F]{16}) generation=([0-9]+) pages=13 allocations=5 retained_free_denials=5 temporary_aliases=0 ring3=0")
ACTIVE = re.compile(r"POOLEOS:KERNEL:USER-ROOT-ACTIVE PASS cr3=(0x[0-9A-F]{16}) stack_probe=(0x[0-9A-F]{16}) cpl=0 if=0 ring3=0")
RESULT = re.compile(r"POOLEOS:KERNEL:USER-ROOT-RESULT PASS restored=(0x[0-9A-F]{16}) cr3_writes=2 allocated_pages=0 released_pages=13 scrubbed_data_pages=6 ring3=0 production=0 terminal=halt")


def validate_markers(markers: list[str]) -> dict:
    if len(markers) != 32:
        raise ValueError("PKUSER3 requires exactly 32 markers")
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
    prepared, active, result = [pattern.fullmatch(marker) for pattern, marker in
                                zip((PREPARED, ACTIVE, RESULT), markers[29:])]
    if prepared is None or active is None or result is None:
        raise ValueError("PKUSER3 marker layout or bounded claims changed")
    original, candidate = (int(prepared[i], 16) for i in (1, 2))
    generation = int(prepared[3])
    probe = int(active[2], 16)
    if (original != common["transfer_arm"]["root"] or original == candidate
            or candidate == 0 or candidate & 4095 or candidate >= (1 << 32)
            or generation == 0 or generation >= (1 << 64)
            or int(active[1], 16) != candidate or int(result[1], 16) != original
            or probe != candidate ^ generation ^ 0x504B555345523300):
        raise ValueError("PKUSER3 live root/probe/restoration binding changed")
    return {"transfer_prefix": common, "original_root": original, "candidate_root": candidate,
            "generation": generation, "stack_probe": probe, "cpl": 0,
            "cr3_writes": 2, "ring3_executed": False, "production_ready": False}


def negative_controls(markers: list[str]) -> int:
    """Mutate every field in each live marker, plus sequencing and selector."""
    validate_markers(markers)
    candidates = [markers[:-1], [*markers, markers[-1]],
                  [*markers[:29], markers[30], markers[29], markers[31]]]
    wrong = markers.copy()
    wrong[23] = wrong[23].replace("trap_scenario=23", "trap_scenario=0")
    candidates.append(wrong)
    for i in range(29, 32):
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
