"""Independent marker checks for bounded PKUSER15 unmeasured-dispatch recovery."""
from __future__ import annotations

import re
from runtime import native_kernel_transfer as transfer

FEATURE = "development-user-root"
CLOCK = re.compile(r"POOLEOS:KERNEL:USER-CLOCK PASS contract=PKCLOCK1 origin=([0-9]+) last=([0-9]+) period_fs=([0-9]+) elapsed_ns=([0-9]+) samples=([0-9]+) idle_ns=([0-9]+) enters=12 leaves=12 idle_intervals=4 config_restored=1 counter_reset=0 mmio_writes=24 mapping_windows=6 mapping_revoked=6 guards=3 clock=hpet64 scope=one_bsp timed_ipc=0 production=0")
REQUEST = re.compile(r"POOLEOS:KERNEL:USER-IPC-REQUEST PASS contract=PKIPC4 round=([0-9]+) generation=([0-9]+) outcome=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) preemptions=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) calls0=([0-9]+) calls1=([0-9]+) waits=1 wakes=1 cr3_writes=([0-9]+) client_cancel=1 stale_token=0 take_once=1 survivor_query=1 client_exit=97 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
REPLY = re.compile(r"POOLEOS:KERNEL:USER-IPC-REPLY PASS contract=PKIPC3 generation=6 endpoints=2 handles=3 sender_client=2 sender_server=3 reply_generations=2 reply_consumed=1 reply_discarded=1 replay_denied=2 unminted_denied=1 cross_owner_denied=1 wrong_type_denied=1 request_rights_denied=1 output_prefix=8 input_fault=1 transformed=1 root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) preemptions=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) calls0=8 calls1=11 waits=1 wakes=1 cr3_writes=([0-9]+) client_exit=95 server_exit=94 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
PRESSURE = re.compile(r"POOLEOS:KERNEL:USER-IPC-PRESSURE PASS contract=PKIPC2 round=([0-9]+) generation=([0-9]+) owner=(exit|fault|cancel|wait_cancel|quarantine) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) preemptions=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) calls0=([0-9]+) calls1=([0-9]+) waits=([0-9]+) wakes=([0-9]+) revoked=([0-9]+) cr3_writes=([0-9]+) full_denied=1 stale_denied=1 partial_output=([0-9]+) survivor_exit=93 persistent_slots=1 automatic_retirement=1 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
IPC = re.compile(r"POOLEOS:KERNEL:USER-IPC PASS contract=PKIPC1 abi=PSABI1 endpoints=2 handles=4 max_bytes=64 depth=4 request_bytes=8 reply_bytes=8 transformed=1 forged_denied=1 rights_denied=1 oversize_denied=1 copy_fault_denied=1 root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) preemptions=([0-9]+) ticks=([0-9]+) calls0=([0-9]+) calls1=([0-9]+) cr3_writes=([0-9]+) waits=3 wakes=2 cancellations=1 client_exit=91 server_exit=90 owners_detached=2 objects_remaining=0 released_pages=26 scrubbed_data_pages=12 cpl=3 blocking=1 automatic_retirement=1 saved_state=1 production=0")
UNKNOWN = re.compile(r"POOLEOS:KERNEL:USER-UNKNOWN PASS contract=PKUSER15 injection=returned_sample_loss unmeasured=1 measured0=0 total0=unknown pending=0 duplicate_denied=1 stale_denied=1 cpu_denied=1 zero_charge_denied=1 requeue_denied=1 outcome_denied=1 cleanup_retry=1 retained_pages=13 free_denials=5 root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) peer_preemptions=([0-9]+) peer_progress=([0-9]+) peer_ticks=([0-9]+) cr3_writes=([0-9]+) peer_exit=84 scheduler_match=1 retired_unknown=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")
WATCHDOG = re.compile(r"POOLEOS:KERNEL:USER-WATCHDOG PASS contract=PKUSER14 source=hpet_msi local_masked=1 recoveries=1 arms=([0-9]+) stops=([0-9]+) restores=([0-9]+) ticks=([0-9]+) deadline_ns=50000000 peer_exit=84 shared_apic=1 requires_if=1 nmi=0 production=0")
RUNTIME = re.compile(r"POOLEOS:KERNEL:USER-RUNTIME PASS contract=PKUSER13 samples=([0-9]+) terminal_samples=([0-9]+) duplicate_denials=([0-9]+) ticks=([0-9]+) preempt_ticks=([0-9]+) terminal_ticks=([0-9]+) failed_cleanup_ticks=([0-9]+) failed_cleanup_samples=1 scheduler_match=1 pending=0 unknown=0 clock=hpet charge_window=arm_to_event production=0")
SPAWN = re.compile(r"POOLEOS:KERNEL:USER-SPAWN PASS contract=PKUSER11 quota_failures=1 quota_released_pages=5 quota_scrubbed_pages=5 after_effect_failures=6 cleanup_quarantines=6 cleanup_retries=6 retained_free_denials=30 released_pages=83 scrubbed_pages=83 peer_resumed=1 peer_exit=84 cpu_exposures=0 production=0")
DRAIN = re.compile(r"POOLEOS:KERNEL:USER-TIMER-DRAIN PASS contract=PKUSER12 pending=1 late=1 quarantines=1 retries=1 retained_pages=13 free_denials=5 restart_denials=2 reap_denials=1 peer_exit=84 deliveries=([0-9]+) eois=([0-9]+) empty_irr_isr=1 kernel_window=1 detached_after_shutdown=1 if=0 production=0")
SELECTOR = 23
COMPLETION = b"POOLEOS:KERNEL:USER-ROOT-RESULT PASS"
PREPARED = re.compile(r"POOLEOS:KERNEL:USER-ROOT-PREPARED PASS contract=PKUSER3 original=(0x[0-9A-F]{16}) candidate=(0x[0-9A-F]{16}) generation=([0-9]+) pages=13 allocations=5 retained_free_denials=5 temporary_aliases=0 ring3=0")
ACTIVE = re.compile(r"POOLEOS:KERNEL:USER-ROOT-ACTIVE PASS cr3=(0x[0-9A-F]{16}) stack_probe=(0x[0-9A-F]{16}) cpl=0 if=0 ring3=0")
TIMER = re.compile(r"POOLEOS:KERNEL:USER-ROOT-TIMER PASS contract=PKUSER4 cr3=(0x[0-9A-F]{16}) deliveries=3 eois=3 mmio_pages=2 quiesced=1 if=0 ring3=0")
ENTRY = re.compile(r"POOLEOS:KERNEL:USER-ENTRY PASS contract=PKUSER5 cr3=(0x[0-9A-F]{16}) cpl=3 traps=7 private_rsp0=1 gpr_zero=15 fp_cleared=1 cli_denied=1 io_denied=1 syscall_denied=1 supervisor_fault=1 nx_fault=1 kernel_return=1 descriptors_detached=1 if=0 production=0")
PREEMPT = re.compile(r"POOLEOS:KERNEL:USER-PREEMPT PASS contract=PKUSER6 cr3=(0x[0-9A-F]{16}) cpl=3 deliveries=3 eois=3 resumes=2 first_progress=([0-9]+) last_progress=([0-9]+) private_rsp0=1 gpr_preserved=14 fp_preserved=1 timer_quiesced=1 forced_return=1 if=0 production=0")
RESULT = re.compile(r"POOLEOS:KERNEL:USER-ROOT-RESULT PASS restored=(0x[0-9A-F]{16}) cr3_writes=([0-9]+) allocated_pages=([0-9]+) retained_acpi_pages=([0-9]+) released_pages=876 scrubbed_data_pages=403 ring3=1 production=0 terminal=halt")
PEERS = re.compile(r"POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER10 scheduler=PKSCHED1 round=([0-9]+) first=(exit|fault|cancel|limit|return|quarantine|watchdog) value=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) preempt0=([0-9]+) preempt1=([0-9]+) progress0=([0-9]+) progress1=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) survivor_after_stop=([0-9]+) cr3_writes=([0-9]+) return_vector=([0-9]+) survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")


CALL = re.compile(r"POOLEOS:KERNEL:USER-CALL PASS contract=PKUSER7 abi=PSABI1 profile=development version=1 cr3=(0x[0-9A-F]{16}) calls=12 ok=3 version_denied=1 unknown=1 arguments=4 faults=3 read_faults=1 write_faults=2 cpl=3 entry=syscall return=iretq max_copy=256 input_atomic=1 output_prefix=1 completion_traps=1 msrs_cleared=1 if=0 production=0")
TASK = re.compile(r"POOLEOS:KERNEL:USER-TASK PASS contract=PKUSER8 slot=0 generation=([0-9]+) root=(0x[0-9A-F]{16}) reason=(exit|fault) value=([0-9]+) syscalls=([0-9]+) cpl=3 stale_denials=([01]) restart_denied=1 repeat_reap_denied=1 retained_free_denials=5 entry_quiesced=1 root_restored=1 released_pages=13 scrubbed_data_pages=6 production=0")


def validate_markers(markers: list[str]) -> dict:
    if len(markers) != 73 or SPAWN.fullmatch(markers[55]) is None:
        raise ValueError("PKCLOCK1 requires exactly 73 markers and transactional rollback")
    drain = DRAIN.fullmatch(markers[56])
    if drain is None or not 3 <= int(drain[1]) == int(drain[2]) <= 256:
        raise ValueError("PKUSER12 missing or inconsistent timer shutdown proof")
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
    prepared, active, timer, entry, preempt, call, result = [pattern.fullmatch(marker) for pattern, marker in
                                zip((PREPARED, ACTIVE, TIMER, ENTRY, PREEMPT, CALL, RESULT), [*markers[29:35],markers[72]])]
    if any(m is None for m in (prepared, active, timer, entry, preempt, call, result)):
        raise ValueError("PKUSER7 marker layout or bounded claims changed")
    original, candidate = (int(prepared[i], 16) for i in (1, 2))
    generation = int(prepared[3])
    probe = int(active[2], 16)
    if (original != common["transfer_arm"]["root"] or original == candidate
            or candidate == 0 or candidate & 4095 or candidate >= (1 << 32)
            or generation == 0 or generation >= (1 << 64)
            or int(active[1], 16) != candidate or int(timer[1], 16) != candidate or int(entry[1], 16) != candidate
            or int(preempt[1], 16) != candidate or not (0 < int(preempt[2]) < int(preempt[3]) < (1 << 64))
            or int(call[1], 16) != candidate
            or int(result[1], 16) != original
            or not (0 < int(result[3]) == int(result[4]) <= 19)
            or probe != candidate ^ generation ^ 0x504B555345523300):
        raise ValueError("PKUSER3 live root/probe/restoration binding changed")
    tasks = []
    for index,(reason,value,calls) in enumerate((("exit",42,2),("fault",6,0),("fault",13,0),("fault",14,0))):
        row = TASK.fullmatch(markers[35+index])
        if row is None:
            raise ValueError("PKUSER8 missing or malformed termination marker")
        gen,root = int(row[1]),int(row[2],16)
        if (gen != index+1 or root==0 or root&4095 or root>=1<<32 or root==original
                or row[3]!=reason or int(row[4])!=value or int(row[5])!=calls or int(row[6])!=int(index>0)):
            raise ValueError("PKUSER8 task identity, termination, or lifecycle binding changed")
        tasks.append(dict(slot=0,generation=gen,root=root,reason=reason,value=value,syscalls=calls))
    peers = []
    for index, (reason, value, return_vector) in enumerate((("exit",42,0),("fault",6,0),("cancel",0,0),("limit",64,0),
            ("return",2,256),("return",2,256),("return",3,256),("return",3,256),("return",1,256),("return",2,64),
            ("fault",0,0),("fault",1,0),("fault",3,0),("fault",13,0),("quarantine",0,0),("watchdog",65,0))):
        row = PEERS.fullmatch(markers[39+index])
        if row is None:
            raise ValueError("PKUSER10 missing or malformed peer marker")
        roots = [int(row[i],16) for i in (4,5)]
        dispatches,p0,p1,progress0,progress1,ticks0,ticks1,after,writes = (int(row[i]) for i in range(6,15))
        cancel = int(index == 2)
        if (int(row[1]) != index or row[2] != reason or int(row[3]) != value
                or int(row[15]) != return_vector
                or roots[0] == roots[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in roots)
                or (index < 14 and p0 < 1) or p1 < 2 or not 1 <= after <= p1 or (cancel and p0 != 3)
                or (index >= 14 and (p0 != 0 or progress0 != 0 or ticks0 <= 0 or after != p1))
                or not 1 <= dispatches <= 64 or dispatches != p0+p1+2-cancel
                or writes != 2*dispatches+cancel
                or not all(0 < n < 1<<64 for n in ((progress1,ticks0,ticks1) if index >= 14 else (progress0,progress1,ticks0,ticks1)))):
            raise ValueError("PKUSER10 peer isolation, schedule accounting, or survivor progress changed")
        peers.append(dict(round=index,first=reason,value=value,return_vector=return_vector,roots=roots,dispatches=dispatches,
            preemptions=[p0,p1],progress=[progress0,progress1],ticks=[ticks0,ticks1],
            survivor_after_stop=after,cr3_writes=writes))
    unknown = UNKNOWN.fullmatch(markers[59])
    if unknown is None:
        raise ValueError("PKUSER15 missing explicit unknown accounting and recovery evidence")
    roots = [int(unknown[i],16) for i in (1,2)]
    unknown_dispatches, unknown_preempts, unknown_progress, unknown_peer_ticks, unknown_writes = (
        int(unknown[i]) for i in range(3,8))
    if (roots[0] == roots[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in roots)
            or not 4 <= unknown_dispatches <= 65 or unknown_dispatches != unknown_preempts + 2
            or unknown_writes != 2 * unknown_dispatches
            or not all(0 < n < 1<<64 for n in (unknown_progress, unknown_peer_ticks))):
        raise ValueError("PKUSER15 peer progress, identity, or root-write conservation changed")
    ipc = IPC.fullmatch(markers[60])
    if ipc is None:
        raise ValueError("PKIPC1 missing native request/reply evidence")
    ipc_roots = [int(ipc[i], 16) for i in (1, 2)]
    ipc_dispatches, ipc_preempts, ipc_ticks, calls0, calls1, ipc_writes = (int(ipc[i]) for i in range(3, 9))
    if (ipc_roots[0] == ipc_roots[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in ipc_roots)
            or not 5 <= ipc_dispatches <= 64 or ipc_dispatches != ipc_preempts + 5
            or not 0 < ipc_ticks < 1<<64 or calls0 != 9 or calls1 != 4
            or ipc_writes != 2 * ipc_dispatches):
        raise ValueError("PKIPC1 root, syscall or scheduler conservation changed")
    pressure = []
    for index, owner in enumerate(("exit", "fault", "cancel", "wait_cancel", "quarantine")):
        row = PRESSURE.fullmatch(markers[61 + index])
        if row is None:
            raise ValueError("PKIPC2 missing pressure or enrolled-owner retirement evidence")
        proots = [int(row[i], 16) for i in (4, 5)]
        dispatches, preempts, ticks0, ticks1, client_calls, server_calls, waits, wakes, revoked, writes, prefix = (int(row[i]) for i in range(6, 17))
        cancelled = int(index in (2, 3))
        expected_waits = 3 if index == 0 else 2 if index == 3 else 1
        if (int(row[1]) != index or int(row[2]) != index + 1 or row[3] != owner
                or proots[0] == proots[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in proots)
                or not 3 <= dispatches <= 64 or dispatches != preempts + waits + 2 - cancelled
                or (index == 2 and preempts < 1) or not all(0 < t < 1<<64 for t in (ticks0, ticks1))
                or (client_calls, server_calls) != ((12, 11) if index == 0 else (13, int(index == 3)))
                or waits != expected_waits or wakes != (3 if index == 0 else 1)
                or revoked != int(index > 0) or writes != dispatches * 2 + cancelled
                or prefix != (4 if index == 0 else 0)):
            raise ValueError("PKIPC2 generation, survivor, copy or accounting conservation changed")
        pressure.append(dict(round=index, generation=index+1, owner=owner, roots=proots,
            dispatches=dispatches, preemptions=preempts, ticks=[ticks0,ticks1], calls=[client_calls,server_calls],
            waits=waits, wakes=wakes, revoked=revoked, cr3_writes=writes, output_prefix=prefix))
    reply = REPLY.fullmatch(markers[66])
    if reply is None:
        raise ValueError("PKIPC3 missing sender and one-use reply evidence")
    reply_roots = [int(reply[i], 16) for i in (1, 2)]
    reply_dispatches, reply_preempts, reply_ticks0, reply_ticks1, reply_writes = (int(reply[i]) for i in range(3, 8))
    if (reply_roots[0] == reply_roots[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in reply_roots)
            or not 3 <= reply_dispatches <= 64 or reply_dispatches != reply_preempts + 3
            or reply_writes != 2 * reply_dispatches or not all(0 < t < 1<<64 for t in (reply_ticks0, reply_ticks1))):
        raise ValueError("PKIPC3 roots, dispatch or accounting conservation changed")
    total_writes = 10 + sum(p["cr3_writes"] for p in peers) + unknown_writes + ipc_writes + sum(p["cr3_writes"] for p in pressure) + reply_writes
    requests = []
    for index in range(4):
        request = REQUEST.fullmatch(markers[67 + index])
        if request is None:
            raise ValueError("PKIPC4 missing caller-owned request completion")
        round_, generation_, outcome = (int(request[i]) for i in range(1, 4))
        roots_ = [int(request[i], 16) for i in (4, 5)]
        dispatches_, preempts_, t0, t1, c0, c1, writes_ = (int(request[i]) for i in range(6, 13))
        if (round_ != index or generation_ != index + 7 or outcome != (0, 8, 9, 9)[index]
                or roots_[0] == roots_[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in roots_)
                or not 3 <= dispatches_ <= 64 or dispatches_ != preempts_ + 3 or writes_ != 2 * dispatches_
                or not all(0 < t < 1<<64 for t in (t0, t1))
                or (c0, c1) != ((11, 5), (10, 5), (10, 0), (10, 2))[index]):
            raise ValueError("PKIPC4 completion, generation or accounting conservation changed")
        requests.append(dict(round=index, generation=generation_, outcome=outcome, roots=roots_,
            dispatches=dispatches_, preemptions=preempts_, ticks=[t0, t1], calls=[c0, c1], cr3_writes=writes_))
        total_writes += writes_
    clock = CLOCK.fullmatch(markers[71])
    if clock is None:
        raise ValueError("PKCLOCK1 missing continuous owner and teardown proof")
    origin, last, period, elapsed, clock_samples, idle_ns = map(int, clock.groups())
    if (not 0 <= origin < last < 1 << 64 or not 100_000 <= period <= 100_000_000
            or not 0 < elapsed < 1 << 64 or elapsed != (last - origin) * period // 1_000_000
            or not 4_000_000 <= idle_ns <= elapsed or not 33 <= clock_samples <= 8_000_029
            or sum(r["dispatches"] for r in requests) != 12):
        raise ValueError("PKCLOCK1 raw counter, idle progress or child conservation changed")
    if int(result[2]) != total_writes:
        raise ValueError("PKUSER10 total root writes not conserved")
    charge = RUNTIME.fullmatch(markers[57])
    if charge is None:
        raise ValueError("PKUSER13 missing runtime settlement evidence")
    samples, terminal_samples, duplicates, total, preempt_ticks, terminal_ticks, failed_ticks = map(int, charge.groups())
    preemptions = sum(sum(p["preemptions"]) for p in peers)
    if (samples != sum(p["dispatches"] for p in peers) or duplicates != samples
            or terminal_samples != samples - preemptions - 1 or terminal_samples != 30
            or total != sum(sum(p["ticks"]) for p in peers)
            or failed_ticks != peers[14]["ticks"][0]
            or total != preempt_ticks + terminal_ticks + failed_ticks
            or not all(0 < n < 1<<64 for n in (total,preempt_ticks,terminal_ticks,failed_ticks))):
        raise ValueError("PKUSER13 lost, duplicated or inconsistent runtime charge")
    watchdog = WATCHDOG.fullmatch(markers[58])
    if watchdog is None:
        raise ValueError("PKUSER14 missing HPET backup proof")
    arms, stops, restores, watchdog_ticks = map(int, watchdog.groups())
    if arms != samples or stops != samples or restores != samples or watchdog_ticks != peers[15]["ticks"][0]:
        raise ValueError("PKUSER14 ownership or recovered runtime not conserved")
    return {"transfer_prefix": common, "original_root": original, "candidate_root": candidate,
            "generation": generation, "stack_probe": probe, "root_probe_cpl": 0, "cpl": 3,
            "cr3_writes": total_writes, "timer_deliveries": 3, "timer_eois": 3,
            "timer_quiesced": True, "retained_acpi_pages": int(result[4]),
            "ring3_executed": True, "user_traps": 7, "private_rsp0": True,
            "user_timer_preemption": True, "user_timer_deliveries": 3, "user_timer_eois": 3,
            "user_resumes": 2, "first_progress": int(preempt[2]), "last_progress": int(preempt[3]),
            "syscall_abi": "PSABI1_development", "user_calls": 12, "copy_faults": 3,
            "copy_read_faults": 1, "copy_write_faults": 2, "syscall_msrs_cleared": True,
            "terminated_tasks": tasks, "normal_exits": 1, "fault_terminations": 3,
            "task_stale_denials": 3, "released_pages": 876, "scrubbed_data_pages": 403,
            "ipc_request_lifetimes": requests, "ipc_caller_owned_completion": True,
            "ipc_request_cancellation": True, "ipc_dead_service_notification": True,
            "continuous_clock": {"origin": origin, "last": last, "period_fs": period,
                "elapsed_ns": elapsed, "samples": clock_samples, "idle_ns": idle_ns,
                "child_enters": 12, "child_leaves": 12, "idle_intervals": 4,
                "config_restored": True, "counter_reset": False, "mmio_writes": 24,
                "mapping_windows": 6, "mapping_revoked": 6},
            "native_continuous_clock": True, "clock_scope": "one_bsp_hpet64",
            "ipc_authenticated_sender": True, "ipc_one_use_replies": True,
            "ipc_reply_roots": reply_roots, "ipc_reply_dispatches": reply_dispatches,
            "ipc_reply_preemptions": reply_preempts, "ipc_reply_ticks": [reply_ticks0, reply_ticks1],
            "ipc_reply_cr3_writes": reply_writes, "ipc_reply_calls": [8, 11],
            "ipc_reply_task_generation": 6, "ipc_reply_token_generations": 2,
            "ipc_reply_consumed": 1, "ipc_reply_discarded": 1, "ipc_reply_output_prefix": 8,
            "ipc_synchronous_call": False, "ipc_deadlines": False,
            "ipc_pressure_rounds": pressure, "ipc_persistent_generations": 5,
            "ipc_native_dead_owner_cases": 4, "ipc_native_output_fault_prefix": 4,
            "ipc_native_writable_wait": True, "ipc_native_wait_termination": True,
            "bounded_capability_ipc": True, "ipc_roots": ipc_roots, "ipc_dispatches": ipc_dispatches,
            "ipc_preemptions": ipc_preempts, "ipc_ticks": ipc_ticks, "ipc_calls": [calls0, calls1],
            "ipc_cr3_writes": ipc_writes, "ipc_blocking": True, "ipc_general_lifecycle": False,
            "ipc_waits": 3, "ipc_readiness_wakes": 2, "ipc_cancellations": 1,
            "ipc_automatic_retirement": True, "ipc_saved_state_preserved": True,
            "peer_scheduling": True, "peer_rounds": peers, "peer_survival_cases": 17,
            "unknown_runtime_recovery": True, "unmeasured_dispatches": 1,
            "unknown_task_total_ticks": None, "unknown_task_measured_ticks": 0,
            "unknown_recovery_roots": roots, "unknown_recovery_dispatches": unknown_dispatches,
            "unknown_peer_preemptions": unknown_preempts, "unknown_peer_progress": unknown_progress,
            "unknown_peer_ticks": unknown_peer_ticks, "unknown_recovery_cr3_writes": unknown_writes,
            "complete_runtime_tick_accounting": False, "physical_clock_failure_recovery": False,
            "invalid_return_terminations": 6, "additional_user_exception_terminations": 4,
            "observed_stack_access_vector": 13, "architectural_stack_fault_qualified": False,
            "new_native_exception_vectors": [0, 1, 3],
            "spawn_quota_failures": 1, "spawn_quota_released_pages": 5, "spawn_after_effect_failures": 6, "spawn_cleanup_quarantines": 6,
            "spawn_cleanup_retries": 6, "spawn_released_pages": 83,
            "spawn_scrubbed_pages": 83, "spawn_peer_continuation": True,
            "timer_drain_deliveries": int(drain[1]), "timer_drain_eois": int(drain[2]),
            "timer_pending_cases": 1, "timer_late_cases": 1, "timer_quarantine_retries": 1,
            "timer_quarantine_retained_pages": 13, "timer_quarantine_peer_survived": True,
            "peer_preemptions": sum(sum(p["preemptions"]) for p in peers),
            "runtime_samples": samples, "runtime_terminal_samples": terminal_samples,
            "runtime_duplicate_denials": duplicates, "runtime_ticks": total,
            "runtime_preempt_ticks": preempt_ticks, "runtime_terminal_ticks": terminal_ticks,
            "runtime_failed_cleanup_ticks": failed_ticks, "runtime_failed_cleanup_samples": 1,
            "bounded_runtime_accounting": True, "pure_user_instruction_time": False,
            "bounded_hpet_backup_recovery": True, "watchdog_recoveries": 1,
            "watchdog_arms": arms, "watchdog_stops": stops, "watchdog_restores": restores,
            "watchdog_ticks": watchdog_ticks, "watchdog_shared_apic": True,
            "independent_missing_interrupt_watchdog": False, "nmi_recovery": False,
            "production_ready": False}


def negative_controls(markers: list[str]) -> int:
    """Mutate every field in each live marker, plus sequencing and selector."""
    validate_markers(markers)
    candidates = [markers[:-1], [*markers, markers[-1]],
                  [*markers[:29], markers[30], markers[29], *markers[31:]]]
    wrong = markers.copy()
    wrong[23] = wrong[23].replace("trap_scenario=23", "trap_scenario=0")
    candidates.append(wrong)
    for i in range(29, 73):
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
