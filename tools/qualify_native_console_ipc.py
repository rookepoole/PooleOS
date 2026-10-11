"""Native tracked console requests and bounded peer-death termination; no ISO."""
from __future__ import annotations
import argparse
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import native_console as console, native_console_ipc as ipc, native_session as session
from runtime import native_kernel_load as load, native_kernel_transfer as transfer, native_tier0 as tier0
from tools import qualify_native_console as previous, qualify_native_kernel_entry as entry, qualify_native_pooleboot as boot
from tools import qualify_native_session as session_build
from tools.native_build_space import require_space
from tools.qualify_native_elf_loader import _toolchain
sha = previous.sha


def sources():
    result = previous.sources()
    for path in ("runtime/native_console_ipc.py","tools/qualify_native_console_ipc.py","tests/test_native_console_ipc.py", "tests/test_native_console_rpc.py"):
        result[path]=sha((ROOT/path).read_bytes())
    return dict(sorted(result.items()))


def program_inputs(directory, env):
    receipt=session_build.program_inputs(directory,env)
    for name,key in (("PooleConsoleService","POOLEOS_CONSOLE_CODE"),("PooleConsoleClient","POOLEOS_CONSOLE_CLIENT_CODE")):
        code=(directory/f"build1-{name}.bin").read_bytes()
        if code!=(directory/f"build2-{name}.bin").read_bytes() or sha(code)!=receipt["programs"][name]["code_sha256"]:
            raise ValueError("console program identity differs")
        env[key]=str(directory/f"build1-{name}.bin")
    return receipt


class Interaction(previous.Interaction):
    def poll(self, debug: bytes) -> bool:
        if self.sock is None:
            self.sock=socket.create_connection(("127.0.0.1",self.port),timeout=2)
            self.sock.setblocking(False)
        while True:
            try: data=self.sock.recv(4096)
            except BlockingIOError: break
            if not data: raise ValueError("COM2 disconnected")
            self.received.extend(data)
            if len(self.received)>console.CONTROL_PREFIX_LIMIT+len(self.payload): raise ValueError("unbounded COM2")
        _,application=console.split_output(bytes(self.received),partial=True)
        markers=session.extract_markers(debug)
        runs=[ipc.RUN.fullmatch(m) for m in markers if m.startswith("POOLEOS:SESSION RUN ")]
        runs=[m for m in runs if m is not None]
        if self.bad:
            if application: raise ValueError("wrong peer produced output")
        else:
            if not self.payload.startswith(application): raise ValueError("IPC output differs from host input")
            if (runs and int(runs[-1][11])>=32 and len(application)==self.sent and self.sent<len(self.payload)):
                self.sent+=self.sock.send(self.payload[self.sent:self.sent+8])
            if not self.eot and application==self.payload and runs and int(runs[-1][1])>=256:
                self.eot=self.sock.send(b"\x04")==1
        service_stop=any(m.startswith(session.STOP.format(task=2,code=152 if self.bad else 0)+" dispatches=") for m in markers)
        client_stop=any(m.startswith(session.STOP.format(task=3,code=163 if self.bad else 0)+" dispatches=") for m in markers)
        retired=[m for m in runs if m[13]=="1" and m[17]=="1"]
        return bool(service_stop and client_stop and (self.bad or self.eot) and len(retired)>=2 and int(runs[-1][1])>=512)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir",type=Path,required=True)
    parser.add_argument("--program-dir",type=Path,required=True)
    args=parser.parse_args(); work,program_dir=args.work_dir.resolve(),args.program_dir.resolve()
    if not work.is_relative_to(ROOT/"outputs") or not program_dir.is_relative_to(ROOT/"outputs"):
        parser.error("capture paths must be under outputs")
    storage=require_space(work)
    work.mkdir(parents=True,exist_ok=False)
    before=sources()
    report=dict(cycle=265,contract_id="PSESSION4",status="fail",source_bindings=before,
        storage_preflight=storage,guest_runs=[],native_console_ipc=False,peer_death_termination=False,polling_peer_death_recovery=False,
        shell=False,iso_built=False,production_ready=False)
    try:
        cargo,_,env=_toolchain(ROOT/".toolchains/rust-1.97.0")
        report["program_build"]=program_inputs(program_dir,env)
        lock,profile=tier0.validate_contracts(ROOT)
        qemu=tier0._require_workspace_tool_path(tier0.DEFAULT_QEMU_ROOT,ROOT)
        tier0.verify_local_launch_runtime(lock,qemu,ROOT)
        print("Build two four-task kernels and wrong-peer control",flush=True)
        linked,kernel,plan=entry._build_product(cargo,env,work/"kernel1",features=("development-console-ipc",))
        linked2,kernel2,_=entry._build_product(cargo,env,work/"kernel2",features=("development-console-ipc",))
        if (linked,kernel)!=(linked2,kernel2): raise ValueError("independent kernel mismatch")
        bad_linked,bad,bad_plan=entry._build_product(cargo,env,work/"bad-kernel",features=("development-console-ipc-bad-peer",))
        if bad==kernel: raise ValueError("control must differ")
        report["kernels"]={}
        for name,image,link,layout in (("ipc",kernel,linked,plan),("bad-peer",bad,bad_linked,bad_plan)):
            (work/f"{name}.elf").write_bytes(image)
            for key in ("POOLEOS_INIT_CODE","POOLEOS_COUNTER_CODE","POOLEOS_CONSOLE_CODE","POOLEOS_CONSOLE_CLIENT_CODE"):
                if image.count(Path(env[key]).read_bytes())!=1: raise ValueError("program embedding mismatch")
            report["kernels"][name]=dict(sha256=sha(image),linked_sha256=sha(link),bytes=len(image),image_pages=layout.image_byte_count//4096)
        report["independent_kernel_builds_equal"]=True
        development,dev_build=boot._build_and_test(ROOT/".toolchains/rust-1.97.0",work/"development",development_feature="development-user-root")
        report["boot_build"]=dev_build
        files,config=load.canonical_artifact_files(),load.canonical_config_bytes()
        payloads=[b"Native RPC alpha\r\nPOOLEOS:PANIC untrusted\r\n\x00\xff",b"Native RPC beta 265\r\nPOOLEOS:SESSION STOP forged\r\n\x7f\x80"]
        for name,image,payload,denied in (("ipc-1",kernel,payloads[0],False),("ipc-2",kernel,payloads[1],False),("bad-peer",bad,b"",True)):
            manifest=load.canonical_manifest_bytes(image,files)
            retained=transfer.canonical_retained_files(manifest,image,files)
            media=load.build_media_bytes(development,config,manifest,image,files)
            if media!=load.build_media_bytes(development,config,manifest,image,files): raise ValueError("media mismatch")
            inspected=load.inspect_media_bytes(media)
            path=work/f"{name}.img"; path.write_bytes(media)
            run_dir=work/name; run_dir.mkdir()
            interaction=Interaction(payload,denied)
            print(f"Native {name}: 120-second bound",flush=True)
            try:
                run,_,handoff=boot._execute_once(name,lock,profile,qemu,path,run_dir,120,
                    marker_validator=lambda m:ipc.validate_tracked_markers(m,bad_peer=denied),
                    marker_extractor=session.extract_markers,hpet_msi=True,pause_on_completion=True,
                    console_port=interaction.port,console_poll=interaction.poll)
            finally:
                interaction.close()
                (run_dir/"console-input.bin").write_bytes(payload[:interaction.sent])
                (run_dir/"console-output.bin").write_bytes(interaction.received)
            run["interaction"]=ipc.validate_echo(payload,bytes(interaction.received),bad_peer=denied)
            run["interaction"].update(input_sha256=sha(payload),output_sha256=sha(bytes(interaction.received)),
                input_hex=payload.hex(),output_hex=bytes(interaction.received).hex(),eot_sent=interaction.eot)
            names=("PooleInit","PooleCounter","PooleConsoleService","PooleConsoleClient")
            if run["marker_summary"]["program_bytes"]!=[report["program_build"]["programs"][n]["code_bytes"] for n in names]:
                raise ValueError("runtime sizes mismatch")
            prefix=run["marker_summary"]["transfer_prefix"]
            load.validate_oracle_binding(prefix["boot_prefix"],inspected,run["pbp1_transcript"])
            run["transcript_binding"]=transfer.validate_transcript_binding(prefix,run["pbp1_transcript"])
            run["independent_revalidation"]=transfer.validate_revalidation_binding(prefix,handoff,retained)
            run["hostile_marker_cases_rejected"]=ipc.negative_controls(run["markers"],bad_peer=denied,tracked=True)
            run.update(media_sha256=sha(media),kernel_sha256=sha(image))
            report["guest_runs"].append(run)
        if program_inputs(program_dir,env)!=report["program_build"]: raise ValueError("program receipt drift")
        if before!=sources(): raise ValueError("source drift")
        report.update(status="pass",native_console_ipc=True,peer_death_termination=True)
    except Exception as exc:
        report["failure"]=f"{type(exc).__name__}: {exc}"
        print(report["failure"],flush=True)
    report["source_unchanged"]=before==sources()
    (work/"receipt.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"PSESSION4 {report['status']}; shell=0 ISO=0 production=0",flush=True)
    return int(report["status"]!="pass")

if __name__=="__main__": raise SystemExit(main())
