"""PPROC1 strict native observations; parsing alone is not execution evidence."""
from __future__ import annotations
import re
from runtime import native_kernel_transfer as transfer

ROUND = re.compile(r"POOLEOS:KERNEL:PROCESS-ROUND PASS contract=PPROC1 generation=([12]) waiting=([01]) dispatches=([0-9]+) controller_calls=([0-9]+) survivor_calls=1025 survivor_after_stop=([0-9]+) ticks0=([0-9]+) ticks1=([0-9]+) ticks2=([0-9]+) cr3_writes=([0-9]+) root0=(0x[0-9A-F]{16}) root1=(0x[0-9A-F]{16}) root2=(0x[0-9A-F]{16}) forged_denied=1 rights_denied=1 permit_invalidated=1 cancelled=1 retirement_flushes=1 released_pages=39 scrubbed_data_pages=18 cpl=3 production=0")
RESULT = "POOLEOS:KERNEL:PROCESS-RESULT PASS contract=PPROC1 rounds=2 cancelled=2 controller_exit=104 survivor_exit=100 released_pages=78 scrubbed_data_pages=36 objects_remaining=0 cpl=3 production=0 terminal=halt"
COMPLETION = (RESULT+"\r\n").encode("ascii")

def validate_markers(markers: list[str]) -> dict:
    if len(markers)!=32 or markers[-1]!=RESULT:
        raise ValueError("process probe requires exact prefix, two rounds and terminal")
    arm=transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10))!=23:
        raise ValueError("requires development selector23")
    prefix=markers[:29]
    prefix[23]=re.sub(r"trap_scenario=[0-9]+","trap_scenario=0",prefix[23],count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common=transfer.validate_markers(prefix)
    common["transfer_arm"]["trap_scenario"]=23
    common.pop("kernel_terminal",None)
    common["synthetic_unsigned_terminal_used_for_prefix_parser_only"]=True
    rounds=[]
    for generation,marker in enumerate(markers[29:31],1):
        m=ROUND.fullmatch(marker)
        if m is None: raise ValueError("invalid process round")
        g,w,d,c,a,t0,t1,t2,writes=map(int,m.groups()[:9])
        roots=[int(v,16) for v in m.groups()[9:]]
        if (g!=generation or w!=generation-1 or not 3<d<=256 or not 6<=c<=64*d
                or not 2<=a<d or min(t0,t1,t2)<=0 or max(t0,t1,t2)>=1<<64 or writes!=d*2+1
                or len(set(roots))!=3 or any(r==0 or r&4095 or r>=1<<32 or r==common["transfer_arm"]["root"] for r in roots)):
            raise ValueError("invalid process accounting, identity or survival")
        rounds.append(dict(generation=g,waiting=bool(w),dispatches=d,controller_calls=c,
                           survivor_after_stop=a,ticks=[t0,t1,t2],cr3_writes=writes,roots=roots))
    return dict(transfer_prefix=common,rounds=rounds,native_execution_requires_guest_binding=True,
                iso_built=False,production_ready=False)

def negative_controls(markers: list[str]) -> int:
    validate_markers(markers)
    cases=[markers[:i]+markers[i+1:] for i in range(len(markers))]
    cases+=[markers+[markers[-1]],markers[:29]+[markers[30],markers[29],markers[31]]]
    for i in range(29,32):
        for m in re.finditer(r"(?<==)(?:0x[0-9A-F]+|[0-9]+)(?= |$)",markers[i]):
            candidate=markers.copy()
            candidate[i]=markers[i][:m.start()]+("0" if m.group()!="0" else "1")+markers[i][m.end():]
            cases.append(candidate)
    for case in cases:
        try: validate_markers(case)
        except ValueError: continue
        raise ValueError("hostile process observation accepted")
    return len(cases)
