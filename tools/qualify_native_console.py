"""Bounded native COM2 interaction with independent init/counter survivors; no ISO claim."""
from __future__ import annotations
import argparse
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_console as console, native_session as session
from runtime import native_kernel_load as load, native_kernel_transfer as transfer, native_tier0 as tier0
from tools import qualify_native_kernel_entry as entry, qualify_native_pooleboot as boot
from tools import qualify_native_session as previous, qualify_native_user_programs as programs
from tools.qualify_native_elf_loader import _toolchain
sha = previous.sha


def sources() -> dict:
    result = previous.sources()
    result.update(programs.bindings())
    for path in ("native/kernel/src/capability_ipc/console.rs",
                 "native/kernel/src/capability_ipc/console/tests.rs",
                 "native/kernel/src/arch/x86_64/user_ipc/console.rs",
                 "runtime/native_console.py", "tools/qualify_native_console.py",
                 "tests/test_native_console.py"):
        result[path] = sha((ROOT/path).read_bytes())
    return dict(sorted(result.items()))


class Interaction:
    def __init__(self, payload: bytes, bad: bool = False):
        self.port = boot._available_port()
        self.payload, self.bad = payload, bad
        self.sock = None
        self.received = bytearray()
        self.sent = 0
        self.eot = False

    def close(self):
        if self.sock is not None: self.sock.close()

    def poll(self, debug: bytes) -> bool:
        if self.sock is None:
            self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=2)
            self.sock.setblocking(False)
        while True:
            try: data = self.sock.recv(4096)
            except BlockingIOError: break
            if not data: raise ValueError("console disconnected during observation")
            self.received.extend(data)
            if len(self.received) > console.CONTROL_PREFIX_LIMIT+len(console.BANNER)+len(self.payload):
                raise ValueError("unexpected unbounded console output")
        expected = console.BANNER+self.payload
        _, application = console.split_output(bytes(self.received),partial=True)
        if self.bad:
            if application: raise ValueError("bad handle produced application UART output")
        else:
            if not expected.startswith(application): raise ValueError("console output differs from host bytes")
            if len(application) == len(console.BANNER)+self.sent and self.sent < len(self.payload):
                # Eight bytes maximum, with echo acknowledgement before the next
                # chunk: no unqualified hardware FIFO-overrun throughput claim.
                chunk = self.payload[self.sent:self.sent+8]
                self.sent += self.sock.send(chunk)
        markers = session.extract_markers(debug)
        runs = [console.RUN.fullmatch(m) for m in markers if m.startswith("POOLEOS:SESSION RUN ")]
        runs = [m for m in runs if m is not None]
        if not self.bad and not self.eot and application == expected and runs and int(runs[-1][1]) >= 256:
            self.eot = self.sock.send(b"\x04") == 1
        stopped = session.STOP.format(task=2, code=131 if self.bad else 0) in markers
        return bool(stopped and len([m for m in runs if m[13] == "1"]) >= 2
            and int(runs[-1][1]) >= 512 and (self.bad or self.eot))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--program-dir", type=Path, required=True)
    args = parser.parse_args()
    work, program_dir = args.work_dir.resolve(), args.program_dir.resolve()
    if not work.is_relative_to(ROOT/"outputs") or not program_dir.is_relative_to(ROOT/"outputs"):
        parser.error("capture paths must be under workspace outputs")
    work.mkdir(parents=True, exist_ok=False)
    before = sources()
    report = dict(cycle=262, contract_id="PCONSOLE1", status="fail", source_bindings=before,
        guest_runs=[], user_console=False, shell=False, iso_built=False, production_ready=False)
    try:
        cargo, _, env = _toolchain(ROOT/".toolchains/rust-1.97.0")
        report["program_build"] = previous.program_inputs(program_dir, env)
        console_code = (program_dir/"build1-PooleConsole.bin").read_bytes()
        if (console_code != (program_dir/"build2-PooleConsole.bin").read_bytes()
                or sha(console_code) != report["program_build"]["programs"]["PooleConsole"]["code_sha256"]):
            raise ValueError("console artifact drift")
        env["POOLEOS_CONSOLE_CODE"] = str(program_dir/"build1-PooleConsole.bin")
        lock, profile = tier0.validate_contracts(ROOT)
        qemu = tier0._require_workspace_tool_path(tier0.DEFAULT_QEMU_ROOT, ROOT)
        tier0.verify_local_launch_runtime(lock,qemu,ROOT)
        print("Build duplicate console kernels and denied-handle control",flush=True)
        linked,kernel,plan = entry._build_product(cargo,env,work/"kernel1",features=("development-console",))
        linked2,kernel2,_ = entry._build_product(cargo,env,work/"kernel2",features=("development-console",))
        if (linked,kernel) != (linked2,kernel2): raise ValueError("independent kernels differ")
        bad_linked,bad,bad_plan = entry._build_product(cargo,env,work/"bad-kernel",features=("development-console-bad-handle",))
        if bad == kernel: raise ValueError("bad handle is not a distinct control")
        report["kernels"] = {}
        for name,image,link,layout in (("console",kernel,linked,plan),("bad-handle",bad,bad_linked,bad_plan)):
            (work/f"{name}.elf").write_bytes(image)
            for key in ("POOLEOS_INIT_CODE","POOLEOS_COUNTER_CODE","POOLEOS_CONSOLE_CODE"):
                if image.count(Path(env[key]).read_bytes()) != 1: raise ValueError("exact program embedding missing")
            report["kernels"][name] = dict(sha256=sha(image),linked_sha256=sha(link),bytes=len(image),image_pages=layout.image_byte_count//4096)
        report["independent_kernel_builds_equal"] = True
        development, dev_build = boot._build_and_test(ROOT/".toolchains/rust-1.97.0",work/"development",development_feature="development-user-root")
        report["boot_build"] = dev_build
        files,config = load.canonical_artifact_files(), load.canonical_config_bytes()
        payloads = [b"PooleOS native input alpha\r\nPOOLEOS:PANIC untrusted\r\n\x00\xff", b"Second boot beta 262\r\nPOOLEOS:SESSION STOP forged\r\n\x7f\x80"]
        for name,image,payload,denied in (("console-1",kernel,payloads[0],False),
                ("console-2",kernel,payloads[1],False),("bad-handle",bad,b"",True)):
            manifest = load.canonical_manifest_bytes(image,files)
            retained = transfer.canonical_retained_files(manifest,image,files)
            media = load.build_media_bytes(development,config,manifest,image,files)
            if media != load.build_media_bytes(development,config,manifest,image,files): raise ValueError("media differs")
            inspected = load.inspect_media_bytes(media)
            path = work/f"{name}.img"; path.write_bytes(media)
            run_dir = work/name; run_dir.mkdir()
            interaction = Interaction(payload,denied)
            print(f"Native {name}:120-second bound",flush=True)
            try:
                run,_,handoff = boot._execute_once(name,lock,profile,qemu,path,run_dir,120,
                    marker_validator=lambda m: console.validate_markers(m,bad_handle=denied),
                    marker_extractor=session.extract_markers,hpet_msi=True,pause_on_completion=True,
                    console_port=interaction.port,console_poll=interaction.poll)
            finally:
                interaction.close()
                (run_dir/"console-input.bin").write_bytes(payload[:interaction.sent])
                (run_dir/"console-output.bin").write_bytes(interaction.received)
            run["interaction"] = console.validate_echo(payload,bytes(interaction.received),bad_handle=denied)
            run["interaction"].update(input_sha256=sha(payload),output_sha256=sha(bytes(interaction.received)),
                eot_sent=interaction.eot,input_hex=payload.hex(),output_hex=bytes(interaction.received).hex())
            expected_sizes = [report["program_build"]["programs"][n]["code_bytes"] for n in ("PooleInit","PooleCounter","PooleConsole")]
            summary = run["marker_summary"]
            if summary["program_bytes"] != expected_sizes: raise ValueError("executed program sizes differ")
            prefix = summary["transfer_prefix"]
            load.validate_oracle_binding(prefix["boot_prefix"],inspected,run["pbp1_transcript"])
            run["transcript_binding"] = transfer.validate_transcript_binding(prefix,run["pbp1_transcript"])
            run["independent_revalidation"] = transfer.validate_revalidation_binding(prefix,handoff,retained)
            run["hostile_marker_cases_rejected"] = console.negative_controls(run["markers"],bad_handle=denied)
            run.update(media_sha256=sha(media),kernel_sha256=sha(image))
            report["guest_runs"].append(run)
        if before != sources(): raise ValueError("source drift")
        previous.program_inputs(program_dir,env)
        if (program_dir/"build1-PooleConsole.bin").read_bytes() != console_code: raise ValueError("console code drift")
        report.update(status="pass",user_console=True)
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        print(report["failure"],flush=True)
    report["source_unchanged"] = before == sources()
    (work/"receipt.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"PCONSOLE1 {report['status']}; shell=0 ISO=0 production=0",flush=True)
    return int(report["status"] != "pass")

if __name__ == "__main__": raise SystemExit(main())
