"""Qualify focused/dragging fault and exit in an owned native input-profile VM."""
import argparse,json,time
from pathlib import Path
from tools import qualify_native_local_console as local
from tools.qualify_native_windows import SurfaceProbe
from tools.native_input_lifetime_probe import LifetimeInteraction,LifetimeProbe
from runtime import native_surface_lifecycle as final_frames


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--backend',choices=('qemu','virtualbox'),required=True)
    p.add_argument('--keyboard-batch',type=int,choices=(1,4),default=1)
    p.add_argument('--virtualbox',type=Path);p.add_argument('--visible',action='store_true')
    args=p.parse_args()
    if args.visible and args.backend!='virtualbox':p.error('visible mode is VirtualBox-only')
    if args.backend=='virtualbox' and args.virtualbox is None:p.error('explicit VirtualBox executable required')
    report,iso,disk=local.check_preview(args.receipt.resolve())
    if not all(report.get(k) is True for k in ('window_surfaces','window_capacity','surface_lifecycle','surface_input')):
        raise ValueError('qualified interactive lifecycle image required')
    work=args.work_dir.resolve()
    if not work.is_relative_to(local.ROOT/'outputs') or work==local.ROOT/'outputs':raise ValueError('new workspace output required')
    work.mkdir(parents=True,exist_ok=False)
    before=local.source.source_bindings();started=time.monotonic()
    interaction=LifetimeInteraction(args.keyboard_batch);probe=LifetimeProbe(work);surfaces=SurfaceProbe(work)
    result=dict(cycle=301,contract_id='PWS1',status='fail',source_bindings=before,iso_sha256=local.digest(iso),
                backend=args.backend,visible=args.visible,guest_bound_seconds=240,physical_hardware_tested=False,
                native_arbitrary_backlog_qualified=False,native_continuous_typematic_qualified=False,production_ready=False)
    pointer=None
    try:
        shared=local.qualification.shared
        if args.backend=='qemu':
            lock,base=shared.tier0.validate_contracts(local.ROOT)
            qemu=shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT,local.ROOT)
            shared.tier0.verify_local_launch_runtime(lock,qemu,local.ROOT)
            def control(client,debug):
                def inject(codes):
                    client.execute('input-send-event',{'events':[{'type':'key','data':{'down':not bool(c&128),'key':{'type':'number','data':c&127}}} for c in codes]})
                interaction.inject=inject;probe.tick(client,interaction,debug);surfaces.tick(client,interaction,debug)
            run,_,_=shared.boot._execute_once('native-input-lifetime',lock,local.optical.optical_profile(base),qemu,iso,work,240,
                marker_validator=lambda m:local.apps.validate_markers(m,file_waits=True,windows=True,window_capacity=True,surface_lifecycle=True),
                marker_extractor=local.native_session.extract_markers,hpet_msi=True,pause_on_completion=True,
                console_port=interaction.port,console_poll=interaction.poll,capture_log_limit_bytes=local.LOG_LIMIT,
                guest_control=control,frame_validator=final_frames.inspect_ppm)
        else:
            from runtime.native_virtualbox_mouse import PointerClient
            def control(owner,debug):
                nonlocal pointer
                if not interaction.sustained_evidence:return
                if pointer is None:pointer=PointerClient(owner,args.virtualbox.resolve())
                probe.tick(pointer,interaction,debug);surfaces.tick(pointer,interaction,debug)
            local.vbox_run(report,iso,work,interaction,result,args.virtualbox.resolve(),args.visible,control)
            run=result['run']
            if pointer is None:raise ValueError('pointer API not reached')
            pointer.check_shell()
        _,output=local.native_console.split_output(bytes(interaction.received))
        serial=b''.join(c['command'] for c in interaction.controls)
        if (not probe.done or len(probe.evidence)!=24 or interaction.completed!={0,1} or
            bytes(interaction.serial_controls)!=serial or interaction.sent!=len(interaction.case.sent) or
            interaction.keyboard_bytes+len(serial)!=interaction.sent or output!=interaction.case.expected or
            interaction.observed_surfaces!=set(interaction.surface_barriers) or len(surfaces.evidence)!=6):
            raise ValueError('incomplete or inexact input lifetime challenge')
        shared.load.validate_oracle_binding(run['marker_summary']['transfer_prefix']['boot_prefix'],
                                           shared.load.inspect_media_bytes(disk),run['pbp1_transcript'])
        result.update(status='pass',run=run,exact_interaction=True,focused_fault_and_exit_verified=True,
                      active_drag_retirement_verified=True,explicit_focus_recovery_verified=True,
                      held_modifier_recovery_verified=True,sustained_window=interaction.sustained_evidence,
                      hostile_marker_cases_rejected=local.apps.negative_controls(run['markers'],file_waits=True,windows=True,window_capacity=True,surface_lifecycle=True))
    except Exception as e:result['failure']=f'{type(e).__name__}: {e}'
    finally:
        interaction.close()
        (work/'challenge-input.bin').write_bytes(interaction.case.sent[:interaction.sent])
        (work/'serial-controls.bin').write_bytes(interaction.serial_controls)
        (work/'console-output.bin').write_bytes(interaction.received)
        result.update(evidence=probe.evidence,movements=probe.movements,probe_scancodes=probe.codes,
            captures=probe.captures,maximum_captures=probe.MAX_CAPTURES,action_bound_seconds=probe.ACTION_SECONDS,
            surface_observations=surfaces.evidence,keyboard_batch=interaction.keyboard_batch,batches=interaction.batches,
            keyboard_input_bytes=interaction.keyboard_bytes,serial_input_bytes=len(interaction.serial_controls),
            source_unchanged=before==local.source.source_bindings(),iso_unchanged=local.digest(iso)==result['iso_sha256'],
            elapsed_seconds=round(time.monotonic()-started,3))
        if pointer is not None:
            result['pointer_api_diagnostics']=pointer.diagnostics
            result['pointer_api']=dict(events=pointer.records,powershell_sha256=pointer.shell_hash,
                failed=pointer.failed,host_cursor_moved=False,unlocked_per_event=True,api_bound_seconds=5,maximum_events=96)
        if not result['source_unchanged'] or not result['iso_unchanged']:result['status']='fail'
        (work/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],result.get('failure',''),flush=True)
    return int(result['status']!='pass')


if __name__=='__main__':raise SystemExit(main())
