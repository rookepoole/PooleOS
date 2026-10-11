"""PSESSION3/PCS1 observations, separate from untrusted COM2 application bytes."""
from __future__ import annotations
import re
from runtime import native_console as console, native_session as session, native_kernel_transfer as transfer

START = re.compile(r"POOLEOS:SESSION START contract=PSESSION3 programs=4 bootstrap=PSTART1 abi=PSABI1 init_bytes=([0-9]+) counter_bytes=([0-9]+) console_bytes=([0-9]+) client_bytes=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) root2=(0x[0-9A-F]{16}) root3=(0x[0-9A-F]{16}) task_image_pages=52 firmware_pages=([0-9]+) granted_handles=9 protocol=PCS1 port=COM2 irq=0 diagnostics=0 production=0")
RUN = re.compile(console.RUN.pattern.replace(" cpl=3", r" calls3=([0-9]+) ticks3=([0-9]+) client_dead=([01]) cpl=3"))
TRACKED_START = re.compile(START.pattern.replace("PSESSION3", "PSESSION4").replace("protocol=PCS1 ", "protocol=PCS1 transport=PRPC1 "))
TRACKED_STOP = re.compile(r"(POOLEOS:SESSION STOP .+ production=0) dispatches=([0-9]+)")


def validate_markers(markers: list[str], *, bad_peer: bool = False) -> dict:
    return _validate_markers(markers, bad_peer=bad_peer, tracked=False)


def validate_tracked_markers(markers: list[str], *, bad_peer: bool = False) -> dict:
    return _validate_markers(markers, bad_peer=bad_peer, tracked=True)


def _validate_markers(markers: list[str], *, bad_peer: bool, tracked: bool) -> dict:
    if len(markers) < 39: raise ValueError("four-task observation interval missing")
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10)) != 23: raise ValueError("selector23 required")
    prefix = markers[:29]
    prefix[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", prefix[23], count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common = transfer.validate_markers(prefix)
    common["transfer_arm"]["trap_scenario"] = 23
    common.pop("kernel_terminal", None)
    common["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    start = (TRACKED_START if tracked else START).fullmatch(markers[29])
    if start is None or any(not 0 < int(start[i]) <= 4096 for i in range(1,5)):
        raise ValueError("four program sizes required")
    roots = [int(start[i],16) for i in range(5,9)]
    if not 0 < int(start[9]) <= 12: raise ValueError("firmware snapshot allowance exceeded")
    if len(set(roots)) != 4 or any(r == common["transfer_arm"]["root"] or not 0 < r < 1<<32 or r&4095 for r in roots):
        raise ValueError("four private DMA32 roots required")
    expected = {session.STOP.format(task=2,code=152 if bad_peer else 0):2}
    if not bad_peer or tracked: expected[session.STOP.format(task=3,code=163 if bad_peer else 0)] = 3
    stopped, samples, alive, retired = set(), [], [], []
    frozen, stop_dispatches = {}, {}
    for marker in markers[30:]:
        event = TRACKED_STOP.fullmatch(marker) if tracked else None
        if event is not None:
            marker = event[1]
        if marker in expected:
            task = expected[marker]
            if task in stopped: raise ValueError("duplicate retirement")
            if tracked:
                if event is None: raise ValueError("tracked retirement dispatch missing")
                at, previous = int(event[2]), samples[-1][0] if samples else 0
                if not previous < at <= previous+64 or at <= max(stop_dispatches.values(), default=0):
                    raise ValueError("retirement dispatch order/interval invalid")
                stop_dispatches[task] = at
            stopped.add(task)
            continue
        match = RUN.fullmatch(marker)
        if match is None: raise ValueError("unrecognized IPC session event")
        v = tuple(map(int,match.groups()))
        d,c0,c1,t0,t1,waits,wakes,preempt,yields,writes,c2,t2,dead2,pages,c3,t3,dead3 = v
        if (any(x >= 1<<64 for x in v) or d != (len(samples)+1)*64
                or writes != 2*d or d != waits+preempt+yields+len(stopped)
                or not 0 < wakes <= waits or waits-wakes > 2 or abs(c0-c1)>16
                or min(c0,c1,t0,t1,c2,t2,c3,t3)<=0
                or (dead2,dead3) != (int(2 in stopped),int(3 in stopped))
                or pages != 52-13*len(stopped)):
            raise ValueError("IPC session accounting/retirement inconsistent")
        if samples:
            if any(v[i]<=samples[-1][i] for i in (0,1,2,3,4)):
                raise ValueError("independent pair ceased progress")
            if any(v[i]<samples[-1][i] for i in (5,6,7,8,9,10,11,14,15)):
                raise ValueError("cumulative accounting regressed")
        for task, pair in ((2,(c2,t2)),(3,(c3,t3))):
            if task in stopped:
                if pair != frozen.setdefault(task,pair): raise ValueError("retired task resumed")
        if not stopped: alive.append(v)
        if stopped == set(expected.values()): retired.append(v)
        samples.append(v)
    if stopped != set(expected.values()) or len(retired)<2 or samples[-1][0]<512:
        raise ValueError("retirement/survivor interval missing")
    if bad_peer and tracked:
        if not 0 < stop_dispatches[3]-stop_dispatches[2] <= 8 or max(stop_dispatches.values()) > 64:
            raise ValueError("bounded peer-death retirement missing")
    elif bad_peer:
        if retired[-1][14]<=retired[0][14] or retired[-1][15]<=retired[0][15]:
            raise ValueError("pending polling client evidence missing")
    elif (len(alive)<2 or any(alive[-1][i]<=alive[0][i] for i in (10,11,14,15))
            or alive[-1][7]+alive[-1][8]==0):
        raise ValueError("both console programs must progress before close")
    result = dict(transfer_prefix=common,program_bytes=[int(start[i]) for i in range(1,5)],
        roots=roots,firmware_pages=int(start[9]),task_image_pages=52,samples=samples,bad_peer_rejected=bad_peer,service_exit=152 if bad_peer else 0,
        client_exit=(163 if tracked else None) if bad_peer else 0,console_reaped_pages=13 if bad_peer and not tracked else 26,
        polling_peer_death_recovery=False,surviving_pair_verified=True,
        native_execution_requires_guest_binding=True,shell=False,iso_built=False,production_ready=False)
    if tracked:
        result.update(transport="PRPC1", stop_dispatches={str(k):v for k,v in stop_dispatches.items()},
            peer_death_termination=bad_peer, service_restart=False)
    return result


def validate_echo(sent: bytes, received: bytes, *, bad_peer: bool = False) -> dict:
    if type(sent) is not bytes or type(received) is not bytes: raise ValueError("byte capture required")
    prefix, application = console.split_output(received)
    if bad_peer:
        if sent or application: raise ValueError("wrong peer must not produce application traffic")
    elif not sent or len(sent)>512 or b"\x04" in sent or application!=sent:
        raise ValueError("exact host-input IPC echo missing")
    return dict(input_bytes=len(sent),output_bytes=len(received),exact_echo=not bad_peer,
        control_prefix_bytes=len(prefix),control_prefix_hex=prefix.hex(),application_output_bytes=len(application),
        console_output_is_not_kernel_evidence=True,production_ready=False)


def negative_controls(markers: list[str], *, bad_peer: bool = False, tracked: bool = False) -> int:
    validate = validate_tracked_markers if tracked else validate_markers
    validate(markers,bad_peer=bad_peer)
    copies = [markers[:i]+markers[i+1:] for i in range(len(markers)-1)]
    copies += [markers+[markers[-1]], markers+["POOLEOS:PANIC injected"]]
    for i in range(29,len(markers)):
        for field in ("production=0","kernel_root_restored=1","image_reaped=1","authority_revoked=1"):
            if field in markers[i]:
                candidate=markers.copy(); candidate[i]=candidate[i].replace(field,field[:-1]+str(1-int(field[-1])))
                copies.append(candidate)
    for candidate in copies:
        try: validate(candidate,bad_peer=bad_peer)
        except ValueError: continue
        raise ValueError("hostile four-task observation accepted")
    return len(copies)
