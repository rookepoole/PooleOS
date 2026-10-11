"""PSESSION5: native six-root capacity observations, not a shell or application set."""
from __future__ import annotations
import re
from runtime import native_console_ipc as ipc, native_session as session, native_kernel_transfer as transfer

START = re.compile(ipc.TRACKED_START.pattern.replace("PSESSION4 programs=4", "PSESSION5 programs=6")
    .replace(" task_image_pages=52", r" root4=(0x[0-9A-F]{16}) root5=(0x[0-9A-F]{16}) task_image_pages=78")
    .replace("granted_handles=9", "granted_handles=13")
    .replace("transport=PRPC1 ", "transport=PRPC1 capacity=PCAP8 "))
RUN = re.compile(ipc.RUN.pattern.replace(" cpl=3", r" calls4=([0-9]+) ticks4=([0-9]+) worker0_dead=([01]) calls5=([0-9]+) ticks5=([0-9]+) worker1_dead=([01]) cpl=3"))


def validate_markers(markers: list[str], *, bad_worker: bool = False) -> dict:
    if len(markers) < 40:
        raise ValueError("six-task observation interval missing")
    arm = transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm[10]) != 23:
        raise ValueError("selector23 required")
    prefix = markers[:29]
    prefix[23] = re.sub(r"trap_scenario=[0-9]+", "trap_scenario=0", prefix[23], count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common = transfer.validate_markers(prefix)
    common["transfer_arm"]["trap_scenario"] = 23
    common.pop("kernel_terminal", None)
    common["synthetic_unsigned_terminal_used_for_prefix_parser_only"] = True
    start = START.fullmatch(markers[29])
    if start is None or any(not 0 < int(start[i]) <= 4096 for i in range(1, 5)):
        raise ValueError("six-root program identity missing")
    roots = [int(start[i], 16) for i in range(5, 11)]
    if (len(set(roots)) != 6 or not 0 < int(start[11]) <= 12
            or any(r == common["transfer_arm"]["root"] or not 0 < r < 1 << 32 or r & 4095 for r in roots)):
        raise ValueError("six private roots and bounded firmware required")
    expected = {session.STOP.format(task=2, code=0): 2, session.STOP.format(task=3, code=0): 3}
    if bad_worker:
        expected.update({session.STOP.format(task=5, code=120): 5, session.STOP.format(task=4, code=111): 4})
    stops, frozen, samples, console_alive, retired = {}, {}, [], [], []
    for marker in markers[30:]:
        event = ipc.TRACKED_STOP.fullmatch(marker)
        if event is not None and event[1] in expected:
            task, at = expected[event[1]], int(event[2])
            previous = samples[-1][0] if samples else 0
            if task in stops or not previous < at <= previous + 64 or at <= max(stops.values(), default=0):
                raise ValueError("duplicate or unordered retirement")
            stops[task] = at
            continue
        match = RUN.fullmatch(marker)
        if match is None:
            raise ValueError("unknown capacity event")
        v = tuple(map(int, match.groups()))
        d,c0,c1,t0,t1,waits,wakes,preempt,yields,writes,c2,t2,dead2,pages,c3,t3,dead3,c4,t4,dead4,c5,t5,dead5 = v
        if (any(x >= 1 << 64 for x in v) or d != (len(samples) + 1) * 64
                or writes != 2*d or d != waits + preempt + yields + len(stops)
                or not 0 < wakes <= waits or waits-wakes > 4 or abs(c0-c1) > 16
                or min(c0,c1,t0,t1,c2,t2,c3,t3,c4,t4,c5,t5) <= 0
                or (dead2,dead3,dead4,dead5) != tuple(int(i in stops) for i in (2,3,4,5))
                or pages != 78 - 13*len(stops)):
            raise ValueError("capacity accounting/ownership differs")
        if samples:
            progress = (0,1,2,3,4) if bad_worker else (0,1,2,3,4,17,18,20,21)
            if any(v[i] <= samples[-1][i] for i in progress):
                raise ValueError("independent pair ceased progress")
            if any(v[i] < samples[-1][i] for i in (5,6,7,8,9,10,11,14,15,17,18,20,21)):
                raise ValueError("cumulative accounting regressed")
        if not bad_worker and abs(c4-c5) > 16:
            raise ValueError("extra pair exchange diverged")
        for task, pair in ((2,(c2,t2)), (3,(c3,t3)), (4,(c4,t4)), (5,(c5,t5))):
            if task in stops and pair != frozen.setdefault(task, pair):
                raise ValueError("retired process resumed")
        if 2 not in stops and 3 not in stops:
            console_alive.append(v)
        if set(stops) == set(expected.values()):
            retired.append(v)
        samples.append(v)
    if set(stops) != set(expected.values()) or len(retired) < 2 or samples[-1][0] < 512:
        raise ValueError("cleanup/survivor interval missing")
    if len(console_alive) < 2 or any(console_alive[-1][i] <= console_alive[0][i] for i in (10,11,14,15)):
        raise ValueError("console must work while workers run or fail")
    if bad_worker and (not 0 < stops[4]-stops[5] <= 8 or max(stops[4], stops[5]) > 64):
        raise ValueError("worker dependency retirement is not bounded")
    return dict(transfer_prefix=common, program_bytes=[int(start[i]) for i in range(1,5)],
        roots=roots, firmware_pages=int(start[11]), task_image_pages=78, capacity="PCAP8",
        samples=samples, stop_dispatches={str(k): v for k,v in stops.items()},
        worker_startup_rejected=bad_worker, extra_pair_survives=not bad_worker,
        released_pages=52 if bad_worker else 26, surviving_pair_verified=True,
        transport="PRPC1", native_execution_requires_guest_binding=True,
        fixed_bootstrap_only=True, user_lifecycle_authority=False, service_restart=False,
        useful_application_count=0, shell=False, iso_built=False, production_ready=False)


def negative_controls(markers: list[str], *, bad_worker: bool = False) -> int:
    validate_markers(markers, bad_worker=bad_worker)
    candidates = [markers[:i] + markers[i+1:] for i in range(len(markers)-1)]
    candidates += [markers+[markers[-1]], markers+["POOLEOS:PANIC injected"]]
    for i in range(30, len(markers)):
        for field in ("console_dead=0", "console_dead=1", "client_dead=0", "client_dead=1",
                      "worker0_dead=0", "worker0_dead=1", "worker1_dead=0", "worker1_dead=1"):
            if field in markers[i]:
                copy = markers.copy()
                copy[i] = copy[i].replace(field, field[:-1]+str(1-int(field[-1])))
                candidates.append(copy)
    for candidate in candidates:
        try:
            validate_markers(candidate, bad_worker=bad_worker)
        except ValueError:
            continue
        raise ValueError("hostile six-task observation accepted")
    return len(candidates)
