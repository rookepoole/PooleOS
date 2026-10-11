"""PCONSOLE1 observations: untrusted UART bytes are never kernel evidence."""
from __future__ import annotations
import re
from runtime import native_kernel_transfer as transfer, native_session as session

BANNER = b"PooleConsole ready\r\n"
CONTROL_PREFIX_LIMIT = 4096
CONTROL_SEQUENCES = (b"\x1b[2J", b"\x1b[01;01H", b"\x1b[=3h",
    b'BdsDxe: loading Boot0001 "UEFI Misc Device" from PciRoot(0x0)/Pci(0x1,0x0)\r\n',
    b'BdsDxe: starting Boot0001 "UEFI Misc Device" from PciRoot(0x0)/Pci(0x1,0x0)\r\n',
    b"PooleOS native UEFI proof of life\r\n")
START = re.compile(r"POOLEOS:SESSION START contract=PSESSION2 programs=3 bootstrap=PSTART1 abi=PSABI1 init_bytes=([0-9]+) counter_bytes=([0-9]+) console_bytes=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) root2=(0x[0-9A-F]{16}) granted_handles=5 port=COM2 irq=0 diagnostics=0 production=0")
RUN = re.compile(session.RUN.pattern.replace(" cpl=3", r" calls2=([0-9]+) ticks2=([0-9]+) console_dead=([01]) allocated_pages=([0-9]+) cpl=3"))


def validate_markers(markers: list[str], *, bad_handle: bool = False) -> dict:
    if len(markers) < 39:
        raise ValueError("console session prefix/observation interval missing")
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != 23:
        raise ValueError("console requires selector23")
    prefix = markers[:29]
    prefix[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", prefix[23], count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common = transfer.validate_markers(prefix)
    common["transfer_arm"]["trap_scenario"] = 23
    common.pop("kernel_terminal", None)
    common["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    start = START.fullmatch(markers[29])
    if start is None or any(not 0 < int(start[i]) <= 4096 for i in (1, 2, 3)):
        raise ValueError("three owned program identities required")
    roots = [int(start[i], 16) for i in (4, 5, 6)]
    if len(set(roots)) != 3 or any(r == common["transfer_arm"]["root"] or
            not 0 < r < 1 << 32 or r & 4095 for r in roots):
        raise ValueError("private roots alias or are outside DMA32")
    stopped = False
    samples = []
    alive, dead = [], []
    expected_stop = session.STOP.format(task=2, code=131 if bad_handle else 0)
    for marker in markers[30:]:
        if marker == expected_stop:
            if stopped: raise ValueError("duplicate console retirement")
            stopped = True
            continue
        match = RUN.fullmatch(marker)
        if match is None: raise ValueError("unexpected console-session event")
        values = tuple(map(int, match.groups()))
        d,c0,c1,t0,t1,waits,wakes,preemptions,yields,writes,c2,t2,is_dead,pages = values
        if (any(v >= 1 << 64 for v in values) or d != (len(samples)+1)*64
                or writes != 2*d or d != waits+preemptions+yields+int(stopped)
                or not 0 < wakes <= waits or waits-wakes > 2 or abs(c0-c1) > 16
                or min(c0,c1,t0,t1,c2,t2) <= 0 or is_dead != int(stopped)
                or pages != (26 if stopped else 39)):
            raise ValueError("console scheduling/reap accounting inconsistent")
        if samples:
            if any(values[i] <= samples[-1][i] for i in (0,1,2,3,4)):
                raise ValueError("init/counter must continue growing, including after console death")
            if any(values[i] < samples[-1][i] for i in (5,6,7,8,9,10,11)):
                raise ValueError("cumulative observations regressed")
        (dead if stopped else alive).append(values)
        samples.append(values)
    if not stopped or len(dead) < 2 or not samples or samples[-1][0] < 512:
        raise ValueError("retirement plus surviving peer progress missing")
    if not bad_handle and (len(alive) < 2 or alive[-1][10] <= alive[0][10]
            or alive[-1][11] <= alive[0][11] or alive[-1][7]+alive[-1][8] == 0):
        raise ValueError("console dispatch progress/bounded yielding missing")
    if bad_handle and alive:
        raise ValueError("bad capability must terminate before steady console progress")
    if any(row[10:12] != dead[0][10:12] for row in dead):
        raise ValueError("retired console must never run again")
    return dict(transfer_prefix=common, program_bytes=[int(start[i]) for i in (1,2,3)],
        roots=roots, samples=samples, bad_handle_denied=bad_handle, console_exit=131 if bad_handle else 0,
        surviving_pair_verified=True, console_reaped_pages=13,
        native_execution_requires_guest_binding=True, iso_built=False, production_ready=False)


def split_output(raw: bytes, *, partial: bool = False) -> tuple[bytes, bytes]:
    """Preserve exact launch-profile prelude tokens, never discard arbitrary text."""
    at = 0
    while at < len(raw):
        tail = raw[at:]
        token = next((s for s in CONTROL_SEQUENCES if tail.startswith(s)), None)
        if token is None:
            if partial and len(raw) <= CONTROL_PREFIX_LIMIT and any(s.startswith(tail) for s in CONTROL_SEQUENCES):
                return raw, b""
            if tail.startswith(b"\x1b"): raise ValueError("unrecognized pre-session control output")
            break
        at += len(token)
        if at > CONTROL_PREFIX_LIMIT: raise ValueError("pre-session output exceeded bound")
    return raw[:at], raw[at:]


def validate_echo(sent: bytes, received: bytes, *, bad_handle: bool = False) -> dict:
    if type(sent) is not bytes or type(received) is not bytes:
        raise ValueError("exact byte capture required")
    prefix, application = split_output(received)
    if bad_handle:
        if sent or application: raise ValueError("denied console must produce no application UART traffic")
    elif not sent or len(sent) > 512 or b"\x04" in sent or application != BANNER + sent:
        raise ValueError("console did not echo exact independent host input")
    return dict(input_bytes=len(sent), output_bytes=len(received), exact_echo=not bad_handle,
        control_prefix_bytes=len(prefix), control_prefix_hex=prefix.hex(), application_output_bytes=len(application),
        console_output_is_not_kernel_evidence=True, production_ready=False)


def negative_controls(markers: list[str], *, bad_handle: bool = False) -> int:
    validate_markers(markers, bad_handle=bad_handle)
    # The last poll may include optional progress beyond the required interval.
    candidates = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    candidates += [markers+[markers[-1]], markers+["POOLEOS:PANIC injected"]]
    for i in range(29, len(markers)):
        for field in ("production=0", "kernel_root_restored=1", "image_reaped=1", "authority_revoked=1"):
            if field in markers[i]:
                copy=markers.copy(); copy[i]=copy[i].replace(field,field[:-1]+str(1-int(field[-1])))
                candidates.append(copy)
    for copy in candidates:
        try: validate_markers(copy, bad_handle=bad_handle)
        except ValueError: continue
        raise ValueError("hostile kernel observation accepted")
    return len(candidates)
