"""Independent marker checks for bounded PKUSER10 preemptive peer tasks."""
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
RESULT = re.compile(r"POOLEOS:KERNEL:USER-ROOT-RESULT PASS restored=(0x[0-9A-F]{16}) cr3_writes=([0-9]+) allocated_pages=([0-9]+) retained_acpi_pages=([0-9]+) released_pages=429 scrubbed_data_pages=198 ring3=1 production=0 terminal=halt")
PEERS = re.compile(r"POOLEOS:KERNEL:USER-PEERS PASS contract=PKUSER10 scheduler=PKSCHED1 round=([0-9]+) first=(exit|fault|cancel|limit|return) value=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) dispatches=([0-9]+) preempt0=([0-9]+) preempt1=([0-9]+) progress0=([0-9]+) progress1=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) survivor_after_stop=([0-9]+) cr3_writes=([0-9]+) return_vector=([0-9]+) survivor_exit=84 states_preserved=1 root_restored=1 released_pages=26 scrubbed_data_pages=12 cpl=3 production=0")


CALL = re.compile(r"POOLEOS:KERNEL:USER-CALL PASS contract=PKUSER7 abi=PSABI1 profile=development version=1 cr3=(0x[0-9A-F]{16}) calls=12 ok=3 version_denied=1 unknown=1 arguments=4 faults=3 read_faults=1 write_faults=2 cpl=3 entry=syscall return=iretq max_copy=256 input_atomic=1 output_prefix=1 completion_traps=1 msrs_cleared=1 if=0 production=0")
TASK = re.compile(r"POOLEOS:KERNEL:USER-TASK PASS contract=PKUSER8 slot=0 generation=([0-9]+) root=(0x[0-9A-F]{16}) reason=(exit|fault) value=([0-9]+) syscalls=([0-9]+) cpl=3 stale_denials=([01]) restart_denied=1 repeat_reap_denied=1 retained_free_denials=5 entry_quiesced=1 root_restored=1 released_pages=13 scrubbed_data_pages=6 production=0")


def validate_markers(markers: list[str]) -> dict:
    if len(markers) != 54:
        raise ValueError("PKUSER10 requires exactly 54 markers")
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
                                zip((PREPARED, ACTIVE, TIMER, ENTRY, PREEMPT, CALL, RESULT), [*markers[29:35],markers[53]])]
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
            ("fault",0,0),("fault",1,0),("fault",3,0),("fault",13,0))):
        row = PEERS.fullmatch(markers[39+index])
        if row is None:
            raise ValueError("PKUSER10 missing or malformed peer marker")
        roots = [int(row[i],16) for i in (4,5)]
        dispatches,p0,p1,progress0,progress1,ticks0,ticks1,after,writes = (int(row[i]) for i in range(6,15))
        cancel = int(index == 2)
        if (int(row[1]) != index or row[2] != reason or int(row[3]) != value
                or int(row[15]) != return_vector
                or roots[0] == roots[1] or any(r == original or r == 0 or r & 4095 or r >= 1<<32 for r in roots)
                or p0 < 1 or p1 < 2 or not 1 <= after <= p1 or (cancel and p0 != 3)
                or not 1 <= dispatches <= 64 or dispatches != p0+p1+2-cancel
                or writes != 2*dispatches+cancel
                or not all(0 < n < 1<<64 for n in (progress0,progress1,ticks0,ticks1))):
            raise ValueError("PKUSER10 peer isolation, schedule accounting, or survivor progress changed")
        peers.append(dict(round=index,first=reason,value=value,return_vector=return_vector,roots=roots,dispatches=dispatches,
            preemptions=[p0,p1],progress=[progress0,progress1],ticks=[ticks0,ticks1],
            survivor_after_stop=after,cr3_writes=writes))
    total_writes = 10 + sum(p["cr3_writes"] for p in peers)
    if int(result[2]) != total_writes:
        raise ValueError("PKUSER10 total root writes not conserved")
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
            "task_stale_denials": 3, "released_pages": 429, "scrubbed_data_pages": 198,
            "peer_scheduling": True, "peer_rounds": peers, "peer_survival_cases": 14,
            "invalid_return_terminations": 6, "additional_user_exception_terminations": 4,
            "observed_stack_access_vector": 13, "architectural_stack_fault_qualified": False,
            "new_native_exception_vectors": [0, 1, 3],
            "peer_preemptions": sum(sum(p["preemptions"]) for p in peers),
            "production_ready": False}


def negative_controls(markers: list[str]) -> int:
    """Mutate every field in each live marker, plus sequencing and selector."""
    validate_markers(markers)
    candidates = [markers[:-1], [*markers, markers[-1]],
                  [*markers[:29], markers[30], markers[29], *markers[31:]]]
    wrong = markers.copy()
    wrong[23] = wrong[23].replace("trap_scenario=23", "trap_scenario=0")
    candidates.append(wrong)
    for i in range(29, 54):
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
