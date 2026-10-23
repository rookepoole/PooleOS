"""Observe real emulated keyboard input, CPL3 apps and native framebuffer output."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import socket
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import native_app_session as apps, native_console, native_session, native_userspace_iso as optical
from runtime import native_virtualbox as vbox, native_live_boot_handoff as handoff
from runtime import native_local_console as frames
from runtime import native_windows as window_frames
from runtime import native_surface_lifecycle as lifecycle_frames
from tools import qualify_native_app_session as qualification, qualify_native_user_entry as source
from tools.launch_native_userspace_iso import check_preview, LOG_LIMIT
from tools.launch_native_virtualbox import listener_socket
from tools.native_build_space import require_space

# Independent host-side US key -> set-1 make code. Break codes are explicit.
KEYS={}
for start,chars in [(2,'1234567890-='),(16,'qwertyuiop[]'),(30,"asdfghjkl;'`"),(44,'zxcvbnm,./')]:
    KEYS.update({c:(start+i,False) for i,c in enumerate(chars)})
KEYS.update({' ':(57,False),'\\':(43,False),'\r':(28,False),'\x08':(14,False)})
KEYS.update({c.upper():(code,True) for c,(code,_) in list(KEYS.items()) if c.isalpha()})
for a,b in zip('1234567890-=[];\'`\\,./','!@#$%^&*()_+{}:"~|<>?'):
    KEYS[b]=(KEYS[a][0],True)

def scancodes(byte: bytes) -> list[int]:
    if len(byte)!=1 or chr(byte[0]) not in KEYS: raise ValueError('unsupported keyboard challenge byte')
    code,shift=KEYS[chr(byte[0])]
    return ([0x2a] if shift else [])+[code,code|0x80]+([0xaa] if shift else [])

class KeyboardSocket:
    """Receive COM2 for the oracle; send() injects device keys, never serial bytes."""
    def __init__(self,connection,inject): self.connection,self.inject=connection,inject
    def recv(self,n): return self.connection.recv(n)
    def send(self,data):
        codes=scancodes(data)
        self.inject(codes)
        return len(data)
    def close(self): self.connection.close()

class Interaction(qualification.Interaction):
    def __init__(self, keyboard_batch=1):
        if keyboard_batch not in (1,4): raise ValueError('keyboard batch must be1 or4')
        case=apps.scenario(secrets.token_hex(8))
        # Exercise shifted letters, punctuation and editing without changing app lifetimes.
        extra=[]
        for b in b'echo PooleOX': extra.append((bytes([b]),bytes([b])))
        extra.append((b'\x08',b'\x08 \x08'))
        for b in b'S!':extra.append((bytes([b]),bytes([b])))
        extra.append((b'\r',b'\r\nPooleOS!\r\n'+apps.shell.PROMPT))
        case=apps.shell.Scenario('native-keyboard',case.nonce,case.steps[:-5]+tuple(extra)+case.steps[-5:])
        super().__init__(case,sustained=True)
        self.inject=None
        self.keyboard_bytes=0
        self.keyboard_batch=keyboard_batch
        self.batches=[]
    def send_ready(self):
        if self.keyboard_batch==1:
            return super().send_ready()
        group=[]
        for byte,response in self.case.steps[self.step:self.step+self.keyboard_batch]:
            group.append((byte,response))
            if byte==b'\r':break
        if not group or self.inject is None:raise ValueError('unbound batch challenge')
        codes=[code for byte,_ in group for code in scancodes(byte)]
        self.inject(codes)
        self.batches.append(dict(start=self.step,bytes=len(group),scancodes=len(codes)))
        self.keyboard_bytes+=len(group);self.sent+=len(group);self.step+=len(group)
        self.expected+=b''.join(response for _,response in group)
    def wrap(self,connection):
        def inject(codes):
            if self.inject is None:raise ValueError('guest keyboard is not bound')
            self.inject(codes)
            self.keyboard_bytes+=1
        self.sock=KeyboardSocket(connection,inject)
    def poll(self,debug):
        if self.sock is None:
            connection=socket.create_connection(('127.0.0.1',self.port),timeout=2)
            connection.setblocking(False)
            self.wrap(connection)
        return super().poll(debug)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def qemu_run(report,iso,work,interaction,result):
    options=apps.profile_options(report)
    windows=report.get('window_surfaces',False)
    pixels=lifecycle_frames if report.get('surface_lifecycle') else window_frames if windows else frames
    shared=qualification.shared
    lock,base=shared.tier0.validate_contracts(ROOT)
    qemu=shared.tier0._require_workspace_tool_path(shared.tier0.DEFAULT_QEMU_ROOT,ROOT)
    shared.tier0.verify_local_launch_runtime(lock,qemu,ROOT)
    captured=False
    def control(client,debug):
        nonlocal captured
        def inject(codes):
            # QEMU's number form is a set-1 key number; release is an event, not bit7.
            client.execute('input-send-event',{'events':[
                {'type':'key','data':{'down':not bool(c&0x80),'key':{'type':'number','data':c&0x7f}}} for c in codes]})
        interaction.inject=inject
        if not captured and interaction.step>=len(b'status text\rtext /readme.txt\rstart text\rstart numbers\r'):
            client.execute('screendump',{'filename':str(work/'initial.ppm'),'format':'ppm'})
            captured=True
    run,_,_=shared.boot._execute_once('native-keyboard',lock,optical.optical_profile(base),qemu,iso,work,240,
        marker_validator=lambda m:apps.validate_markers(m,**options),marker_extractor=native_session.extract_markers,
        hpet_msi=True,pause_on_completion=True,console_port=interaction.port,console_poll=interaction.poll,
        capture_log_limit_bytes=LOG_LIMIT,guest_control=control,frame_validator=pixels.inspect_ppm)
    if not captured:raise ValueError('initial frame missing')
    result.update(run=run,initial_frame_sha256=digest(work/'initial.ppm'),final_frame_sha256=digest(work/'pooleboot-frame.ppm'),
        final_frame_pixels=pixels.inspect_ppm((work/'pooleboot-frame.ppm').read_bytes()))

def vbox_run(report,iso,work,interaction,result,executable,visible=False,control=None):
    options=apps.profile_options(report)
    windows=report.get('window_surfaces',False)
    pixels=lifecycle_frames if report.get('surface_lifecycle') else window_frames if windows else frames
    profile=json.loads((ROOT/'specs/native-virtualbox-preview-profile.json').read_bytes())
    hashes=vbox.verify_runtime(executable,profile,visible=visible)
    command=vbox.Command(executable)
    owner=vbox.OwnedVm(work,command)
    listener=listener_socket()
    result.update(vm_uuid=owner.identity,vm_name=owner.name,tool_hashes=hashes)
    try:
        if owner.checked('--version').strip()!=profile['version']:raise ValueError('runtime version differs')
        owner.create(iso,listener.getsockname()[1]);owner.start(visible=visible)
        def inject(codes):owner.checked('controlvm',owner.identity,'keyboardputscancode',*[f'{v:02x}' for v in codes])
        interaction.inject=inject
        deadline=time.monotonic()+240
        captured=False
        while time.monotonic()<deadline:
            if interaction.sock is None:
                try:connection,address=listener.accept()
                except BlockingIOError:pass
                else:
                    if address[0]!='127.0.0.1':connection.close();raise ValueError('nonloopback console')
                    connection.setblocking(False);interaction.wrap(connection)
            path=work/'com1.log'
            log=vbox.serial_payload(vbox.bounded_read(path,LOG_LIMIT),partial=True) if path.exists() else b''
            if b'PANIC' in log or b' DENIED stage=' in log or b'POOLEBOOT/0.1 ERROR' in log:raise ValueError('native kernel failure')
            if interaction.sock is not None and interaction.poll(log):
                owner.pause()
                log=vbox.serial_payload(vbox.bounded_read(path,LOG_LIMIT))
                markers=native_session.extract_markers(log)
                result['run']=dict(markers=markers,marker_summary=apps.validate_markers(markers,**options),pbp1_transcript=handoff.extract_transcript(log).summary)
                owner.checked('controlvm',owner.identity,'screenshotpng',work/'final.png')
                result.update(initial_frame_sha256=digest(work/'initial.png'),final_frame_sha256=digest(work/'final.png'))
                from PIL import Image
                with Image.open(work/'final.png') as frame:
                    if not 320<=frame.width<=4096 or not 200<=frame.height<=2160:raise ValueError('invalid native frame size')
                    result['final_frame_pixels']=pixels.inspect_rgb(frame.width,frame.height,frame.convert('RGB').tobytes())
                return
            if interaction.step>=len(b'status text\rtext /readme.txt\rstart text\rstart numbers\r') and not captured:
                owner.checked('controlvm',owner.identity,'screenshotpng',work/'initial.png');captured=True
            if control is not None:control(owner,log)
            time.sleep(.01)
        raise TimeoutError('native keyboard session exceeded 240 seconds')
    finally:
        listener.close()
        result['cleanup']=owner.cleanup()
        result['commands']=command.records
        result['runtime_unchanged']=hashes==vbox.verify_runtime(executable,profile,visible=visible)
        if not result['runtime_unchanged'] or not all(result['cleanup'][k] for k in ('stopped','unregistered','prior_registrations_unchanged')):
            raise ValueError('runtime or owned VM cleanup unconfirmed')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--backend',choices=['qemu','virtualbox'],required=True);p.add_argument('--virtualbox',type=Path)
    p.add_argument('--visible',action='store_true')
    p.add_argument('--keyboard-batch',type=int,choices=(1,4),default=1)
    args=p.parse_args()
    if args.visible and args.backend!='virtualbox':p.error('visible mode is VirtualBox-only')
    report,iso,disk=check_preview(args.receipt.resolve())
    options=apps.profile_options(report)
    if report.get('local_console') is not True:raise ValueError('native local-console ISO required')
    windows=report.get('window_surfaces',False)
    if args.keyboard_batch!=1 and not windows:raise ValueError('burst input requires window FIFO profile')
    work=args.work_dir.resolve()
    if not work.is_relative_to(ROOT/'outputs') or work==ROOT/'outputs':raise ValueError('new workspace output required')
    storage=require_space(work)
    work.mkdir(parents=True,exist_ok=False)
    before=source.source_bindings();interaction=Interaction(args.keyboard_batch)
    result=dict(contract_id='PWS1' if windows else 'PDISPLAY1',cycle=297,status='fail',source_bindings=before,backend=args.backend,
        guest_bound_seconds=240,iso_sha256=digest(iso),serial_input_bytes=0,physical_keyboard_tested=False,
        visible=args.visible,
        window_surfaces=windows,mouse_interaction_verified=False,graphical_desktop=False,production_ready=False,
        application_profile=options,storage_preflight=storage)
    started=time.monotonic()
    try:
        if args.backend=='qemu':qemu_run(report,iso,work,interaction,result)
        else:
            if args.virtualbox is None:raise ValueError('explicit installed VirtualBox executable required')
            vbox_run(report,iso,work,interaction,result,args.virtualbox.resolve(),args.visible)
        _,output=native_console.split_output(bytes(interaction.received))
        if interaction.sent!=len(interaction.case.sent) or output!=interaction.case.expected or interaction.keyboard_bytes!=interaction.sent:
            raise ValueError('keyboard interaction differs from independent challenge')
        if not interaction.sustained_evidence or result['initial_frame_sha256']==result['final_frame_sha256']:
            raise ValueError('native progress or changed frame missing')
        prefix=result['run']['marker_summary']['transfer_prefix']
        qualification.shared.load.validate_oracle_binding(prefix['boot_prefix'],qualification.shared.load.inspect_media_bytes(disk),result['run']['pbp1_transcript'])
        result.update(status='pass',keyboard_input_bytes=interaction.keyboard_bytes,exact_interaction=True,
            sustained_window=interaction.sustained_evidence,framebuffer_changed=True,
            hostile_marker_cases_rejected=apps.negative_controls(result['run']['markers'],**options))
    except Exception as e:result['failure']=f'{type(e).__name__}: {e}'
    finally:
        interaction.close()
        (work/'keyboard-input.bin').write_bytes(interaction.case.sent[:interaction.sent])
        (work/'console-output.bin').write_bytes(bytes(interaction.received))
        result.update(keyboard_batch=interaction.keyboard_batch,batches=interaction.batches,
            source_unchanged=before==source.source_bindings(),iso_unchanged=digest(iso)==result['iso_sha256'],elapsed_seconds=round(time.monotonic()-started,3))
        if not result['source_unchanged'] or not result['iso_unchanged']:result['status']='fail'
        (work/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],result.get('failure',''),flush=True)
    return int(result['status']!='pass')

if __name__=='__main__':raise SystemExit(main())
