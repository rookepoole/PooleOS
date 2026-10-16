"""PSESSION1 observation oracle; recorded text alone is not execution evidence."""
from __future__ import annotations

import re
from runtime import native_kernel_transfer as transfer

START = re.compile(r"POOLEOS:SESSION START contract=PSESSION1 programs=2 bootstrap=PSTART1 abi=PSABI1 init_bytes=([0-9]+) counter_bytes=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) granted_handles=4 diagnostics=0 production=0")
RUN = re.compile(r"POOLEOS:SESSION RUN dispatches=([0-9]+) calls0=([0-9]+) calls1=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) waits=([0-9]+) wakes=([0-9]+) preemptions=([0-9]+) yields=([0-9]+) cr3_writes=([0-9]+) cpl=3 kernel_root_restored=1 production=0")
STOP = "POOLEOS:SESSION STOP task={task} reason=exit value={code} authority_revoked=1 image_reaped=1 production=0"
EMPTY = "POOLEOS:SESSION EMPTY tasks=0 objects=0 released_pages=26 kernel_alive=1 production=0"
COMPLETION = b"POOLEOS:SESSION RUN dispatches=512 "


def extract_markers(raw: bytes) -> list[str]:
    text = raw.decode("ascii", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
    # QMP can stop a continuous session partway through the next logging operation.
    # Only complete records count; the complete prefix still must reach acceptance.
    return [line.strip() for line in text.split("\n")[:-1]
            if line.strip().startswith(("POOLEBOOT/0.1 ", "POOLEOS:"))]


def validate_markers(markers: list[str], *, bad_startup: bool = False) -> dict:
    if len(markers) < 33:
        raise ValueError("session prefix/start/progress missing")
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != 23:
        raise ValueError("session requires independently validated selector23")
    prefix = markers[:29]
    prefix[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", prefix[23], count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common = transfer.validate_markers(prefix)
    common["transfer_arm"]["trap_scenario"] = 23
    common.pop("kernel_terminal", None)
    common["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    start = START.fullmatch(markers[29])
    if start is None or any(not 0 < int(start[i]) <= 4096 for i in (1, 2)):
        raise ValueError("session owned-program identity missing")
    roots = [int(start[i], 16) for i in (3, 4)]
    original = common["transfer_arm"]["root"]
    if roots[0] == roots[1] or any(r == original or r == 0 or r & 4095 or r >= 1 << 32 for r in roots):
        raise ValueError("session roots must be distinct owned DMA32 roots")
    if bad_startup:
        expected = [STOP.format(task=1, code=120), STOP.format(task=0, code=111), EMPTY]
        if markers[30:] != expected:
            raise ValueError("bad role must fail in user decoder and retire its dependent")
        progress = []
    else:
        progress = []
        for row, marker in enumerate(markers[30:], 1):
            match = RUN.fullmatch(marker)
            if match is None:
                raise ValueError("unexpected session event or diagnostic record")
            values = tuple(map(int, match.groups()))
            d, c0, c1, t0, t1, waits, wakes, preemptions, yields, writes = values
            if (any(v >= 1 << 64 for v in values) or d != row * 64 or writes != d * 2
                    or d != waits + preemptions + yields or not 0 < wakes <= waits or waits - wakes > 2
                    or min(c0, c1, t0, t1) <= 0 or abs(c0 - c1) > 16):
                raise ValueError("session accounting/progress inconsistent")
            if progress and any(values[i] <= progress[-1][i] for i in (0, 1, 2, 3, 4)):
                raise ValueError("both real tasks must continue making progress")
            progress.append(values)
        if not progress or progress[-1][0] < 512 or min(progress[-1][1:3]) < 512:
            raise ValueError("session observation interval too short")
    return dict(transfer_prefix=common, program_bytes=[int(start[1]), int(start[2])],
                roots=roots, samples=progress, malformed_startup_denied=bad_startup,
                native_execution_requires_guest_binding=True, iso_built=False, production_ready=False)


def negative_controls(markers: list[str], *, bad_startup: bool = False) -> int:
    validate_markers(markers, bad_startup=bad_startup)
    # Dropping optional observations after the required 512-dispatch window is
    # not a falsification; omission within the acceptance interval must reject.
    required = len(markers) if bad_startup else min(len(markers), 38)
    candidates = [markers[:i] + markers[i+1:] for i in range(required)]
    candidates += [markers + [markers[-1]], markers[:29] + [markers[29].replace("production=0", "production=1")] + markers[30:]]
    for i in range(29, len(markers)):
        for match in re.finditer(r"(?<==)(?:0x[0-9A-F]+|[0-9]+)(?= |$)", markers[i]):
            replacement = "0" if match.group() != "0" else "1"
            candidate = markers.copy()
            candidate[i] = markers[i][:match.start()] + replacement + markers[i][match.end():]
            candidates.append(candidate)
    for candidate in candidates:
        try:
            validate_markers(candidate, bad_startup=bad_startup)
        except ValueError:
            continue
        raise ValueError("hostile observation accepted")
    return len(candidates)
