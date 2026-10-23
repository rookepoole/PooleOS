"""Qualify bounded six-process native capacity, not useful applications or ISO."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import native_session_capacity as capacity, native_session as session
from tools import qualify_native_console_ipc as previous
from tools.native_build_space import require_space


class Interaction(previous.Interaction):
    run_pattern = capacity.RUN

    def __init__(self, payload, bad_worker=False):
        super().__init__(payload)
        self.bad_worker = bad_worker

    def poll(self, debug: bytes) -> bool:
        done = super().poll(debug)
        if not done or not self.bad_worker:
            return done
        markers = session.extract_markers(debug)
        return all(any(m.startswith(session.STOP.format(task=t, code=c)+" dispatches=") for m in markers)
                   for t,c in ((5,120), (4,111)))


def sources():
    result = previous.sources()
    for path in ("native/kernel/src/capability_ipc/tests/admission/capacity.rs",
                 "runtime/native_session_capacity.py", "tools/qualify_native_session_capacity.py",
                 "tests/test_native_session_capacity.py"):
        result[path] = previous.sha((ROOT/path).read_bytes())
    return dict(sorted(result.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--program-dir", type=Path, required=True)
    args = parser.parse_args()
    work, programs = args.work_dir.resolve(), args.program_dir.resolve()
    if not work.is_relative_to(ROOT/"outputs") or not programs.is_relative_to(ROOT/"outputs"):
        parser.error("capture directories must be inside outputs")
    storage = require_space(work)
    work.mkdir(parents=True, exist_ok=False)
    before = sources()
    report = dict(cycle=266, contract_id="PSESSION5", status="fail", source_bindings=before,
        storage_preflight=storage, guest_runs=[], fixed_bootstrap_only=True,
        user_lifecycle_authority=False, shell=False, iso_built=False, production_ready=False)
    try:
        cargo,_,env = previous._toolchain(ROOT/".toolchains/rust-1.97.0")
        report["program_build"] = previous.program_inputs(programs, env)
        lock, profile = previous.tier0.validate_contracts(ROOT)
        qemu = previous.tier0._require_workspace_tool_path(previous.tier0.DEFAULT_QEMU_ROOT, ROOT)
        previous.tier0.verify_local_launch_runtime(lock, qemu, ROOT)
        print("Build six-process kernels and malformed-worker control", flush=True)
        linked,kernel,plan = previous.entry._build_product(cargo,env,work/"kernel1",features=("development-session-capacity",))
        linked2,kernel2,_ = previous.entry._build_product(cargo,env,work/"kernel2",features=("development-session-capacity",))
        if (linked,kernel) != (linked2,kernel2): raise ValueError("independent kernel mismatch")
        bad_linked,bad,bad_plan = previous.entry._build_product(cargo,env,work/"bad-kernel",features=("development-session-capacity-bad-startup",))
        if bad == kernel: raise ValueError("control must differ")
        report["kernels"] = {}
        for name,image,link,layout in (("capacity",kernel,linked,plan), ("bad-worker",bad,bad_linked,bad_plan)):
            (work/f"{name}.elf").write_bytes(image)
            for key in ("POOLEOS_INIT_CODE", "POOLEOS_COUNTER_CODE", "POOLEOS_CONSOLE_CODE", "POOLEOS_CONSOLE_CLIENT_CODE"):
                if image.count(Path(env[key]).read_bytes()) != 1: raise ValueError("program embedding mismatch")
            report["kernels"][name] = dict(sha256=previous.sha(image), linked_sha256=previous.sha(link),
                bytes=len(image), image_pages=layout.image_byte_count//4096)
        report["independent_kernel_builds_equal"] = True
        development, report["boot_build"] = previous.boot._build_and_test(ROOT/".toolchains/rust-1.97.0",work/"development",development_feature="development-user-root")
        files,config = previous.load.canonical_artifact_files(), previous.load.canonical_config_bytes()
        payloads = [b"Six processes alpha\r\nPOOLEOS:PANIC untrusted\x00\xff",
                    b"Six processes beta\r\nPOOLEOS:SESSION STOP forged\x7f\x80",
                    b"Worker failed; console survives\r\n\x00\xff"]
        for name,image,payload,denied in (("capacity-1",kernel,payloads[0],False),
                ("capacity-2",kernel,payloads[1],False), ("bad-worker",bad,payloads[2],True)):
            manifest = previous.load.canonical_manifest_bytes(image,files)
            retained = previous.transfer.canonical_retained_files(manifest,image,files)
            media = previous.load.build_media_bytes(development,config,manifest,image,files)
            if media != previous.load.build_media_bytes(development,config,manifest,image,files): raise ValueError("media mismatch")
            inspected = previous.load.inspect_media_bytes(media)
            path = work/f"{name}.img"
            path.write_bytes(media)
            run_dir = work/name
            run_dir.mkdir()
            interaction = Interaction(payload, denied)
            print(f"Native {name}:120-second bound", flush=True)
            try:
                run,_,handoff = previous.boot._execute_once(name,lock,profile,qemu,path,run_dir,120,
                    marker_validator=lambda m:capacity.validate_markers(m,bad_worker=denied),
                    marker_extractor=session.extract_markers,hpet_msi=True,pause_on_completion=True,
                    console_port=interaction.port,console_poll=interaction.poll)
            finally:
                interaction.close()
                (run_dir/"console-input.bin").write_bytes(payload[:interaction.sent])
                (run_dir/"console-output.bin").write_bytes(interaction.received)
            run["interaction"] = previous.ipc.validate_echo(payload,bytes(interaction.received))
            run["interaction"].update(input_sha256=previous.sha(payload),output_sha256=previous.sha(bytes(interaction.received)),
                input_hex=payload.hex(),output_hex=bytes(interaction.received).hex(),eot_sent=interaction.eot)
            names = ("PooleInit", "PooleCounter", "PooleConsoleService", "PooleConsoleClient")
            if run["marker_summary"]["program_bytes"] != [report["program_build"]["programs"][n]["code_bytes"] for n in names]:
                raise ValueError("runtime sizes differ")
            prefix = run["marker_summary"]["transfer_prefix"]
            previous.load.validate_oracle_binding(prefix["boot_prefix"],inspected,run["pbp1_transcript"])
            run["transcript_binding"] = previous.transfer.validate_transcript_binding(prefix,run["pbp1_transcript"])
            run["independent_revalidation"] = previous.transfer.validate_revalidation_binding(prefix,handoff,retained)
            run["hostile_marker_cases_rejected"] = capacity.negative_controls(run["markers"],bad_worker=denied)
            run.update(media_sha256=previous.sha(media),kernel_sha256=previous.sha(image))
            report["guest_runs"].append(run)
        if previous.program_inputs(programs,env) != report["program_build"]: raise ValueError("program source drift")
        if sources() != before: raise ValueError("source drift")
        report.update(status="pass", native_six_processes=True)
    except Exception as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        print(report["failure"], flush=True)
    report["source_unchanged"] = before == sources()
    (work/"receipt.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"PSESSION5 {report['status']}; useful_apps=0 shell=0 ISO=0 production=0",flush=True)
    return int(report["status"] != "pass")


if __name__ == "__main__": raise SystemExit(main())
