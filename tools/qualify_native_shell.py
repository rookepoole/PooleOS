"""Observe independent PooleShell commands at CPL3 over the console RPC service."""
from __future__ import annotations
import argparse
import json
import secrets
import socket
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import native_shell as shell, native_console as console, native_console_ipc as ipc
from runtime import native_session as session, native_kernel_load as load, native_kernel_transfer as transfer, native_tier0 as tier0
from tools import qualify_native_console_ipc as previous, qualify_native_kernel_entry as entry, qualify_native_pooleboot as boot
from tools.native_build_space import require_space
from tools.qualify_native_elf_loader import _toolchain
sha=previous.sha

def sources():
    result=previous.sources()
    for path in ("runtime/native_shell.py","tests/test_native_shell.py","tools/qualify_native_shell.py"):
        result[path]=sha((ROOT/path).read_bytes())
    return dict(sorted(result.items()))

def program_inputs(directory,env):
    receipt=previous.program_inputs(directory,env)
    path=directory/"build1-PooleShell.bin"
    code=path.read_bytes()
    if code!=(directory/"build2-PooleShell.bin").read_bytes() or sha(code)!=receipt["programs"]["PooleShell"]["code_sha256"]:
        raise ValueError("independent shell bytes differ")
    env["POOLEOS_CONSOLE_CLIENT_CODE"]=str(path)
    return receipt

class Interaction(previous.Interaction):
    def __init__(self,case):
        super().__init__(case.sent if case else b"",case is None)
        self.case=case
        self.step=0
        self.expected=shell.BANNER if case else b""

    def poll(self,debug):
        if self.sock is None:
            self.sock=socket.create_connection(("127.0.0.1",self.port),timeout=2)
            self.sock.setblocking(False)
        while True:
            try: data=self.sock.recv(4096)
            except BlockingIOError: break
            if not data: raise ValueError("shell COM2 disconnected")
            self.received.extend(data)
            if len(self.received)>console.CONTROL_PREFIX_LIMIT+2048: raise ValueError("unbounded shell output")
        _,application=console.split_output(bytes(self.received),partial=True)
        if not self.expected.startswith(application): raise ValueError("shell output differs from host challenge")
        markers=session.extract_markers(debug)
        runs=[ipc.RUN.fullmatch(m) for m in markers if m.startswith("POOLEOS:SESSION RUN ")]
        runs=[m for m in runs if m is not None]
        # Keep two live observations, then type one acknowledged byte at a time.
        if self.case and runs and int(runs[-1][1])>=128 and application==self.expected and self.step<len(self.case.steps):
            byte,response=self.case.steps[self.step]
            if self.sock.send(byte)==1:
                self.sent+=1
                self.step+=1
                self.expected+=response
        stops=[any(m.startswith(session.STOP.format(task=t,code=c)+" dispatches=") for m in markers)
            for t,c in ((2,152 if self.bad else 0),(3,163 if self.bad else 0))]
        retired=[m for m in runs if m[13]=="1" and m[17]=="1"]
        done=self.bad or (self.step==len(self.case.steps) and application==self.case.expected)
        return bool(all(stops) and done and len(retired)>=2 and int(runs[-1][1])>=512)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir",type=Path,required=True)
    parser.add_argument("--program-dir",type=Path,required=True)
    args=parser.parse_args()
    work,program_dir=args.work_dir.resolve(),args.program_dir.resolve()
    if not work.is_relative_to(ROOT/"outputs") or not program_dir.is_relative_to(ROOT/"outputs"):
        parser.error("captures must be under outputs")
    storage=require_space(work)
    work.mkdir(parents=True,exist_ok=False)
    before=sources()
    report=dict(cycle=270,contract_id="PSHELL1",status="fail",source_bindings=before,storage_preflight=storage,
        guest_runs=[],native_command_shell=False,application_launch=False,bundled_files=False,iso_built=False,production_ready=False)
    try:
        cargo,_,env=_toolchain(ROOT/".toolchains/rust-1.97.0")
        report["program_build"]=program_inputs(program_dir,env)
        lock,profile=tier0.validate_contracts(ROOT)
        qemu=tier0._require_workspace_tool_path(tier0.DEFAULT_QEMU_ROOT,ROOT)
        tier0.verify_local_launch_runtime(lock,qemu,ROOT)
        print("Build independent shell session kernels and denied-peer control",flush=True)
        linked,kernel,plan=entry._build_product(cargo,env,work/"kernel1",features=("development-console-ipc",))
        linked2,kernel2,_=entry._build_product(cargo,env,work/"kernel2",features=("development-console-ipc",))
        if (linked,kernel)!=(linked2,kernel2): raise ValueError("independent kernel mismatch")
        bad_linked,bad,bad_plan=entry._build_product(cargo,env,work/"bad-kernel",features=("development-console-ipc-bad-peer",))
        if bad==kernel: raise ValueError("denied peer is not a distinct control")
        report["kernels"]={}
        for name,image,link,layout in (("shell",kernel,linked,plan),("bad-peer",bad,bad_linked,bad_plan)):
            (work/f"{name}.elf").write_bytes(image)
            for key in ("POOLEOS_INIT_CODE","POOLEOS_COUNTER_CODE","POOLEOS_CONSOLE_CODE","POOLEOS_CONSOLE_CLIENT_CODE"):
                if image.count(Path(env[key]).read_bytes())!=1: raise ValueError("exact independent program embedding mismatch")
            report["kernels"][name]=dict(sha256=sha(image),linked_sha256=sha(link),bytes=len(image),image_pages=layout.image_byte_count//4096)
        report["independent_kernel_builds_equal"]=True
        development,dev_build=boot._build_and_test(ROOT/".toolchains/rust-1.97.0",work/"development",development_feature="development-user-root")
        report["boot_build"]=dev_build
        files,config=load.canonical_artifact_files(),load.canonical_config_bytes()
        for name,image,case in (("commands",kernel,shell.scenario("commands",secrets.token_hex(8))),
                ("editing",kernel,shell.scenario("editing",secrets.token_hex(8))),("bad-peer",bad,None)):
            manifest=load.canonical_manifest_bytes(image,files)
            retained=transfer.canonical_retained_files(manifest,image,files)
            media=load.build_media_bytes(development,config,manifest,image,files)
            if media!=load.build_media_bytes(development,config,manifest,image,files): raise ValueError("media mismatch")
            inspected=load.inspect_media_bytes(media)
            path=work/f"{name}.img"; path.write_bytes(media)
            run_dir=work/name; run_dir.mkdir()
            interaction=Interaction(case)
            print(f"Native shell {name}: 120-second bound",flush=True)
            try:
                run,_,handoff=boot._execute_once(name,lock,profile,qemu,path,run_dir,120,
                    marker_validator=lambda m:ipc.validate_tracked_markers(m,bad_peer=case is None),
                    marker_extractor=session.extract_markers,hpet_msi=True,pause_on_completion=True,
                    console_port=interaction.port,console_poll=interaction.poll)
            finally:
                interaction.close()
                sent=interaction.payload[:interaction.sent]
                output=bytes(interaction.received)
                (run_dir/"console-input.bin").write_bytes(sent)
                (run_dir/"console-output.bin").write_bytes(output)
            run["interaction"]=shell.validate_interaction(case,sent,output)
            run["interaction"].update(input_sha256=sha(sent),output_sha256=sha(output),input_hex=sent.hex(),output_hex=output.hex())
            names=("PooleInit","PooleCounter","PooleConsoleService","PooleShell")
            if run["marker_summary"]["program_bytes"]!=[report["program_build"]["programs"][n]["code_bytes"] for n in names]:
                raise ValueError("native program sizes differ from compiled inputs")
            prefix=run["marker_summary"]["transfer_prefix"]
            load.validate_oracle_binding(prefix["boot_prefix"],inspected,run["pbp1_transcript"])
            run["transcript_binding"]=transfer.validate_transcript_binding(prefix,run["pbp1_transcript"])
            run["independent_revalidation"]=transfer.validate_revalidation_binding(prefix,handoff,retained)
            run["hostile_marker_cases_rejected"]=ipc.negative_controls(run["markers"],bad_peer=case is None,tracked=True)
            run.update(media_sha256=sha(media),kernel_sha256=sha(image))
            report["guest_runs"].append(run)
        if program_inputs(program_dir,env)!=report["program_build"] or before!=sources(): raise ValueError("source/input drift")
        report.update(status="pass",native_command_shell=True)
    except Exception as exc:
        report["failure"]=f"{type(exc).__name__}: {exc}"
        print(report["failure"],flush=True)
    report["source_unchanged"]=before==sources()
    (work/"receipt.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"PSHELL1 {report['status']}; app-launch=0 files=0 ISO=0 production=0",flush=True)
    return int(report["status"]!="pass")

if __name__=="__main__": raise SystemExit(main())
