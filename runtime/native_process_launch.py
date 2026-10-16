"""PLAUNCH1 exact ordered observations; native execution needs external binding."""
from __future__ import annotations
import re
from runtime import native_kernel_transfer as transfer

END="POOLEOS:KERNEL:LAUNCH-END PASS contract=PLAUNCH1 cpl=3 production=0 terminal=halt"
COMPLETION=(END+"\r\n").encode("ascii")
FIELDS={
    "START":"bad_owner supervisor_bytes root0 root1 root2 image_pages firmware_pages",
    "ADMITTED":"sequence child_generation root handle owned_pages",
    "RETIRED":"sequence child_generation calls released_pages scrubbed_data_pages",
    "CANCELLED":"prepared calls released_pages scrubbed_data_pages",
    "RESULT":"launched retired prepared_cancelled supervisor_exit supervisor_calls child_calls survivor_calls survivor_after_restart ticks0 ticks1 ticks2 dispatches cr3_writes released_pages scrubbed_data_pages objects_remaining",
}
def parse(line:str,event:str)->dict:
    names=FIELDS[event].split()
    pattern="POOLEOS:KERNEL:LAUNCH-"+event+" PASS contract=PLAUNCH1"+"".join(" "+n+"=([0-9]+)" for n in names)
    m=re.fullmatch(pattern,line)
    if m is None: raise ValueError("invalid launch marker")
    values=list(map(int,m.groups()))
    if any(n>=1<<64 for n in values): raise ValueError("launch observation overflow")
    return dict(zip(names,values))

def validate_markers(markers:list[str],*,bad_owner:bool=False,supervisor_code_pages:int=1)->dict:
    if type(supervisor_code_pages) is not int or not 1<=supervisor_code_pages<=4:
        raise ValueError("supervisor page bound")
    image_pages=38+supervisor_code_pages
    if len(markers)!=(33 if bad_owner else 36) or markers[-1]!=END: raise ValueError("launch ordering/terminal")
    arm=transfer.TRANSFER_ARM.fullmatch(markers[23])
    if arm is None or int(arm.group(10))!=23: raise ValueError("launch selector")
    prefix=markers[:29]
    prefix[23]=re.sub(r"trap_scenario=[0-9]+","trap_scenario=0",prefix[23],count=1)
    prefix.append("POOLEOS:KERNEL:TRANSFER-DENIED PASS contract=PKXFER1 terminal=halt entry_count=1 post_exit_firmware_calls=0 signatures=0 authority=0 actions=0 writes=0")
    common=transfer.validate_markers(prefix);common["transfer_arm"]["trap_scenario"]=23
    common.pop("kernel_terminal",None);common["synthetic_unsigned_terminal_used_for_prefix_parser_only"]=True
    start=parse(markers[29],"START");roots=[start[f"root{i}"] for i in range(3)]
    def root_ok(r): return 0<r<1<<32 and r%4096==0 and r!=common["transfer_arm"]["root"]
    if start["bad_owner"]!=int(bad_owner) or not (supervisor_code_pages-1)*4096<start["supervisor_bytes"]<=supervisor_code_pages*4096 or start["image_pages"]!=image_pages or not 1<=start["firmware_pages"]<=12 or len(set(roots))!=3 or not all(root_ok(r) for r in roots): raise ValueError("launch startup bounds")
    lifetimes=[]
    if bad_owner:
        cancel=parse(markers[30],"CANCELLED")
        if cancel!=dict(prepared=1,calls=0,released_pages=13,scrubbed_data_pages=6): raise ValueError("prepared cleanup")
    else:
        for n in (1,2):
            admitted=parse(markers[29+2*n-1],"ADMITTED")
            retired=parse(markers[29+2*n],"RETIRED")
            if admitted["sequence"]!=n or admitted["child_generation"]!=n or admitted["handle"]!=(n<<32)|0x50001 or admitted["owned_pages"]!=13 or not root_ok(admitted["root"]) or admitted["root"] in roots[1:] or (n==1 and admitted["root"]!=roots[0]): raise ValueError("launch lifetime/authority")
            if retired!=dict(sequence=n,child_generation=n,calls=257,released_pages=13,scrubbed_data_pages=6): raise ValueError("child retirement")
            lifetimes.append(dict(admitted=admitted,retired=retired))
    result=parse(markers[-2],"RESULT")
    fixed=dict(launched=0 if bad_owner else 2,retired=0 if bad_owner else 2,prepared_cancelled=int(bad_owner),supervisor_exit=170 if bad_owner else 0,child_calls=0 if bad_owner else 514,survivor_calls=8193,released_pages=image_pages+(0 if bad_owner else 13),scrubbed_data_pages=image_pages-21+(0 if bad_owner else 6),objects_remaining=0)
    if any(result[k]!=v for k,v in fixed.items()): raise ValueError("launch cleanup/outcome")
    d=result["dispatches"]
    if not 129<d<=512 or result["cr3_writes"]!=2*d or not 2<=result["supervisor_calls"]<=64*d or result["ticks1"]==0 or result["ticks2"]==0: raise ValueError("launch accounting")
    if bad_owner:
        if result["survivor_after_restart"]!=0 or result["ticks0"]!=0 or result["supervisor_calls"]!=2: raise ValueError("denied launch executed")
    elif not 0<result["survivor_after_restart"]<d or result["ticks0"]==0 or result["supervisor_calls"]<7: raise ValueError("restart survival")
    return dict(transfer_prefix=common,start=start,lifetimes=lifetimes,result=result,bad_owner=bad_owner,native_execution_requires_guest_binding=True,iso_built=False,production_ready=False)

def negative_controls(markers:list[str],*,bad_owner:bool=False,supervisor_code_pages:int=1)->int:
    validate_markers(markers,bad_owner=bad_owner,supervisor_code_pages=supervisor_code_pages)
    cases=[markers[:i]+markers[i+1:] for i in range(len(markers))]+[markers+[markers[-1]],markers[:29]+list(reversed(markers[29:]))]
    for i in range(29,len(markers)):
        for m in re.finditer(r"(?<==)[0-9]+(?= |$)",markers[i]):
            changed=markers.copy();changed[i]=markers[i][:m.start()]+("0" if m.group()!="0" else "1")+markers[i][m.end():]
            cases.append(changed)
    for case in cases:
        try: validate_markers(case,bad_owner=bad_owner,supervisor_code_pages=supervisor_code_pages)
        except ValueError: continue
        raise ValueError("hostile launch observation accepted")
    return len(cases)
