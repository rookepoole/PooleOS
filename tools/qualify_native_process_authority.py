"""Two fresh bounded PPROC1 guests on independently reproduced native binaries."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import native_process_authority as probe
from tools import qualify_native_console_ipc as shared, qualify_native_user_entry as source
from tools.native_build_space import require_space

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir",type=Path,required=True)
    args=p.parse_args();work=args.work_dir.resolve()
    if not work.is_relative_to(ROOT/"outputs"): p.error("work must be inside outputs")
    storage=require_space(work);work.mkdir(parents=True,exist_ok=False)
    before=source.source_bindings()
    report=dict(cycle=267,contract_id="PPROC1",status="fail",source_bindings=before,
        storage_preflight=storage,guest_bound_seconds=120,guest_runs=[],iso_built=False,production_ready=False)
    try:
        cargo,_,env=shared._toolchain(ROOT/".toolchains/rust-1.97.0")
        lock,profile=shared.tier0.validate_contracts(ROOT)
        qemu=shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT,ROOT)
        shared.tier0.verify_local_launch_runtime(lock,qemu,ROOT)
        print("Build independent PPROC1 kernels",flush=True)
        linked,kernel,plan=shared.entry._build_product(cargo,env,work/"kernel1",features=("development-process-control",))
        linked2,kernel2,_=shared.entry._build_product(cargo,env,work/"kernel2",features=("development-process-control",))
        if (linked,kernel)!=(linked2,kernel2): raise ValueError("independent kernel mismatch")
        (work/"kernel.elf").write_bytes(kernel)
        report["kernel"]=dict(sha256=shared.sha(kernel),linked_sha256=shared.sha(linked),bytes=len(kernel),image_pages=plan.image_byte_count//4096)
        report["independent_kernel_builds_equal"]=True
        development,report["boot_build"]=shared.boot._build_and_test(ROOT/".toolchains/rust-1.97.0",work/"development",development_feature="development-user-root")
        files,config=shared.load.canonical_artifact_files(),shared.load.canonical_config_bytes()
        manifest=shared.load.canonical_manifest_bytes(kernel,files)
        retained=shared.transfer.canonical_retained_files(manifest,kernel,files)
        media=shared.load.build_media_bytes(development,config,manifest,kernel,files)
        if media!=shared.load.build_media_bytes(development,config,manifest,kernel,files): raise ValueError("media mismatch")
        inspected=shared.load.inspect_media_bytes(media);path=work/"process.img";path.write_bytes(media)
        report["media_sha256"]=shared.sha(media)
        for number in (1,2):
            name=f"guest-{number}";run_dir=work/name;run_dir.mkdir()
            print(f"PPROC1 {name}:120-second bound",flush=True)
            run,_,handoff=shared.boot._execute_once(name,lock,profile,qemu,path,run_dir,120,
                marker_validator=probe.validate_markers,marker_extractor=shared.transfer.extract_markers,
                completion_marker=probe.COMPLETION,hpet_msi=True)
            prefix=run["marker_summary"]["transfer_prefix"]
            shared.load.validate_oracle_binding(prefix["boot_prefix"],inspected,run["pbp1_transcript"])
            run["transcript_binding"]=shared.transfer.validate_transcript_binding(prefix,run["pbp1_transcript"])
            run["independent_revalidation"]=shared.transfer.validate_revalidation_binding(prefix,handoff,retained)
            run["hostile_marker_cases_rejected"]=probe.negative_controls(run["markers"])
            report["guest_runs"].append(run)
        if before!=source.source_bindings(): raise ValueError("source drift")
        report["status"]="pass"
    except Exception as error:
        report["failure"]=f"{type(error).__name__}: {error}"
        print(report["failure"],flush=True)
    report["source_unchanged"]=before==source.source_bindings()
    (work/"receipt.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"PPROC1 {report['status']}; supervisor=0 shell=0 ISO=0 production=0",flush=True)
    return int(report["status"]!="pass")
if __name__=="__main__": raise SystemExit(main())
