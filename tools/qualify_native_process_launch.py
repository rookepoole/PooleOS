"""Independent supervisor/kernel builds; three PLAUNCH1 guests with PCOMP1 completion."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import native_process_completion as probe, native_user_program
from tools import qualify_native_console_ipc as shared, qualify_native_user_entry as source
from tools.qualify_native_user_programs import bindings as program_bindings
from tools.native_build_space import require_space

def program_input(directory,env):
    receipt=json.loads((directory/'receipt.json').read_bytes())
    if receipt['status']!='pass' or not receipt['source_unchanged'] or not receipt['direct_byte_equality']: raise ValueError('program qualification failed')
    if receipt.get('independent_builds')!=2 or receipt['source_bindings']!=program_bindings():raise ValueError('incomplete or stale program source bindings')
    for p,h in receipt['source_bindings'].items():
        if shared.sha((ROOT/p).read_bytes())!=h: raise ValueError('program source drift')
    name='PooleSupervisor'
    a=(directory/f'build1-{name}.bin').read_bytes();b=(directory/f'build2-{name}.bin').read_bytes()
    if a!=b or shared.sha(a)!=receipt['programs'][name]['code_sha256']:raise ValueError('supervisor code mismatch')
    # ELF/code identity is checked before capture, not inferred from the receipt.
    for build in ('build1','build2'):
        snapshot=directory/f'{build}-{name}.elf'
        elf=(snapshot if snapshot.is_file() else directory/build/'x86_64-unknown-none/release'/name).read_bytes()
        code,record=native_user_program.extract(elf)
        if code!=a or record['elf_sha256']!=receipt['programs'][name]['elf_sha256']:raise ValueError('supervisor ELF mismatch')
    env['POOLEOS_SUPERVISOR_CODE']=str((directory/f'build1-{name}.bin').resolve())
    return receipt,a

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--program-dir',type=Path,required=True)
    args=p.parse_args();work=args.work_dir.resolve();programs=args.program_dir.resolve()
    if not work.is_relative_to(ROOT/'outputs') or not programs.is_relative_to(ROOT/'outputs'):p.error('workspace outputs required')
    storage=require_space(work);work.mkdir(parents=True,exist_ok=False);before=source.source_bindings()
    report=dict(cycle=271,contract_id='PCOMP1',launch_contract_id='PLAUNCH1',status='fail',source_bindings=before,storage_preflight=storage,guest_bound_seconds=120,guest_runs=[],iso_built=False,production_ready=False)
    try:
        cargo,_,env=shared._toolchain(ROOT/'.toolchains/rust-1.97.0')
        report['program_build'],code=program_input(programs,env)
        lock,profile=shared.tier0.validate_contracts(ROOT);qemu=shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT,ROOT)
        shared.tier0.verify_local_launch_runtime(lock,qemu,ROOT)
        print('Build independent launch kernels and denied-owner control',flush=True)
        linked,kernel,plan=shared.entry._build_product(cargo,env,work/'kernel1',features=('development-process-launch',))
        linked2,kernel2,_=shared.entry._build_product(cargo,env,work/'kernel2',features=('development-process-launch',))
        if (linked,kernel)!=(linked2,kernel2):raise ValueError('independent kernel mismatch')
        bad_linked,bad,bad_plan=shared.entry._build_product(cargo,env,work/'bad-kernel',features=('development-process-launch-bad-owner',))
        if bad==kernel:raise ValueError('bad owner control not distinct')
        report['independent_kernel_builds_equal']=True;report['kernels']={}
        for name,image,link,layout in [('launch',kernel,linked,plan),('bad-owner',bad,bad_linked,bad_plan)]:
            if image.count(code)!=1:raise ValueError('exact independent supervisor not embedded once')
            (work/f'{name}.elf').write_bytes(image)
            report['kernels'][name]=dict(sha256=shared.sha(image),linked_sha256=shared.sha(link),bytes=len(image),image_pages=layout.image_byte_count//4096)
        development,report['boot_build']=shared.boot._build_and_test(ROOT/'.toolchains/rust-1.97.0',work/'development',development_feature='development-user-root')
        files,config=shared.load.canonical_artifact_files(),shared.load.canonical_config_bytes()
        for name,image,bad_owner in [('launch-1',kernel,False),('launch-2',kernel,False),('bad-owner',bad,True)]:
            manifest=shared.load.canonical_manifest_bytes(image,files);retained=shared.transfer.canonical_retained_files(manifest,image,files)
            media=shared.load.build_media_bytes(development,config,manifest,image,files)
            if media!=shared.load.build_media_bytes(development,config,manifest,image,files):raise ValueError('media mismatch')
            inspected=shared.load.inspect_media_bytes(media);path=work/f'{name}.img';path.write_bytes(media)
            run_dir=work/name;run_dir.mkdir();print(f'PLAUNCH1 {name}:120-second bound',flush=True)
            run,_,handoff=shared.boot._execute_once(name,lock,profile,qemu,path,run_dir,120,
                marker_validator=lambda m:probe.validate_markers(m,bad_owner=bad_owner),marker_extractor=shared.transfer.extract_markers,
                completion_marker=probe.COMPLETION,hpet_msi=True)
            if run['marker_summary']['start']['supervisor_bytes']!=len(code):raise ValueError('observed program size mismatch')
            prefix=run['marker_summary']['transfer_prefix'];shared.load.validate_oracle_binding(prefix['boot_prefix'],inspected,run['pbp1_transcript'])
            run['transcript_binding']=shared.transfer.validate_transcript_binding(prefix,run['pbp1_transcript'])
            run['independent_revalidation']=shared.transfer.validate_revalidation_binding(prefix,handoff,retained)
            run['hostile_marker_cases_rejected']=probe.negative_controls(run['markers'],bad_owner=bad_owner)
            run['kernel_sha256']=shared.sha(image);run['media_sha256']=shared.sha(media);report['guest_runs'].append(run)
        if before!=source.source_bindings():raise ValueError('source drift')
        program_input(programs,env)
        report['status']='pass'
    except Exception as error:
        report['failure']=f'{type(error).__name__}: {error}';print(report['failure'],flush=True)
    report['source_unchanged']=before==source.source_bindings()
    (work/'receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f"PLAUNCH1 {report['status']}; general_supervisor=0 shell=0 ISO=0 production=0",flush=True)
    return int(report['status']!='pass')
if __name__=='__main__':raise SystemExit(main())
