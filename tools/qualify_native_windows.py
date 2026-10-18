"""Device-input qualification of the native window profile in owned guests."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from tools import qualify_native_local_console as local
from runtime import native_windows as frames
from runtime import native_surface_lifecycle as lifecycle_frames
from runtime import native_application_input as application_frames
from tools.native_application_input_probe import InputProbe
ROOT=local.ROOT

def lifecycle_barriers(sent):
    """Six ordered observations after acknowledged application commands."""
    cursor=sent.index(b'fault numbers\r')+len(b'fault numbers\r')
    result={}
    for command,visible,event,task,generation in (
        (b'status numbers', (True,False), 'RETIRE',5,1),
        (b'numbers /numbers.csv', (True,True), 'ADMIT',5,2),
        (b'status text', (False,True), 'RETIRE',4,1),
        (b'text /numbers.csv', (True,True), 'ADMIT',4,2),
        (b'status text', (False,True), 'RETIRE',4,2),
        (b'status numbers', (False,False), 'RETIRE',5,2),
    ):
        cursor=sent.index(command+b'\r',cursor)+len(command)+1
        result[cursor]=dict(visible=visible,event=event,task=task,generation=generation)
    return result

class WindowInteraction(local.Interaction):
    def __init__(self, keyboard_batch=1, surface_lifecycle=False, surface_input=False):
        if type(surface_lifecycle) is not bool:raise ValueError('explicit lifecycle mode required')
        if type(surface_input) is not bool or surface_input and not surface_lifecycle:raise ValueError('input requires lifecycle')
        super().__init__(keyboard_batch)
        self.surface_input=surface_input
        if surface_input:
            self.case=application_frames.compact_scenario(self.case)
            self.payload=self.case.sent
        self.pointer_done=False
        self.surface_barriers=lifecycle_barriers(self.case.sent) if surface_lifecycle else {}
        self.observed_surfaces=set()
    def blocked(self):
        return (self.step==self.sustained_barrier and not self.pointer_done or
                self.step in self.surface_barriers and self.step not in self.observed_surfaces)
    def send_ready(self):
        if self.blocked():return
        return super().send_ready()
    def wrap(self, connection):
        owner=self
        class DeviceSocket(local.KeyboardSocket):
            def send(self, data):
                if owner.blocked():return 0
                return super().send(data)
        def inject(codes):
            if self.inject is None:raise ValueError('unbound keyboard')
            self.inject(codes);self.keyboard_bytes+=1
        self.sock=DeviceSocket(connection,inject)

class SurfaceProbe:
    def __init__(self,work):
        self.work=work;self.step=None;self.deadline=0;self.sample=0;self.evidence=[]
    def tick(self,client,interaction,debug):
        step=interaction.step
        if step not in interaction.surface_barriers or step in interaction.observed_surfaces:return
        now=time.monotonic()
        if self.step!=step:
            self.step=step;self.deadline=now+12;self.sample=0
        if now>self.deadline:raise TimeoutError(f'surface lifecycle step {step} not observed')
        _,output=local.native_console.split_output(bytes(interaction.received),partial=True)
        if not interaction.expected.startswith(output):raise ValueError('lifecycle transcript differs')
        if output!=interaction.expected or now<self.sample:return
        barrier=interaction.surface_barriers[step]
        event=barrier['event']
        markers=local.native_session.extract_markers(debug)
        observations=[local.apps.parse(m,event) for m in markers if m.startswith('POOLEOS:APPS '+event+' ')]
        identity=(barrier['task'],barrier['generation'])
        if identity not in {(m['task'],m['generation']) for m in observations}:return
        self.sample=now+.15
        path=self.work/f'lifecycle-{len(self.evidence):02}.ppm'
        client.execute('screendump',{'filename':str(path),'format':'ppm'})
        try:
            pixels=frames.inspect_ppm(path.read_bytes(),expected=barrier['visible'])
            if interaction.surface_input and event=='ADMIT':
                pixels['fresh_draft']=application_frames.inspect_rows(path.read_bytes(),{barrier['task']-4:{6:'',7:''}})
        except ValueError:return
        self.evidence.append(dict(step=step,**barrier,frame_sha256=local.digest(path),pixels=pixels))
        interaction.observed_surfaces.add(step)

def bounded_motion(x,y,target_x,target_y):
    return max(-96,min(96,target_x-x)),max(-96,min(96,target_y-y))

def pointer_steps(w,h):
    if not 1000<=w<=4096 or not 600<=h<=2160:raise ValueError('mouse qualification viewport outside profile')
    x,y=w-320,72
    # x/y, left button, and independent expected pixel after the event.
    return [
        (x+100,y+12,False,None),
        (x+100,y+12,True,(x,y,'508D78')),
        (x+60,y+44,True,(x-40,y+32,'508D78')),
        (x+60,y+44,False,(x-38,y+62,'F8FAF9')),
        (x+248,y+44,False,None),
        (x+248,y+44,True,(x-40,y+32,'D3DFDF')),
        (x+248,y+44,False,None),
        (200,h-24,False,None),
        (200,h-24,True,(x-40,y+32,'508D78')),
        (200,h-24,False,None),
        (x+60,y+44,False,None),
        (x+60,y+44,True,None),
        (x+100,y+12,True,(x,y,'508D78')),
        (x+100,y+12,False,None),
        (40,100,False,None),
        (40,100,True,(16,48,'508D78')),
        (40,100,False,None),
    ]

class PointerProbe:
    def __init__(self, work, surface_input=False):
        self.work=work;self.steps=None;self.index=0;self.pending=False
        self.deadline=0;self.sample=0;self.discard_dispatch=None;self.evidence=[];self.movements=[]
        self.application=InputProbe(work) if surface_input else None
    def tick(self, client, interaction, debug):
        if interaction.pointer_done or not interaction.sustained_evidence:return
        now=time.monotonic()
        if self.steps is None:
            path=self.work/'pointer-before.ppm'
            client.execute('screendump',{'filename':str(path),'format':'ppm'})
            frames.inspect_ppm(path.read_bytes())
            p=path.read_bytes().split(b'\n',3)
            self.w,self.h=map(int,p[1].split());self.steps=pointer_steps(self.w,self.h)
            self.x,self.y,self.left=self.w//2,self.h//2,False
        if self.index==14:
            if self.application is not None:
                self.application.tick(client,interaction,self)
                if not self.application.done:return
            else:
                runs=[local.apps.parse(m,'RUN') for m in local.native_session.extract_markers(debug) if m.startswith('POOLEOS:APPS RUN ')]
                if not runs:return
                if self.discard_dispatch is None:
                    interaction.inject(local.scancodes(b'z'))
                    self.discard_dispatch=runs[-1]['dispatches'];self.deadline=now+12
                    return
                if runs[-1]['dispatches']<self.discard_dispatch+256:
                    if now>self.deadline:raise TimeoutError('focused surface key isolation made no progress')
                    return
        target_x,target_y,target_left,expected=self.steps[self.index]
        if not self.pending:
            dx,dy=bounded_motion(self.x,self.y,target_x,target_y)
            x,y=self.x+dx,self.y+dy
            left=target_left if (x,y)==(target_x,target_y) else self.left
            events=[{'type':'rel','data':{'axis':'x','value':dx}}, {'type':'rel','data':{'axis':'y','value':dy}}]
            if left!=self.left:events.append({'type':'btn','data':{'button':'left','down':left}})
            client.execute('input-send-event',{'events':events})
            self.x,self.y,self.left=x,y,left;self.pending=True;self.deadline=now+12;self.sample=now+.15
            return
        if now<self.sample:return
        self.sample=now+.15
        x,y,left=self.x,self.y,self.left
        arrived=(x,y,left)==(target_x,target_y,target_left)
        path=self.work/f'pointer-{self.index:02}-{len(self.movements):02}.ppm'
        client.execute('screendump',{'filename':str(path),'format':'ppm'})
        p=path.read_bytes().split(b'\n',3)
        if len(p)!=4 or p[0]!=b'P6' or p[2]!=b'255' or list(map(int,p[1].split()))!=[self.w,self.h] or len(p[3])!=self.w*self.h*3:
            raise ValueError('invalid pointer screenshot')
        def pixel(xx,yy):
            a=(yy*self.w+xx)*3;return p[3][a:a+3]
        ok=(pixel(x,y)==bytes.fromhex('172B24') and pixel(x+1,y+6)==b'\xff\xff\xff' and pixel(x,y+17)==bytes.fromhex('172B24'))
        if expected and arrived:ok=ok and pixel(expected[0],expected[1])==bytes.fromhex(expected[2])
        if not ok:
            if now>self.deadline:raise TimeoutError(f'mouse step {self.index} pixels not observed')
            return
        self.movements.append(dict(step=self.index,x=x,y=y,left=left,frame_sha256=local.digest(path)))
        if not arrived:
            self.pending=False;return
        self.evidence.append(dict(step=self.index,x=x,y=y,left=left,frame_sha256=local.digest(path),expected_pixel=expected))
        self.index+=1;self.pending=False
        if self.index==len(self.steps):interaction.pointer_done=True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--keyboard-batch',type=int,choices=(1,4),default=1)
    p.add_argument('--backend',choices=('qemu','virtualbox'),default='qemu')
    p.add_argument('--virtualbox',type=Path)
    p.add_argument('--visible',action='store_true')
    args=p.parse_args();report,iso,disk=local.check_preview(args.receipt.resolve())
    if args.visible and args.backend!='virtualbox':p.error('visible mode is VirtualBox-only')
    if args.backend=='virtualbox' and args.virtualbox is None:p.error('explicit VirtualBox executable required')
    if report.get('window_surfaces') is not True:raise ValueError('qualified windows profile required')
    work=args.work_dir.resolve()
    if not work.is_relative_to(ROOT/'outputs') or work==ROOT/'outputs':raise ValueError('new workspace output required')
    work.mkdir(parents=True,exist_ok=False)
    lifecycle=report.get('surface_lifecycle',False)
    application_input=report.get('surface_input',False)
    before=local.source.source_bindings();interaction=WindowInteraction(args.keyboard_batch,lifecycle,application_input);pointer=PointerProbe(work,application_input)
    surfaces=SurfaceProbe(work)
    result=dict(cycle=300 if application_input else 299 if lifecycle else 297,contract_id='PWS1',surface_lifecycle=lifecycle,surface_input=application_input,status='fail',source_bindings=before,iso_sha256=local.digest(iso),
        backend=args.backend,visible=args.visible,serial_input_bytes=0,physical_hardware_tested=False,production_ready=False,guest_bound_seconds=240)
    vbox_pointer=None
    started=time.monotonic()
    try:
        shared=local.qualification.shared
        if args.backend=='qemu':
            lock,base=shared.tier0.validate_contracts(ROOT)
            qemu=shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT,ROOT)
            shared.tier0.verify_local_launch_runtime(lock,qemu,ROOT)
            def control(client,debug):
                def inject(codes):
                    client.execute('input-send-event',{'events':[{'type':'key','data':{'down':not bool(c&128),'key':{'type':'number','data':c&127}}} for c in codes]})
                interaction.inject=inject;pointer.tick(client,interaction,debug);surfaces.tick(client,interaction,debug)
            run,_,_=shared.boot._execute_once('native-windows',lock,local.optical.optical_profile(base),qemu,iso,work,240,
                marker_validator=lambda m:local.apps.validate_markers(m,file_waits=True,windows=True,window_capacity=report.get('window_capacity',False),surface_lifecycle=lifecycle),marker_extractor=local.native_session.extract_markers,
                hpet_msi=True,pause_on_completion=True,console_port=interaction.port,console_poll=interaction.poll,
                capture_log_limit_bytes=local.LOG_LIMIT,guest_control=control,frame_validator=lifecycle_frames.inspect_ppm if lifecycle else frames.inspect_ppm)
        else:
            from runtime.native_virtualbox_mouse import PointerClient
            def control(owner,debug):
                nonlocal vbox_pointer
                if not interaction.sustained_evidence:return
                if vbox_pointer is None:vbox_pointer=PointerClient(owner,args.virtualbox.resolve())
                pointer.tick(vbox_pointer,interaction,debug);surfaces.tick(vbox_pointer,interaction,debug)
            local.vbox_run(report,iso,work,interaction,result,args.virtualbox.resolve(),args.visible,control)
            run=result['run']
            if vbox_pointer is None:raise ValueError('pointer API was not reached')
            vbox_pointer.check_shell()
        _,output=local.native_console.split_output(bytes(interaction.received))
        if not interaction.pointer_done or interaction.sent!=len(interaction.case.sent) or output!=interaction.case.expected or interaction.keyboard_bytes!=interaction.sent:
            raise ValueError('inexact native mouse/keyboard interaction')
        if interaction.observed_surfaces!=set(interaction.surface_barriers) or len(surfaces.evidence)!=(6 if lifecycle else 0):
            raise ValueError('incomplete surface lifecycle observations')
        if application_input and (not pointer.application.done or len(pointer.application.evidence)!=len(pointer.application.actions)):
            raise ValueError('incomplete native application input challenge')
        prefix=run['marker_summary']['transfer_prefix']
        shared.load.validate_oracle_binding(prefix['boot_prefix'],shared.load.inspect_media_bytes(disk),run['pbp1_transcript'])
        result.update(status='pass',run=run,mouse_interaction_verified=True,drag_minimize_restore_verified=True,
            focus_routing_verified=True,focused_nonterminal_keys_discarded=0 if application_input else 1,keyboard_input_bytes=interaction.keyboard_bytes,
            isolated_application_input_verified=application_input,
            exact_interaction=True,sustained_window=interaction.sustained_evidence,
            hostile_marker_cases_rejected=local.apps.negative_controls(run['markers'],file_waits=True,windows=True,window_capacity=report.get('window_capacity',False),surface_lifecycle=lifecycle))
    except Exception as e:result['failure']=f'{type(e).__name__}: {e}'
    finally:
        interaction.close()
        (work/'keyboard-input.bin').write_bytes(interaction.case.sent[:interaction.sent])
        (work/'console-output.bin').write_bytes(bytes(interaction.received))
        result.update(pointer_steps=pointer.evidence,movement_samples=pointer.movements,maximum_injected_axis_delta=96,
            surface_observations=surfaces.evidence,surface_observation_bound_seconds=12,
            keyboard_batch=interaction.keyboard_batch,batches=interaction.batches,keyboard_input_bytes=interaction.keyboard_bytes,
            unpaced_burst_input_qualified=False,source_unchanged=before==local.source.source_bindings(),
            iso_unchanged=local.digest(iso)==result['iso_sha256'],elapsed_seconds=round(time.monotonic()-started,3))
        if vbox_pointer is not None:
            result['pointer_api_diagnostics']=vbox_pointer.diagnostics
            result['pointer_api']=dict(contract_id='PVBMOUSE1',powershell_sha256=vbox_pointer.shell_hash,
                events=vbox_pointer.records,failed=vbox_pointer.failed,host_cursor_moved=False,unlocked_per_event=True,
                api_bound_seconds=5,maximum_events=96)
        if pointer.application is not None:
            result['application_input']=dict(actions=pointer.application.evidence,scancodes=pointer.application.codes,
                movements=pointer.application.movements,captures=pointer.application.captures,maximum_captures=256,
                action_bound_seconds=12,complete=pointer.application.done,app_owned_draft_bytes=48)
        if not result['source_unchanged'] or not result['iso_unchanged']:result['status']='fail'
        (work/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],result.get('failure',''),flush=True)
    return int(result['status']!='pass')

if __name__=='__main__':raise SystemExit(main())
